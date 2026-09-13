"""Sol §SOL-3: the conditional preprocessing portfolio.

Pages are generated here with a known defect, so each test can assert not
only *that* a variant was built but *why* — the signal that justified it —
and that a clean page gets no variant at all.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from caissa.ocr.portfolio import (
    PortfolioConfig,
    VariantGeometry,
    build_portfolio,
    detect_signals,
)
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord

from .conftest import render_text_page, requires_font, rotate


@pytest.fixture(scope="module")
def clean_page() -> np.ndarray:
    # Body text at a real book size: 44 px is 10.5 pt at 300 DPI, an
    # x-height near 20 px.  The conftest default (30 px, 7 pt) is small
    # print, and the portfolio is right to want it upscaled.
    image, _ = render_text_page(font_size=44, wrap=44)
    return image


@requires_font
def test_a_clean_page_gets_only_the_original(clean_page):
    portfolio = build_portfolio(clean_page, dpi=300)
    assert portfolio.names == ("original",), portfolio.describe_pt()
    assert portfolio.original.is_original
    assert portfolio.original.geometry.is_identity
    assert abs(portfolio.signals.skew_deg) < 0.3
    assert portfolio.signals.shadow_spread < 25


@requires_font
def test_skew_justifies_a_deskew_variant_whose_boxes_map_back(clean_page):
    skewed = rotate(clean_page, -2.0)
    portfolio = build_portfolio(skewed, dpi=300)
    assert "deskew_shadow" in portfolio.names
    variant = next(v for v in portfolio.variants if v.name == "deskew_shadow")
    assert "deskew" in variant.applied_steps
    assert any("inclinação" in r for r in variant.reasons_pt)
    assert variant.geometry.affine is not None
    # A box at the centre of the deskewed page maps to the centre of the
    # original: rotation about the centre is its own fixed point.
    h, w = variant.image.shape[:2]
    centre = BBox(w / 2 - 5, h / 2 - 5, 10, 10)
    back = variant.geometry.to_original(centre)
    oh, ow = skewed.shape[:2]
    assert abs(back.cx - ow / 2) < 2.0
    assert abs(back.cy - oh / 2) < 2.0


@requires_font
def test_low_resolution_justifies_an_upscale_and_the_scale_is_undone(clean_page):
    small = cv2.resize(clean_page, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    portfolio = build_portfolio(small, dpi=150)
    assert "upscale" in portfolio.names
    variant = next(v for v in portfolio.variants if v.name == "upscale")
    assert variant.dpi == 300
    assert variant.geometry.scale == pytest.approx(2.0)
    word = OcrWord(text="x", box=BBox(100.0, 50.0, 40.0, 20.0), confidence=0.9)
    result = OcrResult(engine="t", lang="eng",
                       lines=(OcrLine(words=(word,), box=word.box, font_size=20.0),))
    mapped = variant.map_result(result)
    assert mapped.words[0].box == BBox(50.0, 25.0, 20.0, 10.0)
    assert mapped.lines[0].font_size == pytest.approx(10.0)
    assert mapped.meta["variant"] == "upscale"


@requires_font
def test_a_shadow_justifies_the_shadow_variant(clean_page):
    h, w = clean_page.shape
    gradient = np.linspace(1.0, 0.45, w, dtype=np.float32)[None, :]
    shaded = np.clip(clean_page.astype(np.float32) * gradient, 0, 255).astype(np.uint8)
    signals = detect_signals(shaded, dpi=300)
    assert signals.shadow_spread >= 25
    portfolio = build_portfolio(shaded, dpi=300, signals=signals)
    variant = next(v for v in portfolio.variants if v.name == "deskew_shadow")
    assert "shadow_removal" in variant.applied_steps
    assert detect_signals(variant.image, dpi=300).shadow_spread < signals.shadow_spread


@requires_font
def test_noise_justifies_the_binarised_variant(clean_page):
    rng = np.random.default_rng(1)
    noisy = np.clip(clean_page.astype(np.float32) + rng.normal(0, 14, clean_page.shape),
                    0, 255).astype(np.uint8)
    signals = detect_signals(noisy, dpi=300)
    assert signals.noise_sigma >= 6
    portfolio = build_portfolio(noisy, dpi=300, signals=signals)
    variant = next(v for v in portfolio.variants if v.name == "bleed_sauvola")
    assert "binarize" in variant.applied_steps
    assert len(np.unique(variant.image)) <= 2


@requires_font
def test_the_variant_cap_keeps_the_cheapest_reasons(clean_page):
    small = cv2.resize(rotate(clean_page, -2.0), None, fx=0.5, fy=0.5,
                       interpolation=cv2.INTER_AREA)
    rng = np.random.default_rng(2)
    noisy = np.clip(small.astype(np.float32) + rng.normal(0, 14, small.shape),
                    0, 255).astype(np.uint8)
    portfolio = build_portfolio(noisy, dpi=150, config=PortfolioConfig(max_variants=1))
    assert portfolio.names == ("original", "upscale")
    assert any("teto" in n for n in portfolio.notes)


def test_geometry_inverse_composes_scale_and_affine():
    matrix = cv2.getRotationMatrix2D((50.0, 50.0), 10.0, 1.0)
    affine = ((float(matrix[0, 0]), float(matrix[0, 1]), float(matrix[0, 2])),
              (float(matrix[1, 0]), float(matrix[1, 1]), float(matrix[1, 2])))
    geometry = VariantGeometry(scale=2.0, affine=affine, field=None)
    # Forward: original (10, 20) -> scaled (20, 40) -> rotated.
    px = matrix[0, 0] * 20 + matrix[0, 1] * 40 + matrix[0, 2]
    py = matrix[1, 0] * 20 + matrix[1, 1] * 40 + matrix[1, 2]
    x, y = geometry.point_to_original(px, py)
    assert x == pytest.approx(10.0, abs=1e-6)
    assert y == pytest.approx(20.0, abs=1e-6)
    field = VariantGeometry(field=tuple(3.0 for _ in range(100)))
    assert field.point_to_original(5.0, 10.0) == (5.0, 13.0)


def test_signals_on_a_binary_page_skip_the_grey_measures():
    page = np.where(np.random.default_rng(0).random((400, 400)) > 0.9, 0, 255).astype(np.uint8)
    signals = detect_signals(page, dpi=200)
    assert signals.is_binary
    assert signals.noise_sigma == 0.0
    assert signals.bleed_share == 0.0
