"""Notation locales: piece letters, castling, marks, and language detection.

Chess notation is not one language written eight ways.  It is eight languages
that happen to share an alphabet, and the overlaps are hostile:

===========  ==  ==  ==  ==  ==  ==
locale        K   Q   R   B   N   P
===========  ==  ==  ==  ==  ==  ==
en (Eng.)     K   Q   R   B   N   P
pt (Port.)    R   D   T   B   C   P
es (Span.)    R   D   T   A   C   P
fr (Fren.)    R   D   T   F   C   P
it (Ital.)    R   D   T   A   C   P
de (Germ.)    K   D   T   L   S   B
nl (Dutch)    K   D   T   L   P   -
ru (Russ.)   Кр   Ф   Л   С   К   п
===========  ==  ==  ==  ==  ==  ==

Read that table column by column and three traps fall out.

**``R`` is the king in pt/es/fr/it and the rook in English.**  They collide with
*opposite* meanings, and both readings are frequently legal in the same
position -- a rook ending is the worst case, because ``Rc7`` is usually playable
by both pieces.  Getting this wrong does not raise an error; it silently
substitutes one piece for another and every subsequent move of the game is
wrong.  This is the single highest-stakes conversion in the whole product, and
it is why :func:`detect_language` exists and why it is allowed to abstain.

**``B`` is the bishop in English and Portuguese but the *pawn* in German.**  The
Portuguese coincidence is harmless (``Bd3`` is a bishop either way); the German
one is not, but it is self-limiting: German prints no letter for pawn moves in
practice, so a leading ``B`` in a German text is nearly always an OCR artefact
or an English quotation.  The table records the truth anyway, because
:func:`from_language` must reject ``B`` as a German *bishop*.

**``P`` is the pawn in English and the knight (Paard) in Dutch.**  Dutch writes
no letter for pawns at all, so :data:`NotationLocale.pawn` is ``None`` there --
a locale whose two pieces claimed the same letter would be unparseable, and the
honest encoding of "Dutch has no pawn letter" is the absence of one.

Canonical form
--------------
Everything in Caissa is stored as **English SAN** -- ``Nf3``, ``O-O``, ``exd5``,
``e8=Q+`` -- exactly as :mod:`chess` produces it.  A locale is a rendering, not
a storage format (SPEC 5.5: the move is not text).  :func:`to_language` and
:func:`from_language` are exact inverses on well-formed SAN; the round-trip is
tested over 100k real moves per locale.

Detection
---------
:func:`detect_language` returns a *ranked* list with a confidence, and abstains
rather than guessing.  Abstention is not a failure mode here, it is the product
requirement: a wrong language silently corrupts a book, while an abstention
falls back to the PGN standard (English) and costs nothing when the text really
was English.

It also reports something more useful than a language when the language is
undecidable: :attr:`Detection.consensus_pieces`.  ``Cf3 Dd8 Tf1`` narrows the
text to {pt, es, fr, it} and no further -- but all four map ``R`` to the king,
so the question that actually matters is answered even though the language is
not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping, Sequence

__all__ = [
    "ENGLISH_PIECES",
    "FIGURINE_OUTLINE",
    "FIGURINE_SOLID",
    "LOCALES",
    "Detection",
    "LanguageScore",
    "MoveParts",
    "NotationLocale",
    "available_locales",
    "detect_language",
    "figurine",
    "from_language",
    "get_locale",
    "parse_san",
    "to_language",
]

#: The canonical piece letters.  Everything else in this module is a bijection
#: onto this alphabet.
ENGLISH_PIECES: Final[tuple[str, ...]] = ("K", "Q", "R", "B", "N", "P")

#: U+2654..U+2659 -- the *white* (outline) figurines.
FIGURINE_OUTLINE: Final[Mapping[str, str]] = MappingProxyType(
    {"K": "\u2654", "Q": "\u2655", "R": "\u2656", "B": "\u2657", "N": "\u2658", "P": "\u2659"}
)

#: U+265A..U+265F -- the *black* (solid) figurines.
FIGURINE_SOLID: Final[Mapping[str, str]] = MappingProxyType(
    {"K": "\u265a", "Q": "\u265b", "R": "\u265c", "B": "\u265d", "N": "\u265e", "P": "\u265f"}
)

#: Every figurine, either fill, back to its English letter.  Books mix the two
#: sets freely -- the printed glyph tracks the *font*, not the side to move, and
#: `ChessVisionOFF/text/notacao.py` documents the same finding ("um conjunto so
#: de glifos para os dois lados").
_FIGURINE_TO_LETTER: Final[Mapping[str, str]] = MappingProxyType(
    {glyph: letter for table in (FIGURINE_OUTLINE, FIGURINE_SOLID) for letter, glyph in table.items()}
)


@dataclass(frozen=True)
class MoveParts:
    """A SAN move taken apart, so that rendering is a pure re-assembly.

    Exactly one of :attr:`castling` and :attr:`target` is set.  ``suffix`` holds
    only the check/mate mark; evaluation glyphs (``!?``, ``+-``) are NAGs and
    belong to :mod:`caissa.notation.nag_table`, not here.
    """

    piece: str = ""
    """English piece letter, or ``""`` for a pawn move."""

    disambiguator: str = ""
    """The file, rank or square that resolves an ambiguity: the ``b`` of ``Nbd2``."""

    capture: bool = False
    target: str = ""
    """Destination square, e.g. ``"d5"``."""

    promotion: str = ""
    """English piece letter promoted to, or ``""``."""

    suffix: str = ""
    """``"+"``, ``"#"`` or ``""``."""

    castling: str = ""
    """``"O-O"``, ``"O-O-O"`` or ``""``."""

    @property
    def is_castling(self) -> bool:
        return bool(self.castling)


# --------------------------------------------------------------------------- #
# Locale table
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NotationLocale:
    """Everything that changes when the same move is printed in another language."""

    code: str
    name: str
    endonym: str

    #: English letter -> the letter(s) this locale prints.  A value may be more
    #: than one character (Russian ``Кр``); parsing is longest-match-first.
    #: ``None`` means "this locale prints no letter for that piece", which is
    #: only ever the pawn.
    king: str
    queen: str
    rook: str
    bishop: str
    knight: str
    pawn: str | None = "P"

    castling_short: str = "O-O"
    castling_long: str = "O-O-O"
    #: Input-only spellings.  ``0-0`` (digit zero) is the ASCII form that every
    #: European publisher uses and that OCR produces from ``O-O`` half the time;
    #: ``enroque`` / ``arrocco`` / ``roque`` are the words books spell out in
    #: prose.  Rendering never uses these -- they exist so that reading does.
    castling_aliases: tuple[str, ...] = ()

    check: str = "+"
    mate: str = "#"
    #: Older books write the mark as a word: ``ch``/``mate`` (pt, en pre-1950),
    #: ``Schach``/``matt`` (de), ``jaque``/``mate`` (es).  Input only.
    check_aliases: tuple[str, ...] = ()
    mate_aliases: tuple[str, ...] = ()

    capture: str = "x"
    capture_aliases: tuple[str, ...] = (":",)
    promotion: str = "="
    promotion_aliases: tuple[str, ...] = ("(", "/")

    #: Function words and chess vocabulary that only this language uses.  Used
    #: *only* by :func:`detect_language`, and only to break ties that the piece
    #: letters cannot break -- Spanish and Italian have identical piece tables.
    lexicon: tuple[str, ...] = ()

    # -- derived ---------------------------------------------------------- #

    @property
    def pieces(self) -> Mapping[str, str]:
        """English letter -> local letter, pawn included only when it has one."""
        table = {
            "K": self.king,
            "Q": self.queen,
            "R": self.rook,
            "B": self.bishop,
            "N": self.knight,
        }
        if self.pawn is not None:
            table["P"] = self.pawn
        return MappingProxyType(table)

    @property
    def reverse_pieces(self) -> Mapping[str, str]:
        """Local letter -> English letter."""
        return MappingProxyType({local: english for english, local in self.pieces.items()})

    @property
    def move_letters(self) -> frozenset[str]:
        """The letters that can *start a move* in this locale -- the pawn is excluded.

        No locale prints its pawn letter in front of a pawn move; ``P`` in
        ``Pe4`` is an artefact of engine output, not of books.  Including it
        would make every Dutch knight move ambiguous with an English pawn move
        for no gain.
        """
        return frozenset(letter for english, letter in self.pieces.items() if english != "P")

    @property
    def collides_with_english(self) -> frozenset[str]:
        """Letters this locale reuses for a *different* piece than English does.

        These are the characters that silently corrupt a game when the language
        is guessed wrong.  ``R`` for pt/es/fr/it, ``B`` for de, ``P`` for nl.
        """
        english = set(ENGLISH_PIECES)
        return frozenset(
            local
            for eng, local in self.pieces.items()
            if local in english and local != eng
        )

    def ambiguity_set(self) -> Mapping[str, frozenset[str]]:
        """Local letter -> every locale code that also uses it, for another piece.

        This is the "which letters collide with which other language" map.  A
        letter with an empty set is decisive evidence for this locale.
        """
        out: dict[str, frozenset[str]] = {}
        for local, english in self.reverse_pieces.items():
            rivals = {
                other.code
                for other in LOCALES.values()
                if other.code != self.code and other.reverse_pieces.get(local, english) != english
            }
            out[local] = frozenset(rivals)
        return MappingProxyType(out)


def _locale(**kwargs: object) -> NotationLocale:
    return NotationLocale(**kwargs)  # type: ignore[arg-type]


#: The eight real locales plus two figurine pseudo-locales.
LOCALES: Final[Mapping[str, NotationLocale]] = MappingProxyType(
    {
        loc.code: loc
        for loc in (
            NotationLocale(
                code="en",
                name="English",
                endonym="English",
                king="K",
                queen="Q",
                rook="R",
                bishop="B",
                knight="N",
                pawn="P",
                castling_aliases=("0-0", "0-0-0", "OO", "OOO", "castles"),
                check_aliases=("ch",),
                mate_aliases=("mate", "++"),
                lexicon=(
                    "white",
                    "black",
                    "the",
                    "and",
                    "with",
                    "knight",
                    "bishop",
                    "queen",
                    "rook",
                    "king",
                    "pawn",
                    "check",
                    "mate",
                    "game",
                    "move",
                ),
            ),
            NotationLocale(
                code="pt",
                name="Portuguese",
                endonym="português",
                king="R",
                queen="D",
                rook="T",
                bishop="B",
                knight="C",
                pawn="P",
                castling_aliases=("0-0", "0-0-0", "roque", "roque-grande"),
                check_aliases=("ch", "xeque", "+"),
                mate_aliases=("mate", "mat"),
                lexicon=(
                    "brancas",
                    "pretas",
                    "lance",
                    "peça",
                    "peao",
                    "peão",
                    "cavalo",
                    "bispo",
                    "torre",
                    "dama",
                    "rei",
                    "xeque",
                    "partida",
                    "não",
                    "com",
                    "que",
                    "para",
                    "melhor",
                    "posição",
                    "abertura",
                    "final",
                    "ameaça",
                ),
            ),
            NotationLocale(
                code="es",
                name="Spanish",
                endonym="español",
                king="R",
                queen="D",
                rook="T",
                bishop="A",
                knight="C",
                pawn="P",
                castling_aliases=("0-0", "0-0-0", "enroque", "enroque corto", "enroque largo"),
                check_aliases=("jaque", "j"),
                mate_aliases=("mate",),
                lexicon=(
                    "blancas",
                    "negras",
                    "jugada",
                    "pieza",
                    "peon",
                    "peón",
                    "caballo",
                    "alfil",
                    "torre",
                    "dama",
                    "rey",
                    "jaque",
                    "partida",
                    "pero",
                    "para",
                    "posición",
                    "apertura",
                    "amenaza",
                    "del",
                    "los",
                    "las",
                ),
            ),
            NotationLocale(
                code="fr",
                name="French",
                endonym="français",
                king="R",
                queen="D",
                rook="T",
                bishop="F",
                knight="C",
                pawn="P",
                castling_aliases=("0-0", "0-0-0", "roque", "petit roque", "grand roque"),
                check_aliases=("éch", "ech"),
                mate_aliases=("mat",),
                lexicon=(
                    "blancs",
                    "noirs",
                    "coup",
                    "pièce",
                    "pion",
                    "cavalier",
                    "fou",
                    "tour",
                    "dame",
                    "roi",
                    "échec",
                    "partie",
                    "pour",
                    "les",
                    "des",
                    "une",
                    "position",
                    "ouverture",
                    "menace",
                ),
            ),
            NotationLocale(
                code="it",
                name="Italian",
                endonym="italiano",
                king="R",
                queen="D",
                rook="T",
                bishop="A",
                knight="C",
                pawn="P",
                castling_aliases=("0-0", "0-0-0", "arrocco", "arrocco corto", "arrocco lungo"),
                check_aliases=("scacco",),
                mate_aliases=("matto",),
                lexicon=(
                    "bianco",
                    "nero",
                    "bianchi",
                    "neri",
                    "mossa",
                    "pezzo",
                    "pedone",
                    "cavallo",
                    "alfiere",
                    "torre",
                    "donna",
                    "scacco",
                    "partita",
                    "che",
                    "per",
                    "della",
                    "posizione",
                    "apertura",
                    "minaccia",
                ),
            ),
            NotationLocale(
                code="de",
                name="German",
                endonym="Deutsch",
                king="K",
                queen="D",
                rook="T",
                bishop="L",
                knight="S",
                pawn="B",
                castling_aliases=("0-0", "0-0-0", "rochade", "kurze rochade", "lange rochade"),
                check_aliases=("schach", "+"),
                mate_aliases=("matt",),
                lexicon=(
                    "weiss",
                    "weiß",
                    "schwarz",
                    "zug",
                    "figur",
                    "bauer",
                    "springer",
                    "läufer",
                    "laufer",
                    "turm",
                    "dame",
                    "könig",
                    "konig",
                    "schach",
                    "partie",
                    "und",
                    "der",
                    "die",
                    "das",
                    "nicht",
                    "stellung",
                    "eröffnung",
                    "droht",
                ),
            ),
            NotationLocale(
                code="nl",
                name="Dutch",
                endonym="Nederlands",
                king="K",
                queen="D",
                rook="T",
                bishop="L",
                knight="P",
                # Dutch calls the pawn "pion" but prints no letter for it -- and
                # `P` is already the knight.  See the module docstring.
                pawn=None,
                castling_aliases=("0-0", "0-0-0", "rokade", "korte rokade", "lange rokade"),
                check_aliases=("schaak",),
                mate_aliases=("mat",),
                lexicon=(
                    "wit",
                    "zwart",
                    "zet",
                    "stuk",
                    "pion",
                    "paard",
                    "loper",
                    "toren",
                    "dame",
                    "koning",
                    "schaak",
                    "partij",
                    "niet",
                    "het",
                    "een",
                    "van",
                    "stelling",
                    "opening",
                    "dreigt",
                ),
            ),
            NotationLocale(
                code="ru",
                name="Russian",
                endonym="русский",
                # `Кр` is two Cyrillic characters and `К` alone is the knight:
                # parsing must be longest-match-first or every king move becomes
                # a knight move.
                king="\u041a\u0440",
                queen="\u0424",
                rook="\u041b",
                bishop="\u0421",
                knight="\u041a",
                pawn="\u043f",
                castling_aliases=("0-0", "0-0-0", "\u043e-\u043e", "\u043e-\u043e-\u043e"),
                check_aliases=("\u0448\u0430\u0445", "+"),
                # Older Russian books mark mate with `x`, which collides with the
                # capture sign -- input only, and only in final position.
                mate_aliases=("\u043c\u0430\u0442", "x"),
                capture_aliases=(":", "\u0445"),
                lexicon=(
                    "\u0431\u0435\u043b\u044b\u0435",
                    "\u0447\u0451\u0440\u043d\u044b\u0435",
                    "\u0447\u0435\u0440\u043d\u044b\u0435",
                    "\u0445\u043e\u0434",
                    "\u0444\u0438\u0433\u0443\u0440\u0430",
                    "\u043f\u0435\u0448\u043a\u0430",
                    "\u043a\u043e\u043d\u044c",
                    "\u0441\u043b\u043e\u043d",
                    "\u043b\u0430\u0434\u044c\u044f",
                    "\u0444\u0435\u0440\u0437\u044c",
                    "\u043a\u043e\u0440\u043e\u043b\u044c",
                    "\u0448\u0430\u0445",
                    "\u043f\u0430\u0440\u0442\u0438\u044f",
                    "\u043f\u043e\u0437\u0438\u0446\u0438\u044f",
                ),
            ),
            NotationLocale(
                code="figurine",
                name="Figurine (outline)",
                endonym="\u2658f3",
                king=FIGURINE_OUTLINE["K"],
                queen=FIGURINE_OUTLINE["Q"],
                rook=FIGURINE_OUTLINE["R"],
                bishop=FIGURINE_OUTLINE["B"],
                knight=FIGURINE_OUTLINE["N"],
                pawn=FIGURINE_OUTLINE["P"],
                castling_aliases=("0-0", "0-0-0"),
            ),
            NotationLocale(
                code="figurine-solid",
                name="Figurine (solid)",
                endonym="\u265ef3",
                king=FIGURINE_SOLID["K"],
                queen=FIGURINE_SOLID["Q"],
                rook=FIGURINE_SOLID["R"],
                bishop=FIGURINE_SOLID["B"],
                knight=FIGURINE_SOLID["N"],
                pawn=FIGURINE_SOLID["P"],
                castling_aliases=("0-0", "0-0-0"),
            ),
        )
    }
)

#: The locales a detector may return.  The figurine pseudo-locales are excluded
#: because they are a *typeface*, not a language: a figurine book still spells
#: its prose in Portuguese or German, and reporting "figurine" as the language
#: would throw that away.  :func:`from_language` reads figurines in every locale.
DETECTABLE: Final[tuple[str, ...]] = ("en", "pt", "es", "fr", "it", "de", "nl", "ru")


def available_locales() -> tuple[str, ...]:
    """Every locale code, in table order."""
    return tuple(LOCALES)


def get_locale(code: str) -> NotationLocale:
    """The locale for ``code``.

    Raises:
        KeyError: if ``code`` is not a known locale, with the list of valid ones.
    """
    try:
        return LOCALES[code]
    except KeyError:
        raise KeyError(f"unknown notation locale {code!r}; known: {', '.join(LOCALES)}") from None


# --------------------------------------------------------------------------- #
# SAN <-> locale
# --------------------------------------------------------------------------- #

_SAN_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    ^(?:
        (?P<castling>O-O-O|O-O)
      | (?P<piece>[KQRBN])?
        (?P<disamb>[a-h][1-8]|[a-h]|[1-8])?
        (?P<capture>x)?
        (?P<target>[a-h][1-8])
        (?:=(?P<promotion>[QRBNK]))?
    )
    (?P<suffix>[+#])?$
    """,
    re.VERBOSE,
)


def parse_san(san: str) -> MoveParts | None:
    """Take an English SAN move apart, or ``None`` when it is not one.

    Strict by design: a token this rejects is a repair problem, not a rendering
    problem, and belongs to :mod:`caissa.notation.legality_repair`.
    """
    match = _SAN_RE.match(san)
    if match is None:
        return None
    if match.group("castling"):
        return MoveParts(castling=match.group("castling"), suffix=match.group("suffix") or "")
    return MoveParts(
        piece=match.group("piece") or "",
        disambiguator=match.group("disamb") or "",
        capture=bool(match.group("capture")),
        target=match.group("target"),
        promotion=match.group("promotion") or "",
        suffix=match.group("suffix") or "",
    )


def _castling_pattern(locale: NotationLocale) -> str:
    forms = {locale.castling_long, locale.castling_short}
    for alias in locale.castling_aliases:
        if re.fullmatch(r"[0Oo0\u043e]-[0Oo\u043e](?:-[0Oo\u043e])?", alias):
            forms.add(alias)
    # Longest first: `O-O-O` must win over `O-O`.
    return "|".join(re.escape(form) for form in sorted(forms, key=len, reverse=True))


def _piece_pattern(locale: NotationLocale) -> str:
    """Alternation of every letter that can begin a move, longest first.

    Longest-first is the whole of the Russian problem: ``Кр`` and ``К`` share a
    prefix, and a shortest-first alternation reads every king move as a knight
    move followed by a stray ``р``.
    """
    letters = sorted(locale.move_letters, key=len, reverse=True)
    # Figurines are always readable, whatever the locale: a Portuguese book that
    # prints figurines is still a Portuguese book (SPEC 5.5).
    letters += sorted(set(_FIGURINE_TO_LETTER) - set(letters))
    return "|".join(re.escape(letter) for letter in letters)


_LOCAL_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _local_re(locale: NotationLocale) -> re.Pattern[str]:
    cached = _LOCAL_RE_CACHE.get(locale.code)
    if cached is not None:
        return cached

    captures = "".join(re.escape(sign) for sign in (locale.capture, *locale.capture_aliases))
    promo = "".join(re.escape(sign) for sign in (locale.promotion, *locale.promotion_aliases))
    marks = "".join(
        re.escape(mark) for mark in dict.fromkeys((locale.check, locale.mate, "+", "#"))
    )
    pattern = re.compile(
        rf"""
        ^(?:
            (?P<castling>{_castling_pattern(locale)})
          | (?P<piece>{_piece_pattern(locale)})?
            (?P<disamb>[a-h][1-8]|[a-h]|[1-8])?
            (?P<capture>[{captures}])?
            (?P<target>[a-h][1-8])
            (?:[{promo}](?P<promotion>{_piece_pattern(locale)}))?
        )
        (?P<suffix>[{marks}])?$
        """,
        re.VERBOSE,
    )
    _LOCAL_RE_CACHE[locale.code] = pattern
    return pattern


def _to_english_letter(locale: NotationLocale, letter: str) -> str | None:
    if letter in _FIGURINE_TO_LETTER:
        return _FIGURINE_TO_LETTER[letter]
    return locale.reverse_pieces.get(letter)


def to_language(san: str, lang: str) -> str:
    """Render an English SAN move in ``lang``.

    ``to_language("Nf3", "pt") == "Cf3"``; ``to_language("Nf3", "figurine")``
    gives ``"\u2658f3"``.  A token that is not well-formed SAN comes back
    unchanged -- rendering is not the place to fix a broken move, and mangling
    it here would hide the problem from the repair pass.
    """
    locale = get_locale(lang)
    parts = parse_san(san)
    if parts is None:
        return san

    if parts.is_castling:
        body = locale.castling_long if parts.castling == "O-O-O" else locale.castling_short
        return body + _render_suffix(locale, parts.suffix)

    piece = locale.pieces.get(parts.piece, parts.piece) if parts.piece else ""
    promotion = ""
    if parts.promotion:
        promotion = locale.promotion + locale.pieces.get(parts.promotion, parts.promotion)
    capture = locale.capture if parts.capture else ""
    return f"{piece}{parts.disambiguator}{capture}{parts.target}{promotion}" + _render_suffix(
        locale, parts.suffix
    )


def _render_suffix(locale: NotationLocale, suffix: str) -> str:
    if suffix == "+":
        return locale.check
    if suffix == "#":
        return locale.mate
    return ""


def from_language(text: str, lang: str) -> str | None:
    """Read a move written in ``lang`` and return canonical English SAN.

    ``None`` when ``text`` is not a well-formed move *in that locale* -- which
    is the answer that matters: ``from_language("Sf3", "pt")`` is ``None``
    because ``S`` is not a Portuguese piece, and that ``None`` is exactly the
    evidence :func:`detect_language` scores against.
    """
    locale = get_locale(lang)
    match = _local_re(locale).match(text.strip())
    if match is None:
        return None

    suffix = match.group("suffix") or ""
    if suffix and suffix not in ("+", "#"):
        suffix = "+" if suffix == locale.check else "#"

    if match.group("castling"):
        raw = match.group("castling")
        long = raw.count("-") == 2
        return ("O-O-O" if long else "O-O") + suffix

    piece = ""
    if match.group("piece"):
        english = _to_english_letter(locale, match.group("piece"))
        if english is None or english == "P":
            # A leading pawn letter is not SAN; `Pe4` means `e4`.  Dutch never
            # reaches this branch because its pawn has no letter.
            return None
        piece = english

    promotion = ""
    if match.group("promotion"):
        english = _to_english_letter(locale, match.group("promotion"))
        if english is None or english == "P":
            return None
        promotion = f"={english}"

    capture = "x" if match.group("capture") else ""
    return f"{piece}{match.group('disamb') or ''}{capture}{match.group('target')}{promotion}{suffix}"


def figurine(san: str, *, solid: bool = False) -> str:
    """``to_language`` for the figurine pseudo-locales, spelled as a flag."""
    return to_language(san, "figurine-solid" if solid else "figurine")


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

#: Anything that could be the head of a move in *any* locale.  Deliberately
#: broad -- the scoring, not the regex, decides what the evidence means.
_ALL_MOVE_LETTERS: Final[frozenset[str]] = frozenset(
    letter for loc in LOCALES.values() for letter in loc.move_letters
)

_CANDIDATE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?P<head>"
    + "|".join(re.escape(letter) for letter in sorted(_ALL_MOVE_LETTERS, key=len, reverse=True))
    + r")(?P<rest>(?:[a-h][1-8]|[a-h]|[1-8])?[x:\u0445]?[a-h][1-8])(?![\w])"
)

_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[^\W\d_]{2,}", re.UNICODE)

#: Minimum number of piece-letter observations before a ranking may be trusted.
#: One `Cf3` in a page of English prose is a typo, not a language.
MIN_PIECE_EVIDENCE: Final[int] = 2

#: How far ahead of the runner-up the leader must be, as a share of the total
#: score, before the result stops being an abstention.
DECISION_MARGIN: Final[float] = 0.12

#: What one unexplainable move head costs a locale.  Calibrated against the
#: weighted hit scale (0.17 for a letter six locales share, 1.0 for one only
#: this locale has): a single miss cancels roughly six shared hits.
MISS_PENALTY: Final[float] = 1.0


@dataclass(frozen=True)
class LanguageScore:
    """One locale's standing in a detection, and why."""

    code: str
    score: float
    """Normalised to ``[0, 1]`` across the ranking; the ranking sums to 1."""

    piece_hits: int
    """Move heads this locale can explain."""

    piece_misses: int
    """Move heads it cannot -- a single one is near-fatal evidence."""

    lexicon_hits: float
    """Exclusivity-weighted vocabulary score; a word shared by *n* locales is
    worth ``1/n``."""

    evidence: tuple[str, ...] = ()
    """Up to a handful of the actual tokens that voted, for the UI to show."""


@dataclass(frozen=True)
class Detection:
    """The result of :func:`detect_language`.

    ``best`` is ``None`` whenever :attr:`abstained` is true.  Callers must treat
    that as "use the PGN standard, English, and say so" -- never as "probably
    the first one in the list".
    """

    ranked: tuple[LanguageScore, ...]
    abstained: bool
    reason: str
    consensus_pieces: Mapping[str, str] | None = None
    """Local letter -> English letter, when every plausible locale agrees.

    Present even when the language itself is undecidable: ``Cf3 Dd8 Tf1``
    narrows a text to {pt, es, fr, it}, which is an abstention *and* a complete
    answer to "is ``R`` the king here?" -- all four say yes.
    """

    @property
    def best(self) -> str | None:
        """The winning locale code, or ``None`` if the detector abstained."""
        if self.abstained or not self.ranked:
            return None
        return self.ranked[0].code

    @property
    def confidence(self) -> float:
        """Score of the leader; ``0.0`` when there is no ranking at all."""
        return self.ranked[0].score if self.ranked else 0.0

    def piece_map(self) -> Mapping[str, str]:
        """The letter->English map to actually use, abstention included.

        Falls back to :attr:`consensus_pieces` when the language is undecided,
        and to the empty map (i.e. plain English SAN) when even that is unknown.
        """
        if self.best is not None:
            return get_locale(self.best).reverse_pieces
        return self.consensus_pieces if self.consensus_pieces is not None else MappingProxyType({})


def _piece_heads(sample: str) -> list[str]:
    """Every move-looking token's leading letter, in order of appearance."""
    return [match.group("head") for match in _CANDIDATE_RE.finditer(sample)]


def _letter_owners() -> Mapping[str, int]:
    """Move letter -> how many detectable locales use it.

    ``S`` is German alone; ``T`` is six locales.  Counting them the same is what
    lets a page of shared ``T`` and ``D`` outweigh the one ``A`` that actually
    says which language it is -- which is how a Spanish book gets read as
    Italian.  The lexicon is weighted the same way, for the same reason.
    """
    counts: dict[str, int] = {}
    for code in DETECTABLE:
        for letter in LOCALES[code].move_letters:
            counts[letter] = counts.get(letter, 0) + 1
    return MappingProxyType(counts)


def _lexicon_owners() -> Mapping[str, int]:
    """Word -> how many locales claim it.

    ``torre`` is Portuguese, Spanish *and* Italian; ``brancas`` is only
    Portuguese.  Scoring them the same would let three shared nouns outvote one
    decisive one, which is how Spanish books get read as Italian.
    """
    counts: dict[str, int] = {}
    for locale in LOCALES.values():
        for word in {w.lower() for w in locale.lexicon}:
            counts[word] = counts.get(word, 0) + 1
    return MappingProxyType(counts)


_LETTER_OWNERS: Final[Mapping[str, int]] = _letter_owners()
_LEXICON_OWNERS: Final[Mapping[str, int]] = _lexicon_owners()


def _lexicon_hits(sample: str, locale: NotationLocale) -> tuple[float, tuple[str, ...]]:
    """Exclusivity-weighted vocabulary score, and the words that produced it."""
    if not locale.lexicon:
        return (0.0, ())
    words = {unicodedata.normalize("NFC", word.lower()) for word in _WORD_RE.findall(sample)}
    found = tuple(sorted(words & {w.lower() for w in locale.lexicon}))
    weight = sum(1.0 / _LEXICON_OWNERS.get(word, 1) for word in found)
    return (weight, found[:6])


def detect_language(
    sample: str,
    *,
    candidates: Sequence[str] = DETECTABLE,
    min_evidence: int = MIN_PIECE_EVIDENCE,
    margin: float = DECISION_MARGIN,
) -> Detection:
    """Rank the notation locales that could have produced ``sample``.

    The scoring has two independent signals and they are deliberately unequal:

    * **Piece letters**, each weighted by how few locales use it.  ``S`` is
      German alone and counts 1.0; ``T`` belongs to six locales and counts
      0.167.  A locale that cannot explain an observed head takes a flat
      :data:`MISS_PENALTY` -- ``Sf3`` is not Portuguese, full stop, and one such
      token outweighs several agreeable ones.  This is the signal the corpus
      actually provides: a scanned page gives dozens of moves and often no
      prose at all.

    * **Vocabulary** (weight 0.9 per distinct word, divided by how many locales
      claim that word).  Only there to break ties the letters cannot break.
      Spanish and Italian have *identical* piece tables -- ``R D T A C P``
      both -- so no amount of notation separates them and only the prose can.

    The detector abstains when the evidence is thin (fewer than ``min_evidence``
    move heads and no vocabulary) or when the leader's lead over the runner-up
    is under ``margin``.  Abstaining is the correct answer for ``1.e4 e5 2.d4``:
    the text is real notation in eight languages at once.
    """
    heads = _piece_heads(sample)
    head_counts: dict[str, int] = {}
    for head in heads:
        head_counts[head] = head_counts.get(head, 0) + 1

    scores: list[LanguageScore] = []
    for code in candidates:
        locale = LOCALES[code]
        letters = locale.move_letters
        hits = sum(count for letter, count in head_counts.items() if letter in letters)
        misses = sum(count for letter, count in head_counts.items() if letter not in letters)
        weighted_hits = sum(
            count / _LETTER_OWNERS.get(letter, 1)
            for letter, count in head_counts.items()
            if letter in letters
        )
        lex_count, lex_words = _lexicon_hits(sample, locale)

        # A miss outweighs many hits, because hits are shared and misses are
        # not: `T` agrees with six locales, `S` disagrees with seven.  The flat
        # penalty is deliberate -- "this locale has no such letter" is hard
        # evidence whose strength does not depend on who else has it.
        raw = weighted_hits + 0.9 * lex_count - MISS_PENALTY * misses
        evidence = tuple(
            sorted({letter for letter in head_counts if letter in letters})
        )[:6] + lex_words
        scores.append(
            LanguageScore(
                code=code,
                score=max(raw, 0.0),
                piece_hits=hits,
                piece_misses=misses,
                lexicon_hits=lex_count,
                evidence=evidence,
            )
        )

    total = sum(score.score for score in scores)
    if total <= 0.0:
        ranked = tuple(
            sorted(scores, key=lambda s: (-s.score, s.code))
        )
        return Detection(
            ranked=tuple(
                LanguageScore(s.code, 0.0, s.piece_hits, s.piece_misses, s.lexicon_hits, s.evidence)
                for s in ranked
            ),
            abstained=True,
            reason="no evidence for any locale",
            consensus_pieces=None,
        )

    normalised = tuple(
        sorted(
            (
                LanguageScore(
                    s.code,
                    s.score / total,
                    s.piece_hits,
                    s.piece_misses,
                    s.lexicon_hits,
                    s.evidence,
                )
                for s in scores
            ),
            key=lambda s: (-s.score, s.code),
        )
    )

    leader = normalised[0]
    runner_up = normalised[1] if len(normalised) > 1 else None
    lead = leader.score - (runner_up.score if runner_up else 0.0)

    plausible = _plausible_locales(normalised)
    consensus = _consensus_pieces(plausible)

    if len(heads) < min_evidence and leader.lexicon_hits <= 0.0:
        return Detection(
            ranked=normalised,
            abstained=True,
            reason=(
                f"only {len(heads)} piece-letter observation(s) and no vocabulary; "
                f"need {min_evidence}"
            ),
            consensus_pieces=consensus,
        )

    if lead < margin:
        tied = ", ".join(s.code for s in normalised if abs(s.score - leader.score) < 1e-9)
        return Detection(
            ranked=normalised,
            abstained=True,
            reason=f"lead of {lead:.3f} is under the {margin} margin; tied: {tied}",
            consensus_pieces=consensus,
        )

    return Detection(
        ranked=normalised,
        abstained=False,
        reason=f"{leader.code} leads by {lead:.3f}",
        consensus_pieces=consensus,
    )


def _plausible_locales(ranked: Sequence[LanguageScore]) -> tuple[str, ...]:
    """The locales still in contention: no misses, and within reach of the leader."""
    alive = [score for score in ranked if score.piece_misses == 0 and score.score > 0.0]
    if not alive:
        return ()
    top = alive[0].score
    return tuple(score.code for score in alive if score.score >= top - 1e-9)


def _consensus_pieces(codes: Sequence[str]) -> Mapping[str, str] | None:
    """The letter->English map every locale in ``codes`` agrees on, or ``None``.

    A letter is in the map only when **every** locale still in contention both
    defines it and reads it the same way.  Anything less is left out rather than
    guessed: with {pt, es, fr, it} alive, all four read ``R`` as the king, so
    ``R`` is in -- but only Portuguese knows ``B``, so ``B`` stays out and a
    ``Bd3`` in that text remains an open question for the legality pass.
    The result is ``None`` only when nothing at all is agreed.
    """
    if not codes:
        return None
    maps = [dict(LOCALES[code].reverse_pieces) for code in codes]
    merged: dict[str, str] = {}
    for letter in {key for table in maps for key in table}:
        readings = {table.get(letter) for table in maps}
        if len(readings) != 1:
            continue
        reading = next(iter(readings))
        if reading is not None:
            merged[letter] = reading
    return MappingProxyType(merged) if merged else None
