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
