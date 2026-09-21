"""OCR_UI ciclo 2, C12: the printed demand reaches the ``Diagram`` -- and is checked.

``Diagram.stipulation`` used to carry only "Brancas jogam"; ``Diagram.solution`` was never
filled (análise §3.10, SPEC §6.4).  Now a caption ``#2`` gives ``stipulation="Mate em 2"``,
the key move as ``solution`` when the reading closes, and a warning that says so either way
-- a demand that does not close never erases the reading.
"""

from __future__ import annotations

import pytest

from caissa.core.model import Diagram, RecognitionPath
from caissa.ingest.pdf.importer import DiagramHit, PdfImportOptions, import_pdf

from .conftest import PageSpec, requires_pymupdf

pytestmark = requires_pymupdf


def _trunk_or_skip() -> None:
    try:
        from caissa.vision.classify.cvoff import ensure_cvoff_on_path

        ensure_cvoff_on_path()
        import chess_diagram_ocr.estipulacao  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"o verificador é do tronco: {exc}")

#: Black to move, mate in exactly 2: 1...Qd1+ 2.Re1 Qxe1#.
CLOSES = "6k1/5ppp/3q4/4R3/8/8/5PPP/6K1"
#: The same reading with the queen's colour wrong: nothing mates.
FAILS = "6k1/5ppp/3Q4/4R3/8/8/5PPP/6K1"


def _import(pdf_file, placement: str, caption: str, **options):
    hit = DiagramHit(box=(72, 120, 272, 320), fen=f"{placement} w - - 0 1", confidence=0.97,
                     path=RecognitionPath.NEURAL, method="contour",
                     square_confidences=tuple([0.97] * 64))
    spec = PageSpec()
    spec.text("Pretas jogam", 72, 330, size=10)
    spec.text(caption, 72, 344, size=10)
    pdf = pdf_file([spec])
    result = import_pdf(pdf, PdfImportOptions(
        diagram_finder=lambda _page, _frame, _text: [hit], enable_ocr=False, games=False,
        **options))
    diagrams = [b for b in result.document.body if isinstance(b, Diagram)]
    assert len(diagrams) == 1
    return diagrams[0], result.report


def test_a_demand_that_closes_gives_the_stipulation_and_the_key(pdf_file) -> None:
    _trunk_or_skip()
    diagram, report = _import(pdf_file, CLOSES, "#2")
    assert diagram.stipulation == "Mate em 2"
    assert diagram.fen.split()[1] == "b", "a legenda deu o lado"
    assert diagram.solution is not None
    assert [node.san for node in diagram.solution.children] == ["Qd1+"]
    assert diagram.solution.initial_fen == diagram.fen
    assert diagram.recognition is not None
    warnings = diagram.recognition.warnings
    assert any(w.startswith("exigência #2: ") and "fecha" in w for w in warnings)
    assert report.counters["stipulations_checked"] == 1
    assert report.counters["stipulations_failed"] == 0


def test_a_demand_that_does_not_close_is_said_and_the_reading_stays(pdf_file) -> None:
    _trunk_or_skip()
    diagram, report = _import(pdf_file, FAILS, "#2")
    assert diagram.stipulation == "Mate em 2"
    assert diagram.fen.startswith(FAILS), "a leitura não é apagada"
    assert diagram.solution is None
    assert diagram.recognition is not None
    assert any("não fecha" in w for w in diagram.recognition.warnings)
    assert report.counters["stipulations_failed"] == 1


def test_without_a_demand_the_stipulation_is_the_side_and_nothing_is_checked(pdf_file) -> None:
    diagram, report = _import(pdf_file, CLOSES, "Diagrama 12")
    assert diagram.stipulation == "Pretas jogam"
    assert diagram.solution is None
    assert report.counters["stipulations_checked"] == 0


def test_the_switch_is_the_before(pdf_file) -> None:
    diagram, report = _import(pdf_file, CLOSES, "#2", verify_stipulations=False)
    assert diagram.stipulation == "Mate em 2", "a exigência impressa continua dita"
    assert diagram.solution is None
    assert report.counters["stipulations_checked"] == 0
    assert diagram.recognition is not None
    assert not any(w.startswith("exigência") for w in diagram.recognition.warnings)
