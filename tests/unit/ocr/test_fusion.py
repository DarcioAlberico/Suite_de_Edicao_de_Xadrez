"""Sol §SOL-6: token fusion is conservative and explains itself."""

from __future__ import annotations

import pytest

from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.fusion import FusionConfig, fuse_candidates
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord


def result_of(text: str, confidences, *, engine: str = "tesseract", variant: str = "original",
              y: float = 0.0, x: float = 0.0, lines: int = 1) -> OcrResult:
    """Words laid out at fixed 60 px pitch so geometry aligns across candidates."""
    tokens = text.split()
    confs = list(confidences) if not isinstance(confidences, float) else [confidences] * len(tokens)
    per_line = max(1, -(-len(tokens) // lines))
    ocr_lines = []
    for li in range(lines):
        chunk = list(enumerate(tokens))[li * per_line:(li + 1) * per_line]
        words = tuple(
            OcrWord(text=tok, box=BBox(x + 60.0 * (n - li * per_line), y + 30.0 * li, 50.0, 20.0),
                    confidence=confs[n], word_index=n)
            for n, tok in chunk)
        if words:
            ocr_lines.append(OcrLine(words=words, box=BBox.union_of([w.box for w in words])))
    return OcrResult(engine=engine, lang="eng", lines=tuple(ocr_lines),
                     meta={"variant": variant})


def decision(kind: Decision = Decision.ACCEPTED, score: float = 0.9) -> RegionDecision:
    return RegionDecision(kind, score, 0.78, 0.5, ())


def test_agreeing_candidates_fuse_to_the_anchor_with_lifted_confidence():
    a = result_of("the rook belongs behind", 0.9)
    b = result_of("the rook belongs behind", 0.8, variant="deskew_shadow")
    fused = fuse_candidates([(a, 0.9, decision()), (b, 0.85, decision())], lang="eng")
    assert fused is not None
    assert fused.result.text == "the rook belongs behind"
    assert fused.changed == 0 and fused.disputed == 0
    assert all(t.agreement == 1.0 for t in fused.tokens)
    assert fused.result.words[0].confidence == pytest.approx(0.95)
    assert fused.result.meta["fused"] is True


def test_a_confident_lexical_reading_replaces_a_doubtful_anchor_token():
    a = result_of("the r0ok belongs behind", [0.9, 0.35, 0.9, 0.9])
    b = result_of("the rook belongs behind", [0.9, 0.92, 0.9, 0.9], variant="upscale")
    fused = fuse_candidates([(a, 0.85, decision()), (b, 0.80, decision())], lang="eng")
    assert fused is not None
    assert fused.result.text == "the rook belongs behind"
    assert fused.changed == 1
    token = fused.tokens[1]
    assert token.chosen_from == "upscale/tesseract"
    assert token.alternative == "r0ok"
    assert [r.text for r in token.readings] == ["r0ok", "rook"]


def test_no_token_is_ever_inserted_from_another_candidate():
    a = result_of("the rook belongs", 0.9)
    b = result_of("the rook belongs behind the pawn", 0.95, variant="bleed_sauvola")
    fused = fuse_candidates([(a, 0.9, decision()), (b, 0.9, decision())], lang="eng")
    assert fused is not None
    assert fused.result.text == "the rook belongs"
    assert len(fused.tokens) == 3


def test_a_trusted_text_layer_anchor_is_never_overridden():
    layer = result_of("the rook belongs", [0.99, 0.99, 0.99], engine="pdf_text_layer")
    ocr = result_of("the rook belongz", 0.99, variant="original")
    fused = fuse_candidates([(layer, 0.95, decision()), (ocr, 0.9, decision())], lang="eng")
    assert fused is not None
    assert fused.result.text == "the rook belongs"
    assert fused.changed == 0


def test_a_known_anchor_token_is_never_replaced_only_disputed():
    """``rook`` is a word: a clearly more confident ``rock`` (also a word) is a
    dispute for the reviewer; an equally confident one is nothing at all."""
    a = result_of("the rook belongs behind", [0.9, 0.62, 0.9, 0.9])
    b = result_of("the rock belongs behind", [0.9, 0.95, 0.9, 0.9], variant="deskew_shadow")
    fused = fuse_candidates([(a, 0.85, decision()), (b, 0.85, decision())], lang="eng")
    assert fused is not None
    token = fused.tokens[1]
    assert token.text == "rook" and token.disputed
    assert token.alternative == "rock"
    assert fused.disputed == 1 and fused.changed == 0
    same = result_of("the rock belongs behind", [0.9, 0.62, 0.9, 0.9], variant="deskew_shadow")
    quiet = fuse_candidates([(a, 0.85, decision()), (same, 0.85, decision())], lang="eng")
    assert quiet is not None and quiet.disputed == 0 and quiet.tokens[1].text == "rook"


def test_many_disputes_send_the_region_to_review():
    # Anchor tokens are nonwords the engine doubted; the alternatives are
    # words but not clearly better: every slot is a dispute.
    a = result_of("tbe r0ok belongz behlnd", [0.62] * 4)
    b = result_of("the rook belongs behind", [0.62] * 4, variant="upscale")
    fused = fuse_candidates([(a, 0.85, decision()), (b, 0.85, decision())], lang="eng",
                            config=FusionConfig(dispute_margin=0.9))
    assert fused is not None
    assert fused.decision.decision is Decision.REVIEW
    assert "disputa" in " ".join(fused.decision.reasons_pt)


def test_lines_of_different_columns_never_pair():
    left = result_of("torre peão rei", 0.6)
    right = result_of("rook pawn king", 0.99, x=800.0, variant="upscale")
    fused = fuse_candidates([(left, 0.8, decision()), (right, 0.8, decision())], lang="por")
    assert fused is not None
    assert fused.result.text == "torre peão rei"
    assert all(len(t.readings) == 1 for t in fused.tokens)


def test_diacritics_and_line_end_hyphens_are_preferred():
    a = result_of("posicao exige preci-", [0.85, 0.9, 0.85])
    b = result_of("posição exige preci", [0.85, 0.9, 0.85], variant="deskew_shadow")
    fused = fuse_candidates([(a, 0.85, decision()), (b, 0.85, decision())], lang="por")
    assert fused is not None
    assert fused.tokens[0].text == "posição"
    assert fused.tokens[2].text == "preci-"


def test_one_candidate_or_empty_ones_fuse_to_nothing():
    a = result_of("the rook", 0.9)
    assert fuse_candidates([(a, 0.9, decision())]) is None
    empty = OcrResult(engine="t", lang="eng")
    assert fuse_candidates([(a, 0.9, decision()), (empty, 0.1, decision(Decision.ABSTAINED))]) is None


def test_a_bare_move_number_is_not_replaced_by_a_move():
    """``38`` is the printed form of a move number.  A candidate misaligned by
    one slot offers ``g5`` for it with lexical support; before 2026-09-14 the
    fusion took it, and every such swap was an invented move."""
    from caissa.ocr.fusion import _supported

    assert _supported("38", ("eng",))
    assert _supported("36...", ("eng",))
    assert _supported("12.", ("eng",))
    assert not _supported("@c2", ("eng",))


def test_an_abstained_anchor_comes_out_of_the_fusion_as_review_at_most():
    """SOL-2: the alternatives' agreement may propose a reading for a region
    the arbiter abstained on, never certify it (41 such regions were ACCEPTED
    at CER 0,24 on 2026-09-14 before this rule)."""
    from caissa.ocr.decision import Decision, RegionDecision
    from caissa.ocr.fusion import fuse_candidates
    from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

    def reading(engine, text, conf):
        words = tuple(OcrWord(text=t, box=BBox(10.0 + 60 * i, 8.0, 50.0, 18.0), confidence=conf,
                              word_index=i) for i, t in enumerate(text.split()))
        line = OcrLine(words=words, box=BBox(10.0, 8.0, 60.0 * len(words), 18.0), baseline=None,
                       block_index=0, paragraph_index=0, line_index=0, kind=RegionKind.MOVETEXT)
        return OcrResult(engine=engine, lang="eng", lines=(line,), region_kind=RegionKind.MOVETEXT)

    abstained = RegionDecision(Decision.ABSTAINED, 0.47, 0.78, 0.55, ("baixo",))
    accepted = RegionDecision(Decision.ACCEPTED, 0.95, 0.78, 0.55, ())
    fused = fuse_candidates([
        (reading("tesseract", "G\e4 Kf3", 0.5), 0.47, abstained),
        (reading("mock_b", "Nxe4 Kf3", 0.99), 0.95, accepted),
        (reading("mock_c", "Nxe4 Kf3", 0.99), 0.95, accepted),
    ], lang="eng", never_anchor=frozenset({"mock_b", "mock_c"}))
    assert fused is not None
    assert fused.decision.decision is not Decision.ACCEPTED
