"""The EPUB package: the container rules, and EPUBCheck itself.

Two of these tests are not about our code at all -- they are about the two
mistakes that make a package that *looks* fine on disk fail on a device. The
``mimetype`` entry must come first and must be stored uncompressed; get either
wrong and a reader refuses the file with no useful message, and the author
finds out from a customer.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from corpus import epubcheck_jar, java_available, local_paths_in_epub, run_epubcheck

from caissa.core.model import (
    Diagram,
    DiagramSource,
    Document,
    DocumentMetadata,
    ImageBlock,
    Paragraph,
    Provenance,
    Rect,
    Resource,
    SourceKind,
    Text,
)
from caissa.export.epub import EpubExporter, EpubOptions, read_epub


@pytest.fixture(scope="module")
def package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write the corpus as an EPUB once and share it.

    Args:
        tmp_path_factory: Where to write.

    Returns:
        The ``.epub`` path.
    """
    from corpus import CORPUS_NODES, CORPUS_SEED
    from generators import NodeFactory

    document = NodeFactory(CORPUS_SEED).document(min_nodes=CORPUS_NODES)
    target = tmp_path_factory.mktemp("epub") / "livro.epub"
    EpubExporter().export(document, target)
    return target


def test_mimetype_is_the_first_entry(package: Path) -> None:
    """``mimetype`` must be the first file in the archive.

    The specification requires it so a reader can identify the file by reading
    its first bytes, without unzipping anything.
    """
    with zipfile.ZipFile(package) as archive:
        first = archive.infolist()[0]
    assert first.filename == "mimetype"


def test_mimetype_is_stored_uncompressed(package: Path) -> None:
    """``mimetype`` must be stored, not deflated, and carry no extra field."""
    with zipfile.ZipFile(package) as archive:
        entry = archive.infolist()[0]
        assert entry.compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/epub+zip"


def test_the_container_points_at_the_package_document(package: Path) -> None:
    """``META-INF/container.xml`` names the OPF, which is what a reader opens."""
    with zipfile.ZipFile(package) as archive:
        container = archive.read("META-INF/container.xml").decode("utf-8")
    assert "OEBPS/content.opf" in container


def test_every_xml_part_is_well_formed(package: Path) -> None:
    """Every XHTML, OPF and NCX part parses as XML.

    An EPUB is XML, not HTML: a reader will not repair a mismatched tag, it
    will refuse the book. The section splitter used to cut chapters mid-element
    and this is the test that would have caught it.
    """
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            if not name.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                continue
            text = archive.read(name).decode("utf-8")
            body = re.sub(r"^<\?xml[^>]*\?>\s*", "", text.strip())
            body = re.sub(r"^<!DOCTYPE[^>]*>\s*", "", body.strip())
            ET.fromstring(body)  # raises on malformed markup


def test_the_navigation_document_has_landmarks(package: Path) -> None:
    """``nav.xhtml`` carries a table of contents *and* landmarks.

    SPEC section 8.3 asks for landmarks by name: they are what let a reader
    jump to the start of the text rather than to page one of the front matter.
    """
    with zipfile.ZipFile(package) as archive:
        nav = archive.read("OEBPS/nav.xhtml").decode("utf-8")
    assert 'epub:type="toc"' in nav
    assert 'epub:type="landmarks"' in nav
    assert 'epub:type="bodymatter"' in nav


def test_the_package_carries_dublin_core_metadata(package: Path) -> None:
    """The OPF names the title, the language and a unique identifier."""
    with zipfile.ZipFile(package) as archive:
        opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert "dc:title" in opf
    assert "dc:language" in opf
    assert "dc:identifier" in opf
    assert 'property="dcterms:modified"' in opf


def test_diagrams_are_inline_svg_and_not_images(package: Path) -> None:
    """A diagram is geometry in the page, not a picture beside it.

    An ``<img>`` cannot take the reader's colours in night mode and cannot
    scale with the type. SPEC section 8.3 asks for inline SVG and this is where
    that is enforced.
    """
    with zipfile.ZipFile(package) as archive:
        pages = [
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".xhtml")
        ]
    body = "\n".join(pages)
    assert "<svg" in body, "nenhum diagrama vetorial no pacote"
    assert 'data-ir="diagram"' in body
    assert ".svg" not in body or "<img" not in body


def test_the_stylesheet_is_modular(package: Path) -> None:
    """CSS is split so a user can replace the board look without the rest."""
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert "OEBPS/Styles/base.css" in names
    assert "OEBPS/Styles/chess.css" in names
    assert "OEBPS/Styles/props.css" in names


def test_the_stylesheet_has_no_direction_declaration(package: Path) -> None:
    """EPUB forbids ``direction`` in CSS; the value rides on a custom property."""
    with zipfile.ZipFile(package) as archive:
        css = archive.read("OEBPS/Styles/props.css").decode("utf-8")
    assert not re.search(r"(?<![-\w])direction:", css)
    assert "--caissa-rdirection" in css or "--caissa-pdirection" in css


def test_reading_it_back_gives_a_document(package: Path) -> None:
    """The package parses back into the IR through its own XHTML."""
    document = read_epub(package)
    assert isinstance(document, Document)
    assert document.body


def _png() -> bytes:
    """A one-pixel PNG, for an image resource with real bytes on disk."""
    import struct
    import zlib

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        return struct.pack(">I", len(body)) + kind + body + crc

    return (
        bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes([0, 40, 120, 200])))
        + chunk(b"IEND", b"")
    )


def test_the_package_carries_no_path_of_the_authors_disk(tmp_path: Path) -> None:
    """The importer records absolute paths -- the PDF's in the book's ``source`` and in
    every node's provenance, the extracted image's in its resource -- and on Windows they
    carry the user's name.  A package is handed on: the embedded IR and ``dc:source`` name
    the file only, the hashes stay, and the packaged IR reads back as the document but for
    the folders."""
    pdf = str(tmp_path / "Livros" / "Livro.pdf")
    image = tmp_path / "assets" / "fig.png"
    image.parent.mkdir()
    image.write_bytes(_png())
    rect = Rect(x=72.0, y=120.0, width=200.0, height=200.0)
    provenance = Provenance(kind=SourceKind.VISION, document_path=pdf, document_hash="cc" * 32,
                            page_index=0, rect=rect)
    paragraph = Paragraph(content=(Text(content="Um parágrafo lido do PDF."),),
                          provenance=provenance)
    figure = ImageBlock(resource="fig", alt_text="Uma figura")
    diagram = Diagram(
        fen="6k1/5ppp/3q4/4R3/8/8/5PPP/6K1 b - - 0 1", stipulation="Mate em 2",
        provenance=provenance,
        source=DiagramSource(kind=SourceKind.VISION, path=pdf, content_hash="cc" * 32,
                             page_index=0, rect=rect),
    )
    resource = Resource(key="fig", path=str(image), media_type="image/png",
                        content_hash="ee" * 32)
    document = Document(metadata=DocumentMetadata(title="Livro", source=pdf),
                        resources=(resource,), body=(paragraph, figure, diagram))
    target = tmp_path / "livro.epub"
    EpubExporter().export(document, target)

    assert local_paths_in_epub(target, tmp_path) == []
    with zipfile.ZipFile(target) as archive:
        opf = archive.read("OEBPS/content.opf").decode("utf-8")
        assert any(name.startswith("OEBPS/Images/") for name in archive.namelist())
    assert "<dc:source>Livro.pdf</dc:source>" in opf
    named = replace(provenance, document_path="Livro.pdf")
    expected = replace(
        document,
        metadata=replace(document.metadata, source="Livro.pdf"),
        resources=(replace(resource, path="fig.png"),),
        body=(
            replace(paragraph, provenance=named),
            figure,
            replace(diagram, provenance=named, source=replace(diagram.source, path="Livro.pdf")),
        ),
    )
    assert read_epub(target, use_sidecar=True) == expected
    assert read_epub(target).metadata.source == "Livro.pdf"


def test_fixed_layout_declares_itself(tmp_path: Path, small: Document) -> None:
    """A fixed-layout package says so in the OPF, or a reader reflows it."""
    target = tmp_path / "fixo.epub"
    EpubExporter().export(small, target, options=EpubOptions(layout="fixed"))
    with zipfile.ZipFile(target) as archive:
        opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert "rendition:layout" in opf
    assert "pre-paginated" in opf


@pytest.mark.skipif(not java_available(), reason="Java nao esta instalado nesta maquina.")
@pytest.mark.skipif(
    epubcheck_jar() is None,
    reason=(
        "EPUBCheck nao encontrado. Defina CAISSA_EPUBCHECK apontando para "
        "epubcheck.jar para rodar o portao de aceitacao real."
    ),
)
def test_epubcheck_reports_no_errors(package: Path) -> None:
    """The SPEC section 11.3 gate: EPUBCheck, zero errors.

    This is the only test in the suite that runs somebody else's validator, and
    it is the one that matters: our own parser accepting the file proves that
    our parser is lenient, not that the file is valid.
    """
    jar = epubcheck_jar()
    assert jar is not None
    errors, output = run_epubcheck(jar, package)
    assert errors == 0, output[-4000:]


# --------------------------------------------------------------------------- #
# The font-embedding path, exercised
# --------------------------------------------------------------------------- #
# SPEC section 8.3 asks for embedded and subset chess fonts, and the machinery
# for it has always been there -- but nothing in the corpus reached it, because
# the diagram renderer draws pieces as outlines and never asks for a face. A
# mechanism with no test is a mechanism that is about to stop working, so this
# is a book that asks for chess type in running text.
def _figurine_book() -> Document:
    """Build a document that sets chess type in the running text.

    Returns:
        The document. Chess Merida is a legacy face: it draws a knight for the
        character ``n``, which is what makes ``1.Nf3`` come out as a figurine.
    """
    from caissa.core.chess.notation_tables import FigurineSet, PieceType
    from caissa.core.model import PieceGlyph, RunProps

    return Document(
        metadata=DocumentMetadata(title="Figurino", language="pt-BR"),
        body=(
            Paragraph(
                content=(
                    Text(content="O lance "),
                    PieceGlyph(
                        piece=PieceType.KNIGHT,
                        figurine_set=FigurineSet.WHITE,
                        font_family="Chess Merida",
                    ),
                    Text(content="f3", props=RunProps(font_family="Chess Merida")),
                    Text(content=" abre a partida."),
                ),
            ),
        ),
    )


def _chess_font_installed() -> bool:
    """Whether this machine has the face the test asks for.

    Returns:
        ``True`` when Chess Merida is on the font search path.
    """
    try:
        from caissa.typeset.fonts import find_font_file, get_spec

        return find_font_file(get_spec("merida")) is not None
    except Exception:  # noqa: BLE001 - an absent font is a skip, not a failure
        return False


def test_chess_type_in_running_text_is_embedded_and_subset(tmp_path: Path) -> None:
    """A book that asks for chess type carries the face, cut to what it uses.

    Three things have to be true at once for a figurine to reach a reader, and
    each has broken on its own before: the face is in the package, it is a
    *subset* rather than the whole file, and the ``@font-face`` rule names it
    with a ``unicode-range`` that covers exactly the characters written.
    """
    if not _chess_font_installed():
        pytest.skip("Chess Merida nao esta instalada nesta maquina")

    from caissa.typeset.fonts import find_font_file, get_spec

    target = tmp_path / "figurino.epub"
    result = EpubExporter().export(_figurine_book(), target)
    assert result.stats.get("fonts") == 1, "nenhuma fonte foi embutida"

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        faces = [name for name in names if name.startswith("OEBPS/Fonts/")]
        assert faces, f"o pacote nao carrega nenhuma fonte: {names}"
        data = archive.read(faces[0])
        css = archive.read("OEBPS/Styles/fonts.css").decode("utf-8")
        opf = archive.read(
            next(name for name in names if name.endswith(".opf"))
        ).decode("utf-8")

    whole = find_font_file(get_spec("merida")).stat().st_size
    assert len(data) < whole / 4, (
        f"a fonte foi embutida inteira ({len(data)} de {whole} bytes), nao subconjuntada"
    )
    assert '@font-face' in css
    assert 'font-family: "Chess Merida"' in css
    assert "unicode-range:" in css
    assert faces[0].rsplit("/", 1)[-1] in opf, "a fonte nao esta no manifesto"


def test_the_embedded_subset_carries_exactly_the_glyphs_the_text_asks_for(
    tmp_path: Path,
) -> None:
    """A subset that keeps too little is a book with holes where the pieces were.

    The document sets a knight, an ``f`` and a ``3`` in Chess Merida and nothing
    else, so the face must answer to those three codepoints and to no others --
    and it must answer through a Unicode ``cmap``, because a reader looks up
    ``U+006E`` and a legacy chess font often only knows ``U+F06E``.
    """
    if not _chess_font_installed():
        pytest.skip("Chess Merida nao esta instalada nesta maquina")

    from fontTools.ttLib import TTFont

    from caissa.typeset.fonts import get_spec

    target = tmp_path / "figurino.epub"
    EpubExporter().export(_figurine_book(), target)
    with zipfile.ZipFile(target) as archive:
        face = next(name for name in archive.namelist() if name.startswith("OEBPS/Fonts/"))
        data = archive.read(face)

    font = TTFont(io.BytesIO(data))
    knight = get_spec("merida").artwork_char("N")
    covered: set[int] = set()
    for table in font["cmap"].tables:
        covered.update(table.cmap)
    assert covered == {ord(knight), ord("f"), ord("3")}, sorted(covered)
    assert any(
        (table.platformID, table.platEncID) == (3, 1) for table in font["cmap"].tables
    ), "sem cmap Unicode o leitor procura U+006E e nao acha nada"


def test_the_piece_is_written_in_the_encoding_of_the_face_that_sets_it(
    tmp_path: Path,
) -> None:
    """Naming a face and writing a character it cannot draw is a blank page.

    Chess Merida has no glyph at ``U+265E``. Writing the Unicode figurine while
    asking for that family gives the reader nothing to draw, so the piece is
    written in the face's own encoding.
    """
    if not _chess_font_installed():
        pytest.skip("Chess Merida nao esta instalada nesta maquina")

    from caissa.typeset.fonts import get_spec

    target = tmp_path / "figurino.epub"
    EpubExporter().export(_figurine_book(), target)
    with zipfile.ZipFile(target) as archive:
        pages = [
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith("OEBPS/Text/")
        ]
    body = "\n".join(pages)
    assert 'data-ir="piece_glyph"' in body
    knight = get_spec("merida").artwork_char("N")
    marker = 'data-piece="knight"'
    index = body.index(marker)
    assert knight in body[index : index + 400]


def test_a_font_that_cannot_be_subset_says_so_out_loud(tmp_path: Path) -> None:
    """A face that could not be cut is a degradation, not a silence.

    The reader falls back to some other face and the figurines come out as
    letters; the user has to be told which family it was.
    """
    from caissa.core.model import RunProps

    document = Document(
        metadata=DocumentMetadata(title="Fonte ausente", language="pt-BR"),
        body=(
            Paragraph(
                content=(
                    Text(
                        content="Nf3",
                        props=RunProps(font_family="Chess Nao Existe Mesmo"),
                    ),
                ),
            ),
        ),
    )
    result = EpubExporter().export(document, tmp_path / "ausente.epub")
    assert result.stats.get("fonts", 0) == 0
    assert not [
        warning
        for warning in result.degradation.warnings
        if warning.property == "font_embedding"
    ], "uma familia de texto comum nao e uma fonte de xadrez e nao deve avisar"
