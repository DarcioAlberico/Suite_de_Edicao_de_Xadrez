"""A table read row by row, whatever blocks the engine cut it into — OCR_UI_ROADMAP_C2 passo B13.

The readings are built the way Tesseract in PSM 3 returned the golden corpus
items (``OCR_UI_REPORT_C2_FASE5.md`` §B13): ``table:7`` at 150 DPI came back as
four blocks — the name column, the first row's tail as one line, the places,
the openings with their page numbers — and the Dvoretsky move list as the
White column and the Black column.  The other side of the rule is the page it
must never touch: two columns of prose whose lines sit at the same heights.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from caissa.ocr.arbiter import Arbiter, ArbiterConfig, RegionTask
from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.layout.rows import TableRowsConfig, rows_of_tables, table_groups
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

CHAR_W = 9.0
LINE_H = 20.0


def _line(text: str, x: float, y: float, block: int, *, h: float = LINE_H) -> OcrLine:
    words = []
    for token in text.split():
        w = CHAR_W * len(token)
        words.append(OcrWord(text=token, box=BBox(x, y, w, h), confidence=0.9,
                             block_index=block))
        x += w + 7.0
    return OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words]),
                   block_index=block)


def _reading(lines: list[OcrLine], *, psm: int = 3) -> OcrResult:
    return OcrResult(engine="tesseract", lang="por", lines=tuple(lines),
                     region_kind=RegionKind.PAGE, duration_s=0.1, meta={"psm": psm})


# --------------------------------------------------------------------------- #
# The shapes of the corpus
# --------------------------------------------------------------------------- #


ROWS_Y = [25.0, 60.0, 95.0, 130.0, 165.0]


def table_7_at_150_dpi() -> OcrResult:
    """``table:7`` as PSM 3 cut it: names (b1), the first row's tail as one
    line (b2), places (b3), openings + page numbers (b4)."""
    names = ["36. Lasker — Rubinstein", "37. Alekhine — Euwe", "38. Petrosian — Spassky",
             "39. Karpov — Korchnoi", "40. Kramnik — Leko"]
    lines = [_line(n, 20.0, y, 1) for n, y in zip(names, ROWS_Y, strict=True)]
    lines.append(_line("São Petersburgo 1914 Espanhola 56", 268.0, ROWS_Y[0] - 4, 2))
    places = ["Haia 1937", "Moscovo 1966", "Baguio 1978", "Brissago 2004"]
    lines += [_line(p, 268.0, y, 3) for p, y in zip(places, ROWS_Y[1:], strict=True)]
    openings = ["Eslava 140", "Inglesa 77", "Espanhola, Aberta 230", "Petroff 184"]
    lines += [_line(o, 490.0, y - 5, 4) for o, y in zip(openings, ROWS_Y[1:], strict=True)]
    return _reading(lines)


def move_list() -> OcrResult:
    """The Dvoretsky move list: White's column, then Black's."""
    white = ["45 ♔g1", "46 ♖a5"]
    black = ["♔g6", "g3!"]
    lines = [_line(t, 0.0, 1.0 + 58.0 * n, 1) for n, t in enumerate(white)]
    lines += [_line(t, 408.0, 0.0 + 60.0 * n, 2) for n, t in enumerate(black)]
    return _reading(lines)


def two_prose_columns() -> OcrResult:
    """Two columns of prose, PSM 3 one block each, every line at the same
    height as its neighbour across the gutter (a book set on a baseline grid)."""
    left = ["After the exchange of queens the endgame is", "clearly better for White because the black",
            "pawns on the queenside are weak and the king", "cannot reach the centre in time to help them"]
    right = ["The same idea appears in a later game where", "Black defended better and held the draw by",
             "keeping the rook active behind the passed pawn", "which is the lesson of the whole chapter here"]
    lines = [_line(t, 20.0, y, 1) for t, y in zip(left, ROWS_Y, strict=False)]
    lines += [_line(t, 480.0, y, 2) for t, y in zip(right, ROWS_Y, strict=False)]
    return _reading(lines)


# --------------------------------------------------------------------------- #
# The rule
# --------------------------------------------------------------------------- #


def test_a_table_cut_into_column_blocks_is_read_row_by_row() -> None:
    read = rows_of_tables(table_7_at_150_dpi())
    assert [line.text for line in read.lines] == [
        "36. Lasker — Rubinstein São Petersburgo 1914 Espanhola 56",
        "37. Alekhine — Euwe Haia 1937 Eslava 140",
        "38. Petrosian — Spassky Moscovo 1966 Inglesa 77",
        "39. Karpov — Korchnoi Baguio 1978 Espanhola, Aberta 230",
        "40. Kramnik — Leko Brissago 2004 Petroff 184",
    ]
    assert read.meta["table_rows"] == 1


def test_a_move_list_reads_each_move_beside_its_reply() -> None:
    read = rows_of_tables(move_list())
    assert [line.text for line in read.lines] == ["45 ♔g1 ♔g6", "46 ♖a5 g3!"]


def test_two_columns_of_prose_are_never_a_table() -> None:
    reading = two_prose_columns()
    assert table_groups(reading) == []
    assert rows_of_tables(reading) is reading


PROSE = ["after", "the", "exchange", "of", "queens", "the", "endgame", "is", "clearly", "better", "for", "white", "because", "the", "black", "pawns", "on", "the", "queenside", "are", "weak", "and", "the", "king", "cannot", "reach", "the", "centre", "in", "time", "to", "help", "them", "so", "the", "knight", "goes", "to", "c5", "and", "the", "rook", "to", "the", "seventh", "rank", "where", "it", "ties", "the", "black", "pieces", "down", "until", "the", "white", "king", "walks", "in", "and", "the", "pawns", "fall", "one", "by", "one"]


def _justified(x0: float, x1: float, y: float, block: int, start: int) -> OcrLine:
    """A justified line of prose, as a book sets a column: the words of :data:`PROSE` from
    ``start`` that fit between ``x0`` and ``x1``, the spaces stretched to reach both edges.
    Each line starts at another word, so its spaces fall elsewhere -- as on a real page,
    where no space runs down every line of a column."""
    tokens: list[str] = []
    k = start
    while True:
        token = PROSE[k % len(PROSE)]
        if CHAR_W * (len("".join(tokens)) + len(token)) + 6.0 * len(tokens) > x1 - x0:
            break
        tokens.append(token)
        k += 1
    space = (x1 - x0 - CHAR_W * len("".join(tokens))) / (len(tokens) - 1)
    words, x = [], x0
    for token in tokens:
        w = CHAR_W * len(token)
        words.append(OcrWord(text=token, box=BBox(x, y, w, LINE_H), confidence=0.9,
                             block_index=block))
        x += w + space
    return OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words]), block_index=block)


def _column_prose(y: float, block: int, *, x: float = 0.0, lines: int = 4,
                  width: float = 460.0) -> list[OcrLine]:
    """Prose that fills a column ``width`` px wide: the text above a move list in a book."""
    return [_justified(x, x + width, y + 30.0 * n, block, start=7 * n + block)
            for n in range(lines)]


def test_a_column_of_prose_beside_a_table_does_not_join_it() -> None:
    """A tall prose block with a few lines at the table's heights: the partner
    share is low and prose never joins -- only the table's own columns merge.
    (The list sits under prose of its own column, as in a book.)"""
    above = _column_prose(-140.0, 8)
    prose = [_line("the long column of analysis goes on and on here", 600.0, 10.0 + 35.0 * n, 9)
             for n in range(12)]
    reading = _reading(above + list(move_list().lines) + prose)
    groups = table_groups(reading)
    assert groups == [[1, 2]]
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert texts[4:6] == ["45 ♔g1 ♔g6", "46 ♖a5 g3!"]
    assert texts[6:] == [line.text for line in prose]


def test_a_column_of_moves_with_a_line_of_prose_does_not_pull_the_other_column() -> None:
    """Levenfis p. 40 (two-column scan): the right column's block is short move lines and one
    line of prose; two left-column fragments sit at the height of its last lines.  Seeded by
    the right block, the group pulled the whole right column into the middle of the left one.
    Two rules keep it out, each on its own: a block with a line of prose is not a column of
    cells, and the gap to it holds the page's gutter.  The left move list still pairs up."""
    right = [_line(t, 888.0, 1819.0 + 36.0 * n, 30) for n, t in enumerate(
        ["ks Dd4—c5", "2. Re7—b7", "3. Rb7—c8", "4. Rc8—d8",
         "Scopul a fost atins, tempoul a", "fost cîştigat.", "4... Rb3—c4",
         "5. Rd8—e7", "6. Re7—e8", "7. Re8—f7"])]
    left_black = [_line("Dd4—c5", 616.0, 2107.0, 13), _line("De5—a5", 616.0, 2143.0, 13)]
    left_white = [_line("2. Re7—b7", 229.0, 2143.0, 18)]
    left_prose = _column_prose(1800.0, 5, x=150.0, lines=8, width=650.0)
    reading = _reading(left_prose + left_black + left_white + right)
    # the sabotage: without the ceiling on a cell's longest line and without the gutter
    # rules (the corridor, and the page's gutter, which needs prose beside it), the right
    # column seeds and pulls the left fragments
    neither = TableRowsConfig(cell_max_chars=999, gutter_min_lines=10**6, prose_words=999,
                              prose_chars=999)
    assert any(30 in group for group in table_groups(reading, config=neither))
    for alone in (TableRowsConfig(gutter_min_lines=10**6), TableRowsConfig(cell_max_chars=999)):
        assert all(30 not in group for group in table_groups(reading, config=alone))
    groups = table_groups(reading)
    assert all(30 not in group for group in groups)
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert texts[-len(right):] == [line.text for line in right], "the right column stays whole and last"
    assert "2. Re7—b7 De5—a5" in texts


def test_a_gap_no_other_line_touches_is_the_page_gutter() -> None:
    """The same two columns of short cells: across the page's gutter (no other line of the
    page touches the gap) they are two columns; under prose that runs across the gap they are
    a move list.  The page is the Levenfis p. 40's kind -- prose on the left, a move list on
    the right -- where the B1 decision does not read two columns of prose (the right band's
    median line is a move), so the corridor is the only rule between them."""
    cells = [_line(f"{n}. Kf{n}", 100.0, 300.0 + 30.0 * n, 2) for n in range(3)]
    cells += [_line(f"Kd{n}", 620.0, 300.0 + 30.0 * n, 3) for n in range(3)]
    # the other lines of the page: prose in the left column (0–460), moves in the right (600–)
    moves = [_line(f"{n + 5}. Rd{n}—e7", 600.0, 30.0 * n, 4) for n in range(8)]
    columns = _column_prose(-100.0, 1, lines=10) + moves
    assert table_groups(_reading(columns + cells)) == []
    # the sabotage: without the gutter rules (the corridor, and the page's gutter, which
    # needs prose beside it) they join across the page's gutter
    blind = TableRowsConfig(gutter_min_lines=10**6, prose_words=999, prose_chars=999)
    assert table_groups(_reading(columns + cells), config=blind) == [[2, 3]]
    # the same cells with prose of their own column running across the gap: a move list
    across = _column_prose(200.0, 5, x=100.0, lines=3, width=560.0)
    assert table_groups(_reading(columns + across + cells)) == [[2, 3]]


def test_on_two_prose_columns_a_move_list_is_read_by_rows_inside_its_column() -> None:
    """A page of two columns of prose (the B1 decision), each with a two-cell move list at the
    same heights: each list pairs up inside its column, and no group crosses the gutter."""
    prose = "the black king cannot reach the pawn in time and white wins easily"
    lines = []
    for n in range(14):
        y = 40.0 + 30.0 * n
        if n in (6, 7):
            lines += [_line(f"{n}. Kf{n}", 20.0, y, 2), _line(f"Kd{n}", 260.0, y, 3),
                      _line(f"{n}. Rh{n}", 640.0, y, 6), _line(f"Ra{n}", 880.0, y, 7)]
        else:
            lines += [_line(prose[:44], 20.0, y, 1 if n < 6 else 4),
                      _line(prose[5:49], 640.0, y, 5 if n < 6 else 8)]
    reading = _reading(lines)
    groups = table_groups(reading)
    assert sorted(sorted(g) for g in groups) == [[2, 3], [6, 7]]
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert "6. Kf6 Kd6" in texts and "6. Rh6 Ra6" in texts


def table_4_at_150_dpi() -> OcrResult:
    """``table:4`` as PSM 3 cut it at 150 DPI -- the blocks, texts and positions of the
    product's reading (``OCR_UI_REPORT_C2_FASE5.md`` §B13): eighteen lines, and a free
    corridor between the openings and the page numbers that none of them crosses."""
    lines = [_line(t, 20.0, 23.0 + 36.0 * n, 1) for n, t in enumerate(
        ["21. Anand — Kramnik", "22. Carisen — Nakamura", "23. Steinitz — Zukertort",
         "24. Lasker — Rubinstein", "25. Alekhine — Euwe"])]
    lines += [_line(t, 246.0, 22.0 + 36.0 * n, 2) for n, t in enumerate(
        ["Bona 2008", "Wijk aan Zee 2011", "St. Louis 1886"])]
    lines.append(_line("Gambito da Dama Recusado 88", 456.0, 18.0, 3))
    lines.append(_line("Índia do Rei", 456.0, 52.0, 4))
    lines.append(_line("Abertura Escocesa", 456.0, 90.0, 5))
    lines.append(_line("São Petersburgo 1914 Espanhola", 248.0, 124.0, 6))
    lines.append(_line("Haia 1937", 248.0, 162.0, 7))
    lines.append(_line("Eslava", 458.0, 160.0, 8))
    lines += [_line(t, 724.0, 53.0 + 36.0 * n, 9) for n, t in enumerate(["301", "15", "56", "140"])]
    return _reading(lines)


def test_a_table_s_own_column_gaps_are_not_a_gutter() -> None:
    """Nothing crosses the gaps between a table's columns -- not even on a crop of eighteen
    lines; only running text tells a page's gutter from them, and a table has none."""
    read = rows_of_tables(table_4_at_150_dpi())
    assert [line.text for line in read.lines] == [
        "21. Anand — Kramnik Bona 2008 Gambito da Dama Recusado 88",
        "22. Carisen — Nakamura Wijk aan Zee 2011 Índia do Rei 301",
        "23. Steinitz — Zukertort St. Louis 1886 Abertura Escocesa 15",
        "24. Lasker — Rubinstein São Petersburgo 1914 Espanhola 56",
        "25. Alekhine — Euwe Haia 1937 Eslava 140",
    ]
    assert read.meta["table_rows"] == 1


def test_the_tallest_column_of_cells_seeds_the_table() -> None:
    """``table:4``: two one-line cells of the last row would, seeded in reading
    order, make a group of their own and split that row."""
    names = ["21. Anand — Kramnik", "22. Carlsen — Nakamura", "23. Steinitz — Zukertort",
             "24. Lasker — Rubinstein", "25. Alekhine — Euwe"]
    lines = [_line(n, 20.0, y, 1) for n, y in zip(names, ROWS_Y, strict=True)]
    lines.append(_line("Bona 2008 Gambito da Dama Recusado 88", 246.0, ROWS_Y[0], 2))
    lines += [_line(t, 246.0, y, 3) for t, y in
              (("Wijk aan Zee 2011", ROWS_Y[1]), ("St. Louis 1886", ROWS_Y[2]))]
    lines.append(_line("São Petersburgo 1914 Espanhola", 246.0, ROWS_Y[3], 4))
    lines.append(_line("Haia 1937", 246.0, ROWS_Y[4], 5))
    lines.append(_line("Eslava", 456.0, ROWS_Y[4] - 2, 6))
    lines += [_line(n, 724.0, y - 3, 7) for n, y in zip(["301", "15", "56", "140"], ROWS_Y[1:], strict=True)]
    read = rows_of_tables(_reading(lines))
    assert [line.text for line in read.lines][-1] == "25. Alekhine — Euwe Haia 1937 Eslava 140"
    assert read.meta["table_rows"] == 1


def test_a_single_block_is_left_alone() -> None:
    reading = _reading([_line("1 d4 ♘f6 2 c4 c5", 0.0, 0.0, 1), _line("3 ♘f3 cxd4", 0.0, 30.0, 1)])
    assert rows_of_tables(reading) is reading


def test_the_row_keeps_the_leftmost_baseline_on_the_merged_box() -> None:
    left = replace(_line("45 ♔g1", 10.0, 100.0, 1), baseline=(0.0, -4.0))
    right = _line("♔g6", 400.0, 96.0, 2)
    extra_left = _line("46 ♖a5", 10.0, 160.0, 1)
    extra_right = _line("g3!", 400.0, 158.0, 2)
    read = rows_of_tables(_reading([left, extra_left, right, extra_right]))
    first = read.lines[0]
    assert first.text == "45 ♔g1 ♔g6"
    # the absolute baseline under x0 is the left cell's: 100 + 20 - 4 = 116
    assert abs(first.baseline_y_at(first.box.x0) - 116.0) < 1e-6


# --------------------------------------------------------------------------- #
# The critic's pages (fase 5, ciclo 1): narrow columns, numbered flows, stray gaps
# --------------------------------------------------------------------------- #

GRID = 49.0   # the Gallagher's baseline grid at 300 DPI


def gallagher_p50() -> OcrResult:
    """The Gallagher (``Winning With the King's Gambit``) p. 50 as PSM 3 cut it (the
    critic's trace): two columns of 22–27 characters, notes and moves on the left, a move
    list in three blocks on the right -- the numbers, White's moves, Black's."""
    def at(n: int) -> float:
        return 265.0 + GRID * n

    lines = [_line(t, 152.0, at(n), 1) for n, t in enumerate(
        ["position.", "18 Rad1 a6", "19 Bc4 Rc8", "20 Rhe1 g5!?"])]
    notes = ["The best chance to get", "his rook into the game, but", "of course the dark squares",
             "are now terribly weak.", "21 Be5", "It could well have been", "time to part with the two",
             "bishops. 21 Bd6 looks good", "for White."]
    lines += [_line(t, 149.0, at(4 + n), 2) for n, t in enumerate(notes)]
    lines += [_line(t, 266.0, at(13 + n), 3) for n, t in enumerate(
        ["21... Rg8", "22 g4 Rg6", "23 b4 b5", "24 Bd5 Nd7", "25 Bd4 Bf6!"])]
    lines += [_line(t, 145.0, at(18 + n), 4) for n, t in enumerate(
        ["Now Black is able to ex-", "change the bishops under", "more favourable circum-",
         "stances. Although White", "still has an edge, his own"])]
    lines.append(_line("Cunningham Defence 51", 897.0, 176.0, 5))
    lines += [_line(t, 817.0, at(n), 6) for n, t in enumerate(
        ["weaknesses give Black just", "enough play to hold the"])]
    lines.append(_line("draw.", 816.0, at(2), 7))
    lines += [_line(str(26 + n), 936.0, at(3 + n), 7) for n in range(20)]
    lines += [_line(t, 1025.0, at(3 + n), 8) for n, t in enumerate(["Re3", "Bxd4"])]
    black = ["Bxd4", "Rd6", "Rf6+", "Rc7", "Nb6", "Nc4", "h6", "gh+", "Re7", "hg+", "Re1", "Rf4+",
             "Rxg4+", "Re4", "Re3", "Rxc3", "Na3", "Rc2", "Rxa2", "1/2-1/2"]
    lines += [_line(t, 1193.0, at(3 + n), 9) for n, t in enumerate(black)]
    return _reading(lines)


def _crosses(groups: list[list[int]], left: set[int], right: set[int]) -> bool:
    return any(set(g) & left and set(g) & right for g in groups)


def test_a_narrow_column_of_notes_never_joins_the_move_list_of_the_other_column() -> None:
    """Gallagher p. 50 (crítico da fase 5): no line reaches 30 characters, so the prose rule
    by length never fired, the corridor was never judged, and the right column's move numbers
    pulled the left column's notes and moves into their rows -- CER 0,27 → 0,70 on the page.
    The notes are prose by **words**, the left column's moves are numbered on their own, and
    the page's gutter has prose on both sides: the move list pairs up inside its column."""
    reading = gallagher_p50()
    groups = table_groups(reading)
    assert sorted(sorted(g) for g in groups) == [[7, 8, 9]]
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert "26 Re3 Bxd4" in texts and "The best chance to get" in texts
    # the sabotage: without the prose by words and the numbering, the columns interleave
    blind = TableRowsConfig(prose_words=999, numbered_share=2.0)
    assert _crosses(table_groups(reading, config=blind), {1, 2, 3, 4}, {6, 7, 8, 9})


def test_two_numbered_columns_are_two_games_not_a_move_list() -> None:
    """Two games side by side (the critic's page, CER 0,0190 → 0,5625): each column numbers
    its own moves, and a move list has one column of numbers -- never two."""
    moves = ["e4 c5", "Nf3 d6", "d4 cxd4", "Nxd4 Nf6", "Nc3 a6", "Bg5 e6", "f4 Be7", "Qf3 Qc7"]
    left = [_line(f"{n + 1}. {m}", 150.0, 100.0 + 50.0 * n, 1) for n, m in enumerate(moves)]
    right = [_line(f"{n + 1}. {m}", 850.0, 100.0 + 50.0 * n, 2) for n, m in enumerate(reversed(moves))]
    reading = _reading(left + right)
    assert table_groups(reading) == []
    assert rows_of_tables(reading) is reading
    assert table_groups(reading, config=TableRowsConfig(numbered_share=2.0)) == [[1, 2]]


def test_moves_numbered_by_their_own_column_do_not_join_another_numbering() -> None:
    """One game in two page columns, 1–20 | 21–40, under a full-width heading (the critic's
    page, 0,2241 → 0,4152): Tesseract cut the right column's numbers into a block of their
    own (``21`` alone, then ``22.``, ``23.``…) and left its moves unnumbered, so the right
    moves looked like the Black replies of the left column.  Their own numbering stands
    between them and the left one; the right column pairs up with its numbers instead."""
    heading = ["Game 12  B. Spassky - R. Fischer, Reykjavik 1972",
               "The sixth game of the match was a quiet Sicilian that turned sharp once White",
               "castled long and threw his kingside pawns forward; the notes are the winner's."]
    lines = [_line(t, 151.0, 159.0 + 50.0 * n, 1) for n, t in enumerate(heading)]
    moves = ["e4 c5", "Nf3 d6", "d4 cxd4", "Nxd4 Nf6", "Nc3 a6", "Bg5 e6", "f4 Be7", "Qf3 Qc7"]
    lines += [_line(f"{n + 1}. {m}", 151.0, 341.0 + 50.0 * n, 2) for n, m in enumerate(moves)]
    lines.append(_line("21", 946.0, 341.0, 3))
    lines += [_line(f"{22 + n}.", 946.0, 391.0 + 50.0 * n, 4) for n in range(7)]
    lines += [_line(m, 1006.0, 391.0 + 50.0 * n, 5) for n, m in enumerate(moves[1:])]
    reading = _reading(lines)
    groups = table_groups(reading)
    assert not _crosses(groups, {2}, {3, 4, 5})
    assert sorted(sorted(g) for g in groups) == [[4, 5]]
    # the sabotage: without the numbering rules the right moves answer the left column
    assert _crosses(table_groups(reading, config=TableRowsConfig(numbered_share=2.0)), {2}, {5})


def test_a_paragraph_with_a_stray_gap_is_prose_not_a_row_of_cells() -> None:
    """Kmoch p. 44 (crítico da fase 5): a paragraph whose lines end in a stray ``|`` has an
    internal gutter, and the gutter made it cells -- it seeded a group with a fragment of
    the other column.  Cut at its gutter, its widest cell holds a line of prose."""
    paragraph = ["(Een duidelijke wenk tot", "remise, dien de tegenstander", "dadelijk begrijpt nu wel.)"]
    lines = []
    for n, text in enumerate(paragraph):
        y = 774.0 + 50.0 * n
        words = (*_line(text, 842.0, y, 20).words, *_line("| 17. Kf2", 1300.0, y, 20).words)
        lines.append(OcrLine(words=words, box=BBox.union_of([w.box for w in words]), block_index=20))
    lines.append(_line("Pd5: |", 692.0, 774.0 + 50.0, 12))
    reading = _reading(lines)
    assert table_groups(reading) == []
    assert table_groups(reading, config=TableRowsConfig(prose_words=999)) == [[20, 12]]


def _split_heading() -> OcrResult:
    """Gallagher p. 52: «The so-called “Long» cut into ``The``, ``“Long`` and a paragraph
    that begins with ``so-called`` -- three blocks on one line."""
    lines = [_line("The", 193.0, 1026.0, 8), _line("“Long", 622.0, 1027.0, 6)]
    para = ["so-called", "Whip” variation. The fact", "that it is not seen very", "often these days does not"]
    lines += [_line(t, 290.0 if n == 0 else 145.0, 1026.0 + 48.0 * n, 7) for n, t in enumerate(para)]
    return _reading(lines)


def test_two_words_with_a_third_between_them_are_not_a_row_of_cells() -> None:
    reading = _split_heading()
    assert table_groups(reading) == []
    assert rows_of_tables(reading) is reading


def test_the_sabotage_without_adjacency_pairs_the_words_around_the_third(monkeypatch) -> None:
    import caissa.ocr.layout.rows as rows

    monkeypatch.setattr(rows, "_adjacent", lambda *args: True)
    assert sorted(sorted(g) for g in rows.table_groups(_split_heading())) == [[6, 8]]


def test_merged_cells_count_their_words_cell_by_cell() -> None:
    """``table:2`` at 150 DPI: Tesseract read three cells of each row as one line
    (``Bona 2008 | Gambito da Dama Recusado | 88``).  Six words in the line, four in the widest
    cell: a row of cells, not a line of prose -- the table still reads by rows."""
    reading = _merged_cells_reading()
    assert sorted(sorted(g) for g in table_groups(reading)) == [[2, 3]]
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert "13. Anand — Kramnik Bona 2008 Gambito da Dama Recusado 88" in texts


def test_the_sabotage_counting_words_across_cells_makes_the_row_prose(monkeypatch) -> None:
    import caissa.ocr.layout.rows as rows

    monkeypatch.setattr(rows, "_cell_words", lambda line, spans: rows._words(line.text))
    assert rows.table_groups(_merged_cells_reading()) == []


def _merged_cells_reading() -> OcrResult:
    """``table:2`` at 150 DPI: the header row alone, the names, and the other three cells
    of each row read as one line with gaps between them."""
    names = ["12. Tal — Botvinnik", "13. Anand — Kramnik", "14. Carlsen — Nakamura",
             "15. Steinitz — Zukertort"]
    cells = [("Moscovo 1960", "Francesa, Winawer", "203"), ("Bona 2008", "Gambito da Dama Recusado", "88"),
             ("Wijk aan Zee 2011", "Índia do Rei", "301"), ("St. Louis 1886", "Abertura Escocesa", "15")]
    lines = [_line("11. Capablanca - Marshall Nova Iorque 1918 Ruy López 9", 21.0, 22.0, 1)]
    for n, (name, row) in enumerate(zip(names, cells, strict=True)):
        y = 61.0 + 32.0 * n
        lines.append(_line(name, 21.0, y, 2))
        words = [*_line(row[0], 289.0, y, 3).words, *_line(row[1], 480.0, y, 3).words,
                 *_line(row[2], 760.0, y, 3).words]
        lines.append(OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words]), block_index=3))
    return _reading(lines)


def test_config_shares_are_the_rules_numbers() -> None:
    cfg = TableRowsConfig()
    assert cfg.cell_chars == 12 and cfg.align_share == 0.8 and cfg.overlap == 0.5


# --------------------------------------------------------------------------- #
# Where it runs: the arbiter, on a segmenting PSM, behind the switch
# --------------------------------------------------------------------------- #


class _FakeTesseract:
    """An engine that returns a fixed reading, as Tesseract would in ``psm``."""

    name = "tesseract"

    def __init__(self, reading: OcrResult) -> None:
        self.reading = reading

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(level=EngineLevel.TESSERACT, cost_per_megapixel_s=1.0,
                                  supports_char_boxes=False, supports_confidence=True)

    def available(self) -> bool:
        return True

    def supports_language(self, lang: str) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def recognize(self, image, *, lang="por", psm_hint=RegionKind.PARAGRAPH) -> OcrResult:
        return self.reading


def _arbitrate(reading: OcrResult, *, table_rows: bool) -> OcrResult:
    arbiter = Arbiter([_FakeTesseract(reading)], ArbiterConfig(table_rows=table_rows))
    task = RegionTask(image=np.full((200, 800), 255, np.uint8), region_kind=RegionKind.PAGE,
                      lang="por")
    return arbiter.run(task).result


def test_the_arbiter_reads_a_psm_3_table_by_rows() -> None:
    result = _arbitrate(move_list(), table_rows=True)
    assert [line.text for line in result.lines] == ["45 ♔g1 ♔g6", "46 ♖a5 g3!"]


def test_the_sabotage_switch_gives_back_the_column_order() -> None:
    result = _arbitrate(move_list(), table_rows=False)
    assert [line.text for line in result.lines] == ["45 ♔g1", "46 ♖a5", "♔g6", "g3!"]


def test_a_single_block_psm_is_not_touched() -> None:
    reading = replace(move_list(), meta={"psm": 6})
    result = _arbitrate(reading, table_rows=True)
    assert [line.text for line in result.lines] == ["45 ♔g1", "46 ♖a5", "♔g6", "g3!"]


def test_the_service_switch_reaches_the_page_arbiter() -> None:
    from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig

    on = OcrService([_FakeTesseract(move_list())], config=OcrServiceConfig())
    off = OcrService([_FakeTesseract(move_list())], config=OcrServiceConfig(table_rows=False))
    assert on.recognizer_for("por").config.arbiter.table_rows is True
    assert off.recognizer_for("por").config.arbiter.table_rows is False
