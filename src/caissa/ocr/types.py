"""Core data types shared by every OCR engine, the layout analyser and the arbiter.

The single most important design decision here is that an OCR result is *not* a
string.  The notation post-corrector (F6) needs to know which pixels produced
which character in order to re-cut a token such as ``Kf3`` into ``Nf3``; the
arbiter needs per-word confidence to decide whether to escalate; the layout
analyser needs baselines to rebuild paragraphs.  A flat string throws all three
away, so :class:`OcrResult` keeps the full hierarchy

    result -> block -> paragraph -> line -> word -> character

with a bounding box and a confidence at every level that has one.

Coordinates are floats in the pixel space of the image that was handed to the
engine.  When the source is a PDF text layer the caller supplies the scale that
converts PDF points to that same pixel space, so downstream code never has to
care which engine produced a box.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterator, Mapping, Sequence

__all__ = [
    "BBox",
    "RegionKind",
    "OcrChar",
    "OcrWord",
    "OcrLine",
    "OcrResult",
    "TextRegion",
    "empty_result",
]


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class BBox:
    """An axis-aligned rectangle in image pixel space.

    Stored as origin plus size because that is what every OCR engine emits;
    the ``x1``/``y1`` edges are derived.  Width and height are clamped to be
    non-negative so a degenerate box from a misbehaving engine cannot produce
    negative areas that silently corrupt IoU scores.
    """

    x: float
    y: float
    w: float
    h: float

    def __post_init__(self) -> None:
        if self.w < 0.0:
            object.__setattr__(self, "w", 0.0)
        if self.h < 0.0:
            object.__setattr__(self, "h", 0.0)

    # -- derived edges ----------------------------------------------------- #

    @property
    def x0(self) -> float:
        return self.x

    @property
    def y0(self) -> float:
        return self.y

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0

    # -- constructors ------------------------------------------------------ #

    @classmethod
    def from_edges(cls, x0: float, y0: float, x1: float, y1: float) -> "BBox":
        """Build from two corners, tolerating a swapped pair."""
        lo_x, hi_x = (x0, x1) if x0 <= x1 else (x1, x0)
        lo_y, hi_y = (y0, y1) if y0 <= y1 else (y1, y0)
        return cls(lo_x, lo_y, hi_x - lo_x, hi_y - lo_y)

    @classmethod
    def union_of(cls, boxes: Sequence["BBox"]) -> "BBox":
        """Smallest box containing every input box; empty box when given none."""
        if not boxes:
            return cls(0.0, 0.0, 0.0, 0.0)
        x0 = min(b.x0 for b in boxes)
        y0 = min(b.y0 for b in boxes)
        x1 = max(b.x1 for b in boxes)
        y1 = max(b.y1 for b in boxes)
        return cls.from_edges(x0, y0, x1, y1)

    # -- relations --------------------------------------------------------- #

    def intersection(self, other: "BBox") -> "BBox":
        x0 = max(self.x0, other.x0)
        y0 = max(self.y0, other.y0)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)
        if x1 <= x0 or y1 <= y0:
            return BBox(x0, y0, 0.0, 0.0)
        return BBox(x0, y0, x1 - x0, y1 - y0)

    def iou(self, other: "BBox") -> float:
        inter = self.intersection(other).area
        if inter <= 0.0:
            return 0.0
        union = self.area + other.area - inter
        return inter / union if union > 0.0 else 0.0

    def coverage_by(self, other: "BBox") -> float:
        """Fraction of *this* box that lies inside ``other``.

        This is the right question for diagram exclusion: a coordinate label is
        small and fully inside the diagram, so its coverage is ~1.0 even though
        the IoU against the whole diagram rect is tiny.
        """
        if self.area <= 0.0:
            return 0.0
        return self.intersection(other).area / self.area

    def horizontal_overlap(self, other: "BBox") -> float:
        """Overlap along x as a fraction of the narrower box."""
        lo = max(self.x0, other.x0)
        hi = min(self.x1, other.x1)
        if hi <= lo:
            return 0.0
        narrow = min(self.w, other.w)
        return (hi - lo) / narrow if narrow > 0.0 else 0.0

    def vertical_overlap(self, other: "BBox") -> float:
        """Overlap along y as a fraction of the shorter box."""
        lo = max(self.y0, other.y0)
        hi = min(self.y1, other.y1)
        if hi <= lo:
            return 0.0
        short = min(self.h, other.h)
        return (hi - lo) / short if short > 0.0 else 0.0

    # -- transforms -------------------------------------------------------- #

    def scaled(self, sx: float, sy: float | None = None) -> "BBox":
        sy = sx if sy is None else sy
        return BBox(self.x * sx, self.y * sy, self.w * sx, self.h * sy)

    def translated(self, dx: float, dy: float) -> "BBox":
        return BBox(self.x + dx, self.y + dy, self.w, self.h)

    def expanded(self, margin: float) -> "BBox":
        return BBox(self.x - margin, self.y - margin,
                    self.w + 2.0 * margin, self.h + 2.0 * margin)

    def clipped_to(self, bounds: "BBox") -> "BBox":
        return self.intersection(bounds)

    def to_int_tuple(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` rounded outwards, for slicing a numpy array."""
        x0 = int(math.floor(self.x0))
        y0 = int(math.floor(self.y0))
        x1 = int(math.ceil(self.x1))
        y1 = int(math.ceil(self.y1))
        return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


# --------------------------------------------------------------------------- #
# Region taxonomy
# --------------------------------------------------------------------------- #


class RegionKind(StrEnum):
    """What a region is, which drives both the page-segmentation hint given to
    the engine and how the layout analyser treats the text afterwards."""

    PAGE = "page"
    COLUMN = "column"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    TABLE = "table"
    MOVETEXT = "movetext"
    DIAGRAM_LABEL = "diagram_label"
    SINGLE_LINE = "single_line"
    SINGLE_WORD = "single_word"
    SPARSE = "sparse"
    VERTICAL = "vertical"
    UNKNOWN = "unknown"

    @property
    def is_prose(self) -> bool:
        """True when the region carries running text destined for the IR body."""
        return self in {
            RegionKind.PARAGRAPH,
            RegionKind.HEADING,
            RegionKind.CAPTION,
            RegionKind.FOOTNOTE,
            RegionKind.MOVETEXT,
            RegionKind.COLUMN,
            RegionKind.PAGE,
            RegionKind.SINGLE_LINE,
        }

    @property
    def is_furniture(self) -> bool:
        """True for repeated page furniture that must not enter the body text."""
        return self in {
            RegionKind.HEADER,
            RegionKind.FOOTER,
            RegionKind.PAGE_NUMBER,
        }


# --------------------------------------------------------------------------- #
# Recognition results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class OcrChar:
    """One recognised character with its own box.

    ``confidence`` is inherited from the parent word when the engine does not
    report per-character confidence (Tesseract's hOCR does not), which is
    flagged by ``inherited_confidence`` so that callers never mistake an
    inherited number for a measured one.
    """

    text: str
    box: BBox
    confidence: float = 0.0
    inherited_confidence: bool = True


@dataclass(frozen=True, slots=True)
class OcrWord:
    """One recognised word.

    ``block_index`` / ``paragraph_index`` / ``line_index`` mirror the engine's
    own segmentation so that the grouping survives round trips even when a
    caller flattens the result.
    """

    text: str
    box: BBox
    confidence: float
    chars: tuple[OcrChar, ...] = ()
    block_index: int = 0
    paragraph_index: int = 0
    line_index: int = 0
    word_index: int = 0

    @property
    def has_char_boxes(self) -> bool:
        return len(self.chars) > 0

    def char_box(self, offset: int) -> BBox | None:
        """Box of the character at ``offset`` in :attr:`text`, when known.

        Falls back to a proportional slice of the word box, which is what the
        notation corrector needs in order to point at "the third glyph" even
        for an engine that reports no character boxes at all.
        """
        if not self.text or offset < 0 or offset >= len(self.text):
            return None
        if len(self.chars) == len(self.text):
            return self.chars[offset].box
        share = self.box.w / len(self.text)
        return BBox(self.box.x + share * offset, self.box.y, share, self.box.h)


@dataclass(frozen=True, slots=True)
class OcrLine:
    """One recognised text line.

    ``baseline`` is ``(slope, intercept)`` relative to the *bottom-left* corner
    of :attr:`box`, exactly as hOCR reports it.  Keeping the engine's own
    convention avoids a lossy re-derivation; :meth:`baseline_y_at` converts to
    absolute image coordinates.
    """

    words: tuple[OcrWord, ...]
    box: BBox
    baseline: tuple[float, float] | None = None
    block_index: int = 0
    paragraph_index: int = 0
    line_index: int = 0
    kind: RegionKind = RegionKind.UNKNOWN
    font_size: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words if w.text)

    @property
    def confidence(self) -> float:
        """Length-weighted mean word confidence.

        Weighting by length keeps a stray one-character misread from dragging a
        long, correct line down, and — more importantly — keeps a confident
        one-character word from propping a bad long one up.
        """
        total = 0.0
        weight = 0.0
        for word in self.words:
            n = max(1, len(word.text))
            total += word.confidence * n
            weight += n
        return total / weight if weight else 0.0

    def baseline_y_at(self, x: float) -> float:
        """Absolute y of the baseline under image column ``x``."""
        if self.baseline is None:
            return self.box.y1
        slope, intercept = self.baseline
        return self.box.y1 + intercept + slope * (x - self.box.x0)


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Everything one engine produced for one region.

    ``meta`` is deliberately open: each adapter records what only it knows
    (Tesseract's PSM, the PDF text layer's font list, the arbiter's escalation
    trail) without forcing a union type on every consumer.
    """

    engine: str
    lang: str
    lines: tuple[OcrLine, ...] = ()
    region_kind: RegionKind = RegionKind.UNKNOWN
    duration_s: float = 0.0
    warnings: tuple[str, ...] = ()
    meta: Mapping[str, object] = field(default_factory=dict)

    # -- flattened views --------------------------------------------------- #

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def words(self) -> tuple[OcrWord, ...]:
        return tuple(w for line in self.lines for w in line.words)

    @property
    def chars(self) -> tuple[OcrChar, ...]:
        return tuple(c for line in self.lines for w in line.words for c in w.chars)

    @property
    def box(self) -> BBox:
        return BBox.union_of([line.box for line in self.lines])

    @property
    def is_empty(self) -> bool:
        return not any(line.words for line in self.lines)

    @property
    def char_count(self) -> int:
        return sum(len(w.text) for w in self.words)

    @property
    def mean_confidence(self) -> float:
        """Length-weighted mean word confidence over the whole result."""
        total = 0.0
        weight = 0.0
        for word in self.words:
            n = max(1, len(word.text))
            total += word.confidence * n
            weight += n
        return total / weight if weight else 0.0

    @property
    def min_word_confidence(self) -> float:
        """Worst word.  A page is only as trustworthy as its weakest token, and
        the mean hides exactly the tokens a proofreader must be sent to.

        Use this to *route a human*, which is what it is for.  Do not use it to
        score an engine over a whole page: see
        :meth:`weak_word_confidence` for why."""
        words = [w for w in self.words if w.text.strip()]
        return min((w.confidence for w in words), default=0.0)

    def weak_word_confidence(self, quantile: float = 0.05) -> float:
        """The ``quantile``-th worst word — the robust form of the above.

        :attr:`min_word_confidence` is the right question for a region and the
        wrong one for a page.  Measured over twelve corpus pages, Tesseract's
        minimum word confidence is **0.000 on every single one**: a full page
        always contains one artefact — a speck read as a letter, a diagram
        coordinate, a fragment of a rule — that the engine rates at zero.  A
        term that is constant carries no information, and when it is blended
        into a score at weight 0.35 it stops being harmless and becomes a flat
        35 % penalty that pushed the engine below its own calibration floor on
        12 of 12 pages.  See docs/quality/F5_REPORT_C2.md §5.

        A low quantile keeps what the minimum was for — refusing to let the
        mean hide the tokens that are actually wrong — while surviving the one
        artefact that every page has.
        """
        scores = sorted(w.confidence for w in self.words if w.text.strip())
        if not scores:
            return 0.0
        index = int(quantile * (len(scores) - 1))
        return float(scores[max(0, min(index, len(scores) - 1))])

    def low_confidence_words(self, threshold: float = 0.60) -> tuple[OcrWord, ...]:
        return tuple(w for w in self.words
                     if w.text.strip() and w.confidence < threshold)

    def iter_lines(self) -> Iterator[OcrLine]:
        return iter(self.lines)

    def with_meta(self, **extra: object) -> "OcrResult":
        merged = dict(self.meta)
        merged.update(extra)
        return OcrResult(
            engine=self.engine,
            lang=self.lang,
            lines=self.lines,
            region_kind=self.region_kind,
            duration_s=self.duration_s,
            warnings=self.warnings,
            meta=merged,
        )

    def with_warning(self, message: str) -> "OcrResult":
        return OcrResult(
            engine=self.engine,
            lang=self.lang,
            lines=self.lines,
            region_kind=self.region_kind,
            duration_s=self.duration_s,
            warnings=self.warnings + (message,),
            meta=self.meta,
        )


def empty_result(engine: str, lang: str, *,
                 region_kind: RegionKind = RegionKind.UNKNOWN,
                 warning: str | None = None,
                 duration_s: float = 0.0,
                 **meta: object) -> OcrResult:
    """A result carrying no text — the honest answer when an engine cannot run."""
    return OcrResult(
        engine=engine,
        lang=lang,
        lines=(),
        region_kind=region_kind,
        duration_s=duration_s,
        warnings=(warning,) if warning else (),
        meta=meta,
    )


# --------------------------------------------------------------------------- #
# Layout regions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TextRegion:
    """A rectangle of the page that the layout analyser wants OCR'd, together
    with everything the arbiter needs to pick an engine for it."""

    box: BBox
    kind: RegionKind = RegionKind.PARAGRAPH
    column_index: int = 0
    reading_order: int = 0
    lang_hint: str | None = None
    #: Index of the figure/diagram this region is attached to, for captions.
    attached_to: int | None = None
    meta: Mapping[str, object] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Text helpers used by more than one module
# --------------------------------------------------------------------------- #
