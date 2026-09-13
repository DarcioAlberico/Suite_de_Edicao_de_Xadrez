"""The page loop — SPEC §7.1, docs/quality/F5_REPORT_C2.md §3.

The arbiter was tested with mock engines because its job is to *decide*.  This
module's job is different: it cuts a page up, hands each piece to the arbiter,
and puts the answers back together in one coordinate space.  So the tests here
use the **real** level-0 engine on **real** synthetic PDFs, and mock only the
level-1 engine — because the thing most likely to be wrong is not a decision,
it is the arithmetic that turns a crop-relative box back into a page box.

That arithmetic gets the sabotage.  ``test_a_region_result_lands_in_page_space``
pins the offset a level-1 engine's boxes must receive, and
``test_the_offset_is_not_zero_by_accident`` proves the test would fail if the
translation were dropped — because a test that passes against ``+0`` is
indistinguishable from a test that is not measuring the offset at all.
"""

from __future__ import annotations

import numpy as np
import pytest

from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.engines.pdf_text_layer import PdfTextLayerEngine
from caissa.ocr.page import (
    PageConfig,
    PageRecognizer,
    PageTask,
    recognize_page,
)
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

from .conftest import FONT_PATH, corpus_path, requires_pymupdf

pytestmark = requires_pymupdf


# --------------------------------------------------------------------------- #
# Page building
# --------------------------------------------------------------------------- #

PROSE = (
    "The rook belongs behind the passed pawn and the reason is not hard to "
    "see at all. When the rook stands in front of the pawn it must move away "
    "before the pawn can advance, so the attacking side loses time with every "
    "single step while the defender simply waits and keeps his own rook where "
    "it already stands. This is one of the most useful rules in the endgame "
    "and it repays the small effort of learning it properly."
)

#: Word-shaped, pronounceable-looking, and in no dictionary — the shape of a
#: broken CMap.  Level 0 must reject a region made of this.
GIBBERISH = (
    "xqzvbn mklpqr wxyzzq jjkvvn mmqpplx wqzbnm kklrrt yyuiio zzqwxy "
    "vbnxqz pqrmkl zzqwxy jjkvvn mmqpplx wqzbnm kklrrt yyuiio xqzvbn "
    "mklpqr wxyzzq jjkvvn mmqpplx wqzbnm kklrrt yyuiio zzqwxy vbnxqz"
)


def build_page(pymupdf, blocks, *, width=595.0, height=842.0):
    """A one-page PDF from ``[(y, size, text), ...]``, wrapped by hand.

    Hand-placed rather than flowed, because the tests below assert which
    *regions* come out and that depends on the vertical gaps.  A flowing
    helper would make the gaps an accident of the text length.
    """
    if FONT_PATH is None:
        pytest.skip("nenhuma fonte TrueType disponível para embutir")
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    page.insert_font(fontname="EMB", fontfile=FONT_PATH)
    for y, size, text in blocks:
        step = size * 1.4
        words, line, cursor = text.split(), [], y
        while words:
            line.append(words.pop(0))
            if len(" ".join(line)) > 64 or not words:
                page.insert_text((60, cursor), " ".join(line),
                                 fontname="EMB", fontsize=size)
                line, cursor = [], cursor + step
    reopened = pymupdf.open(stream=doc.tobytes(), filetype="pdf")
    doc.close()
    return reopened


@pytest.fixture
def mixed_doc(pymupdf):
    """Good prose, then a block of gibberish, far enough apart to be two
    regions.  This is the page the loop exists for: one region is worth
    trusting and the other is not."""
    return build_page(pymupdf, [
        (90.0, 11.0, PROSE),
        (500.0, 11.0, GIBBERISH),
        (760.0, 11.0, PROSE),
    ])


# --------------------------------------------------------------------------- #
# Mock level 1
# --------------------------------------------------------------------------- #

#: Where the mock puts its word *inside the crop it is given*.  Non-zero on
#: both axes so a translation that only fixes one shows up.
MOCK_WORD_BOX = BBox(7.0, 3.0, 40.0, 12.0)


class MockOcr:
    """A level-1 engine that reports one word at a fixed crop-relative box."""

    name = "mock_ocr"

    def __init__(self, text: str = "recovered text", confidence: float = 0.95):
        self.text = text
        self.confidence = confidence
        self.crops: list[tuple[int, int]] = []

    def available(self) -> bool:
        return True

    def unavailable_reason(self):
        return None

    def languages(self) -> set[str]:
        return {"eng", "por"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.TESSERACT, cost_per_megapixel_s=0.4,
            supports_char_boxes=False, supports_confidence=True,
            handles_layout=True, requires_pdf_page=False)

    def recognize(self, image, *, lang="eng",
                  psm_hint=RegionKind.PARAGRAPH) -> OcrResult:
        self.crops.append(tuple(image.shape[:2]))
        # One word per token, side by side from the fixed box, so the
        # decision layer sees a line rather than one floating word.
        words = []
        x = MOCK_WORD_BOX.x
        for token in self.text.split():
            box = BBox(x, MOCK_WORD_BOX.y, MOCK_WORD_BOX.w, MOCK_WORD_BOX.h)
            words.append(OcrWord(text=token, box=box, confidence=self.confidence))
            x += MOCK_WORD_BOX.w + 4.0
        line = OcrLine(words=tuple(words),
                       box=BBox.from_edges(MOCK_WORD_BOX.x0, MOCK_WORD_BOX.y0,
                                           x - 4.0, MOCK_WORD_BOX.y1),
                       kind=psm_hint)
        return OcrResult(engine=self.name, lang=lang, lines=(line,),
                         region_kind=psm_hint, duration_s=0.01)


def raster_for(page, dpi: float = 150.0) -> np.ndarray:
    pix = page.get_pixmap(dpi=int(dpi), colorspace="gray")
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height,
                                                              pix.width)


# --------------------------------------------------------------------------- #
# Cutting the page up
# --------------------------------------------------------------------------- #


def test_a_clean_page_is_read_region_by_region_at_level_zero(mixed_doc):
    """Nothing escalates on the prose, and every region gets its own text."""
    doc = build_page(mixed_doc.__class__ and __import__("pymupdf"), [
        (90.0, 11.0, PROSE), (500.0, 11.0, PROSE)])
    outcome = recognize_page([PdfTextLayerEngine()],
                             PageTask(pdf_page=doc[0], lang="eng"))
    assert not outcome.whole_page
    assert len(outcome.regions) >= 2
    assert outcome.engines_used == ("pdf_text_layer",)
    assert not outcome.escalated_regions
    assert "rook belongs behind" in outcome.text
    doc.close()


def test_only_the_bad_region_escalates(mixed_doc):
    """**The point of the whole module.**

    A page whose prose is fine and whose middle block is broken must send only
    the middle block to OCR.  Before this loop existed the choice was all or
    nothing, because the verdict was computed once for the whole page.
    """
    mock = MockOcr()
    outcome = recognize_page(
        [PdfTextLayerEngine(), mock],
        PageTask(pdf_page=mixed_doc[0], image=raster_for(mixed_doc[0]),
                 dpi=150.0, lang="eng"))

    assert not outcome.whole_page, outcome.explain_pt()
    escalated = outcome.escalated_regions
    assert len(escalated) == 1, outcome.explain_pt()
    assert escalated[0].engine == "mock_ocr"
    # ...and the escalated region is the gibberish one.
    assert "xqzvbn" not in outcome.text
    # ...while the prose regions stayed with the text layer.
    kept = [r for r in outcome.regions if r not in escalated]
    assert kept and all(r.engine == "pdf_text_layer" for r in kept)
    assert "rook belongs behind" in outcome.text


#: A hundred correct moves.  Enough to carry a page's average on its own.
GOOD_MOVES = " ".join(f"{n}. Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5"
                      for n in range(1, 11))

#: Fifteen moves whose figurine did not survive, in the shapes the corpus
#: actually produced.  Two thirds of them are unreadable.
BROKEN_MOVES = ("ll'lf3 'i'd2 @g2 ll'lc6 'i'h5 @f1 ll'le5 'i'xd4 @h2 ll'lg4 "
                "'i'e3 @g1 ll'lb3 'i'c7 @e2")


def test_a_diluted_page_hides_a_destroyed_block_and_the_region_does_not(pymupdf):
    """**What per-region arbitration is actually for — measured, not assumed.**

    The page as a whole reads 0.087 damaged moves, below the 0.15 bar, so the
    page verdict is *borderline* at 0.80.  The block at the bottom reads 0.667
    on its own, above the 0.60 bar, so its own verdict is an outright
    rejection, while the block at the top is a clean 0.98.

    Two things change, and neither is the choice of engine — with the region
    verdict switched off the damaged block still escalates, because its
    plausibility is 0.00 either way.  What changes is:

    * the **good** block is judged at 0.98 instead of being dragged to 0.80 by
      damage in a different part of the page.  A confidence is what the UI
      sends a proofreader to; borrowing another region's is how a clean block
      ends up in the review queue;
    * the **bad** block's level-0 result is empty and *rejected* rather than
      garbage text competing on score.  Sabotaged, no engine reaches its
      threshold at all and the winner is chosen by the "best of a bad lot"
      branch at 0.643 — a decision the trail cannot explain.

    Numbers taken from the run recorded in F5_REPORT_C2 §3.
    """
    doc = build_page(pymupdf, [(70.0, 10.0, GOOD_MOVES),
                               (700.0, 10.0, BROKEN_MOVES)])
    mock = MockOcr()
    outcome = recognize_page(
        [PdfTextLayerEngine(), mock],
        PageTask(pdf_page=doc[0], image=raster_for(doc[0]), dpi=150.0,
                 lang="eng"))

    assert not outcome.whole_page, outcome.explain_pt()
    assert all(r.own_verdict for r in outcome.regions), (
        "as regiões foram julgadas pelo veredito da página, não pelo próprio")

    good, bad = outcome.regions[0], outcome.regions[1]

    # The clean block keeps its own, undiluted confidence.
    assert good.engine == "pdf_text_layer"
    assert not good.escalated
    assert good.outcome.winner.confidence == pytest.approx(0.98)
    assert "Nf3" in good.result.text

    # The damaged block is rejected outright — level 0 offers nothing at all,
    # so the garbage never competes.
    assert bad.escalated and bad.engine == "mock_ocr"
    level_zero = [s for s in bad.outcome.scores if s.engine == "pdf_text_layer"]
    assert level_zero and level_zero[0].total == 0.0, (
        "o nível 0 devolveu texto para um bloco que ele mesmo reprovou")
    assert any(d.action == "accepted" for d in bad.outcome.decisions)
    assert bad.outcome.winner.total >= 0.78, (
        "o vencedor foi escolhido pelo ramo de 'melhor de um lote ruim'")
    assert "ll'lf3" not in outcome.text
    doc.close()


def test_a_short_region_inherits_the_page_verdict(pymupdf):
    """A heading is not a scan.

    Level 0 calls anything under 24 characters an image-only page, which is
    right for a page and catastrophic for a region: assessed independently,
    every heading and folio in the collection would be rejected and sent to
    OCR.  The runner hands those regions the page's verdict instead, and the
    test that proves it is that *nothing* escalates and the heading survives.
    """
    doc = build_page(pymupdf, [
        (80.0, 16.0, "Chapter Four"),
        (140.0, 11.0, PROSE),
        (700.0, 9.0, "41"),
    ])
    mock = MockOcr()
    outcome = recognize_page(
        [PdfTextLayerEngine(), mock],
        PageTask(pdf_page=doc[0], image=raster_for(doc[0]), dpi=150.0,
                 lang="eng"))

    assert not outcome.escalated_regions, outcome.explain_pt()
    assert mock.crops == [], "uma região curta foi para o OCR sem precisar"
    assert "Chapter Four" in outcome.text
    inherited = [r for r in outcome.regions if not r.own_verdict]
    assert inherited, "nenhuma região herdou o veredito: o piso não foi usado"
    doc.close()


# --------------------------------------------------------------------------- #
# Coordinate spaces — the part that fails silently
# --------------------------------------------------------------------------- #


def test_a_region_result_lands_in_page_space(mixed_doc):
    """A level-1 box is crop-relative; what comes out must be page-relative.

    This is the failure that no string comparison catches: the text is right,
    the boxes are off by the region origin, and everything downstream that
    points at a word — the proofreader, the notation corrector — points at the
    wrong pixels.
    """
    mock = MockOcr()
    task = PageTask(pdf_page=mixed_doc[0], image=raster_for(mixed_doc[0]),
                    dpi=150.0, lang="eng")
    outcome = recognize_page([PdfTextLayerEngine(), mock], task)

    escalated = outcome.escalated_regions
    assert len(escalated) == 1
    region = escalated[0]

    # The crop's origin in page pixels, derived independently of the runner.
    expected = region.region.box.scaled(task.scale)
    ox, oy, _, _ = expected.to_int_tuple()

    word = region.result.words[0]
    assert word.box.x == pytest.approx(MOCK_WORD_BOX.x + ox)
    assert word.box.y == pytest.approx(MOCK_WORD_BOX.y + oy)
    assert word.box.w == pytest.approx(MOCK_WORD_BOX.w)
    assert region.result.meta["page_origin"] == (float(ox), float(oy))


def test_the_offset_is_not_zero_by_accident(mixed_doc):
    """Vitality: the gate above must be able to fail.

    A region that begins at the page origin would make the translation a
    no-op, and the test above would pass against code that never translates
    anything.  So assert the offset is large — if the escalated region ever
    moves to the top-left corner, the sabotage stops working and this says so.
    """
    mock = MockOcr()
    task = PageTask(pdf_page=mixed_doc[0], image=raster_for(mixed_doc[0]),
                    dpi=150.0, lang="eng")
    outcome = recognize_page([PdfTextLayerEngine(), mock], task)
    region = outcome.escalated_regions[0]
    ox, oy, _, _ = region.region.box.scaled(task.scale).to_int_tuple()
    assert ox > 20 and oy > 200, (ox, oy)

    # And the box really moved: the raw mock box is not what came out.
    assert region.result.words[0].box != MOCK_WORD_BOX


def test_level_zero_boxes_survive_a_raster(pymupdf):
    """A level-0 region must read the same with and without a raster.

    **This test exists because the bug was real.**  ``_run_region`` translated
    whatever the arbiter returned by the crop's origin — correct for an engine
    that saw only the crop, and wrong for level 0, which is handed the clip and
    the scale and answers in page coordinates already.  With a raster attached,
    a paragraph at 600 pt came back at y=2458 px on a page 1754 px tall: off
    the page, at exactly twice its own offset.

    The reason it went unnoticed is worth keeping too.  The test below passes
    no raster, so the crop is ``None``, the origin is ``(0, 0)``, and the
    translation is a no-op — a gate that could not see the failure it was
    written for.  The fix is not a better assertion on that test; it is this
    one, which runs the same page **both ways** and requires the answer to
    match.
    """
    doc = build_page(pymupdf, [(600.0, 11.0, PROSE)])
    page = doc[0]
    try:
        without = recognize_page(
            [PdfTextLayerEngine()],
            PageTask(pdf_page=page, dpi=150.0, lang="eng"))
        with_raster = recognize_page(
            [PdfTextLayerEngine()],
            PageTask(pdf_page=page, image=raster_for(page), dpi=150.0,
                     lang="eng"))

        assert without.engines_used == with_raster.engines_used ==             ("pdf_text_layer",)
        boxes_a = [w.box for w in without.as_result().words]
        boxes_b = [w.box for w in with_raster.as_result().words]
        assert boxes_a and len(boxes_a) == len(boxes_b)
        assert boxes_a == boxes_b, (
            "a mesma página deu caixas diferentes só por ter um raster junto")

        # And the sabotage that makes this test meaningful: the region does not
        # start at the top of the page, so a doubled offset is visible.
        page_height_px = page.rect.height * 150.0 / 72.0
        assert min(b.y for b in boxes_b) > 0.6 * page_height_px
        assert max(b.y for b in boxes_b) < page_height_px, (
            "as caixas saíram da página — a translação foi aplicada duas vezes")
    finally:
        doc.close()


def test_level_zero_boxes_are_already_in_page_space(pymupdf):
    """The other half: level 0 is handed the clip and the scale, so its boxes
    come back in page pixels and must *not* be translated again."""
    doc = build_page(pymupdf, [(400.0, 11.0, PROSE)])
    task = PageTask(pdf_page=doc[0], dpi=144.0, lang="eng")
    outcome = recognize_page([PdfTextLayerEngine()], task)
    boxes = [w.box for w in outcome.as_result().words]
    assert boxes
    # 400 pt at 144 dpi is 800 px; every word sits below it, once.
    assert min(b.y for b in boxes) > 700.0
    assert max(b.y for b in boxes) < 1400.0
    assert all("page_origin" not in r.result.meta for r in outcome.regions)
    doc.close()


# --------------------------------------------------------------------------- #
# Falling back to the whole page
# --------------------------------------------------------------------------- #


def test_a_rejected_page_never_arbitrates_region_by_region(pymupdf):
    """When the page's own layer is condemned there is nothing to salvage per
    region, and cutting it up would only pay the cost thirty times."""
    doc = build_page(pymupdf, [(90.0, 11.0, GIBBERISH),
                               (400.0, 11.0, GIBBERISH)])
    mock = MockOcr()
    outcome = recognize_page(
        [PdfTextLayerEngine(), mock],
        PageTask(pdf_page=doc[0], image=raster_for(doc[0]), dpi=150.0,
                 lang="eng"))
    assert outcome.whole_page
    assert len(outcome.regions) == 1
    assert len(mock.crops) == 1
    assert any("reprovada" in n for n in outcome.notes), outcome.notes
    doc.close()


def test_a_page_without_a_pdf_goes_whole(pymupdf):
    """No text layer means no free line source, and a level-1 engine that
    declares ``handles_layout`` does its own segmentation anyway."""
    doc = build_page(pymupdf, [(90.0, 11.0, PROSE)])
    mock = MockOcr()
    outcome = recognize_page(
        [mock], PageTask(image=raster_for(doc[0]), dpi=150.0, lang="eng"))
    assert outcome.whole_page
    assert outcome.regions[0].engine == "mock_ocr"
    assert any("sem página de PDF" in n for n in outcome.notes)
    doc.close()


def test_the_region_ceiling_is_enforced(mixed_doc):
    """A pathological page must not spend minutes."""
    config = PageConfig(max_regions=1)
    outcome = PageRecognizer([PdfTextLayerEngine()], config).run(
        PageTask(pdf_page=mixed_doc[0], lang="eng"))
    assert outcome.whole_page
    assert any("teto" in n for n in outcome.notes), outcome.notes


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #


def test_body_text_drops_the_folio(pymupdf):
    doc = build_page(pymupdf, [
        (80.0, 16.0, "Chapter Four"), (140.0, 11.0, PROSE), (800.0, 9.0, "41")])
    outcome = recognize_page([PdfTextLayerEngine()],
                             PageTask(pdf_page=doc[0], lang="eng"))
    assert "41" in outcome.text
    folio = [r for r in outcome.regions if r.kind.is_furniture]
    if folio:
        assert "41" not in outcome.body_text
    doc.close()


def test_the_flattened_result_keeps_reading_order(mixed_doc):
    outcome = recognize_page([PdfTextLayerEngine()],
                             PageTask(pdf_page=mixed_doc[0], lang="eng"))
    flat = outcome.as_result()
    assert flat.region_kind is RegionKind.PAGE
    assert flat.meta["regions"] == len(outcome.regions)
    assert flat.text.count("rook belongs behind") >= 1
    per_region = "\n".join(r.result.text for r in outcome.regions
                           if r.result.text.strip())
    assert flat.text.replace("\n", " ").split() == per_region.split()


def test_the_page_loop_is_deterministic(mixed_doc):
    """Same page, same engines, same answer — five times."""
    task = lambda: PageTask(pdf_page=mixed_doc[0],
                            image=raster_for(mixed_doc[0]), dpi=150.0,
                            lang="eng")
    runs = [recognize_page([PdfTextLayerEngine(), MockOcr()], task())
            for _ in range(5)]
    texts = {r.text for r in runs}
    engines = {r.engines_used for r in runs}
    assert len(texts) == 1, "a página produziu textos diferentes entre execuções"
    assert len(engines) == 1


def test_it_explains_itself(mixed_doc):
    """A page loop that cannot say what it did is unfixable in the field."""
    outcome = recognize_page(
        [PdfTextLayerEngine(), MockOcr()],
        PageTask(pdf_page=mixed_doc[0], image=raster_for(mixed_doc[0]),
                 dpi=150.0, lang="eng"))
    text = outcome.explain_pt()
    assert "região" in text
    assert "mock_ocr" in text
    assert "pdf_text_layer" in text


# --------------------------------------------------------------------------- #
# The corpus, end to end
# --------------------------------------------------------------------------- #


#: (key, page, whether level 0 must lose the page).  The first three are pages
#: whose notation is destroyed (F5_REPORT_C2 §2.6); the last two are the clean
#: controls, which must be left alone.
_ESCALATION_CASES = [
    ("gaprindashvili_ocr", 202, True),
    ("gaprindashvili_ocr", 245, True),
    ("aagaard", 222, True),
    ("dvoretsky", 408, False),
    ("nunn_pawnless", 250, False),
]


@pytest.mark.golden
@pytest.mark.parametrize("key,page_no,must_escalate", _ESCALATION_CASES)
def test_damaged_notation_actually_sends_the_page_on(pymupdf, key, page_no,
                                                     must_escalate):
    """The claim in F5_REPORT_C2 §2.6, measured instead of derived.

    Lowering the confidence to 0.55 is only worth anything if it actually
    misses the arbiter's level-0 bar of 0.82 and lets another engine compete.
    Arithmetic says it should; this runs it on the real pages and checks.

    Measured 2026-09-10, level-0 score:

    ==========================  =======  ==========  =============
    page                        score    confidence  plausibility
    ==========================  =======  ==========  =============
    Gaprindashvili p202         0.543    0.55        0.84
    Gaprindashvili p245         0.509    0.55        0.74
    Aagaard p222                0.545    0.55        0.84
    Dvoretsky p408 (control)    0.978    0.98        0.97
    Nunn p250 (control)         0.946    0.98        0.90
    ==========================  =======  ==========  =============

    Note the *plausibility* column: 0.84 on a page whose move text is
    destroyed.  That is the whole argument for the notation signal in one
    number — every language-shaped measure says the page is fine.

    What this does **not** show is that the OCR reads those moves better.  The
    level-1 engine here is a mock; whether Tesseract actually wins on merit is
    an open measurement (F5_REPORT_C2 §6, item 2).
    """
    from caissa.ocr.arbiter import Arbiter, RegionTask

    doc = pymupdf.open(corpus_path(key))
    try:
        page = doc[page_no]
        outcome = Arbiter([PdfTextLayerEngine(), MockOcr()]).run(
            RegionTask(image=raster_for(page), pdf_page=page, lang="eng",
                       scale=150.0 / 72.0))
        level_zero = next(s for s in outcome.scores
                          if s.engine == "pdf_text_layer")
        if must_escalate:
            assert outcome.escalated, outcome.explain_pt()
            assert level_zero.total < 0.82, level_zero.describe_pt()
            assert level_zero.confidence == pytest.approx(0.55)
            assert level_zero.plausibility > 0.70, (
                "a plausibilidade caiu: se ela agora acusa o dano, o sinal de "
                "notação pode ser redundante — confira antes de removê-lo")
        else:
            assert not outcome.escalated, outcome.explain_pt()
            assert level_zero.total >= 0.82, level_zero.describe_pt()
            assert level_zero.confidence == pytest.approx(0.98)
    finally:
        doc.close()


@pytest.mark.golden
def test_cutting_a_page_up_must_not_launder_its_verdict(pymupdf, corpus_doc):
    """**The defect the region loop introduced, and the rule that fixes it.**

    Gaprindashvili p202 is flagged at 0.55: 0.157 damaged moves over 83.  Cut
    into regions, both halves came back at **0.98** —

    =========  ==========  =============  ===============================
    unidade    confiança   danificados    por quê
    =========  ==========  =============  ===============================
    página     0.55        0.157 / 83     acusada, corretamente
    região 0   0.98        0.273 / **11**  o piso de 12 lances abstém-se
    região 1   0.98        **0.139** / 72  cai por baixo da barra de 0,15
    =========  ==========  =============  ===============================

    One half hides behind the sample floor and the other behind the bar, and a
    correct page-level finding is destroyed by splitting.  Before the fix the
    loop escalated **nothing** on this page; the page-level verdict alone was
    strictly better than the loop.

    The fix is not a lower bar per region.  Damaged figurines are a property of
    the **font**, which is the same in every region of the page, so a region
    with fewer pieces shows less damage without being more trustworthy.  A
    region may therefore be judged *worse* than its page — that is what
    per-region arbitration is for — but never *better*, on a defect the page
    measured with more evidence.
    """
    from caissa.ocr.page import PageRecognizer

    doc = corpus_doc("gaprindashvili_ocr")
    page = doc[202]
    engine = PdfTextLayerEngine()

    page_verdict = engine.assess(page, lang="eng")
    assert page_verdict.confidence == 0.55, page_verdict.reason

    recognizer = PageRecognizer([engine, MockOcr()])
    outcome = recognizer.run(PageTask(pdf_page=page, image=raster_for(page),
                                      dpi=150.0, lang="eng"))

    assert not outcome.whole_page, outcome.explain_pt()
    assert len(outcome.escalated_regions) == len(outcome.regions) >= 2, (
        "uma região desta página escapou do escalonamento: o veredito da "
        "página foi lavado pelo corte")

    # And the cap is what did it: assessed on its own, region 1 of this page
    # reads *cleaner* than the page and would have kept 0.98.
    from caissa.ocr.layout.analyze import (
        LayoutInput, analyze_page, lines_from_pdf_page)
    from caissa.ocr.types import BBox

    rect = page.rect
    layout = analyze_page(LayoutInput(
        page_box=BBox.from_edges(rect.x0, rect.y0, rect.x1, rect.y1),
        lines=lines_from_pdf_page(page, scale=1.0)))
    raw = [engine.assess(page, lang="eng", clip=r.box) for r in layout.regions]
    assert all(v.confidence == 0.98 for v in raw), (
        "as regiões desta página deixaram de ser mais confiantes que ela; "
        "o caso perdeu a graça e o teste não prova mais nada")

    capped = [recognizer._cap_by_page(v, page_verdict, engine) for v in raw]
    assert all(v.confidence == 0.55 for v in capped)
    # A number with no reason is unfixable in the field.
    assert all("não pode valer mais que a página" in v.reason for v in capped)
