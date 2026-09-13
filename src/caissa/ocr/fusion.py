"""Geometric token fusion — Sol §SOL-6.

The arbiter picks one *result* per region.  That is the right granularity
for deciding whether a region was read at all and the wrong one for
deciding what it says: the text layer is right about the prose and wrong
about the figurines, Tesseract on the deskewed variant reads the diacritics
and drops a hyphen, Tesseract on the binarised variant does the opposite.
Choosing a whole result throws away the parts of the others that were
better.  Fusion keeps them, token by token.

The method is deliberately conservative, in the order the rules apply:

1. **Anchor.**  The best candidate by decision and score is the anchor;
   every other candidate is aligned *to it*.  The fused text has exactly
   the anchor's tokens — no token is inserted from another candidate, so
   the insertion rate cannot rise (§SOL-6, "penalizar inserções sem suporte
   visual em outro candidato").
2. **Lines by geometry.**  A line of another candidate is paired with the
   anchor line it overlaps most, and only when the overlap is real (half
   the shorter height, half the narrower width).  Lines of different
   columns never pair, so words are never joined across a gutter.
3. **Words by position and text.**  Within paired lines, words are matched
   left to right by horizontal overlap, then by edit distance among the
   overlapping ones.  A word with no partner simply contributes nothing.
4. **Choice per slot.**  Each slot has the anchor's reading and up to one
   reading per other candidate.  Readings are weighted by their calibrated
   word confidence, the source's score and lexical support (a dictionary
   word, a move token), with small, specific preferences for a reading
   that keeps diacritics the language uses, that keeps punctuation the
   others confirm, and that keeps a line-end hyphen.  The anchor wins ties.
5. **Trust is not overridden downwards.**  When the anchor is the PDF text
   layer with an accepted verdict, its tokens are never replaced; the
   others only supply alternatives for the reviewer.
6. **A close call is a review item.**  A slot whose winner beat the anchor
   by less than a margin, or where the sources disagree with no clear
   winner, is *disputed*: the anchor's reading stays, the alternative is
   recorded, and enough disputed slots turn the region's decision to
   review.

Every fused token records where it came from — which sources agreed,
which read something else, and what — so the answer to "why does it say
this?" is one lookup (§SOL-6, "explicar de onde veio cada token final").
Hyphenation at line ends is left exactly as read: joining across lines is
a reading-order question and happens after layout, not here.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

from .decision import Decision, RegionDecision, decide
from .lexicon import dictionary_hit_rate, is_move_token, normalise_lang
from .quality import levenshtein
from .types import BBox, OcrLine, OcrResult, OcrWord

__all__ = ["FusedRegion", "FusedToken", "FusionConfig", "fuse_candidates"]

_TRUSTED_ENGINES = frozenset({"pdf_text_layer"})
_DIACRITIC_LANGS = frozenset({"por", "spa", "deu", "fra", "ita", "nld", "ron"})


@dataclass(frozen=True, slots=True)
class FusionConfig:
    min_line_overlap: float = 0.5
    min_word_overlap: float = 0.3
    #: Below this margin over the anchor's reading a winner is a dispute.
    dispute_margin: float = 0.08
    #: Share of disputed characters that sends the region to review.
    max_disputed_share: float = 0.10
    lexicon_bonus: float = 0.15
    move_bonus: float = 0.15
    diacritic_bonus: float = 0.05
    punctuation_bonus: float = 0.03
    hyphen_bonus: float = 0.03
    #: Weight of the source's region score against the word confidence.
    source_weight: float = 0.35


@dataclass(frozen=True, slots=True)
class Reading:
    source: str            # "variant/engine"
    text: str
    confidence: float
    box: BBox


@dataclass(frozen=True, slots=True)
class FusedToken:
    """One token of the fused text and its provenance."""

    text: str
    box: BBox
    confidence: float
    chosen_from: str
    readings: tuple[Reading, ...]
    disputed: bool = False
    alternative: str = ""

    @property
    def agreement(self) -> float:
        same = sum(1 for r in self.readings if _fold(r.text) == _fold(self.text))
        return same / len(self.readings) if self.readings else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text, "from": self.chosen_from,
            "confidence": round(self.confidence, 3),
            "agreement": round(self.agreement, 2),
            "disputed": self.disputed, "alternative": self.alternative,
            "readings": [(r.source, r.text, round(r.confidence, 3)) for r in self.readings],
        }


@dataclass(frozen=True, slots=True)
class FusedRegion:
    result: OcrResult
    decision: RegionDecision
    tokens: tuple[FusedToken, ...]
    anchor: str
    sources: tuple[str, ...]
    changed: int
    disputed: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchor": self.anchor, "sources": list(self.sources),
            "tokens": len(self.tokens), "changed": self.changed, "disputed": self.disputed,
            "changed_tokens": [t.as_dict() for t in self.tokens
                               if t.chosen_from != self.anchor or t.disputed][:40],
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _has_diacritics(text: str) -> bool:
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", text))


def _source_of(result: OcrResult) -> str:
    return f"{result.meta.get('variant', 'original')}/{result.engine}"


def _pair_lines(anchor: OcrLine, lines: Sequence[OcrLine], cfg: FusionConfig) -> OcrLine | None:
    best, best_score = None, 0.0
    for line in lines:
        v = anchor.box.vertical_overlap(line.box)
        h = anchor.box.horizontal_overlap(line.box)
        if v < cfg.min_line_overlap or h < cfg.min_line_overlap:
            continue
        score = v * h
        if score > best_score:
            best, best_score = line, score
    return best


def _pair_words(anchor: OcrLine, other: OcrLine, cfg: FusionConfig) -> dict[int, OcrWord]:
    """Anchor word index → the other line's word, by overlap then by text."""
    pairs: dict[int, OcrWord] = {}
    used: set[int] = set()
    others = list(other.words)
    for i, word in enumerate(anchor.words):
        best, best_key = None, (-1.0, 10 ** 6)
        for j, candidate in enumerate(others):
            if j in used:
                continue
            overlap = word.box.horizontal_overlap(candidate.box)
            if overlap < cfg.min_word_overlap:
                continue
            distance = levenshtein(_fold(word.text), _fold(candidate.text))
            key = (overlap - 0.05 * distance, -distance)
            if key > best_key:
                best, best_key = j, key
        if best is not None:
            used.add(best)
            pairs[i] = others[best]
    return pairs


# --------------------------------------------------------------------------- #
# Fusion
# --------------------------------------------------------------------------- #


def fuse_candidates(candidates: Sequence[tuple[OcrResult, float, RegionDecision]], *,
                    lang: str = "", image: NDArray[np.uint8] | None = None,
                    config: FusionConfig | None = None) -> FusedRegion | None:
    """Fuse the candidates of one region.  ``None`` when there is nothing to fuse."""
    cfg = config or FusionConfig()
    usable = [(r, s, d) for r, s, d in candidates if r.lines and r.text.strip()]
    if len(usable) < 2:
        return None
    rank = {Decision.ACCEPTED: 2, Decision.REVIEW: 1, Decision.ABSTAINED: 0}
    usable.sort(key=lambda c: (rank[c[2].decision], c[1]), reverse=True)
    anchor_result, anchor_score, anchor_decision = usable[0]
    anchor_name = _source_of(anchor_result)
    trusted = (anchor_result.engine in _TRUSTED_ENGINES
               and anchor_decision.decision is Decision.ACCEPTED)
    langs = normalise_lang(lang)
    diacritic_lang = bool(langs) and langs[0] in _DIACRITIC_LANGS

    # Per anchor word: the readings of every source.
    slots: list[list[Reading]] = []
    slot_words: list[tuple[int, int, OcrWord]] = []   # (line index, word index, word)
    for li, line in enumerate(anchor_result.lines):
        for wi, word in enumerate(line.words):
            slots.append([Reading(anchor_name, word.text, word.confidence, word.box)])
            slot_words.append((li, wi, word))
    slot_index = {(li, wi): n for n, (li, wi, _) in enumerate(slot_words)}

    source_scores = {anchor_name: anchor_score}
    for other_result, other_score, _ in usable[1:]:
        name = _source_of(other_result)
        source_scores[name] = other_score
        for li, line in enumerate(anchor_result.lines):
            partner = _pair_lines(line, other_result.lines, cfg)
            if partner is None:
                continue
            for wi, other_word in _pair_words(line, partner, cfg).items():
                slots[slot_index[(li, wi)]].append(
                    Reading(name, other_word.text, other_word.confidence, other_word.box))

    tokens: list[FusedToken] = []
    changed = 0
    disputed = 0
    for readings, (li, _, word) in zip(slots, slot_words, strict=True):
        line = anchor_result.lines[li]
        at_line_end = word is line.words[-1]
        chosen, alternative, is_disputed = _choose(
            readings, cfg, source_scores, langs, diacritic_lang, at_line_end, trusted)
        agreeing = [r for r in readings if _fold(r.text) == _fold(chosen.text)]
        confidence = max(r.confidence for r in agreeing)
        if len(agreeing) > 1:
            # Independent agreement is evidence; it lifts, it does not certify.
            confidence = min(1.0, confidence + 0.05 * (len(agreeing) - 1))
        if chosen.source != anchor_name:
            changed += 1
        if is_disputed:
            disputed += 1
        tokens.append(FusedToken(
            text=chosen.text, box=word.box, confidence=confidence,
            chosen_from=chosen.source, readings=tuple(readings),
            disputed=is_disputed, alternative=alternative))

    fused_result = _rebuild(anchor_result, tokens, slot_words)
    total_chars = sum(len(t.text) for t in tokens) or 1
    disputed_chars = sum(len(t.text) for t in tokens if t.disputed)
    decision = anchor_decision
    if changed or disputed:
        decision = decide(
            fused_result, anchor_score, image=image, langs=langs,
            region_kind=anchor_result.region_kind,
            accept_threshold=anchor_decision.accept_threshold,
            reached_threshold=not anchor_decision.below_threshold,
            trusted_source=trusted, legality=anchor_decision.legality)
        if (disputed_chars / total_chars > cfg.max_disputed_share
                and decision.decision is Decision.ACCEPTED):
            decision = RegionDecision(
                Decision.REVIEW, decision.score, decision.accept_threshold,
                decision.review_threshold,
                decision.reasons_pt + (
                    f"{disputed} token(s) em disputa entre as leituras "
                    f"({disputed_chars / total_chars:.0%} dos caracteres).",),
                decision.evidence, decision.flagged_words, True, decision.legality)
    return FusedRegion(
        result=fused_result, decision=decision, tokens=tuple(tokens), anchor=anchor_name,
        sources=tuple(source_scores), changed=changed, disputed=disputed)


def _choose(readings: Sequence[Reading], cfg: FusionConfig, source_scores: dict[str, float],
            langs: tuple[str, ...], diacritic_lang: bool, at_line_end: bool,
            trusted: bool) -> tuple[Reading, str, bool]:
    anchor = readings[0]
    if trusted or len(readings) == 1:
        return anchor, "", False
    distinct: dict[str, list[Reading]] = {}
    for reading in readings:
        distinct.setdefault(reading.text, []).append(reading)
    if len(distinct) == 1:
        return anchor, "", False

    scored: list[tuple[float, str, Reading]] = []
    for text, group in distinct.items():
        base = max(cfg.source_weight * source_scores.get(r.source, 0.0)
                   + (1.0 - cfg.source_weight) * r.confidence for r in group)
        # Every agreeing source adds evidence.
        base += 0.10 * (len(group) - 1)
        support = 0.0
        if is_move_token(text):
            support += cfg.move_bonus
        else:
            hit, judged = dictionary_hit_rate(text, langs)
            if judged and hit > 0:
                support += cfg.lexicon_bonus
        if diacritic_lang and _has_diacritics(text) and all(
                _fold(t) == _fold(text) for t in distinct):
            support += cfg.diacritic_bonus
        if text and text[-1] in ".,;:!?" and any(
                _fold(t.rstrip(".,;:!?")) == _fold(text.rstrip(".,;:!?")) and t != text
                for t in distinct):
            support += cfg.punctuation_bonus
        if at_line_end and text.endswith("-"):
            support += cfg.hyphen_bonus
        scored.append((base + support, text, group[0]))
    scored.sort(key=lambda s: (-s[0], s[1] != anchor.text, s[1]))
    best_score, best_text, best_reading = scored[0]
    anchor_score = next(s for s, t, _ in scored if t == anchor.text)
    # Readings that differ only in diacritics, case or a trailing mark are
    # exactly what the specific preferences decide; they are not a dispute.
    if len({_fold(t.rstrip(".,;:!?-")) for t in distinct}) == 1:
        return (best_reading if best_text != anchor.text else anchor,
                anchor.text if best_text != anchor.text else scored[1][1], False)
    if best_text == anchor.text:
        runner = scored[1]
        return anchor, runner[1], (best_score - runner[0]) < cfg.dispute_margin
    if best_score - anchor_score < cfg.dispute_margin:
        return anchor, best_text, True
    return best_reading, anchor.text, False


def _rebuild(anchor: OcrResult, tokens: Sequence[FusedToken],
             slot_words: Sequence[tuple[int, int, OcrWord]]) -> OcrResult:
    by_line: dict[int, list[OcrWord]] = {}
    for token, (li, _, word) in zip(tokens, slot_words, strict=True):
        by_line.setdefault(li, []).append(OcrWord(
            text=token.text, box=word.box, confidence=token.confidence,
            chars=word.chars if token.text == word.text else (),
            block_index=word.block_index, paragraph_index=word.paragraph_index,
            line_index=word.line_index, word_index=word.word_index))
    lines = tuple(
        OcrLine(words=tuple(by_line.get(li, ())), box=line.box, baseline=line.baseline,
                block_index=line.block_index, paragraph_index=line.paragraph_index,
                line_index=line.line_index, kind=line.kind, font_size=line.font_size)
        for li, line in enumerate(anchor.lines)
    )
    return OcrResult(
        engine=anchor.engine, lang=anchor.lang, lines=lines, region_kind=anchor.region_kind,
        duration_s=anchor.duration_s, warnings=anchor.warnings,
        meta={**dict(anchor.meta), "fused": True,
              "fusion_tokens": [t.as_dict() for t in tokens
                                if t.chosen_from != _source_of(anchor) or t.disputed]},
    )


def fusion_summary(region: FusedRegion) -> dict[str, Any]:
    return region.as_dict()

