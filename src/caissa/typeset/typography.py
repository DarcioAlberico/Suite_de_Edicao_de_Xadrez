"""Text typography: hyphenation, quotes, dashes, chess-aware spacing, small caps.

The rules here are the ones a copy editor would apply, and the ones the critic charter
names as failing defects: straight quotes where typographic ones belong, a hyphen where
an en dash belongs, missing or wrong hyphenation for the language, a move number torn
from its move at a line break, and widows and orphans left standing.

Hyphenation
-----------
Real Liang patterns, not an approximation. ``caissa/typeset/hyphen`` carries the
canonical TeX ``hyph-utf8`` pattern sets for the seven languages the SPEC names, with
each language's upstream copyright and licence beside it (BSD-3, MIT and LPPL -- all
redistributable). The algorithm is Liang's from *Word Hy-phen-a-tion by Com-put-er*: it
is what TeX itself runs, so a line broken here breaks where a TeX-set book breaks it.

Chess is where a general hyphenator goes wrong, and the wrongness is conspicuous:
``Nf3`` must never become ``Nf-3`` and ``Ruy Lopez`` must not be split inside a move.
:class:`Hyphenator` refuses to break any token that looks like chess notation at all.

What is here and what is not
----------------------------
This module knows about *text*: how to shape a paragraph's characters and where a line
may break. It also carries a line breaker and a widow/orphan-aware column filler,
because a rule about widows is worth nothing without something that honours it -- the
proof sheet sets its two-column chess-book page through this code, so the rules are
demonstrated rather than asserted.

It does not do page geometry, floats or footnote placement. That belongs to the export
layer (SPEC §8).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Literal, Mapping, Sequence

__all__ = [
    "strip_diacritics",
    "diacritic_vocabulary",
    "missing_diacritics",
    "EM_DASH",
    "EN_DASH",
    "HAIR_SPACE",
    "Hyphenator",
    "LanguageStyle",
    "NBSP",
    "NARROW_NBSP",
    "QuoteStyle",
    "STYLES",
    "SmallCaps",
    "THIN_SPACE",
    "break_lines",
    "fill_columns",
    "get_style",
    "hyphenate_word",
    "looks_like_chess",
    "protect_chess_notation",
    "smart_dashes",
    "chess_symbols",
    "check_marks",
    "smart_quotes",
    "small_caps_runs",
    "typeset_text",
]

NBSP = " "
NARROW_NBSP = " "
THIN_SPACE = " "
HAIR_SPACE = " "
EN_DASH = "–"
EM_DASH = "—"
MINUS = "−"
ELLIPSIS = "…"
SOFT_HYPHEN = "­"
ZERO_WIDTH_SPACE = "​"


# --------------------------------------------------------------------------- #
# Language conventions
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class QuoteStyle:
    """The four marks a language uses, outer pair then inner pair."""

    open_outer: str
    close_outer: str
    open_inner: str
    close_inner: str
    space_inside: str = ""
    """French sets a narrow no-break space inside its guillemets. Nothing else does."""


@dataclass(frozen=True)
class LanguageStyle:
    code: str
    label: str
    quotes: QuoteStyle
    parenthetical_dash: str
    """The dash used for an aside. English (US) uses an em dash closed up; most of
    Europe uses an en dash with spaces around it."""

    dash_spaced: bool
    decimal: str
    thousands: str
    hyphen_patterns: str | None
    """File stem under ``hyphen/``, or None when no pattern set is bundled."""

    dialogue_dash: str = EM_DASH
    """Portuguese and Spanish open reported speech with a travessao / raya."""


STYLES: dict[str, LanguageStyle] = {}


def _add(style: LanguageStyle) -> None:
    STYLES[style.code] = style


# pt-BR: curly double quotes as the outer pair -- Brazil follows the English shape here,
# unlike Portugal, which often prefers guillemets. Asides take a spaced en dash, and
# reported speech opens with a travessao.
_add(
    LanguageStyle(
        code="pt",
        label="Portugues (Brasil)",
        quotes=QuoteStyle("“", "”", "‘", "’"),
        parenthetical_dash=EN_DASH,
        dash_spaced=True,
        decimal=",",
        thousands=".",
        hyphen_patterns="pt",
        dialogue_dash=EM_DASH,
    )
)
_add(
    LanguageStyle(
        code="en",
        label="English (UK)",
        quotes=QuoteStyle("‘", "’", "“", "”"),
        parenthetical_dash=EN_DASH,
        dash_spaced=True,
        decimal=".",
        thousands=",",
        hyphen_patterns="en",
    )
)
_add(
    LanguageStyle(
        code="en_us",
        label="English (US)",
        quotes=QuoteStyle("“", "”", "‘", "’"),
        parenthetical_dash=EM_DASH,
        dash_spaced=False,
        decimal=".",
        thousands=",",
        hyphen_patterns="en_us",
    )
)
# German: low-nine opening, high-six closing -- „so“ -- and the inner pair matches.
# Getting this wrong is the classic tell of a book typeset by someone who does not read
# the language.
_add(
    LanguageStyle(
        code="de",
        label="Deutsch",
        quotes=QuoteStyle("„", "“", "‚", "‘"),
        parenthetical_dash=EN_DASH,
        dash_spaced=True,
        decimal=",",
        thousands=".",
        hyphen_patterns="de",
    )
)
_add(
    LanguageStyle(
        code="es",
        label="Espanol",
        quotes=QuoteStyle("«", "»", "“", "”"),
        parenthetical_dash=EN_DASH,
        dash_spaced=True,
        decimal=",",
        thousands=".",
        hyphen_patterns="es",
        dialogue_dash=EM_DASH,
    )
)
# French guillemets take a narrow no-break space on the inside, and the same space goes
# before ; : ! ?  -- see `_french_spacing`.
_add(
    LanguageStyle(
        code="fr",
        label="Francais",
        quotes=QuoteStyle("«", "»", "‹", "›", space_inside=NARROW_NBSP),
        parenthetical_dash=EN_DASH,
        dash_spaced=True,
        decimal=",",
        thousands=NARROW_NBSP,
        hyphen_patterns="fr",
    )
)
_add(
    LanguageStyle(
        code="it",
        label="Italiano",
        quotes=QuoteStyle("«", "»", "“", "”"),
        parenthetical_dash=EN_DASH,
        dash_spaced=True,
        decimal=",",
        thousands=".",
        hyphen_patterns="it",
    )
)
_add(
    LanguageStyle(
        code="ru",
        label="Russkij",
        quotes=QuoteStyle("«", "»", "„", "“"),
        parenthetical_dash=EM_DASH,
        dash_spaced=True,
        decimal=",",
        thousands=NARROW_NBSP,
        hyphen_patterns="ru",
    )
)


def get_style(language: str) -> LanguageStyle:
    code = (language or "en").replace("-", "_").lower()
    if code in STYLES:
        return STYLES[code]
    base = code.split("_")[0]
    if base in STYLES:
        return STYLES[base]
    raise KeyError(
        f"Idioma sem regras tipograficas: {language!r}. "
        f"Disponiveis: {', '.join(sorted(STYLES))}"
    )


# --------------------------------------------------------------------------- #
# Hyphenation -- Liang's algorithm
# --------------------------------------------------------------------------- #
_PATTERN_DIR = Path(__file__).resolve().parent / "hyphen"


class Hyphenator:
    """Liang hyphenation with the canonical TeX patterns.

    ``left`` and ``right`` are the minimum number of characters that must remain on
    each side of a break. TeX's defaults are 2 and 3; book practice for a narrow chess
    column is 3 and 3, because a two-letter fragment dangling at a line end is exactly
    the kind of thing the charter calls a defect.
    """

    def __init__(
        self,
        language: str = "en",
        *,
        left: int = 3,
        right: int = 3,
        patterns: Mapping[str, list[int]] | None = None,
        exceptions: Mapping[str, list[int]] | None = None,
    ) -> None:
        self.language = language
        self.left = max(1, left)
        self.right = max(1, right)
        if patterns is None:
            style = get_style(language)
            patterns, exceptions_loaded = _load_patterns(style.hyphen_patterns)
            exceptions = dict(exceptions_loaded) | dict(exceptions or {})
        self._patterns = patterns
        self._exceptions = dict(exceptions or {})
        self._max = max((len(p) for p in self._patterns), default=0)

    def positions(self, word: str) -> list[int]:
        """Indices inside ``word`` where a hyphen may be inserted."""
        lowered = word.lower()
        if lowered in self._exceptions:
            points = self._exceptions[lowered]
        else:
            points = self._points(lowered)
        # points[i] is the value for a break *before* word[i], i.e. the split
        # word[:i] + "-" + word[i:]. Indexing this by i-1 is the classic off-by-one in
        # a Liang implementation, and it shifts every hyphen one letter left: it turns
        # "hy-phen-ation" into "hyp-hena-tion", which looks almost right and is wrong in
        # every word.
        return [
            i
            for i in range(self.left, len(word) - self.right + 1)
            if i < len(points) and points[i] % 2 == 1
        ]

    def _points(self, word: str) -> list[int]:
        text = "." + word + "."
        values = [0] * (len(text) + 1)
        for i in range(len(text)):
            for j in range(i + 1, min(i + self._max, len(text)) + 1):
                pattern = self._patterns.get(text[i:j])
                if pattern:
                    for k, value in enumerate(pattern):
                        pos = i + k
                        if pos < len(values) and value > values[pos]:
                            values[pos] = value
        # values[0] belongs to the leading '.', so drop it to align with the word.
        return values[1:]

    def split(self, word: str) -> list[str]:
        """The word cut into hyphenation fragments."""
        points = self.positions(word)
        if not points:
            return [word]
        out: list[str] = []
        last = 0
        for point in points:
            out.append(word[last:point])
            last = point
        out.append(word[last:])
        return out

    def soft_hyphenate(self, word: str) -> str:
        return SOFT_HYPHEN.join(self.split(word))


@lru_cache(maxsize=16)
def _load_patterns(stem: str | None) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Parse a TeX pattern file into Liang's lookup table."""
    if not stem:
        return {}, {}
    patterns: dict[str, list[int]] = {}
    path = _PATTERN_DIR / f"{stem}.pat.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            token = line.strip()
            if not token or token.startswith("%"):
                continue
            key = re.sub(r"\d", "", token)
            if key:
                patterns[key] = _pattern_values(token)
    exceptions: dict[str, list[int]] = {}
    hyp = _PATTERN_DIR / f"{stem}.hyp.txt"
    if hyp.exists():
        for line in hyp.read_text(encoding="utf-8", errors="replace").splitlines():
            token = line.strip()
            if not token or token.startswith("%"):
                continue
            word = token.replace("-", "")
            marks = [0] * len(word)
            index = 0
            for char in token:
                if char == "-":
                    if 0 < index <= len(marks):
                        marks[index - 1] = 1
                else:
                    index += 1
            exceptions[word.lower()] = marks
    return patterns, exceptions


def _pattern_values(token: str) -> list[int]:
    """Digits of a Liang pattern, one slot per inter-letter position.

    ``a1bc3d`` describes ``abcd`` with values ``[0, 1, 0, 3, 0]`` -- a slot before the
    first letter, between each pair, and after the last.
    """
    values: list[int] = []
    pending = 0
    seen_letter = False
    for char in token:
        if char.isdigit():
            pending = int(char)
        else:
            values.append(pending)
            pending = 0
            seen_letter = True
    values.append(pending)
    return values if seen_letter else [0]


# Anything that looks like chess notation is never hyphenated. `Nf3`, `exd5`, `O-O-O`,
# `1-0`, `Qxh7+`, `e8=Q`, `+-`, `1...Rxd4`. A general hyphenator has no reason to know
# these are atomic, and breaking one is immediately visible to a chess reader.
_CHESS_TOKEN = re.compile(
    r"^(?:"
    r"[KQRBNPKDTLSACФЛКП]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBNDTLSAC])?[+#]?[!?]{0,2}"
    r"|O-O(?:-O)?|0-0(?:-0)?"
    r"|\d+\.{1,3}"
    r"|[01]-[01]|1/2-1/2|½-½|½–½|[01]–[01]"
    r"|[+\-=]/?[+\-=]"
    r")$",
    re.UNICODE,
)


def looks_like_chess(token: str) -> bool:
    return bool(_CHESS_TOKEN.match(token.strip()))


def hyphenate_word(word: str, hyphenator: Hyphenator) -> list[str]:
    """Fragments of ``word``, or the whole word when it must not be broken."""
    if len(word) < hyphenator.left + hyphenator.right:
        return [word]
    if looks_like_chess(word) or any(ch.isdigit() for ch in word):
        return [word]
    if "-" in word:
        # An already-hyphenated compound breaks at its own hyphens and nowhere else;
        # adding a second hyphen to "Rook-and-pawn" reads as a typo.
        parts = word.split("-")
        out: list[str] = []
        for i, part in enumerate(parts):
            out.append(part + ("-" if i < len(parts) - 1 else ""))
        return out
    return hyphenator.split(word)


# --------------------------------------------------------------------------- #
# Quotes, dashes, spacing
# --------------------------------------------------------------------------- #
_APOSTROPHE_INSIDE = re.compile(r"(?<=\w)'(?=\w)")


def smart_quotes(text: str, language: str = "en") -> str:
    """Straight quotes to the language's typographic pair.

    The nesting is tracked as the string is scanned, so an inner quotation gets the
    inner pair. Apostrophes inside words are converted first and taken out of play, so
    ``Karpov's`` never opens a quotation.
    """
    style = get_style(language)
    q = style.quotes
    text = _APOSTROPHE_INSIDE.sub("’", text)

    out: list[str] = []
    double_open = False
    single_open = False
    for index, char in enumerate(text):
        before = text[index - 1] if index else " "
        if char == '"':
            if double_open:
                out.append(q.space_inside + q.close_outer if q.space_inside else q.close_outer)
                double_open = False
            else:
                out.append(q.open_outer + q.space_inside if q.space_inside else q.open_outer)
                double_open = True
        elif char == "'":
            # A leading apostrophe on a word ('tis, '90s) is an apostrophe, not a quote.
            if not single_open and index + 1 < len(text) and text[index + 1].isdigit():
                out.append("’")
                continue
            if single_open:
                out.append(q.close_inner)
                single_open = False
            elif before.isalnum():
                out.append("’")
            else:
                out.append(q.open_inner)
                single_open = True
        else:
            out.append(char)
    return "".join(out)


_RANGE = re.compile(r"(?<=\d)\s*-\s*(?=\d)")

# A *result*, and nothing else. `0-0` is deliberately absent: in running chess prose it
# is castling perhaps a thousand times for every double forfeit, and setting castling as
# `0` en-dash `0` makes it read as a score. `0-0-0` is excluded for the same reason, and
# the lookarounds stop `1-0` being found inside it.
_RESULT = re.compile(
    r"(?<![-\d/½])(1|0|½|1/2)\s*-\s*(0|1|½|1/2)(?![-\d/½])"
)

# Castling, in either notation, guarded so the range rule cannot reach it.
_CASTLING = re.compile(r"\b(?:0-0-0|0-0)\b")
_SPACED_HYPHEN = re.compile(r"(?<=\s)-{1,3}(?=\s)")
_DOUBLE_HYPHEN = re.compile(r"(?<!-)--(?!-)")
_TRIPLE = re.compile(r"---")


def smart_dashes(text: str, language: str = "en", *, castling_dash: str = "-") -> str:
    """Pick the right dash for each job.

    * A range of numbers, and a chess **result**, take an en dash: ``1-0`` set with a
      hyphen is the commonest typographic error in chess books, and ``1``–``0`` is
      what a publisher sets.
    * **Castling is a house style, not a rule.** ``0-0`` is left exactly as the author
      typed it unless ``castling_dash`` says otherwise. Quality Chess sets ``0``–``0``
      with an en dash (verified against the reference page in
      ``benchmarks/reports/blind/``); the PGN standard and most other houses set
      ``O-O`` with a hyphen. What must never happen is castling being converted *by
      accident*, which is what the result and range rules both do if left unguarded.
    * ``--`` becomes an en dash, ``---`` an em dash, the TeX convention authors type by
      habit.
    * A lone spaced hyphen becomes the language's parenthetical dash: an em dash closed
      up in US English, a spaced en dash nearly everywhere else.
    * A hyphen inside a word is left exactly as it is.
    """
    style = get_style(language)
    text = _TRIPLE.sub(EM_DASH, text)
    text = _DOUBLE_HYPHEN.sub(EN_DASH, text)
    # Castling stands aside while the result and range rules run, and comes back
    # untouched. Both of those rules match `0-0` on sight -- one reads it as a double
    # forfeit, the other as a numeric range -- and either way the reader is handed a
    # score where the author wrote a move.
    guards: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        guards.append(match.group(0))
        return f"\x00{len(guards) - 1}\x00"

    text = _CASTLING.sub(_stash, text)
    text = _RESULT.sub(lambda m: f"{m.group(1)}{EN_DASH}{m.group(2)}", text)
    text = _RANGE.sub(EN_DASH, text)
    if guards:
        text = re.sub(
            r"\x00(\d+)\x00",
            lambda m: guards[int(m.group(1))].replace("-", castling_dash),
            text,
        )
    if style.dash_spaced:
        text = _SPACED_HYPHEN.sub(style.parenthetical_dash, text)
    else:
        text = re.sub(r"\s+-{1,2}\s+", style.parenthetical_dash, text)
    return _bind_parenthetical_dash(text)


# A spaced en or em dash belongs to the phrase it follows: it ends a line, it never
# starts one. Observed on the reference page as `... the game Vitiugov -` / `Bologan
# from ...`; our own first setting of the same sentence put the dash at the head of the
# next line, which is the kind of thing a reader notices without knowing why.
_LEADING_DASH = re.compile(r"[  ]+([" + EN_DASH + EM_DASH + r"])(?=[  ])")


def _bind_parenthetical_dash(text: str) -> str:
    return _LEADING_DASH.sub(lambda m: NBSP + m.group(1), text)


# Move number and move are one token. `12.` followed by a space and `Nf3` may not be
# split across a line, and neither may `12...Rxd4`. The no-break space is the standard
# way to say so and survives every export format.
_MOVE_NUMBER = re.compile(r"(\b\d{1,3}\.{1,3})[  ]+(?=[KQRBNPa-hO0♔-♟])")
_ELLIPSIS_MOVE = re.compile(r"(\b\d{1,3})\.\.\.")
_NAG_SPACE = re.compile(r"[  ]+(?=[!?]{1,2}(?:\s|$))")
# A result is set tight -- `1–0`, never `1 – 0`. Quality Chess, Gambit and New in Chess
# all set it closed up, and closing it up also makes the no-break question moot: there is
# no space left for a line breaker to break at. An earlier version padded both sides with
# NBSP, which put a visible gap on either side of the dash and made `0–0` read as a score.
_RESULT_TOKEN = re.compile("(?<![-\d/½])([01½])[   ]*–[   ]*([01½])(?![-\d/½])")

# Informant evaluation symbols. A reader who knows the code reads `±` instantly and
# `+/-` not at all, so the substitution is worth making -- but only when the face that
# will set the page can actually draw the character. Times New Roman, the serif most
# chess books are set in, carries U+00B1 and *not* U+2213, U+2A71 or U+2A72; substituting
# those blind puts a notdef box on the page, which is strictly worse than the ASCII the
# author typed. Real books get them from the chess font, not the text font -- until that
# path exists, `can_render` is the gate. Verified with `pymupdf.Font.has_glyph`.
_EVAL_SYMBOLS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![-+/=])\+/-(?![-+/=\w])"), "±"),
    (re.compile(r"(?<![-+/=])-/\+(?![-+/=\w])"), "∓"),
    (re.compile(r"(?<![-+/=])\+/=(?![-+/=\w])"), "⩲"),
    (re.compile(r"(?<![-+/=])=/\+(?![-+/=\w])"), "⩱"),
    # `+-` is "White is winning" and its second half is a MINUS SIGN, U+2212 -- not an
    # en dash. Cycle 2 set U+002B U+2013 here and the critic caught it: on the same page
    # one evaluation came out as a correct single glyph (`16.e3±`) and the other as a
    # forged pair. Times New Roman carries U+2212 (checked in its cmap), so this was
    # never a coverage limit; it was the wrong character. `usable` still gates it, and
    # `MINUS` is not in the `assumed` set, so a face without it keeps the ASCII.
    (re.compile(r"(?<![-+/=])\+-(?![-+/=\w])"), "+" + MINUS),
    (re.compile(r"(?<![-+/=])-\+(?![-+/=\w])"), MINUS + "+"),
]


def chess_symbols(text: str, *, can_render: Callable[[str], bool] | None = None) -> str:
    """Turn ASCII evaluation shorthand into the characters a book actually sets.

    ``can_render`` is asked, character by character, whether the target face has the
    glyph. A substitution whose glyph is missing is **not made**: the ASCII stays, and
    the reader gets `+/=` rather than an empty box. Passing nothing means "assume
    nothing", and only the substitutions whose characters are in Latin-1 -- which every
    text face has -- are applied.
    """

    # The dashes are not in question: `smart_dashes` already sets them unconditionally
    # on every page, so a face that could not draw them would have failed long before
    # reaching here. Only the genuinely rare Informant symbols need the gate.
    assumed = {EN_DASH, EM_DASH}

    def usable(replacement: str) -> bool:
        for char in replacement:
            if ord(char) < 0x100 or char in assumed:
                continue
            if can_render is None:
                return False
            if not can_render(char):
                return False
        return True

    for pattern, replacement in _EVAL_SYMBOLS:
        if usable(replacement):
            text = pattern.sub(replacement, text)
    return text


# Check and mate marks. `+` and `#` are the PGN standard and what an author types;
# Quality Chess, Batsford and Chess Informant all set a dagger and a double dagger
# instead (verified on the reference page: `24.Bxh7†`, `25.Rh8‡` style). House style,
# so it is opt-in -- and gated on the face having the glyph, like every other
# substitution here.
CHECK_MARKS: dict[str, tuple[str, str]] = {
    "ascii": ("+", "#"),
    "dagger": ("†", "‡"),
}

# The lookahead must also refuse the evaluation symbols, which run *before* this
# pass: in `h5+-` -> `h5+–` the plus belongs to the evaluation, not to a check,
# and turning it into a dagger gives `h5†–`.
_CHECK = re.compile("(?<=[a-h1-8QRBNKO])(\+|#)(?![-+/=\w–—−±∓⩱⩲])")


def check_marks(text: str, style: str = "ascii", *, can_render=None) -> str:
    """Set check and mate in the house's marks. ``ascii`` leaves the text alone."""
    check, mate = CHECK_MARKS.get(style, CHECK_MARKS["ascii"])
    if (check, mate) == CHECK_MARKS["ascii"]:
        return text
    if can_render is not None and not (can_render(check) and can_render(mate)):
        return text
    return _CHECK.sub(lambda m: check if m.group(1) == "+" else mate, text)


def protect_chess_notation(text: str) -> str:
    """Insert no-break spaces where chess notation must not be torn apart.

    Four places, each of which a general text engine gets wrong:

    * between a move number and its move -- ``12.`` and ``Nf3`` are one thing;
    * inside a Black-to-move ellipsis, ``12...Rxd4``;
    * before a trailing ``!``/``?`` annotation, which must not start a line;
    * a result is closed up to ``1``–``0``, which leaves nothing to break.
    """
    text = _ELLIPSIS_MOVE.sub(lambda m: f"{m.group(1)}{ELLIPSIS}", text)
    text = _MOVE_NUMBER.sub(lambda m: f"{m.group(1)}{NARROW_NBSP}", text)
    text = _NAG_SPACE.sub("", text)
    text = _RESULT_TOKEN.sub(lambda m: f"{m.group(1)}{EN_DASH}{m.group(2)}", text)
    return text


def _french_spacing(text: str) -> str:
    """French sets a narrow no-break space before ; : ! ? and inside guillemets."""
    text = re.sub(r"[   ]*([;:!?])", NARROW_NBSP + r"\1", text)
    text = re.sub(r"«[   ]*", "«" + NARROW_NBSP, text)
    text = re.sub(r"[   ]*»", NARROW_NBSP + "»", text)
    return text


_ELLIPSIS_DOTS = re.compile(r"(?<!\.)\.\.\.(?!\.)")


def typeset_text(
    text: str,
    language: str = "en",
    *,
    chess: bool = True,
    castling_dash: str = "-",
    check_style: str = "ascii",
    can_render: Callable[[str], bool] | None = None,
) -> str:
    """Apply every character-level rule for ``language``, in the order they must run.

    Order matters: quotes before dashes (a dash rule must not see a straight quote as a
    word boundary), dashes before the chess protection (which looks for the en dash it
    produces), and French spacing last, once the guillemets exist.
    """
    style = get_style(language)
    out = smart_quotes(text, language)
    out = smart_dashes(out, language, castling_dash=castling_dash)
    # An ellipsis that is not part of a chess move becomes the single character.
    if chess:
        out = chess_symbols(out, can_render=can_render)
        out = check_marks(out, check_style, can_render=can_render)
        out = protect_chess_notation(out)
    out = _ELLIPSIS_DOTS.sub(ELLIPSIS, out)
    if style.code == "fr":
        out = _french_spacing(out)
    return out


# --------------------------------------------------------------------------- #
# Small caps
# --------------------------------------------------------------------------- #
class SmallCaps(str, Enum):
    REAL = "real"
    """The font has a genuine small-caps set (an ``smcp`` feature or an SC family)."""

    SYNTHETIC = "synthetic"
    """No such set: capitals scaled down. Legitimate only with a weight correction,
    because scaled capitals are visibly lighter than the text around them."""

    NONE = "none"


# A synthetic small capital is set at this fraction of the cap height. Scaling a capital
# to the x-height (about 0.52 em) makes it too small and too light; 0.78 of the cap
# height is what type designers use when they cut a real small-caps set.
SYNTHETIC_SMALL_CAP_RATIO = 0.78


def has_real_small_caps(ttfont) -> bool:  # noqa: ANN001
    """True when the font declares an ``smcp``/``c2sc`` feature."""
    try:
        gsub = ttfont.get("GSUB")
        if gsub is None:
            return False
        features = gsub.table.FeatureList.FeatureRecord
        return any(record.FeatureTag in ("smcp", "c2sc") for record in features)
    except Exception:
        return False


def small_caps_runs(text: str) -> list[tuple[str, bool]]:
    """Split into runs, flagging which should be set as small capitals.

    Lower-case letters become small capitals; existing capitals stay full size. That is
    what makes ``Karpov`` read as ``K`` ``ARPOV`` rather than as a shout.
    """
    runs: list[tuple[str, bool]] = []
    buffer = ""
    current: bool | None = None
    for char in text:
        small = char.islower()
        if current is None:
            current = small
        if small != current:
            runs.append((buffer, current))
            buffer = ""
            current = small
        buffer += char.upper() if small else char
    if buffer:
        runs.append((buffer, bool(current)))
    return runs


# --------------------------------------------------------------------------- #
# Line breaking
# --------------------------------------------------------------------------- #
@dataclass
class Line:
    text: str
    width: float
    is_last: bool = False
    hyphenated: bool = False


def break_lines(
    text: str,
    *,
    width: float,
    measure: Callable[[str], float],
    hyphenator: Hyphenator | None = None,
    hyphen: str = "-",
    max_consecutive_hyphens: int = 2,
) -> list[Line]:
    """Break a paragraph into lines that fit ``width``.

    Greedy with hyphenation, plus the one refinement that matters for a narrow chess
    column: ``max_consecutive_hyphens``. Three hyphens in a row down a column edge is a
    defect every house style bans, so once the limit is reached the breaker stops
    offering hyphen points and lets the line run loose instead.

    Words joined by a no-break space (a move number and its move) are measured and placed
    as one unit, so :func:`protect_chess_notation` is actually honoured rather than
    merely applied.
    """
    tokens = [t for t in re.split(r"[ \t]+", text.strip()) if t]
    lines: list[Line] = []
    current: list[str] = []
    consecutive = 0

    def current_text() -> str:
        return " ".join(current)

    pending = list(tokens)
    while pending:
        token = pending.pop(0)
        trial_text = " ".join(current + [token])
        if measure(trial_text) <= width:
            current.append(token)
            continue

        # The token does not fit. Try to hyphenate it onto this line, taking the
        # LONGEST head that still fits -- the shortest would leave the line loose.
        best: tuple[str, str] | None = None
        if hyphenator is not None and consecutive < max_consecutive_hyphens:
            prefix = current_text()
            for head, tail in _hyphen_points(token, hyphenator):
                candidate = (prefix + " " if prefix else "") + head + hyphen
                if measure(candidate) <= width:
                    best = (candidate, tail)
        if best is not None:
            candidate, tail = best
            lines.append(Line(candidate, measure(candidate), hyphenated=True))
            consecutive += 1
            current = []
            pending.insert(0, tail)
            continue

        if current:
            lines.append(Line(current_text(), measure(current_text())))
            consecutive = 0
            current = [token]
        else:
            # A single unbreakable token wider than the column. Setting it alone and
            # letting it overhang is the honest outcome: silently dropping or squeezing
            # it would hide a measure that is simply too narrow for the content.
            lines.append(Line(token, measure(token)))
            consecutive = 0
            current = []

    if current:
        lines.append(Line(current_text(), measure(current_text()), is_last=True))
    elif lines:
        lines[-1].is_last = True
    return lines


def _hyphen_points(token: str, hyphenator: Hyphenator) -> list[tuple[str, str]]:
    """Every legal (head, tail) split of ``token``, shortest head first."""
    # Strip punctuation so that "Verteidigung," hyphenates on the word, not the comma.
    lead = len(token) - len(token.lstrip("“„«('‘"))
    trail_text = token[lead:]
    trail = len(trail_text) - len(trail_text.rstrip(".,;:!?”’»)"))
    core = token[lead : len(token) - trail] if trail else token[lead:]
    if not core:
        return []
    fragments = hyphenate_word(core, hyphenator)
    if len(fragments) < 2:
        return []
    out: list[tuple[str, str]] = []
    for i in range(1, len(fragments)):
        head = token[:lead] + "".join(fragments[:i])
        tail = "".join(fragments[i:]) + (token[len(token) - trail :] if trail else "")
        out.append((head, tail))
    return out


# --------------------------------------------------------------------------- #
# Widows and orphans
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ColumnPolicy:
    """How few lines of a paragraph may be left alone at a column boundary.

    An **orphan** is the first line of a paragraph stranded at the foot of a column; a
    **widow** is the last line stranded at the head of the next. Both defaults are 2,
    which is standard book practice.
    """

    min_orphan: int = 2
    min_widow: int = 2


@dataclass
class ParagraphBlock:
    lines: list[Line]
    keep_with_next: bool = False
    space_before: float = 0.0
    space_after: float = 0.0


def fill_columns(
    blocks: Sequence[ParagraphBlock],
    *,
    lines_per_column: int,
    policy: ColumnPolicy | None = None,
) -> list[list[tuple[int, Line]]]:
    """Distribute paragraphs into columns without leaving widows or orphans.

    Returns one list per column of ``(block index, line)``. When a paragraph would leave
    fewer than ``min_orphan`` lines at the foot, the whole paragraph is pushed to the
    next column; when it would leave fewer than ``min_widow`` at the head, enough lines
    are pushed with it to make up the number. Pushing lines is the correct fix and the
    only one available without re-setting the paragraph, which a real page engine would
    then do.
    """
    policy = policy or ColumnPolicy()
    columns: list[list[tuple[int, Line]]] = [[]]
    room = lines_per_column

    for index, block in enumerate(blocks):
        remaining = list(block.lines)
        while remaining:
            if room <= 0:
                columns.append([])
                room = lines_per_column

            if len(remaining) == len(block.lines):
                # Starting the paragraph here: refuse to leave an orphan.
                if room < policy.min_orphan and len(remaining) > room:
                    columns.append([])
                    room = lines_per_column

            take = min(room, len(remaining))
            left_over = len(remaining) - take
            # Refuse to leave a widow at the top of the next column.
            if 0 < left_over < policy.min_widow:
                pull = policy.min_widow - left_over
                take = max(0, take - pull)
                if take <= 0:
                    columns.append([])
                    room = lines_per_column
                    continue

            for line in remaining[:take]:
                columns[-1].append((index, line))
            remaining = remaining[take:]
            room -= take

    return columns


# --------------------------------------------------------------------------- #
# Diacritics
# --------------------------------------------------------------------------- #
# Endings that a Portuguese word cannot carry without an accent. The nasal diphthongs
# are the whole of it: `-ao`, `-oes` and `-aes` are always written `-ão`, `-ões`, `-ães`,
# so a word that ends in one of them unaccented is a spelling error and not a variant.
# The cycle-5 blind sample carried `peoes` in its running head, one line above a title
# that spelled `peões` correctly, and nothing in the project looked.
_PT_NASAL_ENDINGS = ("oes", "aes", "ao")

# Words that carry an accent and whose unaccented spelling is a different word or no
# word. Structural rules cannot reach a proparoxytone like `Capítulo`, so the ones the
# project's own copy uses are named. Callers add their own with `diacritic_vocabulary`.
#
# Nothing shorter than `_MIN_VOCABULARY_WORD` goes in, harvested or built in: `é` and `à`
# strip to `e` and `a`, which are an ordinary conjunction and an ordinary article, and a
# check that flagged those would flag every sentence and be turned off within a day.
_PT_ACCENTED_WORDS = (
    "após", "até", "área", "básico", "cálculo", "capítulo", "número", "página",
    "próximo", "público", "período", "século", "série", "símbolo", "título", "único",
    "último", "vários", "três", "além", "está", "estão",
    "possível", "impossível", "difícil", "fácil", "última", "índice", "média",
    "ângulo", "código", "família", "matemática", "prática", "técnica", "história",
    "referência", "sequência", "consequência", "página", "início", "própria", "próprio",
)

_MIN_VOCABULARY_WORD = 4

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def strip_diacritics(word: str) -> str:
    """``word`` with every combining mark removed. `peões` -> `peoes`."""
    decomposed = unicodedata.normalize("NFD", word)
    return unicodedata.normalize(
        "NFC", "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    )


def diacritic_vocabulary(*texts: str) -> set[str]:
    """Every accented word in ``texts``, lower-cased.

    Harvested from the project's own copy so the check cannot go stale: whatever the book
    spells with an accent in one place must not appear without it in another.
    """
    found: set[str] = set()
    for text in texts:
        for word in _WORD_RE.findall(text):
            if strip_diacritics(word) != word and len(word) >= _MIN_VOCABULARY_WORD:
                found.add(word.lower())
    return found


def missing_diacritics(
    text: str, language: str = "pt", *, vocabulary: "Iterable[str] | None" = None
) -> list[str]:
    """Words in ``text`` that would gain a diacritic if they were spelled correctly.

    The check the cycle-5 critique found missing: *"nenhuma cadeia em portugues pode
    conter uma palavra que ganhe diacritico ao ser normalizada"*. Two rules, both
    conservative -- a false positive here is a spelling argument, and a false negative is
    a misspelled word on a page submitted for judgement against five published books.

    * a word ending in a nasal diphthong (`-ao`, `-oes`, `-aes`) is always accented;
    * a word whose accented form is in the vocabulary -- the built-in list of common
      accented Portuguese words, plus anything the caller harvested with
      :func:`diacritic_vocabulary` from the document's own copy.

    Returns the offending words in order, empty for a clean string. Languages other than
    Portuguese return empty: the rules above are Portuguese orthography, not a general
    spell check, and a check that guessed at other languages would be worse than none.
    """
    if language not in ("pt", "pt_br", "pt-br"):
        return []
    wrong = {strip_diacritics(w).lower() for w in _PT_ACCENTED_WORDS
             if len(w) >= _MIN_VOCABULARY_WORD}
    wrong |= {strip_diacritics(w).lower() for w in (vocabulary or ())
              if len(w) >= _MIN_VOCABULARY_WORD}
    out: list[str] = []
    for word in _WORD_RE.findall(text):
        lowered = word.lower()
        if strip_diacritics(word) != word:
            continue                      # already accented
        if lowered in wrong:
            out.append(word)
            continue
        if len(lowered) > 2 and lowered.endswith(_PT_NASAL_ENDINGS):
            out.append(word)
    return out
