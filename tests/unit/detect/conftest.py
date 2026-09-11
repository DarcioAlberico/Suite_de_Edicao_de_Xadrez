"""Shared fixtures: synthesise PDFs that contain real chess diagrams.

The round-trip these tests perform is the strongest self-check available for
this front: render a known FEN into a PDF with a real chess font, hand the page
to the detector, and demand the same FEN back.  Nothing is mocked -- the PDF is
a real PDF, the font is a real font, and PyMuPDF does the extraction.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Iterator, Mapping, Sequence

import pytest

pymupdf = pytest.importorskip("pymupdf")

from caissa.vision.detect.font_catalog import (  # noqa: E402
    ChessFontFamily,
    GlyphRole,
    family_by_key,
)

# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

#: Where to look for a chess font, most specific first.
_FONT_ROOTS: tuple[Path, ...] = (
    Path(os.environ.get("CAISSA_CHESS_FONT_DIR", "")) if os.environ.get("CAISSA_CHESS_FONT_DIR") else Path(),
    Path(__file__).resolve().parents[3] / "assets" / "fonts",
    Path(r"C:\Python-Chess2\Editor_Diagramas_de_Xadrez"),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts")),
    Path(r"C:\Windows\Fonts"),
)


def find_font(*names: str) -> Path | None:
    """First readable font file among ``names``, searching the known roots."""
    for root in _FONT_ROOTS:
        if not root or not root.is_dir():
            continue
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


@pytest.fixture(scope="session")
def merida_font() -> Path:
    path = find_font("chessmerida.otf", "ChessMerida.ttf", "Chess Merida.ttf", "Merida.otf")
    if path is None:
        pytest.skip("fonte Chess Merida não encontrada nesta máquina")
    return path


# --------------------------------------------------------------------------
# Board -> rows of characters
# --------------------------------------------------------------------------

#: The Merida table copied verbatim from the *write* side of the source
#: project, Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/renderer.py.  It is
#: reproduced here on purpose: the round-trip must not be circular, so the test
#: renders with a table the detector never sees.
MERIDA_LIGHT: Mapping[str, str] = {
    "P": "p", "N": "n", "B": "b", "R": "r", "Q": "q", "K": "k",
    "p": "o", "n": "m", "b": "v", "r": "t", "q": "w", "k": "l",
    ".": " ",
}
MERIDA_DARK: Mapping[str, str] = {
    "P": "P", "N": "N", "B": "B", "R": "R", "Q": "Q", "K": "K",
    "p": "O", "n": "M", "b": "V", "r": "T", "q": "W", "k": "L",
    ".": "+",
}


def matrix_from_placement(placement: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in placement.split("/"):
        cells: list[str] = []
        for ch in row:
            if ch.isdigit():
                cells.extend("." * int(ch))
            else:
                cells.append(ch)
        rows.append(cells)
    return rows


def merida_rows(placement: str) -> list[str]:
    """The eight text rows a Merida diagram is made of."""
    matrix = matrix_from_placement(placement)
    out: list[str] = []
    for rank in range(8):
        chars = [
            (MERIDA_DARK if (rank + file_) % 2 else MERIDA_LIGHT)[matrix[rank][file_]]
            for file_ in range(8)
        ]
        out.append("".join(chars))
    return out


def _inverse_table(family: ChessFontFamily) -> dict[tuple[str | None, str], str]:
    """``(piece letter or None, square colour) -> character`` for a family."""
    table: dict[tuple[str | None, str], str] = {}
    for char, role in family.glyphs.items():
        if role.zero_advance or role.square is None:
            continue
        if role.kind == "piece":
            table.setdefault((role.piece, role.square), char)
        elif role.kind == "empty":
            table.setdefault((None, role.square), char)
    return table


def _background_table(family: ChessFontFamily) -> str:
    for char, role in family.glyphs.items():
        if role.zero_advance and role.square == "dark":
            return char
    return ""


def family_rows(family: ChessFontFamily, placement: str) -> list[tuple[list[str], str]]:
    """Rows for any catalogued family, as ``(backgrounds, piece run)`` pairs.

    ``backgrounds`` always has eight entries, one per column, holding the
    zero-advance background character for that cell or ``""``.  Families that
    compose a dark square from a background glyph plus the piece glyph
    (ChessBase) fill it in; everyone else leaves it empty.  Returns ``[]`` when
    the family cannot express the position.
    """
    table = _inverse_table(family)
    background = _background_table(family)
    matrix = matrix_from_placement(placement)
    rows: list[tuple[list[str], str]] = []
    for rank in range(8):
        pieces: list[str] = []
        backs: list[str] = []
        for file_ in range(8):
            cell = matrix[rank][file_]
            square = "dark" if (rank + file_) % 2 else "light"
            piece = None if cell == "." else cell
            char = table.get((piece, square))
            back = ""
            if char is None and square == "dark" and background:
                # ChessBase style: the dark square is a zero-advance background
                # glyph with the light-square piece glyph printed over it.
                char = table.get((piece, "light"))
                if char is not None:
                    back = background
            if char is None:
                return []
            backs.append(back)
            pieces.append(char)
        rows.append((backs, "".join(pieces)))
    return rows


# --------------------------------------------------------------------------
# PDF synthesis
# --------------------------------------------------------------------------


def build_diagram_pdf(
    font_path: Path,
    rows: Sequence[str],
    *,
    size: float = 22.0,
    origin: tuple[float, float] = (72.0, 120.0),
    page_size: tuple[float, float] = (420.0, 560.0),
    rotation: int = 0,
    cropbox: tuple[float, float, float, float] | None = None,
    extra_text: Sequence[tuple[str, float, float, float, str | None]] = (),
    coordinates: bool = False,
) -> object:
    """A one-page PDF whose only content is the diagram (plus what you add).

    ``extra_text`` items are ``(text, x, y, size, font file or None)``; passing
    ``None`` for the font uses Helvetica, which is what a real book uses for
    its caption.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=page_size[0], height=page_size[1])
    page.insert_font(fontname="CHESS", fontfile=str(font_path))
    x, y = origin
    for i, row in enumerate(rows):
        page.insert_text(
            pymupdf.Point(x, y + i * size), row, fontsize=size, fontname="CHESS"
        )
    if coordinates:
        for i, letter in enumerate("abcdefgh"):
            page.insert_text(
                pymupdf.Point(x + i * size + size * 0.35, y + 8 * size + size * 0.55),
                letter, fontsize=size * 0.45, fontname="helv",
            )
        for i, digit in enumerate("87654321"):
            page.insert_text(
                pymupdf.Point(x - size * 0.55, y + i * size - size * 0.25),
                digit, fontsize=size * 0.45, fontname="helv",
            )
    for text, tx, ty, tsize, font_file in extra_text:
        if font_file is None:
            page.insert_text(pymupdf.Point(tx, ty), text, fontsize=tsize, fontname="helv")
        else:
            page.insert_font(fontname="EXTRA", fontfile=font_file)
            page.insert_text(
                pymupdf.Point(tx, ty), text, fontsize=tsize, fontname="EXTRA"
            )
    blob = doc.tobytes()
    doc.close()

    out = pymupdf.open("pdf", blob)
    target = out[0]
    if cropbox is not None:
        target.set_cropbox(pymupdf.Rect(*cropbox))
    if rotation:
        target.set_rotation(rotation)
    return out


def build_overprint_pdf(
    font_path: Path,
    rows: Sequence[tuple[list[str], str]],
    *,
    size: float = 22.0,
    origin: tuple[float, float] = (72.0, 120.0),
) -> object:
    """Like :func:`build_diagram_pdf`, but also writes the zero-advance backgrounds.

    Each row becomes one text run in which every dark cell is a background
    glyph immediately followed by its piece glyph.  Because the background has
    zero advance the piece lands on top of it and the run still steps one cell
    per piece -- which is exactly how a ChessBase diagram font composes a dark
    square, and what the overprint merge in the detector has to survive.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=420.0, height=560.0)
    page.insert_font(fontname="CHESS", fontfile=str(font_path))
    x, y = origin
    for i, (backs, pieces) in enumerate(rows):
        run = "".join(back + piece for back, piece in zip(backs, pieces))
        page.insert_text(
            pymupdf.Point(x, y + i * size), run, fontsize=size, fontname="CHESS"
        )
    blob = doc.tobytes()
    doc.close()
    return pymupdf.open("pdf", blob)


# --------------------------------------------------------------------------
# Random legal positions
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def random_positions() -> list[str]:
    """At least 200 legal positions, reached by playing random legal moves."""
    chess = pytest.importorskip("chess")
    rng = random.Random(20260907)
    seen: list[str] = []
    while len(seen) < 220:
        board = chess.Board()
        plies = rng.randint(0, 80)
        for _ in range(plies):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        seen.append(board.board_fen())
    return seen


@pytest.fixture()
def catalogued_families() -> Iterator[ChessFontFamily]:
    for key in ("merida", "cases", "alpha", "utrecht", "openchess", "chessbase_diagram"):
        family = family_by_key(key)
        if family is not None:
            yield family


def role_of(family: ChessFontFamily, char: str) -> GlyphRole | None:
    return family.role(char)
