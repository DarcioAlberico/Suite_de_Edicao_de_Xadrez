"""The reading that leaves ink unread — OCR_UI_ROADMAP_C2 passo B14.

A page is drawn with six lines of real letters (``cv2.putText``) and read
twice by hand: the whole page, and its first two lines only — what Tesseract
returned for ``synth:Dvoretsky…:201:21`` on the photograph stratum, accepted
at 0,872 with CER 0,786.  The measure must tell them apart; the vignette of a
photograph, a faint show-through and a board's pieces must not count as ink;
and the service must neither anchor on nor accept the partial reading.
"""

from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from caissa.ingest.pdf.ocr_service import Candidate, OcrService, OcrServiceConfig
from caissa.ocr.coverage import CoverageConfig, ink_coverage, ink_map
from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.layout.analyze import LayoutRegion
from caissa.ocr.page import PageTask, RegionOutcome
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

FONT = cv2.FONT_HERSHEY_SIMPLEX
LINES = ["the king walks to the centre", "and the rook cuts it off", "white wins the pawn ending",
         "because the opposition decides", "black cannot hold the draw", "the lesson is simple"]


def draw_page(*, vignette: bool = False, show_through: bool = False,
              board: bool = False) -> tuple[np.ndarray, list[OcrLine]]:
    """A 300 DPI strip with six lines of text and the reading of all of them."""
    page = np.full((560, 1100), 255, np.uint8)
    lines: list[OcrLine] = []
    y = 60
    for n, text in enumerate(LINES):
        x = 40
        words = []
        for token in text.split():
            (w, h), base = cv2.getTextSize(token, FONT, 1.0, 2)
            cv2.putText(page, token, (x, y), FONT, 1.0, 0, 2, cv2.LINE_AA)
            words.append(OcrWord(text=token, box=BBox(x, y - h, w, h + base), confidence=0.95,
                                 block_index=1, line_index=n))
            x += w + 18
        lines.append(OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words]),
                             block_index=1, line_index=n))
        y += 80
    if show_through:
        mirrored = np.full_like(page, 255)
        for n, text in enumerate(LINES):
            cv2.putText(mirrored, text[::-1], (60, 100 + 80 * n), FONT, 1.0, 0, 2, cv2.LINE_AA)
        # the verso at 25 %: 0,75 of the paper where its letters are
        page = np.minimum(page, (255 - 0.25 * (255 - mirrored)).astype(np.uint8))
    if vignette:
        ramp = np.linspace(1.0, 0.45, page.shape[1])[None, :]
        page = (page.astype(np.float32) * ramp).astype(np.uint8)
    if board:
        cv2.rectangle(page, (800, 20), (1080, 300), 0, 3)
        for r in range(4):
            for c in range(4):
                cv2.putText(page, "K", (815 + 70 * c, 75 + 70 * r), FONT, 1.2, 0, 3)
    return page, lines


def reading(lines: list[OcrLine]) -> OcrResult:
    return OcrResult(engine="tesseract", lang="eng", lines=tuple(lines),
                     region_kind=RegionKind.PAGE, duration_s=0.1, meta={"psm": 3})


# --------------------------------------------------------------------------- #
# The measure
# --------------------------------------------------------------------------- #


def test_the_whole_reading_covers_the_ink_and_a_partial_one_does_not() -> None:
    page, lines = draw_page()
    ink = ink_map(page, 300.0)
    assert ink.count >= 100
    assert ink_coverage(reading(lines), ink) == pytest.approx(1.0, abs=0.02)
    partial = ink_coverage(reading(lines[:2]), ink)
    assert partial is not None and partial < 0.45


def test_a_line_that_lost_its_end_is_measured_as_lost() -> None:
    page, lines = draw_page()
    ink = ink_map(page, 300.0)
    cut = [OcrLine(words=line.words[:2], box=BBox.union_of([w.box for w in line.words[:2]]),
                   block_index=1) for line in lines]
    share = ink_coverage(reading(cut), ink)
    assert share is not None and 0.2 < share < 0.75


def test_the_vignette_of_a_photograph_is_not_ink() -> None:
    page, lines = draw_page(vignette=True)
    ink = ink_map(page, 300.0)
    assert ink_coverage(reading(lines), ink) == pytest.approx(1.0, abs=0.03)


def test_a_faint_show_through_is_not_ink() -> None:
    page, lines = draw_page(show_through=True)
    clean = ink_map(draw_page()[0], 300.0)
    ink = ink_map(page, 300.0)
    assert ink.count == pytest.approx(clean.count, rel=0.05)
    assert ink_coverage(reading(lines), ink) == pytest.approx(1.0, abs=0.03)


def test_the_pieces_inside_a_board_are_not_the_regions_text() -> None:
    page, lines = draw_page(board=True)
    ink = ink_map(page, 300.0)
    assert ink_coverage(reading(lines), ink) == pytest.approx(1.0, abs=0.03)


def _with_picture(page: np.ndarray, picture: np.ndarray) -> np.ndarray:
    out = np.vstack([page, np.full((picture.shape[0] + 40, page.shape[1]), 255, np.uint8)])
    out[page.shape[0] + 20:page.shape[0] + 20 + picture.shape[0], 200:200 + picture.shape[1]] = picture
    return out


def test_a_halftone_photograph_does_not_hijack_the_letter_size() -> None:
    """Thousands of 5 px dots made a relative median call the letters "too big": coverage
    0,009 on a page read whole.  Letters are sized in inches now."""
    page, lines = draw_page()
    dots = np.full((300, 500), 255, np.uint8)
    for y0 in range(0, 300, 6):
        for x0 in range(0, 500, 6):
            radius = int(2.5 * (0.5 + 0.5 * np.sin(x0 / 40) * np.cos(y0 / 30)))
            if radius > 0:
                cv2.circle(dots, (x0, y0), radius, 0, -1)
    ink = ink_map(_with_picture(page, dots), 300.0)
    assert ink_coverage(reading(lines), ink) == pytest.approx(1.0, abs=0.02)
    assert ink_coverage(reading(lines[:2]), ink) < 0.45


def test_a_continuous_tone_photograph_is_not_text() -> None:
    """Letter-sized blobs of a photograph smear into shapes that are not lines."""
    page, lines = draw_page()
    noise = np.random.default_rng(1).normal(0, 1, (300, 500)).astype(np.float32)
    blur = cv2.GaussianBlur(noise, (0, 0), 15)
    photo = (128 + 90 * blur / (blur.std() + 1e-6)).clip(0, 255).astype(np.uint8)
    ink = ink_map(_with_picture(page, photo), 300.0)
    assert ink_coverage(reading(lines), ink) >= 0.95


def test_a_column_gutter_is_not_smeared_across() -> None:
    """Two columns stay two runs of text: a reading of the left one covers only it."""
    page = np.full((300, 1400), 255, np.uint8)
    left: list[OcrLine] = []
    for n in range(4):
        y, x, words = 60 + 60 * n, 40, []
        for token in ["the", "rook", "cuts", "the", "king", "off"]:
            (w, h), base = cv2.getTextSize(token, FONT, 1.0, 2)
            cv2.putText(page, token, (x, y), FONT, 1.0, 0, 2, cv2.LINE_AA)
            words.append(OcrWord(text=token, box=BBox(x, y - h, w, h + base), confidence=0.9))
            x += w + 18
        left.append(OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words])))
        cv2.putText(page, "and black holds the draw", (x + 120, y), FONT, 1.0, 0, 2, cv2.LINE_AA)
    share = ink_coverage(reading(left), ink_map(page, 300.0))
    assert share is not None and 0.35 < share < 0.65


def test_the_diagram_boxes_the_caller_names_are_left_out() -> None:
    page, lines = draw_page()
    everything = ink_map(page, 300.0)
    without_last_lines = ink_map(page, 300.0, exclude=[BBox(0, 330, 1100, 230)])
    assert without_last_lines.count < everything.count
    assert ink_coverage(reading(lines[:4]), without_last_lines) == pytest.approx(1.0, abs=0.03)


def test_a_scanner_frame_around_the_page_is_not_a_thing_on_it() -> None:
    """Kmoch (1936), crítico da fase 5: the dark border a scanner leaves around the page is one
    component the size of the page, and as a «big thing» it took every letter inside it -- 0
    letters instead of ~1.000.  A box that takes half the image is the page's frame."""
    page, _lines = draw_page()
    framed = cv2.copyMakeBorder(page, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=40)
    assert ink_map(framed, 300.0).count == ink_map(page, 300.0).count > 100
    # the sabotage: without the exception for the frame, the border swallows the page
    assert ink_map(framed, 300.0, config=CoverageConfig(frame_area_share=1.01)).count == 0


def test_too_few_letters_say_nothing() -> None:
    page = np.full((120, 400), 255, np.uint8)
    cv2.putText(page, "17", (20, 80), FONT, 1.0, 0, 2)
    assert ink_coverage(reading([]), ink_map(page, 300.0)) is None
    assert ink_coverage(reading([]), ink_map(None, 300.0)) is None


def test_the_config_holds_the_measured_numbers() -> None:
    cfg = CoverageConfig()
    assert cfg.ink_fraction == 0.62 and cfg.min_components == 12 and cfg.pad == 0.35


# --------------------------------------------------------------------------- #
# The service: anchor, decision, variants -- and the switch
# --------------------------------------------------------------------------- #


def _decision(kind: Decision, score: float) -> RegionDecision:
    return RegionDecision(kind, score, 0.78, 0.5, ())


def _candidate(result: OcrResult, kind: Decision, score: float, variant: str) -> Candidate:
    return Candidate(variant=variant, engine=result.engine, result=result,
                     decision=_decision(kind, score), score=score, outcome=None)


def _settle(config: OcrServiceConfig, candidates: list[Candidate], page: np.ndarray, lines):
    service = OcrService([], config=config)
    region = LayoutRegion(kind=RegionKind.PAGE, box=BBox(0, 0, page.shape[1], page.shape[0]),
                          line_indices=(), reading_order=0)
    outcome = RegionOutcome(region=region, outcome=None, result=candidates[0].result, own_verdict=True)
    task = PageTask(image=page, lang="eng", dpi=300.0)
    ink = ink_map(page, 300.0) if config.ink_coverage else None
    return service._settle(outcome, candidates, task, ink=ink)


QUIET = dict(fuse=False, validate_notation=False, movetext_candidates=False,
             glyph_candidates=False, figurine_candidates=False, secondary_engines=())


def test_the_partial_reading_is_never_accepted() -> None:
    page, lines = draw_page()
    partial = _candidate(reading(lines[:2]), Decision.ACCEPTED, 0.87, "original")
    settled = _settle(OcrServiceConfig(**QUIET), [partial], page, lines)
    assert settled.decision.decision is Decision.REVIEW
    assert settled.decision.demoted
    assert "da tinta desta região" in settled.decision.reasons_pt[-1]
    assert settled.ink_coverage is not None and settled.ink_coverage < 0.45


def test_the_complete_reading_anchors_over_the_higher_scoring_partial_one() -> None:
    page, lines = draw_page()
    partial = _candidate(reading(lines[:2]), Decision.ACCEPTED, 0.87, "original")
    complete = _candidate(reading(lines), Decision.REVIEW, 0.60, "deskew_shadow")
    settled = _settle(OcrServiceConfig(**QUIET), [partial, complete], page, lines)
    assert settled.result.text == reading(lines).text
    assert settled.variant == "deskew_shadow"


def test_the_fusion_anchors_on_the_complete_reading_too() -> None:
    page, lines = draw_page()
    partial = _candidate(reading(lines[:2]), Decision.ACCEPTED, 0.87, "original")
    complete = _candidate(reading(lines), Decision.ACCEPTED, 0.80, "deskew_shadow")
    quiet = {**QUIET, "fuse": True}
    settled = _settle(OcrServiceConfig(**quiet), [partial, complete], page, lines)
    assert len(settled.result.lines) == len(LINES)
    assert settled.decision.decision is Decision.ACCEPTED


def test_an_abstained_complete_reading_does_not_take_the_seat() -> None:
    """A complete reading the arbiter abstained on would silence the region;
    the partial one keeps it -- and goes to review, never accepted."""
    page, lines = draw_page()
    partial = _candidate(reading(lines[:2]), Decision.ACCEPTED, 0.87, "original")
    complete = _candidate(reading(lines), Decision.ABSTAINED, 0.30, "upscale")
    settled = _settle(OcrServiceConfig(**QUIET), [partial, complete], page, lines)
    assert settled.variant == "original"
    assert settled.decision.decision is Decision.REVIEW


def test_the_sabotage_switch_accepts_the_partial_reading_again() -> None:
    page, lines = draw_page()
    partial = _candidate(reading(lines[:2]), Decision.ACCEPTED, 0.87, "original")
    complete = _candidate(reading(lines), Decision.REVIEW, 0.60, "deskew_shadow")
    settled = _settle(OcrServiceConfig(**QUIET, ink_coverage=False), [partial, complete], page, lines)
    assert settled.variant == "original"
    assert settled.decision.decision is Decision.ACCEPTED
    assert settled.ink_coverage is None


def test_an_accepted_but_partial_reading_asks_for_the_variants() -> None:
    service = OcrService([], config=OcrServiceConfig())
    result = reading(draw_page()[1][:2])
    arbitration = SimpleNamespace(accepted=True, result=result, candidates=(result,),
                                  engines_run=("tesseract",), winner=SimpleNamespace(total=0.87))
    outcome = SimpleNamespace(outcome=arbitration)
    assert service._wants_variants(outcome, coverage=0.30) is True
    assert service._wants_variants(outcome, coverage=0.97) is False
    assert service._wants_variants(outcome) is False


class _Engine:
    """An engine that returns a fixed reading, as Tesseract would."""

    name = "tesseract"

    def __init__(self, result: OcrResult) -> None:
        self.result = result

    def capabilities(self):
        from caissa.ocr.engines.base import EngineCapabilities, EngineLevel

        return EngineCapabilities(level=EngineLevel.TESSERACT, cost_per_megapixel_s=1.0,
                                  supports_char_boxes=False, supports_confidence=True)

    def available(self) -> bool:
        return True

    def supports_language(self, lang: str) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def recognize(self, image, *, lang="por", psm_hint=RegionKind.PARAGRAPH) -> OcrResult:
        return self.result


def test_a_region_the_measure_cannot_judge_is_said_in_the_trace() -> None:
    """Crítico da fase 5: a region the measure cannot judge (too few letters, or ink the rules
    left out) went on as if it had passed.  The trace now says so."""
    page = np.full((200, 600), 255, np.uint8)
    cv2.putText(page, "ab", (40, 100), FONT, 1.0, 0, 2, cv2.LINE_AA)
    word = OcrWord(text="ab", box=BBox(40, 80, 40, 30), confidence=0.95, block_index=1)
    result = OcrResult(engine="tesseract", lang="eng",
                       lines=(OcrLine(words=(word,), box=word.box, block_index=1),),
                       region_kind=RegionKind.PAGE, duration_s=0.1, meta={"psm": 3})
    service = OcrService([_Engine(result)], config=OcrServiceConfig(**QUIET))
    notes = service.recognize_image(page, dpi=300.0, lang="eng").trace().get("notes", [])
    assert any("cobertura da tinta não medida" in note for note in notes)
