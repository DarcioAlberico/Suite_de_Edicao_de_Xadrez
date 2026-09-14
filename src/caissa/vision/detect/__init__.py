"""Board detection -- the vector path (SPEC 6.1 "Via A", ADR-0006).

The one call almost everybody wants::

    from caissa.vision.detect import detect_vector_boards

    for board in detect_vector_boards(page):
        print(board.fen, board.confidence, board.evidence.summary)

``page`` is a PyMuPDF page.  An empty list means the page carries no vector
diagram and the caller should fall back to the geometric detector (via B) or
the neural one (via C).

Two ways in, both exact
-----------------------
* ``font-glyph-lattice`` -- the diagram is set with a chess font, so the
  position is already in the file as text.  Reading it is exact: no inference,
  no model, no rasterisation.  This is what nobody else does.
* ``drawing-lattice`` -- the diagram is vector art.  The 8x8 grid is found from
  the filled squares, and the pieces are grouped by an exact hash of their
  normalised path commands.  Naming a group once makes every later occurrence
  in the book an exact match; :class:`SignatureIndex` is where that knowledge
  lives.

Everything the detector believes is backed by :class:`Evidence`, in Brazilian
Portuguese, so the interface can show the user *why* -- which font, which
glyphs, which grid.
"""

from __future__ import annotations

from .font_catalog import (
    FAMILIES,
    ChessFontFamily,
    Confidence,
    GlyphKind,
    GlyphRole,
    LayoutSpec,
    family_by_key,
    looks_like_chess_font,
    lookup_family,
    normalize_char,
    normalize_font_name,
)
from .orientation import (
    BoardOrientation,
    OrientationCandidate,
    auto_orient,
    orientation_from_labels,
    plausibility,
    rank_orientations,
)
from .vector_detect import (
    DetectionMethod,
    Evidence,
    SignatureIndex,
    UnknownFontLattice,
    VectorBoard,
    detect_drawing_boards,
    detect_glyph_boards,
    detect_unknown_font_lattices,
    detect_vector_boards,
    from_write_space,
    learn_from_board,
    to_write_space,
    write_space_cropbox,
)

# ``recall`` imports the trunk (``chess_diagram_ocr``) at module level and
# raises when it is not installed.  The font catalogue and the vector detector
# need nothing of the kind, and the F2 importer's text path reads the
# catalogue on every page -- so the recall names are resolved lazily (PEP 562)
# and a checkout without the trunk can still import this package.
_RECALL_NAMES = frozenset(
    {
        "EMBEDDED_CHECKER_FLOOR",
        "SEARCH_SCALES",
        "SQUARE_MIN_ELONGATION",
        "embedded_checker_floor",
        "multiscale_search",
        "recall_pack",
        "square_anchors",
    }
)


def __getattr__(name: str) -> object:
    if name in _RECALL_NAMES:
        from . import recall

        return getattr(recall, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # main entry point
    "detect_vector_boards",
    "VectorBoard",
    "Evidence",
    "DetectionMethod",
    # the two paths on their own
    "detect_glyph_boards",
    "detect_drawing_boards",
    "detect_unknown_font_lattices",
    "UnknownFontLattice",
    "SignatureIndex",
    "learn_from_board",
    # font catalog
    "FAMILIES",
    "ChessFontFamily",
    "Confidence",
    "GlyphKind",
    "GlyphRole",
    "LayoutSpec",
    "family_by_key",
    "lookup_family",
    "looks_like_chess_font",
    "normalize_char",
    "normalize_font_name",
    # orientation
    "BoardOrientation",
    "OrientationCandidate",
    "auto_orient",
    "orientation_from_labels",
    "plausibility",
    "rank_orientations",
    # recall recovery over the trunk's contour detector
    "recall_pack",
    "multiscale_search",
    "embedded_checker_floor",
    "square_anchors",
    "SEARCH_SCALES",
    "SQUARE_MIN_ELONGATION",
    "EMBEDDED_CHECKER_FLOOR",
    # coordinate spaces
    "write_space_cropbox",
    "to_write_space",
    "from_write_space",
]
