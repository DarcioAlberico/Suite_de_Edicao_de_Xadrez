"""What must *not* be read as a board.

A false diagram is worse than a missed one: it puts a wrong position into the
document with the detector's own confidence behind it.  These tests pin the
three guards -- family kind, lattice geometry, and the checkerboard -- against
the cases that actually occur in books.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.vision.detect import detect_vector_boards, lookup_family

from .conftest import build_diagram_pdf, find_font, merida_rows

pymupdf = pytest.importorskip("pymupdf")


def test_figurine_notation_in_a_paragraph_is_not_a_board(merida_font: Path) -> None:
    """Eight lines of moves set in a chess font must stay text.

    This is the realistic false positive: a chess font on the page, eight lines
    of it, glyphs that the catalog maps to pieces.  Only the checkerboard tells
    it apart from a diagram.
    """
    paragraph = [
        "1.knbqk 2.rnbqkp 3.bqknrp",
        "4.qkbnrp 5.nrbqkp 6.pkqbnr",
        "7.rqnbkp 8.kbnqrp 9.qnrbkp",
        "10.bnkqrp 11.rpkqnb 12.nqbkrp",
        "13.pqrnbk 14.kqnbrp 15.bkrnqp",
        "16.nbkqrp 17.qrbknp 18.kpnbqr",
        "19.rnqkbp 20.bqnkrp 21.pnkbqr",
        "22.qbknrp 23.nkrbqp 24.krbnqp",
    ]
    doc = build_diagram_pdf(merida_font, paragraph, size=11.0)
    try:
        boards = detect_vector_boards(doc[0])
    finally:
        doc.close()
    assert boards == [], f"notação em fonte de xadrez virou tabuleiro: {boards}"


def test_eight_by_eight_of_pieces_without_a_checkerboard_is_rejected(
    merida_font: Path,
) -> None:
    """Right geometry, wrong colours: still not a board.

    Eight rows of eight glyphs on a perfect square pitch -- but every glyph is
    a light-square one, so the squares do not alternate.  Geometry alone would
    accept this; the checkerboard is what refuses it.
    """
    rows = ["pnbrqkpn"] * 8
    doc = build_diagram_pdf(merida_font, rows, size=20.0)
    try:
        boards = detect_vector_boards(doc[0])
    finally:
        doc.close()
    assert boards == []


def test_seven_rows_is_not_a_board(merida_font: Path) -> None:
    placement = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    doc = build_diagram_pdf(merida_font, merida_rows(placement)[:7], size=20.0)
    try:
        assert detect_vector_boards(doc[0]) == []
    finally:
        doc.close()


def test_non_square_cells_are_rejected(merida_font: Path) -> None:
    """Rows spaced at twice the glyph width are a table, not a board."""
    placement = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    doc = pymupdf.open()
    page = doc.new_page(width=400.0, height=700.0)
    page.insert_font(fontname="CHESS", fontfile=str(merida_font))
    for i, row in enumerate(merida_rows(placement)):
        page.insert_text(
            pymupdf.Point(60.0, 80.0 + i * 48.0), row, fontsize=20.0, fontname="CHESS"
        )
    blob = doc.tobytes()
    doc.close()
    reopened = pymupdf.open("pdf", blob)
    try:
        assert detect_vector_boards(reopened[0]) == []
    finally:
        reopened.close()


def test_inline_figurine_fonts_are_never_read() -> None:
    """A figurine family is catalogued precisely so it can be refused."""
    for name in ("SemFig", "ABCDEF+SemFigBold", "FigurineCB TimeSP Roman", "SkakNew-Figurine"):
        family = lookup_family(name)
        assert family is not None, name
        assert family.kind == "figurine", name
        assert not family.readable, name


def test_figurine_font_on_the_page_produces_nothing() -> None:
    """Even a perfect 8x8 grid in a figurine font must be ignored."""
    font = find_font("SEMFIGN_NORMAL.TTF", "verfig.ttf")
    if font is None:
        pytest.skip("nenhuma fonte de figurino instalada nesta máquina")
    doc = build_diagram_pdf(font, ["KQRBNPKQ"] * 8, size=20.0)
    try:
        assert detect_vector_boards(doc[0]) == []
    finally:
        doc.close()


def test_plain_text_page_produces_nothing() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        pymupdf.Point(72, 100),
        "Diagrama 12 - brancas jogam e ganham. 1.Qc2 Rb8 2.Bxh7+ Kxh7 3.Ng5+",
        fontsize=11,
    )
    blob = doc.tobytes()
    doc.close()
    reopened = pymupdf.open("pdf", blob)
    try:
        assert detect_vector_boards(reopened[0]) == []
    finally:
        reopened.close()


def test_unverified_families_need_an_explicit_opt_in() -> None:
    """A family whose layout was never checked must not read silently."""
    from caissa.vision.detect.font_catalog import FAMILIES

    unverified = [f for f in FAMILIES if f.kind == "diagram" and f.confidence == "unverified"]
    assert unverified, "o catálogo deveria admitir famílias não verificadas"
    for family in unverified:
        assert not family.readable, family.key
        assert family.source, f"{family.key} não diz por que não foi verificada"
