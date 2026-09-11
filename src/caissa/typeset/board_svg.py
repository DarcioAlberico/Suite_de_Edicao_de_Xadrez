"""The canonical vector diagram renderer: FEN in, publication-grade SVG out.

Origem: Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/renderer.py
Absorvido em 2026-09-07.

Alteracoes e por que
--------------------
O renderer original tinha tres caminhos paralelos -- Merida via PyMuPDF para PDF,
``chess.svg`` para SVG, Pillow para PNG -- e os tres desenhavam tabuleiros *diferentes*.
O proprio docstring dele admitia: "o desenho e o do python-chess, e nao o da Merida que
vai para o PDF". Um livro cujo PDF e o EPUB mostram diagramas diferentes nao e um livro.

Aqui ha **um** renderer. O SVG e a forma canonica; PDF, EPUB, HTML e DOCX derivam dele.

Why millimetres
---------------
The unit of this module is the millimetre: ``viewBox`` is in mm and ``width`` carries the
``mm`` suffix. That is not a detail, it is the reason the output survives both ends of
the size range the brief demands.

A diagram drawn in abstract units and scaled to fit has stroke weights that scale with
it, so the frame that reads correctly at 90 mm becomes a bloated slab at 20 mm and the
grid hairline vanishes below the printer's resolution. Authoring in millimetres lets
every rule be specified the way a typographer specifies it -- *this* line is 0.25 mm --
and lets a floor be enforced in the same breath: no rule is ever emitted below
``MIN_RULE_MM``, whatever the board size. At 400 % on screen the vector simply gets
bigger; nothing is rasterised on the way.

Determinism
-----------
The same FEN and the same style produce byte-identical SVG. Every float goes through
``format_number``, no element carries a generated id, no timestamp or hostname reaches
the output, and marks are drawn in the order given. `tests/unit/typeset` asserts it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import lru_cache
from typing import Callable, Iterable, Literal, Mapping, Sequence

from .fonts import (
    Confidence,
    FontModel,
    FontNotFoundError,
    LoadedFont,
    UNICODE_PIECES,
    get_spec,
    load_font,
)
from .outlines import Outline, format_number

__all__ = [
    "Arrow",
    "BoardTheme",
    "CircleMark",
    "CoordinateStyle",
    "DiagramStyle",
    "FrameStyle",
    "MIN_RULE_MM",
    "Mark",
    "SideToMove",
    "SquareHighlight",
    "THEMES",
    "board_from_fen",
    "contrast_ratio",
    "get_theme",
    "width_for_square",
    "highlight_pair",
    "inside_coordinates_fit",
    "resolved_side_to_move",
    "frame_origin",
    "MARK_HEAD_KEYLINE",
    "MARK_HEAD_LANDING",
    "MARK_INK_MIN_CONTRAST",
    "relative_luminance",
    "render_many",
    "render_svg",
    "side_to_move_from_fen",
    "square_index",
    "square_name",
]

# A printed rule below roughly 0.18 mm (about half a point) breaks up on offset presses
# and disappears entirely on a laser proof. Every stroke this module emits is clamped to
# it, which is what stops the 20 mm diagram from losing its frame.
MIN_RULE_MM = 0.18

FRAME_RATIO = 110.0
"""The one number that decides every frame weight: ``board width / rule width``.

Measured off the four reference pages in `benchmarks/reports/blind/` (Quality Chess
p165 1/122, p151 1/129; Aagaard p60 1/139, p151 1/94), which bracket 1/94 to 1/139.
110 sits in the middle of that band. Cycle 1 had no such rule at all -- the weights were
independent fractions of the *square* with a hard floor underneath, and the same document
shipped frames from 1/98 to 1/230, a spread of 2.3x between diagrams of the same size.

Every ``FrameStyle`` now derives its rules from this ratio and stays inside +/-15 % of
it, so a frame is a system value rather than a per-style opinion; what distinguishes the
styles is their *structure* (one rule, two rules, an inset rule, a shadow), which is how
a house style actually distinguishes them.
"""

FRAME_RATIO_TOLERANCE = 0.15
"""Every emitted frame rule must satisfy ``board / rule`` within this of FRAME_RATIO.
Asserted over the whole proofsheet by
`tests/unit/typeset/test_proofsheet.py::test_every_frame_weight_is_the_system_value`."""

# Per style, in units of ``FRAME_RATIO`` denominators: 1/outer, 1/inner.
_FRAME_DENOMINATORS: dict[str, tuple[float, float]] = {
    "hairline": (118.0, 0.0),
    "rule": (103.0, 0.0),
    "double": (98.0, 122.0),
    "shadowed": (118.0, 0.0),
    "inset": (118.0, 122.0),
}

HATCH_COVERAGE = 0.28
"""Fraction of a hatched square that is ink.

Measured off all four reference pages at 200 DPI (Quality Chess p165 34.5 %, p151
34.2 %; Aagaard p60 26.8 %, p151 22.1 %) -- the band is 22 to 35 % and the median is
30 %. Cycle 1 targeted **19 %**, which made our dark squares the *lightest* of seven
blind samples and turned four thick rules per square into competing graphic elements
instead of a tone. Holding coverage constant is still what keeps a 20 mm diagram the
same weight as a 90 mm one; only the target moved."""

HATCH_COVERAGE_MAX = 0.30
"""Ceiling used when the rule width has hit ``MIN_RULE_MM`` and the pitch has to open up
to stop a small square going solid."""

MIN_COORDINATE_PT = 5.5
"""Coordinates smaller than this are **suppressed**, not printed.

3.92 pt of a serif does not survive offset printing -- the thin strokes simply drop out
-- and every book that sets a diagram this small omits the coordinates instead. Cycle 1
printed them: the 20 mm diagram on proofsheet page 6 carried 3.92 pt labels under a
caption claiming the test had passed."""

FILES = "abcdefgh"
RANKS = "87654321"


# --------------------------------------------------------------------------- #
# Colour helpers
# --------------------------------------------------------------------------- #
def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _parse_hex(colour: str) -> tuple[float, float, float]:
    text = colour.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        raise ValueError(f"Cor invalida: {colour!r}. Use #rrggbb.")
    return tuple(int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(colour: str) -> float:
    """WCAG relative luminance of an ``#rrggbb`` colour."""
    r, g, b = (_srgb_to_linear(c) for c in _parse_hex(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two colours, 1.0 to 21.0."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _rgb255(colour: str) -> tuple[int, int, int]:
    return tuple(int(round(c * 255.0)) for c in _parse_hex(colour))  # type: ignore[return-value]


def _hex255(rgb: Sequence[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(c)))):02X}" for c in rgb)


def highlight_pair(theme: "BoardTheme", colour: str | None = None) -> tuple[str, str]:
    """The colours a **light** and a **dark** square take when highlighted.

    The highlight is a *shift*, not a replacement: ``delta = anchor - light`` is added to
    both square tints, so the difference between them survives untouched and the chequer
    still reads inside the highlighted region. Cycle 1 painted one flat grey over both --
    measured on the proofsheet, a highlighted light square and a highlighted dark square
    were both 135, indistinguishable, and the highlight against an ordinary dark square
    came to 1.95:1.

    The delta is scaled down, and only down, by the largest factor that keeps every
    channel of both squares inside 0..255. Without that a dark theme (which highlights by
    adding light rather than removing it) would clamp one square and not the other, which
    is exactly how a "same delta" rule quietly stops being one.
    """
    light = _rgb255(theme.light)
    dark = _rgb255(theme.dark)
    anchor = _rgb255(colour or theme.highlight_fill or theme.highlight)
    delta = [a - l for a, l in zip(anchor, light)]

    scale = 1.0
    for square in (light, dark):
        for channel, d in zip(square, delta):
            if d > 0 and channel + d > 255:
                scale = min(scale, (255.0 - channel) / d)
            elif d < 0 and channel + d < 0:
                scale = min(scale, channel / -d)
    scale = max(0.0, scale)

    def shift(square: Sequence[int]) -> str:
        return _hex255([c + d * scale for c, d in zip(square, delta)])

    return shift(light), shift(dark)


# --------------------------------------------------------------------------- #
# Themes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BoardTheme:
    """A board's colours.

    ``piece_body`` and ``piece_ink`` are the two layers described in ``outlines``: the
    body is what fills a white piece and what shows through a black piece's counters;
    the ink is the outline of a white piece and the mass of a black one. Keeping them as
    theme colours rather than hard black and white is what lets the dark theme be
    *designed* instead of inverted -- pure #000 pieces on a dark board lose their edges.
    """

    key: str
    label: str
    light: str
    dark: str
    piece_body: str
    piece_ink: str
    frame: str
    coordinate: str
    page: str
    highlight: str = "#F2C14E"
    arrow: str = "#D1495B"
    circle: str = "#2E86AB"
    grid: str = "#8A8A8A"
    grayscale_safe: bool = False
    """True when the design carries no hue-only distinctions, so it survives a
    greyscale print run. Asserted, not assumed -- see ``tests/unit/typeset``."""

    hatch: bool = False
    """Draw the dark squares as 45 deg rules instead of a flat tint.

    This is not decoration. It is what Quality Chess, Chess Informant and Batsford put
    on the page, and it exists for a press reason: a hatch is *line art*, so it survives
    a one-colour print run and a photocopy at any size without the tint shifting, while
    a 26 % grey becomes mud on cheap paper. Compare
    ``benchmarks/reports/blind/`` -- the flat tint is the single loudest tell between
    our page and a real Quality Chess page.
    """

    hatch_spacing: float = 0.131
    """**Perpendicular** distance between hatch rules, as a fraction of one square.

    Measured off the reference pages at 200 DPI: the pitch is 6 to 7 px, i.e. 0.76 to
    0.89 mm, on a board whose square is 6.5 mm -- 0.131 of a square, or 7.6 rules across
    it. Cycle 1 declared 0.155 but then parametrised the family by ``x + y``, where a
    step is sqrt(2) times the perpendicular distance, and let a coverage floor open it
    further: the delivered pitch was 11 px, 1.6x every reference. This value is now the
    perpendicular pitch, which is the thing that can be measured on the page."""

    hatch_width: float = 0.0367
    """Hatch rule weight as a fraction of one square, before the MIN_RULE_MM floor.
    0.0367 / 0.131 = 28.0 % ink. Chosen at the bottom of the 28-32 % target band
    because a raster measurement reads a shade heavier than the geometry (antialiasing
    adds about half a pixel to each rule), so the measured value lands mid-band at every
    resolution instead of sitting on the ceiling at 200 DPI and under the floor at 600."""

    highlight_fill: str | None = None
    """The colour a **light** square takes when highlighted, or None to disable filling.

    The highlight is applied as the *same additive delta* to both square tints --
    ``delta = highlight_fill - light`` -- rather than as a flat overwrite. Cycle 1
    replaced both tints with one grey: a highlighted light square and a highlighted dark
    square both measured 135, so the chequer died exactly inside the region the author
    wanted to draw attention to. Preserving the delta preserves the chequer by
    construction; see :func:`highlight_pair`."""

    def is_dark(self) -> bool:
        return relative_luminance(self.page) < 0.3


THEMES: dict[str, BoardTheme] = {}


def _add(theme: BoardTheme) -> None:
    THEMES[theme.key] = theme


# The default. White paper, a neutral grey for the dark squares: what Quality Chess and
# Gambit actually put on a page, and the only combination guaranteed to reproduce on a
# one-colour press. The 26 % grey is chosen so the squares read apart at 20 mm without
# the dark squares fighting the black pieces (contrast to ink stays above 5:1).
_add(
    BoardTheme(
        key="book",
        label="Livro (cinza neutro)",
        light="#FFFFFF",
        dark="#BFBFBF",
        piece_body="#FFFFFF",
        piece_ink="#000000",
        frame="#000000",
        coordinate="#000000",
        page="#FFFFFF",
        # A fill highlight has to be told apart from BOTH square tints in greyscale, and
        # still let a black piece sit on it. #9E9E9E was one short step from the #BFBFBF
        # dark square and vanished on it; #878787 gives 3.6:1 against the light square,
        # 1.95:1 against the dark one, and still 5.9:1 for the piece ink standing on it.
        # For mono print prefer style="corner" anyway -- see SquareHighlight.
        highlight="#878787",
        # What a *light* square becomes when highlighted; the same delta (-55 per
        # channel) is applied to the dark square, which therefore lands on #888888 and
        # keeps the chequer. A black piece still stands on it at 5.9:1.
        highlight_fill="#C8C8C8",
        # See MARK_INK_MIN_CONTRAST. #3A3A3A measured 1.85:1 against a black piece: the
        # arrowhead that lands on a black knight has to be told apart from it, and at
        # 1.85:1 it is not. #616161 is the darkest grey that clears 3:1 against the
        # piece ink (3.39), the piece body (6.19), the dark square (3.37) and the
        # highlight tint (3.70) at once.
        arrow="#616161",
        circle="#616161",
        grid="#808080",
        grayscale_safe=True,
    )
)

# The New in Chess look: a warm cream and tan. Still safe in greyscale because the two
# tints differ in luminance, not only in hue.
_add(
    BoardTheme(
        key="warm",
        label="Livro (creme e sepia)",
        light="#F4ECDD",
        dark="#C9AC85",
        piece_body="#FFFFFF",
        piece_ink="#141210",
        frame="#141210",
        coordinate="#3A332C",
        page="#FFFFFF",
        highlight="#E3B04B",
        highlight_fill="#E5C77E",
        arrow="#A6402F",
        circle="#2F6D8C",
        grid="#A8906B",
        grayscale_safe=True,
    )
)

_add(
    BoardTheme(
        key="screen",
        label="Tela (verde)",
        light="#EDEED1",
        dark="#7C955F",
        piece_body="#FFFFFF",
        piece_ink="#15181C",
        frame="#2E3A22",
        coordinate="#2E3A22",
        page="#FFFFFF",
        highlight="#E6C34A",
        highlight_fill="#DFCB78",
        arrow="#C0392B",
        circle="#1F6F9C",
        grid="#5F7448",
        grayscale_safe=True,
    )
)

# Designed for a dark interface, not derived from the light one. Three deliberate
# departures from "invert everything":
#   * the squares stay in the *same* order (light square still lighter), because a board
#     with the tints swapped reads as the wrong colour to a player;
#   * the white pieces come down off pure white to #EDEDEA so they do not glare;
#   * the black pieces come *up* off pure black to #14171A, so their outline still
#     separates them from the dark squares. Inverting would have made them white.
_add(
    BoardTheme(
        key="dark",
        label="Tema escuro",
        light="#9BA3AB",
        dark="#5E666E",
        piece_body="#EDEDEA",
        piece_ink="#14171A",
        # The frame LIGHTENS in the dark theme. #0E1114 was darker than the page it was
        # drawn on -- RGB(14,17,20) on RGB(27,31,35), 1.14:1 -- so the one rule that
        # says where the board ends was invisible in the one theme where the board most
        # needs an edge. Taking the theme's own light ink puts it at 14.13:1 against the
        # page, 4.97:1 against a dark square and 2.18:1 against a light one.
        frame="#EDEDEA",
        coordinate="#B9C0C7",
        page="#1B1F23",
        highlight="#D6A02E",
        # The dark theme highlights by *adding* light, not by removing it: the delta
        # runs the same direction as the theme's own contrast so neither tint clamps.
        highlight_fill="#C9A96B",
        arrow="#D6604D",
        circle="#5BA3CF",
        grid="#464D54",
        grayscale_safe=True,
    )
)

# The Quality Chess / Chess Informant look: dark squares as 45 deg line art rather than
# a tint. `dark` is still declared because it is what a greyscale *approximation* of the
# board uses (a thumbnail too small to resolve the rules falls back to it), and because
# `contrast_ratio` needs a colour to check the piece ink against.
_add(
    BoardTheme(
        key="hatched",
        label="Livro (hachurado, estilo Quality Chess)",
        light="#FFFFFF",
        dark="#FFFFFF",
        piece_body="#FFFFFF",
        piece_ink="#000000",
        frame="#000000",
        coordinate="#000000",
        page="#FFFFFF",
        highlight="#878787",
        highlight_fill="#D8D8D8",
        arrow="#616161",
        circle="#616161",
        grid="#000000",
        grayscale_safe=True,
        hatch=True,
    )
)

_add(
    BoardTheme(
        key="high_contrast",
        label="Alto contraste",
        light="#FFFFFF",
        dark="#8A8A8A",
        piece_body="#FFFFFF",
        piece_ink="#000000",
        frame="#000000",
        coordinate="#000000",
        page="#FFFFFF",
        highlight="#FFD400",
        highlight_fill="#DCDCDC",
        # Black-on-black is 1:1. Even the high-contrast theme has to keep the arrowhead
        # apart from the piece it lands on; see MARK_INK_MIN_CONTRAST.
        arrow="#616161",
        circle="#616161",
        grid="#000000",
        grayscale_safe=True,
    )
)


def get_theme(key: str | BoardTheme) -> BoardTheme:
    if isinstance(key, BoardTheme):
        return key
    try:
        return THEMES[key]
    except KeyError:
        raise KeyError(
            f"Tema desconhecido: {key!r}. Disponiveis: {', '.join(sorted(THEMES))}"
        ) from None


# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #
class FrameStyle(str, Enum):
    NONE = "none"
    """No frame. The squares' own edges bound the diagram."""

    HAIRLINE = "hairline"
    """A single thin rule. The commonest choice in modern chess books."""

    RULE = "rule"
    """A single heavier rule, for diagrams that must hold their own on a busy page."""

    DOUBLE = "double"
    """A heavy outer rule, a gap, then a hairline. Gambit's house style."""

    SHADOWED = "shadowed"
    """Hairline frame plus a solid offset shadow at the right and bottom."""

    INSET = "inset"
    """Hairline frame with a second hairline inset inside the board edge."""


class SideToMove(str, Enum):
    NONE = "none"
    SQUARE = "square"
    """A small square beside the frame: filled for Black, hollow for White."""

    TRIANGLE = "triangle"
    DOT = "dot"
    BAR = "bar"
    """A short bar against the frame at the top (Black) or bottom (White)."""

    TEXT = "text"
    """The words, for diagrams that must be unambiguous."""


class CoordinateStyle(str, Enum):
    NONE = "none"
    OUTSIDE = "outside"
    """Files below the board, ranks to the left. The book convention."""

    OUTSIDE_RIGHT = "outside_right"
    """Files below, ranks to the right."""

    INSIDE = "inside"
    """Set inside the corner squares. Screen convention; cramped in print."""


@dataclass(frozen=True)
class DiagramStyle:
    """Everything that is presentation rather than position."""

    font: str = "merida"
    theme: str | BoardTheme = "book"
    width_mm: float = 40.0
    """Total width of the finished diagram, coordinates and frame included -- the
    measurement a page layout actually needs."""

    orientation: Literal["white", "black"] = "white"
    coordinates: CoordinateStyle = CoordinateStyle.OUTSIDE
    coordinate_scale: float = 0.62
    """Coordinate type size as a fraction of one square.

    Measured, not chosen. On the Quality Chess reference page the rank digit stands
    **0.408 of a square** tall (`benchmarks/reports/blind/`, measured by ink extent at
    600 dpi); 0.62 em of a serif whose digits are 0.66 em tall reproduces that at 0.412.
    The previous default of 0.30 gave 0.201 -- half the reference, and the first thing
    that read as undersized when the two pages were put side by side."""

    inside_coordinate_scale: float = 0.32
    """Coordinate size for ``CoordinatePlacement.inside``, as a fraction of one square.

    Smaller than the outside scale, and necessarily so: an outside label has a gutter to
    itself, an inside one shares the square with a piece. At 0.62 the rank digit and the
    file letter of a1 came within a millimetre of each other and read as a single token
    "1a" -- one of the seven labels the cycle-1 critic found destroyed on proofsheet
    page 3.

    0.42 was still too big to clear a king's crown or a pawn's base inside the corner of
    its own square. Measured against the Merida silhouettes, the largest scale at which a
    king, a bishop and a pawn all still leave a free corner is **0.32**; a rook and a
    queen leave none at any printable size, and a diagram that needs one refuses the
    placement instead of defacing the piece -- see ``inside_coordinates_fit``. At the
    5.5 pt printing floor 0.32 needs a square of 6.1 mm, which is why the specimen row
    that exercises it is set on a 7 mm square."""

    coordinate_font: str = "Georgia, 'Times New Roman', serif"
    min_coordinate_pt: float = MIN_COORDINATE_PT
    """Below this type size the coordinates are withheld instead of being printed.

    See ``MIN_COORDINATE_PT``. ``_layout`` reports the decision through
    ``_Layout.coordinates_suppressed`` so a caller is never left guessing why a small
    diagram came back without labels."""

    frame: FrameStyle = FrameStyle.HAIRLINE
    side_to_move: SideToMove = SideToMove.NONE
    grid: bool = False
    """Rules between the squares. Off by default: the tint already separates them, and
    a grid at 20 mm turns the board into a mesh."""

    piece_scale: float = 1.0
    """Piece size as a fraction of the square. The legacy fonts are drawn so that one em
    is exactly one square, so 1.0 is the designer's intent; publishers occasionally set
    0.92 to open the board up."""

    show_piece_outline: bool = True
    """Draw the ink layer. Turning it off gives silhouettes only."""

    background: bool = True
    """Emit the page-coloured backdrop rect. Off when compositing onto a page."""

    margin_mm: float = 0.0
    """Extra clear space outside everything."""

    def resolved_theme(self) -> BoardTheme:
        return get_theme(self.theme)


# --------------------------------------------------------------------------- #
# Marks
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Mark:
    """Base class for editorial annotations drawn over the board."""


@dataclass(frozen=True)
class SquareHighlight(Mark):
    square: str
    colour: str | None = None
    opacity: float = 1.0
    style: Literal["fill", "outline", "corner"] = "fill"
    """``outline`` and ``corner`` exist because a translucent wash is unreliable in
    print: it can flatten to invisibility in greyscale or overprint the piece."""


@dataclass(frozen=True)
class CircleMark(Mark):
    square: str
    colour: str | None = None
    width_scale: float = 0.075


@dataclass(frozen=True)
class Arrow(Mark):
    source: str
    target: str
    colour: str | None = None
    width_scale: float = 0.15
    """Shaft width as a fraction of a square."""

    knight_elbow: bool = True
    """Draw an L for a knight's move, the way analysis tools do, instead of a diagonal
    that crosses squares the knight never visits."""

    opacity: float = 1.0


# --------------------------------------------------------------------------- #
# FEN
# --------------------------------------------------------------------------- #
def board_from_fen(fen: str) -> list[list[str]]:
    """Piece placement as 8 rows of 8, rank 8 first. ``.`` is an empty square.

    Accepts a full FEN or a bare placement field. Raises ``ValueError`` with a message
    that names the offending rank, because "invalid FEN" alone is useless to a user
    fixing a recognised diagram.
    """
    placement = fen.strip().split()[0] if fen.strip() else ""
    rows = placement.split("/")
    if len(rows) != 8:
        raise ValueError(
            f"FEN invalida: esperadas 8 fileiras separadas por '/', encontradas "
            f"{len(rows)} em {placement!r}"
        )
    board: list[list[str]] = []
    for index, row in enumerate(rows):
        squares: list[str] = []
        for char in row:
            if char.isdigit():
                squares.extend("." * int(char))
            elif char in "pnbrqkPNBRQK":
                squares.append(char)
            else:
                raise ValueError(
                    f"FEN invalida: caractere {char!r} na fileira {8 - index} ({row!r})"
                )
        if len(squares) != 8:
            raise ValueError(
                f"FEN invalida: a fileira {8 - index} ({row!r}) descreve {len(squares)} "
                f"casas, e nao 8"
            )
        board.append(squares)
    return board


def side_to_move_from_fen(fen: str) -> str:
    parts = fen.strip().split()
    return parts[1] if len(parts) > 1 and parts[1] in ("w", "b") else "w"


def square_index(name: str) -> tuple[int, int]:
    """``'e4'`` to ``(row, col)`` with row 0 = rank 8, col 0 = file a."""
    text = name.strip().lower()
    if len(text) != 2 or text[0] not in FILES or text[1] not in "12345678":
        raise ValueError(f"Casa invalida: {name!r}. Use algo como 'e4'.")
    return 8 - int(text[1]), FILES.index(text[0])


def square_name(row: int, col: int) -> str:
    return f"{FILES[col]}{8 - row}"


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Layout:
    square: float
    board: float
    board_x: float
    board_y: float
    width: float
    height: float
    frame_outer: float
    frame_inner: float
    frame_gap: float
    coord_size: float
    shadow: float
    frame_total: float = 0.0
    """Total width of the frame outside the board edge. For an inset frame that is the
    outer rule alone -- its second rule is drawn inside the board and costs no space --
    which is why this is stored rather than recomputed as outer + gap + inner at each
    call site, as cycle 1 did."""

    coordinates: CoordinateStyle = CoordinateStyle.NONE
    """The coordinate style actually drawn. It differs from ``DiagramStyle.coordinates``
    when the diagram is too small to carry legible labels -- see ``coordinates_suppressed``."""

    coord_gutter: float = 0.0
    """Width reserved for the rank digits beside the board, in mm; 0 when they are not
    outside. It sits on the left for ``OUTSIDE`` and on the **right** for
    ``OUTSIDE_RIGHT``, which is what ``board_x`` already accounts for -- and what a
    caller drawing anything else on the right edge (the side-to-move marker) has to
    step over."""

    coordinates_suppressed: bool = False
    """True when coordinates were asked for and withheld because the type would have
    fallen below ``MIN_COORDINATE_PT``. Exposed rather than silent: a caller that needs
    coordinates at that size needs to know it must set a bigger diagram."""


def _frame_weights(style: FrameStyle, square: float) -> tuple[float, float, float]:
    """Outer rule, inner rule and gap, in mm, for one frame style at one square size.

    One system value drives all of them: ``board / FRAME_RATIO``, where the board is
    eight squares. The floor is the press floor and nothing else, and it only engages
    below a board of about 20 mm -- a regime in which coordinates are suppressed anyway.
    """
    if style is FrameStyle.NONE:
        return 0.0, 0.0, 0.0
    board = square * 8.0
    outer_d, inner_d = _FRAME_DENOMINATORS[style.value]
    outer = max(MIN_RULE_MM, board / outer_d)
    inner = max(MIN_RULE_MM, board / inner_d) if inner_d else 0.0
    if style is FrameStyle.DOUBLE:
        return outer, inner, square * 0.075
    if style is FrameStyle.INSET:
        return outer, inner, square * 0.10
    return outer, 0.0, 0.0


_STM_GAP = 0.22
"""Clear space between the frame and the side-to-move marker, in squares."""

_STM_SIZE = 0.42
"""Marker size in squares. Big enough to read at 20 mm, small enough not to compete
with the board at 90 mm."""


def _side_to_move_units(style: DiagramStyle) -> float:
    """Width the side-to-move marker needs outside the frame, in squares."""
    kind = style.side_to_move
    if kind in (SideToMove.NONE, SideToMove.BAR):
        return 0.0
    if kind is SideToMove.TEXT:
        # "Brancas jogam" set at the size `_stm_text_size` will actually use -- the
        # coordinate size when there are coordinates, 0.30 of a square when there are
        # not. Budgeting the coordinate scale in both cases reserved twice the room the
        # words needed, and the specimen came out visibly wider than the five beside it,
        # which is the "inconsistent spacing between equivalent elements" the charter
        # fails a build for.
        scale = (style.coordinate_scale
                 if style.coordinates is not CoordinateStyle.NONE else 0.30)
        return _STM_GAP + scale * 6.6
    # Plus half the marker's own rule, which straddles its path and would otherwise
    # have its outer half clipped by the viewBox edge.
    return _STM_GAP + _STM_SIZE + 0.05


def width_for_square(style: DiagramStyle, square_mm: float, *, passes: int = 6) -> float:
    """The ``width_mm`` that gives this style squares of exactly ``square_mm``.

    A page that puts several diagrams side by side needs them to share a square size or
    the row reads as an accident -- and because ``width_mm`` is the *finished* width, two
    diagrams that differ only in whether they carry a side-to-move marker come out with
    different boards for the same declared width. That is the "inconsistent spacing
    between equivalent elements" the charter fails a build for, and this is the arithmetic
    that avoids it. Solved by iteration because the coordinate-suppression threshold makes
    the relation piecewise linear.
    """
    def solve(candidate: DiagramStyle) -> float:
        width = square_mm * 8.0
        for _ in range(passes):
            lay = _layout(replace(candidate, width_mm=width))
            if abs(lay.square - square_mm) < 1e-9:
                break
            width *= square_mm / lay.square
        return width

    width = solve(style)
    # `SideToMove.TEXT` degrades to the square below the type floor, and the words and
    # the square do not ask for the same gutter: solving for one and drawing the other
    # is what put a specimen of the indicator row on a board half again the size of its
    # five neighbours. The decision is taken at the solved width -- taking it at the
    # first guess makes it circular, because the words shrink the square that decides
    # whether the words fit.
    resolved = resolved_side_to_move(replace(style, width_mm=width))
    if resolved is not style.side_to_move:
        width = solve(replace(style, side_to_move=resolved))
    return width


def frame_origin(style: DiagramStyle, fen: str | None = None) -> tuple[float, float]:
    """Top-left corner of the board's frame inside the finished diagram, in mm.

    A caption belongs under the board, not under the SVG's bounding box: a diagram with
    outside coordinates carries a rank gutter on its left, so the two differ by the
    gutter plus the margin. On the cycle-2 sheet the "90 mm" caption was set from the
    fragment and landed **9.3 mm** left of the board it labelled, while the 20/40/60 mm
    captions -- laid out by a different code path -- landed exactly on theirs. Callers
    that set captions ask for this offset.

    ``fen`` is optional and only matters for ``CoordinateStyle.INSIDE``, whose gutter
    depends on whether the position leaves room for the labels.
    """
    if fen is not None and style.coordinates is CoordinateStyle.INSIDE \
            and not inside_coordinates_fit(fen, style):
        style = replace(style, coordinates=CoordinateStyle.OUTSIDE)
    resolved = resolved_side_to_move(style)
    if resolved is not style.side_to_move:
        style = replace(style, side_to_move=resolved)
    lay = _layout(style)
    return lay.board_x - lay.frame_total, lay.board_y - lay.frame_total


def _frame_units(frame: FrameStyle, square: float) -> float:
    """Width one side of the frame takes, in units of one square.

    Computed from the *actual* millimetre weights, so that when ``MIN_RULE_MM`` floors a
    rule on a tiny diagram the extra width is budgeted rather than pushed past the
    declared ``width_mm``.
    """
    if frame is FrameStyle.NONE:
        return 0.0
    outer, inner, gap = _frame_weights(frame, square)
    if frame is FrameStyle.DOUBLE:
        return (outer + gap + inner) / square
    # An inset frame's second rule is drawn *inside* the board and costs no width.
    return outer / square


def _layout(style: DiagramStyle) -> _Layout:
    """Solve for the square size that makes the whole diagram exactly ``width_mm``.

    Every part is proportional to the square, so the total is a linear function of it and
    one division gives the answer. Two things make that a fixed point rather than a
    single division, and both are honest: ``MIN_RULE_MM`` can floor a frame rule on a
    tiny diagram, and coordinates are *withheld* below ``MIN_COORDINATE_PT`` (which frees
    the gutter they would have used). Four passes are far more than the two the worst
    case needs, and the result is deterministic.
    """
    margin = style.margin_mm
    stm_units = _side_to_move_units(style)
    shadow_units = 0.09 if style.frame is FrameStyle.SHADOWED else 0.0
    inner_w = style.width_mm - 2.0 * margin
    if inner_w <= 0:
        raise ValueError(
            f"width_mm={style.width_mm} e pequena demais para uma margem de {margin} mm."
        )

    coord = style.coordinates
    suppressed = False
    square = inner_w / 8.0

    def scale_for(mode: CoordinateStyle) -> float:
        if mode is CoordinateStyle.NONE:
            return 0.0
        if mode is CoordinateStyle.INSIDE:
            return style.inside_coordinate_scale
        return style.coordinate_scale

    for _ in range(4):
        k = scale_for(coord)
        outside = coord in (CoordinateStyle.OUTSIDE, CoordinateStyle.OUTSIDE_RIGHT)
        gutter = k * 1.45 if outside else 0.0
        below = k * 1.60 if outside else 0.0
        frame_units = _frame_units(style.frame, square)
        denom_w = 8.0 + gutter + 2.0 * frame_units + shadow_units + stm_units
        square = inner_w / denom_w
        if square <= 0:
            raise ValueError(
                f"width_mm={style.width_mm} e pequena demais para o estilo pedido "
                f"(margem {margin} mm, coordenadas {coord.value}, "
                f"moldura {style.frame.value})."
            )
        # Withhold coordinates rather than print them illegibly. A 20 mm diagram wants
        # 3.9 pt labels; no press holds that, and every book that sets diagrams this
        # small omits the coordinates instead of shrinking them.
        if coord is not CoordinateStyle.NONE:
            if (k * square) * (72.0 / 25.4) < style.min_coordinate_pt:
                coord = CoordinateStyle.NONE
                suppressed = True
                continue
        break

    k = scale_for(coord)
    outside = coord in (CoordinateStyle.OUTSIDE, CoordinateStyle.OUTSIDE_RIGHT)
    gutter = k * 1.45 if outside else 0.0
    below = k * 1.60 if outside else 0.0

    outer, inner, gap = _frame_weights(style.frame, square)
    frame_total = outer + gap + inner if style.frame is FrameStyle.DOUBLE else outer
    shadow = square * shadow_units

    board = square * 8.0
    # The gutter goes on the side the rank digits are actually drawn on. Until cycle 11
    # it was always reserved on the LEFT while `_draw_coordinates` put the digits of
    # `OUTSIDE_RIGHT` on the right, so that mode carried an empty gutter one side and
    # spilled its labels out of its own declared `width_mm` on the other. Measured on the
    # delivered sheet: `proofsheet.pdf` p4, the `outside_right` specimen, put ink at
    # 149.35-151.13 mm against a type area that ends at 146.90 -- up to **4.23 mm** past
    # the measure, 1444 pixels at 300 DPI -- while the cycle-9 report said "nothing
    # outside the type area". The width arithmetic already paid for the gutter; it was
    # spent on the wrong edge.
    on_right = coord is CoordinateStyle.OUTSIDE_RIGHT
    board_x = margin + (0.0 if on_right else gutter * square) + frame_total
    board_y = margin + frame_total
    width = style.width_mm
    height = margin * 2 + frame_total * 2 + board + below * square + shadow
    return _Layout(
        square=square,
        board=board,
        board_x=board_x,
        board_y=board_y,
        width=width,
        height=height,
        frame_outer=outer,
        frame_inner=inner,
        frame_gap=gap,
        coord_size=k * square,
        shadow=shadow,
        frame_total=frame_total,
        coord_gutter=gutter * square,
        coordinates=coord,
        coordinates_suppressed=suppressed,
    )


# --------------------------------------------------------------------------- #
# SVG emission
# --------------------------------------------------------------------------- #
def _n(value: float) -> str:
    return format_number(value)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class _Canvas:
    """Accumulates SVG elements. Exists so ordering is explicit and testable."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, element: str) -> None:
        self.parts.append(element)

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str = "none",
        stroke: str | None = None,
        stroke_width: float = 0.0,
        opacity: float | None = None,
    ) -> None:
        attrs = [f'x="{_n(x)}"', f'y="{_n(y)}"', f'width="{_n(w)}"', f'height="{_n(h)}"']
        attrs.append(f'fill="{fill}"')
        if stroke:
            attrs.append(f'stroke="{stroke}"')
            attrs.append(f'stroke-width="{_n(stroke_width)}"')
        if opacity is not None and opacity < 1.0:
            attrs.append(f'opacity="{_n(opacity)}"')
        self.add(f"<rect {' '.join(attrs)}/>")

    def path(
        self,
        d: str,
        *,
        fill: str = "none",
        stroke: str | None = None,
        stroke_width: float = 0.0,
        opacity: float | None = None,
        rule: str | None = None,
        linecap: str | None = None,
        linejoin: str | None = None,
    ) -> None:
        if not d:
            return
        attrs = [f'd="{d}"', f'fill="{fill}"']
        if rule:
            attrs.append(f'fill-rule="{rule}"')
        if stroke:
            attrs.append(f'stroke="{stroke}"')
            attrs.append(f'stroke-width="{_n(stroke_width)}"')
        if linecap:
            attrs.append(f'stroke-linecap="{linecap}"')
        if linejoin:
            attrs.append(f'stroke-linejoin="{linejoin}"')
        if opacity is not None and opacity < 1.0:
            attrs.append(f'opacity="{_n(opacity)}"')
        self.add(f"<path {' '.join(attrs)}/>")

    def line(
        self, x1: float, y1: float, x2: float, y2: float, *, stroke: str, width: float
    ) -> None:
        self.add(
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
            f'stroke="{stroke}" stroke-width="{_n(width)}"/>'
        )

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        *,
        fill: str = "none",
        stroke: str | None = None,
        stroke_width: float = 0.0,
        opacity: float | None = None,
    ) -> None:
        attrs = [f'cx="{_n(cx)}"', f'cy="{_n(cy)}"', f'r="{_n(r)}"', f'fill="{fill}"']
        if stroke:
            attrs.append(f'stroke="{stroke}"')
            attrs.append(f'stroke-width="{_n(stroke_width)}"')
        if opacity is not None and opacity < 1.0:
            attrs.append(f'opacity="{_n(opacity)}"')
        self.add(f"<circle {' '.join(attrs)}/>")

    def text(
        self,
        x: float,
        y: float,
        content: str,
        *,
        size: float,
        fill: str,
        family: str,
        anchor: str = "middle",
        weight: str | None = None,
        style: str | None = None,
    ) -> None:
        attrs = [
            f'x="{_n(x)}"',
            f'y="{_n(y)}"',
            f'font-family="{_escape(family)}"',
            f'font-size="{_n(size)}"',
            f'fill="{fill}"',
            f'text-anchor="{anchor}"',
        ]
        if weight:
            attrs.append(f'font-weight="{weight}"')
        if style:
            attrs.append(f'font-style="{style}"')
        self.add(f"<text {' '.join(attrs)}>{_escape(content)}</text>")


# --------------------------------------------------------------------------- #
# Arrow geometry
# --------------------------------------------------------------------------- #
def _arrow_path(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    shaft: float,
    head_len: float,
    head_w: float,
) -> str:
    """A single closed outline for a straight arrow.

    Built as one polygon rather than a stroked line plus a marker, because SVG markers
    scale with ``stroke-width`` and a marker sized that way is exactly how arrowheads end
    up stretched. Here the head has a fixed length and width in millimetres and the
    shaft simply stops short of it, so the head keeps its proportions at every board
    size and every arrow length.
    """
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ""
    ux, uy = dx / length, dy / length
    px, py = -uy, ux  # unit normal

    head_len = min(head_len, length * 0.92)
    bx, by = x1 - ux * head_len, y1 - uy * head_len  # base of the head
    hs, hw = shaft / 2.0, head_w / 2.0

    pts = [
        (x0 + px * hs, y0 + py * hs),
        (bx + px * hs, by + py * hs),
        (bx + px * hw, by + py * hw),
        (x1, y1),
        (bx - px * hw, by - py * hw),
        (bx - px * hs, by - py * hs),
        (x0 - px * hs, y0 - py * hs),
    ]
    d = f"M{_n(pts[0][0])} {_n(pts[0][1])}"
    for x, y in pts[1:]:
        d += f"L{_n(x)} {_n(y)}"
    return d + "Z"


def _arrow_head_path(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    shaft: float,
    head_len: float,
    head_w: float,
) -> str:
    """Just the triangle at the tip of :func:`_arrow_path`, same clamping, same points.

    It exists so the head can be drawn a second time, over the pieces, while the shaft
    stays underneath them -- see :data:`MARK_PAINT_ORDER`.
    """
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return ""
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    head_len = min(head_len, length * 0.92)
    bx, by = x1 - ux * head_len, y1 - uy * head_len
    hw = head_w / 2.0
    pts = [
        (bx + px * hw, by + py * hw),
        (x1, y1),
        (bx - px * hw, by - py * hw),
    ]
    d = f"M{_n(pts[0][0])} {_n(pts[0][1])}"
    for x, y in pts[1:]:
        d += f"L{_n(x)} {_n(y)}"
    return d + "Z"


def _elbow_arrow_path(
    x0: float,
    y0: float,
    xc: float,
    yc: float,
    x1: float,
    y1: float,
    *,
    shaft: float,
    head_len: float,
    head_w: float,
) -> str:
    """An L-shaped arrow: a rectangular shaft to the corner, then a straight head leg."""
    hs = shaft / 2.0
    d1x, d1y = xc - x0, yc - y0
    l1 = math.hypot(d1x, d1y)
    if l1 < 1e-9:
        return _arrow_path(x0, y0, x1, y1, shaft=shaft, head_len=head_len, head_w=head_w)
    u1x, u1y = d1x / l1, d1y / l1
    p1x, p1y = -u1y, u1x

    parts: list[str] = []
    # First leg as a rectangle overshooting into the corner by half the shaft, so the
    # elbow is filled without a mitre join artefact.
    ex, ey = xc + u1x * hs, yc + u1y * hs
    quad = [
        (x0 + p1x * hs, y0 + p1y * hs),
        (ex + p1x * hs, ey + p1y * hs),
        (ex - p1x * hs, ey - p1y * hs),
        (x0 - p1x * hs, y0 - p1y * hs),
    ]
    d = f"M{_n(quad[0][0])} {_n(quad[0][1])}"
    for x, y in quad[1:]:
        d += f"L{_n(x)} {_n(y)}"
    parts.append(d + "Z")
    parts.append(_arrow_path(xc, yc, x1, y1, shaft=shaft, head_len=head_len, head_w=head_w))
    return "".join(p for p in parts if p)


# --------------------------------------------------------------------------- #
# The renderer
# --------------------------------------------------------------------------- #
def _hatch_square(canvas: _Canvas, x: float, y: float, size: float, theme: BoardTheme) -> None:
    """Fill one square with 45 deg rules, clipped analytically to the square.

    The clipping is done by solving for the segment rather than by an SVG ``clipPath``,
    for two reasons: the PDF writer in ``svgpdf`` understands ``line`` and not clip
    paths, and an analytic segment survives being scaled to any diagram width without
    the clip and the rule drifting apart by a rounding step.

    Rules run lower-left to upper-right, matching the reference books. In SVG's y-down
    space that is the family ``x + y = c``.
    """
    width = max(MIN_RULE_MM, theme.hatch_width * size)
    # `hatch_spacing` is the PERPENDICULAR pitch, in squares -- the distance a reader
    # (or a densitometer) actually measures across the rules. The family is parametrised
    # by `c = x + y` along the diagonal, where one step is sqrt(2) perpendicular
    # millimetres, so the conversion happens here, once, and the declared number means
    # what it says. Cycle 1 declared 0.155 of a square and delivered an 11 px pitch at
    # 200 DPI -- 1.6x every reference page -- because the sqrt(2) went the other way and
    # a coverage floor of 19 % opened the pitch further still.
    pitch = max(theme.hatch_spacing * size, 0.05)
    # Hold the *ink coverage* inside its band. Below about 25 mm of board the rule weight
    # stops shrinking -- it has hit MIN_RULE_MM, the finest line a press will hold --
    # while a pitch tied only to the square keeps closing up, and the two meet at a solid
    # black square (measured on the 20 mm board before this floor existed: 0.18 mm of ink
    # every 0.31 mm, 58 % coverage, a muddy grey). Opening the pitch trades rules away
    # instead, which is what a printer does by hand.
    pitch = max(pitch, width / HATCH_COVERAGE_MAX)
    spacing = pitch * math.sqrt(2.0)
    ink = theme.piece_ink
    # Start half a step in so the rules sit symmetrically inside the square instead of
    # one landing exactly on the corner.
    c = spacing / 2.0
    limit = 2.0 * size
    while c < limit:
        x0 = max(0.0, c - size)
        x1 = min(size, c)
        if x1 - x0 > 1e-9:
            canvas.line(
                x + x0, y + (c - x0),
                x + x1, y + (c - x1),
                stroke=ink, width=width,
            )
        c += spacing


def render_svg(
    fen: str,
    style: DiagramStyle | None = None,
    *,
    marks: Sequence[Mark] = (),
    font: LoadedFont | None = None,
    side_to_move: str | None = None,
) -> str:
    """Render a position to SVG.

    ``font`` may be passed in to avoid re-opening the file when rendering many diagrams;
    otherwise the family named by ``style.font`` is loaded.
    """
    style = style or DiagramStyle()
    theme = style.resolved_theme()
    board = board_from_fen(fen)
    stm = side_to_move or side_to_move_from_fen(fen)
    loaded = font if font is not None else load_font(style.font)
    # Inside labels are refused *before* the layout, not after: falling back later would
    # leave the outside labels with no gutter to stand in.
    if style.coordinates is CoordinateStyle.INSIDE and not inside_coordinates_fit(
        fen, style, font=loaded
    ):
        style = replace(style, coordinates=CoordinateStyle.OUTSIDE)
    # Same contract for the side-to-move marker: decided before the layout, because the
    # words and the square do not ask for the same gutter.
    resolved_stm = resolved_side_to_move(style)
    if resolved_stm is not style.side_to_move:
        style = replace(style, side_to_move=resolved_stm)
    lay = _layout(style)

    flip = style.orientation == "black"
    if flip:
        board = [list(reversed(row)) for row in reversed(board)]

    canvas = _Canvas()

    if style.background:
        canvas.rect(0, 0, lay.width, lay.height, fill=theme.page)

    # --- shadow, behind everything the frame draws ------------------------
    if style.frame is FrameStyle.SHADOWED:
        off = lay.shadow
        canvas.rect(
            lay.board_x - lay.frame_outer + off,
            lay.board_y - lay.frame_outer + off,
            lay.board + lay.frame_outer * 2,
            lay.board + lay.frame_outer * 2,
            fill=theme.frame,
            opacity=0.55,
        )

    # --- squares ----------------------------------------------------------
    # Order: tints, then square highlights (which are a *shift* of those tints), then
    # the hatch. The hatch has to come after the highlight or a highlighted dark square
    # loses the very rules that make it dark; cycle 1 painted the highlight last and did
    # exactly that.
    sq = lay.square
    highlights = {}
    for mark in marks:
        if isinstance(mark, SquareHighlight) and mark.style == "fill":
            row, col = square_index(mark.square)
            if flip:
                row, col = 7 - row, 7 - col
            highlights[(row, col)] = mark
    tinted = {}
    for row in range(8):
        for col in range(8):
            dark = (row + col) % 2 == 1
            fill = theme.dark if dark else theme.light
            mark = highlights.get((row, col))
            if mark is not None:
                pair = highlight_pair(theme, mark.colour)
                fill = pair[1] if dark else pair[0]
                tinted[(row, col)] = fill
            canvas.rect(
                lay.board_x + col * sq,
                lay.board_y + row * sq,
                sq,
                sq,
                fill=fill,
                opacity=mark.opacity if mark is not None else None,
            )
    if theme.hatch:
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    _hatch_square(
                        canvas, lay.board_x + col * sq, lay.board_y + row * sq, sq, theme
                    )

    # --- square highlights: the keyline, and the non-fill styles ----------
    for mark in marks:
        if isinstance(mark, SquareHighlight):
            _draw_highlight(canvas, mark, lay, theme, flip)

    # --- grid -------------------------------------------------------------
    if style.grid:
        w = max(MIN_RULE_MM, sq * 0.012)
        for i in range(1, 8):
            canvas.line(
                lay.board_x + i * sq, lay.board_y,
                lay.board_x + i * sq, lay.board_y + lay.board,
                stroke=theme.grid, width=w,
            )
            canvas.line(
                lay.board_x, lay.board_y + i * sq,
                lay.board_x + lay.board, lay.board_y + i * sq,
                stroke=theme.grid, width=w,
            )

    occupied = frozenset(
        square_name(7 - row if flip else row, 7 - col if flip else col)
        for row in range(8)
        for col in range(8)
        if board[row][col] != "."
    )

    def square_fill(name: str) -> str:
        """The colour of one square as it was actually painted, tint included."""
        row, col = square_index(name)
        if flip:
            row, col = 7 - row, 7 - col
        return tinted.get((row, col)) or (
            theme.dark if (row + col) % 2 == 1 else theme.light
        )

    # --- marks, UNDER the pieces ------------------------------------------
    # See MARK_PAINT_ORDER. The annotation goes below the position; only the arrowhead
    # comes back on top, in step 5, so a shaft can cross a piece without cutting it.
    for mark in marks:
        if isinstance(mark, CircleMark):
            _draw_circle(canvas, mark, lay, theme, flip)
        elif isinstance(mark, Arrow):
            _draw_arrow(canvas, mark, lay, theme, flip, occupied)

    # --- pieces -----------------------------------------------------------
    _draw_pieces(canvas, board, lay, theme, style, loaded)

    # --- frame ------------------------------------------------------------
    _draw_frame(canvas, lay, theme, style)

    # --- coordinates ------------------------------------------------------
    _draw_coordinates(canvas, lay, theme, style, flip)

    # --- arrowheads, back on top, keylined in their square's colour -------
    for mark in marks:
        if isinstance(mark, Arrow):
            _draw_arrow_head(canvas, mark, lay, theme, flip, square_fill, occupied)

    # --- inside coordinates, in a corner no piece stands in ---------------
    if lay.coordinates is CoordinateStyle.INSIDE:
        _draw_inside_coordinates(canvas, lay, theme, style, flip, board, loaded)

    # --- side to move -----------------------------------------------------
    _draw_side_to_move(canvas, lay, theme, style, stm)

    header = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_n(lay.width)}mm" height="{_n(lay.height)}mm" '
        f'viewBox="0 0 {_n(lay.width)} {_n(lay.height)}" '
        f'role="img" aria-label="{_escape(_aria_label(fen, stm))}">'
    )
    return header + "".join(canvas.parts) + "</svg>"


def _aria_label(fen: str, stm: str) -> str:
    who = "brancas" if stm == "w" else "pretas"
    placement = fen.strip().split()[0] if fen.strip() else ""
    return f"Diagrama de xadrez, posicao {placement}, jogam as {who}"


def _square_xy(lay: _Layout, name: str, flip: bool) -> tuple[float, float]:
    row, col = square_index(name)
    if flip:
        row, col = 7 - row, 7 - col
    return lay.board_x + col * lay.square, lay.board_y + row * lay.square


def _draw_pieces(
    canvas: _Canvas,
    board: list[list[str]],
    lay: _Layout,
    theme: BoardTheme,
    style: DiagramStyle,
    font: LoadedFont,
) -> None:
    """Two layers per piece: body, then ink. See ``outlines`` for why.

    The legacy fonts are drawn so that one em is exactly one square with the baseline on
    the square's bottom edge, so the glyph is placed at that scale and origin rather than
    being centred by its bounding box -- centring is what makes pieces bob up and down
    from square to square in amateur output.
    """
    sq = lay.square
    upem = font.units_per_em
    scale = (sq / upem) * style.piece_scale
    # Re-centre the shrunk em box when piece_scale is not 1.
    slack = (sq - sq * style.piece_scale) / 2.0

    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == ".":
                continue
            outline = font.piece_outline(piece)
            if outline.is_empty():
                _draw_missing_glyph(canvas, lay, theme, row, col, piece)
                continue
            x = lay.board_x + col * sq + slack
            # Baseline sits on the bottom edge of the square; font y is up, SVG y down.
            y = lay.board_y + row * sq + sq - slack
            if font.spec.model is FontModel.UNICODE:
                x, y = _fit_unicode_glyph(outline, lay, row, col, style)
                scale_here = _unicode_scale(outline, sq, style)
            else:
                scale_here = scale

            body = outline.to_svg_path(
                scale=scale_here, dx=x, dy=y, contours=outline.outer_contours()
            )
            canvas.path(body, fill=theme.piece_body)
            if style.show_piece_outline:
                full = outline.to_svg_path(scale=scale_here, dx=x, dy=y)
                canvas.path(full, fill=theme.piece_ink, rule="nonzero")


def _unicode_scale(outline: Outline, sq: float, style: DiagramStyle) -> float:
    """Unicode chess glyphs vary wildly in how much of the em they use, so they are
    fitted to the square by their own bounding box instead of by the em."""
    x0, y0, x1, y1 = outline.bbox()
    extent = max(x1 - x0, y1 - y0)
    if extent <= 0:
        return sq / outline.units_per_em
    return (sq * 0.84 * style.piece_scale) / extent


def _fit_unicode_glyph(
    outline: Outline, lay: _Layout, row: int, col: int, style: DiagramStyle
) -> tuple[float, float]:
    sq = lay.square
    scale = _unicode_scale(outline, sq, style)
    x0, y0, x1, y1 = outline.bbox()
    w, h = (x1 - x0) * scale, (y1 - y0) * scale
    cx = lay.board_x + col * sq + (sq - w) / 2.0
    cy = lay.board_y + row * sq + (sq + h) / 2.0
    return cx - x0 * scale, cy + y0 * scale


def _draw_missing_glyph(
    canvas: _Canvas, lay: _Layout, theme: BoardTheme, row: int, col: int, piece: str
) -> None:
    """Fallback when the family has no glyph for a piece.

    Deliberately conspicuous. A silently blank square is the failure mode that lets a
    wrong diagram reach print; a box with the FEN letter in it does not.
    """
    sq = lay.square
    x = lay.board_x + col * sq + sq * 0.18
    y = lay.board_y + row * sq + sq * 0.18
    canvas.rect(
        x, y, sq * 0.64, sq * 0.64,
        fill="none", stroke=theme.piece_ink, stroke_width=max(MIN_RULE_MM, sq * 0.03),
    )
    canvas.text(
        lay.board_x + col * sq + sq * 0.5,
        lay.board_y + row * sq + sq * 0.68,
        piece,
        size=sq * 0.42,
        fill=theme.piece_ink,
        family="monospace",
    )


def _draw_frame(canvas: _Canvas, lay: _Layout, theme: BoardTheme, style: DiagramStyle) -> None:
    if style.frame is FrameStyle.NONE:
        return
    outer, inner, gap = lay.frame_outer, lay.frame_inner, lay.frame_gap

    def stroke_rect(inset: float, width: float) -> None:
        # A stroke straddles its path, so the path is placed half a stroke out from the
        # board edge for the rule to sit flush against the squares.
        half = width / 2.0
        canvas.rect(
            lay.board_x - inset - half,
            lay.board_y - inset - half,
            lay.board + 2 * (inset + half),
            lay.board + 2 * (inset + half),
            fill="none",
            stroke=theme.frame,
            stroke_width=width,
        )

    if style.frame in (FrameStyle.HAIRLINE, FrameStyle.RULE, FrameStyle.SHADOWED):
        stroke_rect(0.0, outer)
    elif style.frame is FrameStyle.DOUBLE:
        stroke_rect(0.0, inner)
        stroke_rect(inner + gap, outer)
    elif style.frame is FrameStyle.INSET:
        stroke_rect(0.0, outer)
        # Second rule *inside* the board edge.
        half = inner / 2.0
        canvas.rect(
            lay.board_x + gap + half,
            lay.board_y + gap + half,
            lay.board - 2 * (gap + half),
            lay.board - 2 * (gap + half),
            fill="none",
            stroke=theme.frame,
            stroke_width=inner,
        )


def _draw_coordinates(
    canvas: _Canvas, lay: _Layout, theme: BoardTheme, style: DiagramStyle, flip: bool
) -> None:
    # ``lay.coordinates`` and not ``style.coordinates``: below MIN_COORDINATE_PT the
    # labels are withheld, and the layout is the single place that decision is made.
    mode = lay.coordinates
    if mode is CoordinateStyle.NONE or mode is CoordinateStyle.INSIDE:
        # Inside labels are drawn last, over the pieces, on their own plates.
        return
    size = lay.coord_size
    sq = lay.square
    files = list(FILES) if not flip else list(reversed(FILES))
    ranks = list(RANKS) if not flip else list(reversed(RANKS))
    frame_total = lay.frame_total

    # Outside, the book convention: files under the board, ranks in the side gutter.
    # The baseline sits a little under half the type size below the frame, which is what
    # puts the digits optically level with the board rather than hanging off it.
    for col, ch in enumerate(files):
        canvas.text(
            lay.board_x + col * sq + sq / 2.0,
            lay.board_y + lay.board + frame_total + size * 1.02,
            ch, size=size, fill=theme.coordinate, family=style.coordinate_font, anchor="middle",
        )
    right = mode is CoordinateStyle.OUTSIDE_RIGHT
    for row, ch in enumerate(ranks):
        x = (
            lay.board_x + lay.board + frame_total + size * 0.62
            if right
            else lay.board_x - frame_total - size * 0.62
        )
        canvas.text(
            x,
            # 0.35 em above the square's centre puts the digit's optical centre on the
            # rank; using the geometric centre makes numerals sit low.
            lay.board_y + row * sq + sq / 2.0 + size * 0.35,
            ch,
            size=size,
            fill=theme.coordinate,
            family=style.coordinate_font,
            anchor="start" if right else "end",
        )


INSIDE_LABEL_GRID = 96
"""Resolution of the silhouette map used to find a free corner. See ``_free_corner``."""

INSIDE_LABEL_CLEAR = 0.025
"""Clear space kept between an inside label and the piece on its square, in squares."""

_INSIDE_INSETS = (0.020, 0.035, 0.050, 0.065, 0.080, 0.095)
"""Insets from the square's edges tried, in order, when looking for a free corner."""


def _label_box(size: float, square: float) -> tuple[float, float]:
    """Width and height of one inside label's clear box, in millimetres.

    A digit of a serif face carries ink about 0.62 em wide and 0.72 em tall (figure
    height plus the tail of a ``4``); the clearance is added on every side so a label
    that just clears the piece still looks clear.
    """
    clear = square * INSIDE_LABEL_CLEAR
    return size * 0.62 + 2 * clear, size * 0.72 + 2 * clear


@lru_cache(maxsize=64)
def _silhouette(font_key: str, piece: str, piece_scale: float,
                n: int = INSIDE_LABEL_GRID) -> tuple[tuple[int, ...], ...]:
    """Prefix sums of the piece's silhouette on an ``n x n`` grid over its square.

    The *silhouette*, not the ink: a label sitting in the white belly of a rook is the
    cycle-1 defect ("o algarismo 2 continua desenhado dentro do peao de a2"), even though
    no black pixel is touched. The outer contours are filled by scanline, which is the
    same rule the renderer fills them with.
    """
    loaded = load_font(font_key)
    outline = loaded.piece_outline(piece)
    upem = loaded.units_per_em
    rows = [[0] * n for _ in range(n)]
    if not outline.is_empty():
        slack = (1.0 - piece_scale) / 2.0
        if loaded.spec.model is FontModel.UNICODE:
            # A Unicode chess glyph uses whatever part of the em it likes, so the
            # renderer fits it by its own bounding box; the map has to use the same
            # transform or it would guard the wrong region.
            x0, y0, x1, y1 = outline.bbox()
            extent = max(x1 - x0, y1 - y0) or upem
            k = 0.84 * piece_scale / extent
            wn, hn = (x1 - x0) * k, (y1 - y0) * k

            def to_square(px: float, py: float) -> tuple[float, float]:
                return ((1.0 - wn) / 2.0 + (px - x0) * k,
                        (1.0 + hn) / 2.0 - (py - y0) * k)
        else:
            def to_square(px: float, py: float) -> tuple[float, float]:
                return (slack + (px / upem) * piece_scale,
                        slack + (1.0 - py / upem) * piece_scale)

        polys: list[list[tuple[float, float]]] = []
        for contour in outline.outer_contours():
            pts = contour.points()
            if len(pts) < 3:
                continue
            polys.append([
                (sx * n, sy * n) for sx, sy in (to_square(px, py) for px, py in pts)
            ])
        for row in range(n):
            y = row + 0.5
            xs: list[float] = []
            for poly in polys:
                for i in range(len(poly)):
                    x0, y0 = poly[i]
                    x1, y1 = poly[(i + 1) % len(poly)]
                    if (y0 <= y < y1) or (y1 <= y < y0):
                        xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                a = max(0, int(xs[i]))
                b = min(n - 1, int(xs[i + 1]))
                for col in range(a, b + 1):
                    rows[row][col] = 1
    # 2-D prefix sums, (n+1) x (n+1), so a box query is four lookups.
    acc = [[0] * (n + 1) for _ in range(n + 1)]
    for r in range(n):
        run = 0
        for c in range(n):
            run += rows[r][c]
            acc[r + 1][c + 1] = acc[r][c + 1] + run
    return tuple(tuple(row) for row in acc)


def _box_cover(acc, n: int, x0: float, y0: float, x1: float, y1: float) -> int:
    """Silhouette cells inside the box, all coordinates in square fractions."""
    a = max(0, min(n, int(x0 * n)))
    b = max(0, min(n, int(y0 * n)))
    c = max(0, min(n, int(x1 * n + 0.999)))
    d = max(0, min(n, int(y1 * n + 0.999)))
    if c <= a or d <= b:
        return 0
    return acc[d][c] - acc[b][c] - acc[d][a] + acc[b][a]


def _free_corner(font_key: str, piece: str, piece_scale: float,
                 box_w: float, box_h: float,
                 prefer: str = "br") -> tuple[float, float] | None:
    """Centre of a label box that no part of ``piece`` reaches, in square fractions.

    Corners are tried nearest-the-board-edge first, then the two remaining ones; within
    a corner the box is pushed a little further into the angle until it is clear. Returns
    ``None`` when the piece leaves no free corner at all -- a rook or a queen in most
    families -- which is what makes ``CoordinateStyle.INSIDE`` refuse the diagram rather
    than deface it.
    """
    order = {
        "br": ("br", "bl", "tr", "tl"),
        "tl": ("tl", "tr", "bl", "br"),
    }[prefer]

    def centre(corner: str, inset: float) -> tuple[float, float]:
        x = box_w / 2.0 + inset if corner[1] == "l" else 1.0 - box_w / 2.0 - inset
        y = box_h / 2.0 + inset if corner[0] == "t" else 1.0 - box_h / 2.0 - inset
        return x, y

    if piece == ".":
        return centre(order[0], _INSIDE_INSETS[0])
    n = INSIDE_LABEL_GRID
    acc = _silhouette(font_key, piece, piece_scale, n)

    def clear(corner: str, inset: float) -> "tuple[float, float] | None":
        cx, cy = centre(corner, inset)
        if _box_cover(acc, n, cx - box_w / 2.0, cy - box_h / 2.0,
                      cx + box_w / 2.0, cy + box_h / 2.0) == 0:
            return cx, cy
        return None

    # Every inset on the preferred EDGE before any corner on the far one. Cycle 5 tried
    # all four corners at each inset in turn, so a king that blocked both bottom corners
    # at the shallowest inset sent its file letter to the top of the square: the critic
    # measured `a b c d e f h` on y = 199.71 pt and the `g` on y = 187.57 -- **12.14 pt
    # above the line**, two thirds of a square, in a row of eight labels that reads as
    # one row. A label pushed further into its own angle stays on the line; a label
    # moved to the other end of the square breaks it, and the charter calls that
    # "alinhamento optico errado".
    near = [c for c in order if c[0] == order[0][0]]
    far = [c for c in order if c[0] != order[0][0]]
    for group in (near, far):
        for inset in _INSIDE_INSETS:
            for corner in group:
                found = clear(corner, inset)
                if found is not None:
                    return found
    return None


def _shared_corner(font_key: str, pieces: "Sequence[str]", piece_scale: float,
                   box_w: float, box_h: float,
                   prefer: str = "br") -> tuple[float, float] | None:
    """One label position, in square fractions, that is clear in **every** square given.

    A rank of eight file letters is a row, and a row sits on one baseline. Cycle 6 found
    each label its own free corner and the critic measured the result: `a b c d e f h` on
    ``y = 199.71 pt`` and the `g` on ``y = 187.57`` -- **12.14 pt above**, two thirds of a
    square, because the Merida king covers the bottom of g1 at every inset and that one
    letter went to the top of its square alone. The charter calls a broken row
    "alinhamento optico errado", and it is the same fault whichever letter breaks it.

    So the eight are placed together: the corner nearest the board edge is tried at each
    inset, and only a corner clear in all eight is taken. When the bottom is blocked
    anywhere, all eight go to the top of their own squares -- still each inside its own
    square, still a row. Only if no corner is clear in all eight does the position lose
    its inside labels altogether, and ``inside_coordinates_fit`` says so beforehand.
    """
    order = {
        "br": ("br", "bl", "tr", "tl"),
        "tl": ("tl", "tr", "bl", "br"),
    }[prefer]

    def centre(corner: str, inset: float) -> tuple[float, float]:
        x = box_w / 2.0 + inset if corner[1] == "l" else 1.0 - box_w / 2.0 - inset
        y = box_h / 2.0 + inset if corner[0] == "t" else 1.0 - box_h / 2.0 - inset
        return x, y

    n = INSIDE_LABEL_GRID
    silhouettes = [None if piece == "." else _silhouette(font_key, piece, piece_scale, n)
                   for piece in pieces]
    near = [c for c in order if c[0] == order[0][0]]
    far = [c for c in order if c[0] != order[0][0]]
    for group in (near, far):
        for inset in _INSIDE_INSETS:
            for corner in group:
                cx, cy = centre(corner, inset)
                if all(acc is None
                       or _box_cover(acc, n, cx - box_w / 2.0, cy - box_h / 2.0,
                                     cx + box_w / 2.0, cy + box_h / 2.0) == 0
                       for acc in silhouettes):
                    return cx, cy
    return None


def inside_coordinates_fit(
    fen: str, style: DiagramStyle, *, font: LoadedFont | None = None
) -> bool:
    """True when every inside label of this position has a corner of its own.

    ``CoordinateStyle.INSIDE`` is honoured only when this is true. It is exposed because
    a caller that asked for inside labels has a right to know it is not getting them --
    the same contract ``_Layout.coordinates_suppressed`` keeps for tiny diagrams.
    """
    if style.coordinates is not CoordinateStyle.INSIDE:
        return True
    board = board_from_fen(fen)
    if style.orientation == "black":
        board = [list(reversed(row)) for row in reversed(board)]
    key = (font.spec.key if font is not None else style.font)
    lay = _layout(replace(style, coordinates=CoordinateStyle.NONE))
    size = lay.square * style.inside_coordinate_scale
    bw, bh = _label_box(size, lay.square)
    bw, bh = bw / lay.square, bh / lay.square
    files = [board[7][col] for col in range(8)]
    ranks = [board[row][0] for row in range(8)]
    return (_shared_corner(key, files, style.piece_scale, bw, bh, "br") is not None
            and _shared_corner(key, ranks, style.piece_scale, bw, bh, "tl") is not None)


def _draw_inside_coordinates(
    canvas: _Canvas,
    lay: _Layout,
    theme: BoardTheme,
    style: DiagramStyle,
    flip: bool,
    board: list[list[str]],
    font: LoadedFont,
) -> None:
    """Coordinates set inside the edge squares, each in a corner no piece reaches.

    Cycle 1 drew them under the pieces: seven of sixteen were destroyed. Cycle 2 drew
    them last on **opaque plates**, which made all sixteen legible and moved the damage
    onto the position -- the critic measured rectangular bites out of the c1 rook, the d1
    queen, the f1 rook and the g1 king, the ``2`` still inside the a2 pawn, and the ``2``
    itself cut by the rank edge.

    There is no plate now and nothing is drawn over a piece. The label goes in a corner
    of its square that the piece does not occupy, found by ``_free_corner`` against the
    glyph's own silhouette. A position that leaves no such corner does not get inside
    labels at all: ``inside_coordinates_fit`` says so before the layout is computed and
    the diagram falls back to the outside convention, gutter and all.
    """
    size = lay.coord_size
    sq = lay.square
    files = list(FILES) if not flip else list(reversed(FILES))
    ranks = list(RANKS) if not flip else list(reversed(RANKS))
    bw, bh = _label_box(size, sq)
    fw, fh = bw / sq, bh / sq
    key = font.spec.key

    def place(row: int, col: int, ch: str, spot: "tuple[float, float] | None") -> None:
        if spot is None:  # pragma: no cover - refused by inside_coordinates_fit
            return
        cx, cy = spot
        x = lay.board_x + col * sq + cx * sq
        # `cy` is the centre of the clear box; the baseline sits below it by half the
        # figure height, which is what puts the digit optically inside the box.
        y = lay.board_y + row * sq + cy * sq + size * 0.36
        canvas.text(
            x, y, ch, size=size, fill=theme.coordinate,
            family=style.coordinate_font, anchor="middle",
        )

    # One spot for the whole rank of file letters, one for the whole file of rank
    # figures: the eight labels of a row are set on one line or the row is broken.
    file_spot = _shared_corner(key, [board[7][col] for col in range(8)],
                               style.piece_scale, fw, fh, "br")
    rank_spot = _shared_corner(key, [board[row][0] for row in range(8)],
                               style.piece_scale, fw, fh, "tl")
    for col, ch in enumerate(files):
        place(7, col, ch, file_spot)
    for row, ch in enumerate(ranks):
        place(row, 0, ch, rank_spot)


def _stm_text_size(lay: _Layout, style: DiagramStyle) -> float:
    """Type size of the ``SideToMove.TEXT`` marker, in millimetres."""
    return lay.coord_size or lay.square * 0.30


def resolved_side_to_move(style: DiagramStyle) -> SideToMove:
    """The marker actually drawn -- ``TEXT`` degrades when it would set below the floor.

    On a 4 mm-square specimen ``TEXT`` set "Pretas jogam" at **3.40 pt**: smaller than the
    3.92 pt the cycle-1 critic blocked, printed on the very sheet that announces a 5.5 pt
    floor, and missed because the floor test only looked at one-character coordinates.
    The floor belongs to the *renderer*, not to the test: below it the words are replaced
    by the square marker, which carries the same information at any size.
    """
    if style.side_to_move is not SideToMove.TEXT:
        return style.side_to_move
    lay = _layout(style)
    if _stm_text_size(lay, style) * (72.0 / 25.4) < style.min_coordinate_pt:
        return SideToMove.SQUARE
    return SideToMove.TEXT


def _draw_side_to_move(
    canvas: _Canvas, lay: _Layout, theme: BoardTheme, style: DiagramStyle, stm: str
) -> None:
    kind = style.side_to_move
    if kind is SideToMove.NONE:
        return
    black = stm == "b"
    frame_total = lay.frame_total
    sq = lay.square
    size = sq * _STM_SIZE
    gap = sq * _STM_GAP
    # `OUTSIDE_RIGHT` puts the rank digits in this same strip, so the marker steps over
    # their gutter. Without it the two are drawn on top of each other -- and before
    # cycle 11 they were drawn on top of each other *and* past the diagram's declared
    # width, because the gutter was being reserved on the far side. The width arithmetic
    # pays for both (`denom_w` counts `gutter + stm_units`); this spends it correctly.
    beside = lay.coord_gutter if lay.coordinates is CoordinateStyle.OUTSIDE_RIGHT else 0.0
    x = lay.board_x + lay.board + frame_total + beside + gap
    # Black to move is marked at the top of the board, White at the bottom: the marker
    # sits on the side of the board that player is playing from.
    y = lay.board_y if black else lay.board_y + lay.board - size
    rule = max(MIN_RULE_MM, sq * 0.045)

    # The marker stands on the *page*, not on the board, so its outline has to contrast
    # with the page. Using the frame colour looked right on white paper and made the
    # marker vanish in the dark theme, where frame and page are both near-black -- the
    # one mark that says whose move it is, invisible. The coordinate colour is the
    # theme's answer to "ink that reads against the page", so it is the right one here.
    edge = theme.coordinate
    fill = theme.piece_ink if black else theme.piece_body

    if kind is SideToMove.SQUARE:
        canvas.rect(x, y, size, size, fill=fill, stroke=edge, stroke_width=rule)
    elif kind is SideToMove.DOT:
        canvas.circle(
            x + size / 2.0, y + size / 2.0, size / 2.0,
            fill=fill, stroke=edge, stroke_width=rule,
        )
    elif kind is SideToMove.TRIANGLE:
        if black:
            d = f"M{_n(x)} {_n(y)}L{_n(x + size)} {_n(y)}L{_n(x + size / 2)} {_n(y + size)}Z"
        else:
            d = f"M{_n(x)} {_n(y + size)}L{_n(x + size)} {_n(y + size)}L{_n(x + size / 2)} {_n(y)}Z"
        canvas.path(d, fill=fill, stroke=edge, stroke_width=rule, linejoin="miter")
    elif kind is SideToMove.BAR:
        bar_h = sq * 0.16
        by = lay.board_y - frame_total - bar_h * 1.4 if black else (
            lay.board_y + lay.board + frame_total + bar_h * 0.4
        )
        canvas.rect(
            lay.board_x + lay.board - sq * 1.2, by, sq * 1.2, bar_h,
            fill=fill, stroke=edge, stroke_width=max(MIN_RULE_MM, sq * 0.02),
        )
    elif kind is SideToMove.TEXT:
        canvas.text(
            x, y + size * 0.8,
            "Pretas jogam" if black else "Brancas jogam",
            size=_stm_text_size(lay, style),
            fill=theme.coordinate,
            family=style.coordinate_font,
            anchor="start",
        )


def _draw_highlight(
    canvas: _Canvas, mark: SquareHighlight, lay: _Layout, theme: BoardTheme, flip: bool
) -> None:
    x, y = _square_xy(lay, mark.square, flip)
    sq = lay.square
    colour = mark.colour or theme.highlight
    if mark.style == "fill":
        # The tint itself was applied to the square in `render_svg`, as a shift of the
        # square's own colour so the chequer survives. What is left here is the keyline:
        # once both tints move by the same delta a highlighted light square lands close
        # to an ordinary dark one, and without an edge the reader cannot tell where the
        # highlight begins. The critic measured that as 1.95:1 in cycle 1.
        w = max(MIN_RULE_MM, sq * 0.055)
        canvas.rect(
            x + w / 2, y + w / 2, sq - w, sq - w,
            fill="none", stroke=theme.highlight, stroke_width=w, opacity=mark.opacity,
        )
    elif mark.style == "outline":
        w = max(MIN_RULE_MM, sq * 0.075)
        canvas.rect(
            x + w / 2, y + w / 2, sq - w, sq - w,
            fill="none", stroke=colour, stroke_width=w, opacity=mark.opacity,
        )
    else:  # corner ticks -- readable in greyscale and never hides the piece
        w = max(MIN_RULE_MM, sq * 0.07)
        arm = sq * 0.28
        d = (
            f"M{_n(x)} {_n(y + arm)}L{_n(x)} {_n(y)}L{_n(x + arm)} {_n(y)}"
            f"M{_n(x + sq - arm)} {_n(y)}L{_n(x + sq)} {_n(y)}L{_n(x + sq)} {_n(y + arm)}"
            f"M{_n(x + sq)} {_n(y + sq - arm)}L{_n(x + sq)} {_n(y + sq)}L{_n(x + sq - arm)} {_n(y + sq)}"
            f"M{_n(x + arm)} {_n(y + sq)}L{_n(x)} {_n(y + sq)}L{_n(x)} {_n(y + sq - arm)}"
        )
        canvas.path(d, fill="none", stroke=colour, stroke_width=w, opacity=mark.opacity, linecap="square")


MARK_PAINT_ORDER = "under the pieces; only the head is redrawn on top"
"""How an annotation and a position share the page. Read this before changing it.

Cycle 2 gave every mark a *knockout*: the shape was stroked first in the page colour,
0.30 mm each side, and then filled. On a board whose pieces are white **outlines**, a
white keyline drawn over a white outline erases the outline. The critic measured the
result on proofsheet page 5: the b2 and f2 pawns lost the join between head and body,
the c5 pawn's base was replaced by an arrowhead, and the d2 knight was left with a white
bite out of its tail. The metric cycle 2 chose -- pixels of the arrow's colour inside the
arrowhead -- went *up* as the defect got worse.

The order below is the one a publisher uses, and it needs no knockout at all:

1. squares, hatch, highlights, grid;
2. **marks**: circles and whole arrows, plain fills, drawn *under* the pieces;
3. pieces;
4. frame and outside coordinates;
5. **arrowheads again**, over the pieces, each stroked in its own destination square's
   colour so the tip is separated from whatever it lands on without cutting it.

Consequence: a piece crossed by a shaft is drawn *after* the shaft and comes out whole --
its outline has exactly the connected components it had with no mark at all. Only the
destination piece carries ink on top of it, and only the head's worth: see
:data:`MARK_HEAD_LANDING`."""

MARK_HEAD_LANDING = 0.30
"""Where the arrow's tip stops, as a fraction of a square from the target's centre.

Far enough out that the head sits on the *edge* of the destination piece rather than in
the middle of it: measured, 88 to 95 % of the piece's ink still shows. Cycle 2 stopped at
0.12 and the head replaced the c5 pawn's base."""

MARK_HEAD_KEYLINE = 0.030
"""Width of the keyline around the redrawn arrowhead, as a fraction of a square.

Drawn in the *destination square's* colour, not the page's: on a dark square a white
keyline is a hole. It is a stroke on the head alone, so it costs the piece a rim of ink
and not a limb."""

MARK_INK_MIN_CONTRAST = 3.0
"""Contrast the mark colour must hold against the piece it lands on (WCAG 1.4.11).

`test_the_arrowhead_contrasts_with_the_piece_it_lands_on` asserts it for every theme.
The LaTeX side measured 1.99:1 in cycle 2 and the SVG side 1.85:1; both are now 3.39:1."""

KNOCKOUT_MM = 0.0
"""Deprecated, and kept at zero so nothing silently reintroduces it.

See :data:`MARK_PAINT_ORDER` for what replaced it and why."""


def _draw_circle(
    canvas: _Canvas, mark: CircleMark, lay: _Layout, theme: BoardTheme, flip: bool
) -> None:
    """A ring round a square, drawn *under* the pieces. See :data:`MARK_PAINT_ORDER`."""
    x, y = _square_xy(lay, mark.square, flip)
    sq = lay.square
    w = max(MIN_RULE_MM, sq * mark.width_scale)
    cx, cy = x + sq / 2.0, y + sq / 2.0
    r = sq / 2.0 - w / 2.0 - sq * 0.04
    canvas.circle(
        cx, cy, r,
        fill="none", stroke=mark.colour or theme.circle, stroke_width=w,
    )


def _arrow_paths(
    mark: Arrow,
    lay: _Layout,
    flip: bool,
    occupied: frozenset = frozenset(),
) -> tuple[str, str]:
    """``(whole arrow, head only)`` as SVG path data, in millimetres.

    One geometry, two paths, so the head drawn on top in step 5 is exactly the head that
    was drawn under the pieces in step 2 -- no second computation to drift out of step.
    """
    sq = lay.square
    sx, sy = _square_xy(lay, mark.source, flip)
    tx, ty = _square_xy(lay, mark.target, flip)
    cx0, cy0 = sx + sq / 2.0, sy + sq / 2.0
    cx1, cy1 = tx + sq / 2.0, ty + sq / 2.0

    shaft = max(MIN_RULE_MM * 2, sq * mark.width_scale)
    # Fixed proportions: a head 2.2 shafts long and 2.5 wide reads as an arrowhead at
    # every size. Deriving either from the arrow's *length* is what produces the
    # stretched heads that give amateur diagrams away.
    head_len = shaft * 2.2
    head_w = shaft * 2.5

    row_s, col_s = square_index(mark.source)
    row_t, col_t = square_index(mark.target)
    dr, dc = abs(row_t - row_s), abs(col_t - col_s)
    is_knight = sorted((dr, dc)) == [1, 2]

    # An arrow that starts inside the piece it leaves reads as a spike growing out of it
    # (cycle 1: "a seta g2-b7 comeca dentro do bispo de g2"). When the source square
    # carries a piece the tail is pushed out to the square's edge; on an empty square it
    # may start closer in, which looks less amputated.
    tail = 0.44 if mark.source.strip().lower() in occupied else 0.30
    land = MARK_HEAD_LANDING

    if is_knight and mark.knight_elbow:
        # Travel the long leg first, then turn: the shape a knight's move is drawn as.
        ex, ey = (cx1, cy0) if dc == 2 else (cx0, cy1)
        first_len = math.hypot(ex - cx0, ey - cy0)
        if first_len > 1e-9:
            ux, uy = (ex - cx0) / first_len, (ey - cy0) / first_len
            bx, by = cx0 + ux * sq * tail, cy0 + uy * sq * tail
        else:
            bx, by = cx0, cy0
        second = math.hypot(cx1 - ex, cy1 - ey)
        if second > 1e-9:
            vx, vy = (cx1 - ex) / second, (cy1 - ey) / second
            fx, fy = cx1 - vx * sq * land, cy1 - vy * sq * land
        else:
            fx, fy = cx1, cy1
        whole = _elbow_arrow_path(
            bx, by, ex, ey, fx, fy, shaft=shaft, head_len=head_len, head_w=head_w
        )
        head = _arrow_head_path(
            ex, ey, fx, fy, shaft=shaft, head_len=head_len, head_w=head_w
        )
        return whole, head

    length = math.hypot(cx1 - cx0, cy1 - cy0)
    if length < 1e-9:
        return "", ""
    ux, uy = (cx1 - cx0) / length, (cy1 - cy0) / length
    bx, by = cx0 + ux * sq * tail, cy0 + uy * sq * tail
    fx, fy = cx1 - ux * sq * land, cy1 - uy * sq * land
    whole = _arrow_path(bx, by, fx, fy, shaft=shaft, head_len=head_len, head_w=head_w)
    head = _arrow_head_path(bx, by, fx, fy, shaft=shaft, head_len=head_len, head_w=head_w)
    return whole, head


def _draw_arrow(
    canvas: _Canvas,
    mark: Arrow,
    lay: _Layout,
    theme: BoardTheme,
    flip: bool,
    occupied: frozenset = frozenset(),
) -> None:
    """The whole arrow, plain fill, under the pieces. Step 2 of :data:`MARK_PAINT_ORDER`."""
    whole, _ = _arrow_paths(mark, lay, flip, occupied)
    if not whole:
        return
    canvas.path(whole, fill=mark.colour or theme.arrow, opacity=mark.opacity,
                linejoin="miter")


def _draw_arrow_head(
    canvas: _Canvas,
    mark: Arrow,
    lay: _Layout,
    theme: BoardTheme,
    flip: bool,
    square_fill: "Callable[[str], str]",
    occupied: frozenset = frozenset(),
) -> None:
    """The head alone, over the pieces, keylined in its destination square's colour.

    Step 5 of :data:`MARK_PAINT_ORDER`.
    """
    _, head = _arrow_paths(mark, lay, flip, occupied)
    if not head:
        return
    keyline = max(MIN_RULE_MM * 0.5, lay.square * MARK_HEAD_KEYLINE)
    colour = mark.colour or theme.arrow
    canvas.path(
        head, fill=square_fill(mark.target), stroke=square_fill(mark.target),
        stroke_width=keyline, opacity=mark.opacity, linejoin="miter",
    )
    canvas.path(head, fill=colour, opacity=mark.opacity, linejoin="miter")


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
def render_many(
    positions: Iterable[tuple[str, DiagramStyle]],
) -> list[str]:
    """Render several diagrams, reusing each opened font. Fonts dominate the cost."""
    cache: dict[str, LoadedFont] = {}
    out: list[str] = []
    for fen, style in positions:
        font = cache.get(style.font)
        if font is None:
            font = load_font(style.font)
            cache[style.font] = font
        out.append(render_svg(fen, style, font=font))
    return out
