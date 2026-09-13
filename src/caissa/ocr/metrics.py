"""Exact OCR metrics — the numbers Sol §SOL-0 asks every change to be judged by.

Everything here needs ground truth and is therefore *benchmark* code, not
production code: the arbiter never sees a reference text.  It lives in the
package rather than under ``benchmarks/`` because the unit tests pin each
metric with a hand-computed case, and because the review model (SOL-11)
records human corrections in the same shape so they can feed calibration.

Two conventions hold throughout.

**Scoring form.**  Every text is compared after :func:`normalise`: NFKC,
the five Unicode dashes folded to ``-``, curly quotes straightened, the soft
hyphen the text layer emits for a line-end hyphen turned into a real one,
castling with zeros rewritten with letters, whitespace collapsed.  A metric
that counted ``’`` against ``'`` would measure the font, not the OCR.

**Moves are counted as multisets.**  ``moves_kept`` is the multiset
intersection of truth moves and hypothesis moves; ``moves_invented`` is what
the hypothesis has beyond that; ``moves_missing`` what the truth has beyond
that.  An altered move therefore counts once as missing *and* once as
invented, which is what the release gate wants: a changed move is an invented
move as far as the reader is concerned.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .quality import levenshtein

__all__ = [
    "CalibrationReport",
    "MoveAccounting",
    "ReliabilityBin",
    "RiskCoveragePoint",
    "TextScore",
    "brier_score",
    "expected_calibration_error",
    "line_exact_accuracy",
    "move_accounting",
    "move_tokens",
    "normalise",
    "reading_order_accuracy",
    "region_prf",
    "reliability",
    "risk_coverage",
    "score_text",
]


# --------------------------------------------------------------------------- #
# Normalisation and tokens
# --------------------------------------------------------------------------- #

_FOLD: tuple[tuple[str, str], ...] = (
    ("­", "-"),
    ("‐", "-"), ("‑", "-"), ("‒", "-"), ("–", "-"),
    ("—", "-"), ("−", "-"),
    ("‘", "'"), ("’", "'"), ("‚", "'"),
    ("“", '"'), ("”", '"'), ("„", '"'),
    ("…", "..."),
    ("×", "x"),
)

_ZERO_CASTLE_LONG = re.compile(r"(?<![\w])0-0-0(?![\w])")
_ZERO_CASTLE = re.compile(r"(?<![\w])0-0(?![\w])")

#: A move token in any of the notations the corpus prints: SAN with the
#: piece letters of English, Portuguese, German, Spanish and Russian, an
#: optional figurine, promotion and check marks, or castling.
MOVE_TOKEN = re.compile(
    r"(?<![\w])(?:O-O(?:-O)?|"
    r"[KQRBNPDTCSAFLГЛСКФП♔-♟]?"
    r"[a-h]?[1-8]?x?[a-h][1-8]"
    r"(?:=?[QRBNDTCSAFL♔-♟])?[+#]?)(?![\w])(?!-?[A-Za-z]{2})"
)


def normalise(text: str) -> str:
    """Scoring form of ``text`` — see the module docstring."""
    text = unicodedata.normalize("NFKC", text or "")
    for source, target in _FOLD:
        text = text.replace(source, target)
    text = _ZERO_CASTLE_LONG.sub("O-O-O", text)
    text = _ZERO_CASTLE.sub("O-O", text)
    return " ".join(text.split())


def move_tokens(text: str) -> list[str]:
    """Move-shaped tokens of ``text`` in scoring form, in order."""
    return MOVE_TOKEN.findall(normalise(text))


# --------------------------------------------------------------------------- #
# Text scores
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class MoveAccounting:
    """How the hypothesis treated the truth's moves."""

    truth: int
    kept: int
    missing: int
    invented: int

    @property
    def accuracy(self) -> float:
        """Exact move-token accuracy: kept over truth (1.0 when no moves)."""
        return self.kept / self.truth if self.truth else 1.0


def move_accounting(truth: str, hypothesis: str) -> MoveAccounting:
    """Multiset accounting of move tokens, as described in the module doc."""
    truth_moves = Counter(move_tokens(truth))
    got = Counter(move_tokens(hypothesis))
    kept = sum((truth_moves & got).values())
    return MoveAccounting(
        truth=sum(truth_moves.values()),
        kept=kept,
        missing=sum(truth_moves.values()) - kept,
        invented=sum(got.values()) - kept,
    )


@dataclass(frozen=True, slots=True)
class TextScore:
    """Every per-item number the benchmark reports for one answer."""

    answered: bool
    cer: float = 0.0
    wer: float = 0.0
    line_exact: float = 0.0
    moves: MoveAccounting = field(default_factory=lambda: MoveAccounting(0, 0, 0, 0))
    truth_chars: int = 0
    hypothesis_chars: int = 0

    @property
    def length_ratio(self) -> float:
        return self.hypothesis_chars / max(1, self.truth_chars)

    def as_dict(self) -> dict[str, object]:
        return {
            "answered": self.answered,
            "cer": round(self.cer, 5),
            "wer": round(self.wer, 5),
            "line_exact": round(self.line_exact, 4),
            "moves_truth": self.moves.truth,
            "moves_kept": self.moves.kept,
            "moves_missing": self.moves.missing,
            "moves_invented": self.moves.invented,
            "truth_chars": self.truth_chars,
            "hypothesis_chars": self.hypothesis_chars,
        }


def line_exact_accuracy(truth: str, hypothesis: str) -> float:
    """Share of truth lines reproduced exactly (after normalisation).

    Lines are aligned by edit distance over the line sequence, so one
    inserted line does not shift every later line into a miss.
    """
    truth_lines = [normalise(line) for line in truth.splitlines() if line.strip()]
    hyp_lines = [normalise(line) for line in hypothesis.splitlines() if line.strip()]
    if not truth_lines:
        return 1.0 if not hyp_lines else 0.0
    matched = _lcs_length(truth_lines, hyp_lines)
    return matched / len(truth_lines)


def _lcs_length(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for item in a:
        current = [0]
        for j, other in enumerate(b, 1):
            if item == other:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[j - 1]))
        previous = current
    return previous[-1]


def score_text(truth: str, hypothesis: str | None) -> TextScore:
    """Score one answer.  ``None`` means the system abstained."""
    if hypothesis is None:
        return TextScore(answered=False, truth_chars=len(normalise(truth)))
    t, h = normalise(truth), normalise(hypothesis)
    cer = levenshtein(h, t) / len(t) if t else (0.0 if not h else 1.0)
    t_words, h_words = t.split(), h.split()
    wer = (levenshtein(h_words, t_words) / len(t_words) if t_words
           else (0.0 if not h_words else 1.0))
    return TextScore(
        answered=True,
        cer=float(cer),
        wer=float(wer),
        line_exact=line_exact_accuracy(truth, hypothesis),
        moves=move_accounting(truth, hypothesis),
        truth_chars=len(t),
        hypothesis_chars=len(h),
    )


# --------------------------------------------------------------------------- #
# Layout metrics
# --------------------------------------------------------------------------- #


def reading_order_accuracy(truth_order: Sequence[str],
                           hypothesis_order: Sequence[str]) -> float:
    """1.0 when the hypothesis lists the truth's regions in the same order.

    Regions are matched by identifier; a region the hypothesis never produced
    counts against the order, because a reader would notice its absence as
    much as a swap.  Measured as the longest common subsequence over the
    truth length, so one displaced region costs one region, not the page.
    """
    if not truth_order:
        return 1.0
    return _lcs_length(list(truth_order), list(hypothesis_order)) / len(truth_order)


def region_prf(truth_boxes: Sequence[tuple[float, float, float, float]],
               hypothesis_boxes: Sequence[tuple[float, float, float, float]],
               *, iou_threshold: float = 0.5) -> tuple[float, float, float]:
    """Precision, recall and F1 of region detection at an IoU threshold.

    Greedy one-to-one matching by descending IoU, which is the standard
    detection protocol and is deterministic for equal IoUs by index order.
    """
    if not truth_boxes and not hypothesis_boxes:
        return 1.0, 1.0, 1.0
    pairs: list[tuple[float, int, int]] = []
    for i, t in enumerate(truth_boxes):
        for j, h in enumerate(hypothesis_boxes):
            iou = _iou(t, h)
            if iou >= iou_threshold:
                pairs.append((-iou, i, j))
    pairs.sort()
    used_t: set[int] = set()
    used_h: set[int] = set()
    matched = 0
    for _, i, j in pairs:
        if i in used_t or j in used_h:
            continue
        used_t.add(i)
        used_h.add(j)
        matched += 1
    precision = matched / len(hypothesis_boxes) if hypothesis_boxes else 0.0
    recall = matched / len(truth_boxes) if truth_boxes else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    return precision, recall, f1


def _iou(a: tuple[float, float, float, float],
         b: tuple[float, float, float, float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    """One bin of a reliability diagram."""

    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float

    @property
    def gap(self) -> float:
        return abs(self.mean_confidence - self.accuracy)


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    ece: float
    brier: float
    bins: tuple[ReliabilityBin, ...]
    count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "ece": round(self.ece, 5),
            "brier": round(self.brier, 5),
            "n": self.count,
            "bins": [
                {
                    "lower": b.lower, "upper": b.upper, "n": b.count,
                    "confidence": round(b.mean_confidence, 4),
                    "accuracy": round(b.accuracy, 4),
                }
                for b in self.bins
            ],
        }


def reliability(confidences: Sequence[float], correct: Sequence[bool], *,
                bins: int = 10) -> tuple[ReliabilityBin, ...]:
    """Equal-width reliability bins over ``[0, 1]``."""
    if len(confidences) != len(correct):
        raise ValueError("confidências e acertos têm tamanhos diferentes")
    out: list[ReliabilityBin] = []
    for k in range(bins):
        lower, upper = k / bins, (k + 1) / bins
        members = [
            (c, ok) for c, ok in zip(confidences, correct, strict=True)
            if (lower <= c < upper) or (k == bins - 1 and c == 1.0)
        ]
        if not members:
            out.append(ReliabilityBin(lower, upper, 0, 0.0, 0.0))
            continue
        mean_conf = sum(c for c, _ in members) / len(members)
        accuracy = sum(1 for _, ok in members if ok) / len(members)
        out.append(ReliabilityBin(lower, upper, len(members), mean_conf, accuracy))
    return tuple(out)


def expected_calibration_error(confidences: Sequence[float],
                               correct: Sequence[bool], *,
                               bins: int = 10) -> float:
    """ECE: bin-count-weighted mean of |confidence − accuracy|."""
    total = len(confidences)
    if total == 0:
        return 0.0
    return sum(b.count / total * b.gap
               for b in reliability(confidences, correct, bins=bins))


def brier_score(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    if not confidences:
        return 0.0
    return sum((c - (1.0 if ok else 0.0)) ** 2
               for c, ok in zip(confidences, correct, strict=True)) / len(confidences)


def calibration_report(confidences: Sequence[float], correct: Sequence[bool], *,
                       bins: int = 10) -> CalibrationReport:
    return CalibrationReport(
        ece=expected_calibration_error(confidences, correct, bins=bins),
        brier=brier_score(confidences, correct),
        bins=reliability(confidences, correct, bins=bins),
        count=len(confidences),
    )


# --------------------------------------------------------------------------- #
# Risk versus coverage
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RiskCoveragePoint:
    threshold: float
    coverage: float
    risk: float


def risk_coverage(confidences: Sequence[float], errors: Sequence[float], *,
                  steps: int = 20) -> tuple[RiskCoveragePoint, ...]:
    """The abstention curve: accept everything at or above a threshold, and
    report the share accepted (coverage) and their mean error (risk).

    ``errors`` is any per-item loss in ``[0, 1]`` — CER is the usual one.
    """
    if len(confidences) != len(errors):
        raise ValueError("confidências e erros têm tamanhos diferentes")
    n = len(confidences)
    points: list[RiskCoveragePoint] = []
    for k in range(steps + 1):
        threshold = k / steps
        accepted = [e for c, e in zip(confidences, errors, strict=True)
                    if c >= threshold]
        coverage = len(accepted) / n if n else 0.0
        risk = sum(accepted) / len(accepted) if accepted else 0.0
        points.append(RiskCoveragePoint(threshold, coverage, risk))
    return tuple(points)


def bootstrap_mean_ci(values: Sequence[float], *, samples: int = 1000,
                      alpha: float = 0.05, seed: int = 7) -> tuple[float, float, float]:
    """``(mean, low, high)`` percentile bootstrap — the tolerance SOL-12 needs.

    A pure-Python LCG rather than :mod:`random` so the interval is identical
    on every machine and every Python build; the benchmark commits it.
    """
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    state = seed & 0xFFFFFFFF
    means: list[float] = []
    for _ in range(samples):
        total = 0.0
        for _ in range(n):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            total += values[state % n]
        means.append(total / n)
    means.sort()
    low = means[max(0, math.floor(alpha / 2 * samples))]
    high = means[min(samples - 1, math.ceil((1 - alpha / 2) * samples) - 1)]
    return mean, low, high


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def region_order_from_text(hypothesis: str, region_truths: Sequence[str], *,
                           window_words: int = 6, min_ratio: float = 0.6) -> list[int]:
    """Indices of ``region_truths`` in the order their text appears in ``hypothesis``.

    Each region is located by the best fuzzy match of its first
    ``window_words`` words against every same-length window of the
    hypothesis; regions that never reach ``min_ratio`` are absent from the
    result, which :func:`reading_order_accuracy` then counts against the
    page.  Fuzzy on purpose: OCR errors inside the anchor must not make a
    correctly ordered region look missing.
    """
    import difflib

    hyp_words = normalise(hypothesis).split()
    placed: list[tuple[int, int]] = []
    for index, truth in enumerate(region_truths):
        anchor = normalise(truth).split()[:window_words]
        if not anchor or not hyp_words:
            continue
        anchor_text = " ".join(anchor)
        best_ratio, best_at = 0.0, -1
        span = len(anchor)
        for start in range(max(1, len(hyp_words) - span + 1)):
            window = " ".join(hyp_words[start:start + span])
            ratio = difflib.SequenceMatcher(None, anchor_text, window).ratio()
            if ratio > best_ratio:
                best_ratio, best_at = ratio, start
        if best_ratio >= min_ratio:
            placed.append((best_at, index))
    return [index for _, index in sorted(placed)]
