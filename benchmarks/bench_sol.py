"""The single benchmark executor of Sol §SOL-0.

One command, one manifest, one system under test, one JSON and one Markdown
report — and every number in them traceable to ``(item, stratum, engine,
configuration)``::

    python benchmarks/bench_sol.py --system baseline --label baseline
    python benchmarks/bench_sol.py --system sol --compare benchmarks/reports/sol/baseline.json

Systems:

``baseline``
    The cascade as it stood before Sol: :class:`caissa.ocr.page.PageRecognizer`
    over a 300 DPI render, no preprocessing, the arbiter accepting the best
    engine even below its threshold.  Kept so the baseline stays reproducible
    after the production path changes.

``sol``
    The production path: :class:`caissa.ingest.pdf.ocr_service.OcrService`
    on the same image, with the conditional preprocessing portfolio, the
    decision policy and token fusion.

The blind partition is never loaded unless ``--blind`` is given, and the
report records whether it was.  Nothing here fits a threshold; the
calibration fitter is a separate command (``calibrate_sol.py``) and reads
only the calibration partition.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "benchmarks") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from sol_corpus import Rendered, render, tesseract_lang  # noqa: E402

from caissa.ocr.gates import (  # noqa: E402
    GateThresholds,
    evaluate_gates,
    group_rows,
    summarise_rows,
)
from caissa.ocr.golden import GoldenItem, items_sorted, load_manifest  # noqa: E402
from caissa.ocr.metrics import (  # noqa: E402
    normalise,
    reading_order_accuracy,
    region_order_from_text,
    score_text,
)
import contextlib

GOLDEN = REPO_ROOT / "benchmarks" / "corpus" / "golden"
#: The private manifest (with passages of corpus books) when this machine has
#: it, else the versioned public one.  The report records the content hash.
MANIFEST = (GOLDEN / "manifest.private.json" if (GOLDEN / "manifest.private.json").exists()
            else GOLDEN / "manifest.json")
REPORTS = REPO_ROOT / "benchmarks" / "reports" / "sol"
PUBLISHED = REPO_ROOT / "docs" / "quality" / "sol"


# --------------------------------------------------------------------------- #
# Systems under test
# --------------------------------------------------------------------------- #


class Answer(dict):
    """``text`` (``None`` = abstained), ``decision``, ``confidence``, ``engine``,
    ``below_threshold``, ``meta``.
    """


System = Callable[[Rendered, GoldenItem], Answer]


def make_baseline() -> System:
    from caissa.ocr.arbiter import ArbiterConfig
    from caissa.ocr.engines.registry import default_registry
    from caissa.ocr.page import PageConfig, PageRecognizer, PageTask

    registry = default_registry()
    recognizers: dict[str, PageRecognizer] = {}

    def run(rendered: Rendered, item: GoldenItem) -> Answer:
        lang = tesseract_lang(item)
        if lang not in recognizers:
            engines = registry.available(lang=lang)
            recognizers[lang] = PageRecognizer(
                engines, PageConfig(arbiter=ArbiterConfig(decision_enabled=False))
                if "decision_enabled" in ArbiterConfig.__dataclass_fields__
                else PageConfig())
        outcome = recognizers[lang].run(PageTask(image=rendered.gray, dpi=float(rendered.dpi),
                                                  lang=lang))
        text = outcome.text
        winner = outcome.regions[0].outcome.winner if outcome.regions else None
        threshold = recognizers[lang].config.arbiter.threshold_for(winner.level) if winner else 1.0
        score = winner.total if winner else 0.0
        return Answer(
            text=text if text.strip() else None,
            decision="accepted" if text.strip() else "abstained",
            confidence=score,
            engine=winner.engine if winner else "",
            below_threshold=bool(winner) and score < threshold,
            meta={"engines": list(outcome.engines_used)},
        )

    return run


#: ``--tessdata-dir`` / ``--model-prefix``: measure a fine-tuned model
#: (``tools/treinar_tesseract.py``) — ``por`` becomes ``<prefix>_por`` when
#: that file exists in the directory, so the same run reads every language
#: the reviewer trained and the base for the rest.
TESSDATA_DIR: Path | None = None
MODEL_PREFIX: str = ""


def model_lang(lang: str) -> str:
    if TESSDATA_DIR is None or not MODEL_PREFIX:
        return lang
    parts = []
    for part in lang.split("+"):
        tuned = f"{MODEL_PREFIX}_{part}"
        parts.append(tuned if (TESSDATA_DIR / f"{tuned}.traineddata").is_file() else part)
    return "+".join(parts)


def make_sol() -> System:
    """The production service.  ``SOL_CONFIG='{"fuse": false}'`` (JSON kwargs of
    :class:`OcrServiceConfig`) switches parts off for an ablation run."""
    import os

    from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig

    overrides = json.loads(os.environ.get("SOL_CONFIG", "{}"))
    engines = None
    if TESSDATA_DIR is not None:
        from caissa.ocr.engines.tesseract import TesseractConfig, TesseractEngine

        engines = [TesseractEngine(TesseractConfig(tessdata_dir=str(TESSDATA_DIR)))]
    service = OcrService(engines, config=OcrServiceConfig(**overrides))

    def run(rendered: Rendered, item: GoldenItem) -> Answer:
        recognition = service.recognize_image(rendered.gray, dpi=float(rendered.dpi),
                                              lang=model_lang(tesseract_lang(item)))
        text = recognition.text
        return Answer(
            text=text if recognition.answered else None,
            decision=str(recognition.decision),
            confidence=recognition.confidence,
            engine=recognition.engine,
            below_threshold=recognition.below_threshold,
            meta=recognition.trace(),
        )

    return run


SYSTEMS: dict[str, Callable[[], System]] = {"baseline": make_baseline, "sol": make_sol}


# --------------------------------------------------------------------------- #
# One measurement
# --------------------------------------------------------------------------- #


def measure(system: System, item: GoldenItem, stratum: str) -> dict[str, Any] | None:
    rendered = render(item, stratum)
    if rendered is None:
        return None
    started = time.perf_counter()
    answer = system(rendered, item)
    duration = time.perf_counter() - started
    row: dict[str, Any] = {
        "id": item.id,
        "stratum": stratum,
        "partition": str(item.partition),
        "source": str(item.source),
        "prose_lang": item.prose_lang,
        "script": item.script,
        "layout": item.layout,
        "genre": item.genre,
        "control": item.is_control,
        "dpi": rendered.dpi,
        "megapixels": round(rendered.megapixels, 4),
        "duration_s": round(duration, 4),
        "engine": answer.get("engine", ""),
        "decision": answer.get("decision", ""),
        "confidence": round(float(answer.get("confidence", 0.0)), 4),
        "below_threshold": bool(answer.get("below_threshold", False)),
        #: Page notes that name a setup fault (every region failed in the engine).
        "faults": [n for n in (answer.get("meta") or {}).get("notes", ()) if "falharam" in n],
    }
    text = answer.get("text")
    if item.is_control:
        row["answered"] = text is not None
        row["hypothesis_chars"] = len(normalise(text or ""))
        row["hypothesis"] = (text or "")[:120]
        return row
    score = score_text(item.truth, text)
    row.update(score.as_dict())
    row["length_ratio"] = round(score.length_ratio, 4)
    if len(item.regions) > 1 and text is not None:
        truths = [r.truth for r in sorted(item.regions, key=lambda r: r.reading_order)]
        found = region_order_from_text(text, truths)
        row["reading_order"] = round(reading_order_accuracy(
            [str(i) for i in range(len(truths))], [str(i) for i in found]), 4)
    if text is not None and score.cer > 0.05:
        row["hypothesis"] = text[:200]
    return row


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def environment() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "commit": "",
    }
    with contextlib.suppress(OSError):
        info["commit"] = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
            cwd=REPO_ROOT, check=False).stdout.strip()
    try:
        from caissa.ocr.engines.tesseract import TesseractEngine

        engine = TesseractEngine()
        info["tesseract"] = engine.version if engine.available() else None
    except Exception:  # noqa: BLE001 - a missing engine is a fact for the report
        info["tesseract"] = None
    for module in ("numpy", "cv2", "fitz", "PIL"):
        try:
            mod = __import__(module)
            info[module] = getattr(mod, "__version__", "?")
        except ImportError:
            info[module] = None
    return info


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Sol · benchmark `{report['system']}` — {report['label']}",
        "",
        f"> {report['generated_at']} · corpus `{report['corpus_hash']}` "
        f"({report['corpus_version']}) · commit `{report['environment'].get('commit', '')}` · "
        f"Tesseract {report['environment'].get('tesseract')} · "
        f"cego {'incluído' if report['blind_included'] else 'excluído'}",
        "",
        "## Resumo por estrato",
        "",
        "| estrato | n | resp. | abst. | revisão | CER médio | IC 95% | WER | lances "
        "| perdidos | inventados | ctrl FP | s/MP |",
        "|---|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|",
    ]
    for name, s in report["summary"]["by_stratum"].items():
        lines.append(
            f"| {name} | {s['n']} | {s['answered']} | {s['abstained']} | {s['review']} | "
            f"{_fmt(s['cer_mean'])} | {_fmt(s['cer_ci'][0])}–{_fmt(s['cer_ci'][1])} | "
            f"{_fmt(s['wer_mean'])} | {_fmt(s['move_accuracy'])} | {s['moves_missing']} | "
            f"{s['moves_invented']} | {s['control_false_positives']}/{s['controls']} | "
            f"{_fmt(s['seconds_per_megapixel'], 2)} |")
    for facet in ("prose_lang", "script", "layout", "genre", "partition"):
        lines += ["", f"## Por {facet}", "",
                  "| valor | n | resp. | CER médio | WER | lances | inventados | ordem |",
                  "|---|--:|--:|--:|--:|--:|--:|--:|"]
        for value, s in report["summary"]["by_facet"][facet].items():
            ro = s.get("reading_order_mean")
            lines.append(
                f"| {value or '—'} | {s['n']} | {s['answered']} | {_fmt(s['cer_mean'])} | "
                f"{_fmt(s['wer_mean'])} | {_fmt(s['move_accuracy'])} | {s['moves_invented']} | "
                f"{_fmt(ro) if ro is not None else '—'} |")
    overall = report["summary"]["overall"]
    lines += ["", "## Calibração e abstenção", ""]
    cal = overall.get("calibration")
    if cal:
        lines.append(f"- ECE {cal['ece']:.4f}, Brier {cal['brier']:.4f} em {cal['n']} respostas "
                     f"(acerto = CER ≤ 2 %).")
        lines.append("- Confiabilidade por faixa (confiança → acerto, n): " + ", ".join(
            f"{b['lower']:.1f}–{b['upper']:.1f}: {b['confidence']:.2f}→{b['accuracy']:.2f} "
            f"({b['n']})" for b in cal["bins"] if b["n"]))
    rc = overall.get("risk_coverage")
    if rc:
        lines.append("- Risco × cobertura (limiar: cobertura / CER): " + ", ".join(
            f"{p['threshold']:.1f}: {p['coverage']:.2f}/{p['risk']:.3f}" for p in rc))
    lines.append(f"- Enviado para revisão: {overall['review_share']:.1%}; abstenção "
                 f"{overall['abstention_rate']:.1%}; importações silenciosas abaixo do limiar: "
                 f"{overall['silent_below_threshold']}.")
    lines.append(f"- Tempo total {overall['seconds_total']} s, "
                 f"{overall['seconds_per_megapixel']} s/MP.")
    if report.get("gates"):
        lines += ["", "## Portões", ""]
        for r in report["gates"]["results"]:
            mark = "✓" if r["passed"] else ("✗" if r["blocking"] else "!")
            lines.append(f"- {mark} **{r['name']}** — {r['detail']}")
        lines.append("")
        lines.append("**Resultado:** " + ("verde" if report["gates"]["passed"] else "bloqueado"))
    worst = sorted((r for r in report["rows"] if r.get("answered") and not r.get("control")),
                   key=lambda r: -float(r.get("cer", 0)))[:10]
    lines += ["", "## Dez piores itens", "", "| item | estrato | CER | motor | decisão |",
              "|---|---|--:|---|---|"]
    for r in worst:
        lines.append(f"| `{r['id']}` | {r['stratum']} | {_fmt(r['cer'])} | {r['engine']} | "
                     f"{r['decision']} |")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--system", choices=sorted(SYSTEMS), default="sol")
    parser.add_argument("--label", default="")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--strata", default="", help="comma-separated subset of strata")
    parser.add_argument("--limit", type=int, default=0, help="first N items (after sorting)")
    parser.add_argument("--filter", default="", help="substring of the item id")
    parser.add_argument("--blind", action="store_true", help="include the blind partition")
    parser.add_argument("--compare", type=Path, default=None,
                        help="baseline report JSON for the regression gates")
    parser.add_argument("--out", type=Path, default=REPORTS)
    parser.add_argument("--publish", action="store_true",
                        help="also write the Markdown and a text-free JSON under docs/quality/sol")
    parser.add_argument("--tessdata-dir", type=Path, default=None,
                        help="tessdata with a fine-tuned model (tools/treinar_tesseract.py output)")
    parser.add_argument("--model-prefix", default="caissa",
                        help="with --tessdata-dir: use <prefix>_<lang>.traineddata when present")
    args = parser.parse_args()
    global TESSDATA_DIR, MODEL_PREFIX  # run options read by the system factory
    TESSDATA_DIR, MODEL_PREFIX = args.tessdata_dir, args.model_prefix

    manifest = load_manifest(args.manifest, include_blind=args.blind)
    items = items_sorted(manifest.items)
    if args.filter:
        items = [i for i in items if args.filter in i.id]
    if args.limit:
        items = items[:args.limit]
    wanted = set(args.strata.split(",")) if args.strata else None

    system = SYSTEMS[args.system]()
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    total = sum(len([s for s in i.strata if wanted is None or s in wanted]) for i in items)
    done = 0
    for item in items:
        for stratum in item.strata:
            if wanted is not None and stratum not in wanted:
                continue
            row = measure(system, item, stratum)
            done += 1
            if row is None:
                print(f"  ! {item.id} [{stratum}]: fonte ausente, pulado")
                continue
            rows.append(row)
            if done % 25 == 0 or done == total:
                elapsed = time.perf_counter() - started
                print(f"  {done}/{total} em {elapsed:.0f} s")

    answered = sum(1 for r in rows if r.get("answered"))
    if rows and answered == 0:
        notes = {n for r in rows for n in r.get("faults", ())}
        print("  !!! NENHUMA linha respondida: o motor falhou em toda região — isto é um defeito de "
              "instalação, não uma medição. " + (next(iter(notes)) if notes else ""))

    by_facet = {
        facet: {value: summarise_rows(group) for value, group in group_rows(rows, facet).items()}
        for facet in ("prose_lang", "script", "layout", "genre", "partition", "source")
    }
    report: dict[str, Any] = {
        "system": args.system,
        "label": args.label or args.system,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        # The corpus identity is the whole manifest, blind partition included,
        # so a release run (--blind) and a development run report the same
        # hash and the environment gate compares them on what they measured,
        # recorded separately in ``blind_included``.
        "corpus_hash": load_manifest(args.manifest, include_blind=True).content_hash(),
        "corpus_version": manifest.corpus_version,
        "blind_included": args.blind,
        "environment": {**environment(),
                        "tessdata_dir": str(TESSDATA_DIR) if TESSDATA_DIR else None,
                        "model_prefix": MODEL_PREFIX if TESSDATA_DIR else None},
        "thresholds": GateThresholds().__dict__ if hasattr(GateThresholds(), "__dict__") else {},
        "summary": {
            "overall": summarise_rows(rows),
            "by_stratum": {n: summarise_rows(g) for n, g in group_rows(rows, "stratum").items()},
            "by_facet": by_facet,
        },
        "rows": rows,
    }
    baseline_rows = None
    if args.compare is not None:
        with args.compare.open(encoding="utf-8") as handle:
            baseline_rows = json.load(handle)["rows"]
    gates = evaluate_gates(rows, baseline_rows)
    report["gates"] = gates.as_dict()

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{args.label or args.system}_{stamp}"
    (args.out / f"{stem}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / f"{stem}.md").write_text(markdown(report), encoding="utf-8")
    print(f"\n{args.out / stem}.json / .md")
    if args.publish:
        # The versioned copy carries no hypothesis text: rows keep every
        # number, and the corpus passages stay on this machine.
        stripped = dict(report)
        stripped["rows"] = [{k: v for k, v in row.items() if k != "hypothesis"}
                            for row in rows]
        PUBLISHED.mkdir(parents=True, exist_ok=True)
        name = args.label or args.system
        (PUBLISHED / f"{name}.json").write_text(
            json.dumps(stripped, ensure_ascii=False, indent=1), encoding="utf-8")
        (PUBLISHED / f"{name}.md").write_text(markdown(report), encoding="utf-8")
        print(f"publicado em {PUBLISHED / name}.json / .md")
    print(gates.describe_pt())
    for name, s in report["summary"]["by_stratum"].items():
        print(f"  {name:20s} n={s['n']:3d} CER={s['cer_mean']:.4f} lances={s['move_accuracy']:.4f} "
              f"inventados={s['moves_invented']} abst={s['abstained']} ctrlFP="
              f"{s['control_false_positives']}")
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    raise SystemExit(main())
