"""The trunk's page reader as the importer's OCR provider.

The user's words, on the Yusupov export of 2026-10-11: *"exportar o livro para
EPUB não está usando o OCR de glifos de xadrez, que está com excelente
precisão"*.  He was right twice.  The page went out through the damaged text
layer anchored by the fusion (``I.'Wxh6t!``, ``E.Jackson ackson``, the two
columns interleaved), while the trunk's own page reader -- the «Ler folha» of
the Texto tab, ``chess_diagram_ocr.text.leitor.ler_pagina`` with the glyph
classifier -- reads the same page as 72 clean lines in the right columns, with
the figurines as figurines.

So this module hands that reader to the importer as an
:data:`~caissa.ingest.pdf.importer.OcrProvider`: ``(page, frame, verdict) ->
PageText``.  The importer only asks a provider for the pages whose layer is
missing, rejected or damaged (``_decide_source``), so a born-digital book with
a clean layer never comes here; the Yusupov, whose layer is another OCR's
guess, does.

What is kept of the trunk's reading: every line's text, box (the trunk
measures in points of ``page.rect``, the importer's own space), confidence,
bold and italic flags, and the block it belongs to -- one ``block_index`` per
trunk block, column by column, because a block boundary between lines is what
the paragraph builder reads as a paragraph break.  Running head and folio come
along as blocks of their own; the importer's furniture detector classifies
them by position as it does for a text layer.  What is dropped: the trunk's
diagram blocks (the importer finds diagrams by its own finders) and its table
cells (no box per row to give).

The reader is built once per process: the classifier is the trunk's and costs
a second to load.  Without the trunk or its model on this machine
:meth:`TrunkPageReader.build` says why, and the importer falls back to the
service.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import numpy as np

from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan

__all__ = ["TrunkPageReader", "page_text_from_pagina"]

LOGGER = logging.getLogger(__name__)

#: The resolution the trunk's Texto tab reads with by default
#: (``RecognitionSettings.dpi``); its page chain was measured at it.
DEFAULT_DPI = 220

MISSING_TRUNK_PT = (
    "O leitor de página do tronco (ChessVisionOFF_Puro, chess_diagram_ocr.text.leitor) "
    "não está ao alcance."
)

_FIGURINES = "♔♕♖♗♘♙♚♛♜♝♞♟"


def _box(bbox: Any, scale: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(v) for v in bbox)
    if scale != 1.0:
        x0, y0, x1, y1 = x0 * scale, y0 * scale, x1 * scale, y1 * scale
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _spans_of(linha: Any, box: tuple[float, float, float, float], size: float,
              engine: str) -> tuple[TextSpan, ...]:
    """One span per style run of the line.

    The trunk says where the bold and the italic are (``negrito_em`` /
    ``italico_em``, intervals of characters); with no detail the line's own
    flag stands, and ``None`` -- the trunk's "not known" -- is ``False`` here,
    which is what a span without evidence of weight is.
    """
    text = str(getattr(linha, "texto", "") or "")
    confidence = float(getattr(linha, "confianca", 1.0) or 0.0)
    bold_line = bool(getattr(linha, "negrito", None))
    italic_line = bool(getattr(linha, "italico", None))
    bold_runs = tuple(getattr(linha, "negrito_em", ()) or ())
    italic_runs = tuple(getattr(linha, "italico_em", ()) or ())
    if not bold_runs and not italic_runs:
        return (TextSpan(text=text, box=box, size=size, bold=bold_line, italic=italic_line,
                         confidence=confidence, engine=engine),)
    cuts = {0, len(text)}
    for start, end in (*bold_runs, *italic_runs):
        cuts.update((max(0, min(len(text), int(start))), max(0, min(len(text), int(end)))))
    edges = sorted(cuts)
    width = box[2] - box[0]
    spans: list[TextSpan] = []
    for start, end in pairwise(edges):
        if end <= start:
            continue
        piece = text[start:end]
        inside_bold = any(s <= start and end <= e for s, e in bold_runs)
        inside_italic = any(s <= start and end <= e for s, e in italic_runs)
        # A proportional slice of the line box: the trunk has no box per
        # character here, and the paragraph builder only needs the order.
        x0 = box[0] + width * (start / max(1, len(text)))
        x1 = box[0] + width * (end / max(1, len(text)))
        spans.append(TextSpan(
            text=piece, box=(x0, box[1], x1, box[3]), size=size,
            bold=inside_bold or (bold_line and not bold_runs),
            italic=inside_italic or (italic_line and not italic_runs),
            confidence=confidence, engine=engine,
        ))
    return tuple(spans) or (TextSpan(text=text, box=box, size=size, confidence=confidence,
                                     engine=engine),)


def page_text_from_pagina(pagina: Any, frame: PageFrame, *, dpi: float = DEFAULT_DPI,
                          engine: str = "glifo", min_confidence: float = 0.0) -> PageText:
    """The trunk's ``PaginaLida`` as the importer's :class:`PageText`.

    ``pagina.unidade`` is honoured: ``"pt"`` is the importer's space already,
    ``"px"`` is divided by ``dpi / 72``.  A line without a letter, a digit or
    a figurine is not text and is left out -- a blank scan comes back from
    the trunk as one line «— —», and the page with nothing left is declined,
    so the importer keeps it as an image with the reason.  Lines below
    ``min_confidence`` are left out too (see
    :attr:`TrunkPageReader.min_confidence`, off by default).
    """
    unidade = str(getattr(pagina, "unidade", "pt") or "pt")
    scale = 72.0 / float(dpi) if unidade == "px" else 1.0
    lines: list[TextLine] = []
    block = 0

    def add(linha: Any, block_index: int) -> None:
        text = str(getattr(linha, "texto", "") or "")
        if not any(ch.isalnum() or ch in _FIGURINES for ch in text):
            return
        if float(getattr(linha, "confianca", 1.0) or 0.0) < min_confidence:
            return
        box = _box(getattr(linha, "bbox", (0.0, 0.0, 0.0, 0.0)), scale)
        size = max(1.0, box[3] - box[1])
        lines.append(TextLine(box=box, spans=_spans_of(linha, box, size, engine),
                              block_index=block_index))

    columns: list[tuple[float, float, float, float]] = []
    for coluna in getattr(pagina, "colunas", ()) or ():
        bbox = getattr(coluna, "bbox", None)
        if bbox is not None and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
            columns.append(_box(bbox, scale))
        for bloco in getattr(coluna, "blocos", ()) or ():
            linhas = getattr(bloco, "linhas", None)
            if not linhas:
                # Diagram and table blocks: the importer has its own finders
                # for the first, and the second gives no box per row.
                continue
            for linha in linhas:
                add(linha, block)
            block += 1
    for furniture in (getattr(pagina, "cabecalho", None), getattr(pagina, "rodape", None)):
        # The trunk takes the running head and the folio from the text layer
        # (``page_margin_lines``); on a page whose layer is another OCR's
        # guess the glyph has already read the same line in a column, and
        # adding the layer's copy on top gave «S()lut1'()ns :Solutions» and
        # «1 51 5» (the folio twice) on the Yusupov p. 19.  The copy only
        # enters where no line of the page sits already.
        if furniture is None:
            continue
        box = _box(getattr(furniture, "bbox", (0.0, 0.0, 0.0, 0.0)), scale)
        if any(_overlaps(box, line.box) for line in lines):
            continue
        add(furniture, block)
        block += 1
    # One column is no layout to hand over: the importer's own detector is
    # right about a single column, and a hint of one would only silence it.
    hint = tuple(columns) if len(columns) > 1 else ()
    return PageText(frame=frame, lines=tuple(lines), source=engine, columns=hint)


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float],
              share: float = 0.5) -> bool:
    """Do two line boxes share at least ``share`` of the smaller one's height and any width?"""
    dy = min(a[3], b[3]) - max(a[1], b[1])
    if dy <= 0.0:
        return False
    smaller = max(1e-6, min(a[3] - a[1], b[3] - b[1]))
    dx = min(a[2], b[2]) - max(a[0], b[0])
    return dy / smaller >= share and dx > 0.0


@dataclass
class TrunkPageReader:
    """``OcrProvider`` backed by ``chess_diagram_ocr.text.leitor.ler_pagina``.

    Attributes:
        dpi: Resolution the page is rendered at for the reader.
        max_boards: Cap on the trunk's diagram detection per page, which the
            reader uses only to keep the boards' pixels out of the text;
            ``None`` is the trunk's default.
        pages_read: Pages this reader answered, for the import report.
    """

    dpi: int = DEFAULT_DPI
    max_boards: int | None = None
    name: str = "glifo"
    #: Lines the trunk read below this confidence are left out.  Off by
    #: default, and on purpose: the trunk's line confidence is the *minimum*
    #: over its characters, and a line read right with one unsure letter
    #: carries 0,0 («First English edition 2008 by Quality Chess», measured
    #: on the Yusupov p. 6) -- a floor here would throw away good text.
    #: What keeps a blank scan out is :func:`page_text_from_pagina`'s rule
    #: that a line without a letter, a digit or a figurine is not text.
    min_confidence: float = 0.0
    pages_read: list[int] = field(default_factory=list)
    _reader: Any = field(default=None, repr=False)
    _recognizer: Any = field(default=None, repr=False)

    @classmethod
    def build(cls, *, dpi: int = DEFAULT_DPI,
              max_boards: int | None = None) -> tuple[TrunkPageReader | None, str | None]:
        """A reader, or ``(None, why)`` when the trunk or its model is missing.

        The classifier is loaded here, once, so that a book of 2 600 pages
        does not reload it 2 600 times; the trunk's own diagnosis is the
        message when it cannot.
        """
        try:
            from caissa.vision.classify.cvoff import ensure_cvoff_on_path

            ensure_cvoff_on_path()
            from chess_diagram_ocr.text import leitor
            from chess_diagram_ocr.text.recognizer import build_glyph_recognizer
        except FileNotFoundError as exc:
            return None, f"{MISSING_TRUNK_PT} ({exc})"
        except ImportError as exc:
            return None, f"{MISSING_TRUNK_PT} Módulo ausente: {exc}"
        try:
            # The trunk's own variable for its weights (``settings.ENV_OCR_GLYPH_MODEL``),
            # honoured here so that a checkout without ``models/char_classifier.pt`` can
            # point at one; empty lets the trunk look beside its metadata.
            recognizer = build_glyph_recognizer(os.environ.get("CVOFF_OCR_GLYPH_MODEL", ""))
        except Exception as exc:  # noqa: BLE001 - the trunk's own diagnosis is the message
            return None, f"Classificador de glifos do tronco não carregou: {exc}"
        return cls(dpi=dpi, max_boards=max_boards, _reader=leitor, _recognizer=recognizer), None

    def render(self, page: Any) -> np.ndarray:
        """The page as the RGB array the trunk reads, at :attr:`dpi`."""
        import fitz  # PyMuPDF only where the page is in hand

        matrix = fitz.Matrix(self.dpi / 72.0, self.dpi / 72.0)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        raw = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        return np.ascontiguousarray(raw[:, :, :3].copy())

    def __call__(self, page: Any, frame: PageFrame, _verdict: Any = None) -> PageText | None:
        """The ``OcrProvider`` call.

        The verdict is the importer's reason for asking and changes nothing
        here: the trunk reads the whole page.
        """
        if self._reader is None:
            return None
        source = getattr(getattr(page, "parent", None), "name", "") or ""
        if not source:
            LOGGER.warning("Leitor de glifo: página %d sem caminho do PDF; ignorada.", frame.index)
            return None
        pagina = self._reader.ler_pagina(
            source, int(frame.index), dpi=int(self.dpi), motor="glifo",
            reconhecedor=self._recognizer, imagem_rgb=self.render(page),
            max_boards=self.max_boards,
        )
        text = page_text_from_pagina(pagina, frame, dpi=self.dpi, engine=self.name,
                                     min_confidence=self.min_confidence)
        if text.is_empty:
            return None
        self.pages_read.append(int(frame.index))
        return text

    def describe_pt(self) -> str:
        count = len(self.pages_read)
        return (f"{count} página(s) lida(s) pelo leitor de glifo do tronco "
                f"(chess_diagram_ocr.text.leitor, {self.dpi} dpi)")
