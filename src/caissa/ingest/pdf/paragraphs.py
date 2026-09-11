"""From lines on a page to paragraphs of a book.

The layout questions -- which lines are furniture, footnotes, headings or
captions; where the columns are; in what order a human reads -- are answered
by :mod:`caissa.ocr.layout.analyze`, which already serves the OCR path and is
deliberately not duplicated here.  What this module adds is the part PDFimport
got right and the layout analyser does not attempt: turning ordered lines into
**paragraphs with styled runs**, across line breaks, column breaks and page
breaks, without gluing what should be apart or cutting what should be one.

The rules, each with the measurement that put it there (PDFimport
``extract.py``, absorbed 2026-09-11):

**A block is not a paragraph.**  PDF writers and OCR engines start a new block
wherever an inline image or a font change interrupts a line, so a printed line
can arrive as half a dozen blocks.  Lines are first merged into visual *rows*
-- fragments sharing a *baseline* inside one column, in whatever order the
producer emitted them -- and each row remembers which blocks it came from.  A
block boundary that falls *between* rows is evidence of a paragraph break,
never proof: a third-party OCR layer (Nunn) opens a block every few lines for
no reason, so the boundary counts only where the row before it stopped short
or the row after it is indented.

**Ragged text has no measure, so it reads three other things.**  An indent
against the open paragraph's own left edge; a short line that closed a
sentence followed by a line indented against the column that opens like a
sentence (a capital, a figurine, or -- after a full stop or a change of
weight -- a digit); and, with neither indent nor extra leading (Chernev), a
short line that closed a sentence and stopped where the next line's first
word would still have fitted: a break the typesetter chose, not one the
measure forced.

**Justified text reads its own right margin.**  A first-line indent and a
hanging indent are mirror images, so "starts right of the paragraph's left
edge" fires on the second line of a list item and stays silent on the next
item.  Where the column is justified, the right margin decides both ways: the
line before an opener is short *and* ends like a sentence.  Measured over
three books: two justified ones put 84 % and 70 % of body lines on the margin,
an OCR'd typewriting manual 25 % -- so the measure is reported only for a
column whose lines really do line up (:func:`column_measures`).

**Hyphenation is undone, moves are not split.**  A trailing hyphen between
two letters is a line-break hyphen; one after a digit or before a capital
belongs to the text.  And a move broken across lines between the piece and
its square (``26.Bxc6 K`` / ``h8!``) must close up, not read ``K h8``.

**A paragraph continues onto the next page unless it ended like a sentence**
and the next fragment starts like a continuation (lowercase, digit, closing
punctuation, or a figurine).

Heading levels, outline attachment and move-text styling are document-level
decisions and live in :func:`finish_document`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Final

from caissa.ingest.pdf.document import OutlineEntry
from caissa.ingest.pdf.geometry import RectT
from caissa.ingest.pdf.textlayer import ImagePlacement, PageText, TextLine, TextSpan
from caissa.ocr.layout.analyze import (
    LayoutConfig,
    LayoutInput,
    LayoutLine,
    PageLayout,
    RunningFurnitureDetector,
    analyze_page,
)
from caissa.ocr.types import BBox, RegionKind

__all__ = [
    "BlockDraft",
    "PageRows",
    "ParagraphBuilder",
    "ParagraphConfig",
    "Row",
    "column_measures",
    "diagram_extents",
    "finish_document",
    "layout_page",
    "looks_like_moves",
]

#: A paragraph continues onto the next page unless it ends like a sentence.
SENTENCE_END: Final = ".!?…:;”’\"')]}»"
#: Bare-digit list openers and move numbers must not count as sentence ends.
_MAX_HEADING_LEVELS: Final = 6
_MIN_HEADING_CHARS: Final = 4
_MIN_HEADING_LETTERS: Final = 3
_ROUND_SIZE: Final = 1
_MOVE_TAIL: Final = re.compile(r"(?:^|\s)[KQRBN♔-♟]$")
_MOVE_HEAD: Final = re.compile(r"^(?:[a-h][1-8x]|x[a-h])")
#: A move with its number: ``12.Nf3``, ``12...Nf3``, ``12…♘f3``, ``21 ♖f1-d1``
#: (a tabular move line, number and move in separate cells), ``21 f1-d1``,
#: and castling.  The number may be followed by dots, an ellipsis, or -- only
#: when a figurine or a long-algebraic move follows -- nothing at all.
_MOVE_RE: Final = re.compile(
    r"\d+\s*(?:\.{1,3}|…)\s*[♔-♟]?[KQRBNCDTLSAPFH]?[a-h]?[1-8]?[x×:\-–]?[a-h][1-8]"
    r"|\d+\s+(?:[♔-♟][a-h]?[1-8]?[x×:\-–]?[a-h][1-8]|[a-h][1-8][x×:\-–][a-h][1-8])"
    r"|O-O(?:-O)?|0-0(?:-0)?"
)
_WS: Final = re.compile(r"\s+")
_CAPTION_RE: Final = re.compile(
    r"^(position after|diagram|diagrama|posi[cç][aã]o ap[oó]s|stellung nach|"
    r"posici[oó]n despu[eé]s)\b",
    re.IGNORECASE,
)
_HYPHENS: Final = ("-", "‐", "­")
_MIN_MOVES_TEXT: Final = 4
_SHORT_MOVE_TEXT: Final = 40
#: Share of the non-space characters that must sit inside move matches for a
#: paragraph to be move text.  Measured on Dvoretsky p. 201-206: analysis
#: lines score 0.55-0.90, commentary paragraphs quoting moves score 0.08-0.22.
_MOVE_SHARE: Final = 0.35
_MAX_CAPTION_CHARS: Final = 120
#: A bold run-in head must be at least this share of the body size; smaller
#: bold text is a caption or a footnote label.
_RUN_IN_MIN_SIZE: Final = 0.95
#: A line counts as reaching the measure when it ends within this much of it:
#: four points, or three percent of the measure, whichever is larger.
_MEASURE_SLACK_PT: Final = 4.0
#: Two rows are "the same size" within this much.
_HALF_POINT: Final = 0.6
_MEASURE_SLACK_FRAC: Final = 0.03


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ParagraphConfig:
    """Every tunable of the paragraph rules, with its reason."""

    #: A row starting this far right of the paragraph's own left edge opens a
    #: new paragraph (first-line indent).  In points; 6 pt is half an em at the
    #: body sizes books use and clears the jitter of a ragged left edge.
    indent_pt: float = 6.0
    #: Vertical gap, in multiples of the page's mean row height, that opens a
    #: paragraph.  1,5 lines is the classic "space between paragraphs".
    paragraph_gap: float = 1.5
    #: Rows whose baselines are this close (fraction of the median row height)
    #: are one visual row.
    row_tolerance: float = 0.5
    #: A justified column must put this share of its body lines on the margin.
    justified_share: float = 0.55
    #: ...over at least this many body lines, or the measure is unknown.
    min_measure_lines: int = 6
    #: Body lines shorter than this are not prose and do not vote.
    min_measure_chars: int = 25
    #: In a ragged-right column, a row ending this share of the column width
    #: before the right edge is "short" (a paragraph's last line).
    ragged_short_frac: float = 0.15
    #: The next line's first word must fit in the previous line's leftover
    #: space with this much to spare (a space and some kerning) before the
    #: leftover counts as a chosen break.
    word_fit_slack: float = 1.5
    #: Inline image: height at most this many times the host line's height.
    inline_image_max_em: float = 1.6
    #: An image with a side under this is a bullet or a rule fragment.
    min_figure_pt: float = 24.0
    #: An image covering this share of the page is a full-page plate or scan.
    full_page_share: float = 0.80
    #: Coordinate labels sit within this many board cells of the lattice.
    axis_label_reach: float = 2.0
    #: An image covering this share of a diagram box (or covered by it) is
    #: the diagram's own pixels, not a separate figure.
    diagram_image_overlap: float = 0.5
    #: Characters inside the detected columns must outnumber the characters
    #: of lines spanning them by this factor for the columns to be believed.
    column_mass_ratio: float = 1.0
    #: The text of a real column spans at least this share of the page's
    #: text width; the cells of a move table span a few percent.
    column_width_min_frac: float = 0.18
    #: Join a paragraph across a page break when the rules say it continues.
    join_pages: bool = True
    #: Heading must be at least this much larger than the body (mirrors
    #: ``LayoutConfig.heading_size_ratio``).
    heading_ratio: float = 1.15
    heading_max_chars: int = 90
    layout: LayoutConfig = field(default_factory=LayoutConfig)


# --------------------------------------------------------------------------- #
# Rows
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Row:
    """One visual line: fragments on one baseline in one column, merged.

    Attributes:
        box: Union of the fragments, ``page.rect`` points.
        spans: Styled runs, left to right, an implied space inserted between
            fragments the PDF stored without one.
        blocks: Producer blocks the fragments came from.
        size: Largest font size on the row.
        column: Column index, ``-1`` for a spanning row.
        kind: Region kind decided by the layout analyser.
        page_index: Zero-based page.
        inline_images: Small images hosted by this row, in x order with the
            text (``spans`` carries a placeholder span for each).
        confidence: Lowest span confidence.
    """

    box: RectT
    spans: tuple[TextSpan, ...]
    blocks: frozenset[int]
    size: float
    column: int
    kind: RegionKind
    page_index: int
    inline_images: tuple[ImagePlacement, ...] = ()
    confidence: float = 1.0

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def starts_with_image(self) -> bool:
        return bool(self.spans) and self.spans[0].text == _IMAGE_PLACEHOLDER

    @property
    def ends_with_image(self) -> bool:
        return bool(self.spans) and self.spans[-1].text == _IMAGE_PLACEHOLDER


#: Object replacement character: the span that stands for an inline image.
_IMAGE_PLACEHOLDER: Final = "￼"
#: Clearance, in ems, that separates an inline symbol from the word next to
#: it; a figurine inside a move touches (0,0-0,1 em), a word gap is 0,25+.
_EM_GAP: Final = 0.2


@dataclass(slots=True)
class PageRows:
    """A page after layout: rows in reading order plus what is not text."""

    page_index: int
    rows: list[Row]
    layout: PageLayout
    figures: list[ImagePlacement]
    full_page_images: list[ImagePlacement]
    #: Diagram boxes handed in by the caller, unchanged, for placement.
    diagrams: tuple[RectT, ...]
    mean_row_height: float
    body_size: float
    #: Measure (right edge) per column for the columns that justify.
    measures: dict[int, float] = field(default_factory=dict)
    #: Left edge per column: the smallest ``x0`` of its rows.
    column_lefts: dict[int, float] = field(default_factory=dict)
    #: Right edge per column: the largest ``x1`` of its rows -- the "soft"
    #: measure for ragged-right columns.
    column_rights: dict[int, float] = field(default_factory=dict)


def _to_bbox(rect: RectT) -> BBox:
    return BBox.from_edges(*rect)


def _union(a: RectT, b: RectT) -> RectT:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _overlap_share(a: RectT, b: RectT) -> float:
    """Intersection area over the smaller of the two boxes."""
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (width * height) / smaller if smaller > 0 else 0.0


def _vertical_overlap(a: RectT, b: RectT) -> float:
    span = min(a[3] - a[1], b[3] - b[1])
    if span <= 0:
        return 0.0
    return max(0.0, min(a[3], b[3]) - max(a[1], b[1])) / span


def _host_line(
    image: ImagePlacement, lines: Sequence[TextLine], config: ParagraphConfig
) -> int | None:
    """Index of the text line an image sits inside, or ``None`` for a figure.

    A piece symbol dropped into a sentence is about the height of the line and
    overlaps it vertically; a figure is taller than its neighbours or stands
    apart from every line.
    """
    ix0, iy0, ix1, iy1 = image.box
    height = iy1 - iy0
    best: tuple[float, int] | None = None
    for index, line in enumerate(lines):
        lx0, ly0, lx1, ly1 = line.box
        line_h = max(1.0, ly1 - ly0)
        if height > config.inline_image_max_em * line_h:
            continue
        if _vertical_overlap(image.box, line.box) < 0.5:  # noqa: PLR2004 - half the shorter height
            continue
        # Horizontally inside the line, or right next to its ends (an em).
        slack = line_h
        if ix1 < lx0 - slack or ix0 > lx1 + slack:
            continue
        gap = 0.0 if lx0 <= ix0 <= lx1 else min(abs(ix0 - lx1), abs(lx0 - ix1))
        if best is None or gap < best[0]:
            best = (gap, index)
    return None if best is None else best[1]


def _row_spans(
    fragments: Sequence[tuple[float, TextLine | ImagePlacement]],
) -> tuple[TextSpan, ...]:
    """Interleave text fragments and inline images strictly by x."""
    out: list[TextSpan] = []
    prev_right = 0.0
    for _, payload in sorted(fragments, key=lambda item: item[0]):
        if isinstance(payload, ImagePlacement):
            x0, y0, x1, y1 = payload.box
            # A symbol inside notation ("1.<knight>f3") touches its
            # neighbours; one between words stands a quarter em clear of
            # them.  The source has no space glyph either way, so the
            # geometry decides.
            if (
                out
                and out[-1].text != _IMAGE_PLACEHOLDER
                and x0 - prev_right > _EM_GAP * out[-1].size
                and not out[-1].text.endswith(" ")
            ):
                out[-1] = replace(out[-1], text=out[-1].text + " ")
            out.append(TextSpan(text=_IMAGE_PLACEHOLDER, box=(x0, y0, x1, y1), size=y1 - y0))
            prev_right = x1
            continue
        piece = list(payload.spans)
        if out and piece:
            prev = out[-1]
            if prev.text == _IMAGE_PLACEHOLDER:
                first = piece[0]
                if first.box[0] - prev_right > _EM_GAP * first.size and not first.text.startswith(
                    " "
                ):
                    piece[0] = replace(first, text=" " + first.text)
            elif (
                prev.text
                and not prev.text.endswith(" ")
                and not piece[0].text.startswith(" ")
                and piece[0].box[0] - prev_right > _EM_GAP * max(prev.size, piece[0].size)
            ):
                # Fragments side by side with clearance between them are
                # separate words even when the PDF stores no space glyph; a
                # fragment that touches the previous one ("1." then the
                # figurine knight, split at the font change) is not.
                out[-1] = replace(prev, text=prev.text + " ")
        out.extend(piece)
        prev_right = payload.box[2]
    return tuple(out)


def _median(values: Sequence[float], default: float) -> float:
    if not values:
        return default
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _baseline(line: TextLine) -> float:
    """The line's baseline: median of its spans', or the box bottom."""
    baselines = [span.baseline for span in line.spans if span.baseline > 0.0 and span.text.strip()]
    return _median(baselines, line.box[3])


def _build_rows(
    lines: Sequence[TextLine],
    layout: PageLayout,
    page_index: int,
    inline_hosts: Mapping[int, list[ImagePlacement]],
    config: ParagraphConfig,
) -> list[Row]:
    """Merge same-baseline fragments within a column, in reading order.

    Fragments are gathered by *baseline*, not by box top -- a figurine glyph
    set in a chess font has a different ascent from the text beside it, so
    its box starts lower while it sits on the same line (Chernev, *Melhores
    Finais de Capablanca*: every ``♖`` came out as a paragraph of its own) --
    and regardless of the order they arrive in: the producer may emit the
    figurine after the text it precedes, and the XY-cut reads the cells of a
    move table column by column (``28``, ``29``, then ``...``, ``♔g1-f2``,
    then the Black moves).  Each fragment joins the open row of its column
    that shares its baseline, wherever that row is; :func:`_row_spans` sorts
    the fragments by x.  Rows keep the order of their first fragment.
    """
    column_of: dict[int, int] = {}
    for col in layout.columns:
        for i in col.line_indices:
            column_of[i] = col.index
    # On a single-column page every line is in the column, including the
    # wide ones the column detector left out as "spanning": a fragment that
    # ends a line ("30 … ♔") and the long fragment that continues it are on
    # one baseline and must be one row.
    single_column = layout.column_count <= 1
    heights = [ln.box[3] - ln.box[1] for ln in lines if ln.box[3] > ln.box[1]]
    tol = max(2.0, config.row_tolerance * _median(heights, 10.0))

    groups: list[tuple[int, RegionKind, float, list[tuple[int, TextLine]]]] = []
    for i in layout.order:
        line = lines[i]
        kind = layout.kinds[i]
        # Geometry alone calls any short line under a diagram a caption; a
        # line of moves there is analysis continuing from the previous page
        # (Dvoretsky p. 207, "♕b3+! 4.♕xb3 axb3+" at the top of the column).
        if kind is RegionKind.CAPTION and looks_like_moves(line.text.strip()):
            kind = RegionKind.PARAGRAPH
        column = 0 if single_column else column_of.get(i, -1)
        baseline = _baseline(line)
        for group in groups:
            if group[0] == column and group[1] is kind and abs(group[2] - baseline) <= tol:
                group[3].append((i, line))
                break
        else:
            groups.append((column, kind, baseline, [(i, line)]))

    rows: list[Row] = []
    for column, kind, _, members in groups:
        fragments: list[tuple[float, TextLine | ImagePlacement]] = []
        blocks: set[int] = set()
        box = members[0][1].box
        images: list[ImagePlacement] = []
        for i, line in members:
            fragments.append((line.box[0], line))
            blocks.add(line.block_index)
            box = _union(box, line.box)
            for image in inline_hosts.get(i, ()):
                fragments.append((image.box[0], image))
                images.append(image)
                box = _union(box, image.box)
        rows.append(
            Row(
                box=box,
                spans=_row_spans(fragments),
                blocks=frozenset(blocks),
                size=max((ln.size for _, ln in members), default=0.0),
                column=column,
                kind=kind,
                page_index=page_index,
                inline_images=tuple(sorted(images, key=lambda im: im.box[0])),
                confidence=min((ln.confidence for _, ln in members), default=1.0),
            )
        )
    return rows


def column_measures(
    rows: Sequence[Row], body_size: float, config: ParagraphConfig
) -> dict[int, float]:
    """Where a full line ends in each column, for the columns that justify.

    Only lines at the body size and long enough to be prose vote: headings,
    captions, move notation and the loose lines around a diagram are short by
    nature and would drown the signal.
    """
    columns: dict[int, list[Row]] = {}
    for row in rows:
        if (
            abs(row.size - body_size) > _HALF_POINT
            or len(row.text.strip()) < config.min_measure_chars
        ):
            continue
        columns.setdefault(row.column, []).append(row)
    out: dict[int, float] = {}
    for column, group in columns.items():
        if len(group) < config.min_measure_lines:
            continue
        right = max(r.box[2] for r in group)
        span = right - min(r.box[0] for r in group)
        if span <= 0:
            continue
        limit = right - max(_MEASURE_SLACK_PT, _MEASURE_SLACK_FRAC * span)
        if sum(1 for r in group if r.box[2] >= limit) >= config.justified_share * len(group):
            out[column] = limit
    return out


_AXIS_LABEL: Final = re.compile(r"^(?:[1-8]|[a-h](?:\W+[a-h])*)$")


def _is_axis_label_near(line: TextLine, diagrams: Sequence[RectT], config: ParagraphConfig) -> bool:
    """A bare rank digit or a run of file letters within reach of a board.

    The vector detector reports the 8x8 lattice; the labels sit outside it,
    which is why coverage by the board rectangle never catches them and why
    they used to come out as eight one-character paragraphs (Dvoretsky, every
    diagram).  Only the label *pattern* qualifies, so a caption printed just
    under the board is untouched.
    """
    if not diagrams or not _AXIS_LABEL.match(line.text.strip()):
        return False
    lx0, ly0, lx1, ly1 = line.box
    for dx0, dy0, dx1, dy1 in diagrams:
        reach = config.axis_label_reach * max(dx1 - dx0, dy1 - dy0) / 8.0
        if lx1 < dx0 - reach or lx0 > dx1 + reach or ly1 < dy0 - reach or ly0 > dy1 + reach:
            continue
        return True
    return False


def _columns_are_real(layout: PageLayout, config: ParagraphConfig) -> bool:
    """Are the detected columns text columns, or the cells of a move table?

    Two tests, both needed.  *Mass*: a page whose wide lines (spanning the
    gutters) carry at least as many characters as the lines inside the
    columns is a single-column page with some tabular rows.  *Width*: the
    text of a real column covers a sizeable share of the page -- 0,4 and
    more of the text width for two columns, 0,25 for three -- while the
    "columns" of a game score set as a table are cells: the move-number
    column of a Chernev game page is 10 pt wide, 0,02 of the page.  A
    per-line *fill* test was tried first and threw away real two-column
    pages whose lines are short moves (Boleslavsky, Euwe, Schiller: 12 of
    12 two-column pages read as one column); a *single-token* test after it
    threw away the two-column problem books (Schiller 10 of 12, Boleslavsky
    6 of 12), whose columns are numbers and captions.  What survives is the
    pair above, measured on the collection: 3 of 552 sampled pages keep a
    move table as three columns (all Chernev), and no two-column page is
    lost.
    """
    in_column = 0
    text_x0 = min((line.box.x0 for line in layout.lines if line.text.strip()), default=0.0)
    text_x1 = max((line.box.x1 for line in layout.lines if line.text.strip()), default=0.0)
    text_width = max(1.0, text_x1 - text_x0)
    for column in layout.columns:
        members = [layout.lines[i] for i in column.line_indices]
        in_column += sum(line.char_count for line in members)
        if members:
            union = max(m.box.x1 for m in members) - min(m.box.x0 for m in members)
            if union < config.column_width_min_frac * text_width:
                return False
    total = sum(
        line.char_count
        for line, kind in zip(layout.lines, layout.kinds, strict=True)
        if kind.is_prose
    )
    spanning = max(0, total - in_column)
    return in_column > spanning * config.column_mass_ratio


def diagram_extents(
    page: PageText, diagrams: Sequence[RectT], config: ParagraphConfig | None = None
) -> list[RectT]:
    """Each diagram box grown to cover the coordinate labels printed beside it.

    The visible diagram is board *plus* labels, and a caption's distance is
    measured from what is visible: on the Dvoretsky the caption sits 72 pt
    under the lattice but 53 pt under the file letters, and the trunk's 60 pt
    radius -- measured on books without labels -- only reaches it this way.
    """
    config = config or ParagraphConfig()
    extents = list(diagrams)
    for line in page.lines:
        if line.is_diagram:
            continue
        for i, box in enumerate(diagrams):
            if _is_axis_label_near(line, (box,), config):
                extents[i] = _union(extents[i], line.box)
                break
    return extents


def layout_page(
    page: PageText,
    *,
    diagrams: Sequence[RectT] = (),
    consumed: Sequence[RectT] = (),
    furniture: RunningFurnitureDetector | None = None,
    config: ParagraphConfig | None = None,
    body_size_hint: float = 0.0,
) -> PageRows:
    """Run layout analysis on a page and merge its lines into rows.

    ``diagrams`` are chess diagram boxes (from the vision front or the vector
    detector); text inside them is coordinate labels and leaves the flow.
    Lines set in a diagram font leave the flow regardless, and so do the
    ``consumed`` lines -- captions a diagram has already claimed.
    """
    config = config or ParagraphConfig()
    frame = page.frame
    taken = set(consumed)

    # Diagram-font rows are board glyphs, and the coordinate labels printed
    # beside a board are not prose either: out of the flow before layout.
    prose_lines = [
        line
        for line in page.lines
        if not line.is_diagram
        and not line.vertical
        and line.box not in taken
        and not _is_axis_label_near(line, diagrams, config)
    ]

    figures: list[ImagePlacement] = []
    full_page: list[ImagePlacement] = []
    inline_hosts: dict[int, list[ImagePlacement]] = {}
    for image in page.images:
        if image.area >= config.full_page_share * frame.area:
            full_page.append(image)
            continue
        # An image that *is* a detected diagram is the diagram's rendering,
        # not a figure of its own: the Karpov's scanned boards came out twice,
        # as a Diagram and as a Figure of the same pixels.
        if any(_overlap_share(image.box, d) > config.diagram_image_overlap for d in diagrams):
            continue
        host = _host_line(image, prose_lines, config)
        if host is not None:
            inline_hosts.setdefault(host, []).append(image)
            continue
        width = image.box[2] - image.box[0]
        height = image.box[3] - image.box[1]
        if width >= config.min_figure_pt and height >= config.min_figure_pt:
            figures.append(image)

    layout_lines = tuple(
        LayoutLine(
            box=_to_bbox(line.box),
            text=line.text,
            font_size=line.size or (line.box[3] - line.box[1]),
            confidence=line.confidence,
            source=line,
        )
        for line in prose_lines
    )
    layout_input = LayoutInput(
        page_box=BBox(0.0, 0.0, frame.width, frame.height),
        lines=layout_lines,
        figures=tuple(_to_bbox(f.box) for f in figures),
        diagrams=tuple(_to_bbox(d) for d in diagrams),
        rules=tuple(_to_bbox(r) for r in page.rules),
        page_index=frame.index,
    )
    layout = analyze_page(layout_input, config=config.layout, furniture=furniture)
    if layout.column_count > 1 and not _columns_are_real(layout, config):
        # The gutters were voted in by short fragments -- a tabular move list
        # ("21     ...     ♖f8-d8") on a single-column page -- while the
        # prose, which spans them, was excluded from the vote as "spanning
        # lines".  Character mass tells the two apart: real columns hold the
        # bulk of the page's characters inside them.
        single = replace(config.layout, max_columns=1)
        layout = analyze_page(layout_input, config=single, furniture=furniture)
    rows = _build_rows(prose_lines, layout, frame.index, inline_hosts, config)
    heights = [r.box[3] - r.box[1] for r in rows]
    mean_h = sum(heights) / len(heights) if heights else 12.0
    body = body_size_hint or layout.body_font_size
    # Column edges from the body text only: a footnote set wider than the
    # measure, or a heading, would push the "right edge" out and make every
    # body line look short (the synthetic gate book caught exactly that).
    # The right edge is the 90th percentile of the body rows' ``x1``, so one
    # stray wide row cannot own it either.
    lefts: dict[int, float] = {}
    rights_seen: dict[int, list[float]] = {}
    for row in rows:
        if not (row.kind is RegionKind.PARAGRAPH and row.text.strip()):
            continue
        if body > 0 and abs(row.size - body) > _HALF_POINT:
            continue
        lefts[row.column] = min(lefts.get(row.column, row.box[0]), row.box[0])
        rights_seen.setdefault(row.column, []).append(row.box[2])
    rights = {
        column: sorted(values)[min(len(values) - 1, int(len(values) * 0.9))]
        for column, values in rights_seen.items()
    }
    return PageRows(
        page_index=frame.index,
        rows=rows,
        layout=layout,
        figures=figures,
        full_page_images=full_page,
        diagrams=tuple(diagrams),
        mean_row_height=mean_h,
        body_size=body,
        measures=column_measures(rows, body, config),
        column_lefts=lefts,
        column_rights=rights,
    )


# --------------------------------------------------------------------------- #
# Paragraphs
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class BlockDraft:
    """A paragraph-level block before it becomes an IR node.

    Attributes:
        kind: ``PARAGRAPH``, ``HEADING``, ``CAPTION``, ``FOOTNOTE`` or
            ``MOVETEXT``.
        spans: Styled runs with line breaks resolved.
        size: Largest font size in the block.
        first_page: Page the block starts on.
        last_page: Page it ends on.
        boxes: Union box per page, for provenance.
        rows: How many rows were merged.
        column: Column of the first row.
        heading_level: Set by :func:`finish_document` for headings.
        outline_title: Outline entry title matched to this block, if any.
        inline_images: Images hosted inside the text, in order.
        confidence: Lowest row confidence.
        style: Paragraph style name decided at the end.
    """

    kind: RegionKind
    spans: list[TextSpan]
    size: float
    first_page: int
    last_page: int
    boxes: dict[int, RectT]
    rows: int = 1
    column: int = 0
    heading_level: int | None = None
    outline_title: str | None = None
    inline_images: list[ImagePlacement] = field(default_factory=list)
    confidence: float = 1.0
    style: str = "Body"

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans if s.text != _IMAGE_PLACEHOLDER)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and not self.inline_images


def _hyphen_wrap(tail: str, head: str) -> bool:
    """True when a line break falls inside a hyphenated word."""
    tail = tail.rstrip()
    return (
        tail.endswith(_HYPHENS)
        and len(tail) > 1
        and tail[-2].isalpha()
        and head[:1].isalpha()
        and head[:1].islower()
    )


def _split_move(tail: str, head: str) -> bool:
    """True when a line ends with a bare piece and the next starts with its square."""
    return bool(_MOVE_TAIL.search(tail)) and bool(_MOVE_HEAD.match(head))


def _merge_runs(spans: Iterable[TextSpan]) -> list[TextSpan]:
    out: list[TextSpan] = []
    for span in spans:
        if span.text == _IMAGE_PLACEHOLDER:
            out.append(span)
            continue
        if not span.text:
            continue
        if out and out[-1].text != _IMAGE_PLACEHOLDER and out[-1].same_style(span):
            prev = out[-1]
            out[-1] = replace(prev, text=prev.text + span.text, box=_union(prev.box, span.box))
        else:
            out.append(span)
    return out


def _append_row(spans: list[TextSpan], row_spans: Sequence[TextSpan]) -> None:
    """Append a wrapped row to a paragraph, undoing hyphenation."""
    if not row_spans:
        return
    if not spans:
        spans.extend(row_spans)
        return
    prev = spans[-1]
    head = row_spans[0].text
    if _IMAGE_PLACEHOLDER in (prev.text, head):
        spans.extend(row_spans)
        return
    tail = prev.text.rstrip()
    if _hyphen_wrap(tail, head):
        spans[-1] = replace(prev, text=tail[:-1])
    elif _split_move(tail, head):
        spans[-1] = replace(prev, text=tail)
    elif tail:
        spans[-1] = replace(prev, text=tail + " ")
    spans.extend(row_spans)


def _starts_paragraph(
    row: Row, prev: Row | None, page: PageRows, left: float, config: ParagraphConfig
) -> bool:
    """Whether ``row`` opens a paragraph, going by how the page is set.

    The question is asked of the row above, against the measure of the column
    *that row* sits in: "did what came before end?" is the same question at a
    column break.  Falling short of the measure is necessary but not
    sufficient -- a column can hold more than one measure (a puzzle prompt
    indented on both sides) -- so the line has to read like an ending too.

    A ragged-right column has no measure.  There the indent against the open
    paragraph's own left edge decides, plus one more case the indent alone
    cannot see: a one-line indented paragraph followed by another indented
    paragraph puts both first lines at the same ``x``.  For that, a short
    previous row that ended like a sentence, followed by a row indented
    against the *column's* left edge, opens a paragraph.
    """
    if prev is None:
        return row.box[0] > left + config.indent_pt
    limit = page.measures.get(prev.column)
    tail = prev.text.rstrip()
    ended = bool(tail) and tail[-1] in SENTENCE_END
    column_left = page.column_lefts.get(row.column)
    indented = column_left is not None and row.box[0] > column_left + config.indent_pt
    # A short line that did not close a sentence can still be the end of a
    # block when what follows is indented against the column and opens like
    # a sentence: the Dvoretsky's game header "4/2. G.van Breukelen 1969",
    # its bold move header "1.b6 axb6", and the first-line-indented prose
    # under each.  A hanging continuation is indented too, but the line
    # before it is full, not short.
    # A digit opens a sentence only after a closed one or a change of weight:
    # "29 ♔g1-f2" under "28 … ♔b8-b7" is the next row of a move table (same
    # weight, no full stop), while the bold "1.b6 axb6" under the game header
    # "4/3. A.Gerbstman 1928" is a new line of the book.
    opens = indented and _opens_sentence(row.text, allow_digit=ended or _weight_changes(prev, row))
    if limit is not None:
        # Where the column justifies, the right margin decides *instead of*
        # the indent: a hanging continuation is indented and is not a start.
        return prev.box[2] < limit and (ended or opens)
    if row.box[0] > left + config.indent_pt:
        return True
    column_right = page.column_rights.get(prev.column)
    if column_left is None or column_right is None or not (ended or opens):
        return False
    span = column_right - column_left
    short = prev.box[2] < column_right - config.ragged_short_frac * span
    # Neither indent nor extra leading (the Chernev sets paragraphs flush
    # and tight), but the previous line closed a sentence and stopped where
    # this line's first word would still have fitted: the break was chosen,
    # not forced by the measure.
    chosen = ended and column_right - prev.box[2] > _first_word_width(row) * config.word_fit_slack
    return short and (indented or chosen)


def _row_is_short(row: Row, page: PageRows, config: ParagraphConfig) -> bool:
    """Does the row stop before the column's right edge -- measure or ragged?"""
    limit = page.measures.get(row.column)
    if limit is not None:
        return row.box[2] < limit
    column_left = page.column_lefts.get(row.column)
    column_right = page.column_rights.get(row.column)
    if column_left is None or column_right is None:
        return False
    return row.box[2] < column_right - config.ragged_short_frac * (column_right - column_left)


def _first_word_width(row: Row) -> float:
    """Width of the row's first word, in points, from its span's proportions."""
    for span in row.spans:
        text = span.text
        if not text.strip() or text == _IMAGE_PLACEHOLDER:
            continue
        stripped = text.lstrip()
        word = stripped.split()[0]
        width = span.box[2] - span.box[0]
        if width <= 0 or not text:
            return span.size * len(word) * 0.5
        return width * len(word) / max(1, len(text))
    return 0.0


def _weight_changes(prev: Row, row: Row) -> bool:
    """Is the first inked span of ``row`` bold where the last of ``prev`` was not, or vice versa?"""
    last = next(
        (s for s in reversed(prev.spans) if s.text.strip() and s.text != _IMAGE_PLACEHOLDER), None
    )
    first = next((s for s in row.spans if s.text.strip() and s.text != _IMAGE_PLACEHOLDER), None)
    return last is not None and first is not None and last.bold != first.bold


def _opens_sentence(text: str, *, allow_digit: bool = True) -> bool:
    """Does the row start the way a paragraph starts -- capital, digit, figurine?"""
    head = text.lstrip()
    if not head:
        return False
    first = head[0]
    if first.isdigit():
        return allow_digit
    return first.isupper() or "♔" <= first <= "♟" or first in '(«“"'


def _continues(prev: BlockDraft, row: Row, body_size: float, config: ParagraphConfig) -> bool:
    """Would the open block and this row have been one paragraph but for the page break?"""
    prev_text = prev.text.rstrip()
    next_text = row.text.lstrip()
    if not prev_text or not next_text:
        return False
    if abs(prev.size - row.size) > 0.6:  # noqa: PLR2004 - half a point
        return False
    if body_size > 0 and prev.size >= body_size * config.heading_ratio:
        return False
    if prev_text[-1] in SENTENCE_END:
        return False
    first = next_text[0]
    return first.islower() or first.isdigit() or first in ",;)" or "♔" <= first <= "♟"


class ParagraphBuilder:
    """Feeds rows page by page and closes paragraphs by the rules above.

    Stateful across pages on purpose: the open paragraph at the foot of page
    12 is what page 13's first row may continue.
    """

    def __init__(self, config: ParagraphConfig | None = None, body_size: float = 0.0) -> None:
        self.config = config or ParagraphConfig()
        self.body_size = body_size
        self._open: BlockDraft | None = None
        self._left = 0.0
        self._prev_row: Row | None = None
        self._prev_blocks: frozenset[int] | None = None
        self._prev_bottom: float | None = None
        self._prev_ends_image = False

    @property
    def open_block(self) -> BlockDraft | None:
        return self._open

    def flush(self) -> BlockDraft | None:
        """Close the open block, if any, and return it."""
        block = self._open
        self._open = None
        self._prev_row = None
        self._prev_blocks = None
        self._prev_bottom = None
        self._prev_ends_image = False
        if block is None:
            return None
        block.spans = _merge_runs(block.spans)
        return None if block.is_empty else block

    def break_flow(self) -> BlockDraft | None:
        """A figure or diagram interrupts the text: close what is open."""
        return self.flush()

    def _should_start(self, row: Row, page: PageRows) -> bool:
        block = self._open
        if (
            block is None
            or row.kind is not block.kind
            or _starts_paragraph(row, self._prev_row, page, self._left, self.config)
        ):
            return True
        if block.last_page != row.page_index:
            return not (
                self.config.join_pages and _continues(block, row, page.body_size, self.config)
            )
        gap = row.box[1] - self._prev_bottom if self._prev_bottom is not None else 0.0
        if gap > page.mean_row_height * self.config.paragraph_gap:
            return True
        # A block boundary that falls between rows is evidence of a paragraph
        # break; one that falls mid-row only means an image interrupted the
        # text, and an image right at the row break explains the boundary too.
        # Evidence, not proof: an OCR'd layer (Nunn, *Secrets of Minor Piece
        # Endings*) starts a new block every few lines for no reason at all,
        # so the boundary counts only where the page agrees -- the previous
        # row stopped short of the measure, or this one is indented.
        boundary = bool(
            self._prev_blocks is not None
            and not (row.blocks & self._prev_blocks)
            and not self._prev_ends_image
            and not row.starts_with_image
        )
        if not boundary or self._prev_row is None:
            return False
        column_left = page.column_lefts.get(row.column)
        indented = column_left is not None and row.box[0] > column_left + self.config.indent_pt
        return indented or _row_is_short(self._prev_row, page, self.config)

    def feed(self, page: PageRows) -> list[BlockDraft]:
        """Consume one page's rows; return the blocks closed while doing so."""
        closed: list[BlockDraft] = []
        for row in page.rows:
            if row.kind.is_furniture or row.kind is RegionKind.DIAGRAM_LABEL:
                continue
            if not row.text.strip() and not row.inline_images:
                continue
            if self._should_start(row, page):
                done = self.flush()
                if done is not None:
                    closed.append(done)
            if self._open is None:
                self._open = BlockDraft(
                    kind=row.kind if row.kind in _BLOCK_KINDS else RegionKind.PARAGRAPH,
                    spans=list(row.spans),
                    size=row.size,
                    first_page=row.page_index,
                    last_page=row.page_index,
                    boxes={row.page_index: row.box},
                    column=row.column,
                    inline_images=list(row.inline_images),
                    confidence=row.confidence,
                )
                self._left = row.box[0]
            else:
                block = self._open
                _append_row(block.spans, row.spans)
                block.size = max(block.size, row.size)
                block.rows += 1
                block.last_page = row.page_index
                block.boxes[row.page_index] = _union(
                    block.boxes.get(row.page_index, row.box), row.box
                )
                block.inline_images.extend(row.inline_images)
                block.confidence = min(block.confidence, row.confidence)
                # A wrapped row may sit left of the indented first row.
                self._left = min(self._left, row.box[0])
            self._prev_row = row
            self._prev_blocks = row.blocks
            self._prev_bottom = row.box[3]
            self._prev_ends_image = row.ends_with_image
        return closed


_BLOCK_KINDS: Final = frozenset(
    {
        RegionKind.PARAGRAPH,
        RegionKind.HEADING,
        RegionKind.CAPTION,
        RegionKind.FOOTNOTE,
        RegionKind.MOVETEXT,
    }
)


# --------------------------------------------------------------------------- #
# Document-level decisions
# --------------------------------------------------------------------------- #


def looks_like_moves(text: str) -> bool:
    """Is this paragraph *mostly* chess notation, rather than prose quoting moves?

    PDFimport styled a paragraph as moves from two hits anywhere in it, which
    on the Dvoretsky put a full commentary paragraph ("White had to play 1.h2!
    Black can neither drive...") in the move style.  Here the notation has to
    carry the paragraph: at least two moves, and the characters inside move
    matches must be at least :data:`_MOVE_SHARE` of the non-space text.  A
    very short line with one move (``"1.e4"``) still counts.
    """
    if len(text) < _MIN_MOVES_TEXT:
        return False
    matches = list(_MOVE_RE.finditer(text))
    if not matches:
        return False
    if len(matches) < 2 and len(text) >= _SHORT_MOVE_TEXT:  # noqa: PLR2004 - two moves
        return False
    inked = sum(1 for ch in text if not ch.isspace()) or 1
    covered = sum(1 for m in matches for ch in m.group(0) if not ch.isspace())
    return covered / inked >= _MOVE_SHARE


def _heading_len_ok(text: str, config: ParagraphConfig) -> bool:
    """Short enough to be a title, long enough to be one, and made of letters.

    The letter floor is what keeps an OCR layer's ``____________ ã`` -- bold
    because the scan's rule was read as bold text -- from becoming a chapter
    title (Karpov, p. 61).
    """
    stripped = text.strip()
    if not _MIN_HEADING_CHARS <= len(stripped) <= config.heading_max_chars:
        return False
    return sum(1 for ch in stripped if ch.isalpha()) >= _MIN_HEADING_LETTERS


def assign_heading_levels(
    blocks: Sequence[BlockDraft], body_size: float, config: ParagraphConfig
) -> dict[float, int]:
    """Rank the heading sizes and turn the largest into level 1, and so on.

    A block the layout called a heading but whose size is not above the body
    (a bold run-in, a short line) is demoted back to a paragraph: size is the
    evidence for a level, and without it there is none.
    """
    candidates: dict[float, int] = {}
    run_in: list[BlockDraft] = []
    for block in blocks:
        if block.kind is not RegionKind.HEADING or block.is_empty:
            continue
        if not _heading_len_ok(block.text, config):
            block.kind = RegionKind.PARAGRAPH
            continue
        if body_size > 0 and block.size < body_size * config.heading_ratio:
            inked = [s for s in block.spans if s.text.strip() and s.text != _IMAGE_PLACEHOLDER]
            if inked and all(s.bold for s in inked):
                run_in.append(block)
            else:
                block.kind = RegionKind.PARAGRAPH
            continue
        key = round(block.size, _ROUND_SIZE)
        candidates[key] = candidates.get(key, 0) + 1
    ranked = sorted(candidates, reverse=True)[:_MAX_HEADING_LEVELS]
    levels = {size: i + 1 for i, size in enumerate(ranked)}
    # Bold run-in heads at the body size sit one level below the smallest
    # ranked size: they are the deepest heads the book has.
    run_in_level = min(len(levels) + 1, _MAX_HEADING_LEVELS)
    for block in blocks:
        if block.kind is RegionKind.HEADING:
            block.heading_level = levels.get(round(block.size, _ROUND_SIZE), run_in_level)
    for block in run_in:
        block.heading_level = run_in_level
    return levels


def promote_bold_headings(
    blocks: Sequence[BlockDraft], body_size: float, config: ParagraphConfig
) -> int:
    """A short, one-row, all-bold block at body size is a run-in heading.

    Size ranking cannot see it: the Dvoretsky sets ``Tragicomedies`` and
    ``Exercises`` in bold italic at the body size, and they came out as
    paragraphs (or, next to a diagram, as captions).  Move text is excluded
    -- a bold ``1.Bb1!!`` is a main line, not a title -- and so is anything
    that looks like a caption opener.  Returns how many were promoted.
    """
    promoted = 0
    for block in blocks:
        if block.kind not in (RegionKind.PARAGRAPH, RegionKind.CAPTION) or block.rows != 1:
            continue
        text = block.text.strip()
        if not _heading_len_ok(text, config) or _CAPTION_RE.match(text):
            continue
        if looks_like_moves(text) or text[-1] in ".,;:":
            continue
        inked = [s for s in block.spans if s.text.strip() and s.text != _IMAGE_PLACEHOLDER]
        if not inked or not all(s.bold for s in inked):
            continue
        if body_size > 0 and block.size < body_size * _RUN_IN_MIN_SIZE:
            continue
        block.kind = RegionKind.HEADING
        promoted += 1
    return promoted


def _norm_title(text: str) -> str:
    text = text.replace("–", "-").replace("—", "-").replace("�", "-")
    text = re.sub(r"[^0-9a-zÀ-ɏЀ-ӿ]+", " ", text.lower())
    return _WS.sub(" ", text).strip()


def attach_outline(blocks: Sequence[BlockDraft], outline: Sequence[OutlineEntry]) -> int:
    """Point each PDF bookmark at the block that carries its title.

    Bookmarks can land a page early or late, so a small window is searched.
    A matched paragraph becomes a heading at the bookmark's level; a matched
    heading takes the bookmark's level, which is the author's word over a
    size ranking.  Returns how many entries were attached.
    """
    if not outline:
        return 0
    by_page: dict[int, list[int]] = {}
    for index, block in enumerate(blocks):
        by_page.setdefault(block.first_page, []).append(index)
    used: set[int] = set()
    attached = 0
    for entry in outline:
        if entry.page_index < 0:
            continue
        want = _norm_title(entry.title)
        if not want:
            continue
        best: int | None = None
        for probe in (entry.page_index, entry.page_index + 1, entry.page_index - 1):
            for index in by_page.get(probe, []):
                block = blocks[index]
                if index in used or block.kind not in (RegionKind.PARAGRAPH, RegionKind.HEADING):
                    continue
                got = _norm_title(block.text)
                if not got:
                    continue
                if got == want or (len(want) > 3 and (want in got or got in want)):  # noqa: PLR2004 - three letters is a word
                    best = index
                    break
            if best is not None:
                break
        if best is None:
            continue
        used.add(best)
        block = blocks[best]
        block.kind = RegionKind.HEADING
        block.heading_level = min(max(1, entry.level), _MAX_HEADING_LEVELS)
        block.outline_title = entry.title
        attached += 1
    return attached


def tag_captions(blocks: Sequence[BlockDraft], figure_pages: Mapping[int, int]) -> None:
    """An italic one-liner right after a figure, or a "Position after", is a caption.

    ``figure_pages`` maps a page index to how many figures it carries -- the
    check is cheap and only for blocks on pages that have something to caption.
    """
    for block in blocks:
        if block.kind is not RegionKind.PARAGRAPH or block.rows > 2:  # noqa: PLR2004 - a caption is a line or two
            continue
        text = block.text.strip()
        if not text or len(text) > _MAX_CAPTION_CHARS:
            continue
        if _CAPTION_RE.match(text):
            block.kind = RegionKind.CAPTION
            continue
        if figure_pages.get(block.first_page, 0) == 0:
            continue
        inked = [s for s in block.spans if s.text.strip() and s.text != _IMAGE_PLACEHOLDER]
        if inked and all(s.italic for s in inked):
            block.kind = RegionKind.CAPTION


def tag_movetext(blocks: Sequence[BlockDraft]) -> None:
    for block in blocks:
        if block.kind is RegionKind.PARAGRAPH and looks_like_moves(block.text.strip()):
            block.kind = RegionKind.MOVETEXT


_STYLE_OF: Final[Mapping[RegionKind, str]] = {
    RegionKind.PARAGRAPH: "Body",
    RegionKind.CAPTION: "Caption",
    RegionKind.FOOTNOTE: "Footnote",
    RegionKind.MOVETEXT: "Movetext",
}


def finish_document(
    blocks: Sequence[BlockDraft],
    *,
    body_size: float,
    outline: Sequence[OutlineEntry] = (),
    figure_pages: Mapping[int, int] | None = None,
    config: ParagraphConfig | None = None,
) -> dict[str, int]:
    """Document-level passes: heading levels, outline, captions, move text, styles.

    Returns counters for the import report.
    """
    config = config or ParagraphConfig()
    promoted = promote_bold_headings(blocks, body_size, config)
    levels = assign_heading_levels(blocks, body_size, config)
    attached = attach_outline(blocks, outline)
    tag_captions(blocks, figure_pages or {})
    tag_movetext(blocks)
    for block in blocks:
        if block.kind is RegionKind.HEADING:
            block.style = f"Heading {block.heading_level or _MAX_HEADING_LEVELS}"
        else:
            block.style = _STYLE_OF.get(block.kind, "Body")
    return {
        "heading_sizes": len(levels),
        "run_in_headings": promoted,
        "outline_attached": attached,
        "headings": sum(1 for b in blocks if b.kind is RegionKind.HEADING),
        "captions": sum(1 for b in blocks if b.kind is RegionKind.CAPTION),
        "footnotes": sum(1 for b in blocks if b.kind is RegionKind.FOOTNOTE),
        "movetext": sum(1 for b in blocks if b.kind is RegionKind.MOVETEXT),
        "paragraphs": sum(1 for b in blocks if b.kind is RegionKind.PARAGRAPH),
    }
