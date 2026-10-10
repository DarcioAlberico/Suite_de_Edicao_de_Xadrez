"""Image preprocessing for OCR — SPEC §7.2, as composable, reporting steps.

Every step is an object with three obligations:

* it can be switched off individually (``enabled``), because no single ordering
  is right for every scan and the user needs to be able to say "stop doing the
  thing that is ruining my page";
* it can be *measured* individually, so a test can assert that deskew recovers
  a known angle rather than merely asserting that it returned an image;
* it reports what it did (:class:`StepReport`), in numbers for the debugger and
  in a Brazilian Portuguese sentence for the UI.

The default order is not arbitrary:

    upscale -> shadow removal -> bleed-through -> reverse video -> deskew
            -> dewarp -> binarise (Sauvola) -> despeckle

Grayscale corrections come first because they are all photometric and none of
them cares about geometry.  Reverse video (white text knocked out of a black
band) is the last of them: it needs the flattened page so that a gutter shadow
is not mistaken for a band, and it must precede binarisation so that the
engines see the band's text as ordinary ink.  Geometry comes next, on grayscale, because rotating
or remapping a *binary* image quantises every stroke edge into a staircase that
no later step can undo.  Binarisation is therefore last but one, and despeckle
follows it because "speck" is only definable once there are connected
components to measure.

Nothing here is adaptive-by-magic: every threshold is a named parameter with a
documented default, and every default that depends on resolution is derived
from the declared DPI rather than guessed from the pixel count.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

__all__ = [
    "PreprocessContext",
    "PreprocessOutcome",
    "PreprocessPipeline",
    "PreprocessStep",
    "StepReport",
    "Deskew",
    "ShadowRemoval",
    "BleedThroughReduction",
    "Binarize",
    "Despeckle",
    "Dewarp",
    "ReverseBand",
    "ReverseVideo",
    "Upscale",
    "BAND_HALO",
    "BAND_INVERT",
    "default_pipeline",
    "deskew_image",
    "estimate_skew_angle",
    "find_reverse_bands",
    "invert_reverse_bands",
    "sauvola_threshold",
    "otsu_threshold",
    "to_gray",
]

Image = NDArray[np.uint8]


# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #


def to_gray(image: NDArray[Any]) -> Image:
    """Single-channel uint8 copy of ``image``."""
    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        if arr.dtype.kind == "f":
            hi = float(arr.max()) if arr.size else 1.0
            arr = np.clip(arr * (255.0 if hi <= 1.0 + 1e-6 else 1.0), 0, 255)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 3:
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        if arr.shape[2] == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        else:
            arr = arr[:, :, 0]
    elif arr.ndim != 2:
        raise ValueError(f"imagem com {arr.ndim} dimensões não é suportada")
    return np.ascontiguousarray(arr)


def _odd(value: float, minimum: int = 3) -> int:
    n = max(minimum, int(round(value)))
    return n if n % 2 == 1 else n + 1


def otsu_threshold(gray: Image) -> int:
    """Otsu's global threshold, computed directly from the histogram.

    Written out rather than delegated to ``cv2.threshold`` so that the
    Sauvola-versus-Otsu comparison in the tests is a comparison of the two
    algorithms and not of two libraries' edge-case conventions.
    """
    hist = np.bincount(gray.reshape(-1), minlength=256).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 127
    levels = np.arange(256, dtype=np.float64)
    weight_bg = np.cumsum(hist)
    weight_fg = total - weight_bg
    sum_total = float((hist * levels).sum())
    sum_bg = np.cumsum(hist * levels)
    valid = (weight_bg > 0) & (weight_fg > 0)
    if not valid.any():
        return 127
    mean_bg = np.divide(sum_bg, weight_bg, out=np.zeros(256), where=weight_bg > 0)
    mean_fg = np.divide(sum_total - sum_bg, weight_fg,
                        out=np.zeros(256), where=weight_fg > 0)
    between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    between[~valid] = -1.0
    return int(np.argmax(between))


def _integral_mean_std(gray: Image, window: int) -> tuple[NDArray[np.float64],
                                                          NDArray[np.float64]]:
    """Local mean and standard deviation over a ``window`` x ``window`` box.

    Uses summed-area tables in float64.  float32 is not enough here: the sum of
    squares over a 25x25 window of 8-bit values reaches 4e7, and accumulating
    those across a 3000x2000 page in float32 loses the low bits that the
    variance is made of, which shows up as banding in the threshold surface.

    Windows are clamped at the image border rather than reflected, so an edge
    pixel is thresholded against the pixels that actually exist.
    """
    img = gray.astype(np.float64)
    h, w = img.shape
    radius = window // 2

    integral = np.zeros((h + 1, w + 1), dtype=np.float64)
    integral_sq = np.zeros((h + 1, w + 1), dtype=np.float64)
    np.cumsum(np.cumsum(img, axis=0), axis=1, out=integral[1:, 1:])
    np.cumsum(np.cumsum(img * img, axis=0), axis=1, out=integral_sq[1:, 1:])

    y0 = np.clip(np.arange(h) - radius, 0, h)
    y1 = np.clip(np.arange(h) + radius + 1, 0, h)
    x0 = np.clip(np.arange(w) - radius, 0, w)
    x1 = np.clip(np.arange(w) + radius + 1, 0, w)

    yy0, xx0 = y0[:, None], x0[None, :]
    yy1, xx1 = y1[:, None], x1[None, :]
    count = ((yy1 - yy0) * (xx1 - xx0)).astype(np.float64)

    def box(table: NDArray[np.float64]) -> NDArray[np.float64]:
        return (table[yy1, xx1] - table[yy0, xx1]
                - table[yy1, xx0] + table[yy0, xx0])

    total = box(integral)
    total_sq = box(integral_sq)
    mean = total / count
    variance = np.maximum(total_sq / count - mean * mean, 0.0)
    return mean, np.sqrt(variance)


def sauvola_threshold(gray: Image, window: int = 25, k: float = 0.2,
                      r: float = 128.0) -> NDArray[np.float64]:
    """Sauvola's local threshold surface ``T = m (1 + k (s/R - 1))``.

    ``R`` is the dynamic range of the standard deviation (128 for 8-bit), and
    ``k`` controls how far below the local mean the threshold sits in
    low-variance regions.  The point of the ``s/R`` term is that in a *flat*
    region (blank paper, however dark or bright) ``s`` is near zero, the
    threshold collapses to ``m(1-k)`` — safely below the paper — and no ink is
    hallucinated.  Otsu, having one global threshold, cannot do this, which is
    why it fails on unevenly lit pages.
    """
    window = _odd(window)
    mean, std = _integral_mean_std(gray, window)
    return mean * (1.0 + k * (std / r - 1.0))


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class StepReport:
    """What one step did, for the UI and for debugging."""

    name: str
    #: The step ran, i.e. it was enabled and did not raise.
    applied: bool
    duration_s: float
    message_pt: str
    detail: Mapping[str, Any] = field(default_factory=dict)
    #: The step actually altered the image.  ``applied`` alone is not enough:
    #: every step here can decide, correctly, to do nothing — a level page needs
    #: no deskew, a flat page no shadow removal, a 300 DPI page no upscaling —
    #: and reporting those as "applied" told the UI, and a caller comparing
    #: pipelines, the opposite of the truth.
    changed: bool = True

    def __str__(self) -> str:
        mark = "•" if self.changed else "–"
        return f"{mark} {self.name}: {self.message_pt} ({self.duration_s * 1000:.0f} ms)"


@dataclass(slots=True)
class PreprocessContext:
    """State threaded through the pipeline.

    ``dpi`` is the single most useful thing a caller can supply: almost every
    default below is a physical size in inches wearing pixel clothing, and
    getting it from the PDF is free.
    """

    dpi: int = 300
    #: The reverse side of the sheet, for true bleed-through subtraction.
    verso: Image | None = None
    #: Set once an image has been reduced to two levels.
    is_binary: bool = False
    #: Estimated background level, kept so geometry steps fill with paper
    #: colour instead of black.
    background: int = 255
    lang: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PreprocessOutcome:
    """Result of running a pipeline."""

    image: Image
    reports: tuple[StepReport, ...]
    context: PreprocessContext
    total_duration_s: float

    def report_for(self, name: str) -> StepReport | None:
        for report in self.reports:
            if report.name == name:
                return report
        return None

    @property
    def applied_steps(self) -> tuple[str, ...]:
        """Steps that ran *and* changed the page."""
        return tuple(r.name for r in self.reports if r.applied and r.changed)

    def describe_pt(self) -> str:
        lines = [str(r) for r in self.reports]
        lines.append(f"Total: {self.total_duration_s * 1000:.0f} ms")
        return "\n".join(lines)


class PreprocessStep(Protocol):
    """One transformation of the page image."""

    name: str
    enabled: bool

    def apply(self, image: Image,
              ctx: PreprocessContext) -> tuple[Image, StepReport]:
        ...


class _StepBase:
    """Timing, the disabled path, and the failure path shared by all steps.

    A preprocessing failure must not lose the page: the step returns the image
    it was given, says so, and the pipeline continues.  A batch of 500 books is
    not the place to discover that one unusual page shape crashes a morphology
    call.
    """

    name = "step"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def apply(self, image: Image,
              ctx: PreprocessContext) -> tuple[Image, StepReport]:
        if not self.enabled:
            return image, StepReport(self.name, False, 0.0, "desativado",
                                     changed=False)
        started = time.perf_counter()
        try:
            out, message, detail = self._run(image, ctx)
        except (cv2.error, ValueError, MemoryError) as exc:
            return image, StepReport(
                self.name, False, time.perf_counter() - started,
                f"falhou e foi ignorado: {exc}", {"error": str(exc)},
                changed=False,
            )
        # Every no-op path below returns the array it was handed, so identity is
        # an exact and free test for "nothing happened".  Comparing contents
        # instead would cost a full-page compare on the hot path.
        return out, StepReport(self.name, True, time.perf_counter() - started,
                               message, detail, changed=out is not image)

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Deskew
# --------------------------------------------------------------------------- #


def estimate_skew_angle(
    gray: Image,
    *,
    max_angle: float = 10.0,
    coarse_step: float = 0.5,
    fine_step: float = 0.02,
    max_width: int = 1200,
    min_ink_pixels: int = 200,
) -> tuple[float, dict[str, Any]]:
    """Skew angle in degrees, positive when text slopes down to the right.

    Projection-profile method, but computed **without rotating anything**.  For
    a candidate angle the projection coordinate of an ink pixel is
    ``y cos t - x sin t``; histogramming that over the ink pixels gives exactly
    the profile a rotation would produce, with two advantages that matter for
    the required 0.2 degree accuracy:

    * no interpolation, so the ink mass is identical at every candidate angle
      and the scores are directly comparable;
    * the angular resolution is limited by the page width, not by the pixel
      grid, so a 0.02 degree step is meaningful on a page 1200 px wide.

    The score is the sum of squared bin counts.  Because the pixel set does not
    change with the angle, the sum of the bins is constant, so maximising the
    sum of squares is exactly maximising the variance of the profile — peaky
    profile, aligned text lines.
    """
    small = gray
    scale = 1.0
    if gray.shape[1] > max_width:
        scale = max_width / gray.shape[1]
        small = cv2.resize(gray, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA)

    threshold = otsu_threshold(small)
    ink = small <= threshold
    ys, xs = np.nonzero(ink)
    detail: dict[str, Any] = {
        "ink_pixels": int(ys.size),
        "scale": scale,
        "threshold": threshold,
    }
    if ys.size < min_ink_pixels:
        detail["reason"] = "tinta insuficiente para estimar a inclinação"
        return 0.0, detail

    ys = ys.astype(np.float64)
    xs = xs.astype(np.float64)
    height = float(small.shape[0])
    width = float(small.shape[1])
    offset = width  # keeps the projection coordinate non-negative
    n_bins = int(math.ceil(height + width)) + 2

    def score(angle_deg: float) -> float:
        t = math.radians(angle_deg)
        proj = ys * math.cos(t) - xs * math.sin(t) + offset
        bins = np.bincount(proj.astype(np.int64), minlength=n_bins)
        return float(np.dot(bins, bins))

    def best_in(grid: Sequence[float]) -> tuple[float, float]:
        best_angle, best_score = 0.0, -1.0
        for angle in grid:
            value = score(angle)
            # Strict ">" makes the search deterministic: on a tie the smallest
            # angle in the grid wins, and the grid is generated in order.
            if value > best_score:
                best_angle, best_score = angle, value
        return best_angle, best_score

    steps = int(round(2 * max_angle / coarse_step)) + 1
    coarse_grid = [-max_angle + i * coarse_step for i in range(steps)]
    coarse_angle, _ = best_in(coarse_grid)

    # The fine grid is clamped to the caller's range.  Without the clamp a
    # coarse winner at the edge of the range lets the refinement step outside
    # it, and ``Deskew(max_angle=3)`` returns 3.5 — a promise the parameter
    # made and the function broke.
    span = coarse_step
    fine_steps = int(round(2 * span / fine_step)) + 1
    fine_grid = [
        angle for angle in
        (coarse_angle - span + i * fine_step for i in range(fine_steps))
        if -max_angle - 1e-9 <= angle <= max_angle + 1e-9
    ] or [coarse_angle]
    angle, best_score = best_in(fine_grid)

    flat_score = score(0.0)
    detail.update({
        "coarse_angle": coarse_angle,
        "angle": angle,
        "score": best_score,
        "score_at_zero": flat_score,
        "gain": (best_score / flat_score) if flat_score > 0 else 1.0,
    })
    return angle, detail


class Deskew(_StepBase):
    """Rotate the page so its text lines are horizontal."""

    name = "deskew"

    def __init__(self, enabled: bool = True, *, max_angle: float = 10.0,
                 coarse_step: float = 0.5, fine_step: float = 0.02,
                 min_angle: float = 0.15) -> None:
        super().__init__(enabled)
        self.max_angle = max_angle
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        #: Below this the rotation costs more (interpolation blur) than it buys
        #: — and, more to the point, below this the estimator is not measuring
        #: anything.  Measured on four synthetic pages that are level by
        #: construction (different body sizes and line lengths), the estimate
        #: comes back at -0.06, -0.08, -0.12 and -0.12 degrees: a small
        #: systematic bias, because ragged line ends make the projection
        #: profile very slightly asymmetric.  The previous default of 0.05
        #: sat *below* that floor, so every already-level page in the corpus
        #: was resampled — a bicubic warp, and the blur that comes with it, to
        #: correct noise.
        self.min_angle = min_angle

    def estimate(self, image: Image) -> tuple[float, dict[str, Any]]:
        return estimate_skew_angle(
            to_gray(image), max_angle=self.max_angle,
            coarse_step=self.coarse_step, fine_step=self.fine_step)

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        gray = to_gray(image)
        angle, detail = estimate_skew_angle(
            gray, max_angle=self.max_angle, coarse_step=self.coarse_step,
            fine_step=self.fine_step)
        detail["min_angle"] = self.min_angle
        if abs(angle) < self.min_angle:
            return (image,
                    f"inclinação de {angle:+.2f}° está dentro da tolerância; "
                    f"nada a corrigir", detail)

        rotated = deskew_image(image, angle, background=ctx.background)
        detail["applied_angle"] = angle
        return (rotated,
                f"inclinação de {angle:+.2f}° corrigida", detail)


def deskew_image(image: Image, skew_deg: float, *,
                 background: int = 255) -> Image:
    """Undo a measured skew of ``skew_deg``, keeping the whole page.

    Sign convention, stated once so it is not rediscovered by experiment:
    :func:`estimate_skew_angle` returns a positive angle when text slopes
    *down* to the right, which is what a clockwise rotation of the page does.
    OpenCV's ``getRotationMatrix2D`` takes positive angles as counter-clockwise
    with the origin at the top left.  Undoing a clockwise skew therefore means
    passing the skew straight through, unnegated.

    The canvas grows so that no corner is clipped: a 300 DPI page rotated by
    two degrees loses a strip 25 px deep at each corner otherwise, and on a
    tightly cropped scan that strip contains text.
    """
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), skew_deg, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(math.ceil(h * sin + w * cos))
    new_h = int(math.ceil(h * cos + w * sin))
    matrix[0, 2] += (new_w - w) / 2.0
    matrix[1, 2] += (new_h - h) / 2.0
    return cv2.warpAffine(
        image, matrix, (new_w, new_h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
        borderValue=int(background),
    )


# --------------------------------------------------------------------------- #
# Shadow removal
# --------------------------------------------------------------------------- #


class ShadowRemoval(_StepBase):
    """Flatten uneven illumination by dividing out an estimated background.

    The background is a morphological closing with a structuring element larger
    than any stroke: closing removes everything darker than its neighbourhood
    that is smaller than the element, which is precisely the definition of
    "text".  What survives is the page lighting — the gutter shadow of a book
    photographed open, the falloff of a flatbed lamp, the darkening at the
    spine — and dividing by it flattens the page without touching the ink.

    Division rather than subtraction because illumination is multiplicative:
    ink in a dim region is dim ink, not ink minus a constant.
    """

    name = "shadow_removal"

    def __init__(self, enabled: bool = True, *,
                 kernel_inches: float = 0.18,
                 smooth_inches: float = 0.10,
                 min_spread: int = 12) -> None:
        super().__init__(enabled)
        self.kernel_inches = kernel_inches
        self.smooth_inches = smooth_inches
        #: Skip when the page is already flat; the division is not free and it
        #: slightly compresses contrast.
        self.min_spread = min_spread

    def estimate_background(self, image: Image, dpi: int = 300) -> Image:
        gray = to_gray(image)
        k = _odd(self.kernel_inches * dpi, 9)
        k = min(k, _odd(min(gray.shape) // 2, 9))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        smooth = _odd(self.smooth_inches * dpi, 5)
        smooth = min(smooth, _odd(min(gray.shape) // 2, 5))
        return cv2.medianBlur(background, smooth)

    @staticmethod
    def _spread(background: Image) -> float:
        lo, hi = np.percentile(background, [5.0, 95.0])
        return float(hi - lo)

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        gray = to_gray(image)
        background = self.estimate_background(gray, ctx.dpi)
        before = self._spread(background)
        detail: dict[str, Any] = {"background_spread_before": round(before, 2)}
        if before < self.min_spread:
            detail["skipped"] = True
            return (gray,
                    f"iluminação já uniforme (variação de {before:.0f} níveis); "
                    f"nada a corrigir", detail)

        safe = np.maximum(background.astype(np.float32), 1.0)
        flattened = np.clip(gray.astype(np.float32) * 255.0 / safe, 0, 255)
        out = flattened.astype(np.uint8)
        after = self._spread(self.estimate_background(out, ctx.dpi))
        detail["background_spread_after"] = round(after, 2)
        ctx.background = 255
        return (out,
                f"sombra removida: variação do fundo caiu de {before:.0f} para "
                f"{after:.0f} níveis", detail)


# --------------------------------------------------------------------------- #
# Bleed-through
# --------------------------------------------------------------------------- #


class BleedThroughReduction(_StepBase):
    """Suppress ink showing through from the reverse of the sheet.

    Two modes:

    *With* the verso image, the problem is well posed: mirror the reverse side,
    register it against the front, and anything dark on the mirrored verso that
    is only *mid*-grey on the front is show-through, not ink.  This is the
    honest solution and it is what SPEC §7.2 asks for.

    *Without* it, the only usable prior is that show-through is fainter than
    ink and is not connected to it.  So: threshold twice, and lighten the
    mid-grey pixels that no genuine ink component reaches.  Being connected to
    real ink protects antialiasing halos and the faint tails of thin strokes,
    which a plain "lighten everything mid-grey" rule destroys — and destroying
    the tails of thin strokes is worse than leaving the show-through in.
    """

    name = "bleed_through"

    def __init__(self, enabled: bool = True, *,
                 band: int | None = None,
                 band_fraction: float = 0.80,
                 dilate_inches: float = 0.012,
                 max_shift_inches: float = 0.05,
                 target: int = 255) -> None:
        super().__init__(enabled)
        #: Absolute width of the "suspicious" band above the ink threshold, in
        #: grey levels.  ``None`` derives it from the page instead, which is
        #: what the default does and why:
        #:
        #: a fixed 60 levels was the first version, and it made the step see
        #: only show-through in a 60-level window just above the ink
        #: threshold.  Measured on a synthetic page with a ghost at level 214:
        #: Otsu put the ink threshold at 146, so the window ended at 206 and
        #: the ghost — plainly visible, plainly not ink — was never touched.
        #: Show-through is defined by where it sits *between ink and paper*,
        #: not by a constant number of levels, so the band is now a fraction of
        #: that range.
        self.band = band
        #: Share of the ink-to-paper range treated as possible show-through.
        #: Below 1.0 so that clean paper is never a candidate.
        self.band_fraction = band_fraction
        self.dilate_inches = dilate_inches
        self.max_shift_inches = max_shift_inches
        self.target = target

    @staticmethod
    def paper_level(gray: Image) -> int:
        """The page's paper brightness — the 98th percentile, not the maximum.

        The maximum is a single blown-out pixel on any real scan.
        """
        return int(np.percentile(gray, 98.0)) if gray.size else 255

    def band_high(self, gray: Image, ink_threshold: int) -> int:
        if self.band is not None:
            return int(min(255, ink_threshold + self.band))
        paper = self.paper_level(gray)
        span = max(0, paper - ink_threshold)
        return int(min(255, ink_threshold + round(self.band_fraction * span)))

    # -- verso path -------------------------------------------------------- #

    def register_verso(self, gray: Image, verso: Image,
                       dpi: int = 300) -> tuple[Image, tuple[int, int], float]:
        """Mirror ``verso`` and align it to ``gray``; returns the aligned image,
        the shift applied, and the normalised correlation achieved."""
        mirrored = cv2.flip(to_gray(verso), 1)
        if mirrored.shape != gray.shape:
            mirrored = cv2.resize(mirrored, (gray.shape[1], gray.shape[0]),
                                  interpolation=cv2.INTER_AREA)
        limit = max(1, int(round(self.max_shift_inches * dpi)))
        pad = cv2.copyMakeBorder(mirrored, limit, limit, limit, limit,
                                 cv2.BORDER_REPLICATE)
        # Correlate the *inverted* images: both sides' ink is dark, and
        # matchTemplate on the raw images is dominated by the paper.
        result = cv2.matchTemplate(255 - pad, 255 - gray, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(result)
        dx, dy = loc[0] - limit, loc[1] - limit
        matrix = np.float32([[1, 0, -dx], [0, 1, -dy]])
        aligned = cv2.warpAffine(mirrored, matrix,
                                 (gray.shape[1], gray.shape[0]),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=255)
        return aligned, (int(dx), int(dy)), float(score)

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        gray = to_gray(image)
        ink_threshold = otsu_threshold(gray)
        band_hi = self.band_high(gray, ink_threshold)
        ink = gray <= ink_threshold
        suspicious = (gray > ink_threshold) & (gray <= band_hi)

        detail: dict[str, Any] = {
            "ink_threshold": ink_threshold,
            "band_high": band_hi,
            "paper_level": self.paper_level(gray),
            "suspicious_pixels": int(suspicious.sum()),
        }

        if ctx.verso is not None:
            aligned, shift, score = self.register_verso(gray, ctx.verso, ctx.dpi)
            verso_ink = aligned <= otsu_threshold(aligned)
            mask = suspicious & verso_ink & ~ink
            detail.update({"mode": "verso", "shift": shift,
                           "correlation": round(score, 4)})
        else:
            radius = max(1, int(round(self.dilate_inches * ctx.dpi)))
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
            near_ink = cv2.dilate(ink.astype(np.uint8), kernel) > 0
            mask = suspicious & ~near_ink
            detail.update({"mode": "heuristic", "dilate_radius": radius})

        removed = int(mask.sum())
        detail["removed_pixels"] = removed
        if removed == 0:
            return gray, "nenhum vestígio de transparência do verso encontrado", detail

        out = gray.copy()
        out[mask] = self.target
        share = removed / gray.size
        detail["removed_fraction"] = round(share, 5)
        return (out,
                f"transparência do verso reduzida em {removed} pixel(s) "
                f"({share:.2%} da página)", detail)


# --------------------------------------------------------------------------- #
# Reverse video (white text on a black band)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ReverseBand:
    """One black band with light text knocked out of it, in pixel coordinates.

    ``x1``/``y1`` are exclusive, numpy-slice style.  ``dark_share`` is the
    share of the band's box that is ink in the *input*: the number that made
    it a band rather than a word, kept so a report can say why.
    """

    x0: int
    y0: int
    x1: int
    y1: int
    dark_share: float

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


#: Values of the mask :func:`find_reverse_bands` returns.
BAND_INVERT = 1
BAND_HALO = 2


def _band_core_rows(box_ink: NDArray[np.uint8], min_margin_share: float,
                    inset: int = 2) -> tuple[int, int]:
    """``(first, last)`` rows of ``box_ink`` whose two end margins are solid.

    Falls back to the whole box when no row qualifies — a band whose text
    runs to its very ends has no solid margin to measure, and keeping it
    whole is the harmless answer.
    """
    h, w = box_ink.shape
    m = max(4, round(0.05 * w))
    lo, hi = min(inset, max(0, w - 1)), max(w - inset, 0)
    if hi - lo < 2 * m:
        return 0, h - 1
    margins = np.concatenate([box_ink[:, lo:lo + m], box_ink[:, hi - m:hi]], axis=1)
    solid = np.flatnonzero(margins.mean(axis=1) >= min_margin_share)
    if solid.size == 0:
        return 0, h - 1
    return int(solid[0]), int(solid[-1])


def _fill_holes(mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Fill every enclosed hole of a 0/1 mask (the counters of the letters)."""
    h, w = mask.shape
    padded = np.zeros((h + 2, w + 2), dtype=np.uint8)
    padded[1:-1, 1:-1] = mask
    outside = (1 - padded).astype(np.uint8)
    flood = outside.copy()
    cv2.floodFill(flood, np.zeros((h + 4, w + 4), dtype=np.uint8), (0, 0), 2)
    # ``outside`` pixels the flood did not reach are holes.
    holes = (flood == 1)
    filled = padded.copy()
    filled[holes] = 1
    return filled[1:-1, 1:-1]


def find_reverse_bands(image: NDArray[Any], dpi: int = 300, *,
                       min_width_inches: float = 0.6,
                       min_height_inches: float = 0.06,
                       max_height_inches: float = 0.75,
                       min_aspect: float = 2.5,
                       min_dark_share: float = 0.55,
                       min_solidity: float = 0.80,
                       close_inches: float = 0.03,
                       min_margin_share: float = 0.9,
                       ) -> tuple[list[ReverseBand], NDArray[np.uint8]]:
    """Locate the black bands that carry light text.

    The game header of a Yusupov solutions page, the shaded row of a table,
    a reversed title.

    Returns ``(bands, mask)``: the bands found and a page mask in which
    :data:`BAND_INVERT` marks the band's own pixels, holes filled — exactly
    the set to invert — and :data:`BAND_HALO` marks the ragged fringe a
    scanner leaves along the band's edge, which belongs to no text and is
    erased: left alone it becomes, after the inversion, a dark strip of noise
    that an engine reads as a line of its own.

    A band is defined by what it is, not by what it contains: a box of the
    page where **most pixels are dark** (``min_dark_share`` of the input's
    ink), **wide and short** (``min_aspect``, the height between
    ``min_height_inches`` and ``max_height_inches``), **solid** once the
    light strokes are closed (``min_solidity``).  Each criterion rules out
    one neighbour: a bold heading is wide and short but at most 45 % ink
    once its letters are closed into a blob; a chess diagram is half dark but
    square; a rule is wide and dark but thinner than 0.06 in; a photograph is
    dark but taller than 0.75 in, and inverting one that is not would cost
    nothing a recogniser could read anyway.

    The band's **core** is the run of rows whose left and right margins (5 %
    of the width at each end) are solid ink to ``min_margin_share``: a row of
    the band with text on it is still solid at its ends, while a row of the
    scanner's fringe is a texture everywhere (measured on the Yusupov page:
    0,30 at most in the fringe, 1,00 in every row of the band).  Rows of the
    box outside the core are fringe.

    Everything is physical (inches at ``dpi``) so the same band is found at
    150 and at 600 DPI.
    """
    gray = to_gray(image)
    h, w = gray.shape[:2]
    empty = np.zeros((h, w), dtype=np.uint8)
    if gray.size == 0:
        return [], empty
    threshold = otsu_threshold(gray)
    ink = (gray <= threshold).astype(np.uint8)
    if not ink.any():
        return [], empty
    k = _odd(close_inches * dpi, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    # Closing the ink swallows the light strokes, so a band becomes one solid
    # component; letters of black text merge into word blobs that the dark
    # share and the solidity then reject.
    solid = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    min_w = max(4, round(min_width_inches * dpi))
    min_h = max(3, round(min_height_inches * dpi))
    max_h = max(min_h, round(max_height_inches * dpi))
    bands: list[ReverseBand] = []
    mask = empty
    for label in range(1, count):
        x, y, bw, bh, area = (int(v) for v in stats[label])
        if bw < min_w or bh < min_h or bh > max_h or bw < min_aspect * bh:
            continue
        if area < min_solidity * bw * bh:
            continue
        box_ink = ink[y:y + bh, x:x + bw]
        dark_share = float(box_ink.mean())
        if dark_share < min_dark_share:
            continue
        component = (labels[y:y + bh, x:x + bw] == label).astype(np.uint8)
        filled = _fill_holes(component)
        # Opening trims the ragged halo a scanner leaves along the band's
        # edge, which the closing above joined to the body; the rectangular
        # body itself is unchanged by a rectangular element.
        trimmed = cv2.morphologyEx(filled, cv2.MORPH_OPEN, kernel)
        if not trimmed.any():
            continue
        first, last = _band_core_rows(box_ink, min_margin_share)
        if mask is empty:
            mask = empty.copy()
        window = mask[y:y + bh, x:x + bw]
        body = trimmed.astype(bool)
        # The fringe is what the closing joined to the band and the opening
        # took away, plus the rows of the box above and below the solid core.
        halo = component.astype(bool) & ~body
        halo[:first] |= body[:first]
        halo[last + 1:] |= body[last + 1:]
        body[:first] = False
        body[last + 1:] = False
        window[halo] = BAND_HALO
        window[body] = BAND_INVERT
        bands.append(ReverseBand(x, y + first, x + bw, y + last + 1, dark_share))
    bands.sort(key=lambda b: (b.y0, b.x0))
    return bands, mask


def invert_reverse_bands(image: NDArray[Any], dpi: int = 300,
                         **criteria: Any) -> tuple[NDArray[np.uint8], list[ReverseBand]]:
    """Turn every white-on-black band into black-on-white.

    The rest of the page is left untouched.  Returns ``(image, bands)``; when
    no band is found the very array that was passed in comes back, so
    ``out is image`` says "nothing happened".

    Only the band's own pixels are inverted — not its bounding box — so a
    caption flush under the band stays black on white.  The scanner's fringe
    along the band and the two pixels of anti-aliased edge around it are set
    to paper, so that no strip of noise and no frame survives for a
    recogniser to read as a line or an underline.
    """
    gray = to_gray(image)
    bands, mask = find_reverse_bands(gray, dpi, **criteria)
    if not bands:
        return gray, []
    out = gray.copy()
    inside = mask == BAND_INVERT
    out[inside] = 255 - gray[inside]
    body = inside.astype(np.uint8)
    rim = cv2.dilate(body, np.ones((5, 5), dtype=np.uint8)).astype(bool) & ~inside
    out[rim | (mask == BAND_HALO)] = 255
    return out, bands


class ReverseVideo(_StepBase):
    """Invert the bands of white text on black so the engines read them.

    Measured on the Yusupov *Build Up Your Chess* solutions page 19 (200 DPI
    render): every exercise header ("E.Jackson – D.Baird") sits on a black
    band, and the book's own text layer carries "E. ackson" for it.  A
    recogniser trained on black-on-white treats the band as a picture or
    reads its edge as a line of noise; inverting just the band gives it the
    header as ordinary text, and the rest of the page — including the line
    flush under the band — is not touched.

    Photometric, so it runs before any geometry step and before binarisation;
    after shadow removal, because a gutter shadow on an unflattened page is a
    dark region too and the aspect test is all that keeps it apart.
    """

    name = "reverse_video"

    def __init__(self, enabled: bool = True, *,
                 min_width_inches: float = 0.6,
                 min_height_inches: float = 0.06,
                 max_height_inches: float = 0.75,
                 min_aspect: float = 2.5,
                 min_dark_share: float = 0.55) -> None:
        super().__init__(enabled)
        self.min_width_inches = min_width_inches
        self.min_height_inches = min_height_inches
        self.max_height_inches = max_height_inches
        self.min_aspect = min_aspect
        self.min_dark_share = min_dark_share

    def criteria(self) -> dict[str, float]:
        return {
            "min_width_inches": self.min_width_inches,
            "min_height_inches": self.min_height_inches,
            "max_height_inches": self.max_height_inches,
            "min_aspect": self.min_aspect,
            "min_dark_share": self.min_dark_share,
        }

    def find(self, image: Image, dpi: int = 300) -> list[ReverseBand]:
        return find_reverse_bands(image, dpi, **self.criteria())[0]

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        gray = to_gray(image)
        out, bands = invert_reverse_bands(gray, ctx.dpi, **self.criteria())
        detail: dict[str, Any] = {
            "bands": tuple(b.as_tuple() for b in bands),
            "band_count": len(bands),
            "dark_shares": tuple(round(b.dark_share, 3) for b in bands),
        }
        if not bands:
            return gray, "nenhuma faixa de texto claro sobre fundo escuro", detail
        inverted = int(sum(b.width * b.height for b in bands))
        detail["inverted_pixels"] = inverted
        return (out,
                f"{len(bands)} faixa(s) de texto claro sobre fundo escuro "
                f"invertida(s) ({inverted / gray.size:.2%} da página)", detail)


# --------------------------------------------------------------------------- #
# Binarisation
# --------------------------------------------------------------------------- #


#: Ink fraction a page of text can plausibly have.
#:
#: Origem: ChessVisionOFF_Puro/src/chess_diagram_ocr/text/binarizacao.py
#: (``TINTA_PLAUSIVEL``, ``tinta_plausivel``).  Absorvido em 2026-09-07.
#: Alterações: the trunk uses it to choose between Otsu and adaptive up front;
#: here it is a *post-hoc* guard applied to whatever method was configured,
#: because our default is Sauvola and Sauvola has its own failure mode the
#: trunk never meets — on a region with almost no ink the local standard
#: deviation collapses, the threshold surface sits just under the paper level,
#: and the whole region turns black.  The trunk's measured lesson holds either
#: way: the cheapest reliable detector of a binarisation that went wrong is the
#: ink fraction of its own output, not the shape of the input histogram.
PLAUSIBLE_INK = (0.0005, 0.35)

#: Order tried when the configured method produces an implausible page.  Otsu
#: first because a global threshold cannot produce a locally-flooded region,
#: which is the failure being escaped.
_BINARIZE_FALLBACKS = ("otsu", "adaptive_gaussian", "sauvola")


class Binarize(_StepBase):
    """Reduce to two levels — ink 0, paper 255.

    Sauvola is the default because a scanned book page is almost never evenly
    lit, and a global threshold on an unevenly lit page either loses the light
    half or floods the dark half.  ``otsu`` and ``adaptive_gaussian`` are
    offered for comparison and for the pathological pages where the local
    method oscillates.

    Whichever method is chosen, the result is checked against
    :data:`PLAUSIBLE_INK` and another method is tried if it fails.  A page that
    comes out 60 % black is not a hard page, it is a broken binarisation, and
    passing it to an OCR engine wastes a second and returns nothing.
    """

    name = "binarize"

    def __init__(self, enabled: bool = True, *, method: str = "sauvola",
                 window: int | None = None, k: float = 0.2,
                 r: float = 128.0, guard: bool = True) -> None:
        super().__init__(enabled)
        if method not in ("sauvola", "otsu", "adaptive_gaussian"):
            raise ValueError(f"método de binarização desconhecido: {method}")
        self.method = method
        #: ``None`` derives the window from the DPI: roughly 2 mm, which is a
        #: little wider than a body-text stroke at any normal scan resolution.
        self.window = window
        self.k = k
        self.r = r
        #: Switch off to measure one method honestly, without the ladder.
        self.guard = guard

    def window_for(self, dpi: int) -> int:
        if self.window is not None:
            return _odd(self.window)
        return _odd(max(15, dpi / 12.0), 15)

    @staticmethod
    def ink_fraction(binary: Image) -> float:
        return float((binary == 0).mean()) if binary.size else 0.0

    @classmethod
    def plausible_ink(cls, binary: Image) -> bool:
        lo, hi = PLAUSIBLE_INK
        return lo <= cls.ink_fraction(binary) <= hi

    def _binarize_with(self, gray: Image, method: str, dpi: int) -> Image:
        if method == "otsu":
            threshold = otsu_threshold(gray)
            return np.where(gray <= threshold, 0, 255).astype(np.uint8)
        if method == "adaptive_gaussian":
            window = self.window_for(dpi)
            return cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, window, 10)
        window = self.window_for(dpi)
        surface = sauvola_threshold(gray, window=window, k=self.k, r=self.r)
        return np.where(gray.astype(np.float64) <= surface, 0, 255).astype(np.uint8)

    def binarize(self, image: Image, dpi: int = 300) -> Image:
        """Binarise, escaping to another method if the result is implausible."""
        return self.binarize_reported(image, dpi)[0]

    def binarize_reported(self, image: Image,
                          dpi: int = 300) -> tuple[Image, str, list[str]]:
        """As :meth:`binarize`, but also returns the method used and the ladder.

        The ladder is returned rather than logged because "which binarisation
        actually ran on page 412" is the first question asked when a page reads
        badly, and it must be answerable from the report the batch already
        keeps.
        """
        gray = to_gray(image)
        out = self._binarize_with(gray, self.method, dpi)
        tried = [self.method]
        if not self.guard or self.plausible_ink(out):
            return out, self.method, tried
        for candidate in _BINARIZE_FALLBACKS:
            if candidate in tried:
                continue
            tried.append(candidate)
            alternative = self._binarize_with(gray, candidate, dpi)
            if self.plausible_ink(alternative):
                return alternative, candidate, tried
        # Nothing was plausible.  Keep the configured method's output: an
        # arbitrary fallback is not more likely to be right, and switching
        # silently would hide the fact that this page is genuinely odd.
        return out, self.method, tried

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        gray = to_gray(image)
        out, used, tried = self.binarize_reported(gray, ctx.dpi)
        ink_fraction = self.ink_fraction(out)
        ctx.is_binary = True
        ctx.background = 255
        detail: dict[str, Any] = {
            "method": used,
            "method_configured": self.method,
            "methods_tried": tuple(tried),
            "window": self.window_for(ctx.dpi) if used != "otsu" else None,
            "k": self.k if used == "sauvola" else None,
            "ink_fraction": round(ink_fraction, 5),
            "ink_plausible": self.plausible_ink(out),
        }
        if used == "otsu":
            detail["threshold"] = otsu_threshold(gray)
        message = (f"binarizada por {used}; {ink_fraction:.1%} da página "
                   f"ficou como tinta")
        if used != self.method:
            message += (f" (o método configurado, {self.method}, produziu uma "
                        f"fração de tinta implausível e foi trocado)")
            ctx.notes.append(
                f"binarização: {self.method} falhou nesta página, "
                f"{used} foi usado no lugar")
        elif not detail["ink_plausible"]:
            message += (" — fração implausível, e nenhum método alternativo "
                        "melhorou; a página é atípica")
            ctx.notes.append(
                "binarização: nenhum método produziu uma fração de tinta "
                "plausível nesta página")
        return out, message, detail


# --------------------------------------------------------------------------- #
# Despeckle
# --------------------------------------------------------------------------- #


class Despeckle(_StepBase):
    """Delete isolated specks without eating thin strokes.

    The rule is a conjunction, and the conjunction is the whole point: a
    component is removed only when it is **both** small in area **and** small in
    every dimension.  Area alone would delete the stem of an "l" and the bar of
    a "t"; a 1 px by 40 px stroke has an area of 40, less than many specks, but
    an extent of 40 and so survives.  Dimension alone would keep every dense
    blob of dirt.
    """

    name = "despeckle"

    def __init__(self, enabled: bool = True, *,
                 max_area_inches2: float = 0.00009,
                 max_extent_inches: float = 0.011,
                 connectivity: int = 8) -> None:
        super().__init__(enabled)
        #: ~8 px^2 at 300 DPI.
        self.max_area_inches2 = max_area_inches2
        #: ~3.3 px at 300 DPI — narrower than any printed stroke.
        self.max_extent_inches = max_extent_inches
        self.connectivity = connectivity

    def limits_for(self, dpi: int) -> tuple[int, int]:
        area = max(2, int(round(self.max_area_inches2 * dpi * dpi)))
        extent = max(2, int(round(self.max_extent_inches * dpi)))
        return area, extent

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        gray = to_gray(image)
        if not ctx.is_binary:
            binary = np.where(gray <= otsu_threshold(gray), 0, 255).astype(np.uint8)
        else:
            binary = gray
        max_area, max_extent = self.limits_for(ctx.dpi)

        ink = (binary == 0).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            ink, connectivity=self.connectivity)

        detail: dict[str, Any] = {
            "components": int(count - 1),
            "max_area": max_area,
            "max_extent": max_extent,
        }
        if count <= 1:
            return binary, "nenhum componente de tinta para analisar", detail

        areas = stats[1:, cv2.CC_STAT_AREA]
        widths = stats[1:, cv2.CC_STAT_WIDTH]
        heights = stats[1:, cv2.CC_STAT_HEIGHT]
        extents = np.maximum(widths, heights)
        doomed = (areas <= max_area) & (extents <= max_extent)

        removed = int(doomed.sum())
        detail["removed_components"] = removed
        detail["removed_pixels"] = int(areas[doomed].sum())
        if removed == 0:
            return binary, "nenhum ponto isolado a remover", detail

        doomed_labels = np.flatnonzero(doomed) + 1
        lookup = np.zeros(count, dtype=bool)
        lookup[doomed_labels] = True
        out = binary.copy()
        out[lookup[labels]] = 255
        return (out,
                f"{removed} ponto(s) isolado(s) removido(s) de "
                f"{count - 1} componente(s)", detail)


# --------------------------------------------------------------------------- #
# Dewarp
# --------------------------------------------------------------------------- #


class Dewarp(_StepBase):
    """Straighten vertical page curl in a photograph of an open book.

    Scope, stated plainly: this corrects the *vertical* displacement field, the
    one that makes text lines bow near the spine.  It does not correct
    perspective and it does not correct horizontal compression, both of which
    need the page outline and a camera model.  Within its scope it is a real
    correction, not a cosmetic one.

    Method: close the binarised page horizontally so each text line becomes one
    long blob, take the vertical centre of each blob column by column, fit a
    low-order polynomial to each line, average the fits (after removing each
    line's own offset) into a single displacement field, and remap.  Averaging
    across lines is what makes it robust: an individual line may be short, may
    be a heading, or may be interrupted by a diagram, but the curl is a
    property of the page and every line carries a noisy sample of it.
    """

    name = "dewarp"

    def __init__(self, enabled: bool = False, *, degree: int = 2,
                 min_lines: int = 4, min_amplitude_px: float = 3.0,
                 min_consistency: float = 2.0,
                 close_inches: float = 0.25) -> None:
        super().__init__(enabled)
        self.degree = degree
        self.min_lines = min_lines
        #: Below this the curl is noise and remapping only blurs the page.
        self.min_amplitude_px = min_amplitude_px
        #: Amplitude of the agreed field divided by the disagreement between
        #: lines.  Measured on a 21-line synthetic page: flat scores 1.43
        #: (amplitude 9.0 px against a between-line spread of 6.3 px), the same
        #: page bowed by 14 px scores 6.92 (40.7 px against 5.9 px).  2.0 sits
        #: in that gap with room on both sides.  Without this test the flat
        #: page of ragged-right prose reports 9 px of curl — three times
        #: ``min_amplitude_px`` — and gets remapped for nothing.
        self.min_consistency = min_consistency
        self.close_inches = close_inches

    def line_curves(self, image: Image,
                    dpi: int = 300) -> list[tuple[NDArray[np.int64],
                                                  NDArray[np.float64]]]:
        """Per text line, the columns it covers and its vertical centre there."""
        gray = to_gray(image)
        binary = np.where(gray <= otsu_threshold(gray), 255, 0).astype(np.uint8)
        width = _odd(self.close_inches * dpi, 9)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width, 1))
        merged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        count, labels, stats, _ = cv2.connectedComponentsWithStats(merged, 8)
        curves: list[tuple[NDArray[np.int64], NDArray[np.float64]]] = []
        min_width = max(20, int(0.25 * gray.shape[1]))
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_WIDTH] < min_width:
                continue
            if stats[label, cv2.CC_STAT_HEIGHT] > 0.2 * gray.shape[0]:
                continue  # a diagram or a column rule, not a text line
            ys, xs = np.nonzero(labels == label)
            if xs.size < min_width:
                continue
            order = np.argsort(xs)
            xs, ys = xs[order], ys[order]
            unique_x, starts = np.unique(xs, return_index=True)
            sums = np.add.reduceat(ys.astype(np.float64), starts)
            counts = np.diff(np.append(starts, xs.size))
            curves.append((unique_x, sums / counts))
        return curves

    def displacement_field(self, image: Image,
                           dpi: int = 300) -> tuple[NDArray[np.float64] | None,
                                                    dict[str, Any]]:
        gray = to_gray(image)
        curves = self.line_curves(gray, dpi)
        detail: dict[str, Any] = {"lines_found": len(curves)}
        if len(curves) < self.min_lines:
            detail["reason"] = "linhas de texto insuficientes"
            return None, detail

        width = gray.shape[1]
        columns = np.arange(width, dtype=np.float64)
        fits: list[NDArray[np.float64]] = []
        for xs, ys in curves:
            if xs.size <= self.degree + 1:
                continue
            coeffs = np.polyfit(xs.astype(np.float64), ys, self.degree)
            curve = np.polyval(coeffs, columns)
            # Remove the line's own vertical position; only its shape carries
            # information about the curl.
            fits.append(curve - curve.mean())
        detail["lines_fitted"] = len(fits)
        if len(fits) < self.min_lines:
            detail["reason"] = "ajustes insuficientes"
            return None, detail

        stack = np.vstack(fits)
        field = np.median(stack, axis=0)
        field -= field.mean()
        amplitude = float(field.max() - field.min())
        detail["amplitude_px"] = round(amplitude, 3)

        # Amplitude alone does not distinguish a curl from noise, and the
        # measurement that showed it: a *flat* synthetic page of 21 lines
        # reports 9.0 px of "curl", against 40.7 px for the same page bowed by
        # 14 px.  A threshold between those two numbers would be a constant
        # fitted to one page.
        #
        # The real difference is that a curl is the *same shape* on every line
        # while the wobble of a line's ink centroid is not — ragged line ends
        # and varying ascender/descender content move each line differently.
        # So compare the agreed signal against the disagreement: the spread of
        # the individual fits around the median, at the same columns.
        spread = float(np.median(np.percentile(stack, 75.0, axis=0)
                                 - np.percentile(stack, 25.0, axis=0)))
        detail["line_spread_px"] = round(spread, 3)
        detail["consistency"] = round(amplitude / spread, 3) if spread > 0 else None
        return field, detail

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        field, detail = self.displacement_field(image, ctx.dpi)
        if field is None:
            return image, f"não aplicado: {detail.get('reason', 'sem dados')}", detail
        amplitude = float(detail.get("amplitude_px", 0.0))
        if amplitude < self.min_amplitude_px:
            detail["skipped"] = True
            return (image,
                    f"curvatura de {amplitude:.1f} px está abaixo do limite; "
                    f"nada a corrigir", detail)
        consistency = detail.get("consistency")
        if consistency is not None and consistency < self.min_consistency:
            detail["skipped"] = True
            return (image,
                    f"as linhas discordam demais sobre a curvatura "
                    f"(amplitude {amplitude:.1f} px contra dispersão de "
                    f"{detail['line_spread_px']:.1f} px entre linhas); isto é "
                    f"ruído de composição, não curvatura da página",
                    detail)

        h, w = image.shape[:2]
        map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
        map_y = (np.tile(np.arange(h, dtype=np.float32).reshape(-1, 1), (1, w))
                 + field.astype(np.float32)[None, :])
        out = cv2.remap(image, map_x, map_y, interpolation=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=int(ctx.background))
        residual, residual_detail = self.displacement_field(out, ctx.dpi)
        detail["residual_amplitude_px"] = (
            residual_detail.get("amplitude_px") if residual is not None else None)
        return (out,
                f"curvatura vertical de {amplitude:.1f} px corrigida a partir de "
                f"{detail.get('lines_fitted')} linha(s)", detail)


# --------------------------------------------------------------------------- #
# Upscaling
# --------------------------------------------------------------------------- #


class Upscale(_StepBase):
    """Resample a low-resolution page up to something Tesseract can read.

    Tesseract's LSTM wants roughly 30 px of x-height; below about 200 DPI a
    body-text page does not provide it and the error rate rises sharply.  Plain
    bicubic plus a mild unsharp mask recovers most of that — not because it
    invents detail, but because the recogniser's own normalisation works better
    from a larger, smoother input than from a small aliased one.

    This is the interpolation fallback.  SPEC §7.2 also allows a learned
    super-resolution model; that belongs behind the ONNX worker of ADR-0003 and
    is deliberately not wired here, where the rule is CPU-only and correct.
    """

    name = "upscale"

    def __init__(self, enabled: bool = True, *, min_dpi: int = 200,
                 target_dpi: int = 300, max_scale: float = 4.0,
                 unsharp_amount: float = 0.6) -> None:
        super().__init__(enabled)
        self.min_dpi = min_dpi
        self.target_dpi = target_dpi
        self.max_scale = max_scale
        self.unsharp_amount = unsharp_amount

    def _run(self, image: Image,
             ctx: PreprocessContext) -> tuple[Image, str, dict[str, Any]]:
        detail: dict[str, Any] = {"dpi_in": ctx.dpi, "min_dpi": self.min_dpi}
        if ctx.dpi >= self.min_dpi:
            return (image,
                    f"resolução de {ctx.dpi} DPI é suficiente; sem ampliação",
                    detail)
        scale = min(self.max_scale, self.target_dpi / max(1, ctx.dpi))
        if scale <= 1.01:
            return image, "fator de ampliação desprezível", detail

        out = cv2.resize(image, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_CUBIC)
        if self.unsharp_amount > 0:
            blurred = cv2.GaussianBlur(out, (0, 0), sigmaX=1.0)
            out = cv2.addWeighted(out, 1.0 + self.unsharp_amount,
                                  blurred, -self.unsharp_amount, 0)
        effective = int(round(ctx.dpi * scale))
        detail.update({"scale": round(scale, 4), "dpi_out": effective,
                       "unsharp": self.unsharp_amount})
        ctx.dpi = effective
        return (out,
                f"ampliada {scale:.2f}x, de {detail['dpi_in']} para "
                f"{effective} DPI", detail)


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #


class PreprocessPipeline:
    """An ordered list of steps, run in sequence with a report each."""

    def __init__(self, steps: Sequence[PreprocessStep]) -> None:
        self.steps: list[PreprocessStep] = list(steps)

    def __iter__(self):
        return iter(self.steps)

    def step(self, name: str) -> PreprocessStep | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def enable(self, name: str, enabled: bool = True) -> "PreprocessPipeline":
        step = self.step(name)
        if step is None:
            raise KeyError(f"etapa desconhecida: {name}")
        step.enabled = enabled
        return self

    def only(self, *names: str) -> "PreprocessPipeline":
        """Switch every step off except the named ones — the debugging tool for
        "which step ruined this page?"."""
        wanted = set(names)
        for step in self.steps:
            step.enabled = step.name in wanted
        return self

    def run(self, image: NDArray[Any],
            ctx: PreprocessContext | None = None) -> PreprocessOutcome:
        ctx = ctx or PreprocessContext()
        current = to_gray(image)
        reports: list[StepReport] = []
        started = time.perf_counter()
        for step in self.steps:
            current, report = step.apply(current, ctx)
            reports.append(report)
        return PreprocessOutcome(
            image=current,
            reports=tuple(reports),
            context=ctx,
            total_duration_s=time.perf_counter() - started,
        )


def default_pipeline(*, dewarp: bool = False,
                     binarize_method: str = "sauvola") -> PreprocessPipeline:
    """The order argued for in this module's docstring.

    ``dewarp`` is off by default because it is only right for photographs; on a
    flatbed scan it finds a curl that is not there and remaps the page for
    nothing.  The caller — or the UI — turns it on for camera input.
    """
    return PreprocessPipeline([
        Upscale(),
        ShadowRemoval(),
        BleedThroughReduction(),
        ReverseVideo(),
        Deskew(),
        Dewarp(enabled=dewarp),
        Binarize(method=binarize_method),
        Despeckle(),
    ])
