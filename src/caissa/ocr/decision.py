"""Accept, review or abstain — Sol §SOL-2.

Before this module the arbiter had one verb: *accept*.  When no engine
reached its threshold it accepted the best of them anyway and labelled the
step ``accepted``, so a page of noise came out of the cascade looking
exactly like a page of prose, and a white image on which Tesseract read
``rs`` produced a paragraph reading ``rs``.  Sol §2 makes abstention a
result: nothing below the threshold may be called accepted, and a result
must show *evidence* — enough characters, words the image actually has ink
under, a shape a text region can have — before it is allowed into the IR.

The policy has three outcomes and is deliberately conservative:

``ACCEPTED``
    Score at or above the acceptance bar **and** every evidence check
    passed.  Only accepted text enters the body without a mark.

``REVIEW``
    Plausible but doubtful: below the acceptance bar yet above the review
    floor, or accepted on score but with a weak spot — many low-confidence
    words, move-shaped tokens with nothing but their shape vouching for
    them, a word without ink under it.  Enters the IR flagged, with the
    reasons, for the reviewer.

``ABSTAINED``
    No engine reached the review floor, or the result fails an evidence
    check that no confidence can repair: empty text, a few characters of
    noise, words floating over blank paper.  The region keeps its image and
    the reasons; nothing textual is emitted for it.

Every decision carries its reasons in Portuguese so the report and the
review panel can say why, not just what.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .lexicon import dictionary_hit_rate, is_move_token, tokenize
from .types import OcrResult, OcrWord, RegionKind

__all__ = [
    "Decision",
    "DecisionPolicy",
    "Evidence",
    "RegionDecision",
    "decide",
    "measure_evidence",
]


class Decision(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    ABSTAINED = "abstained"

    @property
    def emits_text(self) -> bool:
        """Whether text with this decision may enter the document body."""
        return self is not Decision.ABSTAINED


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Every threshold the decision depends on, in one place.

    ``accept_score`` and ``review_score`` are arbiter scores (calibrated
    confidence blended with plausibility and agreement, 0..1).  The
    evidence floors are absolute and cannot be bought back by a high score.
    """

    accept_score: float = 0.78
    review_score: float = 0.50
    #: Fewer non-space characters than this is noise, not a region.
    min_chars: int = 3
    #: A very short result (under ``short_chars``) must contain at least one
    #: dictionary word or one move to count as text at all.
    short_chars: int = 12
    #: Share of characters in words with no ink under them beyond which the
    #: region is abstained rather than reviewed.
    max_unsupported_share: float = 0.50
    #: A word box is "unsupported" when fewer than this share of its pixels
    #: are ink.  Printed text at 300 DPI runs 8–25 %; a speck runs under 1 %.
    min_ink_in_word: float = 0.015
    #: Words taller than this multiple of the median word height, or shorter
    #: than its reciprocal, have no geometric support.
    height_ratio_limit: float = 3.5
    #: Share of characters in low-confidence words that sends the region to
    #: review even when the score cleared the bar.
    max_low_confidence_share: float = 0.30
    low_confidence_word: float = 0.60
    #: A region that is mostly move-shaped tokens needs its move tokens to be
    #: confident, or a legality replay, to be accepted; shape alone is review.
    movetext_share: float = 0.50
    move_token_confidence: float = 0.80
    #: Word shape.  An engine reading a checkerboard or a photograph produces
    #: a litter of one- and two-letter tokens that the dictionary, absurdly,
    #: accepts ("be", "by", "À", "spa").  Measured over every truth of the
    #: golden corpus with at least twelve word tokens: the share of tokens of
    #: two characters or fewer never exceeds 0.47 and the mean token length
    #: never drops under 3.05; the board and photo controls score 1.00/1.4
    #: and 0.71/2.1.  Move tokens are left out of the count (``e4`` is two
    #: characters and perfectly real).
    min_tokens_for_shape: int = 12
    max_short_token_share: float = 0.60
    min_mean_token_length: float = 2.6


@dataclass(frozen=True, slots=True)
class Evidence:
    """What the checks measured, kept so the decision can be explained."""

    chars: int
    words: int
    dictionary_words: int
    move_tokens: int
    move_share: float
    unsupported_share: float
    ink_measured: bool
    geometry_outliers: int
    low_confidence_share: float
    move_token_confidence: float
    short_token_share: float = 0.0
    mean_token_length: float = 0.0
    word_tokens: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "chars": self.chars,
            "words": self.words,
            "dictionary_words": self.dictionary_words,
            "move_tokens": self.move_tokens,
            "move_share": round(self.move_share, 3),
            "unsupported_share": round(self.unsupported_share, 3),
            "ink_measured": self.ink_measured,
            "geometry_outliers": self.geometry_outliers,
            "low_confidence_share": round(self.low_confidence_share, 3),
            "move_token_confidence": round(self.move_token_confidence, 3),
            "short_token_share": round(self.short_token_share, 3),
            "mean_token_length": round(self.mean_token_length, 2),
            "word_tokens": self.word_tokens,
        }


@dataclass(frozen=True, slots=True)
class RegionDecision:
    decision: Decision
    score: float
    accept_threshold: float
    review_threshold: float
    reasons_pt: tuple[str, ...]
    evidence: Evidence | None = None
    #: Words the checks singled out, for the review panel.
    flagged_words: tuple[OcrWord, ...] = ()
    #: True when the score alone would have accepted; the evidence demoted it.
    demoted: bool = False
    #: Support from a legality replay (SOL-8), when one ran.
    legality: Mapping[str, Any] = field(default_factory=dict)

    @property
    def below_threshold(self) -> bool:
        return self.score < self.accept_threshold

    def describe_pt(self) -> str:
        label = {
            Decision.ACCEPTED: "aceita",
            Decision.REVIEW: "para revisão",
            Decision.ABSTAINED: "abstenção",
        }[self.decision]
        head = (f"Região {label}: escore {self.score:.3f} "
                f"(aceitar ≥ {self.accept_threshold:.2f}, revisar ≥ "
                f"{self.review_threshold:.2f}).")
        return head + ("" if not self.reasons_pt else " " + " ".join(self.reasons_pt))

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": str(self.decision),
            "score": round(self.score, 4),
            "accept_threshold": self.accept_threshold,
            "review_threshold": self.review_threshold,
            "reasons": list(self.reasons_pt),
            "evidence": self.evidence.as_dict() if self.evidence else None,
            "flagged_words": [w.text for w in self.flagged_words],
            "demoted": self.demoted,
            "legality": dict(self.legality),
        }


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #


def _ink_share(image: NDArray[np.uint8], word: OcrWord, paper: float) -> float | None:
    """Share of the word box darker than the paper by a margin, or ``None``
    when the box lies outside the image.
    """
    h, w = image.shape[:2]
    x, y, bw, bh = word.box.to_int_tuple()
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + bw), min(h, y + bh)
    if x1 <= x0 or y1 <= y0:
        return None
    patch = image[y0:y1, x0:x1]
    if patch.ndim == 3:
        patch = patch.mean(axis=2)
    return float(np.mean(patch < paper - 40.0))


def _paper_level(image: NDArray[np.uint8]) -> float:
    flat = image if image.ndim == 2 else image.mean(axis=2)
    return float(np.percentile(flat, 90))


def measure_evidence(result: OcrResult, image: NDArray[np.uint8] | None,
                     policy: DecisionPolicy, *, langs: tuple[str, ...] = ()
                     ) -> tuple[Evidence, tuple[OcrWord, ...]]:
    """Run every evidence check once and return the numbers plus the words
    that failed one.
    """
    words = [w for w in result.words if w.text.strip()]
    chars = sum(len(w.text.strip()) for w in words)
    flagged: list[OcrWord] = []

    tokens = tokenize(result.text)
    move_count = sum(1 for t in tokens if is_move_token(t))
    _, judged = dictionary_hit_rate(result.text, langs)
    hit_rate, _ = dictionary_hit_rate(result.text, langs)
    dictionary_words = round(hit_rate * judged)
    move_share = move_count / len(tokens) if tokens else 0.0

    # Geometry: a word far taller or shorter than the others has no line.
    outliers = 0
    heights = [w.box.h for w in words if w.box.h > 0]
    if len(heights) >= 3:
        median = statistics.median(heights)
        for w in words:
            if w.box.h <= 0:
                continue
            ratio = w.box.h / median
            if ratio > policy.height_ratio_limit or ratio < 1.0 / policy.height_ratio_limit:
                outliers += 1
                flagged.append(w)

    # Ink: a word over blank paper is a hallucination.
    unsupported_chars = 0
    ink_measured = False
    if image is not None and getattr(image, "size", 0) > 0 and words:
        paper = _paper_level(image)
        ink_measured = True
        for w in words:
            share = _ink_share(image, w, paper)
            if share is None:
                continue
            if share < policy.min_ink_in_word:
                unsupported_chars += len(w.text.strip())
                if w not in flagged:
                    flagged.append(w)
    unsupported_share = unsupported_chars / chars if chars else 0.0

    low = [w for w in words if w.confidence < policy.low_confidence_word]
    low_share = (sum(len(w.text.strip()) for w in low) / chars) if chars else 0.0
    move_words = [w for w in words if is_move_token(w.text.strip())]
    move_conf = (sum(w.confidence for w in move_words) / len(move_words)
                 if move_words else 0.0)
    word_tokens = [t for t in tokens if any(c.isalpha() for c in t) and not is_move_token(t)]
    short_share = (sum(1 for t in word_tokens if len(t) <= 2) / len(word_tokens)
                   if word_tokens else 0.0)
    mean_length = (sum(len(t) for t in word_tokens) / len(word_tokens)) if word_tokens else 0.0

    return Evidence(
        chars=chars, words=len(words), dictionary_words=dictionary_words,
        move_tokens=move_count, move_share=move_share,
        unsupported_share=unsupported_share, ink_measured=ink_measured,
        geometry_outliers=outliers, low_confidence_share=low_share,
        move_token_confidence=move_conf, short_token_share=short_share,
        mean_token_length=mean_length, word_tokens=len(word_tokens),
    ), tuple(flagged)


# --------------------------------------------------------------------------- #
# Decision
# --------------------------------------------------------------------------- #


def decide(result: OcrResult, score: float, *, policy: DecisionPolicy | None = None,
           image: NDArray[np.uint8] | None = None, langs: tuple[str, ...] = (),
           region_kind: RegionKind = RegionKind.UNKNOWN,
           accept_threshold: float | None = None,
           reached_threshold: bool | None = None,
           legality: Mapping[str, Any] | None = None,
           trusted_source: bool = False) -> RegionDecision:
    """The decision for one region's chosen result.

    ``score`` is the arbiter's score for ``result``.  ``accept_threshold``
    lets the caller pass the level-specific bar the arbiter used;
    ``reached_threshold`` overrides the comparison when the arbiter already
    knows (a level-0 result accepted by its own verdict, for instance).
    ``legality`` is the outcome of a legality replay, when one ran: a block
    that replays cleanly is evidence for its move tokens.

    ``trusted_source`` marks a result that was *read*, not recognised — the
    PDF's own text layer, already judged by its verdict.  The noise floors
    exist for an engine that can hallucinate letters on blank paper; a text
    layer cannot, and a folio reading ``41`` is two characters of real
    text, not noise.  The score bars still apply.
    """
    policy = policy or DecisionPolicy()
    accept_bar = policy.accept_score if accept_threshold is None else accept_threshold
    review_bar = min(policy.review_score, accept_bar)
    legality = dict(legality or {})
    reasons: list[str] = []

    if result.is_empty or not result.text.strip():
        return RegionDecision(
            Decision.ABSTAINED, score, accept_bar, review_bar,
            ("Nenhum texto foi reconhecido nesta região.",), None, (), False, legality)

    evidence, flagged = measure_evidence(result, image, policy, langs=langs)

    # -- evidence floors: no score buys these back ------------------------ #
    if trusted_source:
        pass
    elif evidence.chars < policy.min_chars:
        reasons.append(f"Apenas {evidence.chars} caractere(s): ruído, não texto.")
        return RegionDecision(Decision.ABSTAINED, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)
    if (not trusted_source and evidence.chars < policy.short_chars
            and evidence.dictionary_words == 0 and evidence.move_tokens == 0):
        reasons.append(
            f"Texto curto ({evidence.chars} caracteres) sem palavra de dicionário nem lance: "
            f"sem evidência de que seja texto.")
        return RegionDecision(Decision.ABSTAINED, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)
    if evidence.ink_measured and evidence.unsupported_share > policy.max_unsupported_share:
        reasons.append(
            f"{evidence.unsupported_share:.0%} dos caracteres estão em palavras sem tinta "
            f"sob a caixa: o motor leu papel em branco.")
        return RegionDecision(Decision.ABSTAINED, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)
    if (not trusted_source and evidence.word_tokens >= policy.min_tokens_for_shape
            and evidence.move_share < 0.3
            and (evidence.short_token_share > policy.max_short_token_share
                 or evidence.mean_token_length < policy.min_mean_token_length)):
        reasons.append(
            f"{evidence.short_token_share:.0%} das palavras têm até dois caracteres "
            f"(comprimento médio {evidence.mean_token_length:.1f}): forma de ruído, não de "
            f"texto, ainda que o dicionário aceite os fragmentos.")
        return RegionDecision(Decision.ABSTAINED, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)
    if evidence.words >= 3 and evidence.geometry_outliers > evidence.words / 2:
        reasons.append(
            f"{evidence.geometry_outliers} de {evidence.words} palavras com altura "
            f"incompatível com uma linha de texto.")
        return RegionDecision(Decision.ABSTAINED, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)

    # -- score bars -------------------------------------------------------- #
    cleared = (reached_threshold if reached_threshold is not None
               else score >= accept_bar)
    if not cleared and score < review_bar:
        reasons.append(
            f"Nenhum motor alcançou o piso de revisão ({review_bar:.2f}); "
            f"melhor escore {score:.3f}.")
        return RegionDecision(Decision.ABSTAINED, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)
    if not cleared:
        reasons.append(
            f"Escore {score:.3f} abaixo do limite de aceitação ({accept_bar:.2f}), "
            f"mas acima do piso de revisão.")
        return RegionDecision(Decision.REVIEW, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, False, legality)

    # -- accepted on score: look for a weak spot --------------------------- #
    demote = False
    if evidence.unsupported_share > 0.0:
        demote = True
        reasons.append(
            f"{evidence.unsupported_share:.0%} dos caracteres em palavras sem tinta sob a caixa.")
    if evidence.geometry_outliers:
        demote = True
        reasons.append(f"{evidence.geometry_outliers} palavra(s) fora da geometria das linhas.")
    if evidence.low_confidence_share > policy.max_low_confidence_share:
        demote = True
        reasons.append(
            f"{evidence.low_confidence_share:.0%} dos caracteres em palavras de baixa confiança.")
    movetext_like = (region_kind is RegionKind.MOVETEXT
                     or evidence.move_share >= policy.movetext_share)
    if movetext_like and evidence.move_tokens:
        replayed = bool(legality.get("replayed_to_end")) and not legality.get("unresolved")
        if not replayed and evidence.move_token_confidence < policy.move_token_confidence:
            demote = True
            reasons.append(
                f"Lances com confiança média {evidence.move_token_confidence:.2f} e sem replay "
                f"legal: forma de lance não basta para aceitar.")
        if legality.get("unresolved"):
            demote = True
            reasons.append(
                f"{legality['unresolved']} lance(s) não puderam ser reproduzidos legalmente.")
    if demote:
        return RegionDecision(Decision.REVIEW, score, accept_bar, review_bar,
                              tuple(reasons), evidence, flagged, True, legality)
    return RegionDecision(Decision.ACCEPTED, score, accept_bar, review_bar,
                          tuple(reasons), evidence, flagged, False, legality)


def decision_counts(decisions: Sequence[RegionDecision]) -> dict[str, int]:
    counts = {str(d): 0 for d in Decision}
    for decision in decisions:
        counts[str(decision.decision)] += 1
    return counts
