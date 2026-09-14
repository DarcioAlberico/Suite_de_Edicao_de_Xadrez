"""Atalho para ``caissa-rotular`` (``caissa.ocr.labeling.app``), sem instalar o pacote.

python tools/rotular.py [pasta_do_projeto] [--pdf livro.pdf] [--reviewer nome]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.ocr.labeling.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
