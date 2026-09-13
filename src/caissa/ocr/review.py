"""The review queue — Sol §SOL-11, without the window.

The reviewer's job is to correct doubtful spans, not to reread the book.
This module is the model behind that job: it takes what the importer
already knows (Sol §SOL-10's review items and traces), orders it by risk,
gives each item its crop, its best reading, the alternatives and the
reason for the doubt, records every human decision with who, when and how
long, and exports the decisions in the shapes calibration (SOL-4) and the
benchmark (SOL-0) consume — with one guard: **a decision on a page of the
blind partition never leaves the queue as training data**.

There is no Qt here on purpose.  The F9 shell is not in this repository
yet; a widget written blind would be a second design to throw away.  What
the widget will need — a list of items, a crop for each, three actions, an
audit log, a timer — is all here and testable, and it is what the batch
importer's report can already write to disk as JSON.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .golden import Partition, partition_for

__all__ = [
    "Action",
    "AuditEntry",
    "ReviewItem",
    "ReviewQueue",
    "blind_guard",
]

RectT = tuple[float, float, float, float]


class Action(StrEnum):
    ACCEPT = "accept"          # the best reading is right
    EDIT = "edit"              # the reviewer typed the text
    KEEP_IMAGE = "keep_image"  # leave the region as a picture
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """One doubtful region, everything the reviewer needs on one screen."""

    key: str                              # "<document>:p<page>:r<order>"
    document: str
    page_index: int
    rect: RectT                           # page points
    kind: str
    decision: str                         # "review" | "abstained"
    reasons: tuple[str, ...]
    text: str
    engine: str
    score: float
    alternatives: tuple[tuple[str, str], ...] = ()      # (source, text)
    low_confidence_words: tuple[str, ...] = ()
    disputed_tokens: tuple[tuple[str, str], ...] = ()   # (chosen, alternative)
    legality: dict[str, Any] = field(default_factory=dict)
    #: A suggestion from a model that must never be applied by itself.
    suggestion: str = ""

    @property
    def risk(self) -> float:
        """Higher first: abstentions, then low scores, then legality trouble."""
        base = 1.0 if self.decision == "abstained" else 0.5
        trouble = 0.2 if self.legality.get("unresolved") else 0.0
        return base + trouble + (1.0 - min(1.0, self.score)) * 0.3

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "document": self.document, "page_index": self.page_index,
            "rect": list(self.rect), "kind": self.kind, "decision": self.decision,
            "reasons": list(self.reasons), "text": self.text, "engine": self.engine,
            "score": round(self.score, 4),
            "alternatives": [list(a) for a in self.alternatives],
            "low_confidence_words": list(self.low_confidence_words),
            "disputed_tokens": [list(d) for d in self.disputed_tokens],
            "legality": dict(self.legality), "suggestion": self.suggestion,
        }


@dataclass(frozen=True, slots=True)
class AuditEntry:
    key: str
    action: Action
    text: str
    reviewer: str
    at: str
    seconds: float
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "action": str(self.action), "text": self.text,
                "reviewer": self.reviewer, "at": self.at, "seconds": round(self.seconds, 2),
                "note": self.note}


#: Decides whether a page belongs to the blind partition.  The default maps
#: ``(document, page)`` onto the golden manifest's id scheme for PDF items;
#: a caller with a manifest passes its own predicate.
BlindGuard = Callable[[str, int], bool]


def blind_guard(item_ids: Iterable[str] = ()) -> BlindGuard:
    """A guard from the golden manifest's PDF item ids (``real:<book>:<page>:…``)."""
    blind_pages: set[tuple[str, int]] = set()
    for item_id in item_ids:
        parts = item_id.split(":")
        if len(parts) >= 3 and parts[0] == "real" and partition_for(item_id) is Partition.BLIND:
            try:
                blind_pages.add((parts[1], int(parts[2])))
            except ValueError:
                continue

    def guard(document: str, page: int) -> bool:
        return any(document[:24] == book and page == index for book, index in blind_pages)

    return guard


@dataclass(slots=True)
class ReviewQueue:
    """Items ordered by risk, with the audit trail of what was decided."""

    items: list[ReviewItem] = field(default_factory=list)
    log: list[AuditEntry] = field(default_factory=list)
    reviewer: str = ""
    #: Crop provider: ``(document, page_index, rect) -> PNG bytes`` when the
    #: caller can render; ``None`` keeps the queue usable without a renderer.
    render: Callable[[str, int, RectT], bytes] | None = None
    blind: BlindGuard = field(default_factory=lambda: (lambda document, page: False))
    _opened: dict[str, float] = field(default_factory=dict)
    _page_seconds: dict[tuple[str, int], float] = field(default_factory=dict)

    # -- building ---------------------------------------------------------- #

    @classmethod
    def from_import(cls, report: Any, *, document: str, reviewer: str = "",
                    render: Callable[[str, int, RectT], bytes] | None = None,
                    blind: BlindGuard | None = None) -> "ReviewQueue":
        """From an :class:`~caissa.ingest.pdf.importer.ImportReport`.

        Only ``REVIEW`` and ``ABSTAINED`` regions are queued (Sol §SOL-11,
        "mostrar apenas regiões REVIEW e ABSTAINED por padrão").
        """
        queue = cls(reviewer=reviewer, render=render)
        if blind is not None:
            queue.blind = blind
        traces = getattr(report, "ocr_traces", {}) or {}
        for n, item in enumerate(getattr(report, "review_items", ())):
            trace = _region_trace(traces.get(item.page_index), item.rect, item.kind)
            queue.items.append(ReviewItem(
                key=f"{document}:p{item.page_index}:r{n}", document=document,
                page_index=item.page_index, rect=tuple(item.rect), kind=item.kind,
                decision=item.decision, reasons=tuple(item.reasons), text=item.text,
                engine=item.engine, score=float(item.score),
                alternatives=tuple((a, b) for a, b in item.alternatives),
                low_confidence_words=tuple(trace.get("flagged_words", ())),
                disputed_tokens=tuple((t["text"], t["alternative"])
                                      for t in trace.get("disputed", ())),
                legality=dict(trace.get("legality", {})),
            ))
        queue.items.sort(key=lambda i: (-i.risk, i.page_index, i.rect[1]))
        return queue

    # -- viewing ----------------------------------------------------------- #

    def pending(self) -> list[ReviewItem]:
        done = {entry.key for entry in self.log if entry.action is not Action.SKIP}
        return [i for i in self.items if i.key not in done]

    def open(self, key: str) -> ReviewItem:
        """Start the clock on an item and return it."""
        item = self._item(key)
        self._opened[key] = time.perf_counter()
        return item

    def crop(self, key: str) -> bytes | None:
        item = self._item(key)
        if self.render is None:
            return None
        return self.render(item.document, item.page_index, item.rect)

    def suggest(self, key: str, suggestion: str) -> ReviewItem:
        """Attach a model's suggestion (a VLM's, say).  It is shown, never applied."""
        item = self._item(key)
        updated = ReviewItem(**{**_fields(item), "suggestion": suggestion})
        self.items[self.items.index(item)] = updated
        return updated

    # -- deciding ---------------------------------------------------------- #

    def decide(self, key: str, action: Action, *, text: str | None = None,
               note: str = "") -> AuditEntry:
        item = self._item(key)
        if action is Action.EDIT and text is None:
            raise ValueError("editar exige o texto corrigido")
        final = (text if action is Action.EDIT else item.text if action is Action.ACCEPT else "")
        started = self._opened.pop(key, None)
        seconds = (time.perf_counter() - started) if started is not None else 0.0
        entry = AuditEntry(key=key, action=action, text=final or "", reviewer=self.reviewer,
                           at=datetime.now(UTC).isoformat(timespec="seconds"), seconds=seconds,
                           note=note)
        self.log.append(entry)
        page = (item.document, item.page_index)
        self._page_seconds[page] = self._page_seconds.get(page, 0.0) + seconds
        return entry

    def seconds_per_page(self) -> dict[tuple[str, int], float]:
        return dict(self._page_seconds)

    # -- exporting --------------------------------------------------------- #

    def corrections(self) -> list[dict[str, Any]]:
        """Human truth for calibration and the benchmark — minus blind pages.

        Each entry pairs the OCR's reading with the reviewer's, so
        :func:`caissa.ocr.calibration.pairs_from_alignment` can turn it into
        ``(confidence, correct)`` pairs and the manifest can grow a labelled
        region.  A page the guard calls blind is withheld and counted.
        """
        out: list[dict[str, Any]] = []
        for entry in self.log:
            if entry.action not in (Action.ACCEPT, Action.EDIT):
                continue
            item = self._item(entry.key)
            if self.blind(item.document, item.page_index):
                continue
            out.append({
                "document": item.document, "page_index": item.page_index,
                "rect": list(item.rect), "kind": item.kind, "engine": item.engine,
                "hypothesis": item.text, "truth": entry.text,
                "action": str(entry.action), "reviewer": entry.reviewer, "at": entry.at,
            })
        return out

    def withheld(self) -> int:
        return sum(1 for e in self.log if e.action in (Action.ACCEPT, Action.EDIT)
                   and self.blind(self._item(e.key).document, self._item(e.key).page_index))

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps({
            "reviewer": self.reviewer,
            "items": [i.as_dict() for i in self.items],
            "log": [e.as_dict() for e in self.log],
            "seconds_per_page": {f"{d}:{p}": round(s, 2)
                                 for (d, p), s in self._page_seconds.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- helpers ----------------------------------------------------------- #

    def _item(self, key: str) -> ReviewItem:
        for item in self.items:
            if item.key == key:
                return item
        raise KeyError(key)


def _fields(item: ReviewItem) -> dict[str, Any]:
    return {name: getattr(item, name) for name in ReviewItem.__dataclass_fields__}


def _region_trace(page_trace: Any, rect: RectT, kind: str) -> dict[str, Any]:
    """The trace of the region at ``rect`` on a page trace, or nothing."""
    if not page_trace:
        return {}
    regions: Sequence[dict[str, Any]] = page_trace.get("regions", ())
    dpi = float(page_trace.get("dpi", 72.0)) or 72.0
    scale = dpi / 72.0
    best, best_iou = None, 0.0
    for region in regions:
        box = region.get("box_px") or [0, 0, 0, 0]
        pts = (box[0] / scale, box[1] / scale, box[2] / scale, box[3] / scale)
        iou = _iou(pts, rect)
        if iou > best_iou:
            best, best_iou = region, iou
    if best is None or best_iou < 0.5:
        return {}
    decision = best.get("decision") or {}
    fusion = best.get("fusion") or {}
    return {
        "flagged_words": decision.get("flagged_words", []),
        "disputed": [t for t in fusion.get("changed_tokens", []) if t.get("disputed")],
        "legality": best.get("legality") or {},
    }


def _iou(a: RectT, b: RectT) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0
