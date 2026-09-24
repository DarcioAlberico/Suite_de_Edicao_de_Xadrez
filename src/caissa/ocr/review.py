"""The review queue — Sol §SOL-11, without the window.

The reviewer's job is to correct doubtful spans, not to reread the book.
This module is the model behind that job: it takes what the importer
already knows (Sol §SOL-10's review items and traces), orders it by risk,
gives each item its crop, its best reading, the alternatives and the
reason for the doubt, records every human decision with who, when and how
long, and exports the decisions in the shapes calibration (SOL-4) and the
benchmark (SOL-0) consume — with one guard: **a decision on a page of the
blind partition never leaves the queue as training data**.

There is no Qt here on purpose: the window (:mod:`caissa.ui.views.revisao_de_texto`,
OCR_UI_ROADMAP passo 14) is a list, a crop, three buttons and a timer over
this queue, and everything it decides is decided here.

The decisions outlive the window.  :class:`ReviewDecisions` is the queue's
log reduced to one decision per region, saved as JSON next to the labelling
project (``labeling/revisao/<book>.json``) and **applied by the importer** the
next time the book is read (``PdfImportOptions.review_decisions``): an
accepted region stops being "for review" and carries ``verified_by_human``,
an edited one carries the reviewer's text, a region kept as image is
abstained — so the export sees the book as the reviewer left it, and says
how many doubtful regions remain.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .golden import Partition, partition_for

__all__ = [
    "Action",
    "AuditEntry",
    "Decided",
    "ReviewDecisions",
    "ReviewItem",
    "ReviewQueue",
    "accepts_nothing",
    "blind_guard",
    "decisions_path",
]

RectT = tuple[float, float, float, float]


class Action(StrEnum):
    ACCEPT = "accept"          # the best reading is right
    EDIT = "edit"              # the reviewer typed the text
    KEEP_IMAGE = "keep_image"  # leave the region as a picture
    SKIP = "skip"


def accepts_nothing(action: Action, reading: str) -> bool:
    """An accept of no reading: «Aceitar leitura», or the Enter on an empty truth, accepts nothing.

    The item was never read: a page whose OCR raised, a contested page the OCR could not answer.
    Crítico da fase 5, ciclo 6: the page item of a ``MemoryError``, accepted with the Enter, became
    an accept over the whole page's rectangle, and the next import applied it to the reading that
    came then -- «aceita pelo revisor», verified, out of the queue -- a reading nobody saw.  An
    accept records the reading it accepted (:meth:`ReviewQueue.decide`), so an accept without one
    is refused by the window, left out of the decisions and not applied to a region.
    """
    return action is Action.ACCEPT and not reading.strip()


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewItem:
        return cls(
            key=data["key"], document=data["document"], page_index=int(data["page_index"]),
            rect=tuple(float(v) for v in data["rect"]), kind=data.get("kind", ""),
            decision=data.get("decision", "review"), reasons=tuple(data.get("reasons", ())),
            text=data.get("text", ""), engine=data.get("engine", ""),
            score=float(data.get("score", 0.0)),
            alternatives=tuple((a, b) for a, b in data.get("alternatives", ())),
            low_confidence_words=tuple(data.get("low_confidence_words", ())),
            disputed_tokens=tuple((a, b) for a, b in data.get("disputed_tokens", ())),
            legality=dict(data.get("legality", {})), suggestion=data.get("suggestion", ""),
        )

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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEntry:
        return cls(key=data["key"], action=Action(data["action"]), text=data.get("text", ""),
                   reviewer=data.get("reviewer", ""), at=data.get("at", ""),
                   seconds=float(data.get("seconds", 0.0)), note=data.get("note", ""))


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
                    blind: BlindGuard | None = None) -> ReviewQueue:
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

    @classmethod
    def load(cls, path: Path | str, *, render: Callable[[str, int, RectT], bytes] | None = None,
             blind: BlindGuard | None = None) -> ReviewQueue:
        """A queue :meth:`save` wrote, items and log, ready to go on."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        queue = cls(reviewer=data.get("reviewer", ""), render=render)
        if blind is not None:
            queue.blind = blind
        queue.items = [ReviewItem.from_dict(i) for i in data.get("items", ())]
        queue.log = [AuditEntry.from_dict(e) for e in data.get("log", ())]
        for key, seconds in (data.get("seconds_per_page") or {}).items():
            document, _, page = key.rpartition(":")
            queue._page_seconds[(document, int(page))] = float(seconds)
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

    def refusal(self, key: str, action: Action) -> str:
        """Why the window must not record ``action`` on ``key`` — empty when it may.

        A correction on a page of the blind partition is refused with the
        phrase (SOL-11): the partition exists to measure, and a page the
        reviewer fixed by hand would measure the reviewer.  Keeping the
        region as an image or skipping it changes no text and is allowed.
        And an accept of an item without a reading is refused: there is
        nothing to accept (:func:`accepts_nothing`).
        """
        item = self._item(key)
        if action in (Action.ACCEPT, Action.EDIT) and self.blind(item.document, item.page_index):
            return (f"página {item.page_index + 1} está na partição cega: "
                    "a leitura não pode ser aceita nem corrigida aqui (ela mede o OCR).")
        if accepts_nothing(action, item.text):
            return ("não há leitura para aceitar: o OCR não leu esta "
                    f"{'página' if item.kind == 'page' else 'região'}. Escreva o texto e grave a "
                    "edição, ou mantenha-a como imagem.")
        return ""

    def carry_over(self, previous: ReviewQueue | None) -> int:
        """Keep the decisions of ``previous`` (the same book, an earlier queue) in this one.

        OCR_UI ciclo 2, passo C7: the window's import hands its result to the
        review tab, which rebuilds the queue from it.  A region decided before
        was applied on that import and is not in the new ``review_items`` -- so
        a queue built from scratch would have no trace of it, and the next
        ``gravar`` would write the decisions file **without** it.  The earlier
        decisions come along here: an item of ``previous`` that was decided is
        matched to the new items by page and rectangle (IoU ≥ 0,5) and its log
        entries re-keyed; one that has no counterpart is appended, decided, so
        :meth:`decisions` still sees it.  Returns how many decisions came over.
        """
        if previous is None or not previous.log:
            return 0
        decided = previous.decided()
        if not decided:
            return 0
        by_key = {item.key: item for item in self.items}
        carried = 0
        rekey: dict[str, str] = {}
        for key, _entry in decided.items():
            try:
                old = previous._item(key)
            except KeyError:
                continue
            match = next(
                (item for item in self.items
                 if item.page_index == old.page_index and _iou(item.rect, old.rect) >= 0.5),
                None,
            )
            if match is not None:
                rekey[key] = match.key
            else:
                new_key = key if key not in by_key else f"{key}:anterior"
                rekey[key] = new_key
                self.items.append(replace(old, key=new_key))
                by_key[new_key] = self.items[-1]
            carried += 1
        for entry in previous.log:
            if entry.key in rekey:
                self.log.append(replace(entry, key=rekey[entry.key]))
        return carried

    def decided(self) -> dict[str, AuditEntry]:
        """The last non-skip decision per item."""
        out: dict[str, AuditEntry] = {}
        for entry in self.log:
            if entry.action is Action.SKIP:
                continue
            out[entry.key] = entry
        return out

    def decisions(self) -> ReviewDecisions:
        """The decisions the importer applies (blind pages withheld, as in :meth:`corrections`).

        An accept of an item without a reading is none (:func:`accepts_nothing`) -- a log written
        before the window refused it would otherwise hand the importer an accept over the page.
        """
        entries = []
        for key, entry in self.decided().items():
            item = self._item(key)
            if entry.action in (Action.ACCEPT, Action.EDIT) and self.blind(
                item.document, item.page_index
            ):
                continue
            if accepts_nothing(entry.action, item.text):
                continue
            entries.append(Decided(page_index=item.page_index, rect=item.rect,
                                   action=entry.action, text=entry.text, reviewer=entry.reviewer,
                                   at=entry.at))
        return ReviewDecisions(document=self.items[0].document if self.items else "",
                               entries=tuple(entries))

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


# --------------------------------------------------------------------------- #
# Decisions the importer applies
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Decided:
    """One region's final decision, placed on the page."""

    page_index: int
    rect: RectT
    action: Action
    text: str = ""
    reviewer: str = ""
    at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"page_index": self.page_index, "rect": list(self.rect), "action": str(self.action),
                "text": self.text, "reviewer": self.reviewer, "at": self.at}


@dataclass(frozen=True, slots=True)
class ReviewDecisions:
    """What the reviewer settled, by page and box — applied to the OCR regions on import.

    Matching is by overlap (IoU ≥ 0.5) between the decision's box and the
    region's, both in page points: the layout is deterministic for a given
    page and DPI, so a region found again is found at the same place.
    """

    document: str = ""
    entries: tuple[Decided, ...] = ()

    IOU_FLOOR = 0.5

    def __len__(self) -> int:
        return len(self.entries)

    def for_page(self, page_index: int) -> list[Decided]:
        return [d for d in self.entries if d.page_index == page_index]

    def match(self, page_index: int, rect: RectT) -> Decided | None:
        """The decision over ``rect`` -- never an accept of no reading (:func:`accepts_nothing`)."""
        best, best_iou = None, 0.0
        for decided in self.for_page(page_index):
            if accepts_nothing(decided.action, decided.text):
                continue
            iou = _iou(decided.rect, rect)
            if iou > best_iou:
                best, best_iou = decided, iou
        return best if best_iou >= self.IOU_FLOOR else None

    def apply(self, recognition: Any, frame: Any) -> int:
        """Patch ``recognition.regions`` in place; how many regions were decided.

        ``accept`` → the region is accepted and verified; ``edit`` → its
        reading becomes the reviewer's text (one line over the region's box
        when the line count differs), accepted and verified; ``keep_image``
        → abstained, so the importer keeps the region as a picture.  An
        accept that carries no reading accepted nothing and is not applied
        (:func:`accepts_nothing`): the file may predate the window's refusal.
        """
        from dataclasses import replace

        from caissa.ocr.decision import Decision
        from caissa.ocr.types import OcrLine, OcrWord

        applied = 0
        regions = list(recognition.regions)
        for index, region in enumerate(regions):
            if region.decision.decision is Decision.ACCEPTED:
                continue
            box = region.box_px
            rect = frame.pixels_to_page((box.x0, box.y0, box.x1, box.y1), recognition.dpi)
            decided = self.match(frame.index, rect)
            if decided is None:
                continue
            reason = f"decidido pelo revisor {decided.reviewer or '?'} em {decided.at or '?'}"
            if decided.action is Action.KEEP_IMAGE:
                decision = replace(region.decision, decision=Decision.ABSTAINED,
                                   reasons_pt=("mantida como imagem pelo revisor", reason))
                regions[index] = replace(region, decision=decision, verified=True)
            elif decided.action in (Action.ACCEPT, Action.EDIT):
                result = region.result
                if decided.action is Action.EDIT:
                    typed = [t for t in decided.text.splitlines() if t.strip()]
                    lines = list(result.lines)
                    if typed and len(typed) == len(lines):
                        lines = [
                            replace(line, words=(OcrWord(text=text, box=line.box, confidence=1.0),))
                            for line, text in zip(lines, typed, strict=True)
                        ]
                    else:
                        lines = [OcrLine(words=(OcrWord(text=" ".join(typed), box=box,
                                                         confidence=1.0),), box=box,
                                         kind=result.region_kind)]
                    result = replace(result, lines=tuple(lines))
                decision = replace(region.decision, decision=Decision.ACCEPTED, score=1.0,
                                   reasons_pt=("aceita pelo revisor", reason))
                regions[index] = replace(region, result=result, decision=decision, score=1.0,
                                         verified=True)
            else:
                continue
            applied += 1
        if applied:
            recognition.regions[:] = regions
        return applied

    # -- files ------------------------------------------------------------ #

    def as_dict(self) -> dict[str, Any]:
        return {"document": self.document, "entries": [d.as_dict() for d in self.entries]}

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | str) -> ReviewDecisions:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(document=data.get("document", ""), entries=tuple(
            Decided(page_index=int(e["page_index"]), rect=tuple(float(v) for v in e["rect"]),
                    action=Action(e["action"]), text=e.get("text", ""),
                    reviewer=e.get("reviewer", ""), at=e.get("at", ""))
            for e in data.get("entries", ())))

    @classmethod
    def for_pdf(cls, pdf_path: Path | str) -> ReviewDecisions | None:
        """The decisions saved for this book, or ``None`` when nobody reviewed it."""
        path = decisions_path(pdf_path)
        return cls.load(path) if path.is_file() else None


def decisions_path(pdf_path: Path | str) -> Path:
    """Where a book's review decisions live: ``<labeling>/revisao/<book>.json``.

    Next to the labelling project (git-ignored, on this machine), never
    next to the PDF — the corpus folder is not ours to write in.
    """
    from caissa.ocr.labeling.helpers import default_project_dir

    return default_project_dir() / "revisao" / (Path(pdf_path).stem + ".json")
