"""OCR_UI_ROADMAP_C2 passo B2: the movetext profile reaches the mixed page.

Sol §SOL-7's profile ran only on a region that read as movetext *as a
whole* (half its tokens moves).  A book page is prose with analysis in it,
always under half, so the prose DAWG "corrected" its moves into words and
the profile never ran.  Now each line that carries notation is read again
as a strip with the movetext profile, and the strips are one more candidate
for the fusion.  The mock engine below records which crops were asked with
which profile; the sabotage is the config switch.
"""

from __future__ import annotations

import numpy as np

from caissa.ingest.pdf.ocr_service import (
    OcrService,
    OcrServiceConfig,
    _line_carries_notation,
    _looks_like_movetext,
)
from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.engines.profiles import TesseractProfile
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

ROWS = [
    "Rubinstein showed how to convert a small endgame edge in this position",
    "After 34.Kf2 Kf7 35.Ke3 Ke6 36.Kd4 Kd6 37.b4 axb4 38.axb4 g5 39.g3 White",
    "keeps the opposition and will eventually win the c-pawn for nothing",
    "The black king arrived one tempo too late because the rooks had to go",
]
LINE_H = 22.0


class MockTesseract:
    """Reads ``ROWS`` as four lines on the whole page; on a strip, reads the
    row whose height it was given (the strip is that row plus a margin)."""

    name = "tesseract"

    def __init__(self) -> None:
        self.strips: list[tuple[str, tuple[int, int]]] = []
        self._forced: TesseractProfile | None = None

    def available(self) -> bool:
        return True

    def unavailable_reason(self):
        return None

    def languages(self) -> set[str]:
        return {"eng", "por"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(level=EngineLevel.TESSERACT, cost_per_megapixel_s=0.1,
                                  supports_char_boxes=False, supports_confidence=True,
                                  handles_layout=True)

    @property
    def version(self) -> str:
        return "mock"

    def recognize_with_profile(self, image, *, lang: str, psm_hint: RegionKind,
                               profile: TesseractProfile) -> OcrResult:
        self._forced = profile
        try:
            return self.recognize(image, lang=lang, psm_hint=psm_hint)
        finally:
            self._forced = None

    @staticmethod
    def _line(text: str, y: float, confidence: float) -> OcrLine:
        words, x = [], 10.0
        for i, token in enumerate(text.split()):
            width = 9.0 * len(token)
            words.append(OcrWord(text=token, box=BBox(x, y, width, LINE_H),
                                 confidence=confidence, word_index=i))
            x += width + 6.0
        return OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words]))

    def recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
        h, w = image.shape[:2]
        if psm_hint is RegionKind.SINGLE_LINE:
            # A strip: the row under it is the one whose band the crop covers.
            self.strips.append((str(self._forced), (h, w)))
            text = ROWS[1] if h < 2 * LINE_H + 20 else " ".join(ROWS)
            return OcrResult(engine=self.name, lang=lang,
                             lines=(self._line(text, 0.35 * LINE_H, 0.97),),
                             region_kind=psm_hint,
                             meta={"profile": str(self._forced or TesseractProfile.PROSE)})
        lines = tuple(self._line(row, 8.0 + n * (LINE_H + 10.0), 0.85)
                      for n, row in enumerate(ROWS))
        return OcrResult(engine=self.name, lang=lang, lines=lines, region_kind=psm_hint,
                         meta={"profile": str(self._forced or TesseractProfile.PROSE)})


def inked(h: int = 200, w: int = 1400) -> np.ndarray:
    image = np.full((h, w), 248, dtype=np.uint8)
    for n in range(len(ROWS)):
        y = int(8 + n * (LINE_H + 10))
        image[y:y + int(LINE_H), ::3] = 10
    return image


def _service(engine: MockTesseract, **overrides) -> OcrService:
    config = OcrServiceConfig(use_portfolio=False, glyph_candidates=False,
                              figurine_candidates=False, secondary_engines=(),
                              validate_notation=False, **overrides)
    return OcrService([engine], config, lang="eng")


def test_only_the_notation_line_of_a_mixed_region_is_read_as_a_strip():
    engine = MockTesseract()
    recognition = _service(engine).recognize_image(inked(), dpi=300, lang="eng")
    assert recognition.answered
    # One strip, with the movetext profile, over one row plus its margin.
    assert len(engine.strips) == 1
    profile, (h, _w) = engine.strips[0]
    assert profile == str(TesseractProfile.MOVETEXT)
    assert LINE_H < h < 2 * LINE_H
    # ...and it is a candidate of the region, paired with the anchor.
    variants = [c.variant for c in recognition.regions[0].candidates]
    assert "movetext_strips" in variants
    strip = next(c for c in recognition.regions[0].candidates if c.variant == "movetext_strips")
    assert strip.result.text == ROWS[1]
    assert strip.result.meta["strips"] == 1


def test_sabotage_the_switch_leaves_the_mixed_region_to_the_prose_profile():
    engine = MockTesseract()
    recognition = _service(engine, movetext_strips=False).recognize_image(
        inked(), dpi=300, lang="eng")
    assert recognition.answered
    assert engine.strips == []
    assert "movetext_strips" not in [c.variant for c in recognition.regions[0].candidates]


def test_a_strip_that_fails_is_said_in_the_page_notes_and_the_page_keeps_its_anchor():
    """Never silently (crítico Codex, fase 2 ciclo 1): the extra candidate must not fail the
    page, but the recognition says the strips were lost — in ``notes``, not only in the log."""

    class Failing(MockTesseract):
        def recognize_with_profile(self, image, *, lang, psm_hint, profile):
            raise RuntimeError("tesseract morreu na faixa")

    engine = Failing()
    recognition = _service(engine).recognize_image(inked(), dpi=300, lang="eng")
    assert recognition.answered, "the page keeps its anchor"
    assert "movetext_strips" not in [c.variant for c in recognition.regions[0].candidates]
    assert any("faixa de lances falhou" in n and "RuntimeError" in n for n in recognition.notes), recognition.notes
    assert sum("faixa de lances falhou" in n for n in recognition.notes) == 1, "one note per region"


def test_a_line_needs_two_moves_to_be_a_strip():
    line = MockTesseract._line("the e4 pawn is weak", 0.0, 0.9)
    assert not _line_carries_notation(line)
    assert _line_carries_notation(MockTesseract._line(ROWS[1], 0.0, 0.9))


def test_numbered_moves_past_move_nine_still_read_as_movetext():
    """``10.d4`` tokenises as three; the numbers and dots no longer count
    against the moves (the region-level rule of passo B2)."""
    text = "10.d4 Nbd7 11.Nbd2 Bb7 12.Bc2 Re8 13.Nf1 Bf8 14.Ng3 g6"
    result = OcrResult(engine="tesseract", lang="eng",
                       lines=(MockTesseract._line(text, 0.0, 0.9),),
                       region_kind=RegionKind.PAGE)
    assert _looks_like_movetext(result)
    prose = OcrResult(engine="tesseract", lang="eng",
                      lines=(MockTesseract._line(ROWS[0], 0.0, 0.9),),
                      region_kind=RegionKind.PAGE)
    assert not _looks_like_movetext(prose)


def test_the_strips_candidate_is_calibrated_with_tesseract_table():
    """Passo B6 meets B2: the strips are Tesseract readings under another name, so their raw
    confidences go through Tesseract's fitted table.  Without the mapping the anchor was
    calibrated and the strips stayed raw -- the mismatch B6 exists to remove."""
    from types import SimpleNamespace

    from caissa.ingest.pdf.ocr_service import STRIPS_ENGINE
    from caissa.ocr.arbiter import ArbiterConfig
    from caissa.ocr.types import RegionKind as Kind

    def result(engine: str) -> OcrResult:
        word = OcrWord(text="Nf3", box=BBox(0, 0, 10, 10), confidence=0.8)
        line = OcrLine(words=(word,), box=BBox(0, 0, 10, 10), kind=Kind.MOVETEXT)
        return OcrResult(engine=engine, lang="eng", lines=(line,), region_kind=Kind.MOVETEXT)

    recognizer = SimpleNamespace(config=SimpleNamespace(arbiter=ArbiterConfig()))
    region_outcome = SimpleNamespace(region=SimpleNamespace(kind=Kind.MOVETEXT))
    task = SimpleNamespace(image=np.zeros((8, 8), np.uint8), lang="eng", scale=300.0 / 72.0)
    candidates = [SimpleNamespace(result=result("tesseract")), SimpleNamespace(result=result(STRIPS_ENGINE))]

    calibrators = OcrService._calibrators(recognizer, candidates, region_outcome, task)

    assert "tesseract" in calibrators
    assert STRIPS_ENGINE in calibrators, "the strips stayed on the raw scale"
    for raw in (0.3, 0.6, 0.85, 0.95):
        assert calibrators[STRIPS_ENGINE](raw) == calibrators["tesseract"](raw)


def test_the_arbiter_scores_the_strips_on_tesseract_scale_too():
    """Not only the fusion: the arbiter's own scoring of the strips candidate (``arbiter.score``
    → ``calibration_for(result.engine, key)``) borrows Tesseract's calibration (``SCALE_OF``)."""
    from caissa.ingest.pdf.ocr_service import STRIPS_ENGINE
    from caissa.ocr.arbiter import SCALE_OF, ArbiterConfig
    from caissa.ocr.calibration import FacetKey

    assert SCALE_OF[STRIPS_ENGINE] == "tesseract"
    config = ArbiterConfig()
    theirs = config.calibration_for(STRIPS_ENGINE, FacetKey(engine=STRIPS_ENGINE, lang="eng"))
    ours = config.calibration_for("tesseract", FacetKey(engine="tesseract", lang="eng"))
    assert theirs.table is not None, "the strips stayed on the raw scale"
    assert theirs.key == ours.key and theirs.table == ours.table
    assert theirs.worst_word_weight == ours.worst_word_weight
