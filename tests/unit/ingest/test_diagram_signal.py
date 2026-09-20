"""OCR_UI ciclo 2, passo C1: the per-square signal crosses the boundary intact.

The trunk's ``BoardPrediction`` says *where* it is unsure (``uncertain_squares``,
reading order, ``a8`` first), *what* the legality decoder changed
(``decode.changed_squares``) and *how* the orientation was chosen
(``OrientedPrediction.ambiguous/reason``).  Before this step ``DiagramHit``
carried one number and the IR's ``RecognitionResult.per_square_confidence``
stayed empty, so ``doubtful_squares()`` -- the consumer the reader already has
-- had nothing to paint.

Parity is the test: the squares the IR calls doubtful must be exactly the
squares the trunk called uncertain, square for square, after the change of
numbering (the trunk reads ``a8`` first, the IR counts from ``a1``).  Inverting
the 64 indices, the roadmap's sabotage, makes the first test fail.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from caissa.core.model import Diagram, RecognitionPath
from caissa.ingest.pdf import finders
from caissa.ingest.pdf.importer import (
    DiagramHit,
    PdfImportOptions,
    import_pdf,
    square_confidences_from_holes,
)
from caissa.vision.classify.cvoff import ensure_cvoff_on_path

from .conftest import LOREM, PageSpec, lines_of, requires_pymupdf

try:
    CVOFF_ROOT: Path | None = ensure_cvoff_on_path()
except FileNotFoundError:  # pragma: no cover - only on a machine without the trunk
    CVOFF_ROOT = None

needs_trunk = pytest.mark.skipif(CVOFF_ROOT is None, reason="tronco ChessVisionOFF_Puro ausente")

DOUBT = 0.9
PLACEMENT = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R"


def _a1(index: int) -> int:
    """The **trunk's** numbering, so the parity below is against the trunk and not against
    the product's own copy of the conversion (which the first test pins separately)."""
    from chess_diagram_ocr.fen_utils import square_from_reading_index

    return int(square_from_reading_index(index))


# --------------------------------------------------------------------------
# The numbering and the classes are the trunk's
# --------------------------------------------------------------------------


@needs_trunk
def test_the_local_numbering_is_the_trunks_square_from_reading_index() -> None:
    from chess_diagram_ocr.config import PIECE_CLASSES
    from chess_diagram_ocr.fen_utils import square_from_reading_index, square_name

    for index in range(64):
        assert finders.a1_index_from_reading_index(index) == int(square_from_reading_index(index))
        assert finders.square_name_from_reading_index(index) == square_name(index)
    assert tuple(PIECE_CLASSES) == finders.PIECE_CLASSES


# --------------------------------------------------------------------------
# A real BoardPrediction from synthetic probabilities, through the finder and the IR
# --------------------------------------------------------------------------


def _probs_for(placement: str, *, doubtful: dict[int, float]) -> np.ndarray:
    """A (64, 13) matrix that reads ``placement`` with the given squares below the line."""
    classes = finders.PIECE_CLASSES
    rows = "".join("." * int(ch) if ch.isdigit() else ch for ch in placement.replace("/", ""))
    assert len(rows) == 64
    probs = np.full((64, 13), 0.001)
    for index, ch in enumerate(rows):
        chosen = classes.index("empty" if ch == "." else ch)
        top = doubtful.get(index, 0.995)
        probs[index, :] = (1.0 - top) / 12.0
        probs[index, chosen] = top
    return probs


def _oriented(prediction, *, ambiguous: bool, alternative=None):
    from chess_diagram_ocr.orientation import OrientedPrediction

    return OrientedPrediction(
        prediction=prediction,
        rotation=0,
        margin=0.004,
        ambiguous=ambiguous,
        reason="empate apertado entre as duas orientações (margem 0,004)",
        alternative=alternative,
    )


@needs_trunk
def test_doubtful_squares_of_the_ir_are_the_uncertain_squares_of_the_trunk() -> None:
    """Parity, square for square, after the change of numbering."""
    from chess_diagram_ocr.inference import prediction_from_probs

    # Reading index 36 is e4 (row 4 from the top, file e); 4 is e8.
    probs = _probs_for(PLACEMENT, doubtful={36: 0.62, 4: 0.81, 59: 0.88})
    prediction = prediction_from_probs(probs, uncertain_threshold=DOUBT, constrained=True)
    assert prediction.uncertain_squares, "a matriz sintética precisa produzir casas incertas"

    signal = finders.signal_from_prediction(_oriented(prediction, ambiguous=False))
    hit = DiagramHit(box=(0, 0, 100, 100), fen=f"{prediction.fen_board} w - - 0 1",
                     confidence=float(prediction.min_confidence), path=RecognitionPath.NEURAL,
                     **signal)
    assert len(hit.square_confidences) == 64
    expected = sorted(_a1(index) for index in prediction.uncertain_squares)
    doubtful = sorted(i for i, v in enumerate(hit.square_confidences) if v < DOUBT)
    assert doubtful == expected
    # Say the names out loud: e4 is a1-index 28, e8 is 60, d1 (reading 59) is 3.
    assert 28 in doubtful, "e4 lido a 0,62 tem de estar entre as duvidosas"
    assert 60 in doubtful, "e8 lido a 0,81 tem de estar entre as duvidosas"
    assert 3 in doubtful, "d1 (índice de leitura 59) lido a 0,88 tem de estar entre as duvidosas"
    assert hit.model_hash == ""
    assert hit.orientation_ambiguous is False
    assert hit.repairs == ()


@needs_trunk
def test_repairs_alternatives_and_the_ambiguous_orientation_travel_too() -> None:
    from chess_diagram_ocr.inference import prediction_from_probs

    # Two white kings: e1 and, wrongly, e4 -- the decoder has to repair one.
    two_kings = PLACEMENT.replace("2B1P3", "2B1K3")
    probs = _probs_for(two_kings, doubtful={36: 0.70})
    prediction = prediction_from_probs(probs, uncertain_threshold=DOUBT, constrained=True)
    assert prediction.decode is not None
    assert prediction.decode.changed_squares, "a posição com dois reis brancos tem de ser reparada"

    other = prediction_from_probs(_probs_for(PLACEMENT, doubtful={}), uncertain_threshold=DOUBT)
    signal = finders.signal_from_prediction(
        _oriented(prediction, ambiguous=True, alternative=other), model_hash="abc123"
    )
    repairs = signal["repairs"]
    assert [r.square for r in repairs] == [
        finders.square_name_from_reading_index(sq) for sq, _, _ in prediction.decode.changed_squares
    ]
    assert repairs[0].recognised == "K"
    assert repairs[0].confidence_before == pytest.approx(0.70)
    assert signal["orientation_ambiguous"] is True
    assert "empate" in signal["orientation_reason"]
    assert signal["model_hash"] == "abc123"
    # The discarded orientation comes first, then the runner-up per uncertain square.
    assert signal["alternatives"][0].fen.split()[0] == other.fen_board
    assert len(signal["alternatives"]) >= 2


@needs_trunk
@requires_pymupdf
def test_the_importer_copies_the_signal_into_the_recognition_result(pdf_file) -> None:
    """``RecognitionResult.doubtful_squares(0.9)`` is the trunk's ``uncertain_squares``."""
    from chess_diagram_ocr.inference import prediction_from_probs

    probs = _probs_for(PLACEMENT, doubtful={36: 0.62, 4: 0.81})
    prediction = prediction_from_probs(probs, uncertain_threshold=DOUBT, constrained=True)
    signal = finders.signal_from_prediction(
        _oriented(prediction, ambiguous=True), model_hash="f00d"
    )
    hit = DiagramHit(box=(72, 120, 272, 320), fen=f"{prediction.fen_board} w - - 0 1",
                     confidence=float(prediction.min_confidence), path=RecognitionPath.NEURAL,
                     method="contour", **signal)

    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=80, width_chars=60))
    spec.items.extend(lines_of(LOREM, x=72, y=500, width_chars=60))
    pdf = pdf_file([spec])
    result = import_pdf(pdf, PdfImportOptions(
        diagram_finder=lambda _page, _frame, _text: [hit], enable_ocr=False, games=False))
    diagrams = [b for b in result.document.body if isinstance(b, Diagram)]
    assert len(diagrams) == 1
    recognition = diagrams[0].recognition
    assert recognition is not None
    assert len(recognition.per_square_confidence) == 64
    assert sorted(recognition.doubtful_squares(DOUBT)) == sorted(
        _a1(index) for index in prediction.uncertain_squares
    )
    assert recognition.model_hash == "f00d"
    assert recognition.orientation_confidence == 0.5
    assert any(w.startswith("orientação ambígua: ") for w in recognition.warnings)


# --------------------------------------------------------------------------
# The vector route: 1,0 everywhere the font spoke, 0,0 where it was silent
# --------------------------------------------------------------------------


def test_the_vector_route_marks_its_holes_as_the_doubtful_squares() -> None:
    # Lattice (row 0 = top). White at the bottom: (0, 0) is a8 = 56, (7, 4) is e1 = 4.
    confidences = square_confidences_from_holes(((0, 0), (7, 4)), True)
    assert len(confidences) == 64
    assert [i for i, v in enumerate(confidences) if v < DOUBT] == [4, 56]
    # Black at the bottom: the lattice is the board turned around, (0, 0) is h1 = 7.
    flipped = square_confidences_from_holes(((0, 0),), False)
    assert [i for i, v in enumerate(flipped) if v < DOUBT] == [7]
    assert square_confidences_from_holes((), True) == (1.0,) * 64


def test_fill_holes_keeps_the_filled_cells_below_the_doubt_line() -> None:
    hit = DiagramHit(
        box=(0, 0, 10, 10),
        fen="8/8/8/8/8/8/8/R3K3 w - - 0 1",
        confidence=1.0,
        holes=((7, 0),),
        cells_box=(0, 0, 10, 10),
        square_confidences=square_confidences_from_holes(((7, 0),), True),
    )
    filled = finders.fill_holes(hit, "8/8/8/8/8/8/8/R3K3")
    assert filled is not None
    assert filled.holes == ()
    assert [i for i, v in enumerate(filled.square_confidences) if v < DOUBT] == [0], (
        "a1 veio do classificador: fica abaixo da linha de dúvida, o resto continua exato"
    )
    assert filled.square_confidences[0] == pytest.approx(finders.INFERRED_CONFIDENCE_CAP)


# --------------------------------------------------------------------------
# Corpus parity, with the real classifier (skips without the weights)
# --------------------------------------------------------------------------


@needs_trunk
@pytest.mark.slow
@pytest.mark.golden
def test_field_parity_with_the_real_classifier_on_a_corpus_page() -> None:
    """One field-set page through the shipped finder equals the trunk's own prediction."""
    import pymupdf
    from chess_diagram_ocr.field_eval import load_field_set

    assert CVOFF_ROOT is not None
    field_set = CVOFF_ROOT / "data" / "field_set.jsonl"
    pdf_dir = CVOFF_ROOT / "PDF"
    if not field_set.is_file() or not pdf_dir.is_dir():
        pytest.skip("conjunto de campo ou acervo ausente")
    try:
        from caissa.vision.classify.batched import load_classifier

        classifier = load_classifier()
    except Exception as exc:  # noqa: BLE001 - no torch, no weights, no GPU: skip, say why
        pytest.skip(f"classificador indisponível: {exc}")

    from chess_diagram_ocr.detection import detect_diagrams

    from caissa.vision.classify.page import predict_boards_batched

    page_entry = next(
        (
            p
            for p in load_field_set(field_set)
            if p.reviewed and p.diagrams and (pdf_dir / p.pdf).is_file()
        ),
        None,
    )
    if page_entry is None:
        pytest.skip("nenhuma página anotada com o PDF presente")
    finder = finders.raster_diagram_finder(classifier=classifier)
    with pymupdf.open(pdf_dir / page_entry.pdf) as doc:
        page = doc[page_entry.page]
        hits = [h for h in finder(page, SimpleNamespace(index=page_entry.page), None) if h.fen]
        rgb = finders._render_rgb(page, finders.DEFAULT_DPI)
        candidates = detect_diagrams(page, rgb, max_boards=finders.DEFAULT_MAX_BOARDS)
        oriented = predict_boards_batched([c.board_rgb for c in candidates], classifier)
    assert hits, "a página anotada tem de render pelo menos um diagrama lido"
    assert len(hits) == len(oriented)
    for hit, prediction in zip(hits, oriented, strict=True):
        doubtful = sorted(i for i, v in enumerate(hit.square_confidences) if v < DOUBT)
        assert doubtful == sorted(_a1(i) for i in prediction.prediction.uncertain_squares)
        assert hit.orientation_reason == prediction.reason
        assert hit.model_hash
