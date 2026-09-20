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
   reading per other candidate.  **An anchor token that is already a word
   or a move is never replaced** — measured on the fax stratum, letting a
   supported alternative outvote a supported anchor raised CER from 0.031
   to 0.082 on a page, because a noisy variant is confident about its own
   misreadings too.  Only an anchor token with no lexical support and no
   strong confidence is open, and then an alternative must itself be
   supported (a dictionary word, a move token) and at least as confident.
   Among such alternatives the choice weighs word confidence, source score
   and the small, specific preferences: diacritics the language uses,
   punctuation the others confirm, a kept line-end hyphen.
   One exception is specific and visual: a **figurine** read by a glyph
   source (``♖e8!``) replaces an anchor token that is the same move with
   a Latin look-alike in front (``Hea!``, ``2h6``, ``De2``), because that
   is the substitution cipher of :mod:`caissa.ocr.notation.cipher` with
   the evidence in hand instead of inferred.  Glyph sources never anchor
   and never decide punctuation or case (``36...`` stays ``36...``).
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

import re
import unicodedata
from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from caissa.notation.nag_table import MOVE_SUFFIX_CHARS

from .decision import Decision, RegionDecision, decide
from .lexicon import PIECE_LETTERS_BY_LANG, dictionary_hit_rate, is_move_token, normalise_lang
from .quality import levenshtein
from .types import BBox, OcrLine, OcrResult, OcrWord

__all__ = ["FusedRegion", "FusedToken", "FusionConfig", "fuse_candidates"]

_TRUSTED_ENGINES = frozenset({"pdf_text_layer"})
_FIGURINES = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")
#: Longest look-alike cluster a damaged layer leaves for one figurine.
_MAX_CLUSTER = 5
#: Sentence punctuation and the annotation tail a move may carry
#: (:data:`caissa.notation.nag_table.MOVE_SUFFIX_CHARS`, passo A4).
_MARKS = ".,;:" + MOVE_SUFFIX_CHARS
#: Engines whose figurine readings are letter-guarded (see ``fuse_candidates``).
_LETTER_GUARDED = frozenset({"tesseract_figurine"})
#: Piece letters per Tesseract language, as the books of that language print
#: them -- the table now lives in :mod:`caissa.ocr.lexicon` (passo B4), where
#: :func:`~caissa.ocr.lexicon.is_move_token` reads it too.
_PIECE_LETTERS = PIECE_LETTERS_BY_LANG
#: Leading brackets a token may carry into a comparison (``(17...♗c7``).
_OPENERS = "(["
_B4 = ContextVar("fusion_passo_b4", default=True)
"""Whether the string repairs of passo B4 are on for the fusion running in this context."""


#: A move number glued to a move: digits then dots or a space.  A bare
#: digit before a square (``2d5``) is not a number — it is what a line engine
#: makes of ♗.
_NUMBER_PREFIX = re.compile(r"^(\d{1,3})(?:\.{1,3}|\s)")
#: A token that is only a move number, with or without its dots.
_MOVE_NUMBER = re.compile(r"^\d{1,3}\.{0,3}$")
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
    #: An anchor token at or above this confidence is kept even without
    #: lexical support (a rare name, a foreign word).
    anchor_trust_confidence: float = 0.90
    #: A figurine reading from a glyph source replaces the anchor's Latin
    #: look-alike only at or above this word confidence — the minimum over
    #: its glyphs, a trailing comma included, which is why it sits below the
    #: anchor trust level: the anchor already agrees on the square.
    figurine_min_confidence: float = 0.70
    #: A glyph reading that carries a ``margin`` (the classifier's ``1 - p2/p1``)
    #: replaces the anchor's look-alike only at or above this margin as well:
    #: 0,80 of confidence with a runner-up at 0,75 is a coin toss, not a
    #: figurine.  Readings without a margin are judged on confidence alone.
    figurine_min_margin: float = 0.25
    #: Below this anchor confidence two *independent* secondary sources that
    #: agree on a supported reading may replace it (passo B4): the anchor
    #: read ``e5`` at 0,21 where the glyph reader and the figurine model both
    #: read ``♘e5``.  A different hypothesis from the rejected SOL-6 vote,
    #: which was between noisy variants of the same engine.
    weak_anchor_confidence: float = 0.35
    #: The sabotage switch of passo B4 (``SOL_CONFIG='{"fusion": {"passo_b4": false}}'``):
    #: off, the fusion matches strings the way it did before -- a dash in a
    #: move is not support, an opening bracket or a lost digit blocks the
    #: look-alike → figurine swap, and two agreeing secondaries never outrank
    #: a weak anchor.  It exists so the gate can be made to fail on purpose.
    passo_b4: bool = True


@dataclass(frozen=True, slots=True)
class Reading:
    source: str            # "variant/engine"
    text: str
    confidence: float
    box: BBox
    #: The glyph reader's margin (``GlyphWord.margin``), when the word has one.
    margin: float | None = None

    @property
    def engine(self) -> str:
        return self.source.rsplit("/", 1)[-1]


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


#: Long algebraic notation: two squares joined by a dash (``h7-h5``), after
#: the dashes are folded.  ``...h7—h5—h4`` is one token of it.
_LONG_NOTATION = re.compile(r"[a-h][1-8]-[a-h][1-8]")
_DASH_FOLD = str.maketrans({d: "-" for d in "‐‑‒–—―−"})


def _truncates_long_notation(anchor: str, other: str) -> bool:
    """``other`` is a proper piece of an anchor that holds long notation:
    ``h5–h4.`` for ``...h7—h5—h4.``, ``f4`` for ``f4—-f5``.  A reading that is
    supported *because* it is shorter (the glyph reader dropped the first
    square and the dash) is not a better reading of the same ink.
    """
    if not _B4.get():
        return False   # the guard is passo B4's too; the sabotage takes it away
    a = _fold(anchor.translate(_DASH_FOLD)).strip(_MARKS)
    b = _fold(other.translate(_DASH_FOLD)).strip(_MARKS)
    return bool(b) and b != a and b in a and _LONG_NOTATION.search(a) is not None


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
                    config: FusionConfig | None = None,
                    never_anchor: frozenset[str] = frozenset(),
                    letter_guarded: frozenset[str] = _LETTER_GUARDED) -> FusedRegion | None:
    """Fuse the candidates of one region.  ``None`` when there is nothing to fuse.

    The thin outer layer: it pins the passo B4 switch of ``config`` to this
    context (:data:`_B4`, read by the string helpers that take no config) and
    hands over to :func:`_fuse_candidates`, which holds the algorithm.
    """
    cfg = config or FusionConfig()
    token = _B4.set(cfg.passo_b4)
    try:
        return _fuse_candidates(candidates, lang=lang, image=image, config=cfg,
                                never_anchor=never_anchor, letter_guarded=letter_guarded)
    finally:
        _B4.reset(token)


def _fuse_candidates(candidates: Sequence[tuple[OcrResult, float, RegionDecision]], *,
                    lang: str = "", image: NDArray[np.uint8] | None = None,
                    config: FusionConfig | None = None,
                    never_anchor: frozenset[str] = frozenset(),
                    letter_guarded: frozenset[str] = _LETTER_GUARDED) -> FusedRegion | None:
    """Fuse the candidates of one region.  ``None`` when there is nothing to fuse.

    ``never_anchor`` names engines that only ever supply alternatives — the
    figurine reader, whose prose is worse than the line engines' and whose
    value is the tokens the anchor could not read.  ``letter_guarded`` names
    the secondary engines whose figurine may not replace a **piece letter of
    the book's language**: a model fine-tuned on figurines reads a printed
    ``N`` as ♘, and on a book that prints letters that is an invention.
    """
    cfg = config or FusionConfig()
    usable = [(r, s, d) for r, s, d in candidates if r.lines and r.text.strip()]
    if len(usable) < 2:
        return None
    rank = {Decision.ACCEPTED: 2, Decision.REVIEW: 1, Decision.ABSTAINED: 0}
    usable.sort(key=lambda c: (c[0].engine not in never_anchor, rank[c[2].decision], c[1]),
                reverse=True)
    if usable[0][0].engine in never_anchor:
        return None
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
                    Reading(name, other_word.text, other_word.confidence, other_word.box,
                            margin=getattr(other_word, "margin", None)))

    secondary = frozenset(_source_of(r) for r, _, _ in usable if r.engine in never_anchor)
    guarded = frozenset(_source_of(r) for r, _, _ in usable if r.engine in letter_guarded)
    piece_letters = _PIECE_LETTERS.get(langs[0] if langs else "", "")
    tokens: list[FusedToken] = []
    changed = 0
    disputed = 0
    for readings, (li, _, word) in zip(slots, slot_words, strict=True):
        line = anchor_result.lines[li]
        at_line_end = word is line.words[-1]
        chosen, alternative, is_disputed = _choose(
            readings, cfg, source_scores, langs, diacritic_lang, at_line_end, trusted,
            secondary=secondary, guarded=guarded, piece_letters=piece_letters)
        # A restyled reading (``2g5`` → ``2.g5``) matches its source by text
        # without the formatting; the source itself still counts as agreeing.
        agreeing = [r for r in readings if _fold(r.text) == _fold(chosen.text)
                    or r.source == chosen.source]
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
        if (anchor_decision.decision is Decision.ABSTAINED
                and decision.decision is Decision.ACCEPTED):
            # SOL-2: an anchor the arbiter abstained on is not certified by
            # the agreement of its alternatives.  Measured 2026-09-14 with a
            # second engine: 41 abstained move regions came out ACCEPTED at
            # CER 0,24 (``♘e4`` for ``37... ♘e4`` — right move, lost number).
            # Worth showing, not worth accepting: REVIEW, never more.
            decision = RegionDecision(
                Decision.REVIEW, decision.score, decision.accept_threshold,
                decision.review_threshold,
                decision.reasons_pt + ("o motor âncora se absteve; a fusão só pode "
                                       "propor, não aceitar.",),
                decision.evidence, decision.flagged_words, True, decision.legality)
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


def _supported(text: str, langs: tuple[str, ...]) -> bool:
    """A reading with lexical support: a move token or a dictionary word.

    A move keeps its support with a glued move number (``8.Kc2!``) and with
    an evaluation mark after it (``Bg6—+``): both are the printed form, and
    a candidate that lost the number or the dash must not outrank them.
    """
    core = text.strip(_MARKS + "()\"'—–")
    if not core:
        return False
    if not _B4.get() and any(dash in core for dash in "–—‒−"):
        return False   # the old alphabet: ``b2—b4`` was not a move
    if _MOVE_NUMBER.match(text.strip()):
        # A bare move number (``38``, ``36...``, ``12.``) is the printed form
        # too: a misaligned candidate must not turn it into a move (measured
        # 2026-09-14 with a second engine: ``38`` → ``g5`` is an invention).
        return True
    prefix = _NUMBER_PREFIX.match(core)
    # ``langs`` reaches the move test (passo B4): ``8c4`` and ``De2`` on an
    # English page are look-alikes, not support, and an anchor that has only
    # that for support is open to a supported alternative.
    # The sabotage switch also takes the language out of the move test: the
    # old ``is_move_token`` was the union of eight languages plus rank-only
    # tokens, so ``2c7`` counted as support and was never replaced.
    move_langs = langs if _B4.get() else ()
    if is_move_token(core, move_langs) or (
            prefix and is_move_token(core[prefix.end():].strip(_MARKS + "—–"), move_langs)):
        return True
    hit, judged = dictionary_hit_rate(core, langs)
    return bool(judged) and hit > 0


def _piece_letter_start(anchor: str, piece_letters: str) -> bool:
    """The anchor is a move that starts with a piece letter of the language
    (a glued move number allowed): ``Nf3``, ``22...Bf8`` in an English book.
    """
    prefix = _NUMBER_PREFIX.match(anchor)
    core = anchor[prefix.end():] if prefix else anchor
    return bool(core) and core[0] in piece_letters


def _keep_number_prefix(anchor: str, other: str) -> str:
    """``2.25`` replaced by ``2g5`` becomes ``2.g5``: the anchor's move-number
    formatting survives when the replacement carries the same digits bare;
    ``17...Ae5`` replaced by ``7...♘e5`` becomes ``17...♘e5`` (the glyph
    reader lost the first digit, the anchor kept it); a bracket the anchor
    opened (``(17...``) stays open.
    """
    lead = anchor[:len(anchor) - len(anchor.lstrip(_OPENERS))]
    anchor, other = anchor[len(lead):], other.lstrip(_OPENERS)
    prefix = _NUMBER_PREFIX.match(anchor)
    if not prefix:
        return lead + other
    digits = prefix.group(1)
    other_prefix = _NUMBER_PREFIX.match(other)
    if (other_prefix and other_prefix.group(1) != digits
            and digits.endswith(other_prefix.group(1))):
        return lead + prefix.group(0) + other[other_prefix.end():]
    if not prefix.group(0).rstrip(" ").endswith("."):
        return lead + other
    if other.startswith(digits) and len(other) > len(digits) and other[len(digits)] not in ". ":
        return lead + prefix.group(0).rstrip(" ") + other[len(digits):]
    return lead + other


def _restyled(anchor: Reading, chosen: Reading) -> Reading:
    text = _keep_number_prefix(anchor.text, chosen.text)
    return chosen if text == chosen.text else Reading(chosen.source, text, chosen.confidence, chosen.box)


def _figurine_fix(anchor: str, other: str) -> bool:
    """``other`` is ``anchor`` with a figurine where a Latin look-alike was."""
    return _figurine_cut(anchor, other) is not None


def _figurine_cut(anchor: str, other: str) -> int | None:
    """Length of the look-alike in ``anchor`` when ``other`` is its figurine form.

    The cipher shape: same move after the first character (one misread
    digit or letter tolerated, ``Hea!`` → ``♖e8!``), the alternative a move
    token, and the anchor *not* already a figurine.
    """
    # ``(17...2c7`` and ``(17...♗c7``: a bracket the page opened before the
    # move is not part of the cipher (passo B4).
    if _B4.get():
        anchor, other = anchor.lstrip(_OPENERS), other.lstrip(_OPENERS)
    # ``22...♗f8`` and ``22...28``: a move number glued to the move is the
    # same cipher one prefix later.  Both must carry a prefix, and the
    # secondary's digits must be the anchor's or a suffix of them (``17...``
    # against ``7...``: the glyph reader lost the first digit, not the move).
    prefix_a = _NUMBER_PREFIX.match(anchor)
    prefix_b = _NUMBER_PREFIX.match(other)
    if (prefix_a is None) != (prefix_b is None):
        return None
    if prefix_a is not None and prefix_b is not None:
        same = (prefix_a.group(1).endswith(prefix_b.group(1)) if _B4.get()
                else prefix_a.group(1) == prefix_b.group(1))
        if not same:
            return None
        anchor, other = anchor[prefix_a.end():], other[prefix_b.end():]
    if not other or other[0] not in _FIGURINES or not anchor or anchor[0] in _FIGURINES:
        return None
    if anchor[0] in "abcdefgh":
        # A pawn move (``e4``) is not a cipher: the look-alikes of figurines
        # are capitals, symbols and digits, never a file letter.
        return None
    if not is_move_token(other.strip(_MARKS)) or len(anchor) < 2:
        return None
    tail_b = other[1:].rstrip(_MARKS)
    if not tail_b:
        return None
    # The look-alike is normally one character (Tesseract: ``H`` for ♖).  A
    # damaged text layer leaves a *cluster* instead — ``'it>d1`` for ♔d1,
    # ``ll:'ixe5`` for ♕xe5 — consistent per figurine but several characters
    # long (OCR_UI_ROADMAP passo 3: 15 % of the Gaprindashvili's moves after
    # every one-character symbol was resolved).  Such a prefix qualifies when
    # it is short, carries a non-alphanumeric character (a word never does)
    # and leaves the same move body behind; a plain run of letters does not,
    # so a real word glued to a square stays out.
    for cut in range(1, min(len(anchor) - 1, _MAX_CLUSTER) + 1):
        prefix = anchor[:cut]
        if cut > 1 and all(ch.isalnum() for ch in prefix):
            continue
        tail_a = anchor[cut:].rstrip(_MARKS)
        if tail_a and abs(len(tail_a) - len(tail_b)) <= 1 and levenshtein(tail_a, tail_b) <= 1:
            return cut
    return None


def _margin_clears(reading: Reading, cfg: FusionConfig) -> bool:
    """A reading without a margin is judged on confidence alone; one with a
    margin (the glyph reader's) must clear ``figurine_min_margin`` too.
    """
    return reading.margin is None or reading.margin >= cfg.figurine_min_margin


def _independent_agreement(readings: Sequence[Reading], secondary: frozenset[str],
                           langs: tuple[str, ...], cfg: FusionConfig) -> Reading | None:
    """The reading two secondary sources of *different engines* agree on,
    when it is a supported token they both read confidently; else ``None``.
    """
    groups: dict[str, list[Reading]] = {}
    for reading in readings[1:]:
        if (reading.source in secondary and reading.confidence >= cfg.figurine_min_confidence
                and _margin_clears(reading, cfg)):
            groups.setdefault(_fold(reading.text.rstrip(_MARKS)), []).append(reading)
    anchor_key = _fold(readings[0].text.rstrip(_MARKS))
    for key, group in groups.items():
        if key == anchor_key or len({reading.engine for reading in group}) < 2:
            continue
        best = max(group, key=lambda reading: reading.confidence)
        if _supported(best.text, langs):
            return best
    return None


def _choose(readings: Sequence[Reading], cfg: FusionConfig, source_scores: dict[str, float],
            langs: tuple[str, ...], diacritic_lang: bool, at_line_end: bool,
            trusted: bool, *, secondary: frozenset[str] = frozenset(),
            guarded: frozenset[str] = frozenset(), piece_letters: str = ""
            ) -> tuple[Reading, str, bool]:
    anchor = readings[0]
    if trusted or len(readings) == 1:
        return anchor, "", False

    # A glyph source's figurine, where the anchor has the look-alike: the
    # one replacement a secondary source may make on its own evidence.  A
    # reading that carries the classifier's margin must clear it too.
    for reading in readings[1:]:
        if (reading.source in secondary and reading.confidence >= cfg.figurine_min_confidence
                and _margin_clears(reading, cfg)
                and _figurine_fix(anchor.text, reading.text)
                and not (reading.source in guarded
                         and _piece_letter_start(anchor.text, piece_letters))):
            return _restyled(anchor, reading), anchor.text, False

    # Two independent secondary sources (different engines) that agree on a
    # supported reading outweigh an anchor that barely read its own token
    # (passo B4): ``e5`` at 0,21 against ``♘e5`` from the glyph reader and
    # from the figurine model.  Never over a piece letter of the language.
    if cfg.passo_b4 and anchor.confidence < cfg.weak_anchor_confidence and not _piece_letter_start(
            anchor.text, piece_letters):
        agreed = _independent_agreement(readings, secondary, langs, cfg)
        if agreed is not None:
            return _restyled(anchor, agreed), anchor.text, False

    primary = [r for r in readings if r.source not in secondary]
    distinct: dict[str, list[Reading]] = {}
    for reading in primary:
        distinct.setdefault(reading.text, []).append(reading)
    if len(distinct) == 1:
        # Only glyph readings differ.  They may still replace a nonword the
        # anchor doubted (below), but never restyle a token the primaries agree on.
        extra = [r for r in readings if r.source in secondary
                 and _fold(r.text.rstrip(_MARKS)) != _fold(anchor.text.rstrip(_MARKS))]
        if not extra or _supported(anchor.text, langs) \
                or anchor.confidence >= cfg.anchor_trust_confidence:
            return anchor, "", False
        for reading in extra:
            # Judged in the anchor's numbering (``2g5`` under ``2.25`` is
            # ``2.g5``, a move; a bare ``2g5`` is a rank with no piece), and
            # a glyph reading with a thin margin is no evidence here either.
            if (_supported(_keep_number_prefix(anchor.text, reading.text), langs)
                    and reading.confidence >= anchor.confidence - 0.10
                    and _margin_clears(reading, cfg)
                    and not _truncates_long_notation(anchor.text, reading.text)):
                return _restyled(anchor, reading), anchor.text, False
        return anchor, extra[0].text, True

    def score_of(text: str, group: list[Reading]) -> float:
        base = max(cfg.source_weight * source_scores.get(r.source, 0.0)
                   + (1.0 - cfg.source_weight) * r.confidence for r in group)
        base += 0.10 * (len(group) - 1)
        if diacritic_lang and _has_diacritics(text) and all(
                _fold(t) == _fold(text) for t in distinct):
            base += cfg.diacritic_bonus
        if text and text[-1] in ".,;:!?" and any(
                _fold(t.rstrip(".,;:!?")) == _fold(text.rstrip(".,;:!?")) and t != text
                for t in distinct):
            base += cfg.punctuation_bonus
        if at_line_end and text.endswith("-"):
            base += cfg.hyphen_bonus
        return base

    scored = sorted(((score_of(t, g), t, g[0]) for t, g in distinct.items()),
                    key=lambda s: (-s[0], s[1] != anchor.text, s[1]))
    anchor_score = next(sc for sc, t, _ in scored if t == anchor.text)
    others = [(sc, t, r) for sc, t, r in scored if t != anchor.text]

    # Readings that differ only in diacritics, case or a trailing mark are
    # exactly what the specific preferences decide; they are not a dispute.
    if len({_fold(t.rstrip(".,;:!?-")) for t in distinct}) == 1:
        best_score, best_text, best_reading = scored[0]
        if best_text != anchor.text:
            return best_reading, anchor.text, False
        return anchor, others[0][1] if others else "", False

    anchor_known = (_supported(anchor.text, langs)
                    or anchor.confidence >= cfg.anchor_trust_confidence)
    if anchor_known:
        # Never replaced.  A supported alternative that is also clearly more
        # confident is a dispute for the reviewer, nothing more.
        for sc, text, _ in others:
            if _supported(text, langs) and sc - anchor_score >= cfg.dispute_margin:
                return anchor, text, True
        return anchor, "", False

    # The anchor is a nonword the engine itself doubted: a supported, at
    # least as confident alternative may replace it.
    candidates = [(sc, t, r) for sc, t, r in others
                  if _supported(_keep_number_prefix(anchor.text, t), langs)
                  and r.confidence >= anchor.confidence - 0.10
                  and not _truncates_long_notation(anchor.text, t)]
    if not candidates:
        return anchor, others[0][1] if others else "", bool(others)
    best_score, best_text, best_reading = candidates[0]
    if best_score - anchor_score < cfg.dispute_margin:
        return anchor, best_text, True
    return _restyled(anchor, best_reading), anchor.text, False


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

