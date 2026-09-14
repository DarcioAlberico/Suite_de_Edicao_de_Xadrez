"""DOCX output: real styles, real fields, and vector diagrams.

SPEC section 8.2 asks for five things ``python-docx`` cannot do on its own, and
so this module writes OOXML directly:

*   **estilos reais (nao formatacao direta)** -- the IR's stylesheet becomes
    ``word/styles.xml``, and a run that names a style gets ``w:rStyle`` rather
    than a copy of the style's properties. A reader who changes the style
    changes the book, which is the entire point of a style;
*   **numeracao automatica de figuras via campos SEQ** -- ``{ SEQ Figura }``,
    so inserting a diagram renumbers the rest;
*   **sumario via campo TOC** -- ``{ TOC \\o "1-3" }``, updated by Word, not
    frozen by us;
*   **diagramas como EMF vetorial** -- see below;
*   **notas de rodape e propriedades de documento**.

Why the diagrams are EMF
------------------------
A chess diagram is line art. Rasterised at any resolution it is soft on a
retina screen and jagged in print; as an Enhanced Metafile it is geometry that
Word scales losslessly and a printer renders at device resolution.
:mod:`caissa.export.emf` converts the same SVG the HTML and EPUB exporters use,
so the three formats draw the same board.

The fallback is honest. When a diagram cannot be converted -- an SVG feature
the metafile writer does not carry -- the exporter writes a
:attr:`~caissa.export.base.ExportOptions.diagram_dpi` PNG **and records a
rasterisation warning naming the diagram**. A PNG that quietly replaced a
vector is exactly the failure this front exists to prevent, so the statistics
count ``diagrams_emf`` and ``diagrams_png`` separately and the export summary
prints both.

Identity, and how it survives Word
----------------------------------
The round trip needs to find a paragraph again after Word has rewritten the
file. OOXML has no attribute for application data on a run, but it does have
bookmarks, and a bookmark name may be forty characters: every node is written
between ``w:bookmarkStart w:name="caissa_<ULID>"`` and its ``w:bookmarkEnd``.
Three things have no element of their own and are named by *place* instead:
the document (``w:body`` is the document, so its id is a ``w:docVar`` in
``word/settings.xml``), and a footnote or endnote, whose body lives outside the
story and whose position is an empty bookmark.

What that survives, measured rather than assumed. Opening a file written here
in Word 2016 and saving it keeps the bookmarks, but **Word moves a block-level
one inside the paragraph it wrapped**, after ``w:pPr``, leaving the end outside.
:func:`_hoisted_identity` recovers those, so headings, paragraphs and game
scores come back with their ids after a real Word edit. A table's does not, and
the note markers do not: see ``docs/quality/F8_REPORT.md``.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

from caissa.core.model import (
    ULID,
    Alignment,
    Block,
    Callout,
    CalloutKind,
    CodeBlock,
    Color,
    ColorSpace,
    Diagram,
    Document,
    Emphasis,
    Endnote,
    Figure,
    Footnote,
    GameScore,
    Group,
    Heading,
    ImageBlock,
    ImageInline,
    Inline,
    InlineDiagram,
    LengthUnit,
    LineBreak,
    LineSpacingRule,
    Link,
    ListBlock,
    ListItem,
    ListKind,
    MathBlock,
    MathInline,
    Measure,
    Move,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    NumberingRef,
    Orientation,
    PageBreak,
    Paragraph,
    ParagraphProps,
    PieceGlyph,
    Quote,
    RawInline,
    RawPassthrough,
    Resource,
    RunProps,
    SectionBreak,
    SmallCaps,
    Space,
    Strike,
    StrikeStyle,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableOfContents,
    Text,
    TextTransform,
    ThematicBreak,
    Underline,
    UnderlineStyle,
    VerticalAlign,
    tag_of,
)
from caissa.export.base import ExportContext, Exporter, ExportError, ExportOptions, ExportResult
from caissa.export.diagrams import DiagramRenderer, diagram_alt_text
from caissa.export.emf import EmfError, svg_to_emf, svg_to_png
from caissa.export.profiles import DOCX_PROFILE
from caissa.export.text import nag_symbol, render_move

__all__ = ["DocxExporter", "DocxOptions", "read_docx"]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"

_FLATTENED: frozenset[str] = frozenset(
    {
        "emphasis",
        "strong",
        "underline",
        "strike",
        "small_caps",
        "superscript",
        "subscript",
        "span",
        "link",
    }
)
"""Inline wrappers OOXML has no element for; see :data:`_DOCX_NODES`."""

_SELF_IDENTIFIED: frozenset[str] = frozenset({"table", "footnote", "endnote", "game_score"})
"""Blocks whose handler places its own bookmark.

A block that renders as several paragraphs must say *which* of them carries its
identity, or the bookmark opens before a caption and the re-import reports a
table that turned into a paragraph.
"""

DOCUMENT_ID_VAR = "caissaDocumentId"
"""Name of the ``w:docVar`` that carries the document node's identity."""

BOOKMARK_PREFIX = "caissa_"
"""Bookmark-name prefix that carries a node's identity through Word."""

EMU_PER_MM = 36000
_TWIP_PER_POINT = 20
_MAX_BOOKMARK = 40

_SPACE_RUN = '<w:r><w:t xml:space="preserve"> </w:t></w:r>'
"""The separator between two movetext tokens, as its own run.

Keeping the space out of the token runs is what lets the reader take a run's
text as the token itself, with no trimming and no guessing.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class DocxOptions(ExportOptions):
    """Settings specific to Word output.

    Attributes:
        page_width_mm: Page width; A5 by default, the size a chess book is.
        page_height_mm: Page height.
        margin_mm: Margin on all four sides.
        default_font: Family for the ``Normal`` style.
        default_size_pt: Body size for the ``Normal`` style.
        track_identity: Write the bookmarks that make a re-import exact. Costs
            two elements per node; turning it off makes the file smaller and
            the round trip approximate.
        compatibility: Value of ``w:compat/w:compatSetting``; 15 is Word 2013.
    """

    page_width_mm: float = 148.0
    page_height_mm: float = 210.0
    margin_mm: float = 18.0
    default_font: str = "Cambria"
    default_size_pt: float = 11.0
    track_identity: bool = True
    compatibility: int = 15


# --------------------------------------------------------------------------- #
# XML helpers
# --------------------------------------------------------------------------- #
_RPR_ORDER: tuple[str, ...] = (
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid",
    "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz",
    "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
    "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath",
)
"""Child order of ``CT_RPr`` in ECMA-376.

OOXML declares its property groups as ``xsd:sequence``, not ``xsd:all``: an
element in the wrong position is a *schema violation*, and Word answers a schema
violation by refusing to open the file and offering to repair it. The order is
here rather than in the writer's control flow so the writer can emit properties
in whatever order reads best and be sorted into legality at the end.
"""

_PPR_ORDER: tuple[str, ...] = (
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
    "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
    "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE",
    "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind",
    "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
    "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
)
"""Child order of ``CT_PPr`` in ECMA-376. See :data:`_RPR_ORDER`."""

_TRPR_ORDER: tuple[str, ...] = (
    "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
    "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
)
"""Child order of ``CT_TrPr`` in ECMA-376. See :data:`_RPR_ORDER`."""

_TCPR_ORDER: tuple[str, ...] = (
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
)
"""Child order of ``CT_TcPr`` in ECMA-376. See :data:`_RPR_ORDER`."""

_CELL_VALIGN: Mapping[str, str] = {
    "top": "top",
    "middle": "center",
    "bottom": "bottom",
}
"""``w:vAlign`` has three positions; the IR's cell alignments map onto them."""

_VALUES_CELL_VALIGN_NAMES: Mapping[str, str] = {
    value: key for key, value in _CELL_VALIGN.items()
}
"""``w:vAlign`` back to the IR's name for the same position."""

_ELEMENT_NAME = re.compile(r"<w:([A-Za-z0-9]+)")


def _in_schema_order(parts: Sequence[str], order: Sequence[str]) -> str:
    """Sort rendered property elements into the order the schema demands.

    Args:
        parts: Rendered elements, each starting with its own tag.
        order: The canonical child order.

    Returns:
        The elements joined in schema order. Anything the order does not name
        keeps its relative position at the end, which is where the extension
        elements belong.
    """
    index = {name: position for position, name in enumerate(order)}

    def key(item: tuple[int, str]) -> tuple[int, int]:
        position, element = item
        match = _ELEMENT_NAME.match(element)
        name = match.group(1) if match else ""
        return (index.get(name, len(order)), position)

    return "".join(element for _, element in sorted(enumerate(parts), key=key))


def _attr(name: str) -> str:
    """Render a ``w:``-namespaced attribute name.

    Args:
        name: The local name.

    Returns:
        The qualified name.
    """
    return f"w:{name}"


def xml_escape(text: str) -> str:
    """Escape text for XML character data.

    Args:
        text: The raw text.

    Returns:
        The escaped text, control characters removed. Word refuses to open a
        file containing a raw control character, and refusing is correct: the
        character was never legal XML.
    """
    cleaned = "".join(
        char
        for char in text
        if char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF or ord(char) >= 0xE000
    )
    return (
        cleaned.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def xml_attr(text: str) -> str:
    """Escape text for an XML attribute value.

    Args:
        text: The raw text.

    Returns:
        The escaped text.
    """
    return xml_escape(text).replace('"', "&quot;").replace("\n", " ").replace("\t", " ")


def _twips(measure: Measure | None) -> int | None:
    """Convert a length to whole twips, OOXML's unit for almost everything.

    Args:
        measure: The length, or ``None``.

    Returns:
        The length in twips, or ``None`` when unset or relative.
    """
    if measure is None or not measure.is_absolute:
        return None
    return round(measure.to_points() * _TWIP_PER_POINT)


def _half_points(measure: Measure | None) -> int | None:
    """Convert a length to half-points, OOXML's unit for font size.

    Args:
        measure: The length, or ``None``.

    Returns:
        The size in half-points, or ``None``.
    """
    if measure is None or not measure.is_absolute:
        return None
    return max(1, round(measure.to_points() * 2))


def _hex_colour(color: Color | None) -> str | None:
    """Render a colour as OOXML's six-hex-digit sRGB.

    Args:
        color: The colour, or ``None``.

    Returns:
        The hex digits without a leading hash, or ``None``.
    """
    if color is None or color.space in (ColorSpace.AUTO, ColorSpace.NONE):
        return None
    return color.to_hex().lstrip("#").upper()


_HIGHLIGHTS: Mapping[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "green": (0, 128, 0),
    "magenta": (255, 0, 255),
    "red": (255, 0, 0),
    "yellow": (255, 255, 0),
    "white": (255, 255, 255),
    "darkBlue": (0, 0, 139),
    "darkCyan": (0, 139, 139),
    "darkGreen": (0, 100, 0),
    "darkMagenta": (139, 0, 139),
    "darkRed": (139, 0, 0),
    "darkYellow": (128, 128, 0),
    "darkGray": (169, 169, 169),
    "lightGray": (211, 211, 211),
}
"""Word's sixteen fixed highlight colours, the whole palette ``w:highlight`` has."""


def _nearest_highlight(color: Color) -> str:
    """Pick the closest of Word's sixteen highlight colours.

    Args:
        color: The colour asked for.

    Returns:
        The OOXML highlight name.
    """
    red, green, blue = (component * 255 for component in color.to_rgb_tuple())
    return min(
        _HIGHLIGHTS,
        key=lambda name: sum(
            (channel - target) ** 2
            for channel, target in zip((red, green, blue), _HIGHLIGHTS[name])
        ),
    )


_EMPHASIS_VALUES: Mapping[str, str] = {
    "none": "none",
    "dot": "dot",
    "comma": "comma",
    "circle": "circle",
    "under-dot": "underDot",
}
"""The five marks ``w:em`` has, keyed by the IR's own names."""

_VALUES_EMPHASIS: Mapping[str, str] = {value: key for key, value in _EMPHASIS_VALUES.items()}


_UNDERLINE_VALUES: Mapping[UnderlineStyle, str] = {
    UnderlineStyle.NONE: "none",
    UnderlineStyle.SINGLE: "single",
    UnderlineStyle.DOUBLE: "double",
    UnderlineStyle.THICK: "thick",
    UnderlineStyle.DOTTED: "dotted",
    UnderlineStyle.DOTTED_HEAVY: "dottedHeavy",
    UnderlineStyle.DASHED: "dash",
    UnderlineStyle.DASHED_HEAVY: "dashedHeavy",
    UnderlineStyle.DASH_LONG: "dashLong",
    UnderlineStyle.DASH_DOT: "dotDash",
    UnderlineStyle.DASH_DOT_DOT: "dotDotDash",
    UnderlineStyle.WAVY: "wave",
    UnderlineStyle.WAVY_DOUBLE: "wavyDouble",
    UnderlineStyle.WAVY_HEAVY: "wavyHeavy",
    UnderlineStyle.WORDS_ONLY: "words",
}

_VALUES_UNDERLINE: Mapping[str, UnderlineStyle] = {
    value: key for key, value in _UNDERLINE_VALUES.items()
}

_ALIGNMENT_VALUES: Mapping[Alignment, str] = {
    Alignment.LEFT: "left",
    Alignment.RIGHT: "right",
    Alignment.CENTER: "center",
    Alignment.JUSTIFY: "both",
    Alignment.JUSTIFY_LOW: "lowKashida",
    Alignment.DISTRIBUTE: "distribute",
    Alignment.START: "start",
    Alignment.END: "end",
}

_VALUES_ALIGNMENT: Mapping[str, Alignment] = {
    value: key for key, value in _ALIGNMENT_VALUES.items()
}

_VALUES_TAB_ALIGNMENT: Mapping[str, str] = {
    "left": "left",
    "start": "left",
    "center": "center",
    "right": "right",
    "end": "right",
    "decimal": "decimal",
    "bar": "bar",
}
"""``w:tab/@w:val`` back to a :class:`~caissa.core.model.props.TabAlignment`.

``clear`` and ``num`` name no stop the IR has, so a ruler that carries them
comes back without them rather than with a stop nobody asked for.
"""

_VALUES_TAB_LEADER: Mapping[str, str] = {
    "none": "none",
    "dot": "dot",
    "hyphen": "hyphen",
    "underscore": "underscore",
    "middleDot": "middle-dot",
    "heavy": "underscore",
}
"""``w:tab/@w:leader`` back to a :class:`~caissa.core.model.props.TabLeader`."""


# --------------------------------------------------------------------------- #
# Run and paragraph properties
# --------------------------------------------------------------------------- #
def run_props_to_rpr(props: RunProps, context: ExportContext | None = None) -> str:
    """Translate run properties into a ``w:rPr`` element.

    Only what OOXML actually has. Everything else is declared in
    :data:`caissa.export.profiles.DOCX_PROFILE` and reported by
    :meth:`~caissa.export.base.ExportContext.audit_run_props`, so this function
    never has to decide whether a loss matters -- the table already did.

    Args:
        props: The run properties.
        context: The export context, for the highlight substitution note.

    Returns:
        The ``w:rPr`` element, or an empty string when nothing is set.
    """
    parts: list[str] = []
    if props.style:
        parts.append(f'<w:rStyle w:val="{xml_attr(props.style)}"/>')
    if props.font_family:
        family = xml_attr(props.font_family)
        parts.append(
            f'<w:rFonts w:ascii="{family}" w:hAnsi="{family}" w:cs="{family}"/>'
        )
    if props.font_weight is not None:
        parts.append("<w:b/>" if props.font_weight >= 600 else '<w:b w:val="0"/>')
    if props.italic is not None:
        parts.append("<w:i/>" if props.italic else '<w:i w:val="0"/>')
    if props.small_caps is not None:
        parts.append(
            "<w:smallCaps/>" if props.small_caps.value != "none" else '<w:smallCaps w:val="0"/>'
        )
    if props.text_transform is TextTransform.UPPERCASE:
        parts.append("<w:caps/>")
    elif props.text_transform is TextTransform.NONE:
        # ``w:caps w:val="0"`` is how OOXML spells "explicitly not capitalised",
        # which is a different statement from saying nothing at all.
        parts.append('<w:caps w:val="0"/>')
    if props.strikethrough is not None:
        if props.strikethrough is StrikeStyle.DOUBLE:
            parts.append("<w:dstrike/>")
        elif props.strikethrough is StrikeStyle.NONE:
            parts.append('<w:strike w:val="0"/>')
        else:
            parts.append("<w:strike/>")
    if props.outline is not None:
        parts.append("<w:outline/>" if props.outline else '<w:outline w:val="0"/>')
    if props.emboss is not None:
        parts.append("<w:emboss/>" if props.emboss else '<w:emboss w:val="0"/>')
    if props.engrave is not None:
        parts.append("<w:imprint/>" if props.engrave else '<w:imprint w:val="0"/>')
    if props.shadow is not None:
        parts.append("<w:shadow/>")
    if props.hidden is not None:
        parts.append("<w:vanish/>" if props.hidden else '<w:vanish w:val="0"/>')
    colour = _hex_colour(props.color)
    if colour:
        parts.append(f'<w:color w:val="{colour}"/>')
    if props.letter_spacing is not None:
        spacing = _twips(props.letter_spacing)
        if spacing is not None:
            parts.append(f'<w:spacing w:val="{spacing}"/>')
    if props.horizontal_scale is not None:
        parts.append(f'<w:w w:val="{max(1, round(props.horizontal_scale))}"/>')
    if props.kerning is not None:
        minimum = _half_points(props.kerning_min_size) if props.kerning else None
        parts.append(f'<w:kern w:val="{minimum or (2 if props.kerning else 0)}"/>')
    size = _half_points(props.font_size)
    if size is not None:
        parts.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    if props.highlight is not None:
        parts.append(f'<w:highlight w:val="{_nearest_highlight(props.highlight)}"/>')
    if props.background is not None:
        shade = _hex_colour(props.background)
        if shade:
            parts.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    if props.underline is not None:
        value = _UNDERLINE_VALUES.get(props.underline, "single")
        colour = _hex_colour(props.underline_color)
        extra = f' w:color="{colour}"' if colour else ""
        parts.append(f'<w:u w:val="{value}"{extra}/>')
    if props.baseline_shift is not None:
        position = _half_points(props.baseline_shift)
        if position is not None:
            parts.append(f'<w:position w:val="{position}"/>')
    elif (
        props.rise_relative is not None
        and props.font_size is not None
        and props.font_size.is_absolute
    ):
        points = props.rise_relative * props.font_size.to_points()
        parts.append(f'<w:position w:val="{round(points * 2)}"/>')
    if props.vertical_align in (
        VerticalAlign.BASELINE,
        VerticalAlign.SUPERSCRIPT,
        VerticalAlign.SUBSCRIPT,
    ):
        # ``ST_VerticalAlignRun`` has exactly these three values, ``baseline``
        # included: an author who wrote "on the baseline" said something, and
        # OOXML has the word for it.
        parts.append(f'<w:vertAlign w:val="{props.vertical_align.value}"/>')
    if props.language:
        parts.append(f'<w:lang w:val="{xml_attr(props.language)}"/>')
    if props.spell_check is not None:
        parts.append("<w:noProof/>" if not props.spell_check else '<w:noProof w:val="0"/>')
    if props.direction is not None:
        parts.append("<w:rtl/>" if props.direction.value == "rtl" else '<w:rtl w:val="0"/>')
    if props.numeral_spacing is not None:
        parts.append(f'<w:numSpacing w:val="{props.numeral_spacing.value}"/>')
    if props.emphasis_mark is not None:
        parts.append(f'<w:em w:val="{_EMPHASIS_VALUES.get(props.emphasis_mark.value, "none")}"/>')
    if props.ligatures is not None or props.numeral_figure is not None:
        parts.append(_typography_element(props))
    if not parts:
        return ""
    return "<w:rPr>" + _in_schema_order(parts, _RPR_ORDER) + "</w:rPr>"


def _typography_element(props: RunProps) -> str:
    """Render the ``w14`` typography switches OOXML does expose.

    Args:
        props: The run properties.

    Returns:
        The ``w14:ligatures`` and ``w14:numForm`` elements.
    """
    parts: list[str] = []
    if props.ligatures is not None:
        value = {
            "none": "none",
            "standard": "standard",
            "contextual": "standardContextual",
            "discretionary": "standardContextualDiscretional",
            "historical": "standardContextualHistorical",
            "all": "all",
        }.get(props.ligatures.value, "standard")
        parts.append(f'<w14:ligatures w14:val="{value}"/>')
    if props.numeral_figure is not None:
        value = {"lining": "lining", "oldstyle": "oldStyle", "default": "default"}.get(
            props.numeral_figure.value, "default"
        )
        parts.append(f'<w14:numForm w14:val="{value}"/>')
    return "".join(parts)


def paragraph_props_to_ppr(
    props: ParagraphProps | None,
    *,
    extra: Sequence[str] = (),
    numbering: _Numbering | None = None,
    context: ExportContext | None = None,
) -> str:
    """Translate paragraph properties into a ``w:pPr`` element.

    Args:
        props: The paragraph properties, or ``None``.
        extra: Extra child elements, already rendered, inserted after the
            style reference -- a numbering reference or a section break.
        numbering: The document's numbering registry, so a ``NumberingRef``
            can be turned into the ``w:numId`` that names it.
        context: The export context, carried into the paragraph mark's own run
            properties.

    Returns:
        The ``w:pPr`` element, or an empty string.
    """
    parts: list[str] = []
    if props is not None and props.style:
        parts.append(f'<w:pStyle w:val="{xml_attr(props.style)}"/>')
    parts.extend(extra)
    if props is not None:
        parts.extend(_paragraph_body(props, numbering=numbering, context=context))
    if not parts:
        return ""
    return "<w:pPr>" + _in_schema_order(parts, _PPR_ORDER) + "</w:pPr>"


def _paragraph_body(
    props: ParagraphProps,
    *,
    numbering: _Numbering | None = None,
    context: ExportContext | None = None,
) -> list[str]:
    """Render the paragraph-level elements that are not the style reference.

    Args:
        props: The paragraph properties.
        numbering: The document's numbering registry.
        context: The export context, for the paragraph mark's run properties.

    Returns:
        The elements, in schema order.
    """
    parts: list[str] = []
    if props.numbering is not None and numbering is not None:
        parts.append(numbering.reference(props.numbering))
    if props.mark_props is not None:
        # ``w:pPr/w:rPr`` is the paragraph *mark*'s formatting -- ECMA-376
        # CT_ParaRPr -- which is exactly what ``mark_props`` means and what
        # decides how tall an empty paragraph is.
        mark = run_props_to_rpr(props.mark_props, context)
        if mark:
            parts.append(mark)
    if props.keep_together is not None:
        parts.append("<w:keepLines/>" if props.keep_together else '<w:keepLines w:val="0"/>')
    if props.keep_with_next is not None:
        parts.append("<w:keepNext/>" if props.keep_with_next else '<w:keepNext w:val="0"/>')
    if props.page_break_before is not None:
        parts.append(
            "<w:pageBreakBefore/>"
            if props.page_break_before
            else '<w:pageBreakBefore w:val="0"/>'
        )
    if props.widow_control is not None:
        parts.append("<w:widowControl/>" if props.widow_control else '<w:widowControl w:val="0"/>')
    if props.suppress_line_numbers is not None:
        parts.append(
            "<w:suppressLineNumbers/>"
            if props.suppress_line_numbers
            else '<w:suppressLineNumbers w:val="0"/>'
        )
    if props.shading is not None:
        shade = _hex_colour(props.shading)
        if shade:
            parts.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    borders = _borders_element(props)
    if borders:
        parts.append(borders)
    indents = {
        "w:left": _twips(props.indent_left),
        "w:right": _twips(props.indent_right),
        "w:firstLine": _twips(props.indent_first_line),
    }
    given = {name: value for name, value in indents.items() if value is not None}
    if given:
        attributes = " ".join(
            f'{name}="{value}"'
            for name, value in given.items()
            if not (name == "w:firstLine" and value < 0)
        )
        hanging = given.get("w:firstLine")
        if hanging is not None and hanging < 0:
            attributes = (attributes + f' w:hanging="{-hanging}"').strip()
        parts.append(f"<w:ind {attributes}/>")
    spacing = _spacing_element(props)
    if spacing:
        parts.append(spacing)
    if props.contextual_spacing is not None:
        parts.append(
            "<w:contextualSpacing/>"
            if props.contextual_spacing
            else '<w:contextualSpacing w:val="0"/>'
        )
    if props.hyphenate is not None:
        parts.append(
            '<w:suppressAutoHyphens w:val="0"/>'
            if props.hyphenate
            else "<w:suppressAutoHyphens/>"
        )
    if props.direction is not None:
        parts.append("<w:bidi/>" if props.direction.value == "rtl" else '<w:bidi w:val="0"/>')
    if props.alignment is not None:
        parts.append(f'<w:jc w:val="{_ALIGNMENT_VALUES[props.alignment]}"/>')
    if props.outline_level is not None:
        parts.append(f'<w:outlineLvl w:val="{max(0, min(8, props.outline_level))}"/>')
    if props.tab_stops:
        stops = "".join(
            f'<w:tab w:val="{_TAB_ALIGNMENT.get(stop.alignment.value, "left")}" '
            f'w:pos="{_twips(stop.position) or 0}" '
            f'w:leader="{_TAB_LEADER.get(stop.leader.value, "none")}"/>'
            for stop in props.tab_stops
        )
        parts.append(f"<w:tabs>{stops}</w:tabs>")
    return parts


LIST_ORDERED_NUM_ID = 1
"""``w:numId`` of the exporter's own ordered-list numbering."""

LIST_BULLET_NUM_ID = 2
"""``w:numId`` of the exporter's own bulleted-list numbering."""

_RESERVED_NUM_IDS: frozenset[int] = frozenset({LIST_ORDERED_NUM_ID, LIST_BULLET_NUM_ID})
"""The two numberings a ``ListBlock`` uses, which belong to no ``NumberingRef``.

A paragraph inside a list did not ask for numbering: its list did. Reading these
two ids back as a ``NumberingRef`` would invent an author decision, so the
reader maps them to "nothing", and the loss of the list block itself is the one
already declared in :data:`caissa.export.profiles.DOCX_PROFILE`.
"""


class _Numbering:
    """Turns ``NumberingRef`` names into the numeric ids OOXML numbering uses.

    ``w:numId`` is an integer; a ``NumberingRef`` names a definition. The name
    survives because ECMA-376 gives ``w:abstractNum`` a ``w:name`` child, which
    is exactly a human-readable label for a numbering definition -- so the round
    trip goes name -> abstract id -> num id and back.
    """

    def __init__(self) -> None:
        """Create an empty registry holding only the two list numberings."""
        self._abstract: dict[str, int] = {}
        self._nums: dict[tuple[str, int | None, int | None], int] = {}
        self._next_abstract = 3
        self._next_num = 3

    def reference(self, ref: NumberingRef) -> str:
        """Render the ``w:numPr`` that names one numbering reference.

        Args:
            ref: The reference.

        Returns:
            The ``w:numPr`` element.
        """
        level = max(0, min(8, ref.level))
        return (
            f'<w:numPr><w:ilvl w:val="{level}"/>'
            f'<w:numId w:val="{self._num_id(ref)}"/></w:numPr>'
        )

    def _num_id(self, ref: NumberingRef) -> int:
        """Allocate or find the ``w:numId`` for one reference.

        Args:
            ref: The reference.

        Returns:
            The numeric id.
        """
        abstract = self._abstract.get(ref.definition)
        if abstract is None:
            abstract = self._next_abstract
            self._next_abstract += 1
            self._abstract[ref.definition] = abstract
        key = (
            ref.definition,
            ref.level if ref.start_override is not None else None,
            ref.start_override,
        )
        found = self._nums.get(key)
        if found is None:
            found = self._next_num
            self._next_num += 1
            self._nums[key] = found
        return found

    def xml(self) -> str:
        """Render the ``w:abstractNum`` and ``w:num`` elements this document needs.

        Returns:
            The elements, abstracts first as the schema demands.
        """
        abstracts: list[str] = []
        for name, identifier in sorted(self._abstract.items(), key=lambda item: item[1]):
            abstracts.append(
                f'<w:abstractNum w:abstractNumId="{identifier}">'
                f'<w:name w:val="{xml_attr(name)}"/>'
                '<w:multiLevelType w:val="hybridMultilevel"/>'
                + _numbering_levels("decimal", "%1.")
                + "</w:abstractNum>"
            )
        nums: list[str] = []
        for (name, level, start), identifier in sorted(
            self._nums.items(), key=lambda item: item[1]
        ):
            override = ""
            if start is not None:
                override = (
                    f'<w:lvlOverride w:ilvl="{max(0, min(8, level or 0))}">'
                    f'<w:startOverride w:val="{start}"/></w:lvlOverride>'
                )
            nums.append(
                f'<w:num w:numId="{identifier}">'
                f'<w:abstractNumId w:val="{self._abstract[name]}"/>{override}</w:num>'
            )
        return "".join(abstracts) + "".join(nums)


def _spacing_element(props: ParagraphProps) -> str:
    """Render ``w:spacing`` from the space and line-spacing fields.

    Args:
        props: The paragraph properties.

    Returns:
        The element, or an empty string.
    """
    attributes: list[str] = []
    before = _twips(props.space_before)
    after = _twips(props.space_after)
    if before is not None:
        attributes.append(f'w:before="{before}"')
    if after is not None:
        attributes.append(f'w:after="{after}"')
    spacing = props.line_spacing
    if spacing is not None:
        if spacing.rule is LineSpacingRule.MULTIPLE:
            attributes.append(f'w:line="{round(spacing.value * 240)}" w:lineRule="auto"')
        elif spacing.length is not None:
            rule = "exact" if spacing.rule is LineSpacingRule.EXACT else "atLeast"
            attributes.append(f'w:line="{_twips(spacing.length) or 240}" w:lineRule="{rule}"')
    if not attributes:
        return ""
    return f"<w:spacing {' '.join(attributes)}/>"


_TAB_ALIGNMENT: Mapping[str, str] = {
    "left": "left",
    "center": "center",
    "right": "right",
    "decimal": "decimal",
    "bar": "bar",
    "clear": "clear",
}
"""The tab alignments ``w:tab/@w:val`` has."""

_TAB_LEADER: Mapping[str, str] = {
    "none": "none",
    "dot": "dot",
    "hyphen": "hyphen",
    "underscore": "underscore",
    "middle-dot": "middleDot",
    "em-dash": "hyphen",
}
"""The leaders ``w:tab/@w:leader`` has."""

_BORDER_STYLES: Mapping[str, str] = {
    "none": "none",
    "solid": "single",
    "double": "double",
    "dotted": "dotted",
    "dashed": "dashed",
    "dash-dot": "dotDash",
    "dash-dot-dot": "dotDotDash",
    "groove": "threeDEngrave",
    "ridge": "threeDEmboss",
    "inset": "inset",
    "outset": "outset",
    "wave": "wave",
    "thick-thin": "thickThinSmallGap",
    "thin-thick": "thinThickSmallGap",
}


_BORDER_SIDES: tuple[tuple[str, str], ...] = (
    ("top", "top"),
    ("left", "left"),
    ("bottom", "bottom"),
    ("right", "right"),
    ("inside_horizontal", "insideH"),
    ("inside_vertical", "insideV"),
)
"""The six edges of a border box, IR name and OOXML element name."""

_VALUES_BORDER_STYLE: Mapping[str, str] = {
    value: key for key, value in _BORDER_STYLES.items()
}
"""``w:val`` back to a :class:`~caissa.core.model.props.BorderStyle` name."""

_TABLE_ALIGNMENT: Mapping[str, str] = {
    "left": "left",
    "start": "left",
    "center": "center",
    "right": "right",
    "end": "right",
    "justify": "left",
    "justify-low": "left",
    "distribute": "left",
}
"""``w:tblPr/w:jc`` has three positions; the IR's eight map onto them."""


def _borders_element(props: ParagraphProps) -> str:
    """Render ``w:pBdr`` from the paragraph's borders.

    Args:
        props: The paragraph properties.

    Returns:
        The element, or an empty string.
    """
    return _border_box("w:pBdr", props.borders)


def _border_box(name: str, borders: Any) -> str:
    """Render a border box as ``w:pBdr``, ``w:tblBorders`` or ``w:tcBorders``.

    The three elements have the same children, so the paragraph, the table and
    the cell can share one renderer -- and the same quantisation applies to all
    three: eighths of a point for the stroke, whole points for the gap, sRGB
    for the ink.

    Args:
        name: The wrapping element, with its namespace prefix.
        borders: The :class:`~caissa.core.model.props.Borders`, or ``None``.

    Returns:
        The element, or an empty string.
    """
    if borders is None:
        return ""
    parts: list[str] = []
    for side, element in _BORDER_SIDES:
        if element.startswith("inside") and name == "w:pBdr":
            # ``w:pBdr`` has ``between`` and ``bar``; it has no inside grid.
            continue
        border = getattr(borders, side, None)
        if border is None:
            continue
        style = _BORDER_STYLES.get(border.style.value, "single")
        eighths = 4
        if border.width is not None and border.width.is_absolute:
            eighths = max(2, min(96, round(abs(border.width.to_points()) * 8)))
        colour = _hex_colour(border.color) or "auto"
        space = 0
        if border.space is not None and border.space.is_absolute:
            space = max(0, min(31, round(abs(border.space.to_points()))))
        parts.append(
            f'<w:{element} w:val="{style}" w:sz="{eighths}" '
            f'w:space="{space}" w:color="{colour}"/>'
        )
    if not parts:
        return ""
    return f"<{name}>" + "".join(parts) + f"</{name}>"


def _read_border_box(element: ET.Element | None) -> Any:
    """Rebuild a border box from ``w:tblBorders`` or ``w:tcBorders``.

    Args:
        element: The border box element, or ``None``.

    Returns:
        The :class:`~caissa.core.model.props.Borders`, or ``None``.
    """
    if element is None:
        return None
    from caissa.core.model import Border, Borders, BorderStyle

    sides: dict[str, Any] = {}
    for side, name in _BORDER_SIDES:
        found = element.find(f"{{{W}}}{name}")
        if found is None:
            continue
        style = _VALUES_BORDER_STYLE.get(found.get(f"{{{W}}}val") or "single", "solid")
        raw = found.get(f"{{{W}}}color") or "auto"
        colour = Color.from_hex("#" + raw) if re.fullmatch(r"[0-9A-Fa-f]{6}", raw) else None
        width = Measure(value=float(found.get(f"{{{W}}}sz") or "4") / 8, unit=LengthUnit.PT)
        space = Measure(value=float(found.get(f"{{{W}}}space") or "0"), unit=LengthUnit.PT)
        sides[side] = Border(
            style=BorderStyle(style), width=width, color=colour, space=space
        )
    return Borders(**sides) if sides else None


def _margins_element(name: str, padding: Any) -> str:
    """Render ``w:tblCellMar`` or ``w:tcMar`` from a padding box.

    Args:
        name: The wrapping element, with its namespace prefix.
        padding: The :class:`~caissa.core.model.props.Padding`, or ``None``.

    Returns:
        The element, or an empty string.
    """
    if padding is None:
        return ""
    parts: list[str] = []
    for side in ("top", "left", "bottom", "right"):
        value = _twips(getattr(padding, side, None))
        if value is None:
            continue
        parts.append(f'<w:{side} w:w="{max(0, value)}" w:type="dxa"/>')
    if not parts:
        return ""
    return f"<{name}>" + "".join(parts) + f"</{name}>"


def _table_width(width: Measure | None) -> str:
    """Render ``w:tblW`` from a table's width.

    Args:
        width: The width, or ``None``.

    Returns:
        The element. A table with no width, or one measured in a unit the
        ruler has no name for, comes out as ``auto``.
    """
    if width is not None and width.unit is LengthUnit.PERCENT:
        return f'<w:tblW w:w="{max(0, round(width.value * 50))}" w:type="pct"/>'
    twips = _twips(width)
    if twips is None:
        return '<w:tblW w:w="0" w:type="auto"/>'
    return f'<w:tblW w:w="{max(0, twips)}" w:type="dxa"/>'


def _read_table_width(element: ET.Element | None) -> Measure | None:
    """Rebuild a table width from ``w:tblW``.

    Args:
        element: The ``w:tblW``, or ``None``.

    Returns:
        The width, or ``None`` when the table is automatic.
    """
    if element is None:
        return None
    kind = element.get(f"{{{W}}}type") or "auto"
    raw = float(element.get(f"{{{W}}}w") or "0")
    if kind == "pct":
        return Measure(value=raw / 50, unit=LengthUnit.PERCENT)
    if kind == "dxa" and raw:
        return Measure(value=raw, unit=LengthUnit.TWIP)
    return None


def _table_alignment(alignment: Any) -> str:
    """Render ``w:tblPr/w:jc`` from a table's alignment.

    Args:
        alignment: The :class:`~caissa.core.model.props.Alignment`, or ``None``.

    Returns:
        The element, or an empty string.
    """
    if alignment is None:
        return ""
    return f'<w:jc w:val="{_TABLE_ALIGNMENT.get(alignment.value, "left")}"/>'


def _read_margins(element: ET.Element | None) -> Any:
    """Rebuild a padding box from ``w:tblCellMar`` or ``w:tcMar``.

    Args:
        element: The margin element, or ``None``.

    Returns:
        The :class:`~caissa.core.model.props.Padding`, or ``None``.
    """
    if element is None:
        return None
    from caissa.core.model import Padding

    sides: dict[str, Any] = {}
    for side in ("top", "left", "bottom", "right"):
        found = element.find(f"{{{W}}}{side}")
        if found is None or found.get(f"{{{W}}}w") is None:
            continue
        sides[side] = Measure(
            value=float(found.get(f"{{{W}}}w") or "0"), unit=LengthUnit.TWIP
        )
    return Padding(**sides) if sides else None


# --------------------------------------------------------------------------- #
# The exporter
# --------------------------------------------------------------------------- #
class DocxExporter(Exporter):
    """Writes a Word document with real styles, real fields and vector art."""

    format_name: ClassVar[str] = "docx"
    profile: ClassVar[Any] = DOCX_PROFILE
    suffix: ClassVar[str] = ".docx"

    def write(
        self, document: Document, destination: Path, context: ExportContext
    ) -> ExportResult:
        """Write the package.

        Args:
            document: The IR to write.
            destination: The ``.docx`` file.
            context: The export context.

        Returns:
            The result.

        Raises:
            ExportError: The package could not be written.
        """
        builder = _Body(context, document)
        body = builder.render()

        media: list[tuple[str, bytes, str]] = builder.media
        relationships = builder.relationships
        parts: dict[str, bytes] = {
            "[Content_Types].xml": _content_types(media).encode("utf-8"),
            "_rels/.rels": _root_rels().encode("utf-8"),
            "word/document.xml": _document_xml(body, document, context).encode("utf-8"),
            "word/_rels/document.xml.rels": _document_rels(relationships).encode("utf-8"),
            "word/styles.xml": _styles_xml(document, context).encode("utf-8"),
            "word/numbering.xml": _numbering_xml(builder.numbering).encode("utf-8"),
            "word/settings.xml": _settings_xml(context).encode("utf-8"),
            "word/fontTable.xml": _font_table_xml(builder.families).encode("utf-8"),
            "word/footnotes.xml": builder.footnotes_xml().encode("utf-8"),
            "word/endnotes.xml": builder.endnotes_xml().encode("utf-8"),
            "docProps/core.xml": _core_xml(document).encode("utf-8"),
            "docProps/app.xml": _app_xml(document, context).encode("utf-8"),
        }
        for name, data, _ in media:
            parts[f"word/media/{name}"] = data

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in parts.items():
                    archive.writestr(name, data)
        except OSError as error:
            raise ExportError(f"Nao foi possivel gravar {destination}: {error}") from error

        context.count("bytes", destination.stat().st_size)
        if builder.emf_count:
            context.note(
                f"{builder.emf_count} diagrama(s) gravado(s) como EMF vetorial; "
                "o Word os escala sem perda e a impressora os desenha na resolucao "
                "do dispositivo."
            )
        if builder.png_count:
            context.note(
                f"{builder.png_count} diagrama(s) nao puderam virar EMF e sairam como "
                f"PNG de {context.options.diagram_dpi} DPI. Cada um tem um aviso de "
                "rasterizacao com o motivo."
            )
        return context.finish(destination)


class _Body:
    """Renders the IR into ``w:body`` content, collecting what the package needs."""

    def __init__(self, context: ExportContext, document: Document) -> None:
        """Create a body builder.

        Args:
            context: The export context.
            document: The document being written.
        """
        self.context = context
        self.document = document
        self.diagrams = DiagramRenderer(context)
        self.media: list[tuple[str, bytes, str]] = []
        self.relationships: list[tuple[str, str, str]] = []
        self.families: set[str] = set()
        self.footnotes: list[Footnote] = []
        self.endnotes: list[Endnote] = []
        self.emf_count = 0
        self.png_count = 0
        self._bookmark_id = 0
        self._sequence: dict[str, int] = {}
        self._drawing_id = 0
        self.numbering = _Numbering()
        self._movetext_started = False

    # -- entry point -------------------------------------------------------

    def render(self) -> str:
        """Render every block, plus the trailing section properties.

        Returns:
            The body content.
        """
        # The notes are indexed first: ``w:footnoteReference`` has to name the
        # note's number, and a reference usually appears before the note that
        # answers it.
        self._collect_notes()
        self.context.audit_node(self.document)
        parts = [self.block(node) for node in self.document.body]
        parts.append(_section_properties(self.context.options))
        return "\n".join(part for part in parts if part)

    def _collect_notes(self) -> None:
        """Walk the tree once and index every note, wherever it sits."""
        from caissa.core.model import walk

        for _, node in walk(self.document):
            if isinstance(node, Footnote):
                self.footnotes.append(node)
            elif isinstance(node, Endnote):
                self.endnotes.append(node)

    # -- identity ----------------------------------------------------------

    def bookmark(self, node: Any, body: str) -> str:
        """Wrap rendered content in the bookmark that carries the node's id.

        Args:
            node: The node.
            body: Its rendered OOXML.

        Returns:
            The wrapped content, or ``body`` unchanged when identity tracking
            is off or the content is empty.
        """
        if not getattr(self.context.options, "track_identity", True) or not body:
            return body
        name = f"{BOOKMARK_PREFIX}{node.id}"
        if len(name) > _MAX_BOOKMARK:
            return body
        self._bookmark_id += 1
        identifier = self._bookmark_id
        return (
            f'<w:bookmarkStart w:id="{identifier}" w:name="{xml_attr(name)}"/>'
            f"{body}"
            f'<w:bookmarkEnd w:id="{identifier}"/>'
        )

    def marker(self, node: Any) -> str:
        """Write an empty bookmark that records where a node sat in the flow.

        A footnote's body lives in ``word/footnotes.xml``, outside the story,
        and the document itself has no element of its own at all. An empty
        bookmark is how OOXML names a *place*, so the place survives even
        though the content moved.

        Args:
            node: The node whose position is being recorded.

        Returns:
            The bookmark pair, or an empty string when identity tracking is off.
        """
        if not getattr(self.context.options, "track_identity", True):
            return ""
        name = f"{BOOKMARK_PREFIX}{node.id}"
        if len(name) > _MAX_BOOKMARK:
            return ""
        self._bookmark_id += 1
        return (
            f'<w:bookmarkStart w:id="{self._bookmark_id}" w:name="{xml_attr(name)}"/>'
            f'<w:bookmarkEnd w:id="{self._bookmark_id}"/>'
        )

    # -- blocks ------------------------------------------------------------

    def block(self, node: Block) -> str:
        """Render one block.

        Args:
            node: The block.

        Returns:
            The OOXML.
        """
        with self.context.at(f"{tag_of(node)}/"):
            self.context.count("nodes")
            self.context.audit_node(node)
            handler = getattr(self, f"_block_{tag_of(node)}", None)
            if handler is None:
                return ""
            props = getattr(node, "props", None)
            if isinstance(props, ParagraphProps):
                self.context.audit_paragraph_props(props, node=node)
                if props.default_run is not None:
                    self.context.degrade(
                        self.context.profile.paragraph_support("default_run"),
                        prop="default_run",
                        node=node,
                        original=props.default_run,
                    )
            rendered = str(handler(node))
            if tag_of(node) in _SELF_IDENTIFIED:
                return rendered
            return self.bookmark(node, rendered)

    def blocks(self, nodes: Sequence[Block]) -> str:
        """Render a sequence of blocks.

        Args:
            nodes: The blocks.

        Returns:
            The OOXML.
        """
        return "".join(self.block(node) for node in nodes if node is not None)

    def _paragraph(
        self, props: ParagraphProps | None, content: str, *, extra: Sequence[str] = ()
    ) -> str:
        """Assemble one ``w:p``.

        Args:
            props: Its paragraph properties.
            content: The rendered runs.
            extra: Extra ``w:pPr`` children.

        Returns:
            The paragraph.
        """
        rendered = paragraph_props_to_ppr(
            props, extra=extra, numbering=self.numbering, context=self.context
        )
        return f"<w:p>{rendered}{content}</w:p>"

    def _block_heading(self, node: Heading) -> str:
        style = f"Heading{min(max(node.level, 1), 9)}"
        # A heading takes the heading style even when the author named another
        # one. Word's outline, its navigation pane and the TOC field all key off
        # the built-in Heading styles: a heading left in a style called
        # "Titulo1" stops being a heading in Word. Losing the author's own name
        # is the approximation ``_DOCX_PARAGRAPH["style"]`` declares.
        props = _force_paragraph_style(node.props, style)
        content = ""
        if node.numbering_text:
            content += _run(f"{node.numbering_text}\t", node.run_props, self.context)
        content += self.inlines(node.content, node.props.default_run)
        anchor = ""
        if node.anchor:
            self._bookmark_id += 1
            anchor = (
                f'<w:bookmarkStart w:id="{self._bookmark_id}" '
                f'w:name="{xml_attr(node.anchor)}"/>'
                f'<w:bookmarkEnd w:id="{self._bookmark_id}"/>'
            )
        return self._paragraph(props, anchor + content)

    def _block_paragraph(self, node: Paragraph) -> str:
        extra: list[str] = []
        if node.drop_cap:
            self.context.audit_feature("drop_cap", node=node, original="capitular")
            extra.append(_frame_properties(node.drop_cap))
        return self._paragraph(
            node.props,
            self.inlines(node.content, node.props.default_run),
            extra=extra,
        )

    def _block_quote(self, node: Quote) -> str:
        parts = []
        for child in node.content:
            rendered = self.block(child)
            parts.append(_force_style(rendered, "Quote"))
        if node.attribution:
            parts.append(
                self._paragraph(
                    _with_style(ParagraphProps(), "QuoteAttribution"),
                    self.inlines(node.attribution),
                )
            )
        return "".join(parts)

    def _block_callout(self, node: Callout) -> str:
        self.context.audit_feature("callout", node=node, original=node.kind.value)
        title = (
            self.inlines(node.title)
            if node.title
            else _run(
                _CALLOUT_LABEL.get(node.kind, "Nota"),
                RunProps(font_weight=700),
                self.context,
            )
        )
        head = self._paragraph(_with_style(node.props, "Callout"), title)
        return head + "".join(_force_style(self.block(child), "Callout") for child in node.content)

    def _block_list_block(self, node: ListBlock) -> str:
        numbering = 1 if node.kind is ListKind.ORDERED else 2
        return "".join(
            self._list_item(item, numbering, 0) for item in node.items
        )

    def _list_item(self, item: ListItem, numbering: int, level: int) -> str:
        self.context.count("nodes")
        self.context.audit_node_fields(item)
        reference = (
            f'<w:numPr><w:ilvl w:val="{min(level, 8)}"/>'
            f'<w:numId w:val="{numbering}"/></w:numPr>'
        )
        parts: list[str] = []
        for index, child in enumerate(item.content):
            rendered = self.block(child)
            if index == 0 and rendered.startswith("<w:p>"):
                rendered = _insert_ppr(rendered, reference, "ListParagraph")
            parts.append(rendered)
        return self.bookmark(item, "".join(parts))

    def _block_code_block(self, node: CodeBlock) -> str:
        lines = node.text.split("\n")
        return "".join(
            self._paragraph(
                _with_style(node.props, "Code"),
                _run(line, RunProps(font_family="Consolas"), self.context),
            )
            for line in lines
        )

    def _block_math_block(self, node: MathBlock) -> str:
        self.context.audit_feature("math", node=node, original="LaTeX")
        return self._paragraph(
            _with_style(node.props, "Code"),
            _run(node.latex, RunProps(font_family="Cambria Math"), self.context),
        )

    def _block_table(self, node: Table) -> str:
        rows: list[str] = []
        for row in node.rows:
            self.context.count("nodes")
            self.context.audit_node_fields(row)
            cells: list[str] = []
            for cell in row.cells:
                self.context.count("nodes")
                self.context.audit_node_fields(cell)
                content = self.blocks(cell.content) or "<w:p/>"
                span = (
                    f'<w:gridSpan w:val="{cell.col_span}"/>' if cell.col_span > 1 else ""
                )
                shade = _hex_colour(cell.shading)
                shading = (
                    f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ""
                )
                vertical = ""
                if cell.vertical_alignment is not None:
                    vertical = (
                        '<w:vAlign w:val="'
                        f'{_CELL_VALIGN.get(cell.vertical_alignment.value, "top")}"/>'
                    )
                rendered = _in_schema_order(
                    [
                        part
                        for part in (
                            span,
                            _border_box("w:tcBorders", cell.borders),
                            shading,
                            _margins_element("w:tcMar", cell.padding),
                            vertical,
                        )
                        if part
                    ],
                    _TCPR_ORDER,
                )
                # ``EG_ContentCellContent`` admits ``EG_RunLevelElts``, and a
                # bookmark is one: the cell keeps its identity without a
                # paragraph having to carry it.
                cells.append(
                    self.bookmark(
                        cell, f"<w:tc><w:tcPr>{rendered}</w:tcPr>{content}</w:tc>"
                    )
                )
            row_properties: list[str] = []
            height = _twips(row.height)
            if height is not None:
                row_properties.append(
                    f'<w:trHeight w:val="{max(0, height)}" w:hRule="atLeast"/>'
                )
            if row.keep_together:
                row_properties.append("<w:cantSplit/>")
            if row.is_header:
                row_properties.append("<w:tblHeader/>")
            trailer = (
                "<w:trPr>" + _in_schema_order(row_properties, _TRPR_ORDER) + "</w:trPr>"
                if row_properties
                else ""
            )
            rows.append(self.bookmark(row, f"<w:tr>{trailer}{''.join(cells)}</w:tr>"))
        columns = node.column_count or max((len(row.cells) for row in node.rows), default=1)
        widths = [
            _twips(column.width) if index < len(node.columns) else None
            for index, column in enumerate(node.columns)
        ]
        grid = "".join(
            f'<w:gridCol w:w="{widths[index] if index < len(widths) and widths[index] else 2000}"/>'
            for index in range(max(1, columns))
        )
        table = (
            "<w:tbl><w:tblPr>"
            f'<w:tblStyle w:val="{xml_attr(node.style or "TableGrid")}"/>'
            + _table_width(node.width)
            + _table_alignment(node.alignment)
            + _border_box("w:tblBorders", node.borders)
            + _margins_element("w:tblCellMar", node.cell_padding)
            + (
                f'<w:tblDescription w:val="{xml_attr(node.summary)}"/>'
                if node.summary
                else ""
            )
            + "</w:tblPr>"
            f"<w:tblGrid>{grid}</w:tblGrid>"
            f"{''.join(rows)}</w:tbl>"
        )
        caption = ""
        if node.caption:
            caption = self._caption("Tabela", node.caption)
        # The bookmark hugs ``w:tbl`` rather than the whole fragment: wrapping
        # the caption too would hand the table's identity to the caption
        # paragraph, and the re-import would report a table that became a
        # paragraph.
        # A table must be followed by a paragraph or Word inserts one silently.
        return caption + self.bookmark(node, table) + "<w:p/>"

    def _block_figure(self, node: Figure) -> str:
        body = self.blocks(node.content)
        caption = self._caption("Figura", node.caption) if node.caption else ""
        return body + caption

    def _block_diagram(self, node: Diagram) -> str:
        rendered = self.diagrams.svg(node)
        picture = self._picture(
            rendered.svg,
            rendered.width_mm,
            rendered.height_mm,
            node,
            extension=_diagram_extension(node),
        )
        parts = [
            self._paragraph(
                _with_style(ParagraphProps(alignment=Alignment.CENTER), "Diagram"), picture
            )
        ]
        if node.stipulation:
            parts.insert(
                0,
                self._paragraph(
                    _with_style(ParagraphProps(alignment=Alignment.CENTER), "Caption"),
                    _run(node.stipulation, RunProps(italic=True), self.context),
                ),
            )
        if node.caption or node.number is not None:
            parts.append(self._caption("Diagrama", node.caption or ()))
        if node.solution is not None and node.solution.children:
            # A study whose solution is only in the IR is a study the book does
            # not print. It goes in as its own movetext, with the same
            # per-move bookmarks a ``GameScore`` block gets.
            parts.append(self._block_game_score(node.solution))
        return "".join(parts)

    def _block_image_block(self, node: ImageBlock) -> str:
        # The alignment is written only when the author set one: the Diagram
        # style already centres, and a ``w:jc`` the node never asked for would
        # come back as an alignment the node never had.
        props = ParagraphProps(alignment=node.alignment)
        return self._paragraph(_with_style(props, "Diagram"), self._raster_picture(node))

    def _raster_picture(self, node: ImageBlock | ImageInline) -> str:
        """Embed the raster image a node refers to as a ``w:drawing``.

        A scanned page, a figure the text placed, an OCR region the reader
        abstained on: each is an image resource with bytes on disk after an
        import, and a Word file that shows ``[figura-p12-0003]`` where the
        page was is a Word file with the book missing. The bytes go in as an
        image part (PNG, JPEG and GIF as they are; SVG rasterised at the
        diagram DPI; anything else re-encoded as PNG) and the node becomes the
        same picture the diagrams use. The size is what the node asked for;
        failing that, the pixels at the resource's resolution (96 dpi when
        unstated); either way capped at the text width so a full-page scan
        fits the page.

        **The node travels in the picture's own fields**, so :func:`read_docx`
        can rebuild it from ``word/document.xml`` alone: the resource key in
        ``wp:docPr/@name``, the alternative text in ``@descr``, the title in
        ``@title``, the crop in ``a:srcRect``. A resource whose file is not
        there gets a grey placeholder picture -- the counterpart of the
        ``image-missing`` box the XHTML writes -- with the key still in the
        name, and the report says so through the ``images`` feature.
        """
        resource = self.context.document.resource(node.resource)
        path = Path(resource.path) if resource is not None and resource.path else None
        data: bytes | None = None
        suffix = "png"
        if path is not None and path.is_file():
            suffix = path.suffix.lower().lstrip(".")
            if suffix == "jpeg":
                suffix = "jpg"
            try:
                if suffix == "svg":
                    data = svg_to_png(
                        path.read_text(encoding="utf-8"), dpi=self.context.options.diagram_dpi
                    )
                    suffix = "png"
                elif suffix in ("png", "jpg", "gif"):
                    data = path.read_bytes()
                else:
                    data = _to_png(path)
                    suffix = "png"
            except Exception as error:  # noqa: BLE001 - an unreadable file is a placeholder
                self.context.recorder.substituted(
                    prop="images",
                    node=node,
                    path=self.context.path,
                    original=node.resource,
                    detail=f"A imagem {path.name} nao pode ser lida ({error}).",
                    replacement="quadro de reserva",
                )
        else:
            self.context.audit_feature("images", node=node, original=node.resource)
        if data is None:
            data, suffix = _placeholder_png(), "png"
        width_mm, height_mm = self._image_size_mm(node, resource, data, suffix)
        name = f"imagem{len(self.media) + 1}.{suffix}"
        self.media.append((name, data, suffix))
        relationship = f"rIdImg{len(self.media)}"
        self.relationships.append((relationship, f"{R}/image", f"media/{name}"))
        self._drawing_id += 1
        self.context.count("images")
        return _drawing(
            relationship,
            self._drawing_id,
            round(width_mm * EMU_PER_MM),
            round(height_mm * EMU_PER_MM),
            node.alt_text or "",
            name=node.resource,
            title=getattr(node, "title", None),
            crop=tuple(getattr(node, "crop", ()) or ()),
        )

    def _image_size_mm(
        self,
        node: ImageBlock | ImageInline,
        resource: Resource | None,
        data: bytes,
        suffix: str,
    ) -> tuple[float, float]:
        """The picture's size on the page, in millimetres, capped at the text width."""
        options = self.context.options
        page_width = float(getattr(options, "page_width_mm", 148.0))
        text_width = page_width - 2 * float(getattr(options, "margin_mm", 18.0))
        pixels = _raster_pixels(data, suffix)
        if pixels is None and resource is not None and resource.width and resource.height:
            pixels = (int(resource.width), int(resource.height))
        dpi = float((resource.dpi if resource is not None else None) or 96.0)
        ratio = (pixels[1] / pixels[0]) if pixels and pixels[0] else 1.0
        crop = tuple(getattr(node, "crop", ()) or ())
        if len(crop) == _CROP_EDGES:
            # The picture shows the cropped part, so the shape to keep is the crop's.
            visible_width = max(1e-6, crop[2] - crop[0])
            visible_height = max(1e-6, crop[3] - crop[1])
            ratio = ratio * visible_height / visible_width
        asked_width = _mm(node.width)
        asked_height = _mm(node.height)
        if asked_width is not None:
            width = asked_width
            height = asked_height if asked_height is not None else width * ratio
        elif asked_height is not None:
            height = asked_height
            width = height / ratio if ratio else height
        else:
            width = (pixels[0] / dpi * 25.4) if pixels else text_width
            height = width * ratio
        if width > text_width:
            height = height * text_width / width
            width = text_width
        return max(1.0, width), max(1.0, height)

    def _block_game_score(self, node: GameScore) -> str:
        """The movetext as one run per token, each move bookmarked.

        Writing the whole game as a single string of PGN is what a word
        processor would do, and it is what made the move tree stop existing on
        the way back: a string has no places to hang identities on. One ``w:r``
        per token costs a few hundred bytes and gives every move a bookmark, so
        the tree is still a tree after the round trip. The text in the file is
        unchanged -- it is still readable PGN.
        """
        self.context.count("games")
        # The style is forced, not defaulted: it is the only thing that tells
        # the reader this paragraph is a movetext and not prose, so a game left
        # in some other style would come back as a bag of text runs.
        return self.bookmark(
            node,
            self._paragraph(
                _force_paragraph_style(getattr(node, "props", None), "GameScore"),
                self._movetext(node),
            ),
        )

    def _movetext(self, node: GameScore) -> str:
        """Render the movetext of one game as a run per token.

        Args:
            node: The game.

        Returns:
            The runs.
        """
        from caissa.export.text import escape_pgn_comment

        runs: list[str] = []
        if node.initial_comment:
            runs.append(
                self._game_token(f"{{{escape_pgn_comment(node.initial_comment)}}}")
            )
        self._game_line(node.children, runs, force_number=True)
        runs.append(self._game_token(node.result))
        return "".join(runs)

    def _game_token(self, text: str, *, space: bool = True) -> str:
        """Render one movetext token, preceded by its separating space.

        Args:
            text: The token.
            space: Whether a space belongs in front of it. A closing bracket
                takes none, and neither does the first token of a line.

        Returns:
            The runs: the space, when there is one, and then the token.
        """
        lead = _SPACE_RUN if space and self._movetext_started else ""
        self._movetext_started = True
        return lead + _run(text, None, self.context)

    def _game_line(
        self, children: Sequence[Any], runs: list[str], *, force_number: bool
    ) -> None:
        """Write a mainline and its alternatives, mirroring ``game_to_pgn``.

        The shape is the one :func:`caissa.export.text.game_to_pgn` documents:
        ``children[1:]`` are alternatives to ``children[0]``, so they are
        written after it, and the line then continues into ``children[0]``'s own
        children.

        Args:
            children: The continuations; ``children[0]`` is the mainline.
            runs: Collector for the rendered runs.
            force_number: Print the move number even for a Black move.
        """
        current: Sequence[Any] = children
        needs_number = force_number
        while current:
            main = current[0]
            needs_number = self._game_move(main, runs, force_number=needs_number)
            for alternative in current[1:]:
                runs.append(self._game_token("("))
                self._movetext_started = False
                self._game_line((alternative,), runs, force_number=True)
                runs.append(self._game_token(")", space=False))
                self._movetext_started = True
                needs_number = True
            current = main.children

    def _game_move(self, node: Any, runs: list[str], *, force_number: bool) -> bool:
        """Write one move: its comments, number, SAN and NAGs.

        Args:
            node: The move node.
            runs: Collector for the rendered runs.
            force_number: Print the number even for a Black move.

        Returns:
            Whether the next move needs an explicit number.
        """
        from caissa.export.text import escape_pgn_comment, move_commands

        self.context.count("nodes")
        self.context.audit_node(node)
        # The number comes before the starting comment, which is the one place
        # this movetext departs from ``game_to_pgn``. It is what makes the two
        # kinds of comment tell themselves apart on the way back: everything
        # between a number and a move belongs to the move ahead, everything
        # between a move and the next number belongs to the move behind.
        if not node.is_black_move:
            runs.append(self._game_token(f"{node.move_number}."))
        elif force_number or node.comment_before:
            runs.append(self._game_token(f"{node.move_number}..."))
        if node.comment_before:
            runs.append(self._game_token(f"{{{escape_pgn_comment(node.comment_before)}}}"))
        # The bookmark hugs the run that holds the SAN, which is the one place
        # in the file where this move exists.
        emphasis = RunProps(font_weight=700) if node.emphasis else None
        runs.append(_SPACE_RUN if self._movetext_started else "")
        self._movetext_started = True
        runs.append(self.bookmark(node, _run(node.san, emphasis, self.context)))
        for nag in node.nags:
            runs.append(self._game_token(f"${nag}"))
        trailing = False
        if node.comment_after:
            runs.append(self._game_token(f"{{{escape_pgn_comment(node.comment_after)}}}"))
            trailing = True
        commands = move_commands(node)
        if commands:
            runs.append(self._game_token(f"{{{commands}}}"))
            trailing = True
        return trailing

    def _block_footnote(self, node: Footnote) -> str:
        # Already indexed by ``_collect_notes``; the note itself lives in
        # word/footnotes.xml rather than in the body. What stays here is the
        # empty bookmark that remembers where in the story the note was written.
        return self.marker(node)

    def _block_endnote(self, node: Endnote) -> str:
        return self.marker(node)

    def _block_page_break(self, node: PageBreak) -> str:
        return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'

    def _block_section_break(self, node: SectionBreak) -> str:
        columns = ""
        if node.columns is not None:
            columns = f'<w:cols w:num="{node.columns.count}"/>'
        header = ""
        if node.header_text or node.footer_text:
            self.context.audit_feature(
                "headers_footers", node=node, original="cabecalho/rodape"
            )
        return (
            "<w:p><w:pPr><w:sectPr>"
            '<w:type w:val="nextPage"/>'
            f"{columns}{header}"
            "</w:sectPr></w:pPr></w:p>"
        )

    def _block_thematic_break(self, node: ThematicBreak) -> str:
        if node.ornament:
            return self._paragraph(
                ParagraphProps(alignment=Alignment.CENTER),
                _run(node.ornament, RunProps(), self.context),
            )
        return (
            "<w:p><w:pPr><w:pBdr>"
            '<w:bottom w:val="single" w:sz="6" w:space="1" w:color="auto"/>'
            "</w:pBdr></w:pPr></w:p>"
        )

    def _block_group(self, node: Group) -> str:
        title = ""
        if node.title:
            title = self._paragraph(
                _with_style(ParagraphProps(), "GroupTitle"), self.inlines(node.title)
            )
        if node.columns:
            self.context.audit_feature("columns", node=node, original=str(node.columns))
        return title + self.blocks(node.content)

    def _block_table_of_contents(self, node: TableOfContents) -> str:
        """The TOC as a real field, so Word owns it and can update it."""
        instruction = f'TOC \\o "{node.min_level}-{node.max_level}" \\h \\z \\u'
        title = (
            self._paragraph(_with_style(ParagraphProps(), "TOCHeading"), self.inlines(node.title))
            if node.title
            else ""
        )
        return title + (
            "<w:p><w:pPr><w:pStyle w:val=\"TOC1\"/></w:pPr>"
            '<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> {xml_escape(instruction)} '
            "</w:instrText></w:r>"
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            "<w:r><w:t>Atualize o sumario (F9) para gerar as entradas.</w:t></w:r>"
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            "</w:p>"
        )

    def _block_raw_passthrough(self, node: RawPassthrough) -> str:
        if node.format.lower() in ("ooxml", "docx", "wordprocessingml"):
            return node.text
        self.context.audit_feature("raw_passthrough", node=node, original=node.format)
        return ""

    # -- captions and fields ----------------------------------------------

    def _caption(self, label: str, content: Sequence[Inline]) -> str:
        """Render a caption whose number is a live ``SEQ`` field.

        Args:
            label: The sequence name, ``"Figura"`` or ``"Diagrama"``.
            content: The caption text.

        Returns:
            The caption paragraph.
        """
        self._sequence[label] = self._sequence.get(label, 0) + 1
        number = self._sequence[label]
        field = (
            f"<w:r><w:t xml:space=\"preserve\">{xml_escape(label)} </w:t></w:r>"
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> SEQ {xml_escape(label)} '
            '\\* ARABIC </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f"<w:r><w:t>{number}</w:t></w:r>"
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        )
        body = self.inlines(content) if content else ""
        separator = '<w:r><w:t xml:space="preserve"> — </w:t></w:r>' if body else ""
        return self._paragraph(
            _with_style(ParagraphProps(alignment=Alignment.CENTER), "Caption"),
            field + separator + body,
        )

    # -- pictures ----------------------------------------------------------

    def _picture(
        self,
        svg: str,
        width_mm: float,
        height_mm: float,
        node: Any,
        *,
        extension: str = "",
    ) -> str:
        """Embed a diagram, vector first.

        Args:
            svg: The canonical diagram SVG.
            width_mm: Intrinsic width.
            height_mm: Intrinsic height.
            node: The diagram node, for the degradation report.
            extension: An ``a:extLst`` for ``wp:docPr`` -- the node's own
                fields, so the reader can rebuild it (:func:`_diagram_extension`).

        Returns:
            The run containing the drawing.
        """
        self.context.count("diagrams")
        alt = diagram_alt_text(node)
        data: bytes
        suffix: str
        try:
            if not self.context.options.vector_diagrams:
                raise EmfError("vetorial desativado nas opcoes")
            image = svg_to_emf(svg, width_mm=width_mm)
            data, suffix = image.data, "emf"
            width_mm, height_mm = image.width_mm, image.height_mm
            self.emf_count += 1
            self.context.count("diagrams_emf")
            for note in image.notes:
                self.context.recorder.approximated(
                    prop="vector_diagram",
                    node=node,
                    path=self.context.path,
                    original="SVG",
                    detail=note,
                )
        except Exception as error:  # noqa: BLE001 - any failure means raster
            data = svg_to_png(svg, dpi=self.context.options.diagram_dpi)
            suffix = "png"
            self.png_count += 1
            self.context.count("diagrams_png")
            self.context.rasterised(
                node=node,
                detail=(
                    f"O diagrama nao pode ser convertido para EMF vetorial "
                    f"({error}); foi gravado como PNG de "
                    f"{self.context.options.diagram_dpi} DPI."
                ),
            )
        name = f"diagrama{len(self.media) + 1}.{suffix}"
        self.media.append((name, data, suffix))
        relationship = f"rIdImg{len(self.media)}"
        self.relationships.append(
            (
                relationship,
                f"{R}/image",
                f"media/{name}",
            )
        )
        self._drawing_id += 1
        return _drawing(
            relationship,
            self._drawing_id,
            round(width_mm * EMU_PER_MM),
            round(height_mm * EMU_PER_MM),
            alt,
            extension=extension,
        )

    # -- inlines -----------------------------------------------------------

    def inlines(self, nodes: Sequence[Inline], inherited: RunProps | None = None) -> str:
        """Render inline content.

        Args:
            nodes: The inlines.
            inherited: Formatting the paragraph hands down to every run --
                ``ParagraphProps.default_run``, which OOXML has no element for
                and which therefore has to be written onto each run.

        Returns:
            The OOXML runs.
        """
        return "".join(self.inline(node, inherited) for node in nodes)

    def inline(self, node: Inline, inherited: RunProps | None = None) -> str:
        """Render one inline.

        Args:
            node: The inline.
            inherited: Formatting from an enclosing wrapper.

        Returns:
            The OOXML.
        """
        self.context.count("nodes")
        self.context.audit_node(node)
        props = getattr(node, "props", None)
        if isinstance(props, RunProps):
            self.context.audit_run_props(props, node=node)
            if props.font_family:
                self.families.add(props.font_family)
        handler = getattr(self, f"_inline_{tag_of(node)}", None)
        if handler is None:
            return ""
        rendered = str(handler(node, inherited))
        # Only a node OOXML actually has an element for keeps its identity.
        # Bookmarking a wrapper would hand its id to the run it flattened
        # into, and a re-import would report a paragraph that changed type.
        if tag_of(node) in _FLATTENED:
            return rendered
        return self.bookmark(node, rendered)

    def _wrapped(self, node: Any, inherited: RunProps | None, **overrides: Any) -> str:
        """Render a wrapper inline by pushing its meaning onto its children.

        Word has no ``<em>``: emphasis is italic on every run inside. So a
        wrapper contributes properties and its children carry them.

        Args:
            node: The wrapper node.
            inherited: Formatting from further out.
            **overrides: The properties this wrapper contributes.

        Returns:
            The rendered children.
        """
        base = inherited or RunProps()
        merged = _merge(base, RunProps(**overrides))
        merged = _merge(merged, getattr(node, "props", None))
        return "".join(self._child(child, merged) for child in node.content)

    def _child(self, node: Inline, inherited: RunProps) -> str:
        """Render one child of a wrapper, carrying the wrapper's formatting."""
        return self.inline(node, inherited)

    def _inline_text(self, node: Text, inherited: RunProps | None = None) -> str:
        return _run(node.content, _merge(inherited, node.props), self.context)

    def _inline_emphasis(self, node: Emphasis, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited, italic=True)

    def _inline_strong(self, node: Strong, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited, font_weight=700)

    def _inline_underline(self, node: Underline, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited, underline=UnderlineStyle.SINGLE)

    def _inline_strike(self, node: Strike, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited, strikethrough=StrikeStyle.SINGLE)

    def _inline_small_caps(self, node: SmallCaps, inherited: RunProps | None = None) -> str:
        from caissa.core.model import SmallCapsMode

        return self._wrapped(node, inherited, small_caps=SmallCapsMode.SYNTHETIC)

    def _inline_superscript(self, node: Superscript, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited, vertical_align=VerticalAlign.SUPERSCRIPT)

    def _inline_subscript(self, node: Subscript, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited, vertical_align=VerticalAlign.SUBSCRIPT)

    def _inline_span(self, node: Any, inherited: RunProps | None = None) -> str:
        return self._wrapped(node, inherited)

    def _inline_link(self, node: Link, inherited: RunProps | None = None) -> str:
        relationship = f"rIdLnk{len(self.relationships) + 1}"
        self.relationships.append((relationship, f"{R}/hyperlink", node.target))
        body = "".join(
            self._child(child, _merge(inherited, RunProps(style="Hyperlink")))
            for child in node.content
        )
        return f'<w:hyperlink r:id="{relationship}">{body}</w:hyperlink>'

    def _inline_move(self, node: Move, inherited: RunProps | None = None) -> str:
        return _run(
            render_move(node, self.document), _merge(inherited, node.props), self.context
        )

    def _inline_piece_glyph(self, node: PieceGlyph, inherited: RunProps | None = None) -> str:
        from caissa.export.text import figurine_char

        glyph = figurine_char(node.piece.value, node.figurine_set)
        props = _merge(inherited, node.props)
        if node.font_family:
            props = _merge(props, RunProps(font_family=node.font_family))
        return _run(glyph, props, self.context)

    def _inline_nag_symbol(self, node: NagSymbol, inherited: RunProps | None = None) -> str:
        return _run(
            nag_symbol(node.nag),
            _merge(inherited, getattr(node, "props", None)),
            self.context,
        )

    def _inline_note_ref(self, node: NoteRef, inherited: RunProps | None = None) -> str:
        """A note reference as a real ``w:footnoteReference``."""
        index = next(
            (
                position
                for position, note in enumerate(self.footnotes, start=1)
                if note.ref == node.ref
            ),
            None,
        )
        if index is None:
            return _run(
                node.marker or node.ref,
                _merge(inherited, RunProps(vertical_align=VerticalAlign.SUPERSCRIPT)),
                self.context,
            )
        return (
            '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
            f'<w:footnoteReference w:id="{index}"/></w:r>'
        )

    def _inline_inline_diagram(
        self, node: InlineDiagram, inherited: RunProps | None = None
    ) -> str:
        rendered = self.diagrams.svg(node)
        return self._picture(rendered.svg, rendered.width_mm, rendered.height_mm, node)

    def _inline_math_inline(self, node: MathInline, inherited: RunProps | None = None) -> str:
        self.context.audit_feature("math", node=node, original="LaTeX")
        return _run(
            node.latex, _merge(inherited, RunProps(font_family="Cambria Math")), self.context
        )

    def _inline_image_inline(self, node: ImageInline, inherited: RunProps | None = None) -> str:
        return self._raster_picture(node)

    def _inline_anchor(self, node: Any, inherited: RunProps | None = None) -> str:
        self._bookmark_id += 1
        return (
            f'<w:bookmarkStart w:id="{self._bookmark_id}" w:name="{xml_attr(node.name)}"/>'
            f'<w:bookmarkEnd w:id="{self._bookmark_id}"/>'
        )

    def _inline_index_entry(self, node: Any, inherited: RunProps | None = None) -> str:
        """An index entry as an ``XE`` field, which is what Word's index reads."""
        entry = ":".join(node.terms)
        return (
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> XE "{xml_escape(entry)}" '
            "</w:instrText></w:r>"
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        )

    def _inline_line_break(self, node: LineBreak, inherited: RunProps | None = None) -> str:
        return "<w:r><w:br/></w:r>"

    def _inline_non_breaking_space(
        self, node: NonBreakingSpace, inherited: RunProps | None = None
    ) -> str:
        return _run(" ", _merge(inherited, getattr(node, "props", None)), self.context)

    def _inline_space(self, node: Space, inherited: RunProps | None = None) -> str:
        return _run(" ", _merge(inherited, RunProps()), self.context)

    def _inline_tab(self, node: Any, inherited: RunProps | None = None) -> str:
        return "<w:r><w:tab/></w:r>"

    def _inline_raw_inline(self, node: RawInline, inherited: RunProps | None = None) -> str:
        if node.format.lower() in ("ooxml", "docx", "wordprocessingml"):
            return node.text
        self.context.audit_feature("raw_passthrough", node=node, original=node.format)
        return ""

    # -- notes -------------------------------------------------------------

    def footnotes_xml(self) -> str:
        """Render ``word/footnotes.xml``.

        Returns:
            The part, including the two separators Word requires.
        """
        parts = [
            '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr>'
            '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            "<w:r><w:separator/></w:r></w:p></w:footnote>",
            '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr>'
            '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            "<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>",
        ]
        for index, note in enumerate(self.footnotes, start=1):
            body = self.blocks(note.content) or "<w:p/>"
            body = _force_style(body, "FootnoteText")
            # The note's own identity travels with the note, not with the
            # marker in the story: ``CT_FtnEdn`` is block-level content and
            # takes a bookmark like any other.
            parts.append(
                f'<w:footnote w:id="{index}">{self.marker(note)}{body}</w:footnote>'
            )
        return _wrap_part("w:footnotes", "".join(parts))

    def endnotes_xml(self) -> str:
        """Render ``word/endnotes.xml``.

        Returns:
            The part, including the two separators Word requires.
        """
        parts = [
            '<w:endnote w:type="separator" w:id="-1"><w:p>'
            "<w:r><w:separator/></w:r></w:p></w:endnote>",
            '<w:endnote w:type="continuationSeparator" w:id="0"><w:p>'
            "<w:r><w:continuationSeparator/></w:r></w:p></w:endnote>",
        ]
        for index, note in enumerate(self.endnotes, start=1):
            body = self.blocks(note.content) or "<w:p/>"
            parts.append(
                f'<w:endnote w:id="{index}">{self.marker(note)}{body}</w:endnote>'
            )
        return _wrap_part("w:endnotes", "".join(parts))


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


def _merge(base: RunProps | None, extra: RunProps | None) -> RunProps:
    """Overlay one property record on another.

    Args:
        base: The inherited record, or ``None``.
        extra: The nearer record, whose set fields win.

    Returns:
        The merged record.
    """
    if base is None:
        return extra or RunProps()
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


def _frame_properties(lines: int) -> str:
    """Render the ``w:framePr`` that makes Word draw a drop cap.

    ``CT_FramePr`` carries ``w:dropCap`` and ``w:lines``, so the number of
    lines the initial spans survives exactly rather than as an appearance.

    Args:
        lines: How many lines the initial drops through.

    Returns:
        The element.
    """
    return (
        '<w:framePr w:dropCap="drop" '
        f'w:lines="{max(1, min(10, int(lines)))}" '
        'w:wrap="around" w:vAnchor="text" w:hAnchor="text"/>'
    )


def _force_paragraph_style(props: ParagraphProps | None, style: str) -> ParagraphProps:
    """Return the paragraph properties with a style name, overriding any other.

    Args:
        props: The properties, or ``None``.
        style: The style the block's role demands.

    Returns:
        The properties, naming ``style``.
    """
    from dataclasses import replace

    return replace(props or ParagraphProps(), style=style)


def _with_style(props: ParagraphProps | None, style: str) -> ParagraphProps:
    """Return the paragraph properties with a style name attached.

    Args:
        props: The properties, or ``None``.
        style: The style to name when the properties do not name one.

    Returns:
        The properties.
    """
    from dataclasses import replace

    base = props or ParagraphProps()
    return base if base.style else replace(base, style=style)


def _run(text: str, props: RunProps | None, context: ExportContext) -> str:
    """Render one ``w:r``.

    Args:
        text: The literal text.
        props: The run properties.
        context: The export context.

    Returns:
        The run, or an empty string when the text is empty.
    """
    if not text:
        return ""
    body = "".join(
        f'<w:t xml:space="preserve">{xml_escape(part)}</w:t>' if index == 0 else
        f'<w:br/><w:t xml:space="preserve">{xml_escape(part)}</w:t>'
        for index, part in enumerate(text.split("\n"))
    )
    return f"<w:r>{run_props_to_rpr(props or RunProps(), context)}{body}</w:r>"


def _insert_ppr(paragraph: str, extra: str, style: str) -> str:
    """Insert extra ``w:pPr`` children into a rendered paragraph.

    Args:
        paragraph: The rendered ``w:p``.
        extra: The children to insert.
        style: Style to apply when the paragraph names none.

    Returns:
        The paragraph.
    """
    if "<w:numPr>" in paragraph and "<w:numPr>" in extra:
        # The paragraph already names a numbering of its own; a second
        # ``w:numPr`` is a schema violation and Word refuses the file.
        extra = ""
    if paragraph.startswith("<w:p><w:pPr>"):
        head = "<w:p><w:pPr>"
        if '<w:pStyle' not in paragraph:
            extra = f'<w:pStyle w:val="{style}"/>' + extra
        return head + extra + paragraph[len(head) :]
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra}</w:pPr>' + paragraph[len("<w:p>") :]
    )


def _force_style(rendered: str, style: str) -> str:
    """Apply a style to every paragraph of a rendered fragment that has none.

    Args:
        rendered: The OOXML fragment.
        style: The style name.

    Returns:
        The fragment.
    """
    if "<w:pStyle" in rendered:
        return rendered
    reference = f'<w:pStyle w:val="{style}"/>'
    rendered = rendered.replace("<w:p><w:pPr>", f"<w:p><w:pPr>{reference}")
    return re.sub(r"<w:p>(?!<w:pPr)", f"<w:p><w:pPr>{reference}</w:pPr>", rendered)


def _mm(measure: Measure | None) -> float | None:
    """A length in millimetres, or ``None`` when unset or relative."""
    if measure is None or not measure.is_absolute:
        return None
    return measure.to_points() * 25.4 / 72.0


_PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
_PNG_IHDR_END = 24  # signature (8) + IHDR length and type (8) + width and height (8)
_GIF_HEADER_END = 10  # "GIF89a" (6) + logical screen width and height (4)


def _raster_pixels(data: bytes, suffix: str) -> tuple[int, int] | None:
    """Width and height in pixels read from the file header, for PNG and GIF.

    JPEG needs a marker walk; Pillow answers it when present, and the
    resource's own ``width``/``height`` answer otherwise.
    """
    if suffix == "png" and data[:8] == _PNG_SIGNATURE and len(data) >= _PNG_IHDR_END:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if suffix == "gif" and data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= _GIF_HEADER_END:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            return int(image.width), int(image.height)
    except Exception:  # noqa: BLE001 - no Pillow, or not an image it knows
        return None


_PLACEHOLDER_SIDE = 64


def _placeholder_png(side: int = _PLACEHOLDER_SIDE, grey: int = 0xD9) -> bytes:
    """A flat grey square, written with the standard library alone.

    It stands where an image whose file the package could not find would be,
    so the document keeps the node's place, size and name; the report is what
    says the picture is not the author's.
    """
    import struct
    import zlib

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    row = b"\x00" + bytes([grey]) * (side * 3)
    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * side, 9))
        + chunk(b"IEND", b"")
    )


def _to_png(path: Path) -> bytes:
    """Re-encode an image Word does not take as it is (WebP, BMP, TIFF) as PNG."""
    import io

    from PIL import Image

    with Image.open(path) as image:
        buffer = io.BytesIO()
        mode = "RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB"
        image.convert(mode).save(buffer, format="PNG")
        return buffer.getvalue()


DIAGRAM_EXT_URI = "{7A1C5B3E-2D4F-4C8A-9E6B-CAISSA0D1A6}"
"""The ``a:ext/@uri`` of the diagram extension. A GUID-shaped token, as the
schema asks; the letters spell who put it there."""

DIAGRAM_NS = "urn:caissa:ir:diagram"


def _diagram_extension(node: Diagram) -> str:
    """The diagram node's own fields, as an ``a:ext`` for ``wp:docPr``.

    What the XHTML writer puts in ``data-*`` attributes goes here in the one
    place DrawingML reserves for a producer's extras: FEN, orientation,
    number, label, stipulation, marks, the side-to-move flag, the anchor, the
    alternative text and the move context. Three flags say which neighbours
    the writer laid down around the picture -- the stipulation paragraph
    before it, the caption after it, the solution's movetext after that --
    so the reader can fold them back into the node instead of reading them
    as paragraphs of their own.
    """
    from caissa.export.html import _marks_data

    attributes: dict[str, str | None] = {
        "fen": node.fen,
        "orientation": node.orientation.value,
        "number": str(node.number) if node.number is not None else None,
        "label": node.label,
        "stipulation": node.stipulation,
        "marks": _marks_data(node.marks) or None,
        "side-to-move": "1" if node.side_to_move_indicator else None,
        "anchor": node.anchor,
        "alt": node.alt_text,
        "move-context": node.move_context,
        "verified": "1" if node.verified_by_human else None,
        "caption": "1" if (node.caption or node.number is not None) else None,
        "solution": "1" if node.solution is not None and node.solution.children else None,
    }
    rendered = "".join(
        f' {name}="{xml_attr(value)}"' for name, value in attributes.items() if value is not None
    )
    return (
        f'<a:ext uri="{DIAGRAM_EXT_URI}">'
        f'<caissa:diagram xmlns:caissa="{DIAGRAM_NS}"{rendered}/>'
        "</a:ext>"
    )


_CROP_UNIT = 100_000  # ``a:srcRect`` insets are in thousandths of a percent
_CROP_EDGES = 4


def _src_rect(crop: tuple[float, ...]) -> str:
    """Render the IR's fractional crop as ``a:srcRect``, or nothing for no crop.

    The IR keeps ``(left, top, right, bottom)`` as fractions of the source
    that stay visible; DrawingML keeps the four *insets*, so the right and
    bottom edges are complemented.
    """
    if len(crop) != _CROP_EDGES:
        return ""
    left, top, right, bottom = crop
    insets = (left, top, 1.0 - right, 1.0 - bottom)
    if all(abs(value) < 1e-9 for value in insets):
        return ""
    edges = [round(max(0.0, min(1.0, value)) * _CROP_UNIT) for value in insets]
    return f'<a:srcRect l="{edges[0]}" t="{edges[1]}" r="{edges[2]}" b="{edges[3]}"/>'


def _drawing(
    relationship: str,
    identifier: int,
    width: int,
    height: int,
    alt: str,
    *,
    name: str | None = None,
    title: str | None = None,
    crop: tuple[float, ...] = (),
    extension: str = "",
) -> str:
    """Render an inline ``w:drawing`` for one embedded picture.

    Args:
        relationship: The relationship id of the image part.
        identifier: A document-unique drawing id.
        width: Width in EMU.
        height: Height in EMU.
        alt: Accessible description.
        name: The picture's name -- the resource key of an image, so it comes
            back; ``Diagrama N`` for a diagram.
        title: The picture's title, when the node has one.
        crop: The IR's fractional crop, written as ``a:srcRect``.
        extension: Children for an ``a:extLst`` inside ``wp:docPr`` -- the
            OOXML extension mechanism, which Word keeps and ignores.

    Returns:
        The run containing the drawing.
    """
    safe = xml_attr(alt)[:400]
    label = xml_attr(name if name is not None else f"Diagrama {identifier}")
    titled = f' title="{xml_attr(title)}"' if title else ""
    properties = (
        f'<wp:docPr id="{identifier}" name="{label}" descr="{safe}"{titled}>'
        f"<a:extLst>{extension}</a:extLst></wp:docPr>"
        if extension
        else f'<wp:docPr id="{identifier}" name="{label}" descr="{safe}"{titled}/>'
    )
    return (
        "<w:r><w:drawing>"
        f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{width}" cy="{height}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f"{properties}"
        "<wp:cNvGraphicFramePr/>"
        f'<a:graphic xmlns:a="{A}">'
        f'<a:graphicData uri="{PIC}">'
        f'<pic:pic xmlns:pic="{PIC}">'
        f'<pic:nvPicPr><pic:cNvPr id="{identifier}" name="{label}" '
        f'descr="{safe}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{relationship}"/>{_src_rect(crop)}'
        "<a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
        "<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/>"
        f'<a:ext cx="{width}" cy="{height}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline>"
        "</w:drawing></w:r>"
    )


# --------------------------------------------------------------------------- #
# The package parts
# --------------------------------------------------------------------------- #
_NAMESPACES = (
    f'xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'mc:Ignorable="w14"'
)


def _wrap_part(root: str, body: str) -> str:
    """Wrap part content in its XML declaration and root element.

    Args:
        root: The root element name.
        body: The content.

    Returns:
        The complete part.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<{root} {_NAMESPACES}>{body}</{root}>"
    )


def _document_xml(body: str, document: Document, context: ExportContext) -> str:
    """Render ``word/document.xml``.

    Args:
        body: The rendered body content.
        document: The IR.
        context: The export context.

    Returns:
        The part.
    """
    return _wrap_part("w:document", f"<w:body>{body}</w:body>")


def _section_properties(options: ExportOptions) -> str:
    """Render the final ``w:sectPr``: page size, margins and columns.

    Args:
        options: The export options.

    Returns:
        The element.
    """
    width = round(getattr(options, "page_width_mm", 148.0) * 56.6929)
    height = round(getattr(options, "page_height_mm", 210.0) * 56.6929)
    margin = round(getattr(options, "margin_mm", 18.0) * 56.6929)
    return (
        "<w:sectPr>"
        f'<w:pgSz w:w="{width}" w:h="{height}"/>'
        f'<w:pgMar w:top="{margin}" w:right="{margin}" w:bottom="{margin}" '
        f'w:left="{margin}" w:header="708" w:footer="708" w:gutter="0"/>'
        '<w:cols w:space="708"/>'
        '<w:docGrid w:linePitch="360"/>'
        "</w:sectPr>"
    )


_BUILTIN_STYLES: tuple[tuple[str, str, str, str], ...] = (
    ("Normal", "Normal", "", ""),
    ("Heading1", "Titulo 1", "Normal", '<w:outlineLvl w:val="0"/>'),
    ("Heading2", "Titulo 2", "Normal", '<w:outlineLvl w:val="1"/>'),
    ("Heading3", "Titulo 3", "Normal", '<w:outlineLvl w:val="2"/>'),
    ("Heading4", "Titulo 4", "Normal", '<w:outlineLvl w:val="3"/>'),
    ("Heading5", "Titulo 5", "Normal", '<w:outlineLvl w:val="4"/>'),
    ("Heading6", "Titulo 6", "Normal", '<w:outlineLvl w:val="5"/>'),
    ("Caption", "Legenda", "Normal", '<w:jc w:val="center"/>'),
    ("Quote", "Citacao", "Normal", '<w:ind w:left="567" w:right="567"/>'),
    ("QuoteAttribution", "Atribuicao", "Quote", '<w:jc w:val="right"/>'),
    ("Callout", "Destaque", "Normal", '<w:ind w:left="284"/>'),
    ("Code", "Codigo", "Normal", ""),
    ("Diagram", "Diagrama", "Normal", '<w:jc w:val="center"/><w:keepNext/>'),
    ("GameScore", "Partida", "Normal", ""),
    ("GroupTitle", "Titulo de grupo", "Normal", '<w:keepNext/>'),
    ("ListParagraph", "Paragrafo de lista", "Normal", '<w:contextualSpacing/>'),
    ("FootnoteText", "Texto de nota", "Normal", ""),
    ("TOCHeading", "Titulo do sumario", "Heading1", ""),
    ("TOC1", "Sumario 1", "Normal", ""),
)


def _styles_xml(document: Document, context: ExportContext) -> str:
    """Render ``word/styles.xml`` from the IR's own stylesheet.

    A style is what makes a Word document editable: change ``Diagrama`` once
    and every diagram caption follows. Writing direct formatting instead would
    produce a file that *looks* right and cannot be maintained, which is why
    SPEC section 8.2 names this explicitly.

    Args:
        document: The IR, for its stylesheet.
        context: The export context, for the default font.

    Returns:
        The part.
    """
    options = context.options
    family = xml_attr(getattr(options, "default_font", "Cambria"))
    size = round(getattr(options, "default_size_pt", 11.0) * 2)
    parts = [
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        f'<w:rFonts w:ascii="{family}" w:hAnsi="{family}" w:cs="{family}"/>'
        f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        f'<w:lang w:val="{xml_attr(document.metadata.language or "pt-BR")}"/>'
        "</w:rPr></w:rPrDefault>"
        '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
    ]
    seen: set[str] = set()
    for name, display, based_on, extra in _BUILTIN_STYLES:
        seen.add(name)
        parts.append(_style_element(name, display, based_on, extra, "", default=name == "Normal"))
    parts.append(
        _style_element(
            "FootnoteReference",
            "Referencia de nota",
            "",
            "",
            '<w:vertAlign w:val="superscript"/>',
            kind="character",
        )
    )
    parts.append(
        _style_element(
            "Hyperlink",
            "Hiperlink",
            "",
            "",
            '<w:color w:val="0563C1"/><w:u w:val="single"/>',
            kind="character",
        )
    )
    seen.update({"FootnoteReference", "Hyperlink"})
    parts.append(
        '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>'
        "<w:tblPr><w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        "</w:tblBorders></w:tblPr></w:style>"
    )

    for style in document.styles.paragraph_styles:
        if style.name in seen:
            continue
        seen.add(style.name)
        parts.append(
            _style_element(
                style.name,
                style.display_name or style.name,
                style.based_on or "Normal",
                "".join(_paragraph_body(style.paragraph)),
                run_props_to_rpr(style.run, context).removeprefix("<w:rPr>").removesuffix(
                    "</w:rPr>"
                ),
            )
        )
    for style in document.styles.character_styles:
        if style.name in seen:
            continue
        seen.add(style.name)
        parts.append(
            _style_element(
                style.name,
                style.display_name or style.name,
                style.based_on or "",
                "",
                run_props_to_rpr(style.props, context)
                .removeprefix("<w:rPr>")
                .removesuffix("</w:rPr>"),
                kind="character",
            )
        )
    context.count("styles", len(seen))
    return _wrap_part("w:styles", "".join(parts))


def _style_element(
    name: str,
    display: str,
    based_on: str,
    paragraph: str,
    run: str,
    *,
    kind: str = "paragraph",
    default: bool = False,
) -> str:
    """Render one ``w:style``.

    Args:
        name: The style id.
        display: The human-readable name.
        based_on: The parent style id, or an empty string.
        paragraph: Rendered ``w:pPr`` children.
        run: Rendered ``w:rPr`` children.
        kind: ``"paragraph"`` or ``"character"``.
        default: Whether this is the document default.

    Returns:
        The element.
    """
    attributes = f'w:type="{kind}" w:styleId="{xml_attr(name)}"'
    if default:
        attributes += ' w:default="1"'
    parts = [f'<w:name w:val="{xml_attr(display)}"/>']
    if based_on:
        parts.append(f'<w:basedOn w:val="{xml_attr(based_on)}"/>')
    parts.append("<w:qFormat/>")
    if paragraph:
        parts.append(f"<w:pPr>{paragraph}</w:pPr>")
    if run:
        parts.append(f"<w:rPr>{run}</w:rPr>")
    return f"<w:style {attributes}>{''.join(parts)}</w:style>"


def _numbering_levels(fmt: str, text: str) -> str:
    """Render the nine ``w:lvl`` elements one abstract numbering needs.

    Args:
        fmt: ``w:numFmt`` value, ``"decimal"`` or ``"bullet"``.
        text: ``w:lvlText`` template, with ``%1`` standing for the counter.

    Returns:
        The levels.
    """
    return "".join(
        f'<w:lvl w:ilvl="{level}"><w:start w:val="1"/>'
        f'<w:numFmt w:val="{fmt}"/>'
        f'<w:lvlText w:val="{text.replace("%1", "%" + str(level + 1))}"/>'
        '<w:lvlJc w:val="left"/>'
        f'<w:pPr><w:ind w:left="{720 * (level + 1)}" w:hanging="360"/></w:pPr></w:lvl>'
        for level in range(9)
    )


def _numbering_xml(numbering: _Numbering | None = None) -> str:
    """Render ``word/numbering.xml``.

    Args:
        numbering: The registry of ``NumberingRef`` definitions the document
            used; only the two list numberings are written when omitted.

    Returns:
        The part.
    """
    body = (
        f'<w:abstractNum w:abstractNumId="{LIST_ORDERED_NUM_ID}">'
        '<w:multiLevelType w:val="hybridMultilevel"/>'
        + _numbering_levels("decimal", "%1.")
        + "</w:abstractNum>"
        f'<w:abstractNum w:abstractNumId="{LIST_BULLET_NUM_ID}">'
        '<w:multiLevelType w:val="hybridMultilevel"/>'
        + _numbering_levels("bullet", "•")
        + "</w:abstractNum>"
        + (numbering.xml() if numbering is not None else "")
    )
    body += (
        f'<w:num w:numId="{LIST_ORDERED_NUM_ID}">'
        f'<w:abstractNumId w:val="{LIST_ORDERED_NUM_ID}"/></w:num>'
        f'<w:num w:numId="{LIST_BULLET_NUM_ID}">'
        f'<w:abstractNumId w:val="{LIST_BULLET_NUM_ID}"/></w:num>'
    )
    return _wrap_part("w:numbering", body)


def _settings_xml(context: ExportContext) -> str:
    """Render ``word/settings.xml``.

    ``w:updateFields`` is what makes the TOC and every SEQ field fill in when
    the reader opens the file: without it Word shows the placeholder text and
    the user has to know about F9.

    Args:
        context: The export context.

    Returns:
        The part.
    """
    version = getattr(context.options, "compatibility", 15)
    # ``w:docVars`` is OOXML's own place for application data about the
    # document as a whole (ECMA-376 17.15.1.85), and Word keeps it across an
    # edit. The document node has no element of its own -- ``w:body`` *is* the
    # document -- so this is where its identity lives.
    identity = ""
    if getattr(context.options, "track_identity", True):
        identity = (
            f'<w:docVars><w:docVar w:name="{DOCUMENT_ID_VAR}" '
            f'w:val="{xml_attr(str(context.document.id))}"/></w:docVars>'
        )
    return _wrap_part(
        "w:settings",
        '<w:zoom w:percent="100"/>'
        '<w:updateFields w:val="true"/>'
        "<w:footnotePr><w:footnote w:id=\"-1\"/><w:footnote w:id=\"0\"/></w:footnotePr>"
        "<w:endnotePr><w:endnote w:id=\"-1\"/><w:endnote w:id=\"0\"/></w:endnotePr>"
        "<w:compat><w:compatSetting w:name=\"compatibilityMode\" "
        f'w:uri="http://schemas.microsoft.com/office/word" w:val="{version}"/></w:compat>'
        + identity,
    )


def _font_table_xml(families: Iterable[str]) -> str:
    """Render ``word/fontTable.xml``.

    Args:
        families: Family names the document uses.

    Returns:
        The part.
    """
    names = sorted({"Cambria", "Consolas", "Cambria Math", *families})
    body = "".join(
        f'<w:font w:name="{xml_attr(name)}"><w:pitch w:val="variable"/></w:font>'
        for name in names
    )
    return _wrap_part("w:fonts", body)


def _content_types(media: Sequence[tuple[str, bytes, str]]) -> str:
    """Render ``[Content_Types].xml``.

    Args:
        media: The image parts, for their default extensions.

    Returns:
        The part.
    """
    extensions = {"rels": "application/vnd.openxmlformats-package.relationships+xml",
                  "xml": "application/xml"}
    for _, _, suffix in media:
        extensions[suffix] = {
            "emf": "image/x-emf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "gif": "image/gif",
        }.get(suffix, "application/octet-stream")
    defaults = "".join(
        f'<Default Extension="{name}" ContentType="{value}"/>'
        for name, value in sorted(extensions.items())
    )
    base = "application/vnd.openxmlformats-officedocument.wordprocessingml"
    overrides = "".join(
        f'<Override PartName="{part}" ContentType="{kind}"/>'
        for part, kind in (
            ("/word/document.xml", f"{base}.document.main+xml"),
            ("/word/styles.xml", f"{base}.styles+xml"),
            ("/word/numbering.xml", f"{base}.numbering+xml"),
            ("/word/settings.xml", f"{base}.settings+xml"),
            ("/word/fontTable.xml", f"{base}.fontTable+xml"),
            ("/word/footnotes.xml", f"{base}.footnotes+xml"),
            ("/word/endnotes.xml", f"{base}.endnotes+xml"),
            (
                "/docProps/core.xml",
                "application/vnd.openxmlformats-package.core-properties+xml",
            ),
            (
                "/docProps/app.xml",
                "application/vnd.openxmlformats-officedocument.extended-properties+xml",
            ),
        )
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        f"{defaults}{overrides}</Types>"
    )


def _root_rels() -> str:
    """Render ``_rels/.rels``.

    Returns:
        The part.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/'
        'core-properties" Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="{R}/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _document_rels(extra: Sequence[tuple[str, str, str]]) -> str:
    """Render ``word/_rels/document.xml.rels``.

    Args:
        extra: ``(id, type, target)`` triples for images and hyperlinks.

    Returns:
        The part.
    """
    fixed = [
        ("rIdStyles", f"{R}/styles", "styles.xml", ""),
        ("rIdNumbering", f"{R}/numbering", "numbering.xml", ""),
        ("rIdSettings", f"{R}/settings", "settings.xml", ""),
        ("rIdFonts", f"{R}/fontTable", "fontTable.xml", ""),
        ("rIdFootnotes", f"{R}/footnotes", "footnotes.xml", ""),
        ("rIdEndnotes", f"{R}/endnotes", "endnotes.xml", ""),
    ]
    parts = [
        f'<Relationship Id="{identifier}" Type="{kind}" Target="{target}"{mode}/>'
        for identifier, kind, target, mode in fixed
    ]
    for identifier, kind, target in extra:
        mode = ' TargetMode="External"' if kind.endswith("/hyperlink") else ""
        parts.append(
            f'<Relationship Id="{identifier}" Type="{kind}" '
            f'Target="{xml_attr(target)}"{mode}/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(parts)}</Relationships>"
    )


def _core_xml(document: Document) -> str:
    """Render ``docProps/core.xml``: the properties a librarian reads.

    Args:
        document: The IR.

    Returns:
        The part.
    """
    metadata = document.metadata
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    authors = ", ".join(person.name for person in metadata.contributors) or ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{xml_escape(metadata.title or '')}</dc:title>"
        f"<dc:creator>{xml_escape(authors)}</dc:creator>"
        f"<cp:lastModifiedBy>{xml_escape(authors)}</cp:lastModifiedBy>"
        f"<dc:subject>{xml_escape(metadata.subtitle or '')}</dc:subject>"
        f"<dc:description>{xml_escape(metadata.description or '')}</dc:description>"
        f"<cp:keywords>{xml_escape(', '.join(metadata.subjects))}</cp:keywords>"
        f"<dc:language>{xml_escape(metadata.language or 'pt-BR')}</dc:language>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_xml(document: Document, context: ExportContext) -> str:
    """Render ``docProps/app.xml``.

    Args:
        document: The IR.
        context: The export context, for the node count.

    Returns:
        The part.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<Properties "
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Caissa Studio</Application>"
        f"<Company>{xml_escape(document.metadata.publisher or '')}</Company>"
        "<AppVersion>1.0000</AppVersion>"
        "</Properties>"
    )


# --------------------------------------------------------------------------- #
# Reading back
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class _FlowMarker:
    """Where a node stood in the story, recovered from an empty bookmark.

    A footnote's body lives outside ``w:body`` and the document node has no
    element of its own; both are written as an empty bookmark, and this is what
    the reader gets back before it puts the node in its place. It never leaves
    :func:`read_docx`.

    Attributes:
        identity: The ULID the bookmark carried.
    """

    identity: str


@dataclass
class _ReadState:
    """What the reader carries from part to part.

    Attributes:
        numbering: ``w:numId`` to the name of the numbering definition it
            points at, taken from ``word/numbering.xml``.
        starts: ``w:numId`` to the ``w:startOverride`` that id carries, when it
            carries one.
    """

    numbering: Mapping[int, str]
    starts: Mapping[int, int]
    targets: Mapping[str, str] = field(default_factory=dict)
    """``r:id`` to the part it points at, from ``word/_rels/document.xml.rels``:
    what tells a picture of a diagram (``media/diagramaN.emf``) from an image."""


def read_docx(path: Path | str) -> Document:
    """Read a ``.docx`` written by :class:`DocxExporter` back into the IR.

    This parses ``word/document.xml`` -- the part Word itself reads -- and not
    any sidecar, so a fidelity number obtained through it measures this writer.
    The tree that comes back is flat where the original was nested, because
    OOXML *is* flat: a quotation is a run of paragraphs in the ``Quote`` style,
    not a container. Those structural differences show up in the fidelity
    report as missing container nodes, which is the truth about what Word can
    hold.

    Args:
        path: The ``.docx`` file.

    Returns:
        The reconstructed document.

    Raises:
        ValueError: The file is not a readable package.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())

            def part(name: str) -> str:
                return archive.read(name).decode("utf-8") if name in names else ""

            main = archive.read("word/document.xml").decode("utf-8")
            core = part("docProps/core.xml")
            settings_part = part("word/settings.xml")
            numbering_part = part("word/numbering.xml")
            footnotes_part = part("word/footnotes.xml")
            endnotes_part = part("word/endnotes.xml")
            rels_part = part("word/_rels/document.xml.rels")
    except (KeyError, zipfile.BadZipFile) as error:
        raise ValueError(f"Nao e um DOCX legivel: {error}") from error

    numbering_names, numbering_starts = _read_numbering(numbering_part)
    state = _ReadState(
        numbering=numbering_names, starts=numbering_starts, targets=_read_targets(rels_part)
    )
    root = ET.fromstring(main)
    body = root.find(f"{{{W}}}body")
    read: list[Any] = []
    identity: dict[int, str] = {}
    if body is not None:
        _collect(body, read, identity, state)
    own = _read_document_id(settings_part)
    notes = _read_notes(footnotes_part, "footnote", state)
    notes.extend(_read_notes(endnotes_part, "endnote", state))
    document = Document(
        metadata=_metadata_from_core(core), body=tuple(_place_notes(read, notes))
    )
    return _apply_identity(document, [own] if own else [])


def _read_document_id(part: str) -> str:
    """Read the document node's identity out of ``word/settings.xml``.

    Args:
        part: The settings part, possibly empty.

    Returns:
        The ULID as written, or an empty string when the file was written by
        something else or with identity tracking off.
    """
    if not part:
        return ""
    try:
        root = ET.fromstring(part)
    except ET.ParseError:
        return ""
    for variable in root.iter(f"{{{W}}}docVar"):
        if variable.get(f"{{{W}}}name") == DOCUMENT_ID_VAR:
            return variable.get(f"{{{W}}}val") or ""
    return ""


def _read_targets(part: str) -> Mapping[str, str]:
    """Read ``r:id`` to target out of the main part's relationships."""
    if not part:
        return {}
    namespace = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    try:
        root = ET.fromstring(part)
    except ET.ParseError:
        return {}
    return {
        element.get("Id") or "": element.get("Target") or ""
        for element in root.iter(f"{namespace}Relationship")
    }


def _read_numbering(part: str) -> tuple[Mapping[int, str], Mapping[int, int]]:
    """Map every ``w:numId`` to the name of the definition it points at.

    ``w:numId`` is a number and a ``NumberingRef`` is a name; ECMA-376 gives
    ``w:abstractNum`` a ``w:name`` child precisely so that the name has
    somewhere to live, and this is the walk back along that link.

    Args:
        part: ``word/numbering.xml``, possibly empty.

    Returns:
        The numbering id to definition name mapping, and the numbering id to
        ``w:startOverride`` mapping. The two ids the exporter reserves for list
        blocks are in neither: see :data:`_RESERVED_NUM_IDS`.
    """
    if not part:
        return {}, {}
    try:
        root = ET.fromstring(part)
    except ET.ParseError:
        return {}, {}
    names: dict[int, str] = {}
    for abstract in root.findall(f"{{{W}}}abstractNum"):
        label = abstract.find(f"{{{W}}}name")
        raw = abstract.get(f"{{{W}}}abstractNumId")
        if label is not None and raw is not None and label.get(f"{{{W}}}val"):
            names[int(raw)] = label.get(f"{{{W}}}val") or ""
    mapping: dict[int, str] = {}
    starts: dict[int, int] = {}
    for num in root.findall(f"{{{W}}}num"):
        raw = num.get(f"{{{W}}}numId")
        reference = num.find(f"{{{W}}}abstractNumId")
        if raw is None or reference is None:
            continue
        identifier = int(raw)
        if identifier in _RESERVED_NUM_IDS:
            continue
        name = names.get(int(reference.get(f"{{{W}}}val") or -1))
        if name:
            mapping[identifier] = name
        override = num.find(f"{{{W}}}lvlOverride/{{{W}}}startOverride")
        if override is not None and override.get(f"{{{W}}}val") is not None:
            starts[identifier] = int(override.get(f"{{{W}}}val") or 1)
    return mapping, starts


def _read_notes(part: str, kind: str, state: _ReadState) -> list[Block]:
    """Rebuild the notes of ``word/footnotes.xml`` or ``word/endnotes.xml``.

    Args:
        part: The part text, possibly empty.
        kind: ``"footnote"`` or ``"endnote"``.
        state: The reader state.

    Returns:
        One :class:`~caissa.core.model.blocks.Footnote` or
        :class:`~caissa.core.model.blocks.Endnote` per real note, in file order.
    """
    if not part:
        return []
    try:
        root = ET.fromstring(part)
    except ET.ParseError:
        return []
    from caissa.core.model import Endnote as EndnoteNode
    from caissa.core.model import Footnote as FootnoteNode

    build = FootnoteNode if kind == "footnote" else EndnoteNode
    notes: list[Block] = []
    for element in root.findall(f"{{{W}}}{kind}"):
        if element.get(f"{{{W}}}type") or element.get(f"{{{W}}}id") in ("-1", "0"):
            continue
        read: list[Any] = []
        _collect(element, read, {}, state)
        own = ""
        if read and isinstance(read[0], _FlowMarker):
            own = read.pop(0).identity
        content = tuple(item for item in read if not isinstance(item, _FlowMarker))
        notes.append(_apply_identity(build(ref="", content=content), [own] if own else []))
    return notes


def _place_notes(read: Sequence[Any], notes: Sequence[Block]) -> list[Block]:
    """Put each rebuilt note back where its empty bookmark stood in the story.

    Args:
        read: What ``w:body`` gave back, note markers included.
        notes: The notes rebuilt from the note parts.

    Returns:
        The blocks, every marker replaced by the note that belongs to it.
    """
    by_id = {str(note.id): note for note in notes}
    placed: list[Block] = []
    for item in read:
        if not isinstance(item, _FlowMarker):
            placed.append(item)
            continue
        note = by_id.pop(item.identity, None)
        if note is not None:
            placed.append(note)
    placed.extend(by_id.values())
    return placed


def _collect(
    container: ET.Element,
    blocks: list[Any],
    identity: dict[int, str],
    state: _ReadState,
) -> None:
    """Walk a block container and rebuild what it holds.

    Used for ``w:body``, for a table cell and for a note body, which are the
    three places OOXML puts block-level content.

    Args:
        container: The element to walk.
        blocks: Collector for the rebuilt blocks and flow markers.
        identity: Open bookmark ids to node identities.
        state: The reader state.
    """
    pending: list[str] = []
    ranges: dict[int, str] = {}
    for child in container:
        tag = child.tag.split("}")[-1]
        if tag == "bookmarkStart":
            name = child.get(f"{{{W}}}name") or ""
            if name.startswith(BOOKMARK_PREFIX):
                value = name[len(BOOKMARK_PREFIX) :]
                pending.append(value)
                key = int(child.get(f"{{{W}}}id") or 0)
                ranges[key] = value
                identity[key] = value
        elif tag == "bookmarkEnd":
            key = int(child.get(f"{{{W}}}id") or 0)
            value = ranges.pop(key, "")
            identity.pop(key, None)
            if value and value in pending:
                # Nothing stood between the start and the end: this bookmark
                # names a *place*, not a node.
                pending.remove(value)
                blocks.append(_FlowMarker(identity=value))
        elif tag == "p":
            if not pending and _is_packaging_paragraph(child):
                # OOXML wants a paragraph after a table and Word inserts one
                # anyway. It carries no bookmark, no text and no properties: it
                # is packaging, and reading it back as a node would add a block
                # the author never wrote.
                continue
            node = _read_paragraph(child, state)
            if node is not None:
                blocks.append(
                    _apply_identity(node, pending or _hoisted_identity(child))
                )
                pending = []
        elif tag == "tbl":
            blocks.append(_apply_identity(_read_table(child, state), pending))
            pending = []
    blocks[:] = _assemble_diagrams(blocks)


def _hoisted_identity(paragraph: ET.Element) -> list[str]:
    """Find a block bookmark Word moved inside the paragraph it wrapped.

    Word normalises a bookmark that opened before ``w:p`` by moving its
    ``w:bookmarkStart`` in after ``w:pPr`` and leaving its ``w:bookmarkEnd``
    outside. That is measured behaviour, not a guess: opening a file written
    here and saving it in Word 2016 does exactly this. The range that is still
    open when the paragraph ends is the one that wrapped the paragraph, which
    is how the block is told from the runs inside it.

    Args:
        paragraph: The ``w:p``.

    Returns:
        The identities of the bookmarks left open, outermost last, or an empty
        list when the paragraph carries none.
    """
    opened: dict[int, str] = {}
    closed: set[int] = set()
    for child in paragraph:
        tag = child.tag.split("}")[-1]
        if tag == "bookmarkStart":
            name = child.get(f"{{{W}}}name") or ""
            if name.startswith(BOOKMARK_PREFIX):
                opened[int(child.get(f"{{{W}}}id") or 0)] = name[len(BOOKMARK_PREFIX) :]
        elif tag == "bookmarkEnd":
            closed.add(int(child.get(f"{{{W}}}id") or 0))
    return [name for key, name in opened.items() if key not in closed]


def _is_packaging_paragraph(element: ET.Element) -> bool:
    """Whether a ``w:p`` is structure the format needed rather than content.

    Args:
        element: The paragraph element.

    Returns:
        ``True`` for a paragraph with no identity, no properties and nothing in
        it -- which is the empty paragraph a table has to be followed by.
    """
    return not list(element)


def _apply_identity(node: Any, pending: Sequence[str]) -> Any:
    """Restore a node's identity from the bookmark that wrapped it.

    A :class:`_DiagramDraft` hands the identity to the node it carries.

    Args:
        node: The rebuilt node.
        pending: Bookmark names opened just before it.

    Returns:
        The node, with its original id when one was found.
    """
    from dataclasses import replace

    if isinstance(node, _DiagramDraft):
        node.node = _apply_identity(node.node, pending)
        return node
    for raw in reversed(pending):
        try:
            return replace(node, id=ULID.from_string(raw))
        except (ValueError, TypeError):
            continue
    return node


def _read_paragraph(element: ET.Element, state: _ReadState) -> Block | None:
    """Rebuild one ``w:p``.

    Args:
        element: The paragraph element.
        state: The reader state.

    Returns:
        A :class:`~caissa.core.model.blocks.Paragraph`, a
        :class:`~caissa.core.model.blocks.Heading` or a
        :class:`~caissa.core.model.game.GameScore`, or ``None`` for a paragraph
        that carries only a section break.
    """
    properties = element.find(f"{{{W}}}pPr")
    style = ""
    if properties is not None:
        reference = properties.find(f"{{{W}}}pStyle")
        if reference is not None:
            style = reference.get(f"{{{W}}}val") or ""
        if properties.find(f"{{{W}}}sectPr") is not None and not list(element):
            return None
    if style == "GameScore":
        return _read_game(element)
    props = _read_paragraph_props(properties, style, state)
    # Only a Diagram-styled paragraph holds a block picture: a lone inline
    # image in a title or a caption keeps being the inline it was.
    drawing = _lone_drawing(element) if style == "Diagram" else None
    if drawing is not None:
        draft = _diagram_from_drawing(drawing)
        if draft is not None:
            return draft
        picture = _read_picture(drawing, state)
        if picture is not None:
            return _image_block(picture, props.alignment)
    content = _read_runs(element, state)
    match = re.fullmatch(r"Heading([1-9])", style)
    if match:
        from caissa.core.model import Heading as HeadingNode

        return HeadingNode(level=int(match.group(1)), content=content, props=props)
    node = Paragraph(content=content, props=props)
    frame = properties.find(f"{{{W}}}framePr") if properties is not None else None
    if frame is not None and (frame.get(f"{{{W}}}dropCap") or "none") != "none":
        from dataclasses import replace

        node = replace(node, drop_cap=int(frame.get(f"{{{W}}}lines") or 1))
    return node


def _read_paragraph_props(
    element: ET.Element | None, style: str, state: _ReadState
) -> ParagraphProps:
    """Rebuild paragraph properties from ``w:pPr``.

    Args:
        element: The ``w:pPr`` element, or ``None``.
        style: The style name already extracted.
        state: The reader state, for the numbering names.

    Returns:
        The properties.
    """
    changes: dict[str, Any] = {}
    if style and not re.fullmatch(r"Heading[1-9]", style):
        changes["style"] = style
    if element is not None:
        alignment = element.find(f"{{{W}}}jc")
        if alignment is not None:
            value = alignment.get(f"{{{W}}}val") or ""
            if value in _VALUES_ALIGNMENT:
                changes["alignment"] = _VALUES_ALIGNMENT[value]
        indent = element.find(f"{{{W}}}ind")
        if indent is not None:
            for attribute, name in (
                ("left", "indent_left"),
                ("right", "indent_right"),
                ("firstLine", "indent_first_line"),
            ):
                raw = indent.get(f"{{{W}}}{attribute}")
                if raw is not None:
                    changes[name] = Measure(value=float(raw), unit=LengthUnit.TWIP)
            hanging = indent.get(f"{{{W}}}hanging")
            if hanging is not None:
                changes["indent_first_line"] = Measure(
                    value=-float(hanging), unit=LengthUnit.TWIP
                )
        for name, field_name in (
            ("keepLines", "keep_together"),
            ("keepNext", "keep_with_next"),
            ("pageBreakBefore", "page_break_before"),
            ("contextualSpacing", "contextual_spacing"),
            ("suppressLineNumbers", "suppress_line_numbers"),
            ("widowControl", "widow_control"),
        ):
            value = _switch(element, name)
            if value is not None:
                changes[field_name] = value
        hyphens = _switch(element, "suppressAutoHyphens")
        if hyphens is not None:
            changes["hyphenate"] = not hyphens
        bidi = _switch(element, "bidi")
        if bidi is not None:
            from caissa.core.model import TextDirection

            changes["direction"] = TextDirection.RTL if bidi else TextDirection.LTR
        level = element.find(f"{{{W}}}outlineLvl")
        if level is not None:
            changes["outline_level"] = int(level.get(f"{{{W}}}val") or 0)
        shading = element.find(f"{{{W}}}shd")
        if shading is not None and shading.get(f"{{{W}}}fill") not in (None, "auto"):
            changes["shading"] = Color.from_hex("#" + shading.get(f"{{{W}}}fill"))
        spacing = element.find(f"{{{W}}}spacing")
        if spacing is not None:
            for attribute, field_name in (("before", "space_before"), ("after", "space_after")):
                raw = spacing.get(f"{{{W}}}{attribute}")
                if raw is not None:
                    changes[field_name] = Measure(value=float(raw), unit=LengthUnit.TWIP)
            line = spacing.get(f"{{{W}}}line")
            rule = spacing.get(f"{{{W}}}lineRule")
            if line is not None:
                from caissa.core.model import LineSpacing, LineSpacingRule

                if rule in (None, "auto"):
                    changes["line_spacing"] = LineSpacing(
                        rule=LineSpacingRule.MULTIPLE, value=float(line) / 240
                    )
                else:
                    changes["line_spacing"] = LineSpacing(
                        rule=(
                            LineSpacingRule.EXACT if rule == "exact" else LineSpacingRule.AT_LEAST
                        ),
                        value=1.0,
                        length=Measure(value=float(line), unit=LengthUnit.TWIP),
                    )
        stops = _read_tab_stops(element)
        if stops:
            changes["tab_stops"] = stops
        reference = _read_numbering_ref(element, state)
        if reference is not None:
            changes["numbering"] = reference
        mark = element.find(f"{{{W}}}rPr")
        if mark is not None:
            changes["mark_props"] = _read_run_props(mark)
    return ParagraphProps(**changes)


def _read_tab_stops(element: ET.Element) -> tuple[Any, ...]:
    """Rebuild the paragraph ruler from ``w:tabs``.

    Args:
        element: The ``w:pPr``.

    Returns:
        The tab stops, in file order.
    """
    from caissa.core.model import TabAlignment, TabLeader, TabStop

    tabs = element.find(f"{{{W}}}tabs")
    if tabs is None:
        return ()
    stops: list[TabStop] = []
    for stop in tabs.findall(f"{{{W}}}tab"):
        alignment = _VALUES_TAB_ALIGNMENT.get(stop.get(f"{{{W}}}val") or "left")
        if alignment is None:
            continue
        leader = _VALUES_TAB_LEADER.get(stop.get(f"{{{W}}}leader") or "none", "none")
        stops.append(
            TabStop(
                position=Measure(
                    value=float(stop.get(f"{{{W}}}pos") or "0"), unit=LengthUnit.TWIP
                ),
                alignment=TabAlignment(alignment),
                leader=TabLeader(leader),
            )
        )
    return tuple(stops)


def _read_numbering_ref(element: ET.Element, state: _ReadState) -> Any:
    """Rebuild a ``NumberingRef`` from ``w:numPr``.

    Args:
        element: The ``w:pPr``.
        state: The reader state, holding the ``w:numId`` mapping.

    Returns:
        The reference, or ``None`` when the paragraph names no numbering or
        names one of the two a list block uses.
    """
    reference = element.find(f"{{{W}}}numPr")
    if reference is None:
        return None
    identifier = reference.find(f"{{{W}}}numId")
    if identifier is None:
        return None
    number = int(identifier.get(f"{{{W}}}val") or 0)
    name = state.numbering.get(number)
    if not name:
        return None
    level = reference.find(f"{{{W}}}ilvl")
    return NumberingRef(
        definition=name,
        level=int(level.get(f"{{{W}}}val") or 0) if level is not None else 0,
        start_override=state.starts.get(number),
    )


@dataclass(frozen=True, slots=True)
class _Picture:
    """What one ``w:drawing`` says about the node it stands for."""

    resource: str
    alt_text: str | None
    title: str | None
    width: Measure
    height: Measure
    crop: tuple[float, ...]


def _read_picture(drawing: ET.Element, state: _ReadState | None) -> _Picture | None:
    """Read an image ``w:drawing`` back; ``None`` for a diagram's picture.

    A diagram is an EMF (or PNG fallback) part named ``media/diagramaN``; it
    stands for a :class:`Diagram` node this reader does not rebuild, so it is
    left alone as it always was. Everything else is an image node, whose key,
    text, title, size and crop the writer put in the picture's own fields.
    """
    extent = drawing.find(f".//{{{WP}}}extent")
    properties = drawing.find(f".//{{{WP}}}docPr")
    blip = drawing.find(f".//{{{A}}}blip")
    if extent is None or properties is None:
        return None
    if blip is not None and state is not None:
        target = state.targets.get(blip.get(f"{{{R}}}embed") or "", "")
        if target.rsplit("/", 1)[-1].startswith("diagrama"):
            return None
    elif (properties.get("name") or "").startswith("Diagrama "):
        return None
    source = drawing.find(f".//{{{A}}}srcRect")
    crop: tuple[float, ...] = ()
    if source is not None:
        insets = [int(source.get(edge) or 0) / _CROP_UNIT for edge in ("l", "t", "r", "b")]
        crop = (insets[0], insets[1], 1.0 - insets[2], 1.0 - insets[3])
    return _Picture(
        resource=properties.get("name") or "",
        alt_text=properties.get("descr") or None,
        title=properties.get("title") or None,
        width=_measure_from_emu(extent.get("cx")),
        height=_measure_from_emu(extent.get("cy")),
        crop=crop,
    )


def _measure_from_emu(raw: str | None) -> Measure:
    return Measure(value=round(int(raw or 0) / _EMU_PER_POINT, 2), unit=LengthUnit.PT)


_EMU_PER_POINT = 12700


def _lone_drawing(element: ET.Element) -> ET.Element | None:
    """The drawing a paragraph consists of, when it consists of nothing else.

    That is how the writer lays an :class:`ImageBlock` or a :class:`Diagram`
    down: one run, one drawing, no text -- in the Diagram style, which the
    paragraph keeps as its only other content.
    """
    runs = [child for child in element if child.tag == f"{{{W}}}r"]
    if len(runs) != 1:
        return None
    run = runs[0]
    if run.find(f"{{{W}}}t") is not None:
        return None
    return run.find(f"{{{W}}}drawing")


@dataclass(slots=True)
class _DiagramDraft:
    """A diagram read from its picture, still waiting for its neighbours.

    The writer lays a diagram down as up to four blocks -- stipulation,
    picture, caption, solution -- and only the picture carries the node. The
    draft says which of the other three the writer promised, so
    :func:`_assemble_diagrams` can fold them in. It never leaves the reader.
    """

    node: Diagram
    wants_stipulation: bool
    wants_caption: bool
    wants_solution: bool


def _diagram_from_drawing(drawing: ET.Element) -> _DiagramDraft | None:
    """Rebuild a diagram from the extension its picture carries, or ``None``."""
    from caissa.export.html import _parse_marks

    element = drawing.find(f".//{{{A}}}extLst/{{{A}}}ext/{{{DIAGRAM_NS}}}diagram")
    if element is None:
        return None
    number = element.get("number")
    marks = element.get("marks")
    node = Diagram(
        fen=element.get("fen") or "",
        orientation=Orientation(element.get("orientation") or "white"),
        number=int(number) if number else None,
        label=element.get("label"),
        marks=_parse_marks(marks) if marks else (),
        side_to_move_indicator=element.get("side-to-move") == "1",
        stipulation=element.get("stipulation"),
        anchor=element.get("anchor"),
        alt_text=element.get("alt"),
        move_context=element.get("move-context"),
        verified_by_human=element.get("verified") == "1",
    )
    return _DiagramDraft(
        node=node,
        wants_stipulation=bool(node.stipulation),
        wants_caption=element.get("caption") == "1",
        wants_solution=element.get("solution") == "1",
    )


_CAPTION_SEPARATOR = " — "


def _caption_inlines(paragraph: Paragraph) -> tuple[Inline, ...]:
    """The caption text after the ``Diagrama N — `` the writer prefixed.

    The runs before the separator are the label, the SEQ field's number and
    the separator itself; none of them was in the node.
    """
    content = list(paragraph.content)
    for index, inline in enumerate(content):
        if isinstance(inline, Text) and inline.content == _CAPTION_SEPARATOR:
            return tuple(content[index + 1 :])
    return ()


def _assemble_diagrams(blocks: list[Any]) -> list[Any]:
    """Fold each diagram's neighbours back into its node.

    The stipulation paragraph stood *before* the picture, inside the same
    bookmark, so it is the block that received the node's identity: the
    diagram takes it back from there. The caption and the solution stood
    after it, each in its own block.
    """
    from dataclasses import replace

    from caissa.core.model import GameScore as GameScoreNode

    out: list[Any] = []
    index = 0
    while index < len(blocks):
        item = blocks[index]
        if not isinstance(item, _DiagramDraft):
            out.append(item)
            index += 1
            continue
        node = item.node
        if item.wants_stipulation and out and isinstance(out[-1], Paragraph):
            previous = out.pop()
            node = replace(node, id=previous.id)
        following = index + 1
        if (
            item.wants_caption
            and following < len(blocks)
            and isinstance(blocks[following], Paragraph)
        ):
            node = replace(node, caption=_caption_inlines(blocks[following]))
            following += 1
        if (
            item.wants_solution
            and following < len(blocks)
            and isinstance(blocks[following], GameScoreNode)
        ):
            node = replace(node, solution=blocks[following])
            following += 1
        out.append(node)
        index = following
    return out


def _image_block(picture: _Picture, alignment: Alignment | None) -> ImageBlock:
    return ImageBlock(
        resource=picture.resource,
        alt_text=picture.alt_text,
        width=picture.width,
        height=picture.height,
        alignment=alignment,
        title=picture.title,
        crop=picture.crop,
    )


def _read_runs(element: ET.Element, state: _ReadState | None = None) -> tuple[Inline, ...]:
    """Rebuild the inline content of a paragraph.

    Args:
        element: The ``w:p`` or ``w:hyperlink``.
        state: The reader state, for the picture targets; ``None`` reads any
            drawing as an image.

    Returns:
        The inlines.
    """
    content: list[Inline] = []
    pending: list[str] = []
    for child in element:
        tag = child.tag.split("}")[-1]
        if tag == "bookmarkStart":
            name = child.get(f"{{{W}}}name") or ""
            if name.startswith(BOOKMARK_PREFIX):
                pending.append(name[len(BOOKMARK_PREFIX) :])
        elif tag == "hyperlink":
            content.extend(_read_runs(child, state))
        elif tag == "r":
            node = _read_run(child, state)
            if node is not None:
                content.append(_apply_identity(node, pending))
                pending = []
    return tuple(content)


def _read_run(element: ET.Element, state: _ReadState | None = None) -> Inline | None:
    """Rebuild one ``w:r``.

    Args:
        element: The run element.
        state: The reader state, for the picture targets.

    Returns:
        A :class:`~caissa.core.model.inline.Text`, an
        :class:`~caissa.core.model.inline.ImageInline` for a run that carries
        an image, or ``None`` when the run carries no text.
    """
    if element.find(f"{{{W}}}br") is not None and element.find(f"{{{W}}}t") is None:
        return LineBreak()
    drawing = element.find(f"{{{W}}}drawing")
    if drawing is not None and element.find(f"{{{W}}}t") is None:
        picture = _read_picture(drawing, state)
        if picture is None:
            return None
        return ImageInline(
            resource=picture.resource,
            alt_text=picture.alt_text,
            width=picture.width,
            height=picture.height,
        )
    pieces = [node.text or "" for node in element.findall(f"{{{W}}}t")]
    if not pieces:
        return None
    return Text(content="".join(pieces), props=_read_run_props(element.find(f"{{{W}}}rPr")))


def _read_run_props(element: ET.Element | None) -> RunProps:
    """Rebuild run properties from ``w:rPr``.

    Args:
        element: The ``w:rPr`` element, or ``None``.

    Returns:
        The properties.
    """
    if element is None:
        return RunProps()
    changes: dict[str, Any] = {}
    style = element.find(f"{{{W}}}rStyle")
    if style is not None:
        changes["style"] = style.get(f"{{{W}}}val")
    fonts = element.find(f"{{{W}}}rFonts")
    if fonts is not None and fonts.get(f"{{{W}}}ascii"):
        changes["font_family"] = fonts.get(f"{{{W}}}ascii")
    bold = element.find(f"{{{W}}}b")
    if bold is not None:
        changes["font_weight"] = 400 if bold.get(f"{{{W}}}val") == "0" else 700
    italic = element.find(f"{{{W}}}i")
    if italic is not None:
        changes["italic"] = italic.get(f"{{{W}}}val") != "0"
    size = element.find(f"{{{W}}}sz")
    if size is not None:
        changes["font_size"] = Measure(
            value=float(size.get(f"{{{W}}}val") or 22) / 2, unit=LengthUnit.PT
        )
    colour = element.find(f"{{{W}}}color")
    if colour is not None:
        raw = colour.get(f"{{{W}}}val") or ""
        if re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
            changes["color"] = Color.from_hex("#" + raw)
    underline = element.find(f"{{{W}}}u")
    if underline is not None:
        changes["underline"] = _VALUES_UNDERLINE.get(
            underline.get(f"{{{W}}}val") or "single", UnderlineStyle.SINGLE
        )
    strike = element.find(f"{{{W}}}strike")
    if strike is not None:
        changes["strikethrough"] = (
            StrikeStyle.NONE if strike.get(f"{{{W}}}val") == "0" else StrikeStyle.SINGLE
        )
    if element.find(f"{{{W}}}dstrike") is not None:
        changes["strikethrough"] = StrikeStyle.DOUBLE
    vertical = element.find(f"{{{W}}}vertAlign")
    if vertical is not None:
        raw = vertical.get(f"{{{W}}}val") or ""
        if raw in ("baseline", "superscript", "subscript"):
            changes["vertical_align"] = VerticalAlign(raw)
    language = element.find(f"{{{W}}}lang")
    if language is not None and language.get(f"{{{W}}}val"):
        changes["language"] = language.get(f"{{{W}}}val")
    _read_switches(element, changes)
    _read_metrics(element, changes)
    return RunProps(**changes)


def _switch(element: ET.Element, name: str) -> bool | None:
    """Read an OOXML on/off element.

    Args:
        element: The ``w:rPr`` or ``w:pPr``.
        name: The child element's local name.

    Returns:
        ``True``, ``False``, or ``None`` when the element is absent.
    """
    found = element.find(f"{{{W}}}{name}")
    if found is None:
        return None
    return found.get(f"{{{W}}}val") not in ("0", "false")


def _read_switches(element: ET.Element, changes: dict[str, Any]) -> None:
    """Read the boolean run properties.

    Args:
        element: The ``w:rPr``.
        changes: Collector for the field values.
    """
    from caissa.core.model import EmphasisMark, SmallCapsMode, TextDirection, TextOutline

    for name, field_name in (
        ("emboss", "emboss"),
        ("imprint", "engrave"),
        ("vanish", "hidden"),
    ):
        value = _switch(element, name)
        if value is not None:
            changes[field_name] = value
    outline = _switch(element, "outline")
    if outline is not None:
        changes["outline"] = TextOutline() if outline else None
    caps = _switch(element, "smallCaps")
    if caps is not None:
        changes["small_caps"] = SmallCapsMode.SYNTHETIC if caps else SmallCapsMode.NONE
    upper = _switch(element, "caps")
    if upper is not None:
        changes["text_transform"] = (
            TextTransform.UPPERCASE if upper else TextTransform.NONE
        )
    proof = _switch(element, "noProof")
    if proof is not None:
        changes["spell_check"] = not proof
    rtl = _switch(element, "rtl")
    if rtl is not None:
        changes["direction"] = TextDirection.RTL if rtl else TextDirection.LTR
    mark = element.find(f"{{{W}}}em")
    if mark is not None:
        raw = _VALUES_EMPHASIS.get(mark.get(f"{{{W}}}val") or "none", "none")
        changes["emphasis_mark"] = EmphasisMark(raw)
    if element.find(f"{{{W}}}shadow") is not None:
        from caissa.core.model import Measure as IrMeasure
        from caissa.core.model import TextShadow

        changes["shadow"] = TextShadow(
            offset_x=IrMeasure.points(1.0), offset_y=IrMeasure.points(1.0)
        )


def _read_metrics(element: ET.Element, changes: dict[str, Any]) -> None:
    """Read the measured run properties.

    Args:
        element: The ``w:rPr``.
        changes: Collector for the field values.
    """
    from caissa.core.model import LigatureMode, NumeralFigure, NumeralSpacing

    spacing = element.find(f"{{{W}}}spacing")
    if spacing is not None and spacing.get(f"{{{W}}}val"):
        changes["letter_spacing"] = Measure(
            value=float(spacing.get(f"{{{W}}}val")), unit=LengthUnit.TWIP
        )
    scale = element.find(f"{{{W}}}w")
    if scale is not None and scale.get(f"{{{W}}}val"):
        changes["horizontal_scale"] = float(scale.get(f"{{{W}}}val"))
    kern = element.find(f"{{{W}}}kern")
    if kern is not None:
        raw = float(kern.get(f"{{{W}}}val") or 0)
        changes["kerning"] = raw > 0
    position = element.find(f"{{{W}}}position")
    if position is not None and position.get(f"{{{W}}}val"):
        changes["baseline_shift"] = Measure(
            value=float(position.get(f"{{{W}}}val")) / 2, unit=LengthUnit.PT
        )
    highlight = element.find(f"{{{W}}}highlight")
    if highlight is not None:
        name = highlight.get(f"{{{W}}}val") or "yellow"
        red, green, blue = _HIGHLIGHTS.get(name, (255, 255, 0))
        changes["highlight"] = Color.from_hex(f"#{red:02X}{green:02X}{blue:02X}")
    shading = element.find(f"{{{W}}}shd")
    if shading is not None and shading.get(f"{{{W}}}fill") not in (None, "auto"):
        changes["background"] = Color.from_hex("#" + shading.get(f"{{{W}}}fill"))
    ligatures = element.find("{http://schemas.microsoft.com/office/word/2010/wordml}ligatures")
    if ligatures is not None:
        raw = ligatures.get(
            "{http://schemas.microsoft.com/office/word/2010/wordml}val"
        ) or "standard"
        changes["ligatures"] = LigatureMode(
            {
                "none": "none",
                "standard": "standard",
                "standardContextual": "contextual",
                "standardContextualDiscretional": "discretionary",
                "standardContextualHistorical": "historical",
                "all": "all",
            }.get(raw, "standard")
        )
    figures = element.find("{http://schemas.microsoft.com/office/word/2010/wordml}numForm")
    if figures is not None:
        raw = figures.get(
            "{http://schemas.microsoft.com/office/word/2010/wordml}val"
        ) or "default"
        changes["numeral_figure"] = NumeralFigure(
            {"lining": "lining", "oldStyle": "oldstyle", "default": "default"}.get(
                raw, "default"
            )
        )
    numeral_spacing = element.find(f"{{{W}}}numSpacing")
    if numeral_spacing is not None:
        changes["numeral_spacing"] = NumeralSpacing(
            numeral_spacing.get(f"{{{W}}}val") or "default"
        )


def _read_table(element: ET.Element, state: _ReadState) -> Table:
    """Rebuild one ``w:tbl``, rows and cells included.

    ``EG_ContentRowContent`` and ``EG_ContentCellContent`` both admit
    ``EG_RunLevelElts``, and a bookmark is one -- so a row and a cell can carry
    an identity without borrowing a paragraph's.

    Args:
        element: The table element.
        state: The reader state.

    Returns:
        The table.
    """
    from caissa.core.model import TableColumn, TableRow

    rows: list[TableRow] = []
    pending: list[str] = []
    ranges: dict[int, str] = {}
    for child in element:
        tag = child.tag.split("}")[-1]
        if tag == "bookmarkStart":
            name = child.get(f"{{{W}}}name") or ""
            if name.startswith(BOOKMARK_PREFIX):
                value = name[len(BOOKMARK_PREFIX) :]
                pending.append(value)
                ranges[int(child.get(f"{{{W}}}id") or 0)] = value
        elif tag == "bookmarkEnd":
            value = ranges.pop(int(child.get(f"{{{W}}}id") or 0), "")
            if value and value in pending:
                pending.remove(value)
        elif tag == "tr":
            rows.append(_apply_identity(_read_row(child, state), pending))
            pending = []
    grid = [
        Measure(value=float(column.get(f"{{{W}}}w") or "0"), unit=LengthUnit.TWIP)
        for column in element.findall(f"{{{W}}}tblGrid/{{{W}}}gridCol")
    ]
    columns = max(
        max((sum(cell.col_span for cell in row.cells) for row in rows), default=0),
        len(grid),
    )
    properties = element.find(f"{{{W}}}tblPr")
    style = None
    summary = None
    width = None
    alignment = None
    borders = None
    padding = None
    if properties is not None:
        named = properties.find(f"{{{W}}}tblStyle")
        if named is not None:
            style = named.get(f"{{{W}}}val")
        description = properties.find(f"{{{W}}}tblDescription")
        if description is not None:
            summary = description.get(f"{{{W}}}val")
        width = _read_table_width(properties.find(f"{{{W}}}tblW"))
        justify = properties.find(f"{{{W}}}jc")
        if justify is not None:
            alignment = _VALUES_ALIGNMENT.get(justify.get(f"{{{W}}}val") or "left")
        borders = _read_border_box(properties.find(f"{{{W}}}tblBorders"))
        padding = _read_margins(properties.find(f"{{{W}}}tblCellMar"))
    header_rows = sum(1 for row in rows if row.is_header)
    return Table(
        rows=tuple(rows),
        columns=tuple(
            TableColumn(width=grid[index] if index < len(grid) else None)
            for index in range(columns)
        ),
        header_row_count=header_rows,
        repeat_header=header_rows > 0,
        borders=borders,
        cell_padding=padding,
        width=width,
        alignment=alignment,
        style=style if style != "TableGrid" else None,
        summary=summary,
    )


def _read_row(element: ET.Element, state: _ReadState) -> Any:
    """Rebuild one ``w:tr``.

    Args:
        element: The row element.
        state: The reader state.

    Returns:
        The row.
    """
    from caissa.core.model import TableRow

    cells: list[Any] = []
    pending: list[str] = []
    ranges: dict[int, str] = {}
    for child in element:
        tag = child.tag.split("}")[-1]
        if tag == "bookmarkStart":
            name = child.get(f"{{{W}}}name") or ""
            if name.startswith(BOOKMARK_PREFIX):
                value = name[len(BOOKMARK_PREFIX) :]
                pending.append(value)
                ranges[int(child.get(f"{{{W}}}id") or 0)] = value
        elif tag == "bookmarkEnd":
            value = ranges.pop(int(child.get(f"{{{W}}}id") or 0), "")
            if value and value in pending:
                pending.remove(value)
        elif tag == "tc":
            cells.append(_apply_identity(_read_cell(child, state), pending))
            pending = []
    header = element.find(f"{{{W}}}trPr/{{{W}}}tblHeader") is not None
    height = element.find(f"{{{W}}}trPr/{{{W}}}trHeight")
    return TableRow(
        cells=tuple(cells),
        is_header=header,
        repeat_on_break=header,
        keep_together=element.find(f"{{{W}}}trPr/{{{W}}}cantSplit") is not None,
        height=(
            Measure(value=float(height.get(f"{{{W}}}val") or "0"), unit=LengthUnit.TWIP)
            if height is not None
            else None
        ),
    )


def _read_cell(element: ET.Element, state: _ReadState) -> Any:
    """Rebuild one ``w:tc``.

    Args:
        element: The cell element.
        state: The reader state.

    Returns:
        The cell.
    """
    from caissa.core.model import TableCell, VerticalCellAlignment

    read: list[Any] = []
    _collect(element, read, {}, state)
    content = tuple(item for item in read if not isinstance(item, _FlowMarker))
    properties = element.find(f"{{{W}}}tcPr")
    span = 1
    shading: Color | None = None
    vertical: VerticalCellAlignment | None = None
    if properties is not None:
        grid = properties.find(f"{{{W}}}gridSpan")
        if grid is not None:
            span = int(grid.get(f"{{{W}}}val") or 1)
        shade = properties.find(f"{{{W}}}shd")
        fill = shade.get(f"{{{W}}}fill") if shade is not None else None
        if fill and fill != "auto":
            shading = Color.from_hex("#" + fill)
        align = properties.find(f"{{{W}}}vAlign")
        if align is not None:
            name = _VALUES_CELL_VALIGN_NAMES.get(align.get(f"{{{W}}}val") or "top")
            vertical = VerticalCellAlignment(name) if name else None
    return TableCell(
        content=content,
        col_span=span,
        shading=shading,
        vertical_alignment=vertical,
        borders=_read_border_box(
            properties.find(f"{{{W}}}tcBorders") if properties is not None else None
        ),
        padding=_read_margins(
            properties.find(f"{{{W}}}tcMar") if properties is not None else None
        ),
    )


# --------------------------------------------------------------------------- #
# The movetext, read back run by run
# --------------------------------------------------------------------------- #
_MOVE_NUMBER = re.compile(r"^(\d+)(\.+)$")


def _read_game(element: ET.Element) -> Any:
    """Rebuild a game score from the runs of one movetext paragraph.

    The writer put each token in its own ``w:r`` and hung each move's bookmark
    on the run that holds its SAN, so the tree can be rebuilt without parsing
    the game as a string and without a chess engine having to agree that the
    moves are legal. The nesting comes from the ``(`` and ``)`` tokens, which
    is where PGN keeps it too.

    Args:
        element: The ``w:p`` in the ``GameScore`` style.

    Returns:
        The game score.
    """
    from caissa.core.model import GameHeaders
    from caissa.core.model import GameScore as GameScoreNode

    builder = _MoveTreeBuilder()
    for text, identity, bold in _movetext_tokens(element):
        builder.token(text, identity, bold)
    return GameScoreNode(
        headers=GameHeaders(result=builder.result or "*"),
        initial_comment=builder.initial_comment,
        children=builder.finish(),
    )


def _movetext_tokens(element: ET.Element) -> list[tuple[str, str, bool]]:
    """Collect the movetext tokens of a paragraph, with their identities.

    Args:
        element: The ``w:p``.

    Returns:
        One ``(text, identity, bold)`` triple per non-blank run, where the
        identity is the ULID of the bookmark that wrapped it, or ``""``.
    """
    tokens: list[tuple[str, str, bool]] = []
    pending: list[str] = []
    ranges: dict[int, str] = {}
    for child in element:
        tag = child.tag.split("}")[-1]
        if tag == "bookmarkStart":
            name = child.get(f"{{{W}}}name") or ""
            if name.startswith(BOOKMARK_PREFIX):
                value = name[len(BOOKMARK_PREFIX) :]
                pending.append(value)
                ranges[int(child.get(f"{{{W}}}id") or 0)] = value
        elif tag == "bookmarkEnd":
            value = ranges.pop(int(child.get(f"{{{W}}}id") or 0), "")
            if value and value in pending:
                pending.remove(value)
        elif tag == "r":
            text = "".join(node.text or "" for node in child.findall(f"{{{W}}}t"))
            if not text.strip():
                pending = []
                continue
            properties = child.find(f"{{{W}}}rPr")
            bold = properties is not None and properties.find(f"{{{W}}}b") is not None
            tokens.append((text.strip(), pending[-1] if pending else "", bold))
            pending = []
    return tokens


class _MoveTreeBuilder:
    """Rebuilds a move tree from the movetext token stream.

    The rule is the one :meth:`_Body._game_line` writes by: a move joins the
    line it is in, an alternative in parentheses is a sibling of the move it
    replaces, and the line then continues into the move's own children. Two
    lists are therefore live at once -- the one the *next* mainline move joins,
    and the one an alternative to the *last* move would join -- and mixing them
    up is the classic way to turn a variation into a continuation.
    """

    def __init__(self) -> None:
        """Start an empty tree."""
        self.initial_comment = ""
        self.result = ""
        self._root: list[dict[str, Any]] = []
        # Where the next mainline move goes.
        self._container: list[dict[str, Any]] = self._root
        # Where an alternative to the last move goes: the list that move is in.
        self._alternatives: list[dict[str, Any]] | None = None
        self._stack: list[tuple[list[dict[str, Any]], list[dict[str, Any]] | None]] = []
        self._last: dict[str, Any] | None = None
        self._pending_comment = ""
        self._pending_ply: int | None = None
        self._after_move = False

    def token(self, text: str, identity: str, bold: bool) -> None:
        """Consume one movetext token.

        Args:
            text: The token.
            identity: The ULID the bookmark carried, or ``""``.
            bold: Whether the run was bold, which is how emphasis travels.
        """
        if text == "(":
            self._stack.append((self._container, self._alternatives))
            if self._alternatives is not None:
                self._container = self._alternatives
            self._alternatives = None
            self._last = None
            self._after_move = False
            return
        if text == ")":
            if self._stack:
                self._container, self._alternatives = self._stack.pop()
            self._last = None
            self._after_move = False
            return
        if text.startswith("{") and text.endswith("}"):
            self._comment(text[1:-1].strip())
            return
        if text.startswith("$") and text[1:].isdigit():
            if self._last is not None:
                self._last["nags"] = (*self._last["nags"], int(text[1:]))
            return
        number = _MOVE_NUMBER.match(text)
        if number is not None:
            full = int(number.group(1))
            self._pending_ply = 2 * full if len(number.group(2)) > 1 else 2 * full - 1
            self._after_move = False
            return
        if text in ("1-0", "0-1", "1/2-1/2", "*"):
            self.result = text
            return
        self._move(text, identity, bold)

    def _comment(self, text: str) -> None:
        """Attach a comment either to the move behind it or the one ahead.

        PGN puts a move's starting comment *before* its number and its trailing
        comment *after* its notation, so position alone decides: everything
        between a move's notation and the next number belongs to that move, and
        everything else belongs to the move that is coming.

        Args:
            text: The comment body, braces already stripped.
        """
        if not self._root and self._container is self._root and not self.initial_comment:
            self.initial_comment = text
            return
        if self._after_move and self._last is not None:
            self._last["comments"].append(text)
            return
        self._pending_comment = (
            f"{self._pending_comment} {text}".strip() if self._pending_comment else text
        )

    def _move(self, san: str, identity: str, bold: bool) -> None:
        """Append one move to the line being read.

        Args:
            san: The move's notation.
            identity: The ULID the bookmark carried.
            bold: Whether the run was bold.
        """
        ply = self._pending_ply
        if ply is None:
            ply = (self._last["ply"] + 1) if self._last is not None else 1
        node: dict[str, Any] = {
            "san": san,
            "identity": identity,
            "ply": ply,
            "nags": (),
            "comments": [],
            "before": self._pending_comment,
            "emphasis": bold,
            "children": [],
        }
        self._pending_comment = ""
        self._pending_ply = None
        if self._last is None:
            self._container.append(node)
            self._alternatives = self._container
        else:
            self._last["children"].append(node)
            self._alternatives = self._last["children"]
        self._container = node["children"]
        self._last = node
        self._after_move = True

    def finish(self) -> tuple[Any, ...]:
        """Freeze the tree into ``MoveNode`` objects.

        Returns:
            The root continuations.
        """
        return tuple(_freeze_move(node) for node in self._root)


def _freeze_move(raw: Mapping[str, Any]) -> Any:
    """Turn one builder record into a :class:`~caissa.core.model.game.MoveNode`.

    Args:
        raw: The record.

    Returns:
        The move node.
    """
    from dataclasses import replace

    from caissa.core.model import MoveNode
    from caissa.export.text import split_move_commands

    after = ""
    clock: Any = None
    evaluation: Any = None
    arrows: tuple[Any, ...] = ()
    highlights: tuple[Any, ...] = ()
    for comment in raw["comments"]:
        found_clock, found_eval, found_arrows, found_highlights, rest = split_move_commands(
            comment
        )
        clock = found_clock or clock
        evaluation = found_eval or evaluation
        arrows = found_arrows or arrows
        highlights = found_highlights or highlights
        if rest:
            after = f"{after} {rest}".strip() if after else rest
    node = MoveNode(
        san=raw["san"],
        ply=raw["ply"],
        nags=tuple(raw["nags"]),
        comment_before=raw["before"],
        comment_after=after,
        arrows=arrows,
        highlights=highlights,
        clock=clock,
        evaluation=evaluation,
        emphasis=raw["emphasis"],
        children=tuple(_freeze_move(child) for child in raw["children"]),
    )
    if raw["identity"]:
        try:
            node = replace(node, id=ULID.from_string(raw["identity"]))
        except (ValueError, TypeError):
            pass
    return node


def _metadata_from_core(core: str) -> Any:
    """Rebuild document metadata from ``docProps/core.xml``.

    Args:
        core: The part text, possibly empty.

    Returns:
        The metadata.
    """
    from caissa.core.model import Contributor, ContributorRole, DocumentMetadata

    if not core:
        return DocumentMetadata()
    root = ET.fromstring(core)
    dc = "{http://purl.org/dc/elements/1.1/}"
    cp = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"

    def value(tag: str) -> str | None:
        found = root.find(tag)
        return (found.text or None) if found is not None else None

    authors = value(f"{dc}creator") or ""
    keywords = value(f"{cp}keywords") or ""
    return DocumentMetadata(
        title=value(f"{dc}title"),
        subtitle=value(f"{dc}subject"),
        description=value(f"{dc}description"),
        language=value(f"{dc}language") or "pt-BR",
        contributors=tuple(
            Contributor(name=name.strip(), role=ContributorRole.AUTHOR)
            for name in authors.split(",")
            if name.strip()
        ),
        subjects=tuple(part.strip() for part in keywords.split(",") if part.strip()),
    )
