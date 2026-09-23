"""Fit ``OcrServiceConfig.min_ink_coverage`` (OCR_UI_ROADMAP_C2 passo B14) on the calibration partition.

For every (item, stratum) of the **calibration** partition the production
service reads the rendered image with the coverage switch **off** (the
behaviour before B14), and the share of the page's letter-size ink under the
emitted words is measured on each region (:mod:`caissa.ocr.coverage`).  The
table says, for each candidate floor, how many readings it would flag and
how many of those had lost text (CER above ``--lost``) against how many were
good (CER at most ``--good``).  The development partition is measured the
same way and printed beside it, as the check -- never fitted on::

    python benchmarks/fit_ink_coverage.py --out benchmarks/reports/sol/ink_coverage_fit.json

Nothing is written to the source tree: the floor is a constant in
``OcrServiceConfig`` and the report says which number the table supports.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "benchmarks") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from bench_sol import MANIFEST, model_lang  # noqa: E402
from sol_corpus import render, tesseract_lang  # noqa: E402

from caissa.ocr.golden import Partition, items_sorted, load_manifest  # noqa: E402
from caissa.ocr.metrics import score_text  # noqa: E402

FLOORS = (0.70, 0.75, 0.80, 0.85, 0.88, 0.90, 0.92, 0.94, 0.96)


def measure(partition: Partition, strata: set[str] | None, limit: int | None) -> list[dict[str, Any]]:
    from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig
    from caissa.ocr.coverage import ink_coverage, ink_map

    manifest = load_manifest(MANIFEST)
    service = OcrService(None, config=OcrServiceConfig(ink_coverage=False))
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for item in items_sorted(manifest.items):
        if item.partition is not partition or item.is_control:
            continue
        for stratum in item.strata:
            if strata and stratum not in strata:
                continue
            rendered = render(item, stratum)
            if rendered is None:
                continue
            recognition = service.recognize_image(
                rendered.gray, dpi=float(rendered.dpi), lang=model_lang(tesseract_lang(item)))
            ink = ink_map(rendered.gray, float(rendered.dpi))
            coverages = [ink_coverage(r.result, ink.within(r.box_px)) for r in recognition.regions
                         if r.emits_text and not r.result.is_empty]
            measured = [c for c in coverages if c is not None]
            cer = score_text(item.truth, recognition.text).cer if recognition.answered else None
            rows.append({
                "id": item.id, "stratum": stratum, "decision": str(recognition.decision),
                "cer": None if cer is None else round(float(cer), 5),
                "coverage": round(min(measured), 4) if measured else None,
                "letters": ink.count,
            })
            if len(rows) % 25 == 0:
                print(f"  {partition}: {len(rows)} em {time.perf_counter() - started:.0f} s", flush=True)
            if limit and len(rows) >= limit:
                return rows
    return rows


def table(rows: list[dict[str, Any]], *, lost: float, good: float) -> list[dict[str, Any]]:
    answered = [r for r in rows if r["cer"] is not None and r["coverage"] is not None]
    lost_rows = [r for r in answered if r["cer"] > lost]
    good_rows = [r for r in answered if r["cer"] <= good]
    out = []
    for floor in FLOORS:
        flagged = [r for r in answered if r["coverage"] < floor]
        out.append({
            "floor": floor,
            "flagged": len(flagged),
            "lost_flagged": sum(1 for r in flagged if r["cer"] > lost),
            "lost_total": len(lost_rows),
            "good_flagged": sum(1 for r in flagged if r["cer"] <= good),
            "good_total": len(good_rows),
            "accepted_lost_flagged": sum(1 for r in flagged if r["cer"] > lost and r["decision"] == "accepted"),
            "accepted_lost_total": sum(1 for r in lost_rows if r["decision"] == "accepted"),
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strata", default="", help="comma-separated subset")
    parser.add_argument("--lost", type=float, default=0.10, help="CER above which a reading lost text")
    parser.add_argument("--good", type=float, default=0.02, help="CER at or below which it is good")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-dev", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    strata = {s for s in args.strata.split(",") if s} or None

    report: dict[str, Any] = {"lost": args.lost, "good": args.good, "strata": sorted(strata or [])}
    for partition in (Partition.CALIB, Partition.DEV):
        if partition is Partition.DEV and args.skip_dev:
            continue
        rows = measure(partition, strata, args.limit or None)
        report[str(partition)] = {"rows": rows, "table": table(rows, lost=args.lost, good=args.good)}
        print(f"\n{partition}: {len(rows)} leituras")
        print("  piso  sinaliza  perdidas  boas  aceitas-perdidas")
        for line in report[str(partition)]["table"]:
            print(f"  {line['floor']:.2f}  {line['flagged']:8d}  {line['lost_flagged']:3d}/{line['lost_total']:<3d}"
                  f"  {line['good_flagged']:3d}/{line['good_total']:<3d}"
                  f"  {line['accepted_lost_flagged']:3d}/{line['accepted_lost_total']}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
