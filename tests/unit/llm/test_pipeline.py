"""The caption-band seam: it may add a field, and it may not touch one.

These tests are the executable form of the F11 guardrail. They do not check
that the enrichment is *good* -- that is what ``benchmarks/bench_llm.py`` and
``docs/quality/F11_REPORT_C2.md`` are for. They check that it is *bounded*: the
printed page wins every disagreement, the context is never mutated, and nothing
here raises when the model is missing.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, dataclass

import pytest

from caissa.llm.pipeline import (
    LLM_ENRICHMENT_DEFAULT,
    CaptionEnrichment,
    enrich_contexts,
    stipulation_for_context,
    stipulations_for_pdf_page,
)
from caissa.llm.runtime import NullRuntime

from .conftest import FakeRuntime


@dataclass(frozen=True)
class FakeContext:
    """Stands in for ``chess_diagram_ocr.pdf_text.DiagramContext``.

    Frozen for the same reason the real one is: so a test that tried to write
    through it would fail loudly rather than pass quietly.
    """

    caption: str = ""
    side_to_move: bool | None = None
    exercise_number: int | None = None


def stipulation_reply(
    kind: str = "mate",
    moves: int | None = 2,
    side: str | None = "w",
    number: int | None = None,
) -> str:
    """Serialise a well-formed ``extract_stipulation`` reply."""
    return json.dumps(
        {
            "kind": kind,
            "moves": moves,
            "side_to_move": side,
            "diagram_number": number,
            "language": "pt",
            "confidence": 0.9,
        }
    )


# --------------------------------------------------------------------------- #
# The application must work with no model at all
# --------------------------------------------------------------------------- #


def test_the_model_is_off_by_default() -> None:
    """The default is measured, not preferred. See F11_REPORT_C2.md."""
    assert LLM_ENRICHMENT_DEFAULT is False


def test_deterministic_path_answers_without_any_runtime() -> None:
    """A caption the matcher understands never reaches a model."""
    found = stipulation_for_context(
        FakeContext(caption="Diagrama 12. Mate em 2 lances. Brancas jogam."),
        runtime=NullRuntime(),
    )
    assert found.stipulation is not None
    assert found.stipulation.kind == "mate"
    assert found.stipulation.moves == 2
    assert found.used_llm is False
    assert found.stipulation.source == "rules"


def test_absent_model_degrades_to_none_not_to_an_error() -> None:
    """An unclassifiable caption with no model is ``None``, never an exception."""
    found = stipulation_for_context(
        FakeContext(caption="Bremen 1998 Hickl - Yusupov"),
        runtime=NullRuntime(),
        allow_llm=True,
    )
    assert found.stipulation is None
    assert found.has_stipulation is False
    assert found.needs_review is False


def test_empty_caption_is_a_normal_outcome() -> None:
    """No caption band is not an error; it is the commonest case in scans."""
    found = stipulation_for_context(FakeContext(caption="   "), runtime=NullRuntime())
    assert found.stipulation is None
    assert "sem legenda" in found.detail


def test_a_raising_extractor_cannot_break_a_page() -> None:
    """An optional subsystem may not propagate an exception into the pipeline."""

    class Exploding:
        model = "boom"

        def info(self) -> object:  # pragma: no cover - never reached
            raise RuntimeError("nao deveria ser chamado")

        def is_available(self) -> bool:
            raise RuntimeError("estourou")

    found = stipulation_for_context(
        FakeContext(caption="Bremen 1998 Hickl - Yusupov"),
        runtime=Exploding(),  # type: ignore[arg-type]
        allow_llm=True,
    )
    assert found.stipulation is None
    assert "falhou" in found.detail


# --------------------------------------------------------------------------- #
# The printed page wins
# --------------------------------------------------------------------------- #


def test_printed_side_beats_the_extractor_and_the_conflict_is_recorded() -> None:
    """The page said White; the caption text says Black. The page wins."""
    found = stipulation_for_context(
        FakeContext(caption="Mate em 3. Pretas jogam.", side_to_move=True)
    )
    assert found.stipulation is not None
    assert found.stipulation.side_to_move == "w"
    assert found.side_conflict is True
    assert found.needs_review is True
    assert "a pagina venceu" in found.detail


def test_black_to_move_is_not_mistaken_for_absent() -> None:
    """``side_to_move=False`` means *black*, not *unknown*.

    ``chess.Color`` is a bool, so a truthiness test here would silently treat
    every black-to-move page as a page that said nothing.
    """
    found = stipulation_for_context(
        FakeContext(caption="Mate em 2. Brancas jogam.", side_to_move=False)
    )
    assert found.stipulation is not None
    assert found.stipulation.side_to_move == "b"
    assert found.side_conflict is True


def test_printed_number_beats_the_extractor() -> None:
    """A printed ordinal is exact; an extracted one is a guess."""
    found = stipulation_for_context(
        FakeContext(caption="Diagrama 47. Mate em 2.", exercise_number=470)
    )
    assert found.stipulation is not None
    assert found.stipulation.diagram_number == 470
    assert found.number_conflict is True


def test_a_conflict_lowers_confidence_and_never_raises_it() -> None:
    """The LLM may only lower a confidence. This is that rule, measured."""
    agreed = stipulation_for_context(
        FakeContext(caption="Mate em 3. Brancas jogam.", side_to_move=True)
    )
    conflicted = stipulation_for_context(
        FakeContext(caption="Mate em 3. Pretas jogam.", side_to_move=True)
    )
    assert agreed.stipulation is not None
    assert conflicted.stipulation is not None
    assert conflicted.stipulation.confidence < agreed.stipulation.confidence


def test_the_context_is_never_mutated() -> None:
    """The enrichment sits beside the context; it does not write into it."""
    context = FakeContext(caption="Diagrama 5. Mate em 2.", side_to_move=True, exercise_number=5)
    stipulation_for_context(context)
    assert context.caption == "Diagrama 5. Mate em 2."
    assert context.side_to_move is True
    assert context.exercise_number == 5
    with pytest.raises(FrozenInstanceError):
        context.side_to_move = False  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# The model path, when a caller asks for it
# --------------------------------------------------------------------------- #


def test_the_model_is_consulted_only_when_the_matcher_cannot_answer() -> None:
    """A caption the rules classify must not cost a model call."""
    runtime = FakeRuntime([stipulation_reply()])
    stipulation_for_context(
        FakeContext(caption="Diagrama 12. Mate em 2 lances."), runtime=runtime, allow_llm=True
    )
    assert runtime.requests == []


def test_model_answers_are_marked_as_model_answers() -> None:
    """A reviewer must be able to tell a regex answer from a generated one."""
    runtime = FakeRuntime([stipulation_reply(kind="win", moves=None, side=None)])
    found = stipulation_for_context(
        FakeContext(caption="Bremen 1998 Hickl - Yusupov"),
        runtime=runtime,
        allow_llm=True,
    )
    assert found.used_llm is True
    assert found.stipulation is not None
    assert found.stipulation.source == "llm"
    assert found.needs_review is True


def test_a_model_answer_is_asked_for_with_a_forced_schema() -> None:
    """The grammar is what turns unparseable replies into parseable ones."""
    runtime = FakeRuntime([stipulation_reply(kind="win", moves=None, side=None)])
    stipulation_for_context(
        FakeContext(caption="Bremen 1998 Hickl - Yusupov"),
        runtime=runtime,
        allow_llm=True,
    )
    assert len(runtime.requests) == 1
    request = runtime.requests[0]
    assert request.json_schema is not None
    assert request.json_schema["properties"]["kind"]["enum"][0] == "mate"
    assert request.think is False


# --------------------------------------------------------------------------- #
# Page-level API
# --------------------------------------------------------------------------- #


def test_enrich_contexts_returns_one_entry_per_diagram_in_order() -> None:
    """The tuple lines up with the context list the pipeline already has."""
    contexts = [
        FakeContext(caption="Diagrama 1. Mate em 2."),
        FakeContext(caption="Bremen 1998 Hickl - Yusupov"),
        FakeContext(caption="Diagrama 3. Brancas jogam e ganham."),
    ]
    found = enrich_contexts(contexts)
    assert [item.index for item in found] == [0, 1, 2]
    assert [item.has_stipulation for item in found] == [True, False, True]


def test_enrich_contexts_tolerates_an_empty_page() -> None:
    """A page with no diagrams is ordinary, and costs nothing."""
    assert enrich_contexts([]) == ()
    assert enrich_contexts(None) == ()


def test_page_entry_point_needs_no_boxes_to_be_safe() -> None:
    """A page with no detected diagram costs nothing and reads no file."""
    assert stipulations_for_pdf_page("nao-existe.pdf", 0, []) == ()


def test_page_entry_point_degrades_on_an_unreadable_pdf() -> None:
    """A missing or broken PDF is an empty answer, not an exception."""
    assert stipulations_for_pdf_page("nao-existe.pdf", 0, [(0.0, 0.0, 10.0, 10.0)]) == ()


def test_enrichment_is_frozen() -> None:
    """The result is data, not a mutable accumulator someone can edit later."""
    found = CaptionEnrichment(index=0)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        found.index = 3  # type: ignore[misc]
