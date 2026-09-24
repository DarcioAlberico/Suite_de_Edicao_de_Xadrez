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


def _line(text: str, x: float, y: float, block: int, *, h: float = LINE_H,
          char_w: float = CHAR_W) -> OcrLine:
    words = []
    for token in text.split():
        w = char_w * len(token)
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
    # rules (the corridor, and the page's gutter, which needs prose beside it -- by length,
    # by words or as running text -- or a game beside text), the right column seeds and
    # pulls the left fragments
    neither = TableRowsConfig(cell_max_chars=999, gutter_min_lines=10**6, prose_words=999,
                              prose_chars=999, running_lines=10**6, game_min_lines=10**6)
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
    # the sabotage: without the prose by words, the running text (ciclo 3), the numbering and
    # the page's gutter by width (ciclo 2), the columns interleave
    blind = TableRowsConfig(prose_words=999, numbered_share=2.0, page_band_share=2.0,
                            running_lines=10**6)
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
    blind = TableRowsConfig(numbered_share=2.0, page_band_share=2.0)
    assert table_groups(reading, config=blind) == [[1, 2]]


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
    # the stray cell (``| 17. Kf2``) puts a move number inside every line, so the notes are
    # turned off with the prose by words and the page's gutter
    blind = TableRowsConfig(prose_words=999, page_band_share=2.0, notes_share=2.0)
    assert table_groups(reading, config=blind) == [[20, 12]]


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
    # the lines of cells continue nothing, so the continuation is turned off with it
    assert rows.table_groups(_merged_cells_reading(),
                             config=TableRowsConfig(prose_continued=0.0)) == []


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


# --------------------------------------------------------------------------- #
# The critic's pages (fase 5, ciclo 2): no prose to judge the gutter by
# --------------------------------------------------------------------------- #


INDEX_LEFT = ["Radulescu 8", "Ragozin 24", "Rashkovsky 132", "Reshko 38, 53", "Ribli 158",
              "Robatsch 178", "Rytov 137", "Sakharov 47", "Sanguinetti 37", "Santo-Roman 210",
              "Schmid 69", "Seirawan 165, 179", "Short 166", "Sigurjonsson 156", "Simagin 20",
              "Smyslov 9"]
INDEX_RIGHT = ["Bennett 218", "Berliner 258", "Bisguier 240, 260", "Bolbochan 250", "Bredoff 217",
               "Byrne D. 211", "Byrne R. 255, 271, 304", "Camara 300", "Ciocaltea 251", "Darga 244",
               "Dely 272", "Di Camillo 212", "Donner 270", "Durao 263", "Eliskases 257"]


def karpov2_p268() -> OcrResult:
    """The Karpov 2 (``Chess Combinations -- World Champions 2``) p. 268 as PSM 3 cut it (the
    critic's trace): an index of names in two columns -- the folio, the left column (b4), the
    right column's first entry alone (b6) and the rest of it (b7); every line a name and pages,
    no line of prose."""
    lines = [_line("268", 120.0, 77.0, 1)]
    lines += [_line(t, 133.0, 188.0 + 44.0 * n, 4) for n, t in enumerate(INDEX_LEFT)]
    lines.append(_line("Benko 221, 246, 256, 261", 1002.0, 187.0, 6))
    lines += [_line(t, 1002.0, 232.0 + 44.0 * n, 7) for n, t in enumerate(INDEX_RIGHT)]
    return _reading(lines)


def test_an_index_in_two_columns_is_two_lists_not_a_table() -> None:
    """Karpov 2 p. 268 (crítico da fase 5, ciclo 2): no prose on the page, so the gutter the
    rule itself found was dropped, and every line joined two entries of the two columns --
    «Ragozin 24 Bennett 218», CER 0,76 against the book's order.  One gutter that leaves two
    bands of comparable width is the page's gutter, prose or no prose."""
    reading = karpov2_p268()
    assert not _crosses(table_groups(reading), {4}, {6, 7})
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert "Ragozin 24" in texts and "Bennett 218" in texts
    # the sabotage: the gutter only with prose beside it, as in the second cycle (and without
    # the lists of one form of the sixth, which hold it too)
    blind = TableRowsConfig(page_band_share=2.0, list_listed_share=2.0)
    assert _crosses(table_groups(reading, config=blind), {4}, {6, 7})


def dvoretsky_13_278_52(right: list[str] | None = None,
                        left: list[str] | None = None) -> OcrResult:
    """``real:Dvoretsky…:13:278:52`` as PSM 3 cut it, at its own scale (a native page at
    300 DPI, ~20 px a character): White's column x 0–153, Black's 413–516 -- one gutter, the
    bands 0,67 of each other."""
    white = left or ["30 ♖c1", "31 ♘h1", "32 ♗xc5", "33 ♖xc5"]
    black = right or ["♗xd4", "♘xc5", "♖xc5", "♕xc5"]
    lines = [_line(t, 0.0, 1.0 + 58.0 * n, 1, char_w=20.0) for n, t in enumerate(white)]
    lines += [_line(t, 413.0, 58.0 * n, 2, char_w=20.0) for n, t in enumerate(black)]
    return _reading(lines)


def test_only_a_move_list_crosses_the_page_s_gutter(monkeypatch) -> None:
    """The Dvoretsky lists leave one gutter too, bands 0,65–0,85 of each other: the numbers and
    White's moves on the left, one move a line on the right.  That is the positive evidence of
    a table two lists of names never give -- and a right column with numbers of its own (pages,
    or its own move numbers) keeps the gutter."""
    from caissa.ocr.layout.scan import find_gutters

    reading = dvoretsky_13_278_52()
    assert len(find_gutters(reading.lines)) == 1
    assert sorted(sorted(g) for g in table_groups(reading)) == [[1, 2]]
    assert [line.text for line in rows_of_tables(reading).lines][0] == "30 ♖c1 ♗xd4"
    assert table_groups(dvoretsky_13_278_52(["♗xd4 12", "♘xc5 14", "♖xc5 15", "♕xc5 19"])) == []
    # the sabotage: without the evidence, the move list stays by columns
    import caissa.ocr.layout.rows as rows

    monkeypatch.setattr(rows, "_numbers_column", lambda block, cfg: False)
    assert rows.table_groups(reading) == []


def test_an_evaluation_set_apart_is_part_of_its_move(monkeypatch) -> None:
    """A move list with its evaluations set apart from the moves (``31 ♘h1 !?``, ``♗xd4 +-``,
    the critic's list, ciclo 3): three tokens on a line, and the evidence refused it -- the
    list read by columns, 0,0603 → 0,6724.  An evaluation is part of its move."""
    reading = dvoretsky_13_278_52(right=["♗xd4 +-", "♘xc5", "♖xc5", "♕xc5 +-"],
                                  left=["30 ♖c1", "31 ♘h1 !?", "32 ♗xc5", "33 ♖xc5 !?"])
    assert sorted(sorted(g) for g in table_groups(reading)) == [[1, 2]]
    assert [line.text for line in rows_of_tables(reading).lines][1] == "31 ♘h1 !? ♘xc5"
    # the sabotage: the evaluation as a token of its own
    import caissa.ocr.layout.rows as rows

    monkeypatch.setattr(rows, "_move_tokens", lambda text: text.split())
    assert rows.table_groups(reading) == []


VARIATIONS = ["Or 21 Bd6 Rg8 22 g4 Rg6", "23 Bc5 b6 24 Be3 with an", "edge for White.",
              "21 Be5 Rg8 22 g4 Rg6 23", "b4 b5 24 Bd5 Nd7 25 Bd4", "Bf6! is the game.", "21 Bd6",
              "Rg8 22 g4 Rg6 23 Bc5 b6", "24 Be3 Nd7 is unclear."]
VARIATIONS_TAIL = ["26 Bxf6 Nxf6 27 Re7 Rc7", "28 Rxc7 Kxc7 29 Kf3 Nd7", "30 Ke4 Kd6 31 c4 c5 is",
                   "equal: 32 b3 b6 33 a4", "a5 34 h4 h6 35 g3 Ke6."]


def gallagher_p50_with_variations() -> OcrResult:
    """The Gallagher p. 50 with the notes written as variations (the critic's construction,
    ciclo 2): a word or two a line, no block of prose anywhere -- not even at the top of the
    right column."""
    reading = gallagher_p50()
    notes = {2: VARIATIONS, 4: VARIATIONS_TAIL, 6: ["26 Bxf6 Nxf6 27 Re7", "Rc7 28 Rxc7 Kxc7 is"]}
    lines = []
    for block in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        members = [line for line in reading.lines if line.block_index == block]
        if block in notes:
            members = [_line(text, line.box.x0, line.box.y0, block)
                       for line, text in zip(members, notes[block], strict=False)]
        lines += members
    return _reading(lines)


def test_notes_of_variations_are_running_text_not_cells() -> None:
    """A line with move numbers inside it -- «Or 21 Bd6 Rg8 22 g4 Rg6» -- is a note, not a
    row: the column of variations never joins the move list of the other column."""
    reading = gallagher_p50_with_variations()
    groups = table_groups(reading)
    assert not _crosses(groups, {1, 2, 3, 4}, {6, 7, 8, 9})
    # the sabotage: without the notes, the variations join the other column's move list
    # (the game beside text holds the gutter too, since the fourth cycle)
    blind = TableRowsConfig(notes_share=2.0, page_band_share=2.0, game_min_lines=10**6)
    assert _crosses(table_groups(reading, config=blind), {1, 2, 3, 4}, {6, 7, 8, 9})


NOTES_BESIDE_THE_GAME = [
    "Or 21 Bd6 Rg8 22 g4 Rg6", "23 Bc5 b6 24 Be3 with an", "edge for White.",
    "21...Rg8 22 g4 Rg6 23 b4", "b5 24 Bd5 Nd7 25 Bd4 Bf6!", "Now Black can swap the",
    "bishops: 26 Re3 Bxd4 27", "Rxd4 Rd6 28 Bb7 Rf6+ 29", "Kg3 Rc7 30 Bf3 Nb6 31",
    "Red3 Nc4 32 Rd5 h6 33", "h4 gxh4+ 34 Kxh4 Re7 is", "equal, as 35 g5 hxg5+"]
THE_GAME = ["26 Re3 Bxd4", "27 Rxd4 Rd6", "28 Bb7 Rf6+", "29 Kg3 Rc7", "30 Bf3 Nb6", "31 Red3 Nc4",
            "32 Rd5 h6", "33 h4 gxh4+", "34 Kxh4 Re7", "35 g5 hxg5+", "36 Rxg5 Re1", "37 Rd1 Rf4+"]


def test_notes_beside_the_game_in_two_narrow_columns_stay_in_their_column() -> None:
    """The critic's page set as the Gallagher p. 50 (``b13_estreita.py``, ciclo 2): notes of
    variations on the left, the game's move list on the right, line for line -- read by the
    service it went 0,0113 → 0,5845 («Or 21 Bd6 Rg8 22 g4 Rg6 26 Re3 Bxd4»).  The notes are
    running text: they never join, and as prose beside the gutter they keep it.  The widths do
    not hold this page -- a move list's lines are short, so its band is half the notes' -- the
    notes do."""
    lines = [_line(t, 150.0, 300.0 + 50.0 * n, 1) for n, t in enumerate(NOTES_BESIDE_THE_GAME)]
    lines += [_line(t, 810.0, 300.0 + 50.0 * n, 2) for n, t in enumerate(THE_GAME)]
    reading = _reading(lines)
    assert table_groups(reading) == []
    assert table_groups(reading, config=TableRowsConfig(page_band_share=2.0)) == []
    # the sabotage: without the notes (and the game beside text), the variations and the
    # game interleave
    blind = TableRowsConfig(notes_share=2.0, game_min_lines=10**6)
    assert _crosses(table_groups(reading, config=blind), {1}, {2})


OPENINGS_WRITTEN_OUT = ["Defesa Francesa, Variante Winawer", "Gambito da Dama Recusado"]


def _openings_written_out() -> OcrResult:
    """The ``table:2`` with the openings written out (the critic's table, ciclo 2), as PSM 3
    cut it at 150 DPI: four words a cell, and the openings of two rows in one block."""
    lines = [_line("11. Capablanca - Marshall Nova Iorque 1918 Defesa Siciliana, Variante Najdorf 9",
                   21.0, 22.0, 1)]
    names = ["12. Tal — Botvinnik", "13. Anand — Kramnik", "14. Carlsen — Nakamura",
             "15. Steinitz — Zukertort"]
    lines += [_line(t, 21.0, 61.0 + 32.0 * n, 2) for n, t in enumerate(names)]
    lines += [_line(t, 289.0, 61.0 + 32.0 * n, 3) for n, t in enumerate(["Moscovo 1960", "Bona 2008"])]
    lines += [_line(t, 480.0, 61.0 + 32.0 * n, 4) for n, t in enumerate(OPENINGS_WRITTEN_OUT)]
    lines.append(_line("Wijk aan Zee 2011 Defesa Índia do Rei", 289.0, 125.0, 5))
    lines.append(_line("St. Louis 1886", 289.0, 157.0, 6))
    lines.append(_line("Abertura Escocesa, Variante Clássica", 480.0, 157.0, 7))
    lines += [_line(t, 860.0, 61.0 + 32.0 * n, 8) for n, t in enumerate(["203", "88", "301", "15"])]
    return _reading(lines)


def test_cells_of_four_words_that_continue_nothing_are_still_cells() -> None:
    """Prose by words needs lines that carry the sentence over (a lowercase start); a column
    of openings written out starts every line anew.  With the words alone the two openings
    left their rows and came out after the table (0,4646 → 0,3456; now 0,0113)."""
    reading = _openings_written_out()
    assert any(4 in g for g in table_groups(reading))
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert "12. Tal — Botvinnik Moscovo 1960 Defesa Francesa, Variante Winawer 203" in texts
    # the sabotage: prose by the words alone
    blind = TableRowsConfig(prose_continued=0.0)
    assert not any(4 in g for g in table_groups(reading, config=blind))


# --------------------------------------------------------------------------- #
# The critic's pages (fase 5, ciclo 3): ordinary notes in a narrow column
# --------------------------------------------------------------------------- #


ORDINARY_NOTES = ["White could also try", "21 Bd6!?, when after", "21...Rg8 22 g4 Rg6 the",
                  "position is unclear.", "Black's knight is", "strong on d7, but",
                  "White keeps an edge", "thanks to the bishop", "pair. Instead, 22 Bc5",
                  "b6 23 Be3 is met by", "23...Nd7 with equality.", "After the text move",
                  "Black is able to ex-", "change the bishops.", "Now 26 Re3 was best.",
                  "White's rooks are", "active, but Black", "holds the draw."]
GAME_UNTABBED = ["26 Re3 Bxd4", "27 Rxd4 Rd6", "28 Bb7 Rf6+", "29 Kg3 Rc7", "30 Bf3 Nb6",
                 "31 Red3 Nc4", "32 Rd5 h6", "33 h4 gxh4+", "34 Kxh4 Re7", "35 g5 hxg5+",
                 "36 Rxg5 Re1", "37 Rd1 Rf4+", "38 Rg4 Rxg4+", "39 Bxg4 Re4", "40 Rd4 Re3",
                 "41 Bc8 Rxc3", "42 Bxa6 Na3", "43 Kg5 Rc2"]


def _spread(text: str, x0: float, x1: float, y: float, block: int, *,
            char_w: float = CHAR_W) -> OcrLine:
    """A line of a justified column: spread to ``x1`` unless it ends its paragraph."""
    line = _line(text, x0, y, block, char_w=char_w)
    words = list(line.words)
    if text.endswith(".") or len(words) < 2:
        return line
    space = (x1 - x0 - sum(w.box.w for w in words)) / (len(words) - 1)
    spread, x = [], x0
    for word in words:
        spread.append(replace(word, box=BBox(x, word.box.y0, word.box.w, word.box.h)))
        x += word.box.w + space
    return replace(line, words=tuple(spread), box=BBox.union_of([w.box for w in spread]))


def ordinary_notes_beside_the_game(*, blocks: tuple[int, ...] = (18,),
                                   tab: float | None = None) -> OcrResult:
    """The critic's page set as the Gallagher p. 50 (``b13_fixture_notas_comuns.py``,
    ``b13_estreita3.py --justificar``, ciclo 3): ordinary notes justified in a column of
    1,95 in -- three words a line, a move here and there -- and the game's move list, set
    without tabs, in the other column; Times 10 pt at 300 DPI (~20 px a character, a line
    every 50 px).  ``blocks`` cuts the notes the way PSM 3 did (4, 3, 6 and 5 lines: blocks
    1–4), the game one block after them -- or two, with Black's moves at a ``tab`` (a share
    of the column, ``b13_tabulada.py``)."""
    lines, start = [], 0
    for index, size in enumerate(blocks, start=1):
        lines += [_spread(t, 150.0, 735.0, 300.0 + 50.0 * n, index, char_w=20.0)
                  for n, t in enumerate(ORDINARY_NOTES[start:start + size], start=start)]
        start += size
    game = len(blocks) + 1
    # set at a tab, the game ends in its result, as the Gallagher's does
    moves = GAME_UNTABBED if tab is None else [*GAME_UNTABBED, "44 Kf6 1/2-1/2"]
    for n, text in enumerate(moves):
        y = 300.0 + 50.0 * n
        if tab is None:
            lines.append(_line(text, 811.0, y, game, char_w=20.0))
            continue
        white, black = text.rsplit(" ", 1)
        lines.append(_line(white, 811.0, y, game, char_w=20.0))
        lines.append(_line(black, 811.0 + tab * 585.0, y, game + 1, char_w=20.0))
    return _reading(lines)


def test_ordinary_notes_beside_a_move_list_are_running_text() -> None:
    """The critic's page (ciclo 3), whole and as PSM 3 cut it: the notes are not prose by
    length (a median line of 20 characters), nor by words (three), nor notes of variations
    (a move number inside a third of the lines), and the gutter's bands are 587 and 240 px
    -- nothing held the gutter, and the page read «White could also try 26 Re3 Bxd4», CER
    0,0052 → 0,6440 and *accepted* through the importer.  Lines longer than a cell that
    carry the sentence over are running text: they never join, and they hold the gutter."""
    for cut in ((18,), (4, 3, 6, 5)):
        reading = ordinary_notes_beside_the_game(blocks=cut)
        game = len(cut) + 1
        assert not _crosses(table_groups(reading), set(range(1, game)), {game}), cut
        assert rows_of_tables(reading) is reading
        # the sabotage: without the running text (and the game beside text) the notes join
        # the game line by line
        blind = TableRowsConfig(running_lines=10**6, game_min_lines=10**6)
        assert _crosses(table_groups(reading, config=blind), set(range(1, game)), {game}), cut
        assert rows_of_tables(reading, config=blind).lines[0].text == (
            "White could also try 26 Re3 Bxd4")


def test_a_move_is_not_a_word_that_carries_a_sentence_over() -> None:
    """``b6 23 Be3 is met by`` opens with a move, not a lowercase word; a column of moves
    (``33 h4 gxh4+``) or of openings (``1 e4 c5 2 Nf3 d6``) carries nothing over."""
    from caissa.ocr.layout.rows import _continues

    assert _continues("position is unclear.") and _continues("(and then") and _continues("ex-")
    assert not _continues("b6 23 Be3 is met by") and not _continues("33 h4 gxh4+")
    assert not _continues("1 e4 c5 2 Nf3 d6") and not _continues("Black's knight is")
    assert _continues("so-called “Long") and _continues("l’avantage de")


def test_running_text_never_seeds_a_group(monkeypatch) -> None:
    """A seed is a member whatever it is.  The last block of the critic's notes (ciclo 3:
    «change the bishops. / Now 26 Re3 was best. / White's rooks are / active, but Black /
    holds the draw.») is a column of cells by the river its two spread lines open -- and
    running text: it never seeds (the filter had no test).  On this page the gutter holds
    first, and a five-line seed could not take the game's eighteen lines anyway (the
    partner share); the filter is the rule's contract where they do not."""
    import caissa.ocr.layout.rows as rows

    reading = ordinary_notes_beside_the_game(blocks=(4, 3, 6, 5))
    cfg = TableRowsConfig()
    last = next(b for b in rows._blocks(reading.lines, cfg) if b.index == 4)
    assert last.gutters and rows._is_cells(last, cfg) and rows._running(last, cfg)
    assert [b.index for b in rows._seeds(rows._blocks(reading.lines, cfg), cfg)] == [5]
    # the sabotage: every column of cells seeds, running text or not
    monkeypatch.setattr(rows, "_seeds", lambda blocks, cfg: sorted(
        (b for b in blocks if rows._is_cells(b, cfg)), key=lambda b: -len(b.lines)))
    assert 4 in [b.index for b in rows._seeds(rows._blocks(reading.lines, cfg), cfg)]


def gallagher_p50_with_the_tab() -> OcrResult:
    """The Gallagher p. 50 at its own scale (~20 px a character) as a reading the arbiter
    discarded (the builder's probe, ciclo 3): the game in the right column with Black's
    moves at a tab, so ``find_gutters`` finds two gutters -- the page's (755–817) and the
    tab's (1161–1193) --, and the left column's move list with its numbers misread
    (``21 a.. Hg8``, ``22 94 Hg6``: no numbering to hold it)."""
    def at(n: int) -> float:
        return 265.0 + GRID * n

    notes = ["The best chance to get", "his rook into the game, but", "of course the dark squares",
             "are now terribly weak."]
    lines = [_spread(t, 145.0, 754.0, at(n), 2, char_w=20.0) for n, t in enumerate(notes)]
    lines += [_line(t, 266.0, at(4 + n), 3, char_w=20.0) for n, t in enumerate(
        ["21 a.. Hg8", "22 94 Hg6", "2З b4 b5", "24 Bd5 Nd7", "2S Bd4 Bf6!"])]
    lines += [_spread(t, 145.0, 754.0, at(9 + n), 4, char_w=20.0) for n, t in enumerate(
        ["Now Black is able to ex-", "change the bishops under", "more favourable circum-",
         "stances. Although White", "still has an edge, his own"])]
    lines.append(_line("Cunningham Defence 51", 897.0, 176.0, 5, char_w=20.0))
    lines += [_line(t, 817.0, at(n), 6, char_w=14.0) for n, t in enumerate(
        ["weaknesses give Black just", "enough play to hold the"])]
    lines.append(_line("draw.", 816.0, at(2), 7, char_w=20.0))
    lines += [_line(str(26 + n), 936.0, at(3 + n), 7, char_w=20.0) for n in range(15)]
    white = ["Re3", "Rxd4", "Bb7", "Kg3", "Bf3", "Red3", "Rd5", "h4", "Kxh4", "g5", "Rxg5", "Rd1",
             "Rg4", "Bxg4", "Rd4"]
    lines += [_line(t, 1025.0, at(3 + n), 8, char_w=20.0) for n, t in enumerate(white)]
    black = ["Bxd4", "Rd6", "Rf6+", "Rc7", "Nb6", "Nc4", "h6", "gxh4+", "Re7", "hxg5+", "Re1",
             "Rf4+", "Rxg4+", "Re4", "1/2-1/2"]
    lines += [_line(t, 1193.0, at(3 + n), 9, char_w=20.0) for n, t in enumerate(black)]
    return _reading(lines)


def test_of_two_gutters_the_page_s_is_the_one_next_to_the_prose(monkeypatch) -> None:
    """With two gutters the rule saw no page gutter at all.  With the left column's numbers
    misread, nothing kept its moves out of the right column's game -- a reading of the
    Gallagher p. 50 the arbiter discarded joined them (the critic, ciclo 3); and on the
    critic's page with the game at a tab, the notes that are not prose by any rule joined
    it.  The page's gutter is the first one past the prose; the tab has the game's own text
    on both sides.  Prose on *both* sides would miss the second page: its right column is
    the game alone."""
    import caissa.ocr.layout.rows as rows
    from caissa.ocr.layout.scan import find_gutters

    gallagher = gallagher_p50_with_the_tab()
    tabbed = ordinary_notes_beside_the_game(blocks=(4, 3, 6, 5), tab=0.45)
    for reading in (gallagher, tabbed):
        assert len(find_gutters(reading.lines)) == 2
    assert sorted(sorted(g) for g in rows.table_groups(gallagher)) == [[7, 8, 9]]
    assert sorted(sorted(g) for g in rows.table_groups(tabbed)) == [[5, 6]]
    original = rows._page_gutters

    def both_sides(result, blocks, cfg):
        gutters = find_gutters(result.lines)
        if len(gutters) < 2:
            return original(result, blocks, cfg)
        prose = [b for b in blocks if rows._is_prose(b, cfg)]
        return [g for g in gutters if any(b.extent.x1 <= g[1] for b in prose)
                and any(b.extent.x0 >= g[0] for b in prose)]

    # the sabotages: a page gutter only when find_gutters finds one; prose on both sides
    monkeypatch.setattr(rows, "_page_gutters", lambda result, blocks, cfg: (
        [] if len(find_gutters(result.lines)) > 1 else original(result, blocks, cfg)))
    assert _crosses(rows.table_groups(gallagher), {3}, {7, 8, 9})
    assert _crosses(rows.table_groups(tabbed), {1, 2, 3, 4}, {5, 6})
    monkeypatch.setattr(rows, "_page_gutters", both_sides)
    assert _crosses(rows.table_groups(tabbed), {1, 2, 3, 4}, {5, 6})


# --------------------------------------------------------------------------- #
# The critic's pages (fase 5, ciclo 4): indexes, games beside text, the bands
# --------------------------------------------------------------------------- #


INDEX_ENTRIES = [
    "Radulescu 8", "Ragozin 24", "Rashkovsky 139", "Reshko 38, 53", "Ribli 158", "Robatsch 178",
    "Rytov 137", "Sakharov 47", "Sanguinetti 37", "Santo-Roman 210", "Schmid 69", "Seirawan 165",
    "Vilup 3, 4", "Vizantiadis 122", "Vranesic 77", "Wirthensohn 180", "Witkowski 43",
    "Zhu Chen 206", "Zhukhovitsky 25", "Zilberman 143", "Zuk 124", "Zurakhov 17, 18",
    "Aaron 249", "Acevedo 228", "Geller 279, 280", "Gligoric 229, 264", "Gudmundsson 243",
    "Hook 301", "Ivkov 268", "Johannessen 265", "Keres 222, 248", "Korchnoi 290", "Kramer 215",
    "Kupper 230", "Larsen 220, 303", "Letelier 234"]


def index_in_three_columns(*, prose_third: bool = False) -> OcrResult:
    """The critic's index (``c4\\tres.pdf``, Times 9 pt at 300 DPI, ~17 px a character) as PSM 3
    cut it: one block per column, twelve entries each, a line every 44 px -- two gutters, no
    prose; or, with ``prose_third``, «índice | índice | prosa»."""
    lines: list[OcrLine] = []
    for column, x in enumerate((150.0, 750.0, 1349.0)):
        if prose_third and column == 2:
            lines += [_line(t, x, 157.0 + 44.0 * n, 3, char_w=17.0) for n, t in enumerate(
                ["The endgame is the part", "of the game in which the", "fewest pieces remain on",
                 "the board, and it is there", "that the value of each", "piece can be judged most",
                 "exactly. A rook and a", "bishop against a rook is", "usually a draw, but the",
                 "defender must know where", "to put his king and which",
                 "side to keep his rook."])]
            continue
        entries = INDEX_ENTRIES[12 * column:12 * column + 12]
        lines += [_line(t, x, 157.0 + 44.0 * n, column + 1, char_w=17.0)
                  for n, t in enumerate(entries)]
    return _reading(lines)


def test_an_index_in_three_columns_is_three_lists() -> None:
    """With two gutters and no prose the rule saw no page gutter, and the three columns of an
    index were joined line by line -- «Radulescu 8 Vilup 3, 4 Geller 279, 280», CER 0,0007 →
    0,7791 and *accepted* through the importer (crítico da fase 5, ciclo 4).  Each column is a
    list of entries -- a name and its pages --: the gutter between two lists of one form is the
    page's."""
    from caissa.ocr.layout.scan import find_gutters

    for prose_third in (False, True):
        reading = index_in_three_columns(prose_third=prose_third)
        assert len(find_gutters(reading.lines)) == 2
        groups = table_groups(reading)
        assert not _crosses(groups, {1}, {2}) and not _crosses(groups, {2}, {3}), prose_third
        # the sabotage: without the lists of one form, the gutters hold only beside prose
        blind = TableRowsConfig(list_listed_share=2.0)
        assert _crosses(table_groups(reading, config=blind), {1}, {2}), prose_third


GAMES_INDEX = [
    ["Potkin", "   Carlsen 112", "Predojevic", "   Pashikian 65", "Prohaszka", "   Luther 112",
     "Pruijssers", "   Ernst 104", "Radjabov", "   Kamsky 174", "   Perunovic 66", "Ragger",
     "   Morozevich 188", "Rahman", "   Petrosian 113", "Ramis", "   Fidel 182", "Rasulov",
     "   Safarli 112", "Raznikov", "   Ma Qun 114", "Reinderman", "   Ruijgrok 64",
     "   Wahono 118", "Reshevsky", "   Bisguier 49", "Rodshtein", "   Zhigalko 118"],
    ["Savchenko", "   Dauletova 120", "   Dreev 111", "   Shomoev 122", "Schmaltz", "   Graf 131",
     "Sebag", "   Hou 67, 103", "Seirawan", "   Gulko 56", "Sengupta", "   Gupta 112",
     "   Istratescu 166", "Sethuraman", "   Krejci 114", "Shanava", "   Mamedyarov 103",
     "Shanglei", "   Dimakiling 46", "Shankland", "   Michiels 109", "Shengelia",
     "   Dambacher 47", "Sherif", "   Pogonina 198", "Shimanov", "   Belous 55", "   Inarkiev 48"],
    ["Smirnov", "   Pantsulaia 55, 59", "Smyslov", "   Geller 56", "   Pilnik 55", "   Timman 123",
     "Sokolov", "   Georgiev 123", "Spassky", "   Benko 189", "   Dvoiris 115", "   Fischer 70, 71",
     "   Gipslis 189", "   Gufeld 190", "   Hjartarson 190", "   Kindermann 190", "   Larsen 191",
     "Speelman", "   Jonathan 179", "Sprenger", "   Stevic 197", "Stefanova", "   Yusupov 108",
     "Stellwagen", "   Yusupov 184", "Stevic", "   Kummer 69", "   Papaioannou 103"],
]


def games_index() -> OcrResult:
    """The Yusupov 4 p. 206 («Índice de partidas») as PSM 3 cut it: each player at the margin
    and the opponents indented under the player, three columns of 28 lines; the scan is skewed,
    the margin drifting 0,02 px a pixel down the page (the Aagaard's index drifts 40 px)."""
    lines: list[OcrLine] = []
    for column, (x, entries) in enumerate(zip((127.0, 680.0, 1233.0), GAMES_INDEX, strict=True)):
        for n, text in enumerate(entries):
            y = 193.0 + 49.0 * n
            indent = 51.0 if text.startswith(" ") else 0.0
            lines.append(_line(text.strip(), x + indent - 0.02 * y, y, column + 1, char_w=17.0))
    return _reading(lines)


def test_a_games_index_is_three_lists_of_players_and_their_opponents() -> None:
    """The games index: each player and, under the player, the opponents with their pages -- a
    list of entries, the players' lines among them; the three columns are three lists (the
    importer read the page 0,0465 → 0,7915 with the columns joined)."""
    reading = games_index()
    groups = table_groups(reading)
    assert not _crosses(groups, {1}, {2}) and not _crosses(groups, {2}, {3})
    # the sabotage: no list of one form
    blind = TableRowsConfig(list_listed_share=2.0)
    assert _crosses(table_groups(reading, config=blind), {1, 2}, {3})


def index_with_the_pages_apart() -> OcrResult:
    """The Nunn p. 288 («Index of Players and Composers») as PSM 3 cut it: in each column the
    names in one block and their pages in another, beside them."""
    names = [["Polak", "Polgar, J.", "Polugaevsky", "Portisch", "Psakhis", "Radulov", "Ragozin",
              "Rauzer"],
             ["Rumiantsev", "Ruszcynski", "Sackmann", "Saidy", "Salov", "Sanguinetti", "Savon",
              "Sax"]]
    pages = [["P251", "P305, 412", "R296", "P139, 171, 209", "M61, 79", "R70", "P342",
              "R231, P26, 110"],
             ["M30", "P121, 390", "P119", "R48, 479", "M269", "P104", "R204, M3", "M315"]]
    lines: list[OcrLine] = []
    for column, (x_name, x_pages) in enumerate(((158.0, 432.0), (817.0, 1086.0))):
        lines += [_line(t, x_name, 396.0 + 49.0 * n, 2 * column + 1, char_w=17.0)
                  for n, t in enumerate(names[column])]
        lines += [_line(t, x_pages, 396.0 + 49.0 * n, 2 * column + 2, char_w=17.0)
                  for n, t in enumerate(pages[column])]
    return _reading(lines)


def test_an_index_reads_each_name_with_its_pages_and_never_the_next_column() -> None:
    """Each name with its pages is a row -- what the rule gets right on the Nunn p. 289
    (0,3027 → 0,0174) -- and the next column's names are another list."""
    reading = index_with_the_pages_apart()
    groups = table_groups(reading)
    assert not _crosses(groups, {1, 2}, {3, 4})
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert "Polak P251" in texts and "Rumiantsev M30" in texts
    blind = TableRowsConfig(list_listed_share=2.0)
    assert _crosses(table_groups(reading, config=blind), {1, 2}, {3, 4})


# --------------------------------------------------------------------------- #
# The critic's pages (fase 5, ciclo 5): lists out of order, short lists, a game
# beside a table, a table whose columns rise in order by chance
# --------------------------------------------------------------------------- #


STANDINGS = ["Carlsen", "Caruana", "Ding", "Nepomniachtchi", "Aronian", "Giri", "So", "Mamedyarov",
             "Anand", "Grischuk", "Nakamura", "Vachier-Lagrave", "Karjakin", "Radjabov", "Topalov",
             "Rapport", "Firouzja", "Duda"]


def players_by_the_standings() -> OcrResult:
    """The critic's «jogador / adversários» (``c5\\ataque\\indices_ataque.pdf`` p. 8, Times 9 pt at
    300 DPI) as PSM 3 cut it: the players by the standings -- not in alphabetical order --, the
    opponents indented under each with a page, three columns of 22 lines, one block each."""
    lines: list[OcrLine] = []
    rows: list[str] = []
    for i, player in enumerate(STANDINGS):
        others = [p for p in STANDINGS if p != player]
        rows += [player, *(f"   {others[(i * 3 + k) % len(others)]} {40 + 7 * i + 3 * k}"
                           for k in range(2 + i % 2))]
    for column, x in enumerate((150.0, 740.0, 1330.0)):
        for n, text in enumerate(rows[22 * column:22 * column + 22]):
            indent = 51.0 if text.startswith(" ") else 0.0
            lines.append(_line(text.strip(), x + indent, 157.0 + 44.0 * n, column + 1, char_w=17.0))
    return _reading(lines)


def test_players_by_the_standings_are_three_lists_not_a_table() -> None:
    """Out of alphabetical order the rule of the fourth cycle saw no index, and the three columns
    were joined line by line -- «Carlsen Caruana 82 Nepomniachtchi 127», 0,0000 → 0,6577 and
    *accepted* through the importer (crítico da fase 5, ciclo 5).  Three lists of one form -- a
    player, the opponents with their pages -- in any order: the gutters between them are the
    page's.  The sabotage: no list of one form, and the columns join."""
    reading = players_by_the_standings()
    groups = table_groups(reading)
    assert not _crosses(groups, {1}, {2}) and not _crosses(groups, {2}, {3})
    blind = TableRowsConfig(list_listed_share=2.0)
    assert _crosses(table_groups(reading, config=blind), {1}, {2, 3})


def index_last_page(entries_right: int) -> OcrResult:
    """The critic's «nome | páginas» index (p. 4): the pages set apart from the names, as the Nunn
    sets them, two columns -- and on the last page the second column holds five entries."""
    names = [t.split()[0] for t in INDEX_ENTRIES]
    pages = [t.split(" ", 1)[1] for t in INDEX_ENTRIES]
    lines: list[OcrLine] = []
    for column, (x_name, x_pages, count) in enumerate(((150.0, 510.0, 28), (930.0, 1290.0,
                                                                               entries_right))):
        first = 0 if column == 0 else 28
        for n in range(count):
            y = 170.0 + 45.0 * n
            lines.append(_line(names[(first + n) % len(names)], x_name, y, 2 * column + 1,
                               char_w=17.0))
            lines.append(_line(pages[(first + n) % len(pages)], x_pages, y, 2 * column + 2,
                               char_w=17.0))
    return _reading(lines)


def test_the_last_page_of_an_index_is_two_lists_however_short_the_second() -> None:
    """With five entries in the second column the rule of the fourth cycle saw one index column
    (six heads at least) and no gutter: the first five rows joined two entries each, «Aaron 249
    Ivkov 268», 0,6634 → 0,3196 *accepted* (crítico da fase 5, ciclo 5).  A name and its pages are
    a row; the second column is another list, however short -- from two entries: a column of one
    line is not a column to ``find_gutters`` (no gutter before it), and its entry joins the first
    row, one line (said in the report)."""
    for right in (5, 2, 28):
        reading = index_last_page(right)
        groups = table_groups(reading)
        assert not _crosses(groups, {1, 2}, {3, 4}), right
        texts = [line.text for line in rows_of_tables(reading).lines]
        assert texts[0] == INDEX_ENTRIES[0], right
        blind = TableRowsConfig(list_listed_share=2.0)
        assert _crosses(table_groups(reading, config=blind), {1, 2}, {3, 4}), right


def test_columns_of_names_and_nothing_else_are_lists() -> None:
    """A page of names in three columns -- no pages, no values -- in alphabetical order or not:
    lists (the rule of the fourth cycle held the ones in order by their order, and the form of a
    list of entries needs the pages).  The sabotage: no list of one form."""
    names = sorted(t.split()[0] for t in INDEX_ENTRIES)
    for order in (names, names[::-1]):
        lines = [_line(order[12 * column + n], x, 157.0 + 44.0 * n, column + 1, char_w=17.0)
                 for column, x in enumerate((150.0, 750.0, 1349.0)) for n in range(12)]
        reading = _reading(lines)
        groups = table_groups(reading)
        assert not _crosses(groups, {1}, {2}) and not _crosses(groups, {2}, {3})
        blind = TableRowsConfig(list_listed_share=2.0)
        assert _crosses(table_groups(reading, config=blind), {1}, {2, 3})


GAME_ON_THE_LEFT = ["1 e4 e5", "2 Nf3 Nc6", "3 Bb5 a6", "4 Ba4 Nf6", "5 O-O Be7", "6 Re1 b5",
                    "7 Bb3 d6", "8 c3 O-O", "9 h3 Nb8", "10 d4 Nbd7", "11 Nbd2 Bb7", "12 Bc2 Re8"]
POINTS = ["7½", "7", "6½", "6", "5½", "5", "4½", "4", "3½", "3", "2½", "2"]
PLAYERS = ["Aljechin", "Keres", "Flohr", "Petrov", "Fine", "Reshevsky", "Tartakower", "Steiner",
           "Lilienthal", "Stahlberg", "Book", "Mikenas"]


def game_beside_the_standings() -> OcrResult:
    """The critic's ``c5\\partida_tabela\\P_T.png`` as PSM 3 cut it: the game (b1), the players of
    the standings (b2) and their points, one block each (b3–b14) -- as a tournament book sets a
    round's game beside the table."""
    lines = [_line(t, 151.0, 157.0 + 50.0 * n, 1, char_w=20.0)
             for n, t in enumerate(GAME_ON_THE_LEFT)]
    lines += [_line(t, 810.0, 157.0 + 50.0 * n, 2, char_w=20.0) for n, t in enumerate(PLAYERS)]
    lines += [_line(t, 1221.0, 157.0 + 50.0 * n, 3 + n, char_w=20.0) for n, t in enumerate(POINTS)]
    return _reading(lines)


def test_a_game_beside_the_standings_is_a_game_and_a_table() -> None:
    """The game's lines joined to the standings' rows -- «1 e4 e5 Aljechin 7½», 0,2218 → 0,7564
    (crítico da fase 5, ciclo 5; the same in the fourth cycle): the gutter beside a game is the
    page's only when the other side is text, and the first column of a table is cells.  A group
    never holds a game and a column of names: the game stays as the engine read it, the standings
    are read by rows.  The sabotage: no column of names, and the game joins the table."""
    reading = game_beside_the_standings()
    groups = table_groups(reading)
    assert not _crosses(groups, {1}, {2})
    texts = [line.text for line in rows_of_tables(reading).lines]
    assert texts[:12] == GAME_ON_THE_LEFT
    # the standings by rows (a whole point alone, «7», is taken for a move number and joins one
    # row only -- the rule of the numbering, as before)
    assert "Aljechin 7½" in texts and "Book 2½" in texts
    blind = TableRowsConfig(names_share=2.0)
    assert _crosses(table_groups(reading, config=blind), {1}, {2})


def tournament_table(countries: list[str]) -> OcrResult:
    """The critic's tournament table (``c5\\b13_tabela_em_ordem.py``): name | country | rating |
    points, twelve players, the names in alphabetical order -- one block a column."""
    names = ["Alekhine", "Bogoljubow", "Capablanca", "Duras", "Euwe", "Flohr", "Grünfeld",
             "Hromadka", "Ilyin", "Janowski", "Keres", "Lasker"]
    ratings = ["2690", "2620", "2725", "2580", "2650", "2640", "2600", "2560", "2570", "2590",
               "2660", "2700"]
    lines: list[OcrLine] = []
    for column, (x, cells) in enumerate(((150.0, names), (600.0, countries), (1000.0, ratings),
                                          (1200.0, POINTS))):
        lines += [_line(t, x, 157.0 + 50.0 * n, column + 1, char_w=17.0)
                  for n, t in enumerate(cells)]
    return _reading(lines)


def test_a_table_whose_columns_rise_in_order_by_chance_is_one_table(monkeypatch) -> None:
    """The names in alphabetical order, and the countries too, by chance: the rule of the fourth
    cycle took the two for index columns and read the names alone, 0,7509 → 0,6367 (crítico da
    fase 5, ciclo 5, não bloqueante 11) -- with the countries out of order, 0,1207.  A name, a
    country, a rating and a score are not two lists of one form: the table is read by rows, in
    order or not.  The sabotage: every column a list of entries."""
    import caissa.ocr.layout.rows as rows

    in_order = ["Argentina", "Bélgica", "Cuba", "Dinamarca", "Escócia", "Finlândia", "Grécia",
                "Hungria", "Irlanda", "Japão", "Letônia", "Malta"]
    out_of_order = ["França", "Alemanha", "Cuba", "Holanda", "Escócia", "Suécia", "Áustria",
                    "Tchecoslováquia", "URSS", "Polônia", "Estônia", "EUA"]
    for countries in (in_order, out_of_order):
        texts = [line.text for line in rows_of_tables(tournament_table(countries)).lines]
        assert texts[0] == f"Alekhine {countries[0]} 2690 7½", texts[0]
    monkeypatch.setattr(rows, "_band_form", lambda lines, cfg: "E")
    texts = [line.text for line in rows.rows_of_tables(tournament_table(in_order)).lines]
    assert texts[0] != f"Alekhine {in_order[0]} 2690 7½"


def test_the_kinds_of_a_row() -> None:
    """What a line of a list holds (``rows._row_kind``): the numbers after a name are a list's
    (pages, or four digits in a list: the Karpov 1 index, «999, 1046»); a year, a rating or a
    score are a table's values; a move is neither."""
    from caissa.ocr.layout.rows import _band_form, _row_kind

    assert _row_kind("Aaron 249") == ("numbered", ["249"])
    assert _row_kind("Keres 222, 248")[0] == "numbered"
    assert _row_kind("Polugaevsky — 999, 1046") == ("numbered", ["999,", "1046"])
    assert _row_kind("Pogosiants R352, 441, P29")[0] == "numbered"
    assert _row_kind("Van den Ende M60")[0] == "numbered"
    assert _row_kind("Carlsen – Caruana 1–0 45") == ("numbered", ["45"])
    assert _row_kind("Aljechin 7½") == ("value", ["7½"])
    assert _row_kind("231, 246")[0] == "refs"
    assert _row_kind("7½")[0] == "score"
    assert _row_kind("Carlsen") == ("word", [])
    assert _row_kind("1 e4 e5") == ("", [])
    assert _row_kind("1. Kasparov – Karpov") == ("", [])
    cfg = TableRowsConfig()
    column = [_line(t, 0.0, 50.0 * n, 1) for n, t in enumerate(
        ["Moscovo 1985", "Reykjavik 1972", "Nova Iorque 1918", "Bona 2008", "Haia 1937"])]
    assert _band_form(column, cfg) == "V", "one year a line: a table's values, not a list"
    index = [_line(t, 0.0, 50.0 * n, 1) for n, t in enumerate(
        ["Polugaevsky — 999, 1046", "Porath — 1012", "Portisch — 1015, 1030", "Averkin — 1934"])]
    assert _band_form(index, cfg) == "E", "four digits in a list: an index"


FRINGE_NOTES = ["White could play 24 Rd1", "Bxd4 Rxd4 with an edge.", "Black's reply Kf8 holds",
                "Ke7 and Kd6 is solid,", "Nd7 and Nc5 follow.", "Stronger is 23 Bd3!",
                "Rd8 and the rook is", "Active, but White keeps", "Bf1 and Rd2 with some",
                "Pressure on the d-file.", "After 23...Nd7 24 Bf1", "Nc5 Black is fine and",
                "Rc8 25 Rd2 Nc5 26 f3", "Kf8 draws comfortably.", "Instead 24 Kf2 Rc8 25",
                "Rd2 is met by Nc5 and", "Kf8 with equality.", "The game went 24 Re2."]


def test_notes_that_no_rule_calls_prose_stay_beside_the_game() -> None:
    """The fringe the critic measured (ciclo 4: 12 of 29 pages at risk joined, the Nunn p. 29
    notes beside a game 0,0824 → 0,6571): lines that open with a move or a capital -- no third
    of them carries the sentence over --, a move number inside a third of them, three words a
    line.  No prose rule holds them; the game beside a column of text makes the gutter the
    page's, and only a move list crosses it."""
    from caissa.ocr.layout import rows as rows_module

    notes = [_spread(t, 150.0, 735.0, 300.0 + 50.0 * n, 1, char_w=20.0)
             for n, t in enumerate(FRINGE_NOTES)]
    whole = [_line(t, 811.0, 300.0 + 50.0 * n, 2, char_w=20.0) for n, t in enumerate(GAME_UNTABBED)]
    # the German notation: the period parts the numbers from the moves, and PSM 3 cuts them in
    # two blocks (the critic's Gunderam and Euwe pages, ciclo 4)
    cut = [_line(f"{t.split()[0]}.", 811.0, 300.0 + 50.0 * n, 2, char_w=20.0)
           for n, t in enumerate(GAME_UNTABBED)]
    cut += [_line(" ".join(t.split()[1:]), 872.0, 300.0 + 50.0 * n, 3, char_w=20.0)
            for n, t in enumerate(GAME_UNTABBED)]
    cfg = TableRowsConfig()
    for game in (whole, cut):
        reading = _reading(notes + game)
        block = next(b for b in rows_module._blocks(reading.lines, cfg) if b.index == 1)
        assert not rows_module._is_prose(block, cfg), "the case: no rule calls these notes prose"
        assert not _crosses(table_groups(reading), {1}, {2, 3})
        # the sabotage: without the game beside text, the notes join the game
        blind = TableRowsConfig(game_min_lines=10**6)
        assert _crosses(table_groups(reading, config=blind), {1}, {2, 3})


def test_a_river_in_the_notes_does_not_hide_the_gutter_beside_the_game(monkeypatch) -> None:
    """The crítico's Dvoretsky pages (the book's index reflowed in the Gallagher's measure,
    beside a game; ciclo 4, 4 of 11 still joined in ciclo 5): ``find_gutters`` found the river
    of the column of short justified lines (551–569) besides the page's gutter (736–811), the
    notes' blocks sit left of the river, and the band next to the page's gutter was empty -- no
    text beside the game.  The text is looked for in the nearest band that holds a block."""
    from caissa.ocr.layout import rows as rows_module
    from caissa.ocr.layout import scan

    notes = [_spread(t, 150.0, 735.0, 300.0 + 50.0 * n, 1, char_w=20.0)
             for n, t in enumerate(FRINGE_NOTES)]
    game = [_line(t, 811.0, 300.0 + 50.0 * n, 2, char_w=20.0) for n, t in enumerate(GAME_UNTABBED)]
    reading = _reading(notes + game)
    river, page = (551.0, 569.0), (736.0, 811.0)
    monkeypatch.setattr(scan, "find_gutters", lambda lines, **kw: [river, page])
    cfg = TableRowsConfig()
    blocks = rows_module._blocks(reading.lines, cfg)
    bands = {0: [b for b in blocks if b.index == 1], 2: [b for b in blocks if b.index == 2]}
    assert rows_module._game_gutters([river, page], bands, cfg) == [page]
    assert not _crosses(table_groups(reading), {1}, {2})
    # the sabotage: without the game beside text, the notes join the game across the river
    assert _crosses(table_groups(reading, config=TableRowsConfig(game_min_lines=10**6)), {1}, {2})


def test_a_move_list_crosses_two_page_gutters_in_order_and_nothing_jumps_a_band(
        monkeypatch) -> None:
    """The numbers, White's moves and Black's, split by two gutters of the page: one move list,
    the bands one after the other.  A group never jumps a band.  (The crítico da fase 5, ciclo
    4: the rule had no test -- without it, the 34 passed.)"""
    from caissa.ocr.layout import rows as rows_module

    numbers = [_line(f"{30 + n}.", 0.0, 58.0 * n, 1, char_w=20.0) for n in range(4)]
    white = [_line(t, 200.0, 58.0 * n, 2, char_w=20.0)
             for n, t in enumerate(["♖c1", "♘h1", "♗xc5", "♖xc5"])]
    black = [_line(t, 500.0, 58.0 * n, 3, char_w=20.0)
             for n, t in enumerate(["♗xd4", "♘xc5", "♖xc5", "♕xc5"])]
    reading = _reading(numbers + white + black)
    monkeypatch.setattr(rows_module, "_prose_gutters", lambda result: [])
    monkeypatch.setattr(rows_module, "_page_gutters",
                        lambda result, blocks, cfg: [(120.0, 180.0), (320.0, 480.0)])
    assert sorted(sorted(g) for g in rows_module.table_groups(reading)) == [[1, 2, 3]]
    assert rows_module.rows_of_tables(reading).lines[0].text == "30. ♖c1 ♗xd4"
    # nothing in the middle band: numbers and Black's moves would jump it
    jumping = _reading(numbers + black)
    assert rows_module.table_groups(jumping) == []
    # the sabotages: more than two bands always cross (the fourth cycle's first rule), and a
    # group that may jump a band
    original = rows_module._crosses_the_page
    monkeypatch.setattr(rows_module, "_crosses_the_page", lambda members, band, cfg: (
        len({band(m) for m in members}) > 2 or original(members, band, cfg)))
    assert rows_module.table_groups(reading) != [[1, 2, 3]]
    monkeypatch.setattr(rows_module, "_crosses_the_page", lambda members, band, cfg: (
        False if {band(m) for m in members} == {0, 2} else original(members, band, cfg)))
    assert rows_module.table_groups(jumping) == [[1, 3]]


def test_config_shares_are_the_rules_numbers() -> None:
    cfg = TableRowsConfig()
    assert cfg.cell_chars == 12 and cfg.align_share == 0.8 and cfg.overlap == 0.5
    assert cfg.running_lines == 4 and cfg.prose_continued == 1 / 3


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
