"""The reviewer's diagram corrections, kept and applied on import (OCR_UI ciclo 2, passo A3).

``docs/OCR_UI_ANALISE_C2.md`` §6.2: the window lets the reviewer correct a
position and save it, and nothing downstream reads that.  ``export_book``
re-imports the PDF and applies only :class:`~caissa.ocr.review.ReviewDecisions`
(the OCR text regions); the corrected FEN stays in ``labels.csv`` and the
EPUB ships the machine's reading.  This module is the diagram counterpart of
``ReviewDecisions``, built to the contract of ``OCR_UI_ROADMAP_C2.md`` §1.1:

* :class:`DiagramDecision` -- one corrected position: page, rectangle in
  **page points**, full FEN, side, when, who;
* :class:`DiagramDecisions` -- the book's decisions, one per (page, box),
  matched by IoU ≥ 0,5 exactly as ``ReviewDecisions.match`` does, saved as
  JSON next to the labelling project (``labeling/diagramas/<book>.json``,
  the same slug as ``labeling/revisao/<book>.json``);
* :func:`record` -- load-or-create, add, save: the one call the trunk's
  result panel makes when the reviewer saves a position (guarded there by
  "is ``caissa`` importable", like the suite's tabs).

The importer applies them in ``_diagram_node``
(``PdfImportOptions.diagram_decisions``): the :class:`~caissa.core.model.Diagram`
gets the decision's FEN and ``provenance.verified_by_human``, while
``recognition.fen`` keeps the machine's reading -- the pair the docstring of
``RecognitionResult.fen`` promises, and what makes the correction reviewable.
``export_book`` loads them with :meth:`DiagramDecisions.for_pdf` when the
caller passed none, as it already does for ``ReviewDecisions``.

Where the file lives is a parameter or the environment, never only a
constant: the audit harness (``caissa.ui.audit.percurso``) and the tests
point :data:`ENV_ROOT` at a temporary folder so that a gate never writes into
the real ``labeling/``.
"""

from __future__ import annotations

from collections.abc import Iterator

import time

import contextlib

import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "ENV_ROOT",
    "IOU_FLOOR",
    "DiagramDecision",
    "DiagramDecisions",
    "decisions_dir",
    "decisions_path",
    "record",
]

RectT = tuple[float, float, float, float]

IOU_FLOOR = 0.5
"""From this overlap up a decision and a detected box are the same diagram
(``ReviewDecisions.IOU_FLOOR``)."""

ENV_ROOT = "DIAGRAM_DECISIONS_DIR"
"""Environment variable that relocates the decisions folder (harnesses and tests).

Not under the ``CAISSA_`` prefix on purpose: :mod:`caissa.core.config` owns
that namespace (``CAISSA_<SECTION>__<FIELD>``) and refuses the process's
settings -- and with them the classifier -- when it meets an unknown name.
"""

SUBFOLDER = "diagramas"
"""Under the labelling project, next to ``revisao/`` (the OCR text decisions)."""


@dataclass(frozen=True, slots=True)
class DiagramDecision:
    """One corrected position, placed on the page.

    Attributes:
        page_index: Zero-based, as ``ReviewDecisions``.
        rect: ``page.rect`` in **points** ``(x0, y0, x1, y1)`` -- the window
            converts its pixel box with ``72 / dpi`` before recording.
        fen: Full FEN (placement, side, castling, en passant, counters).
        side: ``"w"`` or ``"b"``; kept apart from ``fen`` so a caller that
            only corrected the side can say so.
        decided_at: ISO-8601 UTC.
        reviewer: Who, when known.
        source: Who recorded it: ``"janela"`` (the trunk's window),
            ``"rotulagem"``, ``"arnes"``...
        note: Free text.
    """

    page_index: int
    rect: RectT
    fen: str
    side: str
    decided_at: str
    reviewer: str = ""
    source: str = "janela"
    note: str = ""

    def __post_init__(self) -> None:
        if self.side not in ("w", "b"):
            raise ValueError(f"lado a jogar tem de ser 'w' ou 'b'; recebido {self.side!r}")
        if len(self.rect) != 4:  # noqa: PLR2004 - a rectangle has four numbers
            raise ValueError(
                f"rect precisa de quatro números (x0, y0, x1, y1); recebido {self.rect!r}"
            )
        if not self.fen.strip():
            raise ValueError("a decisão precisa de uma FEN")

    @property
    def placement(self) -> str:
        return self.fen.split()[0]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rect"] = list(self.rect)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagramDecision:
        return cls(
            page_index=int(data["page_index"]),
            rect=tuple(float(v) for v in data["rect"]),  # type: ignore[arg-type]
            fen=str(data["fen"]),
            side=str(data.get("side") or _side_of(str(data["fen"]))),
            decided_at=str(data.get("decided_at", "")),
            reviewer=str(data.get("reviewer", "")),
            source=str(data.get("source", "janela")),
            note=str(data.get("note", "")),
        )

    @classmethod
    def now(
        cls,
        page_index: int,
        rect: RectT,
        fen: str,
        *,
        side: str | None = None,
        reviewer: str = "",
        source: str = "janela",
        note: str = "",
    ) -> DiagramDecision:
        """A decision stamped with the current UTC time; ``side`` defaults to the FEN's."""
        return cls(
            page_index=int(page_index),
            rect=tuple(float(v) for v in rect),  # type: ignore[arg-type]
            fen=fen.strip(),
            side=side or _side_of(fen),
            decided_at=datetime.now(UTC).isoformat(timespec="seconds"),
            reviewer=reviewer,
            source=source,
            note=note,
        )


def _side_of(fen: str) -> str:
    fields = fen.split()
    return fields[1] if len(fields) > 1 and fields[1] in ("w", "b") else "w"


def _iou(a: RectT, b: RectT) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass(frozen=True, slots=True)
class DiagramDecisions:
    """A book's corrected positions, one per (page, box), matched by overlap on import."""

    document: str = ""
    items: tuple[DiagramDecision, ...] = ()

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def for_page(self, page_index: int) -> list[DiagramDecision]:
        return [d for d in self.items if d.page_index == page_index]

    def match(
        self, page_index: int, rect: RectT, *, iou: float = IOU_FLOOR
    ) -> DiagramDecision | None:
        """The decision on this page whose box overlaps ``rect`` most, at ``iou`` or above."""
        best, best_iou = None, 0.0
        for decision in self.for_page(page_index):
            overlap = _iou(decision.rect, rect)
            if overlap > best_iou:
                best, best_iou = decision, overlap
        return best if best is not None and best_iou >= iou else None

    def add(self, decision: DiagramDecision) -> DiagramDecisions:
        """A copy with ``decision`` in, replacing the one it overlaps (same page, IoU ≥ 0,5)."""
        kept = tuple(
            d
            for d in self.items
            if d.page_index != decision.page_index or _iou(d.rect, decision.rect) < IOU_FLOOR
        )
        return replace(self, items=(*kept, decision))

    def apply(self, hit: Any, page_index: int) -> Any:
        """``hit`` with the decision's FEN and side, ``method="human"`` -- or ``hit`` untouched.

        ``hit`` is a :class:`caissa.ingest.pdf.importer.DiagramHit` (imported
        lazily: this module must not pull the importer in).  The importer
        itself does **not** use this -- it keeps the machine's reading in
        ``recognition.fen`` and puts the decision on the ``Diagram`` -- but a
        consumer that only wants "the position as the reviewer left it" does.
        """
        decision = self.match(int(page_index), tuple(hit.box))  # type: ignore[arg-type]
        if decision is None:
            return hit
        from caissa.core.model import RecognitionPath

        return replace(
            hit,
            fen=decision.fen,
            confidence=1.0,
            path=RecognitionPath.MANUAL,
            method="human",
            square_confidences=(1.0,) * 64,
            repairs=(),
            alternatives=(),
            orientation_ambiguous=False,
            orientation_reason="",
        )

    def as_dict(self) -> dict[str, Any]:
        return {"document": self.document, "items": [d.as_dict() for d in self.items]}

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(target)
        return target

    @classmethod
    def load(cls, path: Path | str) -> DiagramDecisions:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            document=str(data.get("document", "")),
            items=tuple(DiagramDecision.from_dict(e) for e in data.get("items", ())),
        )

    @classmethod
    def for_pdf(
        cls, pdf_path: Path | str, *, root: Path | str | None = None
    ) -> DiagramDecisions | None:
        """The decisions saved for this book, or ``None`` when nobody corrected a diagram."""
        path = decisions_path(pdf_path, root=root)
        return cls.load(path) if path.is_file() else None


def decisions_dir(root: Path | str | None = None) -> Path:
    """Where the decisions live: ``root``, else :data:`ENV_ROOT`, else ``labeling/diagramas``."""
    if root is not None:
        return Path(root)
    from_env = os.environ.get(ENV_ROOT, "")
    if from_env:
        return Path(from_env)
    from caissa.ocr.labeling.helpers import default_project_dir

    return default_project_dir() / SUBFOLDER


def decisions_path(pdf_path: Path | str, *, root: Path | str | None = None) -> Path:
    """``<decisions_dir>/<book>.json``, the slug ``ReviewDecisions`` uses (the PDF's stem)."""
    return decisions_dir(root) / (Path(pdf_path).stem + ".json")


def record(
    pdf_path: Path | str, decision: DiagramDecision, *, root: Path | str | None = None
) -> Path:
    """Load-or-create the book's decisions, add ``decision``, save.  Returns the file.

    This is the function the trunk's window calls when the reviewer saves a
    position; the window guards the call with "is ``caissa`` importable".
    """
    path = decisions_path(pdf_path, root=root)
    # Load-add-save under a lock file: two windows (or the window and an
    # audit harness) recording on the same book must not lose each other's
    # decision.  ``O_EXCL`` is atomic on every platform; a lock older than
    # a minute is a crash, not a writer.
    with _locked(path):
        current = DiagramDecisions.load(path) if path.is_file() else DiagramDecisions()
        if not current.document:
            current = replace(current, document=Path(pdf_path).name)
        return current.add(decision).save(path)


@contextlib.contextmanager
def _locked(path: Path, *, timeout_s: float = 10.0, stale_s: float = 60.0) -> Iterator[None]:
    lock = path.with_suffix(path.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_s:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError(f"decisões de {path.name} presas por outro processo ({lock})")
            time.sleep(0.05)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)
