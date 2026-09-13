"""The labelling project: pages, regions, lines and what was decided on each.

A line is the unit of work because it is the unit Tesseract trains on and
the unit a reviewer can check without rereading the page: one image strip,
one string.  A region groups lines in reading order so the manifest gets a
paragraph — and a manifest item, which is what fixes its partition; a page
groups regions so the reviewer works one scan at a time.

Coordinates are PDF points, never pixels.  A pixel only exists relative to
a DPI, and the DPI is a field the reviewer changes; a box stored in pixels
would point at the wrong place the moment the page is re-rendered.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from caissa.ocr.golden import Partition, partition_for

__all__ = [
    "LabelProject",
    "LineLabel",
    "LineStatus",
    "PageLabels",
    "RectT",
    "RegionLabel",
    "WordHint",
    "item_id_for",
    "page_key",
]

RectT = tuple[float, float, float, float]

PROJECT_VERSION = 1


class LineStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"  # the engine's reading is right
    EDITED = "edited"  # the reviewer typed the text
    REJECTED = "rejected"  # not text, or unreadable: kept as image, never trained on


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _rect(values: Any) -> RectT:
    x0, y0, x1, y1 = (float(v) for v in values)
    return x0, y0, x1, y1


def page_key(document: str, page_index: int) -> str:
    return f"{document}:p{page_index}"


def item_id_for(book: str, page_index: int, rect: RectT) -> str:
    """The golden manifest id of a region.

    The scheme of ``build_manifest.py``
    (``real:<book>:<page>:<y0>``) plus ``x0`` so two columns at the same
    height stay distinct.  :func:`caissa.ocr.review.blind_guard` reads only
    the first three parts, so the extra one changes nothing there.
    """
    return f"real:{book[:24]}:{page_index}:{round(rect[1])}:{round(rect[0])}"


# --------------------------------------------------------------------------- #
# Lines
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class WordHint:
    """One word the engine read, for highlighting: text, confidence, box (points)."""

    text: str
    confidence: float
    box: RectT

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "box": [round(v, 2) for v in self.box],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WordHint:
        return cls(
            text=str(data.get("text", "")),
            confidence=float(data.get("confidence", 0.0)),
            box=_rect(data.get("box", (0, 0, 0, 0))),
        )


@dataclass(slots=True)
class LineLabel:
    """One text line: the engine's reading and the reviewer's verdict."""

    index: int
    box: RectT  # page points
    hypothesis: str
    confidence: float = 0.0
    words: tuple[WordHint, ...] = ()
    #: ``(source, text)`` readings of the same line by other candidates.
    alternatives: tuple[tuple[str, str], ...] = ()
    truth: str = ""
    status: LineStatus = LineStatus.PENDING
    reviewer: str = ""
    at: str = ""
    seconds: float = 0.0
    note: str = ""

    @property
    def done(self) -> bool:
        return self.status is not LineStatus.PENDING

    @property
    def text(self) -> str:
        """The line's final text: what the reviewer typed, or what they accepted."""
        if self.status is LineStatus.EDITED:
            return self.truth
        if self.status is LineStatus.ACCEPTED:
            return self.hypothesis
        return ""

    @property
    def trainable(self) -> bool:
        return self.status in (LineStatus.ACCEPTED, LineStatus.EDITED) and bool(self.text.strip())

    def low_confidence_words(self, threshold: float) -> tuple[str, ...]:
        return tuple(w.text for w in self.words if w.confidence < threshold and w.text.strip())

    def doubtful(self, threshold: float) -> bool:
        """Worth a look before the rest.

        A weak word, an empty reading, or a candidate that disagrees.
        """
        if not self.hypothesis.strip() or self.confidence < threshold:
            return True
        if any(w.confidence < threshold for w in self.words if w.text.strip()):
            return True
        return any(alt.strip() != self.hypothesis.strip() for _, alt in self.alternatives)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "box": [round(v, 2) for v in self.box],
            "hypothesis": self.hypothesis,
            "confidence": round(self.confidence, 4),
            "words": [w.as_dict() for w in self.words],
            "alternatives": [list(a) for a in self.alternatives],
            "truth": self.truth,
            "status": str(self.status),
            "reviewer": self.reviewer,
            "at": self.at,
            "seconds": round(self.seconds, 2),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LineLabel:
        return cls(
            index=int(data["index"]),
            box=_rect(data["box"]),
            hypothesis=str(data.get("hypothesis", "")),
            confidence=float(data.get("confidence", 0.0)),
            words=tuple(WordHint.from_dict(w) for w in data.get("words", ())),
            alternatives=tuple((str(a), str(b)) for a, b in data.get("alternatives", ())),
            truth=str(data.get("truth", "")),
            status=LineStatus(data.get("status", "pending")),
            reviewer=str(data.get("reviewer", "")),
            at=str(data.get("at", "")),
            seconds=float(data.get("seconds", 0.0)),
            note=str(data.get("note", "")),
        )


# --------------------------------------------------------------------------- #
# Regions
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RegionLabel:
    """A block of lines in reading order — a manifest region once complete."""

    index: int
    rect: RectT  # page points
    kind: str
    reading_order: int
    lines: list[LineLabel] = field(default_factory=list)
    engine: str = ""
    score: float = 0.0
    decision: str = ""
    reasons: tuple[str, ...] = ()
    prose_lang: str = ""
    notation_lang: str = ""
    #: Drawn by the reviewer rather than found by the layout analyser.
    drawn: bool = False
    #: FEN before the first move of a movetext region, when the reviewer
    #: labelled it — what the legality replay (Sol §SOL-8) needs and 98 % of
    #: the corpus lacks (``SOL_REPORT.md`` §3).
    start_fen: str = ""

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines if line.trainable)

    @property
    def pending(self) -> int:
        return sum(1 for line in self.lines if not line.done)

    @property
    def complete(self) -> bool:
        """Every line decided and at least one kept as text."""
        return bool(self.lines) and self.pending == 0 and any(line.trainable for line in self.lines)

    def item_id(self, book: str, page_index: int) -> str:
        return item_id_for(book, page_index, self.rect)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "rect": [round(v, 2) for v in self.rect],
            "kind": self.kind,
            "reading_order": self.reading_order,
            "lines": [line.as_dict() for line in self.lines],
            "engine": self.engine,
            "score": round(self.score, 4),
            "decision": self.decision,
            "reasons": list(self.reasons),
            "prose_lang": self.prose_lang,
            "notation_lang": self.notation_lang,
            "drawn": self.drawn,
            "start_fen": self.start_fen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegionLabel:
        return cls(
            index=int(data["index"]),
            rect=_rect(data["rect"]),
            kind=str(data.get("kind", "paragraph")),
            reading_order=int(data.get("reading_order", 0)),
            lines=[LineLabel.from_dict(row) for row in data.get("lines", ())],
            engine=str(data.get("engine", "")),
            score=float(data.get("score", 0.0)),
            decision=str(data.get("decision", "")),
            reasons=tuple(str(r) for r in data.get("reasons", ())),
            prose_lang=str(data.get("prose_lang", "")),
            notation_lang=str(data.get("notation_lang", "")),
            drawn=bool(data.get("drawn", False)),
            start_fen=str(data.get("start_fen", "")),
        )


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class PageLabels:
    """One page of one document, with everything found and decided on it."""

    document: str  # the book: the PDF's stem
    pdf_path: str
    page_index: int
    width_pt: float
    height_pt: float
    dpi: float
    lang: str
    regions: list[RegionLabel] = field(default_factory=list)
    engines: dict[str, str] = field(default_factory=dict)
    recognised_at: str = ""
    #: Review time accumulated on this page (Sol §SOL-11 measures it).
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return page_key(self.document, self.page_index)

    def lines(self) -> Iterator[tuple[RegionLabel, LineLabel]]:
        for region in self.regions:
            for line in region.lines:
                yield region, line

    def region_partition(self, region: RegionLabel) -> Partition:
        return partition_for(region.item_id(self.document, self.page_index))

    def region_blind(self, region: RegionLabel) -> bool:
        return self.region_partition(region) is Partition.BLIND

    @property
    def blind_regions(self) -> int:
        """Regions whose manifest id hashes to the blind partition.

        The partition is the manifest's, per item — and an item is a region — so
        the rule is applied per region, not per page: a page with twenty
        regions would otherwise be blind with near certainty.
        """
        return sum(1 for r in self.regions if r.lines and self.region_blind(r))

    def counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in LineStatus}
        for _, line in self.lines():
            counts[line.status.value] += 1
        counts["total"] = sum(counts.values())
        return counts

    def next_region_index(self) -> int:
        return max((r.index for r in self.regions), default=-1) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "pdf_path": self.pdf_path,
            "page_index": self.page_index,
            "width_pt": round(self.width_pt, 2),
            "height_pt": round(self.height_pt, 2),
            "dpi": self.dpi,
            "lang": self.lang,
            "regions": [r.as_dict() for r in self.regions],
            "engines": dict(self.engines),
            "recognised_at": self.recognised_at,
            "seconds": round(self.seconds, 2),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageLabels:
        return cls(
            document=str(data["document"]),
            pdf_path=str(data.get("pdf_path", "")),
            page_index=int(data["page_index"]),
            width_pt=float(data.get("width_pt", 0.0)),
            height_pt=float(data.get("height_pt", 0.0)),
            dpi=float(data.get("dpi", 300.0)),
            lang=str(data.get("lang", "")),
            regions=[RegionLabel.from_dict(r) for r in data.get("regions", ())],
            engines={str(k): str(v) for k, v in data.get("engines", {}).items()},
            recognised_at=str(data.get("recognised_at", "")),
            seconds=float(data.get("seconds", 0.0)),
            notes=[str(n) for n in data.get("notes", ())],
        )


# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class LabelProject:
    """A directory of labels.

    ``project.json``, one file per page under ``pages/``, and ``audit.jsonl``
    with every decision ever made, in order.
    """

    root: Path
    name: str = ""
    reviewer: str = ""
    #: book (PDF stem) → path of the PDF on this machine.
    documents: dict[str, str] = field(default_factory=dict)
    #: book → Tesseract language of the book (``eng``, ``por+eng``).  The
    #: window restores it when the book is selected, so the language a page
    #: is recognised and labelled with is the book's, not the window's default
    #: — the manifest's ``prose_lang`` facet comes from it.
    languages: dict[str, str] = field(default_factory=dict)
    pages: dict[str, PageLabels] = field(default_factory=dict)
    #: Word confidence below which a line is shown as doubtful.
    doubt_threshold: float = 0.85
    created_at: str = field(default_factory=_now)

    # -- documents --------------------------------------------------------- #

    def add_document(self, pdf_path: Path | str) -> str:
        path = Path(pdf_path)
        book = path.stem
        self.documents[book] = str(path)
        return book

    def pdf_for(self, document: str) -> Path:
        return Path(self.documents[document])

    def set_language(self, document: str, lang: str) -> int:
        """Record the book's language and re-stamp its labelled pages with it.

        Returns how many pages changed.  The manifest facet (``pt``/``en``)
        follows the page language, so a page recognised with the window's
        default ``por+eng`` on an English book is corrected here.
        """
        from .recognise import iso_lang

        self.languages[document] = lang
        iso = iso_lang(lang)
        changed = 0
        for page in self.pages_of(document):
            if page.lang != lang:
                page.lang = lang
                changed += 1
            for region in page.regions:
                region.prose_lang = iso
                region.notation_lang = iso
        return changed

    # -- pages ------------------------------------------------------------- #

    def page(self, document: str, page_index: int) -> PageLabels | None:
        return self.pages.get(page_key(document, page_index))

    def put_page(self, page: PageLabels) -> None:
        self.pages[page.key] = page

    def remove_page(self, document: str, page_index: int) -> None:
        self.pages.pop(page_key(document, page_index), None)

    def pages_of(self, document: str) -> list[PageLabels]:
        return sorted(
            (p for p in self.pages.values() if p.document == document), key=lambda p: p.page_index
        )

    def blind_regions(self) -> int:
        return sum(p.blind_regions for p in self.pages.values())

    # -- deciding ---------------------------------------------------------- #

    def decide(
        self,
        page: PageLabels,
        line: LineLabel,
        status: LineStatus,
        *,
        text: str | None = None,
        seconds: float = 0.0,
        note: str = "",
    ) -> LineLabel:
        """Record a verdict on a line and append it to the audit trail."""
        if status is LineStatus.EDITED:
            if text is None:
                raise ValueError("editar exige o texto corrigido")
            line.truth = text
        elif status is LineStatus.ACCEPTED:
            line.truth = line.hypothesis
        elif status is LineStatus.REJECTED:
            line.truth = ""
        line.status = status
        line.reviewer = self.reviewer
        line.at = _now()
        line.seconds = float(seconds)
        line.note = note
        page.seconds += float(seconds)
        self._audit(
            {
                "page": page.key,
                "line": line.index,
                "box": [round(v, 2) for v in line.box],
                "action": str(status),
                "hypothesis": line.hypothesis,
                "text": line.text,
                "reviewer": self.reviewer,
                "at": line.at,
                "seconds": round(float(seconds), 2),
                "note": note,
            }
        )
        return line

    def reset(self, page: PageLabels, line: LineLabel) -> None:
        line.status = LineStatus.PENDING
        line.truth = ""
        self._audit(
            {
                "page": page.key,
                "line": line.index,
                "action": "reset",
                "reviewer": self.reviewer,
                "at": _now(),
            }
        )

    def _audit(self, entry: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- summary ----------------------------------------------------------- #

    def summary(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in LineStatus}
        regions = complete = blind_regions = 0
        seconds = 0.0
        for page in self.pages.values():
            seconds += page.seconds
            blind_regions += page.blind_regions
            for region in page.regions:
                regions += 1
                complete += int(region.complete)
                for line in region.lines:
                    counts[line.status.value] += 1
        counts["total"] = sum(counts.values())
        return {
            "documents": len(self.documents),
            "pages": len(self.pages),
            "blind_regions": blind_regions,
            "regions": regions,
            "regions_complete": complete,
            "lines": counts,
            "seconds": round(seconds, 1),
        }

    # -- persistence ------------------------------------------------------- #

    @staticmethod
    def _page_file(root: Path, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return root / "pages" / f"{safe}.json"

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "pages").mkdir(exist_ok=True)
        index = {
            "version": PROJECT_VERSION,
            "name": self.name,
            "reviewer": self.reviewer,
            "documents": dict(self.documents),
            "languages": dict(self.languages),
            "doubt_threshold": self.doubt_threshold,
            "created_at": self.created_at,
            "saved_at": _now(),
            "pages": sorted(self.pages),
        }
        (self.root / "project.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        kept = set()
        for key, page in self.pages.items():
            target = self._page_file(self.root, key)
            kept.add(target.name)
            target.write_text(
                json.dumps(page.as_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
        for stale in (self.root / "pages").glob("*.json"):
            if stale.name not in kept:
                stale.unlink()

    @classmethod
    def load(cls, root: Path | str) -> LabelProject:
        root = Path(root)
        data = json.loads((root / "project.json").read_text("utf-8"))
        if int(data.get("version", 0)) != PROJECT_VERSION:
            raise ValueError(f"projeto na versão {data.get('version')}, esperada {PROJECT_VERSION}")
        project = cls(
            root=root,
            name=str(data.get("name", "")),
            reviewer=str(data.get("reviewer", "")),
            documents={str(k): str(v) for k, v in data.get("documents", {}).items()},
            languages={str(k): str(v) for k, v in data.get("languages", {}).items()},
            doubt_threshold=float(data.get("doubt_threshold", 0.85)),
            created_at=str(data.get("created_at", "")),
        )
        for key in data.get("pages", ()):
            page_file = cls._page_file(root, str(key))
            if page_file.is_file():
                page = PageLabels.from_dict(json.loads(page_file.read_text("utf-8")))
                project.pages[page.key] = page
        return project

    @classmethod
    def open_or_create(
        cls, root: Path | str, *, name: str = "", reviewer: str = ""
    ) -> LabelProject:
        root = Path(root)
        if (root / "project.json").is_file():
            project = cls.load(root)
            if reviewer:
                project.reviewer = reviewer
            return project
        project = cls(root=root, name=name or root.name, reviewer=reviewer)
        project.save()
        return project
