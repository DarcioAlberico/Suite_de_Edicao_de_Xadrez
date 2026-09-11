"""Run the F4 fine-tune and write a candidate checkpoint. Decides nothing.

The candidate is graded afterwards, by three measurements that this script deliberately
does not run:

    benchmarks/lab_gate.py       --candidate models/piece_classifier_f4.pt   (must not regress)
    benchmarks/style_coverage.py --model     models/piece_classifier_f4.pt   (held-out styles)
    benchmarks/field_exact.py    --model     models/piece_classifier_f4.pt   (the target metric)

Disk: this writes one checkpoint (~8,7 MB) and nothing else.  The synthetic boards are
rendered into RAM and discarded -- ``docs/ROADMAP.md`` F0 asks for a disk check before
generating anything, and the cheapest way to pass it is not to generate files.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.train.finetune import FineTuneConfig, finetune  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boards", type=int, default=2500)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--real-repeat", type=int, default=3)
    parser.add_argument("--holdout", type=float, default=0.34)
    parser.add_argument("--print-like", action="store_true",
                        help="Hue shift off and disk themes off: ink on paper, not a wooden board.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "models" / "piece_classifier_f4.pt")
    args = parser.parse_args(argv)

    free_before = shutil.disk_usage(REPO_ROOT.anchor).free
    print(f"disco livre antes: {free_before / 2**30:.1f} GiB")
    if free_before < 5 * 2**30:
        raise SystemExit("menos de 5 GiB livres; nao inicie um treino aqui.")

    config = FineTuneConfig(
        synth_boards=args.boards,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        real_repeat=args.real_repeat,
        holdout=args.holdout,
        hue_prob=0.0 if args.print_like else 0.5,
        themes=not args.print_like,
    )
    record = finetune(config, args.out)

    free_after = shutil.disk_usage(REPO_ROOT.anchor).free
    record["disk_free_before_gib"] = round(free_before / 2**30, 2)
    record["disk_free_after_gib"] = round(free_after / 2**30, 2)
    print(f"disco livre depois: {free_after / 2**30:.1f} GiB "
          f"(delta {(free_after - free_before) / 2**20:+.0f} MiB)")

    reports = REPO_ROOT / "benchmarks" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    destination = reports / f"f4_finetune_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    destination.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"registro -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
