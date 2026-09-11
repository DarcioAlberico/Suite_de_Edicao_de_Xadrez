"""The contract every OCR engine adapter implements.

An adapter has three jobs and no more:

1.  Say honestly whether it can run right now (:meth:`available`) and, when it
    cannot, say why in a sentence a non-programmer can act on
    (:meth:`unavailable_reason` — Brazilian Portuguese, because it is shown in
    the UI).
2.  Declare which languages it can actually serve *on this machine* — for
    Tesseract that means which ``traineddata`` files exist, not which languages
    the project theoretically supports.
3.  Turn pixels into an :class:`~caissa.ocr.types.OcrResult` with word and
    character boxes.

Everything else — preprocessing, region cutting, escalation, scoring — belongs
to the pipeline, not to the adapter.  An adapter that preprocesses internally
makes the arbiter's comparison between engines meaningless, because the two
engines would then be scored on different images.

Availability is a *cached* property of the adapter instance, not of the class:
the registry builds an adapter once per process and asks it once, so probing a
missing binary costs one failed ``CreateProcess`` per session rather than one
per page.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from ..types import (
    BBox,
    OcrChar,
    OcrLine,
    OcrResult,
    OcrWord,
    RegionKind,
    empty_result,
)

__all__ = [
    "BBox",
    "OcrChar",
    "OcrEngine",
    "OcrEngineBase",
    "OcrError",
    "OcrLine",
    "OcrResult",
    "OcrWord",
    "RegionKind",
    "EngineCapabilities",
    "EngineLevel",
    "empty_result",
    "normalise_gray",
]


class OcrError(RuntimeError):
    """Raised when an engine that reported itself available then failed.

    Distinct from unavailability on purpose: "Tesseract is not installed" is a
    setup problem the user fixes once, while "Tesseract exited with status 1 on
    this page" is a data problem the arbiter should route around by escalating.
    """

    def __init__(self, engine: str, message: str, *, detail: str = "") -> None:
        super().__init__(f"{engine}: {message}")
        self.engine = engine
        self.message = message
        self.detail = detail


class EngineLevel:
    """Cascade levels from SPEC §7.1.  Lower runs first and costs less."""

    PDF_TEXT_LAYER = 0
    TESSERACT = 1
    PADDLE = 2
    SURYA = 3
    VLM = 4


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    """Static facts about an engine, used by the arbiter to order the cascade
    and by the UI to explain what will happen."""

    level: int
    #: Rough seconds per megapixel on CPU.  Only the ordering matters.
    cost_per_megapixel_s: float
    supports_char_boxes: bool
    supports_confidence: bool
    #: True when the engine handles a full multi-column page by itself; false
    #: when it must be fed one region at a time.
    handles_layout: bool = False
    requires_pdf_page: bool = False
    gpu_capable: bool = False


@runtime_checkable
class OcrEngine(Protocol):
    """Structural interface — adapters need not inherit, only conform."""

    name: str

    def available(self) -> bool:
        """True when :meth:`recognize` can be expected to work right now."""
        ...

    def unavailable_reason(self) -> str | None:
        """pt-BR sentence explaining the unavailability, or ``None``."""
        ...

    def languages(self) -> set[str]:
        """ISO-639-2/T-ish codes this engine can serve on this machine."""
        ...

    def supports_language(self, lang: str) -> bool:
        """True when ``lang`` — possibly a compound such as ``por+eng`` — can
        be served.  Part of the protocol because
        :meth:`~caissa.ocr.engines.registry.EngineRegistry.available` and the
        arbiter both call it on anything registered, so an adapter that omits
        it fails at the first page rather than at registration.
        """
        ...

    def capabilities(self) -> EngineCapabilities:
        ...

    def recognize(
        self,
        image: NDArray[np.uint8],
        *,
        lang: str,
        psm_hint: RegionKind,
    ) -> OcrResult:
        """Recognise one region.  ``image`` is grayscale or BGR, uint8."""
        ...


class OcrEngineBase(abc.ABC):
    """Shared plumbing for adapters: availability caching, language checks,
    timing, and the guard that turns a crash into an empty result plus a
    warning rather than an exception that aborts a 500-page batch."""

    name: str = "base"

    def __init__(self) -> None:
        self._available: bool | None = None
        self._reason: str | None = None
        self._languages: set[str] | None = None

    # -- availability ------------------------------------------------------ #

    @abc.abstractmethod
    def _probe(self) -> tuple[bool, str | None]:
        """Do the real check.  Returns ``(available, pt_BR_reason)``."""

    def available(self) -> bool:
        if self._available is None:
            try:
                self._available, self._reason = self._probe()
            except Exception as exc:  # a probe must never take the app down
                self._available = False
                self._reason = (
                    f"Falha ao verificar o motor {self.name}: {exc}"
                )
        return bool(self._available)

    def unavailable_reason(self) -> str | None:
        self.available()
        return None if self._available else self._reason

    def invalidate(self) -> None:
        """Forget the cached probe — call after the user installs something."""
        self._available = None
        self._reason = None
        self._languages = None

    # -- languages --------------------------------------------------------- #

    @abc.abstractmethod
    def _discover_languages(self) -> set[str]:
        ...

    def languages(self) -> set[str]:
        if self._languages is None:
            if not self.available():
                self._languages = set()
            else:
                try:
                    self._languages = self._discover_languages()
                except Exception:
                    self._languages = set()
        return set(self._languages)

    def supports_language(self, lang: str) -> bool:
        """``lang`` may be a Tesseract-style compound such as ``por+eng``."""
        known = self.languages()
        if not known:
            return False
        return all(part in known for part in lang.split("+") if part)

    # -- capabilities ------------------------------------------------------ #

    @abc.abstractmethod
    def capabilities(self) -> EngineCapabilities:
        ...

    # -- recognition ------------------------------------------------------- #

    @abc.abstractmethod
    def _recognize(
        self,
        image: NDArray[np.uint8],
        *,
        lang: str,
        psm_hint: RegionKind,
    ) -> OcrResult:
        ...

    def recognize(
        self,
        image: NDArray[np.uint8],
        *,
        lang: str = "por",
        psm_hint: RegionKind = RegionKind.PARAGRAPH,
    ) -> OcrResult:
        """Recognise ``image``, never raising for an operational failure.

        A batch of 500 books must not stop because page 312 of book 7 made one
        engine unhappy; the arbiter needs a result object it can score and
        escalate away from.  Programming errors are a different matter and are
        allowed through.
        """
        if not self.available():
            return empty_result(
                self.name, lang,
                region_kind=psm_hint,
                warning=self.unavailable_reason() or
                f"Motor {self.name} indisponível.",
            )
        if image is None or getattr(image, "size", 0) == 0:
            return empty_result(
                self.name, lang,
                region_kind=psm_hint,
                warning="Imagem vazia: nada a reconhecer.",
            )

        started = time.perf_counter()
        try:
            result = self._recognize(image, lang=lang, psm_hint=psm_hint)
        except OcrError as exc:
            return empty_result(
                self.name, lang,
                region_kind=psm_hint,
                duration_s=time.perf_counter() - started,
                warning=f"{exc.message}",
                error_detail=exc.detail,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            return empty_result(
                self.name, lang,
                region_kind=psm_hint,
                duration_s=time.perf_counter() - started,
                warning=f"Falha inesperada no motor {self.name}: {exc}",
            )
        if result.duration_s <= 0.0:
            result = OcrResult(
                engine=result.engine,
                lang=result.lang,
                lines=result.lines,
                region_kind=result.region_kind,
                duration_s=time.perf_counter() - started,
                warnings=result.warnings,
                meta=result.meta,
            )
        return result


# --------------------------------------------------------------------------- #
# Image helpers shared by adapters
# --------------------------------------------------------------------------- #


def normalise_gray(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Return a contiguous single-channel uint8 view of ``image``.

    Adapters must not silently accept float images: a float array in 0..1 sent
    to Tesseract renders as a black page and produces an empty result that
    looks like a hard page rather than a caller mistake.
    """
    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        if arr.dtype.kind == "f":
            hi = float(arr.max()) if arr.size else 1.0
            scale = 255.0 if hi <= 1.0 + 1e-6 else 1.0
            arr = np.clip(arr * scale, 0, 255).astype(np.uint8)
        else:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 3:
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        if arr.shape[2] == 3:
            # BGR (OpenCV order) -> luma.  Coefficients are Rec. 601.
            arr = (0.114 * arr[:, :, 0] + 0.587 * arr[:, :, 1]
                   + 0.299 * arr[:, :, 2]).astype(np.uint8)
        else:
            arr = arr[:, :, 0]
    elif arr.ndim != 2:
        raise ValueError(f"imagem com {arr.ndim} dimensões não é suportada")
    return np.ascontiguousarray(arr)
