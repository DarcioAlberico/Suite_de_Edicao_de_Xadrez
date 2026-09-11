"""Throughput of a whole-acervo run: pages in parallel, one GPU.

Two different questions hide behind "seconds per diagram", and the SPEC gate only
asks the first one:

*Latency* -- how long one page takes end to end, which is what
``field_eval.evaluate_field`` times and what ``ASSETS.md`` publishes as 0,635.
That number is bounded by the slowest serial stage and no amount of batching
moves it.

*Throughput* -- what a 500-PDF unattended run actually costs per diagram
(persona P4 in ``SPEC`` 1). Once the classifier is off the critical path, what
remains is PyMuPDF rendering, OpenCV detection, PDF text extraction and the
constrained decoder: four single-threaded CPU stages on a 6-core machine, all
embarrassingly parallel *across pages*.

This script measures the second number honestly and reports it beside the first,
labelled, so nobody mistakes one for the other.

VRAM discipline
---------------
With ``--device cuda`` every worker builds its own CUDA context. ADR-0004 caps
the whole application at 7,0 GB shared, so ``--max-cells`` is lowered from the
single-process default to keep N workers inside the budget, and the script prints
the measured total.

Usage:
    .venv/Scripts/python.exe benchmarks/bench_batch_throughput.py --workers 6 --device cpu
    .venv/Scripts/python.exe benchmarks/bench_batch_throughput.py --workers 4 --device cuda \\
        --max-cells 512
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "src", REPO_ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

_WORKER: dict[str, Any] = {}


def _init_worker(model_path: str, device: str, dtype: str, max_cells: int, threads: int) -> None:
    """One classifier per worker process, built once."""
    for name in ("path",):
        _WORKER.pop(name, None)
    sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT)]

    import torch

    torch.set_num_threads(max(1, threads))

    from caissa.vision.classify import load_classifier
    from caissa.vision.classify.cvoff import ensure_cvoff_on_path

    ensure_cvoff_on_path()  # must precede the trunk import below
    from chess_diagram_ocr.service import RecognitionOptions  # noqa: PLC0415

    classifier = load_classifier(Path(model_path), prefer=device, dtype=dtype, max_cells_per_forward=max_cells)
    classifier.warmup(64)
    classifier.reset_peak_vram()
    _WORKER["classifier"] = classifier
    _WORKER["options"] = RecognitionOptions(model_path=Path(model_path), max_boards=12, dpi=220)


def _work(item: tuple[str, int]) -> dict[str, Any]:
    from chess_diagram_ocr.board_detection import NoBoardDetectedError

    from caissa.vision.classify.page import PageTimings, recognize_page_batched

    pdf, index = item
    classifier = _WORKER["classifier"]
    options = _WORKER["options"]
    timings = PageTimings()
    started = time.perf_counter()
    try:
        diagrams = recognize_page_batched(Path(pdf), index, classifier, options=options, timings=timings)
    except NoBoardDetectedError:
        diagrams = []
    elapsed = time.perf_counter() - started
    return {
        "pdf": Path(pdf).name,
        "page": index,
        "diagrams": len(diagrams),
        "placements": [d.placement for d in diagrams],
        "wall_s": elapsed,
        "pid": os.getpid(),
        "peak_vram_bytes": classifier.peak_vram_bytes(),
        "stages": timings.as_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--dtype", choices=("fp32", "fp16"), default="fp32")
    parser.add_argument("--max-cells", type=int, default=512)
    parser.add_argument("--threads-per-worker", type=int, default=1)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--pages", type=int, default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    parser.add_argument("--tag", default="")
    args = parser.parse_args(argv)
    if args.runs < 3:
        parser.error("--runs deve ser >= 3")

    from benchmarks.bench_recognition import field_set_pages

    from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path

    ensure_cvoff_on_path()
    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH  # noqa: PLC0415

    pages = field_set_pages(limit=args.pages)
    if not pages:
        raise SystemExit("Sem corpus: ChessVisionOFF_Puro/PDF ausente.")
    model = Path(DEFAULT_MODEL_PATH)
    if not model.is_file():
        model = cvoff_root() / "models" / "piece_classifier.pt"
    items = [(str(p.pdf), p.index) for p in pages]

    per_run: list[dict[str, Any]] = []
    placements: list[tuple[str, ...]] = []
    # The pool is built ONCE, outside the timed region. Spawning six Windows
    # processes that each import torch and load a checkpoint costs ~15 s; timing
    # that as if it were recognition would measure process creation and call it
    # throughput. A real batch run pays it once for 500 PDFs, not once per page.
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_init_worker,
        initargs=(str(model), args.device, args.dtype, args.max_cells, args.threads_per_worker),
    ) as pool:
        print(f"aquecendo {args.workers} processos ...")
        list(pool.map(_work, items[: args.workers], chunksize=1))
        for run_index in range(args.runs):
            started = time.perf_counter()
            results = list(pool.map(_work, items, chunksize=1))
            wall = time.perf_counter() - started
            diagrams = sum(r["diagrams"] for r in results)
            peak = max((r["peak_vram_bytes"] for r in results), default=0)
            workers_seen = len({r["pid"] for r in results})
            per_run.append(
                {
                    "wall_s": round(wall, 3),
                    "diagrams": diagrams,
                    "pages": len(results),
                    "seconds_per_diagram": round(wall / diagrams, 6) if diagrams else None,
                    "seconds_per_page": round(wall / len(results), 6),
                    "peak_vram_bytes_per_worker": peak,
                    "distinct_worker_pids": workers_seen,
                }
            )
            placements.append(
                tuple(
                    placement
                    for r in sorted(results, key=lambda r: (r["pdf"], r["page"]))
                    for placement in r["placements"]
                )
            )
            print(
                f"  run {run_index + 1}/{args.runs}: {wall:7.3f} s wall, {diagrams} diagramas, "
                f"{wall / max(diagrams, 1):.4f} s/diagrama, {workers_seen} processos"
            )

    stable = len(set(placements)) == 1
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "workers": args.workers,
        "device": args.device,
        "dtype": args.dtype,
        "max_cells_per_forward": args.max_cells,
        "threads_per_worker": args.threads_per_worker,
        "corpus_pages": len(pages),
        "runs": args.runs,
        "results_stable_across_runs": stable,
        "per_run": per_run,
        "seconds_per_diagram": {
            "median": round(statistics.median([r["seconds_per_diagram"] for r in per_run]), 6),
            "min": round(min(r["seconds_per_diagram"] for r in per_run), 6),
            "max": round(max(r["seconds_per_diagram"] for r in per_run), 6),
        },
        "peak_vram_bytes_per_worker": max(r["peak_vram_bytes_per_worker"] for r in per_run),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    destination = args.out / (
        f"bench_throughput_{args.device}_{args.workers}w_{args.dtype}{tag}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    median = summary["seconds_per_diagram"]["median"]
    print(f"\nworkers={args.workers} device={args.device} dtype={args.dtype} max_cells={args.max_cells}")
    print(f"FENs identical across runs: {stable}")
    print(f"THROUGHPUT: {median:.4f} s/diagrama (mediana de {args.runs}), "
          f"{1.0 / median:.1f} diagramas/s")
    if summary["peak_vram_bytes_per_worker"]:
        total = summary["peak_vram_bytes_per_worker"] * args.workers
        print(f"pico VRAM por worker (allocator): {summary['peak_vram_bytes_per_worker'] / 1024**2:.1f} MiB"
              f"  -> {total / 1024**2:.1f} MiB somados em {args.workers} processos")
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
