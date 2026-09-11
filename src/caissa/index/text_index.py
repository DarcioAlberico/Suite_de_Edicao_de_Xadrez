"""Full-text indexing: incremental, resumable, and inside a disk budget.

Three properties matter more than raw speed here, because all three are things
a user notices and a benchmark does not.

**Incremental.**  Adding one book to a library of 1,200 must read one book.
:meth:`TextIndex.add` compares ``documents.content_key`` -- size and mtime --
and returns without opening the file when it matches.  The test for this asserts
on the source's ``read_calls``, not on wall time, because "it was fast" is not
the same claim as "it did not read".

**Resumable.**  A pass over a 10 GB PGN that is cancelled at 80 % stores its
cursor and continues from there.  The cursor is committed with the batch it
belongs to, so a crash between batches loses at most one batch and never leaves
the index claiming a document is complete when it is not.

**Budgeted.**  SPEC R4 gives the index a ceiling and
``caissa.core.config.CacheConfig.index_budget_gb`` holds it.  Running out is a
state, not an exception: the documents already indexed stay valid and queryable,
the current one is marked ``partial`` with its cursor, and raising the budget
resumes.  An index that deleted itself when full, or that filled the disk,
would both be worse than one that stops.

The batching is deliberate and measured.  Rows are accumulated and written with
``executemany`` inside one transaction; ``node_id`` values are allocated by the
writer rather than read back from ``lastrowid``, because a per-row round trip is
the difference between an hour and four minutes on a ten-gigabyte file.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from caissa.core.config import CaissaConfig, get_config
from caissa.index.errors import BudgetExceededError
from caissa.index.schema import connect, database_bytes, transaction
from caissa.index.sources import IndexUnit, Source
from caissa.index.tokenizer import DEFAULT_TOKENIZER, ChessTokenizer
from caissa.index.zobrist import hash_placement, pack_placement

__all__ = [
    "DocumentRow",
    "IndexReport",
    "IndexStats",
    "TextIndex",
    "index_all",
    "open_index",
]

#: Units per write batch.  Chosen by measurement, not by feel: below ~5k the
#: commit dominates, above ~100k the pending rows start to show up in RSS.
_BATCH: Final = 20_000



@dataclass(frozen=True, slots=True)
class DocumentRow:
    """A document as the index knows it."""

    doc_id: int
    uri: str
    title: str
    kind: str
    stratum: str
    size_bytes: int
    content_key: str
    state: str
    cursor: int
    node_count: int
    indexed_at: str
    error: str


@dataclass(frozen=True, slots=True)
class IndexReport:
    """What one :meth:`TextIndex.add` did.  Every number is counted, not estimated."""

    uri: str
    doc_id: int
    units: int
    positions: int
    bytes_read: int
    seconds: float
    skipped: bool = False
    """The content key matched and nothing was read."""

    resumed_from: int = 0
    stopped_for_budget: bool = False
    cancelled: bool = False

    @property
    def throughput_mb_s(self) -> float:
        """Source megabytes per second, or ``0.0`` for a skipped document."""
        if self.seconds <= 0 or not self.bytes_read:
            return 0.0
        return self.bytes_read / 1e6 / self.seconds


@dataclass(frozen=True, slots=True)
class IndexStats:
    """Size accounting -- the numbers the 15 % gate is measured with."""

    documents: int
    nodes: int
    positions: int
    index_bytes: int
    corpus_bytes: int

    @property
    def ratio(self) -> float:
        """Index size as a fraction of the indexed corpus."""
        return self.index_bytes / self.corpus_bytes if self.corpus_bytes else 0.0


class TextIndex:
    """The writable face of the index.

    Args:
        path: The index file, or ``":memory:"``.
        tokenizer: Overridden only by tests that want the folding off.
        config: Configuration to read the disk budget from.  Defaults to the
            process configuration, so the budget is the user's, not this
            module's invention (SPEC R4).
    """

    def __init__(
        self,
        path: Path | str,
        *,
        tokenizer: ChessTokenizer = DEFAULT_TOKENIZER,
        config: CaissaConfig | None = None,
    ) -> None:
        self.path = path
        self.tokenizer = tokenizer
        self._config = config
        self._connection = connect(path, create=True)
        self._lock = threading.Lock()

    # -- lifecycle -------------------------------------------------------- #

    @property
    def connection(self) -> sqlite3.Connection:
        """The live connection, for readers built on top of this index."""
        return self._connection

    def close(self) -> None:
        """Close the connection.  Safe to call twice."""
        with contextlib.suppress(sqlite3.Error):
            self._connection.close()

    def __enter__(self) -> TextIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def budget_bytes(self) -> int:
        """The configured ceiling for this index file, in bytes."""
        config = self._config or get_config()
        return int(config.cache.index_budget_gb * 1024**3)

    # -- reading the catalogue -------------------------------------------- #

    def documents(self) -> list[DocumentRow]:
        """Every document in the index, in insertion order."""
        rows = self._connection.execute(
            "SELECT doc_id, uri, title, kind, stratum, size_bytes, content_key, state, "
            "cursor, node_count, indexed_at, error FROM documents ORDER BY doc_id"
        ).fetchall()
        return [DocumentRow(*tuple(row)) for row in rows]

    def document(self, uri: str) -> DocumentRow | None:
        """One document by URI, or ``None``."""
        row = self._connection.execute(
            "SELECT doc_id, uri, title, kind, stratum, size_bytes, content_key, state, "
            "cursor, node_count, indexed_at, error FROM documents WHERE uri = ?",
            (uri,),
        ).fetchone()
        return DocumentRow(*tuple(row)) if row is not None else None

    def needs_reindex(self, source: Source) -> bool:
        """Would :meth:`add` read this source?

        Answered without opening the file, which is the point.
        """
        row = self.document(source.uri)
        if row is None:
            return True
        return row.state != "complete" or row.content_key != source.content_key

    def stats(self) -> IndexStats:
        """Count rows and measure the file.  Used by the report and the gate."""
        cursor = self._connection.execute(
            "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM nodes), "
            "(SELECT count(*) FROM positions), "
            "(SELECT coalesce(sum(size_bytes), 0) FROM documents)"
        ).fetchone()
        return IndexStats(
            documents=int(cursor[0]),
            nodes=int(cursor[1]),
            positions=int(cursor[2]),
            index_bytes=database_bytes(self.path),
            corpus_bytes=int(cursor[3]),
        )

    # -- writing ---------------------------------------------------------- #

    def add(
        self,
        source: Source,
        *,
        force: bool = False,
        stratum: str = "",
        on_progress: Callable[[int, int], None] | None = None,
        cancel: threading.Event | None = None,
        budget_bytes: int | None = None,
        batch_size: int | None = None,
    ) -> IndexReport:
        """Index ``source``, resuming or skipping as its fingerprint dictates.

        Args:
            source: What to index.
            force: Re-read even when the fingerprint matches.  For a rebuild
                after a tokenizer change, which is otherwise invisible.
            stratum: The ``CORPUS.md`` stratum, recorded so a measurement can
                say which one it came from.
            on_progress: Called with ``(units, bytes_read)`` after each batch.
            cancel: Checked between batches.  A cancelled pass keeps what it
                wrote and stores its cursor; it does not roll back, because a
                user who cancels a four-minute pass at 90 % wants the 90 %.
            budget_bytes: Override the configured ceiling.  Tests set it low.
            batch_size: Units per write batch.  The default is measured; a
                caller lowers it only to make the budget and cancel checks fire
                sooner, which is what the tests need.

        Returns:
            An :class:`IndexReport`.  Nothing is estimated in it.

        Raises:
            BudgetExceededError: Only when the budget is already spent *before* any
                work happens.  Running out mid-pass is reported in the result
                instead, because partial progress is worth keeping.
        """
        started = time.perf_counter()
        with self._lock:
            existing = self.document(source.uri)
            if (
                not force
                and existing is not None
                and existing.state == "complete"
                and existing.content_key == source.content_key
            ):
                return IndexReport(
                    uri=source.uri,
                    doc_id=existing.doc_id,
                    units=0,
                    positions=0,
                    bytes_read=0,
                    seconds=time.perf_counter() - started,
                    skipped=True,
                )

            resume = 0
            if existing is not None:
                changed = existing.content_key != source.content_key
                if force or changed:
                    self._purge(existing.doc_id)
                elif existing.state == "partial":
                    resume = existing.cursor
                else:
                    self._purge(existing.doc_id)

            doc_id = self._upsert_document(source, stratum=stratum, resume=resume)
            ceiling = self.budget_bytes if budget_bytes is None else budget_bytes
            used = database_bytes(self.path)
            if used >= ceiling:
                self._set_state(doc_id, "partial", cursor=resume, error="orcamento esgotado")
                raise BudgetExceededError(used, ceiling)

            return self._run(
                source,
                doc_id=doc_id,
                resume=resume,
                started=started,
                ceiling=ceiling,
                on_progress=on_progress,
                cancel=cancel,
                batch_size=batch_size or _BATCH,
            )

    def mark_failed(self, uri: str, error: str) -> None:
        """Record that a source could not be read.

        A failure is a state on the document, not a missing row: a library that
        silently forgot the book it could not open would offer no way to find
        out why it is not in the results.
        """
        with self._lock, transaction(self._connection):
            self._connection.execute(
                "UPDATE documents SET state = 'failed', error = ? WHERE uri = ?", (error, uri)
            )

    def remove(self, uri: str) -> bool:
        """Drop a document and everything that points at it.  ``False`` if absent."""
        with self._lock:
            row = self.document(uri)
            if row is None:
                return False
            self._purge(row.doc_id)
            with transaction(self._connection):
                self._connection.execute("DELETE FROM documents WHERE doc_id = ?", (row.doc_id,))
            return True

    # -- the pass --------------------------------------------------------- #

    def _run(
        self,
        source: Source,
        *,
        doc_id: int,
        resume: int,
        started: float,
        ceiling: int,
        on_progress: Callable[[int, int], None] | None,
        cancel: threading.Event | None,
        batch_size: int = _BATCH,
    ) -> IndexReport:
        batch = _Batch(self._next_node_id())
        units = 0
        positions = 0
        bytes_read = 0
        ordinal = resume
        cursor = resume
        batches = 0
        stopped_for_budget = False
        cancelled = False

        for unit in source.units(start=resume):
            batch.append(doc_id, unit, ordinal, self.tokenizer)
            units += 1
            positions += len(unit.positions)
            ordinal += 1
            bytes_read += unit.byte_len or len(unit.text.encode("utf-8"))
            cursor = unit.cursor if unit.cursor >= 0 else ordinal

            if len(batch) < batch_size:
                continue

            self._flush(batch, doc_id, cursor)
            batches += 1
            batch = _Batch(self._next_node_id())
            if on_progress is not None:
                on_progress(units, bytes_read)
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            # Checked every batch, not every few: a batch is tens of thousands
            # of rows, and sampling less often means the overshoot is unbounded
            # exactly when the disk is tightest.  Three ``stat`` calls cost
            # nothing next to the commit that just happened.
            if database_bytes(self.path) >= ceiling:
                stopped_for_budget = True
                break

        # Whatever the reason for stopping, the rows already built are written:
        # a cancelled pass keeps its work, and a budget stop keeps what fitted.
        self._flush(batch, doc_id, cursor)

        state = "partial" if (cancelled or stopped_for_budget) else "complete"
        error = "orcamento esgotado" if stopped_for_budget else ""
        self._finish(doc_id, state=state, cursor=cursor, error=error)
        if on_progress is not None:
            on_progress(units, bytes_read)

        return IndexReport(
            uri=source.uri,
            doc_id=doc_id,
            units=units,
            positions=positions,
            bytes_read=bytes_read,
            seconds=time.perf_counter() - started,
            resumed_from=resume,
            stopped_for_budget=stopped_for_budget,
            cancelled=cancelled,
        )

    def _flush(self, batch: _Batch, doc_id: int, cursor: int) -> None:
        if not len(batch):
            return
        with transaction(self._connection):
            self._connection.executemany(
                "INSERT INTO nodes(node_id, doc_id, scope, node_ulid, page, ordinal, "
                "byte_start, byte_len, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch.nodes,
            )
            self._connection.executemany(
                "INSERT INTO nodes_fts(rowid, tokens) VALUES (?, ?)", batch.fts
            )
            if batch.facets:
                self._connection.executemany(
                    "INSERT INTO facets(node_id, doc_id, white, black, eco, year, result) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    batch.facets,
                )
            if batch.positions:
                self._connection.executemany(
                    "INSERT OR IGNORE INTO positions(zobrist, doc_id, node_id, ply, turn, "
                    "placement) VALUES (?, ?, ?, ?, ?, ?)",
                    batch.positions,
                )
            self._connection.execute(
                "UPDATE documents SET cursor = ?, node_count = node_count + ?, state = 'partial' "
                "WHERE doc_id = ?",
                (cursor, len(batch), doc_id),
            )

    # -- catalogue bookkeeping -------------------------------------------- #

    def _next_node_id(self) -> int:
        row = self._connection.execute("SELECT coalesce(max(node_id), 0) FROM nodes").fetchone()
        return int(row[0]) + 1

    def _upsert_document(self, source: Source, *, stratum: str, resume: int) -> int:
        with transaction(self._connection):
            self._connection.execute(
                "INSERT INTO documents(uri, title, kind, stratum, size_bytes, content_key, "
                "state, cursor, node_count) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, 0) "
                "ON CONFLICT(uri) DO UPDATE SET title = excluded.title, kind = excluded.kind, "
                "stratum = excluded.stratum, size_bytes = excluded.size_bytes, "
                "content_key = excluded.content_key, state = 'pending', error = ''",
                (
                    source.uri,
                    source.title,
                    source.kind,
                    stratum,
                    source.size_bytes,
                    source.content_key,
                    resume,
                ),
            )
        row = self._connection.execute(
            "SELECT doc_id FROM documents WHERE uri = ?", (source.uri,)
        ).fetchone()
        return int(row[0])

    def _purge(self, doc_id: int) -> None:
        """Remove every row a document owns, FTS postings included."""
        with transaction(self._connection):
            self._connection.execute(
                "DELETE FROM nodes_fts WHERE rowid IN (SELECT node_id FROM nodes WHERE doc_id = ?)",
                (doc_id,),
            )
            self._connection.execute("DELETE FROM facets WHERE doc_id = ?", (doc_id,))
            self._connection.execute("DELETE FROM positions WHERE doc_id = ?", (doc_id,))
            self._connection.execute("DELETE FROM nodes WHERE doc_id = ?", (doc_id,))
            self._connection.execute(
                "UPDATE documents SET node_count = 0, cursor = 0 WHERE doc_id = ?", (doc_id,)
            )

    def _set_state(self, doc_id: int, state: str, *, cursor: int, error: str = "") -> None:
        with transaction(self._connection):
            self._connection.execute(
                "UPDATE documents SET state = ?, cursor = ?, error = ? WHERE doc_id = ?",
                (state, cursor, error, doc_id),
            )

    def _finish(self, doc_id: int, *, state: str, cursor: int, error: str) -> None:
        """Close a pass.

        ``node_count`` is recounted rather than taken from the pass, because a
        resumed pass only knows about its own half and writing that number would
        make a resumed document report fewer nodes than it holds.
        """
        with transaction(self._connection):
            self._connection.execute(
                "UPDATE documents SET state = ?, cursor = ?, error = ?, indexed_at = ?, "
                "node_count = (SELECT count(*) FROM nodes WHERE doc_id = ?) WHERE doc_id = ?",
                (
                    state,
                    cursor,
                    error,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    doc_id,
                    doc_id,
                ),
            )


@dataclass(slots=True)
class _Batch:
    """Rows waiting to be written, with node ids already allocated.

    Allocating ids here rather than reading ``lastrowid`` per insert is what
    lets the whole batch go out in four ``executemany`` calls.
    """

    next_id: int
    nodes: list[tuple[int, int, str, str, int, int, int, int, str]] = field(default_factory=list)
    fts: list[tuple[int, str]] = field(default_factory=list)
    facets: list[tuple[int, int, str, str, str, int, str]] = field(default_factory=list)
    positions: list[tuple[int, int, int, int, int, bytes]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.nodes)

    def append(self, doc_id: int, unit: IndexUnit, ordinal: int, tokenizer: ChessTokenizer) -> None:
        node_id = self.next_id
        self.next_id += 1
        self.nodes.append(
            (
                node_id,
                doc_id,
                str(unit.scope),
                unit.node_ulid,
                unit.page,
                ordinal,
                unit.byte_start,
                unit.byte_len,
                unit.text if unit.store_text else "",
            )
        )
        self.fts.append((node_id, tokenizer.encode(unit.text)))
        if unit.facets is not None:
            facets = unit.facets
            self.facets.append(
                (
                    node_id,
                    doc_id,
                    facets.white,
                    facets.black,
                    facets.eco,
                    facets.year,
                    facets.result,
                )
            )
        for position in unit.positions:
            try:
                key = hash_placement(position.placement)
                packed = pack_placement(position.placement)
            except ValueError:
                # A placement the reader could not make sense of. Skipping it is
                # right: an index entry for a position nobody can reproduce is
                # worse than a missing one.
                continue
            self.positions.append((key, doc_id, node_id, position.ply, int(position.turn), packed))


def open_index(path: Path | str, *, tokenizer: ChessTokenizer = DEFAULT_TOKENIZER) -> TextIndex:
    """Convenience constructor, so callers do not import the class to open a file."""
    return TextIndex(path, tokenizer=tokenizer)


def index_all(
    index: TextIndex,
    sources: Iterable[Source],
    *,
    stratum: str = "",
    cancel: threading.Event | None = None,
    budget_bytes: int | None = None,
) -> list[IndexReport]:
    """Index a sequence of sources, stopping cleanly when the budget runs out.

    Stopping is not failing: every source already indexed stays queryable and
    the one that ran out keeps its cursor, so raising the budget resumes rather
    than restarts.
    """
    reports: list[IndexReport] = []
    for source in sources:
        try:
            report = index.add(
                source, stratum=stratum, cancel=cancel, budget_bytes=budget_bytes
            )
        except BudgetExceededError:
            break
        reports.append(report)
        if report.stopped_for_budget or report.cancelled:
            break
    return reports
