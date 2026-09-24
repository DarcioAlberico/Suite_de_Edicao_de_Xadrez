"""Gera as fixtures douradas sem importar nem usar um escritor v2.

O serializador abaixo é a implementação independente da regra do Apêndice C:
usa ``dataclasses.fields`` para os dez objetos, não chama ``as_dict`` e só usa
o exportador v1 existente para produzir ``v1_de_hoje.jsonl``.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from caissa.core.model import (
    Diagram,
    Document,
    FenCandidate,
    RecognitionResult,
    Rect,
    SquareRepair,
    Provenance,
    DiagramSource,
    GameScore,
    Paragraph,
)
from caissa.core.model.registry import tag_for_class
from caissa.core.model.visitor import walk
from caissa.ocr.diagram_decisions import DiagramDecision
from caissa.ocr.review import AuditEntry, Decided, ReviewItem

from entrada import entrada, entrada_v1


FIXTURE_DIR = Path(__file__).resolve().parent
FIXED_GENERATED_AT = "2026-01-01T00:00:00+00:00"
FIXED_COMMIT = "fixture"

SIDEcar_CLASSES = (
    Provenance,
    Rect,
    DiagramSource,
    RecognitionResult,
    FenCandidate,
    SquareRepair,
    ReviewItem,
    AuditEntry,
    Decided,
    DiagramDecision,
)
REGISTERED_CLASSES = {Provenance, Rect, DiagramSource, RecognitionResult,
                      FenCandidate, SquareRepair}


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _tag_for_class(cls: type[Any]) -> str:
    if cls in REGISTERED_CLASSES:
        return tag_for_class(cls)
    return _snake_case(cls.__name__)


def _json_value(value: Any) -> Any:
    """Converte somente os tipos admitidos pelo contrato canônico."""

    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        cls = type(value)
        if cls not in SIDEcar_CLASSES:
            raise TypeError(f"dataclass não serializável na fixture: {cls.__name__}")
        obj: dict[str, Any] = {"type": _tag_for_class(cls)}
        for field in fields(value):
            obj[field.name] = _json_value(getattr(value, field.name))
        return obj
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"valor não serializável na fixture: {type(value).__name__}")


def _line(obj: Any) -> str:
    return json.dumps(_json_value(obj), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def _schema() -> dict[str, list[str]]:
    """Esquema completo, em ordem de fields(), das dez classes."""

    return {_tag_for_class(cls): [field.name for field in fields(cls)]
            for cls in SIDEcar_CLASSES}


def _header(data: dict[str, Any]) -> dict[str, Any]:
    cabecalho = data["cabecalho"]
    return {
        "tipo": "cabecalho",
        "formato": "caissa.proveniencia",
        "versao": 2,
        "livro": cabecalho["livro"],
        "documento": cabecalho["documento"],
        "alvo": cabecalho["alvo"],
        "formato_do_livro": cabecalho["formato_do_livro"],
        "paginas": cabecalho["paginas"],
        "perfil": cabecalho["perfil"],
        "gerado_em": data["gerado_em"],
        "gerador": {"programa": "caissa", "commit_da_suite": data["commit_da_suite"]},
        "esquema": _schema(),
    }


def _id_v2(page_index: int, suffix: str, ordinal: int) -> str:
    # R2.7: o id público é base 1; pagina0/chave_v1 continuam base 0.
    return f"p{page_index + 1}-{suffix}{ordinal if suffix else ordinal}"


def _count_moves(score: GameScore) -> int:
    count = 0
    stack = list(score.children)
    while stack:
        node = stack.pop()
        count += 1
        stack.extend(getattr(node, "children", ()))
    return count


def v2_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Produz registros nativos v2 em pré-ordem de ``visitor.walk``."""

    document: Document = data["documento"]
    block_ordinals: dict[int, int] = {}
    diagram_ordinals: dict[int, int] = {}
    game_ordinals: dict[int, int] = {}
    records: list[dict[str, Any]] = []
    for _path, node in walk(document):
        ir_id = str(node.id)
        if isinstance(node, Paragraph) and node.provenance is not None:
            page = node.provenance.page_index
            assert page is not None
            block_ordinals[page] = block_ordinals.get(page, 0) + 1
            metadata = data["blocos"][ir_id]
            records.append({
                "tipo": "bloco",
                "id": _id_v2(page, "", block_ordinals[page]),
                "ir_id": ir_id,
                "pagina0": page,
                "folio": metadata["folio"],
                "proveniencia": node.provenance,
                "duvidas": tuple({
                    "ini": doubt["ini"],
                    "fim": doubt["fim"],
                    "texto": doubt["texto"],
                    "proveniencia": doubt["proveniencia"],
                } for doubt in metadata["duvidas"]),
                "revisao": metadata["revisao"],
                "extras_v1": {},
            })
        elif isinstance(node, Diagram) and node.provenance is not None:
            source = node.source
            page = source.page_index
            assert page is not None
            diagram_ordinals[page] = diagram_ordinals.get(page, 0) + 1
            metadata = data["diagramas"][ir_id]
            ordinal = diagram_ordinals[page]
            records.append({
                "tipo": "diagrama",
                "id": _id_v2(page, "d", ordinal),
                "chave_v1": f"p{page}:d{ordinal}",
                "ir_id": ir_id,
                "fen": node.fen,
                "orientacao": node.orientation,
                "estipulacao": node.stipulation,
                "verificado_por_pessoa": node.verified_by_human,
                "fonte": source,
                "reconhecimento": node.recognition,
                "proveniencia": node.provenance,
                "decisoes": metadata["decisoes"],
                "extras_v1": {},
            })
        elif isinstance(node, GameScore) and node.provenance is not None:
            page = node.provenance.page_index
            assert page is not None
            game_ordinals[page] = game_ordinals.get(page, 0) + 1
            ordinal = game_ordinals[page]
            records.append({
                "tipo": "partida",
                "id": _id_v2(page, "g", ordinal),
                "chave_v1": f"p{page}:g{ordinal}",
                "ir_id": ir_id,
                "fen_inicial": node.initial_fen,
                "lances": _count_moves(node),
                "proveniencia": node.provenance,
                "extras_v1": {},
            })
    return records


def write_v2(path: Path, data: dict[str, Any]) -> None:
    lines = [_header(data), *v2_records(data)]
    path.write_text("".join(_line(item) for item in lines), encoding="utf-8", newline="")


def _rect_from_v1(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return {
            "type": "rect",
            "x": value["x"],
            "y": value["y"],
            "width": value["width"],
            "height": value["height"],
            "unit": value.get("unit", "pt"),
        }
    x, y, width, height = value
    return {"type": "rect", "x": x, "y": y, "width": width,
            "height": height, "unit": "pt"}


def _provenance_from_v1(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "type": "provenance",
        "kind": value.get("kind"),
        "document_path": None,
        "document_hash": None,
        "page_index": value.get("page_index"),
        "block_index": None,
        "rect": _rect_from_v1(value.get("rect")),
        "dpi": None,
        "engine": value.get("engine"),
        "engine_version": value.get("engine_version"),
        "model_hash": value.get("model_hash"),
        "confidence": value.get("confidence"),
        "band": value.get("band"),
        "extracted_at": None,
        "verified_by_human": value.get("verified_by_human", False),
        "out_of_model": False,
        "note": value.get("note"),
    }


def _source_from_v1(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "diagram_source",
        "kind": None,
        "path": None,
        "content_hash": record.get("content_hash"),
        "page_index": record.get("page_index"),
        "rect": _rect_from_v1(record.get("rect")),
        "dpi": record.get("dpi"),
        "rotation_degrees": None,
        "image_hash": record.get("image_hash"),
        "extracted_at": None,
        "extractor": None,
        "extractor_version": None,
    }


def _recognition_from_v1(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "recognition_result",
        "fen": value.get("fen"),
        "per_square_confidence": value.get("per_square_confidence"),
        "overall_confidence": value.get("overall_confidence"),
        "orientation_confidence": None,
        "side_to_move_confidence": None,
        "side_to_move_source": value.get("side_to_move_source"),
        "path": value.get("path"),
        "model_name": value.get("model_name"),
        "model_version": value.get("model_version"),
        "model_hash": value.get("model_hash"),
        "recognised_at": None,
        "duration_ms": None,
        "corners": [],
        "alternatives": [
            {"type": "fen_candidate", "fen": item.get("fen"),
             "score": item.get("score"), "legal": item.get("legal")}
            for item in value.get("alternatives", [])
        ],
        "repairs": [
            {"type": "square_repair", "square": item.get("square"),
             "recognised": item.get("recognised"), "repaired": item.get("repaired"),
             "reason": item.get("reason"),
             "confidence_before": item.get("confidence_before")}
            for item in value.get("repairs", [])
        ],
        "warnings": value.get("warnings"),
    }


def _migrated_record(record: dict[str, Any]) -> dict[str, Any]:
    kind = record["kind"]
    page = record.get("page_index")
    ordinal = int(record["key"].split(":")[-1][1:])
    suffix = "d" if kind == "diagram" else "g"
    known = {
        "kind", "key", "id", "page_index", "rect", "image_hash", "content_hash",
        "dpi", "fen", "orientation", "verified_by_human", "recognition", "provenance",
        "stipulation", "initial_fen", "moves",
    }
    extras = {key: value for key, value in record.items() if key not in known}
    extras["kind"] = record["kind"]
    if kind == "diagram":
        return {
            "tipo": "diagrama",
            "id": f"p{page + 1}-d{ordinal}",
            "chave_v1": record["key"],
            "ir_id": record["id"],
            "fen": record["fen"],
            "orientacao": record["orientation"],
            "estipulacao": record["stipulation"],
            "verificado_por_pessoa": record["verified_by_human"],
            "fonte": _source_from_v1(record),
            "reconhecimento": _recognition_from_v1(record["recognition"]),
            "proveniencia": _provenance_from_v1(record["provenance"]),
            "decisoes": [],
            "extras_v1": extras,
        }
    return {
        "tipo": "partida",
        "id": f"p{page + 1}-g{ordinal}",
        "chave_v1": record["key"],
        "ir_id": record["id"],
        "fen_inicial": record["initial_fen"],
        "lances": record["moves"],
        "proveniencia": _provenance_from_v1(record["provenance"]),
        "extras_v1": extras,
    }


def migrate_v1(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Migração independente conforme a tabela do Apêndice C."""

    header = lines[0]
    document_path = header.get("document_path")
    return [{
        "tipo": "cabecalho",
        "formato": "caissa.proveniencia",
        "versao": 2,
        "livro": {"sha256": header.get("document_hash"),
                  "nome": Path(document_path).name if document_path else ""},
        "documento": {"caminho": document_path, "hash": header.get("document_hash")},
        "alvo": header.get("target"),
        "formato_do_livro": header.get("format"),
        "paginas": header.get("pages"),
        "perfil": header.get("profile"),
        "gerado_em": header.get("exported_at"),
        "gerador": {"programa": "caissa", "commit_da_suite": header.get("suite_commit")},
        "esquema": _schema(),
    }, *(_migrated_record(record) for record in lines[1:])]


def _write_v1_with_product_exporter(data: dict[str, Any], path: Path) -> None:
    """Executa write_sidecar v1, injetando os dois valores variáveis da fixture."""

    import caissa.export.provenance as exporter_v1

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            fixed = datetime(2026, 1, 1, tzinfo=UTC)
            return fixed.astimezone(tz) if tz is not None else fixed.replace(tzinfo=None)

    old_datetime = exporter_v1.datetime
    old_commit = exporter_v1._suite_commit
    exporter_v1.datetime = FixedDateTime
    exporter_v1._suite_commit = lambda: FIXED_COMMIT
    try:
        with tempfile.TemporaryDirectory(dir=FIXTURE_DIR) as temp_dir:
            import os

            old_cwd = Path.cwd()
            os.chdir(temp_dir)
            try:
                sidecar = exporter_v1.write_sidecar(
                    data["documento"], Path("Livro.epub"),
                    format_name=data["cabecalho"]["formato_do_livro"],
                    pages=data["cabecalho"]["paginas"],
                    profile=data["cabecalho"]["perfil"],
                )
                path.write_bytes(sidecar.read_bytes())
            finally:
                os.chdir(old_cwd)
    finally:
        exporter_v1.datetime = old_datetime
        exporter_v1._suite_commit = old_commit


def write_all() -> None:
    data = entrada()
    write_v2(FIXTURE_DIR / "v2_completo.jsonl", data)
    v1_path = FIXTURE_DIR / "v1_de_hoje.jsonl"
    _write_v1_with_product_exporter({**data, "documento": entrada_v1()}, v1_path)
    v1_lines = [json.loads(line) for line in v1_path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    migrated = migrate_v1(v1_lines)
    (FIXTURE_DIR / "v1_migrado_esperado.jsonl").write_text(
        "".join(_line(item) for item in migrated), encoding="utf-8", newline="")


if __name__ == "__main__":
    write_all()

