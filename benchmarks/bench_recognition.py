"""Stage-by-stage timing of the diagram recognition pipeline (front F4-GPU).

Why this exists
---------------
``docs/ASSETS.md`` 1.2 records ``seconds_per_diagram = 0,635`` from
``ChessVisionOFF_Puro/docs/metrics/field_20260822_s99.json``. That number is a
single wall clock around ``OcrService.recognize_page`` -- it says the pipeline is
slow and nothing about *where*. Optimising against it would be guessing.

This harness runs the same corpus (the 68 hand-annotated field pages in
``ChessVisionOFF_Puro/data/field_set.jsonl``) and splits the clock into the six
stages the work actually has:

    pdf_open | render | detect | split | preprocess | forward | decode

``split`` and ``preprocess`` are separated on purpose: cutting the 800x800 warp
into 64 crops is a view operation and nearly free, while turning each crop into a
64x64 float tensor is 64 OpenCV call pairs -- and only the measurement says which
of the two matters.

Modes
-----
``--mode baseline``
    The production path, re-assembled from the trunk's own functions so each
    stage can be timed. ``--verify`` checks the reassembly against the real
    ``OcrService.recognize_page`` and refuses to report if a single FEN differs.
``--mode accelerated``
    ``caissa.vision.classify``: whole-board preprocessing and one forward per
    page instead of one per diagram.

Every reported number is the **median of >= 3 runs** with the spread beside it. A
single run of a CUDA pipeline measures the allocator warming up.

Usage
-----
    .venv/Scripts/python.exe benchmarks/bench_recognition.py --runs 3
    .venv/Scripts/python.exe benchmarks/bench_recognition.py --mode accelerated \\
        --device cuda --dtype fp16 --runs 3
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import statistics
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

logger = logging.getLogger("bench")

STAGES = ("pdf_open", "render", "detect", "context", "split", "preprocess", "forward", "decode")


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Page:
    """One page of the benchmark corpus."""

    pdf: Path
    index: int
    label: str
    annotated_diagrams: int


def field_set_pages(limit: int | None = None) -> list[Page]:
    """The annotated field corpus, or ``[]`` if the trunk's PDFs are absent."""
    root = cvoff_root()
    jsonl = root / "data" / "field_set.jsonl"
    pdf_dir = root / "PDF"
    if not jsonl.is_file() or not pdf_dir.is_dir():
        return []

    pages: list[Page] = []
    with jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not record.get("reviewed"):
                continue
            path = pdf_dir / record["pdf"]
            if not path.is_file():
                logger.warning("PDF ausente, pagina ignorada: %s", path.name)
                continue
            pages.append(
                Page(
                    pdf=path,
                    index=int(record["page"]),
                    label=f"{record['pdf']}#{record['page']}",
                    annotated_diagrams=len(record.get("diagrams", [])),
                )
            )
    if limit is not None:
        pages = pages[:limit]
    return pages


def synthesize_corpus(destination: Path, pages: int = 12, per_page: int = 6) -> Path:
    """Render a multi-page PDF of synthetic diagrams, for machines without the acervo.

    Only used when ``ChessVisionOFF_Puro/PDF`` is empty or missing. The report
    says so explicitly when this path is taken -- synthetic pages are clean and
    flatter the detector, so their timings are not comparable to the field set.
    """
    import fitz  # type: ignore[import-untyped]

    import chess  # noqa: PLC0415

    destination.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    board = chess.Board()
    side = 150.0
    for page_number in range(pages):
        page = doc.new_page(width=595, height=842)
        for slot in range(per_page):
            column, row = slot % 2, slot // 2
            x0 = 60 + column * (side + 40)
            y0 = 60 + row * (side + 50)
            for rank in range(8):
                for file in range(8):
                    dark = (rank + file) % 2 == 1
                    rect = fitz.Rect(
                        x0 + file * side / 8,
                        y0 + rank * side / 8,
                        x0 + (file + 1) * side / 8,
                        y0 + (rank + 1) * side / 8,
                    )
                    page.draw_rect(rect, color=None, fill=(0.45, 0.45, 0.45) if dark else (1, 1, 1))
            for square, piece in board.piece_map().items():
                file = chess.square_file(square)
                rank = 7 - chess.square_rank(square)
                page.insert_text(
                    fitz.Point(x0 + file * side / 8 + side / 40, y0 + (rank + 1) * side / 8 - side / 40),
                    piece.symbol(),
                    fontsize=side / 10,
                    color=(0, 0, 0) if piece.color else (0.1, 0.1, 0.1),
                )
            page.draw_rect(fitz.Rect(x0, y0, x0 + side, y0 + side), color=(0, 0, 0), width=1)
        page.insert_text(fitz.Point(60, 800), f"pagina sintetica {page_number + 1}", fontsize=9)
    doc.save(str(destination))
    doc.close()
    return destination


def synthetic_pages(path: Path, page_count: int) -> list[Page]:
    return [Page(pdf=path, index=i, label=f"{path.name}#{i}", annotated_diagrams=0) for i in range(page_count)]


# --------------------------------------------------------------------------- #
# Timing accumulator
# --------------------------------------------------------------------------- #


@dataclass
class RunTotals:
    """Seconds per stage over one pass across the corpus."""

    seconds: dict[str, float] = field(default_factory=lambda: dict.fromkeys(STAGES, 0.0))
    pages: int = 0
    diagrams: int = 0
    cells: int = 0
    forwards: int = 0
    wall_s: float = 0.0
    fens: list[str] = field(default_factory=list)
    peak_vram_bytes: int = 0

    def add(self, stage: str, value: float) -> None:
        self.seconds[stage] += value

    @property
    def measured_s(self) -> float:
        return sum(self.seconds.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "stages_s": {k: round(v, 6) for k, v in self.seconds.items()},
            "measured_s": round(self.measured_s, 6),
            "wall_s": round(self.wall_s, 6),
            "pages": self.pages,
            "diagrams": self.diagrams,
            "cells": self.cells,
            "forwards": self.forwards,
            "seconds_per_diagram": round(self.wall_s / self.diagrams, 6) if self.diagrams else None,
            "seconds_per_page": round(self.wall_s / self.pages, 6) if self.pages else None,
            "peak_vram_bytes": self.peak_vram_bytes,
        }


class _Timer:
    """``with timer("detect"):`` -> adds the elapsed time to that stage."""

    def __init__(self, totals: RunTotals) -> None:
        self.totals = totals
        self._stage = ""
        self._start = 0.0

    def __call__(self, stage: str) -> _Timer:
        self._stage = stage
        return self

    def __enter__(self) -> _Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.totals.add(self._stage, time.perf_counter() - self._start)


# --------------------------------------------------------------------------- #
# Baseline: the production path, re-assembled with a clock on every stage
# --------------------------------------------------------------------------- #


def _baseline_page(page: Page, model: Any, device: str, options: Any, totals: RunTotals) -> list[str]:
    import cv2
    import torch

    from chess_diagram_ocr.board_detection import split_board_into_cells
    from chess_diagram_ocr.config import (
        CONSTRAINED_DECODING,
        ORIENTATION_DECISIVE_MARGIN,
        ORIENTATION_PAWN_PRIOR_MARGIN,
        PIECE_CLASSES,
        UNCERTAIN_SQUARE_THRESHOLD,
    )
    from chess_diagram_ocr.detection import detect_diagrams_in_pdf_page
    from chess_diagram_ocr.fen_utils import check_position
    from chess_diagram_ocr.inference import prediction_from_probs
    from chess_diagram_ocr.model import (
        DEFAULT_ARCH,
        preprocess_cell_to_tensor,
        with_coordinate_channels,
    )
    from chess_diagram_ocr.orientation import (
        ConfidenceMarginRule,
        CoordinateRule,
        OrientationEvidence,
        OrientationPolicy,
        PawnPriorRule,
        SingleLegalRule,
        TightMarginFallback,
    )
    from chess_diagram_ocr.pdf_io import opened, render_pdf_page
    from chess_diagram_ocr.pdf_text import contexts_for_pdf_page
    from chess_diagram_ocr.preprocess import IDENTITY, BoardNormalizer
    from chess_diagram_ocr.semantics import compose_fen, infer_side_to_move

    timer = _Timer(totals)
    arch = getattr(model, "arch", DEFAULT_ARCH)
    temperature = float(getattr(model, "temperature", 1.0))
    normalizador = BoardNormalizer(options.normalizer if options.normalizer is not None else IDENTITY)

    # Informational: how much of render/detect/context is just opening the file
    # again. `evaluate_field` passes a path, so the trunk opens the document
    # three times per page -- once per stage.
    with timer("pdf_open"):
        with opened(page.pdf) as _doc:
            pass

    with timer("render"):
        page_rgb = render_pdf_page(page.pdf, page.index, dpi=options.dpi)

    with timer("detect"):
        candidates = detect_diagrams_in_pdf_page(
            page.pdf, page.index, page_rgb, max_boards=options.max_boards
        )

    with timer("context"):
        contexts = contexts_for_pdf_page(
            page.pdf, page.index, [c.bbox_pdf for c in candidates], caption_reader=None
        )

    policy = OrientationPolicy(
        (
            CoordinateRule(),
            SingleLegalRule(),
            ConfidenceMarginRule(ORIENTATION_DECISIVE_MARGIN),
            PawnPriorRule(ORIENTATION_PAWN_PRIOR_MARGIN),
            TightMarginFallback(),
        )
    )

    fens: list[str] = []
    for index, candidate in enumerate(candidates):
        board_rgb = candidate.board_rgb
        views = [board_rgb, cv2.rotate(board_rgb, cv2.ROTATE_180)]

        cells_per_view = []
        with timer("split"):
            for view in views:
                cells_per_view.append(split_board_into_cells(normalizador.normalize(view)))

        with timer("preprocess"):
            tensors = [
                with_coordinate_channels(preprocess_cell_to_tensor(cell, arch), square, arch)
                for cells in cells_per_view
                for square, cell in enumerate(cells)
            ]
            batch = torch.stack(tensors, dim=0).to(device)

        with timer("forward"):
            with torch.inference_mode():
                probs = torch.softmax(model(batch) / temperature, dim=1)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            plane = probs.cpu().numpy().astype("float64")
        totals.cells += int(batch.shape[0])
        totals.forwards += 1

        with timer("decode"):
            matrices = plane.reshape(2, 64, len(PIECE_CLASSES))
            upright, flipped = (
                prediction_from_probs(
                    matrices[k],
                    uncertain_threshold=UNCERTAIN_SQUARE_THRESHOLD,
                    constrained=CONSTRAINED_DECODING,
                )
                for k in (0, 1)
            )
            oriented = policy.resolve(OrientationEvidence(upright=upright, flipped=flipped))
            prediction = oriented.prediction
            context = contexts[index] if index < len(contexts) else None
            side = infer_side_to_move(prediction.fen_board, context)
            check_position(compose_fen(prediction.fen_board, side))
            fens.append(prediction.fen_board)

    totals.diagrams += len(candidates)
    return fens


# --------------------------------------------------------------------------- #
# Accelerated: caissa.vision.classify
# --------------------------------------------------------------------------- #


def _accelerated_page(
    page: Page,
    classifier: Any,
    options: Any,
    totals: RunTotals,
    *,
    reuse_open: bool,
) -> list[str]:
    from chess_diagram_ocr.detection import detect_diagrams_in_pdf_page
    from chess_diagram_ocr.fen_utils import check_position
    from chess_diagram_ocr.pdf_io import opened, render_pdf_page
    from chess_diagram_ocr.pdf_text import contexts_for_pdf_page
    from chess_diagram_ocr.semantics import compose_fen, infer_side_to_move

    from caissa.vision.classify.page import PageTimings, predict_boards_batched

    timer = _Timer(totals)
    stack: Any = None
    with timer("pdf_open"):
        source: Any = page.pdf
        if reuse_open:
            stack = opened(page.pdf)
            source = stack.__enter__()

    try:
        with timer("render"):
            page_rgb = render_pdf_page(source, page.index, dpi=options.dpi)
        with timer("detect"):
            candidates = detect_diagrams_in_pdf_page(
                source, page.index, page_rgb, max_boards=options.max_boards
            )
        with timer("context"):
            contexts = contexts_for_pdf_page(
                source, page.index, [c.bbox_pdf for c in candidates], caption_reader=None
            )
    finally:
        if stack is not None:
            stack.__exit__(None, None, None)

    if not candidates:
        return []

    stage = PageTimings()
    oriented = predict_boards_batched(
        [c.board_rgb for c in candidates],
        classifier,
        mode=options.orientation,
        normalizer=options.normalizer,
        timings=stage,
    )
    # The fast path fuses splitting into the single whole-board resize, so there
    # is no separate `split` cost to report -- it is inside `preprocess`.
    totals.add("preprocess", stage.preprocess_s)
    totals.add("forward", stage.forward_s)
    totals.add("decode", stage.decode_s)
    totals.cells += stage.cells
    totals.forwards += stage.forwards

    fens: list[str] = []
    with timer("decode"):
        for index, item in enumerate(oriented):
            prediction = item.prediction
            context = contexts[index] if index < len(contexts) else None
            side = infer_side_to_move(prediction.fen_board, context)
            check_position(compose_fen(prediction.fen_board, side))
            fens.append(prediction.fen_board)
    totals.diagrams += len(candidates)
    return fens


def _service_page(page: Page, service: Any, options: Any, totals: RunTotals) -> list[str]:
    """The production entry point, timed exactly as ``field_eval.evaluate_field`` does.

    One wall clock around ``recognize_page``, path in and diagrams out -- no stage
    split, because this exists to reproduce the published number rather than to
    explain it. The whole cost lands in the ``decode`` bucket so that the totals
    still add up; the stage table is meaningless in this mode and the report says
    so.
    """
    from chess_diagram_ocr.board_detection import NoBoardDetectedError

    start = time.perf_counter()
    try:
        diagrams = service.recognize_page(page.pdf, page.index, options=options)
    except NoBoardDetectedError:
        diagrams = []
    totals.add("decode", time.perf_counter() - start)
    totals.diagrams += len(diagrams)
    return [d.placement for d in diagrams]


# --------------------------------------------------------------------------- #
# Verification of the instrumented reassembly
# --------------------------------------------------------------------------- #


def verify_against_service(pages: Sequence[Page], model_path: Path, options: Any, device: str) -> dict[str, Any]:
    """Run the real ``OcrService.recognize_page`` and compare FENs.

    A harness that measures something other than the pipeline is worse than no
    harness. This refuses to let that pass unnoticed.
    """
    from chess_diagram_ocr.board_detection import NoBoardDetectedError
    from chess_diagram_ocr.inference import load_model
    from chess_diagram_ocr.service import OcrService

    service = OcrService(model_path=model_path, loader=lambda p: load_model(p, device=device))
    model, resolved = service.load(model_path)

    mismatches: list[dict[str, Any]] = []
    checked = 0
    for page in pages:
        try:
            reference = [d.placement for d in service.recognize_page(page.pdf, page.index, options=options)]
        except NoBoardDetectedError:
            reference = []
        totals = RunTotals()
        mine = _baseline_page(page, model, resolved, options, totals)
        checked += len(reference)
        if reference != mine:
            mismatches.append({"page": page.label, "service": reference, "harness": mine})
    return {"pages": len(pages), "diagrams": checked, "mismatches": mismatches}


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


def _spread(values: Sequence[float]) -> dict[str, float]:
    return {
        "median": round(statistics.median(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean": round(statistics.fmean(values), 6),
        "stdev": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
    }


def _device_report() -> dict[str, Any]:
    try:
        from caissa.vision.runtime import get_device_info, probe_real_compute
    except Exception as exc:  # noqa: BLE001 - runs in the trunk's venv too
        return {"info": {"kind": "unknown", "usable": False}, "probe": {"ok": False, "error": repr(exc)}}

    info = get_device_info()
    payload: dict[str, Any] = {"info": info.as_dict()}
    try:
        payload["probe"] = probe_real_compute().as_dict()
    except Exception as exc:  # noqa: BLE001 - a failed probe is itself the finding
        payload["probe"] = {"ok": False, "error": repr(exc)}
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--mode",
        choices=("baseline", "accelerated", "service"),
        default="baseline",
        help=(
            "baseline = production path with a clock on each stage; "
            "accelerated = caissa.vision.classify; "
            "service = the untouched OcrService.recognize_page, wall clock only "
            "(this is what produced the 0,635 s/diagram in ASSETS.md)."
        ),
    )
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="auto")
    parser.add_argument("--dtype", choices=("fp32", "fp16"), default="fp32")
    parser.add_argument("--runs", type=int, default=3, help="Passes over the corpus. Minimum 3.")
    parser.add_argument("--pages", type=int, default=None, help="Cap the corpus size.")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--max-boards", type=int, default=12)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--reuse-open", action="store_true", help="Accelerated only: open each PDF once per page.")
    parser.add_argument("--no-fast-preprocess", action="store_true")
    parser.add_argument("--max-cells", type=int, default=2048)
    parser.add_argument("--verify", action="store_true", help="Check the harness against OcrService first.")
    parser.add_argument("--verify-pages", type=int, default=8)
    parser.add_argument("--tag", default="", help="Suffix for the report filename.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if args.runs < 3:
        parser.error("--runs deve ser >= 3: uma medicao unica de pipeline CUDA mede o allocator aquecendo.")

    ensure_cvoff_on_path()
    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH
    from chess_diagram_ocr.service import RecognitionOptions

    model_path = args.model or DEFAULT_MODEL_PATH
    if not Path(model_path).is_file():
        model_path = cvoff_root() / "models" / "piece_classifier.pt"

    synthetic = False
    pages = field_set_pages(limit=args.pages)
    if not pages:
        synthetic = True
        target = REPO_ROOT / "benchmarks" / "corpus" / "synthetic_diagrams.pdf"
        if not target.is_file():
            synthesize_corpus(target)
        pages = synthetic_pages(target, 12)[: args.pages or 12]
        logger.warning("Corpus SINTETICO: ChessVisionOFF_Puro/PDF esta vazio ou ausente.")

    options = RecognitionOptions(model_path=Path(model_path), max_boards=args.max_boards, dpi=args.dpi)

    device_report = _device_report()
    if args.device == "auto":
        device = "cuda" if args.mode == "accelerated" and device_report["info"]["usable"] else "cpu"
        if args.mode == "accelerated" and not device_report["info"]["usable"]:
            device = "cpu"
    else:
        device = args.device
    if device == "cuda" and device_report["info"]["kind"] != "cuda":
        raise SystemExit("--device cuda pedido, mas nenhuma GPU passou na verificacao de computacao real.")

    verification: dict[str, Any] | None = None
    if args.verify:
        verification = verify_against_service(
            pages[: args.verify_pages], Path(model_path), options, "cpu"
        )
        if verification["mismatches"]:
            print(json.dumps(verification, indent=2, ensure_ascii=False))
            raise SystemExit("O harness instrumentado divergiu do OcrService. Nao reporte estes numeros.")

    # ------------------------------------------------------------------ setup
    classifier: Any = None
    model: Any = None
    service: Any = None
    resolved = device
    if args.mode == "service":
        from chess_diagram_ocr.inference import load_model
        from chess_diagram_ocr.service import OcrService

        service = OcrService(
            model_path=Path(model_path), loader=lambda p: load_model(p, device=device)
        )
        _, resolved = service.load(Path(model_path))
    elif args.mode == "accelerated":
        from caissa.vision.classify import load_classifier

        classifier = load_classifier(
            Path(model_path),
            prefer=device,
            dtype=args.dtype,
            fast_preprocess=not args.no_fast_preprocess,
            max_cells_per_forward=args.max_cells,
        )
        resolved = classifier.device
        classifier.warmup(128)
        classifier.reset_peak_vram()
    else:
        from chess_diagram_ocr.inference import load_model

        model, resolved = load_model(Path(model_path), device=device)

    # ------------------------------------------------------------------- runs
    runs: list[RunTotals] = []
    for run_index in range(args.runs):
        totals = RunTotals()
        started = time.perf_counter()
        for page in pages:
            try:
                if args.mode == "service":
                    fens = _service_page(page, service, options, totals)
                elif args.mode == "accelerated":
                    fens = _accelerated_page(page, classifier, options, totals, reuse_open=args.reuse_open)
                else:
                    fens = _baseline_page(page, model, resolved, options, totals)
            except Exception as exc:  # noqa: BLE001
                logger.error("Falha em %s: %r", page.label, exc)
                raise
            totals.fens.extend(fens)
            totals.pages += 1
        totals.wall_s = time.perf_counter() - started
        if classifier is not None:
            totals.peak_vram_bytes = classifier.peak_vram_bytes()
        runs.append(totals)
        print(
            f"  run {run_index + 1}/{args.runs}: {totals.wall_s:7.3f} s wall, "
            f"{totals.diagrams} diagramas, "
            f"{totals.wall_s / max(totals.diagrams, 1):.4f} s/diagrama"
        )

    fen_sets = {tuple(r.fens) for r in runs}
    stable = len(fen_sets) == 1

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": args.mode,
        "device_requested": args.device,
        "device_used": resolved,
        "dtype": args.dtype,
        "runs": args.runs,
        "dpi": args.dpi,
        "max_boards": args.max_boards,
        "reuse_open": bool(args.reuse_open),
        "fast_preprocess": not args.no_fast_preprocess,
        "max_cells_per_forward": args.max_cells,
        "corpus": "synthetic" if synthetic else "ChessVisionOFF_Puro/data/field_set.jsonl",
        "corpus_pages": len(pages),
        "model": str(model_path),
        "python": platform.python_version(),
        "host": {"platform": platform.platform(), "processor": platform.processor()},
        "device_report": device_report,
        "verification": verification,
        "results_stable_across_runs": stable,
        "per_run": [r.as_dict() for r in runs],
        "seconds_per_diagram": _spread([r.wall_s / r.diagrams for r in runs if r.diagrams]),
        "seconds_per_page": _spread([r.wall_s / r.pages for r in runs if r.pages]),
        "wall_s": _spread([r.wall_s for r in runs]),
        "stages_s_per_diagram": {
            stage: _spread([r.seconds[stage] / r.diagrams for r in runs if r.diagrams]) for stage in STAGES
        },
        "diagrams": runs[0].diagrams,
        "cells": runs[0].cells,
        "forwards_per_run": runs[0].forwards,
        "peak_vram_bytes": max(r.peak_vram_bytes for r in runs),
    }
    if "torch" in sys.modules:
        summary["torch"] = sys.modules["torch"].__version__

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    destination = args.out / f"bench_{args.mode}_{resolved.replace(':', '')}_{args.dtype}{tag}_{stamp}.json"
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"mode={args.mode} device={resolved} dtype={args.dtype} runs={args.runs} pages={len(pages)}")
    print(f"diagrams/run={runs[0].diagrams}  cells/run={runs[0].cells}  forwards/run={runs[0].forwards}")
    print(f"FENs identical across runs: {stable}")
    print()
    print(f"{'stage':<12}{'median s/diagram':>18}{'min':>12}{'max':>12}{'share':>9}")
    median_total = summary["seconds_per_diagram"]["median"]
    for stage in STAGES:
        spread = summary["stages_s_per_diagram"][stage]
        share = 100.0 * spread["median"] / median_total if median_total else 0.0
        print(f"{stage:<12}{spread['median']:>18.4f}{spread['min']:>12.4f}{spread['max']:>12.4f}{share:>8.1f}%")
    print(f"{'TOTAL':<12}{median_total:>18.4f}{summary['seconds_per_diagram']['min']:>12.4f}"
          f"{summary['seconds_per_diagram']['max']:>12.4f}{100.0:>8.1f}%")
    if summary["peak_vram_bytes"]:
        print(f"\npeak VRAM (torch allocator): {summary['peak_vram_bytes'] / 1024**2:.1f} MiB")
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
