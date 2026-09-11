"""Background indexing: a worker thread, a budget, and a cancel that means it.

SPEC 9 asks for "indexação incremental, em segundo plano, com orçamento de disco
configurável", and SPEC 10.5 says nothing blocks.  Both are the same
requirement: the user adds forty books, keeps reading, and the library fills in
behind them.

**One writer.**  ADR-0007 flagged concurrent writes as the cost of SQLite, and
WAL solves readers-during-writes but not two writers.  So there is exactly one
indexing thread per index, and :class:`BackgroundIndexer` owns it.  Readers open
their own connections and are never blocked by it.

**Cancel is checked between batches, not between documents.**  A 10 GB PGN is
one document; a cancel that waited for it would take four minutes to be
noticed.  The work already committed is kept and the cursor is stored, so
cancelling and restarting costs nothing but the current batch.

**Progress is real.**  SPEC 10.5 forbids indeterminate progress bars.  The
queue knows the total bytes it was given and reports bytes done, so the caller
has a fraction rather than a spinner.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from caissa.index.errors import BudgetExceededError
from caissa.index.schema import database_bytes
from caissa.index.sources import Source
from caissa.index.text_index import IndexReport, TextIndex

__all__ = [
    "BackgroundIndexer",
    "Progress",
]


@dataclass(frozen=True, slots=True)
class Progress:
    """A snapshot a UI can render without asking anything else.

    Attributes:
        queued: Sources still waiting.
        done: Sources finished, skipped ones included.
        bytes_total: Bytes of source enqueued.
        bytes_done: Bytes of source processed.
        current: URI being indexed, or ``""``.
        index_bytes: Current size of the index file.
        budget_bytes: The ceiling it is measured against.
        stopped_for_budget: The queue stopped because the budget is spent.
    """

    queued: int
    done: int
    bytes_total: int
    bytes_done: int
    current: str
    index_bytes: int
    budget_bytes: int
    stopped_for_budget: bool = False

    @property
    def fraction(self) -> float:
        """Completed fraction in ``[0, 1]``.  Real, not indeterminate."""
        if self.bytes_total <= 0:
            return 1.0 if self.queued == 0 else 0.0
        return min(1.0, self.bytes_done / self.bytes_total)

    @property
    def budget_fraction(self) -> float:
        """How much of the disk budget is spent."""
        return min(1.0, self.index_bytes / self.budget_bytes) if self.budget_bytes else 0.0


class BackgroundIndexer:
    """Indexes a queue of sources on one worker thread.

    Args:
        index: The index to write.  Owned by this object while the worker runs.
        budget_bytes: Override the configured ceiling.  ``None`` uses
            ``cache.index_budget_gb`` (SPEC R4).
        on_progress: Called after each document and each batch, on the worker
            thread.  A Qt caller marshals it; this module stays toolkit-free.
        on_document: Called with each :class:`IndexReport` as it completes.
    """

    def __init__(
        self,
        index: TextIndex,
        *,
        budget_bytes: int | None = None,
        on_progress: Callable[[Progress], None] | None = None,
        on_document: Callable[[IndexReport], None] | None = None,
    ) -> None:
        self._index = index
        self._budget = budget_bytes
        self._on_progress = on_progress
        self._on_document = on_document
        self._queue: deque[tuple[Source, str]] = deque()
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._reports: list[IndexReport] = []
        self._bytes_total = 0
        self._bytes_done = 0
        self._done = 0
        self._current = ""
        self._stopped_for_budget = False

    # -- queue ------------------------------------------------------------ #

    def enqueue(self, sources: Iterable[Source], *, stratum: str = "") -> int:
        """Add sources to the queue.  Returns how many were added.

        Sources whose fingerprint already matches are still enqueued: deciding
        that here would mean two places that know the incremental rule, and
        :meth:`TextIndex.add` returns a skipped report in microseconds anyway.
        """
        added = 0
        with self._lock:
            for source in sources:
                self._queue.append((source, stratum))
                self._bytes_total += source.size_bytes
                added += 1
        return added

    # -- lifecycle -------------------------------------------------------- #

    def start(self) -> None:
        """Start the worker.  Idempotent while one is already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._cancel.clear()
            self._thread = threading.Thread(target=self._run, name="caissa-index", daemon=True)
            self._thread.start()

    def cancel(self) -> None:
        """Ask the worker to stop.  Committed work and cursors are kept."""
        self._cancel.set()

    def join(self, timeout: float | None = None) -> bool:
        """Wait for the worker.  ``True`` when it finished."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def run_now(self) -> list[IndexReport]:
        """Drain the queue on the calling thread.

        The synchronous path: tests use it, and so does a command-line run where
        a background thread would only add a join.
        """
        self._run()
        return list(self._reports)

    @property
    def reports(self) -> list[IndexReport]:
        """Reports for every document processed so far."""
        return list(self._reports)

    @property
    def stopped_for_budget(self) -> bool:
        """Whether the queue stopped because the disk budget ran out."""
        return self._stopped_for_budget

    def progress(self) -> Progress:
        """A snapshot.  Safe to call from any thread."""
        with self._lock:
            return Progress(
                queued=len(self._queue),
                done=self._done,
                bytes_total=self._bytes_total,
                bytes_done=self._bytes_done,
                current=self._current,
                index_bytes=database_bytes(self._index.path),
                budget_bytes=self._budget if self._budget is not None else self._index.budget_bytes,
                stopped_for_budget=self._stopped_for_budget,
            )

    # -- the worker ------------------------------------------------------- #

    def _run(self) -> None:
        while not self._cancel.is_set():
            with self._lock:
                if not self._queue:
                    break
                source, stratum = self._queue.popleft()
                self._current = source.uri
            self._emit_progress()

            try:
                report = self._index.add(
                    source,
                    stratum=stratum,
                    cancel=self._cancel,
                    budget_bytes=self._budget,
                    on_progress=lambda _units, _bytes: self._emit_progress(),
                )
            except BudgetExceededError:
                with self._lock:
                    self._stopped_for_budget = True
                    self._queue.appendleft((source, stratum))
                    self._current = ""
                self._emit_progress()
                return
            except OSError as error:
                # A source that vanished or cannot be read fails alone.  One bad
                # book must not stop a library from indexing.
                self._index.mark_failed(source.uri, str(error))
                with self._lock:
                    self._done += 1
                    self._bytes_done += source.size_bytes
                    self._current = ""
                self._emit_progress()
                continue

            with self._lock:
                self._reports.append(report)
                self._done += 1
                self._bytes_done += source.size_bytes
                self._current = ""
                if report.stopped_for_budget:
                    self._stopped_for_budget = True
            if self._on_document is not None:
                self._on_document(report)
            self._emit_progress()
            if report.stopped_for_budget:
                return

    def _emit_progress(self) -> None:
        if self._on_progress is None:
            return
        self._on_progress(self.progress())
