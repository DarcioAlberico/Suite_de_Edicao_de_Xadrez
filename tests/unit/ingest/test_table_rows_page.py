"""B13 on a page the importer reads, end to end (OCR_UI_ROADMAP_C2 passo B13).

The critic's page (fase 5, ciclo 3: ``construido.pdf`` p. 0, ``b13_estreita3.py --justificar``):
the Gallagher's measure -- two columns of 1,95 in, Times 10 pt, a line every 12 pt -- with
**ordinary notes** justified on the left (three words a line, a move here and there) and the game's
move list, set without tabs, on the right, scanned at 300 DPI.  The notes are not prose by length,
nor by words, nor notes of variations, and the gutter's bands are not comparable: the rule of the
third cycle joined them line by line -- «White could also try 26 Re3 Bxd4» -- and the importer
**accepted** the page, CER 0,0052 → 0,6440.  Lines longer than a cell that carry the sentence over
are running text (``rows._running``): the page reads as with the rule off.  The unit tests pin the
rule on the blocks; this one pins it on what Tesseract cuts from a rendered page.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from caissa.core.model import Heading, Paragraph, plain_text
from caissa.ingest.pdf.importer import PdfImportOptions, import_pdf
from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig


def _tesseract() -> bool:
    from caissa.ocr.engines.tesseract import find_tesseract

    return find_tesseract() is not None


requires_tesseract = pytest.mark.skipif(not _tesseract(), reason="Tesseract não instalado")

NOTES = ["White could also try", "21 Bd6!?, when after", "21...Rg8 22 g4 Rg6 the",
         "position is unclear.", "Black's knight is", "strong on d7, but", "White keeps an edge",
         "thanks to the bishop", "pair. Instead, 22 Bc5", "b6 23 Be3 is met by",
         "23...Nd7 with equality.", "After the text move", "Black is able to ex-",
         "change the bishops.", "Now 26 Re3 was best.", "White's rooks are", "active, but Black",
         "holds the draw."]
GAME = ["26 Re3 Bxd4", "27 Rxd4 Rd6", "28 Bb7 Rf6+", "29 Kg3 Rc7", "30 Bf3 Nb6", "31 Red3 Nc4",
        "32 Rd5 h6", "33 h4 gxh4+", "34 Kxh4 Re7", "35 g5 hxg5+", "36 Rxg5 Re1", "37 Rd1 Rf4+",
        "38 Rg4 Rxg4+", "39 Bxg4 Re4", "40 Rd4 Re3", "41 Bc8 Rxc3", "42 Bxa6 Na3", "43 Kg5 Rc2"]

TIMES = Path(r"C:\Windows\Fonts\times.ttf")
requires_times = pytest.mark.skipif(not TIMES.is_file(), reason="sem a Times do Windows: o corte "
                                    "dos blocos do Tesseract depende da fonte da página do crítico")
DPI = 300


def _page(tmp_path: Path) -> Path:
    """The critic's page, drawn as the critic drew it (Times 10 pt at 300 DPI, margins of 0,5 in,
    columns of 1,95 in, a gutter of 0,25 in, a line every 12 pt; the notes justified to the column
    but the last line of a paragraph), and saved as a PDF of one picture -- a scanned book."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(TIMES), int(10 / 72 * DPI))
    lead, margin, column, gutter = (int(12 / 72 * DPI), int(0.5 * DPI), int(1.95 * DPI),
                                    int(0.25 * DPI))
    image = Image.new("L", (2 * margin + 2 * column + gutter, 2 * margin + lead * (1 + len(NOTES))),
                      255)
    draw = ImageDraw.Draw(image)
    for n, text in enumerate(NOTES):
        x, y = margin, margin + n * lead
        words = text.split()
        natural = sum(font.getlength(w) for w in words)
        if (len(words) < 2 or text.endswith(".")
                or natural + font.getlength(" ") * (len(words) - 1) > column):
            draw.text((x, y), text, font=font, fill=0)
            continue
        gap = (column - natural) / (len(words) - 1)
        for word in words:
            draw.text((x, y), word, font=font, fill=0)
            x += font.getlength(word) + gap
    for n, text in enumerate(GAME):
        draw.text((margin + column + gutter, margin + n * lead), text, font=font, fill=0)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", dpi=(DPI, DPI))
    pdf = pymupdf.open()
    page = pdf.new_page(width=image.width * 72 / DPI, height=image.height * 72 / DPI)
    page.insert_image(page.rect, stream=buffer.getvalue())
    path = tmp_path / "notas_comuns.pdf"
    pdf.save(path)
    pdf.close()
    return path


def _read(path: Path, *, table_rows: bool) -> str:
    """The text of the imported document, block by block (headings and paragraphs)."""
    service = OcrService(None, config=OcrServiceConfig(table_rows=table_rows))
    result = import_pdf(path, PdfImportOptions(lang="eng", ocr=service))
    return "\n".join(plain_text(b.content) for b in result.document.body
                     if isinstance(b, (Heading, Paragraph)))


@pytest.mark.slow
# Three imports with OCR: ~60 s on a free machine, past the suite's 120 s with the machine busy.
@pytest.mark.timeout(600)
@requires_tesseract
@requires_times
def test_ordinary_notes_beside_the_game_read_as_with_the_rule_off(tmp_path, monkeypatch):
    path = _page(tmp_path)
    on = _read(path, table_rows=True)
    assert "could also try" in on
    assert "holds the draw" in on
    assert on == _read(path, table_rows=False), "the rule changes nothing on this page"
    # the sabotage: without the running text and without the gutter beside the game (the fifth
    # cycle's: each alone holds this page) the notes join the game line by line
    from caissa.ocr.layout import rows

    monkeypatch.setattr(rows, "_running", lambda block, cfg: False)
    monkeypatch.setattr(rows, "_game_gutters", lambda gutters, bands, cfg: [])
    scrambled = _read(path, table_rows=True)
    assert "could also try 26" in scrambled
