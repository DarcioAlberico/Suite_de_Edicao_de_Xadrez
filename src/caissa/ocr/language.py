"""Language of the prose, convention of the notation — Sol §SOL-7.

Two different questions with two different answers.  A Brazilian edition of
a Russian book has Portuguese prose and may keep ``Кf3`` in its diagrams'
solutions; an English translation of Dvoretsky has English prose and
figurine notation; a German book of the 1950s has German prose and ``Sf3``.
The prose language chooses the OCR model and the dictionary; the notation
convention chooses the piece letters the legality replay tries first.  So
they are detected separately and reported separately.

The prose detector is deliberately simple: the script of the letters first
(Cyrillic is Russian here; nothing else Cyrillic is in the corpus), then the
dictionary hit rate of each supported language over the same tokens.  It
abstains below a margin, and an abstention means "keep the caller's hint",
never "guess the first in the list".  The notation detector is
:func:`caissa.notation.languages.detect_language`, which already replays
piece letters against every locale and says when it cannot tell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .lexicon import (
    SUPPORTED_LANGUAGES,
    dictionary_hit_rate,
    normalise_lang,
    script_profile,
    tokenize,
)

__all__ = [
    "LanguageGuess",
    "NotationGuess",
    "detect_notation_convention",
    "detect_prose_language",
    "document_language",
]

#: OCR codes → notation locale codes, the vocabulary of :mod:`caissa.notation`.
_TO_LOCALE = {"eng": "en", "por": "pt", "spa": "es", "fra": "fr", "ita": "it",
              "deu": "de", "nld": "nl", "rus": "ru"}
_MIN_TOKENS = 12
_MARGIN = 0.08


@dataclass(frozen=True, slots=True)
class LanguageGuess:
    lang: str                 # ISO-639-2 as :mod:`caissa.ocr` speaks it, "" when abstained
    confidence: float
    scores: dict[str, float]
    tokens: int
    reason_pt: str

    @property
    def abstained(self) -> bool:
        return not self.lang


@dataclass(frozen=True, slots=True)
class NotationGuess:
    locale: str | None        # "en", "pt", "de", ...; None when abstained
    confidence: float
    ranked: tuple[tuple[str, float], ...]
    reason_pt: str

    @property
    def abstained(self) -> bool:
        return self.locale is None


def detect_prose_language(text: str, *, candidates: Iterable[str] = SUPPORTED_LANGUAGES,
                          hint: str = "") -> LanguageGuess:
    """The language of ``text``'s prose, or an abstention."""
    tokens = [t for t in tokenize(text or "") if len(t) >= 2 and any(c.isalpha() for c in t)]
    if len(tokens) < _MIN_TOKENS:
        return LanguageGuess("", 0.0, {}, len(tokens),
                             f"apenas {len(tokens)} palavra(s): poucas para decidir o idioma")
    profile = script_profile(text)
    letters = sum(profile.values()) or 1
    if profile.get("cyrillic", 0) / letters > 0.5:
        return LanguageGuess("rus", min(1.0, profile["cyrillic"] / letters), {"rus": 1.0},
                             len(tokens), "alfabeto cirílico predominante")
    scores: dict[str, float] = {}
    for code in candidates:
        if code == "rus":
            continue
        rate, judged = dictionary_hit_rate(text, (code,))
        if judged >= _MIN_TOKENS:
            scores[code] = rate
    if not scores:
        return LanguageGuess("", 0.0, {}, len(tokens), "nenhum idioma pôde ser julgado")
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best, second = ordered[0], (ordered[1] if len(ordered) > 1 else (None, 0.0))
    margin = best[1] - second[1]
    hinted = normalise_lang(hint)
    if margin < _MARGIN:
        if hinted and hinted[0] in scores and best[1] - scores[hinted[0]] < _MARGIN:
            return LanguageGuess(hinted[0], best[1], scores, len(tokens),
                                 f"empate entre {best[0]} e {second[0]}; mantida a dica "
                                 f"{hinted[0]}")
        return LanguageGuess("", best[1], scores, len(tokens),
                             f"empate entre {best[0]} ({best[1]:.2f}) e {second[0]} "
                             f"({second[1]:.2f})")
    return LanguageGuess(best[0], best[1], scores, len(tokens),
                         f"{best[0]} com {best[1]:.0%} de palavras conhecidas, "
                         f"{margin:.2f} acima do segundo")


def document_language(page_texts: Iterable[str], *, hint: str = "") -> LanguageGuess:
    """The document's prose language from a sample of its pages."""
    joined = "\n".join(t for t in page_texts if t)
    return detect_prose_language(joined[:200_000], hint=hint)


def detect_notation_convention(text: str, *, prose_lang: str = "") -> NotationGuess:
    """The piece-letter convention of the moves in ``text``."""
    from caissa.notation.languages import detect_language

    detection = detect_language(text or "")
    ranked = tuple((s.code, float(s.score)) for s in detection.ranked)
    if detection.abstained or not detection.ranked:
        prior = _TO_LOCALE.get(normalise_lang(prose_lang)[0], "") if normalise_lang(
            prose_lang) else ""
        return NotationGuess(None, 0.0, ranked,
                             f"{detection.reason}" + (f"; a prosa sugere {prior}" if prior else ""))
    best = detection.ranked[0]
    return NotationGuess(best.code, float(best.score), ranked, detection.reason)
