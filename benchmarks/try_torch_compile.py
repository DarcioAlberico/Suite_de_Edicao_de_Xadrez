"""Does ``torch.compile`` help the square classifier on Blackwell/Windows?

Deliverable (e) of front F4-GPU says: test it, and if it fails or is slower, say
so and move on -- do not fight it. This script is that test, and its output is
quotable either way.

It measures the eager forward and the compiled forward at the production batch
size (2048 cells = 16 diagrams x 2 orientations x 64 squares), reports the
compile wall time, and checks that the compiled model still produces the same
argmax on real cells. A compiled model that is faster and wrong is not a result.

Usage:
    .venv/Scripts/python.exe benchmarks/try_torch_compile.py
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "src", REPO_ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from caissa.vision.classify import load_classifier, trunk_model_path  # noqa: E402

BATCH = 2048
REPEATS = 20


def _bench(model: Any, batch: Any, torch: Any, *, repeats: int = REPEATS) -> list[float]:
    times: list[float] = []
    with torch.inference_mode():
        for _ in range(3):  # warm the allocator and any autotune
            model(batch)
        if batch.is_cuda:
            torch.cuda.synchronize()
        for _ in range(repeats):
            start = time.perf_counter()
            model(batch)
            if batch.is_cuda:
                torch.cuda.synchronize()
            times.append(time.perf_counter() - start)
    return times


def main() -> int:
    import torch

    from benchmarks.board_corpus import load_board_crops
    from caissa.vision.classify.preprocess import boards_to_cell_array

    result: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "torch": torch.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "batch": BATCH,
        "repeats": REPEATS,
    }

    classifier = load_classifier(trunk_model_path(), prefer="cuda", dtype="fp32")
    classifier.warmup(128)
    device = classifier.device
    result["device"] = device

    crops, _ = load_board_crops(32)
    cells = boards_to_cell_array([np.ascontiguousarray(b) for b in crops], classifier.arch)
    cells = np.resize(cells, (BATCH, *cells.shape[1:]))
    batch = torch.from_numpy(np.ascontiguousarray(cells)).to(device)

    eager = _bench(classifier.model, batch, torch)
    result["eager_ms"] = {
        "median": round(statistics.median(eager) * 1000, 4),
        "min": round(min(eager) * 1000, 4),
        "max": round(max(eager) * 1000, 4),
    }
    with torch.inference_mode():
        reference = classifier.model(batch).argmax(dim=1).cpu().numpy()

    try:
        import torch._dynamo  # noqa: F401

        start = time.perf_counter()
        compiled = torch.compile(classifier.model, mode="max-autotune-no-cudagraphs")
        with torch.inference_mode():
            compiled(batch)  # triggers the actual compilation
            if batch.is_cuda:
                torch.cuda.synchronize()
        result["compile_wall_s"] = round(time.perf_counter() - start, 3)

        timings = _bench(compiled, batch, torch)
        result["compiled_ms"] = {
            "median": round(statistics.median(timings) * 1000, 4),
            "min": round(min(timings) * 1000, 4),
            "max": round(max(timings) * 1000, 4),
        }
        with torch.inference_mode():
            got = compiled(batch).argmax(dim=1).cpu().numpy()
        mismatches = int((reference != got).sum())
        result["argmax_mismatches"] = mismatches
        result["ok"] = True
        result["speedup"] = round(
            result["eager_ms"]["median"] / result["compiled_ms"]["median"], 3
        )
    except Exception as exc:  # noqa: BLE001 - the failure IS the finding
        result["ok"] = False
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:2000]
        result["traceback"] = traceback.format_exc()[-3000:]

    destination = REPO_ROOT / "benchmarks" / "reports" / "torch_compile.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "traceback"}, indent=2, ensure_ascii=False))
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
