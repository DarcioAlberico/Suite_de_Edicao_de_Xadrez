"""Importers: from a file on disk to the Document IR (SPEC section 4, ``INGEST``).

``caissa.ingest.pdf``
    PDF, vector or scanned: one open handle, a byte-budgeted render cache, the
    text layer judged before it is believed, paragraphs rebuilt across pages,
    diagrams as positions.  See :mod:`caissa.ingest.pdf`.

Every importer produces a :class:`~caissa.core.model.Document` with provenance
on every node, which is what lets the reader tint doubtful text and lets an
export be audited back to a page rectangle.
"""

from __future__ import annotations

from caissa.ingest.pdf import (
    ImportReport,
    ImportResult,
    PdfDocument,
    PdfImportOptions,
    PdfOpenError,
    import_pdf,
    open_pdf,
)

__all__ = [
    "ImportReport",
    "ImportResult",
    "PdfDocument",
    "PdfImportOptions",
    "PdfOpenError",
    "import_pdf",
    "open_pdf",
]
