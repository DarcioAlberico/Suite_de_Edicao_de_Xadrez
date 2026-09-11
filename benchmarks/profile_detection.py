"""Where the 95 ms/page of contour detection actually goes.

``board_detection._extract_candidate_quads`` is OpenCV, not torch, so no GPU helps
it. ``docs/ASSETS.md`` 2.1 records the cost of the diagonal repair pass -- 61,6 ->
95,0 ms/page, "+54%, and it is in evaluating more candidates, not in binarising
one more time". This script checks that claim on the field corpus and says which
of the four suspects dominates:

    threshold   adaptiveThreshold + the three morphological passes
    contours    findContours + approxPolyDP over all three binarisations
    geometry    _contour_geometry_score, _bbox_visible_ratio, quad-inside ratio
    score       warp_from_quad(320) + _small_gray + _checker_score + _grid_score

The last one is the per-candidate 320x320 warp, which runs once for every quad
that survives the geometry gate -- and there are far more of those than there are
diagrams.

It also measures a downscale-then-refine variant: run the search on a half-scale
page, then re-warp the survivors at full resolution. That variant is only a
candidate for shipping if ``benchmarks/validate_detection.py`` shows recall and
precision unchanged; speed bought with recall is a loss -- and it is:
``docs/quality/F3_REPORT.md`` 4 measures half-scale *replacing* the search at
recall 0,9391 against the trunk's 0,9478, so it does not ship on its own.

What does ship is ``caissa.vision.detect.recall``, which uses the same half-scale
page as an **extra** source rather than a replacement. That costs time instead of
saving it, so this script times it too: the ``--pack`` rows are the price of
0,9478 -> 0,9913 recall, on the same pages and the same clock as everything else.

Usage:
    .venv/Scripts/python.exe benchmarks/profile_detection.py --pages 24 --runs 3
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from caissa.vision.classify.cvoff import ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

PARTS = ("threshold", "contours", "geometry", "warp_score", "dedupe")


@dataclass
class Profile:
    seconds: dict[str, float] = field(default_factory=lambda: dict.fromkeys(PARTS, 0.0))
    counts: Counter[str] = field(default_factory=Counter)

    def as_dict(self) -> dict[str, Any]:
        return {
            "seconds": {k: round(v, 6) for k, v in self.seconds.items()},
            "counts": dict(self.counts),
            "total_s": round(sum(self.seconds.values()), 6),
        }


def profile_page(image_rgb: np.ndarray, profile: Profile, *, scale: float = 1.0) -> list[Any]:
    """Re-run ``_extract_candidate_quads`` with a clock on each part.

    The body mirrors the trunk's function exactly, including the order of the
    gates. It is a measuring copy, not a replacement: nothing here is imported by
    production code.
    """
    import cv2

    from chess_diagram_ocr import board_detection as bd

    if scale != 1.0:
        height, width = image_rgb.shape[:2]
        search = cv2.resize(
            image_rgb, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA
        )
    else:
        search = image_rgb

    start = time.perf_counter()
    gray = cv2.cvtColor(search, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh_base = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 8
    )
    passes = bd._threshold_passes(thresh_base)
    profile.seconds["threshold"] += time.perf_counter() - start

    image_area = float(search.shape[0] * search.shape[1])
    raw: list[tuple[np.ndarray, float, tuple[int, int, int, int], float]] = []

    for thresh in passes:
        start = time.perf_counter()
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        quads: list[np.ndarray] = []
        for contour in contours:
            if len(contour) < 4:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) == 4:
                quads.append(approx.reshape(4, 2).astype(np.float32))
            else:
                quads.append(cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.float32))
        profile.seconds["contours"] += time.perf_counter() - start
        profile.counts["contours"] += len(contours)
        profile.counts["quads"] += len(quads)

        survivors: list[np.ndarray] = []
        start = time.perf_counter()
        for quad in quads:
            geom = bd._contour_geometry_score(quad, image_area)
            if geom <= 0:
                continue
            bbox = bd._bbox_from_quad(quad)
            if (
                bd._bbox_visible_ratio(bbox, search.shape) < bd.MIN_VISIBLE_RATIO
                or bd._quad_point_inside_ratio(quad, search.shape) < bd.MIN_QUAD_INSIDE_RATIO
            ):
                continue
            survivors.append(quad)
        profile.seconds["geometry"] += time.perf_counter() - start
        profile.counts["past_geometry"] += len(survivors)

        start = time.perf_counter()
        for quad in survivors:
            small = bd._small_gray(bd.warp_from_quad(search, quad, target_size=320))
            checker = bd._checker_score(small)
            if bd.MIN_CHECKER_CONTRAST is not None and checker <= bd.MIN_CHECKER_CONTRAST:
                continue
            pattern = bd._texture_from_parts(checker, bd._grid_score(small))
            geom = bd._contour_geometry_score(quad, image_area)
            raw.append(
                (
                    quad,
                    float(geom * (0.55 + 0.45 * pattern)),
                    bd._bbox_from_quad(quad),
                    float(cv2.contourArea(quad.astype(np.float32))),
                )
            )
        profile.seconds["warp_score"] += time.perf_counter() - start
        profile.counts["scored"] += len(survivors)

    start = time.perf_counter()
    raw.sort(key=lambda item: item[1], reverse=True)
    deduped: list[Any] = []
    for candidate in raw:
        if any(bd._bbox_iou(candidate[2], kept[2]) > bd.DEDUPE_IOU for kept in deduped):
            continue
        deduped.append(candidate)
    profile.seconds["dedupe"] += time.perf_counter() - start
    profile.counts["deduped"] += len(deduped)
    return deduped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pages", type=int, default=24)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--scales", default="1.0,0.5", help="Search scales to compare.")
    parser.add_argument(
        "--packs",
        default="baseline,recall-pack",
        help="Variantes de caissa.vision.detect.recall a cronometrar em detect_boards.",
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)
    if args.runs < 3:
        parser.error("--runs deve ser >= 3")

    from benchmarks.bench_recognition import field_set_pages

    from chess_diagram_ocr.board_detection import detect_boards
    from chess_diagram_ocr.pdf_io import render_pdf_page

    pages = field_set_pages(limit=args.pages)
    if not pages:
        raise SystemExit("Sem corpus: ChessVisionOFF_Puro/PDF esta ausente.")

    print(f"renderizando {len(pages)} paginas a {args.dpi} dpi ...")
    images = [render_pdf_page(p.pdf, p.index, dpi=args.dpi) for p in pages]

    summary: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pages": len(pages),
        "dpi": args.dpi,
        "runs": args.runs,
        "scales": {},
    }

    for scale_text in args.scales.split(","):
        scale = float(scale_text)
        per_run: list[Profile] = []
        for _ in range(args.runs):
            profile = Profile()
            for image in images:
                profile_page(image, profile, scale=scale)
            per_run.append(profile)
        medians = {
            part: statistics.median([p.seconds[part] / len(pages) for p in per_run]) for part in PARTS
        }
        total = statistics.median([sum(p.seconds.values()) / len(pages) for p in per_run])
        summary["scales"][scale_text] = {
            "ms_per_page": {k: round(v * 1000, 3) for k, v in medians.items()},
            "total_ms_per_page": round(total * 1000, 3),
            "counts_per_page": {k: round(v / len(pages) / args.runs, 2) for k, v in per_run[0].counts.items()},
        }

    # The trunk's own entry point, for a number that includes everything -- once as it
    # ships today and once under each recall variant, so the cost of the recall recovery is
    # on the same clock as the number it is compared against.
    import contextlib

    from caissa.vision.detect.recall import recall_pack

    pack_factories: dict[str, Any] = {
        "baseline": contextlib.nullcontext,
        "multiscale": lambda: recall_pack(rescue_squares=False, embedded_floor=None),
        "square-rescue": lambda: recall_pack(scales=(), embedded_floor=None),
        "recall-pack": lambda: recall_pack(embedded_floor=None),
    }
    summary["detect_boards_ms_per_page"] = {}
    for name in args.packs.split(","):
        name = name.strip()
        if not name:
            continue
        if name not in pack_factories:
            raise SystemExit(f"variante desconhecida: {name!r}; use {sorted(pack_factories)}")
        whole: list[float] = []
        for _ in range(args.runs):
            start = time.perf_counter()
            with pack_factories[name]():
                for image in images:
                    detect_boards(image_rgb=image, max_boards=12)
            whole.append((time.perf_counter() - start) / len(pages))
        summary["detect_boards_ms_per_page"][name] = {
            "median": round(statistics.median(whole) * 1000, 3),
            "min": round(min(whole) * 1000, 3),
            "max": round(max(whole) * 1000, 3),
        }

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"profile_detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    for name, timing in summary["detect_boards_ms_per_page"].items():
        print(f"detect_boards {name:<16}{timing['median']:8.1f} ms/pagina  (min {timing['min']:.1f}, max {timing['max']:.1f})")
    for scale_text, data in summary["scales"].items():
        print(f"\nescala {scale_text}: {data['total_ms_per_page']:.1f} ms/pagina")
        for part in PARTS:
            value = data["ms_per_page"][part]
            share = 100.0 * value / data["total_ms_per_page"] if data["total_ms_per_page"] else 0
            print(f"  {part:<12}{value:8.2f} ms{share:8.1f}%")
        print(f"  contagens/pagina: {data['counts_per_page']}")
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
