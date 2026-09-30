"""The field's ruler for the model decision — OCR_UI_ROADMAP_C2 passo C17.

Two models built by hand: ``confiante`` puts every diagram above the gate and one of
its mistakes at the top; ``cauteloso`` reads the same diagrams with lower confidence and
ranks both its mistakes last.  At the production gate the confident one exports more; at
equal risk the cautious one exports more *exact* diagrams — which is the comparison the
fixed gate cannot make.  The sabotage shuffles the exactness labels.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BENCHMARKS = Path(__file__).resolve().parents[3] / "benchmarks"
if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

model_ruler = pytest.importorskip("model_ruler")


def _row(n: int, conf: float, exact: bool | None, *, legal: bool = True) -> dict:
    return {"pdf": "a.pdf", "page": 1, "index": n, "legal": legal, "gate_confidence": conf,
            "min_confidence": conf, "exact": exact, "contaminated": False}


def confiante() -> list[dict]:
    rows = [_row(0, 0.99, False)] + [_row(n, 0.95, True) for n in range(1, 9)]
    rows += [_row(9, 0.90, False), _row(10, 0.97, None)]
    return rows


def cauteloso() -> list[dict]:
    rows = [_row(n, round(0.70 + 0.02 * n, 2), True) for n in range(1, 9)]
    rows += [_row(0, 0.50, False), _row(9, 0.45, False), _row(10, 0.97, None)]
    return rows


def test_the_cut_reproduces_the_gate_and_ignores_the_unjudged() -> None:
    assert model_ruler.cut(confiante(), 0.80) == (10, 2)
    assert model_ruler.cut(cauteloso(), 0.80) == (4, 0)


def test_an_illegal_reading_never_leaves_whatever_its_confidence() -> None:
    rows = [_row(0, 0.99, True, legal=False), _row(1, 0.99, True)]
    assert model_ruler.cut(rows, 0.50) == (1, 0)


def test_at_equal_risk_the_cautious_model_exports_more_exact_diagrams() -> None:
    bold = model_ruler.summarise("confiante", confiante())
    shy = model_ruler.summarise("cauteloso", cauteloso())
    assert bold["gate"]["exported"] > shy["gate"]["exported"]           # the fixed gate
    zero = {s["model"]: s["budgets"][0] for s in (bold, shy)}
    assert zero["cauteloso"]["exact"] == 8 and zero["cauteloso"]["wrong"] == 0
    assert zero["confiante"]["exact"] == 0                               # its top pick is wrong
    assert shy["aurc"] < bold["aurc"]


def test_the_budget_takes_the_lowest_threshold_among_ties() -> None:
    best = model_ruler.best_at_budget(model_ruler.cuts(cauteloso()), 0)
    assert best["threshold"] == pytest.approx(0.72)
    assert (best["exact"], best["wrong"]) == (8, 0)


def test_a_mistake_above_the_grid_does_not_hide_the_exact_diagrams_above_it() -> None:
    """The critic's case (fase 5): the production's one wrong export sits at 0,9979 and 74
    exact diagrams sit above it.  A grid that stops at 0,99 finds no gate with zero wrong;
    every distinct confidence is a gate, and 0,998 exports the 74 with none wrong."""
    rows = [_row(n, 0.999, True) for n in range(74)]
    rows += [_row(74, 0.9979, False)] + [_row(75 + n, 0.9, True) for n in range(28)]
    zero = model_ruler.best_at_budget(model_ruler.cuts(rows), 0)
    assert (zero["exact"], zero["wrong"], zero["threshold"]) == (74, 0, 0.999)
    grid = model_ruler.best_at_budget(model_ruler.curve(rows), 0)   # the first version
    assert grid["exact"] == 0


def test_the_aurc_of_a_tie_is_its_expectation_over_every_order() -> None:
    exact_first = [_row(0, 0.9, True), _row(1, 0.9, False)]
    wrong_first = [_row(1, 0.9, False), _row(0, 0.9, True)]
    assert model_ruler.aurc(exact_first) == pytest.approx(0.5)
    assert model_ruler.aurc(wrong_first) == pytest.approx(0.5)
    # without ties it is the plain running mean: exact at 0,9 then wrong at 0,8
    assert model_ruler.aurc([_row(0, 0.9, True), _row(1, 0.8, False)]) == pytest.approx(0.25)


def test_the_sabotage_shuffled_labels_break_the_ordering() -> None:
    honest = model_ruler.summarise("cauteloso", cauteloso())["aurc"]
    sabotaged = model_ruler.summarise("cauteloso", model_ruler.shuffled(cauteloso()))["aurc"]
    assert sabotaged > honest                                  # the default seed of the harness
    mean = sum(model_ruler.aurc(model_ruler.shuffled(cauteloso(), seed=s)) for s in range(30)) / 30
    assert mean > honest                                       # and on average, any seed
    assert sum(1 for r in model_ruler.shuffled(cauteloso()) if r["exact"] is False) == 2


def test_kendall_tau_reads_the_order_and_nothing_else() -> None:
    assert model_ruler.kendall_tau([0.1, 0.2, 0.3], [1.0, 5.0, 9.0]) == 1.0
    assert model_ruler.kendall_tau([0.1, 0.2, 0.3], [9.0, 5.0, 1.0]) == -1.0
    assert model_ruler.kendall_tau([0.5], [0.1]) == 1.0


def test_the_saved_rows_come_back_and_a_sabotaged_run_is_refused(tmp_path: Path) -> None:
    import json

    honest = tmp_path / "honest.json"
    honest.write_text(json.dumps({"sabotage": "", "models": [
        {"model": "cauteloso", "rows": cauteloso()}]}), encoding="utf-8")
    assert model_ruler.rows_from(honest) == {"cauteloso": cauteloso()}
    sabotaged = tmp_path / "sabotaged.json"
    sabotaged.write_text(json.dumps({"sabotage": "embaralhar", "models": []}), encoding="utf-8")
    with pytest.raises(SystemExit):
        model_ruler.rows_from(sabotaged)


def test_the_default_models_are_the_ones_the_decision_needs() -> None:
    assert model_ruler.DEFAULT_MODELS[0] == "production"
    assert {"c4_aug0_s42", "c4_mhspe_s44", "c4_x10_s42", "c4_w3_s42"} <= set(model_ruler.DEFAULT_MODELS)
