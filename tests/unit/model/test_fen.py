"""FEN structure and chess legality, with no ``python-chess`` in sight.

Two layers, deliberately separate:

``validate_fen``
    Structural. Is this six-field string shaped like a FEN at all? A malformed
    string is an import bug.
``position_problems``
    Chess. Could this position exist? Two white kings, a pawn on the first rank
    or seventeen black pieces did not come off a board -- they came off a
    misread square, which is exactly the failure SPEC 6.4's repair solver has to
    catch.

Keeping them apart matters because the UI reacts differently: a malformed FEN is
an error, an illegal position is a prompt to review the amber squares.
"""

from __future__ import annotations

import pytest

from caissa.core.chess.fen import (
    EMPTY_BOARD_FEN,
    PIECE_LETTERS,
    STARTING_FEN,
    FenError,
    board_squares,
    is_valid_fen,
    parse_fen,
    position_problems,
    validate_fen,
)

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fen",
    [
        STARTING_FEN,
        EMPTY_BOARD_FEN,
        KIWIPETE,
        "8/8/8/4k3/8/8/4K3/8 w - - 0 1",
        "4k3/8/8/8/8/8/8/4K2R w K - 0 1",
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "8/8/8/8/8/8/8/8 w - -",
        "8/8/8/8/8/8/8/8 w - - 0",
        "r3k2r/8/8/8/8/8/8/R3K2R w AHah - 0 1",
    ],
)
def test_well_formed_fens_are_accepted(fen):
    assert validate_fen(fen) == ()
    assert is_valid_fen(fen)


@pytest.mark.parametrize(
    ("fen", "fragment"),
    [
        ("", "vazia"),
        ("   ", "vazia"),
        ("8/8/8", "ao menos"),
        ("8/8/8/8/8/8/8/8 w - - 0 1 extra", "no maximo"),
        ("8/8/8/8/8/8/8 w - - 0 1", "8 fileiras"),
        ("8/8/8/8/8/8/8/8/8 w - - 0 1", "8 fileiras"),
        ("ppppppppp/8/8/8/8/8/8/8 w - - 0 1", "9 casas"),
        ("9/8/8/8/8/8/8/8 w - - 0 1", "caracteres invalidos"),
        ("7/8/8/8/8/8/8/8 w - - 0 1", "7 casas"),
        ("44/8/8/8/8/8/8/8 w - - 0 1", "digitos consecutivos"),
        ("8/8/8/8/8/8/8/XXXXXXXX w - - 0 1", "caracteres invalidos"),
        ("8/8/8/8/8/8/8/8 x - - 0 1", "lado a jogar"),
        ("8/8/8/8/8/8/8/8 w KQKQ - 0 1", "letras repetidas"),
        ("8/8/8/8/8/8/8/8 w ZZ - 0 1", "roque invalido"),
        ("8/8/8/8/8/8/8/8 w - e4 0 1", "en passant"),
        ("8/8/8/8/8/8/8/8 w - - x 1", "meio-lance"),
        ("8/8/8/8/8/8/8/8 w - - 0 0", "numero do lance"),
    ],
)
def test_malformed_fens_are_reported_with_a_readable_reason(fen, fragment):
    problems = validate_fen(fen)
    assert problems, f"{fen!r} was accepted"
    assert any(fragment in problem for problem in problems), problems


def test_every_problem_is_reported_not_just_the_first():
    problems = validate_fen("ppppppppp/8/8/8/8/8/8/8 x KQKQ e4 0 1")
    assert len(problems) >= 3


def test_parse_raises_on_the_first_problem():
    with pytest.raises(FenError, match="fileira"):
        parse_fen("ppppppppp/8/8/8/8/8/8/8 w - - 0 1")


def test_a_non_string_is_refused_rather_than_crashing():
    assert validate_fen(None) == ("FEN vazia.",)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def test_squares_are_indexed_from_a1():
    position = parse_fen(STARTING_FEN)
    assert position.piece_at(0) == "R", "a1"
    assert position.piece_at(4) == "K", "e1"
    assert position.piece_at(60) == "k", "e8"
    assert position.piece_at(63) == "r", "h8"
    assert position.piece_at(32) == "", "a5 is empty"


def test_board_squares_returns_sixty_four_entries():
    squares = board_squares(STARTING_FEN)
    assert len(squares) == 64
    assert sum(1 for square in squares if square) == 32


def test_piece_counts_are_readable():
    position = parse_fen(STARTING_FEN)
    assert position.count("P") == 8
    assert position.count("k") == 1
    assert position.count("Q") == 1


def test_the_trailing_fields_are_parsed():
    position = parse_fen(KIWIPETE)
    assert position.side_to_move == "w"
    assert position.castling == "KQkq"
    assert position.en_passant == "-"
    assert position.halfmove_clock == 0
    assert position.fullmove_number == 1


def test_short_forms_default_their_clocks():
    position = parse_fen("8/8/8/8/8/8/8/8 w - -")
    assert position.halfmove_clock == 0
    assert position.fullmove_number == 1


@pytest.mark.parametrize("fen", [STARTING_FEN, KIWIPETE, EMPTY_BOARD_FEN])
def test_a_parsed_position_re_renders_to_the_same_fen(fen):
    assert parse_fen(fen).to_fen() == fen


def test_the_placement_field_re_renders_with_runs_collapsed():
    position = parse_fen("8/8/8/3k4/8/8/8/3K4 w - - 0 1")
    assert position.placement_field() == "8/8/8/3k4/8/8/8/3K4"


def test_every_piece_letter_survives_a_parse():
    fen = "kqrbnp2/8/8/8/8/8/8/KQRBNP2 w - - 0 1"
    squares = set(board_squares(fen))
    assert squares - {""} == set(PIECE_LETTERS) - {""}


# --------------------------------------------------------------------------- #
# Chess legality (SPEC 6.4)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fen", [STARTING_FEN, KIWIPETE, "8/8/8/4k3/8/4K3/4P3/8 w - - 0 1"])
def test_a_real_position_has_no_legality_problems(fen):
    assert position_problems(fen) == ()


@pytest.mark.parametrize(
    ("fen", "fragment"),
    [
        ("4k3/8/8/8/8/8/8/K3K3 w - - 0 1", "2 reis das brancas"),
        ("k3k3/8/8/8/8/8/8/4K3 w - - 0 1", "2 reis das pretas"),
        ("4k3/8/8/8/8/8/8/8 w - - 0 1", "nao ha rei das brancas"),
        ("8/8/8/8/8/8/8/4K3 w - - 0 1", "nao ha rei das pretas"),
        ("4k3/PPPPPPPP/PP6/8/8/8/8/4K3 w - - 0 1", "peoes das brancas"),
        ("4k3/8/8/8/8/8/8/P3K3 w - - 0 1", "peao em a1"),
        ("P3k3/8/8/8/8/8/8/4K3 w - - 0 1", "peao em a8"),
        ("8/8/8/8/8/8/8/3Kk3 w - - 0 1", "adjacentes"),
        ("4k3/8/8/8/8/8/8/4K3 w - - 0 1", None),
    ],
)
def test_impossible_positions_are_reported(fen, fragment):
    problems = position_problems(fen)
    if fragment is None:
        assert problems == ()
    else:
        assert any(fragment in problem for problem in problems), problems


def test_too_many_pieces_on_one_side_is_reported():
    seventeen_white = "4k3/8/8/8/QQQQQQQQ/QQQQQQQQ/QQQ5/4K3 w - - 0 1"
    assert any("pecas brancas" in problem for problem in position_problems(seventeen_white))


def test_kings_diagonally_adjacent_count_as_touching():
    problems = position_problems("8/8/8/3k4/4K3/8/8/8 w - - 0 1")
    assert any("adjacentes" in problem for problem in problems)


def test_kings_a_knights_move_apart_do_not():
    assert position_problems("8/8/8/3k4/8/4K3/8/8 w - - 0 1") == ()


def test_a_composed_problem_may_omit_a_king_when_asked():
    """A study sometimes has no black king; a scanned game diagram never does."""
    fen = "8/8/8/8/8/8/8/4K3 w - - 0 1"
    assert position_problems(fen) != ()
    assert position_problems(fen, allow_composition=True) == ()


def test_legality_checks_refuse_to_run_on_a_malformed_fen():
    """It returns the structural problems rather than pretending to parse."""
    broken = "ppppppppp/8/8/8/8/8/8/8 w - - 0 1"
    assert position_problems(broken) == validate_fen(broken)


def test_the_empty_board_is_structurally_valid_but_has_no_kings():
    assert validate_fen(EMPTY_BOARD_FEN) == ()
    assert len(position_problems(EMPTY_BOARD_FEN)) == 2
    assert position_problems(EMPTY_BOARD_FEN, allow_composition=True) == ()


def test_every_message_is_in_portuguese():
    """The user reads these; SPEC says the product speaks pt-BR."""
    problems = [
        *validate_fen("ppppppppp/8/8/8/8/8/8/8 x - - 0 1"),
        *position_problems("4k3/8/8/8/8/8/8/K3K3 w - - 0 1"),
    ]
    assert problems
    for problem in problems:
        assert not problem[0].isupper() or problem.startswith("FEN"), problem
        assert any(word in problem for word in ("fileira", "lado", "rei", "reis", "campo", "peao"))
