"""Styled spans, figurines, images and rules from one page."""

from __future__ import annotations

import pytest

from caissa.ingest.pdf.document import open_pdf
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.textlayer import (
    FigurineMapper,
    TextLine,
    TextSpan,
    extract_page_text,
    page_text_from_ocr,
    stroke_bold_fonts,
)

from .conftest import PageSpec, find_font, requires_pymupdf

pytestmark = requires_pymupdf


def _page_text(doc, index=0, **kwargs):
    frame = doc.frame(index)
    with doc.locked() as raw:
        return extract_page_text(raw[index], frame, **kwargs)


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #


def test_bold_and_italic_come_from_flags_and_names(pdf_file):
    spec = PageSpec()
    spec.text("regular", 72, 100, font="helv")
    spec.text("negrito", 72, 120, font="hebo")
    spec.text("itálico", 72, 140, font="heit")
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    by_text = {line.text: line.spans[0] for line in text.lines}
    assert not by_text["regular"].bold
    assert not by_text["regular"].italic
    assert by_text["negrito"].bold
    assert by_text["itálico"].italic
    assert by_text["regular"].size == pytest.approx(11.0)
    assert by_text["regular"].font == "Helvetica"


def test_spans_sharing_a_style_are_merged_and_boxes_are_page_space(pdf_file):
    spec = PageSpec(size=(300.0, 200.0), rotation=90)
    spec.text("giro", 50, 100)
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    assert len(text.lines) == 1
    line = text.lines[0]
    # A 300x200 page turned 90 cw is 200 wide; text at x=50 in text space
    # lands near the top (y = x) and to the right (x = 200 - y).
    assert line.box[1] == pytest.approx(50.0, abs=1.0)
    assert 80.0 < line.box[0] < 120.0
    assert text.frame.is_rotated


def test_figurine_font_maps_piece_letters_by_context():
    mapper = FigurineMapper()
    assert mapper.map_text("Nf3", "SemFigBold") == "♘f3"
    assert mapper.map_text("Rxe1", "ABCDEF+FigurineCB") == "♖xe1"
    assert mapper.map_text("R1e2", "Figurine") == "♖1e2"
    assert mapper.map_text("Nbd7", "Figurine") == "♘bd7"
    assert mapper.map_text("Black's threat", "SemFigNormal") == "Black's threat"
    assert mapper.map_text("K", "SemFigNormal") == "♔", "isolated letter is a figurine"
    assert mapper.map_text("Now", "SemFigNormal") == "Now"
    assert mapper.count == 5


def test_figurine_font_recognition_excludes_chessboard():
    mapper = FigurineMapper(extra_fonts=("MinhaFonte",))
    assert mapper.is_figurine("SemFigBold")
    assert mapper.is_figurine("ABCDEF+ChessMerida")
    assert not mapper.is_figurine("Chessboard")
    assert not mapper.is_figurine("TimesNewRoman")
    assert mapper.is_figurine("MinhaFonte-Regular")


def test_informator_symbols_are_translated():
    mapper = FigurineMapper()
    assert mapper.is_informator("Informator")
    assert mapper.map_informator("¢ £ ¥", "Informator") == "⩲ ⩱ ±"
    assert mapper.informator_count == 3


def test_diagram_font_spans_are_marked_not_dropped(pdf_file, merida_font):
    spec = PageSpec()
    spec.text("rnbqkbnr", 72, 100, size=20, fontfile=str(merida_font))
    spec.text("prosa normal", 72, 200)
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    kinds = {line.text.strip(): line.is_diagram for line in text.lines}
    assert kinds["rnbqkbnr"] is True
    assert kinds["prosa normal"] is False
    assert text.lines[0].spans[0].diagram_font == "merida"


@pytest.mark.skipif(
    find_font("times.ttf", "arial.ttf") is None, reason="sem TrueType com ligaduras"
)
def test_ligatures_are_expanded(pdf_file):
    """The IR carries plain text; the typesetter re-forms ligatures.

    Needs a face that *has* the ``ﬁ``/``ﬂ`` glyphs -- the base-14 Helvetica
    does not, and renders them as a dot.
    """
    spec = PageSpec()
    spec.text("ﬁnal ﬂuido", 72, 100, fontfile=str(find_font("times.ttf", "arial.ttf")))
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    assert text.lines[0].text == "final fluido"


# --------------------------------------------------------------------------- #
# Images and rules
# --------------------------------------------------------------------------- #


def test_image_placements_are_reported_in_page_space(pdf_file):
    spec = PageSpec(images=[(100.0, 100.0, 200.0, 150.0, 40, 20)])
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    assert len(text.images) == 1
    image = text.images[0]
    assert image.box == pytest.approx((100.0, 100.0, 200.0, 150.0), abs=0.5)
    assert (image.width, image.height) == (40, 20)
    assert image.axis_aligned
    assert not image.flipped


def test_rules_are_thin_wide_strokes_only(pdf_file):
    spec = PageSpec(
        rects=[
            (72.0, 700.0, 200.0, 700.5),  # footnote rule
            (72.0, 100.0, 300.0, 300.0),  # a box, not a rule
            (72.0, 400.0, 80.0, 400.5),  # too short
        ]
    )
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    assert len(text.rules) == 1
    assert text.rules[0][1] == pytest.approx(700.0, abs=0.5)


# --------------------------------------------------------------------------- #
# OCR adapter and bold by ink
# --------------------------------------------------------------------------- #


def test_ocr_results_adapt_to_the_same_shape():
    from caissa.ocr.types import BBox, OcrChar, OcrLine, OcrResult, OcrWord

    word = OcrWord(text="lance", box=BBox(100, 200, 50, 12), confidence=0.8, chars=())
    line = OcrLine(words=(word,), box=BBox(100, 200, 50, 12), font_size=12.0)
    result = OcrResult(engine="tesseract", lang="por", lines=(line,))
    frame = PageFrame.synthetic(3, 612.0, 792.0)
    text = page_text_from_ocr(result, frame, dpi=144.0)
    assert text.source == "tesseract"
    assert text.page_index == 3
    assert text.lines[0].text == "lance"
    assert text.lines[0].box == pytest.approx((50.0, 100.0, 75.0, 106.0))
    assert text.lines[0].confidence == pytest.approx(0.8)
    assert isinstance(text.lines[0].spans[0], TextSpan)
    _ = OcrChar  # imported to prove the type exists for callers


def test_stroke_bold_measures_the_ink(pdf_file):
    """A bold face renamed to nothing is still bold when the ink says so."""
    pages = []
    for _ in range(4):
        spec = PageSpec()
        for i in range(24):
            spec.text("corpo do texto em peso normal para a medida", 72, 100 + i * 14, font="helv")
        for i in range(8):
            spec.text("linha principal em negrito para a medida", 72, 460 + i * 14, font="hebo")
        pages.append(spec)
    path = pdf_file(pages)
    with open_pdf(path) as doc:
        bold = stroke_bold_fonts(doc, list(range(4)), sample_pages=4)
    assert "Helvetica-Bold" in bold
    assert "Helvetica" not in bold


def test_textline_helpers():
    span = TextSpan(text="a", box=(0, 0, 1, 1), size=10.0, confidence=0.5)
    line = TextLine(box=(0, 0, 1, 1), spans=(span, TextSpan(text=" ", box=(1, 0, 2, 1))))
    assert line.text == "a "
    assert line.size == 10.0
    assert line.confidence == 0.5
    assert not line.is_diagram


@pytest.mark.skipif(find_font("arial.ttf") is None, reason="sem Arial para o teste de estilo")
def test_named_font_file_keeps_its_family_name(pdf_file):
    spec = PageSpec()
    spec.text("Arial aqui", 72, 100, fontfile=str(find_font("arial.ttf")))
    path = pdf_file([spec])
    with open_pdf(path) as doc:
        text = _page_text(doc)
    assert "Arial" in text.lines[0].spans[0].font
