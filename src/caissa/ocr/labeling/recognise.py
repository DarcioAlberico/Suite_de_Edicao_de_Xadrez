"""From a PDF page to a :class:`PageLabels` — rendering and recognition.

The engine runs through the production service (:class:`OcrService`), so
the reviewer corrects exactly what the importer would have emitted:
same layout, same candidates, same fusion, same doubts.  A line's
alternatives are the other candidates' readings of the same strip, matched
by overlap; they are shown, never applied.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from caissa.ocr.types import BBox, OcrLine, RegionKind

from .model import LineLabel, PageLabels, RectT, RegionLabel, WordHint

__all__ = [
    "close_documents",
    "label_page",
    "page_count",
    "page_size",
    "recognise_rect",
    "render_gray",
    "render_rgb",
]

_DOCS: dict[str, Any] = {}
#: Overlap below which another candidate's line is not the same strip.
MIN_LINE_IOU = 0.3


def _open(pdf_path: Path | str) -> Any:
    import pymupdf

    key = str(Path(pdf_path).resolve())
    doc = _DOCS.get(key)
    if doc is None or getattr(doc, "is_closed", False):
        doc = pymupdf.open(key)
        _DOCS[key] = doc
    return doc


def close_documents() -> None:
    for doc in _DOCS.values():
        with contextlib.suppress(Exception):  # closing is best effort
            doc.close()
    _DOCS.clear()


def page_count(pdf_path: Path | str) -> int:
    return int(_open(pdf_path).page_count)


def page_size(pdf_path: Path | str, page_index: int) -> tuple[float, float]:
    page = _open(pdf_path)[page_index]
    rect = page.rect
    return float(rect.width), float(rect.height)


def _pixmap(
    pdf_path: Path | str, page_index: int, dpi: float, clip: RectT | None, gray: bool
) -> Any:
    import pymupdf

    page = _open(pdf_path)[page_index]
    kwargs: dict[str, Any] = {
        "dpi": round(dpi),
        "alpha": False,
        "colorspace": pymupdf.csGRAY if gray else pymupdf.csRGB,
    }
    if clip is not None:
        x0, y0, x1, y1 = clip
        bounds = page.rect
        clipped = pymupdf.Rect(
            max(bounds.x0, x0), max(bounds.y0, y0), min(bounds.x1, x1), min(bounds.y1, y1)
        )
        if clipped.is_empty:
            clipped = pymupdf.Rect(bounds.x0, bounds.y0, bounds.x0 + 1, bounds.y0 + 1)
        kwargs["clip"] = clipped
    return page.get_pixmap(**kwargs)


def render_gray(
    pdf_path: Path | str, page_index: int, dpi: float = 300.0, clip: RectT | None = None
) -> np.ndarray:
    """A grayscale raster of the page (or of ``clip``, in points) at ``dpi``."""
    pix = _pixmap(pdf_path, page_index, dpi, clip, gray=True)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def render_rgb(
    pdf_path: Path | str, page_index: int, dpi: float = 300.0, clip: RectT | None = None
) -> np.ndarray:
    pix = _pixmap(pdf_path, page_index, dpi, clip, gray=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()


# --------------------------------------------------------------------------- #
# Recognition → labels
# --------------------------------------------------------------------------- #


def _pt(box: BBox, scale: float, dx: float = 0.0, dy: float = 0.0) -> RectT:
    return (
        round(box.x0 * scale + dx, 2),
        round(box.y0 * scale + dy, 2),
        round(box.x1 * scale + dx, 2),
        round(box.y1 * scale + dy, 2),
    )


def _alternatives_for(
    line: OcrLine, candidates: Sequence[Any], chosen: tuple[str, str]
) -> tuple[tuple[str, str], ...]:
    """Other candidates' readings of the strip ``line`` covers, when they differ."""
    out: list[tuple[str, str]] = []
    seen = {line.text.strip()}
    for candidate in candidates:
        source = f"{candidate.variant}/{candidate.engine}"
        if (candidate.variant, candidate.engine) == chosen:
            continue
        best, best_iou = None, 0.0
        for other in candidate.result.lines:
            iou = line.box.iou(other.box)
            if iou > best_iou:
                best, best_iou = other, iou
        if best is None or best_iou < MIN_LINE_IOU:
            continue
        text = best.text.strip()
        if text and text not in seen:
            seen.add(text)
            out.append((source, text))
    return tuple(out)


def _lines_from(
    result_lines: Sequence[OcrLine],
    scale: float,
    candidates: Sequence[Any],
    chosen: tuple[str, str],
    *,
    dx: float = 0.0,
    dy: float = 0.0,
) -> list[LineLabel]:
    lines: list[LineLabel] = []
    for n, line in enumerate(result_lines):
        if not line.words:
            continue
        words = tuple(
            WordHint(text=w.text, confidence=float(w.confidence), box=_pt(w.box, scale, dx, dy))
            for w in line.words
        )
        lines.append(
            LineLabel(
                index=n,
                box=_pt(line.box, scale, dx, dy),
                hypothesis=line.text,
                confidence=float(line.confidence),
                words=words,
                alternatives=_alternatives_for(line, candidates, chosen),
            )
        )
    return lines


def label_page(
    service: Any,
    pdf_path: Path | str,
    document: str,
    page_index: int,
    *,
    dpi: float = 300.0,
    lang: str = "",
) -> PageLabels:
    """Run the service on one page and lay its regions and lines out for review."""
    gray = render_gray(pdf_path, page_index, dpi)
    width_pt, height_pt = page_size(pdf_path, page_index)
    recognition = service.recognize_image(gray, dpi=float(dpi), lang=lang, page_index=page_index)
    scale = 72.0 / float(recognition.dpi or dpi)
    regions: list[RegionLabel] = []
    iso = _first_lang(lang or getattr(service, "lang", ""))
    for region in sorted(recognition.regions, key=lambda r: r.reading_order):
        chosen = (region.variant, region.engine)
        common: dict[str, Any] = {
            "engine": region.engine,
            "score": float(region.score),
            "decision": str(region.decision.decision),
            "reasons": tuple(str(r) for r in getattr(region.decision, "reasons_pt", ())),
            "prose_lang": iso,
            "notation_lang": iso,
        }
        if str(region.kind) in _SPLIT_KINDS:
            # The layout gave the engine the whole page (or a column): its own
            # paragraph segmentation is the block structure the reviewer wants.
            for para_lines in _paragraphs(region.result.lines):
                lines = _lines_from(para_lines, scale, region.candidates, chosen)
                if not lines:
                    continue
                rect = _union(line.box for line in lines)
                regions.append(
                    RegionLabel(
                        index=len(regions),
                        rect=rect,
                        kind="paragraph",
                        reading_order=len(regions),
                        lines=lines,
                        **common,
                    )
                )
            continue
        lines = _lines_from(region.result.lines, scale, region.candidates, chosen)
        regions.append(
            RegionLabel(
                index=len(regions),
                rect=_pt(region.box_px, scale),
                kind=str(region.kind),
                reading_order=len(regions),
                lines=lines,
                **common,
            )
        )
    return PageLabels(
        document=document,
        pdf_path=str(pdf_path),
        page_index=page_index,
        width_pt=width_pt,
        height_pt=height_pt,
        dpi=float(dpi),
        lang=lang or str(getattr(service, "lang", "")),
        regions=regions,
        engines=dict(recognition.engines),
        recognised_at=datetime.now(UTC).isoformat(timespec="seconds"),
        notes=list(recognition.notes),
    )


def recognise_rect(
    service: Any, page: PageLabels, rect: RectT, *, kind: str = "paragraph", lang: str = ""
) -> RegionLabel:
    """OCR a rectangle the reviewer drew and return it as a new region."""
    x0, y0, x1, y1 = rect
    rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    gray = render_gray(page.pdf_path, page.page_index, page.dpi, clip=rect)
    recognition = service.recognize_image(
        gray, dpi=float(page.dpi), lang=lang or page.lang, page_index=page.page_index
    )
    scale = 72.0 / float(recognition.dpi or page.dpi)
    lines: list[LineLabel] = []
    engine, score, decision = "", 0.0, ""
    for region in sorted(recognition.regions, key=lambda r: r.reading_order):
        chosen = (region.variant, region.engine)
        lines.extend(
            _lines_from(
                region.result.lines, scale, region.candidates, chosen, dx=rect[0], dy=rect[1]
            )
        )
        if region.score >= score:
            engine, score, decision = (
                region.engine,
                float(region.score),
                str(region.decision.decision),
            )
    for n, line in enumerate(lines):
        line.index = n
    order = max((r.reading_order for r in page.regions), default=-1) + 1
    return RegionLabel(
        index=page.next_region_index(),
        rect=rect,
        kind=kind,
        reading_order=order,
        lines=lines,
        engine=engine,
        score=score,
        decision=decision,
        drawn=True,
        prose_lang=_first_lang(lang or page.lang),
        notation_lang=_first_lang(lang or page.lang),
    )


_SPLIT_KINDS = {str(RegionKind.PAGE), str(RegionKind.COLUMN), str(RegionKind.UNKNOWN)}


def _paragraphs(lines: Sequence[OcrLine]) -> list[list[OcrLine]]:
    """Group the engine's lines by its own block and paragraph indices.

    The order is the one the engine emitted them in.
    """
    groups: dict[tuple[int, int], list[OcrLine]] = {}
    for line in lines:
        groups.setdefault((line.block_index, line.paragraph_index), []).append(line)
    return list(groups.values())


def _union(boxes: Any) -> RectT:
    boxes = list(boxes)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _first_lang(lang: str) -> str:
    """``por+eng`` → ``pt``: the manifest's two-letter facet from Tesseract's code."""
    code = (lang or "").split("+")[0].strip()
    return _TESS_TO_ISO.get(code, code[:2] if code else "")


_TESS_TO_ISO = {
    "eng": "en",
    "por": "pt",
    "deu": "de",
    "spa": "es",
    "rus": "ru",
    "fra": "fr",
    "ita": "it",
    "nld": "nl",
    "ron": "ro",
}


def kinds_for_menu() -> list[str]:
    """Region kinds a reviewer can assign, prose first."""
    return [
        str(k)
        for k in (
            RegionKind.PARAGRAPH,
            RegionKind.MOVETEXT,
            RegionKind.HEADING,
            RegionKind.CAPTION,
            RegionKind.FOOTNOTE,
            RegionKind.TABLE,
            RegionKind.HEADER,
            RegionKind.FOOTER,
            RegionKind.PAGE_NUMBER,
            RegionKind.DIAGRAM_LABEL,
        )
    ]
