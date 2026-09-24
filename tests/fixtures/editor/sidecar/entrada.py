"""Entrada dourada do sidecar v2.

Este módulo é deliberadamente uma fixture, não um escritor: os objetos vêm das
classes reais do produto e o dicionário devolvido por :func:`entrada` é o
contrato congelado que o escritor v2 receberá.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from caissa.core.model import (
    ConfidenceBand,
    Diagram,
    DiagramSource,
    Document,
    FenCandidate,
    GameScore,
    MoveNode,
    Orientation,
    Paragraph,
    Provenance,
    RecognitionPath,
    RecognitionResult,
    Rect,
    SourceKind,
    SquareRepair,
    Text,
    ULID,
)
from caissa.ocr.diagram_decisions import DiagramDecision
from caissa.ocr.review import Action, AuditEntry, Decided, ReviewItem


FEN_MACHINE = "8/8/3k4/8/4K3/8/8/8 b - - 7 42"
FEN_CORRIGIDA = "8/8/3k4/8/4K3/8/8/8 w - - 7 42"
FONTE_HASH = "ab" * 32


def _id(numero: int) -> ULID:
    """ID estável para que a fixture não dependa do relógio/entropia."""

    return ULID.from_parts(1_704_067_200_000, numero)


def _proveniencia_bloco() -> Provenance:
    # Imita caissa.ingest.pdf.importer.PdfImporter._provenance para um bloco OCR.
    return Provenance(
        kind=SourceKind.OCR,
        document_path="livro-fonte.pdf",
        document_hash=FONTE_HASH,
        page_index=4,
        block_index=7,
        rect=Rect(x=13.123456789, y=27.987654321, width=301.246813579,
                  height=88.135792468, unit="px"),
        dpi=287.654321,
        engine="tesseract+glyph",
        engine_version="5.5.0-fixture",
        model_hash="model-bloco-123",
        confidence=0.123456789,
        band=ConfidenceBand.DOUBTFUL,
        extracted_at=datetime(2026, 1, 2, 3, 4, 5, 678901,
                              tzinfo=timezone(timedelta(hours=-3))),
        verified_by_human=True,
        out_of_model=True,
        note="trecho OCR para revisão humana",
    )


def _proveniencia_diagrama() -> Provenance:
    # Imita caissa.ingest.pdf.importer.PdfImporter._provenance no nó Diagram.
    return Provenance(
        kind=SourceKind.VISION,
        document_path="livro-fonte.pdf",
        document_hash=FONTE_HASH,
        page_index=4,
        block_index=8,
        rect=Rect(x=11.123456789, y=22.987654321, width=333.246813579,
                  height=177.135792468, unit="mm"),
        dpi=301.234567,
        engine="board-reader",
        engine_version="2.7.3-fixture",
        model_hash="model-diagrama-456",
        confidence=0.876543219,
        band=ConfidenceBand.CONFIDENT,
        extracted_at=datetime(2026, 1, 3, 4, 5, 6, 789012,
                              tzinfo=timezone(timedelta(hours=5, minutes=30))),
        verified_by_human=True,
        out_of_model=True,
        note="posição inferida do recorte vetorial",
    )


def _proveniencia_partida() -> Provenance:
    # Imita caissa.ingest.pdf.importer.PdfImporter._provenance no GameScore.
    return Provenance(
        kind=SourceKind.PDF_TEXT_LAYER,
        document_path="livro-fonte.pdf",
        document_hash=FONTE_HASH,
        page_index=6,
        block_index=11,
        rect=Rect(x=4.111111111, y=8.222222222, width=190.333333333,
                  height=64.444444444, unit="in"),
        dpi=199.876543,
        engine="pdf-text-layer",
        engine_version="1.4-fixture",
        model_hash="text-layer-model-789",
        confidence=0.654321987,
        band=ConfidenceBand.UNRELIABLE,
        extracted_at=datetime(2026, 1, 4, 5, 6, 7, 890123,
                              tzinfo=timezone(timedelta(hours=1))),
        verified_by_human=True,
        out_of_model=True,
        note="partida transcrita da camada de texto",
    )


def _duvida() -> dict[str, object]:
    # Imita caissa.ingest.pdf.importer.PdfImporter._review_item e o recorte de OCR.
    return {
        "ini": 12,
        "fim": 29,
        "texto": "O cavalo encontra a casa crítica.",
        "proveniencia": Provenance(
            kind=SourceKind.OCR,
            document_path="livro-fonte.pdf",
            document_hash=FONTE_HASH,
            page_index=4,
            block_index=7,
            rect=Rect(x=13.123456789, y=27.987654321, width=301.246813579,
                      height=88.135792468, unit="px"),
            dpi=287.654321,
            engine="tesseract+glyph",
            engine_version="5.5.0-fixture",
            model_hash="model-bloco-123",
            confidence=0.234567891,
            band=ConfidenceBand.DOUBTFUL,
            extracted_at=datetime(2026, 1, 2, 3, 4, 5, 678901,
                                  tzinfo=timezone(timedelta(hours=-3))),
            verified_by_human=True,
            out_of_model=True,
            note="dúvida localizada no trecho",
        ),
    }


def _review_item() -> ReviewItem:
    # Imita caissa.ingest.pdf.importer.PdfImporter._review_item na fila do OCR.
    return ReviewItem(
        key="livro-fonte.pdf:p4:r1",
        document="livro-fonte.pdf",
        page_index=4,
        rect=(13.123456789, 27.987654321, 301.246813579, 88.135792468),
        kind="paragraph",
        decision="review",
        reasons=("glifo ambíguo", "confiança abaixo do limiar"),
        text="O cavalo encontra a casa crítica.",
        engine="tesseract+glyph",
        score=0.876543219,
        alternatives=(("ocr", "O cavalo encontra a casa crítica."),
                      ("glyph", "O cavalo encontra a casa crílica.")),
        low_confidence_words=("cavalo", "crítica"),
        disputed_tokens=(("t", "l"), ("í", "i")),
        legality={"unresolved": True, "token_index": 5},
        suggestion="confirmar a letra t",
    )


def _audit_entry() -> AuditEntry:
    # Imita caissa.ocr.review.ReviewQueue.decide, que cria o log de auditoria.
    return AuditEntry(
        key="livro-fonte.pdf:p4:r1",
        action=Action.EDIT,
        text="O cavalo encontra a casa crítica.",
        reviewer="crítica@fixture",
        at="2026-01-05T06:07:08+00:00",
        seconds=12.3456789,
        note="confirmado comparando o recorte",
    )


def _decided() -> Decided:
    # Imita caissa.ocr.review.ReviewQueue.decisions, que reduz o log a Decided.
    return Decided(
        page_index=4,
        rect=(13.123456789, 27.987654321, 301.246813579, 88.135792468),
        action=Action.EDIT,
        text="O cavalo encontra a casa crítica.",
        reviewer="crítica@fixture",
        at="2026-01-05T06:07:08+00:00",
    )


def _fonte_diagrama() -> DiagramSource:
    # Imita caissa.ingest.pdf.importer.PdfImporter._diagram_node na fonte do crop.
    return DiagramSource(
        kind=SourceKind.PDF_VECTOR,
        path="livro-fonte.pdf",
        content_hash=FONTE_HASH,
        page_index=4,
        rect=Rect(x=11.123456789, y=22.987654321, width=333.246813579,
                  height=177.135792468, unit="mm"),
        dpi=301.234567,
        rotation_degrees=1.23456789,
        image_hash="cd" * 32,
        extracted_at=datetime(2026, 1, 3, 4, 5, 6, 789012,
                              tzinfo=timezone(timedelta(hours=5, minutes=30))),
        extractor="diagram-cropper",
        extractor_version="0.8.1-fixture",
    )


def _reconhecimento() -> RecognitionResult:
    # Imita caissa.ingest.pdf.importer.PdfImporter._diagram_node e a leitura OCR.
    confidence = tuple(0.123456789 + index * 0.001234567 for index in range(64))
    return RecognitionResult(
        fen=FEN_MACHINE,
        per_square_confidence=confidence,
        overall_confidence=0.765432109,
        orientation_confidence=0.654321098,
        side_to_move_confidence=0.543210987,
        side_to_move_source="text-page-scope",
        path=RecognitionPath.HYBRID,
        model_name="square-classifier",
        model_version="9.8.7-fixture",
        model_hash="classifier-hash-123",
        recognised_at=datetime(2026, 1, 3, 4, 5, 6, 789012,
                               tzinfo=timezone(timedelta(hours=5, minutes=30))),
        duration_ms=123.456789,
        corners=(11.123456789, 22.987654321, 344.370370368, 22.987654321,
                 344.370370368, 200.123456789, 11.123456789, 200.123456789),
        alternatives=(
            FenCandidate(fen=FEN_CORRIGIDA, score=0.234567891, legal=False),
            FenCandidate(fen=FEN_MACHINE, score=0.345678912, legal=False),
        ),
        repairs=(
            SquareRepair(square="d6", recognised="Q", repaired="q",
                         reason="lado a jogar", confidence_before=0.456789123),
            SquareRepair(square="e4", recognised="", repaired="P",
                         reason="legalidade material", confidence_before=0.567891234),
        ),
        warnings=("duas casas abaixo do limiar", "rotação corrigida"),
    )


def _decisao_diagrama() -> DiagramDecision:
    # Imita caissa.ocr.diagram_decisions.record, chamada pela janela de revisão.
    return DiagramDecision(
        page_index=4,
        rect=(11.123456789, 22.987654321, 344.370370368, 200.123456789),
        fen=FEN_CORRIGIDA,
        side="w",
        decided_at="2026-01-06T07:08:09+00:00",
        reviewer="crítica@fixture",
        source="janela",
        note="lado corrigido pela revisão",
    )


def _documento() -> Document:
    # Imita caissa.ingest.pdf.importer.PdfImporter.import_document e o
    # caissa.core.model.visitor.walk em ordem de leitura.
    bloco_com_duvida = Paragraph(
        id=_id(2),
        provenance=_proveniencia_bloco(),
        content=(Text(id=_id(3), content="O cavalo encontra a casa crítica."),),
    )
    diagrama = Diagram(
        id=_id(4),
        provenance=_proveniencia_diagrama(),
        fen=FEN_CORRIGIDA,
        orientation=Orientation.BLACK,
        source=_fonte_diagrama(),
        recognition=_reconhecimento(),
        verified_by_human=True,
        stipulation="Mate em 3",
        anchor="diag-fixture-1",
        alt_text="Rei preto contra rei branco; posição corrigida.",
        move_context="após 24...Txf2",
    )
    bloco_sem_duvida = Paragraph(
        id=_id(5),
        provenance=Provenance(
            kind=SourceKind.PDF_TEXT_LAYER,
            document_path="livro-fonte.pdf",
            document_hash=FONTE_HASH,
            page_index=5,
            block_index=2,
            rect=Rect(x=2.345678901, y=3.456789012, width=120.567890123,
                      height=45.678901234, unit="pt"),
            dpi=180.123456,
            engine="pdf-reader",
            engine_version="3.2-fixture",
            model_hash="pdf-model-999",
            confidence=0.987654321,
            band=ConfidenceBand.CERTAIN,
            extracted_at=datetime(2026, 1, 7, 8, 9, 10, 111213,
                                  tzinfo=timezone.utc),
            verified_by_human=True,
            out_of_model=True,
            note="bloco limpo",
        ),
        content=(Text(id=_id(6), content="Bloco sem dúvida."),),
    )
    partida = GameScore(
        id=_id(7),
        provenance=_proveniencia_partida(),
        initial_fen=FEN_MACHINE,
        variant="chess960",
        initial_comment="Partida da fixture.",
        children=(MoveNode(id=_id(8), san="Ke3", ply=1),
                  MoveNode(id=_id(9), san="Kd6", ply=2)),
        title="Final de teste",
        annotator="crítica@fixture",
    )
    # Imita conteúdo autoral criado no editor, sem Provenance: não pode gerar linha.
    bloco_autoral = Paragraph(
        id=_id(10),
        content=(Text(id=_id(11), content="Nota autoral sem proveniência."),),
    )
    return Document(id=_id(1), body=(bloco_com_duvida, diagrama, bloco_sem_duvida,
                                     partida, bloco_autoral))


def entrada() -> dict[str, object]:
    """Retorna a entrada do escritor v2 e documenta suas chaves contratuais.

    Chaves do dicionário:
    ``documento`` é o :class:`Document` IR em ordem de leitura;
    ``cabecalho`` contém ``livro``, ``documento``, ``alvo``, ``formato_do_livro``,
    ``paginas`` e ``perfil``;
    ``blocos`` indexa por ``str(ir_id)`` e fornece ``folio``, ``duvidas`` e
    ``revisao`` (estado e decisões);
    ``diagramas`` indexa por ``str(ir_id)`` e fornece ``decisoes``;
    ``partidas`` indexa por ``str(ir_id)`` e reserva metadados de partida;
    ``gerado_em`` e ``commit_da_suite`` são os injetáveis normativos do apêndice.
    """

    documento = _documento()
    # Imita caissa.export.provenance.write_sidecar -> SidecarHeader.as_dict
    # para os metadados que export_book fornece ao exportador.
    blocos = {
        # Imita caissa.ingest.pdf.importer.PdfImporter.report.review_items e
        # caissa.ocr.review.ReviewQueue.decisions, indexados pelo IR do bloco.
        str(documento.body[0].id): {
            "folio": "5",
            "duvidas": (_duvida(),),
            "revisao": {
                "estado": "editada",
                "decisoes": (_review_item(), _audit_entry(), _decided()),
            },
        },
        str(documento.body[2].id): {
            "folio": "6",
            "duvidas": (),
            "revisao": {"estado": "sem_duvida", "decisoes": ()},
        },
    }
    # Imita caissa.ocr.diagram_decisions.record e o resultado aplicado por
    # caissa.ingest.pdf.importer.PdfImporter._diagram_node.
    diagramas = {str(documento.body[1].id): {"decisoes": (_decisao_diagrama(),)}}
    # Imita o GameScore que caissa.export.provenance.records_for recebe no
    # percurso de caissa.core.model.visitor.walk.
    partidas = {str(documento.body[3].id): {}}
    return {
        "documento": documento,
        "cabecalho": {
            "livro": {"sha256": FONTE_HASH, "nome": "livro-fonte.pdf"},
            "documento": {"caminho": Path("livro-fonte.pdf"), "hash": FONTE_HASH},
            "alvo": "Livro.epub",
            "formato_do_livro": "epub",
            "paginas": [4, 5, 6],
            "perfil": {"fecho": "editor", "revisao": "completa"},
        },
        "blocos": blocos,
        "diagramas": diagramas,
        "partidas": partidas,
        "gerado_em": "2026-01-01T00:00:00+00:00",
        "commit_da_suite": "fixture",
    }


def entrada_v1() -> Document:
    """A mesma árvore para o exportador v1, com rect da fonte como tupla.

    Imita a chamada de ``caissa.export.provenance.write_sidecar`` usada por
    ``caissa.export.book.export_book`` e preserva a forma sintética do teste
    atual: o ``DiagramSource.rect`` é uma tupla, não um ``Rect``.
    """

    documento = _documento()
    diagrama = documento.body[1]
    assert isinstance(diagrama, Diagram)
    source = diagrama.source
    assert isinstance(source.rect, Rect)
    source_tuple = (source.rect.x, source.rect.y, source.rect.width, source.rect.height)
    from dataclasses import replace

    return replace(documento, body=(documento.body[0], replace(diagrama,
                       source=replace(source, rect=source_tuple)), *documento.body[2:]))
