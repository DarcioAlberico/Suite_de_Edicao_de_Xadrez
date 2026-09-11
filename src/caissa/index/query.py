"""One entry point the UI calls, and everything a result needs to be acted on.

SPEC 9 lists six kinds of question -- text, regex, scope, move pattern,
material, position -- and the useful ones are *combinations*: "every position
with opposite-coloured bishops and at most six pawns, in a Portuguese book,
where the comment says 'zugzwang'".  A UI that had to call four search APIs and
intersect them itself would get the intersection wrong, so the intersection
happens here.

**Order of evaluation is cost order.**  Facets are a ``WHERE`` clause, so they
run first and cheapest.  The positional index is a B-tree descent, so it runs
next.  Full text is an FTS5 ``MATCH``, which is fast but touches more.  Regex
and the chess predicates run *last*, over candidate nodes only, because they
cannot use an index and their cost is proportional to what survives.  Reversing
this -- running a regex over the corpus and then filtering by year -- is the
difference between milliseconds and minutes.

**Every hit can be jumped to.**  A :class:`Hit` carries the document URI, the
page, the IR node id and the character offsets of the match inside the node's
text.  That is what "provenance enough to jump to the exact page and node"
means, and it is why a node's text is either stored or recoverable from its
byte range: a hit with no text is a hit the user cannot see.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import chess

from caissa.index.errors import QueryError
from caissa.index.position_index import PositionLookup, PositionQuery
from caissa.index.schema import connect
from caissa.index.tokenizer import DEFAULT_TOKENIZER, ChessTokenizer, decode_token
from caissa.index.zobrist import placement_from_fen
from caissa.notation.regex_engine import (
    Match,
    MaterialSignature,
    MoveQuery,
    PatternError,
    PositionPattern,
    RegexEngine,
    Scope,
    compile_move_pattern,
    compile_pattern,
)

__all__ = [
    "Hit",
    "Query",
    "ResultPage",
    "SearchIndex",
]

#: Ceiling on how many candidate nodes a regex or predicate stage will read.
#: Not a truncation of the *answer*: it is reported in
#: :attr:`ResultPage.truncated` so a UI can say "narrow the query" instead of
#: silently showing a slice of the corpus as if it were all of it.
_CANDIDATE_CAP: Final = 20_000


@dataclass(frozen=True, slots=True)
class Hit:
    """One result, with everything needed to show it and to open it."""

    doc_id: int
    uri: str
    title: str
    node_id: int
    node_ulid: str
    scope: Scope
    page: int
    text: str
    start: int
    end: int
    score: float
    snippet: str = ""
    groups: dict[str, str] = field(default_factory=dict)
    position_exact: bool | None = None
    """``True``/``False`` when the hit came from the positional index; ``False``
    means it shares a Zobrist hash but is a *different* position."""

    collisions: tuple[str, ...] = ()
    """Placements that share this hit's hash without being it."""


@dataclass(frozen=True, slots=True)
class ResultPage:
    """A page of hits plus the honest count behind them."""

    hits: tuple[Hit, ...]
    total: int
    offset: int
    limit: int
    elapsed_ms: float
    truncated: bool = False
    """More candidates existed than the engine was willing to read."""


@dataclass(frozen=True, slots=True)
class Query:
    """Everything a search can ask.  Every field is optional and they compose.

    Attributes:
        text: Words or notation.  Goes through the same tokenizer the index was
            built with, so ``O-O-O`` and ``♘f3`` work as typed.
        match: A raw FTS5 ``MATCH`` expression, for a caller that has already
            built one.  Mutually exclusive with :attr:`text`.
        regex: A PCRE pattern applied to candidate node text.
        scope: Restrict to captions, comments, moves, headers, variations or the
            main line.
        move: A move pattern (``"N*xd5"``) or a full
            :class:`~caissa.notation.regex_engine.MoveQuery`.
        position: A FEN or placement to look up in the positional index.
        position_pattern: A wildcard board pattern, checked against candidates.
        material: ``"KRPvKR"`` or a :class:`MaterialSignature`.
        eco: A regex anchored at the start of the ``ECO`` tag.
        player: Substring of either player's name, case-insensitive.
        year_min, year_max: Inclusive bounds on the game year.
        annotation: A printed judgement to require, e.g. ``"??"``.
        documents: Restrict to these URIs.
        stratum: Restrict to a ``CORPUS.md`` stratum.
        include_collisions: Return positional hits that share a hash without
            being the position.  Default ``True``: see
            :mod:`caissa.index.position_index`.
        limit, offset: Pagination.
    """

    text: str | None = None
    match: str | None = None
    regex: str | None = None
    scope: Scope = Scope.ALL
    move: MoveQuery | str | None = None
    position: str | None = None
    position_pattern: PositionPattern | None = None
    material: MaterialSignature | str | None = None
    eco: str | None = None
    player: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    annotation: str | None = None
    documents: Sequence[str] = ()
    stratum: str | None = None
    include_collisions: bool = True
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.text is not None and self.match is not None:
            msg = "informe 'text' ou 'match', nao os dois"
            raise QueryError(msg)
        if self.limit < 1:
            msg = f"limit deve ser >= 1 (recebido: {self.limit})"
            raise QueryError(msg)
        if self.offset < 0:
            msg = f"offset deve ser >= 0 (recebido: {self.offset})"
            raise QueryError(msg)


class SearchIndex:
    """The read side of the index.  Safe to share between reader threads.

    Args:
        path: The index file.  Must exist -- answering "no results" out of an
            index that was never built is a lie, so a missing file raises
            :class:`~caissa.index.errors.IndexMissingError` rather than returning
            nothing.
        tokenizer: Must be the one the index was built with; the schema records
            its version and refuses a mismatch.
    """

    def __init__(self, path: Path | str, *, tokenizer: ChessTokenizer = DEFAULT_TOKENIZER) -> None:
        self.path = path
        self.tokenizer = tokenizer
        self._connection = connect(path, create=False)
        self.positions = PositionLookup(self._connection)
        self._regex = RegexEngine()

    @classmethod
    def wrap(
        cls, connection: sqlite3.Connection, *, tokenizer: ChessTokenizer = DEFAULT_TOKENIZER
    ) -> SearchIndex:
        """Read through an already-open connection -- what a writer's own reads use."""
        instance = cls.__new__(cls)
        instance.path = ":memory:"
        instance.tokenizer = tokenizer
        instance._connection = connection
        instance.positions = PositionLookup(connection)
        instance._regex = RegexEngine()
        return instance

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection."""
        return self._connection

    def close(self) -> None:
        """Close the connection."""
        self._connection.close()

    def __enter__(self) -> SearchIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- the entry point -------------------------------------------------- #

    def search(self, query: Query | str) -> ResultPage:
        """Answer ``query``.

        Args:
            query: A :class:`Query`, or a plain string treated as
                ``Query(text=...)``.

        Returns:
            A :class:`ResultPage`.  ``total`` counts every candidate that
            survived every filter, so a UI can page through them; ``hits`` is
            the requested slice.
        """
        started = time.perf_counter()
        if isinstance(query, str):
            query = Query(text=query)

        candidates, truncated = self._candidates(query)
        rows = self._rows(candidates, query)
        rows = self._apply_predicates(rows, query)

        total = len(rows)
        window = rows[query.offset : query.offset + query.limit]
        hits = tuple(self._as_hit(row, query) for row in window)
        return ResultPage(
            hits=hits,
            total=total,
            offset=query.offset,
            limit=query.limit,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            truncated=truncated,
        )

    # -- stage 1: narrow ---------------------------------------------------- #

    def _candidates(self, query: Query) -> tuple[dict[int, _Candidate] | None, bool]:
        """Node ids surviving the indexed filters, or ``None`` for "everything".

        ``None`` rather than "every id" so that a query with no indexable
        criterion does not materialise the whole corpus just to intersect it
        with itself.
        """
        surviving: dict[int, _Candidate] | None = None
        truncated = False

        expression = query.match if query.match is not None else self._fts_expression(query)
        if expression:
            found, cut = self._fts(expression)
            truncated = truncated or cut
            surviving = _intersect(surviving, found)

        if query.position is not None:
            found = self._position_candidates(query)
            surviving = _intersect(surviving, found)

        return (surviving, truncated)

    def _fts_expression(self, query: Query) -> str:
        parts: list[str] = []
        if query.text:
            parts.append(self._user_text(query.text))
        if query.annotation:
            phrase = self.tokenizer.match_phrase(query.annotation)
            if phrase:
                parts.append(phrase)
        move_filter = self._move_prefilter(query.move)
        if move_filter:
            parts.append(move_filter)
        return " AND ".join(part for part in parts if part)

    def _user_text(self, text: str) -> str:
        """A user's query string as an FTS5 expression.

        Quoted runs stay phrases, the boolean words pass through, and everything
        else goes through the tokenizer so that ``O-O-O`` reaches the index in
        the same shape it was stored.
        """
        out: list[str] = []
        for piece in _split_query(text):
            if piece in ("AND", "OR", "NOT"):
                out.append(piece)
            elif piece.startswith('"') and piece.endswith('"') and len(piece) > 1:
                phrase = self.tokenizer.match_phrase(piece[1:-1])
                if phrase:
                    out.append(phrase)
            else:
                term = self.tokenizer.match_term(piece)
                if term:
                    out.append(term)
        joined: list[str] = []
        for index, piece in enumerate(out):
            if (
                index
                and piece not in ("AND", "OR", "NOT")
                and out[index - 1]
                not in (
                    "AND",
                    "OR",
                    "NOT",
                )
            ):
                joined.append("AND")
            joined.append(piece)
        return " ".join(joined)

    def _move_prefilter(self, move: MoveQuery | str | None) -> str:
        """An FTS prefix query derived from a move pattern's literal head.

        ``N*xd5`` cannot be an FTS expression -- FTS5 has prefix queries, not
        infix ones -- but its leading literal ``N`` can be, and narrowing to
        knight moves before running the pattern is most of the win.  A pattern
        with no literal head (or a raw ``re:``) contributes nothing here and is
        checked in the predicate stage instead.
        """
        spec = move.pattern if isinstance(move, MoveQuery) else move
        if not spec or spec.startswith("re:"):
            return ""
        head = ""
        for char in spec:
            if char in "*?":
                break
            head += char
        if not head:
            return ""
        if len(head) == len(spec):
            return self.tokenizer.match_term(spec)
        encoded = self.tokenizer.encode(head)
        if not encoded or " " in encoded:
            return ""
        return f'"{encoded}"*'

    def _fts(self, expression: str) -> tuple[dict[int, _Candidate], bool]:
        try:
            cursor = self._connection.execute(
                "SELECT rowid, bm25(nodes_fts) FROM nodes_fts WHERE nodes_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (expression, _CANDIDATE_CAP + 1),
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError as error:
            msg = f"consulta de texto invalida: {error}"
            raise QueryError(msg) from error
        truncated = len(rows) > _CANDIDATE_CAP
        return (
            {int(row[0]): _Candidate(score=-float(row[1])) for row in rows[:_CANDIDATE_CAP]},
            truncated,
        )

    def _position_candidates(self, query: Query) -> dict[int, _Candidate]:
        assert query.position is not None  # noqa: S101 - guarded by the caller
        hits = self.positions.find(
            PositionQuery(
                placement=query.position,
                include_collisions=query.include_collisions,
                limit=_CANDIDATE_CAP,
            )
        )
        found: dict[int, _Candidate] = {}
        for hit in hits:
            existing = found.get(hit.node_id)
            collisions = () if hit.exact else (hit.placement,)
            if existing is None:
                found[hit.node_id] = _Candidate(
                    score=1.0 if hit.exact else 0.0,
                    position_exact=hit.exact,
                    collisions=collisions,
                )
            elif hit.exact:
                found[hit.node_id] = _Candidate(
                    score=1.0, position_exact=True, collisions=existing.collisions
                )
            else:
                found[hit.node_id] = _Candidate(
                    score=existing.score,
                    position_exact=existing.position_exact,
                    collisions=existing.collisions + collisions,
                )
        return found

    # -- stage 2: fetch ----------------------------------------------------- #

    def _rows(self, candidates: dict[int, _Candidate] | None, query: Query) -> list[_Row]:
        sql = [
            "SELECT n.node_id, n.doc_id, n.scope, n.node_ulid, n.page, n.byte_start, "
            "n.byte_len, n.text, d.uri, d.title, d.kind "
            "FROM nodes n JOIN documents d ON d.doc_id = n.doc_id "
            "LEFT JOIN facets f ON f.node_id = n.node_id WHERE 1=1"
        ]
        params: list[object] = []

        if candidates is not None:
            if not candidates:
                return []
            ids = list(candidates)
            sql.append(f" AND n.node_id IN ({','.join('?' * len(ids))})")
            params.extend(ids)

        if query.scope is not Scope.ALL:
            sql.append(" AND n.scope = ?")
            params.append(str(query.scope))
        if query.documents:
            sql.append(f" AND d.uri IN ({','.join('?' * len(query.documents))})")
            params.extend(query.documents)
        if query.stratum:
            sql.append(" AND d.stratum = ?")
            params.append(query.stratum)
        if query.eco:
            sql.append(" AND f.eco IS NOT NULL AND f.eco != ''")
        if query.player:
            sql.append(" AND (f.white LIKE ? OR f.black LIKE ?)")
            like = f"%{query.player}%"
            params.extend((like, like))
        if query.year_min is not None:
            sql.append(" AND f.year >= ?")
            params.append(query.year_min)
        if query.year_max is not None:
            sql.append(" AND f.year <= ? AND f.year > 0")
            params.append(query.year_max)

        sql.append(" ORDER BY n.doc_id, n.ordinal LIMIT ?")
        params.append(_CANDIDATE_CAP)

        rows: list[_Row] = []
        for raw in self._connection.execute("".join(sql), params):
            node_id = int(raw[0])
            candidate = candidates[node_id] if candidates is not None else _Candidate(score=0.0)
            rows.append(
                _Row(
                    node_id=node_id,
                    doc_id=int(raw[1]),
                    scope=Scope(raw[2]),
                    node_ulid=str(raw[3]),
                    page=int(raw[4]),
                    byte_start=int(raw[5]),
                    byte_len=int(raw[6]),
                    stored_text=str(raw[7]),
                    uri=str(raw[8]),
                    title=str(raw[9]),
                    kind=str(raw[10]),
                    candidate=candidate,
                )
            )
        if query.eco:
            rows = [row for row in rows if self._eco_matches(row.node_id, query.eco)]
        return rows

    def _eco_matches(self, node_id: int, pattern: str) -> bool:
        row = self._connection.execute(
            "SELECT eco FROM facets WHERE node_id = ?", (node_id,)
        ).fetchone()
        if row is None or not row[0]:
            return False
        return compile_pattern(f"^(?:{pattern})").fullmatch(str(row[0])) is not None or bool(
            next(compile_pattern(f"^(?:{pattern})").finditer(str(row[0])), None)
        )

    # -- stage 3: predicates that no index can answer ------------------------ #

    def _apply_predicates(self, rows: list[_Row], query: Query) -> list[_Row]:
        if query.regex is not None:
            rows = self._filter_regex(rows, query)
        if query.move is not None:
            rows = self._filter_move(rows, query)
        if query.material is not None or query.position_pattern is not None:
            rows = self._filter_board(rows, query)
        return rows

    def _filter_regex(self, rows: list[_Row], query: Query) -> list[_Row]:
        assert query.regex is not None  # noqa: S101 - guarded by the caller
        kept: list[_Row] = []
        for row in rows:
            text = self.text_of(row.node_id, row)
            matches = self._regex.search(query.regex, text, scope=Scope.ALL, limit=1)
            if matches:
                kept.append(row.with_match(matches[0], text))
        return kept

    def _filter_move(self, rows: list[_Row], query: Query) -> list[_Row]:
        spec = query.move
        move_query = MoveQuery(pattern=spec) if isinstance(spec, str) else spec
        assert move_query is not None  # noqa: S101 - guarded by the caller
        if move_query.pattern is None:
            return rows
        try:
            pattern = compile_move_pattern(move_query.pattern)
        except PatternError:
            raise
        kept: list[_Row] = []
        for row in rows:
            text = self.text_of(row.node_id, row)
            hit = _first_move_match(text, pattern, self.tokenizer)
            if hit is not None:
                start, end, san = hit
                kept.append(
                    row.with_match(Match(start=start, end=end, text=san, scope=row.scope), text)
                )
        return kept

    def _filter_board(self, rows: list[_Row], query: Query) -> list[_Row]:
        material = query.material
        if isinstance(material, str):
            material = MaterialSignature.parse(material)
        kept: list[_Row] = []
        for row in rows:
            placements = self._placements_of(row.node_id)
            if not placements:
                continue
            for placement in placements:
                fen = f"{placement} w - - 0 1"
                if material is not None and not material.matches(fen):
                    continue
                if query.position_pattern is not None and not query.position_pattern.matches(fen):
                    continue
                kept.append(row)
                break
        return kept

    def _placements_of(self, node_id: int) -> list[str]:
        from caissa.index.zobrist import unpack_placement

        return [
            unpack_placement(bytes(row[0]))
            for row in self._connection.execute(
                "SELECT placement FROM positions WHERE node_id = ? LIMIT 4096", (node_id,)
            )
        ]

    # -- text recovery ------------------------------------------------------ #

    def text_of(self, node_id: int, row: _Row | None = None) -> str:
        """The node's text, stored or read back from its source file.

        A PGN node stores no text -- the bytes are already on disk and copying
        twenty million games into the index is what breaks the 15 % gate -- so
        this seeks and reads.  Callers never need to know which kind they have.
        """
        if row is None:
            raw = self._connection.execute(
                "SELECT n.node_id, n.doc_id, n.scope, n.node_ulid, n.page, n.byte_start, "
                "n.byte_len, n.text, d.uri, d.title, d.kind FROM nodes n "
                "JOIN documents d ON d.doc_id = n.doc_id WHERE n.node_id = ?",
                (node_id,),
            ).fetchone()
            if raw is None:
                return ""
            row = _Row(
                node_id=int(raw[0]),
                doc_id=int(raw[1]),
                scope=Scope(raw[2]),
                node_ulid=str(raw[3]),
                page=int(raw[4]),
                byte_start=int(raw[5]),
                byte_len=int(raw[6]),
                stored_text=str(raw[7]),
                uri=str(raw[8]),
                title=str(raw[9]),
                kind=str(raw[10]),
                candidate=_Candidate(score=0.0),
            )
        if row.stored_text:
            return row.stored_text
        if row.byte_start < 0 or row.byte_len <= 0:
            return ""
        try:
            with Path(row.uri).open("rb") as handle:
                handle.seek(row.byte_start)
                return handle.read(row.byte_len).decode("utf-8", "replace")
        except OSError:
            # The source moved or was deleted.  An empty string is honest; the
            # index still knows the hit exists and where it claimed to be.
            return ""

    def _as_hit(self, row: _Row, query: Query) -> Hit:
        text = row.match_text if row.match_text is not None else self.text_of(row.node_id, row)
        match = row.match
        start = match.start if match is not None else 0
        end = match.end if match is not None else 0
        if match is None and query.text:
            start, end = _locate(text, query.text, self.tokenizer)
        return Hit(
            doc_id=row.doc_id,
            uri=row.uri,
            title=row.title,
            node_id=row.node_id,
            node_ulid=row.node_ulid,
            scope=row.scope,
            page=row.page,
            text=text,
            start=start,
            end=end,
            score=row.candidate.score,
            snippet=_snippet(text, start, end),
            groups=dict(match.groups) if match is not None else {},
            position_exact=row.candidate.position_exact,
            collisions=row.candidate.collisions,
        )


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Candidate:
    score: float
    position_exact: bool | None = None
    collisions: tuple[str, ...] = ()


@dataclass(slots=True)
class _Row:
    node_id: int
    doc_id: int
    scope: Scope
    node_ulid: str
    page: int
    byte_start: int
    byte_len: int
    stored_text: str
    uri: str
    title: str
    kind: str
    candidate: _Candidate
    match: Match | None = None
    match_text: str | None = None

    def with_match(self, match: Match, text: str) -> _Row:
        self.match = match
        self.match_text = text
        return self


def _intersect(
    left: dict[int, _Candidate] | None, right: dict[int, _Candidate]
) -> dict[int, _Candidate]:
    if left is None:
        return right
    merged: dict[int, _Candidate] = {}
    for node_id, candidate in right.items():
        other = left.get(node_id)
        if other is None:
            continue
        merged[node_id] = _Candidate(
            score=candidate.score + other.score,
            position_exact=(
                candidate.position_exact
                if candidate.position_exact is not None
                else other.position_exact
            ),
            collisions=candidate.collisions or other.collisions,
        )
    return merged


def _split_query(text: str) -> list[str]:
    """Split a user query into quoted phrases, boolean words and bare terms."""
    pieces: list[str] = []
    buffer: list[str] = []
    quoted = False
    for char in text:
        if char == '"':
            if quoted:
                pieces.append('"' + "".join(buffer) + '"')
                buffer = []
                quoted = False
            else:
                if buffer:
                    pieces.append("".join(buffer))
                    buffer = []
                quoted = True
            continue
        if char.isspace() and not quoted:
            if buffer:
                pieces.append("".join(buffer))
                buffer = []
            continue
        buffer.append(char)
    if buffer:
        pieces.append(('"' + "".join(buffer) + '"') if quoted else "".join(buffer))
    return pieces


def _first_move_match(
    text: str, pattern: object, tokenizer: ChessTokenizer | None = None
) -> tuple[int, int, str] | None:
    """Find the first whitespace-delimited chunk in ``text`` that is a matching move.

    The chunk is reduced to canonical SAN by
    :meth:`~caissa.index.tokenizer.ChessTokenizer.san_of` before the pattern is
    applied, so ``"3.Nxd5"``, ``"Nxd5!?"``, ``"(Nxd5)"`` and ``"N:d5"`` are all
    the move ``Nxd5``.

    An earlier version compared the raw chunk against the pattern, on the
    assumption -- true for :class:`~caissa.index.sources.IrSource`, which stores
    a main line as canonical SAN separated by spaces -- that the node's text is
    already canonical.  It is not true for :class:`~caissa.index.sources.TextSource`:
    in a real book the move is glued to its move number.  ``compile_move_pattern``
    anchors its regex, so ``^N.*xd5$`` never matched ``3.Nxd5``, and the search
    silently lost exactly the moves that open a variation.  ``san_of`` exists to
    stop the indexer and the search from drifting apart on "is this chunk a
    move"; using it here is the whole point of it being public.
    """
    full_match = getattr(pattern, "fullmatch", None)
    if full_match is None:  # pragma: no cover - defensive
        return None
    tokenizer = tokenizer if tokenizer is not None else ChessTokenizer()
    position = 0
    for chunk in text.split(" "):
        if chunk:
            san = tokenizer.san_of(chunk)
            if san is not None and full_match(san) is not None:
                # Report the offsets of the printed chunk, not of the canonical
                # form: the caller highlights the source text.
                return (position, position + len(chunk), san)
        position += len(chunk) + 1
    return None


def _locate(text: str, needle: str, tokenizer: ChessTokenizer) -> tuple[int, int]:
    """Best-effort character offsets of a text query inside a node's text.

    FTS5 knows *which* node matched, not where.  Rather than store per-token
    offsets -- which would roughly double the index -- the offset is recovered
    here, on the handful of rows actually being displayed.
    """
    tokens = tokenizer.tokens(needle)
    if not tokens:
        return (0, 0)
    surface = decode_token(tokens[0])
    index = text.find(surface)
    if index < 0:
        index = text.lower().find(surface.lower())
    if index < 0:
        return (0, 0)
    return (index, index + len(surface))


def _snippet(text: str, start: int, end: int, width: int = 60) -> str:
    left = max(0, start - width)
    right = min(len(text), max(end, start) + width)
    return " ".join(text[left:right].split())


def _board_of(placement: str) -> chess.Board:  # pragma: no cover - helper
    return chess.Board(f"{placement_from_fen(placement)} w - - 0 1")
