"""OCR quality measurement, with and without ground truth.

Two different jobs, kept apart on purpose:

* :func:`character_error_rate` measures CER against a known reference.  It is
  exact, and it is what the acceptance gate in SPEC §11.3 is written in.  It
  needs ground truth, so it can only be used on the golden corpus.
* :func:`estimate_cer` *estimates* CER with no reference at all, so that the UI
  can tell a user which of 500 imported pages to look at.  It is not exact and
  it does not pretend to be; :class:`RegionQuality` reports it alongside the
  signals it was derived from, so a suspicious number can always be traced.

The estimator's core is one inversion.  A word survives OCR only if every one
of its characters survives, so with a character error rate ``c`` and a mean word
length ``L`` the fraction of *damaged* words is ``1 - (1 - c)**L``.  Counting
damaged words therefore gives ``c`` directly::

    c = 1 - (1 - damaged) ** (1 / L)

The whole problem is counting damaged words without a reference.  The obvious
route — the dictionary hit rate — turns out to be the wrong primary signal, and
the measurement that shows why is worth stating: clean chess prose scores 0.79
in English, 0.60 in German and 0.50 in Portuguese against the embedded lexicon.
There is no absolute threshold across a spread that wide, so the dictionary can
only speak when :func:`document_baseline` has established what *this book*
scores when clean.

What works instead is a test whose clean value is zero in every language:
:func:`~caissa.ocr.lexicon.is_implausible_token` — a digit inside a word, a
four-letter run with no vowel, two scripts in one token.  Clean English,
Portuguese and German prose all score exactly 0.000, and the score rises
monotonically with corruption in all of them.  It sees only about half the
damage, since half of OCR substitutions replace a letter with another letter
and leave a pronounceable token behind, so the count is divided by that measured
share.

Accuracy, measured against synthetic corruption of prose in three languages
(the table is in docs/quality/F5_REPORT.md): the estimate is exactly zero on
clean text and lands within a factor of 0.6 to 1.3 of true CER through the
0.2 %–5 % band that the F5 gate is written in, drifting to about 1.4x high by
15 %.  It is a triage instrument for pointing a proofreader at the worst pages,
never a substitute for :func:`character_error_rate` on the golden corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable, Mapping, Sequence

import numpy as np

from .lexicon import (
    dictionary_hit_rate,
    implausible_char_ratio,
    is_chess_notation,
    ngram_plausibility,
    nonword_ratio,
    normalise_lang,
    tokenize,
)
from .types import OcrResult, RegionKind

__all__ = [
    "Severity",
    "QualitySignals",
    "RegionQuality",
    "PageQuality",
    "QualityThresholds",
    "character_error_rate",
    "word_error_rate",
    "levenshtein",
    "estimate_cer",
    "document_baseline",
    "measure_text",
    "assess_result",
    "assess_page",
    "text_plausibility",
]


# --------------------------------------------------------------------------- #
# Exact metrics (need ground truth)
# --------------------------------------------------------------------------- #


def levenshtein(a: Sequence[object], b: Sequence[object]) -> int:
    """Edit distance, vectorised one row at a time.

    The insertion term ``c[j] = min(c[j], c[j-1] + 1)`` looks sequential, but it
    is a running minimum in disguise: ``c[j] = j + min_{k<=j}(p[k] - k)``.
    Rewriting it that way turns the inner loop into
    ``np.minimum.accumulate`` and makes a full page comparison take
    milliseconds rather than seconds — which matters because the arbiter
    compares engine outputs on every region of every page.
    """
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)

    b_arr = np.array(list(b), dtype=object)
    prev = np.arange(len(b) + 1, dtype=np.int64)
    ramp = np.arange(len(b) + 1, dtype=np.int64)
    row = np.empty(len(b) + 1, dtype=np.int64)

    for i, ch in enumerate(a, start=1):
        row[0] = i
        substitution = prev[:-1] + (b_arr != ch)
        deletion = prev[1:] + 1
        np.minimum(substitution, deletion, out=row[1:])
        prev = ramp + np.minimum.accumulate(row - ramp)
    return int(prev[-1])


def character_error_rate(hypothesis: str, reference: str, *,
                         normalise_whitespace: bool = True) -> float:
    """CER = edit distance / length of the reference.

    Whitespace is collapsed by default.  A line break that OCR put in a
    different place is a layout question, not a character-recognition question,
    and letting it count as errors makes the number measure the wrong thing.
    """
    if normalise_whitespace:
        hypothesis = " ".join(hypothesis.split())
        reference = " ".join(reference.split())
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein(hypothesis, reference) / len(reference)


def word_error_rate(hypothesis: str, reference: str) -> float:
    """WER = word-level edit distance / reference word count."""
    hyp = hypothesis.split()
    ref = reference.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(hyp, ref) / len(ref)


# --------------------------------------------------------------------------- #
# Reference-free estimation
# --------------------------------------------------------------------------- #

#: Dictionary hit rate a *clean* page of prose reaches with this lexicon.
#: Only used as a weak corroborator, because the clean level is a property of
#: the *text* and not of its quality: measured here, clean chess prose scores
#: 0.79 in English, 0.60 in German and 0.50 in Portuguese.  An absolute
#: threshold across that spread is worthless, which is why the dictionary route
#: is only trusted when :func:`document_baseline` has supplied the clean level
#: for this particular book.
CLEAN_DICTIONARY_BASELINE = 0.55

#: Mean length of a word in the supported languages, near enough.  The
#: exponent is a weak lever — halving it moves the estimate by well under the
#: estimator's own noise — so a constant is honest here.
MEAN_WORD_LENGTH = 5.0

#: Share of damaged words that :func:`~caissa.ocr.lexicon.is_implausible_token`
#: actually catches.  Calibrated against synthetic corruption of English,
#: Portuguese and German chess prose using the standard OCR confusion set
#: ``l 1 I 5 0 O B 8 S G 6``: roughly half of those substitutions put a digit
#: in a word or destroy its vowels, and the other half replace one letter with
#: another letter and leave a pronounceable token behind.  Dividing by this
#: converts "damage we can see" into "damage there is".
#:
#: It is a *measured constant of the confusion set*, not of any one engine, and
#: it is the estimator's largest single source of error.  See
#: docs/quality/F5_REPORT.md for the measured spread.
NONWORD_DETECTION_RATE = 0.55

#: Character n-gram plausibility of clean prose, averaged over the supported
#: languages.  The deficit below it is the secondary damage signal.
CLEAN_NGRAM_PLAUSIBILITY = 0.97


def _damage_to_cer(damaged_fraction: float) -> float:
    """Invert ``damaged = 1 - (1 - cer) ** L`` for ``cer``."""
    damaged = max(0.0, min(0.999, damaged_fraction))
    return 1.0 - (1.0 - damaged) ** (1.0 / MEAN_WORD_LENGTH)


def document_baseline(signals: Sequence[QualitySignals],
                      percentile: float = 80.0) -> float | None:
    """Clean dictionary hit rate for one book, from its own best pages.

    Vocabulary is homogeneous within a book, so the pages that scored best are
    the closest thing to ground truth available offline.  Measuring the rest
    against them turns the dictionary from a useless absolute test into the
    strongest signal there is — but only for a document, never for a lone page,
    which is why this is a separate function the caller must choose to use.
    """
    rates = [s.dictionary_hit_rate for s in signals if s.judged_tokens >= 24]
    if len(rates) < 3:
        return None
    return float(np.percentile(rates, percentile))


@dataclass(frozen=True, slots=True)
class QualitySignals:
    """Everything measured about a piece of text, before any judgement."""

    char_count: int
    word_count: int
    judged_tokens: int
    dictionary_hit_rate: float
    nonword_ratio: float
    ngram_plausibility: float
    implausible_char_ratio: float
    notation_token_ratio: float

    def as_dict(self) -> dict[str, float]:
        return {
            "char_count": float(self.char_count),
            "word_count": float(self.word_count),
            "judged_tokens": float(self.judged_tokens),
            "dictionary_hit_rate": self.dictionary_hit_rate,
            "nonword_ratio": self.nonword_ratio,
            "ngram_plausibility": self.ngram_plausibility,
            "implausible_char_ratio": self.implausible_char_ratio,
            "notation_token_ratio": self.notation_token_ratio,
        }


def measure_text(text: str, lang: str = "") -> QualitySignals:
    """Compute every reference-free signal for ``text``."""
    langs = normalise_lang(lang)
    tokens = tokenize(text)
    notation = sum(1 for t in tokens if is_chess_notation(t))
    hit_rate, judged = dictionary_hit_rate(text, langs)
    nonword, _ = nonword_ratio(text, langs)
    plausibility, _ = ngram_plausibility(text)
    implausible, _ = implausible_char_ratio(text)
    return QualitySignals(
        char_count=sum(1 for c in text if not c.isspace()),
        word_count=len(tokens),
        judged_tokens=judged,
        dictionary_hit_rate=hit_rate,
        nonword_ratio=nonword,
        ngram_plausibility=plausibility,
        implausible_char_ratio=implausible,
        notation_token_ratio=notation / len(tokens) if tokens else 0.0,
    )


def estimate_cer(text: str, lang: str = "", *,
                 signals: QualitySignals | None = None,
                 dictionary_baseline: float | None = None) -> tuple[float, float]:
    """Estimate CER without ground truth.  Returns ``(cer, confidence)``.

    Three routes, in decreasing order of trust:

    1.  **Implausible tokens.**  The primary signal, because it is the only one
        whose *clean* value is zero in every language — English, Portuguese and
        German prose all score 0.000 — so no per-text baseline is needed.  It
        sees only about half the damage (see :data:`NONWORD_DETECTION_RATE`), and
        dividing by that share recovers the rest.
    2.  **Character n-gram deficit.**  Weaker and language-dependent, used only
        to raise the estimate when it sees damage the token test missed.
    3.  **Dictionary decline**, and only when ``dictionary_baseline`` gives the
        clean level for this book.  Without it the absolute hit rate says more
        about the author's vocabulary than about the scan.

    ``confidence`` is confidence *in the estimate*, not in the text.  It falls
    with the number of judged tokens and with the share of the text that is
    chess notation, which is excluded from every lexical test by design.
    Callers must not present a low-confidence estimate as a measurement.
    """
    signals = signals or measure_text(text, lang)
    if signals.char_count == 0:
        return 0.0, 0.0

    # Characters no correct output contains are errors outright, whatever the
    # word-level tests say; they are added at the end rather than blended.
    hard_errors = signals.implausible_char_ratio

    seen = min(0.999, signals.nonword_ratio / NONWORD_DETECTION_RATE)
    from_tokens = _damage_to_cer(seen)

    ngram_damage = max(0.0, (CLEAN_NGRAM_PLAUSIBILITY - signals.ngram_plausibility)
                       / CLEAN_NGRAM_PLAUSIBILITY)
    from_ngram = _damage_to_cer(ngram_damage)

    # The n-gram route only ever raises the estimate, and only halfway: it is
    # the corroborator, not the measurement.
    cer = from_tokens + 0.5 * max(0.0, from_ngram - from_tokens)

    if dictionary_baseline and dictionary_baseline > 0.05:
        decline = max(0.0, (dictionary_baseline - signals.dictionary_hit_rate)
                      / dictionary_baseline)
        from_dictionary = _damage_to_cer(decline)
        weight = min(1.0, signals.judged_tokens / 48.0)
        cer = (1.0 - 0.5 * weight) * cer + 0.5 * weight * from_dictionary

    cer = min(1.0, cer + hard_errors * (1.0 - cer))

    confidence = min(1.0, signals.judged_tokens / 24.0)
    if signals.notation_token_ratio > 0.5:
        # Move text is legitimate but invisible to every lexical test.
        confidence *= max(0.0, 1.0 - (signals.notation_token_ratio - 0.5) * 2.0)
    if signals.char_count < 40:
        confidence *= signals.char_count / 40.0
    return cer, max(0.0, min(1.0, confidence))


def text_plausibility(text: str, lang: str = "", *,
                      signals: QualitySignals | None = None) -> float:
    """A 0..1 "is this real language" score, for the arbiter.

    Blends the dictionary and n-gram signals, penalises impossible characters,
    and — importantly — does not punish a region that is pure move text, which
    is exactly the region an engine is most likely to mangle and where the
    arbiter most needs a usable score.
    """
    signals = signals or measure_text(text, lang)
    if signals.char_count == 0:
        return 0.0

    dictionary = min(1.0, signals.dictionary_hit_rate / CLEAN_DICTIONARY_BASELINE)
    evidence = min(1.0, signals.judged_tokens / 24.0)
    lexical = evidence * dictionary + (1.0 - evidence) * signals.ngram_plausibility
    score = 0.6 * lexical + 0.4 * signals.ngram_plausibility
    score *= (1.0 - signals.implausible_char_ratio)
    score *= (1.0 - 0.5 * signals.nonword_ratio)
    if signals.notation_token_ratio > 0.5:
        # Blend towards neutral rather than towards zero.
        weight = min(1.0, (signals.notation_token_ratio - 0.5) * 2.0)
        score = (1.0 - weight) * score + weight * max(score, 0.65)
    return max(0.0, min(1.0, score))


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


class Severity(StrEnum):
    """How badly a region or page needs a human."""

    OK = "ok"
    ATTENTION = "attention"
    BAD = "bad"

    @property
    def label_pt(self) -> str:
        return {
            Severity.OK: "aprovada",
            Severity.ATTENTION: "revisar",
            Severity.BAD: "reprovada",
        }[self]


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    """Tied to the F5 acceptance gate: CER <= 0,5 % clean, <= 2,0 % noisy."""

    cer_ok: float = 0.005
    cer_attention: float = 0.020
    min_mean_confidence: float = 0.80
    min_word_confidence: float = 0.45
    #: Share of words below :attr:`min_word_confidence` that still counts as OK.
    max_low_confidence_share: float = 0.02
    #: Below this the CER estimate is reported but not acted on.
    min_estimate_confidence: float = 0.35


@dataclass(frozen=True, slots=True)
class RegionQuality:
    """Quality of one recognised region."""

    engine: str
    region_kind: RegionKind
    severity: Severity
    estimated_cer: float
    estimate_confidence: float
    mean_confidence: float
    min_word_confidence: float
    low_confidence_words: int
    word_count: int
    signals: QualitySignals
    reasons: tuple[str, ...] = ()

    @property
    def low_confidence_share(self) -> float:
        return (self.low_confidence_words / self.word_count
                if self.word_count else 0.0)

    def describe_pt(self) -> str:
        head = (f"{self.severity.label_pt} — CER estimado "
                f"{self.estimated_cer:.2%}")
        if self.estimate_confidence < 0.35:
            head += " (estimativa pouco confiável)"
        if self.reasons:
            head += ": " + "; ".join(self.reasons)
        return head


@dataclass(frozen=True, slots=True)
class PageQuality:
    """Quality of a whole page, and which of its regions to look at."""

    page_index: int
    severity: Severity
    estimated_cer: float
    mean_confidence: float
    regions: tuple[RegionQuality, ...] = ()
    reasons: tuple[str, ...] = ()
    meta: Mapping[str, object] = field(default_factory=dict)

    @property
    def needs_attention(self) -> bool:
        return self.severity is not Severity.OK

    @property
    def worst_regions(self) -> tuple[RegionQuality, ...]:
        return tuple(sorted(
            (r for r in self.regions if r.severity is not Severity.OK),
            key=lambda r: (-r.estimated_cer, r.engine),
        ))

    def describe_pt(self) -> str:
        head = (f"Página {self.page_index + 1}: {self.severity.label_pt}, "
                f"CER estimado {self.estimated_cer:.2%}, "
                f"confiança média {self.mean_confidence:.0%}")
        bad = self.worst_regions
        if bad:
            head += f", {len(bad)} região(ões) a revisar"
        if self.reasons:
            head += ". " + "; ".join(self.reasons)
        return head


def _severity_for(cer: float, estimate_confidence: float,
                  mean_conf: float, low_share: float,
                  th: QualityThresholds) -> tuple[Severity, list[str]]:
    reasons: list[str] = []
    severity = Severity.OK

    if estimate_confidence >= th.min_estimate_confidence:
        if cer > th.cer_attention:
            severity = Severity.BAD
            reasons.append(
                f"taxa de erro de caractere estimada em {cer:.1%}, acima do "
                f"limite de {th.cer_attention:.1%}")
        elif cer > th.cer_ok:
            severity = Severity.ATTENTION
            reasons.append(
                f"taxa de erro de caractere estimada em {cer:.1%}, acima da "
                f"meta de {th.cer_ok:.1%}")
    else:
        reasons.append(
            "texto curto demais ou majoritariamente notação: a estimativa de "
            "erro não é confiável")

    if mean_conf and mean_conf < th.min_mean_confidence:
        reasons.append(f"confiança média do motor em {mean_conf:.0%}")
        if severity is Severity.OK:
            severity = Severity.ATTENTION

    if low_share > th.max_low_confidence_share:
        reasons.append(
            f"{low_share:.0%} das palavras abaixo de "
            f"{th.min_word_confidence:.0%} de confiança")
        if severity is Severity.OK:
            severity = Severity.ATTENTION
    return severity, reasons


def assess_result(result: OcrResult, *, lang: str = "",
                  thresholds: QualityThresholds | None = None
                  ) -> RegionQuality:
    """Quality report for one engine result."""
    th = thresholds or QualityThresholds()
    language = lang or result.lang
    signals = measure_text(result.text, language)
    cer, estimate_confidence = estimate_cer(result.text, language,
                                            signals=signals)

    words = [w for w in result.words if w.text.strip()]
    low = [w for w in words if w.confidence < th.min_word_confidence]
    mean_conf = result.mean_confidence
    low_share = len(low) / len(words) if words else 0.0

    severity, reasons = _severity_for(cer, estimate_confidence, mean_conf,
                                      low_share, th)
    if result.is_empty:
        severity = Severity.BAD
        reasons = ["nenhum texto foi reconhecido nesta região"]
    for warning in result.warnings[:2]:
        reasons.append(warning)

    return RegionQuality(
        engine=result.engine,
        region_kind=result.region_kind,
        severity=severity,
        estimated_cer=cer,
        estimate_confidence=estimate_confidence,
        mean_confidence=mean_conf,
        min_word_confidence=result.min_word_confidence,
        low_confidence_words=len(low),
        word_count=len(words),
        signals=signals,
        reasons=tuple(reasons),
    )


def assess_page(results: Iterable[OcrResult], *, page_index: int = 0,
                lang: str = "",
                thresholds: QualityThresholds | None = None) -> PageQuality:
    """Aggregate region reports into a page report.

    Aggregation is by character count, not by region count: a page with one
    long clean paragraph and one three-word broken caption is a good page with
    one problem, and averaging the two region scores unweighted would call it a
    mediocre page throughout.  The severity, by contrast, is the *worst* region's
    — because the user's question is "must I open this page?", and one bad
    region is enough for the answer to be yes.
    """
    th = thresholds or QualityThresholds()
    regions = tuple(assess_result(r, lang=lang, thresholds=th) for r in results)
    if not regions:
        return PageQuality(page_index, Severity.BAD, 1.0, 0.0, (),
                           ("nenhuma região reconhecida nesta página",))

    weights = [max(1, r.signals.char_count) for r in regions]
    total = float(sum(weights))
    cer = sum(r.estimated_cer * w for r, w in zip(regions, weights)) / total
    confidence = sum(r.mean_confidence * w
                     for r, w in zip(regions, weights)) / total

    order = {Severity.OK: 0, Severity.ATTENTION: 1, Severity.BAD: 2}
    severity = max((r.severity for r in regions), key=lambda s: order[s])

    reasons: list[str] = []
    bad = [r for r in regions if r.severity is Severity.BAD]
    attention = [r for r in regions if r.severity is Severity.ATTENTION]
    if bad:
        reasons.append(f"{len(bad)} região(ões) reprovada(s)")
    if attention:
        reasons.append(f"{len(attention)} região(ões) a revisar")

    return PageQuality(
        page_index=page_index,
        severity=severity,
        estimated_cer=cer,
        mean_confidence=confidence,
        regions=regions,
        reasons=tuple(reasons),
        meta={
            "region_count": len(regions),
            "char_count": int(total),
            "engines": sorted({r.engine for r in regions}),
        },
    )
