"""PP-StructureV3 adapter — the layout backend of Sol §SOL-5.

The plain PaddleOCR adapter (:mod:`caissa.ocr.engines.paddle`) is a line
recogniser: detection boxes plus text.  PP-StructureV3 is PaddleOCR 3.x's
document pipeline — layout detection with labelled regions (text, title,
table, figure, caption, header, footer, number), reading order over those
regions, and the OCR of each — and it is what Sol routes tables and complex
layouts to.  Until this module the registry's "PaddleOCR" promised structure
it did not deliver (Sol §4, "PaddleOCR não implementa realmente
PP-StructureV3"); now the two are distinct backends with distinct names, and
the router prefers this one for :attr:`~caissa.ocr.types.RegionKind.TABLE`.

Output shape (PaddleOCR 3.x, ``PPStructureV3().predict(image)``): a list of
result objects, dict-like, with ``layout_det_res.boxes`` (``label``,
``coordinate``, ``score``), ``overall_ocr_res`` (``rec_texts``,
``rec_scores``, ``rec_polys``) and ``parsing_res_list`` (blocks with
``block_label``, ``block_content``, ``block_bbox`` in reading order).  Each
recognised line is assigned to the parsing block that contains it, and the
block's reading-order index becomes the line's ``block_index`` — so the
layout consumer can rebuild the page order without trusting the raster
engine's own text order.  A payload that has none of those keys raises
:class:`~caissa.ocr.engines.contracts.SchemaError`.

Opt-in, like the other Paddle backend, and run in an isolated worker by
default (ADR-0003: the Paddle runtime does not share a process with the
project's torch build).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

from ..types import BBox, OcrLine, OcrResult, RegionKind
from .base import EngineCapabilities, EngineLevel, OcrEngineBase, OcrError, normalise_gray
from .contracts import SchemaError, check_version
from .paddle import INSTALL_HINT_PT, LANG_MAP, _split_line

__all__ = ["LayoutBlock", "PaddleStructureConfig", "PaddleStructureEngine", "LABEL_TO_KIND"]

LABEL_TO_KIND: dict[str, RegionKind] = {
    "text": RegionKind.PARAGRAPH,
    "paragraph_title": RegionKind.HEADING,
    "doc_title": RegionKind.HEADING,
    "title": RegionKind.HEADING,
    "table": RegionKind.TABLE,
    "table_title": RegionKind.CAPTION,
    "figure_title": RegionKind.CAPTION,
    "chart_title": RegionKind.CAPTION,
    "image": RegionKind.UNKNOWN,
    "figure": RegionKind.UNKNOWN,
    "chart": RegionKind.UNKNOWN,
    "header": RegionKind.HEADER,
    "footer": RegionKind.FOOTER,
    "number": RegionKind.PAGE_NUMBER,
    "footnote": RegionKind.FOOTNOTE,
    "abstract": RegionKind.PARAGRAPH,
    "content": RegionKind.PARAGRAPH,
    "formula": RegionKind.UNKNOWN,
    "seal": RegionKind.UNKNOWN,
}


@dataclass(frozen=True, slots=True)
class LayoutBlock:
    """One region the layout model found, in reading order."""

    order: int
    label: str
    kind: RegionKind
    box: BBox
    score: float
    text: str = ""


@dataclass(slots=True)
class PaddleStructureConfig:
    use_gpu: bool = False
    #: Sub-pipelines that cost time and are not needed for text: off.
    use_doc_orientation_classify: bool = False
    use_doc_unwarping: bool = False
    use_textline_orientation: bool = False
    use_table_recognition: bool = True
    use_formula_recognition: bool = False
    use_chart_recognition: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class PaddleStructureEngine(OcrEngineBase):
    """Level 2, layout-aware: PP-StructureV3."""

    name = "paddle_structure"

    def __init__(self, config: PaddleStructureConfig | None = None) -> None:
        super().__init__()
        self.config = config or PaddleStructureConfig()
        self._pipeline: Any = None
        self._version: str | None = None
        self.last_blocks: tuple[LayoutBlock, ...] = ()

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        ok, version, reason = check_version("paddleocr", engine=self.name)
        self._version = version
        if not ok:
            return False, reason
        try:
            from paddleocr import PPStructureV3  # noqa: F401
        except ImportError:
            return False, (
                "PP-StructureV3 exige PaddleOCR 3.x.\n" + INSTALL_HINT_PT)
        except Exception as exc:  # noqa: BLE001 - a broken install must be reported, not hidden
            return False, f"PaddleOCR está instalado mas não pôde ser carregado: {exc}"
        return True, None

    def _discover_languages(self) -> set[str]:
        return set(LANG_MAP)

    @property
    def version(self) -> str | None:
        self.available()
        return self._version

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.PADDLE,
            cost_per_megapixel_s=4.0,
            supports_char_boxes=False,
            supports_confidence=True,
            handles_layout=True,
            requires_pdf_page=False,
            gpu_capable=True,
        )

    # -- pipeline ---------------------------------------------------------- #

    def _load(self, lang: str) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        from paddleocr import PPStructureV3

        cfg = self.config
        kwargs: dict[str, Any] = {
            "use_doc_orientation_classify": cfg.use_doc_orientation_classify,
            "use_doc_unwarping": cfg.use_doc_unwarping,
            "use_textline_orientation": cfg.use_textline_orientation,
            "use_table_recognition": cfg.use_table_recognition,
            "use_formula_recognition": cfg.use_formula_recognition,
            "use_chart_recognition": cfg.use_chart_recognition,
            "lang": LANG_MAP.get(lang.split("+")[0], "en"),
        }
        if cfg.use_gpu:
            kwargs["device"] = "gpu"
        kwargs.update(cfg.extra)
        try:
            self._pipeline = PPStructureV3(**kwargs)
        except TypeError:
            self._pipeline = PPStructureV3()
        return self._pipeline

    # -- recognition ------------------------------------------------------- #

    def _recognize(self, image: NDArray[np.uint8], *, lang: str,
                   psm_hint: RegionKind) -> OcrResult:
        gray = normalise_gray(image)
        rgb = np.repeat(gray[:, :, None], 3, axis=2)
        started = time.perf_counter()
        try:
            pipeline = self._load(lang)
            raw = list(pipeline.predict(rgb))
        except OcrError:
            raise
        except Exception as exc:  # noqa: BLE001 - the engine's own failure, reported explicitly
            raise OcrError(self.name, f"PP-StructureV3 falhou nesta região: {exc}",
                           detail=str(exc)) from exc
        blocks, lines = self.parse(raw, psm_hint)
        self.last_blocks = tuple(blocks)
        return OcrResult(
            engine=self.name, lang=lang, lines=tuple(lines), region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            warnings=() if lines else ("Nenhum texto reconhecido nesta região.",),
            meta={
                "version": self._version,
                "layout_blocks": [
                    {"order": b.order, "label": b.label, "kind": str(b.kind),
                     "box": [b.box.x0, b.box.y0, b.box.x1, b.box.y1], "score": round(b.score, 3)}
                    for b in blocks
                ],
                "image_shape": tuple(int(v) for v in gray.shape),
            },
        )

    # -- parsing ----------------------------------------------------------- #

    @classmethod
    def parse(cls, raw: Sequence[Any], region_kind: RegionKind
              ) -> tuple[list[LayoutBlock], list[OcrLine]]:
        """Blocks in reading order and lines assigned to them.

        Raises :class:`SchemaError` on a non-empty payload of unknown shape.
        """
        if not raw:
            return [], []
        page = raw[0]
        get = _getter(page)
        if get is None:
            raise SchemaError("paddle_structure", f"resultado do tipo {type(page).__name__}")
        parsing = get("parsing_res_list")
        layout = get("layout_det_res")
        ocr = get("overall_ocr_res")
        if parsing is None and layout is None and ocr is None:
            raise SchemaError("paddle_structure",
                              f"chaves presentes: {sorted(_keys(page))[:12]}")

        blocks: list[LayoutBlock] = []
        source = parsing if parsing is not None else []
        for order, entry in enumerate(source):
            g = _getter(entry)
            if g is None:
                continue
            label = str(g("block_label") or g("label") or "text")
            bbox = g("block_bbox") or g("bbox")
            if not bbox or len(bbox) < 4:
                continue
            box = BBox.from_edges(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            blocks.append(LayoutBlock(order=order, label=label,
                                      kind=LABEL_TO_KIND.get(label, RegionKind.UNKNOWN),
                                      box=box, score=float(g("score") or 1.0),
                                      text=str(g("block_content") or "")))
        if not blocks and layout is not None:
            lg = _getter(layout)
            boxes = (lg("boxes") if lg else None) or []
            for order, entry in enumerate(boxes):
                g = _getter(entry)
                if g is None:
                    continue
                coordinate = g("coordinate")
                if not coordinate or len(coordinate) < 4:
                    continue
                label = str(g("label") or "text")
                box = BBox.from_edges(*(float(v) for v in coordinate[:4]))
                blocks.append(LayoutBlock(order=order, label=label,
                                          kind=LABEL_TO_KIND.get(label, RegionKind.UNKNOWN),
                                          box=box, score=float(g("score") or 1.0)))
            blocks.sort(key=lambda b: (b.box.y0, b.box.x0))
            blocks = [LayoutBlock(n, b.label, b.kind, b.box, b.score, b.text)
                      for n, b in enumerate(blocks)]

        lines: list[OcrLine] = []
        og = _getter(ocr) if ocr is not None else None
        texts = (og("rec_texts") if og else None) or []
        scores = (og("rec_scores") if og else None) or []
        polys = (og("rec_polys") if og else None) or (og("dt_polys") if og else None) or []
        if ocr is not None and og is not None and texts and not polys:
            raise SchemaError("paddle_structure", "overall_ocr_res sem rec_polys/dt_polys")
        for index, (text, poly) in enumerate(zip(texts, polys, strict=False)):
            if not str(text).strip():
                continue
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            box = BBox.from_edges(min(xs), min(ys), max(xs), max(ys))
            score = float(scores[index]) if index < len(scores) else 0.5
            owner = _owner(box, blocks)
            kind = owner.kind if owner is not None and owner.kind is not RegionKind.UNKNOWN \
                else region_kind
            lines.append(OcrLine(
                words=_split_line(str(text), box, score, index), box=box, baseline=None,
                block_index=owner.order if owner is not None else len(blocks),
                paragraph_index=0, line_index=index, kind=kind, font_size=box.h))
        lines.sort(key=lambda ln: (ln.block_index, ln.box.y0, ln.box.x0))
        return blocks, lines


def _getter(obj: Any) -> Any:
    """A uniform ``get(key)`` over dicts, dict-like results and attribute objects."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get
    if hasattr(obj, "get") and callable(obj.get):
        return obj.get
    if hasattr(obj, "__getitem__") and hasattr(obj, "keys"):
        return lambda key: obj[key] if key in obj.keys() else None
    if hasattr(obj, "__dict__") or hasattr(obj, "__slots__"):
        return lambda key: getattr(obj, key, None)
    return None


def _keys(obj: Any) -> list[str]:
    if isinstance(obj, dict) or hasattr(obj, "keys"):
        return [str(k) for k in obj.keys()]
    return [k for k in dir(obj) if not k.startswith("_")]


def _owner(box: BBox, blocks: Sequence[LayoutBlock]) -> LayoutBlock | None:
    best, best_cover = None, 0.0
    for block in blocks:
        cover = box.coverage_by(block.box)
        if cover > best_cover:
            best, best_cover = block, cover
    return best if best_cover >= 0.5 else None
