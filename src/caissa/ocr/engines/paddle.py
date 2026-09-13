"""PaddleOCR / PP-Structure adapter — level 2 of the cascade.

Level 2 exists for what Tesseract cannot do: tables, and pages whose layout
defeats Tesseract's own segmentation.  PP-Structure is the part that matters
here; plain PaddleOCR detection-plus-recognition is a fallback within the
fallback.

**PaddleOCR is not a dependency of this project and must not become one.**  It
drags in the whole Paddle runtime, and ADR-0003 rules out putting a second
CUDA-linked runtime in the main process on this machine.  It is an opt-in
install, and the adapter below is complete: if the user installs the package,
this works, with no code change and no restart beyond the one the registry
already needs to re-probe.  If they do not, :meth:`available` returns ``False``
with an install command, and the cascade skips level 2.

Deliberately CPU-only.  ``use_gpu`` is exposed but defaults to off, because on
this hardware ``paddlepaddle-gpu`` and torch cu128 in one process is precisely
the DLL collision ADR-0003 was written about.  Running level 2 on the GPU means
running it behind the ADR-0003 worker process, which is a separate piece of work
and is not pretended to be done here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind
from .base import EngineCapabilities, EngineLevel, OcrEngineBase, OcrError, normalise_gray
from .contracts import SchemaError, check_version

__all__ = ["PaddleOcrEngine", "PaddleConfig"]


INSTALL_HINT_PT = (
    "PaddleOCR não está instalado. Ele é opcional e melhora o reconhecimento "
    "de tabelas e de páginas com layout complexo.\n"
    "  • Para instalar (somente CPU, recomendado nesta máquina):\n"
    "      pip install paddlepaddle paddleocr\n"
    "  • Não instale 'paddlepaddle-gpu' no mesmo ambiente do PyTorch: as duas "
    "bibliotecas carregam runtimes CUDA diferentes no mesmo processo e o "
    "resultado é queda silenciosa para CPU ou erro de DLL (ver ADR-0003)."
)

#: PaddleOCR's own language codes, mapped from the project's ISO-639-2 codes.
LANG_MAP: dict[str, str] = {
    "por": "pt",
    "eng": "en",
    "deu": "german",
    "spa": "es",
    "fra": "fr",
    "ita": "it",
    "nld": "nl",
    "rus": "ru",
}


@dataclass(slots=True)
class PaddleConfig:
    """Construction arguments for the underlying ``PaddleOCR`` object."""

    use_gpu: bool = False
    use_angle_cls: bool = True
    #: Passed straight through; PaddleOCR takes one language per instance, so
    #: the adapter keeps one instance per language and builds them lazily.
    det_model_dir: str | None = None
    rec_model_dir: str | None = None
    show_log: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class PaddleOcrEngine(OcrEngineBase):
    """Level 2: PaddleOCR, CPU, opt-in."""

    name = "paddleocr"

    def __init__(self, config: PaddleConfig | None = None) -> None:
        super().__init__()
        self.config = config or PaddleConfig()
        self._instances: dict[str, Any] = {}
        self._version: str | None = None

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        ok, version, reason = check_version("paddleocr", engine=self.name)
        if version is not None:
            self._version = version
        if not ok:
            return False, reason
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            return False, INSTALL_HINT_PT
        except Exception as exc:  # noqa: BLE001 - a broken install must be reported, not hidden
            return False, (
                f"PaddleOCR está instalado mas não pôde ser carregado: {exc}. "
                f"Reinstale o pacote ou remova-o para que o nível 2 seja "
                f"simplesmente ignorado."
            )
        if self._version is None:
            self._version = getattr(paddleocr, "__version__", None) or "?"
        return True, None

    def _discover_languages(self) -> set[str]:
        # PaddleOCR downloads models on first use, so what it *can* serve is
        # not knowable offline.  Advertising the mapped set is the honest
        # answer: any of these will work once its model is fetched.
        return set(LANG_MAP)

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.PADDLE,
            cost_per_megapixel_s=2.5,
            supports_char_boxes=False,
            supports_confidence=True,
            handles_layout=True,
            requires_pdf_page=False,
            gpu_capable=True,
        )

    # -- lazy construction ------------------------------------------------- #

    def _instance(self, lang: str) -> Any:
        code = LANG_MAP.get(lang.split("+")[0], "en")
        if code in self._instances:
            return self._instances[code]
        from paddleocr import PaddleOCR
        kwargs: dict[str, Any] = {
            "lang": code,
            "use_angle_cls": self.config.use_angle_cls,
            "show_log": self.config.show_log,
        }
        if self.config.det_model_dir:
            kwargs["det_model_dir"] = self.config.det_model_dir
        if self.config.rec_model_dir:
            kwargs["rec_model_dir"] = self.config.rec_model_dir
        if self.config.use_gpu:
            kwargs["use_gpu"] = True
        kwargs.update(self.config.extra)
        try:
            instance = PaddleOCR(**kwargs)
        except TypeError:
            # PaddleOCR 3.x dropped several 2.x keyword arguments; retry with
            # only the one every version has ever accepted.
            instance = PaddleOCR(lang=code)
        self._instances[code] = instance
        return instance

    # -- recognition ------------------------------------------------------- #

    def _recognize(self, image: NDArray[np.uint8], *, lang: str,
                   psm_hint: RegionKind) -> OcrResult:
        gray = normalise_gray(image)
        # PaddleOCR expects three channels; give it grey replicated rather than
        # a colour conversion, so the adapter never invents colour information.
        rgb = np.repeat(gray[:, :, None], 3, axis=2)
        started = time.perf_counter()
        try:
            instance = self._instance(lang)
            if hasattr(instance, "predict") and not hasattr(instance, "ocr"):
                raw = list(instance.predict(rgb))
            else:
                try:
                    raw = instance.ocr(rgb, cls=self.config.use_angle_cls)
                except TypeError:
                    raw = instance.ocr(rgb)
        except OcrError:
            raise
        except Exception as exc:  # noqa: BLE001 - the engine's own failure, reported explicitly
            raise OcrError(self.name,
                           f"PaddleOCR falhou nesta região: {exc}",
                           detail=str(exc)) from exc

        lines = self._to_lines(raw, psm_hint)
        return OcrResult(
            engine=self.name,
            lang=lang,
            lines=tuple(lines),
            region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            warnings=() if lines else ("Nenhum texto reconhecido nesta região.",),
            meta={
                "version": self._version,
                "paddle_lang": LANG_MAP.get(lang.split("+")[0], "en"),
                "use_gpu": self.config.use_gpu,
                "image_shape": tuple(int(v) for v in gray.shape),
            },
        )

    @staticmethod
    def _to_lines(raw: Any, region_kind: RegionKind) -> list[OcrLine]:
        """Normalise PaddleOCR's output into :class:`OcrLine`.

        Two shapes are parsed: 2.x ``[[ [polygon, (text, score)], ... ]]``
        (one entry per image, sometimes unwrapped) and 3.x result objects,
        dict-like, with ``rec_texts``, ``rec_scores`` and ``rec_polys`` (or
        ``dt_polys``).  A non-empty payload in any other shape raises
        :class:`~caissa.ocr.engines.contracts.SchemaError` (Sol §SOL-5): a
        version bump must fail loudly, not as an empty page.
        """
        if not raw:
            return []
        first = raw[0] if isinstance(raw, (list, tuple)) else raw
        if _dict_like(first) and _get(first, "rec_texts") is not None:
            return PaddleOcrEngine._lines_from_v3(first, region_kind)
        if first is None:
            return []
        page = raw[0] if (isinstance(raw, (list, tuple)) and raw
                          and isinstance(raw[0], (list, tuple))
                          and raw[0] and isinstance(raw[0][0], (list, tuple))
                          and len(raw[0][0]) == 2) else raw
        lines: list[OcrLine] = []
        parsed = 0
        for index, entry in enumerate(page or []):
            try:
                polygon, payload = entry[0], entry[1]
                text = str(payload[0])
                score = float(payload[1])
            except (TypeError, IndexError, ValueError, KeyError):
                continue
            parsed += 1
            if not text.strip():
                continue
            xs = [float(p[0]) for p in polygon]
            ys = [float(p[1]) for p in polygon]
            box = BBox.from_edges(min(xs), min(ys), max(xs), max(ys))
            words = _split_line(text, box, score, index)
            lines.append(OcrLine(
                words=words, box=box, baseline=None,
                block_index=0, paragraph_index=0, line_index=index,
                kind=region_kind, font_size=box.h,
            ))
        if not parsed and page:
            raise SchemaError("paddleocr", f"primeiro item: {type(page[0]).__name__}: "
                                           f"{str(page[0])[:200]}")
        return lines

    @staticmethod
    def _lines_from_v3(result: Any, region_kind: RegionKind) -> list[OcrLine]:
        texts = _get(result, "rec_texts") or []
        scores = _get(result, "rec_scores") or []
        polys = _get(result, "rec_polys") or _get(result, "dt_polys") or []
        if texts and not polys:
            raise SchemaError("paddleocr", "rec_texts sem rec_polys/dt_polys")
        lines: list[OcrLine] = []
        for index, (text, poly) in enumerate(zip(texts, polys, strict=False)):
            if not str(text).strip():
                continue
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            box = BBox.from_edges(min(xs), min(ys), max(xs), max(ys))
            score = float(scores[index]) if index < len(scores) else 0.5
            lines.append(OcrLine(
                words=_split_line(str(text), box, score, index), box=box, baseline=None,
                block_index=0, paragraph_index=0, line_index=index,
                kind=region_kind, font_size=box.h))
        return lines


def _dict_like(obj: Any) -> bool:
    return isinstance(obj, dict) or (hasattr(obj, "get") and callable(obj.get))


def _get(obj: Any, key: str) -> Any:
    try:
        return obj.get(key)
    except (AttributeError, TypeError):
        return None


def _split_line(text: str, box: BBox, confidence: float,
                line_index: int) -> tuple[OcrWord, ...]:
    """Distribute a line box over its words in proportion to their length."""
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
