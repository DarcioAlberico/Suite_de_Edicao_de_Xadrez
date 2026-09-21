"""A11 (ciclo 2): the provenance sidecar next to the exported book.

What has to hold: every diagram and game of the IR has one line, keyed like the trunk's
PGN sidecar (``p<page>:d<n>``) with the node's ULID; the line carries what the EPUB/DOCX
loses (rect, image hash, model hash, per-square confidence, repairs, alternatives, human
verification); a synthetic item survives export and reimport; and the sabotage -- a key by
FEN -- makes two equal positions on two pages collide, and the collision is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.core.model import (
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
    SourceKind,
    SquareRepair,
    Text,
)
from caissa.export.provenance import (
    ProvenanceCollision,
    read_sidecar,
    records_for,
    sidecar_path,
    write_sidecar,
)

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
