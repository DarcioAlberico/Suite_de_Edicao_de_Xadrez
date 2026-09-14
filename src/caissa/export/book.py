"""A PDF in, an EPUB or a DOCX out -- the whole book or a range of pages.

This is the composition the product window and the ``caissa-exportar`` command
share: :func:`caissa.ingest.pdf.import_pdf` builds the Document IR of the pages
asked for, and the exporter of :data:`caissa.export.EXPORTERS` writes it.  No
toolkit here; the Qt dialog in :mod:`caissa.ui.views.exportacao` and the CLI in
:mod:`caissa.export.cli` are two skins over :func:`export_book`.

Pages are **one-based in every string a person types or reads** (``"10-25"``,
``"1-3, 7, 40-"``) and zero-based in every sequence the code passes on, which is
what :class:`~caissa.ingest.pdf.PdfImportOptions.pages` expects.
:func:`parse_page_range` is the only place the two meet.

Progress is reported in two phases because they cost differently: the import
walks each page twice (survey, build) and, with OCR on, may take minutes on a
scanned book; the write takes milliseconds per page.  Cancellation is answered
between pages of the import, through the importer's own hook, and the partial
document is discarded -- there is nothing to resume, an EPUB of half a range
is not a deliverable.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

from caissa.core.model import Document, MetadataEntry
from caissa.export.base import ExportError, ExportOptions, ExportResult
from caissa.ingest.pdf import (
    ImportCanceled,
    ImportReport,
    PdfImportOptions,
    open_pdf,
)
from caissa.ingest.pdf.importer import PdfImporter

__all__ = [
    "BOOK_FORMATS",
    "BookExportResult",
    "PageRangeError",
    "ProgressHook",
    "default_output_path",
    "describe_pages",
    "export_book",
    "format_for_path",
    "parse_page_range",
]

BOOK_FORMATS: Final[tuple[str, ...]] = ("epub", "docx")
"""The formats a book is published in from the window; both write one file."""

_EXTENSION: Final[dict[str, str]] = {"epub": ".epub", "docx": ".docx"}
_FORMAT_LABEL: Final[dict[str, str]] = {"epub": "EPUB", "docx": "DOCX"}
_RANGE_PIECE: Final = re.compile(r"^\s*(\d*)\s*(?:(-|–|—|\.\.)\s*(\d*))?\s*$")

ProgressHook = Callable[[str, int, int], None]
"""``(phase, done, total)``: ``phase`` is ``"importando"`` or ``"gravando"``."""


class PageRangeError(ValueError):
    """A page range a person typed cannot be read, with the reason in Portuguese."""


# --------------------------------------------------------------------------- #
# Page ranges
# --------------------------------------------------------------------------- #


def parse_page_range(text: str, page_count: int) -> tuple[int, ...]:
    """Read a one-based range string into sorted, unique zero-based indices.

    Accepted pieces, separated by commas: ``7``, ``10-25``, ``40-`` (to the
    end), ``-3`` (from the start), ``10..25``.  An empty string means the
    whole book.

    Args:
        text: What the person typed.
        page_count: Pages in the PDF; every number must fall in ``1..page_count``.

    Returns:
        Zero-based indices in reading order, without repeats.

    Raises:
        PageRangeError: Empty piece, non-number, page out of range, or a range
            whose end precedes its start.
    """
    if page_count < 1:
        raise PageRangeError("O PDF não tem páginas.")
    cleaned = text.strip()
    if not cleaned:
        return tuple(range(page_count))
    chosen: set[int] = set()
    for piece in cleaned.split(","):
        match = _RANGE_PIECE.match(piece)
        if match is None or not piece.strip():
            raise PageRangeError(
                f"Não entendi «{piece.strip()}». Use números de página separados por "
                f"vírgula e intervalos como 10-25."
            )
        start_text, dash, end_text = match.groups()
        if dash is not None and not start_text and not end_text:
            raise PageRangeError(f"Falta um número de página em «{piece.strip()}».")
        if dash is None:
            first = last = _page_number(start_text, page_count, piece)
        else:
            first = _page_number(start_text, page_count, piece) if start_text else 1
            last = _page_number(end_text, page_count, piece) if end_text else page_count
        if last < first:
            raise PageRangeError(f"O intervalo «{piece.strip()}» termina antes de começar.")
        chosen.update(range(first - 1, last))
    return tuple(sorted(chosen))


def _page_number(text: str, page_count: int, piece: str) -> int:
    if not text:
        raise PageRangeError(f"Falta um número de página em «{piece.strip()}».")
    number = int(text)
    if not 1 <= number <= page_count:
        raise PageRangeError(f"A página {number} não existe: o PDF tem {page_count} página(s).")
    return number


def describe_pages(indices: Sequence[int] | None, page_count: int) -> str:
    """The shortest one-based description of a selection, for names and notes.

    ``None`` or every page reads as ``"livro completo"``; runs collapse to
    ``"10-25"``; the rest is a comma list.
    """
    if indices is None or (len(indices) == page_count and set(indices) == set(range(page_count))):
        return "livro completo"
    if not indices:
        return "nenhuma página"
    ordered = sorted(set(indices))
    runs: list[str] = []
    start = previous = ordered[0]
    for index in ordered[1:]:
        if index == previous + 1:
            previous = index
            continue
        runs.append(_run(start, previous))
        start = previous = index
    runs.append(_run(start, previous))
    return ", ".join(runs)


def _run(start: int, end: int) -> str:
    return f"{start + 1}" if start == end else f"{start + 1}-{end + 1}"


# --------------------------------------------------------------------------- #
# Names and formats
# --------------------------------------------------------------------------- #


def format_for_path(path: Path) -> str:
    """The book format a destination's extension names.

    Raises:
        ExportError: The extension is not one of :data:`BOOK_FORMATS`.
    """
    suffix = path.suffix.lower()
    for name, extension in _EXTENSION.items():
        if suffix == extension:
            return name
    known = ", ".join(_EXTENSION.values())
    raise ExportError(f"Extensão {suffix or '(nenhuma)'} não é de livro; use {known}.")


def default_output_path(
    pdf_path: Path, format_name: str, indices: Sequence[int] | None, page_count: int
) -> Path:
    """Beside the PDF, same stem, the page selection in the name when partial.

    ``Livro.pdf`` becomes ``Livro.epub`` for the whole book and
    ``Livro (p. 10-25).epub`` for a range, so two exports of the same book do
    not overwrite each other.
    """
    _check_format(format_name)
    pages = describe_pages(indices, page_count)
    stem = pdf_path.stem if pages == "livro completo" else f"{pdf_path.stem} (p. {pages})"
    return pdf_path.with_name(stem + _EXTENSION[format_name])


def _check_format(format_name: str) -> None:
    if format_name not in BOOK_FORMATS:
        known = ", ".join(BOOK_FORMATS)
        raise ExportError(f"Formato de livro desconhecido: {format_name}. Use {known}.")


# --------------------------------------------------------------------------- #
# The composition
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, kw_only=True)
class BookExportResult:
    """What one book export produced, from both halves of the pipeline."""

    format: str
    path: Path
    page_indices: tuple[int, ...]
    page_count: int
    document: Document
    import_report: ImportReport
    export_result: ExportResult
    warnings: tuple[str, ...] = field(default_factory=tuple)
    """The OCR regions the import could not settle, one line each, one-based page first."""

    @property
    def pages(self) -> str:
        return describe_pages(self.page_indices, self.page_count)

    def summary(self) -> str:
        """One line for a status bar, in Portuguese."""
        label = _FORMAT_LABEL[self.format]
        count = len(self.page_indices)
        head = f"{label} gravado em {self.path.name}: {count} página(s) ({self.pages})"
        counters = self.import_report.counters
        parts = [head]
        if counters:
            parts.append(
                f"{counters.get('paragraphs', 0)} parágrafos, "
                f"{counters.get('headings', 0)} títulos, "
                f"{counters.get('diagrams', 0)} diagramas, "
                f"{counters.get('figures', 0) + counters.get('scanned_pages', 0)} imagens"
            )
        degraded = self.export_result.degradation
        if not degraded.is_lossless:
            parts.append(f"{len(degraded.warnings)} propriedade(s) aproximada(s) no {label}")
        if self.warnings:
            parts.append(f"OCR: {len(self.warnings)} região(ões) para revisão")
        return "; ".join(parts) + "."


def export_book(
    pdf_path: Path | str,
    destination: Path | str | None,
    format_name: str,
    *,
    pages: Sequence[int] | str | None = None,
    enable_ocr: bool | None = None,
    import_options: PdfImportOptions | None = None,
    export_options: ExportOptions | None = None,
    progress: ProgressHook | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> BookExportResult:
    """Import the pages asked for and write them as one EPUB or DOCX.

    Args:
        pdf_path: The book.
        destination: Where to write; ``None`` uses :func:`default_output_path`.
        format_name: ``"epub"`` or ``"docx"``.
        pages: Zero-based indices, a one-based range string such as
            ``"10-25"``, or ``None`` for the whole book.
        enable_ocr: Read pages without a usable text layer with OCR.  Off is the
            fast path: such pages import as images.  ``None`` keeps what
            ``import_options`` says (on, by default).
        import_options: Overrides for the import; ``pages``, ``progress`` and
            ``should_cancel`` are set from the arguments above, and
            ``asset_dir`` too when it is ``None``: the images of the pages
            (figures, scanned pages, abstained OCR regions) are extracted to
            a temporary folder for the exporter to package, and dropped
            after the write.
        export_options: Overrides for the write.
        progress: ``(phase, done, total)`` as the work advances.
        should_cancel: Polled between pages of the import.

    Returns:
        The result with both reports.

    Raises:
        ExportError: Unknown format.
        PageRangeError: The range string cannot be read.
        IndexError: A zero-based index is out of the PDF.
        ImportCanceled: ``should_cancel`` answered ``True``; nothing was written.
        caissa.ingest.pdf.PdfOpenError: The file is not a usable PDF.
    """
    _check_format(format_name)
    source = Path(pdf_path)
    with tempfile.TemporaryDirectory(prefix="caissa-export-") as scratch:
        return _export_book(
            source,
            destination,
            format_name,
            pages=pages,
            enable_ocr=enable_ocr,
            import_options=import_options,
            export_options=export_options,
            progress=progress,
            should_cancel=should_cancel,
            scratch=Path(scratch),
        )


def _export_book(
    source: Path,
    destination: Path | str | None,
    format_name: str,
    *,
    pages: Sequence[int] | str | None,
    enable_ocr: bool | None,
    import_options: PdfImportOptions | None,
    export_options: ExportOptions | None,
    progress: ProgressHook | None,
    should_cancel: Callable[[], bool] | None,
    scratch: Path,
) -> BookExportResult:
    with open_pdf(source) as pdf:
        page_count = pdf.page_count
        if isinstance(pages, str):
            indices = parse_page_range(pages, page_count)
        elif pages is None:
            indices = tuple(range(page_count))
        else:
            indices = tuple(pdf.check_index(int(i)) for i in pages)
        if not indices:
            raise PageRangeError("Nenhuma página selecionada.")
        target = (
            Path(destination)
            if destination is not None
            else default_output_path(source, format_name, indices, page_count)
        )

        def import_progress(done: int, total: int) -> None:
            if progress is not None:
                progress("importando", done, total)

        options = replace(
            import_options or PdfImportOptions(),
            pages=indices,
            progress=import_progress,
            should_cancel=should_cancel,
        )
        if enable_ocr is not None:
            options.enable_ocr = enable_ocr
        if options.asset_dir is None:
            options.asset_dir = scratch / "assets"
        imported = PdfImporter(pdf, options).run()

    if should_cancel is not None and should_cancel():
        raise ImportCanceled("Exportação cancelada antes da gravação; nada foi escrito.")
    document = _stamp_selection(imported.document, indices, page_count)
    if progress is not None:
        progress("gravando", 0, 1)
    from caissa.export import export

    written = export(document, target, format_name, options=export_options)
    if progress is not None:
        progress("gravando", 1, 1)
    warnings = tuple(
        f"página {item.page_index + 1}: {item.decision} -- {'; '.join(item.reasons)}"
        for item in imported.report.review_items
    )
    return BookExportResult(
        format=format_name,
        path=written.path,
        page_indices=indices,
        page_count=page_count,
        document=document,
        import_report=imported.report,
        export_result=written,
        warnings=warnings,
    )


def _stamp_selection(document: Document, indices: Sequence[int], page_count: int) -> Document:
    """Record which pages of the source the file holds, so a reader can tell.

    A partial export keeps the book's title -- a reader shelves it under the
    book -- and says in the metadata (``caissa:pages``) and in the description
    which pages it is.  A whole-book export is left alone.
    """
    pages = describe_pages(indices, page_count)
    if pages == "livro completo":
        return document
    metadata = document.metadata
    note = f"Páginas {pages} de {page_count} do original."
    description = f"{metadata.description}\n{note}" if metadata.description else note
    custom = (*metadata.custom, MetadataEntry(name="pages", value=pages, scheme="caissa"))
    return replace(document, metadata=replace(metadata, description=description, custom=custom))
