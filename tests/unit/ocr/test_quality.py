"""Quality estimation, and the lexicon it rests on.

Two different claims live here and they are held to different standards.

``character_error_rate`` is arithmetic: it has one right answer and the tests
assert it exactly.

``estimate_cer`` is an **estimate made without ground truth** — the only kind
available when a book is being read for the first time — and the honest test of
an estimator is not that it hits a number but that it *orders* correctly and
reports its own uncertainty.  So the tests below corrupt text at rates this
file chose and assert monotonicity and a bounded error, never a point value.
"""

from __future__ import annotations

import pytest

from caissa.ocr import lexicon as lex
from caissa.ocr.quality import (
    PageQuality,
    QualityThresholds,
    RegionQuality,
    Severity,
    assess_page,
    assess_result,
    character_error_rate,
    document_baseline,
    estimate_cer,
    levenshtein,
    measure_text,
    word_error_rate,
)
from .conftest import ENGLISH_BODY, PORTUGUESE_BODY, corrupt_text

from .test_arbiter import make_result


# --------------------------------------------------------------------------- #
# Exact arithmetic
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("a,b,expected", [
    ("", "", 0), ("a", "", 1), ("", "abc", 3),
    ("kitten", "sitting", 3), ("flaw", "lawn", 2),
    ("abc", "abc", 0), ("abcdef", "abcdff", 1),
])
def test_levenshtein(a, b, expected):
    assert levenshtein(a, b) == expected
    assert levenshtein(b, a) == expected, "a distância é simétrica"


def test_levenshtein_matches_a_naive_implementation():
    """The vectorised inner loop is a rewrite of the textbook recurrence; the
    rewrite is only safe if it agrees with it."""
    import random

    def naive(a, b):
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            row = [i]
            for j, cb in enumerate(b, 1):
                row.append(min(prev[j] + 1, row[j - 1] + 1,
                               prev[j - 1] + (ca != cb)))
            prev = row
        return prev[-1]

    rng = random.Random(4)
    alphabet = "abcde"
    for _ in range(60):
        a = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25)))
        b = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25)))
        assert levenshtein(a, b) == naive(a, b), (a, b)


def test_cer_is_zero_for_an_exact_match():
    assert character_error_rate(ENGLISH_BODY, ENGLISH_BODY) == 0.0


def test_cer_ignores_where_the_lines_broke():
    """A line break in a different place is a layout question, not a
    character-recognition one."""
    reference = "the rook belongs behind the passed pawn"
    hypothesis = "the rook belongs\nbehind the  passed\npawn"
    assert character_error_rate(hypothesis, reference) == 0.0
    assert character_error_rate(hypothesis, reference,
                                normalise_whitespace=False) > 0.0


def test_cer_of_one_substitution():
    assert character_error_rate("abcde", "abXde") == pytest.approx(1 / 5)


def test_cer_can_exceed_one_when_the_engine_invents():
    """Not clamped, deliberately: an engine that returns three times the text
    is worse than one that returns nothing, and a clamp hides that."""
    assert character_error_rate("abc" * 10, "abc") > 1.0


def test_cer_of_empty_inputs():
    assert character_error_rate("", "") == 0.0
    assert character_error_rate("abc", "") == 1.0
    assert character_error_rate("", "abc") == 1.0


def test_wer_counts_words():
    assert word_error_rate("the rook is here", "the rook is there") == \
        pytest.approx(1 / 4)


def test_cer_grows_with_the_damage_this_test_applied():
    reference = ENGLISH_BODY * 3
    previous = -1.0
    for rate in (0.0, 0.02, 0.05, 0.10, 0.20):
        cer = character_error_rate(corrupt_text(reference, rate, seed=1),
                                   reference)
        assert cer > previous, rate
        previous = cer


# --------------------------------------------------------------------------- #
# The lexicon
# --------------------------------------------------------------------------- #


def test_the_lexicon_reports_where_it_came_from():
    source = lex.lexicon_source()
    assert source["embedded_words"] > 500
    assert source["total_words"] >= source["embedded_words"]
    if source["external_words"]:
        assert source["external_dir"]


def test_the_embedded_core_works_on_its_own(monkeypatch):
    """A clean checkout, with no sibling project on disk, must still work."""
    monkeypatch.setattr(lex, "external_lexicon_dir", lambda: None)
    lex.reset_lexicon_cache()
    try:
        assert lex.lexicon_source()["external_words"] == 0
        rate, judged = lex.dictionary_hit_rate(ENGLISH_BODY, ("eng",))
        assert judged > 20
        assert rate > 0.35, (
            f"o núcleo embutido caiu para {rate:.2f}; ele é o piso do produto")
    finally:
        lex.reset_lexicon_cache()


def test_the_external_lists_raise_the_hit_rate_on_clean_prose():
    """Measured 2026-09-07 on the corpus: 0.48-0.67 with the embedded core
    alone, 0.88-0.97 with the trunk's lists."""
    if not lex.external_lexicon():
        pytest.skip("as listas do tronco não estão nesta máquina")
    big, _ = lex.dictionary_hit_rate(ENGLISH_BODY, ("eng",))

    original = lex.external_lexicon_dir
    lex.external_lexicon_dir = lambda: None  # type: ignore[assignment]
    lex.reset_lexicon_cache()
    try:
        small, _ = lex.dictionary_hit_rate(ENGLISH_BODY, ("eng",))
    finally:
        lex.external_lexicon_dir = original  # type: ignore[assignment]
        lex.reset_lexicon_cache()

    assert big > small, f"listas maiores não ajudaram: {small:.3f} -> {big:.3f}"


def test_garbage_scores_far_below_prose():
    """The gap this module exists to measure."""
    prose, _ = lex.dictionary_hit_rate(ENGLISH_BODY, ("eng",))
    cipher, _ = lex.dictionary_hit_rate(
        "vwx qzn plk mrt bdf hjg wqp zxv nmk lrt", ("eng",))
    assert prose > cipher + 0.30, (prose, cipher)


def test_chess_notation_is_not_counted_against_the_dictionary():
    """A page of pure move text must not read as garbage."""
    moves = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 1-0"
    rate, judged = lex.dictionary_hit_rate(moves, ("eng",))
    assert judged <= 2, f"{judged} lances foram julgados como palavras"


def test_is_chess_notation_is_stricter_than_the_notation_front():
    """A deliberate divergence from ``caissa.notation.looks_like_move``.

    ``looks_like_move`` is a *recall*-oriented pre-filter: it lets ``lLib8``
    and ``l0xd4`` through so that F6's parser gets a chance to validate them
    against the board.  Here the same permissiveness would be a bug — those two
    strings are precisely what a broken CMap produces from ``♖b8`` and
    ``♘xd4``, and excluding them from the dictionary denominator would blind
    the level-0 detector to the failure it exists to catch.

    So this is duplication on purpose, and the test is what stops someone
    "removing the duplicate" later.
    """
    notation = pytest.importorskip("caissa.notation")
    for token in ("lLib8", "l0xd4", "i.d4+"):
        assert notation.looks_like_move(token), token
        assert not lex.is_chess_notation(token), (
            f"{token!r} conta como notação e sai do denominador; a detecção "
            f"de CMap quebrada fica cega para ele")
    # ...while real notation is still excluded on both sides.
    for token in ("Nf3", "O-O", "Qxe4+", "e4"):
        assert lex.is_chess_notation(token), token


def test_modelled_script_share():
    assert lex.modelled_script_share("the rook belongs") == 1.0
    assert lex.modelled_script_share("Кр d3—сЗ Крe7") < 0.6
    assert lex.modelled_script_share("1. 2. 3.") == 0.0
    assert lex.modelled_script_share("") == 0.0


def test_the_ngram_model_is_not_retrained_by_the_external_lists():
    """The n-gram term has to be a signal that does not move when the word list
    does; training it on 350,000 surnames would destroy that."""
    before = lex.ngram_plausibility(ENGLISH_BODY)
    lex.reset_lexicon_cache()
    after = lex.ngram_plausibility(ENGLISH_BODY)
    assert before == after


def test_ngram_plausibility_separates_prose_from_noise():
    good, _ = lex.ngram_plausibility(ENGLISH_BODY)
    bad, _ = lex.ngram_plausibility("qxz vbn mkl pqr wxy zzq jjk vvn mmq")
    assert good > 0.80 > bad, (good, bad)


def test_normalise_lang_accepts_the_shapes_callers_use():
    assert lex.normalise_lang("por+eng") == ("por", "eng")
    assert lex.normalise_lang("pt-BR") == ("por",)
    assert lex.normalise_lang("") == ()
    assert lex.normalise_lang("klingon") == ()


# --------------------------------------------------------------------------- #
# Reference-free estimation
# --------------------------------------------------------------------------- #

DAMAGE_RATES = (0.0, 0.02, 0.05, 0.10, 0.20, 0.35)


@pytest.mark.parametrize("text,lang", [(ENGLISH_BODY, "eng"),
                                       (PORTUGUESE_BODY, "por")])
def test_the_estimate_rises_with_real_damage(text, lang):
    """The property that makes the estimator useful: it *orders* pages.

    Ordering is what the review queue needs.  A page whose estimate is 0.09
    when the truth is 0.06 is still the page to look at first, and that is the
    decision the number is actually used for.
    """
    reference = text * 4
    estimates = [estimate_cer(corrupt_text(reference, rate, seed=2), lang)[0]
                 for rate in DAMAGE_RATES]
    for earlier, later in zip(estimates, estimates[1:]):
        assert later >= earlier - 0.01, estimates
    assert estimates[-1] > estimates[0] + 0.05, estimates


@pytest.mark.parametrize("text,lang", [(ENGLISH_BODY, "eng"),
                                       (PORTUGUESE_BODY, "por")])
def test_the_estimate_is_within_a_stated_band_of_the_truth(text, lang):
    """The band is wide and is stated rather than hidden.

    ``NONWORD_DETECTION_RATE`` is a measured constant of the OCR confusion set,
    not of any engine, and it is the estimator's largest single source of
    error.  Asserting a tight band here would be asserting a precision the
    method does not have.
    """
    reference = text * 4
    for rate in (0.05, 0.10, 0.20):
        damaged = corrupt_text(reference, rate, seed=3)
        truth = character_error_rate(damaged, reference)
        estimate, confidence = estimate_cer(damaged, lang)
        assert abs(estimate - truth) < 0.15, (
            f"{lang} @ {rate}: verdadeiro {truth:.3f}, estimado "
            f"{estimate:.3f}, confiança {confidence:.2f}")
        assert 0.0 <= confidence <= 1.0


def test_clean_text_estimates_near_zero():
    for text, lang in ((ENGLISH_BODY * 4, "eng"), (PORTUGUESE_BODY * 4, "por")):
        estimate, _ = estimate_cer(text, lang)
        assert estimate < 0.06, (lang, estimate)


def test_a_short_string_reports_low_confidence():
    """Four tokens cannot support a quality judgement, and the estimator must
    say so instead of producing a number that looks like the others."""
    _, confidence = estimate_cer("the rook is", "eng")
    _, plenty = estimate_cer(ENGLISH_BODY * 4, "eng")
    assert confidence < plenty
    assert confidence < 0.5


def test_measure_text_reports_its_inputs():
    signals = measure_text(ENGLISH_BODY, "eng")
    as_dict = signals.as_dict()
    for key in ("dictionary_hit_rate", "nonword_ratio", "judged_tokens"):
        assert key in as_dict, sorted(as_dict)
    assert signals.char_count > 100


def test_document_baseline_needs_several_pages():
    """A clean level for one page is not a baseline, and pretending otherwise
    is how a whole book gets judged by its worst page."""
    signals = [measure_text(ENGLISH_BODY * 3, "eng") for _ in range(2)]
    assert document_baseline(signals) is None
    signals = [measure_text(ENGLISH_BODY * 3, "eng") for _ in range(6)]
    baseline = document_baseline(signals)
    assert baseline is not None and 0.0 < baseline <= 1.0


# --------------------------------------------------------------------------- #
# Severity and reporting
# --------------------------------------------------------------------------- #


def test_a_clean_result_is_not_flagged():
    result = make_result("tesseract", ENGLISH_BODY * 2, 0.97)
    quality = assess_result(result, lang="eng")
    assert isinstance(quality, RegionQuality)
    assert quality.severity is Severity.OK, quality.describe_pt()


def test_a_low_confidence_result_is_flagged():
    result = make_result("tesseract", ENGLISH_BODY * 2, 0.35)
    quality = assess_result(result, lang="eng")
    assert quality.severity is not Severity.OK
    assert quality.describe_pt()


def test_garbage_is_flagged_even_at_high_confidence():
    result = make_result("tesseract",
                         "xqz vbn mkl pqr wxy zzq jjk vvn mmq pplx " * 4, 0.99)
    quality = assess_result(result, lang="eng")
    assert quality.severity is not Severity.OK, quality.describe_pt()


def test_every_severity_has_a_portuguese_label():
    for severity in Severity:
        assert severity.label_pt


def test_page_quality_orders_the_worst_first():
    results = [make_result("tesseract", ENGLISH_BODY * 2, 0.97),
               make_result("tesseract", "xqz vbn mkl pqr wxy " * 8, 0.99),
               make_result("tesseract", ENGLISH_BODY * 2, 0.55)]
    page = assess_page(results, page_index=3, lang="eng")
    assert isinstance(page, PageQuality)
    worst = page.worst_regions
    assert worst, page.describe_pt()
    severities = [r.estimated_cer for r in worst]
    assert severities == sorted(severities, reverse=True)
    assert page.needs_attention


def test_a_clean_page_needs_no_attention():
    results = [make_result("tesseract", ENGLISH_BODY * 2, 0.97)
               for _ in range(3)]
    page = assess_page(results, page_index=1, lang="eng")
    assert not page.needs_attention, page.describe_pt()


def test_thresholds_are_injectable():
    """A build must be able to raise the bar without editing the module."""
    result = make_result("tesseract", ENGLISH_BODY * 2, 0.97)
    assert assess_result(result, lang="eng").severity is Severity.OK

    strict = QualityThresholds(min_mean_confidence=0.99)
    quality = assess_result(result, lang="eng", thresholds=strict)
    assert quality.severity is Severity.ATTENTION
    assert any("confiança média" in r for r in quality.reasons), quality.reasons


def test_an_empty_result_is_reported_not_scored_as_perfect():
    """Nothing read is the worst outcome, not the best."""
    result = make_result("tesseract", "", 0.0)
    quality = assess_result(result, lang="eng")
    assert quality.severity is not Severity.OK
    assert quality.describe_pt()
