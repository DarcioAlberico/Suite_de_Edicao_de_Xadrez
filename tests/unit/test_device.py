"""Tests for device selection and the real-compute probe (ADR-0003).

The GPU is mocked with a small but *functional* fake torch: fake tensors really
multiply, really slice and really report a device, so ``probe_real_compute`` runs
its complete code path -- allocation, matmul, synchronise, timing, CPU
cross-check -- without a GPU. That is what lets the interesting failure modes be
tested: the sm_120 "no kernel image" error, a silent fallback to CPU, and
numerically wrong results.

The single test that touches the real GPU is marked ``gpu`` and skips when there
is no usable device.
"""

from __future__ import annotations

import math
import types

import pytest

from caissa.core.config import load_config, set_config
from caissa.vision.runtime import device as devmod
from caissa.vision.runtime.device import (
    ComputeProbeResult,
    DeviceUnavailableError,
    diagnose_cuda_error,
    get_device,
    get_device_info,
    probe_real_compute,
    reset_device_cache,
)

NO_KERNEL_MESSAGE = (
    "CUDA error: no kernel image is available for execution on the device\n"
    "CUDA kernel errors might be asynchronously reported at some other API call."
)


# --------------------------------------------------------------------------- #
# A small, working fake torch
# --------------------------------------------------------------------------- #


class FakeDType:
    """Stands in for ``torch.float16`` and friends."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f"torch.{self.name}"

    def __repr__(self) -> str:
        return str(self)


class FakeTensor:
    """Row-major 2-D tensor with just enough behaviour for the probe."""

    def __init__(self, rows: list[list[float]], device: str, dtype: FakeDType) -> None:
        self.rows = rows
        self._device = device
        self.dtype = dtype

    @property
    def device(self) -> str:
        return self._device

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.rows), len(self.rows[0]) if self.rows else 0)

    def to(self, device: str | None = None, dtype: FakeDType | None = None) -> FakeTensor:
        return FakeTensor(
            [row[:] for row in self.rows],
            device if device is not None else self._device,
            dtype if dtype is not None else self.dtype,
        )

    def __matmul__(self, other: FakeTensor) -> FakeTensor:
        _rows, k = self.shape
        k2, m = other.shape
        assert k == k2
        columns = [[other.rows[i][j] for i in range(k2)] for j in range(m)]
        product = [
            [sum(a * b for a, b in zip(row, col, strict=True)) for col in columns]
            for row in self.rows
        ]
        return FakeTensor(product, self._device, self.dtype)

    def __sub__(self, other: FakeTensor) -> FakeTensor:
        return FakeTensor(
            [
                [a - b for a, b in zip(x, y, strict=True)]
                for x, y in zip(self.rows, other.rows, strict=True)
            ],
            self._device,
            self.dtype,
        )

    def __getitem__(self, key: tuple[slice, slice]) -> FakeTensor:
        rows_slice, cols_slice = key
        return FakeTensor(
            [row[cols_slice] for row in self.rows[rows_slice]], self._device, self.dtype
        )

    def abs(self) -> FakeTensor:
        return FakeTensor([[abs(v) for v in row] for row in self.rows], self._device, self.dtype)

    def max(self) -> FakeScalar:
        return FakeScalar(max(max(row) for row in self.rows))

    def isfinite(self) -> FakeTensor:
        return FakeTensor(
            [[float(math.isfinite(v)) for v in row] for row in self.rows],
            self._device,
            self.dtype,
        )

    def all(self) -> FakeScalar:
        return FakeScalar(all(all(row) for row in self.rows))


class FakeScalar:
    """Result of a reduction; only ``.item()`` is needed."""

    def __init__(self, value: float | bool) -> None:
        self.value = value

    def item(self) -> float | bool:
        return self.value


class FakeGenerator:
    """Deterministic pseudo-random source, so the probe stays reproducible."""

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self.state = 1

    def manual_seed(self, seed: int) -> FakeGenerator:
        self.state = seed & 0xFFFFFFFF or 1
        return self

    def next(self) -> float:
        self.state = (1103515245 * self.state + 12345) & 0x7FFFFFFF
        return (self.state / 0x7FFFFFFF) * 2.0 - 1.0


class FakeProperties:
    def __init__(self, name: str, major: int, minor: int, total: int, sms: int) -> None:
        self.name = name
        self.major = major
        self.minor = minor
        self.total_memory = total
        self.multi_processor_count = sms


def build_fake_torch(
    *,
    available: bool = True,
    capability: tuple[int, int] = (12, 0),
    cuda_build: str | None = "12.8",
    matmul_error: Exception | None = None,
    force_result_device: str | None = None,
    corrupt: bool = False,
    device_count: int = 1,
    mem_info: tuple[int, int] = (6 * 1024**3, 8 * 1024**3),
) -> types.ModuleType:
    """Assemble a fake ``torch`` module with the requested behaviour."""
    module = types.ModuleType("torch")
    module.__version__ = "2.9.0+cu128"
    module.version = types.SimpleNamespace(cuda=cuda_build)
    module.float32 = FakeDType("float32")
    module.float16 = FakeDType("float16")
    module.bfloat16 = FakeDType("bfloat16")
    module.Generator = FakeGenerator
    module.device = lambda spec: f"device({spec})"

    def randn(rows: int, cols: int, *, generator: FakeGenerator, dtype: FakeDType) -> FakeTensor:
        return FakeTensor(
            [[generator.next() for _ in range(cols)] for _ in range(rows)], "cpu", dtype
        )

    module.randn = randn

    synchronised = {"count": 0}

    def synchronize() -> None:
        synchronised["count"] += 1

    original_matmul = FakeTensor.__matmul__

    def patched_matmul(self: FakeTensor, other: FakeTensor) -> FakeTensor:
        on_gpu = self.device.startswith("cuda")
        if matmul_error is not None and on_gpu:
            raise matmul_error
        result = original_matmul(self, other)
        if not on_gpu:
            # The CPU reference slice must stay honest, otherwise the test would
            # corrupt both sides and prove nothing.
            return result
        if force_result_device is not None:
            result = FakeTensor(result.rows, force_result_device, result.dtype)
        if corrupt:
            result = FakeTensor(
                [[v + 1000.0 for v in row] for row in result.rows], result.device, result.dtype
            )
        return result

    module.patched_matmul = patched_matmul
    module.cuda = types.SimpleNamespace(
        is_available=lambda: available,
        device_count=lambda: device_count,
        get_device_properties=lambda _index=0: FakeProperties(
            "NVIDIA GeForce RTX 5060", capability[0], capability[1], mem_info[1], 30
        ),
        get_device_capability=lambda _index=0: capability,
        mem_get_info=lambda _index=0: mem_info,
        synchronize=synchronize,
        empty_cache=lambda: None,
        synchronised=synchronised,
    )
    return module


@pytest.fixture
def fake_torch(monkeypatch):
    """Install a fake torch and neutralise nvidia-smi."""

    def install(**kwargs) -> types.ModuleType:
        module = build_fake_torch(**kwargs)
        monkeypatch.setattr(FakeTensor, "__matmul__", module.patched_matmul)
        monkeypatch.setattr(devmod, "import_torch", lambda: module)
        monkeypatch.setattr(devmod, "nvidia_smi_driver_version", lambda: "591.86")
        reset_device_cache()
        return module

    return install


# --------------------------------------------------------------------------- #
# probe_real_compute -- the honest check
# --------------------------------------------------------------------------- #


def test_probe_succeeds_and_reports_real_numbers(fake_torch):
    fake_torch()
    result = probe_real_compute(device="cuda:0", size=8, dtype="float16")
    assert isinstance(result, ComputeProbeResult)
    assert result.ok is True
    assert result.device == "cuda:0"
    assert result.result_device == "cuda:0"
    assert result.size == 8
    assert result.warm_ms >= 0.0
    assert result.gflops > 0.0
    assert result.max_abs_error == pytest.approx(0.0, abs=1e-9)
    assert result.notes == ()
    assert result.diagnosis is None


def test_probe_synchronises_around_the_workload(fake_torch):
    module = fake_torch()
    probe_real_compute(device="cuda:0", size=4, dtype="float16")
    # once before timing, once after the cold run, once after the warm run
    assert module.cuda.synchronised["count"] >= 3


def test_probe_diagnoses_the_sm120_failure(fake_torch):
    fake_torch(matmul_error=RuntimeError(NO_KERNEL_MESSAGE), cuda_build="12.4")
    result = probe_real_compute(device="cuda:0", size=8, dtype="float16")
    assert result.ok is False
    assert result.error_type == "RuntimeError"
    assert "no kernel image" in (result.error_message or "")
    assert result.diagnosis is not None
    assert "sm_120" in result.diagnosis
    assert "12.4" in result.diagnosis
    assert "cu128" in result.diagnosis


def test_probe_detects_a_silent_fallback_to_cpu(fake_torch):
    fake_torch(force_result_device="cpu")
    result = probe_real_compute(device="cuda:0", size=8, dtype="float16")
    assert result.ok is False
    assert result.result_device == "cpu"
    assert "fallback silencioso" in (result.diagnosis or "")


def test_probe_detects_numerically_wrong_results(fake_torch):
    fake_torch(corrupt=True)
    result = probe_real_compute(device="cuda:0", size=8, dtype="float16")
    assert result.ok is False
    assert result.max_abs_error is not None
    assert result.max_abs_error > result.tolerance
    assert "Erro numerico" in (result.diagnosis or "")


def test_probe_reports_out_of_memory_in_plain_language(fake_torch):
    fake_torch(matmul_error=RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"))
    result = probe_real_compute(device="cuda:0", size=8, dtype="float16")
    assert result.ok is False
    assert "VRAM insuficiente" in (result.diagnosis or "")


def test_probe_without_torch_says_so(monkeypatch):
    monkeypatch.setattr(devmod, "import_torch", lambda: None)
    monkeypatch.setattr(devmod, "torch_import_error", lambda: "ModuleNotFoundError: torch")
    reset_device_cache()
    result = probe_real_compute(device="cuda:0", size=8)
    assert result.ok is False
    assert result.error_type == "ImportError"
    assert "setup_env.ps1" in (result.diagnosis or "")


def test_probe_rejects_an_unknown_dtype(fake_torch):
    fake_torch()
    result = probe_real_compute(device="cuda:0", size=4, dtype="float128")
    assert result.ok is False
    assert "float128" in (result.diagnosis or "")


def test_probe_runs_on_cpu_too(fake_torch):
    fake_torch(available=False)
    result = probe_real_compute(device="cpu", size=8, dtype="float32")
    assert result.ok is True
    assert result.result_device == "cpu"


# --------------------------------------------------------------------------- #
# diagnose_cuda_error
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (NO_KERNEL_MESSAGE, "nao contem kernels"),
        ("CUDA out of memory", "VRAM insuficiente"),
        ("CUDA driver version is insufficient for CUDA runtime version", "driver NVIDIA"),
        ("DLL load failed while importing onnxruntime_pybind11_state", "onnxruntime-gpu"),
        ("device-side assert triggered", "Assert dentro do kernel"),
        ("something entirely new", "nao classificado"),
    ],
)
def test_diagnosis_maps_every_known_failure_mode(fake_torch, message, expected):
    fake_torch()
    assert expected in diagnose_cuda_error(RuntimeError(message), (12, 0))


# --------------------------------------------------------------------------- #
# get_device_info / get_device
# --------------------------------------------------------------------------- #


def test_device_info_describes_a_healthy_gpu(fake_torch):
    fake_torch()
    info = get_device_info(refresh=True)
    assert info.kind == "cuda"
    assert info.index == 0
    assert info.usable is True
    assert info.capability == (12, 0)
    assert info.cuda_build == (12, 8)
    assert info.driver_version == "591.86"
    assert info.torch_device_string == "cuda:0"
    assert info.is_blackwell_or_newer is True
    assert info.cuda_build_supports_capability is True
    assert info.total_vram_bytes == 8 * 1024**3
    assert info.failure_reason is None
    payload = info.as_dict()
    assert payload["total_vram_gb"] == 8.0
    assert payload["torch_device_string"] == "cuda:0"


def test_device_info_is_cached_until_refreshed(fake_torch):
    fake_torch()
    first = get_device_info()
    assert get_device_info() is first
    assert get_device_info(refresh=True) is not first


def test_old_wheel_on_blackwell_is_reported_as_unusable(fake_torch):
    fake_torch(cuda_build="12.4", matmul_error=RuntimeError(NO_KERNEL_MESSAGE))
    info = get_device_info(refresh=True)
    assert info.cuda_reported_available is True  # torch lied
    assert info.usable is False  # reality
    assert info.kind == "cpu"
    assert info.torch_device_string == "cpu"
    assert info.cuda_build_supports_capability is False
    assert "cu128" in (info.failure_reason or "")


def test_no_cuda_device_degrades_to_cpu(fake_torch):
    fake_torch(available=False)
    info = get_device_info(refresh=True)
    assert info.kind == "cpu"
    assert info.usable is True
    assert "is_available() retornou False" in (info.failure_reason or "")


def test_missing_ordinal_degrades_to_cpu(fake_torch):
    fake_torch(device_count=1)
    info = get_device_info(index=3, refresh=True)
    assert info.kind == "cpu"
    assert "nao existe" in (info.failure_reason or "")


def test_configuration_can_force_cpu(fake_torch):
    fake_torch()
    set_config(
        load_config(
            env={"CAISSA_RUNTIME__DEVICE": "cpu"},
            include_user_file=False,
            include_project_file=False,
        )
    )
    reset_device_cache()
    info = get_device_info(refresh=True)
    assert info.kind == "cpu"
    assert "runtime.device" in (info.failure_reason or "")


def test_configuration_can_demand_cuda_and_then_it_must_work(fake_torch):
    fake_torch(matmul_error=RuntimeError(NO_KERNEL_MESSAGE))
    set_config(
        load_config(
            env={"CAISSA_RUNTIME__DEVICE": "cuda"},
            include_user_file=False,
            include_project_file=False,
        )
    )
    reset_device_cache()
    with pytest.raises(DeviceUnavailableError, match="cu128"):
        get_device_info(refresh=True)


def test_get_device_returns_a_cached_handle(fake_torch):
    fake_torch()
    handle = get_device()
    assert handle == "device(cuda:0)"
    assert get_device() is handle
    assert get_device(prefer="cpu") == "device(cpu)"


def test_get_device_prefer_cuda_raises_when_unusable(fake_torch):
    fake_torch(matmul_error=RuntimeError(NO_KERNEL_MESSAGE))
    with pytest.raises(DeviceUnavailableError, match="cu128"):
        get_device(prefer="cuda")


def test_get_device_without_torch_raises(monkeypatch):
    monkeypatch.setattr(devmod, "import_torch", lambda: None)
    monkeypatch.setattr(devmod, "torch_import_error", lambda: "ModuleNotFoundError: torch")
    reset_device_cache()
    with pytest.raises(DeviceUnavailableError, match=r"setup_env\.ps1"):
        get_device()


def test_vram_status(fake_torch):
    fake_torch()
    assert devmod.vram_status() == (6 * 1024**3, 8 * 1024**3)


def test_vram_status_is_zero_without_cuda(fake_torch):
    fake_torch(available=False)
    assert devmod.vram_status() == (0, 0)


def test_cuda_build_version_parsing(fake_torch):
    fake_torch(cuda_build="12.8")
    assert devmod.torch_cuda_build_version() == (12, 8)
    fake_torch(cuda_build=None)
    assert devmod.torch_cuda_build_version() is None


# --------------------------------------------------------------------------- #
# The one test that uses the real device
# --------------------------------------------------------------------------- #


@pytest.mark.gpu
def test_real_gpu_matmul_meets_the_f0_gate():
    """F0 gate: a warm 4096x4096 fp16 matmul on the real GPU, under 100 ms."""
    torch = devmod.import_torch()
    if torch is None or not torch.cuda.is_available():
        pytest.skip("nenhuma GPU CUDA disponivel")
    info = get_device_info(refresh=True)
    if not info.usable:
        pytest.fail(f"A GPU existe mas nao executa kernels: {info.failure_reason}")

    result = probe_real_compute(size=4096, dtype="float16")
    assert result.ok, result.diagnosis
    assert result.result_device.startswith("cuda")
    assert result.max_abs_error is not None
    assert result.max_abs_error <= result.tolerance
    assert result.warm_ms < 100.0, f"matmul quente levou {result.warm_ms:.2f} ms"
