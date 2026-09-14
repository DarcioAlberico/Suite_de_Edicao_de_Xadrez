"""The book's figurine cipher — OCR_UI_ROADMAP passo 3.

Three things have to hold, and each has a test that fails when it stops
holding: a symbol is applied only when the book's evidence settled it
(support, and no contradiction beyond a visual classifier's own error rate);
a table never touches a page whose notation was never broken; and the
replay proves symbols by trying the assignments as hypotheses, refusing a
tie.
"""

from __future__ import annotations

from pathlib import Path

import chess

from caissa.notation.legality_repair import repair_movetext
from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.notation.book_cipher import BookCipher
from caissa.ocr.notation.validate import validate_region
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind


def _reading(text: str, conf: float = 0.8, engine: str = "tesseract") -> OcrResult:
    words = tuple(OcrWord(text=t, box=BBox(10.0 + 60 * i, 8.0, 50.0, 18.0), confidence=conf,
                          word_index=i) for i, t in enumerate(text.split()))
    line = OcrLine(words=words, box=BBox(10.0, 8.0, 60.0 * len(words), 18.0), baseline=None,
                   block_index=0, paragraph_index=0, line_index=0, kind=RegionKind.MOVETEXT)
    return OcrResult(engine=engine, lang="eng", lines=(line,), region_kind=RegionKind.MOVETEXT)


DECISION = RegionDecision(Decision.REVIEW, 0.6, 0.78, 0.55, ())
TABLE = {"W": "Q", "H": "R", "&": "B", "S": "K"}


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #


def test_a_row_is_proven_by_five_legal_proofs_or_ten_visual_ones_and_no_contradiction():
    table = BookCipher(fingerprint="abc")
    for _ in range(4):
        table.observe("W", "Q", raw="Wd5", san="Qd5")
    assert table.proven() == {}, "four legality proofs are not five"
    table.observe("W", "Q", raw="Wc3", san="Qc3")
    assert table.proven() == {"W": "Q"}
    for _ in range(9):
        table.observe("H", "R", source="glyph")
    assert "H" not in table.proven(), "nine visual proofs are not ten"
    table.observe("H", "R", source="glyph")
    assert table.proven()["H"] == "R"
    table.observe("W", "B", raw="Wf4", san="Bf4")
    assert "W" not in table.proven(), "one contradiction demotes a legality row"
    assert table.entries["W"].disputed == {"B": 1}
    assert "contraditada" in table.describe_pt()


def test_a_visual_row_tolerates_the_classifier_error_rate_and_no_more():
    table = BookCipher()
    for _ in range(50):
        table.observe("S", "K", source="glyph")
    table.observe("S", "N", source="glyph")
    assert table.proven()["S"] == "K", "1 in 51 is the glyph reader's own error rate"
    table.observe("S", "N", source="glyph")
    assert "S" not in table.proven(), "2 in 52 is above 2 %"


def test_the_table_round_trips_and_refuses_another_books_fingerprint(tmp_path: Path):
    table = BookCipher(fingerprint="abc", document="livro")
    for _ in range(5):
        table.observe("W", "Q", page=3, raw="Wd5", san="Qd5")
    path = table.save(tmp_path / "cipher.json")
    assert not table.dirty
    again = BookCipher.load(path, fingerprint="abc")
    assert again is not None and again.proven() == {"W": "Q"}
    assert again.entries["W"].examples[0] == (3, "Wd5", "Qd5")
    assert BookCipher.load(path, fingerprint="other") is None
    assert BookCipher.load(tmp_path / "missing.json") is None


# --------------------------------------------------------------------------- #
# Applying the table
# --------------------------------------------------------------------------- #


def test_a_proven_table_rewrites_the_ciphered_moves_of_a_block_without_a_position():
    out = validate_region(_reading("23...Wd5 24.Hb1 &xd5 25.Sf1 Hxb7 26.Wc3 &d4"), DECISION,
                          lang="eng", book_cipher=TABLE)
    assert not out.attempted, "no position: the replay did not run"
    assert out.result.text == "23...Qd5 24.Rb1 Bxd5 25.Kf1 Rxb7 26.Qc3 Bd4"
    assert len(out.result.meta["book_cipher_applied"]) == 7
    assert any("cifra do livro" in r for r in out.reasons_pt)


def test_the_table_leaves_correct_notation_and_prose_alone():
    clean = "23...Qd5 24.Rb1 Bxd5 25.Kf1 Rxb7 26.Qc3 Bd4"
    assert validate_region(_reading(clean), DECISION, lang="eng",
                           book_cipher=TABLE).result.text == clean
    prose = "White stands better. However 23...Wd5 is weak"
    assert validate_region(_reading(prose), DECISION, lang="eng",
                           book_cipher=TABLE).result.text == prose, (
        "one symbol among prose is below the ciphered-majority floor")


def test_a_cluster_symbol_of_a_damaged_layer_is_a_symbol_too():
    out = validate_region(_reading("23...'it>d1 24.l:tb1 'i'xd5"), DECISION, lang="eng",
                          book_cipher={"'it>": "K", "l:t": "R", "'i'": "Q"})
    assert out.result.text == "23...Kd1 24.Rb1 Qxd5"


# --------------------------------------------------------------------------- #
# Proving symbols by replay
# --------------------------------------------------------------------------- #

#: The Opera game with ♗ → ``&``, ♕ → ``W``, ♖ → ``H``; the knights print ``N``.
OPERA = ("1.e4 e5 2.Nf3 d6 3.d4 &g4 4.dxe5 &xf3 5.Wxf3 dxe5 6.&c4 Nf6 7.Wb3 We7 8.Nc3 c6 "
         "9.&g5 b5 10.Nxb5 cxb5 11.&xb5+ Nbd7 12.O-O-O Hd8 13.Hxd7 Hxd7 14.Hd1 We6 "
         "15.&xd7+ Nxd7 16.Wb8+ Nxb8 17.Hd8#")


def test_a_complete_replay_proves_the_assignment_and_rewrites_the_block():
    out = validate_region(_reading(OPERA), DECISION, lang="eng")
    assert out.replayed_to_end and out.moves_replayed == 33
    assert out.cipher["symbols"] == {"&": "B", "W": "Q", "H": "R"}
    assert {(s, p) for s, p, _, _ in out.proven_pieces} == {("&", "B"), ("W", "Q"), ("H", "R")}
    assert out.result.text.startswith("1.e4 e5 2.Nf3 d6 3.d4 Bg4 4.dxe5 Bxf3 5.Qxf3")
    assert not out.unresolved


def test_a_block_that_replays_under_two_assignments_proves_nothing():
    # ``?`` on move 2: both Qf3 and Nf3 are legal; the page does not say.
    out = validate_region(_reading("1.e4 e5 2.Xf3 Xc6"), DECISION, lang="eng")
    assert out.proven_pieces == ()
    assert out.result.text == "1.e4 e5 2.Xf3 Xc6"


def test_the_repairer_resolves_a_piece_slot_only_when_one_piece_is_legal():
    report = repair_movetext("1.e4 e5 2.?f3 ?c6", start_fen=chess.STARTING_FEN)
    assert [u.raw for u in report.unresolved] == ["?f3"]
    assert set(report.unresolved[0].near_misses) == {"Qf3", "Nf3"}
    report = repair_movetext("1.e4 e5 2.Nf3 ?c6 3.?b5 a6 4.?a4", start_fen=chess.STARTING_FEN)
    assert [m.san for m in report.moves] == ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4"]
    assert report.replayed_to_end
