"""Rendering and the byte-budgeted cache."""

from __future__ import annotations

import threading

import numpy as np
import pytest

from caissa.ingest.pdf.document import open_pdf
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.render import PageRenderer, RenderCache, RenderedPage

from .conftest import PageSpec, requires_pymupdf

pytestmark = requires_pymupdf


def _fake(page_index: int, nbytes: int) -> RenderedPage:
    side = max(1, int(nbytes**0.5))
    image = np.zeros((side, nbytes // side or 1), dtype=np.uint8)
    return RenderedPage(
        page_index, 72.0, image, (0, 0, 1, 1), "gray", PageFrame.synthetic(page_index, 1, 1)
    )


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


def test_cache_accounts_bytes_and_evicts_least_recently_used():
    cache = RenderCache(budget_bytes=1000)
    for i in range(3):
        assert cache.put((1, i, 72.0, None, "gray"), _fake(i, 400))
    # 1200 bytes asked, 1000 allowed: the first entry went.
    assert cache.bytes_used <= 1000
    assert cache.get((1, 0, 72.0, None, "gray")) is None
    assert cache.get((1, 2, 72.0, None, "gray")) is not None
    assert cache.stats.evictions == 1
    # Touching page 1 makes page 2 the eviction candidate.
    cache.get((1, 1, 72.0, None, "gray"))
    cache.put((1, 3, 72.0, None, "gray"), _fake(3, 400))
    assert cache.get((1, 2, 72.0, None, "gray")) is None
    assert cache.get((1, 1, 72.0, None, "gray")) is not None


def test_an_entry_larger_than_the_budget_is_returned_but_not_stored():
    cache = RenderCache(budget_bytes=500)
    assert cache.put((1, 0, 72.0, None, "gray"), _fake(0, 400))
    assert not cache.put((1, 1, 72.0, None, "gray"), _fake(1, 2000))
    assert cache.stats.oversize == 1
    assert cache.get((1, 0, 72.0, None, "gray")) is not None, "o pequeno sobreviveu"


def test_replacing_a_key_does_not_double_count():
    cache = RenderCache(budget_bytes=1000)
    cache.put((1, 0, 72.0, None, "gray"), _fake(0, 400))
    cache.put((1, 0, 72.0, None, "gray"), _fake(0, 300))
    assert cache.bytes_used == cache.get((1, 0, 72.0, None, "gray")).nbytes
    assert len(cache) == 1


def test_clear_by_document():
    cache = RenderCache(budget_bytes=10_000)
    cache.put((1, 0, 72.0, None, "gray"), _fake(0, 100))
    cache.put((2, 0, 72.0, None, "gray"), _fake(0, 100))
    cache.clear(document=1)
    assert len(cache) == 1
    assert cache.bytes_used == cache.get((2, 0, 72.0, None, "gray")).nbytes
    cache.clear()
    assert len(cache) == 0
    assert cache.bytes_used == 0


def test_cache_is_thread_safe():
    cache = RenderCache(budget_bytes=50_000)
    errors: list[BaseException] = []

    def worker(seed: int) -> None:
        try:
            for i in range(200):
                key = (seed, i % 17, 72.0, None, "gray")
                if cache.get(key) is None:
                    cache.put(key, _fake(i, 900))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert cache.bytes_used <= cache.budget_bytes
    assert cache.bytes_used == sum(v.nbytes for v in cache._entries.values())


def test_negative_budget_is_refused():
    with pytest.raises(ValueError, match="orçamento"):
        RenderCache(budget_bytes=-1)


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #


def test_render_produces_an_owned_rgb_array_at_the_frame_size(pdf_file):
    path = pdf_file([PageSpec(size=(300.0, 200.0), rects=[(50, 50, 100, 100)])])
    with open_pdf(path) as doc:
        renderer = PageRenderer(doc, RenderCache(10_000_000))
        rendered = renderer.render(0, dpi=144)
        assert rendered.image.shape == (400, 600, 3)
        assert rendered.image.flags.owndata
        assert rendered.image.flags.writeable
        # The black square drawn at (50..100) pt lands at (100..200) px.
        ink = rendered.image[:, :, 0] < 128
        ys, xs = np.where(ink)
        assert (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) == (100, 100, 200, 200)
        assert rendered.to_pixels((50.0, 50.0, 100.0, 100.0)) == pytest.approx((100, 100, 200, 200))
        assert rendered.to_points((100.0, 100.0, 200.0, 200.0)) == pytest.approx((50, 50, 100, 100))


def test_render_is_cached_and_gray_is_a_different_entry(pdf_file):
    path = pdf_file([PageSpec(size=(300.0, 200.0)).text("x", 72, 100)])
    with open_pdf(path) as doc:
        renderer = PageRenderer(doc, RenderCache(10_000_000))
        first = renderer.render(0, dpi=72)
        assert renderer.render(0, dpi=72) is first
        gray = renderer.render(0, dpi=72, colorspace="gray")
        assert gray.image.ndim == 2
        assert renderer.cache.stats.hits == 1
        assert renderer.cache.stats.misses == 2


def test_render_clip_maps_pixels_back_to_page_points(pdf_file):
    path = pdf_file([PageSpec(size=(300.0, 200.0), rects=[(50, 50, 100, 100)])])
    with open_pdf(path) as doc:
        renderer = PageRenderer(doc, RenderCache(10_000_000))
        rendered = renderer.render(0, dpi=72, clip=(40.0, 40.0, 140.0, 140.0))
        assert rendered.image.shape[:2] == (100, 100)
        ys, xs = np.where(rendered.image[:, :, 0] < 128)
        assert (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) == (10, 10, 60, 60)
        assert rendered.to_points((10.0, 10.0, 60.0, 60.0)) == pytest.approx((50, 50, 100, 100))


def test_render_refuses_nonsense(pdf_file):
    path = pdf_file([PageSpec(size=(300.0, 200.0)).text("x", 72, 100)])
    with open_pdf(path) as doc:
        renderer = PageRenderer(doc, RenderCache(10_000_000))
        with pytest.raises(ValueError, match="resolução"):
            renderer.render(0, dpi=0)
        with pytest.raises(ValueError, match="região vazia"):
            renderer.render(0, dpi=72, clip=(500.0, 500.0, 600.0, 600.0))
        with pytest.raises(IndexError, match="fora do intervalo"):
            renderer.render(7, dpi=72)


def test_thumbnail_fits_the_longer_side(pdf_file):
    path = pdf_file([PageSpec(size=(300.0, 600.0)).text("x", 72, 100)])
    with open_pdf(path) as doc:
        thumb = PageRenderer(doc, RenderCache(10_000_000)).thumbnail(0, max_side_px=150)
        assert max(thumb.image.shape[:2]) == 150


def test_rotated_page_renders_rotated(pdf_file):
    path = pdf_file([PageSpec(size=(300.0, 200.0), rotation=90).text("x", 72, 100)])
    with open_pdf(path) as doc:
        rendered = PageRenderer(doc, RenderCache(10_000_000)).render(0, dpi=72)
        assert rendered.image.shape[:2] == (300, 200)
