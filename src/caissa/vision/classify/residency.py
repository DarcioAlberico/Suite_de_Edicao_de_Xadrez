"""Registration of the square classifier with the shared VRAM budget (ADR-0004).

ADR-0004 is explicit: 8 GB of VRAM are contested by the detector, this
classifier, one or more OCR engines and an LLM; the sum of the peaks exceeds the
card, and "no subsystem may assume exclusive ownership". So the classifier is not
loaded by whoever happens to need it first -- it is *declared* here, with its
measured footprint, and borrowed through
:meth:`~caissa.vision.runtime.residency.ModelResidencyManager.acquire`.

The classifier registers ``pinned=True``. It is the smallest resident by two
orders of magnitude (2,19 M parameters, 8,4 MiB of weights) and it is on the hot
path of every page, so evicting it to make room would trade a large, repeated
cost for a negligible amount of memory. ADR-0004 names the LLM as the first
eviction candidate; this is the other end of that same ordering.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from caissa.vision.classify.batched import BatchedClassifier
from caissa.vision.classify.cvoff import trunk_model_path

__all__ = [
    "SQUARE_CLASSIFIER",
    "SQUARE_CLASSIFIER_VRAM_BYTES",
    "acquire_square_classifier",
    "register_square_classifier",
    "shared_square_classifier",
]

SQUARE_CLASSIFIER = "square-classifier"

SQUARE_CLASSIFIER_VRAM_BYTES = 620 * 1024**2
"""Declared footprint: weights plus the activations of one full-page forward.

Measured, not estimated -- ``torch.cuda.max_memory_allocated`` over the
production batch (``DEFAULT_MAX_CELLS_PER_FORWARD`` = 2048 cells = 16 diagrams x
2 orientations x 64 squares), rounded up. The number and how it was obtained are
in ``docs/quality/F4GPU_REPORT.md``. An optimistic value here causes real OOMs in
the middle of a 500-PDF batch, which ADR-0004 calls the worst possible moment, so
it is rounded **up**.
"""


def register_square_classifier(
    manager: Any = None,
    *,
    model_path: Path | None = None,
    vram_bytes: int = SQUARE_CLASSIFIER_VRAM_BYTES,
    replace: bool = False,
    **classifier_kwargs: Any,
) -> Any:
    """Declare the square classifier with the residency manager. Returns the manager.

    Nothing is loaded here: ADR-0004 requires load-on-demand, so the weights only
    reach the GPU on the first :func:`acquire_square_classifier`.
    """
    from caissa.vision.runtime import ModelSpec, get_residency_manager

    manager = manager if manager is not None else get_residency_manager()
    path = model_path if model_path is not None else trunk_model_path()

    def loader(device: str) -> BatchedClassifier:
        from chess_diagram_ocr.inference import load_model  # noqa: PLC0415

        from caissa.vision.classify.cvoff import ensure_cvoff_on_path

        ensure_cvoff_on_path()
        model, resolved = load_model(path, device=device)
        classifier = BatchedClassifier(model, resolved, **classifier_kwargs)
        # OCR_UI ciclo 2, passo C1: the weights' fingerprint travels with the
        # classifier, so every read it produces can say which model it was
        # (`DiagramHit.model_hash`).  Best effort: an unreadable file gives "".
        try:
            from chess_diagram_ocr.checkpoint import checkpoint_fingerprint

            classifier.model_hash = checkpoint_fingerprint(path)
        except Exception:  # noqa: BLE001 - identity is a courtesy, never a failure to load
            classifier.model_hash = ""
        return classifier

    manager.register(
        ModelSpec(
            name=SQUARE_CLASSIFIER,
            vram_bytes=vram_bytes,
            loader=loader,
            pinned=True,
            allow_cpu_fallback=True,
            description="Classificador de casas cnn-gray-64-linear (2,19 M par.)",
        ),
        replace=replace,
    )
    return manager


@contextmanager
def acquire_square_classifier(manager: Any = None, **kwargs: Any) -> Iterator[BatchedClassifier]:
    """Borrow the classifier under the shared budget.

    Registers it on first use, so callers do not need to know whether someone
    else already did::

        with acquire_square_classifier() as classifier:
            matrices = classifier.board_probabilities_batch(boards)
    """
    from caissa.vision.runtime import get_residency_manager

    manager = manager if manager is not None else get_residency_manager()
    if SQUARE_CLASSIFIER not in manager.registered():
        register_square_classifier(manager, **kwargs)
    with manager.acquire(SQUARE_CLASSIFIER) as lease:
        yield lease.model


_shared: BatchedClassifier | None = None
_shared_lock = threading.Lock()


def shared_square_classifier(manager: Any = None, **kwargs: Any) -> BatchedClassifier:
    """The one classifier of this process, loaded on first use under the shared budget.

    OCR_UI ciclo 2, passo A2: the product's import (``combined_finder``) runs
    in a thread next to the window's own reads, and a finder that loaded its
    own copy per call -- or per book -- would pay eight seconds and 620 MiB
    each time.  The classifier is registered ``pinned`` (never evicted), so
    the reference kept here stays valid after the lease of
    :func:`acquire_square_classifier` is returned; the first call loads it
    through the residency manager like any other borrower, the rest share it.
    """
    global _shared  # noqa: PLW0603 - one classifier per process is the point
    with _shared_lock:
        if _shared is None:
            with acquire_square_classifier(manager, **kwargs) as classifier:
                _shared = classifier
        return _shared
