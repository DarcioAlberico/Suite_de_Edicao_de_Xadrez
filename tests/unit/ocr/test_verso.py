"""OCR_UI_ROADMAP_C2 passo B8: the real verso reaches the bleed step.

``BleedThroughReduction.register_verso`` was written in Sol and nothing ever
handed it a verso: ``PortfolioConfig.verso`` stayed ``None``.  Now the
service offers the bleed step the neighbouring pages of the PDF (and the
page's own mirror), keeps the one that registers best, and the portfolio
builds a ``bleed_verso`` variant **next to** the heuristic one — measured on
``shadow_curl_bleed`` neither wins every page, so the arbiter chooses.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig
from caissa.ocr.page import PageTask
from caissa.ocr.portfolio import PortfolioConfig, build_portfolio, detect_signals

from .conftest import render_text_page, requires_font


@pytest.fixture(scope="module")
def page_and_verso() -> tuple[np.ndarray, np.ndarray]:
    """A page and a *different* page that shows through it, mirrored."""
    recto, _ = render_text_page(font_size=44, wrap=44)
    verso, _ = render_text_page(font_size=44, wrap=38, repeat=6)
    if verso.shape != recto.shape:
        verso = cv2.resize(verso, (recto.shape[1], recto.shape[0]))
    mirrored = cv2.GaussianBlur(cv2.flip(verso, 1), (0, 0), 1.2)
    show = 255 - (255 - mirrored.astype(np.float32)) * 0.25
    bled = np.minimum(recto.astype(np.float32), show).astype(np.uint8)
    return bled, verso


@requires_font
def test_a_verso_in_hand_builds_the_verso_variant_next_to_the_heuristic(page_and_verso):
    bled, verso = page_and_verso
    signals = detect_signals(bled, dpi=300)
    assert signals.bleed_share >= PortfolioConfig().min_bleed_share
    portfolio = build_portfolio(bled, dpi=300, signals=signals,
                                config=PortfolioConfig(verso=verso))
    assert "bleed_sauvola" in portfolio.names and "bleed_verso" in portfolio.names
    heuristic = next(v for v in portfolio.variants if v.name == "bleed_sauvola")
    registered = next(v for v in portfolio.variants if v.name == "bleed_verso")
    modes = {v.name: next(s.detail.get("mode") for s in v.steps if s.name == "bleed_through")
             for v in (heuristic, registered)}
    # Only the verso variant saw the verso; the heuristic stays what it was measured as.
    assert modes == {"bleed_sauvola": "heuristic", "bleed_verso": "verso"}
    detail = next(s.detail for s in registered.steps if s.name == "bleed_through")
    assert detail["correlation"] > 0.0 and detail["removed_pixels"] > 0


@requires_font
def test_without_a_verso_there_is_no_verso_variant(page_and_verso):
    bled, _ = page_and_verso
    portfolio = build_portfolio(bled, dpi=300)
    assert "bleed_verso" not in portfolio.names


@requires_font
def test_the_service_keeps_the_candidate_that_registers_best(page_and_verso):
    bled, verso = page_and_verso
    noise = np.random.default_rng(3).integers(0, 255, bled.shape, dtype=np.uint8)
    service = OcrService([], OcrServiceConfig(use_verso=True, verso_self_mirror=False), lang="eng")
    task = PageTask(image=bled, dpi=300.0, lang="eng", verso_sources=lambda: [noise, verso])
    notes: list[str] = []
    chosen = service._verso_for(task, bled, detect_signals(bled, dpi=300), notes)
    assert chosen is verso
    assert any("verso real: página vizinha 2" in n for n in notes)


@requires_font
def test_a_candidate_below_the_correlation_floor_is_not_a_verso(page_and_verso):
    bled, verso = page_and_verso
    service = OcrService([], OcrServiceConfig(use_verso=True, verso_self_mirror=False,
                                              verso_min_correlation=0.99), lang="eng")
    task = PageTask(image=bled, dpi=300.0, lang="eng", verso_sources=lambda: [verso])
    notes: list[str] = []
    assert service._verso_for(task, bled, detect_signals(bled, dpi=300), notes) is None
    assert any("redução heurística" in n for n in notes)


@requires_font
def test_a_page_without_show_through_never_asks_for_the_neighbours(page_and_verso):
    _, clean = page_and_verso
    asked = []
    service = OcrService([], OcrServiceConfig(use_verso=True), lang="eng")
    task = PageTask(image=clean, dpi=300.0, lang="eng",
                    verso_sources=lambda: asked.append(1) or [])
    assert service._verso_for(task, clean, detect_signals(clean, dpi=300), []) is None
    assert asked == []


def test_sabotage_the_switch_leaves_the_heuristic_alone(page_and_verso):
    bled, verso = page_and_verso
    service = OcrService([], OcrServiceConfig(use_verso=False), lang="eng")
    task = PageTask(image=bled, dpi=300.0, lang="eng", verso_sources=lambda: [verso])
    assert service._verso_for(task, bled, detect_signals(bled, dpi=300), []) is None


def test_the_neighbours_of_a_pdf_page_are_rendered_on_demand(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for n in range(3):
        page = doc.new_page(width=200, height=200)
        page.insert_text((20, 100), f"page {n}", fontsize=20)
    service = OcrService([], OcrServiceConfig(), lang="eng")
    renders = service._neighbour_renders(doc[1], 72)()
    assert len(renders) == 2 and all(r.shape[:2] == (200, 200) for r in renders)
    assert len(service._neighbour_renders(doc[0], 72)()) == 1
    doc.close()
