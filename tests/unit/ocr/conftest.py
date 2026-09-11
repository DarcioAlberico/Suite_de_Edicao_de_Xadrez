"""Shared fixtures and synthetic-page generators for the OCR tests.

Every degradation used in these tests is *generated here*, which is the whole
point: the ground truth is known exactly, so a test can assert that deskew
recovered 2.30 degrees rather than merely that it returned an image.  Nothing
in this file reads a sample from disk, so the suite has no corpus to ship and
no fixture to go stale.
"""

from __future__ import annotations

import math
import os
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

# The project has no installed distribution yet (pyproject.toml belongs to
# another front), so put ``src`` on the path when ``caissa.ocr`` is not already
# importable.  Harmless once the package is installed properly.
_SRC = Path(__file__).resolve().parents[3] / "src"
if str(_SRC) not in sys.path:
    try:
        import caissa.ocr  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(_SRC))


# --------------------------------------------------------------------------- #
# Optional dependencies
# --------------------------------------------------------------------------- #


def _font_path() -> str | None:
    """A real serif TrueType font, needed to render realistic test pages."""
    candidates = [
        r"C:\Windows\Fonts\times.ttf",
        r"C:\Windows\Fonts\georgia.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


FONT_PATH = _font_path()

try:
    import pymupdf as _pymupdf
except ImportError:  # pragma: no cover - environment dependent
    try:
        import fitz as _pymupdf  # type: ignore[no-redef]
    except ImportError:
        _pymupdf = None

HAVE_PYMUPDF = _pymupdf is not None

requires_font = pytest.mark.skipif(
    FONT_PATH is None,
    reason="nenhuma fonte TrueType encontrada para renderizar páginas de teste",
)
requires_pymupdf = pytest.mark.skipif(
    not HAVE_PYMUPDF,
    reason="PyMuPDF não está instalado (pip install pymupdf)",
)


def tesseract_binary() -> str | None:
    from caissa.ocr.engines.tesseract import find_tesseract
    return find_tesseract()


HAVE_TESSERACT = tesseract_binary() is not None

requires_tesseract = pytest.mark.skipif(
    not HAVE_TESSERACT,
    reason=(
        "Tesseract não está instalado nesta máquina. Instale-o "
        "(https://github.com/UB-Mannheim/tesseract/wiki) ou aponte a variável "
        "CAISSA_TESSERACT para o executável para habilitar os testes de "
        "ponta a ponta."
    ),
)


@pytest.fixture(scope="session")
def pymupdf():
    if _pymupdf is None:
        pytest.skip("PyMuPDF não está instalado")
    return _pymupdf


# --------------------------------------------------------------------------- #
# Sample text
# --------------------------------------------------------------------------- #

ENGLISH_BODY = (
    "The rook belongs behind the passed pawn. This is one of the most useful "
    "rules in the endgame, and it is not hard to see why it should be so. "
    "When the rook stands in front of the pawn it must move away before the "
    "pawn can advance, and every such move is a move the defender does not "
    "have to make. The attacking side therefore loses time with each step, "
    "while the defender simply waits. "
)

PORTUGUESE_BODY = (
    "A torre pertence atras do peao passado. Esta e uma das regras mais uteis "
    "do final, e nao e dificil entender por que deve ser assim. Quando a torre "
    "esta na frente do peao, ela precisa sair antes que o peao avance, e cada "
    "lance desses e um lance que o defensor nao precisa fazer. "
)


# --------------------------------------------------------------------------- #
# Synthetic page rendering
# --------------------------------------------------------------------------- #


def render_text_page(text: str = ENGLISH_BODY, *, width: int = 1700,
                     height: int = 1150, font_size: int = 30,
                     margin: int = 70, wrap: int = 62,
                     repeat: int = 8) -> tuple[np.ndarray, str]:
    """Render prose onto a white page.  Returns ``(image, exact_text)``.

    The returned string is what was actually drawn, line by line, so a CER can
    be computed against it without guessing where the renderer wrapped.
    """
    from PIL import Image, ImageDraw, ImageFont

    if FONT_PATH is None:
        pytest.skip("nenhuma fonte TrueType disponível")

    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, font_size)

    body = text * repeat
    lines: list[str] = []
    y = margin
    step = int(font_size * 1.55)
    for line in textwrap.wrap(body, wrap):
        if y + step > height - margin:
            break
        draw.text((margin, y), line, fill=0, font=font)
        lines.append(line)
        y += step
    return np.array(image), "\n".join(lines)


def rotate(image: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate counter-clockwise by ``degrees`` (OpenCV's sign convention).

    A page rotated counter-clockwise has text sloping *up* to the right, which
    is a skew of ``-degrees`` under this package's convention.
    """
    import cv2

    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), degrees, 1.0)
    return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def add_illumination(image: np.ndarray, *, strength: float = 0.62,
                     tilt: float = 0.22, floor: int = 8) -> np.ndarray:
    """Darken the page towards one side, as a flatbed lamp or a gutter does."""
    h, w = image.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    shade = 1.0 - strength * (xx / w) - tilt * (yy / h)
    return np.clip(image.astype(np.float32) * shade + floor, 0, 255).astype(np.uint8)


def add_specks(image: np.ndarray, *, count: int = 400,
               seed: int = 7) -> np.ndarray:
    """Sprinkle isolated black pixels — scanner dust."""
    rng = np.random.default_rng(seed)
    out = image.copy()
    ys = rng.integers(0, image.shape[0], size=count)
    xs = rng.integers(0, image.shape[1], size=count)
    out[ys, xs] = 0
    return out


def add_bleed_through(image: np.ndarray, *, level: int = 150,
                      seed: int = 11) -> np.ndarray:
    """Add faint mirrored strokes, as ink showing through thin paper does."""
    import cv2

    rng = np.random.default_rng(seed)
    verso = np.full_like(image, 255)
    h, w = image.shape
    for _ in range(40):
        x = int(rng.integers(40, max(41, w - 120)))
        y = int(rng.integers(40, max(41, h - 40)))
        length = int(rng.integers(30, 110))
        cv2.line(verso, (x, y), (x + length, y), 0, 3)
    mirrored = cv2.flip(verso, 1)
    faint = np.where(mirrored == 0, level, 255).astype(np.uint8)
    return np.minimum(image, faint)


def curl(image: np.ndarray, *, amplitude: float = 14.0) -> np.ndarray:
    """Bow the page vertically, as a photograph of an open book does."""
    import cv2

    h, w = image.shape
    columns = np.arange(w, dtype=np.float32)
    field = amplitude * (1.0 - np.cos(2.0 * math.pi * columns / w)) / 2.0
    field -= field.mean()
    map_x = np.tile(columns, (h, 1))
    map_y = (np.tile(np.arange(h, dtype=np.float32).reshape(-1, 1), (1, w))
             - field[None, :])
    return cv2.remap(image, map_x, map_y, cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=255)


# --------------------------------------------------------------------------- #
# Synthetic PDFs
# --------------------------------------------------------------------------- #

DEAD_CMAP_ENTRIES = 512


def dead_tounicode_stream(entries: int = DEAD_CMAP_ENTRIES) -> bytes:
    """A syntactically valid ToUnicode CMap that maps every code to U+0000.

    This is the failure this project has to survive: the CMap is present, so a
    naive "has ToUnicode?" check passes, and every character it produces is
    nothing.
    """
    body = "".join(f"<{code:04X}> <0000>\n" for code in range(1, entries))
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        f"{entries - 1} beginbfchar\n{body}endbfchar\nendcmap\n"
        "CMapName currentdict /CMap defineresource pop\nend\nend\n"
    ).encode("latin-1")


def build_pdf(text: str = ENGLISH_BODY, *, embed_font: bool = True,
              repeat: int = 4, wrap: int = 62):
    """A one-page PDF with a real text layer.

    ``embed_font`` chooses between a subset-embedded TrueType (a Type0 font
    with Identity-H encoding, exactly the shape that breaks) and a base-14
    font, which cannot break because it needs no ToUnicode at all.
    """
    if _pymupdf is None:
        pytest.skip("PyMuPDF não está instalado")
    if embed_font and FONT_PATH is None:
        pytest.skip("nenhuma fonte TrueType disponível para embutir")

    doc = _pymupdf.open()
    page = doc.new_page(width=595, height=842)
    if embed_font:
        page.insert_font(fontname="EMB", fontfile=FONT_PATH)
        fontname = "EMB"
    else:
        fontname = "helv"
    y = 70
    for line in textwrap.wrap(text * repeat, wrap):
        if y > 800:
            break
        page.insert_text((60, y), line, fontname=fontname, fontsize=12)
        y += 18
    reopened = _pymupdf.open(stream=doc.tobytes(), filetype="pdf")
    doc.close()
    return reopened


def break_tounicode(doc, *, mode: str = "delete"):
    """Damage the first embedded font's ToUnicode and return a reopened doc.

    ``mode`` is ``"delete"`` (remove the entry, as a subsetter that never wrote
    one) or ``"dead"`` (replace it with a CMap mapping everything to U+0000, as
    a subsetter that wrote a useless one).
    """
    fonts = doc[0].get_fonts(full=True)
    if not fonts:
        pytest.skip("o PDF de teste não tem fonte embutida")
    xref = fonts[0][0]
    if mode == "delete":
        doc.xref_set_key(xref, "ToUnicode", "null")
    elif mode == "dead":
        kind, value = doc.xref_get_key(xref, "ToUnicode")
        if kind != "xref":
            pytest.skip("a fonte de teste não tem stream ToUnicode")
        doc.update_stream(int(value.split()[0]), dead_tounicode_stream())
    else:  # pragma: no cover - programming error
        raise ValueError(f"modo desconhecido: {mode}")
    return _pymupdf.open(stream=doc.tobytes(), filetype="pdf")


def blank_pdf():
    """A page with no text layer at all — a scan."""
    if _pymupdf is None:
        pytest.skip("PyMuPDF não está instalado")
    doc = _pymupdf.open()
    doc.new_page(width=595, height=842)
    out = _pymupdf.open(stream=doc.tobytes(), filetype="pdf")
    doc.close()
    return out


# --------------------------------------------------------------------------- #
# Text corruption, for the quality tests
# --------------------------------------------------------------------------- #

#: The classic OCR confusion set, straight out of SPEC §7.3.
CONFUSABLES = "l1I50OB8SG6"


def corrupt_text(text: str, rate: float, seed: int = 0) -> str:
    """Damage ``text`` at a known per-character rate."""
    import random

    rng = random.Random(seed)
    out: list[str] = []
    for ch in text:
        if ch.isalnum() and rng.random() < rate:
            roll = rng.random()
            if roll < 0.70:
                out.append(rng.choice(CONFUSABLES))     # substitution
            elif roll < 0.85:
                pass                                     # deletion
            else:
                out.append(ch)
                out.append(rng.choice(CONFUSABLES))      # insertion
        else:
            out.append(ch)
    return "".join(out)


# --------------------------------------------------------------------------- #
# The local corpus (docs/quality/CORPUS.md)
# --------------------------------------------------------------------------- #

#: The corpus is copyrighted material that never leaves this machine, so every
#: test that touches it is skipped rather than failed when it is absent.  A
#: number measured outside this corpus does not count (CORPUS.md §5).
CORPUS_DIR = Path(os.environ.get(
    "CAISSA_CORPUS_PDF", r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF"))

#: name -> (file, stratum).  Only the files the OCR front actually needs.
CORPUS_FILES = {
    # E8 — already passed through third-party OCR.  The point of these two is
    # that a bad text layer must be *detected*, not trusted (CORPUS.md §2 E8).
    "gaprindashvili_ocr": (
        "Gaprindashvili, Paata - Imagination in Chess. How To Think Creatively"
        " And Avoid Foolish Mistakes (Bastford, 2005) 2p 145p_OCR_Aprimorar_"
        "Aprimorar.pdf", "E8"),
    "dobonov_ocr": (
        "La_Combinacion_En_El_Ajedrez_Constantin_Dobonov_83p,1974_OCR.pdf",
        "E8"),
    # E1 — born-digital, the control: these must be accepted.
    "dvoretsky": ("Dvoretsky - Dvoretsky's Endgame Manual (2025).pdf", "E1"),
    "aagaard": ("AAGAARD - Practical Chess Defence.pdf", "E1"),
    "flores_rios": ("Mauricio Flores Rios - Chess Structures - A Grandmaster "
                    "Guide[Quality Chess, 2015].pdf", "E1"),
    # E2 — clean scan with a real two-column layout and a running head.
    "nunn_pawnless": ("\U0001F4DANunn J. Secrets of Pawnless Endings.pdf", "E2"),
    # Books whose text layer reads its *notation* correctly.  These are the
    # controls the cipher decoder is held against (test_cipher.py), and they
    # are deliberately three scripts and three notation languages: a guard
    # that only ever sees English notation is not a guard.
    "boleslavsky": (
        "📚Болеслав"
        "ский_И_Избр"
        "анные_парт"
        "ии.pdf", "E6"),
    "quebra_cabecas": (
        "400 Quebra-cabeças de Estratégia de Xadrez.pdf", "E7"),
    "capablanca": (
        "Melhores Finais de Capablanca - Irving Chernev pt-br - Copia.pdf",
        "E7"),
}


def corpus_path(key: str) -> Path:
    """Absolute path of a corpus file, or skip the test."""
    try:
        name, _stratum = CORPUS_FILES[key]
    except KeyError:  # pragma: no cover - programming error
        raise KeyError(f"arquivo de corpus desconhecido: {key}") from None
    path = CORPUS_DIR / name
    if not path.is_file():
        pytest.skip(
            f"o arquivo de corpus '{key}' não está nesta máquina "
            f"({path}). O acervo é local e protegido por direito autoral; "
            f"aponte CAISSA_CORPUS_PDF para ele se estiver noutro lugar."
        )
    return path


HAVE_CORPUS = CORPUS_DIR.is_dir()

requires_corpus = pytest.mark.skipif(
    not HAVE_CORPUS,
    reason=f"o acervo local não está em {CORPUS_DIR} (docs/quality/CORPUS.md)",
)


@pytest.fixture
def corpus_doc(pymupdf):
    """Open a corpus PDF by key; closed automatically."""
    opened = []

    def _open(key: str):
        doc = pymupdf.open(corpus_path(key))
        opened.append(doc)
        return doc

    yield _open
    for doc in opened:
        doc.close()


def add_faint_bleed_through(image: np.ndarray, *, level: int = 214,
                            seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    """Bleed-through in the regime the heuristic path is built for.

    Returns ``(page, ghost_mask)``.  ``level`` sits *above* a page-wide Otsu
    threshold on purpose: the no-verso heuristic looks for pixels in a band
    above the ink threshold that no ink component reaches, so a ghost darker
    than the ink threshold is by construction invisible to it.  That is a real
    limitation of the heuristic and is asserted separately rather than hidden
    by choosing a convenient level.
    """
    import cv2

    rng = np.random.default_rng(seed)
    ghost = np.zeros(image.shape, dtype=bool)
    h, w = image.shape
    canvas = np.full_like(image, 255)
    for _ in range(40):
        x = int(rng.integers(40, max(41, w - 160)))
        y = int(rng.integers(40, max(41, h - 40)))
        length = int(rng.integers(40, 140))
        cv2.line(canvas, (x, y), (x + length, y), 0, 3)
    mirrored = cv2.flip(canvas, 1)
    faint = np.where(mirrored == 0, level, 255).astype(np.uint8)
    out = np.minimum(image, faint)
    ghost = (faint < 255) & (image > level)
    return out, ghost
