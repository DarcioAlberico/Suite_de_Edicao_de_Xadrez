"""HTML output, and the XHTML/CSS engine EPUB builds on.

SPEC section 8.4 asks for a self-contained single page or a static site, SVG
diagrams, optional interactive replay, real dark mode, and CSS Paged Media for
printing. Section 8.3 then asks EPUB 3 for semantic XHTML with modular CSS and
inline SVG -- which is the same engine with a different container. So this module
owns the engine and :mod:`caissa.export.epub` owns the container.

Three decisions shape everything here.

**The markup is XHTML-serialisable HTML5.** Every tag is closed, every attribute
is quoted, and only numeric character references appear -- never ``&nbsp;``.
That costs nothing in a browser and buys two things: EPUB gets its required
well-formed XHTML from the same writer, and :func:`read_html` can parse the
output back with :mod:`xml.etree.ElementTree` instead of a forgiving HTML
parser. A round-trip measurement is only as trustworthy as the reader that makes
it.

**CSS is the carrier, and it is read back.** Run properties become a declaration
block on a generated class; :func:`read_html` parses the same stylesheet and
rebuilds :class:`~caissa.core.model.props.RunProps` from it. Nothing is smuggled
past CSS into a private attribute -- with exactly one declared exception: a CMYK
or spot colour is written as its sRGB equivalent *plus* a ``--caissa-ink``
custom property naming the original space and components, because CSS has no
CMYK and losing an author's spot ink between two of our own files would be
indefensible. That substitution is recorded as a degradation like any other.

**Chess semantics live in ``data-`` attributes.** ``data-san``, ``data-ply``,
``data-fen``, ``data-nag`` -- exactly what ``data-`` exists for. A move is a
``<span class="move">`` a stylesheet can restyle and a script can step through,
and it still carries the canonical English SAN next to the Portuguese letters
the reader sees.

What is deliberately not carried
--------------------------------
Recognition provenance -- the per-square confidences, the model hash, the source
rectangle -- does not go into the HTML. It is forensic data about how the
document was *read*, not part of the document, and a reader that had to
reconstruct sixty-four floats from an attribute would be reconstructing our
database, not the book. The loss is recorded per diagram, and
:mod:`caissa.export.fidelity` reports it as accounted-for rather than silent.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, ClassVar, Literal

from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle, PieceType
from caissa.core.model import (
    ULID,
    Alignment,
    Anchor,
    Block,
    Callout,
    CalloutKind,
    CodeBlock,
    Color,
    ColorSpace,
    Contributor,
    ContributorRole,
    Diagram,
    Document,
    DocumentMetadata,
    Emphasis,
    Endnote,
    Figure,
    FontFeature,
    FontStretch,
    Footnote,
    Group,
    GroupRole,
    Heading,
    ImageBlock,
    ImageInline,
    IndexEntry,
    Inline,
    InlineDiagram,
    LengthUnit,
    LigatureMode,
    LineBreak,
    LineSpacing,
    LineSpacingRule,
    Link,
    LinkKind,
    ListBlock,
    ListItem,
    ListKind,
    ListMarkerStyle,
    MathBlock,
    MathInline,
    Measure,
    Move,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    NumeralFigure,
    NumeralSpacing,
    Orientation,
    PageBreak,
    Paragraph,
    ParagraphProps,
    Quote,
    RawInline,
    RawPassthrough,
    Resource,
    RunProps,
    SectionBreak,
    SmallCaps,
    SmallCapsMode,
    Space,
    SpaceKind,
    Span,
    Strike,
    StrikeStyle,
    Strong,
    Subscript,
    Superscript,
    Tab,
    Table,
    TableCell,
    TableOfContents,
    TableRow,
    Text,
    TextDirection,
    TextTransform,
    ThematicBreak,
    Underline,
    UnderlineStyle,
    VerticalAlign,
    document_from_payload,
    document_to_payload,
    resolve_paragraph_props,
    resolve_run_props,
    tag_of,
)
from caissa.export.base import ExportContext, Exporter, ExportOptions, ExportResult
from caissa.export.diagrams import DiagramRenderer, RenderedDiagram
from caissa.export.profiles import HTML_PROFILE
from caissa.export.text import (
    figurine_char,
    game_to_pgn,
    inline_plain_text,
    nag_symbol,
    render_move,
)

__all__ = [
    "BASE_CSS",
    "OWN_SUFFIX",
    "CssRegistry",
    "HtmlExporter",
    "HtmlOptions",
    "XhtmlBuilder",
    "css_to_run_props",
    "read_html",
    "run_props_to_css",
    "split_markup",
    "top_level_starts",
]


# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #
BASE_CSS = """\
/* Caissa Studio -- folha base. Claro e escuro sao dois projetos, nao um invertido. */
:root {
  --tinta: #1a1a1a;
  --tinta-suave: #4a4a4a;
  --papel: #fbfaf7;
  --papel-caixa: #f2efe8;
  --regua: #d8d2c6;
  --realce: #f2c14e;
  --ligacao: #1c4f8b;
  --medida: 34em;
  --corpo: 1rem;
  --entrelinha: 1.55;
  --serifada: Georgia, "Times New Roman", "Liberation Serif", serif;
  --monoespacada: "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --tinta: #e8e4dc;
    --tinta-suave: #b3ada2;
    --papel: #16181c;
    --papel-caixa: #1f2228;
    --regua: #3a3f47;
    --realce: #8a6d1f;
    --ligacao: #7fb2f0;
  }
}
:root[data-theme="dark"] {
  --tinta: #e8e4dc;
  --tinta-suave: #b3ada2;
  --papel: #16181c;
  --papel-caixa: #1f2228;
  --regua: #3a3f47;
  --realce: #8a6d1f;
  --ligacao: #7fb2f0;
}
html { color-scheme: light dark; }
body {
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
  max-width: var(--medida);
  background: var(--papel);
  color: var(--tinta);
  font-family: var(--serifada);
  font-size: var(--corpo);
  line-height: var(--entrelinha);
  text-rendering: optimizeLegibility;
  font-kerning: normal;
  hyphens: auto;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.2; font-weight: 600; margin: 2.2em 0 0.6em; }
h1 { font-size: 1.9em; } h2 { font-size: 1.5em; } h3 { font-size: 1.22em; }
h4, h5, h6 { font-size: 1.05em; }
p { margin: 0; text-align: justify; }
p + p { text-indent: 1.2em; }
p.first, h1 + p, h2 + p, h3 + p, blockquote p, li p:first-child { text-indent: 0; }
a { color: var(--ligacao); }
figure { margin: 1.6em 0; text-align: center; }
figure svg { max-width: 100%; height: auto; }
figcaption {
  margin-top: 0.5em; font-size: 0.86em; color: var(--tinta-suave);
  text-align: center; text-indent: 0;
}
.diagram { break-inside: avoid; page-break-inside: avoid; }
.diagram-inline { display: inline-block; vertical-align: middle; }
.diagram-inline svg { height: 1.9em; width: auto; }
.move { font-weight: 600; white-space: nowrap; font-variant-numeric: lining-nums; }
.move .nag { font-weight: 600; }
.piece { font-family: "DejaVu Sans", "Segoe UI Symbol", "Arial Unicode MS", serif; }
.game { margin: 1.4em 0; }
.game .headers { font-size: 0.9em; color: var(--tinta-suave); margin-bottom: 0.4em; }
.game .variation { color: var(--tinta-suave); font-size: 0.94em; }
.game .comment { font-style: italic; }
.game .move.current { background: var(--realce); border-radius: 0.15em; }
blockquote {
  margin: 1.4em 0; padding-left: 1.2em; border-left: 2px solid var(--regua);
  color: var(--tinta-suave);
}
blockquote .attribution { display: block; text-align: right; font-style: italic; }
.callout {
  margin: 1.5em 0; padding: 0.9em 1.1em; background: var(--papel-caixa);
  border-left: 3px solid var(--regua); border-radius: 0.2em;
}
.callout > .callout-title { font-weight: 700; margin-bottom: 0.35em; }
.callout-warning { border-left-color: #b3541e; }
.callout-exercise { border-left-color: #1c4f8b; }
.callout-solution { border-left-color: #2f6f4f; }
table { border-collapse: collapse; margin: 1.4em auto; font-size: 0.95em; }
th, td { border: 1px solid var(--regua); padding: 0.32em 0.6em; text-align: left; }
thead th { background: var(--papel-caixa); }
caption { caption-side: top; font-size: 0.86em; color: var(--tinta-suave); padding-bottom: 0.4em; }
pre {
  background: var(--papel-caixa); padding: 0.8em 1em; overflow-x: auto;
  font-family: var(--monoespacada); font-size: 0.88em; line-height: 1.4;
}
code { font-family: var(--monoespacada); font-size: 0.92em; }
hr { border: 0; border-top: 1px solid var(--regua); margin: 2em auto; width: 30%; }
hr.page-break { border: 0; height: 0; margin: 0; }
.ornament { text-align: center; border: 0; margin: 2em 0; color: var(--tinta-suave); }
.footnotes { margin-top: 3em; border-top: 1px solid var(--regua); padding-top: 1em;
             font-size: 0.9em; }
.footnote { margin: 0.5em 0; }
.noteref { text-decoration: none; }
.toc ol { list-style: none; padding-left: 1.1em; }
.toc > ol { padding-left: 0; }
.toc a { text-decoration: none; }
.index-entry { display: none; }
.sc { font-variant-caps: small-caps; }
.dropcap::first-letter {
  float: left; font-size: 3.1em; line-height: 0.86; padding-right: 0.06em;
  font-weight: 600;
}
.columns { column-gap: 1.6em; }
@media print {
  @page { size: A5; margin: 18mm 16mm 20mm; }
  body { max-width: none; padding: 0; background: #fff; color: #000; }
  a { color: #000; text-decoration: none; }
  h1, h2 { break-after: avoid; page-break-after: avoid; }
  figure, table, .callout { break-inside: avoid; page-break-inside: avoid; }
  hr.page-break { break-after: page; page-break-after: always; }
  p { orphans: 2; widows: 2; }
}
"""

REPLAY_SCRIPT = """\
/* Navegacao de partida pelas setas do teclado. Degradacao graciosa: sem script,
   os lances continuam legiveis e o diagrama mostra a posicao inicial. */
(function () {
  "use strict";
  var games = document.querySelectorAll("[data-pgn]");
  if (!games.length) { return; }
  Array.prototype.forEach.call(games, function (game) {
    var moves = game.querySelectorAll(".move[data-fen-after]");
    var board = game.querySelector("[data-board]");
    if (!moves.length || !board) { return; }
    var at = -1;
    function show(index) {
      if (index < -1 || index >= moves.length) { return; }
      if (at >= 0) { moves[at].classList.remove("current"); }
      at = index;
      var fen = at < 0 ? board.getAttribute("data-fen-start") :
        moves[at].getAttribute("data-fen-after");
      if (at >= 0) {
        moves[at].classList.add("current");
        moves[at].scrollIntoView({ block: "nearest" });
      }
      board.setAttribute("data-fen", fen || "");
      var label = game.querySelector("[data-replay-label]");
      if (label) { label.textContent = fen || ""; }
    }
    game.setAttribute("tabindex", "0");
    game.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") { show(at + 1); event.preventDefault(); }
      else if (event.key === "ArrowLeft") { show(at - 1); event.preventDefault(); }
      else if (event.key === "Home") { show(-1); event.preventDefault(); }
      else if (event.key === "End") { show(moves.length - 1); event.preventDefault(); }
    });
    Array.prototype.forEach.call(moves, function (node, index) {
      node.addEventListener("click", function () { show(index); });
    });
  });
}());
"""


# --------------------------------------------------------------------------- #
# Property <-> CSS
# --------------------------------------------------------------------------- #
_UNIT_SUFFIX: Mapping[LengthUnit, str] = {
    LengthUnit.PT: "pt",
    LengthUnit.PX: "px",
    LengthUnit.MM: "mm",
    LengthUnit.CM: "cm",
    LengthUnit.INCH: "in",
    LengthUnit.PICA: "pc",
    LengthUnit.EM: "em",
    LengthUnit.EX: "ex",
    LengthUnit.REM: "rem",
    LengthUnit.PERCENT: "%",
}

_SUFFIX_UNIT: Mapping[str, LengthUnit] = {value: key for key, value in _UNIT_SUFFIX.items()}

_UNDERLINE_CSS: Mapping[UnderlineStyle, tuple[str, str]] = {
    UnderlineStyle.SINGLE: ("underline", "solid"),
    UnderlineStyle.DOUBLE: ("underline", "double"),
    UnderlineStyle.THICK: ("underline", "solid"),
    UnderlineStyle.DOTTED: ("underline", "dotted"),
    UnderlineStyle.DOTTED_HEAVY: ("underline", "dotted"),
    UnderlineStyle.DASHED: ("underline", "dashed"),
    UnderlineStyle.DASHED_HEAVY: ("underline", "dashed"),
    UnderlineStyle.DASH_LONG: ("underline", "dashed"),
    UnderlineStyle.DASH_DOT: ("underline", "dashed"),
    UnderlineStyle.DASH_DOT_DOT: ("underline", "dashed"),
    UnderlineStyle.WAVY: ("underline", "wavy"),
    UnderlineStyle.WAVY_DOUBLE: ("underline", "wavy"),
    UnderlineStyle.WAVY_HEAVY: ("underline", "wavy"),
    UnderlineStyle.WORDS_ONLY: ("underline", "solid"),
}

_ALIGN_CSS: Mapping[Alignment, str] = {
    Alignment.LEFT: "left",
    Alignment.RIGHT: "right",
    Alignment.CENTER: "center",
    Alignment.JUSTIFY: "justify",
    Alignment.JUSTIFY_LOW: "justify",
    Alignment.DISTRIBUTE: "justify",
    Alignment.START: "start",
    Alignment.END: "end",
}

_CSS_ALIGN: Mapping[str, Alignment] = {
    "left": Alignment.LEFT,
    "right": Alignment.RIGHT,
    "center": Alignment.CENTER,
    "justify": Alignment.JUSTIFY,
    "start": Alignment.START,
    "end": Alignment.END,
}

_MARKER_CSS: Mapping[ListMarkerStyle, str] = {
    ListMarkerStyle.DECIMAL: "decimal",
    ListMarkerStyle.DECIMAL_LEADING_ZERO: "decimal-leading-zero",
    ListMarkerStyle.LOWER_ALPHA: "lower-alpha",
    ListMarkerStyle.UPPER_ALPHA: "upper-alpha",
    ListMarkerStyle.LOWER_ROMAN: "lower-roman",
    ListMarkerStyle.UPPER_ROMAN: "upper-roman",
    ListMarkerStyle.BULLET: "disc",
    ListMarkerStyle.DASH: "'-  '",
    ListMarkerStyle.SQUARE: "square",
    ListMarkerStyle.CIRCLE: "circle",
    ListMarkerStyle.NONE: "none",
    ListMarkerStyle.CUSTOM: "none",
}


_RUN_FLAGS: tuple[str, ...] = (
    "overline",
    "emboss",
    "engrave",
    "no_break",
    "hidden",
    "underline_skip_ink",
)
"""Boolean run properties whose *off* state produces no CSS declaration.

CSS cannot tell "the author said no" from "the author said nothing", and the
golden rule of SPEC section 5.2 forbids losing the difference quietly. They are
listed in ``--caissa-off`` instead.
"""


_PARAGRAPH_FLAGS: tuple[str, ...] = (
    "keep_together",
    "keep_with_next",
    "page_break_before",
    "contextual_spacing",
    "suppress_line_numbers",
)
"""Boolean paragraph properties whose *off* state produces no CSS declaration."""


def _twip_back(measure: Measure | None, marked: bool) -> Measure | None:
    """Restore a length that was written in points but authored in twips.

    Args:
        measure: The parsed length.
        marked: Whether ``--caissa-twip`` named this property.

    Returns:
        The length in its original unit.
    """
    if measure is None or not marked:
        return measure
    return Measure(value=round(measure.value * 20.0, 6), unit=LengthUnit.TWIP)


def _measure_css(measure: Measure) -> str:
    """Render an IR length as a CSS length.

    Args:
        measure: The length.

    Returns:
        The CSS form, e.g. ``"10.5pt"``. Twips are converted to points, which is
        exact: a twip is one twentieth of a point.
    """
    if measure.unit is LengthUnit.TWIP:
        return f"{_num(measure.value / 20.0)}pt"
    return f"{_num(measure.value)}{_UNIT_SUFFIX[measure.unit]}"


def _measure_attribute(measure: Measure | None) -> str | None:
    """Render a length for a ``data-`` attribute, unit and all.

    CSS cannot spell ``twip``, so :func:`_measure_css` converts one to points --
    an equal length written in a different unit, which is not the same value.
    A data attribute is ours and can carry the unit that was authored.

    Args:
        measure: The length, or ``None``.

    Returns:
        The attribute value, or ``None``.
    """
    if measure is None:
        return None
    return _measure_css(measure) + (":twip" if measure.unit is LengthUnit.TWIP else "")


def _measure_from_attribute(text: str | None) -> Measure | None:
    """Read back what :func:`_measure_attribute` wrote.

    Args:
        text: The attribute value, or ``None``.

    Returns:
        The length, or ``None``.
    """
    if not text:
        return None
    return _twip_back(_css_measure(text.partition(":")[0]), text.endswith(":twip"))


def _css_measure(text: str) -> Measure | None:
    """Parse a CSS length back into an IR length.

    Args:
        text: The CSS value.

    Returns:
        The length, or ``None`` when the value is not a length.
    """
    match = re.fullmatch(r"\s*(-?[0-9.]+)\s*([a-z%]*)\s*", text)
    if match is None:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    unit = _SUFFIX_UNIT.get(match.group(2) or "pt")
    if unit is None:
        return None
    return Measure(value=value, unit=unit)


def _num(value: float) -> str:
    """Render a float compactly and deterministically.

    Args:
        value: The number.

    Returns:
        The shortest form that round-trips to the same value at four decimals.
    """
    rounded = round(value, 6)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _color_css(color: Color) -> str:
    """Render an IR colour as a CSS colour.

    Args:
        color: The colour.

    Returns:
        A hex or ``rgba()`` value; ``"currentColor"`` for automatic.
    """
    if color.space is ColorSpace.AUTO:
        return "currentColor"
    if color.space is ColorSpace.NONE:
        return "transparent"
    if color.space is ColorSpace.NAMED and color.name:
        return color.name
    red, green, blue = color.to_rgb_tuple()
    if color.alpha < 1.0:
        return (
            f"rgba({int(round(red * 255))}, {int(round(green * 255))}, "
            f"{int(round(blue * 255))}, {_num(color.alpha)})"
        )
    return color.to_hex()


def _css_color(text: str) -> Color | None:
    """Parse a CSS colour back into an IR colour.

    Args:
        text: The CSS value.

    Returns:
        The colour, or ``None`` when unparseable.
    """
    value = text.strip()
    if value == "currentColor":
        return Color.automatic()
    if value == "transparent":
        return Color(space=ColorSpace.NONE)
    if value.startswith("#"):
        try:
            return Color.from_hex(value)
        except Exception:
            return None
    match = re.fullmatch(r"rgba?\(([^)]*)\)", value)
    if match is not None:
        parts = [part.strip() for part in match.group(1).replace("/", ",").split(",")]
        try:
            numbers = [float(part.rstrip("%")) for part in parts if part]
        except ValueError:
            return None
        if len(numbers) >= 3:
            alpha = numbers[3] if len(numbers) > 3 else 1.0
            return Color.rgb8(
                int(numbers[0]), int(numbers[1]), int(numbers[2]), alpha=alpha
            )
        return None
    if re.fullmatch(r"[A-Za-z-]+", value):
        return Color.named(value)
    return None


def _ink_custom_property(color: Color) -> str | None:
    """Encode a colour space CSS cannot express, for an exact re-import.

    CSS has no CMYK and no spot ink. The rendered value is the sRGB equivalent --
    which is what the degradation report says happened -- and this custom
    property carries the author's actual numbers alongside it so that our own
    reader gets them back. It is the one and only place this module puts
    something in CSS that CSS itself does not define.

    Args:
        color: The colour.

    Returns:
        The custom-property value, or ``None`` when sRGB says it all.
    """
    if color.space in (ColorSpace.RGB, ColorSpace.AUTO, ColorSpace.NONE):
        return None
    components = " ".join(_num(component) for component in color.components)
    name = (color.name or "").replace(";", "").replace('"', "")
    return f"{color.space.value} {components} / {name}".strip()


def _parse_ink(text: str) -> Color | None:
    """Decode a ``--caissa-ink`` custom property.

    Args:
        text: The property value.

    Returns:
        The colour, or ``None`` when unparseable.
    """
    head, _, name = text.partition("/")
    parts = head.split()
    if not parts:
        return None
    try:
        space = ColorSpace(parts[0])
    except ValueError:
        return None
    try:
        components = tuple(float(part) for part in parts[1:])
    except ValueError:
        return None
    return Color(space=space, components=components, name=name.strip() or None)


def run_props_to_css(props: RunProps) -> dict[str, str]:
    """Translate run properties into a CSS declaration block.

    Args:
        props: The properties to translate. Only fields that are set produce
            declarations, so an empty record produces an empty block.

    Returns:
        A mapping from CSS property to value, in a stable order.
    """
    css: dict[str, str] = {}
    twips: list[str] = []

    def measure(name: str, value: Measure) -> str:
        """Render a length, remembering the units CSS cannot spell."""
        if value.unit is LengthUnit.TWIP:
            twips.append(name)
        return _measure_css(value)

    if props.style:
        css["--caissa-style"] = props.style
    families: list[str] = []
    if props.font_family:
        families.append(props.font_family)
    # A run with fallbacks but no family of its own would otherwise come
    # back with its first fallback promoted to the family.
    elif props.font_fallbacks:
        css["--caissa-family"] = "inherit"
    families.extend(props.font_fallbacks)
    if families:
        css["font-family"] = ", ".join(_quote_family(name) for name in families)
    if props.font_size is not None:
        css["font-size"] = measure("font-size", props.font_size)
    if props.font_weight is not None:
        css["font-weight"] = str(props.font_weight)
    if props.italic is not None:
        css["font-style"] = "italic" if props.italic else "normal"
    if props.oblique_angle is not None:
        # One CSS property, two IR ones. The angle wins the rendering; the
        # marker keeps the italic flag from vanishing behind it.
        css["font-style"] = f"oblique {_num(props.oblique_angle)}deg"
        if props.italic is not None:
            css["--caissa-italic"] = "1" if props.italic else "0"
    if props.font_stretch is not None:
        css["font-stretch"] = props.font_stretch.value
    if props.color is not None:
        css["color"] = _color_css(props.color)
        ink = _ink_custom_property(props.color)
        if ink:
            css["--caissa-ink"] = ink
    if props.highlight is not None:
        css["background-color"] = _color_css(props.highlight)
        ink = _ink_custom_property(props.highlight)
        if ink:
            css["--caissa-ink-highlight"] = ink
    if props.background is not None:
        css["box-shadow"] = f"inset 0 0 0 100vw {_color_css(props.background)}"
        css["--caissa-background"] = _color_css(props.background)
        ink = _ink_custom_property(props.background)
        if ink:
            css["--caissa-ink-background"] = ink
    if props.letter_spacing is not None:
        css["letter-spacing"] = measure("letter-spacing", props.letter_spacing)
    if props.word_spacing is not None:
        css["word-spacing"] = measure("word-spacing", props.word_spacing)
    if props.horizontal_scale is not None:
        css["transform"] = f"scaleX({_num(props.horizontal_scale / 100.0)})"
        css["display"] = "inline-block"
        css["--caissa-hscale"] = _num(props.horizontal_scale)
    if props.kerning is not None:
        css["font-kerning"] = "normal" if props.kerning else "none"
    if props.ligatures is not None:
        css["font-variant-ligatures"] = _ligatures_css(props.ligatures)
    if props.font_features:
        css["font-feature-settings"] = ", ".join(
            f'"{feature.tag}" {feature.value}' for feature in props.font_features
        )
    if props.variation_axes:
        css["font-variation-settings"] = ", ".join(
            f'"{axis.tag}" {_num(axis.value)}' for axis in props.variation_axes
        )
    if props.small_caps is not None:
        css["font-variant-caps"] = _small_caps_css(props.small_caps)
        if props.small_caps is SmallCapsMode.SYNTHETIC:
            css["font-synthesis"] = "small-caps"
    if props.text_transform is not None:
        css["text-transform"] = (
            "none" if props.text_transform is TextTransform.NONE else props.text_transform.value
        )
    # Three distinct IR properties all render as ``vertical-align``. Only one
    # can win the cascade, so each also states itself, or a re-import cannot
    # tell "superscript" from "raised by 3pt".
    if props.baseline_shift is not None:
        css["vertical-align"] = measure("--caissa-baseline-shift", props.baseline_shift)
        css["--caissa-baseline-shift"] = css["vertical-align"]
    if props.rise_relative is not None:
        css["vertical-align"] = f"{_num(props.rise_relative)}em"
        css["--caissa-rise"] = _num(props.rise_relative)
    if props.vertical_align is not None:
        css["vertical-align"] = props.vertical_align.value
        css["--caissa-valign"] = props.vertical_align.value
    if props.numeral_figure is not None or props.numeral_spacing is not None:
        css["font-variant-numeric"] = _numeric_css(props.numeral_figure, props.numeral_spacing)
        # ``normal`` is what CSS says for three different IR states. Say which.
        css["--caissa-numeric"] = (
            f"{props.numeral_figure.value if props.numeral_figure else '-'}"
            f"/{props.numeral_spacing.value if props.numeral_spacing else '-'}"
        )
    decoration = _decoration_css(props, twips)
    css.update(decoration)
    if props.outline is not None:
        width = _measure_css(props.outline.width) if props.outline.width else "1px"
        colour = _color_css(props.outline.color) if props.outline.color else "currentColor"
        css["-webkit-text-stroke"] = f"{width} {colour}"
        if props.outline.color is not None:
            ink = _ink_custom_property(props.outline.color)
            if ink:
                css["--caissa-ink-outline"] = ink
        if not props.outline.fill:
            css["-webkit-text-fill-color"] = "transparent"
    if props.shadow is not None:
        shadow = props.shadow
        blur = _measure_css(shadow.blur) if shadow.blur else "0"
        colour = _color_css(shadow.color) if shadow.color else "currentColor"
        css["text-shadow"] = (
            f"{measure('--caissa-shadow-x', shadow.offset_x)} "
            f"{measure('--caissa-shadow-y', shadow.offset_y)} {blur} {colour}"
        )
        if shadow.blur is not None and shadow.blur.unit is LengthUnit.TWIP:
            twips.append("--caissa-shadow-blur")
        if shadow.color is not None:
            ink = _ink_custom_property(shadow.color)
            if ink:
                css["--caissa-ink-shadow"] = ink
    if props.emboss or props.engrave:
        # Relief is rendered *as* a shadow, so an author's own shadow would be
        # overwritten by it. Keep the author's value beside the rendering.
        if props.shadow is not None:
            css["--caissa-shadow"] = css["text-shadow"]
        css["text-shadow"] = (
            "0 1px 0 rgba(255,255,255,0.65), 0 -1px 0 rgba(0,0,0,0.45)"
            if props.emboss
            else "0 -1px 0 rgba(255,255,255,0.65), 0 1px 0 rgba(0,0,0,0.45)"
        )
        css["--caissa-relief"] = " ".join(
            name for name, on in (("emboss", props.emboss), ("engrave", props.engrave)) if on
        )
    if props.emphasis_mark is not None:
        css["text-emphasis"] = _emphasis_css(props.emphasis_mark)
        css["--caissa-emphasis"] = props.emphasis_mark.value
    if props.opacity is not None:
        css["opacity"] = _num(props.opacity)
    if props.hyphenate is not None:
        css["hyphens"] = "auto" if props.hyphenate else "manual"
    if props.no_break:
        css["white-space"] = "nowrap"
    if props.hidden:
        css["display"] = "none"
    if props.language:
        css["--caissa-lang"] = props.language
    if props.direction is not None:
        css["direction"] = props.direction.value
        css["--caissa-rdirection"] = props.direction.value
    if props.spell_check is not None:
        css["--caissa-spellcheck"] = "1" if props.spell_check else "0"
    # A property explicitly turned off renders as no declaration at all, which
    # is indistinguishable from never having been set. Name them.
    for name in _RUN_FLAGS:
        if getattr(props, name) is False:
            css[f"--caissa-off-{name.replace('_', '-')}"] = "1"
    for name in twips:
        css[f"--caissa-twip-{name.lstrip('-')}"] = "1"
    return css


DECORATION_PREFIX = "d"
"""Class prefix of a node's *own* decoration -- borders, padding, shading.

``Callout`` and ``TableCell`` carry these as fields of their own rather than
inside :class:`~caissa.core.model.props.ParagraphProps`, so folding them into
the paragraph rule would make a re-import put them back in the wrong place.
They get their own rule, and :meth:`_Reader.declarations` skips it.
"""


OWN_SUFFIX = "-own"
"""Suffix of the rule that holds a node's *own* formatting.

A stylesheet has to carry the *resolved* value of every property, because that
is what a browser applies once the named-style chain has been flattened. The IR
node carries only what its author set directly. Reading the resolved block
straight back would promote every inherited value onto the node -- a re-import
that rewrites the document it has just read.

So the authoring layer gets a rule of its own, ``.r5-own`` beside ``.r5``, in
the same generated stylesheet. No element carries that class, so it cannot
disturb the rendering; it is ordinary readable CSS rather than an opaque
sidecar; and it is what makes the round trip exact rather than approximately
right. A rule written without a companion -- an older file -- reads back as
before, which is why the lookup falls through instead of failing.
"""


def chess_font_spec(family: str | None) -> Any:
    """Return the chess font specification a family name refers to, if any.

    Args:
        family: A CSS family name, or ``None``.

    Returns:
        The :class:`caissa.typeset.fonts.ChessFontSpec`, or ``None`` when the
        name is an ordinary text family.
    """
    if not family:
        return None
    from caissa.typeset.fonts import get_spec

    for candidate in (family, family.lower(), family.replace("Chess ", "").lower()):
        try:
            return get_spec(candidate)
        except Exception:  # an unknown name is simply not a chess font
            continue
    return None


def _glyph_for(node: Any) -> str:
    """Return the character a piece glyph should be written as.

    A legacy chess font is encoded in ASCII: Chess Merida draws a knight for
    ``n`` and has no glyph at ``U+265E`` at all. Writing the Unicode figurine
    while naming that family gives a reader a character the font it was told to
    use cannot draw, so the piece is written in the encoding of the face that
    is going to set it.

    Args:
        node: The :class:`~caissa.core.model.inline.PieceGlyph`.

    Returns:
        The character to write.
    """
    glyph = figurine_char(node.piece.value, node.figurine_set)
    spec = chess_font_spec(node.font_family)
    if spec is None:
        return glyph
    try:
        return spec.artwork_char(chess_font_letter(node.piece.value, node.figurine_set))
    except Exception:  # a family with no such piece keeps the figurine
        return glyph


def chess_font_letter(piece: str, figurine_set: Any) -> str:
    """Return the letter a legacy chess font keys a piece by.

    Args:
        piece: The IR piece name, ``"knight"`` and so on.
        figurine_set: Which colour the figurine is drawn in.

    Returns:
        The upper-case letter for a white piece, the lower-case one for a black
        piece -- the convention every legacy chess font follows.
    """
    from caissa.export.text import _PIECE_LETTER

    letter = _PIECE_LETTER.get(piece, "P")
    return letter if getattr(figurine_set, "value", "") == "white" else letter.lower()


def _quote_family(name: str) -> str:
    """Quote a font family name when CSS requires it.

    Args:
        name: The family name.

    Returns:
        The name, quoted when it contains anything but letters, digits and
        hyphens.
    """
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", name):
        return name
    return '"' + name.replace('"', "'") + '"'


def _ligatures_css(mode: LigatureMode) -> str:
    """Map a ligature mode onto ``font-variant-ligatures``.

    Args:
        mode: The mode.

    Returns:
        The CSS value.
    """
    return {
        LigatureMode.NONE: "none",
        LigatureMode.STANDARD: "common-ligatures",
        LigatureMode.CONTEXTUAL: "contextual",
        LigatureMode.DISCRETIONARY: "discretionary-ligatures",
        LigatureMode.HISTORICAL: "historical-ligatures",
        LigatureMode.ALL: (
            "common-ligatures discretionary-ligatures historical-ligatures contextual"
        ),
    }[mode]


def _small_caps_css(mode: SmallCapsMode) -> str:
    """Map a small-caps mode onto ``font-variant-caps``.

    Args:
        mode: The mode.

    Returns:
        The CSS value.
    """
    return {
        SmallCapsMode.NONE: "normal",
        SmallCapsMode.REAL: "small-caps",
        SmallCapsMode.SYNTHETIC: "small-caps",
        SmallCapsMode.PETITE: "petite-caps",
        SmallCapsMode.UNICASE: "unicase",
    }[mode]


def _numeric_css(figure: NumeralFigure | None, spacing: NumeralSpacing | None) -> str:
    """Build a ``font-variant-numeric`` value.

    Args:
        figure: Lining or old-style figures.
        spacing: Proportional or tabular figures.

    Returns:
        The CSS value, ``"normal"`` when neither is specified.
    """
    parts: list[str] = []
    if figure is NumeralFigure.LINING:
        parts.append("lining-nums")
    elif figure is NumeralFigure.OLDSTYLE:
        parts.append("oldstyle-nums")
    if spacing is NumeralSpacing.PROPORTIONAL:
        parts.append("proportional-nums")
    elif spacing is NumeralSpacing.TABULAR:
        parts.append("tabular-nums")
    return " ".join(parts) or "normal"


def _emphasis_css(mark: Any) -> str:
    """Map an emphasis mark onto ``text-emphasis``.

    Args:
        mark: The mark.

    Returns:
        The CSS value.
    """
    return {
        "none": "none",
        "dot": "filled dot",
        "comma": "filled sesame",
        "circle": "open circle",
        "under-dot": "filled dot",
    }.get(getattr(mark, "value", str(mark)), "filled dot")


def _decoration_css(props: RunProps, twips: list[str] | None = None) -> dict[str, str]:
    """Build the text-decoration declarations for a run.

    Args:
        props: The run properties.
        twips: Collector for lengths authored in twips, which CSS cannot spell.

    Returns:
        The declarations, empty when the run carries no decoration.
    """
    css: dict[str, str] = {}
    twips = [] if twips is None else twips
    lines: list[str] = []
    style = ""
    if props.underline is not None:
        css["--caissa-underline"] = props.underline.value
    if props.underline is not None and props.underline is not UnderlineStyle.NONE:
        line, style = _UNDERLINE_CSS.get(props.underline, ("underline", "solid"))
        lines.append(line)
    if props.strikethrough is not None:
        css["--caissa-strike"] = props.strikethrough.value
    if props.strikethrough is not None and props.strikethrough is not StrikeStyle.NONE:
        lines.append("line-through")
        if props.strikethrough is StrikeStyle.DOUBLE and not style:
            style = "double"
    if props.overline:
        lines.append("overline")
    if props.underline is UnderlineStyle.NONE and props.strikethrough is StrikeStyle.NONE:
        css["text-decoration-line"] = "none"
    if lines:
        css["text-decoration-line"] = " ".join(lines)
        if style:
            css["text-decoration-style"] = style
        if props.underline is UnderlineStyle.THICK and props.underline_thickness is None:
            css["text-decoration-thickness"] = "0.14em"
            # Says the thickness is our own rendering of THICK, not the
            # author's measurement, so a re-import does not invent one.
            css["--caissa-thickness"] = "synthetic"
    if props.underline_color is not None:
        css["text-decoration-color"] = _color_css(props.underline_color)
        ink = _ink_custom_property(props.underline_color)
        if ink:
            css["--caissa-ink-underline"] = ink
    if props.strikethrough_color is not None:
        # CSS has one decoration colour for both rules; the underline wins
        # the rendering and the strike keeps its own value beside it.
        css.setdefault("text-decoration-color", _color_css(props.strikethrough_color))
        css["--caissa-strike-color"] = _color_css(props.strikethrough_color)
        ink = _ink_custom_property(props.strikethrough_color)
        if ink:
            css["--caissa-ink-strike"] = ink
    if props.underline_thickness is not None:
        css["text-decoration-thickness"] = _measure_css(props.underline_thickness)
        if props.underline_thickness.unit is LengthUnit.TWIP:
            twips.append("--caissa-thickness")
    if props.underline_offset is not None:
        css["text-underline-offset"] = _measure_css(props.underline_offset)
        if props.underline_offset.unit is LengthUnit.TWIP:
            twips.append("--caissa-offset")
    if props.underline_skip_ink is not None:
        css["text-decoration-skip-ink"] = "auto" if props.underline_skip_ink else "none"
    return css


def css_to_run_props(declarations: Mapping[str, str]) -> RunProps:
    """Rebuild run properties from a CSS declaration block.

    The inverse of :func:`run_props_to_css`, and the reason a fidelity
    measurement on HTML means something: the reader gets the formatting from the
    stylesheet the browser would have used, not from a private side channel.

    Args:
        declarations: A mapping from CSS property to value.

    Returns:
        The reconstructed properties.
    """
    changes: dict[str, Any] = {}
    get = declarations.get
    twips = frozenset(
        key[len("--caissa-twip-") :] for key in declarations if key.startswith("--caissa-twip-")
    )

    def measure(name: str, text: str) -> Measure | None:
        """Parse a length, restoring the unit CSS could not spell."""
        return _twip_back(_css_measure(text), name.lstrip("-") in twips)

    if (value := get("--caissa-style")) is not None:
        changes["style"] = value

    families = get("font-family")
    if families:
        names = [_unquote_family(part) for part in _split_commas(families)]
        if get("--caissa-family") == "inherit":
            changes["font_fallbacks"] = tuple(names)
        elif names:
            changes["font_family"] = names[0]
            if len(names) > 1:
                changes["font_fallbacks"] = tuple(names[1:])

    if (value := get("font-size")) is not None:
        changes["font_size"] = measure("font-size", value)
    if (value := get("font-weight")) is not None and value.isdigit():
        changes["font_weight"] = int(value)
    if (value := get("font-style")) is not None:
        if value == "italic":
            changes["italic"] = True
        elif value == "normal":
            changes["italic"] = False
        elif value.startswith("oblique"):
            match = re.search(r"(-?[0-9.]+)deg", value)
            if match:
                changes["oblique_angle"] = float(match.group(1))
    if (value := get("--caissa-italic")) is not None:
        changes["italic"] = value == "1"
    if (value := get("font-stretch")) is not None:
        try:
            changes["font_stretch"] = FontStretch(value)
        except ValueError:
            pass
    if (value := get("--caissa-ink")) is not None:
        changes["color"] = _parse_ink(value)
    elif (value := get("color")) is not None:
        changes["color"] = _css_color(value)
    if (value := get("--caissa-ink-highlight")) is not None:
        changes["highlight"] = _parse_ink(value)
    elif (value := get("background-color")) is not None:
        changes["highlight"] = _css_color(value)
    if (value := get("--caissa-ink-background")) is not None:
        changes["background"] = _parse_ink(value)
    elif (value := get("--caissa-background")) is not None:
        changes["background"] = _css_color(value)
    if (value := get("letter-spacing")) is not None:
        changes["letter_spacing"] = measure("letter-spacing", value)
    if (value := get("word-spacing")) is not None:
        changes["word_spacing"] = measure("word-spacing", value)
    if (value := get("--caissa-hscale")) is not None:
        try:
            changes["horizontal_scale"] = float(value)
        except ValueError:
            pass
    if (value := get("font-kerning")) is not None:
        changes["kerning"] = value == "normal"
    if (value := get("font-variant-ligatures")) is not None:
        for mode in LigatureMode:
            if _ligatures_css(mode) == value:
                changes["ligatures"] = mode
                break
    if (value := get("font-feature-settings")) is not None:
        features: list[FontFeature] = []
        for part in _split_commas(value):
            match = re.fullmatch(r'\s*"(\w{4})"\s*(-?\d+)?\s*', part)
            if match:
                features.append(
                    FontFeature(tag=match.group(1), value=int(match.group(2) or 1))
                )
        if features:
            changes["font_features"] = tuple(features)
    if (value := get("font-variation-settings")) is not None:
        from caissa.core.model import VariationAxis

        axes: list[VariationAxis] = []
        for part in _split_commas(value):
            match = re.fullmatch(r'\s*"(\w{4})"\s*(-?[0-9.]+)\s*', part)
            if match:
                axes.append(VariationAxis(tag=match.group(1), value=float(match.group(2))))
        if axes:
            changes["variation_axes"] = tuple(axes)
    if (value := get("font-variant-caps")) is not None:
        synthetic = get("font-synthesis") == "small-caps"
        changes["small_caps"] = {
            "normal": SmallCapsMode.NONE,
            "small-caps": SmallCapsMode.SYNTHETIC if synthetic else SmallCapsMode.REAL,
            "petite-caps": SmallCapsMode.PETITE,
            "unicase": SmallCapsMode.UNICASE,
        }.get(value)
    if (value := get("text-transform")) is not None:
        try:
            changes["text_transform"] = TextTransform(value)
        except ValueError:
            pass
    if (value := get("--caissa-valign")) is not None:
        try:
            changes["vertical_align"] = VerticalAlign(value)
        except ValueError:
            pass
    if (value := get("--caissa-rise")) is not None:
        try:
            changes["rise_relative"] = float(value)
        except ValueError:
            pass
    if (value := get("--caissa-baseline-shift")) is not None:
        changes["baseline_shift"] = measure("--caissa-baseline-shift", value)
    if not {"vertical_align", "rise_relative", "baseline_shift"} & changes.keys():
        if (value := get("vertical-align")) is not None:
            try:
                changes["vertical_align"] = VerticalAlign(value)
            except ValueError:
                if value.endswith("em") and not value.endswith(("rem", "chem")):
                    try:
                        changes["rise_relative"] = float(value[:-2])
                    except ValueError:
                        changes["baseline_shift"] = _css_measure(value)
                else:
                    changes["baseline_shift"] = _css_measure(value)
    if (value := get("--caissa-numeric")) is not None:
        figure, _, spacing = value.partition("/")
        if figure != "-":
            changes["numeral_figure"] = NumeralFigure(figure)
        if spacing != "-":
            changes["numeral_spacing"] = NumeralSpacing(spacing)
    elif (value := get("font-variant-numeric")) is not None:
        if "oldstyle-nums" in value:
            changes["numeral_figure"] = NumeralFigure.OLDSTYLE
        elif "lining-nums" in value:
            changes["numeral_figure"] = NumeralFigure.LINING
        if "tabular-nums" in value:
            changes["numeral_spacing"] = NumeralSpacing.TABULAR
        elif "proportional-nums" in value:
            changes["numeral_spacing"] = NumeralSpacing.PROPORTIONAL
    if (value := get("--caissa-underline")) is not None:
        changes["underline"] = UnderlineStyle(value)
    elif (value := get("text-decoration-line")) is not None and "underline" in value:
        changes["underline"] = UnderlineStyle.SINGLE
    if (value := get("--caissa-strike")) is not None:
        changes["strikethrough"] = StrikeStyle(value)
    elif (value := get("text-decoration-line")) is not None and "line-through" in value:
        changes["strikethrough"] = StrikeStyle.SINGLE
    if (value := get("text-decoration-line")) is not None and "overline" in value:
        changes["overline"] = True
    if (value := get("--caissa-ink-strike")) is not None:
        changes["strikethrough_color"] = _parse_ink(value)
    elif (value := get("--caissa-strike-color")) is not None:
        changes["strikethrough_color"] = _css_color(value)
    if (value := get("--caissa-ink-underline")) is not None:
        changes["underline_color"] = _parse_ink(value)
    elif (value := get("text-decoration-color")) is not None and not get(
        "--caissa-strike-color"
    ):
        changes["underline_color"] = _css_color(value)
    if (value := get("text-decoration-thickness")) is not None and get(
        "--caissa-thickness"
    ) != "synthetic":
        changes["underline_thickness"] = _twip_back(
            _css_measure(value), "caissa-thickness" in twips
        )
    if (value := get("text-underline-offset")) is not None:
        changes["underline_offset"] = _twip_back(
            _css_measure(value), "caissa-offset" in twips
        )
    if (value := get("text-decoration-skip-ink")) is not None:
        changes["underline_skip_ink"] = value == "auto"
    if (value := get("-webkit-text-stroke")) is not None:
        from caissa.core.model import TextOutline

        parts = value.split(None, 1)
        ink = get("--caissa-ink-outline")
        changes["outline"] = TextOutline(
            width=_css_measure(parts[0]) if parts else None,
            color=(
                _parse_ink(ink)
                if ink
                else (_css_color(parts[1]) if len(parts) > 1 else None)
            ),
            fill=get("-webkit-text-fill-color") != "transparent",
        )
    relief = (get("--caissa-relief") or "").split()
    if "emboss" in relief:
        changes["emboss"] = True
    if "engrave" in relief:
        changes["engrave"] = True
    shadow_css = get("--caissa-shadow") or (None if relief else get("text-shadow"))
    if shadow_css is not None:
        changes["shadow"] = _css_shadow(shadow_css, get("--caissa-ink-shadow"), twips)
    if (value := get("--caissa-emphasis")) is not None:
        from caissa.core.model import EmphasisMark

        try:
            changes["emphasis_mark"] = EmphasisMark(value)
        except ValueError:
            pass
    elif (value := get("text-emphasis")) is not None:
        from caissa.core.model import EmphasisMark

        changes["emphasis_mark"] = {
            "none": EmphasisMark.NONE,
            "filled dot": EmphasisMark.DOT,
            "filled sesame": EmphasisMark.COMMA,
            "open circle": EmphasisMark.CIRCLE,
        }.get(value, EmphasisMark.DOT)
    if (value := get("opacity")) is not None:
        try:
            changes["opacity"] = float(value)
        except ValueError:
            pass
    if (value := get("hyphens")) is not None:
        changes["hyphenate"] = value == "auto"
    if get("white-space") == "nowrap":
        changes["no_break"] = True
    if get("display") == "none":
        changes["hidden"] = True
    if (value := get("--caissa-lang")) is not None:
        changes["language"] = value
    if (value := get("--caissa-rdirection") or get("direction")) is not None:
        try:
            changes["direction"] = TextDirection(value)
        except ValueError:
            pass
    if (value := get("--caissa-spellcheck")) is not None:
        changes["spell_check"] = value == "1"
    for name in _RUN_FLAGS:
        if get(f"--caissa-off-{name.replace('_', '-')}") == "1":
            changes[name] = False
    return RunProps(
        **{
            key: value
            for key, value in changes.items()
            if value is not None or key in _RUN_FLAGS
        }
    )


def _css_shadow(
    value: str, ink: str | None = None, twips: frozenset[str] = frozenset()
) -> Any:
    """Parse a ``text-shadow`` value into a :class:`TextShadow`.

    Args:
        value: The CSS value.
        ink: The ``--caissa-ink-shadow`` companion, when the shadow colour is
            in a space CSS cannot spell.
        twips: The ``--caissa-twip`` names, for offsets authored in twips.

    Returns:
        The shadow, or ``None`` when unparseable.
    """
    from caissa.core.model import TextShadow

    parts = value.split()
    if len(parts) < 2:
        return None
    offset_x = _twip_back(_css_measure(parts[0]), "caissa-shadow-x" in twips)
    offset_y = _twip_back(_css_measure(parts[1]), "caissa-shadow-y" in twips)
    if offset_x is None or offset_y is None:
        return None
    blur = (
        _twip_back(_css_measure(parts[2]), "caissa-shadow-blur" in twips)
        if len(parts) > 2
        else None
    )
    if ink:
        colour = _parse_ink(ink)
    else:
        colour = _css_color(" ".join(parts[3:])) if len(parts) > 3 else None
    return TextShadow(offset_x=offset_x, offset_y=offset_y, blur=blur, color=colour)


def paragraph_props_to_css(props: ParagraphProps) -> dict[str, str]:
    """Translate paragraph properties into a CSS declaration block.

    Args:
        props: The properties to translate.

    Returns:
        A mapping from CSS property to value.
    """
    css: dict[str, str] = {}
    twips: list[str] = []

    def measure(name: str, value: Measure) -> str:
        """Render a length, remembering the units CSS cannot spell."""
        if value.unit is LengthUnit.TWIP:
            twips.append(name)
        return _measure_css(value)

    if props.style:
        # ``--caissa-style`` is also what a run writes, and a paragraph rule
        # carries both records. Each names itself.
        css["--caissa-pstyle"] = props.style
    if props.alignment is not None:
        css["text-align"] = _ALIGN_CSS[props.alignment]
        css["--caissa-align"] = props.alignment.value
    if props.indent_left is not None:
        css["margin-left"] = measure("margin-left", props.indent_left)
    if props.indent_right is not None:
        css["margin-right"] = measure("margin-right", props.indent_right)
    if props.indent_first_line is not None:
        css["text-indent"] = measure("text-indent", props.indent_first_line)
    if props.space_before is not None:
        css["margin-top"] = measure("margin-top", props.space_before)
    if props.space_after is not None:
        css["margin-bottom"] = measure("margin-bottom", props.space_after)
    if props.line_spacing is not None:
        css["line-height"] = _line_height_css(props.line_spacing)
        css["--caissa-leading"] = (
            f"{props.line_spacing.rule.value} {_num(props.line_spacing.value)}"
            + (
                f" {measure('--caissa-leading', props.line_spacing.length)}"
                if props.line_spacing.length
                else ""
            )
        )
    if props.keep_together:
        css["break-inside"] = "avoid"
    if props.keep_with_next:
        css["break-after"] = "avoid"
    if props.page_break_before:
        css["break-before"] = "page"
    if props.widow_control is not None:
        css["orphans"] = "2" if props.widow_control else "1"
        css["widows"] = "2" if props.widow_control else "1"
    if props.contextual_spacing:
        css["--caissa-contextual"] = "1"
    if props.shading is not None:
        css["background-color"] = _color_css(props.shading)
        css["--caissa-pshading"] = _color_css(props.shading)
        ink = _ink_custom_property(props.shading)
        if ink:
            css["--caissa-ink-shading"] = ink
    if props.padding is not None:
        for side, value in (
            ("top", props.padding.top),
            ("right", props.padding.right),
            ("bottom", props.padding.bottom),
            ("left", props.padding.left),
        ):
            if value is not None:
                css[f"padding-{side}"] = measure(f"padding-{side}", value)
    if props.borders is not None:
        for side, border in (
            ("top", props.borders.top),
            ("right", props.borders.right),
            ("bottom", props.borders.bottom),
            ("left", props.borders.left),
        ):
            if border is not None:
                width = measure(f"border-{side}", border.width) if border.width else "1px"
                colour = _color_css(border.color) if border.color else "currentColor"
                css[f"border-{side}"] = f"{width} {border.style.value} {colour}"
                # CSS has no per-edge "space between rule and text", and the
                # padding shorthand is already spoken for by ``padding``.
                if border.space is not None:
                    css[f"--caissa-border-{side}-space"] = measure(
                        f"--caissa-border-{side}-space", border.space
                    )
                if border.shadow:
                    css[f"--caissa-border-{side}-shadow"] = "1"
                if border.color is not None:
                    ink = _ink_custom_property(border.color)
                    if ink:
                        css[f"--caissa-border-{side}-ink"] = ink
    if props.direction is not None:
        css["direction"] = props.direction.value
        # A paragraph rule also carries the block's run properties, and those
        # write ``direction`` too. Say which one is the paragraph's.
        css["--caissa-pdirection"] = props.direction.value
    if props.hyphenate is not None:
        css["hyphens"] = "auto" if props.hyphenate else "manual"
        css["--caissa-phyphens"] = "auto" if props.hyphenate else "manual"
    if props.outline_level is not None:
        css["--caissa-outline-level"] = str(props.outline_level)
    if props.suppress_line_numbers:
        css["--caissa-no-line-numbers"] = "1"
    if props.numbering is not None:
        start = props.numbering.start_override
        css["--caissa-numbering"] = (
            f"{props.numbering.definition}|{props.numbering.level}"
            f"|{'-' if start is None else start}"
        )
    if props.default_run is not None:
        # A run property on the paragraph *is* an inherited CSS declaration --
        # that is what the cascade is for, and the browser needs it under its
        # real name. But the paragraph writes some of the same names, and
        # whichever lands second would win, so the record is also written under
        # names of its own that nothing else can overwrite.
        inherited = run_props_to_css(props.default_run)
        css["--caissa-default-run"] = "1"
        for key, value in inherited.items():
            css.setdefault(key, value)
            css[_inherited_name(key)] = value
    for name in _PARAGRAPH_FLAGS:
        if getattr(props, name, None) is False:
            css[f"--caissa-off-{name.replace('_', '-')}"] = "1"
    for name in twips:
        css[f"--caissa-twip-{name.lstrip('-')}"] = "1"
    return css


_INHERITED_PREFIX = "--caissa-dr-"
"""Prefix under which a paragraph's inherited run record is written."""


def _inherited_name(key: str) -> str:
    """Rename a run declaration so a paragraph rule can hold both records.

    Args:
        key: The CSS property name the run wrote.

    Returns:
        The name it is also written under, unique to the inherited record.
    """
    return _INHERITED_PREFIX + key.lstrip("-")


def _inherited_original(key: str) -> str:
    """Undo :func:`_inherited_name`.

    Args:
        key: The prefixed name.

    Returns:
        The original CSS property name.
    """
    bare = key[len(_INHERITED_PREFIX) :]
    return f"--{bare}" if bare.startswith("caissa-") else bare


def _line_height_css(spacing: LineSpacing) -> str:
    """Render an IR line spacing as a CSS ``line-height``.

    Args:
        spacing: The spacing.

    Returns:
        The CSS value.
    """
    if spacing.rule is LineSpacingRule.MULTIPLE:
        return _num(spacing.value)
    if spacing.length is not None:
        return _measure_css(spacing.length)
    return _num(spacing.value)


def css_to_paragraph_props(declarations: Mapping[str, str]) -> ParagraphProps:
    """Rebuild paragraph properties from a CSS declaration block.

    Args:
        declarations: A mapping from CSS property to value.

    Returns:
        The reconstructed properties.
    """
    changes: dict[str, Any] = {}
    get = declarations.get
    twips = frozenset(
        key[len("--caissa-twip-") :] for key in declarations if key.startswith("--caissa-twip-")
    )

    def measure(name: str, text: str) -> Measure | None:
        """Parse a length, restoring the unit CSS could not spell."""
        return _twip_back(_css_measure(text), name.lstrip("-") in twips)

    if (value := get("--caissa-pstyle")) is not None:
        changes["style"] = value
    if (value := get("--caissa-align")) is not None:
        changes["alignment"] = Alignment(value)
    elif (value := get("text-align")) is not None:
        changes["alignment"] = _CSS_ALIGN.get(value)
    if (value := get("margin-left")) is not None:
        changes["indent_left"] = measure("margin-left", value)
    if (value := get("margin-right")) is not None:
        changes["indent_right"] = measure("margin-right", value)
    if (value := get("text-indent")) is not None:
        changes["indent_first_line"] = measure("text-indent", value)
    if (value := get("margin-top")) is not None:
        changes["space_before"] = measure("margin-top", value)
    if (value := get("margin-bottom")) is not None:
        changes["space_after"] = measure("margin-bottom", value)
    if (value := get("--caissa-leading")) is not None:
        parts = value.split()
        if parts:
            try:
                rule = LineSpacingRule(parts[0])
            except ValueError:
                rule = LineSpacingRule.MULTIPLE
            amount = float(parts[1]) if len(parts) > 1 else 1.0
            length = measure("--caissa-leading", parts[2]) if len(parts) > 2 else None
            changes["line_spacing"] = LineSpacing(rule=rule, value=amount, length=length)
    if get("break-inside") == "avoid":
        changes["keep_together"] = True
    if get("break-after") == "avoid":
        changes["keep_with_next"] = True
    if get("break-before") == "page":
        changes["page_break_before"] = True
    if (value := get("orphans")) is not None:
        changes["widow_control"] = value != "1"
    if get("--caissa-contextual") == "1":
        changes["contextual_spacing"] = True
    if (value := get("--caissa-ink-shading")) is not None:
        changes["shading"] = _parse_ink(value)
    elif (value := get("--caissa-pshading")) is not None:
        changes["shading"] = _css_color(value)
    padding = {
        side: measure(f"padding-{side}", get(f"padding-{side}") or "")
        for side in ("top", "right", "bottom", "left")
    }
    if any(value is not None for value in padding.values()):
        from caissa.core.model import Padding

        changes["padding"] = Padding(**padding)
    borders: dict[str, Any] = {}
    for side in ("top", "right", "bottom", "left"):
        value = get(f"border-{side}")
        if value:
            borders[side] = _css_border(
                value,
                ink=get(f"--caissa-border-{side}-ink"),
                space=measure(
                    f"--caissa-border-{side}-space",
                    get(f"--caissa-border-{side}-space") or "",
                ),
                shadow=get(f"--caissa-border-{side}-shadow") == "1",
                twip=f"border-{side}" in twips,
                # ``space`` above already went through ``measure``.
            )
    if borders:
        from caissa.core.model import Borders

        changes["borders"] = Borders(**borders)
    if (value := get("--caissa-pdirection") or get("direction")) is not None:
        changes["direction"] = TextDirection(value)
    if (value := get("--caissa-phyphens") or get("hyphens")) is not None:
        changes["hyphenate"] = value == "auto"
    if (value := get("--caissa-outline-level")) is not None:
        changes["outline_level"] = int(value)
    if get("--caissa-no-line-numbers") == "1":
        changes["suppress_line_numbers"] = True
    if (value := get("--caissa-numbering")) is not None:
        from caissa.core.model import NumberingRef

        definition, _, rest = value.partition("|")
        level, _, start = rest.partition("|")
        changes["numbering"] = NumberingRef(
            definition=definition,
            level=int(level or 0),
            start_override=None if start in ("", "-") else int(start),
        )
    if get("--caissa-default-run") is not None:
        changes["default_run"] = css_to_run_props(
            {
                _inherited_original(key): item
                for key, item in declarations.items()
                if key.startswith(_INHERITED_PREFIX)
            }
        )
    for name in _PARAGRAPH_FLAGS:
        if get(f"--caissa-off-{name.replace('_', '-')}") == "1":
            changes[name] = False
    return ParagraphProps(
        **{
            key: value
            for key, value in changes.items()
            if value is not None or key in _PARAGRAPH_FLAGS
        }
    )


def _css_border(
    value: str,
    *,
    ink: str | None = None,
    space: Measure | None = None,
    shadow: bool = False,
    twip: bool = False,
) -> Any:
    """Parse a CSS shorthand border into an IR border.

    Args:
        value: The CSS value, ``"1px solid #000000"``.
        ink: The companion custom property carrying a non-sRGB colour.
        space: The gap between rule and text, which CSS keeps in ``padding``
            and so cannot be recovered from the shorthand.
        shadow: Whether the border was drawn with a drop shadow.
        twip: Whether the width was authored in twips.

    Returns:
        The border.
    """
    from caissa.core.model import Border, BorderStyle

    parts = value.split()
    width = _twip_back(_css_measure(parts[0]) if parts else None, twip)
    style = BorderStyle.SOLID
    if len(parts) > 1:
        try:
            style = BorderStyle(parts[1])
        except ValueError:
            style = BorderStyle.SOLID
    if ink:
        colour = _parse_ink(ink)
    else:
        colour = _css_color(parts[2]) if len(parts) > 2 else None
    return Border(style=style, width=width, color=colour, space=space, shadow=shadow)


def _split_commas(value: str) -> list[str]:
    """Split a CSS list on commas that are not inside quotes or parentheses.

    Args:
        value: The CSS value.

    Returns:
        The parts, stripped.
    """
    parts: list[str] = []
    depth = 0
    quote = ""
    current = ""
    for char in value:
        if quote:
            current += char
            if char == quote:
                quote = ""
            continue
        if char in "'\"":
            quote = char
            current += char
        elif char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def _unquote_family(name: str) -> str:
    """Strip quotes from a CSS font family name.

    Args:
        name: The family name as written in CSS.

    Returns:
        The bare name.
    """
    stripped = name.strip()
    if len(stripped) >= 2 and stripped[0] in "'\"" and stripped[-1] == stripped[0]:
        return stripped[1:-1]
    return stripped


class CssRegistry:
    """Interns declaration blocks into generated classes.

    Two runs with identical formatting share one class, which is both smaller
    and what a hand-written stylesheet would do. The class names are stable and
    ordered, so re-exporting an unchanged document produces an unchanged file --
    a property that makes diffing two exports useful.
    """

    __slots__ = ("_order", "_own", "_prefix", "_rules")

    def __init__(self, prefix: str = "r") -> None:
        """Create an empty registry.

        Args:
            prefix: Class-name prefix; ``"r"`` for runs, ``"p"`` for paragraphs.
        """
        self._prefix = prefix
        self._rules: dict[tuple[str, str], str] = {}
        self._order: list[tuple[str, str]] = []
        self._own: dict[str, str] = {}

    def intern(
        self, declarations: Mapping[str, str], direct: Mapping[str, str] | None = None
    ) -> str | None:
        """Return the class name for a declaration block.

        Args:
            declarations: What a browser must apply -- the node's formatting
                with the named-style chain already flattened into it.
            direct: What the node itself set. When given and different, a
                companion ``<name>-own`` rule records it; see
                :data:`OWN_SUFFIX`.

        Returns:
            The class name, or ``None`` when there is nothing to declare.
        """
        if not declarations:
            return None
        body = _render_block(declarations)
        own = _render_block(direct or {}) if direct is not None else ""
        key = (body, own)
        existing = self._rules.get(key)
        if existing is not None:
            return existing
        name = f"{self._prefix}{len(self._order) + 1}"
        self._rules[key] = name
        self._order.append(key)
        if direct is not None and own != body:
            self._own[name] = own
        return name

    def stylesheet(self) -> str:
        """Render every interned rule.

        Returns:
            The CSS text, one rule per line.
        """
        lines: list[str] = []
        for key in self._order:
            name = self._rules[key]
            lines.append(f".{name} {{ {key[0]}; }}")
            own = self._own.get(name)
            if own is not None:
                lines.append(f".{name}{OWN_SUFFIX} {{ {own or '--caissa-own: none'}; }}")
        return "\n".join(lines)

    def __len__(self) -> int:
        """Return how many distinct blocks were interned."""
        return len(self._order)


def _render_block(declarations: Mapping[str, str]) -> str:
    """Render a declaration mapping as a CSS block body.

    Args:
        declarations: The block.

    Returns:
        The body, without the surrounding braces or the trailing semicolon.
    """
    return "; ".join(f"{name}: {value}" for name, value in declarations.items())


def parse_stylesheet(css: str) -> dict[str, dict[str, str]]:
    """Parse a stylesheet into a class-name to declaration mapping.

    Only the simple single-class rules this module generates are read; the base
    stylesheet's descendant selectors and media queries are skipped, which is
    correct -- they carry the design, not the document.

    Args:
        css: The stylesheet text.

    Returns:
        A mapping from class name to declarations.
    """
    result: dict[str, dict[str, str]] = {}
    without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"\.([A-Za-z_][\w-]*)\s*\{([^{}]*)\}", without_comments):
        name = match.group(1)
        declarations: dict[str, str] = {}
        for part in match.group(2).split(";"):
            key, sep, value = part.partition(":")
            if sep and key.strip():
                declarations[key.strip()] = value.strip()
        if declarations:
            result[name] = declarations
    return result


# --------------------------------------------------------------------------- #
# Options
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True, kw_only=True)
class HtmlOptions(ExportOptions):
    """Settings specific to HTML output.

    Attributes:
        mode: ``"single"`` writes one self-contained file; ``"site"`` writes a
            directory with one page per chapter, a shared stylesheet and
            previous/next navigation.
        split_level: Heading level that starts a new page in site mode.
        page_title_suffix: Appended to each page's ``<title>`` in site mode.
    """

    mode: Literal["single", "site"] = "single"
    split_level: int = 1
    page_title_suffix: str = ""


# --------------------------------------------------------------------------- #
# The writer
# --------------------------------------------------------------------------- #
_CALLOUT_LABEL: Mapping[CalloutKind, str] = {
    CalloutKind.NOTE: "Nota",
    CalloutKind.TIP: "Dica",
    CalloutKind.WARNING: "Atencao",
    CalloutKind.IMPORTANT: "Importante",
    CalloutKind.EXAMPLE: "Exemplo",
    CalloutKind.EXERCISE: "Exercicio",
    CalloutKind.SOLUTION: "Solucao",
    CalloutKind.THEORY: "Teoria",
    CalloutKind.SUMMARY: "Resumo",
    CalloutKind.SIDEBAR: "Quadro",
}

_SPACE_CHARS: Mapping[SpaceKind, str] = {
    SpaceKind.THIN: " ",
    SpaceKind.HAIR: " ",
    SpaceKind.EN: " ",
    SpaceKind.EM: " ",
    SpaceKind.FIGURE: " ",
    SpaceKind.PUNCTUATION: " ",
    SpaceKind.ZERO_WIDTH: "\u200b",
    SpaceKind.ZERO_WIDTH_NON_JOINER: "‌",
    SpaceKind.ZERO_WIDTH_JOINER: "‍",
}

_ROLE_TAG: Mapping[GroupRole, str] = {
    GroupRole.GENERIC: "div",
    GroupRole.SECTION: "section",
    GroupRole.CHAPTER: "section",
    GroupRole.FRONT_MATTER: "section",
    GroupRole.BACK_MATTER: "section",
    GroupRole.DIAGRAM_GRID: "div",
    GroupRole.EXERCISE_SET: "section",
    GroupRole.ABSTRACT: "section",
    GroupRole.DEDICATION: "section",
    GroupRole.COLOPHON: "section",
}


def escape(text: str) -> str:
    """Escape text for an XML text node.

    Args:
        text: The raw text.

    Returns:
        The escaped text, using numeric references only so the result is valid
        XHTML as well as HTML.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(" ", "&#160;")
    )


def escape_attr(text: str) -> str:
    """Escape text for an XML attribute value.

    Args:
        text: The raw text.

    Returns:
        The escaped text.
    """
    return escape(text).replace('"', "&quot;")


class XhtmlBuilder:
    """Turns IR blocks into XHTML, and collects what the container needs.

    One builder per export. It holds the two CSS registries, the diagram
    renderer, the note collector and the heading index, because a container --
    a single page, a site, an EPUB -- needs all four and would otherwise gather
    them by walking the tree a second time.
    """

    def __init__(
        self,
        context: ExportContext,
        *,
        epub: bool = False,
        interactive: bool = False,
    ) -> None:
        """Create a builder.

        Args:
            context: The export context, for degradations and settings.
            epub: Emit ``epub:type`` semantics and EPUB-safe markup.
            interactive: Emit the data attributes the replay script reads.
        """
        self.context = context
        self.epub = epub
        self.interactive = interactive
        self.runs = CssRegistry("r")
        self.paragraphs = CssRegistry("p")
        self.decorations = CssRegistry(DECORATION_PREFIX)
        self.diagrams = DiagramRenderer(context)
        self.headings: list[tuple[int, str, str]] = []
        self.notes: list[Footnote | Endnote] = []
        self.index_entries: list[tuple[tuple[str, ...], str]] = []
        self._anchor_counter = 0
        self._in_link = False
        self._used_anchors: set[str] = set()

    # -- helpers -----------------------------------------------------------

    def _anchor(self, preferred: str | None, node: Any) -> str:
        """Mint a unique element id.

        Args:
            preferred: The anchor the document asked for.
            node: The node, whose ULID is the fallback.

        Returns:
            A unique id.
        """
        base = preferred or f"n-{node.id}"
        candidate = re.sub(r"[^A-Za-z0-9_.:-]", "-", base)
        if not candidate or not candidate[0].isalpha():
            candidate = f"a-{candidate}"
        if candidate in self._used_anchors:
            self._anchor_counter += 1
            candidate = f"{candidate}-{self._anchor_counter}"
        self._used_anchors.add(candidate)
        return candidate

    def _run_class(self, props: RunProps, node: Any) -> str | None:
        """Intern a run's formatting and audit it.

        Args:
            props: The direct run properties.
            node: The node, for the degradation report.

        Returns:
            The class name, or ``None``.
        """
        resolved = resolve_run_props(self.context.stylesheet, direct=props)
        self.context.audit_run_props(resolved, node=node)
        return self.runs.intern(run_props_to_css(resolved), run_props_to_css(props))

    def _paragraph_class(self, props: ParagraphProps, node: Any) -> str | None:
        """Intern a paragraph's formatting and audit it.

        Args:
            props: The direct paragraph properties.
            node: The node, for the degradation report.

        Returns:
            The class name, or ``None``.
        """
        resolved = resolve_paragraph_props(self.context.stylesheet, direct=props)
        self.context.audit_paragraph_props(resolved.paragraph, node=node)
        self.context.audit_run_props(resolved.run, node=node)
        declarations = paragraph_props_to_css(resolved.paragraph)
        declarations.update(run_props_to_css(resolved.run))
        own = paragraph_props_to_css(props)
        own.update(run_props_to_css(props.default_run) if props.default_run else {})
        return self.paragraphs.intern(declarations, own)

    def _decoration_class(self, node: Any) -> str | None:
        """Intern a node's own borders, padding and shading as their own rule.

        Args:
            node: A :class:`~caissa.core.model.blocks.Callout` or
                :class:`~caissa.core.model.blocks.TableCell`.

        Returns:
            The class name, or ``None`` when the node is undecorated.
        """
        props = ParagraphProps(
            borders=getattr(node, "borders", None),
            padding=getattr(node, "padding", None),
            shading=getattr(node, "shading", None),
        )
        declarations = paragraph_props_to_css(props)
        if not declarations:
            return None
        return self.decorations.intern(declarations, declarations)

    @staticmethod
    def _attrs(pairs: Mapping[str, str | None]) -> str:
        """Render an attribute mapping.

        Args:
            pairs: Attribute names to values; ``None`` values are skipped.

        Returns:
            The rendered attributes, with a leading space when non-empty.
        """
        parts = [
            f'{name}="{escape_attr(value)}"' for name, value in pairs.items() if value is not None
        ]
        return (" " + " ".join(parts)) if parts else ""

    def _epub_type(self, value: str) -> str:
        """Render an ``epub:type`` attribute when writing EPUB.

        Args:
            value: The semantic value.

        Returns:
            The attribute text, empty outside EPUB.
        """
        return f' epub:type="{value}"' if self.epub else ""

    # -- blocks ------------------------------------------------------------

    def blocks(self, nodes: Sequence[Block]) -> str:
        """Render a block sequence.

        Args:
            nodes: The blocks.

        Returns:
            The XHTML.
        """
        return "\n".join(self.block(node) for node in nodes if node is not None)

    def block(self, node: Block) -> str:
        """Render one block.

        Args:
            node: The block.

        Returns:
            The XHTML.
        """
        with self.context.at(f"{tag_of(node)}/"):
            self.context.count("nodes")
            self.context.audit_node_fields(node)
            handler = getattr(self, f"_block_{tag_of(node)}", None)
            if handler is None:
                self.context.audit_node(node)
                return f"<!-- no nao suportado: {tag_of(node)} -->"
            result = handler(node)
            return str(result)

    def _block_heading(self, node: Heading) -> str:
        level = max(1, min(6, node.level))
        anchor = self._anchor(node.anchor, node)
        text = self.inlines(node.content)
        if node.numbering_text:
            text = (
                f'<span class="number" data-generated="1">'
                f"{escape(node.numbering_text)}</span> {text}"
            )
        title = node.toc_text or inline_plain_text(node.content, self.context.document)
        if node.list_in_toc:
            self.headings.append((level, anchor, title))
        classes = " ".join(
            part for part in (self._paragraph_class(node.props, node), None) if part
        )
        run_class = self._run_class(node.run_props, node)
        attrs = self._attrs(
            {
                "id": anchor,
                "class": " ".join(part for part in (classes, run_class) if part) or None,
                "data-ir": "heading",
                "data-ir-id": str(node.id),
                "data-toc-text": node.toc_text,
                "data-anchor": node.anchor,
                "data-run-class": self._run_class(node.run_props, node),
                "data-numbering-text": node.numbering_text,
                "data-in-toc": None if node.list_in_toc else "0",
            }
        )
        return f"<h{level}{attrs}>{text}</h{level}>"

    def _block_paragraph(self, node: Paragraph) -> str:
        classes = [self._paragraph_class(node.props, node)]
        if node.drop_cap:
            classes.append("dropcap")
        attrs = self._attrs(
            {
                "class": " ".join(part for part in classes if part) or None,
                "data-ir": "paragraph",
                "data-ir-id": str(node.id),
                "data-drop-cap": str(node.drop_cap) if node.drop_cap else None,
            }
        )
        return f"<p{attrs}>{self.inlines(node.content)}</p>"

    def _block_list_block(self, node: ListBlock) -> str:
        if node.kind is ListKind.DEFINITION:
            items = []
            for item in node.items:
                self.context.count("nodes")
                self.context.audit_node(item)
                items.append(f"<dt>{self.inlines(item.term)}</dt>")
                items.append(
                    f'<dd data-ir="list_item" data-ir-id="{escape_attr(str(item.id))}">'
                    f"{self.blocks(item.content)}</dd>"
                )
            body = "\n".join(items)
            attrs = self._attrs(
                {
                    "class": self._paragraph_class(node.props, node),
                    "data-ir": "list_block",
                    "data-ir-id": str(node.id),
                    "data-kind": "definition",
                    "data-marker-style": node.marker_style.value,
                    "data-marker-text": node.marker_text,
                    "data-start": str(node.start),
                    "data-indent": _measure_attribute(node.indent),
                    "data-tight": "1" if node.tight else None,
                }
            )
            return f"<dl{attrs}>\n{body}\n</dl>"

        ordered = node.kind is ListKind.ORDERED
        tag = "ol" if ordered else "ul"
        style = _MARKER_CSS.get(node.marker_style, "disc" if not ordered else "decimal")
        declarations = {"list-style-type": style}
        if node.tight:
            declarations["--caissa-tight"] = "1"
        if node.indent is not None:
            declarations["padding-left"] = _measure_css(node.indent)
            declarations["--caissa-list-indent"] = _measure_css(node.indent) + (
                ":twip" if node.indent.unit is LengthUnit.TWIP else ""
            )
        if node.marker_text:
            declarations["--caissa-marker"] = f'"{node.marker_text}"'
        list_class = self.decorations.intern(declarations, declarations)
        classes = " ".join(
            part for part in (self._paragraph_class(node.props, node), list_class) if part
        )
        attrs = self._attrs(
            {
                "class": classes or None,
                "start": str(node.start) if ordered and node.start != 1 else None,
                "data-ir": "list_block",
                "data-ir-id": str(node.id),
                "data-marker-style": node.marker_style.value,
                "data-marker-text": node.marker_text,
                "data-start": str(node.start),
            }
        )
        items = "\n".join(self._list_item(item) for item in node.items)
        return f"<{tag}{attrs}>\n{items}\n</{tag}>"

    def _list_item(self, item: ListItem) -> str:
        """Render one list item.

        Args:
            item: The item.

        Returns:
            The XHTML.
        """
        self.context.count("nodes")
        attrs = self._attrs(
            {
                "data-ir": "list_item",
                "data-ir-id": str(item.id),
                # ``value`` is only legal on an <li> inside an <ol>; on a
                # bulleted list it is what makes a reader refuse the file.
                "data-start": str(item.start_override) if item.start_override else None,
                "data-marker": item.marker_override,
                "data-checked": None if item.checked is None else ("1" if item.checked else "0"),
            }
        )
        prefix = ""
        if item.checked is not None:
            checked = ' checked="checked"' if item.checked else ""
            prefix = f'<input type="checkbox" disabled="disabled"{checked}/> '
        return f"<li{attrs}>{prefix}{self.blocks(item.content)}</li>"

    def _block_quote(self, node: Quote) -> str:
        attribution = ""
        if node.attribution:
            attribution = (
                f'<span class="attribution">{self.inlines(node.attribution)}</span>'
            )
        attrs = self._attrs(
            {
                "class": self._paragraph_class(node.props, node),
                "data-ir": "quote",
                "data-ir-id": str(node.id),
            }
        )
        return f"<blockquote{attrs}>\n{self.blocks(node.content)}\n{attribution}</blockquote>"

    def _block_callout(self, node: Callout) -> str:
        title = self.inlines(node.title) if node.title else escape(_CALLOUT_LABEL[node.kind])
        extra = self._decoration_class(node)
        classes = " ".join(
            part
            for part in (
                "callout",
                f"callout-{node.kind.value}",
                self._paragraph_class(node.props, node),
                extra,
            )
            if part
        )
        attrs = self._attrs(
            {
                "class": classes,
                "data-ir": "callout",
                "data-ir-id": str(node.id),
                "data-kind": node.kind.value,
                "data-collapsed": "1" if node.collapsed else None,
            }
        )
        if node.collapsed:
            return (
                f"<details{attrs}><summary>{title}</summary>\n"
                f"{self.blocks(node.content)}\n</details>"
            )
        return (
            f'<aside{attrs}><p class="callout-title">{title}</p>\n'
            f"{self.blocks(node.content)}\n</aside>"
        )

    def _block_code_block(self, node: CodeBlock) -> str:
        run_class = self._run_class(node.run_props, node)
        attrs = self._attrs(
            {
                "class": " ".join(
                    part for part in (self._paragraph_class(node.props, node), run_class) if part
                )
                or None,
                "data-ir": "code_block",
                "data-run-class": self._run_class(node.run_props, node),
                "data-ir-id": str(node.id),
                "data-line-numbers": "1" if node.show_line_numbers else None,
            }
        )
        language = f' class="language-{escape_attr(node.language)}"' if node.language else ""
        return f"<pre{attrs}><code{language}>{escape(node.text)}</code></pre>"

    def _block_math_block(self, node: MathBlock) -> str:
        attrs = self._attrs(
            {
                "class": self._paragraph_class(node.props, node),
                "id": self._anchor(node.label, node) if node.label else None,
                "data-ir": "math_block",
                "data-ir-id": str(node.id),
                "data-tex": node.latex,
                "data-mathml": node.mathml,
                "data-display": "1" if node.display else "0",
                "data-numbered": "1" if node.numbered else None,
                "data-label": node.label,
            }
        )
        if node.mathml:
            return f'<div{attrs}>{_namespaced_mathml(node.mathml)}</div>'
        body = escape(node.latex)
        return f'<div{attrs}><span class="math">\\[{body}\\]</span></div>'

    def _block_table(self, node: Table) -> str:
        columns = ""
        if node.columns:
            cols = []
            for column in node.columns:
                declarations: dict[str, str] = {}
                if column.width is not None:
                    declarations["width"] = _measure_css(column.width)
                if column.min_width is not None:
                    declarations["min-width"] = _measure_css(column.min_width)
                if column.alignment is not None:
                    declarations["text-align"] = _ALIGN_CSS[column.alignment]
                    declarations["--caissa-align"] = column.alignment.value
                name = self.paragraphs.intern(declarations)
                cols.append(f'<col{self._attrs({"class": name})}/>')
            columns = f"<colgroup>{''.join(cols)}</colgroup>"

        header_rows = node.rows[: node.header_row_count]
        footer_start = len(node.rows) - node.footer_row_count if node.footer_row_count else None
        body_rows = node.rows[node.header_row_count : footer_start]
        footer_rows = node.rows[footer_start:] if footer_start is not None else ()

        parts: list[str] = []
        if node.caption:
            parts.append(f"<caption>{self.inlines(node.caption)}</caption>")
        parts.append(columns)
        if header_rows:
            parts.append(f"<thead>{''.join(self._row(row) for row in header_rows)}</thead>")
        parts.append(f"<tbody>{''.join(self._row(row) for row in body_rows)}</tbody>")
        if footer_rows:
            parts.append(f"<tfoot>{''.join(self._row(row) for row in footer_rows)}</tfoot>")

        declarations = {}
        if node.width is not None:
            declarations["width"] = _measure_css(node.width)
        if node.alignment is Alignment.LEFT:
            declarations["margin-left"] = "0"
            declarations["margin-right"] = "auto"
        elif node.alignment is Alignment.RIGHT:
            declarations["margin-left"] = "auto"
            declarations["margin-right"] = "0"
        table_class = self.paragraphs.intern(declarations)
        attrs = self._attrs(
            {
                "id": self._anchor(node.anchor, node) if node.anchor else None,
                "class": table_class,
                "data-ir": "table",
                "data-ir-id": str(node.id),
                "data-header-rows": str(node.header_row_count),
                "data-footer-rows": str(node.footer_row_count),
                "data-repeat-header": "1" if node.repeat_header else "0",
                "data-caption-above": "1" if node.caption_above else "0",
                "data-number": str(node.number) if node.number is not None else None,
                "data-style": node.style,
                "data-decoration": self.decorations.intern(
                    _table_decoration(node), _table_decoration(node)
                ),
                "data-alignment": node.alignment.value if node.alignment else None,
                "data-width": _measure_css(node.width) if node.width else None,
                "data-summary": node.summary,
            }
        )
        return f"<table{attrs}>{''.join(part for part in parts if part)}</table>"

    def _row(self, row: TableRow) -> str:
        """Render one table row.

        Args:
            row: The row.

        Returns:
            The XHTML.
        """
        self.context.count("nodes")
        attrs = self._attrs(
            {
                "data-ir": "table_row",
                "data-ir-id": str(row.id),
                "data-header": "1" if row.is_header else None,
                "data-repeat": "1" if row.repeat_on_break else None,
                "data-keep": "1" if row.keep_together else None,
                "data-height": _measure_css(row.height) if row.height else None,
            }
        )
        return f"<tr{attrs}>{''.join(self._cell(cell, row) for cell in row.cells)}</tr>"

    def _cell(self, cell: TableCell, row: TableRow) -> str:
        """Render one table cell.

        Args:
            cell: The cell.
            row: The row it sits in, which decides the header question when the
                cell does not.

        Returns:
            The XHTML.
        """
        self.context.count("nodes")
        tag = "th" if (cell.is_header or row.is_header) else "td"
        declarations: dict[str, str] = {}
        if cell.alignment is not None:
            declarations["text-align"] = _ALIGN_CSS[cell.alignment]
            declarations["--caissa-align"] = cell.alignment.value
        if cell.vertical_alignment is not None:
            declarations["vertical-align"] = cell.vertical_alignment.value
        classes = " ".join(
            name
            for name in (self.paragraphs.intern(declarations), self._decoration_class(cell))
            if name
        )
        attrs = self._attrs(
            {
                "class": classes or None,
                "rowspan": str(cell.row_span) if cell.row_span != 1 else None,
                "colspan": str(cell.col_span) if cell.col_span != 1 else None,
                "data-ir": "table_cell",
                "data-ir-id": str(cell.id),
                "data-is-header": "1" if cell.is_header else None,
            }
        )
        return f"<{tag}{attrs}>{self.blocks(cell.content)}</{tag}>"

    def _block_figure(self, node: Figure) -> str:
        caption = ""
        if node.caption or node.number is not None:
            label = node.label or (
                f"Figura {node.number}" if node.number is not None else ""
            )
            inner = self.inlines(node.caption)
            prefix = f'<span class="label">{escape(label)}</span> ' if label else ""
            caption = (
                f'<figcaption>{prefix}<span class="caption-text">{inner}</span></figcaption>'
            )
        attrs = self._attrs(
            {
                "id": self._anchor(node.anchor, node) if node.anchor else None,
                "class": self._paragraph_class(node.props, node),
                "data-ir": "figure",
                "data-ir-id": str(node.id),
                "data-number": str(node.number) if node.number is not None else None,
                "data-label": node.label,
                "data-placement": node.placement.value,
                "data-caption-above": "1" if node.caption_above else "0",
                "aria-label": node.alt_text,
            }
        )
        body = self.blocks(node.content)
        parts = [caption, body] if node.caption_above else [body, caption]
        return f"<figure{attrs}>\n{parts[0]}\n{parts[1]}\n</figure>"

    def _block_diagram(self, node: Diagram) -> str:
        rendered = self.diagrams.svg(node)
        self._record_diagram_losses(node)
        caption = self._diagram_caption(node)
        attrs = self._attrs(
            {
                "id": self._anchor(node.anchor, node) if node.anchor else None,
                "class": "diagram",
                "data-ir": "diagram",
                "data-alt": node.alt_text,
                "data-ir-id": str(node.id),
                "data-fen": node.fen,
                "data-orientation": node.orientation.value,
                "data-number": str(node.number) if node.number is not None else None,
                "data-label": node.label,
                "data-stipulation": node.stipulation,
                "data-move-context": node.move_context,
                "data-verified": "1" if node.verified_by_human else "0",
                "data-side-to-move": "1" if node.side_to_move_indicator else "0",
                "data-marks": _marks_data(node.marks) or None,
                "data-solution": (
                    game_to_pgn(node.solution, include_headers=False).strip()
                    if node.solution is not None
                    else None
                ),
            }
        )
        svg = _svg_with_alt(rendered, node.alt_text or rendered.alt_text)
        parts = [caption, svg] if _caption_above(node) else [svg, caption]
        return f"<figure{attrs}>\n{parts[0]}\n{parts[1]}\n</figure>"

    def _diagram_caption(self, node: Diagram) -> str:
        """Render a diagram caption.

        Args:
            node: The diagram.

        Returns:
            The ``<figcaption>``, or an empty string.
        """
        pieces: list[str] = []
        label = node.label or (
            f"Diagrama {node.number}" if node.number is not None else ""
        )
        if label:
            pieces.append(f'<span class="label">{escape(label)}</span>')
        if node.stipulation:
            pieces.append(f'<span class="stipulation">{escape(node.stipulation)}</span>')
        if node.caption:
            pieces.append(f'<span class="caption-text">{self.inlines(node.caption)}</span>')
        if not pieces:
            return ""
        return f"<figcaption>{' '.join(pieces)}</figcaption>"

    def _record_diagram_losses(self, node: Diagram) -> None:
        """Record the diagram data XHTML deliberately does not carry.

        Args:
            node: The diagram.
        """
        if node.recognition.per_square_confidence or node.recognition.model_name:
            self.context.recorder.unsupported(
                prop="recognition",
                node=node,
                path=self.context.path,
                original="confianca por casa e identidade do modelo",
                detail=(
                    "XHTML carrega o documento, nao a auditoria do reconhecimento; a "
                    "proveniencia fica no arquivo .caissa.json quando a exportacao o inclui."
                ),
            )
        if node.source.path or node.source.page_index is not None:
            self.context.recorder.unsupported(
                prop="source",
                node=node,
                path=self.context.path,
                original=node.source.path or "pagina de origem",
                detail="XHTML nao carrega o retangulo de origem do diagrama.",
            )

    def _block_image_block(self, node: ImageBlock) -> str:
        resource = self.context.document.resource(node.resource)
        if not _resource_available(resource):
            self.context.audit_feature(
                "images", node=node, original=node.resource
            )
            return self._missing_image(node, inline=False)
        declarations: dict[str, str] = {}
        if node.width is not None:
            declarations["width"] = _measure_css(node.width)
        if node.height is not None:
            declarations["height"] = _measure_css(node.height)
        attrs = self._attrs(
            {
                "src": _resource_href(resource, node.resource),
                "alt": node.alt_text or "",
                "title": node.title,
                "class": self.paragraphs.intern(declarations),
                "data-ir": "image_block",
                "data-ir-id": str(node.id),
                "data-resource": node.resource,
                "data-crop": ",".join(_num(value) for value in node.crop) or None,
                "data-alignment": node.alignment.value if node.alignment else None,
            }
        )
        if node.alt_text is None:
            self.context.recorder.unsupported(
                prop="alt_text",
                node=node,
                path=self.context.path,
                detail=(
                    "A imagem nao tem descricao alternativa; EPUB e PDF marcado exigem uma."
                ),
            )
        return f"<img{attrs}/>"

    def _block_game_score(self, node: Any) -> str:
        from caissa.core.model import GameScore

        assert isinstance(node, GameScore)
        pgn = game_to_pgn(node)
        headers = ""
        if node.render.show_headers:
            names = f"{escape(node.headers.white)} &#8211; {escape(node.headers.black)}"
            place = ", ".join(
                part
                for part in (node.headers.event, node.headers.site, node.headers.date)
                if part and part not in ("?", "????.??.??")
            )
            headers = (
                f'<p class="headers">{names}'
                + (f" &#183; {escape(place)}" if place else "")
                + f" &#183; {escape(node.headers.result)}</p>"
            )
        title = f"<p class=\"game-title\">{escape(node.title)}</p>" if node.title else ""
        board = ""
        if self.interactive:
            start = node.initial_fen or _START_FEN
            board = (
                f'<div data-board="1" data-fen-start="{escape_attr(start)}" '
                f'data-fen="{escape_attr(start)}"></div>'
            )
        moves = self._movetext(node)
        attrs = self._attrs(
            {
                "class": "game",
                "data-ir": "game_score",
                "data-ir-id": str(node.id),
                "data-pgn": pgn.strip(),
                "data-variant": node.variant,
                "data-initial-fen": node.initial_fen,
                "data-annotator": node.annotator,
                "data-language": node.render.language,
                "data-render": node.render.render.value,
                "data-variation-style": node.render.variation_style.value,
            }
        )
        comment = (
            f'<span class="comment">{escape(node.initial_comment)}</span> '
            if node.initial_comment
            else ""
        )
        return (
            f"<div{attrs}>\n{title}{headers}{board}"
            f'<p class="movetext">{comment}{moves}</p>\n</div>'
        )

    def _movetext(self, score: Any) -> str:
        """Render a game's movetext with variations and comments.

        Args:
            score: The game score.

        Returns:
            The XHTML.
        """
        parts: list[str] = []
        self._movetext_line(score.children, parts, force_number=True, depth=0)
        return " ".join(parts)

    def _movetext_line(
        self, children: Sequence[Any], parts: list[str], *, force_number: bool, depth: int
    ) -> None:
        """Render one line of movetext, recursing only into variations.

        Args:
            children: Continuations; ``children[0]`` is the mainline.
            parts: The output fragments being built.
            force_number: Print the number even for a Black move.
            depth: Variation nesting depth, for styling.
        """
        current = children
        needs_number = force_number
        while current:
            main = current[0]
            needs_number = self._movetext_single(main, parts, needs_number, depth)
            for alternative in current[1:]:
                inner: list[str] = []
                self._movetext_line((alternative,), inner, force_number=True, depth=depth + 1)
                parts.append(
                    f'<span class="variation" data-depth="{depth + 1}">'
                    f"({' '.join(inner)})</span>"
                )
                needs_number = True
            current = main.children

    def _movetext_single(
        self, node: Any, parts: list[str], force_number: bool, depth: int
    ) -> bool:
        """Render one move of movetext.

        Args:
            node: The move node.
            parts: The output fragments being built.
            force_number: Print the number even for a Black move.
            depth: Variation nesting depth.

        Returns:
            Whether the next move needs an explicit number.
        """
        self.context.count("nodes")
        if node.comment_before:
            parts.append(f'<span class="comment">{escape(node.comment_before)}</span>')
            force_number = True
        number = ""
        if not node.is_black_move:
            number = f"{node.move_number}."
        elif force_number:
            number = f"{node.move_number}&#8230;"
        settings = self.context.document.settings
        move = Move(
            san=node.san,
            ply=node.ply,
            language=settings.notation_language,
            render=settings.move_render,
            figurine_set=settings.figurine_set,
        )
        rendered = render_move(move, self.context.document)
        nags = "".join(nag_symbol(nag) for nag in node.nags)
        attrs = self._attrs(
            {
                "class": "move" + (" key" if node.emphasis else ""),
                "data-ir": "move_node",
                "data-ir-id": str(node.id),
                "data-san": node.san,
                "data-ply": str(node.ply),
                "data-uci": node.uci,
                "data-nags": ",".join(str(nag) for nag in node.nags) or None,
                "data-fen-before": node.position_before or None,
                "data-fen-after": node.position_after or None,
                "data-depth": str(depth) if depth else None,
                "data-emphasis": "1" if node.emphasis else None,
                "data-clock": node.clock.text if node.clock is not None else None,
                "data-clock-kind": node.clock.kind.value if node.clock is not None else None,
                "data-eval": node.evaluation.text if node.evaluation is not None else None,
                "data-arrows": _marks_data(node.arrows) or None,
                "data-highlights": _marks_data(node.highlights) or None,
            }
        )
        parts.append(f"<span{attrs}>{number}{escape(rendered)}{escape(nags)}</span>")
        trailing = node.comment_after
        if trailing:
            parts.append(f'<span class="comment">{escape(trailing)}</span>')
            return True
        return False

    def _block_footnote(self, node: Footnote) -> str:
        self.notes.append(node)
        return self._note_slot(node)

    def _block_endnote(self, node: Endnote) -> str:
        self.notes.append(node)
        return self._note_slot(node)

    def _note_slot(self, node: Footnote | Endnote) -> str:
        """Mark where in the story a note stood.

        The note body itself goes to the notes section at the end, which is
        where a reader looks for it and where ``epub:type="footnotes"`` says it
        belongs. What stays behind is an empty, hidden element carrying the
        note's identity, so reopening the file puts the note back in the place
        the author wrote it instead of at the bottom of the book.

        Args:
            node: The note.

        Returns:
            The slot element.
        """
        attrs = self._attrs(
            {
                "class": "note-slot",
                "data-ir": "note_slot",
                "data-ir-id": str(node.id),
                "hidden": "hidden",
            }
        )
        return f"<div{attrs}></div>"

    def _block_page_break(self, node: PageBreak) -> str:
        self.context.audit_feature("page_geometry", node=node, original="quebra de pagina")
        return (
            f'<hr class="page-break" data-ir="page_break" '
            f'data-ir-id="{escape_attr(str(node.id))}"/>'
        )

    def _block_section_break(self, node: SectionBreak) -> str:
        for feature, present in (
            ("columns", node.columns is not None),
            ("page_geometry", node.geometry is not None),
            ("headers_footers", bool(node.header_text or node.footer_text)),
        ):
            if present:
                self.context.audit_feature(feature, node=node, original=node.kind.value)
        attrs = self._attrs(
            {
                "class": "section-break",
                "data-ir": "section_break",
                "data-ir-id": str(node.id),
                "data-kind": node.kind.value,
                "data-columns": str(node.columns.count) if node.columns else None,
                "data-column-gap": (
                    _measure_css(node.columns.gap)
                    + (":twip" if node.columns.gap.unit is LengthUnit.TWIP else "")
                    if node.columns and node.columns.gap
                    else None
                ),
                "data-column-rule": _column_rule(node.columns),
                "data-column-balanced": (
                    ("1" if node.columns.balanced else "0") if node.columns else None
                ),
                "data-column-widths": (
                    " ".join(_measure_css(width) for width in node.columns.widths)
                    if node.columns and node.columns.widths
                    else None
                ),
                "data-page-number-start": (
                    str(node.page_number_start) if node.page_number_start else None
                ),
                "data-page-number-format": node.page_number_format,
                "data-different-first": "1" if node.different_first_page else None,
                "data-different-odd-even": "1" if node.different_odd_even else None,
                "data-geometry": _geometry_data(node.geometry),
            }
        )
        # The running heads are inline content, not a string: a header with a
        # move in it is a move, and flattening it to text would lose the move.
        parts = [
            f'<span class="running-{name}">{self.inlines(nodes)}</span>'
            for name, nodes in (("head", node.header_text), ("foot", node.footer_text))
            if nodes
        ]
        return f"<div{attrs}>{''.join(parts)}</div>"

    def _block_thematic_break(self, node: ThematicBreak) -> str:
        if node.ornament:
            attrs = self._attrs(
                {
                    "class": "ornament",
                    "data-ir": "thematic_break",
                    "data-ir-id": str(node.id),
                    "data-ornament": node.ornament,
                }
            )
            return f"<p{attrs}>{escape(node.ornament)}</p>"
        declarations: dict[str, str] = {}
        if node.rule is not None:
            width = _measure_css(node.rule.width) if node.rule.width else "1px"
            colour = _color_css(node.rule.color) if node.rule.color else "currentColor"
            declarations["border-top"] = f"{width} {node.rule.style.value} {colour}"
        attrs = self._attrs(
            {
                "class": self.paragraphs.intern(declarations),
                "data-ir": "thematic_break",
                "data-ir-id": str(node.id),
            }
        )
        return f"<hr{attrs}/>"

    def _block_group(self, node: Group) -> str:
        tag = _ROLE_TAG.get(node.role, "div")
        declarations: dict[str, str] = {}
        if node.columns:
            declarations["column-count"] = str(node.columns)
            self.context.audit_feature("columns", node=node, original=str(node.columns))
        classes = " ".join(
            part
            for part in (
                self._paragraph_class(node.props, node),
                self.paragraphs.intern(declarations),
                "columns" if node.columns else None,
            )
            if part
        )
        attrs = self._attrs(
            {
                "id": self._anchor(node.anchor, node) if node.anchor else None,
                "class": classes or None,
                "data-ir": "group",
                "data-ir-id": str(node.id),
                "data-role": node.role.value,
                "data-columns": str(node.columns) if node.columns else None,
                "data-title": inline_plain_text(node.title, self.context.document) or None,
            }
        )
        title = (
            f'<p class="group-title">{self.inlines(node.title)}</p>' if node.title else ""
        )
        return f"<{tag}{attrs}>\n{title}{self.blocks(node.content)}\n</{tag}>"

    def _block_table_of_contents(self, node: TableOfContents) -> str:
        self.context.audit_feature("toc_field", node=node, original="sumario")
        attrs = self._attrs(
            {
                "class": "toc",
                "data-ir": "table_of_contents",
                "data-ir-id": str(node.id),
                "data-min-level": str(node.min_level),
                "data-max-level": str(node.max_level),
                "data-page-numbers": "1" if node.show_page_numbers else "0",
                "data-leader": "1" if node.leader else "0",
                "data-scope": node.scope,
            }
        )
        # The default heading is ours, not the author's; saying so stops a
        # re-import handing it back as a title the document never had.
        title = (
            f"<h2>{self.inlines(node.title)}</h2>"
            if node.title
            else '<h2 data-generated="1">Sum&#225;rio</h2>'
        )
        return f"<nav{attrs} data-toc-placeholder=\"1\">\n{title}\n</nav>"

    def _block_raw_passthrough(self, node: RawPassthrough) -> str:
        if node.format.lower() in ("html", "xhtml", "html5"):
            return node.text
        self.context.audit_feature("raw_passthrough", node=node, original=node.format)
        return (
            f'<div class="raw" data-ir="raw_passthrough" data-ir-id="{escape_attr(str(node.id))}" '
            f'data-format="{escape_attr(node.format)}" hidden="hidden">{escape(node.text)}</div>'
        )

    # -- inlines -----------------------------------------------------------

    def inlines(self, nodes: Sequence[Inline]) -> str:
        """Render an inline sequence.

        Args:
            nodes: The inlines.

        Returns:
            The XHTML.
        """
        return "".join(self.inline(node) for node in nodes)

    def inline(self, node: Inline) -> str:
        """Render one inline.

        Args:
            node: The inline.

        Returns:
            The XHTML.
        """
        self.context.count("nodes")
        self.context.audit_node_fields(node)
        handler = getattr(self, f"_inline_{tag_of(node)}", None)
        if handler is None:
            self.context.audit_node(node)
            return ""
        return str(handler(node))

    def _wrap(self, tag: str, node: Any, extra: Mapping[str, str | None] | None = None) -> str:
        """Render a wrapper inline as an element.

        Args:
            tag: The HTML tag.
            node: The wrapper node.
            extra: Extra attributes.

        Returns:
            The XHTML.
        """
        attributes: dict[str, str | None] = {
            "class": self._run_class(node.props, node),
            "data-ir": tag_of(node),
            "data-ir-id": str(node.id),
        }
        if extra:
            attributes.update(extra)
        return f"<{tag}{self._attrs(attributes)}>{self.inlines(node.content)}</{tag}>"

    def _inline_text(self, node: Text) -> str:
        # A run with no formatting used to be emitted as bare text, which is
        # smaller and loses the node: reading the page back merged it into its
        # neighbours and gave it a new identity. A book of plain prose scored
        # worse on the fidelity gate than a book of exotic typography, which is
        # the wrong way round. Every run keeps its span.
        attrs = self._attrs(
            {
                "class": self._run_class(node.props, node),
                "data-ir": "text",
                "data-ir-id": str(node.id),
            }
        )
        return f"<span{attrs}>{escape(node.content)}</span>"

    def _inline_emphasis(self, node: Emphasis) -> str:
        return self._wrap("em", node)

    def _inline_strong(self, node: Strong) -> str:
        return self._wrap("strong", node)

    def _inline_underline(self, node: Underline) -> str:
        return self._wrap("u", node)

    def _inline_strike(self, node: Strike) -> str:
        return self._wrap("s", node)

    def _inline_small_caps(self, node: SmallCaps) -> str:
        klass = self._run_class(node.props, node)
        classes = " ".join(part for part in ("sc", klass) if part)
        return (
            f'<span class="{classes}" data-ir="small_caps" '
            f'data-ir-id="{escape_attr(str(node.id))}">{self.inlines(node.content)}</span>'
        )

    def _inline_superscript(self, node: Superscript) -> str:
        return self._wrap("sup", node)

    def _inline_subscript(self, node: Subscript) -> str:
        return self._wrap("sub", node)

    def _inline_span(self, node: Span) -> str:
        return self._wrap("span", node)

    def _inline_link(self, node: Link) -> str:
        href = node.target
        if node.kind is LinkKind.INTERNAL and not href.startswith("#"):
            href = f"#{href}"
        elif node.kind is LinkKind.EMAIL and not href.startswith("mailto:"):
            # A mail link whose target is a fragment is not a mail address, and
            # a reader that validates URIs rejects the file over it.
            href = f"mailto:{href}" if "@" in href else href.lstrip("#") or "#"
            if not href.startswith("mailto:"):
                href = f"#{href}"
        if self._in_link:
            # XHTML forbids an anchor inside an anchor. The inner one keeps its
            # identity and its target as data, and stops being a link.
            return self._wrap(
                "span",
                node,
                {
                    "data-link-kind": node.kind.value,
                    "data-target": node.target,
                    "data-tooltip": node.tooltip,
                    "data-title": node.title,
                    "data-nested-link": "1",
                },
            )
        self._in_link = True
        try:
            return self._link_element(node, href)
        finally:
            self._in_link = False

    def _link_element(self, node: Link, href: str) -> str:
        """Render the anchor itself.

        Args:
            node: The link.
            href: The resolved target.

        Returns:
            The XHTML.
        """
        return self._wrap(
            "a",
            node,
            {
                "href": href,
                "title": node.tooltip or node.title,
                "data-link-kind": node.kind.value,
                "data-target": node.target,
                "data-tooltip": node.tooltip,
                "data-title": node.title,
            },
        )

    def _inline_move(self, node: Move) -> str:
        klass = self._run_class(node.props, node)
        attrs = self._attrs(
            {
                "class": " ".join(part for part in ("move", klass) if part),
                "data-ir": "move",
                "data-ir-id": str(node.id),
                "data-san": node.san,
                "data-ply": str(node.ply),
                "data-uci": node.uci,
                "data-fen-before": node.position_before or None,
                "data-nags": ",".join(str(nag) for nag in node.nags) or None,
                "data-language": node.language,
                "data-render": node.render.value,
                "data-figurine-set": node.figurine_set.value,
                "data-show-number": "1" if node.show_move_number else None,
                "data-number-text": node.move_number_text,
            }
        )
        return f"<span{attrs}>{escape(render_move(node, self.context.document))}</span>"

    def _inline_piece_glyph(self, node: Any) -> str:
        klass = self._run_class(node.props, node)
        declarations = (
            {"font-family": _quote_family(node.font_family)} if node.font_family else {}
        )
        # The face the glyph needs is the *node's* font, not the run's: putting
        # it in the run rule would hand it back as a run property on re-import.
        family_class = self.decorations.intern(declarations, declarations)
        attrs = self._attrs(
            {
                "class": " ".join(
                    part for part in ("piece", klass, family_class) if part
                ),
                "data-ir": "piece_glyph",
                "data-ir-id": str(node.id),
                "data-piece": node.piece.value,
                "data-figurine-set": node.figurine_set.value,
                "data-font-family": node.font_family,
            }
        )
        glyph = _glyph_for(node)
        return f"<span{attrs}>{escape(glyph)}</span>"

    def _inline_nag_symbol(self, node: NagSymbol) -> str:
        klass = self._run_class(node.props, node)
        attrs = self._attrs(
            {
                "class": " ".join(part for part in ("nag", klass) if part),
                "data-ir": "nag_symbol",
                "data-ir-id": str(node.id),
                "data-nag": str(node.nag),
            }
        )
        return f"<span{attrs}>{escape(nag_symbol(node.nag))}</span>"

    def _inline_note_ref(self, node: NoteRef) -> str:
        klass = self._run_class(node.props, node)
        marker = node.marker or str(len(self.notes) + 1)
        if self._in_link:
            inner = self._attrs(
                {
                    "class": " ".join(part for part in ("noteref", klass) if part),
                    "data-ir": "note_ref",
                    "data-ir-id": str(node.id),
                    "data-ref": node.ref,
                    "data-marker": node.marker,
                }
            )
            return f"<span{inner}><sup>{escape(marker)}</sup></span>"
        attrs = self._attrs(
            {
                "class": " ".join(part for part in ("noteref", klass) if part),
                "href": f"#note-{node.ref}",
                "id": f"ref-{node.ref}",
                "data-ir": "note_ref",
                "data-ir-id": str(node.id),
                "data-ref": node.ref,
                "data-marker": node.marker,
            }
        )
        semantics = self._epub_type("noteref")
        return f"<a{attrs}{semantics}><sup>{escape(marker)}</sup></a>"

    def _inline_inline_diagram(self, node: InlineDiagram) -> str:
        rendered = self.diagrams.svg(node)
        attrs = self._attrs(
            {
                "class": "diagram-inline",
                "data-ir": "inline_diagram",
                "data-ir-id": str(node.id),
                "data-fen": node.fen,
                "data-orientation": node.orientation.value,
                "data-size": _measure_css(node.size) if node.size else None,
                "data-style": node.style,
                "data-marks": _marks_data(node.marks) or None,
                "data-alt": node.alt_text,
            }
        )
        svg = _svg_with_alt(rendered, node.alt_text or rendered.alt_text)
        return f"<span{attrs}>{svg}</span>"

    def _inline_math_inline(self, node: MathInline) -> str:
        klass = self._run_class(node.props, node)
        attrs = self._attrs(
            {
                "class": " ".join(part for part in ("math", klass) if part),
                "data-ir": "math_inline",
                "data-mathml": node.mathml,
                "data-ir-id": str(node.id),
                "data-tex": node.latex,
            }
        )
        if node.mathml:
            return f"<span{attrs}>{_namespaced_mathml(node.mathml)}</span>"
        return f"<span{attrs}>\\({escape(node.latex)}\\)</span>"

    def _inline_image_inline(self, node: ImageInline) -> str:
        resource = self.context.document.resource(node.resource)
        if not _resource_available(resource):
            self.context.audit_feature(
                "images", node=node, original=node.resource
            )
            return self._missing_image(node, inline=True)
        declarations: dict[str, str] = {}
        twips: list[str] = []
        for name, value in (
            ("width", node.width),
            ("height", node.height),
            ("vertical-align", node.baseline_shift),
        ):
            if value is None:
                continue
            declarations[name] = _measure_css(value)
            if value.unit is LengthUnit.TWIP:
                twips.append(name)
        for name in twips:
            declarations[f"--caissa-twip-{name}"] = "1"
        attrs = self._attrs(
            {
                "src": _resource_href(resource, node.resource),
                "alt": node.alt_text or "",
                "class": self.runs.intern(declarations),
                "data-ir": "image_inline",
                "data-ir-id": str(node.id),
                "data-resource": node.resource,
            }
        )
        return f"<img{attrs}/>"

    def _missing_image(self, node: Any, *, inline: bool) -> str:
        """Render an image whose file the package does not contain.

        Emitting ``<img src="assets/capa.png">`` for a file that is not there
        is how an EPUB fails validation and a reader shows a broken box. The
        node is kept -- with its identity, its key and its description -- as
        text, and the export report says the file was missing.

        Args:
            node: The image node.
            inline: Whether it sat in a run rather than on its own.

        Returns:
            The XHTML.
        """
        tag = "span" if inline else "div"
        declarations: dict[str, str] = {}
        twips: list[str] = []
        for name, value in (
            ("width", node.width),
            ("height", node.height),
            ("vertical-align", getattr(node, "baseline_shift", None)),
        ):
            if value is None:
                continue
            declarations[name] = _measure_css(value)
            if value.unit is LengthUnit.TWIP:
                twips.append(name)
        for name in twips:
            declarations[f"--caissa-twip-{name}"] = "1"
        registry = self.runs if inline else self.paragraphs
        attrs = self._attrs(
            {
                "class": " ".join(
                    part
                    for part in ("image-missing", registry.intern(declarations, declarations))
                    if part
                ),
                "data-ir": tag_of(node),
                "data-ir-id": str(node.id),
                "data-resource": node.resource,
                "data-alt": getattr(node, "alt_text", None),
                "data-title": getattr(node, "title", None),
                "data-alignment": (
                    node.alignment.value if getattr(node, "alignment", None) else None
                ),
                "data-crop": (
                    ",".join(_num(part) for part in node.crop)
                    if getattr(node, "crop", ())
                    else None
                ),
                "data-missing": "1",
            }
        )
        label = escape(getattr(node, "alt_text", None) or node.resource)
        return f"<{tag}{attrs}>[{label}]</{tag}>"

    def _inline_anchor(self, node: Anchor) -> str:
        anchor = self._anchor(node.name, node)
        attrs = self._attrs(
            {
                "id": anchor,
                "class": "anchor",
                "data-ir": "anchor",
                "data-ir-id": str(node.id),
                "data-name": node.name,
                "data-title": node.title,
            }
        )
        # An anchor target is any element with an id; using <a> for it puts an
        # anchor inside an anchor whenever the target sits inside a link, and
        # XHTML forbids that.
        return f"<span{attrs}></span>"

    def _inline_index_entry(self, node: IndexEntry) -> str:
        anchor = self._anchor(f"idx-{node.id}", node)
        self.index_entries.append((node.terms, anchor))
        self.context.audit_feature("index_entry", node=node, original=" > ".join(node.terms))
        attrs = self._attrs(
            {
                "id": anchor,
                "class": "index-entry",
                "data-ir": "index_entry",
                "data-ir-id": str(node.id),
                "data-terms": "|".join(node.terms),
                "data-sort-key": node.sort_key,
                "data-see-also": "|".join(node.see_also) or None,
                "data-primary": "1" if node.primary else None,
            }
        )
        return f"<span{attrs}></span>"

    def _inline_line_break(self, node: LineBreak) -> str:
        return f'<br data-ir-id="{escape_attr(str(node.id))}"/>'

    def _inline_non_breaking_space(self, node: NonBreakingSpace) -> str:
        return (
            f'<span data-ir="non_breaking_space" '
            f'data-ir-id="{escape_attr(str(node.id))}">&#160;</span>'
        )

    def _inline_space(self, node: Space) -> str:
        char = _SPACE_CHARS.get(node.kind, " ")
        return (
            f'<span data-ir="space" data-kind="{node.kind.value}" '
            f'data-ir-id="{escape_attr(str(node.id))}">&#{ord(char)};</span>'
        )

    def _inline_tab(self, node: Tab) -> str:
        return (
            f'<span class="tab" data-ir="tab" '
            f'data-ir-id="{escape_attr(str(node.id))}">&#9;</span>'
        )

    def _inline_raw_inline(self, node: RawInline) -> str:
        if node.format.lower() in ("html", "xhtml", "html5"):
            return node.text
        self.context.audit_feature("raw_passthrough", node=node, original=node.format)
        return (
            f'<span class="raw" data-ir="raw_inline" data-ir-id="{escape_attr(str(node.id))}" '
            f'data-format="{escape_attr(node.format)}" hidden="hidden">{escape(node.text)}</span>'
        )

    # -- trailing matter ---------------------------------------------------

    def notes_section(self) -> str:
        """Render the collected footnotes and endnotes.

        Returns:
            The XHTML, or an empty string when the document has no notes.
        """
        if not self.notes:
            return ""
        items: list[str] = []
        for index, note in enumerate(self.notes, start=1):
            marker = note.marker or str(index)
            kind = "footnote" if isinstance(note, Footnote) else "endnote"
            attrs = self._attrs(
                {
                    "id": f"note-{note.ref}",
                    "class": " ".join(
                        part
                        for part in ("footnote", self._paragraph_class(note.props, note))
                        if part
                    ),
                    "data-ir": kind,
                    "data-ir-id": str(note.id),
                    "data-ref": note.ref,
                    "data-marker": note.marker,
                }
            )
            back = f'<a class="backref" href="#ref-{escape_attr(note.ref)}">&#8617;</a>'
            items.append(
                f"<aside{attrs}{self._epub_type(kind)}>"
                f'<span class="marker">{escape(marker)}</span> '
                f"{self.blocks(note.content)} {back}</aside>"
            )
        semantics = self._epub_type("footnotes")
        return (
            f'<section class="footnotes"{semantics}>'
            f"<h2>Notas</h2>\n" + "\n".join(items) + "\n</section>"
        )

    def toc_html(self, *, hrefs: Mapping[str, str] | None = None) -> str:
        """Render a nested table of contents from the headings seen so far.

        Args:
            hrefs: Optional map from anchor to a cross-file href, for site and
                EPUB output where the target is in another document.

        Returns:
            The ``<ol>`` tree, empty when there are no headings.
        """
        if not self.headings:
            return ""
        return _nested_list(self.headings, hrefs or {})

    def index_html(self) -> str:
        """Render the back-of-book index from the entries seen so far.

        Returns:
            The XHTML, empty when the document has no index entries.
        """
        if not self.index_entries:
            return ""
        grouped: dict[tuple[str, ...], list[str]] = {}
        for terms, anchor in self.index_entries:
            grouped.setdefault(terms, []).append(anchor)
        lines: list[str] = []
        for terms in sorted(grouped, key=lambda item: [part.lower() for part in item]):
            anchors = grouped[terms]
            links = ", ".join(
                f'<a href="#{escape_attr(anchor)}">{index + 1}</a>'
                for index, anchor in enumerate(anchors)
            )
            depth = len(terms) - 1
            lines.append(
                f'<li class="index-level-{depth}">{escape(" &#8212; ".join(terms))} {links}</li>'
            )
        return (
            '<section class="index"><h2>&#205;ndice remissivo</h2><ul>'
            + "".join(lines)
            + "</ul></section>"
        )

    def stylesheet(self) -> str:
        """Render the generated rules.

        Returns:
            The CSS for the interned run and paragraph classes.
        """
        parts = [
            self.paragraphs.stylesheet(),
            self.runs.stylesheet(),
            self.decorations.stylesheet(),
        ]
        return "\n".join(part for part in parts if part)


_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


_GEOMETRY_FIELDS: tuple[str, ...] = (
    "width",
    "height",
    "margin_top",
    "margin_bottom",
    "margin_inner",
    "margin_outer",
    "gutter",
)

_GEOMETRY_FLAGS: tuple[str, ...] = ("landscape", "mirror_margins")


def _table_decoration(node: Any) -> dict[str, str]:
    """Render a table's own borders and cell padding as a declaration block.

    Args:
        node: The :class:`~caissa.core.model.blocks.Table`.

    Returns:
        The declarations, empty when the table is undecorated.
    """
    return paragraph_props_to_css(
        ParagraphProps(borders=node.borders, padding=node.cell_padding)
    )


def _column_rule(columns: Any) -> str | None:
    """Render a column rule as a CSS border shorthand.

    Args:
        columns: The :class:`~caissa.core.model.blocks.ColumnLayout`, or
            ``None``.

    Returns:
        The shorthand, or ``None``.
    """
    if columns is None or columns.rule is None:
        return None
    border = columns.rule
    width = _measure_css(border.width) if border.width else "1px"
    if border.color is None:
        return f"{width} {border.style.value}"
    return f"{width} {border.style.value} {_color_css(border.color)}"


def _geometry_data(geometry: Any) -> str | None:
    """Encode a page geometry for the markup.

    CSS Paged Media can express the page box but not the header and gutter
    distances a book actually needs, and ``@page`` cannot be attached to one
    element anyway. The values ride on the section break that declared them.

    Args:
        geometry: The :class:`~caissa.core.model.blocks.PageGeometry`, or
            ``None``.

    Returns:
        A ``name=value`` list, or ``None`` when there is no geometry.
    """
    if geometry is None:
        return None
    parts = [
        f"{flag}={'1' if getattr(geometry, flag, False) else '0'}"
        for flag in _GEOMETRY_FLAGS
    ]
    for name in _GEOMETRY_FIELDS:
        value = getattr(geometry, name, None)
        if value is not None:
            # ``twip`` is not a CSS unit, and a page width that came back in
            # points is a different value, not the same one written differently.
            suffix = ":twip" if value.unit is LengthUnit.TWIP else ""
            parts.append(f"{name}={_measure_css(value)}{suffix}")
    return " ".join(parts)


def _geometry_from_data(text: str | None) -> Any:
    """Decode a page geometry written by :func:`_geometry_data`.

    Args:
        text: The attribute value, or ``None``.

    Returns:
        The geometry, or ``None``.
    """
    if not text:
        return None
    from caissa.core.model import PageGeometry

    values: dict[str, Any] = {}
    for part in text.split():
        name, _, raw = part.partition("=")
        if name in _GEOMETRY_FLAGS:
            values[name] = raw == "1"
        elif name in _GEOMETRY_FIELDS:
            text, _, marker = raw.partition(":")
            values[name] = _twip_back(_css_measure(text), marker == "twip")
    return PageGeometry(**values)


def _caption_above(node: Diagram) -> bool:
    """Whether a diagram's caption sits above the board.

    Args:
        node: The diagram.

    Returns:
        Whether to print the caption first.
    """
    position = node.style.caption_position
    return position is not None and position.value == "above"


def _svg_with_alt(rendered: RenderedDiagram, alt: str) -> str:
    """Attach an accessible label to a rendered SVG.

    Args:
        rendered: The rendered diagram.
        alt: The description.

    Returns:
        The SVG with ``role`` and ``aria-label`` set, and a ``<title>`` child
        for readers that prefer it.
    """
    svg = rendered.svg
    close = svg.find(">")
    if close < 0:
        return svg
    head = svg[:close]
    head = re.sub(r'\s+aria-label="[^"]*"', "", head)
    head = re.sub(r'\s+role="[^"]*"', "", head)
    title = f"<title>{escape(alt)}</title>"
    return f'{head} role="img" aria-label="{escape_attr(alt)}">{title}{svg[close + 1 :]}'


def _marks_data(marks: Sequence[Any]) -> str:
    """Encode board marks compactly for a data attribute.

    Args:
        marks: The marks.

    Returns:
        A semicolon-separated encoding, empty when there are none.
    """
    parts: list[str] = []
    for mark in marks:
        colour = mark.color.to_hex() if mark.color is not None else ""
        parts.append(
            ",".join(
                [
                    mark.kind.value,
                    "+".join(mark.squares),
                    colour,
                    mark.line_style.value,
                    _num(mark.opacity) if mark.opacity is not None else "",
                    (mark.text or "").replace(",", "&#44;").replace(";", "&#59;"),
                    str(mark.layer),
                    "1" if mark.filled else "0",
                    (
                        _measure_css(mark.width)
                        + (":twip" if mark.width.unit is LengthUnit.TWIP else "")
                        if mark.width is not None
                        else ""
                    ),
                    _ink_custom_property(mark.color) or "" if mark.color else "",
                ]
            )
        )
    return ";".join(parts)


def _parse_marks(text: str) -> tuple[Any, ...]:
    """Decode the mark encoding produced by :func:`_marks_data`.

    Args:
        text: The attribute value.

    Returns:
        The marks.
    """
    from caissa.core.model import Mark, MarkKind, MarkLineStyle

    marks: list[Any] = []
    for part in text.split(";"):
        if not part:
            continue
        fields = part.split(",")
        while len(fields) < 10:
            fields.append("")
        kind, squares, colour, line_style, opacity, label, layer, filled, width, ink = (
            fields[:10]
        )
        marks.append(
            Mark(
                kind=MarkKind(kind),
                squares=tuple(square for square in squares.split("+") if square),
                color=_parse_ink(ink) if ink else (Color.from_hex(colour) if colour else None),
                line_style=MarkLineStyle(line_style) if line_style else MarkLineStyle.SOLID,
                width=(
                    _twip_back(_css_measure(width.partition(":")[0]), width.endswith(":twip"))
                    if width
                    else None
                ),
                opacity=float(opacity) if opacity else None,
                text=(label.replace("&#44;", ",").replace("&#59;", ";") or None),
                layer=int(layer) if layer else 0,
                filled=filled == "1",
            )
        )
    return tuple(marks)


def _namespaced_mathml(markup: str) -> str:
    """Put the MathML namespace on a ``math`` element that lacks it.

    XHTML has no ``math`` element of its own; without the namespace the
    validator reports it as an element that may not appear there, and a reader
    shows the markup as text.

    Args:
        markup: The MathML fragment.

    Returns:
        The fragment, namespaced.
    """
    if "xmlns" in markup[:200]:
        return markup
    return re.sub(
        r"<math(\s|/|>)", f'<math xmlns="{MATHML_NAMESPACE}"\\1', markup, count=1
    )


MATHML_NAMESPACE = "http://www.w3.org/1998/Math/MathML"
"""The namespace a ``math`` element must carry inside XHTML."""


def _resource_available(resource: Resource | None) -> bool:
    """Whether a resource's bytes can actually be found on disk.

    Args:
        resource: The resource record, or ``None``.

    Returns:
        ``True`` when the file exists and can be packaged.
    """
    if resource is None or not resource.path:
        return False
    return Path(resource.path).exists()


def _resource_href(resource: Resource | None, key: str) -> str:
    """Build the ``src`` of an image resource.

    Args:
        resource: The resource record, when the document has one.
        key: The resource key, used when it does not.

    Returns:
        The href.
    """
    if resource is not None and resource.path:
        return resource.path
    return f"images/{key}"


def _nested_list(
    headings: Sequence[tuple[int, str, str]], hrefs: Mapping[str, str]
) -> str:
    """Build a nested ``<ol>`` from a flat heading list.

    Args:
        headings: ``(level, anchor, title)`` triples in document order.
        hrefs: Optional cross-file hrefs keyed by anchor.

    Returns:
        The list markup.
    """
    out: list[str] = []
    stack: list[int] = []
    for level, anchor, title in headings:
        while stack and stack[-1] > level:
            out.append("</li></ol>")
            stack.pop()
        if stack and stack[-1] == level:
            out.append("</li>")
        else:
            out.append("<ol>")
            stack.append(level)
        href = hrefs.get(anchor, f"#{anchor}")
        out.append(f'<li><a href="{escape_attr(href)}">{escape(title)}</a>')
    while stack:
        out.append("</li></ol>")
        stack.pop()
    return "".join(out)


# --------------------------------------------------------------------------- #
# The exporter
# --------------------------------------------------------------------------- #
class HtmlExporter(Exporter):
    """Writes a document as a self-contained page or a static site."""

    format_name: ClassVar[str] = "html"
    profile: ClassVar[Any] = HTML_PROFILE
    suffix: ClassVar[str] = ".html"

    def write(
        self, document: Document, destination: Path, context: ExportContext
    ) -> ExportResult:
        """Write the document.

        Args:
            document: The IR to write.
            destination: The output file in single mode, or the index file of
                the site directory in site mode.
            context: The export context.

        Returns:
            The result.
        """
        options = context.options
        mode = getattr(options, "mode", "single")
        builder = XhtmlBuilder(context, interactive=options.interactive)
        body = builder.blocks(document.body)

        if mode == "site":
            return self._write_site(document, destination, context, builder, body)
        return self._write_single(document, destination, context, builder, body)

    def _write_single(
        self,
        document: Document,
        destination: Path,
        context: ExportContext,
        builder: XhtmlBuilder,
        body: str,
    ) -> ExportResult:
        """Write one self-contained page.

        Args:
            document: The IR.
            destination: The output file.
            context: The export context.
            builder: The builder that produced ``body``.
            body: The rendered blocks.

        Returns:
            The result.
        """
        body = _fill_toc(body, builder.toc_html())
        # Render every fragment before the stylesheet is read: the notes and the
        # index register classes of their own, and a class registered after the
        # <style> element is written is a run whose formatting silently vanished.
        notes = builder.notes_section()
        index_html = builder.index_html()
        pieces = [
            _head(
                document,
                context,
                inline_css=BASE_CSS,
                generated_css=builder.stylesheet(),
            ),
            "<body>",
            _book_head(document),
            f"<main>\n{body}\n</main>",
            notes,
            index_html,
            _replay_script(context),
            _ir_sidecar(document, context),
            "</body>",
            "</html>",
        ]
        text = "\n".join(part for part in pieces if part)
        destination.write_text(text, encoding="utf-8")
        context.count("bytes", len(text.encode("utf-8")))
        if builder.diagrams.font_families:
            context.note(
                "Fontes de xadrez usadas: "
                + ", ".join(builder.diagrams.font_families)
                + ". Os diagramas sao SVG vetorial; nenhuma fonte precisa ser embutida."
            )
        return context.finish(destination)

    def _write_site(
        self,
        document: Document,
        destination: Path,
        context: ExportContext,
        builder: XhtmlBuilder,
        body: str,
    ) -> ExportResult:
        """Write a static site: one page per chapter plus a shared stylesheet.

        Args:
            document: The IR.
            destination: The index file; its parent is the site root.
            context: The export context.
            builder: The builder that produced ``body``.
            body: The rendered blocks, split on the configured heading level.

        Returns:
            The result.
        """
        root = destination.parent
        root.mkdir(parents=True, exist_ok=True)
        level = getattr(context.options, "split_level", 1)
        sections = _split_on_headings(body, level)

        # Same reason as in single mode: every fragment first, stylesheet last.
        notes = builder.notes_section()
        index_html = builder.index_html()

        css_path = root / "estilo.css"
        css_path.write_text(BASE_CSS, encoding="utf-8")

        names = [destination.name] + [f"cap{index:03d}.html" for index in range(1, len(sections))]
        hrefs = {
            anchor: f"{names[_section_of(anchor, sections)]}#{anchor}"
            for _, anchor, _ in builder.headings
        }
        toc = builder.toc_html(hrefs=hrefs)

        artifacts = [css_path]
        for index, (name, chunk) in enumerate(zip(names, sections)):
            path = root / name
            nav = _site_nav(names, index)
            content = _fill_toc(chunk, toc)
            pieces = [
                _head(
                    document,
                    context,
                    stylesheet_href="estilo.css",
                    generated_css=builder.stylesheet(),
                ),
                "<body>",
                _book_head(document) if index == 0 else "",
                f'<nav class="toc">{toc}</nav>' if index == 0 else "",
                f"<main>\n{content}\n</main>",
                nav,
                notes if index == len(sections) - 1 else "",
                index_html if index == len(sections) - 1 else "",
                _replay_script(context),
                _ir_sidecar(document, context) if index == 0 else "",
                "</body>",
                "</html>",
            ]
            text = "\n".join(part for part in pieces if part)
            path.write_text(text, encoding="utf-8")
            context.count("bytes", len(text.encode("utf-8")))
            if path != destination:
                artifacts.append(path)
        context.count("pages", len(sections))
        return context.finish(destination, artifacts)


def _section_of(anchor: str, sections: Sequence[str]) -> int:
    """Find which site page an anchor landed on.

    Args:
        anchor: The element id.
        sections: The page bodies.

    Returns:
        The page index, ``0`` when not found.
    """
    needle = f'id="{anchor}"'
    for index, section in enumerate(sections):
        if needle in section:
            return index
    return 0


_MARKUP_SCAN = re.compile(
    r"<!--.*?-->"
    r"|<!\[CDATA\[.*?\]\]>"
    r"|<(?P<close>/?)(?P<name>[A-Za-z][A-Za-z0-9:_.\-]*)"
    r"(?P<attrs>(?:[^>\"']|\"[^\"]*\"|'[^']*')*)>",
    re.S,
)


def top_level_starts(body: str, names: frozenset[str]) -> list[int]:
    """Find the offsets of elements that open at nesting depth zero.

    Splitting generated markup by regex alone is how an exporter ships a file
    that no reader will open: a ``<h2>`` nested inside a ``<nav>`` looks exactly
    like a chapter start, and cutting there leaves both halves unbalanced. This
    walks the tag stream instead, so only genuinely top-level elements count.

    Args:
        body: The rendered blocks -- a sequence of balanced elements.
        names: Lower-case element names that may start a chunk.

    Returns:
        Byte offsets into ``body``, ascending.
    """
    depth = 0
    starts: list[int] = []
    for match in _MARKUP_SCAN.finditer(body):
        name = match.group("name")
        if name is None:
            continue
        if match.group("close"):
            depth = max(0, depth - 1)
            continue
        if depth == 0 and name.lower() in names:
            starts.append(match.start())
        if not match.group("attrs").rstrip().endswith("/"):
            depth += 1
    return starts


def split_markup(body: str, names: frozenset[str]) -> list[str]:
    """Cut markup into balanced chunks before each top-level element named.

    Args:
        body: The rendered blocks.
        names: Element names that start a new chunk.

    Returns:
        One string per chunk; always at least one, and every chunk balanced.
    """
    offsets = top_level_starts(body, names)
    if not offsets:
        return [body]
    bounds = sorted({0, *offsets, len(body)})
    parts = [body[start:end] for start, end in zip(bounds, bounds[1:]) if body[start:end].strip()]
    return parts or [body]


def _split_on_headings(body: str, level: int) -> list[str]:
    """Split rendered markup before each heading of a given level.

    Args:
        body: The rendered blocks.
        level: The heading level that starts a new page.

    Returns:
        One string per page; always at least one.
    """
    return split_markup(body, frozenset({f"h{level}"}))


def _site_nav(names: Sequence[str], index: int) -> str:
    """Build previous/next navigation for a site page.

    Args:
        names: Every page file name in order.
        index: The current page.

    Returns:
        The navigation markup.
    """
    links: list[str] = []
    if index > 0:
        links.append(f'<a rel="prev" href="{escape_attr(names[index - 1])}">Anterior</a>')
    if index + 1 < len(names):
        links.append(f'<a rel="next" href="{escape_attr(names[index + 1])}">Pr&#243;ximo</a>')
    if not links:
        return ""
    return f'<nav class="pager">{" &#183; ".join(links)}</nav>'


def _fill_toc(body: str, toc: str) -> str:
    """Replace the table-of-contents placeholder with the generated list.

    Args:
        body: The rendered blocks.
        toc: The generated list.

    Returns:
        The markup with the placeholder filled.
    """
    if 'data-toc-placeholder="1"' not in body or not toc:
        return body
    return body.replace('data-toc-placeholder="1">', 'data-toc-placeholder="1">' + toc, 1)


def _head(
    document: Document,
    context: ExportContext,
    *,
    inline_css: str | None = None,
    stylesheet_href: str | None = None,
    generated_css: str | None = None,
) -> str:
    """Build the document head.

    Args:
        document: The IR.
        context: The export context.
        inline_css: Stylesheet to inline, for a self-contained page.
        stylesheet_href: Stylesheet to link, for a site.
        generated_css: The rules generated from the document's own formatting.
            Kept in a separate, identified ``<style>`` element so that
            :func:`read_html` reads back the *document's* formatting and not
            the design stylesheet -- a distinction that is the difference
            between measuring the exporter and measuring ``BASE_CSS``.

    Returns:
        The doctype, ``<html>`` open tag and ``<head>``.
    """
    metadata = document.metadata
    language = context.options.language or metadata.language or "pt-BR"
    title = metadata.title or "Documento"
    authors = ", ".join(
        contributor.name
        for contributor in metadata.contributors
        if contributor.role is ContributorRole.AUTHOR
    )
    meta = [
        '<meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        f"<title>{escape(title)}</title>",
    ]
    if authors:
        meta.append(f'<meta name="author" content="{escape_attr(authors)}"/>')
    if metadata.description:
        meta.append(f'<meta name="description" content="{escape_attr(metadata.description)}"/>')
    meta.append('<meta name="generator" content="Caissa Studio"/>')
    for name, value in (
        ("caissa-subtitle", metadata.subtitle),
        ("caissa-short-title", metadata.short_title),
        ("caissa-publisher", metadata.publisher),
        ("caissa-imprint", metadata.imprint),
        ("caissa-isbn", metadata.isbn),
        ("caissa-issn", metadata.issn),
        ("caissa-identifier", metadata.identifier),
        ("caissa-date", metadata.publication_date),
        ("caissa-edition", metadata.edition),
        ("caissa-series", metadata.series),
        ("caissa-rights", metadata.rights),
        ("caissa-source", metadata.source),
        ("caissa-series-index", metadata.series_index),
        ("caissa-page-count", metadata.page_count),
        ("caissa-cover", metadata.cover_resource),
        ("caissa-modified", metadata.modified.isoformat() if metadata.modified else None),
        ("caissa-languages", " ".join(metadata.additional_languages)),
        (
            "caissa-custom",
            "|".join(
                f"{entry.name}={entry.value}={entry.scheme or ''}"
                for entry in metadata.custom
            ),
        ),
        (
            "caissa-contributors",
            "|".join(
                f"{person.name}~{person.role.value}~{person.sort_name or ''}"
                f"~{person.identifier or ''}"
                for person in metadata.contributors
            ),
        ),
    ):
        if value:
            meta.append(f'<meta name="{name}" content="{escape_attr(str(value))}"/>')
    if metadata.subjects:
        meta.append(
            f'<meta name="keywords" content="{escape_attr(", ".join(metadata.subjects))}"/>'
        )
    if stylesheet_href:
        meta.append(f'<link rel="stylesheet" href="{escape_attr(stylesheet_href)}"/>')
    if inline_css:
        meta.append(f"<style>{_css_cdata(inline_css)}</style>")
    if generated_css:
        meta.append(f'<style id="caissa-props">{_css_cdata(generated_css)}</style>')
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{escape_attr(language)}" data-caissa="1" '
        f'data-ir-id="{escape_attr(str(document.id))}">\n'
        "<head>\n" + "\n".join(meta) + "\n</head>"
    )


def _book_head(document: Document) -> str:
    """Build the visible title block.

    Args:
        document: The IR.

    Returns:
        The header markup, empty when the document has no title.
    """
    metadata = document.metadata
    if not metadata.title:
        return ""
    parts = [f'<h1 class="book-title">{escape(metadata.title)}</h1>']
    if metadata.subtitle:
        parts.append(f'<p class="book-subtitle">{escape(metadata.subtitle)}</p>')
    names = ", ".join(
        contributor.name
        for contributor in metadata.contributors
        if contributor.role is ContributorRole.AUTHOR
    )
    if names:
        parts.append(f'<p class="book-authors">{escape(names)}</p>')
    return f'<header class="book-head">{"".join(parts)}</header>'


def _replay_script(context: ExportContext) -> str:
    """Emit the game replay script when the export asked for it.

    Args:
        context: The export context.

    Returns:
        The ``<script>`` element, or an empty string.
    """
    if not context.options.interactive:
        return ""
    return f"<script>{_js_cdata(REPLAY_SCRIPT)}</script>"



def _css_cdata(text: str) -> str:
    """Wrap a stylesheet so the page stays well-formed XML.

    An EPUB is XHTML and must parse as XML, and so must our own output if
    :func:`read_html` is to read it with a real XML parser rather than a
    forgiving one. ``/*<![CDATA[*/`` is a CSS comment in HTML and a CDATA
    opener in XML, so one string satisfies both.

    Args:
        text: The stylesheet.

    Returns:
        The wrapped stylesheet.
    """
    return "\n/*<![CDATA[*/\n" + text.replace("]]>", "]]&gt;") + "\n/*]]>*/\n"


def _js_cdata(text: str) -> str:
    """Wrap a script so the page stays well-formed XML.

    ``//<![CDATA[`` is a JavaScript line comment in HTML and a CDATA opener in
    XML. Without it a ``<`` or ``&`` in the script makes the file unparseable,
    which is exactly the bug that ships broken EPUBs.

    Args:
        text: The script.

    Returns:
        The wrapped script.
    """
    return "\n//<![CDATA[\n" + text.replace("]]>", "]] >") + "\n//]]>\n"


def _ir_sidecar(document: Document, context: ExportContext) -> str:
    """Emit the serialised IR as a JSON island.

    It is what makes "open my export and keep editing" work. It is *not* used by
    :mod:`caissa.export.fidelity`: a measurement that read this back would be
    measuring :mod:`json`, not the exporter.

    Args:
        document: The IR.
        context: The export context.

    Returns:
        The ``<script>`` element, or an empty string.
    """
    if not context.options.embed_ir:
        return ""
    payload = json.dumps(document_to_payload(document), ensure_ascii=False, separators=(",", ":"))
    safe = (
        payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    return f'<script type="application/json" id="caissa-ir">{safe}</script>'


# --------------------------------------------------------------------------- #
# Reading back
# --------------------------------------------------------------------------- #
def read_html(path: Path | str, *, use_sidecar: bool = False) -> Document:
    """Read a page written by :class:`HtmlExporter` back into the IR.

    This is the honest half of the round trip. It parses the markup and the
    generated stylesheet -- the same two things a browser reads -- and rebuilds
    the tree from them. ``use_sidecar`` is available for the product feature
    ("reopen my export"), and is off by default so that a fidelity measurement
    measures the exporter.

    Args:
        path: The file to read.
        use_sidecar: Prefer the embedded IR JSON when the file carries one.

    Returns:
        The reconstructed document.

    Raises:
        ValueError: The file is not parseable as XML.
    """
    text = Path(path).read_text(encoding="utf-8")
    return read_html_text(text, use_sidecar=use_sidecar)


def read_html_text(text: str, *, use_sidecar: bool = False) -> Document:
    """Read page markup back into the IR.

    Args:
        text: The XHTML text.
        use_sidecar: Prefer the embedded IR JSON when present.

    Returns:
        The reconstructed document.

    Raises:
        ValueError: The markup is not well-formed XML.
    """
    if use_sidecar:
        match = re.search(
            r'<script type="application/json" id="caissa-ir">(.*?)</script>', text, re.S
        )
        if match:
            document, _migrations = document_from_payload(json.loads(match.group(1)))
            return document

    body = re.sub(r"^<!DOCTYPE[^>]*>\s*", "", text.strip(), flags=re.I)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise ValueError(f"O HTML gerado nao e XML bem formado: {error}") from error
    return _document_from_tree(root)


def _document_from_tree(root: ET.Element) -> Document:
    """Rebuild a document from a parsed page.

    Args:
        root: The ``<html>`` element.

    Returns:
        The document.
    """
    head = root.find("head")
    metadata = _metadata_from_head(head, root.get("lang") or "pt-BR")
    reader = _Reader(_stylesheet_from_head(head))
    read = read_section_blocks(root, reader)
    document = Document(metadata=metadata, body=tuple(fill_note_slots(read)))
    return _restore_ids([document], root)[0]


def read_section_blocks(root: ET.Element, reader: _Reader) -> list[object]:
    """Read one page's body into blocks, note slots kept where they stand.

    Args:
        root: The parsed ``<html>``.
        reader: The block reader to use.

    Returns:
        The blocks, with a :class:`_NoteSlot` wherever a note stood in the
        story and the notes themselves at the end.
    """
    body = root.find("body")
    if body is None:
        return []
    blocks: list[object] = []
    notes: list[Block] = []
    main = body.find("main")
    _walk_flow(main if main is not None else body, reader, blocks)
    for section in body.iter():
        if section.get("class") == "footnotes":
            for note in section:
                notes.extend(reader.block(note))
    blocks.extend(notes)
    return blocks


def _walk_flow(source: ET.Element, reader: _Reader, blocks: list[object]) -> None:
    """Read the blocks of one flow, descending through the container elements.

    An EPUB section is wrapped in a ``<section epub:type="chapter">`` that
    belongs to the packaging and not to the IR, so the note slots inside it are
    a level deeper than they are on a single page. Anything the IR named --
    anything with ``data-ir`` -- is handed to the reader untouched.

    Args:
        source: The element whose children are the flow.
        reader: The block reader.
        blocks: Collector.
    """
    for child in source:
        if child.get("data-ir") == "note_slot":
            blocks.append(_NoteSlot(identity=child.get("data-ir-id") or ""))
            continue
        if child.get("class") == "footnotes":
            # Read below, once, whether it sits inside the flow or beside it.
            continue
        if child.tag == "section" and not child.get("data-ir"):
            _walk_flow(child, reader, blocks)
            continue
        blocks.extend(reader.block(child))


@dataclass(frozen=True, slots=True)
class _NoteSlot:
    """Where a note stood in the story, read back from its slot element.

    Attributes:
        identity: The ULID the slot carried.
    """

    identity: str


def fill_note_slots(read: Sequence[object]) -> list[Block]:
    """Put each note back where its slot stands, and drop the empty slots.

    Args:
        read: What :func:`read_section_blocks` returned, possibly concatenated
            over several sections of one package.

    Returns:
        The blocks, every slot replaced by the note that belongs to it and
        every note seen only once.
    """
    slots = {item.identity for item in read if isinstance(item, _NoteSlot)}
    notes: dict[str, Block] = {}
    for item in read:
        if isinstance(item, _NoteSlot):
            continue
        identity = str(item.id)  # type: ignore[attr-defined]
        if identity in slots and identity not in notes:
            notes[identity] = item  # type: ignore[assignment]
    filled: list[Block] = []
    seen: set[str] = set()
    for item in read:
        if isinstance(item, _NoteSlot):
            note = notes.get(item.identity)
            if note is not None and item.identity not in seen:
                seen.add(item.identity)
                filled.append(note)
            continue
        identity = str(item.id)  # type: ignore[attr-defined]
        if identity in notes:
            continue
        if identity in seen:
            continue
        seen.add(identity)
        filled.append(item)  # type: ignore[arg-type]
    for identity, note in notes.items():
        if identity not in seen:
            filled.append(note)
    return filled


def _metadata_from_head(head: ET.Element | None, language: str) -> DocumentMetadata:
    """Rebuild document metadata from ``<head>``.

    Args:
        head: The head element.
        language: The document language from ``<html lang>``.

    Returns:
        The metadata.
    """
    if head is None:
        return DocumentMetadata(language=language)
    values: dict[str, str] = {}
    for meta in head.findall("meta"):
        name = meta.get("name")
        if name:
            values[name] = meta.get("content") or ""
    title_element = head.find("title")
    contributors = _contributors(values)
    subjects = tuple(
        subject.strip() for subject in (values.get("keywords") or "").split(",") if subject.strip()
    )
    return DocumentMetadata(
        title=(title_element.text or "") if title_element is not None else "",
        subtitle=values.get("caissa-subtitle") or None,
        short_title=values.get("caissa-short-title") or None,
        contributors=contributors,
        language=language,
        identifier=values.get("caissa-identifier") or None,
        isbn=values.get("caissa-isbn") or None,
        issn=values.get("caissa-issn") or None,
        publisher=values.get("caissa-publisher") or None,
        imprint=values.get("caissa-imprint") or None,
        publication_date=values.get("caissa-date") or None,
        edition=values.get("caissa-edition") or None,
        series=values.get("caissa-series") or None,
        description=values.get("description") or None,
        subjects=subjects,
        rights=values.get("caissa-rights") or None,
        source=values.get("caissa-source") or None,
        series_index=_as_int(values.get("caissa-series-index")),
        page_count=_as_int(values.get("caissa-page-count")),
        cover_resource=values.get("caissa-cover") or None,
        modified=_as_moment(values.get("caissa-modified")),
        additional_languages=tuple(
            (values.get("caissa-languages") or "").split()
        ),
        custom=_custom_entries(values.get("caissa-custom")),
    )


def _as_int(text: str | None) -> int | None:
    """Parse an integer metadata value.

    Args:
        text: The attribute value, or ``None``.

    Returns:
        The number, or ``None``.
    """
    try:
        return int(text) if text else None
    except ValueError:
        return None


def _as_moment(text: str | None) -> Any:
    """Parse an ISO timestamp metadata value.

    Args:
        text: The attribute value, or ``None``.

    Returns:
        The datetime, or ``None``.
    """
    from datetime import datetime

    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _custom_entries(text: str | None) -> tuple[Any, ...]:
    """Decode the custom metadata entries written into ``caissa-custom``.

    Args:
        text: The attribute value, or ``None``.

    Returns:
        The entries.
    """
    from caissa.core.model import MetadataEntry

    entries = []
    for part in (text or "").split("|"):
        if not part:
            continue
        name, _, rest = part.partition("=")
        value, _, scheme = rest.partition("=")
        entries.append(MetadataEntry(name=name, value=value, scheme=scheme or None))
    return tuple(entries)


def _contributors(values: Mapping[str, str]) -> tuple[Any, ...]:
    """Rebuild the contributor list from the head.

    ``<meta name="author">`` carries names for a search engine; the roles, sort
    names and identifiers a book actually has ride on ``caissa-contributors``,
    because HTML has nowhere else to put them.

    Args:
        values: The parsed ``<meta>`` values.

    Returns:
        The contributors.
    """
    from caissa.core.model import ContributorRole

    packed = values.get("caissa-contributors")
    if packed:
        people = []
        for part in packed.split("|"):
            if not part:
                continue
            fields = part.split("~")
            while len(fields) < 4:
                fields.append("")
            name, role, sort_name, identifier = fields[:4]
            try:
                kind = ContributorRole(role)
            except ValueError:
                kind = ContributorRole.AUTHOR
            people.append(
                Contributor(
                    name=name,
                    role=kind,
                    sort_name=sort_name or None,
                    identifier=identifier or None,
                )
            )
        return tuple(people)
    return tuple(
        Contributor(name=name.strip(), role=ContributorRole.AUTHOR)
        for name in (values.get("author") or "").split(",")
        if name.strip()
    )


def _stylesheet_from_head(head: ET.Element | None) -> dict[str, dict[str, str]]:
    """Parse the inline stylesheet out of ``<head>``.

    Args:
        head: The head element.

    Returns:
        The class-to-declaration mapping.
    """
    if head is None:
        return {}
    styles: dict[str, dict[str, str]] = {}
    for element in head.findall("style"):
        if element.get("id") != "caissa-props":
            continue
        styles.update(parse_stylesheet(_style_text(element)))
    return styles


def _style_text(element: ET.Element) -> str:
    """Collect a ``<style>`` element's text, CDATA sections included.

    Args:
        element: The style element.

    Returns:
        The stylesheet text.
    """
    return _text_content(element)


def _from_registry(name: str, prefix: str) -> bool:
    """Whether a generated class name came from one registry.

    Args:
        name: The class name.
        prefix: The registry prefix, ``"r"``, ``"p"`` or ``"d"``.

    Returns:
        ``True`` when the name is that prefix followed by digits.
    """
    return name.startswith(prefix) and name[len(prefix) :].isdigit()


def _is_decoration(name: str) -> bool:
    """Whether a generated class name belongs to the decoration registry.

    Args:
        name: The class name.

    Returns:
        ``True`` for ``d1``, ``d2`` and so on.
    """
    return (
        name.startswith(DECORATION_PREFIX)
        and len(name) > 1
        and name[len(DECORATION_PREFIX) :].isdigit()
    )


def _restore_ids(nodes: list[Any], element: ET.Element) -> list[Any]:
    """Put the node identity the markup carries back on the rebuilt node.

    Every element the builder emits carries ``data-ir-id``. Reading it back is
    what makes a round trip *measurable*: without it the diff has to pair nodes
    by position and cannot tell a moved paragraph from a replaced one. Only the
    first node of a multi-node expansion takes the id, because only one node in
    the original owned it.

    Args:
        nodes: The nodes just rebuilt from ``element``.
        element: The source element.

    Returns:
        The same list, with the first node's id restored when possible.
    """
    raw = element.get("data-ir-id")
    if not raw or not nodes:
        return nodes
    try:
        identity = ULID.from_string(raw)
    except (ValueError, TypeError):
        return nodes
    nodes[0] = replace(nodes[0], id=identity)
    return nodes


class _Reader:
    """Rebuilds IR nodes from parsed XHTML elements."""

    def __init__(self, styles: Mapping[str, Mapping[str, str]]) -> None:
        """Create a reader.

        Args:
            styles: The parsed stylesheet, keyed by class name.
        """
        self._styles = styles

    def declarations(self, element: ET.Element, prefix: str = "") -> dict[str, str]:
        """Collect the declarations that apply to an element.

        A ``<pre>`` carries both a paragraph rule and a run rule, and merging
        the two would put the run's background into the paragraph's shading.
        The registries name their classes ``p1``, ``r1``, ``d1``; ``prefix``
        keeps each answer to its own.

        Args:
            element: The element.
            prefix: Registry prefix to read, or an empty string for every
                registry except decorations.

        Returns:
            The merged declarations.
        """
        merged: dict[str, str] = {}
        for name in (element.get("class") or "").split():
            if prefix:
                if not _from_registry(name, prefix):
                    continue
            elif _is_decoration(name):
                continue
            block = self._styles.get(name + OWN_SUFFIX)
            if block is None:
                block = self._styles.get(name)
            if block:
                merged.update(block)
        return merged

    def run_props(self, element: ET.Element) -> RunProps:
        """Rebuild run properties for an element.

        Args:
            element: The element.

        Returns:
            The properties.
        """
        return css_to_run_props(self.declarations(element, "r"))

    def named_run(self, element: ET.Element) -> RunProps:
        """Read the run rule an element names in ``data-run-class``.

        A heading and a code block both have run properties of their own that
        are not those of any run inside them, so the rule is named rather than
        merged into ``class`` where a re-import could not tell them apart.

        Args:
            element: The element.

        Returns:
            The properties, empty when no rule is named.
        """
        name = element.get("data-run-class") or ""
        block = self._styles.get(name + OWN_SUFFIX) or self._styles.get(name)
        return css_to_run_props(block) if block else RunProps()

    def decoration(self, element: ET.Element) -> ParagraphProps:
        """Read the node's *own* decoration rule.

        Args:
            element: The element.

        Returns:
            Properties carrying only borders, padding and shading.
        """
        for name in (element.get("class") or "").split():
            if not _is_decoration(name):
                continue
            block = self._styles.get(name + OWN_SUFFIX) or self._styles.get(name)
            if block:
                return css_to_paragraph_props(block)
        return ParagraphProps()

    def paragraph_props(self, element: ET.Element) -> ParagraphProps:
        """Rebuild paragraph properties for an element.

        Args:
            element: The element.

        Returns:
            The properties.
        """
        return css_to_paragraph_props(self.declarations(element, "p"))

    # -- blocks ------------------------------------------------------------

    def block(self, element: ET.Element) -> list[Block]:
        """Rebuild the blocks an element stands for.

        Args:
            element: The element.

        Returns:
            Zero or more blocks; a wrapper yields its children.
        """
        kind = element.get("data-ir") or ""
        handler = getattr(self, f"_read_{kind}", None) if kind else None
        if handler is not None:
            result = handler(element)
            nodes = result if isinstance(result, list) else [result]
            return _restore_ids(nodes, element)
        collected: list[Block] = []
        for child in element:
            collected.extend(self.block(child))
        return collected

    def _read_heading(self, element: ET.Element) -> Heading:
        level = int(element.tag[1]) if element.tag[:1] == "h" and element.tag[1:].isdigit() else 1
        return Heading(
            level=level,
            content=self.inlines(element),
            anchor=element.get("data-anchor"),
            toc_text=element.get("data-toc-text"),
            numbering_text=element.get("data-numbering-text"),
            props=self.paragraph_props(element),
            run_props=self.named_run(element),
            list_in_toc=element.get("data-in-to") != "0" and element.get("data-in-toc") != "0",
        )

    def _read_paragraph(self, element: ET.Element) -> Paragraph:
        drop = element.get("data-drop-cap")
        return Paragraph(
            content=self.inlines(element),
            props=self.paragraph_props(element),
            drop_cap=int(drop) if drop else None,
        )

    def _read_list_block(self, element: ET.Element) -> ListBlock:
        if element.tag == "dl":
            items: list[ListItem] = []
            term: tuple[Inline, ...] = ()
            for child in element:
                if child.tag == "dt":
                    term = self.inlines(child)
                elif child.tag == "dd":
                    item = ListItem(content=tuple(self._children(child)), term=term)
                    items.append(_restore_ids([item], child)[0])
                    term = ()
            marker = element.get("data-marker-style")
            start = element.get("data-start")
            indent = element.get("data-indent")
            return ListBlock(
                kind=ListKind.DEFINITION,
                items=tuple(items),
                marker_style=(
                    ListMarkerStyle(marker) if marker else ListMarkerStyle.NONE
                ),
                marker_text=element.get("data-marker-text"),
                start=int(start) if start else 1,
                indent=_measure_from_attribute(indent),
                tight=element.get("data-tight") == "1",
                props=self.paragraph_props(element),
            )
        kind = ListKind.ORDERED if element.tag == "ol" else ListKind.UNORDERED
        marker = element.get("data-marker-style")
        start = element.get("data-start")
        listing = self.declarations(element, DECORATION_PREFIX)
        indent = listing.get("--caissa-list-indent")
        return ListBlock(
            kind=kind,
            indent=(
                _twip_back(
                    _css_measure(indent.partition(":")[0]), indent.endswith(":twip")
                )
                if indent
                else None
            ),
            tight=listing.get("--caissa-tight") == "1",
            items=tuple(self._read_list_item(child) for child in element if child.tag == "li"),
            marker_style=ListMarkerStyle(marker) if marker else ListMarkerStyle.BULLET,
            marker_text=element.get("data-marker-text"),
            start=int(start) if start else 1,
            props=self.paragraph_props(element),
        )

    def _read_list_item(self, element: ET.Element) -> ListItem:
        """Rebuild one list item.

        Args:
            element: The ``<li>``.

        Returns:
            The item.
        """
        checked = element.get("data-checked")
        value = element.get("data-start") or element.get("value")
        item = ListItem(
            content=tuple(self._children(element)),
            marker_override=element.get("data-marker"),
            start_override=int(value) if value else None,
            checked=None if checked is None else checked == "1",
        )
        return _restore_ids([item], element)[0]

    def _read_quote(self, element: ET.Element) -> Quote:
        attribution: tuple[Inline, ...] = ()
        content: list[Block] = []
        for child in element:
            if child.get("class") == "attribution":
                attribution = self.inlines(child)
            else:
                content.extend(self.block(child))
        return Quote(
            content=tuple(content),
            attribution=attribution,
            props=self.paragraph_props(element),
        )

    def _read_callout(self, element: ET.Element) -> Callout:
        title: tuple[Inline, ...] = ()
        content: list[Block] = []
        for child in element:
            classes = (child.get("class") or "").split()
            if "callout-title" in classes or child.tag == "summary":
                title = self.inlines(child)
            else:
                content.extend(self.block(child))
        kind = element.get("data-kind") or "note"
        decoration = self.decoration(element)
        return Callout(
            kind=CalloutKind(kind),
            title=title,
            content=tuple(content),
            props=self.paragraph_props(element),
            borders=decoration.borders,
            padding=decoration.padding,
            shading=decoration.shading,
            collapsed=element.get("data-collapsed") == "1",
        )

    def _read_code_block(self, element: ET.Element) -> CodeBlock:
        code = element.find("code")
        language = ""
        if code is not None:
            klass = code.get("class") or ""
            if klass.startswith("language-"):
                language = klass[len("language-") :]
        run_class = element.get("data-run-class") or ""
        block = self._styles.get(run_class + OWN_SUFFIX) or self._styles.get(run_class)
        return CodeBlock(
            language=language,
            text=_text_content(code if code is not None else element),
            show_line_numbers=element.get("data-line-numbers") == "1",
            props=self.paragraph_props(element),
            run_props=css_to_run_props(block) if block else RunProps(),
        )

    def _read_math_block(self, element: ET.Element) -> MathBlock:
        return MathBlock(
            latex=element.get("data-tex") or "",
            mathml=element.get("data-mathml"),
            display=element.get("data-display") != "0",
            numbered=element.get("data-numbered") == "1",
            label=element.get("data-label"),
            props=self.paragraph_props(element),
        )

    def _read_table(self, element: ET.Element) -> Table:
        from caissa.core.model import TableColumn

        caption: tuple[Inline, ...] = ()
        columns: list[TableColumn] = []
        rows: list[TableRow] = []
        for child in element:
            if child.tag == "caption":
                caption = self.inlines(child)
            elif child.tag == "colgroup":
                for col in child:
                    declarations = self.declarations(col)
                    align = declarations.get("--caissa-align")
                    columns.append(
                        TableColumn(
                            width=_css_measure(declarations.get("width", "")),
                            min_width=_css_measure(declarations.get("min-width", "")),
                            alignment=Alignment(align) if align else None,
                        )
                    )
            elif child.tag in ("thead", "tbody", "tfoot"):
                rows.extend(self._read_row(row) for row in child if row.tag == "tr")
            elif child.tag == "tr":
                rows.append(self._read_row(child))
        header = element.get("data-header-rows")
        footer = element.get("data-footer-rows")
        number = element.get("data-number")
        alignment = element.get("data-alignment")
        width = element.get("data-width")
        name = element.get("data-decoration") or ""
        block = self._styles.get(name + OWN_SUFFIX) or self._styles.get(name)
        decoration = css_to_paragraph_props(block) if block else ParagraphProps()
        return Table(
            columns=tuple(columns),
            rows=tuple(rows),
            header_row_count=int(header) if header else 0,
            footer_row_count=int(footer) if footer else 0,
            repeat_header=element.get("data-repeat-header") != "0",
            borders=decoration.borders,
            cell_padding=decoration.padding,
            width=_css_measure(width) if width else None,
            alignment=Alignment(alignment) if alignment else None,
            caption=caption,
            caption_above=element.get("data-caption-above") == "1",
            number=int(number) if number else None,
            style=element.get("data-style"),
            anchor=element.get("id"),
            summary=element.get("data-summary") or element.get("summary"),
        )

    def _read_row(self, element: ET.Element) -> TableRow:
        """Rebuild one table row.

        Args:
            element: The ``<tr>``.

        Returns:
            The row.
        """
        height = element.get("data-height")
        return _restore_ids([self._row(element, height)], element)[0]

    def _row(self, element: ET.Element, height: str | None) -> TableRow:
        """Build the row itself.

        Args:
            element: The ``<tr>``.
            height: The declared row height, if any.

        Returns:
            The row.
        """
        return TableRow(
            cells=tuple(self._read_cell(cell) for cell in element if cell.tag in ("td", "th")),
            height=_css_measure(height) if height else None,
            is_header=element.get("data-header") == "1",
            repeat_on_break=element.get("data-repeat") == "1",
            keep_together=element.get("data-keep") == "1",
        )

    def _read_cell(self, element: ET.Element) -> TableCell:
        """Rebuild one table cell.

        Args:
            element: The ``<td>`` or ``<th>``.

        Returns:
            The cell.
        """
        return _restore_ids([self._cell(element)], element)[0]

    def _cell(self, element: ET.Element) -> TableCell:
        """Build the cell itself.

        Args:
            element: The ``<td>`` or ``<th>``.

        Returns:
            The cell.
        """
        from caissa.core.model import VerticalCellAlignment

        declarations = self.declarations(element)
        align = declarations.get("--caissa-align")
        vertical = declarations.get("vertical-align")
        decoration = self.decoration(element)
        return TableCell(
            content=tuple(self._children(element)),
            row_span=int(element.get("rowspan") or 1),
            col_span=int(element.get("colspan") or 1),
            alignment=Alignment(align) if align else None,
            vertical_alignment=(
                VerticalCellAlignment(vertical)
                if vertical in {item.value for item in VerticalCellAlignment}
                else None
            ),
            borders=decoration.borders,
            padding=decoration.padding,
            shading=decoration.shading,
            # ``<th>`` says the *row* is a header; only the attribute says the
            # cell claimed it for itself.
            is_header=element.get("data-is-header") == "1",
        )

    def _read_figure(self, element: ET.Element) -> Figure:
        caption: tuple[Inline, ...] = ()
        content: list[Block] = []
        for child in element:
            if child.tag == "figcaption":
                caption = self._caption_text(child)
            else:
                content.extend(self.block(child))
        number = element.get("data-number")
        from caissa.core.model import FigurePlacement

        placement = element.get("data-placement") or "here"
        return Figure(
            content=tuple(content),
            caption=caption,
            number=int(number) if number else None,
            label=element.get("data-label"),
            placement=FigurePlacement(placement),
            caption_above=element.get("data-caption-above") == "1",
            anchor=element.get("id"),
            alt_text=element.get("aria-label"),
            props=self.paragraph_props(element),
        )

    def _read_diagram(self, element: ET.Element) -> Diagram:
        from caissa.core.model import CaptionPosition, GameScore
        from caissa.core.model import DiagramStyle as IrDiagramStyle

        caption: tuple[Inline, ...] = ()
        for child in element:
            if child.tag == "figcaption":
                caption = self._caption_text(child)
        number = element.get("data-number")
        solution_pgn = element.get("data-solution")
        solution: GameScore | None = None
        if solution_pgn:
            solution = _game_from_pgn(solution_pgn)
        style = IrDiagramStyle()
        children = list(element)
        if children and children[0].tag == "figcaption":
            style = replace(style, caption_position=CaptionPosition.ABOVE)
        marks = element.get("data-marks")
        return Diagram(
            fen=element.get("data-fen") or "",
            orientation=Orientation(element.get("data-orientation") or "white"),
            style=style,
            caption=caption,
            number=int(number) if number else None,
            label=element.get("data-label"),
            marks=_parse_marks(marks) if marks else (),
            side_to_move_indicator=element.get("data-side-to-move") == "1",
            stipulation=element.get("data-stipulation"),
            solution=solution,
            anchor=element.get("id"),
            alt_text=element.get("data-alt"),
            move_context=element.get("data-move-context"),
            verified_by_human=element.get("data-verified") == "1",
        )

    def _read_image_block(self, element: ET.Element) -> ImageBlock:
        declarations = self.declarations(element, "p")
        crop = element.get("data-crop")
        alignment = element.get("data-alignment")
        return ImageBlock(
            resource=element.get("data-resource") or "",
            alt_text=element.get("alt") or element.get("data-alt") or None,
            width=_twip_back(
                _css_measure(declarations.get("width", "")),
                bool(declarations.get("--caissa-twip-width")),
            ),
            height=_twip_back(
                _css_measure(declarations.get("height", "")),
                bool(declarations.get("--caissa-twip-height")),
            ),
            alignment=Alignment(alignment) if alignment else None,
            title=element.get("title") or element.get("data-title"),
            crop=tuple(float(part) for part in crop.split(",")) if crop else (),
        )

    def _read_game_score(self, element: ET.Element) -> Any:
        pgn = element.get("data-pgn") or ""
        score = _game_from_pgn(pgn)
        from caissa.core.model import GameRenderOptions, VariationStyle

        render = score.render
        language = element.get("data-language")
        variation_style = element.get("data-variation-style")
        render = GameRenderOptions(
            language=language or render.language,
            render=MoveRenderStyle(element.get("data-render") or render.render.value),
            variation_style=(
                VariationStyle(variation_style) if variation_style else render.variation_style
            ),
            show_headers=any(
                child.get("class") == "headers" for child in element.iter() if child is not element
            ),
        )
        title_element = next(
            (child for child in element if child.get("class") == "game-title"), None
        )
        return replace(
            score,
            initial_fen=element.get("data-initial-fen"),
            variant=element.get("data-variant") or "standard",
            annotator=element.get("data-annotator"),
            render=render,
            title=_text_content(title_element) if title_element is not None else None,
        )

    def _read_page_break(self, element: ET.Element) -> PageBreak:
        return PageBreak()

    def _read_section_break(self, element: ET.Element) -> SectionBreak:
        from caissa.core.model import ColumnLayout, SectionBreakKind

        columns = element.get("data-columns")
        gap = element.get("data-column-gap")
        start = element.get("data-page-number-start")
        header: tuple[Inline, ...] = ()
        footer: tuple[Inline, ...] = ()
        for child in element:
            classes = (child.get("class") or "").split()
            if "running-head" in classes:
                header = self.inlines(child)
            elif "running-foot" in classes:
                footer = self.inlines(child)
        return SectionBreak(
            kind=SectionBreakKind(element.get("data-kind") or "next-page"),
            geometry=_geometry_from_data(element.get("data-geometry")),
            columns=(
                ColumnLayout(
                    count=int(columns),
                    gap=(
                        _twip_back(
                            _css_measure(gap.partition(":")[0]),
                            gap.endswith(":twip"),
                        )
                        if gap
                        else None
                    ),
                    rule=(
                        _css_border(element.get("data-column-rule") or "")
                        if element.get("data-column-rule")
                        else None
                    ),
                    balanced=element.get("data-column-balanced") != "0",
                    widths=tuple(
                        measure
                        for raw in (element.get("data-column-widths") or "").split()
                        if (measure := _css_measure(raw)) is not None
                    ),
                )
                if columns
                else None
            ),
            header_text=header,
            footer_text=footer,
            different_first_page=element.get("data-different-first") == "1",
            different_odd_even=element.get("data-different-odd-even") == "1",
            page_number_start=int(start) if start else None,
            page_number_format=element.get("data-page-number-format"),
        )

    def _read_thematic_break(self, element: ET.Element) -> ThematicBreak:
        declarations = self.declarations(element)
        border = declarations.get("border-top")
        return ThematicBreak(
            ornament=element.get("data-ornament"),
            rule=_css_border(border) if border else None,
        )

    def _read_group(self, element: ET.Element) -> Group:
        columns = element.get("data-columns")
        title: tuple[Inline, ...] = ()
        content: list[Block] = []
        for child in element:
            if child.get("class") == "group-title":
                title = self.inlines(child)
                continue
            content.extend(self.block(child))
        return Group(
            role=GroupRole(element.get("data-role") or "generic"),
            content=tuple(content),
            title=title,
            props=self.paragraph_props(element),
            anchor=element.get("id"),
            columns=int(columns) if columns else None,
        )

    def _read_table_of_contents(self, element: ET.Element) -> TableOfContents:
        title_element = element.find("h2")
        generated = (
            title_element is not None and title_element.get("data-generated") == "1"
        )
        return TableOfContents(
            title=(
                self.inlines(title_element)
                if title_element is not None and not generated
                else ()
            ),
            min_level=int(element.get("data-min-level") or 1),
            max_level=int(element.get("data-max-level") or 3),
            show_page_numbers=element.get("data-page-numbers") != "0",
            leader=element.get("data-leader") != "0",
            scope=element.get("data-scope") or "headings",
        )

    def _read_raw_passthrough(self, element: ET.Element) -> RawPassthrough:
        return RawPassthrough(
            format=element.get("data-format") or "",
            text=_text_content(element),
        )

    def _read_footnote(self, element: ET.Element) -> Footnote:
        return Footnote(
            ref=element.get("data-ref") or "",
            content=tuple(self._note_content(element)),
            marker=element.get("data-marker"),
            props=self.paragraph_props(element),
        )

    def _read_endnote(self, element: ET.Element) -> Endnote:
        return Endnote(
            ref=element.get("data-ref") or "",
            content=tuple(self._note_content(element)),
            marker=element.get("data-marker"),
            props=self.paragraph_props(element),
        )

    def _note_content(self, element: ET.Element) -> list[Block]:
        """Read a note body, skipping the generated marker and back-reference.

        Args:
            element: The ``<aside>``.

        Returns:
            The blocks.
        """
        blocks: list[Block] = []
        for child in element:
            classes = (child.get("class") or "").split()
            if "marker" in classes or "backref" in classes:
                continue
            blocks.extend(self.block(child))
        return blocks

    def _caption_text(self, element: ET.Element) -> tuple[Inline, ...]:
        """Read the author's caption out of a generated ``<figcaption>``.

        The exporter prints a label, a stipulation and the caption, in that
        order and separated by spaces. Only the last is the author's, so it is
        wrapped in its own ``<span class="caption-text">`` on the way out and
        read from there on the way back -- rather than trying to un-guess a
        label from the flattened text, which is how a caption ends up with a
        stray leading space or, worse, keeps the word "Diagrama".

        Args:
            element: The ``<figcaption>``.

        Returns:
            The caption inlines.
        """
        for child in element:
            if "caption-text" in (child.get("class") or "").split():
                return self.inlines(child)
        return ()

    def _children(self, element: ET.Element) -> list[Block]:
        """Read the block children of a container.

        Args:
            element: The container.

        Returns:
            The blocks.
        """
        collected: list[Block] = []
        for child in element:
            collected.extend(self.block(child))
        return collected

    # -- inlines -----------------------------------------------------------

    def inlines(self, element: ET.Element) -> tuple[Inline, ...]:
        """Rebuild the inline content of an element.

        Args:
            element: The element.

        Returns:
            The inlines.
        """
        result: list[Inline] = []
        if element.text:
            result.append(Text(content=_unescape(element.text)))
        for child in element:
            if child.get("data-generated") == "1":
                # Numbering the exporter produced. Returning it as content
                # would grow the document a little on every round trip.
                if child.tail:
                    result.append(Text(content=_unescape(child.tail.lstrip())))
                continue
            result.extend(self._inline(child))
            if child.tail:
                result.append(Text(content=_unescape(child.tail)))
        return tuple(node for node in result if not _is_empty_text(node))

    def _inline(self, element: ET.Element) -> list[Inline]:
        """Rebuild one inline element, restoring its identity from the markup.

        Args:
            element: The element.

        Returns:
            Zero or more inlines.
        """
        return _restore_ids(self._inline_uncoded(element), element)

    def _inline_uncoded(self, element: ET.Element) -> list[Inline]:
        """Rebuild one inline element without touching node identity.

        Args:
            element: The element.

        Returns:
            Zero or more inlines.
        """
        kind = element.get("data-ir") or ""
        props = self.run_props(element)
        content = self.inlines(element)

        if kind == "span":
            return [Span(content=content, props=props)]
        if kind == "link":
            return [
                Link(
                    target=element.get("data-target") or "",
                    content=content,
                    kind=LinkKind(element.get("data-link-kind") or "external"),
                    tooltip=element.get("data-tooltip"),
                    title=element.get("data-title"),
                    props=props,
                )
            ]
        if kind == "move":
            nags = element.get("data-nags")
            return [
                Move(
                    san=element.get("data-san") or "",
                    ply=int(element.get("data-ply") or 0),
                    position_before=element.get("data-fen-before") or "",
                    nags=tuple(int(part) for part in nags.split(",")) if nags else (),
                    render=MoveRenderStyle(element.get("data-render") or "letters"),
                    language=element.get("data-language") or "en",
                    figurine_set=FigurineSet(element.get("data-figurine-set") or "black"),
                    uci=element.get("data-uci"),
                    show_move_number=element.get("data-show-number") == "1",
                    move_number_text=element.get("data-number-text"),
                    props=props,
                )
            ]
        if kind == "piece_glyph":
            from caissa.core.model import PieceGlyph

            return [
                PieceGlyph(
                    piece=PieceType(element.get("data-piece") or "pawn"),
                    figurine_set=FigurineSet(element.get("data-figurine-set") or "black"),
                    font_family=element.get("data-font-family"),
                    props=props,
                )
            ]
        if kind == "nag_symbol":
            return [NagSymbol(nag=int(element.get("data-nag") or 0), props=props)]
        if kind == "note_ref":
            return [
                NoteRef(
                    ref=element.get("data-ref") or "",
                    marker=element.get("data-marker"),
                    props=props,
                )
            ]
        if kind == "inline_diagram":
            size = element.get("data-size")
            marks = element.get("data-marks")
            return [
                InlineDiagram(
                    fen=element.get("data-fen") or "",
                    size=_css_measure(size) if size else None,
                    orientation=Orientation(element.get("data-orientation") or "white"),
                    marks=_parse_marks(marks) if marks else (),
                    style=element.get("data-style"),
                    alt_text=element.get("data-alt"),
                )
            ]
        if kind == "math_inline":
            return [
                MathInline(
                    latex=element.get("data-tex") or "",
                    mathml=element.get("data-mathml"),
                    props=props,
                )
            ]
        if kind == "image_inline":
            declarations = self.declarations(element, "r")

            def sized(name: str) -> Any:
                """Read one image length, twips restored."""
                return _twip_back(
                    _css_measure(declarations.get(name, "")),
                    bool(declarations.get(f"--caissa-twip-{name}")),
                )

            return [
                ImageInline(
                    resource=element.get("data-resource") or "",
                    alt_text=element.get("alt") or element.get("data-alt") or None,
                    width=sized("width"),
                    height=sized("height"),
                    baseline_shift=sized("vertical-align"),
                )
            ]
        if kind == "anchor":
            return [Anchor(name=element.get("data-name") or "", title=element.get("data-title"))]
        if kind == "index_entry":
            terms = element.get("data-terms") or ""
            see_also = element.get("data-see-also") or ""
            return [
                IndexEntry(
                    terms=tuple(part for part in terms.split("|") if part),
                    sort_key=element.get("data-sort-key"),
                    see_also=tuple(part for part in see_also.split("|") if part),
                    primary=element.get("data-primary") == "1",
                )
            ]
        if kind == "space":
            return [Space(kind=SpaceKind(element.get("data-kind") or "thin"))]
        if kind == "non_breaking_space":
            return [NonBreakingSpace()]
        if kind == "tab":
            return [Tab()]
        if kind == "raw_inline":
            return [
                RawInline(format=element.get("data-format") or "", text=_text_content(element))
            ]
        if element.tag == "br":
            return [LineBreak()]
        if element.tag == "em":
            return [Emphasis(content=content, props=props)]
        if element.tag == "strong":
            return [Strong(content=content, props=props)]
        if element.tag == "u":
            return [Underline(content=content, props=props)]
        if element.tag == "s":
            return [Strike(content=content, props=props)]
        if element.tag == "sup":
            return [Superscript(content=content, props=props)]
        if element.tag == "sub":
            return [Subscript(content=content, props=props)]
        if kind == "small_caps":
            return [SmallCaps(content=content, props=props)]
        if element.tag == "a" and element.get("href"):
            kind_value = element.get("data-link-kind") or "external"
            return [
                Link(
                    target=element.get("data-target") or element.get("href") or "",
                    content=content,
                    tooltip=element.get("data-tooltip"),
                    title=element.get("data-title"),
                    kind=LinkKind(kind_value),
                    props=props,
                )
            ]
        if kind == "text":
            return [Text(content=_text_content(element), props=props)]
        if element.tag in ("span", "a"):
            if not props.is_empty:
                return [Span(content=content, props=props)]
            return list(content)
        return list(content)


def _is_empty_text(node: Inline) -> bool:
    """Whether an inline is an empty text run worth dropping.

    Args:
        node: The inline.

    Returns:
        Whether it carries nothing.
    """
    return isinstance(node, Text) and node.content == ""


def _is_generated_label(text: str) -> bool:
    """Whether a caption fragment is one the exporter generated.

    Args:
        text: The fragment.

    Returns:
        Whether it is a ``Diagrama N`` or ``Figura N`` label.
    """
    return bool(re.fullmatch(r"\s*(Diagrama|Figura)\s+\d+\s*", text))


def _text_content(element: ET.Element | None) -> str:
    """Collect an element's text, descendants included.

    Args:
        element: The element, or ``None``.

    Returns:
        The concatenated text.
    """
    if element is None:
        return ""
    parts = [element.text or ""]
    for child in element:
        parts.append(_text_content(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _unescape(text: str) -> str:
    """Return parsed text unchanged.

    ElementTree has already resolved numeric character references, so this is a
    named seam rather than a transformation -- it exists so a future change of
    parser has one place to adapt.

    Args:
        text: The parsed text.

    Returns:
        The same text.
    """
    return text


def _game_from_pgn(pgn: str) -> Any:
    """Rebuild a game score from PGN.

    Args:
        pgn: The PGN text.

    Returns:
        The game score; an empty one when the text is unreadable.
    """
    from caissa.export.text import game_from_pgn

    return game_from_pgn(pgn)
