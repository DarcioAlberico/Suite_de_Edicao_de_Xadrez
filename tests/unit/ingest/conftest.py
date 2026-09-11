"""Fixtures for the F2 tests: synthetic PDFs whose ground truth is known exactly.

Nothing here reads a sample from disk.  Every page is generated with PyMuPDF
from a description of what should be on it -- which column, which size,
which face, hyphenated where -- so a test can assert *the* paragraph text
rather than "some text came out".  The reference collection is used only by
the tests marked ``golden``, which skip when it is absent.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"
if str(_SRC) not in sys.path:
    try:
        import caissa.ingest  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(_SRC))

try:
    import pymupdf as _pymupdf
except ImportError:  # pragma: no cover - environment dependent
    _pymupdf = None

HAVE_PYMUPDF = _pymupdf is not None
requires_pymupdf = pytest.mark.skipif(not HAVE_PYMUPDF, reason="PyMuPDF não instalado")

CORPUS_DIR = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF")


def find_font(*names: str) -> Path | None:
    """First font file matching one of ``names``, most specific root first.

    The same roots the F3-A tests search, so the two suites agree on which
    Chess Merida they render with.
    """
    roots = [
        Path(os.environ["CAISSA_CHESS_FONT_DIR"])
        if os.environ.get("CAISSA_CHESS_FONT_DIR")
        else None,
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path(r"C:\Python-Chess2\Editor_Diagramas_de_Xadrez"),
        Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    ]
    for root in roots:
        if root is None or not root.is_dir():
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
        pytest.skip("Chess Merida não está instalada; o diagrama vetorial precisa dela")
    return path


@pytest.fixture(scope="session")
def corpus_dir() -> Path:
    if not CORPUS_DIR.is_dir():
        pytest.skip("acervo de referência ausente (CORPUS.md §0)")
    return CORPUS_DIR


def corpus_file(name_fragment: str) -> Path:
    """A corpus book by a unique fragment of its file name, or skip."""
    if not CORPUS_DIR.is_dir():
        pytest.skip("acervo de referência ausente (CORPUS.md §0)")
    matches = [p for p in CORPUS_DIR.glob("*.pdf") if name_fragment.lower() in p.name.lower()]
    if not matches:
        pytest.skip(f"livro {name_fragment!r} ausente do acervo")
    return matches[0]


# --------------------------------------------------------------------------- #
# Page builder
# --------------------------------------------------------------------------- #

LETTER = (612.0, 792.0)


@dataclass(slots=True)
class TextItem:
    """One line of text to place: ``(x, baseline_y)`` in points."""

    text: str
    x: float
    y: float
    size: float = 11.0
    font: str = "helv"
    fontfile: str | None = None
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(slots=True)
class PageSpec:
    items: list[TextItem] = field(default_factory=list)
    size: tuple[float, float] = LETTER
    rotation: int = 0
    cropbox: tuple[float, float, float, float] | None = None
    #: ``(x0, y0, x1, y1)`` rectangles filled black -- rules and fake images.
    rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    #: ``(x0, y0, x1, y1, width_px, height_px)`` raster images to insert.
    images: list[tuple[float, float, float, float, int, int]] = field(default_factory=list)

    def text(self, text: str, x: float, y: float, **kwargs: object) -> PageSpec:
        self.items.append(TextItem(text, x, y, **kwargs))  # type: ignore[arg-type]
        return self


def lines_of(
    paragraph: str,
    *,
    x: float,
    y: float,
    width_chars: int,
    size: float = 11.0,
    leading: float | None = None,
    font: str = "helv",
    indent_first: float = 0.0,
    hyphenate: bool = False,
) -> list[TextItem]:
    """Break ``paragraph`` into lines the way a typesetter would: by measured width.

    ``width_chars`` names the measure in average characters (``0,5 em`` each,
    the Helvetica mean); the wrap itself is by the real advance widths of the
    glyphs, so a word goes on the line when it *fits in points*.  A wrap by
    character count would leave lines with room to spare in points, which
    the paragraph rules (rightly) read as a chosen break.

    With ``hyphenate`` a word that does not fit is split with a trailing
    hyphen, so the test knows exactly where the line-break hyphens are.
    """
    import pymupdf

    leading = leading or size * 1.2
    measure = width_chars * size * 0.5

    def width(text: str) -> float:
        return pymupdf.get_text_length(text, fontname=font, fontsize=size)

    words = paragraph.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if width(candidate) <= measure:
            current = candidate
            continue
        if hyphenate and len(word) > 6:
            placed = False
            for cut in range(len(word) - 3, 2, -1):
                head, tail = word[:cut], word[cut:]
                if width(f"{current} {head}-".strip()) <= measure:
                    lines.append(f"{current} {head}-".strip())
                    current = tail
                    placed = True
                    break
            if placed:
                continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    out: list[TextItem] = []
    for i, line in enumerate(lines):
        out.append(
            TextItem(line, x + (indent_first if i == 0 else 0.0), y + i * leading, size, font)
        )
    return out


def build_pdf(pages: Sequence[PageSpec], *, toc: Sequence[tuple[int, str, int]] = ()) -> bytes:
    """Render the page specs to PDF bytes."""
    import pymupdf

    doc = pymupdf.open()
    for spec in pages:
        page = doc.new_page(width=spec.size[0], height=spec.size[1])
        fonts: dict[str, str] = {}
        for item in spec.items:
            fontname = item.font
            if item.fontfile is not None:
                alias = fonts.get(item.fontfile)
                if alias is None:
                    alias = f"F{len(fonts)}"
                    page.insert_font(fontname=alias, fontfile=item.fontfile)
                    fonts[item.fontfile] = alias
                fontname = alias
            page.insert_text(
                pymupdf.Point(item.x, item.y),
                item.text,
                fontsize=item.size,
                fontname=fontname,
                color=item.color,
            )
        for rect in spec.rects:
            shape = page.new_shape()
            shape.draw_rect(pymupdf.Rect(*rect))
            shape.finish(fill=(0, 0, 0), color=None)
            shape.commit()
        for x0, y0, x1, y1, w, h in spec.images:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), 0)
            pix.clear_with(90)
            page.insert_image(pymupdf.Rect(x0, y0, x1, y1), pixmap=pix)
    if toc:
        doc.set_toc([[level, title, page + 1] for level, title, page in toc])
    blob = doc.tobytes()
    doc.close()
    if any(spec.rotation or spec.cropbox for spec in pages):
        reopened = pymupdf.open("pdf", blob)
        for index, spec in enumerate(pages):
            page = reopened[index]
            if spec.cropbox is not None:
                page.set_cropbox(pymupdf.Rect(*spec.cropbox))
            if spec.rotation:
                page.set_rotation(spec.rotation)
        blob = reopened.tobytes()
        reopened.close()
    return blob


@pytest.fixture
def pdf_file(tmp_path: Path) -> Callable[..., Path]:
    """Write a built PDF to ``tmp_path`` and return its path."""

    def _write(pages: Sequence[PageSpec], name: str = "livro.pdf", **kwargs: object) -> Path:
        target = tmp_path / name
        target.write_bytes(build_pdf(pages, **kwargs))  # type: ignore[arg-type]
        return target

    return _write


# --------------------------------------------------------------------------- #
# A small two-column book with known reading order
# --------------------------------------------------------------------------- #

LOREM = (
    "A posição exige precisão porque cada tempo conta e o rei precisa chegar ao canto "
    "antes que o peão avance mais uma casa na coluna torre."
)
LOREM_EN = (
    "The position demands precision because every tempo counts and the king must reach "
    "the corner before the pawn advances one more square on the rook file."
)

COLUMN_LEFT = 54.0
COLUMN_RIGHT = 324.0
COLUMN_CHARS = 42
BODY_SIZE = 10.0
LEADING = 12.0


def two_column_page(
    left_paragraphs: Sequence[str],
    right_paragraphs: Sequence[str],
    *,
    heading: str | None = None,
    footnote: str | None = None,
    running_head: str | None = None,
    folio: int | None = None,
    hyphenate: bool = False,
    top: float = 90.0,
) -> tuple[PageSpec, list[str]]:
    """Build a two-column page and return it with its expected reading order.

    The expected order is: heading, left column top to bottom, right column
    top to bottom, footnote.  Running head and folio are furniture and must
    not appear at all.
    """
    spec = PageSpec()
    expected: list[str] = []
    if running_head:
        spec.text(running_head, COLUMN_LEFT, 40.0, size=8.0)
    if folio is not None:
        spec.text(str(folio), 300.0, 770.0, size=9.0)
    y = top
    if heading:
        spec.text(heading, COLUMN_LEFT, y, size=16.0, font="hebo")
        expected.append(heading)
        y += 30.0
    for column_x, paragraphs in ((COLUMN_LEFT, left_paragraphs), (COLUMN_RIGHT, right_paragraphs)):
        cy = y
        for paragraph in paragraphs:
            items = lines_of(
                paragraph,
                x=column_x,
                y=cy,
                width_chars=COLUMN_CHARS,
                size=BODY_SIZE,
                leading=LEADING,
                indent_first=12.0,
                hyphenate=hyphenate,
            )
            spec.items.extend(items)
            cy += LEADING * len(items) + LEADING * 0.8
    expected.extend(left_paragraphs)
    expected.extend(right_paragraphs)
    if footnote:
        spec.rects.append((COLUMN_LEFT, 700.0, COLUMN_LEFT + 120.0, 700.6))
        # Two lines, wrapped like a typesetter would wrap them.
        note = f"{footnote} Esta nota continua numa segunda linha para ser um bloco de rodapé."
        spec.items.extend(lines_of(note, x=COLUMN_LEFT, y=714.0, width_chars=64, size=8.0))
        expected.append(note)
    return spec, expected


def paragraphs_of(document: object) -> list[str]:
    """Reading text of every paragraph-like block of an IR document, in order."""
    from caissa.core.model import Heading, Paragraph, plain_text

    return [
        " ".join(plain_text(block.content).split())
        for block in document.body  # type: ignore[attr-defined]
        if isinstance(block, (Paragraph, Heading))
    ]
