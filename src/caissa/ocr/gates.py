"""Release gates and report aggregation — Sol §SOL-0 (metrics) and §SOL-12.

The benchmark produces one row per ``(item, stratum)``; this module turns
rows into the per-stratum summary the report prints and into the verdict
the release needs.  It is pure: rows in, numbers out, so the unit tests can
feed it hand-made rows and pin every gate.

The gates compare *by stratum*, never by an aggregate mean, because a mean
hides the language or the scan quality that regressed (Sol §8, "média
esconder idioma ruim").  A regression only blocks when it is outside the
bootstrap confidence interval of the difference — a run-to-run wobble of
Tesseract on a noisy page is not a regression — except for the counts that
must be exactly zero (invented moves, silent imports below threshold), where
one is enough.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .metrics import (
    bootstrap_mean_ci,
    calibration_report,
    mean,
    risk_coverage,
)

__all__ = [
    "GateReport",
    "GateResult",
    "GateThresholds",
    "Row",
    "evaluate_gates",
    "summarise_rows",
]

Row = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class GateThresholds:
    """The Sol §1 targets, as numbers."""

    cer_clean_max: float = 0.005
    cer_150dpi_max: float = 0.020
    move_accuracy_min: float = 0.998
    invented_moves_max: int = 0
    reading_order_min: float = 1.0
    silent_below_threshold_max: int = 0
    #: A stratum's mean CER may rise by at most this much *and* the rise must
    #: be outside the bootstrap interval of the difference to block.
    cer_regression_tolerance: float = 0.002
    insertion_rate_tolerance: float = 0.002
    #: Which strata the CER targets apply to.
    clean_strata: tuple[str, ...] = ("native", "scan_clean_300")
    dpi150_strata: tuple[str, ...] = ("scan_degraded_150",)
    #: Rows whose CER is at most this are "correct" for calibration purposes.
    correct_cer: float = 0.02
    #: An **accepted** row whose CER is above this lost text and went into the book as if it
    #: were whole -- the count B14 of the cycle 2 exists to bring down (30 in the phase 4
    #: ``sol.json``: the photo that lost the end of every line, accepted at 0,87).
    accepted_wrong_cer: float = 0.10


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    passed: bool
    observed: float
    limit: float
    detail: str
    blocking: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "passed": self.passed, "observed": self.observed,
            "limit": self.limit, "detail": self.detail, "blocking": self.blocking,
        }


@dataclass(slots=True)
class GateReport:
    results: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.blocking)

    @property
    def failures(self) -> list[GateResult]:
        return [r for r in self.results if not r.passed]

    def as_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "results": [r.as_dict() for r in self.results]}

    def describe_pt(self) -> str:
        lines = ["Portões: " + ("VERDES" if self.passed else "BLOQUEADOS")]
        for r in self.results:
            mark = "✓" if r.passed else ("✗" if r.blocking else "!")
            lines.append(f"  {mark} {r.name}: {r.detail}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def _answered(rows: Iterable[Row]) -> list[Row]:
    return [r for r in rows if r.get("answered") and not r.get("control")]


def summarise_rows(rows: Sequence[Row], *, thresholds: GateThresholds | None = None
                   ) -> dict[str, Any]:
    """Per-subset numbers.  Every value is traceable to the rows it came from."""
    t = thresholds or GateThresholds()
    controls = [r for r in rows if r.get("control")]
    measured = [r for r in rows if not r.get("control")]
    answered = _answered(measured)
    cers = [float(r["cer"]) for r in answered]
    # B11: the CER over **every** measured item, an abstention costing the whole page (1,0);
    # and the CER of the text the service withheld, over the abstained items that had any.
    cers_all = [float(r.get("cer_all", r["cer"] if r.get("answered") else 1.0)) for r in measured]
    cers_withheld = [float(r["cer_withheld"]) for r in measured if r.get("cer_withheld") is not None]
    truth_moves = sum(int(r.get("moves_truth", 0)) for r in answered)
    kept = sum(int(r.get("moves_kept", 0)) for r in answered)
    invented = sum(int(r.get("moves_invented", 0)) for r in answered)
    missing = sum(int(r.get("moves_missing", 0)) for r in answered)
    insertions = [max(0.0, float(r.get("length_ratio", 1.0)) - 1.0) for r in answered]
    cer_mean, cer_lo, cer_hi = bootstrap_mean_ci(cers)
    confidences = [float(r.get("confidence", 0.0)) for r in answered]
    correct = [float(r["cer"]) <= t.correct_cer for r in answered]
    reviews = [r for r in measured if r.get("decision") == "review"]
    abstained = [r for r in measured if r.get("decision") == "abstained"]
    silent = [r for r in answered if r.get("below_threshold") and r.get("decision") == "accepted"]
    accepted_wrong = [r for r in answered if r.get("decision") == "accepted"
                      and float(r["cer"]) > t.accepted_wrong_cer]
    control_hits = [r for r in controls if r.get("answered") and r.get("hypothesis_chars", 0)]
    reading_orders = [float(r["reading_order"]) for r in answered
                      if r.get("reading_order") is not None]
    seconds = [float(r.get("duration_s", 0.0)) for r in measured]
    megapixels = [float(r.get("megapixels", 0.0)) for r in measured]
    total_mp = sum(megapixels)
    summary: dict[str, Any] = {
        "n": len(measured),
        "answered": len(answered),
        "abstained": len(abstained),
        "review": len(reviews),
        "review_share": round(len(reviews) / len(measured), 4) if measured else 0.0,
        "abstention_rate": round(1 - len(answered) / len(measured), 4) if measured else 0.0,
        "cer_mean": round(cer_mean, 5),
        "cer_ci": [round(cer_lo, 5), round(cer_hi, 5)],
        "cer_median": round(sorted(cers)[len(cers) // 2], 5) if cers else 0.0,
        "cer_all_mean": round(mean(cers_all), 5) if cers_all else 0.0,
        "cer_withheld_mean": round(mean(cers_withheld), 5) if cers_withheld else None,
        "withheld_with_text": len(cers_withheld),
        "wer_mean": round(mean(float(r.get("wer", 0.0)) for r in answered), 5),
        "line_exact_mean": round(mean(float(r.get("line_exact", 0.0)) for r in answered), 4),
        "moves_truth": truth_moves,
        "moves_kept": kept,
        "moves_missing": missing,
        "moves_invented": invented,
        "move_accuracy": round(kept / truth_moves, 5) if truth_moves else 1.0,
        "insertion_rate": round(mean(insertions), 5),
        "silent_below_threshold": len(silent),
        "accepted_wrong": len(accepted_wrong),
        "controls": len(controls),
        "control_false_positives": len(control_hits),
        "reading_order_mean": round(mean(reading_orders), 4) if reading_orders else None,
        "seconds_per_megapixel": round(sum(seconds) / total_mp, 4) if total_mp else 0.0,
        "seconds_total": round(sum(seconds), 2),
    }
    if answered:
        summary["calibration"] = calibration_report(confidences, correct).as_dict()
        summary["risk_coverage"] = [
            {"threshold": p.threshold, "coverage": round(p.coverage, 4),
             "risk": round(p.risk, 5)}
            for p in risk_coverage(confidences, cers, steps=10)
        ]
    return summary


def group_rows(rows: Sequence[Row], key: str) -> dict[str, list[Row]]:
    groups: dict[str, list[Row]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key, "")), []).append(row)
    return dict(sorted(groups.items()))


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #


def _by_stratum(rows: Sequence[Row]) -> dict[str, dict[str, Any]]:
    return {name: summarise_rows(group) for name, group in group_rows(rows, "stratum").items()}


def evaluate_gates(rows: Sequence[Row], baseline: Sequence[Row] | None = None, *,
                   thresholds: GateThresholds | None = None,
                   environment_ok: bool = True) -> GateReport:
    """Every blocking gate of Sol §SOL-12 against ``rows``.

    ``baseline`` enables the regression gates (CER per stratum, insertion
    rate, reading order); without it only the absolute targets are checked.
    """
    t = thresholds or GateThresholds()
    report = GateReport()
    current = _by_stratum(rows)
    previous = _by_stratum(baseline) if baseline else {}

    def stratum_cer(names: tuple[str, ...], summary: Mapping[str, Mapping[str, Any]]
                    ) -> tuple[float, int]:
        cers: list[float] = []
        for name in names:
            block = summary.get(name)
            if block and block["answered"]:
                cers.append(float(block["cer_mean"]))
        return (mean(cers) if cers else 0.0), len(cers)

    clean, n_clean = stratum_cer(t.clean_strata, current)
    report.results.append(GateResult(
        "CER limpo", n_clean > 0 and clean <= t.cer_clean_max, clean, t.cer_clean_max,
        f"{clean:.4f} em {n_clean} estrato(s) limpo(s), limite {t.cer_clean_max:.4f}"
        + ("" if n_clean else " — nenhum estrato limpo medido")))
    noisy, n_noisy = stratum_cer(t.dpi150_strata, current)
    report.results.append(GateResult(
        "CER 150 DPI", n_noisy > 0 and noisy <= t.cer_150dpi_max, noisy, t.cer_150dpi_max,
        f"{noisy:.4f} em {n_noisy} estrato(s) a 150 DPI, limite {t.cer_150dpi_max:.4f}"
        + ("" if n_noisy else " — nenhum estrato a 150 DPI medido")))

    overall = summarise_rows(rows)
    report.results.append(GateResult(
        "acurácia de lances", overall["move_accuracy"] >= t.move_accuracy_min,
        overall["move_accuracy"], t.move_accuracy_min,
        f"{overall['moves_kept']}/{overall['moves_truth']} lances exatos "
        f"({overall['move_accuracy']:.4f}), mínimo {t.move_accuracy_min:.4f}"))
    report.results.append(GateResult(
        "lances inventados", overall["moves_invented"] <= t.invented_moves_max,
        overall["moves_invented"], t.invented_moves_max,
        f"{overall['moves_invented']} token(s) de lance sem correspondência na verdade"))
    report.results.append(GateResult(
        "importação silenciosa abaixo do limiar",
        overall["silent_below_threshold"] <= t.silent_below_threshold_max,
        overall["silent_below_threshold"], t.silent_below_threshold_max,
        f"{overall['silent_below_threshold']} região(ões) aceitas abaixo do limiar sem revisão"))
    report.results.append(GateResult(
        "controles negativos", overall["control_false_positives"] == 0,
        overall["control_false_positives"], 0,
        f"{overall['control_false_positives']} de {overall['controls']} controle(s) sem texto "
        f"produziram conteúdo"))
    ro = overall.get("reading_order_mean")
    if ro is not None:
        report.results.append(GateResult(
            "ordem de leitura em duas colunas", ro >= t.reading_order_min, ro,
            t.reading_order_min, f"{ro:.4f} de ordem correta nos itens com mais de uma região"))
    report.results.append(GateResult(
        "reprodução do ambiente", environment_ok, 1.0 if environment_ok else 0.0, 1.0,
        "ambiente, versões e hashes registrados" if environment_ok
        else "o ambiente não reproduz o baseline"))

    if previous:
        for name, block in current.items():
            before = previous.get(name)
            if not before or not before["answered"] or not block["answered"]:
                continue
            delta = float(block["cer_mean"]) - float(before["cer_mean"])
            lo = float(block["cer_ci"][0]) - float(before["cer_ci"][1])
            regressed = delta > t.cer_regression_tolerance and lo > 0.0
            report.results.append(GateResult(
                f"regressão de CER [{name}]", not regressed, delta, t.cer_regression_tolerance,
                f"CER {before['cer_mean']:.4f} → {block['cer_mean']:.4f} "
                f"(Δ {delta:+.4f}; IC da diferença começa em {lo:+.4f})"))
            ins_delta = float(block["insertion_rate"]) - float(before["insertion_rate"])
            report.results.append(GateResult(
                f"inserções de texto [{name}]", ins_delta <= t.insertion_rate_tolerance,
                ins_delta, t.insertion_rate_tolerance,
                f"taxa de inserção {before['insertion_rate']:.4f} → "
                f"{block['insertion_rate']:.4f}"))
            if before.get("reading_order_mean") is not None and block.get(
                    "reading_order_mean") is not None:
                report.results.append(GateResult(
                    f"ordem de leitura [{name}]",
                    float(block["reading_order_mean"]) >= float(before["reading_order_mean"]),
                    float(block["reading_order_mean"]), float(before["reading_order_mean"]),
                    f"{before['reading_order_mean']:.3f} → {block['reading_order_mean']:.3f}"))
    return report
