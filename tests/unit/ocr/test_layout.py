"""Page layout: columns, reading order, furniture, footnotes, captions.

Synthetic pages first, because a hand-built page has an unarguable answer: this
file decides where the columns are, so it knows what reading order is correct.

Then real corpus pages, because a synthetic page is always cleaner than a book.
The corpus half asserts on properties that survive OCR noise — the column
count, the running head being removed, the printed folio being found — rather
than on exact strings, which would make the test a transcription check.
"""

from __future__ import annotations

import pytest

from caissa.ocr.layout.analyze import (
    LayoutConfig,
    LayoutInput,
    LayoutLine,
    RunningFurnitureDetector,
    analyze_document,
    analyze_page,
    body_font_size,
    detect_columns,
    fingerprint,
    is_page_number,
    lines_from_pdf_page,
)
from caissa.ocr.types import BBox, RegionKind

from .conftest import requires_pymupdf

PAGE = BBox.from_edges(0.0, 0.0, 600.0, 800.0)
LINE_H = 12.0


def line(text: str, x: float, y: float, *, width: float | None = None,
         size: float = 10.0) -> LayoutLine:
    """A line box at a chosen place, with a width that follows the text."""
    w = width if width is not None else 5.0 * max(len(text), 1)
    return LayoutLine(box=BBox.from_edges(x, y, x + w, y + LINE_H),
                      text=text, font_size=size)


def two_column_page(*, rows: int = 20, gutter: float = 40.0,
                    head: str | None = "CHAPTER FOUR",
                    folio: str | None = "57") -> LayoutInput:
    """Two columns of ``rows`` lines each, plus optional furniture.

    Left column carries ``L00``..; right column ``R00``.., so the correct
    reading order is every ``L`` then every ``R`` — checkable at a glance and
    impossible to satisfy by accident with a naive top-to-bottom sort.
    """
    left_x, right_x = 50.0, 50.0 + 230.0 + gutter
    lines: list[LayoutLine] = []
    if head is not None:
        lines.append(line(head, 220.0, 20.0))
    if folio is not None:
        lines.append(line(folio, 540.0, 20.0))
    top = 70.0
    for i in range(rows):
        y = top + i * (LINE_H + 6.0)
        lines.append(line(f"L{i:02d} the rook belongs behind the pawn",
                          left_x, y, width=230.0))
        lines.append(line(f"R{i:02d} and the defender simply waits",
                          right_x, y, width=230.0))
    return LayoutInput(page_box=PAGE, lines=tuple(lines))


def body_indices(layout, prefix: str) -> list[str]:
    return [layout.lines[i].text.split()[0] for i in layout.order
            if layout.lines[i].text.startswith(prefix)]


# --------------------------------------------------------------------------- #
# Small pieces
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text,expected", [
    ("57", True), ("  128  ", True), ("- 42 -", True), ("[9]", True),
    ("xiv", True), ("XVII", True),
    ("1.e4 e5", False), ("Chapter 4", False),
    ("The rook", False), ("2024", True),
    # Documented and deliberate: an empty line in the margin is furniture
    # whichever way it is classified, so the predicate says True.
    ("", True), ("   ", True),
])
def test_is_page_number(text, expected):
    assert is_page_number(text) is expected


def test_fingerprint_ignores_the_folio_but_not_the_words():
    """A running head is the same words with a different number every page."""
    assert fingerprint("CHAPTER FOUR   57") == fingerprint("CHAPTER FOUR   58")
    assert fingerprint("CHAPTER FOUR") != fingerprint("CHAPTER FIVE")


def test_body_font_size_is_the_dominant_size_not_the_mean():
    """One 28 pt heading must not drag the body size up."""
    lines = [line("heading", 50.0, 20.0, size=28.0)]
    lines += [line(f"body {i}", 50.0, 60.0 + 14.0 * i, size=10.0)
              for i in range(30)]
    assert body_font_size(lines) == pytest.approx(10.0, abs=0.5)


# --------------------------------------------------------------------------- #
# Columns
# --------------------------------------------------------------------------- #


def test_two_columns_are_found():
    # No furniture: a running head sits inside a column's x-range and would be
    # counted as one of its lines, which is a question for analyze_page and not
    # for the column finder.
    page = two_column_page(head=None, folio=None)
    columns = detect_columns(page.lines, page.page_box, LayoutConfig())
    assert len(columns) == 2
    left, right = columns
    assert left.box.x1 <= right.box.x0
    assert len(left.line_indices) == len(right.line_indices) == 20


def test_a_single_column_page_is_one_column():
    lines = tuple(line(f"line {i} of ordinary prose across the measure",
                       50.0, 60.0 + 20.0 * i, width=500.0) for i in range(25))
    columns = detect_columns(lines, PAGE, LayoutConfig())
    assert len(columns) == 1


def test_a_narrow_gutter_is_not_a_gutter():
    """Word spacing must not be mistaken for a column break."""
    page = two_column_page(gutter=4.0)
    columns = detect_columns(page.lines, page.page_box, LayoutConfig())
    assert len(columns) == 1, [(c.box.x0, c.box.x1) for c in columns]


def test_a_spanning_heading_does_not_destroy_the_gutter():
    """A full-width line crosses both columns; a naive projection loses the
    gutter entirely because of it."""
    page = two_column_page()
    lines = list(page.lines)
    lines.insert(2, line("A FULL WIDTH SECTION HEADING", 50.0, 50.0,
                         width=500.0, size=14.0))
    columns = detect_columns(tuple(lines), PAGE, LayoutConfig())
    assert len(columns) == 2


def test_column_count_is_capped():
    config = LayoutConfig(max_columns=2)
    lines: list[LayoutLine] = []
    for c in range(4):
        for i in range(12):
            lines.append(line(f"c{c} line {i}", 20.0 + c * 150.0,
                              60.0 + 20.0 * i, width=110.0))
    columns = detect_columns(tuple(lines), PAGE, config)
    assert len(columns) <= 2


def test_too_few_lines_gives_one_column_covering_the_page():
    """Fewer than four lines is not enough evidence for a gutter, and the
    honest answer is one column, not zero."""
    assert len(detect_columns((), PAGE, LayoutConfig())) == 1
    assert len(detect_columns((line("solitary", 50.0, 400.0),), PAGE,
                              LayoutConfig())) == 1


# --------------------------------------------------------------------------- #
# Reading order
# --------------------------------------------------------------------------- #


def test_reading_order_finishes_a_column_before_starting_the_next():
    """The property that a top-to-bottom sort gets wrong on every book."""
    layout = analyze_page(two_column_page())
    assert layout.column_count == 2

    order = [layout.lines[i].text.split()[0] for i in layout.order]
    body = [tag for tag in order if tag[0] in "LR"]
    assert body == [f"L{i:02d}" for i in range(20)] + \
                   [f"R{i:02d}" for i in range(20)], body[:6]


def test_reading_order_within_a_column_is_top_to_bottom():
    layout = analyze_page(two_column_page())
    assert body_indices(layout, "L") == [f"L{i:02d}" for i in range(20)]


def test_body_text_joins_in_reading_order():
    layout = analyze_page(two_column_page())
    text = layout.body_text()
    assert text.index("L00") < text.index("L19") < text.index("R00")


def test_a_spanning_heading_is_read_before_both_columns():
    page = two_column_page(head=None, folio=None)
    lines = [line("A SECTION HEADING", 50.0, 45.0, width=500.0, size=16.0)]
    lines += list(page.lines)
    layout = analyze_page(LayoutInput(page_box=PAGE, lines=tuple(lines)))
    order = [layout.lines[i].text for i in layout.order]
    assert order[0].startswith("A SECTION HEADING"), order[:3]


def test_reading_order_is_deterministic():
    page = two_column_page()
    orders = [analyze_page(page).order for _ in range(5)]
    assert all(o == orders[0] for o in orders)


# --------------------------------------------------------------------------- #
# Running heads and folios
# --------------------------------------------------------------------------- #


def test_a_folio_is_furniture_on_a_single_page():
    """A page number is recognisable without seeing another page."""
    layout = analyze_page(two_column_page(head=None, folio="57"))
    kinds = {layout.lines[i].text.strip(): k
             for i, k in enumerate(layout.kinds)}
    assert kinds["57"] is RegionKind.PAGE_NUMBER
    assert "57" not in layout.body_text()


def test_a_running_head_needs_more_than_one_page():
    """One page cannot tell a running head from a heading, and must say so
    rather than guess."""
    layout = analyze_page(two_column_page(head="CHAPTER FOUR"))
    assert any("repete" in note for note in layout.notes), layout.notes
    assert layout.lines_of_kind(RegionKind.HEADER) == ()


def test_a_running_head_is_removed_across_a_document():
    pages = [two_column_page(head="SECRETS OF PAWNLESS ENDINGS",
                             folio=str(100 + n)) for n in range(8)]
    layouts = analyze_document(pages)

    assert len(layouts) == 8
    for n, layout in enumerate(layouts):
        heads = [l.text.strip() for l in
                 layout.lines_of_kind(RegionKind.HEADER)]
        assert heads == ["SECRETS OF PAWNLESS ENDINGS"], (n, heads)
        assert "SECRETS" not in layout.body_text()
        folios = [l.text.strip() for l in
                  layout.lines_of_kind(RegionKind.PAGE_NUMBER)]
        assert folios == [str(100 + n)], (n, folios)


#: Headings that differ in their *words*.  ``SECTION 1``..``SECTION 8`` would
#: not do: ``fingerprint`` strips digits on purpose, so those eight strings
#: share one fingerprint and are — correctly — a running head with a folio.
_DISTINCT_HEADS = (
    "THE ROOK ENDING", "OPPOSITE BISHOPS", "QUEEN AGAINST ROOK",
    "PAWN RACES", "THE LUCENA POSITION", "FORTRESS DRAWS",
    "ZUGZWANG", "TRIANGULATION",
)


def test_a_heading_that_does_not_repeat_stays_in_the_body():
    """Removing a one-off heading because it sits in the top margin would lose
    real text.  Repetition is the evidence, not position."""
    pages = [two_column_page(head=head, folio=str(10 + n))
             for n, head in enumerate(_DISTINCT_HEADS)]
    layouts = analyze_document(pages)
    for n, layout in enumerate(layouts):
        assert _DISTINCT_HEADS[n] in layout.body_text(), n
        # ...while the folio, which is furniture on its own evidence, goes.
        assert layout.lines_of_kind(RegionKind.PAGE_NUMBER), n


def test_a_head_that_differs_only_by_its_folio_is_still_a_running_head():
    """``CHAPTER FOUR 57`` and ``CHAPTER FOUR 58`` are the same head.

    ``fingerprint`` drops digits for exactly this reason, and pinning it here
    keeps the next reader from "fixing" that as a bug.
    """
    pages = [two_column_page(head=f"CHAPTER FOUR {57 + n}", folio=None)
             for n in range(8)]
    layouts = analyze_document(pages)
    for n, layout in enumerate(layouts):
        assert layout.lines_of_kind(RegionKind.HEADER), n
        assert "CHAPTER FOUR" not in layout.body_text(), n


def test_min_repeats_is_honoured():
    """Two repetitions can be coincidence; the default asks for three."""
    detector = RunningFurnitureDetector(LayoutConfig(min_repeats=3,
                                                     repeat_frac=0.0))
    head = line("A REPEATED HEAD", 220.0, 20.0)
    for _ in range(2):
        detector.observe([head], PAGE)
    assert detector.finalize() == frozenset()

    detector = RunningFurnitureDetector(LayoutConfig(min_repeats=3,
                                                     repeat_frac=0.0))
    for _ in range(3):
        detector.observe([head], PAGE)
    assert detector.finalize()


def test_a_footer_is_found_at_the_bottom():
    pages = []
    for n in range(6):
        page = two_column_page(head=None, folio=None, rows=12)
        lines = list(page.lines)
        lines.append(line("A CHESS BOOK", 220.0, 770.0))
        pages.append(LayoutInput(page_box=PAGE, lines=tuple(lines)))
    layouts = analyze_document(pages)
    for layout in layouts:
        feet = [l.text.strip() for l in layout.lines_of_kind(RegionKind.FOOTER)]
        assert feet == ["A CHESS BOOK"], feet


# --------------------------------------------------------------------------- #
# Footnotes
# --------------------------------------------------------------------------- #


def footnote_page() -> LayoutInput:
    lines = [line(f"body line {i} running across the measure",
                  50.0, 60.0 + 20.0 * i, width=500.0, size=10.0)
             for i in range(28)]
    lines.append(line("1 A note about the Rubinstein variation, set smaller.",
                      50.0, 700.0, width=500.0, size=8.0))
    lines.append(line("2 And a second note, also at the foot of the page.",
                      50.0, 715.0, width=500.0, size=8.0))
    return LayoutInput(page_box=PAGE, lines=tuple(lines))


def test_footnotes_are_separated_from_the_body():
    """Separated means *labelled and grouped*, not deleted.

    A footnote is real text and stays in reading order; what has to happen is
    that it becomes its own region of its own kind, so an exporter can set it
    as a note and the notation pass does not read it as part of the sentence
    above it.
    """
    layout = analyze_page(footnote_page())
    notes = [l.text for l in layout.lines_of_kind(RegionKind.FOOTNOTE)]
    assert len(notes) == 2, [str(k) for k in layout.kinds]
    assert layout.signals["footnotes"] == 2

    note_regions = [r for r in layout.regions if r.kind is RegionKind.FOOTNOTE]
    assert len(note_regions) == 1, "as duas notas deveriam formar um bloco só"
    body = [r for r in layout.regions if r.kind is RegionKind.PARAGRAPH]
    assert body and all(r.box.y1 <= note_regions[0].box.y0 + 1.0 for r in body)


def test_a_single_small_line_at_the_foot_is_not_a_footnote():
    """One small line at the bottom is a folio or a colophon.  Calling it a
    footnote would delete it from the body on every page of some books."""
    lines = [line(f"body line {i}", 50.0, 60.0 + 20.0 * i,
                  width=500.0, size=10.0) for i in range(28)]
    lines.append(line("a lone small line", 50.0, 715.0, width=200.0, size=8.0))
    layout = analyze_page(LayoutInput(page_box=PAGE, lines=tuple(lines)))
    assert layout.lines_of_kind(RegionKind.FOOTNOTE) == ()


def test_a_small_line_mid_page_is_not_a_footnote():
    lines = [line(f"body line {i}", 50.0, 60.0 + 20.0 * i,
                  width=500.0, size=10.0) for i in range(28)]
    lines.append(line("a small caption in the middle", 50.0, 300.0,
                      width=200.0, size=8.0))
    lines.append(line("another small one", 50.0, 316.0, width=200.0, size=8.0))
    layout = analyze_page(LayoutInput(page_box=PAGE, lines=tuple(lines)))
    assert layout.lines_of_kind(RegionKind.FOOTNOTE) == ()


# --------------------------------------------------------------------------- #
# Captions and diagram labels
# --------------------------------------------------------------------------- #


def test_a_caption_is_attached_to_its_diagram():
    diagram = BBox.from_edges(180.0, 200.0, 420.0, 440.0)
    lines = [line(f"body {i}", 50.0, 60.0 + 18.0 * i, width=500.0)
             for i in range(6)]
    lines.append(line("Diagram 14", 260.0, 448.0, width=80.0, size=9.0))
    layout = analyze_page(LayoutInput(page_box=PAGE, lines=tuple(lines),
                                      diagrams=(diagram,)))
    captions = [r for r in layout.regions if r.kind is RegionKind.CAPTION]
    assert captions, [str(k) for k in layout.kinds]
    assert captions[0].attached_to == 0
    assert captions[0].attached_kind == "diagram"


def test_board_coordinate_labels_are_not_body_text():
    """``a``..``h`` printed around a diagram must not enter the prose."""
    diagram = BBox.from_edges(180.0, 200.0, 420.0, 440.0)
    lines = [line(f"body {i}", 50.0, 60.0 + 18.0 * i, width=500.0)
             for i in range(6)]
    for i, ch in enumerate("abcdefgh"):
        lines.append(LayoutLine(
            box=BBox.from_edges(190.0 + i * 28.0, 420.0,
                                200.0 + i * 28.0, 432.0),
            text=ch, font_size=7.0))
    layout = analyze_page(LayoutInput(page_box=PAGE, lines=tuple(lines),
                                      diagrams=(diagram,)))
    body = layout.body_text()
    for ch in "abcdefgh":
        assert f"\n{ch}\n" not in f"\n{body}\n", ch


# --------------------------------------------------------------------------- #
# Robustness
# --------------------------------------------------------------------------- #


def test_an_empty_page_analyses_without_raising():
    layout = analyze_page(LayoutInput(page_box=PAGE, lines=()))
    assert layout.order == ()
    assert layout.body_text() == ""
    assert layout.describe_pt()


def test_a_one_line_page_analyses():
    layout = analyze_page(LayoutInput(
        page_box=PAGE, lines=(line("only this", 50.0, 400.0),)))
    assert len(layout.order) <= 1


def test_signals_are_reported():
    layout = analyze_page(two_column_page())
    for key in ("line_count", "columns", "body_font_size", "furniture"):
        assert key in layout.signals, sorted(layout.signals)


# --------------------------------------------------------------------------- #
# The corpus (docs/quality/CORPUS.md)
# --------------------------------------------------------------------------- #


@pytest.mark.golden
@requires_pymupdf
def test_nunn_pages_are_two_columns(corpus_doc):
    """E2, a Gambit book set in two columns.  Measured 2026-09-07."""
    doc = corpus_doc("nunn_pawnless")
    counts = []
    for index in (118, 120, 122, 124, 126, 128):
        page = doc[index]
        rect = page.rect
        layout = analyze_page(LayoutInput(
            page_box=BBox.from_edges(0.0, 0.0, rect.width, rect.height),
            lines=lines_from_pdf_page(page), page_index=index))
        counts.append(layout.column_count)
    assert counts.count(2) >= 5, counts


@pytest.mark.golden
@requires_pymupdf
def test_nunn_running_head_and_folio_are_removed(corpus_doc):
    """Measured 2026-09-07 over pages 118-129: the verso running head
    ``SECRETS OF PAWNLESS ENDINGS`` repeats and is stripped; the printed folio
    is found on 11 of 12 pages.

    Note the limitation this also pins: the *recto* running head is the chapter
    title, which changes from section to section, so it does not repeat often
    enough to be furniture and stays in the body.  That is the correct
    behaviour for a repetition-based rule and the wrong answer for the book;
    fixing it needs a section model, which is F1's, not F5's.
    """
    doc = corpus_doc("nunn_pawnless")
    pages = []
    for index in range(118, 130):
        page = doc[index]
        rect = page.rect
        pages.append(LayoutInput(
            page_box=BBox.from_edges(0.0, 0.0, rect.width, rect.height),
            lines=lines_from_pdf_page(page), page_index=index))
    layouts = analyze_document(pages)

    stripped = sum(
        1 for layout in layouts
        if any("PAWNLESS" in l.text.upper()
               for l in layout.lines_of_kind(RegionKind.HEADER)))
    assert stripped >= 5, f"cabeçalho corrente removido em apenas {stripped}/12"

    for layout in layouts:
        assert "SECRETS OF PAWNLESS ENDINGS" not in layout.body_text().upper()

    folios = sum(1 for layout in layouts
                 if layout.lines_of_kind(RegionKind.PAGE_NUMBER))
    assert folios >= 10, f"fólio encontrado em apenas {folios}/12 páginas"


@pytest.mark.golden
@requires_pymupdf
def test_corpus_reading_order_keeps_columns_apart(corpus_doc):
    """On a real two-column page, reading order must not interleave columns.

    Asserted as a property rather than as a string: within the body order, the
    left column's lines must all precede the right column's.  That is exactly
    what a naive top-to-bottom sort violates, and it is checkable without
    knowing what the page says.
    """
    doc = corpus_doc("nunn_pawnless")
    page = doc[120]
    rect = page.rect
    layout = analyze_page(LayoutInput(
        page_box=BBox.from_edges(0.0, 0.0, rect.width, rect.height),
        lines=lines_from_pdf_page(page), page_index=120))
    assert layout.column_count == 2

    boundary = layout.columns[0].box.x1
    sides = [0 if layout.lines[i].box.cx < boundary else 1
             for i in layout.order]
    # Once the right column starts, the left must never come back.
    assert sides == sorted(sides), sides
