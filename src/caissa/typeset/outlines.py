"""Glyph outline extraction: font contours in, deterministic SVG path data out.

Origem: conceito derivado de Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/renderer.py
Absorvido em 2026-09-07. Alteracoes: o renderer original desenhava o glifo como *texto*
(``page.insert_text`` com a fonte embutida). Aqui o contorno e extraido e emitido como
``<path>``, pelas razoes registradas em ``PIECE ARTWORK`` abaixo.

Why extract outlines instead of setting text
--------------------------------------------
The legacy renderer set the piece as a character in an embedded font. That works for a
single PDF, but it fails every other target:

* SVG/EPUB/HTML consumers need the font present, and the legacy chess fonts carry a
  symbol-only ``(3, 0)`` cmap that browsers will not map from ASCII.
* The square background is baked into the dark-square glyph as a hatch pattern, so the
  board theme could never change.
* Text is not deterministic across font-cache states; path data is.

Extracting the contour gives one artwork model that every backend can draw, keeps the
piece a true vector at any zoom, and makes the square colour ours to choose.

PIECE ARTWORK
-------------
A legacy chess font stores, for each piece, a *light-square* glyph and a *dark-square*
glyph. Only the light-square glyph is used here: it is the bare piece, with no square
background. It has the shape a publisher wants, and drawing it takes two layers:

1. ``outer`` -- the outermost contours only, filled with the piece's *body* colour.
2. ``full``  -- every contour, non-zero winding, filled with the piece's *ink* colour.

For a white piece the body reads light and the counters become the outline. For a black
piece the body is covered by the solid ink and the counters (a knight's eye, the slit in
a bishop's mitre) show the body colour through. One algorithm, both colours, correct on
any square tint -- which is exactly why the board theme can then be anything.
"""

from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

__all__ = [
    "Contour",
    "Outline",
    "PathBuilder",
    "format_number",
    "outline_from_pen",
]

# Coordinates are rounded to this many decimals before they reach a path string.
# Determinism requirement: the same FEN and style must give byte-identical SVG, so
# every float that reaches the output goes through `format_number`.
_DECIMALS = 3


def format_number(value: float) -> str:
    """Round to a fixed precision and strip trailing zeros, deterministically.

    ``-0`` is normalised to ``0`` so that sign-of-zero differences between platforms
    cannot change the output bytes.
    """
    rounded = round(float(value) + 0.0, _DECIMALS)
    if rounded == 0:
        rounded = 0.0
    text = f"{rounded:.{_DECIMALS}f}".rstrip("0").rstrip(".")
    return text if text and text != "-" else "0"


@dataclass(frozen=True)
class Contour:
    """One closed subpath in font units.

    ``segments`` holds ``("L", x, y)`` and ``("C", x1, y1, x2, y2, x, y)`` tuples that
    follow ``start``. Quadratics are converted to cubics on the way in, so consumers
    only ever have to handle two segment kinds.
    """

    start: tuple[float, float]
    segments: tuple[tuple, ...]

    def points(self) -> list[tuple[float, float]]:
        """Every on-curve and control point, for bounding-box and area work."""
        out = [self.start]
        for seg in self.segments:
            kind = seg[0]
            if kind == "L":
                out.append((seg[1], seg[2]))
            else:
                out.extend([(seg[1], seg[2]), (seg[3], seg[4]), (seg[5], seg[6])])
        return out

    def bbox(self) -> tuple[float, float, float, float]:
        pts = self.points()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def flatten(self, steps: int = 24) -> list[tuple[float, float]]:
        """The contour as a closed polygon, curves sampled at ``steps`` points each.

        `points` returns control points too, which overstates a curve's length by a few
        percent and understates the area it encloses. Anything that measures the drawing
        rather than its box needs the flattened form.
        """
        out: list[tuple[float, float]] = [self.start]
        px, py = self.start
        for seg in self.segments:
            if seg[0] == "L":
                out.append((seg[1], seg[2]))
                px, py = seg[1], seg[2]
                continue
            x1, y1, x2, y2, x3, y3 = seg[1:7]
            ax, ay = px, py
            for i in range(1, steps + 1):
                t = i / steps
                u = 1.0 - t
                out.append((
                    u * u * u * ax + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
                    u * u * u * ay + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3,
                ))
            px, py = x3, y3
        return out

    def perimeter(self, steps: int = 24) -> float:
        """Length of the closed contour, in font units."""
        pts = self.flatten(steps)
        total = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            total += math.hypot(x1 - x0, y1 - y0)
        return total

    def area(self, steps: int = 24) -> float:
        """Unsigned area enclosed by the flattened contour, in font units squared."""
        pts = self.flatten(steps)
        total = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            total += x0 * y1 - x1 * y0
        return abs(total) / 2.0

    def signed_area(self) -> float:
        """Shoelace area over the on-curve polygon. Sign gives the winding direction."""
        pts = [self.start]
        for seg in self.segments:
            pts.append((seg[1], seg[2]) if seg[0] == "L" else (seg[5], seg[6]))
        total = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            total += x0 * y1 - x1 * y0
        return total / 2.0


@dataclass(frozen=True)
class Outline:
    """A glyph as a set of closed contours, in font units, y-up."""

    contours: tuple[Contour, ...]
    advance: float
    units_per_em: float

    def is_empty(self) -> bool:
        return not self.contours

    def bbox(self) -> tuple[float, float, float, float]:
        if not self.contours:
            return (0.0, 0.0, 0.0, 0.0)
        boxes = [c.bbox() for c in self.contours]
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )

    def outer_contours(self) -> tuple[Contour, ...]:
        """Contours that no other contour encloses.

        Containment is decided by bounding box. A counter (the hole in a white rook, the
        eye of a knight) always sits strictly inside its parent's box, while genuinely
        separate parts of a piece -- the loose balls of a crown, a king's cross clear of
        the mitre -- do not, so they are correctly kept.
        """
        boxes = [c.bbox() for c in self.contours]
        keep: list[Contour] = []
        for i, contour in enumerate(self.contours):
            x0, y0, x1, y1 = boxes[i]
            enclosed = False
            for j, other in enumerate(boxes):
                if i == j:
                    continue
                ox0, oy0, ox1, oy1 = other
                # Strict containment, with a small tolerance so that coincident edges
                # (a counter that touches its parent's outline) still count as inside.
                tol = 1e-6
                if ox0 - tol <= x0 and oy0 - tol <= y0 and ox1 + tol >= x1 and oy1 + tol >= y1:
                    area_self = abs(x1 - x0) * abs(y1 - y0)
                    area_other = abs(ox1 - ox0) * abs(oy1 - oy0)
                    if area_other > area_self:
                        enclosed = True
                        break
            if not enclosed:
                keep.append(contour)
        return tuple(keep)

    def to_svg_path(
        self,
        *,
        scale: float,
        dx: float = 0.0,
        dy: float = 0.0,
        flip_y: bool = True,
        contours: Sequence[Contour] | None = None,
    ) -> str:
        """Serialise to SVG path data.

        Font space is y-up; SVG user space is y-down. ``flip_y`` negates y so the glyph
        arrives upright, and ``dx``/``dy`` place it after scaling.
        """
        src = self.contours if contours is None else tuple(contours)
        sy = -scale if flip_y else scale
        parts: list[str] = []
        for contour in src:
            x, y = contour.start
            parts.append(f"M{format_number(x * scale + dx)} {format_number(y * sy + dy)}")
            for seg in contour.segments:
                if seg[0] == "L":
                    parts.append(
                        f"L{format_number(seg[1] * scale + dx)} {format_number(seg[2] * sy + dy)}"
                    )
                else:
                    parts.append(
                        "C"
                        f"{format_number(seg[1] * scale + dx)} {format_number(seg[2] * sy + dy)} "
                        f"{format_number(seg[3] * scale + dx)} {format_number(seg[4] * sy + dy)} "
                        f"{format_number(seg[5] * scale + dx)} {format_number(seg[6] * sy + dy)}"
                    )
            parts.append("Z")
        return "".join(parts)


class PathBuilder:
    """A fontTools pen that records contours, converting quadratics to cubics."""

    def __init__(self) -> None:
        self.contours: list[Contour] = []
        self._start: tuple[float, float] | None = None
        self._current: tuple[float, float] = (0.0, 0.0)
        self._segments: list[tuple] = []

    # -- pen protocol -------------------------------------------------------
    def moveTo(self, pt: tuple[float, float]) -> None:  # noqa: N802 - pen protocol
        self._flush()
        self._start = (float(pt[0]), float(pt[1]))
        self._current = self._start
        self._segments = []

    def lineTo(self, pt: tuple[float, float]) -> None:  # noqa: N802
        p = (float(pt[0]), float(pt[1]))
        self._segments.append(("L", p[0], p[1]))
        self._current = p

    def curveTo(self, *points: tuple[float, float]) -> None:  # noqa: N802
        # A cubic arrives as two controls plus an endpoint. Higher-order forms are
        # legal in the pen protocol but do not occur in the fonts handled here; they
        # are reduced by treating the last point as the endpoint.
        pts = [(float(p[0]), float(p[1])) for p in points]
        if len(pts) == 1:
            self.lineTo(pts[0])
            return
        c1, c2, end = pts[0], pts[-2], pts[-1]
        self._segments.append(("C", c1[0], c1[1], c2[0], c2[1], end[0], end[1]))
        self._current = end

    def qCurveTo(self, *points: tuple[float, float]) -> None:  # noqa: N802
        """TrueType quadratics, including the implied on-curve midpoints."""
        pts = [None if p is None else (float(p[0]), float(p[1])) for p in points]
        if pts and pts[-1] is None:
            # A closed contour made entirely of off-curve points: synthesise the
            # implied start as the midpoint of the last and first controls.
            controls = [p for p in pts if p is not None]
            if not controls:
                return
            implied = (
                (controls[-1][0] + controls[0][0]) / 2.0,
                (controls[-1][1] + controls[0][1]) / 2.0,
            )
            if self._start is None:
                self._start = implied
                self._current = implied
            pts = controls + [implied]
        clean = [p for p in pts if p is not None]
        if not clean:
            return
        # Expand implied on-curve points between consecutive controls.
        for i in range(len(clean) - 1):
            ctrl = clean[i]
            nxt = clean[i + 1]
            end = nxt if i == len(clean) - 2 else ((ctrl[0] + nxt[0]) / 2.0, (ctrl[1] + nxt[1]) / 2.0)
            self._quad_to(ctrl, end)

    def _quad_to(self, ctrl: tuple[float, float], end: tuple[float, float]) -> None:
        """Exact quadratic-to-cubic elevation."""
        x0, y0 = self._current
        c1 = (x0 + 2.0 / 3.0 * (ctrl[0] - x0), y0 + 2.0 / 3.0 * (ctrl[1] - y0))
        c2 = (end[0] + 2.0 / 3.0 * (ctrl[0] - end[0]), end[1] + 2.0 / 3.0 * (ctrl[1] - end[1]))
        self._segments.append(("C", c1[0], c1[1], c2[0], c2[1], end[0], end[1]))
        self._current = end

    def closePath(self) -> None:  # noqa: N802
        self._flush()

    def endPath(self) -> None:  # noqa: N802
        self._flush()

    def addComponent(self, glyphName: str, transformation) -> None:  # noqa: N802, ANN001
        # Composite glyphs are decomposed by the caller through a DecomposingPen, so a
        # component reaching this pen means the glyph set could not resolve it. Ignore
        # rather than raise: a missing accent is better than a failed board.
        return

    def _flush(self) -> None:
        if self._start is not None and self._segments:
            self.contours.append(Contour(start=self._start, segments=tuple(self._segments)))
        self._start = None
        self._segments = []


def outline_from_pen(
    builder: PathBuilder,
    *,
    advance: float,
    units_per_em: float,
) -> Outline:
    builder._flush()
    return Outline(
        contours=tuple(builder.contours),
        advance=float(advance),
        units_per_em=float(units_per_em),
    )
