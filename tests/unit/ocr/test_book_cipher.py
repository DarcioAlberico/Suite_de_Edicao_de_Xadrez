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
    assert again.entries["W"].examples[0] == (3, "Wd5", "Qd5", 0.0)
    assert BookCipher.load(path, fingerprint="other") is None
    assert BookCipher.load(tmp_path / "missing.json") is None


def test_a_version_one_file_loads_with_its_evidence(tmp_path: Path):
    """The tables the corpus already has (``models/tessdata/livros/*/cipher.json``,
    version 1) keep their rows: first piece with its sources, disputed pieces
    counted as visual evidence against it."""
    import json

    old = {"version": 1, "fingerprint": "abc", "document": "livro", "min_support": 5,
           "updated_at": "", "entries": {
               "W": {"piece": "Q", "support": 139, "contradictions": 1,
                     "examples": [[17, "Wc7!", "♕c7!"]], "disputed": {"K": 1},
                     "by_source": {"glyph": 139}},
               "8": {"piece": "K", "support": 1, "contradictions": 5,
                     "examples": [[5, "8a8", "♔a8"]], "disputed": {"R": 1, "Q": 3, "B": 1},
                     "by_source": {"glyph": 1}}}}
    path = tmp_path / "cipher.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    table = BookCipher.load(path, fingerprint="abc")
    assert table is not None
    assert table.entries["W"].support == 139 and table.entries["W"].disputed == {"K": 1}
    assert table.entries["W"].examples == [(17, "Wc7!", "♕c7!", 0.0)]
    assert table.proven() == {"W": "Q"}
    # The majority rule: ``8`` was fixed on K by its first swap; Q has 3 of 6.
    assert table.entries["8"].piece == "Q" and table.entries["8"].contradictions == 3
    assert "8" not in table.proven()
    assert table.as_dict()["version"] == 2


# --------------------------------------------------------------------------- #
# B10: majority, style and window
# --------------------------------------------------------------------------- #


def test_the_piece_of_a_row_is_the_majority_not_the_first_swap():
    """``'it`` → Q ×3 then K ×26 on the corpus: the first version could never
    prove K.  The row's piece follows the evidence."""
    table = BookCipher()
    for _ in range(3):
        table.observe("'it", "Q", source="glyph", page=1)
    assert table.entries["'it"].piece == "Q"
    for _ in range(26):
        table.observe("'it", "K", source="glyph", page=2)
    entry = table.entries["'it"]
    assert entry.piece == "K" and entry.support == 26 and entry.disputed == {"Q": 3}
    assert "'it" not in table.proven(window=0), "3 in 29 is above the 2 % share"
    for page in range(3, 9):
        for _ in range(5):
            table.observe("'it", "K", source="glyph", page=page)
    assert table.proven(window=0) == {}, "the whole row still carries 3 against 56"
    assert table.proven()["'it"] == "K", "six agreeing pages outlive the early mistake"
    assert "'it" not in table.proven(majority=False), "the version-1 rule judges the first swap (Q)"
    assert entry.first_piece == "Q"


def test_a_window_is_pages_not_tokens():
    """One page of swaps is one burst: it never proves by itself, however many."""
    table = BookCipher()
    table.observe("W", "K", source="glyph", page=1)
    for _ in range(40):
        table.observe("W", "Q", source="glyph", page=2)
    assert "W" not in table.proven(), "one recent page with 40 tokens is not a window"
    for _ in range(3):
        table.observe("W", "Q", source="glyph", page=3)
    assert "W" not in table.proven(), "pages 2 and 3 agree, but page 1 is inside a window of six"
    table.observe("W", "K", source="glyph", page=9)
    for page in range(10, 16):
        for _ in range(2):
            table.observe("W", "Q", source="glyph", page=page)
    assert table.proven()["W"] == "Q", "the last six pages (10–15) agree: the K of page 9 is outside"
    assert "W" not in table.proven(window=0)


def test_a_symbol_proves_per_style_when_the_faces_disagree():
    """A look-alike the main line uses for one figurine and the small-type
    variations for another: counted together it never proves; per style it does."""
    table = BookCipher()
    for _ in range(12):
        table.observe("&", "B", source="glyph", style="r", page=1)
    for _ in range(12):
        table.observe("&", "K", source="glyph", style="s", page=1)
    assert "&" not in table.proven(style=None), "12 against 12 is no majority"
    assert table.proven(style="r")["&"] == "B"
    assert table.proven(style="s")["&"] == "K"
    assert "&" not in table.proven(style="l"), "a style with no evidence falls back to the row"
    assert "&" not in table.proven(style=""), "and the style-less row is contradicted"


def test_size_class_and_body_size():
    from caissa.ocr.notation.book_cipher import body_size_of, size_class

    assert body_size_of([10.0, 12.0, 11.0, 0.0]) == 11.0
    assert body_size_of([]) == 0.0
    assert size_class(11.0, 11.0) == "r"
    assert size_class(8.0, 11.0) == "s"
    assert size_class(16.0, 11.0) == "l"
    assert size_class(8.0, 0.0) == "" and size_class(0.0, 11.0) == ""


def test_examples_keep_the_confidence_of_the_swap():
    table = BookCipher()
    table.observe("H", "R", source="glyph", raw="Hea!", san="♖e8!", confidence=0.93, page=4)
    assert table.entries["H"].examples == [(4, "Hea!", "♖e8!", 0.93)]


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
