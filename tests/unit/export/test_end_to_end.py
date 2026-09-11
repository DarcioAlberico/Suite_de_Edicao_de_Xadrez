"""One book, five formats, and the report that says what each one cost.

This is the test a user's workflow actually is: build a document, export it
everywhere, and read the fidelity report. It exists to catch the failures that
only appear when the pieces are put together -- an exporter that works on a
paragraph and dies on a game score, a format whose options object the
dispatcher does not accept, a report that cannot be rendered.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from corpus import FORMATS

from caissa.core.model import (
    Callout,
    CalloutKind,
    Diagram,
    Document,
    DocumentMetadata,
    Emphasis,
    Heading,
    ListBlock,
    ListItem,
    ListKind,
    Paragraph,
    Quote,
    Strong,
    Table,
    TableCell,
    TableOfContents,
    TableRow,
    Text,
)
from caissa.export import EXPORTERS, export
from caissa.export.fidelity import export_then_reimport, measure_all

STARTING = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture
def book() -> Document:
    """A small but realistic chess book, hand built rather than generated."""
    return Document(
        metadata=DocumentMetadata(
            title="O final de torre",
            subtitle="Da ponte de Lucena ao Philidor",
            language="pt-BR",
            publisher="Caissa Studio",
            subjects=("xadrez", "finais", "torre"),
        ),
        body=(
            TableOfContents(),
            Heading(level=1, content=(Text(content="A ponte de Lucena"),)),
            Paragraph(
                content=(
                    Text(content="A ideia e simples: "),
                    Emphasis(content=(Text(content="construir uma ponte"),)),
                    Text(content=" com a torre na quarta fila."),
                )
            ),
            Diagram(fen=STARTING, number=1, caption=(Text(content="A posicao inicial"),)),
            Callout(
                kind=CalloutKind.TIP,
                title=(Text(content="Regra pratica"),),
                content=(Paragraph(content=(Text(content="O rei na frente do peao."),)),),
            ),
            ListBlock(
                kind=ListKind.ORDERED,
                items=(
                    ListItem(content=(Paragraph(content=(Text(content="Corte o rei."),)),)),
                    ListItem(content=(Paragraph(content=(Text(content="Construa a ponte."),)),)),
                ),
            ),
            Quote(
                content=(Paragraph(content=(Text(content="Todo final e um estudo."),)),),
                attribution=(Text(content="Tarrasch"),),
            ),
            Table(
                rows=(
                    TableRow(
                        cells=(
                            TableCell(content=(Paragraph(content=(Text(content="Peao"),)),)),
                            TableCell(content=(Paragraph(content=(Text(content="Resultado"),)),)),
                        ),
                        is_header=True,
                    ),
                    TableRow(
                        cells=(
                            TableCell(content=(Paragraph(content=(Text(content="e"),)),)),
                            TableCell(content=(Paragraph(content=(Strong(content=(Text(content="ganha"),)),)),)),
                        )
                    ),
                ),
            ),
        ),
    )


@pytest.mark.parametrize("format_name", FORMATS)
def test_the_book_exports_without_crashing(
    tmp_path: Path, book: Document, format_name: str
) -> None:
    """Every format writes a non-empty file and reports what it cost."""
    suffix = EXPORTERS[format_name].suffix
    result = export(book, tmp_path / f"livro{suffix}", format_name)

    assert result.path.exists()
    assert result.path.stat().st_size > 0
    assert result.format == format_name
    assert result.summary()
    for artifact in result.artifacts:
        assert artifact.exists(), f"artefato prometido e ausente: {artifact}"


def test_every_format_produces_a_fidelity_report(tmp_path: Path, book: Document) -> None:
    """``measure_all`` gives one report per format, each with both numbers."""
    reports = measure_all(book, FORMATS, directory=tmp_path)

    assert set(reports) == set(FORMATS)
    for name, report in reports.items():
        assert 0.0 <= report.fidelity <= 1.0, name
        assert 0.0 <= report.declared_fidelity <= 1.0, name
        assert report.declared_fidelity >= report.fidelity, (
            f"{name}: a fidelidade declarada nunca pode ser menor que a bruta"
        )
        assert report.node_count > 0, name
        assert report.summary(), name


@pytest.mark.parametrize("format_name", FORMATS)
def test_a_realistic_book_loses_nothing_undeclared(
    tmp_path: Path, book: Document, format_name: str
) -> None:
    """A book written the way a user would write one survives every format.

    The adversarial corpus in ``test_fidelity`` is there to find edges. This
    one is there to say that the edges are edges: an ordinary book comes back
    whole.
    """
    report = export_then_reimport(book, format_name, directory=tmp_path / format_name)
    assert report.declared_fidelity >= 0.99, f"{format_name}: {report}"


def test_an_unknown_format_is_refused_by_name(tmp_path: Path, book: Document) -> None:
    """Asking for a format that does not exist says which ones do."""
    from caissa.export.base import ExportError

    with pytest.raises(ExportError) as raised:
        export(book, tmp_path / "livro.rtf", "rtf")
    assert "rtf" in str(raised.value)
    assert "html" in str(raised.value)


def test_exporting_twice_produces_the_same_bytes(tmp_path: Path, book: Document) -> None:
    """A rerun of an unchanged document is byte-identical where it can be.

    Class names are interned in a stable order and nothing is timestamped in
    the markup, so diffing two exports of a book shows the author's edits and
    nothing else. Formats that stamp a date are excluded and say so.
    """
    for name in ("html", "latex"):
        suffix = EXPORTERS[name].suffix
        first = tmp_path / f"um{suffix}"
        second = tmp_path / f"dois{suffix}"
        export(book, first, name)
        export(book, second, name)
        assert first.read_bytes() == second.read_bytes(), (
            f"{name} nao e reproduzivel; diffs entre exportacoes viram ruido"
        )


def test_the_result_summary_is_written_for_a_person(
    tmp_path: Path, book: Document
) -> None:
    """The summary names the file, the counts, and the losses, in Portuguese."""
    result = export(book, tmp_path / "livro.epub", "epub")
    text = result.summary()
    assert "EPUB gravado em livro.epub" in text
    assert "diagrams" in text or "nodes" in text
