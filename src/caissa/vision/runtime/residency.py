"""VRAM residency management -- the ADR-0004 implementation.

The reference machine has 8 GiB of VRAM shared by the board detector, the square
classifier, one or more OCR engines and an optional multimodal LLM. The sum of
their peaks does not fit. Without arbitration the failure shows up as an
out-of-memory error in the middle of a 500-PDF batch, which is the worst possible
moment.

So there is exactly one arbiter, and it works like this:

* **Declarative cost.** Every model registers a :class:`ModelSpec` stating what
  it costs in VRAM *before* it is loaded. Placement decisions are made from the
  declaration, never by loading and hoping.
* **Lazy loading.** Nothing is loaded at startup. The first
  :meth:`ModelResidencyManager.acquire` triggers the loader.
* **Hard budget cap.** Resident cost never exceeds
  ``runtime.vram_budget_gb`` (default 7.0 GiB, leaving roughly 1 GiB to the
  Windows desktop compositor).
* **LRU eviction.** When a load would breach the cap, idle residents are evicted
  least-recently-used first. ``priority`` breaks ties: the LLM registers with a
  high priority so it is the first candidate, as ADR-0004 requires.
* **CPU fallback with a warning.** If eviction cannot free enough room, the model
  loads on CPU and the user is warned loudly -- a slow application beats a
  crashed one, but silence would be worse than both.
* **Serialised queue.** Models declaring the same ``exclusive_group`` never
  co-reside; requests for them queue in FIFO order.

Everything is thread-safe: the pipeline runs on a ``QThreadPool`` and several
workers may want the same classifier at once.
"""

from __future__ import annotations

import logging
import threading
import time
import warnings
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Final

from caissa.core.config import get_config

__all__ = [
    "BudgetReport",
    "ModelAlreadyResidentError",
    "ModelLease",
    "ModelNotRegisteredError",
    "ModelResidencyManager",
    "ModelSpec",
    "ResidencyError",
    "ResidencyTimeoutError",
    "ResidentReport",
    "VramBudgetExceededError",
    "VramFallbackWarning",
    "get_residency_manager",
    "gigabytes",
    "megabytes",
    "reset_residency_manager",
]

logger = logging.getLogger(__name__)

_BYTES_PER_GB: Final = 1024**3
_BYTES_PER_MB: Final = 1024**2

LoaderCallable = Callable[[str], Any]
UnloaderCallable = Callable[[Any], None]


def gigabytes(value: float) -> int:
    """Convert GiB to bytes, for readable :class:`ModelSpec` declarations."""
    return int(value * _BYTES_PER_GB)


def megabytes(value: float) -> int:
    """Convert MiB to bytes, for readable :class:`ModelSpec` declarations."""
    return int(value * _BYTES_PER_MB)


# --------------------------------------------------------------------------- #
# Errors and warnings
# --------------------------------------------------------------------------- #


class ResidencyError(RuntimeError):
    """Base class for residency-management failures."""


class ModelNotRegisteredError(ResidencyError, KeyError):
    """Raised when acquiring a model that was never registered."""

    def __init__(self, name: str, known: tuple[str, ...]) -> None:
        """Report the unknown name together with the registered ones."""
        self.name = name
        self.known = known
        listing = ", ".join(known) if known else "(nenhum)"
        super().__init__(f"Modelo '{name}' nao registrado. Registrados: {listing}")


class ModelAlreadyResidentError(ResidencyError):
    """Raised when re-registering a model that is currently loaded."""


class VramBudgetExceededError(ResidencyError):
    """Raised when a model does not fit and CPU fallback is disabled."""


class ResidencyTimeoutError(ResidencyError, TimeoutError):
    """Raised when waiting for VRAM or for an exclusive slot timed out."""


class VramFallbackWarning(UserWarning):
    """Emitted when a model is placed on the CPU because VRAM ran out.

    This is a warning rather than a log line on purpose: it changes the
    performance characteristics of the run and the user must be told.
    """


# --------------------------------------------------------------------------- #
# Declarative registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Declaration of one model's residency requirements.

    Attributes:
        name: Unique key used by :meth:`ModelResidencyManager.acquire`.
        vram_bytes: Declared VRAM footprint. Measure it once with
          ``torch.cuda.max_memory_allocated()`` and record it here; the manager
          budgets from this number, so an optimistic value causes real OOMs.
        loader: Called with the target device string (``"cuda:0"`` / ``"cpu"``)
            and must return the loaded model object.
        unloader: Optional teardown called before the reference is dropped.
        exclusive_group: Models sharing a group never co-reside; acquisitions
            queue FIFO. Used for models whose peaks cannot overlap at all
            (e.g. the 12B "quality mode" LLM against the vision pipeline).
        allow_cpu_fallback: Whether this specific model may run on CPU. Set
            ``False`` for models that would be uselessly slow there.
        pinned: Never evicted automatically. Reserve for the small, always-hot
            models (the square classifier).
        priority: Eviction preference. Higher is evicted first; ties are broken
            by least-recently-used. ADR-0004 makes the LLM the first candidate,
            so it registers with a high value.
        description: Human-readable label for the UI budget panel.
    """

    name: str
    vram_bytes: int
    loader: LoaderCallable
    unloader: UnloaderCallable | None = None
    exclusive_group: str | None = None
    allow_cpu_fallback: bool = True
    pinned: bool = False
    priority: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        """Reject nonsensical declarations at registration time."""
        if not self.name:
            raise ValueError("ModelSpec.name nao pode ser vazio")
        if self.vram_bytes < 0:
            raise ValueError(f"ModelSpec.vram_bytes nao pode ser negativo ({self.vram_bytes})")
        if self.pinned and self.priority:
            raise ValueError("ModelSpec fixado (pinned) nao usa priority de despejo")


@dataclass(frozen=True, slots=True)
class ModelLease:
    """A borrowed, eviction-protected reference to a loaded model.

    While a lease is held the model cannot be evicted. Leases are handed out by
    the :meth:`ModelResidencyManager.acquire` context manager and must not
    outlive it.
    """

    name: str
    model: Any
    device: str
    on_cpu_fallback: bool

    @property
    def is_cuda(self) -> bool:
        """Whether the model actually sits on a CUDA device."""
        return self.device.startswith("cuda")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResidentReport:
    """One row of :class:`BudgetReport`."""

    name: str
    device: str
    vram_bytes: int
    lease_count: int
    idle_seconds: float
    pinned: bool
    priority: int
    description: str

    @property
    def in_use(self) -> bool:
        """Whether at least one lease is currently held."""
        return self.lease_count > 0


@dataclass(frozen=True, slots=True)
class BudgetReport:
    """Snapshot of the VRAM budget, shaped for the UI status panel."""

    device: str
    budget_bytes: int
    reserved_bytes: int
    residents: tuple[ResidentReport, ...]
    registered: tuple[str, ...]
    loads: int
    evictions: int
    cpu_fallbacks: int
    waits: int
    device_free_bytes: int | None = None
    device_total_bytes: int | None = None

    @property
    def free_bytes(self) -> int:
        """Budget left before the cap is reached."""
        return max(0, self.budget_bytes - self.reserved_bytes)

    @property
    def utilisation(self) -> float:
        """Fraction of the budget currently reserved, in ``[0, 1]``."""
        if self.budget_bytes <= 0:
            return 0.0
        return min(1.0, self.reserved_bytes / self.budget_bytes)

    def as_dict(self) -> dict[str, Any]:
        """Plain-data view for ``--json`` output and for Qt models."""
        return {
            "device": self.device,
            "budget_bytes": self.budget_bytes,
            "reserved_bytes": self.reserved_bytes,
            "free_bytes": self.free_bytes,
            "utilisation": round(self.utilisation, 4),
            "loads": self.loads,
            "evictions": self.evictions,
            "cpu_fallbacks": self.cpu_fallbacks,
            "waits": self.waits,
            "device_free_bytes": self.device_free_bytes,
            "device_total_bytes": self.device_total_bytes,
            "registered": list(self.registered),
            "residents": [
                {
                    "name": r.name,
                    "device": r.device,
                    "vram_bytes": r.vram_bytes,
                    "vram_gb": round(r.vram_bytes / _BYTES_PER_GB, 3),
                    "lease_count": r.lease_count,
                    "in_use": r.in_use,
                    "idle_seconds": round(r.idle_seconds, 2),
                    "pinned": r.pinned,
                    "priority": r.priority,
                    "description": r.description,
                }
                for r in self.residents
            ],
        }

    def to_text(self) -> str:
        """Render the report as Brazilian-Portuguese lines for the UI/logs."""
        used_gb = self.reserved_bytes / _BYTES_PER_GB
        budget_gb = self.budget_bytes / _BYTES_PER_GB
        lines = [
            f"Orcamento de VRAM ({self.device}): "
            f"{used_gb:.2f} / {budget_gb:.2f} GiB ({self.utilisation * 100:.0f}%)",
        ]
        if self.device_total_bytes:
            free_gb = (self.device_free_bytes or 0) / _BYTES_PER_GB
            total_gb = self.device_total_bytes / _BYTES_PER_GB
            lines.append(f"VRAM real livre no dispositivo: {free_gb:.2f} / {total_gb:.2f} GiB")
        if not self.residents:
            lines.append("Nenhum modelo residente.")
        for resident in self.residents:
            state = "em uso" if resident.in_use else f"ocioso ha {resident.idle_seconds:.0f}s"
            flag = " [fixado]" if resident.pinned else ""
            lines.append(
                f"  - {resident.name}: {resident.vram_bytes / _BYTES_PER_GB:.2f} GiB "
                f"em {resident.device}, {state}{flag}"
            )
        lines.append(
            f"Cargas: {self.loads} · Despejos: {self.evictions} · "
            f"Quedas para CPU: {self.cpu_fallbacks} · Esperas: {self.waits}"
        )
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Internal state
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _Resident:
    """Bookkeeping for one loaded model.

    ``recency`` is a monotonically increasing counter rather than a timestamp:
    on Windows ``time.monotonic()`` advances in ~16 ms steps, so several
    acquisitions inside one tick would compare equal and destroy the LRU order.
    ``last_used`` stays a real clock reading, but only for the "idle for N
    seconds" figure shown in :meth:`ModelResidencyManager.budget_report`.
    """

    spec: ModelSpec
    device: str
    reserved_bytes: int
    state: str  # "loading" | "ready"
    lease_count: int
    recency: int
    last_used: float
    loaded_at: float
    on_cpu_fallback: bool
    model: Any = None


@dataclass(frozen=True, slots=True)
class _Placement:
    device: str
    reserved_bytes: int
    cpu_fallback: bool


class _SerialQueue:
    """FIFO gate for models that may not co-reside.

    Reentrant for the *same* model on the same thread; a different model of the
    same group re-entered on the same thread would deadlock, so it raises
    instead of hanging.
    """

    def __init__(self, group: str) -> None:
        """Create an empty queue for ``group``."""
        self.group = group
        self._cv = threading.Condition()
        self._waiting: deque[object] = deque()
        self._holder: object | None = None
        self._holder_thread: int | None = None
        self._holder_name: str | None = None
        self._depth = 0

    def enter(self, name: str, timeout: float) -> object | None:
        """Take the slot, blocking until it is free. Returns a release token."""
        ident = threading.get_ident()
        with self._cv:
            if self._holder is not None and self._holder_thread == ident:
                if self._holder_name != name:
                    raise ResidencyError(
                        f"Impasse evitado: a thread ja detem '{self._holder_name}' do grupo "
                        f"exclusivo '{self.group}' e pediu '{name}'. Modelos do mesmo grupo "
                        f"nao podem ser usados aninhados (ADR-0004)."
                    )
                self._depth += 1
                return None
            token = object()
            self._waiting.append(token)

            def ready() -> bool:
                return self._holder is None and bool(self._waiting) and self._waiting[0] is token

            if not self._cv.wait_for(ready, timeout=timeout):
                self._waiting.remove(token)
                self._cv.notify_all()
                raise ResidencyTimeoutError(
                    f"Tempo esgotado ({timeout:.0f}s) esperando o grupo exclusivo "
                    f"'{self.group}' para carregar '{name}'."
                )
            self._waiting.popleft()
            self._holder = token
            self._holder_thread = ident
            self._holder_name = name
            self._depth = 1
            return token

    def leave(self, token: object | None) -> None:
        """Release the slot taken by :meth:`enter`."""
        with self._cv:
            if token is None:
                self._depth = max(0, self._depth - 1)
                return
            if self._holder is not token:
                return
            self._depth -= 1
            if self._depth > 0:
                return
            self._holder = None
            self._holder_thread = None
            self._holder_name = None
            self._cv.notify_all()

    @property
    def busy(self) -> bool:
        """Whether the slot is currently held."""
        with self._cv:
            return self._holder is not None


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #


class ModelResidencyManager:
    """Single arbiter of GPU memory for every model in the application.

    Args:
        budget_bytes: Hard cap. Defaults to ``runtime.vram_budget_gb``.
        device: Target device string (``"cuda:0"`` / ``"cpu"``). Defaults to
            whatever :func:`caissa.vision.runtime.device.get_device_info`
            actually verified. Injectable so tests never need a GPU.
        allow_cpu_fallback: Global switch. Defaults to
            ``runtime.allow_cpu_fallback``. A spec may still opt out
            individually.
        wait_timeout_s: How long ``acquire`` may block. Defaults to
            ``runtime.residency_wait_timeout_s``.
        empty_cache: Called after each eviction. Defaults to
            ``torch.cuda.empty_cache`` when torch is importable, else a no-op.
        vram_probe: Returns ``(free, total)`` device bytes for the report.
        clock: Monotonic time source, injectable for deterministic tests.
    """

    def __init__(
        self,
        *,
        budget_bytes: int | None = None,
        device: str | None = None,
        allow_cpu_fallback: bool | None = None,
        wait_timeout_s: float | None = None,
        empty_cache: Callable[[], None] | None = None,
        vram_probe: Callable[[], tuple[int, int]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build a manager, reading unset arguments from the configuration."""
        runtime = get_config().runtime
        self._budget_bytes = (
            runtime.vram_budget_bytes if budget_bytes is None else int(budget_bytes)
        )
        if self._budget_bytes <= 0:
            raise ValueError("budget_bytes deve ser positivo")
        self._allow_cpu_fallback = (
            runtime.allow_cpu_fallback if allow_cpu_fallback is None else allow_cpu_fallback
        )
        self._wait_timeout_s = (
            runtime.residency_wait_timeout_s if wait_timeout_s is None else float(wait_timeout_s)
        )
        self._explicit_device = device
        self._device: str | None = device
        self._empty_cache = empty_cache
        self._vram_probe = vram_probe
        self._clock = clock

        self._cv = threading.Condition(threading.RLock())
        self._sequence = 0
        self._specs: dict[str, ModelSpec] = {}
        self._residents: dict[str, _Resident] = {}
        self._queues: dict[str, _SerialQueue] = {}
        self._loads = 0
        self._evictions = 0
        self._cpu_fallbacks = 0
        self._waits = 0

    # -- registry ---------------------------------------------------------- #

    def register(self, spec: ModelSpec, *, replace: bool = False) -> None:
        """Declare a model. Idempotent for an identical spec.

        Args:
            spec: The declaration.
            replace: Allow overwriting an existing, non-resident declaration.

        Raises:
            ModelAlreadyResidentError: If the model is loaded and the new spec
                differs, since its reservation is already accounted for.
        """
        with self._cv:
            existing = self._specs.get(spec.name)
            if existing is not None and existing != spec:
                if spec.name in self._residents:
                    raise ModelAlreadyResidentError(
                        f"'{spec.name}' esta carregado; descarregue-o antes de re-registrar."
                    )
                if not replace:
                    raise ModelAlreadyResidentError(
                        f"'{spec.name}' ja registrado com outra especificacao; "
                        f"use register(..., replace=True)."
                    )
            self._specs[spec.name] = spec
            if spec.exclusive_group and spec.exclusive_group not in self._queues:
                self._queues[spec.exclusive_group] = _SerialQueue(spec.exclusive_group)

    def registered(self) -> tuple[str, ...]:
        """Names of every declared model, in registration order."""
        with self._cv:
            return tuple(self._specs)

    def is_resident(self, name: str) -> bool:
        """Whether ``name`` is currently loaded (in any state)."""
        with self._cv:
            return name in self._residents

    def spec_for(self, name: str) -> ModelSpec:
        """Return the declaration for ``name``."""
        with self._cv:
            spec = self._specs.get(name)
            if spec is None:
                raise ModelNotRegisteredError(name, tuple(self._specs))
            return spec

    # -- device ------------------------------------------------------------ #

    def resolve_device(self) -> str:
        """Determine and memoise the target device, verifying the GPU for real.

        Safe to call eagerly (``scripts/doctor.py`` does) -- any failure inside
        the device layer degrades to ``"cpu"`` rather than propagating.
        """
        try:
            return self._resolve_device()
        except Exception as exc:  # noqa: BLE001 - never let reporting break
            logger.warning("Resolucao de dispositivo falhou (%s); assumindo CPU.", exc)
            with self._cv:
                if self._device is None:
                    self._device = "cpu"
                return self._device

    def _resolve_device(self) -> str:
        """Determine the target device once, verifying it for real."""
        with self._cv:
            if self._device is not None:
                return self._device
        # Imported lazily: the residency manager must be usable (on CPU) in an
        # environment where torch is absent -- see ADR-0003.
        from caissa.vision.runtime.device import (  # noqa: PLC0415 - lazy by design
            get_device_info,
        )

        info = get_device_info()
        resolved = info.torch_device_string if info.usable else "cpu"
        with self._cv:
            if self._device is None:
                self._device = resolved
            return self._device

    def _run_empty_cache(self) -> None:
        if self._empty_cache is not None:
            self._empty_cache()
            return
        from caissa.vision.runtime.device import import_torch  # noqa: PLC0415

        torch = import_torch()
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _probe_vram(self) -> tuple[int, int] | None:
        if self._vram_probe is not None:
            return self._vram_probe()
        if self._explicit_device is not None and not self._explicit_device.startswith("cuda"):
            return None
        try:
            from caissa.vision.runtime.device import vram_status  # noqa: PLC0415

            free_bytes, total_bytes = vram_status()
        except Exception:  # noqa: BLE001 - reporting must never break the caller
            return None
        return (free_bytes, total_bytes) if total_bytes else None

    # -- accounting -------------------------------------------------------- #

    def _reserved_bytes(self) -> int:
        return sum(r.reserved_bytes for r in self._residents.values())

    def _touch(self, resident: _Resident) -> None:
        """Mark a resident as most-recently-used. Call with the lock held."""
        self._sequence += 1
        resident.recency = self._sequence
        resident.last_used = self._clock()

    def _eviction_order(self, *, only_idle: bool) -> list[_Resident]:
        """Residents that may be evicted, most-evictable first.

        Sorted by ``priority`` descending (ADR-0004 makes the LLM the first
        candidate) and then by ``last_used`` ascending -- plain LRU when every
        priority is equal, which is the default.
        """
        candidates = [
            r
            for r in self._residents.values()
            if not r.spec.pinned and r.reserved_bytes > 0 and (not only_idle or r.lease_count == 0)
        ]
        candidates.sort(key=lambda r: (-r.spec.priority, r.recency))
        return candidates

    def _plan(self, spec: ModelSpec, device: str) -> _Placement | None:
        """Decide where ``spec`` should go, evicting as needed.

        Returns ``None`` to mean "cannot place right now, but waiting could
        help". Must be called with the lock held.
        """
        if not device.startswith("cuda") or spec.vram_bytes == 0:
            return _Placement(device, 0, cpu_fallback=False)

        need = spec.vram_bytes
        if need > self._budget_bytes:
            logger.warning(
                "Modelo '%s' declara %.2f GiB, acima do orcamento total de %.2f GiB.",
                spec.name,
                need / _BYTES_PER_GB,
                self._budget_bytes / _BYTES_PER_GB,
            )
            return self._cpu_placement(spec, reason="excede o orcamento total")

        if self._reserved_bytes() + need <= self._budget_bytes:
            return _Placement(device, need, cpu_fallback=False)

        for victim in self._eviction_order(only_idle=True):
            self._evict_locked(victim.spec.name, reason=f"liberar espaco para '{spec.name}'")
            if self._reserved_bytes() + need <= self._budget_bytes:
                return _Placement(device, need, cpu_fallback=False)

        # Nothing idle is left. Would waiting for the busy ones help?
        busy_reclaimable = sum(r.reserved_bytes for r in self._eviction_order(only_idle=False))
        if busy_reclaimable and self._reserved_bytes() - busy_reclaimable + need <= (
            self._budget_bytes
        ):
            return None

        return self._cpu_placement(spec, reason="nao ha VRAM suficiente mesmo apos despejos")

    def _cpu_placement(self, spec: ModelSpec, *, reason: str) -> _Placement:
        """Fall back to CPU, or refuse loudly if fallback is disabled."""
        if not (self._allow_cpu_fallback and spec.allow_cpu_fallback):
            raise VramBudgetExceededError(
                f"'{spec.name}' precisa de {spec.vram_bytes / _BYTES_PER_GB:.2f} GiB mas "
                f"{reason}; o fallback para CPU esta desabilitado "
                f"(runtime.allow_cpu_fallback / ModelSpec.allow_cpu_fallback)."
            )
        self._cpu_fallbacks += 1
        message = (
            f"'{spec.name}' sera carregado na CPU porque {reason} "
            f"(precisa de {spec.vram_bytes / _BYTES_PER_GB:.2f} GiB, orcamento "
            f"{self._budget_bytes / _BYTES_PER_GB:.2f} GiB). O desempenho sera muito menor."
        )
        logger.warning(message)
        warnings.warn(message, VramFallbackWarning, stacklevel=4)
        return _Placement("cpu", 0, cpu_fallback=True)

    def _evict_locked(self, name: str, *, reason: str) -> None:
        """Drop a resident. Must be called with the lock held."""
        resident = self._residents.pop(name, None)
        if resident is None:
            return
        logger.info(
            "Despejando '%s' (%.2f GiB, ocioso ha %.1fs): %s",
            name,
            resident.reserved_bytes / _BYTES_PER_GB,
            self._clock() - resident.last_used,
            reason,
        )
        unloader = resident.spec.unloader
        model = resident.model
        resident.model = None
        self._evictions += 1
        if unloader is not None and model is not None:
            try:
                unloader(model)
            except Exception:
                logger.exception("O descarregador de '%s' falhou; seguindo assim mesmo.", name)
        del model
        self._run_empty_cache()
        self._cv.notify_all()

    # -- acquisition ------------------------------------------------------- #

    def _ensure_loaded(self, spec: ModelSpec, timeout: float) -> _Resident:
        """Load ``spec`` if needed and return it with a lease already counted."""
        device = self._resolve_device()
        deadline = self._clock() + timeout
        placement: _Placement

        while True:
            with self._cv:
                resident = self._residents.get(spec.name)
                if resident is not None and resident.state == "ready":
                    resident.lease_count += 1
                    self._touch(resident)
                    return resident
                if resident is not None:  # another thread is loading it
                    remaining = deadline - self._clock()
                    if remaining <= 0 or not self._cv.wait_for(
                        lambda: self._residents.get(spec.name) is None
                        or self._residents[spec.name].state == "ready",
                        timeout=remaining,
                    ):
                        raise ResidencyTimeoutError(
                            f"Tempo esgotado esperando outra thread carregar '{spec.name}'."
                        )
                    continue

                maybe = self._plan(spec, device)
                if maybe is None:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        raise ResidencyTimeoutError(
                            f"Tempo esgotado ({timeout:.0f}s) esperando VRAM para "
                            f"'{spec.name}'. Modelos em uso no momento: "
                            f"{', '.join(sorted(self._residents)) or '(nenhum)'}."
                        )
                    self._waits += 1
                    self._cv.wait(timeout=remaining)
                    continue

                placement = maybe
                self._sequence += 1
                self._residents[spec.name] = _Resident(
                    spec=spec,
                    device=placement.device,
                    reserved_bytes=placement.reserved_bytes,
                    state="loading",
                    lease_count=1,
                    recency=self._sequence,
                    last_used=self._clock(),
                    loaded_at=self._clock(),
                    on_cpu_fallback=placement.cpu_fallback,
                )
                break

        # The loader is slow (disk + host-to-device copy); it runs outside the
        # lock so other threads can keep using already-resident models.
        try:
            model = spec.loader(placement.device)
        except BaseException:
            with self._cv:
                self._residents.pop(spec.name, None)
                self._cv.notify_all()
            raise

        with self._cv:
            resident = self._residents[spec.name]
            resident.model = model
            resident.state = "ready"
            resident.loaded_at = self._clock()
            self._touch(resident)
            self._loads += 1
            logger.info(
                "Carregado '%s' em %s (%.2f GiB reservados; %.2f/%.2f GiB do orcamento).",
                spec.name,
                placement.device,
                placement.reserved_bytes / _BYTES_PER_GB,
                self._reserved_bytes() / _BYTES_PER_GB,
                self._budget_bytes / _BYTES_PER_GB,
            )
            self._cv.notify_all()
            return resident

    def _release(self, name: str) -> None:
        with self._cv:
            resident = self._residents.get(name)
            if resident is None:
                return
            resident.lease_count = max(0, resident.lease_count - 1)
            self._touch(resident)
            if resident.lease_count == 0:
                self._cv.notify_all()

    @contextmanager
    def acquire(self, name: str, *, timeout: float | None = None) -> Iterator[ModelLease]:
        """Borrow a model, loading it on first use.

        The model cannot be evicted while the lease is held. Always use this as
        a context manager::

            with manager.acquire("square-classifier") as lease:
                logits = lease.model(batch.to(lease.device))

        Args:
            name: A registered model name.
            timeout: Maximum seconds to wait for VRAM or for an exclusive slot.
                Defaults to ``runtime.residency_wait_timeout_s``.

        Yields:
            A :class:`ModelLease`.

        Raises:
            ModelNotRegisteredError: If ``name`` was never registered.
            ResidencyTimeoutError: If the wait exceeded ``timeout``.
            VramBudgetExceededError: If it does not fit and CPU fallback is off.
        """
        spec = self.spec_for(name)
        wait = self._wait_timeout_s if timeout is None else float(timeout)
        queue = self._queues.get(spec.exclusive_group or "")
        token: object | None = None
        if spec.exclusive_group and queue is not None:
            token = queue.enter(name, wait)
        try:
            resident = self._ensure_loaded(spec, wait)
            try:
                yield ModelLease(
                    name=name,
                    model=resident.model,
                    device=resident.device,
                    on_cpu_fallback=resident.on_cpu_fallback,
                )
            finally:
                self._release(name)
        finally:
            if spec.exclusive_group and queue is not None:
                queue.leave(token)

    # -- explicit lifecycle ------------------------------------------------ #

    def preload(self, name: str, *, timeout: float | None = None) -> None:
        """Load a model now instead of on first use, and release it immediately."""
        with self.acquire(name, timeout=timeout):
            pass

    def unload(self, name: str, *, force: bool = False) -> bool:
        """Evict ``name``. Returns ``False`` if it was not resident.

        Args:
            name: Model to evict.
            force: Evict even while leases are held. Dangerous -- only for
                shutdown paths.

        Raises:
            ResidencyError: If leases are held and ``force`` is ``False``.
        """
        with self._cv:
            resident = self._residents.get(name)
            if resident is None:
                return False
            if resident.lease_count > 0 and not force:
                raise ResidencyError(
                    f"'{name}' esta em uso por {resident.lease_count} chamador(es); "
                    f"use unload(force=True) apenas no encerramento."
                )
            self._evict_locked(name, reason="descarregamento explicito")
            return True

    def unload_all(self, *, force: bool = True) -> int:
        """Evict every resident. Returns how many were dropped."""
        with self._cv:
            names = list(self._residents)
            dropped = 0
            for name in names:
                resident = self._residents.get(name)
                if resident is None:
                    continue
                if resident.lease_count > 0 and not force:
                    continue
                self._evict_locked(name, reason="descarregamento total")
                dropped += 1
            return dropped

    def set_budget(self, budget_bytes: int) -> None:
        """Change the cap at runtime, evicting immediately if it shrank."""
        if budget_bytes <= 0:
            raise ValueError("budget_bytes deve ser positivo")
        with self._cv:
            self._budget_bytes = int(budget_bytes)
            for victim in self._eviction_order(only_idle=True):
                if self._reserved_bytes() <= self._budget_bytes:
                    break
                self._evict_locked(victim.spec.name, reason="orcamento reduzido")
            self._cv.notify_all()

    # -- reporting --------------------------------------------------------- #

    @property
    def budget_bytes(self) -> int:
        """Current hard cap, in bytes."""
        with self._cv:
            return self._budget_bytes

    @property
    def reserved_bytes(self) -> int:
        """Sum of the declared cost of every GPU-resident model."""
        with self._cv:
            return self._reserved_bytes()

    def budget_report(self) -> BudgetReport:
        """Snapshot the budget for the UI panel and for ``scripts/doctor.py``."""
        probe = self._probe_vram()
        now = self._clock()
        with self._cv:
            residents = tuple(
                ResidentReport(
                    name=r.spec.name,
                    device=r.device,
                    vram_bytes=r.reserved_bytes,
                    lease_count=r.lease_count,
                    idle_seconds=0.0 if r.lease_count else max(0.0, now - r.last_used),
                    pinned=r.spec.pinned,
                    priority=r.spec.priority,
                    description=r.spec.description,
                )
                for r in sorted(self._residents.values(), key=lambda r: r.spec.name)
            )
            return BudgetReport(
                device=self._device or self._explicit_device or "(nao resolvido)",
                budget_bytes=self._budget_bytes,
                reserved_bytes=self._reserved_bytes(),
                residents=residents,
                registered=tuple(self._specs),
                loads=self._loads,
                evictions=self._evictions,
                cpu_fallbacks=self._cpu_fallbacks,
                waits=self._waits,
                device_free_bytes=probe[0] if probe else None,
                device_total_bytes=probe[1] if probe else None,
            )


# --------------------------------------------------------------------------- #
# Process-wide singleton
# --------------------------------------------------------------------------- #

_SINGLETON_LOCK = threading.Lock()


@dataclass
class _Singleton:
    """Holder for the process-wide manager, so no function needs ``global``."""

    value: ModelResidencyManager | None = None


_SINGLETON = _Singleton()


def get_residency_manager() -> ModelResidencyManager:
    """Return the process-wide manager, creating it on first use."""
    with _SINGLETON_LOCK:
        if _SINGLETON.value is None:
            _SINGLETON.value = ModelResidencyManager()
        return _SINGLETON.value


def reset_residency_manager() -> None:
    """Unload everything and drop the singleton. For tests and shutdown."""
    with _SINGLETON_LOCK:
        if _SINGLETON.value is not None:
            _SINGLETON.value.unload_all(force=True)
        _SINGLETON.value = None
