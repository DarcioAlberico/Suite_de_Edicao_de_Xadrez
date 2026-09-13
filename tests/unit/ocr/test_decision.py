"""Sol §SOL-2: accept, review or abstain — and the negative controls.

The first half drives :func:`caissa.ocr.decision.decide` with hand-built
results, so each rule is pinned on its own.  The second half runs the real
cascade over the negative controls (blank page, empty board, stains, border,
noise, photo) and asserts that nothing textual comes out *accepted*: a
white page on which Tesseract reads ``rs`` was the founding bug.
"""

from __future__ import annotations

import numpy as np
import pytest

from caissa.ocr.controls import control_image
from caissa.ocr.decision import Decision, DecisionPolicy, decide, measure_evidence
from caissa.ocr.golden import ControlKind
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

from .conftest import requires_tesseract

PROSE = ("The rook belongs behind the passed pawn and the defender simply "
         "waits while the attacking side loses time with every step")


def result_of(text: str, confidence: float = 0.95, *, y: float = 5.0,
              height: float = 20.0, engine: str = "mock") -> OcrResult:
    words = []
    x = 10.0
    for index, token in enumerate(text.split()):
        width = 9.0 * len(token)
        words.append(OcrWord(text=token, box=BBox(x, y, width, height),
                             confidence=confidence, word_index=index))
        x += width + 8.0
    line = OcrLine(words=tuple(words), box=BBox(10.0, y, x, height))
    return OcrResult(engine=engine, lang="eng", lines=(line,) if words else ())


def inked(width: int = 1200, height: int = 40) -> np.ndarray:
    image = np.full((height, width), 250, dtype=np.uint8)
    image[6:24, ::3] = 0
    return image


def blank(width: int = 1200, height: int = 40) -> np.ndarray:
    return np.full((height, width), 250, dtype=np.uint8)


# --------------------------------------------------------------------------- #
# The rules, one at a time
# --------------------------------------------------------------------------- #


def test_a_clean_confident_region_over_ink_is_accepted():
    d = decide(result_of(PROSE), 0.90, image=inked(), langs=("eng",))
    assert d.decision is Decision.ACCEPTED
    assert not d.reasons_pt
    assert d.evidence is not None
    assert d.evidence.ink_measured
    assert d.evidence.unsupported_share == 0.0


def test_empty_text_abstains():
    d = decide(result_of(""), 0.99, image=inked())
    assert d.decision is Decision.ABSTAINED
    assert "Nenhum texto" in d.reasons_pt[0]


def test_two_characters_of_noise_abstain_whatever_the_score():
    d = decide(result_of("rs", 0.99), 0.99, image=inked())
    assert d.decision is Decision.ABSTAINED
    assert "ruído" in d.reasons_pt[0]


def test_a_short_result_needs_a_word_or_a_move():
    assert decide(result_of("xq zzk", 0.9), 0.9, image=inked(),
                  langs=("eng",)).decision is Decision.ABSTAINED
    assert decide(result_of("Chapter", 0.9), 0.9, image=inked(),
                  langs=("eng",)).decision is Decision.ACCEPTED
    assert decide(result_of("1.e4 e5", 0.9), 0.9, image=inked(),
                  langs=("eng",)).decision is not Decision.ABSTAINED


def test_words_over_blank_paper_are_hallucinations():
    d = decide(result_of(PROSE, 0.97), 0.95, image=blank(), langs=("eng",))
    assert d.decision is Decision.ABSTAINED
    assert "sem tinta" in " ".join(d.reasons_pt)
    assert len(d.flagged_words) == len(PROSE.split())


def test_a_trusted_source_is_exempt_from_the_noise_floors_but_not_the_bars():
    folio = result_of("41", 1.0, engine="pdf_text_layer")
    assert decide(folio, 0.95, image=None, trusted_source=True).decision is Decision.ACCEPTED
    assert decide(folio, 0.30, image=None, trusted_source=True).decision is Decision.ABSTAINED


def test_below_the_bar_is_review_and_below_the_floor_is_abstention():
    policy = DecisionPolicy(accept_score=0.78, review_score=0.50)
    assert decide(result_of(PROSE), 0.65, policy=policy, image=inked(),
                  langs=("eng",)).decision is Decision.REVIEW
    assert decide(result_of(PROSE), 0.40, policy=policy, image=inked(),
                  langs=("eng",)).decision is Decision.ABSTAINED
    d = decide(result_of(PROSE), 0.65, policy=policy, image=inked(), langs=("eng",))
    assert d.below_threshold
    assert "abaixo do limite" in d.reasons_pt[0]


def test_many_low_confidence_words_demote_an_accepted_score_to_review():
    words = list(result_of(PROSE, 0.95).words)
    low = tuple(OcrWord(text=w.text, box=w.box, confidence=0.3 if i % 2 else 0.95,
                        word_index=w.word_index) for i, w in enumerate(words))
    result = OcrResult(engine="mock", lang="eng",
                       lines=(OcrLine(words=low, box=BBox.union_of([w.box for w in low])),))
    d = decide(result, 0.90, image=inked(), langs=("eng",))
    assert d.decision is Decision.REVIEW
    assert d.demoted
    assert "baixa confiança" in " ".join(d.reasons_pt)


def test_move_shaped_tokens_are_not_accepted_on_shape_alone():
    moves = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5"
    doubtful = decide(result_of(moves, 0.70), 0.85, image=inked(),
                      region_kind=RegionKind.MOVETEXT)
    assert doubtful.decision is Decision.REVIEW
    assert "forma de lance" in " ".join(doubtful.reasons_pt)
    confident = decide(result_of(moves, 0.95), 0.85, image=inked(),
                       region_kind=RegionKind.MOVETEXT)
    assert confident.decision is Decision.ACCEPTED
    replayed = decide(result_of(moves, 0.70), 0.85, image=inked(),
                      region_kind=RegionKind.MOVETEXT,
                      legality={"replayed_to_end": True, "unresolved": 0})
    assert replayed.decision is Decision.ACCEPTED


def test_geometry_outliers_are_flagged_and_a_majority_abstains():
    words = list(result_of(PROSE, 0.95).words)
    heights = (20.0, 200.0, 2.0)       # one in three is a line; the rest are not
    tall = tuple(OcrWord(text=w.text, box=BBox(w.box.x, 0.0, w.box.w, heights[i % 3]),
                         confidence=0.95, word_index=w.word_index)
                 for i, w in enumerate(words))
    result = OcrResult(engine="mock", lang="eng",
                       lines=(OcrLine(words=tall, box=BBox(0, 0, 1200, 200)),))
    d = decide(result, 0.90, image=None, langs=("eng",))
    assert d.decision is Decision.ABSTAINED
    assert "altura" in " ".join(d.reasons_pt)


def test_evidence_is_measured_once_and_explained():
    evidence, flagged = measure_evidence(result_of(PROSE), inked(), DecisionPolicy(),
                                         langs=("eng",))
    assert evidence.words == len(PROSE.split())
    assert evidence.chars > 100
    assert evidence.dictionary_words > 10
    assert evidence.move_tokens == 0
    assert not flagged
    d = decide(result_of(PROSE), 0.9, image=inked(), langs=("eng",))
    assert "Região aceita" in d.describe_pt()
    assert d.as_dict()["decision"] == "accepted"


# --------------------------------------------------------------------------- #
# Negative controls through the real cascade
# --------------------------------------------------------------------------- #


def test_every_control_kind_renders_deterministically():
    for kind in ControlKind:
        a = control_image(kind, height=300, width=240, seed=3)
        b = control_image(kind, height=300, width=240, seed=3)
        assert a.shape == (300, 240)
        assert a.dtype == np.uint8
        assert np.array_equal(a, b)


@requires_tesseract
@pytest.mark.parametrize("kind", list(ControlKind))
def test_negative_controls_never_produce_accepted_text(kind):
    """Sol §SOL-2, acceptance criterion: a white image produces nothing."""
    from caissa.ocr.engines.registry import default_registry
    from caissa.ocr.page import PageRecognizer, PageTask

    engines = default_registry().available(lang="eng")
    outcome = PageRecognizer(engines).run(
        PageTask(image=control_image(kind, height=1100, width=850, seed=1),
                 dpi=100.0, lang="eng"))
    for region in outcome.regions:
        decision = region.decision
        assert decision is not None
        assert decision.decision is not Decision.ACCEPTED, (
            f"{kind}: '{region.result.text[:60]}' foi aceito — "
            + decision.describe_pt())
    assert outcome.text.strip() == "" or outcome.decision_counts["accepted"] == 0
