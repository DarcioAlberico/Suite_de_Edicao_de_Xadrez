"""Diagram finders the importer can be handed: the raster route (F3 vias B/C + F4).

The importer's default finder was the vector detector (F3-A), which costs two
milliseconds a page and reads exactly -- but only on vector PDFs set with a
chess font or drawn as paths.  Thirty-two of the forty-six books in the
reference collection are scans or carry raster diagrams (the Aagaard came out
of the product's import with 0 diagrams -- ``OCR_UI_ANALISE_C2.md`` §3.2), so
since OCR_UI ciclo 2 passo A2 the importer's default is :func:`combined_finder`
(``PdfImportOptions.detect_raster_diagrams``), and for the raster books the
trunk's detector (``chess_diagram_ocr.detection``, field recall 0,9913 with
the F3 recall pack -- the trunk's own default since OCR_UI cycle 2 step A1)
and the F4 batched classifier (0,0903 s per diagram on the GPU) are the
route.  This module wraps them in the importer's
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

from caissa.core.model import FenCandidate, RecognitionPath, SquareRepair
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.importer import (
    DiagramFinder,
    DiagramHit,
    square_confidences_from_holes,
    vector_diagram_finder,
)
from caissa.ingest.pdf.textlayer import PageText

__all__ = [
    "combined_finder",
    "fill_holes",
    "inferred_font_finder",
    "raster_diagram_finder",
    "shared_classifier",
    "signal_from_prediction",
]

LOGGER = logging.getLogger("caissa.ingest.pdf.finders")

#: The trunk's own default; the F3 field numbers were measured at it.
DEFAULT_DPI: Final = 220
DEFAULT_MAX_BOARDS: Final = 12
_RGBA: Final = 4
#: A raster hit covering this share of a vector hit is the same board twice.
_SAME_BOARD_OVERLAP: Final = 0.5
#: OCR_UI_ROADMAP passo 10: a board in a chess font outside the catalog is
#: read from its rendered cells, and the read can never claim more than
#: this — the font was not decoded, the pixels were classified.
INFERRED_CONFIDENCE_CAP: Final = 0.85
#: Render resolution of the board crop handed to the classifier (the
#: trunk's field numbers are at 220 dpi for whole pages; a lone board can
#: afford more, and the classifier warps it to its own size anyway).
INFERRED_DPI: Final = 300


def _render_rgb(page: Any, dpi: int) -> np.ndarray:
    """The trunk's ``render_pdf_page`` for an already-open page."""
    import pymupdf

    matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    buffer = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return buffer[:, :, :3].copy() if pix.n == _RGBA else buffer.copy()


def shared_classifier() -> Any:
    """The process's one square classifier, or ``None`` with the reason logged.

    OCR_UI ciclo 2, passo A2: the finders borrowed a fresh ``load_classifier()``
    each -- three loads for one ``combined_finder`` -- while
    :func:`caissa.vision.classify.residency.acquire_square_classifier`, the
    ADR-0004 way of sharing the VRAM budget with the window's own reads, had
    no caller.  Now every finder that needs the model asks here: the residency
    manager loads it once per process and keeps it (pinned); when the manager
    cannot (no registration, a budget rule), the plain loader is the fallback;
    when nothing can load it (no weights, no torch) the finder locates the
    boards and leaves them unread, and the warning says why.
    """
    try:
        from caissa.vision.classify.residency import shared_square_classifier

        return shared_square_classifier()
    except Exception as first:  # noqa: BLE001 - the plain loader is the second chance
        try:
            from caissa.vision.classify.batched import load_classifier

            return load_classifier()
        except Exception as second:  # noqa: BLE001 - no weights, no GPU: locate only, say so
            LOGGER.warning(
                "Classificador indisponível; diagramas serão localizados sem leitura "
                "(residência: %s; carga direta: %s)", first, second,
            )
            return None


def _model_hash(classifier: Any) -> str:
    """Fingerprint of the weights behind ``classifier`` (passo C1).

    A classifier borrowed through
    :func:`~caissa.vision.classify.residency.acquire_square_classifier` carries
    it as ``model_hash``; one from ``load_classifier()`` does not, and then the
    production checkpoint's fingerprint is the honest answer, because that is
    the only file ``load_classifier()`` loads.  ``""`` when nothing can be
    read -- a report must not die for failing to identify itself.
    """
    known = getattr(classifier, "model_hash", "")
    if known:
        return str(known)
    try:
        from chess_diagram_ocr.checkpoint import (
            checkpoint_fingerprint,  # type: ignore[import-not-found]
        )
        from chess_diagram_ocr.config import DEFAULT_MODEL_PATH  # type: ignore[import-not-found]

        from caissa.vision.classify.cvoff import trunk_model_path

        path = DEFAULT_MODEL_PATH if DEFAULT_MODEL_PATH.exists() else trunk_model_path()
        return checkpoint_fingerprint(path)
    except Exception:  # noqa: BLE001 - identity is a courtesy, never a failure
        return ""


#: Runner-up alternatives are offered for at most this many uncertain squares.
_MAX_RUNNER_UPS: Final = 3
_SQUARES: Final = 64
_FILES: Final = 8
#: The trunk's ``config.PIECE_CLASSES``, in the order the classifier's
#: probabilities use.  Copied so the signal can be unpacked without importing
#: the trunk; ``tests/unit/ingest/test_diagram_signal.py`` pins it equal.
PIECE_CLASSES: Final = ("empty", "P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k")


def a1_index_from_reading_index(index: int) -> int:
    """``fen_utils.square_from_reading_index`` without the trunk: 0 = ``a8`` -> 56."""
    if not 0 <= index < _SQUARES:
        raise ValueError(f"índice de casa fora de 0..63: {index}")
    return (_FILES - 1 - index // _FILES) * _FILES + index % _FILES


def square_name_from_reading_index(index: int) -> str:
    """``fen_utils.square_name`` without the trunk: 0 = ``a8``, 63 = ``h1``."""
    if not 0 <= index < _SQUARES:
        raise ValueError(f"índice de casa fora de 0..63: {index}")
    return f"{'abcdefgh'[index % _FILES]}{_FILES - index // _FILES}"


def signal_from_prediction(oriented: Any, *, model_hash: str = "") -> dict[str, Any]:
    """The contract §1.2 fields of a :class:`DiagramHit` from one ``OrientedPrediction``.

    The trunk's ``BoardPrediction`` numbers squares in **reading order** (0 =
    ``a8``); the IR numbers them from ``a1``
    (``RecognitionResult.per_square_confidence``), so every index goes through
    ``fen_utils.square_from_reading_index``.  What is carried:

    * ``square_confidences`` -- the probability of the chosen class per square;
    * ``repairs`` -- ``decode.changed_squares`` as :class:`SquareRepair`, with
      the classifier's confidence in what it had read;
    * ``alternatives`` -- the discarded orientation when the policy called the
      choice ambiguous (so the reader can *compare the two*), then the
      runner-up piece on the least certain squares, one candidate each;
    * ``orientation_ambiguous`` / ``orientation_reason`` -- the policy's verdict.

    A prediction without the per-square distribution (a stub, an older trunk)
    yields the orientation fields only and empty tuples for the rest.
    """
    prediction = oriented.prediction
    orientation = {
        "model_hash": model_hash,
        "orientation_ambiguous": bool(getattr(oriented, "ambiguous", False)),
        "orientation_reason": str(getattr(oriented, "reason", "") or ""),
    }
    raw = getattr(prediction, "square_confidences", None)
    if raw is None:
        return orientation
    reading = [float(v) for v in raw]
    if len(reading) != _SQUARES:
        return orientation
    by_a1 = [0.0] * _SQUARES
    for index, value in enumerate(reading):
        by_a1[a1_index_from_reading_index(index)] = value

    def _letter(class_index: int) -> str:
        name = PIECE_CLASSES[int(class_index)] if 0 <= int(class_index) < len(PIECE_CLASSES) else ""
        return "" if name == "empty" else name

    repairs: list[SquareRepair] = []
    decode = getattr(prediction, "decode", None)
    if decode is not None:
        for square, before, after in getattr(decode, "changed_squares", ()):
            repairs.append(
                SquareRepair(
                    square=square_name_from_reading_index(int(square)),
                    recognised=_letter(before),
                    repaired=_letter(after),
                    reason="decodificação com restrições de legalidade",
                    confidence_before=float(prediction.probs[int(square), int(before)]),
                )
            )

    alternatives: list[FenCandidate] = []
    other = getattr(oriented, "alternative", None)
    if other is not None and bool(getattr(oriented, "ambiguous", False)):
        alternatives.append(
            FenCandidate(
                fen=f"{other.fen_board} w - - 0 1",
                score=float(other.min_confidence),
                legal=not bool(getattr(getattr(other, "position", None), "is_fatal", False)),
            )
        )
    rows = [list(_expand(row)) for row in prediction.fen_board.split("/")]
    if len(rows) == _FILES and all(len(row) == _FILES for row in rows):
        for square in list(getattr(prediction, "uncertain_squares", ()))[:_MAX_RUNNER_UPS]:
            second, probability = prediction.runner_up(int(square))
            board = [row[:] for row in rows]
            board[int(square) // _FILES][int(square) % _FILES] = _letter(second) or "."
            alternatives.append(
                FenCandidate(fen=f"{_placement(board)} w - - 0 1", score=float(probability))
            )

    return {
        **orientation,
        "square_confidences": tuple(by_a1),
        "repairs": tuple(repairs),
        "alternatives": tuple(alternatives),
    }


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
            state["classifier"] = shared_classifier()
        return state["classifier"]

    def finder(page: Any, frame: PageFrame, _text: PageText) -> list[DiagramHit]:
        from caissa.vision.classify.cvoff import ensure_cvoff_on_path

        ensure_cvoff_on_path()
        from chess_diagram_ocr.detection import detect_diagrams  # type: ignore[import-not-found]

        started = time.perf_counter()
        rgb = _render_rgb(page, dpi)
        try:
            # The F3 recall pack (multi-scale, square rescue, embedded floor) is the
            # trunk's own default since OCR_UI cycle 2 step A1 (`config.DEFAULT_RECALL`):
            # the window and this finder now run the same function with the same options,
            # and nothing is monkeypatched around the call any more.
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
        model_hash = _model_hash(model) if oriented else ""
        for index, candidate in enumerate(candidates):
            x0, y0, x1, y1 = candidate.bbox_pdf
            fen: str | None = None
            confidence = float(getattr(candidate, "detector_score", 0.0) or 0.0)
            path = RecognitionPath.GEOMETRIC
            white_bottom = True
            signal: dict[str, Any] = {}
            if index < len(oriented):
                prediction = oriented[index].prediction
                fen = f"{prediction.fen_board} w - - 0 1"
                confidence = float(prediction.min_confidence)
                path = RecognitionPath.NEURAL
                white_bottom = int(getattr(oriented[index], "rotation", 0)) == 0
                signal = signal_from_prediction(oriented[index], model_hash=model_hash)
            hits.append(
                DiagramHit(
                    box=(float(x0), float(y0), float(x1), float(y1)),
                    fen=fen,
                    confidence=confidence,
                    path=path,
                    method=str(getattr(candidate, "source", "raster")),
                    orientation_white=white_bottom,
                    **signal,
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


def _render_clip_rgb(page: Any, box: tuple[float, float, float, float], dpi: int) -> np.ndarray:
    """One rectangle of the page (``page.rect`` space), RGB, at ``dpi``."""
    import pymupdf

    matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, clip=pymupdf.Rect(*box), alpha=False)
    buffer = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return buffer[:, :, :3].copy() if pix.n == _RGBA else buffer.copy()


def inferred_font_finder(
    *,
    classifier: Any = None,
    dpi: int = INFERRED_DPI,
    lookup: Any = None,
    confidence_cap: float = INFERRED_CONFIDENCE_CAP,
) -> DiagramFinder:
    """OCR_UI_ROADMAP passo 10: boards set in a chess font the catalog does not know.

    The lattice (:func:`caissa.vision.detect.detect_unknown_font_lattices`)
    gives the rectangle exactly; the position comes from rendering that
    rectangle and classifying its 64 cells with the F4 classifier.  The hit
    carries :attr:`RecognitionPath.VECTOR_INFERRED`, a confidence of at most
    ``confidence_cap`` and the font's name in ``method``, so the report says
    what happened.  Without the classifier (no weights, no torch) the board is
    located and left unread, ``fen=None``.

    ``lookup`` replaces the catalog lookup — the sabotage of the roadmap hides
    a catalogued family to make an exact book fall through this path.
    """
    state: dict[str, Any] = {"classifier": classifier, "tried": False}

    def _classifier() -> Any:
        if state["classifier"] is None and not state["tried"]:
            state["tried"] = True
            state["classifier"] = shared_classifier()
        return state["classifier"]

    def finder(page: Any, frame: PageFrame, _text: PageText) -> list[DiagramHit]:
        from caissa.vision.detect.vector_detect import detect_unknown_font_lattices

        kwargs = {"lookup": lookup} if lookup is not None else {}
        try:
            lattices = detect_unknown_font_lattices(page, **kwargs)
        except Exception as exc:  # noqa: BLE001 - a detector crash is a note, not a lost page
            LOGGER.warning("Reticulado de fonte desconhecida falhou na página %d: %s",
                           frame.index, exc)
            return []
        if not lattices:
            return []
        oriented: Sequence[Any] = ()
        model = _classifier()
        if model is not None:
            from caissa.vision.classify.page import predict_boards_batched

            try:
                crops = [_render_clip_rgb(page, lattice.rect_pdf, dpi) for lattice in lattices]
                oriented = predict_boards_batched(crops, model)
            except Exception as exc:  # noqa: BLE001 - keep the boxes even if the read failed
                LOGGER.warning("Classificação da fonte desconhecida falhou na página %d: %s",
                               frame.index, exc)
                oriented = ()
        hits: list[DiagramHit] = []
        model_hash = _model_hash(model) if oriented else ""
        for index, lattice in enumerate(lattices):
            x0, y0, x1, y1 = lattice.rect_pdf
            fen: str | None = None
            confidence = 0.0
            white_bottom = True
            signal: dict[str, Any] = {}
            if index < len(oriented):
                prediction = oriented[index].prediction
                fen = f"{prediction.fen_board} w - - 0 1"
                confidence = min(confidence_cap, float(prediction.min_confidence))
                white_bottom = int(getattr(oriented[index], "rotation", 0)) == 0
                signal = signal_from_prediction(oriented[index], model_hash=model_hash)
                # The cap applies per square too: no cell of an inferred read
                # may claim more than the route can (passo 10).
                signal["square_confidences"] = tuple(
                    min(confidence_cap, value) for value in signal.get("square_confidences", ())
                )
            hits.append(DiagramHit(
                box=(float(x0), float(y0), float(x1), float(y1)),
                fen=fen,
                confidence=confidence,
                path=RecognitionPath.VECTOR_INFERRED,
                method=f"fonte fora do catálogo {lattice.font_name} ({lattice.font_size:.1f} pt): "
                       f"reticulado 8x8 renderizado e classificado",
                orientation_white=white_bottom,
                **signal,
            ))
        return hits

    return finder


def _expand(row: str) -> str:
    return "".join("." * int(ch) if ch.isdigit() else ch for ch in row)


def _matrix(placement: str) -> list[list[str]]:
    return [list(_expand(row)) for row in placement.split("/")]


def _placement(matrix: list[list[str]]) -> str:
    rows = []
    for row in matrix:
        out, run = "", 0
        for ch in row:
            if ch == ".":
                run += 1
            else:
                out += (str(run) if run else "") + ch
                run = 0
        rows.append(out + (str(run) if run else ""))
    return "/".join(rows)


def fill_holes(hit: DiagramHit, classified_placement: str) -> DiagramHit | None:
    """An exact vector read with missing cells, completed by the classifier.

    ``classified_placement`` is the classifier's read of the same board, in
    FEN order (rank 8 first, white at the bottom).  The classifier is
    trusted only where the text layer was silent: every cell the font *did*
    give must agree, or the read is left as it was (``None``).  The result
    carries :attr:`RecognitionPath.VECTOR_INFERRED`, a confidence capped at
    :data:`INFERRED_CONFIDENCE_CAP`, and no holes.
    """
    if not hit.holes or not hit.fen:
        return None
    exact = _matrix(hit.fen.split()[0])
    read = _matrix(classified_placement)
    if len(exact) != 8 or len(read) != 8 or any(len(r) != 8 for r in exact + read):
        return None
    # Lattice order is the printed order; the placement is in FEN order, so a
    # board printed with Black at the bottom is the lattice turned around.
    def to_fen(r: int, c: int) -> tuple[int, int]:
        return (r, c) if hit.orientation_white else (7 - r, 7 - c)

    holes = {to_fen(r, c) for r, c in hit.holes}
    for r in range(8):
        for c in range(8):
            if (r, c) not in holes and exact[r][c] != read[r][c]:
                return None
    filled = 0
    for r, c in holes:
        if exact[r][c] != read[r][c]:
            exact[r][c] = read[r][c]
            filled += 1
    from dataclasses import replace

    confidence = min(INFERRED_CONFIDENCE_CAP, hit.confidence)
    return replace(
        hit,
        fen=f"{_placement(exact)} {' '.join(hit.fen.split()[1:])}".strip(),
        confidence=confidence,
        path=RecognitionPath.VECTOR_INFERRED,
        method=f"{hit.method}; {len(holes)} casa(s) ausentes na camada de texto lidas pelo "
               f"classificador ({filled} com peça)",
        holes=(),
        # Passo C1: the filled cells were classified, not decoded -- they keep
        # the capped confidence (below the 0,9 doubt line); the rest stays exact.
        square_confidences=square_confidences_from_holes(
            hit.holes, hit.orientation_white, hole_value=confidence
        ),
    )


def combined_finder(
    raster: DiagramFinder | None = None, *, inferred: DiagramFinder | None = None,
    classifier: Any = None, dpi: int = INFERRED_DPI,
) -> DiagramFinder:
    """Vector first (exact), then unknown-font lattices (inferred), raster for the rest.

    An exact read whose text layer lacked cells (``DiagramHit.holes``) is
    completed by the classifier (:func:`fill_holes`).  A board read from a
    chess font is never re-detected from pixels; a raster hit overlapping a
    vector one by more than half is the same board seen twice and is dropped.
    """
    raster = raster or raster_diagram_finder(classifier=classifier)
    inferred = inferred or inferred_font_finder(classifier=classifier)
    state: dict[str, Any] = {"classifier": classifier, "tried": False}

    def _classifier() -> Any:
        if state["classifier"] is None and not state["tried"]:
            state["tried"] = True
            state["classifier"] = shared_classifier()
        return state["classifier"]

    def refine(page: Any, frame: PageFrame, hits: list[DiagramHit]) -> list[DiagramHit]:
        holed = [h for h in hits if h.holes and h.fen and h.cells_box]
        if not holed:
            return hits
        model = _classifier()
        if model is None:
            return hits
        from caissa.vision.classify.page import predict_boards_batched

        try:
            crops = [_render_clip_rgb(page, h.cells_box, dpi) for h in holed]  # type: ignore[arg-type]
            oriented = predict_boards_batched(crops, model, mode="0")
        except Exception as exc:  # noqa: BLE001 - keep the exact read, holes empty
            LOGGER.warning("Classificação das casas ausentes falhou na página %d: %s",
                           frame.index, exc)
            return hits
        replaced = {}
        for hit, result in zip(holed, oriented, strict=False):
            board = result.prediction.fen_board
            if not hit.orientation_white:
                board = "/".join(row[::-1] for row in reversed(board.split("/")))
            fixed = fill_holes(hit, board)
            if fixed is not None:
                replaced[id(hit)] = fixed
        return [replaced.get(id(h), h) for h in hits]

    def finder(page: Any, frame: PageFrame, text: PageText) -> list[DiagramHit]:
        hits = refine(page, frame, list(vector_diagram_finder(page, frame, text)))
        for later in (inferred, raster):
            for hit in later(page, frame, text):
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
