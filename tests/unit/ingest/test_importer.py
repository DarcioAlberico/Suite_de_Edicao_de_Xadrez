"""The whole pipeline on synthetic books whose IR is known in advance."""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.core.model import (
    ConfidenceBand,
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


def test_a_cancel_at_thirty_percent_keeps_thirty_percent_of_the_pages(pdf_file):
    """OCR_UI_ROADMAP passo 17 (R3.5): the partial result is the pages built so far.

    Ten pages; the cancel flag rises after the third page is built (progress in the build
    pass is ``total + n + 1`` of ``2 * total``).  The document must carry exactly the three
    pages, the report must say it was canceled and how many were planned.  The sabotage the
    roadmap names -- "a cancel that throws the partial away" -- is the ``keep_partial=False``
    default, asserted right below as an empty result raising ``ImportCanceled``.
    """
    pages = [
        PageSpec().text(f"Página {i} com texto suficiente para contar.", 72, 100)
        for i in range(10)
    ]
    path = pdf_file(pages)
    built: list[int] = []

    def progress(done: int, total: int) -> None:
        if done > total // 2:
            built.append(done - total // 2)

    result = import_pdf(
        path,
        PdfImportOptions(
            progress=progress,
            should_cancel=lambda: len(built) >= 3,
            keep_partial=True,
        ),
    )
    assert result.report.canceled is True
    assert result.report.pages_planned == 10
    assert [p.index for p in result.report.pages] == [0, 1, 2]
    assert result.report.pages_built == 3
    assert any("cancelada" in note for note in result.report.notes)

    # The complete import of the same book, for the denominator: the partial document is
    # the head of the whole one -- three of ten pages of text, block for block.
    whole = import_pdf(path, PdfImportOptions())
    assert whole.report.canceled is False
    assert [p.index for p in whole.report.pages][:3] == [0, 1, 2]
    assert 0 < len(result.document.body) < len(whole.document.body)
    assert [type(b).__name__ for b in result.document.body] == [
        type(b).__name__ for b in whole.document.body[: len(result.document.body)]
    ]
    assert len(result.document.body) * 10 // len(whole.document.body) == 3

    # The sabotage: without ``keep_partial`` the same cancel discards everything.
    built.clear()
    with pytest.raises(ImportCanceled):
        import_pdf(path, PdfImportOptions(progress=progress, should_cancel=lambda: len(built) >= 3))


def test_a_cancel_during_the_survey_returns_an_empty_document_marked_canceled(pdf_file):
    pages = [PageSpec().text(f"Página {i}.", 72, 100) for i in range(4)]
    path = pdf_file(pages)
    result = import_pdf(path, PdfImportOptions(should_cancel=lambda: True, keep_partial=True))
    assert result.report.canceled is True
    assert result.report.pages_built == 0
    assert result.report.pages_planned == 4


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


def test_a_failing_ocr_provider_does_not_lose_the_book(pdf_file, monkeypatch):
    """And the page it failed on is in the review queue, not only in the notes (crítico da fase 5,
    ciclo 5: a ``MemoryError`` left «OCR falhou na página 165» in the notes and no review item --
    the page was gone from the list someone reads page by page).  The sabotage: the page is not
    listed."""
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])

    def broken(*_args):
        raise MemoryError("bad allocation")

    result = import_pdf(path, PdfImportOptions(ocr=broken))
    assert result.report.pages[0].source == "image-only"
    assert any("bad allocation" in note for note in result.report.notes)
    review = [i for i in result.report.review_items if i.page_index == 0]
    assert len(review) == 1, review
    assert review[0].kind == "page" and review[0].decision == "abstained"
    assert "O OCR falhou nesta página" in review[0].reasons[0]
    assert "bad allocation" in review[0].reasons[0]
    monkeypatch.setattr(PdfImporter, "_failed_for_review", lambda self, frame, ocr: None)
    sabotaged = import_pdf(path, PdfImportOptions(ocr=broken))
    assert sabotaged.report.review_items == []


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
    # ``games=False``: from move 1 the line would chain into a game (passo 11).
    options = PdfImportOptions(figurine_fonts=("Arial",), games=False)
    paragraph = import_pdf(path, options).document.body[0]
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


def _accepted_text_blocks(result) -> list:
    """Text blocks on pages nothing marked for review -- what the rail calls clean."""
    flagged = {item.page_index for item in result.report.review_items}
    return [
        b for b in result.document.body
        if isinstance(b, Paragraph) and b.provenance is not None
        and b.provenance.page_index not in flagged
    ]


@pytest.mark.parametrize(
    ("shape", "fragment"),
    [
        ("raises", "o provedor falhou"),
        ("none", "não emitiu texto"),
        ("empty", "texto vazio"),
    ],
)
def test_a_contested_layer_whose_ocr_says_nothing_is_never_the_layer_again(
    pdf_file, monkeypatch, shape: str, fragment: str
) -> None:
    """OCR_UI ciclo 2, passo A8 (análise §7.2): an accused layer whose contest came back
    empty used to return as ``text-layer`` at the layer's own confidence.  Now the page
    keeps its prose but goes to review, at a doubtful confidence, and the report names it.
    """
    # A verdict that kept the layer at its full confidence while accusing the notation:
    # what used to come back untouched when the contest had nothing to say.
    path, _, _ = _contest_fixture(pdf_file, monkeypatch, _damaged_verdict(confidence=0.98))
    baseline = import_pdf(path, PdfImportOptions(ocr=lambda *a: None, detect_diagrams=False,
                                                 ocr_contests_text_layer=False))
    assert baseline.report.pages[0].source == "text-layer"
    assert baseline.report.pages[0].confidence == 0.98
    accepted_before = _accepted_text_blocks(baseline)
    assert accepted_before, "the normal round accepts the layer's text"

    def provider(_page, frame, _verdict):
        if shape == "raises":
            raise RuntimeError("motor caiu")
        if shape == "none":
            return None
        return PageText(frame=frame, lines=(), source="tesseract")

    result = import_pdf(path, PdfImportOptions(ocr=provider, detect_diagrams=False))
    page = result.report.pages[0]
    assert page.source == "text-layer/review"
    assert page.confidence <= 0.6
    assert fragment in page.verdict
    assert len(_accepted_text_blocks(result)) < len(accepted_before), (
        "the sabotaged round must not accept as much text as the normal one"
    )
    assert any("página 1" in n and "para revisão" in n for n in result.report.notes)
    review = [i for i in result.report.review_items if i.page_index == 0]
    assert review
    assert review[0].decision == "review"
    assert any(fragment in r for r in review[0].reasons)
    # The prose is still there -- doubtful, not dropped.
    assert any(isinstance(b, Paragraph) for b in result.document.body)
    assert all(
        b.provenance.band in (ConfidenceBand.DOUBTFUL, ConfidenceBand.UNRELIABLE)
        for b in result.document.body if isinstance(b, Paragraph) and b.provenance is not None
    )


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


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP passo 14: the reviewer's decisions are applied on import
# --------------------------------------------------------------------------- #


class _ServiceLikeOcr:
    """A provider shaped like ``OcrService``.

    It keeps ``last``, the page recognition, which is what the decisions are applied to.
    """

    def __init__(self) -> None:
        self.last = None

    def __call__(self, _page, frame, _verdict):
        from caissa.ingest.pdf.ocr_service import PageRecognition, RegionRecognition
        from caissa.ocr.decision import Decision, RegionDecision
        from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

        def region(order, y_px, text, decision):
            box = BBox(300.0, y_px, 950.0, 50.0)
            words = tuple(OcrWord(text=w, box=box, confidence=0.7) for w in text.split())
            result = OcrResult(engine="tesseract", lang="eng", lines=(
                OcrLine(words=words, box=box, kind=RegionKind.PARAGRAPH),))
            return RegionRecognition(
                reading_order=order, kind=RegionKind.PARAGRAPH, box_px=box, result=result,
                decision=RegionDecision(decision, 0.7, 0.78, 0.55, ("Escore baixo",)),
                engine="tesseract", variant="base", score=0.7)

        self.last = PageRecognition(page_index=frame.index, dpi=300.0, regions=[
            region(0, 400.0, "the r0ok belongs", Decision.REVIEW),
            region(1, 1200.0, "a clean line", Decision.ACCEPTED),
        ], portfolio=None, notes=[], duration_s=0.1, whole_page=False, engines={})
        return self.last.to_page_text(frame)


class _WholePageOcr(_ServiceLikeOcr):
    """The page read again after an OCR that raised: one region over the whole page, for review --
    the Gallagher p. 54 of the critic (fase 5, ciclo 6), whose region the arbiter sent to review for
    moves it suspected were invented."""

    def __call__(self, _page, frame, _verdict):
        from caissa.ingest.pdf.ocr_service import PageRecognition, RegionRecognition
        from caissa.ocr.decision import Decision, RegionDecision
        from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

        box = BBox(0.0, 0.0, frame.width * 300.0 / 72.0, frame.height * 300.0 / 72.0)
        words = tuple(OcrWord(text=w, box=box, confidence=0.6)
                      for w in ("1", "e4", "e5", "2", "e4", "e5"))
        result = OcrResult(engine="tesseract", lang="eng", lines=(
            OcrLine(words=words, box=box, kind=RegionKind.PARAGRAPH),))
        self.last = PageRecognition(page_index=frame.index, dpi=300.0, regions=[RegionRecognition(
            reading_order=0, kind=RegionKind.PARAGRAPH, box_px=box, result=result,
            decision=RegionDecision(Decision.REVIEW, 0.6, 0.78, 0.55,
                                    ("sequência de lances repetida: suspeita de invenção",)),
            engine="tesseract", variant="base", score=0.6)],
            portfolio=None, notes=[], duration_s=0.1, whole_page=True, engines={})
        return self.last.to_page_text(frame)


def test_an_accept_of_the_page_nobody_read_accepts_nothing_on_the_next_import(
        pdf_file, monkeypatch):
    """Crítico da fase 5, ciclo 6: the OCR raised on the page, the page item went to the review
    queue with no reading, and the Enter on its empty truth recorded an accept over the whole page;
    the next import applied it to the reading that came then -- «aceita pelo revisor», verified, out
    of the queue.  The window refuses the accept, and an accept written anyway (an older window, a
    script) settles nothing: the page is still for review.  The sabotage: the accept of nothing
    counts, and the page leaves the queue accepted."""
    from caissa.ocr import review
    from caissa.ocr.review import Action, ReviewQueue

    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])

    def broken(*_args):
        raise MemoryError("bad allocation")

    failed = import_pdf(path, PdfImportOptions(ocr=broken, detect_diagrams=False))
    queue = ReviewQueue.from_import(failed.report, document="livro", reviewer="ana")
    (item,) = queue.items
    assert item.kind == "page"
    assert item.text == ""
    assert "não há leitura para aceitar" in queue.refusal(item.key, Action.ACCEPT)
    queue.decide(item.key, Action.ACCEPT)
    written = review.ReviewDecisions(entries=(
        review.Decided(item.page_index, item.rect, Action.ACCEPT, reviewer="ana"),))

    for decisions in (queue.decisions(), written):
        provider = _WholePageOcr()
        again = import_pdf(path, PdfImportOptions(
            ocr=provider, detect_diagrams=False, review_decisions=decisions))
        assert again.report.counters["review_decisions_applied"] == 0
        assert [i.page_index for i in again.report.review_items] == [0]
        (region,) = provider.last.regions
        assert not region.verified
        assert "aceita pelo revisor" not in region.decision.reasons_pt

    monkeypatch.setattr(review, "accepts_nothing", lambda action, reading: False)
    provider = _WholePageOcr()
    sabotaged = import_pdf(path, PdfImportOptions(
        ocr=provider, detect_diagrams=False, review_decisions=written))
    assert sabotaged.report.counters["review_decisions_applied"] == 1
    assert sabotaged.report.review_items == []
    (region,) = provider.last.regions
    assert region.verified
    assert "aceita pelo revisor" in region.decision.reasons_pt


def test_review_decisions_settle_the_region_on_import(pdf_file):
    from caissa.ocr.review import Action, Decided, ReviewDecisions

    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    before = import_pdf(path, PdfImportOptions(ocr=_ServiceLikeOcr(), detect_diagrams=False))
    assert [i.text for i in before.report.review_items] == ["the r0ok belongs"]
    doubtful = before.document.body[0]
    assert isinstance(doubtful, Paragraph)
    assert not doubtful.provenance.verified_by_human
    rect = before.report.review_items[0].rect
    decisions = ReviewDecisions(entries=(
        Decided(0, rect, Action.EDIT, text="the rook belongs", reviewer="ana"),))
    after = import_pdf(path, PdfImportOptions(
        ocr=_ServiceLikeOcr(), detect_diagrams=False, review_decisions=decisions))
    assert after.report.review_items == []
    assert after.report.counters["review_decisions_applied"] == 1
    settled = after.document.body[0]
    assert isinstance(settled, Paragraph)
    assert plain_text(settled.content) == "the rook belongs"
    assert settled.provenance.verified_by_human
    assert settled.provenance.confidence == 1.0
    assert "revisor" in (settled.provenance.note or "")
    clean = after.document.body[1]
    assert not clean.provenance.verified_by_human, "the reviewer did not touch the clean line"
