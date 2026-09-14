"""RapidOCR's detection order becomes reading order before it reaches the arbiter.

Measured on 2026-09-14 (OCR_UI_ROADMAP passo 1): on the ``twocol`` items the
engine returned the two columns interleaved line by line (``L1 R1 L2 R2``),
which is a CER of 0,7 on a region it had actually read correctly.  The fix is
geometry, not a model, so it is tested as geometry.
"""

from __future__ import annotations

from caissa.ocr.engines.rapidocr import _reading_order, _script_of


def _box(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_two_columns_come_out_column_by_column_top_down() -> None:
    def prose(tag: str) -> str:
        return f"{tag} is a full line of prose, as a book prints it"

    interleaved = [
        (_box(0, 0, 100, 10), prose("L1"), 0.9), (_box(120, 0, 220, 10), prose("R1"), 0.9),
        (_box(0, 12, 100, 22), prose("L2"), 0.9), (_box(120, 12, 220, 22), prose("R2"), 0.9),
        (_box(120, 24, 220, 34), prose("R3"), 0.9), (_box(0, 24, 100, 34), prose("L3"), 0.9),
    ]
    assert [t[:2] for _, t, _ in _reading_order(interleaved)] == ["L1", "L2", "L3", "R1", "R2", "R3"]


def test_fragments_on_one_baseline_read_left_to_right() -> None:
    split = [
        (_box(45, 24, 100, 34), "that it is White's move", 0.9),
        (_box(0, 24, 40, 34), "suppose", 0.9),
        (_box(0, 0, 100, 10), "first line", 0.9),
    ]
    assert [t for _, t, _ in _reading_order(split)] == [
        "first line", "suppose", "that it is White's move"]


def test_a_table_of_moves_reads_row_by_row() -> None:
    """White's column beside Black's is one game, not two columns of prose."""
    table = [
        (_box(0, 0, 40, 10), "1 d4", 0.9), (_box(60, 0, 100, 10), "♘f6", 0.9),
        (_box(0, 12, 40, 22), "2 c4", 0.9), (_box(60, 12, 100, 22), "c5", 0.9),
        (_box(0, 24, 40, 34), "3 ♘f3", 0.9), (_box(60, 24, 100, 34), "cxd4", 0.9),
    ]
    assert [t for _, t, _ in _reading_order(table)] == [
        "1 d4", "♘f6", "2 c4", "c5", "3 ♘f3", "cxd4"]


def test_two_columns_of_prose_are_not_a_table() -> None:
    prose = [
        (_box(0, 0, 100, 10), "the techniques of cutting the king off", 0.9),
        (_box(120, 0, 220, 10), "3.Bd8+-) 3.a6 is the same. 2.a6 Kc6", 0.9),
        (_box(0, 12, 100, 22), "suppose that it is White's move", 0.9),
        (_box(120, 12, 220, 22), "of 4.Bd8, White distracts the king", 0.9),
    ]
    assert [t[:3] for _, t, _ in _reading_order(prose)] == ["the", "sup", "3.B", "of "]


def test_an_entry_without_geometry_keeps_its_place_at_the_end() -> None:
    entries = [(None, "loose", 0.5), (_box(0, 0, 10, 10), "boxed", 0.9)]
    assert [t for _, t, _ in _reading_order(entries)] == ["boxed", "loose"]


def test_the_script_follows_the_first_language_of_the_task() -> None:
    assert _script_of("rus+eng") == "eslav"
    assert _script_of("bul") == "cyrillic"
    assert _script_of("eng+rus") == "latin"
    assert _script_of("por") == "latin"
    assert _script_of("") == "latin"
