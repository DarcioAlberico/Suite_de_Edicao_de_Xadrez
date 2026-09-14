"""The Word package: real styles, live fields, and a file Word will open.

SPEC section 8.2 names four things ``python-docx`` cannot do, and each has a
test here. The fifth thing -- "abre no Word sem pedido de reparo" -- cannot be
tested on a machine without Word, so what is tested instead is every mechanical
precondition for it: the package parts exist, the content types are declared,
every relationship resolves, and every XML part parses. The report says plainly
that this is a schema check and not Word.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from caissa.core.model import (
    Alignment,
    Diagram,
    Document,
    DocumentMetadata,
    Footnote,
    Heading,
    ImageBlock,
    ImageInline,
    Measure,
    NoteRef,
    Paragraph,
    ParagraphProps,
    Resource,
    ResourceKind,
    RunProps,
    TableOfContents,
    Text,
)
from caissa.export.docx import BOOKMARK_PREFIX, DocxExporter, read_docx

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STARTING = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture(scope="module")
def package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a document that exercises every SPEC section 8.2 feature.

    Args:
        tmp_path_factory: Where to write.

    Returns:
        The ``.docx`` path.
    """
    document = Document(
        metadata=DocumentMetadata(
            title="Finais de torre",
            subtitle="Um manual",
            language="pt-BR",
            publisher="Caissa",
            subjects=("xadrez", "finais"),
        ),
        body=(
            TableOfContents(),
            Heading(level=1, content=(Text(content="Lucena"),), anchor="lucena"),
            Paragraph(
                content=(
                    Text(content="A ponte", props=RunProps(italic=True)),
                    NoteRef(ref="n1"),
                ),
                props=ParagraphProps(style="Corpo"),
            ),
            Diagram(fen=STARTING, number=1, caption=(Text(content="A posicao"),)),
            Footnote(
                ref="n1",
                content=(Paragraph(content=(Text(content="Lucena, 1497."),)),),
            ),
        ),
    )
    target = tmp_path_factory.mktemp("docx") / "livro.docx"
    DocxExporter().export(document, target)
    return target


def _part(package: Path, name: str) -> str:
    """Read one package part as text.

    Args:
        package: The ``.docx``.
        name: The part name inside the archive.

    Returns:
        The part text.
    """
    with zipfile.ZipFile(package) as archive:
        return archive.read(name).decode("utf-8")


def test_every_part_is_well_formed_xml(package: Path) -> None:
    """A malformed part is exactly what makes Word offer to repair a file."""
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(archive.read(name))


def test_the_package_has_the_parts_word_requires(package: Path) -> None:
    """The minimum set: content types, root relationships, and the document."""
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    for required in (
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
        "word/_rels/document.xml.rels",
        "word/styles.xml",
        "word/numbering.xml",
        "word/settings.xml",
        "word/footnotes.xml",
        "word/endnotes.xml",
        "docProps/core.xml",
        "docProps/app.xml",
    ):
        assert required in names, f"parte obrigatoria ausente: {required}"


def test_every_content_type_is_declared(package: Path) -> None:
    """A part with no declared content type is a part Word refuses."""
    types = _part(package, "[Content_Types].xml")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
    extensions = {name.rsplit(".", 1)[-1].lower() for name in names if "." in name}
    declared = set(re.findall(r'Extension="([^"]+)"', types))
    overridden = {
        part.lstrip("/") for part in re.findall(r'PartName="([^"]+)"', types)
    }
    for name in names:
        suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        assert suffix in declared or name in overridden, f"{name} sem content type"
    assert extensions <= declared | {
        name.rsplit(".", 1)[-1].lower() for name in overridden
    }


def test_every_relationship_resolves(package: Path) -> None:
    """A relationship pointing at nothing is a broken document."""
    rels = _part(package, "word/_rels/document.xml.rels")
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    for target, mode in re.findall(
        r'Target="([^"]+)"(\s+TargetMode="External")?', rels
    ):
        if mode:
            continue
        assert f"word/{target}" in names, f"relacionamento quebrado: {target}"


def test_formatting_comes_from_named_styles(package: Path) -> None:
    """SPEC section 8.2: "estilos reais (nao formatacao direta)".

    A style is what makes a Word document maintainable: change ``Diagrama``
    once and every caption follows. Direct formatting produces a file that
    looks right and cannot be edited.
    """
    styles = _part(package, "word/styles.xml")
    for name in ("Normal", "Heading1", "Caption", "Diagram", "FootnoteText"):
        assert f'w:styleId="{name}"' in styles, f"estilo '{name}' ausente"
    assert "<w:docDefaults>" in styles

    document = _part(package, "word/document.xml")
    assert "<w:pStyle " in document, "nenhum paragrafo referencia um estilo"


def test_figure_numbering_is_a_seq_field(package: Path) -> None:
    """SPEC section 8.2: numbering via ``SEQ``, so inserting renumbers."""
    document = _part(package, "word/document.xml")
    assert "SEQ Diagrama" in document or "SEQ Figura" in document
    assert 'w:fldCharType="begin"' in document
    assert 'w:fldCharType="end"' in document


def test_the_table_of_contents_is_a_toc_field(package: Path) -> None:
    """SPEC section 8.2: the TOC belongs to Word, not frozen by us."""
    document = _part(package, "word/document.xml")
    assert "TOC " in document
    settings = _part(package, "word/settings.xml")
    assert "<w:updateFields" in settings, (
        "sem w:updateFields o leitor ve o texto reserva ate apertar F9"
    )


def test_footnotes_are_real_footnotes(package: Path) -> None:
    """The note is in ``footnotes.xml`` and referenced from the run."""
    notes = _part(package, "word/footnotes.xml")
    root = ET.fromstring(notes)
    ids = [item.get(f"{{{W}}}id") for item in root]
    assert "-1" in ids and "0" in ids, "faltam os separadores que o Word exige"
    assert any(item not in ("-1", "0") for item in ids), "nenhuma nota real"
    assert "w:footnoteReference" in _part(package, "word/document.xml")


def test_document_properties_are_filled(package: Path) -> None:
    """A librarian reads ``core.xml``; leaving it empty loses the book."""
    core = _part(package, "docProps/core.xml")
    assert "Finais de torre" in core
    assert "dc:language" in core
    assert "dcterms:modified" in core


def test_node_identity_survives_as_bookmarks(package: Path) -> None:
    """The tree can be found again after Word has rewritten the file."""
    document = _part(package, "word/document.xml")
    assert BOOKMARK_PREFIX in document
    names = re.findall(rf'w:name="{BOOKMARK_PREFIX}([^"]+)"', document)
    assert names
    assert all(len(name) == 26 for name in names), "um bookmark nao carrega um ULID"


def test_reading_it_back_gives_a_document(package: Path) -> None:
    """``read_docx`` parses ``word/document.xml``, not a sidecar."""
    document = read_docx(package)
    assert isinstance(document, Document)
    assert document.body
    assert document.metadata.title == "Finais de torre"


def test_no_sidecar_is_written(package: Path) -> None:
    """DOCX carries no embedded IR, so its fidelity number measures the writer."""
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
    assert not [name for name in names if "caissa-ir" in name]


def test_control_characters_never_reach_the_file(tmp_path: Path) -> None:
    """A raw control character is illegal XML, and Word says so on open."""
    document = Document(
        metadata=DocumentMetadata(title="Controle"),
        body=(Paragraph(content=(Text(content="a\x00b\x07c"),)),),
    )
    target = tmp_path / "controle.docx"
    DocxExporter().export(document, target)
    with zipfile.ZipFile(target) as archive:
        ET.fromstring(archive.read("word/document.xml"))


# --------------------------------------------------------------------------- #
# What the round trip has to bring back
# --------------------------------------------------------------------------- #
# Each of these was a measured leak in the first F8 report: the writer put the
# thing in the file and the reader walked past it, so the fidelity number
# counted a silent loss where the file was in fact complete. One test per leak,
# so that closing it cannot quietly reopen.
def _round_trip(document: Document, tmp_path: Path) -> Document:
    """Write a document and read it back through ``word/document.xml``.

    Args:
        document: The IR to write.
        tmp_path: Where to write it.

    Returns:
        The re-imported document.
    """
    target = tmp_path / "ida-e-volta.docx"
    DocxExporter().export(document, target)
    return read_docx(target)


def _only_paragraph(document: Document) -> Paragraph:
    """Return the first paragraph of a round-tripped document.

    Args:
        document: The re-imported document.

    Returns:
        The paragraph.
    """
    found = [block for block in document.body if isinstance(block, Paragraph)]
    assert found, "nenhum paragrafo voltou do arquivo"
    return found[0]


def test_the_paragraph_ruler_comes_back_from_w_tabs(tmp_path: Path) -> None:
    """``w:tabs`` was written from the first day and never read back.

    Alignment and leader are exact: ``ST_TabJc`` and ``ST_TabTlc`` name every
    stop the IR has. The position is a whole number of twips, which is why the
    profile calls ``tab_stops`` approximate rather than full.
    """
    from caissa.core.model import Measure, TabAlignment, TabLeader, TabStop

    stops = (
        TabStop(
            position=Measure.points(36),
            alignment=TabAlignment.DECIMAL,
            leader=TabLeader.DOT,
        ),
        TabStop(
            position=Measure.points(72),
            alignment=TabAlignment.RIGHT,
            leader=TabLeader.MIDDLE_DOT,
        ),
    )
    document = Document(
        metadata=DocumentMetadata(title="Regua"),
        body=(
            Paragraph(
                content=(Text(content="a b"),),
                props=ParagraphProps(tab_stops=stops),
            ),
        ),
    )
    back = _only_paragraph(_round_trip(document, tmp_path))
    assert len(back.props.tab_stops) == 2
    assert [stop.alignment for stop in back.props.tab_stops] == [
        TabAlignment.DECIMAL,
        TabAlignment.RIGHT,
    ]
    assert [stop.leader for stop in back.props.tab_stops] == [
        TabLeader.DOT,
        TabLeader.MIDDLE_DOT,
    ]
    assert [stop.position.to_points() for stop in back.props.tab_stops] == [36.0, 72.0]


def test_a_numbering_reference_survives_by_name(tmp_path: Path) -> None:
    """``w:numId`` is a number and a ``NumberingRef`` is a name.

    ECMA-376 gives ``w:abstractNum`` a ``w:name`` child, which is the only
    place the author's name for a numbering definition can live. Without it the
    reference comes back as an integer nobody can match to a stylesheet entry.
    """
    from caissa.core.model import NumberingRef

    reference = NumberingRef(definition="Notacao", level=2, start_override=7)
    document = Document(
        metadata=DocumentMetadata(title="Numeracao"),
        body=(
            Paragraph(
                content=(Text(content="um"),),
                props=ParagraphProps(numbering=reference),
            ),
        ),
    )
    package = tmp_path / "numeracao.docx"
    DocxExporter().export(document, package)
    numbering = _part(package, "word/numbering.xml")
    assert '<w:name w:val="Notacao"/>' in numbering
    assert "w:startOverride" in numbering
    assert "<w:numPr>" in _part(package, "word/document.xml")

    back = _only_paragraph(read_docx(package))
    assert back.props.numbering == reference


def test_a_list_numbering_is_not_read_back_as_an_author_decision(
    tmp_path: Path,
) -> None:
    """A paragraph inside a list did not ask for numbering: its list did.

    The exporter marks list items with two numbering definitions of its own.
    Reading those back as a ``NumberingRef`` would invent a decision the author
    never made, and the loss of the list block itself is already declared.
    """
    from caissa.core.model import ListBlock, ListItem, ListKind

    document = Document(
        metadata=DocumentMetadata(title="Lista"),
        body=(
            ListBlock(
                kind=ListKind.ORDERED,
                items=(
                    ListItem(content=(Paragraph(content=(Text(content="um"),)),)),
                    ListItem(content=(Paragraph(content=(Text(content="dois"),)),)),
                ),
            ),
        ),
    )
    back = _round_trip(document, tmp_path)
    paragraphs = [block for block in back.body if isinstance(block, Paragraph)]
    assert paragraphs
    assert all(block.props.numbering is None for block in paragraphs)


def test_rows_and_cells_keep_their_own_identity(tmp_path: Path) -> None:
    """A bookmark may sit between two ``w:tr`` and between two ``w:tc``.

    ``EG_ContentRowContent`` and ``EG_ContentCellContent`` both admit
    ``EG_RunLevelElts``, and a bookmark is one. Before this, a row and a cell
    had nowhere to keep an id and came back as new nodes.
    """
    from caissa.core.model import Table, TableCell, TableRow

    cells = (
        TableCell(content=(Paragraph(content=(Text(content="a"),)),)),
        TableCell(content=(Paragraph(content=(Text(content="b"),)),)),
    )
    row = TableRow(cells=cells, is_header=True)
    table = Table(rows=(row,))
    document = Document(metadata=DocumentMetadata(title="Tabela"), body=(table,))
    back = _round_trip(document, tmp_path)

    tables = [block for block in back.body if isinstance(block, Table)]
    assert tables, "a tabela voltou como outra coisa"
    assert tables[0].id == table.id
    assert tables[0].rows[0].id == row.id
    assert [cell.id for cell in tables[0].rows[0].cells] == [cell.id for cell in cells]


def test_the_table_carries_its_borders_padding_and_description(
    tmp_path: Path,
) -> None:
    """``w:tblBorders``, ``w:tblCellMar`` and ``w:tblDescription`` all exist."""
    from caissa.core.model import (
        Border,
        Borders,
        BorderStyle,
        Measure,
        Padding,
        Table,
        TableCell,
        TableRow,
    )

    table = Table(
        rows=(
            TableRow(
                cells=(TableCell(content=(Paragraph(content=(Text(content="a"),)),)),)
            ),
        ),
        borders=Borders(top=Border(style=BorderStyle.DOUBLE, width=Measure.points(1.5))),
        cell_padding=Padding(top=Measure.points(3), left=Measure.points(6)),
        summary="Resultados por peao",
    )
    package = tmp_path / "tabela.docx"
    DocxExporter().export(
        Document(metadata=DocumentMetadata(title="T"), body=(table,)), package
    )
    xml = _part(package, "word/document.xml")
    assert "<w:tblBorders>" in xml
    assert "<w:tblCellMar>" in xml
    assert 'w:tblDescription w:val="Resultados por peao"' in xml

    back = [block for block in read_docx(package).body if isinstance(block, Table)][0]
    assert back.summary == "Resultados por peao"
    assert back.borders is not None
    assert back.borders.top is not None
    assert back.borders.top.style is BorderStyle.DOUBLE
    assert back.cell_padding is not None
    assert back.cell_padding.top is not None


def test_the_move_tree_survives_run_by_run(tmp_path: Path) -> None:
    """The game is written one run per token, so every move keeps its id.

    Writing the movetext as a single string is what made the tree stop existing
    on the way back. Nothing here needs the moves to be legal chess: the
    structure comes from the parentheses and the identities from the bookmarks.
    """
    from caissa.core.model import GameScore, MoveNode

    deep = MoveNode(san="Nf3", ply=3)
    black = MoveNode(san="e5", ply=2, emphasis=True, children=(deep,))
    variation = MoveNode(san="c5", ply=2, comment_before="a siciliana")
    white = MoveNode(
        san="e4",
        ply=1,
        nags=(1, 14),
        comment_after="bom lance",
        children=(black, variation),
    )
    game = GameScore(initial_comment="Uma partida.", children=(white,))
    document = Document(metadata=DocumentMetadata(title="Partida"), body=(game,))

    back = _round_trip(document, tmp_path)
    games = [block for block in back.body if isinstance(block, GameScore)]
    assert games, "a partida nao voltou como partida"
    read = games[0]
    assert read.id == game.id
    assert read.initial_comment == "Uma partida."

    first = read.children[0]
    assert first.id == white.id
    assert first.san == "e4"
    assert first.ply == 1
    assert first.nags == (1, 14)
    assert first.comment_after == "bom lance"
    assert len(first.children) == 2, "a variante virou continuacao da linha principal"
    assert first.children[0].id == black.id
    assert first.children[0].emphasis is True
    assert first.children[0].children[0].id == deep.id
    assert first.children[1].id == variation.id
    assert first.children[1].comment_before == "a siciliana"


def test_the_paragraph_mark_formatting_is_written_and_read(tmp_path: Path) -> None:
    """``w:pPr/w:rPr`` is the paragraph mark, which is what ``mark_props`` means."""
    from caissa.core.model import Measure

    mark = RunProps(font_size=Measure.points(18), italic=True)
    document = Document(
        metadata=DocumentMetadata(title="Marca"),
        body=(
            Paragraph(
                content=(Text(content="a"),), props=ParagraphProps(mark_props=mark)
            ),
        ),
    )
    back = _only_paragraph(_round_trip(document, tmp_path))
    assert back.props.mark_props is not None
    assert back.props.mark_props.italic is True
    assert back.props.mark_props.font_size == Measure.points(18)


def test_a_drop_cap_is_a_frame_and_comes_back_as_one(tmp_path: Path) -> None:
    """``w:framePr`` carries ``w:dropCap`` and ``w:lines``, so the count is exact."""
    document = Document(
        metadata=DocumentMetadata(title="Capitular"),
        body=(Paragraph(content=(Text(content="Era uma vez"),), drop_cap=4),),
    )
    package = tmp_path / "capitular.docx"
    DocxExporter().export(document, package)
    assert 'w:dropCap="drop"' in _part(package, "word/document.xml")
    assert _only_paragraph(read_docx(package)).drop_cap == 4


def _png(width: int, height: int) -> bytes:
    """A flat PNG of the given size, for a resource with real bytes."""
    import struct
    import zlib

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    row = bytes([0]) + bytes([40, 120, 200]) * width
    return (
        bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def test_an_image_travels_as_a_picture_and_comes_back_as_a_node(tmp_path: Path) -> None:
    """The picture's own fields carry the node: key in ``wp:docPr/@name``,
    alternative text in ``@descr``, title in ``@title``, crop in ``a:srcRect``,
    size in ``wp:extent`` -- so ``read_docx`` rebuilds an ``ImageBlock`` and an
    ``ImageInline`` from ``word/document.xml`` alone, and a diagram's picture
    is left alone as before."""
    figure = tmp_path / "figura.png"
    figure.write_bytes(_png(120, 60))
    document = Document(
        metadata=DocumentMetadata(title="Ilustrado"),
        resources=(
            Resource(
                key="fig-1", kind=ResourceKind.IMAGE, path=str(figure), media_type="image/png"
            ),
        ),
        body=(
            ImageBlock(
                resource="fig-1",
                alt_text="Uma figura de prova",
                title="Prova",
                width=Measure.points(90.0),
                height=Measure.points(45.0),
                alignment=Alignment.RIGHT,
                crop=(0.0, 0.1, 1.0, 0.9),
            ),
            Paragraph(
                content=(
                    Text(content="Antes "),
                    ImageInline(resource="fig-1", alt_text="em linha", width=Measure.points(12.0)),
                    Text(content=" depois"),
                )
            ),
            Diagram(fen=STARTING),
        ),
    )
    package = tmp_path / "ilustrado.docx"
    DocxExporter().export(document, package)
    main = _part(package, "word/document.xml")
    assert main.count("<w:drawing>") == 3
    assert 'name="fig-1"' in main
    assert 'descr="Uma figura de prova"' in main
    assert 'title="Prova"' in main
    assert '<a:srcRect l="0" t="10000" r="0" b="10000"/>' in main
    assert "[fig-1]" not in main

    read = read_docx(package)
    block = read.body[0]
    assert isinstance(block, ImageBlock)
    assert block.resource == "fig-1"
    assert block.alt_text == "Uma figura de prova"
    assert block.title == "Prova"
    assert block.alignment is Alignment.RIGHT
    assert block.crop == (0.0, 0.1, 1.0, 0.9)
    assert block.width is not None
    assert abs(block.width.to_points() - 90.0) < 0.01
    assert block.height is not None
    assert abs(block.height.to_points() - 45.0) < 0.01
    paragraph = read.body[1]
    assert isinstance(paragraph, Paragraph)
    inline = paragraph.content[1]
    assert isinstance(inline, ImageInline)
    assert inline.resource == "fig-1"
    assert inline.alt_text == "em linha"
    assert inline.width is not None
    assert abs(inline.width.to_points() - 12.0) < 0.01
    # the diagram's EMF picture is not mistaken for an image node
    assert not isinstance(read.body[2], (ImageBlock, ImageInline))


def test_an_image_without_its_file_keeps_its_place_as_a_placeholder(tmp_path: Path) -> None:
    """No bytes to embed: a grey placeholder picture of the asked size stands
    in, the key still names it, and the report says so -- the DOCX
    counterpart of the ``image-missing`` box the XHTML writes."""
    document = Document(
        metadata=DocumentMetadata(title="Sem arquivo"),
        resources=(
            Resource(key="capa", kind=ResourceKind.IMAGE, path="assets/nao-existe.png"),
        ),
        body=(ImageBlock(resource="capa", alt_text="A capa", width=Measure.points(50.0)),),
    )
    package = tmp_path / "sem-arquivo.docx"
    result = DocxExporter().export(document, package)
    main = _part(package, "word/document.xml")
    assert "<w:drawing>" in main
    assert 'name="capa"' in main
    with zipfile.ZipFile(package) as archive:
        assert archive.read("word/media/imagem1.png")[:4] == bytes([0x89]) + b"PNG"
    assert any(warning.property == "images" for warning in result.degradation.warnings)
    block = read_docx(package).body[0]
    assert isinstance(block, ImageBlock)
    assert block.resource == "capa"
    assert block.alt_text == "A capa"
    assert block.width is not None
    assert abs(block.width.to_points() - 50.0) < 0.01


def test_a_note_comes_back_where_it_stood_in_the_story(tmp_path: Path) -> None:
    """The body of a note lives outside ``w:body``; its place does not.

    An empty bookmark is how OOXML names a place, so the note goes back between
    the same two paragraphs it was written between instead of at the end.
    """
    from caissa.core.model import Endnote

    note = Footnote(ref="n1", content=(Paragraph(content=(Text(content="Nota."),)),))
    tail = Endnote(ref="e1", content=(Paragraph(content=(Text(content="Fim."),)),))
    before = Paragraph(content=(Text(content="antes"),))
    after = Paragraph(content=(Text(content="depois"),))
    document = Document(
        metadata=DocumentMetadata(title="Notas"),
        body=(before, note, after, tail),
    )
    back = _round_trip(document, tmp_path)
    kinds = [type(block).__name__ for block in back.body]
    assert kinds == ["Paragraph", "Footnote", "Paragraph", "Endnote"], kinds
    assert back.body[1].id == note.id
    assert back.body[3].id == tail.id
    assert back.body[1].content[0].id == note.content[0].id


def test_the_document_itself_keeps_its_identity(tmp_path: Path) -> None:
    """``w:body`` *is* the document, so the document node has no element.

    Its id is an empty bookmark at the head of the story, and without it the
    root of the tree comes back as a different node every time.
    """
    document = Document(
        metadata=DocumentMetadata(title="Identidade"),
        body=(Paragraph(content=(Text(content="a"),)),),
    )
    assert _round_trip(document, tmp_path).id == document.id


def test_a_heading_always_takes_a_heading_style(tmp_path: Path) -> None:
    """Word's outline, navigation pane and TOC field key off the Heading styles.

    A heading left in a style the author named would stop being a heading in
    Word and would come back as an ordinary paragraph. Losing the author's own
    style name is what ``_DOCX_PARAGRAPH["style"]`` declares.
    """
    heading = Heading(
        level=2,
        content=(Text(content="Lucena"),),
        props=ParagraphProps(style="Titulo1"),
    )
    document = Document(metadata=DocumentMetadata(title="Titulos"), body=(heading,))
    package = tmp_path / "titulos.docx"
    DocxExporter().export(document, package)
    assert 'w:pStyle w:val="Heading2"' in _part(package, "word/document.xml")

    back = read_docx(package).body[0]
    assert isinstance(back, Heading)
    assert back.level == 2
    assert back.id == heading.id


def test_a_diagram_prints_its_solution(tmp_path: Path) -> None:
    """A study whose solution is only in the IR is a study the book omits."""
    from caissa.core.model import GameScore, MoveNode, walk

    solution = GameScore(children=(MoveNode(san="Rb2", ply=1),))
    document = Document(
        metadata=DocumentMetadata(title="Estudo"),
        body=(Diagram(fen=STARTING, solution=solution),),
    )
    package = tmp_path / "estudo.docx"
    DocxExporter().export(document, package)
    assert "Rb2" in _part(package, "word/document.xml")

    moves = [
        node
        for _path, node in walk(read_docx(package))
        if type(node).__name__ == "MoveNode"
    ]
    assert [node.id for node in moves] == [solution.children[0].id]


def test_every_property_element_is_in_schema_order() -> None:
    """OOXML declares its property groups as ``xsd:sequence``, not ``xsd:all``.

    Word answers an element out of position by refusing the file, so the new
    ``w:trPr`` and ``w:tcPr`` children are ordered like the older ``w:rPr`` and
    ``w:pPr`` ones.
    """
    from caissa.export.docx import _TCPR_ORDER, _TRPR_ORDER, _in_schema_order

    scrambled = ["<w:tblHeader/>", '<w:trHeight w:val="1"/>', "<w:cantSplit/>"]
    assert _in_schema_order(scrambled, _TRPR_ORDER) == (
        '<w:cantSplit/><w:trHeight w:val="1"/><w:tblHeader/>'
    )
    cell = ['<w:vAlign w:val="center"/>', "<w:tcMar/>", '<w:gridSpan w:val="2"/>']
    assert _in_schema_order(cell, _TCPR_ORDER) == (
        '<w:gridSpan w:val="2"/><w:tcMar/><w:vAlign w:val="center"/>'
    )
