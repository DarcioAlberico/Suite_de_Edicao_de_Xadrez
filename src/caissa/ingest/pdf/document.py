"""One open PDF, owned or borrowed, validated before anyone touches a page.

This is the unification the roadmap calls F2: the trunk's ``pdf_io.py``
(``OpenPdf`` -- open once per scan, lend the handle), the Editor's
``pdf_service.py`` (a service that owns the document and a lock) and
PDFimport's ``extract.py`` (``open_pdf`` -- refuse what is not a PDF) each
solved a third of the problem.  Absorbed 2026-09-11, with the measurements
that justified each of them kept:

**Open once, lend the handle (trunk, S-61).**  Each page used to go through
three independent opens -- render, detection, text layer.  Measured: 1,16 ms
per open on the ``Polgar`` and **28,80 ms** on the ``Yusupov``, which over a
full scan is 4,1 s against 225,7 s.  So the document is opened once and
:class:`PdfDocument` is what circulates.  A borrowed document is never closed
by the borrower: a ``with pymupdf.open(...)`` in the middle of a pipeline would
close the scan's document and the symptom would appear on the *next* page, far
from the cause.

**Refuse the encrypted file at open (trunk, S-331).**  ``pymupdf.open`` accepts
a password-protected PDF without complaint: ``needs_pass`` is set,
``page_count`` answers the right number, and only the first page access raises
``ValueError: document closed or encrypted`` -- in English, three layers away
from the code that could have said what was wrong.  Nothing in this product can
ask for a password, so the refusal is here, once, in Portuguese.

**Refuse what is not a PDF (PDFimport).**  MuPDF also reads XPS, CBZ, SVG,
EPUB and plain text, so a mistyped path happily converts into a one-page book
instead of reporting the mistake.

**Never iterate the pages at open.**  ``pymupdf.open`` on a path reads the
xref table and nothing else; page objects are parsed on first access and
released when the Python object dies.  Everything here preserves that: the
page count, the metadata and the outline are all header-level reads, and the
first page of a 500-page book costs the same as the first page of a 5-page one
(SPEC 11.3: ``<= 2 s`` to first page; measured in ``test_gates.py``).

**One lock per document.**  PyMuPDF is not thread-safe.  The reader UI renders
on a worker while the importer reads text on another; without a lock that is a
crash with no traceback.  Every method here takes :attr:`PdfDocument.lock`;
callers that hold a raw page across several calls take it themselves via
:meth:`PdfDocument.locked`.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from caissa.ingest.pdf.geometry import PageFrame

__all__ = [
    "OutlineEntry",
    "PdfDocument",
    "PdfMetadata",
    "PdfOpenError",
    "open_count",
    "open_pdf",
]

LOGGER = logging.getLogger("caissa.ingest.pdf")

_WS: Final = re.compile(r"\s+")
_HASH_CHUNK: Final = 1 << 20
#: Beyond this many characters a "title" is a pasted abstract, not a title.
_MAX_META_LEN: Final = 500
#: Calibre packs ``"Title - Author"`` into the title field; the author half is
#: accepted only when it is short enough to be a name.
_MAX_PACKED_AUTHOR: Final = 60
_MIN_PACKED_AUTHOR: Final = 2
#: A file-name author is a surname, ``Karpov A`` or ``Euwe, Kramer`` -- three
#: words at most; a longer head is a title.
_MAX_AUTHOR_WORDS: Final = 3
#: First code point outside the Basic Multilingual Plane.
_ASTRAL: Final = 0x10000

_opens = 0
_opens_lock = threading.Lock()


def open_count() -> int:
    """How many times a document was actually opened by this process.

    Exists so the S-61 test can assert "one open per scan, not three" without
    instrumenting PyMuPDF.
    """
    return _opens


class PdfOpenError(ValueError):
    """The file cannot be used as a PDF, with the reason in Portuguese.

    A ``ValueError`` so the trunk's CLI error translation (code 2) and the
    panel's existing ``except`` both catch it unchanged.
    """


def _pymupdf() -> Any:
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - environment dependent
        try:
            import fitz as pymupdf  # type: ignore[import-untyped, no-redef]
        except ImportError as exc:
            raise PdfOpenError(
                "PyMuPDF não está instalado, portanto nenhum PDF pode ser aberto. "
                "Instale-o com 'pip install pymupdf'."
            ) from exc
    return pymupdf


def clean_metadata_text(text: str | None) -> str:
    """Metadata as a reader should see it.

    Ported from ``PDFimport/extract.py::_clean_meta_text``.  PDFs passed around
    on file-sharing channels arrive with the channel's decorations baked into
    the title -- a pictograph in front, control bytes from a sloppy tool.
    Letters and digits outside the Basic Multilingual Plane are kept (they are
    real script); symbols and pictographs out there, and anything unassigned or
    private, are dropped.
    """
    out: list[str] = []
    for ch in text or "":
        code = ord(ch)
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf", "Co", "Cn", "Cs") and ch != "\t":
            continue
        if code >= _ASTRAL and not cat.startswith(("L", "N")):
            continue
        out.append(ch)
    cleaned = _WS.sub(" ", "".join(out)).strip(" _-.,;:")
    return cleaned[:_MAX_META_LEN]


@dataclass(frozen=True, slots=True)
class PdfMetadata:
    """The document information dictionary, cleaned.

    Attributes:
        title: Title, falling back to the file name when the field is empty.
        author: Author, empty when unknown.  ``"unknown"`` counts as empty.
        subject: Subject field.
        keywords: Keywords field.
        creator: Producing application.
        producer: PDF library that wrote the file.
        creation_date: Raw ``D:YYYYMMDD...`` string; parsed by whoever needs it.
        modification_date: Same, for the last modification.
        title_from_filename: True when the title came from the file name.
    """

    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    modification_date: str = ""
    title_from_filename: bool = False

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | None, path: Path | None) -> PdfMetadata:
        raw = raw or {}
        title = clean_metadata_text(str(raw.get("title") or ""))
        author = clean_metadata_text(str(raw.get("author") or ""))
        from_filename = False
        if not title and path is not None:
            title = clean_metadata_text(path.stem)
            from_filename = True
        if author.lower() == "unknown":
            author = ""
        if not author and " - " in title:
            if from_filename:
                # Measured on the 24 dashed file names of the reference
                # collection: 19 are "Author - Title (year)", 5 are
                # "Title - Author".  A short head that does not open with a
                # digit picks the 19 and mislabels 2 ("Simple Chess - Stean",
                # "Xadrez Vitorioso - ..."); the raw stem is kept in ``custom``
                # so the user can see what was guessed from.
                head, tail = title.split(" - ", 1)
                head_words = head.strip().split()
                if (
                    0 < len(head_words) <= _MAX_AUTHOR_WORDS
                    and not head_words[0][0].isdigit()
                    and _MIN_PACKED_AUTHOR < len(head.strip()) < _MAX_PACKED_AUTHOR
                    and tail.strip()
                ):
                    author, title = head.strip(), tail.strip()
            else:
                # Calibre packs "Title - Author" into the title *field*.
                head, tail = title.rsplit(" - ", 1)
                if _MIN_PACKED_AUTHOR < len(tail.strip()) < _MAX_PACKED_AUTHOR and head.strip():
                    title, author = head.strip(), tail.strip()
        return cls(
            title=title,
            author=author,
            subject=clean_metadata_text(str(raw.get("subject") or "")),
            keywords=clean_metadata_text(str(raw.get("keywords") or "")),
            creator=clean_metadata_text(str(raw.get("creator") or "")),
            producer=clean_metadata_text(str(raw.get("producer") or "")),
            creation_date=str(raw.get("creationDate") or ""),
            modification_date=str(raw.get("modDate") or ""),
            title_from_filename=from_filename,
        )


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    """One bookmark of the PDF outline.

    Attributes:
        level: Nesting depth, ``1`` for a top-level entry.
        title: Bookmark text.
        page_index: Zero-based target page, or ``-1`` for an entry without a
            page destination (an external link, a collapsed group).
    """

    level: int
    title: str
    page_index: int


class PdfDocument:
    """An open PDF: page access, metadata, outline, one lock, one close.

    Construct with :func:`open_pdf` (owns the handle) or
    :meth:`PdfDocument.borrow` (does not).  Both are context managers; closing
    a borrowed document is a no-op, by design (see the module docstring).
    """

    __slots__ = (
        "_content_hash",
        "_doc",
        "_frames",
        "_metadata",
        "_outline",
        "_owned",
        "_page_count",
        "lock",
        "path",
        "source_name",
    )

    def __init__(self, doc: Any, *, path: Path | None, owned: bool, source_name: str) -> None:
        self._doc = doc
        self._owned = owned
        self.path = path
        self.source_name = source_name
        self.lock = threading.RLock()
        self._page_count = int(doc.page_count)
        self._metadata: PdfMetadata | None = None
        self._outline: tuple[OutlineEntry, ...] | None = None
        self._content_hash: str | None = None
        self._frames: dict[int, PageFrame] = {}

    # -- construction ------------------------------------------------------ #

    @classmethod
    def borrow(cls, doc: Any, *, path: Path | str | None = None) -> PdfDocument:
        """Wrap an already-open ``pymupdf.Document`` without taking ownership."""
        p = Path(path) if path is not None else _path_of(doc)
        _validate(doc, p.name if p else "O PDF recebido em memória")
        return cls(doc, path=p, owned=False, source_name=p.name if p else "memória")

    @property
    def raw(self) -> Any:
        """The underlying ``pymupdf.Document``.  Hold :attr:`lock` while using it."""
        return self._doc

    @property
    def is_owned(self) -> bool:
        return self._owned

    @property
    def is_closed(self) -> bool:
        return bool(getattr(self._doc, "is_closed", False))

    # -- lifetime ---------------------------------------------------------- #

    def close(self) -> None:
        """Close the handle if this object owns it; otherwise do nothing."""
        if not self._owned:
            return
        with self.lock:
            if not self.is_closed:
                self._doc.close()
        self._frames.clear()

    def __enter__(self) -> PdfDocument:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def locked(self) -> Iterator[Any]:
        """Hold the document lock and get the raw document for several calls."""
        with self.lock:
            yield self._doc

    # -- header-level facts ------------------------------------------------ #

    @property
    def page_count(self) -> int:
        return self._page_count

    def __len__(self) -> int:
        return self._page_count

    @property
    def metadata(self) -> PdfMetadata:
        if self._metadata is None:
            with self.lock:
                self._metadata = PdfMetadata.from_raw(self._doc.metadata, self.path)
        return self._metadata

    @property
    def outline(self) -> tuple[OutlineEntry, ...]:
        """The PDF bookmarks, page indices zero-based, in document order."""
        if self._outline is None:
            entries: list[OutlineEntry] = []
            with self.lock:
                try:
                    toc = self._doc.get_toc(simple=True)
                except Exception as exc:  # noqa: BLE001 - a broken outline is a note, not a failure
                    LOGGER.warning("Sumário do PDF ilegível em %s: %s", self.source_name, exc)
                    toc = []
            for item in toc:
                try:
                    level, title, page = int(item[0]), str(item[1]), int(item[2])
                except (TypeError, ValueError, IndexError):
                    continue
                index = page - 1 if page >= 1 else -1
                if index >= self._page_count:
                    index = -1
                entries.append(OutlineEntry(max(1, level), clean_metadata_text(title), index))
            self._outline = tuple(entries)
        return self._outline

    @property
    def content_hash(self) -> str | None:
        """SHA-256 of the file bytes, for provenance; ``None`` for a stream.

        Lazy: a 143 MB file costs ~0,3 s to hash and most callers never ask.
        """
        if self._content_hash is None and self.path is not None:
            digest = hashlib.sha256()
            with self.path.open("rb") as handle:
                while chunk := handle.read(_HASH_CHUNK):
                    digest.update(chunk)
            self._content_hash = digest.hexdigest()
        return self._content_hash

    # -- pages ------------------------------------------------------------- #

    def check_index(self, index: int) -> int:
        """Validate a page index, in Portuguese, before PyMuPDF does in English."""
        if not 0 <= index < self._page_count:
            raise IndexError(
                f"Página {index} fora do intervalo (0..{self._page_count - 1}) "
                f"em {self.source_name}."
            )
        return index

    def page(self, index: int) -> Any:
        """The raw PyMuPDF page.  Hold :attr:`lock` while using it.

        Not cached on purpose: a ``Page`` keeps its display list and its parsed
        content alive, and caching five hundred of them is exactly the linear
        memory growth the F2 gate forbids.  PyMuPDF itself re-parses a page in
        about a millisecond; the render cache is where the expensive thing is
        kept.
        """
        with self.lock:
            return self._doc[self.check_index(index)]

    def frame(self, index: int) -> PageFrame:
        """The page's coordinate frame, captured once and cached (tiny)."""
        frame = self._frames.get(index)
        if frame is None:
            with self.lock:
                frame = PageFrame.from_page(self._doc[self.check_index(index)], index)
            self._frames[index] = frame
        return frame

    def pages(self, indices: Sequence[int] | None = None) -> Iterator[tuple[int, Any]]:
        """Yield ``(index, page)`` one at a time, under the lock, releasing each.

        The caller must finish with a page before asking for the next; that is
        what keeps a full scan at constant memory.
        """
        wanted = range(self._page_count) if indices is None else indices
        for index in wanted:
            self.check_index(index)
            with self.lock:
                page = self._doc[index]
                yield index, page
                del page

    def sample_indices(self, wanted: int) -> list[int]:
        """Equally spaced page indices avoiding both covers.

        Ported from the trunk's ``pdf_io.sample_pages``: the first and last
        pages of a chess book are cover, index or catalogue, and spending two
        twelfths of a sample on pages that never carry a diagram is waste.
        """
        return sample_indices(self._page_count, wanted)


def sample_indices(page_count: int, wanted: int) -> list[int]:
    """Equally spaced, duplicate-free indices, deterministic (no RNG)."""
    if page_count <= 0 or wanted <= 0:
        return []
    if page_count <= wanted:
        return list(range(page_count))
    step = page_count / (wanted + 1)
    return sorted({min(page_count - 1, round(step * (i + 1))) for i in range(wanted)})


def _path_of(doc: Any) -> Path | None:
    name = getattr(doc, "name", "") or ""
    return Path(name) if name else None


def _validate(doc: Any, name: str) -> None:
    if not getattr(doc, "is_pdf", True):
        kind = ""
        try:
            kind = str((doc.metadata or {}).get("format") or "")
        except Exception:  # noqa: BLE001 - only decorating the message
            kind = ""
        raise PdfOpenError(
            f"{name} não é um PDF"
            + (f" (formato detectado: {kind})" if kind else "")
            + ". Este importador lê apenas PDF; converta o arquivo antes."
        )
    if getattr(doc, "needs_pass", False):
        raise PdfOpenError(
            f"{name} está protegido por senha. Este programa não tem onde pedi-la: "
            "abra o arquivo no leitor de PDF do sistema, salve uma cópia sem senha, "
            "e use a cópia."
        )


def open_pdf(source: Path | str | bytes) -> PdfDocument:
    """Open ``source`` -- a path or raw bytes -- as an owned :class:`PdfDocument`.

    Raises:
        PdfOpenError: for a missing file, a non-PDF, or an encrypted PDF, each
            with a message a user can act on.
    """
    global _opens  # noqa: PLW0603 - the counter is the point of open_count()
    pymupdf = _pymupdf()
    path: Path | None
    if isinstance(source, bytes):
        path = None
        name = "O PDF recebido em memória"
        try:
            doc = pymupdf.open(stream=source, filetype="pdf")
        except Exception as exc:  # MuPDF raises several types for "not a PDF"
            raise PdfOpenError(f"{name} não pôde ser lido como PDF: {exc}") from exc
    else:
        path = Path(source)
        name = path.name
        if not path.is_file():
            raise PdfOpenError(f"O arquivo {path} não existe ou não é um arquivo.")
        try:
            doc = pymupdf.open(str(path))
        except Exception as exc:  # see above
            raise PdfOpenError(f"{name} não pôde ser aberto como PDF: {exc}") from exc
    with _opens_lock:
        _opens += 1
    try:
        _validate(doc, name)
    except PdfOpenError:
        doc.close()
        raise
    return PdfDocument(doc, path=path, owned=True, source_name=name)
