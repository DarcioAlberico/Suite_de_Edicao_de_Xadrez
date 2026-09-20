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


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP_C2 passo B4: what counts as support; dashes; prefixes
# --------------------------------------------------------------------------- #


def _glyph_words(text: str, confidences, *, engine: str = "glyph", variant: str = "glyph",
                 margins=None) -> OcrResult:
    """Secondary readings laid out on the anchor's pitch, optionally with the
    glyph reader's ``margin`` on each word (the attribute the fusion reads
    with ``getattr``)."""
    from dataclasses import dataclass

    @dataclass(frozen=True, slots=True)
    class MarginWord(OcrWord):
        margin: float | None = None

    tokens = text.split()
    confs = list(confidences) if not isinstance(confidences, float) else [confidences] * len(tokens)
    margins = list(margins) if margins is not None else [None] * len(tokens)
    words = tuple(
        MarginWord(text=tok, box=BBox(60.0 * n, 0.0, 50.0, 20.0), confidence=confs[n],
                   word_index=n, margin=margins[n])
        for n, tok in enumerate(tokens))
    return OcrResult(engine=engine, lang="eng",
                     lines=(OcrLine(words=words, box=BBox.union_of([w.box for w in words])),),
                     meta={"variant": variant})


def test_a_rank_without_a_piece_is_not_support_for_the_anchor():
    """``8c4`` passes the multilingual shape and, counted as a move, made the
    anchor unreplaceable at any confidence (analysis §4.4).  With the page's
    language it is a look-alike; without one (the sabotage) it still counts."""
    from caissa.ocr.fusion import _supported

    assert not _supported("8c4", ("eng",))
    assert not _supported("2c7", ("eng",))
    assert not _supported("De2", ("eng",))
    assert _supported("De2", ("por",))
    assert _supported("R8c4", ("eng",))
    assert _supported("Nf3", ("por",)), "international SAN is printed in every language"
    assert _supported("8c4", ()), "sabotage: without a language the count is what it was"
    assert _supported("De2", ())


def test_a_dash_read_as_a_long_dash_keeps_the_move_and_the_fusion_leaves_it():
    """Dvoretsky p17 (analysis §4.4): Tesseract read the hyphen of ``b2-b4,``
    as ``b2—b4,``; not a move, so the fusion traded it for the glyph reader's
    truncated ``b4,`` and destroyed two correct moves."""
    from caissa.ocr.fusion import _supported

    for dash in "-–—‒−":
        assert _supported(f"b2{dash}b4,", ("eng",)), repr(dash)
    tess = result_of("21. b2—b4, Kc6", [0.9, 0.55, 0.9])
    glyph = _glyph_words("21 b4, Kc6", [1.0, 0.99, 0.99])
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None
    assert fused.result.text == "21. b2—b4, Kc6"
    assert fused.changed == 0


def test_the_figurine_cut_ignores_an_opening_bracket_and_a_lost_leading_digit():
    """``(17...2c7`` × ``(17...♗c7``: the ``(`` blocked the swap.  ``17...Ae5``
    × ``7...♘e5``: the glyph reader lost the ``1``; the anchor keeps it."""
    from caissa.ocr.fusion import _figurine_cut, _keep_number_prefix

    assert _figurine_cut("(17...2c7", "(17...♗c7") == 1
    assert _figurine_cut("(17...2c7", "17...♗c7") == 1
    assert _figurine_cut("17...Ae5", "7...♘e5") == 1
    assert _figurine_cut("17...Ae5", "27...♘e5") is None, "a different number is a different move"
    assert _keep_number_prefix("17...Ae5", "7...♘e5") == "17...♘e5"
    assert _keep_number_prefix("(17...2c7", "17...♗c7") == "(17...♗c7"
    assert _keep_number_prefix("(17...2c7", "(17...♗c7") == "(17...♗c7"
    tess = result_of("(17...2c7 18.Nd4", [0.6, 0.9])
    glyph = _glyph_words("(17...♗c7 18.♘d4", [0.98, 0.98])
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None
    assert fused.result.text.split()[0] == "(17...♗c7"
    tess = result_of("17...Ae5 18.Nd4", [0.6, 0.9])
    glyph = _glyph_words("7...♘e5 18.♘d4", [0.98, 0.98])
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None
    assert fused.result.text.split()[0] == "17...♘e5"


def test_two_independent_secondaries_outweigh_a_barely_read_anchor():
    """Anchor ``e5`` at 0,21 (a pawn move, so not a cipher) against ``♘e5``
    from the glyph reader *and* the figurine model: agreement between two
    engines, not two variants of one (the SOL-6 vote that was rejected)."""
    tess = result_of("17... e5 18.Nd4", [0.9, 0.21, 0.9])
    glyph = _glyph_words("17... ♘e5 18.♘d4", [1.0, 1.0, 0.98])
    figurine = _glyph_words("17... ♘e5 18.Nd4", [0.97, 0.97, 0.97],
                            engine="tesseract_figurine", variant="original")
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision()),
                             (figurine, 0.85, decision())], lang="eng",
                            never_anchor=frozenset({"glyph", "tesseract_figurine"}))
    assert fused is not None
    assert fused.result.text.split()[1] == "♘e5"
    assert fused.tokens[1].alternative == "e5"
    # The same two readings from one engine's two variants are not independent.
    glyph_b = _glyph_words("17... ♘e5 18.♘d4", [1.0, 1.0, 0.98], variant="glyph_b")
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision()),
                             (glyph_b, 0.85, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None
    assert fused.result.text.split()[1] == "e5"
    # And an anchor that read its token is not outweighed.
    confident = result_of("17... e5 18.Nd4", [0.9, 0.80, 0.9])
    fused = fuse_candidates([(confident, 0.8, decision()), (glyph, 0.9, decision()),
                             (figurine, 0.85, decision())], lang="eng",
                            never_anchor=frozenset({"glyph", "tesseract_figurine"}))
    assert fused is not None
    assert fused.result.text.split()[1] == "e5"


def test_a_glyph_reading_with_a_thin_margin_does_not_swap_the_look_alike():
    """``margin`` (WP5's ``GlyphWord``) is a second criterion: 0,80 of
    confidence with the runner-up at 0,75 is a coin toss."""
    tess = result_of("36... Hea! 2h6", [0.9, 0.6, 0.85])
    sure = _glyph_words("36 ♖e8! ♗h6", [1.0, 0.95, 0.95], margins=[1.0, 0.9, 0.9])
    fused = fuse_candidates([(tess, 0.8, decision()), (sure, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None and fused.result.text == "36... ♖e8! ♗h6"
    thin = _glyph_words("36 ♖e8! ♗h6", [1.0, 0.95, 0.95], margins=[1.0, 0.05, 0.9])
    fused = fuse_candidates([(tess, 0.8, decision()), (thin, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None and fused.result.text == "36... Hea! ♗h6"
    assert fused.tokens[1].readings[1].margin == 0.05
    without = _glyph_words("36 ♖e8! ♗h6", [1.0, 0.95, 0.95])
    fused = fuse_candidates([(tess, 0.8, decision()), (without, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None and fused.result.text == "36... ♖e8! ♗h6", "no margin: confidence alone"


def test_measure_evidence_counts_the_unsupported_moves_apart():
    from caissa.ocr.decision import DecisionPolicy, measure_evidence
    from caissa.ocr.lexicon import is_unsupported_move

    assert is_unsupported_move("8c4", ("eng",))
    assert not is_unsupported_move("8c4", ())
    assert not is_unsupported_move("Nf3", ("eng",))
    result = result_of("22. Nf3 8c4 23. De2 exd5", 0.9)
    evidence, _ = measure_evidence(result, None, DecisionPolicy(), langs=("eng",))
    assert evidence.mangled_moves == 2
    assert evidence.as_dict()["mangled_moves"] == 2
    evidence, _ = measure_evidence(result, None, DecisionPolicy(), langs=())
    assert evidence.mangled_moves == 0, "sabotage: without a language nothing is unsupported"


def test_a_supported_but_truncated_reading_does_not_replace_long_notation():
    """Secrets of Chess Training p872 (measured with the post-chain glyph
    reader of WP5): the anchor ``...h7—h5—h4.`` is not a move token (three
    squares), the glyph reader's ``h5–h4.`` is -- because it dropped a square.
    Shorter is not better; the anchor stays."""
    from caissa.ocr.fusion import _truncates_long_notation

    assert _truncates_long_notation("...h7—h5—h4.", "h5–h4.")
    assert _truncates_long_notation("b2—b4,", "b4,")
    assert not _truncates_long_notation("ofa", "of"), "prose is judged as before"
    assert not _truncates_long_notation("Hea!", "♖e8!")
    tess = result_of("as ...h7—h5—h4. Of", [0.9, 0.82, 0.9])
    glyph = _glyph_words("as h5–h4. Of", [0.99, 0.94, 0.99])
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}))
    assert fused is not None
    assert fused.result.text == "as ...h7—h5—h4. Of"


def test_the_passo_b4_switch_off_brings_the_old_string_matching_back():
    """The sabotage of passo B4 (``FusionConfig.passo_b4=False``): the same three
    cases the step fixed come out the old way -- a long dash makes ``b2—b4`` open
    to the truncated ``b4,``, an opening bracket blocks the figurine swap, and
    two agreeing secondaries never outrank a weak anchor.  This is what
    ``SOL_CONFIG='{"fusion": {"passo_b4": false}}'`` does in ``bench_sol``."""
    from caissa.ocr.fusion import FusionConfig

    off = FusionConfig(passo_b4=False)
    tess = result_of("21. b2—b4, Kc6", [0.9, 0.55, 0.9])
    glyph = _glyph_words("21 b4, Kc6", [1.0, 0.99, 0.99])
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}), config=off)
    assert fused is not None and fused.result.text != "21. b2—b4, Kc6"
    tess = result_of("(17...2c7 18.Nd4", [0.6, 0.9])
    glyph = _glyph_words("(17...♗c7 18.♘d4", [0.98, 0.98])
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision())], lang="eng",
                            never_anchor=frozenset({"glyph"}), config=off)
    assert fused is not None and fused.result.text.split()[0] == "(17...2c7"
    tess = result_of("17... e5 18.Nd4", [0.9, 0.21, 0.9])
    glyph = _glyph_words("17... ♘e5 18.♘d4", [1.0, 1.0, 0.98])
    figurine = _glyph_words("17... ♘e5 18.Nd4", [0.97, 0.97, 0.97],
                            engine="tesseract_figurine", variant="original")
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision()),
                             (figurine, 0.85, decision())], lang="eng",
                            never_anchor=frozenset({"glyph", "tesseract_figurine"}), config=off)
    assert fused is not None and fused.result.text.split()[1] == "e5"
    # And the switch is per call: the default config right after is unaffected.
    fused = fuse_candidates([(tess, 0.8, decision()), (glyph, 0.9, decision()),
                             (figurine, 0.85, decision())], lang="eng",
                            never_anchor=frozenset({"glyph", "tesseract_figurine"}))
    assert fused is not None and fused.result.text.split()[1] == "♘e5"
