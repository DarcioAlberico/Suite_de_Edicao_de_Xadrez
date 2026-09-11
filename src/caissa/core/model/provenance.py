"""Provenance: where a node came from, who read it, and how sure they were.

SPEC section 5.3 requires auditable provenance for diagrams. This module
generalises it to *every* node, because the existing rich-text model that
Caissa absorbs (``ChessVisionOFF_Puro/src/chess_diagram_ocr/text/rico.py``)
already proved the idea on text runs: each run remembers which engine read it,
which page block it came from, and which confidence band it fell into, and the
reader UI paints that band. Losing it on the way into the IR would be a
regression.

Carrying provenance on :class:`~caissa.core.model.base.IRNode` means:

* the reader can tint low-confidence text amber and let the user review only
  what is doubtful -- the workflow that makes 97 % accuracy usable in practice;
* an export can be audited back to a page rectangle in the original PDF;
* ``verified_by_human`` is a first-class fact, not a comment.

It costs nothing when unused: the field defaults to ``None``, and the serialiser
omits defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from caissa.core.model.registry import ir_node

__all__ = [
    "ConfidenceBand",
    "Provenance",
    "Rect",
    "SourceKind",
]


class SourceKind(StrEnum):
    """What produced a node."""

    UNKNOWN = "unknown"
    PDF_TEXT_LAYER = "pdf-text-layer"
    PDF_VECTOR = "pdf-vector"
    OCR = "ocr"
    VISION = "vision"
    LLM = "llm"
    PGN = "pgn"
    EPUB = "epub"
    DOCX = "docx"
    HTML = "html"
    IMAGE = "image"
    HUMAN = "human"
    SYNTHETIC = "synthetic"


class ConfidenceBand(StrEnum):
    """Coarse confidence bucket, the thing the reader UI actually paints.

    Kept alongside the numeric confidence rather than derived from it, because
    the thresholds are a calibrated per-engine decision (SPEC section 6.5) and
    must not be re-derived, differently, by each consumer.
    """

    CERTAIN = "certain"
    CONFIDENT = "confident"
    DOUBTFUL = "doubtful"
    UNRELIABLE = "unreliable"


@ir_node("rect")
@dataclass(frozen=True, slots=True, kw_only=True)
class Rect:
    """An axis-aligned rectangle in the coordinate space of its source page.

    Attributes:
        x: Left edge.
        y: Top edge.
        width: Horizontal extent.
        height: Vertical extent.
        unit: Name of the coordinate space, e.g. ``"pt"`` for PDF user space or
            ``"px"`` for a rendered raster.
    """

    x: float
    y: float
    width: float
    height: float
    unit: str = "pt"

    @property
    def right(self) -> float:
        """The right edge."""
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """The bottom edge."""
        return self.y + self.height

    @property
    def area(self) -> float:
        """The enclosed area."""
        return self.width * self.height


@ir_node("provenance")
@dataclass(frozen=True, slots=True, kw_only=True)
class Provenance:
    """Audit trail for a single node.

    Attributes:
        kind: What produced the node.
        document_path: Path or URI of the originating file.
        document_hash: Content hash of the originating file, so provenance
            survives the file being moved or renamed.
        page_index: Zero-based page number within that file.
        block_index: Index of the layout block the node came from, when the
            importer works block by block.
        rect: Region on the page.
        dpi: Rasterisation resolution, when the node came from a raster.
        engine: Name of the reader (``"tesseract"``, ``"surya"``, a model name).
        engine_version: Version of that reader, so a re-run can be compared.
        model_hash: Hash of the model weights, for reproducibility.
        confidence: Calibrated confidence in ``[0, 1]``.
        band: Coarse confidence bucket used by the UI.
        extracted_at: When the reading happened.
        verified_by_human: Whether a person has confirmed this node.
        out_of_model: The content contains symbols no model class can confirm,
            typically because a human typed them. Not an error -- a statement
            that this is authored, not read.
        note: Free-form remark from the importer.
    """

    kind: SourceKind = SourceKind.UNKNOWN
    document_path: str | None = None
    document_hash: str | None = None
    page_index: int | None = None
    block_index: int | None = None
    rect: Rect | None = None
    dpi: float | None = None
    engine: str | None = None
    engine_version: str | None = None
    model_hash: str | None = None
    confidence: float | None = None
    band: ConfidenceBand | None = None
    extracted_at: datetime | None = None
    verified_by_human: bool = False
    out_of_model: bool = False
    note: str | None = None
