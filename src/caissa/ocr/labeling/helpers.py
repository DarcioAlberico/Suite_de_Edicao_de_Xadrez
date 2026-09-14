"""What both labelling windows (Tk bench, Qt tab) decide the same way — no toolkit here."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .model import LineStatus

__all__ = [
    "FIGURINE_KEYS",
    "STATUS_COLOR",
    "default_project_dir",
    "fen_problem",
    "letters_to_figurines",
    "status_pt",
]

#: Line status → colour of its box on the page and of its row in the list.
STATUS_COLOR = {
    LineStatus.PENDING: "#d97706",  # amber: still to look at
    LineStatus.ACCEPTED: "#16a34a",  # green
    LineStatus.EDITED: "#2563eb",  # blue
    LineStatus.REJECTED: "#6b7280",  # grey: not text
}
#: Alt+key → figurine, in the truth field and on the palette.
FIGURINE_KEYS = {"k": "♔", "q": "♕", "r": "♖", "b": "♗", "n": "♘", "p": "♙"}
_LETTER_TO_FIGURINE = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘"}
#: A piece letter that starts a move: optional glued move number before it,
#: a square (with optional disambiguation and capture) after it.
_PIECE_MOVE = re.compile(
    r"(?<![A-Za-z♔-♙])(?P<number>\d{1,3}\.{0,3})?(?P<piece>[KQRBN])"
    r"(?=[a-h]?[1-8]?x?[a-h][1-8])"
)
FEN_RANKS = 8


def letters_to_figurines(text: str) -> str:
    """``Nf3`` → ``♘f3`` for every English piece letter that starts a move."""
    return _PIECE_MOVE.sub(
        lambda m: (m.group("number") or "") + _LETTER_TO_FIGURINE[m.group("piece")], text
    )


def fen_problem(fen: str) -> str:
    """Why ``fen`` is not a position, or an empty string when it is."""
    try:
        import chess
    except ImportError:
        ranks = fen.split()[0].count("/") + 1
        shaped = len(fen.split()) in (4, 5, 6) and ranks == FEN_RANKS
        return "" if shaped else "FEN com formato inválido."
    try:
        chess.Board(fen)
    except ValueError as exc:
        return f"FEN inválida: {exc}"
    return ""


def status_pt(status: LineStatus) -> str:
    return {
        LineStatus.PENDING: "pendente",
        LineStatus.ACCEPTED: "aceita",
        LineStatus.EDITED: "editada",
        LineStatus.REJECTED: "rejeitada",
    }[status]


def default_project_dir() -> Path:
    """Where a labelling project lives when nobody said: ``labeling/`` at the
    repository root in a checkout, ``rotulagem/`` next to the executable in the
    bundle (its writable folders all sit there)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "rotulagem"
    return Path(__file__).resolve().parents[4] / "labeling"
