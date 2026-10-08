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

import logging
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from caissa.core.model import Document, MetadataEntry, ResourceKind
from caissa.export.base import ExportError, ExportOptions, ExportResult
from caissa.ingest.pdf import (
    ImportCanceled,
    ImportReport,
    ImportResult,
    PdfImportOptions,
    open_pdf,
)
from caissa.ingest.pdf.importer import PdfImporter

LOGGER = logging.getLogger(__name__)

__all__ = [
    "BOOK_FORMATS",
    "BookExportResult",
    "PageRangeError",
    "ProgressHook",
    "apply_diagram_decisions",
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


def _write_provenance(
    document: Document, written: Path, format_name: str, indices: Sequence[int],
    pdf_path: Path | str,
) -> tuple[Path | None, str | None]:
    """The sidecar beside the book, or why it is not there -- never fatal (A11 is additive).

    A failure is logged *and* returned, for :attr:`BookExportResult.provenance_error` and
    the summary to say it: a sidecar that failed on every real import looked like success.
    """
    from caissa.export.provenance import write_sidecar

    profile: dict[str, Any] = {}
    try:
        from caissa.ocr.book_profile import BookProfile

        stored = BookProfile.for_pdf(Path(pdf_path))
        if stored is not None:
            profile = {"fingerprint": stored.fingerprint, "closures": stored.closures,
                       "model_identity": stored.model_identity, "dataset_version": stored.dataset_version}
    except Exception:  # noqa: BLE001 - the profile is a courtesy of the header
        profile = {}
    try:
        path = write_sidecar(document, written, format_name=format_name, pages=indices,
                             profile=profile)
    except Exception as exc:  # noqa: BLE001 - additive: the book is written, the sidecar is not
        LOGGER.warning("sidecar de proveniência não gravado ao lado de %s", written, exc_info=True)
        return None, f"{type(exc).__name__}: {exc}"
    return path, None


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
    decisions_applied: int = 0
    """Regions the reviewer had settled (OCR_UI_ROADMAP passo 14), applied on import."""
    diagram_decisions_applied: int = 0
    """Positions the reviewer had corrected (OCR_UI ciclo 2, passo A3), applied on import."""
    provenance_path: Path | None = None
    """The provenance sidecar written next to the book (ciclo 2, passo A11); ``None`` when
    the write failed (the book is still there -- the sidecar is additive)."""
    provenance_error: str | None = None
    """Why :attr:`provenance_path` is ``None`` -- the exception, in one line; :meth:`summary`
    says it, so the failure reaches the status bar and the CLI, not only the log."""

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
        if self.decisions_applied:
            parts.append(f"{self.decisions_applied} decisão(ões) do revisor aplicada(s)")
        if self.diagram_decisions_applied:
            parts.append(
                f"{self.diagram_decisions_applied} posição(ões) corrigida(s) pelo revisor"
            )
        if self.warnings:
            parts.append(
                f"OCR: {'restam ' if self.decisions_applied else ''}"
                f"{len(self.warnings)} região(ões) para revisão"
            )
        if self.provenance_error:
            parts.append(f"sidecar de proveniência não gravado ({self.provenance_error})")
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
    document: Document | ImportResult | None = None,
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
            after the write.  ``review_decisions`` and ``diagram_decisions``
            left ``None`` are loaded from the book's files under the
            labelling project (what the reviewer settled in the text-review
            window and in the diagram panel -- OCR_UI passo 14 and ciclo 2
            passo A3).
        export_options: Overrides for the write.
        progress: ``(phase, done, total)`` as the work advances.
        should_cancel: Polled between pages of the import.
        document: A :class:`~caissa.core.model.Document` -- or the whole
            :class:`~caissa.ingest.pdf.ImportResult`, whose report then
            travels into the result -- already in hand (the window's
            *Importar o livro*, OCR_UI ciclo 2 passo A3): the import is
            skipped and the document is written as it is, so the book is
            read once.  The caller is responsible for it covering ``pages``
            -- the trunk's ``Ponte.documento_para`` only hands one over when
            the pages asked for are within the pages imported and the import
            was not cancelled.  Images the document references must still be
            on disk (its ``asset_dir``).

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
            document=document,
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
    document: Document | ImportResult | None = None,
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

        if document is not None and not _covers_exactly(document, indices, page_count):
            # The ready document is written as it is: a book of three pages asked for
            # as "page 1" must not come out with the three.  A bare ``Document`` has no
            # page list, so it only qualifies for the whole book.
            LOGGER.warning(
                "%s: o documento pronto não é exatamente as páginas pedidas; a exportação reimporta.",
                source.name,
            )
            document = None
        if document is not None and not _images_on_disk(
            document.document if isinstance(document, ImportResult) else document
        ):
            # The window's import without an ``asset_dir`` (or one whose files
            # are gone) has image resources with no file behind them; the EPUB
            # would drop those pages' images and call it a success.  Say so and
            # read the book again instead of writing a hollow one.
            LOGGER.warning(
                "%s: o documento pronto não tem as imagens em disco; a exportação reimporta.",
                source.name,
            )
            document = None
        if document is not None:
            # Passo A3: the book was read once already; write what is in hand --
            # with the positions the reviewer corrected *after* that import
            # applied to it, or the correction made in the window would be the
            # one thing an export of the window's own document left out.
            imported = (
                document
                if isinstance(document, ImportResult)
                else ImportResult(document=document, report=ImportReport())
            )
            decisions = import_options.diagram_decisions if import_options is not None else None
            if decisions is None:
                from caissa.ocr.diagram_decisions import DiagramDecisions

                decisions = DiagramDecisions.for_pdf(source)
            if decisions is not None:
                imported = apply_diagram_decisions(imported, decisions)
            if progress is not None:
                progress("importando", 1, 1)
        else:
            options = _import_options(
                source,
                import_options,
                indices,
                enable_ocr=enable_ocr,
                progress=import_progress,
                should_cancel=should_cancel,
                scratch=scratch,
            )
            imported = PdfImporter(pdf, options).run()

    if should_cancel is not None and should_cancel():
        raise ImportCanceled("Exportação cancelada antes da gravação; nada foi escrito.")
    document = _stamp_selection(imported.document, indices, page_count)
    if progress is not None:
        progress("gravando", 0, 1)
    from caissa.export import export

    written = export(document, target, format_name, options=export_options)
    # A11: the provenance the EPUB/DOCX cannot carry, next to it, keyed like the PGN's.
    provenance_path, provenance_error = _write_provenance(
        document, written.path, format_name, indices, source
    )
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
        decisions_applied=int(imported.report.counters.get("review_decisions_applied", 0)),
        diagram_decisions_applied=int(
            imported.report.counters.get("diagram_decisions_applied", 0)
        ),
        provenance_path=provenance_path,
        provenance_error=provenance_error,
    )


def _covers_exactly(
    document: Document | ImportResult, indices: Sequence[int], page_count: int
) -> bool:
    """Whether the ready document is exactly the pages asked for (passo A3).

    An :class:`ImportResult` says which pages it built (``report.pages``); a
    bare :class:`Document` says nothing, so it only qualifies when the export
    asks for the whole book.
    """
    wanted = {int(i) for i in indices}
    if isinstance(document, ImportResult):
        built = {int(p.index) for p in getattr(document.report, "pages", ())}
        return bool(wanted) and built == wanted
    return wanted == set(range(page_count))


def _images_on_disk(document: Document) -> bool:
    """Whether every image resource the document references is a file on disk (passo A3)."""
    for resource in getattr(document, "resources", ()):
        if getattr(resource, "kind", None) is not ResourceKind.IMAGE:
            continue
        path = getattr(resource, "path", None)
        if not path or not Path(path).is_file():
            return False
    return True


def _import_options(
    source: Path,
    base: PdfImportOptions | None,
    indices: Sequence[int],
    *,
    enable_ocr: bool | None,
    progress: Callable[[int, int], None],
    should_cancel: Callable[[], bool] | None,
    scratch: Path,
) -> PdfImportOptions:
    """The import options of one export: the caller's, completed with what the export sets.

    ``review_decisions`` and ``diagram_decisions`` left ``None`` are loaded
    from the book's files under the labelling project, so the export sees the
    book as the reviewer left it (OCR_UI passo 14; ciclo 2 passo A3).
    """
    options = replace(
        base or PdfImportOptions(),
        pages=indices,
        progress=progress,
        should_cancel=should_cancel,
    )
    if enable_ocr is not None:
        options.enable_ocr = enable_ocr
    if options.asset_dir is None:
        options.asset_dir = scratch / "assets"
    if options.review_decisions is None:
        # What the reviewer settled in the text-review window, when anything.
        from caissa.ocr.review import ReviewDecisions

        options.review_decisions = ReviewDecisions.for_pdf(source)
    if options.diagram_decisions is None:
        # And the positions corrected in the diagram panel (passo A3).
        from caissa.ocr.diagram_decisions import DiagramDecisions

        options.diagram_decisions = DiagramDecisions.for_pdf(source)
    return options


def apply_diagram_decisions(imported: ImportResult, decisions: Any) -> ImportResult:
    """The import with the reviewer's positions applied to its top-level diagrams (passo A3).

    The importer applies :class:`~caissa.ocr.diagram_decisions.DiagramDecisions`
    while it builds the nodes; this is the same rule for a document that was
    built **before** the decision existed -- the window's import, corrected
    and saved afterwards, then exported from memory.  A diagram whose
    ``source`` places it on a page is matched by IoU ≥ 0,5 like the importer
    does; the machine's reading stays in ``recognition.fen`` and the warning,
    the provenance and the counter (``diagram_decisions_applied``) say what
    happened.  A decision already applied on import is not counted twice.
    The stipulation follows the importer's precedence too: a printed demand
    (``"Mate em 2"``, C12) stays; only a stipulation that says no more than
    whose move it is -- or none -- takes the reviewer's side
    (:func:`_stipulation_after_decision`).
    """
    from caissa.core.model import Diagram, SourceKind

    applied = 0
    body: list[Any] = []
    for block in imported.document.body:
        if not isinstance(block, Diagram) or block.source is None or block.source.rect is None:
            body.append(block)
            continue
        rect = block.source.rect
        box = (rect.x, rect.y, rect.x + rect.width, rect.y + rect.height)
        decision = decisions.match(int(block.source.page_index or 0), box)
        if decision is None or block.fen == decision.fen:
            body.append(block)
            continue
        applied += 1
        who = f" ({decision.reviewer})" if decision.reviewer else ""
        note = f"corrigido pelo revisor{who} em {decision.decided_at or 'data desconhecida'}"
        recognition = block.recognition
        if recognition is not None:
            recognition = replace(recognition, warnings=(*recognition.warnings, note))
        provenance = block.provenance
        if provenance is not None:
            provenance = replace(
                provenance, verified_by_human=True, kind=SourceKind.HUMAN, confidence=1.0
            )
        body.append(
            replace(
                block,
                fen=decision.fen,
                recognition=recognition,
                provenance=provenance,
                stipulation=_stipulation_after_decision(block.stipulation, decision.side),
                side_to_move_indicator=True,
            )
        )
    if not applied:
        return imported
    report = imported.report
    report.counters["diagram_decisions_applied"] = (
        int(report.counters.get("diagram_decisions_applied", 0)) + applied
    )
    return ImportResult(document=replace(imported.document, body=tuple(body)), report=report)


_SIDE_ONLY_STIPULATIONS: Final = frozenset({"brancas jogam", "pretas jogam"})
"""What the importer writes when all it knows is whose move it is, casefolded."""


def _stipulation_after_decision(current: str | None, side: str) -> str:
    """The stipulation of a diagram the reviewer corrected after the import (passo A3).

    ``"Brancas jogam"``/``"Pretas jogam"`` only restate the side to move, so they follow
    the reviewer's side, as an empty stipulation takes it; anything that says more -- the
    caption's ``"Mate em 2"`` -- is the book's demand and stays, as it does when the
    importer applies the decision itself.
    """
    if current is not None:
        said = " ".join(current.split()).rstrip(".").casefold()
        if said and said not in _SIDE_ONLY_STIPULATIONS:
            return current
    return "Brancas jogam" if side == "w" else "Pretas jogam"


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
