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
    And a block of prose is never a member at all, whatever its partners:
    long lines, several of them, no internal gutter — or, in a column too
    narrow for long lines, four **words** a line (counted cell by cell when the
    block has internal gutters: ``Bona 2008 | Gambito da Dama Recusado | 88``
    is a row of cells) — or, however few words a line holds, lines longer than a
    cell that **carry the sentence over** (a word in lowercase opens a third of
    them: ``White could also try / 21 Bd6!?, when after / 21...Rg8 22 g4 Rg6 the
    / position is unclear.``).  **Notes** are running text too: a block whose
    lines hold move numbers inside them (``Or 21 Bd6 Rg8 22 g4 Rg6``, a variation
    in a narrow column) never joins.  A group holds at most one column that **numbers
    the moves** (consecutive move numbers, bare or followed by a move): two such
    columns side by side are two games, or one game in two page columns, and a
    move column whose own numbers stand between it and the group's numbering
    belongs to those numbers.  And a group never holds a game and a column of
    **names** -- a move list beside the standings of the tournament is a game and
    a table, never one table (``1 e4 e5 Aljechin 7½``) -- or a game and a column of
    **numbers or scores** that does not number its moves (the ratings beside it);
    a game whose move numbers Tesseract cut from most lines (``. Lb5 a6``) is a
    game still.  And a **cell is one row
    high**: a block with a line at the height of two lines of another, lines not
    at one height between them, never joins the other's group (Tesseract reads a
    column of placings, ``1.`` … ``12.``, as one line eight rows high).
4.  A group never crosses a **column gutter**: the gap between two blocks
    holds the page's gutter when a corridor inside it is touched by almost no
    line of prose reaching into the two blocks (at most
    :attr:`TableRowsConfig.gutter_max_share` of at least
    :attr:`TableRowsConfig.gutter_min_lines` lines) — the gap between the
    columns of a table or a move list is crossed by the running text above and
    below it, a column gutter by nothing but a header.  And the page's gutter
    holds by itself when the B1 layout reads two columns of prose
    (:mod:`.scan`), or when one gutter over the whole reading leaves two bands
    of **comparable width** — prose or no prose: an index of names in two
    columns has none — or a band of prose (any of the kinds above) beside a
    narrow one; of two gutters or more, the ones next to a block of prose (the
    others are a table's gaps, or the tab of a move list in one column).  Two
    kinds of page gutter need no prose, however many gutters there are: the one
    between two **lists** side by side — two units of one form, entries (a name
    and its pages in one band, ``Aaron 249``; a name in one band and its pages in
    the next, ``Aaron | 249``; a player and the opponents under the player) or
    names with values (``Aljechin 7½``), in any order and however short; or any
    two units of a **page of lists**, every unit of it entries, names with values
    or names, whatever the form of each (a column of four-digit numbers beside
    columns of pages, a column of names only between two columns of entries, a
    half of the standings whose points the OCR lost) — a table has a column that
    is none of them, and a column of numbers set apart beside the names (the
    ratings of a pairing) makes its band a table's —
    and the one between a **game** (numbered lines with their moves, or a column
    of move numbers beside a column of moves, as the German books cut them) and a
    column of text (lines longer than a cell that are not moves), whether or not
    a rule above calls that text prose.
    Across a page's gutter only a **move list** is a group: numbers and
    White's moves on the left, one move a line on the right (an evaluation set
    apart, ``31 Nh1 !?``, is part of its move) — the positive evidence of a
    table that two lists of the same shape never give; across two, the numbers
    in the first band and the bands one after the other — a group never jumps a
    band.  A table of two columns
    that is not a move list (``Wilhelm Steinitz | 1886–1894``) and leaves one
    gutter of comparable bands is read by columns, as with the rule off.
5.  The group is written out **row by row**: its lines clustered by height,
    each row left to right, in the place of the group's first line.

The rules 2, 3 and 4 were measured on real pages, not on the corpus (whose
table items are crops): on the two-column scans of the Levenfis the right
column's move lines, or the noise Tesseract reads in a left-column diagram,
seeded groups that crossed the page's gutter (pages 40 and 41); and the phase's
critic found the narrow columns of the Gallagher, where no line is long enough
to be prose by length and the right column's move numbers pulled the left
column's notes into their rows (p. 50, CER 0,27 → 0,70), and the pages of two
numbered columns (``OCR_UI_REPORT_C2_FASE5.md`` §B13); its second cycle found
the index of names of the Karpov 2 (p. 268: two columns of names and page numbers,
no prose at all) joined line by line across the gutter the rule itself had found,
and notes of variations beside a move list joining it; and its third cycle found
ordinary notes -- three words a line, a move here and there, justified in a narrow
column -- beside a move list set without tabs, joined line by line and *accepted* by
the importer, because nothing called them prose.  Its fourth cycle found the indexes of
three columns or more -- the Flores pp. 460–464, the Yusupov 4 p. 206, the Nunn p. 288:
names and pages of two columns joined line by line, the gutters between them read as a
table's gaps because no prose stood beside them -- and notes that no rule calls prose,
beside a game, joined to it (the Nunn pp. 29 and 143, the Burgess p. 133).  The rule that
answered it -- a column whose heads rise in alphabetical order is a list -- was not the class:
its fifth cycle found «jogador / adversários» by the standings (0,0000 → 0,6577, *accepted*),
the last page of an index with five entries in its second column, a game beside the standings of
a tournament joined to them, and a table whose names and countries rose in order by chance read
as two lists.  What makes two columns two lists is their form, not their order.  And in its own
page of a game beside the standings with the placings, the column of placings read as one line
eight rows high joined the game, and the game's fifth move came out on its second line.  Its sixth
cycle found lists whose columns differ in form joined again and *accepted* -- a column of
four-digit numbers (0,0026 → 0,4916), a column of names only between two of entries, a half of the
standings whose points the OCR lost --, and a game beside a column of ratings, or set in German
notation with its numbers cut off, joined to the table beside it: a page of lists is one whose
every column is a list, whatever the form of each.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Sequence
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
    #: ...and so is a block of at least this many lines whose median line holds at
    #: least this many **words** (two letters or more, no digit): the prose of a
    #: *narrow* column.  The Gallagher (``Winning With the King's Gambit``) sets its
    #: two columns at 22–27 characters a line, so no line reaches ``prose_chars``, and a
    #: column of notes joined the move list of the other column (crítico da fase 5,
    #: ``OCR_UI_REPORT_C2_FASE5.md`` §B13).  A table's cells run 1–3 words
    #: (``21. Anand — Kramnik``, ``Wijk aan Zee 2011``); a move has none.
    prose_word_lines: int = 2
    prose_words: int = 4
    #: ...whose lines **continue** one another: at least this share of them, after the
    #: first, begin with a word in lowercase -- a sentence carried over the end of a line
    #: (``The best chance to get / his rook into the game``); a move (``b6 23 Be3``) is not
    #: a word.  A column of cells starts every line anew: ``Defesa Francesa, Variante
    #: Winawer / Gambito da Dama Recusado`` holds four words a cell and continues nothing
    #: (crítico da fase 5, ciclo 2: a table with the openings written out read 0,4646 →
    #: 0,3456 by the words alone).
    prose_continued: float = 1 / 3
    #: A block of at least this many lines, its median line longer than a cell
    #: (``cell_chars``), whose lines continue one another (``prose_continued``) is **running
    #: text**, however few words a line holds.  Notes in a narrow column run three words a
    #: line and hold a move here and there (``White could also try / 21 Bd6!?, when after /
    #: 21...Rg8 22 g4 Rg6 the / position is unclear.``): not prose by length, nor by words,
    #: nor notes of variations -- and beside a move list set without tabs they joined it line
    #: by line, the page read «White could also try 26 Re3 Bxd4» and *accepted* (crítico da
    #: fase 5, ciclo 3: a page set as the Gallagher p. 50, CER 0,0052 → 0,6440 through the
    #: importer).  Four lines, because a sentence needs room to be carried over twice.
    running_lines: int = 4
    #: A block **numbers the moves** when at least this share of its lines open with
    #: consecutive move numbers, bare (``26``, ``27``…) or followed by a move (``22 g4``,
    #: ``21... ♖g8``); a group holds at most one such block.  Two numbered columns side by
    #: side are two games, or one game in two page columns -- never a White column and
    #: its Black replies (crítico da fase 5: two games side by side, CER 0,0190 → 0,5625).
    numbered_share: float = 0.5
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
    #: A block's **internal** gutter separates cells only when it is this many times
    #: wider than the block's median space between words that do not cross it.  A
    #: river through three justified lines is narrower than a word space (Gallagher
    #: p. 53: 20 px against 33, measured); the gap between the cells of a table row is
    #: wider (``table:2`` at 150 DPI: 15 px against 7; at 300 DPI 32–68 against 14).
    cell_gap_ratio: float = 1.5
    #: One gutter over the whole reading that leaves two bands of comparable width --
    #: the narrower at least this share of the wider -- is the page's gutter, prose or no
    #: prose.  The Karpov 2 (``Chess Combinations -- World Champions 2``) p. 268 is an index
    #: of names in two columns, 552 and 511 px: no line of prose, and its entries were
    #: joined two by two across the gutter (crítico da fase 5, ciclo 2: CER 0,76 against the
    #: book's order).  A table's columns leave two gutters or more (``table:2/4/7`` at
    #: 150 DPI); the Dvoretsky move lists leave one, their bands 0,65–0,85 of each other,
    #: and cross it as the one group that may: a move list.
    page_band_share: float = 0.5
    #: A block is **notes** -- running text, never a member -- when at least this share of
    #: its lines hold a move number inside the line, not at its start, followed by a move
    #: (``Or 21 Bd6 Rg8 22 g4 Rg6``).  A column of variations has a word or two a line, and
    #: beside a numbered move list it joined it (crítico da fase 5, ciclo 2: a page set as
    #: the Gallagher p. 50, notes of variations beside the game, CER 0,0113 → 0,5845).  A
    #: move list opens its lines with the number; a table's numbers are years and pages.
    notes_share: float = 0.5
    #: A band of the page is a **list of entries** (:func:`_band_form`) when at least this share of
    #: its rows are a name and its numbers -- the «jogador / adversários» columns of the Yusupov 4
    #: p. 206 hold 52–63 % entries, the rest the players they are listed under --, and at least
    #: ``list_listed_share`` of its rows are names, entries or numbers.  Two lists of one form side
    #: by side are two lists: the gutter between them is the page's, found without prose and
    #: without order (crítico da fase 5, ciclos 4 e 5: the Flores pp. 460–464, the Yusupov 4
    #: p. 206 and the Nunn p. 288 interleaved line by line, «David 412 Galkin 198», CER 0,0230 →
    #: 0,7217; the players by the standings «Carlsen Caruana 82 Nepomniachtchi 127», 0,0000 →
    #: 0,6577 *accepted*; the last page of an index, five entries in the second column).  A
    #: table's columns are not two lists of one form: a name, a place and a year, an opening and
    #: its page (``table:2/4/7``); a name, a country, a rating and a score.
    list_entry_share: float = 0.3
    list_listed_share: float = 0.8
    #: A block is a column of **names** -- never grouped with a game -- when it has at least
    #: ``names_min_lines`` lines of a cell's length at most (``cell_max_chars``) and at least
    #: ``names_share`` of them are names, alone or with a value or numbers (:func:`_names`).  One
    #: line that reads as a word is OCR's noise as often as a name (``(hi?`` for a Black move of
    #: the Gallagher p. 33), and a line of text is not a cell (``Zurück zur Textvariante: 1.``,
    #: the Gunderam p. 20).
    names_share: float = 0.6
    names_min_lines: int = 3
    #: A **game** -- at least this many lines that open with consecutive move numbers, each
    #: followed by a move (``26 Re3 Bxd4``) -- makes the gutter beside it the page's when
    #: the other side holds text (lines longer than a cell): notes that no rule calls prose
    #: -- lines opening with a move, a number or a capital -- joined the game line by line
    #: (crítico da fase 5, ciclo 4: 12 of 29 pages at risk; the Nunn p. 29 notes set as the
    #: Gallagher p. 50, 0,0824 → 0,6571).  Cells beside a game (Black's replies) cross it as
    #: the move list they are.
    game_min_lines: int = 3


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
    #: The internal gutters of the block's own lines (``find_gutters``): the gaps
    #: between the cells of a row that Tesseract read as one line.
    gutter_spans: tuple[tuple[float, float], ...] = ()

    @property
    def gutters(self) -> bool:
        return bool(self.gutter_spans)

    def side_by_side(self, other: _Block) -> bool:
        a, b = self.extent, other.extent
        disjoint = a.x1 <= b.x0 or b.x1 <= a.x0
        return disjoint and min(a.y1, b.y1) > max(a.y0, b.y0)


def _median(values: Sequence[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else 0


def _cell_gaps(members: Sequence[OcrLine], spans: Sequence[tuple[float, float]],
               cfg: TableRowsConfig) -> tuple[tuple[float, float], ...]:
    """The internal gutters that separate cells: wider than ``cell_gap_ratio`` times the
    median space between words that cross no gutter (the characters' median width when
    every space crosses one)."""
    if not spans:
        return ()
    spaces: list[float] = []
    widths: list[float] = []
    for line in members:
        words = sorted((w for w in line.words if w.text.strip()), key=lambda w: w.box.x0)
        widths += [w.box.w / max(1, len(w.text)) for w in words]
        for left, right in zip(words, words[1:], strict=False):
            gap = (left.box.x1, right.box.x0)
            if gap[1] > gap[0] and not any(gap[0] < high and low < gap[1] for low, high in spans):
                spaces.append(gap[1] - gap[0])
    scale = _median_float(spaces) if spaces else _median_float(widths)
    return tuple(span for span in spans if span[1] - span[0] >= cfg.cell_gap_ratio * scale)


def _median_float(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else 0.0


def _blocks(lines: Sequence[OcrLine], cfg: TableRowsConfig | None = None) -> list[_Block]:
    """The engine's blocks, in the order their first line is read."""
    from .scan import find_gutters

    cfg = cfg or TableRowsConfig()
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
            gutter_spans=_cell_gaps(members, find_gutters(members), cfg),
        ))
    return blocks


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #


def _is_cells(block: _Block, cfg: TableRowsConfig) -> bool:
    short = block.median_chars <= cfg.cell_chars and block.max_chars <= cfg.cell_max_chars
    # An internal gutter makes cells of merged table cells (``Moscovo 1960 | Francesa,
    # Winawer | 203``), not of a paragraph with a stray gap: the Kmoch p. 44's
    # «(Een duidelijke wenk tot» seeded a group across the page's gutter (crítico da fase 5).
    return short or (block.gutters and not _wordy(block, cfg))


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


def _page_gutters(result: OcrResult, blocks: Sequence[_Block],
                  cfg: TableRowsConfig) -> list[tuple[float, float]]:
    """The gutter of a page of two columns whatever the columns hold, or nothing.

    The B1 decision (:func:`_prose_gutters`) wants every band to read as prose by the
    length of its lines, and a narrow column never does: on the Gallagher p. 50 the
    right band is a move list under two lines of notes, its median line is a move
    number, and the page read as one column.  Here one gutter over the whole page is
    enough when its two bands are of **comparable width** (``page_band_share``) --
    whatever they hold: the Karpov 2 p. 268 is two columns of names and page numbers,
    with no prose to judge by -- or when a side of it holds a block of prose by
    :func:`_is_prose` (words or running text, not characters: the Gallagher p. 53's left
    column is notes and moves).  A move list split by one gutter keeps it, and
    :func:`table_groups` lets a move list, and only it, cross it.  Of two gutters or more
    -- a table's gaps, or the page's gutter beside the tab of a move list set in one column
    (the Gallagher p. 50: the page's 754–817 and Black's tab 1171–1193, where a reading the
    arbiter discarded joined the left column's moves to the right column's game) -- the
    page's are those next to a block of prose, the first on each side of it; a table has
    no prose, and a tab has the column's own text on both sides.

    And two kinds of page need no prose at all (crítico da fase 5, ciclos 4 e 5): **two lists of
    one form** side by side -- the gutter between them (:func:`_list_gutters`) -- and a **game**
    beside a column of text (the gutter between them, :func:`_game_gutters`).
    """
    from .scan import _band_of, find_gutters

    gutters = find_gutters(result.lines)
    if not gutters:
        return []
    bands: dict[int, list[_Block]] = {}
    for block in blocks:
        bands.setdefault(_band_of(block.extent.cx, gutters), []).append(block)
    page = set(_list_gutters(gutters, bands, cfg)) | set(_game_gutters(gutters, bands, cfg))
    prose = [b for b in blocks if _is_prose(b, cfg)]
    if len(gutters) > 1:
        # A table's gaps, or the page's gutter beside the tab of a move list set in one of
        # the columns (the Gallagher p. 50: 754–817 and the tab of Black's moves,
        # 1171–1193): the page's gutters are the ones next to a block of prose -- the first
        # gutter past its right edge, the first before its left.  A table has no prose.
        for block in prose:
            after = [g for g in gutters if g[0] >= block.extent.x1]
            before = [g for g in gutters if g[1] <= block.extent.x0]
            if after:
                page.add(min(after, key=lambda g: g[0]))
            if before:
                page.add(max(before, key=lambda g: g[1]))
        return sorted(page)
    low, high = gutters[0]
    boxes = [w.box for line in result.lines for w in line.words if w.text.strip()]
    left_band = low - min(b.x0 for b in boxes)
    right_band = max(b.x1 for b in boxes) - high
    if min(left_band, right_band) >= cfg.page_band_share * max(left_band, right_band):
        return gutters
    if any(b.extent.x1 <= high or b.extent.x0 >= low for b in prose):
        return gutters
    return sorted(page)


def _first_word(text: str) -> str:
    """The line's first token when it is a word (letters, with a hyphen, an apostrophe or a
    period inside: ``Santo-Roman``, ``O'Kelly``, ``J.``), or nothing."""
    for token in text.split():
        core = token.strip(_PUNCTUATION)
        if not core:
            continue
        letters = core.replace("-", "").replace("'", "").replace("’", "").replace(".", "")
        return core if letters.isalpha() else ""
    return ""


#: A number a list gives after a name: a page, or the number of a game or an exercise (the Karpov
#: 1 index runs to four digits: «999, 1046»), with a letter before it (the Nunn's «R352», «P29»)
#: or a comma after it.
_NUMBER = re.compile(r"^[A-Z]?\d{1,4}[a-z]?[,;.]?$")
#: A page number has at most this many digits; a number of four is a page only in a list of them
#: (``999, 1046``) -- alone it is a year or a rating (``Moscovo 1985``).
_PAGE_DIGITS = 3
#: A score (``7½``, ``½``, ``=``): a value, never a page.  The ``%`` is the ½ Tesseract reads in
#: a book's type (``6½`` → ``6%``, the standings of the crítico da fase 5, ciclo 6), as ``=``.
_SCORE = re.compile(r"^(\d{0,2}[½=%]|\d{1,2}[.,]5)[,;.]?$")
#: What stands between a name and its numbers in an index (``Polugaevsky — 999``).
_BETWEEN = frozenset({"—", "–", "-", "…", "...", ":"})
#: The result of a game, part of a name in a list of games (``Carlsen – Caruana 1–0 45``).
_RESULT = re.compile(r"^(1|0|½)[-–:](1|0|½)[,;.]?$")


def _row_kind(text: str) -> tuple[str, list[str]]:
    """What a row of a band holds, and its numbers: ``refs`` (numbers only: ``231, 246``),
    ``numbered`` (a name and its numbers: ``Aaron 249``, ``Polugaevsky — 999, 1046``, ``Moscovo
    1985``), ``score`` (a score alone: ``7½``), ``value`` (a name and a score: ``Aljechin 7½``),
    ``word`` (words, no digit: ``Carlsen``), or ``""``."""
    tokens = [t for t in text.split() if t not in _BETWEEN]
    if not tokens:
        return "", []
    if all(_NUMBER.match(t) or _SCORE.match(t) for t in tokens):
        return ("score" if any(_SCORE.match(t) for t in tokens) else "refs"), tokens
    if not _first_word(text):
        return "", []
    tail = len(tokens)
    while tail > 1 and (_NUMBER.match(tokens[tail - 1]) or _SCORE.match(tokens[tail - 1])):
        tail -= 1
    head, numbers = tokens[:tail], tokens[tail:]
    if any(ch.isdigit() for token in head if not _RESULT.match(token) for ch in token):
        return "", []
    if not numbers:
        return "word", []
    return ("value" if any(_SCORE.match(t) for t in numbers) else "numbered"), numbers


def _line_kinds(lines: Sequence[OcrLine], cfg: TableRowsConfig) -> list[tuple[str, list[str]]]:
    """The kind of every line of a band (:func:`_row_kind`), a name and its numbers read as two
    lines at one height counted as one entry: the Flores p. 460 sets the pages apart from the
    names in its second column, and Tesseract read «Berzinsh» and «436, 459» side by side -- and a
    name and its score, one name with a value (a standings whose points Tesseract read as blocks
    of their own, «Flohr» and «6%»).  Line by line, and not row by row: a band that holds two
    columns of entries (a gutter the reading did not leave) would make every row two entries and
    no entry."""
    kinds = [_row_kind(line.text) for line in lines]
    taken: set[int] = set()
    for i, (line, (kind, _numbers)) in enumerate(zip(lines, kinds, strict=True)):
        if kind != "word":
            continue
        pages = next((j for j, (other, (other_kind, _n)) in enumerate(zip(lines, kinds, strict=True))
                      if other_kind in ("refs", "score") and j not in taken
                      and other.box.x0 > line.box.x1
                      and _same_height(line.box, other.box, cfg.overlap)), None)
        if pages is not None:
            taken.add(pages)
            kinds[i] = ("numbered" if kinds[pages][0] == "refs" else "value", kinds[pages][1])
    return [kind for j, kind in enumerate(kinds) if j not in taken]


def _numbers_beside(lines: Sequence[OcrLine], cfg: TableRowsConfig) -> int:
    """How many lines of numbers alone stand beside another line of the band, at one height.

    A column of numbers set apart from the names (the ratings of a pairing, «Nepomniachtchi | 2790
    | Firouzja | 2710»), and not the continuation of an entry's pages, which has its own height.
    A name and its pages at one height are one entry (:func:`_line_kinds`), and are not counted.
    """
    kinds = [_row_kind(line.text)[0] for line in lines]
    taken: set[int] = set()
    for i, (line, kind) in enumerate(zip(lines, kinds, strict=True)):
        if kind != "word":
            continue
        pages = next((j for j, (other, other_kind) in enumerate(zip(lines, kinds, strict=True))
                      if other_kind == "refs" and j not in taken and other.box.x0 > line.box.x1
                      and _same_height(line.box, other.box, cfg.overlap)), None)
        if pages is not None:
            taken.update((i, pages))
    return sum(1 for j, (line, kind) in enumerate(zip(lines, kinds, strict=True))
               if kind == "refs" and j not in taken
               and any(k != j and _same_height(line.box, other.box, cfg.overlap)
                       for k, other in enumerate(lines)))


def _band_form(lines: Sequence[OcrLine], cfg: TableRowsConfig) -> str:
    """The form of a band of the page (:func:`_line_kinds`): ``E`` a list of entries -- a third of
    the lines or more are a name and its numbers, nearly all are names, entries or numbers (the
    heads and the sub-entries of «jogador / adversários», the continuation lines of a long entry),
    and the numbers are a list somewhere (``999, 1046``) or short (pages: ``249``) --; ``V`` names
    with values (a year, a rating: ``Moscovo 1985``; a score: ``Aljechin 7½``); ``W`` names only;
    ``R`` numbers only; ``S`` scores only; ``""`` anything else -- and a band with a column of
    numbers beside its names (:func:`_numbers_beside`), a table's."""
    rows = _line_kinds(lines, cfg)
    n = len(rows)
    if not n:
        return ""
    if _numbers_beside(lines, cfg) >= cfg.list_entry_share * n:
        return ""
    count = {k: sum(1 for kind, _ in rows if kind == k)
             for k in ("refs", "numbered", "value", "word", "score")}
    listed = cfg.list_listed_share * n
    if (count["numbered"] >= cfg.list_entry_share * n
            and count["numbered"] + count["word"] + count["refs"] >= listed):
        numbers = [nums for kind, nums in rows if kind in ("numbered", "refs")]
        a_list = any(len(nums) > 1 for nums in numbers)
        short = all(sum(ch.isdigit() for ch in t) <= _PAGE_DIGITS for nums in numbers for t in nums)
        return "E" if a_list or short else "V"
    if (count["value"] >= cfg.list_entry_share * n
            and count["value"] + count["word"] >= listed):
        return "V"
    for kind, form in (("word", "W"), ("refs", "R"), ("score", "S")):
        if count[kind] >= listed:
            return form
    return ""


def _list_gutters(gutters: Sequence[tuple[float, float]], bands: dict[int, list[_Block]],
                  cfg: TableRowsConfig) -> list[tuple[float, float]]:
    """The gutter between two lists of the same form, side by side: two units of entries -- a band
    of entries (``Aaron 249``), or a band of names followed by a band of their references (the name
    and its pages set apart: ``Aaron | 249``) --, or two units of names with values.  Whatever their
    order and however short: a list beside a list is two lists, and the gutter before the second is
    the page's (crítico da fase 5, ciclo 5: «jogador / adversários» by the standings, 0,0000 →
    0,6577 *accepted*; the last page of an index, five entries in the second column, joined to the
    first).  And on a **page of lists** -- every unit of it a list: entries, names with values or
    names -- the gutter between any two, whatever the form of each: a detail of one column does not
    make it another list (crítico da fase 5, ciclo 6: the third column of an index whose numbers
    have four digits and no list, 0,0026 → 0,4916 *accepted*; a column of names only between two
    of entries; a half of the standings whose points the OCR lost).
    A table has a column that is not a list -- numbers alone, scores, numbered rows: a name, a place
    and a year, an opening, a page (``table:2/4/7``); a name, a country, a rating and a score -- or
    a band with a column of numbers beside its names (:func:`_numbers_beside`)."""
    filled = sorted(n for n, members in bands.items() if members)
    forms = {n: _band_form([ln for m in bands[n] for ln in m.lines], cfg) for n in filled}
    units: list[tuple[int, str]] = []   # (first band, form)
    k = 0
    while k < len(filled):
        n, form = filled[k], forms[filled[k]]
        after = forms[filled[k + 1]] if k + 1 < len(filled) else ""
        if form == "W" and after in ("R", "S"):
            units.append((n, "E" if after == "R" else "V"))
            k += 2
            continue
        units.append((n, form))
        k += 1
    lists = _page_of_lists([form for _n, form in units])
    return [gutters[second - 1] for (_first, a), (second, b) in itertools.pairwise(units)
            if 0 < second <= len(gutters)
            and ((a == b and a in ("E", "V")) or (a in lists and b in lists))]


def _page_of_lists(forms: Sequence[str]) -> tuple[str, ...]:
    """The forms whose gutters are the page's whatever the form beside them.

    Every one on a page of lists -- two units or more, every one entries, names with values or
    names --, none on any other page.  Crítico da fase 5, ciclo 6: a column of four-digit numbers,
    a column of names only, a half of the standings whose points the OCR lost; a table has a
    column that is none of them -- numbers alone, scores, numbered rows.
    """
    lists = ("E", "V", "W")
    return lists if len(forms) > 1 and all(form in lists for form in forms) else ()


def _game_gutters(gutters: Sequence[tuple[float, float]], bands: dict[int, list[_Block]],
                  cfg: TableRowsConfig) -> list[tuple[float, float]]:
    """The gutters with a game (:func:`_game`) on one side and text on the other -- lines
    longer than a cell that are neither the game nor its moves.

    The gutter is the one next to the game's band, and the text is in the nearest band that
    holds a block: ``find_gutters`` also finds the river of a column of short justified lines,
    and the blocks of that column all sit left of it -- the band between the river and the
    page's gutter is empty (the crítico's notes from the Dvoretsky index, pp. 789–798)."""
    def text(block: _Block) -> bool:
        return (block.median_chars > cfg.cell_chars and not _game(block, cfg)
                and not _numbers_moves(block, cfg) and not _move_column(block, cfg))

    def game(members: Sequence[_Block]) -> bool:
        # a game in one block, or cut in two: the numbers alone (``26.``, ``27.``: the German
        # notation's period parts them from the moves) and the moves beside them
        return any(_game(b, cfg) for b in members) or (
            any(_numbers_column(b, cfg) for b in members)
            and any(_move_column(b, cfg) for b in members)
            and sum(len(b.lines) for b in members if _numbers_column(b, cfg)) >= cfg.game_min_lines)

    filled = sorted(n for n, members in bands.items() if members)
    found: set[tuple[float, float]] = set()
    for k, n in enumerate(filled):
        if not game(bands[n]):
            continue
        if k > 0 and 0 < n <= len(gutters) and any(text(b) for b in bands[filled[k - 1]]):
            found.add(gutters[n - 1])
        if k + 1 < len(filled) and n < len(gutters) and any(
                text(b) for b in bands[filled[k + 1]]):
            found.add(gutters[n])
    return sorted(found)


def _game(block: _Block, cfg: TableRowsConfig) -> bool:
    """A numbered game: ``game_min_lines`` lines or more that open with consecutive move
    numbers, each followed by a move in the same line (``26 Re3 Bxd4``, ``21... Rg8``).
    Bare numbers cut from their moves are not a game on their own."""
    from ..lexicon import is_move_token

    numbers = []
    for line in block.lines:
        lead = _leading_number(line.text)
        if lead is not None and lead[1] and is_move_token(lead[1].rstrip(",;")):
            numbers.append(lead[0])
    if len(numbers) < cfg.game_min_lines or len(numbers) < cfg.numbered_share * len(block.lines):
        return False
    steps = sum(1 for a, b in itertools.pairwise(numbers) if b == a + 1)
    return steps >= cfg.numbered_share * (len(numbers) - 1)


#: What a word may carry around it -- stripped before a token is judged a word.
_PUNCTUATION = ".,;:!?()[]«»\"'“”‘’—–-…_|"


def _words(text: str) -> int:
    """The words of a line: tokens of two letters or more and no digit -- not a move,
    not a move number, not a dash."""
    count = 0
    for token in text.split():
        core = token.strip(_PUNCTUATION)
        if len(core) >= 2 and core.isalpha():
            count += 1
    return count


def _cell_words(line: OcrLine, spans: Sequence[tuple[float, float]]) -> int:
    """The words of a line's widest cell: the line cut at the block's internal gutters.
    ``Bona 2008 Gambito da Dama Recusado 88`` (``table:2`` at 150 DPI, three cells) holds
    four words in one cell, not six in one line of prose."""
    if not spans:
        return _words(line.text)
    cells: dict[int, list[str]] = {}
    for word in line.words:
        cell = sum(1 for _low, high in spans if word.box.cx >= high)
        cells.setdefault(cell, []).append(word.text)
    return max((_words(" ".join(texts)) for texts in cells.values()), default=0)


def _wordy(block: _Block, cfg: TableRowsConfig) -> bool:
    """Prose by words: the lower median line of the block holds ``prose_words`` words
    in one cell, and the lines carry the sentence over (:func:`_continued`)."""
    if len(block.lines) < cfg.prose_word_lines:
        return False
    words = sorted(_cell_words(line, block.gutter_spans) for line in block.lines)
    if words[(len(words) - 1) // 2] < cfg.prose_words:
        return False
    return _continued(block) >= cfg.prose_continued


def _continued(block: _Block) -> float:
    """The share of the block's lines, after the first, that carry a sentence over
    (:func:`_continues`)."""
    starts = [_continues(line.text) for line in block.lines[1:]]
    return sum(starts) / max(1, len(starts))


def _continues(text: str) -> bool:
    """Whether the line's first token is a word in lowercase: letters only (a hyphen or an
    apostrophe inside), so a move (``b6``, ``exd5``) or a move number opens no sentence."""
    for token in text.split():
        core = token.strip(_PUNCTUATION)
        if core:
            letters = core.replace("-", "").replace("'", "").replace("’", "")
            return letters.isalpha() and core[0].islower()
    return False


def _running(block: _Block, cfg: TableRowsConfig) -> bool:
    """Running text without counting words: ``running_lines`` lines, a median line longer
    than a cell, and lines that carry the sentence over (``prose_continued``)."""
    return (len(block.lines) >= cfg.running_lines and block.median_chars > cfg.cell_chars
            and _continued(block) >= cfg.prose_continued)


def _is_prose(block: _Block, cfg: TableRowsConfig) -> bool:
    long_lines = (len(block.lines) >= cfg.prose_min_lines
                  and block.median_chars >= cfg.prose_chars and not block.gutters)
    return long_lines or _wordy(block, cfg) or _running(block, cfg) or _notes(block, cfg)


_MOVE_NUMBER = re.compile(r"^(\d{1,3})(?!\d)(\.{1,3}|…)?(.*)$")
#: A move as OCR reads it: a square somewhere in it (``Bd6``, ``♖xd4``, ``@g1``, ``\\c3``)
#: or castling.
_MOVE_SQUARE = re.compile(r"[a-h][1-8]|[0O]-[0O]")
_PURE_NUMBER = re.compile(r"^\d+[.,;:]?$")
#: A line of a move list holds a move, or White's and Black's: two at most.
_MOVES_A_LINE = 2
#: An evaluation set apart from its move (``31 Nh1 !?``, ``Bxd4 +-``): part of the move, not
#: a token of its own.
_EVALUATION = re.compile(r"^[!?+\-=±∓∞#/⩲⩱]+$")


def _move_tokens(text: str) -> list[str]:
    """The line's tokens, less the evaluations set apart from their moves and bare punctuation.

    The period a move number leaves when Tesseract cuts the number off (``. Lb5 a6``) is not a
    move.
    """
    return [token for token in text.split()
            if not _EVALUATION.match(token) and any(ch.isalnum() for ch in token)]


def _inner_move_numbers(text: str) -> int:
    """Move numbers inside a line -- not its first token -- each followed by a move:
    ``Or 21 Bd6 Rg8 22 g4 Rg6`` holds two.  A year (``Moscovo 1960``) is not a move
    number, and a page number ends the line with no move after it."""
    tokens = text.split()
    count = 0
    for i, token in enumerate(tokens[1:], start=1):
        match = _MOVE_NUMBER.match(token)
        if match is None:
            continue
        rest = match.group(3) or (tokens[i + 1] if i + 1 < len(tokens) else "")
        if _MOVE_SQUARE.search(rest):
            count += 1
    return count


def _notes(block: _Block, cfg: TableRowsConfig) -> bool:
    """Notes of variations: ``notes_share`` of the block's lines hold a move number inside
    them.  Running text, whatever the number of words."""
    if len(block.lines) < cfg.prose_word_lines:
        return False
    inner = sum(1 for line in block.lines if _inner_move_numbers(line.text) > 0)
    return inner >= cfg.notes_share * len(block.lines)


def _numbers_column(block: _Block, cfg: TableRowsConfig) -> bool:
    """The left side of a move list split by the page's gutter: consecutive move numbers,
    each followed by one move at most, as OCR reads them (``1d4``, ``45 @g1``, ``3 exds``,
    ``31 Nh1 !?``), or bare (the numbers cut into a block of their own)."""
    numbers: list[int] = []
    moves = 0
    for line in block.lines:
        lead = _leading_number(line.text)
        if lead is None or len(_move_tokens(line.text)) > 2:
            continue
        numbers.append(lead[0])
        moves += bool(not lead[1] or _MOVE_SQUARE.search(lead[1]))
    if len(numbers) < 2 or len(numbers) < cfg.numbered_share * len(block.lines):
        return False
    steps = sum(1 for a, b in zip(numbers, numbers[1:], strict=False) if b == a + 1)
    return (steps >= cfg.numbered_share * (len(numbers) - 1)
            and moves >= cfg.numbered_share * len(numbers))


def _move_column(block: _Block, cfg: TableRowsConfig) -> bool:
    """A column of moves with no numbers of its own: one move a line (Black's replies, or
    White's moves cut from their numbers; ``Bxd4 +-`` is one move).  ``Bennett 218`` is a
    name and a page."""
    tokens = [_move_tokens(line.text) for line in block.lines]
    if any(len(t) > 2 or any(_PURE_NUMBER.match(x) for x in t) for t in tokens):
        return False
    moves = sum(1 for line in block.lines if _MOVE_SQUARE.search(line.text))
    return moves >= cfg.numbered_share * len(block.lines)


def _leading_number(text: str) -> tuple[int, str, bool] | None:
    """The number a line opens with, what follows it, and whether it is Black's
    (``21...``); ``None`` when the line does not open with a number."""
    tokens = text.split()
    if not tokens:
        return None
    match = _MOVE_NUMBER.match(tokens[0])
    if match is None:
        return None
    rest = match.group(3) or (tokens[1] if len(tokens) > 1 else "")
    return int(match.group(1)), rest, (match.group(2) or "") in ("..", "...", "…")


def _numbers_moves(block: _Block, cfg: TableRowsConfig) -> bool:
    """Whether the block is the column that numbers the moves: its lines open with
    consecutive numbers, bare or followed by a move.  A table's numbered rows
    (``21. Anand — Kramnik``) open with a number and a name; its page numbers
    (``301``, ``15``, ``56``) are bare and not consecutive."""
    from ..lexicon import is_move_token

    numbers = []
    for line in block.lines:
        lead = _leading_number(line.text)
        if lead is None:
            continue
        number, rest, black = lead
        if not rest or black or is_move_token(rest.rstrip(",;")):
            numbers.append(number)
    if len(numbers) < 2 or len(numbers) < cfg.numbered_share * len(block.lines):
        return False
    steps = sum(1 for a, b in zip(numbers, numbers[1:], strict=False) if b == a + 1)
    return steps >= cfg.numbered_share * (len(numbers) - 1)


def _lone_number(block: _Block) -> bool:
    """A block that is one bare number -- a move number Tesseract cut off its column
    (the ``21`` above ``22.``, ``23.``… of a page column's move list)."""
    if len(block.lines) != 1:
        return False
    tokens = block.lines[0].text.split()
    match = _MOVE_NUMBER.match(tokens[0]) if len(tokens) == 1 else None
    return match is not None and not match.group(3)


def _cut_game(block: _Block, cfg: TableRowsConfig) -> bool:
    """A game whose move numbers Tesseract cut from most lines, read apart (a tall line of them).

    ``game_min_lines`` lines or more, ``numbered_share`` of them one or two moves, after their
    number when it stayed (``10 d4 Sbd7``) or alone (``. Lb5 a6``).
    """
    if len(block.lines) < cfg.game_min_lines:
        return False
    moves = 0
    for line in block.lines:
        tokens = _move_tokens(line.text)
        if tokens and _PURE_NUMBER.match(tokens[0]):
            tokens = tokens[1:]
        if 1 <= len(tokens) <= _MOVES_A_LINE and _MOVE_SQUARE.search(" ".join(tokens)):
            moves += 1
    return moves >= cfg.numbered_share * len(block.lines)


def _moveish(block: _Block, cfg: TableRowsConfig) -> bool:
    """A block of a move list: a game, a column of moves, or move numbers with their moves."""
    return (_game(block, cfg) or _move_column(block, cfg) or _cut_game(block, cfg)
            or (_numbers_column(block, cfg)
                and any(_MOVE_SQUARE.search(line.text) for line in block.lines)))


def _names(block: _Block, cfg: TableRowsConfig) -> bool:
    """A column of names -- a table's cells, not a game's: ``names_min_lines`` short lines or more,
    ``names_share`` of them names, alone or with a value or page references (``Aljechin``,
    ``Aljechin 7½``).  A game's
    columns misread by OCR (``R£6+``, ``Hc?``, a stray «draw.» over the move numbers) are not."""
    if len(block.lines) < cfg.names_min_lines or block.median_chars > cfg.cell_max_chars:
        return False
    names = sum(1 for line in block.lines
                if _row_kind(line.text)[0] in ("word", "value", "numbered"))
    return names >= cfg.names_share * len(block.lines)


def _values(block: _Block, cfg: TableRowsConfig) -> bool:
    """A column of numbers or scores that does not number the moves: a table's, not a game's.

    Ratings, points, years: ``names_min_lines`` lines or more, ``names_share`` of them numbers or
    scores and nothing else (:func:`_row_kind`).
    """
    if (len(block.lines) < cfg.names_min_lines or _numbers_column(block, cfg)
            or _numbers_moves(block, cfg)):
        return False
    alone = sum(1 for line in block.lines if _row_kind(line.text)[0] in ("refs", "score"))
    return alone >= cfg.names_share * len(block.lines)


def _shares_rows(a: _Block, b: _Block, cfg: TableRowsConfig) -> bool:
    return any(_same_height(x.box, y.box, cfg.overlap) for x in a.lines for y in b.lines)


def _spans_rows(a: _Block, b: _Block, cfg: TableRowsConfig) -> bool:
    """A line of ``a`` stands at the height of two lines of ``b`` not at one height between them.

    A line two rows high or more.  Two lines of ``b`` at one height are one row: a name and its
    pages that Tesseract read as two lines (the Flores p. 460).
    """
    for line in a.lines:
        level = [other.box for other in b.lines if _same_height(line.box, other.box, cfg.overlap)]
        if any(not _same_height(p, q, cfg.overlap) for p, q in itertools.combinations(level, 2)):
            return True
    return False


def _one_row_high(a: _Block, b: _Block, cfg: TableRowsConfig) -> bool:
    """No line of either block is two rows of the other high: the cells of a row are one row high.

    The critic's game beside the standings with the placings (fase 5, ciclo 5, ``P|Tn``):
    Tesseract read the column of placings as one line 378 px high, ``SANDMNS WNP``; the game
    joined it, and the row that took the tall line took the game's fifth move too --
    «2 Nf3 Nc6 5 O-O Be7 2. WNP», 0,3185 → 0,3376 (ciclo 6, construtor).
    """
    return not (_spans_rows(a, b, cfg) or _spans_rows(b, a, cfg))


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


def _adjacent(block: _Block, group: Sequence[_Block], blocks: Sequence[_Block],
              cfg: TableRowsConfig) -> bool:
    """Most of the block's lines meet their nearest partner in the group across empty space:
    no word of a block outside the group stands between them at that height.

    The cells of a table row touch across white space; two fragments of one line of prose
    do not.  Gallagher p. 52: Tesseract cut «The so-called “Long» into ``The``, ``“Long``
    and a paragraph that begins with ``so-called``; the first two looked like a row of two
    cells, and the line came out «The “Long» with ``so-called`` below it (crítico da fase 5).
    """
    inside = {m.index for m in group} | {block.index}
    members = [line for member in group for line in member.lines]
    foreign = [word for other in blocks if other.index not in inside
               for line in other.lines for word in line.words if word.text.strip()]
    met = clear = 0
    for line in block.lines:
        partners = [m for m in members if _same_height(line.box, m.box, cfg.overlap)]
        if not partners:
            continue
        nearest = min(partners, key=lambda m: max(m.box.x0 - line.box.x1, line.box.x0 - m.box.x1))
        low, high = ((line.box.x1, nearest.box.x0) if line.box.x1 <= nearest.box.x0
                     else (nearest.box.x1, line.box.x0))
        met += 1
        if not any(low < w.box.cx < high and _same_height(line.box, w.box, cfg.overlap)
                   for w in foreign):
            clear += 1
    return met > 0 and 2 * clear >= met


def _partner_share(block: _Block, group: Sequence[_Block], cfg: TableRowsConfig) -> float:
    others = [line.box for member in group for line in member.lines]
    found = sum(1 for line in block.lines
                if any(_same_height(line.box, box, cfg.overlap) for box in others))
    return found / max(1, len(block.lines))


def _seeds(blocks: Sequence[_Block], cfg: TableRowsConfig) -> list[_Block]:
    """The blocks a group may start at: columns of cells that are not running text, the
    tallest first.

    Not running text, because a paragraph can be cells by a gap inside it -- a river through
    justified notes, a stray rule read as ``|`` -- and a seed is a member whatever it is: the
    notes would pull the other column's move list into their rows.  The tallest first: on
    ``table:4`` at 150 DPI the two one-line cells of the last row (``Haia 1937``,
    ``Eslava``) seeded in reading order would form a group of their own and leave that row
    split in two; the column of page numbers (four lines) seeds the whole table.
    """
    return sorted((b for b in blocks if _is_cells(b, cfg) and not _is_prose(b, cfg)),
                  key=lambda b: -len(b.lines))


def _crosses_the_page(members: Sequence[_Block], band: Callable[[_Block], int],
                      cfg: TableRowsConfig) -> bool:
    """The group would hold blocks on both sides of a page's gutter, and is not a move list
    split by it: the numbers (and maybe White's moves) in the first band, one move a line in
    each of the next -- positive evidence of a table, which two lists of the same shape (an
    index of names and pages) never give.  The bands must follow each other: a group never
    jumps over a band (numbers | White | Black across two gutters is one move list; two
    columns of an index with a third between them are not)."""
    bands = sorted({band(m) for m in members})
    if len(bands) < 2:
        return False
    if bands != list(range(bands[0], bands[-1] + 1)):
        return True
    first = [m for m in members if band(m) == bands[0]]
    rest = [m for m in members if band(m) != bands[0]]
    numbered = {m.index for m in first if _numbers_column(m, cfg)}
    return not (numbered
                and all(m.index in numbered or _move_column(m, cfg) for m in first)
                and all(_move_column(m, cfg) for m in rest))


def table_groups(result: OcrResult, *,
                 config: TableRowsConfig | None = None) -> list[list[int]]:
    """The block indices of every group that reads as a table, seeds first.

    Exposed for the tests and for whoever wants to say *why* a page was
    reordered; :func:`rows_of_tables` is the one the pipeline calls.
    """
    cfg = config or TableRowsConfig()
    blocks = _blocks(result.lines, cfg)
    if len(blocks) < 2:
        return []
    from .scan import _band_of

    gutters = _prose_gutters(result) or _page_gutters(result, blocks, cfg)

    def band(block: _Block) -> int:
        return _band_of(block.extent.cx, gutters) if gutters else 0

    numbering = {b.index for b in blocks if _numbers_moves(b, cfg) or _lone_number(b)}

    def numbered_twice(block: _Block, group: Sequence[_Block]) -> bool:
        """The group would hold two numberings, or moves another column numbers: a
        numbering block outside the group stands between one of its numbering members
        and one of its plain members, at the plain member's heights (the moves of a
        page column whose numbers Tesseract cut into a block of their own)."""
        members = [*group, block]
        numbered = [m for m in members if m.index in numbering]
        if len(numbered) > 1:
            return True
        inside = {m.index for m in members}
        for n in numbered:
            for plain in (m for m in members if m.index not in numbering):
                low, high = sorted((n.extent.x0, plain.extent.x0))
                if any(x.index in numbering and x.index not in inside
                       and low < x.extent.x0 < high and _shares_rows(x, plain, cfg)
                       for x in blocks):
                    return True
        return False

    def crosses(block: _Block, group: Sequence[_Block]) -> bool:
        return _crosses_the_page([*group, block], band, cfg)

    kind = {b.index: ("moves" if _moveish(b, cfg) else "names" if _names(b, cfg)
                      else "values" if _values(b, cfg) else "")
            for b in blocks}

    def mixes(block: _Block, group: Sequence[_Block]) -> bool:
        """A game and a table in one group: a move list beside the standings of the tournament
        (crítico da fase 5, ciclo 5: «1 e4 e5 Aljechin 7½», 0,2218 → 0,7564).  A game's own
        columns are moves and numbers; a column of names is a table's."""
        kinds = {kind[m.index] for m in (*group, block)}
        return "moves" in kinds and bool(kinds & {"names", "values"})

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
    for seed in _seeds(blocks, cfg):
        if seed.index in taken:
            continue
        group = [seed]
        grew = True
        while grew:
            grew = False
            for block in blocks:
                if (block.index in taken or any(block is m for m in group)
                        or _is_prose(block, cfg) or crosses(block, group)
                        or numbered_twice(block, group) or mixes(block, group)
                        or not all(_one_row_high(block, m, cfg) for m in group)
                        or not beside(block, group)):
                    continue
                if (_partner_share(block, group, cfg) >= cfg.align_share
                        and _adjacent(block, group, blocks, cfg)):
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
    median extent, so a tall cell among three does not chain two rows into one
    (of two, the lower extent: a line two rows high never gets here,
    :func:`_one_row_high`).
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
