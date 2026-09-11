"""Block nodes: everything that stacks vertically down a page (SPEC 5.1).

Blocks nest -- a table cell holds blocks, a list item holds blocks, a callout
holds blocks -- so the structures a chess book actually uses (an exercise box
containing a diagram, a caption and a hidden solution; a two-column opening
table whose cells hold move sequences) are expressible without special cases.

:class:`~caissa.core.model.diagram.Diagram` and
:class:`~caissa.core.model.game.GameScore` are blocks too, defined in their own
modules because of their size, and re-exported here as part of the ``Block``
union.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from caissa.core.model.base import IRNode
from caissa.core.model.diagram import Diagram
from caissa.core.model.game import GameScore
from caissa.core.model.inline import Inline
from caissa.core.model.props import (
    Alignment,
    Border,
    Borders,
    Color,
    Measure,
    NumberingRef,
    Padding,
    ParagraphProps,
    RunProps,
)
from caissa.core.model.registry import ir_node

__all__ = [
    "Block",
    "Callout",
    "CalloutKind",
    "CodeBlock",
    "ColumnLayout",
    "Endnote",
    "Figure",
    "FigurePlacement",
    "Footnote",
    "Group",
    "GroupRole",
    "Heading",
    "ImageBlock",
    "ListBlock",
    "ListItem",
    "ListKind",
    "ListMarkerStyle",
    "MathBlock",
    "PageBreak",
    "PageGeometry",
    "Paragraph",
    "Quote",
    "RawPassthrough",
    "SectionBreak",
    "SectionBreakKind",
    "Table",
    "TableCell",
    "TableColumn",
    "TableOfContents",
    "TableRow",
    "ThematicBreak",
    "VerticalCellAlignment",
    "block_children",
]


class ListKind(StrEnum):
    """What kind of list a :class:`ListBlock` is."""

    ORDERED = "ordered"
    UNORDERED = "unordered"
    DEFINITION = "definition"


class ListMarkerStyle(StrEnum):
    """How list markers are drawn."""

    DECIMAL = "decimal"
    DECIMAL_LEADING_ZERO = "decimal-leading-zero"
    LOWER_ALPHA = "lower-alpha"
    UPPER_ALPHA = "upper-alpha"
    LOWER_ROMAN = "lower-roman"
    UPPER_ROMAN = "upper-roman"
    BULLET = "bullet"
    DASH = "dash"
    SQUARE = "square"
    CIRCLE = "circle"
    NONE = "none"
    CUSTOM = "custom"


class FigurePlacement(StrEnum):
    """Where a floating figure is allowed to land."""

    HERE = "here"
    TOP = "top"
    BOTTOM = "bottom"
    PAGE = "page"
    INLINE = "inline"
    FLOAT_LEFT = "float-left"
    FLOAT_RIGHT = "float-right"


class CalloutKind(StrEnum):
    """What a callout box is for.

    The chess-specific kinds are not decoration: an ``EXERCISE`` box and a
    ``SOLUTION`` box are the structure a puzzle book is built from, and an
    exporter needs to know which is which to hide solutions until the end of a
    chapter.
    """

    NOTE = "note"
    TIP = "tip"
    WARNING = "warning"
    IMPORTANT = "important"
    EXAMPLE = "example"
    EXERCISE = "exercise"
    SOLUTION = "solution"
    THEORY = "theory"
    SUMMARY = "summary"
    SIDEBAR = "sidebar"


class GroupRole(StrEnum):
    """Why a set of blocks is grouped."""

    GENERIC = "generic"
    SECTION = "section"
    CHAPTER = "chapter"
    FRONT_MATTER = "front-matter"
    BACK_MATTER = "back-matter"
    DIAGRAM_GRID = "diagram-grid"
    EXERCISE_SET = "exercise-set"
    ABSTRACT = "abstract"
    DEDICATION = "dedication"
    COLOPHON = "colophon"


class SectionBreakKind(StrEnum):
    """Where a new section starts."""

    CONTINUOUS = "continuous"
    NEXT_PAGE = "next-page"
    EVEN_PAGE = "even-page"
    ODD_PAGE = "odd-page"
    NEXT_COLUMN = "next-column"


class VerticalCellAlignment(StrEnum):
    """Vertical placement of content inside a table cell."""

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


# --------------------------------------------------------------------------- #
# Text blocks
# --------------------------------------------------------------------------- #


@ir_node("heading")
@dataclass(frozen=True, slots=True, kw_only=True)
class Heading(IRNode):
    """A section heading.

    Attributes:
        level: Depth from ``1`` (chapter) to ``6``.
        content: The heading text.
        numbering: Reference into a numbering definition, so chapter numbers
            renumber themselves after an edit.
        numbering_text: Literal number to print, when the source had one and it
            must not be recomputed.
        anchor: Name links and the table of contents point at.
        toc_text: Short form for the table of contents, when the full heading
            is too long.
        props: Paragraph formatting.
        run_props: Character formatting shared by the whole heading.
        list_in_toc: Whether the heading appears in generated tables of
            contents.
    """

    level: int = 1
    content: tuple[Inline, ...] = ()
    numbering: NumberingRef | None = None
    numbering_text: str | None = None
    anchor: str | None = None
    toc_text: str | None = None
    props: ParagraphProps = field(default_factory=ParagraphProps)
    run_props: RunProps = field(default_factory=RunProps)
    list_in_toc: bool = True


@ir_node("paragraph")
@dataclass(frozen=True, slots=True, kw_only=True)
class Paragraph(IRNode):
    """A paragraph of running text.

    Attributes:
        content: The inlines that make it up.
        props: Paragraph formatting, including the named paragraph style.
        drop_cap: Number of lines a drop capital spans; ``None`` for no drop
            cap.
    """

    content: tuple[Inline, ...] = ()
    props: ParagraphProps = field(default_factory=ParagraphProps)
    drop_cap: int | None = None


@ir_node("list_item")
@dataclass(frozen=True, slots=True, kw_only=True)
class ListItem(IRNode):
    """One entry in a list.

    Attributes:
        content: Blocks making up the item body.
        term: The term being defined, for definition lists only.
        marker_override: Literal marker text replacing the computed one.
        start_override: Restart the counter at this value.
        checked: Checkbox state, for task lists; ``None`` for a plain item.
    """

    content: tuple[Block, ...] = ()
    term: tuple[Inline, ...] = ()
    marker_override: str | None = None
    start_override: int | None = None
    checked: bool | None = None


@ir_node("list_block")
@dataclass(frozen=True, slots=True, kw_only=True)
class ListBlock(IRNode):
    """An ordered, unordered or definition list.

    Attributes:
        kind: Which of the three.
        items: The entries.
        marker_style: How markers are drawn.
        marker_text: Literal marker for ``CUSTOM`` style, e.g. a chess glyph.
        start: First number of an ordered list.
        tight: Whether items are set without inter-item spacing.
        numbering: Reference into a numbering definition, when the list shares
            a counter with other lists.
        props: Paragraph formatting applied to every item.
        indent: Indent of the whole list.
    """

    kind: ListKind = ListKind.UNORDERED
    items: tuple[ListItem, ...] = ()
    marker_style: ListMarkerStyle = ListMarkerStyle.BULLET
    marker_text: str | None = None
    start: int = 1
    tight: bool = False
    numbering: NumberingRef | None = None
    props: ParagraphProps = field(default_factory=ParagraphProps)
    indent: Measure | None = None


@ir_node("quote")
@dataclass(frozen=True, slots=True, kw_only=True)
class Quote(IRNode):
    """A block quotation.

    Attributes:
        content: The quoted blocks.
        attribution: Who said it.
        props: Paragraph formatting.
    """

    content: tuple[Block, ...] = ()
    attribution: tuple[Inline, ...] = ()
    props: ParagraphProps = field(default_factory=ParagraphProps)


@ir_node("callout")
@dataclass(frozen=True, slots=True, kw_only=True)
class Callout(IRNode):
    """A set-apart box: a note, a warning, an exercise, a solution.

    Attributes:
        kind: What the box is for.
        title: Heading printed on the box.
        content: The blocks inside.
        props: Paragraph formatting.
        borders: Box border.
        padding: Space between border and content.
        shading: Background fill.
        collapsed: Whether interactive formats start it folded away -- how an
            EPUB hides a solution until the reader asks.
    """

    kind: CalloutKind = CalloutKind.NOTE
    title: tuple[Inline, ...] = ()
    content: tuple[Block, ...] = ()
    props: ParagraphProps = field(default_factory=ParagraphProps)
    borders: Borders | None = None
    padding: Padding | None = None
    shading: Color | None = None
    collapsed: bool = False


@ir_node("code_block")
@dataclass(frozen=True, slots=True, kw_only=True)
class CodeBlock(IRNode):
    """Preformatted text, kept verbatim.

    Attributes:
        language: Language hint for syntax highlighting; also used for raw
            PGN and FEN listings.
        text: The content, newlines included.
        show_line_numbers: Whether lines are numbered.
        props: Paragraph formatting.
        run_props: Character formatting; usually a monospaced family.
    """

    language: str = ""
    text: str = ""
    show_line_numbers: bool = False
    props: ParagraphProps = field(default_factory=ParagraphProps)
    run_props: RunProps = field(default_factory=RunProps)


@ir_node("math_block")
@dataclass(frozen=True, slots=True, kw_only=True)
class MathBlock(IRNode):
    """A displayed formula.

    Attributes:
        latex: The formula in LaTeX.
        mathml: A pre-built MathML rendering, when the importer had one.
        display: Whether it is set on its own line rather than in the text
            flow. SPEC 5.1 names the node ``Math(latex, display|inline)``; the
            inline case is
            :class:`~caissa.core.model.inline.MathInline`, and this flag lets a
            block-level formula still be typeset tightly.
        numbered: Whether the formula carries an equation number.
        label: Name cross-references point at.
        props: Paragraph formatting.
    """

    latex: str = ""
    mathml: str | None = None
    display: bool = True
    numbered: bool = False
    label: str | None = None
    props: ParagraphProps = field(default_factory=ParagraphProps)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


@ir_node("table_column")
@dataclass(frozen=True, slots=True, kw_only=True)
class TableColumn:
    """One column's shared settings.

    Attributes:
        width: Preferred width.
        alignment: Default horizontal alignment of its cells.
        min_width: Lower bound when the layout is elastic.
    """

    width: Measure | None = None
    alignment: Alignment | None = None
    min_width: Measure | None = None


@ir_node("table_cell")
@dataclass(frozen=True, slots=True, kw_only=True)
class TableCell(IRNode):
    """One cell.

    Attributes:
        content: The blocks inside.
        row_span: How many rows the cell covers.
        col_span: How many columns the cell covers.
        alignment: Horizontal alignment, overriding the column's.
        vertical_alignment: Vertical placement inside the cell.
        borders: Cell borders.
        padding: Space between border and content.
        shading: Background fill.
        is_header: Whether the cell is a header cell, which decides both its
            styling and its accessibility role.
    """

    content: tuple[Block, ...] = ()
    row_span: int = 1
    col_span: int = 1
    alignment: Alignment | None = None
    vertical_alignment: VerticalCellAlignment | None = None
    borders: Borders | None = None
    padding: Padding | None = None
    shading: Color | None = None
    is_header: bool = False


@ir_node("table_row")
@dataclass(frozen=True, slots=True, kw_only=True)
class TableRow(IRNode):
    """One row.

    Attributes:
        cells: The cells, left to right. A cell covered by a neighbour's
            ``row_span`` or ``col_span`` is simply absent, as in HTML.
        height: Preferred row height.
        is_header: Whether the whole row is a header row.
        repeat_on_break: Whether the row repeats at the top of each page the
            table spills onto.
        keep_together: Forbid a page break inside the row.
    """

    cells: tuple[TableCell, ...] = ()
    height: Measure | None = None
    is_header: bool = False
    repeat_on_break: bool = False
    keep_together: bool = False


@ir_node("table")
@dataclass(frozen=True, slots=True, kw_only=True)
class Table(IRNode):
    """A table.

    Attributes:
        columns: Per-column settings; its length is the declared column count
            the validator checks spans against.
        rows: The rows.
        header_row_count: How many leading rows are header rows.
        footer_row_count: How many trailing rows are footer rows.
        repeat_header: Whether header rows repeat across page breaks.
        borders: Table-level borders, including the inside rules.
        cell_padding: Default padding for every cell.
        width: Overall table width.
        alignment: Horizontal placement of the table itself.
        caption: Caption inlines.
        caption_above: Whether the caption sits above the table.
        number: Automatic table number.
        style: Name of a table style in the document stylesheet.
        anchor: Name cross-references point at.
        summary: Accessible description of the table's structure.
    """

    columns: tuple[TableColumn, ...] = ()
    rows: tuple[TableRow, ...] = ()
    header_row_count: int = 0
    footer_row_count: int = 0
    repeat_header: bool = True
    borders: Borders | None = None
    cell_padding: Padding | None = None
    width: Measure | None = None
    alignment: Alignment | None = None
    caption: tuple[Inline, ...] = ()
    caption_above: bool = False
    number: int | None = None
    style: str | None = None
    anchor: str | None = None
    summary: str | None = None

    @property
    def column_count(self) -> int:
        """The declared number of columns."""
        return len(self.columns)


# --------------------------------------------------------------------------- #
# Figures and images
# --------------------------------------------------------------------------- #


@ir_node("image_block")
@dataclass(frozen=True, slots=True, kw_only=True)
class ImageBlock(IRNode):
    """A standalone image.

    Attributes:
        resource: Key into the document's resource table.
        alt_text: Accessible description. Its absence is an accessibility
            defect the validator reports, because EPUB and tagged PDF both
            require it.
        width: Rendered width.
        height: Rendered height.
        alignment: Horizontal placement.
        title: Title attribute, shown on hover in reflowable formats.
        crop: Fractional crop as ``(left, top, right, bottom)`` of the source.
    """

    resource: str
    alt_text: str | None = None
    width: Measure | None = None
    height: Measure | None = None
    alignment: Alignment | None = None
    title: str | None = None
    crop: tuple[float, ...] = ()


@ir_node("figure")
@dataclass(frozen=True, slots=True, kw_only=True)
class Figure(IRNode):
    """A numbered figure: content plus caption, kept together.

    Attributes:
        content: The blocks the figure contains -- an image, a diagram, a
            table, or several of them side by side.
        caption: Caption inlines.
        number: Automatic figure number.
        label: Literal label overriding the derived one.
        placement: Where a floating figure may land.
        caption_above: Whether the caption sits above the content.
        anchor: Name cross-references point at.
        alt_text: Accessible description for the figure as a whole.
        props: Paragraph formatting of the figure container.
    """

    content: tuple[Block, ...] = ()
    caption: tuple[Inline, ...] = ()
    number: int | None = None
    label: str | None = None
    placement: FigurePlacement = FigurePlacement.HERE
    caption_above: bool = False
    anchor: str | None = None
    alt_text: str | None = None
    props: ParagraphProps = field(default_factory=ParagraphProps)


# --------------------------------------------------------------------------- #
# Notes
# --------------------------------------------------------------------------- #


@ir_node("footnote")
@dataclass(frozen=True, slots=True, kw_only=True)
class Footnote(IRNode):
    """A footnote body, printed at the foot of the page that references it.

    Attributes:
        ref: The key a :class:`~caissa.core.model.inline.NoteRef` points at.
            Must be unique across footnotes and endnotes.
        content: The note body.
        marker: Literal marker text, when it must not be renumbered.
        props: Paragraph formatting.
    """

    ref: str
    content: tuple[Block, ...] = ()
    marker: str | None = None
    props: ParagraphProps = field(default_factory=ParagraphProps)


@ir_node("endnote")
@dataclass(frozen=True, slots=True, kw_only=True)
class Endnote(IRNode):
    """An endnote body, collected at the end of the chapter or book.

    Attributes:
        ref: The key a :class:`~caissa.core.model.inline.NoteRef` points at.
            Must be unique across footnotes and endnotes.
        content: The note body.
        marker: Literal marker text, when it must not be renumbered.
        props: Paragraph formatting.
    """

    ref: str
    content: tuple[Block, ...] = ()
    marker: str | None = None
    props: ParagraphProps = field(default_factory=ParagraphProps)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #


@ir_node("page_geometry")
@dataclass(frozen=True, slots=True, kw_only=True)
class PageGeometry:
    """The trim size and margins of a section.

    Attributes:
        width: Page width.
        height: Page height.
        margin_top: Top margin.
        margin_bottom: Bottom margin.
        margin_inner: Inner margin -- the spine side, which swaps between
            recto and verso.
        margin_outer: Outer margin.
        gutter: Extra allowance for binding.
        landscape: Whether the page is rotated.
        mirror_margins: Whether inner and outer swap on facing pages.
    """

    width: Measure | None = None
    height: Measure | None = None
    margin_top: Measure | None = None
    margin_bottom: Measure | None = None
    margin_inner: Measure | None = None
    margin_outer: Measure | None = None
    gutter: Measure | None = None
    landscape: bool = False
    mirror_margins: bool = True


@ir_node("column_layout")
@dataclass(frozen=True, slots=True, kw_only=True)
class ColumnLayout:
    """A multi-column text area.

    Attributes:
        count: Number of columns.
        gap: Space between columns.
        rule: Vertical rule drawn in the gap.
        balanced: Whether the last page's columns are balanced in height.
        widths: Explicit per-column widths for an unequal layout.
    """

    count: int = 1
    gap: Measure | None = None
    rule: Border | None = None
    balanced: bool = True
    widths: tuple[Measure, ...] = ()


@ir_node("page_break")
@dataclass(frozen=True, slots=True, kw_only=True)
class PageBreak(IRNode):
    """A forced page break."""


@ir_node("section_break")
@dataclass(frozen=True, slots=True, kw_only=True)
class SectionBreak(IRNode):
    """A change of page geometry, column layout, or running heads.

    Attributes:
        kind: Where the new section starts.
        columns: Column layout of the new section.
        geometry: Page geometry of the new section.
        header_text: Running head content.
        footer_text: Running foot content.
        different_first_page: Whether the section's first page suppresses the
            running head.
        different_odd_even: Whether recto and verso have different running
            heads.
        page_number_start: Restart page numbering at this value.
        page_number_format: Numbering style, e.g. ``"decimal"`` or
            ``"lower-roman"`` for front matter.
        vertical_alignment: Vertical placement of the text block on the page.
    """

    kind: SectionBreakKind = SectionBreakKind.NEXT_PAGE
    columns: ColumnLayout | None = None
    geometry: PageGeometry | None = None
    header_text: tuple[Inline, ...] = ()
    footer_text: tuple[Inline, ...] = ()
    different_first_page: bool = False
    different_odd_even: bool = False
    page_number_start: int | None = None
    page_number_format: str | None = None
    vertical_alignment: VerticalCellAlignment | None = None


@ir_node("thematic_break")
@dataclass(frozen=True, slots=True, kw_only=True)
class ThematicBreak(IRNode):
    """A scene break: a rule, a row of asterisks, or extra leading.

    Attributes:
        ornament: The character or glyph used, when the break is decorative.
        rule: The rule drawn, when the break is a line.
    """

    ornament: str | None = None
    rule: Border | None = None


@ir_node("group")
@dataclass(frozen=True, slots=True, kw_only=True)
class Group(IRNode):
    """A named grouping of blocks with no page-level semantics of its own.

    Attributes:
        role: Why the blocks are grouped.
        content: The grouped blocks.
        title: Optional label for the group.
        props: Paragraph formatting applied to the container.
        anchor: Name cross-references point at.
        columns: Column count when the group lays its children out in a grid,
            as a page of exercise diagrams does.
    """

    role: GroupRole = GroupRole.GENERIC
    content: tuple[Block, ...] = ()
    title: tuple[Inline, ...] = ()
    props: ParagraphProps = field(default_factory=ParagraphProps)
    anchor: str | None = None
    columns: int | None = None


@ir_node("table_of_contents")
@dataclass(frozen=True, slots=True, kw_only=True)
class TableOfContents(IRNode):
    """A placeholder the exporter fills with a generated contents list.

    Kept as a node rather than pre-rendered text so that DOCX can emit a live
    ``TOC`` field, PDF a real outline, and EPUB a ``nav`` document -- all from
    one declaration.

    Attributes:
        title: Heading printed above the list.
        min_level: Shallowest heading level included.
        max_level: Deepest heading level included.
        show_page_numbers: Whether page numbers are printed.
        leader: Whether a dot leader runs to the page number.
        scope: Restrict the list to a kind of entry: ``"headings"``,
            ``"figures"``, ``"tables"``, ``"diagrams"``, ``"games"``.
    """

    title: tuple[Inline, ...] = ()
    min_level: int = 1
    max_level: int = 3
    show_page_numbers: bool = True
    leader: bool = True
    scope: str = "headings"


@ir_node("raw_passthrough")
@dataclass(frozen=True, slots=True, kw_only=True)
class RawPassthrough(IRNode):
    """Format-specific block content passed straight through (escape hatch).

    ADR-0002 keeps this deliberately measurable: a document full of passthrough
    means the IR has a gap, and the fidelity report counts it.

    Attributes:
        format: Target format the content belongs to, e.g. ``"latex"``,
            ``"html"``, ``"docx-xml"``. Other exporters skip it and record a
            ``DegradationWarning``.
        text: The verbatim content.
    """

    format: str
    text: str


#: Every block node type. Exhaustive.
Block = (
    Heading
    | Paragraph
    | ListBlock
    | Table
    | Figure
    | Diagram
    | GameScore
    | CodeBlock
    | MathBlock
    | Footnote
    | Endnote
    | PageBreak
    | SectionBreak
    | ThematicBreak
    | Quote
    | Callout
    | Group
    | ImageBlock
    | TableOfContents
    | RawPassthrough
)


def block_children(node: Block) -> tuple[Block, ...]:
    """Return the blocks a container block holds directly.

    Table rows and list items are not blocks themselves, so their contents are
    reached through them; this helper flattens that for callers that only care
    about block nesting.

    Args:
        node: Any block node.

    Returns:
        Its block children, in document order.
    """
    if isinstance(node, (Quote, Callout, Figure, Group)):
        return node.content
    if isinstance(node, (Footnote, Endnote)):
        return node.content
    if isinstance(node, ListBlock):
        collected: list[Block] = []
        for item in node.items:
            collected.extend(item.content)
        return tuple(collected)
    if isinstance(node, Table):
        cells: list[Block] = []
        for row in node.rows:
            for cell in row.cells:
                cells.extend(cell.content)
        return tuple(cells)
    return ()
