"""GPU-batched square classification, output-identical to the trunk.

What this replaces
------------------
``service.OcrService._predict_boards`` loops over the diagrams of a page and calls
``inference.predict_with_orientation`` once per diagram. The trunk already batches
*within* a diagram -- S-61 made the two orientations one forward of 128 cells --
but a page with six diagrams still pays six launches, six preprocessing loops and
six host<->device round trips.

:class:`BatchedClassifier` batches the whole page: every diagram, both
orientations, one forward. Six diagrams become 768 cells in a single launch.

What is deliberately *not* changed
----------------------------------
The decode side. ``prediction_from_probs`` (constrained decoding, S-11), the
orientation policy (S-48), side inference and the legality check are the trunk's
own functions, called on the trunk's own probability matrices. This class only
changes *how the (64, 13) matrices are computed*, which is why parity is testable
as an equality and not as a tolerance.

Two rejected ideas, per ``docs/ASSETS.md`` 2.14, are not re-proposed here: TTA
(7 views, +1 board in 320 at 6x cost) and the calibrated temperature (T=1,85,
doubled the review queue). ``tta`` is still accepted as a parameter because the
trunk's signature has it; the default stays off.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from caissa.vision.classify.cvoff import ensure_cvoff_on_path
from caissa.vision.classify.preprocess import (
    boards_to_cell_array,
    fast_path_supported,
    to_torch_batch,
)

logger = logging.getLogger(__name__)

__all__ = ["BatchStats", "BatchedClassifier", "DEFAULT_MAX_CELLS_PER_FORWARD", "load_classifier"]

DEFAULT_MAX_CELLS_PER_FORWARD = 2048
"""Cells per forward. 2048 = 16 diagrams x 2 orientations x 64 squares.

The cap exists for ADR-0004, not for speed: VRAM is a shared 7,0 GB budget and no
subsystem may assume exclusive ownership. Measured peak for a full-page forward is
reported by :meth:`BatchedClassifier.peak_vram_bytes`.
"""


@dataclass
class BatchStats:
    """Cumulative, per-stage timings collected by the classifier (seconds)."""

    preprocess_s: float = 0.0
    forward_s: float = 0.0
    calls: int = 0
    cells: int = 0
    forwards: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "preprocess_s": round(self.preprocess_s, 6),
            "forward_s": round(self.forward_s, 6),
            "calls": self.calls,
            "cells": self.cells,
            "forwards": self.forwards,
            "notes": list(self.notes),
        }


def load_classifier(
    model_path: Any = None,
    *,
    prefer: str | None = None,
    **kwargs: Any,
) -> BatchedClassifier:
    """Load the production checkpoint onto the verified device.

    Device selection goes through ``caissa.vision.runtime.get_device`` -- the one
    chokepoint (ADR-0003). It only returns CUDA after a real kernel has produced
    numerically correct results, so a silent CPU fallback is impossible and a
    deliberate one is logged here with the reason.
    """
    from caissa.vision.runtime import get_device, get_device_info

    ensure_cvoff_on_path()
    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH  # noqa: PLC0415
    from chess_diagram_ocr.inference import load_model  # noqa: PLC0415

    from caissa.vision.classify.cvoff import trunk_model_path

    if model_path is None:
        model_path = DEFAULT_MODEL_PATH
        if not model_path.exists():
            model_path = trunk_model_path()

    info = get_device_info()
    device_str = str(get_device(prefer))  # type: ignore[arg-type]

    if device_str.startswith("cpu"):
        # Never silent. Say which of the three it is.
        logger.warning(
            "Classificador em CPU. Motivo: %s | torch=%s cuda_build=%s is_available=%s",
            info.failure_reason or "nenhuma GPU CUDA presente",
            info.torch_version,
            info.cuda_build,
            info.cuda_reported_available,
        )
    else:
        capability = info.capability or (0, 0)
        logger.info(
            "Classificador em %s (%s, sm_%d%d, driver %s), verificado por computacao real.",
            device_str,
            info.name,
            capability[0],
            capability[1],
            info.driver_version,
        )

    model, resolved = load_model(model_path, device=device_str)
    return BatchedClassifier(model, resolved, **kwargs)


class BatchedClassifier:
    """The trunk's classifier, driven one page at a time instead of one board.

    Args:
        model: A loaded ``nn.Module`` from ``inference.load_model``.
        device: Device string it was placed on.
        dtype: ``"fp32"`` or ``"fp16"``. fp16 runs the forward under
            ``torch.autocast`` and is only shippable if the parity test says no
            FEN changed -- see ``docs/quality/F4GPU_REPORT.md``.
        max_cells_per_forward: VRAM guard, see
            :data:`DEFAULT_MAX_CELLS_PER_FORWARD`.
        pin_memory: Page-lock the host staging buffer so the H2D copy can overlap.
        fast_preprocess: Use the whole-board shortcut of
            :mod:`caissa.vision.classify.preprocess`. ``False`` falls back to the
            trunk's per-cell loop, which is what the parity test compares against.
    """

    def __init__(
        self,
        model: Any,
        device: str,
        *,
        dtype: str = "fp32",
        max_cells_per_forward: int = DEFAULT_MAX_CELLS_PER_FORWARD,
        pin_memory: bool = True,
        fast_preprocess: bool = True,
    ) -> None:
        import torch

        ensure_cvoff_on_path()
        from chess_diagram_ocr.model import DEFAULT_ARCH  # noqa: PLC0415

        if dtype not in ("fp32", "fp16"):
            raise ValueError("dtype deve ser 'fp32' ou 'fp16'; recebido " + repr(dtype))

        self.model = model
        self.device = device
        self.dtype = dtype
        self.max_cells_per_forward = max(64, int(max_cells_per_forward))
        self.is_cuda = device.startswith("cuda")
        self.pin_memory = bool(pin_memory) and self.is_cuda
        self.arch = getattr(model, "arch", DEFAULT_ARCH)
        self.temperature = float(getattr(model, "temperature", 1.0))
        self.stats = BatchStats()
        self._torch = torch

        self.fast_preprocess = bool(fast_preprocess) and fast_path_supported(self.arch)
        if fast_preprocess and not self.fast_preprocess:
            logger.warning(
                "Pre-processamento rapido indisponivel para a arquitetura %s; usando o "
                "laco por casa do tronco.",
                self.arch.version,
            )

    # ------------------------------------------------------------------ helpers

    def _sync(self) -> None:
        if self.is_cuda:
            self._torch.cuda.synchronize()

    def _preprocess(self, boards_rgb: Sequence[np.ndarray]) -> np.ndarray:
        if self.fast_preprocess:
            return boards_to_cell_array(list(boards_rgb), self.arch)

        from chess_diagram_ocr.board_detection import split_board_into_cells  # noqa: PLC0415
        from chess_diagram_ocr.model import (  # noqa: PLC0415
            preprocess_cell_to_tensor,
            with_coordinate_channels,
        )

        tensors = [
            with_coordinate_channels(preprocess_cell_to_tensor(cell, self.arch), index, self.arch)
            for board in boards_rgb
            for index, cell in enumerate(split_board_into_cells(board))
        ]
        return self._torch.stack(tensors, dim=0).numpy()

    def peak_vram_bytes(self) -> int:
        """``torch.cuda.max_memory_allocated`` for this process, or 0 on CPU."""
        if not self.is_cuda:
            return 0
        return int(self._torch.cuda.max_memory_allocated())

    def reset_peak_vram(self) -> None:
        if self.is_cuda:
            self._torch.cuda.reset_peak_memory_stats()

    def warmup(self, cells: int = 128) -> None:
        """Pay the one-off cuDNN autotune and allocator cost before timing.

        Without it the first page of a run carries ~200 ms of kernel selection
        that belongs to no stage in particular, and a benchmark that reports it as
        "forward" is lying about steady state.
        """
        size = int(self.arch.image_size)
        dummy = np.zeros((cells, self.arch.in_channels, size, size), dtype=np.float32)
        self.cell_probabilities(dummy)
        self.stats = BatchStats()

    # ---------------------------------------------------------------- inference

    def cell_probabilities(self, cells: np.ndarray) -> np.ndarray:
        """``(N, C, S, S)`` preprocessed cells -> ``(N, 13)`` float64 probabilities.

        The op order matches the trunk exactly: ``softmax(logits / temperature)``
        on device, then ``.cpu().numpy().astype(float64)``.
        """
        torch = self._torch
        ensure_cvoff_on_path()
        from chess_diagram_ocr.config import PIECE_CLASSES  # noqa: PLC0415

        if cells.shape[0] == 0:
            return np.zeros((0, len(PIECE_CLASSES)), dtype=np.float64)

        chunks: list[np.ndarray] = []
        limit = self.max_cells_per_forward
        for start in range(0, cells.shape[0], limit):
            piece = np.ascontiguousarray(cells[start : start + limit])
            host = to_torch_batch(piece, pin_memory=self.pin_memory)
            batch = host.to(self.device, non_blocking=self.pin_memory)

            with torch.inference_mode():
                if self.dtype == "fp16" and self.is_cuda:
                    with torch.autocast("cuda", dtype=torch.float16):
                        logits = self.model(batch)
                    logits = logits.float()
                else:
                    logits = self.model(batch)
                probs = torch.softmax(logits / self.temperature, dim=1)

            chunks.append(probs.cpu().numpy().astype(np.float64))
            self.stats.forwards += 1
        return chunks[0] if len(chunks) == 1 else np.concatenate(chunks, axis=0)

    def board_probabilities_batch(
        self,
        boards_rgb: Sequence[np.ndarray],
        *,
        tta: bool = False,
        normalizer: Any = None,
    ) -> list[np.ndarray]:
        """Drop-in for ``inference.board_probabilities_batch``, page-wide batched.

        Returns one ``(64, 13)`` float64 matrix per board, in input order.
        """
        if not boards_rgb:
            return []

        ensure_cvoff_on_path()
        from chess_diagram_ocr.config import PIECE_CLASSES  # noqa: PLC0415
        from chess_diagram_ocr.inference import tta_views  # noqa: PLC0415
        from chess_diagram_ocr.preprocess import IDENTITY, BoardNormalizer  # noqa: PLC0415

        normalizador = BoardNormalizer(normalizer if normalizer is not None else IDENTITY)

        start = time.perf_counter()
        per_board = [
            tta_views(normalizador.normalize(board)) if tta else [normalizador.normalize(board)]
            for board in boards_rgb
        ]
        flat = [view for views in per_board for view in views]
        cells = self._preprocess(flat)
        after_preprocess = time.perf_counter()

        plane = self.cell_probabilities(cells)
        after_forward = time.perf_counter()

        self.stats.preprocess_s += after_preprocess - start
        self.stats.forward_s += after_forward - after_preprocess
        self.stats.calls += 1
        self.stats.cells += int(cells.shape[0])

        out: list[np.ndarray] = []
        cursor = 0
        for views in per_board:
            stop = cursor + len(views) * 64
            matrices = plane[cursor:stop].reshape(len(views), 64, len(PIECE_CLASSES))
            out.append(matrices.mean(axis=0))
            cursor = stop
        return out
