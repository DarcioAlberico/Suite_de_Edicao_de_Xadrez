"""The five reasons the LLM exists. Nothing else may call the model.

Each task is a typed function with a strict output schema, and each one fails
*closed*: when the model is absent, slow, cancelled, or says something that does
not validate, the task returns ``None`` or a zero-confidence result. It never
returns a guess dressed as an answer.

Two design rules run through all of them:

**Cheap and exact first.** :func:`extract_stipulation` runs a deterministic
multilingual matcher before it considers the model, and
:func:`caption_for_diagram` can build a correct caption from the FEN alone. The
LLM is the fallback, never the first attempt -- which is also what keeps the
VRAM budget intact, since most items never wake it.

**The LLM never touches a move.** :func:`translate_notation_prose` masks every
move token before the text leaves this process and restores the original bytes
afterwards, verifying that the mask survived. Moves belong to the F6 notation
engine, which is exact.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final, Literal

from caissa.llm.guardrails import (
    ConfidenceDecision,
    ConfidencePolicy,
    FieldSpec,
    apply_verdict,
    guarded_json_call,
    normalise_square_names,
    validate_fen,
)
from caissa.llm.prompts import load_prompt
from caissa.llm.runtime import CancellationToken, LlmRuntime, get_runtime

__all__ = [
    "STIPULATION_KINDS",
    "Stipulation",
    "VerificationResult",
    "caption_for_diagram",
    "extract_stipulation",
    "material_summary",
    "repair_ocr_region",
    "translate_notation_prose",
    "verify_diagram",
]

logger = logging.getLogger(__name__)

StipulationKind = Literal["mate", "win", "draw", "best_move", "study", "unknown"]
Verdict = Literal["consistent", "inconsistent", "uncertain"]

STIPULATION_KINDS: Final[tuple[str, ...]] = (
    "mate",
    "win",
    "draw",
    "best_move",
    "study",
    "unknown",
)

_LANG_CODES: Final = ("pt", "en", "de", "es", "fr", "it", "ru")


def _runtime(runtime: LlmRuntime | None) -> LlmRuntime:
    """Resolve the runtime once, so tasks can be called with or without one."""
    return runtime if runtime is not None else get_runtime()


# --------------------------------------------------------------------------- #
# 1. Diagram verification (SPEC 6.5)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Whether a candidate FEN agrees with the picture.

    There is deliberately **no FEN field**. The model is never asked for a
    position and could not deliver one through this type if it tried: the worst
    failure mode of an LLM here is a plausible, wrong FEN, and the cheapest way
    to make that impossible is to leave nowhere to put it.

    Attributes:
        verdict: ``"consistent"``, ``"inconsistent"`` or ``"uncertain"``.
            ``"uncertain"`` is also what every failure produces.
        confidence: The model's own stated confidence, ``0.0`` when it did not
            answer usefully.
        suspect_squares: Advisory squares to highlight in the review overlay.
            Validated to be real squares; junk is dropped.
        notes: Short pt-BR note for the review panel.
        used_llm: Whether a model actually answered. ``False`` means this result
            carries no information, and callers must not treat it as agreement.
        detail: Why, when ``used_llm`` is ``False``.
        latency_ms: Wall clock spent, for the benchmark.
    """

    verdict: Verdict = "uncertain"
    confidence: float = 0.0
    suspect_squares: tuple[str, ...] = ()
    notes: str = ""
    used_llm: bool = False
    detail: str = ""
    latency_ms: float = 0.0

    @property
    def disagrees(self) -> bool:
        """Whether this is an actual, usable disagreement."""
        return self.used_llm and self.verdict == "inconsistent"

    def decide(
        self, vision_confidence: float, *, policy: ConfidencePolicy | None = None
    ) -> ConfidenceDecision:
        """Fold this verdict into a vision confidence under the guardrail policy.

        The only sanctioned way to let this result affect anything. See
        :func:`caissa.llm.guardrails.apply_verdict` for the invariants.
        """
        if not self.used_llm:
            return apply_verdict(vision_confidence, "uncertain", 0.0, policy=policy)
        return apply_verdict(vision_confidence, self.verdict, self.confidence, policy=policy)


_VERIFY_SCHEMA: Final = {
    "verdict": FieldSpec(kind="str", choices=("consistent", "inconsistent", "uncertain")),
    "confidence": FieldSpec(kind="float", minimum=0.0, maximum=1.0, required=False, default=0.0),
    "suspect_squares": FieldSpec(kind="list[str]", required=False, default=[], max_length=6),
    "notes": FieldSpec(kind="str", required=False, default="", max_length=160),
}


def material_summary(fen: str) -> str:
    """Human-readable piece inventory implied by a FEN.

    Handed to the model alongside the FEN because counting pieces from a
    picture is exactly the thing a VLM is worst at, and stating the expected
    inventory turns "read the board" into the much easier "check this list".
    """
    placement = (fen or "").split(" ")[0]
    names = {
        "K": "Rei branco",
        "Q": "Dama branca",
        "R": "Torre branca",
        "B": "Bispo branco",
        "N": "Cavalo branco",
        "P": "Peao branco",
        "k": "Rei preto",
        "q": "Dama preta",
        "r": "Torre preta",
        "b": "Bispo preto",
        "n": "Cavalo preto",
        "p": "Peao preto",
    }
    counts: dict[str, int] = {}
    for char in placement:
        if char in names:
            counts[char] = counts.get(char, 0) + 1
    if not counts:
        return "vazio"
    return ", ".join(f"{counts[key]}x {names[key]}" for key in names if key in counts)


def verify_diagram(
    crop_image: bytes,
    candidate_fen: str,
    caption: str = "",
    *,
    runtime: LlmRuntime | None = None,
    language: str = "portugues",
    timeout_s: float = 60.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> VerificationResult:
    """Ask whether ``candidate_fen`` is consistent with the diagram crop.

    Used **only** on low-confidence items (SPEC 6.5). Running it on everything
    would spend the whole VRAM budget to confirm what the vision pipeline
    already knows, and would slow a 500-PDF batch by orders of magnitude.

    Args:
        crop_image: PNG or JPEG bytes of the rectified diagram.
        candidate_fen: The FEN the pipeline produced.
        caption: Nearby caption text, if any.
        runtime: Backend override; defaults to the process runtime.
        language: Language for the ``notes`` field.
        timeout_s: Wall-clock budget.
        cancel: Cancellation token.
        seed: Fixed seed for reproducibility.

    Returns:
        A :class:`VerificationResult`. On any failure, an ``"uncertain"`` result
        with ``used_llm=False`` -- which :meth:`VerificationResult.decide` turns
        into "leave the vision result exactly as it was".
    """
    engine = _runtime(runtime)
    if not crop_image:
        return VerificationResult(detail="nenhuma imagem fornecida")
    normalised = validate_fen(candidate_fen, require_legal=False)
    if normalised is None:
        # A FEN that does not even parse is not the LLM's problem to solve.
        return VerificationResult(detail="FEN candidato nao e analisavel; nada a verificar")

    template = load_prompt("verify_diagram")
    outcome = guarded_json_call(
        engine,
        template,
        _VERIFY_SCHEMA,
        {
            "placement": normalised.split(" ")[0],
            "inventory": material_summary(normalised),
            "caption": caption.strip() or "(nenhuma)",
            "language": language,
        },
        task="verify_diagram",
        images=(crop_image,),
        timeout_s=timeout_s,
        cancel=cancel,
        seed=seed,
    )
    if not outcome.ok or outcome.payload is None:
        return VerificationResult(detail=outcome.detail, latency_ms=outcome.latency_ms)

    payload = outcome.payload
    verdict: Verdict = payload["verdict"]
    squares = normalise_square_names(payload.get("suspect_squares") or (), limit=6)
    # A model that says "inconsistent" but cannot name a single square has not
    # actually seen a disagreement. Demote it rather than trust it: this is the
    # single cheapest defence against a confident, contentless "it's wrong".
    if verdict == "inconsistent" and not squares:
        return VerificationResult(
            verdict="uncertain",
            confidence=0.0,
            notes=str(payload.get("notes") or ""),
            used_llm=True,
            detail="discordancia sem casa apontada; rebaixada para indefinido",
            latency_ms=outcome.latency_ms,
        )
    return VerificationResult(
        verdict=verdict,
        confidence=float(payload.get("confidence") or 0.0),
        suspect_squares=squares,
        notes=str(payload.get("notes") or ""),
        used_llm=True,
        latency_ms=outcome.latency_ms,
    )


# --------------------------------------------------------------------------- #
# 2. Stipulation extraction
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Stipulation:
    """What the caption says the reader is supposed to do.

    Attributes:
        kind: The task type.
        moves: Number of moves, for ``"mate"``.
        side_to_move: ``"w"``/``"b"`` when the caption states it.
        diagram_number: The printed ordinal, when present.
        language: ISO 639-1 code of the caption.
        confidence: How sure the extractor is.
        source: ``"rules"`` when the deterministic matcher answered, ``"llm"``
            when the model did. Recorded because a rules answer is exact and an
            LLM answer is not, and the UI treats them differently.
        raw: The caption text the answer came from.
    """

    kind: StipulationKind
    moves: int | None = None
    side_to_move: Literal["w", "b"] | None = None
    diagram_number: int | None = None
    language: str = ""
    confidence: float = 0.0
    source: Literal["rules", "llm"] = "rules"
    raw: str = ""


# Deterministic patterns, in the seven languages CORPUS.md lists. These are
# cheap, exact and cover the overwhelming majority of real captions; the model
# only sees what they miss.
_MATE_RE: Final = re.compile(
    r"""(?ix)
    \b(?:
        mate|matt|mat|matto|м(?:ат)             # pt/en/es | de | fr | it | ru
      | xeque[-\s]?mate
    )\b
    # The number must belong to the same phrase as the word. The original
    # window was 24 characters and allowed sentence punctuation, which turned
    # a French primer's "...pour faire mat. ... 2) s'il ne reste pas..." into
    # "mate in 2" (F11 cycle 2, dev half). A stipulation reads "mate in 2",
    # "Mate em 2 lances", "Matt in 3 Zuegen", "Mat v 2 khoda" -- one connective,
    # no full stop.
    [^0-9\n.;:!?()\[\]]{0,12}?
    (?P<n>\d{1,2})
    """,
)
#: A lone capital M (or #) next to a digit. On clean text this is problem
#: notation for "mate in N"; on a scanned page it is whatever the OCR made of a
#: piece glyph, and it manufactured four of the ten fabrications this matcher
#: produced in F11 cycle 2. It is therefore *weak* evidence -- see
#: :func:`_is_caption_shaped`.
_MATE_SHORT_RE: Final = re.compile(r"(?i)\b(?:#|M)\s?(?P<n>[1-9])\b")
_WIN_RE: Final = re.compile(
    r"""(?ix)
    \b(?:
        gan(?:ham|har|a|an)                     # pt/es
      | vence(?:m|r)?                           # pt
      | win(?:s|ning)?                          # en
      | gewinn(?:t|en)                          # de
      | gagne(?:nt)?                            # fr
      | vinc(?:e|ono)                           # it
      | выигрыва(?:ет|ют)|выигрыш                # ru
    )\b
    """,
)
_DRAW_RE: Final = re.compile(
    r"""(?ix)
    \b(?:
        empat(?:am|ar|e)|tabl(?:as|a)           # pt/es
      | draw(?:s)?                              # en
      | remis|remise                            # de/fr/nl
      | nulle|annulent                          # fr
      | patta                                   # it
      | ничья|ничью                             # ru
    )\b
    """,
)
_BEST_MOVE_RE: Final = re.compile(
    r"""(?ix)
    (?:
        melhor\s+lance | qual\s+o\s+lance
      | best\s+move | find\s+the\s+move
      | beste[rn]?\s+zug | was\s+ist\s+der\s+beste
      | mejor\s+jugada
      | meilleur\s+coup
      | miglior\s+mossa
      | лучший\s+ход
    )
    """,
)
_STUDY_RE: Final = re.compile(r"(?i)\b(?:estudo|study|studie|estudio|étude|etude|studio|этюд)\b")
_WHITE_RE: Final = re.compile(r"(?i)\b(?:brancas|white|wei(?:ss|ß)|blancas|blancs|bianco|белые)\b")
_BLACK_RE: Final = re.compile(r"(?i)\b(?:pretas|negras|black|schwarz|noirs|nero|чёрные|черные)\b")
_NUMBER_RE: Final = re.compile(
    r"""(?ix)
    (?:
        diagram(?:a|me)?|abb(?:ildung)?|stellung
      | posi[cç][aã]o|posici[oó]n|position|posizione
      | exerc[ií]cio|exercise|[uú]bung|problema|problem|no\.?|n[.º°]|\#
    )
    \s*(?P<n>\d{1,4})\b
    """,
)
_LANG_HINTS: Final = (
    ("ru", re.compile(r"[Ѐ-ӿ]")),
    ("pt", re.compile(r"(?i)\b(?:brancas|pretas|jogam|lance|ganham|empatam|diagrama)\b")),
    ("de", re.compile(r"(?i)\b(?:wei(?:ss|ß)|schwarz|zieht|gewinnt|zug|matt)\b")),
    ("es", re.compile(r"(?i)\b(?:blancas|negras|juegan|jugada|ganan|tablas)\b")),
    ("fr", re.compile(r"(?i)\b(?:blancs|noirs|jouent|coup|gagnent|nulle)\b")),
    ("it", re.compile(r"(?i)\b(?:bianco|nero|muove|mossa|vince|patta)\b")),
    ("en", re.compile(r"(?i)\b(?:white|black|to\s+play|move|wins|draw|mate)\b")),
)


def _guess_language(text: str) -> str:
    """Cheap language hint from stop words. Good enough to steer the answer."""
    for code, pattern in _LANG_HINTS:
        if pattern.search(text):
            return code
    return ""


#: A stipulation names the side **and** the result, close together and inside
#: one clause: "las blancas ganan", "Weiss zieht und gewinnt", "White to play
#: and win", "Les Blancs gagnent", "belye vyigryvayut". A lone result word --
#: "gewinnt.", "vence.", "Remis." -- is something else: it is the end of a
#: variation, and it appears in running commentary on every second page of a
#: game collection. This pattern is what separates the two.
#:
#: The ``[^.;\n]`` window is the load-bearing part. "Weiss: Stellung nach dem
#: 20. Zuge von ..." carries a side word and, forty words later, a "gewinnt";
#: stopping at the full stop keeps them apart.
_SIDE_RESULT_RE: Final = re.compile(
    r"""(?ix)
    \b(?:
        brancas|pretas|negras|blancas|white|black|wei(?:ss|ß)|schwarz
      | blancs|noirs|bianco|nero|wit|zwart|бел(?:ые|ых)|ч[её]рные
    )\b
    [^.;\n]{0,44}?
    \b(?:
        ganh(?:am|a)|gan[ao]n|vencem?|win(?:s)?|gewinn(?:t|en)|gagne(?:nt)?
      | vinc(?:e|ono)|wint|winnen|выигрыва(?:ет|ют)
      | empat(?:am|a)|draw(?:s)?|remis(?:e)?|tablas|nulle|patta|ничья|ничью
    )\b
    """,
)

#: A printed caption is short. Past this, the text next to the diagram is the
#: page's running commentary, and a result word inside it is analysis.
_CAPTION_LIKE_CHARS: Final = 90

#: More move tokens than this and the text is a variation, whatever its length.
_MAX_VARIATION_MOVES: Final = 3


def _is_caption_shaped(text: str) -> bool:
    """Whether weak evidence may be read from this text at all.

    Weak evidence is a single word that *might* state a result. It is trusted
    only inside something that looks like a printed caption: short, and not a
    line of moves. Measured on the dev half of the F11 cycle-2 caption set,
    this is what separates "Remis." printed under a study from "...wuerde
    Schwarz auf glaenzende Weise das Remis erzwingen" printed beside a game.
    """
    stripped = text.strip()
    if len(stripped) > _CAPTION_LIKE_CHARS:
        return False
    return len(_MASKABLE_RE.findall(stripped)) <= _MAX_VARIATION_MOVES


def _rules_stipulation(caption: str) -> Stipulation | None:
    """Deterministic extraction. Returns ``None`` when nothing matched."""
    text = caption.strip()
    if not text:
        return None
    language = _guess_language(text)
    number_match = _NUMBER_RE.search(text)
    number = int(number_match["n"]) if number_match else None

    side: Literal["w", "b"] | None = None
    white_at = _WHITE_RE.search(text)
    black_at = _BLACK_RE.search(text)
    if white_at and (not black_at or white_at.start() < black_at.start()):
        side = "w"
    elif black_at:
        side = "b"

    # Strong evidence names the task: "mate in 2", "las blancas ganan", "White
    # to play and win", "Qual o melhor lance?". Weak evidence is one word that
    # might be a result and might be the end of a variation, and it is read only
    # from something caption-shaped. Splitting the two is what stopped this
    # matcher asserting a stipulation on scanned commentary -- ten times in 199
    # captions before the split, in F11 cycle 2.
    caption_shaped = _is_caption_shaped(text)
    kind: StipulationKind | None = None
    moves: int | None = None
    if match := _MATE_RE.search(text):
        count = int(match["n"])
        if 1 <= count <= 20:  # noqa: PLR2004 - "mate in 40" is a typo, not a stipulation
            kind, moves = "mate", count
    if kind is None and caption_shaped and (match := _MATE_SHORT_RE.search(text)):
        count = int(match["n"])
        if 1 <= count <= 20:  # noqa: PLR2004 - same bound, same reason
            kind, moves = "mate", count
    if kind is None and (result := _SIDE_RESULT_RE.search(text)):
        # The side and the result were printed together, so the phrase is a
        # stipulation whatever else surrounds it.
        kind = "draw" if _DRAW_RE.search(result.group(0)) else "win"
    if kind is None and _BEST_MOVE_RE.search(text):
        kind = "best_move"
    if kind is None and caption_shaped and _DRAW_RE.search(text):
        kind = "draw"
    if kind is None and caption_shaped and _WIN_RE.search(text):
        kind = "win"
    if kind is None and caption_shaped and _STUDY_RE.search(text):
        kind = "study"
    if kind is None:
        if number is not None or side is not None:
            # A bare "Diagrama 12" is a real, complete answer: it states no
            # stipulation, and saying so is more useful than asking a model.
            return Stipulation(
                kind="unknown",
                side_to_move=side,
                diagram_number=number,
                language=language,
                confidence=0.55,
                source="rules",
                raw=text,
            )
        return None
    return Stipulation(
        kind=kind,
        moves=moves,
        side_to_move=side,
        diagram_number=number,
        language=language,
        confidence=0.95,
        source="rules",
        raw=text,
    )


_STIPULATION_SCHEMA: Final = {
    "kind": FieldSpec(kind="str", choices=STIPULATION_KINDS),
    "moves": FieldSpec(kind="int", minimum=1, maximum=20, required=False),
    "side_to_move": FieldSpec(kind="str", choices=("w", "b"), required=False),
    "diagram_number": FieldSpec(kind="int", minimum=1, maximum=9999, required=False),
    "language": FieldSpec(kind="str", required=False, default="", max_length=8),
    "confidence": FieldSpec(kind="float", minimum=0.0, maximum=1.0, required=False, default=0.0),
}


def extract_stipulation(
    caption_text: str,
    crop_image: bytes | None = None,
    *,
    runtime: LlmRuntime | None = None,
    timeout_s: float = 45.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
    allow_llm: bool = True,
    allow_rules: bool = True,
    force_schema: bool = True,
) -> Stipulation | None:
    """Extract the stipulation and diagram number from a caption.

    Tries the deterministic multilingual matcher first (pt/en/de/es/fr/it/ru).
    Only captions it cannot classify reach the model.

    Args:
        caption_text: The caption near the diagram.
        crop_image: Optional crop, attached when the model is consulted -- a
            caption is sometimes only legible in the picture.
        runtime: Backend override.
        timeout_s: Wall-clock budget.
        cancel: Cancellation token.
        seed: Fixed seed.
        allow_llm: Set ``False`` to measure the rules path alone.
        allow_rules: Set ``False`` to measure the model alone. Production never
            does this -- the rules path is exact where it fires and free -- but
            a benchmark that cannot isolate the model cannot attribute a result
            to it.
        force_schema: Constrain decoding to the reply schema. See
            :func:`caissa.llm.guardrails.json_schema_for`.

    Returns:
        A :class:`Stipulation`, or ``None`` when neither path could say
        anything. ``None`` means "no stipulation extracted", never "no
        stipulation exists".
    """
    rules = _rules_stipulation(caption_text) if allow_rules else None
    if rules is not None and (rules.kind != "unknown" or not allow_llm):
        return rules

    if not allow_llm:
        return rules
    engine = _runtime(runtime)
    if not engine.is_available():
        return rules
    if not caption_text.strip() and not crop_image:
        return rules

    template = load_prompt("extract_stipulation")
    outcome = guarded_json_call(
        engine,
        template,
        _STIPULATION_SCHEMA,
        {"caption": caption_text.strip() or "(ilegivel; veja a imagem)"},
        task="extract_stipulation",
        images=(crop_image,) if crop_image else (),
        timeout_s=timeout_s,
        cancel=cancel,
        seed=seed,
        force_schema=force_schema,
    )
    if not outcome.ok or outcome.payload is None:
        return rules

    payload = outcome.payload
    language = str(payload.get("language") or "").lower()[:2]
    guessed = Stipulation(
        kind=payload["kind"],
        moves=payload.get("moves"),
        side_to_move=payload.get("side_to_move"),
        diagram_number=payload.get("diagram_number"),
        language=language if language in _LANG_CODES else _guess_language(caption_text),
        confidence=min(0.85, float(payload.get("confidence") or 0.0)),
        source="llm",
        raw=caption_text.strip(),
    )
    # The rules path is exact where it fires. An LLM answer never overrides it;
    # it only fills a gap the rules left.
    if rules is not None and rules.kind != "unknown":
        return rules
    if rules is not None and guessed.kind == "unknown":
        return rules
    if rules is not None and guessed.diagram_number is None and rules.diagram_number is not None:
        return Stipulation(
            kind=guessed.kind,
            moves=guessed.moves,
            side_to_move=guessed.side_to_move or rules.side_to_move,
            diagram_number=rules.diagram_number,
            language=guessed.language or rules.language,
            confidence=guessed.confidence,
            source="llm",
            raw=guessed.raw,
        )
    return guessed


# --------------------------------------------------------------------------- #
# 3. Last-resort OCR (SPEC 7.1 level 4)
# --------------------------------------------------------------------------- #

_OCR_SCHEMA: Final = {
    "text": FieldSpec(kind="str", required=False, default="", max_length=2000),
    "confidence": FieldSpec(kind="float", minimum=0.0, maximum=1.0, required=False, default=0.0),
}

#: A transcription may not be wildly longer than what the cascade already read.
#: Runaway length is the signature of a model that started narrating instead of
#: transcribing, and it is the failure mode that would poison a book's text.
_OCR_LENGTH_FACTOR: Final = 4.0
_OCR_LENGTH_FLOOR: Final = 80
_OCR_MIN_CONFIDENCE: Final = 0.40


def repair_ocr_region(
    image: bytes,
    ocr_text: str,
    language: str = "pt",
    *,
    runtime: LlmRuntime | None = None,
    timeout_s: float = 90.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> str | None:
    """Transcribe a region the OCR cascade rejected. Level 4 of SPEC 7.1.

    **Measured and not wired** (F11 cycle 3, ``docs/quality/F11_REPORT_C3.md``).
    On the 70 regions the cascade rejected, the model fixed 69 move tokens and
    broke 2 -- and wrote 103 move-shaped tokens that are on no page, against 18
    from Tesseract. Its output on a historical-quality scan holds more wrong
    moves than right ones, and each one looks legal. The gain is real only
    where the hint from the cascade is already close (it edits the hint; with
    no hint its CER is seven times worse), and its declared confidence is 0.9
    or more on 92 % of answers regardless of error. The function stays for a
    review-panel *suggestion* if one is ever wanted; it must not replace text.

    Args:
        image: PNG/JPEG bytes of the region.
        ocr_text: The low-confidence attempt from earlier engines; may be empty.
        language: Page language, to steer the transcription.
        runtime: Backend override.
        timeout_s: Wall-clock budget.
        cancel: Cancellation token.
        seed: Fixed seed.

    Returns:
        The transcription, or ``None``. ``None`` when the model is absent, when
        it returned nothing, when it was not confident, or when the answer grew
        far beyond the region -- all of which mean "keep the cascade's result
        and leave the region flagged for the human".
    """
    engine = _runtime(runtime)
    if not image:
        return None

    template = load_prompt("repair_ocr_region")
    outcome = guarded_json_call(
        engine,
        template,
        _OCR_SCHEMA,
        {"language": language, "ocr_text": ocr_text.strip() or "(vazio)"},
        task="repair_ocr_region",
        images=(image,),
        timeout_s=timeout_s,
        cancel=cancel,
        seed=seed,
    )
    if not outcome.ok or outcome.payload is None:
        return None

    text = str(outcome.payload.get("text") or "").strip()
    confidence = float(outcome.payload.get("confidence") or 0.0)
    if not text or confidence < _OCR_MIN_CONFIDENCE:
        return None
    ceiling = max(_OCR_LENGTH_FLOOR, int(len(ocr_text.strip()) * _OCR_LENGTH_FACTOR))
    if len(text) > ceiling:
        logger.info(
            "transcricao do LLM rejeitada: %d caracteres para uma regiao de %d",
            len(text),
            len(ocr_text.strip()),
        )
        return None
    return text


# --------------------------------------------------------------------------- #
# 4. Caption generation
# --------------------------------------------------------------------------- #

_CAPTION_SCHEMA: Final = {"caption": FieldSpec(kind="str", max_length=200)}

_SIDE_WORDS: Final = {
    "pt": ("Brancas jogam", "Pretas jogam"),
    "en": ("White to move", "Black to move"),
    "de": ("Weiss am Zug", "Schwarz am Zug"),
    "es": ("Juegan blancas", "Juegan negras"),
    "fr": ("Les Blancs jouent", "Les Noirs jouent"),
    "it": ("Muove il Bianco", "Muove il Nero"),
    "ru": ("Ход белых", "Ход чёрных"),
}

#: An SAN-shaped token. Used to reject a caption that smuggled a move in.
_MOVE_TOKEN_RE: Final = re.compile(
    r"""(?x)
    (?<![\w])
    (?:
        O-O(?:-O)?
      | [KQRBNPRDTCSAFLTVCГЛСКФ]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBNDTCFGL])?
    )
    [+#!?]*
    (?![\w])
    """
)


def _fallback_caption(fen: str, language: str) -> str:
    """Build a correct caption from the FEN alone. No model involved.

    This is what :func:`caption_for_diagram` returns when there is no LLM, and
    it is also why that function's return type is ``str`` rather than
    ``str | None``: a caption is always available, it is just plainer.
    """
    parts = (fen or "").split(" ")
    side = parts[1] if len(parts) > 1 else "w"
    white_word, black_word = _SIDE_WORDS.get(language[:2], _SIDE_WORDS["pt"])
    return white_word if side == "w" else black_word


def caption_for_diagram(
    fen: str,
    context: str = "",
    *,
    runtime: LlmRuntime | None = None,
    language: str = "pt",
    timeout_s: float = 45.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> str:
    """Write a short caption for a diagram, in the user's language.

    Args:
        fen: The position.
        context: Surrounding document text the caption may draw on.
        runtime: Backend override.
        language: ISO 639-1 code for the caption.
        timeout_s: Wall-clock budget.
        cancel: Cancellation token.
        seed: Fixed seed.

    Returns:
        A caption. **Always a string** -- without a model, a deterministic
        "Brancas jogam"-style caption built from the FEN. A generated caption
        containing a move in algebraic notation is discarded in favour of that
        fallback, because moves must come from the exact F6 engine.
    """
    engine = _runtime(runtime)
    fallback = _fallback_caption(fen, language)
    normalised = validate_fen(fen, require_legal=False)
    if normalised is None:
        return fallback

    template = load_prompt("caption_for_diagram")
    outcome = guarded_json_call(
        engine,
        template,
        _CAPTION_SCHEMA,
        {
            "fen": normalised,
            "side": "brancas" if normalised.split(" ")[1] == "w" else "pretas",
            "material": material_summary(normalised),
            "context": context.strip()[:600] or "(nenhum)",
            "language": language,
        },
        task="caption_for_diagram",
        images=(),
        timeout_s=timeout_s,
        cancel=cancel,
        seed=seed,
    )
    if not outcome.ok or outcome.payload is None:
        return fallback
    caption = str(outcome.payload.get("caption") or "").strip()
    if not caption:
        return fallback
    if _MOVE_TOKEN_RE.search(caption):
        logger.info("legenda gerada continha notacao de lance; descartada")
        return fallback
    return caption


# --------------------------------------------------------------------------- #
# 5. Prose translation -- moves are masked, never translated
# --------------------------------------------------------------------------- #

_TRANSLATION_SCHEMA: Final = {"translation": FieldSpec(kind="str", max_length=8000)}

_SENTINEL_RE: Final = re.compile(r"\[\[M(\d+)\]\]")

#: Tokens that look like moves and must not reach the model. Deliberately
#: greedy: a false positive costs an untranslated word, a false negative costs a
#: corrupted move, and those are not comparable.
_MASKABLE_RE: Final = re.compile(
    r"""(?x)
    (?<![\w\[])
    (?:
        \d{1,3}\.{1,3}                              # move numbers: 12. 12...
      | O-O-O|O-O|0-0-0|0-0                         # castling, both spellings
      | [KQRBNPRDTCSAFLGVMИЛСКФ]?[a-h]x?[a-h]?[1-8](?:=[A-ZА-Я])?[+#]?[!?]{0,2}
      | [KQRBNPRDTCSAFLGVMИЛСКФ][1-8]?x?[a-h][1-8](?:=[A-ZА-Я])?[+#]?[!?]{0,2}
      | 1-0|0-1|½-½|1/2-1/2
    )
    (?![\w\]])
    """
)


def _mask_moves(text: str) -> tuple[str, list[str]]:
    """Replace move-like tokens with sentinels, returning the originals."""
    originals: list[str] = []

    def swap(match: re.Match[str]) -> str:
        originals.append(match.group(0))
        return f"[[M{len(originals) - 1}]]"

    return _MASKABLE_RE.sub(swap, text), originals


def _restore_moves(text: str, originals: list[str]) -> str | None:
    """Put the original tokens back, or return ``None`` if the mask was broken.

    This is the guardrail, not a convenience. If the model dropped, duplicated,
    reordered or edited a sentinel, the translation is discarded entirely: a
    translated chess book with one corrupted move is worse than an untranslated
    one, because the corruption is invisible.
    """
    found = [int(index) for index in _SENTINEL_RE.findall(text)]
    if found != list(range(len(originals))):
        logger.warning(
            "traducao rejeitada: sentinelas esperadas %s, encontradas %s",
            list(range(len(originals))),
            found,
        )
        return None
    return _SENTINEL_RE.sub(lambda match: originals[int(match.group(1))], text)


def translate_notation_prose(
    text: str,
    from_lang: str,
    to_lang: str,
    *,
    runtime: LlmRuntime | None = None,
    timeout_s: float = 120.0,
    cancel: CancellationToken | None = None,
    seed: int | None = 0,
) -> str:
    """Translate prose around chess moves, leaving every move byte-identical.

    Moves are masked before the text leaves this process and restored
    afterwards. The mask is then verified: any sentinel lost, duplicated or
    reordered discards the whole translation.

    Args:
        text: Source prose, moves included.
        from_lang: Source language name or code.
        to_lang: Target language name or code.
        runtime: Backend override.
        timeout_s: Wall-clock budget.
        cancel: Cancellation token.
        seed: Fixed seed.

    Returns:
        The translation, or the **original text unchanged** on any failure.
        Returning the source is the honest fallback: the user sees untranslated
        prose, which is obvious, rather than silently damaged notation, which is
        not.
    """
    engine = _runtime(runtime)
    if not text.strip():
        return text
    masked, originals = _mask_moves(text)

    template = load_prompt("translate_notation_prose")
    outcome = guarded_json_call(
        engine,
        template,
        _TRANSLATION_SCHEMA,
        {"from_lang": from_lang, "to_lang": to_lang, "text": masked},
        task="translate_notation_prose",
        images=(),
        timeout_s=timeout_s,
        cancel=cancel,
        seed=seed,
    )
    if not outcome.ok or outcome.payload is None:
        return text
    translated = str(outcome.payload.get("translation") or "").strip()
    if not translated:
        return text
    restored = _restore_moves(translated, originals)
    if restored is None:
        return text
    return restored
