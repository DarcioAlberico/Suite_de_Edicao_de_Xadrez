"""The text layer's ligatures, read as letters everywhere — OCR_UI_ROADMAP_C2 passo A14.

B12 folded ``ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ`` out of every engine's output, and the importer's
extractor has always read the layer with ``TEXT_PRESERVE_LIGATURES`` off.  Three
readers of the layer still used PyMuPDF's defaults: the level-0 engine (whose
``recognize_page`` never passes through the engines' fold), the layout's page
lines, and the search index — measured on the Polgar: 6 ligatures on page 6 and
5 on page 9 out of the level-0 engine (``OCR_UI_REPORT_C2_FASE5.md`` §A14).  The
PDF here is built with a TrueType face that has the ligature glyphs; the
sabotage is the old flags, which bring the U+FB01 back.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf")

from caissa.index.sources import PdfTextSource  # noqa: E402
from caissa.ocr.engines import normalize  # noqa: E402
from caissa.ocr.engines.pdf_text_layer import PdfTextLayerEngine  # noqa: E402
from caissa.ocr.layout.analyze import lines_from_pdf_page  # noqa: E402

LIGATURE = re.compile("[\ufb00-\ufb06]")
FACE = Path(r"C:\Windows\Fonts\times.ttf")
TEXT = ("The \ufb01rst \ufb02ank attack of the \ufb01nal is e\ufb00ective: "
        "½ point, move 2² and № 12 stay as printed.")


@pytest.fixture
def ligature_pdf(tmp_path: Path) -> Path:
    if not FACE.exists():
        pytest.skip("Times New Roman não está nesta máquina")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_font(fontname="tnr", fontfile=str(FACE))
    for n in range(12):
        page.insert_text((60, 80 + 22 * n), TEXT, fontname="tnr", fontsize=11)
    path = tmp_path / "ligaduras.pdf"
    doc.save(path)
    return path


def test_the_default_flags_would_carry_the_ligature(ligature_pdf: Path) -> None:
    """The premise: PyMuPDF's defaults keep U+FB01 on this page."""
    with pymupdf.open(ligature_pdf) as doc:
        assert LIGATURE.search(doc[0].get_text("text"))


def test_the_level_zero_engine_reads_the_letters(ligature_pdf: Path) -> None:
    with pymupdf.open(ligature_pdf) as doc:
        result = PdfTextLayerEngine().recognize_page(doc[0], lang="eng", force=True)
    assert "first flank" in result.text and "effective" in result.text
    assert not LIGATURE.search(result.text)
    for line in result.lines:
        for word in line.words:
            if word.chars:
                assert len(word.chars) == len(word.text), word.text


def test_the_signs_that_are_not_ligatures_stay(ligature_pdf: Path) -> None:
    with pymupdf.open(ligature_pdf) as doc:
        result = PdfTextLayerEngine().recognize_page(doc[0], lang="eng", force=True)
    assert "½" in result.text and "²" in result.text and "№" in result.text


def test_the_layout_lines_and_the_search_index_read_the_letters(ligature_pdf: Path) -> None:
    with pymupdf.open(ligature_pdf) as doc:
        lines = lines_from_pdf_page(doc[0])
    assert lines and not any(LIGATURE.search(line.text) for line in lines)
    units = list(PdfTextSource(ligature_pdf).units())
    # MuPDF writes this face's space as U+00A0; the words are what matter here.
    assert units and "first flank" in " ".join(units[0].text.split())
    assert not LIGATURE.search(units[0].text)


def test_the_sabotage_old_flags_bring_the_ligature_back(ligature_pdf: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    import caissa.ocr.engines.pdf_text_layer as level0

    defaults = {"text": pymupdf.TEXTFLAGS_TEXT, "dict": pymupdf.TEXTFLAGS_DICT,
                "rawdict": pymupdf.TEXTFLAGS_RAWDICT}
    monkeypatch.setattr(level0, "text_layer_flags", lambda mode="text": defaults[mode])
    with pymupdf.open(ligature_pdf) as doc:
        result = PdfTextLayerEngine().recognize_page(doc[0], lang="eng", force=True)
    assert LIGATURE.search(result.text)


def test_the_helper_changes_only_the_ligature_bit() -> None:
    for mode, name in (("text", "TEXTFLAGS_TEXT"), ("dict", "TEXTFLAGS_DICT"),
                       ("rawdict", "TEXTFLAGS_RAWDICT")):
        default = int(getattr(pymupdf, name))
        assert normalize.text_layer_flags(mode) | int(pymupdf.TEXT_PRESERVE_LIGATURES) == default | int(
            pymupdf.TEXT_PRESERVE_LIGATURES)
        assert not normalize.text_layer_flags(mode) & int(pymupdf.TEXT_PRESERVE_LIGATURES)
