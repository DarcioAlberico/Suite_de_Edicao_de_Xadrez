"""Surya adapter — level 3 of the cascade.

Level 3 is for what levels 1 and 2 do badly: non-Latin script, and pages whose
reading order is genuinely hard.  For this product that means Russian above all
— a large share of the serious chess literature is Russian, and Cyrillic on a
1970s Soviet print run is exactly where Tesseract's Latin-tuned defaults give
out.  Surya is a document OCR model rather than a line recogniser, so it brings
its own layout and reading-order model with it.

Like PaddleOCR, **not a dependency**: Surya pulls in torch and a set of model
weights, and the weights alone would violate the disk constraint (SPEC §2, R4)
if they shipped in the installer.  Opt-in, fully implemented here, skipped
cleanly when absent.

Surya is a torch model, so unlike level 2 it can share the process with the
project's own torch cu128 build — ADR-0003 is about ONNX Runtime, not about
torch.  It still defaults to CPU here, for the reason stated in the F5 brief:
correctness first, and a second torch model competing for the 8 GB budget is a
question for the residency manager of ADR-0004, not for this adapter to answer
on its own.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

from ..types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind
from .base import EngineCapabilities, EngineLevel, OcrEngineBase, OcrError, normalise_gray
from .contracts import SchemaError, check_version

__all__ = ["SuryaEngine", "SuryaConfig"]


INSTALL_HINT_PT = (
    "Surya não está instalado. Ele é opcional e é o motor mais forte para "
    "russo, grego e outros alfabetos não latinos.\n"
    "  • Para instalar:\n"
    "      pip install surya-ocr\n"
    "  • Os pesos do modelo são baixados na primeira execução e ocupam alguns "
    "gigabytes; verifique o espaço livre em disco antes.\n"
    "  • Mantenha o modo CPU nesta máquina, a menos que o gerenciador de "
    "residência de modelos (ADR-0004) tenha reservado VRAM para ele."
)

#: Surya uses ISO-639-1.
LANG_MAP: dict[str, str] = {
    "por": "pt", "eng": "en", "deu": "de", "spa": "es",
    "fra": "fr", "ita": "it", "nld": "nl", "rus": "ru",
}


@dataclass(slots=True)
class SuryaConfig:
    device: str = "cpu"
    dtype: str = "float32"
    batch_size: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class SuryaEngine(OcrEngineBase):
    """Level 3: Surya, CPU by default, opt-in."""

    name = "surya"

    def __init__(self, config: SuryaConfig | None = None) -> None:
        super().__init__()
        self.config = config or SuryaConfig()
        self._predictor: Any = None
        self._api: str = ""
        self._version: str | None = None

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        ok, version, reason = check_version("surya-ocr", engine=self.name)
        self._version = version
        if not ok:
            return False, reason
        try:
            import surya  # noqa: F401
        except ImportError:
            return False, INSTALL_HINT_PT
        except Exception as exc:
            return False, (
                f"Surya está instalado mas não pôde ser carregado: {exc}. "
                f"Reinstale o pacote ou remova-o para que o nível 3 seja "
                f"simplesmente ignorado."
            )
        # Surya has reorganised its public API more than once.  Detect which
        # shape is present now rather than pinning a version: the whole point
        # of an opt-in engine is that the user's version is not ours to choose.
        for module, attribute, tag in (
            ("surya.foundation", "FoundationPredictor", "foundation"),
            ("surya.recognition", "RecognitionPredictor", "recognition"),
            ("surya.ocr", "run_ocr", "run_ocr"),
        ):
            try:
                mod = __import__(module, fromlist=[attribute])
            except Exception:
                continue
            if hasattr(mod, attribute):
                self._api = tag
                break
        if not self._api:
            return False, (
                "Surya está instalado, mas nenhuma das APIs conhecidas "
                "(RecognitionPredictor, FoundationPredictor, run_ocr) foi "
                "encontrada. A versão instalada não é compatível com este "
                "adaptador."
            )
        return True, None

    def _discover_languages(self) -> set[str]:
        return set(LANG_MAP)

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.SURYA,
            cost_per_megapixel_s=6.0,
            supports_char_boxes=False,
            supports_confidence=True,
            handles_layout=True,
            requires_pdf_page=False,
            gpu_capable=True,
        )

    # -- lazy construction ------------------------------------------------- #

    def _load(self) -> Any:
        if self._predictor is not None:
            return self._predictor
        if self._api == "recognition":
            from surya.detection import DetectionPredictor
            from surya.recognition import RecognitionPredictor
            self._predictor = (RecognitionPredictor(), DetectionPredictor())
        elif self._api == "foundation":
            from surya.detection import DetectionPredictor
            from surya.foundation import FoundationPredictor
            from surya.recognition import RecognitionPredictor
            foundation = FoundationPredictor()
            self._predictor = (RecognitionPredictor(foundation),
                               DetectionPredictor())
        else:
            from surya.model.detection.model import load_model as load_det
            from surya.model.detection.model import load_processor as load_det_proc
            from surya.model.recognition.model import load_model as load_rec
            from surya.model.recognition.processor import load_processor as load_rec_proc
            self._predictor = (load_det(), load_det_proc(),
                               load_rec(), load_rec_proc())
        return self._predictor

    # -- recognition ------------------------------------------------------- #

    def _recognize(self, image: NDArray[np.uint8], *, lang: str,
                   psm_hint: RegionKind) -> OcrResult:
        from PIL import Image

        gray = normalise_gray(image)
        pil = Image.fromarray(gray).convert("RGB")
        codes = [LANG_MAP.get(part, "en")
                 for part in lang.split("+") if part in LANG_MAP] or ["en"]
        started = time.perf_counter()

        try:
            predictions = self._predict(pil, codes)
        except Exception as exc:
            raise OcrError(self.name,
                           f"Surya falhou nesta região: {exc}",
                           detail=str(exc)) from exc

        lines = self._to_lines(predictions, psm_hint)
        return OcrResult(
            engine=self.name,
            lang=lang,
            lines=tuple(lines),
            region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            warnings=() if lines else ("Nenhum texto reconhecido nesta região.",),
            meta={
                "api": self._api,
                "version": self._version,
                "device": self.config.device,
                "surya_langs": codes,
                "image_shape": tuple(int(v) for v in gray.shape),
            },
        )

    def _predict(self, pil: Any, codes: Sequence[str]) -> Any:
        loaded = self._load()
        if self._api in ("recognition", "foundation"):
            recognition, detection = loaded
            try:
                return recognition([pil], det_predictor=detection)
            except TypeError:
                return recognition([pil], [codes], detection)
        from surya.ocr import run_ocr
        det_model, det_proc, rec_model, rec_proc = loaded
        return run_ocr([pil], [list(codes)], det_model, det_proc,
                       rec_model, rec_proc)

    @staticmethod
    def _to_lines(predictions: Any, region_kind: RegionKind) -> list[OcrLine]:
        """Normalise Surya's ``OCRResult`` objects into :class:`OcrLine`.

        Surya 0.13+ reports ``chars`` per text line — each with its own
        ``bbox`` and ``confidence`` — and those are used when present, so the
        character boxes are measured, not interpolated.  Older shapes (a
        line with ``text``/``bbox``/``confidence`` only, or dicts) are still
        read.  A page object with none of the known fields raises
        :class:`~caissa.ocr.engines.contracts.SchemaError` (Sol §SOL-5).
        """
        if not predictions:
            return []
        page = predictions[0]
        raw_lines = getattr(page, "text_lines", None)
        if raw_lines is None and isinstance(page, dict):
            raw_lines = page.get("text_lines")
        if raw_lines is None:
            raise SchemaError("surya", f"resultado {type(page).__name__} sem text_lines")
        if not raw_lines:
            return []

        lines: list[OcrLine] = []
        for index, item in enumerate(raw_lines):
            get = (item.get if isinstance(item, dict)
                   else (lambda key, _i=item: getattr(_i, key, None)))
            text, bbox, confidence = get("text"), get("bbox"), get("confidence")
            if text is None and bbox is None:
                raise SchemaError("surya", f"linha {type(item).__name__} sem text/bbox")
            if not text or not str(text).strip() or not bbox or len(bbox) < 4:
                continue
            score = float(confidence) if confidence is not None else 0.5
            box = BBox.from_edges(float(bbox[0]), float(bbox[1]),
                                  float(bbox[2]), float(bbox[3]))
            words = _words_from_chars(get("chars"), box, score, index) or _split_line(
                str(text), box, score, index)
            lines.append(OcrLine(
                words=words, box=box, baseline=None,
                block_index=0, paragraph_index=0, line_index=index,
                kind=region_kind, font_size=box.h,
            ))
        return lines


def _words_from_chars(chars: Any, line_box: BBox, line_confidence: float,
                      line_index: int) -> tuple[OcrWord, ...]:
    """Words from Surya's per-character output, when the version has it."""
    if not chars:
        return ()
    words: list[OcrWord] = []
    current: list[OcrChar] = []

    def flush() -> None:
        if not current:
            return
        box = BBox.union_of([c.box for c in current])
        confidence = sum(c.confidence for c in current) / len(current)
        words.append(OcrWord(text="".join(c.text for c in current), box=box,
                             confidence=confidence, chars=tuple(current), block_index=0,
                             paragraph_index=0, line_index=line_index, word_index=len(words)))
        current.clear()

    for item in chars:
        get = item.get if isinstance(item, dict) else (lambda key, _i=item: getattr(_i, key, None))
        text = get("text")
        bbox = get("bbox")
        if text is None or bbox is None or len(bbox) < 4:
            return ()
        if str(text).isspace():
            flush()
            continue
        confidence = get("confidence")
        current.append(OcrChar(
            text=str(text), box=BBox.from_edges(*(float(v) for v in bbox[:4])),
            confidence=float(confidence) if confidence is not None else line_confidence,
            inherited_confidence=confidence is None))
    flush()
    return tuple(words)


def _split_line(text: str, box: BBox, confidence: float,
                line_index: int) -> tuple[OcrWord, ...]:
    """Distribute a line box over its words in proportion to their length.

    Surya recognises whole lines and reports no word geometry, so the word and
    character boxes below are interpolated.  They are marked
    ``inherited_confidence=True`` so that a consumer needing true glyph
    geometry — the notation corrector, when it wants to point at one character —
    can tell that this engine cannot provide it.
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
