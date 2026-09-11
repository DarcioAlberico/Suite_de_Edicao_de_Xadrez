"""Page layout analysis: columns, reading order, furniture, footnotes, captions.

The input is deliberately engine-agnostic.  Both the PDF text layer and every
OCR engine produce lines with boxes and text, so this module takes
:class:`LayoutLine` and never learns which produced it — otherwise the layout
rules would have to be written twice and would drift apart.

What it decides, in order:

1.  **Body size** — the font size most of the page's characters are set in.
    Everything else is measured against it.
2.  **Diagram exclusion** — text inside a detected chess diagram is coordinate
    labels ("a".."h", "1".."8") and piece glyphs, not prose.  Letting it into
    the body text produces sentences with "abcdefgh" in the middle of them,
    which is both wrong and unfixable later, because by then the geometry that
    proved it was a label has been discarded.
3.  **Running furniture** — headers, footers and page numbers, detected across
    pages by fingerprint repetition rather than by position alone.
4.  **Footnotes** — a contiguous, smaller-set run at the foot of the page.
5.  **Columns** — from a whitespace-gutter histogram that ignores lines wide
    enough to be spanning headings.
6.  **Reading order** — recursive XY-cut, which handles the case columns alone
    cannot: a headline spanning both columns, with two columns beneath it.
7.  **Captions** — short lines adjacent to a figure or diagram, bound to it.

``_fingerprint`` and ``_is_page_number`` are ported from
``PDFimport/PDFImport_v1.2.0/PDFImport/extract.py``, absorbed 2026-09-07.
Changes: none to the logic — the digit-masking fingerprint is exactly right and
is the reason "Chapter 3 - page 41" and "Chapter 3 - page 42" collapse to one
pattern.  The surrounding scan is rewritten because the original walks a
PyMuPDF page directly, while this one must also accept OCR output; the
``repeat_frac`` / ``margin_frac`` policy and the ``max(3, ...)`` floor are kept
because they are tuned and because three repetitions is genuinely the smallest
number that means anything.

The observation behind ``_page_rows`` in the original — *a block is not a
paragraph* — is honoured here too: lines are grouped into rows and paragraphs by
geometry across the whole page, never by trusting the producer's own block
boundaries, because both PDF writers and OCR engines start a new block wherever
an inline image interrupts a line.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from ..types import BBox, OcrResult, RegionKind

__all__ = [
    "LayoutLine",
    "LayoutInput",
    "LayoutRegion",
    "Column",
    "PageLayout",
    "LayoutConfig",
    "RunningFurnitureDetector",
    "analyze_page",
    "detect_columns",
    "reading_order",
    "lines_from_result",
    "fingerprint",
    "is_page_number",
]


# --------------------------------------------------------------------------- #
# Ported helpers
# --------------------------------------------------------------------------- #

_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")
_ROMAN_ONLY = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)


def fingerprint(text: str) -> str:
    """Normalise a line so 'Chapter 1 - page 12' and '... page 13' match.

    Ported verbatim from ``PDFimport/extract.py::_fingerprint``.
    """
    return _WS.sub(" ", _DIGITS.sub("#", text.strip())).lower()


def is_page_number(text: str) -> bool:
    """True for a line that is nothing but a page number.

    Ported from ``PDFimport/extract.py::_is_page_number``.  Empty text counts as
    a page number, which is correct at the call site: an empty line in the
    margin is furniture either way.
    """
    t = text.strip().strip("[](){}.–—- ")
    if not t:
        return True
    return t.isdigit() or bool(_ROMAN_ONLY.match(t))


#: Words that open a caption in the supported languages.  Only a hint — a
#: caption is identified by geometry first and by wording second.
_CAPTION_OPENERS = re.compile(
    r"^\s*(?:diagrama|diagram|diagramm|diagrama|fig\.?|figura|figure|abb\.?"
    r"|abbildung|tabela|table|tabelle|quadro|posição|position|stellung"
    r"|диаграмма|рис\.?)\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Input / output types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LayoutLine:
    """One text line, from whatever produced it."""

    box: BBox
    text: str
    font_size: float = 0.0
    confidence: float = 1.0
    #: The producer's own object, carried through untouched.
    source: Any = None

    @property
    def height(self) -> float:
        return self.box.h if self.box.h > 0 else self.font_size

    @property
    def char_count(self) -> int:
        return len(self.text.strip())


@dataclass(frozen=True, slots=True)
class LayoutInput:
    """Everything known about one page before layout is decided."""

    page_box: BBox
    lines: tuple[LayoutLine, ...]
    #: Raster figures and illustrations.
    figures: tuple[BBox, ...] = ()
    #: Chess diagrams located by the vision front (F3).
    diagrams: tuple[BBox, ...] = ()
    #: Vector rules, when the source is a PDF; used to spot the footnote rule.
    rules: tuple[BBox, ...] = ()
    page_index: int = 0


@dataclass(frozen=True, slots=True)
class Column:
    """A vertical text column."""

    index: int
    box: BBox
    line_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LayoutRegion:
    """A run of consecutive lines that belong together."""

    kind: RegionKind
    box: BBox
    line_indices: tuple[int, ...]
    column_index: int = 0
    reading_order: int = 0
    #: Index into :attr:`LayoutInput.figures` + ``diagrams`` for captions.
    attached_to: int | None = None
    attached_kind: str = ""

    @property
    def in_body(self) -> bool:
        return self.kind.is_prose


@dataclass(frozen=True, slots=True)
class PageLayout:
    """The analysed page."""

    page_box: BBox
    lines: tuple[LayoutLine, ...]
    kinds: tuple[RegionKind, ...]
    regions: tuple[LayoutRegion, ...]
    columns: tuple[Column, ...]
    #: Indices into :attr:`lines`, in the order a human reads them, furniture
    #: and diagram labels removed.
    order: tuple[int, ...]
    body_font_size: float
    notes: tuple[str, ...] = ()
    signals: Mapping[str, Any] = field(default_factory=dict)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def body_text(self) -> str:
        return "\n".join(self.lines[i].text for i in self.order)

    def lines_of_kind(self, kind: RegionKind) -> tuple[LayoutLine, ...]:
        return tuple(line for line, k in zip(self.lines, self.kinds) if k is kind)

    def describe_pt(self) -> str:
        counts = Counter(str(k) for k in self.kinds)
        parts = [f"{self.column_count} coluna(s)",
                 f"corpo em {self.body_font_size:.1f}"]
        for kind, n in sorted(counts.items()):
            parts.append(f"{n} {kind}")
        return "; ".join(parts)


@dataclass(slots=True)
class LayoutConfig:
    """Every tunable, with the reasoning for its default in the comment."""

    #: Fraction of page height at top and bottom searched for furniture.
    margin_frac: float = 0.075
    #: A margin line must repeat on this share of pages to be furniture.
    repeat_frac: float = 0.25
    #: ...but never on fewer than this many pages.  Two repetitions can be a
    #: coincidence; three is a pattern.
    min_repeats: int = 3
    #: A gutter must be at least this fraction of the page width.
    min_gutter_frac: float = 0.022
    #: Share of lines allowed to cross a candidate gutter (spanning headings).
    gutter_cross_tolerance: float = 0.12
    max_columns: int = 4
    #: A line wider than this share of the text block is a spanning line and is
    #: excluded from gutter voting.
    spanning_width_frac: float = 0.62
    #: Footnotes live in the bottom of the page...
    footnote_zone_frac: float = 0.32
    #: ...and are set smaller than the body.
    footnote_size_ratio: float = 0.93
    #: A heading is set larger than the body...
    heading_size_ratio: float = 1.15
    #: ...and is short.
    heading_max_chars: int = 90
    #: A line this much inside a diagram rect is a coordinate label.
    diagram_coverage: float = 0.60
    #: Caption search distance, in multiples of the body line height.
    caption_gap_lines: float = 1.8
    #: Minimum horizontal overlap between a caption and its figure.
    caption_overlap: float = 0.35
    #: Paragraph break when the vertical gap exceeds this many line heights.
    paragraph_gap_lines: float = 1.55
    #: XY-cut stops splitting below this many lines.
    xy_cut_min_lines: int = 2


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #


def lines_from_result(result: OcrResult) -> tuple[LayoutLine, ...]:
    """Turn an :class:`OcrResult` into layout input."""
    return tuple(
        LayoutLine(box=line.box, text=line.text,
                   font_size=line.font_size or line.box.h,
                   confidence=line.confidence, source=line)
        for line in result.lines
        if line.text.strip()
    )


def lines_from_pdf_page(page: Any, *, scale: float = 1.0) -> tuple[LayoutLine, ...]:
    """Layout input straight from a PyMuPDF page, bypassing OCR."""
    out: list[LayoutLine] = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", []))
            if not text.strip():
                continue
            size = max((s.get("size", 0.0) for s in line.get("spans", [])),
                       default=0.0)
            out.append(LayoutLine(
                box=BBox.from_edges(*(line.get("bbox") or (0, 0, 0, 0))).scaled(scale),
                text=text, font_size=size * scale, source=line,
            ))
    return tuple(out)


# --------------------------------------------------------------------------- #
# Running furniture
# --------------------------------------------------------------------------- #


class RunningFurnitureDetector:
    """Finds headers, footers and page numbers across a document.

    Position alone is not enough — the first line of a chapter also sits at the
    top of the page — so the test is *repetition of a digit-masked fingerprint*
    in the margin band, which is what makes "Chapter 3 · 41" and "Chapter 3 · 42"
    the same piece of furniture.

    Usage is two-pass: :meth:`observe` every page, :meth:`finalize`, then
    :meth:`classify` each line.  Single-page callers can use
    :meth:`classify_single_page`, which falls back to the position-and-shape
    rules alone and says so.
    """

    def __init__(self, config: LayoutConfig | None = None) -> None:
        self.config = config or LayoutConfig()
        self._counts: Counter[str] = Counter()
        self._pages = 0
        self._repeated: frozenset[str] = frozenset()
        self._finalized = False
        #: Where bare numbers sit in the margin band, as a fraction of the
        #: page width, rounded to a twentieth: a folio lives at one, two or
        #: three fixed positions across a book.
        self._folio_slots: Counter[int] = Counter()
        self._folio_positions: frozenset[int] = frozenset()

    @property
    def pages_observed(self) -> int:
        return self._pages

    @property
    def repeated_patterns(self) -> frozenset[str]:
        return self._repeated

    def observe(self, lines: Sequence[LayoutLine], page_box: BBox) -> None:
        self._pages += 1
        self._finalized = False
        top, bottom = self._margins(page_box)
        seen: set[str] = set()
        for line in lines:
            if not self._in_margin(line, top, bottom):
                continue
            text = line.text.strip()
            if not text:
                continue
            if is_page_number(text):
                self._folio_slots[self._slot(line, page_box)] += 1
            key = fingerprint(text)
            # Count a pattern once per page: a page listing the same running
            # head twice must not vote twice.
            if key not in seen:
                seen.add(key)
                self._counts[key] += 1

    def finalize(self) -> frozenset[str]:
        threshold = max(self.config.min_repeats,
                        int(self._pages * self.config.repeat_frac))
        self._repeated = frozenset(k for k, n in self._counts.items()
                                   if n >= threshold)
        self._folio_positions = frozenset(
            slot for slot, n in self._folio_slots.items() if n >= threshold
        )
        self._finalized = True
        return self._repeated

    @staticmethod
    def _slot(line: LayoutLine, page_box: BBox) -> int:
        """The line's horizontal position as a twentieth of the page width."""
        width = page_box.w or 1.0
        return int(round((line.box.cx - page_box.x0) / width * 20))

    def _is_folio_here(self, line: LayoutLine, page_box: BBox) -> bool:
        """A bare number in the band is the folio only where the book prints it.

        A folio sits at the same one, two or three positions on every page.
        A bare number elsewhere in the band -- the ``22`` of a tabular move
        line that happens to fall in the bottom 7,5 % of a Chernev page -- is
        text.  With no positional evidence yet (a single page) position is
        not held against it.
        """
        if not self._folio_positions:
            # Enough pages seen and no position ever repeated: the book has
            # no folio in the band, so a bare number there is text.  Too few
            # pages to know: position is not held against it.
            return self._pages < self.config.min_repeats
        slot = self._slot(line, page_box)
        return any(abs(slot - known) <= 1 for known in self._folio_positions)

    def _margins(self, page_box: BBox) -> tuple[float, float]:
        band = page_box.h * self.config.margin_frac
        return page_box.y0 + band, page_box.y1 - band

    @staticmethod
    def _in_margin(line: LayoutLine, top: float, bottom: float) -> bool:
        return line.box.y1 <= top or line.box.y0 >= bottom

    def classify(self, line: LayoutLine, page_box: BBox) -> RegionKind | None:
        """``HEADER`` / ``FOOTER`` / ``PAGE_NUMBER``, or ``None`` for body."""
        if not self._finalized:
            self.finalize()
        top, bottom = self._margins(page_box)
        if not self._in_margin(line, top, bottom):
            return None
        text = line.text.strip()
        if not text:
            return None
        in_header = line.box.y1 <= top
        if is_page_number(text):
            return RegionKind.PAGE_NUMBER if self._is_folio_here(line, page_box) else None
        if fingerprint(text) in self._repeated:
            return RegionKind.HEADER if in_header else RegionKind.FOOTER
        return None

    def classify_single_page(self, line: LayoutLine,
                             page_box: BBox) -> RegionKind | None:
        """Best effort for a page with no document context.

        Only a bare page number can be identified without repetition evidence;
        guessing at running heads from one page removes chapter openings.
        """
        top, bottom = self._margins(page_box)
        if not self._in_margin(line, top, bottom):
            return None
        if is_page_number(line.text):
            return RegionKind.PAGE_NUMBER
        return None


# --------------------------------------------------------------------------- #
# Columns
# --------------------------------------------------------------------------- #


def _text_span(lines: Sequence[LayoutLine], page_box: BBox) -> tuple[float, float]:
    if not lines:
        return page_box.x0, page_box.x1
    return (min(l.box.x0 for l in lines), max(l.box.x1 for l in lines))


def detect_columns(lines: Sequence[LayoutLine], page_box: BBox,
                   config: LayoutConfig | None = None) -> list[Column]:
    """Split the page into columns at whitespace gutters.

    The histogram counts, for each horizontal position, how many lines cover it.
    A gutter is a wide run of positions that almost no line crosses.  "Almost"
    is the important word: a two-column page with a spanning headline has *no*
    position that zero lines cross, and a strict rule finds one column and puts
    the page into the wrong reading order.  Lines wide enough to be spanning are
    therefore excluded from voting, and a small crossing tolerance remains for
    the stragglers.
    """
    config = config or LayoutConfig()
    body = [l for l in lines if l.text.strip()]
    if len(body) < 4:
        return [Column(0, page_box, tuple(range(len(lines))))]

    left, right = _text_span(body, page_box)
    width = right - left
    if width <= 0:
        return [Column(0, page_box, tuple(range(len(lines))))]

    voters = [l for l in body
              if l.box.w <= config.spanning_width_frac * width]
    if len(voters) < 4:
        voters = body

    bins = max(64, min(2048, int(width)))
    scale = bins / width
    coverage = [0] * bins
    for line in voters:
        start = max(0, min(bins - 1, int((line.box.x0 - left) * scale)))
        stop = max(start + 1, min(bins, int(math.ceil((line.box.x1 - left) * scale))))
        for i in range(start, stop):
            coverage[i] += 1

    allowed = config.gutter_cross_tolerance * len(voters)
    min_gutter_bins = max(2, int(config.min_gutter_frac * bins
                                 * (page_box.w / width if width else 1.0)))

    gutters: list[tuple[int, int]] = []
    run_start: int | None = None
    for i, value in enumerate(coverage):
        if value <= allowed:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start >= min_gutter_bins:
                gutters.append((run_start, i))
            run_start = None
    if run_start is not None and bins - run_start >= min_gutter_bins:
        gutters.append((run_start, bins))

    # Gutters touching the page edge are margins, not column separators.
    interior = [(a, b) for a, b in gutters if a > 0 and b < bins]
    if not interior:
        return [Column(0, BBox.from_edges(left, page_box.y0, right, page_box.y1),
                       tuple(range(len(lines))))]

    interior.sort(key=lambda g: g[1] - g[0], reverse=True)
    interior = sorted(interior[: config.max_columns - 1])

    edges = [0.0]
    for a, b in interior:
        edges.append(left + (a + b) / 2.0 / scale)
    edges[0] = left
    edges.append(right)

    columns: list[Column] = []
    spanning_width = config.spanning_width_frac * width
    for index in range(len(edges) - 1):
        x0, x1 = edges[index], edges[index + 1]
        members = [
            i for i, line in enumerate(lines)
            if line.text.strip()
            # A line wider than a column belongs to no column: it spans them.
            # Assigning it by its centre puts a two-column headline inside
            # whichever column happens to contain its midpoint, and the
            # paragraph grouper then glues it to that column's first paragraph.
            and line.box.w <= spanning_width
            and x0 - 1e-6 <= line.box.cx <= x1 + 1e-6
        ]
        if not members:
            continue
        columns.append(Column(
            index=len(columns),
            box=BBox.from_edges(x0, page_box.y0, x1, page_box.y1),
            line_indices=tuple(members),
        ))
    if not columns:
        return [Column(0, BBox.from_edges(left, page_box.y0, right, page_box.y1),
                       tuple(range(len(lines))))]
    return columns


# --------------------------------------------------------------------------- #
# Reading order (recursive XY-cut)
# --------------------------------------------------------------------------- #


def _largest_gap(intervals: Sequence[tuple[float, float]],
                 lo: float, hi: float) -> tuple[float, float, float]:
    """Widest empty span in ``[lo, hi]`` not covered by ``intervals``.

    Returns ``(gap_start, gap_end, width)``; width 0 when there is none.
    """
    if not intervals:
        return lo, hi, hi - lo
    ordered = sorted(intervals)
    best = (0.0, 0.0, 0.0)
    cursor = lo
    for start, end in ordered:
        if start - cursor > best[2]:
            best = (cursor, start, start - cursor)
        cursor = max(cursor, end)
    if hi - cursor > best[2]:
        best = (cursor, hi, hi - cursor)
    return best


def reading_order(lines: Sequence[LayoutLine], indices: Sequence[int],
                  page_box: BBox,
                  config: LayoutConfig | None = None) -> list[int]:
    """Order ``indices`` the way a human reads the page.

    Recursive XY-cut.  At each step the widest horizontal band of whitespace
    and the widest vertical band are measured; whichever is more decisively
    above its own minimum wins, the group is split there, and the halves are
    recursed into — top before bottom, left before right.

    This is why a spanning headline over two columns comes out right: the
    horizontal band under the headline is the most decisive cut on the page, so
    it happens first, and the two columns are only discovered inside the block
    beneath it.  A pure column-then-vertical-sort ordering puts the headline
    into whichever column it overlaps most and reads it in the middle of the
    text.
    """
    config = config or LayoutConfig()
    order: list[int] = []
    _xy_cut(lines, list(indices), page_box, config, order, depth=0)
    return order


def _xy_cut(lines: Sequence[LayoutLine], indices: list[int], box: BBox,
            config: LayoutConfig, out: list[int], depth: int) -> None:
    if not indices:
        return
    if len(indices) < config.xy_cut_min_lines or depth > 12:
        out.extend(sorted(indices,
                          key=lambda i: (lines[i].box.y0, lines[i].box.x0)))
        return

    boxes = [lines[i].box for i in indices]
    heights = sorted(b.h for b in boxes if b.h > 0)
    line_h = heights[len(heights) // 2] if heights else 1.0
    x_lo = min(b.x0 for b in boxes)
    x_hi = max(b.x1 for b in boxes)
    y_lo = min(b.y0 for b in boxes)
    y_hi = max(b.y1 for b in boxes)

    h_start, h_end, h_width = _largest_gap(
        [(b.y0, b.y1) for b in boxes], y_lo, y_hi)
    v_start, v_end, v_width = _largest_gap(
        [(b.x0, b.x1) for b in boxes], x_lo, x_hi)

    min_h = max(1e-6, config.paragraph_gap_lines * line_h)
    min_v = max(1e-6, config.min_gutter_frac * box.w)

    h_score = h_width / min_h
    v_score = v_width / min_v

    # A vertical cut must be clearly better than a horizontal one to be taken:
    # splitting a single column of prose down the middle because its ragged
    # right edge left a gap is the classic XY-cut failure.
    if v_score > 1.0 and v_score > h_score * 1.25:
        cut = (v_start + v_end) / 2.0
        left = [i for i in indices if lines[i].box.cx <= cut]
        right = [i for i in indices if lines[i].box.cx > cut]
        if left and right:
            _xy_cut(lines, left, box, config, out, depth + 1)
            _xy_cut(lines, right, box, config, out, depth + 1)
            return

    if h_score > 1.0:
        cut = (h_start + h_end) / 2.0
        top = [i for i in indices if lines[i].box.cy <= cut]
        low = [i for i in indices if lines[i].box.cy > cut]
        if top and low:
            _xy_cut(lines, top, box, config, out, depth + 1)
            _xy_cut(lines, low, box, config, out, depth + 1)
            return

    out.extend(sorted(indices, key=lambda i: (lines[i].box.y0, lines[i].box.x0)))


# --------------------------------------------------------------------------- #
# Body size, footnotes, captions, diagrams
# --------------------------------------------------------------------------- #


def body_font_size(lines: Sequence[LayoutLine]) -> float:
    """The size most of the page's *characters* are set in.

    Weighted by character count, not by line count: a page with twelve one-word
    headings and six long paragraphs has more heading lines than body lines, and
    an unweighted mode would call the heading size the body size.
    """
    weights: Counter[float] = Counter()
    for line in lines:
        size = round(line.font_size or line.box.h, 1)
        if size <= 0:
            continue
        weights[size] += max(1, line.char_count)
    if not weights:
        return 0.0
    return max(weights.items(), key=lambda kv: (kv[1], -kv[0]))[0]


def _classify_diagram_labels(lines: Sequence[LayoutLine],
                             diagrams: Sequence[BBox],
                             config: LayoutConfig) -> dict[int, int]:
    """Line index -> diagram index, for text that sits inside a diagram."""
    out: dict[int, int] = {}
    for i, line in enumerate(lines):
        for d, rect in enumerate(diagrams):
            if line.box.coverage_by(rect) >= config.diagram_coverage:
                out[i] = d
                break
    return out


def _detect_footnotes(lines: Sequence[LayoutLine], page_box: BBox,
                      body_size: float, config: LayoutConfig,
                      excluded: set[int]) -> set[int]:
    """Indices of lines belonging to the footnote zone.

    A footnote block is *contiguous* and *reaches the bottom* of the text.  Both
    conditions matter: a single small line in the middle of the page is a
    caption or an inset, and a small line at the bottom with body-size lines
    below it is not a footnote either.
    """
    if body_size <= 0:
        return set()
    zone_top = page_box.y1 - page_box.h * config.footnote_zone_frac
    max_size = body_size * config.footnote_size_ratio

    candidates = [
        i for i, line in enumerate(lines)
        if i not in excluded and line.text.strip()
    ]
    candidates.sort(key=lambda i: lines[i].box.y0)
    if not candidates:
        return set()

    # Walk upwards from the bottom while the lines stay small and inside zone.
    footnotes: set[int] = set()
    for i in reversed(candidates):
        line = lines[i]
        size = line.font_size or line.box.h
        if line.box.y0 < zone_top:
            break
        if size > max_size:
            break
        footnotes.add(i)
    # One stray small line at the very bottom is a page number or a folio, not
    # a footnote block; require either two lines or a rule above it.
    if len(footnotes) < 2:
        return set()
    return footnotes


def _associate_captions(lines: Sequence[LayoutLine],
                        anchors: Sequence[tuple[str, int, BBox]],
                        body_size: float, config: LayoutConfig,
                        excluded: set[int]) -> dict[int, tuple[str, int]]:
    """Line index -> ``(anchor_kind, anchor_index)`` for caption lines.

    A caption is short, sits close to a figure, overlaps it horizontally, and is
    not larger than the body text.  Below beats above, because that is where
    captions overwhelmingly are; wording is only a tie-breaker, so a caption
    that does not begin with "Diagrama" is still found.
    """
    out: dict[int, tuple[str, int]] = {}
    if not anchors:
        return out
    heights = sorted(l.box.h for l in lines if l.box.h > 0)
    line_h = heights[len(heights) // 2] if heights else (body_size or 10.0)
    reach = config.caption_gap_lines * line_h

    for i, line in enumerate(lines):
        if i in excluded or not line.text.strip():
            continue
        size = line.font_size or line.box.h
        if body_size > 0 and size > body_size * 1.02:
            continue
        best: tuple[float, str, int] | None = None
        for kind, index, rect in anchors:
            if line.box.horizontal_overlap(rect) < config.caption_overlap:
                continue
            below = line.box.y0 - rect.y1
            above = rect.y0 - line.box.y1
            if 0 <= below <= reach:
                distance = below
            elif 0 <= above <= reach:
                # Penalise "above" so a caption between two figures binds to
                # the one it follows.
                distance = above + reach * 0.5
            else:
                continue
            if _CAPTION_OPENERS.match(line.text):
                distance *= 0.25
            if best is None or distance < best[0]:
                best = (distance, kind, index)
        if best is not None:
            out[i] = (best[1], best[2])
    return out


def _group_regions(lines: Sequence[LayoutLine], order: Sequence[int],
                   kinds: Sequence[RegionKind], columns: Sequence[Column],
                   config: LayoutConfig) -> list[LayoutRegion]:
    """Merge consecutive same-kind lines into paragraph-level regions.

    The break rules are the ones ``PDFimport``'s paragraph builder arrived at:
    a vertical gap wider than a line and a half, a change of kind, or a line
    starting to the right of the region's own left edge (an indent, which books
    use to mark a new paragraph and also to mark nesting — hence comparing
    against the region's edge rather than the page margin).
    """
    #: -1 marks a line that spans the columns rather than sitting in one.
    column_of: dict[int, int] = {}
    for column in columns:
        for i in column.line_indices:
            column_of[i] = column.index

    regions: list[LayoutRegion] = []
    current: list[int] = []
    current_kind: RegionKind | None = None
    current_left = 0.0
    previous_bottom: float | None = None
    previous_column = 0

    heights = sorted(l.box.h for l in lines if l.box.h > 0)
    line_h = heights[len(heights) // 2] if heights else 10.0
    indent = max(2.0, 0.6 * line_h)

    def flush() -> None:
        nonlocal current, current_kind
        if current and current_kind is not None:
            regions.append(LayoutRegion(
                kind=current_kind,
                box=BBox.union_of([lines[i].box for i in current]),
                line_indices=tuple(current),
                column_index=column_of.get(current[0], -1),
                reading_order=len(regions),
            ))
        current = []
        current_kind = None

    for i in order:
        kind = kinds[i]
        line = lines[i]
        column = column_of.get(i, -1)
        start_new = (
            current_kind is None
            or kind is not current_kind
            or column != previous_column
            or (previous_bottom is not None
                and line.box.y0 - previous_bottom
                > config.paragraph_gap_lines * line_h)
            or line.box.x0 > current_left + indent
        )
        if start_new:
            flush()
            current_kind = kind
            current_left = line.box.x0
        current.append(i)
        previous_bottom = line.box.y1
        previous_column = column
    flush()
    return regions


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def analyze_page(page: LayoutInput, *,
                 config: LayoutConfig | None = None,
                 furniture: RunningFurnitureDetector | None = None) -> PageLayout:
    """Full analysis of one page.

    ``furniture`` should be a detector that has already observed the document;
    without one, only bare page numbers are removed and a note says so, because
    guessing at running heads from a single page deletes chapter titles.
    """
    config = config or LayoutConfig()
    lines = list(page.lines)
    notes: list[str] = []
    n = len(lines)
    kinds: list[RegionKind] = [RegionKind.PARAGRAPH] * n
    if n == 0:
        return PageLayout(page.page_box, (), (), (), (), (), 0.0,
                          ("página sem linhas de texto",), {})

    # 1. body size
    body_size = body_font_size(lines)

    # 2. diagram labels — first, so they never vote on anything else
    diagram_labels = _classify_diagram_labels(lines, page.diagrams, config)
    for i in diagram_labels:
        kinds[i] = RegionKind.DIAGRAM_LABEL
    excluded: set[int] = set(diagram_labels)

    # 3. running furniture
    if furniture is None:
        detector = RunningFurnitureDetector(config)
        for i, line in enumerate(lines):
            if i in excluded:
                continue
            kind = detector.classify_single_page(line, page.page_box)
            if kind is not None:
                kinds[i] = kind
                excluded.add(i)
        notes.append(
            "cabeçalhos e rodapés não foram detectados: é necessário observar "
            "várias páginas antes de decidir o que se repete."
        )
    else:
        for i, line in enumerate(lines):
            if i in excluded:
                continue
            kind = furniture.classify(line, page.page_box)
            if kind is not None:
                kinds[i] = kind
                excluded.add(i)

    # 4. footnotes
    footnotes = _detect_footnotes(lines, page.page_box, body_size, config,
                                  excluded)
    for i in footnotes:
        kinds[i] = RegionKind.FOOTNOTE

    # 5. headings
    if body_size > 0:
        for i, line in enumerate(lines):
            if i in excluded or i in footnotes:
                continue
            size = line.font_size or line.box.h
            text = line.text.strip()
            if (size >= body_size * config.heading_size_ratio
                    and 3 <= len(text) <= config.heading_max_chars):
                kinds[i] = RegionKind.HEADING

    # 6. captions
    anchors: list[tuple[str, int, BBox]] = []
    anchors += [("figure", i, r) for i, r in enumerate(page.figures)]
    anchors += [("diagram", i, r) for i, r in enumerate(page.diagrams)]
    captions = _associate_captions(lines, anchors, body_size, config,
                                   excluded | footnotes)
    for i in captions:
        if kinds[i] in (RegionKind.PARAGRAPH, RegionKind.HEADING):
            kinds[i] = RegionKind.CAPTION

    # 7. columns and reading order, over body lines only
    body_indices = [i for i in range(n)
                    if i not in excluded and lines[i].text.strip()]
    columns = detect_columns([lines[i] for i in body_indices],
                             page.page_box, config)
    # detect_columns indexes into the subset; map back to page indices.
    columns = [
        Column(index=c.index, box=c.box,
               line_indices=tuple(body_indices[j] for j in c.line_indices
                                  if j < len(body_indices)))
        for c in columns
    ]
    order = reading_order(lines, body_indices, page.page_box, config)

    # 8. regions
    regions = _group_regions(lines, order, kinds, columns, config)
    for i, (kind, anchor) in captions.items():
        for r, region in enumerate(regions):
            if i in region.line_indices and region.kind is RegionKind.CAPTION:
                regions[r] = LayoutRegion(
                    kind=region.kind, box=region.box,
                    line_indices=region.line_indices,
                    column_index=region.column_index,
                    reading_order=region.reading_order,
                    attached_to=anchor, attached_kind=kind,
                )
                break

    signals = {
        "line_count": n,
        "body_lines": len(body_indices),
        "columns": len(columns),
        "diagram_labels": len(diagram_labels),
        "footnotes": len(footnotes),
        "captions": len(captions),
        "furniture": sum(1 for k in kinds if k.is_furniture),
        "body_font_size": body_size,
    }
    return PageLayout(
        page_box=page.page_box,
        lines=tuple(lines),
        kinds=tuple(kinds),
        regions=tuple(regions),
        columns=tuple(columns),
        order=tuple(order),
        body_font_size=body_size,
        notes=tuple(notes),
        signals=signals,
    )


def analyze_document(pages: Iterable[LayoutInput],
                     config: LayoutConfig | None = None) -> list[PageLayout]:
    """Two-pass analysis: observe every page, then classify every page.

    This is the entry point real callers want.  The single-page function exists
    for tests and for the interactive inspector, where only one page is loaded.
    """
    config = config or LayoutConfig()
    materialised = list(pages)
    detector = RunningFurnitureDetector(config)
    for page in materialised:
        detector.observe(page.lines, page.page_box)
    detector.finalize()
    return [analyze_page(page, config=config, furniture=detector)
            for page in materialised]
