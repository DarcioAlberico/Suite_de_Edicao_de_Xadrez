"""Measure the numbers front F7 is judged on, the way the critic measured them.

Every accept criterion in `docs/quality/F7_CRITIQUE_C1.md` has a subcommand here, and
each one prints the same quantity the critic printed, by the same method, so the two can
be compared without argument:

    .venv\\Scripts\\python.exe tools\\measure_typography.py bottom      # P1
    .venv\\Scripts\\python.exe tools\\measure_typography.py marks       # P2
    .venv\\Scripts\\python.exe tools\\measure_typography.py highlight   # P2
    .venv\\Scripts\\python.exe tools\\measure_typography.py frames      # P3
    .venv\\Scripts\\python.exe tools\\measure_typography.py hatch       # P3
    .venv\\Scripts\\python.exe tools\\measure_typography.py coords      # P3
    .venv\\Scripts\\python.exe tools\\measure_typography.py figurine    # P4
    .venv\\Scripts\\python.exe tools\\measure_typography.py feet        # column balance
    .venv\\Scripts\\python.exe tools\\measure_typography.py folio       # C8 R5, exits 1 on a defect
    .venv\\Scripts\\python.exe tools\\measure_typography.py folio --sabotage 1   # and it fires

The rasters are produced here rather than read from disk, so a number cannot be stale.
Ink density is `1 - v/255` averaged inside the glyph's own ink bounding box, at 200 DPI,
which is the definition the critic used.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402

import typeset_page as tp  # noqa: E402
from caissa.typeset import board_svg as bs  # noqa: E402
from caissa.typeset.board_svg import (  # noqa: E402
    Arrow,
    CircleMark,
    CoordinateStyle,
    DiagramStyle,
    FrameStyle,
    SquareHighlight,
    get_theme,
)

MM = 72.0 / 25.4
DPI = 200
PX = DPI / 25.4  # pixels per millimetre

FEN = "r2q1rk1/pb1n1ppp/1p6/2Pp4/8/6P1/PP1NPPBP/2RQ1RK1 b - - 0 13"


# --------------------------------------------------------------------------- #
# Raster helpers
# --------------------------------------------------------------------------- #
def raster(svg: str, dpi: int = DPI) -> np.ndarray:
    """Rasterise one SVG through the real PDF writer. Returns a greyscale array."""
    from caissa.typeset import svgpdf

    frag = svgpdf.parse_svg(svg)
    doc = pymupdf.open()
    page = doc.new_page(width=frag.width_mm * MM, height=frag.height_mm * MM)
    svgpdf.draw_svg(page, frag, origin=(0.0, 0.0), font_files=tp.serif_files())
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    out = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(float)
    doc.close()
    return out


def raster_rgb(svg: str, dpi: int = DPI) -> np.ndarray:
    from caissa.typeset import svgpdf

    frag = svgpdf.parse_svg(svg)
    doc = pymupdf.open()
    page = doc.new_page(width=frag.width_mm * MM, height=frag.height_mm * MM)
    svgpdf.draw_svg(page, frag, origin=(0.0, 0.0), font_files=tp.serif_files())
    pix = page.get_pixmap(dpi=dpi)
    out = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    doc.close()
    return out.astype(float)


def density(patch: np.ndarray) -> float:
    """Continuous ink density, `1 - v/255`, the critic's definition."""
    return float((1.0 - patch / 255.0).mean())


# --------------------------------------------------------------------------- #
# P4 -- figurine weight
# --------------------------------------------------------------------------- #
def _set_line(text: str, face: str, size_pt: float, width_mm: float = 90.0) -> str:
    font, metrics = tp.metrics_for("merida")
    size = size_pt * 25.4 / 72.0
    canvas = tp.Canvas(width_mm, size * 2.6)
    runs = tp.parse_markup(tp.prepared(text, "en"))
    runs = [tp.Run(r.kind, r.content, face) for r in runs]
    canvas.runs(2.0, size * 1.7, runs, size=size, metrics=metrics, font=font)
    return canvas.render()


def _ink_density(image: np.ndarray, box: tuple[float, float, float, float],
                 threshold: float = 200.0) -> tuple[float, float]:
    """Density inside the ink bounding box found within ``box`` (in pixels).

    The critic's definition: the box is tightened to the glyph's own ink before the mean
    is taken, so a character with side bearing is not diluted by its white margin.
    """
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    patch = image[max(0, y0):y1, max(0, x0):x1]
    if patch.size == 0:
        return 0.0, 0.0
    ink = patch < threshold
    if not ink.any():
        return 0.0, 0.0
    ys, xs = np.nonzero(ink)
    tight = patch[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return density(tight), float(tight.size)


def _line_pdf(text: str, face: str, size_pt: float, dpi: int):  # noqa: ANN201
    """Set one line through the real writer.

    Returns ``(raster, char boxes in px, figurine box in px)``. Character boxes come from
    the PDF's own text layer, so a "neighbouring glyph" is one glyph and not a cluster of
    them. The figurine's box comes from the SVG path it is drawn as, widened by its own
    stroke -- exact, and independent of how much ink is in it.
    """
    import re as _re

    from caissa.typeset import svgpdf

    svg = _set_line(text, face, size_pt)
    xs: list[float] = []
    ys: list[float] = []
    stroke = 0.0
    for match in _re.finditer(r'<path d="([^"]+)"([^>]*)>', svg):
        numbers = [float(v) for v in _re.findall(r"-?\d+\.?\d*", match.group(1))]
        xs += numbers[0::2]
        ys += numbers[1::2]
        sw = _re.search(r'stroke-width="([\d.]+)"', match.group(2))
        if sw:
            stroke = max(stroke, float(sw.group(1)))
    if not xs:
        raise SystemExit("nenhum figurino desenhado na linha")
    half = stroke / 2.0
    piece_mm = (min(xs) - half, min(ys) - half, max(xs) + half, max(ys) + half)

    frag = svgpdf.parse_svg(svg)
    doc = pymupdf.open()
    page = doc.new_page(width=frag.width_mm * MM, height=frag.height_mm * MM)
    svgpdf.draw_svg(page, frag, origin=(0.0, 0.0), font_files=tp.serif_files())
    scale = dpi / 72.0
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                for char in span["chars"]:
                    if char["c"].strip():
                        bbox = char["bbox"]
                        chars.append((char["c"], tuple(v * scale for v in bbox)))
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width
    ).astype(float)
    doc.close()
    chars.sort(key=lambda c: c[1][0])
    px = dpi / 25.4
    piece = tuple(v * px for v in piece_mm)
    return image, chars, piece


def measure_figurine(size_pt: float = 8.6, dpi: int = 600) -> dict:
    """Figurine ink density over the mean of its two neighbouring glyphs.

    The passages are the critic's: a roman sentence carrying `Bxg6` and a bold move
    heading `24.Bxh7+`. Reference (Quality Chess) measures 0.94; cycle 1 measured 0.56
    roman and 0.43 bold.
    """
    out: dict[str, float] = {}
    cases = [
        ("roman", "roman", "White answered Bxg6 at once."),
        ("bold", "bold", "24.Bxh7+"),
    ]
    for name, face, text in cases:
        image, chars, piece = _line_pdf(text, face, size_pt, dpi)
        fx0, fx1 = piece[0], piece[2]
        fig_d, _ = _ink_density(image, (fx0, 0, fx1, image.shape[0]))

        # Neighbour boxes are clipped clear of the figurine's own column range. Without
        # that clip a heavier figurine bleeds into the box of the glyph beside it and
        # flatters its own ratio -- the measurement would improve as the defect got worse.
        def clipped(box, side):  # noqa: ANN001, ANN202
            x0, y0, x1, y1 = box
            return (x0, y0, min(x1, fx0), y1) if side == "left" else (max(x0, fx1), y0, x1, y1)

        left = max((c for c in chars if c[1][2] <= fx0 + 1), key=lambda c: c[1][2], default=None)
        right = min((c for c in chars if c[1][0] >= fx1 - 1), key=lambda c: c[1][0], default=None)
        if left is None or right is None:
            raise SystemExit(f"{name}: figurino sem dois vizinhos")
        ld, _ = _ink_density(image, clipped(left[1], "left"))
        rd, _ = _ink_density(image, clipped(right[1], "right"))
        neighbours = (ld + rd) / 2.0
        out[name] = fig_d / neighbours if neighbours else 0.0
        print(
            f"{name:6s} figurino {fig_d * 100:5.1f} %   vizinhos {left[0]!r} "
            f"{ld * 100:5.1f} % / {right[0]!r} {rd * 100:5.1f} %   razao "
            f"{out[name]:.2f}   (alvo >= 0.85, referencia 0.94, ciclo 1: "
            f"{'0.56' if name == 'roman' else '0.43'})"
        )
    return out


# --------------------------------------------------------------------------- #
# P3 -- hatch
# --------------------------------------------------------------------------- #
def measure_hatch(widths=(20, 30, 40, 52, 58.7, 60, 90)) -> None:
    """Ink coverage across one empty dark square, horizontal scan, exactly as measured
    by the critic on the blind samples."""
    print(f"{'diag':>6} {'board':>7} {'pitch':>7} {'px@200':>7} {'cov':>7}  alvo 0.28-0.32")
    for width in widths:
        style = DiagramStyle(font="merida", width_mm=width, theme="hatched",
                             coordinates=CoordinateStyle.NONE)
        lay = bs._layout(style)
        image = raster(bs.render_svg("8/8/8/8/8/8/8/8 w - - 0 1", style), dpi=DPI)
        # a7 -- row 1, col 0 -- is dark and empty on an empty board.
        x0 = (lay.board_x + 0.10 * lay.square) * PX
        x1 = (lay.board_x + 0.90 * lay.square) * PX
        y = (lay.board_y + 1.5 * lay.square) * PX
        scan = image[int(round(y)), int(round(x0)) : int(round(x1))]
        cov = float((1.0 - scan / 255.0).mean())
        ink = scan < 128
        # Pitch: distance between the starts of successive ink runs, times cos(45).
        starts = [i for i in range(1, len(ink)) if ink[i] and not ink[i - 1]]
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        pitch_px = float(np.median(gaps)) if gaps else float("nan")
        pitch_mm = pitch_px / PX / math.sqrt(2.0)
        print(
            f"{width:6.1f} {lay.board:7.2f} {pitch_mm:7.3f} "
            f"{pitch_px / math.sqrt(2.0):7.2f} {cov:7.3f}"
        )


# --------------------------------------------------------------------------- #
# P3 -- frames and coordinate sizes
# --------------------------------------------------------------------------- #
def frame_rules(pdf: Path, min_side_pt: float = 40.0) -> list[tuple[int, float, float]]:
    """(page, board width pt, stroke pt) for every squarish stroked frame in a PDF."""
    out: list[tuple[int, float, float]] = []
    doc = pymupdf.open(pdf)
    for number, page in enumerate(doc, start=1):
        for drawing in page.get_drawings():
            width = drawing.get("width") or 0.0
            if not width or drawing.get("color") is None:
                continue
            rect = drawing["rect"]
            if rect.width < min_side_pt or abs(rect.width - rect.height) > 1.5:
                continue
            if not any(item[0] == "re" for item in drawing["items"]):
                continue
            out.append((number, rect.width - width, width))
    doc.close()
    return out


def measure_frames(pdf: Path) -> None:
    rows = frame_rules(pdf)
    lo = bs.FRAME_RATIO * (1 - bs.FRAME_RATIO_TOLERANCE)
    hi = bs.FRAME_RATIO * (1 + bs.FRAME_RATIO_TOLERANCE)
    bad = 0
    ratios = []
    for page, board, stroke in rows:
        ratio = board / stroke
        ratios.append(ratio)
        flag = "" if lo <= ratio <= hi else "   *** FORA DA FAIXA"
        if flag:
            bad += 1
        print(f"p{page:<3d} board={board:7.2f} pt  stroke={stroke:6.3f} pt  1/{ratio:6.1f}{flag}")
    if ratios:
        print(
            f"\n{len(ratios)} molduras.  faixa 1/{min(ratios):.1f} a 1/{max(ratios):.1f}  "
            f"(alvo 1/{bs.FRAME_RATIO:.0f} +/-{bs.FRAME_RATIO_TOLERANCE:.0%} "
            f"= 1/{hi:.1f} a 1/{lo:.1f}).  espalhamento "
            f"{max(ratios) / min(ratios):.2f}x.  fora da faixa: {bad}"
        )


def measure_coords(pdf: Path) -> None:
    """Smallest coordinate type actually printed anywhere in a PDF."""
    doc = pymupdf.open(pdf)
    sizes: dict[float, int] = {}
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if len(text) == 1 and text in "abcdefgh12345678":
                        key = round(span["size"], 2)
                        sizes[key] = sizes.get(key, 0) + 1
    doc.close()
    for size in sorted(sizes):
        print(f"{size:6.2f} pt   x{sizes[size]}")
    if sizes:
        print(f"\nmenor corpo de coordenada impresso: {min(sizes):.2f} pt "
              f"(piso {bs.MIN_COORDINATE_PT} pt)")


# --------------------------------------------------------------------------- #
# P2 -- marks and highlights
# --------------------------------------------------------------------------- #
def _components(mask):
    """Number of 8-connected components of a boolean mask. Union-find, no scipy."""
    height, width = mask.shape
    parent = {}

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    ys, xs = np.nonzero(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        parent[y * width + x] = y * width + x
    for y, x in zip(ys.tolist(), xs.tolist()):
        here = y * width + x
        for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width and mask[ny, nx]:
                union(here, ny * width + nx)
    return len({find(key) for key in parent})


MARK_SETS = {
    "setas retas": [Arrow("d1", "d7"), Arrow("g2", "b7"), Arrow("c1", "c5")],
    "salto de cavalo": [Arrow("d2", "b3"), Arrow("d2", "f3"), Arrow("d2", "e4")],
    "misto sobre pecas": [SquareHighlight("d5"), Arrow("g2", "d5"), CircleMark("d5"),
                          Arrow("c1", "c5")],
}


def measure_marks(width_mm: float = 62.0, dpi: int = 600):
    """Q1, the three numbers the critic asked for, on the p5 specimen.

    1. connected components of every piece's outline, before and after the mark: the
       same count, for every piece a shaft crosses;
    2. contrast of the arrowhead against the piece it lands on, >= 3:1;
    3. ink of the destination piece that survives the head, >= 80 %.

    Cycle 2's knockout failed all three: the b2 and f2 pawns came apart, the head over
    the black g7 pawn measured 1.99:1 in LaTeX, and the c5 pawn lost its whole base.
    """
    theme = get_theme("book")
    style = DiagramStyle(font="merida", width_mm=width_mm, theme="book",
                         coordinates=CoordinateStyle.NONE, frame=FrameStyle.HAIRLINE)
    lay = bs._layout(style)
    px = dpi / 25.4
    # Threshold on the PIECE's ink, not on every dark pixel: the mark is #616161 (97 in
    # grey) and the pieces are #000000, so a threshold at 60 isolates the piece and lets
    # the shaft underneath it be ignored. Counting the shaft as ink would report a piece
    # as "broken" merely because an arrow passes behind it.
    plain = raster(bs.render_svg(FEN, style), dpi=dpi) < 60
    board = bs.board_from_fen(FEN)
    step = int(lay.square * px)

    def box(row, col):
        x0 = int((lay.board_x + col * lay.square) * px)
        y0 = int((lay.board_y + row * lay.square) * px)
        return y0, x0

    broken = 0
    checked = 0
    worst_ink = 1.0
    for name, marks in MARK_SETS.items():
        image = raster(bs.render_svg(FEN, style, marks=marks), dpi=dpi) < 60
        targets = {m.target for m in marks if isinstance(m, Arrow)}
        for row in range(8):
            for col in range(8):
                if board[row][col] == ".":
                    continue
                y0, x0 = box(row, col)
                before = plain[y0:y0 + step, x0:x0 + step]
                after = image[y0:y0 + step, x0:x0 + step]
                if not before.any():
                    continue
                square = bs.square_name(row, col)
                if square in targets:
                    worst_ink = min(worst_ink, min(1.0, after.sum() / before.sum()))
                    continue
                checked += 1
                a, b = _components(before), _components(after)
                if b != a:
                    broken += 1
                    print(f"    {name}: {square} {board[row][col]} componentes "
                          f"{a} -> {b}")
    worst_contrast = min(bs.contrast_ratio(theme.arrow, theme.piece_ink),
                         bs.contrast_ratio(theme.arrow, theme.piece_body))
    print(f"pecas atravessadas por uma haste: {checked}, com o contorno partido: "
          f"{broken}   (criterio: 0)")
    print(f"tinta da peca de destino que sobrevive: {worst_ink * 100:.1f} %   "
          f"(criterio: >= 80 %)")
    print(f"contraste da ponta contra a peca: {worst_contrast:.2f}:1   "
          f"(criterio: >= {bs.MARK_INK_MIN_CONTRAST:.1f}:1; LaTeX no ciclo 2: 1,99:1)")
    for key, other in bs.THEMES.items():
        ratio = min(bs.contrast_ratio(other.arrow, other.piece_ink),
                    bs.contrast_ratio(other.arrow, other.piece_body))
        print(f"    tema {key:14s} {ratio:5.2f}:1")
    return broken, worst_ink, worst_contrast


def measure_latex_marks(dpi: int = 600, keep: bool = False):
    """Q1 on the OTHER exporter. The same three numbers, measured on a real compile.

    Two pages are compiled into a scratch directory: the same position with and without
    the marks. The pieces are then compared square by square, exactly as `measure_marks`
    compares them on the SVG side.

    Thresholding at 60 isolates the black ink -- the pieces and the board font's own
    hatch -- from the mark, which is `black!62` (97 in grey). The hatch is identical on
    both pages, so the only square that may differ is the one the arrowhead lands on.
    """
    import shutil
    import tempfile

    from caissa.typeset import latex as lx

    fen = "4rnk1/pbr2ppB/1pq1p3/4P1BQ/2P5/P5R1/5PPP/R5K1 b - - 0 21"
    marks = [SquareHighlight("h7"), Arrow("g3", "g7")]
    options = lx.LatexOptions(language="en", font_family="alpha", board_font_size="26pt",
                              document_class="article", class_options="10pt",
                              geometry="paperwidth=90mm,paperheight=90mm,margin=3mm",
                              show_mover=False, coordinates=False, border=False)
    body = [
        lx.chessboard_command(fen),
        "\\newpage",
        lx.chessboard_command(fen, marks=marks),
    ]
    source = lx.preamble(options) + "\n\\pagestyle{empty}\n\\begin{document}\n" \
        + "\n".join(body) + "\n\\end{document}\n"
    workdir = Path(tempfile.mkdtemp(prefix="caissa-marks-"))
    try:
        tex = workdir / "marks.tex"
        tex.write_text(source, encoding="utf-8")
        result = lx.compile_document(tex, engine="pdflatex", workdir=workdir, runs=1)
        if not result.ok or not result.pdf:
            print(f"LaTeX nao compilou: {result.reason or result.errors[:2]}")
            return None
        doc = pymupdf.open(result.pdf)
        # The first page of the compiled document is blank -- `geometry` on a page this
        # small pushes the first box over -- so the two boards are found rather than
        # assumed to be pages 1 and 2.
        inked = []
        pages = []
        for index in range(doc.page_count):
            pix = doc[index].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width).astype(float)
            if (array < 60).sum() > 1000:
                inked.append(index)
                pages.append(array)
        if len(pages) < 2:
            print(f"o documento compilou com {len(pages)} tabuleiro(s); esperados 2")
            doc.close()
            return None
        pages = pages[:2]
        rgb = doc[inked[1]].get_pixmap(dpi=dpi)
        colour_page = np.frombuffer(rgb.samples, dtype=np.uint8).reshape(
            rgb.height, rgb.width, 3).astype(float)
        doc.close()
    finally:
        if not keep:
            shutil.rmtree(workdir, ignore_errors=True)

    plain, marked = (page < 60 for page in pages)
    ys, xs = np.nonzero(plain)
    top, left, bottom, right = ys.min(), xs.min(), ys.max(), xs.max()
    side = min(bottom - top, right - left) + 1
    step = side / 8.0
    board = bs.board_from_fen(fen)
    broken = 0
    checked = 0
    survived = 1.0
    for row in range(8):
        for col in range(8):
            if board[row][col] == ".":
                continue
            y0, x0 = int(top + row * step), int(left + col * step)
            y1, x1 = int(top + (row + 1) * step), int(left + (col + 1) * step)
            before, after = plain[y0:y1, x0:x1], marked[y0:y1, x0:x1]
            if not before.any():
                continue
            if bs.square_name(row, col) == "g7":
                survived = min(1.0, after.sum() / before.sum())
                continue
            checked += 1
            a, b = _components(before), _components(after)
            if a != b:
                broken += 1
                print(f"    {bs.square_name(row, col)} {board[row][col]}: "
                      f"componentes {a} -> {b}")
    # The head's own colour where it lands on the black g7 pawn.
    row, col = bs.square_index("g7")
    y0, x0 = int(top + row * step), int(left + col * step)
    y1, x1 = int(top + (row + 1) * step), int(left + (col + 1) * step)
    patch = colour_page[y0:y1, x0:x1].reshape(-1, 3)
    greys = patch[(np.abs(patch[:, 0] - patch[:, 1]) < 6)
                  & (np.abs(patch[:, 1] - patch[:, 2]) < 6)]
    mark_pixels = greys[(greys[:, 0] > 70) & (greys[:, 0] < 130)]
    if len(mark_pixels):
        value = int(round(float(np.median(mark_pixels[:, 0]))))
        colour = f"#{value:02X}{value:02X}{value:02X}"
        ratio = bs.contrast_ratio(colour, "#000000")
    else:
        colour, ratio = "(nenhum)", 0.0
    print(f"pecas atravessadas por uma haste: {checked}, com o contorno partido: "
          f"{broken}   (criterio: 0)")
    print(f"tinta do peao de g7 que sobrevive: {survived * 100:.1f} %   "
          f"(criterio: >= 80 %)")
    print(f"cor da ponta sobre a peca: {colour} ({len(mark_pixels)} px)   "
          f"contraste {ratio:.2f}:1   (criterio: >= 3,0:1; ciclo 2: 1,99:1)")
    return broken, survived, ratio


def measure_inside(square_mm: float = 6.3, dpi: int = 900):
    """Q2. Inside coordinates on the p4 specimen: no notched piece, sixteen whole labels.

    The same connected-components proof as Q1, plus the count of labels drawn.
    """
    import re as _re

    from caissa.typeset.board_svg import width_for_square

    import typeset_proofsheet as ps

    probe = DiagramStyle(font="merida", theme="book",
                         coordinates=CoordinateStyle.INSIDE)
    style = DiagramStyle(font="merida", theme="book",
                         width_mm=width_for_square(probe, square_mm),
                         coordinates=CoordinateStyle.INSIDE)
    print(f"posicao do especime aceita as coordenadas de dentro: "
          f"{bs.inside_coordinates_fit(ps.FEN_INSIDE, style)}")
    print(f"posicao cheia (torre em c1, dama em d1): "
          f"{bs.inside_coordinates_fit(ps.FEN_MARECO, style)}"
          f"   (esperado False -- os rotulos voltam para fora)")

    bare = DiagramStyle(font="merida", theme="book", width_mm=style.width_mm,
                        coordinates=CoordinateStyle.NONE)
    lay, bare_lay = bs._layout(style), bs._layout(bare)
    px = dpi / 25.4
    board = bs.board_from_fen(ps.FEN_INSIDE)
    plain = raster(bs.render_svg(ps.FEN_INSIDE, bare), dpi=dpi) < 128
    labelled = raster(bs.render_svg(ps.FEN_INSIDE, style), dpi=dpi) < 128
    step = int(lay.square * px)
    broken = 0
    for row in range(8):
        for col in range(8):
            if board[row][col] == ".":
                continue
            y0 = int((bare_lay.board_y + row * bare_lay.square) * px)
            x0 = int((bare_lay.board_x + col * bare_lay.square) * px)
            before = plain[y0:y0 + step, x0:x0 + step]
            y1 = int((lay.board_y + row * lay.square) * px)
            x1 = int((lay.board_x + col * lay.square) * px)
            after = labelled[y1:y1 + step, x1:x1 + step]
            if not before.any():
                continue
            a, b = _components(before), _components(after)
            if b < a:
                broken += 1
                print(f"    {bs.square_name(row, col)} {board[row][col]}: "
                      f"componentes {a} -> {b}")
    svg = bs.render_svg(ps.FEN_INSIDE, style)
    labels = _re.findall(r"<text[^>]*>([^<]*)</text>", svg)
    print(f"rotulos desenhados: {len(labels)} -- {''.join(sorted(labels))}")
    print(f"pecas com entalhe: {broken}   (criterio: 0)")
    return broken, len(labels)


def measure_figset(size_pt: float = 8.6, dpi: int = 1200, family: str = "merida"):
    """R3. Is the inline figurine the same set as the diagram's, piece by piece?

    The critic's criterion, and his method: *"para as seis pecas, a fracao de tinta do
    glifo em linha tem de cair na mesma banda (+-0,08) que a do mesmo glifo desenhado no
    diagrama para a mesma cor"*. He measured knights at 0.31-0.40 and queens at 0.60 in
    one bold run and read it, correctly, as two sets in one line.

    Ink fraction is the mean ink over the glyph's own tight ink box, which is
    scale-invariant: measured unstroked at text size and at diagram size the six pieces
    agree to 0.012, so the diagram column below is the *drawing* both places share.
    """
    from caissa.typeset import figurine as figmod
    from caissa.typeset.fonts import load_font

    font = load_font(family)
    metrics = figmod.measure_family(font)
    size = size_pt * 25.4 / 72.0

    def ink_of(piece: str, weight: float, scale: float = 1.0) -> float:
        markup, advance = figmod.figurine_svg(
            piece, font=font, metrics=metrics, text_size=size * scale, x=1.0,
            baseline_y=size * scale * 1.3, colour="#000000", weight=weight,
            counter_colour="#FFFFFF",
        )
        width, height = advance + 2.0, size * scale * 2.0
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" '
               f'height="{height}mm" viewBox="0 0 {width} {height}">'
               f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>'
               f'{markup}</svg>')
        image = raster(svg, dpi=dpi)
        mask = image < 128
        if not mask.any():
            return 0.0
        ys, xs = np.nonzero(mask)
        return float(mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean())

    worst = 0.0
    print(f"{'peca':5s} {'diagrama':>9s} {'romano':>8s} {'negrito':>8s} "
          f"{'d rom':>7s} {'d neg':>7s}   (banda +-0.08)")
    out = {}
    for piece in "KQRBNP":
        base = ink_of(piece, 0.0)
        roman = ink_of(piece, metrics.outset_for(piece, "roman"))
        bold = ink_of(piece, metrics.outset_for(piece, "bold"))
        worst = max(worst, abs(roman - base), abs(bold - base))
        out[piece] = (base, roman, bold)
        print(f"{piece:5s} {base:9.3f} {roman:8.3f} {bold:8.3f} "
              f"{roman - base:+7.3f} {bold - base:+7.3f}"
              + ("   FORA DA BANDA" if max(abs(roman - base), abs(bold - base)) > 0.08 else ""))
    spread = max(v[2] for v in out.values()) - min(v[2] for v in out.values())
    base_spread = max(v[0] for v in out.values()) - min(v[0] for v in out.values())
    print()
    print(f"maior desvio contra o diagrama: {worst:.3f}  (criterio <= 0.080)")
    print(f"dispersao entre as seis pecas: negrito {spread:.3f}, diagrama {base_spread:.3f} "
          f"-- o conjunto em linha nao pode ser mais disperso que o do diagrama")
    return worst, out


def measure_counters(size_pt: float = 8.6, dpi: int = 2400):
    """Counter area of a bold figurine over the same glyph in roman. Non-blocking 11."""
    from collections import deque

    from caissa.typeset import figurine as figmod
    from caissa.typeset.fonts import load_font

    font = load_font("merida")
    metrics = figmod.measure_family(font)

    def image_of(piece, weight):
        size = size_pt * 25.4 / 72.0
        markup, advance = figmod.figurine_svg(
            piece, font=font, metrics=metrics, text_size=size, x=1.0,
            baseline_y=size * 1.2, colour="#000000", weight=weight,
            # The page's own drawing path, not a simplified one. Measuring the figurine
            # without the paper colour that punches its counters back measures a glyph
            # the book does not contain -- which is how cycle 5 reported the queen at
            # 0.56 of its counters while believing the weight was the only difference.
            counter_colour="#FFFFFF",
        )
        width, height = advance + 2.0, size * 1.9
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" '
               f'height="{height}mm" viewBox="0 0 {width} {height}">{markup}</svg>')
        return raster(svg, dpi=dpi)

    def counter_area(image):
        ink = image < 128
        white = ~ink
        seen = np.zeros_like(white)
        queue = deque()
        height, width = white.shape
        for x in range(width):
            for y in (0, height - 1):
                if white[y, x] and not seen[y, x]:
                    seen[y, x] = True
                    queue.append((y, x))
        for y in range(height):
            for x in (0, width - 1):
                if white[y, x] and not seen[y, x]:
                    seen[y, x] = True
                    queue.append((y, x))
        while queue:
            y, x = queue.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and white[ny, nx] \
                        and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        return int((white & ~seen).sum())

    out = {}
    print(f"{'peca':5s} {'romano':>9s} {'negrito':>9s} {'razao':>7s}   "
          f"(criterio: >= {figmod.FIGURINE_COUNTER_FLOOR:.2f})")
    for piece in "KQRBNP":
        roman = counter_area(image_of(piece, metrics.outset_for(piece, "roman")))
        bold = counter_area(image_of(piece, metrics.outset_for(piece, "bold")))
        ratio = bold / roman if roman else 1.0
        out[piece] = ratio
        print(f"{piece:5s} {roman:9d} {bold:9d} {ratio:7.2f}")
    return out


def measure_wordspace(pdf, pages: str = "", dpi: int = 200):
    """Q4.5. The loosest justified line, as a multiple of the page's nominal word space.

    The critic's method exactly (`critique/c3/wordspace.py`): the page is rasterised, each
    text band is split into ink clusters, the gaps between clusters that are word-sized
    are collected, and each line's median word gap is divided by the page's own median.
    Measured on the raster and not on the PDF's character boxes for one reason: a figurine
    is a *path*, so it leaves no character, and a character-based measurement reads the
    space a figurine occupies as a word gap and reports a move line as three times loose.

    He measured our worst line at 3.00x, against 1.60x (Gambit), 2.19x (Quality Chess) and
    2.79x (Everyman).
    """
    doc = pymupdf.open(pdf)
    wanted = [int(v) for v in pages.split(",") if v.strip()] or list(
        range(1, doc.page_count + 1))
    lines = []
    for number in wanted:
        page = doc[number - 1]
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width).astype(float)
        ink = (255.0 - image) / 255.0 > 0.35
        mid = ink.shape[1] // 2
        # Bands that belong to a diagram are excluded, as in the critic's own script: a
        # row of eight file letters under a board is a band of eight clusters separated
        # by a third of a square, and counting those as word spaces reports a page of
        # prose as five times loose.
        scale = dpi / 72.0
        boards = []
        for drawing in page.get_drawings():
            rect = drawing["rect"]
            if rect.width > 60 and rect.height > 60 and abs(rect.width - rect.height) < 24:
                boards.append((rect.x0 * scale, rect.x1 * scale,
                               rect.y0 * scale - 8, rect.y1 * scale + 8 + 0.25 * dpi))
        for x0, x1 in ((0, mid), (mid, ink.shape[1])):
            column = ink[:, x0:x1]
            rows = column.sum(axis=1)
            bands = []
            start = None
            for y, count in enumerate(rows):
                if count > 0 and start is None:
                    start = y
                elif count == 0 and start is not None:
                    bands.append((start, y - 1))
                    start = None
            if start is not None:
                bands.append((start, len(rows) - 1))
            for top, bottom in bands:
                height = bottom - top + 1
                if not 8 <= height <= 45:      # a line of type, not a diagram
                    continue
                if any(bottom >= b2 and top <= b3 and x1 > b0 and x0 < b1
                       for b0, b1, b2, b3 in boards):
                    continue
                strip = column[top:bottom + 1]
                cols = strip.sum(axis=0)
                filled = np.nonzero(cols)[0]
                if len(filled) < 40:
                    continue
                gaps, run = [], 0
                for value in cols[filled[0]:filled[-1] + 1]:
                    if value == 0:
                        run += 1
                    elif run:
                        gaps.append(run)
                        run = 0
                gaps = np.array([g for g in gaps if g >= 3])
                if len(gaps) < 3:
                    continue
                words = gaps[gaps >= max(4, 0.45 * gaps.max())]
                if len(words) < 2:
                    continue
                lines.append((float(np.median(words)), number, int(top)))
    doc.close()
    if not lines:
        return 0.0
    nominal = float(np.median([g for g, _, _ in lines]))
    ranked = sorted(lines, reverse=True)
    print(f"{len(lines)} linhas | espaco nominal {nominal:.1f} px a {dpi} DPI "
          f"= {nominal * 25.4 / dpi:.2f} mm")
    for gap, number, top in ranked[:4]:
        print(f"    p{number:<3d} y={top:<5d} {gap / nominal:5.2f}x")
    worst = ranked[0][0] / nominal
    tight = ranked[-1][0] / nominal
    over = sum(1 for g, _, _ in lines if g / nominal > 2.0)
    print(f"linha mais frouxa: {worst:.2f}x   mais apertada: {tight:.2f}x   "
          f"linhas acima de 2,0x: {over}   "
          f"(criterio: <= 2,00x; referencias F 1,60 C 2,19 D 2,79; nos no ciclo 2: 3,00)")
    # R1: *"Reportar, junto com o wordspace, quantas linhas o compositor recusou
    # justificar -- uma metrica de espaco entre palavras que nao conta as recusas nao e
    # uma metrica."* Cycle 5's figure of 1,73x was measured over the lines the breaker
    # justified and left out the 1 line in 8 it had refused to, the worst of them at 0,55
    # of the measure. The refusals are counted here, on the same pages, by the critic's
    # own rule, and printed beside the number they would otherwise flatter.
    short, total, deepest = measure_midshort(pdf, pages, quiet=True)
    print(f"linhas de meio de paragrafo que NAO chegam a medida: {short} de {total}"
          + (f"   a mais curta a {deepest[0]:.2f} (p{deepest[1]} y={deepest[2]:.1f})"
             if short else "   (ciclo 5: 5 de 37, a pior a 0,55)"))
    return worst


# --------------------------------------------------------------------------- #
# The word-space band, ours against the five reference pages
# --------------------------------------------------------------------------- #
BLIND3 = ROOT / "benchmarks" / "reports" / "blind3"

REFERENCE_COLUMNS = {
    # The critic's own column boxes, `critique/c5/wordgap.py`, character for character.
    # They are his because the comparison is his: a box drawn by the side being judged is
    # a box that can be drawn around the good lines.
    "amostra_A.png": (("L", 89, 625, 150, 1745), ("R", 645, 1180, 150, 1745)),
    "amostra_B.png": (("S", 100, 960, 280, 1450),),
    "amostra_C.png": (("L", 100, 500, 80, 1400), ("R", 515, 920, 80, 1400)),
    "amostra_D.png": (("L", 38, 575, 90, 1650), ("R", 595, 1120, 90, 1650)),
    "amostra_E.png": (("L", 80, 745, 100, 2090), ("R", 950, 1620, 100, 2090)),
    "amostra_F.png": (("L", 160, 920, 300, 2510), ("R", 960, 1760, 300, 2510)),
}

REFERENCE_NAMES = {
    "amostra_A.png": "A Quality Chess p149",
    "amostra_B.png": "B Nunn p50",
    "amostra_C.png": "C Gambit p116",
    "amostra_D.png": "D Everyman/Aagaard p215",
    "amostra_E.png": "E Dvoretsky 2025 p215",
}

BAND_FLOOR, BAND_CEILING = 0.85, 1.5
"""The band the accept test draws, and it is not arbitrary. At the composer's glue --
stretch half the nominal space, shrink a fifth of it -- TeX calls a line *decent* or
*loose* between 0.901x and 1.498x, which sits **inside** this band. So a page whose every
line is decent or loose has no line outside 0.85x-1.50x, while a line at 0.87x is inside
the band and TeX still calls it tight: the inclusion runs one way and is asserted that
way in `test_the_fitness_classes_are_texs_four`."""

BLIND3_DPI = 300
"""The DPI `amostra_F` was rendered at. Our page is rasterised at the same one so that
the critic's own box for it applies unchanged."""


def _ink(gray: np.ndarray) -> np.ndarray:
    """Ink mask at the midpoint between the page's paper and its darkest ink.

    Not a fixed 128: sample A is a **scan**, its paper is not 255 and its ink is not 0,
    and a fixed threshold measures a scan's word gaps wider than a vector page's simply
    because the paper is grey. The two levels are read off each page's own histogram --
    the 90th percentile is paper, the 0.5th is ink -- so the same rule gives 127.5 on
    every vector page and follows the scan where the scan goes.
    """
    paper = float(np.percentile(gray, 90))
    darkest = float(np.percentile(gray, 0.5))
    mask = gray < (paper + darkest) / 2.0
    # Ink is the minority on a page of type. On the dark theme it is the *light* pixels
    # that are ink, and a mask that took the majority class would measure the gaps
    # between the holes in the background.
    return ~mask if mask.mean() > 0.5 else mask


def _row_bands(sub: np.ndarray) -> list[tuple[int, int]]:
    """Runs of rows that carry ink: one entry per line of type (or per drawing)."""
    on = sub.sum(axis=1) > 0
    out: list[tuple[int, int]] = []
    start = None
    for index, value in enumerate(on):
        if value and start is None:
            start = index
        elif not value and start is not None:
            out.append((start, index - 1))
            start = None
    if start is not None:
        out.append((start, len(on) - 1))
    return out


def _line_gaps(strip: np.ndarray) -> tuple[int, int, list[int]]:
    """``(left, right, gap widths)`` of one line, from its ink columns."""
    column = strip.any(axis=0)
    filled = np.nonzero(column)[0]
    if filled.size == 0:
        return -1, -1, []
    left, right = int(filled[0]), int(filled[-1])
    widths, run = [], 0
    for value in column[left:right + 1]:
        if not value:
            run += 1
        elif run:
            widths.append(run)
            run = 0
    return left, right, widths


class GapCut(NamedTuple):
    """The verdict of `word_gap_cut_detail`: a threshold, or an honest refusal."""

    cut: int
    ok: bool
    reason: str
    letter_mode: int
    word_mode: int
    trough: int
    depth: float
    words: int

    def __str__(self) -> str:
        if not self.ok:
            return f"cut INDECISO ({self.reason})"
        return (f"cut={self.cut} px  modas {self.letter_mode}/{self.word_mode}  "
                f"vale {self.trough}  profundidade {self.depth:.2f}  "
                f"{self.words} vaos de palavra")


CUT_MIN_POOL = 50
"""Fewest gaps a page must offer before a threshold is worth computing at all."""

CUT_MIN_SPAN = 3
"""Fewest bins between the two modes. Two adjacent peaks have no trough between them."""

CUT_MAX_DEPTH = 0.5
"""The trough must hold at most half the count of the *smaller* of the two modes.
Above that the histogram is one population with a dent in it, not two."""

CUT_MIN_WORDS = 20
"""Fewest gaps that must land on the word side. A cut that leaves almost nothing above
it is a cut that measured the end of the data."""


def word_gap_cut_detail(pool: "list[int]", leading: float = 0.0) -> GapCut:
    """Where a letter gap stops and a word gap starts, on this page, in pixels.

    Not a fixed fraction of the x-height. The cycle-5 critic's `wordgap.py` called every
    gap of at least 0.18 x-heights a word gap, and the consequence was visible in his own
    output: the tightest line of A, B, C, D and E all came out at 0.196-0.216 of the
    pitch, which is the cutoff itself. A threshold that the answer sits on is not
    measuring the page.

    **And the first version of this function did the same thing** -- the cycle-10 critic
    caught it and was right. It scanned a window fixed at 0.06 to 0.30 of the page's own
    estimated leading and took the `argmin`, so it could return, and did return, the
    window's own edge:

    * `proofsheet_run.pdf` at 300 DPI, pages 1-3: the leading came out 61.75 px instead
      of the true 43.4 (the estimator medians the steps between *ink bands*, and half of
      those bands are two fused lines or a whole diagram). The window floor moved from
      3 px to 4 px, which stepped over the letter-gap mode at 3 (count 193), and the
      `argmin` fell into the empty bin at the **top** of the window: `cut = 19`. Three of
      the four pages then measured fewer than five lines and were dropped as `thin` --
      including page 2, which is the blind sample.
    * At 200 DPI the same window ended past the word-gap mode, so the `argmin` found a
      thin bin in the *tail* of the word population instead of the trough: `cut = 10`
      where the trough is at 5. The same page then read 0.0 %, 6.7 % or 33.3 % outside
      the band depending only on the DPI it was rasterised at.

    So the leading is gone from this decision entirely. The gap widths of a page of type
    are two populations -- inside words, between words -- and the histogram is read for
    what it is:

    1. the **letter mode** is the tallest bin (a page has far more gaps inside its words
       than between them, on every one of the twenty-two rasters measured for cycle 11:
       our four run pages, three book pages and Portuguese page at 200 and at
       300 DPI, plus the six blind-set pages);
    2. the **cut** is the bin that maximises ``max(counts above it) - counts[bin]`` --
       the deepest bin that still has a tall peak somewhere above it. Ties go to the
       narrower gap;
    3. the **word mode** is that tall peak.

    Step 2 is what makes an edge return impossible: the score of the last non-empty bin
    is at best zero, because there is nothing above it to be tall, so a real trough with
    a real peak beyond it always wins. There is no window and therefore no window edge.

    It is also why the rule is a prominence and not a plain `argmin` between two modes:
    reference E's letter population has a one-bin wobble at 5 px (92 then 104), and a
    rule that stopped walking at the first rise would call 5 px the word mode and cut the
    page at 4. Prominence ignores the wobble because the wobble has no peak above it.

    On the six blind-set rasters this reproduces the value the old rule found -- A 6,
    B 4, C 5, D 5, E 9, our Portuguese page 7 -- so no published reference number moves;
    and it repairs the two places the old rule broke.

    The refusal is the other half. Four conditions must hold, and if any fails the
    caller gets ``ok=False`` and **no number** -- because the cost of this bug was not
    that it computed a bad threshold, it was that the bad threshold was reported as if
    it were a good one:

    * at least `CUT_MIN_POOL` gaps on the page;
    * the two modes at least `CUT_MIN_SPAN` bins apart;
    * the trough at most `CUT_MAX_DEPTH` of the smaller mode -- otherwise the page is
      not bimodal and there is nothing to separate;
    * at least `CUT_MIN_WORDS` gaps above the cut.

    ``leading`` is accepted and ignored; it is kept in the signature because callers
    pass it, and reported nowhere.
    """
    del leading  # deliberately unused: see the docstring.
    if len(pool) < CUT_MIN_POOL:
        return GapCut(0, False, f"poucos vaos na pagina ({len(pool)} < {CUT_MIN_POOL})",
                      0, 0, 0, 0.0, 0)
    counts = np.bincount(np.asarray(pool, dtype=int), minlength=8)
    letter_mode = int(np.argmax(counts[1:])) + 1
    last = int(np.nonzero(counts)[0][-1])

    # `suffix[i]` is the tallest bin at or above `i`: the peak a cut at `i - 1` would be
    # separating itself from.
    suffix = np.maximum.accumulate(counts[::-1])[::-1]
    first = letter_mode + 2  # one bin of decay before a cut is allowed at all
    if first > last - 1:
        return GapCut(0, False,
                      f"nenhum vao suficientemente largo (moda {letter_mode}, "
                      f"maior vao {last})", letter_mode, 0, 0, 0.0, 0)
    candidates = np.arange(first, last)
    cut = int(candidates[int(np.argmax(suffix[candidates + 1] - counts[candidates]))])

    word_mode = cut + 1 + int(np.argmax(counts[cut + 1:]))
    if counts[word_mode] == 0:
        return GapCut(0, False, "nenhum vao acima do corte", letter_mode, 0, 0, 0.0, 0)
    if word_mode - letter_mode < CUT_MIN_SPAN:
        return GapCut(0, False,
                      f"modas coladas ({letter_mode} e {word_mode}, "
                      f"minimo {CUT_MIN_SPAN} bins)",
                      letter_mode, word_mode, 0, 0.0, 0)

    trough = int(counts[cut])
    smaller = int(min(counts[letter_mode], counts[word_mode]))
    depth = trough / smaller if smaller else 1.0
    words = int(counts[cut + 1:].sum())
    if depth > CUT_MAX_DEPTH:
        return GapCut(0, False,
                      f"histograma nao e bimodal (vale {trough} contra moda menor "
                      f"{smaller}, {depth:.2f} > {CUT_MAX_DEPTH})",
                      letter_mode, word_mode, trough, depth, words)
    if words < CUT_MIN_WORDS:
        return GapCut(0, False,
                      f"so {words} vaos acima do corte (minimo {CUT_MIN_WORDS})",
                      letter_mode, word_mode, trough, depth, words)
    assert letter_mode < cut < word_mode, "o corte saiu do intervalo entre as modas"
    return GapCut(cut, True, "", letter_mode, word_mode, trough, depth, words)


def word_gap_cut(pool: "list[int]", leading: float) -> int:
    """`word_gap_cut_detail(...).cut`; **0 when the page has no decidable cut**.

    Kept because callers exist. A caller that must not silently proceed on a refusal
    should use `word_gap_cut_detail` and read `ok`.
    """
    return word_gap_cut_detail(pool, leading).cut


def page_word_band(gray: np.ndarray, boxes, *, label: str = "",
                   margin_tol: float = 0.012, verbose: bool = False) -> dict | None:
    """The word-space band of one page: the critic's quantity, measured fairly.

    Both sides are measured from glyph boxes in exactly the same way -- ink columns
    inside a line, runs of blank columns between them -- so nothing about the method
    knows which page is ours.

    A line counts only if it is **justified**, and that is a measurement and not an
    assumption: its right edge must reach the column's own right margin (the 90th
    percentile of the line right edges) within ``margin_tol``. This matters. Reference E
    is set **ragged right** -- 7 of its 42 body lines reach the margin, and its line
    edges spread over 46 % of the measure -- so on a word-space statistic it is not a
    comparable page at all; its spaces are constant because nothing ever stretches them.
    The fraction is reported for every page so that the reader can see which pages are
    justified before reading the band.
    """
    ink = _ink(gray)
    columns, pool, leads = [], [], []
    for name, x0, x1, y0, y1 in boxes:
        sub = ink[y0:y1, x0:x1]
        segments = _row_bands(sub)
        if len(segments) < 4:
            continue
        steps = np.diff([s for s, _ in segments])
        leading = float(np.median(steps[steps > 3])) if (steps > 3).any() else 1.0
        leads.append(leading)
        rows = []
        for top, bottom in segments:
            height = bottom - top + 1
            # A line of type, not a diagram and not a stray accent: between a third and
            # one and a quarter of the column's own leading.
            if not 0.30 * leading <= height <= 1.25 * leading:
                continue
            left, right, widths = _line_gaps(sub[top:bottom + 1])
            if left < 0 or len(widths) < 3:
                continue
            rows.append((top, left, right, widths))
            pool += [w for w in widths if w >= 1]
        columns.append((name, leading, rows))
    if not columns or not pool:
        return None
    leading = float(np.median(leads))
    verdict = word_gap_cut_detail(pool, leading)
    if not verdict.ok:
        # Refuse, loudly, rather than measure with a threshold that is not one. Cycle 10
        # found the old rule returning its own window edge on three of the four run
        # pages, which then dropped out as `thin` -- a wrong number wearing the same
        # clothes as a right one. `undecided` has no band, no deviation and no share.
        return dict(label=label, lines=0, body=len(
            [r for _n, _l, rows in columns for r in rows]), justified=0,
            leading=leading, cut=0, thin=True, undecided=True, why=verdict.reason)
    cut = verdict.cut
    measured, body, ragged, few = [], 0, 0, 0
    for name, _leading, rows in columns:
        if not rows:
            continue
        margin = float(np.percentile([r[2] for r in rows], 90))
        measure = float(np.percentile([r[2] - r[1] for r in rows], 90))
        for top, left, right, widths in rows:
            body += 1
            if right < margin - margin_tol * measure:
                ragged += 1
                continue
            words = [w for w in widths if w > cut]
            if len(words) < 3:
                few += 1
                continue
            measured.append((float(np.median(words)), name, top, len(words)))
    if len(measured) < 5:
        return dict(label=label, lines=len(measured), body=body, justified=body - ragged,
                    leading=leading, cut=cut, thin=True, undecided=False,
                    why=f"so {len(measured)} linhas justificadas com 3+ vaos de palavra")
    nominal = float(np.median([g for g, _, _, _ in measured]))
    ratios = np.array([g / nominal for g, _, _, _ in measured])
    out = dict(
        label=label, lines=len(ratios), body=body, justified=body - ragged, few=few,
        leading=leading, cut=cut, nominal=nominal, thin=False, undecided=False,
        ratios=ratios, low=float(ratios.min()), high=float(ratios.max()),
        band=float(ratios.max() / ratios.min()), std=float(ratios.std()),
        outside=int(((ratios < BAND_FLOOR) | (ratios > BAND_CEILING)).sum()),
    )
    if verbose:
        ranked = sorted(measured)
        for gap, name, top, count in ranked[:2] + ranked[-2:]:
            print(f"       {gap / nominal:5.2f}x  col{name} y={top:<5d} "
                  f"{count} word gaps, median {gap:.0f} px")
    return out


def _row(stats: dict) -> str:
    if stats is None:
        return "  (nao medivel)"
    share = f"{stats['justified']}/{stats['body']}"
    if stats.get("undecided"):
        return (f"{stats['label']:24s}  RECUSADO — sem limiar entre vao de letra e vao "
                f"de palavra: {stats.get('why', '')}")
    if stats.get("thin"):
        return (f"{stats['label']:24s}  linhas justificadas {share:>7s}  "
                f"— menos de 5 linhas medidas, banda nao reportavel "
                f"({stats.get('why', '')})")
    return (f"{stats['label']:24s}  just {share:>7s}  n={stats['lines']:3d}  "
            f"corte {stats['cut']:2d} px  "
            f"banda {stats['low']:.2f}–{stats['high']:.2f} = {stats['band']:.2f}x  "
            f"desvio {stats['std']:.3f}  fora de "
            f"{BAND_FLOOR:.2f}–{BAND_CEILING:.1f} {stats['outside']:2d}/{stats['lines']}"
            f"  ({stats['outside'] / stats['lines'] * 100:4.1f} %)")


def _page_folio(page) -> str:  # noqa: ANN001
    """The number the page actually prints, read back off the page.

    A label that names the pages it read is the only thing that would have caught the
    bug below, so the label is not written by hand: the folio is the first short numeric
    span above `RUNNING_HEAD_MM`, which is where `compose_book_page` puts it.
    """
    best = None
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                text = span["text"].strip()
                if text.isdigit() and len(text) <= 4 and span["bbox"][3] < 40:
                    if best is None or span["bbox"][1] < best[0]:
                        best = (span["bbox"][1], text)
    return best[1] if best else "?"


def _our_pages(dpi: int = BLIND3_DPI):  # noqa: ANN201
    """Our delivered book pages, rasterised at the DPI the blind sample was made at.

    The Portuguese page is the one in the critic's blind set (`amostra_F`), so it is the
    page the table compares; the English book pages of the proof sheet are measured too,
    by the same rule, because a number quoted from one page of three is a number chosen.
    The page geometry is `book_geometry()` for all of them, so the critic's own box for
    `amostra_F` lands on the same columns in every one.

    **This read the wrong pages until cycle 11**, and the cycle-10 critic found it. The
    tuple was a hardcoded `(10, 11, 12)` indexed as `doc[number - 1]`, i.e. 1-based
    10-11-12, while `_book_pages()` in this same file derives the book pages as 13-3+1 =
    **11, 12, 13**. So it measured one specimen page -- which comes back `thin` and is
    silently dropped -- and **never measured folio 46 at all**, while printing a label
    that said "the last 3". It now calls `_book_pages()`, the one derivation there is,
    and the label names the folios it actually read so the mismatch cannot recur
    unnoticed.
    """
    out = []
    sheet = ROOT / "benchmarks" / "reports" / "proofsheet.pdf"
    for path, pages, stem in (
        (ROOT / "benchmarks" / "reports" / "proofsheet_rios.pdf", (1,), "F nossa, pt"),
        (sheet, tuple(int(p) for p in _book_pages(sheet).split(",")), "F nossa, en"),
        (ROOT / "benchmarks" / "reports" / "proofsheet_run.pdf", (1, 2, 3, 4),
         "F nossa, corrida"),
    ):
        doc = pymupdf.open(path)
        grays, folios = [], []
        for number in pages:
            page = doc[number - 1]
            folios.append(_page_folio(page))
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            grays.append(np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width).astype(float))
        doc.close()
        out.append((f"{stem} (folio {'/'.join(folios)})", grays))
    return out


def _merged(stats: "list[dict]", label: str) -> dict | None:
    """Several pages measured as one page: the ratios are already per-page normalised.

    A page that could not be measured is **not** quietly left out of the pool. Cycle 10's
    3-of-4 unmeasurable run pages were invisible in the aggregate precisely because the
    aggregate took what it could get; here one refusal refuses the whole row, and the
    per-page rows are printed above it so the reader can see which page it was.
    """
    if any(s is None for s in stats):
        return None
    refused = [s for s in stats if s.get("undecided")]
    if refused:
        return dict(label=label, lines=0, body=sum(s["body"] for s in stats),
                    justified=0, leading=stats[0]["leading"], cut=0, thin=True,
                    undecided=True,
                    why=f"{len(refused)} de {len(stats)} paginas sem limiar: "
                        + "; ".join(s.get("why", "") for s in refused))
    good = [s for s in stats if not s.get("thin")]
    if not good:
        return None
    ratios = np.concatenate([s["ratios"] for s in good])
    return dict(
        label=label, lines=len(ratios),
        body=sum(s["body"] for s in good), justified=sum(s["justified"] for s in good),
        leading=good[0]["leading"], cut=good[0]["cut"], nominal=good[0]["nominal"],
        thin=False, undecided=False,
        ratios=ratios, low=float(ratios.min()), high=float(ratios.max()),
        band=float(ratios.max() / ratios.min()), std=float(ratios.std()),
        outside=int(((ratios < BAND_FLOOR) | (ratios > BAND_CEILING)).sum()),
    )


def measure_wordband(verbose: bool = False, sabotage: int = 0) -> dict:
    """Q5. The word-space band of our pages against all five reference pages.

    Three statistics per page, all dimensionless, all produced by one rule run over six
    rasters at the same DPI:

    * **banda** -- the loosest justified line's word space over the tightest one's, each
      line taken as the median of its own word gaps and divided by the page's median;
    * **desvio** -- the standard deviation of those per-line ratios;
    * **fora** -- the share of justified lines outside 0.85x-1.50x of the page nominal.

    Every page also reports how many of its body lines are **justified at all**, because
    one of the five is not: reference E reaches its right margin on 7 lines of 42 and its
    line ends spread over 46 % of the measure. A page that never stretches a word space
    has a constant word space; its band is not a result, it is the definition of ragged
    setting. The verdict is therefore printed twice -- against all five, and against the
    four that justify -- and both are in the report.

    ``sabotage`` is the liveness proof: pass an integer *n* and one justified line in *n*
    of **our** page is re-set in the raster with its last word taken away, which is what a
    breaker does when it puts one word too few on a line. All three statistics must move.
    """
    rows, ourselves_then = [], None
    for name, boxes in REFERENCE_COLUMNS.items():
        gray = np.asarray(Image.open(BLIND3 / name).convert("L")).astype(float)
        if name == "amostra_F.png":
            # Our own page as the blind set holds it -- a CYCLE 5 render. It is not a
            # reference and does not enter the verdict; it is here because it is the only
            # earlier rendering of ours that survives on disk and can be re-measured, and
            # because it does not flatter us: cycle 5 refused to justify 4 of its 42 body
            # lines, and a band computed over the lines a compositor *agreed* to justify
            # leaves out the ones it declined.
            ourselves_then = page_word_band(gray, boxes,
                                            label="(nos, ciclo 5: render antigo)",
                                            verbose=verbose)
            continue
        rows.append(page_word_band(gray, boxes, label=REFERENCE_NAMES[name],
                                   verbose=verbose))
    ours, per_page = [], {}
    for label, grays in _our_pages():
        parts = []
        for index, gray in enumerate(grays, start=1):
            if sabotage:
                gray = _sabotage(gray, REFERENCE_COLUMNS["amostra_F.png"], sabotage)
            # The page suffix only when there is more than one page to tell apart: a row
            # reading "F nossa, pt (folio 44) p1" invites a reader to look for a p2.
            part_label = f"{label} p{index}" if len(grays) > 1 else label
            parts.append(page_word_band(gray, REFERENCE_COLUMNS["amostra_F.png"],
                                        label=part_label, verbose=verbose))
        merged = _merged(parts, label) if len(parts) > 1 else parts[0]
        if len(parts) > 1:
            per_page[label] = parts
        ours.append(merged)
    print(f"banda de espaco entre palavras — {BLIND3_DPI} DPI, uma so regra para "
          f"todas as paginas" + ("   [SABOTADO]" if sabotage else ""))
    for stats in rows:
        print(_row(stats))
    for stats in ours:
        print(_row(stats))
        for part in per_page.get(stats["label"] if stats else "", ()):
            print("    " + _row(part))
    if ourselves_then is not None:
        print(_row(ourselves_then))
    good = [s for s in rows if s and not s.get("thin")]
    justifying = [s for s in good if s["justified"] >= 0.5 * s["body"]]
    ragged = [s for s in good if s not in justifying]
    mine = ours[0]
    refused = [s for s in (rows + ours) if s and s.get("undecided")]
    if refused:
        # A refusal is a failure of the instrument on that page, and it is reported as
        # one. Cycle 10's version dropped three of the four run pages here in silence.
        print(chr(10) + "PAGINAS RECUSADAS (sem limiar de vao de palavra): "
              + "; ".join(f"{s['label']} — {s.get('why', '')}" for s in refused))
    if not (mine and not mine.get("thin") and good):
        return dict(ours=mine, references=good, ours_all=ours, refused=refused,
                    passed=False)
    if ragged:
        print(chr(10) + "nao justificam (banda de espaco nao aplicavel): "
              + "; ".join(f"{s['label']} {s['justified']}/{s['body']} linhas"
                          for s in ragged))
    got = {"banda": mine["band"], "desvio": mine["std"],
           "fora": mine["outside"] / mine["lines"]}
    report = dict(ours=mine, references=good, got=got, cycle5=ourselves_then,
                  ours_all=ours, per_page=per_page, refused=refused)
    for title, group, key in (("as cinco referencias", good, "passed"),
                              ("as quatro que justificam", justifying, "passed_just")):
        if not group:
            continue
        wins = {
            "banda": all(got["banda"] < s["band"] for s in group),
            "desvio": all(got["desvio"] < s["std"] for s in group),
            "fora": all(got["fora"] < s["outside"] / s["lines"] for s in group),
        }
        medians = {
            "banda": float(np.median([s["band"] for s in group])),
            "desvio": float(np.median([s["std"] for s in group])),
            "fora": float(np.median([s["outside"] / s["lines"] for s in group])),
        }
        rest = [k for k in wins if not wins[k]]
        ok = sum(wins.values()) >= 2 and all(got[k] <= medians[k] for k in rest)
        print(chr(10) + f"criterio contra {title}: melhor que todas em pelo menos duas das tres, "
              f"e nao pior que a mediana na terceira")
        for key_name in ("banda", "desvio", "fora"):
            print(f"   {key_name:7s} nos {got[key_name]:.3f}   mediana {medians[key_name]:.3f}"
                  f"   ganha todas: {wins[key_name]}")
        print(f"   -> {'PASSA' if ok else 'NAO PASSA'} "
              f"({sum(wins.values())} de 3 ganhas)")
        report[key] = ok
        report[key + "_wins"] = wins
        report[key + "_medians"] = medians

    # Cycle 10, non-blocking nº 4: the criterion above is passed by the **Portuguese**
    # page. The English page was printed and never scored, and the report of cycle 9
    # quoted the Portuguese numbers as if they held for both. Every page of ours is now
    # put through the same criterion, printed, and returned.
    report["by_page"] = {}
    for page in ours:
        if not page or page.get("thin"):
            continue
        got_p = {"banda": page["band"], "desvio": page["std"],
                 "fora": page["outside"] / page["lines"]}
        wins_p = {
            "banda": all(got_p["banda"] < s["band"] for s in justifying),
            "desvio": all(got_p["desvio"] < s["std"] for s in justifying),
            "fora": all(got_p["fora"] < s["outside"] / s["lines"] for s in justifying),
        }
        report["by_page"][page["label"]] = dict(got=got_p, wins=wins_p,
                                                score=sum(wins_p.values()))
        print(f"   {page['label']:26s} contra as quatro que justificam: "
              f"{sum(wins_p.values())} de 3   "
              + "  ".join(f"{k} {got_p[k]:.3f} {'ganha' if wins_p[k] else 'PERDE'}"
                          for k in ("banda", "desvio", "fora")))
    return report


def _sabotage(gray: np.ndarray, boxes, every: int = 4) -> np.ndarray:
    """Set one justified line in ``every`` the way a bad breaker would, in the raster.

    The transform is the physical one, not a cosmetic one: the line's **last word is
    taken away** and the words that remain are re-set with the freed width shared equally
    among the word gaps, between the same left and right edges. That is exactly what a
    breaker does when it puts one word too few on a line -- same measure, less ink, wider
    spaces -- so if the three statistics do not move, they are not reading word spaces.

    Ink is moved, never redrawn: each word block is copied column for column to its new
    left edge.
    """
    out = gray.copy()
    ink = _ink(gray)
    pool, leads = [], []
    for _name, x0, x1, y0, y1 in boxes:
        sub = ink[y0:y1, x0:x1]
        segments = _row_bands(sub)
        steps = np.diff([s for s, _ in segments])
        leads.append(float(np.median(steps[steps > 3])) if (steps > 3).any() else 1.0)
        for top, bottom in segments:
            if not 0.30 * leads[-1] <= bottom - top + 1 <= 1.25 * leads[-1]:
                continue
            _l, _r, widths = _line_gaps(sub[top:bottom + 1])
            pool += [w for w in widths if w >= 1]
    verdict = word_gap_cut_detail(pool, float(np.median(leads)))
    if not verdict.ok:
        raise RuntimeError(
            "sabotagem impossivel: a pagina nao tem limiar de vao de palavra "
            f"({verdict.reason}). Sabotar com um corte inventado provaria nada."
        )
    cut = verdict.cut
    for _name, x0, x1, y0, y1 in boxes:
        sub = ink[y0:y1, x0:x1]
        segments = _row_bands(sub)
        leading = float(np.median(np.diff([s for s, _ in segments])))
        chosen = 0
        for top, bottom in segments:
            if not 0.30 * leading <= bottom - top + 1 <= 1.25 * leading:
                continue
            column = sub[top:bottom + 1].any(axis=0)
            filled = np.nonzero(column)[0]
            if filled.size < 40:
                continue
            left, right = int(filled[0]), int(filled[-1])
            blocks, start, run = [], left, 0
            for x in range(left, right + 2):
                on = x <= right and column[x]
                if on and run:
                    if run > cut:
                        blocks.append((start, x - run - 1))
                        start = x
                    run = 0
                elif not on:
                    run += 1
            blocks.append((start, right))
            if len(blocks) < 4:
                continue
            chosen += 1
            if chosen % every:
                continue
            keep = blocks[:-1]
            ink_width = sum(b - a + 1 for a, b in keep)
            gap = (right - left + 1 - ink_width) / (len(keep) - 1)
            strip = out[y0 + top:y0 + bottom + 1, x0:x1]
            source = strip.copy()
            strip[:, left:right + 1] = 255.0
            cursor = float(left)
            for a, b in keep:
                at = int(round(cursor))
                strip[:, at:at + (b - a + 1)] = np.minimum(
                    strip[:, at:at + (b - a + 1)], source[:, a:b + 1])
                cursor += (b - a + 1) + gap
    return out

# --------------------------------------------------------------------------- #
# What total fit is worth: the breaker against itself
# --------------------------------------------------------------------------- #
def first_fit(runs, *, width_mm, size_mm, metrics, first_indent_mm=0.0,
              **_kw):  # noqa: ANN001, ANN201
    """The breaker cycle 7 replaced, kept so the comparison can be re-run.

    Fill each line as far as it goes and let the last one take what is left. No
    hyphenation, no lookahead, no cost.
    """
    words = tp._split_words(runs)
    space = tp.measure_runs([tp.Run("text", " ")], size_mm, metrics)
    groups, current, ink = [], [], 0.0
    for word in words:
        width = tp.measure_runs(word, size_mm, metrics)
        room = width_mm - (first_indent_mm if not groups else 0.0)
        if current and ink + len(current) * space + width > room:
            groups.append((current, ink))
            current, ink = [], 0.0
        current.append(word)
        ink += width
    if current:
        groups.append((current, ink))
    out = []
    for index, (group, ink) in enumerate(groups):
        last = index == len(groups) - 1
        run_list = []
        for k, word in enumerate(group):
            if k:
                run_list.append(tp.Run("text", " "))
            run_list.extend(word)
        room = width_mm - (first_indent_mm if index == 0 else 0.0)
        gaps = len(group) - 1
        ratio = 1.0 if (last or not gaps) else (room - ink) / (gaps * space)
        out.append(tp.SetLine(tp._merge(run_list),
                              tp.measure_runs(run_list, size_mm, metrics),
                              is_last=last, justify=not last, space_ratio=ratio))
    return out


def measure_breaker() -> None:
    """The word-space band at the SOURCE, where the breaker's own decision is readable.

    `SetLine.space_ratio` is the number the canvas is told to set, so this measurement has
    no rasteriser, no threshold and no column box in it. Four settings on the same two
    book sources:

    * the delivered breaker;
    * the same breaker with the cycle-6 hyphen minimums (3/3 instead of 2/3);
    * the same breaker with the cycle-6 glue shrink (a third instead of a fifth);
    * a first-fit breaker in the same composer.

    It also prints the arithmetic of the one line neither the breaker nor any breaker can
    improve -- the fifteen-token move block of the English page.
    """
    import typeset_proofsheet as ps
    from caissa.typeset import typography as typo

    original = tp.break_paragraph
    log: list[tuple[float, bool]] = []

    def spy(breaker):  # noqa: ANN001, ANN202
        def wrapped(runs, **kwargs):  # noqa: ANN001, ANN202
            lines = breaker(runs, **kwargs)
            if kwargs.get("size_mm", 0) > 2.5:
                log.extend((line.space_ratio, line.justify) for line in lines)
            return lines
        return wrapped

    base = typo.Hyphenator

    def run(label: str, breaker=None, left=None, **constants) -> None:  # noqa: ANN001
        saved = {k: getattr(tp, k) for k in constants}
        for key, value in constants.items():
            setattr(tp, key, value)
        if left is not None:
            ps.book_hyphenator = lambda lang, _l=left: base(lang, left=_l, right=3)
        cells = []
        for name, factory, language in (("en", ps.book_source_mareco, "en"),
                                        ("pt", ps.book_source_rios, "pt")):
            log.clear()
            wrapped = spy(breaker or original)
            tp.break_paragraph = wrapped
            ps.tp.break_paragraph = wrapped
            try:
                ps.compose_book_page("book", source=factory(),
                                     diagram_theme="hatched", page_number=44,
                                     running_head="H", language=language)
            finally:
                tp.break_paragraph = original
                ps.tp.break_paragraph = original
            ratios = np.array([r for r, justified in log if justified])
            outside = int(((ratios < BAND_FLOOR) | (ratios > BAND_CEILING)).sum())
            cells.append(f"{name} {ratios.min():.2f}-{ratios.max():.2f} "
                         f"banda {ratios.max() / ratios.min():.2f} "
                         f"dp {ratios.std():.3f} fora {outside}/{len(ratios)}")
        print(f"{label:34s} | " + " | ".join(cells))
        for key, value in saved.items():
            setattr(tp, key, value)
        ps.book_hyphenator = lambda lang: base(lang, left=ps.LEFT_HYPHEN_MIN,
                                               right=ps.RIGHT_HYPHEN_MIN)

    print("banda de espaco entre palavras na FONTE (SetLine.space_ratio)")
    run("ciclo 7 (entregue)")
    run("o mesmo, com hifen 3/3", left=3)
    run("o mesmo, com encolhimento 1/3", SPACE_SHRINK=1.0 / 3.0)
    run("first fit no mesmo compositor", breaker=first_fit)

    font, metrics = tp.metrics_for("merida")
    size = 8.6 * 25.4 / 72.0
    width = 63.45
    text = ("**6.Bg2 0-0 7.Ngf3 b6 8.0-0 Bb7 9.Rc1 Nbd7 10.cxd5 exd5 11.Ne5 c5 "
            "12.Nxd7 Nxd7 13.dxc5**")
    words = tp._split_words(tp.parse_markup(tp.prepared(text, "en")))
    space = tp.measure_runs([tp.Run("text", " ")], size, metrics)
    widths = [tp.measure_runs(w, size, metrics) for w in words]
    print(f"\na linha de lances da pagina inglesa: {len(words)} fichas indivisiveis, "
          f"medida {width} mm, espaco nominal {space:.3f} mm")
    for count in (7, 8, 9):
        ink = sum(widths[:count])
        print(f"   {count} fichas na 1a linha: tinta {ink:.2f} mm, {count - 1} vaos, "
              f"razao {(width - ink) / ((count - 1) * space):.3f} do nominal")
    print(f"   piso absoluto de encolhimento: {tp.ABS_MIN_SPACE_RATIO:.2f}")

def measure_indent(pdf, page_number: int = 0):
    """Q4.4. Every line of an indented block carries the block's indent.

    Measured on the composition, which is the only place the *blocks* are known -- a PDF
    has lines and no idea which of them belong together -- and then confirmed against the
    delivered page by matching the drawn x of each line.

    The critic's measurement: the sub-variation `22...g6 23.Qxh7+! ...` sat at 9.46 pt of
    indent and its continuation `25.Rh8#` at 0.00 pt, under the main line's margin, where
    a chess reader reads it as a new main-line move.
    """
    import typeset_proofsheet as ps

    composition = ps.compose_book_page("book", diagram_theme="hatched")
    geometry = ps.book_geometry()
    style_size = ps.BODY_PT * 25.4 / 72.0
    leading = style_size * 1.21
    bad = 0
    blocks: dict[str, list[tuple[float, float, float]]] = {}
    for index, column in enumerate(composition.columns):
        x = geometry.column_x(index % geometry.columns, index // geometry.columns)
        for placed in column.atoms:
            atom = placed.atom
            if atom.kind != "line":
                continue
            top = geometry.text_top + (placed.slot - 1) * leading
            blocks.setdefault(atom.label.split("#")[0], []).append(
                (top, atom.indent, x))
    print(f"{'bloco':22s} {'linhas':>7s} {'1a linha':>10s} {'restantes':>10s}  (pt)")
    for label, entries in blocks.items():
        entries.sort()
        if len(entries) < 2:
            continue
        # Indent relative to the COLUMN's own margin, not to the block's smallest line:
        # relative to the block, an indented block reads as no indent at all.
        first_pt = entries[0][1] * 72.0 / 25.4
        least = min(indent for _, indent, _ in entries[1:]) * 72.0 / 25.4
        kind = label.split(":")[0]
        # Q4.4 is about indented BLOCKS. A first-line indent is the mark that opens a
        # paragraph of prose and is meant to be alone; a variation is set as a block and
        # every one of its lines carries the indent.
        if kind == "variation" and least < first_pt - 0.1:
            bad += 1
            print(f"    {label}: primeira linha {first_pt:.2f} pt, continuacao "
                  f"{least:.2f} pt")
        print(f"{label:22s} {len(entries):7d} {first_pt:10.2f} {least:10.2f}")
    print(f"blocos recuados cuja continuacao volta a margem: {bad}   (criterio: 0)")
    return bad


def measure_grid(pdf, page_number: int = 0, leading_pt: float = 10.406,
                 body_pt: float = 8.6):
    """Q5 candidate 1. Baseline grid: occupancy and registration across the gutter.

    The critic's two numbers on the delivered page were 45 % occupancy and 41 %
    registration, against 100 %/100 % on a scanned Gambit page. Occupancy is the share of
    the column's grid slots that carry a baseline, counting only the slots that are not
    taken by a diagram; registration is the share of the shorter column's baselines that
    have a baseline of the other column on the same grid line.
    """
    doc = pymupdf.open(pdf)
    if not page_number:
        page_number = doc.page_count - 2
    page = doc[page_number - 1]
    mid = page.rect.width / 2.0
    baselines = ([], [])
    diagrams = ([], [])
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            for span in line["spans"]:
                if abs(span["size"] - body_pt) > 0.2:
                    continue
                baselines[0 if span["bbox"][0] < mid else 1].append(
                    round(span["origin"][1], 3))
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.width > 60 and rect.height > 60 and rect.width < 0.9 * page.rect.width:
            diagrams[0 if rect.x0 < mid else 1].append((rect.y0, rect.y1))
    origin = min(min(side) for side in baselines if side)
    on_grid = ([], [])
    for side in (0, 1):
        unique = sorted(set(baselines[side]))
        for y in unique:
            phase = (y - origin) % leading_pt
            if min(phase, leading_pt - phase) < 0.05:
                on_grid[side].append(round((y - origin) / leading_pt))
        if not unique:
            continue
        span = max(unique) - origin
        slots = int(round(span / leading_pt)) + 1
        merged = []
        for top, bottom in sorted(diagrams[side]):
            if merged and top <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], bottom))
            else:
                merged.append((top, bottom))
        blocked = sum(int(round((b - t) / leading_pt)) for t, b in merged)
        occupancy = len(unique) / max(1, slots - blocked)
        print(f"coluna {'esquerda' if side == 0 else 'direita ':8s}: "
              f"{len(unique)} linhas de base, {len(on_grid[side])} na grade de "
              f"{leading_pt:.3f} pt, {slots} casas, {blocked} tomadas por diagrama, "
              f"ocupacao {occupancy * 100:.0f} %")
    left, right = set(on_grid[0]), set(on_grid[1])
    shared = left & right
    smaller = min(len(left), len(right)) or 1
    print(f"registo atraves da calha: {len(shared)} de {smaller} = "
          f"{len(shared) / smaller * 100:.0f} %   (ciclo 2: 41 %; amostra F: 100 %)")
    doc.close()
    return len(on_grid[0]), len(on_grid[1]), len(shared)


def measure_highlight() -> None:
    """Does a highlighted light square still differ from a highlighted dark one?"""
    print(f"{'tema':14s} {'clara':>7} {'escura':>7} {'delta':>7} | "
          f"{'HL clara':>9} {'HL escura':>9} {'delta':>7}")
    for key, theme in bs.THEMES.items():
        style = DiagramStyle(font="merida", width_mm=62, theme=key,
                             coordinates=CoordinateStyle.NONE)
        lay = bs._layout(style)
        svg = bs.render_svg(
            "8/8/8/8/8/8/8/8 w - - 0 1", style,
            marks=[SquareHighlight("c5"), SquareHighlight("d5")],
        )
        image = raster(svg, dpi=DPI)

        def sample(square: str) -> float:
            x, y = bs._square_xy(lay, square, False)
            cx, cy = (x + lay.square * 0.5) * PX, (y + lay.square * 0.5) * PX
            return float(image[int(cy) - 2 : int(cy) + 3, int(cx) - 2 : int(cx) + 3].mean())

        # c4 is a light square and d4 a dark one; c5 (dark) and d5 (light) are the two
        # that carry the highlight. Getting this pair the wrong way round inverts the
        # sign of every delta in the table.
        light, dark = sample("c4"), sample("d4")
        hl, hd = sample("d5"), sample("c5")
        print(f"{key:14s} {light:7.1f} {dark:7.1f} {light - dark:7.1f} | "
              f"{hl:9.1f} {hd:9.1f} {hl - hd:7.1f}")


# --------------------------------------------------------------------------- #
# P1 -- the page bottom, and the column feet
# --------------------------------------------------------------------------- #
def content_bottom(page) -> tuple[float, str]:  # noqa: ANN001
    """Lowest inked y on a page, ignoring the page-colour backdrop.

    The backdrop is a rect covering the whole trim; it is the paper, not content, and
    including it would make the criterion unsatisfiable for any page with a background.
    """
    lowest, what = 0.0, ""
    full = page.rect
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if (abs(rect.width - full.width) < 1.0 and abs(rect.height - full.height) < 1.0):
            continue
        if rect.y1 > lowest:
            lowest, what = rect.y1, f"desenho {drawing['type']}"
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["bbox"][3] > lowest:
                    lowest, what = span["bbox"][3], f"texto {span['text'][:22]!r}"
    return lowest, what


def measure_bottom(pdf: Path, bottom_mm: float = 16.0) -> int:
    doc = pymupdf.open(pdf)
    limit_offset = bottom_mm * MM
    worst = -1e9
    bad = 0
    print(f"{'pg':>3} {'altura':>8} {'limite':>8} {'mais baixo':>11} {'folga mm':>9}  o que")
    for number, page in enumerate(doc, start=1):
        limit = page.rect.height - limit_offset
        lowest, what = content_bottom(page)
        slack = (limit - lowest) / MM
        worst = max(worst, lowest - limit)
        flag = "" if lowest <= limit + 1e-6 else "  *** FORA DA PAGINA"
        if flag:
            bad += 1
        print(f"{number:3d} {page.rect.height:8.1f} {limit:8.1f} {lowest:11.1f} "
              f"{slack:9.2f}  {what}{flag}")
    print(f"\n{doc.page_count} paginas, {bad} com conteudo abaixo da margem inferior. "
          f"Pior transbordo: {max(0.0, worst) / MM:.2f} mm")
    doc.close()
    return bad


def _bands(page, columns: int = 1) -> "list[list[tuple[float, float, str]]]":  # noqa: ANN001
    """Ink bands per column, merged, in points. The critic's method (`holes.py`).

    ``columns`` > 1 splits at the page's middle, which is what makes a hole inside one
    column of a two-column page visible; measured page-wide, two columns hide each
    other's holes.
    """
    rect = page.rect
    mid = rect.width / 2.0
    groups: list[list[tuple[float, float, str]]] = [[] for _ in range(columns)]

    def side(x0: float, x1: float) -> int:
        if columns == 1:
            return 0
        return 0 if (x0 + x1) / 2.0 < mid else 1

    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.width > 0.97 * rect.width and r.height > 0.97 * rect.height:
            continue
        groups[side(r.x0, r.x1)].append((r.y0, r.y1, "desenho"))
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                groups[side(x0, x1)].append((y0, y1, span["text"][:28]))
    out = []
    for items in groups:
        items.sort()
        bands: list[tuple[float, float, str]] = []
        for y0, y1, what in items:
            if bands and y0 <= bands[-1][1] + 0.5:
                top, bottom, label = bands[-1]
                bands[-1] = (top, max(bottom, y1), label)
            else:
                bands.append((y0, y1, what))
        out.append(bands)
    return out


def _line_boxes(page, columns: int = 2):  # noqa: ANN001, ANN201
    """Per column, one box for every band of type: ``(top, bottom, left, right, text,
    bold_fraction)``.

    Text spans *and* drawings, because a figurine is a path: a move line that opens with
    one would otherwise be reported as starting a character-width right of where it is.
    Diagram bands are dropped by height.
    """
    rect = page.rect
    mid = rect.width / 2.0
    groups = [[] for _ in range(columns)]

    def side(x0: float, x1: float) -> int:
        return 0 if columns == 1 or (x0 + x1) / 2.0 < mid else 1

    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.width > 0.97 * rect.width and r.height > 0.97 * rect.height:
            continue
        groups[side(r.x0, r.x1)].append([r.y0, r.y1, r.x0, r.x1, "", 0.0, 0.0])
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                n = float(len(span["text"]))
                bold = n if ("Bold" in span["font"] or span["flags"] & 16) else 0.0
                groups[side(x0, x1)].append([y0, y1, x0, x1, span["text"], bold, n])
    out = []
    for items in groups:
        items.sort()
        bands = []
        for y0, y1, x0, x1, what, bold, n in items:
            if bands and y0 <= bands[-1][1] + 0.5:
                b = bands[-1]
                b[1] = max(b[1], y1); b[2] = min(b[2], x0); b[3] = max(b[3], x1)
                b[4] += what; b[5] += bold; b[6] += n
            else:
                bands.append([y0, y1, x0, x1, what, bold, n])
        out.append([(b[0], b[1], b[2], b[3], b[4], (b[5] / b[6] if b[6] else 0.0))
                    for b in bands if 4.0 <= b[1] - b[0] <= 16.0])
    return out


def measure_midshort(pdf, pages: str = "", floor: float = 0.94, quiet: bool = False):
    """R1. Mid-paragraph lines that do not reach the measure -- the critic's instrument.

    `critique/c5/midshort.py` runs this on a raster of each blind sample; the same rule is
    applied here to the PDF's own geometry, which is that measurement without the
    rasteriser's one-pixel slop. A line and the line under it belong to the same paragraph
    unless one of four things says otherwise:

    * the next line's left edge sits past the column margin -- it **opens** a paragraph;
    * the vertical step to it is more than 1.6 pitches -- the block **ended**;
    * the next line is set in a different weight. This is the false-positive class the
      critic found by eye in reference D and threw out by hand -- *"linhas finais de
      paragrafo seguidas de uma linha de lances em negrito rente a margem"*. On our page
      it is every prose paragraph that ends above a bold move line, and it is decided
      here by the span's own font name, not by eye;
    * either line is **centred** (both margins clear, and equal) -- a venue line or a
      cross-head is not a justified body line at all.

    None of the four can hide the defect R1 names, which is a short line *inside* a
    running paragraph: there the line below is flush, one pitch down, and in the same
    face. The critic measured `0 of 37`, `0 of 34`, `0 of 80`, `0 of 53` in references A,
    B, C and D and `5 of 37` on our cycle-5 page, worst **0.55**.

    This is also the count of lines the compositor **refused to justify**, which is why
    `wordspace` prints it beside its own number: a word-space figure that leaves the
    refusals out is not a word-space figure.
    """
    doc = pymupdf.open(pdf)
    wanted = [int(v) for v in pages.split(",") if v.strip()] or list(
        range(1, doc.page_count + 1))
    total = short = 0
    dropped = {"opener": 0, "block end": 0, "weight": 0, "centred": 0}
    worst = (1.0, 0, 0.0, "")
    for number in wanted:
        page = doc[number - 1]
        for index, bands in enumerate(_line_boxes(page)):
            if len(bands) < 6:
                continue
            left = Counter(round(b[2], 1) for b in bands).most_common(1)[0][0]
            right = Counter(round(b[3], 1) for b in bands).most_common(1)[0][0]
            measure = right - left
            if measure <= 0:
                continue
            pitch = float(np.median(np.diff([b[0] for b in bands]))) or 1.0
            slop = 0.03 * measure

            def centred(b, _l=left, _r=right, _s=slop, _m=measure) -> bool:
                return (b[2] > _l + _s and b[3] < _r - _s
                        and abs((b[2] - _l) - (_r - b[3])) < 0.06 * _m)

            for i in range(len(bands) - 1):
                here, nxt = bands[i], bands[i + 1]
                if nxt[0] - here[0] > 1.6 * pitch:
                    dropped["block end"] += 1
                    continue
                if nxt[2] > left + slop and not centred(nxt):
                    dropped["opener"] += 1
                    continue
                if centred(here) or centred(nxt):
                    dropped["centred"] += 1
                    continue
                if abs(here[5] - nxt[5]) > 0.5:
                    dropped["weight"] += 1
                    continue
                fill = (here[3] - left) / measure
                total += 1
                if fill < floor:
                    short += 1
                    if not quiet:
                        print(f"    p{number} col{index} y={here[0]:7.2f} "
                              f"fill {fill:.2f}  |{here[4][:46]}|")
                if fill < worst[0]:
                    worst = (fill, number, here[0], here[4][:46])
    doc.close()
    if not quiet:
        print(f"{total} linhas de meio de paragrafo; {short} abaixo de {floor:.2f} da "
              f"medida; a mais curta a {worst[0]:.2f}"
              + (f"  |{worst[3]}|" if worst[0] < 1.0 else ""))
        print("   nao contadas: " + ", ".join(f"{k} {v}" for k, v in dropped.items()))
    return short, total, worst


# --------------------------------------------------------------------------- #
# R5 -- the folio sits on the OUTER margin of its own leaf
# --------------------------------------------------------------------------- #
FOLIO_BAND_MM = 20.0
"""Above this is running-head furniture and nothing else: the head and the folio."""

FOLIO_TOL_MM = 0.05
"""How far a folio may sit from its outer margin. The composer places it by arithmetic,
so the only slack is the PDF writer's rounding; measured on the delivered sheet it is
0.00 mm."""

FOLIOS_EXPECTED = 7
"""Three on `proofsheet.pdf` (44/45/46) and four on `proofsheet_run.pdf` (44-47)."""


def folio_spans(doc, pages=None):  # noqa: ANN001, ANN201
    """``(page, number, x0_mm, x1_mm, width_mm)`` for every folio in the head band.

    PyMuPDF reports `bbox` in POINTS. The cycle-8 critique's reproduction snippet filters
    on `s['bbox'][1] < 14` and this sheet sets its folio at `bbox[1] = 22.85 pt`, so that
    snippet as published matches nothing; the threshold here is in millimetres.
    """
    out = []
    for index in (range(doc.page_count) if pages is None else pages):
        page = doc[index]
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if span["bbox"][1] / MM > FOLIO_BAND_MM or not text.isdigit():
                        continue
                    out.append((index, int(text), span["bbox"][0] / MM,
                                span["bbox"][2] / MM, page.rect.width / MM))
    return out


def folio_defects(doc, pages=None, outer_mm: float | None = None):  # noqa: ANN001, ANN201
    """Folios that are NOT flush to the outer margin of their own leaf.

    A verso carries an even folio and the outer edge of a verso is the LEFT edge; a recto
    carries an odd folio and its outer edge is the RIGHT one. Cycle 8 wrote every folio at
    `geometry.outer` from the left, so page 45 of the delivered sheet -- a recto -- carried
    its number 129.6 mm from where a bound book puts it, against the spine, and the critic
    identified our blind sample by it before looking at a single typographic detail
    (`F7_CRITIQUE_C8.md`, blocking nº 1).
    """
    if outer_mm is None:
        import typeset_proofsheet as ps

        outer_mm = ps.BOOK_OUTER_MM
    defects = []
    for index, number, x0, x1, width in folio_spans(doc, pages):
        if number % 2:                      # recto: flush right
            got, side = width - x1, "direita"
        else:                               # verso: flush left
            got, side = x0, "esquerda"
        if abs(got - outer_mm) > FOLIO_TOL_MM:
            kind = "impar/recto" if number % 2 else "par/verso"
            defects.append(
                f"p{index + 1}: folio {number} ({kind}) devia ficar a {outer_mm:.1f} mm "
                f"da margem {side}; esta a {got:.2f} mm "
                f"(x={x0:.2f}-{x1:.2f} de {width:.1f} mm)"
            )
    return defects


def measure_folio(verbose: bool = False, sabotage: bool = False) -> dict:
    """R5. The folio of every book page is flush to the outer margin of its leaf.

    Two artefacts, one rule. The delivered `proofsheet.pdf` numbers a real run 44/45/46 on
    its last three pages; `proofsheet_run.pdf` is four consecutive folios inside ONE
    composition, so `decorate(canvas, index)` is exercised for index 0..3 and not only for
    0. Both are read the same way, from the PDF's own spans.

    ``sabotage=True`` recomposes the run with `mirror_margins=False` -- which is exactly
    what cycle 8 shipped by omission, every page set as a verso -- and measures that
    instead. The verdict must flip, and it must flip on the rectos and on nothing else.
    A gate that has never been seen to fire is indistinguishable from a blind one.
    """
    import tempfile

    import typeset_proofsheet as ps

    outer = ps.BOOK_OUTER_MM
    sheet = ROOT / "benchmarks" / "reports" / "proofsheet.pdf"
    run = ROOT / "benchmarks" / "reports" / "proofsheet_run.pdf"
    tmp = None
    if sabotage:
        tmp = Path(tempfile.mkdtemp()) / "run_sabotado.pdf"
        tp.pages_to_pdf(ps.compose_book_run(mirror_margins=False).pages, str(tmp))
        run = tmp

    report: dict = {"outer_mm": outer, "sabotage": sabotage, "sources": []}
    defects: list[str] = []
    rows: list[tuple] = []
    for path, pages, label in (
        (sheet, [n - 1 for n in (int(p) for p in _book_pages(sheet).split(","))],
         "proofsheet.pdf (paginas de livro)"),
        (run, None, ("proofsheet_run.pdf" if not sabotage
                     else "corrida SABOTADA (mirror_margins=False)")),
    ):
        if not Path(path).exists():
            defects.append(f"{label}: {path} nao existe")
            continue
        with pymupdf.open(path) as doc:
            spans = folio_spans(doc, pages)
            bad = folio_defects(doc, pages, outer_mm=outer)
        report["sources"].append({"label": label, "folios": [s[1] for s in spans],
                                 "defects": bad})
        defects += bad
        rows += [(label, *s) for s in spans]

    report["defects"] = defects
    # A parity check that finds no folios is not a passing parity check: three on the
    # sheet, four on the run. Without this the gate goes green the day the folio stops
    # being printed at all, which is the failure mode of every "no defects found" test.
    report["passed"] = not defects and len(rows) >= FOLIOS_EXPECTED
    if verbose:
        print(f"fólio na margem exterior — margem declarada {outer:.1f} mm, "
              f"tolerância {FOLIO_TOL_MM:.2f} mm")
        seen = None
        for label, _index, number, x0, x1, width in rows:
            if label != seen:
                print(f"  {label}")
                seen = label
            kind = "impar/recto" if number % 2 else "par/verso"
            edge = (width - x1) if number % 2 else x0
            side = "direita" if number % 2 else "esquerda"
            mark = "OK " if abs(edge - outer) <= FOLIO_TOL_MM else "ERRADO"
            print(f"    folio {number:>4}  {kind:<11}  x = {x0:7.2f}–{x1:7.2f} mm de "
                  f"{width:.1f}   margem {side:<8} {edge:6.2f} mm   [{mark}]")
        print(f"  {len(rows)} fólios lidos, {len(defects)} defeito(s)")
        for line in defects:
            print("    " + line)
        print("  -> " + ("PASSA" if report["passed"] else "NAO PASSA"))
    if tmp is not None:
        tmp.unlink(missing_ok=True)
    return report


TYPE_AREA_TOL_MM = 0.15
"""How far ink may sit outside the type area before it is a defect, in millimetres.

One pixel at 300 DPI is 0.085 mm and the rasteriser antialiases over the next one, so a
rule drawn exactly on the edge reads as 0.08-0.12 mm past it. Anything above this is
ink placed outside the measure, not ink rounded outside it."""

TYPE_AREA_DPI = 300


def type_area_defects(pdf: Path, *, dpi: int = TYPE_AREA_DPI,
                      tol: float = TYPE_AREA_TOL_MM,
                      verbose: bool = False) -> list[tuple[int, str, float, float]]:
    """Every page of ``pdf`` whose ink leaves the type area, with how far, in mm.

    Q: "nothing outside the type area." Cycle 9 wrote that sentence after saying it had
    looked at all eighteen pages with its eyes; the cycle-10 critic measured
    `proofsheet.pdf` p4 and found the `outside_right` coordinate specimen putting ink
    **2.45 to 4.10 mm** past the right edge of the measure. The sentence was false and
    nothing in the suite could have contradicted it, because nothing measured it.

    Three things this does that the eye did not:

    * it reads the ink **raster**, not the text spans, so a rule, a board frame and a
      coordinate digit all count -- the p4 overflow is a text span, but the cycle-2
      gallery overflow that started all this was a drawing;
    * it measures **every** page, and prints every page, so a clean report cannot be a
      report of the pages somebody chose;
    * it handles the dark page by the same rule as the light ones. The dark theme fills
      the whole leaf with ink-coloured paper, so a naive threshold calls the entire page
      ink and the page can never be measured. `_ink` takes the minority class, which is
      the text; the page-wide background is excluded as background because it is the
      majority.

    Returns ``(page, side, overflow_mm, ink_edge_mm)`` per defect, empty when clean.
    """
    import typeset_proofsheet as ps

    # Which geometry a page was set in is not read off the page number: the gallery and
    # the book declare the same outer margin, and the instrument asserts that instead of
    # picking one and hoping. If they ever diverge, this raises rather than measuring the
    # wrong page against the wrong measure -- which is the failure `_our_pages` had.
    geometries = [ps.gallery_geometry(), ps.book_geometry()]
    edges = {(round(g.left_margin(0), 4), round(g.width - g.right_margin(0), 4))
             for g in geometries}
    if len(edges) != 1:
        raise RuntimeError(
            "galeria e livro declaram manchas diferentes " + repr(sorted(edges))
            + "; este instrumento precisa saber em qual geometria cada pagina foi posta."
        )
    left, right = next(iter(edges))
    geo = geometries[0]
    doc = pymupdf.open(pdf)
    out: list[tuple[int, str, float, float]] = []
    scale = 25.4 / dpi
    for number, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width).astype(float)
        ink = _ink(gray)
        # Crop to the declared trim before looking. The leaf is 160.9 mm, which at
        # 300 DPI is 1900.39 pixels, so PyMuPDF returns 1901 columns and the last one is
        # a 0.39-pixel blend of the page background with the white behind the pixmap. On
        # the dark page that fringe reads 175 against a 30 background -- the minority
        # class, i.e. "ink" -- and it made the instrument report 14.05 mm of overflow on
        # a page that has none. It is an artefact of the raster, not of the page.
        inside = int(geo.width / scale)
        ink = ink[:, :inside]
        columns = np.nonzero(ink.any(axis=0))[0]
        if columns.size == 0:
            if verbose:
                print(f"  p{number:2d}: sem tinta")
            continue
        x0, x1 = columns[0] * scale, (columns[-1] + 1) * scale
        over_left, over_right = left - x0, x1 - right
        marks = []
        if over_left > tol:
            out.append((number, "esquerda", over_left, x0))
            marks.append(f"esq {over_left:+.2f} mm")
        if over_right > tol:
            out.append((number, "direita", over_right, x1))
            marks.append(f"dir {over_right:+.2f} mm")
        if verbose:
            print(f"  p{number:2d}: mancha {left:6.2f}..{right:6.2f}   tinta "
                  f"{x0:6.2f}..{x1:6.2f}"
                  + ("   FORA: " + ", ".join(marks) if marks else ""))
    doc.close()
    return out


def measure_type_area(pdf: Path, *, sabotage: int = 0) -> dict:
    """CLI wrapper for `type_area_defects`, with its own liveness handle.

    ``sabotage`` shrinks the declared type area by that many millimetres on each side,
    which must make every page of a full sheet a defect. A gate that has never been seen
    to fire is indistinguishable from one that cannot.
    """
    tol = TYPE_AREA_TOL_MM + (0.0 if not sabotage else -float(sabotage))
    print(f"tinta fora da mancha — {pdf.name}, {TYPE_AREA_DPI} DPI, tolerancia "
          f"{tol:.2f} mm" + ("   [SABOTADO]" if sabotage else ""))
    defects = type_area_defects(pdf, tol=tol, verbose=True)
    print(f"{len(defects)} transbordo(s) -> "
          f"{'NAO PASSA' if defects else 'PASSA'}")
    for number, side, over, edge in defects:
        print(f"  p{number}: {over:.2f} mm fora pela {side} (tinta ate {edge:.2f} mm)")
    return dict(defects=defects, passed=not defects)


def _book_pages(pdf, count: int = 3) -> str:
    """The last ``count`` pages of the proof sheet: the two-column book pages.

    Derived, not hardcoded. The specimen sections ahead of them grow and shrink between
    cycles, and a hardcoded page number is how a measurement quietly starts reporting the
    wrong page.
    """
    doc = pymupdf.open(pdf)
    total = doc.page_count
    doc.close()
    return ",".join(str(n) for n in range(total - count + 1, total + 1))


def measure_holes(pdf: Path, leading_pt: float = 10.406, book_pages: str = "",
                  book_leading_pt: float = 10.406, columns: int = 2) -> float:
    """Every internal white gap, in millimetres AND in leadings. Q4.1.

    Cycle 2 bought column feet of 0.000 mm by pouring the slack into the body: nine of
    twelve pages carried a page-wide hole of 8 mm or more and page 8 carried 35.6 mm and
    27.8 mm. This prints every hole, not only the ones over 8 mm, and says which band it
    sits under -- so the number cannot be quoted without its cause.
    """
    doc = pymupdf.open(pdf)
    book = {int(v) for v in book_pages.split(",") if v.strip()}
    worst = 0.0
    print(f"{'pg':>3} {'topo':>7} {'pe':>7}  vaos internos (mm / entrelinhas)")
    for number, page in enumerate(doc, start=1):
        lead = book_leading_pt if number in book else leading_pt
        cols = columns if number in book else 1
        rows = []
        for index, bands in enumerate(_bands(page, cols)):
            for i in range(len(bands) - 1):
                gap = bands[i + 1][0] - bands[i][1]
                if gap <= 0.5:
                    continue
                rows.append((gap, index, bands[i][2], bands[i + 1][2]))
        rows.sort(reverse=True)
        first = min((b[0][0] for b in _bands(page, 1) if b), default=0.0)
        last = max((b[-1][1] for b in _bands(page, 1) if b), default=0.0)
        biggest = rows[0][0] if rows else 0.0
        worst = max(worst, biggest / lead)
        shown = ", ".join(
            f"{g / MM:.1f} mm = {g / lead:.2f}el [{a!r}->{b!r}]"
            for g, _, a, b in rows[:2]
        )
        print(f"{number:3d} {first / MM:6.1f} {(page.rect.height - last) / MM:6.1f}  {shown}")
    print(f"\nMaior vao interno: {worst:.2f} entrelinhas "
          f"(teto: 2 numa pagina de livro, 4 numa folha de especimes)")
    doc.close()
    return worst


def measure_feet(pdf: Path, pages: str = "", columns: int = 2,
                 bottom_mm: float = 16.0) -> None:
    """Difference between the feet of the columns of a two-column page, in mm.

    Reference pages measure 0.0, 1.8, 4.6 and 10.7 mm (critic, cycle 1).

    **Every page is reported.** Cycle 2's report showed three rows and the critic ran the
    same tool and found `p2 44.073 mm`, `p4 30.750 mm`: the number was true of the pages
    quoted and not of the document. The specimen pages are set in ONE column, where a
    "difference between the column feet" has no meaning, so they are reported as what
    they are -- one foot and its slack to the bottom margin.
    """
    doc = pymupdf.open(pdf)
    wanted = [int(v) for v in pages.split(",") if v.strip()] or list(
        range(1, doc.page_count + 1)
    )
    book = set(int(v) for v in _book_pages(pdf).split(","))
    for number in wanted:
        if number not in book:
            page = doc[number - 1]
            lowest, _ = content_bottom(page)
            print(f"p{number:<3d} uma coluna: pe {lowest:.1f} pt, folga ate a margem "
                  f"{(page.rect.height - bottom_mm * MM - lowest) / MM:.1f} mm")
            continue
        page = doc[number - 1]
        mid = page.rect.width / 2.0
        feet = [0.0] * columns
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    x0, _, x1, y1 = span["bbox"]
                    if y1 > page.rect.height - bottom_mm * MM + 1:
                        continue
                    side = 0 if (x0 + x1) / 2.0 < mid else 1
                    feet[side] = max(feet[side], y1)
        for drawing in page.get_drawings():
            rect = drawing["rect"]
            if abs(rect.width - page.rect.width) < 1.0:
                continue
            side = 0 if rect.x0 + rect.width / 2.0 < mid else 1
            feet[side] = max(feet[side], rect.y1)
        if min(feet) <= 0:
            continue
        print(f"p{number:<3d} pes das colunas: "
              + "  ".join(f"{f:.1f} pt" for f in feet)
              + f"   diferenca {abs(feet[0] - feet[1]) / MM:.3f} mm")
    doc.close()


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("what", choices=[
        "bottom", "feet", "frames", "coords", "hatch", "figurine", "marks", "highlight",
        "holes", "inside", "counters", "wordspace", "indent", "grid", "latexmarks",
        "midshort", "figset", "wordband", "breaker", "folio", "typearea",
    ])
    parser.add_argument("--pdf", default=str(ROOT / "benchmarks" / "reports" / "proofsheet.pdf"))
    parser.add_argument("--pages", default="")
    parser.add_argument("--sabotage", type=int, default=0,
                        help="wordband: prove the gate fires by setting one justified "
                             "line in four with its last word removed. "
                             "folio: prove it fires by recomposing the run with "
                             "mirror_margins=False, which is the cycle-8 state")
    args = parser.parse_args(argv)
    pdf = Path(args.pdf)

    if args.what == "latexmarks":
        measure_latex_marks()
        return 0
    if args.what == "inside":
        measure_inside()
        return 0
    if args.what == "counters":
        measure_counters()
        return 0
    if args.what == "figset":
        worst, _ = measure_figset()
        return 1 if worst > 0.08 else 0
    if args.what == "breaker":
        measure_breaker()
        return 0
    if args.what == "wordband":
        report = measure_wordband(verbose=True, sabotage=args.sabotage)
        return 0 if report.get("passed") else 1
    if args.what == "folio":
        report = measure_folio(verbose=True, sabotage=bool(args.sabotage))
        return 0 if report.get("passed") else 1
    if args.what == "typearea":
        report = measure_type_area(pdf, sabotage=args.sabotage)
        return 0 if report.get("passed") else 1
    if args.what == "wordspace":
        measure_wordspace(pdf, args.pages or _book_pages(pdf))
        return 0
    if args.what == "midshort":
        short, _, _ = measure_midshort(pdf, args.pages or _book_pages(pdf))
        return 1 if short else 0
    if args.what == "indent":
        measure_indent(pdf, int(args.pages) if args.pages else 0)
        return 0
    if args.what == "grid":
        measure_grid(pdf, int(args.pages) if args.pages else 0)
        return 0
    if args.what == "holes":
        measure_holes(pdf, book_pages=args.pages or _book_pages(pdf))
        return 0
    if args.what == "bottom":
        return 1 if measure_bottom(pdf) else 0
    if args.what == "feet":
        measure_feet(pdf, args.pages)
    elif args.what == "frames":
        measure_frames(pdf)
    elif args.what == "coords":
        measure_coords(pdf)
    elif args.what == "hatch":
        measure_hatch()
    elif args.what == "figurine":
        measure_figurine()
    elif args.what == "marks":
        measure_marks()
    elif args.what == "highlight":
        measure_highlight()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
