"""Diagram finders the importer can be handed: the raster route (F3 vias B/C + F4).

The importer's default finder is the vector detector (F3-A), which costs two
milliseconds a page and reads exactly -- but only on vector PDFs set with a
chess font or drawn as paths.  Thirty-two of the forty-six books in the
reference collection are scans or carry raster diagrams, and for those the
trunk's detector (``chess_diagram_ocr.detection``, field recall 0,9913 with
the F3 recall pack) and the F4 batched classifier (0,0903 s per diagram on the
GPU) are the route.  This module wraps them in the importer's
:data:`~caissa.ingest.pdf.importer.DiagramFinder` shape.

Kept out of ``importer.py`` on purpose: it imports the trunk, ``torch`` and
``cv2``, none of which the text path needs, and a text-only import of a
500-page book must not pay eight seconds of model import to not use a model.

Coordinate spaces: the trunk's ``DiagramCandidate.bbox_pdf`` is in
``page.rect`` space (its S-129 rotates the boxes for rotated pages), which is
the space the importer works in, so it passes through unchanged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any, Final

import numpy as np

from caissa.core.model import RecognitionPath
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.importer import DiagramFinder, DiagramHit, vector_diagram_finder
from caissa.ingest.pdf.textlayer import PageText

__all__ = ["combined_finder", "raster_diagram_finder"]

LOGGER = logging.getLogger("caissa.ingest.pdf.finders")

#: The trunk's own default; the F3 field numbers were measured at it.
DEFAULT_DPI: Final = 220
DEFAULT_MAX_BOARDS: Final = 12
_RGBA: Final = 4
#: A raster hit covering this share of a vector hit is the same board twice.
_SAME_BOARD_OVERLAP: Final = 0.5


def _render_rgb(page: Any, dpi: int) -> np.ndarray:
    """The trunk's ``render_pdf_page`` for an already-open page."""
    import pymupdf

    matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    buffer = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return buffer[:, :, :3].copy() if pix.n == _RGBA else buffer.copy()


def raster_diagram_finder(
    *,
    classify: bool = True,
    dpi: int = DEFAULT_DPI,
    max_boards: int = DEFAULT_MAX_BOARDS,
    classifier: Any = None,
) -> DiagramFinder:
    """A finder that detects diagrams in the rendered page and, optionally, reads them.

    Args:
        classify: Run the F4 classifier on each board.  Off, the diagrams are
            located and left unread (``fen=None``), which is what a machine
            without the model weights can still do.
        dpi: Render resolution handed to the detector.
        max_boards: Cap per page, as the trunk defines it.
        classifier: A loaded :class:`~caissa.vision.classify.BatchedClassifier`
            to reuse across books; loaded on first use when ``None``.

    The model is loaded lazily on the first page that has a candidate, so a
    book with no diagrams never pays for it.
    """
    state: dict[str, Any] = {"classifier": classifier, "tried": False}

    def _classifier() -> Any:
        if state["classifier"] is None and classify and not state["tried"]:
            state["tried"] = True
            try:
                from caissa.vision.classify.batched import load_classifier

                state["classifier"] = load_classifier()
            except Exception as exc:  # noqa: BLE001 - no weights, no GPU: locate only, say so
                LOGGER.warning(
                    "Classificador indisponível; diagramas serão localizados sem leitura: %s", exc
                )
        return state["classifier"]

    def finder(page: Any, frame: PageFrame, _text: PageText) -> list[DiagramHit]:
        from caissa.vision.classify.cvoff import ensure_cvoff_on_path
        from caissa.vision.detect.recall import recall_pack

        ensure_cvoff_on_path()
        from chess_diagram_ocr.detection import detect_diagrams  # type: ignore[import-not-found]

        started = time.perf_counter()
        rgb = _render_rgb(page, dpi)
        try:
            with recall_pack():
                candidates = detect_diagrams(page, rgb, max_boards=max_boards)
        except Exception as exc:  # noqa: BLE001 - a detector crash is a note, not a lost page
            LOGGER.warning("Detector raster falhou na página %d: %s", frame.index, exc)
            return []
        if not candidates:
            return []

        oriented: Sequence[Any] = ()
        model = _classifier()
        if model is not None:
            from caissa.vision.classify.page import predict_boards_batched

            try:
                oriented = predict_boards_batched([c.board_rgb for c in candidates], model)
            except Exception as exc:  # noqa: BLE001 - keep the boxes even if the read failed
                LOGGER.warning("Classificação falhou na página %d: %s", frame.index, exc)
                oriented = ()

        hits: list[DiagramHit] = []
        for index, candidate in enumerate(candidates):
            x0, y0, x1, y1 = candidate.bbox_pdf
            fen: str | None = None
            confidence = float(getattr(candidate, "detector_score", 0.0) or 0.0)
            path = RecognitionPath.GEOMETRIC
            white_bottom = True
            if index < len(oriented):
                prediction = oriented[index].prediction
                fen = f"{prediction.fen_board} w - - 0 1"
                confidence = float(prediction.min_confidence)
                path = RecognitionPath.NEURAL
                white_bottom = int(getattr(oriented[index], "rotation", 0)) == 0
            hits.append(
                DiagramHit(
                    box=(float(x0), float(y0), float(x1), float(y1)),
                    fen=fen,
                    confidence=confidence,
                    path=path,
                    method=str(getattr(candidate, "source", "raster")),
                    orientation_white=white_bottom,
                )
            )
        LOGGER.debug(
            "Página %d: %d diagrama(s) raster em %.0f ms",
            frame.index,
            len(hits),
            (time.perf_counter() - started) * 1000.0,
        )
        return hits

    return finder


def combined_finder(raster: DiagramFinder | None = None) -> DiagramFinder:
    """Vector first (exact), raster for what the vector route did not claim.

    A board read from a chess font is never re-detected from pixels; a raster
    hit overlapping a vector one by more than half is the same board seen
    twice and is dropped.
    """
    raster = raster or raster_diagram_finder()

    def finder(page: Any, frame: PageFrame, text: PageText) -> list[DiagramHit]:
        hits = list(vector_diagram_finder(page, frame, text))
        for hit in raster(page, frame, text):
            if any(_overlap(hit.box, other.box) > _SAME_BOARD_OVERLAP for other in hits):
                continue
            hits.append(hit)
        hits.sort(key=lambda h: (h.box[1], h.box[0]))
        return hits

    return finder


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection over the smaller box."""
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = width * height
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / smaller if smaller > 0 else 0.0
