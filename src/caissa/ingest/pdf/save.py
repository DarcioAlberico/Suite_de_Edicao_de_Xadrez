"""Writing a PDF without ever leaving half of one behind, and stopping on request.

Ported from the Editor's ``pdf_service.py`` (sections 43 and 60), absorbed
2026-09-11.  Nothing changed in the mechanism; the measurements that shaped it:

**``doc.save(path)`` writes straight into the user's file.**  Any death in the
middle -- power, task manager, the ``terminate()`` a closing window must be
allowed to issue -- leaves a truncated PDF there, and when the export was over
a previous one, the good file goes with it.  Measured: an abort on the third
``write`` call left **2 bytes** in the destination.  So: partial file next to
the target, ``fsync``, then ``os.replace``.  Next to the target and not in a
system temporary directory because ``os.replace`` is only atomic within one
filesystem, and exporting to a USB stick or a network share is the common
case here.

**PyMuPDF's ``save`` has no cancellation hook, but it accepts a file object**
and calls ``write()`` on it many times.  Measured on a 900-page scanned book
(17,8 MB): **121.495 calls** of about 5 bytes each.  That turns a save that
was atomic from the outside into something that can be abandoned midway.  Two
more measurements explain the details: cancellation is checked every
``CHECK_EVERY`` calls, not on every one (asking 121 thousand times to answer
once is paying in all of them); and the first ``write`` only happens at
**57 % of the save's time** -- MuPDF spends most of it rebuilding the xref
(``garbage=3``) before emitting a byte.  What can be abandoned is the writing
phase, which on a network share is exactly the phase that hurts.

**No ``name`` attribute on the writer.**  A raw ``open(..., "wb")`` handle has
``.name``, and PyMuPDF treats that as having been given a path -- it tries to
remove the file our own handle holds open and fails with ``Permission denied``
on Windows.
"""

from __future__ import annotations

import io
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

__all__ = ["EXPORT_PART_SUFFIX", "ExportCanceled", "save_document_atomically"]

LOGGER = logging.getLogger("caissa.ingest.pdf.save")

#: Suffix of the partial file, written next to the destination.
EXPORT_PART_SUFFIX: Final = ".parte"


class ExportCanceled(RuntimeError):  # noqa: N818 - the Editor's name, kept for its callers
    """The export was stopped on request.  No file was written."""


class _CancelableWriter(io.RawIOBase):
    """A ``save`` destination that honours a stop request."""

    #: How many writes between cancellation checks.
    CHECK_EVERY: Final = 256

    def __init__(self, handle: io.BufferedWriter, should_cancel: Callable[[], bool] | None) -> None:
        super().__init__()
        self._handle = handle
        self._should_cancel = should_cancel
        self._writes = 0
        #: Did the stop come from here?  ``save`` wraps our exception in a
        #: ``FzErrorGeneric``, so the type does not survive the round trip;
        #: the flag does.
        self.canceled = False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return self._handle.seek(offset, whence)

    def tell(self) -> int:
        return self._handle.tell()

    def write(self, data: Any) -> int:
        self._writes += 1
        if (
            self._should_cancel is not None
            and self._writes % self.CHECK_EVERY == 0
            and self._should_cancel()
        ):
            self.canceled = True
            raise ExportCanceled("Exportação cancelada durante a gravação.")
        return self._handle.write(data)


def _discard_part(part: Path) -> None:
    """Remove the partial.  Failing here must not mask the error that led here."""
    try:
        part.unlink(missing_ok=True)
    except OSError:  # pragma: no cover - only if unlink itself fails
        LOGGER.warning("Parcial da exportação não pôde ser removido: %s", part, exc_info=True)


def save_document_atomically(
    doc: Any,
    output_pdf: Path | str,
    *,
    should_cancel: Callable[[], bool] | None = None,
    garbage: int = 3,
    deflate: bool = True,
) -> None:
    """Write ``doc`` to ``output_pdf`` so the destination is never half-written.

    The destination ends with one of two contents, never a third: the previous
    file (or nothing) or the new one, whole.

    Raises:
        ExportCanceled: ``should_cancel`` returned ``True``; nothing was
            published.
    """
    target = Path(output_pdf)
    part = target.with_name(target.name + EXPORT_PART_SUFFIX)
    # Leftover of an export killed before this one.  On Windows the handle of
    # a force-stopped thread is only released when the process exits, so the
    # clean-up that actually works is here, not there.
    _discard_part(part)

    writer: _CancelableWriter | None = None
    try:
        with part.open("wb") as handle:
            writer = _CancelableWriter(handle, should_cancel)
            doc.save(writer, deflate=deflate, garbage=garbage)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # BaseException: a KeyboardInterrupt midway leaves the same debris as
        # an OSError.
        _discard_part(part)
        if writer is not None and writer.canceled:
            raise ExportCanceled(
                "Exportação cancelada durante a gravação. Nenhum arquivo foi gravado."
            ) from None
        raise

    if should_cancel is not None and should_cancel():
        # Got this far, but the stop came before the rename: the destination
        # is untouched, which is what cancellation promises.
        _discard_part(part)
        raise ExportCanceled("Exportação cancelada antes de publicar o arquivo.")
    part.replace(target)
