"""Position lookup for the question SPEC 9 asks by name.

The whole answer is one indexed integer comparison.  ``positions`` is keyed on
``(zobrist, doc_id, node_id, ply)`` and stored ``WITHOUT ROWID``, so a lookup is
a B-tree descent to a contiguous run of rows and the row *is* the leaf -- no
second probe to fetch it.  That is what makes the SPEC 11.3 gate (<= 50 ms over
a million positions) reachable on a laptop.

**This is not what the trunk does, and that is the point.**
``games_db.scan_by_positions`` inverts the search: it holds the wanted positions
in memory and streams the whole 18.9 GB base past them, which its own docstring
measures at about thirty minutes.  That design is *correct* for the question
"which game in this enormous third-party file matches", where building an index
would cost tens of gigabytes for a query asked once per acquisition.  It is the
wrong shape for "which of my books shows this", which is asked once per click.
The two coexist: this index covers the library the user owns and curates; the
scanner covers the giant file they downloaded.

**Collisions are surfaced, never resolved by luck.**  Every row carries the
exact 32-byte packed placement.  A lookup compares it, and when two placements
share a hash both come back -- the matching ones as
:attr:`PositionHit.exact`, the others flagged.  Returning only the first would
be a wrong answer indistinguishable from a right one, which is the failure mode
this whole design exists to avoid.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from caissa.index.zobrist import hash_placement, pack_placement, unpack_placement

__all__ = [
    "PositionHit",
    "PositionLookup",
    "PositionQuery",
]

TurnFilter = Literal["any", "white", "black"]


@dataclass(frozen=True, slots=True)
class PositionHit:
    """One indexed occurrence of a position.

    Attributes:
        doc_id: Which document.
        node_id: Which node inside it -- the caption, the game, the diagram.
        ply: Half-move at which the position occurred; ``0`` for a set-up
            position or a book diagram.
        turn: ``True`` when White is to move.
        exact: Whether the stored placement equals the one asked for.  ``False``
            means this row shares a Zobrist hash with the query and is a
            **different position**; it is returned so the caller can see the
            collision rather than being quietly given the wrong book.
        placement: The stored placement, so a collision can be shown.
    """

    doc_id: int
    node_id: int
    ply: int
    turn: bool
    exact: bool
    placement: str


@dataclass(frozen=True, slots=True)
class PositionQuery:
    """What to look up.

    Attributes:
        placement: FEN or bare piece placement.
        turn: Restrict to a side to move.  ``"any"`` by default, because a
            printed diagram usually does not say, and filtering on a guess would
            lose the hit the user is looking at.
        documents: Restrict to these ``doc_id``s.
        include_collisions: Return rows that share the hash but not the
            position.  On by default -- see the module docstring.
        limit: Maximum rows.
    """

    placement: str
    turn: TurnFilter = "any"
    documents: Sequence[int] = ()
    include_collisions: bool = True
    limit: int = 500


class PositionLookup:
    """Read-only view of the positional index."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def count(self) -> int:
        """How many positions are indexed."""
        row = self._connection.execute("SELECT count(*) FROM positions").fetchone()
        return int(row[0])

    def find(self, query: PositionQuery | str) -> list[PositionHit]:
        """Every indexed occurrence of a position.

        Args:
            query: A :class:`PositionQuery`, or a FEN/placement string with the
                defaults.

        Returns:
            Hits ordered document, node, ply.  Exact matches come first so that
            a caller that takes ``[0]`` still gets a correct answer, and a
            caller that inspects :attr:`PositionHit.exact` gets the whole truth.
        """
        if isinstance(query, str):
            query = PositionQuery(placement=query)

        key = hash_placement(query.placement)
        wanted = pack_placement(query.placement)

        sql = "SELECT doc_id, node_id, ply, turn, placement FROM positions WHERE zobrist = ?"
        params: list[object] = [key]
        if query.turn != "any":
            sql += " AND turn = ?"
            params.append(1 if query.turn == "white" else 0)
        if query.documents:
            marks = ",".join("?" * len(query.documents))
            sql += f" AND doc_id IN ({marks})"
            params.extend(query.documents)
        sql += " ORDER BY doc_id, node_id, ply LIMIT ?"
        params.append(query.limit)

        hits: list[PositionHit] = []
        for row in self._connection.execute(sql, params):
            stored = bytes(row[4])
            exact = stored == wanted
            if not exact and not query.include_collisions:
                continue
            hits.append(
                PositionHit(
                    doc_id=int(row[0]),
                    node_id=int(row[1]),
                    ply=int(row[2]),
                    turn=bool(row[3]),
                    exact=exact,
                    placement=unpack_placement(stored),
                )
            )
        hits.sort(key=lambda hit: (not hit.exact, hit.doc_id, hit.node_id, hit.ply))
        return hits

    def documents_containing(self, placement: str) -> list[int]:
        """The ``doc_id``s that contain a position, exact matches only.

        The literal form of SPEC 9's question.  Collisions are excluded here
        because the answer is a list of books to open, and opening the wrong one
        is the failure this filters out; :meth:`find` is where the collision is
        visible.
        """
        seen: list[int] = []
        for hit in self.find(PositionQuery(placement=placement, include_collisions=False)):
            if hit.doc_id not in seen:
                seen.append(hit.doc_id)
        return seen

    def any_of(self, placements: Iterable[str], *, limit: int = 500) -> list[PositionHit]:
        """Look several positions up in one pass.

        A book's worth of diagrams is hundreds of placements, and asking them
        one at a time pays the query overhead hundreds of times.
        """
        found: list[PositionHit] = []
        for placement in placements:
            found.extend(self.find(PositionQuery(placement=placement, limit=limit)))
            if len(found) >= limit:
                break
        return found[:limit]
