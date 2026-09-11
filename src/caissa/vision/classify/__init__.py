"""Accelerated square classification (front F4-GPU).

The recogniser itself is ChessVisionOFF_Puro's ``chess_diagram_ocr``; per
``docs/ASSETS.md`` it is absorbed, not rewritten. This package is an *adapter*
that makes the same code run on the RTX 5060, and it changes only two things:

* :mod:`caissa.vision.classify.preprocess` -- 64 OpenCV call pairs per board
  collapse into two, proven byte-identical to the trunk's per-cell loop.
* :mod:`caissa.vision.classify.batched` / :mod:`caissa.vision.classify.page` --
  every diagram of a page and both orientations go through **one** forward
  instead of one forward per diagram.

Decoding, orientation policy, legality and side inference are untouched trunk
code, which is why ``tests/integration/test_gpu_parity.py`` can assert *equality*
of FEN and per-square argmax rather than a tolerance.

Device selection is not done here: it goes through
``caissa.vision.runtime.get_device``, the single chokepoint that only returns
CUDA after a real kernel has produced numerically correct results (ADR-0003).
"""

from __future__ import annotations

from caissa.vision.classify.batched import (
    DEFAULT_MAX_CELLS_PER_FORWARD,
    BatchedClassifier,
    BatchStats,
    load_classifier,
)
from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path, trunk_model_path
from caissa.vision.classify.page import (
    PageTimings,
    predict_boards_batched,
    recognize_page_batched,
)
from caissa.vision.classify.preprocess import (
    assert_equivalent_to_trunk,
    board_to_cell_array,
    boards_to_cell_array,
    fast_path_supported,
)
from caissa.vision.classify.residency import (
    SQUARE_CLASSIFIER,
    SQUARE_CLASSIFIER_VRAM_BYTES,
    acquire_square_classifier,
    register_square_classifier,
)

__all__ = [
    "DEFAULT_MAX_CELLS_PER_FORWARD",
    "SQUARE_CLASSIFIER",
    "SQUARE_CLASSIFIER_VRAM_BYTES",
    "BatchStats",
    "BatchedClassifier",
    "PageTimings",
    "acquire_square_classifier",
    "assert_equivalent_to_trunk",
    "board_to_cell_array",
    "boards_to_cell_array",
    "cvoff_root",
    "ensure_cvoff_on_path",
    "fast_path_supported",
    "load_classifier",
    "predict_boards_batched",
    "recognize_page_batched",
    "register_square_classifier",
    "trunk_model_path",
]
