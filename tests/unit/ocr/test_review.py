"""Sol §SOL-11: the review queue shows only doubt, records every decision,
measures the time, and never leaks a blind page into training data."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from caissa.ocr.golden import Partition, partition_for
from caissa.ocr.review import Action, ReviewQueue, blind_guard


def _report():
    items = [
        SimpleNamespace(page_index=3, rect=(10.0, 20.0, 200.0, 60.0), kind="paragraph",
                        decision="review", reasons=("Escore 0.70 abaixo do limite",),
                        text="the r0ok belongs", engine="tesseract", score=0.70,
                        alternatives=(("upscale/tesseract", "the rook belongs"),)),
        SimpleNamespace(page_index=3, rect=(10.0, 300.0, 200.0, 340.0), kind="movetext",
                        decision="abstained", reasons=("Nenhum texto",), text="",
                        engine="tesseract", score=0.1, alternatives=()),
        SimpleNamespace(page_index=7, rect=(10.0, 20.0, 200.0, 60.0), kind="movetext",
                        decision="review", reasons=("1 lance(s) sem leitura legal: Nz6",),
                        text="1.e4 e5 2.Nf3 Nz6", engine="tesseract", score=0.82,
                        alternatives=()),
    ]
    traces = {3: {"dpi": 300.0, "regions": [{
        "box_px": [41.7, 83.3, 833.3, 250.0],
        "decision": {"flagged_words": ["r0ok"]},
        "fusion": {"changed_tokens": [{"text": "r0ok", "alternative": "rook", "disputed": True}]},
        "legality": {},
    }]}, 7: {"dpi": 300.0, "regions": [{
        "box_px": [41.7, 83.3, 833.3, 250.0], "decision": {"flagged_words": []},
        "fusion": {}, "legality": {"unresolved": 1, "replayed_to_end": False},
    }]}}
    return SimpleNamespace(review_items=items, ocr_traces=traces)


def test_the_queue_holds_only_doubt_ordered_by_risk_with_context():
    queue = ReviewQueue.from_import(_report(), document="livro", reviewer="ana")
    assert [i.decision for i in queue.items] == ["abstained", "review", "review"]
    doubtful = next(i for i in queue.items if i.text == "the r0ok belongs")
    assert doubtful.low_confidence_words == ("r0ok",)
    assert doubtful.disputed_tokens == (("r0ok", "rook"),)
    assert doubtful.alternatives == (("upscale/tesseract", "the rook belongs"),)
    legality = next(i for i in queue.items if i.page_index == 7)
    assert legality.legality["unresolved"] == 1
    assert legality.risk > doubtful.risk


def test_decisions_are_audited_and_timed():
    queue = ReviewQueue.from_import(_report(), document="livro", reviewer="ana",
                                    render=lambda d, p, r: b"PNG")
    key = next(i for i in queue.items if i.text == "the r0ok belongs").key
    assert queue.crop(key) == b"PNG"
    queue.open(key)
    entry = queue.decide(key, Action.EDIT, text="the rook belongs", note="0 lido como o")
    assert entry.reviewer == "ana" and entry.seconds >= 0.0
    assert entry.text == "the rook belongs"
    with pytest.raises(ValueError):
        queue.decide(queue.items[0].key, Action.EDIT)
    queue.decide(queue.items[0].key, Action.KEEP_IMAGE)
    assert len(queue.pending()) == 1
    assert ("livro", 3) in queue.seconds_per_page()
    corrections = queue.corrections()
    assert corrections == [{
        "document": "livro", "page_index": 3, "rect": [10.0, 20.0, 200.0, 60.0],
        "kind": "paragraph", "engine": "tesseract", "hypothesis": "the r0ok belongs",
        "truth": "the rook belongs", "action": "edit", "reviewer": "ana", "at": entry.at,
    }]


def test_a_suggestion_is_shown_and_never_applied():
    queue = ReviewQueue.from_import(_report(), document="livro")
    key = next(i for i in queue.items if i.text == "the r0ok belongs").key
    queue.suggest(key, "the rook belongs behind the pawn")
    item = queue.open(key)
    assert item.suggestion == "the rook belongs behind the pawn"
    assert item.text == "the r0ok belongs"
    entry = queue.decide(key, Action.ACCEPT)
    assert entry.text == "the r0ok belongs"     # accept means the OCR's reading, not the model's


def test_blind_pages_never_reach_the_corrections(tmp_path):
    ids = [f"real:livro:{n}:100" for n in range(200)]
    blind_pages = [int(i.split(":")[2]) for i in ids if partition_for(i) is Partition.BLIND]
    assert blind_pages
    guard = blind_guard(ids)
    assert guard("livro", blind_pages[0])
    report = _report()
    clear = [p for p in range(200) if p not in blind_pages]
    report.review_items[0].page_index = blind_pages[0]
    report.review_items[1].page_index = clear[0]
    report.review_items[2].page_index = clear[1]
    queue = ReviewQueue.from_import(report, document="livro", blind=guard)
    for item in queue.items:
        queue.decide(item.key, Action.ACCEPT)
    exported = queue.corrections()
    assert all(not guard(c["document"], c["page_index"]) for c in exported)
    assert queue.withheld() == 1
    queue.save(tmp_path / "review.json")
    saved = json.loads((tmp_path / "review.json").read_text("utf-8"))
    assert len(saved["log"]) == 3 and saved["items"]
