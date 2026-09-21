"""Layout for a page with no text layer — OCR_UI_ROADMAP_C2 passo B1.

The gutter is found by projecting *lines* made of *word* boxes, exactly as
the trunk does with connected components (``text/colunas.py``).  The tests
build the two pages the method must tell apart: a two-column page whose
whole-page reading came back as lines crossing the gutter (``twocol:d:9``,
five lines of 2.300 px over a 90 px gutter), and a single-column page of
justified text, whose word gaps never line up.  The sabotage is the config
switch the benchmark uses: with the layout off the page is one region.
"""

from __future__ import annotations

import numpy as np
import pytest

from caissa.ocr.engines.base import EngineCapabilities, EngineLevel
from caissa.ocr.layout.scan import (
    ScanLayoutConfig,
    find_gutters,
    scan_layout,
    split_at_gutters,
)
from caissa.ocr.page import PageConfig, PageRecognizer, PageTask
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

# --------------------------------------------------------------------------- #
# Building readings
# --------------------------------------------------------------------------- #

CHAR_W = 12.0
LINE_H = 30.0


def _words(text: str, x: float, y: float, *, gap: float = 8.0,
           confidence: float = 0.95) -> list[OcrWord]:
    out = []
    for token in text.split():
        w = CHAR_W * len(token)
        out.append(OcrWord(text=token, box=BBox(x, y, w, LINE_H), confidence=confidence))
        x += w + gap
    return out


def _line(words: list[OcrWord]) -> OcrLine:
    return OcrLine(words=tuple(words), box=BBox.union_of([w.box for w in words]))


def two_column_reading(left: list[str], right: list[str], *, gutter: float = 90.0,
                       x0: float = 40.0) -> OcrResult:
    """What PSM 3 makes of a two-column page: one line per row, both columns
    in it.  The right column starts one gutter after the widest left line."""
    lines = []
    column_w = max(_line(_words(a, x0, 0.0)).box.x1 for a in left) - x0
    for n, (a, b) in enumerate(zip(left, right, strict=True)):
        y = 40.0 + n * (LINE_H + 20.0)
        lines.append(_line(_words(a, x0, y) + _words(b, x0 + column_w + gutter, y)))
    return OcrResult(engine="tesseract", lang="eng", lines=tuple(lines),
                     region_kind=RegionKind.PAGE, duration_s=0.1)


def single_column_reading(rows: list[str], *, x0: float = 40.0) -> OcrResult:
    """Justified prose: the gap after each word differs from line to line, so
    no x is free on every line."""
    lines = []
    for n, row in enumerate(rows):
        y = 40.0 + n * (LINE_H + 20.0)
        lines.append(_line(_words(row, x0, y, gap=8.0 + 3.0 * (n % 5))))
    return OcrResult(engine="tesseract", lang="eng", lines=tuple(lines),
                     region_kind=RegionKind.PAGE, duration_s=0.1)


LEFT = [
    "after Kc3 Kf6 White is in zugzwang if",
    "Kxe6 Nf3 Ne5 axb3 Kxb3 Nd4 Kc3 Nxe6 Kb4",
    "Nd4 Kc5 Ke5 defending the knight and",
    "remarkable Kd2 changes everything now",
    "Black is in zugzwang Ke7 b3 axb3 Kxb3",
    "the win requires very good technique",
    "stumble into a draw it is not possible",
    "lines neither is it desirable we will",
    "White and show some pitfalls to avoid",
    "should be mentioned here as well too",
    "one more line to pass the twelve floor",
    "and another one to be safe about it",
]
RIGHT = [
    "But the win requires very good technique",
    "stumble into a draw It is not possible",
    "lines neither is it desirable We will",
    "White and show some pitfalls to avoid",
    "h5 should be mentioned as the move",
    "the second column keeps going on",
    "with more prose of the same kind",
    "until the twelve line floor is met",
    "so that one crossing line is allowed",
    "and the gutter survives the count",
    "which is what the trunk measured",
    "on the Nunn and the Aagaard pages",
]


# --------------------------------------------------------------------------- #
# Gutters
# --------------------------------------------------------------------------- #


def test_a_two_column_reading_has_one_interior_gutter():
    reading = two_column_reading(LEFT, RIGHT)
    gutters = find_gutters(reading.lines)
    assert len(gutters) == 1
    a, b = gutters[0]
    # The gutter ends where the right column starts.  It begins where the
    # *second* widest left line ends: on twelve lines one crossing line is
    # tolerated, and the widest line is exactly that one.
    right_x0 = min(w.box.x0 for line in reading.lines for w in line.words if w.box.x0 > 500)
    left_ends = sorted({line.words[len(LEFT[n].split()) - 1].box.x1
                        for n, line in enumerate(reading.lines)})
    assert b == pytest.approx(right_x0, abs=2.0), gutters
    assert left_ends[-2] - 2.0 <= a <= left_ends[-1], (gutters, left_ends)


def test_justified_single_column_has_no_gutter():
    """The control: Darcy Lima 0/39 in the trunk's measurement."""
    reading = single_column_reading(LEFT + RIGHT)
    assert find_gutters(reading.lines) == []


def test_one_crossing_line_is_tolerated_on_a_long_page_only():
    """A centred running head crosses the gutter; on twelve lines it is
    forgiven, on five it is not (one of five would invent columns)."""
    long_page = two_column_reading(LEFT, RIGHT)
    head = _line(_words("A running head across both columns of this page", 300.0, 5.0))
    with_head = OcrResult(engine="tesseract", lang="eng",
                          lines=(head, *long_page.lines), region_kind=RegionKind.PAGE,
                          duration_s=0.1)
    assert len(find_gutters(with_head.lines)) == 1

    short_page = two_column_reading(LEFT[:4], RIGHT[:4])
    with_head = OcrResult(engine="tesseract", lang="eng",
                          lines=(head, *short_page.lines), region_kind=RegionKind.PAGE,
                          duration_s=0.1)
    assert find_gutters(with_head.lines) == []
    # Without the head the short page still has its gutter: the floor is
    # about tolerating a crossing, not about page length.
    assert len(find_gutters(short_page.lines)) == 1


def test_a_band_too_narrow_to_be_a_column_is_merged():
    """A contents page: title, wide gap, page number.  The number band is
    2 % of the text width — a gutter there reads all titles then all numbers."""
    lines = []
    for n in range(14):
        y = 40.0 + n * (LINE_H + 20.0)
        lines.append(_line(_words(f"Chapter {n} the title of the chapter", 40.0, y)
                           + _words(str(10 + n), 1500.0, y)))
    reading = OcrResult(engine="tesseract", lang="eng", lines=tuple(lines),
                        region_kind=RegionKind.PAGE, duration_s=0.1)
    assert find_gutters(reading.lines) == []


def test_a_gutter_below_the_floor_is_not_one():
    """The word gap of a line is not a gutter even when it lines up: the
    floor is 0,8 median character widths."""
    # ``gutter=0``: the right column starts one word gap (8 px) after the
    # widest left line, under the 0,8 × 12 px floor.
    reading = two_column_reading(LEFT, RIGHT, gutter=0.0)
    assert find_gutters(reading.lines) == []
    # ...and twice the floor is a gutter again.
    assert len(find_gutters(two_column_reading(LEFT, RIGHT, gutter=20.0).lines)) == 1


# --------------------------------------------------------------------------- #
# Splitting
# --------------------------------------------------------------------------- #


def test_split_deals_each_line_into_one_per_column():
    reading = two_column_reading(LEFT, RIGHT)
    split = split_at_gutters(reading, find_gutters(reading.lines))
    assert len(split.lines) == 2 * len(LEFT)
    # Each new line is boxed by its own words and keeps their order.
    assert split.lines[0].text == LEFT[0]
    assert split.lines[1].text == RIGHT[0]
    assert split.lines[0].box.x1 < split.lines[1].box.x0 - 80.0
    assert split.meta["split_at_gutters"] == 1


def test_split_without_gutters_is_the_same_result():
    reading = single_column_reading(LEFT)
    assert split_at_gutters(reading, []) is reading


# --------------------------------------------------------------------------- #
# The layout
# --------------------------------------------------------------------------- #


def test_scan_layout_orders_the_columns_left_then_right():
    reading = two_column_reading(LEFT, RIGHT)
    page_box = BBox(0.0, 0.0, 2400.0, 700.0)
    laid_out = scan_layout(reading, page_box=page_box)
    assert laid_out is not None
    assert laid_out.columns == 2
    assert laid_out.layout.column_count == 2
    ordered = [laid_out.layout.lines[i].text for i in laid_out.layout.order]
    assert ordered == LEFT + RIGHT
    assert laid_out.signals["scan_columns"] == 2


def test_scan_layout_is_none_for_one_column():
    reading = single_column_reading(LEFT + RIGHT)
    assert scan_layout(reading, page_box=BBox(0.0, 0.0, 2400.0, 1300.0)) is None


def test_scan_layout_tags_a_column_of_moves_as_movetext():
    moves = [
        "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6",
        "5.O-O Be7 6.Re1 b5 7.Bb3 d6 8.c3 O-O",
        "9.h3 Nb8 10.d4 Nbd7 11.Nbd2 Bb7 12.Bc2",
        "Re8 13.Nf1 Bf8 14.Ng3 g6 15.a4 c5 16.d5",
    ] * 3
    reading = two_column_reading(moves, RIGHT)
    laid_out = scan_layout(reading, page_box=BBox(0.0, 0.0, 2400.0, 700.0))
    assert laid_out is not None
    kinds = {r.column_index: r.kind for r in laid_out.layout.regions}
    assert kinds[0] is RegionKind.MOVETEXT
    assert kinds[1] is RegionKind.PARAGRAPH
    assert laid_out.signals["scan_movetext_regions"] == 1


def test_the_switch_turns_the_layout_off():
    """The sabotage of the benchmark: no gutter is ever found."""
    reading = two_column_reading(LEFT, RIGHT)
    assert scan_layout(reading, page_box=BBox(0.0, 0.0, 2400.0, 700.0),
                       config=ScanLayoutConfig(enabled=False)) is None


def test_layout_in_points_when_the_page_is_a_pdf():
    """An image-only PDF page lays out in points: the pixel boxes of the
    reading are divided by the scale, the split reading stays in pixels."""
    reading = two_column_reading(LEFT, RIGHT)
    scale = 300.0 / 72.0
    laid_out = scan_layout(reading, page_box=BBox(0.0, 0.0, 2400.0 / scale, 700.0 / scale),
                           scale=scale)
    assert laid_out is not None
    first = laid_out.layout.lines[0]
    assert first.box.x0 == pytest.approx(40.0 / scale)
    assert laid_out.result.lines[0].box.x0 == pytest.approx(40.0)


# --------------------------------------------------------------------------- #
# Through the page loop
# --------------------------------------------------------------------------- #


class MergingOcr:
    """A level-1 engine that reads a whole page the way PSM 3 does — one line
    per row across both columns — and counts how often it was asked."""

    name = "merging_ocr"

    def __init__(self, reading: OcrResult):
        self.reading = reading
        self.calls = 0

    def available(self) -> bool:
        return True

    def unavailable_reason(self):
        return None

    def languages(self) -> set[str]:
        return {"eng"}

    def supports_language(self, lang: str) -> bool:
        return True

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.TESSERACT, cost_per_megapixel_s=0.4,
            supports_char_boxes=False, supports_confidence=True,
            handles_layout=True, requires_pdf_page=False)

    def recognize(self, image, *, lang="eng", psm_hint=RegionKind.PARAGRAPH) -> OcrResult:
        self.calls += 1
        return self.reading


def _blank(width: int = 2400, height: int = 700) -> np.ndarray:
    return np.full((height, width), 255, dtype=np.uint8)


def _recognizer(engine, config: PageConfig | None = None) -> PageRecognizer:
    """The page loop with the decision layer off: a blank raster has no ink
    under the mock's words, and an abstained page is (rightly) never laid
    out — what is under test here is the layout, not the evidence."""
    from caissa.ocr.arbiter import ArbiterConfig

    config = config or PageConfig()
    config.arbiter = ArbiterConfig(decision_enabled=False)
    return PageRecognizer([engine], config)


def test_the_page_loop_reads_a_scan_in_two_regions_in_reading_order():
    engine = MergingOcr(two_column_reading(LEFT, RIGHT))
    outcome = _recognizer(engine).run(PageTask(image=_blank(), lang="eng", dpi=300.0))
    assert not outcome.whole_page
    assert len(outcome.regions) == 2
    assert outcome.signals["scan_layout"] is True
    assert outcome.text.split("\n") == LEFT + RIGHT
    # The default slices the whole-page reading: one call, not three.
    assert engine.calls == 1
    assert any("leiaute em scan" in n for n in outcome.notes)


def test_the_regions_are_reread_when_asked():
    engine = MergingOcr(two_column_reading(LEFT, RIGHT))
    outcome = _recognizer(engine, PageConfig(scan_reread=True)).run(
        PageTask(image=_blank(), lang="eng", dpi=300.0))
    assert not outcome.whole_page and len(outcome.regions) == 2
    assert engine.calls == 3


def test_sabotage_one_region_when_the_layout_is_off():
    """The benchmark's ``SOL_CONFIG='{"page": {"scan": {"enabled": false}}}'``."""
    engine = MergingOcr(two_column_reading(LEFT, RIGHT))
    outcome = _recognizer(engine, PageConfig(scan=ScanLayoutConfig(enabled=False))).run(
        PageTask(image=_blank(), lang="eng", dpi=300.0))
    assert outcome.whole_page
    assert len(outcome.regions) == 1
    assert outcome.text != "\n".join(LEFT + RIGHT)


def test_a_single_column_scan_is_still_one_region():
    engine = MergingOcr(single_column_reading(LEFT + RIGHT))
    outcome = _recognizer(engine).run(
        PageTask(image=_blank(height=1300), lang="eng", dpi=300.0))
    assert outcome.whole_page
    assert len(outcome.regions) == 1


def test_a_table_of_three_bands_is_not_split():
    """``table:2``: every row has an entry in every band, so the gutters are
    as clean as a column's -- and reading band by band scrambles the rows.
    Three bands is a table, not columns."""
    rows = [("11. Capablanca Marshall", "Nova Iorque 1918", "Ruy Lopez 9"),
            ("12. Tal Botvinnik", "Moscovo 1960", "Francesa Winawer 203"),
            ("13. Anand Kramnik", "Bona 2008", "Gambito da Dama 88"),
            ("14. Carlsen Nakamura", "Wijk aan Zee 2011", "India do Rei 301"),
            ("15. Steinitz Zukertort", "St Louis 1886", "Abertura Escocesa 15")]
    lines = []
    for n, (a, b, c) in enumerate(rows):
        y = 40.0 + n * (LINE_H + 20.0)
        lines.append(_line(_words(a, 40.0, y) + _words(b, 500.0, y) + _words(c, 900.0, y)))
    reading = OcrResult(engine="tesseract", lang="eng", lines=tuple(lines),
                        region_kind=RegionKind.PAGE, duration_s=0.1)
    assert len(find_gutters(reading.lines)) == 2
    assert scan_layout(reading, page_box=BBox(0.0, 0.0, 1400.0, 400.0)) is None
    # ...unless a caller allows three columns and short bands.
    assert scan_layout(reading, page_box=BBox(0.0, 0.0, 1400.0, 400.0),
                       config=ScanLayoutConfig(max_columns=3, min_band_chars=3)) is not None


def test_the_two_bands_of_a_move_list_are_not_columns():
    """``28 ♘f2 | ♗h4!``: White's moves and Black's in two aligned bands with a clean
    gutter -- reading band by band would put every White move before every Black one."""
    rows = [("27...", "Bd8"), ("28 Nf2", "Bh4!"), ("29 Ree2", "Qe7"), ("30 Kh1", "Rf8"),
            ("31 Qd3", "g5"), ("32 Nd1", "Rf7")]
    lines = []
    for n, (a, b) in enumerate(rows):
        y = 40.0 + n * (LINE_H + 20.0)
        lines.append(_line(_words(a, 40.0, y) + _words(b, 200.0, y)))
    reading = OcrResult(engine="tesseract", lang="eng", lines=tuple(lines),
                        region_kind=RegionKind.PAGE, duration_s=0.1)
    assert len(find_gutters(reading.lines)) == 1
    assert scan_layout(reading, page_box=BBox(0.0, 0.0, 600.0, 400.0)) is None
    assert scan_layout(reading, page_box=BBox(0.0, 0.0, 600.0, 400.0),
                       config=ScanLayoutConfig(min_band_chars=3)) is not None
