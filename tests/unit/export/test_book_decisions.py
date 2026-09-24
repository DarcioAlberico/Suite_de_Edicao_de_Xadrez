"""OCR_UI ciclo 2, passo A3: the reviewer's corrected position reaches the EPUB.

``docs/OCR_UI_ANALISE_C2.md`` §6.2: the window saved the correction and the
export shipped the machine's reading.  What is pinned here, on a synthetic
book with a finder that "reads" a known wrong position:

* a decision recorded in a temporary folder is applied on import and the
  EPUB carries the corrected FEN, the machine's reading staying in
  ``recognition.fen`` and the provenance saying a human verified it;
* ``export_book`` loads the book's file by itself when the caller passed no
  ``diagram_decisions`` (through :data:`ENV_ROOT`, so the real ``labeling/``
  is never touched);
* the sabotage of the roadmap -- exporting without applying -- ships the
  machine's FEN, which is what the ``percurso`` gate now refuses;
* ``export_book(document=...)`` writes an import already in hand and does
  not read the PDF again;
* a correction applied to the import in hand keeps the book's printed demand
  (``"Mate em 2"``, C12) -- only a stipulation that restates the side, or
  none, takes the reviewer's side.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_INGEST_TESTS = Path(__file__).resolve().parent.parent / "ingest"
if str(_INGEST_TESTS) not in sys.path:
    sys.path.insert(0, str(_INGEST_TESTS))

from caissa.core.model import (  # noqa: E402
    Diagram,
    DiagramSource,
    Document,
    RecognitionPath,
    Rect,
    SourceKind,
)
from caissa.export import export_book, read_epub  # noqa: E402
from caissa.export.book import apply_diagram_decisions  # noqa: E402
from caissa.ingest.pdf import (  # noqa: E402
    DiagramHit,
    ImportReport,
    ImportResult,
    PdfImportOptions,
    import_pdf,
)
from caissa.ocr.diagram_decisions import (  # noqa: E402
    ENV_ROOT,
    DiagramDecision,
    DiagramDecisions,
    record,
)
from conftest import LOREM, PageSpec, build_pdf, lines_of, requires_pymupdf  # noqa: E402

MACHINE = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"
CORRECTED = "8/8/8/4k3/8/8/4K3/4R3 b - - 0 1"
BOX = (100.0, 200.0, 300.0, 400.0)


def _finder(calls: list[int]):
    def finder(_page, frame, _text):
        calls.append(frame.index)
        return [DiagramHit(box=BOX, fen=MACHINE, confidence=0.71, path=RecognitionPath.NEURAL,
                           method="contour", square_confidences=(0.95,) * 64)]
    return finder


@pytest.fixture
def book(tmp_path: Path) -> Path:
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=80, width_chars=60))
    spec.items.extend(lines_of(LOREM, x=72, y=500, width_chars=60))
    path = tmp_path / "livro.pdf"
    path.write_bytes(build_pdf([spec, spec]))
    return path


def _diagrams(path: Path, *, sidecar: bool = False) -> list[Diagram]:
    """The diagrams a reader sees (the XHTML), or the packaged IR with its audit trail."""
    return [b for b in read_epub(path, use_sidecar=sidecar).body if isinstance(b, Diagram)]


@requires_pymupdf
def test_a_recorded_decision_reaches_the_epub_with_the_machine_reading_kept(
    book: Path, tmp_path: Path
) -> None:
    root = tmp_path / "decisoes"
    record(book, DiagramDecision.now(0, (104.0, 203.0, 303.0, 402.0), CORRECTED,
                                     reviewer="ana", source="teste"), root=root)
    calls: list[int] = []
    result = export_book(
        book, tmp_path / "corrigido.epub", "epub", pages=[0, 1], enable_ocr=False,
        import_options=PdfImportOptions(
            diagram_finder=_finder(calls), games=False,
            diagram_decisions=DiagramDecisions.for_pdf(book, root=root),
        ),
    )
    assert result.diagram_decisions_applied == 1
    assert "1 posição(ões) corrigida(s) pelo revisor" in result.summary()
    assert [d.fen for d in _diagrams(result.path)] == [CORRECTED, MACHINE], (
        "a página 1 tem a decisão; a página 2, a mesma caixa, não -- as decisões são por página"
    )
    diagrams = _diagrams(result.path, sidecar=True)
    assert [d.fen for d in diagrams] == [CORRECTED, MACHINE]
    corrected = diagrams[0]
    assert corrected.recognition is not None
    assert corrected.recognition.fen == MACHINE, "a leitura da máquina fica no registro"
    assert any(w.startswith("corrigido pelo revisor (ana)") for w in corrected.recognition.warnings)
    assert corrected.provenance is not None
    assert corrected.provenance.verified_by_human is True
    assert corrected.provenance.kind is SourceKind.HUMAN
    assert corrected.stipulation == "Pretas jogam"
    untouched = diagrams[1]
    assert untouched.provenance is not None
    assert untouched.provenance.verified_by_human is False


@requires_pymupdf
def test_export_book_loads_the_books_decisions_by_itself(
    book: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "decisoes"))
    record(book, DiagramDecision.now(0, BOX, CORRECTED, source="teste"))
    assert (tmp_path / "decisoes" / "livro.json").is_file()
    result = export_book(
        book, tmp_path / "auto.epub", "epub", pages=[0], enable_ocr=False,
        import_options=PdfImportOptions(diagram_finder=_finder([]), games=False),
    )
    assert result.diagram_decisions_applied == 1
    assert [d.fen for d in _diagrams(result.path)] == [CORRECTED]


@requires_pymupdf
def test_the_sabotage_exporting_without_applying_ships_the_machine_fen(
    book: Path, tmp_path: Path, monkeypatch
) -> None:
    """What the ``percurso`` gate's ``--sabotar sem_decisao`` reproduces: the old behaviour."""
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "vazio"))
    result = export_book(
        book, tmp_path / "sabotado.epub", "epub", pages=[0], enable_ocr=False,
        import_options=PdfImportOptions(diagram_finder=_finder([]), games=False),
    )
    assert result.diagram_decisions_applied == 0
    assert [d.fen for d in _diagrams(result.path)] == [MACHINE]
    diagrams = _diagrams(result.path, sidecar=True)
    assert diagrams[0].provenance is not None
    assert diagrams[0].provenance.verified_by_human is False


@requires_pymupdf
def test_a_document_in_hand_is_written_without_reading_the_pdf_again(
    book: Path, tmp_path: Path
) -> None:
    calls: list[int] = []
    root = tmp_path / "decisoes"
    record(book, DiagramDecision.now(0, BOX, CORRECTED, source="teste"), root=root)
    imported = import_pdf(book, PdfImportOptions(
        pages=[0, 1], diagram_finder=_finder(calls), games=False, enable_ocr=False,
        asset_dir=tmp_path / "assets",
        diagram_decisions=DiagramDecisions.for_pdf(book, root=root),
    ))
    assert calls == [0, 1]
    result = export_book(
        book, tmp_path / "pronto.epub", "epub", pages=[0, 1], enable_ocr=False,
        import_options=PdfImportOptions(diagram_finder=_finder(calls)),
        document=imported,
    )
    assert calls == [0, 1], "com `document=` o PDF não é lido de novo"
    assert [d.fen for d in _diagrams(result.path)] == [CORRECTED, MACHINE]
    assert result.diagram_decisions_applied == 1
    assert result.import_report is imported.report


@requires_pymupdf
def test_a_bare_document_is_accepted_for_the_whole_book_only(book: Path, tmp_path: Path) -> None:
    """A bare ``Document`` says nothing about which pages it holds, so it is written as it is
    only when the export asks for the whole book; for a subset the book is read again."""
    calls: list[int] = []
    imported = import_pdf(book, PdfImportOptions(
        pages=[0, 1], diagram_finder=_finder(calls), games=False, enable_ocr=False,
        asset_dir=tmp_path / "assets",
    ))
    result = export_book(
        book, tmp_path / "documento.epub", "epub", pages=[0, 1], enable_ocr=False,
        import_options=PdfImportOptions(diagram_finder=_finder(calls)),
        document=imported.document,
    )
    assert calls == [0, 1], "the whole book: written as it is, no second import"
    assert [d.fen for d in _diagrams(result.path)] == [MACHINE, MACHINE]
    assert result.import_report.counters == {}, "sem o relatório em mãos, o resultado não inventa"
    calls.clear()
    result = export_book(
        book, tmp_path / "pagina1.epub", "epub", pages=[0], enable_ocr=False,
        import_options=PdfImportOptions(diagram_finder=_finder(calls)),
        document=imported.document,
    )
    assert calls == [0], "a subset: the book is read again, for the page asked"
    assert [d.fen for d in _diagrams(result.path)] == [MACHINE]


@requires_pymupdf
def test_a_result_of_more_pages_than_asked_is_not_written_as_it_is(book: Path, tmp_path: Path) -> None:
    """Critic, fase 1 ciclo 1: three pages imported and ``pages=[0]`` came out as three."""
    calls: list[int] = []
    imported = import_pdf(book, PdfImportOptions(
        pages=[0, 1], diagram_finder=_finder(calls), games=False, enable_ocr=False,
        asset_dir=tmp_path / "assets",
    ))
    calls.clear()
    result = export_book(
        book, tmp_path / "so_a_primeira.epub", "epub", pages=[0], enable_ocr=False,
        import_options=PdfImportOptions(diagram_finder=_finder(calls)),
        document=imported,
    )
    assert calls == [0], "read again, only the page asked"
    assert len(_diagrams(result.path)) == 1


@requires_pymupdf
def test_a_decision_recorded_after_the_import_still_reaches_the_document_in_hand(
    book: Path, tmp_path: Path, monkeypatch
) -> None:
    """The window's flow: import, correct and save, export from memory (``document=``)."""
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "decisoes"))
    imported = import_pdf(book, PdfImportOptions(
        pages=[0, 1], diagram_finder=_finder([]), games=False, enable_ocr=False,
        asset_dir=tmp_path / "assets",
    ))
    assert imported.report.counters["diagram_decisions_applied"] == 0
    record(book, DiagramDecision.now(0, BOX, CORRECTED, reviewer="ana", source="teste"))
    result = export_book(
        book, tmp_path / "depois.epub", "epub", pages=[0, 1], enable_ocr=False,
        document=imported.document,
    )
    assert result.diagram_decisions_applied == 1
    assert [d.fen for d in _diagrams(result.path)] == [CORRECTED, MACHINE]
    corrected = _diagrams(result.path, sidecar=True)[0]
    assert corrected.recognition is not None
    assert corrected.recognition.fen == MACHINE
    assert any(w.startswith("corrigido pelo revisor (ana)") for w in corrected.recognition.warnings)
    assert corrected.provenance is not None
    assert corrected.provenance.verified_by_human is True


def _in_hand(stipulation: str | None) -> ImportResult:
    """An import already in hand: one diagram at ``BOX`` on page 1, read as ``MACHINE``."""
    diagram = Diagram(fen=MACHINE, stipulation=stipulation, source=DiagramSource(
        page_index=0, rect=Rect(x=100.0, y=200.0, width=200.0, height=200.0)))
    return ImportResult(document=Document(body=(diagram,)), report=ImportReport())


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Mate em 2", "Mate em 2"),  # the book's demand outlives the correction
        (None, "Pretas jogam"),  # nothing better: the reviewer's side is filled
        ("Brancas jogam", "Pretas jogam"),  # a side sentence follows the corrected side
        ("brancas  jogam.", "Pretas jogam"),  # however it was spaced or cased
    ],
)
def test_a_correction_keeps_the_printed_demand_and_fills_only_the_side(
    before: str | None, after: str
) -> None:
    decisions = DiagramDecisions(items=(DiagramDecision.now(0, BOX, CORRECTED, source="teste"),))
    result = apply_diagram_decisions(_in_hand(before), decisions)
    (diagram,) = result.document.body
    assert diagram.fen == CORRECTED
    assert diagram.stipulation == after
    assert diagram.side_to_move_indicator is True
    assert result.report.counters["diagram_decisions_applied"] == 1


@requires_pymupdf
def test_a_correction_after_the_import_keeps_the_books_demand(
    tmp_path: Path, monkeypatch
) -> None:
    """The window's flow on a problem: the caption prints ``#2``, the import says «Mate em 2»,
    the reviewer corrects the position -- and the EPUB still says «Mate em 2»; it used to
    trade the book's demand for «Pretas jogam»."""
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "decisoes"))
    pdf = tmp_path / "problemas.pdf"
    pdf.write_bytes(build_pdf([PageSpec().text("#2", 100, 410, size=10)]))
    imported = import_pdf(pdf, PdfImportOptions(
        diagram_finder=_finder([]), games=False, enable_ocr=False, verify_stipulations=False,
        asset_dir=tmp_path / "assets",
    ))
    (read,) = [b for b in imported.document.body if isinstance(b, Diagram)]
    assert read.stipulation == "Mate em 2", "a legenda deu a exigência"
    record(pdf, DiagramDecision.now(0, BOX, CORRECTED, reviewer="ana", source="teste"))
    result = export_book(pdf, tmp_path / "problemas.epub", "epub", enable_ocr=False,
                         document=imported.document)
    assert result.diagram_decisions_applied == 1
    for diagram in (_diagrams(result.path, sidecar=True)[0], _diagrams(result.path)[0]):
        assert diagram.fen == CORRECTED
        assert diagram.stipulation == "Mate em 2"
