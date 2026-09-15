"""What the text around a diagram says about it: side to move, players, event.

Ported from the trunk's ``pdf_text.py`` (S-16, S-43, S-129, S-217), absorbed
2026-09-11.  Changes: the input is the engine-agnostic
:class:`~caissa.ingest.pdf.textlayer.PageText` instead of a live page, the
diagram-font row filter is gone because the text layer already marks those
spans, and the side-to-move colour is a plain ``bool`` (``True`` = White, the
``python-chess`` convention) so the module needs no chess import.  Every
measured rule is kept, with its measurement.

**Why this exists.**  Measured on the trunk's labels: 0 of 3.244 had Black to
move, so every exported FEN said ``w`` -- and in a tactics book half the
exercises are "Black to play".  The information is on the page: three of the
books that declare the side do it in a caption next to each diagram.  This
module reads that and never invents: a field the page does not state is
``None``.

**Where the caption is, measured.**  ``400 Quebra-cabeças``: below.
``Schiller``, ``AAGAARD``, ``Karpov``: **above**.  Distance alone assigns
systematically wrong, always in the same direction: in the ``Karpov`` the gap
above a diagram is 10 pt and the gap below 7 pt, so every diagram steals the
next one's caption and the whole page shifts by one exercise (``№79`` becomes
``№81``).  Hence :func:`dominant_placement`: the side that wins captions for
*more* diagrams on the page decides, and mean distance only breaks ties.

**Four traps the measurement imposed on the design.**

1. *Line granularity, not block.*  In the ``Karpov`` one block covers the
   captions of both columns.  Lines have their own boxes.
2. *But the caption decides as a group.*  Number, players and event are one
   block, and distributing them line by line shifts the page by one exercise
   (``Schiller``).  The unit is the group: block, split by column.
3. *Prose is not a caption.*  Running the patterns over the whole page yields
   false positives in 8 books ("se as brancas jogarem 32 f2×g2").  In prose the
   pattern counts only when it *opens* the line -- the ``AAGAARD`` glues the
   stipulation to the commentary.
4. *A page number looks like an exercise number.*  In ``Reinfeld 1001`` the
   only text on the page is the printed folio, 16 pt from the diagram.  Two
   filters, both needed: the margin band and local consecutiveness
   (:func:`running_page_number`).
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from caissa.ingest.pdf.geometry import RectT
from caissa.ingest.pdf.textlayer import PageText, TextLine

__all__ = [
    "CaptionLine",
    "DiagramContext",
    "NearbyLine",
    "PageScope",
    "Placement",
    "apply_page_scope",
    "assign_lines_to_diagrams",
    "bare_integers",
    "caption_lines",
    "context_from_lines",
    "contexts_for_page",
    "dominant_placement",
    "fold",
    "lines_near",
    "page_contexts",
    "page_scope_declaration",
    "parse_context",
    "running_page_number",
]

LOGGER = logging.getLogger("caissa.ingest.pdf.captions")

Placement = Literal["above", "below", "left", "right", "overlapping"]

#: Search radius in points.  Measured captions sit 0-20 pt from the diagram.
DEFAULT_RADIUS_PT: Final = 60.0
#: Fraction of the shorter side a line and a diagram must share on the cross
#: axis.  Keeps the neighbouring column's caption out: in the ``Karpov`` the
#: right column's line (x 278-402) does not touch the left diagram (x 56-203).
MIN_AXIS_OVERLAP: Final = 0.25
#: Above this a block is commentary, not a caption, and its patterns do not
#: count as declarations.
MAX_CAPTION_WORDS: Final = 25
#: Top and bottom band holding running heads and folios, dropped wholesale --
#: except for the page-scope declaration, which is read there on purpose.
MARGIN_BAND: Final = 0.07
#: From this many loose axis labels in one strip, they are a board's border.
_MIN_AXIS_LABELS: Final = 6
_AXIS_LABEL: Final = re.compile(r"^[a-h1-8]$")
#: The file letters printed as one line under a board.
_FILE_LABELS: Final = re.compile(r"^a\W*b\W*c\W*d\W*e\W*f\W*g\W*h$", re.IGNORECASE)
_BARE_INT: Final = re.compile(r"^\(?(\d{1,4})\)?$")
#: Neighbours consulted for the folio.  ±2 because book numbering alternates
#: sides: even pages print the number right, odd pages left (``AAGAARD``).
_NEIGHBOUR_DELTAS: Final = (1, -1, 2, -2)
#: How far the folio may drift between pages and still be the same element.
_SAME_COLUMN_TOLERANCE: Final = 24.0
_MAX_EXERCISE_NUMBER: Final = 10000

_DASHES: Final = "‐‑‒–—―−"


def fold(text: str) -> str:
    """Lowercase, no accents, collapsed spaces, every dash a hyphen.

    ``ß`` is handled apart because NFKD does not decompose it: without this
    "Weiß am Zug" matches nothing, and German is one of the collection's
    languages.
    """
    text = text.replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for dash in _DASHES:
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip().lower()


# Portuguese in the collection takes five forms (``400 Quebra-cabeças``, 400
# exercises): "brancas jogam" (117), "jogada das pretas" (52), "jogada de
# pretas" (27), "pretas jogam" (13), "jogar de pretas" (12), "jogam as pretas"
# (1).  Covering only two would leave 39 exercises without a side.
_PT_PLAY: Final = r"jog(?:ada|ar|am|a)\s+(?:d(?:as|os|a|o|e)|as|os)\s+"

_WHITE_PATTERNS: Final[tuple[str, ...]] = (
    r"\b(?:as\s+)?brancas\s+(?:jogam|jogar|comecam|iniciam)\b",
    rf"\b{_PT_PLAY}brancas\b",
    r"\b(?:e\s+a\s+)?vez\s+d[ao]s\s+brancas\b",
    r"\bbrancas\s+no\s+lance\b",
    r"\bwhite\s+to\s+(?:move|play)\b",
    r"\bwhite\s+(?:plays|moves|begins|starts)\b",
    r"\bweiss?\s+(?:am\s+zug|zieht|beginnt|spielt|setzt)\b",
    r"\bam\s+zug\s*:\s*weiss?\b",
    r"\b(?:juegan\s+(?:las\s+)?blancas|blancas\s+juegan|turno\s+de\s+las\s+blancas)\b",
    r"\b(?:les\s+)?blancs\s+jouent\b",
    r"\btrait\s+aux\s+blancs\b",
)

_BLACK_PATTERNS: Final[tuple[str, ...]] = (
    r"\b(?:as\s+)?(?:pretas|negras)\s+(?:jogam|jogar|comecam|iniciam)\b",
    rf"\b{_PT_PLAY}(?:pretas|negras)\b",
    r"\b(?:e\s+a\s+)?vez\s+d[ao]s\s+(?:pretas|negras)\b",
    r"\b(?:pretas|negras)\s+no\s+lance\b",
    r"\bblack\s+to\s+(?:move|play)\b",
    r"\bblack\s+(?:plays|moves|begins|starts)\b",
    r"\bschwarz\s+(?:am\s+zug|zieht|beginnt|spielt|setzt)\b",
    r"\bam\s+zug\s*:\s*schwarz\b",
    r"\b(?:juegan\s+(?:las\s+)?negras|negras\s+juegan|turno\s+de\s+las\s+negras)\b",
    r"\b(?:les\s+)?noirs\s+jouent\b",
    r"\btrait\s+aux\s+noirs\b",
)

_WHITE_SYMBOLS: Final = "◻□▫⬜◽⚪"
_BLACK_SYMBOLS: Final = "◼■▪⬛◾⚫"

#: A word right before the pattern that turns a declaration into a hypothesis.
#: "Se as brancas jogarem 32.f2xg2" describes an imaginary line, not whose turn
#: it is -- a measured false positive in ``Melhores Finais de Capablanca``.
_SUBORDINATORS: Final = frozenset(
    {
        "se", "if", "when", "wenn", "quando", "after", "depois", "apos", "because",
        "porque", "since", "although", "though", "embora", "caso", "que", "para",
        "wo", "als", "nachdem", "wie",
    }
)  # fmt: skip

#: ``79.``, ``No 79.``, ``Nº79:``, ``№79.`` -- the numero sign on its own is
#: the form the Karpov prints, and the trunk's pattern required a leading ``n``.
_NUMBER_PREFIX: Final = re.compile(
    r"^(?:(?:n[o°º!№]*|№)\s*[.º]?\s*)?(\d{1,4})\s*[.:)\]\-–]",
    re.IGNORECASE,
)
_YEAR: Final = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
_NAME: Final = r"[A-ZÀ-Þ][\w'’.À-ÿ-]*(?:\s+[A-ZÀ-Þ][\w'’.À-ÿ-]*)?"
_PLAYERS: Final = re.compile(rf"({_NAME})\s*[-–—]\s*({_NAME})\s*$")
#: Move text in any of the collection's spellings, figurines included: the
#: trunk's pattern knew only Latin piece letters, and a figurine line
#: (``♕b3+! 4.♕xb3 axb3+``) passed for a caption.
_MOVE_TEXT: Final = re.compile(r"\d\s*[.…]\s*[\w♔-♟]|[♔-♟KQRBNRPKDTLSC][a-h][1-8]")
#: OCR_UI_ROADMAP passo 7: the first move printed under a diagram says whose
#: turn it is -- ``22... ♖g8`` is Black's, ``23 ♘c4`` / ``23.♘c4`` is White's.
#: The number is the full-move number of that side's move.
_MOVE_TOKEN_AHEAD: Final = r"(?=[♔-♟]|[KQRBNDTLSCФЛКС][a-h]?[1-8x]|[a-h][1-8x]|O-O|0-0)"  # noqa: S105
_MOVE_START: Final = re.compile(r"^\s*(\d{1,3})\s*(\.{3}|…|\.)?\s*" + _MOVE_TOKEN_AHEAD)
#: "após 23...♗d5" / "after 23.Nc4" / "nach 23...Ld5" / "después de" / "после":
#: the position *after* that move, so the other side is to move.
_AFTER_MOVE: Final = re.compile(
    r"\b(?:ap[oó]s|depois de|after|nach|despu[eé]s de|после|posle)\s+"
    r"(\d{1,3})\s*(\.{3}|…|\.)\s*" + _MOVE_TOKEN_AHEAD,
    re.IGNORECASE,
)
#: Exercise number without punctuation, digits possibly split by OCR: the
#: ``AAGAARD`` numbers ``1 19 Bartrina - Ghitescu`` for exercise 119.
_LOOSE_NUMBER_PREFIX: Final = re.compile(r"^(\d[\d ]{0,4})\s+(?=[A-ZÀ-Þ])")
#: A chapter-qualified diagram label: ``4-10``, ``16-42``, ``4/1``.  Not an
#: exercise *number* -- ``4-10`` is not exercise 4 -- so it is kept whole as
#: the diagram's literal label instead.
_COMPOUND_LABEL: Final = re.compile(r"^(\d{1,3}[-–/]\d{1,4})(?:\s|$)")
#: Problem-book shorthand for the side to move, on a line of its own:
#: ``W?`` / ``B`` (Dvoretsky), optionally with the stipulation mark.
_SIDE_SHORTHAND: Final = re.compile(r"^([WB])[?+=#!]?$")


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CaptionLine:
    """One text line as the caption reader sees it.

    Attributes:
        text: Whitespace-collapsed text.
        box: ``page.rect`` points.
        block_words: Words in the whole producer block the line came from.
        group_id: Caption group: same block *and* same column.
        confidence: ``1.0`` for a text layer, the engine's value for OCR.
        origin: ``"text"`` or ``"ocr"`` -- the layer wins a contradiction.
    """

    text: str
    box: RectT
    block_words: int
    group_id: int = 0
    confidence: float = 1.0
    origin: str = "text"

    @property
    def is_caption_like(self) -> bool:
        return self.block_words <= MAX_CAPTION_WORDS


@dataclass(frozen=True, slots=True)
class NearbyLine:
    """A line near a diagram, with the geometry of the relation kept."""

    line: CaptionLine
    distance: float
    placement: Placement
    #: Came from *this* diagram's caption, not a neighbour that passed near.
    primary: bool = False

    @property
    def text(self) -> str:
        return self.line.text


@dataclass(frozen=True, slots=True)
class DiagramContext:
    """What the text says about a diagram.  A field not said is ``None``.

    Attributes:
        caption: Associated lines, cleaned, joined by newlines.
        side_to_move: ``True`` White, ``False`` Black, ``None`` not stated.
        side_to_move_evidence: The fragment that decided, for the user to
            disagree with.
        side_to_move_origin: ``"text"``, ``"ocr"``, ``"text-page-scope"`` ...
        side_to_move_confidence: Confidence of the deciding fragment.
        exercise_number: Declared exercise number.
        players: ``(white, black)``.
        event: Event name.
        year: Four-digit year.
    """

    caption: str = ""
    #: Only the lines of the claimed caption group, or empty when no group
    #: claimed the diagram.  What a ``Diagram.caption`` should carry; the
    #: full :attr:`caption` also holds neighbouring commentary.
    caption_primary: str = ""
    #: Literal diagram label when it is not a plain integer: ``"4-10"``,
    #: ``"16-42"``, ``"4/1"``.
    label: str | None = None
    side_to_move: bool | None = None
    side_to_move_evidence: str = ""
    side_to_move_origin: str | None = None
    side_to_move_confidence: float = 1.0
    #: OCR_UI_ROADMAP passo 7: ``(number, black_to_move)`` read from the first
    #: line of moves under the diagram (``22...`` → ``(22, True)``; ``23 ♘c4``
    #: → ``(23, False)``), and from a caption "após/after N.x" (the position
    #: after that move: ``after 23...♗d5`` → ``(24, False)``).  Both feed the
    #: side cascade after the declared text and before the page scope.
    first_move_number: tuple[int, bool] | None = None
    caption_after_move: tuple[int, bool] | None = None
    exercise_number: int | None = None
    players: tuple[str, str] | None = None
    event: str | None = None
    year: int | None = None

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.caption,
                self.side_to_move is not None,
                self.exercise_number,
                self.players,
                self.event,
                self.year,
            )
        )


@dataclass(frozen=True, slots=True)
class PageScope:
    """A side-to-move declaration valid for the whole page, not one diagram."""

    color: bool
    evidence: str
    origin: str
    confidence: float = 1.0


# --------------------------------------------------------------------------- #
# Side-to-move patterns
# --------------------------------------------------------------------------- #


def _preceded_by_subordinator(folded: str, start: int) -> bool:
    prefix_words = folded[:start].split()
    return bool(prefix_words) and prefix_words[-1] in _SUBORDINATORS


def _match_side(folded: str) -> tuple[bool, str] | None:
    """Side declared in already-folded text, with the deciding fragment."""
    hits: list[tuple[int, bool, str]] = []
    for patterns, color in ((_WHITE_PATTERNS, True), (_BLACK_PATTERNS, False)):
        for pattern in patterns:
            match = re.search(pattern, folded)
            if match is None:
                continue
            if _preceded_by_subordinator(folded, match.start()):
                continue
            hits.append((match.start(), color, match.group(0)))
    if not hits:
        return None
    hits.sort()
    # Two opposite declarations in one caption: the page says both things
    # (a solutions page listing several exercises).  Nothing to choose.
    if len({color for _, color, _ in hits}) > 1:
        return None
    _, color, evidence = hits[0]
    return color, evidence


def _match_side_symbol(text: str) -> tuple[bool, str] | None:
    """Typographic convention: hollow square = White, solid = Black.

    Only in short text; in a paragraph the symbol is an ornament or a piece.
    """
    for ch in text:
        if ch in _WHITE_SYMBOLS:
            return True, ch
        if ch in _BLACK_SYMBOLS:
            return False, ch
    return None


def _side_from_line(text: str, *, caption_like: bool) -> tuple[bool, str] | None:
    """Side declared by this line, the bar set by the line's format.

    In a caption the pattern counts wherever it stands.  In a paragraph it
    counts only when it *opens* the line -- the measured false positives are
    all clausal ("se as brancas jogarem", "it was possible for White to play")
    while the true positives in prose all open the line (``AAGAARD``).
    """
    symbol = _match_side_symbol(text) if caption_like else None
    if symbol is not None:
        return symbol
    if caption_like:
        shorthand = _SIDE_SHORTHAND.match(text.strip())
        if shorthand is not None:
            return shorthand.group(1) == "W", text.strip()
    folded = fold(text)
    found = _match_side(folded)
    if found is None:
        return None
    if caption_like:
        return found
    _, evidence = found
    return found if folded.startswith(evidence) else None


# --------------------------------------------------------------------------- #
# Lines of a page
# --------------------------------------------------------------------------- #


def _axis_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    span = min(a1 - a0, b1 - b0)
    if span <= 0:
        return 0.0
    return max(0.0, min(a1, b1) - max(a0, b0)) / span


class _DisjointSet:
    """Union-find over ``n`` items, path-halving."""

    __slots__ = ("_labels",)

    def __init__(self, n: int) -> None:
        self._labels = list(range(n))

    def find(self, index: int) -> int:
        labels = self._labels
        while labels[index] != index:
            labels[index] = labels[labels[index]]
            index = labels[index]
        return index

    def union(self, i: int, j: int) -> None:
        self._labels[self.find(i)] = self.find(j)


def _axis_label_strip(items: Sequence[tuple[str, RectT]]) -> set[int]:
    """Indices of the labels forming a diagram's **border**, not loose text.

    Counting per block was not enough (S-217): the ``Polgar`` puts each rank
    digit in its own block.  Counting the whole page would break the
    ``1937 Kemeri`` crosstable, whose dozens of loose ``1`` are results.  What
    separates them is what a board border is: labels **aligned** in a strip
    and **distinct** -- eight ranks or eight files, each once.
    """
    dropped: set[int] = set()
    for axis in (0, 1):
        sets = _DisjointSet(len(items))
        for i, (_, a) in enumerate(items):
            for j in range(i + 1, len(items)):
                b = items[j][1]
                if _axis_overlap(a[axis], a[axis + 2], b[axis], b[axis + 2]) > 0.0:
                    sets.union(i, j)
        groups: dict[int, list[int]] = {}
        for index in range(len(items)):
            groups.setdefault(sets.find(index), []).append(index)
        for group in groups.values():
            marks = {items[index][0].lower() for index in group}
            ranks = sum(1 for mark in marks if mark.isdigit())
            files = len(marks) - ranks
            if ranks >= _MIN_AXIS_LABELS or files >= _MIN_AXIS_LABELS:
                dropped |= set(group)
    return dropped


def _split_into_columns(boxes: Sequence[RectT]) -> list[int]:
    """Label a block's lines by column, joining those that overlap horizontally.

    The ``Karpov`` puts both columns' captions in one block (``№79`` at
    x 82-181, ``№80`` at x 278-402).  Kept whole, each diagram would inherit
    the neighbour's opponent.
    """
    sets = _DisjointSet(len(boxes))
    for i, (ax0, _, ax1, _) in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            bx0, _, bx1, _ = boxes[j]
            if _axis_overlap(ax0, ax1, bx0, bx1) > 0.0:
                sets.union(i, j)
    return [sets.find(index) for index in range(len(boxes))]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_Kept = tuple[str, RectT, float]


def _keep_band(
    lines: Sequence[TextLine], top_limit: float, bottom_limit: float, margin: bool
) -> list[_Kept]:
    """One block's lines inside (or outside) the margin band, axis labels culled."""
    kept: list[_Kept] = []
    for line in lines:
        if line.is_diagram:
            continue
        text = _clean(line.text)
        if not text or _FILE_LABELS.match(text):
            continue
        x0, y0, x1, y1 = line.box
        in_margin = y1 <= top_limit or y0 >= bottom_limit
        if in_margin != margin:
            continue
        kept.append((text, (x0, y0, x1, y1), line.confidence))
    # Axis labels arrive as loose "a" / "7"; a loose "7" would read as an
    # exercise number.  No real caption block has six of them.
    if sum(1 for text, _, _ in kept if _AXIS_LABEL.match(text)) >= _MIN_AXIS_LABELS:
        kept = [item for item in kept if not _AXIS_LABEL.match(item[0])]
    return kept


def caption_lines(page: PageText, *, margin: bool = False) -> list[CaptionLine]:
    """The page's lines as caption candidates, body or margin band.

    ``margin=False`` drops the top and bottom 7 % (running heads, folios) and
    every diagram-font row; ``margin=True`` returns only that band, which is
    where a page-scope declaration lives (``LAS BLANCAS JUEGAN PRIMERO`` on
    top of ``Reinfeld`` p. 40, valid for the six diagrams of the page).
    """
    frame = page.frame
    top_limit = frame.height * MARGIN_BAND
    bottom_limit = frame.height * (1.0 - MARGIN_BAND)

    blocks: dict[int, list[TextLine]] = {}
    for line in page.lines:
        blocks.setdefault(line.block_index, []).append(line)

    kept_blocks: list[tuple[int, list[_Kept]]] = []
    for _, lines in sorted(blocks.items()):
        block_words = sum(len(line.text.split()) for line in lines)
        kept = _keep_band(lines, top_limit, bottom_limit, margin)
        if kept:
            kept_blocks.append((block_words, kept))

    # The border ignores blocks, hence the page-wide second pass.
    marks = [
        (bi, ii, text, box)
        for bi, (_, kept) in enumerate(kept_blocks)
        for ii, (text, box, _) in enumerate(kept)
        if _AXIS_LABEL.match(text)
    ]
    if len(marks) >= _MIN_AXIS_LABELS:
        strip = _axis_label_strip([(text, box) for _, _, text, box in marks])
        drop = {(marks[i][0], marks[i][1]) for i in strip}
        if drop:
            kept_blocks = [
                (words, [item for ii, item in enumerate(kept) if (bi, ii) not in drop])
                for bi, (words, kept) in enumerate(kept_blocks)
            ]

    out: list[CaptionLine] = []
    next_group = 0
    for block_words, kept in kept_blocks:
        if not kept:
            continue
        columns = _split_into_columns([box for _, box, _ in kept])
        group_ids = {label: next_group + k for k, label in enumerate(dict.fromkeys(columns))}
        next_group += len(group_ids)
        for (text, box, confidence), label in zip(kept, columns, strict=True):
            out.append(
                CaptionLine(
                    text=text,
                    box=box,
                    block_words=block_words,
                    group_id=group_ids[label],
                    confidence=confidence,
                    origin="text" if page.source == "pdf-text-layer" else "ocr",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Geometry between lines and diagrams
# --------------------------------------------------------------------------- #


def _relate(line_box: RectT, box: RectT) -> tuple[float, Placement] | None:
    """Distance and placement of a line relative to a diagram, or ``None``."""
    lx0, ly0, lx1, ly1 = line_box
    bx0, by0, bx1, by1 = box
    dx = max(bx0 - lx1, lx0 - bx1, 0.0)
    dy = max(by0 - ly1, ly0 - by1, 0.0)
    distance = math.hypot(dx, dy)
    vertical = dy > 0.0 or (dx == 0.0 and dy == 0.0)
    if vertical and _axis_overlap(lx0, lx1, bx0, bx1) >= MIN_AXIS_OVERLAP:
        if dy == 0.0 and dx == 0.0:
            return distance, "overlapping"
        return distance, "above" if ly1 <= by0 else "below"
    if dx > 0.0 and _axis_overlap(ly0, ly1, by0, by1) >= MIN_AXIS_OVERLAP:
        return distance, "left" if lx1 <= bx0 else "right"
    return None


def lines_near(
    lines: Iterable[CaptionLine], box: RectT, *, radius_pt: float = DEFAULT_RADIUS_PT
) -> list[NearbyLine]:
    """Lines within ``radius_pt`` of the diagram, nearest first.

    Cross-axis alignment is required: a line "above" must share the column.
    """
    found: list[NearbyLine] = []
    for line in lines:
        relation = _relate(line.box, box)
        if relation is None or relation[0] > radius_pt:
            continue
        found.append(NearbyLine(line=line, distance=relation[0], placement=relation[1]))
    found.sort(key=lambda item: (item.distance, item.line.box[1]))
    return found


_GroupMatch = list[tuple[CaptionLine, float, Placement]]


def _group_matches(
    lines: Sequence[CaptionLine], boxes: Sequence[RectT], radius_pt: float
) -> tuple[list[int], dict[tuple[int, int], _GroupMatch]]:
    order: list[int] = list(dict.fromkeys(line.group_id for line in lines))
    by_group: dict[int, list[CaptionLine]] = {}
    for line in lines:
        by_group.setdefault(line.group_id, []).append(line)
    matches: dict[tuple[int, int], _GroupMatch] = {}
    for group_id in order:
        for index, box in enumerate(boxes):
            related = [
                (line, relation[0], relation[1])
                for line in by_group[group_id]
                if (relation := _relate(line.box, box)) is not None
            ]
            # The group is the unit (module docstring, trap 2): when any of
            # its lines is within reach, the whole group comes -- the "W?"
            # printed under "4-10" is 71 pt from the board and belongs to
            # the same caption as the number 53 pt above it.
            if related and min(item[1] for item in related) <= radius_pt:
                matches[(group_id, index)] = related
    return order, matches


def _match_distance(matched: _GroupMatch) -> float:
    return min(item[1] for item in matched)


def _match_placement(matched: _GroupMatch) -> Placement:
    return min(matched, key=lambda item: item[1])[2]


def _can_be_caption(matched: _GroupMatch) -> bool:
    """A group may *claim* a diagram only when it reads like a caption.

    A short block of analysis that happens to sit above a board
    (``♕b3+! 4.♕xb3 axb3+`` continuing from the previous page, Dvoretsky
    p. 207) is context, never the caption -- with it eligible, the real
    caption ``16-43`` printed under the board lost the claim on distance.
    """
    lines = [line for line, _, _ in matched]
    if not lines or not all(line.is_caption_like for line in lines):
        return False
    return not any(_MOVE_TEXT.search(_strip_number_prefix(line.text)) for line in lines)


def dominant_placement(
    group_ids: Sequence[int],
    matches: Mapping[tuple[int, int], _GroupMatch],
    diagram_count: int,
) -> Placement | None:
    """Which side of the diagram this page prints the caption on.

    Decided per page, not per diagram, because the local information is what
    misleads (module docstring).  The side that wins a caption for **more**
    diagrams wins; mean distance breaks ties.
    """
    scores: dict[Placement, tuple[int, float]] = {}
    sides: tuple[Placement, ...] = ("above", "below")
    for side in sides:
        distances: list[float] = []
        for index in range(diagram_count):
            candidates = [
                _match_distance(matches[(group_id, index)])
                for group_id in group_ids
                if (group_id, index) in matches
                and _can_be_caption(matches[(group_id, index)])
                and _match_placement(matches[(group_id, index)]) == side
            ]
            if candidates:
                distances.append(min(candidates))
        if distances:
            scores[side] = (len(distances), sum(distances) / len(distances))
    if not scores:
        return None
    return min(scores.items(), key=lambda item: (-item[1][0], item[1][1]))[0]


def assign_lines_to_diagrams(
    lines: Sequence[CaptionLine],
    boxes: Sequence[RectT],
    *,
    radius_pt: float = DEFAULT_RADIUS_PT,
) -> list[list[NearbyLine]]:
    """Distribute the page's lines among its diagrams, caption first in each.

    The unit is the **group** (block split by column), not the loose line
    (``Schiller``: distributed line by line, the ``6`` of the lower diagram's
    caption falls 15 pt from the upper diagram and the upper one, whose
    caption says ``5``, comes out numbered 6).  Each diagram takes the nearest
    group on the dominant side and a group serves one diagram; what is left
    goes to the nearest diagram as context, not caption.
    """
    buckets: list[list[NearbyLine]] = [[] for _ in boxes]
    if not boxes:
        return buckets
    group_ids, matches = _group_matches(lines, boxes, radius_pt)
    side = dominant_placement(group_ids, matches, len(boxes))

    primary_of: dict[int, int] = {}
    claims = sorted(
        (_match_distance(matched), index, group_id)
        for (group_id, index), matched in matches.items()
        if side is not None and _match_placement(matched) == side and _can_be_caption(matched)
    )
    taken: set[int] = set()
    for _, index, group_id in claims:
        if index in primary_of or group_id in taken:
            continue
        primary_of[index] = group_id
        taken.add(group_id)
    for index, group_id in primary_of.items():
        buckets[index].extend(
            NearbyLine(line=line, distance=distance, placement=placement, primary=True)
            for line, distance, placement in matches[(group_id, index)]
        )
    for group_id in group_ids:
        if group_id in taken:
            continue
        candidates = [
            (_match_distance(matches[(group_id, index)]), index)
            for index in range(len(boxes))
            if (group_id, index) in matches
        ]
        if not candidates:
            continue
        _, index = min(candidates)
        buckets[index].extend(
            NearbyLine(line=line, distance=distance, placement=placement)
            for line, distance, placement in matches[(group_id, index)]
        )
    for bucket in buckets:
        bucket.sort(key=lambda item: (not item.primary, item.distance, item.line.box[1]))
    return buckets


# --------------------------------------------------------------------------- #
# Printed page number
# --------------------------------------------------------------------------- #


def bare_integers(page: PageText) -> list[tuple[int, RectT]]:
    """Every line that is nothing but an integer, with its box.

    Cheap enough to keep for every page of a book (a folio and a handful of
    exercise numbers), which is what lets :func:`running_page_number` look at
    neighbouring pages without re-reading them.
    """
    found: list[tuple[int, RectT]] = []
    for line in page.lines:
        match = _BARE_INT.match(line.text.strip())
        if match is not None:
            found.append((int(match.group(1)), line.box))
    return found


def running_page_number(
    current: Sequence[tuple[int, RectT]],
    neighbours: Mapping[int, Sequence[tuple[int, RectT]]],
    page_height: float,
) -> int | None:
    """The folio **printed** on this page, if some integer behaves like one.

    There is no constant offset between the folio and the page index: in the
    ``Reinfeld`` it runs from -10 at page 46 to -29 at page 1012, because the
    scan has more pages than the book.  What a folio is, and what is tested,
    is *locally* consecutive: an integer is the folio when a neighbouring page
    carries its successor in the same column.  ``neighbours`` maps a page
    index delta (``±1``, ``±2``) to that page's bare integers.  Exercise
    numbers also step by one (``400 Quebra-cabeças``); what separates them is
    height -- the folio lives at the edge.
    """
    if not current:
        return None
    confirmed: list[tuple[float, int]] = []
    for delta in _NEIGHBOUR_DELTAS:
        others = neighbours.get(delta)
        if not others:
            continue
        for value, box in current:
            for other_value, other_box in others:
                if other_value != value + delta:
                    continue
                if _axis_overlap(box[0], box[2], other_box[0], other_box[2]) <= 0.0:
                    continue
                if abs(box[1] - other_box[1]) > _SAME_COLUMN_TOLERANCE:
                    continue
                confirmed.append((min(box[1], page_height - box[3]), value))
    if not confirmed:
        return None
    return min(confirmed)[1]


# --------------------------------------------------------------------------- #
# Caption interpretation
# --------------------------------------------------------------------------- #


def _strip_number_prefix(text: str) -> str:
    return _NUMBER_PREFIX.sub("", text, count=1).strip()


def _parse_exercise_number(text: str) -> int | None:
    if _COMPOUND_LABEL.match(text):
        return None
    bare = _BARE_INT.match(text)
    if bare is not None:
        return int(bare.group(1))
    prefix = _NUMBER_PREFIX.match(text)
    if prefix is not None and _strip_number_prefix(text):
        return int(prefix.group(1))
    loose = _LOOSE_NUMBER_PREFIX.match(text)
    if loose is not None and not _MOVE_TEXT.search(text):
        digits = loose.group(1).replace(" ", "")
        if digits.isdigit() and 0 < int(digits) < _MAX_EXERCISE_NUMBER:
            return int(digits)
    return None


def _parse_players(text: str) -> tuple[str, str] | None:
    """``Steinitz - Bird`` to ``("Steinitz", "Bird")``; anything else ``None``.

    Both sides capitalised and the pair at the end of the line, so that
    ``1937 Kemeri`` (an event) and ``12.Na4! - forte`` (a move) do not pass.
    """
    candidate = _strip_number_prefix(text).strip(" .;")
    if not candidate or _MOVE_TEXT.search(candidate):
        return None
    if _match_side(fold(candidate)) is not None:
        return None
    match = _PLAYERS.search(candidate)
    if match is None:
        return None
    white, black = match.group(1).strip(" .-"), match.group(2).strip(" .-")
    if not white or not black or white.isdigit() or black.isdigit():
        return None
    if _YEAR.search(white) or _YEAR.search(black):
        return None
    return white, black


def _parse_event_year(text: str) -> tuple[str | None, int | None]:
    candidate = _strip_number_prefix(text).strip(" .;")
    # A line that is nothing but an integer is a diagram number, not a year:
    # the Polgar's exercise 1699 is not a game from 1699.
    if _BARE_INT.match(candidate):
        return None, None
    match = _YEAR.search(candidate)
    if match is None:
        return None, None
    year = int(match.group(1))
    event = candidate[: match.start()].strip(" ,;.-") or candidate[match.end() :].strip(" ,;.-")
    if _MOVE_TEXT.search(event or ""):
        return None, year
    return (event or None), year


def move_start(text: str) -> tuple[int, bool] | None:
    """``(number, black_to_move)`` when ``text`` opens with a numbered move."""
    match = _MOVE_START.match(text)
    if match is None:
        return None
    dots = match.group(2) or ""
    return int(match.group(1)), dots in ("...", "…")


def after_move(text: str) -> tuple[int, bool] | None:
    """``(number, black_to_move)`` of the side to move *after* "após N.x" in ``text``."""
    match = _AFTER_MOVE.search(text)
    if match is None:
        return None
    number = int(match.group(1))
    black_moved = match.group(2) in ("...", "…")
    # After Black's Nth move White is to move at N+1; after White's, Black at N.
    return (number + 1, False) if black_moved else (number, True)


@dataclass(frozen=True, slots=True)
class _ParsedLine:
    text: str
    caption_like: bool
    primary: bool
    origin: str = "text"
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class _SideDecision:
    color: bool
    evidence: str
    origin: str
    confidence: float


def _side_from_tier(lines: Sequence[_ParsedLine]) -> _SideDecision | None:
    """Side of this tier, or ``None`` when it says both things.

    When the tier mixes the text layer and OCR and they disagree, **the text
    layer wins**: it is what the editor wrote, OCR is a reading of pixels
    that confuses ``negras`` with ``negros`` on a dirty scan.
    """
    found = [
        _SideDecision(decl[0], decl[1], line.origin, line.confidence)
        for line in lines
        if (decl := _side_from_line(line.text, caption_like=line.caption_like)) is not None
    ]
    if not found:
        return None
    if len({item.color for item in found}) > 1:
        from_text = [item for item in found if item.origin == "text"]
        if from_text and len({item.color for item in from_text}) == 1:
            return from_text[0]
        return None
    return next((item for item in found if item.origin == "text"), found[0])


def _first_found(
    items: Sequence[_ParsedLine], reader: Callable[[str], tuple[int, bool] | None]
) -> tuple[tuple[int, bool] | None, str]:
    for item in items:
        found = reader(item.text)
        if found is not None:
            return found, item.text
    return None, ""


def _side_from_numbering(
    first_move: tuple[int, bool] | None,
    first_move_text: str,
    after: tuple[int, bool] | None,
    after_text: str,
) -> _SideDecision | None:
    """OCR_UI_ROADMAP passo 7: the numbering decides when no words did.

    The first line of moves under the diagram (``22...`` is Black's turn,
    ``23 ♘c4`` White's) comes first; a caption "após/after N.x" (the
    position *after* that move) second.  Both sit between the declared text
    and the page scope in the cascade -- more specific than a page header,
    less than a caption that says "Black to move".
    """
    if first_move is not None:
        return _SideDecision(not first_move[1], first_move_text.strip()[:40], "move-number", 0.9)
    if after is not None:
        return _SideDecision(not after[1], after_text.strip()[:60], "caption-after", 0.85)
    return None


def _parse_lines(
    lines: Sequence[_ParsedLine],
    *,
    page_number: int | None,
    below: Sequence[_ParsedLine] = (),
) -> DiagramContext:
    # The caption decides; the neighbourhood answers only when it is silent.
    primary = [item for item in lines if item.primary]
    secondary = [item for item in lines if not item.primary]
    decision = _side_from_tier(primary) or _side_from_tier(secondary)
    captions = [item.text for item in [*primary, *secondary] if item.caption_like]

    first_move, first_move_text = _first_found(below, move_start)
    after, after_text = _first_found([*primary, *secondary], after_move)
    if decision is None:
        decision = _side_from_numbering(first_move, first_move_text, after, after_text)

    exercise_number: int | None = None
    for text in captions:
        # A line of moves opens with a move number, which is not an exercise
        # number: "3.Kxc7 Kf7" next to a diagram gave it ``number=3``.  The
        # test is on what follows the prefix, or "№79. Steinitz" is a move.
        if _MOVE_TEXT.search(_strip_number_prefix(text)):
            continue
        value = _parse_exercise_number(text)
        if value is None or value == page_number:
            continue
        exercise_number = value
        break

    players: tuple[str, str] | None = None
    event: str | None = None
    year: int | None = None
    for text in captions:
        if players is None:
            players = _parse_players(text)
        if year is None:
            line_event, line_year = _parse_event_year(text)
            if line_year is not None:
                event, year = line_event, line_year

    label: str | None = None
    for text in captions:
        match = _COMPOUND_LABEL.match(text)
        if match is not None:
            label = match.group(1)
            break

    return DiagramContext(
        caption="\n".join(item.text for item in lines),
        caption_primary="\n".join(item.text for item in primary if item.caption_like),
        label=label,
        side_to_move=None if decision is None else decision.color,
        side_to_move_evidence="" if decision is None else decision.evidence,
        side_to_move_origin=None if decision is None else decision.origin,
        side_to_move_confidence=1.0 if decision is None else decision.confidence,
        first_move_number=first_move,
        caption_after_move=after,
        exercise_number=exercise_number,
        players=players,
        event=event,
        year=year,
    )


def parse_context(caption: str, *, page_number: int | None = None) -> DiagramContext:
    """Interpret an already-cut caption.  Each field ``None`` unless stated."""
    lines = [line.strip() for line in caption.splitlines() if line.strip()]
    if not lines:
        return DiagramContext()
    return _parse_lines(
        [_ParsedLine(text=line, caption_like=True, primary=True) for line in lines],
        page_number=page_number,
    )


def context_from_lines(
    nearby: Sequence[NearbyLine], *, page_number: int | None = None
) -> DiagramContext:
    """A :class:`DiagramContext` from the lines already assigned to a diagram.

    A paragraph line enters the caption (the exercise commentary is what the
    reader wants) but faces the stricter bar for structured data.  When no
    line was marked primary (no dominant side found), all count as such: one
    tier is better than none.
    """
    if not nearby:
        return DiagramContext()
    has_primary = any(item.primary for item in nearby)
    below = [
        _ParsedLine(text=item.text, caption_like=item.line.is_caption_like,
                    primary=item.primary, origin=item.line.origin,
                    confidence=item.line.confidence)
        for item in sorted(
            (i for i in nearby if i.placement == "below"), key=lambda i: i.line.box[1]
        )
    ]
    return _parse_lines(
        [
            _ParsedLine(
                text=item.text,
                caption_like=item.line.is_caption_like,
                primary=item.primary or not has_primary,
                origin=item.line.origin,
                confidence=item.line.confidence,
            )
            for item in nearby
        ],
        page_number=page_number,
        below=below,
    )


def page_scope_declaration(page: PageText) -> PageScope | None:
    """A side declaration in the margin band, valid for the whole page.

    Worth less than a caption and more than the default "White": the caller
    applies it only where the caption was silent.  A contradiction within the
    band (``White to Move`` on top, ``Black to Move`` at the foot) yields
    ``None`` -- the page is saying both things.
    """
    declarations = [
        (found, line)
        for line in caption_lines(page, margin=True)
        if (found := _side_from_line(line.text, caption_like=True)) is not None
    ]
    if not declarations:
        return None
    if len({color for (color, _), _ in declarations}) > 1:
        return None
    (color, evidence), line = declarations[0]
    origin = "text-page-scope" if line.origin == "text" else "ocr-page-scope"
    return PageScope(color=color, evidence=evidence, origin=origin, confidence=line.confidence)


def apply_page_scope(context: DiagramContext, scope: PageScope | None) -> DiagramContext:
    """The page declaration fills only what the caption left empty."""
    if scope is None or context.side_to_move is not None:
        return context
    return replace(
        context,
        side_to_move=scope.color,
        side_to_move_evidence=scope.evidence,
        side_to_move_origin=scope.origin,
        side_to_move_confidence=scope.confidence,
    )


def page_contexts(
    page: PageText,
    boxes: Sequence[RectT],
    *,
    page_number: int | None = None,
    radius_pt: float = DEFAULT_RADIUS_PT,
) -> tuple[list[DiagramContext], list[RectT]]:
    """One context per diagram box, plus the boxes of the lines it consumed.

    A line that is the *primary, caption-like* text of a diagram belongs to
    that diagram: it is returned so the caller can keep it out of the prose,
    where it would otherwise print a second time as a one-line paragraph
    ("4-10 W?" above every Dvoretsky exercise).  Commentary near a diagram is
    context, not caption, and stays in the flow.
    """
    if not boxes:
        return [], []
    lines = caption_lines(page)
    buckets = assign_lines_to_diagrams(lines, boxes, radius_pt=radius_pt)
    scope = page_scope_declaration(page)
    contexts = [
        apply_page_scope(
            _with_numbering_below(context_from_lines(bucket, page_number=page_number), lines, box),
            scope,
        )
        for bucket, box in zip(buckets, boxes, strict=True)
    ]
    consumed = [
        item.line.box
        for bucket in buckets
        for item in bucket
        if item.primary and item.line.is_caption_like
    ]
    return contexts, consumed


#: OCR_UI_ROADMAP passo 7: how far below a diagram the first line of moves may
#: sit and still count as its continuation -- past the caption radius, because
#: a paragraph of commentary often stands between the board and the moves
#: (SFC4 p. 12: 96 pt).  Same column only.
NUMBERING_REACH_PT: Final = 200.0


def _with_numbering_below(
    context: DiagramContext, lines: Sequence[CaptionLine], box: RectT
) -> DiagramContext:
    """The numbering rule with the longer reach, when the caption bucket had no move line."""
    if context.side_to_move is not None or context.first_move_number is not None:
        return context
    below = sorted(
        (
            (relation[0], line)
            for line in lines
            if (relation := _relate(line.box, box)) is not None
            and relation[1] == "below" and relation[0] <= NUMBERING_REACH_PT
        ),
        key=lambda pair: (pair[0], pair[1].box[1]),
    )
    for _distance, line in below:
        found = move_start(line.text)
        if found is not None:
            decision = _side_from_numbering(found, line.text, None, "")
            if decision is None:  # pragma: no cover - a found move always decides
                return context
            return replace(
                context,
                side_to_move=decision.color,
                side_to_move_evidence=decision.evidence,
                side_to_move_origin=decision.origin,
                side_to_move_confidence=decision.confidence,
                first_move_number=found,
            )
    return context


def contexts_for_page(
    page: PageText,
    boxes: Sequence[RectT],
    *,
    page_number: int | None = None,
    radius_pt: float = DEFAULT_RADIUS_PT,
) -> list[DiagramContext]:
    """One context per diagram box, page scope applied where captions are silent."""
    return page_contexts(page, boxes, page_number=page_number, radius_pt=radius_pt)[0]
