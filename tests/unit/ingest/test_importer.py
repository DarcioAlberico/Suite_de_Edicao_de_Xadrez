"""The whole pipeline on synthetic books whose IR is known in advance."""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.core.model import (
    Diagram,
    Heading,
    ImageBlock,
    ImageInline,
    Paragraph,
    PieceGlyph,
    SourceKind,
    plain_text,
    validate,
)
from caissa.ingest.pdf import (
    DiagramHit,
    ImportCanceled,
    PdfImporter,
    PdfImportOptions,
    import_pdf,
    open_pdf,
)
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan

from .conftest import (
    LOREM,
    LOREM_EN,
    PageSpec,
    find_font,
    lines_of,
    paragraphs_of,
    requires_pymupdf,
    two_column_page,
)

pytestmark = requires_pymupdf


# --------------------------------------------------------------------------- #
# Text books
# --------------------------------------------------------------------------- #


def test_a_small_book_round_trips_its_structure(pdf_file):
    pages = []
    expected: list[str] = []
    for n in range(4):
        spec, order = two_column_page(
            [f"Parágrafo {n}.1. {LOREM}", f"Parágrafo {n}.2. {LOREM_EN}"],
            [f"Parágrafo {n}.3. {LOREM}", f"Parágrafo {n}.4. {LOREM_EN}"],
            heading=f"Capítulo {n + 1}" if n % 2 == 0 else None,
            running_head="Manual de Finais",
            folio=n + 10,
        )
        pages.append(spec)
        expected.extend(order)
    path = pdf_file(pages, toc=[(1, "Capítulo 1", 0), (1, "Capítulo 3", 2)])
    result = import_pdf(path, PdfImportOptions(lang="por"))
    document, report = result.document, result.report

    assert paragraphs_of(document) == expected
    headings = [b for b in document.body if isinstance(b, Heading)]
    assert [plain_text(h.content) for h in headings] == ["Capítulo 1", "Capítulo 3"]
    assert all(h.level == 1 for h in headings)
    assert report.counters["outline_attached"] == 2
    assert report.counters["paragraphs"] == 16
    assert report.furniture_patterns >= 1, "o cabeçalho corrente repetido devia ter sido visto"
    assert all(p.source == "text-layer" for p in report.pages)
    assert document.metadata.page_count == 4
    assert not [i for i in validate(document) if i.severity.value == "error"]


def test_every_block_carries_provenance_to_a_page_rectangle(pdf_file):
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=100, width_chars=60))
    path = pdf_file([spec])
    document = import_pdf(path).document
    block = document.body[0]
    assert isinstance(block, Paragraph)
    prov = block.provenance
    assert prov is not None
    assert prov.kind is SourceKind.PDF_TEXT_LAYER
    assert prov.page_index == 0
    assert prov.rect is not None
    assert prov.rect.x == pytest.approx(72.0, abs=1.0)
    assert prov.document_hash is not None
    assert len(prov.document_hash) == 64
    assert prov.confidence == pytest.approx(0.98)
    assert block.props.style == "Body"
    assert document.styles.default_paragraph_style == "Body"


def test_runs_keep_bold_italic_and_size(pdf_file):
    spec = PageSpec()
    spec.text("Uma palavra ", 72, 100, font="helv")
    spec.text("forte", 140, 100, font="hebo")
    spec.text(" e outra", 170, 100, font="heit")
    path = pdf_file([spec])
    paragraph = import_pdf(path).document.body[0]
    assert isinstance(paragraph, Paragraph)
    weights = [
        (plain_text((node,)), node.props.font_weight, node.props.italic)
        for node in paragraph.content
    ]
    assert ("forte", 700, None) in weights
    assert any(italic for _, _, italic in weights)
    assert paragraph.content[0].props.font_size is not None
    assert paragraph.content[0].props.font_size.value == pytest.approx(11.0)


def test_metadata_flows_into_the_document(pdf_file):
    path = pdf_file([PageSpec().text("x", 72, 100)], name="Autor - Título do Livro.pdf")
    document = import_pdf(path).document
    assert document.metadata.title == "Título do Livro"
    assert [c.name for c in document.metadata.contributors] == ["Autor"]
    assert any(e.name == "filename" for e in document.metadata.custom)
    assert document.metadata.source is not None
    assert document.metadata.source.endswith(".pdf")


def test_page_selection_progress_and_cancel(pdf_file):
    pages = [
        PageSpec().text(f"Página {i} com texto suficiente para contar.", 72, 100) for i in range(6)
    ]
    path = pdf_file(pages)
    seen: list[tuple[int, int]] = []
    result = import_pdf(
        path, PdfImportOptions(pages=[1, 3], progress=lambda d, t: seen.append((d, t)))
    )
    assert [p.index for p in result.report.pages] == [1, 3]
    assert seen
    assert seen[-1] == (4, 4)
    with pytest.raises(ImportCanceled):
        import_pdf(path, PdfImportOptions(should_cancel=lambda: True))
    with pytest.raises(IndexError):
        import_pdf(path, PdfImportOptions(pages=[99]))


# --------------------------------------------------------------------------- #
# Scans, OCR, images
# --------------------------------------------------------------------------- #


def test_a_scanned_page_becomes_an_image_block_with_the_reason(pdf_file):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    result = import_pdf(path)
    assert result.report.pages[0].source == "image-only"
    block = result.document.body[0]
    assert isinstance(block, ImageBlock)
    assert block.provenance is not None
    assert "não contém texto" in (block.provenance.note or "")
    assert result.document.resource(block.resource) is not None
    assert result.report.counters["scanned_pages"] == 1


def test_an_ocr_provider_takes_over_a_page_without_text(pdf_file):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    calls: list[int] = []

    def fake_ocr(_page, frame, verdict) -> PageText:
        calls.append(frame.index)
        assert verdict.is_image_only
        box = (72.0, 100.0, 300.0, 112.0)
        return PageText(
            frame=frame,
            lines=(
                TextLine(
                    box=box,
                    spans=(TextSpan(text="lido pelo OCR", box=box, size=10.0, confidence=0.7),),
                ),
            ),
            source="tesseract",
        )

    result = import_pdf(path, PdfImportOptions(ocr=fake_ocr))
    assert calls == [0]
    assert result.report.pages[0].source == "ocr"
    block = result.document.body[0]
    assert isinstance(block, Paragraph)
    assert plain_text(block.content) == "lido pelo OCR"
    assert block.provenance is not None
    assert block.provenance.kind is SourceKind.OCR
    assert block.provenance.confidence == pytest.approx(0.7)


def test_a_failing_ocr_provider_does_not_lose_the_book(pdf_file):
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])

    def broken(*_args):
        raise RuntimeError("motor caiu")

    result = import_pdf(path, PdfImportOptions(ocr=broken))
    assert result.report.pages[0].source == "image-only"
    assert any("motor caiu" in note for note in result.report.notes)


def test_figures_and_inline_images_are_placed_and_written(pdf_file, tmp_path):
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=100, width_chars=60))
    spec.images.append((72.0, 200.0, 272.0, 350.0, 100, 75))  # a figure
    spec.text("Legenda em itálico da figura", 72, 366, font="heit")
    spec.items.extend(lines_of(LOREM_EN, x=72, y=420, width_chars=60))
    # A tiny symbol inside a line of text.
    spec.text("O lance", 72, 520)
    spec.images.append((112.0, 511.0, 122.0, 521.0, 10, 10))
    spec.text("foi decisivo.", 126, 520)
    path = pdf_file([spec])
    assets = tmp_path / "assets"
    result = import_pdf(path, PdfImportOptions(asset_dir=assets))
    kinds = [type(b).__name__ for b in result.document.body]
    assert kinds[:3] == ["Paragraph", "Figure", "Paragraph"]
    caption = result.document.body[2]
    assert isinstance(caption, Paragraph)
    assert caption.props.style == "Caption"
    last = result.document.body[-1]
    assert isinstance(last, Paragraph)
    assert any(isinstance(node, ImageInline) for node in last.content)
    assert " ".join(plain_text(last.content).split()) == "O lance foi decisivo."
    written = sorted(p.name for p in assets.glob("*.png"))
    assert len(written) == 2
    assert all(r.path and Path(r.path).is_file() for r in result.document.resources)
    assert result.report.counters["inline_images"] == 1


# --------------------------------------------------------------------------- #
# Diagrams
# --------------------------------------------------------------------------- #


def _merida_rows(placement: str) -> list[str]:
    light = {
        "P": "p",
        "N": "n",
        "B": "b",
        "R": "r",
        "Q": "q",
        "K": "k",
        "p": "o",
        "n": "m",
        "b": "v",
        "r": "t",
        "q": "w",
        "k": "l",
        ".": " ",
    }
    dark = {
        "P": "P",
        "N": "N",
        "B": "B",
        "R": "R",
        "Q": "Q",
        "K": "K",
        "p": "O",
        "n": "M",
        "b": "V",
        "r": "T",
        "q": "W",
        "k": "L",
        ".": "+",
    }
    rows = []
    for r, rank in enumerate(placement.split("/")):
        cells = []
        for ch in rank:
            cells.extend(["."] * int(ch) if ch.isdigit() else [ch])
        rows.append(
            "".join((light if (r + c) % 2 == 0 else dark)[cell] for c, cell in enumerate(cells))
        )
    return rows


def test_a_vector_diagram_becomes_a_position_with_its_caption(pdf_file, merida_font):
    placement = "8/8/8/4k3/8/8/4K3/8"
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=80, width_chars=60))
    for i, row in enumerate(_merida_rows(placement)):
        spec.text(row, 100, 160 + i * 22, size=22, fontfile=str(merida_font))
    for i, digit in enumerate("87654321"):
        spec.text(digit, 88, 155 + i * 22, size=8)
    spec.text("a b c d e f g h", 105, 348, size=8)
    spec.text("12", 165, 372, size=10)
    spec.text("Brancas jogam", 140, 386, size=10)
    spec.items.extend(lines_of(LOREM_EN, x=72, y=430, width_chars=60))
    path = pdf_file([spec])
    result = import_pdf(path)
    kinds = [type(b).__name__ for b in result.document.body]
    assert kinds == ["Paragraph", "Diagram", "Paragraph"], kinds
    diagram = result.document.body[1]
    assert isinstance(diagram, Diagram)
    assert diagram.fen.split()[0] == placement
    assert diagram.fen.split()[1] == "w"
    assert diagram.number == 12
    assert diagram.side_to_move_indicator
    assert diagram.stipulation == "Brancas jogam"
    assert diagram.recognition.overall_confidence == 1.0
    assert diagram.source.rect is not None
    assert diagram.source.page_index == 0
    assert plain_text(diagram.caption) == "12 Brancas jogam"
    # The labels and the consumed caption are not in the prose.
    texts = paragraphs_of(result.document)
    assert not any(t in ("8", "a b c d e f g h", "12", "Brancas jogam") for t in texts)
    assert result.report.counters["diagrams_read"] == 1
    assert result.report.counters["side_to_move"] == 1
    assert diagram.recognition.side_to_move_source == "text"
    assert result.report.counters["side_to_move_origin:text"] == 1


def test_the_first_move_under_a_vector_diagram_decides_the_side(pdf_file, merida_font):
    """OCR_UI_ROADMAP passo 7: no caption says whose turn; the moves below do."""
    placement = "8/8/8/4k3/8/8/4K3/8"
    spec = PageSpec()
    for i, row in enumerate(_merida_rows(placement)):
        spec.text(row, 100, 160 + i * 22, size=22, fontfile=str(merida_font))
    spec.text("22... Kd5 23.Kd3 Kc5", 100, 372, size=10)
    spec.text("24.Ke3 Kd5", 100, 386, size=10)
    path = pdf_file([spec])
    result = import_pdf(path)
    diagram = next(b for b in result.document.body if isinstance(b, Diagram))
    assert diagram.fen.split()[1] == "b"
    assert diagram.recognition.side_to_move_source == "move-number"
    assert result.report.counters["side_to_move_origin:move-number"] == 1
    assert "22... Kd5" in " ".join(w.strip() for w in diagram.recognition.warnings)


def test_a_custom_finder_can_report_an_unread_diagram(pdf_file):
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=80, width_chars=60))
    spec.items.extend(lines_of(LOREM_EN, x=72, y=500, width_chars=60))
    path = pdf_file([spec])

    def finder(_page, _frame, _text):
        from caissa.core.model import RecognitionPath

        return [DiagramHit(box=(100.0, 200.0, 300.0, 400.0), path=RecognitionPath.GEOMETRIC)]

    result = import_pdf(path, PdfImportOptions(diagram_finder=finder))
    diagram = next(b for b in result.document.body if isinstance(b, Diagram))
    assert diagram.fen.startswith("8/8/8/8/8/8/8/8")
    assert diagram.recognition.overall_confidence == 0.0
    assert any("não lida" in w for w in diagram.recognition.warnings)
    assert result.report.counters["diagrams"] == 1
    assert result.report.counters["diagrams_read"] == 0


@pytest.mark.skipif(find_font("arial.ttf") is None, reason="sem Arial para fazer de figurino")
def test_figurines_become_piece_glyphs(pdf_file):
    """A figurine font's ``N`` is a knight in the IR, not a letter.

    No figurine face is installed here, so Arial plays one through the
    ``figurine_fonts`` option -- the same mechanism a user reaches for when a
    book uses a figurine font the catalogue does not know.
    """
    import pymupdf

    spec = PageSpec()
    spec.text("1.", 72, 100)
    after_number = 72 + pymupdf.get_text_length("1.", fontname="helv", fontsize=11)
    spec.text("N", after_number, 100, fontfile=str(find_font("arial.ttf")))
    knight_width = pymupdf.Font(fontfile=str(find_font("arial.ttf"))).text_length("N", fontsize=11)
    spec.text("f3 e5", after_number + knight_width, 100)
    path = pdf_file([spec])
    paragraph = import_pdf(path, PdfImportOptions(figurine_fonts=("Arial",))).document.body[0]
    assert isinstance(paragraph, Paragraph)
    assert any(isinstance(n, PieceGlyph) for n in paragraph.content)
    assert " ".join(plain_text(paragraph.content).split()) == "1.Nf3 e5"


def test_importer_object_exposes_the_report(pdf_file):
    path = pdf_file([PageSpec().text("Texto de uma página.", 72, 100)])
    with open_pdf(path) as doc:
        importer = PdfImporter(doc, PdfImportOptions(detect_diagrams=False))
        result = importer.run()
    assert result.report is importer.report
    assert "1 página" in result.report.describe_pt()


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP passo 2: a kept layer with damaged notation is contested
# --------------------------------------------------------------------------- #


def _damaged_verdict(confidence: float = 0.55):
    from caissa.ocr.engines.pdf_text_layer import TextLayerVerdict

    return TextLayerVerdict(
        True, "a prosa está legível, mas 43% dos 30 lances perderam o glifo da peça",
        confidence, {"mangled_move_ratio": 0.43, "moves_judged": 30.0}, (), False,
        notation_damaged=True)


def _contest_fixture(pdf_file, monkeypatch, verdict):
    from caissa.ocr.engines.pdf_text_layer import PdfTextLayerEngine

    spec = PageSpec().text("For the present White cannot play 1 'i'xg7 l:txg7 2 'i'd6+", 72, 100)
    path = pdf_file([spec])
    monkeypatch.setattr(PdfTextLayerEngine, "assess", lambda self, page, **kw: verdict)
    calls: list[tuple[int, bool]] = []

    def fake_ocr(_page, frame, verdict) -> PageText:
        calls.append((frame.index, verdict.notation_damaged))
        box = (72.0, 100.0, 300.0, 112.0)
        return PageText(frame=frame, lines=(TextLine(box=box, spans=(
            TextSpan(text="1 Bxg7 Kxg7 2 Qd6+", box=box, size=10.0, confidence=0.8),)),),
            source="tesseract")

    return path, fake_ocr, calls


def test_a_kept_layer_with_damaged_notation_goes_to_the_ocr(pdf_file, monkeypatch):
    path, fake_ocr, calls = _contest_fixture(pdf_file, monkeypatch, _damaged_verdict())
    result = import_pdf(path, PdfImportOptions(ocr=fake_ocr, detect_diagrams=False))
    assert calls == [(0, True)], "the OCR ran on the kept page and saw why"
    page = result.report.pages[0]
    assert page.source == "text-layer+ocr"
    assert result.report.counters["contested_pages"] == 1
    block = result.document.body[0]
    assert isinstance(block, Paragraph)
    assert plain_text(block.content) == "1 Bxg7 Kxg7 2 Qd6+"
    assert block.provenance is not None and block.provenance.kind is SourceKind.OCR


def test_the_contest_is_off_by_option_and_absent_on_a_healthy_layer(pdf_file, monkeypatch):
    from caissa.ocr.engines.pdf_text_layer import TextLayerVerdict

    path, fake_ocr, calls = _contest_fixture(pdf_file, monkeypatch, _damaged_verdict())
    result = import_pdf(path, PdfImportOptions(ocr=fake_ocr, detect_diagrams=False,
                                               ocr_contests_text_layer=False))
    assert calls == [] and result.report.pages[0].source == "text-layer"
    assert result.report.counters["contested_pages"] == 0

    healthy = TextLayerVerdict(True, "camada aceita", 0.98, {"mangled_move_ratio": 0.0,
                                                             "moves_judged": 30.0}, (), False)
    path, fake_ocr, calls = _contest_fixture(pdf_file, monkeypatch, healthy)
    result = import_pdf(path, PdfImportOptions(ocr=fake_ocr, detect_diagrams=False))
    assert calls == [] and result.report.pages[0].source == "text-layer"


def test_the_importer_keeps_the_book_cipher_next_to_the_books_models(pdf_file, monkeypatch,
                                                                     tmp_path):
    """OCR_UI_ROADMAP passo 3: the table is read from and written to
    ``models/tessdata/livros/<slug>/cipher.json`` under the PDF's fingerprint."""
    from caissa.ocr.notation.book_cipher import BookCipher
    from caissa.ocr.training.books import book_dir

    monkeypatch.setenv("CAISSA_FIGURINE_TESSDATA", str(tmp_path))
    path, fake_ocr, _ = _contest_fixture(pdf_file, monkeypatch, _damaged_verdict())
    cipher_path = book_dir(tmp_path, path.stem) / "cipher.json"

    class Provider:
        """A provider that behaves like the service: it carries the table and
        observes on it."""

        book_cipher = None

        def __call__(self, page, frame, verdict):
            for _ in range(5):
                self.book_cipher.observe("W", "Q", page=frame.index, raw="Wd5", san="Qd5")
            return fake_ocr(page, frame, verdict)

    from caissa.ingest.pdf import importer as importer_module

    provider = Provider()
    original = importer_module.PdfImporter._ocr_provider

    def with_table(self):
        if provider.book_cipher is None:
            provider.book_cipher = self._load_book_cipher()
            self._ocr_service = provider
        return provider

    monkeypatch.setattr(importer_module.PdfImporter, "_ocr_provider", with_table)
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False))
    assert cipher_path.is_file(), "the table was saved with the book's models"
    assert result.report.counters["cipher_proven"] == 1
    saved = BookCipher.load(cipher_path)
    assert saved is not None and saved.proven() == {"W": "Q"}
    assert any("cifra do livro" in n and "gravada" in n for n in result.report.notes)

    # Off: neither read nor written.
    cipher_path.unlink()
    provider.book_cipher = None
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False, book_cipher=False))
    assert not cipher_path.exists()
    monkeypatch.setattr(importer_module.PdfImporter, "_ocr_provider", original)
