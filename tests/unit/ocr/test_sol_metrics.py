"""Sol §SOL-0: the exact metrics, the golden manifest and the release gates.

Every metric is pinned with a case small enough to compute by hand, because
a benchmark whose numbers nobody can verify is the same as no benchmark.
"""

from __future__ import annotations

import json

import pytest

from caissa.ocr.gates import GateThresholds, evaluate_gates, summarise_rows
from caissa.ocr.golden import (
    DEGRADATIONS,
    ControlKind,
    GoldenItem,
    GoldenManifest,
    GoldenRegion,
    Partition,
    Source,
    annotate_moves,
    load_manifest,
    partition_for,
    save_manifest,
)
from caissa.ocr.metrics import (
    brier_score,
    expected_calibration_error,
    line_exact_accuracy,
    move_accounting,
    move_tokens,
    normalise,
    reading_order_accuracy,
    region_order_from_text,
    region_prf,
    reliability,
    risk_coverage,
    score_text,
)

# --------------------------------------------------------------------------- #
# Normalisation and moves
# --------------------------------------------------------------------------- #


def test_normalisation_folds_typography_but_not_letters():
    assert normalise("Kasparov – Karpov,  “Moscow”­") == 'Kasparov - Karpov, "Moscow"-'
    assert normalise("0-0-0 and 0-0") == "O-O-O and O-O"
    assert normalise("ﬁne") == "fine"          # NFKC unfolds the ligature
    assert normalise("Ébano") == "Ébano"       # accents survive


def test_move_tokens_cover_the_corpus_notations():
    assert move_tokens("1.e4 e5 2.Nf3 Nc6 3.Bb5") == ["e4", "e5", "Nf3", "Nc6", "Bb5"]
    assert move_tokens("1.e4 c5 2.Cf3 d6 3.d4 cxd4") == ["e4", "c5", "Cf3", "d6", "d4", "cxd4"]
    assert move_tokens("Sf3 Lb5 0-0 Te1 e8=D") == ["Sf3", "Lb5", "O-O", "Te1", "e8=D"]
    # Cyrillic homoglyphs fold to Latin: the same ink is the same move.
    assert move_tokens("1.e4 e5 2.Кf3 Кc6 3.Сb5") == ["e4", "e5", "Kf3", "Kc6", "Cb5"]
    assert move_tokens("the e4-square and rank 5") == []


def test_move_accounting_counts_an_altered_move_as_missing_and_invented():
    truth = "1.e4 e5 2.Nf3 Nc6"
    hyp = "1.e4 e5 2.Nf3 Nc5"
    acc = move_accounting(truth, hyp)
    assert (acc.truth, acc.kept, acc.missing, acc.invented) == (4, 3, 1, 1)
    assert acc.accuracy == pytest.approx(0.75)


def test_score_text_cer_and_abstention():
    score = score_text("abcd", "abcf")
    assert score.answered
    assert score.cer == pytest.approx(0.25)
    assert score_text("abcd", None).answered is False
    assert score_text("", "").cer == 0.0
    assert score_text("", "junk").cer == 1.0


def test_line_exact_accuracy_aligns_by_subsequence():
    truth = "one\ntwo\nthree"
    assert line_exact_accuracy(truth, "one\ninserted\ntwo\nthree") == pytest.approx(1.0)
    assert line_exact_accuracy(truth, "one\ntwoo\nthree") == pytest.approx(2 / 3)


# --------------------------------------------------------------------------- #
# Layout metrics
# --------------------------------------------------------------------------- #


def test_reading_order_accuracy_counts_lcs_over_truth():
    assert reading_order_accuracy(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert reading_order_accuracy(["a", "b", "c"], ["a", "c", "b"]) == pytest.approx(2 / 3)
    assert reading_order_accuracy(["a", "b", "c"], ["a", "b"]) == pytest.approx(2 / 3)
    assert reading_order_accuracy([], []) == 1.0


def test_region_order_from_text_locates_columns_fuzzily():
    left = "The rook belongs behind the passed pawn and waits"
    right = "A torre pertence atrás do peão passado e espera"
    hypothesis = right + "\n" + "The r0ok belongs behlnd the passed pawn and waits"
    assert region_order_from_text(hypothesis, [left, right]) == [1, 0]


def test_region_prf_greedy_iou():
    truth = [(0, 0, 10, 10), (20, 20, 30, 30)]
    hyp = [(1, 1, 10, 10), (50, 50, 60, 60)]
    p, r, f1 = region_prf(truth, hyp)
    assert (p, r) == (0.5, 0.5)
    assert f1 == pytest.approx(0.5)
    assert region_prf([], []) == (1.0, 1.0, 1.0)


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def test_reliability_ece_and_brier_by_hand():
    conf = [0.95, 0.95, 0.15, 0.55]
    ok = [True, False, False, True]
    bins = reliability(conf, ok, bins=10)
    top = bins[9]
    assert top.count == 2
    assert top.accuracy == 0.5
    assert top.mean_confidence == pytest.approx(0.95)
    # ECE = 2/4*|0.95-0.5| + 1/4*|0.15-0| + 1/4*|0.55-1|
    assert expected_calibration_error(conf, ok) == pytest.approx(
        0.5 * 0.45 + 0.25 * 0.15 + 0.25 * 0.45)
    assert brier_score(conf, ok) == pytest.approx(
        (0.05 ** 2 + 0.95 ** 2 + 0.15 ** 2 + 0.45 ** 2) / 4)


def test_risk_coverage_curve_is_monotone_in_coverage():
    conf = [0.9, 0.7, 0.4, 0.2]
    err = [0.0, 0.01, 0.1, 0.5]
    curve = risk_coverage(conf, err, steps=10)
    coverages = [p.coverage for p in curve]
    assert coverages == sorted(coverages, reverse=True)
    assert curve[0].coverage == 1.0
    assert curve[0].risk == pytest.approx(0.1525)
    assert curve[8].coverage == 0.25
    assert curve[8].risk == 0.0


# --------------------------------------------------------------------------- #
# Golden manifest
# --------------------------------------------------------------------------- #


def _item(item_id: str, **extra) -> GoldenItem:
    return GoldenItem(id=item_id, source=Source.SYNTH, synth_font="times.ttf",
                      regions=(annotate_moves(GoldenRegion(kind="paragraph",
                                                           truth="1.e4 e5 2.Nf3 Nc6")),),
                      strata=("scan_clean_300",), **extra)


def test_partition_is_fixed_by_hash_and_the_blind_set_is_withheld(tmp_path):
    ids = [f"item:{n}" for n in range(300)]
    parts = [partition_for(i) for i in ids]
    assert partition_for("item:7") == partition_for("item:7")
    shares = {p: parts.count(p) / len(parts) for p in Partition}
    assert 0.35 < shares[Partition.DEV] < 0.65
    assert 0.12 < shares[Partition.BLIND] < 0.40
    manifest = GoldenManifest(items=[_item(i) for i in ids[:40]])
    path = tmp_path / "manifest.json"
    save_manifest(manifest, path)
    visible = load_manifest(path)
    assert all(i.partition is not Partition.BLIND for i in visible)
    everything = load_manifest(path, include_blind=True)
    assert len(everything) == 40
    assert len(visible) < 40


def test_a_hand_edited_partition_is_refused(tmp_path):
    path = tmp_path / "manifest.json"
    save_manifest(GoldenManifest(items=[_item("x:1")]), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"][0]["partition"] = "dev" if data["items"][0]["partition"] != "dev" else "blind"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="partição"):
        load_manifest(path, include_blind=True)


def test_manifest_validation_catches_the_obvious():
    bad = GoldenManifest(items=[
        _item("dup"), _item("dup"),
        GoldenItem(id="ctrl", source=Source.CONTROL, control=ControlKind.BLANK,
                   regions=(GoldenRegion(kind="paragraph", truth="text"),)),
        GoldenItem(id="pdf", source=Source.PDF_NATIVE, regions=(
            GoldenRegion(kind="paragraph", truth="x"),), strata=("nope",)),
    ])
    problems = "\n".join(bad.validate())
    assert "duplicado" in problems
    assert "controle negativo com texto" in problems
    assert "sem livro" in problems
    assert "estratos desconhecidos" in problems


def test_moves_are_annotated_from_truth_unless_verified():
    region = annotate_moves(GoldenRegion(kind="movetext", truth="1.e4 e5 2.Nf3"))
    assert region.moves == ("e4", "e5", "Nf3")
    assert not region.moves_verified
    verified = GoldenRegion(kind="movetext", truth="1.e4 e5", moves=("e4",), moves_verified=True)
    assert annotate_moves(verified).moves == ("e4",)


def test_every_declared_stratum_has_a_degradation():
    assert set(DEGRADATIONS) >= {"native", "scan_clean_300", "scan_degraded_150",
                                 "shadow_curl_bleed", "fax_dither", "photo"}
    assert DEGRADATIONS["scan_degraded_150"].dpi == 150


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #


def _row(stratum: str, cer: float, *, moves=(10, 10, 0, 0), decision="accepted",
         below=False, control=False, answered=True, order=None, conf=0.9):
    truth, kept, missing, invented = moves
    row = {
        "stratum": stratum, "answered": answered, "control": control, "cer": cer,
        "wer": cer * 2, "line_exact": 1 - cer, "moves_truth": truth, "moves_kept": kept,
        "moves_missing": missing, "moves_invented": invented, "length_ratio": 1.0,
        "decision": decision, "below_threshold": below, "confidence": conf,
        "duration_s": 0.5, "megapixels": 1.0, "hypothesis_chars": 100,
    }
    if order is not None:
        row["reading_order"] = order
    return row


def test_summary_reads_the_rows_it_is_given():
    rows = [_row("native", 0.0), _row("native", 0.02, decision="review"),
            _row("native", 0.0, answered=False, decision="abstained"),
            _row("native", 0.0, control=True, answered=False)]
    s = summarise_rows(rows)
    assert s["n"] == 3
    assert s["answered"] == 2
    assert s["abstained"] == 1
    assert s["review"] == 1
    assert s["cer_mean"] == pytest.approx(0.01)
    assert s["controls"] == 1
    assert s["control_false_positives"] == 0
    assert s["move_accuracy"] == 1.0
    # B11 (ciclo 2): the abstention is not CER 0 -- over the three measured items it costs
    # the whole page, and the mean says so; the withheld text is reported when it exists.
    assert s["cer_all_mean"] == pytest.approx((0.0 + 0.02 + 1.0) / 3)
    assert s["cer_withheld_mean"] is None
    assert s["withheld_with_text"] == 0
    rows[2]["cer_withheld"] = 0.3
    again = summarise_rows(rows)
    assert again["cer_withheld_mean"] == pytest.approx(0.3)
    assert again["withheld_with_text"] == 1


def test_gates_block_on_each_target_and_on_a_control_false_positive():
    rows = [
        _row("native", 0.001), _row("scan_clean_300", 0.002),
        _row("scan_degraded_150", 0.01),
        _row("native", 0.0, control=True, answered=True),
    ]
    report = evaluate_gates(rows)
    names = {r.name: r for r in report.results}
    assert names["CER limpo"].passed
    assert names["CER 150 DPI"].passed
    assert not names["controles negativos"].passed
    assert not report.passed

    rows = [_row("native", 0.001, moves=(100, 99, 1, 1)), _row("scan_degraded_150", 0.03)]
    report = evaluate_gates(rows)
    names = {r.name: r for r in report.results}
    assert not names["lances inventados"].passed
    assert not names["acurácia de lances"].passed
    assert not names["CER 150 DPI"].passed

    rows = [_row("native", 0.001, below=True, decision="accepted"),
            _row("scan_degraded_150", 0.001)]
    names = {r.name: r for r in evaluate_gates(rows).results}
    assert not names["importação silenciosa abaixo do limiar"].passed


def test_regression_gate_needs_a_change_outside_the_interval():
    base = [_row("native", 0.001 + 0.0001 * k) for k in range(30)]
    same = [_row("native", 0.0012 + 0.0001 * k) for k in range(30)]
    worse = [_row("native", 0.02 + 0.0001 * k) for k in range(30)]
    ok = {r.name: r for r in evaluate_gates(same, base).results}
    assert ok["regressão de CER [native]"].passed
    bad = {r.name: r for r in evaluate_gates(worse, base).results}
    assert not bad["regressão de CER [native]"].passed
    thresholds = GateThresholds(cer_regression_tolerance=0.05)
    lenient = {r.name: r for r in evaluate_gates(worse, base, thresholds=thresholds).results}
    assert lenient["regressão de CER [native]"].passed


def test_reading_order_gate_uses_the_multi_region_rows():
    rows = [_row("scan_clean_300", 0.0, order=1.0), _row("scan_clean_300", 0.0, order=0.5)]
    names = {r.name: r for r in evaluate_gates(rows).results}
    assert not names["ordem de leitura em duas colunas"].passed
    assert names["ordem de leitura em duas colunas"].observed == pytest.approx(0.75)
