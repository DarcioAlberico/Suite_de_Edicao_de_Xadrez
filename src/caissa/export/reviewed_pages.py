"""The pages corrected in the *Revisão de texto* window, for the trunk's notebook (R7 de volta).

The trunk (ChessVisionOFF) sends the pages corrected in its *Texto* tab to the book the suite
writes (:mod:`caissa.export.page_texts`).  This is the other way: the regions a reviewer edited
in the suite reach the trunk's notebook, so a correction made on either side is not lost on the
other.  What the trunk does with them -- the notebook's own correction wins, and the suite's goes
to the page's *anterior* -- is the trunk's rule, in its ``text/caderno_na_suite.py``.

**Which pages.**  The ones with at least one region the reviewer **edited**
(:attr:`~caissa.ocr.review.Action.EDIT`): only an edit puts words that are not the machine's on
the page.  Accepting a reading changes nothing in the text, and a region kept as an image has no
words to send.

**From which import.**  The decisions live in their own file and reach the document only through
an import that applies them.  The window's import in hand is used when it built those pages and
saw these decisions (its ``review_decisions_digest``, the same check the export makes); otherwise
those pages -- and only those -- are imported again, with the options the export would use.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from caissa.export.book import _import_options, _review_changed
from caissa.export.page_texts import page_texts_of
from caissa.ingest.pdf import ImportResult, import_pdf

__all__ = ["ReviewedPages", "edited_pages", "reviewed_page_texts"]


@dataclass(frozen=True, slots=True)
class ReviewedPages:
    """What :func:`reviewed_page_texts` found: the pages in the trunk's format, and how."""

    page_texts: tuple[dict[str, Any], ...] = ()
    pages: tuple[int, ...] = ()
    reimported: bool = False
    """Whether the pages were imported again, because the import in hand did not serve."""


def edited_pages(decisions: Any) -> dict[int, str]:
    """``page -> when it was last edited`` for the pages with an edited region. Pure."""
    from caissa.ocr.review import Action

    pages: dict[int, str] = {}
    for entry in getattr(decisions, "entries", ()) or ():
        if entry.action is not Action.EDIT:
            continue
        index = int(entry.page_index)
        pages[index] = max(pages.get(index, ""), entry.at or "")
    return pages


def _serves(document: Any, source: Path, pages: Sequence[int]) -> bool:
    """Whether the import in hand built every page asked for and saw the decisions of now."""
    if not isinstance(document, ImportResult) or getattr(document.report, "canceled", False):
        return False
    built = {int(p.index) for p in getattr(document.report, "pages", ())}
    if not set(pages) <= built:
        return False
    # The digest the import recorded is over the pages it built; the decisions of now, over the
    # same pages, must give the same digest.
    return not _review_changed(document, source, None, sorted(built))


def reviewed_page_texts(
    pdf_path: Path | str,
    *,
    document: Any = None,
    progress: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ReviewedPages:
    """The pages a reviewer edited, in the trunk's format, from an import that applied the edits.

    ``document`` is the window's :class:`ImportResult` in hand, when there is one.  With no
    edited page there is nothing to import, and the answer is empty.
    """
    from caissa.ocr.review import ReviewDecisions

    source = Path(pdf_path)
    decisions = ReviewDecisions.for_pdf(source)
    edited = edited_pages(decisions)
    pages = sorted(edited)
    if not pages:
        return ReviewedPages()
    if _serves(document, source, pages):
        imported, reimported = document, False
    else:
        with tempfile.TemporaryDirectory(prefix="caissa-revisadas-") as scratch:
            options = _import_options(
                source,
                None,
                pages,
                enable_ocr=None,
                progress=progress or (lambda _done, _total: None),
                should_cancel=should_cancel,
                scratch=Path(scratch),
            )
            options.review_decisions = decisions
            imported, reimported = import_pdf(source, options), True
    if getattr(imported.report, "canceled", False):
        return ReviewedPages(pages=tuple(pages), reimported=reimported)
    texts = page_texts_of(imported, pages, saved_at=edited)
    return ReviewedPages(page_texts=tuple(texts), pages=tuple(pages), reimported=reimported)
