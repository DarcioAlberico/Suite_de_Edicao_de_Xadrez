"""A table read row by row, whatever blocks the engine cut it into — OCR_UI_ROADMAP_C2 passo B13.

Tesseract in PSM 3 segments a page into **blocks** and reads them one after
the other.  On a table at 150 DPI, or on a game score printed as a move list
(``28 ♘f2 | ♗h4!``), the blocks are the *columns*: every name, then every
place, then every opening; every White move, then every Black one.  The text
comes out with every character right and in the wrong order — measured on the
golden corpus (``OCR_UI_REPORT_C2_FASE5.md`` §B13): ``table:7`` at 150 DPI
CER 0,676 with ``hypothesis_chars == truth_chars``, and the Dvoretsky move
list ``real:…:17:401:52`` 0,590.  The same tables at 300 DPI come out one
block per cell, in row order, CER 0.  The RapidOCR adapter already reads
short-cell columns row by row (``engines.rapidocr._reading_order``); this is
the same rule, applied to Tesseract **through its own blocks**:

1.  Two blocks are *side by side* when their word extents are disjoint in
    ``x`` and overlap in ``y``.
2.  A group starts at a block of **cells**: a median line of at most
    :data:`TABLE_CELL_CHARS` characters **and no line longer than twice that**
    (a move list, a column of places — a block with one line of prose in it is
    a column of text, not of cells), or an internal gutter across its own lines
    (``find_gutters`` — a block that merged three cells of a row:
    ``Moscovo 1960 | Francesa, Winawer | 203``).
3.  It grows by any block beside one of its members whose lines **find a
    partner** in the group — a line of another block at the same height — at
    least :attr:`TableRowsConfig.align_share` of the time.  A column of prose
    beside a small table has forty lines and five partners; it never joins.
    And a block of prose (long lines, several of them, no internal gutter) is
    never a member at all, whatever its partners.
4.  A group never crosses a **column gutter**: the gap between two blocks
    holds the page's gutter when a corridor inside it is touched by almost no
    line of prose reaching into the two blocks (at most
    :attr:`TableRowsConfig.gutter_max_share` of at least
    :attr:`TableRowsConfig.gutter_min_lines` lines) — the gap between the
    columns of a table or a move list is crossed by the running text above and
    below it, a column gutter by nothing but a header.  And on a page the B1
    layout reads as two columns of prose (:mod:`.scan`), the same holds by its
    decision.
5.  The group is written out **row by row**: its lines clustered by height,
    each row left to right, in the place of the group's first line.

The rules 2 and 4 were measured on real pages, not on the corpus (whose table
items are crops): on the two-column scans of the Levenfis the right column's
move lines, or the noise Tesseract reads in a left-column diagram, seeded
groups that crossed the page's gutter, and a whole column was pulled into the
middle of the other (pages 40 and 41; ``OCR_UI_REPORT_C2_FASE5.md`` §B13).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from ..types import BBox, OcrLine, OcrResult

__all__ = ["TABLE_CELL_CHARS", "TableRowsConfig", "rows_of_tables", "table_groups"]


#: A block whose median line is this short (characters) is a column of cells —
#: the constant of the RapidOCR adapter (``engines.rapidocr.TABLE_CELL_CHARS``),
#: measured there on the SFC4 move lists.
TABLE_CELL_CHARS = 12


@dataclass(frozen=True, slots=True)
class TableRowsConfig:
    """The rule's numbers, each with the reason it is that number."""

    #: See :data:`TABLE_CELL_CHARS`.
    cell_chars: int = TABLE_CELL_CHARS
    #: Share of a joining block's lines that must find a partner at the same
    #: height in the group.  ``table:7`` at 150 DPI joins its name column at
    #: 4 of 5 (the header row sits alone above the seed's first row).
    align_share: float = 0.8
    #: Two lines are at the same height when their vertical overlap is more
    #: than this share of the shorter one — RapidOCR's ``_overlapping``.
    overlap: float = 0.5
    #: ...and no line of a column of cells is longer than this (twice the cell).
    cell_max_chars: int = 2 * TABLE_CELL_CHARS
    #: A block with at least this many lines, a median line at least this
    #: long and no internal gutter is **prose**: it never joins a group.
    prose_min_lines: int = 3
    prose_chars: int = 30
    #: A gap between two blocks is a column gutter when at most this share of
    #: the lines of prose reaching into the two blocks touch it...
    gutter_max_share: float = 0.1
    #: ...judged only when at least this many lines of prose reach into them (a
    #: crop of a table has none to judge by, and is what this module is for).
    gutter_min_lines: int = 8
    #: ...and only a free corridor at least this wide is a gutter (the floor of
    #: ``scan.ScanLayoutConfig.gutter_min_px``, doubled: the space between two words
    #: of a justified line is never this wide on every line).
    gutter_min_px: int = 8


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


def _words_extent(lines: Sequence[OcrLine]) -> BBox | None:
    boxes = [w.box for line in lines for w in line.words if w.text.strip()]
    return BBox.union_of(boxes) if boxes else None


def _same_height(a: BBox, b: BBox, share: float) -> bool:
    top = max(a.y0, b.y0)
    bottom = min(a.y1, b.y1)
    shorter = max(1e-6, min(a.h, b.h))
    return bottom - top > share * shorter


@dataclass(slots=True)
class _Block:
    index: int
    lines: list[OcrLine]
    extent: BBox
    median_chars: int
    max_chars: int
    gutters: bool

    def side_by_side(self, other: _Block) -> bool:
        a, b = self.extent, other.extent
        disjoint = a.x1 <= b.x0 or b.x1 <= a.x0
        return disjoint and min(a.y1, b.y1) > max(a.y0, b.y0)


def _median(values: Sequence[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else 0


def _blocks(lines: Sequence[OcrLine]) -> list[_Block]:
    """The engine's blocks, in the order their first line is read."""
    from .scan import find_gutters

    grouped: dict[int, list[OcrLine]] = {}
    for line in lines:
        if any(w.text.strip() for w in line.words):
            grouped.setdefault(line.block_index, []).append(line)
    blocks: list[_Block] = []
    for index, members in grouped.items():
        extent = _words_extent(members)
        if extent is None:
            continue
        blocks.append(_Block(
            index=index, lines=members, extent=extent,
            median_chars=_median([len(line.text.strip()) for line in members]),
            max_chars=max(len(line.text.strip()) for line in members),
            gutters=bool(find_gutters(members)),
        ))
    return blocks


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #


def _is_cells(block: _Block, cfg: TableRowsConfig) -> bool:
    short = block.median_chars <= cfg.cell_chars and block.max_chars <= cfg.cell_max_chars
    return short or block.gutters


def _prose_gutters(result: OcrResult) -> list[tuple[float, float]]:
    """The interior gutter of a page of two columns of prose, or nothing.

    The same decision as :func:`.scan.scan_layout` (passo B1): one gutter, and
    every band reads as prose.  A table (three bands) or a move list (short
    bands) returns nothing -- those are what this module exists to read by rows.
    """
    from .scan import ScanLayoutConfig, _bands_are_prose, find_gutters, split_at_gutters

    scan = ScanLayoutConfig()
    gutters = find_gutters(result.lines, config=scan)
    if not gutters or len(gutters) + 1 > scan.max_columns:
        return []
    if not _bands_are_prose(split_at_gutters(result, gutters).lines, gutters, scan):
        return []
    return gutters


def _is_prose(block: _Block, cfg: TableRowsConfig) -> bool:
    return (len(block.lines) >= cfg.prose_min_lines and block.median_chars >= cfg.prose_chars
            and not block.gutters)


def _gap_between(a: BBox, b: BBox) -> tuple[float, float]:
    return (a.x1, b.x0) if a.x1 <= b.x0 else (b.x1, a.x0)


def _prose_lines(lines: Sequence[OcrLine], cfg: TableRowsConfig) -> list[OcrLine]:
    """The lines long enough to be running text -- the ones that cross a table's
    column gaps and never a page's gutter.
    """
    return [line for line in lines if len(line.text.strip()) >= cfg.prose_chars]


def _is_column_gutter(gap: tuple[float, float], span: tuple[float, float],
                      prose: Sequence[OcrLine], cfg: TableRowsConfig) -> bool:
    """Whether ``gap`` holds the page's column gutter: a corridor inside it, at least
    ``gutter_min_px`` wide, that almost no line of prose reaching into ``span`` (the two
    blocks' joint extent in ``x``) touches.

    Prose, because a table's own lines never cross its column gaps -- ``table:4`` at
    150 DPI has 18 lines and a free corridor between its places and its openings; what
    tells a table's gap from a page's gutter is the running text above and below, which
    crosses the one and never the other.  Reaching into ``span``, because the other
    column's prose says nothing about this one.  A corridor and not the whole gap: a
    move-list fragment of the left column ends before the column's edge, so the gap to
    the right column's block starts inside the left column's prose -- measured on the
    Levenfis p. 40, the gap 790–888 is touched by the left column up to x ≈ 800, and the
    gutter is the free 800–888 inside it.
    """
    import numpy as np

    others = [line for line in prose if line.box.x1 > span[0] and line.box.x0 < span[1]]
    if len(others) < cfg.gutter_min_lines:
        return False
    low, high = int(np.floor(gap[0])), int(np.ceil(gap[1]))
    if high - low < cfg.gutter_min_px:
        return False
    touched = np.zeros(high - low, dtype=np.int32)
    for line in others:
        mask = np.zeros(high - low, dtype=bool)
        for word in line.words:
            if not word.text.strip():
                continue
            a = max(0, int(word.box.x0) - low)
            b = min(high - low, int(np.ceil(word.box.x1)) - low)
            if b > a:
                mask[a:b] = True
        touched += mask
    free = touched <= cfg.gutter_max_share * len(others)
    run = best = 0
    for value in free:
        run = run + 1 if value else 0
        best = max(best, run)
    return best >= cfg.gutter_min_px


def _partner_share(block: _Block, group: Sequence[_Block], cfg: TableRowsConfig) -> float:
    others = [line.box for member in group for line in member.lines]
    found = sum(1 for line in block.lines
                if any(_same_height(line.box, box, cfg.overlap) for box in others))
    return found / max(1, len(block.lines))


def table_groups(result: OcrResult, *,
                 config: TableRowsConfig | None = None) -> list[list[int]]:
    """The block indices of every group that reads as a table, seeds first.

    Exposed for the tests and for whoever wants to say *why* a page was
    reordered; :func:`rows_of_tables` is the one the pipeline calls.
    """
    cfg = config or TableRowsConfig()
    blocks = _blocks(result.lines)
    if len(blocks) < 2:
        return []
    from .scan import _band_of

    gutters = _prose_gutters(result)

    def band(block: _Block) -> int:
        return _band_of(block.extent.cx, gutters) if gutters else 0

    prose = _prose_lines([line for block in blocks for line in block.lines], cfg)

    def beside(block: _Block, group: Sequence[_Block]) -> bool:
        """Side by side with a member, across a gap that is not the page's gutter."""
        inside = {m.index for m in group} | {block.index}
        others = [line for line in prose if line.block_index not in inside]
        for m in group:
            if not block.side_by_side(m):
                continue
            span = (min(block.extent.x0, m.extent.x0), max(block.extent.x1, m.extent.x1))
            if not _is_column_gutter(_gap_between(block.extent, m.extent), span, others, cfg):
                return True
        return False

    taken: set[int] = set()
    groups: list[list[int]] = []
    # The tallest column of cells seeds first: on ``table:4`` at 150 DPI the two
    # one-line cells of the last row (``Haia 1937``, ``Eslava``) seeded in
    # reading order would form a group of their own and leave that row split in
    # two; the column of page numbers (four lines) seeds the whole table.
    seeds = sorted((b for b in blocks if _is_cells(b, cfg)), key=lambda b: -len(b.lines))
    for seed in seeds:
        if seed.index in taken:
            continue
        group = [seed]
        grew = True
        while grew:
            grew = False
            for block in blocks:
                if (block.index in taken or any(block is m for m in group)
                        or _is_prose(block, cfg) or band(block) != band(seed)
                        or not beside(block, group)):
                    continue
                if _partner_share(block, group, cfg) >= cfg.align_share:
                    group.append(block)
                    grew = True
        if len(group) >= 2:
            groups.append([b.index for b in group])
            taken.update(b.index for b in group)
    return groups


# --------------------------------------------------------------------------- #
# Rows
# --------------------------------------------------------------------------- #


def _rows(lines: Sequence[OcrLine], cfg: TableRowsConfig) -> list[list[OcrLine]]:
    """Lines clustered by height, top down; a row's height is its members'
    median extent, so a tall cell does not chain two rows into one.
    """
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda ln: (ln.box.cy, ln.box.x0)):
        best, best_overlap = None, 0.0
        for row in rows[-3:]:
            y0 = sorted(m.box.y0 for m in row)[len(row) // 2]
            y1 = sorted(m.box.y1 for m in row)[len(row) // 2]
            top, bottom = max(y0, line.box.y0), min(y1, line.box.y1)
            shorter = max(1e-6, min(y1 - y0, line.box.h))
            share = (bottom - top) / shorter
            if share > cfg.overlap and share > best_overlap:
                best, best_overlap = row, share
        if best is None:
            rows.append([line])
        else:
            best.append(line)
    return rows


def _merged(row: Sequence[OcrLine]) -> OcrLine:
    """One line out of a row of cells, left to right."""
    ordered = sorted(row, key=lambda ln: ln.box.x0)
    if len(ordered) == 1:
        return ordered[0]
    first = ordered[0]
    words = tuple(w for line in ordered for w in line.words)
    box = BBox.union_of([line.box for line in ordered])
    baseline = None
    if first.baseline is not None:
        # hOCR's baseline is relative to the box's bottom-left corner; keep the
        # leftmost cell's line, re-anchored on the merged box.
        slope, intercept = first.baseline
        y_at_left = first.box.y1 + intercept + slope * (box.x0 - first.box.x0)
        baseline = (slope, y_at_left - box.y1)
    return replace(first, words=words, box=box, baseline=baseline,
                   font_size=max(line.font_size for line in ordered))


def rows_of_tables(result: OcrResult, *, config: TableRowsConfig | None = None) -> OcrResult:
    """``result`` with every table group written out row by row.

    The same object when no group is found (a page of prose, a single block,
    an empty reading) — the common case costs one pass over the blocks.
    """
    cfg = config or TableRowsConfig()
    groups = table_groups(result, config=cfg)
    if not groups:
        return result
    group_of = {index: n for n, members in enumerate(groups) for index in members}
    members_lines: dict[int, list[OcrLine]] = {}
    for line in result.lines:
        n = group_of.get(line.block_index)
        if n is not None and any(w.text.strip() for w in line.words):
            members_lines.setdefault(n, []).append(line)
    out: list[OcrLine] = []
    emitted: set[int] = set()
    for line in result.lines:
        n = group_of.get(line.block_index)
        if n is None:
            out.append(line)
            continue
        if n in emitted:
            continue
        emitted.add(n)
        out.extend(_merged(row) for row in _rows(members_lines.get(n, []), cfg))
    return replace(result, lines=tuple(out),
                   meta={**dict(result.meta), "table_rows": len(groups)})
