"""Reference piece silhouettes, as data, for the vector-drawing path.

A diagram drawn as vector art carries no text, so there is nothing to read.
What it does carry is *repetition*: the same book draws the same piece with the
same path, over and over.  :mod:`vector_detect` exploits that by hashing the
normalised path commands of each cell, which groups the 64 cells into a handful
of clusters that are provably identical.  Clustering is exact; naming the
clusters is not.  These masks are the bootstrap that puts a first name on each
cluster when nobody has taught the index yet.

The masks are 32x32 bounding-box-normalised silhouettes of the six piece types,
generated from Chess Merida -- the one font whose glyph table is verified twice
over (by eye and against the write-side table in ``renderer.py``).  They are
stored as 1024-bit integers, row-major from the top-left, so matching is a pair
of popcounts and needs no third-party library.

Their discriminative power is modest and honestly stated: the worst confusable
pair (pawn vs rook) reaches IoU 0.73 against a self-match of 1.00.  Anything
identified this way is reported with ``method="drawing-lattice"`` and a
confidence well under 1.0 -- unlike the glyph path, which is exact.
"""

from __future__ import annotations

from typing import Final, Mapping

__all__ = ["MASK_SIDE", "REFERENCE_MASKS", "mask_from_samples", "match_mask"]

#: Side of the square mask, in cells.
MASK_SIDE: Final = 32

_MASK_BITS: Final = MASK_SIDE * MASK_SIDE

#: ``piece letter -> (silhouette bits, typical width/height of the em box)``.
#: Generated 2026-09-07 from ``chessmerida.otf`` at 96 px, holes filled, then
#: cropped to the ink bounding box and resampled to 32x32.
REFERENCE_MASKS: Final[Mapping[str, tuple[int, float, float]]] = {
    "P": (0x7ffffffe7fffffffffffffffffffffffffffffffffffffff7ffffffe7ffffffe7ffffffe3ffffffc1ffffff80ffffff003ffffc001ffff80003ffc00007ffe0001ffff8001ffff8003ffffc003ffffc003ffffc003ffffc001ffff8000ffff00003ffc00000ff000001ff800003ffc00003ffc00001ff800000ff0000007e000, 0.52, 0.73),
    "N": (0xfffffe00fffffe00fffffe00fffffe00fffffc00fffffc00fffff800fffff060ffffe0fcffffc1feffffc1ffffff83ff7fff87ff7fff1fff7fff7ffe7ffffffe3ffffffc3ffffff83ffffff81ffffff01ffffff00ffffff007ffffe007ffffe003ffffe001ffffc000ffff80003fff800007ffc00001e7c00000c3c0000000c0, 0.77, 0.74),
    "B": (0x21f81f847ffe7ffeffffffffffffffff1f0ff0f80007e000003ffc00003ffc00003ffc00003ffc00001ff800001ff800003ffc00007ffe0000ffff0000ffff0000ffff8001ffff8000ffff0000ffff0000ffff00007ffe00003ffc00001ff800000ff0000007e0000003c0000003c0000007e0000007e0000003c00000018000, 0.73, 0.74),
    "R": (0xffffffffffffffffffffffffffffffffffffffff1ffffff81ffffff81ffffff81ffffff807ffffe003ffffc001ffff8000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0001ffff8003ffffc00ffffff01ffffff83ffffffc3ffffffc3ffffffc3ffffffc3f87e1fc3f87e1fc3f87e1fc, 0.60, 0.73),
    "Q": (0x007ffe0003ffffc003ffffc003ffffc003ffffc003ffffc003ffffc003ffffc003ffffc003ffffc007ffffe007ffffe007ffffe00ffffff00ffffff00ffffff00ffffff00f7bdef00e7bde700e73ce300c73ce301873ce1818618618106186087041820ef841821ff8c1831ff9e1879f73e3c7ce01e3c78001c3c3800003c000, 0.83, 0.76),
    "K": (0x007ffe0007ffffc00ffffff007ffffe007ffffe007ffffe003ffffc003ffffc007ffffe007ffffe007ffffe01ffffff83ffffffc7ffffffe7ffffffeffffffffffffffffffffffffffffffffffffffff7ffffffe3ffffffc1feff7f80787e0e00007e0000003c0000001800000018000000180000003c0000001800000008000, 0.77, 0.76),
}


def mask_from_samples(samples: list[list[bool]]) -> tuple[int, float, float]:
    """Pack an ink map into ``(bits, width fraction, height fraction)``.

    ``samples`` is a rectangular grid of "is this pixel inked"; it is cropped to
    the ink bounding box and resampled to :data:`MASK_SIDE` squared, so the
    result is directly comparable with :data:`REFERENCE_MASKS`.  An empty grid
    yields ``(0, 0.0, 0.0)``.
    """
    rows = len(samples)
    cols = len(samples[0]) if rows else 0
    if not rows or not cols:
        return 0, 0.0, 0.0

    top, bottom, left, right = rows, -1, cols, -1
    for y in range(rows):
        row = samples[y]
        for x in range(cols):
            if row[x]:
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
                if x < left:
                    left = x
                if x > right:
                    right = x
    if bottom < 0:
        return 0, 0.0, 0.0

    box_h = bottom - top + 1
    box_w = right - left + 1
    bits = 0
    for out_y in range(MASK_SIDE):
        src_y = top + (out_y * box_h) // MASK_SIDE
        row = samples[src_y]
        base = out_y * MASK_SIDE
        for out_x in range(MASK_SIDE):
            src_x = left + (out_x * box_w) // MASK_SIDE
            if row[src_x]:
                bits |= 1 << (base + out_x)
    return bits, box_w / cols, box_h / rows


def match_mask(bits: int, width: float, height: float) -> tuple[str, float, float]:
    """Best matching piece type for a silhouette.

    Returns ``(piece letter, IoU, margin over the runner-up)``.  The aspect
    ratio is folded in as a mild tie-breaker, because pawn and rook silhouettes
    overlap heavily but a rook is markedly wider.  An empty mask returns
    ``("", 0.0, 0.0)``.
    """
    if not bits:
        return "", 0.0, 0.0
    aspect = width / height if height > 0 else 0.0
    scored: list[tuple[float, str]] = []
    for piece, (ref, ref_w, ref_h) in REFERENCE_MASKS.items():
        union = (bits | ref).bit_count()
        overlap = (bits & ref).bit_count() / union if union else 0.0
        ref_aspect = ref_w / ref_h if ref_h > 0 else 0.0
        penalty = min(0.15, abs(aspect - ref_aspect) * 0.30)
        scored.append((overlap - penalty, piece))
    scored.sort(reverse=True)
    best_score, best_piece = scored[0]
    margin = best_score - scored[1][0]
    return best_piece, max(0.0, min(1.0, best_score)), margin
