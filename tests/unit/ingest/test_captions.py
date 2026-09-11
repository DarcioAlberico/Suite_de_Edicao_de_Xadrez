"""Diagram context: side to move, players, event, exercise numbers, folios."""

from __future__ import annotations

import pytest

from caissa.ingest.pdf.captions import (
    CaptionLine,
    assign_lines_to_diagrams,
    bare_integers,
    caption_lines,
    context_from_lines,
    dominant_placement,
    fold,
    lines_near,
    page_contexts,
    page_scope_declaration,
    parse_context,
    running_page_number,
)
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan


def _line(text: str, box: tuple[float, float, float, float], block: int = 0) -> TextLine:
    return TextLine(box=box, spans=(TextSpan(text=text, box=box, size=10.0),), block_index=block)


def _page(lines: list[TextLine], width: float = 612.0, height: float = 792.0) -> PageText:
    return PageText(frame=PageFrame.synthetic(0, width, height), lines=tuple(lines))


# --------------------------------------------------------------------------- #
# Side to move
# --------------------------------------------------------------------------- #


def test_fold_handles_eszett_and_dashes():
    assert fold("Weiß am Zug — sofort") == "weiss am zug - sofort"


@pytest.mark.parametrize(
    ("caption", "white"),
    [
        ("Brancas jogam", True),
        ("31: Jogada das pretas", False),
        ("Jogar de pretas", False),
        ("White to play and win", True),
        ("Black to move", False),
        ("Weiß am Zug", True),
        ("Schwarz zieht", False),
        ("Juegan las blancas", True),
        ("Negras juegan", False),
        ("Les blancs jouent", True),
        ("Trait aux noirs", False),
        ("◻", True),
        ("■", False),
        ("W?", True),
        ("B", False),
    ],
)
def test_side_declarations_in_every_language(caption, white):
    assert parse_context(caption).side_to_move is white


def test_a_hypothetical_clause_is_not_a_declaration():
    """ "Se as brancas jogarem 32.f2xg2" describes a line, not whose turn it is."""
    assert parse_context("se as brancas jogarem 32.f2xg2").side_to_move is None


def test_contradiction_yields_no_side():
    assert parse_context("11: Brancas jogam\n12: Pretas jogam").side_to_move is None


def test_in_prose_the_pattern_must_open_the_line():
    prose = CaptionLine("it was possible for White to play 20.Nd3", (0, 0, 200, 10), block_words=40)
    opener = CaptionLine("White to play and win — do you like it?", (0, 0, 200, 10), block_words=40)
    from caissa.ingest.pdf.captions import NearbyLine

    assert context_from_lines([NearbyLine(prose, 5.0, "below", True)]).side_to_move is None
    assert context_from_lines([NearbyLine(opener, 5.0, "below", True)]).side_to_move is True


def test_the_evidence_is_kept_for_the_user():
    context = parse_context("№79. Steinitz - Bird\nBrancas jogam")
    assert context.side_to_move_evidence == "brancas jogam"
    assert context.side_to_move_origin == "text"


# --------------------------------------------------------------------------- #
# Numbers, players, events
# --------------------------------------------------------------------------- #


def test_players_event_and_number():
    context = parse_context("№79. Steinitz - Bird\nParis, 1858")
    assert context.exercise_number == 79
    assert context.players == ("Steinitz", "Bird")
    assert context.event == "Paris"
    assert context.year == 1858


def test_a_compound_label_is_a_label_not_a_number():
    context = parse_context("4-10\nW?")
    assert context.label == "4-10"
    assert context.exercise_number is None
    assert context.side_to_move is True


def test_a_move_number_is_not_an_exercise_number():
    assert parse_context("3.Kxc7 Kf7 4.Kd6").exercise_number is None


def test_a_page_number_equal_to_the_folio_is_ignored():
    assert parse_context("41", page_number=41).exercise_number is None
    assert parse_context("41", page_number=12).exercise_number == 41


def test_loose_number_prefix_from_split_digits():
    """The AAGAARD numbers ``1 19 Bartrina - Ghitescu`` for exercise 119."""
    context = parse_context("1 19 Bartrina - Ghitescu")
    assert context.exercise_number == 119
    assert context.players == ("Bartrina", "Ghitescu")


def test_moves_and_events_do_not_pass_for_players():
    assert parse_context("12.Na4! - forte").players is None
    assert parse_context("1937 Kemeri").players is None
    assert parse_context("1937 Kemeri").year == 1937


# --------------------------------------------------------------------------- #
# Geometry: nearby lines, placement, assignment
# --------------------------------------------------------------------------- #

BOARD = (100.0, 100.0, 300.0, 300.0)


def test_lines_near_requires_cross_axis_overlap():
    above = CaptionLine("acima", (120, 80, 280, 92), 2)
    beside_other_column = CaptionLine("outra coluna", (320, 80, 500, 92), 2)
    found = lines_near([above, beside_other_column], BOARD)
    assert [n.text for n in found] == ["acima"]
    assert found[0].placement == "above"


def test_dominant_placement_is_decided_per_page():
    """Distance alone assigns systematically wrong (Karpov: 10 pt above, 7 pt below)."""
    boards = [(100.0, 100.0, 300.0, 300.0), (100.0, 329.0, 300.0, 529.0)]
    # Captions 10 pt above each board; the caption of board 2 is therefore
    # only 7 pt below board 1 -- the trap distance alone falls into.
    lines = [
        CaptionLine("№79. Steinitz - Bird", (120, 78, 280, 90), 4, group_id=0),
        CaptionLine("№80. Steinitz - Mortimer", (120, 307, 280, 319), 4, group_id=1),
    ]
    buckets = assign_lines_to_diagrams(lines, boards)
    assert [n.text for n in buckets[0] if n.primary] == ["№79. Steinitz - Bird"]
    assert [n.text for n in buckets[1] if n.primary] == ["№80. Steinitz - Mortimer"]


def test_a_group_serves_one_diagram_only():
    boards = [(100.0, 100.0, 300.0, 300.0), (350.0, 100.0, 550.0, 300.0)]
    lines = [CaptionLine("5", (120, 305, 280, 317), 1, group_id=0)]
    buckets = assign_lines_to_diagrams(lines, boards)
    assert [n.primary for n in buckets[0]] == [True]
    assert buckets[1] == []


def test_move_text_never_claims_a_caption():
    """Analysis continuing from the previous page sits above the board."""
    boards = [BOARD]
    lines = [
        CaptionLine("♕b3+! 4.♕xb3 axb3+", (120, 60, 280, 72), 3, group_id=0),
        CaptionLine("16-43", (180, 305, 220, 317), 1, group_id=1),
    ]
    buckets = assign_lines_to_diagrams(lines, boards)
    primary = [n.text for n in buckets[0] if n.primary]
    assert primary == ["16-43"]


def test_a_group_within_reach_comes_whole():
    """ "W?" printed under "4-10" is 71 pt from the board and still caption."""
    lines = [
        CaptionLine("4-10", (180, 340, 220, 352), 2, group_id=0),
        CaptionLine("W?", (185, 358, 215, 370), 2, group_id=0),
    ]
    buckets = assign_lines_to_diagrams(lines, [BOARD])
    assert [n.text for n in buckets[0]] == ["4-10", "W?"]
    context = context_from_lines(buckets[0])
    assert context.label == "4-10"
    assert context.side_to_move is True


def test_dominant_placement_none_without_candidates():
    assert dominant_placement([], {}, 1) is None


# --------------------------------------------------------------------------- #
# Page lines: margin band, axis labels, column split
# --------------------------------------------------------------------------- #


def test_caption_lines_drop_the_margin_band_and_axis_labels():
    lines = [
        _line("Cabeçalho corrente", (72, 30, 300, 42), block=0),
        _line("41", (300, 770, 312, 782), block=1),
        _line("a b c d e f g h", (100, 305, 300, 317), block=2),
    ]
    lines += [
        _line(str(d), (88, 100 + i * 25, 96, 112 + i * 25), block=3 + i)
        for i, d in enumerate("87654321")
    ]
    lines.append(_line("Brancas jogam", (120, 330, 280, 342), block=20))
    page = _page(lines)
    body = caption_lines(page)
    assert [line.text for line in body] == ["Brancas jogam"]
    margin = caption_lines(page, margin=True)
    assert {line.text for line in margin} == {"Cabeçalho corrente", "41"}


def test_crosstable_results_are_not_axis_labels():
    """The 1937 Kemeri crosstable has dozens of loose 1s -- repeated, not a border."""
    lines = [_line("1", (100 + i * 20, 200, 108 + i * 20, 212), block=i) for i in range(8)]
    page = _page(lines)
    assert len(caption_lines(page)) == 8


def test_one_block_spanning_two_columns_is_split_into_groups():
    lines = [
        _line("№79. Steinitz - Bird", (82, 80, 181, 92), block=0),
        _line("№80. Steinitz - Mortimer", (278, 80, 402, 92), block=0),
    ]
    out = caption_lines(_page(lines))
    assert out[0].group_id != out[1].group_id


def test_page_scope_declaration_in_the_margin():
    page = _page([_line("LAS BLANCAS JUEGAN PRIMERO", (72, 30, 400, 42))])
    scope = page_scope_declaration(page)
    assert scope is not None
    assert scope.color is True
    assert scope.origin == "text-page-scope"


def test_page_contexts_apply_scope_only_where_the_caption_is_silent():
    lines = [
        _line("LAS BLANCAS JUEGAN PRIMERO", (72, 30, 400, 42), block=0),
        _line("12", (180, 305, 220, 317), block=1),
        _line("Jogada das pretas", (400, 305, 540, 317), block=2),
    ]
    boards = [(100.0, 100.0, 300.0, 300.0), (350.0, 100.0, 550.0, 300.0)]
    contexts, consumed = page_contexts(_page(lines), boards)
    assert contexts[0].side_to_move is True
    assert contexts[0].side_to_move_origin == "text-page-scope"
    assert contexts[1].side_to_move is False
    assert contexts[1].side_to_move_origin == "text"
    assert len(consumed) == 2


# --------------------------------------------------------------------------- #
# Printed folio
# --------------------------------------------------------------------------- #


def test_running_page_number_needs_a_consecutive_neighbour_in_the_same_column():
    current = [(46, (300.0, 770.0, 312.0, 782.0)), (10, (150.0, 320.0, 162.0, 332.0))]
    neighbours = {1: [(47, (300.0, 770.0, 312.0, 782.0)), (11, (150.0, 320.0, 162.0, 332.0))]}
    # Both step by one; the folio is the one at the page edge.
    assert running_page_number(current, neighbours, 792.0) == 46
    assert running_page_number(current, {}, 792.0) is None
    assert running_page_number([], neighbours, 792.0) is None


def test_bare_integers_of_a_page():
    page = _page(
        [_line("(41)", (0, 0, 10, 10)), _line("4-10", (0, 20, 10, 30)), _line("7", (0, 40, 5, 50))]
    )
    assert [v for v, _ in bare_integers(page)] == [41, 7]
