"""The gate a candidate checkpoint has to pass before it may be measured on the field.

``docs/ROADMAP.md`` records two lab numbers that are **already at target** and therefore
have everything to lose: 0,999854 per square and 0,9906 per board on the test split of
``splits.csv``.  ``docs/quality/CORPUS.md`` 5.3 forbids measuring on train, and the rule
this front was given is explicit: *if a change improves ``field_exact`` but costs square
accuracy or legality, say so and drop it.*

So this runs the trunk's own ``evaluation.evaluate_dataset`` over the same split, for the
production checkpoint and for a candidate, in the same process, and prints them side by
side with the deltas.  It decides nothing; it makes the decision checkable.

Usage::

    .venv/Scripts/python.exe benchmarks/lab_gate.py --candidate models/piece_classifier_f4.pt
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()


def evaluate(model_path: Path, split: str, *, constrained: bool, rules: str = "c11") -> dict[str, Any]:
    from chess_diagram_ocr.checkpoint import load_checkpoint
    from chess_diagram_ocr.dataset import BoardFenDataset
    from chess_diagram_ocr.decode import CLASSIC_RULES, DEFAULT_RULES
    from chess_diagram_ocr.evaluation import evaluate_dataset
    from chess_diagram_ocr.inference import load_model
    from chess_diagram_ocr.model import DEFAULT_ARCH, ArchConfig
    from chess_diagram_ocr.splits import load_splits

    root = cvoff_root()
    checkpoint = load_checkpoint(model_path, map_location="cpu")
    arch = ArchConfig.from_version(checkpoint.arch_version) if checkpoint.arch_version else DEFAULT_ARCH
    model, device = load_model(model_path)
    dataset = BoardFenDataset(
        root / "data" / "labels.csv",
        root / "data" / "samples",
        split=split,
        splits=load_splits(root / "data" / "splits.csv"),
        arch=arch,
    )
    started = time.perf_counter()
    report = evaluate_dataset(
        dataset, model, device, split_name=split, model_path=model_path, constrained=constrained,
        rules=CLASSIC_RULES if rules == "classic" else DEFAULT_RULES,
    )
    return {
        "model": str(model_path),
        "split": split,
        "constrained": constrained,
        "rules": rules if constrained else "",
        "boards": report.board_count,
        "squares": report.square_count,
        "square_correct": report.square_correct,
        "square_accuracy": report.square_correct / report.square_count if report.square_count else 0.0,
        "boards_exact": report.boards_exact,
        "board_exact_accuracy": report.board_exact_accuracy,
        "boards_within_one": report.boards_within_one,
        "illegal_predictions": report.illegal_predictions,
        "decoder_helped": report.decoder_helped,
        "decoder_hurt": report.decoder_hurt,
        "wall_s": round(time.perf_counter() - started, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidate", type=Path, action="append", default=[])
    parser.add_argument("--split", default="test", choices=("test", "val"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--unconstrained", action="store_true", help="Also report raw argmax, without the solver.")
    parser.add_argument("--rules", default="c11", choices=("c11", "classic"),
                        help="C11 (ciclo 2): the decoder's rules -- 'classic' is the pre-C11 solver "
                             "(no bishop-colour promotion count, no adjacent-kings rule), the sabotage.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    parser.add_argument("--tag", default="")
    args = parser.parse_args(argv)
    if args.runs < 3:
        raise SystemExit("docs/quality/CORPUS.md 5.1: mediana de no minimo 3 execucoes.")

    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH

    production = Path(DEFAULT_MODEL_PATH)
    if not production.is_file():
        production = cvoff_root() / "models" / "piece_classifier.pt"

    models = [("production", production)] + [(p.stem, p) for p in args.candidate]
    modes = [True] + ([False] if args.unconstrained else [])

    rows: list[dict[str, Any]] = []
    for name, path in models:
        for constrained in modes:
            runs = [evaluate(path, args.split, constrained=constrained, rules=args.rules) for _ in range(args.runs)]
            invariant = ("square_correct", "boards_exact", "boards_within_one", "illegal_predictions")
            drift = {k for r in runs for k in invariant if r[k] != runs[0][k]}
            if drift:
                raise SystemExit(f"{name}: {sorted(drift)} mudou entre execucoes identicas -- isto e defeito.")
            row = dict(runs[0])
            row["name"] = name
            row["runs"] = args.runs
            row["wall_s"] = round(statistics.median(r["wall_s"] for r in runs), 2)
            rows.append(row)

    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    destination = args.out / f"lab_gate_{datetime.now().strftime('%Y%m%d_%H%M%S')}{tag}.json"
    destination.write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "rows": rows},
                                      indent=2), encoding="utf-8")

    header = (f"{'model':<26}{'dec':>5}{'rules':>8}{'boards':>8}{'square_acc':>13}{'board_exact':>13}"
              f"{'<=1':>6}{'illegal':>9}{'helped':>8}{'hurt':>6}")
    print("\n" + header)
    print("-" * len(header))
    baseline = None
    for row in rows:
        print(f"{row['name']:<26}{'yes' if row['constrained'] else 'no':>5}{row.get('rules', ''):>8}{row['boards']:>8}"
              f"{row['square_accuracy']:>13.6f}{row['board_exact_accuracy']:>13.4f}"
              f"{row['boards_within_one']:>6}{row['illegal_predictions']:>9}"
              f"{row['decoder_helped']:>8}{row['decoder_hurt']:>6}")
        if row["name"] == "production" and row["constrained"]:
            baseline = row
    if baseline is not None:
        print("\ndeltas against production (constrained):")
        for row in rows:
            if row["name"] == "production":
                continue
            d_sq = row["square_accuracy"] - baseline["square_accuracy"]
            d_bd = row["board_exact_accuracy"] - baseline["board_exact_accuracy"]
            verdict = "REGRESSION" if (d_sq < 0 or d_bd < 0) else "ok"
            print(f"  {row['name']:<24} square {d_sq:+.6f}  board_exact {d_bd:+.4f}"
                  f"  illegal {row['illegal_predictions'] - baseline['illegal_predictions']:+d}   {verdict}")
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
