"""The field's ruler for the production model decision (OCR_UI_ROADMAP_C2 passo C17; análise §10.2).

Phase 3 compared the C4 candidates by the laboratory and by the exported-and-wrong count
at the production gate (0,80); phase 4 showed both rulers are blind to the damage that
matters (``OCR_UI_REPORT_C2_FASE4.md`` §C16: ``x10`` exports 72 diagrams instead of 104 with
the same laboratory numbers) and that a less confident model is not a worse one, it is
another *scale*.  Comparing two models at one fixed threshold compares two scales.

This harness runs the field set once per checkpoint (``--runs`` times, asserting that the
per-diagram rows do not move -- recognition is deterministic, and ``CORPUS.md`` 5.1 asks for
three) and, from the rows ``field_eval.FieldReport.diagrams`` keeps, draws the
**risk × coverage curve**: for every gate threshold, how many diagrams leave for the PGN and
how many of those are wrong.  The numbers that answer §10.2:

- the production gate (0,80): exported, exported-and-wrong, exported-and-exact;
- the total exact (argmax, every matched diagram) -- what a reviewer would have to fix;
- **the most exact diagrams exported with at most 0, 1 and 2 wrong**, and the threshold
  that achieves it -- the comparison at equal risk, which no fixed gate gives;
- the area under the risk-coverage curve (lower is better).

Usage::

    .venv/Scripts/python.exe benchmarks/model_ruler.py --runs 3 --tag f5_c17
    .venv/Scripts/python.exe benchmarks/model_ruler.py --models production,c4_aug0_s42 --runs 3

The sabotage (``--sabotar embaralhar``) shuffles the exactness labels across diagrams with a
fixed seed: a ruler that still orders the models the same way would be reading the
confidences, not the truth.  ``--linhas-de`` summarises the rows a previous run saved instead
of measuring the field again, which is how the sabotage runs on the real rows::

    .venv/Scripts/python.exe benchmarks/model_ruler.py --sabotar embaralhar \\
        --linhas-de benchmarks/reports/model_ruler_20260923_043817_f5_c17.json --tag f5_c17_sabotado
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "benchmarks") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

GATE = 0.80
THRESHOLDS = tuple(round(0.30 + 0.01 * n, 2) for n in range(70))   # 0,30 … 0,99
BUDGETS = (0, 1, 2)
DEFAULT_MODELS = (
    "production",
    *(f"c4_{v}_s{s}" for v in ("aug0", "mhsp", "mhspe", "e") for s in (42, 43, 44)),
    "c4_x10_s42", "c4_w3_s42",
)


# --------------------------------------------------------------------------- #
# The curve (pure; the tests pin it)
# --------------------------------------------------------------------------- #


def comparable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The matched diagrams with a reference position -- the ones the ruler can judge."""
    return [r for r in rows if r.get("exact") is not None]


def cut(rows: list[dict[str, Any]], threshold: float) -> tuple[int, int]:
    """(exported, exported and wrong) if the gate were ``threshold``."""
    out = [r for r in comparable(rows) if r["legal"] and r["gate_confidence"] >= threshold]
    return len(out), sum(1 for r in out if not r["exact"])


def curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = []
    for t in THRESHOLDS:
        exported, wrong = cut(rows, t)
        points.append({"threshold": t, "exported": exported, "wrong": wrong,
                       "exact": exported - wrong})
    return points


def cuts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every gate a model can actually have: one per **distinct** gate confidence of its
    comparable, legal diagrams (a gate at that value exports every diagram at or above
    it).  The grid of :data:`THRESHOLDS` stops at 0,99 and cannot tell a mistake at 0,998
    from the 74 exact diagrams above it -- the ruler's first version zeroed the column
    «≤ 0 errados» of six models that way (crítico da fase 5)."""
    ranked = sorted((r for r in comparable(rows) if r["legal"]),
                    key=lambda r: -r["gate_confidence"])
    points: list[dict[str, Any]] = []
    exported = wrong = 0
    for n, row in enumerate(ranked):
        exported += 1
        wrong += int(not row["exact"])
        last_of_tie = n + 1 == len(ranked) or ranked[n + 1]["gate_confidence"] < row["gate_confidence"]
        if last_of_tie:
            points.append({"threshold": row["gate_confidence"], "exported": exported,
                           "wrong": wrong, "exact": exported - wrong})
    return points


def best_at_budget(points: list[dict[str, Any]], budget: int) -> dict[str, Any]:
    """The gate that exports the most exact diagrams with at most ``budget`` wrong
    (ties: the lower threshold, which exports more).  ``points`` are :func:`cuts`.
    """
    allowed = [p for p in points if p["wrong"] <= budget]
    if not allowed:
        return {"budget": budget, "exact": 0, "threshold": None, "exported": 0, "wrong": 0}
    best = max(allowed, key=lambda p: (p["exact"], -p["threshold"]))
    return {"budget": budget, "exact": best["exact"], "threshold": best["threshold"],
            "exported": best["exported"], "wrong": best["wrong"]}


def aurc(rows: list[dict[str, Any]]) -> float:
    """Area under the risk-coverage curve over the comparable, legal diagrams, ranked by
    gate confidence: the mean of the running error rate as the gate is lowered one diagram
    at a time.  Lower is better; a model that ranks its own mistakes last scores lowest.

    **Ties** (diagrams with the same confidence) have no order a gate could pick, so the
    rate inside a tie is its expectation over every order of the tie: after ``j`` of the
    ``k`` tied diagrams, ``j·g/k`` of its ``g`` wrong ones on average (linearity of
    expectation).  The first version took the order ``sorted`` left, and four models moved
    by it -- ``c4_mhspe_s44`` from 0,0111 to 0,0134 (crítico da fase 5).
    """
    ranked = sorted((r for r in comparable(rows) if r["legal"]),
                    key=lambda r: -r["gate_confidence"])
    if not ranked:
        return 0.0
    total = 0.0
    seen = wrong = 0
    start = 0
    while start < len(ranked):
        stop = start
        while stop < len(ranked) and ranked[stop]["gate_confidence"] == ranked[start]["gate_confidence"]:
            stop += 1
        size = stop - start
        tied_wrong = sum(int(not r["exact"]) for r in ranked[start:stop])
        for j in range(1, size + 1):
            total += (wrong + j * tied_wrong / size) / (seen + j)
        seen += size
        wrong += tied_wrong
        start = stop
    return total / len(ranked)


def summarise(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    points = curve(rows)
    exported, wrong = cut(rows, GATE)
    judged = comparable(rows)
    return {
        "model": name,
        "matched": len(rows),
        "comparable": len(judged),
        "total_exact": sum(1 for r in judged if r["exact"]),
        "gate": {"threshold": GATE, "exported": exported, "wrong": wrong, "exact": exported - wrong},
        "budgets": [best_at_budget(cuts(rows), b) for b in BUDGETS],
        "aurc": round(aurc(rows), 5),
        "curve": points,
    }


def shuffled(rows: list[dict[str, Any]], seed: int = 20260923) -> list[dict[str, Any]]:
    """The sabotage: the exactness labels dealt to other diagrams (same count, fixed seed)."""
    labels = [r["exact"] for r in rows]
    random.Random(seed).shuffle(labels)
    return [{**r, "exact": label} for r, label in zip(rows, labels, strict=True)]


def kendall_tau(a: list[float], b: list[float]) -> float:
    """Kendall's tau-a between two scores of the same models: 1 when they order every pair
    alike, -1 when they reverse every pair, near 0 when one says nothing of the other.
    """
    pairs = [(i, j) for i in range(len(a)) for j in range(i + 1, len(a))]
    if not pairs:
        return 1.0

    def sign(x: float) -> int:
        return (x > 0) - (x < 0)

    return sum(sign(a[i] - a[j]) * sign(b[i] - b[j]) for i, j in pairs) / len(pairs)


def rows_from(report: Path) -> dict[str, list[dict[str, Any]]]:
    """The per-diagram rows of a previous run, by model -- to summarise them again (the
    sabotage) without measuring the field again.  A sabotaged run is not a source of truth.
    """
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("sabotage"):
        raise SystemExit(f"{report.name} é uma corrida sabotada: as linhas dela não são a verdade.")
    return {m["model"]: m["rows"] for m in data["models"]}


# --------------------------------------------------------------------------- #
# The measurement
# --------------------------------------------------------------------------- #


def model_path(name: str, root: Path) -> Path:
    if name == "production":
        return root / "models" / "piece_classifier.pt"
    candidate = Path(name)
    if candidate.suffix == ".pt" and candidate.is_file():
        return candidate
    return root / "models" / "experiments" / f"{name}.pt"


def rows_for(model: Path, runs: int, motor: str | None) -> tuple[list[dict[str, Any]], float]:
    from chess_diagram_ocr.field_eval import evaluate_field, load_field_set
    from chess_diagram_ocr.service import RecognitionOptions
    from field_exact import CORRECTIONS, _stipulation_engine, _training_pages, apply_corrections

    from caissa.vision.detect.recall import recall_pack

    root = cvoff_root()
    pages, _hit = apply_corrections(load_field_set(root / "data" / "field_set.jsonl"), CORRECTIONS)
    options = RecognitionOptions(model_path=model, max_boards=12, dpi=220,
                                 stipulation_engine=_stipulation_engine(motor))
    seen: list[list[dict[str, Any]]] = []
    started = time.perf_counter()
    for _ in range(runs):
        with recall_pack():
            report = evaluate_field(pages, options=options, pdf_dir=root / "PDF",
                                    training_pages=_training_pages(root))
        seen.append(list(report.diagrams))
    if any(rows != seen[0] for rows in seen[1:]):
        raise SystemExit(f"{model.name}: as linhas por diagrama mudaram entre execuções idênticas -- "
                         "isto é defeito, não ruído (CORPUS.md 5.1).")
    return seen[0], (time.perf_counter() - started) / max(1, runs)


def table(summaries: list[dict[str, Any]]) -> str:
    head = (f"{'modelo':<14}{'exatos':>7}{'gate exp':>9}{'err':>5}"
            + "".join(f"{f'≤{b} err (lim)':>18}" for b in BUDGETS) + f"{'AURC':>9}")
    lines = [head, "-" * len(head)]
    for s in summaries:
        cells = []
        for budget in s["budgets"]:
            limit = budget["threshold"]
            cell = str(budget["exact"]) if limit is None else f"{budget['exact']} ({limit:.4f})"
            cells.append(f"{cell:>18}")
        lines.append(f"{s['model']:<14}{s['total_exact']:>7}{s['gate']['exported']:>9}{s['gate']['wrong']:>5}"
                     f"{''.join(cells)}{s['aurc']:>9.4f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--motor", default="nenhum",
                        help="C12: o motor UCI para mate em 3+ (a exigência não muda a posição exportada "
                             "sem trocas; `nenhum` por padrão para a medição não depender dele)")
    parser.add_argument("--sabotar", default="", choices=("", "embaralhar"))
    parser.add_argument("--linhas-de", type=Path, default=None, dest="rows_from",
                        help="refaz o resumo com as linhas por diagrama de um relatório anterior, "
                             "sem medir o campo (a sabotagem sobre os dados reais)")
    parser.add_argument("--tag", default="")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)
    if args.runs < 3 and args.rows_from is None:
        raise SystemExit("docs/quality/CORPUS.md 5.1: mediana de no mínimo 3 execuções.")

    root = cvoff_root()
    saved = rows_from(args.rows_from) if args.rows_from is not None else None
    summaries: list[dict[str, Any]] = []
    for name in [m for m in args.models.split(",") if m]:
        if saved is not None:
            if name not in saved:
                print(f"  (sem linhas para {name} em {args.rows_from.name})")
                continue
            rows, seconds, checkpoint = saved[name], 0.0, f"linhas de {args.rows_from.name}"
        else:
            path = model_path(name, root)
            if not path.is_file():
                print(f"  (sem checkpoint para {name}: {path})")
                continue
            rows, seconds = rows_for(path, args.runs, args.motor)
            checkpoint = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        truth = summarise(name, rows)
        if args.sabotar == "embaralhar":
            rows = shuffled(rows)
        summary = summarise(name, rows)
        summary["aurc_true"] = truth["aurc"]
        summary["seconds_per_run"] = round(seconds, 1)
        summary["checkpoint"] = checkpoint
        summary["rows"] = rows
        summaries.append(summary)
        print(f"  {name}: exatos {summary['total_exact']}, gate {summary['gate']['exported']}/"
              f"{summary['gate']['wrong']} err, AURC {summary['aurc']:.4f} ({seconds:.0f} s/execução)",
              flush=True)

    print("\n" + table(summaries))
    tau = kendall_tau([s["aurc_true"] for s in summaries], [s["aurc"] for s in summaries])
    if args.sabotar:
        print(f"\nordem dos modelos pelo AURC, sabotada × verdadeira: tau de Kendall {tau:+.3f}")
    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    destination = args.out / f"model_ruler_{datetime.now().strftime('%Y%m%d_%H%M%S')}{tag}.json"
    destination.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "gate": GATE, "runs": args.runs, "sabotage": args.sabotar, "ruler": "corrected",
        "rows_from": args.rows_from.name if args.rows_from is not None else None,
        "ordering_tau_vs_true": round(tau, 4),
        "models": summaries,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
