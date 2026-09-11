"""Named, inheritable styles and the cascade that resolves them.

Word and InDesign both work this way and so does every professional workflow:
formatting lives in a *named style*, a style may be *based on* another, and a
node may add *direct formatting* on top. Exporting real styles rather than
flattened direct formatting is what makes a DOCX show up correctly in Word's
style panel and an EPUB restyleable by the reader.

Resolution order
----------------

For a run, the effective properties are built by overlaying four layers, each
winning over the one before it:

1. **document defaults** -- :attr:`StyleSheet.default_run`;
2. **named style**, walking the ``based_on`` chain from the *root* ancestor down
   to the named style itself, so a child style overrides its parent;
3. **inherited** -- properties handed down by the enclosing context: the
   paragraph's run defaults, then each enclosing inline wrapper;
4. **direct formatting** -- the ``props`` on the node itself.

Paragraphs resolve the same way, and additionally contribute their run layer to
the runs inside them. Within every layer, a field left unspecified (``None``, or
an empty tuple) falls through; there is no "explicitly inherit" sentinel,
because every source format means the same thing by saying nothing.

Cycles in a ``based_on`` chain raise :class:`StyleError` rather than looping.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from caissa.core.model.diagram import DiagramStyle
from caissa.core.model.props import (
    Borders,
    Color,
    ListMarkerAlignment,
    Measure,
    Padding,
    ParagraphProps,
    RunProps,
)
from caissa.core.model.registry import ir_node

__all__ = [
    "CharacterStyle",
    "DiagramStyleDef",
    "ListStyle",
    "ListStyleLevel",
    "ParagraphStyle",
    "ResolvedProps",
    "StyleError",
    "StyleSheet",
    "TableStyle",
    "resolve_paragraph_props",
    "resolve_run_props",
    "style_chain",
]

_MAX_STYLE_DEPTH = 32


class StyleError(ValueError):
    """Raised when a style cannot be resolved: unknown name or cyclic ``based_on``."""


@ir_node("character_style")
@dataclass(frozen=True, slots=True, kw_only=True)
class CharacterStyle:
    """A named set of character-level properties.

    Attributes:
        name: Machine name, unique among character styles; this is what a
            ``RunProps.style`` refers to.
        display_name: Human-readable name shown in an editor's style panel.
        based_on: Name of the style this one inherits from.
        props: The properties the style contributes.
        hidden: Whether the style is hidden from the user interface.
        locked: Whether the user may edit it.
        priority: Sort order in a style panel.
        description: What the style is for.
    """

    name: str
    display_name: str | None = None
    based_on: str | None = None
    props: RunProps = field(default_factory=RunProps)
    hidden: bool = False
    locked: bool = False
    priority: int = 0
    description: str | None = None


@ir_node("paragraph_style")
@dataclass(frozen=True, slots=True, kw_only=True)
class ParagraphStyle:
    """A named set of paragraph-level properties, plus the runs inside.

    Attributes:
        name: Machine name, unique among paragraph styles; this is what a
            ``ParagraphProps.style`` refers to.
        display_name: Human-readable name.
        based_on: Name of the style this one inherits from.
        next_style: Style automatically applied to the paragraph the user
            creates after this one -- how "Heading" is followed by "Body".
        paragraph: Paragraph-level properties.
        run: Character-level properties applied to every run in the paragraph.
        outline_level: Depth in the document outline; drives PDF bookmarks and
            the EPUB navigation document.
        hidden: Whether the style is hidden from the user interface.
        locked: Whether the user may edit it.
        priority: Sort order in a style panel.
        description: What the style is for.
    """

    name: str
    display_name: str | None = None
    based_on: str | None = None
    next_style: str | None = None
    paragraph: ParagraphProps = field(default_factory=ParagraphProps)
    run: RunProps = field(default_factory=RunProps)
    outline_level: int | None = None
    hidden: bool = False
    locked: bool = False
    priority: int = 0
    description: str | None = None


@ir_node("table_style")
@dataclass(frozen=True, slots=True, kw_only=True)
class TableStyle:
    """A named set of table properties.

    Attributes:
        name: Machine name, unique among table styles.
        display_name: Human-readable name.
        based_on: Name of the style this one inherits from.
        borders: Table and inside borders.
        cell_padding: Default cell padding.
        header_run: Character properties of header cells.
        header_shading: Background of header cells.
        body_run: Character properties of body cells.
        band_size: Number of rows in a banding stripe; ``0`` disables banding.
        band_shading: Background of the shaded stripe.
        first_column_run: Character properties of the first column, for the
            move-number column of an opening table.
        description: What the style is for.
    """

    name: str
    display_name: str | None = None
    based_on: str | None = None
    borders: Borders | None = None
    cell_padding: Padding | None = None
    header_run: RunProps = field(default_factory=RunProps)
    header_shading: Color | None = None
    body_run: RunProps = field(default_factory=RunProps)
    band_size: int = 0
    band_shading: Color | None = None
    first_column_run: RunProps = field(default_factory=RunProps)
    description: str | None = None


@ir_node("list_style_level")
@dataclass(frozen=True, slots=True, kw_only=True)
class ListStyleLevel:
    """One nesting level of a numbering definition.

    Attributes:
        level: Zero-based depth.
        marker_style: How the marker is drawn.
        marker_text: Template for the marker, with ``%1``-style placeholders
            for the counters of this and enclosing levels, exactly as OOXML
            numbering does.
        start: First value of the counter.
        indent: Indent of the item body.
        hanging: Distance the marker hangs left of the body.
        alignment: Alignment of the marker within its own slot.
        props: Paragraph properties applied to items at this level.
        run_props: Character properties applied to the marker itself.
        restart_after_level: Restart this counter whenever the counter of that
            level advances; ``None`` never restarts.
    """

    level: int = 0
    marker_style: str = "decimal"
    marker_text: str | None = None
    start: int = 1
    indent: Measure | None = None
    hanging: Measure | None = None
    alignment: ListMarkerAlignment = ListMarkerAlignment.LEFT
    props: ParagraphProps = field(default_factory=ParagraphProps)
    run_props: RunProps = field(default_factory=RunProps)
    restart_after_level: int | None = None


@ir_node("list_style")
@dataclass(frozen=True, slots=True, kw_only=True)
class ListStyle:
    """A named numbering definition: the counters a list or heading tree uses.

    Attributes:
        name: Machine name, unique among list styles; this is what a
            ``NumberingRef.definition`` refers to.
        display_name: Human-readable name.
        based_on: Name of the definition this one inherits from.
        levels: Per-level settings, ordered by ``level``.
        description: What the definition is for.
    """

    name: str
    display_name: str | None = None
    based_on: str | None = None
    levels: tuple[ListStyleLevel, ...] = ()
    description: str | None = None

    def level(self, index: int) -> ListStyleLevel | None:
        """Return the settings for one nesting level.

        Args:
            index: Zero-based depth.

        Returns:
            The level, or ``None`` when the definition does not reach that
            deep.
        """
        for entry in self.levels:
            if entry.level == index:
                return entry
        return None


@ir_node("diagram_style_def")
@dataclass(frozen=True, slots=True, kw_only=True)
class DiagramStyleDef:
    """A named diagram style, so a whole book restyles in one edit.

    Attributes:
        name: Machine name, unique among diagram styles; this is what a
            ``DiagramStyle.name`` and an ``InlineDiagram.style`` refer to.
        display_name: Human-readable name.
        based_on: Name of the style this one inherits from.
        style: The properties the style contributes.
        description: What the style is for.
    """

    name: str
    display_name: str | None = None
    based_on: str | None = None
    style: DiagramStyle = field(default_factory=DiagramStyle)
    description: str | None = None


@ir_node("style_sheet")
@dataclass(frozen=True, slots=True, kw_only=True)
class StyleSheet:
    """Every named style in a document, plus the document-wide defaults.

    Attributes:
        default_paragraph: Paragraph properties every paragraph starts from.
        default_run: Character properties every run starts from.
        paragraph_styles: Named paragraph styles.
        character_styles: Named character styles.
        table_styles: Named table styles.
        list_styles: Numbering definitions.
        diagram_styles: Named diagram styles.
        default_paragraph_style: Name of the style new paragraphs get.
        default_character_style: Name of the style new runs get.
        default_diagram_style: Name of the style new diagrams get.
    """

    default_paragraph: ParagraphProps = field(default_factory=ParagraphProps)
    default_run: RunProps = field(default_factory=RunProps)
    paragraph_styles: tuple[ParagraphStyle, ...] = ()
    character_styles: tuple[CharacterStyle, ...] = ()
    table_styles: tuple[TableStyle, ...] = ()
    list_styles: tuple[ListStyle, ...] = ()
    diagram_styles: tuple[DiagramStyleDef, ...] = ()
    default_paragraph_style: str | None = None
    default_character_style: str | None = None
    default_diagram_style: str | None = None

    def paragraph_style(self, name: str) -> ParagraphStyle | None:
        """Look up a paragraph style by name.

        Args:
            name: The style's machine name.

        Returns:
            The style, or ``None`` when it is not defined.
        """
        return next((s for s in self.paragraph_styles if s.name == name), None)

    def character_style(self, name: str) -> CharacterStyle | None:
        """Look up a character style by name.

        Args:
            name: The style's machine name.

        Returns:
            The style, or ``None`` when it is not defined.
        """
        return next((s for s in self.character_styles if s.name == name), None)

    def table_style(self, name: str) -> TableStyle | None:
        """Look up a table style by name.

        Args:
            name: The style's machine name.

        Returns:
            The style, or ``None`` when it is not defined.
        """
        return next((s for s in self.table_styles if s.name == name), None)

    def list_style(self, name: str) -> ListStyle | None:
        """Look up a numbering definition by name.

        Args:
            name: The definition's machine name.

        Returns:
            The definition, or ``None`` when it is not defined.
        """
        return next((s for s in self.list_styles if s.name == name), None)

    def diagram_style(self, name: str) -> DiagramStyleDef | None:
        """Look up a diagram style by name.

        Args:
            name: The style's machine name.

        Returns:
            The style, or ``None`` when it is not defined.
        """
        return next((s for s in self.diagram_styles if s.name == name), None)

    def known_names(self) -> frozenset[str]:
        """Return every style name defined anywhere in the sheet.

        Returns:
            The union of all style names, used by the validator to report
            unresolved references.
        """
        names: set[str] = set()
        names.update(style.name for style in self.paragraph_styles)
        names.update(style.name for style in self.character_styles)
        names.update(style.name for style in self.table_styles)
        names.update(style.name for style in self.list_styles)
        names.update(style.name for style in self.diagram_styles)
        return frozenset(names)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedProps:
    """The outcome of resolving a paragraph: its own properties and its runs'.

    Attributes:
        paragraph: Effective paragraph properties.
        run: Effective character properties every run inside starts from.
    """

    paragraph: ParagraphProps
    run: RunProps


def style_chain(
    stylesheet: StyleSheet,
    name: str,
    kind: str,
    *,
    strict: bool = False,
) -> tuple[str, ...]:
    """Return a style's ``based_on`` ancestry, root first.

    Args:
        stylesheet: The sheet to resolve against.
        name: Name of the style to start from.
        kind: Which family to look in: ``"paragraph"``, ``"character"``,
            ``"table"``, ``"list"`` or ``"diagram"``.
        strict: Raise when a name in the chain is not defined, instead of
            stopping there.

    Returns:
        Style names from the root ancestor down to ``name`` itself. A name that
        is not defined contributes nothing and ends the walk.

    Raises:
        StyleError: On a cyclic ``based_on`` chain, on an unknown ``kind``, or
            on an undefined name when ``strict`` is set.
    """
    lookup = _CHAIN_LOOKUPS.get(kind)
    if lookup is None:
        options = ", ".join(sorted(_CHAIN_LOOKUPS))
        msg = f"familia de estilo desconhecida: {kind!r}. Validas: {options}."
        raise StyleError(msg)

    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = name
    while current is not None:
        if current in seen:
            path = " -> ".join([*chain, current])
            msg = f"ciclo em 'based_on' de estilo: {path}"
            raise StyleError(msg)
        seen.add(current)
        parent = lookup(stylesheet, current)
        if isinstance(parent, _Missing):
            if strict:
                msg = f"estilo {kind} nao definido: {current!r}"
                raise StyleError(msg)
            break
        chain.append(current)
        if len(chain) > _MAX_STYLE_DEPTH:
            msg = f"cadeia de estilos excede {_MAX_STYLE_DEPTH} niveis a partir de {name!r}"
            raise StyleError(msg)
        current = parent
    chain.reverse()
    return tuple(chain)


def resolve_run_props(
    stylesheet: StyleSheet,
    direct: RunProps | None = None,
    *,
    inherited: RunProps | None = None,
    style_name: str | None = None,
    strict: bool = False,
) -> RunProps:
    """Resolve character properties through the full cascade.

    Layers, each overriding the previous: document defaults, the named style's
    ``based_on`` chain from root to leaf, the inherited context, then direct
    formatting.

    Args:
        stylesheet: The sheet to resolve against.
        direct: Direct formatting on the node. Its ``style`` field names the
            character style unless ``style_name`` overrides it.
        inherited: Properties handed down by the enclosing context.
        style_name: Character style to apply, overriding ``direct.style``.
        strict: Raise on an unknown style name instead of ignoring it.

    Returns:
        The effective properties. Fields still ``None`` were never specified
        anywhere and mean "use the output format's own default".

    Raises:
        StyleError: On a cyclic chain, or on an unknown name when ``strict``.
    """
    effective_name = style_name if style_name is not None else _style_of(direct)
    result = stylesheet.default_run
    if effective_name:
        for link in style_chain(stylesheet, effective_name, "character", strict=strict):
            style = stylesheet.character_style(link)
            if style is not None:
                result = result.merged_with(style.props)
    if inherited is not None:
        result = result.merged_with(inherited)
    if direct is not None:
        result = result.merged_with(direct)
    return result


def resolve_paragraph_props(
    stylesheet: StyleSheet,
    direct: ParagraphProps | None = None,
    *,
    inherited: ParagraphProps | None = None,
    inherited_run: RunProps | None = None,
    style_name: str | None = None,
    strict: bool = False,
) -> ResolvedProps:
    """Resolve paragraph properties, and the run properties they imply.

    The paragraph layer and the run layer are resolved in lockstep so that a
    paragraph style's ``run`` block reaches the runs inside it, in the right
    place in the cascade -- below the paragraph's own ``default_run`` and below
    each run's direct formatting.

    Args:
        stylesheet: The sheet to resolve against.
        direct: Direct paragraph formatting. Its ``style`` field names the
            paragraph style unless ``style_name`` overrides it.
        inherited: Paragraph properties handed down by an enclosing container.
        inherited_run: Character properties handed down by an enclosing
            container.
        style_name: Paragraph style to apply, overriding ``direct.style``.
        strict: Raise on an unknown style name instead of ignoring it.

    Returns:
        The effective paragraph properties and the run baseline for its runs.

    Raises:
        StyleError: On a cyclic chain, or on an unknown name when ``strict``.
    """
    effective_name = style_name if style_name is not None else _style_of(direct)
    paragraph = stylesheet.default_paragraph
    run = stylesheet.default_run
    if effective_name:
        for link in style_chain(stylesheet, effective_name, "paragraph", strict=strict):
            style = stylesheet.paragraph_style(link)
            if style is not None:
                paragraph = paragraph.merged_with(style.paragraph)
                run = run.merged_with(style.run)
    if inherited is not None:
        paragraph = paragraph.merged_with(inherited)
    if inherited_run is not None:
        run = run.merged_with(inherited_run)
    if direct is not None:
        paragraph = paragraph.merged_with(direct)
    if paragraph.default_run is not None:
        run = run.merged_with(paragraph.default_run)
    return ResolvedProps(paragraph=paragraph, run=run)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


class _Missing:
    """Sentinel for "this style name is not defined in the sheet"."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a readable sentinel name."""
        return "<missing style>"


_MISSING = _Missing()

#: Signature of the per-family ``based_on`` accessors below.
_ParentLookup = Callable[[StyleSheet, str], "str | None | _Missing"]


def _style_of(props: RunProps | ParagraphProps | None) -> str | None:
    """Return the style name a property record refers to.

    Args:
        props: A property record, or ``None``.

    Returns:
        The referenced style name, or ``None``.
    """
    return None if props is None else props.style


def _paragraph_parent(sheet: StyleSheet, name: str) -> str | None | _Missing:
    """Return a paragraph style's parent name, or the missing sentinel.

    Args:
        sheet: The stylesheet.
        name: The style name.

    Returns:
        The parent name, ``None`` at the root, or ``_MISSING``.
    """
    style = sheet.paragraph_style(name)
    return _MISSING if style is None else style.based_on


def _character_parent(sheet: StyleSheet, name: str) -> str | None | _Missing:
    """Return a character style's parent name, or the missing sentinel.

    Args:
        sheet: The stylesheet.
        name: The style name.

    Returns:
        The parent name, ``None`` at the root, or ``_MISSING``.
    """
    style = sheet.character_style(name)
    return _MISSING if style is None else style.based_on


def _table_parent(sheet: StyleSheet, name: str) -> str | None | _Missing:
    """Return a table style's parent name, or the missing sentinel.

    Args:
        sheet: The stylesheet.
        name: The style name.

    Returns:
        The parent name, ``None`` at the root, or ``_MISSING``.
    """
    style = sheet.table_style(name)
    return _MISSING if style is None else style.based_on


def _list_parent(sheet: StyleSheet, name: str) -> str | None | _Missing:
    """Return a numbering definition's parent name, or the missing sentinel.

    Args:
        sheet: The stylesheet.
        name: The definition name.

    Returns:
        The parent name, ``None`` at the root, or ``_MISSING``.
    """
    style = sheet.list_style(name)
    return _MISSING if style is None else style.based_on


def _diagram_parent(sheet: StyleSheet, name: str) -> str | None | _Missing:
    """Return a diagram style's parent name, or the missing sentinel.

    Args:
        sheet: The stylesheet.
        name: The style name.

    Returns:
        The parent name, ``None`` at the root, or ``_MISSING``.
    """
    style = sheet.diagram_style(name)
    return _MISSING if style is None else style.based_on


_CHAIN_LOOKUPS: dict[str, _ParentLookup] = {
    "paragraph": _paragraph_parent,
    "character": _character_parent,
    "table": _table_parent,
    "list": _list_parent,
    "diagram": _diagram_parent,
}
