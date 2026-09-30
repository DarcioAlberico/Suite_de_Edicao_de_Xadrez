"""A11 (ciclo 2): the provenance sidecar next to the exported book.

What has to hold: every diagram and game of the IR has one line, keyed like the trunk's
PGN sidecar (``p<page>:d<n>``) with the node's ULID; the line carries what the EPUB/DOCX
loses (rect, image hash, model hash, per-square confidence, repairs, alternatives, human
verification); a synthetic item survives export and reimport; and the sabotage -- a key by
FEN -- makes two equal positions on two pages collide, and the collision is refused.

And on a real import: the importer stores a :class:`Rect`, not a tuple -- ``list()`` of it
raised, ``export_book`` swallowed the error into the log, and no imported book ever got its
sidecar.  The rect is written by name, and a sidecar that fails is said in the result.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

_INGEST_TESTS = Path(__file__).resolve().parent.parent / "ingest"
if str(_INGEST_TESTS) not in sys.path:
    sys.path.insert(0, str(_INGEST_TESTS))

from caissa.core.model import (  # noqa: E402
    Diagram,
    DiagramSource,
    Document,
    FenCandidate,
    GameScore,
    MoveNode,
    Paragraph,
    Provenance,
    RecognitionPath,
    RecognitionResult,
    Rect,
    SourceKind,
    SquareRepair,
    Text,
)
from caissa.export import export_book  # noqa: E402
from caissa.export.book import BookExportResult  # noqa: E402
from caissa.export.provenance import (  # noqa: E402
    ProvenanceCollision,
    read_sidecar,
    records_for,
    sidecar_path,
    write_sidecar,
)
from caissa.ingest.pdf import DiagramHit, PdfImportOptions  # noqa: E402
from caissa.ocr.diagram_decisions import ENV_ROOT  # noqa: E402
from conftest import PageSpec, build_pdf, requires_pymupdf  # noqa: E402

FEN = "6k1/5ppp/3q4/4R3/8/8/5PPP/6K1 b - - 0 1"


def _diagram(page: int, x0: float = 10.0, *, verified: bool = False) -> Diagram:
    return Diagram(
        fen=FEN,
        source=DiagramSource(kind=SourceKind.PDF_TEXT_LAYER, path="livro.pdf", content_hash="cc" * 32,
                             page_index=page, rect=(x0, 20.0, x0 + 100.0, 120.0), dpi=220.0,
                             image_hash="ab" * 32),
        recognition=RecognitionResult(
            fen=FEN, per_square_confidence=tuple([0.99] * 64), path=RecognitionPath.VECTOR_INFERRED,
            model_name="piece_classifier", model_hash="deadbeef",
            repairs=(SquareRepair(square="d6", recognised="Q", repaired="q", reason="tinta"),),
            alternatives=(FenCandidate(fen=FEN, score=0.3),), warnings=("cor pela tinta",)),
        verified_by_human=verified,
        provenance=Provenance(kind=SourceKind.OCR, page_index=page, engine="cvoff", confidence=0.97,
                              verified_by_human=verified, document_hash="cc" * 32),
    )


def _document() -> Document:
    game = GameScore(initial_fen=FEN, children=(MoveNode(san="Qxe5", ply=1),),
                     provenance=Provenance(kind=SourceKind.OCR, page_index=3, engine="tesseract",
                                           confidence=0.9))
    return Document(body=(
        Paragraph(content=(Text(content="Diagrama 1"),)),
        _diagram(3, verified=True), game, _diagram(3, 200.0), _diagram(9),
    ))


def test_every_diagram_and_game_has_a_keyed_line_with_what_the_book_loses(tmp_path: Path):
    document = _document()
    target = tmp_path / "Livro.epub"
    path = write_sidecar(document, target, format_name="epub", pages=[3, 9],
                         profile={"closures": 1})
    assert path == sidecar_path(target) == tmp_path / "Livro.proveniencia.jsonl"
    header, records = read_sidecar(path)
    assert header["format"] == "epub" and header["pages"] == [3, 9]
    assert header["document_hash"] == "cc" * 32 and header["profile"] == {"closures": 1}
    assert set(records) == {"p3:d1", "p3:d2", "p9:d1", "p3:g1"}
    first = records["p3:d1"]
    assert first["id"] == str(document.body[1].id)
    assert first["rect"] == [10.0, 20.0, 110.0, 120.0]
    assert first["image_hash"] == "ab" * 32
    assert first["verified_by_human"] is True
    assert first["recognition"]["model_hash"] == "deadbeef"
    assert len(first["recognition"]["per_square_confidence"]) == 64
    assert first["recognition"]["repairs"][0]["square"] == "d6"
    assert first["recognition"]["alternatives"][0]["score"] == 0.3
    assert first["recognition"]["warnings"] == ["cor pela tinta"]
    assert first["provenance"]["engine"] == "cvoff" and first["provenance"]["verified_by_human"] is True
    assert records["p3:d2"]["verified_by_human"] is False
    assert records["p3:g1"]["initial_fen"] == FEN and records["p3:g1"]["moves"] == 1


def test_a_synthetic_item_survives_export_and_reimport(tmp_path: Path):
    document = Document(body=(_diagram(12),))
    write_sidecar(document, tmp_path / "x.docx", format_name="docx")
    _, records = read_sidecar(sidecar_path(tmp_path / "x.docx"))
    back = records["p12:d1"]
    diagram = document.body[0]
    assert back["fen"] == diagram.fen
    assert back["id"] == str(diagram.id)
    assert tuple(back["rect"]) == diagram.source.rect
    assert back["recognition"]["per_square_confidence"] == list(diagram.recognition.per_square_confidence)


def test_the_same_position_on_two_pages_is_two_lines_and_a_fen_key_collides(tmp_path: Path):
    document = Document(body=(_diagram(3), _diagram(9)))
    assert len(records_for(document)) == 2
    write_sidecar(document, tmp_path / "ok.epub")
    with pytest.raises(ProvenanceCollision):
        write_sidecar(document, tmp_path / "sabotado.epub", key_of=lambda r: r["fen"])
    assert not sidecar_path(tmp_path / "sabotado.epub").exists()


def test_a_real_rect_is_written_by_name(tmp_path: Path):
    """What every import stores: :class:`Rect` (x, y, width, height, unit), not a tuple."""
    rect = Rect(x=10.0, y=20.0, width=100.0, height=100.0)
    diagram = _diagram(4)
    assert diagram.provenance is not None
    diagram = replace(diagram, source=replace(diagram.source, rect=rect),
                      provenance=replace(diagram.provenance, rect=rect))
    _, records = read_sidecar(write_sidecar(Document(body=(diagram,)), tmp_path / "Livro.epub"))
    by_name = {"x": 10.0, "y": 20.0, "width": 100.0, "height": 100.0, "unit": "pt"}
    assert records["p4:d1"]["rect"] == by_name
    assert records["p4:d1"]["provenance"]["rect"] == by_name


def _imported_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BookExportResult:
    """``export_book`` on a synthetic PDF whose one diagram the importer reads for real."""
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "decisoes"))  # never the real labeling/
    pdf = tmp_path / "livro.pdf"
    pdf.write_bytes(build_pdf([PageSpec().text("Texto da página, sob o diagrama.", 72, 360)]))
    hit = DiagramHit(box=(72.0, 120.0, 272.0, 320.0), fen=FEN, confidence=0.9,
                     path=RecognitionPath.NEURAL, method="contour",
                     square_confidences=(0.95,) * 64)
    return export_book(pdf, tmp_path / "livro.epub", "epub", enable_ocr=False,
                       import_options=PdfImportOptions(diagram_finder=lambda *_: [hit],
                                                       games=False))


@requires_pymupdf
def test_a_book_exported_from_a_real_import_has_its_sidecar(tmp_path: Path, monkeypatch):
    result = _imported_book(tmp_path, monkeypatch)
    assert result.provenance_path == sidecar_path(result.path)
    assert result.provenance_error is None
    header, records = read_sidecar(result.provenance_path)
    (diagram,) = [b for b in result.document.body if isinstance(b, Diagram)]
    assert isinstance(diagram.source.rect, Rect), "the importer's own type, not a test's tuple"
    assert header["format"] == "epub"
    assert header["pages"] == [0]
    record = records["p0:d1"]
    assert record["id"] == str(diagram.id)
    by_name = {"x": 72.0, "y": 120.0, "width": 200.0, "height": 200.0, "unit": "pt"}
    assert record["rect"] == by_name
    assert record["provenance"]["rect"] == by_name
    assert "proveniência" not in result.summary()


@requires_pymupdf
def test_a_sidecar_that_fails_is_said_in_the_result_not_only_in_the_log(tmp_path: Path,
                                                                        monkeypatch):
    """Additive -- the book is written either way -- but the caller is told why it is alone."""
    import caissa.export.provenance as sidecar

    def refuse(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(sidecar, "write_sidecar", refuse)
    result = _imported_book(tmp_path, monkeypatch)
    assert result.path.is_file()
    assert result.provenance_path is None
    assert result.provenance_error == "OSError: disco cheio"
    assert "sidecar de proveniência não gravado (OSError: disco cheio)" in result.summary()
