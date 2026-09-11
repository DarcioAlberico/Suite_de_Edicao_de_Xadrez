"""A minimal, self-contained PDF 1.7 writer: objects, fonts, vectors, tags.

Why this module exists
----------------------
Caissa needs a PDF back end that (a) embeds arbitrary TrueType faces -- including the
symbolic chess diagram fonts, whose ``cmap`` is ``(3, 0)`` and whose glyphs sit on ASCII
letters -- (b) produces *selectable, searchable* text, and (c) emits a tagged structure
tree so the book is accessible. ReportLab can do (a) and (b) but its structure-tree
support is thin, and it drags in a large dependency for what is, at bottom, a byte
format. So the byte format is written here, by hand, with nothing but the standard
library and ``fontTools``.

The module knows **nothing** about the Caissa document IR. It takes points, bytes and
glyph indices. Layout lives in :mod:`caissa.export.pdf`; this file is the printer.

Non-obvious decisions
---------------------
**Identity-H, CID == original GID.** Subsetting normally renumbers glyphs, which would
mean the bytes written into a content stream could only be computed *after* the whole
document is known. Instead :class:`FontEmbedder` subsets with ``retain_gids=True``, so a
glyph keeps the index it had in the source face and :meth:`EmbeddedFont.encode` can run
while the content stream is being built. The cost is a ``loca`` table with holes; on
Georgia a 15-glyph subset still comes out at ~5% of the original file.

**Call order.** ``encode()`` is what records glyph usage, so every content stream must be
built *before* :meth:`FontEmbedder.finalise`. :class:`PdfPage.resources` is a plain
mutable dict precisely so a caller who added pages first can drop the font refs in
afterwards.

**Deferred object construction.** ``set_outline`` / ``set_struct_tree`` / ``set_metadata``
only store data. Every derived object (catalog, page tree, outline items, structure
elements, XMP packet) is built inside :meth:`PdfDocument.to_bytes` against a *copy* of
the object table, so ``to_bytes()`` is repeatable and never mutates the document.

**Classic xref table, not an xref stream.** Both are legal in 1.7. The table is
human-inspectable, which is what makes the test suite's hand-written parser -- and any
future forensic look at a broken export -- possible.

**Deterministic output.** The ``/ID`` is an MD5 of the body rather than a random nonce,
and the subset tag is an MD5 of the face name plus the retained glyph set. The same
input therefore produces byte-identical output, which is what makes golden-file tests
meaningful.

**Kerning.** :meth:`EmbeddedFont.kern` reads the legacy ``kern`` table when present and
otherwise falls back to GPOS ``PairPos`` lookups (formats 1 and 2, including type-9
extensions). Georgia ships no ``kern`` table at all, and a chess book set in Georgia
without kerning looks like a photocopy. Cross-checked against Times New Roman, where both
sources exist and agree.

Honesty about PDF/A
-------------------
``PdfMetadata.pdf_a`` emits PDF/A-2b identification in the XMP packet and an
``/OutputIntent``. Unless the caller supplies :attr:`PdfMetadata.icc_profile`, **no ICC
stream is embedded**, and a file without ``/DestOutputProfile`` is *not* conformant
PDF/A-2b. See :func:`pdfa_caveats` -- the caller is expected to surface those strings in
its export report rather than claim a conformance that was not achieved.

Known limitations
-----------------
* No encryption, no incremental update, no linearisation.
* Link annotations are not wired into the structure tree via ``/OBJR``; a ``Link``
  structure element can be emitted but the annotation itself carries no ``/StructParent``.
* Only ``FlateDecode``; no image XObject helpers (the caller supplies those streams).
"""

from __future__ import annotations

import hashlib
import io
import math
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fontTools import subset
from fontTools.ttLib import TTFont

__all__ = [
    "DEFAULT_LANGUAGE",
    "PDFA_CAVEATS",
    "STRUCT_TAGS",
    "SUPPORTED_VERSIONS",
    "ContentStream",
    "EmbeddedFont",
    "FontEmbedder",
    "LinkAnnotation",
    "OutlineEntry",
    "PdfDocument",
    "PdfMetadata",
    "PdfName",
    "PdfPage",
    "PdfRef",
    "PdfWriteError",
    "StructElement",
    "pdfa_caveats",
]

SUPPORTED_VERSIONS: tuple[str, ...] = ("1.4", "1.5", "1.6", "1.7")
"""PDF header versions this writer will admit to producing."""

DEFAULT_LANGUAGE = "pt-BR"
"""Catalog ``/Lang`` used when a structure tree is present and no language was given."""

STRUCT_TAGS: frozenset[str] = frozenset(
    {
        "Document",
        "Part",
        "Sect",
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
        "P",
        "L",
        "LI",
        "LBody",
        "Table",
        "TR",
        "TH",
        "TD",
        "Figure",
        "Caption",
        "Note",
        "Link",
        "Span",
        "Artifact",
    }
)
"""Structure tags accepted by :class:`StructElement`."""

# Every tag above is already a standard PDF 1.7 structure type except ``Artifact``,
# which is a marked-content category and not a structure type at all; mapping it to
# ``NonStruct`` is what keeps a conforming reader from rejecting the tree.
_ROLE_MAP: dict[str, str] = {tag: tag for tag in STRUCT_TAGS}
_ROLE_MAP["Artifact"] = "NonStruct"

PDFA_CAVEATS: tuple[str, ...] = (
    "PDF/A-2b: nenhum perfil ICC foi embutido em /DestOutputProfile. O OutputIntent "
    "declara apenas /OutputConditionIdentifier (sRGB). Sem o perfil o arquivo NAO e "
    "conformante com PDF/A-2b -- e uma estrutura PDF/A sem perfil de cor.",
    "PDF/A-2b: o arquivo nao foi validado contra veraPDF nem contra qualquer outro "
    "verificador. A conformidade declarada no XMP e uma intencao, nao uma verificacao.",
    "PDF/A-2b: transparencia (ExtGState /CA e /ca) e permitida pela norma, mas exige um "
    "espaco de mesclagem definido. Sem o perfil ICC acima isso nao pode ser garantido.",
    "PDF/A-2b: anotacoes de link nao recebem /StructParent, portanto nao ficam ligadas a "
    "arvore de estrutura por /OBJR.",
)
"""Portuguese caveats that apply to every ``pdf_a=True`` file produced without an ICC
profile. Exposed so the caller can report honestly instead of claiming conformance."""

_XMP_TOOLKIT = "Caissa Studio pdfwrite"
_DEFAULT_PRODUCER = "Caissa Studio pdfwrite (PDF 1.7)"

# Characters that may appear literally inside a PDF name object. Everything else is
# written as ``#xx``. Delimiters and whitespace are excluded on purpose.
_NAME_SAFE: frozenset[int] = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!\"$&'*+,-.:;=?@^_`|~"
)

_LITERAL_ESCAPES: dict[int, bytes] = {
    0x08: b"\\b",
    0x09: b"\\t",
    0x0A: b"\\n",
    0x0C: b"\\f",
    0x0D: b"\\r",
    0x28: b"\\(",
    0x29: b"\\)",
    0x5C: b"\\\\",
}

_ASCII_SPACE = 0x20
_ASCII_DEL = 0x7F
_HEX_PER_BFCHAR_BLOCK = 100
_SUBSET_TAG_LENGTH = 6
_GPOS_LOOKUP_PAIR = 2
_GPOS_LOOKUP_EXTENSION = 9
_GPOS_VALUEFORMAT_XADVANCE = 0x0004
_SYMBOL_CMAP_BASE = 0xF000
_SYMBOL_CMAP_TOP = 0xF0FF
_FSTYPE_MASK = 0x000F
_FSTYPE_RESTRICTED = 0x0002
_PANOSE_LATIN_TEXT = 2
_PANOSE_SERIF_MIN = 2
_PANOSE_SERIF_MAX = 10
_OS2_VERSION_WITH_CAPHEIGHT = 2
_MAX_TEXT_RENDER_MODE = 7

# /FontDescriptor Flags (PDF 1.7, table 123).
_FLAG_FIXED_PITCH = 1 << 0
_FLAG_SERIF = 1 << 1
_FLAG_SYMBOLIC = 1 << 2
_FLAG_NONSYMBOLIC = 1 << 5
_FLAG_ITALIC = 1 << 6


class PdfWriteError(RuntimeError):
    """Falha ao construir ou gravar o PDF."""


# --------------------------------------------------------------------------- #
# Primitive object types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PdfName:
    """A PDF name object such as ``/Type``.

    Wrapping names in a type (instead of using bare ``str``) is what lets the serialiser
    tell ``/Identity-H`` the name apart from ``(Identity-H)`` the string.

    Attributes:
        value: The name without its leading slash.
    """

    value: str

    def to_bytes(self) -> bytes:
        """Serialise the name, escaping anything a PDF name may not carry literally.

        Returns:
            The name as ``/Escaped`` bytes.

        Raises:
            PdfWriteError: If the name is empty.
        """
        if not self.value:
            raise PdfWriteError("Nome PDF vazio nao e valido.")
        out = bytearray(b"/")
        for byte in self.value.encode("utf-8"):
            if byte in _NAME_SAFE:
                out.append(byte)
            else:
                out += b"#%02X" % byte
        return bytes(out)


@dataclass(frozen=True, slots=True)
class PdfRef:
    """An indirect reference to an object, written ``n g R``.

    Attributes:
        number: The object number, 1-based.
        generation: The generation number; always 0 for a freshly written file.
    """

    number: int
    generation: int = 0

    def to_bytes(self) -> bytes:
        """Serialise the reference.

        Returns:
            Bytes of the form ``b"12 0 R"``.
        """
        return b"%d %d R" % (self.number, self.generation)


@dataclass(slots=True)
class _Stream:
    """An internal stream object: a dictionary plus raw (possibly compressed) data."""

    data: bytes
    extra: dict[str, Any]
    compress: bool


# --------------------------------------------------------------------------- #
# Serialisation primitives
# --------------------------------------------------------------------------- #


def _fmt_number(value: float) -> bytes:
    """Format a number the way PDF wants it: no exponent, no trailing noise.

    Args:
        value: The number to format.

    Returns:
        ASCII bytes for the number.

    Raises:
        PdfWriteError: If the value is NaN or infinite.
    """
    if isinstance(value, bool):  # bool is an int; catching it here avoids ``True`` -> 1
        raise PdfWriteError("Booleano usado onde um numero era esperado.")
    if isinstance(value, int):
        return b"%d" % value
    if math.isnan(value) or math.isinf(value):
        raise PdfWriteError(f"Numero nao representavel em PDF: {value!r}.")
    text = f"{value:.5f}".rstrip("0").rstrip(".")
    if text in {"", "-", "-0"}:
        text = "0"
    return text.encode("ascii")


def _encode_text_string(text: str) -> bytes:
    r"""Encode a Python string as a PDF text string.

    Pure ASCII becomes a literal string with ``\\``, ``(`` and ``)`` escaped; anything
    else becomes a UTF-16BE hex string with a BOM, which is the only encoding every
    conforming reader understands for non-Latin text.

    Args:
        text: The string to encode.

    Returns:
        The encoded string object including its delimiters.
    """
    if text.isascii():
        out = bytearray(b"(")
        for byte in text.encode("ascii"):
            escaped = _LITERAL_ESCAPES.get(byte)
            if escaped is not None:
                out += escaped
            elif byte < _ASCII_SPACE or byte == _ASCII_DEL:
                out += b"\\%03o" % byte
            else:
                out.append(byte)
        out += b")"
        return bytes(out)
    payload = ("﻿" + text).encode("utf-16-be").hex().upper()
    return b"<" + payload.encode("ascii") + b">"


def _format_pdf_date(moment: datetime) -> str:
    """Format a datetime as a PDF date string (``D:YYYYMMDDHHmmSS+HH'mm'``).

    A naive datetime is read as UTC; PDF/A requires an explicit offset, and silently
    omitting one is worse than stating the assumption.

    Args:
        moment: The instant to format.

    Returns:
        The date string without its surrounding parentheses.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    offset = moment.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    stamp = moment.strftime("%Y%m%d%H%M%S")
    return f"D:{stamp}{sign}{total_minutes // 60:02d}'{total_minutes % 60:02d}'"


def _format_xmp_date(moment: datetime) -> str:
    """Format a datetime as the ISO 8601 string XMP expects.

    Args:
        moment: The instant to format.

    Returns:
        An ISO 8601 timestamp with an explicit UTC offset.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.isoformat(timespec="seconds")


def _serialise(value: Any) -> bytes:  # noqa: PLR0911 -- one return per PDF type reads best
    """Serialise any supported Python value into PDF syntax.

    The mapping is: ``None`` -> ``null``; ``bool`` -> ``true``/``false``; ``int``/``float``
    -> a number; ``str`` -> a text string; ``bytes`` -> **inserted verbatim** (the escape
    hatch for pre-built syntax); ``datetime`` -> a date string; ``PdfName``/``PdfRef`` ->
    themselves; ``Mapping`` -> a dictionary whose ``str`` keys become names; ``list``/
    ``tuple`` -> an array.

    Args:
        value: The value to serialise.

    Returns:
        The PDF representation.

    Raises:
        PdfWriteError: If the value has no PDF representation, or a stream appears
            nested inside a container (streams may only be top-level objects).
    """
    if value is None:
        return b"null"
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, (PdfName, PdfRef)):
        return value.to_bytes()
    if isinstance(value, (int, float)):
        return _fmt_number(value)
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return _encode_text_string(value)
    if isinstance(value, datetime):
        return _encode_text_string(_format_pdf_date(value))
    if isinstance(value, _Stream):
        raise PdfWriteError("Um stream so pode ser um objeto de primeiro nivel.")
    if isinstance(value, Mapping):
        parts = [b"<<"]
        for key, item in value.items():
            name = key if isinstance(key, PdfName) else PdfName(str(key))
            parts.append(name.to_bytes() + b" " + _serialise(item))
        parts.append(b">>")
        return b" ".join(parts)
    if isinstance(value, (list, tuple)):
        return b"[" + b" ".join(_serialise(item) for item in value) + b"]"
    raise PdfWriteError(f"Valor sem representacao em PDF: {type(value).__name__}.")


class _ObjectTable:
    """Growable table of indirect objects, numbered from 1."""

    def __init__(self) -> None:
        self._payloads: list[Any] = []

    def copy(self) -> _ObjectTable:
        """Return a shallow copy, so derived objects never touch the original.

        Returns:
            A new table holding the same payloads.
        """
        clone = _ObjectTable()
        clone._payloads = list(self._payloads)
        return clone

    def reserve(self) -> PdfRef:
        """Allocate an object number whose payload is supplied later.

        Returns:
            A reference to the reserved slot.
        """
        self._payloads.append(None)
        return PdfRef(len(self._payloads))

    def assign(self, ref: PdfRef, payload: Any) -> None:
        """Fill a previously reserved slot.

        Args:
            ref: The reference returned by :meth:`reserve`.
            payload: The object payload.

        Raises:
            PdfWriteError: If the reference is out of range.
        """
        if not 1 <= ref.number <= len(self._payloads):
            raise PdfWriteError(f"Referencia fora da tabela de objetos: {ref.number}.")
        self._payloads[ref.number - 1] = payload

    def add(self, payload: Any) -> PdfRef:
        """Append a new object.

        Args:
            payload: The object payload.

        Returns:
            A reference to the new object.
        """
        self._payloads.append(payload)
        return PdfRef(len(self._payloads))

    def payloads(self) -> list[Any]:
        """Return the payloads in object-number order.

        Returns:
            The list of payloads; index ``i`` is object number ``i + 1``.
        """
        return self._payloads

    def __len__(self) -> int:
        return len(self._payloads)


# --------------------------------------------------------------------------- #
# Content streams
# --------------------------------------------------------------------------- #


class ContentStream:
    """Builds a PDF content stream with readable operator helpers.

    Every method appends one operator. The class tracks ``q``/``Q``, ``BT``/``ET`` and
    ``BDC``/``EMC`` nesting and refuses to underflow, because an unbalanced content
    stream is the single most common way to produce a PDF that opens as a blank page.
    """

    def __init__(self) -> None:
        self._parts: list[bytes] = []
        self._q_depth = 0
        self._mc_depth = 0
        self._in_text = False

    # -- plumbing ----------------------------------------------------------- #

    def _write(self, *tokens: bytes) -> None:
        self._parts.append(b" ".join(tokens))

    @staticmethod
    def _clamp(value: float) -> bytes:
        if math.isnan(value):
            raise PdfWriteError("Componente de cor invalido (NaN).")
        return _fmt_number(min(1.0, max(0.0, float(value))))

    # -- graphics state ----------------------------------------------------- #

    def save(self) -> None:
        """Push the graphics state (``q``)."""
        self._q_depth += 1
        self._write(b"q")

    def restore(self) -> None:
        """Pop the graphics state (``Q``).

        Raises:
            PdfWriteError: If there is no matching :meth:`save`.
        """
        if self._q_depth == 0:
            raise PdfWriteError("Q sem q correspondente no fluxo de conteudo.")
        self._q_depth -= 1
        self._write(b"Q")

    def transform(self, a: float, b: float, c: float, d: float, e: float, f: float) -> None:
        """Concatenate a matrix onto the CTM (``cm``).

        Args:
            a: Matrix element a.
            b: Matrix element b.
            c: Matrix element c.
            d: Matrix element d.
            e: Horizontal translation.
            f: Vertical translation.
        """
        self._write(*(_fmt_number(v) for v in (a, b, c, d, e, f)), b"cm")

    def set_line_width(self, width: float) -> None:
        """Set the stroke width in points (``w``).

        Args:
            width: The line width.
        """
        self._write(_fmt_number(width), b"w")

    def set_line_cap(self, style: int) -> None:
        """Set the line cap style (``J``).

        Args:
            style: 0 butt, 1 round, 2 projecting square.

        Raises:
            PdfWriteError: If the style is not 0, 1 or 2.
        """
        if style not in {0, 1, 2}:
            raise PdfWriteError(f"Estilo de ponta de linha invalido: {style}.")
        self._write(_fmt_number(style), b"J")

    def set_line_join(self, style: int) -> None:
        """Set the line join style (``j``).

        Args:
            style: 0 miter, 1 round, 2 bevel.

        Raises:
            PdfWriteError: If the style is not 0, 1 or 2.
        """
        if style not in {0, 1, 2}:
            raise PdfWriteError(f"Estilo de juncao de linha invalido: {style}.")
        self._write(_fmt_number(style), b"j")

    def set_miter_limit(self, limit: float) -> None:
        """Set the miter limit (``M``).

        Args:
            limit: The miter limit.
        """
        self._write(_fmt_number(limit), b"M")

    def set_dash(self, pattern: Sequence[float], phase: float = 0.0) -> None:
        """Set the dash pattern (``d``). An empty pattern restores a solid line.

        Args:
            pattern: Alternating on/off lengths in points.
            phase: Distance into the pattern at which to start.
        """
        array = b"[" + b" ".join(_fmt_number(v) for v in pattern) + b"]"
        self._write(array, _fmt_number(phase), b"d")

    def set_alpha(self, name: str) -> None:
        """Apply a named ``ExtGState`` resource (``gs``), typically for alpha.

        Args:
            name: The resource name as it appears under ``/ExtGState`` in the page
                resources, without the leading slash.
        """
        self._write(PdfName(name).to_bytes(), b"gs")

    # -- colour ------------------------------------------------------------- #

    def set_fill_gray(self, gray: float) -> None:
        """Set a DeviceGray fill colour (``g``).

        Args:
            gray: Luminance in 0..1.
        """
        self._write(self._clamp(gray), b"g")

    def set_stroke_gray(self, gray: float) -> None:
        """Set a DeviceGray stroke colour (``G``).

        Args:
            gray: Luminance in 0..1.
        """
        self._write(self._clamp(gray), b"G")

    def set_fill_rgb(self, r: float, g: float, b: float) -> None:
        """Set a DeviceRGB fill colour (``rg``).

        Args:
            r: Red in 0..1.
            g: Green in 0..1.
            b: Blue in 0..1.
        """
        self._write(self._clamp(r), self._clamp(g), self._clamp(b), b"rg")

    def set_stroke_rgb(self, r: float, g: float, b: float) -> None:
        """Set a DeviceRGB stroke colour (``RG``).

        Args:
            r: Red in 0..1.
            g: Green in 0..1.
            b: Blue in 0..1.
        """
        self._write(self._clamp(r), self._clamp(g), self._clamp(b), b"RG")

    def set_fill_cmyk(self, c: float, m: float, y: float, k: float) -> None:
        """Set a DeviceCMYK fill colour (``k``).

        Args:
            c: Cyan in 0..1.
            m: Magenta in 0..1.
            y: Yellow in 0..1.
            k: Black in 0..1.
        """
        self._write(self._clamp(c), self._clamp(m), self._clamp(y), self._clamp(k), b"k")

    def set_stroke_cmyk(self, c: float, m: float, y: float, k: float) -> None:
        """Set a DeviceCMYK stroke colour (``K``).

        Args:
            c: Cyan in 0..1.
            m: Magenta in 0..1.
            y: Yellow in 0..1.
            k: Black in 0..1.
        """
        self._write(self._clamp(c), self._clamp(m), self._clamp(y), self._clamp(k), b"K")

    def set_fill_colour_space(self, name: str) -> None:
        """Select a named fill colour space (``cs``).

        Args:
            name: The resource name under ``/ColorSpace``, without the leading slash.
        """
        self._write(PdfName(name).to_bytes(), b"cs")

    def set_stroke_colour_space(self, name: str) -> None:
        """Select a named stroke colour space (``CS``).

        Args:
            name: The resource name under ``/ColorSpace``, without the leading slash.
        """
        self._write(PdfName(name).to_bytes(), b"CS")

    # -- paths -------------------------------------------------------------- #

    def move_to(self, x: float, y: float) -> None:
        """Begin a new subpath (``m``).

        Args:
            x: Horizontal coordinate in points.
            y: Vertical coordinate in points.
        """
        self._write(_fmt_number(x), _fmt_number(y), b"m")

    def line_to(self, x: float, y: float) -> None:
        """Append a straight segment (``l``).

        Args:
            x: Horizontal coordinate in points.
            y: Vertical coordinate in points.
        """
        self._write(_fmt_number(x), _fmt_number(y), b"l")

    def curve_to(self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float) -> None:
        """Append a cubic Bezier segment (``c``).

        Args:
            x1: First control point, horizontal.
            y1: First control point, vertical.
            x2: Second control point, horizontal.
            y2: Second control point, vertical.
            x3: End point, horizontal.
            y3: End point, vertical.
        """
        self._write(*(_fmt_number(v) for v in (x1, y1, x2, y2, x3, y3)), b"c")

    def close_path(self) -> None:
        """Close the current subpath (``h``)."""
        self._write(b"h")

    def rect(self, x: float, y: float, width: float, height: float) -> None:
        """Append a closed rectangle subpath (``re``).

        Args:
            x: Left edge in points.
            y: Bottom edge in points.
            width: Width in points.
            height: Height in points.
        """
        self._write(*(_fmt_number(v) for v in (x, y, width, height)), b"re")

    def fill(self, *, even_odd: bool = False) -> None:
        """Fill the current path (``f`` or ``f*``).

        Args:
            even_odd: Use the even-odd rule instead of the nonzero winding rule.
        """
        self._write(b"f*" if even_odd else b"f")

    def stroke(self) -> None:
        """Stroke the current path (``S``)."""
        self._write(b"S")

    def close_and_stroke(self) -> None:
        """Close and stroke the current path (``s``)."""
        self._write(b"s")

    def fill_stroke(self, *, even_odd: bool = False) -> None:
        """Fill and then stroke the current path (``B`` or ``B*``).

        Args:
            even_odd: Use the even-odd rule instead of the nonzero winding rule.
        """
        self._write(b"B*" if even_odd else b"B")

    def clip(self, *, even_odd: bool = False) -> None:
        """Intersect the clipping path with the current path (``W``/``W*`` then ``n``).

        Args:
            even_odd: Use the even-odd rule instead of the nonzero winding rule.
        """
        self._write(b"W*" if even_odd else b"W")
        self._write(b"n")

    def end_path(self) -> None:
        """Discard the current path without painting it (``n``)."""
        self._write(b"n")

    def paint_xobject(self, name: str) -> None:
        """Paint a named XObject (``Do``).

        Args:
            name: The resource name under ``/XObject``, without the leading slash.
        """
        self._write(PdfName(name).to_bytes(), b"Do")

    # -- text --------------------------------------------------------------- #

    def begin_text(self) -> None:
        """Open a text object (``BT``).

        Raises:
            PdfWriteError: If a text object is already open (they do not nest).
        """
        if self._in_text:
            raise PdfWriteError("BT dentro de outro BT: objetos de texto nao aninham.")
        self._in_text = True
        self._write(b"BT")

    def end_text(self) -> None:
        """Close a text object (``ET``).

        Raises:
            PdfWriteError: If no text object is open.
        """
        if not self._in_text:
            raise PdfWriteError("ET sem BT correspondente.")
        self._in_text = False
        self._write(b"ET")

    def set_font(self, resource_name: str, size: float) -> None:
        """Select a font resource and size (``Tf``).

        Args:
            resource_name: The name under ``/Font`` in the page resources, e.g. ``"F1"``.
            size: Type size in points.
        """
        self._write(PdfName(resource_name).to_bytes(), _fmt_number(size), b"Tf")

    def set_char_spacing(self, spacing: float) -> None:
        """Set character spacing (``Tc``), applied after every glyph including the last.

        Args:
            spacing: Extra advance per glyph, in unscaled text units.
        """
        self._write(_fmt_number(spacing), b"Tc")

    def set_word_spacing(self, spacing: float) -> None:
        """Set word spacing (``Tw``).

        With Identity-H encoding this affects single-byte code 32 only, which never
        occurs, so the caller should space words with :meth:`show_adjusted` instead.

        Args:
            spacing: Extra advance per space character.
        """
        self._write(_fmt_number(spacing), b"Tw")

    def set_horizontal_scale(self, percent: float) -> None:
        """Set horizontal scaling (``Tz``).

        Args:
            percent: Scale as a percentage; 100 is normal.
        """
        self._write(_fmt_number(percent), b"Tz")

    def set_leading(self, leading: float) -> None:
        """Set the leading used by ``T*`` (``TL``).

        Args:
            leading: Baseline-to-baseline distance in points.
        """
        self._write(_fmt_number(leading), b"TL")

    def set_rise(self, rise: float) -> None:
        """Set the text rise, for super- and subscripts (``Ts``).

        Args:
            rise: Vertical displacement in unscaled text units.
        """
        self._write(_fmt_number(rise), b"Ts")

    def set_render_mode(self, mode: int) -> None:
        """Set the text rendering mode (``Tr``).

        Args:
            mode: 0 fill, 1 stroke, 2 fill+stroke, 3 invisible, 4..7 clipping variants.

        Raises:
            PdfWriteError: If the mode is outside 0..7.
        """
        if not 0 <= mode <= _MAX_TEXT_RENDER_MODE:
            raise PdfWriteError(f"Modo de renderizacao de texto invalido: {mode}.")
        self._write(_fmt_number(mode), b"Tr")

    def set_text_matrix(self, a: float, b: float, c: float, d: float, e: float, f: float) -> None:
        """Replace the text matrix (``Tm``).

        Args:
            a: Matrix element a.
            b: Matrix element b.
            c: Matrix element c.
            d: Matrix element d.
            e: Horizontal translation.
            f: Vertical translation.
        """
        self._write(*(_fmt_number(v) for v in (a, b, c, d, e, f)), b"Tm")

    def text_position(self, x: float, y: float) -> None:
        """Set the text matrix to a plain translation to ``(x, y)``.

        Args:
            x: Baseline origin, horizontal, in points.
            y: Baseline origin, vertical, in points.
        """
        self.set_text_matrix(1, 0, 0, 1, x, y)

    def next_line(self) -> None:
        """Move to the next line using the current leading (``T*``)."""
        self._write(b"T*")

    def show(self, raw: bytes) -> None:
        """Show an already-encoded string (``Tj``).

        The bytes come from :meth:`EmbeddedFont.encode` and are written as a hex string,
        which is the only form that is safe for arbitrary two-byte CID data.

        Args:
            raw: The encoded glyph bytes.
        """
        self._write(b"<" + raw.hex().upper().encode("ascii") + b">", b"Tj")

    def show_adjusted(self, items: Sequence[bytes | float]) -> None:
        """Show a run with inline advance adjustments (``TJ``).

        This is how kerning and micro-tracking are applied: positive numbers move the
        next glyph *left* by ``value/1000`` of the type size.

        Args:
            items: A sequence mixing encoded byte strings and numeric adjustments.
        """
        parts: list[bytes] = []
        for item in items:
            if isinstance(item, (bytes, bytearray)):
                parts.append(b"<" + bytes(item).hex().upper().encode("ascii") + b">")
            else:
                parts.append(_fmt_number(item))
        self._write(b"[" + b" ".join(parts) + b"]", b"TJ")

    # -- marked content ----------------------------------------------------- #

    def begin_marked_content(
        self,
        tag: str,
        mcid: int | None = None,
        *,
        lang: str | None = None,
        alt: str | None = None,
    ) -> None:
        """Open a marked-content sequence (``BMC`` or ``BDC``).

        Args:
            tag: The structure tag, e.g. ``"P"`` or ``"Artifact"``.
            mcid: The marked-content id that the structure tree will point at. When
                omitted and no other property is given, a bare ``BMC`` is emitted.
            lang: Optional ``/Lang`` property for this sequence.
            alt: Optional ``/Alt`` text for this sequence.
        """
        properties: dict[str, Any] = {}
        if mcid is not None:
            properties["MCID"] = mcid
        if lang is not None:
            properties["Lang"] = lang
        if alt is not None:
            properties["Alt"] = alt
        self._mc_depth += 1
        if properties:
            self._write(PdfName(tag).to_bytes(), _serialise(properties), b"BDC")
        else:
            self._write(PdfName(tag).to_bytes(), b"BMC")

    def end_marked_content(self) -> None:
        """Close a marked-content sequence (``EMC``).

        Raises:
            PdfWriteError: If no marked-content sequence is open.
        """
        if self._mc_depth == 0:
            raise PdfWriteError("EMC sem BMC/BDC correspondente.")
        self._mc_depth -= 1
        self._write(b"EMC")

    # -- output ------------------------------------------------------------- #

    def to_bytes(self, *, strict: bool = True) -> bytes:
        """Serialise the stream.

        Args:
            strict: When true (the default) an unbalanced stream is an error. Pass false
                only when building a fragment that will be concatenated with another.

        Returns:
            The content stream bytes.

        Raises:
            PdfWriteError: If ``strict`` and any of ``q``, ``BT`` or ``BDC`` is unclosed.
        """
        if strict:
            if self._q_depth:
                raise PdfWriteError(f"Fluxo de conteudo com {self._q_depth} 'q' sem 'Q'.")
            if self._mc_depth:
                raise PdfWriteError(f"Fluxo de conteudo com {self._mc_depth} 'BDC/BMC' sem 'EMC'.")
            if self._in_text:
                raise PdfWriteError("Fluxo de conteudo com 'BT' sem 'ET'.")
        return b"\n".join(self._parts)


# --------------------------------------------------------------------------- #
# Page-level value types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LinkAnnotation:
    """A clickable rectangle: either an internal jump or an external URI.

    Exactly one destination must be given.

    Attributes:
        rect: ``(x0, y0, x1, y1)`` in default user space.
        page_index: Zero-based index of the target page, for an internal jump.
        top: Vertical position on the target page, used with ``page_index``.
        dest_name: Name of a destination registered with
            :meth:`PdfDocument.add_named_destination`.
        uri: An absolute URI, for an external link.
    """

    rect: tuple[float, float, float, float]
    page_index: int | None = None
    top: float | None = None
    dest_name: str | None = None
    uri: str | None = None

    def __post_init__(self) -> None:
        given = sum(x is not None for x in (self.page_index, self.dest_name, self.uri))
        if given != 1:
            raise PdfWriteError(
                "LinkAnnotation precisa de exatamente um destino: page_index, dest_name ou uri."
            )
        if len(self.rect) != 4:  # noqa: PLR2004 -- a rectangle has four numbers
            raise PdfWriteError("LinkAnnotation.rect precisa de quatro numeros.")


@dataclass
class PdfPage:
    """One page: geometry, its content stream, resources and annotations.

    ``resources`` is deliberately a mutable dict. Font references only exist after
    :meth:`FontEmbedder.finalise`, which in turn can only run once every content stream
    has been built, so a caller that adds pages early needs somewhere to drop the refs in
    later.

    Attributes:
        width: Page width in points.
        height: Page height in points.
        content: The content stream bytes, from :meth:`ContentStream.to_bytes`.
        resources: The ``/Resources`` dictionary, e.g.
            ``{"Font": {"F1": ref}, "ExtGState": {"GS0": ref}}``.
        annotations: Link annotations, or raw annotation dictionaries.
        struct_parents: The ``/StructParents`` key for this page. Leave ``None`` and one
            is assigned automatically when a structure tree is present.
        extra: Extra entries merged into the page dictionary verbatim.
    """

    width: float
    height: float
    content: bytes = b""
    resources: dict[str, Any] = field(default_factory=dict)
    annotations: list[LinkAnnotation | dict[str, Any]] = field(default_factory=list)
    struct_parents: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PdfMetadata:
    """Document metadata, emitted both as DocInfo and as an XMP packet.

    Attributes:
        title: Document title.
        author: Author name.
        subject: Subject line.
        keywords: Comma-separated keywords.
        creator: The application that authored the source document.
        producer: The application that produced the PDF bytes.
        language: RFC 3066 language tag, e.g. ``"pt-BR"``.
        created: Creation timestamp; a naive value is read as UTC.
        modified: Modification timestamp; a naive value is read as UTC.
        pdf_a: When true, emit PDF/A-2b identification and an ``/OutputIntent``. Read
            :func:`pdfa_caveats` before telling a user the file is conformant.
        icc_profile: Raw ICC profile bytes for ``/DestOutputProfile``. Without it the
            output intent has no profile and the file is *not* conformant PDF/A-2b.
    """

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    producer: str | None = _DEFAULT_PRODUCER
    language: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    pdf_a: bool = False
    icc_profile: bytes | None = None


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    """One bookmark in the document outline.

    Attributes:
        title: The text shown in the reader's bookmark pane.
        page_index: Zero-based index of the page to jump to.
        top: Vertical position on that page, in points from the bottom.
        children: Nested bookmarks.
    """

    title: str
    page_index: int
    top: float
    children: tuple[OutlineEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class StructElement:
    """One node of the tagged-PDF structure tree.

    A node either groups children or points at a marked-content sequence on a page; a
    node that carries ``mcid`` must also carry ``page_index``, since the ``/ParentTree``
    is keyed by page.

    Attributes:
        tag: A tag from :data:`STRUCT_TAGS`.
        children: Nested structure elements.
        page_index: Zero-based index of the page this element's content lives on.
        mcid: The marked-content id emitted by
            :meth:`ContentStream.begin_marked_content`.
        alt: Alternate text, required on ``Figure`` for accessibility.
        lang: Language override for this subtree.
        title: Human-readable title, e.g. the heading text.

    Raises:
        PdfWriteError: If the tag is unknown or ``mcid`` is given without ``page_index``.
    """

    tag: str
    children: tuple[StructElement, ...] = ()
    page_index: int | None = None
    mcid: int | None = None
    alt: str | None = None
    lang: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        if self.tag not in STRUCT_TAGS:
            raise PdfWriteError(
                f"Tag de estrutura desconhecida: {self.tag!r}. "
                f"Validas: {', '.join(sorted(STRUCT_TAGS))}."
            )
        if self.mcid is not None and self.page_index is None:
            raise PdfWriteError(
                f"StructElement {self.tag!r} tem mcid={self.mcid} sem page_index; o "
                "/ParentTree e indexado por pagina."
            )


def pdfa_caveats() -> tuple[str, ...]:
    """Return the PDF/A caveats that apply to files produced by this writer.

    The strings are in Brazilian Portuguese and are meant to be shown to the user
    verbatim in an export report. They describe exactly what was *not* achieved, so
    nobody has to guess whether "PDF/A" here means validated conformance. It does not.

    Returns:
        The caveat strings, most important first.
    """
    return PDFA_CAVEATS


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #


def _glyph_id_map(font: TTFont) -> dict[str, int]:
    return {name: index for index, name in enumerate(font.getGlyphOrder())}


def _build_char_map(font: TTFont) -> dict[int, int]:
    """Map Unicode codepoints to glyph ids, with a symbolic-cmap fallback.

    Chess diagram fonts (Merida and the whole Marroquin family) frequently ship only a
    ``(3, 0)`` symbol cmap where the pieces live at ``0xF000 + ord(letter)``. Looking
    only at ``getBestCmap`` returns nothing for those faces and the board renders blank,
    so both ``0xF06B`` and plain ``0x6B`` are registered for such a glyph.

    Args:
        font: An open ``TTFont``.

    Returns:
        A mapping from codepoint to glyph id.
    """
    gid_of = _glyph_id_map(font)
    result: dict[int, int] = {}
    try:
        best = font.getBestCmap() or {}
    except (KeyError, AttributeError):
        best = {}
    for codepoint, name in best.items():
        gid = gid_of.get(name)
        if gid is not None:
            result[codepoint] = gid

    cmap_table = font.get("cmap")
    if cmap_table is None:
        return result
    for table in cmap_table.tables:
        symbolic = (table.platformID, table.platEncID) == (3, 0)
        mac_roman = (table.platformID, table.platEncID) == (1, 0)
        if not (symbolic or mac_roman):
            continue
        for codepoint, name in table.cmap.items():
            gid = gid_of.get(name)
            if gid is None:
                continue
            result.setdefault(codepoint, gid)
            if symbolic and _SYMBOL_CMAP_BASE <= codepoint <= _SYMBOL_CMAP_TOP:
                result.setdefault(codepoint - _SYMBOL_CMAP_BASE, gid)
    return result


def _legacy_kerning(font: TTFont, gid_of: Mapping[str, int]) -> dict[tuple[int, int], int]:
    """Read horizontal pairs from the legacy ``kern`` table (format 0 subtables)."""
    table = font.get("kern")
    if table is None:
        return {}
    pairs: dict[tuple[int, int], int] = {}
    for subtable in getattr(table, "kernTables", []):
        if getattr(subtable, "format", None) != 0:
            continue
        for (left, right), value in subtable.kernTable.items():
            left_gid = gid_of.get(left)
            right_gid = gid_of.get(right)
            if left_gid is not None and right_gid is not None and value:
                pairs[(left_gid, right_gid)] = int(value)
    return pairs


def _pairpos_format1(
    subtable: Any, gid_of: Mapping[str, int], out: dict[tuple[int, int], int]
) -> None:
    for first, pair_set in zip(subtable.Coverage.glyphs, subtable.PairSet, strict=False):
        left_gid = gid_of.get(first)
        if left_gid is None:
            continue
        for record in pair_set.PairValueRecord:
            value = getattr(record.Value1, "XAdvance", 0) if record.Value1 else 0
            right_gid = gid_of.get(record.SecondGlyph)
            if value and right_gid is not None:
                out[(left_gid, right_gid)] = int(value)


def _pairpos_format2(
    subtable: Any, gid_of: Mapping[str, int], out: dict[tuple[int, int], int]
) -> None:
    covered = set(subtable.Coverage.glyphs)
    class1: dict[int, list[str]] = {}
    for glyph, klass in subtable.ClassDef1.classDefs.items():
        class1.setdefault(klass, []).append(glyph)
    class1.setdefault(0, []).extend(g for g in covered if g not in subtable.ClassDef1.classDefs)
    class2: dict[int, list[str]] = {}
    for glyph, klass in subtable.ClassDef2.classDefs.items():
        class2.setdefault(klass, []).append(glyph)

    for i, record1 in enumerate(subtable.Class1Record):
        for j, record2 in enumerate(record1.Class2Record):
            value = getattr(record2.Value1, "XAdvance", 0) if record2.Value1 else 0
            if not value:
                continue
            for left in class1.get(i, ()):
                if left not in covered:
                    continue
                left_gid = gid_of.get(left)
                if left_gid is None:
                    continue
                for right in class2.get(j, ()):
                    right_gid = gid_of.get(right)
                    if right_gid is not None:
                        out[(left_gid, right_gid)] = int(value)


def _gpos_kerning(font: TTFont, gid_of: Mapping[str, int]) -> dict[tuple[int, int], int]:
    """Extract horizontal pair kerning from GPOS ``PairPos`` lookups.

    Modern faces (Georgia among them) carry no ``kern`` table at all. Ignoring GPOS would
    mean setting an entire book unkerned, so formats 1 and 2 are read here, including
    lookups wrapped in a type-9 extension.

    Args:
        font: An open ``TTFont``.
        gid_of: Glyph name to glyph id mapping.

    Returns:
        A mapping from ``(left_gid, right_gid)`` to an advance adjustment in font units.
    """
    gpos = font.get("GPOS")
    if gpos is None or gpos.table is None or gpos.table.LookupList is None:
        return {}
    out: dict[tuple[int, int], int] = {}
    for lookup in gpos.table.LookupList.Lookup:
        subtables = list(lookup.SubTable)
        lookup_type = lookup.LookupType
        if lookup_type == _GPOS_LOOKUP_EXTENSION:
            extended = [getattr(s, "ExtSubTable", None) for s in subtables]
            subtables = [s for s in extended if s is not None]
            lookup_type = _GPOS_LOOKUP_PAIR if subtables else 0
            if subtables and subtables[0].__class__.__name__ != "PairPos":
                continue
        if lookup_type != _GPOS_LOOKUP_PAIR:
            continue
        for subtable in subtables:
            if not getattr(subtable, "ValueFormat1", 0) & _GPOS_VALUEFORMAT_XADVANCE:
                continue
            try:
                if subtable.Format == 1:
                    _pairpos_format1(subtable, gid_of, out)
                elif subtable.Format == _GPOS_LOOKUP_PAIR:
                    _pairpos_format2(subtable, gid_of, out)
            except (AttributeError, IndexError, TypeError, KeyError):
                # A malformed lookup costs us kerning, never the whole export.
                continue
    return out


@dataclass(slots=True)
class _Face:
    """Everything read out of a font file once, so the ``TTFont`` can be closed."""

    data: bytes
    ps_name: str
    units_per_em: float
    char_map: dict[int, int]
    advances: dict[int, int]
    kerning: dict[tuple[int, int], int]
    descriptor: dict[str, Any]
    used: set[int] = field(default_factory=lambda: {0})


def _read_face(data: bytes, *, origin: str) -> _Face:
    """Read every table this writer needs out of a font file.

    Args:
        data: The raw font file bytes.
        origin: A human-readable source name, used in error messages.

    Returns:
        The extracted face data.

    Raises:
        PdfWriteError: If the file cannot be parsed, is not a TrueType outline font, or
            its embedding permissions forbid embedding.
    """
    # Chess fonts in circulation genuinely ship truncated `cmap` and out-of-range `head`
    # dates, and fontTools only notices when the table is decompiled -- which is well
    # after the constructor returns. So the whole read is guarded, not just the open.
    font: TTFont | None = None
    try:
        font = TTFont(io.BytesIO(data), fontNumber=0, lazy=False)
        if "glyf" not in font:
            raise PdfWriteError(
                f"A fonte {origin} nao tem contornos TrueType ('glyf'). Fontes CFF/OTF "
                "precisam ser convertidas antes de serem embutidas."
            )
        os2 = font.get("OS/2")
        if os2 is not None and (os2.fsType & _FSTYPE_MASK) == _FSTYPE_RESTRICTED:
            raise PdfWriteError(
                f"A licenca da fonte {origin} proibe embutir (fsType=0x{os2.fsType:04X})."
            )

        head = font["head"]
        hmtx = font["hmtx"]
        gid_of = _glyph_id_map(font)
        advances = {
            gid: int(hmtx.metrics[name][0]) for name, gid in gid_of.items() if name in hmtx.metrics
        }
        kerning = _legacy_kerning(font, gid_of) or _gpos_kerning(font, gid_of)
        return _Face(
            data=data,
            ps_name=_postscript_name(font, origin),
            units_per_em=float(head.unitsPerEm),
            char_map=_build_char_map(font),
            advances=advances,
            kerning=kerning,
            descriptor=_build_descriptor(font),
        )
    except PdfWriteError:
        raise
    except Exception as exc:
        # fontTools raises a wide, undocumented set; every one of them means the same
        # thing to the caller -- this file is not usable as a font.
        raise PdfWriteError(f"Nao foi possivel ler a fonte {origin}: {exc}") from exc
    finally:
        if font is not None:
            font.close()


def _postscript_name(font: TTFont, origin: str) -> str:
    """Return a usable PostScript name for the face, falling back to the file name."""
    name_table = font.get("name")
    if name_table is not None:
        for name_id in (6, 4, 1):
            record = name_table.getDebugName(name_id)
            if record:
                return "".join(ch for ch in record if ch.isprintable() and ch != " ")
    return Path(origin).stem or "Unnamed"


def _build_descriptor(font: TTFont) -> dict[str, Any]:
    """Compute the ``/FontDescriptor`` entries that do not depend on subsetting.

    Everything is scaled into the 1/1000 em space PDF uses for glyph space.

    Args:
        font: An open ``TTFont``.

    Returns:
        A dictionary with ``Flags``, ``FontBBox``, ``ItalicAngle``, ``Ascent``,
        ``Descent``, ``CapHeight`` and ``StemV``.
    """
    head = font["head"]
    hhea = font["hhea"]
    post = font.get("post")
    os2 = font.get("OS/2")
    upem = float(head.unitsPerEm) or 1000.0
    scale = 1000.0 / upem

    italic_angle = float(getattr(post, "italicAngle", 0.0) or 0.0)

    ascent = float(getattr(os2, "sTypoAscender", 0) or 0) or float(hhea.ascent)
    descent = float(getattr(os2, "sTypoDescender", 0) or 0) or float(hhea.descent)
    if descent > 0:
        descent = -descent

    cap_height = 0.0
    if os2 is not None and os2.version >= _OS2_VERSION_WITH_CAPHEIGHT:
        cap_height = float(getattr(os2, "sCapHeight", 0) or 0)
    if not cap_height:
        cap_height = ascent * 0.7

    flags = 0
    if getattr(post, "isFixedPitch", 0):
        flags |= _FLAG_FIXED_PITCH
    panose = getattr(os2, "panose", None)
    if (
        panose is not None
        and getattr(panose, "bFamilyType", 0) == _PANOSE_LATIN_TEXT
        and _PANOSE_SERIF_MIN <= getattr(panose, "bSerifStyle", 0) <= _PANOSE_SERIF_MAX
    ):
        flags |= _FLAG_SERIF
    if italic_angle:
        flags |= _FLAG_ITALIC
    # Exactly one of Symbolic / Nonsymbolic must be set. A face whose only cmap is the
    # (3, 0) symbol encoding -- every legacy chess font -- is Symbolic by definition.
    cmap_table = font.get("cmap")
    encodings = (
        {(t.platformID, t.platEncID) for t in cmap_table.tables}
        if cmap_table is not None
        else set()
    )
    has_unicode = any(
        (platform, encoding) in {(3, 1), (3, 10), (0, 3), (0, 4), (0, 6)}
        for platform, encoding in encodings
    )
    flags |= _FLAG_NONSYMBOLIC if has_unicode else _FLAG_SYMBOLIC

    # StemV has no counterpart in a TrueType file. This is the widely used Acrobat
    # approximation from the weight class; it is an estimate and nothing more.
    weight = float(getattr(os2, "usWeightClass", 400) or 400)
    stem_v = round(50.0 + (weight / 65.0) ** 2, 1)

    return {
        "Flags": flags,
        "FontBBox": [
            round(head.xMin * scale),
            round(head.yMin * scale),
            round(head.xMax * scale),
            round(head.yMax * scale),
        ],
        "ItalicAngle": round(italic_angle, 2),
        "Ascent": round(ascent * scale),
        "Descent": round(descent * scale),
        "CapHeight": round(cap_height * scale),
        "StemV": stem_v,
    }


@dataclass
class EmbeddedFont:
    """A TrueType/OpenType face embedded as a subset CID font.

    Instances come from :class:`FontEmbedder`; do not build one directly. Calling
    :meth:`encode` is what registers a glyph for the subset, so all text must be encoded
    before :meth:`FontEmbedder.finalise` runs.

    Attributes:
        resource_name: The name used in the content stream, e.g. ``"F1"`` for ``/F1``.
        units_per_em: The face's design grid size, usually 1000 or 2048.
    """

    resource_name: str
    units_per_em: float
    _face: _Face = field(repr=False)
    _to_unicode: dict[int, str] = field(default_factory=dict, repr=False)

    # -- glyph access ------------------------------------------------------- #

    def glyph_id(self, char: str) -> int:
        """Return the glyph id for a character, or 0 when the face lacks it.

        Args:
            char: A single character.

        Returns:
            The glyph id, or 0 (``.notdef``) if the character is not in the face.

        Raises:
            PdfWriteError: If ``char`` is not exactly one character.
        """
        if len(char) != 1:
            raise PdfWriteError(f"Esperado um unico caractere, recebido {char!r}.")
        return self._face.char_map.get(ord(char), 0)

    def has_char(self, char: str) -> bool:
        """Report whether the face can render a character.

        Args:
            char: A single character.

        Returns:
            True if the face maps the character to a real glyph.

        Raises:
            PdfWriteError: If ``char`` is not exactly one character.
        """
        if len(char) != 1:
            raise PdfWriteError(f"Esperado um unico caractere, recebido {char!r}.")
        return ord(char) in self._face.char_map

    def encode(self, text: str) -> bytes:
        """Encode text as Identity-H CID bytes and register the glyphs for subsetting.

        Identity-H is a two-byte encoding, so the result is always ``2 * len(text)``
        bytes; a character the face cannot render becomes ``.notdef`` rather than
        disappearing, which makes the hole visible instead of silent.

        Args:
            text: The text to encode.

        Returns:
            Big-endian two-bytes-per-glyph data, ready for :meth:`ContentStream.show`.
        """
        out = bytearray()
        for char in text:
            gid = self._face.char_map.get(ord(char), 0)
            self._face.used.add(gid)
            if gid:
                self._to_unicode.setdefault(gid, char)
            out += gid.to_bytes(2, "big")
        return bytes(out)

    # -- metrics ------------------------------------------------------------ #

    def width(self, char: str) -> float:
        """Return a character's advance in 1/1000 em units.

        Args:
            char: A single character.

        Returns:
            The advance width; the ``.notdef`` advance when the character is missing.

        Raises:
            PdfWriteError: If ``char`` is not exactly one character.
        """
        return self._advance(self.glyph_id(char))

    def _advance(self, gid: int) -> float:
        raw = self._face.advances.get(gid, 0)
        return raw * 1000.0 / self.units_per_em

    def text_width(self, text: str, size: float, *, tracking: float = 0.0) -> float:
        """Measure a string at a given type size, in points.

        Kerning is *not* included -- ask :meth:`kern` for that and apply it through
        :meth:`ContentStream.show_adjusted`. ``tracking`` matches the PDF ``Tc``
        operator, which adds the extra advance after every glyph *including the last*, so
        that this number predicts exactly what the content stream will do.

        Args:
            text: The string to measure.
            size: Type size in points.
            tracking: Extra advance per glyph, in points.

        Returns:
            The advance width in points.
        """
        total = sum(self._advance(self._face.char_map.get(ord(char), 0)) for char in text)
        return total / 1000.0 * size + tracking * len(text)

    def kern(self, left: str, right: str) -> float:
        """Return the kerning adjustment for a pair, in 1/1000 em units.

        The value is read from the legacy ``kern`` table when the face has one, and from
        GPOS ``PairPos`` lookups otherwise. Negative means "pull the pair together".

        Args:
            left: The left character of the pair.
            right: The right character of the pair.

        Returns:
            The adjustment, or ``0.0`` when the face defines no kerning for the pair.

        Raises:
            PdfWriteError: If either argument is not exactly one character.
        """
        pair = (self.glyph_id(left), self.glyph_id(right))
        raw = self._face.kerning.get(pair)
        if not raw:
            return 0.0
        return raw * 1000.0 / self.units_per_em

    # -- introspection ------------------------------------------------------ #

    @property
    def postscript_name(self) -> str:
        """The face's PostScript name, before the subset tag is prefixed."""
        return self._face.ps_name

    @property
    def used_glyphs(self) -> frozenset[int]:
        """The glyph ids registered so far by :meth:`encode`."""
        return frozenset(self._face.used)


class FontEmbedder:
    """Loads faces, tracks used glyphs, and emits subset CIDFontType2 objects.

    One embedder serves one document. Load each face once, build every content stream,
    then call :meth:`finalise` -- in that order, because :meth:`EmbeddedFont.encode` is
    what tells the subsetter which glyphs to keep.
    """

    def __init__(self) -> None:
        self._fonts: dict[str, EmbeddedFont] = {}
        self._by_source: dict[str, EmbeddedFont] = {}
        self._result: dict[str, PdfRef] | None = None

    def _next_name(self) -> str:
        index = 1
        while f"F{index}" in self._fonts:
            index += 1
        return f"F{index}"

    def load(self, path: Path, *, resource_name: str | None = None) -> EmbeddedFont:
        """Load a face from disk.

        Loading the same file twice returns the same :class:`EmbeddedFont`, so callers
        need not deduplicate.

        Args:
            path: Path to a TrueType/OpenType file with ``glyf`` outlines.
            resource_name: The content-stream resource name. Defaults to ``F1``, ``F2``...

        Returns:
            The embedded face.

        Raises:
            PdfWriteError: If the file is missing or unreadable, if the resource name is
                already taken by another face, or if fonts were already finalised.
        """
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise PdfWriteError(f"Nao foi possivel ler o arquivo de fonte {path}: {exc}") from exc
        key = str(path.resolve()) if path.exists() else str(path)
        cached = self._by_source.get(key)
        if cached is not None and (resource_name is None or resource_name == cached.resource_name):
            return cached
        font = self.load_bytes(data, resource_name=resource_name or self._next_name())
        self._by_source[key] = font
        return font

    def load_bytes(self, data: bytes, *, resource_name: str) -> EmbeddedFont:
        """Load a face from memory.

        Args:
            data: The raw font file bytes.
            resource_name: The content-stream resource name, e.g. ``"F1"``.

        Returns:
            The embedded face.

        Raises:
            PdfWriteError: If the data cannot be parsed, if the resource name is already
                taken, or if fonts were already finalised.
        """
        if self._result is not None:
            raise PdfWriteError(
                "As fontes ja foram finalizadas; carregue todas as faces antes de "
                "chamar finalise()."
            )
        existing = self._fonts.get(resource_name)
        if existing is not None:
            if existing._face.data == data:
                return existing
            raise PdfWriteError(
                f"O nome de recurso {resource_name!r} ja esta em uso por outra fonte."
            )
        face = _read_face(data, origin=resource_name)
        font = EmbeddedFont(
            resource_name=resource_name,
            units_per_em=face.units_per_em,
            _face=face,
        )
        self._fonts[resource_name] = font
        return font

    def fonts(self) -> Mapping[str, EmbeddedFont]:
        """Return the loaded faces keyed by resource name.

        Returns:
            A read-only view of the loaded faces.
        """
        return dict(self._fonts)

    def finalise(self, doc: PdfDocument) -> dict[str, PdfRef]:
        """Subset every loaded face and write its PDF objects into ``doc``.

        For each face this emits a ``Type0``/``Identity-H`` font dictionary, its
        ``CIDFontType2`` descendant with a ``/W`` array and ``/CIDToGIDMap /Identity``, a
        ``/FontDescriptor`` pointing at a ``/FontFile2`` stream with ``/Length1``, and a
        ``/ToUnicode`` CMap so the text can be selected, copied and searched.

        Calling it twice is a no-op that returns the same mapping.

        Args:
            doc: The document to add the objects to.

        Returns:
            A mapping from resource name to the ``Type0`` font dictionary reference,
            ready to drop into ``PdfPage.resources["Font"]``.

        Raises:
            PdfWriteError: If subsetting fails.
        """
        if self._result is not None:
            return dict(self._result)
        result: dict[str, PdfRef] = {}
        for name, font in self._fonts.items():
            result[name] = self._emit_font(doc, font)
        self._result = result
        return dict(result)

    # -- emission ----------------------------------------------------------- #

    def _emit_font(self, doc: PdfDocument, font: EmbeddedFont) -> PdfRef:
        face = font._face
        used = sorted(face.used | {0})
        subset_data = _subset_font(face.data, used, origin=font.resource_name)
        base_name = f"{_subset_tag(face.ps_name, used)}+{face.ps_name}"

        file_ref = doc.add_stream(
            subset_data,
            {"Length1": len(subset_data), "Subtype": PdfName("TrueType")},
        )
        descriptor = dict(face.descriptor)
        descriptor.update(
            {
                "Type": PdfName("FontDescriptor"),
                "FontName": PdfName(base_name),
                "MissingWidth": 0,
                "FontFile2": file_ref,
            }
        )
        # Rebuild in spec order so the object reads well when someone opens the file.
        ordered = {
            "Type": descriptor.pop("Type"),
            "FontName": descriptor.pop("FontName"),
            "Flags": descriptor.pop("Flags"),
            "FontBBox": descriptor.pop("FontBBox"),
            "ItalicAngle": descriptor.pop("ItalicAngle"),
            "Ascent": descriptor.pop("Ascent"),
            "Descent": descriptor.pop("Descent"),
            "CapHeight": descriptor.pop("CapHeight"),
            "StemV": descriptor.pop("StemV"),
            **descriptor,
        }
        descriptor_ref = doc.add_object(ordered)

        to_unicode_ref = doc.add_stream(
            _to_unicode_cmap(font._to_unicode, base_name),
        )
        descendant_ref = doc.add_object(
            {
                "Type": PdfName("Font"),
                "Subtype": PdfName("CIDFontType2"),
                "BaseFont": PdfName(base_name),
                "CIDSystemInfo": {
                    "Registry": "Adobe",
                    "Ordering": "Identity",
                    "Supplement": 0,
                },
                "FontDescriptor": descriptor_ref,
                "DW": 1000,
                "W": _widths_array(used, face),
                "CIDToGIDMap": PdfName("Identity"),
            }
        )
        return doc.add_object(
            {
                "Type": PdfName("Font"),
                "Subtype": PdfName("Type0"),
                "BaseFont": PdfName(base_name),
                "Encoding": PdfName("Identity-H"),
                "DescendantFonts": [descendant_ref],
                "ToUnicode": to_unicode_ref,
            }
        )


def _subset_font(data: bytes, glyph_ids: Sequence[int], *, origin: str) -> bytes:
    """Subset a face to the given glyph ids, keeping glyph indices stable.

    ``retain_gids`` is the whole point: without it the subsetter renumbers glyphs and the
    two-byte codes already written into content streams would address the wrong outlines.

    Args:
        data: The original font file bytes.
        glyph_ids: The glyph ids to keep; ``.notdef`` is always retained.
        origin: A human-readable source name, used in error messages.

    Returns:
        The subset font file bytes.

    Raises:
        PdfWriteError: If fontTools cannot subset the face.
    """
    try:
        font = TTFont(io.BytesIO(data), fontNumber=0)
        options = subset.Options()
        options.retain_gids = True
        options.glyph_names = False
        options.notdef_outline = True
        options.recommended_glyphs = False
        options.layout_features = []
        options.name_IDs = [1, 2, 3, 4, 5, 6]
        options.name_legacy = True
        options.hinting = True
        options.drop_tables += [
            "GSUB",
            "GPOS",
            "GDEF",
            "DSIG",
            "kern",
            "LTSH",
            "hdmx",
            "VDMX",
            "PCLT",
            "gasp",
            "meta",
            "FFTM",
        ]
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(gids=list(glyph_ids))
        subsetter.subset(font)
        buffer = io.BytesIO()
        font.save(buffer)
        font.close()
        return buffer.getvalue()
    except PdfWriteError:
        raise
    except Exception as exc:
        # Same reasoning as _read_face: fontTools' failure modes are undocumented.
        raise PdfWriteError(f"Falha ao criar o subconjunto da fonte {origin}: {exc}") from exc


def _subset_tag(ps_name: str, glyph_ids: Sequence[int]) -> str:
    """Derive the mandatory six-uppercase-letter subset tag.

    The tag is a hash of the face name and the retained glyph set rather than a random
    draw, so identical input yields an identical file.

    Args:
        ps_name: The face's PostScript name.
        glyph_ids: The retained glyph ids.

    Returns:
        Six uppercase ASCII letters.
    """
    seed = ps_name.encode("utf-8") + b"|" + b",".join(b"%d" % g for g in glyph_ids)
    digest = hashlib.md5(seed, usedforsecurity=False).digest()
    value = int.from_bytes(digest[:8], "big")
    letters = []
    for _ in range(_SUBSET_TAG_LENGTH):
        letters.append(chr(ord("A") + value % 26))
        value //= 26
    return "".join(letters)


def _widths_array(glyph_ids: Sequence[int], face: _Face) -> list[Any]:
    """Build the ``/W`` array, grouping runs of consecutive CIDs.

    Args:
        glyph_ids: The retained glyph ids, ascending.
        face: The face the advances come from.

    Returns:
        A ``/W`` array in the ``[cid [w w w] cid [w]]`` form.
    """
    scale = 1000.0 / (face.units_per_em or 1000.0)
    widths: list[Any] = []
    run_start: int | None = None
    run: list[Any] = []
    previous = -2
    for gid in glyph_ids:
        value = round(face.advances.get(gid, 0) * scale)
        if gid != previous + 1:
            if run_start is not None:
                widths.extend([run_start, run])
            run_start, run = gid, []
        run.append(value)
        previous = gid
    if run_start is not None:
        widths.extend([run_start, run])
    return widths


def _to_unicode_cmap(mapping: Mapping[int, str], font_name: str) -> bytes:
    """Build a ``/ToUnicode`` CMap stream mapping CIDs back to text.

    Without this a reader can draw the page but cannot tell you what it says: no
    selection, no copy, no search, no screen reader. For a chess book that is a failure,
    not a cosmetic gap.

    Args:
        mapping: Glyph id to the source text it was encoded from.
        font_name: The subset base font name, used for ``/CMapName``.

    Returns:
        The CMap program bytes.
    """
    entries = sorted(mapping.items())
    header = (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        f"/CMapName /{font_name}-UCS def\n"
        "/CMapType 2 def\n"
        "1 begincodespacerange\n"
        "<0000> <FFFF>\n"
        "endcodespacerange\n"
    )
    body: list[str] = []
    for start in range(0, len(entries), _HEX_PER_BFCHAR_BLOCK):
        block = entries[start : start + _HEX_PER_BFCHAR_BLOCK]
        body.append(f"{len(block)} beginbfchar")
        for gid, text in block:
            target = text.encode("utf-16-be").hex().upper()
            body.append(f"<{gid:04X}> <{target}>")
        body.append("endbfchar")
    footer = "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    return (header + "\n".join(body) + ("\n" if body else "") + footer).encode("ascii")


# --------------------------------------------------------------------------- #
# The document
# --------------------------------------------------------------------------- #


class PdfDocument:
    """Builds a PDF file object by object.

    Typical use::

        doc = PdfDocument()
        fonts = embedder.finalise(doc)  # after every content stream is built
        doc.add_page(PdfPage(595, 842, content, resources={"Font": fonts}))
        doc.set_metadata(PdfMetadata(title="Partidas"))
        doc.write(Path("out.pdf"))

    Objects added with :meth:`add_object` and :meth:`add_stream` are kept as Python
    values and serialised only in :meth:`to_bytes`, which builds the catalog, page tree,
    outline, structure tree and metadata into a *copy* of the table. ``to_bytes`` is
    therefore repeatable and free of side effects.
    """

    def __init__(self, *, version: str = "1.7", compress: bool = True) -> None:
        """Create an empty document.

        Args:
            version: The PDF version to declare in the header.
            compress: Default for stream compression; pass false to write readable,
                uncompressed streams while debugging.

        Raises:
            PdfWriteError: If the version is not one this writer supports.
        """
        if version not in SUPPORTED_VERSIONS:
            raise PdfWriteError(
                f"Versao de PDF nao suportada: {version!r}. "
                f"Use uma de: {', '.join(SUPPORTED_VERSIONS)}."
            )
        self.version = version
        self.compress = compress
        self._objects = _ObjectTable()
        self._pages: list[PdfPage] = []
        self._page_refs: list[PdfRef] = []
        self._page_contents: list[PdfRef] = []
        self._metadata = PdfMetadata()
        self._outline: tuple[OutlineEntry, ...] = ()
        self._struct_root: StructElement | None = None
        self._named_dests: dict[str, tuple[int, float]] = {}

    # -- raw objects -------------------------------------------------------- #

    def add_object(self, payload: bytes | dict[str, Any] | list[Any]) -> PdfRef:
        """Add an indirect object.

        Args:
            payload: A dictionary, an array, or raw pre-serialised PDF syntax as bytes.

        Returns:
            A reference to the new object.
        """
        return self._objects.add(payload)

    def add_stream(
        self,
        data: bytes,
        extra: dict[str, Any] | None = None,
        *,
        compress: bool | None = None,
    ) -> PdfRef:
        """Add a stream object.

        Args:
            data: The stream payload, uncompressed.
            extra: Extra entries for the stream dictionary. ``/Length`` and ``/Filter``
                are supplied by the writer and must not be given here.
            compress: Whether to deflate the data. Defaults to the document setting.

        Returns:
            A reference to the new stream object.

        Raises:
            PdfWriteError: If ``extra`` tries to set ``/Length`` or ``/Filter``.
        """
        extra = dict(extra or {})
        clashes = {"Length", "Filter"} & set(extra)
        if clashes:
            raise PdfWriteError(
                f"O escritor define /Length e /Filter; remova {sorted(clashes)} de extra."
            )
        use_compress = self.compress if compress is None else compress
        return self._objects.add(_Stream(data=data, extra=extra, compress=use_compress))

    # -- pages -------------------------------------------------------------- #

    def add_page(self, page: PdfPage) -> PdfRef:
        """Append a page.

        The content stream object is created immediately; the page dictionary itself is
        assembled in :meth:`to_bytes`, so ``page.resources`` may still be filled in after
        this call.

        Args:
            page: The page to append.

        Returns:
            A reference to the page object.
        """
        content_ref = self.add_stream(page.content)
        page_ref = self._objects.reserve()
        self._pages.append(page)
        self._page_refs.append(page_ref)
        self._page_contents.append(content_ref)
        return page_ref

    @property
    def page_count(self) -> int:
        """Number of pages added so far."""
        return len(self._pages)

    # -- document-level settings -------------------------------------------- #

    def set_metadata(self, meta: PdfMetadata) -> None:
        """Set the document metadata.

        Args:
            meta: The metadata to emit as DocInfo and XMP.
        """
        self._metadata = meta

    def set_outline(self, entries: Sequence[OutlineEntry]) -> None:
        """Set the document outline (bookmarks).

        Args:
            entries: The top-level entries, in display order. Pass an empty sequence to
                remove the outline.
        """
        self._outline = tuple(entries)

    def set_struct_tree(self, root: StructElement | None) -> None:
        """Set the tagged-PDF structure tree.

        Args:
            root: The root element, conventionally tagged ``Document``. ``None`` removes
                the structure tree and the catalog's ``/MarkInfo``.
        """
        self._struct_root = root

    def add_named_destination(self, name: str, page_index: int, top: float) -> None:
        """Register a named destination usable from links and from outside the file.

        Args:
            name: The destination name.
            page_index: Zero-based index of the target page.
            top: Vertical position on that page, in points from the bottom.

        Raises:
            PdfWriteError: If the name is empty or already registered with a different
                target.
        """
        if not name:
            raise PdfWriteError("Nome de destino vazio.")
        existing = self._named_dests.get(name)
        if existing is not None and existing != (page_index, top):
            raise PdfWriteError(f"Destino nomeado duplicado com alvo diferente: {name!r}.")
        self._named_dests[name] = (page_index, top)

    # -- output ------------------------------------------------------------- #

    def to_bytes(self) -> bytes:
        """Serialise the whole document.

        Returns:
            The complete PDF file bytes, header to ``%%EOF``.

        Raises:
            PdfWriteError: If the document has no pages, or if an outline entry,
                destination or structure element points at a page that does not exist.
        """
        if not self._pages:
            raise PdfWriteError("Um PDF precisa de pelo menos uma pagina.")

        table = self._objects.copy()
        pages_ref = table.reserve()
        catalog_ref = table.reserve()

        struct_parents = self._assign_struct_parents()
        struct_ref = self._build_struct_tree(table, struct_parents)
        self._build_pages(table, pages_ref, struct_parents)
        table.assign(
            pages_ref,
            {
                "Type": PdfName("Pages"),
                "Kids": list(self._page_refs),
                "Count": len(self._pages),
            },
        )

        catalog: dict[str, Any] = {
            "Type": PdfName("Catalog"),
            "Pages": pages_ref,
        }
        outline_ref = self._build_outline(table)
        if outline_ref is not None:
            catalog["Outlines"] = outline_ref
            catalog["PageMode"] = PdfName("UseOutlines")
        names_ref = self._build_named_dests(table)
        if names_ref is not None:
            catalog["Names"] = {"Dests": names_ref}
        if struct_ref is not None:
            catalog["StructTreeRoot"] = struct_ref
            catalog["MarkInfo"] = {"Marked": True}
        language = self._metadata.language or (DEFAULT_LANGUAGE if struct_ref is not None else None)
        if language:
            catalog["Lang"] = language
        if self._metadata.title:
            catalog["ViewerPreferences"] = {"DisplayDocTitle": True}
        catalog["Metadata"] = table.add(
            _Stream(
                data=self._build_xmp(),
                extra={"Type": PdfName("Metadata"), "Subtype": PdfName("XML")},
                # XMP must stay readable to tools that scan the raw file for it.
                compress=False,
            )
        )
        if self._metadata.pdf_a:
            catalog["OutputIntents"] = [self._build_output_intent(table)]
        table.assign(catalog_ref, catalog)

        info_ref = self._build_info(table)
        return _assemble(
            version=self.version,
            payloads=table.payloads(),
            root=catalog_ref,
            info=info_ref,
        )

    def write(self, path: Path) -> None:
        """Serialise the document and write it to disk.

        Args:
            path: Destination file. Parent directories are created if missing.

        Raises:
            PdfWriteError: If the document cannot be serialised or the file written.
        """
        data = self.to_bytes()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise PdfWriteError(f"Nao foi possivel gravar o PDF em {path}: {exc}") from exc

    # -- internals ---------------------------------------------------------- #

    def _check_page_index(self, index: int, what: str) -> None:
        if not 0 <= index < len(self._pages):
            raise PdfWriteError(
                f"{what} aponta para a pagina {index}, mas o documento tem "
                f"{len(self._pages)} pagina(s)."
            )

    def _dest_array(self, page_index: int, top: float) -> list[Any]:
        self._check_page_index(page_index, "Destino")
        return [self._page_refs[page_index], PdfName("XYZ"), None, top, None]

    def _assign_struct_parents(self) -> dict[int, int]:
        """Give every page that appears in the structure tree a ``/StructParents`` key."""
        if self._struct_root is None:
            return {}
        needed: set[int] = set()

        def walk(element: StructElement) -> None:
            if element.mcid is not None and element.page_index is not None:
                needed.add(element.page_index)
            for child in element.children:
                walk(child)

        walk(self._struct_root)
        for index in sorted(needed):
            self._check_page_index(index, "Elemento de estrutura")

        assigned: dict[int, int] = {}
        taken: set[int] = set()
        for index in sorted(needed):
            declared = self._pages[index].struct_parents
            if declared is not None:
                assigned[index] = declared
                taken.add(declared)
        counter = 0
        for index in sorted(needed):
            if index in assigned:
                continue
            while counter in taken:
                counter += 1
            assigned[index] = counter
            taken.add(counter)
            counter += 1
        return assigned

    def _build_pages(
        self, table: _ObjectTable, pages_ref: PdfRef, struct_parents: Mapping[int, int]
    ) -> None:
        for index, page in enumerate(self._pages):
            entry: dict[str, Any] = {
                "Type": PdfName("Page"),
                "Parent": pages_ref,
                "MediaBox": [0, 0, page.width, page.height],
                "Resources": page.resources,
                "Contents": self._page_contents[index],
            }
            annots = [self._annotation(table, a) for a in page.annotations]
            if annots:
                entry["Annots"] = annots
            key = struct_parents.get(index, page.struct_parents)
            if key is not None:
                entry["StructParents"] = key
            entry.update(page.extra)
            table.assign(self._page_refs[index], entry)

    def _annotation(
        self, table: _ObjectTable, annotation: LinkAnnotation | dict[str, Any]
    ) -> PdfRef:
        if isinstance(annotation, dict):
            return table.add(annotation)
        entry: dict[str, Any] = {
            "Type": PdfName("Annot"),
            "Subtype": PdfName("Link"),
            "Rect": list(annotation.rect),
            "Border": [0, 0, 0],
            "F": 4,  # Print: required by PDF/A and sane for a book
        }
        if annotation.uri is not None:
            entry["A"] = {"S": PdfName("URI"), "URI": annotation.uri}
        elif annotation.dest_name is not None:
            if annotation.dest_name not in self._named_dests:
                raise PdfWriteError(
                    f"Link aponta para o destino nomeado {annotation.dest_name!r}, que "
                    "nao foi registrado."
                )
            entry["Dest"] = annotation.dest_name
        else:
            # __post_init__ guarantees exactly one destination is set.
            page_index = annotation.page_index or 0
            entry["Dest"] = self._dest_array(page_index, annotation.top or 0.0)
        return table.add(entry)

    def _build_named_dests(self, table: _ObjectTable) -> PdfRef | None:
        if not self._named_dests:
            return None
        names: list[Any] = []
        for name in sorted(self._named_dests):
            page_index, top = self._named_dests[name]
            names.extend([name, {"D": self._dest_array(page_index, top)}])
        return table.add({"Names": names})

    def _build_outline(self, table: _ObjectTable) -> PdfRef | None:
        if not self._outline:
            return None
        root_ref = table.reserve()

        def build(entries: Sequence[OutlineEntry], parent: PdfRef) -> tuple[PdfRef, PdfRef, int]:
            refs = [table.reserve() for _ in entries]
            total = 0
            for position, entry in enumerate(entries):
                self._check_page_index(entry.page_index, f"Marcador {entry.title!r}")
                item: dict[str, Any] = {
                    "Title": entry.title,
                    "Parent": parent,
                    "Dest": self._dest_array(entry.page_index, entry.top),
                }
                if position > 0:
                    item["Prev"] = refs[position - 1]
                if position + 1 < len(refs):
                    item["Next"] = refs[position + 1]
                descendants = 0
                if entry.children:
                    first, last, descendants = build(entry.children, refs[position])
                    item["First"] = first
                    item["Last"] = last
                    # Positive: the subtree is open, matching /PageMode /UseOutlines.
                    item["Count"] = descendants
                table.assign(refs[position], item)
                total += 1 + descendants
            return refs[0], refs[-1], total

        first_ref, last_ref, count = build(self._outline, root_ref)
        table.assign(
            root_ref,
            {
                "Type": PdfName("Outlines"),
                "First": first_ref,
                "Last": last_ref,
                "Count": count,
            },
        )
        return root_ref

    def _build_struct_tree(
        self, table: _ObjectTable, struct_parents: Mapping[int, int]
    ) -> PdfRef | None:
        if self._struct_root is None:
            return None
        root_ref = table.reserve()
        # struct_parents key -> mcid -> owning element
        by_page: dict[int, dict[int, PdfRef]] = {}

        def build(element: StructElement, parent: PdfRef) -> PdfRef:
            ref = table.reserve()
            entry: dict[str, Any] = {
                "Type": PdfName("StructElem"),
                "S": PdfName(element.tag),
                "P": parent,
            }
            if element.title is not None:
                entry["T"] = element.title
            if element.alt is not None:
                entry["Alt"] = element.alt
            if element.lang is not None:
                entry["Lang"] = element.lang
            if element.page_index is not None:
                self._check_page_index(element.page_index, f"StructElement {element.tag!r}")
                entry["Pg"] = self._page_refs[element.page_index]

            kids: list[Any] = []
            if element.mcid is not None and element.page_index is not None:
                kids.append(element.mcid)
                key = struct_parents[element.page_index]
                by_page.setdefault(key, {})[element.mcid] = ref
            kids.extend(build(child, ref) for child in element.children)
            if kids:
                entry["K"] = kids[0] if len(kids) == 1 else kids
            table.assign(ref, entry)
            return ref

        child_ref = build(self._struct_root, root_ref)

        nums: list[Any] = []
        for key in sorted(by_page):
            slots = by_page[key]
            array: list[PdfRef | None] = [slots.get(i) for i in range(max(slots) + 1)]
            nums.extend([key, table.add(array)])
        parent_tree_ref = table.add({"Nums": nums})

        table.assign(
            root_ref,
            {
                "Type": PdfName("StructTreeRoot"),
                "K": child_ref,
                "ParentTree": parent_tree_ref,
                "ParentTreeNextKey": (max(by_page) + 1) if by_page else 0,
                "RoleMap": {tag: PdfName(role) for tag, role in sorted(_ROLE_MAP.items())},
            },
        )
        return root_ref

    def _build_info(self, table: _ObjectTable) -> PdfRef:
        meta = self._metadata
        info: dict[str, Any] = {
            key: value
            for key, value in (
                ("Title", meta.title),
                ("Author", meta.author),
                ("Subject", meta.subject),
                ("Keywords", meta.keywords),
                ("Creator", meta.creator),
                ("Producer", meta.producer),
            )
            if value
        }
        if meta.created is not None:
            info["CreationDate"] = meta.created
        if meta.modified is not None:
            info["ModDate"] = meta.modified
        return table.add(info)

    def _build_output_intent(self, table: _ObjectTable) -> dict[str, Any]:
        """Build the PDF/A ``/OutputIntent``.

        Without :attr:`PdfMetadata.icc_profile` there is no ``/DestOutputProfile``, and
        the file is PDF/A *structure* without a colour profile. See :func:`pdfa_caveats`.

        Args:
            table: The object table the profile stream is added to.

        Returns:
            The output intent dictionary.
        """
        intent: dict[str, Any] = {
            "Type": PdfName("OutputIntent"),
            "S": PdfName("GTS_PDFA1"),
            "OutputConditionIdentifier": "sRGB",
            "OutputCondition": "sRGB IEC61966-2.1",
            "RegistryName": "http://www.color.org",
        }
        if self._metadata.icc_profile:
            intent["DestOutputProfile"] = table.add(
                _Stream(
                    data=self._metadata.icc_profile,
                    extra={"N": 3, "Alternate": PdfName("DeviceRGB")},
                    compress=self.compress,
                )
            )
        else:
            intent["Info"] = "sRGB IEC61966-2.1 -- nenhum perfil ICC embutido"
        return intent

    def _build_xmp(self) -> bytes:
        """Build the XMP metadata packet as well-formed XML.

        Written by hand rather than through a serialiser because the packet needs the
        ``<?xpacket?>`` wrapper and a byte-exact structure that XMP readers expect.

        Returns:
            The UTF-8 encoded XMP packet.
        """
        meta = self._metadata
        lines: list[str] = [
            '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>',
            f'<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="{xml_escape(_XMP_TOOLKIT)}">',
            ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
            '  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">',
        ]
        if meta.title:
            lines.append(
                '   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">'
                f"{xml_escape(meta.title)}</rdf:li></rdf:Alt></dc:title>"
            )
        if meta.author:
            lines.append(
                "   <dc:creator><rdf:Seq><rdf:li>"
                f"{xml_escape(meta.author)}</rdf:li></rdf:Seq></dc:creator>"
            )
        if meta.subject:
            lines.append(
                '   <dc:description><rdf:Alt><rdf:li xml:lang="x-default">'
                f"{xml_escape(meta.subject)}</rdf:li></rdf:Alt></dc:description>"
            )
        language = meta.language or DEFAULT_LANGUAGE
        lines.append(
            "   <dc:language><rdf:Bag><rdf:li>"
            f"{xml_escape(language)}</rdf:li></rdf:Bag></dc:language>"
        )
        lines.append("   <dc:format>application/pdf</dc:format>")
        lines.append("  </rdf:Description>")

        lines.append('  <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">')
        if meta.creator:
            lines.append(f"   <xmp:CreatorTool>{xml_escape(meta.creator)}</xmp:CreatorTool>")
        if meta.created is not None:
            lines.append(f"   <xmp:CreateDate>{_format_xmp_date(meta.created)}</xmp:CreateDate>")
        if meta.modified is not None:
            lines.append(f"   <xmp:ModifyDate>{_format_xmp_date(meta.modified)}</xmp:ModifyDate>")
        lines.append("  </rdf:Description>")

        lines.append('  <rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">')
        if meta.producer:
            lines.append(f"   <pdf:Producer>{xml_escape(meta.producer)}</pdf:Producer>")
        if meta.keywords:
            lines.append(f"   <pdf:Keywords>{xml_escape(meta.keywords)}</pdf:Keywords>")
        lines.append("  </rdf:Description>")

        if meta.pdf_a:
            lines.extend(
                [
                    '  <rdf:Description rdf:about=""'
                    ' xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">',
                    "   <pdfaid:part>2</pdfaid:part>",
                    "   <pdfaid:conformance>B</pdfaid:conformance>",
                    "  </rdf:Description>",
                ]
            )
        lines.extend([" </rdf:RDF>", "</x:xmpmeta>", '<?xpacket end="w"?>'])
        return "\n".join(lines).encode("utf-8")


# --------------------------------------------------------------------------- #
# File assembly
# --------------------------------------------------------------------------- #


def _serialise_object(number: int, payload: Any) -> bytes:
    """Serialise one indirect object, streams included.

    Args:
        number: The object number.
        payload: The object payload, or a ``_Stream``.

    Returns:
        The complete ``n 0 obj ... endobj`` block.

    Raises:
        PdfWriteError: If the payload was never assigned.
    """
    if payload is None:
        raise PdfWriteError(f"O objeto {number} foi reservado mas nunca preenchido.")
    if isinstance(payload, _Stream):
        data = payload.data
        entries = dict(payload.extra)
        if payload.compress:
            data = zlib.compress(data, 9)
            entries["Filter"] = PdfName("FlateDecode")
        entries["Length"] = len(data)
        body = _serialise(entries) + b"\nstream\n" + data + b"\nendstream"
    else:
        body = _serialise(payload)
    return b"%d 0 obj\n" % number + body + b"\nendobj\n"


def _assemble(*, version: str, payloads: Sequence[Any], root: PdfRef, info: PdfRef) -> bytes:
    """Lay out the body, the classic cross-reference table and the trailer.

    Args:
        version: The PDF version for the header.
        payloads: Object payloads in object-number order.
        root: Reference to the catalog.
        info: Reference to the DocInfo dictionary.

    Returns:
        The complete file bytes.
    """
    # The binary comment tells transfer agents this is not a text file.
    out = bytearray(b"%PDF-" + version.encode("ascii") + b"\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, payload in enumerate(payloads, start=1):
        offsets.append(len(out))
        out += _serialise_object(index, payload)

    xref_offset = len(out)
    count = len(payloads) + 1
    out += b"xref\n0 %d\n" % count
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset

    # Deterministic /ID: a hash of the body, so the same document is the same file.
    digest = hashlib.md5(bytes(out), usedforsecurity=False).hexdigest().upper()
    file_id = b"<" + digest.encode("ascii") + b">"
    trailer = {
        "Size": count,
        "Root": root,
        "Info": info,
        "ID": [file_id, file_id],
    }
    out += b"trailer\n" + _serialise(trailer) + b"\n"
    out += b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(out)
