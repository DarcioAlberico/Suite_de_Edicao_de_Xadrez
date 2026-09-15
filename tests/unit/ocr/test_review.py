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


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP passo 14: the decisions outlive the window and reach the import
# --------------------------------------------------------------------------- #


def _recognition(page_index: int = 3, dpi: float = 300.0):
    """A service result with two regions: one for review, one accepted."""
    from caissa.ingest.pdf.ocr_service import PageRecognition, RegionRecognition
    from caissa.ocr.decision import Decision, RegionDecision
    from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

    def region(order, y_px, text, decision):
        box = BBox(41.7, y_px, 791.6, 166.7)
        words = tuple(OcrWord(text=w, box=box, confidence=0.7) for w in text.split())
        result = OcrResult(engine="tesseract", lang="eng", lines=(
            OcrLine(words=words, box=box, kind=RegionKind.PARAGRAPH),))
        return RegionRecognition(reading_order=order, kind=RegionKind.PARAGRAPH, box_px=box,
                                 result=result, decision=RegionDecision(decision, 0.7, 0.78, 0.55,
                                                                        ("Escore baixo",)),
                                 engine="tesseract", variant="base", score=0.7)

    return PageRecognition(page_index=page_index, dpi=dpi, regions=[
        region(0, 83.3, "the r0ok belongs", Decision.REVIEW),
        region(1, 1250.0, "a clean line", Decision.ACCEPTED),
    ], portfolio=None, notes=[], duration_s=0.1, whole_page=False, engines={})


class _Frame:
    index = 3

    @staticmethod
    def pixels_to_page(rect, dpi):
        s = dpi / 72.0
        return tuple(v / s for v in rect)


def test_decisions_reduce_the_log_and_apply_to_the_regions_on_import(tmp_path):
    from caissa.ocr.decision import Decision
    from caissa.ocr.review import ReviewDecisions

    queue = ReviewQueue.from_import(_report(), document="livro", reviewer="ana")
    key = next(i for i in queue.items if i.text == "the r0ok belongs").key
    queue.decide(key, Action.SKIP)
    queue.decide(key, Action.EDIT, text="the rook belongs")
    queue.decide(queue.items[0].key, Action.KEEP_IMAGE)
    decisions = queue.decisions()
    assert len(decisions) == 2, "the skip is not a decision; the edit is the last word on its item"
    path = decisions.save(tmp_path / "revisao" / "livro.json")
    loaded = ReviewDecisions.load(path)
    assert loaded.entries == decisions.entries

    recognition = _recognition()
    assert loaded.apply(recognition, _Frame()) == 1
    edited, clean = recognition.regions
    assert edited.decision.decision is Decision.ACCEPTED
    assert edited.verified and edited.result.text == "the rook belongs"
    assert edited.result.lines[0].confidence == 1.0
    assert "aceita pelo revisor" in edited.decision.reasons_pt
    assert not clean.verified, "an accepted region is not the reviewer's"
    assert not recognition.review_regions

    # The same decisions, another page: nothing matches, nothing changes.
    other = _recognition(page_index=9)
    frame9 = type("F", (), {"index": 9, "pixels_to_page": staticmethod(_Frame.pixels_to_page)})()
    assert loaded.apply(other, frame9) == 0


def test_keep_image_abstains_the_region_and_accept_verifies_it():
    from caissa.ocr.decision import Decision
    from caissa.ocr.review import Decided, ReviewDecisions

    rect = (10.0, 20.0, 200.0, 60.0)   # the review region of _recognition, in points
    kept = ReviewDecisions(entries=(Decided(3, rect, Action.KEEP_IMAGE, reviewer="ana"),))
    recognition = _recognition()
    assert kept.apply(recognition, _Frame()) == 1
    assert recognition.regions[0].decision.decision is Decision.ABSTAINED
    assert recognition.regions[0] in recognition.abstained_regions
    accepted = ReviewDecisions(entries=(Decided(3, rect, Action.ACCEPT),))
    recognition = _recognition()
    assert accepted.apply(recognition, _Frame()) == 1
    assert recognition.regions[0].verified
    assert recognition.regions[0].result.text == "the r0ok belongs", "accept keeps the OCR's text"
    # A box that does not overlap the region is not the region.
    elsewhere = ReviewDecisions(entries=(Decided(3, (300.0, 300.0, 400.0, 320.0), Action.ACCEPT),))
    assert elsewhere.apply(_recognition(), _Frame()) == 0


def test_a_blind_page_refuses_accept_and_edit_with_the_phrase_but_not_the_image():
    ids = [f"real:livro:{n}:100" for n in range(200)]
    blind_pages = [int(i.split(":")[2]) for i in ids if partition_for(i) is Partition.BLIND]
    report = _report()
    report.review_items[0].page_index = blind_pages[0]
    queue = ReviewQueue.from_import(report, document="livro", blind=blind_guard(ids))
    key = next(i for i in queue.items if i.page_index == blind_pages[0]).key
    assert "partição cega" in queue.refusal(key, Action.EDIT)
    assert "partição cega" in queue.refusal(key, Action.ACCEPT)
    assert queue.refusal(key, Action.KEEP_IMAGE) == ""
    other = next(i for i in queue.items if i.page_index != blind_pages[0]).key
    assert queue.refusal(other, Action.EDIT) == ""
    # Sabotage: with the guard off, a correction on the blind page would leave
    # the queue as a decision — this is what the guard exists to stop.
    queue.decide(key, Action.EDIT, text="typed on a blind page")
    assert all(d.page_index != blind_pages[0] for d in queue.decisions().entries)
    unguarded = ReviewQueue.from_import(report, document="livro")
    unguarded.decide(key, Action.EDIT, text="typed on a blind page")
    assert any(d.page_index == blind_pages[0] for d in unguarded.decisions().entries)


def test_a_saved_queue_loads_with_its_log_and_clock(tmp_path):
    queue = ReviewQueue.from_import(_report(), document="livro", reviewer="ana")
    key = queue.items[1].key
    queue.open(key)
    queue.decide(key, Action.ACCEPT)
    queue.save(tmp_path / "fila.json")
    again = ReviewQueue.load(tmp_path / "fila.json")
    assert again.reviewer == "ana"
    assert [i.key for i in again.items] == [i.key for i in queue.items]
    assert [e.key for e in again.pending()] == [e.key for e in queue.pending()]
    assert again.seconds_per_page().keys() == queue.seconds_per_page().keys()
