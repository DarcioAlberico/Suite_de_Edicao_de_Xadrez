"""Position hashing -- ADR-0007's "busca por posição em milissegundos".

The question is "which of my 1,200 PDFs contains this position?", and the
answer has to come back before the user's finger leaves the mouse.  Comparing
placement strings means reading every row; comparing 64-bit integers means a
B-tree descent.  That is the whole trick, and it is what commercial databases
do.

**Why the placement only.**  A printed diagram gives the pieces.  It usually
does not give castling rights, it never gives the halfmove clock, and it gives
the side to move only when the caption says so.  Hashing the full FEN would
make a book diagram fail to match the same position in a game, which is the one
thing this index exists to do.  So the hash covers piece placement, and side to
move is stored beside it as a *filter*, not as part of the key.  This matches
what the trunk's scanner already treats as a position
(``games_db.GameRecord.positions`` yields ``Board.board_fen()``).

**Why not python-chess's own.**  ``chess.polyglot.zobrist_hash`` includes turn,
castling and en passant by design, and its table is tied to the Polyglot book
format.  This one is placement-only and its table is generated from a fixed
seed, so an index built today is readable next year.

**Collisions are handled, not hoped away.**  64 bits over a million positions
gives a birthday collision probability around 2.7e-8, which is small and not
zero -- and over a billion positions it stops being small.  So the packed
placement travels with every row (:func:`pack_placement`, 32 bytes, exact), and
a lookup compares it.  Two positions that share a hash both come back, tagged,
and the caller decides.  Silently returning the first one would be a wrong
answer that looks like a right one.
"""

from __future__ import annotations

import random
from typing import Final

__all__ = [
    "PLACEMENT_BYTES",
    "ZOBRIST_VERSION",
    "hash_placement",
    "pack_placement",
    "placement_from_fen",
    "unpack_placement",
]

#: Bumped if the table or the hashed content ever changes.  Stored in the index
#: so a mismatch is reported as staleness instead of as silent misses.
ZOBRIST_VERSION: Final = "1"

#: Seed of the key table.  Fixed forever: the index outlives the process.
_SEED: Final = 0x_CA155A_2026

#: 64 squares x 12 piece kinds.  ``a1`` is square 0, matching python-chess.
_PIECES: Final = "PNBRQKpnbrqk"
_PIECE_INDEX: Final[dict[str, int]] = {piece: i for i, piece in enumerate(_PIECES)}


def _build_table() -> tuple[int, ...]:
    rng = random.Random(_SEED)  # noqa: S311 - a hash table, not a secret
    return tuple(rng.getrandbits(64) for _ in range(64 * len(_PIECES)))


_TABLE: Final[tuple[int, ...]] = _build_table()

#: The board.
_SQUARES: Final = 64

#: 64 squares, one nibble each: exact, comparable, and small enough to store on
#: every row.  Four bits hold 0 (empty) plus the twelve piece kinds.
PLACEMENT_BYTES: Final = 32

_SIGN_BIT: Final = 1 << 63
_MASK64: Final = (1 << 64) - 1


def placement_from_fen(fen: str) -> str:
    """The piece-placement field of a FEN, or the string itself if that is all it is.

    Accepts a full FEN, an EPD, or a bare placement, because callers get all
    three: the IR stores full FENs, a user pastes whatever their GUI copied, and
    the trunk's scanner speaks bare placements.
    """
    return fen.strip().split(" ", 1)[0]


def hash_placement(placement: str) -> int:
    """The 64-bit key for a piece placement, as a signed SQLite integer.

    Args:
        placement: FEN piece placement (``"rnbqkbnr/pppppppp/8/..."``).  A full
            FEN is accepted and its placement field used.

    Returns:
        The hash, already folded into the signed range SQLite stores, so the
        value round-trips through the database unchanged.
    """
    placement = placement_from_fen(placement)
    key = 0
    square = 56  # a8: the placement field writes the eighth rank first
    for char in placement:
        if char == "/":
            square -= 16
        elif char.isdigit():
            square += int(char)
        else:
            index = _PIECE_INDEX.get(char)
            if index is None:
                msg = f"colocacao invalida: caractere {char!r} em {placement!r}"
                raise ValueError(msg)
            key ^= _TABLE[square * len(_PIECES) + index]
            square += 1
    return key - (1 << 64) if key & _SIGN_BIT else key


def pack_placement(placement: str) -> bytes:
    """A placement as 32 exact bytes, for disambiguating a hash collision.

    Nibble per square, ``a1`` first.  Fixed width, so a comparison is a memcmp
    and a row is a predictable size.
    """
    placement = placement_from_fen(placement)
    squares = bytearray(64)
    square = 56
    for char in placement:
        if char == "/":
            square -= 16
        elif char.isdigit():
            square += int(char)
        else:
            index = _PIECE_INDEX.get(char)
            if index is None:
                msg = f"colocacao invalida: caractere {char!r} em {placement!r}"
                raise ValueError(msg)
            if not 0 <= square < _SQUARES:
                msg = f"colocacao com casas demais: {placement!r}"
                raise ValueError(msg)
            squares[square] = index + 1
            square += 1
    return bytes((squares[i] << 4) | squares[i + 1] for i in range(0, 64, 2))


def unpack_placement(packed: bytes) -> str:
    """Invert :func:`pack_placement`.  Used to show *what else* shared a hash."""
    if len(packed) != PLACEMENT_BYTES:
        msg = f"colocacao empacotada deve ter {PLACEMENT_BYTES} bytes, recebido {len(packed)}"
        raise ValueError(msg)
    squares = [0] * 64
    for i, byte in enumerate(packed):
        squares[i * 2] = byte >> 4
        squares[i * 2 + 1] = byte & 0x0F
    ranks: list[str] = []
    for rank in range(7, -1, -1):
        row: list[str] = []
        empty = 0
        for file in range(8):
            code = squares[rank * 8 + file]
            if code == 0:
                empty += 1
                continue
            if empty:
                row.append(str(empty))
                empty = 0
            row.append(_PIECES[code - 1])
        if empty:
            row.append(str(empty))
        ranks.append("".join(row))
    return "/".join(ranks)
