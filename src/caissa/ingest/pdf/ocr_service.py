"""The importer's OCR — Sol §SOL-1, with the provenance of §SOL-10.

Before Sol, ``PdfImportOptions.ocr`` was ``None`` by default: a scanned book
imported as a stack of page images unless the caller wrote a provider by
hand, and the cascade, the preprocessing steps and the layout analyser sat
unused.  This module is the concrete provider and the default.

What it does for one page whose text layer failed (or is absent):

1. **Render selectively.**  Only the page that needs OCR is rasterised, at
   300 DPI by default and 400 DPI when the page is small print or a
   low-resolution scan (Sol §SOL-1, "300 DPI como base e 400 para texto
   pequeno ou baixa resolução").
2. **Cut and arbitrate.**  :class:`~caissa.ocr.page.PageRecognizer` lays the
   page out from its text layer when there is one — so a partially damaged
   layer keeps its good spans and only the bad regions go to the engines —
   and runs the cascade per region with the decision policy of §SOL-2.
3. **Try the portfolio where it is needed.**  A region that did not come
   out ``ACCEPTED`` on the original render is re-read on each variant the
   page's signals justified (§SOL-3): deskewed, flattened, binarised,
   upscaled or dewarped.  The best candidate wins by decision first and
   score second; the original is always among the candidates, so a clean
   page cannot lose to a variant.
4. **Fuse and validate.**  Candidates of the same region are fused token by
   token (§SOL-6) and a movetext region is replayed for legality (§SOL-8),
   when those modules are enabled.
5. **Report everything.**  The :class:`PageRecognition` carries every
   region's decision, reasons, engine, variant, DPI, score, candidates and
   flagged words, and converts to the importer's :class:`PageText` with the
   per-span confidence, engine and review flag the IR needs.

Abstention is honoured end to end: an abstained region emits no text, and
a page with nothing accepted or reviewable returns ``None`` from the
provider so the importer keeps the page image (``keep_scanned_pages``).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from caissa.ingest.pdf.geometry import PageFrame, RectT
from caissa.ingest.pdf.textlayer import (
    CIPHER_ORIGIN,
    FIGURINE_MODEL_ORIGIN,
    PageText,
    TextLine,
    TextSpan,
)
from caissa.ocr.arbiter import SCALE_OF, ArbitrationOutcome, RegionTask
from caissa.ocr.cancel import OcrCanceled, check_cancel
from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.engines.base import OcrEngine
from caissa.ocr.engines.pdf_text_layer import TextLayerVerdict
from caissa.ocr.notation.book_cipher import STYLE_ANY, body_size_of, size_class
from caissa.ocr.page import PageConfig, PageOutcome, PageRecognizer, PageTask, RegionOutcome
from caissa.ocr.portfolio import Portfolio, PortfolioConfig, Variant, build_portfolio
from caissa.ocr.types import BBox, OcrLine, OcrResult, RegionKind

__all__ = [
    "DiagramRef",
    "OcrService",
    "OcrServiceConfig",
    "PageContext",
    "PageRecognition",
    "RegionRecognition",
    "default_ocr_service",
]

LOGGER = logging.getLogger("caissa.ingest.pdf.ocr_service")

_DECISION_RANK = {Decision.ACCEPTED: 2, Decision.REVIEW: 1, Decision.ABSTAINED: 0}
#: Engine name the fine-tuned figurine model's readings carry in the fusion.
FIGURINE_ENGINE = "tesseract_figurine"
assert FIGURINE_ENGINE == FIGURINE_MODEL_ORIGIN, "the span's figurine origin names this engine"
#: The movetext-profile strips of passo B2, under their own name so they never anchor.
STRIPS_ENGINE = "tesseract_strips"
assert STRIPS_ENGINE in SCALE_OF, "the strips are Tesseract readings: they borrow its scale"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class OcrServiceConfig:
    """Everything the service can be tuned by, with the reason in place."""

    #: Rendering resolution for a page that needs OCR.
    base_dpi: int = 300
    #: Used instead when the page is small print or a low-resolution scan.
    high_dpi: int = 400
    #: Body size (points) at or below which the page counts as small print.
    small_text_pt: float = 8.5
    #: An image-only page whose embedded scan is below this resolution is
    #: rendered at ``high_dpi`` so the upscale happens once, in the renderer.
    low_scan_dpi: int = 200
    #: Language passed to the engines when the importer has none.
    default_lang: str = "por+eng"
    #: Build and try the preprocessing portfolio on regions not accepted on
    #: the original render.
    use_portfolio: bool = True
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    #: OCR_UI_ROADMAP_C2 passo B8: on a page whose show-through crosses
    #: ``portfolio.min_bleed_share``, the bleed step gets the *real* verso —
    #: the neighbouring page of the PDF (either side of the sheet is tried),
    #: mirrored and registered — instead of the "fainter and not connected to
    #: ink" heuristic.  ``register_verso`` was written for this in Sol and
    #: nothing ever handed it a verso.  The candidate that correlates best
    #: with the page is used when it clears ``verso_min_correlation``; a page
    #: with no PDF behind it (the benchmark, a photograph) has only its own
    #: mirror to offer, which is what a synthetic show-through is made of.
    #: The floor was measured on a rendered page with a *different* page
    #: showing through at 25 % (``test_verso``): the true verso registers at
    #: 0,13, the page's own mirror at 0,10, a page that is not the verso at
    #: 0,03 and noise at 0,001; the benchmark's synthetic show-through (the
    #: page itself, flipped) registers at 0,22–0,28.  0,08 sits between the
    #: wrong page and the right one.
    #: **Off by measurement** (2026-09-21, ``OCR_UI_REPORT_C2_FASE2.md`` §B8): on
    #: ``shadow_curl_bleed`` the verso variant made CER 0,0387 → 0,0399 and
    #: invented moves 8 → 10 (inside the bootstrap interval, but the wrong
    #: way) -- the stratum's show-through is the page itself mirrored and
    #: then curled, which defeats a global registration.  The mechanism is
    #: tested and stays for a real book with a real verso; nothing in the
    #: corpus rewards it yet.
    use_verso: bool = False
    verso_min_correlation: float = 0.08
    verso_self_mirror: bool = True
    #: Fuse the candidates of a region token by token (Sol §SOL-6).
    fuse: bool = True
    #: Keyword overrides for :class:`caissa.ocr.fusion.FusionConfig` (the fusion's
    #: thresholds and the passo B4 sabotage switch); ``SOL_CONFIG='{"fusion":
    #: {"passo_b4": false}}'`` in ``bench_sol`` reaches here.
    fusion: dict[str, Any] = field(default_factory=dict)
    #: OCR_UI_ROADMAP_C2 passo B5: the fused text is judged on its own
    #: score, not the anchor's.  When the anchor abstained (Tesseract at
    #: 0,40 on a line of solution under a diagram) and an *independent*
    #: candidate — another engine, or the glyph reader — was accepted or sent
    #: to review agreeing with the fused text on at least
    #: ``fusion_rescue_moves`` move tokens, the fused result is scored by
    #: the arbiter and decided again, capped at REVIEW: SOL-2 still holds, an
    #: abstained anchor is never certified by its alternatives, but a reading
    #: two readers agree on goes to the reviewer instead of to nothing.
    #: Measured before: 33 of the 62 abstained regions of ``native`` had such
    #: a candidate (``OCR_UI_ANALISE_C2.md`` §4.3).
    fusion_rescue: bool = True
    fusion_rescue_moves: int = 2
    #: Replay movetext regions for legality (Sol §SOL-8).
    validate_notation: bool = True
    #: Sol §SOL-7: on a region that reads as movetext, add Tesseract's
    #: movetext profile and its strict (whitelisted) profile as extra
    #: candidates for fusion.  The strict one is never the sole reading.
    movetext_candidates: bool = True
    #: OCR_UI_ROADMAP_C2 passo B2: on a *mixed* region — prose with analysis
    #: in it, never half moves — the movetext profile is run on each line
    #: that carries notation, as a strip, and the strips join the fusion as
    #: one candidate.  The profile's gain (SOL-7: CER 0,0168 → 0,0066 on pure
    #: movetext) reached only regions that read as movetext as a whole; on a
    #: book page the analysis lives inside paragraphs, and the prose DAWG
    #: "corrected" its moves into words.  Off, the switch of the sabotage.
    movetext_strips: bool = True
    #: ...at most this many bands per region (a band is a run of consecutive
    #: notation lines, one Tesseract call each).
    movetext_strips_max: int = 8
    #: The trunk's glyph classifier as a second opinion on regions that read
    #: as movetext (:mod:`caissa.ocr.engines.glyph`): it reads figurines
    #: (``♖e8!``) where a line engine returns Latin look-alikes (``Hea!``),
    #: and the fusion swaps only the tokens that were not words or moves.
    glyph_candidates: bool = True
    #: A Tesseract model fine-tuned on labelled figurine pages
    #: (``tools/treinar_tesseract.py``: ``caissa_<lang>.traineddata``) as a
    #: second opinion, under the same rules as the glyph reader — never the
    #: anchor, only the look-alike → figurine swap.  Measured on its own the
    #: model invents moves on noise (ROTULAGEM.md §4c); as a secondary
    #: candidate it cannot, because the fusion never inserts a token.
    figurine_candidates: bool = True
    #: Directory of ``caissa_<lang>.traineddata`` files.  ``None`` looks at
    #: ``$CAISSA_FIGURINE_TESSDATA`` and then ``<repo>/models/tessdata``.
    #: The importer sets it to the book's own directory when the PDF has a
    #: registered fine-tune (:mod:`caissa.ocr.training.books`).
    figurine_tessdata: str | None = None
    #: The fine-tuned models are named ``<prefix>_<lang>``.
    figurine_prefix: str = "caissa"
    #: OCR_UI_ROADMAP passo 4b: when ``figurine_tessdata`` names the directory
    #: of a book **registered for the PDF at hand** (the importer and the
    #: labelling tab set it that way; the global ``models/tessdata`` fallback
    #: never triggers this), the book's model is the *anchor* of its own
    #: language instead of a secondary candidate.  Measured on the SFC4
    #: (``ROTULAGEM.md`` §4d): alone the model reads 204/204 figurines of the
    #: evaluation lines, as a candidate the fusion keeps 193 — the anchor's
    #: words and moves are never replaced (SOL-6), so the anchor has to be
    #: the reader that already has them.  Off, the candidate path of §4c.
    book_model_anchors: bool = True
    #: OCR_UI_ROADMAP passo 1: the optional engines (level 2 and above —
    #: ``rapidocr``, ``paddleocr``, ``paddle_structure``, ``surya``) the
    #: service may add to the text layer and Tesseract when it assembles the
    #: cascade from the registry itself.  Installing one of them no longer
    #: changes production behaviour by itself: it enters only when named here,
    #: and the default is what the measurement on the golden corpus decided
    #: (``docs/quality/OCR_UI_REPORT_C1.md`` §1): RapidOCR 3.x, routed to the
    #: degraded pages (below), moves 0,819 → 0,893 and invented moves 291 →
    #: 169 with no stratum regressing outside the bootstrap interval.  A name
    #: that is not installed is simply absent from the registry.  An injected
    #: engine list (tests, ``bench_sol.py --tessdata-dir``) is the caller's
    #: choice and is not filtered.
    secondary_engines: tuple[str, ...] = ("rapidocr",)
    #: The secondary engines run only on a page whose signals justify a
    #: preprocessing variant (:func:`caissa.ocr.portfolio.degradation_reasons`):
    #: measured on the golden corpus they win the degraded strata and lose on
    #: clean scans and native pages, so they enter where the portfolio enters.
    secondary_only_when_degraded: bool = True
    #: OCR_UI_ROADMAP passo 2: on a region whose text layer was kept with
    #: damaged notation (``TextLayerVerdict.notation_damaged``), the layer
    #: takes the anchor seat regardless of its capped score and the engines
    #: supply the moves token by token: its prose is the book's own, the
    #: damage is confined to the move tokens, and a mangled token is a
    #: non-word the fusion replaces with a supported reading.  ``False``
    #: lets the arbiter's winner (Tesseract, usually) anchor instead.
    damaged_layer_anchors: bool = True
    page: PageConfig = field(default_factory=PageConfig)
    #: OCR_UI_ROADMAP_C2 passo B9: the extra candidates of a region — the
    #: movetext profiles, the glyph reader, the figurine model, the cascade
    #: on each preprocessing variant — are independent readings of the same
    #: pixels, and Tesseract (a subprocess) and the ONNX readers release the
    #: GIL.  They run on this many threads; ``1`` is the serial loop of
    #: before.  The candidate list keeps its order whatever the threads did,
    #: so the fusion (and the trace) stay byte-for-byte deterministic.
    workers: int = 4
    #: A region already accepted is not re-read on any variant; a region
    #: below this score is not worth the variants either (noise is noise
    #: on every image).  In between, the portfolio earns its cost.
    min_score_for_variants: float = 0.15
    #: OCR_UI ciclo 2, passo B10: the book cipher settles a symbol per
    #: *style* — the size class of the line the symbol was seen on, against
    #: the page's body size (:func:`caissa.ocr.notation.book_cipher.size_class`)
    #: — before it settles the style-less row, so a look-alike the main line
    #: and the small-type variations use for two different figurines proves
    #: in each.  ``False`` keys every observation to the style-less row (the
    #: table of before).
    cipher_style: bool = True
    #: B10: a row whose last ``cipher_window`` pages agree is proven for the
    #: pages that follow even when an earlier page contradicted it (a window
    #: of pages, because the swaps of one page are one burst).  ``0`` is the
    #: table of before: a contradiction counts for ever.
    cipher_window: int = 6
    #: B10: the row's piece is the majority of its evidence, not the first
    #: swap seen.  ``False`` is the version-1 rule -- the sabotage.
    cipher_majority: bool = True


# --------------------------------------------------------------------------- #
# Page context (Sol §SOL-8)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DiagramRef:
    """A diagram the importer located on the page, for movetext association.

    Attributes:
        box: Board rectangle in ``page.rect`` points.
        fen: The position read, or ``None`` when only located.
        trusted: Whether the FEN's provenance allows a legality replay to
            start from it (an exact vector read, or a verified reading).
        side_to_move: ``"w"``/``"b"`` when the caption said so; ``None``
            otherwise — never defaulted.
    """

    box: tuple[float, float, float, float]
    fen: str | None = None
    trusted: bool = False
    side_to_move: str | None = None


@dataclass(frozen=True, slots=True)
class PageContext:
    """What the importer knows about the page before the OCR runs."""

    diagrams: tuple[DiagramRef, ...] = ()
    notation_locale: str | None = None


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Candidate:
    """One reading of a region: engine × variant, with its decision."""

    variant: str
    engine: str
    result: OcrResult          # boxes in original page pixel space
    decision: RegionDecision
    score: float
    outcome: ArbitrationOutcome
    #: A second opinion (the figurine reader): it supplies alternatives to
    #: the fusion and never becomes the region's reading by itself.
    secondary: bool = False

    @property
    def rank(self) -> tuple[int, int, float]:
        return (0 if self.secondary else 1), _DECISION_RANK[self.decision.decision], self.score


@dataclass(frozen=True, slots=True)
class RegionRecognition:
    """What the service settled on for one region."""

    reading_order: int
    kind: RegionKind
    box_px: BBox                       # original page pixel space
    result: OcrResult                  # the chosen (or fused) reading
    decision: RegionDecision
    engine: str
    variant: str
    score: float
    candidates: tuple[Candidate, ...] = ()
    own_verdict: bool = False
    legality: dict[str, Any] = field(default_factory=dict)
    fusion: dict[str, Any] = field(default_factory=dict)
    #: A person settled this region (OCR_UI_ROADMAP passo 14): the IR says so.
    verified: bool = False

    @property
    def emits_text(self) -> bool:
        return self.decision.decision is not Decision.ABSTAINED

    @property
    def text(self) -> str:
        return self.result.text

    def as_dict(self) -> dict[str, Any]:
        return {
            "reading_order": self.reading_order,
            "kind": str(self.kind),
            "box_px": [round(self.box_px.x0, 1), round(self.box_px.y0, 1),
                       round(self.box_px.x1, 1), round(self.box_px.y1, 1)],
            "engine": self.engine,
            "variant": self.variant,
            "score": round(self.score, 4),
            "decision": self.decision.as_dict(),
            "candidates": [
                {"variant": c.variant, "engine": c.engine, "score": round(c.score, 4),
                 "decision": str(c.decision.decision), "chars": c.result.char_count}
                for c in self.candidates
            ],
            "own_verdict": self.own_verdict,
            "legality": self.legality,
            "fusion": self.fusion,
            "chars": self.result.char_count,
            "mean_confidence": round(self.result.mean_confidence, 4),
            "estimated_cer": self.estimated_cer,
        }

    @property
    def estimated_cer(self) -> dict[str, float]:
        """Sol §SOL-10: the CER estimate *and* how much to trust the estimate."""
        from caissa.ocr.quality import estimate_cer

        if self.result.is_empty:
            return {"cer": 1.0, "confidence": 1.0}
        cer, confidence = estimate_cer(self.result.text, self.result.lang)
        return {"cer": round(float(cer), 4), "confidence": round(float(confidence), 3)}


@dataclass(slots=True)
class PageRecognition:
    """Everything the service did to one page, and what it emits."""

    page_index: int
    dpi: float
    regions: list[RegionRecognition]
    portfolio: Portfolio | None
    notes: list[str]
    duration_s: float
    whole_page: bool
    engines: dict[str, str]            # engine name → version

    @property
    def emitted(self) -> list[RegionRecognition]:
        return [r for r in self.regions if r.emits_text and r.result.text.strip()]

    @property
    def text(self) -> str:
        return "\n".join(r.text for r in self.emitted)

    @property
    def answered(self) -> bool:
        return bool(self.emitted)

    @property
    def decision(self) -> Decision:
        """The page's decision.

        A page with one accepted paragraph and two abstained margins has
        accepted text; a page with one accepted paragraph and one paragraph
        sent to review **needs review** -- that region's text enters the page
        flagged, and calling the page "accepted" hid it behind the page-level
        ``below_threshold`` (the benchmark's "silent import" count, which
        counted exactly these pages once passo B1 made scans multi-region).
        """
        if not self.regions:
            return Decision.ABSTAINED
        emitted = [r.decision.decision for r in self.regions if r.emits_text]
        if not emitted:
            return Decision.ABSTAINED
        if Decision.REVIEW in emitted:
            return Decision.REVIEW
        return max(emitted, key=lambda d: _DECISION_RANK[d])

    @property
    def confidence(self) -> float:
        """Length-weighted mean score of the emitted regions."""
        total = 0.0
        weight = 0.0
        for region in self.emitted:
            n = max(1, region.result.char_count)
            total += region.score * n
            weight += n
        return total / weight if weight else 0.0

    @property
    def below_threshold(self) -> bool:
        return any(r.decision.below_threshold for r in self.emitted)

    @property
    def engine(self) -> str:
        names = sorted({r.engine for r in self.emitted})
        return "+".join(names)

    @property
    def review_regions(self) -> list[RegionRecognition]:
        return [r for r in self.regions if r.decision.decision is Decision.REVIEW]

    @property
    def abstained_regions(self) -> list[RegionRecognition]:
        return [r for r in self.regions if r.decision.decision is Decision.ABSTAINED]

    @property
    def decision_counts(self) -> dict[str, int]:
        counts = {str(d): 0 for d in Decision}
        for region in self.regions:
            counts[str(region.decision.decision)] += 1
        return counts

    def trace(self) -> dict[str, Any]:
        """The provenance record (Sol §SOL-10), JSON-ready."""
        return {
            "page_index": self.page_index,
            "dpi": self.dpi,
            "whole_page": self.whole_page,
            "engines": dict(self.engines),
            "portfolio": self.portfolio.as_dict() if self.portfolio else None,
            "decisions": self.decision_counts,
            "regions": [r.as_dict() for r in self.regions],
            "notes": list(self.notes),
            "duration_s": round(self.duration_s, 4),
        }

    def to_page_text(self, frame: PageFrame) -> PageText:
        """The importer's shape: one line per OCR line, with the span
        carrying confidence, engine and the review flag.

        A word that carries a figurine gets a span of its own, with the
        engine that put the figurine there — the glyph reader, the book's
        figurine model, or the cipher (an inference, not a reading) — and
        that word's confidence (OCR_UI ciclo 2, B10/G7).  Before this the
        line collapsed into one span with the line's worst confidence and the
        origin of a figurine survived only in the trace; the reviewer could
        not tell a figurine read at 0,99 from one the cipher inferred.
        """
        lines: list[TextLine] = []
        scale = frame.scale_for(self.dpi)
        for region in self.emitted:
            review = region.decision.decision is Decision.REVIEW
            origins = _figurine_origins(region)
            for index, line in enumerate(region.result.lines):
                text = line.text
                if not text.strip() or _is_board_coordinates(text):
                    continue
                px = (line.box.x0, line.box.y0, line.box.x1, line.box.y1)
                box = frame.pixels_to_page(px, self.dpi)
                size = (line.font_size / scale) if line.font_size else (box[3] - box[1])
                lines.append(TextLine(
                    box=box,
                    spans=_line_spans(line, text, box, size, region, review, origins, frame,
                                      self.dpi),
                    block_index=(int(line.block_index) if line.block_index >= 0
                                 else region.reading_order * 1000 + index),
                ))
        return PageText(frame=frame, lines=tuple(lines), source=self.engine or "ocr")


# --------------------------------------------------------------------------- #
# The service
# --------------------------------------------------------------------------- #


class OcrService:
    """The default :data:`~caissa.ingest.pdf.importer.OcrProvider`."""

    def __init__(self, engines: Sequence[OcrEngine] | None = None,
                 config: OcrServiceConfig | None = None, *,
                 lang: str = "",
                 logger: logging.Logger | None = None,
                 glyph_engine: OcrEngine | None = None,
                 figurine_engine: OcrEngine | None = None) -> None:
        self.config = config or OcrServiceConfig()
        self.log = logger or LOGGER
        self.lang = lang or self.config.default_lang
        self._engines: list[OcrEngine] | None = list(engines) if engines is not None else None
        #: The figurine reader; built on first use unless injected (tests).
        self._glyph_engine: OcrEngine | None = glyph_engine
        self._glyph_probed = glyph_engine is not None
        #: The fine-tuned figurine model, likewise.
        self._figurine_engine: OcrEngine | None = figurine_engine
        self._figurine_probed = figurine_engine is not None
        self._figurine_dir: Path | None = None
        #: The book's model as anchor (passo 4b), built on first use.
        self._book_anchor: Any = None
        self._recognizers: dict[str, PageRecognizer] = {}
        self._pool: Any = None
        self.last: PageRecognition | None = None
        #: Set by the importer before each page: diagrams and notation locale.
        self.page_context: PageContext | None = None
        #: OCR_UI_ROADMAP passo 3: the book's figurine cipher, proved by
        #: legality across its blocks (:mod:`caissa.ocr.notation.book_cipher`).
        #: Set by the importer for the PDF at hand; the service feeds it every
        #: proof a complete replay yields and hands its proven rows to the
        #: validator of every notation region.
        self.book_cipher: Any = None

    # -- engines ----------------------------------------------------------- #

    def engines_for(self, lang: str, *, secondary: bool = True) -> list[OcrEngine]:
        if self._engines is not None:
            return [e for e in self._engines if e.available() and e.supports_language(lang)]
        from caissa.ocr.engines.base import EngineLevel
        from caissa.ocr.engines.registry import default_registry

        allowed = set(self.config.secondary_engines) if secondary else set()
        engines = [e for e in default_registry().available(lang=lang)
                   if e.capabilities().level <= EngineLevel.TESSERACT or e.name in allowed]
        anchor = self.book_anchor(lang)
        if anchor is not None:
            # The book's model takes the Tesseract seat; the base stays out
            # (it would be the same reader without the figurines).
            engines = [anchor if e.name == anchor.name else e for e in engines]
            if all(e.name != anchor.name for e in engines):
                engines.insert(0, anchor)
        return engines

    def book_anchor(self, lang: str) -> OcrEngine | None:
        """The registered book's model as anchor engine, when passo 4b applies.

        Only with ``figurine_tessdata`` set explicitly (a book registered for
        the PDF) and a model for the book's own language in it.
        """
        cfg = self.config
        if not cfg.book_model_anchors or not cfg.figurine_tessdata:
            return None
        if self._book_anchor is None:
            from caissa.ocr.engines.tesseract import TunedTesseractEngine

            engine = TunedTesseractEngine(cfg.figurine_tessdata, prefix=cfg.figurine_prefix)
            if not engine.available():
                self.log.info("modelo do livro indisponível na âncora: %s",
                              engine.unavailable_reason())
                return None
            self._book_anchor = engine
        anchor = self._book_anchor
        return anchor if anchor.has_model_for(lang) and anchor.supports_language(lang) else None

    def recognizer_for(self, lang: str, *, secondary: bool = True) -> PageRecognizer:
        key = f"{lang}|{'+' if secondary else '-'}"
        if key not in self._recognizers:
            self._recognizers[key] = PageRecognizer(
                self.engines_for(lang, secondary=secondary), self.config.page, self.log)
        return self._recognizers[key]

    def _wants_secondary(self, image: NDArray[np.uint8], dpi: int,
                         notes: list[str]) -> tuple[bool, Any]:
        """Whether this page gets the secondary engines, and the signals measured."""
        cfg = self.config
        if not cfg.secondary_engines:
            return False, None
        if not cfg.secondary_only_when_degraded:
            return True, None
        from caissa.ocr.portfolio import degradation_reasons, detect_signals

        signals = detect_signals(image, dpi=dpi)
        reasons = degradation_reasons(signals, dpi=dpi, config=cfg.portfolio)
        if reasons:
            notes.append("motor secundário nesta página: " + ", ".join(reasons))
        return bool(reasons), signals

    def engine_versions(self, lang: str) -> dict[str, str]:
        versions: dict[str, str] = {}
        for engine in self.engines_for(lang):
            version = getattr(engine, "version", None)
            if callable(version):
                version = version()
            versions[engine.name] = str(version) if version else ""
        return versions

    @property
    def available(self) -> bool:
        return any(not e.capabilities().requires_pdf_page for e in self.engines_for(self.lang))

    # -- provider protocol ------------------------------------------------- #

    def __call__(self, page: Any, frame: PageFrame, verdict: TextLayerVerdict) -> PageText | None:
        recognition = self.recognize(page, frame, verdict)
        self.last = recognition
        if not recognition.answered:
            return None
        return recognition.to_page_text(frame)

    # -- resolution -------------------------------------------------------- #

    def choose_dpi(self, page: Any, frame: PageFrame, verdict: TextLayerVerdict | None) -> int:
        """300 DPI unless the page is small print or a low-resolution scan."""
        cfg = self.config
        try:
            if verdict is not None and verdict.is_image_only:
                infos = page.get_image_info() if hasattr(page, "get_image_info") else []
                for info in infos:
                    bbox = info.get("bbox")
                    width = info.get("width")
                    if not bbox or not width:
                        continue
                    inches = max(1e-3, (bbox[2] - bbox[0]) / 72.0)
                    if (bbox[2] - bbox[0]) >= 0.5 * frame.width and width / inches < cfg.low_scan_dpi:
                        return cfg.high_dpi
            sizes: list[float] = []
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            sizes.append(float(span.get("size", 0.0)))
            if sizes:
                sizes.sort()
                if sizes[len(sizes) // 2] <= cfg.small_text_pt:
                    return cfg.high_dpi
        except Exception as exc:  # noqa: BLE001 - a resolution guess must never fail a page
            self.log.debug("escolha de DPI falhou na página %d: %s", frame.index, exc)
        return cfg.base_dpi

    @staticmethod
    def render(page: Any, dpi: int) -> NDArray[np.uint8]:
        import pymupdf

        pix = page.get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY, alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()

    # -- recognition ------------------------------------------------------- #

    @staticmethod
    def engine_lang(lang: str) -> str:
        """The language string the engines get.

        A Cyrillic book writes its squares in Latin letters — ``Кd2``, ``f4``
        — and Tesseract's ``rus`` model alone reads ``f4`` as ``14``.  So a
        Cyrillic language always travels with ``eng`` (Sol §SOL-7, the
        notation convention is detected separately from the prose language).
        """
        parts = [p for p in (lang or "").split("+") if p]
        if any(p in ("rus", "ukr", "bul", "srp", "bel", "mkd") for p in parts) and "eng" not in parts:
            parts.append("eng")
        return "+".join(parts)

    def recognize(self, page: Any, frame: PageFrame,
                  verdict: TextLayerVerdict | None = None, *,
                  lang: str = "", diagrams: Sequence[BBox] = ()) -> PageRecognition:
        """OCR one PDF page: layout from the text layer when it has one."""
        started = time.perf_counter()
        lang = self.engine_lang(lang or self.lang)
        dpi = self.choose_dpi(page, frame, verdict)
        image = self.render(page, dpi)
        task = PageTask(pdf_page=page, image=image, lang=lang, dpi=float(dpi),
                        diagrams=tuple(diagrams), page_index=frame.index,
                        verso_sources=self._neighbour_renders(page, dpi))
        return self._recognize_task(task, image, started)

    def _neighbour_renders(self, page: Any, dpi: int) -> Callable[[], list[NDArray[np.uint8]]]:
        """The pages either side of ``page``, rendered at ``dpi`` — lazily,
        because only a page with show-through will ask (passo B8)."""
        def render_neighbours() -> list[NDArray[np.uint8]]:
            out: list[NDArray[np.uint8]] = []
            try:
                document = page.parent
                number = int(page.number)
            except Exception:  # noqa: BLE001 - a page without a document has no neighbours
                return out
            for index in (number - 1, number + 1):
                if index < 0 or index >= len(document):
                    continue
                try:
                    out.append(self.render(document[index], dpi))
                except Exception as exc:  # noqa: BLE001 - a neighbour that fails is no verso
                    self.log.debug("verso: página %d não renderizou: %s", index, exc)
            return out
        return render_neighbours

    def recognize_image(self, image: NDArray[Any], *, dpi: float = 300.0, lang: str = "",
                        page_index: int = 0) -> PageRecognition:
        """OCR a raster with no PDF behind it (a photograph, the benchmark)."""
        started = time.perf_counter()
        gray = _to_gray(image)
        task = PageTask(image=gray, lang=self.engine_lang(lang or self.lang), dpi=float(dpi),
                        page_index=page_index)
        return self._recognize_task(task, gray, started)

    def _recognize_task(self, task: PageTask, image: NDArray[np.uint8],
                        started: float) -> PageRecognition:
        cfg = self.config
        notes: list[str] = []
        secondary, signals = self._wants_secondary(image, int(task.dpi), notes)
        recognizer = self.recognizer_for(task.lang, secondary=secondary)
        outcome: PageOutcome = recognizer.run(task)
        notes.extend(outcome.notes)
        portfolio: Portfolio | None = None
        regions: list[RegionRecognition] = []

        # B10: the page's body size, so a region (and a token) can say whether
        # it is set in the body face, in small type or in display type.
        body_size = body_size_of(
            line.font_size for r in outcome.regions for line in r.result.lines)
        for region_outcome in outcome.regions:
            check_cancel()
            base = self._candidate("original", region_outcome)
            candidates = [base]
            candidates.extend(self._engine_candidates(recognizer, region_outcome, task))
            # The independent readings, as thunks, in the order the serial
            # loop produced them; the pool runs them, the list keeps the order.
            readings: list[Callable[[], list[Candidate]]] = []
            if cfg.movetext_candidates:
                readings.append(lambda r=region_outcome: self._profile_candidates(recognizer, r, task, notes))
            if cfg.glyph_candidates:
                readings.append(lambda r=region_outcome: self._glyph_candidates(recognizer, r, task))
            if cfg.figurine_candidates:
                readings.append(lambda r=region_outcome: self._figurine_candidates(recognizer, r, task))
            if self._wants_variants(region_outcome):
                if portfolio is None:
                    portfolio = self._portfolio(image, int(task.dpi), notes, signals=signals,
                                                verso=self._verso_for(task, image, signals, notes))
                for variant in portfolio.variants[1:]:
                    readings.append(lambda v=variant, r=region_outcome: [
                        c for c in (self._read_on_variant(recognizer, v, r, task),)
                        if c is not None])
            for extra in self._run_readings(readings):
                candidates.extend(extra)
            regions.append(self._settle(region_outcome, candidates, task, recognizer,
                                        body_size=body_size))

        # A page where every region died inside the engine is not "a page
        # with nothing to read": it is a setup fault (a tessdata folder
        # without configs, a relative path the engine cannot see) and must
        # say so, or a whole benchmark abstains in silence.
        failed = [r for r in regions if r.result.is_empty
                  and r.candidates and r.candidates[0].result.meta.get("error_detail")]
        if regions and len(failed) == len(regions):
            detail = str(failed[0].candidates[0].result.meta["error_detail"]).strip().splitlines()
            note = (f"todas as {len(regions)} regiões falharam no motor "
                    f"{failed[0].candidates[0].result.engine}: {detail[0] if detail else '?'}")
            notes.append(note)
            self.log.warning("página %d: %s", task.page_index, note)

        recognition = PageRecognition(
            page_index=task.page_index, dpi=task.dpi, regions=regions,
            portfolio=portfolio, notes=notes,
            duration_s=time.perf_counter() - started,
            whole_page=outcome.whole_page,
            engines=self.engine_versions(task.lang),
        )
        self.log.debug("página %d: %s", task.page_index, recognition.decision_counts)
        return recognition

    # -- candidates -------------------------------------------------------- #

    def _run_readings(self, readings: Sequence[Callable[[], list[Candidate]]]
                      ) -> list[list[Candidate]]:
        """Run the independent readings of a region, in parallel when the
        service has workers, and return their results **in submission order**
        (passo B9).  Each thread inherits the caller's context — the
        cancellation hook of :mod:`caissa.ocr.cancel` included — and a
        cancellation raised in any of them is re-raised here after the others
        are collected."""
        if not readings:
            return []
        workers = int(self.config.workers or 1)
        if workers <= 1 or len(readings) == 1:
            return [reading() for reading in readings]
        if self._pool is None:
            from concurrent.futures import ThreadPoolExecutor

            self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="caissa-ocr")
        import contextvars

        futures = [self._pool.submit(contextvars.copy_context().run, reading)
                   for reading in readings]
        out: list[list[Candidate]] = []
        canceled: BaseException | None = None
        for future in futures:
            try:
                out.append(future.result())
            except OcrCanceled as exc:
                canceled = exc
                out.append([])
        if canceled is not None:
            raise canceled
        return out

    @staticmethod
    def _candidate(variant: str, region_outcome: RegionOutcome) -> Candidate:
        arbitration = region_outcome.outcome
        decision = arbitration.decision or RegionDecision(
            Decision.ACCEPTED if not arbitration.result.is_empty else Decision.ABSTAINED,
            arbitration.winner.total if arbitration.winner else 0.0, 0.0, 0.0, ())
        return Candidate(
            variant=variant, engine=region_outcome.engine, result=region_outcome.result,
            decision=decision, score=arbitration.winner.total if arbitration.winner else 0.0,
            outcome=arbitration,
        )

    @staticmethod
    def _engine_candidates(recognizer: PageRecognizer, region_outcome: RegionOutcome,
                           task: PageTask) -> list[Candidate]:
        """The readings of the engines that ran on the region and did not win.

        OCR_UI_ROADMAP passo 1: with a second engine in the cascade the
        arbiter's loser is still a reading of the same pixels — the fusion
        needs it as a candidate, and the figurine guard of :meth:`_settle`
        needs the Tesseract reading at hand when the winner may not anchor.
        Each loser carries **its own** decision, judged by the same policy on
        its own arbiter score: a reading the arbiter would have abstained on
        stays abstained here (a flat "review" label let 41 abstained move
        regions come out accepted on 2026-09-14).
        """
        from caissa.ocr.decision import decide
        from caissa.ocr.lexicon import normalise_lang

        arbitration = region_outcome.outcome
        scores = {score.engine: score for score in arbitration.scores}
        out: list[Candidate] = []
        for result in arbitration.candidates:
            # The winner is the base candidate already (possibly as a
            # transformed copy, so compare by engine, not identity).
            if (result.engine in {region_outcome.engine, arbitration.result.engine}
                    or result.is_empty or not result.text.strip()):
                continue
            score = scores.get(result.engine)
            total = float(score.total) if score is not None else 0.0
            level = int(score.level) if score is not None else 1
            decision = decide(
                result, total, policy=recognizer.config.arbiter.policy,
                image=task.image, langs=normalise_lang(task.lang),
                region_kind=region_outcome.region.kind,
                accept_threshold=recognizer.config.arbiter.threshold_for(level))
            out.append(Candidate(
                variant="original", engine=result.engine, result=result,
                decision=decision, score=total, outcome=arbitration))
        return out

    def _wants_variants(self, region_outcome: RegionOutcome) -> bool:
        if not self.config.use_portfolio:
            return False
        arbitration = region_outcome.outcome
        if arbitration.accepted and not arbitration.result.is_empty:
            return False
        # A level-0 winner was read, not recognised; a variant of the raster
        # cannot improve a text layer, and the region has no raster engine
        # to run.
        raster_ran = any(not r.is_empty or r.engine != "pdf_text_layer"
                         for r in arbitration.candidates)
        if not raster_ran and arbitration.engines_run:
            return False
        score = arbitration.winner.total if arbitration.winner else 0.0
        return score >= self.config.min_score_for_variants or arbitration.result.is_empty

    def _verso_for(self, task: PageTask, image: NDArray[np.uint8], signals: Any,
                   notes: list[str]) -> NDArray[np.uint8] | None:
        """The verso the bleed step should subtract, or ``None`` (passo B8).

        Only asked for on a page whose show-through signal crosses the
        portfolio's floor; the candidates are the neighbouring pages (and,
        allowed, the page's own mirror), each mirrored and registered by
        :meth:`BleedThroughReduction.register_verso`; the best correlation
        wins when it clears the floor, and the note says which.
        """
        cfg = self.config
        if not cfg.use_verso or signals is None:
            return None
        if float(getattr(signals, "bleed_share", 0.0)) < cfg.portfolio.min_bleed_share:
            return None
        from caissa.ocr.preprocess import BleedThroughReduction, to_gray

        candidates: list[tuple[str, NDArray[np.uint8]]] = []
        if task.verso_sources is not None:
            try:
                candidates += [(f"página vizinha {n + 1}", to_gray(v))
                               for n, v in enumerate(task.verso_sources())]
            except Exception as exc:  # noqa: BLE001 - no neighbours is the heuristic path
                self.log.debug("verso: vizinhas indisponíveis: %s", exc)
        if cfg.verso_self_mirror:
            candidates.append(("espelho da própria página", image))
        if not candidates:
            return None
        step = BleedThroughReduction()
        gray = to_gray(image)
        best: tuple[float, str, NDArray[np.uint8]] | None = None
        for name, candidate in candidates:
            try:
                _, _, score = step.register_verso(gray, candidate, int(task.dpi))
            except Exception as exc:  # noqa: BLE001 - a candidate that fails to register is no verso
                self.log.debug("verso: %s não registrou: %s", name, exc)
                continue
            if best is None or score > best[0]:
                best = (score, name, candidate)
        if best is None or best[0] < cfg.verso_min_correlation:
            notes.append("verso: nenhum candidato correlaciona com a transparência "
                         f"(melhor {best[0]:.2f} < {cfg.verso_min_correlation:.2f}); "
                         "redução heurística." if best else
                         "verso: nenhum candidato registrou; redução heurística.")
            return None
        notes.append(f"verso real: {best[1]} registrada com correlação {best[0]:.2f}.")
        return best[2]

    def _portfolio(self, image: NDArray[np.uint8], dpi: int, notes: list[str],
                   signals: Any = None, verso: NDArray[np.uint8] | None = None) -> Portfolio:
        from dataclasses import replace

        config = (replace(self.config.portfolio, verso=verso) if verso is not None
                  else self.config.portfolio)
        portfolio = build_portfolio(image, dpi=dpi, config=config, signals=signals)
        if len(portfolio.variants) > 1:
            notes.append("portfólio: " + ", ".join(
                f"{v.name} ({'; '.join(v.reasons_pt)})" for v in portfolio.variants[1:]))
        notes.extend(portfolio.notes)
        return portfolio

    def _read_on_variant(self, recognizer: PageRecognizer, variant: Variant,
                         region_outcome: RegionOutcome, task: PageTask) -> Candidate | None:
        """Run the raster cascade on the region's crop of ``variant``."""
        region = region_outcome.region
        # Layout is in points when there is a PDF behind the page, and in
        # raster pixels when there is not (the page box *is* the image box).
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        vbox = variant.geometry.to_variant(box_px)
        h, w = variant.image.shape[:2]
        clipped = vbox.clipped_to(BBox(0.0, 0.0, float(w), float(h)))
        x, y, cw, ch = clipped.to_int_tuple()
        if cw <= 0 or ch <= 0:
            return None
        crop = variant.image[y:y + ch, x:x + cw]
        arbitration = recognizer.arbiter.run(RegionTask(
            image=crop, region_kind=region.kind, lang=task.lang, pdf_page=None,
            scale=task.scale, region_id=f"p{task.page_index}r{region.reading_order}@{variant.name}",
        ))
        if arbitration.decision is None:
            return None
        result = arbitration.result
        if result.lines:
            result = _translate(result, float(x), float(y))
            result = variant.map_result(result)
        return Candidate(
            variant=variant.name, engine=result.engine, result=result,
            decision=arbitration.decision,
            score=arbitration.winner.total if arbitration.winner else 0.0,
            outcome=arbitration,
        )

    def _profile_candidates(self, recognizer: PageRecognizer, region_outcome: RegionOutcome,
                            task: PageTask, notes: list[str] | None = None) -> list[Candidate]:
        """Sol §SOL-7: the movetext and strict readings of a movetext-like region.

        Only when Tesseract is the engine that read it (the profiles are
        Tesseract's), only when the region looks like notation, and only on
        the original render — the variants get the region-kind profile by
        themselves through ``psm_hint``.
        """
        from caissa.ocr.decision import decide
        from caissa.ocr.engines.profiles import TesseractProfile
        from caissa.ocr.lexicon import normalise_lang

        arbitration = region_outcome.outcome
        result = arbitration.result
        region = region_outcome.region
        if result.is_empty or result.engine != "tesseract" or task.image is None:
            return []
        engine = next((e for e in recognizer.engines
                       if getattr(e, "name", "") == "tesseract"
                       and hasattr(e, "recognize_with_profile")), None)
        if engine is None:
            return []
        movetext = region.kind is RegionKind.MOVETEXT or _looks_like_movetext(result)
        if not movetext:
            if self.config.movetext_strips and _carries_notation(result):
                return self._strip_candidates(recognizer, engine, region_outcome, task, notes)
            return []
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        h, w = task.image.shape[:2]
        x, y, cw, ch = box_px.clipped_to(BBox(0.0, 0.0, float(w), float(h))).to_int_tuple()
        if cw <= 0 or ch <= 0:
            return []
        crop = task.image[y:y + ch, x:x + cw]
        profiles = [TesseractProfile.MOVETEXT_STRICT]
        if str(result.meta.get("profile", "")) != str(TesseractProfile.MOVETEXT):
            profiles.insert(0, TesseractProfile.MOVETEXT)
        out: list[Candidate] = []
        threshold = float(result.meta.get("arbiter_threshold", 0.78))
        for profile in profiles:
            try:
                reading = engine.recognize_with_profile(
                    crop, lang=task.lang, psm_hint=RegionKind.MOVETEXT, profile=profile)
            except Exception as exc:  # noqa: BLE001 - an extra candidate must never fail the page
                self.log.debug("perfil %s falhou: %s", profile, exc)
                continue
            if reading.is_empty:
                continue
            reading = _translate(reading, float(x), float(y)).with_meta(variant=str(profile))
            score = recognizer.arbiter.score(
                reading, level=1, lang=task.lang,
                task=RegionTask(image=crop, region_kind=RegionKind.MOVETEXT, lang=task.lang,
                                scale=task.scale)).total
            decision = decide(reading, score, policy=recognizer.config.arbiter.policy,
                              image=task.image, langs=normalise_lang(task.lang),
                              region_kind=RegionKind.MOVETEXT, accept_threshold=threshold)
            out.append(Candidate(variant=str(profile), engine=reading.engine, result=reading,
                                 decision=decision, score=score, outcome=arbitration))
        return out

    def _strip_candidates(self, recognizer: PageRecognizer, engine: Any,
                          region_outcome: RegionOutcome, task: PageTask,
                          notes: list[str] | None = None) -> list[Candidate]:
        """The movetext profile on the notation lines of a mixed region (passo B2).

        One strip per line of the anchor that carries notation, read in PSM 7
        with the movetext profile (DAWGs off, the move patterns on), and all
        the strips as **one** candidate whose lines the fusion pairs with the
        anchor's by geometry.  Lines of plain prose are not read again: the
        prose profile is the right one for them, and a strip of prose read
        without a dictionary would only feed the fusion worse readings.
        """
        from caissa.ocr.decision import decide
        from caissa.ocr.engines.profiles import TesseractProfile
        from caissa.ocr.lexicon import normalise_lang

        arbitration = region_outcome.outcome
        result = arbitration.result
        region = region_outcome.region
        assert task.image is not None
        h, w = task.image.shape[:2]
        image_box = BBox(0.0, 0.0, float(w), float(h))
        lines: list[OcrLine] = []
        strips = 0
        # Consecutive notation lines form one band, read in one call: a
        # paragraph of analysis is a run of such lines, and one Tesseract
        # call per line (0,10–0,17 s of fixed overhead each) made a page of
        # forty lines cost six seconds more.  A band is PSM 6 (a uniform
        # block) with the movetext profile; a lone line is PSM 7.
        bands: list[list[OcrLine]] = []
        for line in result.lines:
            if line.words and _line_carries_notation(line):
                if bands and bands[-1] and self._adjacent(bands[-1][-1], line):
                    bands[-1].append(line)
                else:
                    bands.append([line])
        for band in bands[:self.config.movetext_strips_max]:
            box = BBox.union_of([line.box for line in band])
            # A third of a line of paper above and below: Tesseract wants
            # the ascenders and descenders whole and a margin around them,
            # and the line box hugs the ink.
            strip = box.expanded(0.35 * band[0].box.h).clipped_to(image_box)
            x, y, cw, ch = strip.to_int_tuple()
            if cw <= 0 or ch <= 0:
                continue
            crop = task.image[y:y + ch, x:x + cw]
            try:
                reading = engine.recognize_with_profile(
                    crop, lang=task.lang,
                    psm_hint=RegionKind.SINGLE_LINE if len(band) == 1 else RegionKind.MOVETEXT,
                    profile=TesseractProfile.MOVETEXT)
            except Exception as exc:  # noqa: BLE001 - an extra candidate must never fail the page
                # Never silently (crítico Codex, fase 2 ciclo 1): the page keeps
                # its anchor, but the recognition says the strips were lost --
                # one note per region, on the page's notes, and a warning.
                self.log.warning("página %d, região %s: a faixa de lances falhou: %s",
                                 task.page_index, region.reading_order, exc)
                if notes is not None and not any(f"região {region.reading_order}" in n
                                                 and "faixa de lances falhou" in n for n in notes):
                    notes.append(f"faixa de lances falhou na região {region.reading_order}: "
                                 f"{type(exc).__name__}: {exc}")
                continue
            strips += 1
            if reading.is_empty:
                continue
            for read in _translate(reading, float(x), float(y)).lines:
                if read.words:
                    lines.append(read)
        if not lines:
            return []
        # Its own engine name and ``secondary=True``: the strips are a *subset*
        # of the region's lines, and a candidate that can anchor would make
        # the region *be* those lines (measured 2026-09-20: ``twocol:d:12``
        # CER 0,0016 → 0,68, REVIEW → ACCEPTED, when the strips outscored the
        # whole reading).  The fusion pairs them by geometry and lets them
        # replace only a token the anchor doubted.
        reading = OcrResult(
            engine=STRIPS_ENGINE, lang=result.lang, lines=tuple(lines),
            region_kind=RegionKind.MOVETEXT, duration_s=0.0,
            meta={"variant": "movetext_strips", "profile": str(TesseractProfile.MOVETEXT),
                  "strips": strips})
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        x, y, cw, ch = box_px.clipped_to(image_box).to_int_tuple()
        crop = task.image[y:y + ch, x:x + cw] if cw > 0 and ch > 0 else task.image
        threshold = float(result.meta.get("arbiter_threshold", 0.78))
        score = recognizer.arbiter.score(
            reading, level=1, lang=task.lang,
            task=RegionTask(image=crop, region_kind=RegionKind.MOVETEXT, lang=task.lang,
                            scale=task.scale)).total
        decision = decide(reading, score, policy=recognizer.config.arbiter.policy,
                          image=task.image, langs=normalise_lang(task.lang),
                          region_kind=RegionKind.MOVETEXT, accept_threshold=threshold)
        return [Candidate(variant="movetext_strips", engine=reading.engine, result=reading,
                          decision=decision, score=score, outcome=arbitration, secondary=True)]

    @staticmethod
    def _adjacent(above: OcrLine, below: OcrLine) -> bool:
        """Two lines of the same column, one under the other, at most a line apart."""
        gap = below.box.y0 - above.box.y1
        return (gap <= max(above.box.h, below.box.h)
                and above.box.horizontal_overlap(below.box) >= 0.3)

    def glyph_engine(self) -> OcrEngine | None:
        """The trunk's glyph reader when this machine has it, else ``None``.

        Probed once per service; its absence is logged once, not per page.
        """
        if not self._glyph_probed:
            self._glyph_probed = True
            from caissa.ocr.engines.glyph import default_glyph_engine

            engine = default_glyph_engine()
            if engine.available():
                self._glyph_engine = engine
            else:
                self.log.info("leitor de figurinas indisponível: %s", engine.unavailable_reason())
        return self._glyph_engine

    def figurine_engine(self) -> OcrEngine | None:
        """A Tesseract over the fine-tuned models' directory, when one exists."""
        if not self._figurine_probed:
            self._figurine_probed = True
            directory = self._figurine_directory()
            if directory is not None:
                from caissa.ocr.engines.tesseract import TesseractConfig, TesseractEngine

                engine = TesseractEngine(TesseractConfig(tessdata_dir=str(directory),
                                                         use_profiles=False))
                if engine.available():
                    self._figurine_engine = engine
                    self._figurine_dir = directory
                else:
                    self.log.info("modelo de figurinas indisponível: %s",
                                  engine.unavailable_reason())
        return self._figurine_engine

    def _figurine_directory(self) -> Path | None:
        from caissa.ocr.training.books import models_root

        cfg = self.config
        candidates = [cfg.figurine_tessdata, str(models_root())]
        for candidate in candidates:
            if candidate and any(Path(candidate).glob(f"{cfg.figurine_prefix}_*.traineddata")):
                return Path(candidate)
        return None

    def _figurine_lang(self, lang: str) -> str | None:
        """``eng`` → ``caissa_eng`` for every part that has a model; ``None``
        when no part has one (the base languages are not re-run)."""
        directory = self._figurine_dir
        parts = [part for part in lang.split("+") if part]
        if directory is None or not parts:
            return None
        prefix = self.config.figurine_prefix
        # The book's own language (the first part) must have a model: a
        # Russian page is not read with the English figurine model just
        # because ``eng`` travels along for the Latin squares.
        if not (directory / f"{prefix}_{parts[0]}.traineddata").is_file():
            return None
        tuned = [f"{prefix}_{part}" for part in parts
                 if (directory / f"{prefix}_{part}.traineddata").is_file()]
        return "+".join(tuned)

    def _figurine_candidates(self, recognizer: PageRecognizer, region_outcome: RegionOutcome,
                             task: PageTask) -> list[Candidate]:
        """The fine-tuned model's reading of a notation region as a secondary
        candidate: the fusion takes its figurines, never its inventions."""
        from dataclasses import replace

        from caissa.ocr.decision import decide
        from caissa.ocr.lexicon import normalise_lang

        arbitration = region_outcome.outcome
        result = arbitration.result
        region = region_outcome.region
        if result.is_empty or task.image is None:
            return []
        if not (region.kind is RegionKind.MOVETEXT or _looks_like_movetext(result)
                or _carries_notation(result)):
            return []
        if self.book_anchor(task.lang) is not None:
            return []  # the model already read the region, as the anchor
        engine = self.figurine_engine()
        lang = self._figurine_lang(task.lang) if engine is not None else None
        if engine is None or lang is None:
            return []
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        h, w = task.image.shape[:2]
        x, y, cw, ch = box_px.clipped_to(BBox(0.0, 0.0, float(w), float(h))).to_int_tuple()
        if cw <= 0 or ch <= 0:
            return []
        crop = task.image[y:y + ch, x:x + cw]
        try:
            reading = engine.recognize(crop, lang=lang, psm_hint=RegionKind.MOVETEXT)
        except Exception as exc:  # noqa: BLE001 - an extra candidate must never fail the page
            self.log.debug("modelo de figurinas falhou: %s", exc)
            return []
        if reading.is_empty:
            return []
        # Its own engine name, so the fusion can keep it off the anchor seat.
        reading = replace(_translate(reading, float(x), float(y)), engine=FIGURINE_ENGINE)
        reading = reading.with_meta(variant="figurine", model=lang)
        threshold = float(result.meta.get("arbiter_threshold", 0.78))
        score = recognizer.arbiter.score(
            reading, level=1, lang=task.lang,
            task=RegionTask(image=crop, region_kind=RegionKind.MOVETEXT, lang=task.lang,
                            scale=task.scale)).total
        decision = decide(reading, score, policy=recognizer.config.arbiter.policy,
                          image=task.image, langs=normalise_lang(task.lang),
                          region_kind=RegionKind.MOVETEXT, accept_threshold=threshold)
        return [Candidate(variant="figurine", engine=FIGURINE_ENGINE, result=reading,
                          decision=decision, score=score, outcome=arbitration, secondary=True)]

    def _glyph_candidates(self, recognizer: PageRecognizer,  # noqa: PLR0911 - each return is a reason not to run
                          region_outcome: RegionOutcome, task: PageTask) -> list[Candidate]:
        """The glyph classifier's reading of a movetext-like region.

        One more candidate for the fusion, only where notation is: the
        engine is a figurine reader, and its prose is worse than Tesseract's.
        """
        from caissa.ocr.decision import decide
        from caissa.ocr.lexicon import normalise_lang

        arbitration = region_outcome.outcome
        result = arbitration.result
        region = region_outcome.region
        if result.is_empty or task.image is None:
            return []
        if not (region.kind is RegionKind.MOVETEXT or _looks_like_movetext(result)
                or _carries_notation(result)):
            return []
        engine = self.glyph_engine()
        if engine is None or not engine.supports_language(task.lang):
            return []
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        h, w = task.image.shape[:2]
        x, y, cw, ch = box_px.clipped_to(BBox(0.0, 0.0, float(w), float(h))).to_int_tuple()
        if cw <= 0 or ch <= 0:
            return []
        crop = task.image[y:y + ch, x:x + cw]
        # One strip per line the anchor already found: the glyph reader then
        # never merges two columns into one line, and the fusion pairs lines
        # one to one.  Strips are in crop pixels.
        strips = [line.box.translated(-float(x), -float(y)) for line in result.lines if line.words]
        try:
            read_lines = getattr(engine, "recognize_lines", None)
            if read_lines is not None and strips:
                reading = read_lines(crop, strips, lang=task.lang, psm_hint=RegionKind.MOVETEXT)
            else:
                reading = engine.recognize(crop, lang=task.lang, psm_hint=RegionKind.MOVETEXT)
        except Exception as exc:  # noqa: BLE001 - an extra candidate must never fail the page
            self.log.debug("leitor de figurinas falhou: %s", exc)
            return []
        if reading.is_empty:
            return []
        reading = _translate(reading, float(x), float(y)).with_meta(variant="glyph")
        threshold = float(result.meta.get("arbiter_threshold", 0.78))
        score = recognizer.arbiter.score(
            reading, level=1, lang=task.lang,
            task=RegionTask(image=crop, region_kind=RegionKind.MOVETEXT, lang=task.lang,
                            scale=task.scale)).total
        decision = decide(reading, score, policy=recognizer.config.arbiter.policy,
                          image=task.image, langs=normalise_lang(task.lang),
                          region_kind=RegionKind.MOVETEXT, accept_threshold=threshold)
        return [Candidate(variant="glyph", engine=reading.engine, result=reading,
                          decision=decision, score=score, outcome=arbitration, secondary=True)]

    def _settle(self, region_outcome: RegionOutcome, candidates: list[Candidate],
                task: PageTask, recognizer: PageRecognizer | None = None, *,
                body_size: float = 0.0) -> RegionRecognition:
        """Pick the best candidate, fuse, validate, and record everything.

        ``body_size`` is the page's body line size (B10): with it the region
        and each swapped token get a style for the book cipher; without it
        every observation is style-less.
        """
        cfg = self.config
        if recognizer is None:
            recognizer = self.recognizer_for(task.lang)
        if not body_size:
            body_size = body_size_of(line.font_size for line in region_outcome.result.lines)
        region_style = (size_class(body_size_of(line.font_size
                                                for line in region_outcome.result.lines),
                                   body_size) if cfg.cipher_style else STYLE_ANY)
        # Who may hold the anchor seat.  The second opinions never do; and a
        # secondary engine (OCR_UI_ROADMAP passo 1: RapidOCR) does not where
        # the glyph reader sees figurines — measured on the SFC4 scans, it
        # drops ♖ and ♕ from the moves it wins, and the swap that rescues
        # Tesseract's look-alikes has nothing to swap in its output.  The
        # Tesseract reading is among the candidates (``_engine_candidates``)
        # and takes the seat; RapidOCR stays as an alternative per token.
        never_anchor = {c.result.engine for c in candidates if c.secondary}
        if cfg.secondary_engines and any(
                c.variant == "glyph" and _has_figurines(c.result) for c in candidates):
            never_anchor.update(cfg.secondary_engines)
        anchorable = [c for c in candidates if c.engine not in never_anchor] or candidates
        damaged_layer = next(
            (c for c in anchorable if c.engine == "pdf_text_layer"
             and c.result.meta.get("notation_damaged") and not c.result.is_empty), None)
        if cfg.damaged_layer_anchors and damaged_layer is not None:
            best = damaged_layer
            never_anchor.update(c.engine for c in candidates
                                if c.engine != "pdf_text_layer" and not c.secondary)
        else:
            best = max(anchorable, key=lambda c: c.rank)
        result, decision, fusion = best.result, best.decision, {}
        if cfg.fuse and len(candidates) > 1:
            try:
                from caissa.ocr.fusion import FusionConfig, fuse_candidates

                fused = fuse_candidates(
                    [(c.result, c.score, c.decision) for c in candidates],
                    lang=task.lang, image=task.image if task.pdf_page is None else None,
                    config=FusionConfig(**self.config.fusion) if self.config.fusion else None,
                    never_anchor=frozenset(never_anchor),
                    calibrators=self._calibrators(recognizer, candidates, region_outcome, task))
                if fused is not None:
                    result, decision, fusion = fused.result, fused.decision, fused.as_dict()
                    if self.book_cipher is not None:
                        self._observe_glyph_swaps(fused, task.page_index, task.lang,
                                                  body_size=body_size if cfg.cipher_style else 0.0)
                    if (cfg.fusion_rescue and best.decision.decision is Decision.ABSTAINED
                            and decision.decision is Decision.ABSTAINED):
                        rescued = self._rescue_abstained(
                            recognizer, fused, best, candidates, region_outcome, task)
                        if rescued is not None:
                            decision = rescued
                            fusion["rescued"] = True
            except ImportError:
                pass
        region = region_outcome.region
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        legality: dict[str, Any] = {}
        # A region whose moves came out as cipher (``Hd2``, ``'i'd6+``) does not
        # *look* like movetext yet — no token is a move — but it carries the
        # notation the validator and the book cipher exist for (passo 3).
        movetext = (region.kind is RegionKind.MOVETEXT or _looks_like_movetext(result)
                    or _carries_notation(result))
        if cfg.validate_notation and movetext and not result.is_empty:
            from caissa.ocr.notation.validate import validate_region

            diagram = self._diagram_for(box_px, task)
            context = self.page_context
            book = self.book_cipher
            validated = validate_region(
                result, decision, lang=task.lang,
                start_fen=diagram.fen if diagram else None,
                fen_trusted=bool(diagram and diagram.trusted),
                side_to_move=diagram.side_to_move if diagram else None,
                notation_locale=context.notation_locale if context else None,
                image=task.image if task.pdf_page is None else None,
                book_cipher=(book.proven(style=region_style if cfg.cipher_style else None,
                                         window=cfg.cipher_window, majority=cfg.cipher_majority)
                             if book is not None else None))
            result, decision, legality = validated.result, validated.decision, validated.as_dict()
            if book is not None:
                for symbol, piece, raw, san in validated.proven_pieces:
                    book.observe(symbol, piece, page=task.page_index, raw=raw, san=san,
                                 style=region_style, confidence=float(decision.score))
            if diagram is not None:
                legality["diagram"] = list(diagram.box)
        return RegionRecognition(
            reading_order=region.reading_order, kind=region.kind, box_px=box_px,
            result=result, decision=decision, engine=result.engine or best.engine,
            variant=str(result.meta.get("variant", best.variant)), score=best.score,
            candidates=tuple(candidates), own_verdict=region_outcome.own_verdict,
            legality=legality, fusion=fusion,
        )


    @staticmethod
    def _calibrators(recognizer: PageRecognizer, candidates: Sequence[Candidate],
                     region_outcome: RegionOutcome, task: PageTask) -> dict[str, Any]:
        """Engine → the function that puts its raw word confidence on the
        arbiter's calibrated scale (passo B6), for the engines that have a
        fitted table.  The facet is the region's, the same the arbiter used
        to score the candidate."""
        from caissa.ocr.arbiter import Arbiter

        out: dict[str, Any] = {}
        region_task = RegionTask(image=task.image, region_kind=region_outcome.region.kind,
                                 lang=task.lang, scale=task.scale)
        for candidate in candidates:
            engine = candidate.result.engine
            if engine in out:
                continue
            # `calibration_for` maps an engine to the scale it borrows
            # (`arbiter.SCALE_OF`: the strips of passo B2 are Tesseract's).
            key = Arbiter._facet_key(candidate.result, region_task)  # noqa: SLF001 - the arbiter's own facet
            calibration = recognizer.config.arbiter.calibration_for(engine, key)
            if calibration.table is not None:
                out[engine] = calibration.apply
        return out

    def _rescue_abstained(self, recognizer: PageRecognizer, fused: Any, best: Candidate,
                          candidates: Sequence[Candidate], region_outcome: RegionOutcome,
                          task: PageTask) -> RegionDecision | None:
        """Passo B5: the fused text of an abstained anchor, judged on its own.

        ``None`` when no independent candidate (another engine, or a second
        opinion) was accepted or sent to review agreeing with the fused text
        on enough move tokens; otherwise the fused result scored by the
        arbiter and decided again, never above REVIEW, and never past the
        evidence floors (a region with no ink under its words stays abstained
        whatever the agreement).
        """
        from caissa.ocr.decision import decide
        from caissa.ocr.lexicon import is_move_token, tokenize, normalise_lang

        wanted = self.config.fusion_rescue_moves
        moves = {t.casefold() for t in tokenize(fused.result.text) if is_move_token(t)}
        if len(moves) < wanted:
            return None
        anchor_engine = best.result.engine
        supporters = []
        for candidate in candidates:
            if candidate is best or candidate.decision.decision is Decision.ABSTAINED:
                continue
            independent = candidate.result.engine != anchor_engine or candidate.secondary
            if not independent:
                continue
            theirs = {t.casefold() for t in tokenize(candidate.result.text) if is_move_token(t)}
            agreeing = len(moves & theirs)
            if agreeing >= wanted:
                supporters.append((agreeing, candidate))
        if not supporters:
            return None
        agreeing, supporter = max(supporters, key=lambda pair: pair[0])
        region = region_outcome.region
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        crop = task.image
        if task.image is not None:
            h, w = task.image.shape[:2]
            x, y, cw, ch = box_px.clipped_to(BBox(0.0, 0.0, float(w), float(h))).to_int_tuple()
            if cw > 0 and ch > 0:
                crop = task.image[y:y + ch, x:x + cw]
        score = recognizer.arbiter.score(
            fused.result, level=1, lang=task.lang,
            others=[c.result for c in candidates if c is not best],
            task=RegionTask(image=crop, region_kind=region.kind, lang=task.lang,
                            scale=task.scale)).total
        decision = decide(
            fused.result, score, policy=recognizer.config.arbiter.policy,
            image=task.image if task.pdf_page is None else None,
            langs=normalise_lang(task.lang), region_kind=region.kind,
            accept_threshold=best.decision.accept_threshold)
        if decision.decision is Decision.ABSTAINED:
            return None
        reason = (f"o motor âncora se absteve (escore {best.score:.3f}); o texto fundido, "
                  f"re-pontuado em {score:.3f}, concorda em {agreeing} lance(s) com "
                  f"{supporter.engine}/{supporter.variant} — vai à revisão, nunca aceito.")
        return RegionDecision(
            Decision.REVIEW, decision.score, decision.accept_threshold,
            decision.review_threshold, decision.reasons_pt + (reason,),
            decision.evidence, decision.flagged_words, True, decision.legality)

    def _observe_glyph_swaps(self, fused: Any, page_index: int, lang: str, *,
                             body_size: float = 0.0) -> None:
        """Feed the book cipher the look-alike → figurine swaps the fusion made.

        Each swap (``Hea!`` → ``♖e8!``) is the glyph reader's visual proof, at
        ≥ 0,70, that this book's ``H`` is the rook.  It is the second source of
        evidence of :mod:`caissa.ocr.notation.book_cipher`, tagged ``glyph`` so
        the table can demand more of them than of a legal replay.  A piece
        letter of the book's own language is never recorded as a symbol
        (SPEC R2.3): a table row ``R → B`` would rewrite a printed rook.

        B10: each observation carries the *style* of the line the token sits
        on (its size class against ``body_size``; style-less when ``0``) and
        the confidence of the reading that made the swap.
        """
        from caissa.ocr.fusion import _FIGURINES, _NUMBER_PREFIX, _figurine_cut
        from caissa.ocr.notation.cipher import ENGLISH_PIECES, _piece_letters

        letters = dict(zip("♔♕♖♗♘♙♚♛♜♝♞♟", "KQRBNPKQRBNP", strict=True))
        first = (lang or "").split("+")[0]
        guarded = _piece_letters(first) | frozenset(ENGLISH_PIECES)
        # The fused result's words are the tokens in order, line by line
        # (``fusion._rebuild``): walking both together gives each token its line.
        styles: list[str] = []
        if body_size:
            for line in fused.result.lines:
                styles.extend([size_class(line.font_size, body_size)] * len(line.words))
        if len(styles) != len(fused.tokens):
            styles = [STYLE_ANY] * len(fused.tokens)
        for token, style in zip(fused.tokens, styles, strict=True):
            if token.chosen_from == fused.anchor or not token.readings:
                continue
            anchor = token.readings[0].text
            chosen = token.text
            cut = _figurine_cut(anchor, chosen)
            if cut is None:
                continue
            core_a = _NUMBER_PREFIX.sub("", anchor)
            core_c = _NUMBER_PREFIX.sub("", chosen)
            if not core_c or core_c[0] not in _FIGURINES:
                continue
            symbol = core_a[:cut]
            # The symbol is the whole look-alike: one character, or a short
            # cluster with a non-alphanumeric character in it (a word never
            # has one); it is never a piece letter of the book's language.
            if (not symbol or len(symbol) > 5 or symbol in guarded or symbol[0] in "abcdefgh"
                    or any(ch in _FIGURINES for ch in symbol)
                    or (len(symbol) > 1 and all(ch.isalnum() for ch in symbol))):
                continue
            swap_confidence = max((r.confidence for r in token.readings
                                   if r.source == token.chosen_from), default=token.confidence)
            self.book_cipher.observe(symbol, letters[core_c[0]], page=page_index,
                                     raw=anchor, san=chosen, source="glyph", style=style,
                                     confidence=float(swap_confidence))

    def _diagram_for(self, box_px: BBox, task: PageTask) -> DiagramRef | None:
        """The diagram a movetext region most plausibly continues from.

        The nearest one *above* the region that shares its column: a solution
        follows its diagram, and the column keeps a left-hand board from
        claiming a right-hand line.  A diagram below or beside is not "the
        position before these moves", whatever its confidence.
        """
        context = self.page_context
        if context is None or not context.diagrams or task.pdf_page is None:
            return None
        best: tuple[float, DiagramRef] | None = None
        for diagram in context.diagrams:
            if diagram.fen is None:
                continue
            dbox = BBox.from_edges(*diagram.box).scaled(task.scale)
            if dbox.y1 > box_px.y0 + 0.25 * box_px.h:
                continue
            if dbox.horizontal_overlap(box_px) < 0.3:
                continue
            gap = box_px.y0 - dbox.y1
            if best is None or gap < best[0]:
                best = (gap, diagram)
        return best[1] if best else None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_FIGURINE_CHARS = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")


def _figurine_origins(region: RegionRecognition) -> dict[str, str]:
    """token text → engine that produced the figurine in it, for the region.

    From the trace the fusion and the validation left in the result's meta:
    ``fusion_tokens`` (``from`` = ``variant/engine`` of the winning reading)
    and ``book_cipher_applied`` (raw → decoded, the cipher's rewrites).  A
    token in both is the cipher's (:data:`~caissa.ingest.pdf.textlayer.CIPHER_ORIGIN`):
    the cipher ran last.
    """
    origins: dict[str, str] = {}
    meta = region.result.meta
    for token in meta.get("fusion_tokens", ()) or ():
        if not isinstance(token, Mapping):
            continue
        text = str(token.get("text", ""))
        engine = str(token.get("from", "")).rsplit("/", 1)[-1]
        if text and engine and any(ch in _FIGURINE_CHARS for ch in text):
            origins[text] = engine
    applied = meta.get("book_cipher_applied")
    if isinstance(applied, Mapping):
        for decoded in applied.values():
            if any(ch in _FIGURINE_CHARS for ch in str(decoded)):
                origins[str(decoded)] = CIPHER_ORIGIN
    return origins


def _line_spans(line: OcrLine, text: str, box: RectT, size: float, region: RegionRecognition,
                review: bool, origins: Mapping[str, str], frame: PageFrame,
                dpi: float) -> tuple[TextSpan, ...]:
    """The spans of one OCR line: one, unless a word carries a figurine.

    The figurine word becomes its own span with its own confidence and the
    origin of the figurine (``figurine_origin``: the glyph reader, the
    figurine model, or the cipher); the words around it keep the line's
    span.  Every span keeps the region's ``engine`` -- the block's
    provenance says who read the words (Sol §SOL-10), the glyph's says who
    put the piece there.  Word boxes come from the OCR; the line box is what
    the text-flow uses.
    """
    common = dict(size=size, baseline=box[3], review=review, verified=region.verified)
    if not any(ch in _FIGURINE_CHARS for ch in text) or not line.words:
        return (TextSpan(text=text, box=box, confidence=float(line.confidence),
                         engine=region.engine, **common),)
    spans: list[TextSpan] = []
    buffer: list[str] = []
    for word in line.words:
        if not any(ch in _FIGURINE_CHARS for ch in word.text):
            buffer.append(word.text)
            continue
        if buffer:
            spans.append(TextSpan(text=" ".join(buffer) + " ", box=box,
                                  confidence=float(line.confidence), engine=region.engine,
                                  **common))
            buffer = []
        origin = origins.get(word.text, "")
        if origin == region.engine:
            origin = ""
        px = (word.box.x0, word.box.y0, word.box.x1, word.box.y1)
        spans.append(TextSpan(text=word.text + " ", box=frame.pixels_to_page(px, dpi),
                              confidence=float(word.confidence), engine=region.engine,
                              figurine_origin=origin, **common))
    if buffer:
        spans.append(TextSpan(text=" ".join(buffer), box=box, confidence=float(line.confidence),
                              engine=region.engine, **common))
    elif spans:
        last = spans[-1]
        spans[-1] = replace(last, text=last.text.rstrip())
    return tuple(spans)


def _to_gray(image: NDArray[Any]) -> NDArray[np.uint8]:
    array = np.asarray(image)
    if array.ndim == 3:
        array = array.mean(axis=2)
    return np.ascontiguousarray(array.astype(np.uint8))


def _translate(result: OcrResult, dx: float, dy: float) -> OcrResult:
    from caissa.ocr.page import PageRecognizer as _Runner

    return _Runner._to_page_space(result, (dx, dy))  # noqa: SLF001 - the one translation routine


_COORDINATE_TOKEN = frozenset("abcdefgh12345678")


def _is_board_coordinates(text: str) -> bool:
    """``a b c d e f g h`` or ``8 7 6 5``: the letters and digits printed around
    a diagram, which an engine reads as a line of one-character words.  Not
    prose, and a movetext line always has a longer token."""
    tokens = text.split()
    if len(tokens) < 2:
        return False
    flat = "".join(tokens)
    return all(len(t) <= 2 and set(t) <= _COORDINATE_TOKEN for t in tokens) and len(flat) <= 16


_FIGURINES = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")


def _has_figurines(result: OcrResult, *, min_confidence: float = 0.70) -> bool:
    """Whether a reading carries at least one confident figurine token."""
    return any(any(ch in _FIGURINES for ch in word.text) and word.confidence >= min_confidence
               for line in result.lines for word in line.words)


def _looks_like_movetext(result: OcrResult) -> bool:
    from caissa.ocr.lexicon import is_move_token, tokenize

    # Move numbers and their dots are the notation's own furniture, not
    # tokens that could have been moves: ``10.d4`` tokenises as three, and
    # counting them against the move made a line of numbered moves past
    # move 9 read as one third notation (passo B2).
    tokens = [t for t in tokenize(result.text) if not (t.isdigit() or set(t) <= set(".…"))]
    if len(tokens) < 6:
        return False
    return sum(1 for t in tokens if is_move_token(t)) >= 0.5 * len(tokens)


def _line_carries_notation(line: OcrLine, *, min_moves: int = 2) -> bool:
    """A line with at least two move tokens in it: a strip worth the movetext
    profile (passo B2).  Not :func:`_carries_notation`, whose share rule is
    for a region — one line of prose with a square name in it (``the e4
    pawn``) is not a strip of moves, and each strip is one Tesseract call."""
    from caissa.ocr.lexicon import is_move_token, tokenize

    return sum(1 for t in tokenize(line.text) if is_move_token(t)) >= min_moves


def _carries_notation(result: OcrResult, *, many: int = 4, min_share: float = 0.2) -> bool:
    """Whether a region has enough notation in it to be worth a figurine reading.

    Looser than :func:`_looks_like_movetext` on purpose: with figurines
    read as Latin look-alikes (``Hea!``) no token *is* a move yet, so the
    test counts what survives the cipher — move numbers, squares, marks —
    and a page mixing prose and moves passes while pure prose does not.
    """
    from caissa.ocr.lexicon import is_chess_notation, tokenize

    tokens = tokenize(result.text)
    if not tokens:
        return False
    notation = sum(1 for t in tokens if is_chess_notation(t))
    # A short region of moves (``36... Hea!``) passes on share; a long
    # prose region with a few move numbers passes on count.
    return notation >= 1 and (notation / len(tokens) >= min_share or notation >= many)


_DEFAULT: OcrService | None = None


def default_ocr_service() -> OcrService:
    """Process-wide service over the default engine registry."""
    global _DEFAULT  # noqa: PLW0603 - one lazily built service per process
    if _DEFAULT is None:
        _DEFAULT = OcrService()
    return _DEFAULT


ProviderFactory = Callable[[], OcrService]
