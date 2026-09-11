"""FEN -> PDF -> detector -> FEN, over hundreds of real positions.

This is the load-bearing test of front F3-A.  If the vector path is exact, it
passes at 100 %; anything less is a bug, not a tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.vision.detect import detect_vector_boards
from caissa.vision.detect.font_catalog import family_by_key

from .conftest import (
    MERIDA_DARK,
    MERIDA_LIGHT,
    build_diagram_pdf,
    build_overprint_pdf,
    family_rows,
    find_font,
    merida_rows,
)


def _read_one(doc: object) -> tuple[str | None, float]:
    page = doc[0]  # type: ignore[index]
    boards = detect_vector_boards(page)
    assert len(boards) == 1, f"esperado exatamente 1 tabuleiro, veio {len(boards)}"
    return boards[0].piece_placement, boards[0].confidence


def test_catalog_merida_matches_the_source_project() -> None:
    """The catalog is the exact inverse of the renderer's write-side table.

    The round-trip below would still pass if both sides were wrong in the same
    way, so the mapping itself is pinned against the production table it came
    from.
    """
    family = family_by_key("merida")
    assert family is not None
    for fen_letter, char in MERIDA_LIGHT.items():
        role = family.role(char)
        assert role is not None, f"Merida: caractere {char!r} ausente do catálogo"
        assert role.square == "light"
        if fen_letter == ".":
            assert role.kind == "empty"
        else:
            assert role.kind == "piece" and role.piece == fen_letter
    for fen_letter, char in MERIDA_DARK.items():
        role = family.role(char)
        assert role is not None, f"Merida: caractere {char!r} ausente do catálogo"
        assert role.square == "dark"
        if fen_letter == ".":
            assert role.kind == "empty"
        else:
            assert role.kind == "piece" and role.piece == fen_letter


def test_roundtrip_merida_many_positions(merida_font: Path, random_positions: list[str]) -> None:
    assert len(random_positions) >= 200
    failures: list[tuple[str, str | None]] = []
    for placement in random_positions:
        doc = build_diagram_pdf(merida_font, merida_rows(placement))
        try:
            got, confidence = _read_one(doc)
        finally:
            doc.close()  # type: ignore[attr-defined]
        if got != placement:
            failures.append((placement, got))
        elif confidence < 1.0:
            failures.append((placement, f"confiança {confidence}"))
    assert not failures, f"{len(failures)}/{len(random_positions)} falharam: {failures[:5]}"


@pytest.mark.parametrize("size", [8.0, 11.5, 22.0, 48.0, 96.0])
def test_roundtrip_survives_any_size(merida_font: Path, size: float) -> None:
    placement = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1B3/PPP2PPP/R2Q1RK1"
    page_side = 8 * size + 120.0
    doc = build_diagram_pdf(
        merida_font,
        merida_rows(placement),
        size=size,
        origin=(40.0, 40.0 + size),
        page_size=(page_side, page_side),
    )
    try:
        got, _ = _read_one(doc)
    finally:
        doc.close()  # type: ignore[attr-defined]
    assert got == placement


def test_two_boards_on_one_page(merida_font: Path) -> None:
    """Books print two diagrams side by side; both must come out."""
    first = "8/8/8/4k3/8/8/4K3/8"
    second = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    import pymupdf  # local import: the fixture already skipped if missing

    doc = pymupdf.open()
    page = doc.new_page(width=520.0, height=400.0)
    page.insert_font(fontname="CHESS", fontfile=str(merida_font))
    for x_offset, placement in ((40.0, first), (280.0, second)):
        for i, row in enumerate(merida_rows(placement)):
            page.insert_text(
                pymupdf.Point(x_offset, 80.0 + i * 22.0),
                row, fontsize=22.0, fontname="CHESS",
            )
    blob = doc.tobytes()
    doc.close()
    reopened = pymupdf.open("pdf", blob)
    try:
        boards = detect_vector_boards(reopened[0])
        found = {b.piece_placement for b in boards}
        assert found == {first, second}, found
        assert all(b.confidence == 1.0 for b in boards)
    finally:
        reopened.close()


def test_two_boards_side_by_side_at_different_heights(merida_font: Path) -> None:
    """Side-by-side boards whose tops are offset must both come out.

    Found by the F2 importer on Dvoretsky 2025 p. 203: the left board starts
    36 pt lower than the right one, so grouping glyph rows page-wide
    interleaves the two boards' rows and no window of eight consecutive rows
    is a board -- 0 of 2 detected, and the coordinate labels of both leaked
    into the prose as sixteen one-character paragraphs.
    """
    first = "8/8/8/4k3/8/8/4K3/8"
    second = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=520.0, height=460.0)
    page.insert_font(fontname="CHESS", fontfile=str(merida_font))
    for x_offset, y_offset, placement in ((40.0, 116.0, first), (280.0, 80.0, second)):
        for i, row in enumerate(merida_rows(placement)):
            page.insert_text(
                pymupdf.Point(x_offset, y_offset + i * 22.0),
                row, fontsize=22.0, fontname="CHESS",
            )
    blob = doc.tobytes()
    doc.close()
    reopened = pymupdf.open("pdf", blob)
    try:
        boards = detect_vector_boards(reopened[0])
        found = {b.piece_placement for b in boards}
        assert found == {first, second}, found
    finally:
        reopened.close()


def test_skaknew_diagram_is_a_diagram_family_with_the_skak_encoding() -> None:
    """``SkakNew-Diagram`` (the Polgar) must not fall under the figurine rule.

    Before the ``skak_diagram`` entry the name matched the inline
    ``skaknew`` family and the Polgar's 5.334 diagrams were invisible to the
    vector route -- and its pages were rejected by level 0 for being "8 %
    dictionary words", because the board glyphs were judged as prose.
    """
    from caissa.vision.detect.font_catalog import lookup_family

    family = lookup_family("ABCDEF+SkakNew-Diagram")
    assert family is not None and family.key == "skak_diagram"
    assert family.kind == "diagram" and family.readable
    # Light squares: case is the colour.  Dark squares: shifted letters.
    assert family.role("Q").piece == "Q" and family.role("Q").square == "light"
    assert family.role("k").piece == "k" and family.role("k").square == "light"
    assert family.role("J").piece == "K" and family.role("J").square == "dark"
    assert family.role("o").piece == "p" and family.role("o").square == "dark"
    assert family.role("0").kind == "empty" and family.role("Z").square == "dark"
    inline = lookup_family("SkakNew-Figurine")
    assert inline is not None and inline.kind == "figurine"


@pytest.mark.parametrize(("rotation", "cropbox"), [(90, (30, 20, 400, 540)), (270, (30, 20, 400, 540)), (180, (30, 20, 400, 540))])
def test_rect_pdf_lands_on_the_ink_of_a_rotated_cropped_page(merida_font: Path, rotation: int, cropbox) -> None:
    """``rect_pdf`` must contain the painted pieces on a rotated page with a displaced CropBox.

    The Editor's section-48 formula added the CropBox origin and put the board
    40 pt from its ink here (found by the F2 geometry proof, 2026-09-11).
    """
    import numpy as np

    doc = build_diagram_pdf(merida_font, merida_rows("8/8/8/4k3/8/8/4K3/8"), rotation=rotation, cropbox=cropbox)
    try:
        page = doc[0]
        boards = detect_vector_boards(page)
        assert len(boards) == 1
        # The hatched dark squares are the board's full ink; the lattice rect
        # (glyph origins and advances) sits within 15 pt of it, the origin
        # formula's error was 40 pt.
        pix = page.get_pixmap(dpi=144)
        array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        ys, xs = np.where(array[:, :, 0] < 250)
        ink = (xs.min() / 2.0, ys.min() / 2.0, xs.max() / 2.0, ys.max() / 2.0)
        for edge, painted in zip(boards[0].rect_pdf, ink, strict=True):
            assert abs(edge - painted) <= 15, (boards[0].rect_pdf, ink)
    finally:
        doc.close()


# --------------------------------------------------------------------------
# Other layouts.  These use the catalog's own inverse to render, so they test
# the machinery -- lattice, checkerboard, overprint merge -- under encodings
# that differ structurally from Merida's, not the mapping itself.
# --------------------------------------------------------------------------

_OTHER_FONTS: dict[str, tuple[str, ...]] = {
    "cases": ("Chess Cases.ttf",),
    "alpha": ("ChessAlpha.ttf", "Chess Alpha.ttf"),
    "utrecht": ("Chess Utrecht.ttf",),
    "openchess": ("OpenChessFont.otf",),
}


@pytest.mark.parametrize("family_key", sorted(_OTHER_FONTS))
def test_roundtrip_other_layouts(family_key: str) -> None:
    font = find_font(*_OTHER_FONTS[family_key])
    if font is None:
        pytest.skip(f"fonte da família {family_key} não instalada nesta máquina")
    family = family_by_key(family_key)
    assert family is not None
    placements = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R",
    ]
    for placement in placements:
        rows = family_rows(family, placement)
        assert rows, f"a família {family_key} não expressa a posição"
        doc = build_diagram_pdf(font, [pieces for _back, pieces in rows])
        try:
            got, _ = _read_one(doc)
        finally:
            doc.close()  # type: ignore[attr-defined]
        assert got == placement, f"{family_key}: {got} != {placement}"


def test_roundtrip_chessbase_overprint() -> None:
    """The zero-advance background must not eat a cell of the lattice."""
    font = find_font("DiaTTFri.ttf", "DiagramTTF.ttf")
    if font is None:
        pytest.skip("fonte ChessBase DiagramTTF não instalada nesta máquina")
    family = family_by_key("chessbase_diagram")
    assert family is not None
    placement = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1B3/PPP2PPP/R2Q1RK1"
    rows = family_rows(family, placement)
    assert rows
    assert any(any(backs) for backs, _ in rows), "esperado glifo de fundo nas casas escuras"
    doc = build_overprint_pdf(font, rows)
    try:
        got, _ = _read_one(doc)
    finally:
        doc.close()  # type: ignore[attr-defined]
    assert got == placement
