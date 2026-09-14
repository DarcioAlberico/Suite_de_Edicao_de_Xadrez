"""Atalho para ``caissa-treinar`` (``caissa.ocr.training.cli``), sem instalar o pacote.

python tools/treinar_tesseract.py --project labeling --document "Livro" --book --base-lang eng
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.ocr.training.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
