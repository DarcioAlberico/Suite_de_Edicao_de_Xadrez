"""The text layer of one page, with styles, in ``page.rect`` points.

What comes out is engine-agnostic on purpose: a :class:`PageText` is lines of
styled spans with boxes, and the paragraph builder that consumes it never
learns whether the spans came from the PDF or from an OCR engine
(:func:`page_text_from_ocr` adapts an :class:`~caissa.ocr.types.OcrResult`).
That is the same rule ``ocr/layout/analyze.py`` follows, for the same reason:
a second copy of the paragraph rules for the OCR path would drift.

Three pieces of PDFimport's ``extract.py`` are absorbed here, with their
measurements:

**Style from three sources, not one.**  PyMuPDF's span ``flags`` are what the
font *declares*; the font *name* (``-Bold``, ``Italic``) is what the producer
meant; and for books whose producer stripped both -- every face renamed
``Type3 (41 0 R)`` -- only the ink can say.  :func:`stroke_bold_fonts` measures
the mean horizontal run length of the ink per font on a sample of pages, and
a face whose runs are ``bold_ratio`` times the body's is bold.  Run length
rather than ink density because it does not care how many spaces or capitals
a span contains.

**Figurine fonts.**  The text layer holds ``N``; the page shows a knight.
Copying that out as ``N`` is what every competitor does and what the SPEC
forbids: the IR carries a :class:`~caissa.core.model.inline.PieceGlyph`, so
the whole book can switch to ``C`` (Portuguese) or to a figurine face without
retyping.  The mapping is by *context*: a capital in a figurine font is a
piece when it stands in notation (``Nf3``, ``Rxe1``, ``R1e2``, ``Nbd7``) or is
an isolated one- or two-letter run; ``"Black's threat"`` set in the figurine
face stays text.  Measured on Thinkers Publishing / Chess Stars books, which
set whole sentences in the SemFig family.

**Informator symbols.**  The Chess Informant symbol fonts park the evaluation
signs on Latin-1 code points, so the layer reads ``¢`` where the page shows
``⩲``.  The table below was read off a book's own SIGNS legend.

Diagram fonts are recognised through the F3-A catalogue and their rows are
marked, not dropped: the vector detector reads the position from them, and
the paragraph builder keeps them out of the prose.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final

from caissa.ingest.pdf.geometry import PageFrame, RectT
from caissa.vision.detect.font_catalog import lookup_family

if TYPE_CHECKING:
    from caissa.ingest.pdf.document import PdfDocument
    from caissa.ocr.types import OcrResult

__all__ = [
    "CIPHER_ORIGIN",
    "FIGURINE_MODEL_ORIGIN",
    "GLYPH_ORIGIN",
    "INFORMATOR_SYMBOLS",
    "FigurineMapper",
    "ImagePlacement",
    "PageText",
    "TextLine",
    "TextSpan",
    "extract_page_text",
    "page_text_from_ocr",
    "stroke_bold_fonts",
]

LOGGER = logging.getLogger("caissa.ingest.pdf.text")

#: The values of :attr:`TextSpan.figurine_origin` (OCR_UI ciclo 2, B10/G7):
#: the glyph reader (its engine name, ``caissa.ocr.engines.glyph.ENGINE_NAME``),
#: the book's fine-tuned figurine model (``ocr_service.FIGURINE_ENGINE``) --
#: both *readings* of the page -- and the book cipher, an inference.
GLYPH_ORIGIN: Final = "glyph"
FIGURINE_MODEL_ORIGIN: Final = "tesseract_figurine"
CIPHER_ORIGIN: Final = "cifra"

# PyMuPDF span flag bits.
_F_SUPERSCRIPT: Final = 1
_F_ITALIC: Final = 2
_F_MONO: Final = 8
_F_BOLD: Final = 16

_BOLD_NAME: Final = re.compile(r"bold|black|heavy|semib|demi", re.IGNORECASE)
_ITALIC_NAME: Final = re.compile(r"italic|oblique", re.IGNORECASE)

#: Figurine font names seen in the wild.  ``chess(?!board)`` catches the older
#: TrueType families; the negative lookahead keeps ``Chessboard`` (a diagram
#: font) out.  Ported from PDFimport ``chessfig.py``.
_FIGURINE_FONT: Final = re.compile(
    r"semfig|figurine|figurin|chessfig|chessbase|diagramttf|dgt"
    r"|linares|marroquin|zurich|berlin|cheq|chess(?!board)",
    re.IGNORECASE,
)
_INFORMATOR_FONT: Final = re.compile(r"informator|informant", re.IGNORECASE)

#: Piece letters to the outline Unicode set.  One figurine per piece regardless
#: of colour, as chess books print them.
_OUTLINE: Final[Mapping[str, str]] = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
}
#: A capital is a piece when notation follows it: a square (``Na3``), a
#: capture (``Rxe1``), a rank disambiguation (``R1e2``) or a file (``Nbd7``).
_NOTATION_AFTER: Final = re.compile(r"^(?:[a-h](?:[1-8x]|[a-h]?[1-8])|x[a-h]|[1-8][a-h])")
_MAX_ISOLATED_FIGURINE: Final = 2

INFORMATOR_SYMBOLS: Final[Mapping[str, str]] = {
    "¢": "⩲",
    "£": "⩱",
    "¥": "±",
    "¤": "∓",
    "»": "−",
    "ú": "=",
    "Õ": "∞",
    "§": "©",
    "¶": "⇑",
    "ï": "→",
    "î": "↑",
    "|": "⇆",
    "Â": "⊙",
    "Å": "△",
    "ì": "□",
    "Ä": "⌓",
    "‹": "≤",
    "°": "⊕",
    "Á": "◻",
    "À": "◼",
}

_MIN_IMAGE_SIDE_PT: Final = 3.0
_MIN_RULE_LENGTH_FRAC: Final = 0.08
_MAX_RULE_THICKNESS_PT: Final = 2.5
#: A drawing wider than this share of the page is a frame, not a rule.
_MAX_RULE_LENGTH_FRAC: Final = 0.98

# Stroke-bold measurement (PDFimport ``_stroke_bold_fonts``).
_BOLD_DPI: Final = 100
_BOLD_RATIO: Final = 1.35
_BOLD_SAMPLE_PAGES: Final = 6
_BOLD_MIN_RUNS: Final = 200
_BOLD_MIN_CHARS: Final = 150
_INK_THRESHOLD: Final = 160
_INK_TABLE: Final = bytes(1 if i < _INK_THRESHOLD else 0 for i in range(256))
#: A paper pixel followed by an ink pixel: the start of one horizontal run.
_RUN_START: Final = bytes([0, 1])


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TextSpan:
    """A run of characters sharing one style.

    Attributes:
        text: The characters, figurines already mapped to Unicode pieces.
        box: Bounding box in ``page.rect`` points.
        font: Bare font name (subset prefix removed).
        size: Font size in points.
        bold: Declared, named, or ink-measured bold.
        italic: Declared or named italic.
        superscript: Raised, smaller run -- a footnote mark, an ordinal.
        monospace: Fixed-pitch face.
        color: ``0xRRGGBB``.
        figurine: True when ``text`` holds mapped piece glyphs.
        diagram_font: F3-A catalogue key when the span is set in a diagram
            font (board glyphs, not prose).
        baseline: Baseline ``y`` in ``page.rect`` points.
        confidence: ``1.0`` for a text layer; the engine's value for OCR.
        engine: The OCR engine that read the span (Sol §SOL-10); empty for
            the text layer.
        figurine_origin: Who put the figurine in the span (OCR_UI ciclo 2,
            B10/G7): the glyph reader (``"glyph"``), the book's figurine
            model, or the book cipher (``"cifra"``, an inference, not a
            reading); empty when the region's own engine read it, or for
            the text layer.  ``engine`` stays the engine that read the
            *words* -- a block's provenance is the OCR's, not the reader's.
        review: The span comes from a region the OCR decision sent to
            review (Sol §SOL-2); the IR marks it and the reviewer sees it.
        verified: A person settled the region the span comes from
            (OCR_UI_ROADMAP passo 14); the IR carries ``verified_by_human``.
    """

    text: str
    box: RectT
    font: str = ""
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    superscript: bool = False
    monospace: bool = False
    color: int = 0
    figurine: bool = False
    diagram_font: str | None = None
    baseline: float = 0.0
    confidence: float = 1.0
    engine: str = ""
    figurine_origin: str = ""
    review: bool = False
    verified: bool = False

    def same_style(self, other: TextSpan) -> bool:
        return (
            self.bold == other.bold
            and self.italic == other.italic
            and self.superscript == other.superscript
            and self.monospace == other.monospace
            and self.figurine == other.figurine
            and self.font == other.font
            and self.diagram_font == other.diagram_font
            and abs(self.size - other.size) < 0.05  # noqa: PLR2004 - a twentieth of a point
            and self.color == other.color
        )


@dataclass(frozen=True, slots=True)
class TextLine:
    """One line as the producer emitted it.

    Attributes:
        box: Bounding box in ``page.rect`` points.
        spans: The styled runs, left to right.
        block_index: Producer block the line came from -- kept because a
            block boundary that falls *between* lines is evidence of a
            paragraph break and one that falls *inside* a line is not.
        vertical: True for a vertical writing mode line.
        direction: Unit vector of the writing direction, in text space.
    """

    box: RectT
    spans: tuple[TextSpan, ...]
    block_index: int = 0
    vertical: bool = False
    direction: tuple[float, float] = (1.0, 0.0)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def size(self) -> float:
        return max((s.size for s in self.spans), default=0.0)

    @property
    def is_diagram(self) -> bool:
        """Every non-blank span is set in a diagram font."""
        inked = [s for s in self.spans if s.text.strip()]
        return bool(inked) and all(s.diagram_font for s in inked)

    @property
    def confidence(self) -> float:
        inked = [s for s in self.spans if s.text.strip()]
        return min((s.confidence for s in inked), default=1.0)


@dataclass(frozen=True, slots=True)
class ImagePlacement:
    """Where a raster image is drawn on the page.

    Attributes:
        box: Drawn extent in ``page.rect`` points.
        xref: Object number of the image, ``0`` for an inline image.
        width: Stored width in pixels.
        height: Stored height in pixels.
        flipped: True when the placement matrix draws the stored rows bottom
            up -- the reader sees the image upside down relative to storage.
        axis_aligned: False for a rotated or skewed placement, which must be
            repainted by rendering the region rather than exported as stored.
    """

    box: RectT
    xref: int = 0
    width: int = 0
    height: int = 0
    flipped: bool = False
    axis_aligned: bool = True

    @property
    def area(self) -> float:
        return max(0.0, self.box[2] - self.box[0]) * max(0.0, self.box[3] - self.box[1])


@dataclass(frozen=True, slots=True)
class PageText:
    """Everything the page's content stream says, ready for layout.

    Attributes:
        frame: The page's coordinate frame.
        lines: Text lines, in producer order (not reading order).
        images: Raster placements.
        rules: Thin horizontal vector rules -- the footnote separator, the
            line under a running head.
        source: ``"pdf-text-layer"`` or the OCR engine name.
        fonts: Bare font names seen, with character counts.
    """

    frame: PageFrame
    lines: tuple[TextLine, ...] = ()
    images: tuple[ImagePlacement, ...] = ()
    rules: tuple[RectT, ...] = ()
    source: str = "pdf-text-layer"
    fonts: Mapping[str, int] = field(default_factory=dict)

    @property
    def page_index(self) -> int:
        return self.frame.index

    @property
    def char_count(self) -> int:
        return sum(1 for line in self.lines for ch in line.text if not ch.isspace())

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def is_empty(self) -> bool:
        return self.char_count == 0


# --------------------------------------------------------------------------- #
# Figurine mapping
# --------------------------------------------------------------------------- #


class FigurineMapper:
    """Rewrites figurine-font characters to Unicode piece symbols.

    Stateful only for the counters, which the import report prints.
    """

    def __init__(self, extra_fonts: Iterable[str] = ()) -> None:
        self._extra = tuple(f.strip().lower() for f in extra_fonts if f.strip())
        self.seen_fonts: set[str] = set()
        self.count = 0
        self.informator_count = 0

    def is_figurine(self, font: str) -> bool:
        if not font:
            return False
        if _FIGURINE_FONT.search(font):
            return True
        low = font.lower()
        return any(e in low for e in self._extra)

    @staticmethod
    def is_informator(font: str) -> bool:
        return bool(font) and bool(_INFORMATOR_FONT.search(font))

    def map_text(self, text: str, font: str) -> str:
        """Piece capitals to figurines, by context; everything else unchanged."""
        self.seen_fonts.add(font)
        stripped = text.strip()
        isolated = 0 < len(stripped) <= _MAX_ISOLATED_FIGURINE and all(
            c in _OUTLINE for c in stripped
        )
        out: list[str] = []
        for i, ch in enumerate(text):
            sym = _OUTLINE.get(ch)
            if sym is not None and (isolated or _NOTATION_AFTER.match(text[i + 1 : i + 4])):
                out.append(sym)
                self.count += 1
            else:
                out.append(ch)
        return "".join(out)

    def map_informator(self, text: str, font: str) -> str:
        self.seen_fonts.add(font)
        out: list[str] = []
        for ch in text:
            sym = INFORMATOR_SYMBOLS.get(ch)
            if sym is None:
                out.append(ch)
            else:
                out.append(sym)
                self.informator_count += 1
        return "".join(out)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def _bare_font(name: str) -> str:
    return (name or "").split("+", 1)[-1]


def _rect_of(raw: Sequence[float] | None) -> RectT:
    """A four-float tuple from whatever sequence PyMuPDF handed back."""
    if not raw or len(raw) < 4:  # noqa: PLR2004 - four edges
        return (0.0, 0.0, 0.0, 0.0)
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))


def _span_from_dict(
    span: Mapping[str, Any],
    frame: PageFrame,
    mapper: FigurineMapper,
    bold_fonts: frozenset[str],
) -> TextSpan | None:
    text = str(span.get("text", "") or "")
    if not text:
        return None
    # MuPDF reports the space glyph of an embedded TrueType face as U+00A0
    # (measured with Times New Roman via ``insert_text``); a no-break space
    # the book meant is indistinguishable from it, and neither must glue two
    # words together when the paragraph is rebuilt.
    text = text.replace(" ", " ")
    font = _bare_font(str(span.get("font", "") or ""))
    flags = int(span.get("flags", 0) or 0)
    size = float(span.get("size", 0.0) or 0.0)

    diagram_font: str | None = None
    family = lookup_family(font) if font else None
    if family is not None and family.kind == "diagram":
        diagram_font = family.key

    figurine = False
    if diagram_font is None and mapper.is_figurine(font):
        mapped = mapper.map_text(text, font)
        figurine = mapped != text
        text = mapped
    if diagram_font is None and mapper.is_informator(font):
        mapped = mapper.map_informator(text, font)
        figurine = figurine or mapped != text
        text = mapped

    box = frame.text_to_page(_rect_of(span.get("bbox")))
    raw_box = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
    origin = span.get("origin") or (raw_box[0], raw_box[3])
    _, baseline = frame.text_point_to_page(float(origin[0]), float(origin[1]))

    return TextSpan(
        text=text,
        box=box,
        font=font,
        size=size,
        bold=bool(flags & _F_BOLD) or bool(_BOLD_NAME.search(font)) or font in bold_fonts,
        italic=bool(flags & _F_ITALIC) or bool(_ITALIC_NAME.search(font)),
        superscript=bool(flags & _F_SUPERSCRIPT),
        monospace=bool(flags & _F_MONO),
        color=int(span.get("color", 0) or 0),
        figurine=figurine,
        diagram_font=diagram_font,
        baseline=baseline,
    )


def _merge_spans(spans: Sequence[TextSpan]) -> tuple[TextSpan, ...]:
    """Collapse neighbouring spans that share a style, keeping the union box."""
    out: list[TextSpan] = []
    for span in spans:
        if not span.text:
            continue
        if out and out[-1].same_style(span):
            prev = out[-1]
            box = (
                min(prev.box[0], span.box[0]),
                min(prev.box[1], span.box[1]),
                max(prev.box[2], span.box[2]),
                max(prev.box[3], span.box[3]),
            )
            out[-1] = replace(prev, text=prev.text + span.text, box=box)
        else:
            out.append(span)
    return tuple(out)


def _inherit_bold(spans: tuple[TextSpan, ...]) -> tuple[TextSpan, ...]:
    """A one- or two-letter run wedged between bold neighbours is bold too.

    Books that set the piece letter in a separate chess font leave that font
    out of the weight measurement -- a handful of characters is not enough to
    judge a face by -- so the letter would stay light in the middle of an
    otherwise bold main line.
    """
    if len(spans) < 3:  # noqa: PLR2004 - needs a left and a right neighbour
        return spans
    out = list(spans)
    for i in range(1, len(out) - 1):
        run = out[i]
        if run.bold:
            continue
        text = run.text.strip()
        if not text or len(text) > _MAX_ISOLATED_FIGURINE:
            continue
        before, after = out[i - 1], out[i + 1]
        if before.bold and after.bold and run.font != before.font:
            out[i] = replace(run, bold=True)
    return tuple(out)


def _text_flags() -> int:
    import pymupdf

    # Expand ligatures ("fi" -> "f" "i"): the IR carries plain text and the
    # typesetter re-forms them.  Keep whitespace: a producer that emits real
    # space glyphs is telling us where the words are.  No images: they are
    # read through get_image_info, which knows the placement matrix.
    flags = int(pymupdf.TEXTFLAGS_DICT)
    flags &= ~int(pymupdf.TEXT_PRESERVE_LIGATURES)
    flags &= ~int(pymupdf.TEXT_PRESERVE_IMAGES)
    return flags


def _orientation(matrix: Sequence[float] | None) -> tuple[bool, bool]:
    """``(axis_aligned, flipped)`` of an image placement matrix.

    The placement matrix maps the unit square to the image's spot.  Its second
    column decides the vertical direction: a negative ``d`` means the first
    stored row is drawn at the bottom.  Anything with shear is not axis
    aligned.
    """
    if not matrix or len(matrix) < 4:  # noqa: PLR2004 - a, b, c, d at least
        return True, False
    a, b, c, d = matrix[0], matrix[1], matrix[2], matrix[3]
    eps = 1e-4
    if abs(b) > eps or abs(c) > eps or abs(a) < eps or abs(d) < eps:
        return False, False
    return True, d < 0


def _images(page: Any, frame: PageFrame) -> tuple[ImagePlacement, ...]:
    out: list[ImagePlacement] = []
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:  # noqa: BLE001 - a broken image list is a note, not a failure
        return ()
    for item in infos:
        raw = item.get("bbox")
        if raw is None:
            LOGGER.debug("Imagem sem caixa na página %d ignorada: %r", frame.index, item)
            continue
        box = frame.text_to_page(_rect_of(raw))
        if box[2] - box[0] < _MIN_IMAGE_SIDE_PT or box[3] - box[1] < _MIN_IMAGE_SIDE_PT:
            continue
        aligned, flipped = _orientation(item.get("transform"))
        out.append(
            ImagePlacement(
                box=box,
                xref=int(item.get("xref") or 0),
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                flipped=flipped,
                axis_aligned=aligned,
            )
        )
    return tuple(out)


def _rules(page: Any, frame: PageFrame) -> tuple[RectT, ...]:
    """Thin horizontal strokes wide enough to be a rule and not a frame."""
    try:
        drawings = page.get_drawings()
    except Exception:  # noqa: BLE001 - drawings are optional evidence
        return ()
    out: list[RectT] = []
    min_len = _MIN_RULE_LENGTH_FRAC * frame.text_width
    max_len = _MAX_RULE_LENGTH_FRAC * frame.text_width
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = float(rect.width)
        height = float(rect.height)
        if height <= _MAX_RULE_THICKNESS_PT and min_len <= width <= max_len:
            out.append(frame.text_to_page(_rect_of((rect.x0, rect.y0, rect.x1, rect.y1))))
    return tuple(out)


def _line_from_dict(
    line: Mapping[str, Any],
    block_index: int,
    frame: PageFrame,
    mapper: FigurineMapper,
    bold_fonts: frozenset[str],
    fonts: dict[str, int],
) -> TextLine | None:
    spans: list[TextSpan] = []
    for raw in line.get("spans", []):
        span = _span_from_dict(raw, frame, mapper, bold_fonts)
        if span is None:
            continue
        spans.append(span)
        if span.text.strip():
            fonts[span.font] = fonts.get(span.font, 0) + sum(
                1 for c in span.text if not c.isspace()
            )
    merged = _inherit_bold(_merge_spans(spans))
    if not merged or not "".join(s.text for s in merged).strip():
        return None
    direction = line.get("dir") or (1.0, 0.0)
    return TextLine(
        box=frame.text_to_page(_rect_of(line.get("bbox"))),
        spans=merged,
        block_index=block_index,
        vertical=int(line.get("wmode", 0) or 0) == 1,
        direction=(float(direction[0]), float(direction[1])),
    )


def _split_mixed(line: TextLine) -> list[TextLine]:
    """A line mixing diagram glyphs with other text becomes two lines.

    The Polgar sets the rank digit and the eight board glyphs of a row on one
    baseline, and PyMuPDF hands them back as one line (``80ZQZ0Z0Z``).  Kept
    whole it is neither a board row nor a label, and it walked into the prose
    as a paragraph.  Split, the glyphs are a diagram row and the digit is the
    axis label the layout already knows how to drop.
    """
    inked = [s for s in line.spans if s.text.strip()]
    if not inked or all(s.diagram_font for s in inked) or not any(s.diagram_font for s in inked):
        return [line]
    board = tuple(s for s in line.spans if s.diagram_font)
    other = tuple(s for s in line.spans if not s.diagram_font and s.text.strip())
    out: list[TextLine] = []
    for spans in (board, other):
        if not spans:
            continue
        box = spans[0].box
        for span in spans[1:]:
            box = (
                min(box[0], span.box[0]),
                min(box[1], span.box[1]),
                max(box[2], span.box[2]),
                max(box[3], span.box[3]),
            )
        out.append(replace(line, box=box, spans=spans))
    return out


def extract_page_text(
    page: Any,
    frame: PageFrame,
    *,
    mapper: FigurineMapper | None = None,
    bold_fonts: frozenset[str] = frozenset(),
    with_images: bool = True,
    with_rules: bool = True,
) -> PageText:
    """Read one page's text layer.  The caller holds the document lock."""
    mapper = mapper or FigurineMapper()
    try:
        data = page.get_text("dict", flags=_text_flags())
    except Exception as exc:  # noqa: BLE001 - MuPDF raises several types on a corrupt stream
        LOGGER.warning("Camada de texto ilegível na página %d: %s", frame.index, exc)
        data = {"blocks": []}

    lines: list[TextLine] = []
    fonts: dict[str, int] = {}
    for block_index, block in enumerate(data.get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            built = _line_from_dict(line, block_index, frame, mapper, bold_fonts, fonts)
            if built is not None:
                lines.extend(_split_mixed(built))

    return PageText(
        frame=frame,
        lines=tuple(lines),
        images=_images(page, frame) if with_images else (),
        rules=_rules(page, frame) if with_rules else (),
        source="pdf-text-layer",
        fonts=fonts,
    )


def page_text_from_ocr(result: OcrResult, frame: PageFrame, *, dpi: float) -> PageText:
    """Adapt an OCR result (pixel boxes at ``dpi``) into the same shape.

    No styles: an OCR engine reports words, not faces.  Confidence is kept per
    line, which is what the IR provenance needs.
    """
    lines: list[TextLine] = []
    for index, line in enumerate(result.lines):
        text = line.text
        if not text.strip():
            continue
        px = (line.box.x0, line.box.y0, line.box.x1, line.box.y1)
        box = frame.pixels_to_page(px, dpi)
        size = (line.font_size / frame.scale_for(dpi)) if line.font_size else (box[3] - box[1])
        lines.append(
            TextLine(
                box=box,
                spans=(
                    TextSpan(
                        text=text,
                        box=box,
                        size=size,
                        baseline=box[3],
                        confidence=float(line.confidence),
                    ),
                ),
                block_index=int(line.block_index) if line.block_index >= 0 else index,
            )
        )
    return PageText(frame=frame, lines=tuple(lines), source=result.engine or "ocr")


# --------------------------------------------------------------------------- #
# Ink-measured bold
# --------------------------------------------------------------------------- #


_SpanBoxes = list[tuple[str, Sequence[float]]]


def _sample_page_ink(
    document: PdfDocument, index: int, dpi: int, chars: dict[str, int]
) -> tuple[_SpanBoxes, bytes, int, int, int] | None:
    """The spans of one page plus its grey raster, or ``None`` to skip it."""
    import pymupdf

    with document.locked() as doc:
        page = doc[index]
        spans: _SpanBoxes = []
        for block in page.get_text("dict", flags=_text_flags()).get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    name = _bare_font(str(span.get("font", "")))
                    spans.append((name, span["bbox"]))
                    chars[name] = chars.get(name, 0) + len(text.strip())
        if not spans:
            return None
        try:
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
        except Exception as exc:  # noqa: BLE001 - a page that will not render is skipped
            LOGGER.debug("Página %d não renderizou para medir negrito: %s", index, exc)
            return None
        return spans, bytes(pix.samples), int(pix.stride), int(pix.width), int(pix.height)


def _accumulate_runs(
    sample: tuple[_SpanBoxes, bytes, int, int, int],
    scale: float,
    totals: dict[str, list[int]],
) -> None:
    spans, data, stride, width, height = sample
    for name, box in spans:
        x0, x1 = max(0, int(box[0] * scale)), min(width, int(box[2] * scale) + 1)
        y0, y1 = max(0, int(box[1] * scale)), min(height, int(box[3] * scale) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        acc = totals.setdefault(name, [0, 0])
        for y in range(y0, y1):
            base = y * stride
            row = data[base + x0 : base + x1].translate(_INK_TABLE)
            ink = row.count(1)
            if not ink:
                continue
            acc[0] += ink
            acc[1] += row.count(_RUN_START) + (1 if row[0] else 0)


def stroke_bold_fonts(
    document: PdfDocument,
    pages: Sequence[int],
    *,
    sample_pages: int = _BOLD_SAMPLE_PAGES,
    dpi: int = _BOLD_DPI,
    ratio: float = _BOLD_RATIO,
) -> frozenset[str]:
    """Font names whose stems are thick enough to be a bold face.

    Ported from PDFimport ``_stroke_bold_fonts``.  Samples the middle of the
    range (front matter is unrepresentative), renders each sample in grey,
    and for every font measures mean horizontal ink-run length inside its
    spans.  The body face is the one with the most characters; a face whose
    runs are ``ratio`` times longer is bold.
    """
    if len(pages) < 2:  # noqa: PLR2004 - one page cannot compare two faces
        return frozenset()
    start = pages[len(pages) // 5]
    end = pages[-1]
    want = max(1, sample_pages)
    step = max(1, (end - start) // want)
    sample = list(range(start, end + 1, step))[:want] or [pages[0]]

    scale = dpi / 72.0
    totals: dict[str, list[int]] = {}
    chars: dict[str, int] = {}
    for index in sample:
        page_sample = _sample_page_ink(document, index, dpi, chars)
        if page_sample is not None:
            _accumulate_runs(page_sample, scale, totals)

    usable = {
        n: t[0] / float(t[1])
        for n, t in totals.items()
        if t[1] >= _BOLD_MIN_RUNS and chars.get(n, 0) >= _BOLD_MIN_CHARS
    }
    if len(usable) < 2:  # noqa: PLR2004 - a body face and at least one other
        return frozenset()
    body = max(usable, key=lambda n: chars[n])
    base = usable[body]
    if base <= 0:
        return frozenset()
    bold = {n for n, v in usable.items() if v / base >= ratio}
    bold.discard(body)
    if bold:
        LOGGER.info(
            "Negrito por espessura de traço: %s",
            ", ".join(f"{n} ({usable[n] / base:.2f}x)" for n in sorted(bold))[:200],
        )
    return frozenset(bold)
