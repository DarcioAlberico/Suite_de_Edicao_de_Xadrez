"""Negative controls — images that contain no text, by construction.

Sol §SOL-2 asks the pipeline to *abstain* on a blank page, an empty board,
a stained margin, a torn border, pure noise and a photograph without
writing.  These generators produce those images deterministically (a seed,
not a clock), so the same control is measured on every run and a unit test
can assert that Tesseract's ``rs`` on a white page never reaches the IR.

Only :mod:`numpy` is used: the controls must be available to the unit tests,
which run without OpenCV.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from .golden import ControlKind

__all__ = ["CONTROL_GENERATORS", "control_image"]

Image = NDArray[np.uint8]


def _blank(h: int, w: int, rng: np.random.Generator) -> Image:
    paper = int(rng.integers(240, 256))
    return np.full((h, w), paper, dtype=np.uint8)


def _board(h: int, w: int, rng: np.random.Generator) -> Image:
    """An empty 8×8 board with a rule around it, centred, no coordinates."""
    image = _blank(h, w, rng)
    side = int(min(h, w) * 0.7)
    square = side // 8
    side = square * 8
    y0 = (h - side) // 2
    x0 = (w - side) // 2
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 1:
                image[y0 + r * square:y0 + (r + 1) * square,
                      x0 + c * square:x0 + (c + 1) * square] = 150
    thickness = max(2, square // 16)
    image[y0 - thickness:y0, x0 - thickness:x0 + side + thickness] = 0
    image[y0 + side:y0 + side + thickness, x0 - thickness:x0 + side + thickness] = 0
    image[y0 - thickness:y0 + side + thickness, x0 - thickness:x0] = 0
    image[y0 - thickness:y0 + side + thickness, x0 + side:x0 + side + thickness] = 0
    return image


def _stains(h: int, w: int, rng: np.random.Generator) -> Image:
    """Soft brown blotches on paper, the way damp does it."""
    image = _blank(h, w, rng).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(int(rng.integers(3, 7))):
        cy, cx = rng.uniform(0, h), rng.uniform(0, w)
        ry, rx = rng.uniform(h * 0.05, h * 0.25), rng.uniform(w * 0.05, w * 0.25)
        depth = rng.uniform(40, 110)
        blob = np.exp(-(((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2))
        image -= depth * blob
    return np.clip(image, 0, 255).astype(np.uint8)


def _border(h: int, w: int, rng: np.random.Generator) -> Image:
    """A dark scanner border with a ragged inner edge and nothing inside."""
    image = _blank(h, w, rng)
    top = int(rng.integers(h // 20, h // 8))
    left = int(rng.integers(w // 20, w // 8))
    image[:top, :] = 20
    image[:, :left] = 20
    image[h - top // 2:, :] = 30
    for y in range(top, h - top // 2):
        wobble = int(rng.integers(0, max(1, left // 3)))
        image[y, left:left + wobble] = 20
    return image


def _noise(h: int, w: int, rng: np.random.Generator) -> Image:
    return rng.integers(0, 256, size=(h, w), dtype=np.uint8)


def _photo(h: int, w: int, rng: np.random.Generator) -> Image:
    """A smooth vignette with a couple of soft shapes — a photo of nothing."""
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h * rng.uniform(0.3, 0.7), w * rng.uniform(0.3, 0.7)
    radial = np.sqrt(((yy - cy) / h) ** 2 + ((xx - cx) / w) ** 2)
    image = 200 - 120 * radial
    for _ in range(3):
        oy, ox = rng.uniform(0, h), rng.uniform(0, w)
        r = rng.uniform(min(h, w) * 0.1, min(h, w) * 0.3)
        image += 40 * np.exp(-(((yy - oy) ** 2 + (xx - ox) ** 2) / (2 * r * r)))
    image += rng.normal(0, 3, size=(h, w))
    return np.clip(image, 0, 255).astype(np.uint8)


CONTROL_GENERATORS: dict[ControlKind, Callable[[int, int, np.random.Generator], Image]] = {
    ControlKind.BLANK: _blank,
    ControlKind.BOARD: _board,
    ControlKind.STAINS: _stains,
    ControlKind.BORDER: _border,
    ControlKind.NOISE: _noise,
    ControlKind.PHOTO: _photo,
}


def control_image(kind: ControlKind, *, height: int = 1100, width: int = 850,
                  seed: int = 0) -> Image:
    """A deterministic control image of the given kind and size."""
    rng = np.random.default_rng(seed)
    return CONTROL_GENERATORS[kind](height, width, rng)
