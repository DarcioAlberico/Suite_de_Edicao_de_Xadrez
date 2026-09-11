"""The audit trail must survive the configuration, not depend on it.

F11 cycle 2 found this by accident: a benchmark started with
``CAISSA_LLM_ENABLED=1`` -- the variable :mod:`caissa.llm.runtime` documents --
reached the model over a thousand times and left nothing on disk. The loader in
``caissa.core.config`` rejects unknown ``CAISSA_*`` names, so the act of turning
the LLM on made ``get_config()`` raise, and the audit log's only fallback at the
time was "keep it in memory and say nothing".

An audit trail that vanishes precisely when the subsystem is in use is worse
than none, because nobody goes looking for a file they believe exists. These
tests pin both halves of the fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.llm.guardrails import AuditLog
from caissa.llm.runtime import DEFAULT_MODEL_TAG, NullRuntime, OllamaRuntime, get_runtime


def test_explicit_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``CAISSA_LLM_AUDIT`` is the escape hatch and takes precedence."""
    target = tmp_path / "trilha.jsonl"
    monkeypatch.setenv("CAISSA_LLM_AUDIT", str(target))
    assert AuditLog(path=None).path == target


def test_a_broken_configuration_does_not_silence_the_trail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``get_config`` raising, the log still lands on disk."""
    monkeypatch.delenv("CAISSA_LLM_AUDIT", raising=False)

    import caissa.core.config as config  # noqa: PLC0415 - patched for this test

    def explode() -> object:
        raise RuntimeError("Opcao desconhecida 'CAISSA_LLM_ENABLED' definida em ambiente")

    monkeypatch.setattr(config, "get_config", explode)
    resolved = AuditLog(path=None).path
    assert resolved is not None
    assert resolved.name == "llm_audit.jsonl"


def test_records_are_kept_in_memory_regardless() -> None:
    """Even with nowhere to write, the process keeps its own trail."""
    log = AuditLog(path=None)
    log._resolved = True  # noqa: SLF001 - keeps the test off the filesystem
    log._path = None  # noqa: SLF001
    from caissa.llm.guardrails import AuditRecord  # noqa: PLC0415

    log.write(
        AuditRecord(
            timestamp="2026-01-01T00:00:00Z",
            task="t",
            prompt_id="extract_stipulation",
            prompt_version=1,
            prompt_sha256="0" * 64,
            model="fake:test",
            decision="accepted",
            detail="",
            latency_ms=1.0,
            prompt_text="",
            system_text="",
            output_text="",
        )
    )
    assert len(log.records()) == 1


@pytest.mark.parametrize(
    "name", ["CAISSA_LLM_ENABLED", "CAISSA_LLM__ENABLED"]
)
def test_both_spellings_enable_the_runtime(name: str) -> None:
    """The config-schema spelling must work, or users break their own config."""
    runtime = get_runtime(env={name: "1"}, force=False)
    assert isinstance(runtime, OllamaRuntime)


def test_no_variable_means_no_runtime() -> None:
    """Absent configuration is still "off", which is the safe default."""
    assert isinstance(get_runtime(env={}), NullRuntime)


@pytest.mark.parametrize(
    "name", ["CAISSA_LLM_MODEL", "CAISSA_LLM__MODEL_ID"]
)
def test_both_model_spellings_select_a_tag(name: str) -> None:
    """Same for the tag override."""
    runtime = get_runtime(env={"CAISSA_LLM_ENABLED": "1", name: "gemma4:12b-it-q4_K_M"})
    assert isinstance(runtime, OllamaRuntime)
    assert runtime.model == "gemma4:12b-it-q4_K_M"
    assert runtime.model != DEFAULT_MODEL_TAG
