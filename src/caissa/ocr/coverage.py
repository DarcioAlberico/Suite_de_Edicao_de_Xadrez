"""How much of a region's ink a reading covers — OCR_UI_ROADMAP_C2 passo B14.

The arbiter's score is word confidence, plausibility and agreement: it judges
the words a reading **has**, never the ones it lost.  Measured on the golden
corpus (``OCR_UI_REPORT_C2_FASE5.md`` §B14): on the ``photo`` stratum the page
darkens to the right and Tesseract drops the end of every line, or four lines
of six, and the reading is *accepted* — ``synth:Dvoretsky…:201:21`` at 0,872
with CER 0,786; 30 items of the corpus accepted with CER above 0,10.  The
preprocessing variants that would read the rest (the shadow normalisation,
Sauvola) never ran, because the service only asks for them when the original
reading was refused.

The missing signal is the page's own ink.  :func:`ink_map` finds the ink that
looks like **lines of text** — after normalising the background, so a dark
corner of a photograph is not ink and faint show-through is not either — and
:func:`ink_coverage` says what share of that ink falls under the reading's
word boxes.  A reading that lost a line leaves that line's ink uncovered.

What is text ink, and why each rule (each was measured on a failure):

1.  **Dark against its own background**: a pixel below ``ink_fraction`` of the
    closed image (the paper, its shadow and its vignette).  Show-through at 25 %
    is 0,75 of the paper and never ink.
2.  **Letter-sized in inches**, not relative to the page: a halftone photograph
    is thousands of dots of 5 px, and a median taken over them made the letters
    "too big" — coverage 0,009 on a page whose text was read whole.  The ceiling
    is B11's physical one (a letter never passes 0,25 in); the floor is a
    period-free 0,03 in.
3.  **In a line of text**: the letters, smeared horizontally by two x-heights
    (a word gap closes, a column gutter does not), must join into a run much
    wider than it is tall, not taller than a line, and **dense** -- a letter
    every x-height or so.  A texture of letter-sized blobs (a continuous-tone
    photograph, an ornament) smears into shapes that are tall, short or sparse;
    and each letter weighs one, so a blob that slips through cannot outweigh a
    line.  Measured on synthetic photographs: coverage 0,64–0,72 → 1,0.
4.  **Not inside a big thing**: everything inside the box of a component far
    taller than a line — a board's frame and its pieces, a figure — is not the
    region's text; nor is what lies in the boxes the caller names (the
    diagrams the importer located).

A region with fewer than :attr:`CoverageConfig.min_components` letters says
nothing (``None``): a folio, a caption of two words.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .types import BBox, OcrResult

__all__ = ["CoverageConfig", "InkMap", "ink_coverage", "ink_map"]


@dataclass(frozen=True, slots=True)
class CoverageConfig:
    """The measure's numbers, each with its reason."""

    #: The background is the image closed by a square this many inches wide
    #: (61 px at 300 DPI): wider than any letter, so the closing removes the
    #: text and keeps the paper, its shadow and its vignette.
    background_in: float = 0.2
    #: Ink is a pixel darker than this share of its local background.  The
    #: synthetic show-through of ``shadow_curl_bleed`` is the page mirrored at
    #: 25 % (``sol_corpus.degrade``): 0,75 of the background, never ink.
    ink_fraction: float = 0.62
    #: A letter's height in inches: no taller than B11's physical ceiling
    #: (``portfolio.LETTER_MAX_INCHES``), no shorter than a small x-height.
    min_letter_in: float = 0.03
    max_letter_in: float = 0.25
    #: A component this many times longer than tall is a rule, not a letter.
    max_aspect: float = 25.0
    #: The horizontal smear that joins letters into a line, in median letter
    #: heights (the x-height): it must close a word gap (up to about one x-height
    #: in justified text) and never a column gutter (three or more).
    smear: float = 2.0
    #: A run of smeared letters is a line of text when it is at least this many
    #: times wider than tall...
    line_min_aspect: float = 3.0
    #: ...and no taller than this many median letter heights.  The median is the
    #: x-height; a real line spans ascenders, descenders and, in a photograph,
    #: its own slant -- measured 1,1–2,9 on the ``photo`` stratum.
    line_max_height: float = 3.5
    #: ...and dense: at least this many letters per median letter height of its
    #: width.  A line of text has a letter every ~0,7 x-height; a row of blobs of a
    #: photograph (3.600–4.700 px each, measured on a synthetic one) has a few.
    line_min_density: float = 0.4
    #: A component taller than this many median letter heights is a "big
    #: thing" (a board, a figure): it is not a letter, and what lies inside its
    #: box is not the region's text.
    big_rel_height: float = 4.0
    #: A word box is padded by this share of its height before the ink under
    #: it is counted: accents, dots and the tail of a comma sit just outside.
    pad: float = 0.35
    #: Fewer letters than this in a region and coverage is not measured.
    min_components: int = 12


@dataclass(frozen=True, slots=True)
class InkMap:
    """Text ink of one raster: centroid and area of each letter component."""

    cx: NDArray[np.float64]
    cy: NDArray[np.float64]
    area: NDArray[np.float64]

    @property
    def count(self) -> int:
        return int(self.cx.size)

    @property
    def total(self) -> float:
        return float(self.area.sum())

    def _keep(self, mask: NDArray[np.bool_]) -> InkMap:
        return InkMap(self.cx[mask], self.cy[mask], self.area[mask])

    def within(self, box: BBox) -> InkMap:
        """The components whose centre lies in ``box`` (pixels)."""
        mask = (self.cx >= box.x0) & (self.cx <= box.x1) & (self.cy >= box.y0) & (self.cy <= box.y1)
        return self._keep(mask)

    def excluding(self, boxes: Iterable[BBox]) -> InkMap:
        """The components outside every box (pixels)."""
        mask = np.ones(self.count, dtype=bool)
        for box in boxes:
            mask &= ~((self.cx >= box.x0) & (self.cx <= box.x1)
                      & (self.cy >= box.y0) & (self.cy <= box.y1))
        return self._keep(mask)


_EMPTY = InkMap(np.zeros(0), np.zeros(0), np.zeros(0))


def ink_map(gray: NDArray[np.uint8] | None, dpi: float, *,
            config: CoverageConfig | None = None,
            exclude: Sequence[BBox] = ()) -> InkMap:
    """The text ink of ``gray`` (a raster at ``dpi``), outside ``exclude``."""
    import cv2

    cfg = config or CoverageConfig()
    if gray is None or getattr(gray, "size", 0) == 0:
        return _EMPTY
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    dpi = max(float(dpi), 72.0)
    side = max(15, int(round(dpi * cfg.background_in)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (side, side))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    background = cv2.GaussianBlur(background, (0, 0), side / 4.0)
    ink = (gray.astype(np.float32) < cfg.ink_fraction * np.maximum(background.astype(np.float32), 1.0))
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    if count <= 1:
        return _EMPTY
    x, y, w, h, area = (stats[1:, i].astype(np.float64) for i in range(5))
    cx, cy = centroids[1:, 0].astype(np.float64), centroids[1:, 1].astype(np.float64)
    # (2) letter-sized in inches -- a relative median is hijacked by halftone dots
    low, high = cfg.min_letter_in * dpi, cfg.max_letter_in * dpi
    letters = (h >= low) & (h <= high) & (w <= cfg.max_aspect * np.maximum(h, 1.0)) & (area >= 4)
    if int(letters.sum()) < 3:
        return _EMPTY
    median = float(np.median(h[letters]))
    # (4) what is inside a big thing is not text
    big = h > cfg.big_rel_height * median
    holes = [BBox(float(x[i]), float(y[i]), float(w[i]), float(h[i])) for i in np.flatnonzero(big)]
    # (3) in a line of text: smear the letters horizontally and keep the runs
    # that are lines -- wide, and no taller than a line
    canvas = np.zeros(gray.shape[:2], dtype=np.uint8)
    for i in np.flatnonzero(letters):
        canvas[int(y[i]):int(y[i] + h[i]), int(x[i]):int(x[i] + w[i])] = 255
    reach = max(3, int(round(cfg.smear * median)))
    smeared = cv2.dilate(canvas, cv2.getStructuringElement(cv2.MORPH_RECT, (reach, 1)))
    runs, run_labels, run_stats, _ = cv2.connectedComponentsWithStats(smeared, 8)
    is_line = np.zeros(runs, dtype=bool)
    rw, rh = run_stats[:, cv2.CC_STAT_WIDTH], run_stats[:, cv2.CC_STAT_HEIGHT]
    is_line[1:] = (rw[1:] >= cfg.line_min_aspect * rh[1:]) & (rh[1:] <= cfg.line_max_height * median)
    iy = np.clip(cy.astype(np.int64), 0, gray.shape[0] - 1)
    ix = np.clip(cx.astype(np.int64), 0, gray.shape[1] - 1)
    run_of = run_labels[iy, ix]
    per_run = np.bincount(run_of[letters], minlength=runs)
    dense = per_run >= cfg.line_min_density * rw / max(median, 1.0)
    in_line = (is_line & dense)[run_of]
    keep = letters & in_line
    # Each letter weighs one: a blob that slips through must not outweigh a line.
    found = InkMap(cx[keep], cy[keep], np.ones(int(keep.sum())))
    return found.excluding([*holes, *exclude])


def ink_coverage(result: OcrResult, ink: InkMap, *,
                 config: CoverageConfig | None = None) -> float | None:
    """The share of ``ink`` (letters) whose centre lies under a word of ``result``.

    ``None`` when the ink has fewer than ``min_components`` letters -- nothing
    to say.  Boxes are in the raster's pixel space, as the service keeps them.
    """
    cfg = config or CoverageConfig()
    if ink.count < cfg.min_components or ink.total <= 0:
        return None
    covered = np.zeros(ink.count, dtype=bool)
    for line in result.lines:
        for word in line.words:
            if not word.text.strip():
                continue
            box = word.box
            pad = cfg.pad * max(box.h, 1.0)
            covered |= ((ink.cx >= box.x0 - pad) & (ink.cx <= box.x1 + pad)
                        & (ink.cy >= box.y0 - pad) & (ink.cy <= box.y1 + pad))
    return float(ink.area[covered].sum() / ink.total)
