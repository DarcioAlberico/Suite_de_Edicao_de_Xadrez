"""The figurine reader as a second opinion: glyph boxes become words the
trunk's way, the fusion swaps only the cipher tokens, and the glyph source
never anchors, never restyles, never touches prose."""

from __future__ import annotations

import numpy as np

from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig
from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.engines.glyph import GlyphBox, GlyphEngine, words_from_glyphs
from caissa.ocr.fusion import _figurine_fix, fuse_candidates
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind


class MockRaster:
    """A level-1 engine that reads a fixed text laid out over the crop (the
    ``tests/unit/ingest`` mock, repeated: the test trees are not packages)."""

    name = "mock_raster"
    version = "mock 1.0"

    def __init__(self, text: str, confidence: float = 0.95) -> None:
        self.text = text
        self.confidence = confidence

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def languages(self) -> set[str]:
        return {"eng", "por"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.TESSERACT,
            cost_per_megapixel_s=0.1,
            supports_char_boxes=False,
            supports_confidence=True,
            handles_layout=True,
        )

    def recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
        _, w = image.shape[:2]
        words = []
        x = 10.0
        for i, token in enumerate(self.text.split()):
            width = min(9.0 * len(token), max(10.0, w - x - 1))
            words.append(
                OcrWord(
                    text=token,
                    box=BBox(x, 8.0, width, 18.0),
                    confidence=self.confidence,
                    word_index=i,
                )
            )
            x += width + 6.0
            if x > w - 20:
                x = 10.0
        line = OcrLine(words=tuple(words), box=BBox(10.0, 8.0, max(20.0, w - 20.0), 18.0))
        return OcrResult(engine=self.name, lang=lang, lines=(line,), region_kind=psm_hint)


def inked_page(h: int = 400, w: int = 1200) -> np.ndarray:
    image = np.full((h, w), 248, dtype=np.uint8)
    image[8:26, ::3] = 10
    return image


def _glyph(text: str, x: float, w: float = 10.0, conf: float = 0.99) -> GlyphBox:
    return GlyphBox(text=text, confidence=conf, box=BBox(x, 0.0, w, 14.0))


def test_words_follow_the_gap_rule_and_marks_attach():
    glyphs = [
        _glyph("3", 0),
        _glyph("6", 10),  # "36"
        _glyph(".", 30, 3),
        _glyph(".", 40, 3),
        _glyph(".", 50, 3),  # wide-set dots
        _glyph("♖", 75),
        _glyph("e", 86),
        _glyph("8", 96),
        _glyph("!", 120, 4, 0.8),
    ]
    words = words_from_glyphs(glyphs)
    assert [w.text for w in words] == ["36...", "♖e8!"]
    assert words[1].confidence == 0.8, "a word is as sure as its least sure glyph"
    assert words[1].box.x0 == 75.0
    assert words[1].box.x1 == 124.0


def test_ligature_classes_split_their_box_per_character():
    words = words_from_glyphs([_glyph("♕x", 0, 20), _glyph("e", 21), _glyph("5", 31)])
    assert [w.text for w in words] == ["♕xe5"]
    chars = words[0].chars
    assert [c.text for c in chars] == ["♕", "x", "e", "5"]
    assert chars[0].box.w == 10.0
    assert chars[1].box.x0 == 10.0
    assert chars[0].inherited_confidence
    assert not chars[2].inherited_confidence


def test_engine_is_unavailable_with_a_sentence_when_the_trunk_is_absent(monkeypatch):
    from caissa.vision.classify import cvoff

    def missing() -> None:
        raise FileNotFoundError("sem tronco")

    monkeypatch.setattr(cvoff, "ensure_cvoff_on_path", missing)
    engine = GlyphEngine()
    assert not engine.available()
    assert "ChessVisionOFF" in (engine.unavailable_reason() or "")
    assert engine.recognize(np.zeros((10, 10), np.uint8), lang="eng").is_empty


# --------------------------------------------------------------------------- #
# Fusion
# --------------------------------------------------------------------------- #


def test_figurine_fix_recognises_the_cipher_and_nothing_else():
    assert _figurine_fix("Hea!", "♖e8!")  # one misread digit tolerated
    assert _figurine_fix("2d5", "♗d5")  # a digit is ♗'s look-alike
    assert _figurine_fix("22...28,", "22...♗f8,")  # glued move number
    assert _figurine_fix("De2", "♘e2")  # a German-looking piece letter
    assert not _figurine_fix("e4", "♘e4")  # a pawn move is not a cipher
    assert not _figurine_fix("If", "lf")
    assert not _figurine_fix("36...", "36")
    assert not _figurine_fix("♖e8", "♖e8")
    assert not _figurine_fix("M", "♔g2")


def _words(text: str, confidences, *, engine: str, variant: str) -> OcrResult:
    tokens = text.split()
    confs = list(confidences) if not isinstance(confidences, float) else [confidences] * len(tokens)
    words = tuple(
        OcrWord(text=tok, box=BBox(60.0 * n, 0.0, 50.0, 20.0), confidence=confs[n], word_index=n)
        for n, tok in enumerate(tokens)
    )
    return OcrResult(
        engine=engine,
        lang="eng",
        lines=(OcrLine(words=words, box=BBox.union_of([w.box for w in words])),),
        meta={"variant": variant},
    )


def _decision(kind: Decision = Decision.REVIEW, score: float = 0.8) -> RegionDecision:
    return RegionDecision(kind, score, 0.78, 0.5, ())


def test_glyph_source_fixes_figurines_but_never_anchors_or_restyles():
    tess = _words(
        "If 36... Hea! 2h6", [0.95, 0.9, 0.6, 0.85], engine="tesseract", variant="original"
    )
    glyph = _words("lf 36 ♖e8! ♗h6", [0.7, 1.0, 1.0, 0.95], engine="glyph", variant="glyph")
    fused = fuse_candidates(
        [(tess, 0.80, _decision()), (glyph, 0.90, _decision(score=0.9))],
        lang="eng",
        never_anchor=frozenset({"glyph"}),
    )
    assert fused is not None
    assert fused.anchor == "original/tesseract", (
        "the better-scored glyph source still never anchors"
    )
    assert fused.result.text == "If 36... ♖e8! ♗h6"
    assert fused.changed == 2
    fixed = fused.tokens[2]
    assert fixed.chosen_from == "glyph/glyph"
    assert fixed.alternative == "Hea!"
    assert not fused.tokens[1].disputed, "36... versus 36 is formatting, not a dispute"
    assert fused.tokens[0].text == "If", "prose stays the anchor's"


def test_glyph_alone_fuses_nothing():
    glyph = _words("36 ♖e8!", 1.0, engine="glyph", variant="glyph")
    assert fuse_candidates([(glyph, 0.9, _decision())], never_anchor=frozenset({"glyph"})) is None
    tess = _words("36... Hea!", 0.7, engine="tesseract", variant="original")
    assert (
        fuse_candidates(
            [(glyph, 0.9, _decision()), (tess, 0.8, _decision())],
            never_anchor=frozenset({"glyph", "tesseract"}),
        )
        is None
    )


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


class FakeGlyph:
    """Reads the strips it is given and answers the figurine form, in place."""

    name = "glyph"
    version = "fake"

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.strips_seen: list[int] = []

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def languages(self) -> set[str]:
        return {"eng"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.TESSERACT,
            cost_per_megapixel_s=0.5,
            supports_char_boxes=True,
            supports_confidence=True,
        )

    def recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
        return OcrResult(engine=self.name, lang=lang, region_kind=psm_hint)

    def recognize_lines(self, image, strips, *, lang: str, psm_hint: RegionKind) -> OcrResult:
        self.strips_seen.append(len(strips))
        # The mock raster lays words at a known pitch; answer at the same boxes.
        raster = MockRaster(text=" ".join(self.answers.values()), confidence=0.99)
        result = raster.recognize(image, lang=lang, psm_hint=psm_hint)
        return OcrResult(engine=self.name, lang=lang, lines=result.lines, region_kind=psm_hint)


def test_service_swaps_the_cipher_tokens_with_the_glyph_reader():
    text = "36... Hea! 37 Exd5 Hb6 38 2g5 White has excellent prospects"
    answers = {
        "36...": "36...",
        "Hea!": "♖e8!",
        "37": "37",
        "Exd5": "♖xd5",
        "Hb6": "♖b6",
        "38": "38",
        "2g5": "♗g5",
        "White": "Whlte",
        "has": "has",
        "excellent": "excellent",
        "prospects": "prospects",
    }
    glyph = FakeGlyph(answers)
    service = OcrService(
        [MockRaster(text=text, confidence=0.75)],
        OcrServiceConfig(use_portfolio=False, movetext_candidates=False),
        lang="eng",
        glyph_engine=glyph,
    )
    recognition = service.recognize_image(inked_page(), dpi=300.0, lang="eng")
    region = recognition.regions[0]
    assert glyph.strips_seen == [1], "one strip per anchor line"
    assert region.text == "36... ♖e8! 37 ♖xd5 ♖b6 38 ♗g5 White has excellent prospects", (
        "figurines swapped in, prose left to the anchor"
    )
    assert region.engine == "mock_raster"
    assert [c.variant for c in region.candidates] == ["original", "glyph"]
    assert region.candidates[1].secondary


def test_service_skips_the_glyph_reader_on_pure_prose():
    glyph = FakeGlyph({})
    service = OcrService(
        [MockRaster("the rook belongs behind the passed pawn", confidence=0.75)],
        OcrServiceConfig(use_portfolio=False, movetext_candidates=False),
        lang="eng",
        glyph_engine=glyph,
    )
    service.recognize_image(inked_page(), dpi=300.0, lang="eng")
    assert glyph.strips_seen == []


class FailingRaster(MockRaster):
    """An engine that is available and dies on every region — a setup fault."""

    def recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
        from caissa.ocr.types import empty_result

        return empty_result(self.name, lang, region_kind=psm_hint,
                            warning="O Tesseract terminou com código 1.",
                            error_detail="Error opening data file models/tessdata/eng.traineddata")


def test_a_page_where_every_region_failed_in_the_engine_says_so():
    service = OcrService([FailingRaster("x")], OcrServiceConfig(use_portfolio=False,
                                                              movetext_candidates=False,
                                                              glyph_candidates=False), lang="eng")
    recognition = service.recognize_image(inked_page(), dpi=300.0, lang="eng")
    assert not recognition.answered
    fault = [n for n in recognition.notes if "falharam" in n]
    assert fault and "Error opening data file" in fault[0]
    assert "falharam" in " ".join(recognition.trace()["notes"])


def test_fine_tuned_figurine_model_is_a_secondary_candidate_too():
    text = "36... Hea! 37 Exd5 Hb6 38 2g5 White has excellent prospects"
    answers = {"36...": "36...", "Hea!": "♖e8!", "37": "37", "Exd5": "♖xd5", "Hb6": "♖b6",
               "38": "38", "2g5": "♗g5", "White": "Whlte", "has": "has",
               "excellent": "excellent", "prospects": "prospects"}

    class FakeFigurineModel(MockRaster):
        name = "tesseract"      # a real one is a Tesseract over models/tessdata
        langs_seen: list[str] = []

        def recognize(self, image, *, lang: str, psm_hint: RegionKind) -> OcrResult:
            self.langs_seen.append(lang)
            return MockRaster(" ".join(answers.values()), 0.97).recognize(
                image, lang=lang, psm_hint=psm_hint)

    model = FakeFigurineModel("unused")
    service = OcrService([MockRaster(text=text, confidence=0.75)],
                         OcrServiceConfig(use_portfolio=False, movetext_candidates=False,
                                          glyph_candidates=False),
                         lang="eng", figurine_engine=model)
    service._figurine_dir = None   # injected engine: the language map is bypassed below
    service._figurine_lang = lambda lang: "caissa_eng"  # type: ignore[method-assign]
    recognition = service.recognize_image(inked_page(), dpi=300.0, lang="eng")
    region = recognition.regions[0]
    assert model.langs_seen == ["caissa_eng"]
    assert region.text == "36... ♖e8! 37 ♖xd5 ♖b6 38 ♗g5 White has excellent prospects"
    assert region.engine == "mock_raster", "the fine-tuned model never anchors"
    assert [c.variant for c in region.candidates] == ["original", "figurine"]
    assert region.candidates[1].engine == "tesseract_figurine"
    assert region.candidates[1].secondary


def test_no_figurine_model_directory_means_no_candidate(tmp_path, monkeypatch):
    monkeypatch.delenv("CAISSA_FIGURINE_TESSDATA", raising=False)
    service = OcrService([MockRaster("36... Hea! 37 Exd5 Hb6 38 2g5", 0.75)],
                         OcrServiceConfig(use_portfolio=False, movetext_candidates=False,
                                          glyph_candidates=False,
                                          figurine_tessdata=str(tmp_path)), lang="eng")
    # tmp_path has no caissa_*.traineddata and the repo default is only used when it has one;
    # whatever this machine holds, an empty explicit directory must not raise.
    recognition = service.recognize_image(inked_page(), dpi=300.0, lang="eng")
    assert recognition.regions
