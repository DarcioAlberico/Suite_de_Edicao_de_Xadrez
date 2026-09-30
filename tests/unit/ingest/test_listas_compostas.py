"""Lists composed as a book sets them, through the production importer and service: two lists
side by side are two lists, and a game beside a table is a game and a table.

The crítico da fase 5 (ciclo 5) composed these pages -- Times at 300 DPI, gray -- and broke the
rule of the fourth cycle with them: the players of a tournament by the standings, each with the
opponents under them and a page (``c5/ataque/indices_ataque.pdf`` p. 8), came out interleaved
line by line and *accepted*, 0,0000 → 0,6577; the last page of an index set as the Nunn sets it,
names and pages apart, five entries in the second column (p. 4), joined its first five rows two
entries a row, 0,6634 → 0,3196 *accepted*; and a game beside the standings of the tournament
(``c5/partida_tabela/P_T.png``) joined its moves to the players, «1 e4 e5 Aljechin 7½», 0,2218
→ 0,7564.  The pages are composed again here the same way, so the test needs no file of his.

The truth is checked without transcribing it: the page reads as with the rule off (the players),
no line holds two entries (a page number followed by a name, «82 Nepomniachtchi»), no line holds a
move and a player.  Needs Tesseract and the Times New Roman of Windows (skips without them).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from caissa.ingest.pdf import PdfImportOptions, import_pdf
from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig

from .conftest import requires_pymupdf

pytestmark = [requires_pymupdf, pytest.mark.slow]

TIMES = Path(r"C:\Windows\Fonts\times.ttf")
DPI = 300


def _tesseract() -> bool:
    from caissa.ocr.engines.tesseract import find_tesseract

    return find_tesseract() is not None


requires_tesseract = pytest.mark.skipif(not _tesseract(), reason="Tesseract não instalado")
requires_times = pytest.mark.skipif(not TIMES.exists(), reason="sem a Times New Roman do Windows")

#: A page number, then a name in the same line: two entries joined.
DOIS_VERBETES = re.compile(r"\d[,.)]?\s+[A-ZÀ-Ý][a-zà-ÿ]")

STANDINGS = ["Carlsen", "Caruana", "Ding", "Nepomniachtchi", "Aronian", "Giri", "So", "Mamedyarov",
             "Anand", "Grischuk", "Nakamura", "Vachier-Lagrave", "Karjakin", "Radjabov", "Topalov",
             "Rapport", "Firouzja", "Duda"]
INDEX = ["Aaron 249", "Acevedo 228", "Addison 227", "Andersson 229", "Barczay 275", "Bazan 236",
         "Beach 257", "Benko 231, 246", "Bennett 218", "Berliner 258", "Bisguier 240, 260",
         "Bolbochan 250", "Bredoff 217", "Byrne 211", "Camara 300", "Ciocaltea 251", "Darga 244",
         "Dely 272", "Donner 270", "Durao 263", "Eliskases 237", "Filip 247", "Finegold 259",
         "Foguelman 239", "Geller 279, 280", "Gligoric 229, 264", "Gudmundsson 243", "Hook 301",
         "Ivkov 268", "Johannessen 265", "Keres 222, 248", "Korchnoi 290", "Kramer 215"]
GAME = ["1 e4 e5", "2 Nf3 Nc6", "3 Bb5 a6", "4 Ba4 Nf6", "5 O-O Be7", "6 Re1 b5", "7 Bb3 d6",
        "8 c3 O-O", "9 h3 Nb8", "10 d4 Nbd7", "11 Nbd2 Bb7", "12 Bc2 Re8", "13 Nf1 Bf8",
        "14 Ng3 g6"]
TABLE = [("Aljechin", "7½"), ("Keres", "7"), ("Flohr", "6½"), ("Petrov", "6"), ("Fine", "5½"),
         ("Reshevsky", "5"), ("Tartakower", "4½"), ("Steiner", "4"), ("Lilienthal", "3½"),
         ("Stahlberg", "3"), ("Book", "2½"), ("Mikenas", "2")]


#: Fifty-seven surnames for the pages of the sixth cycle, in alphabetical order.
SURNAMES = ["Aagaard", "Abramovic", "Adams", "Akopian", "Alburt", "Alekhine", "Anand", "Andersson",
            "Aronian", "Averbakh", "Bareev", "Beliavsky", "Benko", "Bisguier", "Bologan",
            "Botvinnik", "Bronstein", "Byrne", "Capablanca", "Chiburdanidze", "Chigorin",
            "Dolmatov", "Dvoretsky", "Euwe", "Fischer", "Flohr", "Geller", "Gelfand", "Gligoric",
            "Gulko", "Hort", "Ivanchuk", "Kamsky", "Karpov", "Kasparov", "Keres", "Korchnoi",
            "Kramnik", "Larsen", "Lasker", "Ljubojevic", "Makogonov", "Marshall", "Nimzowitsch",
            "Petrosian", "Polugaevsky", "Portisch", "Reshevsky", "Rubinstein", "Short", "Smyslov",
            "Spassky", "Stein", "Tal", "Timman", "Topalov", "Yusupov"]
STANDINGS_IN_HALVES = ["Aljechin 7½", "Keres 7", "Flohr 6½", "Petrov 6", "Fine 5½", "Reshevsky 5",
                       "Tartakower 4½", "Steiner 4", "Lilienthal 3½", "Stahlberg 3", "Book 2½",
                       "Mikenas 2", "Apsenieks 2", "Bondarevsky 1½", "Feigins 1", "Hasenfuss ½"]
PAIRS = [("Carlsen", 2830, "Caruana", 2800), ("Ding", 2780, "Nepomniachtchi", 2790),
         ("Aronian", 2760, "Giri", 2750), ("So", 2770, "Mamedyarov", 2740),
         ("Anand", 2750, "Grischuk", 2745), ("Nakamura", 2760, "Radjabov", 2740),
         ("Karjakin", 2735, "Topalov", 2730), ("Rapport", 2725, "Firouzja", 2720),
         ("Duda", 2715, "Wojtaszek", 2705), ("Harikrishna", 2700, "Vitiugov", 2710),
         ("Artemiev", 2695, "Andreikin", 2690), ("Eljanov", 2685, "Navara", 2680)]


def _four_digit_index() -> list[str]:
    """An index of problem numbers of four digits, two entries with two numbers (the critic's
    ``indice_4dig``): set in three columns, only the first two hold a line with two numbers."""
    entries = [f"{name} {1000 + (733 * k + 211) % 4000}" for k, name in enumerate(SURNAMES)]
    entries[5] = f"{SURNAMES[5]} 1204, 3318"
    entries[27] = f"{SURNAMES[27]} 2087, 4410"
    return entries


def _table(rows: list[list[str]], xs: list[float], *, points: float = 10.0):
    """A table set row by row, a cell at each ``xs`` (inches), 12 pt apart, as the critic's."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(TIMES), int(points / 72 * DPI))
    lead, margin = int(12 / 72 * DPI), int(0.5 * DPI)
    size = (int((xs[-1] + 1.6) * DPI) + 2 * margin, 2 * margin + lead * (len(rows) + 1))
    image = Image.new("L", size, 255)
    draw = ImageDraw.Draw(image)
    for n, row in enumerate(rows):
        for x, cell in zip(xs, row, strict=True):
            draw.text((margin + x * DPI, margin + n * lead), cell, font=font, fill=0)
    return np.asarray(image)


def _players() -> list[str]:
    """Each player of the standings and, indented under the player, two or three opponents with a
    page -- the critic's «jogador / adversários»."""
    rows: list[str] = []
    for i, player in enumerate(STANDINGS):
        others = [p for p in STANDINGS if p != player]
        rows += [player, *(f"   {others[(i * 3 + k) % len(others)]} {40 + 7 * i + 3 * k}"
                           for k in range(2 + i % 2))]
    return rows


def _compose(columns: list[list[str]], xs: list[float], *, pages_at: float | None = None,
             points: float = 9.0):
    """Columns of text at ``xs`` (inches); a line that opens with three spaces is indented 0,17 in;
    with ``pages_at`` what follows the first word goes to a tab of its own, as the Nunn sets it."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(TIMES), int(points / 72 * DPI))
    lead, margin = int((points + 2) / 72 * DPI), int(0.5 * DPI)
    width = int((xs[-1] + 2.6) * DPI) + 2 * margin
    height = 2 * margin + lead * (max(len(c) for c in columns) + 1)
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    for column, x in zip(columns, xs, strict=True):
        for n, text in enumerate(column):
            indent = 0.17 if text.startswith("   ") else 0.0
            y = margin + n * lead
            if pages_at is not None and " " in text.strip():
                name, pages = text.strip().split(" ", 1)
                draw.text((margin + (x + indent) * DPI, y), name, font=font, fill=0)
                draw.text((margin + (x + pages_at) * DPI, y), pages, font=font, fill=0)
            else:
                draw.text((margin + (x + indent) * DPI, y), text.strip(), font=font, fill=0)
    return np.asarray(image)


def _game_and_table():
    """The game on the left, the standings on the right, 10 pt, columns of 1,95 in."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(TIMES), int(10 / 72 * DPI))
    lead, margin = int(12 / 72 * DPI), int(0.5 * DPI)
    column, gutter = int(1.95 * DPI), int(0.25 * DPI)
    size = (2 * margin + 2 * column + gutter, 2 * margin + lead * (len(GAME) + 1))
    image = Image.new("L", size, 255)
    draw = ImageDraw.Draw(image)
    for n, text in enumerate(GAME):
        draw.text((margin, margin + n * lead), text, font=font, fill=0)
    right = margin + column + gutter
    for n, (name, score) in enumerate(TABLE):
        draw.text((right, margin + n * lead), name, font=font, fill=0)
        draw.text((right + int(0.7 * column), margin + n * lead), score, font=font, fill=0)
    return np.asarray(image)


def _as_scanned_pdf(gray, pasta: Path, name: str) -> Path:
    """The picture as the only thing on a PDF page: a scanned book, no text layer."""
    import pymupdf
    from PIL import Image

    buffer = io.BytesIO()
    Image.fromarray(gray).save(buffer, format="PNG", dpi=(DPI, DPI))
    pdf = pymupdf.open()
    page = pdf.new_page(width=gray.shape[1] * 72 / DPI, height=gray.shape[0] * 72 / DPI)
    page.insert_image(page.rect, stream=buffer.getvalue())
    path = pasta / f"{name}.pdf"
    pdf.save(path)
    return path


class _Gravando(OcrService):
    """The production service, keeping the text of every emitted region of the page."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.texto = ""

    def recognize(self, page, frame, verdict=None, **kwargs):  # type: ignore[override]
        reconhecida = super().recognize(page, frame, verdict, **kwargs)
        regioes = sorted(reconhecida.regions, key=lambda r: r.reading_order)
        self.texto = "\n".join(r.text for r in regioes if r.emits_text)
        return reconhecida


def _importar(pdf: Path, *, table_rows: bool = True) -> str:
    servico = _Gravando(None, config=OcrServiceConfig(table_rows=table_rows))
    import_pdf(pdf, PdfImportOptions(ocr=servico, pages=[0]))
    return servico.texto


def _juntas(texto: str) -> list[str]:
    return [linha for linha in texto.splitlines() if DOIS_VERBETES.search(linha)]


@pytest.fixture(scope="module")
def paginas(tmp_path_factory) -> dict[str, Path]:
    pasta = tmp_path_factory.mktemp("listas")
    players = _players()
    four = _four_digit_index()
    entries = [f"{name} {9 + (37 * k) % 380}" for k, name in enumerate(SURNAMES)]
    return {
        "jogadores": _as_scanned_pdf(_compose([players[0:22], players[22:44], players[44:66]],
                                              [0.0, 2.0, 4.0]), pasta, "jogadores"),
        "ultima": _as_scanned_pdf(_compose([INDEX[0:28], INDEX[28:33]], [0.0, 2.6], pages_at=1.2),
                                  pasta, "ultima"),
        # the pages of the sixth cycle: a page of lists whose columns differ in form
        "quatro": _as_scanned_pdf(_compose([four[0:19], four[19:38], four[38:57]],
                                           [0.0, 1.7, 3.4]), pasta, "quatro"),
        "so_nomes": _as_scanned_pdf(_compose([entries[0:19], SURNAMES[19:38], entries[38:57]],
                                             [0.0, 1.6, 3.2]), pasta, "so_nomes"),
        "metades": _as_scanned_pdf(_compose([STANDINGS_IN_HALVES[0:8], STANDINGS_IN_HALVES[8:16]],
                                            [0.0, 2.6], pages_at=1.4), pasta, "metades"),
    }


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_a_page_of_lists_reads_as_with_the_rule_off_whatever_the_forms(paginas):
    """Crítico da fase 5, ciclo 6: an index whose third column has four-digit numbers and no line
    with two (0,0026 → 0,4916 *accepted*), and a column of names only between two of entries
    (0,0032 → 0,7747 *accepted*), joined line by line.  Every column a list: read as with the rule
    off, no line with two entries."""
    for nome in ("quatro", "so_nomes"):
        ligada = _importar(paginas[nome])
        assert ligada == _importar(paginas[nome], table_rows=False), nome
        assert _juntas(ligada) == [], (nome, _juntas(ligada)[:3])


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_the_standings_in_two_halves_are_no_worse_than_with_the_rule_off(paginas):
    """The builder's page of the sixth cycle: the OCR lost the scores of the second half and read
    the half points of the first as ``%``; the halves joined line by line, 0,3316 → 0,7053
    *accepted*.  No line holds a player of each half, and the page is no worse than with the rule
    off."""
    from caissa.ocr.metrics import score_text

    verdade = "\n".join(STANDINGS_IN_HALVES)
    ligada = _importar(paginas["metades"])
    desligada = _importar(paginas["metades"], table_rows=False)
    primeira = {t.split()[0] for t in STANDINGS_IN_HALVES[0:8]}
    segunda = {t.split()[0] for t in STANDINGS_IN_HALVES[8:16]}
    juntas = [linha for linha in ligada.splitlines()
              if set(linha.split()) & primeira and set(linha.split()) & segunda]
    assert juntas == [], juntas
    assert score_text(verdade, ligada).cer <= score_text(verdade, desligada).cer


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_a_pairing_with_the_ratings_apart_is_read_by_rows():
    """The critic's pairing with the ratings in columns of their own (``emparc_sep_sm``, read by
    rows): a page of lists would read it by columns -- the band of ratings, Black players and
    their ratings is a table's, a column of numbers beside the names."""
    texto = _pairing_text()
    assert [linha for linha in texto.splitlines() if "Carlsen" in linha and "Caruana" in linha]


def _pairing_text() -> str:
    servico = OcrService(None, config=OcrServiceConfig(ink_coverage=False))
    rows = [[w, str(rw), b, str(rb)] for w, rw, b, rb in PAIRS]
    return servico.recognize_image(_table(rows, [0.0, 1.4, 2.0, 3.4]), dpi=float(DPI),
                                   lang="eng").text


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_players_by_the_standings_read_as_with_the_rule_off(paginas):
    ligada = _importar(paginas["jogadores"])
    assert ligada == _importar(paginas["jogadores"], table_rows=False)
    assert _juntas(ligada) == []


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_the_last_page_of_an_index_never_joins_two_entries(paginas):
    texto = _importar(paginas["ultima"])
    assert _juntas(texto) == [], _juntas(texto)
    assert "Ivkov 268" in texto


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_a_game_beside_the_standings_through_the_service():
    servico = OcrService(None, config=OcrServiceConfig(ink_coverage=False))
    texto = servico.recognize_image(_game_and_table(), dpi=float(DPI), lang="eng").text
    jogadores = [name for name, _score in TABLE]
    juntas = [linha for linha in texto.splitlines()
              if re.match(r"^\d+\s", linha) and any(j in linha for j in jogadores)]
    assert juntas == [], juntas


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_the_sabotages_join_the_lists_and_the_game_to_the_table(paginas, monkeypatch):
    """Without the gutter between two lists of one form the players and the last page join line by
    line; without the column of names the game joins the standings."""
    from caissa.ocr.layout import rows

    monkeypatch.setattr(rows, "_list_gutters", lambda gutters, bands, cfg: [])
    assert _juntas(_importar(paginas["jogadores"])), "sabotaged: the players join"
    assert _juntas(_importar(paginas["ultima"])), "sabotaged: the last page joins"
    monkeypatch.undo()
    monkeypatch.setattr(rows, "_names", lambda block, cfg: False)
    servico = OcrService(None, config=OcrServiceConfig(ink_coverage=False))
    texto = servico.recognize_image(_game_and_table(), dpi=float(DPI), lang="eng").text
    jogadores = [name for name, _score in TABLE]
    assert [linha for linha in texto.splitlines()
            if re.match(r"^\d+\s", linha) and any(j in linha for j in jogadores)], texto


@pytest.mark.timeout(900)
@requires_tesseract
@requires_times
def test_the_sabotages_of_the_sixth_cycle(paginas, monkeypatch):
    """Without the page of lists the four-digit index and the names between entries join line by
    line; with ``6%`` no score the halves of the standings join; without the numbers beside the
    names the pairing is read by columns."""
    from caissa.ocr.layout import rows

    monkeypatch.setattr(rows, "_page_of_lists", lambda forms: ())
    assert _juntas(_importar(paginas["quatro"])), "sabotaged: the index joins"
    assert _importar(paginas["so_nomes"]) != _importar(paginas["so_nomes"], table_rows=False)
    monkeypatch.undo()
    monkeypatch.setattr(rows, "_SCORE", re.compile(r"^(\d{0,2}[½=]|\d{1,2}[.,]5)[,;.]?$"))
    primeira = {t.split()[0] for t in STANDINGS_IN_HALVES[0:8]}
    segunda = {t.split()[0] for t in STANDINGS_IN_HALVES[8:16]}
    assert [linha for linha in _importar(paginas["metades"]).splitlines()
            if set(linha.split()) & primeira and set(linha.split()) & segunda], "the halves join"
    monkeypatch.undo()
    monkeypatch.setattr(rows, "_numbers_beside", lambda lines, cfg: 0)
    texto = _pairing_text()
    assert not [linha for linha in texto.splitlines() if "Carlsen" in linha and "Caruana" in linha]
