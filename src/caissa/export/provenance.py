"""The provenance sidecar of an exported book — A11 (ciclo 2), X4 of the analysis.

The IR keeps, per diagram, everything a reader of the EPUB/DOCX cannot see and a reviewer
needs: where the board was on the page (:class:`~caissa.core.model.DiagramSource`), the
perceptual hash of the crop, the classifier's identity, the confidence of every square, the
squares the legality solver changed, the runner-up readings, whether a person settled it
(:attr:`Diagram.verified_by_human`), and per game the position it was replayed from.  The
exporters print the board and lose the rest.

This writes it as a JSONL next to the book — ``<Livro>.proveniencia.jsonl`` — one header
line (document hash, suite commit, the book profile, the export target) and one line per
diagram and per game, keyed the way the trunk's PGN sidecar is keyed
(``p<page>:d<ordinal>`` in reading order, the identity the diagram panel and the A3
decisions use), with the IR node's ULID beside it for an exact match.  A key that repeats
is a defect and is refused (:class:`ProvenanceCollision`): two diagrams with the same
position on two pages are two records, never one.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.core.model import Diagram, Document, GameScore, Rect

__all__ = [
    "SIDECAR_SUFFIX",
    "ProvenanceCollision",
    "SidecarHeader",
    "read_sidecar",
    "records_for",
    "sidecar_path",
    "write_sidecar",
]

SIDECAR_SUFFIX = ".proveniencia.jsonl"
VERSION = 1


class ProvenanceCollision(ValueError):
    """Two sidecar lines share a key: two diagrams would become one."""


def sidecar_path(output_path: Path | str) -> Path:
    """``Livro.epub`` → ``Livro.proveniencia.jsonl`` in the same folder."""
    out = Path(output_path)
    return out.with_name(out.stem + SIDECAR_SUFFIX)


@dataclass(slots=True)
class SidecarHeader:
    document_path: str = ""
    document_hash: str = ""
    target: str = ""
    format: str = ""
    suite_commit: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    pages: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": "header", "version": VERSION, "document_path": self.document_path,
                "document_hash": self.document_hash, "target": self.target, "format": self.format,
                "suite_commit": self.suite_commit, "profile": dict(self.profile),
                "pages": list(self.pages),
                "exported_at": datetime.now(UTC).isoformat(timespec="seconds")}


def _walk(document: Document) -> Iterator[Any]:
    """Every node of the tree in document order (:func:`caissa.core.model.visitor.walk`)."""
    from caissa.core.model.visitor import walk

    for _path, node in walk(document):
        yield node


def _rect_record(rect: Any) -> dict[str, Any] | list[Any] | None:
    """A rectangle as the sidecar writes it.

    The IR's :class:`~caissa.core.model.Rect` -- what every real import stores -- is not a
    sequence, so it is written by name, unit included; ``list()`` of it raised and the whole
    sidecar went missing.  A bare tuple (the synthetic items of older callers) stays the
    list it always was.
    """
    if isinstance(rect, Rect):
        return {"x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height,
                "unit": rect.unit}
    return list(rect) if rect else None


def _provenance_dict(provenance: Any) -> dict[str, Any] | None:
    if provenance is None:
        return None
    return {
        "kind": str(getattr(provenance, "kind", "") or ""),
        "page_index": getattr(provenance, "page_index", None),
        "rect": _rect_record(getattr(provenance, "rect", None)),
        "engine": getattr(provenance, "engine", None),
        "engine_version": getattr(provenance, "engine_version", None),
        "model_hash": getattr(provenance, "model_hash", None),
        "confidence": getattr(provenance, "confidence", None),
        "band": str(getattr(provenance, "band", "") or ""),
        "verified_by_human": bool(getattr(provenance, "verified_by_human", False)),
        "note": getattr(provenance, "note", None),
    }


def records_for(document: Document) -> list[dict[str, Any]]:
    """One record per :class:`Diagram` and per :class:`GameScore` of the document."""
    records: list[dict[str, Any]] = []
    per_page: dict[int | None, int] = {}
    for block in _walk(document):
        if isinstance(block, Diagram):
            source = block.source
            page = source.page_index if source is not None else None
            ordinal = per_page.get(page, 0) + 1
            per_page[page] = ordinal
            recognition = block.recognition
            records.append({
                "kind": "diagram",
                "key": f"p{page if page is not None else '?'}:d{ordinal}",
                "id": str(block.id),
                "page_index": page,
                "rect": _rect_record(source.rect) if source is not None else None,
                "image_hash": source.image_hash if source is not None else None,
                "content_hash": source.content_hash if source is not None else None,
                "dpi": source.dpi if source is not None else None,
                "fen": block.fen,
                "orientation": str(block.orientation),
                "verified_by_human": bool(block.verified_by_human),
                "recognition": {
                    "fen": recognition.fen,
                    "path": str(recognition.path),
                    "model_name": recognition.model_name,
                    "model_version": recognition.model_version,
                    "model_hash": recognition.model_hash,
                    "overall_confidence": recognition.overall_confidence,
                    "side_to_move_source": recognition.side_to_move_source,
                    "per_square_confidence": [round(float(c), 4) for c in recognition.per_square_confidence],
                    "repairs": [{"square": r.square, "recognised": r.recognised, "repaired": r.repaired,
                                 "reason": r.reason, "confidence_before": r.confidence_before}
                                for r in recognition.repairs],
                    "alternatives": [{"fen": a.fen, "score": a.score, "legal": a.legal}
                                     for a in recognition.alternatives],
                    "warnings": list(recognition.warnings),
                },
                "provenance": _provenance_dict(block.provenance),
                "stipulation": block.stipulation,
            })
        elif isinstance(block, GameScore):
            provenance = block.provenance
            page = getattr(provenance, "page_index", None)
            ordinal = per_page.get(("game", page), 0) + 1
            per_page[("game", page)] = ordinal  # type: ignore[index]
            records.append({
                "kind": "game",
                "key": f"p{page if page is not None else '?'}:g{ordinal}",
                "id": str(block.id),
                "page_index": page,
                "initial_fen": block.initial_fen,
                "moves": _count_moves(block),
                "provenance": _provenance_dict(provenance),
            })
    return records


def _count_moves(score: GameScore) -> int:
    count = 0
    stack = list(score.children)
    while stack:
        node = stack.pop()
        count += 1
        stack.extend(getattr(node, "children", ()))
    return count


def verify(records: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    by_key: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if record.get("kind") not in ("diagram", "game"):
            continue
        key = str(record.get("key", ""))
        if not key:
            raise ProvenanceCollision("linha sem chave")
        if key in by_key:
            raise ProvenanceCollision(
                f"chave {key!r} repetida: {by_key[key].get('id')} e {record.get('id')} virariam um só")
        by_key[key] = record
    return by_key


def _suite_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parents[3], timeout=10, check=False)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def write_sidecar(document: Document, output_path: Path | str, *, format_name: str = "",
                  pages: Iterable[int] = (), profile: Mapping[str, Any] | None = None,
                  key_of: Any = None) -> Path:
    """Write the sidecar next to ``output_path`` and return its path.

    ``key_of`` replaces the key (the measurement's sabotage keys by FEN, so that two equal
    positions collide and the collision is refused).
    """
    first_source = next((b.source for b in _walk(document) if isinstance(b, Diagram) and b.source is not None), None)
    first_provenance = next((b.provenance for b in _walk(document) if getattr(b, "provenance", None) is not None), None)
    header = SidecarHeader(
        document_path=str((first_source.path if first_source is not None else None)
                          or getattr(first_provenance, "document_path", None) or ""),
        document_hash=str((first_source.content_hash if first_source is not None else None)
                          or getattr(first_provenance, "document_hash", None) or ""),
        target=str(output_path), format=format_name, suite_commit=_suite_commit(),
        profile=dict(profile or {}), pages=sorted(pages),
    )
    records = records_for(document)
    if key_of is not None:
        for record in records:
            record["key"] = str(key_of(record))
    verify(records)
    destination = sidecar_path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header.as_dict(), ensure_ascii=False) + "\n")
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return destination


def read_sidecar(path: Path | str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    header: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            line = json.loads(raw)
            if line.get("kind") == "header":
                header = line
            else:
                records.append(line)
    return header, dict(verify(records))
