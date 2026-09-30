"""The per-region arbiter (SPEC §7.1), driven by mock engines.

Mocks rather than real engines, deliberately.  The arbiter's job is to decide
*between* engines, and the only way to test a decision procedure is to control
its inputs exactly: an engine that returns known text at a known confidence, on
demand, every time.  Real engines are tested for what they read
(``test_engines.py``); this file tests what is chosen and why.

Two properties are asserted everywhere and are the reason this front is worth
having at all:

* **deterministic** — the same region gives the same answer, always, including
  the tie-breaks;
* **logged** — every step of the cascade leaves a decision record naming the
  engine, the score, the threshold and the weakest term.  A cascade that cannot
  say why it escalated is unfixable in the field.
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from caissa.ocr.arbiter import (
    Arbiter,
    ArbiterConfig,
    EngineCalibration,
    RegionTask,
    arbitrate,
)
from caissa.ocr.decision import Decision
from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind

CLEAN = ("The rook belongs behind the passed pawn and the defender simply "
         "waits while the attacking side loses time with every step")
NOISY = ("Th3 r00k b3l0ngs b3h1nd th3 passcd pawn und th3 d3f3nd3r s1mply "
         "wa1ts wh1l3 th3 attack1ng s1d3 l0s3s t1m3")
GARBAGE = "xqz vbn mkl pqr wxy zzq jjk vvn mmq pplx wqz bnm kkl rrt yyu iio"


# --------------------------------------------------------------------------- #
# Mock engine
# --------------------------------------------------------------------------- #


def make_result(engine: str, text: str, confidence: float, *,
                lang: str = "eng",
                region_kind: RegionKind = RegionKind.PARAGRAPH,
                duration_s: float = 0.01) -> OcrResult:
    """An ``OcrResult`` whose every word carries ``confidence``."""
    words: list[OcrWord] = []
    x = 0.0
    for index, token in enumerate(text.split()):
        width = 10.0 * len(token)
        box = BBox.from_edges(x, 0.0, x + width, 20.0)
        chars = tuple(
            OcrChar(text=ch,
                    box=BBox(x + 10.0 * i, 0.0, 10.0, 20.0),
                    confidence=confidence)
            for i, ch in enumerate(token)
        )
        words.append(OcrWord(text=token, box=box, confidence=confidence,
                             chars=chars, block_index=0, paragraph_index=0,
                             line_index=0, word_index=index))
        x += width + 10.0
    line = OcrLine(words=tuple(words),
                   box=BBox.from_edges(0.0, 0.0, max(x, 1.0), 20.0),
                   baseline=None, block_index=0, paragraph_index=0,
                   line_index=0, kind=region_kind, font_size=20.0)
    return OcrResult(engine=engine, lang=lang,
                     lines=(line,) if words else (),
                     region_kind=region_kind, duration_s=duration_s)


class MockEngine:
    """An engine whose output, availability and cost are all dictated."""

    def __init__(self, name: str, level: int, text: str, confidence: float, *,
                 available: bool = True,
                 languages: set[str] | None = None,
                 requires_pdf_page: bool = False,
                 reason: str | None = None,
                 raises: Exception | None = None) -> None:
        self.name = name
        self._level = level
        self._text = text
        self._confidence = confidence
        self._available = available
        self._languages = languages if languages is not None else {"eng", "por"}
        self._requires_pdf_page = requires_pdf_page
        self._reason = reason or f"{name} indisponível (mock)"
        self._raises = raises
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def unavailable_reason(self) -> str | None:
        return None if self._available else self._reason

    def languages(self) -> set[str]:
        return set(self._languages)

    def supports_language(self, lang: str) -> bool:
        return any(part in self._languages
                   for part in (lang or "").replace("+", " ").split()) or not lang

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=self._level,
            cost_per_megapixel_s=0.1 * (self._level + 1),
            supports_char_boxes=True,
            supports_confidence=True,
            handles_layout=False,
            requires_pdf_page=self._requires_pdf_page,
            gpu_capable=False,
        )

    def recognize(self, image, *, lang: str = "eng",
                  psm_hint: RegionKind = RegionKind.PARAGRAPH) -> OcrResult:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return make_result(self.name, self._text, self._confidence,
                           lang=lang, region_kind=psm_hint)

    def recognize_page(self, page, *, lang: str = "eng", clip=None,
                       scale: float = 1.0,
                       psm_hint: RegionKind = RegionKind.PARAGRAPH) -> OcrResult:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return make_result(self.name, self._text, self._confidence,
                           lang=lang, region_kind=psm_hint)


def inked_region(height: int = 60, width: int = 900) -> np.ndarray:
    """Paper with ink where the mock engine puts its words.

    The decision policy (Sol §SOL-2) refuses a word floating over blank
    paper, so a mock that reports words needs pixels under them: a row of
    stripes across the mock's line is enough to look like print.
    """
    image = np.full((height, width), 255, dtype=np.uint8)
    image[2:18, ::3] = 0
    image[2:18, 1::3] = 30
    return image


@pytest.fixture
def region() -> RegionTask:
    return RegionTask(image=inked_region(),
                      lang="eng", region_kind=RegionKind.PARAGRAPH,
                      region_id="p1-r3")


#: Calibration that passes raw confidence through, so a test can reason about
#: the arithmetic instead of about the engine reputation table.
IDENTITY = EngineCalibration(floor=0.0, gamma=1.0, worst_word_weight=0.0)


def identity_config(**kwargs) -> ArbiterConfig:
    calibrations = {name: IDENTITY for name in
                    ("l0", "l1", "l2", "l3", "good", "bad", "a", "b")}
    return ArbiterConfig(calibrations=calibrations, **kwargs)


# --------------------------------------------------------------------------- #
# Accepting without escalating
# --------------------------------------------------------------------------- #


def test_a_confident_first_engine_stops_the_cascade(region):
    first = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.97)
    second = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.99)
    outcome = Arbiter([first, second], identity_config()).run(region)

    assert outcome.engines_run == ("l1",)
    assert second.calls == 0, "o nível 2 rodou sem necessidade"
    assert not outcome.escalated
    assert outcome.result.engine == "l1"
    assert outcome.decisions[-1].action == "accepted"


def test_escalation_when_the_first_engine_is_weak(region):
    weak = MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.42)
    strong = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.96)
    outcome = Arbiter([weak, strong], identity_config()).run(region)

    assert outcome.engines_run == ("l1", "l2")
    assert outcome.escalated
    assert outcome.result.engine == "l2"
    actions = [d.action for d in outcome.decisions]
    assert "escalated" in actions and actions[-1] == "accepted"


def test_escalation_reason_names_the_weakest_term(region):
    weak = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.20)
    strong = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.98)
    outcome = Arbiter([weak, strong], identity_config()).run(region)

    escalation = next(d for d in outcome.decisions if d.action == "escalated")
    assert "confiança" in escalation.reason_pt, escalation.reason_pt
    assert escalation.score is not None and escalation.threshold is not None
    assert escalation.score < escalation.threshold


def test_garbage_text_escalates_even_at_high_confidence(region):
    """Confidence alone must not be able to win.

    An engine that is sure it read ``xqz vbn mkl`` is exactly the failure mode
    the plausibility term exists for, and it is the failure mode that a
    confidence-only arbiter cannot see.
    """
    liar = MockEngine("l1", EngineLevel.TESSERACT, GARBAGE, 0.99)
    honest = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.90)
    outcome = Arbiter([liar, honest], identity_config()).run(region)

    assert outcome.result.engine == "l2", outcome.explain_pt()
    liar_score = next(s for s in outcome.scores if s.engine == "l1")
    honest_score = next(s for s in outcome.scores if s.engine == "l2")
    assert liar_score.confidence > honest_score.confidence
    assert liar_score.plausibility < honest_score.plausibility
    assert liar_score.total < honest_score.total


def test_agreement_raises_the_score_of_a_corroborated_result(region):
    """Agreement is a property of the set, so earlier scores get recomputed."""
    a = MockEngine("a", EngineLevel.TESSERACT, CLEAN, 0.50)
    b = MockEngine("b", EngineLevel.PADDLE, CLEAN, 0.50)
    outcome = Arbiter([a, b], identity_config()).run(region)

    assert outcome.engines_run == ("a", "b")
    for score in outcome.scores:
        assert score.agreement > 0.90, score.describe_pt()


def test_disagreement_leaves_agreement_low(region):
    a = MockEngine("a", EngineLevel.TESSERACT, CLEAN, 0.50)
    b = MockEngine("b", EngineLevel.PADDLE, GARBAGE, 0.50)
    outcome = Arbiter([a, b], identity_config()).run(region)
    for score in outcome.scores:
        assert score.agreement < 0.60, score.describe_pt()


INDEX_LEFT = ["Pogosiants R352, 441, P29, 205,", "217, 239, 244, 247, 323, 368,", "Polak P251",
              "Polgar, J. P305", "Polugaevsky R296", "Ponziani R7, P93", "Popovic R125",
              "Portisch, L. R137, M27, 237", "Pospisil P425", "Prokes R177, 181, P137,",
              "Prokop P139, 171, 209,", "Psakhis M61, 79", "Purtov M9"]
INDEX_RIGHT = ["Ruge M30", "Rumiantsev P121, 390", "Ruszcynski P119", "Sackmann P60, 113",
               "Salov R279, P83", "Salvio R179", "Salwe R93, 497", "Saren M89",
               "Schlechter R3, 11", "Schmid P240", "Seirawan M12", "Short M200, 201",
               "Smyslov R44"]


def test_the_agreement_is_measured_in_the_order_each_engine_read():
    """Crítico da fase 5, ciclo 4: on the Nunn p. 288 the B13 moved Tesseract's lines into the
    book's order, and the moved lines raised the agreement of RapidOCR's reading of the index,
    interleaved, past Tesseract's own score: RapidOCR won.  The lines the B13 moved keep the
    engine's order (``engine_order_text``), and the agreement is measured on it.  The shape:
    two lists read by columns, and by rows."""
    by_columns = " ".join(INDEX_LEFT + INDEX_RIGHT)
    by_rows = " ".join(entry for pair in zip(INDEX_LEFT, INDEX_RIGHT, strict=True)
                        for entry in pair)
    tesseract = make_result("tesseract", by_columns, 0.9)
    moved = make_result("tesseract", by_rows, 0.9).with_meta(engine_order_text=by_columns)
    rapid = make_result("rapidocr", by_rows, 0.9)
    assert Arbiter._agreement(moved, [rapid]) == Arbiter._agreement(tesseract, [rapid])
    assert Arbiter._agreement(rapid, [moved]) == Arbiter._agreement(rapid, [tesseract])
    # the sabotage: measured on the moved lines, RapidOCR's reading agrees with them entirely
    plain = make_result("tesseract", by_rows, 0.9)
    assert Arbiter._agreement(rapid, [plain])[0] > Arbiter._agreement(rapid, [tesseract])[0]


def test_the_rows_move_the_readers_lines_and_never_the_agreement(region, monkeypatch):
    """The B13 moves the lines of a reading the engine segmented itself (``psm`` 1/3), before it
    is scored: the reader gets the moved lines, and confidence and plausibility judge them.
    The agreement among the engines stays the one of their own orders -- with the B13 on it is
    the agreement with it off.  ``rows_of_tables`` is replaced by a stand-in that reverses the
    words; the sabotage measures the agreement on the moved lines."""
    import caissa.ocr.arbiter as arbiter_module
    import caissa.ocr.layout.rows as rows_module

    class Segmenting(MockEngine):
        def recognize(self, image, *, lang: str = "eng",
                      psm_hint: RegionKind = RegionKind.PARAGRAPH) -> OcrResult:
            return super().recognize(image, lang=lang, psm_hint=psm_hint).with_meta(psm=3)

    def reversed_rows(result: OcrResult, *, config=None) -> OcrResult:
        words = " ".join(reversed(result.text.split()))
        return make_result(result.engine, words, 0.5).with_meta(**dict(result.meta), table_rows=1)

    monkeypatch.setattr(rows_module, "rows_of_tables", reversed_rows)

    def run(table_rows: bool):
        engines = [Segmenting("a", EngineLevel.TESSERACT, CLEAN, 0.50),
                   MockEngine("b", EngineLevel.PADDLE, CLEAN, 0.50)]
        return Arbiter(engines, identity_config(table_rows=table_rows)).run(region)

    on, off = run(True), run(False)
    moved = next(r for r in on.candidates if r.engine == "a")
    assert moved.text == " ".join(reversed(CLEAN.split())), "the reader gets the moved lines"
    assert [s.agreement for s in on.scores] == [s.agreement for s in off.scores]
    monkeypatch.setattr(arbiter_module, "_engine_order", lambda result: result.text)
    sabotaged = run(True)
    assert [s.agreement for s in sabotaged.scores] != [s.agreement for s in off.scores]


# --------------------------------------------------------------------------- #
# Level 0 is held to a higher bar
# --------------------------------------------------------------------------- #


def test_level_zero_has_a_stricter_threshold():
    """Accepting a bad text layer is silent and permanent; accepting a bad OCR
    result at least leaves low confidences behind."""
    config = identity_config()
    assert (config.threshold_for(EngineLevel.PDF_TEXT_LAYER)
            > config.threshold_for(EngineLevel.TESSERACT))


def test_a_distrusted_text_layer_escalates_to_ocr():
    """A layer the CMap audit only half believed must not end the cascade.

    0.60 is what the level-0 engine reports for a page it accepted on font
    structure alone — Cyrillic, say, where neither the lexicon nor the n-gram
    model could read a word.  Clean-looking text at that confidence still falls
    short of the stricter level-0 bar, and OCR gets a turn.
    """
    layer = MockEngine("l0", EngineLevel.PDF_TEXT_LAYER, CLEAN, 0.60,
                       requires_pdf_page=True)
    ocr = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.99)
    task = RegionTask(image=np.full((60, 900), 255, dtype=np.uint8),
                      pdf_page=object(), lang="eng")
    outcome = Arbiter([layer, ocr], identity_config()).run(task)
    assert outcome.engines_run == ("l0", "l1")
    assert outcome.result.engine == "l1"


def test_level_zero_is_skipped_without_a_pdf_page(region):
    layer = MockEngine("l0", EngineLevel.PDF_TEXT_LAYER, CLEAN, 0.99,
                       requires_pdf_page=True)
    ocr = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.97)
    outcome = Arbiter([layer, ocr], identity_config()).run(region)

    assert layer.calls == 0
    skipped = next(d for d in outcome.decisions if d.engine == "l0")
    assert skipped.action == "skipped"
    assert "página do PDF" in skipped.reason_pt


# --------------------------------------------------------------------------- #
# Gates: language, availability, budget
# --------------------------------------------------------------------------- #


def test_an_unavailable_engine_is_skipped_with_its_reason(region):
    absent = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.99,
                        available=False,
                        reason="Tesseract não foi encontrado no PATH.")
    present = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.95)
    outcome = Arbiter([absent, present], identity_config()).run(region)

    assert absent.calls == 0
    assert outcome.result.engine == "l2"
    skipped = next(d for d in outcome.decisions if d.engine == "l1")
    assert skipped.action == "skipped"
    assert "Tesseract" in skipped.reason_pt


def test_an_engine_without_the_language_is_skipped(region):
    english_only = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.99,
                              languages={"eng"})
    russian = MockEngine("l3", EngineLevel.SURYA, CLEAN, 0.90,
                         languages={"rus"})
    task = RegionTask(image=region.image, lang="rus")
    outcome = Arbiter([english_only, russian], identity_config()).run(task)

    assert english_only.calls == 0
    assert outcome.result.engine == "l3"


def test_max_engines_caps_the_budget(region):
    engines = [MockEngine(f"l{i}", i, NOISY, 0.30) for i in range(1, 4)]
    outcome = Arbiter(engines, identity_config(max_engines=2)).run(region)

    assert len(outcome.engines_run) == 2
    assert engines[2].calls == 0
    capped = next(d for d in outcome.decisions
                  if d.action == "skipped" and "limite" in d.reason_pt)
    assert "2" in capped.reason_pt


def test_max_level_stops_the_cascade(region):
    cheap = MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.30)
    dear = MockEngine("l3", EngineLevel.SURYA, CLEAN, 0.99)
    outcome = Arbiter([cheap, dear],
                      identity_config(max_level=EngineLevel.TESSERACT)).run(region)

    assert dear.calls == 0
    assert outcome.result.engine == "l1"
    skipped = next(d for d in outcome.decisions if d.engine == "l3")
    assert "teto" in skipped.reason_pt


def test_no_engine_at_all_yields_an_explained_empty_result(region):
    outcome = Arbiter([], identity_config()).run(region)
    assert outcome.result.is_empty
    assert outcome.result.warnings
    assert "Tesseract" in outcome.result.warnings[0]
    assert outcome.decisions[-1].action == "exhausted"
    assert outcome.scores == ()


def test_every_engine_unavailable_yields_an_explained_empty_result(region):
    engines = [MockEngine(f"l{i}", i, CLEAN, 0.9, available=False)
               for i in (1, 2)]
    outcome = Arbiter(engines, identity_config()).run(region)
    assert outcome.result.is_empty
    assert outcome.decisions[-1].action == "exhausted"


def test_a_raising_engine_does_not_abort_the_cascade(region):
    """A batch of 500 books must not stop because one engine threw."""
    broken = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.99,
                        raises=RuntimeError("segfault simulado"))
    good = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.95)
    with pytest.raises(RuntimeError):
        Arbiter([broken, good], identity_config()).run(region)


# --------------------------------------------------------------------------- #
# Determinism and the record
# --------------------------------------------------------------------------- #


def test_the_cascade_is_deterministic(region):
    def build():
        return [MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.55),
                MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.70),
                MockEngine("l3", EngineLevel.SURYA, CLEAN, 0.72)]

    runs = [Arbiter(build(), identity_config()).run(region) for _ in range(5)]
    first = runs[0]
    for other in runs[1:]:
        assert other.engines_run == first.engines_run
        assert other.result.engine == first.result.engine
        assert other.result.text == first.result.text
        assert [d.action for d in other.decisions] == \
               [d.action for d in first.decisions]
        assert [round(s.total, 12) for s in other.scores] == \
               [round(s.total, 12) for s in first.scores]


def test_a_tie_is_broken_by_level_then_name(region):
    """Two engines, identical output and confidence.  Something must decide,
    and it must be the same thing every time: the cheaper level wins, and the
    name breaks a remaining tie."""
    a = MockEngine("b", EngineLevel.PADDLE, CLEAN, 0.60)
    b = MockEngine("a", EngineLevel.TESSERACT, CLEAN, 0.60)
    outcome = Arbiter([a, b], identity_config()).run(region)
    assert outcome.winner is not None
    assert outcome.winner.engine == "a", outcome.explain_pt()


def test_every_step_is_recorded(region):
    engines = [MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.40),
               MockEngine("l2", EngineLevel.PADDLE, NOISY, 0.45),
               MockEngine("l3", EngineLevel.SURYA, CLEAN, 0.99)]
    outcome = Arbiter(engines, identity_config()).run(region)

    assert len(outcome.decisions) >= 3
    assert [d.step for d in outcome.decisions] == \
           sorted(d.step for d in outcome.decisions)
    for decision in outcome.decisions:
        assert decision.reason_pt, decision
        assert str(decision)
    assert outcome.explain_pt().count("\n") >= 2


def test_the_record_is_attached_to_the_result(region):
    """The decision trail must survive into the IR, not only into the log."""
    engines = [MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.40),
               MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.99)]
    outcome = Arbiter(engines, identity_config()).run(region)
    meta = outcome.result.meta
    assert meta["arbiter_engines"] == ("l1", "l2")
    assert meta["arbiter_escalated"] is True
    assert meta["arbiter_score"] == pytest.approx(outcome.winner.total)
    assert len(meta["arbiter_decisions"]) == len(outcome.decisions)


def test_the_cascade_logs(region, caplog):
    engines = [MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.40),
               MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.99)]
    with caplog.at_level(logging.DEBUG, logger="caissa.ocr.arbiter"):
        Arbiter(engines, identity_config()).run(region)
    messages = [r.getMessage() for r in caplog.records]
    assert any("escalating" in m for m in messages), messages
    assert any("accepted" in m for m in messages), messages
    assert any("p1-r3" in m for m in messages), messages


def test_nothing_reaches_the_threshold_and_the_best_is_carried_but_not_accepted(region):
    """Sol §SOL-2: below the bar is review or abstention, never ``accepted``."""
    engines = [MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.30),
               MockEngine("l2", EngineLevel.PADDLE, NOISY, 0.55)]
    outcome = Arbiter(engines, identity_config()).run(region)
    assert outcome.result.engine == "l2"
    exhausted = next(d for d in outcome.decisions if d.action == "exhausted")
    assert "nenhum motor atingiu o limite" in exhausted.reason_pt
    assert outcome.decision is not None
    assert outcome.decision.decision in (Decision.REVIEW, Decision.ABSTAINED)
    assert not outcome.accepted
    assert outcome.decisions[-1].action == str(outcome.decision.decision)
    assert not any(d.action == "accepted" for d in outcome.decisions)
    assert outcome.candidates and {r.engine for r in outcome.candidates} == {"l1", "l2"}


def test_the_legacy_cascade_still_labels_the_best_of_a_bad_lot_accepted(region):
    """Off, the decision layer reproduces the pre-Sol baseline exactly."""
    engines = [MockEngine("l1", EngineLevel.TESSERACT, NOISY, 0.30),
               MockEngine("l2", EngineLevel.PADDLE, NOISY, 0.55)]
    outcome = Arbiter(engines, identity_config(decision_enabled=False)).run(region)
    assert outcome.decision is None
    assert outcome.decisions[-1].action == "accepted"
    assert "nenhum motor atingiu o limite" in outcome.decisions[-1].reason_pt


def test_an_empty_result_scores_zero(region):
    empty = MockEngine("l1", EngineLevel.TESSERACT, "", 0.99)
    good = MockEngine("l2", EngineLevel.PADDLE, CLEAN, 0.90)
    outcome = Arbiter([empty, good], identity_config()).run(region)
    score = next(s for s in outcome.scores if s.engine == "l1")
    assert score.total == 0.0
    assert outcome.result.engine == "l2"
    escalation = next(d for d in outcome.decisions if d.action == "escalated")
    assert "nenhum texto" in escalation.reason_pt


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def test_default_calibrations_are_neutral_and_provisional():
    """Sol §SOL-4: no floor, no gamma — a reputation is not a measurement.

    The fitted tables of ``caissa/ocr/data/calibration.json`` are what bend
    the curve now, per facet, and an engine without one is scored on its raw
    number and *says so* through ``provisional``.
    """
    from caissa.ocr.arbiter import DEFAULT_CALIBRATIONS

    tess = DEFAULT_CALIBRATIONS["tesseract"]
    assert tess.floor == 0.0 and tess.gamma == 1.0
    assert tess.apply(0.50) == pytest.approx(0.50)
    assert tess.provisional and tess.table is None
    assert not DEFAULT_CALIBRATIONS["pdf_text_layer"].provisional


def test_a_fitted_table_is_used_per_facet_and_flagged():
    from caissa.ocr.calibration import CalibrationSet, CalibrationTable

    fitted = CalibrationSet(tables={
        "l1": CalibrationTable(knots=((0.0, 0.0), (1.0, 0.5)), samples=100),
        "l1|lang=eng": CalibrationTable(knots=((0.0, 0.0), (1.0, 1.0)), samples=100),
    })
    config = identity_config(calibration_set=fitted)
    config.calibrations = {}          # nothing static: only the fitted set answers
    from caissa.ocr.calibration import facet_key

    english = config.calibration_for("l1", facet_key("l1", lang="eng"))
    assert english.key == "l1|lang=eng" and not english.provisional
    assert english.apply(0.8) == pytest.approx(0.8)
    other = config.calibration_for("l1", facet_key("l1", lang="deu"))
    assert other.key == "l1"
    assert other.apply(0.8) == pytest.approx(0.4)
    assert config.calibration_for("l9").provisional


def test_calibration_is_monotone():
    for name, calibration in [("identity", IDENTITY)] + list(
            __import__("caissa.ocr.arbiter", fromlist=["x"])
            .DEFAULT_CALIBRATIONS.items()):
        values = [calibration.apply(v / 20.0) for v in range(21)]
        assert values == sorted(values), name


def test_an_unknown_engine_gets_a_neutral_provisional_fallback():
    from caissa.ocr.calibration import CalibrationSet

    config = ArbiterConfig(calibration_set=CalibrationSet())
    fallback = config.calibration_for("something-new")
    assert fallback.floor == 0.0 and fallback.provisional
    assert fallback.apply(0.7) == pytest.approx(0.7)


# --------------------------------------------------------------------------- #
# The convenience wrapper
# --------------------------------------------------------------------------- #


def test_arbitrate_matches_the_class(region):
    engines = [MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.97)]
    a = arbitrate(engines, region, identity_config())
    b = Arbiter([MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.97)],
                identity_config()).run(region)
    assert a.result.text == b.result.text
    assert a.engines_run == b.engines_run


# --------------------------------------------------------------------------- #
# The optional verdict hand-down
# --------------------------------------------------------------------------- #


def test_a_precomputed_verdict_reaches_an_engine_that_wants_one():
    """The page runner computes the level-0 verdict once and hands it down.

    Without this the cascade re-assesses every region from scratch, and a
    region too short to judge on its own gets condemned as "a scan" by the
    24-character floor.  See ``caissa.ocr.page``.
    """
    seen = {}

    class WantsVerdict(MockEngine):
        def recognize_page(self, page, *, lang="eng", clip=None, scale=1.0,
                           psm_hint=RegionKind.PARAGRAPH, verdict=None):
            seen["verdict"] = verdict
            return make_result(self.name, CLEAN, 0.95, lang=lang)

    engine = WantsVerdict("wants", EngineLevel.PDF_TEXT_LAYER, CLEAN, 0.95,
                          requires_pdf_page=True)
    Arbiter([engine], identity_config()).run(
        RegionTask(pdf_page=object(), lang="eng", verdict="o-veredito"))
    assert seen["verdict"] == "o-veredito"


def test_an_engine_without_the_keyword_is_not_handed_one():
    """``verdict`` is an extension of the level-0 entry point, not part of the
    Protocol.  An adapter that never heard of it must keep working — dying with
    a ``TypeError`` on its first page would be a latent trap for whoever writes
    the third level-0 engine.

    ``MockEngine.recognize_page`` takes no ``verdict``, which is exactly the
    shape being guarded against.
    """
    engine = MockEngine("plain", EngineLevel.PDF_TEXT_LAYER, CLEAN, 0.95,
                        requires_pdf_page=True)
    outcome = Arbiter([engine], identity_config()).run(
        RegionTask(pdf_page=object(), lang="eng", verdict="o-veredito"))
    assert not outcome.result.is_empty
    assert engine.calls == 1


# --------------------------------------------------------------------------- #
# The weak-word term (F5_REPORT_C2 §5)
# --------------------------------------------------------------------------- #


def _result_with(confidences):
    """One line whose words carry exactly ``confidences``."""
    words = tuple(
        OcrWord(text=f"w{i}", box=BBox(10.0 * i, 0.0, 9.0, 12.0), confidence=c)
        for i, c in enumerate(confidences))
    line = OcrLine(words=words, box=BBox(0.0, 0.0, 10.0 * len(words), 12.0))
    return OcrResult(engine="mock", lang="eng", lines=(line,))


def test_one_dead_word_destroys_the_minimum_but_not_the_quantile():
    """**The defect this replaced, in three lines.**

    Ninety-nine confident words and one artefact read at zero — a speck, a
    diagram coordinate, a fragment of a rule.  Every full page has one.  The
    minimum reports 0.000 and is therefore a *constant* across all pages,
    which turns its 0.35 weight into a flat 35 % penalty rather than a signal.

    Measured on the corpus before the fix: Tesseract's minimum word confidence
    was 0.000 on **12 of 12** pages, and its calibrated confidence was
    therefore 0.000 on 12 of 12.  See docs/quality/F5_REPORT_C2.md §5.
    """
    result = _result_with([0.9] * 99 + [0.0])
    assert result.min_word_confidence == 0.0
    assert result.weak_word_confidence(0.05) == pytest.approx(0.9)


def test_the_quantile_still_sees_real_trouble():
    """The other half: it must not become blind to an engine that is
    genuinely weak.  A result where a fifth of the words are bad has to report
    a low weak-word confidence, or the term is back to hiding failures — which
    is the very thing ASSETS §2.11 put it there to stop."""
    result = _result_with([0.1] * 20 + [0.9] * 80)
    assert result.weak_word_confidence(0.05) == pytest.approx(0.1)
    # The bad fifth occupies everything below the twentieth percentile, so the
    # quantile reports it right up to that edge...
    assert result.weak_word_confidence(0.19) == pytest.approx(0.1)
    # ...and recovers above it, which is what makes this a quantile rather
    # than a lower minimum: it tracks *how much* is bad, not merely that
    # something is.
    assert result.weak_word_confidence(0.25) == pytest.approx(0.9)


def test_an_empty_result_has_no_weak_word():
    assert _result_with([]).weak_word_confidence(0.05) == 0.0


def test_the_quantile_is_what_the_arbiter_actually_blends():
    """Guard against the fix living in ``types`` and never being called.

    The scoring path must use the quantile; if it goes back to the minimum,
    the raw confidence collapses and this fails.
    """
    arbiter = Arbiter([], ArbiterConfig(
        calibrations={"mock": EngineCalibration(floor=0.0, gamma=1.0,
                                                worst_word_weight=0.35)}))
    calibrated, raw, _ = arbiter._confidence_of(_result_with([0.9] * 99 + [0.0]))
    assert raw == pytest.approx(0.9, abs=0.01), (
        "o árbitro voltou a misturar o mínimo: uma palavra morta em cem "
        "derrubou a confiança da página inteira")
    assert calibrated == pytest.approx(0.9, abs=0.01)
