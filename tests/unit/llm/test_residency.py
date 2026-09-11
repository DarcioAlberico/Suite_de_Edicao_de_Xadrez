"""VRAM discipline: the LLM plays by ADR-0004's rules, including being evicted first.

These tests drive the real ``ModelResidencyManager`` with an injected device and
a fake runtime, so they need neither a GPU nor Ollama.
"""

from __future__ import annotations

import pytest

from caissa.llm.residency import (
    LLM_MODEL_NAME,
    LLM_PRIORITY,
    MEASURED_VISION_VRAM_BYTES,
    MEASURED_VRAM_BYTES,
    QUALITY_EXCLUSIVE_GROUP,
    llm_model_spec,
    register_llm,
    unregister_llm,
)

from .conftest import FakeRuntime

residency = pytest.importorskip("caissa.vision.runtime.residency")


@pytest.fixture
def manager():
    """A manager pinned to a fake CUDA device with a 7.0 GiB budget (ADR-0004)."""
    made = residency.ModelResidencyManager(
        budget_bytes=residency.gigabytes(7.0),
        device="cuda:0",
        vram_probe=lambda: (8 * 1024**3, 8 * 1024**3),
        empty_cache=lambda: None,
    )
    yield made
    made.unload_all(force=True)


def _vision_spec(name: str, gib: float, *, priority: int = 0, pinned: bool = False):
    """Stand-in for a model the vision front will register."""
    return residency.ModelSpec(
        name=name,
        vram_bytes=residency.gigabytes(gib),
        loader=lambda device: f"{name}@{device}",
        priority=priority,
        pinned=pinned,
    )


# --------------------------------------------------------------------------- #
# Declaration
# --------------------------------------------------------------------------- #


def test_declared_cost_is_the_measured_one():
    """Three figures have been claimed; the spec carries the measured one.

    ADR-0005 estimated 3.0-3.5 GiB. F11 cycle 1 measured 4271 MiB against a
    busier idle baseline. F11 cycle 2 measured **6190 MiB** against a 1016 MiB
    idle desktop, with both paths exercised. A budget manager fed an optimistic
    number does not save memory; it moves the failure somewhere worse.
    """
    spec = llm_model_spec(FakeRuntime())
    assert spec.vram_bytes == MEASURED_VRAM_BYTES
    assert 6.0 < spec.vram_bytes / 1024**3 < 6.1


def test_llm_is_the_first_eviction_candidate():
    """ADR-0004: highest priority, never pinned."""
    spec = llm_model_spec(FakeRuntime())
    assert spec.priority == LLM_PRIORITY
    assert spec.pinned is False
    assert spec.priority > _vision_spec("detector", 1.0, priority=10).priority


def test_llm_never_falls_back_to_cpu():
    """CPU inference for a 7.5B multimodal model is minutes per diagram; declining is faster."""
    assert llm_model_spec(FakeRuntime()).allow_cpu_fallback is False


def test_quality_mode_declares_an_exclusive_group():
    """Gemma 4 12B needs ~7.5 GiB and cannot co-reside; it must be serialised."""
    spec = llm_model_spec(
        FakeRuntime(),
        name="llm-gemma4-12b",
        vram_bytes=residency.gigabytes(7.5),
        exclusive_group=QUALITY_EXCLUSIVE_GROUP,
    )
    assert spec.exclusive_group == QUALITY_EXCLUSIVE_GROUP


# --------------------------------------------------------------------------- #
# Lifecycle through the manager
# --------------------------------------------------------------------------- #


def test_registration_and_lazy_load(manager):
    """Nothing loads until first use (ADR-0004)."""
    runtime = FakeRuntime()
    assert register_llm(manager, runtime=runtime) is True
    assert LLM_MODEL_NAME in manager.registered()
    assert manager.is_resident(LLM_MODEL_NAME) is False
    assert runtime.load_calls == 0

    with manager.acquire(LLM_MODEL_NAME) as lease:
        assert lease.model is runtime
        assert runtime.load_calls == 1
        assert manager.is_resident(LLM_MODEL_NAME) is True


def test_eviction_really_unloads_the_weights(manager):
    """The weights live in another process; eviction must reach them."""
    runtime = FakeRuntime()
    register_llm(manager, runtime=runtime)
    manager.preload(LLM_MODEL_NAME)
    assert runtime.unload_calls == 0

    assert unregister_llm(manager) is True
    assert runtime.unload_calls == 1
    assert manager.is_resident(LLM_MODEL_NAME) is False


def test_llm_is_evicted_before_the_vision_models(manager):
    """The scenario ADR-0004 exists for: the budget is full and something must go."""
    register_llm(manager, runtime=FakeRuntime())  # 6.04 GiB, measured
    manager.register(_vision_spec("detector", 0.5, priority=10))
    manager.preload(LLM_MODEL_NAME)
    manager.preload("detector")
    assert manager.is_resident(LLM_MODEL_NAME) is True

    # 3.0 GiB more does not fit next to 6.04 + 0.5 under a 7.0 cap.
    manager.register(_vision_spec("classifier", 3.0, priority=10))
    manager.preload("classifier")

    assert manager.is_resident(LLM_MODEL_NAME) is False, "o LLM deveria sair primeiro"
    assert manager.is_resident("detector") is True
    assert manager.is_resident("classifier") is True


def test_the_measured_pair_does_not_fit_and_the_budget_says_so(manager):
    """The whole F11 cycle-2 VRAM finding, as an assertion.

    Measured on the reference machine: the LLM costs 6190 MiB and the
    recognition pipeline at six CUDA workers costs 6345 MiB, both above the same
    idle desktop. Together that is 12 535 MiB on an 8151 MiB card. With honest
    declarations the manager reaches the same conclusion for free -- it never
    lets both be resident -- and evicts the LLM, because that is what
    ``LLM_PRIORITY`` is for.
    """
    register_llm(manager, runtime=FakeRuntime())
    manager.register(
        _vision_spec("pipeline", MEASURED_VISION_VRAM_BYTES / 1024**3, priority=10)
    )
    manager.preload(LLM_MODEL_NAME)
    manager.preload("pipeline")

    assert manager.is_resident("pipeline") is True
    assert manager.is_resident(LLM_MODEL_NAME) is False


def test_a_held_lease_protects_the_llm_from_eviction(manager):
    """A diagram being verified right now must not lose its model mid-call."""
    register_llm(manager, runtime=FakeRuntime())
    manager.register(_vision_spec("classifier", 3.0))
    with manager.acquire(LLM_MODEL_NAME):
        with pytest.raises(residency.ResidencyError):
            manager.unload(LLM_MODEL_NAME)
        assert manager.is_resident(LLM_MODEL_NAME) is True


def test_budget_is_never_exceeded(manager):
    """The invariant the whole class exists to hold."""
    register_llm(manager, runtime=FakeRuntime())
    manager.register(_vision_spec("detector", 1.0))
    manager.register(_vision_spec("ocr", 1.5))
    manager.register(_vision_spec("classifier", 2.0))
    for name in (LLM_MODEL_NAME, "detector", "ocr", "classifier"):
        manager.preload(name)
        report = manager.budget_report()
        assert report.reserved_bytes <= report.budget_bytes


def test_llm_reports_itself_in_the_budget_panel(manager):
    register_llm(manager, runtime=FakeRuntime())
    manager.preload(LLM_MODEL_NAME)
    row = next(r for r in manager.budget_report().residents if r.name == LLM_MODEL_NAME)
    assert row.vram_bytes == MEASURED_VRAM_BYTES
    assert "despejo" in row.description


# --------------------------------------------------------------------------- #
# Degradation
# --------------------------------------------------------------------------- #


def test_registration_failure_is_not_fatal(monkeypatch):
    """An optional subsystem must not be able to abort startup."""

    class Rejecting:
        def register(self, *args, **kwargs):  # noqa: ANN002, ANN003, ARG002
            raise RuntimeError("orcamento indisponivel")

    assert register_llm(Rejecting(), runtime=FakeRuntime()) is False


def test_unregister_of_an_absent_model_is_false(manager):
    register_llm(manager, runtime=FakeRuntime())
    assert unregister_llm(manager) is False


def test_missing_residency_manager_degrades(monkeypatch):
    """If the vision front is not installed, the LLM still runs -- just unbudgeted."""
    import builtins  # noqa: PLC0415 - local by design

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):  # noqa: ANN002, ANN003
        if "residency" in name:
            raise ImportError("caissa.vision nao instalado")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    assert register_llm(runtime=FakeRuntime()) is False
