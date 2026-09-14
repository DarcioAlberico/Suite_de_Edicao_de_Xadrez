"""Exporters: five formats, one IR, and one rule.

The rule is SPEC section 5.2's: *nenhum exportador pode silenciosamente
descartar uma propriedade*. Every format declares, in
:mod:`caissa.export.profiles`, what it can and cannot carry; every exporter is
audited against that declaration as it writes; and
:mod:`caissa.export.fidelity` reads the written file back and proves the
declaration was true.

The five
--------
==========  ====================================  ===========================
Formato     Modulo                                Diagramas
==========  ====================================  ===========================
HTML        :mod:`caissa.export.html`             SVG inline (vetorial)
EPUB 3      :mod:`caissa.export.epub`             SVG inline (vetorial)
DOCX        :mod:`caissa.export.docx`             EMF vetorial, PNG de reserva
PDF         :mod:`caissa.export.pdf`              vetorial no proprio conteudo
LaTeX       :mod:`caissa.export.latex`            ``\\chessboard``, editavel
==========  ====================================  ===========================

Usage::

    from caissa.export import EXPORTERS, export

    result = export(document, Path("livro.epub"), "epub")
    print(result.summary())

From a PDF, whole or by page range (:mod:`caissa.export.book`)::

    from caissa.export import export_book

    result = export_book("Livro.pdf", None, "epub", pages="10-25")
    print(result.summary())
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from caissa.export.base import (
    Capability,
    ExportContext,
    Exporter,
    ExportError,
    ExportOptions,
    ExportResult,
    FormatProfile,
    PropertySupport,
    approximate,
    full,
    substitute,
    unsupported,
)
from caissa.export.book import (
    BOOK_FORMATS,
    BookExportResult,
    PageRangeError,
    default_output_path,
    describe_pages,
    export_book,
    parse_page_range,
)
from caissa.export.diagrams import DiagramRenderer, RenderedDiagram
from caissa.export.docx import DocxExporter, DocxOptions, read_docx
from caissa.export.epub import EpubExporter, EpubOptions, read_epub
from caissa.export.html import HtmlExporter, HtmlOptions, read_html
from caissa.export.latex import LatexExporter, LatexOptions, read_latex
from caissa.export.pdf import PdfExporter, PdfOptions, read_pdf
from caissa.export.profiles import PROFILES, profile_for
from caissa.export.text import game_from_pgn, game_to_pgn, render_move

__all__ = [
    "BOOK_FORMATS",
    "EXPORTERS",
    "PROFILES",
    "BookExportResult",
    "Capability",
    "DiagramRenderer",
    "DocxExporter",
    "DocxOptions",
    "EpubExporter",
    "EpubOptions",
    "ExportContext",
    "ExportError",
    "ExportOptions",
    "ExportResult",
    "Exporter",
    "FormatProfile",
    "HtmlExporter",
    "HtmlOptions",
    "LatexExporter",
    "LatexOptions",
    "PageRangeError",
    "PdfExporter",
    "PdfOptions",
    "PropertySupport",
    "RenderedDiagram",
    "approximate",
    "default_output_path",
    "describe_pages",
    "export",
    "export_book",
    "full",
    "game_from_pgn",
    "game_to_pgn",
    "parse_page_range",
    "profile_for",
    "read_docx",
    "read_epub",
    "read_html",
    "read_latex",
    "read_pdf",
    "render_move",
    "substitute",
    "unsupported",
]

EXPORTERS: Mapping[str, type[Exporter]] = {
    "html": HtmlExporter,
    "epub": EpubExporter,
    "docx": DocxExporter,
    "pdf": PdfExporter,
    "latex": LatexExporter,
}
"""Every exporter, keyed by format name."""


def export(
    document: object,
    destination: Path,
    format_name: str,
    *,
    options: ExportOptions | None = None,
) -> ExportResult:
    """Write a document in one format.

    Args:
        document: The :class:`~caissa.core.model.document.Document` to write.
        destination: Where to write it.
        format_name: One of the keys of :data:`EXPORTERS`.
        options: Export settings; the format's defaults are used when omitted.

    Returns:
        The result, including the degradation report.

    Raises:
        ExportError: No such format.
    """
    try:
        exporter = EXPORTERS[format_name]
    except KeyError as error:
        known = ", ".join(sorted(EXPORTERS))
        raise ExportError(
            f"Formato desconhecido: {format_name}. Disponiveis: {known}."
        ) from error
    return exporter().export(document, destination, options=options)  # type: ignore[arg-type]
