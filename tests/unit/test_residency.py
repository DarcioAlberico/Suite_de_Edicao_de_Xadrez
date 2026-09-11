"""Tests for the ModelResidencyManager (ADR-0004).

Nothing here needs a GPU: the manager takes the device string and the VRAM probe
as constructor arguments precisely so that budget arithmetic, eviction order,
CPU fallback and the serialised queue can be exercised deterministically.
"""

from __future__ import annotations

import threading
import time

import pytest

from caissa.core.config import load_config, set_config
from caissa.vision.runtime.residency import (
    ModelLease,
    ModelNotRegisteredError,
    ModelResidencyManager,
    ModelSpec,
    ResidencyError,
    ResidencyTimeoutError,
    VramBudgetExceededError,
    VramFallbackWarning,
    get_residency_manager,
    gigabytes,
    megabytes,
)

GB = 1024**3


class Recorder:
    """Loader factory that records every load and unload, thread-safely."""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.loads: list[tuple[str, str]] = []
        self.unloads: list[str] = []
        self._lock = threading.Lock()

    def loader(self, name: str):
        def load(device: str) -> str:
            if self.delay:
                time.sleep(self.delay)
            with self._lock:
                self.loads.append((name, device))
            return f"{name}@{device}"

        return load

    def unloader(self, name: str):
        def unload(model: object) -> None:  # noqa: ARG001
            with self._lock:
                self.unloads.append(name)

        return unload

    def load_count(self, name: str) -> int:
        with self._lock:
            return sum(1 for entry, _ in self.loads if entry == name)


def make_manager(
    *, budget_gb: float = 8.0, device: str = "cuda:0", **kwargs
) -> tuple[ModelResidencyManager, Recorder]:
    recorder = Recorder(delay=kwargs.pop("delay", 0.0))
    manager = ModelResidencyManager(
        budget_bytes=gigabytes(budget_gb),
        device=device,
        empty_cache=lambda: None,
        vram_probe=lambda: (0, 0),
        **kwargs,
    )
    return manager, recorder


def spec(recorder: Recorder, name: str, gb: float, **kwargs) -> ModelSpec:
    return ModelSpec(
        name=name,
        vram_bytes=gigabytes(gb),
        loader=recorder.loader(name),
        unloader=recorder.unloader(name),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Registry and lazy loading
# --------------------------------------------------------------------------- #


def test_units_helpers():
    assert gigabytes(1) == 1024**3
    assert megabytes(1.5) == int(1.5 * 1024**2)


def test_registration_does_not_load_anything():
    manager, recorder = make_manager()
    manager.register(spec(recorder, "detector", 1.0))
    assert manager.registered() == ("detector",)
    assert not manager.is_resident("detector")
    assert recorder.loads == []


def test_first_acquire_loads_and_second_reuses():
    manager, recorder = make_manager()
    manager.register(spec(recorder, "detector", 1.0))

    with manager.acquire("detector") as lease:
        assert isinstance(lease, ModelLease)
        assert lease.model == "detector@cuda:0"
        assert lease.device == "cuda:0"
        assert lease.is_cuda
        assert lease.on_cpu_fallback is False

    with manager.acquire("detector") as lease:
        assert lease.model == "detector@cuda:0"

    assert recorder.load_count("detector") == 1
    assert manager.is_resident("detector")


def test_acquiring_an_unregistered_model_lists_the_known_ones():
    manager, recorder = make_manager()
    manager.register(spec(recorder, "detector", 1.0))
    with pytest.raises(ModelNotRegisteredError, match="detector"), manager.acquire("classificador"):
        pass


def test_reregistration_of_a_resident_model_is_refused():
    manager, recorder = make_manager()
    manager.register(spec(recorder, "detector", 1.0))
    manager.preload("detector")
    with pytest.raises(ResidencyError, match="carregado"):
        manager.register(spec(recorder, "detector", 2.0))


def test_loader_failure_leaves_no_reservation():
    manager, _ = make_manager(budget_gb=4.0)

    def boom(device: str) -> object:  # noqa: ARG001
        raise RuntimeError("pesos corrompidos")

    manager.register(ModelSpec(name="ruim", vram_bytes=gigabytes(2.0), loader=boom))
    with pytest.raises(RuntimeError, match="pesos corrompidos"), manager.acquire("ruim"):
        pass
    assert not manager.is_resident("ruim")
    assert manager.reserved_bytes == 0


# --------------------------------------------------------------------------- #
# Budget enforcement and eviction order
# --------------------------------------------------------------------------- #


def test_budget_is_never_exceeded():
    manager, recorder = make_manager(budget_gb=6.0)
    for name in ("a", "b", "c", "d"):
        manager.register(spec(recorder, name, 2.0))
    for name in ("a", "b", "c", "d"):
        manager.preload(name)
        assert manager.reserved_bytes <= manager.budget_bytes

    assert manager.reserved_bytes == gigabytes(6.0)


def test_eviction_is_least_recently_used():
    manager, recorder = make_manager(budget_gb=6.0)
    for name in ("a", "b", "c"):
        manager.register(spec(recorder, name, 2.0))
        manager.preload(name)

    # Touch "a" so that "b" becomes the least recently used.
    manager.preload("a")

    manager.register(spec(recorder, "d", 2.0))
    manager.preload("d")

    assert recorder.unloads == ["b"]
    assert set(manager.registered()) == {"a", "b", "c", "d"}
    assert manager.is_resident("a")
    assert not manager.is_resident("b")
    assert manager.is_resident("c")
    assert manager.is_resident("d")


def test_high_priority_models_are_evicted_first_even_when_recently_used():
    manager, recorder = make_manager(budget_gb=6.0)
    manager.register(spec(recorder, "detector", 2.0))
    manager.register(spec(recorder, "classificador", 2.0))
    manager.register(spec(recorder, "llm", 2.0, priority=100))
    for name in ("detector", "classificador", "llm"):
        manager.preload(name)

    manager.register(spec(recorder, "ocr", 2.0))
    manager.preload("ocr")

    # The LLM was the most recently used, but ADR-0004 makes it the first
    # candidate for eviction.
    assert recorder.unloads == ["llm"]


def test_pinned_models_are_never_evicted_automatically():
    manager, recorder = make_manager(budget_gb=4.0)
    manager.register(spec(recorder, "classificador", 2.0, pinned=True))
    manager.register(spec(recorder, "detector", 2.0))
    manager.preload("classificador")
    manager.preload("detector")

    manager.register(spec(recorder, "ocr", 2.0))
    manager.preload("ocr")

    assert manager.is_resident("classificador")
    assert recorder.unloads == ["detector"]


def test_leased_models_are_not_evicted_and_the_waiter_proceeds_after_release():
    manager, recorder = make_manager(budget_gb=4.0)
    manager.register(spec(recorder, "grande", 4.0))
    manager.register(spec(recorder, "outro", 4.0))

    started = threading.Event()
    hold_seconds = 0.30

    def borrower() -> None:
        with manager.acquire("grande"):
            started.set()
            time.sleep(hold_seconds)

    thread = threading.Thread(target=borrower)
    thread.start()
    assert started.wait(2.0)

    waited_from = time.monotonic()
    with manager.acquire("outro", timeout=5.0) as lease:
        elapsed = time.monotonic() - waited_from
        # Reachable only after "grande" was released, then evicted to make room.
        assert elapsed >= hold_seconds * 0.6
        assert lease.device == "cuda:0"
        assert not manager.is_resident("grande")

    thread.join(5.0)
    assert not thread.is_alive()
    assert recorder.unloads == ["grande"]


def test_waiting_for_vram_times_out_with_a_useful_message():
    manager, recorder = make_manager(budget_gb=4.0)
    manager.register(spec(recorder, "grande", 4.0))
    manager.register(spec(recorder, "outro", 4.0))

    with (
        manager.acquire("grande"),
        pytest.raises(ResidencyTimeoutError, match="grande"),
        manager.acquire("outro", timeout=0.2),
    ):
        pass


def test_set_budget_shrink_evicts_immediately():
    manager, recorder = make_manager(budget_gb=6.0)
    for name in ("a", "b", "c"):
        manager.register(spec(recorder, name, 2.0))
        manager.preload(name)

    manager.set_budget(gigabytes(2.0))
    assert manager.reserved_bytes <= gigabytes(2.0)
    assert recorder.unloads == ["a", "b"]


def test_unload_refuses_while_leased_and_force_overrides():
    manager, recorder = make_manager()
    manager.register(spec(recorder, "detector", 1.0))
    with manager.acquire("detector"):
        with pytest.raises(ResidencyError, match="em uso"):
            manager.unload("detector")
        assert manager.unload("detector", force=True) is True
    assert manager.unload("detector") is False


def test_unload_all_drops_everything():
    manager, recorder = make_manager()
    for name in ("a", "b"):
        manager.register(spec(recorder, name, 1.0))
        manager.preload(name)
    assert manager.unload_all() == 2
    assert manager.reserved_bytes == 0


# --------------------------------------------------------------------------- #
# CPU fallback
# --------------------------------------------------------------------------- #


def borrow_placement(manager: ModelResidencyManager, name: str) -> tuple[str, bool, bool]:
    """Acquire, snapshot where the model landed, release."""
    with manager.acquire(name) as lease:
        return lease.device, lease.on_cpu_fallback, lease.is_cuda


def test_model_larger_than_the_budget_falls_back_to_cpu_with_a_warning():
    manager, recorder = make_manager(budget_gb=4.0)
    manager.register(spec(recorder, "llm12b", 7.5))

    with pytest.warns(VramFallbackWarning, match="llm12b"):
        placement = borrow_placement(manager, "llm12b")

    assert placement == ("cpu", True, False)

    assert manager.reserved_bytes == 0
    assert manager.budget_report().cpu_fallbacks == 1


def test_cpu_fallback_can_be_refused_per_model():
    manager, recorder = make_manager(budget_gb=4.0)
    manager.register(spec(recorder, "llm12b", 7.5, allow_cpu_fallback=False))
    with pytest.raises(VramBudgetExceededError, match="llm12b"), manager.acquire("llm12b"):
        pass


def test_cpu_fallback_can_be_refused_globally():
    manager, recorder = make_manager(budget_gb=4.0, allow_cpu_fallback=False)
    manager.register(spec(recorder, "llm12b", 7.5))
    with pytest.raises(VramBudgetExceededError), manager.acquire("llm12b"):
        pass


def test_on_a_cpu_only_machine_nothing_is_reserved():
    manager, recorder = make_manager(budget_gb=4.0, device="cpu")
    manager.register(spec(recorder, "detector", 3.0))
    with manager.acquire("detector") as lease:
        assert lease.device == "cpu"
        assert lease.on_cpu_fallback is False
    assert manager.reserved_bytes == 0


# --------------------------------------------------------------------------- #
# Serialised queue for models that cannot co-reside
# --------------------------------------------------------------------------- #


def test_exclusive_group_serialises_use():
    manager, recorder = make_manager(budget_gb=64.0)
    for name in ("llm-e4b", "llm-12b"):
        manager.register(spec(recorder, name, 4.0, exclusive_group="llm"))

    concurrent = 0
    peak = 0
    lock = threading.Lock()
    errors: list[BaseException] = []
    barrier = threading.Barrier(4)

    def worker(name: str) -> None:
        nonlocal concurrent, peak
        try:
            barrier.wait(5.0)
            with manager.acquire(name, timeout=10.0):
                with lock:
                    concurrent += 1
                    peak = max(peak, concurrent)
                time.sleep(0.05)
                with lock:
                    concurrent -= 1
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(name,))
        for name in ("llm-e4b", "llm-12b", "llm-e4b", "llm-12b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15.0)

    assert errors == []
    assert peak == 1, "modelos do mesmo grupo exclusivo nao podem ser usados ao mesmo tempo"


def test_models_outside_an_exclusive_group_run_in_parallel():
    manager, recorder = make_manager(budget_gb=64.0)
    for name in ("detector", "classificador"):
        manager.register(spec(recorder, name, 1.0))

    peak = 0
    concurrent = 0
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def worker(name: str) -> None:
        nonlocal concurrent, peak
        barrier.wait(5.0)
        with manager.acquire(name, timeout=10.0):
            with lock:
                concurrent += 1
                peak = max(peak, concurrent)
            time.sleep(0.10)
            with lock:
                concurrent -= 1

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("detector", "classificador")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15.0)

    assert peak == 2


def test_nested_acquire_of_the_same_exclusive_model_is_reentrant():
    manager, recorder = make_manager(budget_gb=64.0)
    manager.register(spec(recorder, "llm", 1.0, exclusive_group="llm"))
    with manager.acquire("llm", timeout=1.0), manager.acquire("llm", timeout=1.0) as inner:
        assert inner.model == "llm@cuda:0"
    assert recorder.load_count("llm") == 1


def test_nested_acquire_of_a_sibling_exclusive_model_raises_instead_of_deadlocking():
    manager, recorder = make_manager(budget_gb=64.0)
    manager.register(spec(recorder, "llm-a", 1.0, exclusive_group="llm"))
    manager.register(spec(recorder, "llm-b", 1.0, exclusive_group="llm"))
    with (
        manager.acquire("llm-a", timeout=1.0),
        pytest.raises(ResidencyError, match="Impasse"),
        manager.acquire("llm-b", timeout=1.0),
    ):
        pass


# --------------------------------------------------------------------------- #
# Thread safety
# --------------------------------------------------------------------------- #


def test_concurrent_acquire_of_the_same_model_loads_it_once():
    manager, recorder = make_manager(budget_gb=8.0, delay=0.15)
    manager.register(spec(recorder, "classificador", 1.0))

    workers = 12
    barrier = threading.Barrier(workers)
    seen: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            barrier.wait(10.0)
            with manager.acquire("classificador", timeout=15.0) as lease, lock:
                seen.append(lease.model)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30.0)

    assert errors == []
    assert len(seen) == workers
    assert set(seen) == {"classificador@cuda:0"}
    assert recorder.load_count("classificador") == 1


def test_concurrent_churn_never_breaches_the_budget():
    manager, recorder = make_manager(budget_gb=4.0)
    names = [f"m{i}" for i in range(6)]
    for name in names:
        manager.register(spec(recorder, name, 1.0))

    breaches: list[int] = []
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            for step in range(25):
                name = names[(index + step) % len(names)]
                with manager.acquire(name, timeout=20.0):
                    reserved = manager.reserved_bytes
                    if reserved > manager.budget_bytes:
                        breaches.append(reserved)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60.0)

    assert errors == []
    assert breaches == []
    assert manager.reserved_bytes <= manager.budget_bytes


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def test_budget_report_describes_the_state():
    manager, recorder = make_manager(budget_gb=6.0)
    manager.register(spec(recorder, "detector", 2.0, description="Detector de tabuleiro"))
    manager.register(spec(recorder, "classificador", 1.0, pinned=True))
    manager.preload("detector")

    with manager.acquire("classificador"):
        report = manager.budget_report()

    assert report.device == "cuda:0"
    assert report.budget_bytes == gigabytes(6.0)
    assert report.reserved_bytes == gigabytes(3.0)
    assert report.free_bytes == gigabytes(3.0)
    assert report.utilisation == pytest.approx(0.5)
    assert report.registered == ("detector", "classificador")
    assert [r.name for r in report.residents] == ["classificador", "detector"]

    by_name = {r.name: r for r in report.residents}
    assert by_name["classificador"].in_use is True
    assert by_name["classificador"].pinned is True
    assert by_name["detector"].in_use is False
    assert by_name["detector"].description == "Detector de tabuleiro"
    assert report.loads == 2

    payload = report.as_dict()
    assert payload["free_bytes"] == gigabytes(3.0)
    assert payload["residents"][0]["vram_gb"] == 1.0

    text = report.to_text()
    assert "Orcamento de VRAM" in text
    assert "detector" in text
    assert "Cargas: 2" in text


def test_budget_report_counts_evictions_and_waits():
    manager, recorder = make_manager(budget_gb=2.0)
    for name in ("a", "b"):
        manager.register(spec(recorder, name, 2.0))
        manager.preload(name)
    report = manager.budget_report()
    assert report.evictions == 1
    assert report.loads == 2


# --------------------------------------------------------------------------- #
# Defaults from configuration
# --------------------------------------------------------------------------- #


def test_manager_defaults_come_from_the_configuration():
    set_config(
        load_config(
            env={"CAISSA_RUNTIME__VRAM_BUDGET_GB": "5.0"},
            include_user_file=False,
            include_project_file=False,
        )
    )
    manager = ModelResidencyManager(device="cpu", empty_cache=lambda: None)
    assert manager.budget_bytes == gigabytes(5.0)


def test_singleton_is_shared():
    assert get_residency_manager() is get_residency_manager()


def test_specs_reject_nonsense():
    with pytest.raises(ValueError, match="vazio"):
        ModelSpec(name="", vram_bytes=1, loader=lambda device: device)
    with pytest.raises(ValueError, match="negativo"):
        ModelSpec(name="x", vram_bytes=-1, loader=lambda device: device)
    with pytest.raises(ValueError, match="priority"):
        ModelSpec(name="x", vram_bytes=1, loader=lambda d: d, pinned=True, priority=5)
