"""Node behaviour: the projections and helpers built on top of the vocabulary.

The round-trip corpus proves the nodes *survive*. This module proves they
*mean* something: that a move projects to a move number and a colour, that
flattening a paragraph to reading text gives a searcher what they typed, that a
table knows how wide it is, and that walking block containers reaches the blocks
inside them.

``plain_text`` deserves the attention it gets here. It is what feeds search
(SPEC 9) and what fills an alt-text fallback, and it deliberately renders a move
as canonical SAN rather than as its display form -- a Brazilian reader searching
for "Cf3" and an English one searching for "Nf3" must both find the same move,
which only works if the index holds the canonical form.
"""

from __future__ import annotations

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.chess.notation_tables import (
    FigurineSet,
    MoveRenderStyle,
    PieceType,
    render_san,
)
from caissa.core.model import (
    Anchor,
    Callout,
    CalloutKind,
    CodeBlock,
    Contributor,
    ContributorRole,
    Diagram,
    Document,
    DocumentMetadata,
    DocumentSettings,
    Emphasis,
    Endnote,
    Figure,
    Footnote,
    GameHeaders,
    Group,
    GroupRole,
    Heading,
    ImageInline,
    IndexEntry,
    InlineDiagram,
    LineBreak,
    Link,
    ListBlock,
    ListItem,
    MathInline,
    MetadataEntry,
    Move,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    Paragraph,
    PieceGlyph,
    Quote,
    RawInline,
    Resource,
    ResourceKind,
    SmallCaps,
    Space,
    SpaceKind,
    Span,
    Strike,
    Strong,
    Subscript,
    Superscript,
    Tab,
    Table,
    TableCell,
    TableColumn,
    TableRow,
    Text,
    Underline,
    block_children,
    inline_children,
    plain_text,
)

# --------------------------------------------------------------------------- #
# Move -- SPEC 5.5's "a move is not text"
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("ply", "number", "is_black"),
    [(1, 1, False), (2, 1, True), (3, 2, False), (4, 2, True), (83, 42, False)],
)
def test_a_move_projects_its_ply_to_a_number_and_a_colour(ply, number, is_black):
    move = Move(san="Nf3", ply=ply)
    assert move.move_number == number
    assert move.is_black_move is is_black


def test_the_same_move_renders_in_every_language_from_one_ir():
    """SPEC 5.5's whole argument, in five lines."""
    move = Move(san="Nf3", ply=5)
    assert render_san(move.san, language="pt") == "Cf3"
    assert render_san(move.san, language="de") == "Sf3"
    assert render_san(move.san, language="ru") == "Кf3"
    assert render_san(move.san, style=MoveRenderStyle.FIGURINE) == "♞f3"
    assert move.san == "Nf3", "the stored value never changed"


def test_a_move_carries_its_own_rendering_preferences():
    move = Move(
        san="Nf3",
        language="pt",
        render=MoveRenderStyle.BOTH,
        figurine_set=FigurineSet.WHITE,
        show_move_number=True,
        move_number_text="3.",
        uci="g1f3",
    )
    rendered = render_san(
        move.san,
        language=move.language,
        style=move.render,
        figurine_set=move.figurine_set,
    )
    assert rendered == "♘f3 (Cf3)"
    assert move.move_number_text == "3."


def test_a_piece_glyph_is_a_piece_plus_a_glyph_set_not_a_character():
    glyph = PieceGlyph(piece=PieceType.KNIGHT, figurine_set=FigurineSet.BLACK)
    assert glyph.piece is PieceType.KNIGHT
    assert glyph.figurine_set is FigurineSet.BLACK


# --------------------------------------------------------------------------- #
# plain_text
# --------------------------------------------------------------------------- #


def test_plain_text_concatenates_runs():
    assert plain_text((Text(content="uma "), Text(content="frase"))) == "uma frase"


def test_plain_text_renders_a_move_as_canonical_san():
    """A reader searching "Nf3" and one searching "Cf3" must find the same move."""
    inlines = (Text(content="depois de "), Move(san="Nf3", language="pt"))
    assert plain_text(inlines) == "depois de Nf3"


def test_plain_text_descends_through_every_wrapper():
    nested = Span(
        content=(
            Emphasis(content=(Strong(content=(Text(content="fundo"),)),)),
            Underline(content=(Text(content=" e "),)),
            Strike(content=(SmallCaps(content=(Text(content="mais"),)),)),
        ),
    )
    assert plain_text((nested,)) == "fundo e mais"


def test_plain_text_descends_through_a_link():
    link = Link(target="https://exemplo.org", content=(Text(content="clique"),))
    assert plain_text((link,)) == "clique"


def test_plain_text_descends_through_super_and_subscript():
    inlines = (
        Text(content="H"),
        Subscript(content=(Text(content="2"),)),
        Text(content="O e x"),
        Superscript(content=(Text(content="2"),)),
    )
    assert plain_text(inlines) == "H2O e x2"


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        (LineBreak(), "\n"),
        (Tab(), "\t"),
        (NonBreakingSpace(), " "),
        (MathInline(latex=r"\frac12"), r"\frac12"),
    ],
)
def test_plain_text_of_the_typographic_leaves(node, expected):
    assert plain_text((node,)) == expected


@pytest.mark.parametrize("kind", list(SpaceKind))
def test_every_space_kind_flattens_to_exactly_one_character(kind):
    text = plain_text((Space(kind=kind),))
    assert len(text) == 1, kind


def test_the_space_kinds_are_all_different_characters():
    seen = {plain_text((Space(kind=kind),)) for kind in SpaceKind}
    assert len(seen) == len(list(SpaceKind))


@pytest.mark.parametrize(
    "node",
    [
        NagSymbol(nag=1),
        NoteRef(ref="n1"),
        Anchor(name="a"),
        IndexEntry(terms=("xadrez",)),
        InlineDiagram(fen=STARTING_FEN),
        ImageInline(resource="img"),
        RawInline(format="latex", text=r"\kern1pt"),
    ],
)
def test_a_leaf_with_no_reading_text_contributes_nothing(node):
    assert plain_text((node,)) == ""


def test_plain_text_of_nothing_is_the_empty_string():
    assert plain_text(()) == ""


# --------------------------------------------------------------------------- #
# inline_children
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "wrapper",
    [Span, Emphasis, Strong, Underline, Strike, SmallCaps, Superscript, Subscript],
)
def test_every_wrapper_reports_its_children(wrapper):
    inner = Text(content="x")
    assert inline_children(wrapper(content=(inner,))) == (inner,)


def test_a_link_is_a_wrapper_too():
    inner = Text(content="x")
    assert inline_children(Link(target="#a", content=(inner,))) == (inner,)


@pytest.mark.parametrize(
    "leaf",
    [
        Text(content="x"),
        Move(san="e4"),
        NagSymbol(nag=1),
        LineBreak(),
        Tab(),
        NonBreakingSpace(),
        Space(),
        MathInline(latex="x"),
        InlineDiagram(fen=STARTING_FEN),
        ImageInline(resource="img"),
        NoteRef(ref="n"),
        Anchor(name="a"),
        IndexEntry(terms=("t",)),
        RawInline(format="html", text="<wbr>"),
        PieceGlyph(piece=PieceType.KING),
    ],
)
def test_a_leaf_has_no_inline_children(leaf):
    assert inline_children(leaf) == ()


# --------------------------------------------------------------------------- #
# block_children
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("container", [Quote, Callout, Figure, Group, Footnote, Endnote])
def test_every_block_container_reports_its_children(container):
    inner = Paragraph(content=(Text(content="x"),))
    kwargs = {"content": (inner,)}
    if container in (Footnote, Endnote):
        kwargs["ref"] = "n1"
    assert block_children(container(**kwargs)) == (inner,)


def test_a_list_flattens_its_items_into_blocks():
    first = Paragraph(content=(Text(content="um"),))
    second = Paragraph(content=(Text(content="dois"),))
    block = ListBlock(items=(ListItem(content=(first,)), ListItem(content=(second,))))
    assert block_children(block) == (first, second)


def test_a_table_flattens_its_cells_into_blocks():
    first = Paragraph(content=(Text(content="a"),))
    second = Paragraph(content=(Text(content="b"),))
    table = Table(
        columns=(TableColumn(), TableColumn()),
        rows=(TableRow(cells=(TableCell(content=(first,)), TableCell(content=(second,)))),),
    )
    assert block_children(table) == (first, second)


@pytest.mark.parametrize(
    "leaf",
    [
        Heading(level=1),
        Paragraph(),
        CodeBlock(language="pgn", text="1. e4"),
        Diagram(fen=STARTING_FEN),
    ],
)
def test_a_leaf_block_has_no_block_children(leaf):
    assert block_children(leaf) == ()


# --------------------------------------------------------------------------- #
# Table geometry
# --------------------------------------------------------------------------- #


def test_column_count_prefers_the_declared_columns():
    table = Table(
        columns=(TableColumn(), TableColumn(), TableColumn()),
        rows=(TableRow(cells=(TableCell(),)),),
    )
    assert table.column_count == 3


def test_an_unset_ply_is_clamped_to_the_first_move_rather_than_going_negative():
    """``ply=0`` means "not numbered yet"; it must not read as move zero."""
    assert Move(san="Nf3").ply == 0
    assert Move(san="Nf3").move_number == 1
    assert Move(san="Nf3").is_black_move is False


def test_column_count_is_the_declared_columns_not_a_guess():
    """An undeclared column set stays zero; the validator flags it rather than
    the model inventing a width the exporter would then disagree with."""
    table = Table(
        rows=(
            TableRow(cells=(TableCell(),)),
            TableRow(cells=(TableCell(col_span=2), TableCell())),
        ),
    )
    assert table.column_count == 0


def test_an_empty_table_has_no_columns():
    assert Table().column_count == 0


# --------------------------------------------------------------------------- #
# Document metadata, settings and resources
# --------------------------------------------------------------------------- #


def test_authors_are_the_contributors_with_the_author_role():
    metadata = DocumentMetadata(
        title="Livro",
        contributors=(
            Contributor(name="A", role=ContributorRole.AUTHOR),
            Contributor(name="B", role=ContributorRole.TRANSLATOR),
            Contributor(name="C", role=ContributorRole.AUTHOR),
        ),
    )
    assert [person.name for person in metadata.authors] == ["A", "C"]


def test_custom_metadata_entries_carry_their_scheme():
    entry = MetadataEntry(name="dcterms:audience", value="avancado", scheme="dcterms")
    metadata = DocumentMetadata(title="x", custom=(entry,))
    assert metadata.custom[0].scheme == "dcterms"


def test_a_document_looks_up_a_resource_by_key():
    document = Document(
        resources=(
            Resource(key="capa", kind=ResourceKind.IMAGE),
            Resource(key="merida", kind=ResourceKind.FONT),
        ),
    )
    assert document.resource("merida").kind is ResourceKind.FONT
    assert document.resource("nao-existe") is None


def test_document_settings_default_to_the_products_own_conventions():
    settings = DocumentSettings()
    assert settings.notation_language == "en", "the IR stores canonical English"
    assert settings.figurine_set is FigurineSet.BLACK, "solid glyphs are the print default"
    assert settings.confidence_threshold == 0.9, "SPEC 5.3's amber threshold"
    assert settings.auto_number_diagrams is True


def test_settings_can_switch_the_whole_book_to_portuguese_figurine():
    settings = DocumentSettings(
        notation_language="pt",
        move_render=MoveRenderStyle.FIGURINE,
        chess_font_family="Merida",
    )
    assert settings.notation_language == "pt"
    assert settings.move_render is MoveRenderStyle.FIGURINE


# --------------------------------------------------------------------------- #
# Headers
# --------------------------------------------------------------------------- #


def test_headers_get_is_case_sensitive_like_pgn():
    headers = GameHeaders(white="Smyslov")
    assert headers.get("White") == "Smyslov"
    assert headers.get("white") is None


def test_callout_and_group_kinds_cover_the_chess_book_vocabulary():
    """A chess book's boxes: exercise, solution, theory -- not just "note"."""
    kinds = {kind.value for kind in CalloutKind}
    assert {"exercise", "solution", "theory", "warning", "example"} <= kinds
    roles = {role.value for role in GroupRole}
    assert {"chapter", "exercise-set", "diagram-grid", "front-matter"} <= roles
