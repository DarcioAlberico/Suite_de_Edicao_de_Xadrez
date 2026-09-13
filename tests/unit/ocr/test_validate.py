"""Sol §SOL-8: chess validation hooked to the document.

The cases are the ones §7 of Sol lists under "Xadrez": known and unknown
start position, ambiguous side to move, two legal repairs, a visually strong
but illegal candidate, homoglyphs, an inserted or missing separator, a
variation, and an invented sequence with no support in the image.
"""

from __future__ import annotations

import chess

from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.notation.validate import _repeated_moves, validate_region
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

from .test_arbiter import inked_region


def result_of(text: str, confidence: float = 0.7, engine: str = "tesseract") -> OcrResult:
    words = []
    x = 2.0
    for i, token in enumerate(text.split()):
        width = 9.0 * len(token)
        words.append(OcrWord(text=token, box=BBox(x, 2.0, width, 16.0), confidence=confidence,
                             word_index=i))
        x += width + 8.0
    return OcrResult(engine=engine, lang="eng",
                     lines=(OcrLine(words=tuple(words), box=BBox(2.0, 2.0, x, 16.0)),),
                     region_kind=RegionKind.MOVETEXT)


def demoted(score: float = 0.85) -> RegionDecision:
    return RegionDecision(Decision.REVIEW, score, 0.78, 0.5,
                          ("Lances com confiança média 0.70 e sem replay legal.",), demoted=True)


SPANISH = "1.e4 c5 2.Cf3 d6 3.d4 cxd4 4.Cxd4 Cf6 5.Cc3 a6 6.Ag5 e6 7.f4 Ae7 8.Df3 Dc7"


def test_a_clean_block_from_move_one_replays_and_is_accepted():
    out = validate_region(result_of(SPANISH), demoted(), lang="spa",
                          image=inked_region(40, 1400))
    assert out.attempted and out.replayed_to_end
    assert out.language == "es"
    assert out.decision.decision is Decision.ACCEPTED
    assert out.corrected == ()
    assert out.result.text == SPANISH


def test_a_unique_legal_repair_is_applied_and_traced():
    damaged = "1.e4 c5 2.Cf3 dó 3.d4 cxdá 4.Cxd4 Cf6 5.Cc3 a6 6.Ag5 e6"
    out = validate_region(result_of(damaged), demoted(), lang="spa",
                          image=inked_region(40, 1400))
    assert out.replayed_to_end
    assert dict(out.corrected) == {"dó": "d6", "cxdá": "cxd4"}
    assert "d6 3.d4 cxd4" in out.result.text
    assert out.result.meta["legality_corrections"] == {"dó": "d6", "cxdá": "cxd4"}
    assert any("aplicadas" in r for r in out.reasons_pt)


def test_an_unknown_start_position_means_no_replay_and_no_guess():
    out = validate_region(result_of("41.Tb7 Ta2 42.Kfz Ta3+ 43.Ke4"), demoted(), lang="deu")
    assert not out.attempted
    assert out.decision.decision is Decision.REVIEW
    assert any("desconhecida" in r for r in out.reasons_pt)
    assert out.result.text == "41.Tb7 Ta2 42.Kfz Ta3+ 43.Ke4"


def test_a_diagram_without_trusted_provenance_does_not_start_a_replay():
    out = validate_region(result_of("12.Nf3 Nc6"), demoted(), lang="eng",
                          start_fen=chess.STARTING_FEN, fen_trusted=False)
    assert not out.attempted
    assert any("proveniência" in r for r in out.reasons_pt)


def test_side_to_move_is_never_defaulted():
    # A trusted diagram, a block that does not start with a move number,
    # and no caption: nothing says who moves, so nothing is replayed.
    out = validate_region(result_of("Nf3 Nc6 Bb5"), demoted(), lang="eng",
                          start_fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
                          fen_trusted=True)
    assert not out.attempted
    assert any("lado a jogar" in r for r in out.reasons_pt)
    # The numbering says Black; the FEN said White: the page's numbering
    # wins and the disagreement is written down.
    out = validate_region(result_of("2...Nc6 3.Bb5 a6"), demoted(), lang="eng",
                          start_fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 2",
                          fen_trusted=True)
    assert out.attempted and out.side_to_move == "b"
    assert out.replayed_to_end
    assert any("numeração prevalece" in r for r in out.reasons_pt)


def test_two_possible_repairs_go_to_review_with_alternatives():
    # After 1.e4 e5 2.Nf3 the token "N?6" could be Nc6 or Nf6: not unique.
    out = validate_region(result_of("1.e4 e5 2.Nf3 Nz6 3.Bb5 a6"), demoted(), lang="eng")
    assert out.attempted
    assert out.decision.decision is Decision.REVIEW
    assert out.unresolved and out.unresolved[0][0] == "Nz6"
    assert set(out.unresolved[0][1]) >= {"Nc6", "Nf6"}
    assert "Nz6" in out.result.text          # the reading is kept, not deleted


def test_a_visually_strong_but_illegal_candidate_is_not_accepted():
    """``Bxe4`` at 0.97 is illegal; ``Nxe4`` is legal and one letter away.
    Legality may *suggest* it, but B→N is no confusion an engine makes on a
    confident glyph, so the block is not rewritten: review, with the
    alternative attached."""
    out = validate_region(result_of("1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Bxe4",
                                    confidence=0.97), demoted(0.9), lang="eng")
    assert out.attempted
    assert out.decision.decision is Decision.REVIEW
    assert "Bxe4" in out.result.text
    assert ("Bxe4", ("Nxe4",)) in out.unresolved
    assert any("sem apoio visual" in r for r in out.reasons_pt)
    # The same token at low confidence is a doubt the replay may settle.
    doubtful = validate_region(result_of("1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Bxe4",
                                         confidence=0.55), demoted(0.85), lang="eng")
    assert dict(doubtful.corrected) == {"Bxe4": "Nxe4"}


def test_homoglyphs_are_folded_before_the_replay():
    out = validate_region(result_of("1.e4 e5 2.Кf3 Кc6 3.Сb5 a6"), demoted(), lang="rus")
    assert out.attempted and out.replayed_to_end
    assert out.moves_replayed == 6


def test_inserted_and_missing_separators_get_candidates():
    glued = validate_region(result_of("1.e4 e5 2.Nf3Nc6 3.Bb5 a6"), demoted(), lang="eng")
    assert glued.replayed_to_end
    assert "Nf3 Nc6" in glued.result.text
    # A split piece letter: ``2.N f3`` reads legally *both* ways (2.f3 is a
    # pawn move), so the original stands — legality cannot tell, and the
    # validator does not guess.  With a following move only the knight
    # reading survives, and the join is adopted.
    split = validate_region(result_of("1.e4 e5 2.N f3 Nc6 3.Bb5 a6"), demoted(), lang="eng")
    assert split.replayed_to_end
    forced = validate_region(result_of("1.e4 e5 2.N f3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Nxe4"),
                             demoted(), lang="eng")
    assert forced.replayed_to_end
    assert "Nf3 Nc6" in forced.result.text


def test_variations_are_replayed_from_the_position_before_their_parent():
    text = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 (5...Nxe4 6.d4 b5) 6.Re1 b5"
    out = validate_region(result_of(text), demoted(), lang="eng")
    assert out.replayed_to_end
    assert out.variations == 1 and out.variations_ok == 1


def test_an_invented_repetition_that_does_not_replay_is_blocked():
    assert _repeated_moves("1 . e4 e5 2 . Nf3 Nc6 8 . c3 O-O 8 . c3 O-O".split()) == ("c3 O-O",)
    text = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 3.Bb5 a6 3.Bb5 a6 4.Ba4 Nf6"
    out = validate_region(result_of(text, confidence=0.97), demoted(0.95), lang="eng")
    assert not out.replayed_to_end
    assert out.repeated
    assert out.decision.decision is Decision.REVIEW
    assert any("repetida" in r for r in out.reasons_pt)


def test_the_repair_keeps_the_books_own_piece_letters():
    out = validate_region(result_of("1.e4 c5 2.Cf3 dó 3.d4 cxd4"), demoted(), lang="por")
    assert out.replayed_to_end
    assert out.result.text == "1.e4 c5 2.Cf3 d6 3.d4 cxd4"   # C stays C, not N
