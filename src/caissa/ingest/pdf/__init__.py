"""PDF ingestion (front F2): the unification of three working implementations.

Absorbed 2026-09-11 from ``ChessVisionOFF_Puro/pdf_io.py`` + ``pdf_text.py``
(open once per scan, diagram caption context), from
``Editor_Diagramas_de_Xadrez/pdf_service.py`` (the two coordinate spaces, the
cancelable atomic save) and from ``PDFimport/extract.py`` (paragraph
reconstruction, figurines, bold by ink, outline attachment).  Each module's
docstring says what was kept, what was changed, and the measurement behind it.

Layers, bottom up:

``geometry``   the page's coordinate spaces as pure arithmetic
``document``   one open PDF: validation, metadata, outline, lock, pages
``render``     rasters through a byte-budgeted LRU cache
``textlayer``  styled spans and image placements of one page, in points
``captions``   what the text next to a diagram says about it
``paragraphs`` rows to paragraphs across columns and pages
``importer``   the two-pass pipeline that builds the Document IR
``finders``    the raster diagram route (trunk detector + F4 classifier)
``save``       writing a PDF atomically, with cancellation
"""

from __future__ import annotations

from caissa.ingest.pdf.captions import DiagramContext, contexts_for_page, parse_context
from caissa.ingest.pdf.document import (
    OutlineEntry,
    PdfDocument,
    PdfMetadata,
    PdfOpenError,
    open_pdf,
)
from caissa.ingest.pdf.finders import combined_finder, raster_diagram_finder
from caissa.ingest.pdf.geometry import PageFrame, RectT
from caissa.ingest.pdf.importer import (
    DiagramFinder,
    DiagramHit,
    ImportCanceled,
    ImportReport,
    ImportResult,
    OcrProvider,
    PageReport,
    PdfImporter,
    PdfImportOptions,
    import_pdf,
    vector_diagram_finder,
)
from caissa.ingest.pdf.paragraphs import ParagraphConfig
from caissa.ingest.pdf.render import PageRenderer, RenderCache, RenderedPage
from caissa.ingest.pdf.save import ExportCanceled, save_document_atomically
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan, extract_page_text

__all__ = [
    "DiagramContext",
    "DiagramFinder",
    "DiagramHit",
    "ExportCanceled",
    "ImportCanceled",
    "ImportReport",
    "ImportResult",
    "OcrProvider",
    "OutlineEntry",
    "PageFrame",
    "PageRenderer",
    "PageReport",
    "PageText",
    "ParagraphConfig",
    "PdfDocument",
    "PdfImportOptions",
    "PdfImporter",
    "PdfMetadata",
    "PdfOpenError",
    "RectT",
    "RenderCache",
    "RenderedPage",
    "TextLine",
    "TextSpan",
    "combined_finder",
    "contexts_for_page",
    "extract_page_text",
    "import_pdf",
    "open_pdf",
    "parse_context",
    "raster_diagram_finder",
    "save_document_atomically",
    "vector_diagram_finder",
]
