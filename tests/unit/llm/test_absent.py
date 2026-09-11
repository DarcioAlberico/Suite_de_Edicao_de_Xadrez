"""The most important test file in this front: everything works with no LLM.

The LLM is optional (ADR-0005). If any of these fail, the application has
acquired a hidden dependency on a background service and a 6 GB download, and
the acceptance gate for F11 is not met -- regardless of how well the model
performs when it is present.
"""

from __future__ import annotations

import pytest

from caissa.llm import is_available
from caissa.llm.runtime import (
    LlmUnavailableError,
    NullRuntime,
    OllamaRuntime,
    get_runtime,
    reset_runtime,
)
from caissa.llm.tasks import (
    caption_for_diagram,
    extract_stipulation,
    repair_ocr_region,
    translate_notation_prose,
    verify_diagram,
)

from .conftest import GOOD_FEN, PNG_BYTES, FakeRuntime


@pytest.fixture(autouse=True)
def _clean_runtime():
    reset_runtime()
    yield
    reset_runtime()


# --------------------------------------------------------------------------- #
# The default configuration has no LLM at all
# --------------------------------------------------------------------------- #


def test_default_runtime_is_null():
    """`llm.enabled` defaults to false, so the default runtime serves nothing."""
    runtime = get_runtime(env={})
    assert isinstance(runtime, NullRuntime)
    assert runtime.is_available() is False
    assert runtime.info().available is False


def test_is_available_never_raises(monkeypatch):
    """`is_available` swallows a broken configuration rather than propagating it."""

    def explode() -> object:
        raise RuntimeError("configuracao quebrada")

    monkeypatch.setattr("caissa.llm.get_runtime", explode)
    assert is_available() is False


def test_null_runtime_raises_only_when_actually_called():
    """Inspection is safe; generation is the only thing that raises."""
    runtime = NullRuntime("sem modelo")
    assert runtime.is_available() is False
    runtime.unload()  # must not raise: cleanup paths call this blindly
    with pytest.raises(LlmUnavailableError):
        runtime.generate.__call__  # noqa: B018 - attribute access is safe
        runtime.generate(None)  # type: ignore[arg-type]


def test_unreachable_service_is_not_an_error():
    """A dead Ollama port reports unavailable instead of raising."""
    runtime = OllamaRuntime("gemma4:e4b-it-qat", host="http://127.0.0.1:1")
    info = runtime.info(refresh=True)
    assert info.available is False
    assert "inacessivel" in info.detail or "nao instalado" in info.detail


# --------------------------------------------------------------------------- #
# Every task degrades
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_verify_diagram_degrades(runtime):
    """Verification abstains, and abstention must not read as agreement."""
    result = verify_diagram(PNG_BYTES, GOOD_FEN, "Diagrama 1", runtime=runtime)
    assert result.used_llm is False
    assert result.verdict == "uncertain"
    assert result.confidence == 0.0
    assert result.disagrees is False


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_verify_diagram_absent_changes_nothing(runtime):
    """With no LLM, a vision confidence comes out exactly as it went in."""
    result = verify_diagram(PNG_BYTES, GOOD_FEN, runtime=runtime)
    for confidence in (0.05, 0.5, 0.899, 0.9, 1.0):
        decision = result.decide(confidence)
        assert decision.adjusted == confidence
        assert decision.flagged is False
        assert decision.changed is False


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_stipulation_still_works_from_rules(runtime):
    """The deterministic matcher carries the task on its own."""
    stipulation = extract_stipulation("Diagrama 12. Mate em 2.", runtime=runtime)
    assert stipulation is not None
    assert stipulation.kind == "mate"
    assert stipulation.moves == 2
    assert stipulation.diagram_number == 12
    assert stipulation.source == "rules"


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_stipulation_returns_none_when_nothing_matches(runtime):
    """No stipulation extracted is `None`, never a guess."""
    assert extract_stipulation("Uma frase qualquer sobre o clima.", runtime=runtime) is None


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_repair_ocr_returns_none(runtime):
    """Level 4 of the OCR cascade simply does not fire."""
    assert repair_ocr_region(PNG_BYTES, "text0 wjth err0rs", "pt", runtime=runtime) is None


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_caption_always_returns_a_string(runtime):
    """Captions have a deterministic fallback built from the FEN alone."""
    caption = caption_for_diagram(GOOD_FEN, "contexto", runtime=runtime, language="pt")
    assert caption == "Brancas jogam"
    assert caption_for_diagram(
        "8/8/4k3/8/8/4K3/4P3/8 b - - 0 1", runtime=runtime, language="en"
    ) == "Black to move"


@pytest.mark.parametrize("runtime", [NullRuntime(), FakeRuntime(available=False)])
def test_translation_returns_source_unchanged(runtime):
    """An untranslated paragraph is honest; a damaged one is not."""
    source = "As brancas jogam 1.e4 e5 2.Cf3 e obtem vantagem."
    assert translate_notation_prose(source, "pt", "en", runtime=runtime) == source


def test_no_task_touches_the_network_without_a_runtime(monkeypatch):
    """A missing LLM must never reach urlopen -- not even to find out it is missing."""

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        raise AssertionError("nenhuma chamada de rede e permitida sem LLM")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    runtime = NullRuntime()
    assert verify_diagram(PNG_BYTES, GOOD_FEN, runtime=runtime).used_llm is False
    assert repair_ocr_region(PNG_BYTES, "x", runtime=runtime) is None
    assert caption_for_diagram(GOOD_FEN, runtime=runtime)
    assert extract_stipulation("Mate em 2", runtime=runtime) is not None
