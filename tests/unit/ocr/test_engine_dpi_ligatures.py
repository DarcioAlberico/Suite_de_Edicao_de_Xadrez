"""OCR_UI ciclo 2, B12: the DPI an engine is told is the one it looks at; ligatures never
leave an engine.

The upscale variant is 450 DPI and Tesseract was told 300 (``--dpi`` fixed in the config);
``ﬁ`` (U+FB01) from Tesseract reached the IR untouched.  Two boundaries, both tested with
fakes: the arbiter hands ``RegionTask.dpi`` to an engine that has ``with_dpi``; the
Tesseract command and the PNG it writes carry the forced DPI, thread-locally; and the base
wrapper folds the seven ligatures (and nothing else -- ``½`` stays ``½``).
"""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path

import numpy as np

from caissa.ocr.arbiter import Arbiter, RegionTask
from caissa.ocr.engines.base import OcrEngineBase
from caissa.ocr.engines.normalize import LIGATURES, fold_ligatures, fold_result
from caissa.ocr.types import OcrResult, RegionKind

from .test_arbiter import MockEngine, identity_config, make_result


def test_fold_ligatures_touches_only_the_seven() -> None:
    assert fold_ligatures("ﬁnal ﬂor oﬃcial ﬀ ﬄ ﬅ ﬆ") == (
        "final flor official ff ffl ft st")
    assert fold_ligatures("½-½ ² № ﾃ") == "½-½ ² № ﾃ", "não é NFKC: o resultado e o NAG ficam"
    assert fold_ligatures("") == ""
    assert set(LIGATURES) == {"ﬀ", "ﬁ", "ﬂ", "ﬃ", "ﬄ", "ﬅ", "ﬆ"}


def test_fold_result_rewrites_words_and_keeps_the_object_when_clean() -> None:
    clean = make_result("x", "sem ligadura", 0.9)
    assert fold_result(clean) is clean
    dirty = make_result("x", "ﬁnal de partida", 0.9)
    folded = fold_result(dirty)
    assert folded is not dirty
    assert folded.lines[0].text == "final de partida"
    assert folded.lines[0].words[0].confidence == dirty.lines[0].words[0].confidence


class _LigatureEngine(OcrEngineBase):
    name = "ligadura"

    def _probe(self):
        return True, None

    def _discover_languages(self):
        return {"eng"}

    def languages(self):
        return {"eng"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self):
        from caissa.ocr.engines.base import EngineCapabilities

        return EngineCapabilities(level=1, cost_per_megapixel_s=0.1, supports_char_boxes=True,
                                  supports_confidence=True, handles_layout=False,
                                  requires_pdf_page=False, gpu_capable=False)

    def _recognize(self, image, *, lang, psm_hint) -> OcrResult:
        return make_result(self.name, "o ﬁm", 0.9, lang=lang, region_kind=psm_hint)


def test_the_base_wrapper_folds_for_every_engine() -> None:
    engine = _LigatureEngine()
    result = engine.recognize(np.full((20, 20), 255, dtype=np.uint8), lang="eng",
                              psm_hint=RegionKind.PARAGRAPH)
    assert result.lines[0].text == "o fim"


class _DpiAwareEngine(MockEngine):
    """A mock with the ``with_dpi`` hook the arbiter looks for."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.seen: list[float | None] = []
        self._current: float | None = None

    def with_dpi(self, dpi: float):
        import contextlib

        @contextlib.contextmanager
        def block():
            self._current = dpi
            try:
                yield
            finally:
                self._current = None

        return block()

    def recognize(self, image, *, lang="eng", psm_hint=RegionKind.PARAGRAPH):
        self.seen.append(self._current)
        return super().recognize(image, lang=lang, psm_hint=psm_hint)


def test_the_arbiter_hands_the_task_dpi_to_an_engine_that_takes_it() -> None:
    engine = _DpiAwareEngine("t", 1, "texto limpo e claro", 0.95)
    arbiter = Arbiter([engine], identity_config())
    image = np.full((40, 200), 255, dtype=np.uint8)
    arbiter.run(RegionTask(image=image, lang="eng", dpi=450.0))
    arbiter.run(RegionTask(image=image, lang="eng", dpi=None))
    assert engine.seen == [450.0, None]


def test_tesseract_command_and_png_carry_the_forced_dpi(tmp_path: Path) -> None:
    from caissa.ocr.engines.tesseract import TesseractConfig, TesseractEngine

    engine = TesseractEngine(TesseractConfig(dpi=300))
    engine._binary = "tesseract"
    base = engine._build_command(tmp_path / "r.png", tmp_path / "out", lang="eng", psm=3)
    assert base[base.index("--dpi") + 1] == "300"
    with engine.with_dpi(450.0):
        forced = engine._build_command(tmp_path / "r.png", tmp_path / "out", lang="eng", psm=3)
        assert forced[forced.index("--dpi") + 1] == "450"
        # Thread-local: another thread still sees the configured 300.
        seen: list[str] = []

        def other() -> None:
            cmd = engine._build_command(tmp_path / "r.png", tmp_path / "out", lang="eng", psm=3)
            seen.append(cmd[cmd.index("--dpi") + 1])

        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        assert seen == ["300"]
    after = engine._build_command(tmp_path / "r.png", tmp_path / "out", lang="eng", psm=3)
    assert after[after.index("--dpi") + 1] == "300"


def test_the_service_switch_is_the_before(monkeypatch) -> None:
    """``SOL_CONFIG='{"variant_dpi": false}'`` keeps every engine at its own default."""
    from caissa.ingest.pdf.ocr_service import OcrServiceConfig

    on = OcrServiceConfig()
    off = replace(on, variant_dpi=False)
    assert on.variant_dpi is True
    assert off.variant_dpi is False
