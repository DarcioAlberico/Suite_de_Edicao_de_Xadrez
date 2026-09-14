"""The confidence of a *diagram* — OCR_UI_ROADMAP passo 8 — fitted, gated, sabotaged.

``min_confidence`` is the confidence of a *square*; what the review queue, the
amber squares of the editor and the export gate need is the probability that
the **whole board is exact**.  This script runs the field set through the
production recogniser, collects one row of signals per matched diagram
(:mod:`caissa.vision.classify.confidence`), labels it against the annotation
— the corrected ruler of ``benchmarks/field_corrections.json`` applied in
memory, both rulers printed — and fits the packaged model by
leave-one-book-out cross-validation.

**The gate is discrimination, not calibration alone.**  With 93 of 94 exported
boards exact, a constant predictor has an ECE of ~0,01 and would pass a
calibration-only gate (``OCR_UI_ANALISE.md`` §2.4).  So the population is
every *matched* diagram with an annotated position — the boards the export
gate barred included, whose exactness the annotation knows — and the number
that has to clear the bar is the AUROC against that constant predictor.

Sabotage (``--sabotar ruido``): the signals are replaced by noise before
fitting.  AUROC must fall to ~0,5 and the gate must go red; a gate that stays
green on noise is blind.

Usage::

    .venv\\Scripts\\python.exe benchmarks\\diagram_confidence_gate.py --runs 3
    .venv\\Scripts\\python.exe benchmarks\\diagram_confidence_gate.py --runs 3 --sabotar ruido
    .venv\\Scripts\\python.exe benchmarks\\diagram_confidence_gate.py --runs 3 --fit   # rewrite the packaged weights
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "benchmarks") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from caissa.vision.classify.confidence import (  # noqa: E402
    FEATURE_NAMES,
    DiagramSignals,
    auroc,
    brier,
    expected_calibration_error,
    fit_logistic,
    packaged_weights_path,
    risk_coverage,
)
from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

REPORTS = REPO_ROOT / "benchmarks" / "reports"
CORRECTIONS = REPO_ROOT / "benchmarks" / "field_corrections.json"
AUROC_FLOOR = 0.90
ECE_CEILING = 0.03


def collect_rows(variant: str = "recall-pack") -> list[dict[str, Any]]:
    """One row per matched, annotated diagram of the field set."""
    from chess_diagram_ocr.board_detection import NoBoardDetectedError
    from chess_diagram_ocr.config import ACCEPT_MIN_CONFIDENCE, DEFAULT_MODEL_PATH
    from chess_diagram_ocr.field_eval import _match, load_field_set
    from chess_diagram_ocr.service import OcrService, RecognitionOptions
    from field_exact import _variant, apply_corrections

    root = cvoff_root()
    pages = load_field_set(root / "data" / "field_set.jsonl")
    corrected_pages, corrections = apply_corrections(list(pages), CORRECTIONS)
    corrected_by_key = {(p.pdf, p.page): p for p in corrected_pages}
    model = Path(DEFAULT_MODEL_PATH)
    if not model.is_file():
        model = root / "models" / "piece_classifier.pt"
    options = RecognitionOptions(model_path=model, max_boards=12, dpi=220)
    service = OcrService(model_path=options.model_path)

    rows: list[dict[str, Any]] = []
    with _variant(variant):
        for page in pages:
            if not page.reviewed:
                continue
            try:
                read = service.recognize_page(root / "PDF" / page.pdf, page.page, options=options)
            except NoBoardDetectedError:
                read = []
            matched = _match(page.diagrams, read)
            corrected = corrected_by_key.get((page.pdf, page.page), page)
            for index, annotated in enumerate(page.diagrams):
                slot = matched.get(index)
                if slot is None or not annotated.placement:
                    continue
                got = read[slot]
                signals = DiagramSignals.from_recognized(got)
                fixed = corrected.diagrams[index].placement if index < len(corrected.diagrams) else annotated.placement
                rows.append({
                    "pdf": page.pdf, "page": page.page, "diagram": index, "regime": page.regime or "",
                    "features": signals.as_dict(),
                    "vector": [float(v) for v in signals.vector()],
                    "exact_annotated": got.placement == annotated.placement,
                    "exact_corrected": got.placement == fixed,
                    "exported": (got.is_fatal is not True) and got.min_confidence >= ACCEPT_MIN_CONFIDENCE,
                    "min_confidence": float(got.min_confidence),
                })
    return rows


def leave_one_book_out(rows: list[dict[str, Any]], *, l2: float) -> np.ndarray:
    """Out-of-fold probabilities: each book scored by a model that never saw it."""
    books = sorted({r["pdf"] for r in rows})
    x = np.array([r["vector"] for r in rows], dtype=float)
    y = np.array([1.0 if r["exact_corrected"] else 0.0 for r in rows])
    out = np.zeros(len(rows))
    for book in books:
        train = np.array([r["pdf"] != book for r in rows])
        test = ~train
        if y[train].min() == y[train].max():
            # A fold without both classes cannot be fitted; the constant is
            # the honest prediction for it.
            out[test] = y[train].mean()
            continue
        model = fit_logistic(x[train], y[train], l2=l2)
        out[test] = model.probabilities(x[test])
    return out


def evaluate(rows: list[dict[str, Any]], probabilities: np.ndarray) -> dict[str, Any]:
    y = np.array([1.0 if r["exact_corrected"] else 0.0 for r in rows])
    constant = np.full(len(rows), y.mean())
    report: dict[str, Any] = {
        "n": len(rows), "positives": int(y.sum()), "negatives": int(len(y) - y.sum()),
        "auroc": auroc(y, probabilities), "auroc_constant": auroc(y, constant),
        "ece": expected_calibration_error(y, probabilities),
        "ece_constant": expected_calibration_error(y, constant),
        "brier": brier(y, probabilities), "brier_constant": brier(y, constant),
        "risk_coverage": risk_coverage(y, probabilities),
        "min_confidence_auroc": auroc(y, np.array([r["min_confidence"] for r in rows])),
        "by_regime": {},
    }
    for regime in sorted({r["regime"] for r in rows}):
        idx = np.array([r["regime"] == regime for r in rows])
        report["by_regime"][regime] = {
            "n": int(idx.sum()), "negatives": int((1 - y[idx]).sum()),
            "mean_probability": float(probabilities[idx].mean()),
            "exact_share": float(y[idx].mean()),
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--variant", default="recall-pack", choices=("baseline", "recall-pack"))
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--sabotar", choices=("ruido",), default=None)
    parser.add_argument("--fit", action="store_true",
                        help="grava os pesos ajustados em todos os 114 no pacote")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    runs = max(3, args.runs)

    started = time.perf_counter()
    rows = collect_rows(args.variant)
    for _ in range(runs - 1):
        again = collect_rows(args.variant)
        if [r["vector"] for r in again] != [r["vector"] for r in rows]:
            print("os sinais mudaram entre duas execuções idênticas: defeito, não ruído")
            return 3
    elapsed = time.perf_counter() - started

    if args.sabotar == "ruido":
        rng = np.random.default_rng(7)
        for row in rows:
            row["vector"] = [float(v) for v in rng.random(len(FEATURE_NAMES))]

    probabilities = leave_one_book_out(rows, l2=args.l2)
    report = evaluate(rows, probabilities)
    report["variant"] = args.variant
    report["sabotage"] = args.sabotar
    report["runs"] = runs
    report["seconds_per_run"] = round(elapsed / runs, 1)
    report["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    report["features"] = list(FEATURE_NAMES)
    ruler = {"annotated": sum(r["exact_annotated"] for r in rows),
             "corrected": sum(r["exact_corrected"] for r in rows)}
    report["exact_by_ruler"] = ruler
    gate_auroc = report["auroc"] >= AUROC_FLOOR
    gate_ece = report["ece"] <= ECE_CEILING
    report["gate"] = {"auroc": gate_auroc, "ece": gate_ece, "passed": gate_auroc and gate_ece}

    if args.fit and not args.sabotar:
        x = np.array([r["vector"] for r in rows], dtype=float)
        y = np.array([1.0 if r["exact_corrected"] else 0.0 for r in rows])
        model = fit_logistic(x, y, l2=args.l2)
        path = packaged_weights_path()
        model.save(path, note=f"ajustado em {len(rows)} diagramas casados do conjunto de campo, "
                              f"régua corrigida, variante {args.variant}; AUROC fora da dobra "
                              f"{report['auroc']:.3f}, ECE {report['ece']:.3f}")
        report["weights_written"] = str(path)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or REPORTS / f"diagram_confidence_{stamp}{'_' + args.sabotar if args.sabotar else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**report, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"diagramas casados com posição anotada: {report['n']} "
          f"(exatos: {ruler['annotated']} como anotado, {ruler['corrected']} régua corrigida; "
          f"negativos: {report['negatives']})")
    print(f"AUROC (fora da dobra, por livro): {report['auroc']:.3f}  |  preditor constante: "
          f"{report['auroc_constant']:.3f}  |  min_confidence sozinho: {report['min_confidence_auroc']:.3f}")
    print(f"ECE: {report['ece']:.4f} (constante {report['ece_constant']:.4f})  |  "
          f"Brier: {report['brier']:.4f} (constante {report['brier_constant']:.4f})")
    for point in report["risk_coverage"]:
        print(f"  limiar {point['threshold']:.2f}: cobertura {point['coverage']:.3f}, "
              f"exatidão condicional {point['conditional_exact']:.4f}")
    for regime, part in report["by_regime"].items():
        print(f"  {regime:16s} n={part['n']:3d} negativos={part['negatives']} "
              f"p médio={part['mean_probability']:.3f} exatos={part['exact_share']:.3f}")
    print(f"portão: AUROC ≥ {AUROC_FLOOR} {'✓' if gate_auroc else '✗'} · ECE ≤ {ECE_CEILING} "
          f"{'✓' if gate_ece else '✗'} → {'PASSOU' if report['gate']['passed'] else 'REPROVOU'}"
          f"{'  (sabotagem: ' + args.sabotar + ')' if args.sabotar else ''}")
    print(f"relatório: {out}")
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(main())
