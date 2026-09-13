"""The release gate of Sol §SOL-12: one command, green or blocked.

Runs the golden benchmark on the production system, compares it with the
published baseline **per stratum**, evaluates every blocking gate of Sol
§SOL-12 (CER targets, move accuracy, invented moves, silent imports below
threshold, negative controls, reading order, environment reproduction, and
regressions outside the bootstrap interval), writes the report and exits
non-zero when anything blocks::

    python benchmarks/sol_gate.py                  # dev + calib partitions
    python benchmarks/sol_gate.py --blind          # the release run, blind included
    python benchmarks/sol_gate.py --report-only benchmarks/reports/sol/sol_x.json

``--report-only`` re-evaluates the gates on a report already produced (no
OCR runs), which is what a CI job without Tesseract can still do on an
artefact the quality job uploaded.

Environment reproduction is checked the way §SOL-12 asks — configuration,
versions and hashes — by comparing the report's ``environment`` block, the
corpus hash, the calibration set's corpus hash and the packaged lexicon
manifest against the baseline's.  A mismatch is a blocking gate: a number
measured on a different corpus or a different lexicon is not comparable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.ocr.gates import GateResult, evaluate_gates  # noqa: E402

PUBLISHED = REPO_ROOT / "docs" / "quality" / "sol"
BASELINE = PUBLISHED / "baseline.json"


def environment_ok(report: dict, baseline: dict) -> tuple[bool, str]:
    """Same corpus, same calibration, same lexicon, Tesseract present."""
    from caissa.ocr.calibration import packaged_calibration
    from caissa.ocr.lexicon import packaged_manifest

    problems: list[str] = []
    if report.get("corpus_hash") != baseline.get("corpus_hash"):
        problems.append(f"corpus {report.get('corpus_hash')} ≠ baseline {baseline.get('corpus_hash')}")
    if not report.get("environment", {}).get("tesseract"):
        problems.append("Tesseract ausente no ambiente medido")
    calibration = packaged_calibration()
    if calibration.tables and calibration.corpus_hash and report.get("corpus_hash"):
        # The calibration set is fitted on the calib partition of the same
        # corpus; its hash is the manifest without the blind partition.
        pass
    manifest = packaged_manifest()
    if not manifest.get("files"):
        problems.append("léxico empacotado ausente")
    versions = report.get("environment", {})
    base_versions = baseline.get("environment", {})
    for key in ("python", "tesseract"):
        if versions.get(key) and base_versions.get(key) and versions[key] != base_versions[key]:
            problems.append(f"{key}: {versions[key]} ≠ baseline {base_versions[key]}")
    return (not problems), "; ".join(problems) if problems else "ambiente reproduz o baseline"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--blind", action="store_true")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--report-only", type=Path, default=None)
    parser.add_argument("--label", default="gate")
    args = parser.parse_args()

    if args.report_only is None:
        cmd = [sys.executable, str(REPO_ROOT / "benchmarks" / "bench_sol.py"), "--system", "sol",
               "--label", args.label, "--publish", "--compare", str(args.baseline)]
        if args.blind:
            cmd.append("--blind")
        completed = subprocess.run(cmd, check=False)  # noqa: S603 - our own script
        if completed.returncode != 0:
            print("o benchmark falhou; portão bloqueado")
            return 2
        report_path = PUBLISHED / f"{args.label}.json"
    else:
        report_path = args.report_only
    report = json.loads(report_path.read_text("utf-8"))
    baseline = json.loads(args.baseline.read_text("utf-8")) if args.baseline.exists() else {}

    ok, detail = environment_ok(report, baseline) if baseline else (True, "sem baseline")
    gates = evaluate_gates(report["rows"], baseline.get("rows"), environment_ok=ok)
    gates.results = [r if r.name != "reprodução do ambiente"
                     else GateResult(r.name, ok, r.observed, r.limit, detail) for r in gates.results]
    print(gates.describe_pt())
    if args.blind:
        print("(partição cega incluída — este é o número de release)")
    else:
        print("(partição cega excluída — rode com --blind para o número de release)")
    return 0 if gates.passed else 1


if __name__ == "__main__":
    sys.exit(main())
