"""Caissa Studio -- chess material editing, recognition and publishing suite.

The package is organised by subsystem, mirroring section 4 of ``docs/SPEC.md``:

``caissa.core``
    Application core: layered configuration, domain model, events. Pure Python,
    no heavy native dependencies, held to ``mypy --strict``.
``caissa.vision``
    Computer-vision pipeline plus the shared runtime layer (device selection and
    VRAM residency management) that every GPU-touching subsystem must go through.
``caissa.ingest`` / ``caissa.ocr`` / ``caissa.index`` / ``caissa.export``
    Importers, text recognition, search index and the five output formats.
``caissa.typeset`` / ``caissa.ui`` / ``caissa.llm``
    Chess typography, the PySide6 shell and the optional local LLM.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
