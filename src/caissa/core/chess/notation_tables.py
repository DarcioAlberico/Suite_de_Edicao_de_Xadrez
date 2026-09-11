"""Piece-letter tables and SAN translation between languages and figurine.

This is the data half of ADR-0008 ("tabelas de idioma por peca, mantidas como
dado") and the machinery behind SPEC section 5.5: the IR stores one canonical
English SAN per move, and rendering in Portuguese ("Cf3"), German ("Sf3"),
Russian ("Кf3") or figurine ("♞f3") is a projection of that same value.
Translation never touches the document -- it is a display decision, reversible
at any time, which is exactly why a move is not text.

Everything here is pure standard library. Legality reasoning (does this SAN
describe a legal move from this position?) belongs to the notation subsystem
and does use ``python-chess``; this module is the lexical layer underneath it.

The canonical form is always English SAN with ``O-O`` castling, ``x`` for
captures and ``=`` before a promotion piece. :func:`from_language` normalises
every accepted variant back to that form, so
``from_language(to_language(san, lang), lang) == san`` holds for every SAN this
module accepts -- the round trip the F6 gate requires.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "DEFAULT_LANGUAGE",
    "FIGURINE_BLACK",
    "FIGURINE_WHITE",
    "PIECE_TABLES",
    "SUPPORTED_LANGUAGES",
    "FigurineSet",
    "LanguageTable",
    "MoveRenderStyle",
    "NotationError",
    "PieceType",
    "figurine_for_piece",
    "from_figurine",
    "from_language",
    "is_supported_language",
    "language_table",
    "piece_for_letter",
    "piece_letter",
    "render_san",
    "to_figurine",
    "to_language",
]

#: The language the IR stores moves in.
DEFAULT_LANGUAGE: Final = "en"


class NotationError(ValueError):
    """Raised when a token cannot be read as a move in the requested language."""


class PieceType(StrEnum):
    """The six piece types, named in English because the IR is English-canonical."""

    KING = "king"
    QUEEN = "queen"
    ROOK = "rook"
    BISHOP = "bishop"
    KNIGHT = "knight"
    PAWN = "pawn"


class FigurineSet(StrEnum):
    """Which Unicode chess glyph set a figurine rendering uses.

    ``BLACK`` -- the solid glyphs -- is the print convention: a figurine move is
    typeset with solid pieces regardless of whose move it is, because the
    outline glyphs disappear at text sizes on paper.
    """

    WHITE = "white"
    BLACK = "black"


class MoveRenderStyle(StrEnum):
    """How a :class:`~caissa.core.model.inline.Move` is rendered (SPEC 5.5).

    ``BOTH`` prints the figurine glyph followed by the language-letter form in
    parentheses, the convention used by bilingual and teaching editions.
    """

    FIGURINE = "figurine"
    LETTERS = "letters"
    BOTH = "both"


@dataclass(frozen=True, slots=True, kw_only=True)
class LanguageTable:
    """Piece letters and castling convention for one language.

    Attributes:
        code: BCP-47 language subtag.
        name: The language's name in that language.
        king: Letter for the king.
        queen: Letter for the queen.
        rook: Letter for the rook.
        bishop: Letter for the bishop.
        knight: Letter for the knight.
        pawn: Letter for the pawn. Informational only -- SAN never writes it,
            and :func:`from_language` deliberately ignores it, which is why the
            Dutch entry can be empty (Dutch has no pawn letter distinct from
            ``P``, which is already the knight, *Paard*).
        castle_short: How kingside castling is written.
        castle_long: How queenside castling is written.
    """

    code: str
    name: str
    king: str
    queen: str
    rook: str
    bishop: str
    knight: str
    pawn: str
    castle_short: str = "O-O"
    castle_long: str = "O-O-O"

    def letter(self, piece: PieceType) -> str:
        """Return this language's letter for a piece.

        Args:
            piece: The piece type.

        Returns:
            The letter, which may be empty for the pawn in some languages.
        """
        return str(getattr(self, _LETTER_ATTRS[piece]))

    def officer_letters(self) -> tuple[tuple[str, PieceType], ...]:
        """Return ``(letter, piece)`` pairs for every piece SAN can name.

        The pawn is excluded: SAN never writes a pawn letter, and including it
        would let a language whose pawn letter collides with another piece --
        Dutch ``P`` -- misparse.

        Returns:
            Pairs ordered longest letter first, so ``Kp`` matches before ``K``.
        """
        pairs = [
            (self.king, PieceType.KING),
            (self.queen, PieceType.QUEEN),
            (self.rook, PieceType.ROOK),
            (self.bishop, PieceType.BISHOP),
            (self.knight, PieceType.KNIGHT),
        ]
        return tuple(sorted((p for p in pairs if p[0]), key=lambda p: -len(p[0])))


_LETTER_ATTRS: Final[dict[PieceType, str]] = {
    PieceType.KING: "king",
    PieceType.QUEEN: "queen",
    PieceType.ROOK: "rook",
    PieceType.BISHOP: "bishop",
    PieceType.KNIGHT: "knight",
    PieceType.PAWN: "pawn",
}


def _table(
    code: str,
    name: str,
    letters: str,
    *,
    pawn: str,
    zero_castling: bool = False,
) -> LanguageTable:
    """Build a language table from a compact ``KQRBN`` letter string.

    Args:
        code: BCP-47 subtag.
        name: Endonym of the language.
        letters: Five letters in king, queen, rook, bishop, knight order,
            separated by spaces so that multi-character letters (Russian
            ``Kp``) are unambiguous.
        pawn: The pawn letter, or the empty string when the language has none
            that is distinct from another piece.
        zero_castling: Write castling with digit zero, the German and Russian
            convention.

    Returns:
        The table.
    """
    king, queen, rook, bishop, knight = letters.split()
    return LanguageTable(
        code=code,
        name=name,
        king=king,
        queen=queen,
        rook=rook,
        bishop=bishop,
        knight=knight,
        pawn=pawn,
        castle_short="0-0" if zero_castling else "O-O",
        castle_long="0-0-0" if zero_castling else "O-O-O",
    )


#: Piece letters by language. The eight required by the F1 brief come first;
#: the rest are the other languages that appear in the reference corpus.
PIECE_TABLES: Final[dict[str, LanguageTable]] = {
    table.code: table
    for table in (
        _table("en", "English", "K Q R B N", pawn="P"),
        _table("pt", "Portugues", "R D T B C", pawn="P"),
        _table("de", "Deutsch", "K D T L S", pawn="B", zero_castling=True),
        _table("es", "Espanol", "R D T A C", pawn="P"),
        _table("fr", "Francais", "R D T F C", pawn="P"),
        _table("it", "Italiano", "R D T A C", pawn="P"),
        _table("ru", "Russkij", "Кр Ф Л С К", pawn="п", zero_castling=True),
        _table("nl", "Nederlands", "K D T L P", pawn=""),
        _table("pl", "Polski", "K H W G S", pawn="p"),
        _table("cs", "Cestina", "K D V S J", pawn="p"),
        _table("hu", "Magyar", "K V B F H", pawn="g"),
        _table("da", "Dansk", "K D T L S", pawn="B"),
        _table("sv", "Svenska", "K D T L S", pawn="B"),
        _table("no", "Norsk", "K D T L S", pawn="B"),
        _table("fi", "Suomi", "K D T L R", pawn="s"),
        _table("ro", "Romana", "R D T N C", pawn="p"),
        _table("is", "Islenska", "K D H B R", pawn="p"),
        _table("ca", "Catala", "R D T A C", pawn="P"),
    )
}

#: Language codes this module can translate, sorted.
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = tuple(sorted(PIECE_TABLES))

#: Outline (white) Unicode chess glyphs.
FIGURINE_WHITE: Final[dict[PieceType, str]] = {
    PieceType.KING: "♔",
    PieceType.QUEEN: "♕",
    PieceType.ROOK: "♖",
    PieceType.BISHOP: "♗",
    PieceType.KNIGHT: "♘",
    PieceType.PAWN: "♙",
}

#: Solid (black) Unicode chess glyphs -- the print convention for figurine SAN.
FIGURINE_BLACK: Final[dict[PieceType, str]] = {
    PieceType.KING: "♚",
    PieceType.QUEEN: "♛",
    PieceType.ROOK: "♜",
    PieceType.BISHOP: "♝",
    PieceType.KNIGHT: "♞",
    PieceType.PAWN: "♟",
}

_FIGURINE_TO_PIECE: Final[dict[str, PieceType]] = {
    **{glyph: piece for piece, glyph in FIGURINE_WHITE.items()},
    **{glyph: piece for piece, glyph in FIGURINE_BLACK.items()},
}

_ENGLISH_LETTER: Final[dict[PieceType, str]] = {
    PieceType.KING: "K",
    PieceType.QUEEN: "Q",
    PieceType.ROOK: "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
    PieceType.PAWN: "P",
}

_PIECE_FOR_ENGLISH_LETTER: Final[dict[str, PieceType]] = {
    letter: piece for piece, letter in _ENGLISH_LETTER.items()
}

#: Tokens that pass through translation untouched: the two null-move spellings.
_NULL_MOVES: Final[frozenset[str]] = frozenset({"--", "Z0", "z0", "0000", "(null)"})

_DASHES: Final[dict[int, str]] = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
    }
)

#: Lowercase Cyrillic letters that are visually identical to Latin ones. Russian
#: notation uses Latin file letters, so an OCR pass over a Russian book routinely
#: returns the Cyrillic twin. Only lowercase is folded: the uppercase forms are
#: real piece letters (``С`` is the bishop, ``Х`` is nothing at all).
_CYRILLIC_HOMOGLYPHS: Final[dict[int, str]] = str.maketrans(
    {"а": "a", "с": "c", "е": "e", "х": "x", "ѕ": "s", "і": "i", "ј": "j"}
)

#: Number of dashes in the queenside castling token, ``O-O-O``.
_LONG_CASTLE_DASHES: Final = 2

_CASTLE_RE: Final = re.compile(r"^[O0o]-[O0o](?:-[O0o])?$")

_SAN_RE: Final = re.compile(
    r"^(?P<piece>[KQRBN])?"
    r"(?P<from_file>[a-h])?"
    r"(?P<from_rank>[1-8])?"
    r"(?P<capture>x)?"
    r"(?P<target>[a-h][1-8])"
    r"(?:=(?P<promotion>[QRBNK]))?$"
)


@dataclass(frozen=True, slots=True)
class _SanParts:
    """The pieces of a parsed canonical SAN token."""

    castling: str | None
    piece: PieceType | None
    body: str
    promotion: PieceType | None
    suffix: str


def is_supported_language(code: str) -> bool:
    """Report whether a language tag has a piece-letter table.

    Args:
        code: A BCP-47 tag; only the primary subtag is considered, so
            ``"pt-BR"`` matches ``"pt"``.

    Returns:
        ``True`` when the language can be translated.
    """
    return _primary_subtag(code) in PIECE_TABLES


def language_table(code: str) -> LanguageTable:
    """Return the piece-letter table for a language.

    Args:
        code: A BCP-47 tag; only the primary subtag is considered.

    Returns:
        The table.

    Raises:
        NotationError: If the language has no table.
    """
    primary = _primary_subtag(code)
    try:
        return PIECE_TABLES[primary]
    except KeyError as exc:
        available = ", ".join(SUPPORTED_LANGUAGES)
        msg = f"idioma sem tabela de pecas: {code!r}. Disponiveis: {available}."
        raise NotationError(msg) from exc


def piece_letter(piece: PieceType, language: str = DEFAULT_LANGUAGE) -> str:
    """Return the letter a language uses for a piece.

    Args:
        piece: The piece type.
        language: A BCP-47 tag.

    Returns:
        The letter; may be empty for the pawn in languages that have none.

    Raises:
        NotationError: If the language has no table.
    """
    return language_table(language).letter(piece)


def piece_for_letter(letter: str, language: str = DEFAULT_LANGUAGE) -> PieceType | None:
    """Return the piece a letter names in a language, or ``None``.

    Figurine glyphs are recognised in every language.

    Args:
        letter: A piece letter or figurine glyph.
        language: A BCP-47 tag.

    Returns:
        The piece type, or ``None`` when the letter names none.

    Raises:
        NotationError: If the language has no table.
    """
    if letter in _FIGURINE_TO_PIECE:
        return _FIGURINE_TO_PIECE[letter]
    table = language_table(language)
    for candidate, piece in table.officer_letters():
        if candidate == letter:
            return piece
    if table.pawn and letter == table.pawn:
        return PieceType.PAWN
    return None


def figurine_for_piece(piece: PieceType, figurine_set: FigurineSet = FigurineSet.BLACK) -> str:
    """Return the Unicode glyph for a piece.

    Args:
        piece: The piece type.
        figurine_set: Outline or solid glyphs.

    Returns:
        A single-character string.
    """
    mapping = FIGURINE_WHITE if figurine_set is FigurineSet.WHITE else FIGURINE_BLACK
    return mapping[piece]


def to_language(san: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Render a canonical English SAN token in another language.

    Args:
        san: Canonical English SAN, e.g. ``"Nf3"``, ``"O-O"``, ``"exd5"``,
            ``"e8=Q+"``.
        language: Target BCP-47 tag.

    Returns:
        The move written with that language's piece letters and castling
        convention.

    Raises:
        NotationError: If the token is not valid English SAN, or the language
            has no table.
    """
    stripped = san.strip()
    if stripped in _NULL_MOVES:
        return stripped
    table = language_table(language)
    parts = _split_canonical(stripped)
    if parts.castling is not None:
        castle = table.castle_long if parts.castling == "O-O-O" else table.castle_short
        return f"{castle}{parts.suffix}"
    prefix = table.letter(parts.piece) if parts.piece is not None else ""
    promotion = ""
    if parts.promotion is not None:
        promotion = f"={table.letter(parts.promotion)}"
    return f"{prefix}{parts.body}{promotion}{parts.suffix}"


def from_language(text: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Read a move written in some language and return canonical English SAN.

    Generous about input, strict about output. Accepted variants:

    * castling as ``O-O``, ``0-0``, ``o-o``, with any Unicode dash;
    * captures written ``x``, ``:`` or ``×``;
    * check written ``+`` or ``†``, mate written ``#``, ``++`` or
      ``‡``;
    * promotion written ``=Q``, ``(Q)`` or bare ``Q``;
    * figurine glyphs in place of the piece letter, in either glyph set.

    Args:
        text: The move as written.
        language: BCP-47 tag of the language it is written in.

    Returns:
        Canonical English SAN.

    Raises:
        NotationError: If the token cannot be read, or the language has no
            table.
    """
    raw = text.strip()
    if raw in _NULL_MOVES:
        return raw
    if not raw:
        msg = "lance vazio."
        raise NotationError(msg)
    table = language_table(language)
    work, suffix = _split_suffix(_normalise_symbols(raw))

    if _CASTLE_RE.match(work):
        canonical = "O-O-O" if work.count("-") == _LONG_CASTLE_DASHES else "O-O"
        return f"{canonical}{suffix}"

    piece, work = _take_leading_piece(work, table)
    work, promotion = _take_promotion(work, table)

    rebuilt = f"{_ENGLISH_LETTER[piece] if piece else ''}{work}"
    if promotion is not None:
        rebuilt += f"={_ENGLISH_LETTER[promotion]}"
    match = _SAN_RE.match(rebuilt)
    if match is None:
        msg = f"lance ilegivel em {language!r}: {text!r} (normalizado para {rebuilt!r})."
        raise NotationError(msg)
    return f"{rebuilt}{suffix}"


def to_figurine(san: str, figurine_set: FigurineSet = FigurineSet.BLACK) -> str:
    """Render a canonical English SAN token with a Unicode chess glyph.

    Args:
        san: Canonical English SAN.
        figurine_set: Outline or solid glyphs.

    Returns:
        The move with its piece letter replaced by a glyph. Pawn moves and
        castling are returned unchanged, which is the printing convention.

    Raises:
        NotationError: If the token is not valid English SAN.
    """
    stripped = san.strip()
    if stripped in _NULL_MOVES:
        return stripped
    parts = _split_canonical(stripped)
    if parts.castling is not None:
        return f"{parts.castling}{parts.suffix}"
    prefix = figurine_for_piece(parts.piece, figurine_set) if parts.piece is not None else ""
    promotion = ""
    if parts.promotion is not None:
        promotion = f"={figurine_for_piece(parts.promotion, figurine_set)}"
    return f"{prefix}{parts.body}{promotion}{parts.suffix}"


def from_figurine(text: str) -> str:
    """Read a figurine move and return canonical English SAN.

    Args:
        text: A move whose piece is written as a Unicode chess glyph.

    Returns:
        Canonical English SAN.

    Raises:
        NotationError: If the token cannot be read.
    """
    return from_language(text, DEFAULT_LANGUAGE)


def render_san(
    san: str,
    *,
    language: str = DEFAULT_LANGUAGE,
    style: MoveRenderStyle = MoveRenderStyle.LETTERS,
    figurine_set: FigurineSet = FigurineSet.BLACK,
) -> str:
    """Render a move the way a :class:`~caissa.core.model.inline.Move` asks for.

    Args:
        san: Canonical English SAN.
        language: Target language for letter forms.
        style: Figurine, language letters, or both.
        figurine_set: Which glyph set figurine forms use.

    Returns:
        The rendered move.

    Raises:
        NotationError: If the token is not valid English SAN, or the language
            has no table.
    """
    if style is MoveRenderStyle.FIGURINE:
        return to_figurine(san, figurine_set)
    letters = to_language(san, language)
    if style is MoveRenderStyle.LETTERS:
        return letters
    return f"{to_figurine(san, figurine_set)} ({letters})"


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _primary_subtag(code: str) -> str:
    """Return the lowercased primary subtag of a BCP-47 tag.

    Args:
        code: A language tag such as ``"pt-BR"``.

    Returns:
        The primary subtag, e.g. ``"pt"``.
    """
    return code.strip().replace("_", "-").split("-")[0].lower()


def _normalise_symbols(text: str) -> str:
    """Fold the punctuation variants that appear in printed notation.

    Args:
        text: A move token as written.

    Returns:
        The token with dashes, capture marks and check marks normalised.
    """
    work = text.translate(_DASHES).translate(_CYRILLIC_HOMOGLYPHS)
    work = work.replace("×", "x").replace("†", "+").replace("‡", "#")
    work = work.replace("≠", "#")
    # A colon between two move characters is the old capture mark.
    return re.sub(r"(?<=[A-Za-zЀ-ӿ♔-♟0-9]):(?=[a-h])", "x", work)


def _split_suffix(text: str) -> tuple[str, str]:
    """Split trailing check, mate and evaluation marks off a move token.

    Args:
        text: A move token with symbols already normalised.

    Returns:
        The move body and its canonical suffix, with ``++`` folded to ``#``.
    """
    body = text
    trailing: list[str] = []
    while body and body[-1] in "+#!?":
        trailing.append(body[-1])
        body = body[:-1]
    trailing.reverse()
    suffix = "".join(trailing)
    if suffix.startswith("++"):
        suffix = "#" + suffix[2:]
    return body, suffix


def _take_leading_piece(text: str, table: LanguageTable) -> tuple[PieceType | None, str]:
    """Strip a leading piece letter or figurine glyph.

    Args:
        text: A move body.
        table: The language table to match against.

    Returns:
        The piece named, or ``None``, and the remaining text.
    """
    if text and text[0] in _FIGURINE_TO_PIECE:
        return _FIGURINE_TO_PIECE[text[0]], text[1:]
    for letter, piece in table.officer_letters():
        if text.startswith(letter):
            return piece, text[len(letter) :]
    return None, text


def _take_promotion(text: str, table: LanguageTable) -> tuple[str, PieceType | None]:
    """Strip a trailing promotion indicator in any of its accepted spellings.

    Args:
        text: A move body with the leading piece already removed.
        table: The language table to match against.

    Returns:
        The remaining text and the promotion piece, or ``None``.
    """
    if text.endswith(")") and "(" in text:
        head, _, tail = text.rpartition("(")
        piece = _match_piece(tail[:-1], table)
        if piece is not None:
            return head, piece
        return text, None
    if "=" in text:
        head, _, tail = text.rpartition("=")
        piece = _match_piece(tail, table)
        if piece is not None:
            return head, piece
        return text, None
    for letter, piece in _promotion_candidates(table):
        if len(text) > len(letter) and text.endswith(letter) and text[-len(letter) - 1].isdigit():
            return text[: -len(letter)], piece
    return text, None


def _promotion_candidates(table: LanguageTable) -> tuple[tuple[str, PieceType], ...]:
    """Return the letters and glyphs a bare promotion may be written with.

    Args:
        table: The language table.

    Returns:
        ``(letter, piece)`` pairs, longest letter first.
    """
    pairs = list(table.officer_letters())
    pairs.extend((glyph, piece) for glyph, piece in _FIGURINE_TO_PIECE.items())
    return tuple(sorted(pairs, key=lambda pair: -len(pair[0])))


def _match_piece(letter: str, table: LanguageTable) -> PieceType | None:
    """Resolve one letter or glyph to a piece, ignoring pawn letters.

    Args:
        letter: The candidate token.
        table: The language table.

    Returns:
        The piece, or ``None``.
    """
    token = letter.strip()
    if token in _FIGURINE_TO_PIECE:
        return _FIGURINE_TO_PIECE[token]
    for candidate, piece in table.officer_letters():
        if candidate == token:
            return piece
    return None


def _split_canonical(san: str) -> _SanParts:
    """Parse a canonical English SAN token into its components.

    Args:
        san: Canonical English SAN.

    Returns:
        The parsed components.

    Raises:
        NotationError: If the token is not valid English SAN.
    """
    body, suffix = _split_suffix(san)
    if body in ("O-O", "O-O-O"):
        return _SanParts(castling=body, piece=None, body="", promotion=None, suffix=suffix)
    match = _SAN_RE.match(body)
    if match is None:
        msg = f"SAN ingles invalido: {san!r}."
        raise NotationError(msg)
    piece_letter_text = match.group("piece")
    promotion_letter = match.group("promotion")
    core = body
    if piece_letter_text:
        core = core[len(piece_letter_text) :]
    if promotion_letter:
        core = core[: core.rindex("=")]
    return _SanParts(
        castling=None,
        piece=_PIECE_FOR_ENGLISH_LETTER[piece_letter_text] if piece_letter_text else None,
        body=core,
        promotion=_PIECE_FOR_ENGLISH_LETTER[promotion_letter] if promotion_letter else None,
        suffix=suffix,
    )
