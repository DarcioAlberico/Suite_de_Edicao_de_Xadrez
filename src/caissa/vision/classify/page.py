"""Page-level recognition with one forward for the whole page.

``OcrService.recognize_page`` renders, detects, reads the caption context and then
hands the boards to ``_predict_boards``, which loops one ``predict_with_orientation``
per diagram. :func:`recognize_page_batched` keeps every one of those steps and
their order, and changes exactly one thing: the probability matrices for *all*
diagrams and *both* orientations are computed in a single batched call.

Everything downstream -- constrained decoding, the orientation policy, side
inference, the legality check, the ``RecognizedDiagram`` construction -- is the
trunk's own code called with the trunk's own arguments. That is what makes the
parity claim checkable as equality of FEN and per-square argmax rather than as a
tolerance.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from caissa.vision.classify.batched import BatchedClassifier
from caissa.vision.classify.cvoff import ensure_cvoff_on_path

__all__ = ["PageTimings", "predict_boards_batched", "recognize_page_batched"]


@dataclass
class PageTimings:
    """Wall-clock seconds per stage for one page."""

    render_s: float = 0.0
    detect_s: float = 0.0
    context_s: float = 0.0
    preprocess_s: float = 0.0
    forward_s: float = 0.0
    decode_s: float = 0.0
    diagrams: int = 0
    cells: int = 0
    forwards: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_s(self) -> float:
        return (
            self.render_s
            + self.detect_s
            + self.context_s
            + self.preprocess_s
            + self.forward_s
            + self.decode_s
        )

    def as_dict(self) -> dict[str, Any]:
        data = {
            "render_s": self.render_s,
            "detect_s": self.detect_s,
            "context_s": self.context_s,
            "preprocess_s": self.preprocess_s,
            "forward_s": self.forward_s,
            "decode_s": self.decode_s,
            "total_s": self.total_s,
            "diagrams": self.diagrams,
            "cells": self.cells,
            "forwards": self.forwards,
        }
        data.update(self.extra)
        return data


def _orientation_policy(decisive_margin: float, pawn_prior_margin: float) -> Any:
    from chess_diagram_ocr.orientation import (  # noqa: PLC0415
        ConfidenceMarginRule,
        CoordinateRule,
        OrientationPolicy,
        PawnPriorRule,
        SingleLegalRule,
        TightMarginFallback,
    )

    return OrientationPolicy(
        (
            CoordinateRule(),
            SingleLegalRule(),
            ConfidenceMarginRule(decisive_margin),
            PawnPriorRule(pawn_prior_margin),
            TightMarginFallback(),
        )
    )


def predict_boards_batched(
    boards_rgb: Sequence[np.ndarray],
    classifier: BatchedClassifier,
    *,
    mode: str = "auto",
    normalizer: Any = None,
    tta: bool = False,
    timings: PageTimings | None = None,
) -> list[Any]:
    """All boards of a page -> one ``OrientedPrediction`` each, one forward total.

    Args:
        boards_rgb: Warped board crops, RGB uint8, in reading order.
        classifier: A loaded :class:`BatchedClassifier`.
        mode: ``"auto"``, ``"0"`` or ``"180"``, same meaning as the trunk's.
        normalizer: ``NormalizerConfig``; ``None`` means ``IDENTITY``.
        tta: Kept for signature compatibility. Off by default and measured to be
            not worth it (``docs/ASSETS.md`` 2.14).
        timings: Optional accumulator for the preprocess/forward/decode split.

    Returns:
        One ``orientation.OrientedPrediction`` per input board, in input order.
    """
    ensure_cvoff_on_path()
    import cv2  # noqa: PLC0415

    from chess_diagram_ocr.config import (  # noqa: PLC0415
        CONSTRAINED_DECODING,
        ORIENTATION_DECISIVE_MARGIN,
        ORIENTATION_PAWN_PRIOR_MARGIN,
        UNCERTAIN_SQUARE_THRESHOLD,
    )
    from chess_diagram_ocr.inference import prediction_from_probs  # noqa: PLC0415
    from chess_diagram_ocr.orientation import (  # noqa: PLC0415
        OrientationEvidence,
        OrientedPrediction,
    )

    if mode not in ("auto", "0", "180"):
        raise ValueError("mode deve ser 'auto', '0' ou '180'; recebido " + repr(mode))
    if not boards_rgb:
        return []

    # The batch layout is the contract: for "auto" every board contributes the
    # upright view and then the 180-degree view, adjacent, in board order.
    flat: list[np.ndarray] = []
    for board in boards_rgb:
        if mode == "auto":
            flat.append(board)
            flat.append(cv2.rotate(board, cv2.ROTATE_180))
        elif mode == "180":
            flat.append(cv2.rotate(board, cv2.ROTATE_180))
        else:
            flat.append(board)

    before = classifier.stats.preprocess_s, classifier.stats.forward_s, classifier.stats.forwards
    matrices = classifier.board_probabilities_batch(flat, tta=tta, normalizer=normalizer)
    if timings is not None:
        timings.preprocess_s += classifier.stats.preprocess_s - before[0]
        timings.forward_s += classifier.stats.forward_s - before[1]
        timings.forwards += classifier.stats.forwards - before[2]
        timings.cells += len(flat) * 64

    start = time.perf_counter()
    policy = _orientation_policy(ORIENTATION_DECISIVE_MARGIN, ORIENTATION_PAWN_PRIOR_MARGIN)
    results: list[Any] = []
    if mode == "auto":
        for index in range(len(boards_rgb)):
            upright, flipped = (
                prediction_from_probs(
                    matrices[2 * index + offset],
                    uncertain_threshold=UNCERTAIN_SQUARE_THRESHOLD,
                    constrained=CONSTRAINED_DECODING,
                )
                for offset in (0, 1)
            )
            results.append(policy.resolve(OrientationEvidence(upright=upright, flipped=flipped)))
    else:
        rotation = 180 if mode == "180" else 0
        for index in range(len(boards_rgb)):
            prediction = prediction_from_probs(
                matrices[index],
                uncertain_threshold=UNCERTAIN_SQUARE_THRESHOLD,
                constrained=CONSTRAINED_DECODING,
            )
            results.append(
                OrientedPrediction(
                    prediction=prediction,
                    rotation=rotation,
                    margin=0.0,
                    ambiguous=False,
                    reason="orientacao imposta (" + str(rotation) + " graus)",
                )
            )
    if timings is not None:
        timings.decode_s += time.perf_counter() - start
    return results


def recognize_page_batched(
    pdf_source: Any,
    page_index: int,
    classifier: BatchedClassifier,
    *,
    options: Any,
    page_rgb: np.ndarray | None = None,
    candidates: Sequence[Any] | None = None,
    caption_reader: Any = None,
    timings: PageTimings | None = None,
) -> list[Any]:
    """``OcrService.recognize_page`` with the page's diagrams in one forward.

    Returns the same ``list[RecognizedDiagram]``, built by the same constructor
    from the same predictions.
    """
    ensure_cvoff_on_path()
    from chess_diagram_ocr.board_detection import NoBoardDetectedError  # noqa: PLC0415
    from chess_diagram_ocr.detection import detect_diagrams_in_pdf_page  # noqa: PLC0415
    from chess_diagram_ocr.fen_utils import check_position  # noqa: PLC0415
    from chess_diagram_ocr.pdf_io import render_pdf_page  # noqa: PLC0415
    from chess_diagram_ocr.pdf_text import contexts_for_pdf_page  # noqa: PLC0415
    from chess_diagram_ocr.semantics import compose_fen, infer_side_to_move  # noqa: PLC0415
    from chess_diagram_ocr.service import RecognizedDiagram  # noqa: PLC0415

    timings = timings if timings is not None else PageTimings()

    if page_rgb is None:
        start = time.perf_counter()
        page_rgb = render_pdf_page(pdf_source, page_index, dpi=options.dpi)
        timings.render_s += time.perf_counter() - start

    if candidates is None:
        start = time.perf_counter()
        candidates = detect_diagrams_in_pdf_page(
            pdf_source, page_index, page_rgb, max_boards=options.max_boards
        )
        timings.detect_s += time.perf_counter() - start

    start = time.perf_counter()
    contexts = contexts_for_pdf_page(
        pdf_source,
        page_index,
        [candidate.bbox_pdf for candidate in candidates],
        caption_reader=caption_reader,
    )
    timings.context_s += time.perf_counter() - start

    if not candidates:
        raise NoBoardDetectedError("Nenhum tabuleiro foi detectado na imagem selecionada.")

    boards = [candidate.board_rgb for candidate in candidates]
    oriented = predict_boards_batched(
        boards,
        classifier,
        mode=options.orientation,
        normalizer=options.normalizer,
        timings=timings,
    )
    timings.diagrams += len(boards)

    start = time.perf_counter()
    diagrams: list[Any] = []
    for index, board_rgb in enumerate(boards):
        prediction = oriented[index].prediction
        context = contexts[index] if index < len(contexts) else None
        side = infer_side_to_move(prediction.fen_board, context)
        diagrams.append(
            RecognizedDiagram.from_prediction(
                index,
                board_rgb,
                prediction,
                side=side,
                legality=check_position(compose_fen(prediction.fen_board, side)),
                rotation=oriented[index].rotation,
                orientation_ambiguous=oriented[index].ambiguous,
                orientation_reason=oriented[index].reason,
                quad=None,
                bbox_pdf=candidates[index].bbox_pdf,
                context=context,
                detection_source=candidates[index].source,
            )
        )
    timings.decode_s += time.perf_counter() - start
    return diagrams
