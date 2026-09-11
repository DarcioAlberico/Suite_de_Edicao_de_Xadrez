"""Page rendering with a byte-budgeted LRU cache.

Three sources converge here.  The trunk's ``pdf_io.render_pdf_page`` renders a
page to an owned RGB array (the vision front's input, measured recall
0,9913 with ``alpha=False``); the Editor's ``pdf_service`` keeps a small LRU of
rendered assets behind a lock because "the export runs on a worker while the
live preview keeps rendering on the UI thread"; and the F0 configuration
already declares ``cache.page_cache_mb = 2048`` with nothing honouring it.

Two decisions carry the weight:

**The cache is budgeted in bytes, not in entries.**  A 300 DPI render of a
Letter page is 22 MB; a thumbnail at 36 DPI is 300 KB.  An entry-count LRU
either starves the reader (48 thumbnails = 14 MB, a fraction of what is
allowed) or blows the budget (48 full pages = 1 GB).  Accounting in bytes
makes ``page_cache_mb`` mean what it says, and makes the F2 memory gate
("no linear growth over a full scan") a property of the cache rather than a
hope: whatever the scan does, the cache holds at most the budget.

**An entry larger than the whole budget is returned but never stored.**
Storing it would evict everything else for one page that will be evicted
itself on the next request.  The reader asking for a 600 DPI render of an A3
plate gets its pixels; the thumbnails stay.

The renderer takes the document lock around ``get_pixmap`` and copies the
pixmap's buffer into an owned ``numpy`` array before releasing it --
``np.frombuffer`` over ``pix.samples`` is a read-only view whose lifetime is
the pixmap's, and handing that out is a use-after-free waiting for a garbage
collection.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

import numpy as np
from numpy.typing import NDArray

from caissa.ingest.pdf.geometry import PageFrame, RectT

if TYPE_CHECKING:
    from caissa.ingest.pdf.document import PdfDocument

__all__ = [
    "DEFAULT_CACHE_BUDGET_BYTES",
    "CacheStats",
    "Colorspace",
    "PageRenderer",
    "RenderCache",
    "RenderedPage",
]

Colorspace = Literal["rgb", "gray"]

_MB: Final = 1024 * 1024
#: The F0 configuration default (``CacheConfig.page_cache_mb``), repeated here
#: so the renderer works without a loaded configuration -- the doctor and the
#: tests run it in a half-broken environment on purpose.
DEFAULT_CACHE_BUDGET_BYTES: Final = 2048 * _MB
_MIN_DPI: Final = 1.0
_MAX_DPI: Final = 2400.0
_MIN_CLIP_SIDE_PT: Final = 0.5
_RGB_CHANNELS: Final = 3
_RGBA_CHANNELS: Final = 4


@dataclass(frozen=True, slots=True)
class RenderedPage:
    """One render: pixels plus everything needed to map them back to points.

    Attributes:
        page_index: Zero-based page number.
        dpi: Resolution the render was made at.
        image: ``(H, W, 3)`` RGB or ``(H, W)`` grey ``uint8`` array, owned.
        clip: The ``page.rect`` region rendered; the full page when ``None``
            was requested.
        colorspace: ``"rgb"`` or ``"gray"``.
        frame: The page's coordinate frame, for conversions.
    """

    page_index: int
    dpi: float
    image: NDArray[np.uint8]
    clip: RectT
    colorspace: Colorspace
    frame: PageFrame

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def nbytes(self) -> int:
        return int(self.image.nbytes)

    @property
    def scale(self) -> float:
        """Pixels per point."""
        return self.frame.scale_for(self.dpi)

    @property
    def origin(self) -> tuple[float, float]:
        """Top-left of the rendered clip, in points."""
        return (self.clip[0], self.clip[1])

    def to_pixels(self, rect: RectT) -> RectT:
        """A ``page.rect`` box in this image's pixel space."""
        return self.frame.page_to_pixels(rect, self.dpi, origin=self.origin)

    def to_points(self, rect: RectT) -> RectT:
        """A box in this image's pixel space back to ``page.rect`` points."""
        return self.frame.pixels_to_page(rect, self.dpi, origin=self.origin)


@dataclass(slots=True)
class CacheStats:
    """Counters a test or a status bar can read."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    oversize: int = 0
    bytes_used: int = 0
    entries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


_CacheKey = tuple[int, int, float, RectT | None, str]


class RenderCache:
    """LRU of :class:`RenderedPage` bounded by a byte budget.  Thread-safe."""

    def __init__(self, budget_bytes: int = DEFAULT_CACHE_BUDGET_BYTES) -> None:
        if budget_bytes < 0:
            raise ValueError("o orçamento do cache não pode ser negativo")
        self._budget = int(budget_bytes)
        self._entries: OrderedDict[_CacheKey, RenderedPage] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()
        self.stats = CacheStats()

    @property
    def budget_bytes(self) -> int:
        return self._budget

    @property
    def bytes_used(self) -> int:
        return self._bytes

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: _CacheKey) -> RenderedPage | None:
        with self._lock:
            hit = self._entries.get(key)
            if hit is None:
                self.stats.misses += 1
                return None
            self._entries.move_to_end(key)
            self.stats.hits += 1
            return hit

    def put(self, key: _CacheKey, value: RenderedPage) -> bool:
        """Store ``value``; returns ``False`` when it exceeds the whole budget."""
        size = value.nbytes
        with self._lock:
            if size > self._budget:
                self.stats.oversize += 1
                return False
            old = self._entries.pop(key, None)
            if old is not None:
                self._bytes -= old.nbytes
            self._entries[key] = value
            self._bytes += size
            while self._bytes > self._budget and self._entries:
                _, evicted = self._entries.popitem(last=False)
                self._bytes -= evicted.nbytes
                self.stats.evictions += 1
            self.stats.bytes_used = self._bytes
            self.stats.entries = len(self._entries)
            return True

    def clear(self, *, document: int | None = None) -> None:
        """Drop everything, or everything belonging to one document id."""
        with self._lock:
            if document is None:
                self._entries.clear()
                self._bytes = 0
            else:
                for key in [k for k in self._entries if k[0] == document]:
                    self._bytes -= self._entries.pop(key).nbytes
            self.stats.bytes_used = self._bytes
            self.stats.entries = len(self._entries)


def _pixmap_to_array(pix: Any) -> NDArray[np.uint8]:
    """Copy a pixmap into an owned array, dropping any alpha channel."""
    n = int(pix.n)
    height, width = int(pix.height), int(pix.width)
    view = np.frombuffer(pix.samples, dtype=np.uint8)
    if n == 1:
        return view.reshape(height, width).copy()
    array = view.reshape(height, width, n)
    if n == _RGBA_CHANNELS:
        return np.ascontiguousarray(array[:, :, :_RGB_CHANNELS])
    if n == _RGB_CHANNELS:
        return array.copy()
    # CMYK or an exotic space: MuPDF can convert for us.
    raise ValueError(f"pixmap com {n} canais não é suportado")


class PageRenderer:
    """Renders pages of one :class:`PdfDocument` through a shared cache."""

    def __init__(self, document: PdfDocument, cache: RenderCache | None = None) -> None:
        self.document = document
        self.cache = cache if cache is not None else RenderCache()
        self._doc_key = id(document)

    def render(
        self,
        page_index: int,
        *,
        dpi: float = 200.0,
        clip: RectT | None = None,
        colorspace: Colorspace = "rgb",
        annotations: bool = True,
    ) -> RenderedPage:
        """Render ``page_index`` (or a ``clip`` of it, in ``page.rect`` points).

        Raises:
            IndexError: page out of range (message in Portuguese).
            ValueError: absurd DPI or an empty clip.
        """
        if not _MIN_DPI <= dpi <= _MAX_DPI:
            raise ValueError(f"resolução inválida: {dpi} DPI (esperado entre 1 e 2400)")
        frame = self.document.frame(page_index)
        region = frame.rect if clip is None else frame.clamp(clip)
        if region[2] - region[0] < _MIN_CLIP_SIDE_PT or region[3] - region[1] < _MIN_CLIP_SIDE_PT:
            raise ValueError("região vazia para renderizar")
        key: _CacheKey = (
            self._doc_key,
            page_index,
            float(dpi),
            None if clip is None else region,
            colorspace + ("" if annotations else "-noannot"),
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        rendered = self._render(
            page_index, frame, dpi, region, clip is None, colorspace, annotations
        )
        self.cache.put(key, rendered)
        return rendered

    def _render(
        self,
        page_index: int,
        frame: PageFrame,
        dpi: float,
        region: RectT,
        full_page: bool,
        colorspace: Colorspace,
        annotations: bool,
    ) -> RenderedPage:
        import pymupdf

        scale = frame.scale_for(dpi)
        matrix = pymupdf.Matrix(scale, scale)
        cs = pymupdf.csGRAY if colorspace == "gray" else pymupdf.csRGB
        with self.document.locked() as doc:
            page = doc[page_index]
            clip_rect = None if full_page else pymupdf.Rect(*region)
            # alpha=False: MuPDF fills the pixmap white before drawing, which
            # is the composition the detection recall was measured with.
            pix = page.get_pixmap(
                matrix=matrix, colorspace=cs, alpha=False, clip=clip_rect, annots=annotations
            )
            image = _pixmap_to_array(pix)
            del pix
            del page
        return RenderedPage(
            page_index=page_index,
            dpi=float(dpi),
            image=image,
            clip=region,
            colorspace=colorspace,
            frame=frame,
        )

    def thumbnail(self, page_index: int, *, max_side_px: int = 256) -> RenderedPage:
        """A render whose longer side is at most ``max_side_px``."""
        frame = self.document.frame(page_index)
        longest = max(frame.width, frame.height) or 1.0
        dpi = max(_MIN_DPI, 72.0 * max_side_px / longest)
        return self.render(page_index, dpi=dpi)

    def invalidate(self) -> None:
        """Forget every render of this document (after an edit, for example)."""
        self.cache.clear(document=self._doc_key)
