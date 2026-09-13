"""Sol §SOL-4: fitted calibration tables and evidence-based routing."""

from __future__ import annotations

import pytest

from caissa.ocr.arbiter import Arbiter, RegionTask
from caissa.ocr.calibration import (
    CalibrationSet,
    CalibrationTable,
    FacetKey,
    facet_key,
    fit_isotonic,
    packaged_calibration,
    pairs_from_alignment,
)
from caissa.ocr.engines.base import EngineLevel
from caissa.ocr.routing import Router
from caissa.ocr.types import RegionKind

from .test_arbiter import CLEAN, MockEngine, identity_config, inked_region

# --------------------------------------------------------------------------- #
# Fitting
# --------------------------------------------------------------------------- #


def test_isotonic_fit_is_monotone_and_lowers_ece():
    # An engine that says 0.9 for words that are right only 60 % of the time,
    # and 0.5 for words that are right 20 % of the time.
    raw = [0.9] * 100 + [0.5] * 100
    correct = [True] * 60 + [False] * 40 + [True] * 20 + [False] * 80
    table = fit_isotonic(raw, correct)
    assert table is not None
    assert table.apply(0.9) == pytest.approx(0.6, abs=0.02)
    assert table.apply(0.5) == pytest.approx(0.2, abs=0.02)
    values = [table.apply(v / 20) for v in range(21)]
    assert values == sorted(values)
    assert table.ece_after < table.ece_before
    assert table.brier_after < table.brier_before


def test_too_few_samples_fit_nothing():
    assert fit_isotonic([0.9] * 10, [True] * 10) is None


def test_pairs_align_hypothesis_words_to_the_truth():
    pairs = pairs_from_alignment(
        [("The", 0.9), ("r0ok", 0.4), ("belongs", 0.95), ("extra", 0.3)],
        ["The", "rook", "belongs"])
    assert pairs == [(0.9, True), (0.4, False), (0.95, True), (0.3, False)]


# --------------------------------------------------------------------------- #
# Lookup
# --------------------------------------------------------------------------- #


def test_facet_keys_go_from_specific_to_engine():
    key = facet_key("tesseract", lang="por+eng", script="latin", dpi=150, kind="movetext")
    assert key.candidates() == [
        "tesseract|lang=por|script=latin|dpi=low|kind=movetext",
        "tesseract|lang=por|script=latin|dpi=low",
        "tesseract|lang=por|script=latin",
        "tesseract|lang=por",
        "tesseract",
    ]
    assert FacetKey("t", dpi=300).dpi_bucket == "300"
    assert FacetKey("t", dpi=400).dpi_bucket == "high"


def test_lookup_falls_back_and_roundtrips_json(tmp_path):
    fitted = CalibrationSet(tables={
        "t": CalibrationTable(knots=((0.0, 0.1), (1.0, 0.9)), samples=50),
        "t|lang=rus": CalibrationTable(knots=((0.0, 0.0), (1.0, 0.5)), samples=50),
    }, corpus_hash="abc")
    found = fitted.lookup(facet_key("t", lang="rus", script="cyrillic"))
    assert found is not None and found[0] == "t|lang=rus"
    found = fitted.lookup(facet_key("t", lang="deu"))
    assert found is not None and found[0] == "t"
    assert fitted.lookup(facet_key("x")) is None
    path = tmp_path / "cal.json"
    fitted.save(path)
    from caissa.ocr.calibration import load_calibration_set

    again = load_calibration_set(path)
    assert again.corpus_hash == "abc"
    assert again.tables["t|lang=rus"].apply(1.0) == pytest.approx(0.5)


def test_the_packaged_set_was_fitted_on_the_calibration_partition():
    fitted = packaged_calibration()
    assert fitted.partition == "calib"
    assert "tesseract" in fitted.tables
    table = fitted.tables["tesseract"]
    assert table.samples >= 1000
    assert table.ece_after <= table.ece_before


def test_the_arbiter_calibrates_per_word_with_a_fitted_table():
    fitted = CalibrationSet(tables={
        "l1": CalibrationTable(knots=((0.0, 0.0), (0.5, 0.1), (1.0, 0.95)), samples=100)})
    config = identity_config(calibration_set=fitted)
    config.calibrations = {}
    engine = MockEngine("l1", EngineLevel.TESSERACT, CLEAN, 0.5)
    outcome = Arbiter([engine], config).run(
        RegionTask(image=inked_region(), lang="eng", region_kind=RegionKind.PARAGRAPH))
    score = outcome.scores[0]
    assert score.calibration_key == "l1"
    assert not score.provisional
    assert score.confidence == pytest.approx(0.1, abs=0.01)
    assert score.raw_confidence == pytest.approx(0.5, abs=0.01)


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #


def _engines():
    return [
        MockEngine("tesseract", EngineLevel.TESSERACT, CLEAN, 0.9),
        MockEngine("paddleocr", EngineLevel.PADDLE, CLEAN, 0.9),
        MockEngine("paddle_structure", EngineLevel.PADDLE, CLEAN, 0.9),
        MockEngine("surya", EngineLevel.SURYA, CLEAN, 0.9),
        MockEngine("pdf_text_layer", EngineLevel.PDF_TEXT_LAYER, CLEAN, 0.9,
                   requires_pdf_page=True),
    ]


def test_routes_by_language_script_and_kind():
    router = Router()
    names = lambda task: [e.name for e in router.order(_engines(), task)]  # noqa: E731
    assert names(RegionTask(lang="por")) == [
        "pdf_text_layer", "tesseract", "paddle_structure", "paddleocr", "surya"]
    assert names(RegionTask(lang="rus")) == [
        "pdf_text_layer", "surya", "paddleocr", "tesseract", "paddle_structure"]
    assert names(RegionTask(lang="eng", region_kind=RegionKind.TABLE))[:3] == [
        "pdf_text_layer", "paddle_structure", "paddleocr"]
    assert router.route_for(RegionTask(lang="eng", region_kind=RegionKind.MOVETEXT)).name == (
        "movetext")


def test_routing_never_drops_an_engine_and_is_deterministic():
    router = Router()
    engines = _engines()
    once = [e.name for e in router.order(engines, RegionTask(lang="rus"))]
    twice = [e.name for e in router.order(list(reversed(engines)), RegionTask(lang="rus"))]
    assert once == twice
    assert sorted(once) == sorted(e.name for e in engines)


def test_the_cascade_reaches_a_multilingual_engine_for_cyrillic():
    """Sol §SOL-4: the budget no longer counts an empty level 0, and the
    router puts the multilingual engine first for Cyrillic, so Surya runs."""
    langs = {"rus", "eng"}
    tess = MockEngine("tesseract", EngineLevel.TESSERACT, "xq zz kk qq", 0.3, languages=langs)
    surya = MockEngine("surya", EngineLevel.SURYA, CLEAN, 0.95, languages=langs)
    empty0 = MockEngine("pdf_text_layer", EngineLevel.PDF_TEXT_LAYER, "", 0.0,
                        requires_pdf_page=True, languages=langs)
    task = RegionTask(image=inked_region(), lang="rus", pdf_page=object(),
                      region_kind=RegionKind.PARAGRAPH)
    config = identity_config(max_engines=2)
    config.calibrations = {**config.calibrations, "tesseract": config.calibrations["l1"],
                           "surya": config.calibrations["l1"]}
    outcome = Arbiter([tess, surya, empty0], config).run(task)
    assert outcome.engines_run[0] == "pdf_text_layer"
    assert "surya" in outcome.engines_run
    assert outcome.result.engine == "surya"
