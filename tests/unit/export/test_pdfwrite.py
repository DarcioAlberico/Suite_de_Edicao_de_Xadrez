"""Tests for the low-level PDF writer.

The suite deliberately avoids any PDF library: a file that can only be validated by the
same kind of code that produced it has not been validated at all. Everything below goes
through ``NaivePdf``, a small parser written here from the format description -- it
follows ``startxref`` to the cross-reference table, reads object offsets out of it, and
slices stream bodies by their declared ``/Length``. If the writer's offsets are wrong,
the parser falls apart, which is exactly the failure we want to catch.
"""

from __future__ import annotations

import logging
import re
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest

from caissa.export.pdfwrite import (
    PDFA_CAVEATS,
    STRUCT_TAGS,
    ContentStream,
    FontEmbedder,
    LinkAnnotation,
    OutlineEntry,
    PdfDocument,
    PdfMetadata,
    PdfName,
    PdfPage,
    PdfRef,
    PdfWriteError,
    StructElement,
    pdfa_caveats,
)

WINDOWS_FONTS = Path(r"C:\Windows\Fonts")
GEORGIA = WINDOWS_FONTS / "georgia.ttf"
TIMES = WINDOWS_FONTS / "times.ttf"
ARIAL = WINDOWS_FONTS / "arial.ttf"

# fontTools logs (not warns) about the ancient `head` dates in legacy chess fonts.
logging.getLogger("fontTools").setLevel(logging.ERROR)


# --------------------------------------------------------------------------- #
# A naive PDF parser, written here on purpose
# --------------------------------------------------------------------------- #


@dataclass
class ParsedObject:
    """One indirect object as the naive parser sees it."""

    number: int
    body: bytes
    """The dictionary (or bare value) source, before any ``stream`` keyword."""
    stream: bytes | None = None
    """Raw stream bytes, still filtered."""

    def data(self) -> bytes:
        """Return the stream payload, inflating it when ``/FlateDecode`` is declared."""
        if self.stream is None:
            return b""
        if b"/FlateDecode" in self.body:
            return zlib.decompress(self.stream)
        return self.stream

    def name(self, key: str) -> str | None:
        """Return the value of a ``/Key /Name`` entry, or None."""
        match = re.search(rf"/{key}\s*/([A-Za-z0-9#.+-]+)".encode(), self.body)
        return match.group(1).decode("ascii") if match else None

    def number_value(self, key: str) -> float | None:
        """Return the value of a ``/Key 123`` entry, or None."""
        match = re.search(rf"/{key}\s+(-?[0-9.]+)(?![0-9.]*\s+[0-9]+\s+R)".encode(), self.body)
        return float(match.group(1)) if match else None

    def ref(self, key: str) -> int | None:
        """Return the object number of a ``/Key n 0 R`` entry, or None."""
        match = re.search(rf"/{key}\s+([0-9]+)\s+[0-9]+\s+R".encode(), self.body)
        return int(match.group(1)) if match else None

    def refs(self) -> set[int]:
        """Return every object number this object's dictionary references."""
        return {int(m) for m in re.findall(rb"\b([0-9]+)\s+[0-9]+\s+R\b", self.body)}


@dataclass
class NaivePdf:
    """A PDF taken apart with regexes and the cross-reference table."""

    raw: bytes
    version: str
    xref_offset: int
    objects: dict[int, ParsedObject] = field(default_factory=dict)
    trailer: bytes = b""

    def object_for(self, ref: int | None) -> ParsedObject:
        """Return the object with the given number.

        Args:
            ref: The object number.

        Returns:
            The parsed object.
        """
        assert ref is not None, "esperado uma referencia, recebido None"
        assert ref in self.objects, f"objeto {ref} referenciado mas ausente"
        return self.objects[ref]

    def find(self, marker: bytes) -> list[ParsedObject]:
        """Return every object whose dictionary contains ``marker``."""
        return [obj for obj in self.objects.values() if marker in obj.body]


_OBJ_HEADER = re.compile(rb"([0-9]+)\s+([0-9]+)\s+obj")
_STREAM_START = re.compile(rb"stream\r?\n")
_ENDOBJ = re.compile(rb"endobj")


def parse_pdf(raw: bytes) -> NaivePdf:
    """Take a PDF apart via its cross-reference table.

    Args:
        raw: The complete file bytes.

    Returns:
        The parsed document.
    """
    header = re.match(rb"%PDF-(\d\.\d)\n", raw)
    assert header, "arquivo nao comeca com um cabecalho %PDF-x.y"

    tail = re.search(rb"startxref\s+([0-9]+)\s+%%EOF", raw)
    assert tail, "trailer sem startxref/%%EOF"
    xref_offset = int(tail.group(1))
    assert raw[xref_offset : xref_offset + 4] == b"xref", (
        "o offset em startxref nao aponta para a palavra-chave xref"
    )

    section = re.compile(rb"xref\r?\n([0-9]+)\s+([0-9]+)\r?\n").match(raw, xref_offset)
    assert section, "tabela xref malformada"
    first, count = int(section.group(1)), int(section.group(2))
    assert first == 0, "a tabela xref classica precisa comecar no objeto 0"

    offsets: dict[int, int] = {}
    cursor = section.end()
    for index in range(count):
        entry = raw[cursor : cursor + 20]
        assert len(entry) == 20, f"entrada xref {index} nao tem 20 bytes"
        offset, _generation, kind = entry[:10], entry[11:16], entry[17:18]
        if kind == b"n":
            offsets[first + index] = int(offset)
        cursor += 20

    trailer_match = re.compile(rb"trailer\r?\n").search(raw, cursor)
    assert trailer_match, "trailer ausente"
    trailer = raw[trailer_match.end() : tail.start()]

    document = NaivePdf(raw=raw, version=header.group(1).decode(), xref_offset=xref_offset)
    document.trailer = trailer
    for number, offset in offsets.items():
        document.objects[number] = _parse_object(raw, number, offset)
    return document


def _parse_object(raw: bytes, expected: int, offset: int) -> ParsedObject:
    head = _OBJ_HEADER.match(raw, offset)
    assert head, f"nenhum 'N 0 obj' no offset {offset} (objeto {expected})"
    assert int(head.group(1)) == expected, (
        f"xref aponta o objeto {expected} para o objeto {head.group(1).decode()}"
    )
    start = head.end()
    stream_start = _STREAM_START.search(raw, start)
    endobj = _ENDOBJ.search(raw, start)
    assert endobj, f"objeto {expected} sem endobj"
    if stream_start is not None and stream_start.start() < endobj.start():
        body = raw[start : stream_start.start()]
        length = re.search(rb"/Length\s+([0-9]+)", body)
        assert length, f"stream do objeto {expected} sem /Length"
        size = int(length.group(1))
        payload = raw[stream_start.end() : stream_start.end() + size]
        assert raw[stream_start.end() + size : stream_start.end() + size + 11].startswith(
            b"\nendstream"
        ), f"/Length do objeto {expected} nao bate com o fim do stream"
        return ParsedObject(number=expected, body=body, stream=payload)
    return ParsedObject(number=expected, body=raw[start : endobj.start()])


# --------------------------------------------------------------------------- #
# Fixtures / builders
# --------------------------------------------------------------------------- #


def vector_content() -> bytes:
    """Draw a shape using every path operator the tests look for."""
    stream = ContentStream()
    stream.save()
    stream.set_fill_rgb(0.2, 0.4, 0.6)
    stream.set_stroke_gray(0.0)
    stream.set_line_width(1.5)
    stream.set_dash([3, 2], 0)
    stream.set_line_cap(1)
    stream.set_line_join(1)
    stream.rect(50, 50, 200, 120)
    stream.fill()
    stream.move_to(50, 300)
    stream.line_to(250, 300)
    stream.curve_to(260, 310, 270, 320, 280, 300)
    stream.close_path()
    stream.stroke()
    stream.restore()
    return stream.to_bytes()


def simple_document(*, pages: int = 1, compress: bool = True) -> PdfDocument:
    """Build a vector-only document with the given number of pages."""
    doc = PdfDocument(compress=compress)
    for _ in range(pages):
        doc.add_page(PdfPage(595.28, 841.89, vector_content()))
    doc.set_metadata(PdfMetadata(title="Documento minimo", author="Caissa"))
    return doc


# --------------------------------------------------------------------------- #
# File structure
# --------------------------------------------------------------------------- #


def test_minimal_pdf_has_valid_envelope():
    data = simple_document().to_bytes()

    assert data.startswith(b"%PDF-1.7")
    assert data.rstrip(b"\r\n").endswith(b"%%EOF")

    document = parse_pdf(data)
    assert document.version == "1.7"
    # parse_pdf already asserts this, but state it here as the requirement it is.
    assert data[document.xref_offset : document.xref_offset + 4] == b"xref"


def test_every_referenced_object_exists():
    doc = simple_document(pages=3)
    doc.set_outline([OutlineEntry("Um", 0, 800.0)])
    doc.add_named_destination("inicio", 0, 800.0)
    document = parse_pdf(doc.to_bytes())

    known = set(document.objects)
    for obj in document.objects.values():
        missing = obj.refs() - known
        assert not missing, f"objeto {obj.number} referencia objetos inexistentes: {missing}"

    trailer_refs = {int(m) for m in re.findall(rb"\b([0-9]+)\s+[0-9]+\s+R\b", document.trailer)}
    assert trailer_refs <= known
    assert b"/Root" in document.trailer
    assert b"/Info" in document.trailer


def test_trailer_id_is_two_identical_hex_strings():
    document = parse_pdf(simple_document().to_bytes())
    ids = re.search(rb"/ID\s*\[\s*<([0-9A-F]+)>\s*<([0-9A-F]+)>\s*\]", document.trailer)
    assert ids, "trailer sem /ID"
    assert ids.group(1) == ids.group(2)
    assert len(ids.group(1)) == 32  # MD5 as hex


def test_output_is_deterministic():
    first = simple_document(pages=2).to_bytes()
    second = simple_document(pages=2).to_bytes()
    assert first == second


def test_write_creates_parent_directories(tmp_path):
    target = tmp_path / "sub" / "dir" / "livro.pdf"
    simple_document().write(target)
    assert target.exists()
    assert parse_pdf(target.read_bytes()).objects


# --------------------------------------------------------------------------- #
# Round-trip: object numbering and the page tree
# --------------------------------------------------------------------------- #


def test_regex_roundtrip_object_numbering_and_page_tree():
    doc = simple_document(pages=3, compress=False)
    data = doc.to_bytes()

    # Uncompressed and font-free, so a raw regex over the whole file is safe here.
    found = sorted(int(m) for m in re.findall(rb"(?m)^([0-9]+) 0 obj$", data))
    assert found == list(range(1, len(found) + 1)), "numeracao de objetos com buracos"

    document = parse_pdf(data)
    assert sorted(document.objects) == found

    root = document.object_for(int(re.search(rb"/Root\s+([0-9]+)", document.trailer).group(1)))
    assert root.name("Type") == "Catalog"

    pages = document.object_for(root.ref("Pages"))
    assert pages.name("Type") == "Pages"
    assert pages.number_value("Count") == 3

    kids = re.search(rb"/Kids\s*\[(.*?)\]", pages.body, re.S)
    kid_numbers = [int(m) for m in re.findall(rb"([0-9]+)\s+[0-9]+\s+R", kids.group(1))]
    assert len(kid_numbers) == 3

    for number in kid_numbers:
        page = document.object_for(number)
        assert page.name("Type") == "Page"
        assert page.ref("Parent") == pages.number
        assert b"/MediaBox [0 0 595.28 841.89]" in page.body
        contents = document.object_for(page.ref("Contents"))
        assert b" re\n" in contents.data()


# --------------------------------------------------------------------------- #
# Vector graphics
# --------------------------------------------------------------------------- #


def test_vector_content_uses_path_operators_and_no_images():
    data = simple_document(compress=False).to_bytes()
    document = parse_pdf(data)
    page = next(o for o in document.objects.values() if o.name("Type") == "Page")
    content = document.object_for(page.ref("Contents")).data()

    tokens = set(content.split())
    for operator in (b"re", b"m", b"l", b"c", b"f", b"S", b"q", b"Q", b"w", b"d", b"h"):
        assert operator in tokens, f"operador {operator.decode()} ausente no fluxo"

    assert b"/Subtype /Image" not in data
    assert b"/Image" not in data


def test_content_stream_rejects_unbalanced_nesting():
    stream = ContentStream()
    stream.save()
    with pytest.raises(PdfWriteError, match="q"):
        stream.to_bytes()
    assert stream.to_bytes(strict=False)

    with pytest.raises(PdfWriteError, match="EMC"):
        ContentStream().end_marked_content()
    with pytest.raises(PdfWriteError, match="ET"):
        ContentStream().end_text()
    with pytest.raises(PdfWriteError, match="Q"):
        ContentStream().restore()


def test_content_stream_numbers_are_compact():
    stream = ContentStream()
    stream.rect(0, 1.5, 100.0, -0.25)
    assert stream.to_bytes() == b"0 1.5 100 -0.25 re"


def test_marked_content_emits_bdc_with_properties():
    stream = ContentStream()
    stream.begin_marked_content("Figure", 7, alt="Diagrama", lang="pt-BR")
    stream.end_marked_content()
    stream.begin_marked_content("Artifact")
    stream.end_marked_content()
    body = stream.to_bytes()
    assert b"/Figure << /MCID 7 /Lang (pt-BR) /Alt (Diagrama) >> BDC" in body
    assert b"/Artifact BMC" in body
    assert body.count(b"EMC") == 2


# --------------------------------------------------------------------------- #
# Strings, names and escaping
# --------------------------------------------------------------------------- #


def test_literal_strings_escape_backslash_and_parentheses():
    doc = simple_document()
    doc.set_metadata(PdfMetadata(title=r"a (b) c \ d", producer=None))
    document = parse_pdf(doc.to_bytes())
    info = document.object_for(int(re.search(rb"/Info\s+([0-9]+)", document.trailer).group(1)))
    assert rb"(a \(b\) c \\ d)" in info.body


def test_non_ascii_becomes_utf16be_hex_with_bom():
    doc = simple_document()
    doc.set_metadata(PdfMetadata(title="Aberturas: defesa siciliana \u2014 an\u00e1lise"))
    document = parse_pdf(doc.to_bytes())
    info = document.object_for(int(re.search(rb"/Info\s+([0-9]+)", document.trailer).group(1)))
    hex_string = re.search(rb"/Title\s*<([0-9A-F]+)>", info.body)
    assert hex_string, "titulo nao-ASCII deveria virar hex string"
    decoded = bytes.fromhex(hex_string.group(1).decode())
    assert decoded[:2] == b"\xfe\xff"
    assert decoded.decode("utf-16-be")[1:].startswith("Aberturas")


def test_pdf_name_escapes_delimiters():
    assert PdfName("Type").to_bytes() == b"/Type"
    assert PdfName("A B").to_bytes() == b"/A#20B"
    assert PdfName("a/b").to_bytes() == b"/a#2Fb"
    with pytest.raises(PdfWriteError):
        PdfName("").to_bytes()


def test_pdf_ref_serialises():
    assert PdfRef(12).to_bytes() == b"12 0 R"


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #


def _document_with_georgia(text: str = "Caissa Studio 1.e4 e5") -> tuple[bytes, object]:
    embedder = FontEmbedder()
    font = embedder.load(GEORGIA)
    stream = ContentStream()
    stream.begin_text()
    stream.set_font(font.resource_name, 11.0)
    stream.text_position(72, 700)
    stream.show(font.encode(text))
    stream.end_text()
    content = stream.to_bytes()

    doc = PdfDocument()
    refs = embedder.finalise(doc)
    doc.add_page(PdfPage(595.28, 841.89, content, resources={"Font": refs}))
    doc.set_metadata(PdfMetadata(title="Com fonte"))
    return doc.to_bytes(), font


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_georgia_embeds_as_identity_h_cid_font():
    data, _font = _document_with_georgia()
    document = parse_pdf(data)

    type0 = next(o for o in document.objects.values() if o.name("Subtype") == "Type0")
    assert type0.name("Encoding") == "Identity-H"
    base = type0.name("BaseFont")
    assert re.fullmatch(r"[A-Z]{6}\+Georgia", base), f"tag de subconjunto invalida: {base}"

    descendant_number = int(
        re.search(rb"/DescendantFonts\s*\[\s*([0-9]+)\s+[0-9]+\s+R", type0.body).group(1)
    )
    descendant = document.object_for(descendant_number)
    assert descendant.name("Subtype") == "CIDFontType2"
    assert descendant.name("CIDToGIDMap") == "Identity"
    assert descendant.name("BaseFont") == base
    assert b"/Registry (Adobe)" in descendant.body
    assert b"/Ordering (Identity)" in descendant.body
    assert descendant.number_value("DW") == 1000

    widths = re.search(rb"/W\s*\[(.*?)\]\s*/CIDToGIDMap", descendant.body, re.S)
    assert widths, "/W ausente no CIDFont descendente"
    assert re.search(rb"[0-9]+\s*\[", widths.group(1)), "/W nao esta na forma cid [larguras]"


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_font_descriptor_is_complete():
    data, _font = _document_with_georgia()
    document = parse_pdf(data)
    descriptor = next(o for o in document.objects.values() if o.name("Type") == "FontDescriptor")
    for key in ("Flags", "ItalicAngle", "Ascent", "Descent", "CapHeight", "StemV"):
        assert descriptor.number_value(key) is not None, f"/{key} ausente no FontDescriptor"
    assert descriptor.number_value("Ascent") > 0
    assert descriptor.number_value("Descent") < 0
    assert descriptor.number_value("CapHeight") > 0
    assert descriptor.number_value("StemV") > 0
    bbox = re.search(rb"/FontBBox\s*\[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]", descriptor.body)
    assert bbox, "/FontBBox ausente"
    x_min, y_min, x_max, y_max = (int(g) for g in bbox.groups())
    assert x_min < x_max
    assert y_min < y_max

    # Exactly one of Symbolic (4) / Nonsymbolic (32) must be set.
    flags = int(descriptor.number_value("Flags"))
    assert bool(flags & 4) != bool(flags & 32)


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_font_file2_is_a_real_subset_smaller_than_the_original():
    data, _font = _document_with_georgia()
    document = parse_pdf(data)
    descriptor = next(o for o in document.objects.values() if o.name("Type") == "FontDescriptor")
    font_file = document.object_for(descriptor.ref("FontFile2"))
    length1 = font_file.number_value("Length1")
    assert length1 is not None, "/FontFile2 sem /Length1"

    subset_bytes = font_file.data()
    assert len(subset_bytes) == int(length1)
    assert subset_bytes[:4] in (b"\x00\x01\x00\x00", b"true", b"ttcf")

    original = GEORGIA.stat().st_size
    assert len(subset_bytes) < original, (
        f"subconjunto ({len(subset_bytes)}) nao e menor que o original ({original})"
    )
    # A handful of glyphs out of ~860 should be a small fraction, not a rounding error.
    assert len(subset_bytes) < original * 0.5


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_tounicode_cmap_exists_and_maps_the_text():
    data, font = _document_with_georgia("Xadrez")
    document = parse_pdf(data)
    type0 = next(o for o in document.objects.values() if o.name("Subtype") == "Type0")
    to_unicode = document.object_for(type0.ref("ToUnicode"))
    program = to_unicode.data().decode("ascii")

    assert "beginbfchar" in program
    assert "endcmap" in program
    assert "/CMapType 2 def" in program
    assert "<0000> <FFFF>" in program

    mapping = {
        int(src, 16): bytes.fromhex(dst).decode("utf-16-be")
        for src, dst in re.findall(r"<([0-9A-F]{4})> <([0-9A-F]+)>\n", program)
    }
    for char in "Xadrez":
        assert mapping[font.glyph_id(char)] == char


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_encode_is_two_bytes_per_character():
    font = FontEmbedder().load(GEORGIA)
    for text in ("", "a", "Caissa", "1.e4 e5 2.Cf3"):
        assert len(font.encode(text)) == 2 * len(text)
    # A character the face lacks still occupies its two bytes, as .notdef.
    assert font.encode("\u265f") == b"\x00\x00"
    assert not font.has_char("\u265f")
    assert font.has_char("a")


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_text_width_orders_narrow_before_wide():
    font = FontEmbedder().load(GEORGIA)
    assert font.text_width("iii", 12.0) < font.text_width("WWW", 12.0)
    assert font.width("i") < font.width("W")
    assert font.text_width("aaa", 24.0) == pytest.approx(2 * font.text_width("aaa", 12.0))
    tracked = font.text_width("abc", 10.0, tracking=1.0)
    assert tracked == pytest.approx(font.text_width("abc", 10.0) + 3.0)


@pytest.mark.skipif(not TIMES.exists(), reason="Times New Roman nao esta instalada")
def test_kern_reads_the_kern_table():
    font = FontEmbedder().load(TIMES)
    assert font.kern("A", "V") < 0, "o par AV da Times e negativo na tabela kern"
    assert font.kern("T", "o") < 0
    assert font.kern("n", "n") == 0.0


@pytest.mark.skipif(not GEORGIA.exists(), reason="Georgia nao esta instalada")
def test_kern_falls_back_to_gpos_when_there_is_no_kern_table():
    # Georgia ships GPOS only. The pair below is kerned there; A/V happens not to be.
    font = FontEmbedder().load(GEORGIA)
    assert font.kern('"', "A") <= 0.0
    assert font.kern("\u00e1", "\u00e1") == 0.0


@pytest.mark.skipif(not ARIAL.exists(), reason="Arial nao esta instalada")
def test_two_faces_get_distinct_resource_names():
    embedder = FontEmbedder()
    first = embedder.load(ARIAL)
    second = embedder.load(ARIAL, resource_name="F1")
    assert first.resource_name == "F1"
    assert second is first  # same file, same resource name -> cached

    if TIMES.exists():
        third = embedder.load(TIMES)
        assert third.resource_name == "F2"
        doc = PdfDocument()
        refs = embedder.finalise(doc)
        assert set(refs) == {"F1", "F2"}
        assert refs["F1"] != refs["F2"]
        assert embedder.finalise(doc) == refs  # idempotent


def test_loading_a_missing_font_raises():
    with pytest.raises(PdfWriteError, match="Nao foi possivel ler"):
        FontEmbedder().load(Path("nao-existe-xyz.ttf"))


def test_loading_garbage_raises():
    with pytest.raises(PdfWriteError, match="Nao foi possivel ler a fonte"):
        FontEmbedder().load_bytes(b"nao sou uma fonte", resource_name="F1")


def test_chess_fonts_from_the_project_registry_embed():
    fonts_module = pytest.importorskip("caissa.typeset.fonts")
    candidates: list[Path] = []
    for spec in fonts_module.available_specs():
        path = fonts_module.find_font_file(spec)
        if path is not None:
            candidates.append(path)
    if not candidates:
        pytest.skip("nenhuma fonte de xadrez instalada nesta maquina")

    embedded = 0
    refused = 0
    for path in candidates:
        embedder = FontEmbedder()
        try:
            font = embedder.load(path, resource_name="C1")
        except PdfWriteError:
            # A restricted licence or a corrupt table must be refused, not crashed on.
            refused += 1
            continue
        stream = ContentStream()
        stream.begin_text()
        stream.set_font("C1", 24)
        stream.text_position(20, 20)
        stream.show(font.encode("pnbrqk"))
        stream.end_text()
        doc = PdfDocument()
        refs = embedder.finalise(doc)
        doc.add_page(PdfPage(200, 200, stream.to_bytes(), resources={"Font": refs}))
        document = parse_pdf(doc.to_bytes())
        assert any(o.name("Subtype") == "CIDFontType2" for o in document.objects.values())
        embedded += 1
    assert embedded > 0, f"nenhuma das {len(candidates)} fontes de xadrez pode ser embutida"
    assert embedded + refused == len(candidates)


# --------------------------------------------------------------------------- #
# Outline
# --------------------------------------------------------------------------- #


def test_outline_two_levels():
    doc = simple_document(pages=4)
    doc.set_outline(
        [
            OutlineEntry(
                "Parte I",
                0,
                800.0,
                (
                    OutlineEntry("Capitulo 1", 1, 780.0),
                    OutlineEntry("Capitulo 2", 2, 780.0),
                ),
            ),
            OutlineEntry("Parte II", 3, 800.0),
        ]
    )
    data = doc.to_bytes()
    assert b"/Outlines" in data

    document = parse_pdf(data)
    catalog = next(o for o in document.objects.values() if o.name("Type") == "Catalog")
    outlines = document.object_for(catalog.ref("Outlines"))
    assert outlines.name("Type") == "Outlines"
    assert outlines.ref("First") is not None
    assert outlines.ref("Last") is not None
    # Two top-level entries plus two children, all open.
    assert outlines.number_value("Count") == 4

    first = document.object_for(outlines.ref("First"))
    assert b"/Title (Parte I)" in first.body
    assert first.ref("Parent") == outlines.number
    assert first.number_value("Count") == 2
    assert first.ref("Prev") is None

    child = document.object_for(first.ref("First"))
    assert b"/Title (Capitulo 1)" in child.body
    assert child.ref("Parent") == first.number
    sibling = document.object_for(child.ref("Next"))
    assert b"/Title (Capitulo 2)" in sibling.body
    assert sibling.ref("Prev") == child.number
    assert sibling.ref("Next") is None

    last = document.object_for(outlines.ref("Last"))
    assert b"/Title (Parte II)" in last.body
    assert last.ref("Prev") == first.number

    assert re.search(rb"/Dest\s*\[\s*[0-9]+\s+0\s+R\s*/XYZ\s+null\s+800\s+null\]", first.body)


def test_outline_rejects_a_page_that_does_not_exist():
    doc = simple_document(pages=1)
    doc.set_outline([OutlineEntry("Fantasma", 9, 700.0)])
    with pytest.raises(PdfWriteError, match="pagina 9"):
        doc.to_bytes()


# --------------------------------------------------------------------------- #
# Structure tree
# --------------------------------------------------------------------------- #


def tagged_document() -> PdfDocument:
    """A two-page tagged document with marked content on both pages."""
    doc = PdfDocument()
    for page_index in range(2):
        stream = ContentStream()
        stream.begin_marked_content("H1" if page_index == 0 else "P", 0)
        stream.rect(10, 10, 20, 20)
        stream.fill()
        stream.end_marked_content()
        stream.begin_marked_content("P", 1)
        stream.rect(40, 10, 20, 20)
        stream.fill()
        stream.end_marked_content()
        doc.add_page(PdfPage(400, 400, stream.to_bytes()))
    doc.set_struct_tree(
        StructElement(
            "Document",
            (
                StructElement(
                    "Sect",
                    (
                        StructElement("H1", (), 0, 0, title="Introducao"),
                        StructElement("P", (), 0, 1),
                    ),
                ),
                StructElement(
                    "Sect",
                    (
                        StructElement("P", (), 1, 0),
                        StructElement("Figure", (), 1, 1, alt="Diagrama apos 1.e4"),
                    ),
                ),
            ),
        )
    )
    doc.set_metadata(PdfMetadata(title="Livro marcado", language="pt-BR"))
    return doc


def test_struct_tree_is_emitted():
    data = tagged_document().to_bytes()
    for marker in (b"/StructTreeRoot", b"/MarkInfo", b"/ParentTree", b"/RoleMap"):
        assert marker in data, f"{marker.decode()} ausente"

    document = parse_pdf(data)
    catalog = next(o for o in document.objects.values() if o.name("Type") == "Catalog")
    assert b"/MarkInfo << /Marked true >>" in catalog.body
    assert b"/Lang (pt-BR)" in catalog.body

    root = document.object_for(catalog.ref("StructTreeRoot"))
    assert root.name("Type") == "StructTreeRoot"
    assert root.number_value("ParentTreeNextKey") == 2
    for tag in ("H1", "Figure", "LBody"):
        assert f"/{tag} /".encode() in root.body, f"RoleMap sem {tag}"
    assert b"/Artifact /NonStruct" in root.body

    document_element = document.object_for(root.ref("K"))
    assert document_element.name("S") == "Document"
    assert document_element.ref("P") == root.number


def test_parent_tree_maps_struct_parents_to_mcids():
    document = parse_pdf(tagged_document().to_bytes())
    catalog = next(o for o in document.objects.values() if o.name("Type") == "Catalog")
    root = document.object_for(catalog.ref("StructTreeRoot"))
    parent_tree = document.object_for(root.ref("ParentTree"))

    nums = re.search(rb"/Nums\s*\[(.*)\]", parent_tree.body, re.S).group(1)
    pairs = re.findall(rb"([0-9]+)\s+([0-9]+)\s+[0-9]+\s+R", nums)
    assert [int(key) for key, _ in pairs] == [0, 1], "chaves do /Nums fora de ordem"

    pages = [o for o in document.objects.values() if o.name("Type") == "Page"]
    assert sorted(int(p.number_value("StructParents")) for p in pages) == [0, 1]

    for key, array_ref in pairs:
        array = document.object_for(int(array_ref))
        entries = re.findall(rb"([0-9]+)\s+[0-9]+\s+R", array.body)
        assert len(entries) == 2, f"/ParentTree[{int(key)}] deveria ter dois MCIDs"
        for element_ref in entries:
            element = document.object_for(int(element_ref))
            assert element.name("Type") == "StructElem"
            assert element.ref("Pg") is not None


def test_struct_element_validates_its_tag_and_mcid():
    with pytest.raises(PdfWriteError, match="Tag de estrutura desconhecida"):
        StructElement("Paragrafo")
    with pytest.raises(PdfWriteError, match="sem page_index"):
        StructElement("P", (), None, 0)
    assert "LBody" in STRUCT_TAGS


def test_struct_tree_can_be_removed():
    doc = tagged_document()
    doc.set_struct_tree(None)
    data = doc.to_bytes()
    assert b"/StructTreeRoot" not in data
    assert b"/MarkInfo" not in data


# --------------------------------------------------------------------------- #
# Links and named destinations
# --------------------------------------------------------------------------- #


def test_link_annotations_are_emitted():
    doc = PdfDocument()
    doc.add_page(
        PdfPage(
            595.28,
            841.89,
            vector_content(),
            annotations=[
                LinkAnnotation((72, 700, 300, 720), uri="https://lichess.org"),
                LinkAnnotation((72, 660, 300, 680), page_index=1, top=780.0),
                LinkAnnotation((72, 620, 300, 640), dest_name="cap1"),
            ],
        )
    )
    doc.add_page(PdfPage(595.28, 841.89, vector_content()))
    doc.add_named_destination("cap1", 1, 780.0)
    document = parse_pdf(doc.to_bytes())
    annots = [o for o in document.objects.values() if o.name("Subtype") == "Link"]
    assert len(annots) == 3
    assert any(b"/URI (https://lichess.org)" in o.body for o in annots)
    assert any(b"/Dest (cap1)" in o.body for o in annots)
    assert any(re.search(rb"/Dest\s*\[[0-9]+ 0 R /XYZ", o.body) for o in annots)

    catalog = next(o for o in document.objects.values() if o.name("Type") == "Catalog")
    dests_ref = re.search(rb"/Names\s*<<\s*/Dests\s+([0-9]+)\s+0\s+R", catalog.body)
    assert dests_ref, "catalogo sem arvore de nomes /Dests"
    dests = document.object_for(int(dests_ref.group(1)))
    assert b"/Names [(cap1)" in dests.body
    target = document.object_for(int(re.search(rb"/D\s*\[\s*([0-9]+)", dests.body).group(1)))
    assert target.name("Type") == "Page"


def test_link_annotation_requires_exactly_one_target():
    with pytest.raises(PdfWriteError, match="exatamente um destino"):
        LinkAnnotation((0, 0, 1, 1))
    with pytest.raises(PdfWriteError, match="exatamente um destino"):
        LinkAnnotation((0, 0, 1, 1), page_index=0, uri="https://x.test")


def test_unknown_named_destination_is_refused():
    doc = PdfDocument()
    doc.add_page(
        PdfPage(100, 100, b"", annotations=[LinkAnnotation((0, 0, 1, 1), dest_name="ausente")])
    )
    with pytest.raises(PdfWriteError, match="nao foi registrado"):
        doc.to_bytes()


# --------------------------------------------------------------------------- #
# Metadata / XMP
# --------------------------------------------------------------------------- #


def xmp_of(doc: PdfDocument) -> bytes:
    """Pull the XMP packet out of a built document."""
    document = parse_pdf(doc.to_bytes())
    metadata = next(o for o in document.objects.values() if o.name("Type") == "Metadata")
    assert metadata.name("Subtype") == "XML"
    return metadata.data()


def test_xmp_is_well_formed_xml_and_carries_the_title():
    doc = simple_document()
    doc.set_metadata(
        PdfMetadata(
            title="Aberturas & finais <do> xadrez",
            author="A. Karpov",
            subject="Estudo",
            keywords="xadrez, aberturas",
            creator="Caissa Studio",
            language="pt-BR",
            created=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
            modified=datetime(2026, 9, 7, 13, 30, tzinfo=UTC),
        )
    )
    packet = xmp_of(doc)

    # S314: the XML here was produced by the module under test, not by a stranger;
    # parsing it with the stdlib is the whole point of the assertion.
    root = ElementTree.fromstring(packet.decode("utf-8"))  # noqa: S314
    assert root.tag.endswith("xmpmeta")

    text = packet.decode("utf-8")
    assert "Aberturas &amp; finais &lt;do&gt; xadrez" in text
    assert "A. Karpov" in text
    assert "<dc:language>" in text
    assert "2026-09-07T12:00:00+00:00" in text
    assert "http://ns.adobe.com/pdf/1.3/" in text
    assert "pdfaid" not in text


def test_docinfo_and_xmp_agree_on_the_title():
    doc = simple_document()
    doc.set_metadata(PdfMetadata(title="Titulo unico", producer="Caissa"))
    data = doc.to_bytes()
    document = parse_pdf(data)
    info = document.object_for(int(re.search(rb"/Info\s+([0-9]+)", document.trailer).group(1)))
    assert b"/Title (Titulo unico)" in info.body
    assert b"/Producer (Caissa)" in info.body
    assert "Titulo unico" in xmp_of(doc).decode("utf-8")


def test_pdf_dates_carry_an_explicit_offset():
    doc = simple_document()
    doc.set_metadata(PdfMetadata(created=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)))
    document = parse_pdf(doc.to_bytes())
    info = document.object_for(int(re.search(rb"/Info\s+([0-9]+)", document.trailer).group(1)))
    assert rb"/CreationDate (D:20260102030405+00'00')" in info.body


# --------------------------------------------------------------------------- #
# PDF/A
# --------------------------------------------------------------------------- #


def test_pdfa_caveats_are_non_empty_and_portuguese():
    caveats = pdfa_caveats()
    assert caveats
    assert caveats == PDFA_CAVEATS
    assert all(isinstance(text, str) and text for text in caveats)
    assert any("ICC" in text for text in caveats)
    assert any("NAO e conformante" in text for text in caveats)


def test_pdfa_emits_conformance_and_an_output_intent():
    doc = simple_document()
    doc.set_metadata(PdfMetadata(title="Livro PDF/A", pdf_a=True))
    data = doc.to_bytes()

    packet = xmp_of(doc).decode("utf-8")
    ElementTree.fromstring(packet)  # noqa: S314 -- our own output, see above
    assert "pdfaid:conformance" in packet
    assert "<pdfaid:part>2</pdfaid:part>" in packet
    assert "<pdfaid:conformance>B</pdfaid:conformance>" in packet
    assert "http://www.aiim.org/pdfa/ns/id/" in packet

    document = parse_pdf(data)
    catalog = next(o for o in document.objects.values() if o.name("Type") == "Catalog")
    assert b"/OutputIntents" in catalog.body
    assert b"/OutputConditionIdentifier (sRGB)" in catalog.body
    assert b"/GTS_PDFA1" in catalog.body
    # Honesty check: no profile was supplied, so none may be claimed.
    assert b"/DestOutputProfile" not in catalog.body
    assert b"/ViewerPreferences << /DisplayDocTitle true >>" in catalog.body


def test_pdfa_embeds_a_supplied_icc_profile():
    doc = simple_document()
    doc.set_metadata(PdfMetadata(title="Com perfil", pdf_a=True, icc_profile=b"fake-icc" * 8))
    document = parse_pdf(doc.to_bytes())
    catalog = next(o for o in document.objects.values() if o.name("Type") == "Catalog")
    assert b"/DestOutputProfile" in catalog.body
    profile_ref = int(
        re.search(rb"/DestOutputProfile\s+([0-9]+)\s+[0-9]+\s+R", catalog.body).group(1)
    )
    assert document.object_for(profile_ref).data() == b"fake-icc" * 8


# --------------------------------------------------------------------------- #
# Streams, compression and error handling
# --------------------------------------------------------------------------- #


def test_streams_are_flate_compressed_by_default_and_can_be_turned_off():
    payload = b"BT /F1 12 Tf ET " * 400
    doc = PdfDocument()
    compressed = doc.add_stream(payload)
    plain = doc.add_stream(payload, compress=False)
    doc.add_page(PdfPage(100, 100, b""))
    document = parse_pdf(doc.to_bytes())

    assert b"/FlateDecode" in document.object_for(compressed.number).body
    assert document.object_for(compressed.number).data() == payload
    assert b"/FlateDecode" not in document.object_for(plain.number).body
    assert document.object_for(plain.number).stream == payload
    assert len(document.object_for(compressed.number).stream) < len(payload)


def test_add_stream_refuses_to_let_the_caller_set_length_or_filter():
    doc = PdfDocument()
    with pytest.raises(PdfWriteError, match="Length"):
        doc.add_stream(b"x", {"Length": 1})
    with pytest.raises(PdfWriteError, match="Filter"):
        doc.add_stream(b"x", {"Filter": PdfName("FlateDecode")})


def test_empty_document_is_refused():
    with pytest.raises(PdfWriteError, match="pelo menos uma pagina"):
        PdfDocument().to_bytes()


def test_unsupported_version_is_refused():
    with pytest.raises(PdfWriteError, match="Versao de PDF nao suportada"):
        PdfDocument(version="2.0")
    assert PdfDocument(version="1.4").version == "1.4"


def test_to_bytes_is_repeatable_and_does_not_mutate_the_document():
    doc = tagged_document()
    first = doc.to_bytes()
    second = doc.to_bytes()
    assert first == second
    assert len(parse_pdf(first).objects) == len(parse_pdf(second).objects)


def test_duplicate_named_destination_with_a_different_target_is_refused():
    doc = simple_document(pages=2)
    doc.add_named_destination("x", 0, 100.0)
    doc.add_named_destination("x", 0, 100.0)
    with pytest.raises(PdfWriteError, match="Destino nomeado duplicado"):
        doc.add_named_destination("x", 1, 100.0)


def test_raw_bytes_payloads_pass_through_verbatim():
    doc = PdfDocument()
    ref = doc.add_object(b"<< /Custom /Value >>")
    doc.add_page(PdfPage(10, 10, b"", extra={"Custom": ref}))
    document = parse_pdf(doc.to_bytes())
    assert b"/Custom /Value" in document.object_for(ref.number).body
