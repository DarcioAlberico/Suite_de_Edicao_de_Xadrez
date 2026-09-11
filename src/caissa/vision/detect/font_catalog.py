"""Catalog of chess diagram fonts: glyph -> (piece, square colour).

Origem: PDFimport/PDFImport_v1.2.0/PDFImport/chessfig.py (reconhecimento de nome
de fonte de figurino) e Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/renderer.py
(tabela de glifos legados da Merida).
Absorvido em 2026-09-07.  Alterações: o reconhecimento de nome deixou de ser uma
regex única e passou a ser um catálogo por família; a tabela da Merida deixou de
ser apenas de escrita e passou a ser bidirecional (leitura de diagrama);
acrescentadas as demais famílias e a marcação explícita de confiança.

Why this exists
---------------
Most chess books produced by publishers are vector PDFs whose diagrams are set
with a dedicated chess font.  In that case the position is *literally in the
file as text*: the row ``rnbqkbnr`` of the board is a run of eight characters in
a font such as Chess Merida.  Reading it back is exact -- no inference, no
model, no rasterisation.  This module is the Rosetta Stone that makes that
possible: for every family it knows, it says what each character means.

Layouts, not fonts
------------------
Legacy chess fonts do not agree on an encoding, but they do cluster into a
handful of *layouts* shared by whole families.  A layout is pure data
(:class:`LayoutSpec`); a family is a row in :data:`_FAMILY_SPECS` naming one
layout plus the font-name patterns that select it.  Adding a family is adding a
row -- no code.

Evidence and honesty
--------------------
Every family carries a ``confidence``:

``verified``
    The mapping was checked glyph by glyph against the actual font file on this
    machine (rendered and read by eye, cross-checked with an automatic
    silhouette classifier calibrated on Chess Merida).
``inferred``
    The font was not available, but it belongs to a family whose layout was
    verified and whose character set matches exactly.
``unverified``
    Reported by documentation or by the shape of the name only.  The detector
    still recognises the font, but refuses to read a position from it unless
    the caller opts in.

Nothing here is a guess presented as fact.  Where the layout of a family is
only partly known, the unknown characters are simply absent from the table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Literal, Mapping, Sequence

__all__ = [
    "Confidence",
    "FontKind",
    "GlyphKind",
    "GlyphRole",
    "ChessFontFamily",
    "LayoutSpec",
    "FAMILIES",
    "normalize_font_name",
    "normalize_char",
    "lookup_family",
    "looks_like_chess_font",
    "family_by_key",
]

# --------------------------------------------------------------------------
# Types
# --------------------------------------------------------------------------

Confidence = Literal["verified", "inferred", "unverified"]
FontKind = Literal["diagram", "figurine"]
SquareColour = Literal["light", "dark"]
GlyphKind = Literal[
    "piece",       # a piece stands on this square
    "empty",       # an empty square
    "marker",      # an empty square carrying a dot/cross/circle annotation
    "background",  # zero-advance square background printed under a piece glyph
    "border",      # frame / rule around the diagram, not a square
    "coordinate",  # a-h or 1-8 printed in the frame
    "decoration",  # arcs, arrows, publisher logo: not part of the board
]

#: Piece in FEN spelling: uppercase is White, lowercase is Black.
PieceLetter = Literal["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]

_PIECE_ORDER: Final = "PNBRQK"


@dataclass(frozen=True, slots=True)
class GlyphRole:
    """What one character means inside a diagram of a given font family."""

    kind: GlyphKind
    #: FEN letter, only for ``kind == "piece"``.
    piece: PieceLetter | None = None
    #: Colour of the square the glyph draws, when the glyph draws one.
    square: SquareColour | None = None
    #: ``a``-``h`` / ``1``-``8`` for ``kind == "coordinate"``; ``None`` when the
    #: font has such a glyph but which coordinate it prints was not verified.
    coordinate: str | None = None
    #: True for overprint glyphs with zero advance width.  They paint the square
    #: under a piece and must never consume a cell of the 8x8 lattice.
    zero_advance: bool = False

    @property
    def occupies_cell(self) -> bool:
        """Does this glyph stand on exactly one square of the board?"""
        return self.kind in ("piece", "empty", "marker") and not self.zero_advance


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    """One encoding shared by a family of fonts.  Pure data.

    The six ``*_white`` / ``*_black`` strings list the characters for the pieces
    in :data:`_PIECE_ORDER` order (pawn, knight, bishop, rook, queen, king).
    An empty string means the layout has no such set.
    """

    light_white: str = ""
    light_black: str = ""
    dark_white: str = ""
    dark_black: str = ""
    #: Second style for the same pieces (ChessBase ships a silhouette set for
    #: small sizes beside the detailed one).
    alt_light_white: str = ""
    alt_light_black: str = ""
    empty_light: str = ""
    empty_dark: str = ""
    marker_light: str = ""
    marker_dark: str = ""
    #: Zero-advance backgrounds, listed in :data:`_PIECE_ORDER` order; they say
    #: "this square is dark" and are printed under the piece glyph.
    background_dark: str = ""
    border: str = ""
    decoration: str = ""
    #: Characters that print a known coordinate, as ``{char: "a"}``.
    coordinates: Mapping[str, str] = field(default_factory=dict)
    #: Characters that print *some* coordinate whose identity is unverified.
    coordinates_unknown: str = ""
    #: Pieces without a square colour (Unicode chess block, figurine fonts).
    neutral_white: str = ""
    neutral_black: str = ""

    def build(self) -> dict[str, GlyphRole]:
        """Expand the spec into ``{character: role}``."""
        table: dict[str, GlyphRole] = {}

        def add_pieces(chars: str, upper: bool, square: SquareColour | None) -> None:
            if not chars:
                return
            if len(chars) != len(_PIECE_ORDER):
                raise ValueError(f"piece set {chars!r} must list {len(_PIECE_ORDER)} characters")
            for ch, piece in zip(chars, _PIECE_ORDER):
                letter = piece if upper else piece.lower()
                table.setdefault(ch, GlyphRole("piece", piece=letter, square=square))  # type: ignore[arg-type]

        add_pieces(self.light_white, True, "light")
        add_pieces(self.light_black, False, "light")
        add_pieces(self.dark_white, True, "dark")
        add_pieces(self.dark_black, False, "dark")
        add_pieces(self.alt_light_white, True, "light")
        add_pieces(self.alt_light_black, False, "light")

        for ch in self.empty_light:
            table.setdefault(ch, GlyphRole("empty", square="light"))
        for ch in self.empty_dark:
            table.setdefault(ch, GlyphRole("empty", square="dark"))
        for ch in self.marker_light:
            table.setdefault(ch, GlyphRole("marker", square="light"))
        for ch in self.marker_dark:
            table.setdefault(ch, GlyphRole("marker", square="dark"))
        for ch in self.background_dark:
            table.setdefault(ch, GlyphRole("background", square="dark", zero_advance=True))
        for ch in self.border:
            table.setdefault(ch, GlyphRole("border"))
        for ch in self.decoration:
            table.setdefault(ch, GlyphRole("decoration"))
        for ch, label in self.coordinates.items():
            table.setdefault(ch, GlyphRole("coordinate", coordinate=label))
        for ch in self.coordinates_unknown:
            table.setdefault(ch, GlyphRole("coordinate"))

        if self.neutral_white:
            for ch, piece in zip(self.neutral_white, _PIECE_ORDER):
                table.setdefault(ch, GlyphRole("piece", piece=piece))  # type: ignore[arg-type]
        if self.neutral_black:
            for ch, piece in zip(self.neutral_black, _PIECE_ORDER):
                table.setdefault(ch, GlyphRole("piece", piece=piece.lower()))  # type: ignore[arg-type]

        return table


@dataclass(frozen=True, slots=True)
class ChessFontFamily:
    """A chess font family and how to read a diagram set in it."""

    key: str
    display_name: str
    #: Lowercase regular expressions matched against the *bare* font name.
    patterns: tuple[str, ...]
    kind: FontKind
    confidence: Confidence
    glyphs: Mapping[str, GlyphRole]
    #: Where the mapping comes from, and how it was checked.
    source: str
    notes: str = ""

    def role(self, char: str) -> GlyphRole | None:
        """Role of ``char``, after folding the Windows symbol range to ASCII."""
        return self.glyphs.get(normalize_char(char))

    @property
    def readable(self) -> bool:
        """Can a position be read from this family without guessing?"""
        return self.kind == "diagram" and self.confidence in ("verified", "inferred")


# --------------------------------------------------------------------------
# Layouts (pure data)
# --------------------------------------------------------------------------
#
# LAYOUT "marroquin"
#   Armando H. Marroquin's 1998 diagram fonts, and everything that copied them.
#   Case selects the square colour, the letter selects the piece:
#       light square   white: p n b r q k      black: o m v t w l
#       dark  square   white: P N B R Q K      black: O M V T W L
#       empty light: space (also '*' in some cuts)      empty dark: '+'
#   Verified by rendering every glyph of the fonts installed on this machine
#   and reading them (see docs/quality/F3A_REPORT.md).  Cross-checked against
#   the write-side table in Editor_Diagramas_de_Xadrez/renderer.py, which this
#   is the inverse of.
_MARROQUIN = LayoutSpec(
    light_white="pnbrqk",
    light_black="omvtwl",
    dark_white="PNBRQK",
    dark_black="OMVTWL",
    empty_light=" *",
    empty_dark="+",
    marker_light=".x",
    marker_dark=":X",
    border='!"#$%()/12345789',
    decoration="ADFSadfs?",
)

# LAYOUT "alpha"
#   Eric Bentzen's Chess Alpha.  Same case convention as Marroquin, but the
#   knight and bishop letters differ: 'n' is the *black bishop* here, and the
#   knights live on 'h' (white) and 'j' (black).  Reading an Alpha diagram with
#   the Marroquin table silently swaps knights and bishops -- which is exactly
#   why the catalog is per family and not one global table.
_ALPHA = LayoutSpec(
    light_white="phbrqk",
    light_black="ojntwl",
    dark_white="PHBRQK",
    dark_black="OJNTWL",
    empty_light=" ",
    empty_dark="+",
    marker_light=")",
    marker_dark="9",
    border="!\"#$%&'(12345678",
)

# LAYOUT "utrecht"
#   Chess Utrecht inverts the roles of the two axes: *case* selects the piece
#   colour and the *letter group* selects the square colour.
#       light square   white: p n b r q k      black: P N B R Q K
#       dark  square   white: o m v t w l      black: O M V T W L
_UTRECHT = LayoutSpec(
    light_white="pnbrqk",
    light_black="PNBRQK",
    dark_white="omvtwl",
    dark_black="OMVTWL",
    empty_light=" ",
    empty_dark="/",
    border="12345678",
)

# LAYOUT "openchess"
#   OpenChessFont keeps the Marroquin letters but swaps the square polarity of
#   the case: uppercase draws the light square, lowercase the dark one.
_OPENCHESS = LayoutSpec(
    light_white="PNBRQK",
    light_black="OMVTWL",
    dark_white="pnbrqk",
    dark_black="omvtwl",
    empty_light="z",
    empty_dark="x",
)

# LAYOUT "chessbase_diagram"
#   ChessBase's diagram fonts (DiagramTTF / "DiaTTFri", and the Linares,
#   Zurich, Hastings and Berlin diagram cuts shipped with ChessBase products).
#   A dark square with a piece on it is *two* glyphs: a zero-advance background
#   that knocks the piece silhouette out of the hatching, immediately followed
#   by the ordinary piece glyph.  Verified on DiagramTTFritz: the background
#   glyphs 'm s t u v w z * /' all have advance width 0, and overprinting
#   't' + 'N' produces a white knight on a dark square, pixel for pixel.
#
#   The font also carries two black-piece styles: a detailed one on the
#   lowercase letters and a silhouette one (for small sizes) on M V S Z W T.
_CHESSBASE_DIAGRAM = LayoutSpec(
    light_white="PNLRQK",
    light_black="pnlrqk",
    alt_light_black="ZSVTWM",
    empty_light=" ",
    empty_dark="+",
    # Every glyph of DiagramTTFritz with advance width 0 is "*/:`mstuvwz".
    # The first six are listed in _PIECE_ORDER (pawn, knight, bishop, rook,
    # queen, king) order, measured by overprinting: u+P pawn, t+N knight,
    # s+L bishop, w+R rook, v+Q queen, m+K king.  The piece identity is not
    # used -- these glyphs only say "dark square" -- but it was measured, so it
    # is recorded.  The remaining five are dark backgrounds whose paired piece
    # was not identified.
    background_dark="utswvm" + "*/:`z",
    marker_light="Oo<[{,.@",
    marker_dark="]>;}J",
    border="09iI\\|)=~",
    decoration="XYxy^_j",
    coordinates={
        "a": "a", "b": "b", "c": "c", "d": "d",
        "e": "e", "f": "f", "g": "g", "h": "h",
        "A": "a", "B": "b", "C": "c", "D": "d",
        "E": "e", "F": "f", "G": "g", "H": "h",
    },
    coordinates_unknown="12345678!\"#$%&'(",
)

# LAYOUT "unicode"
#   The Unicode chess block.  Modern generators (LaTeX packages, python-chess,
#   web-to-PDF pipelines) emit these directly.  They carry no square colour --
#   the board is drawn separately -- so a lattice built from them is validated
#   by geometry alone.
_UNICODE = LayoutSpec(
    neutral_white="♙♘♗♖♕♔",
    neutral_black="♟♞♝♜♛♚",
)

# LAYOUT "figurine_san"
#   Inline figurine fonts.  The text layer holds K/Q/R/B/N and the glyph drawn
#   is a piece, but there is no board: these must never be read as a diagram.
#   Kept in the catalog precisely so the detector can *reject* them.
_FIGURINE_SAN = LayoutSpec(
    neutral_white="",
    neutral_black="",
)


# --------------------------------------------------------------------------
# Families (pure data)
# --------------------------------------------------------------------------
#
# Fields: key, display name, name patterns, layout, kind, confidence, source.
# ``patterns`` are regular expressions matched, case-insensitively, against the
# font name with its ``ABCDEF+`` subset prefix removed and spaces/dashes/
# underscores stripped, so "Chess Merida", "ChessMerida" and "CHESS-MERIDA"
# all hit the same row.

_VERIFIED_HERE: Final = (
    "Verificado glifo a glifo no arquivo da fonte instalada nesta máquina "
    "(renderização + classificador de silhueta calibrado na Chess Merida), 2026-09-07."
)
_SAME_CHARSET: Final = (
    "Layout herdado da família Marroquin: conjunto de caracteres idêntico ao de "
    "uma fonte verificada, mesmo desenhista e mesma métrica monoespaçada."
)

_FAMILY_SPECS: Final[Sequence[tuple[str, str, tuple[str, ...], LayoutSpec, FontKind, Confidence, str, str]]] = (
    # ---- Marroquin layout, verified font by font --------------------------
    ("merida", "Chess Merida", (r"chessmerida", r"^merida$", r"meridachess"),
     _MARROQUIN, "diagram", "verified",
     _VERIFIED_HERE + " Confere com a tabela de escrita de renderer.py.", ""),
    ("cases", "Chess Cases", (r"chesscases",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("leipzig", "Chess Leipzig", (r"chessleipzig",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("lucena", "Chess Lucena", (r"chesslucena",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("marroquin", "Chess Marroquin", (r"chessmarroquin", r"^marroquin$"),
     _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("motif", "Chess Motif", (r"chessmotif",), _MARROQUIN, "diagram", "verified",
     _VERIFIED_HERE + " Fonte com cmap de símbolo (3,0) em U+F020-U+F0EF.", ""),
    ("kingdom", "Chess Kingdom", (r"chesskingdom",), _MARROQUIN, "diagram", "verified",
     _VERIFIED_HERE + " Fonte com cmap de símbolo (3,0) em U+F020-U+F0EF.", ""),
    ("condal", "Chess Condal", (r"chesscondal",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("maya", "Chess Maya", (r"chessmaya",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("mediaeval", "Chess Mediaeval", (r"chessmediaeval", r"chessmedieval"),
     _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("magnetic", "Chess Magnetic", (r"chessmagnetic",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("adventurer", "Chess Adventurer", (r"chessadventurer",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("alfonsox", "Chess Alfonso-X", (r"chessalfonso",), _MARROQUIN, "diagram", "verified",
     _VERIFIED_HERE + " Fonte com cmap de símbolo (3,0) em U+F020-U+F0EF.", ""),
    ("harlequin", "Chess Harlequin", (r"chessharlequin",), _MARROQUIN, "diagram", "verified",
     _VERIFIED_HERE + " Fonte com cmap de símbolo (3,0) em U+F020-U+F0EF.", ""),
    ("line", "Chess Line", (r"chessline",), _MARROQUIN, "diagram", "verified",
     _VERIFIED_HERE + " Fonte com cmap de símbolo (3,0) em U+F020-U+F0EF.", ""),
    ("millennia", "Chess Millennia", (r"chessmillennia",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),
    ("chess7", "Chess 7", (r"^chess-?7$",), _MARROQUIN, "diagram", "verified", _VERIFIED_HERE, ""),

    # ---- Marroquin layout, inferred from an identical character set -------
    ("berlin", "Chess Berlin", (r"chessberlin", r"^berlin$"), _MARROQUIN, "diagram", "unverified",
     "Família citada na literatura de fontes de xadrez; o arquivo não estava "
     "disponível nesta máquina, o layout não foi conferido.", ""),
    ("uscf", "USCF", (r"\buscf\b",), _MARROQUIN, "diagram", "unverified",
     "Conjunto da US Chess Federation; arquivo indisponível, layout não conferido.", ""),
    ("tilburg", "Chess Tilburg", (r"tilburg",), _MARROQUIN, "diagram", "unverified",
     "Arquivo indisponível; layout não conferido.", ""),

    # ---- Other verified layouts -------------------------------------------
    ("alpha", "Chess Alpha", (r"chessalpha",), _ALPHA, "diagram", "verified",
     _VERIFIED_HERE + " Atenção: 'n' é o bispo preto, não o cavalo.", ""),
    ("utrecht", "Chess Utrecht", (r"chessutrecht",), _UTRECHT, "diagram", "verified",
     _VERIFIED_HERE + " Caixa seleciona a cor da peça; grupo de letras, a cor da casa.", ""),
    ("openchess", "OpenChessFont", (r"openchessfont",), _OPENCHESS, "diagram", "verified",
     _VERIFIED_HERE + " Polaridade de caixa invertida em relação à Marroquin.", ""),

    ("chessbase_diagram", "ChessBase DiagramTTF", (r"diagramttf", r"^diattf", r"diagramttfritz"),
     _CHESSBASE_DIAGRAM, "diagram", "verified",
     _VERIFIED_HERE + " Casas escuras compostas por glifo de fundo com avanço zero.", ""),
    ("linares_diagram", "Linares Diagram", (r"linaresdiagram",), _CHESSBASE_DIAGRAM, "diagram", "unverified",
     "Só havia subconjuntos extraídos de PDF nesta máquina; o layout completo "
     "não pôde ser conferido. Presume-se o da DiagramTTF por ser a mesma origem.", ""),
    ("zurich_diagram", "Zurich Diagram", (r"zurichdiagram",), _CHESSBASE_DIAGRAM, "diagram", "unverified",
     "Só havia subconjuntos extraídos de PDF; layout presumido, não conferido.", ""),
    ("hastings_diagram", "Hastings Diagram", (r"hastingsdiagram",), _CHESSBASE_DIAGRAM, "diagram", "unverified",
     "Só havia subconjuntos extraídos de PDF; layout presumido, não conferido.", ""),

    ("unicode", "Unicode Chess Symbols", (r"^$",), _UNICODE, "diagram", "verified",
     "Bloco Unicode U+2654-U+265F. Independente de fonte.", ""),

    # ---- Figurine (inline) fonts: recognised so they can be REJECTED ------
    ("semfig", "SemFig", (r"semfig",), _FIGURINE_SAN, "figurine", "verified",
     "Família de figurino inline (Thinkers Publishing / Chess Stars). "
     "Não desenha tabuleiro; nunca deve virar diagrama.", ""),
    ("figurinecb", "Figurine CB", (r"figurinecb", r"figurine.*time"),
     _FIGURINE_SAN, "figurine", "verified", "Figurino inline da ChessBase.", ""),
    ("linares_figurine", "Linares Figurine", (r"linaresfigurine",), _FIGURINE_SAN, "figurine", "verified",
     "Figurino inline.", ""),
    ("zurich_figurine", "Zurich Figurine", (r"zurichfigurine",), _FIGURINE_SAN, "figurine", "verified",
     "Figurino inline.", ""),
    ("hastings_figurine", "Hastings Figurine", (r"hastingsfigurine",), _FIGURINE_SAN, "figurine", "verified",
     "Figurino inline.", ""),
    ("verfig", "Verfig", (r"verfig",), _FIGURINE_SAN, "figurine", "verified", "Figurino inline.", ""),
    ("skaknew", "SkakNew", (r"skaknew", r"skak"), _FIGURINE_SAN, "figurine", "verified",
     "Figurino inline do pacote LaTeX skak.", ""),
    ("chess_generic_figurine", "Figurino genérico", (r"figurin", r"chessfig", r"\bdgt\b"),
     _FIGURINE_SAN, "figurine", "unverified",
     "Origem: chessfig.py. Reconhecido pelo nome; usado só para rejeitar.", ""),
)

#: Font-name fragments that mean "some chess font" without naming a family.
#: Origem: chessfig.FIGURINE_FONT_RE, com ``chessboard`` continuando excluído.
_GENERIC_CHESS_NAME: Final = re.compile(
    r"semfig|figurin|chessfig|chessbase|diagramttf|dgt|linares|marroquin"
    r"|zurich|berlin|cheq|uscf|tilburg|utrecht|leipzig|lucena|merida|skak"
    r"|chess(?!board)",
    re.IGNORECASE,
)

_SUBSET_PREFIX: Final = re.compile(r"^[A-Z]{6}\+")
_NAME_NOISE: Final = re.compile(r"[\s_\-.]+")
_STYLE_SUFFIX: Final = re.compile(
    r"(regular|roman|book|normal|bold|italic|oblique|medium|light|mt|ms|psmt)+$"
)


def normalize_font_name(font_name: str | None) -> str:
    """Bare, comparable form of a PDF font name.

    PDF font names are usually subset-tagged (``ABCDEF+ChessMerida``) and the
    same family shows up as ``Chess Merida``, ``ChessMerida-Regular`` or
    ``CHESS_MERIDA``.  Fold all of that away.
    """
    if not font_name:
        return ""
    bare = _SUBSET_PREFIX.sub("", font_name.strip())
    bare = bare.split(",", 1)[0]
    bare = _NAME_NOISE.sub("", bare).lower()
    trimmed = _STYLE_SUFFIX.sub("", bare)
    return trimmed or bare


def normalize_char(char: str) -> str:
    """Fold the Windows symbol range down to ASCII.

    Several of these fonts (Chess Motif, Kingdom, Alfonso-X, Harlequin, Line)
    carry only a ``(3, 0)`` symbol ``cmap`` covering U+F020-U+F0FF.  Extractors
    then hand back private-use characters where the file really means plain
    ASCII, and every table here is written in ASCII.
    """
    if len(char) != 1:
        return char
    code = ord(char)
    if 0xF000 <= code <= 0xF0FF:
        return chr(code - 0xF000)
    return char


def _build_families() -> tuple[ChessFontFamily, ...]:
    built: list[ChessFontFamily] = []
    for key, display, patterns, layout, kind, confidence, source, notes in _FAMILY_SPECS:
        built.append(
            ChessFontFamily(
                key=key,
                display_name=display,
                patterns=tuple(patterns),
                kind=kind,
                confidence=confidence,
                glyphs=layout.build(),
                source=source,
                notes=notes,
            )
        )
    return tuple(built)


FAMILIES: Final[tuple[ChessFontFamily, ...]] = _build_families()

_BY_KEY: Final[Mapping[str, ChessFontFamily]] = {f.key: f for f in FAMILIES}

# Longest pattern first: "chessmeridabold" must not be captured by the generic
# "chess" rule while a specific family still matches.
_COMPILED: Final[tuple[tuple[re.Pattern[str], ChessFontFamily], ...]] = tuple(
    sorted(
        ((re.compile(p, re.IGNORECASE), fam) for fam in FAMILIES for p in fam.patterns),
        key=lambda item: -len(item[0].pattern),
    )
)


def family_by_key(key: str) -> ChessFontFamily | None:
    """The family registered under ``key``, if any."""
    return _BY_KEY.get(key)


def lookup_family(font_name: str | None) -> ChessFontFamily | None:
    """The chess font family a PDF font name belongs to, or ``None``.

    The empty name resolves to the Unicode family, because text carrying
    U+2654-U+265F needs no special font at all.
    """
    bare = normalize_font_name(font_name)
    if not bare:
        return _BY_KEY.get("unicode")
    for pattern, family in _COMPILED:
        if family.key == "unicode":
            continue
        if pattern.search(bare):
            return family
    return None


def looks_like_chess_font(font_name: str | None) -> bool:
    """Does the name look like *some* chess font, catalogued or not?

    Used to log unknown families so the catalog can grow, and to keep an
    unrecognised chess font from being mistaken for body text.
    """
    bare = normalize_font_name(font_name)
    return bool(bare) and bool(_GENERIC_CHESS_NAME.search(bare))
