"""Chess domain primitives that the Document IR is allowed to depend on.

Everything in this package is pure standard library. It holds the parts of chess
knowledge the IR itself needs -- FEN structure and the multilingual notation
tables -- so that a document validates, serialises and round-trips even where
``python-chess`` is not installed.

Legality *reasoning* (which moves are legal from this position, is this SAN the
move it claims to be) lives in the notation subsystem and does use
``python-chess``; the split is deliberate and is what keeps ``caissa.core``
importable in milliseconds.
"""

from __future__ import annotations

from caissa.core.chess.fen import (
    EMPTY_BOARD_FEN,
    PIECE_LETTERS,
    STARTING_FEN,
    FenError,
    FenPosition,
    board_squares,
    is_valid_fen,
    parse_fen,
    position_problems,
    validate_fen,
)
from caissa.core.chess.notation_tables import (
    DEFAULT_LANGUAGE,
    FIGURINE_BLACK,
    FIGURINE_WHITE,
    PIECE_TABLES,
    SUPPORTED_LANGUAGES,
    FigurineSet,
    LanguageTable,
    MoveRenderStyle,
    NotationError,
    PieceType,
    figurine_for_piece,
    from_figurine,
    from_language,
    is_supported_language,
    language_table,
    piece_for_letter,
    piece_letter,
    render_san,
    to_figurine,
    to_language,
)

__all__ = [
    "DEFAULT_LANGUAGE",
    "EMPTY_BOARD_FEN",
    "FIGURINE_BLACK",
    "FIGURINE_WHITE",
    "PIECE_LETTERS",
    "PIECE_TABLES",
    "STARTING_FEN",
    "SUPPORTED_LANGUAGES",
    "FenError",
    "FenPosition",
    "FigurineSet",
    "LanguageTable",
    "MoveRenderStyle",
    "NotationError",
    "PieceType",
    "board_squares",
    "figurine_for_piece",
    "from_figurine",
    "from_language",
    "is_supported_language",
    "is_valid_fen",
    "language_table",
    "parse_fen",
    "piece_for_letter",
    "piece_letter",
    "position_problems",
    "render_san",
    "to_figurine",
    "to_language",
    "validate_fen",
]
