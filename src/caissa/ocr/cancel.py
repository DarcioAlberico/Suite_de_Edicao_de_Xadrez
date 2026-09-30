"""Cancellation that reaches inside a page — OCR_UI_ROADMAP_C2 passo B9.

The importer checked for cancellation **between** pages
(``PdfImporter._check_cancel``), and inside one page up to eight Tesseract
invocations of up to 180 s each ran to the end whatever the user pressed
(``OCR_UI_ANALISE_C2.md`` §4.8).  This module is the hook they now consult.

The hook travels as a :class:`~contextvars.ContextVar`, not a global: the
importer sets it for the duration of one import (:func:`cancellable`), the
service's worker threads inherit it through ``contextvars.copy_context``,
and two imports in one process (the window importing while a benchmark
runs) never see each other's hook.  An engine that is in the middle of a
subprocess polls :func:`should_cancel` while it waits and kills the child;
a loop over candidates calls :func:`check_cancel` between them.

:class:`OcrCanceled` derives from :class:`BaseException` on purpose, like
``KeyboardInterrupt``: every ``except Exception`` on the OCR path exists so
that *one candidate failing never fails the page*, and a cancellation is not
a failing candidate — it must fall through all of them to the importer, which
turns it into its own :class:`~caissa.ingest.pdf.importer.ImportCanceled`
with the partial document in hand.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = ["OcrCanceled", "cancellable", "check_cancel", "current_hook", "should_cancel"]


class OcrCanceled(BaseException):  # noqa: N818 - a signal, not an error, like KeyboardInterrupt
    """Raised inside the OCR when the caller's hook said to stop."""


_HOOK: ContextVar[Callable[[], bool] | None] = ContextVar("caissa_ocr_should_cancel",
                                                           default=None)


def current_hook() -> Callable[[], bool] | None:
    return _HOOK.get()


def should_cancel() -> bool:
    """Whether the caller of the current context asked to stop."""
    hook = _HOOK.get()
    return bool(hook is not None and hook())


def check_cancel() -> None:
    """Raise :class:`OcrCanceled` when the caller asked to stop."""
    if should_cancel():
        raise OcrCanceled("OCR cancelado a pedido do chamador.")


@contextmanager
def cancellable(hook: Callable[[], bool] | None) -> Iterator[None]:
    """Make ``hook`` the cancellation hook of this context for the block."""
    token = _HOOK.set(hook)
    try:
        yield
    finally:
        _HOOK.reset(token)
