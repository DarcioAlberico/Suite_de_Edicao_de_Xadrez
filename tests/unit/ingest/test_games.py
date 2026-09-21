"""OCR_UI_ROADMAP passo 11: a ``Movetext`` paragraph after a read diagram becomes a game.

The gate on real pages is red (``OCR_UI_REPORT_C1.md`` §12); what is tested
here is the mechanism on paragraphs whose truth is known: the main line
chains from the position, the prose around it is kept verbatim, a column of
one-line paragraphs is one game, a repaired-into-another move ends the chain
(no invention), and without a position nothing changes.
"""

from __future__ import annotations

from dataclasses import replace

import chess

from caissa.core.model import Diagram, GameScore, Paragraph, RecognitionResult
from caissa.core.model.inline import Text
from caissa.core.model.props import ParagraphProps
from caissa.core.model.provenance import Provenance, Rect, SourceKind
from caissa.ingest.pdf.games import GamesReport, attach_games, game_from_paragraph

FEN = "4k2r/p2n1ppp/Npr1p3/3pP3/3p1P2/8/P2N2PP/R3K2R b - - 0 19"


def _movetext(text: str) -> Paragraph:
    return Paragraph(
        content=(Text(content=text),),
        props=ParagraphProps(style="Movetext"),
        provenance=Provenance(kind=SourceKind.OCR, page_index=12, engine="tesseract"),
    )


def _diagram(fen: str) -> Diagram:
    return Diagram(fen=fen, recognition=RecognitionResult(fen=fen))


def _sans(score: GameScore) -> list[str]:
    out, node = [], score.children[0]
    while node is not None:
        out.append(node.san)
        node = node.children[0] if node.children else None
    return out


def test_the_main_line_chains_from_the_position_and_the_prose_stays():
    paragraph = _movetext("An excellent counter! 19... g5! 20 g3 gxf4 21 gxf4 Rg8 (21...Nf8) 22 f5")
    score, why = game_from_paragraph(paragraph, FEN)
    assert why == "game"
    assert _sans(score) == ["g5", "g3", "gxf4", "gxf4", "Rg8", "f5"]
    first = score.children[0]
    assert first.ply == 1
    assert first.position_before == FEN
    assert chess.Board(first.position_after).piece_at(chess.G5) is not None
    assert first.provenance.engine == "tesseract", "the paragraph's provenance, per move"
    assert first.provenance.note == "g5! → g5; trailing annotation removed"
    assert first.comment_before == "An excellent counter!"
    assert score.initial_fen == FEN


def test_a_repaired_into_another_move_ends_the_chain_instead_of_inventing():
    paragraph = _movetext("19... g5! 20 g3 Nb4 21 gxf4")
    score, why = game_from_paragraph(paragraph, FEN)
    assert why == "game"
    assert _sans(score) == ["g5", "g3"], "Nb4 is not legal; the repairer's Nb8 is not on the page"
    last = score.children[0].children[0]
    assert "não reproduzidos" in last.comment_after
    assert "Nb4" in last.comment_after


def test_a_line_that_does_not_start_from_the_position_is_kept():
    kept, why = game_from_paragraph(_movetext("21 Rxf4 Nxe5 22 Rxd4 Rg8"), FEN)
    assert kept is None
    assert why == "side_mismatch", "21 is White's move; the diagram has Black to move (X1)"
    kept, why = game_from_paragraph(_movetext("19... Rxf4 20 Rxd4 Rg8"), FEN)
    assert kept is None
    assert why == "no_chain"
    short, why = game_from_paragraph(_movetext("Black is fine."), FEN)
    assert short is None
    assert why == "short"


def test_attach_games_joins_a_column_and_carries_the_position_on():
    blocks = [
        _diagram(FEN),
        Paragraph(content=(Text(content="An excellent counter!"),)),
        _movetext("19... g5!"),
        _movetext("20 g3 gxf4"),
        _movetext("21 gxf4 Rg8"),
        Paragraph(content=(Text(content="prose between"),)),
        _movetext("22 f5 Nf8"),
    ]
    report = GamesReport()
    out = attach_games(blocks, report=report)
    kinds = [type(b).__name__ for b in out]
    assert kinds == ["Diagram", "Paragraph", "GameScore", "Paragraph", "GameScore"], kinds
    assert _sans(out[2]) == ["g5", "g3", "gxf4", "gxf4", "Rg8"]
    assert _sans(out[4]) == ["f5", "Nf8"], "continues from where the column ended"
    assert report.games == 2
    assert report.moves == 7
    assert report.movetext_seen == 4
    assert report.counters()["game_moves"] == 7


def test_without_a_read_diagram_every_paragraph_stays():
    empty = Diagram(fen="8/8/8/8/8/8/8/8 w - - 0 1")
    blocks = [_movetext("19... g5! 20 g3 gxf4"), empty, _movetext("19... g5! 20 g3 gxf4")]
    report = GamesReport()
    out = attach_games(blocks, report=report)
    assert [type(b).__name__ for b in out] == ["Paragraph", "Diagram", "Paragraph"]
    assert report.kept_no_position == 2
    assert report.games == 0


def test_a_spelling_repair_keeps_the_printed_piece_and_square_so_it_is_not_an_invention():
    # ``20g3`` (number glued by the OCR) → g3 and ``♖g8`` → Rg8 say the same move;
    # the chain goes on.  A repair that changes the piece (♖g6 → Bg6) still ends it.
    paragraph = _movetext("19... g5! 20g3 gxf4 21 gxf4 ♖g8")
    score, why = game_from_paragraph(paragraph, FEN)
    assert why == "game"
    assert _sans(score) == ["g5", "g3", "gxf4", "gxf4", "Rg8"]


def test_a_printed_capture_onto_an_empty_square_ends_the_chain():
    # SFC4 p15: the column «14 ♘xe5 ♖xe5» sits two plies after the diagram
    # (13 h3! ♘e5 is in the prose); from the diagram Ne5 is legal but takes
    # nothing — the page says it takes.  Not this position: no game.
    before_13 = "r2qr1k1/p2n1pbp/bp1p1np1/2pP4/8/P1N2NP1/1PQ1PPBP/R1B1R1K1 w - - 0 13"
    score, why = game_from_paragraph(_movetext("14 ♘xe5 ♖xe5 15 e4 ♖e8"), before_13)
    assert score is None
    assert why == "number_mismatch", "the anchor is numbered 13; the column starts at 14 (X1)"
    # With the anchor's number unknown (a recognised diagram says ``1``), the
    # board is the judge: the printed capture onto an empty e5 ends the chain.
    unnumbered = before_13.rsplit(" ", 1)[0] + " 1"
    score, why = game_from_paragraph(_movetext("14 ♘xe5 ♖xe5 15 e4 ♖e8"), unnumbered)
    assert score is None
    assert why == "no_chain"
    after_13 = "r2qr1k1/p4pbp/bp1p1np1/2pPn3/8/P1N2NPP/1PQ1PPB1/R1B1R1K1 w - - 1 14"
    score, why = game_from_paragraph(_movetext("14 ♘xe5 ♖xe5 15 e4 ♖e8"), after_13)
    assert why == "game"
    assert _sans(score) == ["Nxe5", "Rxe5", "e4", "Re8"]


def test_a_column_printed_from_move_one_needs_no_diagram():
    blocks = [_movetext("1 d4 Nf6"), _movetext("2 c4 c5"), _movetext("3 Nf3 cxd4")]
    report = GamesReport()
    out = attach_games(blocks, report=report)
    assert len(out) == 1
    assert isinstance(out[0], GameScore)
    assert out[0].initial_fen is None, "the standard position is implicit"
    assert _sans(out[0]) == ["d4", "Nf6", "c4", "c5", "Nf3", "cxd4"]
    assert report.games == 1
    assert report.kept_no_position == 0
    # ``10 ...`` or a damaged number is not move one.
    kept = attach_games([_movetext("10 0-0 Be7"), _movetext("11 Qd2 0-0")], report=GamesReport())
    assert all(isinstance(b, Paragraph) for b in kept)


def _at(block, x: float, y: float, w: float = 80.0, h: float = 12.0):
    provenance = block.provenance or Provenance(kind=SourceKind.OCR)
    return replace(
        block, provenance=replace(provenance, page_index=10, rect=Rect(x=x, y=y, width=w, height=h))
    )


def test_the_column_takes_the_board_above_it_not_the_last_one_in_reading_order():
    # The importer lists the page's diagrams before its text: left board,
    # right board, then the left column's moves.  Geometry picks the left one.
    other = "8/6k1/3b4/1R1p4/1PpPr1p1/2P3n1/3B2K1/6N1 w - - 0 36"
    left = _at(_diagram(FEN), 60, 80, 200, 200)
    right = _at(_diagram(other), 320, 80, 200, 200)
    column = [
        _at(_movetext("19... g5! 20 g3"), 70, 300),
        _at(_movetext("20... gxf4 21 gxf4"), 70, 314),
    ]
    report = GamesReport()
    out = attach_games([left, right, *column], report=report)
    assert report.games == 1
    assert _sans(out[-1]) == ["g5", "g3", "gxf4", "gxf4"]
    assert out[-1].initial_fen == FEN
    # Without boxes the rule is the old one: the last diagram before the column.
    kept = attach_games(
        [_diagram(FEN), _diagram(other), _movetext("19... g5! 20 g3")], report=GamesReport()
    )
    assert isinstance(kept[-1], Paragraph), "from the right board 19... g5 is not legal"


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP_C2 passo A5 / X1: the anchor is explicit, the number is evidence
# --------------------------------------------------------------------------- #

RUY_8 = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 d6 8.c3 O-O"


def test_castling_with_its_number_glued_chains_through():
    """§5.3 measured 8 moves and ``[não reproduzidos: Be7]``; with ``5. O-O`` it was 16."""
    score, why = game_from_paragraph(_movetext(RUY_8), chess.STARTING_FEN)
    assert why == "game"
    assert len(_sans(score)) == 16
    assert "O-O" in _sans(score)
    last = score
    while last.children:
        last = last.children[0]
    assert not last.comment_after


def test_a_column_with_a_box_and_no_board_above_it_gets_no_position():
    """The last diagram in reading order no longer stands in: with page
    geometry, a column that no readable board sits over stays ``Movetext``
    and says why (``sem diagrama âncora``)."""
    board = _at(_diagram(FEN), 320, 80, 200, 200)          # right column
    column = [
        _at(_movetext("19... g5! 20 g3"), 70, 300),         # left column
        _at(_movetext("20... gxf4 21 gxf4"), 70, 314),
    ]
    report = GamesReport()
    out = attach_games([board, *column], report=report)
    assert report.games == 0
    assert report.kept_no_position == 2
    assert all(isinstance(b, Paragraph) for b in out[1:])
    assert "sem diagrama âncora" in out[1].provenance.note
    assert out[2].provenance.note is None, "only the first paragraph of the column is noted"


def test_the_numbering_of_the_column_must_agree_with_the_anchor():
    # The diagram says White to move (a caption, or the default); the column
    # opens with Black's 19th.  Not this board: kept, with the reason.
    white_to_move = FEN.replace(" b ", " w ")
    blocks = [_diagram(white_to_move), _movetext("19... g5! 20 g3 gxf4")]
    report = GamesReport()
    out = attach_games(blocks, report=report)
    assert report.games == 0
    assert report.kept_anchor_mismatch == 1
    assert report.counters()["movetext_kept_anchor_mismatch"] == 1
    assert "contradiz o lado" in out[1].provenance.note
    # A game's end is a numbered anchor: the column under it must continue it.
    blocks = [
        _diagram(FEN),
        _movetext("19... g5! 20 g3 gxf4"),
        Paragraph(content=(Text(content="prose between"),)),
        _movetext("23 gxf4 Rg8"),
    ]
    report = GamesReport()
    out = attach_games(blocks, report=report)
    assert report.games == 1 and report.kept_anchor_mismatch == 1
    assert isinstance(out[-1], Paragraph)
    assert "não continua" in out[-1].provenance.note


def test_swapped_anchors_yield_no_game(monkeypatch):
    """The sabotage of ``games_gate.py --sabotar ancora`` in miniature: two
    readable boards exchange FENs and no column may chain from the wrong one."""
    other = "8/6k1/3b4/1R1p4/1PpPr1p1/2P3n1/3B2K1/6N1 b - - 0 19"
    left = _at(_diagram(other), 60, 80, 200, 200)           # was FEN
    right = _at(_diagram(FEN), 320, 80, 200, 200)           # was other
    column = [
        _at(_movetext("19... g5! 20 g3"), 70, 300),
        _at(_movetext("20... gxf4 21 gxf4"), 70, 314),
    ]
    report = GamesReport()
    out = attach_games([left, right, *column], report=report)
    assert report.games == 0
    assert all(isinstance(b, Paragraph) for b in out[2:])


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP_C2 passo B3: the NAGs reach the GameScore
# --------------------------------------------------------------------------- #


def _nags(score: GameScore) -> list[tuple[int, ...]]:
    out, node = [], score.children[0]
    while node is not None:
        out.append(node.nags)
        node = node.children[0] if node.children else None
    return out


def test_the_annotation_tail_becomes_the_nodes_nags():
    """``!``, ``!?``, ``±``, the book's ``³`` for ``⩱`` — and the
    side-dependent zugzwang by the side that made the move."""
    paragraph = _movetext("19... g5!? 20 g3± gxf4 21 gxf4³ Rg8! 22 f5⨀")
    score, why = game_from_paragraph(paragraph, FEN)
    assert why == "game"
    assert _sans(score) == ["g5", "g3", "gxf4", "gxf4", "Rg8", "f5"]
    # 19...g5 is Black's: $23 would be Black's zugzwang; 22.f5 is White's: $22.
    assert _nags(score) == [(5,), (16,), (), (15,), (1,), (22,)]


def test_a_move_without_a_tail_has_no_nags():
    paragraph = _movetext("19... g5 20 g3 gxf4 21 gxf4 Rg8 22 f5")
    score, _ = game_from_paragraph(paragraph, FEN)
    assert all(n == () for n in _nags(score))


def test_the_book_symbol_aliases_of_the_informator_font_are_nags():
    from caissa.notation.nag_table import nags_from_suffix

    # The glyph reader's ``⇄`` and the Informator font's ``△``/``⊕``/``◻``.
    assert nags_from_suffix("⇄", False) == (133,)
    assert nags_from_suffix("△") == (140,)
    assert nags_from_suffix("⊕") == (138,)
    assert nags_from_suffix("◻") == (7,)
    # A check mark or an OCR remnant in the tail is skipped, not fatal.
    assert nags_from_suffix("+±") == (16,)
    assert nags_from_suffix("~!") == (1,)
