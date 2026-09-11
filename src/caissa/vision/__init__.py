"""Computer-vision subsystem: detection, rectification, classification, FEN.

The :mod:`caissa.vision.runtime` package underneath is shared infrastructure
rather than pipeline logic: it owns device selection and the VRAM budget, and
every subsystem that touches the GPU -- including OCR and the LLM -- goes
through it (ADR-0003, ADR-0004).
"""

from __future__ import annotations

__all__: list[str] = []
