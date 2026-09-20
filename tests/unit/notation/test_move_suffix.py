"""The tail of a move -- OCR_UI_ROADMAP_C2 passo A4 (analysis §5.2).

Eight places in the program knew, each in its own words, what may trail a move:
``!?±∓`` here, ``+#!?`` there, and two of them spelled ``⩲`` (U+2A72) as ``⧲``
(U+29F2, an "error-barred square" no book prints).  A move printed ``Nf6⩲``
therefore failed the repairer's shape gate, was skipped *as prose*, and the
replay lost every move after it -- silently.  The same narrow alphabets sat in
the instruments, which is why the loss was never measured.

Now there is one alphabet, :data:`caissa.notation.nag_table.MOVE_SUFFIX_CHARS`,
and the tests below fail if any consumer stops accepting a glyph of it.  The
first block is the measurement of the analysis, re-run as a test: it used to
assert 7 and 0, and now asserts 10 and 6.
"""

from __future__ import annotations

import re

import chess
import pytest
from chess import STARTING_FEN as FEN

from caissa.notation.legality_repair import (
    RepairedMove,
    Skipped,
    _is_move_like,
    _MOVE_SHAPE,
    _PUNCTUATION,
    _TRAILING_JUNK,
    repair_movetext,
    split_tail,
)
from caissa.notation.nag_table import (
    BOOK_SYMBOL_ALIASES,
    MOVE_SUFFIX_CHARS,
    SEARCHABLE_GLYPHS,
    move_suffix_class,
)

#: A code point that is *not* in the table -- the one the old alphabets had.
OUTSIDE = "⧲"

RUY = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6"


# --------------------------------------------------------------------------- #
# The block of the analysis (§5.2), as a test
# --------------------------------------------------------------------------- #


def test_the_measured_loss_of_the_analysis_is_gone():
    """§5.2 measured ``Nf6⩲`` → 7 moves with ``O-O`` unresolved and the long
    notation with a dash → 0 moves, silently.  Both replay to the end now."""
    report = repair_movetext(f"{RUY}⩲ 5.O-O Be7", start_fen=FEN)
    assert (len(report.moves), report.unresolved) == (10, ())
    assert report.replayed_to_end

    report = repair_movetext("1.e2—e4 e7—e5 2.Ng1—f3 Nb8—c6 3.Bf1—b5 a7—a6", start_fen=FEN)
    assert (len(report.moves), report.unresolved) == (6, ())
    assert [m.san for m in report.moves] == ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"]


@pytest.mark.parametrize("suffix", ["±", "⩲", "⩱", "²", "³", "!?", "+-", "-+", "∞", "©", "⨀", "ʘ", "□", "→", "∆"])
def test_every_glyph_of_the_table_may_trail_a_move(suffix):
    report = repair_movetext(f"{RUY}{suffix} 5.O-O Be7", start_fen=FEN)
    assert len(report.moves) == 10, (suffix, report.unresolved)
    assert report.moves[7].suffix == suffix
    assert report.moves[7].san == "Nf6"


def test_the_product_path_keeps_the_annotated_move():
    """The importer's chain (movetext run → repair → GameScore)."""
    from caissa.core.model import Paragraph
    from caissa.core.model.inline import Text
    from caissa.ingest.pdf.games import game_from_paragraph

    for suffix in ("±", "⩲", "²"):
        paragraph = Paragraph(content=(Text(content=f"{RUY}{suffix} 5. O-O Be7"),))
        game, why = game_from_paragraph(paragraph, FEN)
        assert game is not None, why
        node, sans = game, []
        while node.children:
            node = node.children[0]
            sans.append(node.san)
        assert len(sans) == 10, (suffix, sans)
        assert not node.comment_after, (suffix, node.comment_after)


# --------------------------------------------------------------------------- #
# One alphabet
# --------------------------------------------------------------------------- #


def test_the_table_is_derived_from_the_nag_table():
    expected = set("".join(SEARCHABLE_GLYPHS) + "".join(BOOK_SYMBOL_ALIASES) + "!?+#")
    assert set(MOVE_SUFFIX_CHARS) == expected
    assert "⩲" in MOVE_SUFFIX_CHARS and "⩱" in MOVE_SUFFIX_CHARS
    assert OUTSIDE not in MOVE_SUFFIX_CHARS
    assert len(set(MOVE_SUFFIX_CHARS)) == len(MOVE_SUFFIX_CHARS)


def test_no_consumer_alphabet_has_a_code_point_outside_the_table():
    """The guard the roadmap asks for: every alphabet a reader or an instrument
    keeps for the tail of a move is a subset of the one table (punctuation
    that is not annotation -- ``.,;:)`` -- is listed apart and allowed)."""
    from caissa.ocr import fusion, lexicon, metrics

    assert set(_TRAILING_JUNK) - set(_PUNCTUATION) <= set(MOVE_SUFFIX_CHARS)
    assert set(lexicon._ANNOTATION_MARKS) <= set(MOVE_SUFFIX_CHARS)
    assert set(fusion._MARKS) - set(".,;:") <= set(MOVE_SUFFIX_CHARS)
    wordlike = {ch for ch in MOVE_SUFFIX_CHARS if re.match(r"\w", ch)}
    assert set(re.sub(r"\\", "", metrics._WORDLIKE_SUFFIX)) <= wordlike


@pytest.mark.parametrize("glyph", sorted(set(MOVE_SUFFIX_CHARS) - set("+#")))
def test_every_reader_accepts_every_glyph_as_a_tail(glyph):
    """Regexes cannot be introspected, so they are exercised: a move followed
    by any glyph of the table is a move for the repairer, the lexicon, the
    cipher, the run extractor and the two instruments."""
    from caissa.ocr.lexicon import is_move_token
    from caissa.ocr.notation.cipher import _split
    from caissa.ocr.notation.movetext import _is_move, _piece_letters

    token = f"Nf6{glyph}"
    assert _is_move_like(token), token
    assert _MOVE_SHAPE.match(token), token
    assert is_move_token(token), token
    assert _split(token) is not None and _split(token)[0] == "N", token
    assert _is_move(token, _piece_letters("")), token
    assert _is_move(f"O-O{glyph}", _piece_letters("")), glyph


def test_a_code_point_outside_the_table_is_not_a_tail():
    from caissa.ocr.lexicon import is_move_token
    from caissa.ocr.notation.cipher import _split

    token = f"Nf6{OUTSIDE}"
    assert not is_move_token(token)
    assert _split(token) is None
    assert re.search(rf"[{move_suffix_class()}]", OUTSIDE) is None


def test_the_instrument_counts_an_annotated_piece_move():
    """Sabotage of the roadmap, made permanent: append ``±`` to the truth's
    piece moves and the instrument's count must not change (the old
    ``[+#!?]`` pattern lost every one of them)."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "notation_integrity",
        Path(__file__).resolve().parents[3] / "benchmarks" / "notation_integrity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    truth = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 d6"
    sabotaged = re.sub(r"\b([KQRBN][a-h]?[1-8]?x?[a-h][1-8])", r"\1±", truth)
    assert sabotaged != truth
    assert module._piece_moves(sabotaged) == module._piece_moves(truth)
    assert module.piece_prefixes(sabotaged)[:3] == module.piece_prefixes(truth)[:3]
    assert sum(module._piece_moves(truth).values()) == 8
    old = re.compile(r"^(?:\d{1,3}\.{1,3})?([KQRBNP♔♕♖♗♘♙])([a-h]?[1-8]?[x:×]?[a-h][1-8])"
                     r"(?:=[A-Za-z])?[+#!?]{0,3}$")
    assert sum(1 for t in sabotaged.split() if old.match(t)) == 0


def test_metrics_do_not_hide_a_move_before_a_wordlike_glyph():
    from caissa.ocr.metrics import move_tokens

    assert move_tokens("4.Ba4 Nf6ƒ 5.O-O") == ["Ba4", "Nf6", "O-O"]
    assert move_tokens("Nf6Δ") == ["Nf6"]
    assert move_tokens("the e4-square") == []


# --------------------------------------------------------------------------- #
# The tail, separated
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("token", "core", "suffix"),
    [
        ("Nf6⩲", "Nf6", "⩲"),
        ("Nf6±!,", "Nf6", "±!"),
        ("Rad8³", "Rad8", "³"),
        ("Nxe4!µ", "Nxe4", "!µ"),
        ("Nf3+", "Nf3+", ""),
        ("Qf7#!", "Qf7#", "!"),
        ("Nf3+-", "Nf3", "+-"),
        ("Bg6—+", "Bg6", "—+"),
        ("Qxe4†", "Qxe4+", ""),
        ("Qxe4ch", "Qxe4+", ""),
        ("Qf7++", "Qf7#", ""),
        ("Qh7mate", "Qh7#", ""),
        ("(Nf3)", "Nf3", ""),
        ("Kd3ʘ", "Kd3", "ʘ"),
        ("e8=Q", "e8=Q", ""),
        ("O-O", "O-O", ""),
        ("much", "much", ""),
    ],
)
def test_split_tail(token, core, suffix):
    assert split_tail(token) == (core, suffix)


def test_the_repaired_move_carries_its_suffix_and_the_board_keeps_the_mark():
    report = repair_movetext("1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7‡", start_fen=FEN)
    last = report.moves[-1]
    assert isinstance(last, RepairedMove)
    assert (last.san, last.suffix) == ("Qxf7#", "")
    report = repair_movetext("1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6?? 4.Qxf7#!!", start_fen=FEN)
    assert [m.suffix for m in report.moves] == ["", "", "", "", "", "??", "!!"]


def test_the_dashes_of_long_notation_are_the_ones_castling_accepts():
    """Every dash of ``_DASHES`` reads as "moves to"."""
    from caissa.notation.legality_repair import _DASHES

    for dash in _DASHES:
        if dash == "_":
            continue
        report = repair_movetext(f"1.e2{dash}e4 e7{dash}e5", start_fen=FEN)
        assert [m.san for m in report.moves] == ["e4", "e5"], repr(dash)


# --------------------------------------------------------------------------- #
# Skipped, not vanished
# --------------------------------------------------------------------------- #


def test_prose_between_two_moves_is_recorded():
    report = repair_movetext("1.e4 e5 2.Nf3 and now Nc6 3.Bb5 a6 wins", start_fen=FEN)
    assert len(report.moves) == 6
    assert report.skipped == (
        Skipped(raw="and", ply=3, reason="not shaped like a move"),
        Skipped(raw="now", ply=3, reason="not shaped like a move"),
    )


def test_prose_before_the_first_or_after_the_last_move_is_not_between_moves():
    report = repair_movetext("White plays 1.e4 e5 2.Nf3 Nc6 and Black is fine", start_fen=FEN)
    assert len(report.moves) == 4
    assert report.skipped == ()


def test_promotion_aliases_are_moves_but_a_slash_in_prose_is_not():
    """``b8/Q`` and ``b8(Q)`` (the English locale's aliases) reach the board;
    ``e4/e5`` in "the e4/e5 squares" stays prose, although ``/`` is in the tail
    alphabet through ``+/-``."""
    assert _is_move_like("b8/Q") and _is_move_like("b8(Q)") and _is_move_like("bxa8/Q!")
    assert not _is_move_like("e4/e5") and not _is_move_like("(e4/e5)")
    report = repair_movetext("1.e4 e5 the e4/e5 squares 2.Nf3 Nc6", start_fen=FEN)
    assert len(report.moves) == 4 and report.unresolved == ()
    assert [s.raw for s in report.skipped] == ["the", "e4/e5", "squares"]
    report = repair_movetext("1.e4 d5 2.exd5 c6 3.dxc6 Nf6 4.cxb7 Nbd7 5.bxa8/Q", start_fen=FEN)
    assert report.moves[-1].san == "bxa8=Q"
    report = repair_movetext("1.e4 d5 2.exd5 c6 3.dxc6 Nf6 4.cxb7 Nbd7 5.bxa8(Q)", start_fen=FEN)
    assert report.moves[-1].san == "bxa8=Q"


def test_the_board_is_still_the_judge():
    """A tail never makes an illegal move legal."""
    board = chess.Board(FEN)
    assert "Qxh7" not in [board.san(m) for m in board.legal_moves]
    report = repair_movetext("1.Qxh7±", start_fen=FEN)
    assert report.moves == () and len(report.unresolved) == 1
    assert report.unresolved[0].raw == "Qxh7±"
