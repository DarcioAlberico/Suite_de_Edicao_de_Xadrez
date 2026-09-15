"""F2 against the reference collection (docs/quality/CORPUS.md).

These are the pages the F2 report's side-by-side reading was done on; each
assertion below is something that was checked against the printed page by
eye on 2026-09-11.  They skip when the collection is absent.
"""

from __future__ import annotations

import pytest

from caissa.core.model import Diagram, Heading, Paragraph, plain_text
from caissa.ingest.pdf import PdfImportOptions, import_pdf, open_pdf

from .conftest import corpus_file, paragraphs_of, requires_pymupdf

pytestmark = [requires_pymupdf, pytest.mark.golden, pytest.mark.slow]


def _blocks(document):
    return [b for b in document.body if isinstance(b, (Paragraph, Heading, Diagram))]


def test_dvoretsky_page_202_matches_the_printed_page():
    """Two columns, two vector diagrams, captions under the boards.

    Read against the page: left column -- game header, prose, two analysis
    paragraphs; right column -- game header, bold move line, analysis,
    bold move line, prose, analysis; a bold section head at the foot.
    """
    path = corpus_file("Dvoretsky - Dvoretsky's Endgame Manual")
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=[201], lang="eng", games=False))
    assert result.report.pages[0].source == "text-layer"
    assert result.report.pages[0].columns == 2
    diagrams = [b for b in result.document.body if isinstance(b, Diagram)]
    assert [d.fen.split()[0] for d in diagrams] == [
        "6B1/8/2K5/8/8/5k1P/8/8",
        "5B2/p7/3p4/PPk5/8/8/4K3/8",
    ]
    assert [d.label for d in diagrams] == ["4-12", "4-13"]
    assert all(d.stipulation == "Brancas jogam" for d in diagrams)
    texts = paragraphs_of(result.document)
    starts = [t[:28] for t in texts]
    assert starts == [
        "4/2. G.van Breukelen 1969",
        "Is it possible to prevent th",
        "1.Kd7!! Kf4 2.Ke8! Kg5 (2...",
        "1.Kd6? leads only to a draw:",
        "4/3. A.Gerbstman 1928",
        "1.b6 axb6",
        "1...Kc6 2.Be7! axb6 (2...Kb7",
        "2.a6 Kc6 3.Be7!",
        "Thanks to the threat of 4.Bd",
        "3...Kc7 (3...b5 4.Bd8 d5 5.K",
        "Pawns at h6 and h7",
    ], starts
    assert isinstance(result.document.body[-1], Heading)
    # No coordinate label and no consumed caption survives as prose.
    assert not any(t in ("8", "1", "a b c d e f g h", "4-12", "W?", "4/2") for t in texts)


def test_dvoretsky_analysis_continues_across_the_page_break():
    path = corpus_file("Dvoretsky - Dvoretsky's Endgame Manual")
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=[205, 206], lang="eng", games=False))
    joined = next(
        b
        for b in result.document.body
        if isinstance(b, Paragraph) and plain_text(b.content).startswith("1.Rh8! d2 2.g8=Q")
    )
    assert "3.Ka2 Qb3+! 4.Qxb3 axb3+" in plain_text(joined.content)
    assert joined.provenance is not None
    assert joined.provenance.note == "continua até a página 206"
    assert joined.props.style == "Movetext"


def test_polgar_diagrams_are_read_exactly_from_the_skak_font():
    """Six diagrams a page, read from ``SkakNew-Diagram`` -- no model, no raster."""
    path = corpus_file("Polgar,_Laszlo_Chess_5334")
    # Three pages: the running heads need three repetitions to be furniture.
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=[300, 301, 302], lang="eng"))
    assert all(p.source == "text-layer" for p in result.report.pages), result.report.pages
    diagrams = [b for b in result.document.body if isinstance(b, Diagram)]
    assert [d.number for d in diagrams][:6] == [1699, 1700, 1701, 1702, 1703, 1704]
    assert len(diagrams) == 18
    # Checked square by square against the page: problem 1699.
    assert diagrams[0].fen.split()[0] == "2Q5/2K5/8/8/8/5np1/4R1R1/5k2"
    assert all(d.recognition.path.value == "vector" for d in diagrams)
    assert result.report.furniture_patterns >= 2, "título corrente e cabeçalho de seção"
    assert not paragraphs_of(result.document), "páginas de problemas não têm prosa"


def test_a_scan_without_a_text_layer_imports_as_pictures_when_ocr_is_off():
    path = corpus_file("Mauricio Flores Rios")
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=[100, 101], enable_ocr=False))
    assert [p.source for p in result.report.pages] == ["image-only", "image-only"]
    kinds = [type(b).__name__ for b in result.document.body]
    assert kinds == ["ImageBlock", "ImageBlock"]
    assert result.report.counters["scanned_pages"] == 2


def test_a_scan_without_a_text_layer_is_read_by_default():
    """Sol §SOL-1: no callback, no option — the scanned page comes back as text,
    with the OCR's own decision and provenance on every block."""
    from caissa.core.model import Paragraph, SourceKind

    from caissa.ocr.engines.tesseract import find_tesseract

    if find_tesseract() is None:
        pytest.skip("Tesseract não instalado")
    path = corpus_file("Mauricio Flores Rios")
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=[100, 101], lang="eng"))
    assert [p.source for p in result.report.pages] == ["ocr", "ocr"]
    for page in result.report.pages:
        assert page.ocr_engine == "tesseract"
        assert page.ocr_dpi == 300.0
        assert sum(page.ocr_decisions.values()) >= 1
        assert page.ocr_decisions["abstained"] < sum(page.ocr_decisions.values())
    paragraphs = [b for b in result.document.body if isinstance(b, Paragraph)]
    assert len(paragraphs) >= 10
    assert all(p.provenance is not None and p.provenance.kind is SourceKind.OCR
               for p in paragraphs)
    assert all(p.provenance.engine == "tesseract" for p in paragraphs)
    text = " ".join(paragraphs_of(result.document))
    assert "critical position" in text
    # Nothing below the bar is imported without a mark: every review item
    # has its page and rectangle.
    for item in result.report.review_items:
        assert item.decision in ("review", "abstained")
        assert item.rect[2] > item.rect[0]


def test_nunn_ocr_layer_keeps_the_paragraphs_whole():
    """An OCR'd layer that starts a new block every few lines must not split prose.

    Page 150 has four paragraphs in the left column; the layer cuts them into
    blocks 0/1/2 at arbitrary lines.  Checked against the printed page.
    """
    path = corpus_file("Nunn J. Secrets of Minor")
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=[150], lang="eng"))
    texts = [t for t in paragraphs_of(result.document) if len(t) > 60]
    # OCR_UI_ROADMAP passo 2: this layer is kept with 35 % of its moves mangled,
    # so the page is now *contested* -- the prose paragraphs stay the layer's
    # (the layer anchors them) and the analysis, unreadable before, comes back
    # from the OCR as further paragraphs after them.
    assert result.report.pages[0].source == "text-layer+ocr"
    assert [t[:24] for t in texts[:5]] == [
        "(206): White to play win",
        "If Black's king starts o",
        "There are a total of 31 ",
        "We end the chapter with ",
        "(207): Black is to play.",
    ], [t[:24] for t in texts]
    assert texts[0].endswith("and wins.")
    # Since passo 6 the right column's layer is kept too (its "unpronounceable"
    # tokens were mangled moves), so the analysis stays one paragraph with its
    # prose and the moves come back inside it.
    analysis = " ".join(texts[4:])
    assert "Ne4" in analysis and "Bf4" in analysis, "the moves are readable now"


def test_chernev_tabular_moves_and_flush_paragraphs():
    """A Word-made PDF: figurines as separate MS Gothic runs, tabular move
    lines, flush paragraphs with no indent and no extra leading.

    Checked against the printed page 121 (index 120): each ``21 ♖f1-d1`` row
    is one move block, ``Agora que...`` and ``Capablanca, é claro...`` are two
    paragraphs, and the last row's ``22`` is a move number, not a folio.
    """
    path = corpus_file("Melhores Finais de Capablanca - Irving Chernev pt-br - Copia.pdf")
    result = import_pdf(open_pdf(path), PdfImportOptions(pages=range(118, 124), lang="por"))
    page = [
        b
        for b in result.document.body
        if isinstance(b, (Paragraph, Heading))
        and b.provenance is not None
        and b.provenance.page_index == 120
    ]
    texts = [" ".join(plain_text(b.content).split()) for b in page]
    assert [t[:22] for t in texts] == [
        "Final 20",
        "Posição após 20 … Qd7-",
        "Villegas",
        "Capablanca joga",
        "A vantagem posicional ",
        "O plano de Capablanca ",
        "21 Rf1-d1",
        "Fortalece o controle d",
        "21 … Rf8-d8",
        "As pretas devem opor-s",
        "22 b3-b4!",
        "Agora que a posição es",
        "Capablanca, é claro, n",
        "22 … Rd8×d4",
    ], [t[:22] for t in texts]
    styles = [b.props.style for b in page]
    assert styles.count("Movetext") == 4
    assert result.report.pages[2].columns == 1, "linhas tabulares não são colunas"
