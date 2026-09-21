"""Signals, model and metrics of ``caissa.vision.classify.confidence`` — passo 8.

The field set cannot fit or judge this model yet (2 negatives in 96,
``OCR_UI_REPORT_C1.md`` §4), so what is tested here is that the pieces do
what they claim on data that has both classes: the fit separates what is
separable, the metrics answer 0,5 / 0 for a constant, and the signals read a
recognised diagram without needing the trunk.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from caissa.vision.classify.confidence import (
    FEATURE_NAMES,
    DiagramConfidence,
    DiagramSignals,
    auroc,
    brier,
    expected_calibration_error,
    fit_logistic,
    risk_coverage,
)


def _diagram(min_conf: float, repaired: int, fatal: bool = False, source: str = "raster") -> SimpleNamespace:
    confidences = [0.99] * 60 + [min_conf, 0.95, 0.85, 0.65]
    probs = np.full((64, 13), 0.001)
    probs[:, 0] = 0.98
    probs[63, 0], probs[63, 1] = 0.40, 0.35
    return SimpleNamespace(
        min_confidence=min_conf, mean_confidence=sum(confidences) / 64,
        square_confidences=confidences, probs=probs, changed_squares=list(range(repaired)),
        legality=SimpleNamespace(is_fatal=fatal, needs_side_to_move_flip=False),
        orientation_ambiguous=False, detection_source=source)


def test_signals_read_a_recognised_diagram():
    signals = DiagramSignals.from_recognized(_diagram(0.30, 1, source="vector-font"))
    assert signals.min_confidence == pytest.approx(0.30)
    assert signals.squares_below_0_90 == 3 and signals.squares_below_0_70 == 2
    assert signals.min_margin == pytest.approx(0.05)
    assert signals.repaired_squares == 1 and signals.vector_route
    # The fitted features first and in order; the C11/C5 signals ride along, outside the vector.
    assert list(signals.as_dict())[: len(FEATURE_NAMES)] == list(FEATURE_NAMES)
    assert list(signals.as_dict())[len(FEATURE_NAMES):] == ["next_move_replays", "external_repairs"]
    assert len(signals.vector()) == len(FEATURE_NAMES)


def test_the_fit_separates_separable_boards_and_the_metrics_know_a_constant():
    rng = np.random.default_rng(3)
    good = np.array([_diagram(rng.uniform(0.85, 1.0), 0).min_confidence for _ in range(60)])
    bad = np.array([_diagram(rng.uniform(0.05, 0.6), 2).min_confidence for _ in range(20)])
    x = np.zeros((80, len(FEATURE_NAMES)))
    x[:60, 0], x[60:, 0] = good, bad
    x[60:, 5] = 2.0
    y = np.array([1.0] * 60 + [0.0] * 20)
    model = fit_logistic(x, y, l2=1.0)
    p = model.probabilities(x)
    assert auroc(y, p) > 0.95
    assert expected_calibration_error(y, p) < 0.1
    assert brier(y, p) < brier(y, np.full(80, y.mean()))
    assert auroc(y, np.full(80, 0.7)) == 0.5, "a constant discriminates nothing"
    coverage = risk_coverage(y, p, thresholds=(0.5, 0.9))
    assert coverage[0]["coverage"] >= coverage[1]["coverage"]
    assert coverage[1]["conditional_exact"] >= y.mean()


def test_the_model_round_trips_and_refuses_foreign_features(tmp_path):
    model = DiagramConfidence(weights=(0.5,) * len(FEATURE_NAMES), bias=0.1,
                              mean=(0.0,) * len(FEATURE_NAMES), scale=(1.0,) * len(FEATURE_NAMES))
    path = model.save(tmp_path / "w.json", note="teste")
    again = DiagramConfidence.from_dict(__import__("json").loads(path.read_text("utf-8")))
    assert again.weights == model.weights and again.note == "teste"
    with pytest.raises(ValueError):
        DiagramConfidence.from_dict({"features": ["x"], "weights": [1], "bias": 0, "mean": [0],
                                     "scale": [1]})
