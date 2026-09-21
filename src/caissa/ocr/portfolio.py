"""The conditional preprocessing portfolio — Sol §SOL-3.

:mod:`caissa.ocr.preprocess` has every step a scanned page might need and,
until this module, nothing in production ran any of them: the importer
handed the raw render to the engines.  Turning the whole pipeline on for
every page would be the wrong fix.  Measured in F5, deskew of an already
level page costs a bicubic resample for nothing, Sauvola on a clean 300 DPI
render loses the thin strokes it exists to protect, and every step is time.

So the portfolio is *conditional*.  The page is measured once — skew,
illumination, show-through, noise, resolution, curl — and only the variants
those signals justify are built, each named by what it did and carrying the
parameters that did it.  **The original is always a candidate**: whatever
the variants do, the arbiter compares them against the untouched page and
a clean page cannot be made worse by a step it never needed (Sol §SOL-3,
"nenhuma variante piora significativamente o estrato limpo").

Every variant knows how to map a box from its own pixel space back to the
original render, because the IR's provenance, the review crop and the ink
check all live in the original's coordinates.  Upscale is a scale, deskew
an affine, dewarp a vertical displacement field; the inverse is applied in
reverse order.  Getting this wrong gives text that is right and boxes that
are silently off the page, which no string comparison catches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from .preprocess import (
    Binarize,
    BleedThroughReduction,
    Deskew,
    Despeckle,
    Dewarp,
    PreprocessContext,
    ShadowRemoval,
    StepReport,
    Upscale,
    estimate_skew_angle,
    otsu_threshold,
    to_gray,
)
from .types import BBox, OcrChar, OcrLine, OcrResult, OcrWord

__all__ = [
    "PageSignals",
    "Portfolio",
    "PortfolioConfig",
    "Variant",
    "VariantGeometry",
    "build_portfolio",
    "detect_signals",
]

Image = NDArray[np.uint8]


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PageSignals:
    """What was measured on the page before deciding anything."""

    dpi: int
    skew_deg: float
    shadow_spread: float
    bleed_share: float
    noise_sigma: float
    xheight_px: float
    curl_amplitude_px: float
    curl_consistency: float | None
    ink_fraction: float
    contrast: float
    is_binary: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "dpi": self.dpi,
            "skew_deg": round(self.skew_deg, 3),
            "shadow_spread": round(self.shadow_spread, 1),
            "bleed_share": round(self.bleed_share, 5),
            "noise_sigma": round(self.noise_sigma, 2),
            "xheight_px": round(self.xheight_px, 1),
            "curl_amplitude_px": round(self.curl_amplitude_px, 2),
            "curl_consistency": (round(self.curl_consistency, 2)
                                 if self.curl_consistency is not None else None),
            "ink_fraction": round(self.ink_fraction, 4),
            "contrast": round(self.contrast, 1),
            "is_binary": self.is_binary,
        }


def _xheight_px(gray: Image) -> float:
    """Median height of letter-sized connected components — an x-height proxy.

    Lowercase letters without ascenders are the most numerous components on
    a page of prose, so the median height of components that are neither
    specks nor lines lands on the x-height or just above it.
    """
    binary = (gray <= otsu_threshold(gray)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        return 0.0
    heights = stats[1:, cv2.CC_STAT_HEIGHT]
    widths = stats[1:, cv2.CC_STAT_WIDTH]
    h, w = gray.shape[:2]
    keep = (heights >= 4) & (heights <= 0.05 * h) & (widths <= 0.05 * w) & (widths >= 2)
    if keep.sum() < 20:
        return 0.0
    return float(np.median(heights[keep]))


def _noise_sigma(gray: Image) -> float:
    """Robust noise estimate over the paper.

    Residual after a 3×3 median filter, but only its *negative* half: paper
    near 255 clips the positive half of the noise, and the MAD of a clipped
    residual under-reads a sigma of 14 as 3.  The median of the absolute
    negative residuals is 0.674 σ for Gaussian noise whichever side is cut.
    """
    residual = gray.astype(np.float32) - cv2.medianBlur(gray, 3).astype(np.float32)
    # Paper only, and not the anti-aliased halo around strokes, whose grey
    # edge pixels read as a "noise" of ten levels on a perfectly clean page.
    ink = (gray <= otsu_threshold(gray)).astype(np.uint8)
    halo = cv2.dilate(ink, np.ones((5, 5), dtype=np.uint8)) > 0
    paper = (gray > (np.percentile(gray, 98) - 40)) & ~halo
    values = residual[paper]
    negative = -values[values < 0]
    if negative.size < 100:
        return 0.0
    return 1.4826 * float(np.median(negative))


def _bleed_share(gray: Image, dpi: int) -> float:
    step = BleedThroughReduction()
    ink_threshold = otsu_threshold(gray)
    band_hi = step.band_high(gray, ink_threshold)
    ink = gray <= ink_threshold
    suspicious = (gray > ink_threshold) & (gray <= band_hi)
    radius = max(1, int(round(step.dilate_inches * dpi)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    near_ink = cv2.dilate(ink.astype(np.uint8), kernel) > 0
    return float((suspicious & ~near_ink).mean())


def detect_signals(image: NDArray[Any], *, dpi: int = 300) -> PageSignals:
    """Measure the page once.  Pure: the image is not modified."""
    gray = to_gray(image)
    levels = np.unique(gray)
    is_binary = levels.size <= 2
    skew, _ = estimate_skew_angle(gray)
    shadow = ShadowRemoval()
    spread = shadow._spread(shadow.estimate_background(gray, dpi))  # noqa: SLF001
    threshold = otsu_threshold(gray)
    ink_fraction = float((gray <= threshold).mean())
    lo, hi = np.percentile(gray, [2.0, 98.0])
    curl_amp, curl_cons = 0.0, None
    if gray.shape[0] >= 200 and gray.shape[1] >= 200:
        field_, detail = Dewarp().displacement_field(gray, dpi)
        if field_ is not None:
            curl_amp = float(detail.get("amplitude_px", 0.0))
            curl_cons = detail.get("consistency")
    return PageSignals(
        dpi=int(dpi),
        skew_deg=float(skew),
        shadow_spread=float(spread),
        bleed_share=_bleed_share(gray, dpi) if not is_binary else 0.0,
        noise_sigma=_noise_sigma(gray) if not is_binary else 0.0,
        xheight_px=_xheight_px(gray),
        curl_amplitude_px=curl_amp,
        curl_consistency=curl_cons,
        ink_fraction=ink_fraction,
        contrast=float(hi - lo),
        is_binary=is_binary,
    )


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class VariantGeometry:
    """How to get from a variant's pixels back to the original's.

    Forward order is upscale → deskew → dewarp; :meth:`to_original` undoes
    them in reverse.  A variant that changed no geometry has the identity.
    """

    scale: float = 1.0
    #: The 2×3 affine deskew applied *after* the scale, or ``None``.
    affine: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None
    #: Vertical displacement per column of the (scaled, deskewed) image, or
    #: ``None``.  ``out(x, y) = in(x, y + field[x])``.
    field: tuple[float, ...] | None = None

    @property
    def is_identity(self) -> bool:
        return self.scale == 1.0 and self.affine is None and self.field is None

    def _inverse_affine(self) -> NDArray[np.float64] | None:
        if self.affine is None:
            return None
        matrix = np.array(self.affine, dtype=np.float64)
        return cv2.invertAffineTransform(matrix)

    def point_to_original(self, x: float, y: float) -> tuple[float, float]:
        if self.field is not None:
            column = min(len(self.field) - 1, max(0, int(round(x))))
            y = y + self.field[column]
        inverse = self._inverse_affine()
        if inverse is not None:
            x, y = (inverse[0, 0] * x + inverse[0, 1] * y + inverse[0, 2],
                    inverse[1, 0] * x + inverse[1, 1] * y + inverse[1, 2])
        return x / self.scale, y / self.scale

    def point_to_variant(self, x: float, y: float) -> tuple[float, float]:
        """Forward map: original pixel → variant pixel."""
        x, y = x * self.scale, y * self.scale
        if self.affine is not None:
            a, b = self.affine
            x, y = a[0] * x + a[1] * y + a[2], b[0] * x + b[1] * y + b[2]
        if self.field is not None:
            column = min(len(self.field) - 1, max(0, int(round(x))))
            y = y - self.field[column]
        return x, y

    def to_variant(self, box: BBox) -> BBox:
        if self.is_identity:
            return box
        corners = [self.point_to_variant(px, py)
                   for px, py in ((box.x0, box.y0), (box.x1, box.y0),
                                  (box.x0, box.y1), (box.x1, box.y1))]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return BBox.from_edges(min(xs), min(ys), max(xs), max(ys))

    def to_original(self, box: BBox) -> BBox:
        if self.is_identity:
            return box
        corners = [self.point_to_original(px, py)
                   for px, py in ((box.x0, box.y0), (box.x1, box.y0),
                                  (box.x0, box.y1), (box.x1, box.y1))]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return BBox.from_edges(min(xs), min(ys), max(xs), max(ys))


# --------------------------------------------------------------------------- #
# Variants
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Variant:
    """One candidate image for the engines, with its provenance."""

    name: str
    image: Image
    dpi: int
    geometry: VariantGeometry = field(default_factory=VariantGeometry)
    steps: tuple[StepReport, ...] = ()
    reasons_pt: tuple[str, ...] = ()
    cost_s: float = 0.0

    @property
    def is_original(self) -> bool:
        return self.name == "original"

    @property
    def applied_steps(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.steps if r.applied and r.changed)

    def parameters(self) -> dict[str, Any]:
        return {r.name: dict(r.detail) for r in self.steps if r.applied and r.changed}

    def map_result(self, result: OcrResult) -> OcrResult:
        """The result with every box in the *original* pixel space, and the
        variant recorded in its metadata."""
        geometry = self.geometry
        if not geometry.is_identity:
            lines = tuple(
                OcrLine(
                    words=tuple(
                        OcrWord(
                            text=w.text, box=geometry.to_original(w.box),
                            confidence=w.confidence,
                            chars=tuple(OcrChar(text=c.text, box=geometry.to_original(c.box),
                                                confidence=c.confidence,
                                                inherited_confidence=c.inherited_confidence)
                                        for c in w.chars),
                            block_index=w.block_index, paragraph_index=w.paragraph_index,
                            line_index=w.line_index, word_index=w.word_index)
                        for w in line.words),
                    box=geometry.to_original(line.box),
                    baseline=None if geometry.affine or geometry.field else line.baseline,
                    block_index=line.block_index, paragraph_index=line.paragraph_index,
                    line_index=line.line_index, kind=line.kind,
                    font_size=line.font_size / geometry.scale,
                )
                for line in result.lines
            )
            result = OcrResult(engine=result.engine, lang=result.lang, lines=lines,
                               region_kind=result.region_kind, duration_s=result.duration_s,
                               warnings=result.warnings, meta=result.meta)
        return result.with_meta(
            variant=self.name, variant_steps=self.applied_steps,
            variant_params=self.parameters(), variant_dpi=self.dpi)


@dataclass(frozen=True, slots=True)
class PortfolioConfig:
    """When each variant is justified.  Every number is a physical threshold
    the signal must cross; none is a weight."""

    #: Skew worth correcting, in degrees.  Deskew's own floor is 0.15°; the
    #: portfolio asks for more because a variant costs an engine run.
    min_skew_deg: float = 0.30
    #: Background spread (grey levels between the 5th and 95th percentile of
    #: the estimated illumination) that counts as a shadow.
    min_shadow_spread: float = 25.0
    #: Share of pixels judged show-through that justifies the bleed variant.
    min_bleed_share: float = 0.004
    #: Noise sigma (grey levels) beyond which binarising helps a recogniser.
    min_noise_sigma: float = 6.0
    #: Below this resolution, or this x-height, the upscale variant is built.
    low_dpi: int = 200
    min_xheight_px: float = 16.0
    #: Curl worth a dewarp.
    min_curl_amplitude_px: float = 3.0
    min_curl_consistency: float = 2.0
    #: Hard cap on variants beyond the original; the cheapest reasons win.
    max_variants: int = 3
    #: Mirror of the page for true bleed subtraction, when the caller has it.
    verso: Image | None = None


@dataclass(frozen=True, slots=True)
class Portfolio:
    variants: tuple[Variant, ...]
    signals: PageSignals
    notes: tuple[str, ...] = ()

    @property
    def original(self) -> Variant:
        return self.variants[0]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.variants)

    def describe_pt(self) -> str:
        lines = [f"Sinais: {self.signals.as_dict()}"]
        for variant in self.variants:
            why = "; ".join(variant.reasons_pt) or "sempre candidata"
            lines.append(f"  · {variant.name}: {why} "
                         f"[{', '.join(variant.applied_steps) or 'sem alteração'}] "
                         f"({variant.cost_s * 1000:.0f} ms)")
        for note in self.notes:
            lines.append(f"  ! {note}")
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "signals": self.signals.as_dict(),
            "variants": [
                {"name": v.name, "dpi": v.dpi, "steps": list(v.applied_steps),
                 "params": v.parameters(), "reasons": list(v.reasons_pt),
                 "cost_s": round(v.cost_s, 4)}
                for v in self.variants
            ],
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------- #
# Building
# --------------------------------------------------------------------------- #


def _run_steps(gray: Image, dpi: int, steps: Sequence[Any], *,
               verso: Image | None = None) -> tuple[Image, int, list[StepReport], VariantGeometry]:
    """Run ``steps`` in order, tracking the geometry each one changed."""
    ctx = PreprocessContext(dpi=dpi, verso=verso)
    current = gray
    reports: list[StepReport] = []
    scale = 1.0
    affine: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None
    field_: tuple[float, ...] | None = None
    for step in steps:
        before = current.shape[:2]
        before_image = current
        current, report = step.apply(current, ctx)
        reports.append(report)
        if not (report.applied and report.changed):
            continue
        if step.name == "upscale":
            scale *= float(report.detail.get("scale", 1.0))
        elif step.name == "deskew":
            angle = float(report.detail.get("applied_angle", 0.0))
            h, w = before
            matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
            cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
            new_w = int(math.ceil(h * sin + w * cos))
            new_h = int(math.ceil(h * cos + w * sin))
            matrix[0, 2] += (new_w - w) / 2.0
            matrix[1, 2] += (new_h - h) / 2.0
            affine = ((float(matrix[0, 0]), float(matrix[0, 1]), float(matrix[0, 2])),
                      (float(matrix[1, 0]), float(matrix[1, 1]), float(matrix[1, 2])))
        elif step.name == "dewarp":
            # The field the step applied is the one measured on its *input*
            # (measuring the output gives the residual).  ``Dewarp._run``
            # does not return it, and the measurement is deterministic, so
            # it is recomputed on the same image the step saw.
            recovered, _ = step.displacement_field(before_image, ctx.dpi)
            if recovered is not None:
                field_ = tuple(float(v) for v in recovered)
    return current, ctx.dpi, reports, VariantGeometry(scale=scale, affine=affine, field=field_)


def degradation_reasons(signals: PageSignals, *, dpi: int,
                        config: PortfolioConfig | None = None) -> tuple[str, ...]:
    """Why the page counts as degraded — the conditions of :func:`build_portfolio`.

    One name per variant the signals would justify (``upscale``,
    ``deskew_shadow``, ``bleed_sauvola``, ``dewarp``); empty for a clean page.
    OCR_UI_ROADMAP passo 1 keys the second engine on this: measured on the
    golden corpus, RapidOCR wins the degraded strata (fax, photo, shadow,
    150 DPI) and loses on clean scans and native pages, so it enters exactly
    where the portfolio enters.  Kept as one function so the route and the
    portfolio cannot drift apart; ``test_portfolio`` holds them together.
    """
    cfg = config or PortfolioConfig()
    reasons: list[str] = []
    if dpi < cfg.low_dpi or (0.0 < signals.xheight_px < cfg.min_xheight_px):
        reasons.append("upscale")
    if abs(signals.skew_deg) >= cfg.min_skew_deg or signals.shadow_spread >= cfg.min_shadow_spread:
        reasons.append("deskew_shadow")
    if (signals.bleed_share >= cfg.min_bleed_share
            or signals.noise_sigma >= cfg.min_noise_sigma) and not signals.is_binary:
        reasons.append("bleed_sauvola")
    if (signals.curl_amplitude_px >= cfg.min_curl_amplitude_px
            and signals.curl_consistency is not None
            and signals.curl_consistency >= cfg.min_curl_consistency):
        reasons.append("dewarp")
    return tuple(reasons)


def build_portfolio(image: NDArray[Any], *, dpi: int = 300,
                    config: PortfolioConfig | None = None,
                    signals: PageSignals | None = None) -> Portfolio:
    """The original plus every variant the signals justify."""
    import time

    cfg = config or PortfolioConfig()
    gray = to_gray(image)
    signals = signals or detect_signals(gray, dpi=dpi)
    notes: list[str] = []
    variants: list[Variant] = [Variant(name="original", image=gray, dpi=int(dpi))]
    plans: list[tuple[str, list[Any], list[str]]] = []

    # 4. Resolution first: a small page must be upscaled before any other
    #    step is measured on it, and it is the cheapest of the variants.
    if dpi < cfg.low_dpi or (0.0 < signals.xheight_px < cfg.min_xheight_px):
        reasons = []
        if dpi < cfg.low_dpi:
            reasons.append(f"resolução de {dpi} DPI abaixo de {cfg.low_dpi}")
        if 0.0 < signals.xheight_px < cfg.min_xheight_px:
            reasons.append(f"altura-x de {signals.xheight_px:.0f} px abaixo de "
                           f"{cfg.min_xheight_px:.0f}")
        target = max(300, int(round(dpi * 2))) if dpi < cfg.low_dpi else int(round(dpi * 1.5))
        plans.append(("upscale", [Upscale(min_dpi=max(cfg.low_dpi, dpi + 1),
                                          target_dpi=target, max_scale=2.0)], reasons))

    # 2. Deskew + shadow.
    if abs(signals.skew_deg) >= cfg.min_skew_deg or signals.shadow_spread >= cfg.min_shadow_spread:
        reasons = []
        if abs(signals.skew_deg) >= cfg.min_skew_deg:
            reasons.append(f"inclinação de {signals.skew_deg:+.2f}°")
        if signals.shadow_spread >= cfg.min_shadow_spread:
            reasons.append(f"sombra com variação de {signals.shadow_spread:.0f} níveis")
        plans.append(("deskew_shadow", [ShadowRemoval(), Deskew()], reasons))

    # 3. Bleed-through + Sauvola (+ despeckle) for show-through and noise.
    if (signals.bleed_share >= cfg.min_bleed_share
            or signals.noise_sigma >= cfg.min_noise_sigma) and not signals.is_binary:
        reasons = []
        if signals.bleed_share >= cfg.min_bleed_share:
            reasons.append(f"transparência do verso em {signals.bleed_share:.2%} dos pixels")
        if signals.noise_sigma >= cfg.min_noise_sigma:
            reasons.append(f"ruído com sigma {signals.noise_sigma:.1f}")
        steps: list[Any] = [BleedThroughReduction(), Binarize(method="sauvola"), Despeckle()]
        if abs(signals.skew_deg) >= cfg.min_skew_deg:
            steps.insert(0, Deskew())
        plans.append(("bleed_sauvola", steps, reasons))
        # OCR_UI_ROADMAP_C2 passo B8: with the real verso in hand the bleed
        # step is well posed (mirror, register, subtract) — but not better
        # on every page: measured on ``shadow_curl_bleed`` the registered
        # verso wins some pages and the heuristic others (the curl defeats a
        # global registration).  So the verso is one more variant, next to
        # the heuristic one, and the arbiter picks per region; it never
        # replaces the heuristic.
        if cfg.verso is not None and signals.bleed_share >= cfg.min_bleed_share:
            plans.append(("bleed_verso", list(steps),
                          ["verso registrado", *reasons]))

    # 5. Dewarp only when the geometry says curl.
    if (signals.curl_amplitude_px >= cfg.min_curl_amplitude_px
            and signals.curl_consistency is not None
            and signals.curl_consistency >= cfg.min_curl_consistency):
        plans.append(("dewarp", [ShadowRemoval(), Dewarp(enabled=True)],
                      [f"curvatura de {signals.curl_amplitude_px:.1f} px com consistência "
                       f"{signals.curl_consistency:.1f}"]))

    # A verso in hand is the page's own evidence: it earns one seat beyond
    # the cap rather than pushing the dewarp out.
    cap = cfg.max_variants + (1 if any(name == "bleed_verso" for name, _, _ in plans) else 0)
    if len(plans) > cap:
        dropped = [name for name, _, _ in plans[cap:]]
        notes.append(f"variantes além do teto de {cap} não construídas: "
                     f"{', '.join(dropped)}")
        plans = plans[:cap]

    for name, steps, reasons in plans:
        started = time.perf_counter()
        # Every plan that follows an upscale runs on the upscaled page, so
        # its geometry composes with the scale.
        base, base_dpi, base_reports, base_geometry = gray, int(dpi), [], VariantGeometry()
        # Only the ``bleed_verso`` plan sees the verso: ``bleed_sauvola``
        # stays the heuristic it was measured as.
        verso = cfg.verso if name == "bleed_verso" else None
        if name != "upscale" and plans and plans[0][0] == "upscale":
            base, base_dpi, base_reports, base_geometry = _run_steps(
                gray, int(dpi), plans[0][1], verso=verso)
        out, out_dpi, reports, geometry = _run_steps(base, base_dpi, steps, verso=verso)
        geometry = VariantGeometry(scale=geometry.scale * base_geometry.scale,
                                   affine=geometry.affine, field=geometry.field)
        variant = Variant(
            name=name, image=out, dpi=int(out_dpi), geometry=geometry,
            steps=tuple(base_reports + reports), reasons_pt=tuple(reasons),
            cost_s=time.perf_counter() - started,
        )
        if not variant.applied_steps:
            notes.append(f"variante {name} não alterou a página; descartada")
            continue
        variants.append(variant)

    return Portfolio(variants=tuple(variants), signals=signals, notes=tuple(notes))
