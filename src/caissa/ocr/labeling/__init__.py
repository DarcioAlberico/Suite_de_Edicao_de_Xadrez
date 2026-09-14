"""Human labelling of scanned pages — the missing input of Sol §SOL-0.

The benchmark measures against text the repository could obtain without a
person: PDF text layers checked against the ink, paragraphs typeset by the
benchmark itself, a few authored passages.  None of it is a scan.  This
package is the model of the work that turns a real scan into truth: a
*labelling project* holds pages, each page holds the regions the layout
found (or the reviewer drew), each region holds its lines, and every line
carries what the engine read, how sure it was, what the reviewer decided
and how long it took.

Three consumers, three exports (:mod:`.export`):

* the golden manifest — one ``pdf-scan`` item per finished region, so the
  gates start measuring scans;
* the calibration and the review audit — the ``corrections()`` shape of
  :class:`caissa.ocr.review.ReviewQueue`;
* Tesseract's trainer — one line image plus one ``.gt.txt`` per line, the
  ground-truth layout ``lstmtraining`` consumes (:mod:`caissa.ocr.training`).

The blind partition rule of the manifest applies here unchanged: a region
whose item id hashes to the blind partition never leaves the project as
training or calibration data.  The window is :mod:`.app` (``caissa-rotular``,
Tk, no Qt); everything it needs is in the other modules and testable, and
:mod:`.measure` scores a book's labelled pages before and after its own
fine-tune (:mod:`caissa.ocr.training.books`); :mod:`.queue` says which page
to label next («Próxima que vale», ``caissa-rotular --sugerir``).
"""

from __future__ import annotations

from .model import (
    LabelProject,
    LineLabel,
    LineStatus,
    PageLabels,
    RegionLabel,
    WordHint,
    item_id_for,
    page_key,
)

__all__ = [
    "LabelProject",
    "LineLabel",
    "LineStatus",
    "PageLabels",
    "RegionLabel",
    "WordHint",
    "item_id_for",
    "page_key",
]
