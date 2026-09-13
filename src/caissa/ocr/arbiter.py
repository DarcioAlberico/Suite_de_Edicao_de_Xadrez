"""Per-region engine arbitration — SPEC §7.1.

The cascade exists because the engines differ by two orders of magnitude in
cost and are not ordered by quality: the PDF's own text layer is both the
cheapest and the *best* when it is trustworthy, Tesseract is cheap and good on
clean Latin scans, and the heavier engines only earn their cost on the pages the
cheap ones fail.  Running everything everywhere would be forty times slower for
a gain confined to a few per cent of regions.

So the arbiter runs the cheapest viable engine, scores what comes back, and
escalates only when the score falls short.  Three properties are non-negotiable:

**It must be deterministic.**  The same region, the same engines, the same
result — always.  Nothing here iterates a set or a dict whose order could vary,
every comparison has an explicit tie-break, and the ladder is sorted by
``(level, name)`` rather than by registration order.  A pipeline that silently
produces different text on a re-run cannot be debugged and cannot be trusted.

**It must say why.**  Every decision is recorded as an
:class:`EscalationDecision` with the numbers that drove it and a Brazilian
Portuguese sentence.  "The OCR got it wrong" is not an actionable bug report;
"level 1 scored 0.62 against a threshold of 0.75 because plausibility was 0.31,
so it escalated to level 2, which scored 0.88" is.

**A low score must not be confused with a low confidence.**  Engine confidences
are not comparable to each other — Tesseract's word confidence is famously
optimistic, and the PDF text layer has no confidence at all — so each engine's
raw number goes through its own calibration before it is scored, and the score
also weighs whether the *text* is plausible language and whether independent
engines agree.  An engine that is confidently wrong is exactly the failure mode
the plausibility term exists to catch.

Confidence aggregation follows the rule the sibling project learned the hard
way (ASSETS §2.11): the mean hides the failure, because most of what is being
averaged is easy.  There it was empty squares on a board; here it is the long
common words that every engine gets right.  So the worst word carries weight of
its own.
"""

from __future__ import annotations

import difflib
import inspect
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .decision import Decision, DecisionPolicy, RegionDecision, decide
from .engines.base import EngineLevel, OcrEngine
from .lexicon import normalise_lang
from .quality import QualitySignals, measure_text, text_plausibility
from .types import BBox, OcrResult, RegionKind, empty_result

__all__ = [
    "DEFAULT_CALIBRATIONS",
    "Arbiter",
    "ArbiterConfig",
    "ArbitrationOutcome",
    "EngineCalibration",
    "EngineScore",
    "EscalationDecision",
    "RegionTask",
]

LOGGER = logging.getLogger("caissa.ocr.arbiter")


@lru_cache(maxsize=32)
def _function_accepts_verdict(func: Any) -> bool:
    try:
        return "verdict" in inspect.signature(func).parameters
    except (TypeError, ValueError):      # a C callable, or a strange wrapper
        return False


def _accepts_verdict(recognize_page: Any) -> bool:
    """True when this ``recognize_page`` takes a pre-computed verdict.

    Keyed on the *underlying function*, not on the bound method: a bound
    method is a fresh object on every attribute access, so caching on it would
    call :func:`inspect.signature` once per region and cache nothing.
    """
    func = getattr(recognize_page, "__func__", recognize_page)
    try:
        return _function_accepts_verdict(func)
    except TypeError:                    # unhashable callable
        return _function_accepts_verdict.__wrapped__(func)


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class EngineCalibration:
    """Maps one engine's raw confidence onto a comparable 0..1 scale.

    ``floor`` is the raw value below which the engine is saying nothing useful;
    ``gamma`` bends the curve.  ``gamma > 1`` pushes middling confidences down,
    which is right for an engine that reports 90 % for text it got wrong.

    These defaults are **provisional**.  Honest calibration needs the labelled
    golden corpus of SPEC §11.2, which does not exist yet; until it does, the
    numbers below encode the documented reputations of the engines and nothing
    more.  They are in one table, named, so that replacing them with fitted
    values is a data change and not a code change.
    """

    floor: float = 0.0
    gamma: float = 1.0
    #: Weight of the weak-word term against the length-weighted mean.  See the
    #: module docstring: averages hide the failures that matter.
    worst_word_weight: float = 0.30
    #: *Which* weak word.  Not the minimum: on a page-sized unit the minimum is
    #: 0.000 for every engine and every page, so the term becomes a constant
    #: and the weight above turns into a flat penalty.  Measured in
    #: docs/quality/F5_REPORT_C2.md §5, where it zeroed Tesseract on 12 of 12
    #: pages and made the whole cascade past level 0 decorative.
    weak_word_quantile: float = 0.05

    def apply(self, raw: float) -> float:
        if raw <= self.floor:
            return 0.0
        span = 1.0 - self.floor
        if span <= 0.0:
            return 1.0
        return float(min(1.0, ((raw - self.floor) / span) ** self.gamma))


DEFAULT_CALIBRATIONS: dict[str, EngineCalibration] = {
    # Tesseract's word confidence rarely drops below 0.60 even on nonsense, so
    # the bottom third of its range carries no information and gamma pulls the
    # middle down.
    "tesseract": EngineCalibration(floor=0.55, gamma=1.4, worst_word_weight=0.35),
    # The text layer has no per-word confidence: the number it reports is the
    # verdict from its own CMap audit, which is already a calibrated judgement.
    "pdf_text_layer": EngineCalibration(floor=0.0, gamma=1.0,
                                        worst_word_weight=0.0),
    "paddleocr": EngineCalibration(floor=0.40, gamma=1.2, worst_word_weight=0.30),
    "surya": EngineCalibration(floor=0.40, gamma=1.2, worst_word_weight=0.30),
}

#: Used for an engine with no entry above — neutral, and deliberately a little
#: pessimistic so an unknown engine cannot outrank a characterised one on
#: confidence alone.
FALLBACK_CALIBRATION = EngineCalibration(floor=0.35, gamma=1.3)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ArbiterConfig:
    """Weights and thresholds.  All of them, in one place."""

    weight_confidence: float = 0.45
    weight_plausibility: float = 0.35
    weight_agreement: float = 0.20

    #: Accept and stop when the score reaches this.
    accept_threshold: float = 0.78
    #: Per-level overrides.  Level 0 is held to a higher bar because accepting
    #: a bad text layer is silent and permanent, while accepting a bad OCR
    #: result at least leaves low confidences behind for the UI to flag.
    accept_threshold_by_level: dict[int, float] = field(
        default_factory=lambda: {EngineLevel.PDF_TEXT_LAYER: 0.82}
    )
    #: Stop escalating past this level regardless of score.
    max_level: int = EngineLevel.VLM
    #: Never run more than this many engines on one region.
    max_engines: int = 3
    #: A region shorter than this has too little text to score lexically; the
    #: plausibility weight is redistributed to confidence.
    min_chars_for_plausibility: int = 24
    calibrations: Mapping[str, EngineCalibration] = field(
        default_factory=lambda: dict(DEFAULT_CALIBRATIONS))
    #: Sol §SOL-2.  When on, a region no engine cleared is *not* labelled
    #: accepted: the outcome carries a :class:`RegionDecision` of ``REVIEW``
    #: or ``ABSTAINED`` and the caller decides what to emit.  Off reproduces
    #: the pre-Sol cascade for the versioned baseline, nothing else.
    decision_enabled: bool = True
    policy: DecisionPolicy = field(default_factory=DecisionPolicy)
    #: Sol §SOL-4: an engine that returned nothing — a rejected or empty
    #: text layer, an engine that crashed — does not spend the region's
    #: engine budget.  Counting it did: on a scanned page level 0 came back
    #: empty, Tesseract ran, and the third slot Surya needed was gone.
    count_empty_in_budget: bool = False

    def threshold_for(self, level: int) -> float:
        return self.accept_threshold_by_level.get(level, self.accept_threshold)

    def calibration_for(self, engine: str) -> EngineCalibration:
        return self.calibrations.get(engine, FALLBACK_CALIBRATION)


# --------------------------------------------------------------------------- #
# Task and results
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RegionTask:
    """One region to recognise.

    ``pdf_page`` is what makes level 0 possible: without it the text-layer
    engine has nothing to read and the cascade starts at level 1.
    """

    image: NDArray[np.uint8] | None = None
    region_kind: RegionKind = RegionKind.PARAGRAPH
    lang: str = "por"
    pdf_page: Any = None
    clip: BBox | None = None
    #: PDF points to image pixels, i.e. ``dpi / 72``.
    scale: float = 1.0
    region_id: str = ""
    #: A verdict already computed for this region, handed to a level-0 engine
    #: that accepts one.  The page runner supplies it so that a region too
    #: short to judge on its own — a heading, a caption, a folio — inherits the
    #: page's verdict instead of being condemned as "a scan" by the 24-char
    #: floor and escalated to OCR for nothing.  Left ``None`` by every other
    #: caller, and then the engine assesses the clip itself.
    verdict: Any = None

    @property
    def has_image(self) -> bool:
        return self.image is not None and getattr(self.image, "size", 0) > 0


@dataclass(frozen=True, slots=True)
class EngineScore:
    """The breakdown of one engine's score, kept so it can be explained."""

    engine: str
    level: int
    total: float
    confidence: float
    raw_confidence: float
    plausibility: float
    agreement: float
    char_count: int
    duration_s: float

    def describe_pt(self) -> str:
        return (f"{self.engine} (nível {self.level}): escore {self.total:.3f} "
                f"[confiança {self.confidence:.2f}, plausibilidade "
                f"{self.plausibility:.2f}, concordância {self.agreement:.2f}] "
                f"em {self.duration_s * 1000:.0f} ms")


@dataclass(frozen=True, slots=True)
class EscalationDecision:
    """One step of the cascade, and why it went the way it did."""

    step: int
    engine: str
    level: int
    action: str            # accepted | escalated | skipped | exhausted | review | abstained
    score: float | None
    threshold: float | None
    reason_pt: str

    def __str__(self) -> str:
        score = "—" if self.score is None else f"{self.score:.3f}"
        return (f"[{self.step}] {self.engine} n{self.level} {self.action} "
                f"({score}): {self.reason_pt}")


@dataclass(frozen=True, slots=True)
class ArbitrationOutcome:
    """Everything the arbiter did, and what it chose."""

    result: OcrResult
    scores: tuple[EngineScore, ...]
    decisions: tuple[EscalationDecision, ...]
    engines_run: tuple[str, ...]
    escalated: bool
    total_duration_s: float
    #: Sol §SOL-2: what the caller may do with :attr:`result`.  ``None`` only
    #: when :attr:`ArbiterConfig.decision_enabled` is off.
    decision: RegionDecision | None = None
    #: Every result the engines produced, in the order they ran — the
    #: candidates token fusion (SOL-6) and the review panel (SOL-11) need.
    candidates: tuple[OcrResult, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.decision is None or self.decision.decision is Decision.ACCEPTED

    @property
    def abstained(self) -> bool:
        return self.decision is not None and self.decision.decision is Decision.ABSTAINED

    @property
    def winner(self) -> EngineScore | None:
        if not self.scores:
            return None
        return max(self.scores, key=lambda s: (s.total, -s.level, s.engine))

    def explain_pt(self) -> str:
        lines = [str(d) for d in self.decisions]
        best = self.winner
        if best is not None:
            lines.append(f"Escolhido: {best.describe_pt()}")
        if self.decision is not None:
            lines.append(self.decision.describe_pt())
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Arbiter
# --------------------------------------------------------------------------- #


class Arbiter:
    """Runs the cascade for one region at a time."""

    def __init__(self, engines: Sequence[OcrEngine],
                 config: ArbiterConfig | None = None,
                 logger: logging.Logger | None = None) -> None:
        self.config = config or ArbiterConfig()
        self.log = logger or LOGGER
        # Sorted by (level, name) rather than by the order the registry handed
        # them over: registry order can depend on import order, and the cascade
        # must not.
        self.engines: list[OcrEngine] = sorted(
            engines, key=lambda e: (e.capabilities().level, e.name))

    # -- scoring ----------------------------------------------------------- #

    def _confidence_of(self, result: OcrResult) -> tuple[float, float]:
        """``(calibrated, raw)`` confidence for a result."""
        calibration = self.config.calibration_for(result.engine)
        mean = result.mean_confidence
        weak = result.weak_word_confidence(calibration.weak_word_quantile)
        weight = calibration.worst_word_weight
        raw = (1.0 - weight) * mean + weight * weak
        return calibration.apply(raw), raw

    @staticmethod
    def _agreement(result: OcrResult,
                   others: Sequence[OcrResult]) -> tuple[float, bool]:
        """Best similarity against any other engine's output.

        ``difflib`` rather than an edit distance: it is C-backed, it is a
        similarity in 0..1 already, and the difference between the two measures
        is far smaller than the noise in what is being compared.
        """
        text = " ".join(result.text.split())
        candidates = [" ".join(o.text.split()) for o in others
                      if o.engine != result.engine and o.text.strip()]
        if not text or not candidates:
            return 0.0, False
        best = max(
            difflib.SequenceMatcher(None, text, other).ratio()
            for other in candidates
        )
        return float(best), True

    def score(self, result: OcrResult, *, level: int, lang: str,
              others: Sequence[OcrResult] = ()) -> EngineScore:
        """Score one result.  Pure: no state, no I/O, no randomness."""
        cfg = self.config
        confidence, raw = self._confidence_of(result)
        signals: QualitySignals = measure_text(result.text, lang or result.lang)

        has_text = signals.char_count >= cfg.min_chars_for_plausibility
        plausibility = (text_plausibility(result.text, lang, signals=signals)
                        if has_text else 0.0)
        agreement, has_agreement = self._agreement(result, others)

        w_conf = cfg.weight_confidence
        w_plaus = cfg.weight_plausibility if has_text else 0.0
        w_agree = cfg.weight_agreement if has_agreement else 0.0
        total_weight = w_conf + w_plaus + w_agree
        if total_weight <= 0.0:
            score = 0.0
        else:
            score = (w_conf * confidence + w_plaus * plausibility
                     + w_agree * agreement) / total_weight

        if result.is_empty:
            score = 0.0

        return EngineScore(
            engine=result.engine,
            level=level,
            total=float(score),
            confidence=confidence,
            raw_confidence=raw,
            plausibility=plausibility,
            agreement=agreement,
            char_count=signals.char_count,
            duration_s=result.duration_s,
        )

    # -- running ----------------------------------------------------------- #

    def _can_run(self, engine: OcrEngine, task: RegionTask) -> tuple[bool, str]:
        caps = engine.capabilities()
        if not engine.available():
            return False, (engine.unavailable_reason()
                           or f"motor {engine.name} indisponível")
        if caps.requires_pdf_page and task.pdf_page is None:
            return False, ("este motor precisa da página do PDF, que não foi "
                           "fornecida para esta região")
        if not caps.requires_pdf_page and not task.has_image:
            return False, "não há imagem rasterizada para esta região"
        if not engine.supports_language(task.lang):
            return False, (f"o idioma '{task.lang}' não está disponível neste "
                           f"motor")
        return True, ""

    @staticmethod
    def _invoke(engine: OcrEngine, task: RegionTask) -> OcrResult:
        caps = engine.capabilities()
        if caps.requires_pdf_page:
            # Level 0 has its own entry point; the protocol method takes a
            # raster and cannot serve it.
            recognize_page = getattr(engine, "recognize_page", None)
            if recognize_page is None:
                return empty_result(
                    engine.name, task.lang, region_kind=task.region_kind,
                    warning=("motor declara exigir a página do PDF mas não "
                             "expõe recognize_page"))
            # ``verdict`` is an optional extension of the level-0 entry
            # point, not part of the Protocol, so it is offered only to an
            # adapter that declares the keyword.  Asking the signature rather
            # than assuming keeps a third adapter from dying with a TypeError
            # on its first page the day someone writes one.
            extra = ({"verdict": task.verdict}
                     if task.verdict is not None
                     and _accepts_verdict(recognize_page) else {})
            # Annotated rather than returned straight through: the engine
            # came out of ``getattr`` and is therefore ``Any``, so mypy
            # otherwise reports the whole call as an untyped escape hatch.
            page_result: OcrResult = recognize_page(
                task.pdf_page, lang=task.lang, clip=task.clip,
                scale=task.scale, psm_hint=task.region_kind, **extra)
            return page_result
        assert task.image is not None
        return engine.recognize(task.image, lang=task.lang,
                                psm_hint=task.region_kind)

    def run(self, task: RegionTask) -> ArbitrationOutcome:
        """Run the cascade for ``task`` and return the chosen result."""
        cfg = self.config
        started = time.perf_counter()
        decisions: list[EscalationDecision] = []
        scores: list[EngineScore] = []
        results: list[OcrResult] = []
        engines_run: list[str] = []
        step = 0

        for engine in self.engines:
            level = engine.capabilities().level
            if level > cfg.max_level:
                decisions.append(EscalationDecision(
                    step, engine.name, level, "skipped", None, None,
                    f"nível {level} está acima do teto configurado "
                    f"({cfg.max_level})"))
                step += 1
                continue
            spent = (len(engines_run) if cfg.count_empty_in_budget
                     else sum(1 for r in results if not r.is_empty))
            if spent >= cfg.max_engines:
                decisions.append(EscalationDecision(
                    step, engine.name, level, "skipped", None, None,
                    f"limite de {cfg.max_engines} motores por região atingido"))
                step += 1
                continue

            ok, why = self._can_run(engine, task)
            if not ok:
                decisions.append(EscalationDecision(
                    step, engine.name, level, "skipped", None, None, why))
                step += 1
                continue

            result = self._invoke(engine, task)
            results.append(result)
            engines_run.append(engine.name)

            # Rescore everything each round: agreement is a property of the
            # set, so an earlier result's score can legitimately rise once a
            # second engine corroborates it.
            scores = [
                self.score(r, level=self._level_of(r.engine), lang=task.lang,
                           others=[o for o in results if o is not r])
                for r in results
            ]
            current = next(s for s in scores if s.engine == result.engine)
            threshold = cfg.threshold_for(level)

            if current.total >= threshold:
                decisions.append(EscalationDecision(
                    step, engine.name, level, "accepted", current.total,
                    threshold,
                    f"escore {current.total:.3f} atingiu o limite "
                    f"{threshold:.2f} — "
                    f"confiança {current.confidence:.2f}, plausibilidade "
                    f"{current.plausibility:.2f}"))
                self.log.debug("region %s accepted by %s at %.3f",
                               task.region_id or "?", engine.name, current.total)
                step += 1
                break

            decisions.append(EscalationDecision(
                step, engine.name, level, "escalated", current.total, threshold,
                self._escalation_reason(current, threshold, result)))
            self.log.debug("region %s escalating past %s (%.3f < %.2f)",
                           task.region_id or "?", engine.name,
                           current.total, threshold)
            step += 1

        if not scores:
            decisions.append(EscalationDecision(
                step, "—", -1, "exhausted", None, None,
                "nenhum motor de OCR estava disponível para esta região"))
            none = RegionDecision(
                Decision.ABSTAINED, 0.0, cfg.accept_threshold,
                cfg.policy.review_score,
                ("Nenhum motor de OCR pôde processar esta região.",),
            ) if cfg.decision_enabled else None
            return ArbitrationOutcome(
                result=empty_result(
                    "arbiter", task.lang, region_kind=task.region_kind,
                    warning=("Nenhum motor de OCR pôde processar esta região. "
                             "Verifique a instalação do Tesseract."),
                    decisions=[str(d) for d in decisions]),
                scores=(), decisions=tuple(decisions), engines_run=(),
                escalated=False,
                total_duration_s=time.perf_counter() - started,
                decision=none, candidates=tuple(results),
            )

        best = max(scores, key=lambda s: (s.total, -s.level, s.engine))
        chosen = next(r for r in results if r.engine == best.engine)
        escalated = len(engines_run) > 1
        cleared = decisions[-1].action == "accepted"
        threshold = cfg.threshold_for(best.level)

        if not cleared:
            if cfg.decision_enabled:
                # Sol §SOL-2: below the bar is *not* accepted.  The best
                # result is still carried — the decision below says whether
                # it is reviewable or must be abstained.
                decisions.append(EscalationDecision(
                    step, best.engine, best.level, "exhausted", best.total,
                    threshold,
                    f"nenhum motor atingiu o limite; o melhor escore foi "
                    f"{best.total:.3f} ({best.engine}) entre "
                    f"{', '.join(sorted(engines_run))} — decisão abaixo"))
                step += 1
            elif escalated:
                decisions.append(EscalationDecision(
                    step, best.engine, best.level, "accepted", best.total,
                    threshold,
                    f"nenhum motor atingiu o limite; escolhido o melhor escore "
                    f"({best.total:.3f}) entre "
                    f"{', '.join(sorted(engines_run))}"))

        decision: RegionDecision | None = None
        if cfg.decision_enabled:
            page_space = self._requires_page(best.engine)
            decision = decide(
                chosen, best.total, policy=cfg.policy,
                image=None if page_space else task.image,
                langs=normalise_lang(task.lang), region_kind=task.region_kind,
                accept_threshold=threshold, reached_threshold=cleared,
                trusted_source=page_space,
            )
            decisions.append(EscalationDecision(
                step, best.engine, best.level, str(decision.decision), best.total,
                threshold, " ".join(decision.reasons_pt) or "evidência e escore coerentes"))

        annotated = chosen.with_meta(
            arbiter_score=best.total,
            arbiter_engines=tuple(engines_run),
            arbiter_escalated=escalated,
            arbiter_decisions=tuple(str(d) for d in decisions),
            arbiter_threshold=threshold,
            **({"decision": str(decision.decision),
                "decision_reasons": decision.reasons_pt}
               if decision is not None else {}),
        )
        return ArbitrationOutcome(
            result=annotated,
            scores=tuple(scores),
            decisions=tuple(decisions),
            engines_run=tuple(engines_run),
            escalated=escalated,
            total_duration_s=time.perf_counter() - started,
            decision=decision,
            candidates=tuple(results),
        )

    # -- helpers ----------------------------------------------------------- #

    def _requires_page(self, engine_name: str) -> bool:
        """True when the engine's boxes are in page space, not crop space."""
        for engine in self.engines:
            if engine.name == engine_name:
                return engine.capabilities().requires_pdf_page
        return False

    def _level_of(self, engine_name: str) -> int:
        for engine in self.engines:
            if engine.name == engine_name:
                return engine.capabilities().level
        return EngineLevel.VLM

    @staticmethod
    def _escalation_reason(score: EngineScore, threshold: float,
                           result: OcrResult) -> str:
        """Name the *weakest* term, so the message points at the real cause."""
        if result.is_empty:
            return (f"nenhum texto reconhecido; escalando "
                    f"(limite {threshold:.2f})")
        terms = [
            ("a confiança calibrada", score.confidence),
            ("a plausibilidade linguística", score.plausibility),
        ]
        if score.agreement > 0.0:
            terms.append(("a concordância entre motores", score.agreement))
        label, value = min(terms, key=lambda kv: (kv[1], kv[0]))
        return (f"escore {score.total:.3f} abaixo do limite {threshold:.2f}; "
                f"o termo mais fraco foi {label} ({value:.2f})")


def arbitrate(engines: Sequence[OcrEngine], task: RegionTask,
              config: ArbiterConfig | None = None) -> ArbitrationOutcome:
    """One-shot convenience wrapper around :class:`Arbiter`."""
    return Arbiter(engines, config).run(task)
