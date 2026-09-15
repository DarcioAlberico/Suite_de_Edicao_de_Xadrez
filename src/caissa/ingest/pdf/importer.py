"""PDF to Document IR: the F2 pipeline, page by page, at constant memory.

Two passes over the pages, both streaming:

1. **Survey.**  Read every page's text once to learn what only the whole book
   can tell: which margin lines repeat (running heads and folios), the size
   most characters are set in (the body size), which fonts are bold by their
   ink, and the bare integers each page carries (for the printed folio).
   Nothing from this pass is kept per page except a few numbers.
2. **Build.**  Read each page again, judge its text layer, find its diagrams,
   lay it out, and feed its rows to a :class:`ParagraphBuilder` that closes
   paragraphs across page breaks.  Figures and diagrams are slotted into the
   flow after the last row above them in their column.  A page's text is
   dropped as soon as its rows are consumed.

Reading each page twice costs one extra ``get_text`` per page (5-30 ms) and is
what keeps a 500-page book from holding 500 pages of spans in memory.  The
F2 gate -- "memory stable over a full scan" -- is measured in
``tests/unit/ingest/test_gates.py`` by watching the process's working set
across the second pass, not by trusting this paragraph.

**The text layer is judged before it is believed** (F5's level 0).  A page
whose layer is rejected -- broken CMap, figurines destroyed beyond salvage --
goes to OCR, and a page with no text at all is a scan and goes the same way.
Since Sol §SOL-1 the OCR is on by default: the
:class:`~caissa.ingest.pdf.ocr_service.OcrService` renders only the pages
that need it, lays them out from whatever layer they have, runs the cascade
per region with the decision policy of §SOL-2 and the preprocessing
portfolio of §SOL-3, and answers with text, a review mark, or an abstention.
An abstained page (or region) is imported as an image with the reason in its
provenance; ``enable_ocr=False`` skips all of it for a fast import.  Nothing
here ever emits text the verdict called garbage.

**Diagrams are positions, not pictures** (SPEC 5.3).  The default finder is the
vector detector (F3-A): exact reads from chess-font glyphs, no model, about
two milliseconds a page.  A caller with the raster pipeline (F3 vias B and C,
F4) plugs it in as ``diagram_finder`` and gets the same IR shape.  Every
diagram carries its page rectangle, the caption the text placed next to it,
and -- when the caption says so -- the side to move, which is where the
trunk's ``0 of 3.244 labels with Black to move`` came from.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from caissa.core.chess.notation_tables import FIGURINE_BLACK, FIGURINE_WHITE, PieceType
from caissa.core.model import (
    Block,
    ConfidenceBand,
    Diagram,
    DiagramSource,
    Document,
    DocumentMetadata,
    Figure,
    FontWeight,
    Heading,
    ImageBlock,
    ImageInline,
    Inline,
    Measure,
    MetadataEntry,
    Orientation,
    Paragraph,
    ParagraphProps,
    ParagraphStyle,
    PieceGlyph,
    Provenance,
    RecognitionPath,
    RecognitionResult,
    Rect,
    Resource,
    ResourceKind,
    RunProps,
    SourceKind,
    StyleSheet,
    Text,
    VerticalAlign,
)
from caissa.core.model.document import Contributor, ContributorRole
from caissa.ingest.pdf.captions import (
    DiagramContext,
    bare_integers,
    page_contexts,
    running_page_number,
)
from caissa.ingest.pdf.document import PdfDocument
from caissa.ingest.pdf.geometry import PageFrame, RectT
from caissa.ingest.pdf.paragraphs import (
    BlockDraft,
    PageRows,
    ParagraphBuilder,
    ParagraphConfig,
    diagram_extents,
    finish_document,
    layout_page,
)
from caissa.ingest.pdf.textlayer import (
    FigurineMapper,
    ImagePlacement,
    PageText,
    TextSpan,
    extract_page_text,
    stroke_bold_fonts,
)
from caissa.ocr.engines.pdf_text_layer import (
    PdfTextLayerEngine,
    TextLayerThresholds,
    TextLayerVerdict,
)
from caissa.ocr.layout.analyze import LayoutLine, RunningFurnitureDetector
from caissa.ocr.types import BBox, RegionKind

__all__ = [
    "DiagramFinder",
    "DiagramHit",
    "ImportCanceled",
    "ImportReport",
    "ImportResult",
    "OcrProvider",
    "PageReport",
    "PdfImportOptions",
    "PdfImporter",
    "ReviewItem",
    "import_pdf",
    "vector_diagram_finder",
]

LOGGER = logging.getLogger("caissa.ingest.pdf.importer")

_EXTRACTOR: Final = "caissa.ingest.pdf"
_EXTRACTOR_VERSION: Final = "1.0"
_IMAGE_PLACEHOLDER: Final = "￼"
_EMPTY_BOARD: Final = "8/8/8/8/8/8/8/8 w - - 0 1"
_CONFIDENT: Final = 0.90
_DOUBTFUL: Final = 0.60

_PIECE_OF_GLYPH: Final[Mapping[str, PieceType]] = {
    **{glyph: piece for piece, glyph in FIGURINE_WHITE.items()},
    **{glyph: piece for piece, glyph in FIGURINE_BLACK.items()},
}


class ImportCanceled(RuntimeError):  # noqa: N818 - matches ExportCanceled next door
    """The import was stopped on request.  The partial document is discarded."""


# --------------------------------------------------------------------------- #
# Extension points
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DiagramHit:
    """A chess diagram located on a page, read or not.

    Attributes:
        box: Board rectangle in ``page.rect`` points.
        fen: Full FEN when the position was read; ``None`` when only located.
        confidence: Calibrated confidence in ``[0, 1]``; ``1.0`` for an exact
            vector read.
        path: Which route produced it.
        method: Free-form detail for the recognition record.
        orientation_white: Whether White is at the bottom.
    """

    box: RectT
    fen: str | None = None
    confidence: float = 0.0
    path: RecognitionPath = RecognitionPath.VECTOR
    method: str = ""
    orientation_white: bool = True
    #: OCR_UI_ROADMAP passo 10: an exact vector read whose text layer lacked
    #: some cells — ``(row, col)`` in lattice order, top row first — and the
    #: 8x8 area to render if a classifier is to fill them.  The exact path
    #: assumes a missing cell empty; on the Polgar (SkakNew) that assumption
    #: was wrong in 61 of 114 boards (every dark-square rook is dropped by
    #: the extractor), so the combined finder asks the classifier.
    holes: tuple[tuple[int, int], ...] = ()
    cells_box: RectT | None = None


#: ``(raw page, frame, page text) -> hits``.  Called with the document lock held.
DiagramFinder = Callable[[Any, PageFrame, PageText], Sequence[DiagramHit]]
#: ``(raw page, frame, verdict) -> page text`` for a page whose layer failed.
#: Called with the document lock held; returns ``None`` to decline the page.
OcrProvider = Callable[[Any, PageFrame, TextLayerVerdict], PageText | None]


def vector_diagram_finder(page: Any, frame: PageFrame, _text: PageText) -> list[DiagramHit]:
    """F3-A: read diagrams from chess-font glyphs and repeated vector drawings."""
    from caissa.vision.detect.vector_detect import detect_vector_boards

    hits: list[DiagramHit] = []
    try:
        boards = detect_vector_boards(page)
    except Exception as exc:  # noqa: BLE001 - a detector crash is a note, not a lost page
        LOGGER.warning("Detector vetorial falhou na página %d: %s", frame.index, exc)
        return hits
    for board in boards:
        x0, y0, x1, y1 = board.rect_pdf
        evidence = board.evidence
        holes = tuple(
            (r, c)
            for r, row in enumerate(getattr(evidence, "raw_rows", ()) or ())
            for c, ch in enumerate(row)
            if ch == "~"
        )
        cells = getattr(evidence, "cells_rect_pdf", None)
        hits.append(
            DiagramHit(
                box=(float(x0), float(y0), float(x1), float(y1)),
                fen=board.fen,
                confidence=float(board.confidence),
                path=RecognitionPath.VECTOR,
                method=str(board.method),
                orientation_white=bool(getattr(board.orientation, "white_at_bottom", True)),
                holes=holes,
                cells_box=tuple(float(v) for v in cells) if cells else None,
            )
        )
    return hits


# --------------------------------------------------------------------------- #
# Options and reports
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class PdfImportOptions:
    """Everything an import can be tuned by."""

    #: Zero-based page indices to import; ``None`` for the whole book.
    pages: Sequence[int] | None = None
    #: Language hint for the text-layer verdict (ISO 639, e.g. ``"por"``).
    lang: str = ""
    #: Locate (and, when possible, read) chess diagrams.
    detect_diagrams: bool = True
    diagram_finder: DiagramFinder | None = None
    #: OCR_UI_ROADMAP passo 2: a page whose text layer was *kept* for its
    #: prose while its notation is mangled (``TextLayerVerdict.notation_damaged``,
    #: the 0,55 verdict of F5-C2) goes to the OCR service anyway.  There the
    #: layer is level 0 per region, below the arbiter's bar, and the engines
    #: compete; the fusion keeps the prose the layer got right and takes the
    #: moves from whoever read them.  Before this the service was never
    #: called on exactly the books it was built for (16 of the 33 with a
    #: layer; ROTULAGEM.md §7c).  ``False`` copies the layer as before.
    ocr_contests_text_layer: bool = True
    #: OCR_UI_ROADMAP passo 3: keep the book's figurine cipher — the Latin
    #: symbols the OCR uses for the figurines, proved piece by piece by the
    #: legality replay of the blocks that have a position — and apply the
    #: proven rows to the blocks that have none (98 % of them).  The table is
    #: stored with the book's other models, keyed by the PDF's content hash
    #: (:mod:`caissa.ocr.notation.book_cipher`).  ``False`` neither reads nor
    #: writes it.
    book_cipher: bool = True
    #: OCR_UI_ROADMAP passo 11: a ``Movetext`` paragraph that follows a read
    #: diagram is replayed from its position and, when the main line chains,
    #: becomes a :class:`GameScore` with provenance per move
    #: (:mod:`caissa.ingest.pdf.games`).  ``False`` keeps every paragraph.
    games: bool = True
    #: Run OCR on pages whose text layer is absent or rejected (Sol §SOL-1).
    #: Off, such pages import as images -- the fast path for a book whose
    #: text will be read another day.
    enable_ocr: bool = True
    #: A custom provider.  ``None`` with ``enable_ocr`` builds the default
    #: :class:`~caissa.ingest.pdf.ocr_service.OcrService` lazily, on the
    #: first page that needs it.
    ocr: OcrProvider | None = None
    #: Use the Tesseract model fine-tuned for *this* book, when the labelling
    #: window trained and registered one for the PDF's content hash
    #: (:mod:`caissa.ocr.training.books`).  The model is a second opinion
    #: on notation regions, never the anchor; the report notes which one
    #: was used.  Off, or with no entry, the default service reads as always.
    book_models: bool = True
    #: Keep an image of every OCR region that was abstained, placed where the
    #: region was, so the reader sees what the text could not say.
    keep_abstained_regions: bool = True
    #: Directory that receives extracted images and diagram crops as PNG.
    #: ``None`` keeps the IR free of files: resources are declared with their
    #: size and provenance but no bytes.
    asset_dir: Path | None = None
    asset_dpi: int = 200
    detect_bold_by_ink: bool = True
    figurine_fonts: tuple[str, ...] = ()
    #: Attach a full-page ``ImageBlock`` for every scanned page.  Off, a
    #: scanned book with no OCR imports as metadata plus page breaks -- which
    #: is honest, but leaves the reader nothing to look at.
    keep_scanned_pages: bool = True
    thresholds: TextLayerThresholds | None = None
    paragraphs: ParagraphConfig = field(default_factory=ParagraphConfig)
    progress: Callable[[int, int], None] | None = None
    should_cancel: Callable[[], bool] | None = None


@dataclass(slots=True)
class PageReport:
    """What happened to one page."""

    index: int
    source: str
    verdict: str = ""
    confidence: float = 0.0
    lines: int = 0
    rows: int = 0
    columns: int = 0
    diagrams: int = 0
    diagrams_read: int = 0
    figures: int = 0
    inline_images: int = 0
    duration_ms: float = 0.0
    #: Sol §SOL-10: what the OCR did on this page, when it ran.
    ocr_engine: str = ""
    ocr_dpi: float = 0.0
    ocr_decisions: dict[str, int] = field(default_factory=dict)
    ocr_regions: int = 0
    ocr_review: int = 0
    ocr_abstained: int = 0
    ocr_variants: tuple[str, ...] = ()
    ocr_duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """A region the OCR could not settle -- clickable in the import report.

    Attributes:
        page_index: Zero-based page.
        rect: Region in ``page.rect`` points.
        kind: Layout kind of the region.
        decision: ``review`` or ``abstained``.
        reasons: The decision's reasons, in Portuguese.
        text: The best reading (empty for a region with none).
        engine: Engine of the best reading.
        score: Arbiter score of the best reading.
        alternatives: Other candidates' text, by ``variant/engine``.
    """

    page_index: int
    rect: RectT
    kind: str
    decision: str
    reasons: tuple[str, ...]
    text: str = ""
    engine: str = ""
    score: float = 0.0
    alternatives: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True)
class ImportReport:
    """Everything measured during an import, for the UI and for the record."""

    pages: list[PageReport] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    body_size: float = 0.0
    bold_fonts: tuple[str, ...] = ()
    figurine_fonts: tuple[str, ...] = ()
    figurines_mapped: int = 0
    furniture_patterns: int = 0
    notes: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    #: Sol §SOL-10: every region the OCR sent to review or abstained on.
    review_items: list[ReviewItem] = field(default_factory=list)
    #: Sol §SOL-10: the OCR's full trace per page (decisions, candidates,
    #: variants, fusion, legality), JSON-ready, for the review panel and for
    #: selective reprocessing.  Written to ``asset_dir/ocr_trace.json``.
    ocr_traces: dict[int, dict[str, Any]] = field(default_factory=dict)
    #: Sol §SOL-7: the prose language and the notation convention detected
    #: (or given), with the detector's reason.
    prose_lang: str = ""
    prose_lang_reason: str = ""
    notation_lang: str = ""
    notation_lang_reason: str = ""

    @property
    def pages_by_source(self) -> dict[str, int]:
        return dict(Counter(p.source for p in self.pages))

    def describe_pt(self) -> str:
        c = self.counters
        by = self.pages_by_source
        parts = [
            f"{len(self.pages)} página(s) em {self.duration_s:.1f} s",
            f"corpo em {self.body_size:.1f} pt",
            f"{c.get('paragraphs', 0)} parágrafos, {c.get('headings', 0)} títulos, "
            f"{c.get('captions', 0)} legendas, {c.get('footnotes', 0)} notas, "
            f"{c.get('movetext', 0)} blocos de lances",
            f"{c.get('diagrams', 0)} diagramas ({c.get('diagrams_read', 0)} lidos, "
            f"{c.get('side_to_move', 0)} com lado a jogar)",
            f"{c.get('figures', 0)} figuras, {c.get('inline_images', 0)} imagens em linha",
            "origem: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items())),
        ]
        if self.review_items:
            review = sum(1 for i in self.review_items if i.decision == "review")
            parts.append(
                f"OCR: {review} região(ões) para revisão, "
                f"{len(self.review_items) - review} abstida(s)")
        return "; ".join(parts)


@dataclass(slots=True)
class ImportResult:
    document: Document
    report: ImportReport


# --------------------------------------------------------------------------- #
# Flow entries
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _FigureEntry:
    page_index: int
    image: ImagePlacement
    full_page: bool = False
    #: Set for an abstained OCR region kept as an image: the reason, for the
    #: provenance note and the resource description.
    note: str = ""


@dataclass(slots=True)
class _DiagramEntry:
    page_index: int
    hit: DiagramHit
    context: DiagramContext


@dataclass(slots=True)
class _ScanEntry:
    page_index: int
    reason: str
    image: ImagePlacement | None


_Entry = BlockDraft | _FigureEntry | _DiagramEntry | _ScanEntry


# --------------------------------------------------------------------------- #
# The importer
# --------------------------------------------------------------------------- #


class PdfImporter:
    """Runs the two passes and builds the IR.  One instance per import."""

    def __init__(self, document: PdfDocument, options: PdfImportOptions | None = None) -> None:
        self.document = document
        self.options = options or PdfImportOptions()
        self.report = ImportReport()
        self._engine = PdfTextLayerEngine(self.options.thresholds)
        self._mapper = FigurineMapper(self.options.figurine_fonts)
        self._bold_fonts: frozenset[str] = frozenset()
        self._furniture = RunningFurnitureDetector(self.options.paragraphs.layout)
        self._integers: dict[int, list[tuple[int, RectT]]] = {}
        self._size_weights: Counter[float] = Counter()
        self._resources: list[Resource] = []
        self._asset_counter = 0
        self._page_reports: dict[int, PageReport] = {}
        self._ocr_service: Any = None
        self._ocr_unavailable = False
        #: The language the verdicts and the OCR use: the option, or what the
        #: survey (or the first OCR page) detected.
        self._lang: str = self.options.lang
        self._language_samples: list[str] = []
        self._movetext_samples: list[str] = []
        self._pending_ocr: tuple[int, dict[str, Any]] | None = None
        #: Abstained OCR regions of the page being built, as figure entries.
        self._abstained_figures: list[_FigureEntry] = []

    # -- driver ------------------------------------------------------------ #

    @property
    def page_indices(self) -> list[int]:
        wanted = self.options.pages
        if wanted is None:
            return list(range(self.document.page_count))
        return [self.document.check_index(i) for i in wanted]

    def run(self) -> ImportResult:
        started = time.perf_counter()
        indices = self.page_indices
        self._survey(indices)
        entries = self._build(indices)
        blocks = [e for e in entries if isinstance(e, BlockDraft)]
        figure_pages = Counter(
            e.page_index for e in entries if isinstance(e, (_FigureEntry, _DiagramEntry))
        )
        counters = finish_document(
            blocks,
            body_size=self.report.body_size,
            outline=self.document.outline,
            figure_pages=figure_pages,
            config=self.options.paragraphs,
        )
        counters["diagrams"] = sum(1 for e in entries if isinstance(e, _DiagramEntry))
        counters["diagrams_read"] = sum(
            1 for e in entries if isinstance(e, _DiagramEntry) and e.hit.fen
        )
        counters["side_to_move"] = sum(
            1
            for e in entries
            if isinstance(e, _DiagramEntry) and e.context.side_to_move is not None
        )
        # OCR_UI_ROADMAP passo 7: how many diagrams got their side from each
        # origin (``default`` = nothing on the page said whose turn it is).
        for e in entries:
            if isinstance(e, _DiagramEntry):
                origin = (
                    e.context.side_to_move_origin if e.context.side_to_move is not None
                    else "default"
                )
                key = f"side_to_move_origin:{origin}"
                counters[key] = counters.get(key, 0) + 1
        # OCR_UI_ROADMAP passo 10: boards in a chess font outside the catalog,
        # read from pixels with a capped confidence — counted apart so the
        # report says how many positions are inferred rather than decoded.
        counters["diagrams_vector_inferred"] = sum(
            1 for e in entries
            if isinstance(e, _DiagramEntry) and e.hit.path is RecognitionPath.VECTOR_INFERRED
        )
        counters["figures"] = sum(1 for e in entries if isinstance(e, _FigureEntry))
        counters["scanned_pages"] = sum(1 for e in entries if isinstance(e, _ScanEntry))
        counters["inline_images"] = sum(len(b.inline_images) for b in blocks)
        # OCR_UI_ROADMAP passo 2: pages whose kept layer was contested by the OCR.
        counters["contested_pages"] = sum(
            1 for r in self.report.pages if r.source == "text-layer+ocr")
        self.report.counters = counters
        self.report.figurines_mapped = self._mapper.count
        self.report.figurine_fonts = tuple(sorted(self._mapper.seen_fonts))
        document = self._to_ir(entries)
        self._save_book_cipher()
        self.report.duration_s = time.perf_counter() - started
        if self.options.asset_dir is not None and self.report.ocr_traces:
            import json

            target = Path(self.options.asset_dir) / "ocr_trace.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(
                {"pages": self.report.ocr_traces,
                 "review_items": [_review_item_dict(i) for i in self.report.review_items],
                 "prose_lang": self.report.prose_lang,
                 "notation_lang": self.report.notation_lang},
                ensure_ascii=False, indent=1), encoding="utf-8")
        return ImportResult(document=document, report=self.report)

    def _check_cancel(self) -> None:
        if self.options.should_cancel is not None and self.options.should_cancel():
            raise ImportCanceled("Importação cancelada. O documento parcial foi descartado.")

    def _progress(self, done: int, total: int) -> None:
        if self.options.progress is not None:
            self.options.progress(done, total)

    # -- pass 1 ------------------------------------------------------------ #

    def _survey(self, indices: Sequence[int]) -> None:
        total = len(indices)
        for n, index in enumerate(indices):
            self._check_cancel()
            frame = self.document.frame(index)
            with self.document.locked() as doc:
                text = extract_page_text(
                    doc[index], frame, mapper=self._mapper, with_images=False, with_rules=False
                )
            page_box = BBox(0.0, 0.0, frame.width, frame.height)
            lines = [
                LayoutLine(
                    box=BBox.from_edges(*line.box),
                    text=line.text,
                    font_size=line.size or (line.box[3] - line.box[1]),
                )
                for line in text.lines
                if not line.is_diagram
            ]
            self._furniture.observe(lines, page_box)
            for line in lines:
                size = round(line.font_size, 1)
                if size > 0:
                    self._size_weights[size] += max(1, line.char_count)
            self._integers[index] = bare_integers(text)
            if len(self._language_samples) < 40 and text.char_count > 200:
                self._language_samples.append(text.text)
            if n % 20 == 0:
                self._progress(n, 2 * total)
        self.report.furniture_patterns = len(self._furniture.finalize())
        self._detect_languages()
        if self._size_weights:
            self.report.body_size = max(self._size_weights.items(), key=lambda kv: (kv[1], -kv[0]))[
                0
            ]
        # Figurine counters from the survey pass would double the build pass's.
        self._mapper.count = 0
        self._mapper.informator_count = 0
        if self.options.detect_bold_by_ink and total >= 2:  # noqa: PLR2004 - needs two faces
            self._bold_fonts = stroke_bold_fonts(self.document, list(indices))
            self.report.bold_fonts = tuple(sorted(self._bold_fonts))

    def _detect_languages(self) -> None:
        """Sol §SOL-7: the prose language from the survey sample, the
        notation convention from the moves seen so far."""
        from caissa.ocr.language import detect_notation_convention, document_language

        if self._language_samples:
            guess = document_language(self._language_samples, hint=self.options.lang)
            if self.options.lang:
                self.report.prose_lang = self.options.lang
                self.report.prose_lang_reason = "idioma informado na importação"
            elif not guess.abstained:
                self._lang = guess.lang
                self.report.prose_lang = guess.lang
                self.report.prose_lang_reason = guess.reason_pt
            else:
                self.report.prose_lang_reason = guess.reason_pt
            notation = detect_notation_convention(
                "\n".join(self._language_samples)[:100_000], prose_lang=self._lang)
            if not notation.abstained:
                self.report.notation_lang = notation.locale or ""
            self.report.notation_lang_reason = notation.reason_pt
        elif self.options.lang:
            self.report.prose_lang = self.options.lang
            self.report.prose_lang_reason = "idioma informado na importação"

    # -- pass 2 ------------------------------------------------------------ #

    def _build(self, indices: Sequence[int]) -> list[_Entry]:
        entries: list[_Entry] = []
        builder = ParagraphBuilder(self.options.paragraphs, self.report.body_size)
        total = len(indices)
        finder = self.options.diagram_finder or (
            vector_diagram_finder if self.options.detect_diagrams else None
        )
        for n, index in enumerate(indices):
            self._check_cancel()
            started = time.perf_counter()
            page_report, page_entries = self._build_page(index, builder, finder)
            page_report.duration_ms = (time.perf_counter() - started) * 1000.0
            self.report.pages.append(page_report)
            self._page_reports[index] = page_report
            entries.extend(page_entries)
            if n % 10 == 0:
                self._progress(total + n, 2 * total)
        tail = builder.flush()
        if tail is not None:
            entries.append(tail)
        self._progress(2 * total, 2 * total)
        return entries

    def _build_page(
        self, index: int, builder: ParagraphBuilder, finder: DiagramFinder | None
    ) -> tuple[PageReport, list[_Entry]]:
        frame = self.document.frame(index)
        with self.document.locked() as doc:
            page = doc[index]
            text = extract_page_text(page, frame, mapper=self._mapper, bold_fonts=self._bold_fonts)
            verdict = (
                self._engine.assess(page, lang=self._lang) if not text.is_empty else None
            )
            # Diagrams first: the OCR's legality replay (Sol §SOL-8) starts
            # from the position a solution follows, so the boards must be
            # known before the text is read.
            hits: list[DiagramHit] = list(finder(page, frame, text)) if finder is not None else []
            self._share_page_context(index, text, hits)
            source, reason, confidence, text = self._decide_source(page, frame, text, verdict)
        report = PageReport(index=index, source=source, verdict=reason, confidence=confidence)
        pending = self._pending_ocr
        if pending is not None and pending[0] == index:
            for key, value in pending[1].items():
                setattr(report, key, value)
            self._pending_ocr = None
        report.lines = len(text.lines)
        report.diagrams = len(hits)
        report.diagrams_read = sum(1 for h in hits if h.fen)

        entries: list[_Entry] = []
        if source == "blank":
            done = builder.break_flow()
            return report, [done] if done is not None else []
        if source in ("image-only", "rejected"):
            # Nothing readable: the page is a picture.  Keep it as one when
            # asked, with the reason where the reader will see it.
            full = next(
                (
                    im
                    for im in text.images
                    if im.area >= self.options.paragraphs.full_page_share * frame.area
                ),
                None,
            )
            done = builder.break_flow()
            if done is not None:
                entries.append(done)
            if self.options.keep_scanned_pages:
                entries.append(_ScanEntry(page_index=index, reason=reason, image=full))
            contexts, _ = self._contexts(index, text, [h.box for h in hits])
            for hit, context in zip(hits, contexts, strict=True):
                entries.append(_DiagramEntry(page_index=index, hit=hit, context=context))
            return report, entries

        extents = diagram_extents(text, [h.box for h in hits], self.options.paragraphs)
        contexts, consumed = self._contexts(index, text, extents)
        rows = layout_page(
            text,
            diagrams=extents,
            consumed=consumed,
            furniture=self._furniture,
            config=self.options.paragraphs,
            body_size_hint=self.report.body_size,
        )
        report.rows = len(rows.rows)
        report.columns = rows.layout.column_count
        report.figures = len(rows.figures) + len(rows.full_page_images)
        report.inline_images = sum(len(r.inline_images) for r in rows.rows)

        slots = self._slot_entries(rows, hits, contexts, index)
        for figure in self._abstained_figures:
            slot = _slot_for_box(rows, figure.image.box)
            slots.setdefault(slot, []).append(figure)
        self._abstained_figures = []
        entries.extend(self._feed(builder, rows, slots))
        return report, entries

    def _decide_source(  # noqa: PLR0911 - one return per outcome reads better than a table
        self, page: Any, frame: PageFrame, text: PageText, verdict: TextLayerVerdict | None
    ) -> tuple[str, str, float, PageText]:
        """Which text the page contributes, and why."""
        if verdict is None or verdict.is_image_only:
            reason = verdict.reason if verdict is not None else "a página não contém texto."
            has_picture = any(
                im.area >= self.options.paragraphs.full_page_share * frame.area
                for im in text.images
            )
            if not text.is_empty and not has_picture:
                # Too short for the lexical tests -- a title page, a part
                # divider -- but there is no picture for it to be a scan of.
                # Level 0 calls this "a scan" because it judges pages, not
                # books; here the words are kept, at the confidence the
                # verdict gives text it could not read.
                return (
                    "text-layer",
                    f"{reason} Sem imagem de página, o pouco texto foi mantido.",
                    self._engine.thresholds.unjudged_script_confidence,
                    text,
                )
            ocr = self._try_ocr(page, frame, verdict)
            if ocr is not None:
                return "ocr", reason, ocr[1], ocr[0]
            if text.is_empty and not text.images:
                return "blank", reason, 0.0, text
            return "image-only", reason, 0.0, text
        if not verdict.accepted:
            ocr = self._try_ocr(page, frame, verdict)
            if ocr is not None:
                return "ocr", verdict.reason, ocr[1], ocr[0]
            return "rejected", verdict.describe_pt(), 0.0, text
        if verdict.notation_damaged and self.options.ocr_contests_text_layer:
            ocr = self._try_ocr(page, frame, verdict)
            if ocr is not None:
                return "text-layer+ocr", verdict.reason, ocr[1], ocr[0]
        return "text-layer", verdict.reason, verdict.confidence, text

    def _ocr_provider(self) -> OcrProvider | None:
        """The configured provider, or the default service built once."""
        if self.options.ocr is not None:
            return self.options.ocr
        if not self.options.enable_ocr or self._ocr_unavailable:
            return None
        if self._ocr_service is None:
            from caissa.ingest.pdf.ocr_service import OcrService

            service = OcrService(lang=self._lang, config=self._book_ocr_config())
            service.book_cipher = self._load_book_cipher()
            if not service.available:
                self._ocr_unavailable = True
                self.report.notes.append(
                    "OCR indisponível: nenhum motor de rasterização instalado; páginas "
                    "sem camada de texto ficam como imagem.")
                return None
            self._ocr_service = service
        return self._ocr_service

    def _load_book_cipher(self) -> Any:
        """The book's cipher table, from disk or fresh; ``None`` when off."""
        if not self.options.book_cipher:
            return None
        from caissa.ocr.notation.book_cipher import BookCipher

        path = self._book_cipher_path()
        fingerprint = self.document.content_hash if self.document.path is not None else None
        table = BookCipher.load(path, fingerprint=fingerprint) if path is not None else None
        if table is None:
            table = BookCipher(fingerprint=fingerprint or "",
                               document=self.document.path.stem if self.document.path else "")
        elif table.entries:
            self.report.notes.append(table.describe_pt() + f" (lida de {path})")
        return table

    def _book_cipher_path(self) -> Path | None:
        if self.document.path is None:
            return None
        from caissa.ocr.notation.book_cipher import CIPHER_FILE
        from caissa.ocr.training.books import book_dir, models_root

        return book_dir(models_root(), self.document.path.stem) / CIPHER_FILE

    def _save_book_cipher(self) -> None:
        service = self._ocr_service
        table = getattr(service, "book_cipher", None) if service is not None else None
        if table is None or not table.dirty:
            return
        path = self._book_cipher_path()
        if path is None:
            return
        try:
            table.save(path)
        except OSError as exc:
            self.report.notes.append(f"cifra do livro não gravada: {exc}")
            return
        self.report.notes.append(table.describe_pt() + f" (gravada em {path})")
        self.report.counters["cipher_observations"] = table.observations
        self.report.counters["cipher_proven"] = len(table.proven())

    def _book_ocr_config(self) -> Any:
        """The service config, pointed at this book's fine-tune when it has one."""
        from caissa.ingest.pdf.ocr_service import OcrServiceConfig

        config = OcrServiceConfig()
        if not self.options.book_models or self.document.path is None:
            return config
        try:
            from caissa.ocr.training.books import BookRegistry

            registry = BookRegistry.default()
            # Hashing the file costs ~0,3 s per 100 MB; skip it with no entries.
            book = registry.lookup(self.document.content_hash) if registry.books else None
        except Exception as exc:  # noqa: BLE001 - a broken registry must not stop an import
            self.report.notes.append(f"registro de modelos por livro ilegível: {exc}")
            return config
        if book is not None:
            config.figurine_tessdata = book.tessdata_dir
            self.report.notes.append(book.describe())
        return config

    def _try_ocr(
        self, page: Any, frame: PageFrame, verdict: TextLayerVerdict | None
    ) -> tuple[PageText, float] | None:
        provider = self._ocr_provider()
        if provider is None:
            return None
        stub = verdict or TextLayerVerdict(False, "a página não contém texto.", 0.0, {}, (), True)
        started = time.perf_counter()
        try:
            result = provider(page, frame, stub)
        except Exception as exc:  # noqa: BLE001 - OCR failing must not lose the book
            self.report.notes.append(f"OCR falhou na página {frame.index}: {exc}")
            return None
        self._record_ocr(frame, provider, (time.perf_counter() - started) * 1000.0)
        if result is None or result.is_empty:
            return None
        self._adapt_language(result)
        # Sol §SOL-10: the page number is a summary, not a cap.  Each block
        # keeps its own spans' confidence; the worst line of the page must not
        # drag every other block down with it.
        weights = [(line.confidence, max(1, len(line.text.strip()))) for line in result.lines]
        total = sum(w for _, w in weights)
        confidence = sum(c * w for c, w in weights) / total if total else 0.0
        return result, confidence

    def _share_page_context(self, index: int, text: PageText, hits: Sequence[DiagramHit]) -> None:
        """Hand the OCR service the page's diagrams and their captions' side."""
        service = self._ocr_service
        if service is None or not hasattr(service, "page_context"):
            return
        from caissa.ingest.pdf.ocr_service import DiagramRef, PageContext

        contexts, _ = self._contexts(index, text, [h.box for h in hits]) if hits else ([], [])
        refs = []
        for hit, context in zip(hits, contexts, strict=False):
            trusted = hit.fen is not None and (
                (hit.path is RecognitionPath.VECTOR and not hit.holes)
                or hit.confidence >= _CONFIDENT)
            side = None
            if context is not None and context.side_to_move is not None:
                side = "w" if context.side_to_move else "b"
            refs.append(DiagramRef(box=hit.box, fen=hit.fen, trusted=trusted, side_to_move=side))
        service.page_context = PageContext(
            diagrams=tuple(refs), notation_locale=self.report.notation_lang or None)

    def _adapt_language(self, result: PageText) -> None:
        """A scanned book has no layer to survey: learn the language from the
        first pages the OCR reads and hand it to the service for the rest.
        """
        if self.options.lang or self.report.prose_lang:
            return
        from caissa.ocr.language import detect_prose_language

        self._language_samples.append(result.text)
        guess = detect_prose_language("\n".join(self._language_samples))
        if guess.abstained:
            return
        self._lang = guess.lang
        self.report.prose_lang = guess.lang
        self.report.prose_lang_reason = guess.reason_pt + " (detectado no OCR)"
        if self._ocr_service is not None:
            self._ocr_service.lang = guess.lang
        self.report.notes.append(f"Idioma da prosa detectado pelo OCR: {guess.lang}.")

    def _record_ocr(self, frame: PageFrame, provider: Any, elapsed_ms: float) -> None:
        """Copy the service's trace into the page report and the review list."""
        recognition = getattr(provider, "last", None)
        if recognition is None or getattr(recognition, "page_index", -1) != frame.index:
            return
        report = self._page_reports.get(frame.index)
        pending: dict[str, Any] = {
            "ocr_engine": recognition.engine,
            "ocr_dpi": float(recognition.dpi),
            "ocr_decisions": dict(recognition.decision_counts),
            "ocr_regions": len(recognition.regions),
            "ocr_review": len(recognition.review_regions),
            "ocr_abstained": len(recognition.abstained_regions),
            "ocr_variants": tuple(recognition.portfolio.names[1:]) if recognition.portfolio else (),
            "ocr_duration_ms": elapsed_ms,
        }
        self._pending_ocr = (frame.index, pending)
        if report is not None:
            for key, value in pending.items():
                setattr(report, key, value)
        try:
            self.report.ocr_traces[frame.index] = recognition.trace()
        except Exception as exc:  # noqa: BLE001 - a trace that cannot be serialised is a note
            self.report.notes.append(f"traço do OCR da página {frame.index} não registrado: {exc}")
        for region in recognition.regions:
            decision = region.decision.decision
            if decision.value == "accepted":
                continue
            rect = frame.pixels_to_page(
                (region.box_px.x0, region.box_px.y0, region.box_px.x1, region.box_px.y1),
                recognition.dpi)
            self.report.review_items.append(ReviewItem(
                page_index=frame.index, rect=rect, kind=str(region.kind),
                decision=decision.value, reasons=tuple(region.decision.reasons_pt),
                text=region.text, engine=region.engine, score=float(region.score),
                alternatives=tuple(
                    (f"{c.variant}/{c.engine}", c.result.text) for c in region.candidates
                    if c.result.text.strip() and c.result.text != region.text),
            ))
            if decision.value == "abstained" and self.options.keep_abstained_regions:
                width = max(1, int(region.box_px.w))
                height = max(1, int(region.box_px.h))
                self._abstained_figures.append(_FigureEntry(
                    page_index=frame.index,
                    image=ImagePlacement(box=rect, width=width, height=height),
                    note="OCR abstido: " + " ".join(region.decision.reasons_pt),
                ))

    def _contexts(
        self, index: int, text: PageText, boxes: Sequence[RectT]
    ) -> tuple[list[DiagramContext], list[RectT]]:
        if not boxes:
            return [], []
        frame = self.document.frame(index)
        neighbours = {
            delta: self._integers[index + delta]
            for delta in (1, -1, 2, -2)
            if index + delta in self._integers
        }
        folio = running_page_number(self._integers.get(index, []), neighbours, frame.height)
        return page_contexts(text, boxes, page_number=folio)

    @staticmethod
    def _slot_entries(
        rows: PageRows,
        hits: Sequence[DiagramHit],
        contexts: Sequence[DiagramContext],
        index: int,
    ) -> dict[int, list[_Entry]]:
        """Where each figure and diagram enters the flow.

        After the last row above it in its column (PDFimport ``_figure_slot``).
        Key ``-1`` means before the first row.
        """
        slots: dict[int, list[_Entry]] = {}

        def slot_for(box: RectT) -> int:
            return _slot_for_box(rows, box)

        for image in rows.full_page_images:
            slots.setdefault(-1, []).append(_FigureEntry(index, image, full_page=True))
        for image in rows.figures:
            slots.setdefault(slot_for(image.box), []).append(_FigureEntry(index, image))
        for hit, context in zip(hits, contexts, strict=True):
            slots.setdefault(slot_for(hit.box), []).append(_DiagramEntry(index, hit, context))
        for items in slots.values():
            _sort_like_a_reader(items)
        return slots

    @staticmethod
    def _feed(
        builder: ParagraphBuilder, rows: PageRows, slots: Mapping[int, list[_Entry]]
    ) -> list[_Entry]:
        """Interleave rows and slotted entries, closing paragraphs at each entry."""
        out: list[_Entry] = []

        def emit(items: Sequence[_Entry]) -> None:
            done = builder.break_flow()
            if done is not None:
                out.append(done)
            out.extend(items)

        if -1 in slots:
            emit(slots[-1])
        # Feed rows one at a time so an entry can land between two rows.
        for r, row in enumerate(rows.rows):
            single = PageRows(
                page_index=rows.page_index,
                rows=[row],
                layout=rows.layout,
                figures=rows.figures,
                full_page_images=rows.full_page_images,
                diagrams=rows.diagrams,
                mean_row_height=rows.mean_row_height,
                body_size=rows.body_size,
                measures=rows.measures,
                column_lefts=rows.column_lefts,
                column_rights=rows.column_rights,
            )
            out.extend(builder.feed(single))
            if r in slots:
                emit(slots[r])
        return out

    # -- IR ---------------------------------------------------------------- #

    def _to_ir(self, entries: Sequence[_Entry]) -> Document:
        body: list[Block] = []
        for entry in entries:
            if isinstance(entry, BlockDraft):
                node = self._block_node(entry)
                if node is not None:
                    body.append(node)
            elif isinstance(entry, _DiagramEntry):
                body.append(self._diagram_node(entry))
            elif isinstance(entry, _FigureEntry):
                node = self._figure_node(entry)
                if node is not None:
                    body.append(node)
            else:
                node = self._scan_node(entry)
                if node is not None:
                    body.append(node)
        if self.options.games:
            from caissa.ingest.pdf.games import GamesReport, attach_games

            games = GamesReport()
            body = attach_games(body, notation_lang=self.report.notation_lang, report=games)
            for key, value in games.counters().items():
                self.report.counters[key] = self.report.counters.get(key, 0) + value
        return Document(
            metadata=self._metadata(),
            styles=_stylesheet(self.report.body_size),
            resources=tuple(self._resources),
            body=tuple(body),
        )

    def _metadata(self) -> DocumentMetadata:
        meta = self.document.metadata
        contributors = (
            (Contributor(name=meta.author, role=ContributorRole.AUTHOR),) if meta.author else ()
        )
        custom: list[MetadataEntry] = []
        if meta.title_from_filename and self.document.path is not None:
            # Title and author were guessed from the file name: keep the raw
            # stem so the guess can be checked.
            custom.append(
                MetadataEntry(name="filename", value=self.document.path.stem, scheme="caissa")
            )
        for name, value in (
            ("creator", meta.creator),
            ("producer", meta.producer),
            ("creationDate", meta.creation_date),
            ("modDate", meta.modification_date),
            ("keywords", meta.keywords),
        ):
            if value:
                custom.append(MetadataEntry(name=name, value=value, scheme="pdf"))
        return DocumentMetadata(
            title=meta.title,
            contributors=contributors,
            description=meta.subject or None,
            subjects=tuple(k.strip() for k in meta.keywords.split(",") if k.strip()),
            source=str(self.document.path) if self.document.path else None,
            page_count=self.document.page_count,
            modified=datetime.now(UTC),
            custom=tuple(custom),
        )

    def _provenance(
        self,
        page_index: int,
        rect: RectT | None,
        confidence: float,
        *,
        kind: SourceKind,
        note: str | None = None,
        engine: str | None = None,
        band: ConfidenceBand | None = None,
    ) -> Provenance:
        report = self._page_reports.get(page_index)
        dpi = report.ocr_dpi if (report is not None and kind is SourceKind.OCR) else None
        return Provenance(
            kind=kind,
            document_path=str(self.document.path) if self.document.path else None,
            document_hash=self.document.content_hash,
            page_index=page_index,
            rect=_rect(rect) if rect is not None else None,
            dpi=dpi or None,
            engine=engine or _EXTRACTOR,
            engine_version=_EXTRACTOR_VERSION,
            confidence=confidence,
            band=band or _band(confidence),
            extracted_at=datetime.now(UTC),
            note=note,
        )

    def _block_node(self, draft: BlockDraft) -> Block | None:
        page = draft.first_page
        report = self._page_reports.get(page)
        kind = (
            SourceKind.OCR
            if report is not None and report.source in ("ocr", "text-layer+ocr")
            else SourceKind.PDF_TEXT_LAYER
        )
        inlines = self._inlines(draft)
        if not inlines:
            return None
        note = (
            None
            if draft.first_page == draft.last_page
            else f"continua até a página {draft.last_page}"
        )
        if kind is SourceKind.OCR:
            # Sol §SOL-10: an OCR block carries its own spans' confidence,
            # engine and review flag -- never the page's worst line.
            confidence = draft.confidence
            engines = sorted({sp.engine for sp in draft.spans if sp.engine})
            review = any(sp.review for sp in draft.spans)
            notes = [n for n in (note,) if n]
            if review:
                notes.append("OCR para revisão: confiança ou evidência insuficiente na região")
            provenance = self._provenance(
                page, draft.boxes.get(page), confidence, kind=kind,
                note="; ".join(notes) or None,
                engine="+".join(engines) if engines else None,
                band=ConfidenceBand.DOUBTFUL if review and confidence >= _DOUBTFUL else None,
            )
        else:
            # Text-layer spans carry 1.0; the page's verdict is what bounds them
            # (0.98 for an accepted layer, lower when the notation is damaged).
            confidence = min(draft.confidence, report.confidence if report is not None else 1.0)
            provenance = self._provenance(
                page, draft.boxes.get(page), confidence, kind=kind, note=note)
        props = ParagraphProps(style=draft.style)
        if draft.kind is RegionKind.HEADING:
            return Heading(
                level=draft.heading_level or 1,
                content=inlines,
                props=props,
                provenance=provenance,
            )
        return Paragraph(content=inlines, props=props, provenance=provenance)

    def _inlines(self, draft: BlockDraft) -> tuple[Inline, ...]:
        out: list[Inline] = []
        images = list(draft.inline_images)
        for span in draft.spans:
            if span.text == _IMAGE_PLACEHOLDER:
                if images:
                    node = self._inline_image_node(images.pop(0), draft.first_page)
                    if node is not None:
                        out.append(node)
                continue
            out.extend(_span_inlines(span))
        return tuple(out)

    def _diagram_node(self, entry: _DiagramEntry) -> Diagram:
        hit, context = entry.hit, entry.context
        fen = hit.fen or _EMPTY_BOARD
        if context.side_to_move is not None and hit.fen:
            fen = _with_side(fen, context.side_to_move)
        warnings: list[str] = []
        if not hit.fen:
            warnings.append(
                "posição não lida: o diagrama foi localizado mas o conteúdo exige a via B/C "
                "(raster); a FEN é um tabuleiro vazio provisório."
            )
        if context.side_to_move is not None:
            warnings.append(f"lado a jogar pela legenda: «{context.side_to_move_evidence}»")
        caption = tuple(_caption_inlines(context))
        crop = self._asset_crop(entry.page_index, hit.box, f"diagrama-p{entry.page_index + 1}")
        source = DiagramSource(
            kind=SourceKind.PDF_VECTOR if hit.path is RecognitionPath.VECTOR else SourceKind.VISION,
            path=str(self.document.path) if self.document.path else None,
            content_hash=self.document.content_hash,
            page_index=entry.page_index,
            rect=_rect(hit.box),
            extracted_at=datetime.now(UTC),
            extractor=_EXTRACTOR,
            extractor_version=_EXTRACTOR_VERSION,
        )
        recognition = RecognitionResult(
            fen=hit.fen or "",
            overall_confidence=hit.confidence if hit.fen else 0.0,
            side_to_move_confidence=(
                context.side_to_move_confidence if context.side_to_move is not None else None
            ),
            # OCR_UI_ROADMAP passo 7 (SPEC R2.5): the origin travels with the
            # side, and "default" is said out loud.
            side_to_move_source=(
                context.side_to_move_origin if context.side_to_move is not None else "default"
            ),
            path=hit.path,
            model_name=hit.method or None,
            recognised_at=datetime.now(UTC),
            warnings=tuple(warnings),
        )
        stipulation = None
        if context.side_to_move is not None:
            stipulation = "Brancas jogam" if context.side_to_move else "Pretas jogam"
        return Diagram(
            fen=fen,
            orientation=Orientation.WHITE if hit.orientation_white else Orientation.BLACK,
            source=source,
            recognition=recognition,
            caption=caption,
            number=context.exercise_number,
            label=context.label,
            stipulation=stipulation,
            side_to_move_indicator=context.side_to_move is not None,
            alt_text=(crop.description if crop else None),
            provenance=self._provenance(
                entry.page_index,
                hit.box,
                hit.confidence if hit.fen else 0.0,
                kind=SourceKind.PDF_VECTOR
                if hit.path is RecognitionPath.VECTOR
                else SourceKind.VISION,
                note=None if crop is None else f"recorte em {crop.key}",
            ),
        )

    def _figure_node(self, entry: _FigureEntry) -> Block | None:
        resource = self._asset_crop(
            entry.page_index, entry.image.box,
            f"regiao-p{entry.page_index + 1}" if entry.note else f"figura-p{entry.page_index + 1}",
            image=entry.image,
            description=(f"Região da página {entry.page_index + 1} mantida como imagem. "
                         f"{entry.note}") if entry.note else None,
        )
        if resource is None:
            return None
        provenance = self._provenance(
            entry.page_index, entry.image.box, 0.0 if entry.note else 1.0,
            kind=SourceKind.IMAGE, note=entry.note or None)
        block = ImageBlock(
            resource=resource.key,
            alt_text=resource.description,
            width=Measure.points(entry.image.box[2] - entry.image.box[0]),
            height=Measure.points(entry.image.box[3] - entry.image.box[1]),
            provenance=provenance,
        )
        if entry.full_page:
            return block
        return Figure(content=(block,), alt_text=resource.description, provenance=provenance)

    def _scan_node(self, entry: _ScanEntry) -> Block | None:
        frame = self.document.frame(entry.page_index)
        box = entry.image.box if entry.image is not None else frame.rect
        resource = self._asset_crop(
            entry.page_index,
            box,
            f"pagina-p{entry.page_index + 1}",
            image=entry.image,
            description=f"Página {entry.page_index + 1} digitalizada, sem texto legível.",
        )
        if resource is None:
            return None
        return ImageBlock(
            resource=resource.key,
            alt_text=resource.description,
            width=Measure.points(box[2] - box[0]),
            height=Measure.points(box[3] - box[1]),
            provenance=self._provenance(
                entry.page_index, box, 0.0, kind=SourceKind.IMAGE, note=entry.reason
            ),
        )

    def _inline_image_node(self, image: ImagePlacement, page_index: int) -> ImageInline | None:
        resource = self._asset_crop(
            page_index, image.box, f"simbolo-p{page_index + 1}", image=image
        )
        if resource is None:
            return None
        return ImageInline(
            resource=resource.key,
            alt_text=resource.description,
            height=Measure.points(image.box[3] - image.box[1]),
        )

    def _asset_crop(
        self,
        page_index: int,
        box: RectT,
        stem: str,
        *,
        image: ImagePlacement | None = None,
        description: str | None = None,
    ) -> Resource | None:
        """Declare (and, with an asset directory, write) one image resource."""
        self._asset_counter += 1
        key = f"{stem}-{self._asset_counter:04d}"
        width_pt = max(0.0, box[2] - box[0])
        height_pt = max(0.0, box[3] - box[1])
        path: str | None = None
        byte_size: int | None = None
        width_px = image.width if image is not None else None
        height_px = image.height if image is not None else None
        dpi = float(self.options.asset_dpi)
        if self.options.asset_dir is not None:
            target = Path(self.options.asset_dir) / f"{key}.png"
            data, width_px, height_px = self._render_png(page_index, box, dpi)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            path = str(target)
            byte_size = len(data)
        resource = Resource(
            key=key,
            kind=ResourceKind.IMAGE,
            path=path,
            media_type="image/png",
            byte_size=byte_size,
            width=width_px,
            height=height_px,
            dpi=dpi if path else None,
            description=description
            or f"Imagem da página {page_index + 1} ({width_pt:.0f} × {height_pt:.0f} pt)",
        )
        self._resources.append(resource)
        return resource

    def _render_png(self, page_index: int, box: RectT, dpi: float) -> tuple[bytes, int, int]:
        import pymupdf

        frame = self.document.frame(page_index)
        clip = frame.clamp(box)
        scale = frame.scale_for(dpi)
        with self.document.locked() as doc:
            page = doc[page_index]
            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                clip=pymupdf.Rect(*clip),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            data = pix.tobytes("png")
            return data, int(pix.width), int(pix.height)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _sort_like_a_reader(items: list[_Entry]) -> None:
    """Order entries sharing one slot the way the page is read: by column, then down.

    A page of six exercise diagrams in two columns is read left column top to
    bottom, then right column -- 1699, 1700, 1701, 1702 -- not row by row.
    Columns are found from the entries themselves (overlapping x ranges), so a
    single-column page degenerates to plain top-to-bottom order.
    """
    if len(items) < 2:  # noqa: PLR2004 - nothing to order
        return
    boxes = [_entry_box(e) for e in items]
    order = sorted(range(len(items)), key=lambda i: boxes[i][0])
    clusters: list[list[int]] = []
    reach = 0.0
    for i in order:
        if clusters and boxes[i][0] <= reach:
            clusters[-1].append(i)
            reach = max(reach, boxes[i][2])
        else:
            clusters.append([i])
            reach = boxes[i][2]
    column_of = {i: c for c, members in enumerate(clusters) for i in members}
    ranked = sorted(range(len(items)), key=lambda i: (column_of[i], boxes[i][1]))
    items[:] = [items[i] for i in ranked]


def _column_of(rows: PageRows, box: RectT) -> int:
    cx = (box[0] + box[2]) / 2.0
    for column in rows.layout.columns:
        if column.box.x0 <= cx <= column.box.x1:
            return column.index
    return -1


def _entry_box(entry: _Entry) -> RectT:
    if isinstance(entry, _FigureEntry):
        return entry.image.box
    if isinstance(entry, _DiagramEntry):
        return entry.hit.box
    if isinstance(entry, BlockDraft):
        return entry.boxes.get(entry.first_page, (0.0, 0.0, 0.0, 0.0))
    return entry.image.box if entry.image is not None else (0.0, 0.0, 0.0, 0.0)


def _rect(box: RectT) -> Rect:
    return Rect(
        x=box[0], y=box[1], width=max(0.0, box[2] - box[0]), height=max(0.0, box[3] - box[1])
    )


def _review_item_dict(item: ReviewItem) -> dict[str, Any]:
    return {
        "page_index": item.page_index, "rect": list(item.rect), "kind": item.kind,
        "decision": item.decision, "reasons": list(item.reasons), "text": item.text,
        "engine": item.engine, "score": item.score,
        "alternatives": [list(a) for a in item.alternatives],
    }


def _slot_for_box(rows: PageRows, box: RectT) -> int:
    """Index of the last row above ``box`` in its column; ``-1`` for none."""
    best = -1
    for r, row in enumerate(rows.rows):
        if row.box[1] <= box[1] and (
            row.column == -1 or _column_of(rows, box) in (-1, row.column)
        ):
            best = r
    return best


def _band(confidence: float) -> ConfidenceBand:
    if confidence >= 0.995:  # noqa: PLR2004 - the text layer's own ceiling
        return ConfidenceBand.CERTAIN
    if confidence >= _CONFIDENT:
        return ConfidenceBand.CONFIDENT
    if confidence >= _DOUBTFUL:
        return ConfidenceBand.DOUBTFUL
    return ConfidenceBand.UNRELIABLE


def _run_props(span: TextSpan) -> RunProps:
    return RunProps(
        font_family=span.font or None,
        font_size=Measure.points(round(span.size, 2)) if span.size > 0 else None,
        font_weight=int(FontWeight.BOLD) if span.bold else None,
        italic=True if span.italic else None,
        vertical_align=VerticalAlign.SUPERSCRIPT if span.superscript else None,
    )


def _span_inlines(span: TextSpan) -> list[Inline]:
    """A span as IR inlines: text runs, with figurines as :class:`PieceGlyph`.

    A Unicode chess symbol is a piece whichever font drew it -- the Chernev
    sets ``♕`` in MS Gothic next to Cambria text -- so every U+2654-U+265F
    becomes a glyph node, not only the letters a figurine font mapped.
    """
    props = _run_props(span)
    if not span.figurine and not any(ch in _PIECE_OF_GLYPH for ch in span.text):
        return [Text(content=span.text, props=props)]
    out: list[Inline] = []
    buffer: list[str] = []
    for ch in span.text:
        piece = _PIECE_OF_GLYPH.get(ch)
        if piece is None:
            buffer.append(ch)
            continue
        if buffer:
            out.append(Text(content="".join(buffer), props=props))
            buffer = []
        out.append(PieceGlyph(piece=piece, font_family=span.font or None, props=props))
    if buffer:
        out.append(Text(content="".join(buffer), props=props))
    return out


def _caption_inlines(context: DiagramContext) -> list[Inline]:
    """The caption as printed, plus the game header when it was parsed elsewhere."""
    primary = " ".join(context.caption_primary.split())
    parts: list[str] = [primary] if primary else []
    if context.players is not None and context.players[0] not in primary:
        parts.append(f"{context.players[0]} – {context.players[1]}")
    if context.event or context.year:
        year = str(context.year) if context.year else ""
        where = ", ".join(p for p in (context.event, year) if p)
        if where and where not in primary and (context.event or year) not in primary:
            parts.append(where)
    text = " · ".join(parts)
    return [Text(content=text)] if text else []


def _with_side(fen: str, white: bool) -> str:
    fields = fen.split()
    if len(fields) < 2:  # noqa: PLR2004 - placement and side
        return fen
    fields[1] = "w" if white else "b"
    return " ".join(fields)


def _stylesheet(body_size: float) -> StyleSheet:
    size = Measure.points(round(body_size, 1)) if body_size > 0 else None
    body = ParagraphStyle(name="Body", display_name="Corpo", run=RunProps(font_size=size))
    styles = [
        body,
        ParagraphStyle(name="Caption", display_name="Legenda", based_on="Body", next_style="Body"),
        ParagraphStyle(name="Footnote", display_name="Nota de rodapé", based_on="Body"),
        ParagraphStyle(name="Movetext", display_name="Lances", based_on="Body"),
    ]
    styles.extend(
        ParagraphStyle(
            name=f"Heading {level}",
            display_name=f"Título {level}",
            next_style="Body",
            outline_level=level,
            run=RunProps(font_weight=int(FontWeight.BOLD)),
        )
        for level in range(1, 7)
    )
    return StyleSheet(paragraph_styles=tuple(styles), default_paragraph_style="Body")


def import_pdf(
    source: PdfDocument | Path | str, options: PdfImportOptions | None = None
) -> ImportResult:
    """Import a PDF into the Document IR.  Opens and closes the file when given a path."""
    if isinstance(source, PdfDocument):
        return PdfImporter(source, options).run()
    from caissa.ingest.pdf.document import open_pdf

    with open_pdf(source) as document:
        return PdfImporter(document, options).run()
