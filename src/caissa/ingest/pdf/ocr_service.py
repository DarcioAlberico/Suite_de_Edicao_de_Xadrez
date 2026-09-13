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
    "OcrService",
    "OcrServiceConfig",
    "PageRecognition",
    "RegionRecognition",
    "default_ocr_service",
]

LOGGER = logging.getLogger("caissa.ingest.pdf.ocr_service")

_DECISION_RANK = {Decision.ACCEPTED: 2, Decision.REVIEW: 1, Decision.ABSTAINED: 0}


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
    page: PageConfig = field(default_factory=PageConfig)
    #: A region already accepted is not re-read on any variant; a region
    #: below this score is not worth the variants either (noise is noise
    #: on every image).  In between, the portfolio earns its cost.
    min_score_for_variants: float = 0.15


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

    @property
    def rank(self) -> tuple[int, float]:
        return _DECISION_RANK[self.decision.decision], self.score


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
        }


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
                 logger: logging.Logger | None = None) -> None:
        self.config = config or OcrServiceConfig()
        self.log = logger or LOGGER
        self.lang = lang or self.config.default_lang
        self._engines: list[OcrEngine] | None = list(engines) if engines is not None else None
        self._recognizers: dict[str, PageRecognizer] = {}
        self.last: PageRecognition | None = None

    # -- engines ----------------------------------------------------------- #

    def engines_for(self, lang: str) -> list[OcrEngine]:
        if self._engines is not None:
            return [e for e in self._engines if e.available() and e.supports_language(lang)]
        from caissa.ocr.engines.registry import default_registry

        return default_registry().available(lang=lang)

    def recognizer_for(self, lang: str) -> PageRecognizer:
        if lang not in self._recognizers:
            self._recognizers[lang] = PageRecognizer(
                self.engines_for(lang), self.config.page, self.log)
        return self._recognizers[lang]

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

    def recognize(self, page: Any, frame: PageFrame,
                  verdict: TextLayerVerdict | None = None, *,
                  lang: str = "", diagrams: Sequence[BBox] = ()) -> PageRecognition:
        """OCR one PDF page: layout from the text layer when it has one."""
        started = time.perf_counter()
        lang = lang or self.lang
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
        task = PageTask(image=gray, lang=lang or self.lang, dpi=float(dpi),
                        page_index=page_index)
        return self._recognize_task(task, gray, started)

    def _recognize_task(self, task: PageTask, image: NDArray[np.uint8],
                        started: float) -> PageRecognition:
        cfg = self.config
        recognizer = self.recognizer_for(task.lang)
        outcome: PageOutcome = recognizer.run(task)
        notes = list(outcome.notes)
        portfolio: Portfolio | None = None
        regions: list[RegionRecognition] = []

        for region_outcome in outcome.regions:
            base = self._candidate("original", region_outcome)
            candidates = [base]
            if self._wants_variants(region_outcome):
                if portfolio is None:
                    portfolio = self._portfolio(image, int(task.dpi), notes)
                for variant in portfolio.variants[1:]:
                    candidate = self._read_on_variant(recognizer, variant, region_outcome, task)
                    if candidate is not None:
                        candidates.append(candidate)
            regions.append(self._settle(region_outcome, candidates, task))

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

    def _portfolio(self, image: NDArray[np.uint8], dpi: int, notes: list[str]) -> Portfolio:
        portfolio = build_portfolio(image, dpi=dpi, config=self.config.portfolio)
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

    def _settle(self, region_outcome: RegionOutcome, candidates: list[Candidate],
                task: PageTask) -> RegionRecognition:
        """Pick the best candidate, fuse, validate, and record everything."""
        cfg = self.config
        best = max(candidates, key=lambda c: c.rank)
        result, decision, fusion = best.result, best.decision, {}
        if cfg.fuse and len(candidates) > 1:
            try:
                from caissa.ocr.fusion import fuse_candidates

                fused = fuse_candidates(
                    [(c.result, c.score, c.decision) for c in candidates],
                    lang=task.lang, image=task.image if task.pdf_page is None else None)
                if fused is not None:
                    result, decision, fusion = fused.result, fused.decision, fused.as_dict()
            except ImportError:
                pass
        legality: dict[str, Any] = {}
        movetext = (region_outcome.region.kind is RegionKind.MOVETEXT
                    or _looks_like_movetext(result))
        if cfg.validate_notation and movetext and not result.is_empty:
            try:
                from caissa.ocr.notation.validate import validate_region

                validated = validate_region(result, decision, lang=task.lang)
                result, decision, legality = validated.result, validated.decision, validated.as_dict()
            except ImportError:
                pass
        region = region_outcome.region
        box_px = region.box.scaled(task.scale) if task.pdf_page is not None else region.box
        return RegionRecognition(
            reading_order=region.reading_order, kind=region.kind, box_px=box_px,
            result=result, decision=decision, engine=result.engine or best.engine,
            variant=str(result.meta.get("variant", best.variant)), score=best.score,
            candidates=tuple(candidates), own_verdict=region_outcome.own_verdict,
            legality=legality, fusion=fusion,
        )


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


def _looks_like_movetext(result: OcrResult) -> bool:
    from caissa.ocr.lexicon import is_move_token, tokenize

    tokens = tokenize(result.text)
    if len(tokens) < 6:
        return False
    return sum(1 for t in tokens if is_move_token(t)) >= 0.5 * len(tokens)


_DEFAULT: OcrService | None = None


def default_ocr_service() -> OcrService:
    """Process-wide service over the default engine registry."""
    global _DEFAULT  # noqa: PLW0603 - one lazily built service per process
    if _DEFAULT is None:
        _DEFAULT = OcrService()
    return _DEFAULT


ProviderFactory = Callable[[], OcrService]
