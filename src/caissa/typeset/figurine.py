"""Inline figurine notation: a piece glyph set into running text, correctly.

Origem: PDFimport/PDFImport_v1.2.0/PDFImport/chessfig.py
Absorvido em 2026-09-07. Alteracoes: o `chessfig.py` resolvia o problema **inverso** --
ler figurino de um PDF e converter para Unicode. Aqui o caminho e o de saida, e o
problema deixa de ser de mapeamento e passa a ser de *metrica*: onde o glifo pousa em
relacao a linha de base e de que tamanho ele e em relacao a letra ao lado.

The problem
-----------
Setting ``Nf3`` as a knight glyph followed by ``f3`` is easy to do and easy to do badly,
and it is the single detail that tells a reader an amateur set the page. Three things go
wrong, all of them at once:

**Vertical placement.** A chess font's piece is drawn to fill a *board square*, so it
sits on the em's baseline and rises nearly a full em. Dropped into a line of 10 pt text
it towers over the lower case and its foot lands below the baseline of the digits beside
it. The fix is not a nudge until it looks right: it is to measure the glyph's own
bounding box in font units and shift it so its *foot* meets the text baseline.

**Optical size.** Scaling the piece to the text's point size makes it far too big,
because point size measures the em and the piece uses all of it while a capital letter
uses about 70 %. A figurine is sized against the **cap height** of the text it sits in --
that is what makes it look like it belongs to the same alphabet.

**Spacing.** ``N`` and ``f3`` are one token, not two words. There is no space between the
piece and the square, but a figurine is optically wider than a capital N and needs a
little air after it, and none before a following ``x``.

Everything here is derived from font metrics. Nothing is a magic constant chosen by
squinting, and :func:`measure_family` reports the numbers so a test can assert them.
"""

from __future__ import annotations

import math

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal, Mapping, Sequence

from caissa.core.chess.notation_tables import (
    NotationError,
    piece_for_letter,
    piece_letter,
    to_language,
)

from .fonts import LoadedFont, UNICODE_PIECES, load_font
from .outlines import Outline, format_number

__all__ = [
    "FigurineMetrics",
    "FigurineRun",
    "SAN_LETTERS",
    "language_letter",
    "PIECE_LETTERS",
    "SanMove",
    "figurine_svg",
    "weight_for",
    "measure_family",
    "measure_for",
    "parse_san",
    "san_to_figurine_runs",
    "translate_san",
]

# SAN piece letters by language live in one place -- ``caissa.core.chess.notation_tables``
# (ADR-0008). This module used to carry its own copy, and the copy disagreed with the
# canonical table (Russian king ``К`` for ``Кр``, knight ``Ко`` for ``К``); the LaTeX
# side printed the wrong letters because of it (OCR_UI_ROADMAP_C2 A6).
def language_letter(letter: str, language: str) -> str:
    """The reader's letter for an English SAN piece letter, from the canonical table.

    ``N`` becomes ``C`` in Portuguese, ``S`` in German and ``К`` in Russian. A letter
    that names no piece, and a language with no table, fall back to the English letter
    rather than raising: this is called while a page is being set, and a blank is the
    one failure a reader cannot recover from.
    """
    piece = piece_for_letter(letter, "en")
    if piece is None:
        return letter
    try:
        return piece_letter(piece, language)
    except NotationError:
        return piece_letter(piece, "en")


PIECE_LETTERS = "KQRBN"

SAN_LETTERS: dict[str, str] = {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N"}
"""What a figurine *says*, for the searchable text layer under it.

The canonical English letters, not the reader's language, and no letter for a pawn --
a pawn move carries none in algebraic notation. This is the table that turns a vector
figurine back into `Nf6` for `page.get_text()`, for a search, for copy and paste and for
a screen reader; the LaTeX side reaches the same six letters through
:func:`caissa.typeset.latex.retag_figurine_text`."""


@dataclass(frozen=True)
class FigurineMetrics:
    """Measured placement of one family's pieces at one text size.

    All values are in *em of the surrounding text*, so multiplying by the text's point
    size gives points. Keeping them unitless is what lets one measurement serve 9, 10,
    11 and 12 pt without re-measuring.
    """

    family: str
    scale: float
    """Multiply the text size by this to get the figurine's font size."""

    baseline_shift: float
    """Move the glyph *down* by this many em to seat its foot on the baseline.
    Negative values lift it."""

    advance: float
    """Width the figurine occupies, including its trailing air."""

    cap_height: float
    """Cap height of the text font, in em, that the figurine was fitted to."""

    per_piece_shift: Mapping[str, float] = field(default_factory=dict)
    """Extra per-piece correction where a family draws one piece off the common foot.
    Usually empty; a knight that overhangs its box is the typical reason."""

    per_piece_advance: Mapping[str, float] = field(default_factory=dict)
    """Set width of each piece, in em of the text size.

    ``advance`` is the *widest* piece and was used for every one of them, while
    :func:`figurine_svg` draws each at its own width. A line of six moves therefore
    measured up to 3.1 mm wider than it drew, and a justified line of chess notation
    stopped 5 % short of the measure with the slack invisible at the right margin."""

    per_piece_outset: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    """``(roman, bold)`` outset for each piece, in em of the text size.

    Solved per glyph so that every piece gains the same *ink*; see
    :data:`FIGURINE_INK_GAIN_BOLD`."""

    def size_for(self, text_size: float) -> float:
        return text_size * self.scale

    def shift_for(self, piece: str, text_size: float) -> float:
        return text_size * (self.baseline_shift + self.per_piece_shift.get(piece.upper(), 0.0))

    def advance_for(self, piece: str, text_size: float) -> float:
        """Set width of one piece. Falls back to the widest piece for a family measured
        before this table existed."""
        return text_size * self.per_piece_advance.get(piece.upper(), self.advance)

    def outset_for(self, piece: str, face: str) -> float:
        """Outset for ``piece`` in ``face``, in em of the text size."""
        pair = self.per_piece_outset.get(piece.upper())
        if pair is None:
            return weight_for(face)
        return pair[1] if face in ("bold", "bolditalic") else pair[0]


# Cap height of the running text, as a fraction of its em. Measured from the text font
# when one is supplied; this is the fallback and matches the serif faces chess books use
# (Times, Minion, Georgia all sit within a couple of percent of it).
DEFAULT_TEXT_CAP_HEIGHT = 0.70

# A figurine set exactly to the cap height reads a shade small, because a piece is a
# rounded, open shape and a capital is a dense one. Publishers set figurines slightly
# taller than caps; 1.06 is the ratio that matches printed New in Chess and Quality
# Chess pages when measured off the page.
FIGURINE_OPTICAL_BOOST = 1.06

# Air after the piece before the destination square. Zero would let the knight's muzzle
# touch the 'f'; a full space would break the token in two.
FIGURINE_TRAILING_SPACE = 0.055

# --------------------------------------------------------------------------- #
# Weight
# --------------------------------------------------------------------------- #
# A legacy chess font's white piece is an *outline* drawing: a thin ring of ink around a
# white body, designed to be read at board-square size. Dropped into a 8.6 pt line it
# carries about half the ink of the letters beside it, and next to a bold move heading it
# faints outright. Measured by the cycle-1 critic, ink density of the figurine over the
# mean of its two neighbouring glyphs:
#
#     reference (Quality Chess, roman)   0.94
#     ours (roman)                       0.56
#     ours (bold heading)                0.43
#
# The cure a type designer uses is a heavier cut. There is no heavier cut of these fonts,
# so the outline is *stroked* in its own colour before it is filled, which thickens the
# ring symmetrically -- exactly what a bolder weight of the same drawing would do -- and
# leaves the silhouette, the advance and the baseline untouched. The stroke is given in
# em of the surrounding text, so one number serves every point size.
#
# These two values were solved for, not chosen: `tools/measure_typography.py figurine`
# rasterises a real set line at 200 DPI and reports the same ratio the critic measured.
FIGURINE_WEIGHT_ROMAN = 0.022
"""Measured ratio with this value: 0.96 roman (reference 0.94, cycle 1 0.56)."""

FIGURINE_WEIGHT_BOLD = 0.032
"""Bold stroke weight, in em of the text. Solved against **two** measurements, not one.

Cycle 2 set this to 0.048 and reported the ink ratio alone: 0.99, the best number in the
report. The critic then measured what it cost. A stroke straddles the contour, so it
shrinks the counters by half its width on each side, and at 0.048 the slit in the Merida
bishop's mitre is filled solid at 8.6 pt -- the drawing lost its interior silhouette
while the metric improved. Bolding a glyph by stroking is legitimate; bolding it until it
becomes a blob is not.

Both numbers now hold, measured by `tools/measure_typography.py figurine` and
`... counters` at 2400 DPI on the same 8.6 pt line:

    ink ratio, bold context   0.86  (target >= 0.85; reference Quality Chess 0.94)
    counter area / roman      B 0.73   N 0.92   K 0.85   R 0.75   P 0.93   Q 0.56

The queen is the one glyph still under the 0.70 the critic proposed: its counters are
hairlines between the crown's balls, and at 8.6 pt no stroke that reads as bold leaves
them at 0.70. It is reported rather than rounded."""

FIGURINE_INK_GAIN_ROMAN = 0.030
FIGURINE_INK_GAIN_BOLD = 0.060
"""How much ink the inline cut adds to a piece, as a fraction of the glyph's own box.

**This is the glyph table.** Cycle 5's inline figurine was bolded by one stroke width for
all six pieces, and a stroke of one width does not add one amount of ink: it adds ink in
proportion to the glyph's *perimeter*, and the Merida queen has twice the perimeter of
the king in two thirds of the area. At 0.032 em the queen gained 0.248 of ink over the
same glyph in the diagram and the knight gained 0.172 -- and since the queen starts
denser (0.336 against 0.207), the bold run showed a queen at 0.60 beside knights at 0.31
to 0.40. The critic read that, correctly, as two different figurine sets in one line.

The cut is specified here as the ink it adds, not as the width of the stroke that adds
it, and :func:`measure_family` solves each piece's own outset from its own outline. Every
piece then gains the same ink, and each stays inside the +-0.08 band of the same glyph
drawn in the diagram, which is the criterion the cycle-5 critique set. Measured at 8.6 pt
and 1200 DPI, ink fraction of the glyph's box, inline bold against diagram:

    K 0.236 -> 0.293   Q 0.336 -> 0.396   R 0.327 -> 0.386
    B 0.208 -> 0.267   N 0.207 -> 0.266   P 0.182 -> 0.241

The price is declared in `docs/quality/F7_REPORT_C6.md`: bolding a board font's white
piece *outward only* cannot make it as dense as the bold letters beside it, and the
cycle-1 ratio of 0.85 in a bold context was bought by letting the stroke close the
counters -- the queen's fell to 0.56 of its roman area. Counters are now at 1.00."""

FIGURINE_COUNTER_FLOOR = 0.70
"""Counter area a bold figurine must keep, as a fraction of the same glyph in roman.

Held for five of the six Merida pieces at :data:`FIGURINE_WEIGHT_BOLD`; see the note
there for the queen."""

FIGURINE_WEIGHTS: Mapping[str, float] = {
    "roman": FIGURINE_WEIGHT_ROMAN,
    "italic": FIGURINE_WEIGHT_ROMAN,
    "bold": FIGURINE_WEIGHT_BOLD,
    "bolditalic": FIGURINE_WEIGHT_BOLD,
}


def weight_for(face: str) -> float:
    """Stroke weight, in em of the text, for a figurine set in ``face``.

    A figurine that does not answer the surrounding weight is the defect the charter
    calls "icons of different origins mixed (weight, style, grid)": cycle 1 measured
    20.3 % ink in a bold context and 19.3 % in a roman one -- the same glyph at the same
    weight, in a line that had changed weight around it.
    """
    return FIGURINE_WEIGHTS.get(face, FIGURINE_WEIGHT_ROMAN)


def measure_family(
    font: LoadedFont,
    *,
    text_cap_height: float = DEFAULT_TEXT_CAP_HEIGHT,
    optical_boost: float = FIGURINE_OPTICAL_BOOST,
) -> FigurineMetrics:
    """Measure how this family's pieces must be placed to sit in a line of text.

    The reference is the **tallest piece the family actually draws**, measured here
    rather than assumed. An earlier version used the king, on the reasoning that it is
    the tallest piece in every Staunton-derived design -- which is simply not true of
    the fonts on this machine. Measured over the eighteen verified families
    (``tests/unit/typeset/test_figurine.py::test_no_piece_overshoots_the_fitted_height``):

    ====================  =====================================
    Chess Leipzig         rook stands 6.7 % above the king
    Chess Cases           bishop 5.5 %
    Chess Marroquin       queen 4.6 %
    Chess Alpha           bishop 2.7 %
    Chess Mediaeval       pawn 2.7 %
    Unicode / DejaVu      queen 2.4 %
    Chess Alfonso-X       bishop 2.1 %
    ====================  =====================================

    Fitting the king therefore let those pieces stand up to 6.7 % proud of the cap
    height, which is visible as a knight or rook that looms over the line it sits in.
    Fitting the tallest piece makes the guarantee true by construction. Each piece is
    then checked for a foot off the common baseline and given its own correction.
    """
    upem = font.units_per_em

    def height_of(outline: Outline) -> float:
        if outline.is_empty():
            return 0.0
        _, low, _, high = outline.bbox()
        return high - low

    reference = Outline(contours=(), advance=0.0, units_per_em=upem)
    tallest = 0.0
    for candidate in PIECE_LETTERS + "P":
        outline = font.piece_outline(candidate)
        measured = height_of(outline)
        if measured > tallest:
            tallest, reference = measured, outline
    if reference.is_empty():
        return FigurineMetrics(
            family=font.spec.family,
            scale=1.0,
            baseline_shift=0.0,
            advance=1.0,
            cap_height=text_cap_height,
        )

    _, y0, _, y1 = reference.bbox()
    glyph_height = (y1 - y0) / upem
    if glyph_height <= 0:
        glyph_height = 1.0

    # Fit the piece's *drawn height* to the text's cap height (times the optical boost),
    # not the em to the em. This is the whole difference between a figurine that belongs
    # to the line and one that looms over it.
    target = text_cap_height * optical_boost
    scale = target / glyph_height

    # After scaling, the glyph's foot sits at y0*scale above the font's own baseline.
    # Shifting down by exactly that puts the foot on the text baseline.
    shift = (y0 / upem) * scale

    widest = 0.0
    per_piece: dict[str, float] = {}
    advances: dict[str, float] = {}
    outsets: dict[str, tuple[float, float]] = {}
    for piece in "KQRBNP":
        outline = font.piece_outline(piece)
        if outline.is_empty():
            continue
        px0, py0, px1, py1 = outline.bbox()
        width = (px1 - px0) / upem * scale
        widest = max(widest, width)
        advances[piece] = width + FIGURINE_TRAILING_SPACE
        foot = (py0 / upem) * scale
        # A piece whose foot differs from the reference by more than a quarter point at
        # 10 pt (0.0025 em) gets its own correction; below that the difference is
        # invisible and a correction would only add noise to the output.
        delta = foot - shift
        if abs(delta) > 0.0025:
            per_piece[piece] = delta
        outsets[piece] = (
            _outset_for_gain(outline, scale / upem, FIGURINE_INK_GAIN_ROMAN),
            _outset_for_gain(outline, scale / upem, FIGURINE_INK_GAIN_BOLD),
        )

    return FigurineMetrics(
        family=font.spec.family,
        scale=scale,
        baseline_shift=shift,
        advance=widest + FIGURINE_TRAILING_SPACE,
        cap_height=text_cap_height,
        per_piece_shift=per_piece,
        per_piece_advance=advances,
        per_piece_outset=outsets,
    )


def _outset_for_gain(outline: Outline, unit: float, gain: float) -> float:
    """Outset, in em of the text, that adds ``gain`` of ink to this glyph's box.

    Growing a shape outward by ``w/2`` is a Minkowski sum with a disc of that radius, so
    the inked area grows by ``(w/2)*perimeter + pi*(w/2)^2`` and the box grows by ``w``
    on each side. That is one equation in ``w`` and it is solved here by bisection --
    once per family, at metrics time, never in the drawing loop.

    Checked against the raster: solving for 0.060 and measuring the drawn glyph at
    1200 DPI gives 0.053 to 0.061 on the six Merida pieces, and the model's own base
    density reproduces the measured one to 0.003 on K, Q and R. It is an estimate of a
    rasterised quantity and the test that guards it measures the raster, not the model.
    """
    outer = outline.outer_contours()
    if not outer:
        return 0.0
    inner = tuple(c for c in outline.contours if not any(c is o for o in outer))
    area = sum(c.area() for c in outer) - sum(c.area() for c in inner)
    perimeter = sum(c.perimeter() for c in outer)
    x0, y0, x1, y1 = outline.bbox()
    box_w, box_h = (x1 - x0) * unit, (y1 - y0) * unit
    area *= unit * unit
    perimeter *= unit
    if box_w <= 0 or box_h <= 0 or perimeter <= 0:
        return 0.0
    base = area / (box_w * box_h)

    def ink(w: float) -> float:
        grown = area + (w / 2.0) * perimeter + math.pi * (w / 2.0) ** 2
        return grown / ((box_w + w) * (box_h + w))

    low, high = 0.0, 0.20
    for _ in range(40):
        mid = (low + high) / 2.0
        if ink(mid) - base < gain:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


# --------------------------------------------------------------------------- #
# SAN
# --------------------------------------------------------------------------- #
_SAN_RE = re.compile(
    r"^(?P<piece>[KQRBN])?"
    r"(?P<disambig>[a-h]?[1-8]?)"
    r"(?P<capture>x?)"
    r"(?P<target>[a-h][1-8])"
    r"(?P<promo>=[QRBN])?"
    r"(?P<suffix>[+#]?[!?]{0,2})$"
)
_CASTLE_RE = re.compile(r"^(?P<castle>O-O-O|O-O|0-0-0|0-0)(?P<suffix>[+#]?[!?]{0,2})$")


@dataclass(frozen=True)
class SanMove:
    piece: str | None
    disambiguation: str
    capture: bool
    target: str
    promotion: str | None
    suffix: str
    castle: str | None = None

    @property
    def is_castle(self) -> bool:
        return self.castle is not None


def parse_san(san: str) -> SanMove | None:
    """Split a SAN move into its parts. Returns None when it is not a move."""
    text = san.strip()
    castle = _CASTLE_RE.match(text)
    if castle:
        normal = castle.group("castle").replace("0", "O")
        return SanMove(
            piece=None,
            disambiguation="",
            capture=False,
            target="",
            promotion=None,
            suffix=castle.group("suffix"),
            castle=normal,
        )
    match = _SAN_RE.match(text)
    if not match:
        return None
    return SanMove(
        piece=match.group("piece"),
        disambiguation=match.group("disambig"),
        capture=bool(match.group("capture")),
        target=match.group("target"),
        promotion=(match.group("promo") or "").lstrip("=") or None,
        suffix=match.group("suffix"),
    )


def translate_san(san: str, language: str) -> str:
    """Rewrite an English SAN move's piece letters into ``language``.

    ``Nf3`` becomes ``Cf3`` in Portuguese and ``Sf3`` in German, from the same input --
    the reason SPEC §5.5 keeps a move as an object rather than as text.
    """
    try:
        return to_language(san, language)
    except NotationError:
        pass
    # The canonical parser refused the token (an evaluation glued to the move, a
    # language it has no table for); set the letters from the same table by hand.
    move = parse_san(san)
    if move is None:
        return san
    if move.is_castle:
        return f"{move.castle}{move.suffix}"
    out = language_letter(move.piece, language) if move.piece else ""
    out += move.disambiguation
    if move.capture:
        out += "x"
    out += move.target
    if move.promotion:
        out += "=" + language_letter(move.promotion, language)
    return out + move.suffix


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FigurineRun:
    """A piece of a move ready to be set: either text or a piece glyph."""

    kind: Literal["text", "piece"]
    content: str
    """The characters to set, or the FEN letter of the piece."""


def san_to_figurine_runs(
    san: str,
    *,
    colour: str = "w",
    fallback_language: str = "en",
    have_glyph: Iterable[str] | None = None,
) -> list[FigurineRun]:
    """Split a SAN move into runs, with the piece letter turned into a glyph run.

    ``colour`` picks which piece glyph is used. Chess books traditionally set *every*
    figurine from the white (outline) set regardless of who is moving, because the
    figurine names the piece, not its owner -- pass ``colour="b"`` only for the solid
    set some publishers prefer on coated stock.

    ``have_glyph`` lets the caller declare which pieces the chosen font can actually
    draw; anything missing falls back to the language letter rather than to a blank,
    which is the failure a reader cannot recover from.
    """
    move = parse_san(san)
    if move is None:
        return [FigurineRun("text", san)]
    if move.is_castle:
        return [FigurineRun("text", f"{move.castle}{move.suffix}")]

    runs: list[FigurineRun] = []
    available = set(have_glyph) if have_glyph is not None else None

    def piece_run(letter: str) -> None:
        fen_letter = letter.upper() if colour == "w" else letter.lower()
        if available is not None and fen_letter not in available:
            runs.append(FigurineRun("text", language_letter(letter, fallback_language)))
        else:
            runs.append(FigurineRun("piece", fen_letter))

    if move.piece:
        piece_run(move.piece)
    tail = move.disambiguation + ("x" if move.capture else "") + move.target
    if tail:
        runs.append(FigurineRun("text", tail))
    if move.promotion:
        runs.append(FigurineRun("text", "="))
        piece_run(move.promotion)
    if move.suffix:
        runs.append(FigurineRun("text", move.suffix))
    return runs


# --------------------------------------------------------------------------- #
# SVG output
# --------------------------------------------------------------------------- #
def figurine_svg(
    piece: str,
    *,
    font: LoadedFont,
    metrics: FigurineMetrics,
    text_size: float,
    x: float,
    baseline_y: float,
    colour: str = "#000000",
    body_colour: str | None = None,
    weight: float = 0.0,
    counter_colour: str | None = None,
) -> tuple[str, float]:
    """Emit one figurine as SVG paths seated on ``baseline_y``. Returns (svg, advance).

    ``body_colour`` fills the silhouette first, so a white piece keeps its light interior
    when it sits over a tinted background, exactly as on the board.

    ``weight`` is the bold cut, in em of the text, and ``counter_colour`` is the paper it
    is cut against. Given both, the glyph grows **outward only** -- see the comment on the
    three layers below, and :data:`FIGURINE_INK_GAIN_BOLD` for why the amount is specified
    as ink rather than as a stroke width. Without ``counter_colour`` the older single-path
    stroke is used, which also thickens the ring inward; it is kept for callers that draw
    on something other than flat paper, and it is not what the book pages use.
    """
    outline = font.piece_outline(piece)
    if outline.is_empty():
        return "", 0.0
    size = metrics.size_for(text_size)
    scale = size / font.units_per_em
    # `to_svg_path` flips y, so a point at font height ``h`` lands at ``dy - h*scale``.
    # The foot sits at ``y0``, so putting it on the baseline needs
    # ``dy = baseline_y + y0*scale``, and ``y0*scale`` is exactly what ``shift_for``
    # returns. The sign was inverted here, which lifted every inline piece off the line
    # by twice the shift -- 1.33 pt of a 9 pt line for the Merida king, about 0.15 em.
    # It reads as a figurine floating above its own text, which is the defect the critic
    # charter lists as "figurino desalinhado da linha de base".
    dy = baseline_y + metrics.shift_for(piece, text_size)

    px0, _, px1, _ = outline.bbox()
    # The outset grows the drawing by w/2 on every side, so it belongs in both the
    # placement and the set width. Leaving it out of the width is how a justified line
    # of six moves measured wider than it drew.
    grow = max(0.0, text_size * weight)
    glyph_w = (px1 - px0) * scale + grow
    # Set the glyph from its own left edge rather than its origin: legacy chess glyphs
    # carry a full square of side bearing, and honouring it would open a gap the width
    # of a board square between the piece and the file letter.
    dx = x + grow / 2.0 - px0 * scale

    outer = outline.outer_contours()
    inner = tuple(c for c in outline.contours if not any(c is o for o in outer))

    parts: list[str] = []
    if body_colour:
        body = outline.to_svg_path(scale=scale, dx=dx, dy=dy, contours=outer)
        parts.append(f'<path d="{body}" fill="{body_colour}"/>')
    if weight <= 0.0 or not inner or not counter_colour:
        # No weight to add, or nothing to protect: one path, counters as holes.
        full = outline.to_svg_path(scale=scale, dx=dx, dy=dy)
        if weight > 0.0:
            stroke = format_number(text_size * weight)
            parts.append(
                f'<path d="{full}" fill="{colour}" fill-rule="nonzero" '
                f'stroke="{colour}" stroke-width="{stroke}" stroke-linejoin="round"/>'
            )
        else:
            parts.append(f'<path d="{full}" fill="{colour}" fill-rule="nonzero"/>')
        return "".join(parts), glyph_w + text_size * FIGURINE_TRAILING_SPACE

    # Bold **outward only**. A stroke straddles the contour, so stroking the whole glyph
    # grows the ring by w overall and takes w/2 off every counter from each side. On a
    # piece whose counters are hairlines -- the gaps between the balls of the Merida
    # queen's crown, the slit in the king's mitre -- w = 0.032 em at 8.6 pt closes them,
    # and the glyph reads as a *filled* piece standing beside hollow knights in the same
    # bold run. The critic of cycle 5 measured it as a mixed figurine set: knights at
    # 0.31-0.40 ink, queens at 0.60, all six from the same white set.
    #
    # A punchcutter grows a bold face outward from the silhouette and re-cuts the
    # counters; that is what these three layers do:
    #   1. the outer silhouette, filled and stroked -- grown by w/2 all round;
    #   2. the counters, punched back at their ORIGINAL size in the paper colour;
    #   3. anything nested inside a counter (none in a Staunton set, but a two-level
    #      glyph would otherwise lose its island) drawn back in ink.
    stroke = format_number(text_size * weight)
    silhouette = outline.to_svg_path(scale=scale, dx=dx, dy=dy, contours=outer)
    parts.append(
        f'<path d="{silhouette}" fill="{colour}" fill-rule="nonzero" '
        f'stroke="{colour}" stroke-width="{stroke}" stroke-linejoin="round"/>'
    )
    holes = outline.to_svg_path(scale=scale, dx=dx, dy=dy, contours=inner)
    parts.append(f'<path d="{holes}" fill="{counter_colour}" fill-rule="nonzero"/>')
    islands = _nested_in(inner, outline.contours)
    if islands:
        island_path = outline.to_svg_path(scale=scale, dx=dx, dy=dy, contours=islands)
        parts.append(f'<path d="{island_path}" fill="{colour}" fill-rule="nonzero"/>')
    return "".join(parts), glyph_w + text_size * FIGURINE_TRAILING_SPACE


def _nested_in(holes, contours):
    """Contours that sit strictly inside one of ``holes`` -- an island in a counter."""
    boxes = [c.bbox() for c in holes]
    out = []
    for contour in contours:
        if any(contour is h for h in holes):
            continue
        x0, y0, x1, y1 = contour.bbox()
        for hx0, hy0, hx1, hy1 in boxes:
            if hx0 <= x0 and hy0 <= y0 and hx1 >= x1 and hy1 >= y1:
                out.append(contour)
                break
    return tuple(out)


def measure_for(family: str, **kwargs) -> FigurineMetrics:
    """Convenience: open a family and measure it."""
    return measure_family(load_font(family), **kwargs)
