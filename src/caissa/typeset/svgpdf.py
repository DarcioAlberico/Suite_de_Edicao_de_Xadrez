"""Draw the SVG this package emits into a PDF page as true vector art.

Why this exists rather than a library
-------------------------------------
The obvious answer is CairoSVG, and the previous generation of this code used it. On
Windows it needs a native GTK runtime that is not present on the reference machine, so
``renderer.py`` silently fell back to a Pillow raster -- which is exactly how a chess
book ends up with diagrams that turn to mush at 400 %.

This module cannot render arbitrary SVG and does not try to. It renders *the* SVG that
``board_svg`` produces, whose vocabulary is a couple of hundred lines long and entirely
known: ``rect``, ``path`` with only ``M``/``L``/``C``/``Z``, ``line``, ``circle`` and
``text``. That is a small enough target to implement exactly, and the result is a PDF
whose diagrams are paths, not pixels.

Units
-----
``board_svg`` authors in millimetres. PDF is in points. One conversion constant, applied
once, at the boundary.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = ["MM_TO_PT", "SvgFragment", "parse_svg", "draw_svg", "svg_to_pdf_bytes", "svg_to_png"]

MM_TO_PT = 72.0 / 25.4

_SVG_NS = "{http://www.w3.org/2000/svg}"
_NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _tag(element: ET.Element) -> str:
    return element.tag.replace(_SVG_NS, "")


def _colour(value: str | None) -> tuple[float, float, float] | None:
    """``#rrggbb`` (or ``none``) to a PyMuPDF 0..1 triple."""
    if not value or value.strip().lower() in ("none", "transparent"):
        return None
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _f(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value.strip().replace("mm", "").replace("pt", "").replace("px", ""))
    except ValueError:
        return default


@dataclass
class SvgFragment:
    """A parsed board SVG: its intrinsic size in mm and its element list."""

    width_mm: float
    height_mm: float
    root: ET.Element

    @property
    def aspect(self) -> float:
        return self.height_mm / self.width_mm if self.width_mm else 1.0


def parse_svg(svg: str) -> SvgFragment:
    root = ET.fromstring(svg)
    view = root.get("viewBox")
    if view:
        nums = [float(n) for n in _NUM.findall(view)]
        width, height = (nums[2], nums[3]) if len(nums) >= 4 else (100.0, 100.0)
    else:
        width, height = _f(root.get("width"), 100.0), _f(root.get("height"), 100.0)
    return SvgFragment(width_mm=width, height_mm=height, root=root)


# --------------------------------------------------------------------------- #
# Path data
# --------------------------------------------------------------------------- #
_CMD = re.compile(r"([MLCZmlcz])([^MLCZmlcz]*)")


def _subpaths(d: str) -> list[list[tuple]]:
    """Split path data into subpaths of ``('L', x, y)`` / ``('C', ...)`` segments.

    Only the absolute commands ``board_svg`` emits are supported; anything else is
    skipped rather than guessed at, so a silent mis-draw is impossible.
    """
    out: list[list[tuple]] = []
    current: list[tuple] = []
    cx = cy = 0.0
    for match in _CMD.finditer(d):
        cmd = match.group(1)
        nums = [float(n) for n in _NUM.findall(match.group(2))]
        if cmd == "M":
            if current:
                out.append(current)
            current = []
            for i in range(0, len(nums) - 1, 2):
                x, y = nums[i], nums[i + 1]
                if i == 0:
                    current.append(("M", x, y))
                else:
                    current.append(("L", x, y))
                cx, cy = x, y
        elif cmd == "L":
            for i in range(0, len(nums) - 1, 2):
                cx, cy = nums[i], nums[i + 1]
                current.append(("L", cx, cy))
        elif cmd == "C":
            for i in range(0, len(nums) - 5, 6):
                x1, y1, x2, y2, x3, y3 = nums[i : i + 6]
                current.append(("C", x1, y1, x2, y2, x3, y3))
                cx, cy = x3, y3
        elif cmd in ("Z", "z"):
            if current:
                current.append(("Z",))
                out.append(current)
                current = []
    if current:
        out.append(current)
    return out


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #
_TRANSLATE = re.compile(r"translate\(\s*([-+0-9.eE]+)(?:[,\s]+([-+0-9.eE]+))?\s*\)")
_SCALE = re.compile(r"scale\(\s*([-+0-9.eE]+)(?:[,\s]+([-+0-9.eE]+))?\s*\)")


def _transform(value: str | None) -> tuple[float, float, float]:
    """Parse the ``translate``/``scale`` subset this writer emits and consumes.

    Deliberately narrow. Rotation and skew are *not* supported, and are not silently
    approximated either -- a page composer that needs them must say so, rather than
    discovering later that a rotated diagram came out upright. ``page_svg`` only ever
    emits translate and uniform scale.
    """
    if not value:
        return (0.0, 0.0, 1.0)
    dx = dy = 0.0
    s = 1.0
    m = _TRANSLATE.search(value)
    if m:
        dx = float(m.group(1))
        dy = float(m.group(2)) if m.group(2) is not None else 0.0
    m = _SCALE.search(value)
    if m:
        s = float(m.group(1))
    return (dx, dy, s)


def _walk(element, state):  # noqa: ANN001, ANN201
    """Yield ``(element, (tx, ty, scale))`` depth-first, composing nested transforms."""
    tx, ty, ts = state
    dx, dy, ds = _transform(element.get("transform"))
    here = (tx + dx * ts, ty + dy * ts, ts * ds)
    yield element, here
    for child in element:
        yield from _walk(child, here)


def draw_svg(
    page,  # noqa: ANN001 - pymupdf.Page
    svg: str | SvgFragment,
    *,
    origin: tuple[float, float] = (0.0, 0.0),
    width_pt: float | None = None,
    text_font: str = "helv",
    serif_font: str = "tiro",
    font_files: dict[str, str] | None = None,
) -> tuple[float, float]:
    """Draw a board SVG onto ``page`` at ``origin`` (points). Returns the size drawn.

    ``width_pt`` scales the whole fragment; without it the SVG's intrinsic millimetre
    size is used at 1 mm = 1 mm.

    ``font_files`` maps ``roman``/``bold``/``italic``/``bolditalic`` to TrueType paths.
    Supply it whenever the text carries anything outside WinAnsi -- which, for a chess
    book, is every en dash, curly quote and ellipsis on the page. See ``_draw_text``.
    """
    import pymupdf

    frag = svg if isinstance(svg, SvgFragment) else parse_svg(svg)
    natural_w = frag.width_mm * MM_TO_PT
    scale = (width_pt / natural_w) if width_pt else 1.0
    k = MM_TO_PT * scale
    ox, oy = origin

    for element, (tx, ty, ts) in _walk(frag.root, (0.0, 0.0, 1.0)):
        name = _tag(element)
        if name in ("svg", "g"):
            continue
        kk = k * ts

        def X(v: float, _tx=tx, _ts=ts) -> float:
            return ox + (_tx + v * _ts) * k

        def Y(v: float, _ty=ty, _ts=ts) -> float:
            return oy + (_ty + v * _ts) * k

        fill = _colour(element.get("fill"))
        stroke = _colour(element.get("stroke"))
        sw = _f(element.get("stroke-width"), 0.0) * kk
        opacity = _f(element.get("opacity"), 1.0)
        even_odd = element.get("fill-rule") == "evenodd"

        if name == "text":
            _draw_text(page, element, X, Y, kk, text_font, serif_font, opacity, font_files)
            continue

        shape = page.new_shape()
        drew = False

        if name == "rect":
            x, y = _f(element.get("x")), _f(element.get("y"))
            w, h = _f(element.get("width")), _f(element.get("height"))
            shape.draw_rect(pymupdf.Rect(X(x), Y(y), X(x + w), Y(y + h)))
            drew = True
        elif name == "line":
            shape.draw_line(
                pymupdf.Point(X(_f(element.get("x1"))), Y(_f(element.get("y1")))),
                pymupdf.Point(X(_f(element.get("x2"))), Y(_f(element.get("y2")))),
            )
            drew = True
        elif name == "circle":
            cx, cy, r = _f(element.get("cx")), _f(element.get("cy")), _f(element.get("r"))
            shape.draw_circle(pymupdf.Point(X(cx), Y(cy)), r * kk)
            drew = True
        elif name == "path":
            d = element.get("d") or ""
            for sub in _subpaths(d):
                if not sub:
                    continue
                start = sub[0]
                if start[0] != "M":
                    continue
                last = pymupdf.Point(X(start[1]), Y(start[2]))
                first = last
                for seg in sub[1:]:
                    if seg[0] == "L":
                        nxt = pymupdf.Point(X(seg[1]), Y(seg[2]))
                        shape.draw_line(last, nxt)
                        last = nxt
                    elif seg[0] == "C":
                        p1 = pymupdf.Point(X(seg[1]), Y(seg[2]))
                        p2 = pymupdf.Point(X(seg[3]), Y(seg[4]))
                        p3 = pymupdf.Point(X(seg[5]), Y(seg[6]))
                        shape.draw_bezier(last, p1, p2, p3)
                        last = p3
                    elif seg[0] == "Z":
                        if abs(last.x - first.x) > 1e-6 or abs(last.y - first.y) > 1e-6:
                            shape.draw_line(last, first)
                        last = first
                drew = True

        if drew:
            # `closePath` must be False for a path already closed explicitly, otherwise
            # MuPDF adds a second closing segment and the non-zero winding of a glyph
            # counter can flip.
            shape.finish(
                fill=fill,
                color=stroke,
                width=sw if stroke else 0,
                even_odd=even_odd,
                closePath=name in ("rect", "circle") or (name == "path" and fill is not None),
                fill_opacity=opacity,
                stroke_opacity=opacity,
            )
            shape.commit()

    return natural_w * scale, frag.height_mm * MM_TO_PT * scale


def _face_key(element) -> str:  # noqa: ANN001
    weight = element.get("font-weight") or ""
    bold = "bold" in weight or (weight.isdigit() and int(weight) >= 600)
    italic = (element.get("font-style") or "") == "italic"
    if bold and italic:
        return "bolditalic"
    if bold:
        return "bold"
    if italic:
        return "italic"
    return "roman"


def _draw_text(page, element, X, Y, k, text_font, serif_font, opacity, font_files=None) -> None:  # noqa: ANN001
    import pymupdf

    content = element.text or ""
    if not content.strip():
        return

    # `data-render-mode="invisible"` sets the run at PDF text render mode 3: it goes into
    # the text layer -- searchable, copyable, readable by a screen reader -- and paints
    # nothing. It is how a figurine drawn as a vector path still says `N`.
    render_mode = 3 if element.get("data-render-mode") == "invisible" else 0

    # --- embedded face --------------------------------------------------- #
    # The Base-14 serif cannot encode an en dash, a curly apostrophe or an ellipsis: it
    # silently substitutes U+00B7 and `get_text_length` returns a space's width for all
    # three. Every character `typography` exists to produce is therefore destroyed on the
    # way to the page unless a real Unicode face is embedded. When the caller supplies
    # one, use it for measuring *and* for setting, so the two cannot disagree.
    if font_files:
        key = _face_key(element)
        path = font_files.get(key) or font_files.get("roman")
        if path:
            size = _f(element.get("font-size"), 3.0) * k
            fill = _colour(element.get("fill")) or (0, 0, 0)
            alias = f"cai{abs(hash(path)) % 100000:05d}"
            measured = pymupdf.Font(fontfile=path)
            width = measured.text_length(content, fontsize=size)
            x, y = X(_f(element.get("x"))), Y(_f(element.get("y")))
            anchor = element.get("text-anchor", "start")
            if anchor == "middle":
                x -= width / 2.0
            elif anchor == "end":
                x -= width
            page.insert_text(
                pymupdf.Point(x, y),
                content,
                fontsize=size,
                fontname=alias,
                fontfile=path,
                color=fill,
                fill_opacity=opacity,
                render_mode=render_mode,
            )
            return

    content = content.strip()
    size = _f(element.get("font-size"), 3.0) * k
    fill = _colour(element.get("fill")) or (0, 0, 0)
    anchor = element.get("text-anchor", "start")
    family = (element.get("font-family") or "").lower()
    weight = element.get("font-weight") or ""
    italic = (element.get("font-style") or "") == "italic"

    if "mono" in family or "courier" in family:
        base = "cour"
    elif "serif" in family or "georgia" in family or "times" in family:
        base = "tiro" if serif_font == "tiro" else serif_font
    else:
        base = text_font
    if base == "tiro":
        fontname = {("", False): "tiro", ("bold", False): "tibo", ("", True): "tiit",
                    ("bold", True): "tibi"}.get((("bold" if "bold" in weight or weight.isdigit()
                    and int(weight) >= 600 else ""), italic), "tiro")
    elif base == "helv":
        fontname = {("", False): "helv", ("bold", False): "hebo", ("", True): "heit",
                    ("bold", True): "hebi"}.get((("bold" if "bold" in weight or weight.isdigit()
                    and int(weight) >= 600 else ""), italic), "helv")
    else:
        fontname = base

    x, y = X(_f(element.get("x"))), Y(_f(element.get("y")))
    width = pymupdf.get_text_length(content, fontname=fontname, fontsize=size)
    if anchor == "middle":
        x -= width / 2.0
    elif anchor == "end":
        x -= width
    page.insert_text(
        pymupdf.Point(x, y),
        content,
        fontsize=size,
        fontname=fontname,
        color=fill,
        fill_opacity=opacity,
        render_mode=render_mode,
    )


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
def svg_to_pdf_bytes(svg: str, *, margin_pt: float = 0.0) -> bytes:
    import pymupdf

    frag = parse_svg(svg)
    w = frag.width_mm * MM_TO_PT + 2 * margin_pt
    h = frag.height_mm * MM_TO_PT + 2 * margin_pt
    doc = pymupdf.open()
    page = doc.new_page(width=w, height=h)
    draw_svg(page, frag, origin=(margin_pt, margin_pt))
    out = doc.tobytes(deflate=True, garbage=3)
    doc.close()
    return out


def svg_to_png(svg: str, *, dpi: int = 300, path: str | None = None) -> bytes:
    """Rasterise for inspection and for the 400 % zoom proofs. Never for output."""
    import pymupdf

    doc = pymupdf.open("pdf", svg_to_pdf_bytes(svg))
    pix = doc[0].get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    if path:
        pix.save(path)
    doc.close()
    return data
