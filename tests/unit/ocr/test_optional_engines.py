"""Sol §SOL-5: optional engines are isolated, versioned and fail explicitly.

None of PaddleOCR, PP-StructureV3 or Surya is installed on the reference
machine, so the contracts are exercised with *fake* modules that reproduce
the documented output shapes of the supported versions.  The point of each
test is the contract, not the engine: a schema the adapter does not know
raises, an unsupported version is refused with the range in the message,
and the worker protocol survives a round trip.
"""

from __future__ import annotations

import io
import json
import sys
import types

import numpy as np
import pytest

from caissa.ocr.engines.contracts import (
    SUPPORTED,
    SchemaError,
    check_version,
    parse_version,
)
from caissa.ocr.engines.paddle import PaddleOcrEngine
from caissa.ocr.engines.paddle_structure import LABEL_TO_KIND, PaddleStructureEngine
from caissa.ocr.engines.surya import SuryaEngine
from caissa.ocr.engines.weights import WeightArtifact, load_ledger, verify_weights
from caissa.ocr.engines.worker import (
    WORKER_SCHEMA,
    IsolatedEngine,
    result_from_json,
    result_to_json,
    serve,
)
from caissa.ocr.types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind

# --------------------------------------------------------------------------- #
# Version contracts
# --------------------------------------------------------------------------- #


def test_version_ranges_are_data_and_refuse_outside_them(monkeypatch):
    assert parse_version("3.1.0rc1") == (3, 1, 0)
    assert SUPPORTED["paddleocr"].contains((2, 7, 3))
    assert not SUPPORTED["paddleocr"].contains((4, 0))
    monkeypatch.setattr("caissa.ocr.engines.contracts.installed_version", lambda d: "5.0.0")
    ok, version, reason = check_version("paddleocr", engine="paddleocr")
    assert not ok and version == "5.0.0"
    assert ">=2.7,<4.0" in reason
    monkeypatch.setattr("caissa.ocr.engines.contracts.installed_version", lambda d: None)
    assert check_version("paddleocr", engine="paddleocr") == (True, None, None)


# --------------------------------------------------------------------------- #
# PaddleOCR shapes
# --------------------------------------------------------------------------- #


def test_paddle_parses_2x_and_3x_shapes_and_refuses_the_rest():
    v2 = [[[[[0, 0], [100, 0], [100, 20], [0, 20]], ("Nf3 Nc6", 0.93)]]]
    lines = PaddleOcrEngine._to_lines(v2, RegionKind.PARAGRAPH)
    assert [ln.text for ln in lines] == ["Nf3 Nc6"]
    v3 = [{"rec_texts": ["the rook", "belongs"], "rec_scores": [0.9, 0.8],
           "rec_polys": [[[0, 0], [80, 0], [80, 20], [0, 20]], [[0, 30], [70, 30], [70, 50], [0, 50]]]}]
    lines = PaddleOcrEngine._to_lines(v3, RegionKind.PARAGRAPH)
    assert [ln.text for ln in lines] == ["the rook", "belongs"]
    assert lines[1].box.y0 == 30.0
    with pytest.raises(SchemaError) as excinfo:
        PaddleOcrEngine._to_lines([{"rec_texts": ["x"], "rec_scores": [0.5]}], RegionKind.PAGE)
    assert "esquema" in str(excinfo.value)
    with pytest.raises(SchemaError):
        PaddleOcrEngine._to_lines([["not", "a", "known", "shape"]], RegionKind.PAGE)
    assert PaddleOcrEngine._to_lines([], RegionKind.PAGE) == []


# --------------------------------------------------------------------------- #
# PP-StructureV3
# --------------------------------------------------------------------------- #


def _structure_payload():
    return [{
        "layout_det_res": {"boxes": [
            {"label": "paragraph_title", "coordinate": [10, 10, 300, 40], "score": 0.98},
            {"label": "text", "coordinate": [10, 50, 300, 200], "score": 0.97},
            {"label": "table", "coordinate": [10, 210, 300, 400], "score": 0.9},
        ]},
        "overall_ocr_res": {
            "rec_texts": ["Chapter One", "The rook belongs", "behind the pawn", "a1 | b2"],
            "rec_scores": [0.95, 0.9, 0.9, 0.7],
            "rec_polys": [
                [[12, 12], [200, 12], [200, 36], [12, 36]],
                [[12, 60], [280, 60], [280, 80], [12, 80]],
                [[12, 90], [280, 90], [280, 110], [12, 110]],
                [[12, 220], [280, 220], [280, 240], [12, 240]],
            ],
        },
        "parsing_res_list": [
            {"block_label": "paragraph_title", "block_bbox": [10, 10, 300, 40],
             "block_content": "Chapter One"},
            {"block_label": "text", "block_bbox": [10, 50, 300, 200],
             "block_content": "The rook belongs behind the pawn"},
            {"block_label": "table", "block_bbox": [10, 210, 300, 400], "block_content": ""},
        ],
    }]


def test_structure_returns_regions_in_reading_order_and_assigns_lines():
    blocks, lines = PaddleStructureEngine.parse(_structure_payload(), RegionKind.PAGE)
    assert [b.kind for b in blocks] == [RegionKind.HEADING, RegionKind.PARAGRAPH, RegionKind.TABLE]
    assert [b.order for b in blocks] == [0, 1, 2]
    assert [(ln.block_index, ln.kind) for ln in lines] == [
        (0, RegionKind.HEADING), (1, RegionKind.PARAGRAPH), (1, RegionKind.PARAGRAPH),
        (2, RegionKind.TABLE)]
    assert LABEL_TO_KIND["number"] is RegionKind.PAGE_NUMBER


def test_structure_falls_back_to_layout_boxes_and_refuses_unknown_shapes():
    payload = _structure_payload()
    del payload[0]["parsing_res_list"]
    blocks, lines = PaddleStructureEngine.parse(payload, RegionKind.PAGE)
    assert len(blocks) == 3 and len(lines) == 4
    with pytest.raises(SchemaError):
        PaddleStructureEngine.parse([{"something": "else"}], RegionKind.PAGE)
    with pytest.raises(SchemaError):
        PaddleStructureEngine.parse([{"overall_ocr_res": {"rec_texts": ["x"]}}], RegionKind.PAGE)


def test_structure_engine_runs_against_a_fake_paddleocr(monkeypatch):
    fake = types.ModuleType("paddleocr")

    class PPStructureV3:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def predict(self, image):
            return iter(_structure_payload())

    fake.PPStructureV3 = PPStructureV3
    fake.__version__ = "3.1.0"
    monkeypatch.setitem(sys.modules, "paddleocr", fake)
    monkeypatch.setattr("caissa.ocr.engines.contracts.installed_version", lambda d: "3.1.0")
    engine = PaddleStructureEngine()
    assert engine.available(), engine.unavailable_reason()
    result = engine.recognize(np.full((420, 320), 255, dtype=np.uint8), lang="eng",
                              psm_hint=RegionKind.PAGE)
    assert "Chapter One" in result.text
    assert [b["label"] for b in result.meta["layout_blocks"]] == [
        "paragraph_title", "text", "table"]
    assert engine.last_blocks[2].kind is RegionKind.TABLE


# --------------------------------------------------------------------------- #
# Surya shapes
# --------------------------------------------------------------------------- #


class _Line:
    def __init__(self, text, bbox, confidence, chars=None):
        self.text, self.bbox, self.confidence, self.chars = text, bbox, confidence, chars


class _Char:
    def __init__(self, text, bbox, confidence):
        self.text, self.bbox, self.confidence = text, bbox, confidence


class _Page:
    def __init__(self, lines):
        self.text_lines = lines


def test_surya_uses_per_character_boxes_when_the_version_has_them():
    chars = [_Char("N", [0, 0, 10, 20], 0.9), _Char("f", [10, 0, 20, 20], 0.8),
             _Char("3", [20, 0, 30, 20], 0.95), _Char(" ", [30, 0, 34, 20], 1.0),
             _Char("a", [34, 0, 44, 20], 0.7), _Char("6", [44, 0, 54, 20], 0.7)]
    page = _Page([_Line("Nf3 a6", [0, 0, 54, 20], 0.85, chars)])
    lines = SuryaEngine._to_lines([page], RegionKind.MOVETEXT)
    words = lines[0].words
    assert [w.text for w in words] == ["Nf3", "a6"]
    assert words[0].box == BBox(0.0, 0.0, 30.0, 20.0)
    assert not words[0].chars[0].inherited_confidence
    old = _Page([_Line("Nf3 a6", [0, 0, 54, 20], 0.85)])
    lines = SuryaEngine._to_lines([old], RegionKind.MOVETEXT)
    assert lines[0].words[0].chars[0].inherited_confidence
    with pytest.raises(SchemaError):
        SuryaEngine._to_lines([object()], RegionKind.PAGE)


# --------------------------------------------------------------------------- #
# The isolated worker
# --------------------------------------------------------------------------- #


def test_result_round_trips_through_json():
    word = OcrWord(text="Nf3", box=BBox(1, 2, 30, 20), confidence=0.9,
                   chars=(OcrChar("N", BBox(1, 2, 10, 20), 0.9, False),))
    result = OcrResult(engine="x", lang="eng",
                       lines=(OcrLine(words=(word,), box=BBox(1, 2, 30, 20), baseline=(0.0, -2.0),
                                      kind=RegionKind.MOVETEXT, font_size=12.0),),
                       region_kind=RegionKind.PAGE, meta={"k": (1, 2)})
    again = result_from_json(json.loads(json.dumps(result_to_json(result))))
    assert again.text == "Nf3"
    assert again.lines[0].baseline == (0.0, -2.0)
    assert again.lines[0].kind is RegionKind.MOVETEXT
    assert again.words[0].chars[0].box == BBox(1, 2, 10, 20)
    assert again.meta["k"] == [1, 2]


def test_the_worker_protocol_answers_probe_and_refuses_unknown_engines():
    out = io.StringIO()
    code = serve("no-such-engine", stdin=io.StringIO(""), stdout=out)
    assert code == 2 and "desconhecido" in out.getvalue()
    out = io.StringIO()
    serve("paddleocr", stdin=io.StringIO('{"op": "probe"}\n{"op": "quit"}\n'), stdout=out)
    probe = json.loads(out.getvalue().splitlines()[0])
    assert probe["schema"] == WORKER_SCHEMA
    assert probe["engine"] == "paddleocr"
    assert probe["ok"] is False and probe["reason"]


@pytest.mark.slow
def test_an_isolated_engine_reports_unavailability_through_the_child():
    engine = IsolatedEngine(hosted="surya")
    try:
        assert not engine.available()
        assert "Surya" in (engine.unavailable_reason() or "")
    finally:
        engine.close()


def test_a_schema_mismatch_between_worker_and_parent_is_explicit(monkeypatch):
    engine = IsolatedEngine(hosted="paddleocr")
    monkeypatch.setattr(engine, "_call", lambda request, timeout: {"ok": True, "schema": 99})
    monkeypatch.setattr(engine, "close", lambda: None)
    ok, reason = engine._probe()
    assert not ok and "esquema 99" in reason


# --------------------------------------------------------------------------- #
# Weights ledger
# --------------------------------------------------------------------------- #


def test_the_weights_ledger_names_licences_and_flags_commercial_checks(tmp_path):
    ledger = load_ledger()
    assert {a.engine for a in ledger.artifacts} >= {"paddleocr", "paddle_structure", "surya"}
    assert any(a.engine == "surya" for a in ledger.needs_licence_check())
    assert all(a.license for a in ledger.artifacts)
    artifact = WeightArtifact("x", "w", "src", "MIT", "ok")
    assert verify_weights(artifact, tmp_path / "none")[0] == "missing"
    blob = tmp_path / "w.bin"
    blob.write_bytes(b"weights")
    assert verify_weights(artifact, blob)[0] == "unknown"
    from caissa.ocr.engines.weights import record_weights

    recorded = record_weights(artifact, blob)
    assert verify_weights(recorded, blob)[0] == "verified"
    blob.write_bytes(b"tampered")
    assert verify_weights(recorded, blob)[0] == "mismatch"
