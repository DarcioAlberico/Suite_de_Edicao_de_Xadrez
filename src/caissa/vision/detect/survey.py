"""Which books in the shelf the vector path can read -- and the evidence for saying so.

``chess_diagram_ocr/detection/__init__.py`` records a survey of 27 books in which **2 are
"diagrama vetorial/fonte", with no embedded image**, and says plainly that no current path
reads them.  It never says *which two*.  This module answers that, over the whole shelf and
by measurement rather than by era or publisher.

What a page can be
------------------
``fonte``
    A chess font sets the diagram, so :func:`detect_glyph_boards` reads the position
    exactly, with no inference and no rasterisation.  This is the differentiator of
    SPEC 6.1 "Via A".
``vetorial``
    No text, but the 8x8 grid is drawn as filled rectangles: :func:`detect_drawing_boards`
    finds the lattice.  The pieces still need naming once per book
    (:class:`~caissa.vision.detect.SignatureIndex`), after which every later occurrence in
    that book is an exact match.
``imagem-embutida``
    The PDF carries one image per diagram, with an exact bounding box.
``scan``
    One image covers the whole page: the raster path is the only path.
``sem-diagrama``
    Nothing on this page.

A **book** is named after what its diagram-bearing pages mostly are, and a book with pages
in more than one regime is ``misto`` -- which is a real category and not a shrug: 3 of the
27 in the trunk's survey were exactly that.

Cost
----
The whole scan is text and display-list queries; nothing is rendered.  Measured over the
50 PDFs of ``docs/quality/CORPUS.md`` at 24 sampled pages per book, in
``docs/quality/F3_REPORT.md`` 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

try:  # PyMuPDF renamed itself; both spellings are in the wild.
    import pymupdf  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only on old installs
    import fitz as pymupdf  # type: ignore[import-untyped, no-redef]

from .font_catalog import looks_like_chess_font, lookup_family
from .vector_detect import detect_drawing_boards, detect_glyph_boards

__all__ = ["BookSurvey", "PageSurvey", "Regime", "survey_page", "survey_pdf", "survey_shelf"]

Regime = str

FULL_PAGE_IMAGE_COVERAGE = 0.60
"""Fracao da area da pagina a partir da qual **uma** imagem e "a pagina inteira".

Um scan cobre a folha de margem a margem; um diagrama embutido de 590 pt numa pagina A5
cobre cerca de 30 %. O corte largo em 0,60 existe porque scan com margem branca aparada
chega a cobrir so dois tercos, e chamar isso de "imagem de diagrama" poria doze livros do
acervo na categoria errada.
"""

SQUARE_TOLERANCE = 0.25
"""Quanto uma imagem embutida pode fugir do quadrado e ainda ser candidata a diagrama."""


@dataclass(frozen=True)
class PageSurvey:
    """O que uma pagina traz, sem renderizar nada."""

    page: int
    regime: Regime
    glyph_boards: int = 0
    drawing_boards: int = 0
    chess_fonts: tuple[str, ...] = ()
    """Fontes catalogadas de diagrama encontradas, pelo nome como o PDF as declara."""

    figurine_fonts: tuple[str, ...] = ()
    """Fontes catalogadas como figurine **de texto corrido**. Nunca viram tabuleiro."""

    unknown_chess_fonts: tuple[str, ...] = ()
    """Nomes que parecem de fonte de xadrez e nao estao no catalogo. E a lista de trabalho."""

    embedded_images: int = 0
    square_images: int = 0
    full_page_image: bool = False
    filled_rects: int = 0
    """Retangulos preenchidos no display list -- a materia-prima do caminho ``vetorial``."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "regime": self.regime,
            "glyph_boards": self.glyph_boards,
            "drawing_boards": self.drawing_boards,
            "chess_fonts": list(self.chess_fonts),
            "figurine_fonts": list(self.figurine_fonts),
            "unknown_chess_fonts": list(self.unknown_chess_fonts),
            "embedded_images": self.embedded_images,
            "square_images": self.square_images,
            "full_page_image": self.full_page_image,
            "filled_rects": self.filled_rects,
        }


@dataclass
class BookSurvey:
    """O veredito de um livro, com o que o sustenta."""

    path: Path
    pages_total: int = 0
    sampled: int = 0
    pages: list[PageSurvey] = field(default_factory=list)
    error: str = ""

    @property
    def counts(self) -> dict[Regime, int]:
        out: dict[Regime, int] = {}
        for page in self.pages:
            out[page.regime] = out.get(page.regime, 0) + 1
        return out

    @property
    def verdict(self) -> Regime:
        """O regime das paginas **com diagrama**, ou ``misto`` quando ha mais de um.

        Paginas sem diagrama nao votam: um livro e o que os diagramas dele sao, e uma
        amostra que caia em vinte paginas de prosa nao muda isso. ``misto`` exige que o
        segundo regime apareca em pelo menos 20 % das paginas com diagrama -- abaixo disso
        e uma pagina de prefacio, nao um regime do livro.
        """
        if self.error:
            return "erro"
        counts = {k: v for k, v in self.counts.items() if k != "sem-diagrama"}
        if not counts:
            return "sem-diagrama"
        total = sum(counts.values())
        ordered = sorted(counts.items(), key=lambda item: -item[1])
        if len(ordered) > 1 and ordered[1][1] >= total * 0.20:
            return "misto"
        return ordered[0][0]

    @property
    def exact_pages(self) -> int:
        """Paginas em que a posicao sai **exata**, sem inferencia: o caminho de fonte."""
        return sum(1 for page in self.pages if page.glyph_boards)

    @property
    def chess_fonts(self) -> tuple[str, ...]:
        return tuple(sorted({name for page in self.pages for name in page.chess_fonts}))

    @property
    def figurine_fonts(self) -> tuple[str, ...]:
        return tuple(sorted({name for page in self.pages for name in page.figurine_fonts}))

    @property
    def unknown_chess_fonts(self) -> tuple[str, ...]:
        return tuple(sorted({name for page in self.pages for name in page.unknown_chess_fonts}))

    def as_dict(self) -> dict[str, Any]:
        return {
            "pdf": self.path.name,
            "pages_total": self.pages_total,
            "sampled": self.sampled,
            "verdict": self.verdict,
            "counts": self.counts,
            "glyph_boards": sum(p.glyph_boards for p in self.pages),
            "drawing_boards": sum(p.drawing_boards for p in self.pages),
            "exact_pages": self.exact_pages,
            "chess_fonts": list(self.chess_fonts),
            "figurine_fonts": list(self.figurine_fonts),
            "unknown_chess_fonts": list(self.unknown_chess_fonts),
            "error": self.error,
            "pages": [p.as_dict() for p in self.pages],
        }


def _font_names(page: Any) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """``(fontes de diagrama, fontes figurine, suspeitas nao catalogadas)`` da pagina."""
    diagram: set[str] = set()
    figurine: set[str] = set()
    unknown: set[str] = set()
    raw = page.get_text("dict")
    for block in raw.get("blocks", ()):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            for span in line.get("spans", ()):
                name = str(span.get("font", ""))
                if not name:
                    continue
                family = lookup_family(name)
                if family is None:
                    if looks_like_chess_font(name):
                        unknown.add(name)
                    continue
                (figurine if family.kind == "figurine" else diagram).add(name)
    return tuple(sorted(diagram)), tuple(sorted(figurine)), tuple(sorted(unknown))


def _image_shapes(page: Any) -> tuple[int, int, bool]:
    """``(imagens, imagens quadradas, tem imagem de pagina inteira)``."""
    area = float(page.rect.width * page.rect.height) or 1.0
    total = square = 0
    full = False
    for info in page.get_image_info():
        bbox = info.get("bbox")
        if not bbox:
            continue
        width = float(bbox[2] - bbox[0])
        height = float(bbox[3] - bbox[1])
        if width <= 1.0 or height <= 1.0:
            continue
        total += 1
        if (width * height) / area >= FULL_PAGE_IMAGE_COVERAGE:
            full = True
        elif abs(width - height) <= SQUARE_TOLERANCE * max(width, height):
            square += 1
    return total, square, full


def _filled_rects(page: Any) -> int:
    count = 0
    for item in page.get_drawings():
        if item.get("fill") is None:
            continue
        for piece in item.get("items", ()):
            if piece and piece[0] == "re":
                count += 1
    return count


def survey_page(page: Any, *, allow_unverified: bool = False) -> PageSurvey:
    """Classifica uma pagina pelo que o PDF declara, sem renderizar.

    A ordem das perguntas e a ordem do custo, e tambem a da exatidao: fonte de xadrez
    primeiro (exato, ~2 ms), grade vetorial depois, imagem embutida em seguida, e scan por
    ultimo -- que e a ordem do arbitro da SPEC 6.1.
    """
    diagram_fonts, figurine_fonts, unknown = _font_names(page)
    glyph = detect_glyph_boards(page, allow_unverified=allow_unverified)
    images, squares, full = _image_shapes(page)

    drawing_count = 0
    filled = 0
    if not glyph:
        filled = _filled_rects(page)
        if filled >= 16:
            drawing_count = len(detect_drawing_boards(page, identify=False))

    if glyph:
        regime = "fonte"
    elif drawing_count:
        regime = "vetorial"
    elif squares:
        regime = "imagem-embutida"
    elif full:
        regime = "scan"
    else:
        regime = "sem-diagrama"

    return PageSurvey(
        page=page.number,
        regime=regime,
        glyph_boards=len(glyph),
        drawing_boards=drawing_count,
        chess_fonts=diagram_fonts,
        figurine_fonts=figurine_fonts,
        unknown_chess_fonts=unknown,
        embedded_images=images,
        square_images=squares,
        full_page_image=full,
        filled_rects=filled,
    )


def _sample_indices(total: int, sample: int) -> list[int]:
    """Paginas espalhadas pelo miolo, evitando capa, indice e catalogo do fim.

    O levantamento do tronco amostrava "12 paginas do meio"; isto e a mesma ideia com o
    intervalo declarado: 5 % a 95 % do livro, espacado por igual.
    """
    if total <= 0:
        return []
    if total <= sample:
        return list(range(total))
    first = int(total * 0.05)
    last = int(total * 0.95)
    span = max(1, last - first)
    return sorted({first + (span * i) // sample for i in range(sample)})


def survey_pdf(path: Path | str, *, sample: int = 24, allow_unverified: bool = False) -> BookSurvey:
    """Amostra um livro e devolve o veredito com a evidencia por pagina."""
    path = Path(path)
    book = BookSurvey(path=path)
    try:
        with pymupdf.open(path) as doc:
            book.pages_total = doc.page_count
            indices = _sample_indices(doc.page_count, sample)
            book.sampled = len(indices)
            for index in indices:
                book.pages.append(survey_page(doc[index], allow_unverified=allow_unverified))
    except Exception as exc:  # noqa: BLE001 - a corrupt PDF is a finding, not a crash
        book.error = f"{type(exc).__name__}: {exc}"
    return book


def survey_shelf(
    pdf_dir: Path | str,
    *,
    sample: int = 24,
    allow_unverified: bool = False,
    only: Iterable[str] | None = None,
) -> list[BookSurvey]:
    """Todo PDF de uma pasta, em ordem de nome."""
    pdf_dir = Path(pdf_dir)
    names: Sequence[Path] = sorted(p for p in pdf_dir.glob("*.pdf") if p.is_file())
    if only is not None:
        wanted = {n.lower() for n in only}
        names = [p for p in names if any(w in p.name.lower() for w in wanted)]
    return [survey_pdf(path, sample=sample, allow_unverified=allow_unverified) for path in names]
