"""Shared GPU runtime: device selection and VRAM residency.

Two rules hold for the whole application:

1. Nobody calls ``torch.device(...)`` or ``.to("cuda")`` directly. Ask
   :func:`caissa.vision.runtime.device.get_device`, which only returns a CUDA
   device after a real kernel has executed successfully (ADR-0003).
2. Nobody keeps model weights alive on their own. Register a
   :class:`~caissa.vision.runtime.residency.ModelSpec` and borrow the model
   through :meth:`~caissa.vision.runtime.residency.ModelResidencyManager.acquire`
   so the 7 GiB budget stays enforced (ADR-0004).
"""

from __future__ import annotations

from caissa.vision.runtime.device import (
    ComputeProbeResult,
    DeviceInfo,
    DeviceUnavailableError,
    diagnose_cuda_error,
    get_device,
    get_device_info,
    import_torch,
    probe_real_compute,
    reset_device_cache,
    vram_status,
)
from caissa.vision.runtime.residency import (
    BudgetReport,
    ModelLease,
    ModelResidencyManager,
    ModelSpec,
    ResidencyError,
    ResidencyTimeoutError,
    ResidentReport,
    VramBudgetExceededError,
    VramFallbackWarning,
    get_residency_manager,
    gigabytes,
    megabytes,
    reset_residency_manager,
)

__all__ = [
    "BudgetReport",
    "ComputeProbeResult",
    "DeviceInfo",
    "DeviceUnavailableError",
    "ModelLease",
    "ModelResidencyManager",
    "ModelSpec",
    "ResidencyError",
    "ResidencyTimeoutError",
    "ResidentReport",
    "VramBudgetExceededError",
    "VramFallbackWarning",
    "diagnose_cuda_error",
    "get_device",
    "get_device_info",
    "get_residency_manager",
    "gigabytes",
    "import_torch",
    "megabytes",
    "probe_real_compute",
    "reset_device_cache",
    "reset_residency_manager",
    "vram_status",
]
