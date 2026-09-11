"""FEN parsing and validation, with no dependency on ``python-chess``.

The Document IR must serialise, validate and round-trip in an environment where
``python-chess`` is not installed -- that is what keeps ``caissa.core`` a
dependency-free core that imports in milliseconds and can be exercised inside a
half-broken environment. Legality *reasoning* (is this move legal from this
position?) belongs to the notation subsystem and does use ``python-chess``;
everything here is structural and self-contained.

The checks implemented are the ones the structural validator needs and the ones
that catch real recognition failures (SPEC section 6.4): rank widths, piece
alphabet, king counts, pawns on the back ranks, and piece-count ceilings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = [
    "EMPTY_BOARD_FEN",
    "PIECE_LETTERS",
    "STARTING_FEN",
    "FenError",
    "FenPosition",
    "board_squares",
    "is_valid_fen",
    "parse_fen",
    "position_problems",
    "validate_fen",
]

#: The standard initial array.
STARTING_FEN: Final = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

#: An empty board, the starting point for a composed problem diagram.
EMPTY_BOARD_FEN: Final = "8/8/8/8/8/8/8/8 w - - 0 1"

#: Every legal piece character in a FEN placement field.
PIECE_LETTERS: Final = "pnbrqkPNBRQK"

_PLACEMENT_RE: Final = re.compile(r"^[pnbrqkPNBRQK1-8/]+$")
_EN_PASSANT_RE: Final = re.compile(r"^[a-h][36]$")
_CASTLING_RE: Final = re.compile(r"^(?:-|[KQkqA-Ha-h]{1,4})$")

_MAX_PIECES_PER_SIDE: Final = 16
_MAX_PAWNS_PER_SIDE: Final = 8

#: A FEN needs at least placement, side, castling and en passant.
_MIN_FIELDS: Final = 4

#: ... and never carries more than the six standard fields.
_MAX_FIELDS: Final = 6

#: Field counts at which each of the two clock fields becomes present.
_FIELDS_WITH_HALFMOVE: Final = 5
_FIELDS_WITH_FULLMOVE: Final = 6

#: The board is eight ranks of eight files.
_RANKS: Final = 8
_FILES: Final = 8


class FenError(ValueError):
    """Raised when a string cannot be parsed as a FEN."""


@dataclass(frozen=True, slots=True)
class FenPosition:
    """A parsed FEN.

    Attributes:
        squares: Sixty-four entries indexed from ``a1`` (0) to ``h8`` (63),
            counting files within ranks. Empty squares are the empty string.
        side_to_move: ``"w"`` or ``"b"``.
        castling: The castling availability field, verbatim.
        en_passant: The en passant target square, or ``"-"``.
        halfmove_clock: Plies since the last capture or pawn move.
        fullmove_number: The move number, starting at 1.
    """

    squares: tuple[str, ...]
    side_to_move: str
    castling: str
    en_passant: str
    halfmove_clock: int
    fullmove_number: int

    def piece_at(self, index: int) -> str:
        """Return the piece letter on a square index, or the empty string.

        Args:
            index: A value in ``[0, 64)``, ``0`` being ``a1``.

        Returns:
            The FEN piece letter, or ``""`` when the square is empty.

        Raises:
            IndexError: If the index is out of range.
        """
        return self.squares[index]

    def count(self, piece: str) -> int:
        """Count occurrences of a piece letter on the board.

        Args:
            piece: A FEN piece letter, e.g. ``"K"`` or ``"p"``.

        Returns:
            How many of them are on the board.
        """
        return sum(1 for square in self.squares if square == piece)

    def placement_field(self) -> str:
        """Re-render the piece placement field.

        Returns:
            The placement field in canonical form, with runs of empty squares
            collapsed into digits.
        """
        ranks: list[str] = []
        for rank in range(7, -1, -1):
            text = ""
            empty = 0
            for file_index in range(8):
                piece = self.squares[rank * 8 + file_index]
                if piece:
                    if empty:
                        text += str(empty)
                        empty = 0
                    text += piece
                else:
                    empty += 1
            if empty:
                text += str(empty)
            ranks.append(text)
        return "/".join(ranks)

    def to_fen(self) -> str:
        """Re-render the complete six-field FEN.

        Returns:
            The canonical FEN string for this position.
        """
        return (
            f"{self.placement_field()} {self.side_to_move} {self.castling} "
            f"{self.en_passant} {self.halfmove_clock} {self.fullmove_number}"
        )


def board_squares(fen: str) -> tuple[str, ...]:
    """Return the 64 square contents of a FEN, ``a1`` first.

    Args:
        fen: A FEN string; only the placement field is read.

    Returns:
        Sixty-four entries, empty string for an empty square.

    Raises:
        FenError: If the placement field is malformed.
    """
    return parse_fen(fen).squares


def parse_fen(fen: str) -> FenPosition:
    """Parse a FEN string.

    Accepts the standard six fields and also the shortened four- and five-field
    forms produced by EPD tooling, defaulting the clocks.

    Args:
        fen: The FEN string.

    Returns:
        The parsed position.

    Raises:
        FenError: If any field is malformed.
    """
    problems = validate_fen(fen)
    if problems:
        raise FenError(problems[0])
    return _parse_unchecked(fen)


def is_valid_fen(fen: str) -> bool:
    """Report whether a string is a structurally valid FEN.

    Args:
        fen: The candidate string.

    Returns:
        ``True`` when :func:`validate_fen` finds nothing wrong.
    """
    return not validate_fen(fen)


def validate_fen(fen: str) -> tuple[str, ...]:
    """Check the structure of a FEN and describe every problem found.

    Structural only: it does not ask whether the position could arise from the
    initial array. Use :func:`position_problems` for the chess-legality layer.

    Args:
        fen: The candidate string.

    Returns:
        Human-readable problem descriptions, in Brazilian Portuguese; empty when
        the string is well formed.
    """
    if not isinstance(fen, str) or not fen.strip():
        return ("FEN vazia.",)
    parts = fen.split()
    if len(parts) < _MIN_FIELDS:
        return (f"FEN precisa de ao menos {_MIN_FIELDS} campos; encontrados {len(parts)}.",)
    if len(parts) > _MAX_FIELDS:
        return (f"FEN aceita no maximo {_MAX_FIELDS} campos; encontrados {len(parts)}.",)

    problems: list[str] = []
    placement = parts[0]
    problems.extend(_placement_problems(placement))

    side = parts[1]
    if side not in ("w", "b"):
        problems.append(f"lado a jogar deve ser 'w' ou 'b'; encontrado {side!r}.")

    castling = parts[2]
    if not _CASTLING_RE.match(castling):
        problems.append(f"campo de roque invalido: {castling!r}.")
    elif castling != "-" and len(set(castling)) != len(castling):
        problems.append(f"campo de roque com letras repetidas: {castling!r}.")

    en_passant = parts[3]
    if en_passant != "-" and not _EN_PASSANT_RE.match(en_passant):
        problems.append(f"casa de en passant invalida: {en_passant!r}.")

    if len(parts) >= _FIELDS_WITH_HALFMOVE:
        problems.extend(_integer_problems(parts[4], "relogio de meio-lance", minimum=0))
    if len(parts) >= _FIELDS_WITH_FULLMOVE:
        problems.extend(_integer_problems(parts[5], "numero do lance", minimum=1))

    return tuple(problems)


def position_problems(fen: str, *, allow_composition: bool = False) -> tuple[str, ...]:
    """Check a position against the chess-legality constraints of SPEC 6.4.

    These are the constraints the FEN repair solver uses, and the ones that
    catch a misread square: a board with two white kings or a pawn on the first
    rank did not come from a real game.

    Args:
        fen: A structurally valid FEN.
        allow_composition: Permit a missing king. Composed problems sometimes
            omit one; a scanned game diagram never does.

    Returns:
        Human-readable problem descriptions, in Brazilian Portuguese; empty when
        the position satisfies every constraint.
    """
    structural = validate_fen(fen)
    if structural:
        return structural
    position = _parse_unchecked(fen)
    problems: list[str] = []

    for piece, side in (("K", "brancas"), ("k", "pretas")):
        count = position.count(piece)
        if count > 1:
            problems.append(f"ha {count} reis das {side}; o maximo e 1.")
        elif count == 0 and not allow_composition:
            problems.append(f"nao ha rei das {side}.")

    for piece, side in (("P", "brancas"), ("p", "pretas")):
        count = position.count(piece)
        if count > _MAX_PAWNS_PER_SIDE:
            problems.append(f"ha {count} peoes das {side}; o maximo e {_MAX_PAWNS_PER_SIDE}.")

    for index in list(range(8)) + list(range(56, 64)):
        piece = position.squares[index]
        if piece in ("P", "p"):
            file_char = "abcdefgh"[index % 8]
            rank = index // 8 + 1
            problems.append(f"peao em {file_char}{rank}: peoes nao ocupam a 1a nem a 8a fileira.")

    white = sum(1 for square in position.squares if square.isupper())
    black = sum(1 for square in position.squares if square.islower())
    if white > _MAX_PIECES_PER_SIDE:
        problems.append(f"ha {white} pecas brancas; o maximo e {_MAX_PIECES_PER_SIDE}.")
    if black > _MAX_PIECES_PER_SIDE:
        problems.append(f"ha {black} pecas pretas; o maximo e {_MAX_PIECES_PER_SIDE}.")

    problems.extend(_adjacent_kings_problems(position))
    return tuple(problems)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _placement_problems(placement: str) -> list[str]:
    """Validate the piece placement field.

    Args:
        placement: The first FEN field.

    Returns:
        Problem descriptions, empty when the field is well formed.
    """
    if not _PLACEMENT_RE.match(placement):
        bad = sorted({char for char in placement if char not in PIECE_LETTERS + "12345678/"})
        return [f"campo de pecas com caracteres invalidos: {''.join(bad)!r}."]
    ranks = placement.split("/")
    if len(ranks) != _RANKS:
        return [f"campo de pecas precisa de {_RANKS} fileiras; encontradas {len(ranks)}."]
    problems: list[str] = []
    for offset, rank_text in enumerate(ranks):
        width = 0
        previous_digit = False
        for char in rank_text:
            if char.isdigit():
                if previous_digit:
                    problems.append(
                        f"fileira {8 - offset} usa digitos consecutivos ({rank_text!r}); "
                        "cada corrida de casas vazias e um digito so."
                    )
                width += int(char)
                previous_digit = True
            else:
                width += 1
                previous_digit = False
        if width != _FILES:
            problems.append(
                f"fileira {8 - offset} soma {width} casas em vez de {_FILES}: {rank_text!r}."
            )
    return problems


def _integer_problems(text: str, label: str, *, minimum: int) -> list[str]:
    """Validate one of the trailing numeric FEN fields.

    Args:
        text: The field text.
        label: Human-readable field name for the message.
        minimum: Smallest accepted value.

    Returns:
        Problem descriptions, empty when the field is well formed.
    """
    if not text.isdigit():
        return [f"{label} deve ser um inteiro; encontrado {text!r}."]
    if int(text) < minimum:
        return [f"{label} deve ser >= {minimum}; encontrado {text}."]
    return []


def _adjacent_kings_problems(position: FenPosition) -> list[str]:
    """Check that the two kings are not on adjacent squares.

    Args:
        position: A parsed position.

    Returns:
        A single problem description when the kings touch, otherwise empty.
    """
    white_index = next((i for i, piece in enumerate(position.squares) if piece == "K"), None)
    black_index = next((i for i, piece in enumerate(position.squares) if piece == "k"), None)
    if white_index is None or black_index is None:
        return []
    file_distance = abs(white_index % 8 - black_index % 8)
    rank_distance = abs(white_index // 8 - black_index // 8)
    if max(file_distance, rank_distance) <= 1:
        return ["os reis estao em casas adjacentes."]
    return []


def _parse_unchecked(fen: str) -> FenPosition:
    """Build a :class:`FenPosition` from a FEN already known to be well formed.

    Args:
        fen: A structurally valid FEN.

    Returns:
        The parsed position.
    """
    parts = fen.split()
    squares: list[str] = [""] * 64
    for offset, rank_text in enumerate(parts[0].split("/")):
        rank = 7 - offset
        file_index = 0
        for char in rank_text:
            if char.isdigit():
                file_index += int(char)
            else:
                squares[rank * 8 + file_index] = char
                file_index += 1
    return FenPosition(
        squares=tuple(squares),
        side_to_move=parts[1],
        castling=parts[2],
        en_passant=parts[3],
        halfmove_clock=int(parts[4]) if len(parts) >= _FIELDS_WITH_HALFMOVE else 0,
        fullmove_number=int(parts[5]) if len(parts) >= _FIELDS_WITH_FULLMOVE else 1,
    )
