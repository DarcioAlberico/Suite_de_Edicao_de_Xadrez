"""PDF output: subset fonts, vector diagrams, a navigable outline, XMP.

SPEC section 8.1 asks for embedded subset fonts, diagrams **vetoriais (nunca
raster)**, a navigable outline, bookmarks, XMP metadata, optional PDF/A-2b and
accessibility tagging. The file writer that does the byte-level work is
:mod:`caissa.export.pdfwrite`; what is here is the part that turns a document
tree into pages.

Vector, and how it is guaranteed
--------------------------------
The diagram arrives as the same SVG the HTML and EPUB exporters use.
:class:`_SvgPainter` walks it and emits PDF path operators -- ``re``, ``m``,
``l``, ``c``, ``f``, ``S`` -- straight into the page content stream. There is no
image XObject anywhere in the diagram path, so the "vectorness" assertion in
``tests/unit/export/test_vectorness.py`` is not a style check: a regression that
rasterised a board would have to add an XObject, and the test would see it.

Where this writer is honest about being simple
----------------------------------------------
The layout engine is a single-column galley: it breaks lines greedily on the
embedded font's own advance widths, keeps headings with their following line,
and starts a new page when the galley is full. It is not a Knuth-Plass
paragraph optimiser, and it does not float figures. Those are typesetting
decisions that belong to :mod:`caissa.typeset`, and where the layout falls
short of what the IR asked for -- a two-column section, a fixed page geometry --
the profile declares it and a warning is recorded rather than the request being
dropped.

Reading it back
---------------
Recovering an IR from a page of glyph-placement operators is not possible in
any useful sense: the tree is gone the moment it becomes ink. The exporter
therefore writes the serialised IR beside the PDF as ``<name>.caissa.json``,
listed in :attr:`~caissa.export.base.ExportResult.artifacts`, and
:func:`read_pdf` reads that. :mod:`caissa.export.fidelity` labels any number
measured this way ``method="sidecar"`` so it is never quoted as evidence about
this writer.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

from caissa.core.model import (
    Alignment,
    Block,
    Callout,
    CodeBlock,
    ColorSpace,
    Diagram,
    Document,
    Endnote,
    Figure,
    Footnote,
    GameScore,
    Group,
    Heading,
    ImageBlock,
    Inline,
    ListBlock,
    ListKind,
    MathBlock,
    Measure,
    PageBreak,
    Paragraph,
    ParagraphProps,
    Quote,
    RawPassthrough,
    RunProps,
    SectionBreak,
    Table,
    TableOfContents,
    ThematicBreak,
    document_from_payload,
    document_to_payload,
    tag_of,
)
from caissa.export.base import ExportContext, Exporter, ExportError, ExportOptions, ExportResult
from caissa.export.diagrams import DiagramRenderer
from caissa.export.pdfwrite import (
    ContentStream,
    EmbeddedFont,
    FontEmbedder,
    OutlineEntry,
    PdfDocument,
    PdfMetadata,
    PdfPage,
    PdfWriteError,
)
from caissa.export.profiles import PDF_PROFILE
from caissa.export.text import figurine_char, game_to_pgn, nag_symbol, render_move

__all__ = ["SIDECAR_SUFFIX", "PdfExporter", "PdfOptions", "read_pdf"]

SIDECAR_SUFFIX = ".caissa.json"
"""Suffix of the IR file written beside the PDF; see the module docstring."""

MM_TO_PT = 72.0 / 25.4

_FONT_SEARCH = (
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/Library/Fonts"),
)

_FALLBACK_FILES: Mapping[str, tuple[str, ...]] = {
    "roman": ("times.ttf", "georgia.ttf", "DejaVuSerif.ttf", "arial.ttf"),
    "bold": ("timesbd.ttf", "georgiab.ttf", "DejaVuSerif-Bold.ttf", "arialbd.ttf"),
    "italic": ("timesi.ttf", "georgiai.ttf", "DejaVuSerif-Italic.ttf", "ariali.ttf"),
    "bolditalic": ("timesbi.ttf", "georgiaz.ttf", "arialbi.ttf"),
    "mono": ("cour.ttf", "consola.ttf", "DejaVuSansMono.ttf"),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class PdfOptions(ExportOptions):
    """Settings specific to PDF output.

    Attributes:
        page_width_mm: Page width; A5 by default.
        page_height_mm: Page height.
        margin_mm: Margin on all four sides.
        body_size_pt: Body type size.
        leading: Line height as a multiple of the type size.
        pdf_a: Emit PDF/A-2b identification. Read
            :func:`caissa.export.pdfwrite.pdfa_caveats` before promising it.
        tagged: Emit a structure tree for accessibility.
        outline_depth: Deepest heading level that becomes a bookmark.
    """

    page_width_mm: float = 148.0
    page_height_mm: float = 210.0
    margin_mm: float = 16.0
    body_size_pt: float = 10.5
    leading: float = 1.32
    pdf_a: bool = False
    tagged: bool = True
    outline_depth: int = 3


# --------------------------------------------------------------------------- #
# SVG -> PDF vector painting
# --------------------------------------------------------------------------- #
_NUMBER = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")
_COMMAND = re.compile(r"([MLCZmlczHhVv])([^MLCZmlczHhVv]*)")
_TRANSLATE = re.compile(r"translate\(\s*(-?[\d.]+)[ ,]*(-?[\d.]+)?\s*\)")
_SCALE = re.compile(r"scale\(\s*(-?[\d.]+)\s*\)")


def _tag(element: ET.Element) -> str:
    """Return an element's local name.

    Args:
        element: The element.

    Returns:
        The tag without its namespace.
    """
    return element.tag.rsplit("}", 1)[-1]


def _number(value: str | None, default: float = 0.0) -> float:
    """Parse an SVG length, ignoring the unit suffix.

    Args:
        value: The attribute text.
        default: What to return when it is missing or unparseable.

    Returns:
        The number.
    """
    if value is None:
        return default
    match = _NUMBER.search(value)
    return float(match.group(0)) if match else default


def _svg_colour(value: str | None) -> tuple[float, float, float] | None:
    """Parse an SVG paint into an RGB triple in ``[0, 1]``.

    Args:
        value: The attribute text.

    Returns:
        The triple, or ``None`` for ``none`` and unparseable values.
    """
    if not value or value in ("none", "transparent"):
        return None
    text = value.strip()
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) == 3:
            digits = "".join(char * 2 for char in digits)
        if len(digits) >= 6:
            return tuple(int(digits[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]
    named = {
        "black": (0.0, 0.0, 0.0),
        "white": (1.0, 1.0, 1.0),
        "red": (1.0, 0.0, 0.0),
        "green": (0.0, 0.5, 0.0),
        "blue": (0.0, 0.0, 1.0),
        "currentColor": (0.0, 0.0, 0.0),
    }
    return named.get(text)


def _subpaths(data: str) -> list[list[tuple[Any, ...]]]:
    """Parse SVG path data into subpaths of absolute segments.

    Only the commands the board renderer emits are understood. An unknown
    command ends the subpath rather than being guessed at: a wrong curve is
    worse than a missing one, because nobody notices it.

    Args:
        data: The ``d`` attribute.

    Returns:
        Subpaths, each a list of ``("L", x, y)``, ``("C", ...)`` or ``("Z",)``.
    """
    paths: list[list[tuple[Any, ...]]] = []
    current: list[tuple[Any, ...]] = []
    x = y = 0.0
    start_x = start_y = 0.0
    for match in _COMMAND.finditer(data):
        command = match.group(1)
        numbers = [float(item) for item in _NUMBER.findall(match.group(2))]
        upper = command.upper()
        relative = command.islower()
        if upper == "Z":
            if current:
                current.append(("Z",))
                paths.append(current)
                current = []
            x, y = start_x, start_y
            continue
        if upper == "M":
            for index in range(0, len(numbers) - 1, 2):
                dx, dy = numbers[index], numbers[index + 1]
                x, y = (x + dx, y + dy) if relative else (dx, dy)
                if index == 0:
                    if current:
                        paths.append(current)
                    current = [("M", x, y)]
                    start_x, start_y = x, y
                else:
                    current.append(("L", x, y))
        elif upper == "L":
            for index in range(0, len(numbers) - 1, 2):
                dx, dy = numbers[index], numbers[index + 1]
                x, y = (x + dx, y + dy) if relative else (dx, dy)
                current.append(("L", x, y))
        elif upper == "H":
            for value in numbers:
                x = x + value if relative else value
                current.append(("L", x, y))
        elif upper == "V":
            for value in numbers:
                y = y + value if relative else value
                current.append(("L", x, y))
        elif upper == "C":
            for index in range(0, len(numbers) - 5, 6):
                points = numbers[index : index + 6]
                if relative:
                    points = [
                        value + (x if position % 2 == 0 else y)
                        for position, value in enumerate(points)
                    ]
                current.append(("C", *points))
                x, y = points[4], points[5]
    if current:
        paths.append(current)
    return paths


def _transform(value: str | None) -> tuple[float, float, float]:
    """Parse the translate/scale subset the board renderer emits.

    Args:
        value: The ``transform`` attribute.

    Returns:
        ``(dx, dy, scale)``.
    """
    if not value:
        return (0.0, 0.0, 1.0)
    dx = dy = 0.0
    scale = 1.0
    match = _TRANSLATE.search(value)
    if match:
        dx = float(match.group(1))
        dy = float(match.group(2)) if match.group(2) is not None else 0.0
    match = _SCALE.search(value)
    if match:
        scale = float(match.group(1))
    return (dx, dy, scale)


@dataclass(slots=True)
class _PaintResult:
    """What painting one SVG produced, so the caller can report it.

    Attributes:
        drawn: How many shapes reached the page.
        skipped: Element names outside the painter's vocabulary.
        text_runs: How many ``text`` elements were drawn.
    """

    drawn: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    text_runs: int = 0


class _SvgPainter:
    """Draws a board SVG into a PDF content stream as real vector geometry."""

    def __init__(self, stream: ContentStream, chess_font: EmbeddedFont | None) -> None:
        """Create a painter.

        Args:
            stream: The content stream to draw into.
            chess_font: The embedded chess face, for the SVG's ``text`` glyphs.
        """
        self.stream = stream
        self.chess_font = chess_font
        self.result = _PaintResult()

    def paint(self, svg: str, x: float, y: float, width_pt: float) -> float:
        """Draw one SVG at a page position.

        Args:
            svg: The SVG source, in millimetre user units.
            x: Left edge, in points from the page's left.
            y: **Top** edge, in points from the page's bottom.
            width_pt: Width to draw at; the height follows the aspect ratio.

        Returns:
            The height drawn, in points.
        """
        root = ET.fromstring(svg)
        view = root.get("viewBox")
        if view:
            numbers = [float(item) for item in _NUMBER.findall(view)]
            width_mm, height_mm = (
                (numbers[2], numbers[3]) if len(numbers) >= 4 else (100.0, 100.0)
            )
        else:
            width_mm = _number(root.get("width"), 100.0)
            height_mm = _number(root.get("height"), 100.0)
        scale = width_pt / (width_mm * MM_TO_PT) if width_mm else 1.0
        unit = MM_TO_PT * scale
        height_pt = height_mm * unit / MM_TO_PT * MM_TO_PT / MM_TO_PT * MM_TO_PT
        height_pt = height_mm * unit

        def px(value: float) -> float:
            return x + value * unit

        def py(value: float) -> float:
            return y - value * unit

        self.stream.save()
        for element, state in self._walk(root, (0.0, 0.0, 1.0)):
            name = _tag(element)
            tx, ty, ts = state

            def mx(value: float, tx: float = tx, ts: float = ts) -> float:
                return px(tx + value * ts)

            def my(value: float, ty: float = ty, ts: float = ts) -> float:
                return py(ty + value * ts)

            if name in ("svg", "g", "title", "desc", "defs"):
                continue
            if name in ("rect", "circle", "line", "path", "polygon", "polyline"):
                self._shape(name, element, mx, my, unit * ts)
            elif name == "text":
                self._text(element, mx, my, unit * ts)
            else:
                self.result.skipped[name] = self.result.skipped.get(name, 0) + 1
        self.stream.restore()
        return height_pt

    def _walk(
        self, element: ET.Element, state: tuple[float, float, float]
    ) -> Iterable[tuple[ET.Element, tuple[float, float, float]]]:
        """Yield every element with its composed transform.

        Args:
            element: The subtree root.
            state: The inherited ``(dx, dy, scale)``.

        Yields:
            ``(element, state)`` pairs, depth first.
        """
        tx, ty, ts = state
        dx, dy, ds = _transform(element.get("transform"))
        here = (tx + dx * ts, ty + dy * ts, ts * ds)
        yield element, here
        for child in element:
            yield from self._walk(child, here)

    def _set_paint(self, element: ET.Element) -> tuple[bool, bool]:
        """Apply fill and stroke colours.

        Args:
            element: The SVG element.

        Returns:
            ``(fill, stroke)`` -- whether each should be painted.
        """
        fill = _svg_colour(element.get("fill"))
        stroke = _svg_colour(element.get("stroke"))
        if element.get("fill") is None and _tag(element) not in ("line", "polyline"):
            fill = (0.0, 0.0, 0.0)
        if fill is not None:
            self.stream.set_fill_rgb(*fill)
        if stroke is not None:
            self.stream.set_stroke_rgb(*stroke)
            width = _number(element.get("stroke-width"), 0.0)
            if width:
                self.stream.set_line_width(max(0.05, width * MM_TO_PT))
        return fill is not None, stroke is not None

    def _paint_ops(self, fill: bool, stroke: bool, even_odd: bool = False) -> None:
        """Emit the painting operator for the current path.

        Args:
            fill: Whether to fill.
            stroke: Whether to stroke.
            even_odd: Whether to fill with the even-odd rule.
        """
        if fill and stroke:
            self.stream.fill_stroke(even_odd=even_odd)
        elif fill:
            self.stream.fill(even_odd=even_odd)
        elif stroke:
            self.stream.stroke()
        else:
            self.stream.end_path()

    def _shape(self, name: str, element: ET.Element, mx: Any, my: Any, unit: float) -> None:
        """Draw one geometric element.

        Args:
            name: The SVG tag.
            element: The element.
            mx: Maps an SVG x to a page x.
            my: Maps an SVG y to a page y.
            unit: Points per SVG user unit at this depth.
        """
        self.stream.save()
        fill, stroke = self._set_paint(element)
        if name == "rect":
            x0, y0 = _number(element.get("x")), _number(element.get("y"))
            width, height = _number(element.get("width")), _number(element.get("height"))
            if width > 0 and height > 0:
                self.stream.rect(mx(x0), my(y0 + height), width * unit, height * unit)
                self._paint_ops(fill, stroke)
                self.result.drawn += 1
            else:
                self.stream.end_path()
        elif name == "circle":
            cx, cy = _number(element.get("cx")), _number(element.get("cy"))
            radius = _number(element.get("r"))
            if radius > 0:
                self._circle(mx(cx), my(cy), radius * unit)
                self._paint_ops(fill, stroke)
                self.result.drawn += 1
            else:
                self.stream.end_path()
        elif name == "line":
            self.stream.move_to(mx(_number(element.get("x1"))), my(_number(element.get("y1"))))
            self.stream.line_to(mx(_number(element.get("x2"))), my(_number(element.get("y2"))))
            self._paint_ops(False, True)
            self.result.drawn += 1
        elif name in ("polygon", "polyline"):
            numbers = [float(item) for item in _NUMBER.findall(element.get("points") or "")]
            if len(numbers) >= 4:
                self.stream.move_to(mx(numbers[0]), my(numbers[1]))
                for index in range(2, len(numbers) - 1, 2):
                    self.stream.line_to(mx(numbers[index]), my(numbers[index + 1]))
                if name == "polygon":
                    self.stream.close_path()
                self._paint_ops(fill and name == "polygon", stroke)
                self.result.drawn += 1
            else:
                self.stream.end_path()
        else:
            drawn = False
            for subpath in _subpaths(element.get("d") or ""):
                for segment in subpath:
                    if segment[0] == "M":
                        self.stream.move_to(mx(segment[1]), my(segment[2]))
                    elif segment[0] == "L":
                        self.stream.line_to(mx(segment[1]), my(segment[2]))
                    elif segment[0] == "C":
                        self.stream.curve_to(
                            mx(segment[1]),
                            my(segment[2]),
                            mx(segment[3]),
                            my(segment[4]),
                            mx(segment[5]),
                            my(segment[6]),
                        )
                    elif segment[0] == "Z":
                        self.stream.close_path()
                drawn = True
            if drawn:
                self._paint_ops(fill, stroke, element.get("fill-rule") == "evenodd")
                self.result.drawn += 1
            else:
                self.stream.end_path()
        self.stream.restore()

    def _circle(self, cx: float, cy: float, radius: float) -> None:
        """Approximate a circle with four cubic curves.

        Args:
            cx: Centre x, in points.
            cy: Centre y, in points.
            radius: Radius, in points.
        """
        k = radius * 0.5522847498
        self.stream.move_to(cx + radius, cy)
        self.stream.curve_to(cx + radius, cy + k, cx + k, cy + radius, cx, cy + radius)
        self.stream.curve_to(cx - k, cy + radius, cx - radius, cy + k, cx - radius, cy)
        self.stream.curve_to(cx - radius, cy - k, cx - k, cy - radius, cx, cy - radius)
        self.stream.curve_to(cx + k, cy - radius, cx + radius, cy - k, cx + radius, cy)
        self.stream.close_path()

    def _text(self, element: ET.Element, mx: Any, my: Any, unit: float) -> None:
        """Draw one ``text`` element with the embedded chess face.

        Args:
            element: The element.
            mx: Maps an SVG x to a page x.
            my: Maps an SVG y to a page y.
            unit: Points per SVG user unit.
        """
        content = (element.text or "").strip()
        if not content or self.chess_font is None:
            if content:
                self.result.skipped["text"] = self.result.skipped.get("text", 0) + 1
            return
        size = _number(element.get("font-size"), 3.0) * unit
        colour = _svg_colour(element.get("fill")) or (0.0, 0.0, 0.0)
        usable = "".join(
            char for char in content if self.chess_font.has_char(char)
        )
        if not usable:
            self.result.skipped["glyph"] = self.result.skipped.get("glyph", 0) + len(content)
            return
        width = self.chess_font.text_width(usable, size)
        anchor = element.get("text-anchor") or "start"
        offset = {"middle": -width / 2, "end": -width}.get(anchor, 0.0)
        self.stream.save()
        self.stream.set_fill_rgb(*colour)
        self.stream.begin_text()
        self.stream.set_font(self.chess_font.resource_name, size)
        self.stream.text_position(
            mx(_number(element.get("x"))) + offset, my(_number(element.get("y")))
        )
        self.stream.show(self.chess_font.encode(usable))
        self.stream.end_text()
        self.stream.restore()
        self.result.text_runs += 1


# --------------------------------------------------------------------------- #
# The exporter
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class _Run:
    """One measured piece of text waiting to be placed.

    Attributes:
        text: The characters.
        font: Which embedded face draws them.
        size: Type size in points.
        colour: Ink, as an RGB triple.
        rise: Baseline shift in points.
        underline: Whether to rule under the run.
    """

    text: str
    font: EmbeddedFont
    size: float
    colour: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rise: float = 0.0
    underline: bool = False


class PdfExporter(Exporter):
    """Writes a PDF: subset fonts, vector diagrams, outline, XMP."""

    format_name: ClassVar[str] = "pdf"
    profile: ClassVar[Any] = PDF_PROFILE
    suffix: ClassVar[str] = ".pdf"

    def write(
        self, document: Document, destination: Path, context: ExportContext
    ) -> ExportResult:
        """Write the file.

        Args:
            document: The IR to write.
            destination: The ``.pdf`` file.
            context: The export context.

        Returns:
            The result.

        Raises:
            ExportError: No usable text font, or the writer refused the file.
        """
        options = context.options
        self.context = context
        self.document = document
        self.diagrams = DiagramRenderer(context)
        self.embedder = FontEmbedder()
        self._load_fonts(context)

        self.width = getattr(options, "page_width_mm", 148.0) * MM_TO_PT
        self.height = getattr(options, "page_height_mm", 210.0) * MM_TO_PT
        self.margin = getattr(options, "margin_mm", 16.0) * MM_TO_PT
        self.body_size = getattr(options, "body_size_pt", 10.5)
        self.leading = getattr(options, "leading", 1.32)

        self.pages: list[tuple[ContentStream, list[Any]]] = []
        self.outline: list[tuple[int, str, int, float]] = []
        self.skipped: dict[str, int] = {}
        self.vector_shapes = 0
        self._new_page()

        for block in document.body:
            self.block(block)

        doc = PdfDocument()
        fonts = self.embedder.finalise(doc)
        for stream, page_annotations in self.pages:
            doc.add_page(
                PdfPage(
                    width=self.width,
                    height=self.height,
                    content=stream.to_bytes(strict=False),
                    resources={"Font": fonts},
                    annotations=page_annotations,
                )
            )
        doc.set_metadata(self._metadata(document, context))
        doc.set_outline(self._outline_entries(context))
        try:
            doc.write(destination)
        except PdfWriteError as error:
            raise ExportError(f"O PDF nao pode ser montado: {error}") from error

        artifacts = [destination]
        if context.options.embed_ir:
            sidecar = destination.with_suffix("")
            sidecar = sidecar.with_name(sidecar.name + SIDECAR_SUFFIX)
            sidecar.write_text(
                json.dumps(document_to_payload(document), ensure_ascii=False),
                encoding="utf-8",
            )
            artifacts.append(sidecar)
            context.note(
                f"O IR foi gravado em {sidecar.name}. Um PDF nao carrega a arvore do "
                "documento; sem esse arquivo o export e definitivo."
            )
        context.count("bytes", destination.stat().st_size)
        context.count("vector_shapes", self.vector_shapes)
        context.count("pages", len(self.pages))
        if self.skipped:
            listed = ", ".join(f"{name} ({count})" for name, count in sorted(self.skipped.items()))
            context.note(
                f"Elementos SVG fora do vocabulario do pintor vetorial foram ignorados: "
                f"{listed}."
            )
        context.note(
            f"{len(fonts)} fonte(s) embutida(s) em subconjunto; "
            "nenhum diagrama foi rasterizado."
        )
        return context.finish(destination, artifacts)

    # -- fonts -------------------------------------------------------------

    def _load_fonts(self, context: ExportContext) -> None:
        """Load the faces the document needs, subset on use.

        Args:
            context: The export context.

        Raises:
            ExportError: No text font could be found at all.
        """
        self.faces: dict[str, EmbeddedFont] = {}
        for key, candidates in _FALLBACK_FILES.items():
            path = _find_font(candidates)
            if path is None:
                continue
            try:
                self.faces[key] = self.embedder.load(path)
            except Exception as error:  # noqa: BLE001 - a bad face is not fatal
                context.note(f"A fonte {path.name} nao pode ser lida: {error}")
        if "roman" not in self.faces:
            raise ExportError(
                "Nenhuma fonte de texto encontrada nesta maquina; o PDF precisa de "
                "pelo menos uma face TrueType para embutir."
            )
        self.chess_face: EmbeddedFont | None = None
        try:
            from caissa.typeset import fonts as chess_fonts

            specs = chess_fonts.available_specs()
            wanted = (self.document.settings.chess_font_family or "").lower()
            spec = next(
                (item for item in specs if wanted and wanted in item.key.lower()),
                specs[0] if specs else None,
            )
            if spec is not None:
                path = chess_fonts.find_font_file(spec)
                if path is not None:
                    self.chess_face = self.embedder.load(path)
        except Exception as error:  # noqa: BLE001 - a missing chess face is reported
            context.note(f"Nenhuma fonte de xadrez pode ser embutida: {error}")

    def _face(self, props: RunProps | None) -> EmbeddedFont:
        """Choose the face a run should be drawn with.

        Args:
            props: The run properties.

        Returns:
            The embedded face.
        """
        bold = bool(props and props.font_weight and props.font_weight >= 600)
        italic = bool(props and props.italic)
        key = (
            "bolditalic"
            if bold and italic
            else "bold"
            if bold
            else "italic"
            if italic
            else "roman"
        )
        return self.faces.get(key) or self.faces["roman"]

    # -- pages -------------------------------------------------------------

    def _new_page(self) -> None:
        """Start a new page and reset the galley cursor."""
        stream = ContentStream()
        self.pages.append((stream, []))
        self.stream = stream
        self.annotations = self.pages[-1][1]
        self.cursor = self.height - self.margin

    def _space(self, amount: float) -> None:
        """Advance down the galley, breaking the page when it is full.

        Args:
            amount: How far down to move, in points.
        """
        if self.cursor - amount < self.margin:
            self._new_page()
            return
        self.cursor -= amount

    @property
    def text_width(self) -> float:
        """Usable line width in points."""
        return self.width - 2 * self.margin

    # -- blocks ------------------------------------------------------------

    def block(self, node: Block) -> None:
        """Lay one block onto the galley.

        Args:
            node: The block.
        """
        with self.context.at(f"{tag_of(node)}/"):
            self.context.count("nodes")
            self.context.audit_node_fields(node)
            handler = getattr(self, f"_block_{tag_of(node)}", None)
            if handler is None:
                self.context.audit_node(node)
                return
            props = getattr(node, "props", None)
            if isinstance(props, ParagraphProps):
                self.context.audit_paragraph_props(props, node=node)
            handler(node)

    def blocks(self, nodes: Sequence[Block]) -> None:
        """Lay a sequence of blocks.

        Args:
            nodes: The blocks.
        """
        for node in nodes:
            if node is not None:
                self.block(node)

    def _block_heading(self, node: Heading) -> None:
        size = self.body_size * (1.9, 1.5, 1.25, 1.12, 1.05, 1.0)[min(node.level, 6) - 1]
        self._space(size * 0.9)
        if self.cursor - size * 3 < self.margin:
            self._new_page()
        depth = getattr(self.context.options, "outline_depth", 3)
        if node.level <= depth:
            from caissa.export.text import inline_plain_text

            title = inline_plain_text(node.content, self.document) or "Sem titulo"
            self.outline.append((node.level, title, len(self.pages) - 1, self.cursor))
        runs = self._runs(node.content, RunProps(font_weight=700, font_size=Measure.points(size)))
        self._place(runs, Alignment.LEFT, size * self.leading)
        self._space(size * 0.35)

    def _block_paragraph(self, node: Paragraph) -> None:
        runs = self._runs(node.content, RunProps())
        alignment = node.props.alignment or Alignment.JUSTIFY
        self._place(runs, alignment, self.body_size * self.leading)
        self._space(self.body_size * 0.28)

    def _block_quote(self, node: Quote) -> None:
        self.margin += 14
        self.blocks(node.content)
        if node.attribution:
            self._place(
                self._runs(node.attribution, RunProps(italic=True)),
                Alignment.RIGHT,
                self.body_size * self.leading,
            )
        self.margin -= 14

    def _block_callout(self, node: Callout) -> None:
        self.margin += 10
        if node.title:
            self._place(
                self._runs(node.title, RunProps(font_weight=700)),
                Alignment.LEFT,
                self.body_size * self.leading,
            )
        self.blocks(node.content)
        self.margin -= 10

    def _block_list_block(self, node: ListBlock) -> None:
        for index, item in enumerate(node.items, start=1):
            self.context.count("nodes")
            self.context.audit_node_fields(item)
            marker = f"{index}." if node.kind is ListKind.ORDERED else "\u2022"
            self._place(
                [_Run(marker + " ", self.faces["roman"], self.body_size)],
                Alignment.LEFT,
                self.body_size * self.leading,
            )
            self.margin += 12
            self.blocks(item.content)
            self.margin -= 12

    def _block_code_block(self, node: CodeBlock) -> None:
        face = self.faces.get("mono") or self.faces["roman"]
        for line in node.text.split("\n"):
            self._place(
                [_Run(line, face, self.body_size * 0.92)],
                Alignment.LEFT,
                self.body_size * self.leading,
            )
        self._space(self.body_size * 0.4)

    def _block_math_block(self, node: MathBlock) -> None:
        self.context.audit_feature("math", node=node, original="LaTeX")
        face = self.faces.get("mono") or self.faces["roman"]
        self._place(
            [_Run(node.latex, face, self.body_size)],
            Alignment.CENTER,
            self.body_size * self.leading,
        )

    def _block_table(self, node: Table) -> None:
        self.context.audit_feature("table_spans", node=node, original="tabela")
        columns = node.column_count or max((len(row.cells) for row in node.rows), default=1)
        column_width = self.text_width / max(1, columns)
        for row in node.rows:
            self.context.count("nodes")
            self.context.audit_node_fields(row)
            self._space(self.body_size * self.leading)
            for index, cell in enumerate(row.cells):
                self.context.count("nodes")
                self.context.audit_node_fields(cell)
                from caissa.export.text import inline_plain_text

                text = " ".join(
                    inline_plain_text(getattr(child, "content", ()), self.document)
                    for child in cell.content
                )
                self._draw_line(
                    [
                        _Run(
                            text[:60],
                            self.faces["roman"],
                            self.body_size * 0.9,
                        )
                    ],
                    self.margin + index * column_width,
                    self.cursor,
                    0.0,
                )
        self._space(self.body_size * 0.6)

    def _block_figure(self, node: Figure) -> None:
        self.blocks(node.content)
        if node.caption:
            self._place(
                self._runs(node.caption, RunProps(font_size=Measure.points(self.body_size * 0.86))),
                Alignment.CENTER,
                self.body_size * self.leading,
            )

    def _block_diagram(self, node: Diagram) -> None:
        rendered = self.diagrams.svg(node)
        width = min(self.text_width, rendered.width_mm * MM_TO_PT)
        height = width * rendered.aspect
        if self.cursor - height - self.body_size * 2 < self.margin:
            self._new_page()
        self._space(self.body_size * 0.5)
        painter = _SvgPainter(self.stream, self.chess_face)
        left = self.margin + (self.text_width - width) / 2
        painter.paint(rendered.svg, left, self.cursor, width)
        self.vector_shapes += painter.result.drawn
        for name, count in painter.result.skipped.items():
            self.skipped[name] = self.skipped.get(name, 0) + count
        self.context.count("diagrams")
        self.cursor -= height
        if node.caption or node.number is not None:
            label = f"Diagrama {node.number}" if node.number is not None else "Diagrama"
            runs = [_Run(label, self._face(RunProps(font_weight=700)), self.body_size * 0.86)]
            runs.extend(
                self._runs(
                    node.caption or (),
                    RunProps(font_size=Measure.points(self.body_size * 0.86)),
                )
            )
            self._space(self.body_size * 0.8)
            self._place(runs, Alignment.CENTER, self.body_size * self.leading)
        self._space(self.body_size * 0.6)

    def _block_image_block(self, node: ImageBlock) -> None:
        self.context.audit_feature("images", node=node, original=node.resource)

    def _block_game_score(self, node: GameScore) -> None:
        self.context.count("games")
        text = game_to_pgn(node, include_headers=False)
        self._place(
            [_Run(text, self.faces["roman"], self.body_size)],
            Alignment.JUSTIFY,
            self.body_size * self.leading,
        )
        self._space(self.body_size * 0.4)

    def _block_footnote(self, node: Footnote) -> None:
        self.context.audit_feature("footnotes", node=node, original="nota de rodape")
        self._place(
            self._runs(
                tuple(
                    inline
                    for child in node.content
                    for inline in getattr(child, "content", ())
                ),
                RunProps(font_size=Measure.points(self.body_size * 0.82)),
            ),
            Alignment.LEFT,
            self.body_size * self.leading * 0.9,
        )

    def _block_endnote(self, node: Endnote) -> None:
        self._block_footnote(node)  # type: ignore[arg-type]

    def _block_page_break(self, node: PageBreak) -> None:
        self._new_page()

    def _block_section_break(self, node: SectionBreak) -> None:
        for feature, present in (
            ("columns", node.columns is not None),
            ("page_geometry", node.geometry is not None),
            ("headers_footers", bool(node.header_text or node.footer_text)),
        ):
            if present:
                self.context.audit_feature(feature, node=node, original=node.kind.value)
        self._new_page()

    def _block_thematic_break(self, node: ThematicBreak) -> None:
        self._space(self.body_size)
        self.stream.save()
        self.stream.set_stroke_gray(0.5)
        self.stream.set_line_width(0.5)
        self.stream.move_to(self.margin + self.text_width * 0.35, self.cursor)
        self.stream.line_to(self.margin + self.text_width * 0.65, self.cursor)
        self.stream.stroke()
        self.stream.restore()
        self.vector_shapes += 1
        self._space(self.body_size)

    def _block_group(self, node: Group) -> None:
        if node.title:
            self._place(
                self._runs(node.title, RunProps(font_weight=700)),
                Alignment.LEFT,
                self.body_size * self.leading,
            )
        if node.columns:
            self.context.audit_feature("columns", node=node, original=str(node.columns))
        self.blocks(node.content)

    def _block_table_of_contents(self, node: TableOfContents) -> None:
        self.context.audit_feature("toc_field", node=node, original="sumario")

    def _block_raw_passthrough(self, node: RawPassthrough) -> None:
        self.context.audit_feature("raw_passthrough", node=node, original=node.format)

    # -- inline shaping ----------------------------------------------------

    def _runs(self, nodes: Sequence[Inline], inherited: RunProps) -> list[_Run]:
        """Flatten inline content into measured runs.

        Args:
            nodes: The inlines.
            inherited: Formatting from the enclosing block.

        Returns:
            The runs, in reading order.
        """
        runs: list[_Run] = []
        for node in nodes:
            runs.extend(self._inline(node, inherited))
        return runs

    def _inline(self, node: Inline, inherited: RunProps) -> list[_Run]:
        """Flatten one inline.

        Args:
            node: The inline.
            inherited: Formatting from further out.

        Returns:
            The runs it produces.
        """
        from dataclasses import replace

        self.context.count("nodes")
        self.context.audit_node_fields(node)
        props = getattr(node, "props", None)
        if isinstance(props, RunProps):
            self.context.audit_run_props(props, node=node)
        tag = tag_of(node)
        merged = _merge(inherited, props if isinstance(props, RunProps) else None)

        if tag == "text":
            return [self._make_run(node.content, merged)]
        if tag in ("emphasis",):
            return self._runs(node.content, replace(merged, italic=True))
        if tag in ("strong",):
            return self._runs(node.content, replace(merged, font_weight=700))
        if tag == "underline":
            runs = self._runs(node.content, merged)
            for run in runs:
                run.underline = True
            return runs
        if tag in ("strike", "small_caps", "span"):
            return self._runs(node.content, merged)
        if tag in ("superscript", "subscript"):
            base = (
                merged.font_size.to_points()
                if merged.font_size is not None and merged.font_size.is_absolute
                else self.body_size
            )
            size = base * 0.7
            rise = size * (0.45 if tag == "superscript" else -0.2)
            runs = self._runs(node.content, replace(merged, font_size=Measure.points(size)))
            for run in runs:
                run.rise = rise
            return runs
        if tag == "link":
            return self._runs(node.content, merged)
        if tag == "move":
            return [self._make_run(render_move(node, self.document), merged)]
        if tag == "piece_glyph":
            return [self._make_run(figurine_char(node.piece.value, node.figurine_set), merged)]
        if tag == "nag_symbol":
            return [self._make_run(nag_symbol(node.nag), merged)]
        if tag == "note_ref":
            return [self._make_run(node.marker or node.ref, merged)]
        if tag == "math_inline":
            self.context.audit_feature("math", node=node, original="LaTeX")
            return [self._make_run(node.latex, merged)]
        if tag == "inline_diagram":
            self.context.audit_feature(
                "inline_diagram", node=node, original="diagrama em linha"
            )
            return [self._make_run(" [diagrama] ", merged)]
        if tag == "image_inline":
            self.context.audit_feature("images", node=node, original=node.resource)
            return []
        if tag in ("line_break",):
            return [self._make_run("\n", merged)]
        if tag == "non_breaking_space":
            return [self._make_run("\u00a0", merged)]
        if tag in ("space", "tab"):
            return [self._make_run(" ", merged)]
        if tag in ("anchor", "index_entry", "raw_inline"):
            return []
        self.context.audit_node(node)
        return []

    def _make_run(self, text: str, props: RunProps) -> _Run:
        """Build one measured run.

        Args:
            text: The characters.
            props: The resolved run properties.

        Returns:
            The run.
        """
        size = (
            props.font_size.to_points()
            if props.font_size is not None and props.font_size.is_absolute
            else self.body_size
        )
        size = size if 3.0 <= size <= 96.0 else self.body_size
        colour = (0.0, 0.0, 0.0)
        if props.color is not None and props.color.space not in (
            ColorSpace.AUTO,
            ColorSpace.NONE,
        ):
            colour = props.color.to_rgb_tuple()
        return _Run(
            text=text,
            font=self._face(props),
            size=size,
            colour=colour,
            underline=props.underline is not None and props.underline.value != "none",
        )

    # -- line breaking -----------------------------------------------------

    def _place(self, runs: Sequence[_Run], alignment: Alignment, line_height: float) -> None:
        """Break runs into lines and draw them.

        Args:
            runs: The measured runs.
            alignment: How to align each line.
            line_height: Baseline-to-baseline distance in points.
        """
        words = _split_words(runs)
        if not words:
            return
        line: list[_Run] = []
        width = 0.0
        for word in words:
            if word.text == "\n":
                self._emit(line, alignment, line_height, last=True)
                line, width = [], 0.0
                continue
            advance = _measure(word)
            if line and width + advance > self.text_width:
                self._emit(line, alignment, line_height, last=False)
                line, width = [], 0.0
                if word.text.strip() == "":
                    continue
            line.append(word)
            width += advance
        self._emit(line, alignment, line_height, last=True)

    def _emit(
        self, line: list[_Run], alignment: Alignment, line_height: float, *, last: bool
    ) -> None:
        """Draw one assembled line.

        Args:
            line: Its runs.
            alignment: How to align it.
            line_height: Baseline-to-baseline distance.
            last: Whether this is a paragraph's final line, which is never
                justified.
        """
        while line and line[-1].text.strip() == "":
            line.pop()
        if not line:
            return
        self._space(line_height)
        width = sum(_measure(run) for run in line)
        extra = 0.0
        x = self.margin
        if alignment is Alignment.CENTER:
            x += (self.text_width - width) / 2
        elif alignment in (Alignment.RIGHT, Alignment.END):
            x += self.text_width - width
        elif alignment in (Alignment.JUSTIFY, Alignment.DISTRIBUTE) and not last:
            gaps = sum(1 for run in line if run.text == " ")
            if gaps:
                extra = (self.text_width - width) / gaps
        self._draw_line(line, x, self.cursor, extra)

    def _draw_line(
        self, line: Sequence[_Run], x: float, y: float, extra: float
    ) -> None:
        """Paint one line of runs at a position.

        Args:
            line: The runs.
            x: Left edge in points.
            y: Baseline in points from the page bottom.
            extra: Additional advance per space, for justification.
        """
        for run in line:
            if not run.text:
                continue
            usable = "".join(char for char in run.text if run.font.has_char(char))
            if not usable:
                continue
            self.stream.save()
            self.stream.set_fill_rgb(*run.colour)
            self.stream.begin_text()
            self.stream.set_font(run.font.resource_name, run.size)
            if run.rise:
                self.stream.set_rise(run.rise)
            self.stream.text_position(x, y)
            self.stream.show(run.font.encode(usable))
            self.stream.end_text()
            self.stream.restore()
            advance = run.font.text_width(usable, run.size)
            if run.underline:
                self.stream.save()
                self.stream.set_stroke_rgb(*run.colour)
                self.stream.set_line_width(max(0.3, run.size * 0.04))
                self.stream.move_to(x, y - run.size * 0.12)
                self.stream.line_to(x + advance, y - run.size * 0.12)
                self.stream.stroke()
                self.stream.restore()
            x += advance + (extra if run.text == " " else 0.0)

    # -- finishing ---------------------------------------------------------

    def _metadata(self, document: Document, context: ExportContext) -> PdfMetadata:
        """Build the document metadata, for both DocInfo and XMP.

        Args:
            document: The IR.
            context: The export context.

        Returns:
            The metadata.
        """
        meta = document.metadata
        now = datetime.now(UTC)
        return PdfMetadata(
            title=meta.title,
            author=", ".join(person.name for person in meta.contributors) or None,
            subject=meta.subtitle or meta.description,
            keywords=", ".join(meta.subjects) or None,
            creator="Caissa Studio",
            language=context.options.language or meta.language or "pt-BR",
            created=now,
            modified=now,
            pdf_a=bool(getattr(context.options, "pdf_a", False)),
        )

    def _outline_entries(self, context: ExportContext) -> tuple[OutlineEntry, ...]:
        """Build the bookmark tree from the headings that were laid out.

        Args:
            context: The export context.

        Returns:
            The top-level entries, nested by heading level.
        """
        roots: list[OutlineEntry] = []
        stack: list[tuple[int, list[OutlineEntry]]] = [(0, roots)]
        for level, title, page, top in self.outline:
            children: list[OutlineEntry] = []
            entry = OutlineEntry(title=title, page_index=page, top=top, children=())
            while stack and stack[-1][0] >= level:
                stack.pop()
            target = stack[-1][1] if stack else roots
            target.append(entry)
            stack.append((level, children))
            self._pending = children
        return tuple(_freeze(roots))


def _freeze(entries: Sequence[OutlineEntry]) -> list[OutlineEntry]:
    """Return the entries with their children made immutable.

    Args:
        entries: The mutable tree.

    Returns:
        The frozen entries.
    """
    return [
        OutlineEntry(
            title=entry.title,
            page_index=entry.page_index,
            top=entry.top,
            children=tuple(_freeze(list(entry.children))),
        )
        for entry in entries
    ]


def _merge(base: RunProps, extra: RunProps | None) -> RunProps:
    """Overlay run properties.

    Args:
        base: The inherited record.
        extra: The nearer record.

    Returns:
        The merged record.
    """
    if extra is None:
        return base
    from dataclasses import fields as dataclass_fields
    from dataclasses import replace

    changes = {
        descriptor.name: getattr(extra, descriptor.name)
        for descriptor in dataclass_fields(extra)
        if getattr(extra, descriptor.name) not in (None, (), "")
    }
    return replace(base, **changes)


def _split_words(runs: Sequence[_Run]) -> list[_Run]:
    """Split runs at word boundaries so lines can break between words.

    Args:
        runs: The measured runs.

    Returns:
        One run per word and one per space, in order.
    """
    from dataclasses import replace

    words: list[_Run] = []
    for run in runs:
        if run.text == "\n":
            words.append(run)
            continue
        for piece in re.split(r"(\s)", run.text):
            if not piece:
                continue
            words.append(replace(run, text=" " if piece.isspace() else piece))
    return words


def _measure(run: _Run) -> float:
    """Measure one run with its own face.

    Args:
        run: The run.

    Returns:
        Its advance width in points.
    """
    usable = "".join(char for char in run.text if run.font.has_char(char))
    return run.font.text_width(usable, run.size) if usable else 0.0


def _find_font(candidates: Sequence[str]) -> Path | None:
    """Find the first of several font files on this machine.

    Args:
        candidates: File names to look for.

    Returns:
        The path, or ``None`` when none is installed.
    """
    for directory in _FONT_SEARCH:
        if not directory.exists():
            continue
        for name in candidates:
            path = directory / name
            if path.exists():
                return path
        lowered = {item.name.lower(): item for item in directory.rglob("*.ttf")}
        for name in candidates:
            found = lowered.get(name.lower())
            if found is not None:
                return found
    return None


def read_pdf(path: Path | str) -> Document:
    """Read a PDF written by :class:`PdfExporter` back into the IR.

    This reads the ``.caissa.json`` sidecar written beside the file, not the
    page content. See the module docstring: a PDF is ink, and
    :mod:`caissa.export.fidelity` labels any number obtained this way
    ``method="sidecar"``.

    Args:
        path: The ``.pdf`` file.

    Returns:
        The document.

    Raises:
        ValueError: There is no sidecar beside the file.
    """
    target = Path(path)
    sidecar = target.with_suffix("")
    sidecar = sidecar.with_name(sidecar.name + SIDECAR_SUFFIX)
    if not sidecar.exists():
        raise ValueError(
            f"Nenhum IR encontrado em {sidecar.name}. Um PDF nao carrega a arvore do "
            "documento; exporte com embed_ir=True para poder reabrir."
        )
    document, _migrations = document_from_payload(
        json.loads(sidecar.read_text(encoding="utf-8"))
    )
    return document
