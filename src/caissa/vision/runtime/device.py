"""Device selection and capability probing.

This module is the *only* place in Caissa Studio allowed to decide whether work
runs on the GPU. No subsystem may call ``.to("cuda")`` directly (ADR-0004); it
asks :func:`get_device` and, for model weights, goes through
:class:`caissa.vision.runtime.residency.ModelResidencyManager`.

The reason this exists as its own module is ADR-0003. On the reference machine
the GPU is Blackwell (``sm_120``), which only has kernels in the PyTorch
``cu128`` wheels. With any earlier wheel ``torch.cuda.is_available()`` still
returns ``True`` -- the driver is there, the device enumerates, memory queries
work -- and then the first real kernel launch fails with::

    CUDA error: no kernel image is available for execution on the device

or, worse, some libraries quietly fall back to CPU and the only symptom is that
everything is thirty times slower. So availability is never taken on faith:
:func:`probe_real_compute` runs an actual matmul, synchronises, times it, and
checks the numbers against a CPU reference.

``torch`` is imported lazily through :func:`import_torch` so that this module
imports cleanly in an environment where torch is missing or broken -- which is
exactly the environment ``scripts/doctor.py`` has to diagnose.
"""

from __future__ import annotations

import contextlib
import math
import platform
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Any, Final, Literal

from caissa.core.config import get_config

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch as torch_module

__all__ = [
    "DEFAULT_PROBE_SIZE",
    "ComputeProbeResult",
    "DeviceInfo",
    "DeviceUnavailableError",
    "diagnose_cuda_error",
    "get_device",
    "get_device_info",
    "import_torch",
    "nvidia_smi_driver_version",
    "probe_real_compute",
    "reset_device_cache",
    "torch_cuda_build_version",
    "vram_status",
]

DeviceKind = Literal["cuda", "cpu"]

DEFAULT_PROBE_SIZE: Final = 4096
"""Matmul edge length used by the F0 gate: 4096x4096 fp16."""

_MIN_CUDA_BUILD_FOR_BLACKWELL: Final = (12, 8)
"""SPEC R1: sm_120 needs CUDA 12.8 or newer in the torch build."""

_BLACKWELL_MAJOR: Final = 12

_NO_KERNEL_PATTERNS: Final = (
    "no kernel image is available",
    "kernel image is available for execution",
)

_LOCK = threading.RLock()


@dataclass
class _ModuleState:
    """Mutable module state, kept in one object so no function needs ``global``."""

    torch: ModuleType | None = None
    import_error: str | None = None
    info_cache: dict[int, DeviceInfo] = field(default_factory=dict)
    selected_device: Any = None


_STATE = _ModuleState()


class DeviceUnavailableError(RuntimeError):
    """Raised when CUDA was explicitly requested but is not usable."""


# --------------------------------------------------------------------------- #
# torch access
# --------------------------------------------------------------------------- #


def import_torch() -> ModuleType | None:
    """Import ``torch`` once, returning ``None`` if it is missing or broken.

    Tests monkeypatch this function to inject a fake torch module; nothing else
    in the package imports torch at module scope.
    """
    with _LOCK:
        if _STATE.torch is not None:
            return _STATE.torch
        if _STATE.import_error is not None:
            return None
        try:
            import torch  # noqa: PLC0415 - lazy on purpose; see the module docstring
        except Exception as exc:  # noqa: BLE001 - a broken DLL raises OSError
            _STATE.import_error = f"{type(exc).__name__}: {exc}"
            return None
        _STATE.torch = torch
        return _STATE.torch


def torch_import_error() -> str | None:
    """Return the reason torch could not be imported, if it could not."""
    import_torch()
    return _STATE.import_error


def torch_cuda_build_version(torch: ModuleType | None = None) -> tuple[int, int] | None:
    """Return the CUDA version the installed torch wheel was built against."""
    mod = import_torch() if torch is None else torch
    if mod is None:
        return None
    raw = getattr(getattr(mod, "version", None), "cuda", None)
    if not raw:
        return None
    match = re.match(r"^(\d+)\.(\d+)", str(raw))
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def nvidia_smi_driver_version() -> str | None:
    """Ask ``nvidia-smi`` for the driver version, or ``None`` if unavailable.

    Used only for reporting: the driver version is not exposed by torch in a
    stable way, and knowing it is what lets a user tell "driver too old" apart
    from "wrong wheel".
    """
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, absolute resolved path
            [executable, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    first = completed.stdout.strip().splitlines()
    return first[0].strip() if first else None


# --------------------------------------------------------------------------- #
# Error diagnosis
# --------------------------------------------------------------------------- #


def diagnose_cuda_error(exc: BaseException, capability: tuple[int, int] | None = None) -> str:
    """Translate a CUDA exception into the actual root cause, in plain language.

    The important case is the ``sm_120`` one: PyTorch reports a perfectly healthy
    device right up until a kernel launch, so the raw exception text is
    misleading unless it is read together with the wheel's CUDA build version.
    """
    text = str(exc)
    lowered = text.lower()
    build = torch_cuda_build_version()
    build_text = ".".join(str(p) for p in build) if build else "desconhecida"
    cap_text = f"sm_{capability[0]}{capability[1]}" if capability else "desconhecida"

    if any(pattern in lowered for pattern in _NO_KERNEL_PATTERNS):
        return (
            f"A GPU tem compute capability {cap_text}, mas a roda do PyTorch instalada foi "
            f"compilada para CUDA {build_text} e nao contem kernels para essa arquitetura. "
            f"Esta e a falha descrita em SPEC R1 / ADR-0003. "
            f"Correcao: reinstale o torch a partir de https://download.pytorch.org/whl/cu128 "
            f"(scripts/setup_env.ps1 faz isso)."
        )
    if "out of memory" in lowered:
        return (
            "VRAM insuficiente para a operacao. Reduza runtime.vram_budget_gb, feche outras "
            "aplicacoes que usam a GPU, ou deixe o ModelResidencyManager despejar modelos "
            "(ADR-0004)."
        )
    if "cuda driver version is insufficient" in lowered or "insufficient cuda" in lowered:
        driver = nvidia_smi_driver_version() or "desconhecida"
        return (
            f"O driver NVIDIA instalado (versao {driver}) e antigo demais para a roda de torch "
            f"compilada com CUDA {build_text}. Atualize o driver."
        )
    if "dll load failed" in lowered or "cannot open shared object" in lowered:
        return (
            "Falha ao carregar as DLLs do CUDA. A causa mais comum e ter onnxruntime-gpu "
            "instalado no mesmo ambiente que o torch cu128: os dois trazem CUDA Runtimes "
            "diferentes e disputam o mesmo processo (ADR-0003). Remova onnxruntime-gpu deste "
            "ambiente e use o ambiente isolado do worker."
        )
    if "device-side assert" in lowered:
        return "Assert dentro do kernel CUDA -- indica indices fora de faixa nos tensores."
    return f"Erro CUDA nao classificado: {type(exc).__name__}: {text}"


# --------------------------------------------------------------------------- #
# Device information
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Everything known about the compute device, gathered without trusting it.

    Attributes:
        kind: ``"cuda"`` or ``"cpu"``.
        index: CUDA device ordinal, or ``None`` on CPU.
        name: Marketing name of the device (``"NVIDIA GeForce RTX 5060"``).
        torch_version: Version string of the installed torch, if any.
        cuda_build: ``(major, minor)`` CUDA version the wheel was built against.
        capability: ``(major, minor)`` compute capability reported by the device.
        driver_version: NVIDIA driver version, from ``nvidia-smi``.
        total_vram_bytes: Total device memory.
        free_vram_bytes: Free device memory at the time of the query.
        multi_processor_count: Number of SMs, useful for sizing work.
        cuda_reported_available: The raw ``torch.cuda.is_available()`` value,
            recorded precisely so that it can be contrasted with reality.
        usable: Whether a real kernel actually executed. This is the field
            callers must branch on.
        failure_reason: Why ``usable`` is ``False``, in plain language.
    """

    kind: DeviceKind
    index: int | None
    name: str
    torch_version: str | None
    cuda_build: tuple[int, int] | None
    capability: tuple[int, int] | None
    driver_version: str | None
    total_vram_bytes: int
    free_vram_bytes: int
    multi_processor_count: int | None
    cuda_reported_available: bool
    usable: bool
    failure_reason: str | None = None

    @property
    def torch_device_string(self) -> str:
        """The string accepted by ``torch.device`` for this device."""
        if self.kind == "cuda" and self.index is not None:
            return f"cuda:{self.index}"
        return self.kind

    @property
    def is_blackwell_or_newer(self) -> bool:
        """Whether the device is sm_120 or later, which forces the cu128 wheel."""
        return self.capability is not None and self.capability[0] >= _BLACKWELL_MAJOR

    @property
    def cuda_build_supports_capability(self) -> bool:
        """Whether the installed wheel can possibly contain kernels for this GPU."""
        if self.capability is None or self.cuda_build is None:
            return False
        if not self.is_blackwell_or_newer:
            return True
        return self.cuda_build >= _MIN_CUDA_BUILD_FOR_BLACKWELL

    def as_dict(self) -> dict[str, Any]:
        """Plain-data view for ``--json`` output."""
        data = asdict(self)
        data["torch_device_string"] = self.torch_device_string
        data["total_vram_gb"] = round(self.total_vram_bytes / 1024**3, 3)
        data["free_vram_gb"] = round(self.free_vram_bytes / 1024**3, 3)
        return data


def _cpu_device_info(reason: str, torch: ModuleType | None) -> DeviceInfo:
    return DeviceInfo(
        kind="cpu",
        index=None,
        name=platform.processor() or platform.machine() or "CPU",
        torch_version=getattr(torch, "__version__", None) if torch else None,
        cuda_build=torch_cuda_build_version(torch),
        capability=None,
        driver_version=None,
        total_vram_bytes=0,
        free_vram_bytes=0,
        multi_processor_count=None,
        cuda_reported_available=False,
        usable=True,
        failure_reason=reason,
    )


def get_device_info(index: int | None = None, *, refresh: bool = False) -> DeviceInfo:
    """Describe the compute device, verifying it with a real kernel launch.

    Args:
        index: CUDA ordinal. Defaults to ``runtime.cuda_device_index``.
        refresh: Ignore the cache and re-probe. Probing costs a few
            milliseconds, so the result is cached per ordinal.

    Returns:
        A :class:`DeviceInfo` whose ``usable`` flag reflects an executed kernel,
        not ``torch.cuda.is_available()``.
    """
    config = get_config()
    ordinal = config.runtime.cuda_device_index if index is None else index

    with _LOCK:
        if not refresh and ordinal in _STATE.info_cache:
            return _STATE.info_cache[ordinal]

    torch = import_torch()
    if torch is None:
        info = _cpu_device_info(
            f"PyTorch nao pode ser importado ({torch_import_error()}); "
            f"execute scripts/setup_env.ps1",
            None,
        )
    elif config.runtime.device == "cpu":
        info = _cpu_device_info("runtime.device = 'cpu' na configuracao", torch)
    else:
        info = _probe_cuda_device(torch, ordinal, config.runtime.device == "cuda")

    with _LOCK:
        _STATE.info_cache[ordinal] = info
    return info


def _probe_cuda_device(torch: ModuleType, ordinal: int, forced: bool) -> DeviceInfo:
    """Build a :class:`DeviceInfo` for a CUDA ordinal, verifying with real compute."""
    reported = bool(torch.cuda.is_available())
    if not reported:
        reason = (
            "torch.cuda.is_available() retornou False. Ou a roda instalada e a versao CPU "
            "(torch.version.cuda vazio), ou o driver NVIDIA nao esta acessivel."
        )
        if forced:
            raise DeviceUnavailableError(reason)
        return _cpu_device_info(reason, torch)

    count = int(torch.cuda.device_count())
    if ordinal >= count:
        reason = f"Dispositivo CUDA {ordinal} nao existe (encontrados: {count})."
        if forced:
            raise DeviceUnavailableError(reason)
        return _cpu_device_info(reason, torch)

    props = torch.cuda.get_device_properties(ordinal)
    capability: tuple[int, int] = (int(props.major), int(props.minor))
    try:
        free_bytes, total_bytes = (int(v) for v in torch.cuda.mem_get_info(ordinal))
    except Exception:  # noqa: BLE001 - mem_get_info can fail on exotic setups
        total_bytes = int(getattr(props, "total_memory", 0))
        free_bytes = 0

    # A liveness probe, not a benchmark: any kernel launch is enough to expose
    # a missing kernel image. doctor.py runs the full 4096 gate separately.
    probe = probe_real_compute(device=f"cuda:{ordinal}", size=64, torch=torch)
    if not probe.ok:
        if forced:
            raise DeviceUnavailableError(probe.diagnosis or "GPU indisponivel")
        return DeviceInfo(
            kind="cpu",
            index=None,
            name=str(props.name),
            torch_version=str(torch.__version__),
            cuda_build=torch_cuda_build_version(torch),
            capability=capability,
            driver_version=nvidia_smi_driver_version(),
            total_vram_bytes=total_bytes,
            free_vram_bytes=free_bytes,
            multi_processor_count=int(getattr(props, "multi_processor_count", 0)) or None,
            cuda_reported_available=True,
            usable=False,
            failure_reason=probe.diagnosis,
        )

    return DeviceInfo(
        kind="cuda",
        index=ordinal,
        name=str(props.name),
        torch_version=str(torch.__version__),
        cuda_build=torch_cuda_build_version(torch),
        capability=capability,
        driver_version=nvidia_smi_driver_version(),
        total_vram_bytes=total_bytes,
        free_vram_bytes=free_bytes,
        multi_processor_count=int(getattr(props, "multi_processor_count", 0)) or None,
        cuda_reported_available=True,
        usable=True,
        failure_reason=None,
    )


def vram_status(index: int | None = None) -> tuple[int, int]:
    """Return ``(free_bytes, total_bytes)`` for the CUDA device, ``(0, 0)`` on CPU."""
    torch = import_torch()
    if torch is None or not torch.cuda.is_available():
        return (0, 0)
    ordinal = get_config().runtime.cuda_device_index if index is None else index
    try:
        free_bytes, total_bytes = torch.cuda.mem_get_info(ordinal)
    except Exception:  # noqa: BLE001
        return (0, 0)
    return (int(free_bytes), int(total_bytes))


# --------------------------------------------------------------------------- #
# The real compute probe
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ComputeProbeResult:
    """Outcome of an executed matrix multiplication, not of a capability query.

    Attributes:
        ok: The kernel ran, produced the expected shape on the expected device,
            and matched a CPU reference within tolerance.
        device: Device string the workload was requested on.
        result_device: Device the output tensor actually landed on. A mismatch
            means a silent fallback happened (the failure mode ADR-0003 warns of).
        size: Edge length of the square matrices.
        dtype: Element type used.
        cold_ms: Wall time of the first (unwarmed) multiplication, including
            context creation and kernel autotuning.
        warm_ms: Wall time of the timed multiplication after warm-up. This is the
            number the F0 gate compares against ``runtime.gpu_matmul_budget_ms``.
        gflops: Achieved throughput of the warm run.
        max_abs_error: Largest absolute difference against the CPU reference.
        tolerance: Threshold ``max_abs_error`` had to stay under.
        error_type: Exception class name when the probe failed.
        error_message: Raw exception text when the probe failed.
        diagnosis: Root cause in plain language (see :func:`diagnose_cuda_error`).
    """

    ok: bool
    device: str
    result_device: str | None
    size: int
    dtype: str
    cold_ms: float
    warm_ms: float
    gflops: float
    max_abs_error: float | None
    tolerance: float
    error_type: str | None = None
    error_message: str | None = None
    diagnosis: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        """Plain-data view for ``--json`` output."""
        return asdict(self)


def _reference_tolerance(size: int, dtype_name: str) -> float:
    """Tolerance for the CPU cross-check.

    fp16 accumulation over ``size`` terms of unit-variance values produces
    results of magnitude ``~sqrt(size)``; fp16 has about 11 bits of mantissa, so
    representation error alone is ``~sqrt(size) * 2**-11``. A generous multiple
    of that still catches genuinely wrong results (transposed operands, garbage
    memory, a half-executed kernel) while never flagging correct arithmetic.
    """
    magnitude = math.sqrt(size)
    if dtype_name in {"torch.float16", "torch.half", "torch.bfloat16"}:
        unit = 2.0**-8 if dtype_name == "torch.bfloat16" else 2.0**-11
        return max(0.05, magnitude * unit * 16.0)
    return max(1e-3, magnitude * 2.0**-23 * 64.0)


def _timed_matmul(left: Any, right: Any, sync: Callable[[], None]) -> tuple[Any, float, float]:
    """Multiply twice -- once cold, once warm -- synchronising around each run.

    The cold run includes context creation and kernel autotuning, which is why
    the F0 gate is judged on the warm one.
    """
    cold_start = time.perf_counter()
    product = left @ right
    sync()
    cold_ms = (time.perf_counter() - cold_start) * 1000.0

    warm_start = time.perf_counter()
    product = left @ right
    sync()
    warm_ms = (time.perf_counter() - warm_start) * 1000.0
    return product, cold_ms, warm_ms


def _cross_check(
    mod: ModuleType, left: Any, right: Any, product: Any, rows: int
) -> tuple[float, bool]:
    """Compare a corner of the product against a float32 CPU reference.

    The reference is built from the *same* (already rounded) input tensors, so
    the only difference that can appear is the arithmetic itself.
    """
    reference = left[:rows, :].to(device="cpu", dtype=mod.float32) @ right[:, :rows].to(
        device="cpu", dtype=mod.float32
    )
    observed = product[:rows, :rows].to(device="cpu", dtype=mod.float32)
    max_abs_error = float((observed - reference).abs().max().item())
    finite = bool(observed.isfinite().all().item())
    return max_abs_error, finite


def _collect_notes(
    *,
    is_cuda: bool,
    device: str,
    result_device: str,
    max_abs_error: float,
    tolerance: float,
    finite: bool,
) -> list[str]:
    """List everything wrong with a run that did not raise.

    An empty list means the workload genuinely executed where it was asked to
    and produced correct numbers.
    """
    notes: list[str] = []
    if is_cuda and not result_device.startswith("cuda"):
        notes.append(
            f"O tensor de saida ficou em '{result_device}' apesar de '{device}' ter sido "
            f"pedido -- houve fallback silencioso para CPU (ADR-0003)."
        )
    if max_abs_error > tolerance:
        notes.append(f"Erro numerico {max_abs_error:.4f} acima da tolerancia {tolerance:.4f}.")
    if not finite:
        notes.append("A saida contem NaN ou infinito.")
    return notes


def _probe_failure(
    *,
    device: str,
    size: int,
    dtype: str,
    error_type: str,
    error_message: str | None,
    diagnosis: str,
) -> ComputeProbeResult:
    """Build a failed probe result, so the happy path stays readable."""
    return ComputeProbeResult(
        ok=False,
        device=device,
        result_device=None,
        size=size,
        dtype=dtype,
        cold_ms=0.0,
        warm_ms=0.0,
        gflops=0.0,
        max_abs_error=None,
        tolerance=0.0,
        error_type=error_type,
        error_message=error_message,
        diagnosis=diagnosis,
    )


def probe_real_compute(
    *,
    device: str | None = None,
    size: int = DEFAULT_PROBE_SIZE,
    dtype: str = "float16",
    reference_rows: int = 8,
    torch: ModuleType | None = None,
) -> ComputeProbeResult:
    """Run a real matmul on ``device`` and verify the numbers.

    This is the heart of the ADR-0003 mitigation and the F0 gate. It allocates
    two ``size x size`` matrices, multiplies them, synchronises, times the warm
    run, and then checks a small slice of the output against a float32 CPU
    reference computed from the same inputs. Any exception is caught and turned
    into a root-cause diagnosis rather than propagated.

    Args:
        device: Torch device string. Defaults to the configured CUDA ordinal, or
            ``"cpu"`` when torch reports no CUDA at all.
        size: Edge length of the square matrices. 4096 is the F0 gate size.
        dtype: Element type name (``"float16"``, ``"bfloat16"``, ``"float32"``).
        reference_rows: How many rows/columns of the output to cross-check.
        torch: Injected torch module, for tests.

    Returns:
        A :class:`ComputeProbeResult`. ``ok`` is ``True`` only if the kernel ran,
        stayed on the requested device, and matched the reference.
    """
    mod = import_torch() if torch is None else torch
    if mod is None:
        return _probe_failure(
            device=device or "cuda",
            size=size,
            dtype=dtype,
            error_type="ImportError",
            error_message=torch_import_error(),
            diagnosis=(
                "PyTorch nao esta instalado neste interpretador. Execute scripts/setup_env.ps1."
            ),
        )

    if device is None:
        if bool(mod.cuda.is_available()):
            device = f"cuda:{get_config().runtime.cuda_device_index}"
        else:
            device = "cpu"

    torch_dtype = getattr(mod, dtype, None)
    if torch_dtype is None:
        return _probe_failure(
            device=device,
            size=size,
            dtype=dtype,
            error_type="ValueError",
            error_message=f"dtype desconhecido: {dtype}",
            diagnosis=f"dtype '{dtype}' nao existe em torch",
        )

    is_cuda = str(device).startswith("cuda")
    capability: tuple[int, int] | None = None

    def sync() -> None:
        if is_cuda:
            mod.cuda.synchronize()

    try:
        if is_cuda:
            ordinal = int(device.split(":", 1)[1]) if ":" in device else 0
            props = mod.cuda.get_device_properties(ordinal)
            capability = (int(props.major), int(props.minor))

        generator = mod.Generator(device="cpu").manual_seed(0x0CA155A)
        left = mod.randn(size, size, generator=generator, dtype=mod.float32).to(
            device=device, dtype=torch_dtype
        )
        right = mod.randn(size, size, generator=generator, dtype=mod.float32).to(
            device=device, dtype=torch_dtype
        )
        sync()

        product, cold_ms, warm_ms = _timed_matmul(left, right, sync)

        result_device = str(product.device)
        rows = min(reference_rows, size)
        max_abs_error, finite = _cross_check(mod, left, right, product, rows)

        tolerance = _reference_tolerance(size, str(torch_dtype))
        gflops = (2.0 * float(size) ** 3) / (warm_ms / 1000.0) / 1e9 if warm_ms > 0 else 0.0

        notes = _collect_notes(
            is_cuda=is_cuda,
            device=device,
            result_device=result_device,
            max_abs_error=max_abs_error,
            tolerance=tolerance,
            finite=finite,
        )
        ok = not notes
        return ComputeProbeResult(
            ok=ok,
            device=device,
            result_device=result_device,
            size=size,
            dtype=dtype,
            cold_ms=cold_ms,
            warm_ms=warm_ms,
            gflops=gflops,
            max_abs_error=max_abs_error,
            tolerance=tolerance,
            diagnosis=None if ok else " ".join(notes),
            notes=tuple(notes),
        )
    except Exception as exc:  # noqa: BLE001 - the whole point is to report anything
        return _probe_failure(
            device=device,
            size=size,
            dtype=dtype,
            error_type=type(exc).__name__,
            error_message=str(exc),
            diagnosis=diagnose_cuda_error(exc, capability),
        )
    finally:
        if is_cuda:
            # Cleanup must never mask the result being reported.
            with contextlib.suppress(Exception):
                mod.cuda.empty_cache()


# --------------------------------------------------------------------------- #
# Public device handle
# --------------------------------------------------------------------------- #


def get_device(prefer: DeviceKind | None = None) -> torch_module.device:
    """Return the torch device every subsystem must use.

    The result is cached for the life of the process; call
    :func:`reset_device_cache` after changing configuration.

    Args:
        prefer: Force a kind, ignoring ``runtime.device``. ``"cuda"`` raises
            :class:`DeviceUnavailableError` if the GPU is not genuinely usable.

    Returns:
        A ``torch.device``.

    Raises:
        DeviceUnavailableError: If torch is missing, or if CUDA was demanded
            (via ``prefer="cuda"`` or ``runtime.device = "cuda"``) but the real
            compute probe failed.
    """
    torch = import_torch()
    if torch is None:
        raise DeviceUnavailableError(
            f"PyTorch nao esta instalado ou nao carrega ({torch_import_error()}). "
            f"Execute scripts/setup_env.ps1."
        )

    with _LOCK:
        if prefer is None and _STATE.selected_device is not None:
            return _STATE.selected_device  # type: ignore[no-any-return]

    if prefer == "cpu":
        return torch.device("cpu")  # type: ignore[no-any-return]

    info = get_device_info()
    if prefer == "cuda" and not (info.kind == "cuda" and info.usable):
        raise DeviceUnavailableError(
            info.failure_reason or "A GPU nao passou na verificacao de computacao real."
        )

    device = torch.device(info.torch_device_string)
    if prefer is None:
        with _LOCK:
            _STATE.selected_device = device
    return device  # type: ignore[no-any-return]


def reset_device_cache(*, forget_torch: bool = False) -> None:
    """Forget the cached device and device information.

    Call this after :func:`caissa.core.config.set_config`, and in test teardown.

    Args:
        forget_torch: Also drop the memoised ``torch`` module handle, forcing the
            next :func:`import_torch` to retry the import. Only useful in tests
            and after an in-place reinstall.
    """
    with _LOCK:
        _STATE.info_cache.clear()
        _STATE.selected_device = None
        if forget_torch:
            _STATE.torch = None
            _STATE.import_error = None
