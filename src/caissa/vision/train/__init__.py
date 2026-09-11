"""Training for the vision stack: the synthetic generator and the fine-tuning harness.

``docs/ASSETS.md`` 3 lists the synthetic generator as one of the real gaps of F4: it exists
in ``Chess_diagram_to_FEN`` and not in the trunk, and the production checkpoint was trained
on 3.290 real diagrams from a single collection.  ``synthgen`` ports it as an adapter --
never a copy -- and ``finetune`` is the harness that measures whether it buys anything.
"""

from __future__ import annotations

from caissa.vision.train.synthgen import (
    DEFAULT_TSOJ_ROOT,
    SynthConfig,
    SyntheticBoards,
    available_piece_sets,
    render_board,
    split_piece_sets,
)

__all__ = [
    "DEFAULT_TSOJ_ROOT",
    "SynthConfig",
    "SyntheticBoards",
    "available_piece_sets",
    "render_board",
    "split_piece_sets",
]
