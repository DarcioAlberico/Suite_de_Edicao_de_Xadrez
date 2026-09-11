"""Where the LLM meets the recognition pipeline: the caption band, and only it.

The vision pipeline already reads a page and hands back one
``chess_diagram_ocr.pdf_text.DiagramContext`` per diagram: the caption text, the
side to move when the page *stated* it, the printed exercise number, players,
event, year. What it does not carry is the **stipulation** -- "mate in 2",
"White to play and win" -- because nothing in the pipeline extracts one.

That gap is this module. It is deliberately the only seam between the LLM and
the recognition path, and it is shaped so the LLM cannot damage anything:

**It adds a field, it never edits one.** A :class:`CaptionEnrichment` sits
*beside* the ``DiagramContext``; the context itself is frozen and is returned
untouched. There is no code path here that writes a FEN, a side to move, or an
exercise number back into the pipeline's own data.

**The text layer wins every disagreement.** ``DiagramContext.side_to_move``
comes from the printed page with confidence 1.0. When the extractor disagrees,
the disagreement is *recorded* (:attr:`CaptionEnrichment.side_conflict`) and the
extractor's answer is dropped. Same for the exercise number. This is the
ADR-0004/F11 rule -- the LLM may lower confidence or raise a flag, never
overwrite a high-confidence result -- applied to the one place it can reach.

**The model is off by default, and the reason is measured.** F11 cycle 2
measured ``extract_stipulation`` over 233 hand-labelled captions from the
corpus. See :data:`LLM_ENRICHMENT_DEFAULT` for the number that set the default
and ``docs/quality/F11_REPORT_C2.md`` for the table it came from.

Nothing here raises. With Ollama absent, with the model absent, with the trunk
absent, every function returns the deterministic answer or ``None`` and the
application behaves exactly as it does today.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from caissa.llm.runtime import CancellationToken, LlmRuntime
from caissa.llm.tasks import Stipulation, extract_stipulation

__all__ = [
    "LLM_ENRICHMENT_DEFAULT",
    "CaptionEnrichment",
    "enrich_contexts",
    "stipulation_for_context",
    "stipulations_for_pdf_page",
]

logger = logging.getLogger(__name__)

#: Whether the model is consulted when the deterministic matcher comes up empty.
#:
#: **False**, and that is a measurement, not a preference: on the 233 labelled
#: captions of F11 cycle 2 the deterministic matcher abstains far more often
#: than ``gemma4:e4b-it-qat`` does on captions that state no stipulation. The
#: table is in ``docs/quality/F11_REPORT_C2.md`` 3. A fabricated "mate in 3"
#: under a game position is worse than no stipulation at all, because the user
#: cannot see that it was invented. Callers that want the model anyway pass
#: ``allow_llm=True`` explicitly, and get the audit log with it.
LLM_ENRICHMENT_DEFAULT: Final = False


@dataclass(frozen=True, slots=True)
class CaptionEnrichment:
    """What was learned about one diagram's caption, and how much to trust it.

    Attributes:
        index: Position of the diagram on the page, matching the context list.
        stipulation: The extracted stipulation, or ``None`` when the caption
            states none. ``None`` means "the caption does not say", never
            "there is no stipulation".
        side_conflict: The extractor named a side to move that contradicts the
            printed page. The page wins; this records that they disagreed so the
            review panel can show it.
        number_conflict: Same, for the printed exercise number.
        used_llm: Whether a model produced this. ``False`` means the
            deterministic matcher did, and the answer is exact where it fired.
        detail: pt-BR note for the review panel.
    """

    index: int
    stipulation: Stipulation | None = None
    side_conflict: bool = False
    number_conflict: bool = False
    used_llm: bool = False
    detail: str = ""

    @property
    def has_stipulation(self) -> bool:
        """Whether a task was actually read off the caption."""
        return self.stipulation is not None and self.stipulation.kind != "unknown"

    @property
    def needs_review(self) -> bool:
        """Whether a human should look at this one before it is trusted."""
        return self.side_conflict or self.number_conflict or (
            self.used_llm and self.has_stipulation
        )


def _context_side(context: Any) -> str | None:
    """``"w"``/``"b"``/``None`` from a ``DiagramContext``, defensively.

    ``side_to_move`` is a ``chess.Color`` (a bool) in the trunk, and ``None``
    when the page did not say. ``bool`` is not a safe thing to test for
    truthiness here -- ``False`` means *black*, not *absent* -- which is exactly
    the bug this function exists to make impossible.
    """
    side = getattr(context, "side_to_move", None)
    if side is None:
        return None
    return "w" if bool(side) else "b"


def stipulation_for_context(
    context: Any,
    *,
    runtime: LlmRuntime | None = None,
    allow_llm: bool = LLM_ENRICHMENT_DEFAULT,
    index: int = 0,
    timeout_s: float = 45.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> CaptionEnrichment:
    """Read the stipulation off one diagram's caption band.

    Args:
        context: A ``chess_diagram_ocr.pdf_text.DiagramContext``, or anything
            with ``caption``, ``side_to_move`` and ``exercise_number``. Duck
            typed on purpose: this module must not import the trunk, so that
            ``caissa.llm`` stays importable without it.
        runtime: Backend override.
        allow_llm: Consult the model for captions the matcher cannot classify.
            Defaults to :data:`LLM_ENRICHMENT_DEFAULT`.
        index: Diagram position on the page, copied into the result.
        timeout_s: Wall-clock budget for the model, if it is consulted.
        cancel: Cancellation token.
        seed: Fixed seed.

    Returns:
        A :class:`CaptionEnrichment`. Never raises, never mutates ``context``.
    """
    caption = str(getattr(context, "caption", "") or "")
    if not caption.strip():
        return CaptionEnrichment(index=index, detail="sem legenda proxima ao diagrama")

    try:
        found = extract_stipulation(
            caption,
            runtime=runtime,
            allow_llm=allow_llm,
            timeout_s=timeout_s,
            cancel=cancel,
            seed=seed,
        )
    except Exception as exc:  # noqa: BLE001 - an optional subsystem may not break a page
        logger.warning("extracao de estipulacao falhou; legenda mantida como esta: %s", exc)
        return CaptionEnrichment(index=index, detail=f"extracao falhou ({type(exc).__name__})")

    if found is None:
        return CaptionEnrichment(index=index, detail="legenda nao declara estipulacao")

    printed_side = _context_side(context)
    printed_number = getattr(context, "exercise_number", None)
    side_conflict = (
        printed_side is not None
        and found.side_to_move is not None
        and found.side_to_move != printed_side
    )
    number_conflict = (
        printed_number is not None
        and found.diagram_number is not None
        and int(printed_number) != int(found.diagram_number)
    )

    # The printed page is the authority on both of these. Where they disagree the
    # extractor's value is dropped, not merged: a "maybe black" next to a printed
    # "White to play" is not extra information, it is noise with a flag on it.
    resolved = Stipulation(
        kind=found.kind,
        moves=found.moves,
        side_to_move=printed_side if printed_side is not None else found.side_to_move,
        diagram_number=(
            int(printed_number) if printed_number is not None else found.diagram_number
        ),
        language=found.language,
        confidence=found.confidence * (0.5 if (side_conflict or number_conflict) else 1.0),
        source=found.source,
        raw=found.raw,
    )
    detail = ""
    if side_conflict:
        detail = (
            f"a legenda impressa diz '{printed_side}' e a extracao disse "
            f"'{found.side_to_move}'; a pagina venceu"
        )
    elif number_conflict:
        detail = (
            f"numero impresso {printed_number} difere do extraido "
            f"{found.diagram_number}; a pagina venceu"
        )
    return CaptionEnrichment(
        index=index,
        stipulation=resolved,
        side_conflict=side_conflict,
        number_conflict=number_conflict,
        used_llm=found.source == "llm",
        detail=detail,
    )


def enrich_contexts(
    contexts: Any,
    *,
    runtime: LlmRuntime | None = None,
    allow_llm: bool = LLM_ENRICHMENT_DEFAULT,
    timeout_s: float = 45.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> tuple[CaptionEnrichment, ...]:
    """Run :func:`stipulation_for_context` over one page's contexts.

    This is the whole integration surface. A caller that already has the page's
    ``list[DiagramContext]`` -- ``caissa.vision.classify.page`` builds one from
    ``contexts_for_pdf_page`` -- adds one line::

        from caissa.llm.pipeline import enrich_contexts
        stipulations = enrich_contexts(contexts)

    and gets a parallel tuple it can show, log or ignore. Nothing upstream
    changes, and with no model installed the call costs one regex pass.
    """
    return tuple(
        stipulation_for_context(
            context,
            runtime=runtime,
            allow_llm=allow_llm,
            index=index,
            timeout_s=timeout_s,
            cancel=cancel,
            seed=seed,
        )
        for index, context in enumerate(contexts or ())
    )


def stipulations_for_pdf_page(
    pdf_source: Any,
    page_index: int,
    bboxes: Any,
    *,
    runtime: LlmRuntime | None = None,
    allow_llm: bool = LLM_ENRICHMENT_DEFAULT,
    timeout_s: float = 45.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> tuple[CaptionEnrichment, ...]:
    """Stipulations for one PDF page's diagrams, reading the caption band itself.

    The self-sufficient entry point: a caller that has a PDF and the diagram
    boxes -- the exporter, a CLI, the review panel -- gets stipulations without
    the recognition path changing at all. It reads the caption band through the
    trunk's own ``contexts_for_pdf_page``, which is the same function
    ``caissa.vision.classify.page`` uses, so the caption text is byte-identical
    to what recognition saw.

    Args:
        pdf_source: Path, bytes, or an already-open ``OpenPdf``.
        page_index: Zero-based page.
        bboxes: Diagram boxes in PDF coordinates, in reading order --
            ``[candidate.bbox_pdf for candidate in candidates]``.
        runtime: Backend override.
        allow_llm: Consult the model for captions the matcher cannot classify.
        timeout_s: Wall-clock budget per model call.
        cancel: Cancellation token.
        seed: Fixed seed.

    Returns:
        One :class:`CaptionEnrichment` per box, in the same order. An empty
        tuple when the trunk is not installed or the page cannot be read --
        this is an optional subsystem and it degrades rather than raising.
    """
    if not bboxes:
        return ()
    try:
        from caissa.vision.classify.cvoff import ensure_cvoff_on_path  # noqa: PLC0415

        ensure_cvoff_on_path()
        from chess_diagram_ocr.pdf_text import contexts_for_pdf_page  # noqa: PLC0415

        contexts = contexts_for_pdf_page(pdf_source, page_index, list(bboxes))
    except Exception as exc:  # noqa: BLE001 - optional; a missing trunk is not fatal
        logger.info("faixa de legenda indisponivel na pagina %s: %s", page_index, exc)
        return ()
    return enrich_contexts(
        contexts,
        runtime=runtime,
        allow_llm=allow_llm,
        timeout_s=timeout_s,
        cancel=cancel,
        seed=seed,
    )
