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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan
from caissa.ocr.arbiter import ArbitrationOutcome, RegionTask
from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.engines.base import OcrEngine
from caissa.ocr.engines.pdf_text_layer import TextLayerVerdict
from caissa.ocr.page import PageConfig, PageOutcome, PageRecognizer, PageTask, RegionOutcome
from caissa.ocr.portfolio import Portfolio, PortfolioConfig, Variant, build_portfolio
from caissa.ocr.types import BBox, OcrResult, RegionKind

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
    #: Fuse the candidates of a region token by token (Sol §SOL-6).
    fuse: bool = True
    #: Replay movetext regions for legality (Sol §SOL-8).
    validate_notation: bool = True
    #: Sol §SOL-7: on a region that reads as movetext, add Tesseract's
    #: movetext profile and its strict (whitelisted) profile as extra
    #: candidates for fusion.  The strict one is never the sole reading.
    movetext_candidates: bool = True
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
    #: A region already accepted is not re-read on any variant; a region
    #: below this score is not worth the variants either (noise is noise
    #: on every image).  In between, the portfolio earns its cost.
    min_score_for_variants: float = 0.15


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
        """The page's decision: the *best* region's, because a page with one
        accepted paragraph and two abstained margins has accepted text."""
        if not self.regions:
            return Decision.ABSTAINED
        return max((r.decision.decision for r in self.regions),
                   key=lambda d: _DECISION_RANK[d])

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
        carrying confidence, engine and the review flag."""
        lines: list[TextLine] = []
        scale = frame.scale_for(self.dpi)
        for region in self.emitted:
            review = region.decision.decision is Decision.REVIEW
            for index, line in enumerate(region.result.lines):
                text = line.text
                if not text.strip() or _is_board_coordinates(text):
                    continue
                px = (line.box.x0, line.box.y0, line.box.x1, line.box.y1)
                box = frame.pixels_to_page(px, self.dpi)
                size = (line.font_size / scale) if line.font_size else (box[3] - box[1])
                lines.append(TextLine(
                    box=box,
                    spans=(TextSpan(text=text, box=box, size=size, baseline=box[3],
                                    confidence=float(line.confidence),
                                    engine=region.engine, review=review),),
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
                        diagrams=tuple(diagrams), page_index=frame.index)
        return self._recognize_task(task, image, started)

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

        for region_outcome in outcome.regions:
            base = self._candidate("original", region_outcome)
            candidates = [base]
            candidates.extend(self._engine_candidates(recognizer, region_outcome, task))
            if cfg.movetext_candidates:
                candidates.extend(self._profile_candidates(recognizer, region_outcome, task))
            if cfg.glyph_candidates:
                candidates.extend(self._glyph_candidates(recognizer, region_outcome, task))
            if cfg.figurine_candidates:
                candidates.extend(self._figurine_candidates(recognizer, region_outcome, task))
            if self._wants_variants(region_outcome):
                if portfolio is None:
                    portfolio = self._portfolio(image, int(task.dpi), notes, signals=signals)
                for variant in portfolio.variants[1:]:
                    candidate = self._read_on_variant(recognizer, variant, region_outcome, task)
                    if candidate is not None:
                        candidates.append(candidate)
            regions.append(self._settle(region_outcome, candidates, task))

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

    def _portfolio(self, image: NDArray[np.uint8], dpi: int, notes: list[str],
                   signals: Any = None) -> Portfolio:
        portfolio = build_portfolio(image, dpi=dpi, config=self.config.portfolio,
                                    signals=signals)
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
                            task: PageTask) -> list[Candidate]:
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
        movetext = region.kind is RegionKind.MOVETEXT or _looks_like_movetext(result)
        if not movetext:
            return []
        engine = next((e for e in recognizer.engines
                       if getattr(e, "name", "") == "tesseract"
                       and hasattr(e, "recognize_with_profile")), None)
        if engine is None:
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
                task: PageTask) -> RegionRecognition:
        """Pick the best candidate, fuse, validate, and record everything."""
        cfg = self.config
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
                from caissa.ocr.fusion import fuse_candidates

                fused = fuse_candidates(
                    [(c.result, c.score, c.decision) for c in candidates],
                    lang=task.lang, image=task.image if task.pdf_page is None else None,
                    never_anchor=frozenset(never_anchor))
                if fused is not None:
                    result, decision, fusion = fused.result, fused.decision, fused.as_dict()
                    if self.book_cipher is not None:
                        self._observe_glyph_swaps(fused, task.page_index, task.lang)
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
                book_cipher=book.proven() if book is not None else None)
            result, decision, legality = validated.result, validated.decision, validated.as_dict()
            if book is not None:
                for symbol, piece, raw, san in validated.proven_pieces:
                    book.observe(symbol, piece, page=task.page_index, raw=raw, san=san)
            if diagram is not None:
                legality["diagram"] = list(diagram.box)
        return RegionRecognition(
            reading_order=region.reading_order, kind=region.kind, box_px=box_px,
            result=result, decision=decision, engine=result.engine or best.engine,
            variant=str(result.meta.get("variant", best.variant)), score=best.score,
            candidates=tuple(candidates), own_verdict=region_outcome.own_verdict,
            legality=legality, fusion=fusion,
        )


    def _observe_glyph_swaps(self, fused: Any, page_index: int, lang: str) -> None:
        """Feed the book cipher the look-alike → figurine swaps the fusion made.

        Each swap (``Hea!`` → ``♖e8!``) is the glyph reader's visual proof, at
        ≥ 0,70, that this book's ``H`` is the rook.  It is the second source of
        evidence of :mod:`caissa.ocr.notation.book_cipher`, tagged ``glyph`` so
        the table can demand more of them than of a legal replay.  A piece
        letter of the book's own language is never recorded as a symbol
        (SPEC R2.3): a table row ``R → B`` would rewrite a printed rook.
        """
        from caissa.ocr.fusion import _FIGURINES, _NUMBER_PREFIX, _figurine_cut
        from caissa.ocr.notation.cipher import ENGLISH_PIECES, _piece_letters

        letters = dict(zip("♔♕♖♗♘♙♚♛♜♝♞♟", "KQRBNPKQRBNP", strict=True))
        first = (lang or "").split("+")[0]
        guarded = _piece_letters(first) | frozenset(ENGLISH_PIECES)
        for token in fused.tokens:
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
            self.book_cipher.observe(symbol, letters[core_c[0]], page=page_index,
                                     raw=anchor, san=chosen, source="glyph")

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

    tokens = tokenize(result.text)
    if len(tokens) < 6:
        return False
    return sum(1 for t in tokens if is_move_token(t)) >= 0.5 * len(tokens)


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
