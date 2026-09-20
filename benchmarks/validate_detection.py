"""Recall/precision guard for any change to board detection.

``docs/ASSETS.md`` 1.2 puts field detection recall at 0,9478 against a target of
0,99 -- detection is already the weakest link, so speed bought with recall is a
loss, not a trade. This script refuses to let that happen silently.

It does not invent a metric. It calls the trunk's own
``field_eval.evaluate_field`` over the 68 hand-annotated pages, which is exactly
what produced ``field_20260822_s99.json``, and reports ``detection_recall`` and
``detection_precision`` before and after a candidate change.

The change under test is supplied as ``--variant``; ``baseline`` applies nothing
and exists to prove the harness reproduces the published number on this machine
before anything is compared to it.  Since OCR_UI cycle 2 step A1 the trunk ships
the F3 recall pack as its default (``chess_diagram_ocr.config.DEFAULT_RECALL``),
so ``baseline`` and ``recall-pack`` are the same call and must print the same
row (0,9913 / 1,0000); ``raw`` is the detector with every recovery off (the old
baseline, 0,9478 / 0,9732) and is the sabotage that proves the gate can fail.

Run it in the trunk's own environment so the number is comparable:
    ChessVisionOFF_Puro/.venv/Scripts/python.exe benchmarks/validate_detection.py \\
        --variant baseline --variant downscale-0.5
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()


@contextlib.contextmanager
def downscaled_search(scale: float) -> Iterator[None]:
    """Run the contour search on a shrunken page, warp the winners at full size.

    Patches ``board_detection._extract_candidate_quads`` for the duration. The
    quads it returns are scaled back to full-page pixels, so ``detect_boards``
    still warps from the original image and the crop the classifier sees is
    unchanged in resolution -- only the *search* is cheaper.
    """
    import cv2
    import numpy as np

    from chess_diagram_ocr import board_detection as bd

    original = bd._extract_candidate_quads

    def patched(
        image_rgb: Any, rejected: Any = None, checker_floor: Any = bd.MIN_CHECKER_CONTRAST, _recall: Any = None
    ) -> Any:
        height, width = image_rgb.shape[:2]
        small = cv2.resize(
            image_rgb, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA
        )
        # The raw pass (`recall=None`): this variant is the record of half-scale *replacing*
        # the search, and the recall pack on top of it would measure something else.
        found = original(small, rejected, checker_floor, None)
        out = []
        for quad, score, bbox in found:
            back = np.asarray(quad, dtype=np.float32) / scale
            out.append((back, score, bd._bbox_from_quad(back)))
        return out

    bd._extract_candidate_quads = patched  # type: ignore[assignment]
    try:
        yield
    finally:
        bd._extract_candidate_quads = original  # type: ignore[assignment]


def _pack(**kwargs: Any) -> Any:
    """Late import: ``caissa.vision.detect.recall`` puts the trunk on ``sys.path`` itself."""
    from caissa.vision.detect.recall import recall_pack

    return recall_pack(**kwargs)


VARIANTS: dict[str, Any] = {
    "baseline": contextlib.nullcontext,
    # The speed lever of `docs/quality/F4GPU_REPORT.md` 7.4, kept for the record: it is
    # what shows that half-scale *replacing* the search costs recall (0,9391) and so may
    # not ship, however cheap it is.
    "downscale-0.75": lambda: downscaled_search(0.75),
    "downscale-0.5": lambda: downscaled_search(0.5),
    # The three recoveries of the trunk's `RecallOptions`, each measurable alone; the
    # variants other than `recall-pack` are forced by the harness of
    # `caissa.vision.detect.recall.recall_pack` because `field_eval` has no `recall=`.
    "raw": lambda: _pack(scales=(), rescue_squares=False, embedded_floor=None),
    "multiscale": lambda: _pack(rescue_squares=False, embedded_floor=None),
    "square-rescue": lambda: _pack(scales=(), embedded_floor=None),
    "embedded-floor": lambda: _pack(scales=(), rescue_squares=False),
    "recall-pack": lambda: _pack(),
}


def run_variant(name: str, options: Any, pages: Any, pdf_dir: Path) -> dict[str, Any]:
    from chess_diagram_ocr.field_eval import evaluate_field

    factory = VARIANTS[name]
    started = time.perf_counter()
    with factory():
        report = evaluate_field(pages, options=options, pdf_dir=pdf_dir)
    elapsed = time.perf_counter() - started
    data = report.as_dict()
    return {
        "variant": name,
        "wall_s": round(elapsed, 3),
        "pages": data["pages"],
        "annotated": data["annotated"],
        "detected": data["detected"],
        "matched": data["matched"],
        "false_positives": data["false_positives"],
        "detection_recall": data["detection_recall"],
        "detection_precision": data["detection_precision"],
        "field_exact": data["field_exact"],
        "export_rate": data["export_rate"],
        "seconds_per_diagram": data["seconds_per_diagram"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", action="append", default=[], choices=sorted(VARIANTS))
    parser.add_argument("--runs", type=int, default=1, help="Repeticoes por variante; a saida e a mediana.")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--max-boards", type=int, default=12)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)
    variants = args.variant or ["baseline"]

    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH
    from chess_diagram_ocr.field_eval import load_field_set
    from chess_diagram_ocr.service import RecognitionOptions

    root = cvoff_root()
    pages = load_field_set(root / "data" / "field_set.jsonl")
    model = DEFAULT_MODEL_PATH if Path(DEFAULT_MODEL_PATH).is_file() else root / "models" / "piece_classifier.pt"
    options = RecognitionOptions(model_path=Path(model), max_boards=args.max_boards, dpi=args.dpi)

    results: list[dict[str, Any]] = []
    for name in variants:
        runs = [run_variant(name, options, pages, root / "PDF") for _ in range(max(1, args.runs))]
        # Recall, precision and the counts are deterministic across runs -- the detector has
        # no randomness -- so the median is only doing work on the clock. Taking it over the
        # whole record anyway keeps the reported row internally consistent: the seconds and
        # the counts printed side by side came from the same run.
        chosen = sorted(runs, key=lambda item: item["wall_s"])[len(runs) // 2]
        chosen["runs"] = len(runs)
        chosen["wall_s_all"] = [item["wall_s"] for item in runs]
        differing = {
            key
            for item in runs
            for key in ("detection_recall", "detection_precision", "field_exact", "detected", "matched")
            if item[key] != runs[0][key]
        }
        if differing:
            raise SystemExit(
                f"variante {name}: {sorted(differing)} mudou entre execucoes identicas. "
                "O detector nao tem aleatoriedade; isto e defeito, nao ruido."
            )
        results.append(chosen)

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"validate_detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    destination.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "results": results}, indent=2),
        encoding="utf-8",
    )

    print(f"\n{'variant':<16}{'recall':>9}{'precision':>11}{'detected':>10}{'FP':>5}{'s/diagram':>12}{'wall s':>9}")
    for item in results:
        print(
            f"{item['variant']:<16}{item['detection_recall']:>9.4f}{item['detection_precision']:>11.4f}"
            f"{item['detected']:>10}{item['false_positives']:>5}{item['seconds_per_diagram']:>12.4f}"
            f"{item['wall_s']:>9.1f}"
        )
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
