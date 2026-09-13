"""Tesseract profiles for prose and for movetext — Sol §SOL-7.

One configuration cannot serve both halves of a chess book.  Prose wants
Tesseract's language model at full strength: the dictionary DAWGs that turn
``tbe`` into ``the`` are right almost every time on running text.  Movetext
is the opposite case: ``Nf3`` is not in any dictionary, ``exd5`` looks like
a typo of nothing, and the same DAWGs that rescue prose "correct" a move
into a word.  So there are two profiles, chosen by the region kind the
layout analyser assigned, and a third, *strict* one that is only ever an
extra candidate for token fusion, never the sole reading of a region.

``PROSE``
    Tesseract's DAWGs on, plus a ``user_words`` list of the editorial and
    chess vocabulary of the language (names of players and openings, the
    words a chess book uses that a general dictionary lacks) and
    ``user_patterns`` for the move numbers and moves that prose quotes
    inline.

``MOVETEXT``
    The system and frequency DAWGs *off* — this is the one place Sol
    allows it — with ``user_words`` reduced to the chess vocabulary and
    ``user_patterns`` covering SAN, LAN, castling, results, move numbers,
    promotion and annotation marks.  Punctuation, comments and NAGs stay
    readable: there is no whitelist here.

``MOVETEXT_STRICT``
    Same, with a character whitelist limited to what notation is made of.
    A comment inside a move list would be mangled by it, which is why it
    is an *additional candidate* (§SOL-7, "whitelist limitada somente em
    candidatos adicionais de movetext"): fusion takes its reading for a
    move token when it wins on the evidence and ignores it elsewhere.

The word and pattern files are written once per process into a temporary
directory and handed to Tesseract by path; the profile records what it
wrote so the result's metadata can say so.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ..lexicon import _NAMES, _RAW_LEXICONS, normalise_lang
from ..types import RegionKind

__all__ = ["ProfileConfig", "ProfileFiles", "TesseractProfile", "profile_for"]


class TesseractProfile(StrEnum):
    PROSE = "prose"
    MOVETEXT = "movetext"
    MOVETEXT_STRICT = "movetext_strict"


def profile_for(kind: RegionKind) -> TesseractProfile:
    return TesseractProfile.MOVETEXT if kind is RegionKind.MOVETEXT else TesseractProfile.PROSE


#: Tesseract ``user_patterns`` syntax: ``\d`` digit, ``\a`` lowercase letter,
#: ``\A`` uppercase letter, ``\n`` alphanumeric, ``\p`` punctuation, ``\*``
#: repeat the previous class.  Literal characters stand for themselves.
MOVE_PATTERNS: tuple[str, ...] = (
    # move numbers
    r"\d.", r"\d\d.", r"\d\d\d.", r"\d...", r"\d\d...", r"\d\d\d...",
    # pawn moves, captures, promotion
    r"\a\d", r"\a\d+", r"\a\d#", r"\ax\a\d", r"\ax\a\d+", r"\a\d=\A", r"\ax\a\d=\A",
    r"\a\d=\A+", r"\a\d-\a\d",
    # piece moves with optional disambiguation and capture
    r"\A\a\d", r"\A\a\d+", r"\A\a\d#", r"\Ax\a\d", r"\Ax\a\d+", r"\Ax\a\d#",
    r"\A\a\a\d", r"\A\ax\a\d", r"\A\d\a\d", r"\A\dx\a\d", r"\A\a\d-\a\d",
    r"\A\a\d-\a\d+", r"\A\a\d:\a\d",
    # annotations
    r"\A\a\d!", r"\A\a\d?", r"\A\a\d!!", r"\A\a\d!?", r"\A\a\d?!", r"\A\a\d??",
    r"\a\d!", r"\a\d?", r"\a\d!!", r"\a\d!?", r"\a\d?!", r"\Ax\a\d!", r"\ax\a\d!",
    r"\A\a\d+!", r"\A\a\d+?",
    # castling and results
    "O-O", "O-O-O", "O-O+", "O-O-O+", "0-0", "0-0-0", "1-0", "0-1", "1/2-1/2", "½-½",
)

#: Editorial words that every chess book uses and no general dictionary
#: carries; the per-language lists in ``caissa/ocr/data/lexicon`` add the
#: language's own.
EDITORIAL_WORDS: tuple[str, ...] = (
    "Nf3", "Nc3", "Bb5", "Qd2", "Rd1", "Kg1", "exd5", "O-O", "O-O-O",
    "ECO", "FIDE", "Elo", "PGN", "FEN", "NAG",
)

#: Characters notation is made of — the strict candidate's whitelist.
STRICT_WHITELIST = ("0123456789abcdefghKQRBNPDTCSAFLxX+#=-.!?/½O:() "
                    "КФЛСКПРrdtcafgpbnÑ")


@dataclass(slots=True)
class ProfileConfig:
    #: Sol §SOL-7 allows turning the DAWGs off only for movetext.
    disable_dawgs_for_movetext: bool = True
    #: Include the names list (players, cities, events) in the prose words.
    names_in_prose: bool = True
    #: Whether the service adds the strict candidate on movetext regions.
    strict_candidate: bool = True


@dataclass(slots=True)
class ProfileFiles:
    """Writes and caches the word and pattern files per (profile, language)."""

    config: ProfileConfig = field(default_factory=ProfileConfig)
    directory: Path | None = None
    _written: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)

    def _dir(self) -> Path:
        if self.directory is None:
            self.directory = Path(tempfile.mkdtemp(prefix="caissa-tess-profiles-"))
            atexit.register(shutil.rmtree, self.directory, True)
        return self.directory

    def words_for(self, profile: TesseractProfile, lang: str) -> list[str]:
        codes = normalise_lang(lang) or ("por", "eng")
        words: set[str] = set(EDITORIAL_WORDS)
        for code in codes:
            raw = _RAW_LEXICONS.get(code, "")
            if profile is TesseractProfile.PROSE:
                words.update(raw.split())
            else:
                # Only the chess vocabulary of the language: the tail of each
                # list, after the function words (see tools/lexicon_authored).
                words.update(w for w in raw.split() if len(w) >= 4)
        if profile is TesseractProfile.PROSE and self.config.names_in_prose:
            words.update(_NAMES)
        return sorted(words)

    def parameters(self, profile: TesseractProfile, lang: str) -> dict[str, str]:
        """The ``-c key=value`` pairs for ``profile`` and ``lang``."""
        key = (str(profile), lang)
        if key in self._written:
            return dict(self._written[key])
        directory = self._dir()
        stem = f"{profile}_{lang.replace('+', '_')}"
        words_path = directory / f"{stem}.user-words"
        patterns_path = directory / f"{stem}.user-patterns"
        words_path.write_text("\n".join(self.words_for(profile, lang)) + "\n", encoding="utf-8")
        patterns_path.write_text("\n".join(MOVE_PATTERNS) + "\n", encoding="utf-8")
        params: dict[str, str] = {
            "user_words_file": str(words_path),
            "user_patterns_file": str(patterns_path),
        }
        if profile is not TesseractProfile.PROSE:
            params["preserve_interword_spaces"] = "1"
            if self.config.disable_dawgs_for_movetext:
                params["load_system_dawg"] = "0"
                params["load_freq_dawg"] = "0"
        if profile is TesseractProfile.MOVETEXT_STRICT:
            params["tessedit_char_whitelist"] = STRICT_WHITELIST
        self._written[key] = params
        return dict(params)
