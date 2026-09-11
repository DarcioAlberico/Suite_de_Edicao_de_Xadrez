"""Bridge to the ChessVisionOFF_Puro trunk (``chess_diagram_ocr``).

The trunk is the production recogniser (85.798 lines, 4.412 passing tests) and
``docs/ASSETS.md`` is binding: it is absorbed, never rewritten. This module is the
only place in ``caissa.vision.classify`` that knows where it lives on disk, so the
rest of the package imports symbols from here instead of poking ``sys.path``.

Resolution order for the trunk root:

1. ``$CAISSA_CVOFF_ROOT``
2. a ``ChessVisionOFF_Puro`` directory beside the Caissa checkout
3. the reference-machine path ``C:/Python-Chess2/ChessVisionOFF_Puro``

Nothing here mutates the trunk. Adding its ``src`` to ``sys.path`` is the whole
integration: the accelerated paths in this package call the trunk's own
functions, so a change there is inherited rather than re-implemented.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = ["CVOFF_ROOT", "cvoff_root", "ensure_cvoff_on_path", "trunk_model_path"]

_REFERENCE_ROOT = Path("C:/Python-Chess2/ChessVisionOFF_Puro")


def cvoff_root() -> Path:
    """Locate the ChessVisionOFF_Puro checkout.

    Returns:
        Path to the trunk root (the directory containing ``src/chess_diagram_ocr``).

    Raises:
        FileNotFoundError: When no candidate contains the package. Failing loudly
            beats importing a half-present tree and blaming the model later.
    """
    candidates: list[Path] = []
    env = os.environ.get("CAISSA_CVOFF_ROOT")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    for parent in here.parents:
        sibling = parent.parent / "ChessVisionOFF_Puro"
        if sibling not in candidates:
            candidates.append(sibling)
        if parent.name == "Suite_de_Edicao_de_Xadrez":
            break
    candidates.append(_REFERENCE_ROOT)

    for candidate in candidates:
        if (candidate / "src" / "chess_diagram_ocr" / "__init__.py").is_file():
            return candidate.resolve()

    tried = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        "ChessVisionOFF_Puro nao foi encontrado. Aponte CAISSA_CVOFF_ROOT para a raiz do "
        f"tronco (a pasta que contem src/chess_diagram_ocr). Tentado:\n  {tried}"
    )


CVOFF_ROOT = None


def ensure_cvoff_on_path() -> Path:
    """Put the trunk's ``src`` on ``sys.path`` exactly once. Returns the root."""
    global CVOFF_ROOT
    root = cvoff_root()
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    CVOFF_ROOT = root
    return root


def trunk_model_path() -> Path:
    """The production checkpoint ``models/piece_classifier.pt`` inside the trunk."""
    return cvoff_root() / "models" / "piece_classifier.pt"
