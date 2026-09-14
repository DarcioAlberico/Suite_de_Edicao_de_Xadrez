"""The probability that a recognised diagram is exact — OCR_UI_ROADMAP passo 8.

What the classifier reports is per *square*: ``min_confidence`` is the least
confident of 64 softmax maxima.  Nothing in the product said how likely the
**whole board** is to be right, and two things needed exactly that: the
review queue (which board to look at first) and the export gate, which barred
20 of 114 field diagrams on ``min_confidence`` alone — among them every board
the constraint decoder repaired, by arithmetic (``decode.py``: a repaired
square's confidence is at most 0,5, the gate is 0,80).  Temperature scaling
was measured and rejected for this (``ASSETS.md`` §2.14): it made the squares
shier and doubled the review queue without fixing one.

This module is the other thing: a **shallow model over signals the pipeline
already has**, fitted on the field set (``benchmarks/diagram_confidence_gate.py``)
and judged by discrimination against the constant predictor, not by
calibration alone (with 93 exact boards in 94 a constant is well calibrated).

The signals (:class:`DiagramSignals`) are the ones a reviewer would look at:
the least and mean square confidence, how many squares fall below two bars,
the smallest top-1/top-2 margin, how many squares the legality decoder had to
repair, whether the position is fatal / needs a side flip / is clean, whether
the orientation was ambiguous, and which route found the board.  A logistic
regression with L2 over standardised features; no dependency beyond numpy,
because the fit is a few kilobytes of weights that ship with the package.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "FEATURE_NAMES",
    "DiagramConfidence",
    "DiagramSignals",
    "auroc",
    "brier",
    "default_confidence",
    "expected_calibration_error",
    "fit_logistic",
    "packaged_weights_path",
    "risk_coverage",
]

FEATURE_NAMES: tuple[str, ...] = (
    "min_confidence",
    "mean_confidence",
    "squares_below_0_90",
    "squares_below_0_70",
    "min_margin",
    "repaired_squares",
    "fatal",
    "side_flip",
    "orientation_ambiguous",
    "vector_route",
)

WEIGHTS_FILE = "diagram_confidence.json"
_LOW_BAR = 0.90
_LOWER_BAR = 0.70


@dataclass(frozen=True, slots=True)
class DiagramSignals:
    """What the recogniser already knows about one board, as numbers."""

    min_confidence: float
    mean_confidence: float
    squares_below_0_90: int
    squares_below_0_70: int
    min_margin: float
    repaired_squares: int
    fatal: bool
    side_flip: bool
    orientation_ambiguous: bool
    vector_route: bool

    @classmethod
    def from_recognized(cls, diagram: Any) -> DiagramSignals:
        """Signals from the trunk's ``RecognizedDiagram`` (or anything shaped like it)."""
        confidences = [float(c) for c in (getattr(diagram, "square_confidences", None) or ())]
        probs = getattr(diagram, "probs", None)
        min_margin = 1.0
        if probs is not None:
            arr = np.asarray(probs, dtype=float)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                top = np.sort(arr, axis=1)
                min_margin = float((top[:, -1] - top[:, -2]).min())
        legality = getattr(diagram, "legality", None)
        fatal = bool(getattr(legality, "is_fatal", False)) if legality is not None else False
        side_flip = (bool(getattr(legality, "needs_side_to_move_flip", False))
                     if legality is not None else False)
        source = str(getattr(diagram, "detection_source", "") or "")
        return cls(
            min_confidence=float(getattr(diagram, "min_confidence", 0.0) or 0.0),
            mean_confidence=(float(getattr(diagram, "mean_confidence", 0.0) or 0.0)
                             or (sum(confidences) / len(confidences) if confidences else 0.0)),
            squares_below_0_90=sum(1 for c in confidences if c < _LOW_BAR),
            squares_below_0_70=sum(1 for c in confidences if c < _LOWER_BAR),
            min_margin=min_margin,
            repaired_squares=len(getattr(diagram, "changed_squares", None) or ()),
            fatal=fatal,
            side_flip=side_flip,
            orientation_ambiguous=bool(getattr(diagram, "orientation_ambiguous", False)),
            vector_route="vector" in source.lower() or "font" in source.lower(),
        )

    def vector(self) -> np.ndarray:
        return np.array([
            self.min_confidence, self.mean_confidence, float(self.squares_below_0_90),
            float(self.squares_below_0_70), self.min_margin, float(self.repaired_squares),
            float(self.fatal), float(self.side_flip), float(self.orientation_ambiguous),
            float(self.vector_route),
        ], dtype=float)

    def as_dict(self) -> dict[str, Any]:
        return dict(zip(FEATURE_NAMES, self.vector().tolist(), strict=True))


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DiagramConfidence:
    """A logistic regression over standardised :class:`DiagramSignals`."""

    weights: tuple[float, ...]
    bias: float
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    note: str = ""
    fitted_at: str = ""

    def probabilities(self, x: np.ndarray) -> np.ndarray:
        z = ((np.asarray(x, dtype=float) - np.array(self.mean)) / np.array(self.scale))
        logits = z @ np.array(self.weights) + self.bias
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))

    def probability(self, signals: DiagramSignals) -> float:
        """``p(exact)`` for one board."""
        return float(self.probabilities(signals.vector()[None, :])[0])

    def as_dict(self) -> dict[str, Any]:
        return {"version": 1, "features": list(FEATURE_NAMES), "weights": list(self.weights),
                "bias": self.bias, "mean": list(self.mean), "scale": list(self.scale),
                "note": self.note, "fitted_at": self.fitted_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagramConfidence:
        if list(data.get("features", ())) != list(FEATURE_NAMES):
            raise ValueError("os pesos empacotados não correspondem às características atuais")
        return cls(weights=tuple(float(w) for w in data["weights"]), bias=float(data["bias"]),
                   mean=tuple(float(m) for m in data["mean"]),
                   scale=tuple(float(s) for s in data["scale"]),
                   note=str(data.get("note", "")), fitted_at=str(data.get("fitted_at", "")))

    def save(self, path: Path | str, *, note: str = "") -> Path:
        from datetime import UTC, datetime

        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        data = self.as_dict()
        data["note"] = note or self.note
        data["fitted_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        file.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return file


def fit_logistic(x: np.ndarray, y: np.ndarray, *, l2: float = 1.0,
                 iterations: int = 500) -> DiagramConfidence:
    """L2-regularised logistic regression by Newton's method on standardised features."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    n, d = z.shape
    design = np.hstack([z, np.ones((n, 1))])
    w = np.zeros(d + 1)
    reg = np.full(d + 1, l2)
    reg[-1] = 0.0                                   # the bias is not shrunk
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(design @ w, -30.0, 30.0)))
        gradient = design.T @ (p - y) + reg * w
        hessian = (design * (p * (1 - p))[:, None]).T @ design + np.diag(reg)
        step = np.linalg.solve(hessian, gradient)
        w = w - step
        if float(np.abs(step).max()) < 1e-8:
            break
    return DiagramConfidence(weights=tuple(w[:-1].tolist()), bias=float(w[-1]),
                             mean=tuple(mean.tolist()), scale=tuple(scale.tolist()))


# --------------------------------------------------------------------------- #
# Packaged weights
# --------------------------------------------------------------------------- #


def packaged_weights_path() -> Path:
    return Path(__file__).resolve().parent / WEIGHTS_FILE


_DEFAULT: DiagramConfidence | None = None


def default_confidence() -> DiagramConfidence | None:
    """The packaged model, or ``None`` when no weights ship (then callers keep
    ``min_confidence`` and say so).
    """
    global _DEFAULT
    if _DEFAULT is None:
        try:
            text = resources.files("caissa.vision.classify").joinpath(WEIGHTS_FILE).read_text("utf-8")
        except (FileNotFoundError, OSError, ModuleNotFoundError):
            return None
        _DEFAULT = DiagramConfidence.from_dict(json.loads(text))
    return _DEFAULT


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


def auroc(y: Sequence[float], scores: Sequence[float]) -> float:
    """Area under the ROC curve by the rank statistic; 0,5 for a constant."""
    y_arr = np.asarray(y, dtype=float)
    s_arr = np.asarray(scores, dtype=float)
    positives = s_arr[y_arr == 1]
    negatives = s_arr[y_arr == 0]
    if len(positives) == 0 or len(negatives) == 0:
        return 0.5
    wins = 0.0
    for neg in negatives:
        wins += float((positives > neg).sum()) + 0.5 * float((positives == neg).sum())
    return wins / (len(positives) * len(negatives))


def expected_calibration_error(y: Sequence[float], p: Sequence[float], bins: int = 10) -> float:
    y_arr = np.asarray(y, dtype=float)
    p_arr = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (p_arr >= lo) & ((p_arr < hi) if hi < 1.0 else (p_arr <= hi))
        if not mask.any():
            continue
        ece += mask.mean() * abs(float(y_arr[mask].mean()) - float(p_arr[mask].mean()))
    return float(ece)


def brier(y: Sequence[float], p: Sequence[float]) -> float:
    y_arr = np.asarray(y, dtype=float)
    p_arr = np.asarray(p, dtype=float)
    return float(((p_arr - y_arr) ** 2).mean())


def risk_coverage(y: Sequence[float], p: Sequence[float],
                  thresholds: Sequence[float] = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)) -> list[dict[str, float]]:
    """Coverage and conditional exactness when only boards with ``p ≥ t`` are exported."""
    y_arr = np.asarray(y, dtype=float)
    p_arr = np.asarray(p, dtype=float)
    out = []
    for t in thresholds:
        mask = p_arr >= t
        out.append({
            "threshold": float(t),
            "coverage": float(mask.mean()) if len(mask) else 0.0,
            "conditional_exact": float(y_arr[mask].mean()) if mask.any() else float("nan"),
        })
    return out
