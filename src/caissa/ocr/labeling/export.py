"""What leaves a labelling project, and in which shape.

Three consumers:

* **the golden manifest** — :func:`manifest_items` turns every complete
  region into a ``pdf-scan`` item with the human truth; :func:`merge_into_manifest`
  writes it next to the existing items.  The benchmark then measures scans
  under the ``native`` stratum (the scan *is* the degradation) and reports
  them under the ``source`` facet;
* **calibration and audit** — :func:`corrections` in the shape of
  :meth:`caissa.ocr.review.ReviewQueue.corrections`, plus
  :func:`calibration_pairs` for a direct ``(confidence, correct)`` fit;
* **Tesseract's trainer** — :func:`write_ground_truth` renders one image per
  line with its ``.gt.txt`` and an ``index.jsonl`` that carries each line's
  partition, so the trainer can split development from calibration without
  reading the manifest.

The blind rule is enforced at every exit: a region whose manifest id hashes
to the blind partition contributes to the manifest (where blind items live,
hidden by default) and to nothing else.  The rule is per region because the
manifest's partition is per item and an item is a region.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ocr.calibration import pairs_from_alignment
from caissa.ocr.golden import (
    GoldenItem,
    GoldenManifest,
    GoldenRegion,
    Partition,
    Source,
    annotate_moves,
    load_manifest,
    save_manifest,
)
from caissa.ocr.metrics import move_tokens

from .model import LabelProject, LineLabel, PageLabels, RegionLabel

__all__ = [
    "GroundTruthReport",
    "calibration_pairs",
    "corrections",
    "manifest_items",
    "merge_into_manifest",
    "normalise_truth",
    "write_ground_truth",
]

MOVETEXT_MIN_MOVES = 6  # as build_manifest.py
SCRIPT_OF = {"ru": "cyrillic"}


def normalise_truth(text: str) -> str:
    """NFC, single spaces, no tabs — the form ``lstmtraining`` expects."""
    text = unicodedata.normalize("NFC", text.replace("\t", " "))
    return " ".join(text.split())


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #


def _genre(text: str) -> str:
    n = len(move_tokens(text))
    if n >= MOVETEXT_MIN_MOVES:
        return "movetext"
    return "mixed" if n else "prose"


def manifest_items(project: LabelProject, *, quality: str = "scan") -> list[GoldenItem]:
    """One ``pdf-scan`` item per complete region, blind ones included."""
    items: list[GoldenItem] = []
    for page in sorted(project.pages.values(), key=lambda p: (p.document, p.page_index)):
        for region in page.regions:
            if not region.complete:
                continue
            truth = "\n".join(normalise_truth(line.text) for line in region.lines if line.trainable)
            genre = _genre(truth)
            kind = "movetext" if genre == "movetext" and region.kind == "paragraph" else region.kind
            reviewers = sorted({line.reviewer for line in region.lines if line.reviewer})
            items.append(
                GoldenItem(
                    id=region.item_id(page.document, page.page_index),
                    source=Source.PDF_SCAN,
                    book=page.document,
                    page_index=page.page_index,
                    clip=region.rect,
                    prose_lang=region.prose_lang,
                    notation_lang=region.notation_lang,
                    script=SCRIPT_OF.get(region.prose_lang, "latin"),
                    genre=genre,
                    quality=quality,
                    regions=(
                        annotate_moves(
                            GoldenRegion(
                                kind=kind,
                                truth=truth,
                                box=region.rect,
                                reading_order=0,
                                prose_lang=region.prose_lang,
                                notation_lang=region.notation_lang,
                                start_fen=region.start_fen or None,
                            )
                        ),
                    ),
                    strata=("native",),
                    tags=("human-labelled", "scan"),
                    notes=f"rotulado por {', '.join(reviewers) or 'revisor'} "
                    f"({len(region.lines)} linhas, projeto {project.name})",
                )
            )
    return items


def merge_into_manifest(path: Path | str, items: Iterable[GoldenItem]) -> tuple[int, int]:
    """Add ``items`` to the manifest at ``path``, replacing items with the same id.

    The manifest is created when absent.  Returns ``(added, replaced)``.
    """
    path = Path(path)
    manifest = load_manifest(path, include_blind=True) if path.is_file() else GoldenManifest()
    by_id = {item.id: item for item in manifest.items}
    added = replaced = 0
    for item in items:
        if item.id in by_id:
            replaced += 1
        else:
            added += 1
        by_id[item.id] = item
    manifest.items = sorted(by_id.values(), key=lambda i: i.id)
    manifest.built_at = datetime.now(UTC).isoformat(timespec="seconds")
    problems = manifest.validate()
    if problems:
        raise ValueError("manifesto inválido após a fusão: " + "; ".join(problems[:5]))
    save_manifest(manifest, path)
    return added, replaced


# --------------------------------------------------------------------------- #
# Corrections and calibration
# --------------------------------------------------------------------------- #


def _decided(project: LabelProject) -> Iterable[tuple[PageLabels, RegionLabel, LineLabel]]:
    for page in sorted(project.pages.values(), key=lambda p: (p.document, p.page_index)):
        for region in page.regions:
            if page.region_blind(region):
                continue
            for line in region.lines:
                if line.trainable:
                    yield page, region, line


def corrections(project: LabelProject) -> list[dict[str, Any]]:
    """Human truth per line, minus blind regions — the review queue's shape."""
    out: list[dict[str, Any]] = []
    for page, region, line in _decided(project):
        out.append(
            {
                "document": page.document,
                "page_index": page.page_index,
                "rect": list(line.box),
                "kind": region.kind,
                "engine": region.engine,
                "hypothesis": line.hypothesis,
                "truth": line.text,
                "action": "edit" if line.truth != line.hypothesis else "accept",
                "reviewer": line.reviewer,
                "at": line.at,
                "words": [[w.text, round(w.confidence, 4)] for w in line.words],
                "lang": page.lang,
                "dpi": page.dpi,
            }
        )
    return out


def calibration_pairs(project: LabelProject) -> list[dict[str, Any]]:
    """``(raw confidence, correct)`` pairs per line, grouped by calibration facet.

    The facets are the ones the calibration needs: engine, language, DPI and region kind.
    """
    out: list[dict[str, Any]] = []
    for page, region, line in _decided(project):
        pairs = pairs_from_alignment(
            ((w.text, w.confidence) for w in line.words), line.text.split()
        )
        if pairs:
            out.append(
                {
                    "engine": region.engine,
                    "lang": page.lang,
                    "dpi": page.dpi,
                    "kind": region.kind,
                    "pairs": [[round(c, 4), ok] for c, ok in pairs],
                }
            )
    return out


def withheld_lines(project: LabelProject) -> int:
    """How many decided lines sit in blind regions and therefore stay inside."""
    return sum(
        1
        for page in project.pages.values()
        for region in page.regions
        if page.region_blind(region)
        for line in region.lines
        if line.trainable
    )


# --------------------------------------------------------------------------- #
# Ground truth for lstmtraining
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class GroundTruthReport:
    out_dir: Path
    written: int = 0
    withheld_blind: int = 0
    skipped_tiny: int = 0
    by_partition: dict[str, int] = field(default_factory=dict)
    by_document: dict[str, int] = field(default_factory=dict)
    chars: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "out_dir": str(self.out_dir),
            "written": self.written,
            "withheld_blind": self.withheld_blind,
            "skipped_tiny": self.skipped_tiny,
            "by_partition": dict(self.by_partition),
            "by_document": dict(self.by_document),
            "chars": self.chars,
        }


def _slug(text: str, limit: int = 24) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)[:limit].strip("_") or "doc"


def write_ground_truth(
    project: LabelProject,
    out_dir: Path | str,
    *,
    dpi: int = 300,
    pad_pt: float = 2.0,
    min_size_pt: float = 2.0,
) -> GroundTruthReport:
    """Render every trainable line as ``<name>.png`` + ``<name>.gt.txt``.

    ``index.jsonl`` records each line's document, page, partition and
    text length; the trainer splits on ``partition`` (``dev`` trains,
    ``calib`` evaluates) and blind regions never get here.
    """
    from PIL import Image

    from .recognise import render_gray

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = GroundTruthReport(out_dir=out)
    rows: list[dict[str, Any]] = []
    for page in sorted(project.pages.values(), key=lambda p: (p.document, p.page_index)):
        for region in page.regions:
            partition = page.region_partition(region)
            if partition is Partition.BLIND:
                report.withheld_blind += sum(1 for line in region.lines if line.trainable)
                continue
            for line in region.lines:
                if not line.trainable:
                    continue
                x0, y0, x1, y1 = line.box
                if (x1 - x0) < min_size_pt or (y1 - y0) < min_size_pt:
                    report.skipped_tiny += 1
                    continue
                text = normalise_truth(line.text)
                if not text:
                    continue
                name = f"{_slug(page.document)}_p{page.page_index}_r{region.index}_l{line.index}"
                clip = (x0 - pad_pt, y0 - pad_pt, x1 + pad_pt, y1 + pad_pt)
                gray = render_gray(page.pdf_path, page.page_index, dpi, clip=clip)
                Image.fromarray(gray).save(out / f"{name}.png")
                (out / f"{name}.gt.txt").write_text(text + "\n", encoding="utf-8")
                rows.append(
                    {
                        "name": name,
                        "document": page.document,
                        "page_index": page.page_index,
                        "region": region.index,
                        "line": line.index,
                        "kind": region.kind,
                        "partition": str(partition),
                        "lang": page.lang,
                        "chars": len(text),
                        "edited": line.truth != line.hypothesis,
                    }
                )
                report.written += 1
                report.chars += len(text)
                report.by_partition[str(partition)] = report.by_partition.get(str(partition), 0) + 1
                report.by_document[page.document] = report.by_document.get(page.document, 0) + 1
    with (out / "index.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "report.json").write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return report


def partition_split(index_path: Path | str) -> dict[str, list[str]]:
    """Names of the ground-truth lines per partition, from ``index.jsonl``."""
    split: dict[str, list[str]] = {str(Partition.DEV): [], str(Partition.CALIB): []}
    with Path(index_path).open(encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            split.setdefault(str(row.get("partition", "dev")), []).append(str(row["name"]))
    return split
