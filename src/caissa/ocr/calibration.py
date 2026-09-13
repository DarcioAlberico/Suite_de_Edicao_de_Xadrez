"""Fitted confidence calibration — Sol §SOL-4.

The arbiter compares engines by a calibrated confidence, and until Sol the
calibration was a floor and a gamma per engine "encoding the documented
reputations of the engines and nothing more" (its own words).  A reputation
is not a measurement.  This module holds what a measurement produces: for
one engine, under one facet (language, script, resolution, region kind), a
monotone map from the engine's raw confidence to the observed probability
that the word it labels is correct.

**Fitting** is isotonic regression by pool-adjacent-violators over the
``(raw confidence, correct)`` pairs of the *calibration* partition of the
golden corpus — never the blind one — and the result is stored as a small
table of ``(raw, calibrated)`` knots that :meth:`CalibrationTable.apply`
interpolates.  Isotonic rather than a parametric curve because Tesseract's
confidence is famously non-linear (flat near 0.9, informative below), and
a monotone step fit follows whatever shape the data has without inventing
one.

**Lookup** goes from the most specific key to the least:
``engine|lang=rus|script=cyrillic|dpi=150|kind=movetext`` down to
``engine``.  A facet with too few samples is not fitted, so it falls back
to the next; the record says which key answered.

The fitted set ships in ``caissa/ocr/data/calibration.json`` with the
corpus hash, the partition, the sample counts and the ECE before and after
fitting, so the number the arbiter uses can be traced to the run that made
it.  Refit with ``benchmarks/calibrate_sol.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .metrics import brier_score, expected_calibration_error

__all__ = [
    "CalibrationSet",
    "CalibrationTable",
    "FacetKey",
    "facet_key",
    "fit_isotonic",
    "load_calibration_set",
    "packaged_calibration",
]

DATA_FILE = "calibration.json"
MIN_SAMPLES = 40


@dataclass(frozen=True, slots=True)
class FacetKey:
    """The facets a calibration can be conditioned on."""

    engine: str
    lang: str = ""
    script: str = ""
    dpi: int = 0
    kind: str = ""

    @property
    def dpi_bucket(self) -> str:
        if self.dpi <= 0:
            return ""
        if self.dpi < 200:
            return "low"
        if self.dpi < 350:
            return "300"
        return "high"

    def candidates(self) -> list[str]:
        """Keys from the most specific to ``engine`` alone."""
        parts = [("lang", self.lang), ("script", self.script),
                 ("dpi", self.dpi_bucket), ("kind", self.kind)]
        present = [(k, v) for k, v in parts if v]
        keys: list[str] = []
        for n in range(len(present), 0, -1):
            keys.append(self.engine + "".join(f"|{k}={v}" for k, v in present[:n]))
        keys.append(self.engine)
        return keys


def facet_key(engine: str, *, lang: str = "", script: str = "", dpi: float = 0.0,
              kind: str = "") -> FacetKey:
    return FacetKey(engine=engine, lang=_first_lang(lang), script=script,
                    dpi=int(dpi), kind=kind)


def _first_lang(lang: str) -> str:
    from .lexicon import normalise_lang

    codes = normalise_lang(lang)
    return codes[0] if codes else ""


@dataclass(frozen=True, slots=True)
class CalibrationTable:
    """Knots of a monotone map raw → calibrated, plus what fitted them."""

    knots: tuple[tuple[float, float], ...]
    samples: int = 0
    ece_before: float = 0.0
    ece_after: float = 0.0
    brier_before: float = 0.0
    brier_after: float = 0.0

    def apply(self, raw: float) -> float:
        knots = self.knots
        if not knots:
            return max(0.0, min(1.0, raw))
        if raw <= knots[0][0]:
            return knots[0][1]
        if raw >= knots[-1][0]:
            return knots[-1][1]
        for (x0, y0), (x1, y1) in zip(knots, knots[1:], strict=False):
            if x0 <= raw <= x1:
                if x1 == x0:
                    return y1
                t = (raw - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return knots[-1][1]

    def as_dict(self) -> dict[str, Any]:
        return {
            "knots": [[round(x, 4), round(y, 4)] for x, y in self.knots],
            "samples": self.samples,
            "ece_before": round(self.ece_before, 4),
            "ece_after": round(self.ece_after, 4),
            "brier_before": round(self.brier_before, 4),
            "brier_after": round(self.brier_after, 4),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CalibrationTable":
        return cls(
            knots=tuple((float(x), float(y)) for x, y in data.get("knots", ())),
            samples=int(data.get("samples", 0)),
            ece_before=float(data.get("ece_before", 0.0)),
            ece_after=float(data.get("ece_after", 0.0)),
            brier_before=float(data.get("brier_before", 0.0)),
            brier_after=float(data.get("brier_after", 0.0)),
        )


def fit_isotonic(raw: Sequence[float], correct: Sequence[bool], *,
                 min_samples: int = MIN_SAMPLES, knots: int = 12) -> CalibrationTable | None:
    """Pool-adjacent-violators over the pairs, reduced to ``knots`` points.

    Returns ``None`` when there are too few samples to say anything: a
    table fitted on twelve words would be noise wearing a decimal point.
    """
    n = len(raw)
    if n < min_samples or n != len(correct):
        return None
    order = sorted(range(n), key=lambda i: raw[i])
    xs = [float(raw[i]) for i in order]
    ys = [1.0 if correct[i] else 0.0 for i in order]
    # PAV: blocks of (sum_y, count, x_lo, x_hi) merged while decreasing.
    blocks: list[list[float]] = []
    for x, y in zip(xs, ys, strict=True):
        blocks.append([y, 1.0, x, x])
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            b = blocks.pop()
            a = blocks[-1]
            a[0] += b[0]
            a[1] += b[1]
            a[3] = b[3]
    steps = [(0.5 * (b[2] + b[3]), b[0] / b[1]) for b in blocks]
    if len(steps) > knots:
        # Keep evenly spaced steps by sample mass, always the ends.
        total = sum(b[1] for b in blocks)
        wanted = [k * total / (knots - 1) for k in range(knots)]
        chosen: list[tuple[float, float]] = []
        mass = 0.0
        target = 0
        for step, block in zip(steps, blocks, strict=True):
            mass += block[1]
            while target < knots and mass >= wanted[target] - 1e-9:
                if not chosen or chosen[-1] != step:
                    chosen.append(step)
                target += 1
        if chosen[-1] != steps[-1]:
            chosen.append(steps[-1])
        steps = chosen
    table = CalibrationTable(knots=tuple(steps), samples=n)
    calibrated = [table.apply(x) for x in raw]
    return CalibrationTable(
        knots=table.knots, samples=n,
        ece_before=expected_calibration_error(list(raw), list(correct)),
        ece_after=expected_calibration_error(calibrated, list(correct)),
        brier_before=brier_score(list(raw), list(correct)),
        brier_after=brier_score(calibrated, list(correct)),
    )


@dataclass(slots=True)
class CalibrationSet:
    """Every fitted table, keyed by facet string, with its provenance."""

    tables: dict[str, CalibrationTable] = field(default_factory=dict)
    fitted_at: str = ""
    corpus_hash: str = ""
    partition: str = "calib"
    notes: list[str] = field(default_factory=list)

    def lookup(self, key: FacetKey) -> tuple[str, CalibrationTable] | None:
        for candidate in key.candidates():
            table = self.tables.get(candidate)
            if table is not None:
                return candidate, table
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "fitted_at": self.fitted_at,
            "corpus_hash": self.corpus_hash,
            "partition": self.partition,
            "notes": list(self.notes),
            "tables": {k: t.as_dict() for k, t in sorted(self.tables.items())},
        }

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CalibrationSet":
        return cls(
            tables={k: CalibrationTable.from_dict(v) for k, v in data.get("tables", {}).items()},
            fitted_at=str(data.get("fitted_at", "")),
            corpus_hash=str(data.get("corpus_hash", "")),
            partition=str(data.get("partition", "calib")),
            notes=list(data.get("notes", ())),
        )


def load_calibration_set(path: Path | str) -> CalibrationSet:
    with Path(path).open(encoding="utf-8") as handle:
        return CalibrationSet.from_dict(json.load(handle))


_PACKAGED: CalibrationSet | None = None


def packaged_calibration() -> CalibrationSet:
    """The set shipped with the package (empty when none was fitted yet)."""
    global _PACKAGED  # noqa: PLW0603 - read once per process
    if _PACKAGED is None:
        try:
            text = resources.files("caissa.ocr.data").joinpath(DATA_FILE).read_text("utf-8")
            _PACKAGED = CalibrationSet.from_dict(json.loads(text))
        except (FileNotFoundError, OSError, ValueError, ModuleNotFoundError):
            _PACKAGED = CalibrationSet()
    return _PACKAGED


def reset_packaged_calibration() -> None:
    global _PACKAGED  # noqa: PLW0603 - for tests
    _PACKAGED = None


def pairs_from_alignment(hypothesis_words: Iterable[tuple[str, float]],
                         truth_words: Sequence[str]) -> list[tuple[float, bool]]:
    """``(raw confidence, correct)`` per hypothesis word, aligned to the truth.

    Alignment is by :mod:`difflib` over the word sequences in scoring form;
    a hypothesis word is correct when it sits in a matching block.
    """
    import difflib

    from .metrics import normalise

    hyp = [(normalise(w), c) for w, c in hypothesis_words if normalise(w)]
    truth = [normalise(w) for w in truth_words if normalise(w)]
    matcher = difflib.SequenceMatcher(None, [w for w, _ in hyp], truth, autojunk=False)
    correct = [False] * len(hyp)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            correct[block.a + k] = True
    return [(c, ok) for (_, c), ok in zip(hyp, correct, strict=True)]
