"""Rendering of golden-manifest items for ``bench_sol.py`` (Sol §SOL-0).

Turns a :class:`caissa.ocr.golden.GoldenItem` plus a stratum name into the
grayscale image the system under test is given, with the effective DPI and
the pixel boxes of the labelled regions when the layout is synthetic.

Everything is deterministic: the seed is derived from the item id and the
stratum, so the same item degrades the same way on every run.  No image is
written anywhere; the corpus PDFs are copyrighted (docs/quality/CORPUS.md).
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.ocr.controls import control_image  # noqa: E402
from caissa.ocr.golden import DEGRADATIONS, Degradation, GoldenItem, Source  # noqa: E402

PDF_DIR = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF")
FONTS_DIR = Path(r"C:\Windows\Fonts")
RENDER_DPI = 300
POINT_SIZE = 10.5
COLUMN_INCHES = 3.9
MARGIN_PX = 40
LANG_TESS = {"en": "eng", "pt": "por", "de": "deu", "ru": "rus", "es": "spa",
             "mixed": "por+eng", "": "por+eng"}


@dataclass
class Rendered:
    """What the system under test receives for one (item, stratum)."""

    gray: np.ndarray
    dpi: int
    stratum: str
    #: Pixel boxes of the labelled regions, in reading order, when known.
    region_boxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def megapixels(self) -> float:
        h, w = self.gray.shape[:2]
        return h * w / 1e6


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #

_PDF_CACHE: dict[str, Any] = {}


def _open_pdf(book: str) -> Any | None:
    import fitz

    if book in _PDF_CACHE:
        return _PDF_CACHE[book]
    path = next((p for p in sorted(PDF_DIR.glob("*.pdf")) if p.stem[:50] == book[:50]), None)
    doc = fitz.open(path) if path is not None else None
    _PDF_CACHE[book] = doc
    return doc


def render_pdf(item: GoldenItem) -> np.ndarray | None:
    import fitz

    doc = _open_pdf(item.book)
    if doc is None or item.clip is None:
        return None
    page = doc[item.page_index]
    pix = page.get_pixmap(clip=fitz.Rect(*item.clip), dpi=RENDER_DPI,
                          colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS_DIR / name), size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if font.getlength(candidate) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _typeset_block(text: str, font: ImageFont.FreeTypeFont, width: int
                   ) -> tuple[Image.Image, int]:
    lines = _wrap(text, font, width)
    leading = int(font.size * 1.25)
    canvas = Image.new("L", (width, leading * len(lines) + leading // 2), 255)
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        draw.text((0, index * leading), line, font=font, fill=0)
    return canvas, leading


def render_synth(item: GoldenItem) -> tuple[np.ndarray, list[tuple[float, float, float, float]]]:
    """Typeset the item's regions in the layout its facets declare."""
    size = round(POINT_SIZE * RENDER_DPI / 72)
    font = _font(item.synth_font or "times.ttf", size)
    column = int(COLUMN_INCHES * RENDER_DPI)
    regions = sorted(item.regions, key=lambda r: r.reading_order)
    boxes: list[tuple[float, float, float, float]] = []

    if item.layout == "two-column":
        gutter = int(0.3 * RENDER_DPI)
        blocks = [_typeset_block(r.truth, font, column)[0] for r in regions]
        height = max(b.height for b in blocks) + 2 * MARGIN_PX
        page = Image.new("L", (2 * column + gutter + 2 * MARGIN_PX, height), 255)
        x = MARGIN_PX
        for block in blocks:
            page.paste(block, (x, MARGIN_PX))
            boxes.append((x, MARGIN_PX, x + block.width, MARGIN_PX + block.height))
            x += column + gutter
        return np.asarray(page, dtype=np.uint8), boxes

    if item.layout == "table":
        rows = regions[0].truth.split("\n")
        cells = [row.split("  ") for row in rows]
        widths = [max(int(font.getlength(c[k])) for c in cells) + 30
                  for k in range(max(len(c) for c in cells))]
        leading = int(size * 1.6)
        page = Image.new("L", (sum(widths) + 2 * MARGIN_PX, leading * len(rows) + 2 * MARGIN_PX),
                         255)
        draw = ImageDraw.Draw(page)
        for r, row in enumerate(cells):
            x = MARGIN_PX
            y = MARGIN_PX + r * leading
            for k, cell in enumerate(row):
                draw.text((x, y), cell, font=font, fill=0)
                x += widths[k]
            draw.line([(MARGIN_PX, y + leading - 4), (page.width - MARGIN_PX, y + leading - 4)],
                      fill=120, width=1)
        boxes.append((MARGIN_PX, MARGIN_PX, page.width - MARGIN_PX, page.height - MARGIN_PX))
        return np.asarray(page, dtype=np.uint8), boxes

    if item.layout == "problems":
        board_side = int(2.2 * RENDER_DPI)
        label_block, _ = _typeset_block(regions[0].truth, font, column)
        solution_block, _ = _typeset_block(regions[1].truth, font, column)
        height = MARGIN_PX * 4 + label_block.height + board_side + solution_block.height
        page = Image.new("L", (column + 2 * MARGIN_PX, height), 255)
        page.paste(label_block, (MARGIN_PX, MARGIN_PX))
        boxes.append((MARGIN_PX, MARGIN_PX, MARGIN_PX + label_block.width,
                      MARGIN_PX + label_block.height))
        by = MARGIN_PX * 2 + label_block.height
        bx = MARGIN_PX + (column - board_side) // 2
        square = board_side // 8
        draw = ImageDraw.Draw(page)
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    draw.rectangle([bx + c * square, by + r * square,
                                    bx + (c + 1) * square - 1, by + (r + 1) * square - 1],
                                   fill=150)
        draw.rectangle([bx - 3, by - 3, bx + 8 * square + 2, by + 8 * square + 2],
                       outline=0, width=3)
        sy = by + board_side + MARGIN_PX
        page.paste(solution_block, (MARGIN_PX, sy))
        boxes.append((MARGIN_PX, sy, MARGIN_PX + solution_block.width,
                      sy + solution_block.height))
        return np.asarray(page, dtype=np.uint8), boxes

    block, _ = _typeset_block(regions[0].truth, font, column)
    page = Image.new("L", (column + 2 * MARGIN_PX, block.height + 2 * MARGIN_PX), 255)
    page.paste(block, (MARGIN_PX, MARGIN_PX))
    boxes.append((MARGIN_PX, MARGIN_PX, MARGIN_PX + block.width, MARGIN_PX + block.height))
    return np.asarray(page, dtype=np.uint8), boxes


# --------------------------------------------------------------------------- #
# Degradation
# --------------------------------------------------------------------------- #


def _seed(item_id: str, stratum: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{item_id}|{stratum}".encode()).digest()[:4], "big")


def degrade(gray: np.ndarray, spec: Degradation, rng: np.random.Generator) -> np.ndarray:
    """Turn a 300-dpi render into a scan of the stratum's quality."""
    out = gray
    h, w = out.shape
    if spec.bleed:
        # The verso shows through: a mirrored, faded copy of the page itself.
        verso = cv2.flip(out, 1)
        verso = cv2.GaussianBlur(verso, (0, 0), 1.2)
        show = 255 - (255 - verso.astype(np.float32)) * spec.bleed
        out = np.minimum(out.astype(np.float32), show).astype(np.uint8)
    if spec.shadow:
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
        gradient = 1.0 - spec.shadow * np.clip(xx * 1.4 - 0.4, 0, 1) * (0.6 + 0.4 * yy)
        out = np.clip(out.astype(np.float32) * gradient, 0, 255).astype(np.uint8)
    if spec.curl:
        amplitude = spec.curl * h * 0.03
        xs = np.arange(w, dtype=np.float32)
        map_x = np.tile(xs, (h, 1))
        offset = amplitude * np.sin(np.pi * xs / w)
        map_y = np.arange(h, dtype=np.float32)[:, None] - offset[None, :]
        out = cv2.remap(out, map_x, map_y.astype(np.float32), cv2.INTER_LINEAR,
                        borderValue=255)
    scale = spec.dpi / RENDER_DPI
    if scale != 1.0:
        out = cv2.resize(out, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if spec.fade:
        out = (255 - (255 - out.astype(np.float32)) * (1.0 - spec.fade)).astype(np.uint8)
    if spec.angle:
        hh, ww = out.shape
        matrix = cv2.getRotationMatrix2D((ww / 2, hh / 2), spec.angle, 1.0)
        out = cv2.warpAffine(out, matrix, (ww, hh), flags=cv2.INTER_LINEAR, borderValue=255)
    if spec.blur:
        out = cv2.GaussianBlur(out, (0, 0), spec.blur)
    if spec.noise:
        noise = rng.normal(0.0, spec.noise, out.shape).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if spec.dither:
        # Fax: a 1-bit ordered dither.  Text survives, grey does not.
        bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
                         dtype=np.float32) / 16.0
        hh, ww = out.shape
        tile = np.tile(bayer, (hh // 4 + 1, ww // 4 + 1))[:hh, :ww]
        out = np.where(out.astype(np.float32) / 255.0 > tile, 255, 0).astype(np.uint8)
    if spec.jpeg < 95:
        ok, encoded = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, int(spec.jpeg)])
        if ok:
            out = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    return out


def _scale_boxes(boxes: list[tuple[float, float, float, float]], scale: float
                 ) -> list[tuple[float, float, float, float]]:
    return [(x0 * scale, y0 * scale, x1 * scale, y1 * scale) for x0, y0, x1, y1 in boxes]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def render(item: GoldenItem, stratum: str) -> Rendered | None:
    """The image for one item under one stratum, or ``None`` when its PDF is absent."""
    spec = DEGRADATIONS[stratum]
    rng = np.random.default_rng(_seed(item.id, stratum))
    boxes: list[tuple[float, float, float, float]] = []
    if item.source is Source.CONTROL:
        assert item.control is not None
        gray = control_image(item.control, height=1100 + 80 * item.page_index,
                             width=850 + 60 * item.page_index, seed=item.page_index)
        return Rendered(gray=gray, dpi=100, stratum=stratum)
    if item.source is Source.SYNTH:
        gray, boxes = render_synth(item)
    else:
        rendered = render_pdf(item)
        if rendered is None:
            return None
        gray = rendered
    if stratum != "native":
        gray = degrade(gray, spec, rng)
        boxes = _scale_boxes(boxes, spec.dpi / RENDER_DPI)
    return Rendered(gray=gray, dpi=spec.dpi, stratum=stratum, region_boxes=boxes)


def tesseract_lang(item: GoldenItem) -> str:
    return LANG_TESS.get(item.prose_lang, "por+eng")
