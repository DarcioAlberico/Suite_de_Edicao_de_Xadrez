"""The SQLite file: schema, connection policy, budget accounting.

One file per library (ADR-0007).  Three concerns live here so that the index
modules can be about searching rather than about SQLite.

**Connection policy.**  WAL, ``synchronous=NORMAL``, a large page cache and
memory temp store.  WAL is what lets a background indexer write while the UI
reads -- the consequence ADR-0007 flagged.  ``synchronous=NORMAL`` is safe under
WAL for everything except a machine losing power mid-commit, and an index is
rebuildable by definition, so paying full ``FULL`` fsync per batch would be
buying durability the data does not need at roughly four times the cost.

**Text that is not stored twice.**  A node either carries its own ``text`` or a
``(byte_start, byte_len)`` slice of its source file.  A 10 GB PGN has 20 million
games; storing their headers again would cost gigabytes to hold a copy of bytes
that are already on disk and are not going anywhere.  The FTS index needs the
tokens, not the text, so the text comes back by ``seek`` when a hit is shown.
That single decision is most of the difference between an index that fits the
15 % budget and one that does not.

**Contentless FTS5.**  ``content=''`` stores the postings and nothing else;
``contentless_delete=1`` (SQLite 3.43+) makes rows deletable, which is what
re-indexing one changed book requires.  Without it, incremental indexing would
mean rebuilding the whole table.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Final

from caissa.index.errors import IndexCorruptError, IndexMissingError, IndexStaleError
from caissa.index.tokenizer import FTS5_TOKENIZE, TOKENIZER_VERSION
from caissa.index.zobrist import ZOBRIST_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "connect",
    "database_bytes",
    "read_meta",
    "transaction",
    "write_meta",
]

#: Bumped on any change to the tables below.  Together with the tokenizer and
#: Zobrist versions this is the whole staleness contract.
SCHEMA_VERSION: Final = "1"

_META_KEYS: Final = {
    "schema_version": SCHEMA_VERSION,
    "tokenizer_version": TOKENIZER_VERSION,
    "zobrist_version": ZOBRIST_VERSION,
}

_DDL: Final = f"""
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One row per indexed source: a book, a PGN file, a Document IR.
CREATE TABLE IF NOT EXISTS documents (
    doc_id      INTEGER PRIMARY KEY,
    uri         TEXT    NOT NULL UNIQUE,
    title       TEXT    NOT NULL DEFAULT '',
    kind        TEXT    NOT NULL DEFAULT 'ir',
    stratum     TEXT    NOT NULL DEFAULT '',
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    -- Fingerprint of the source.  Equal fingerprint means "do not read again";
    -- it is the whole of incremental indexing.
    content_key TEXT    NOT NULL DEFAULT '',
    state       TEXT    NOT NULL DEFAULT 'pending',
    -- Where a partial pass stopped.  Resumability is a byte offset, not a flag.
    cursor      INTEGER NOT NULL DEFAULT 0,
    node_count  INTEGER NOT NULL DEFAULT 0,
    indexed_at  TEXT    NOT NULL DEFAULT '',
    error       TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS documents_state ON documents(state);

-- One row per indexable unit: a caption, a heading, a comment, a movetext, a
-- game header block.  This is the thing a hit points at.
CREATE TABLE IF NOT EXISTS nodes (
    node_id    INTEGER PRIMARY KEY,
    doc_id     INTEGER NOT NULL REFERENCES documents(doc_id),
    scope      TEXT    NOT NULL,
    node_ulid  TEXT    NOT NULL DEFAULT '',
    page       INTEGER NOT NULL DEFAULT -1,
    ordinal    INTEGER NOT NULL DEFAULT 0,
    byte_start INTEGER NOT NULL DEFAULT -1,
    byte_len   INTEGER NOT NULL DEFAULT 0,
    -- Empty when the text is recoverable from (byte_start, byte_len).
    text       TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS nodes_doc ON nodes(doc_id, ordinal);

-- Structured facets, kept out of nodes so the common row stays narrow.
CREATE TABLE IF NOT EXISTS facets (
    node_id INTEGER PRIMARY KEY REFERENCES nodes(node_id),
    doc_id  INTEGER NOT NULL,
    white   TEXT NOT NULL DEFAULT '',
    black   TEXT NOT NULL DEFAULT '',
    eco     TEXT NOT NULL DEFAULT '',
    year    INTEGER NOT NULL DEFAULT 0,
    result  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS facets_eco  ON facets(eco);
CREATE INDEX IF NOT EXISTS facets_year ON facets(year);

-- The positional index.  Key order is (zobrist, ...) because every lookup
-- starts from a hash; WITHOUT ROWID keeps the row inside the B-tree instead of
-- paying a second probe per hit.
CREATE TABLE IF NOT EXISTS positions (
    zobrist   INTEGER NOT NULL,
    doc_id    INTEGER NOT NULL,
    node_id   INTEGER NOT NULL DEFAULT -1,
    ply       INTEGER NOT NULL DEFAULT 0,
    turn      INTEGER NOT NULL DEFAULT 1,
    placement BLOB    NOT NULL,
    PRIMARY KEY (zobrist, doc_id, node_id, ply)
) WITHOUT ROWID;

-- Substitution history, so undo survives closing the application.
CREATE TABLE IF NOT EXISTS edit_journal (
    edit_id    INTEGER PRIMARY KEY,
    batch      TEXT    NOT NULL,
    doc_id     INTEGER NOT NULL,
    node_id    INTEGER NOT NULL,
    before     TEXT    NOT NULL,
    after      TEXT    NOT NULL,
    applied_at TEXT    NOT NULL DEFAULT '',
    undone     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS edit_journal_batch ON edit_journal(batch);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    tokens,
    content='',
    contentless_delete=1,
    tokenize="{FTS5_TOKENIZE}"
);
"""

_REQUIRED_TABLES: Final = frozenset(
    {"meta", "documents", "nodes", "facets", "positions", "edit_journal", "nodes_fts"}
)


def connect(
    path: Path | str, *, create: bool = True, read_only: bool = False
) -> sqlite3.Connection:
    """Open the index at ``path``, creating and validating it as asked.

    Args:
        path: The index file.  ``":memory:"`` is accepted and is what tests use.
        create: Create the file and the schema when absent.  ``False`` turns a
            missing index into :class:`IndexMissingError` instead of an empty one --
            which is what a search should do, since answering "no results" from
            an index that was never built is a lie.
        read_only: Refuse writes.  Several readers may share one index.

    Returns:
        A configured connection.  The caller closes it.

    Raises:
        IndexMissingError: ``create`` is false and the file is not there.
        IndexStaleError: Built by a different schema, tokenizer or hash table.
        IndexCorruptError: SQLite opened it but a required table is missing.
    """
    target = Path(path) if path != ":memory:" else None
    if target is not None:
        if not target.exists():
            if not create:
                msg = f"indice nao encontrado: {target}"
                raise IndexMissingError(msg)
            target.parent.mkdir(parents=True, exist_ok=True)
        elif target.stat().st_size == 0 and not create:
            msg = f"indice vazio: {target}"
            raise IndexMissingError(msg)

    uri = path == ":memory:"
    try:
        connection = sqlite3.connect(
            "file:memdb?mode=memory&cache=shared" if uri and read_only else str(path),
            uri=uri and read_only,
            timeout=30.0,
            isolation_level=None,
        )
    except sqlite3.Error as error:  # pragma: no cover - platform dependent
        msg = f"nao foi possivel abrir o indice {path}: {error}"
        raise IndexCorruptError(msg) from error

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA cache_size=-65536")  # 64 MiB, bounded and explicit
    connection.execute("PRAGMA foreign_keys=ON")

    if create and not read_only:
        try:
            connection.executescript(_DDL)
        except sqlite3.Error as error:
            connection.close()
            msg = f"nao foi possivel criar o esquema do indice: {error}"
            raise IndexCorruptError(msg) from error
        _ensure_meta(connection)
    else:
        try:
            _check(connection)
        except Exception:
            connection.close()
            raise
    return connection


def _check(connection: sqlite3.Connection) -> None:
    known = connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
    present = {row[0] for row in known}
    missing = _REQUIRED_TABLES - present
    if missing:
        msg = f"indice incompleto: faltam as tabelas {sorted(missing)}"
        raise IndexCorruptError(msg)
    _verify_meta(connection)


def _ensure_meta(connection: sqlite3.Connection) -> None:
    existing = read_meta(connection)
    if not existing:
        with transaction(connection):
            for key, value in _META_KEYS.items():
                connection.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value)
                )
        return
    _verify_meta(connection)


def _verify_meta(connection: sqlite3.Connection) -> None:
    stored = read_meta(connection)
    for key, expected in _META_KEYS.items():
        found = stored.get(key, "")
        if found != expected:
            raise IndexStaleError(f"{key}={found}", f"{key}={expected}")


def read_meta(connection: sqlite3.Connection) -> dict[str, str]:
    """Every ``meta`` row as a plain dict.  Empty when the table is empty."""
    try:
        with closing(connection.execute("SELECT key, value FROM meta")) as cursor:
            return {str(row[0]): str(row[1]) for row in cursor}
    except sqlite3.Error as error:
        msg = f"tabela meta ilegivel: {error}"
        raise IndexCorruptError(msg) from error


def write_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    """Set one ``meta`` key."""
    connection.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One explicit transaction.  Rolls back on any exception.

    ``isolation_level=None`` on the connection means Python's implicit
    transaction handling is off, so batching is visible in the code that does
    it rather than hidden in the driver -- which matters when a batch is a
    hundred thousand rows and a commit is the expensive part.
    """
    connection.execute("BEGIN")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    else:
        connection.execute("COMMIT")


def database_bytes(path: Path | str) -> int:
    """Bytes the index occupies on disk, WAL and shared-memory files included.

    The WAL is part of the footprint: a large batch can leave hundreds of
    megabytes there, and a budget check that ignored it would let the index
    overshoot exactly when it is growing fastest.
    """
    if path == ":memory:":
        return 0
    base = Path(path)
    total = 0
    for candidate in (base, base.with_name(base.name + "-wal"), base.with_name(base.name + "-shm")):
        try:
            total += candidate.stat().st_size
        except OSError:
            continue
    return total
