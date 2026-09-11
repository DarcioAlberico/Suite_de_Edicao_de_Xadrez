"""Incremental indexing, resumption, the disk budget, and degraded indexes.

The claims tested here are operational rather than algorithmic: "adding one book
reads one book", "a cancelled pass keeps its work", "a full budget stops instead
of filling the disk", "a corrupt index says so".  Each is a promise the user
experiences directly and none of them is visible in a search result.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from caissa.index import (
    BudgetExceededError,
    IndexCorruptError,
    IndexMissingError,
    IndexStaleError,
    IndexUnit,
    Query,
    SearchIndex,
    TextIndex,
    TextSource,
    index_all,
)
from caissa.index.schema import SCHEMA_VERSION, connect, write_meta
from caissa.notation.regex_engine import Scope


@dataclass
class CountingSource:
    """A source that records how many times it was actually read.

    The incremental claim is "it did not read the file", and only a counter can
    assert that.  Timing it would assert "it was fast", which is a different and
    weaker statement.
    """

    uri: str
    paragraphs: list[str]
    key: str = "v1"
    title: str = ""
    kind: str = "text"
    reads: int = field(default=0, init=False)

    @property
    def size_bytes(self) -> int:
        return sum(len(p.encode("utf-8")) for p in self.paragraphs)

    @property
    def content_key(self) -> str:
        return self.key

    def units(self, *, start: int = 0) -> Iterator[IndexUnit]:
        self.reads += 1
        for ordinal, text in enumerate(self.paragraphs):
            if ordinal < start:
                continue
            yield IndexUnit(text=text, scope=Scope.ALL)


def _many(count: int, uri: str = "mem://big") -> CountingSource:
    return CountingSource(uri=uri, paragraphs=[f"posicao numero {n} com Nf3" for n in range(count)])


# --------------------------------------------------------------------------- #
# Incremental
# --------------------------------------------------------------------------- #


def test_unchanged_document_is_not_read_again(index, book):
    first = index.add(book)
    assert not first.skipped
    second = index.add(book)
    assert second.skipped
    assert second.bytes_read == 0


def test_adding_one_book_reads_only_that_book(index):
    """The whole point of an incremental index, asserted on read counts."""
    library = [CountingSource(uri=f"mem://livro-{n}", paragraphs=[f"livro {n} com Nf3"])
               for n in range(5)]
    index_all(index, library)
    assert [source.reads for source in library] == [1] * 5

    newcomer = CountingSource(uri="mem://livro-novo", paragraphs=["um livro novo com O-O-O"])
    index_all(index, [*library, newcomer])

    assert [source.reads for source in library] == [1] * 5, "livros antigos foram relidos"
    assert newcomer.reads == 1


def test_changed_fingerprint_forces_a_reread(index):
    source = CountingSource(uri="mem://livro", paragraphs=["antes"])
    index.add(source)
    assert index.needs_reindex(source) is False

    source.paragraphs = ["depois"]
    source.key = "v2"
    assert index.needs_reindex(source) is True
    index.add(source)
    assert source.reads == 2

    reader = SearchIndex.wrap(index.connection)
    assert reader.search(Query(text="antes")).total == 0
    assert reader.search(Query(text="depois")).total == 1


def test_force_reindexes_an_unchanged_document(index, book):
    index.add(book)
    report = index.add(book, force=True)
    assert not report.skipped
    assert report.units > 0
    assert index.stats().nodes == report.units, "reindexar duplicou os nos"


def test_remove_drops_every_row(index, book):
    index.add(book)
    assert index.stats().nodes > 0
    assert index.remove(book.uri) is True
    stats = index.stats()
    assert stats.nodes == 0
    assert stats.documents == 0
    assert index.remove(book.uri) is False


# --------------------------------------------------------------------------- #
# Resumption
# --------------------------------------------------------------------------- #


def test_cancelled_pass_keeps_its_work_and_resumes(index):
    source = _many(120)
    cancel = threading.Event()

    def stop_after_first_batch(units, _bytes):
        if units >= 20:
            cancel.set()

    first = index.add(source, cancel=cancel, batch_size=20, on_progress=stop_after_first_batch)
    assert first.cancelled
    assert 0 < first.units < 120
    row = index.document(source.uri)
    assert row is not None
    assert row.state == "partial"
    assert row.cursor == first.units

    second = index.add(source)
    assert second.resumed_from == first.units
    assert first.units + second.units == 120
    assert index.stats().nodes == 120
    assert index.document(source.uri).state == "complete"


def test_resumed_document_reports_all_its_nodes(index):
    source = _many(60)
    cancel = threading.Event()
    index.add(
        source,
        cancel=cancel,
        batch_size=10,
        on_progress=lambda units, _b: cancel.set() if units >= 10 else None,
    )
    index.add(source)
    row = index.document(source.uri)
    assert row is not None
    assert row.node_count == 60


# --------------------------------------------------------------------------- #
# Budget (SPEC R4)
# --------------------------------------------------------------------------- #


def test_spent_budget_refuses_before_reading(index, book):
    with pytest.raises(BudgetExceededError) as error:
        index.add(book, budget_bytes=1)
    assert "orcamento" in str(error.value)
    assert error.value.budget_bytes == 1


def test_budget_stops_mid_pass_and_keeps_what_fitted(index):
    source = _many(40_000)
    ceiling = index.stats().index_bytes + 64 * 1024
    report = index.add(source, budget_bytes=ceiling, batch_size=250)

    assert report.stopped_for_budget
    assert 0 < report.units < 40_000
    row = index.document(source.uri)
    assert row is not None
    assert row.state == "partial"
    assert "orcamento" in row.error

    reader = SearchIndex.wrap(index.connection)
    assert reader.search(Query(text="posicao")).total > 0, "o que coube deve continuar pesquisavel"


def test_budget_comes_from_the_configuration(index):
    """SPEC R4 says the ceiling is the user's, not this module's invention."""
    from caissa.core.config import CacheConfig, CaissaConfig

    configured = TextIndex(
        index.path, config=CaissaConfig(cache=CacheConfig(index_budget_gb=0.5))
    )
    assert configured.budget_bytes == int(0.5 * 1024**3)
    configured.close()


def test_index_all_stops_when_the_budget_runs_out(index):
    """The queue stops; it does not fail, and it does not fill the disk."""
    library = [_many(20_000, uri=f"mem://grande-{n}") for n in range(4)]
    ceiling = index.stats().index_bytes + 64 * 1024
    reports = index_all(index, library, budget_bytes=ceiling)

    assert len(reports) < len(library), "o orcamento nao interrompeu a fila"
    untouched = [source for source in library if source.reads == 0]
    assert untouched, "nenhuma fonte ficou pendente para retomar depois"

    reader = SearchIndex.wrap(index.connection)
    assert reader.search(Query(text="posicao")).total > 0, "o que coube deve continuar valido"


# --------------------------------------------------------------------------- #
# Degraded indexes
# --------------------------------------------------------------------------- #


def test_missing_index_is_named_as_missing(tmp_path):
    with pytest.raises(IndexMissingError):
        SearchIndex(tmp_path / "nunca-criado.sqlite")


def test_corrupt_index_is_named_as_corrupt(tmp_path):
    path = tmp_path / "meio.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.commit()
    connection.close()
    with pytest.raises(IndexCorruptError) as error:
        connect(path, create=False)
    assert "nodes" in str(error.value)


def test_stale_index_is_named_as_stale(tmp_path, book):
    path = tmp_path / "velho.sqlite"
    with TextIndex(path) as index:
        index.add(book)
        write_meta(index.connection, "tokenizer_version", "0")

    with pytest.raises(IndexStaleError) as error:
        connect(path, create=False)
    assert error.value.expected.startswith("tokenizer_version=")


def test_a_stale_index_is_not_silently_answered(tmp_path, book):
    """Answering out of an index built by another tokenizer would miss silently."""
    path = tmp_path / "velho2.sqlite"
    with TextIndex(path) as index:
        index.add(book)
        write_meta(index.connection, "zobrist_version", "0")
    with pytest.raises(IndexStaleError):
        SearchIndex(path)


def test_schema_version_is_recorded(index):
    from caissa.index.schema import read_meta

    assert read_meta(index.connection)["schema_version"] == SCHEMA_VERSION


def test_failed_source_is_recorded_not_forgotten(index, book):
    index.add(book)
    index.mark_failed(book.uri, "arquivo sumiu")
    row = index.document(book.uri)
    assert row is not None
    assert row.state == "failed"
    assert row.error == "arquivo sumiu"


# --------------------------------------------------------------------------- #
# Accounting
# --------------------------------------------------------------------------- #


def test_stats_count_what_was_indexed(index, book):
    report = index.add(book)
    stats = index.stats()
    assert stats.documents == 1
    assert stats.nodes == report.units
    assert stats.index_bytes > 0
    assert stats.corpus_bytes == book.size_bytes
    assert stats.ratio > 0
