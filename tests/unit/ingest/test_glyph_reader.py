"""The trunk's page reader as the importer's OCR provider (2026-10-12).

Nothing here loads the trunk or its classifier: the conversion is tested on
a ``PaginaLida``-shaped object built here, and the importer's choice of
reader on a stand-in that ``TrunkPageReader.build`` is patched to return.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from caissa.core.model import plain_text
from caissa.ingest.pdf import PdfImportOptions, import_pdf
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.glyph_reader import TrunkPageReader, page_text_from_pagina
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan

from .conftest import PageSpec


def _linha(texto: str, bbox: tuple[float, float, float, float], **extra: object) -> SimpleNamespace:
    fields: dict[str, object] = {"texto": texto, "bbox": bbox, "confianca": 0.9,
                                 "procedencia": "glifo", "negrito": None, "italico": None,
                                 "negrito_em": (), "italico_em": ()}
    fields.update(extra)
    return SimpleNamespace(**fields)


def _pagina(unidade: str = "pt") -> SimpleNamespace:
    """Two columns, a diagram block between two text blocks, a running head."""
    s = 220.0 / 72.0 if unidade == "px" else 1.0
    bloco_a = SimpleNamespace(linhas=(
        _linha("E.Jackson – D.Baird", (80 * s, 100 * s, 260 * s, 112 * s), negrito=True),
        _linha("England – USA 1896", (90 * s, 114 * s, 250 * s, 124 * s)),
    ))
    diagrama = SimpleNamespace(linhas=(), bbox=(80 * s, 130 * s, 260 * s, 310 * s), indice=0)
    bloco_b = SimpleNamespace(linhas=(
        _linha("1.♖h8†!! ♔xh8 2.♕g8#", (80 * s, 320 * s, 240 * s, 332 * s),
               negrito_em=((0, 7),)),
    ))
    bloco_c = SimpleNamespace(linhas=(_linha("2.♕xh3", (320 * s, 100 * s, 380 * s, 112 * s)),))
    return SimpleNamespace(
        unidade=unidade, largura=453.6, altura=666.0,
        colunas=(SimpleNamespace(blocos=(bloco_a, diagrama, bloco_b)),
                 SimpleNamespace(blocos=(bloco_c,))),
        cabecalho=_linha("Solutions", (200 * s, 40 * s, 260 * s, 52 * s)),
        rodape=None,
    )


def _frame() -> PageFrame:
    return PageFrame(index=18, width=453.6, height=666.0, text_width=453.6, text_height=666.0)


def test_the_trunk_page_becomes_lines_block_by_block():
    text = page_text_from_pagina(_pagina(), _frame())
    assert text.source == "glifo"
    assert [line.text for line in text.lines] == [
        "E.Jackson – D.Baird", "England – USA 1896", "1.♖h8†!! ♔xh8 2.♕g8#", "2.♕xh3", "Solutions",
    ]
    # One block per trunk block, the diagram block skipped without a gap in meaning.
    assert [line.block_index for line in text.lines] == [0, 0, 1, 2, 3]
    assert text.lines[0].box == pytest.approx((80.0, 100.0, 260.0, 112.0))
    assert text.lines[0].spans[0].bold is True
    assert text.lines[0].spans[0].confidence == pytest.approx(0.9)
    assert text.lines[0].spans[0].engine == "glifo"


def test_bold_runs_split_the_line_into_spans():
    text = page_text_from_pagina(_pagina(), _frame())
    moves = text.lines[2]
    assert [(s.text, s.bold) for s in moves.spans] == [("1.♖h8†!", True), ("! ♔xh8 2.♕g8#", False)]
    assert moves.spans[0].box[0] == pytest.approx(80.0)
    assert moves.spans[-1].box[2] == pytest.approx(240.0)


def test_pixel_pages_are_brought_back_to_points():
    in_px = page_text_from_pagina(_pagina("px"), _frame(), dpi=220)
    in_pt = page_text_from_pagina(_pagina("pt"), _frame())
    for a, b in zip(in_px.lines, in_pt.lines, strict=True):
        assert a.box == pytest.approx(b.box, abs=1e-6)


def test_build_says_why_without_the_trunk(monkeypatch):
    def missing() -> None:
        raise FileNotFoundError("sem tronco")

    monkeypatch.setattr("caissa.vision.classify.cvoff.ensure_cvoff_on_path", missing)
    reader, why = TrunkPageReader.build()
    assert reader is None
    assert "sem tronco" in (why or "")


class _FakeReader(TrunkPageReader):
    """Answers every page with one line, without the trunk."""

    calls: list[int]

    def __call__(self, page, frame, verdict):  # type: ignore[override]
        self.pages_read.append(frame.index)
        box = (72.0, 100.0, 300.0, 112.0)
        return PageText(frame=frame, lines=(TextLine(
            box=box, spans=(TextSpan(text="lido pelo glifo", box=box, size=10.0,
                                     confidence=0.8, engine="glifo"),)),), source="glifo")


def test_auto_picks_the_glyph_reader_when_it_builds(pdf_file, monkeypatch):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    built: list[str] = []

    def build(cls=None, **_kw):
        built.append("glifo")
        return _FakeReader(), None

    monkeypatch.setattr(TrunkPageReader, "build", classmethod(lambda cls, **kw: build(cls, **kw)))
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False, page_reader="auto"))
    assert result.report.pages[0].ocr_engine == "glifo"
    assert built == ["glifo"]
    assert result.report.pages[0].source == "ocr"
    assert plain_text(result.document.body[0].content) == "lido pelo glifo"
    assert result.report.counters["glyph_reader_pages"] == 1
    assert any("leitor de glifo do tronco" in note for note in result.report.notes)


def test_servico_never_asks_for_the_glyph_reader(pdf_file, monkeypatch):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])

    def never(cls, **_kw):
        raise AssertionError("o leitor de glifo não devia ser construído")

    monkeypatch.setattr(TrunkPageReader, "build", classmethod(never))
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False, page_reader="servico",
                                               enable_ocr=False))
    assert result.report.pages[0].source != "ocr"


def test_glifo_asked_and_missing_is_a_note_not_a_stop(pdf_file, monkeypatch):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    monkeypatch.setattr(TrunkPageReader, "build",
                        classmethod(lambda cls, **kw: (None, "sem tronco de teste")))
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False, page_reader="glifo"))
    assert any("sem tronco de teste" in note for note in result.report.notes)


def test_an_unknown_reader_name_is_refused(pdf_file):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    with pytest.raises(ValueError, match="page_reader"):
        import_pdf(path, PdfImportOptions(detect_diagrams=False, page_reader="tesseract"))
