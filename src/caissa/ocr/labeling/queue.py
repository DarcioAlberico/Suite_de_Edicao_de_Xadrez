"""Which page to label next — the queue by value of the label (OCR_UI_ROADMAP passo 5).

Thirteen pages labelled out of two hundred, one of them timed at eight
minutes: a human label is expensive, so the bench should say where it buys
the most.  The value of labelling a page is what the label would *change*:

* lines the service would send to review (``REVIEW``/``ABSTAINED`` regions,
  and doubtful lines — a weak word, an empty reading, a candidate that
  disagrees) — every one of them is a correction the fine-tune learns from
  and a calibration pair the tables lack;
* ``movetext`` regions, because a ``start_fen`` there feeds the legality
  replay that 98 % of the corpus cannot run (``SOL_REPORT.md`` §3);
* a book nobody labelled yet, or whose items in the golden manifest carry
  no language or stratum — a facet the benchmark cannot group by.

What does **not** count: lines in regions that hash to the blind partition
(``golden.partition_for`` is a function of the item id, so the queue knows
before anyone labels) — they enter the manifest but train nothing, and a
queue that sent the reviewer there would be spending labels on the exam.

The scoring runs the production service on a spaced sample of the book's
pages (``sample_indices``, as ``bench_ingest --sample``), skips pages already
labelled, and is cancellable between pages: a reviewer who clicked «Próxima
que vale» on a 400-page scan can change their mind.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

from caissa.ingest.pdf.document import sample_indices
from caissa.ocr.golden import GoldenManifest, load_manifest
from caissa.ocr.types import RegionKind

from .model import LabelProject, PageLabels
from .recognise import label_page, page_count

__all__ = [
    "BookContext",
    "PageValue",
    "Ranking",
    "default_manifest_path",
    "rank_pages",
    "value_of",
]

REVIEW_DECISIONS = frozenset({"review", "abstained"})
#: A doubtful line outside a ``REVIEW`` region: half a review line — the
#: reviewer will look at it, but the service would have shipped it.
WEIGHT_DOUBT = 0.5
#: A ``movetext`` region without ``start_fen``: worth three review lines
#: (the FEN unlocks the legality replay of every move under it).
WEIGHT_MOVETEXT_FEN = 3.0
#: A book with no label and no manifest item: its first page is worth more
#: than another page of a book the model already knows.
NEW_BOOK_FACTOR = 1.5
#: A book whose manifest items lack a facet: one label fills the gap.
FACET_GAP_BONUS = 2.0
DEFAULT_SAMPLE = 12


def default_manifest_path() -> Path:
    """The private golden manifest of a checkout; the queue reads it when present."""
    root = Path(__file__).resolve().parents[4]
    return root / "benchmarks" / "corpus" / "golden" / "manifest.private.json"


@dataclass(slots=True)
class BookContext:
    """What the project and the manifest already know about a book."""

    labelled_pages: int = 0
    manifest_items: int = 0
    #: Manifest items of the book with an empty ``prose_lang``,
    #: ``notation_lang`` or ``strata``.
    facet_gaps: int = 0

    @property
    def is_new(self) -> bool:
        return self.labelled_pages == 0 and self.manifest_items == 0

    @classmethod
    def of(
        cls, project: LabelProject, document: str, manifest: GoldenManifest | None = None
    ) -> BookContext:
        items = [i for i in (manifest.items if manifest else ()) if i.book == document]
        gaps = sum(1 for i in items if not i.prose_lang or not i.notation_lang or not i.strata)
        return cls(
            labelled_pages=len(project.pages_of(document)),
            manifest_items=len(items),
            facet_gaps=gaps,
        )


@dataclass(slots=True)
class PageValue:
    """The score of one page and every count behind it."""

    document: str
    page_index: int
    review_lines: int = 0
    doubtful_lines: int = 0
    total_lines: int = 0
    blind_lines: int = 0
    movetext_without_fen: int = 0
    score: float = 0.0
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "page_index": self.page_index,
            "review_lines": self.review_lines,
            "doubtful_lines": self.doubtful_lines,
            "total_lines": self.total_lines,
            "blind_lines": self.blind_lines,
            "movetext_without_fen": self.movetext_without_fen,
            "score": round(self.score, 3),
            "reasons": list(self.reasons),
        }

    def describe_pt(self) -> str:
        return f"p. {self.page_index}: {self.score:.1f} — " + "; ".join(self.reasons)


def value_of(page: PageLabels, *, threshold: float, book: BookContext) -> PageValue:
    """Score a recognised page.  Pure: no I/O, no service."""
    value = PageValue(document=page.document, page_index=page.page_index)
    for region in page.regions:
        lines = [line for line in region.lines if line.hypothesis.strip() or line.words]
        value.total_lines += len(lines)
        if page.region_blind(region):
            value.blind_lines += len(lines)
            continue
        if str(region.decision).lower() in REVIEW_DECISIONS:
            value.review_lines += len(lines)
        else:
            value.doubtful_lines += sum(1 for line in lines if line.doubtful(threshold))
        if region.kind == RegionKind.MOVETEXT and not region.start_fen:
            value.movetext_without_fen += 1

    score = value.review_lines + WEIGHT_DOUBT * value.doubtful_lines
    score += WEIGHT_MOVETEXT_FEN * value.movetext_without_fen
    reasons: list[str] = []
    if value.review_lines:
        reasons.append(f"{value.review_lines} linha(s) em revisão")
    if value.doubtful_lines:
        reasons.append(f"{value.doubtful_lines} linha(s) duvidosa(s)")
    if value.movetext_without_fen:
        reasons.append(f"{value.movetext_without_fen} bloco(s) de lances sem FEN inicial")
    if book.facet_gaps:
        score += FACET_GAP_BONUS
        reasons.append(f"{book.facet_gaps} item(ns) do livro sem idioma/estrato no manifesto")
    if book.is_new and score > 0:
        score *= NEW_BOOK_FACTOR
        reasons.append("livro sem rótulo")
    if value.blind_lines:
        reasons.append(f"{value.blind_lines} linha(s) na partição cega, fora da conta")
    if not reasons:
        reasons.append("nada a corrigir: a página já sai aceita")
    value.score = score
    value.reasons = tuple(reasons)
    return value


@dataclass(slots=True)
class Ranking:
    """The queue of one book: sampled pages by value, best first."""

    document: str
    sampled: list[int] = field(default_factory=list)
    skipped_labelled: list[int] = field(default_factory=list)
    values: list[PageValue] = field(default_factory=list)
    cancelled: bool = False
    dpi: float = 0.0
    lang: str = ""
    book: BookContext = field(default_factory=BookContext)

    def top(self, n: int = 5) -> list[PageValue]:
        return self.values[:n]

    def median_review_lines(self) -> float:
        return float(median(v.review_lines for v in self.values)) if self.values else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "sampled": list(self.sampled),
            "skipped_labelled": list(self.skipped_labelled),
            "cancelled": self.cancelled,
            "dpi": self.dpi,
            "lang": self.lang,
            "book": {
                "labelled_pages": self.book.labelled_pages,
                "manifest_items": self.book.manifest_items,
                "facet_gaps": self.book.facet_gaps,
            },
            "median_review_lines": self.median_review_lines(),
            "values": [v.as_dict() for v in self.values],
        }

    def heading_pt(self) -> str:
        skipped = self.skipped_labelled
        return (
            f"{len(self.values)} página(s) pontuada(s) a {self.dpi:.0f} DPI ({self.lang})"
            + (f", {len(skipped)} já rotulada(s) fora" if skipped else "")
            + (" — pontuação cancelada antes do fim" if self.cancelled else "")
            + f"; mediana de linhas em revisão {self.median_review_lines():.0f}."
        )

    def describe_pt(self, n: int = 5) -> str:
        if not self.values:
            return "Nenhuma página pontuada" + (" (cancelado)." if self.cancelled else ".")
        return "\n".join([self.heading_pt(), *(v.describe_pt() for v in self.top(n))])


def rank_pages(
    service: Any,
    project: LabelProject,
    document: str,
    *,
    sample: int = DEFAULT_SAMPLE,
    indices: Sequence[int] | None = None,
    dpi: float = 300.0,
    lang: str = "",
    manifest: GoldenManifest | None | Path | str = None,
    cancel: threading.Event | None = None,
    progress: Callable[[str], None] | None = None,
    score: Callable[[PageLabels], PageValue] | None = None,
) -> Ranking:
    """Recognise a spaced sample of the book and order it by value.

    ``manifest`` may be a loaded manifest, a path (read with the blind
    partition included — the queue only counts facets) or ``None``.
    ``score`` replaces :func:`value_of` (the benchmark's sabotage passes a
    constant).  ``cancel`` is checked between pages; the ranking returned
    then carries what was scored and ``cancelled=True``.
    """
    pdf = project.pdf_for(document)
    lang = lang or project.languages.get(document, "") or str(getattr(service, "lang", ""))
    if isinstance(manifest, (str, Path)):
        path = Path(manifest)
        manifest = load_manifest(path, include_blind=True) if path.is_file() else None
    book = BookContext.of(project, document, manifest)
    ranking = Ranking(document=document, dpi=float(dpi), lang=lang, book=book)
    wanted = list(indices) if indices is not None else sample_indices(page_count(pdf), sample)
    for index in wanted:
        if project.page(document, index) is not None:
            ranking.skipped_labelled.append(index)
            continue
        ranking.sampled.append(index)
    threshold = project.doubt_threshold
    for n, index in enumerate(ranking.sampled, start=1):
        if cancel is not None and cancel.is_set():
            ranking.cancelled = True
            break
        if progress is not None:
            progress(f"pontuando página {index} ({n}/{len(ranking.sampled)})")
        page = label_page(service, pdf, document, index, dpi=dpi, lang=lang)
        value = score(page) if score is not None else value_of(page, threshold=threshold, book=book)
        ranking.values.append(value)
    ranking.values.sort(key=lambda v: (-v.score, v.page_index))
    return ranking
