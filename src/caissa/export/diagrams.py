"""One diagram renderer for five formats.

Every exporter needs the same picture of the same position, and the SPEC's whole
argument for the Document IR collapses if the EPUB and the PDF disagree about
what the board looks like. So no exporter draws a board. They all call
:meth:`DiagramRenderer.svg`, which resolves the IR's presentation model against
the document stylesheet, hands the result to
:func:`caissa.typeset.board_svg.render_svg` -- the canonical renderer that F7
owns -- and caches the answer.

The cache is not an optimisation detail. A 300-page opening manual has hundreds
of diagrams and many of them repeat (the same tabiya opens six chapters), and
loading a chess font plus tracing 32 glyph outlines is not free. Keying on the
resolved style rather than the node means two nodes that *look* the same share
one render, which is also what makes the byte-identical-output guarantee in
``board_svg`` useful to us.

What this module owns, and what it refuses to own
-------------------------------------------------
It owns the *translation*: IR :class:`~caissa.core.model.diagram.DiagramStyle`
and :class:`~caissa.core.model.marks.Mark` into the renderer's own vocabulary,
plus the degradation warnings for the places where the two vocabularies do not
line up (the IR can ask for a cross on a square; the renderer draws highlights,
circles and arrows). It does not own a single line of drawing code. When a
diagram looks wrong, the bug is in ``typeset``, and this module's job is to have
made that obvious.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from caissa.core.model import (
    Color,
    Diagram,
    DiagramStyle,
    DiagramStyleDef,
    InlineDiagram,
    Mark,
    MarkKind,
    Measure,
    StyleSheet,
)
from caissa.export.base import ExportContext
from caissa.typeset import board_svg as bsvg

__all__ = [
    "DiagramRenderer",
    "RenderedDiagram",
    "diagram_alt_text",
    "resolve_diagram_style",
]

_MM_PER_PT = 25.4 / 72.0

_MIN_WIDTH_MM = 1.0
"""Below this a board is not small, it is invalid; see ``_style_for``."""

_FRAME_BY_BORDER_STYLE: Mapping[str, bsvg.FrameStyle] = {
    "none": bsvg.FrameStyle.NONE,
    "solid": bsvg.FrameStyle.HAIRLINE,
    "double": bsvg.FrameStyle.DOUBLE,
    "thick-thin": bsvg.FrameStyle.DOUBLE,
    "thin-thick": bsvg.FrameStyle.DOUBLE,
    "inset": bsvg.FrameStyle.INSET,
    "outset": bsvg.FrameStyle.INSET,
    "ridge": bsvg.FrameStyle.INSET,
    "groove": bsvg.FrameStyle.INSET,
}

_COORD_BY_PLACEMENT: Mapping[str, bsvg.CoordinateStyle] = {
    "none": bsvg.CoordinateStyle.NONE,
    "outside": bsvg.CoordinateStyle.OUTSIDE,
    "inside": bsvg.CoordinateStyle.INSIDE,
}

# Marks the IR can express that the canonical renderer has no primitive for. The value
# is what stands in, and the reason, both shown to the user.
_MARK_FALLBACK: Mapping[MarkKind, tuple[str, str]] = {
    MarkKind.CROSS: (
        "circulo",
        "O renderizador desenha destaque, circulo e seta; a cruz virou um circulo.",
    ),
    MarkKind.DOT: (
        "circulo",
        "O renderizador desenha destaque, circulo e seta; o ponto virou um circulo.",
    ),
    MarkKind.LABEL: (
        "destaque",
        "O renderizador nao escreve rotulos sobre casas; a casa foi apenas destacada e o "
        "texto entrou na descricao alternativa.",
    ),
}

_PIECE_NAMES: Mapping[str, str] = {
    "K": "Rei branco",
    "Q": "Dama branca",
    "R": "Torre branca",
    "B": "Bispo branco",
    "N": "Cavalo branco",
    "P": "Peao branco",
    "k": "Rei preto",
    "q": "Dama preta",
    "r": "Torre preta",
    "b": "Bispo preto",
    "n": "Cavalo preto",
    "p": "Peao preto",
}


def _to_mm(measure: Measure | None) -> float | None:
    """Convert an IR length to millimetres.

    Args:
        measure: The length, or ``None``.

    Returns:
        The length in millimetres, or ``None`` when it was unset or relative.
        Relative units are refused rather than guessed: a diagram sized in
        percent has no absolute answer until a page exists, and inventing one
        here would put a different-sized board in each format.
    """
    if measure is None:
        return None
    if not measure.is_absolute:
        return None
    return measure.to_points() * _MM_PER_PT


def _hex(color: Color | None) -> str | None:
    """Render a colour as ``#rrggbb`` for the SVG renderer.

    Args:
        color: The colour, or ``None``.

    Returns:
        The hexadecimal form, or ``None`` when unset or explicitly automatic.
    """
    if color is None or color.space.value in ("auto", "none"):
        return None
    return color.to_hex()


def resolve_diagram_style(stylesheet: StyleSheet, style: DiagramStyle | None) -> DiagramStyle:
    """Flatten a diagram style against the stylesheet's inheritance chain.

    ``DiagramStyle.name`` points at a :class:`DiagramStyleDef` in the sheet, which
    may itself be ``based_on`` another. Direct settings win over the named style,
    which wins over its parent, which wins over the sheet default -- the same
    three-level cascade :mod:`caissa.core.model.styles` applies to text.

    Args:
        stylesheet: The document's styles.
        style: The direct style on the node.

    Returns:
        A style with every field resolved as far as the sheet allows.
    """
    direct = style or DiagramStyle()
    names: list[str] = []
    seen: set[str] = set()
    current = direct.name or stylesheet.default_diagram_style
    while current and current not in seen:
        seen.add(current)
        names.append(current)
        definition: DiagramStyleDef | None = stylesheet.diagram_style(current)
        current = definition.based_on if definition else None

    merged = DiagramStyle()
    for name in reversed(names):
        definition = stylesheet.diagram_style(name)
        if definition is not None:
            merged = _merge_diagram_style(merged, definition.style)
    return _merge_diagram_style(merged, direct)


def _merge_diagram_style(base: DiagramStyle, override: DiagramStyle) -> DiagramStyle:
    """Overlay one diagram style on another.

    Args:
        base: The lower-precedence style.
        override: The higher-precedence style.

    Returns:
        The merged style; ``name`` is taken from ``override`` so the chain is not
        re-walked.
    """
    changes: dict[str, object] = {}
    for field_name in (
        "piece_set",
        "piece_font_family",
        "piece_scale",
        "theme",
        "coordinates",
        "size",
        "square_size",
        "border",
        "margin",
        "show_side_to_move",
        "side_to_move_placement",
        "caption_position",
        "shadow",
        "grid_lines",
        "keep_with_caption",
    ):
        value = getattr(override, field_name)
        if value is not None:
            changes[field_name] = value
    if not changes:
        return replace(base, name=override.name or base.name)
    return replace(base, name=override.name or base.name, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RenderedDiagram:
    """One diagram, drawn once and reusable by every format.

    Attributes:
        svg: The canonical SVG, in millimetre user units.
        width_mm: Intrinsic width, the measurement a page layout needs.
        height_mm: Intrinsic height.
        alt_text: Accessible description, in Brazilian Portuguese.
        fen: The position, for formats that carry it as data.
        orientation: Which side faces the reader.
    """

    svg: str
    width_mm: float
    height_mm: float
    alt_text: str
    fen: str
    orientation: str = "white"

    @property
    def aspect(self) -> float:
        """Height divided by width, for a format that scales by width alone."""
        return self.height_mm / self.width_mm if self.width_mm else 1.0


def diagram_alt_text(node: Diagram | InlineDiagram) -> str:
    """Build an accessible description of a position.

    EPUB requires one and tagged PDF requires one, and "diagrama de xadrez" is
    not a description. This names the stipulation when the node has one, then
    every piece and its square, so a screen-reader user gets the position rather
    than the fact that a position exists.

    Args:
        node: The diagram node.

    Returns:
        The description, in Brazilian Portuguese.
    """
    explicit = getattr(node, "alt_text", None)
    if explicit:
        return explicit

    fen = (node.fen or "").strip()
    placement = fen.split(" ")[0] if fen else ""
    parts: list[str] = []
    stipulation = getattr(node, "stipulation", None)
    if stipulation:
        parts.append(str(stipulation))

    pieces: list[str] = []
    rank = 8
    file_index = 0
    for char in placement:
        if char == "/":
            rank -= 1
            file_index = 0
        elif char.isdigit():
            file_index += int(char)
        else:
            name = _PIECE_NAMES.get(char)
            if name is not None and 0 <= file_index < 8 and 1 <= rank <= 8:
                pieces.append(f"{name} em {'abcdefgh'[file_index]}{rank}")
            file_index += 1

    side = "brancas" if _side_to_move(fen) == "w" else "pretas"
    head = "Diagrama de xadrez" if isinstance(node, Diagram) else "Diagrama de xadrez em miniatura"
    parts.append(f"{head}, jogam as {side}")
    if pieces:
        parts.append("; ".join(pieces))
    else:
        parts.append("tabuleiro vazio")
    return ". ".join(parts) + "."


def _side_to_move(fen: str) -> str:
    """Read the side to move out of a FEN.

    Args:
        fen: A full FEN or a bare placement field.

    Returns:
        ``"w"`` or ``"b"``; ``"w"`` when the field is missing.
    """
    fields = fen.strip().split()
    if len(fields) >= 2 and fields[1] in ("w", "b"):
        return fields[1]
    return "w"


class DiagramRenderer:
    """Renders IR diagrams to canonical SVG, once each.

    One renderer per export. It holds the cache and the export context, so every
    translation shortfall lands in the same degradation report as everything
    else.
    """

    __slots__ = ("_cache", "_context", "_default_width_mm", "_fonts")

    def __init__(self, context: ExportContext, *, default_width_mm: float = 46.0) -> None:
        """Create a renderer bound to one export.

        Args:
            context: The export context, for recording degradations.
            default_width_mm: Width used when neither the node nor the
                stylesheet names one. 46 mm is a two-column chess-book diagram;
                it is a starting point, not a house style.
        """
        self._context = context
        self._default_width_mm = default_width_mm
        self._cache: dict[tuple[object, ...], RenderedDiagram] = {}
        self._fonts: dict[str, object] = {}

    @property
    def font_families(self) -> tuple[str, ...]:
        """Chess font families actually used, for the font-embedding pass."""
        return tuple(sorted(self._fonts))

    def svg(self, node: Diagram | InlineDiagram) -> RenderedDiagram:
        """Render a diagram node.

        Args:
            node: The diagram or inline diagram to draw.

        Returns:
            The rendered diagram; identical inputs return the identical object.
        """
        style, width_mm = self._style_for(node)
        marks = tuple(self._marks_for(node))
        key = (
            node.fen,
            style.font,
            str(style.theme),
            round(style.width_mm, 4),
            style.orientation,
            style.coordinates.value,
            style.frame.value,
            style.side_to_move.value,
            style.grid,
            round(style.piece_scale, 4),
            style.background,
            _mark_key(marks),
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            svg_text = bsvg.render_svg(node.fen, style, marks=marks)
        except Exception as error:  # a bad FEN or a missing font must not kill an export
            self._context.audit_feature("vector_diagram", node=node, original=str(error))
            self._context.recorder.unsupported(
                prop="diagram",
                node=node,
                path=self._context.path,
                original=node.fen,
                detail=f"O renderizador recusou a posicao: {error}",
            )
            svg_text = _placeholder_svg(style.width_mm)

        layout_height = style.width_mm * _svg_aspect(svg_text)
        rendered = RenderedDiagram(
            svg=svg_text,
            width_mm=style.width_mm,
            height_mm=layout_height,
            alt_text=diagram_alt_text(node),
            fen=node.fen,
            orientation=style.orientation,
        )
        self._cache[key] = rendered
        self._fonts[style.font] = True
        self._context.count("diagrams")
        return rendered

    # -- translation -------------------------------------------------------

    def _style_for(self, node: Diagram | InlineDiagram) -> tuple[bsvg.DiagramStyle, float]:
        """Translate the IR presentation model into the renderer's own.

        Args:
            node: The diagram node.

        Returns:
            The renderer style and the width in millimetres.
        """
        sheet = self._context.stylesheet
        if isinstance(node, Diagram):
            ir_style = resolve_diagram_style(sheet, node.style)
            orientation = node.orientation.value
            show_stm = node.side_to_move_indicator
        else:
            named = DiagramStyle(name=node.style) if node.style else None
            ir_style = resolve_diagram_style(sheet, named)
            orientation = node.orientation.value
            show_stm = False
            if node.size is not None:
                ir_style = replace(ir_style, size=node.size)

        width_mm = (
            _to_mm(ir_style.size)
            or (_to_mm(ir_style.square_size) or 0.0) * 8 or None
            or self._default_width_mm
        )
        if width_mm <= _MIN_WIDTH_MM:
            # A board with no width is not a smaller board, it is a file no
            # reader will open: OOXML's drawing extent and SVG's viewBox both
            # refuse a non-positive size. The default stands in, and the report
            # names the measurement that could not be honoured.
            self._context.recorder.substituted(
                prop="diagram_size",
                node=node if isinstance(node, (Diagram, InlineDiagram)) else None,
                path=self._context.path,
                original=f"{width_mm:.4g} mm",
                replacement=f"{self._default_width_mm:.4g} mm",
                detail=(
                    "O estilo pediu um diagrama de largura nula ou negativa. Nenhum "
                    "formato aceita isso -- o Word recusa o arquivo e o SVG fica sem "
                    "viewBox -- entao a largura padrao foi usada."
                ),
            )
            width_mm = self._default_width_mm
        if ir_style.size is not None and _to_mm(ir_style.size) is None:
            self._context.degrade(
                self._context.profile.feature_support("vector_diagram"),
                prop="size",
                node=node,
                original=str(ir_style.size),
            )

        font = self._font_key(ir_style, node)
        theme = self._theme_for(ir_style, node)
        frame = self._frame_for(ir_style)
        coordinates = self._coordinates_for(ir_style, node)
        side_to_move = self._side_to_move_for(ir_style, show_stm)

        style = bsvg.DiagramStyle(
            font=font,
            theme=theme,
            width_mm=width_mm,
            orientation="black" if orientation == "black" else "white",
            coordinates=coordinates,
            frame=frame,
            side_to_move=side_to_move,
            grid=bool(ir_style.grid_lines),
            piece_scale=ir_style.piece_scale if ir_style.piece_scale is not None else 1.0,
            margin_mm=_to_mm(ir_style.margin) or 0.0,
            background=True,
        )
        if ir_style.shadow and frame is not bsvg.FrameStyle.SHADOWED:
            style = replace(style, frame=bsvg.FrameStyle.SHADOWED)
        return style, width_mm

    def _font_key(self, ir_style: DiagramStyle, node: object) -> str:
        """Choose the chess font family for a diagram.

        Args:
            ir_style: The resolved IR style.
            node: The node, for the degradation report.

        Returns:
            A family key the renderer knows.
        """
        requested = (
            ir_style.piece_set
            or ir_style.piece_font_family
            or self._context.document.settings.chess_font_family
        )
        if not requested:
            return "merida"
        key = str(requested).strip().lower().replace(" ", "")
        try:
            from caissa.typeset.fonts import get_spec

            get_spec(key)
        except Exception:
            self._context.recorder.substituted(
                prop="piece_set",
                node=node if isinstance(node, (Diagram, InlineDiagram)) else None,
                path=self._context.path,
                original=str(requested),
                replacement="merida",
                detail="A familia de pecas pedida nao esta registrada; foi usada a Merida.",
            )
            return "merida"
        return key

    def _theme_for(self, ir_style: DiagramStyle, node: object) -> str | bsvg.BoardTheme:
        """Translate the IR board theme into a renderer theme.

        The IR carries eleven independent colours; the renderer's theme carries
        those plus hatching and greyscale-safety flags it computes itself. Where
        the IR names no colours at all, the renderer's own named theme is used,
        which is the case that keeps a plain document looking like a book.

        Args:
            ir_style: The resolved IR style.
            node: The node, for the degradation report.

        Returns:
            A theme key or a fully built theme.
        """
        theme = ir_style.theme
        if theme is None:
            return "book"
        base = bsvg.get_theme("book")
        light = _hex(theme.light_square)
        dark = _hex(theme.dark_square)
        if (light is not None or dark is not None) and base.hatch:
            # A document that names its own square colours wants a tint, not the
            # reference hatch; keeping the hatch would repaint the author's choice.
            base = replace(base, hatch=False)
        built = replace(
            base,
            key="documento",
            label="Tema do documento",
            light=light or base.light,
            dark=dark or base.dark,
            frame=_hex(theme.border) or base.frame,
            grid=_hex(theme.grid_line) or base.grid,
            piece_body=_hex(theme.white_piece_fill) or base.piece_body,
            piece_ink=_hex(theme.black_piece_fill) or base.piece_ink,
            page=_hex(theme.background) or base.page,
            highlight=_hex(theme.highlight) or base.highlight,
            arrow=_hex(theme.arrow) or base.arrow,
        )
        if theme.white_piece_stroke is not None or theme.black_piece_stroke is not None:
            self._context.recorder.approximated(
                prop="piece_stroke",
                node=node if isinstance(node, (Diagram, InlineDiagram)) else None,
                path=self._context.path,
                original="contorno de peca proprio",
                replacement="camada de tinta do tema",
                detail=(
                    "O renderizador usa duas camadas -- corpo e tinta -- em vez de "
                    "preenchimento e contorno separados por cor de peca."
                ),
            )
        return built

    def _frame_for(self, ir_style: DiagramStyle) -> bsvg.FrameStyle:
        """Translate the IR border into a renderer frame style.

        Args:
            ir_style: The resolved IR style.

        Returns:
            The frame style.
        """
        border = ir_style.border
        if border is None:
            return bsvg.FrameStyle.HAIRLINE
        return _FRAME_BY_BORDER_STYLE.get(border.style.value, bsvg.FrameStyle.HAIRLINE)

    def _coordinates_for(self, ir_style: DiagramStyle, node: object) -> bsvg.CoordinateStyle:
        """Translate the IR coordinate settings into a renderer coordinate style.

        Args:
            ir_style: The resolved IR style.
            node: The node, for the degradation report.

        Returns:
            The coordinate style.
        """
        coords = ir_style.coordinates
        if coords is None:
            return bsvg.CoordinateStyle.OUTSIDE
        if not coords.files and not coords.ranks:
            return bsvg.CoordinateStyle.NONE
        if coords.files != coords.ranks:
            self._context.recorder.approximated(
                prop="coordinates",
                node=node if isinstance(node, (Diagram, InlineDiagram)) else None,
                path=self._context.path,
                original="apenas um dos eixos rotulado",
                replacement="ambos os eixos",
                detail="O renderizador desenha os dois eixos ou nenhum.",
            )
        if coords.both_sides:
            self._context.recorder.approximated(
                prop="coordinates",
                node=node if isinstance(node, (Diagram, InlineDiagram)) else None,
                path=self._context.path,
                original="rotulos nos quatro lados",
                replacement="rotulos em dois lados",
                detail="O renderizador rotula dois lados do tabuleiro.",
            )
        return _COORD_BY_PLACEMENT.get(coords.placement.value, bsvg.CoordinateStyle.OUTSIDE)

    def _side_to_move_for(self, ir_style: DiagramStyle, show: bool) -> bsvg.SideToMove:
        """Choose the side-to-move indicator.

        Args:
            ir_style: The resolved IR style.
            show: Whether the node itself asks for the indicator.

        Returns:
            The indicator style.
        """
        wants = show or bool(ir_style.show_side_to_move)
        if not wants:
            return bsvg.SideToMove.NONE
        placement = ir_style.side_to_move_placement
        if placement is not None and placement.value == "inside":
            return bsvg.SideToMove.DOT
        return bsvg.SideToMove.SQUARE

    def _marks_for(self, node: Diagram | InlineDiagram) -> Iterable[bsvg.Mark]:
        """Translate IR board marks into renderer marks.

        Args:
            node: The diagram node.

        Yields:
            Renderer marks, in the IR's own paint order.
        """
        marks: Sequence[Mark] = node.marks
        for mark in sorted(marks, key=lambda m: m.layer):
            colour = _hex(mark.color)
            opacity = 1.0 if mark.opacity is None else float(mark.opacity)
            if mark.kind is MarkKind.ARROW:
                origin, target = mark.origin, mark.target
                if origin and target:
                    yield bsvg.Arrow(
                        source=origin, target=target, colour=colour, opacity=opacity
                    )
                continue
            if mark.kind is MarkKind.SQUARE:
                for square in mark.squares:
                    yield bsvg.SquareHighlight(
                        square=square,
                        colour=colour,
                        opacity=opacity,
                        style="fill" if mark.filled else "outline",
                    )
                continue
            if mark.kind is MarkKind.CIRCLE:
                for square in mark.squares:
                    yield bsvg.CircleMark(square=square, colour=colour)
                continue

            replacement, detail = _MARK_FALLBACK[mark.kind]
            self._context.recorder.substituted(
                prop="mark",
                node=node,
                path=self._context.path,
                original=mark.kind.value,
                replacement=replacement,
                detail=detail,
            )
            for square in mark.squares:
                if mark.kind is MarkKind.LABEL:
                    yield bsvg.SquareHighlight(square=square, colour=colour, opacity=opacity)
                else:
                    yield bsvg.CircleMark(square=square, colour=colour)

    # -- font embedding ----------------------------------------------------

    def used_characters(self) -> Mapping[str, set[str]]:
        """Return which characters each chess font must carry.

        A subset is only correct if it keeps every glyph that will be drawn, and
        the renderer draws pieces by their artwork characters, not by their FEN
        letters. Asking the font spec settles it rather than guessing.

        Returns:
            A mapping from family key to the characters to keep.
        """
        from caissa.typeset.fonts import get_spec

        wanted: dict[str, set[str]] = {}
        for family in self._fonts:
            try:
                spec = get_spec(family)
            except Exception:
                continue
            chars = {spec.artwork_char(piece) for piece in "KQRBNPkqrbnp"}
            wanted[family] = {char for char in chars if char}
        return wanted


def _mark_key(marks: Sequence[bsvg.Mark]) -> tuple[object, ...]:
    """Build a hashable cache key from a mark list.

    Args:
        marks: The renderer marks.

    Returns:
        A tuple that distinguishes any two different mark lists.
    """
    key: list[object] = []
    for mark in marks:
        if isinstance(mark, bsvg.Arrow):
            key.append(("a", mark.source, mark.target, mark.colour, mark.opacity))
        elif isinstance(mark, bsvg.SquareHighlight):
            key.append(("h", mark.square, mark.colour, mark.opacity, mark.style))
        elif isinstance(mark, bsvg.CircleMark):
            key.append(("c", mark.square, mark.colour))
    return tuple(key)


def _svg_aspect(svg: str) -> float:
    """Read height/width out of an SVG's ``viewBox``.

    Args:
        svg: The SVG text.

    Returns:
        The aspect ratio, defaulting to ``1.0`` when the header is unreadable.
    """
    start = svg.find('viewBox="')
    if start < 0:
        return 1.0
    end = svg.find('"', start + 9)
    parts = svg[start + 9 : end].split()
    if len(parts) != 4:
        return 1.0
    try:
        width = float(parts[2])
        height = float(parts[3])
    except ValueError:
        return 1.0
    return height / width if width else 1.0


def _placeholder_svg(width_mm: float) -> str:
    """Build a visible placeholder for a position that could not be drawn.

    A silently missing diagram is the worst possible outcome: the reader does
    not know something is gone. A box that says so is honest, and the
    degradation report says why.

    Args:
        width_mm: Width of the box in millimetres.

    Returns:
        The SVG.
    """
    height = width_mm
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:g}mm" '
        f'height="{height:g}mm" viewBox="0 0 {width_mm:g} {height:g}" role="img" '
        f'aria-label="Diagrama nao pode ser desenhado">'
        f'<rect x="0.4" y="0.4" width="{width_mm - 0.8:g}" height="{height - 0.8:g}" '
        f'fill="#FFFFFF" stroke="#B00020" stroke-width="0.4"/>'
        f'<text x="{width_mm / 2:g}" y="{height / 2:g}" text-anchor="middle" '
        f'font-size="{width_mm * 0.09:g}" fill="#B00020">posicao invalida</text>'
        f"</svg>"
    )
