"""``validate()`` -- one test per error class the module docstring claims.

The validator's job is narrow and worth stating precisely: *is this document
internally consistent enough to export?* It does not judge typography. What it
does catch is the set of defects that turn into a broken EPUB, an unopenable
DOCX or a wrong diagram -- dangling references, impossible chess, impossible
layout, unresolved names, accessibility gaps.

Every issue carries a stable ``code``, so these tests assert on codes rather
than on message text: the message is written for a Brazilian reader and may be
reworded, the code is an API.

The module-level guard ``test_every_documented_code_has_a_test`` keeps this file
honest -- add a code to the validator without adding a case here and the suite
fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.model import (
    SQUARE_COUNT,
    ULID,
    Anchor,
    CharacterStyle,
    Color,
    ColorSpace,
    Diagram,
    Document,
    DocumentMetadata,
    DocumentSettings,
    Figure,
    Heading,
    ImageBlock,
    ImageInline,
    IndexEntry,
    LengthUnit,
    Link,
    LinkKind,
    ListBlock,
    ListItem,
    ListKind,
    ListMarkerStyle,
    Mark,
    MarkKind,
    Measure,
    Move,
    MoveNode,
    NagSymbol,
    NoteRef,
    Paragraph,
    ParagraphProps,
    ParagraphStyle,
    RawInline,
    RawPassthrough,
    RecognitionResult,
    Resource,
    ResourceKind,
    RunProps,
    Severity,
    StyleSheet,
    Table,
    TableCell,
    TableOfContents,
    TableRow,
    Text,
    validate,
)
from caissa.core.model.blocks import Callout, Footnote
from caissa.core.model.props import NumberingRef

VALIDATE_SOURCE = Path("src/caissa/core/model/validate.py")


def document(*blocks, **kwargs) -> Document:
    """A document that is valid apart from whatever the caller put in it."""
    kwargs.setdefault("metadata", DocumentMetadata(title="Livro de teste", language="pt-BR"))
    return Document(body=tuple(blocks), **kwargs)


def codes(doc: Document, **kwargs) -> set[str]:
    """The set of issue codes ``validate`` reports for a document."""
    return {issue.code for issue in validate(doc, **kwargs)}


def only(doc: Document, code: str):
    """The issues carrying one code, for asserting on severity and path."""
    return [issue for issue in validate(doc) if issue.code == code]


# --------------------------------------------------------------------------- #
# A clean document produces nothing
# --------------------------------------------------------------------------- #


def test_a_well_formed_document_reports_nothing():
    doc = document(
        Heading(level=1, content=(Text(content="Capitulo 1"),)),
        Paragraph(content=(Text(content="Uma frase."),)),
        Diagram(fen=STARTING_FEN, alt_text="posicao inicial"),
    )
    assert validate(doc) == []


def test_issues_render_as_one_readable_line():
    issue = only(document(Heading(level=9)), "titulo.nivel-invalido")[0]
    assert str(issue).startswith("error titulo.nivel-invalido $.body[0]")
    assert issue.node_type == "heading"
    assert isinstance(issue.node_id, ULID)


# --------------------------------------------------------------------------- #
# Orphan note references, and the reverse
# --------------------------------------------------------------------------- #


def test_a_note_reference_with_no_note_is_an_orphan():
    doc = document(Paragraph(content=(NoteRef(ref="nota-1"),)))
    assert "nota.referencia-orfa" in codes(doc)


def test_a_note_reference_that_resolves_is_clean():
    doc = document(
        Paragraph(content=(NoteRef(ref="nota-1"),)),
        Footnote(ref="nota-1", content=(Paragraph(content=(Text(content="A nota."),)),)),
    )
    assert not {code for code in codes(doc) if code.startswith("nota.")}


def test_a_note_that_nobody_references_is_reported():
    doc = document(Footnote(ref="orfa", content=(Paragraph(content=(Text(content="x"),)),)))
    assert "nota.nunca-referenciada" in codes(doc)


def test_two_notes_sharing_a_ref_are_reported():
    doc = document(
        Paragraph(content=(NoteRef(ref="n"),)),
        Footnote(ref="n", content=(Paragraph(content=(Text(content="a"),)),)),
        Footnote(ref="n", content=(Paragraph(content=(Text(content="b"),)),)),
    )
    assert "nota.ref-duplicada" in codes(doc)


def test_an_internal_link_to_a_missing_anchor_is_reported():
    doc = document(Paragraph(content=(Link(target="#ausente", kind=LinkKind.INTERNAL),)))
    assert "link.ancora-inexistente" in codes(doc)


def test_an_internal_link_to_a_real_anchor_is_clean():
    doc = document(
        Paragraph(content=(Anchor(name="cap-1"),)),
        Paragraph(content=(Link(target="#cap-1", kind=LinkKind.INTERNAL),)),
    )
    assert "link.ancora-inexistente" not in codes(doc)


def test_an_external_link_is_not_checked_against_anchors():
    doc = document(Paragraph(content=(Link(target="https://exemplo.org"),)))
    assert "link.ancora-inexistente" not in codes(doc)


def test_a_link_with_no_target_is_reported():
    doc = document(Paragraph(content=(Link(target="   "),)))
    assert "link.alvo-vazio" in codes(doc)


def test_two_anchors_with_the_same_name_are_reported():
    doc = document(
        Paragraph(content=(Anchor(name="dup"),)),
        Paragraph(content=(Anchor(name="dup"),)),
    )
    assert "ancora.duplicada" in codes(doc)


def test_an_image_pointing_at_an_undeclared_resource_is_reported():
    doc = document(ImageBlock(resource="nao-declarado", alt_text="x"))
    assert "recurso.inexistente" in codes(doc)


def test_an_image_pointing_at_a_declared_resource_is_clean():
    doc = document(
        ImageBlock(resource="img-1", alt_text="capa"),
        resources=(Resource(key="img-1", kind=ResourceKind.IMAGE, path="capa.png"),),
    )
    assert not {code for code in codes(doc) if code.startswith(("imagem.", "recurso."))}


def test_an_image_with_a_blank_resource_key_is_reported():
    assert "imagem.sem-recurso" in codes(document(ImageBlock(resource="  ", alt_text="x")))


def test_an_inline_image_is_checked_the_same_way():
    doc = document(Paragraph(content=(ImageInline(resource="fantasma", alt_text="x"),)))
    assert "recurso.inexistente" in codes(doc)


def test_two_nodes_sharing_an_id_are_reported():
    shared = ULID.from_parts(1_700_000_000_000, 1)
    doc = document(Paragraph(id=shared), Paragraph(id=shared))
    assert "no.id-duplicado" in codes(doc)


# --------------------------------------------------------------------------- #
# Invalid FEN and impossible chess
# --------------------------------------------------------------------------- #


def test_a_malformed_fen_is_an_error():
    issues = only(document(Diagram(fen="isto nao e uma fen", alt_text="x")), "fen.invalida")
    assert issues
    assert issues[0].severity is Severity.ERROR


def test_an_empty_fen_is_reported_as_missing():
    assert "fen.ausente" in codes(document(Diagram(fen="", alt_text="x")))


def test_an_illegal_position_is_a_warning_not_an_error():
    issues = only(
        document(Diagram(fen="4k3/8/8/8/8/8/8/K3K3 w - - 0 1", alt_text="x")),
        "fen.posicao-ilegal",
    )
    assert issues
    assert issues[0].severity is Severity.WARNING


def test_a_move_node_position_is_validated_too():
    doc = document(
        Paragraph(content=(Move(san="Nf3", position_before="lixo"),)),
    )
    assert "fen.invalida" in codes(doc)


# --------------------------------------------------------------------------- #
# Table span overflow
# --------------------------------------------------------------------------- #


def test_a_row_whose_spans_exceed_the_declared_columns_is_reported():
    from caissa.core.model import TableColumn

    table = Table(
        columns=(TableColumn(), TableColumn()),
        rows=(TableRow(cells=(TableCell(col_span=2), TableCell(col_span=2))),),
    )
    assert "tabela.span-excede" in codes(document(table))


def test_a_row_that_fits_exactly_is_clean():
    from caissa.core.model import TableColumn

    table = Table(
        columns=(TableColumn(), TableColumn(), TableColumn()),
        rows=(TableRow(cells=(TableCell(col_span=2), TableCell())),),
    )
    assert not {code for code in codes(document(table)) if code.startswith("tabela.")}


@pytest.mark.parametrize(("row_span", "col_span"), [(0, 1), (1, 0), (-1, 1), (1, -3)])
def test_a_non_positive_span_is_reported(row_span, col_span):
    from caissa.core.model import TableColumn

    table = Table(
        columns=(TableColumn(),),
        rows=(TableRow(cells=(TableCell(row_span=row_span, col_span=col_span),)),),
    )
    assert "tabela.span-invalido" in codes(document(table))


def test_a_table_with_rows_but_no_columns_is_reported():
    table = Table(rows=(TableRow(cells=(TableCell(),)),))
    assert "tabela.sem-colunas" in codes(document(table))


def test_more_header_and_footer_rows_than_rows_is_reported():
    from caissa.core.model import TableColumn

    table = Table(
        columns=(TableColumn(),),
        rows=(TableRow(cells=(TableCell(),)),),
        header_row_count=2,
        footer_row_count=1,
    )
    assert "tabela.cabecalho-excede" in codes(document(table))


# --------------------------------------------------------------------------- #
# Unresolved style names
# --------------------------------------------------------------------------- #


def test_a_run_naming_an_undefined_character_style_is_reported():
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(style="Fantasma")),)))
    assert "estilo.nao-resolvido" in codes(doc)


def test_a_paragraph_naming_an_undefined_style_is_reported():
    doc = document(Paragraph(props=ParagraphProps(style="Fantasma")))
    assert "estilo.nao-resolvido" in codes(doc)


def test_a_numbering_reference_to_an_undefined_definition_is_reported():
    doc = document(
        Paragraph(props=ParagraphProps(numbering=NumberingRef(definition="Fantasma"))),
    )
    assert "estilo.nao-resolvido" in codes(doc)


def test_a_defined_style_resolves_cleanly():
    doc = document(
        Paragraph(props=ParagraphProps(style="Corpo")),
        styles=StyleSheet(paragraph_styles=(ParagraphStyle(name="Corpo"),)),
    )
    assert "estilo.nao-resolvido" not in codes(doc)


def test_strict_styles_can_be_turned_off_mid_import():
    doc = document(Paragraph(props=ParagraphProps(style="AindaNaoDefinido")))
    assert "estilo.nao-resolvido" in codes(doc)
    assert "estilo.nao-resolvido" not in codes(doc, strict_styles=False)


def test_a_cyclic_based_on_chain_is_reported():
    doc = document(
        Paragraph(content=(Text(content="x", props=RunProps(style="A")),)),
        styles=StyleSheet(
            character_styles=(
                CharacterStyle(name="A", based_on="B"),
                CharacterStyle(name="B", based_on="A"),
            ),
        ),
    )
    assert "estilo.ciclo" in codes(doc)


def test_two_styles_with_the_same_name_are_reported():
    doc = document(
        styles=StyleSheet(
            paragraph_styles=(ParagraphStyle(name="Corpo"), ParagraphStyle(name="Corpo")),
        ),
    )
    assert "estilo.nome-duplicado" in codes(doc)


def test_a_style_with_an_empty_name_is_reported():
    doc = document(styles=StyleSheet(character_styles=(CharacterStyle(name=""),)))
    assert "estilo.nome-vazio" in codes(doc)


# --------------------------------------------------------------------------- #
# Empty required fields
# --------------------------------------------------------------------------- #


def test_a_document_without_a_title_is_a_warning():
    doc = Document(metadata=DocumentMetadata(title="  ", language="pt-BR"))
    issues = only(doc, "documento.sem-titulo")
    assert issues
    assert issues[0].severity is Severity.WARNING


def test_a_document_without_a_language_is_an_error():
    doc = Document(metadata=DocumentMetadata(title="Livro", language=""))
    issues = only(doc, "documento.sem-idioma")
    assert issues
    assert issues[0].severity is Severity.ERROR


def test_an_unknown_notation_language_is_reported():
    doc = document(settings=DocumentSettings(notation_language="klingon"))
    assert "documento.idioma-de-notacao-desconhecido" in codes(doc)


def test_an_empty_heading_is_reported():
    assert "titulo.vazio" in codes(document(Heading(level=2)))


def test_an_empty_san_is_reported():
    doc = document(Paragraph(content=(Move(san="   "),)))
    assert "lance.san-vazio" in codes(doc)


def test_a_negative_ply_is_reported():
    doc = document(Paragraph(content=(Move(san="Nf3", ply=-1),)))
    assert "lance.ply-negativo" in codes(doc)


def test_a_move_in_an_unknown_language_is_reported():
    doc = document(Paragraph(content=(Move(san="Nf3", language="klingon"),)))
    assert "lance.idioma-desconhecido" in codes(doc)


def test_raw_passthrough_without_a_format_is_reported():
    assert "passthrough.formato-vazio" in codes(document(RawPassthrough(format=" ", text="x")))


def test_raw_inline_without_a_format_is_reported():
    doc = document(Paragraph(content=(RawInline(format="", text="x"),)))
    assert "passthrough.formato-vazio" in codes(doc)


def test_an_index_entry_with_no_terms_is_reported():
    doc = document(Paragraph(content=(IndexEntry(terms=()),)))
    assert "indice.entrada-vazia" in codes(doc)


def test_an_anchor_with_an_empty_name_is_reported():
    doc = document(Paragraph(content=(Anchor(name="  "),)))
    assert "ancora.nome-vazio" in codes(doc)


def test_a_resource_with_an_empty_key_is_reported():
    doc = document(resources=(Resource(key=""),))
    assert "recurso.chave-vazia" in codes(doc)


def test_two_resources_with_the_same_key_are_reported():
    doc = document(resources=(Resource(key="a"), Resource(key="a")))
    assert "recurso.chave-duplicada" in codes(doc)


def test_an_empty_text_run_is_an_observation_not_an_error():
    issues = only(document(Paragraph(content=(Text(content=""),))), "texto.vazio")
    assert issues
    assert issues[0].severity is Severity.INFO


def test_a_newline_inside_a_text_run_is_reported():
    """A paragraph break is a new block; a line break is ``LineBreak``."""
    doc = document(Paragraph(content=(Text(content="uma\nduas"),)))
    assert "texto.quebra-de-linha" in codes(doc)


def test_an_empty_list_item_is_reported():
    doc = document(ListBlock(items=(ListItem(),)))
    assert "lista.item-vazio" in codes(doc)


def test_an_empty_callout_is_reported():
    assert "destaque.vazio" in codes(document(Callout()))


def test_an_empty_language_tag_on_a_run_is_reported():
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(language="   ")),)))
    assert "texto.idioma-vazio" in codes(doc)


# --------------------------------------------------------------------------- #
# Impossible layout
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("level", [0, -1, 7, 9, 100])
def test_a_heading_outside_levels_one_to_six_is_reported(level):
    doc = document(Heading(level=level, content=(Text(content="x"),)))
    assert "titulo.nivel-invalido" in codes(doc)


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
def test_the_six_legal_heading_levels_are_accepted(level):
    doc = document(Heading(level=level, content=(Text(content="x"),)))
    assert "titulo.nivel-invalido" not in codes(doc)


def test_a_definition_list_item_without_a_term_is_reported():
    doc = document(
        ListBlock(
            kind=ListKind.DEFINITION,
            items=(ListItem(content=(Paragraph(content=(Text(content="x"),)),)),),
        ),
    )
    assert "lista.termo-ausente" in codes(doc)


def test_a_term_on_a_non_definition_list_is_reported():
    doc = document(
        ListBlock(
            kind=ListKind.UNORDERED,
            items=(
                ListItem(
                    term=(Text(content="termo"),),
                    content=(Paragraph(content=(Text(content="x"),)),),
                ),
            ),
        ),
    )
    assert "lista.termo-inesperado" in codes(doc)


def test_a_custom_marker_style_without_marker_text_is_reported():
    doc = document(
        ListBlock(
            marker_style=ListMarkerStyle.CUSTOM,
            items=(ListItem(content=(Paragraph(content=(Text(content="x"),)),)),),
        ),
    )
    assert "lista.marcador-vazio" in codes(doc)


def test_a_table_of_contents_with_an_inverted_range_is_reported():
    assert "sumario.faixa-invalida" in codes(document(TableOfContents(min_level=4, max_level=2)))


# --------------------------------------------------------------------------- #
# Property ranges
# --------------------------------------------------------------------------- #


def test_a_negative_font_size_is_reported():
    props = RunProps(font_size=Measure(value=-2.0, unit=LengthUnit.PT))
    doc = document(Paragraph(content=(Text(content="x", props=props),)))
    assert "medida.tamanho-negativo" in codes(doc)


@pytest.mark.parametrize("weight", [0, -100, 1001, 5000])
def test_a_font_weight_outside_one_to_a_thousand_is_reported(weight):
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(font_weight=weight)),)))
    assert "fonte.peso-fora-da-faixa" in codes(doc)


@pytest.mark.parametrize("opacity", [-0.1, 1.5, 42.0])
def test_an_opacity_outside_zero_to_one_is_reported(opacity):
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(opacity=opacity)),)))
    assert "cor.opacidade-fora-da-faixa" in codes(doc)


def test_a_colour_with_the_wrong_component_count_is_reported():
    colour = Color(space=ColorSpace.RGB, components=(0.1, 0.2))
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(color=colour)),)))
    assert "cor.componentes" in codes(doc)


def test_a_colour_channel_outside_zero_to_one_is_reported():
    colour = Color(space=ColorSpace.RGB, components=(0.1, 2.0, 0.3))
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(color=colour)),)))
    assert "cor.canal-fora-da-faixa" in codes(doc)


def test_a_named_colour_without_a_name_is_reported():
    colour = Color(space=ColorSpace.NAMED, components=(), name=None)
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(color=colour)),)))
    assert "cor.sem-nome" in codes(doc)


@pytest.mark.parametrize("nag", [0, 256, -1])
def test_a_standalone_nag_symbol_outside_range_is_reported(nag):
    doc = document(Paragraph(content=(NagSymbol(nag=nag),)))
    assert "nag.fora-da-faixa" in codes(doc)


def test_a_move_node_nag_outside_range_is_reported():
    from caissa.core.model import GameScore

    doc = document(GameScore(children=(MoveNode(san="e4", nags=(999,)),)))
    assert "nag.fora-da-faixa" in codes(doc)


# --------------------------------------------------------------------------- #
# Accessibility
# --------------------------------------------------------------------------- #


def test_an_image_without_alt_text_is_reported():
    doc = document(
        ImageBlock(resource="img-1"),
        resources=(Resource(key="img-1"),),
    )
    assert "imagem.sem-texto-alternativo" in codes(doc)


def test_a_diagram_with_a_caption_needs_no_alt_text():
    doc = document(Diagram(fen=STARTING_FEN, caption=(Text(content="Posicao inicial"),)))
    assert "diagrama.sem-texto-alternativo" not in codes(doc)


def test_a_numbered_figure_without_a_caption_is_an_observation():
    issues = only(document(Figure(number=3)), "figura.sem-legenda")
    assert issues
    assert issues[0].severity is Severity.INFO


# --------------------------------------------------------------------------- #
# Ordering, paths and completeness
# --------------------------------------------------------------------------- #


def test_issues_carry_the_path_of_the_offending_node():
    doc = document(Paragraph(), Paragraph(content=(Text(content="uma\nduas"),)))
    issue = only(doc, "texto.quebra-de-linha")[0]
    assert issue.path == "$.body[1].content[0]"


def test_marks_inside_a_move_node_are_validated():
    from caissa.core.model import GameScore

    doc = document(
        GameScore(
            children=(MoveNode(san="e4", arrows=(Mark(kind=MarkKind.ARROW, squares=("j9",)),)),),
        ),
    )
    assert "marca.casa-invalida" in codes(doc)


def test_a_diagram_deep_inside_a_figure_is_still_validated():
    doc = document(
        Figure(content=(Diagram(fen="lixo", alt_text="x"),), caption=(Text(content="c"),)),
    )
    assert "fen.invalida" in codes(doc)


def test_a_recognition_vector_of_the_wrong_length_is_reported():
    diagram = Diagram(
        fen=STARTING_FEN,
        alt_text="x",
        recognition=RecognitionResult(per_square_confidence=(0.9,) * (SQUARE_COUNT - 1)),
    )
    assert "reconhecimento.confianca-tamanho" in codes(document(diagram))


def test_every_documented_code_has_a_test():
    """The guard: a validator code with no case here fails the suite."""
    pattern = r"\"([a-z]+\.[a-z0-9-]+)\""
    declared = set(re.findall(pattern, VALIDATE_SOURCE.read_text(encoding="utf-8")))
    tested: set[str] = set()
    for module in (
        Path(__file__),
        Path("tests/unit/model/test_diagram.py"),
        Path("tests/unit/model/test_game.py"),
        Path("tests/unit/model/test_edges.py"),
    ):
        tested |= set(re.findall(pattern, module.read_text(encoding="utf-8")))
    missing = declared - tested
    assert not missing, f"validator codes never exercised: {sorted(missing)}"
