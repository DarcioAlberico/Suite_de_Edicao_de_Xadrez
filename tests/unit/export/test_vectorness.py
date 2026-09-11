"""A diagram is geometry, never pixels.

SPEC section 8.1 says "diagramas **vetoriais** (nunca raster)" and section 8.3
says inline SVG. This is the test that makes those words a gate rather than an
aspiration, because a rasterised board is a quality loss nobody notices in a
diff: the file still opens, the diagram is still there, and it is soft on every
screen made after 2012.

Each format is checked against the thing that would actually be there if it had
gone wrong -- a ``<img>`` or a data URI in the markup, an image XObject in the
PDF, a ``\\includegraphics`` in the LaTeX, a PNG part in the DOCX package.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from caissa.core.model import (
    Diagram,
    Document,
    DocumentMetadata,
    Orientation,
    Paragraph,
    Text,
)
from caissa.export import export
from caissa.export.base import ExportOptions

STARTING = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MIDDLEGAME = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


@pytest.fixture
def with_diagrams() -> Document:
    """A document that is mostly diagrams, so the check has something to find."""
    return Document(
        metadata=DocumentMetadata(title="Diagramas", language="pt-BR"),
        body=(
            Paragraph(content=(Text(content="Posicao inicial:"),)),
            Diagram(fen=STARTING, number=1),
            Paragraph(content=(Text(content="Depois de 3...Nf6:"),)),
            Diagram(fen=MIDDLEGAME, number=2, orientation=Orientation.BLACK),
        ),
    )


def test_html_draws_the_board_as_inline_svg(
    tmp_path: Path, with_diagrams: Document
) -> None:
    """The page carries real ``<path>`` and ``<rect>``, not an ``<img>``."""
    target = tmp_path / "livro.html"
    export(with_diagrams, target, "html")
    page = target.read_text(encoding="utf-8")

    assert "<svg" in page, "nenhum SVG na pagina"
    assert re.search(r"<(rect|path|circle)\b", page), "o SVG nao tem geometria"
    assert "data:image" not in page, "um diagrama virou imagem embutida"
    assert not re.search(r'<img[^>]*data-ir="diagram"', page)


def test_epub_draws_the_board_as_inline_svg(
    tmp_path: Path, with_diagrams: Document
) -> None:
    """The package has no raster part at all."""
    target = tmp_path / "livro.epub"
    export(with_diagrams, target, "epub")
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        pages = "\n".join(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".xhtml")
        )
    assert not [name for name in names if name.endswith((".png", ".jpg", ".jpeg"))]
    assert "<svg" in pages
    assert re.search(r"<(rect|path|circle)\b", pages)


def test_pdf_paints_the_board_with_path_operators(
    tmp_path: Path, with_diagrams: Document
) -> None:
    """The PDF has no image XObject, and it does have filled paths.

    ``/Subtype /Image`` is the only way a bitmap can be in a PDF page. Its
    absence, together with the presence of ``re``/``m``/``c`` operators, is
    what "vector" means at the byte level.
    """
    target = tmp_path / "livro.pdf"
    result = export(with_diagrams, target, "pdf")
    raw = target.read_bytes()

    assert b"/Subtype /Image" not in raw and b"/Subtype/Image" not in raw
    assert result.stats.get("vector_shapes", 0) > 50, (
        f"apenas {result.stats.get('vector_shapes', 0)} formas vetoriais; "
        "um tabuleiro tem 64 casas"
    )


def test_latex_writes_the_position_and_not_a_picture(
    tmp_path: Path, with_diagrams: Document
) -> None:
    """A LaTeX diagram is ``\\chessboard[setfen=...]``: editable text.

    SPEC section 8.5 is explicit that the position must stay editable in the
    source. ``\\includegraphics`` would mean the author cannot fix a wrong
    square without going back to the original.
    """
    target = tmp_path / "livro.tex"
    export(with_diagrams, target, "latex")
    source = target.read_text(encoding="utf-8")

    assert "\\chessboard[" in source
    assert "setfen={" in source
    assert STARTING in source, "a posicao nao esta legivel no fonte"
    assert "\\includegraphics" not in source.split("%%CAISSA-IR")[0]


def test_docx_embeds_the_board_as_a_metafile(
    tmp_path: Path, with_diagrams: Document
) -> None:
    """Word gets EMF, and the export says which diagrams got what.

    SPEC section 8.2 asks for EMF with a PNG fallback. A fallback that silently
    replaced the vector is the failure this front exists to prevent, so the
    statistics count the two paths separately and this test reads them.
    """
    target = tmp_path / "livro.docx"
    result = export(with_diagrams, target, "docx")
    with zipfile.ZipFile(target) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]

    assert media, "nenhum diagrama foi embutido"
    emf = [name for name in media if name.endswith(".emf")]
    png = [name for name in media if name.endswith(".png")]
    assert result.stats.get("diagrams_emf", 0) == len(emf)
    assert result.stats.get("diagrams_png", 0) == len(png)
    assert emf, "nenhum diagrama saiu como EMF vetorial"
    assert not png, (
        "um diagrama caiu para PNG; procure o aviso de rasterizacao no relatorio: "
        + result.degradation.summary()
    )


def test_asking_for_raster_says_so_out_loud(
    tmp_path: Path, with_diagrams: Document
) -> None:
    """Turning vector off produces PNG *and* a rasterisation warning each time.

    The option exists for a user whose Word cannot render EMF. Taking it must
    never be quiet: the report names every diagram that became pixels.
    """
    target = tmp_path / "raster.docx"
    result = export(
        with_diagrams,
        target,
        "docx",
        options=ExportOptions(vector_diagrams=False, diagram_dpi=300),
    )
    with zipfile.ZipFile(target) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]

    assert all(name.endswith(".png") for name in media)
    rasterised = [
        warning
        for warning in result.degradation.warnings
        if warning.kind.value == "rasterised"
    ]
    assert len(rasterised) >= len(media), "um diagrama virou pixels sem aviso"
    assert result.stats.get("diagrams_emf", 0) == 0
