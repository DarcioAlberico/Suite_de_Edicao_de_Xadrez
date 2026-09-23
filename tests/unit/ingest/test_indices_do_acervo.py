"""The indexes of real books, through the production importer: every list in its own order.

The crítico da fase 5 (ciclo 4) found the B13 interleaving, line by line, the columns of an index
when the page had two gutters or more and no prose -- the Flores pp. 460–464 (raster, from the
acervo), the Yusupov 4 p. 206 and the Nunn p. 288 as a scanned book --: «David 412 Galkin 198».
And on the Nunn p. 288, once the B13 read Tesseract's page right (CER 0,0193), the arbiter chose
RapidOCR's interleaved reading of it (0,7516): the agreement between the engines was measured on
the lines the B13 had moved, and the moved lines agreed better with RapidOCR's rows.

The truth is the book's order, checked without transcribing it: in a right reading no line holds
two entries (a page number followed by a name, «205, Ruge») and the names rise in alphabetical
order down the page (the second column goes on with the alphabet); interleaved, both break on every
other line.  The Yusupov's «Índice de partidas» lists opponents under each player, not in order,
and is held to the first test only.

Needs the acervo (skips without it) and Tesseract; ~2 min on a free machine.
"""

from __future__ import annotations

import io
import itertools
import re
from pathlib import Path

import pytest

from caissa.ingest.pdf import PdfImportOptions, import_pdf
from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig

from .conftest import corpus_file, requires_pymupdf

pytestmark = [requires_pymupdf, pytest.mark.slow]


def _tesseract() -> bool:
    from caissa.ocr.engines.tesseract import find_tesseract

    return find_tesseract() is not None


requires_tesseract = pytest.mark.skipif(not _tesseract(), reason="Tesseract não instalado")

#: A page number, then a name in the same line: two entries joined.
DOIS_VERBETES = re.compile(r"\d[,.)]?\s+[A-ZÀ-Ý][a-zà-ÿ]")
DPI = 300


class _Gravando(OcrService):
    """The production service, keeping the text of every emitted region, page by page."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.textos: dict[int, str] = {}

    def recognize(self, page, frame, verdict=None, **kwargs):  # type: ignore[override]
        reconhecida = super().recognize(page, frame, verdict, **kwargs)
        regioes = sorted(reconhecida.regions, key=lambda r: r.reading_order)
        self.textos[frame.index] = "\n".join(r.text for r in regioes if r.emits_text)
        return reconhecida


def _ler(pdf: Path, paginas: list[int]) -> dict[int, str]:
    servico = _Gravando(None, config=OcrServiceConfig())
    import_pdf(pdf, PdfImportOptions(ocr=servico, pages=paginas))
    return servico.textos


def _digitalizada(livro: str, pagina: int, pasta: Path) -> Path:
    """The page as a scanned book has it: a 300 DPI grey picture, no text layer."""
    import pymupdf

    origem = pymupdf.open(corpus_file(livro))
    imagem = origem[pagina].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    buffer = io.BytesIO(imagem.tobytes("png"))
    saida = pymupdf.open()
    folha = saida.new_page(width=origem[pagina].rect.width, height=origem[pagina].rect.height)
    folha.insert_image(folha.rect, stream=buffer.getvalue())
    caminho = pasta / f"{livro.split()[0]}_{pagina}.pdf"
    saida.save(caminho)
    return caminho


def _juntas(texto: str) -> list[str]:
    return [linha for linha in texto.splitlines() if DOIS_VERBETES.search(linha)]


def _descidas(texto: str) -> tuple[int, int]:
    """How often the alphabetical order of the entries goes down, and how many entries."""
    from caissa.ocr.layout.rows import _first_word, _sort_key

    chaves = []
    for linha in texto.splitlines():
        palavra = _first_word(linha)
        if len(palavra) > 1 and palavra[0].isupper():
            chaves.append(_sort_key(palavra))
    return sum(1 for a, b in itertools.pairwise(chaves) if b < a), len(chaves)


def _em_ordem(texto: str) -> bool:
    descidas, verbetes = _descidas(texto)
    return verbetes >= 20 and descidas <= 0.10 * verbetes


@pytest.fixture(scope="module")
def flores() -> dict[int, str]:
    return _ler(corpus_file("Flores Rios - Chess Structures"), [460, 461, 462, 463, 464])


@pytest.fixture(scope="module")
def digitalizadas(tmp_path_factory) -> dict[str, str]:
    pasta = tmp_path_factory.mktemp("indices")
    nunn = _digitalizada("Nunn J. Secrets of Minor", 288, pasta)
    yusupov = _digitalizada("Yusupov_4", 206, pasta)
    return {"nunn": _ler(nunn, [0])[0], "yusupov": _ler(yusupov, [0])[0]}


@pytest.mark.timeout(900)
@requires_tesseract
@pytest.mark.parametrize("pagina", [460, 461, 462, 463, 464])
def test_the_flores_index_reads_each_list_in_order(flores, pagina):
    texto = flores[pagina]
    assert len(_juntas(texto)) <= 2, _juntas(texto)[:6]
    assert _em_ordem(texto), _descidas(texto)


@pytest.mark.timeout(900)
@requires_tesseract
def test_the_scanned_indexes_of_the_nunn_and_the_yusupov_keep_their_lists(digitalizadas):
    assert len(_juntas(digitalizadas["nunn"])) <= 2, _juntas(digitalizadas["nunn"])[:6]
    assert _em_ordem(digitalizadas["nunn"]), _descidas(digitalizadas["nunn"])
    assert len(_juntas(digitalizadas["yusupov"])) <= 2, _juntas(digitalizadas["yusupov"])[:6]


@pytest.mark.timeout(900)
@requires_tesseract
def test_the_sabotages_interleave_the_flores_and_the_nunn(monkeypatch, tmp_path):
    """Without the index's gutters the Flores p. 462 joins its lists line by line; with the
    agreement measured on the lines the B13 moved (the before), the arbiter takes RapidOCR's
    interleaved Nunn p. 288."""
    from caissa.ocr import arbiter
    from caissa.ocr.layout import rows

    monkeypatch.setattr(rows, "_index_gutters", lambda gutters, bands, cfg: [])
    assert len(_juntas(_ler(corpus_file("Flores Rios - Chess Structures"), [462])[462])) > 10
    monkeypatch.undo()
    monkeypatch.setattr(arbiter, "_engine_order", lambda result: result.text)
    nunn = _ler(_digitalizada("Nunn J. Secrets of Minor", 288, tmp_path), [0])[0]
    assert not _em_ordem(nunn), _descidas(nunn)
