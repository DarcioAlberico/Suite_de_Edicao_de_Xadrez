"""The R collision -- the reason front F6 exists.

``R`` is the **king** in Portuguese, Spanish, French and Italian and the
**rook** in English.  The two readings are frequently legal at the same time,
and picking the wrong one does not raise an error: it substitutes one piece for
another and quietly rewrites every move after it.

Every test here reads its input **without being told the language**.  Being told
would make the problem trivial and would not be the situation the program is
actually in when a user drops a PDF on it.

The positions are chosen so that the collision is real.  In a rook ending
``Rf1`` is a legal rook move *and* a legal king move, so legality alone cannot
decide and the language evidence has to carry it.  A test that used a position
where only one reading is legal would pass with the logic removed.
"""

from __future__ import annotations

import chess
import pytest

from caissa.notation.languages import detect_language, to_language
from caissa.notation.legality_repair import repair_movetext

# White Kf2 + Rf5, Black Kb7.  The line was searched for, not written: **every
# one of White's six moves is legal as a rook move and as a king move**, so the
# board cannot decide a single one of them and the language evidence has to
# carry all six.  `test_the_collision_is_real` re-derives that property, so a
# future edit to the line cannot quietly make these tests trivial.
ROOK_ENDING_FEN = "8/1k6/8/5R2/8/8/5K2/8 w - - 0 1"

ROOK_ENDING_MOVES = [
    "Rf3", "Ka8", "Kg3", "Ka7", "Rf2", "Ka6",
    "Kf3", "Ka5", "Kg2", "Kb4", "Rf3", "Ka4",
]

PROSE = {
    "pt": "As brancas jogam e ganham este final de torre.",
    "es": "Las blancas juegan y ganan este final de torre.",
    "fr": "Les blancs jouent et gagnent cette finale de tour.",
    "it": "Il bianco muove e vince questo finale di torre.",
    "en": "White plays and wins this rook endgame.",
}


def _numbered(moves: list[str], lang: str | None) -> str:
    """The move list as a book prints it, in ``lang`` (``None`` = English SAN)."""
    out = []
    for index, san in enumerate(moves):
        text = san if lang is None else to_language(san, lang)
        out.append(f"{index // 2 + 1}.{text}" if index % 2 == 0 else text)
    return " ".join(out)


class TestTheCollisionIsReal:
    """Guard the guard: if these stop being ambiguous the tests below prove nothing."""

    def test_every_white_move_is_legal_as_both_a_rook_and_a_king_move(self):
        board = chess.Board(ROOK_ENDING_FEN)
        ambiguous = 0
        for san in ROOK_ENDING_MOVES:
            if board.turn == chess.WHITE:
                legal = {board.san(move).rstrip("+#") for move in board.legal_moves}
                other = ("K" if san[0] == "R" else "R") + san[1:]
                assert san.rstrip("+#") in legal
                assert other.rstrip("+#") in legal, (
                    f"{san} must also be legal as {other}, or this ply proves nothing"
                )
                ambiguous += 1
            board.push_san(san)
        assert ambiguous == 6

    def test_r_means_opposite_pieces_in_the_two_languages(self):
        assert to_language("Kf1", "pt") == "Rf1"
        assert to_language("Rf1", "pt") == "Tf1"


class TestPortuguese:
    """Stratum E7: the user's own books."""

    def test_a_portuguese_rook_ending_reads_r_as_the_king(self):
        text = f"{PROSE['pt']} {_numbered(ROOK_ENDING_MOVES, 'pt')}"
        report = repair_movetext(text, start_fen=ROOK_ENDING_FEN)

        assert [move.san for move in report.moves] == ROOK_ENDING_MOVES
        assert report.replayed_to_end
        assert report.language == "pt"

    def test_a_portuguese_opening_reads_every_letter(self):
        text = (
            "Nesta abertura as brancas ameacam. "
            "1.e4 e5 2.Cf3 Cc6 3.Bb5 a6 4.Bxc6 dxc6 5.O-O f6 6.d4 exd4 "
            "7.Cxd4 c5 8.Cb3 Dxd1 9.Txd1 Bg4 10.f3 Be6 11.Cc3 Rf7"
        )
        report = repair_movetext(text)
        sans = [move.san for move in report.moves]
        assert sans[-1] == "Kf7", "the last move is the king, not a rook"
        assert sans[-5:] == ["Rxd1", "Bg4", "f3", "Be6", "Nc3", "Kf7"][-5:]
        assert "Rxd1" in sans, "T is the rook and must become R"
        assert report.replayed_to_end


class TestEnglish:
    """The other half of the trap: an English PGN must not be 'translated'."""

    def test_an_english_rook_ending_leaves_r_as_the_rook(self):
        text = f"{PROSE['en']} {_numbered(ROOK_ENDING_MOVES, None)}"
        report = repair_movetext(text, start_fen=ROOK_ENDING_FEN)

        assert [move.san for move in report.moves] == ROOK_ENDING_MOVES
        assert report.language is None, "English SAN is read as-is, not via a locale"
        assert report.repaired_count == 0, "nothing in a correct English PGN needs repair"

    def test_a_plain_english_pgn_is_untouched(self):
        text = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 O-O"
        report = repair_movetext(text)
        assert report.language is None
        assert report.repaired_count == 0
        sans = [move.san for move in report.moves]
        assert sans == [
            "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6",
            "O-O", "Be7", "Re1", "b5", "Bb3", "O-O",
        ]
        assert "Re1" in sans, "R stays a rook"


@pytest.mark.parametrize("lang", ["pt", "es", "fr", "it"])
class TestEveryRLanguage:
    """The same trap in all four languages that share it."""

    def test_the_rook_ending_survives(self, lang):
        text = f"{PROSE[lang]} {_numbered(ROOK_ENDING_MOVES, lang)}"
        report = repair_movetext(text, start_fen=ROOK_ENDING_FEN)

        assert [move.san for move in report.moves] == ROOK_ENDING_MOVES
        assert report.language == lang
        assert not report.reading_disputed, "the tied locales must agree on every move"

    def test_kings_and_rooks_are_told_apart_in_the_same_line(self, lang):
        # 33.Rd7+ Kf8 34.Rd8+ Kg7 -- an `R` move and a `K` move next to each
        # other, printed with the same letter in these four languages.
        fen = "5k2/8/8/8/8/8/3R4/6K1 w - - 0 33"
        moves = ["Rd7", "Kg8", "Rd8+", "Kh7", "Kg2", "Kg6"]
        text = f"{PROSE[lang]} " + " ".join(
            f"{33 + i // 2}.{to_language(san, lang)}" if i % 2 == 0 else to_language(san, lang)
            for i, san in enumerate(moves)
        )
        report = repair_movetext(text, start_fen=fen)
        assert [move.san for move in report.moves] == moves


class TestDetectionUnderCollision:
    """What the detector itself claims, separately from what the repair does."""

    def test_a_page_with_no_disambiguating_letter_abstains(self):
        # Only `R` and `T` appear: `R` fits five locales and `T` fits six.
        detection = detect_language("18.Tf3 Rg8 19.Td3 Rf8 20.Te3 Rg8")
        assert detection.abstained
        assert detection.best is None

    def test_but_it_still_answers_the_question_that_matters(self):
        detection = detect_language("18.Tf3 Rg8 19.Td3 Rf8 20.Te3 Rg8")
        assert detection.consensus_pieces is not None
        assert detection.consensus_pieces["R"] == "K", (
            "every locale still in contention reads R as the king, "
            "so the abstention does not block the translation"
        )
        assert detection.piece_map()["T"] == "R"

    def test_an_english_page_is_not_ambiguous_at_all(self):
        detection = detect_language("1.e4 e5 2.Nf3 Nc6 3.Bb5 Qd8 4.Re1 Kf8")
        assert detection.best == "en"
        assert not detection.abstained
        assert detection.piece_map()["R"] == "R"
