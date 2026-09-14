"""Did the training help *this* book?  Measured on the reviewer's own lines.

FineReader answers that question by showing the verification screen again
with fewer doubts.  Here the answer is a number: every labelled line of the
book (accepted or edited, outside the blind partition) is read again by
the product's service — once as the importer would read the book without
a fine-tune, once with the book's model — and the readings are scored
against the reviewer's truth with the benchmark's metrics
(:mod:`caissa.ocr.metrics`): character error rate weighted by length,
moves kept and invented, figurines emitted, lines the service did not read.

Two honesty rules.  The lines are grouped by **partition**: ``dev`` lines
are the ones the model trained on and flatter it; ``calib`` lines were
held out and are the number to quote.  And a line the new recognition did
not find (no strip overlapping the labelled box) counts as *unread*, not as
correct — an abstention is not an answer.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ocr.golden import Partition
from caissa.ocr.metrics import move_accounting, normalise
from caissa.ocr.quality import levenshtein

from .model import LabelProject, LineLabel, PageLabels, RectT

__all__ = ["BookMeasure", "MeasureGroup", "SideMeasure", "measure_book", "score_lines"]

FIGURINES = "♔♕♖♗♘♙♚♛♜♝♞♟"
#: Overlap below which a recognised strip is not the labelled line.
MIN_LINE_IOU = 0.5
TOTAL = "total"
ProgressFn = Callable[[str], None]


def _iou(a: RectT, b: RectT) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _figurines(text: str) -> Counter[str]:
    return Counter(ch for ch in text if ch in FIGURINES)


@dataclass(slots=True)
class MeasureGroup:
    """Sums over one set of lines; the rates are properties."""

    lines: int = 0
    unread: int = 0
    exact: int = 0
    truth_chars: int = 0
    edits: int = 0
    moves_truth: int = 0
    moves_kept: int = 0
    moves_invented: int = 0
    figurines_truth: int = 0
    figurines_kept: int = 0

    def add(self, truth: str, hypothesis: str | None) -> None:
        t = normalise(truth)
        self.lines += 1
        self.truth_chars += len(t)
        moves = move_accounting(truth, hypothesis or "")
        self.moves_truth += moves.truth
        figs = _figurines(t)
        self.figurines_truth += sum(figs.values())
        if hypothesis is None:
            self.unread += 1
            self.edits += len(t)
            return
        h = normalise(hypothesis)
        self.edits += levenshtein(h, t)
        self.exact += int(h == t)
        self.moves_kept += moves.kept
        self.moves_invented += moves.invented
        self.figurines_kept += sum((figs & _figurines(h)).values())

    @property
    def cer(self) -> float:
        return self.edits / self.truth_chars if self.truth_chars else 0.0

    @property
    def move_accuracy(self) -> float:
        return self.moves_kept / self.moves_truth if self.moves_truth else 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "lines": self.lines,
            "unread": self.unread,
            "exact": self.exact,
            "truth_chars": self.truth_chars,
            "edits": self.edits,
            "cer": round(self.cer, 4),
            "moves_truth": self.moves_truth,
            "moves_kept": self.moves_kept,
            "moves_invented": self.moves_invented,
            "figurines_truth": self.figurines_truth,
            "figurines_kept": self.figurines_kept,
        }


@dataclass(slots=True)
class SideMeasure:
    """One recognition setup (without the model, with it) over every group."""

    label: str
    groups: dict[str, MeasureGroup] = field(default_factory=dict)
    seconds: float = 0.0

    def group(self, name: str) -> MeasureGroup:
        return self.groups.setdefault(name, MeasureGroup())

    def add(self, partition: str, truth: str, hypothesis: str | None) -> None:
        self.group(partition).add(truth, hypothesis)
        self.group(TOTAL).add(truth, hypothesis)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "seconds": round(self.seconds, 2),
            "groups": {k: g.as_dict() for k, g in self.groups.items()},
        }


@dataclass(slots=True)
class BookMeasure:
    document: str
    pages: list[int]
    sides: list[SideMeasure]
    measured_at: str = ""
    lines_blind: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "pages": list(self.pages),
            "measured_at": self.measured_at,
            "lines_blind": self.lines_blind,
            "notes": list(self.notes),
            "sides": [s.as_dict() for s in self.sides],
        }

    def markdown(self) -> str:
        def pct(value: float) -> str:
            return f"{100.0 * value:.1f} %"

        order = [str(Partition.CALIB), str(Partition.DEV), TOTAL]
        names = {
            str(Partition.CALIB): "avaliação (`calib`, fora do treino)",
            str(Partition.DEV): "treino (`dev`)",
            TOTAL: "todas",
        }
        heads = " | ".join(s.label for s in self.sides)
        out = [
            f"# Medida no livro — {self.document}",
            "",
            f"Páginas {', '.join(str(p) for p in self.pages)} · medido em {self.measured_at} · "
            f"{self.lines_blind} linhas cegas fora da conta.",
            "",
            f"| linhas | métrica | {heads} |",
            f"|---|---|{'---:|' * len(self.sides)}",
        ]
        for key in order:
            if not any(key in s.groups for s in self.sides):
                continue
            groups = [s.groups.get(key, MeasureGroup()) for s in self.sides]
            n = max(g.lines for g in groups)
            rows = [
                ("CER ponderado", [pct(g.cer) for g in groups]),
                ("linhas exatas", [f"{g.exact} / {g.lines}" for g in groups]),
                ("não lidas", [str(g.unread) for g in groups]),
                ("lances certos", [f"{g.moves_kept} / {g.moves_truth}" for g in groups]),
                ("lances inventados", [str(g.moves_invented) for g in groups]),
            ]
            if any(g.figurines_truth for g in groups):
                figurines = [f"{g.figurines_kept} / {g.figurines_truth}" for g in groups]
                rows.append(("figurinas certas", figurines))
            for m, (metric, values) in enumerate(rows):
                label = f"{names[key]} ({n})" if m == 0 else ""
                out.append(f"| {label} | {metric} | {' | '.join(values)} |")
        if self.notes:
            out.append("")
            out.extend(f"- {note}" for note in self.notes)
        return "\n".join(out) + "\n"

    def save(self, directory: Path | str) -> tuple[Path, Path]:
        import json

        from caissa.ocr.training.books import book_slug

        folder = Path(directory)
        folder.mkdir(parents=True, exist_ok=True)
        stem = book_slug(self.document)
        json_path = folder / f"{stem}.json"
        md_path = folder / f"{stem}.md"
        json_path.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        md_path.write_text(self.markdown(), encoding="utf-8")
        return json_path, md_path


def _labelled(page: PageLabels) -> Iterable[tuple[str, LineLabel]]:
    """``(partition, line)`` for every trainable line outside the blind partition."""
    for region in page.regions:
        partition = page.region_partition(region)
        if partition is Partition.BLIND:
            continue
        for line in region.lines:
            if line.trainable:
                yield str(partition), line


def _strips(page: PageLabels) -> list[tuple[RectT, str]]:
    return [(line.box, line.hypothesis) for _, line in page.lines()]


def score_lines(
    labelled: PageLabels,
    recognised: PageLabels,
    side: SideMeasure,
    *,
    min_iou: float = MIN_LINE_IOU,
) -> int:
    """Score every labelled line of ``labelled`` against ``recognised``.

    Returns how many lines were scored.  A labelled line with no recognised
    strip overlapping it by ``min_iou`` counts as unread.
    """
    strips = _strips(recognised)
    scored = 0
    for partition, line in _labelled(labelled):
        best, best_iou = None, 0.0
        for box, text in strips:
            iou = _iou(line.box, box)
            if iou > best_iou:
                best, best_iou = text, iou
        hypothesis = best if best is not None and best_iou >= min_iou else None
        side.add(partition, line.text, hypothesis)
        scored += 1
    return scored


def measure_book(
    project: LabelProject,
    document: str,
    services: Mapping[str, Any],
    *,
    pages: Sequence[int] | None = None,
    progress: ProgressFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> BookMeasure:
    """Re-read the book's labelled pages with each service and score them.

    ``services`` maps a label (``"sem modelo"``, ``"com modelo"``) to an
    object with ``recognize_image`` — the product's :class:`OcrService`
    built with and without the book's fine-tune.  Pages are recognised at
    the DPI and language they were labelled with.
    """
    import time

    from .recognise import label_page

    labelled_pages = [
        p for p in project.pages_of(document) if pages is None or p.page_index in set(pages)
    ]
    labelled_pages = [p for p in labelled_pages if any(True for _ in _labelled(p))]
    measure = BookMeasure(
        document=document,
        pages=[p.page_index for p in labelled_pages],
        sides=[SideMeasure(label=label) for label in services],
        measured_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    for page in labelled_pages:
        measure.lines_blind += sum(
            1
            for region in page.regions
            if page.region_blind(region)
            for line in region.lines
            if line.trainable
        )
    pdf_path = project.pdf_for(document) if document in project.documents else None
    for page in labelled_pages:
        path = pdf_path or Path(page.pdf_path)
        for side, (label, service) in zip(measure.sides, services.items(), strict=True):
            if should_cancel is not None and should_cancel():
                measure.notes.append("medição cancelada antes do fim")
                return measure
            if progress is not None:
                progress(f"página {page.page_index} · {label}")
            started = time.monotonic()
            try:
                recognised = label_page(
                    service, path, document, page.page_index, dpi=page.dpi, lang=page.lang
                )
            except Exception as exc:  # noqa: BLE001 - one page must not lose the measurement
                measure.notes.append(f"página {page.page_index} ({label}): {exc}")
                recognised = PageLabels(
                    document=document,
                    pdf_path=str(path),
                    page_index=page.page_index,
                    width_pt=page.width_pt,
                    height_pt=page.height_pt,
                    dpi=page.dpi,
                    lang=page.lang,
                )
            side.seconds += time.monotonic() - started
            score_lines(page, recognised, side)
    return measure
