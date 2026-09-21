"""Read a chess position straight out of a vector PDF -- exactly, with no model.

Origem: Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/pdf_service.py (os dois
espaços de coordenadas da página) e PDFimport/.../extract.py (varredura de spans
e prefixo de subconjunto de fonte).
Absorvido em 2026-09-07.  Alterações: a conversão de espaços virou um par de
funções puras com o inverso explícito, e a varredura de spans passou a usar
``rawdict`` para ter a caixa de cada caractere, não só a do span.

Why this is the differentiator (SPEC 6.1 "Via A", ADR-0006)
-----------------------------------------------------------
Everything that competes with us rasterises the page and runs a neural network.
For a photograph that is the only option.  But a chess book from a publisher is
usually a *vector* PDF, and there the diagram is one of two things:

* **Glyphs of a chess font.**  The position is literally in the file as text --
  ``rnbqkbnr`` is eight characters in Chess Merida.  Read it through
  :mod:`font_catalog` and the answer is exact: 100 % accurate, no inference, no
  model, about two milliseconds a page.
* **Vector rectangles and piece outlines.**  No text, but massive repetition: a
  book draws the same knight with the same path on every page.  Hash the
  normalised path commands per cell and identical drawings collapse into one
  cluster.  Name a cluster once and every later occurrence is matched exactly.

Both paths are implemented here.  Neither guesses silently: a
:class:`VectorBoard` carries the evidence that produced it.

What stops false positives
--------------------------
Figurine notation inside a paragraph is set in a chess font too.  Three things
keep it from being read as a board:

1. the font family must be a *diagram* family, not an inline figurine one;
2. the glyphs must form eight rows of eight on a square, regular pitch;
3. and -- the check that really does the work -- the square colours the glyphs
   carry must alternate like a chessboard.

Prose cannot accidentally satisfy the third one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, cast

try:  # PyMuPDF renamed itself; both spellings are in the wild.
    import pymupdf  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only on old installs
    import fitz as pymupdf  # type: ignore[import-untyped, no-redef]

from .font_catalog import (
    ChessFontFamily,
    GlyphRole,
    family_by_key,
    looks_like_chess_font,
    lookup_family,
    normalize_char,
)
from .orientation import (
    BoardOrientation,
    auto_orient,
    matrix_from_placement,
    orientation_from_labels,
    placement_from_matrix,
    unknown_orientation,
    rotate_placement,
)
from .piece_shapes import mask_from_samples, match_mask

__all__ = [
    "DetectionMethod",
    "Evidence",
    "SignatureIndex",
    "VectorBoard",
    "detect_drawing_boards",
    "detect_glyph_boards",
    "detect_vector_boards",
    "from_write_space",
    "learn_from_board",
    "to_write_space",
    "write_space_cropbox",
]

Rect = tuple[float, float, float, float]
DetectionMethod = Literal["font-glyph-lattice", "drawing-lattice"]

#: Smallest board side, in points, worth reporting.  Below this a "diagram" is
#: more likely to be an ornament than a position.
MIN_BOARD_SIDE_PT: Final = 24.0

#: How far a cell may sit from its ideal lattice position, as a fraction of the
#: cell pitch, and still be counted as belonging to it.
LATTICE_TOLERANCE: Final = 0.30

#: How far the horizontal and vertical pitches may differ and still be called
#: square cells.
SQUARENESS_TOLERANCE: Final = 0.30

#: How many of the 64 cells may be missing from the text layer before the read
#: is refused.  Extractors do sometimes drop runs of spaces, and a missing cell
#: on a checkerboard is provably an empty square of a known colour -- but a
#: board that is mostly holes is not a board.
MAX_INFERRED_CELLS: Final = 12

_UNICODE_CHESS: Final = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")

#: What an extractor hands back for a glyph the font does not define and the
#: PDF does not describe.  Chess Alpha, for one, ships no ``space`` glyph, so
#: every empty light square of an Alpha diagram arrives as U+0000.  The cell is
#: really there -- it has an advance and it holds the lattice together -- we
#: simply cannot name it, and on a checkerboard an unnameable cell is empty.
_UNRESOLVED_CHARS: Final = frozenset("\x00�")
_UNRESOLVED_ROLE: Final = GlyphRole("empty")

#: The checkerboard test needs this many cells whose square colour was actually
#: read before it is allowed to conclude anything.
MIN_COLOURED_CELLS: Final = 16

#: OCR_UI_ROADMAP passo 10: a board whose text layer lacked cells is not an
#: exact read.  The old rule took a missing cell for an empty square; on the
#: Polgar (SkakNew) the extractor drops every rook on a dark square, and 61
#: of 114 boards came out wrong at 0,79–0,82.  With holes the read is capped
#: here, the holes are reported, and the combined finder asks the square
#: classifier to fill them (``caissa.ingest.pdf.finders.fill_holes``).
HOLE_CONFIDENCE_CAP: Final = 0.60


# --------------------------------------------------------------------------
# The two coordinate spaces of a page
# --------------------------------------------------------------------------
#
# Everything the user sees and picks lives in `page.rect` space: the selection,
# the gallery, the `rect_pdf` stored in the project.  Reading text and
# drawings -- `get_text` (every mode, and its `clip=`), `get_image_info`,
# `get_drawings` -- happens in *text space*: CropBox applied, rotation not.
#
#     page.rect = text * page.rotation_matrix
#     text      = page.rect * page.derotation_matrix
#
# and nothing else.  The Editor's section-48 formula that used to live here
# added the CropBox origin in write space; measured on PyMuPDF 1.28.2 across
# four rotations, a displaced CropBox and a MediaBox with a non-zero origin
# (tests/unit/ingest/test_geometry.py, against the rendered ink), the origin
# term is wrong: on a rotated page with a displaced CropBox it put the board
# 40 pt from where it is drawn.  Corrected 2026-09-11 by the F2 front, whose
# `caissa.ingest.pdf.geometry.PageFrame` is the same conversion in pure
# arithmetic; the two functions are kept here for their callers and now agree
# with it.  Unrotated pages -- 18.766 of the collection's 18.767 -- never
# noticed either way.


def write_space_cropbox(page: Any) -> Any:
    """The CropBox -- the visible region -- in text coordinates.

    In text space the visible page starts at the origin: ``(0, 0, w, h)`` with
    the *unrotated* width and height.  It is the right clip bound for any
    rectangle converted with :func:`to_write_space`: on a rotated page
    ``page.rect`` has width and height swapped relative to text space, and
    using it as the bound cuts away valid content.
    """
    rect = pymupdf.Rect(page.rect) * page.derotation_matrix
    rect.normalize()
    return rect


def to_write_space(page: Any, rect: Rect) -> Any:
    """From the space the user sees to the space text and drawings live in."""
    out = pymupdf.Rect(rect) * page.derotation_matrix
    out.normalize()
    return out


def from_write_space(page: Any, rect: Rect) -> Rect:
    """The exact inverse of :func:`to_write_space`."""
    out = pymupdf.Rect(rect) * page.rotation_matrix
    out.normalize()
    return (float(out.x0), float(out.y0), float(out.x1), float(out.y1))


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Evidence:
    """Why the detector believes this is a board.  Shown to the user verbatim."""

    #: One line in Brazilian Portuguese, ready for the UI.
    summary: str
    method: DetectionMethod
    family_key: str | None = None
    family_name: str | None = None
    font_name: str | None = None
    font_size: float | None = None
    cell_pitch_pt: float = 0.0
    #: The eight rows exactly as they were found, before interpretation.
    raw_rows: tuple[str, ...] = ()
    #: Cells the text layer did not provide and that the checkerboard filled in.
    inferred_cells: int = 0
    #: Cells whose printed square colour disagreed with the checkerboard.
    checkerboard_faults: int = 0
    #: The 8x8 area itself (``page.rect`` space), the union of the cells' own
    #: boxes — ``rect_pdf`` is the origin-based rectangle kept for the crop
    #: and sits half a cell to the left of it.  What a classifier must see.
    cells_rect_pdf: tuple[float, float, float, float] | None = None
    #: For the drawing path: signature -> piece letter, as decided.
    clusters: Mapping[str, str] = field(default_factory=dict)
    #: For the drawing path: ``"row,col"`` -> signature of the drawing there.
    cell_signatures: Mapping[str, str] = field(default_factory=dict)
    details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Plain data, for logging and for the project file."""
        return {
            "summary": self.summary,
            "method": self.method,
            "family_key": self.family_key,
            "family_name": self.family_name,
            "font_name": self.font_name,
            "font_size": self.font_size,
            "cell_pitch_pt": self.cell_pitch_pt,
            "raw_rows": list(self.raw_rows),
            "inferred_cells": self.inferred_cells,
            "checkerboard_faults": self.checkerboard_faults,
            "cells_rect_pdf": list(self.cells_rect_pdf) if self.cells_rect_pdf else None,
            "clusters": dict(self.clusters),
            "cell_signatures": dict(self.cell_signatures),
            "details": list(self.details),
        }


@dataclass(frozen=True, slots=True)
class VectorBoard:
    """A chess diagram found in the vector content of a page."""

    #: Full FEN.  Side to move, castling and clocks are the neutral defaults: a
    #: book diagram does not carry them, and inventing them would be a lie.
    fen: str | None
    #: The piece-placement field on its own, which is what was actually read.
    piece_placement: str | None
    #: Board rectangle in ``page.rect`` space -- the space the UI works in.
    rect_pdf: Rect
    #: The same rectangle in write space, for anyone re-reading the page.
    rect_write: Rect
    #: Zero-based page number.
    page: int
    orientation: BoardOrientation
    method: DetectionMethod
    #: 1.0 only for an exact read of a verified font family.
    confidence: float
    evidence: Evidence

    @property
    def exact(self) -> bool:
        """Was the position read rather than inferred?"""
        return self.method == "font-glyph-lattice" and self.confidence >= 0.999


# --------------------------------------------------------------------------
# Glyph path
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Glyph:
    char: str
    role: GlyphRole
    ox: float
    oy: float
    bbox: Rect
    size: float
    font: str
    family_key: str


def _iter_spans(page: Any) -> Iterator[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Every text span of the page, with the line it belongs to."""
    raw = page.get_text("rawdict")
    for block in raw.get("blocks", ()):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            for span in line.get("spans", ()):
                yield line, span


def _family_for_span(span: Mapping[str, Any], allow_unverified: bool) -> ChessFontFamily | None:
    family = lookup_family(cast(str, span.get("font", "")))
    if family is None:
        chars = span.get("chars", ())
        if any(normalize_char(cast(str, c.get("c", ""))) in _UNICODE_CHESS for c in chars):
            family = family_by_key("unicode")
    if family is None:
        return None
    if family.kind == "figurine":
        return None
    if family.confidence == "unverified" and not allow_unverified:
        return None
    return family


def _collect_glyphs(page: Any, allow_unverified: bool) -> tuple[list[_Glyph], set[str]]:
    """Board-cell glyphs of the page, plus the names of unknown chess fonts."""
    glyphs: list[_Glyph] = []
    unknown_fonts: set[str] = set()
    for _line, span in _iter_spans(page):
        font_name = cast(str, span.get("font", ""))
        family = _family_for_span(span, allow_unverified)
        if family is None:
            if looks_like_chess_font(font_name):
                unknown_fonts.add(font_name)
            continue
        size = float(span.get("size", 0.0) or 0.0)
        for char in span.get("chars", ()):
            text = cast(str, char.get("c", ""))
            role = family.role(text)
            if role is None:
                if text not in _UNRESOLVED_CHARS:
                    continue
                role = _UNRESOLVED_ROLE
            elif role.kind not in ("piece", "empty", "marker", "background"):
                continue
            origin = char.get("origin", (0.0, 0.0))
            bbox = char.get("bbox", (0.0, 0.0, 0.0, 0.0))
            glyphs.append(
                _Glyph(
                    char=normalize_char(text),
                    role=role,
                    ox=float(origin[0]),
                    oy=float(origin[1]),
                    bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                    size=size,
                    font=font_name,
                    family_key=family.key,
                )
            )
    return glyphs, unknown_fonts


def _bucket(glyphs: Iterable[_Glyph]) -> dict[tuple[str, str, float], list[_Glyph]]:
    """Split glyphs into groups that could plausibly belong to one board."""
    out: dict[tuple[str, str, float], list[_Glyph]] = {}
    for g in glyphs:
        key = (g.family_key, g.font, round(g.size, 1))
        out.setdefault(key, []).append(g)
    return out


def _merge_overprints(cells: Sequence[_Glyph], tol: float) -> list[_Glyph]:
    """Fold zero-advance background glyphs into the piece printed over them.

    ChessBase diagram fonts draw a dark square with a piece on it as two glyphs
    at the same origin: a zero-advance background that knocks the piece shape
    out of the hatching, then the piece itself.  The background must not eat a
    cell of the lattice -- and its square colour *wins*, because the piece
    glyph it is printed under is the light-square cut of that piece.
    """
    if not any(g.role.zero_advance for g in cells):
        return list(cells)

    grid = max(tol, 1e-6)
    buckets: dict[tuple[int, int], list[_Glyph]] = {}
    for g in cells:
        buckets.setdefault((round(g.ox / grid), round(g.oy / grid)), []).append(g)

    merged: list[_Glyph] = []
    for group in buckets.values():
        backgrounds = [g for g in group if g.role.zero_advance]
        printed = [g for g in group if not g.role.zero_advance]
        if not printed:
            # A background with nothing over it is still a dark square.
            for bg in backgrounds:
                merged.append(
                    _Glyph(
                        char=bg.char,
                        role=GlyphRole("empty", square=bg.role.square),
                        ox=bg.ox, oy=bg.oy, bbox=bg.bbox, size=bg.size,
                        font=bg.font, family_key=bg.family_key,
                    )
                )
            continue
        square = backgrounds[0].role.square if backgrounds else None
        for g in printed:
            if square is not None and g.role.square != square:
                g = _Glyph(
                    char=g.char,
                    role=GlyphRole(g.role.kind, piece=g.role.piece, square=square),
                    ox=g.ox, oy=g.oy, bbox=g.bbox, size=g.size,
                    font=g.font, family_key=g.family_key,
                )
            merged.append(g)
    return merged


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return 0.0
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _group_rows(cells: Sequence[_Glyph], tol: float) -> list[list[_Glyph]]:
    """Cluster glyphs into text rows by their baseline."""
    rows: list[list[_Glyph]] = []
    for g in sorted(cells, key=lambda c: (c.oy, c.ox)):
        if rows and abs(rows[-1][0].oy - g.oy) <= tol:
            rows[-1].append(g)
        else:
            rows.append([g])
    for row in rows:
        row.sort(key=lambda c: c.ox)
    return rows


@dataclass(frozen=True, slots=True)
class _Lattice:
    cells: tuple[tuple[_Glyph | None, ...], ...]
    x0: float
    y_top: float
    pitch_x: float
    pitch_y: float
    inferred: int
    faults: int


def _row_pitch(rows: Sequence[Sequence[_Glyph]]) -> float:
    """Smallest positive gap between neighbouring glyphs: one cell."""
    diffs = [b.ox - a.ox for row in rows for a, b in zip(row, row[1:]) if b.ox - a.ox > 0.01]
    if not diffs:
        return 0.0
    diffs.sort()
    # The smallest gaps are single cells; take a low quantile so one squashed
    # pair cannot drag the estimate down.
    return _median(diffs[: max(1, len(diffs) // 2)])


def _extract_lattice(window: Sequence[Sequence[_Glyph]]) -> _Lattice | None:
    """Fit an 8x8 lattice to eight candidate rows, or give up."""
    ys = [_median([g.oy for g in row]) for row in window]
    dys = [b - a for a, b in zip(ys, ys[1:])]
    if len(dys) != 7:
        return None
    pitch_y = _median(dys)
    if pitch_y <= 0.0:
        return None
    if max(abs(d - pitch_y) for d in dys) > max(LATTICE_TOLERANCE * pitch_y, 0.5):
        return None

    pitch_x = _row_pitch(window)
    if pitch_x <= 0.0:
        return None
    ratio = pitch_x / pitch_y
    if not (1.0 - SQUARENESS_TOLERANCE <= ratio <= 1.0 + SQUARENESS_TOLERANCE):
        return None

    xs = sorted(g.ox for row in window for g in row)
    if len(xs) < 8:
        return None

    best: tuple[int, float, list[list[_Glyph | None]]] | None = None
    for anchor in sorted({round(x, 2) for x in xs}):
        grid: list[list[_Glyph | None]] = [[None] * 8 for _ in range(8)]
        placed = 0
        spoiled = False
        for r, row in enumerate(window):
            for g in row:
                offset = (g.ox - anchor) / pitch_x
                col = int(round(offset))
                if abs(offset - col) > LATTICE_TOLERANCE:
                    continue
                if not 0 <= col <= 7:
                    continue
                if grid[r][col] is not None:
                    spoiled = True
                    continue
                grid[r][col] = g
                placed += 1
        if spoiled or placed < 64 - MAX_INFERRED_CELLS:
            continue
        if best is None or placed > best[0]:
            best = (placed, anchor, grid)
        if placed == 64:
            break
    if best is None:
        return None
    placed, anchor, grid = best

    # Every row must be mostly there; a board with one whole side missing is
    # not a board, however good the total count looks.
    for row_cells in grid:
        if sum(1 for c in row_cells if c is not None) < 5:
            return None

    return _Lattice(
        cells=tuple(tuple(row) for row in grid),
        x0=anchor,
        y_top=ys[0],
        pitch_x=pitch_x,
        pitch_y=pitch_y,
        inferred=64 - placed,
        faults=0,
    )


def _checkerboard_faults(lattice: _Lattice) -> tuple[int, int, int]:
    """``(faults, parity, coloured cells)`` for the colours the glyphs carry.

    ``parity`` is 0 when cell (0, 0) is light and 1 when it is dark; it is -1
    when no glyph carried a square colour at all (the Unicode block, or a
    diagram whose empty squares all came back unresolved).
    """
    votes = {0: 0, 1: 0}
    coloured = 0
    for r in range(8):
        for c in range(8):
            glyph = lattice.cells[r][c]
            if glyph is None or glyph.role.square is None:
                continue
            coloured += 1
            dark = glyph.role.square == "dark"
            votes[((r + c) % 2) ^ (0 if dark else 1)] += 1
    if not coloured:
        return 0, -1, 0
    parity = 0 if votes[0] >= votes[1] else 1
    faults = votes[1 - parity]
    return faults, parity, coloured


def _placement_from_lattice(lattice: _Lattice) -> str:
    matrix: list[list[str]] = []
    for row in lattice.cells:
        line: list[str] = []
        for glyph in row:
            if glyph is None or glyph.role.piece is None:
                line.append(".")
            else:
                line.append(glyph.role.piece)
        matrix.append(line)
    return placement_from_matrix(matrix)


def _raw_rows(lattice: _Lattice) -> tuple[str, ...]:
    """The eight rows as characters, for the user to compare with the page.

    A cell the extractor never produced shows as ``~``; one it produced but
    could not name shows as ``·``.  Both are visible rather than silently
    printed as a space, because the difference matters when a read looks wrong.
    """
    def show(glyph: _Glyph | None) -> str:
        if glyph is None:
            return "~"
        if glyph.char in _UNRESOLVED_CHARS:
            return "·"
        return glyph.char

    return tuple("".join(show(g) for g in row) for row in lattice.cells)


def _short_labels(page: Any, board: Rect) -> list[tuple[str, float, float, float, float]]:
    """Short words around the board, for the coordinate reader."""
    out: list[tuple[str, float, float, float, float]] = []
    x0, y0, x1, y1 = board
    side = max(x1 - x0, y1 - y0)
    margin = max(12.0, side * 0.20)
    zone = pymupdf.Rect(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
    for word in page.get_text("words"):
        wx0, wy0, wx1, wy1, text = word[0], word[1], word[2], word[3], word[4]
        if len(text) > 8:
            continue
        if pymupdf.Rect(wx0, wy0, wx1, wy1).intersects(zone):
            out.append((text, float(wx0), float(wy0), float(wx1), float(wy1)))
    return out


#: Cells further apart than this many cell pitches along x belong to different
#: boards.  1.6: a board's own columns are one pitch apart, and the gutter
#: between side-by-side boards in the collection is never under two.
_X_CLUSTER_GAP_CELLS: Final = 1.6


def _split_by_x(cells: Sequence[_Glyph], gap: float) -> list[list[_Glyph]]:
    """Group cells into horizontal clusters separated by at least ``gap``."""
    clusters: list[list[_Glyph]] = []
    last_x = 0.0
    for g in sorted(cells, key=lambda c: c.ox):
        if clusters and g.ox - last_x <= gap:
            clusters[-1].append(g)
        else:
            clusters.append([g])
        last_x = g.ox
    return clusters


def detect_glyph_boards(
    page: Any,
    *,
    allow_unverified: bool = False,
    min_side_pt: float = MIN_BOARD_SIDE_PT,
) -> list[VectorBoard]:
    """Boards set with a chess font.  This is the exact path."""
    glyphs, unknown_fonts = _collect_glyphs(page, allow_unverified)
    boards: list[VectorBoard] = []
    for (family_key, font_name, size), bucket in _bucket(glyphs).items():
        family = family_by_key(family_key)
        if family is None:
            continue
        tol = max(0.2, size * 0.2)
        cells = _merge_overprints(bucket, tol)
        # Two boards printed side by side at different heights interleave
        # their rows when grouped page-wide, and no window of eight
        # consecutive rows is then a board (Dvoretsky 2025, p. 203: the left
        # board starts 36 pt lower than the right one, 0 of 2 detected).
        # Split the cells at horizontal gaps wider than a cell first, so each
        # column of boards is searched on its own.
        for cluster in _split_by_x(cells, gap=max(size, 1.0) * _X_CLUSTER_GAP_CELLS):
            remaining = list(cluster)
            for _ in range(8):  # a page rarely holds more than a handful of boards
                rows = _group_rows(remaining, tol=max(0.4, size * 0.4))
                found: _Lattice | None = None
                for start in range(max(0, len(rows) - 7)):
                    lattice = _extract_lattice(rows[start : start + 8])
                    if lattice is not None:
                        found = lattice
                        break
                if found is None:
                    break
                used = {id(g) for row in found.cells for g in row if g is not None}
                remaining = [g for g in remaining if id(g) not in used]
                board = _board_from_lattice(page, found, family, font_name, size, unknown_fonts)
                if board is None:
                    continue
                side = board.rect_write[2] - board.rect_write[0]
                if side >= min_side_pt:
                    boards.append(board)
    boards.sort(key=lambda b: (b.rect_pdf[1], b.rect_pdf[0]))
    return boards


def _board_from_lattice(
    page: Any,
    lattice: _Lattice,
    family: ChessFontFamily,
    font_name: str,
    size: float,
    unknown_fonts: set[str],
) -> VectorBoard | None:
    faults, parity, coloured = _checkerboard_faults(lattice)
    coloured_family = parity >= 0 and coloured >= MIN_COLOURED_CELLS
    if coloured_family and faults > 2:
        # The square colours do not alternate: this is text in a chess font,
        # not a board.  This single check is what keeps figurine notation in a
        # paragraph from being read as a diagram.
        return None
    if not coloured_family and family.key != "unicode":
        # A diagram family whose glyphs told us nothing about square colours
        # has not been read, it has been guessed at.  Refuse.
        return None
    unresolved = sum(
        1
        for row in lattice.cells
        for g in row
        if g is not None and g.char in _UNRESOLVED_CHARS
    )

    # Fill the holes the extractor left.  On a checkerboard a missing cell is
    # provably an empty square, and its colour follows from its position -- but
    # it is still recorded, because it was not read.
    placement = _placement_from_lattice(lattice)

    write_rect: Rect = (
        lattice.x0 - lattice.pitch_x * 0.5,
        lattice.y_top - lattice.pitch_y * 0.85,
        lattice.x0 + lattice.pitch_x * 7.5,
        lattice.y_top + lattice.pitch_y * 7.15,
    )
    # The coordinates are read around the glyph cells' own box, in the space
    # ``page.get_text("words")`` reports (passo C10): the write-space rectangle
    # of the lattice is half a cell off the ink on the x axis and turns with
    # the page, so the label reader used to look in the wrong place and fall
    # back to the heuristic every time.
    present = [g for row in lattice.cells for g in row if g is not None]
    cells_rect = from_write_space(page, (
        min(g.bbox[0] for g in present), min(g.bbox[1] for g in present),
        max(g.bbox[2] for g in present), max(g.bbox[3] for g in present)))
    orientation = _orientation_for(page, cells_rect, placement)
    # Passo C10: the lattice reads the rows as printed; from Black's side
    # the printed top row is rank 1, so the canonical placement is the
    # rotated one.  The renderer turns the board again for display
    # (``Orientation.BLACK``); the FEN in the PGN/EPUB must be the position.
    if not orientation.white_at_bottom:
        placement = rotate_placement(placement)

    confidence = 1.0
    details: list[str] = []
    if family.confidence != "verified":
        confidence -= 0.15
        details.append(f"família {family.display_name} catalogada como '{family.confidence}'")
    if lattice.inferred:
        confidence = min(confidence - 0.03 * lattice.inferred, HOLE_CONFIDENCE_CAP)
        details.append(
            f"{lattice.inferred} casa(s) ausentes na camada de texto, tomadas como vazias: a "
            f"posição pode estar incompleta (o extrator omite glifos sem mapa Unicode — na "
            f"SkakNew, toda torre em casa escura); o classificador de casas as completa quando "
            f"está disponível"
        )
    if faults:
        confidence -= 0.10 * faults
        details.append(f"{faults} casa(s) com cor discordante do xadrezado")
    if unresolved:
        details.append(
            f"{unresolved} casa(s) sem glifo definido na fonte (a extração devolveu "
            f"U+0000); estão no xadrezado e são casas vazias"
        )
    if not coloured_family:
        confidence -= 0.10
        details.append("a família não codifica a cor da casa; validação só geométrica")
    if unknown_fonts:
        details.append("fontes de xadrez não catalogadas na página: " + ", ".join(sorted(unknown_fonts)))
    confidence = max(0.0, min(1.0, confidence))

    summary = (
        f"Lida diretamente dos glifos da fonte {family.display_name} "
        f"({font_name or 'sem nome'}, {size:.1f} pt): 8x8 glifos com passo de "
        f"{lattice.pitch_x:.2f} pt e xadrezado consistente."
    )
    evidence = Evidence(
        summary=summary,
        method="font-glyph-lattice",
        family_key=family.key,
        family_name=family.display_name,
        font_name=font_name,
        font_size=size,
        cell_pitch_pt=lattice.pitch_x,
        raw_rows=_raw_rows(lattice),
        inferred_cells=lattice.inferred,
        checkerboard_faults=faults,
        cells_rect_pdf=tuple(float(v) for v in cells_rect),
        details=tuple(details),
    )
    return VectorBoard(
        fen=f"{placement} w - - 0 1",
        piece_placement=placement,
        rect_pdf=from_write_space(page, write_rect),
        rect_write=write_rect,
        page=int(page.number),
        orientation=orientation,
        method="font-glyph-lattice",
        confidence=confidence,
        evidence=evidence,
    )


def _orientation_for(page: Any, board_pdf: Rect, placement: str) -> BoardOrientation:
    """``board_pdf`` in the space of ``page.get_text("words")`` (the visible page)."""
    labels = _short_labels(page, board_pdf)
    from_labels = orientation_from_labels(labels, board_pdf)
    if from_labels is not None:
        return from_labels
    try:
        return auto_orient(placement)
    except ValueError:
        return unknown_orientation()


# --------------------------------------------------------------------------
# Drawing path
# --------------------------------------------------------------------------


class SignatureIndex:
    """Learned mapping from a normalised path signature to a piece.

    A book draws its knight the same way on every page, so one solved diagram
    teaches every other diagram in the same book.  The index is plain data and
    round-trips through JSON, which is how it gets carried between sessions.
    """

    __slots__ = ("_table",)

    def __init__(self, table: Mapping[str, str] | None = None) -> None:
        self._table: dict[str, str] = dict(table or {})

    def learn(self, signature: str, piece: str) -> None:
        """Teach the index that ``signature`` draws ``piece`` (a FEN letter)."""
        if piece and piece not in "PNBRQKpnbrqk":
            raise ValueError(f"letra de peça inválida: {piece!r}")
        self._table[signature] = piece

    def identify(self, signature: str) -> str | None:
        return self._table.get(signature)

    def __len__(self) -> int:
        return len(self._table)

    def to_json(self) -> str:
        return json.dumps(self._table, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> SignatureIndex:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("índice de assinaturas inválido")
        return cls({str(k): str(v) for k, v in data.items()})


def _luminance(colour: Sequence[float] | None) -> float:
    if not colour:
        return 1.0
    if len(colour) == 1:
        return float(colour[0])
    r, g, b = (float(c) for c in colour[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _square_candidates(drawings: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for item in drawings:
        if item.get("type") not in ("f", "fs"):
            continue
        rect = item.get("rect")
        if rect is None:
            continue
        w, h = float(rect.width), float(rect.height)
        if w < 3.0 or h < 3.0:
            continue
        if abs(w - h) > 0.06 * max(w, h):
            continue
        out.append(item)
    return out


@dataclass(frozen=True, slots=True)
class _Grid:
    x0: float
    y0: float
    pitch: float
    squares: tuple[Mapping[str, Any], ...]

    @property
    def rect(self) -> Rect:
        return (self.x0, self.y0, self.x0 + 8 * self.pitch, self.y0 + 8 * self.pitch)


def _fit_grid(squares: Sequence[Mapping[str, Any]]) -> _Grid | None:
    """Do these equal squares sit on an 8x8 lattice with alternating colours?"""
    if len(squares) < 24:
        return None
    pitch = _median([float(s["rect"].width) for s in squares])
    if pitch <= 0:
        return None
    x0 = min(float(s["rect"].x0) for s in squares)
    y0 = min(float(s["rect"].y0) for s in squares)
    seen: dict[tuple[int, int], Mapping[str, Any]] = {}
    parity: set[int] = set()
    for s in squares:
        fx = (float(s["rect"].x0) - x0) / pitch
        fy = (float(s["rect"].y0) - y0) / pitch
        cx, cy = int(round(fx)), int(round(fy))
        if abs(fx - cx) > LATTICE_TOLERANCE or abs(fy - cy) > LATTICE_TOLERANCE:
            return None
        if not (0 <= cx <= 7 and 0 <= cy <= 7):
            return None
        if (cx, cy) in seen:
            continue
        seen[(cx, cy)] = s
        parity.add((cx + cy) % 2)
    cols = {c for c, _ in seen}
    rows = {r for _, r in seen}
    if max(cols) - min(cols) != 7 or max(rows) - min(rows) != 7:
        return None
    if len(parity) == 1:
        # Only one colour of square is painted: the classic "dark squares on a
        # white page" board.  32 of them is a full board.
        if len(seen) < 28:
            return None
    elif len(seen) < 56:
        return None
    return _Grid(x0=x0, y0=y0, pitch=pitch, squares=tuple(seen.values()))


def _canonical_item(item: Sequence[Any], x0: float, y0: float, pitch: float) -> str:
    """One path command, normalised into the cell's own unit square."""
    kind = str(item[0])
    parts: list[str] = [kind]

    def point(p: Any) -> str:
        return f"{(float(p.x) - x0) / pitch:.4f},{(float(p.y) - y0) / pitch:.4f}"

    for element in item[1:]:
        if hasattr(element, "x") and hasattr(element, "y"):
            parts.append(point(element))
        elif hasattr(element, "x0"):
            parts.append(
                f"{(float(element.x0) - x0) / pitch:.4f},{(float(element.y0) - y0) / pitch:.4f}"
                f":{(float(element.x1) - x0) / pitch:.4f},{(float(element.y1) - y0) / pitch:.4f}"
            )
        else:
            parts.append(str(element))
    return "|".join(parts)


def _cell_signature(
    entries: Sequence[Mapping[str, Any]], x0: float, y0: float, pitch: float
) -> str:
    """A hash that is equal exactly when the same drawing is repeated.

    Path commands are normalised into the cell's own unit square, so the same
    piece hashes the same wherever it is drawn and at whatever size the book
    used.  The commands are sorted before hashing, because the order the
    display list happens to emit them in is not part of the drawing.
    """
    tokens: list[str] = []
    for entry in entries:
        head = f"{entry.get('type')}:{entry.get('even_odd')}:{_luminance(entry.get('fill')):.3f}"
        for item in entry.get("items", ()):
            tokens.append(head + "#" + _canonical_item(item, x0, y0, pitch))
    if not tokens:
        return ""
    tokens.sort()
    return hashlib.sha256("\n".join(tokens).encode("utf-8")).hexdigest()[:32]


def _cell_ink_colour(entries: Sequence[Mapping[str, Any]]) -> float:
    """Area-weighted luminance of the fills in a cell; 1.0 when nothing fills."""
    total = 0.0
    weight = 0.0
    for entry in entries:
        rect = entry.get("rect")
        if rect is None or entry.get("type") not in ("f", "fs"):
            continue
        area = float(rect.width) * float(rect.height)
        total += _luminance(entry.get("fill")) * area
        weight += area
    return total / weight if weight else 1.0


def _rasterise_cell(page: Any, rect: Rect, side: int = 48) -> list[list[bool]]:
    """Ink map of one cell, as plain nested lists (no third-party arrays)."""
    clip = pymupdf.Rect(*rect)
    zoom = side / max(1e-6, clip.width)
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csGRAY, alpha=False
    )
    data = pix.samples
    width, height = pix.width, pix.height
    stride = pix.stride
    return [
        [data[y * stride + x] < 128 for x in range(width)]
        for y in range(height)
    ]


def detect_drawing_boards(
    page: Any,
    *,
    index: SignatureIndex | None = None,
    identify: bool = True,
    min_side_pt: float = MIN_BOARD_SIDE_PT,
) -> list[VectorBoard]:
    """Boards drawn as vector art: filled squares plus repeated piece paths."""
    drawings = list(page.get_drawings())
    candidates = _square_candidates(drawings)
    by_size: dict[float, list[Mapping[str, Any]]] = {}
    for square in candidates:
        by_size.setdefault(round(float(square["rect"].width), 1), []).append(square)

    boards: list[VectorBoard] = []
    for size, squares in sorted(by_size.items(), key=lambda kv: -len(kv[1])):
        if size * 8 < min_side_pt:
            continue
        grid = _fit_grid(squares)
        if grid is None:
            continue
        board = _board_from_grid(page, grid, drawings, index, identify)
        if board is not None:
            boards.append(board)
    boards.sort(key=lambda b: (b.rect_pdf[1], b.rect_pdf[0]))
    return boards


def _board_from_grid(
    page: Any,
    grid: _Grid,
    drawings: Sequence[Mapping[str, Any]],
    index: SignatureIndex | None,
    identify: bool,
) -> VectorBoard | None:
    board_rect = grid.rect
    square_ids = {id(s) for s in grid.squares}
    cells: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for entry in drawings:
        if id(entry) in square_ids:
            continue
        rect = entry.get("rect")
        if rect is None:
            continue
        w, h = float(rect.width), float(rect.height)
        if w > grid.pitch * 1.4 or h > grid.pitch * 1.4:
            continue  # frames, rules and the board outline itself
        cx = (float(rect.x0) + float(rect.x1)) / 2.0
        cy = (float(rect.y0) + float(rect.y1)) / 2.0
        col = int((cx - grid.x0) // grid.pitch)
        row = int((cy - grid.y0) // grid.pitch)
        if not (0 <= col <= 7 and 0 <= row <= 7):
            continue
        cells.setdefault((row, col), []).append(entry)

    if not cells:
        return None

    signatures: dict[tuple[int, int], str] = {}
    for key, entries in cells.items():
        row, col = key
        sig = _cell_signature(
            entries, grid.x0 + col * grid.pitch, grid.y0 + row * grid.pitch, grid.pitch
        )
        if sig:
            signatures[key] = sig

    clusters: dict[str, list[tuple[int, int]]] = {}
    for key, sig in signatures.items():
        clusters.setdefault(sig, []).append(key)

    naming: dict[str, str] = {}
    unresolved = 0
    for sig, members in clusters.items():
        learned = index.identify(sig) if index is not None else None
        if learned is not None:
            naming[sig] = learned
            continue
        if not identify:
            unresolved += 1
            continue
        row, col = members[0]
        cell_rect: Rect = (
            grid.x0 + col * grid.pitch,
            grid.y0 + row * grid.pitch,
            grid.x0 + (col + 1) * grid.pitch,
            grid.y0 + (row + 1) * grid.pitch,
        )
        piece = _bootstrap_identify(page, cell_rect, cells[(row, col)])
        if piece is None:
            unresolved += 1
        else:
            naming[sig] = piece

    matrix = [["." for _ in range(8)] for _ in range(8)]
    for key, sig in signatures.items():
        piece = naming.get(sig)
        if piece:
            matrix[key[0]][key[1]] = piece
    placement = placement_from_matrix(matrix)

    exact_clusters = sum(1 for sig in clusters if index is not None and index.identify(sig))
    confidence = 0.55
    if clusters:
        confidence = 0.55 + 0.40 * (exact_clusters / len(clusters))
    if unresolved:
        confidence -= 0.10 * unresolved / max(1, len(clusters))
    confidence = max(0.0, min(0.99, confidence))

    details = [
        f"{len(grid.squares)} retângulos preenchidos formam a grade 8x8 (passo {grid.pitch:.2f} pt)",
        f"{len(cells)} casas ocupadas em {len(clusters)} desenho(s) distinto(s)",
    ]
    if unresolved:
        details.append(f"{unresolved} desenho(s) sem identificação: assinatura desconhecida")
    if index is not None:
        details.append(f"{exact_clusters} desenho(s) reconhecidos exatamente pelo índice de assinaturas")

    placement_or_none = placement if any(c != "." for row in matrix for c in row) else None
    orientation = (
        _orientation_for(page, from_write_space(page, board_rect), placement)
        if placement_or_none
        else unknown_orientation()
    )
    if placement_or_none and not orientation.white_at_bottom:
        placement = placement_or_none = rotate_placement(placement)   # passo C10
    return VectorBoard(
        fen=f"{placement} w - - 0 1" if placement_or_none else None,
        piece_placement=placement_or_none,
        rect_pdf=from_write_space(page, board_rect),
        rect_write=board_rect,
        page=int(page.number),
        orientation=orientation,
        method="drawing-lattice",
        confidence=confidence,
        evidence=Evidence(
            summary=(
                "Grade 8x8 de retângulos vetoriais com cores alternadas; as peças "
                "foram agrupadas por assinatura de caminho (desenhos idênticos "
                "colapsam num único grupo)."
            ),
            method="drawing-lattice",
            cell_pitch_pt=grid.pitch,
            clusters=dict(naming),
            cell_signatures={f"{r},{c}": sig for (r, c), sig in signatures.items()},
            details=tuple(details),
        ),
    )


def _bootstrap_identify(
    page: Any, cell_rect: Rect, entries: Sequence[Mapping[str, Any]]
) -> str | None:
    """First guess at what a never-seen-before drawing is.

    This is the one inferential step in the whole module, and it is confined to
    naming a cluster the index has not been taught.  Once named -- by this, or
    better, by the user -- every identical drawing in the book is matched
    exactly by its signature.
    """
    try:
        samples = _rasterise_cell(page, cell_rect)
    except Exception:  # pragma: no cover - depends on the renderer
        return None
    bits, width, height = mask_from_samples(samples)
    if not bits:
        return None
    piece, score, margin = match_mask(bits, width, height)
    if not piece or score < 0.45 or margin < 0.02:
        return None
    dark = _cell_ink_colour(entries) < 0.45
    return piece.lower() if dark else piece


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def _overlaps(a: Rect, b: Rect) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def detect_vector_boards(
    page: Any,
    *,
    allow_unverified: bool = False,
    index: SignatureIndex | None = None,
    identify_drawings: bool = True,
    min_side_pt: float = MIN_BOARD_SIDE_PT,
) -> list[VectorBoard]:
    """Every chess diagram this page carries in its vector content.

    The glyph path runs first because it is exact; the drawing path only fills
    in the areas it did not already claim.  An empty list means the page has no
    vector diagram -- the caller should then fall back to the geometric and
    neural detectors (SPEC 6.1, vias B and C).
    """
    boards = detect_glyph_boards(
        page, allow_unverified=allow_unverified, min_side_pt=min_side_pt
    )
    claimed = [b.rect_write for b in boards]
    for board in detect_drawing_boards(
        page, index=index, identify=identify_drawings, min_side_pt=min_side_pt
    ):
        if any(_overlaps(board.rect_write, other) for other in claimed):
            continue
        boards.append(board)
        claimed.append(board.rect_write)
    boards.sort(key=lambda b: (b.rect_pdf[1], b.rect_pdf[0]))
    return boards


def learn_from_board(index: SignatureIndex, board: VectorBoard, piece_placement: str) -> int:
    """Teach an index the drawings of a board whose true position is known.

    Returns how many signatures were learned.  This is what turns one solved
    diagram -- confirmed by the user, or read exactly from a twin diagram set
    in a chess font -- into exact readings for the rest of the book.
    """
    if board.method != "drawing-lattice":
        raise ValueError("só faz sentido aprender assinaturas de tabuleiros vetoriais")
    matrix = matrix_from_placement(piece_placement)
    learned = 0
    for cell, signature in board.evidence.cell_signatures.items():
        row_text, _, col_text = cell.partition(",")
        row, col = int(row_text), int(col_text)
        truth = matrix[row][col]
        if truth != ".":
            index.learn(signature, truth)
            learned += 1
    return learned


# --------------------------------------------------------------------------
# Unknown chess fonts: the lattice without the reading (OCR_UI_ROADMAP passo 10)
# --------------------------------------------------------------------------
#
# A diagram set in a chess font the catalog does not know still *is* an 8x8
# lattice of glyphs of one font at one size: the geometry is exact even when
# the glyph→piece map is not.  This finds that lattice and hands back the
# rectangle, so the board can be rendered and read by the square classifier
# (``caissa.ingest.pdf.finders.inferred_font_finder``), with provenance
# ``VECTOR_INFERRED`` and a confidence ceiling — the read is inferred from
# pixels, not decoded from the font.  Nothing is inferred here: no piece, no
# colour, no orientation.


@dataclass(frozen=True)
class UnknownFontLattice:
    """An 8x8 grid of glyphs of a chess font outside the catalog."""

    rect_pdf: Rect
    rect_write: Rect
    page: int
    font_name: str
    font_size: float
    cell_pitch_pt: float
    #: Cells the text layer did not carry (the lattice is still whole).
    missing_cells: int
    #: The raw characters, row by row, for whoever wants to learn the font.
    raw_rows: tuple[str, ...]


def _collect_unknown_glyphs(page: Any, lookup: Any = lookup_family) -> list[_Glyph]:
    """Every glyph of a span in a chess-looking font that ``lookup`` does not know.

    ``lookup`` is swapped by the sabotage that hides a catalogued family.
    """
    glyphs: list[_Glyph] = []
    for _line, span in _iter_spans(page):
        font_name = cast(str, span.get("font", ""))
        if not font_name or not looks_like_chess_font(font_name) or lookup(font_name) is not None:
            continue
        size = float(span.get("size", 0.0) or 0.0)
        for char in span.get("chars", ()):
            # A space is kept: in Merida and its kin the empty light square
            # *is* the space glyph, and a lattice with holes is no lattice.
            text = cast(str, char.get("c", ""))
            origin = char.get("origin", (0.0, 0.0))
            bbox = char.get("bbox", (0.0, 0.0, 0.0, 0.0))
            glyphs.append(
                _Glyph(
                    char=text,
                    role=_UNRESOLVED_ROLE,
                    ox=float(origin[0]),
                    oy=float(origin[1]),
                    bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                    size=size,
                    font=font_name,
                    family_key="unknown",
                )
            )
    return glyphs


def detect_unknown_font_lattices(
    page: Any,
    *,
    lookup: Any = lookup_family,
    min_side_pt: float = MIN_BOARD_SIDE_PT,
) -> list[UnknownFontLattice]:
    """8x8 lattices of glyphs of chess fonts the catalog does not know.

    Same lattice fit as :func:`detect_glyph_boards`, no checkerboard test
    (an unknown font tells nothing about square colours) — so a paragraph of
    figurine notation in an unknown font could in principle fit; it does not
    in practice, because a paragraph's glyphs are not eight equally spaced
    rows of eight equally spaced columns.
    """
    glyphs = _collect_unknown_glyphs(page, lookup)
    boards: list[UnknownFontLattice] = []
    for (_family_key, font_name, size), bucket in _bucket(glyphs).items():
        tol = max(0.2, size * 0.2)
        cells = _merge_overprints(bucket, tol)
        for cluster in _split_by_x(cells, gap=max(size, 1.0) * _X_CLUSTER_GAP_CELLS):
            remaining = list(cluster)
            for _ in range(8):
                rows = _group_rows(remaining, tol=max(0.4, size * 0.4))
                found: _Lattice | None = None
                for start in range(max(0, len(rows) - 7)):
                    lattice = _extract_lattice(rows[start : start + 8])
                    if lattice is not None:
                        found = lattice
                        break
                if found is None:
                    break
                used = {id(g) for row in found.cells for g in row if g is not None}
                remaining = [g for g in remaining if id(g) not in used]
                # The board is the union of the cells' own boxes — what the
                # classifier needs is the 8x8 area exactly, not the
                # origin-based rectangle the exact path keeps for its crop
                # (half a cell to the left, measured on the DEM).
                present = [g for row in found.cells for g in row if g is not None]
                write_rect: Rect = (
                    min(g.bbox[0] for g in present),
                    min(g.bbox[1] for g in present),
                    max(g.bbox[2] for g in present),
                    max(g.bbox[3] for g in present),
                )
                if write_rect[2] - write_rect[0] < min_side_pt:
                    continue
                boards.append(
                    UnknownFontLattice(
                        rect_pdf=from_write_space(page, write_rect),
                        rect_write=write_rect,
                        page=int(page.number),
                        font_name=font_name,
                        font_size=size,
                        cell_pitch_pt=found.pitch_x,
                        missing_cells=found.inferred,
                        raw_rows=_raw_rows(found),
                    )
                )
    boards.sort(key=lambda b: (b.rect_pdf[1], b.rect_pdf[0]))
    return boards
