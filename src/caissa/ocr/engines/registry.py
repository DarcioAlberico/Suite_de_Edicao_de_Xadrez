"""Discovery and lazy construction of OCR engines.

Two rules shape this module.

**Nothing is imported until it is asked for.**  Registration stores a factory,
not an instance, so importing :mod:`caissa.ocr` does not import PaddleOCR,
Surya, PyMuPDF or PIL, and does not shell out to look for Tesseract.  On a
machine with the optional engines installed those imports cost seconds and
hundreds of megabytes of resident memory; on a machine without them they cost a
traceback.  Neither belongs in application start-up.

**An engine that cannot run is a fact to report, not an error to raise.**
:meth:`EngineRegistry.describe` returns a row per engine — available or not,
with the reason and the install instructions in Brazilian Portuguese — because
"OCR did nothing" is the single most confusing thing this subsystem can do to a
user, and the answer is nearly always "Tesseract is installed but not on PATH"
or "you asked for Russian and only English is installed".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterator

from .base import EngineCapabilities, EngineLevel, OcrEngine

__all__ = [
    "EngineRegistry",
    "EngineInfo",
    "EngineFactory",
    "default_registry",
    "available_engines",
    "describe_engines",
]

LOGGER = logging.getLogger("caissa.ocr.registry")

EngineFactory = Callable[[], OcrEngine]


@dataclass(frozen=True, slots=True)
class EngineInfo:
    """A row of the engine table, for the UI and for ``scripts/doctor.py``."""

    name: str
    level: int
    available: bool
    reason: str | None
    languages: tuple[str, ...]
    capabilities: EngineCapabilities | None
    optional: bool
    error: str | None = None

    def describe_pt(self) -> str:
        head = f"Nível {self.level} · {self.name}: "
        if self.available:
            langs = ", ".join(self.languages[:8]) or "—"
            more = f" (+{len(self.languages) - 8})" if len(self.languages) > 8 else ""
            return head + f"disponível. Idiomas: {langs}{more}."
        tail = self.reason or "indisponível."
        if self.optional:
            tail = "opcional e não instalado. " + tail
        return head + tail


@dataclass(slots=True)
class _Registration:
    name: str
    level: int
    factory: EngineFactory
    optional: bool
    instance: OcrEngine | None = None
    error: str | None = None


class EngineRegistry:
    """Holds engine factories and builds each at most once."""

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}

    # -- registration ------------------------------------------------------ #

    def register(self, name: str, level: int, factory: EngineFactory, *,
                 optional: bool = False, replace: bool = False) -> None:
        if name in self._registrations and not replace:
            raise ValueError(f"motor '{name}' já está registrado")
        self._registrations[name] = _Registration(
            name=name, level=level, factory=factory, optional=optional)

    def unregister(self, name: str) -> None:
        self._registrations.pop(name, None)

    @property
    def names(self) -> tuple[str, ...]:
        """Registered names, ordered by cascade level then name.

        The ordering is defined here rather than left to insertion order so
        that the arbiter's cascade cannot change because an import moved.
        """
        return tuple(
            r.name for r in sorted(self._registrations.values(),
                                   key=lambda r: (r.level, r.name))
        )

    def __contains__(self, name: object) -> bool:
        return name in self._registrations

    def __iter__(self) -> Iterator[str]:
        return iter(self.names)

    # -- construction ------------------------------------------------------ #

    def get(self, name: str) -> OcrEngine | None:
        """Build (once) and return the engine, or ``None`` if it cannot be built.

        A factory that raises is recorded and never retried in this process:
        an engine whose import fails will fail identically on every page, and
        re-raising it per region would flood the log and slow the batch.
        """
        registration = self._registrations.get(name)
        if registration is None:
            return None
        if registration.instance is not None:
            return registration.instance
        if registration.error is not None:
            return None
        try:
            registration.instance = registration.factory()
        except Exception as exc:
            registration.error = str(exc)
            LOGGER.warning("motor '%s' não pôde ser construído: %s", name, exc)
            return None
        return registration.instance

    def engines(self) -> list[OcrEngine]:
        """Every engine that could be constructed, in cascade order."""
        out: list[OcrEngine] = []
        for name in self.names:
            engine = self.get(name)
            if engine is not None:
                out.append(engine)
        return out

    def available(self, *, lang: str | None = None) -> list[OcrEngine]:
        """Engines that can run right now, optionally for a given language."""
        out: list[OcrEngine] = []
        for engine in self.engines():
            if not engine.available():
                continue
            if lang is not None and not engine.supports_language(lang):
                continue
            out.append(engine)
        return out

    def invalidate(self) -> None:
        """Forget every probe — call after the user installs something.

        Instances are kept: re-probing is cheap, rebuilding a model is not.
        """
        for registration in self._registrations.values():
            registration.error = None
            engine = registration.instance
            invalidate = getattr(engine, "invalidate", None)
            if callable(invalidate):
                invalidate()

    # -- reporting --------------------------------------------------------- #

    def describe(self) -> list[EngineInfo]:
        """One row per registered engine, cheap enough to call from the UI."""
        rows: list[EngineInfo] = []
        for name in self.names:
            registration = self._registrations[name]
            engine = self.get(name)
            if engine is None:
                rows.append(EngineInfo(
                    name=name, level=registration.level, available=False,
                    reason=(f"o motor não pôde ser carregado: "
                            f"{registration.error}"
                            if registration.error else "motor não construído"),
                    languages=(), capabilities=None,
                    optional=registration.optional, error=registration.error,
                ))
                continue
            ok = engine.available()
            rows.append(EngineInfo(
                name=engine.name,
                level=engine.capabilities().level,
                available=ok,
                reason=None if ok else engine.unavailable_reason(),
                languages=tuple(sorted(engine.languages())) if ok else (),
                capabilities=engine.capabilities(),
                optional=registration.optional,
            ))
        return rows

    def describe_pt(self) -> str:
        return "\n".join(row.describe_pt() for row in self.describe())


# --------------------------------------------------------------------------- #
# Built-in registrations
# --------------------------------------------------------------------------- #


def _make_pdf_text_layer() -> OcrEngine:
    from .pdf_text_layer import PdfTextLayerEngine
    return PdfTextLayerEngine()


def _make_tesseract() -> OcrEngine:
    from .tesseract import TesseractEngine
    return TesseractEngine()


#: Sol §SOL-5 / ADR-0003: the engines that bring their own runtime (Paddle's
#: inference runtime, Surya's torch) run in an isolated worker process by
#: default, so a crash or a CUDA collision in one of them costs a page, not
#: the batch.  ``CAISSA_OCR_INPROCESS=1`` hosts them in-process (debugging).
ISOLATED_BY_DEFAULT = ("paddleocr", "paddle_structure", "surya")


def _isolate(name: str, direct: Callable[[], OcrEngine]) -> OcrEngine:
    import os

    if os.environ.get("CAISSA_OCR_INPROCESS") == "1":
        return direct()
    from .worker import IsolatedEngine
    return IsolatedEngine(hosted=name)


def _make_paddle() -> OcrEngine:
    from .paddle import PaddleOcrEngine
    return _isolate("paddleocr", PaddleOcrEngine)


def _make_paddle_structure() -> OcrEngine:
    from .paddle_structure import PaddleStructureEngine
    return _isolate("paddle_structure", PaddleStructureEngine)


def _make_rapidocr() -> OcrEngine:
    from .rapidocr import RapidOcrEngine
    return RapidOcrEngine()


def _make_surya() -> OcrEngine:
    from .surya import SuryaEngine
    return _isolate("surya", SuryaEngine)


def build_default_registry() -> EngineRegistry:
    """The cascade of SPEC §7.1, levels 0 to 3.

    Level 4 (the VLM) is deliberately absent: it belongs to front F11, it is
    optional by ADR-0005, and registering a stub for it here would make the
    engine table promise something no code behind it delivers.
    """
    registry = EngineRegistry()
    registry.register("pdf_text_layer", EngineLevel.PDF_TEXT_LAYER,
                      _make_pdf_text_layer)
    registry.register("tesseract", EngineLevel.TESSERACT, _make_tesseract)
    # Two engines share level 2.  ``names`` orders ties by name, so the cascade
    # is ``paddleocr`` then ``rapidocr`` — deterministic, and the order is a
    # property of this table rather than of import order.  RapidOCR is here
    # because it is the recogniser the sibling ChessVisionOFF project actually
    # runs; omitting it would have made the engine table on this machine
    # describe a cascade nobody uses.
    registry.register("paddleocr", EngineLevel.PADDLE, _make_paddle,
                      optional=True)
    # Sol §SOL-5: PP-StructureV3 is a distinct backend from plain PaddleOCR
    # — the layout engine the router sends tables to.
    registry.register("paddle_structure", EngineLevel.PADDLE, _make_paddle_structure,
                      optional=True)
    registry.register("rapidocr", EngineLevel.PADDLE, _make_rapidocr,
                      optional=True)
    registry.register("surya", EngineLevel.SURYA, _make_surya, optional=True)
    return registry


_DEFAULT: EngineRegistry | None = None


def default_registry() -> EngineRegistry:
    """Process-wide registry, built on first use."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = build_default_registry()
    return _DEFAULT


def available_engines(lang: str | None = None) -> list[OcrEngine]:
    return default_registry().available(lang=lang)


def describe_engines() -> list[EngineInfo]:
    return default_registry().describe()
