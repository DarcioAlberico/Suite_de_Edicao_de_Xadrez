"""Typed configuration schema for Caissa Studio.

Why plain dataclasses and ``tomllib`` instead of ``pydantic-settings``
---------------------------------------------------------------------
Three reasons, in order of weight:

1. **The configuration layer has to survive a broken environment.** It is
   imported by ``scripts/doctor.py``, whose entire job is to diagnose an
   environment that may be missing or half-installed. Anything it imports before
   it can print a diagnosis is a way for the diagnosis itself to fail. The only
   import here beyond the standard library is ``platformdirs``, and even that is
   guarded with a stdlib fallback.

2. **The precedence order is unusual and must be explicit.** Layers apply in the
   order *defaults -> user file -> environment -> project file -> runtime
   overrides*, i.e. the most *specific scope* wins: a ``caissa.toml`` sitting in
   a particular working tree beats an environment variable set for the shell
   session, which beats the machine-wide user file. Expressing that in
   ``pydantic-settings`` means overriding ``settings_customise_sources`` anyway,
   at which point the merge is hand-written regardless -- but hidden inside a
   framework instead of being 40 readable lines with per-key provenance.

3. **Provenance is a product requirement, not a nicety.** ``doctor.py`` and the
   UI both report *where* a value came from. Tracking that per key is trivial
   with an explicit merge and awkward with a validation framework that discards
   source information after construction.

``tomllib`` is in the standard library on Python 3.11 (the target, SPEC R5), so
reading TOML costs nothing. Validation lives in ``__post_init__`` and raises
:class:`caissa.core.config.errors.ConfigError` with the dotted key name.

Every section is a frozen dataclass: configuration is immutable once loaded, and
a subsystem that wants a variant uses :func:`dataclasses.replace`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, get_args

from caissa.core.config.errors import ConfigError

__all__ = [
    "APP_NAME",
    "CacheConfig",
    "CaissaConfig",
    "DevicePreference",
    "LlmConfig",
    "PathsConfig",
    "RuntimeConfig",
    "ThemePreference",
    "UiConfig",
    "VisionConfig",
    "default_cache_dir",
    "default_data_dir",
    "default_log_dir",
    "default_models_dir",
]

APP_NAME: Final = "CaissaStudio"

DevicePreference = Literal["auto", "cuda", "cpu"]
ThemePreference = Literal["dark", "light", "system"]

_BYTES_PER_GB: Final = 1024**3
_BYTES_PER_MB: Final = 1024**2
_CAPABILITY_TUPLE_LENGTH: Final = 2


# --------------------------------------------------------------------------- #
# Default locations
# --------------------------------------------------------------------------- #


def _platform_dirs() -> tuple[Path, Path]:
    """Return ``(data_dir, cache_dir)`` for this platform.

    Uses ``platformdirs`` when available and falls back to the standard Windows
    / XDG locations otherwise, so that importing this module never hard-fails on
    a partially installed environment.
    """
    try:
        import platformdirs  # noqa: PLC0415 - optional; stdlib fallback below
    except ImportError:  # pragma: no cover - only on a broken install
        if os.name == "nt":
            local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return local / APP_NAME, local / APP_NAME / "Cache"
        xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return xdg_data / APP_NAME, xdg_cache / APP_NAME
    return (
        Path(platformdirs.user_data_dir(APP_NAME, appauthor=False)),
        Path(platformdirs.user_cache_dir(APP_NAME, appauthor=False)),
    )


def default_data_dir() -> Path:
    """Per-user data directory (library database, user styles, presets)."""
    return _platform_dirs()[0]


def default_cache_dir() -> Path:
    """Per-user cache directory (rendered pages, thumbnails, temporary indexes)."""
    return _platform_dirs()[1]


def default_models_dir() -> Path:
    """Directory holding downloaded model weights (SPEC R4: budgeted, see cache)."""
    return default_data_dir() / "models"


def default_log_dir() -> Path:
    """Directory holding rotating diagnostic logs."""
    return default_data_dir() / "logs"


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ConfigError(f"{name} deve ser maior que zero (recebido: {value!r})")


def _require_range(name: str, value: float, low: float, high: float) -> None:
    if not low <= value <= high:
        raise ConfigError(f"{name} deve estar entre {low} e {high} (recebido: {value!r})")


def _require_literal(name: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} deve ser um de [{options}] (recebido: {value!r})")


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Device selection and the VRAM budget that ADR-0004 hangs off.

    Attributes:
        device: Which device subsystems should target. ``"auto"`` means "CUDA if
            a *real* compute probe succeeds, otherwise CPU" -- never merely
            ``torch.cuda.is_available()`` (ADR-0003).
        cuda_device_index: Index of the CUDA device to use when several exist.
        vram_budget_gb: Hard ceiling for resident model weights, in GiB.
            Default 7.0 per ADR-0004: 8 GiB of VRAM minus roughly 1 GiB left to
            the Windows desktop compositor. This is the number the
            ``ModelResidencyManager`` enforces and the number gate 11.3 measures.
        allow_cpu_fallback: When eviction cannot free enough VRAM, load on CPU
            with a loud warning instead of raising.
        residency_wait_timeout_s: How long an ``acquire`` may block waiting for
            other leases to be released before giving up.
        min_free_disk_gb: ``scripts/doctor.py`` warns below this (F0 risk 3).
        gpu_matmul_budget_ms: F0 gate -- a warm 4096x4096 fp16 matmul must
            complete in less than this.
        min_compute_capability: Lowest CUDA compute capability considered usable.
        worker_processes: Size of the CPU worker pool. Default 5 leaves one of
            the six physical cores of the reference machine for the UI thread.
    """

    device: DevicePreference = "auto"
    cuda_device_index: int = 0
    vram_budget_gb: float = 7.0
    allow_cpu_fallback: bool = True
    residency_wait_timeout_s: float = 120.0
    min_free_disk_gb: float = 20.0
    gpu_matmul_budget_ms: float = 100.0
    min_compute_capability: tuple[int, int] = (7, 0)
    worker_processes: int = 5

    def __post_init__(self) -> None:
        """Validate the section, raising :class:`ConfigError` on bad values."""
        _require_literal("runtime.device", self.device, get_args(DevicePreference))
        if self.cuda_device_index < 0:
            raise ConfigError(
                f"runtime.cuda_device_index nao pode ser negativo "
                f"(recebido: {self.cuda_device_index!r})"
            )
        _require_range("runtime.vram_budget_gb", self.vram_budget_gb, 0.25, 1024.0)
        _require_positive("runtime.residency_wait_timeout_s", self.residency_wait_timeout_s)
        _require_range("runtime.min_free_disk_gb", self.min_free_disk_gb, 0.0, 10_000.0)
        _require_positive("runtime.gpu_matmul_budget_ms", self.gpu_matmul_budget_ms)
        if len(self.min_compute_capability) != _CAPABILITY_TUPLE_LENGTH:
            raise ConfigError(
                "runtime.min_compute_capability deve ter exatamente dois inteiros "
                f"(recebido: {self.min_compute_capability!r})"
            )
        if self.worker_processes < 1:
            raise ConfigError(
                f"runtime.worker_processes deve ser >= 1 (recebido: {self.worker_processes!r})"
            )

    @property
    def vram_budget_bytes(self) -> int:
        """The VRAM ceiling expressed in bytes."""
        return int(self.vram_budget_gb * _BYTES_PER_GB)


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Disk and memory caps. Exists because SPEC R4 leaves only 76 GB free.

    Attributes:
        page_cache_mb: In-memory budget for rendered page pixmaps (LRU).
        thumbnail_cache_mb: In-memory budget for library thumbnails (LRU).
        render_cache_disk_gb: On-disk render cache ceiling.
        index_budget_gb: Ceiling for the SQLite/FTS5 index (ADR-0007).
        model_weights_budget_gb: Ceiling for downloaded weights. SPEC R4 fixes
            the complete weight set at 6 GB.
        max_cached_documents: Upper bound on simultaneously open document caches.
        evict_ratio: Fraction of a cache released in one eviction pass, so that
            eviction is amortised instead of thrashing at the boundary.
    """

    page_cache_mb: int = 2048
    thumbnail_cache_mb: int = 512
    render_cache_disk_gb: float = 8.0
    index_budget_gb: float = 20.0
    model_weights_budget_gb: float = 6.0
    max_cached_documents: int = 32
    evict_ratio: float = 0.25

    def __post_init__(self) -> None:
        """Validate the section, raising :class:`ConfigError` on bad values."""
        _require_positive("cache.page_cache_mb", self.page_cache_mb)
        _require_positive("cache.thumbnail_cache_mb", self.thumbnail_cache_mb)
        _require_positive("cache.render_cache_disk_gb", self.render_cache_disk_gb)
        _require_positive("cache.index_budget_gb", self.index_budget_gb)
        _require_range("cache.model_weights_budget_gb", self.model_weights_budget_gb, 0.1, 64.0)
        if self.max_cached_documents < 1:
            raise ConfigError(
                f"cache.max_cached_documents deve ser >= 1 "
                f"(recebido: {self.max_cached_documents!r})"
            )
        _require_range("cache.evict_ratio", self.evict_ratio, 0.01, 1.0)

    @property
    def page_cache_bytes(self) -> int:
        """In-memory page cache ceiling, in bytes."""
        return self.page_cache_mb * _BYTES_PER_MB

    @property
    def thumbnail_cache_bytes(self) -> int:
        """In-memory thumbnail cache ceiling, in bytes."""
        return self.thumbnail_cache_mb * _BYTES_PER_MB

    @property
    def total_disk_budget_gb(self) -> float:
        """Sum of every on-disk budget -- what doctor compares to free space."""
        return self.render_cache_disk_gb + self.index_budget_gb + self.model_weights_budget_gb


@dataclass(frozen=True, slots=True)
class PathsConfig:
    """Filesystem locations. All are normalised and user-expanded on creation."""

    data_dir: Path = field(default_factory=default_data_dir)
    cache_dir: Path = field(default_factory=default_cache_dir)
    models_dir: Path = field(default_factory=default_models_dir)
    log_dir: Path = field(default_factory=default_log_dir)

    def __post_init__(self) -> None:
        """Expand ``~`` and environment variables in every path."""
        for name in ("data_dir", "cache_dir", "models_dir", "log_dir"):
            raw = getattr(self, name)
            expanded = Path(os.path.expandvars(str(raw))).expanduser()
            object.__setattr__(self, name, expanded)

    def ensure_exists(self) -> None:
        """Create every configured directory. Safe to call repeatedly."""
        for path in (self.data_dir, self.cache_dir, self.models_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class VisionConfig:
    """Thresholds and knobs for the recognition pipeline (SPEC section 6).

    Attributes:
        render_dpi: DPI used to rasterise a page for the geometric/neural paths.
        max_page_dpi: Upper bound the UI may request for a zoomed render.
        detector_confidence_threshold: Minimum score for a board detection to be
            accepted by the arbiter without escalating to the next path.
        square_confidence_threshold: Below this a square is painted amber in the
            review overlay (SPEC section 5.3).
        onnx_worker_enabled: Whether third-party ONNX engines may be used at all.
        onnx_worker_python: Interpreter of the isolated ONNX environment. Empty
            means "not configured". ADR-0003 forbids loading onnxruntime-gpu in
            the main process, so this is always a *separate* interpreter.
    """

    render_dpi: int = 200
    max_page_dpi: int = 400
    detector_confidence_threshold: float = 0.55
    square_confidence_threshold: float = 0.90
    onnx_worker_enabled: bool = False
    onnx_worker_python: str = ""

    def __post_init__(self) -> None:
        """Validate the section, raising :class:`ConfigError` on bad values."""
        _require_range("vision.render_dpi", self.render_dpi, 72, 1200)
        _require_range("vision.max_page_dpi", self.max_page_dpi, 72, 1200)
        if self.max_page_dpi < self.render_dpi:
            raise ConfigError(
                f"vision.max_page_dpi ({self.max_page_dpi}) nao pode ser menor que "
                f"vision.render_dpi ({self.render_dpi})"
            )
        _require_range(
            "vision.detector_confidence_threshold", self.detector_confidence_threshold, 0.0, 1.0
        )
        _require_range(
            "vision.square_confidence_threshold", self.square_confidence_threshold, 0.0, 1.0
        )
        if self.onnx_worker_enabled and not self.onnx_worker_python:
            raise ConfigError(
                "vision.onnx_worker_enabled exige vision.onnx_worker_python apontando para o "
                "interpretador do ambiente isolado (ADR-0003)"
            )


@dataclass(frozen=True, slots=True)
class LlmConfig:
    """Optional local LLM (ADR-0005). The application is fully usable without it."""

    enabled: bool = False
    model_id: str = "gemma-4-e4b"
    quantization: str = "Q4_K_M"
    vram_gb: float = 3.5
    context_tokens: int = 8192

    def __post_init__(self) -> None:
        """Validate the section, raising :class:`ConfigError` on bad values."""
        if not self.model_id:
            raise ConfigError("llm.model_id nao pode ser vazio")
        _require_range("llm.vram_gb", self.vram_gb, 0.1, 64.0)
        _require_range("llm.context_tokens", self.context_tokens, 512, 1_048_576)

    @property
    def vram_bytes(self) -> int:
        """Declared VRAM cost of the LLM, in bytes."""
        return int(self.vram_gb * _BYTES_PER_GB)


@dataclass(frozen=True, slots=True)
class UiConfig:
    """Presentation preferences (SPEC section 10)."""

    theme: ThemePreference = "dark"
    language: str = "pt_BR"
    target_fps: int = 60
    restore_session: bool = True

    def __post_init__(self) -> None:
        """Validate the section, raising :class:`ConfigError` on bad values."""
        _require_literal("ui.theme", self.theme, get_args(ThemePreference))
        if not self.language:
            raise ConfigError("ui.language nao pode ser vazio")
        _require_range("ui.target_fps", self.target_fps, 15, 480)


# --------------------------------------------------------------------------- #
# Root
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CaissaConfig:
    """The complete, validated configuration for one Caissa Studio process.

    Attributes:
        runtime: Device and VRAM budget settings.
        cache: Memory and disk ceilings.
        paths: Filesystem locations.
        vision: Recognition pipeline knobs.
        llm: Optional local LLM settings.
        ui: Presentation preferences.
        provenance: Maps ``"section.field"`` to the name of the layer that
            supplied the effective value (``"defaults"``, ``"user-file"``,
            ``"environment"``, ``"project-file"`` or ``"overrides"``).
        sources: Ordered, human-readable description of every layer consulted.
    """

    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    provenance: dict[str, str] = field(default_factory=dict)
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate invariants that span more than one section."""
        if self.llm.enabled and self.llm.vram_gb > self.runtime.vram_budget_gb:
            raise ConfigError(
                f"llm.vram_gb ({self.llm.vram_gb}) excede runtime.vram_budget_gb "
                f"({self.runtime.vram_budget_gb}); reduza o modelo ou aumente o orcamento "
                f"(ADR-0004)"
            )

    def origin_of(self, dotted_key: str) -> str:
        """Return the layer that produced ``dotted_key`` (e.g. ``runtime.device``)."""
        return self.provenance.get(dotted_key, "defaults")

    def to_dict(self) -> dict[str, dict[str, object]]:
        """Serialise the configuration into plain, TOML-compatible data."""
        out: dict[str, dict[str, object]] = {}
        for section in ("runtime", "cache", "paths", "vision", "llm", "ui"):
            obj = getattr(self, section)
            values: dict[str, object] = {}
            for name in obj.__dataclass_fields__:
                raw = getattr(obj, name)
                if isinstance(raw, Path):
                    values[name] = str(raw)
                elif isinstance(raw, tuple):
                    values[name] = list(raw)
                else:
                    values[name] = raw
            out[section] = values
        return out


SECTION_TYPES: Final[dict[str, type]] = {
    "runtime": RuntimeConfig,
    "cache": CacheConfig,
    "paths": PathsConfig,
    "vision": VisionConfig,
    "llm": LlmConfig,
    "ui": UiConfig,
}
