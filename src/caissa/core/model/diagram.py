"""The ``Diagram`` block: a diagram as a position, not as an image (SPEC 5.3).

This is the node the whole product turns on. Treating a diagram as a FEN plus
provenance plus style -- rather than as a bitmap -- is what makes reflowable
EPUB, crisp vector output at any zoom, search by position inside a book, a
global chess-font swap and notation translation all possible from one edit.

Three records hang off it and each answers a different question:

``DiagramSource``
    *Where did this come from?* File, page, rectangle, resolution. Auditable:
    every diagram in an exported book can be traced back to the pixels it was
    read from.
``RecognitionResult``
    *How sure are we, square by square?* A 64-float confidence vector plus the
    model identity and the repairs the legality solver applied. The reader
    paints anything below threshold amber, so the user reviews only what is
    doubtful -- the workflow that makes high-but-imperfect accuracy usable.
``DiagramStyle``
    *How should it look?* Piece set, board theme, coordinates, frame, size.
    Named styles live in the stylesheet, so restyling every diagram in a book is
    one edit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from caissa.core.model.base import IRNode
from caissa.core.model.game import GameScore
from caissa.core.model.inline import Inline, Orientation
from caissa.core.model.marks import Mark
from caissa.core.model.props import Border, Color, Measure, RunProps
from caissa.core.model.provenance import Rect, SourceKind
from caissa.core.model.registry import ir_node

__all__ = [
    "SQUARE_COUNT",
    "BoardTheme",
    "CaptionPosition",
    "CoordinateStyle",
    "Diagram",
    "DiagramSource",
    "DiagramStyle",
    "FenCandidate",
    "PiecePlacementStyle",
    "RecognitionPath",
    "RecognitionResult",
    "SquareRepair",
]

#: Squares on a board; the length ``RecognitionResult.per_square_confidence``
#: must have.
SQUARE_COUNT = 64


class RecognitionPath(StrEnum):
    """Which detection route produced a reading (SPEC 6.1, ADR-0006)."""

    VECTOR = "vector"
    #: OCR_UI_ROADMAP passo 10: an 8x8 lattice of glyphs in a chess font the
    #: catalog does not know — the rectangle is exact (vector), the position
    #: was read from the rendered cells by the square classifier (inferred),
    #: so the confidence is capped below an exact vector read.
    VECTOR_INFERRED = "vector-inferred"
    GEOMETRIC = "geometric"
    NEURAL = "neural"
    HYBRID = "hybrid"
    LLM = "llm"
    MANUAL = "manual"
    IMPORTED = "imported"


class CaptionPosition(StrEnum):
    """Where a caption sits relative to the board."""

    ABOVE = "above"
    BELOW = "below"
    LEFT = "left"
    RIGHT = "right"
    NONE = "none"


class PiecePlacementStyle(StrEnum):
    """Where coordinates and the side-to-move indicator are drawn."""

    OUTSIDE = "outside"
    INSIDE = "inside"
    NONE = "none"


@ir_node("diagram_source")
@dataclass(frozen=True, slots=True, kw_only=True)
class DiagramSource:
    """Where a diagram was taken from, precisely enough to go back and look.

    Attributes:
        kind: What kind of artefact it came from.
        path: Path or URI of the file.
        content_hash: Hash of that file, so the link survives a rename.
        page_index: Zero-based page number.
        rect: The rectangle on the page, in that page's coordinate space.
        dpi: Rasterisation resolution used, when the board was read from pixels.
        rotation_degrees: Rotation applied during rectification.
        image_hash: Perceptual hash of the crop, used to recognise the same
            diagram appearing in two books.
        extracted_at: When the extraction ran.
        extractor: Name of the ingest component that produced the crop.
        extractor_version: Its version.
    """

    kind: SourceKind = SourceKind.UNKNOWN
    path: str | None = None
    content_hash: str | None = None
    page_index: int | None = None
    rect: Rect | None = None
    dpi: float | None = None
    rotation_degrees: float | None = None
    image_hash: str | None = None
    extracted_at: datetime | None = None
    extractor: str | None = None
    extractor_version: str | None = None


@ir_node("fen_candidate")
@dataclass(frozen=True, slots=True, kw_only=True)
class FenCandidate:
    """A runner-up reading, kept so the user can pick it without re-running.

    Attributes:
        fen: The candidate position.
        score: Log-likelihood or calibrated probability of this reading.
        legal: Whether the candidate satisfies the SPEC 6.4 constraints.
    """

    fen: str
    score: float = 0.0
    legal: bool = True


@ir_node("square_repair")
@dataclass(frozen=True, slots=True, kw_only=True)
class SquareRepair:
    """One square the legality solver changed, and why.

    Recording the repair rather than silently applying it is what SPEC 6.4
    means by "divergencias residuais sao apresentadas ao usuario, nao
    escondidas".

    Attributes:
        square: Algebraic name of the square.
        recognised: What the classifier read, as a FEN piece letter, or the
            empty string for an empty square.
        repaired: What the solver put there instead.
        reason: Which constraint forced the change.
        confidence_before: The classifier's confidence in the original reading.
    """

    square: str
    recognised: str
    repaired: str
    reason: str = ""
    confidence_before: float | None = None


@ir_node("recognition_result")
@dataclass(frozen=True, slots=True, kw_only=True)
class RecognitionResult:
    """The audit trail of a machine reading of a board.

    Attributes:
        fen: What the pipeline read. May differ from :attr:`Diagram.fen` once a
            human has corrected the diagram -- keeping both is what makes the
            correction reviewable and feeds the training corpus.
        per_square_confidence: Sixty-four calibrated confidences in ``[0, 1]``,
            indexed from ``a1`` to ``h8``. The reader paints anything below the
            threshold amber.
        overall_confidence: Calibrated confidence for the whole board.
        orientation_confidence: Confidence that the board is the right way up.
        side_to_move_confidence: Confidence in the side-to-move reading.
        path: Which detection route produced this.
        model_name: Identity of the classifier.
        model_version: Its version.
        model_hash: Hash of its weights, for reproducibility.
        recognised_at: When the reading ran.
        duration_ms: Wall time of the reading.
        corners: The four detected board corners as ``(x0, y0, ... x3, y3)`` in
            source-page coordinates, so the crop can be reproduced exactly.
        alternatives: Runner-up readings.
        repairs: Squares the legality solver changed.
        warnings: Free-form remarks from the pipeline.
    """

    fen: str = ""
    per_square_confidence: tuple[float, ...] = ()
    overall_confidence: float | None = None
    orientation_confidence: float | None = None
    side_to_move_confidence: float | None = None
    path: RecognitionPath = RecognitionPath.MANUAL
    model_name: str | None = None
    model_version: str | None = None
    model_hash: str | None = None
    recognised_at: datetime | None = None
    duration_ms: float | None = None
    corners: tuple[float, ...] = ()
    alternatives: tuple[FenCandidate, ...] = ()
    repairs: tuple[SquareRepair, ...] = ()
    warnings: tuple[str, ...] = ()

    def doubtful_squares(self, threshold: float = 0.9) -> tuple[int, ...]:
        """Return the indices of squares read with confidence below ``threshold``.

        Args:
            threshold: Confidence below which a square counts as doubtful.

        Returns:
            Square indices, ``0`` being ``a1``.
        """
        return tuple(
            index for index, value in enumerate(self.per_square_confidence) if value < threshold
        )


@ir_node("board_theme")
@dataclass(frozen=True, slots=True, kw_only=True)
class BoardTheme:
    """The colours of a board.

    Attributes:
        light_square: Fill of the light squares.
        dark_square: Fill of the dark squares.
        border: Colour of the board frame.
        grid_line: Colour of the lines between squares; ``None`` draws none.
        white_piece_fill: Fill of white pieces.
        white_piece_stroke: Outline of white pieces.
        black_piece_fill: Fill of black pieces.
        black_piece_stroke: Outline of black pieces.
        background: Fill behind the whole diagram.
        highlight: Default colour for highlighted squares.
        arrow: Default colour for arrows.
    """

    light_square: Color | None = None
    dark_square: Color | None = None
    border: Color | None = None
    grid_line: Color | None = None
    white_piece_fill: Color | None = None
    white_piece_stroke: Color | None = None
    black_piece_fill: Color | None = None
    black_piece_stroke: Color | None = None
    background: Color | None = None
    highlight: Color | None = None
    arrow: Color | None = None


@ir_node("coordinate_style")
@dataclass(frozen=True, slots=True, kw_only=True)
class CoordinateStyle:
    """How file and rank labels are drawn around a board.

    Attributes:
        placement: Outside the frame, inside the squares, or not at all.
        files: Whether the ``a``-``h`` labels are drawn.
        ranks: Whether the ``1``-``8`` labels are drawn.
        both_sides: Draw labels on all four edges rather than two.
        props: Character formatting of the labels.
        gap: Distance between the board edge and the labels.
    """

    placement: PiecePlacementStyle = PiecePlacementStyle.NONE
    files: bool = True
    ranks: bool = True
    both_sides: bool = False
    props: RunProps = field(default_factory=RunProps)
    gap: Measure | None = None


@ir_node("diagram_style")
@dataclass(frozen=True, slots=True, kw_only=True)
class DiagramStyle:
    """How a diagram is drawn.

    Attributes:
        name: Name of the diagram style this one is derived from, resolved
            against the document stylesheet the same way character and
            paragraph styles are.
        piece_set: Named piece set: ``"Merida"``, ``"Alpha"``, ``"Chess
            Cases"``, ``"USCF"``, ``"Leipzig"``.
        piece_font_family: Chess font to draw pieces with, when the set is
            font-based rather than SVG.
        piece_scale: Piece size as a fraction of the square.
        theme: Board colours.
        coordinates: File and rank labels.
        size: Overall diagram width.
        square_size: Size of one square; an alternative to ``size``.
        border: Frame around the board.
        margin: Space between the frame and the squares.
        show_side_to_move: Draw the side-to-move indicator.
        side_to_move_placement: Where that indicator goes.
        caption_position: Where the caption sits.
        shadow: Draw a drop shadow behind the board.
        grid_lines: Draw lines between squares.
        keep_with_caption: Forbid a page break between board and caption.
    """

    name: str | None = None
    piece_set: str | None = None
    piece_font_family: str | None = None
    piece_scale: float | None = None
    theme: BoardTheme | None = None
    coordinates: CoordinateStyle | None = None
    size: Measure | None = None
    square_size: Measure | None = None
    border: Border | None = None
    margin: Measure | None = None
    show_side_to_move: bool | None = None
    side_to_move_placement: PiecePlacementStyle | None = None
    caption_position: CaptionPosition | None = None
    shadow: bool | None = None
    grid_lines: bool | None = None
    keep_with_caption: bool | None = None


@ir_node("diagram")
@dataclass(frozen=True, slots=True, kw_only=True)
class Diagram(IRNode):
    """A chess diagram: a position with provenance, style and annotations.

    Attributes:
        fen: The position, as currently believed. This is the authoritative
            value; ``recognition.fen`` is what the machine first read.
        orientation: Which side faces the reader.
        source: Where the diagram came from.
        recognition: The machine reading and its confidences.
        verified_by_human: Whether a person has confirmed the position.
        style: How the diagram is drawn.
        caption: Caption inlines.
        number: Automatic figure number; ``None`` leaves it unnumbered.
        label: Explicit label overriding the derived one, e.g. ``"Diagrama
            12a"``.
        marks: Arrows, highlighted squares and circles drawn on the board.
        side_to_move_indicator: Draw the side-to-move indicator for this
            diagram, overriding the style.
        stipulation: The problem's demand, e.g. ``"Mate em 2"`` or ``"Brancas
            jogam e ganham"``.
        solution: The solution as a game score, when known.
        anchor: Name other nodes can link to.
        alt_text: Accessible description, required by EPUB and by tagged PDF.
        move_context: Where the position sits in a game, e.g. ``"apos
            24...Txf2"``; printed under the diagram in most editions.
    """

    fen: str
    orientation: Orientation = Orientation.WHITE
    source: DiagramSource = field(default_factory=DiagramSource)
    recognition: RecognitionResult = field(default_factory=RecognitionResult)
    verified_by_human: bool = False
    style: DiagramStyle = field(default_factory=DiagramStyle)
    caption: tuple[Inline, ...] = ()
    number: int | None = None
    label: str | None = None
    marks: tuple[Mark, ...] = ()
    side_to_move_indicator: bool = False
    stipulation: str | None = None
    solution: GameScore | None = None
    anchor: str | None = None
    alt_text: str | None = None
    move_context: str | None = None
