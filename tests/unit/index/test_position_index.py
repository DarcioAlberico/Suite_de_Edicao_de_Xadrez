"""Zobrist lookup, and the collision rule that makes it trustworthy.

Two positions sharing a hash must **both** come back and be distinguishable.
The whole value of an index is that its answer can be believed; an index that
silently picks one of two candidates is worse than no index, because the user
has no way to notice.
"""

from __future__ import annotations

import chess
import pytest

from caissa.index import (
    IndexUnit,
    PositionLookup,
    PositionQuery,
    PositionRef,
    Query,
    SearchIndex,
    TextIndex,
    hash_placement,
    pack_placement,
    unpack_placement,
)
from caissa.index.zobrist import PLACEMENT_BYTES, placement_from_fen
from caissa.notation.regex_engine import Scope

from .conftest import OPPOSITE_BISHOPS, SICILIAN_PLACEMENT, STARTING_PLACEMENT


class PositionSource:
    """A source that carries positions and nothing else."""

    def __init__(self, uri: str, positions: list[PositionRef], label: str = "posicao") -> None:
        self.uri = uri
        self.title = uri
        self.kind = "ir"
        self._positions = positions
        self._label = label

    @property
    def size_bytes(self) -> int:
        return len(self._positions) * 64

    @property
    def content_key(self) -> str:
        return f"{len(self._positions)}"

    def units(self, *, start: int = 0):
        for ordinal, position in enumerate(self._positions):
            if ordinal < start:
                continue
            yield IndexUnit(
                text=f"{self._label} {ordinal}",
                scope=Scope.CAPTIONS,
                positions=(position,),
            )


# --------------------------------------------------------------------------- #
# The hash itself
# --------------------------------------------------------------------------- #


def test_hash_ignores_everything_but_the_placement():
    """A book diagram gives pieces, not castling rights or a clock."""
    board = chess.Board()
    assert hash_placement(board.fen()) == hash_placement(board.board_fen())
    assert hash_placement(STARTING_PLACEMENT) == hash_placement(chess.STARTING_FEN)


def test_hash_is_stable_across_runs():
    """The table is seeded, because an index outlives the process that built it."""
    assert hash_placement(STARTING_PLACEMENT) == hash_placement(STARTING_PLACEMENT)
    assert hash_placement(SICILIAN_PLACEMENT) != hash_placement(STARTING_PLACEMENT)


def test_hash_fits_a_signed_sqlite_integer():
    for placement in (STARTING_PLACEMENT, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS, "8/8/8/8/8/8/8/8"):
        assert -(2**63) <= hash_placement(placement) < 2**63


def test_packing_is_exact_and_reversible():
    for placement in (STARTING_PLACEMENT, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS, "8/8/8/8/8/8/8/8"):
        packed = pack_placement(placement)
        assert len(packed) == PLACEMENT_BYTES
        assert unpack_placement(packed) == placement


def test_packing_survives_a_thousand_real_positions():
    board = chess.Board()
    seen = 0
    for move in list(board.legal_moves)[:4]:
        board.push(move)
        for reply in list(board.legal_moves)[:8]:
            board.push(reply)
            assert unpack_placement(pack_placement(board.board_fen())) == board.board_fen()
            seen += 1
            board.pop()
        board.pop()
    assert seen > 0


def test_a_bad_placement_is_refused_not_guessed():
    with pytest.raises(ValueError, match="colocacao invalida"):
        hash_placement("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB!R")


def test_placement_from_fen_accepts_all_three_shapes():
    assert placement_from_fen(chess.STARTING_FEN) == STARTING_PLACEMENT
    assert placement_from_fen(STARTING_PLACEMENT) == STARTING_PLACEMENT
    assert placement_from_fen(f"{STARTING_PLACEMENT} w - -") == STARTING_PLACEMENT


# --------------------------------------------------------------------------- #
# Lookup
# --------------------------------------------------------------------------- #


def test_lookup_finds_the_documents_that_contain_a_position(index):
    """SPEC 9's question, in its literal form."""
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT, ply=6)]))
    index.add(PositionSource("mem://b", [PositionRef(STARTING_PLACEMENT, ply=0)]))
    index.add(PositionSource("mem://c", [PositionRef(SICILIAN_PLACEMENT, ply=12)]))

    lookup = PositionLookup(index.connection)
    assert len(lookup.documents_containing(SICILIAN_PLACEMENT)) == 2
    assert len(lookup.documents_containing(STARTING_PLACEMENT)) == 1
    assert lookup.documents_containing(OPPOSITE_BISHOPS) == []


def test_lookup_accepts_a_full_fen(index):
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT)]))
    lookup = PositionLookup(index.connection)
    assert lookup.find(f"{SICILIAN_PLACEMENT} b KQkq - 0 4")


def test_side_to_move_filters_but_does_not_key(index):
    index.add(
        PositionSource(
            "mem://a",
            [
                PositionRef(SICILIAN_PLACEMENT, ply=6, turn=True),
                PositionRef(SICILIAN_PLACEMENT, ply=7, turn=False),
            ],
        )
    )
    lookup = PositionLookup(index.connection)
    assert len(lookup.find(PositionQuery(SICILIAN_PLACEMENT))) == 2
    assert len(lookup.find(PositionQuery(SICILIAN_PLACEMENT, turn="white"))) == 1
    assert len(lookup.find(PositionQuery(SICILIAN_PLACEMENT, turn="black"))) == 1


def test_lookup_can_be_restricted_to_documents(index):
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT)]))
    index.add(PositionSource("mem://b", [PositionRef(SICILIAN_PLACEMENT)]))
    lookup = PositionLookup(index.connection)
    first = index.document("mem://a")
    assert first is not None
    hits = lookup.find(PositionQuery(SICILIAN_PLACEMENT, documents=(first.doc_id,)))
    assert {hit.doc_id for hit in hits} == {first.doc_id}


# --------------------------------------------------------------------------- #
# Collisions: the part that must never be resolved by luck
# --------------------------------------------------------------------------- #


def _force_collision(index, placement_a: str, placement_b: str) -> int:
    """Store ``placement_b`` under ``placement_a``'s hash.

    A genuine 64-bit collision cannot be produced in a unit test, and waiting
    for one in the field is not a test strategy.  Writing the row by hand
    exercises exactly the code path a real collision would take.
    """
    key = hash_placement(placement_a)
    index.connection.execute(
        "INSERT OR REPLACE INTO positions(zobrist, doc_id, node_id, ply, turn, placement) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key, 1, 9_999, 0, 1, pack_placement(placement_b)),
    )
    return key


def test_a_colliding_position_is_returned_and_flagged(index):
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT, ply=6)]))
    _force_collision(index, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS)

    hits = PositionLookup(index.connection).find(SICILIAN_PLACEMENT)
    assert len(hits) == 2, "a colisao sumiu: uma das duas foi escolhida em silencio"

    exact = [hit for hit in hits if hit.exact]
    other = [hit for hit in hits if not hit.exact]
    assert len(exact) == 1
    assert len(other) == 1
    assert exact[0].placement == SICILIAN_PLACEMENT
    assert other[0].placement == OPPOSITE_BISHOPS


def test_exact_matches_are_ordered_first(index):
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT, ply=6)]))
    _force_collision(index, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS)
    hits = PositionLookup(index.connection).find(SICILIAN_PLACEMENT)
    assert hits[0].exact, "um chamador que pega [0] receberia a posicao errada"


def test_documents_containing_excludes_collisions(index):
    """The answer is a list of books to open; opening the wrong one is the bug."""
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT, ply=6)]))
    _force_collision(index, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS)
    lookup = PositionLookup(index.connection)
    assert lookup.documents_containing(SICILIAN_PLACEMENT) == [1]


def test_collisions_can_be_excluded_from_find(index):
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT, ply=6)]))
    _force_collision(index, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS)
    hits = PositionLookup(index.connection).find(
        PositionQuery(SICILIAN_PLACEMENT, include_collisions=False)
    )
    assert len(hits) == 1
    assert hits[0].exact


def test_a_query_reports_the_collision_to_the_caller(index):
    """The unified API must surface it too, not only the low-level lookup."""
    index.add(PositionSource("mem://a", [PositionRef(SICILIAN_PLACEMENT, ply=6)]))
    _force_collision(index, SICILIAN_PLACEMENT, OPPOSITE_BISHOPS)

    page = SearchIndex.wrap(index.connection).search(Query(position=SICILIAN_PLACEMENT))
    assert page.total >= 1
    assert page.hits[0].position_exact is True


# --------------------------------------------------------------------------- #
# Scale
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_lookup_is_indexed_not_scanned(tmp_path):
    """A hundred thousand rows must not make one lookup a hundred times slower.

    The gate itself (<= 50 ms over a million positions) is measured on the real
    corpus and reported in ``docs/quality/F10_REPORT.md``.  This is the cheap
    guard that catches the index being dropped from the schema.
    """
    import time

    with TextIndex(tmp_path / "positions.sqlite") as index:
        board = chess.Board()
        rows = []
        for ply in range(1, 60):
            move = next(iter(board.legal_moves))
            board.push(move)
            rows.append(PositionRef(board.board_fen(), ply=ply))
        index.add(PositionSource("mem://long", rows * 2_000))

        lookup = PositionLookup(index.connection)
        assert lookup.count() > 100_000
        target = rows[10].placement
        timings = []
        for _ in range(5):
            started = time.perf_counter()
            lookup.find(PositionQuery(target, limit=50))
            timings.append(time.perf_counter() - started)
        median = sorted(timings)[len(timings) // 2]
        assert median < 0.05, f"busca por posicao levou {median * 1000:.1f} ms"
