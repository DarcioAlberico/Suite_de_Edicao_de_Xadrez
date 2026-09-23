"""Sol §SOL-1: the default OCR provider of the importer.

The first half drives :class:`OcrService` with a mock engine, so the
plumbing -- resolution choice, region decisions, the portfolio, the
conversion to :class:`PageText` with per-span provenance -- is pinned
without Tesseract.  The second half needs Tesseract and proves the
acceptance criteria of §SOL-1 on real PDFs built here: a scanned page is
read without any callback, a blank scan is abstained and kept as an image,
a born-digital page is never rasterised.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pymupdf
import pytest

from caissa.core.model import ConfidenceBand, ImageBlock, Paragraph, SourceKind, plain_text
from caissa.ingest.pdf.importer import PdfImportOptions, import_pdf
from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig
from caissa.ocr.decision import Decision
from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

from .conftest import LOREM_EN, PageSpec, lines_of

PROSE = ("The rook belongs behind the passed pawn and the defender simply waits "
         "while the attacking side loses time with every step of the king")


class MockRaster:
    """A level-1 engine that reads a fixed text, laid out over the crop."""

    name = "mock_raster"

    def __init__(self, text: str = PROSE, confidence: float = 0.95) -> None:
        self.text = text
        self.confidence = confidence
        self.calls: list[tuple[int, int]] = []

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def languages(self) -> set[str]:
        return {"eng", "por"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(level=EngineLevel.TESSERACT, cost_per_megapixel_s=0.1,
                                  supports_char_boxes=False, supports_confidence=True,
                                  handles_layout=True)

    @property
    def version(self) -> str:
        return "mock 1.0"

    def recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
        h, w = image.shape[:2]
        self.calls.append((h, w))
        words = []
        x = 10.0
        for i, token in enumerate(self.text.split()):
            width = min(9.0 * len(token), max(10.0, w - x - 1))
            words.append(OcrWord(text=token, box=BBox(x, 8.0, width, 18.0),
                                 confidence=self.confidence, word_index=i))
            x += width + 6.0
            if x > w - 20:
                x = 10.0
        line = OcrLine(words=tuple(words), box=BBox(10.0, 8.0, max(20.0, w - 20.0), 18.0))
        return OcrResult(engine=self.name, lang=lang, lines=(line,), region_kind=psm_hint)


def inked_page(h: int = 400, w: int = 1200) -> np.ndarray:
    image = np.full((h, w), 248, dtype=np.uint8)
    image[8:26, ::3] = 10
    return image


# --------------------------------------------------------------------------- #
# The service with a mock engine
# --------------------------------------------------------------------------- #


def test_recognize_image_reads_accepts_and_traces():
    service = OcrService([MockRaster()], OcrServiceConfig(use_portfolio=False), lang="eng")
    recognition = service.recognize_image(inked_page(), dpi=300, lang="eng")
    assert recognition.answered
    assert recognition.decision is Decision.ACCEPTED
    assert recognition.text.startswith("The rook belongs")
    assert recognition.engine == "mock_raster"
    assert recognition.engines == {"mock_raster": "mock 1.0"}
    trace = recognition.trace()
    assert trace["regions"][0]["decision"]["decision"] == "accepted"
    assert trace["regions"][0]["candidates"][0]["variant"] == "original"


def test_a_blank_raster_is_abstained_and_emits_nothing():
    engine = MockRaster(confidence=0.99)
    service = OcrService([engine], OcrServiceConfig(use_portfolio=False), lang="eng")
    blank = np.full((400, 1200), 250, dtype=np.uint8)
    recognition = service.recognize_image(blank, dpi=300, lang="eng")
    assert not recognition.answered
    assert recognition.decision is Decision.ABSTAINED
    assert recognition.text == ""
    assert "sem tinta" in " ".join(recognition.regions[0].decision.reasons_pt)


def test_page_text_carries_confidence_engine_and_review_per_span():
    from caissa.ingest.pdf.geometry import PageFrame

    service = OcrService([MockRaster(confidence=0.55)], OcrServiceConfig(use_portfolio=False),
                         lang="eng")
    recognition = service.recognize_image(inked_page(), dpi=300, lang="eng")
    assert recognition.decision is Decision.REVIEW, recognition.regions[0].decision.describe_pt()
    frame = PageFrame.synthetic(3, 288.0, 96.0)
    text = recognition.to_page_text(frame)
    assert text.source == "mock_raster"
    span = text.lines[0].spans[0]
    assert span.engine == "mock_raster"
    assert span.review is True
    assert span.confidence == pytest.approx(0.55)
    # 300 DPI pixels back to points: x 10 px -> 2.4 pt.
    assert span.box[0] == pytest.approx(2.4)


def test_the_portfolio_is_tried_only_when_the_original_is_not_accepted():
    engine = MockRaster(confidence=0.55)
    small = inked_page(h=300, w=900)
    service = OcrService([engine], OcrServiceConfig(use_portfolio=True), lang="eng")
    recognition = service.recognize_image(small, dpi=150, lang="eng")
    region = recognition.regions[0]
    assert recognition.portfolio is not None
    assert "upscale" in recognition.portfolio.names
    assert {c.variant for c in region.candidates} >= {"original", "upscale"}
    assert len(engine.calls) >= 2

    engine.calls.clear()
    accepted = OcrService([MockRaster(confidence=0.95)], OcrServiceConfig(use_portfolio=True),
                          lang="eng")
    recognition = accepted.recognize_image(small, dpi=150, lang="eng")
    assert recognition.portfolio is None
    assert [c.variant for c in recognition.regions[0].candidates] == ["original"]


def test_provider_protocol_returns_none_when_nothing_is_emitted(tmp_path: Path):
    from caissa.ingest.pdf.document import open_pdf
    from caissa.ocr.engines.pdf_text_layer import TextLayerVerdict

    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40), 0)
    pix.clear_with(250)
    page.insert_image(pymupdf.Rect(0, 0, 300, 200), pixmap=pix)
    path = tmp_path / "blank.pdf"
    doc.save(path)
    doc.close()
    service = OcrService([MockRaster(confidence=0.99)], OcrServiceConfig(use_portfolio=False),
                         lang="eng")
    document = open_pdf(path)
    try:
        frame = document.frame(0)
        with document.locked() as raw:
            verdict = TextLayerVerdict(False, "a página não contém texto.", 0.0, {}, (), True)
            assert service(raw[0], frame, verdict) is None
    finally:
        document.close()
    assert service.last is not None
    assert service.last.decision is Decision.ABSTAINED


# --------------------------------------------------------------------------- #
# The importer, end to end
# --------------------------------------------------------------------------- #


def _tesseract() -> bool:
    from caissa.ocr.engines.tesseract import find_tesseract

    return find_tesseract() is not None


requires_tesseract = pytest.mark.skipif(not _tesseract(), reason="Tesseract não instalado")


def _scanned_pdf(tmp_path: Path, text: str | None) -> Path:
    """A one-page PDF that is a picture of ``text`` (or of blank paper)."""
    source = pymupdf.open()
    page = source.new_page(width=612, height=792)
    if text:
        for n, line in enumerate(_wrap(text, 70)):
            page.insert_text(pymupdf.Point(72, 110 + n * 16), line, fontsize=11,
                             fontname="tiro")
    pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
    source.close()
    scan = pymupdf.open()
    target = scan.new_page(width=612, height=792)
    target.insert_image(pymupdf.Rect(0, 0, 612, 792), pixmap=pix)
    path = tmp_path / ("scan.pdf" if text else "blank.pdf")
    scan.save(path)
    scan.close()
    return path


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    return textwrap.wrap(text, width)


@requires_tesseract
def test_a_scanned_page_is_read_by_default_without_any_callback(tmp_path: Path):
    path = _scanned_pdf(tmp_path, LOREM_EN + " " + PROSE + ". " + LOREM_EN)
    result = import_pdf(path, PdfImportOptions(lang="eng"))
    report = result.report.pages[0]
    assert report.source == "ocr", report.verdict
    assert report.ocr_engine == "tesseract"
    assert report.ocr_dpi >= 300
    assert report.ocr_decisions["accepted"] + report.ocr_decisions["review"] >= 1
    paragraphs = [b for b in result.document.body if isinstance(b, Paragraph)]
    assert paragraphs
    text = " ".join(plain_text(p.content) for p in paragraphs)
    assert "passed pawn" in text
    assert paragraphs[0].provenance is not None
    assert paragraphs[0].provenance.kind is SourceKind.OCR
    assert paragraphs[0].provenance.engine == "tesseract"
    assert paragraphs[0].provenance.dpi == pytest.approx(report.ocr_dpi)
    assert not result.report.notes


@requires_tesseract
def test_a_blank_scan_is_abstained_and_kept_as_an_image(tmp_path: Path):
    path = _scanned_pdf(tmp_path, None)
    result = import_pdf(path, PdfImportOptions(lang="eng"))
    report = result.report.pages[0]
    assert report.source == "image-only"
    assert report.ocr_decisions.get("accepted", 0) == 0
    blocks = [b for b in result.document.body if isinstance(b, ImageBlock)]
    assert len(blocks) == 1
    assert not any(isinstance(b, Paragraph) for b in result.document.body)


@requires_tesseract
def test_ocr_can_be_switched_off_for_a_fast_import(tmp_path: Path):
    path = _scanned_pdf(tmp_path, LOREM_EN)
    result = import_pdf(path, PdfImportOptions(lang="eng", enable_ocr=False))
    assert result.report.pages[0].source == "image-only"
    assert result.report.pages[0].ocr_engine == ""


def test_a_native_page_is_never_rasterised(pdf_file, monkeypatch):
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM_EN, x=72, y=100, width_chars=60))
    path = pdf_file([spec])
    rendered: list[int] = []
    monkeypatch.setattr(OcrService, "render",
                        staticmethod(lambda page, dpi: rendered.append(dpi)))
    result = import_pdf(path, PdfImportOptions(lang="eng"))
    assert result.report.pages[0].source == "text-layer"
    assert rendered == []


def test_review_regions_are_listed_with_their_rectangles(pdf_file, monkeypatch):
    """A custom provider whose trace says one region needs review."""
    spec = PageSpec(images=[(0.0, 0.0, 612.0, 792.0, 200, 260)])
    path = pdf_file([spec])
    service = OcrService([MockRaster(confidence=0.55)], OcrServiceConfig(use_portfolio=False),
                         lang="eng")

    def fake_render(page, dpi):
        return inked_page(h=int(792 * dpi / 72), w=int(612 * dpi / 72))

    monkeypatch.setattr(OcrService, "render", staticmethod(fake_render))
    result = import_pdf(path, PdfImportOptions(lang="eng", ocr=service))
    assert result.report.pages[0].source == "ocr"
    assert result.report.pages[0].ocr_review == 1
    assert len(result.report.review_items) == 1
    item = result.report.review_items[0]
    assert item.decision == "review"
    assert item.page_index == 0
    assert item.rect[2] > item.rect[0]
    assert "abaixo do limite" in " ".join(item.reasons)
    paragraph = next(b for b in result.document.body if isinstance(b, Paragraph))
    assert paragraph.provenance is not None
    assert paragraph.provenance.band in (ConfidenceBand.DOUBTFUL, ConfidenceBand.UNRELIABLE)
    assert "revisão" in (paragraph.provenance.note or "")


# --------------------------------------------------------------------------- #
# The book's own model (caissa.ocr.training.books)
# --------------------------------------------------------------------------- #


def test_the_importer_points_the_service_at_the_books_model(pdf_file, monkeypatch, tmp_path):
    from caissa.ingest.pdf.document import open_pdf
    from caissa.ingest.pdf.importer import PdfImporter
    from caissa.ocr.training import BookRegistry, FineTuneReport, register_training

    path = pdf_file([PageSpec()])
    root = tmp_path / "tessdata"
    monkeypatch.setenv("CAISSA_FIGURINE_TESSDATA", str(root))
    with open_pdf(path) as document:
        importer = PdfImporter(document, PdfImportOptions(lang="eng"))
        assert importer._book_ocr_config().figurine_tessdata is None
        assert importer.report.notes == [], "an unregistered book gets no note"

    out = root / "livros" / "livro"
    out.mkdir(parents=True)
    (out / "caissa_eng.traineddata").write_bytes(b"model")
    register_training(
        BookRegistry.default(),
        path,
        "livro",
        FineTuneReport(model_name="caissa_eng", out_dir=out, model_path=str(out / "caissa_eng.traineddata"),
                       finished_at="2026-09-14T00:00:00+00:00", lines_train=10, status="trained"),
    )
    with open_pdf(path) as document:
        importer = PdfImporter(document, PdfImportOptions(lang="eng"))
        config = importer._book_ocr_config()
        assert config.figurine_tessdata == str(out.resolve())
        assert config.figurine_candidates
        assert config.book_model_anchors, "passo 4b: inside its book the model anchors"
        assert importer.report.notes == [
            "modelo ajustado para este livro: caissa_eng · treinado em 2026-09-14 · 10 linhas de treino"
        ]
        # The service built from it reads the book's directory.
        service = OcrService(lang="eng", config=config)
        assert service._figurine_directory() == out.resolve()
        # Switched off, the default service is used and nothing is noted.
        importer = PdfImporter(document, PdfImportOptions(lang="eng", book_models=False))
        assert importer._book_ocr_config().figurine_tessdata is None
        assert importer.report.notes == []
    # Another book with the same name is not the same book.
    other = pdf_file([PageSpec(), PageSpec()], name="livro.pdf")
    with open_pdf(other) as document:
        assert PdfImporter(document)._book_ocr_config().figurine_tessdata is None


def test_the_secondary_engine_enters_only_where_the_portfolio_enters():
    """OCR_UI_ROADMAP passo 1: a clean page keeps the level-0/1 cascade; a page
    whose signals justify a variant gets the named secondary engines too."""
    from caissa.ocr.engines.base import EngineCapabilities, EngineLevel

    class Secondary(MockRaster):
        name = "rapidocr"

        def capabilities(self) -> EngineCapabilities:
            return EngineCapabilities(level=EngineLevel.PADDLE, cost_per_megapixel_s=1.2,
                                      supports_char_boxes=False, supports_confidence=True,
                                      handles_layout=False)

    class Registry:
        def __init__(self, engines):
            self._engines = engines

        def available(self, lang=None):
            return list(self._engines)

    import caissa.ocr.engines.registry as registry_module

    engines = [MockRaster(confidence=0.9), Secondary(confidence=0.9)]
    original = registry_module.default_registry
    registry_module.default_registry = lambda: Registry(engines)
    try:
        service = OcrService(config=OcrServiceConfig(secondary_engines=("rapidocr",),
                                                     use_portfolio=False), lang="eng")
        with_secondary = [e.name for e in service.engines_for("eng", secondary=True)]
        without = [e.name for e in service.engines_for("eng", secondary=False)]
        assert "rapidocr" in with_secondary
        assert "rapidocr" not in without
        notes: list[str] = []
        clean = np.full((400, 1200), 248, dtype=np.uint8)
        clean[8:26, ::3] = 10
        wants, _ = service._wants_secondary(clean, 300, notes)
        assert wants is False and notes == []
        rng = np.random.default_rng(1)
        noisy = np.clip(clean.astype(np.float32) + rng.normal(0, 14, clean.shape),
                        0, 255).astype(np.uint8)
        wants, signals = service._wants_secondary(noisy, 300, notes)
        assert wants is True and signals is not None
        assert notes and "motor secundário" in notes[0]
        always = OcrService(config=OcrServiceConfig(secondary_engines=("rapidocr",),
                                                    secondary_only_when_degraded=False))
        assert always._wants_secondary(clean, 300, []) == (True, None)
    finally:
        registry_module.default_registry = original


def test_an_engine_that_fails_on_the_region_is_said_on_the_page(monkeypatch):
    """Crítico da fase 5, ciclo 4 (the Stean p. 165): RapidOCR runs in this process, and without
    memory its allocation fails -- ``RuntimeError("bad allocation")``, the form onnxruntime
    takes.  ``OcrEngineBase.recognize`` turns it into an empty reading with the warning, the
    arbiter goes on with the engine that answered, and the page read by one engine looked like a
    page read by two.  The page now names the engine that failed, and why.  The sabotage: the
    failure without its mark (as before) is silent."""
    from caissa.ocr.engines.base import OcrEngineBase

    class SemMemoria(OcrEngineBase):
        name = "rapidocr"
        version = "sem memória"

        def _probe(self) -> tuple[bool, str | None]:
            return True, None

        def _discover_languages(self) -> set[str]:
            return {"eng", "por"}

        def capabilities(self) -> EngineCapabilities:
            return EngineCapabilities(level=EngineLevel.PADDLE, cost_per_megapixel_s=1.2,
                                      supports_char_boxes=False, supports_confidence=True,
                                      handles_layout=False)

        def _recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
            raise RuntimeError("bad allocation")

    config = OcrServiceConfig(use_portfolio=False, movetext_candidates=False,
                              glyph_candidates=False)
    service = OcrService([MockRaster(confidence=0.40), SemMemoria()], config, lang="eng")
    recognition = service.recognize_image(inked_page(), dpi=300, lang="eng")
    assert recognition.text.startswith("The rook belongs"), "read by the engine that answered"
    falhas = [n for n in recognition.notes if "falhou" in n]
    assert len(falhas) == 1, recognition.notes
    assert "rapidocr" in falhas[0]
    assert "bad allocation" in falhas[0]
    # the sabotage: the empty reading without the mark, as OcrEngineBase gave it before
    import caissa.ocr.engines.base as base_module

    sem_marca = base_module.empty_result
    monkeypatch.setattr(base_module, "empty_result",
                        lambda *a, failed=False, **kw: sem_marca(*a, **kw))
    silent = OcrService([MockRaster(confidence=0.40), SemMemoria()], config, lang="eng")
    assert not [n for n in silent.recognize_image(inked_page(), dpi=300, lang="eng").notes
                if "falhou" in n]


def test_the_books_model_takes_the_anchor_seat_only_inside_its_book(tmp_path: Path, monkeypatch):
    """OCR_UI_ROADMAP passo 4b: with ``figurine_tessdata`` pointing at a book
    registered for the PDF, the tuned Tesseract replaces the base one as anchor
    and the figurine candidate stands down; the global fallback directory and
    a language the book has no model for keep the candidate path of §4c."""
    from caissa.ocr.engines.tesseract import TunedTesseractEngine

    class Registry:
        def available(self, lang=None):
            return [MockRaster(confidence=0.9)]

    class Tuned(TunedTesseractEngine):
        name = "mock_raster"  # the seat it takes

        def available(self) -> bool:
            return True

        def supports_language(self, lang: str) -> bool:
            return True

    import caissa.ocr.engines.registry as registry_module

    book = tmp_path / "livro"
    book.mkdir()
    (book / "caissa_eng.traineddata").write_bytes(b"model")
    (book / "eng.traineddata").write_bytes(b"base")
    original = registry_module.default_registry
    registry_module.default_registry = lambda: Registry()
    monkeypatch.setattr("caissa.ocr.engines.tesseract.TunedTesseractEngine", Tuned)
    try:
        inside = OcrService(lang="eng", config=OcrServiceConfig(figurine_tessdata=str(book)))
        anchor = inside.book_anchor("eng")
        assert isinstance(anchor, Tuned)
        assert anchor.tuned_lang("eng+deu") == "caissa_eng+deu"
        assert [type(e).__name__ for e in inside.engines_for("eng")] == ["Tuned"]
        assert inside.book_anchor("deu") is None, "no model for the book's language: no anchor"
        assert [type(e).__name__ for e in inside.engines_for("deu")] == ["MockRaster"]

        off = OcrService(lang="eng", config=OcrServiceConfig(figurine_tessdata=str(book),
                                                             book_model_anchors=False))
        assert off.book_anchor("eng") is None
        assert [type(e).__name__ for e in off.engines_for("eng")] == ["MockRaster"]

        nowhere = OcrService(lang="eng", config=OcrServiceConfig())
        assert nowhere.book_anchor("eng") is None, "the global fallback never anchors"
    finally:
        registry_module.default_registry = original


def test_the_tuned_engine_maps_languages_and_hands_back_the_requested_one(tmp_path: Path):
    from caissa.ocr.engines.tesseract import TunedTesseractEngine
    from caissa.ocr.types import OcrResult

    book = tmp_path / "livro"
    book.mkdir()
    (book / "caissa_eng.traineddata").write_bytes(b"model")
    engine = TunedTesseractEngine(book)
    assert engine.config.tessdata_dir == str(book)
    assert engine.tuned_lang("eng") == "caissa_eng"
    assert engine.tuned_lang("por+eng") == "por+caissa_eng"
    assert engine.has_model_for("eng+deu")
    assert not engine.has_model_for("deu+eng"), "the book's own language is the first part"
    seen: list[str] = []

    def fake(self, image, *, lang, psm_hint):
        seen.append(lang)
        return OcrResult(engine="tesseract", lang=lang, lines=(), region_kind=psm_hint)

    from caissa.ocr.engines.tesseract import TesseractEngine

    original = TesseractEngine._recognize
    TesseractEngine._recognize = fake
    try:
        result = engine._recognize(np.zeros((10, 10), dtype=np.uint8), lang="eng",
                                   psm_hint=RegionKind.PARAGRAPH)
    finally:
        TesseractEngine._recognize = original
    assert seen == ["caissa_eng"]
    assert result.lang == "eng", "the caller's language comes back: lexicon and decision key on it"
    assert result.meta["model"] == "caissa_eng"
    assert result.engine == "tesseract", "to the fusion it is the anchor"
