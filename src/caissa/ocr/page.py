"""Page-level orchestration — the loop SPEC §7.1 asks for.

The arbiter recognises *one region*.  Until this module existed nothing in the
product ever called it, because the piece that cuts a page into regions and
runs the cascade on each one had never been written.  That is what this is.

Three things make it more than a ``for`` loop.

**Coordinate spaces.**  Level 0 reads the PDF and wants a clip in *points*;
every other engine reads pixels and wants a crop, whose boxes then come back
relative to the crop.  Getting this wrong produces text that is right and boxes
that are silently offset, which no test that compares strings will ever catch.
So the rule here is stated once and obeyed everywhere: **layout is done in
points, results are returned in the pixel space of the full-page raster.**
Level 0 already emits pixel boxes given ``scale``; a region result from any
other engine is translated by the region origin on the way out.

**A short region must not be condemned for being short.**  Level 0's verdict
declares a page with fewer than 24 characters to be a scan, which is right for
a page and wrong for a heading.  Assessing each region independently would
therefore reject every heading, caption and folio in the collection and send
them all to OCR — replacing a known defect with a worse one.  So a region with
too little text to judge inherits the page's verdict, and only regions with
enough text of their own get an independent one.

**A page that is broadly bad is not thirty bad regions.**  When most regions
fail level 0, cutting the page up and running Tesseract thirty times is both
slower and *worse* than handing Tesseract the whole page, because Tesseract has
its own layout analysis and the crops throw it away.  So the runner counts the
failures first and falls back to one whole-page arbitration when they pass a
threshold.

What this module does **not** do is fix the defect F5_REPORT §5 hoped it would.
Measured on Gaprindashvili p202, the destroyed move text and the correct prose
share the same *lines* — ``"For the present White cannot play 1 !txg7 Wxg7"`` —
so no geometric cut separates them.  That defect is closed by
:func:`~caissa.ocr.lexicon.mangled_move_ratio` instead.  See
``docs/quality/F5_REPORT_C2.md`` §1.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .arbiter import Arbiter, ArbiterConfig, ArbitrationOutcome, RegionTask
from .decision import Decision, RegionDecision
from .engines.base import OcrEngine
from .layout.analyze import (
    LayoutConfig,
    LayoutInput,
    LayoutRegion,
    PageLayout,
    RunningFurnitureDetector,
    analyze_page,
    lines_from_pdf_page,
)
from .layout.scan import ScanLayout, ScanLayoutConfig, scan_layout
from .types import BBox, OcrChar, OcrLine, OcrResult, RegionKind

__all__ = [
    "PageConfig",
    "PageOutcome",
    "PageRecognizer",
    "PageTask",
    "RegionOutcome",
    "recognize_page",
]

LOGGER = logging.getLogger("caissa.ocr.page")


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class PageConfig:
    """Everything the page loop can be tuned by, with the reason in place."""

    #: A region with at least this many characters of its own text layer gets
    #: an independent level-0 verdict; a shorter one inherits the page's.  The
    #: same floor level 0 uses for "is this a scan?", because it is the floor
    #: below which its lexical tests are meaningless.
    min_chars_for_own_verdict: int = 24
    #: When more than this share of arbitrated regions had to escalate past
    #: level 0, re-run the page as a single region.  Half is the point where
    #: the crops are costing more than they save.
    whole_page_fallback_frac: float = 0.50
    #: ...but never fall back on a page with fewer regions than this, where
    #: "most regions" is one or two and means nothing.
    min_regions_for_fallback: int = 4
    #: Hard ceiling on region count, so a pathological page cannot spend
    #: minutes.  Beyond it the page is treated as one region.
    max_regions: int = 60
    #: Sol §SOL-1, the confidence mask.  A page whose text layer was rejected
    #: for a *localised* defect — a broken font used by some spans, damaged
    #: notation in one block — is still cut into regions, and each region is
    #: judged on its own: the good spans keep the layer, the bad ones go to
    #: OCR.  Off, a rejected page goes to OCR whole, as before Sol.  A page
    #: with no text at all is whole-page OCR either way.
    localized_level0: bool = True
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    arbiter: ArbiterConfig = field(default_factory=ArbiterConfig)
    #: OCR_UI_ROADMAP_C2 passo B1: a page with no text layer is laid out from
    #: the word boxes of its whole-page reading (:mod:`caissa.ocr.layout.scan`)
    #: and, when that finds columns, read again region by region.
    scan: ScanLayoutConfig = field(default_factory=ScanLayoutConfig)
    #: ...and, on, read again with a second pass of the cascade over each
    #: region's crop (PSM 4/6).  Off, the regions are cut from the whole-page
    #: reading instead: the same words, in reading order, at no extra cost.
    #: Measured on the 26 two-column items of ``scan_clean_300`` (2026-09-20,
    #: ``OCR_UI_REPORT_C2.md`` §B1): slicing CER **0,0111** in 42,5 s, the
    #: second pass 0,0206 in 66,3 s, one region 0,1238 — the tight crop of a
    #: column loses to the words Tesseract already read with the whole page's
    #: context.  Off is the measured default; on stays for a page whose
    #: whole-page reading is not worth slicing.
    scan_reread: bool = False


# --------------------------------------------------------------------------- #
# Task and results
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class PageTask:
    """One page to recognise, from whichever sources are available.

    ``pdf_page`` and ``image`` are both optional but not both absent.  With a
    PDF page the layout comes free from the text layer; with only a raster
    there is no free line source, so the page goes to the cascade whole and a
    note says so — which is also the better answer, because a level-1 engine
    that declares ``handles_layout`` does its own segmentation and crops would
    only take that away from it.
    """

    pdf_page: Any = None
    image: NDArray[np.uint8] | None = None
    lang: str = "por"
    #: Raster resolution, used for the points-to-pixels scale.
    dpi: float = 300.0
    #: Chess diagrams located by the vision front (F3), in PDF points.
    diagrams: tuple[BBox, ...] = ()
    figures: tuple[BBox, ...] = ()
    page_index: int = 0
    #: A detector that has already observed the document, so running heads can
    #: be told from chapter titles.  Without one only bare folios are removed.
    furniture: RunningFurnitureDetector | None = None
    #: OCR_UI_ROADMAP_C2 passo B8: the rasters that may be the other side of
    #: this sheet (the neighbouring pages of a scanned book), rendered at the
    #: same resolution, on demand — only a page with show-through asks.
    verso_sources: Callable[[], Sequence[NDArray[np.uint8]]] | None = None

    @property
    def scale(self) -> float:
        """PDF points to raster pixels."""
        return self.dpi / 72.0

    @property
    def has_image(self) -> bool:
        return self.image is not None and getattr(self.image, "size", 0) > 0


@dataclass(frozen=True, slots=True)
class RegionOutcome:
    """What happened to one region."""

    region: LayoutRegion
    outcome: ArbitrationOutcome
    #: The chosen text, with every box in full-page pixel space.
    result: OcrResult
    #: True when the region's own text layer was judged rather than the page's.
    own_verdict: bool

    @property
    def kind(self) -> RegionKind:
        return self.region.kind

    @property
    def engine(self) -> str:
        return self.result.engine

    @property
    def escalated(self) -> bool:
        return self.outcome.escalated

    @property
    def decision(self) -> RegionDecision | None:
        return self.outcome.decision

    @property
    def emits_text(self) -> bool:
        """False for an abstained region: its text never enters the body."""
        return not self.outcome.abstained

    @property
    def needs_review(self) -> bool:
        d = self.outcome.decision
        return d is not None and d.decision is Decision.REVIEW


@dataclass(frozen=True, slots=True)
class PageOutcome:
    """The whole page: what was read, by what, and why."""

    layout: PageLayout
    regions: tuple[RegionOutcome, ...]
    notes: tuple[str, ...]
    total_duration_s: float
    #: True when the page was recognised as a single region rather than cut up.
    whole_page: bool = False
    signals: Mapping[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Every emitted region's text, in reading order.

        An abstained region (Sol §SOL-2) contributes nothing: its best
        candidate is still in :attr:`regions` for the review panel, but it
        is not text the page can be said to contain.
        """
        return "\n".join(r.result.text for r in self.regions
                         if r.result.text.strip() and r.emits_text)

    @property
    def body_text(self) -> str:
        """Reading order with running furniture and diagram labels removed."""
        return "\n".join(
            r.result.text for r in self.regions
            if r.result.text.strip()
            and r.emits_text
            and not r.kind.is_furniture
            and r.kind is not RegionKind.DIAGRAM_LABEL
        )

    @property
    def review_regions(self) -> tuple[RegionOutcome, ...]:
        return tuple(r for r in self.regions if r.needs_review)

    @property
    def abstained_regions(self) -> tuple[RegionOutcome, ...]:
        return tuple(r for r in self.regions if not r.emits_text)

    @property
    def decision_counts(self) -> dict[str, int]:
        counts = {str(d): 0 for d in Decision}
        for region in self.regions:
            if region.decision is not None:
                counts[str(region.decision.decision)] += 1
        return counts

    @property
    def engines_used(self) -> tuple[str, ...]:
        return tuple(sorted({r.engine for r in self.regions if r.result.lines}))

    @property
    def escalated_regions(self) -> tuple[RegionOutcome, ...]:
        return tuple(r for r in self.regions if r.escalated)

    def as_result(self) -> OcrResult:
        """Flatten to one :class:`OcrResult`, boxes already in page space.

        The lines keep the reading order the layout decided, which is the
        order a caller rebuilding paragraphs needs and *not* the order the
        engines produced them in.
        """
        lines: list[OcrLine] = []
        warnings: list[str] = []
        for region in self.regions:
            if not region.emits_text:
                continue
            lines.extend(region.result.lines)
            warnings.extend(region.result.warnings)
        engines = self.engines_used
        return OcrResult(
            engine="+".join(engines) if engines else "page",
            lang=self.regions[0].result.lang if self.regions else "",
            lines=tuple(lines),
            region_kind=RegionKind.PAGE,
            duration_s=self.total_duration_s,
            warnings=tuple(dict.fromkeys(warnings)),
            meta={
                "regions": len(self.regions),
                "whole_page": self.whole_page,
                "escalated": len(self.escalated_regions),
                "decisions": self.decision_counts,
                "notes": self.notes,
                **dict(self.signals),
            },
        )

    def explain_pt(self) -> str:
        head = [f"Página com {len(self.regions)} região(ões), "
                f"{len(self.escalated_regions)} escalada(s), "
                f"em {self.total_duration_s * 1000:.0f} ms."]
        for note in self.notes:
            head.append(f"  · {note}")
        for region in self.regions:
            decision = region.decision
            head.append(
                f"  [{region.region.reading_order}] {region.kind} → "
                f"{region.engine}"
                + ("" if region.own_verdict else " (veredito da página)")
                + (f" · {decision.decision}" if decision is not None else ""))
        return "\n".join(head)


# --------------------------------------------------------------------------- #
# The runner
# --------------------------------------------------------------------------- #


class PageRecognizer:
    """Cuts a page into regions and arbitrates each one."""

    def __init__(self, engines: Sequence[OcrEngine],
                 config: PageConfig | None = None,
                 logger: logging.Logger | None = None) -> None:
        self.config = config or PageConfig()
        self.log = logger or LOGGER
        self.engines = list(engines)
        self.arbiter = Arbiter(engines, self.config.arbiter, self.log)
        # Engines that read the document rather than a crop.  They are handed
        # the clip and the scale, so their boxes come back already in page
        # pixels and must **not** be translated again — doing so puts a region
        # near the foot of the page at twice its own offset, off the page
        # entirely.  Keyed by name because that is all an OcrResult carries.
        self._page_space_engines = frozenset(
            e.name for e in engines if e.capabilities().requires_pdf_page)

    # -- level 0 ----------------------------------------------------------- #

    def _text_layer_engine(self) -> Any:
        """The level-0 engine, when one is registered and usable."""
        for engine in self.engines:
            caps = engine.capabilities()
            if caps.requires_pdf_page and hasattr(engine, "assess"):
                return engine if engine.available() else None
        return None

    # -- the loop ---------------------------------------------------------- #

    def run(self, task: PageTask) -> PageOutcome:
        started = time.perf_counter()
        notes: list[str] = []

        if task.pdf_page is None:
            notes.append(
                "sem página de PDF: não há de onde tirar as linhas sem antes "
                "reconhecer, então a página foi tratada como uma região única.")
            return self._whole_page(task, started, notes)

        page_box = self._page_box(task.pdf_page)
        lines = lines_from_pdf_page(task.pdf_page, scale=1.0)
        layout = analyze_page(
            LayoutInput(page_box=page_box, lines=lines,
                        figures=task.figures, diagrams=task.diagrams,
                        page_index=task.page_index),
            config=self.config.layout, furniture=task.furniture)
        notes.extend(layout.notes)

        if not layout.regions:
            notes.append("a análise de leiaute não encontrou região alguma; "
                         "a página foi tratada como uma região única.")
            return self._whole_page(task, started, notes, layout=layout)

        # The ceiling is checked against the list that will actually be run,
        # furniture included — counting only the body regions would let a page
        # with a hundred stray margin lines through the gate it exists for.
        regions = self._all_regions(layout)
        if len(regions) > self.config.max_regions:
            notes.append(
                f"{len(regions)} regiões, acima do teto de "
                f"{self.config.max_regions}: a página foi tratada como uma "
                f"região única.")
            return self._whole_page(task, started, notes, layout=layout)

        engine = self._text_layer_engine()
        page_verdict = None
        if engine is not None:
            page_verdict = engine.assess(task.pdf_page, lang=task.lang)
            if not page_verdict.accepted:
                localized = (self.config.localized_level0
                             and not page_verdict.is_image_only
                             and self._is_localized(page_verdict, engine))
                if not localized:
                    notes.append(
                        "a camada de texto da página inteira foi reprovada "
                        f"({page_verdict.reason}) — o nível 0 não concorre em "
                        f"região nenhuma desta página.")
                    return self._whole_page(task, started, notes, layout=layout)
                notes.append(
                    "a camada de texto da página foi reprovada "
                    f"({page_verdict.reason}), mas o defeito é localizável: "
                    "cada região é julgada por si, e só as reprovadas vão ao OCR.")

        outcomes = [self._run_region(task, layout, region, engine, page_verdict)
                    for region in regions]

        escalated = sum(1 for o in outcomes if o.escalated)
        if (len(outcomes) >= self.config.min_regions_for_fallback
                and escalated > self.config.whole_page_fallback_frac
                * len(outcomes)):
            notes.append(
                f"{escalated} de {len(outcomes)} regiões escaparam do nível 0: "
                f"acima de {self.config.whole_page_fallback_frac:.0%}, "
                f"reconhecer a página inteira de uma vez é mais rápido e "
                f"melhor, porque o motor de nível 1 faz o próprio leiaute.")
            return self._whole_page(task, started, notes, layout=layout)

        return PageOutcome(
            layout=layout,
            regions=tuple(outcomes),
            notes=tuple(notes),
            total_duration_s=time.perf_counter() - started,
            whole_page=False,
            signals={
                "regions": len(outcomes),
                "escalated": escalated,
                "own_verdicts": sum(1 for o in outcomes if o.own_verdict),
                "page_verdict": (page_verdict.reason if page_verdict
                                 else "sem motor de nível 0"),
                "page_verdict_accepted": bool(page_verdict and page_verdict.accepted),
            },
        )

    @staticmethod
    def _is_localized(page_verdict: Any, engine: Any) -> bool:
        """Can a rejected page still have trustworthy regions?

        Yes when the rejection names something that lives in *part* of the
        page: a font that only some spans use, or damaged notation (which is
        a property of the figurine font, and a region without figurines is
        untouched by it).  No when the layer is globally unusable — a CMap
        that maps everything to nonsense, a page that is mostly implausible
        characters — because then every region shares the defect and
        judging thirty of them is thirty ways to be wrong.
        """
        signals = page_verdict.signals
        thresholds = getattr(engine, "thresholds", None)
        if thresholds is None:
            return False
        mangled = signals.get("mangled_move_ratio", 0.0)
        judged = signals.get("moves_judged", 0.0)
        if (judged >= thresholds.min_moves_for_notation_check
                and mangled > thresholds.max_mangled_move_ratio):
            return True
        broken = getattr(page_verdict, "broken_fonts", ())
        healthy = [f for f in getattr(page_verdict, "fonts", ()) if f not in broken]
        return bool(broken) and bool(healthy)

    # -- assembling the region list ---------------------------------------- #

    @staticmethod
    def _all_regions(layout: PageLayout) -> list[LayoutRegion]:
        """Body regions plus the furniture the layout analyser set aside.

        ``analyze_page`` builds regions from the reading order, and the reading
        order deliberately excludes running heads, folios and diagram labels —
        they must not enter the body text.  But "not in the body" is not "not
        on the page": the header carries the chapter title and the folio is
        what an index points at, so dropping them here would lose text the
        caller has no other way to reach.  They come back as one region per
        line, placed by height, and :attr:`PageOutcome.body_text` is what
        filters them out again.
        """
        body = list(layout.regions)
        claimed = {i for region in body for i in region.line_indices}
        extra = [
            LayoutRegion(kind=kind, box=layout.lines[i].box,
                         line_indices=(i,), column_index=-1)
            for i, kind in enumerate(layout.kinds)
            if i not in claimed and layout.lines[i].text.strip()
        ]
        body_top = min((r.box.y0 for r in body), default=0.0)
        leading = sorted((r for r in extra if r.box.y1 <= body_top),
                         key=lambda r: (r.box.y0, r.box.x0))
        trailing = sorted((r for r in extra if r.box.y1 > body_top),
                          key=lambda r: (r.box.y0, r.box.x0))
        ordered = leading + body + trailing
        return [
            LayoutRegion(kind=r.kind, box=r.box, line_indices=r.line_indices,
                         column_index=r.column_index, reading_order=n,
                         attached_to=r.attached_to, attached_kind=r.attached_kind)
            for n, r in enumerate(ordered)
        ]

    # -- one region -------------------------------------------------------- #

    def _run_region(self, task: PageTask, layout: PageLayout,
                    region: LayoutRegion, engine: Any,
                    page_verdict: Any) -> RegionOutcome:
        box = region.box
        verdict, own = self._verdict_for(task, region, layout, engine,
                                         page_verdict)
        crop, origin = self._crop(task, box)
        arbitration = self.arbiter.run(RegionTask(
            image=crop,
            region_kind=region.kind,
            lang=task.lang,
            pdf_page=task.pdf_page,
            clip=box,
            scale=task.scale,
            region_id=f"p{task.page_index}r{region.reading_order}",
            verdict=verdict,
        ))
        winner = arbitration.result.engine
        result = (arbitration.result
                  if winner in self._page_space_engines
                  else self._to_page_space(arbitration.result, origin))
        return RegionOutcome(region=region, outcome=arbitration,
                             result=result, own_verdict=own)

    def _verdict_for(self, task: PageTask, region: LayoutRegion,
                     layout: PageLayout, engine: Any,
                     page_verdict: Any) -> tuple[Any, bool]:
        """``(verdict, judged_on_its_own)`` for one region.

        A region with enough text of its own is judged on its own — that is
        the whole point of arbitrating per region, and it is what lets a bad
        table on a good page go to OCR by itself.  A shorter one inherits, for
        the reason in the module docstring.
        """
        if engine is None or page_verdict is None:
            return None, False
        chars = sum(len(layout.lines[i].text.strip())
                    for i in region.line_indices)
        if chars < self.config.min_chars_for_own_verdict:
            return page_verdict, False
        verdict = engine.assess(task.pdf_page, lang=task.lang, clip=region.box)
        return self._cap_by_page(verdict, page_verdict, engine), True

    @staticmethod
    def _cap_by_page(verdict: Any, page_verdict: Any, engine: Any) -> Any:
        """Damaged notation is a property of the *font*, so it is page-wide.

        Cutting a page up must not launder its verdict, and without this it
        does.  Measured on Gaprindashvili p202: the page reads 0.157 damaged
        moves over 83 and is flagged at 0.55, but its two regions come back at
        **0.98 each** — one because it has 11 moves and the twelve-move floor
        makes the check abstain, the other because 0.139 over 72 moves falls
        just under the 0.15 bar.  The page-level finding, which was correct,
        is destroyed by splitting.

        The fix is not a lower bar per region.  A region with few figurines
        shows less damage than the page, but its font is exactly as broken —
        so a region may not come out *more* trusted than the page it was cut
        from on a defect the page measured with more evidence.  Regions stay
        free to be judged *worse* than the page, which is what per-region
        arbitration is for.
        """
        thresholds = getattr(engine, "thresholds", None)
        if thresholds is None or not verdict.accepted:
            return verdict
        bar = thresholds.max_mangled_move_ratio
        judged = page_verdict.signals.get("moves_judged", 0.0)
        page_damaged = (
            judged >= thresholds.min_moves_for_notation_check
            and page_verdict.signals.get("mangled_move_ratio", 0.0) > bar)
        if not page_damaged:
            return verdict
        if not page_verdict.accepted:
            # Sol §SOL-1: the page was *rejected* for its notation.  A region
            # that judged enough moves of its own and passed has evidence the
            # page-wide finding does not override; a region with too few
            # moves to judge has none, and inherits the rejection — otherwise
            # cutting the page up launders the verdict (F5_REPORT_C2 §5.1).
            own = verdict.signals.get("moves_judged", 0.0)
            if own >= thresholds.min_moves_for_notation_check:
                return verdict
            return replace(
                verdict, accepted=False, confidence=0.0,
                reason=(f"{verdict.reason} Região com {own:.0f} lance(s), poucos "
                        f"para julgar a notação por si; a página foi reprovada "
                        f"por notação danificada e a fonte é a mesma."),
            )
        if verdict.confidence <= page_verdict.confidence:
            return verdict
        if verdict.signals.get("moves_judged", 0.0) == 0.0:
            # OCR_UI_ROADMAP passo 2: a region with no move-shaped token at
            # all — not a good one, not a mangled one — has nothing the broken
            # figurine font could have damaged.  Its prose is the layer's own,
            # read at 98,8 % on the controls (HANDOFF §4.1), and capping it
            # would hand it to the OCR for nothing.  A region with even one
            # move keeps the cap: that is the one that launders.
            return verdict
        return replace(
            verdict,
            confidence=page_verdict.confidence,
            notation_damaged=True,
            reason=(f"{verdict.reason} Confiança limitada à da página inteira "
                    f"({page_verdict.confidence:.2f}): os figurinos desta "
                    f"página estão danificados e a fonte é a mesma em todas as "
                    f"regiões, então esta região não pode valer mais que a "
                    f"página que a contém."),
        )

    # -- whole page -------------------------------------------------------- #

    def _whole_page(self, task: PageTask, started: float, notes: list[str],
                    layout: PageLayout | None = None) -> PageOutcome:
        """One arbitration over the entire page."""
        if layout is None:
            box = (self._page_box(task.pdf_page) if task.pdf_page is not None
                   else self._image_box(task.image))
            layout = PageLayout(box, (), (), (), (), (), 0.0, tuple(notes), {})
        region = LayoutRegion(kind=RegionKind.PAGE, box=layout.page_box,
                              line_indices=(), reading_order=0)
        arbitration = self.arbiter.run(RegionTask(
            image=task.image if task.has_image else None,
            region_kind=RegionKind.PAGE,
            lang=task.lang,
            pdf_page=task.pdf_page,
            clip=None,
            scale=task.scale,
            region_id=f"p{task.page_index}",
        ))
        outcome = RegionOutcome(region=region, outcome=arbitration,
                                result=arbitration.result, own_verdict=True)
        laid_out = self._scan_layout(task, outcome, notes)
        if laid_out is not None:
            return self._by_scan_layout(task, outcome, laid_out, started, notes)
        return PageOutcome(
            layout=layout,
            regions=(outcome,),
            notes=tuple(notes),
            total_duration_s=time.perf_counter() - started,
            whole_page=True,
            signals={"regions": 1, "escalated": int(arbitration.escalated),
                     "own_verdicts": 1,
                     "decision": (str(arbitration.decision.decision)
                                  if arbitration.decision else "n/a")},
        )

    # -- scan layout (passo B1) -------------------------------------------- #

    def _scan_layout(self, task: PageTask, whole: RegionOutcome,
                     notes: list[str]) -> ScanLayout | None:
        """Columns and regions from the whole-page reading, when it has them.

        Only for a reading of the raster: a text-layer result already came
        with a layout, and an empty or abstained one has no words to project.
        """
        if not self.config.scan.enabled or not task.has_image:
            return None
        result = whole.result
        if (result.is_empty or result.engine in self._page_space_engines
                or not whole.emits_text):
            return None
        raster_only = task.pdf_page is None
        page_box = (self._image_box(task.image) if raster_only
                    else self._page_box(task.pdf_page))
        try:
            laid_out = scan_layout(
                result, page_box=page_box, scale=1.0 if raster_only else task.scale,
                diagrams=() if raster_only else task.diagrams,
                page_index=task.page_index, config=self.config.scan,
                layout_config=self.config.layout, furniture=task.furniture)
        except Exception as exc:  # noqa: BLE001 - the layout is a refinement; the page is already read
            # Said in the page's notes and not only in the log (crítico
            # Codex, fase 2 ciclo 1): the page goes whole, and whoever reads
            # the outcome sees why it did.
            self.log.warning("leiaute em scan falhou na página %d: %s", task.page_index, exc)
            notes.append(f"leiaute em scan falhou (a página foi lida inteira): {type(exc).__name__}: {exc}")
            return None
        if laid_out is not None:
            notes.extend(laid_out.notes)
        return laid_out

    def _by_scan_layout(self, task: PageTask, whole: RegionOutcome, laid_out: ScanLayout,
                        started: float, notes: list[str]) -> PageOutcome:
        """The page as the regions the scan layout found.

        With ``scan_reread`` each region is arbitrated again on its own crop
        — Tesseract in PSM 4/6 segments a column far better than it segments
        a page, and a movetext region gets the movetext profile.  Without
        it, each region is the slice of the whole-page reading that falls in
        it: the words already read, in reading order.
        """
        layout = laid_out.layout
        regions = self._all_regions(layout)
        raster_only = task.pdf_page is None
        outcomes: list[RegionOutcome] = []
        if self.config.scan_reread:
            for region in regions:
                outcomes.append(self._reread_region(task, region, raster_only))
        else:
            for region in regions:
                lines = tuple(layout.lines[i].source for i in region.line_indices)
                result = replace(whole.result, lines=lines,
                                 meta={**dict(whole.result.meta), "scan_slice": True})
                # The other engines' whole-page readings are sliced to the
                # region too: a whole-page candidate that outranks the slice
                # would anchor the region with the *entire page* (measured
                # 2026-09-21 on the Dvoretsky: every region repeating the
                # page, CER 0 → 0,76).
                box_px = region.box if raster_only else region.box.scaled(task.scale)
                arbitration = replace(
                    whole.outcome, result=result,
                    candidates=tuple(self._slice(c, box_px) for c in whole.outcome.candidates))
                outcomes.append(RegionOutcome(region=region, outcome=arbitration,
                                              result=result, own_verdict=True))
        escalated = sum(1 for o in outcomes if o.escalated)
        return PageOutcome(
            layout=layout,
            regions=tuple(outcomes),
            notes=tuple(notes),
            total_duration_s=time.perf_counter() - started,
            whole_page=False,
            signals={
                "regions": len(outcomes),
                "escalated": escalated,
                "own_verdicts": len(outcomes),
                "page_verdict": "sem camada de texto: leiaute em scan",
                "page_verdict_accepted": False,
                "scan_layout": True,
                "scan_reread": self.config.scan_reread,
                **laid_out.signals,
            },
        )

    @staticmethod
    def _slice(result: OcrResult, box_px: BBox) -> OcrResult:
        """The part of a page-space reading that falls in ``box_px``, **by word**.

        By word and not by line: the other engines read the same page whole,
        and a line that PSM 3 fused across the gutter has its centre in one
        of the two columns — sliced by line it would carry the other column's
        words into this region and the fusion would see them as support.
        A line is kept whole when all its words fall inside, cut to the words
        that do when some do, and dropped when none does.
        """

        def inside(box: BBox) -> bool:
            return box_px.x0 <= box.cx <= box_px.x1 and box_px.y0 <= box.cy <= box_px.y1

        kept: list[OcrLine] = []
        cut = False
        for line in result.lines:
            words = tuple(w for w in line.words if inside(w.box))
            if len(words) == len(line.words):
                if words or inside(line.box):
                    kept.append(line)
                else:
                    cut = True
                continue
            cut = True
            if words:
                kept.append(replace(line, words=words, box=BBox.union_of([w.box for w in words])))
        if not cut:
            return result
        return replace(result, lines=tuple(kept), meta={**dict(result.meta), "scan_slice": True})

    def _reread_region(self, task: PageTask, region: LayoutRegion,
                       raster_only: bool) -> RegionOutcome:
        """The second pass over one region of a page with no text layer.

        Level 0 has nothing to read here (that is why the page went whole),
        so the pass is raster-only: no PDF page, no clip, no verdict.  The
        layout is in pixels for a raster-only task and in points for an
        image-only PDF page; :meth:`_crop` knows which.
        """
        crop, origin = self._crop(task, region.box)
        arbitration = self.arbiter.run(RegionTask(
            image=crop, region_kind=region.kind, lang=task.lang, pdf_page=None,
            clip=None, scale=task.scale,
            region_id=f"p{task.page_index}r{region.reading_order}"))
        return RegionOutcome(region=region, outcome=arbitration,
                             result=self._to_page_space(arbitration.result, origin),
                             own_verdict=True)

    # -- geometry ---------------------------------------------------------- #

    @staticmethod
    def _page_box(page: Any) -> BBox:
        rect = page.rect
        return BBox.from_edges(rect.x0, rect.y0, rect.x1, rect.y1)

    @staticmethod
    def _image_box(image: NDArray[np.uint8] | None) -> BBox:
        if image is None or getattr(image, "size", 0) == 0:
            return BBox(0.0, 0.0, 0.0, 0.0)
        h, w = image.shape[:2]
        return BBox(0.0, 0.0, float(w), float(h))

    def _crop(self, task: PageTask,
              box: BBox) -> tuple[NDArray[np.uint8] | None, tuple[float, float]]:
        """The raster under ``box`` (points), and the crop's page-pixel origin.

        Returns ``(None, (0, 0))`` when there is no raster, which is the normal
        case for a born-digital page: level 0 needs no pixels, and a level-1
        engine correctly refuses a region it was given no image for rather than
        inventing one.
        """
        if not task.has_image:
            return None, (0.0, 0.0)
        assert task.image is not None
        # A raster-only task lays out in pixels (the page box *is* the image
        # box, passo B1); a PDF page lays out in points.
        scaled = box if task.pdf_page is None else box.scaled(task.scale)
        pixels = scaled.clipped_to(self._image_box(task.image))
        x, y, w, h = pixels.to_int_tuple()
        if w <= 0 or h <= 0:
            return None, (0.0, 0.0)
        return task.image[y:y + h, x:x + w], (float(x), float(y))

    @staticmethod
    def _to_page_space(result: OcrResult,
                       origin: tuple[float, float]) -> OcrResult:
        """Translate a crop-relative result into full-page pixel space.

        Only ever called for an engine that was actually handed a crop.  A
        level-0 result is already in page space — it was given the clip and
        the scale — and :meth:`_run_region` filters it out by name before
        reaching here.  The origin is emphatically *not* zero for it, so
        translating would double the offset and put a region near the foot of
        the page off the page entirely.  That bug was real and is pinned by
        ``test_level_zero_boxes_survive_a_raster``.
        """
        dx, dy = origin
        if dx == 0.0 and dy == 0.0:
            return result
        # ``replace`` keeps the word's own type: the glyph reader's word
        # carries a ``margin`` the fusion reads, and rebuilding an ``OcrWord``
        # field by field used to drop it for every region off the origin
        # (OCR_UI_ROADMAP_C2 passo B7).
        lines = tuple(
            OcrLine(
                words=tuple(
                    replace(
                        w,
                        box=w.box.translated(dx, dy),
                        chars=tuple(
                            OcrChar(text=c.text,
                                    box=c.box.translated(dx, dy),
                                    confidence=c.confidence,
                                    inherited_confidence=c.inherited_confidence)
                            for c in w.chars),
                    )
                    for w in line.words),
                box=line.box.translated(dx, dy),
                baseline=line.baseline,
                block_index=line.block_index,
                paragraph_index=line.paragraph_index,
                line_index=line.line_index,
                kind=line.kind,
                font_size=line.font_size,
            )
            for line in result.lines
        )
        return OcrResult(
            engine=result.engine, lang=result.lang, lines=lines,
            region_kind=result.region_kind, duration_s=result.duration_s,
            warnings=result.warnings,
            meta={**dict(result.meta), "page_origin": (dx, dy)},
        )


def recognize_page(engines: Sequence[OcrEngine], task: PageTask,
                   config: PageConfig | None = None) -> PageOutcome:
    """One-shot convenience wrapper around :class:`PageRecognizer`."""
    return PageRecognizer(engines, config).run(task)
