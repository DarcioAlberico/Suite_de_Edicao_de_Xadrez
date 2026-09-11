"""Whole-board cell preprocessing: 64 OpenCV call pairs collapsed into two.

What the trunk does per board (``inference.board_probabilities_batch`` ->
``model.preprocess_cell_to_tensor``), for every one of the 64 squares:

    cv2.cvtColor(cell_100x100, RGB2GRAY)  ->  cv2.resize(.., 64x64, INTER_AREA)
    -> astype(float32)/255 -> torch.from_numpy -> unsqueeze

That is 64 colour conversions, 64 resizes, 64 casts and 64 tensor wraps, then a
``torch.stack``. The pixel work is trivial (640.000 pixels); the *per-call* work
is not, and it is paid once per square per orientation per diagram.

The identity this module exploits
---------------------------------
``BOARD_SIZE`` is 800 and ``CELL_SIZE`` is 100, so a cell resized 100 -> 64 uses
scale 1.5625 -- exactly the scale of the whole board resized 800 -> 512. Because
64 * 1.5625 == 100 is an *integer*, every cell boundary in the source lands on an
output pixel boundary: no output pixel of the whole-board resize ever straddles
two cells. So

    resize(board, 512)  then split into 8x8 tiles of 64x64

and

    split into 8x8 cells of 100x100  then resize each to 64

produce the same bytes. And ``cvtColor`` is pointwise, so hoisting it to the whole
board changes nothing either.

This is not an argument to be taken on faith: :func:`assert_equivalent_to_trunk`
checks it against the trunk's own functions, and
``tests/integration/test_gpu_parity.py`` runs it over real board crops. Measured
on 30 random 800x800 boards (7.864.320 pixels) the two paths agree **bit for
bit** -- max abs diff 0, zero differing pixels.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

__all__ = [
    "assert_equivalent_to_trunk",
    "boards_to_cell_array",
    "board_to_cell_array",
    "fast_path_supported",
]


def _cv2() -> Any:
    import cv2

    return cv2


@lru_cache(maxsize=1)
def _trunk() -> tuple[Any, Any, Any]:
    """(config module, model module, board_detection module) from the trunk."""
    from caissa.vision.classify.cvoff import ensure_cvoff_on_path

    ensure_cvoff_on_path()
    from chess_diagram_ocr import board_detection, config, model  # noqa: PLC0415

    return config, model, board_detection


def fast_path_supported(arch: Any) -> bool:
    """Whether the whole-board shortcut is provably equivalent for this arch.

    It needs the cell grid to divide the board evenly and the model input size to
    divide the resized board evenly -- both true for the production
    ``cnn-gray-64-linear``. Anything else falls back to the trunk's per-cell loop
    rather than guessing.
    """
    config, _, _ = _trunk()
    board = int(config.BOARD_SIZE)
    cell = int(config.CELL_SIZE)
    size = int(arch.image_size)
    if cell * 8 != board or size <= 0:
        return False
    if board % (8 * size) != 0 and (8 * size) > board:
        return False
    # The scale must be identical for cell-wise and board-wise resizing, which it
    # is by construction (cell/size == board/(8*size)); the guard is against a
    # future BOARD_SIZE that breaks the integer cell boundary.
    return cell * (8 * size) == board * size and arch.channels in ("gray", "rgb")


@lru_cache(maxsize=64)
def _coordinate_planes(size: int) -> np.ndarray:
    """(64, 3, S, S) constant planes matching ``model.coordinate_channels``."""
    _, model_mod, _ = _trunk()
    planes = np.empty((64, model_mod.COORDINATE_CHANNELS, size, size), dtype=np.float32)
    for index in range(64):
        planes[index] = model_mod.coordinate_channels(index, size).numpy()
    planes.setflags(write=False)
    return planes


def board_to_cell_array(board_rgb: np.ndarray, arch: Any) -> np.ndarray:
    """One board (RGB uint8) -> ``(64, C, S, S)`` float32 in [0, 1], reading order.

    Byte-identical to stacking the trunk's ``preprocess_cell_to_tensor`` over
    ``split_board_into_cells``; see the module docstring for why.
    """
    cv2 = _cv2()
    config, model_mod, _ = _trunk()
    board_size = int(config.BOARD_SIZE)
    size = int(arch.image_size)

    if board_rgb.shape[0] != board_size or board_rgb.shape[1] != board_size:
        # Same call the trunk's split_board_into_cells makes, same interpolation.
        board_rgb = cv2.resize(board_rgb, (board_size, board_size))

    if arch.channels == "gray":
        plane = cv2.cvtColor(board_rgb, cv2.COLOR_RGB2GRAY)
        resized = cv2.resize(plane, (8 * size, 8 * size), interpolation=cv2.INTER_AREA)
        tiles = resized.reshape(8, size, 8, size).transpose(0, 2, 1, 3).reshape(64, 1, size, size)
    else:
        resized = cv2.resize(board_rgb, (8 * size, 8 * size), interpolation=cv2.INTER_AREA)
        tiles = (
            resized.reshape(8, size, 8, size, 3)
            .transpose(0, 2, 4, 1, 3)
            .reshape(64, 3, size, size)
        )

    cells = np.ascontiguousarray(tiles, dtype=np.float32)
    cells /= 255.0

    if arch.coords:
        cells = np.concatenate((cells, _coordinate_planes(size)), axis=1)
    return cells


def boards_to_cell_array(boards_rgb: list[np.ndarray], arch: Any) -> np.ndarray:
    """N boards -> one contiguous ``(N*64, C, S, S)`` float32 array.

    The row order is ``board-major, square-in-reading-order``, which is the
    contract ``board_probabilities_batch`` documents and the per-board head of
    S-62b depends on. Shuffling here would not raise -- it would silently produce
    a wrong reading.
    """
    if not boards_rgb:
        size = int(arch.image_size)
        return np.empty((0, arch.in_channels, size, size), dtype=np.float32)
    parts = [board_to_cell_array(board, arch) for board in boards_rgb]
    if len(parts) == 1:
        return parts[0]
    return np.concatenate(parts, axis=0)


def to_torch_batch(cells: np.ndarray, *, pin_memory: bool = False) -> "torch.Tensor":
    """Wrap the preprocessed array as a torch tensor, optionally page-locked.

    Pinned memory is what makes ``.to(device, non_blocking=True)`` actually
    asynchronous; on pageable memory the copy is synchronous and the flag is a
    no-op that costs a pin attempt.
    """
    import torch

    tensor = torch.from_numpy(cells)
    if pin_memory and cells.size and not tensor.is_pinned():
        try:
            tensor = tensor.pin_memory()
        except RuntimeError:
            # No CUDA context, or the allocation was refused. Pageable is correct,
            # just slower -- never a reason to fail a recognition.
            pass
    return tensor


def assert_equivalent_to_trunk(board_rgb: np.ndarray, arch: Any) -> dict[str, float]:
    """Compare this module against the trunk's per-cell path on one board.

    Returns:
        ``{"max_abs_diff": float, "differing": int, "count": int}``. The
        equivalence claim is ``max_abs_diff == 0``.
    """
    import torch

    _, model_mod, board_detection = _trunk()
    reference = torch.stack(
        [
            model_mod.with_coordinate_channels(
                model_mod.preprocess_cell_to_tensor(cell, arch), index, arch
            )
            for index, cell in enumerate(board_detection.split_board_into_cells(board_rgb))
        ],
        dim=0,
    ).numpy()
    fast = board_to_cell_array(board_rgb, arch)
    diff = np.abs(reference.astype(np.float64) - fast.astype(np.float64))
    return {
        "max_abs_diff": float(diff.max()) if diff.size else 0.0,
        "differing": int((diff != 0).sum()),
        "count": int(diff.size),
    }
