"""The coordinate spaces of a PDF page, as pure arithmetic.

A PyMuPDF page has two rectangles that both claim to be "the page":

``page.rect``
    What the user sees.  Rotation applied, CropBox applied, origin top-left.
    Every rectangle the product stores -- a selection, a diagram's ``rect_pdf``,
    a provenance rect -- lives here.
``text space``
    What ``get_text`` (every mode, including its ``clip=``), ``get_image_info``
    and ``get_drawings`` report.  CropBox applied, **rotation not applied**.

The two coincide on an unrotated page, which is 18.766 of the 18.767 pages of
the reference collection -- and that is exactly why a conversion bug survives
every test that does not build a rotated page on purpose.  Measured on
PyMuPDF 1.28.2 (``tests/unit/ingest/test_geometry.py``, four rotations, a
displaced CropBox and a MediaBox whose origin is not ``(0, 0)``):

    page_rect = text_rect * page.rotation_matrix
    text_rect = page_rect * page.derotation_matrix

with **no origin term**.  The Editor's section 48 formula
(``vision/detect/vector_detect.py`` carried a copy) adds the CropBox top-left
in write space; on a rotated page with a displaced CropBox that lands the box
100 pt away from the ink.  The test here is the proof, and it is the reason the
conversion lives in one module with the inverse next to it rather than being
re-derived by every reader of a page.

Why pure arithmetic instead of ``pymupdf.Matrix``: a :class:`PageFrame` is
captured once per page, is a plain frozen dataclass, and after that every
conversion -- points to pixels for a render, a diagram box back to points,
text space to the page -- runs without holding the document lock or even
having PyMuPDF imported.  The UI thread converts thousands of rectangles per
second while panning; the importer converts one per line; neither should touch
the document to do it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "IDENTITY",
    "Affine",
    "PageFrame",
    "RectT",
    "affine_apply",
    "affine_compose",
    "affine_invert",
    "affine_rect",
    "rotation_affine",
]

#: ``(x0, y0, x1, y1)`` in whatever space the docstring names.
RectT = tuple[float, float, float, float]

#: ``(a, b, c, d, e, f)`` in the PDF convention: ``x' = a*x + c*y + e``,
#: ``y' = b*x + d*y + f``.  Same layout as ``pymupdf.Matrix``.
Affine = tuple[float, float, float, float, float, float]

IDENTITY: Final[Affine] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_POINTS_PER_INCH: Final = 72.0
_FULL_TURN: Final = 360
_RIGHT_ANGLE: Final = 90
_SINGULAR: Final = 1e-12
#: Slack subtracted before the ceiling so ``612 * 300/72 = 2550.0`` stays 2550
#: instead of becoming 2551 through floating-point noise.
_CEIL_SLACK: Final = 1e-6


def affine_apply(m: Affine, x: float, y: float) -> tuple[float, float]:
    """Map one point through ``m``."""
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def affine_compose(first: Affine, then: Affine) -> Affine:
    """The matrix that applies ``first`` and then ``then``.

    Row-vector convention, so ``p * first * then`` -- the same order PyMuPDF
    uses for ``Rect * Matrix * Matrix``.
    """
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = then
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def affine_invert(m: Affine) -> Affine:
    """The inverse of ``m``.

    Raises:
        ValueError: when ``m`` is singular, which no page matrix ever is; the
            check exists so a corrupt matrix fails loudly instead of producing
            ``inf`` coordinates that a later clamp hides.
    """
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < _SINGULAR:
        raise ValueError("matriz singular: não pode ser invertida")
    ia = d / det
    ib = -b / det
    ic = -c / det
    id_ = a / det
    ie = -(e * ia + f * ic)
    if_ = -(e * ib + f * id_)
    return (ia, ib, ic, id_, ie, if_)


def affine_rect(m: Affine, rect: RectT) -> RectT:
    """Map a rectangle through ``m`` and re-normalise its corners.

    A rotation swaps which corner is top-left, so the result is the bounding
    box of the four mapped corners -- which for the axis-aligned matrices a
    page ever has is exact, not an over-approximation.
    """
    x0, y0, x1, y1 = rect
    corners = (
        affine_apply(m, x0, y0),
        affine_apply(m, x1, y0),
        affine_apply(m, x0, y1),
        affine_apply(m, x1, y1),
    )
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def rotation_affine(rotation: int, width: float, height: float) -> Affine:
    """The matrix PyMuPDF reports as ``page.rotation_matrix``.

    ``width`` and ``height`` are the **unrotated** page size (text space).
    Rotation is clockwise and the origin stays top-left, so a 90-degree turn
    maps ``(x, y)`` to ``(height - y, x)``.

    Written out rather than taken from PyMuPDF so a :class:`PageFrame` can be
    built in a test from four numbers, and so the test can check this against
    the library's own matrix -- both directions of trust.
    """
    rotation = rotation % _FULL_TURN
    if rotation == 0:
        return IDENTITY
    if rotation == _RIGHT_ANGLE:
        return (0.0, 1.0, -1.0, 0.0, height, 0.0)
    if rotation == 2 * _RIGHT_ANGLE:
        return (-1.0, 0.0, 0.0, -1.0, width, height)
    if rotation == 3 * _RIGHT_ANGLE:
        return (0.0, -1.0, 1.0, 0.0, 0.0, width)
    raise ValueError(f"rotação de página inválida: {rotation} (esperado múltiplo de 90)")


@dataclass(frozen=True, slots=True)
class PageFrame:
    """Everything needed to convert between a page's spaces, captured once.

    Attributes:
        index: Zero-based page number.
        width: ``page.rect.width`` -- the visible, rotated width in points.
        height: ``page.rect.height``.
        rotation: ``/Rotate`` of the page, normalised to ``0/90/180/270``.
        text_width: Width of the unrotated page (text space).
        text_height: Height of the unrotated page.
        to_page: Text space to ``page.rect`` space (``page.rotation_matrix``).
        to_text: The inverse (``page.derotation_matrix``).
    """

    index: int
    width: float
    height: float
    rotation: int = 0
    text_width: float = 0.0
    text_height: float = 0.0
    to_page: Affine = IDENTITY
    to_text: Affine = IDENTITY

    @classmethod
    def from_page(cls, page: Any, index: int | None = None) -> PageFrame:
        """Capture the frame of a live PyMuPDF page."""
        rect = page.rect
        rotation = int(page.rotation) % _FULL_TURN
        rm = page.rotation_matrix
        dm = page.derotation_matrix
        to_page: Affine = (
            float(rm.a),
            float(rm.b),
            float(rm.c),
            float(rm.d),
            float(rm.e),
            float(rm.f),
        )
        to_text: Affine = (
            float(dm.a),
            float(dm.b),
            float(dm.c),
            float(dm.d),
            float(dm.e),
            float(dm.f),
        )
        swapped = rotation in (_RIGHT_ANGLE, 3 * _RIGHT_ANGLE)
        width = float(rect.width)
        height = float(rect.height)
        return cls(
            index=int(page.number if index is None else index),
            width=width,
            height=height,
            rotation=rotation,
            text_width=height if swapped else width,
            text_height=width if swapped else height,
            to_page=to_page,
            to_text=to_text,
        )

    @classmethod
    def synthetic(cls, index: int, width: float, height: float, rotation: int = 0) -> PageFrame:
        """A frame built from numbers alone, for tests and for headless callers.

        ``width`` and ``height`` are the unrotated size; the visible size is
        derived, the same way PyMuPDF derives ``page.rect``.
        """
        rotation = rotation % _FULL_TURN
        to_page = rotation_affine(rotation, width, height)
        swapped = rotation in (_RIGHT_ANGLE, 3 * _RIGHT_ANGLE)
        return cls(
            index=index,
            width=height if swapped else width,
            height=width if swapped else height,
            rotation=rotation,
            text_width=width,
            text_height=height,
            to_page=to_page,
            to_text=affine_invert(to_page),
        )

    # -- page space <-> text space ----------------------------------------- #

    @property
    def rect(self) -> RectT:
        """The visible page as ``(0, 0, width, height)``."""
        return (0.0, 0.0, self.width, self.height)

    @property
    def is_rotated(self) -> bool:
        return self.rotation != 0

    @property
    def area(self) -> float:
        return self.width * self.height

    def text_to_page(self, rect: RectT) -> RectT:
        """A ``get_text`` / ``get_image_info`` box in ``page.rect`` space."""
        if not self.is_rotated:
            return rect
        return affine_rect(self.to_page, rect)

    def page_to_text(self, rect: RectT) -> RectT:
        """A ``page.rect`` box as the ``clip=`` a text extraction wants."""
        if not self.is_rotated:
            return rect
        return affine_rect(self.to_text, rect)

    def text_point_to_page(self, x: float, y: float) -> tuple[float, float]:
        if not self.is_rotated:
            return (x, y)
        return affine_apply(self.to_page, x, y)

    # -- points <-> pixels -------------------------------------------------- #

    @staticmethod
    def scale_for(dpi: float) -> float:
        """Pixels per point at ``dpi``."""
        return dpi / _POINTS_PER_INCH

    def pixel_size(self, dpi: float) -> tuple[int, int]:
        """``(width_px, height_px)`` of a full-page render at ``dpi``.

        Rounded the way MuPDF rounds a pixmap: ceiling of the scaled rect, so
        an image the renderer produces and a box converted by this frame agree
        to the pixel.
        """
        s = self.scale_for(dpi)
        return (
            int(math.ceil(self.width * s - _CEIL_SLACK)),
            int(math.ceil(self.height * s - _CEIL_SLACK)),
        )

    def page_to_pixels(
        self, rect: RectT, dpi: float, *, origin: tuple[float, float] = (0.0, 0.0)
    ) -> RectT:
        """A ``page.rect`` box in the pixel space of a render at ``dpi``.

        ``origin`` is the top-left of the rendered clip in points, for a render
        that covered only part of the page.
        """
        s = self.scale_for(dpi)
        x0, y0, x1, y1 = rect
        ox, oy = origin
        return ((x0 - ox) * s, (y0 - oy) * s, (x1 - ox) * s, (y1 - oy) * s)

    def pixels_to_page(
        self, rect: RectT, dpi: float, *, origin: tuple[float, float] = (0.0, 0.0)
    ) -> RectT:
        """The exact inverse of :meth:`page_to_pixels`."""
        s = self.scale_for(dpi)
        x0, y0, x1, y1 = rect
        ox, oy = origin
        return (x0 / s + ox, y0 / s + oy, x1 / s + ox, y1 / s + oy)

    def clamp(self, rect: RectT) -> RectT:
        """``rect`` intersected with the visible page; empty boxes collapse."""
        x0, y0, x1, y1 = rect
        cx0 = min(max(x0, 0.0), self.width)
        cy0 = min(max(y0, 0.0), self.height)
        cx1 = min(max(x1, 0.0), self.width)
        cy1 = min(max(y1, 0.0), self.height)
        cx1 = max(cx1, cx0)
        cy1 = max(cy1, cy0)
        return (cx0, cy0, cx1, cy1)
