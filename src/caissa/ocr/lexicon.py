"""A multilingual lexicon plus a character n-gram model.

Two questions recur across this package and both need the same data:

* *Is this string real language, or is it garbage that merely has the shape of
  language?*  Asked by :mod:`caissa.ocr.engines.pdf_text_layer` about a PDF's
  own text layer with a broken ``ToUnicode``, and by :mod:`caissa.ocr.quality`
  about OCR output when no ground truth exists.
* *Which of two engine outputs is more plausible?*  Asked by
  :mod:`caissa.ocr.arbiter`.

There are two sources, and the difference between them is worth stating plainly
because it changes every threshold downstream.

**The embedded core** is the ~150 most frequent words of each supported
language, written out below as literals.  It is thin as a spell checker, but
this code never needs to *validate* a word — it needs to tell 50 % coverage
from 2 %, which is the gap between real text and a substitution cipher of real
text.  A broken CMap is exactly a substitution cipher: the letter frequencies
still look plausible, and only the words give it away.  The core ships with the
source, needs no data file, and makes a clean checkout work.

**The trunk's lists**, when this machine has them, add 164,723 words:
``acervo.txt.gz`` (the editorial text layer of the corpus's own non-OCR books),
``idioma.txt.gz`` and ``nomes.txt.gz`` (players, cities, tournaments).  With
them the hit rate on clean prose roughly doubles, which widens the gap this
module exists to measure.

Origem: ChessVisionOFF_Puro/assets/lexico/ (built by ``cvoff-texto-lexico``,
read by ``src/chess_diagram_ocr/text/lexico.py``).  Absorvido em 2026-09-07.
Alterações: the files are **read where they are**, never copied into this
repository.  Two reasons, both in the trunk's own
``assets/lexico/PROCEDENCIA.md``: ``idioma.txt.gz`` has no declared origin, and
``nomes.txt.gz`` is in part an extract of a commercial player index — the trunk
records that its licence has not been cleared, and copying it here would be
this project asserting a clearance nobody has made.  The corpus rule applies
unchanged: local material stays local.  Point ``CAISSA_LEXICON_DIR`` at the
folder to move it; leave it unset and the embedded core is used alone.

Chess prose is not ordinary prose, so notation is recognised separately and
excluded from the denominator.  Without that, a page of pure move text scores
as garbage and a perfectly good text layer gets thrown away.
"""

from __future__ import annotations

import gzip
import logging
import math
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hunspell import HunspellDictionary

__all__ = [
    "SUPPORTED_LANGUAGES",
    "LANGUAGE_ALIASES",
    "EXTERNAL_LEXICON_FILES",
    "external_lexicon_dir",
    "external_lexicon",
    "book_lexicon",
    "packaged_manifest",
    "lexicon_source",
    "reset_lexicon_cache",
    "normalise_lang",
    "lexicon_for",
    "tokenize",
    "is_chess_notation",
    "dictionary_hit_rate",
    "ngram_log_probability",
    "ngram_plausibility",
    "modelled_script_share",
    "MODELLED_SCRIPT",
    "script_profile",
    "implausible_char_ratio",
    "nonword_ratio",
    "NOTATION_ALPHABET",
    "is_move_token",
    "is_mangled_move",
    "mangled_move_ratio",
]


# --------------------------------------------------------------------------- #
# Word lists
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# The packaged lists — Sol §SOL-9
# --------------------------------------------------------------------------- #

#: Where the versioned word lists live: one file per language plus
#: ``names.txt`` (players, authors, cities, publishers, events) and a
#: ``MANIFEST.json`` with the origin, licence, word count and SHA-256 of
#: each.  They replaced the literals that used to sit in this module so the
#: lists are data with provenance rather than code, and so every run can
#: record the hash of exactly what it used.
_DATA_PACKAGE = "caissa.ocr.data.lexicon"


def _packaged_text(name: str) -> str:
    from importlib import resources

    try:
        return resources.files(_DATA_PACKAGE).joinpath(name).read_text("utf-8")
    except (FileNotFoundError, OSError, ModuleNotFoundError):
        return ""


def _packaged_words(name: str) -> list[str]:
    return [line.strip() for line in _packaged_text(name).splitlines()
            if line.strip() and not line.startswith("#")]


@lru_cache(maxsize=1)
def packaged_manifest() -> dict[str, object]:
    """The ``MANIFEST.json`` of the packaged lists (empty when absent)."""
    import json

    text = _packaged_text("MANIFEST.json")
    try:
        return dict(json.loads(text)) if text else {}
    except ValueError:
        return {}


_LANGUAGE_FILES: dict[str, str] = {
    "por": "por.txt", "eng": "eng.txt", "deu": "deu.txt", "spa": "spa.txt",
    "fra": "fra.txt", "ita": "ita.txt", "nld": "nld.txt", "rus": "rus.txt",
}

#: language code -> its words, one string per language as the n-gram model
#: and the reference scores below expect.  Proper nouns (``names.txt``) are
#: deliberately *not* here: they are looked up, never modelled — training the
#: letter statistics on Slavic and Hungarian surnames is what the model must
#: not do (see :func:`reset_lexicon_cache`).
_RAW_LEXICONS: dict[str, str] = {
    code: " ".join(_packaged_words(name)) for code, name in _LANGUAGE_FILES.items()
}
_NAMES: frozenset[str] = frozenset(_packaged_words("names.txt"))


def _packaged_dictionary(code: str) -> "HunspellDictionary | None":
    """The licensed Hunspell dictionary packaged for ``code``, or ``None``.
    Loaded once, on first lookup, so importing this module stays cheap."""
    from .hunspell import load_packaged_dictionary

    return load_packaged_dictionary(code)


SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(sorted(_RAW_LEXICONS))

#: Accept ISO-639-1, common Tesseract codes and a few informal spellings.
LANGUAGE_ALIASES: dict[str, str] = {
    "pt": "por", "pt_br": "por", "pt-br": "por", "ptbr": "por", "por": "por",
    "en": "eng", "en_us": "eng", "en-gb": "eng", "eng": "eng",
    "de": "deu", "ger": "deu", "deu": "deu",
    "es": "spa", "esp": "spa", "spa": "spa",
    "fr": "fra", "fre": "fra", "fra": "fra",
    "it": "ita", "ita": "ita",
    "nl": "nld", "dut": "nld", "nld": "nld",
    "ru": "rus", "rus": "rus",
}


def normalise_lang(lang: str) -> tuple[str, ...]:
    """Turn ``"por+eng"`` or ``"pt-BR"`` into a tuple of internal codes.

    Unknown codes are dropped rather than guessed at; an empty result means
    "use every language", which is the right default for a page whose language
    has not been detected yet.
    """
    out: list[str] = []
    for part in re.split(r"[+,;/\s]+", (lang or "").strip().lower()):
        if not part:
            continue
        code = LANGUAGE_ALIASES.get(part)
        if code and code not in out:
            out.append(code)
    return tuple(out)


# --------------------------------------------------------------------------- #
# The trunk's word lists, read in place
# --------------------------------------------------------------------------- #

LOGGER = logging.getLogger("caissa.ocr.lexicon")

#: Sol §SOL-9 removed the absolute default path to the trunk's
#: ``assets/lexico``: a clean install must reproduce the same linguistic
#: scores as this machine, and it cannot if this machine silently reads
#: 164,723 extra words from a sibling checkout.  The trunk's lists are still
#: usable — point ``CAISSA_LEXICON_DIR`` at them — and when they are, their
#: hashes go into :func:`lexicon_source` so the run says what it used.

#: file -> whether it is loaded by default.  ``nomes`` carries 150k proper
#: nouns; it is on because chess prose is dense with player and place names and
#: judging those "not a word" is what made a good page look like garbage.
EXTERNAL_LEXICON_FILES: dict[str, bool] = {
    "acervo.txt.gz": True,
    "idioma.txt.gz": True,
    "nomes.txt.gz": True,
}


def external_lexicon_dir() -> Path | None:
    """Where the trunk's lists are, or ``None``."""
    raw = os.environ.get("CAISSA_LEXICON_DIR")
    if not raw:
        return None
    candidate = Path(raw)
    return candidate if candidate.is_dir() else None


@lru_cache(maxsize=1)
def external_lexicon() -> frozenset[str]:
    """The trunk's word lists, case-folded; empty when they are not present.

    A missing or unreadable file is a fact to report at DEBUG and carry on
    with, never an exception: the embedded core is a working fallback and a
    batch of 500 books must not stop because a sibling checkout moved.
    """
    directory = external_lexicon_dir()
    if directory is None:
        return frozenset()
    words: set[str] = set()
    for name, wanted in EXTERNAL_LEXICON_FILES.items():
        if not wanted:
            continue
        path = directory / name
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    token = line.strip()
                    if token:
                        words.add(token.casefold())
        except (OSError, EOFError, gzip.BadGzipFile) as exc:
            LOGGER.debug("lista de palavras '%s' não pôde ser lida: %s",
                         path, exc)
    return frozenset(words)


def lexicon_source() -> dict[str, object]:
    """What the lexicon is actually made of, for the report and the UI.

    Sol §SOL-9: includes the version and SHA-256 of every packaged file and
    of every external file read, so two runs can be compared on what they
    looked words up in, not on what they hoped they did.
    """
    import hashlib

    external = external_lexicon()
    embedded = frozenset(
        word for raw in _RAW_LEXICONS.values() for word in raw.split())
    dictionaries = {code: len(d) for code in SUPPORTED_LANGUAGES
                    if (d := _packaged_dictionary(code)) is not None}
    directory = external_lexicon_dir()
    manifest = packaged_manifest()
    external_hashes: dict[str, str] = {}
    if directory is not None:
        for name, wanted in EXTERNAL_LEXICON_FILES.items():
            path = directory / name
            if wanted and path.is_file():
                external_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return {
        "embedded_words": len(embedded),
        "names": len(_NAMES),
        "external_words": len(external),
        "external_dir": str(directory) if directory else None,
        "external_files": tuple(
            name for name, wanted in EXTERNAL_LEXICON_FILES.items() if wanted),
        "external_hashes": external_hashes,
        "packaged_version": manifest.get("version"),
        "packaged_files": {
            name: {"sha256": str(info.get("sha256", ""))[:16], "words": info.get("words")}
            for name, info in dict(manifest.get("files", {})).items()
        } if isinstance(manifest.get("files"), dict) else {},
        "dictionaries": dictionaries,
        "total_words": len(embedded | external | _NAMES) + sum(dictionaries.values()),
        "book_words": len(_book_words()),
    }


def reset_lexicon_cache() -> None:
    """Forget every cached word set — for tests, and after a path change.

    The character n-gram model is deliberately *not* reset: it is built from
    the embedded literals alone and must stay that way.  Training it on the
    trunk's 350,000 proper nouns would teach it the letter statistics of Slavic
    and Hungarian surnames, and the whole point of the n-gram term is to be a
    signal that does not move when the word list does.
    """
    external_lexicon.cache_clear()
    lexicon_for.cache_clear()
    _folded_lexicon.cache_clear()
    _dictionaries_for.cache_clear()


@lru_cache(maxsize=64)
def lexicon_for(langs: tuple[str, ...]) -> frozenset[str]:
    """Union of the word lists for ``langs``; all languages when empty.

    The trunk's lists are not tagged by language and are added whole.  That is
    correct for the question this module answers — "is this real text?" — and
    would be wrong for language *identification*, which is why nothing here
    claims to do that.
    """
    codes = langs or SUPPORTED_LANGUAGES
    words: set[str] = set()
    for code in codes:
        raw = _RAW_LEXICONS.get(code)
        if raw:
            words.update(raw.split())
    return frozenset(words) | _NAMES | external_lexicon()


@lru_cache(maxsize=64)
def _dictionaries_for(langs: tuple[str, ...]) -> tuple["HunspellDictionary", ...]:
    """The packaged Hunspell dictionaries of ``langs`` (all when empty)."""
    codes = langs or SUPPORTED_LANGUAGES
    found = [_packaged_dictionary(code) for code in codes]
    return tuple(d for d in found if d is not None)


# --------------------------------------------------------------------------- #
# Per-book lexicon — Sol §SOL-9
# --------------------------------------------------------------------------- #

import contextlib as _contextlib
import contextvars as _contextvars
from collections.abc import Iterable as _Iterable
from collections.abc import Iterator as _Iterator

_BOOK: _contextvars.ContextVar[frozenset[str]] = _contextvars.ContextVar(
    "caissa_book_lexicon", default=frozenset())


def _book_words() -> frozenset[str]:
    return _BOOK.get()


@_contextlib.contextmanager
def book_lexicon(words: _Iterable[str]) -> _Iterator[None]:
    """Words known to be in *this* book — a player index, a glossary — that
    count as dictionary hits while the block runs and vanish after it.

    A context variable rather than a global, so a batch importing two books
    in two threads cannot leak one book's names into the other's scores.
    """
    token = _BOOK.set(frozenset(_fold(w) for w in words if w.strip()))
    try:
        yield
    finally:
        _BOOK.reset(token)


# --------------------------------------------------------------------------- #
# Tokenisation and chess notation
# --------------------------------------------------------------------------- #

#: A token is a maximal run of letters, digits and the few marks that belong
#: inside chess notation.  Splitting on whitespace alone leaves punctuation
#: glued to words and depresses the dictionary hit rate on clean text.
_TOKEN = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*|[^\s\w]+", re.UNICODE)

#: Piece letters in the eight supported languages, plus the Unicode figurines
#: a born-digital book may use directly (U+2654..U+265F).  Named rather than
#: inlined because :func:`is_mangled_move` has to know *exactly* the same set:
#: two tables that agree by coincidence rather than by construction is the
#: twelfth blind gate this project found (docs/ROADMAP.md).
_PIECE_LETTERS = ("KQRBNPCDTSAFLGVWМКФЛСКПРrdtcafgpb"
                  + "".join(chr(c) for c in range(0x2654, 0x2660)))
#: Piece letters a pawn may promote to — no king, no pawn.
_PROMOTION_LETTERS = "KQRBNCDTSAFLGVW"
_FILES = "a-h"
_RANKS = "1-8"
#: Capture and move-link marks.  ``:`` is German/Russian capture.  The ``-``
#: is last so the string stays safe to interpolate into a character class.
_LINK_MARKS = "x:×-"
#: Promotion is written ``=Q``; the ``=`` is part of notation's alphabet.
_PROMOTION_MARK = "="
#: Annotation marks.  They only ever *trail* a move, which is what makes a
#: leading ``!`` in ``!txg7`` evidence of damage rather than of annotation.
_ANNOTATION_MARKS = "+#!?"

#: SAN / LAN / figurine notation in the eight supported languages, plus move
#: numbers, castling, results and evaluation symbols.  Anything matching this
#: is real chess text and must not count against the dictionary hit rate.
_NOTATION = re.compile(
    rf"""^(?:
        [{_PIECE_LETTERS}]?[{_FILES}]?[{_RANKS}]?[{_LINK_MARKS}]?[{_FILES}][{_RANKS}]
            (?:{_PROMOTION_MARK}[{_PROMOTION_LETTERS}])?[{_ANNOTATION_MARKS}]{{0,2}}
      | [OO0]-[OO0](?:-[OO0])?[{_ANNOTATION_MARKS}]{{0,2}}
      | \d{{1,3}}\.{{1,3}}
      | 1-0 | 0-1 | 1/2-1/2 | ½-½
      | [+=−±∓+-]{{1,2}}
      | [KQRBNP]\d?
    )$""",
    re.VERBOSE | re.UNICODE,
)


def tokenize(text: str) -> list[str]:
    """Split into word-ish tokens, keeping the original case."""
    return _TOKEN.findall(text or "")


def is_chess_notation(token: str) -> bool:
    """True for a token that is chess notation rather than a word."""
    if not token:
        return False
    if token.isdigit():
        return True
    return bool(_NOTATION.match(token))


def _fold(token: str) -> str:
    """Lower-case and strip accents, for lexicon lookup only."""
    lowered = token.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped


@lru_cache(maxsize=64)
def _folded_lexicon(langs: tuple[str, ...]) -> frozenset[str]:
    return frozenset(_fold(w) for w in lexicon_for(langs))


#: Pre-reform spellings, applied only when the direct lookup fails.  Each is
#: one-directional and conservative: the folded form must itself be a word.
_HISTORICAL = (
    ("ph", "f"), ("th", "t"), ("rh", "r"), ("mm", "m"), ("nn", "n"), ("ll", "l"),
    ("ss", "s"), ("ch", "c"), ("y", "i"), ("ß", "ss"),
    ("ѣ", "е"), ("і", "и"), ("ѳ", "ф"), ("ъ", ""),
)
#: Inflectional endings whose removal may reveal a lemma in the list.  A
#: stem must keep four letters and be a word itself, so ``lixo`` cannot be
#: made a word by chopping letters off it.
_SUFFIXES = ("es", "s", "en", "er", "em", "n", "e", "a", "o", "os", "as", "ão", "ões",
             "mente", "ing", "ed", "ly", "ая", "ые", "ой", "ом", "ов", "ах", "ами")


def _known(token: str, words: frozenset[str], langs: tuple[str, ...] = ()) -> bool:
    """Is ``token`` a word — directly, by a per-book list, by a packaged
    Hunspell dictionary (inflections through its own affix rules), by
    pre-reform spelling, or by a safe inflection of a listed word?
    Sol §SOL-9, "tratar flexões e ortografias históricas sem aceitar lixo
    arbitrário"."""
    folded = _fold(token)
    if folded in words or folded in _book_words():
        return True
    lowered = token.casefold()
    for dictionary in _dictionaries_for(langs):
        if dictionary.is_word(lowered) or dictionary.is_word(folded):
            return True
    historical = folded
    for old, new in _HISTORICAL:
        if old in historical:
            historical = historical.replace(old, new)
    if historical != folded and historical in words:
        return True
    for suffix in _SUFFIXES:
        if folded.endswith(suffix) and len(folded) - len(suffix) >= 4:
            stem = folded[:-len(suffix)]
            if stem in words:
                return True
    return False


def dictionary_hit_rate(text: str, langs: tuple[str, ...] = ()) -> tuple[float, int]:
    """Fraction of word tokens found in the lexicon, and how many were judged.

    Digits, punctuation, chess notation and single letters are excluded from
    the denominator.  The second element matters: a hit rate over four tokens
    means nothing, and callers must refuse to act on a tiny sample.
    """
    words = _folded_lexicon(langs)
    considered = 0
    hits = 0
    for token in tokenize(text):
        if len(token) < 2 or not any(c.isalpha() for c in token):
            continue
        if is_chess_notation(token):
            continue
        considered += 1
        if _known(token, words, langs):
            hits += 1
    return (hits / considered if considered else 0.0), considered


_VOWELS = frozenset("aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿаеёиоуыэюя")


def is_implausible_token(token: str) -> bool:
    """True when ``token`` cannot be a word in any supported language.

    Three one-sided tests, each chosen because clean text of *any* language
    scores zero on it while OCR output does not:

    * a digit inside a word — ``th1s``, ``be1ieve``, ``rn0ve``.  This is the
      single most characteristic OCR error there is, because the confusable
      pairs are exactly ``l/1/I``, ``O/0``, ``S/5``, ``B/8``, ``G/6``.  Chess
      notation is full of legitimate letter-digit tokens, which is why it is
      excluded before this test runs rather than after;
    * no vowel at all in four or more characters;
    * two different scripts in one token — Latin ``c`` inside a Cyrillic word
      is a scanned-page artefact, not a word.

    The length test counts *characters*, not letters.  Counting letters was a
    bug: substituting the ``i`` of ``th1s`` leaves three letters, the token is
    skipped as too short, and the estimator misses the very error it exists to
    find.
    """
    if len(token) < 4 or is_chess_notation(token):
        return False
    if not any(c.isalpha() for c in token):
        return False
    letters = sum(1 for c in token if c.isalpha())
    digits = sum(1 for c in token if c.isdigit())
    if letters >= 2 and digits >= 1:
        return True
    if len(script_profile(token)) > 1:
        return True
    if letters >= 4 and not any(c in _VOWELS for c in _fold(token)):
        return True
    return False


def nonword_ratio(text: str, langs: tuple[str, ...] = ()) -> tuple[float, int]:
    """Fraction of word-shaped tokens that cannot be words.

    See :func:`is_implausible_token` for the tests.  Real words that trip them
    (acronyms, Czech "smrt", model numbers) are rare enough not to move the
    ratio on a page of prose, while OCR output trips them constantly.
    """
    considered = 0
    bad = 0
    for token in tokenize(text):
        if len(token) < 4 or is_chess_notation(token):
            continue
        if not any(c.isalpha() for c in token):
            continue
        considered += 1
        if is_implausible_token(token):
            bad += 1
    return (bad / considered if considered else 0.0), considered


# --------------------------------------------------------------------------- #
# Notation integrity
# --------------------------------------------------------------------------- #

#: Every character real chess notation is built from, derived from the same
#: constants that build :data:`_NOTATION` so the two cannot drift apart.
#: Annotation marks are *not* here: they are stripped from the tail first,
#: precisely so that a mark found anywhere else counts as damage.
NOTATION_ALPHABET: frozenset[str] = frozenset(
    _PIECE_LETTERS + "abcdefgh" + "12345678"
    + _LINK_MARKS + _PROMOTION_MARK + "Oo0"
)

#: A square name.  The one thing a mangled move almost always keeps, because
#: the file and rank are ordinary Latin characters that no figurine font
#: touches — it is the *piece* glyph that comes back as garbage.
_SQUARE = re.compile(r"[a-h][1-8]")

#: Annotation glyphs (``!``, ``?``, ``+``, ``#``, ``⩲``, ``⨀``, …) trail a move
#: and never open one.  Anything non-alphanumeric at the tail is stripped
#: before judging, which keeps Dvoretsky's zugzwang mark ``Kd3ʘ`` — measured,
#: 60 pages, see docs/quality/F5_REPORT_C2.md — from counting as damage.
_TRAILING_MARKS = re.compile(r"[^0-9A-Za-zЀ-ӿ]+$")

#: Characters that may split a compound the lexicon should get a look at, so
#: that English ``f2-pawn`` and ``e4-square`` are words, not broken moves.
_COMPOUND_SPLIT = re.compile(r"[-'’]")

#: The one move that names no square.  ``0-0`` has to be spelt out rather than
#: caught by "contains a hyphen", because ``1-0`` and ``0-1`` are results and
#: a result is not a move.
_CASTLING = frozenset({"O-O", "O-O-O", "0-0", "0-0-0"})


def is_move_token(token: str) -> bool:
    """True for notation that actually names a move — a square or a castle.

    Narrower than :func:`is_chess_notation`, which also accepts move numbers,
    results and evaluation symbols.  Those are not moves and must not pad the
    denominator of :func:`mangled_move_ratio`: a page of bare move numbers and
    results would otherwise look like a page of healthy notation.
    """
    if not token or not is_chess_notation(token):
        return False
    if _SQUARE.search(token):
        return True
    return _TRAILING_MARKS.sub("", token).upper() in _CASTLING


def is_mangled_move(token: str, langs: tuple[str, ...] = ()) -> bool:
    """True when ``token`` is a move whose piece glyph did not survive.

    This is the one failure a page-level lexical verdict cannot see, and it is
    the failure that matters most in a chess book.  A figurine font maps the
    knight to a private code point; when a PDF is re-OCR'd, or subset without
    a usable ToUnicode, that code point comes back as whatever Latin letters
    happen to sit at the same place — ``♘xe5`` becomes ``ll'lxe5``, ``♕d6+``
    becomes ``'i'd6+``, ``♖h7`` becomes ``l:th7``.

    The prose around it is untouched, so every existing signal stays green:
    measured on Aagaard p222, ``implausible_char_ratio`` 0.001,
    ``broken_font_char_ratio`` 0.000, ``dictionary_hit_rate`` 0.71 — accepted
    at 0.98 with its move text destroyed.

    The test is one-sided by construction.  A mangled move keeps its square —
    file and rank are ordinary Latin that no figurine font touches — but its
    prefix contains a character that notation has no way to produce.  Clean
    notation in any of the eight supported languages scores zero on it:

    * ``Nf3``, ``Cf3``, ``Sf3``, ``Кf3``, ``♘f3`` — the piece letter is in
      :data:`NOTATION_ALPHABET`, and in any case the whole token is already
      valid notation and returns early;
    * ``Lf2-d4``, ``exd5``, ``e8=Q``, ``O-O`` — same;
    * ``f2-pawn``, ``the e4-square`` — a hyphenated compound whose other half
      is a word is a word, not a move;
    * ``Kd3ʘ``, ``Rd1!?`` — annotation glyphs are stripped from the tail.

    Measured over 257 corpus pages (F5_REPORT_C2 §2): the two clean controls
    peak at 0.062, while the damaged books never fall below 0.187.
    """
    if not token or is_chess_notation(token):
        return False
    if not _SQUARE.search(token):
        return False
    words = _folded_lexicon(langs)
    if _known(token, words, langs):
        return False
    parts = _COMPOUND_SPLIT.split(token)
    if len(parts) > 1 and any(len(p) > 2 and _known(p, words, langs) for p in parts):
        return False
    core = _TRAILING_MARKS.sub("", token)
    return any(c not in NOTATION_ALPHABET for c in core)


def mangled_move_ratio(text: str,
                       langs: tuple[str, ...] = ()) -> tuple[float, int]:
    """Share of move-shaped tokens whose piece glyph is damaged, and how many
    moves were judged.

    The second element is the guard the caller must honour: a ratio over four
    moves says nothing, and a page of prose with no notation at all must not
    be condemned by the two moves it happens to quote.
    """
    good = 0
    bad = 0
    for token in tokenize(text):
        if is_move_token(token):
            good += 1
        elif is_mangled_move(token, langs):
            bad += 1
    total = good + bad
    return (bad / total if total else 0.0), total


# --------------------------------------------------------------------------- #
# Character n-gram model
# --------------------------------------------------------------------------- #

_BOUNDARY = "\x02"
#: Stands in for any character that is not a letter but is *inside* a word.
#: It never appears in the model, so every bigram containing it takes the
#: add-one floor — which is the point: an OCR substitution that puts a digit in
#: the middle of a word should be scored as the anomaly it is.
_UNKNOWN = "\x01"


#: Which script each language's list trains — Sol §SOL-9 gives Cyrillic its
#: own model instead of letting the Latin one abstain on it.
_MODEL_SCRIPT_OF_LANG: dict[str, str] = {"rus": "cyrillic"}


def _build_bigrams(script: str) -> tuple[dict[str, int], dict[str, int], int]:
    """Bigram and unigram counts over the lexicon words of one script."""
    bigrams: dict[str, int] = {}
    unigrams: dict[str, int] = {}
    total = 0
    for code, raw in _RAW_LEXICONS.items():
        if _MODEL_SCRIPT_OF_LANG.get(code, "latin") != script:
            continue
        for word in raw.split():
            padded = _BOUNDARY + _fold(word) + _BOUNDARY
            for i in range(len(padded) - 1):
                pair = padded[i:i + 2]
                bigrams[pair] = bigrams.get(pair, 0) + 1
                unigrams[padded[i]] = unigrams.get(padded[i], 0) + 1
                total += 1
    return bigrams, unigrams, total


class _NgramModel:
    """One script's bigram model with its calibration anchors."""

    def __init__(self, script: str) -> None:
        self.script = script
        self.bigrams, self.unigrams, self.total = _build_bigrams(script)
        self.alphabet = max(64, len(self.unigrams) * 2)
        self.good_logp = 0.0
        self.bad_logp = 0.0

    @property
    def usable(self) -> bool:
        return self.total >= 500

    def token_logp(self, form: str) -> tuple[float, int]:
        padded = _BOUNDARY + form + _BOUNDARY
        total = 0.0
        n = 0
        for i in range(len(padded) - 1):
            pair = padded[i:i + 2]
            count = self.bigrams.get(pair, 0)
            context = self.unigrams.get(pair[0], 0)
            total += math.log((count + 1.0) / (context + self.alphabet))
            n += 1
        return total, n


_MODELS: dict[str, _NgramModel] = {
    script: _NgramModel(script) for script in ("latin", "cyrillic")
}
_BIGRAMS, _UNIGRAMS, _BIGRAM_TOTAL = (
    _MODELS["latin"].bigrams, _MODELS["latin"].unigrams, _MODELS["latin"].total)
_ALPHABET_SIZE = _MODELS["latin"].alphabet

#: Log-probability per bigram for text that is entirely unseen.  Used to
#: normalise the raw score into 0..1 so thresholds read as fractions.
_WORST_LOGP = math.log(1.0 / (_BIGRAM_TOTAL + _ALPHABET_SIZE))


def _model_form(token: str) -> str:
    """A token as the bigram model sees it: folded, with non-letters marked.

    Working token by token rather than over the raw string is what makes the
    model sensitive to the errors that matter.  Scanning the whole string and
    treating every non-letter as a word boundary makes ``th1s`` look like the
    two short words ``th`` and ``s``, both perfectly plausible — so the model
    scored corrupted Portuguese at 1.000, a full mark, which is how the bug was
    found.  Marking the digit as an interior unknown instead makes the same
    token score at the smoothing floor.
    """
    return "".join(c if c.isalpha() else _UNKNOWN for c in _fold(token))


def _token_script(token: str) -> str:
    """The script of a token's letters: the majority one."""
    counts: dict[str, int] = {}
    for ch in token:
        if ch.isalpha():
            name = _script_of(ch)
            counts[name] = counts.get(name, 0) + 1
    return max(counts, key=lambda k: (counts[k], k)) if counts else "other"


def ngram_log_probability(text: str, script: str | None = None) -> tuple[float, int]:
    """Mean add-one-smoothed log P(bigram) over the word-shaped tokens.

    Returns ``(mean_log_p, n_bigrams)``.  Chess notation and bare numbers are
    skipped: they are legitimate and they are not words, so scoring them as
    words would make every page of move text look corrupt.  Each token is
    scored by the model of *its own* script (Sol §SOL-9); a token of a
    script with no model is skipped rather than scored as garbage.
    """
    total = 0.0
    n = 0
    for token in tokenize(text or ""):
        if not any(c.isalpha() for c in token):
            continue
        if is_chess_notation(token):
            continue
        model = _MODELS.get(script or _token_script(token))
        if model is None or not model.usable:
            continue
        logp, count = model.token_logp(_model_form(token))
        total += logp
        n += count
    return (total / n if n else 0.0), n


def _reference_scores(model: _NgramModel) -> tuple[float, float]:
    """Calibration anchors: clean lexicon prose, and uniform random letters."""
    sample = " ".join(
        word for code, raw in _RAW_LEXICONS.items()
        if _MODEL_SCRIPT_OF_LANG.get(code, "latin") == model.script
        for word in raw.split()[:80]
    )
    good, _ = ngram_log_probability(sample, model.script)
    # A deterministic pseudo-random string standing in for garbage.  Seeded by
    # a fixed constant so the calibration cannot drift between runs.
    alphabet = "abcdefghijklmnopqrstuvwxyz" if model.script == "latin" else (
        "абвгдежзийклмнопрстуфхцчшщъыьэюя")
    state = 12345
    letters = []
    for _ in range(4000):
        state = (1103515245 * state + 12345) % (1 << 31)
        letters.append(alphabet[state % len(alphabet)])
        if state % 7 == 0:
            letters.append(" ")
    bad, _ = ngram_log_probability("".join(letters), model.script)
    return good, bad


for _model in _MODELS.values():
    if _model.usable:
        _model.good_logp, _model.bad_logp = _reference_scores(_model)
_GOOD_LOGP, _BAD_LOGP = _MODELS["latin"].good_logp, _MODELS["latin"].bad_logp


def ngram_plausibility(text: str) -> tuple[float, int]:
    """Map the bigram log-probability onto 0..1, where 1 is clean prose.

    The anchors are computed at import time per script from the lexicon
    itself and from a fixed pseudo-random string, so the scale survives edits
    to the word lists.  Mixed-script text is scored per token by its own
    model and combined by bigram count.  Values are clamped.
    """
    sums: dict[str, list[float]] = {}
    for token in tokenize(text or ""):
        if not any(c.isalpha() for c in token) or is_chess_notation(token):
            continue
        script = _token_script(token)
        model = _MODELS.get(script)
        if model is None or not model.usable:
            continue
        logp, count = model.token_logp(_model_form(token))
        acc = sums.setdefault(script, [0.0, 0.0])
        acc[0] += logp
        acc[1] += count
    n = int(sum(acc[1] for acc in sums.values()))
    if n == 0:
        return 0.0, 0
    # Normalise per script over the script's whole share of the text, as the
    # single-model version did over the whole text: clamping token by token
    # would let no well-formed word compensate for a rare one.
    total = 0.0
    for script, (logp_sum, count) in sums.items():
        model = _MODELS[script]
        span = model.good_logp - model.bad_logp
        if span <= 0 or count <= 0:  # pragma: no cover - only if a list is emptied
            continue
        total += max(0.0, min(1.0, (logp_sum / count - model.bad_logp) / span)) * count
    return total / n, n


#: The scripts that have a bigram model.  Everything outside them hits the
#: smoothing floor, which reads as "implausible" and is not what it means.
MODELLED_SCRIPT = "latin"
MODELLED_SCRIPTS = frozenset(s for s, m in _MODELS.items() if m.usable)


def modelled_script_share(text: str) -> float:
    """Fraction of the letters in ``text`` the n-gram models can judge.

    Latin has a model since F5; Sol §SOL-9 added a Cyrillic one, built from
    the packaged Russian list, so a Russian page is *scored* rather than
    excused.  Greek, Hebrew or a private-use font still land outside, and
    callers must let the n-gram term abstain on them rather than vote.
    """
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    modelled = sum(1 for c in letters if _script_of(c) in MODELLED_SCRIPTS)
    return modelled / len(letters)


# --------------------------------------------------------------------------- #
# Script sanity
# --------------------------------------------------------------------------- #

_SCRIPT_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x0041, 0x024F, "latin"),
    (0x0370, 0x03FF, "greek"),
    (0x0400, 0x04FF, "cyrillic"),
    (0x0590, 0x05FF, "hebrew"),
    (0x0600, 0x06FF, "arabic"),
    (0x2100, 0x214F, "letterlike"),
    (0x2190, 0x21FF, "arrows"),
    (0x2200, 0x22FF, "math"),
    (0x2600, 0x26FF, "symbols"),      # chess pieces live at U+2654..U+265F
    (0x3000, 0x303F, "cjk_punct"),
    (0x3040, 0x30FF, "kana"),
    (0x4E00, 0x9FFF, "cjk"),
    (0xE000, 0xF8FF, "private_use"),
    (0xFB00, 0xFB4F, "alphabetic_presentation"),
    (0xFFF0, 0xFFFF, "specials"),
)

#: Scripts that a Latin- or Cyrillic-script chess book can legitimately contain.
PLAUSIBLE_SCRIPTS = frozenset({
    "latin", "greek", "cyrillic", "letterlike", "arrows", "math", "symbols",
    "alphabetic_presentation", "digit", "punctuation", "space",
})


def _script_of(ch: str) -> str:
    cp = ord(ch)
    if ch.isspace():
        return "space"
    if ch.isdigit():
        return "digit"
    for lo, hi, name in _SCRIPT_RANGES:
        if lo <= cp <= hi:
            return name
    if cp < 0x0041:
        return "punctuation"
    if unicodedata.category(ch).startswith("P"):
        return "punctuation"
    return "other"


def script_profile(text: str) -> dict[str, int]:
    """Count characters by coarse script.  Whitespace and digits are excluded
    from the *word*-level use in :func:`nonword_ratio` but kept here."""
    profile: dict[str, int] = {}
    for ch in text or "":
        if ch.isspace():
            continue
        name = _script_of(ch)
        if name in ("digit", "punctuation"):
            continue
        profile[name] = profile.get(name, 0) + 1
    return profile


def implausible_char_ratio(text: str) -> tuple[float, int]:
    """Fraction of characters that no correct text layer would contain.

    A missing or dead ``ToUnicode`` makes MuPDF hand back raw glyph indices, and
    glyph indices land wherever they land: the private use area, unassigned
    code points, CJK, or U+0000.  A Latin chess book with 30 % of its
    characters in the CJK block is not a multilingual edition.
    """
    considered = 0
    bad = 0
    for ch in text or "":
        if ch.isspace():
            continue
        considered += 1
        cp = ord(ch)
        if cp == 0 or cp == 0xFFFD:
            bad += 1
            continue
        category = unicodedata.category(ch)
        if category in ("Cc", "Cf", "Co", "Cs", "Cn"):
            bad += 1
            continue
        if _script_of(ch) not in PLAUSIBLE_SCRIPTS:
            bad += 1
    return (bad / considered if considered else 0.0), considered
