"""Inline nodes: everything that lives inside a line of text (SPEC 5.1, 5.5).

An inline is either a leaf that carries content (:class:`Text`, :class:`Move`,
:class:`PieceGlyph`) or a wrapper that gives meaning to the inlines it contains
(:class:`Emphasis`, :class:`Link`). Wrappers nest arbitrarily, which is what
lets "a bold move inside an italic parenthetical inside a footnote" survive a
round trip through five output formats.

The wrappers are *semantic*, not presentational: :class:`Emphasis` means "this
is emphasised", and the stylesheet decides that emphasis is italic. A run that
is italic for no reason carries ``RunProps(italic=True)`` on a :class:`Span`
instead. Keeping the two apart is what allows a global restyle of a whole book,
and it is the difference between an IR and a pile of formatting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from caissa.core.chess.notation_tables import (
    DEFAULT_LANGUAGE,
    FigurineSet,
    MoveRenderStyle,
    PieceType,
    piece_letter,
)
from caissa.core.model.base import IRNode
from caissa.core.model.marks import Mark
from caissa.core.model.props import Measure, RunProps
from caissa.core.model.registry import ir_node

__all__ = [
    "INLINE_WRAPPERS",
    "Anchor",
    "Emphasis",
    "ImageInline",
    "IndexEntry",
    "Inline",
    "InlineDiagram",
    "LineBreak",
    "Link",
    "LinkKind",
    "MathInline",
    "Move",
    "NagSymbol",
    "NonBreakingSpace",
    "NoteRef",
    "Orientation",
    "PieceGlyph",
    "RawInline",
    "SmallCaps",
    "Space",
    "SpaceKind",
    "Span",
    "Strike",
    "Strong",
    "Subscript",
    "Superscript",
    "Tab",
    "Text",
    "Underline",
    "inline_children",
    "plain_text",
]


class Orientation(StrEnum):
    """Which side of the board faces the reader."""

    WHITE = "white"
    BLACK = "black"


class LinkKind(StrEnum):
    """What a link points at, which decides how each format writes it."""

    EXTERNAL = "external"
    INTERNAL = "internal"
    EMAIL = "email"
    RESOURCE = "resource"


class SpaceKind(StrEnum):
    """Fixed-width spaces that carry meaning and must not be collapsed.

    A thin space between a move number and its move is a typographic decision a
    chess publisher makes deliberately; turning it into an ordinary space on
    export would be a visible regression.
    """

    THIN = "thin"
    HAIR = "hair"
    EN = "en"
    EM = "em"
    FIGURE = "figure"
    PUNCTUATION = "punctuation"
    ZERO_WIDTH = "zero-width"
    ZERO_WIDTH_NON_JOINER = "zero-width-non-joiner"
    ZERO_WIDTH_JOINER = "zero-width-joiner"


# --------------------------------------------------------------------------- #
# Leaves
# --------------------------------------------------------------------------- #


@ir_node("text")
@dataclass(frozen=True, slots=True, kw_only=True)
class Text(IRNode):
    """A run of literal characters with uniform formatting.

    Attributes:
        content: The characters. Never contains a newline: a line break is
            :class:`LineBreak`, and a paragraph break is a new block.
        props: Direct character formatting for this run.
    """

    content: str
    props: RunProps = field(default_factory=RunProps)


@ir_node("move")
@dataclass(frozen=True, slots=True, kw_only=True)
class Move(IRNode):
    """A chess move as a semantic object, not as text (SPEC 5.5).

    ``san`` is always canonical English. Rendering in Portuguese, German or
    figurine is a projection performed at export time by
    :func:`caissa.core.chess.notation_tables.render_san`, which is why changing
    the notation language of an entire book is a stylesheet edit rather than a
    rewrite.

    Attributes:
        san: Canonical English SAN, e.g. ``"Nf3"``, ``"O-O"``, ``"exd5"``.
        ply: Half-move number from the start of the game, ``1`` for White's
            first move.
        position_before: FEN of the position the move is played from. Keeping
            it on the move is what lets a move quoted in running prose be
            validated, replayed and turned into a diagram without walking back
            to a game score that may not exist.
        nags: Numeric Annotation Glyphs attached to the move (``$1`` is ``!``).
        render: Figurine, language letters, or both.
        language: BCP-47 tag for the letter form.
        figurine_set: Which Unicode glyph set a figurine rendering uses.
        uci: Long algebraic form, when known. Redundant with ``san`` plus
            ``position_before``, but free to carry and expensive to recompute.
        show_move_number: Whether the rendered form is preceded by its move
            number.
        move_number_text: Explicit move-number prefix, e.g. ``"24..."``. When
            ``None`` the exporter derives it from ``ply``.
        props: Direct character formatting.
    """

    san: str
    ply: int = 0
    position_before: str = ""
    nags: tuple[int, ...] = ()
    render: MoveRenderStyle = MoveRenderStyle.LETTERS
    language: str = DEFAULT_LANGUAGE
    figurine_set: FigurineSet = FigurineSet.BLACK
    uci: str | None = None
    show_move_number: bool = False
    move_number_text: str | None = None
    props: RunProps = field(default_factory=RunProps)

    @property
    def move_number(self) -> int:
        """The full-move number this ply belongs to."""
        return (max(self.ply, 1) + 1) // 2

    @property
    def is_black_move(self) -> bool:
        """Whether this ply is Black's."""
        return self.ply % 2 == 0 and self.ply > 0


@ir_node("piece_glyph")
@dataclass(frozen=True, slots=True, kw_only=True)
class PieceGlyph(IRNode):
    """A single piece symbol in running text -- figurine outside a move.

    Attributes:
        piece: Which piece.
        figurine_set: Outline or solid glyphs; this is also what makes the
            glyph read as a white or a black piece.
        font_family: Chess font to draw it with. ``None`` uses the document's
            chess font, so a global font swap reaches every glyph.
        props: Direct character formatting.
    """

    piece: PieceType
    figurine_set: FigurineSet = FigurineSet.BLACK
    font_family: str | None = None
    props: RunProps = field(default_factory=RunProps)


@ir_node("nag_symbol")
@dataclass(frozen=True, slots=True, kw_only=True)
class NagSymbol(IRNode):
    """A standalone evaluation symbol such as ``!``, ``?!`` or an infinity sign.

    Stored as its NAG number rather than as text so that the symbol set is a
    rendering decision: the same document prints ``+-`` in ASCII, ``±`` in
    a Unicode edition and a dedicated macro in LaTeX.

    Attributes:
        nag: The Numeric Annotation Glyph number, ``1``-``255``.
        props: Direct character formatting.
    """

    nag: int
    props: RunProps = field(default_factory=RunProps)


@ir_node("note_ref")
@dataclass(frozen=True, slots=True, kw_only=True)
class NoteRef(IRNode):
    """A reference to a footnote or endnote.

    Attributes:
        ref: Matches the ``ref`` of a :class:`~caissa.core.model.blocks.Footnote`
            or :class:`~caissa.core.model.blocks.Endnote` in the same document.
            A reference with no matching note is an error the validator
            reports.
        marker: Explicit marker text. ``None`` lets the exporter number it.
        props: Direct character formatting.
    """

    ref: str
    marker: str | None = None
    props: RunProps = field(default_factory=RunProps)


@ir_node("inline_diagram")
@dataclass(frozen=True, slots=True, kw_only=True)
class InlineDiagram(IRNode):
    """A miniature board drawn in the middle of a line (SPEC 5.1).

    Deliberately lighter than :class:`~caissa.core.model.diagram.Diagram`: it
    has no provenance of its own beyond the node's, no caption and no number,
    because it is an illustration inside a sentence rather than a numbered
    figure.

    Attributes:
        fen: The position.
        size: Rendered size; ``None`` scales with the surrounding type.
        orientation: Which side faces the reader.
        marks: Arrows, highlights and circles drawn on the miniature.
        style: Name of a diagram style in the document stylesheet.
        alt_text: Accessible description, required by EPUB.
    """

    fen: str
    size: Measure | None = None
    orientation: Orientation = Orientation.WHITE
    marks: tuple[Mark, ...] = ()
    style: str | None = None
    alt_text: str | None = None


@ir_node("math_inline")
@dataclass(frozen=True, slots=True, kw_only=True)
class MathInline(IRNode):
    """An inline formula.

    Attributes:
        latex: The formula in LaTeX, the interchange form every exporter can
            translate from.
        mathml: A pre-built MathML rendering, when the importer had one.
        props: Direct character formatting.
    """

    latex: str
    mathml: str | None = None
    props: RunProps = field(default_factory=RunProps)


@ir_node("image_inline")
@dataclass(frozen=True, slots=True, kw_only=True)
class ImageInline(IRNode):
    """A small image inside a line, such as a logo or a scanned symbol.

    Attributes:
        resource: Key into the document's resource table.
        alt_text: Accessible description.
        width: Rendered width.
        height: Rendered height.
        baseline_shift: Vertical nudge, so the image sits on the baseline.
    """

    resource: str
    alt_text: str | None = None
    width: Measure | None = None
    height: Measure | None = None
    baseline_shift: Measure | None = None


@ir_node("anchor")
@dataclass(frozen=True, slots=True, kw_only=True)
class Anchor(IRNode):
    """A named target a link or a cross-reference can point at.

    Attributes:
        name: The anchor name, unique within the document.
        title: Human-readable label used when a cross-reference renders the
            target's name.
    """

    name: str
    title: str | None = None


@ir_node("index_entry")
@dataclass(frozen=True, slots=True, kw_only=True)
class IndexEntry(IRNode):
    """A marker that puts the surrounding position into the back-of-book index.

    Attributes:
        terms: The entry path, outermost first: ``("Aberturas", "Siciliana",
            "Najdorf")``.
        sort_key: Explicit sort key, for terms whose alphabetical position does
            not follow from their spelling.
        see_also: Cross-references to other entries.
        primary: Whether this is the principal occurrence, usually set in bold
            in the printed index.
    """

    terms: tuple[str, ...]
    sort_key: str | None = None
    see_also: tuple[str, ...] = ()
    primary: bool = False


@ir_node("line_break")
@dataclass(frozen=True, slots=True, kw_only=True)
class LineBreak(IRNode):
    """A forced line break within a paragraph."""


@ir_node("non_breaking_space")
@dataclass(frozen=True, slots=True, kw_only=True)
class NonBreakingSpace(IRNode):
    """A space that must not become a line break."""


@ir_node("space")
@dataclass(frozen=True, slots=True, kw_only=True)
class Space(IRNode):
    """A fixed-width space that carries typographic meaning.

    Attributes:
        kind: Which space.
    """

    kind: SpaceKind = SpaceKind.THIN


@ir_node("tab")
@dataclass(frozen=True, slots=True, kw_only=True)
class Tab(IRNode):
    """A tab, advancing to the next stop on the paragraph's ruler."""


@ir_node("raw_inline")
@dataclass(frozen=True, slots=True, kw_only=True)
class RawInline(IRNode):
    """Format-specific inline content passed straight through (escape hatch).

    Counted by the fidelity report: a document with much passthrough indicates
    a gap in the IR, which is the failure mode ADR-0002 warns about.

    Attributes:
        format: Target format this content belongs to, e.g. ``"latex"``.
            Exporters for other formats skip it and record a
            ``DegradationWarning``.
        text: The verbatim content.
    """

    format: str
    text: str


# --------------------------------------------------------------------------- #
# Wrappers
# --------------------------------------------------------------------------- #


@ir_node("span")
@dataclass(frozen=True, slots=True, kw_only=True)
class Span(IRNode):
    """A stretch of inlines carrying formatting but no semantics.

    This is where a character style or direct formatting attaches when the
    author meant "make this look different" rather than "this is emphasised".

    Attributes:
        content: The wrapped inlines.
        props: Character formatting applied to everything inside.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("emphasis")
@dataclass(frozen=True, slots=True, kw_only=True)
class Emphasis(IRNode):
    """Emphasised content -- semantic, usually rendered italic.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("strong")
@dataclass(frozen=True, slots=True, kw_only=True)
class Strong(IRNode):
    """Strongly emphasised content -- semantic, usually rendered bold.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("underline")
@dataclass(frozen=True, slots=True, kw_only=True)
class Underline(IRNode):
    """Underlined content.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting, including the underline style and
            colour.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("strike")
@dataclass(frozen=True, slots=True, kw_only=True)
class Strike(IRNode):
    """Struck-through content -- the mark of text decided against but kept.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("small_caps")
@dataclass(frozen=True, slots=True, kw_only=True)
class SmallCaps(IRNode):
    """Content set in small capitals.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting; ``props.small_caps`` records
            whether real or synthetic capitals were asked for.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("superscript")
@dataclass(frozen=True, slots=True, kw_only=True)
class Superscript(IRNode):
    """Raised content.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("subscript")
@dataclass(frozen=True, slots=True, kw_only=True)
class Subscript(IRNode):
    """Lowered content.

    Attributes:
        content: The wrapped inlines.
        props: Additional direct formatting.
    """

    content: tuple[Inline, ...] = ()
    props: RunProps = field(default_factory=RunProps)


@ir_node("link")
@dataclass(frozen=True, slots=True, kw_only=True)
class Link(IRNode):
    """A hyperlink or cross-reference.

    Attributes:
        target: URL, ``#anchor-name``, or resource key, depending on ``kind``.
        content: The linked inlines.
        tooltip: Hover text.
        title: Accessible title.
        kind: What the target is.
        props: Additional direct formatting.
    """

    target: str
    content: tuple[Inline, ...] = ()
    tooltip: str | None = None
    title: str | None = None
    kind: LinkKind = LinkKind.EXTERNAL
    props: RunProps = field(default_factory=RunProps)


#: Every inline node type. Exhaustive: the serialiser, the visitor and the
#: validator all rely on this union covering the whole inline vocabulary.
Inline = (
    Text
    | Move
    | PieceGlyph
    | NagSymbol
    | NoteRef
    | InlineDiagram
    | MathInline
    | ImageInline
    | Anchor
    | IndexEntry
    | LineBreak
    | NonBreakingSpace
    | Space
    | Tab
    | RawInline
    | Span
    | Emphasis
    | Strong
    | Underline
    | Strike
    | SmallCaps
    | Superscript
    | Subscript
    | Link
)

#: The inline types that wrap other inlines. Anything not listed here is a leaf.
INLINE_WRAPPERS: tuple[type[IRNode], ...] = (
    Span,
    Emphasis,
    Strong,
    Underline,
    Strike,
    SmallCaps,
    Superscript,
    Subscript,
    Link,
)

_SPACE_TEXT: dict[SpaceKind, str] = {
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


def inline_children(node: Inline) -> tuple[Inline, ...]:
    """Return the inlines a wrapper contains, or an empty tuple for a leaf.

    Args:
        node: Any inline node.

    Returns:
        Its inline children.
    """
    if isinstance(
        node,
        (Span, Emphasis, Strong, Underline, Strike, SmallCaps, Superscript, Subscript, Link),
    ):
        return node.content
    return ()


def plain_text(nodes: tuple[Inline, ...]) -> str:
    """Flatten inlines to their reading text.

    Used for search indexing, alt-text fallbacks and diff summaries. Moves
    render as canonical SAN, not as their display form, because this is the
    text a reader searches for.

    Args:
        nodes: The inlines to flatten.

    Returns:
        The concatenated reading text.
    """
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.content)
        elif isinstance(node, Move):
            parts.append(node.san)
        elif isinstance(node, PieceGlyph):
            # The canonical English letter, for the same reason a move renders
            # as canonical SAN: a figurine ``N`` before ``f3`` must be found by
            # the reader who searches "Nf3".  Before this, the glyph vanished
            # from the reading text and "Nf3" indexed as "f3" (found by F2).
            parts.append(piece_letter(node.piece))
        elif isinstance(node, MathInline):
            parts.append(node.latex)
        elif isinstance(node, LineBreak):
            parts.append("\n")
        elif isinstance(node, Tab):
            parts.append("\t")
        elif isinstance(node, NonBreakingSpace):
            parts.append(" ")
        elif isinstance(node, Space):
            parts.append(_SPACE_TEXT[node.kind])
        else:
            parts.append(plain_text(inline_children(node)))
    return "".join(parts)
