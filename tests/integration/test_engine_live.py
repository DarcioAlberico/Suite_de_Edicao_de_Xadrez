"""The optional engines, with the real package — not a fake in ``sys.modules``.

``tests/unit/ocr/test_optional_engines.py`` is the *contract*: it injects fake
modules and proves the adapters honour the interface.  It never skips, so with
the real engine installed it says exactly what it said without it — which is
the blind spot the OCR_UI_ROADMAP passo 1 names (anti-padrão 6): a green
contract is no evidence that the installed engine reads anything.

This file is the other half.  Each test skips unless the engine's real package
imports, renders a line of chess prose the way the corpus prints it, and
demands text back with a confidence the arbiter could score.  It is marked
``slow`` (model load is seconds) and lives with the integration tests because
it touches the machine, not the code.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from caissa.ocr.types import RegionKind

pytestmark = pytest.mark.slow

LINE = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 White stands better."
CYRILLIC_LINE = "Комбинация начинается жертвой слона, и белые выигрывают."


def _rendered_line(text: str = LINE) -> np.ndarray:
    image = Image.new("L", (1100, 120), 255)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/times.ttf", 40)
    except OSError:  # not Windows, or no Times: the default bitmap font still reads
        font = ImageFont.load_default()
    draw.text((20, 30), text, font=font, fill=0)
    return np.asarray(image, dtype=np.uint8)


def _rapidocr_installed() -> None:
    try:
        pytest.importorskip("rapidocr")
    except pytest.skip.Exception:
        pytest.importorskip("rapidocr_onnxruntime")


def _words(text: str) -> set[str]:
    return {token.strip(".,") for token in text.split()}


def test_rapidocr_reads_a_printed_line_with_the_real_package() -> None:
    _rapidocr_installed()
    from caissa.ocr.engines.rapidocr import RapidOcrEngine

    engine = RapidOcrEngine()
    assert engine.available(), engine.unavailable_reason

    result = engine.recognize(_rendered_line(), lang="eng", psm_hint=RegionKind.PARAGRAPH)

    assert result.engine == "rapidocr"
    assert result.lines, result.warnings
    # A real recogniser, not a stub: most of the tokens survive verbatim and the
    # score is one the arbiter can calibrate on.
    got = _words(result.text)
    expected = _words(LINE)
    assert len(got & expected) >= len(expected) - 2, result.text
    assert all(0.0 < word.confidence <= 1.0 for word in result.words)


def test_rapidocr_3x_reads_cyrillic_with_its_own_recogniser() -> None:
    """The 1.x package cannot (Chinese model only); 3.x switches models by script."""
    pytest.importorskip("rapidocr")
    from caissa.ocr.engines.rapidocr import RapidOcrEngine

    engine = RapidOcrEngine()
    assert engine.available(), engine.unavailable_reason
    assert engine.supports_language("rus")

    result = engine.recognize(_rendered_line(CYRILLIC_LINE), lang="rus+eng",
                              psm_hint=RegionKind.PARAGRAPH)

    assert result.meta["module"] == "rapidocr"
    assert result.meta["script"] == "eslav"
    got = _words(result.text)
    assert len(got & _words(CYRILLIC_LINE)) >= 4, result.text


def test_rapidocr_is_seen_by_the_registry_and_gated_by_the_service() -> None:
    """Installed ≠ used: the registry lists it, the service adds it only when named."""
    _rapidocr_installed()
    from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig
    from caissa.ocr.engines.registry import default_registry

    assert "rapidocr" in [e.name for e in default_registry().available(lang="eng")]

    silent = OcrService(config=OcrServiceConfig(secondary_engines=()), lang="eng")
    assert "rapidocr" not in [e.name for e in silent.engines_for("eng")]

    named = OcrService(config=OcrServiceConfig(secondary_engines=("rapidocr",)), lang="eng")
    assert "rapidocr" in [e.name for e in named.engines_for("eng")]
