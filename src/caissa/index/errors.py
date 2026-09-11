"""Failure modes of the index, as types a caller can act on.

An index is a *cache of a corpus*, and every one of these errors describes a way
the cache and the corpus can disagree.  They are separate types because the
right response differs: a stale index is rebuilt, a corrupt one is deleted, a
missing one is created, and a full one waits for the user to raise the budget.
Collapsing them into one exception would force the UI to parse a message.
"""

from __future__ import annotations

__all__ = [
    "BudgetExceededError",
    "IndexBackendError",
    "IndexCorruptError",
    "IndexMissingError",
    "IndexStaleError",
    "QueryError",
]


class IndexBackendError(Exception):
    """Base of every index failure.

    Not named ``IndexError``: that is a builtin, and shadowing it inside a
    package that also does list arithmetic is the kind of cleverness that costs
    an afternoon.
    """


class IndexMissingError(IndexBackendError):
    """The index file does not exist and was not asked to be created."""


class IndexStaleError(IndexBackendError):
    """The index was built by an incompatible schema or hash table version.

    Carries both versions so the caller can tell the user what to rebuild.
    """

    def __init__(self, found: str, expected: str) -> None:
        super().__init__(
            f"indice desatualizado: gravado como {found!r}, esperado {expected!r}. "
            f"Reconstrua o indice."
        )
        self.found = found
        self.expected = expected


class IndexCorruptError(IndexBackendError):
    """SQLite refused the file, or a required table is absent."""


class BudgetExceededError(IndexBackendError):
    """Indexing stopped because the on-disk budget (SPEC R4) is spent.

    Not a crash: the index built so far is valid and queryable, and every
    document that was not reached keeps its ``pending`` state so that raising
    the budget resumes instead of restarting.
    """

    def __init__(self, used_bytes: int, budget_bytes: int) -> None:
        super().__init__(
            f"orcamento de disco do indice esgotado: "
            f"{used_bytes / 1024**3:.2f} GiB de {budget_bytes / 1024**3:.2f} GiB. "
            f"Aumente cache.index_budget_gb ou remova documentos do indice."
        )
        self.used_bytes = used_bytes
        self.budget_bytes = budget_bytes


class QueryError(IndexBackendError, ValueError):
    """A query that cannot be answered as written."""
