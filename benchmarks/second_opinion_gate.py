"""Does the second opinion cover the squares the production model gets wrong?

OCR_UI_ROADMAP_C2 passo C3 (analysis §3.5, D4).  The trunk's S-66 measured, on the
Niemeijer, that the set of squares where two *independent* readers disagree covered the
production model's errors exactly (4/4, 23/23, 41/41).  That is the ruler this gate applies
to the field set's failures: for every diagram ``tools/f4_field_failures.py`` recorded as
read wrong (``failures.json``: the crop, the read placement, the annotated one and the wrong
squares), the second reader — ``tsoj/Chess_diagram_to_FEN``, a model of **another family**
than the production classifier — reads the same crop, and the gate counts how many of the
wrong squares fall in the disputed set.

    .venv/Scripts/python.exe benchmarks/second_opinion_gate.py --failures benchmarks/reports/f4_grade/failures.json
    .venv/Scripts/python.exe benchmarks/second_opinion_gate.py ... --sabotar copia

``--sabotar copia`` makes the second reader a copy of the first (the production reading is
handed back as the second opinion): the disputed set is empty, coverage is zero, and the gate
reproves — the reason the second reader has to be of another family.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

#: Share of wrong squares the disputed set has to cover.  Measured 2026-09-20 on the 11
#: failures of ``f4_grade`` (27 wrong squares): see ``OCR_UI_REPORT_C2.md`` §C3 for the
#: number the floor was set under.
FLOOR = 0.75
DEFAULT_READER = Path(os.environ.get("CVOFF_LOCAL_READER_PATH", r"C:\Python-Chess2\Chess_diagram_to_FEN"))


def _reader(path: Path) -> Any:
    from caissa.vision.classify.cvoff import ensure_cvoff_on_path

    ensure_cvoff_on_path()
    from chess_diagram_ocr.tsoj_reader import TsojDiagramReader

    return TsojDiagramReader(path)


def measure(failures: Path, *, reader_path: Path = DEFAULT_READER, sabotage: str = "") -> dict[str, Any]:
    import cv2

    from caissa.vision.classify.cvoff import ensure_cvoff_on_path

    ensure_cvoff_on_path()
    from chess_diagram_ocr.second_opinion import compare

    data = json.loads(failures.read_text(encoding="utf-8"))
    folder = failures.parent
    reader = None if sabotage == "copia" else _reader(reader_path)
    rows: list[dict[str, Any]] = []
    covered = wrong_total = 0
    for record in data.get("failures", ()):
        crop = folder / record["crop"]
        if not crop.is_file():
            rows.append({"n": record["n"], "skipped": f"recorte ausente: {crop.name}"})
            continue
        read = record["read_placement"]
        wrong = {int(s["index"]) for s in record.get("squares", ())}
        started = time.perf_counter()
        if reader is None:
            second = read                      # the sabotage: the first reader again
        else:
            image = cv2.cvtColor(cv2.imread(str(crop)), cv2.COLOR_BGR2RGB)
            try:
                second = reader.predict(image)
            except Exception as exc:  # noqa: BLE001 - a crop the second reader cannot read is a row
                rows.append({"n": record["n"], "skipped": f"segundo leitor falhou: {exc}"})
                continue
        seconds = time.perf_counter() - started
        opinion = compare(read, second, reader="tsoj" if reader else "cópia")
        disputed = set(opinion.disputed)
        hit = len(wrong & disputed)
        covered += hit
        wrong_total += len(wrong)
        rows.append({
            "n": record["n"], "pdf": record["pdf"], "page": record["page"],
            "wrong_squares": sorted(wrong), "disputed": sorted(disputed),
            "covered": hit, "coverage": round(hit / len(wrong), 3) if wrong else None,
            "disputed_count": len(disputed), "collapsed": opinion.collapsed,
            "second_placement": second, "seconds": round(seconds, 3),
        })
    coverage = covered / wrong_total if wrong_total else 0.0
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failures": str(failures), "reader": str(reader_path), "sabotage": sabotage,
        "floor": FLOOR, "wrong_squares": wrong_total, "covered": covered,
        "coverage": round(coverage, 4),
        "median_disputed": sorted(r["disputed_count"] for r in rows if "disputed_count" in r)[
            len([r for r in rows if "disputed_count" in r]) // 2] if any("disputed_count" in r for r in rows) else None,
        "passed": wrong_total > 0 and coverage >= FLOOR,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--failures", type=Path, default=REPO_ROOT / "benchmarks" / "reports" / "f4_grade" / "failures.json")
    parser.add_argument("--leitor", type=Path, default=DEFAULT_READER)
    parser.add_argument("--sabotar", choices=("", "copia"), default="")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)
    report = measure(args.failures, reader_path=args.leitor, sabotage=args.sabotar)
    for row in report["rows"]:
        if "skipped" in row:
            print(f"  {row['n']:2d}  {row['skipped']}")
            continue
        print(f"  {row['n']:2d}  {row['pdf'][:36]:36s} p{row['page']:<4d} erradas {len(row['wrong_squares']):2d} "
              f"cobertas {row['covered']:2d}  disputa {row['disputed_count']:2d}"
              f"{' (desabou)' if row['collapsed'] else ''}  {row['seconds']:.2f}s")
    print(f"\nportão C3: {'PASSOU' if report['passed'] else 'REPROVOU'} — {report['covered']} de "
          f"{report['wrong_squares']} casas erradas cobertas pela disputa ({report['coverage']:.1%}, "
          f"piso {FLOOR:.0%}); mediana de casas em disputa {report['median_disputed']}"
          + (f" (sabotagem: {args.sabotar})" if args.sabotar else ""))
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = args.out / f"second_opinion_{stamp}{'_' + args.sabotar if args.sabotar else ''}.json"
    target.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"gravado em {target}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
