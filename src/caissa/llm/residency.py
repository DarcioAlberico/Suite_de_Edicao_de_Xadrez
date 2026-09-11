"""Registers the LLM with the one VRAM arbiter (ADR-0004).

The residency manager lives in :mod:`caissa.vision.runtime.residency` and is
owned by another front. This module does not reimplement any of it; it declares
what the LLM costs and how to load and drop it, and hands that declaration over.

Two things make the LLM a special case:

**It is the first eviction candidate.** ADR-0004 says so, because it is the
largest single consumer and the only one that is optional. It therefore
registers with a high ``priority`` and is never ``pinned``.

**Its weights live in another process.** Ollama holds them, so the loader and
unloader are HTTP calls, not ``.to(device)``. That is what makes eviction real:
without :meth:`OllamaRuntime.unload` the manager would decrement a counter while
4.2 GiB stayed resident somewhere it cannot see.

Measured cost, not declared cost
--------------------------------
``gemma4:e4b-it-qat`` at ``num_ctx=4096`` occupies **6190 MiB** of VRAM on the
reference machine: NVML total went from 1016 MiB idle to 7206 MiB with the model
resident, measured in F11 cycle 2 on 2026-09-10. Three numbers have been claimed
for this model and only the last one is a measurement of the thing being
declared:

===========================  ==========  =========================================
ADR-0005 estimate            3.0-3.5 GiB never measured
F11 cycle 1                  4271 MiB    measured against a busier idle baseline
**F11 cycle 2**              **6190 MiB** measured against a 1016 MiB idle desktop
===========================  ==========  =========================================

The figure includes Ollama's own CUDA context, which is real cost on the same
device, so it is what the budget has to reserve.

They do not fit together
------------------------
Also measured in cycle 2, with both paths exercised for real: the recognition
pipeline at six CUDA workers peaks at **6345 MiB** above the same idle baseline.
6190 + 6345 = **12 535 MiB on an 8151 MiB card.** Running them at once does not
produce a graceful degradation, it produces an eviction: with the LLM pinned for
45 minutes and a recognition run started underneath it, the LLM was gone by the
end of the run and recognition ran **17 % slower** (0.1780 s/diagram against
0.1522 s/diagram alone).

So the declaration below is not bookkeeping. At 6190 MiB against ADR-0004's
7.0 GiB budget, the arithmetic alone forbids the LLM from co-residing with a
pinned classifier, and the manager evicts it first because that is what
:data:`LLM_PRIORITY` says. An optimistic declaration would not save memory; it
would move the out-of-memory error to a worse moment.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from caissa.llm.runtime import LlmRuntime, get_runtime

__all__ = [
    "LLM_MODEL_NAME",
    "LLM_PRIORITY",
    "LLM_QUALITY_MODEL_NAME",
    "MEASURED_VISION_VRAM_BYTES",
    "MEASURED_VRAM_BYTES",
    "QUALITY_EXCLUSIVE_GROUP",
    "llm_model_spec",
    "register_llm",
    "unregister_llm",
]

logger = logging.getLogger(__name__)

#: Name the LLM registers under.
LLM_MODEL_NAME: Final = "llm-gemma4-e4b"

#: Name for the opt-in 12B "quality mode" of ADR-0005.
LLM_QUALITY_MODEL_NAME: Final = "llm-gemma4-12b"

#: Measured, not estimated. See the module docstring and F11_REPORT_C2.md 7.
MEASURED_VRAM_BYTES: Final = 6190 * 1024 * 1024

#: What the recognition pipeline costs at six CUDA workers, measured the same
#: day on the same device. Kept here so the "do they fit" arithmetic is
#: readable in one place rather than reconstructed from two reports.
MEASURED_VISION_VRAM_BYTES: Final = 6345 * 1024 * 1024

#: Higher is evicted first. Above anything the vision pipeline will register,
#: which is exactly the ADR-0004 requirement.
LLM_PRIORITY: Final = 100

#: Gemma 4 12B needs ~7.5 GiB and cannot share the budget with the vision
#: pipeline at all, so it declares an exclusive group and is serialised.
QUALITY_EXCLUSIVE_GROUP: Final = "gpu-exclusive"


def llm_model_spec(
    runtime: LlmRuntime | None = None,
    *,
    name: str = LLM_MODEL_NAME,
    vram_bytes: int = MEASURED_VRAM_BYTES,
    exclusive_group: str | None = None,
) -> Any:
    """Build the :class:`ModelSpec` describing the LLM.

    Args:
        runtime: The backend to drive. Defaults to the process runtime.
        name: Registry key.
        vram_bytes: Declared cost. Defaults to the measured figure.
        exclusive_group: Set to :data:`QUALITY_EXCLUSIVE_GROUP` for the 12B
            model, which cannot co-reside with the vision pipeline.

    Returns:
        A ``ModelSpec`` from :mod:`caissa.vision.runtime.residency`.

    Raises:
        ImportError: If the residency manager is not installed. Callers that
            want to degrade should use :func:`register_llm`, which does not
            raise.
    """
    from caissa.vision.runtime.residency import ModelSpec  # noqa: PLC0415 - optional at import time

    engine = runtime if runtime is not None else get_runtime()

    def loader(device: str) -> LlmRuntime:
        """Bring the weights up. ``device`` is informational here.

        Ollama picks its own placement and reports it in ``ollama ps``; the
        manager's job is to have decided that there is room, not to force a
        device string into another process.
        """
        logger.info("carregando LLM '%s' (alvo do gerenciador: %s)", name, device)
        engine.load()
        return engine

    def unloader(_model: object) -> None:
        """Really drop the weights from VRAM, in the other process."""
        engine.unload()

    return ModelSpec(
        name=name,
        vram_bytes=vram_bytes,
        loader=loader,
        unloader=unloader,
        exclusive_group=exclusive_group,
        # CPU inference for a 7.5B multimodal model is minutes per diagram. The
        # honest answer there is "skip the LLM", which every task already does,
        # so a CPU fallback would only convert a fast decline into a slow one.
        allow_cpu_fallback=False,
        pinned=False,
        priority=LLM_PRIORITY,
        description="LLM multimodal local (ADR-0005) -- primeiro candidato a despejo",
    )


def register_llm(
    manager: Any | None = None,
    *,
    runtime: LlmRuntime | None = None,
    name: str = LLM_MODEL_NAME,
    vram_bytes: int = MEASURED_VRAM_BYTES,
    exclusive_group: str | None = None,
) -> bool:
    """Declare the LLM to the residency manager.

    Args:
        manager: The manager. Defaults to the process-wide singleton.
        runtime: Backend override.
        name: Registry key.
        vram_bytes: Declared cost.
        exclusive_group: See :func:`llm_model_spec`.

    Returns:
        ``True`` if registered. ``False`` -- with a log line, never an exception
        -- when the residency manager is unavailable or refuses the spec.
        Registration failing must not take down an application whose LLM is
        optional in the first place.
    """
    try:
        if manager is None:
            from caissa.vision.runtime.residency import (  # noqa: PLC0415 - optional
                get_residency_manager,
            )

            manager = get_residency_manager()
        spec = llm_model_spec(
            runtime, name=name, vram_bytes=vram_bytes, exclusive_group=exclusive_group
        )
        manager.register(spec, replace=True)
    except ImportError as exc:
        logger.info("gerenciador de residencia indisponivel (%s); LLM sem orcamento de VRAM", exc)
        return False
    except Exception as exc:  # noqa: BLE001 - optional subsystem, never fatal
        logger.warning("falha ao registrar o LLM no gerenciador de residencia: %s", exc)
        return False
    logger.info(
        "LLM '%s' registrado: %.2f GiB declarados, prioridade %d (primeiro a ser despejado)",
        name,
        vram_bytes / 1024**3,
        LLM_PRIORITY,
    )
    return True


def unregister_llm(manager: Any | None = None, *, name: str = LLM_MODEL_NAME) -> bool:
    """Evict the LLM now, releasing its VRAM. Returns whether it was resident."""
    try:
        if manager is None:
            from caissa.vision.runtime.residency import (  # noqa: PLC0415 - optional
                get_residency_manager,
            )

            manager = get_residency_manager()
        return bool(manager.unload(name, force=True))
    except Exception as exc:  # noqa: BLE001 - cleanup path
        logger.warning("falha ao descarregar o LLM: %s", exc)
        return False
