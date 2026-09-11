"""Write the canonical board SVG as a Windows Enhanced Metafile (EMF).

Origem: caissa/typeset/svgpdf.py — mesma gramatica de SVG, alvo EMF em vez de PDF.

Why EMF and not a PNG
--------------------
SPEC 8.2 asks for "diagramas como EMF vetorial (nao PNG) com fallback PNG de alta
resolucao". A DOCX that carries a raster diagram is a DOCX whose diagrams break the
moment the author resizes the frame or the printer asks for 2400 dpi -- and Word will
happily resize it. EMF is the only vector format Word embeds natively without a
round trip through an external converter, so this module produces the real thing:
GDI path records, not a bitmap wrapped in a metafile.

The SVG this consumes is not arbitrary SVG. ``board_svg`` emits exactly ``rect``,
``path`` (with ``M``/``L``/``C``/``Z`` only), ``line``, ``circle``, ``text`` and ``g``
with ``transform``/``opacity``. That grammar is already parsed by ``typeset.svgpdf``
for the PDF path, so the parsing helpers are imported from there rather than written
twice: one grammar, one parser, two back ends.

Non-obvious decisions
---------------------
*Logical unit = 0.01 mm.* EMF states physical size in ``rclFrame``, whose unit is
0.01 mm. Choosing the same unit for the drawing grid makes ``rclBounds`` and
``rclFrame`` numerically identical, which removes the single most common way an EMF
comes out stretched in Word: a bounds/frame ratio that disagrees with the reference
device resolution. ``szlDevice``/``szlMillimeters`` are then declared at the matching
100 units per mm so every ratio in the header agrees with every other.

*Filled rectangles are widened by one unit.* GDI's ``Rectangle`` excludes the right
and bottom edges. Without the extra unit each of the 64 squares would end 0.01 mm
short of its neighbour and the board would show a faint grid of page-coloured seams.
Stroked rectangles keep their exact geometry, because there the edge is the drawing.

*``EMR_EXTCREATEPEN`` everywhere, never ``EMR_CREATEPEN``.* SVG's default line cap is
butt and its default join is miter; a GDI *geometric* pen defaults to round for both.
Only the extended pen can say ``PS_ENDCAP_FLAT | PS_JOIN_MITER``, and the difference
is plainly visible on the grid rules and arrow shafts.

*Opacity is blended against white.* EMF has no alpha channel. Rather than silently
dropping it or silently blending it, every blended element is counted and reported in
``EmfImage.notes`` so the caller can raise a DegradationWarning.

*Text keeps its font, not its outlines.* The only text in a board diagram is the
coordinate labels, and ``EMR_SETTEXTALIGN`` lets GDI do the centring with the real
font metrics. The ``Dx`` array an ``EMR_EXTTEXTOUTW`` record must carry is estimated
from ``_ADVANCE_EM``; see that table for what the estimate costs.
"""

from __future__ import annotations

import math
import struct
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from caissa.typeset.svgpdf import _colour, _f, _subpaths, _tag, _transform, parse_svg

__all__ = [
    "EMU_PER_MM",
    "UNITS_PER_MM",
    "EmfError",
    "EmfImage",
    "svg_to_emf",
    "svg_to_png",
]

EMU_PER_MM = 36000
"""English Metric Units per millimetre. OOXML measures drawings in these."""

UNITS_PER_MM = 100
"""EMF logical units per millimetre. One unit is 0.01 mm -- the unit of ``rclFrame``."""

# --------------------------------------------------------------------------- #
# EMF record types (MS-EMF 2.1.1)
# --------------------------------------------------------------------------- #
_EMR_HEADER = 1
_EMR_POLYBEZIERTO = 5
_EMR_POLYLINETO = 6
_EMR_SETWINDOWEXTEX = 9
_EMR_SETWINDOWORGEX = 10
_EMR_SETVIEWPORTEXTEX = 11
_EMR_SETVIEWPORTORGEX = 12
_EMR_EOF = 14
_EMR_SETMAPMODE = 17
_EMR_SETBKMODE = 18
_EMR_SETPOLYFILLMODE = 19
_EMR_SETTEXTALIGN = 22
_EMR_SETTEXTCOLOR = 24
_EMR_MOVETOEX = 27
_EMR_SELECTOBJECT = 37
_EMR_CREATEBRUSHINDIRECT = 39
_EMR_DELETEOBJECT = 40
_EMR_ELLIPSE = 42
_EMR_RECTANGLE = 43
_EMR_LINETO = 54
_EMR_BEGINPATH = 59
_EMR_ENDPATH = 60
_EMR_CLOSEFIGURE = 61
_EMR_FILLPATH = 62
_EMR_STROKEANDFILLPATH = 63
_EMR_STROKEPATH = 64
_EMR_EXTCREATEFONTINDIRECTW = 82
_EMR_EXTTEXTOUTW = 84
_EMR_POLYBEZIERTO16 = 88
_EMR_POLYLINETO16 = 89
_EMR_EXTCREATEPEN = 95

# --- GDI enumerations ------------------------------------------------------ #
_MM_ANISOTROPIC = 8
_ALTERNATE = 1
_WINDING = 2
_TRANSPARENT = 1
_GM_COMPATIBLE = 1
_BS_SOLID = 0
_BS_NULL = 1

_PS_SOLID = 0x00000000
_PS_GEOMETRIC = 0x00010000
_PS_ENDCAP_ROUND = 0x00000000
_PS_ENDCAP_SQUARE = 0x00000100
_PS_ENDCAP_FLAT = 0x00000200
_PS_JOIN_ROUND = 0x00000000
_PS_JOIN_BEVEL = 0x00001000
_PS_JOIN_MITER = 0x00002000

_TA_LEFT = 0
_TA_RIGHT = 2
_TA_CENTER = 6
_TA_BASELINE = 24

# Stock objects are addressed with the high bit set and cost no handle slot.
_STOCK_NULL_BRUSH = 0x80000005
_STOCK_NULL_PEN = 0x80000008
_STOCK_SYSTEM_FONT = 0x8000000D

_SIGNATURE = 0x464D4520  # ' EMF' little-endian
_VERSION = 0x00010000
_HEADER_FIXED = 108  # core 88 + extension 1 (12) + extension 2 (8)
_DESCRIPTION = "Caissa Studio\x00Diagrama de xadrez\x00\x00"

# Reference device: 420 x 297 mm at exactly 100 units per mm, so that every ratio
# in the header (bounds/frame, device/millimetres) reports the same resolution.
_DEVICE_MM = (420, 297)
_DEVICE_UNITS = (_DEVICE_MM[0] * UNITS_PER_MM, _DEVICE_MM[1] * UNITS_PER_MM)

_MAX_POINTS = 4092
"""Points per poly record. A multiple of 3 so a bezier run never splits mid-curve."""

_INT16 = range(-32768, 32768)

_ADVANCE_EM: dict[str, float] = {
    "0": 0.530, "1": 0.465, "2": 0.530, "3": 0.526, "4": 0.533,
    "5": 0.514, "6": 0.533, "7": 0.501, "8": 0.548, "9": 0.530,
    "a": 0.474, "b": 0.530, "c": 0.449, "d": 0.537, "e": 0.464,
    "f": 0.329, "g": 0.505, "h": 0.541,
}
"""Advance width in em for the characters a board diagram actually sets.

An ``EMR_EXTTEXTOUTW`` record must carry a ``Dx`` array -- readers dereference the
offset without checking it for zero -- and this module has no way to measure a system
font. The values are the mean of Georgia and Times New Roman, the first two families
in ``DiagramStyle.coordinate_font``, so whichever one resolves the error is at most
0.05 em. Since the labels are single characters, that error only moves a ``TA_CENTER``
origin by half of it: under 0.15 mm on a 90 mm board. Anything outside the table falls
back to ``_ADVANCE_DEFAULT``.
"""

_ADVANCE_DEFAULT = 0.5


class EmfError(RuntimeError):
    """Raised when an SVG cannot be turned into an EMF, or the PNG fallback is absent."""


@dataclass(frozen=True)
class EmfImage:
    """A finished EMF: the bytes plus the intrinsic size Word needs.

    Attributes:
        data: The complete metafile, starting with ``EMR_HEADER``.
        width_mm: Intrinsic width in millimetres, as recorded in ``rclFrame``.
        height_mm: Intrinsic height in millimetres, as recorded in ``rclFrame``.
        notes: Brazilian-Portuguese descriptions of every fidelity loss the
            conversion had to accept. Empty when the EMF is a faithful copy.
            Callers turn these into DegradationWarnings.
    """

    data: bytes
    width_mm: float
    height_mm: float
    notes: tuple[str, ...] = ()

    @property
    def width_emu(self) -> int:
        """Width in English Metric Units, ready for an OOXML ``<wp:extent>``.

        Returns:
            The width rounded to the nearest EMU.
        """
        return round(self.width_mm * EMU_PER_MM)

    @property
    def height_emu(self) -> int:
        """Height in English Metric Units, ready for an OOXML ``<wp:extent>``.

        Returns:
            The height rounded to the nearest EMU.
        """
        return round(self.height_mm * EMU_PER_MM)


# --------------------------------------------------------------------------- #
# Colour
# --------------------------------------------------------------------------- #
def _rgb(value: str | None) -> tuple[int, int, int] | None:
    """Parse ``#rrggbb`` into 0..255 channels, reusing the PDF back end's parser.

    Args:
        value: An SVG paint value, or ``None``/``"none"`` for no paint.

    Returns:
        The channels as ``(r, g, b)``, or ``None`` when nothing should be painted.
    """
    parsed = _colour(value)
    if parsed is None:
        return None
    return (round(parsed[0] * 255), round(parsed[1] * 255), round(parsed[2] * 255))


def _blend_white(rgb: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """Flatten a translucent colour onto a white page.

    Args:
        rgb: The source colour.
        alpha: Coverage in 0..1. Values at or above 1 return ``rgb`` unchanged.

    Returns:
        The opaque colour that reproduces ``rgb`` at ``alpha`` over white.
    """
    if alpha >= 1.0:
        return rgb
    a = min(1.0, max(0.0, alpha))
    return (
        round(rgb[0] * a + 255 * (1.0 - a)),
        round(rgb[1] * a + 255 * (1.0 - a)),
        round(rgb[2] * a + 255 * (1.0 - a)),
    )


def _colorref(rgb: tuple[int, int, int]) -> int:
    """Pack a colour into a GDI ``COLORREF``.

    Args:
        rgb: The colour as ``(r, g, b)``.

    Returns:
        ``0x00BBGGRR`` -- red in the low byte. Reversing this is what swaps red
        and blue in every metafile that gets it wrong.
    """
    return (rgb[0] & 0xFF) | ((rgb[1] & 0xFF) << 8) | ((rgb[2] & 0xFF) << 16)


# --------------------------------------------------------------------------- #
# Record assembly
# --------------------------------------------------------------------------- #
def _record(itype: int, payload: bytes = b"") -> bytes:
    """Wrap a payload in the common ``iType``/``nSize`` record header.

    Args:
        itype: The ``EMR_*`` record type.
        payload: Everything after ``nSize``.

    Returns:
        The record, zero-padded so that ``nSize`` is a multiple of four and equals
        the byte count exactly.
    """
    size = 8 + len(payload)
    pad = -size % 4
    return struct.pack("<II", itype, size + pad) + payload + b"\x00" * pad


def _rectl(left: int, top: int, right: int, bottom: int) -> bytes:
    return struct.pack("<4i", left, top, right, bottom)


@dataclass
class _Bounds:
    """Running ink extent in logical units, used for every record's ``rclBounds``."""

    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    empty: bool = True

    def add(self, x: float, y: float) -> None:
        if self.empty:
            self.left = self.right = x
            self.top = self.bottom = y
            self.empty = False
            return
        self.left = min(self.left, x)
        self.right = max(self.right, x)
        self.top = min(self.top, y)
        self.bottom = max(self.bottom, y)

    def grow(self, amount: float) -> None:
        if not self.empty:
            self.left -= amount
            self.top -= amount
            self.right += amount
            self.bottom += amount

    def to_rectl(self) -> bytes:
        """Serialise as a ``RECTL``. An untouched extent yields GDI's empty rectangle."""
        if self.empty:
            return _rectl(0, 0, -1, -1)
        return _rectl(
            math.floor(self.left),
            math.floor(self.top),
            math.ceil(self.right),
            math.ceil(self.bottom),
        )


@dataclass(frozen=True)
class _PenSpec:
    """Everything that distinguishes one geometric pen from another."""

    colour: int
    width: int
    cap: int
    join: int


@dataclass(frozen=True)
class _FontSpec:
    """Everything that distinguishes one ``LOGFONTW`` from another."""

    face: str
    height: int
    weight: int
    italic: bool


@dataclass
class _Emf:
    """Accumulates EMF records and the object handle table.

    The header is emitted first as a placeholder and back-patched by :meth:`finish`
    once ``nBytes``, ``nRecords`` and ``nHandles`` are known.
    """

    width: int
    height: int
    records: list[bytes] = field(default_factory=list)
    creations: list[bytes] = field(default_factory=list)
    _brushes: dict[int, int] = field(default_factory=dict)
    _pens: dict[_PenSpec, int] = field(default_factory=dict)
    _fonts: dict[_FontSpec, int] = field(default_factory=dict)
    _next_handle: int = 1
    _brush: int | None = None
    _pen: int | None = None
    _font: int | None = None
    _fill_mode: int = _WINDING
    _text_colour: int | None = None
    _text_align: int | None = None
    bounds: _Bounds = field(default_factory=_Bounds)

    # -- record plumbing ---------------------------------------------------- #
    def add(self, itype: int, payload: bytes = b"") -> None:
        self.records.append(_record(itype, payload))

    def _handle(self) -> int:
        index = self._next_handle
        self._next_handle += 1
        return index

    # -- graphics state ----------------------------------------------------- #
    def brush(self, rgb: tuple[int, int, int] | None) -> int:
        """Return the handle of a solid brush, creating it at most once per colour."""
        if rgb is None:
            return _STOCK_NULL_BRUSH
        colour = _colorref(rgb)
        cached = self._brushes.get(colour)
        if cached is None:
            cached = self._handle()
            self._brushes[colour] = cached
            payload = struct.pack("<IIII", cached, _BS_SOLID, colour, 0)
            self.creations.append(_record(_EMR_CREATEBRUSHINDIRECT, payload))
        return cached

    def pen(self, spec: _PenSpec | None) -> int:
        """Return the handle of a geometric pen, creating it at most once per spec."""
        if spec is None:
            return _STOCK_NULL_PEN
        cached = self._pens.get(spec)
        if cached is None:
            cached = self._handle()
            self._pens[spec] = cached
            style = _PS_GEOMETRIC | _PS_SOLID | spec.cap | spec.join
            payload = struct.pack(
                "<IIIIIIIIIII",
                cached, 0, 0, 0, 0,          # ihPen, offBmi, cbBmi, offBits, cbBits
                style, spec.width,           # PenStyle, Width
                _BS_SOLID, spec.colour, 0,   # BrushStyle, ColorRef, BrushHatch
                0,                           # NumStyleEntries
            )
            self.creations.append(_record(_EMR_EXTCREATEPEN, payload))
        return cached

    def font(self, spec: _FontSpec) -> int:
        """Return the handle of a ``LOGFONTW``, creating it at most once per spec."""
        cached = self._fonts.get(spec)
        if cached is None:
            cached = self._handle()
            self._fonts[spec] = cached
            self.creations.append(
                _record(_EMR_EXTCREATEFONTINDIRECTW, struct.pack("<I", cached) + _logfont(spec))
            )
        return cached

    def select_brush(self, rgb: tuple[int, int, int] | None) -> None:
        handle = self.brush(rgb)
        if handle != self._brush:
            self._brush = handle
            self.add(_EMR_SELECTOBJECT, struct.pack("<I", handle))

    def select_pen(self, spec: _PenSpec | None) -> None:
        handle = self.pen(spec)
        if handle != self._pen:
            self._pen = handle
            self.add(_EMR_SELECTOBJECT, struct.pack("<I", handle))

    def select_font(self, spec: _FontSpec) -> None:
        handle = self.font(spec)
        if handle != self._font:
            self._font = handle
            self.add(_EMR_SELECTOBJECT, struct.pack("<I", handle))

    def set_fill_mode(self, mode: int) -> None:
        if mode != self._fill_mode:
            self._fill_mode = mode
            self.add(_EMR_SETPOLYFILLMODE, struct.pack("<I", mode))

    def set_text_colour(self, colour: int) -> None:
        if colour != self._text_colour:
            self._text_colour = colour
            self.add(_EMR_SETTEXTCOLOR, struct.pack("<I", colour))

    def set_text_align(self, align: int) -> None:
        if align != self._text_align:
            self._text_align = align
            self.add(_EMR_SETTEXTALIGN, struct.pack("<I", align))

    # -- geometry ----------------------------------------------------------- #
    def _points(self, itype16: int, itype32: int, points: Sequence[tuple[int, int]]) -> None:
        """Emit a ``*TO`` poly record, 16-bit when the coordinates fit and 32-bit else."""
        for start in range(0, len(points), _MAX_POINTS):
            chunk = points[start : start + _MAX_POINTS]
            box = _Bounds()
            for x, y in chunk:
                box.add(x, y)
            small = all(x in _INT16 and y in _INT16 for x, y in chunk)
            head = box.to_rectl() + struct.pack("<I", len(chunk))
            if small:
                body = b"".join(struct.pack("<hh", x, y) for x, y in chunk)
                self.add(itype16, head + body)
            else:
                body = b"".join(struct.pack("<ii", x, y) for x, y in chunk)
                self.add(itype32, head + body)

    def rectangle(self, box: tuple[int, int, int, int], *, stroked: bool) -> None:
        """Draw a rectangle with the selected pen and brush.

        Args:
            box: ``(left, top, right, bottom)`` in logical units.
            stroked: ``True`` when a pen is selected. Fill-only rectangles are
                widened by one unit so that adjacent board squares abut exactly;
                see the module docstring.
        """
        left, top, right, bottom = box
        if not stroked:
            right += 1
            bottom += 1
        self.bounds.add(left, top)
        self.bounds.add(right, bottom)
        self.add(_EMR_RECTANGLE, _rectl(left, top, right, bottom))

    def ellipse(self, box: tuple[int, int, int, int]) -> None:
        """Draw an ellipse inscribed in ``box`` with the selected pen and brush."""
        left, top, right, bottom = box
        self.bounds.add(left, top)
        self.bounds.add(right + 1, bottom + 1)
        self.add(_EMR_ELLIPSE, _rectl(left, top, right + 1, bottom + 1))

    def line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Draw a straight segment with the selected pen."""
        self.bounds.add(x1, y1)
        self.bounds.add(x2, y2)
        self.add(_EMR_MOVETOEX, struct.pack("<ii", x1, y1))
        self.add(_EMR_LINETO, struct.pack("<ii", x2, y2))

    def path(
        self,
        subpaths: Sequence[Sequence[tuple]],
        *,
        filled: bool,
        stroked: bool,
        even_odd: bool,
    ) -> None:
        """Bracket a set of subpaths in a GDI path and fill and/or stroke it.

        Args:
            subpaths: Segment lists already mapped to logical units, in the shape
                :func:`caissa.typeset.svgpdf._subpaths` returns.
            filled: Emit a fill using the selected brush.
            stroked: Emit a stroke using the selected pen.
            even_odd: Use ``ALTERNATE`` rather than ``WINDING`` filling. The piece
                glyphs rely on this: with the wrong rule every counter fills in and
                the pieces become silhouettes.
        """
        drawable = [s for s in subpaths if s and s[0][0] == "M"]
        if not drawable or not (filled or stroked):
            return
        self.set_fill_mode(_ALTERNATE if even_odd else _WINDING)
        box = _Bounds()
        self.add(_EMR_BEGINPATH)
        for sub in drawable:
            self.add(_EMR_MOVETOEX, struct.pack("<ii", sub[0][1], sub[0][2]))
            box.add(sub[0][1], sub[0][2])
            run: list[tuple[int, int]] = []
            kind = ""
            closed = False
            for seg in sub[1:]:
                if seg[0] == "Z":
                    closed = True
                    continue
                if seg[0] != kind and run:
                    self._flush(kind, run)
                    run = []
                kind = seg[0]
                pairs = [(seg[i], seg[i + 1]) for i in range(1, len(seg) - 1, 2)]
                run.extend(pairs)
                for x, y in pairs:
                    box.add(x, y)
            if run:
                self._flush(kind, run)
            if closed:
                self.add(_EMR_CLOSEFIGURE)
        self.add(_EMR_ENDPATH)
        if filled and stroked:
            op = _EMR_STROKEANDFILLPATH
        elif filled:
            op = _EMR_FILLPATH
        else:
            op = _EMR_STROKEPATH
        self.add(op, box.to_rectl())
        if not box.empty:
            self.bounds.add(box.left, box.top)
            self.bounds.add(box.right, box.bottom)

    def _flush(self, kind: str, run: list[tuple[int, int]]) -> None:
        if kind == "C":
            self._points(_EMR_POLYBEZIERTO16, _EMR_POLYBEZIERTO, run)
        else:
            self._points(_EMR_POLYLINETO16, _EMR_POLYLINETO, run)

    def text(self, x: int, y: int, content: str, *, size: int, advances: list[int]) -> None:
        """Emit an ``EMR_EXTTEXTOUTW`` at a baseline reference point.

        Args:
            x: Baseline x in logical units; the alignment set by
                :meth:`set_text_align` decides what it means.
            y: Baseline y in logical units.
            content: The string. Encoded UTF-16LE, so accented labels survive.
            size: Em size in logical units, used only for the bounding boxes.
            advances: Per-character advance in logical units for the ``Dx`` array.
        """
        chars = len(content)
        if chars == 0:
            return
        data = content.encode("utf-16-le")
        pad = -len(data) % 4
        off_string = 76
        off_dx = off_string + len(data) + pad
        width = sum(advances)
        box = _Bounds()
        box.add(x - width, y - size)
        box.add(x + width, y + size)
        rect = box.to_rectl()
        payload = (
            rect
            + struct.pack("<Iff", _GM_COMPATIBLE, 1.0, 1.0)
            + struct.pack("<iiIII", x, y, chars, off_string, 0)
            + rect
            + struct.pack("<I", off_dx)
            + data
            + b"\x00" * pad
            + b"".join(struct.pack("<i", a) for a in advances)
        )
        self.add(_EMR_EXTTEXTOUTW, payload)
        self.bounds.add(box.left, box.top)
        self.bounds.add(box.right, box.bottom)

    # -- output ------------------------------------------------------------- #
    def finish(self) -> bytes:
        """Close the metafile and back-patch the header.

        Returns:
            The complete EMF, header first and ``EMR_EOF`` last.
        """
        # Nothing may be deleted while it is selected, so hand the DC the stock
        # objects back first; stock handles carry the high bit and cost no slot.
        owned = sorted([*self._brushes.values(), *self._pens.values(), *self._fonts.values()])
        tail = [
            _record(_EMR_SELECTOBJECT, struct.pack("<I", handle))
            for handle in (_STOCK_NULL_BRUSH, _STOCK_NULL_PEN, _STOCK_SYSTEM_FONT)
        ] + [_record(_EMR_DELETEOBJECT, struct.pack("<I", handle)) for handle in owned]
        eof = _record(_EMR_EOF, struct.pack("<III", 0, 16, 20))

        body = b"".join(self.creations) + b"".join(self.records) + b"".join(tail) + eof
        n_records = 1 + len(self.creations) + len(self.records) + len(tail) + 1
        blob = bytearray(self._header_placeholder() + body)
        struct.pack_into("<I", blob, 48, len(blob))
        struct.pack_into("<I", blob, 52, n_records)
        struct.pack_into("<H", blob, 56, self._next_handle)
        return bytes(blob)

    def _header_placeholder(self) -> bytes:
        description = _DESCRIPTION.encode("utf-16-le")
        pad = -(_HEADER_FIXED + len(description)) % 4
        size = _HEADER_FIXED + len(description) + pad
        frame = _rectl(0, 0, self.width - 1, self.height - 1)
        return (
            struct.pack("<II", _EMR_HEADER, size)
            + frame                                    # rclBounds, device units
            + frame                                    # rclFrame, 0.01 mm units
            + struct.pack("<II", _SIGNATURE, _VERSION)
            + struct.pack("<II", 0, 0)                 # nBytes, nRecords: patched
            + struct.pack("<HH", 0, 0)                 # nHandles: patched, sReserved
            + struct.pack("<III", len(_DESCRIPTION), _HEADER_FIXED, 0)
            + struct.pack("<ii", *_DEVICE_UNITS)       # szlDevice
            + struct.pack("<ii", *_DEVICE_MM)          # szlMillimeters
            + struct.pack("<III", 0, 0, 0)             # cbPixelFormat, offPixelFormat, bOpenGL
            + struct.pack("<II", _DEVICE_MM[0] * 1000, _DEVICE_MM[1] * 1000)
            + description
            + b"\x00" * pad
        )


def _logfont(spec: _FontSpec) -> bytes:
    """Serialise a 92-byte ``LOGFONTW``.

    Args:
        spec: The face, em height (negative, GDI's "character height"), weight
            and slant.

    Returns:
        The packed structure, face name padded to 32 UTF-16 code units.
    """
    face = spec.face[:31].encode("utf-16-le")
    face += b"\x00" * (64 - len(face))
    return (
        struct.pack("<5i", spec.height, 0, 0, 0, spec.weight)
        + struct.pack("<8B", 1 if spec.italic else 0, 0, 0, 1, 4, 0, 0, 0x10)
        + face
    )


# --------------------------------------------------------------------------- #
# SVG traversal
# --------------------------------------------------------------------------- #
_State = tuple[float, float, float, float]
"""Composed drawing state carried down the tree: ``(tx, ty, scale, opacity)``."""


def _walk(element, state: _State) -> Iterator[tuple[ET.Element, _State]]:  # noqa: ANN001
    """Yield ``(element, (tx, ty, scale, opacity))`` depth-first.

    The transform composition is the one ``svgpdf._walk`` performs; the fourth
    component is added here because EMF has to resolve inherited group opacity into
    a flat colour at write time, whereas the PDF back end can hand it to the page.
    """
    tx, ty, ts, op = state
    dx, dy, ds = _transform(element.get("transform"))
    inherited = op * _f(element.get("opacity"), 1.0) if _tag(element) in ("svg", "g") else op
    here = (tx + dx * ts, ty + dy * ts, ts * ds, inherited)
    yield element, here
    for child in element:
        yield from _walk(child, here)


def _cap_join(element) -> tuple[int, int]:  # noqa: ANN001
    """Map ``stroke-linecap``/``stroke-linejoin`` to ``PS_*`` bits, SVG defaults first."""
    cap = {
        "round": _PS_ENDCAP_ROUND,
        "square": _PS_ENDCAP_SQUARE,
        "butt": _PS_ENDCAP_FLAT,
    }.get(element.get("stroke-linecap") or "butt", _PS_ENDCAP_FLAT)
    join = {
        "round": _PS_JOIN_ROUND,
        "bevel": _PS_JOIN_BEVEL,
        "miter": _PS_JOIN_MITER,
    }.get(element.get("stroke-linejoin") or "miter", _PS_JOIN_MITER)
    return cap, join


def _face_name(family: str | None) -> str:
    """Pick a concrete Windows face from a CSS ``font-family`` list.

    Args:
        family: The raw attribute, e.g. ``"Georgia, 'Times New Roman', serif"``.

    Returns:
        The first named family, or a concrete stand-in when the list only offers a
        CSS generic. ``LOGFONTW`` has one face name and no fallback chain, so the
        choice has to be made here rather than by the reader.
    """
    generics = {
        "serif": "Times New Roman",
        "sans-serif": "Arial",
        "monospace": "Courier New",
        "cursive": "Comic Sans MS",
        "fantasy": "Impact",
    }
    for part in (family or "").split(","):
        name = part.strip().strip("'\"").strip()
        if not name:
            continue
        return generics.get(name.lower(), name)
    return "Times New Roman"


def _advances(content: str, size: int) -> list[int]:
    """Estimate per-character advances in logical units. See :data:`_ADVANCE_EM`."""
    return [round(_ADVANCE_EM.get(ch, _ADVANCE_DEFAULT) * size) for ch in content]


def _weight(element) -> int:  # noqa: ANN001
    raw = element.get("font-weight") or ""
    if raw.isdigit():
        return max(100, min(900, int(raw)))
    return 700 if "bold" in raw else 400


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #
def svg_to_emf(svg: str, *, width_mm: float | None = None) -> EmfImage:
    """Convert a board SVG to an EMF.

    Args:
        svg: The document ``caissa.typeset.board_svg.render_svg`` produced. Only
            that grammar is understood: ``rect``, ``path`` restricted to
            ``M``/``L``/``C``/``Z``, ``line``, ``circle``, ``text`` and ``g``
            carrying ``transform``/``opacity``.
        width_mm: Overrides the SVG's intrinsic width, scaling height, strokes and
            type by the same factor so the aspect ratio and the optical weight of
            every rule are preserved. ``None`` keeps the intrinsic size.

    Returns:
        An :class:`EmfImage` whose ``notes`` list every fidelity loss the format
        forced -- above all, transparency flattened onto white.

    Raises:
        EmfError: The document is not parseable SVG, or its ``viewBox`` gives a
            width or height of zero, which no metafile can express.
    """
    try:
        frag = parse_svg(svg)
    except ET.ParseError as exc:
        raise EmfError(f"SVG invalido: nao foi possivel interpretar o documento ({exc}).") from exc
    if frag.width_mm <= 0 or frag.height_mm <= 0:
        raise EmfError(
            f"SVG invalido: dimensoes {frag.width_mm} x {frag.height_mm} mm; "
            "o viewBox precisa de largura e altura positivas."
        )

    scale = (width_mm / frag.width_mm) if width_mm else 1.0
    if scale <= 0:
        raise EmfError(f"Largura invalida: {width_mm} mm. Use um valor positivo.")
    out_w = frag.width_mm * scale
    out_h = frag.height_mm * scale
    emf = _Emf(
        width=max(1, round(out_w * UNITS_PER_MM)),
        height=max(1, round(out_h * UNITS_PER_MM)),
    )
    emf.add(_EMR_SETMAPMODE, struct.pack("<I", _MM_ANISOTROPIC))
    emf.add(_EMR_SETWINDOWEXTEX, struct.pack("<ii", emf.width, emf.height))
    emf.add(_EMR_SETWINDOWORGEX, struct.pack("<ii", 0, 0))
    emf.add(_EMR_SETVIEWPORTEXTEX, struct.pack("<ii", emf.width, emf.height))
    emf.add(_EMR_SETVIEWPORTORGEX, struct.pack("<ii", 0, 0))
    emf.add(_EMR_SETPOLYFILLMODE, struct.pack("<I", _WINDING))
    emf.add(_EMR_SETBKMODE, struct.pack("<I", _TRANSPARENT))

    tally = _Tally()
    for element, (tx, ty, ts, inherited) in _walk(frag.root, (0.0, 0.0, 1.0, 1.0)):
        name = _tag(element)
        if name in ("svg", "g"):
            continue
        # mm -> logical units, with the group transform already composed in.
        k = scale * UNITS_PER_MM
        unit = k * ts

        def px(v: float, _tx: float = tx, _ts: float = ts, _k: float = k) -> int:
            return round((_tx + v * _ts) * _k)

        def py(v: float, _ty: float = ty, _ts: float = ts, _k: float = k) -> int:
            return round((_ty + v * _ts) * _k)

        paint = _paint(element, inherited, unit)
        tally.blended += int(paint.blended)
        if name == "text":
            tally.estimated += int(_draw_text(emf, element, px, py, unit, paint))
        elif name in ("rect", "circle", "line", "path"):
            _draw_shape(emf, name, element, px, py, paint)
        else:
            tally.skipped[name] = tally.skipped.get(name, 0) + 1

    return EmfImage(
        data=emf.finish(), width_mm=out_w, height_mm=out_h, notes=tally.notes()
    )


@dataclass
class _Tally:
    """What the conversion had to approximate, so the caller can be told."""

    blended: int = 0
    estimated: int = 0
    skipped: dict[str, int] = field(default_factory=dict)

    def notes(self) -> tuple[str, ...]:
        """Render the tally as Brazilian-Portuguese degradation notes."""
        notes: list[str] = []
        if self.blended:
            notes.append(
                f"EMF nao tem canal alfa; a transparencia de {self.blended} elemento(s) "
                "foi mesclada com o branco."
            )
        if self.estimated:
            notes.append(
                f"Larguras de glifo estimadas em {self.estimated} trecho(s) de texto com "
                "mais de um caractere; o EMF nao carrega as metricas da fonte."
            )
        if self.skipped:
            listed = ", ".join(f"{tag} ({n})" for tag, n in sorted(self.skipped.items()))
            notes.append(
                f"Elemento(s) SVG fora do vocabulario do renderizador foram ignorados: {listed}."
            )
        return tuple(notes)


@dataclass(frozen=True)
class _Paint:
    """One element's paint, with every alpha already resolved against white."""

    fill: tuple[int, int, int] | None
    pen: _PenSpec | None
    blended: bool


def _paint(element, inherited: float, unit: float) -> _Paint:  # noqa: ANN001
    """Resolve fill, stroke and opacity into the opaque colours EMF can carry.

    Args:
        element: The SVG element.
        inherited: Group opacity accumulated by :func:`_walk`.
        unit: Logical units per millimetre at this point in the tree, for the pen width.

    Returns:
        The paint, with ``blended`` set when any channel had to be flattened.
    """
    alpha = inherited * _f(element.get("opacity"), 1.0)
    fill_alpha = alpha * _f(element.get("fill-opacity"), 1.0)
    stroke_alpha = alpha * _f(element.get("stroke-opacity"), 1.0)
    fill = _rgb(element.get("fill"))
    stroke = _rgb(element.get("stroke"))
    blended = (fill is not None and fill_alpha < 1.0) or (
        stroke is not None and stroke_alpha < 1.0
    )
    pen: _PenSpec | None = None
    if stroke is not None:
        cap, join = _cap_join(element)
        pen = _PenSpec(
            colour=_colorref(_blend_white(stroke, stroke_alpha)),
            width=max(1, round(_f(element.get("stroke-width"), 0.0) * unit)),
            cap=cap,
            join=join,
        )
    return _Paint(
        fill=_blend_white(fill, fill_alpha) if fill is not None else None,
        pen=pen,
        blended=blended,
    )


def _draw_shape(emf: _Emf, name: str, element, px, py, paint: _Paint) -> None:  # noqa: ANN001
    """Emit the records for one ``rect``, ``circle``, ``line`` or ``path``.

    Args:
        emf: The metafile under construction.
        name: The SVG tag, already known to be one of the four.
        element: The element itself.
        px: Maps an SVG x to a logical unit.
        py: Maps an SVG y to a logical unit.
        paint: The resolved paint from :func:`_paint`.
    """
    if paint.fill is None and paint.pen is None:
        return
    if name == "rect":
        x, y = _f(element.get("x")), _f(element.get("y"))
        w, h = _f(element.get("width")), _f(element.get("height"))
        if w <= 0 or h <= 0:
            return
        emf.select_brush(paint.fill)
        emf.select_pen(paint.pen)
        emf.rectangle((px(x), py(y), px(x + w), py(y + h)), stroked=paint.pen is not None)
    elif name == "circle":
        cx, cy, r = _f(element.get("cx")), _f(element.get("cy")), _f(element.get("r"))
        if r <= 0:
            return
        emf.select_brush(paint.fill)
        emf.select_pen(paint.pen)
        emf.ellipse((px(cx - r), py(cy - r), px(cx + r), py(cy + r)))
    elif name == "line":
        if paint.pen is None:
            return
        emf.select_pen(paint.pen)
        emf.line(
            px(_f(element.get("x1"))), py(_f(element.get("y1"))),
            px(_f(element.get("x2"))), py(_f(element.get("y2"))),
        )
    else:
        mapped = [
            [_map_segment(seg, px, py) for seg in sub]
            for sub in _subpaths(element.get("d") or "")
        ]
        emf.select_brush(paint.fill)
        emf.select_pen(paint.pen)
        emf.path(
            mapped,
            filled=paint.fill is not None,
            stroked=paint.pen is not None,
            even_odd=element.get("fill-rule") == "evenodd",
        )


def _draw_text(emf: _Emf, element, px, py, unit: float, paint: _Paint) -> bool:  # noqa: ANN001
    """Emit the font, colour, alignment and ``EMR_EXTTEXTOUTW`` for one ``text``.

    Args:
        emf: The metafile under construction.
        element: The ``text`` element; its ``text-anchor`` becomes a ``TA_*`` mode so
            GDI centres with the real font metrics rather than an estimate.
        px: Maps an SVG x to a logical unit.
        py: Maps an SVG y to a logical unit.
        unit: Logical units per millimetre, for the em size.
        paint: The resolved paint; ``fill`` is the ink colour, black by default.

    Returns:
        ``True`` when the run is longer than one character, so the caller can record
        that the ``Dx`` estimate in :data:`_ADVANCE_EM` actually mattered.
    """
    content = (element.text or "").strip()
    if not content:
        return False
    size = max(1, round(_f(element.get("font-size"), 3.0) * unit))
    emf.select_font(
        _FontSpec(
            face=_face_name(element.get("font-family")),
            height=-size,
            weight=_weight(element),
            italic=(element.get("font-style") or "") == "italic",
        )
    )
    emf.set_text_colour(_colorref(paint.fill if paint.fill is not None else (0, 0, 0)))
    emf.set_text_align(
        {
            "start": _TA_LEFT | _TA_BASELINE,
            "middle": _TA_CENTER | _TA_BASELINE,
            "end": _TA_RIGHT | _TA_BASELINE,
        }.get(element.get("text-anchor") or "start", _TA_LEFT | _TA_BASELINE)
    )
    emf.text(
        px(_f(element.get("x"))),
        py(_f(element.get("y"))),
        content,
        size=size,
        advances=_advances(content, size),
    )
    return len(content) > 1


def _map_segment(seg: tuple, px, py) -> tuple:  # noqa: ANN001
    """Map one parsed path segment from millimetres to logical units."""
    if seg[0] == "Z":
        return seg
    out: list = [seg[0]]
    for i in range(1, len(seg) - 1, 2):
        out.append(px(seg[i]))
        out.append(py(seg[i + 1]))
    return tuple(out)


def svg_to_png(svg: str, *, dpi: int = 600) -> bytes:
    """Rasterise the same SVG as a high-resolution fallback.

    Used when a consumer refuses EMF. 600 dpi is the floor at which a 20 mm diagram
    still holds its hairlines on an offset proof.

    Pillow cannot rasterise SVG at all -- it has no path or font machinery for it --
    so this delegates to the project's existing PyMuPDF route, which flattens the
    very same vector drawing the EMF carries. That keeps the fallback and the
    primary output visually identical instead of merely similar.

    Args:
        svg: The board SVG.
        dpi: Output resolution in dots per inch.

    Returns:
        The PNG bytes.

    Raises:
        EmfError: PyMuPDF is not installed, so no rasteriser is available.
    """
    try:
        from caissa.typeset.svgpdf import svg_to_png as _raster

        return _raster(svg, dpi=dpi)
    except ImportError as exc:
        raise EmfError(
            "Fallback PNG indisponivel: o rasterizador (PyMuPDF) nao esta instalado. "
            'Instale o grupo opcional com: pip install -e ".[vision]".'
        ) from exc
