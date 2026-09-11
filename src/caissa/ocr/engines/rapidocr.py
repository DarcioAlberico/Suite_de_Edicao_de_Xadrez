"""RapidOCR adapter — the trunk's engine, given a home in the cascade.

Origem: ChessVisionOFF_Puro/src/chess_diagram_ocr/ocr.py
(``RapidOcrRecognizer``, ``_build_rapidocr``, ``filter_by_allowlist``).
Absorvido em 2026-09-07.

Why this file exists at all, since level 2 is already PaddleOCR: RapidOCR is
**the one third-party engine the sibling project actually runs**.  Leaving it
out of the registry would have meant the engine table on this machine listed
four engines, none of which the trunk uses, and quietly implied that the
trunk's text pipeline had no recogniser behind it.  It has one, and this is it.

What changed from the trunk's version:

* the trunk's ``build_recognizer`` catches every exception and returns ``None``,
  so "not installed", "installed but broken" and "disabled in settings" are one
  outcome with one message.  Here they are three, because the answer to each is
  different and the user has to be told which one they are in;
* the trunk's adapter has no notion of language.  RapidOCR's stock models are
  Chinese + English, and it is genuinely poor at the Cyrillic and German
  fraktur in this corpus, so :meth:`languages` advertises what it can do rather
  than everything the caller might ask for;
* ``allowlist`` post-filtering is kept — it is the one thing RapidOCR needs
  that the other engines get for free — but is expressed as a character set on
  the call rather than a module-level helper.

**RapidOCR is not a dependency and must not become one.**  ``rapidocr`` and
``rapidocr_onnxruntime`` both pull in ONNX Runtime.  The CPU wheel is harmless,
but installing the GPU wheel into the main environment is exactly the DLL
collision ADR-0003 was written about, so the install hint below names the CPU
package explicitly and says why.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

from ..types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind
from .base import EngineCapabilities, EngineLevel, OcrEngineBase, OcrError, normalise_gray

__all__ = ["RapidOcrEngine", "RapidOcrConfig", "INSTALL_HINT_PT"]


INSTALL_HINT_PT = (
    "RapidOCR não está instalado. Ele é opcional. É o motor que o projeto "
    "ChessVisionOFF usa, é leve e não precisa de binário externo.\n"
    "  • Para instalar (somente CPU, que é o recomendado nesta máquina):\n"
    "      pip install rapidocr-onnxruntime\n"
    "  • Não instale 'onnxruntime-gpu' neste mesmo ambiente: ele é compilado "
    "contra CUDA 13 e o PyTorch desta máquina contra CUDA 12.8; os dois no "
    "mesmo processo dão erro de DLL ou queda silenciosa para CPU (ADR-0003). "
    "Para RapidOCR na GPU, use o processo trabalhador separado previsto na "
    "ADR-0003."
)

#: Module names tried, in order.  ``rapidocr`` is the 2.x name and
#: ``rapidocr_onnxruntime`` the 1.x one; both are still in the wild and the
#: trunk pins the second.
_MODULES = ("rapidocr_onnxruntime", "rapidocr")

#: What RapidOCR's stock models actually read.  Advertising more would make the
#: registry lie and would let the arbiter send it a Cyrillic page it cannot do.
SUPPORTED_LANGUAGES = frozenset({"eng", "por", "spa", "fra", "ita", "nld", "deu"})


@dataclass(slots=True)
class RapidOcrConfig:
    """Construction arguments for the underlying engine."""

    #: Detection box score threshold.  RapidOCR's own default.
    box_thresh: float = 0.5
    text_score: float = 0.5
    use_angle_cls: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


class RapidOcrEngine(OcrEngineBase):
    """RapidOCR, CPU, opt-in.  Sits at level 2 alongside PaddleOCR."""

    name = "rapidocr"

    def __init__(self, config: RapidOcrConfig | None = None) -> None:
        super().__init__()
        self.config = config or RapidOcrConfig()
        self._engine: Any = None
        self._module: str | None = None

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        first_error: str | None = None
        for module_name in _MODULES:
            try:
                module = __import__(module_name, fromlist=["RapidOCR"])
            except ImportError:
                continue
            except Exception as exc:
                first_error = first_error or f"{module_name}: {exc}"
                continue
            if not hasattr(module, "RapidOCR"):
                first_error = first_error or (
                    f"{module_name} está instalado mas não expõe RapidOCR")
                continue
            self._module = module_name
            return True, None
        if first_error is not None:
            return False, (
                f"RapidOCR está instalado mas não pôde ser carregado "
                f"({first_error}). Reinstale o pacote ou remova-o para que o "
                f"motor seja simplesmente ignorado."
            )
        return False, INSTALL_HINT_PT

    def _discover_languages(self) -> set[str]:
        return set(SUPPORTED_LANGUAGES)

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.PADDLE,
            # Measured by the trunk as materially cheaper than PaddleOCR; it
            # runs a smaller detector and a smaller recogniser.
            cost_per_megapixel_s=1.2,
            supports_char_boxes=False,
            supports_confidence=True,
            handles_layout=False,
            requires_pdf_page=False,
            gpu_capable=True,
        )

    # -- lazy construction ------------------------------------------------- #

    def _instance(self) -> Any:
        if self._engine is not None:
            return self._engine
        if self._module is None:
            self.available()
        if self._module is None:  # pragma: no cover - guarded by the caller
            raise OcrError(self.name, INSTALL_HINT_PT)
        module = __import__(self._module, fromlist=["RapidOCR"])
        try:
            self._engine = module.RapidOCR(**self.config.extra)
        except TypeError:
            # The keyword surface changed between 1.x and 2.x; the no-argument
            # constructor has always worked.
            self._engine = module.RapidOCR()
        return self._engine

    def invalidate(self) -> None:
        super().invalidate()
        self._engine = None
        self._module = None

    # -- recognition ------------------------------------------------------- #

    def _recognize(self, image: NDArray[np.uint8], *, lang: str,
                   psm_hint: RegionKind, allowlist: str = "") -> OcrResult:
        gray = normalise_gray(image)
        rgb = np.repeat(gray[:, :, None], 3, axis=2)
        started = time.perf_counter()
        try:
            raw = self._instance()(rgb)
        except Exception as exc:
            raise OcrError(self.name,
                           f"RapidOCR falhou nesta região: {exc}",
                           detail=str(exc)) from exc

        entries = _entries_of(raw)
        if allowlist:
            entries = _filter_by_allowlist(entries, allowlist)
        lines = _to_lines(entries, psm_hint)
        return OcrResult(
            engine=self.name,
            lang=lang,
            lines=tuple(lines),
            region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            warnings=() if lines else ("Nenhum texto reconhecido nesta região.",),
            meta={
                "module": self._module,
                "image_shape": tuple(int(v) for v in gray.shape),
                "allowlist": allowlist,
            },
        )


# --------------------------------------------------------------------------- #
# Output normalisation
# --------------------------------------------------------------------------- #


def _entries_of(raw: Any) -> list[tuple[Sequence[Any], str, float]]:
    """``(polygon, text, score)`` triples out of whatever RapidOCR returned.

    1.x returns ``(result, elapse)`` where ``result`` is a list of
    ``[polygon, text, score]``; 2.x returns an object with ``.boxes``,
    ``.txts`` and ``.scores``.  Both are accepted, and an unrecognised shape
    yields nothing rather than raising: a version bump in an optional
    dependency must not break the cascade.
    """
    if raw is None:
        return []

    boxes = getattr(raw, "boxes", None)
    texts = getattr(raw, "txts", None)
    scores = getattr(raw, "scores", None)
    if boxes is not None and texts is not None:
        out: list[tuple[Sequence[Any], str, float]] = []
        score_list = list(scores) if scores is not None else []
        for i, (polygon, text) in enumerate(zip(boxes, texts)):
            score = float(score_list[i]) if i < len(score_list) else 0.0
            out.append((polygon, str(text), score))
        return out

    result = raw[0] if isinstance(raw, tuple) and raw else raw
    if not isinstance(result, (list, tuple)):
        return []
    out = []
    for entry in result:
        try:
            polygon, text, score = entry[0], str(entry[1]), float(entry[2])
        except (TypeError, IndexError, ValueError):
            continue
        out.append((polygon, text, score))
    return out


def _filter_by_allowlist(
    entries: Iterable[tuple[Sequence[Any], str, float]],
    allowlist: str,
) -> list[tuple[Sequence[Any], str, float]]:
    """Drop characters outside ``allowlist``.

    RapidOCR has no allowlist of its own — unlike EasyOCR and Tesseract, which
    constrain the decoder — so this is a post-filter and cannot recover a
    character the recogniser never proposed.  It is still worth having for the
    diagram-label case (``a``..``h``, ``1``..``8``), where the alternative is a
    stray glyph becoming a coordinate.
    """
    permitted = set(allowlist)
    out = []
    for polygon, text, score in entries:
        kept = "".join(c for c in text if c in permitted)
        if kept:
            out.append((polygon, kept, score))
    return out


def _to_lines(entries: Sequence[tuple[Sequence[Any], str, float]],
              region_kind: RegionKind) -> list[OcrLine]:
    lines: list[OcrLine] = []
    for index, (polygon, text, score) in enumerate(entries):
        if not text.strip():
            continue
        try:
            xs = [float(p[0]) for p in polygon]
            ys = [float(p[1]) for p in polygon]
        except (TypeError, IndexError, ValueError):
            continue
        if not xs or not ys:
            continue
        box = BBox.from_edges(min(xs), min(ys), max(xs), max(ys))
        words = _split_line(text, box, score, index)
        lines.append(OcrLine(
            words=words, box=box, baseline=None,
            block_index=0, paragraph_index=0, line_index=index,
            kind=region_kind, font_size=box.h,
        ))
    return lines


def _split_line(text: str, box: BBox, confidence: float,
                line_index: int) -> tuple[OcrWord, ...]:
    """Distribute a line box over its words in proportion to their length.

    RapidOCR reports one box per detected line and no word geometry, so this is
    an approximation.  Every character it produces carries
    ``inherited_confidence=True`` so that nothing downstream — the arbiter
    least of all — mistakes an interpolated box for a measured one.
    """
    total = len(text)
    if total == 0:
        return ()
    words: list[OcrWord] = []
    cursor = 0
    for word_index, token in enumerate(text.split()):
        start = text.find(token, cursor)
        if start < 0:
            start = cursor
        cursor = start + len(token)
        x0 = box.x0 + box.w * (start / total)
        x1 = box.x0 + box.w * (cursor / total)
        word_box = BBox.from_edges(x0, box.y0, x1, box.y1)
        share = word_box.w / len(token) if token else 0.0
        chars = tuple(
            OcrChar(text=ch,
                    box=BBox(word_box.x0 + share * i, word_box.y0,
                             share, word_box.h),
                    confidence=confidence, inherited_confidence=True)
            for i, ch in enumerate(token)
        )
        words.append(OcrWord(
            text=token, box=word_box, confidence=confidence, chars=chars,
            block_index=0, paragraph_index=0, line_index=line_index,
            word_index=word_index,
        ))
    return tuple(words)
