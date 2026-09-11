"""Engine adapters and the registry.

The common case on a real machine is that most engines are **not installed**,
and the single most confusing thing this subsystem can do is stay silent about
it.  So most of this file is about the absent path: an engine that cannot run
must report that as a fact, in Portuguese, with the command that fixes it, and
must never raise into the cascade.

The Tesseract tests at the end are the only ones here that read real text, and
they are skipped when the binary is absent.
"""

from __future__ import annotations

import numpy as np
import pytest

from caissa.ocr.engines.base import EngineCapabilities, EngineLevel, OcrEngineBase
from caissa.ocr.engines.registry import (
    EngineRegistry,
    build_default_registry,
    default_registry,
)
from caissa.ocr.quality import character_error_rate
from caissa.ocr.types import RegionKind

from .conftest import (
    render_text_page,
    requires_font,
    requires_tesseract,
)


# --------------------------------------------------------------------------- #
# The default cascade
# --------------------------------------------------------------------------- #


def test_the_default_registry_is_the_spec_cascade():
    """SPEC §7.1 levels 0 to 3.  Level 4 (the VLM) belongs to F11 and is
    deliberately absent rather than stubbed."""
    registry = build_default_registry()
    assert registry.names == ("pdf_text_layer", "tesseract",
                              "paddleocr", "rapidocr", "surya")
    levels = {row.name: row.level for row in registry.describe()}
    assert levels["pdf_text_layer"] == EngineLevel.PDF_TEXT_LAYER
    assert levels["tesseract"] == EngineLevel.TESSERACT
    assert levels["paddleocr"] == levels["rapidocr"] == EngineLevel.PADDLE
    assert levels["surya"] == EngineLevel.SURYA


def test_cascade_order_is_by_level_then_name():
    """Order must be a property of the table, not of import order."""
    registry = EngineRegistry()
    registry.register("zeta", 1, lambda: _Stub("zeta", 1))
    registry.register("alpha", 1, lambda: _Stub("alpha", 1))
    registry.register("early", 0, lambda: _Stub("early", 0))
    assert registry.names == ("early", "alpha", "zeta")


def test_importing_the_package_builds_no_engine():
    """Start-up must not probe the disk or import PaddleOCR.

    Constructing the registry stores factories; nothing is called until an
    engine is asked for.
    """
    calls: list[str] = []
    registry = EngineRegistry()
    registry.register("noisy", 1, lambda: calls.append("built") or _Stub("noisy", 1))
    assert calls == []
    registry.names
    assert calls == []
    registry.get("noisy")
    assert calls == ["built"]


def test_an_engine_is_built_at_most_once():
    calls: list[int] = []

    def factory():
        calls.append(1)
        return _Stub("once", 1)

    registry = EngineRegistry()
    registry.register("once", 1, factory)
    for _ in range(4):
        registry.get("once")
    assert len(calls) == 1


def test_a_failing_factory_is_recorded_and_not_retried(caplog):
    """An engine whose import fails will fail identically on every page.

    Re-raising per region would flood the log and slow a 500-book batch.
    """
    calls: list[int] = []

    def factory():
        calls.append(1)
        raise ImportError("módulo ausente")

    registry = EngineRegistry()
    registry.register("broken", 1, factory, optional=True)
    for _ in range(5):
        assert registry.get("broken") is None
    assert len(calls) == 1

    row = next(r for r in registry.describe() if r.name == "broken")
    assert not row.available
    assert row.error and "módulo ausente" in row.error
    assert "não pôde ser carregado" in (row.reason or "")


def test_invalidate_forgets_the_failure():
    """After the user installs something, re-probing must be possible."""
    state = {"fail": True}

    def factory():
        if state["fail"]:
            raise ImportError("ainda não instalado")
        return _Stub("later", 1)

    registry = EngineRegistry()
    registry.register("later", 1, factory, optional=True)
    assert registry.get("later") is None
    state["fail"] = False
    assert registry.get("later") is None, "sem invalidate não deve tentar de novo"
    registry.invalidate()
    assert registry.get("later") is not None


def test_registering_twice_is_refused_unless_asked():
    registry = EngineRegistry()
    registry.register("x", 1, lambda: _Stub("x", 1))
    with pytest.raises(ValueError, match="já está registrado"):
        registry.register("x", 1, lambda: _Stub("x", 1))
    registry.register("x", 2, lambda: _Stub("x", 2), replace=True)
    assert next(r for r in registry.describe() if r.name == "x").level == 2


def test_unknown_engine_is_none_not_an_exception():
    assert EngineRegistry().get("nao-existe") is None


# --------------------------------------------------------------------------- #
# Graceful degradation — the common case on this machine
# --------------------------------------------------------------------------- #


OPTIONAL = ("paddleocr", "rapidocr", "surya")


@pytest.mark.parametrize("name", OPTIONAL)
def test_an_absent_optional_engine_explains_itself(name):
    """The registry row must be usable as it stands by a confused user."""
    row = next(r for r in default_registry().describe() if r.name == name)
    if row.available:
        pytest.skip(f"{name} está instalado nesta máquina")

    reason = row.reason or ""
    assert reason, name
    assert "pip install" in reason, f"{name}: sem comando de instalação"
    assert "não está instalado" in reason or "não pôde" in reason
    assert row.optional
    assert row.languages == ()
    assert "opcional" in row.describe_pt()


@pytest.mark.parametrize("name", OPTIONAL)
def test_an_absent_engine_never_raises(name):
    """Probing, listing languages and describing must all be safe."""
    engine = default_registry().get(name)
    if engine is None:
        return
    assert engine.available() in (True, False)
    assert isinstance(engine.languages(), set)
    assert isinstance(engine.capabilities(), EngineCapabilities)
    engine.unavailable_reason()


def test_the_gpu_engines_warn_about_adr_0003():
    """ADR-0003: a second CUDA-linked runtime in this process fails silently.

    An install hint that omits this leads the user straight into it, and the
    symptom — everything works but slowly — is nearly undiagnosable.
    """
    rows = {r.name: (r.reason or "") for r in default_registry().describe()}
    for name in ("paddleocr", "rapidocr"):
        if not rows[name]:
            continue
        assert "ADR-0003" in rows[name], name


def test_available_filters_by_language():
    registry = EngineRegistry()
    registry.register("only_eng", 1, lambda: _Stub("only_eng", 1, {"eng"}))
    registry.register("only_rus", 2, lambda: _Stub("only_rus", 2, {"rus"}))
    assert [e.name for e in registry.available(lang="eng")] == ["only_eng"]
    assert [e.name for e in registry.available(lang="rus")] == ["only_rus"]
    assert len(registry.available()) == 2


def test_describe_pt_is_a_readable_table():
    text = default_registry().describe_pt()
    assert "Nível 0" in text and "pdf_text_layer" in text
    assert text.count("\n") >= 4


# --------------------------------------------------------------------------- #
# Tesseract discovery
# --------------------------------------------------------------------------- #


def test_find_tesseract_prefers_an_explicit_path(tmp_path):
    from caissa.ocr.engines.tesseract import find_tesseract

    fake = tmp_path / "tesseract.exe"
    fake.write_bytes(b"")
    assert find_tesseract(fake) == str(fake)


def test_find_tesseract_honours_the_environment(tmp_path, monkeypatch):
    from caissa.ocr.engines.tesseract import find_tesseract

    fake = tmp_path / "tesseract.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("CAISSA_TESSERACT", str(fake))
    assert find_tesseract() == str(fake)


def test_find_tesseract_accepts_the_install_directory(tmp_path, monkeypatch):
    """The variable pointing at the folder rather than the binary is the
    mistake everyone makes once."""
    import os

    from caissa.ocr.engines.tesseract import find_tesseract

    exe = "tesseract.exe" if os.name == "nt" else "tesseract"
    (tmp_path / exe).write_bytes(b"")
    monkeypatch.setenv("CAISSA_TESSERACT", str(tmp_path))
    assert find_tesseract() == str(tmp_path / exe)


def test_tesseract_is_found_off_the_path_on_this_machine():
    """The whole reason this adapter does its own discovery.

    Tesseract 5's official Windows installer does **not** add itself to
    ``PATH``.  An adapter that only checks ``PATH`` — which is what
    ``pytesseract`` does, and what the sibling project's adapter therefore does
    — reports "not installed" to a user who installed it.  On this machine that
    is exactly the situation, and this test pins the difference.
    """
    import shutil

    from caissa.ocr.engines.tesseract import find_tesseract

    found = find_tesseract()
    if found is None:
        pytest.skip("Tesseract não está instalado nesta máquina")
    if shutil.which("tesseract") is not None:
        pytest.skip("Tesseract está no PATH nesta máquina; nada a distinguir")
    assert found, "encontrado fora do PATH, que é o ponto do adaptador"


def test_the_missing_tesseract_message_is_actionable(monkeypatch):
    from caissa.ocr.engines import tesseract as module

    monkeypatch.setattr(module, "find_tesseract", lambda explicit=None: None)
    engine = module.TesseractEngine()
    assert not engine.available()
    reason = engine.unavailable_reason() or ""
    assert "CAISSA_TESSERACT" in reason
    assert "github.com/UB-Mannheim" in reason
    assert engine.languages() == set()


def test_a_missing_tesseract_returns_an_explained_empty_result(monkeypatch):
    """Absent must mean "no text, and here is why", never a traceback."""
    from caissa.ocr.engines import tesseract as module

    monkeypatch.setattr(module, "find_tesseract", lambda explicit=None: None)
    engine = module.TesseractEngine()
    result = engine.recognize(np.full((60, 200), 255, dtype=np.uint8),
                              lang="eng")
    assert result.is_empty
    assert result.warnings
    assert "Tesseract" in " ".join(result.warnings)


# --------------------------------------------------------------------------- #
# Tesseract, actually reading
# --------------------------------------------------------------------------- #


@requires_tesseract
def test_tesseract_reports_its_languages():
    from caissa.ocr.engines.tesseract import TesseractEngine

    engine = TesseractEngine()
    assert engine.available()
    languages = engine.languages()
    assert "eng" in languages
    for wanted in ("por", "deu", "rus", "spa"):
        assert wanted in languages, (
            f"o idioma {wanted} não está instalado; instale o pacote de "
            f"idioma para que o portão F5 possa ser medido")


@requires_tesseract
@requires_font
def test_tesseract_reads_a_clean_synthetic_page():
    """CER against text this test drew, so the reference is exact."""
    from caissa.ocr.engines.tesseract import TesseractEngine

    image, truth = render_text_page()
    result = TesseractEngine().recognize(image, lang="eng",
                                         psm_hint=RegionKind.PARAGRAPH)
    cer = character_error_rate(result.text, truth)
    assert cer < 0.01, f"CER {cer:.4f} numa página limpa gerada aqui"
    assert result.mean_confidence > 0.85


@requires_tesseract
@requires_font
def test_tesseract_returns_character_boxes():
    """``tsv`` and ``hocr`` in one invocation — the reason this adapter does
    not use ``pytesseract``, which would need two runs."""
    from caissa.ocr.engines.tesseract import TesseractEngine

    image, _ = render_text_page()
    result = TesseractEngine().recognize(image, lang="eng",
                                         psm_hint=RegionKind.PARAGRAPH)
    assert result.words
    with_boxes = [w for w in result.words if w.has_char_boxes]
    assert len(with_boxes) > 0.9 * len(result.words), (
        f"apenas {len(with_boxes)}/{len(result.words)} palavras com caixas "
        f"de caractere")
    word = with_boxes[0]
    assert len(word.chars) == len(word.text)
    assert all(not c.inherited_confidence for c in word.chars), (
        "as caixas de caractere do Tesseract são medidas, não interpoladas")


@requires_tesseract
@requires_font
def test_tesseract_is_deterministic():
    from caissa.ocr.engines.tesseract import TesseractEngine

    image, _ = render_text_page()
    engine = TesseractEngine()
    first = engine.recognize(image, lang="eng", psm_hint=RegionKind.PARAGRAPH)
    second = engine.recognize(image, lang="eng", psm_hint=RegionKind.PARAGRAPH)
    assert first.text == second.text
    assert [w.confidence for w in first.words] == \
           [w.confidence for w in second.words]


@requires_tesseract
def test_tesseract_on_a_blank_region_returns_empty_not_garbage():
    from caissa.ocr.engines.tesseract import TesseractEngine

    blank = np.full((120, 400), 255, dtype=np.uint8)
    result = TesseractEngine().recognize(blank, lang="eng",
                                         psm_hint=RegionKind.PARAGRAPH)
    assert result.is_empty or not result.text.strip()


@requires_tesseract
def test_psm_follows_the_region_kind():
    from caissa.ocr.engines.tesseract import PSM_BY_REGION

    assert PSM_BY_REGION[RegionKind.SINGLE_LINE] == 7
    assert PSM_BY_REGION[RegionKind.SINGLE_WORD] == 8
    assert PSM_BY_REGION[RegionKind.PARAGRAPH] == 6
    assert set(PSM_BY_REGION) == set(RegionKind), (
        "toda espécie de região precisa de um modo de segmentação")


# --------------------------------------------------------------------------- #
# Test double
# --------------------------------------------------------------------------- #


class _Stub(OcrEngineBase):
    def __init__(self, name: str, level: int,
                 languages: set[str] | None = None) -> None:
        # ``super().__init__`` resets ``_languages`` to None, so the base has
        # to run first and the double must keep its own set under a name the
        # base does not own.
        super().__init__()
        self.name = name
        self._level = level
        self._stub_languages = languages or {"eng", "por"}

    def _probe(self):
        return True, None

    def _discover_languages(self):
        return set(self._stub_languages)

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(level=self._level, cost_per_megapixel_s=0.1,
                                  supports_char_boxes=False,
                                  supports_confidence=True)

    def _recognize(self, image, *, lang, psm_hint):
        from caissa.ocr.types import empty_result
        return empty_result(self.name, lang, region_kind=psm_hint)
