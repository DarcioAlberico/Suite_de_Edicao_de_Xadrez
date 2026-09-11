"""OCR engine adapters (SPEC §7.1 cascade)."""

from .base import (
    EngineCapabilities,
    EngineLevel,
    OcrEngine,
    OcrEngineBase,
    OcrError,
)

__all__ = [
    "EngineCapabilities",
    "EngineLevel",
    "OcrEngine",
    "OcrEngineBase",
    "OcrError",
]

from .registry import (
    EngineInfo,
    EngineRegistry,
    build_default_registry,
    default_registry,
)

__all__ += [
    "EngineInfo",
    "EngineRegistry",
    "build_default_registry",
    "default_registry",
]
