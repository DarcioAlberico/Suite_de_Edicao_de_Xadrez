"""SPEC 5.1 transcribed into assertions -- the node vocabulary, item by item.

ADR-0002 says the biggest threat to this project is an IR that turns out not to
be expressive enough. The defence is to write the SPEC's own list down as data
and assert against it, so "the IR expresses SPEC 5.1" stops being a claim in a
report and becomes something the suite re-checks on every run.

Each entry names the SPEC bullet, the class that implements it, and the fields
the bullet explicitly asks for. A field the SPEC names and the class does not
have is a gap, and this module is where it surfaces.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from generators import construct_minimal

from caissa.core.model import (
    Anchor,
    Block,
    Callout,
    CodeBlock,
    Diagram,
    Document,
    DocumentMetadata,
    Emphasis,
    Endnote,
    Figure,
    Footnote,
    GameScore,
    Group,
    Heading,
    ImageBlock,
    ImageInline,
    IndexEntry,
    Inline,
    InlineDiagram,
    IRNode,
    LineBreak,
    Link,
    ListBlock,
    ListItem,
    ListKind,
    MathBlock,
    MathInline,
    Move,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    PageBreak,
    Paragraph,
    PieceGlyph,
    Quote,
    RawInline,
    RawPassthrough,
    Resource,
    ResourceKind,
    SectionBreak,
    SmallCaps,
    Space,
    Span,
    Strike,
    Strong,
    StyleSheet,
    Subscript,
    Superscript,
    Tab,
    Table,
    TableOfContents,
    Text,
    ThematicBreak,
    Underline,
    node_from_payload,
    node_to_payload,
)
from caissa.core.model.reflect import union_members

# --------------------------------------------------------------------------- #
# SPEC 5.1, transcribed
# --------------------------------------------------------------------------- #

#: ``(SPEC bullet, class, fields the bullet names)``
SPEC_BLOCKS: tuple[tuple[str, type, tuple[str, ...]], ...] = (
    ("Heading(level 1-6, inlines, numbering)", Heading, ("level", "content", "numbering")),
    (
        "Paragraph(inlines, style, alignment, indents, spacing)",
        Paragraph,
        ("content", "props"),
    ),
    (
        "List(ordered|unordered|definition, items, marker style)",
        ListBlock,
        ("kind", "items", "marker_style"),
    ),
    (
        "Table(rows, cols, spans, header repeat, borders, alignment)",
        Table,
        ("rows", "columns", "repeat_header", "borders", "alignment"),
    ),
    (
        "Figure(content, caption, number, placement)",
        Figure,
        ("content", "caption", "number", "placement"),
    ),
    ("Diagram (5.3)", Diagram, ("fen", "marks", "recognition")),
    ("GameScore (5.4)", GameScore, ("headers", "children")),
    ("CodeBlock(language, text)", CodeBlock, ("language", "text")),
    ("Math(latex, display|inline)", MathBlock, ("latex", "display")),
    ("Footnote(ref, content)", Footnote, ("ref", "content")),
    ("Endnote(ref, content)", Endnote, ("ref", "content")),
    ("PageBreak", PageBreak, ()),
    (
        "SectionBreak(columns, page geometry)",
        SectionBreak,
        ("columns", "geometry"),
    ),
    ("Quote", Quote, ("content",)),
    ("Callout(kind, content)", Callout, ("kind", "content")),
    ("RawPassthrough(format, text)", RawPassthrough, ("format", "text")),
)

SPEC_INLINES: tuple[tuple[str, type, tuple[str, ...]], ...] = (
    ("Text(string, run properties)", Text, ("content", "props")),
    ("Emphasis", Emphasis, ("content",)),
    ("Strong", Strong, ("content",)),
    ("Underline", Underline, ("content",)),
    ("Strike", Strike, ("content",)),
    ("SmallCaps", SmallCaps, ("content",)),
    ("Super", Superscript, ("content",)),
    ("Sub", Subscript, ("content",)),
    ("Move (5.5)", Move, ("san", "ply", "position_before", "nags", "render", "language")),
    ("PieceGlyph(piece, style)", PieceGlyph, ("piece", "figurine_set")),
    ("Link(target, tooltip)", Link, ("target", "tooltip")),
    ("NoteRef(id)", NoteRef, ("ref",)),
    ("InlineDiagram(fen, size)", InlineDiagram, ("fen", "size")),
    ("MathInline(latex)", MathInline, ("latex",)),
    ("LineBreak", LineBreak, ()),
    ("NonBreakingSpace", NonBreakingSpace, ()),
    ("Tab", Tab, ()),
)

#: Node types the IR adds beyond the SPEC list, each with the reason it exists.
BEYOND_SPEC: dict[type, str] = {
    Span: "a styled run of inlines with no semantic meaning of its own",
    NagSymbol: "a standalone evaluation glyph, stored as its NAG number",
    Anchor: "a link destination, needed by NoteRef and internal Link",
    IndexEntry: "an index term, needed by the back-matter index",
    ImageInline: "an image in the middle of a line",
    RawInline: "the inline half of the RawPassthrough escape hatch",
    Space: "the typographic space family (thin, hair, en, em, figure, ...)",
    ImageBlock: "a block-level image, the non-chess counterpart of Diagram",
    Group: "a semantic container: chapter, exercise set, diagram grid",
    ThematicBreak: "the ornament between scenes",
    TableOfContents: "a generated contents list",
    ListItem: "one entry of a List, addressable in its own right",
}


# --------------------------------------------------------------------------- #
# Every SPEC node exists, constructs and round-trips
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("bullet", "cls", "required"),
    SPEC_BLOCKS,
    ids=[bullet.split("(")[0].strip() for bullet, _cls, _fields in SPEC_BLOCKS],
)
def test_every_spec_block_exists_with_the_fields_the_spec_names(bullet, cls, required):
    declared = {item.name for item in fields(cls)}
    assert set(required) <= declared, f"{bullet}: missing {sorted(set(required) - declared)}"
    instance = construct_minimal(cls)
    assert node_from_payload(node_to_payload(instance), cls) == instance


@pytest.mark.parametrize(
    ("bullet", "cls", "required"),
    SPEC_INLINES,
    ids=[bullet.split("(")[0].strip() for bullet, _cls, _fields in SPEC_INLINES],
)
def test_every_spec_inline_exists_with_the_fields_the_spec_names(bullet, cls, required):
    declared = {item.name for item in fields(cls)}
    assert set(required) <= declared, f"{bullet}: missing {sorted(set(required) - declared)}"
    instance = construct_minimal(cls)
    assert node_from_payload(node_to_payload(instance), cls) == instance


# --------------------------------------------------------------------------- #
# The union types actually admit them
# --------------------------------------------------------------------------- #


def test_the_block_union_admits_every_spec_block():
    members = set(union_members(Block))
    for bullet, cls, _required in SPEC_BLOCKS:
        assert cls in members, f"{bullet}: {cls.__name__} is not a Block"


def test_the_inline_union_admits_every_spec_inline():
    members = set(union_members(Inline))
    for bullet, cls, _required in SPEC_INLINES:
        assert cls in members, f"{bullet}: {cls.__name__} is not an Inline"


def test_the_two_unions_do_not_overlap():
    """A node is a block or an inline, never both: exporters switch on it."""
    assert set(union_members(Block)) & set(union_members(Inline)) == set()


def test_every_union_member_is_a_registered_node():
    for member in (*union_members(Block), *union_members(Inline)):
        assert isinstance(member, type), member
        assert issubclass(member, IRNode), member


def test_every_extra_node_type_is_accounted_for():
    """Nothing sits in Block or Inline without a stated reason for existing."""
    from_spec = {cls for _bullet, cls, _required in (*SPEC_BLOCKS, *SPEC_INLINES)}
    declared = set(union_members(Block)) | set(union_members(Inline))
    unexplained = declared - from_spec - set(BEYOND_SPEC)
    assert not unexplained, f"undocumented node types: {sorted(c.__name__ for c in unexplained)}"


# --------------------------------------------------------------------------- #
# The three list kinds and the document skeleton
# --------------------------------------------------------------------------- #


def test_the_spec_names_three_list_kinds_and_the_ir_has_exactly_those():
    assert {kind.value for kind in ListKind} == {"ordered", "unordered", "definition"}


def test_the_document_has_the_four_parts_the_spec_draws():
    declared = {item.name for item in fields(Document)}
    assert {"metadata", "styles", "resources", "body"} <= declared
    assert isinstance(Document().metadata, DocumentMetadata)
    assert isinstance(Document().styles, StyleSheet)
    assert Document().body == ()


def test_document_metadata_carries_every_field_the_spec_lists():
    """SPEC 5.1: "title, authors, language, isbn, publisher, ..."."""
    declared = {item.name for item in fields(DocumentMetadata)}
    assert {"title", "contributors", "language", "isbn", "publisher"} <= declared
    metadata = DocumentMetadata(title="x")
    assert metadata.authors == ()


def test_resources_cover_the_three_kinds_the_spec_names():
    """SPEC 5.1: "fontes embutidas, imagens, folhas de estilo"."""
    values = {kind.value for kind in ResourceKind}
    assert {"font", "image", "stylesheet"} <= values


def test_a_resource_describes_an_embedded_font_completely_enough_to_subset():
    resource = Resource(
        key="merida",
        kind=ResourceKind.FONT,
        path="fonts/Merida.otf",
        media_type="font/otf",
        family="Merida",
        weight=400,
        italic=False,
        embed=True,
        subset=True,
        license_note="licenca do editor",
    )
    assert node_from_payload(node_to_payload(resource), Resource) == resource


# --------------------------------------------------------------------------- #
# The escape hatch, and the ADR-0002 warning attached to it
# --------------------------------------------------------------------------- #


def test_the_escape_hatch_exists_at_both_levels():
    """ADR-0002: RawPassthrough exists, but heavy use signals a gap in the IR."""
    block = RawPassthrough(format="latex", text=r"\clearpage")
    inline = RawInline(format="html", text="<wbr>")
    assert node_from_payload(node_to_payload(block), RawPassthrough) == block
    assert node_from_payload(node_to_payload(inline), RawInline) == inline


def test_passthrough_use_is_measurable():
    """ADR-0002 says its use is *measured*; ``find`` is how."""
    from caissa.core.model import find

    document = Document(
        body=(
            Paragraph(content=(Text(content="normal"),)),
            RawPassthrough(format="latex", text=r"\clearpage"),
            Paragraph(content=(RawInline(format="html", text="<wbr>"),)),
        ),
    )
    block_count = len(list(find(document, "raw_passthrough")))
    inline_count = len(list(find(document, "raw_inline")))
    assert (block_count, inline_count) == (1, 1)


# --------------------------------------------------------------------------- #
# Immutability, the SPEC 5 preamble's first claim
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("cls", "field_name", "value"),
    [
        (Text, "content", "outro"),
        (Heading, "level", 3),
        (Diagram, "fen", "8/8/8/8/8/8/8/8 w - - 0 1"),
    ],
)
def test_every_node_is_frozen(cls, field_name, value):
    """SPEC 5: "uma arvore imutavel-por-versao"."""
    instance = construct_minimal(cls)
    with pytest.raises((AttributeError, TypeError)):
        setattr(instance, field_name, value)


def test_every_node_is_slotted_so_a_hundred_thousand_of_them_fit_in_ram():
    for _bullet, cls, _required in (*SPEC_BLOCKS, *SPEC_INLINES):
        assert not hasattr(construct_minimal(cls), "__dict__"), cls.__name__


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #


#: Every module of the package, by name. ``validate`` and friends must be
#: imported this way: the package re-exports a *function* under that name, which
#: shadows the module in a plain ``from ... import`` .
MODEL_MODULES = (
    "base",
    "blocks",
    "degradation",
    "diagram",
    "diff",
    "document",
    "game",
    "ids",
    "inline",
    "marks",
    "migrations",
    "props",
    "provenance",
    "serialize",
    "styles",
    "validate",
    "visitor",
)

#: Names a module declares public but the package deliberately keeps internal.
INTERNAL_NAMES = frozenset(
    {
        # The codec's primitives; callers use dumps/loads/node_to_payload.
        "GENERATOR",
        "PAYLOAD_KIND",
        "TYPE_KEY",
        "decode_value",
        "encode_value",
        # A signature alias, useful only to someone writing a migration.
        "MigrationFn",
        # Chess vocabulary that belongs to caissa.core.chess, not to the model.
        "iter_mainline",
        "iter_move_nodes",
        "SQUARE_NAMES",
        "is_square_name",
        "square_index",
        "square_name",
    }
)


def test_the_model_package_re_exports_every_public_name_of_its_modules():
    """Anything a module declares public must be reachable from the package."""
    import importlib

    import caissa.core.model as package

    for name in MODEL_MODULES:
        module = importlib.import_module(f"caissa.core.model.{name}")
        missing = set(module.__all__) - set(package.__all__) - INTERNAL_NAMES
        assert not missing, f"{module.__name__} exports {sorted(missing)} unreachably"


def test_the_chess_package_re_exports_every_public_name_of_its_modules():
    import caissa.core.chess as package
    from caissa.core.chess import fen, notation_tables

    for module in (fen, notation_tables):
        missing = set(module.__all__) - set(package.__all__)
        assert not missing, f"{module.__name__} exports {sorted(missing)} unreachably"


def test_every_name_in_all_actually_resolves():
    import caissa.core.chess as chess_package
    import caissa.core.model as model_package

    for package in (model_package, chess_package):
        for name in package.__all__:
            assert hasattr(package, name), f"{package.__name__}.{name} is missing"


def test_every_node_is_hashable_by_identity_and_comparable_by_value():
    first = Text(content="x")
    same_value = Text(id=first.id, content="x")
    assert first == same_value
    assert hash(first) == hash(same_value)
    assert Text(content="x") != Text(content="x"), "different ids, different nodes"
