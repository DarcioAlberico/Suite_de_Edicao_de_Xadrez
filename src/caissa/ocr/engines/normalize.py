"""What every engine's text goes through before it leaves the engine (OCR_UI ciclo 2, B12).

Tesseract emits the typographic ligatures it sees -- ``ﬁ`` (U+FB01), ``ﬂ``, ``ﬀ``, ``ﬃ``,
``ﬄ``, ``ﬅ``, ``ﬆ`` -- and the IR kept them: the benchmark's metric normalises with NFKC
and never saw them, the EPUB, the search index and the notation grammar did.  This module
folds **only** the ligatures, at the boundary, for every engine.

**Why not NFKC.**  NFKC also turns ``½`` into ``1⁄2`` (the draw result), ``²`` into ``2``
(an Informator NAG), ``№`` into ``No`` and fullwidth digits into ASCII -- changes the chess
grammar and the reviewer would notice.  A folding table is small, explicit and testable.
"""

from __future__ import annotations

from dataclasses import replace

from caissa.ocr.types import OcrLine, OcrResult, OcrWord

__all__ = ["LIGATURES", "fold_ligatures", "fold_result", "text_layer_flags"]

LIGATURES: dict[str, str] = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "ft",
    "ﬆ": "st",
}
_TABLE = str.maketrans(LIGATURES)


def fold_ligatures(text: str) -> str:
    """``ﬁnal`` → ``final``; everything else untouched."""
    return text.translate(_TABLE) if text else text


def fold_result(result: OcrResult) -> OcrResult:
    """The same result with every word's text folded.

    Returns the input object when nothing changes, so the common case allocates nothing.
    """
    changed = False
    lines: list[OcrLine] = []
    for line in result.lines:
        words: list[OcrWord] = []
        line_changed = False
        for word in line.words:
            folded = fold_ligatures(word.text)
            if folded != word.text:
                words.append(replace(word, text=folded))
                line_changed = True
            else:
                words.append(word)
        if line_changed:
            lines.append(replace(line, words=tuple(words)))
            changed = True
        else:
            lines.append(line)
    if not changed:
        return result
    return replace(result, lines=tuple(lines))


#: PyMuPDF's own default flags per extraction mode -- the ones ``page.get_text(mode)``
#: uses when it is given none.
_MODE_FLAGS = {"text": "TEXTFLAGS_TEXT", "dict": "TEXTFLAGS_DICT", "rawdict": "TEXTFLAGS_RAWDICT",
               "words": "TEXTFLAGS_WORDS", "blocks": "TEXTFLAGS_BLOCKS"}


def text_layer_flags(mode: str = "text") -> int:
    """``page.get_text(mode)``'s default flags **without** ``TEXT_PRESERVE_LIGATURES`` (A14).

    The engines' output folds at :func:`fold_result`; a PDF's text layer is read by
    PyMuPDF, and MuPDF expands a ligature into its letters -- ``ﬁ`` into ``f`` and ``i``,
    the box split between them -- when the flag is off.  The importer's extractor
    (``ingest.pdf.textlayer._text_flags``) has always read that way; the level-0 engine,
    the layout's page lines and the search index read with the defaults, and the Polgar
    carried 19 ligatures into them (``OCR_UI_REPORT_C2_FASE5.md`` §A14).  Everything else
    in the flags is the mode's default, so nothing but the ligatures changes.
    """
    import pymupdf

    return int(getattr(pymupdf, _MODE_FLAGS[mode])) & ~int(pymupdf.TEXT_PRESERVE_LIGATURES)
