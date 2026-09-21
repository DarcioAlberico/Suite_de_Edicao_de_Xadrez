"""OCR_UI_ROADMAP_C2 passo C10: a diagram printed from Black's point of view.

The pieces are upright and rank 1 is at the top.  The lattice reads the
rows as printed, so the canonical placement is the rotated one -- the FEN
turns, the pixels do not.  Before this the vector path wrote
``white_at_bottom=False`` and the placement as printed: the renderer turned
the board for display and the PGN/EPUB carried the mirrored position.
"""

from __future__ import annotations

from pathlib import Path

from caissa.vision.detect import detect_vector_boards
from caissa.vision.detect.orientation import rotate_placement

from .conftest import build_diagram_pdf, merida_rows

PLACEMENT = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R"


def test_rotate_placement_is_the_other_side_and_its_own_inverse():
    turned = rotate_placement(PLACEMENT)
    assert turned == "R2KQBNR/PPP1PPPP/2N5/3P1B2/3p4/2n2n2/ppp1pppp/r1bkqb1r"
    assert rotate_placement(turned) == PLACEMENT
    assert rotate_placement("8/8/8/8/8/8/8/8") == "8/8/8/8/8/8/8/8"


def test_a_board_printed_from_blacks_side_yields_the_canonical_placement(merida_font: Path):
    printed = rotate_placement(PLACEMENT)   # what the page shows, top row first
    doc = build_diagram_pdf(merida_font, merida_rows(printed), coordinates="black")
    try:
        boards = detect_vector_boards(doc[0])
    finally:
        doc.close()
    assert len(boards) == 1
    board = boards[0]
    assert board.orientation.white_at_bottom is False
    assert board.orientation.source == "labels"
    assert board.piece_placement == PLACEMENT
    assert board.fen.split()[0] == PLACEMENT


def test_the_same_rows_under_whites_coordinates_read_as_printed(merida_font: Path):
    """The sabotage: mirror the labels and the placement comes out as printed."""
    printed = rotate_placement(PLACEMENT)
    doc = build_diagram_pdf(merida_font, merida_rows(printed), coordinates=True)
    try:
        boards = detect_vector_boards(doc[0])
    finally:
        doc.close()
    assert boards[0].orientation.white_at_bottom is True
    assert boards[0].piece_placement == printed


def test_the_raster_signal_turns_with_the_fen():
    from caissa.core.model.diagram import FenCandidate, SquareRepair
    from caissa.ingest.pdf.finders import rotate_signal

    signal = {
        "square_confidences": tuple(float(i) for i in range(64)),
        "repairs": (SquareRepair(square="a1", recognised="K", repaired="", reason="x",
                                 confidence_before=0.4),),
        "alternatives": (FenCandidate(fen=f"{PLACEMENT} w - - 0 1", score=0.5),),
        "orientation_reason": "r",
    }
    turned = rotate_signal(signal)
    assert turned["square_confidences"][0] == 63.0 and turned["square_confidences"][63] == 0.0
    assert turned["repairs"][0].square == "h8"
    assert turned["alternatives"][0].fen.split()[0] == rotate_placement(PLACEMENT)
    assert turned["orientation_reason"] == "r"
