"""The ``GameScore`` block: a game as a tree, not as a line of text (SPEC 5.4).

The model mirrors PGN exactly, which is also the model ``python-chess`` uses, so
importing and exporting are structural walks rather than translations:

* a node's ``children`` are its continuations;
* ``children[0]`` is the main line;
* ``children[1:]`` are the recursive annotation variations offered *instead of*
  ``children[0]``.

So ``1. e4 e5 (1... c5 2. Nf3) 2. Nf3`` becomes ``e4`` with two children, ``e5``
and ``c5``, each carrying its own continuation. Nesting is unbounded, and a
variation is structurally identical to the main line -- which is what makes
"promote this variation to the main line" a tree rotation rather than a reparse.

The IR stays independent of ``python-chess``: nothing here imports it, so a game
score serialises, validates and diffs in an environment where it is absent. The
notation subsystem wraps ``python-chess`` on top of this model to check legality
and to compute FENs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from caissa.core.chess.notation_tables import DEFAULT_LANGUAGE, FigurineSet, MoveRenderStyle
from caissa.core.model.base import IRNode
from caissa.core.model.marks import Mark
from caissa.core.model.props import RunProps
from caissa.core.model.registry import ir_node

__all__ = [
    "SEVEN_TAG_ROSTER",
    "ClockAnnotation",
    "ClockKind",
    "EvalAnnotation",
    "EvalKind",
    "GameHeaders",
    "GameRenderOptions",
    "GameScore",
    "MoveNode",
    "PgnTag",
    "VariationStyle",
    "iter_mainline",
    "iter_move_nodes",
]

#: The PGN Seven Tag Roster, in the order the standard requires them written.
SEVEN_TAG_ROSTER: tuple[str, ...] = (
    "Event",
    "Site",
    "Date",
    "Round",
    "White",
    "Black",
    "Result",
)


class ClockKind(StrEnum):
    """Which PGN clock command a :class:`ClockAnnotation` came from."""

    CLOCK = "clk"
    ELAPSED_MOVE_TIME = "emt"
    ELAPSED_GAME_TIME = "egt"
    MOVE_CLOCK = "mct"


class EvalKind(StrEnum):
    """How an engine evaluation is expressed."""

    CENTIPAWNS = "centipawns"
    MATE = "mate"


class VariationStyle(StrEnum):
    """How variations are laid out on the page.

    A publishing decision with real typographic consequences, so it belongs to
    the document rather than to the exporter.
    """

    INLINE = "inline"
    INDENTED = "indented"
    COLUMNS = "columns"


@ir_node("pgn_tag")
@dataclass(frozen=True, slots=True, kw_only=True)
class PgnTag:
    """One PGN header outside the Seven Tag Roster.

    Kept as an ordered sequence rather than a mapping so that tag order and
    repeated tags survive a round trip byte for byte.

    Attributes:
        name: The tag name, e.g. ``"ECO"`` or ``"WhiteElo"``.
        value: The tag value, verbatim.
    """

    name: str
    value: str


@ir_node("game_headers")
@dataclass(frozen=True, slots=True, kw_only=True)
class GameHeaders:
    """PGN headers: the Seven Tag Roster plus everything else.

    Attributes:
        event: ``Event`` tag.
        site: ``Site`` tag.
        date: ``Date`` tag, in PGN's ``YYYY.MM.DD`` form with ``??`` for
            unknown parts.
        round: ``Round`` tag.
        white: ``White`` tag.
        black: ``Black`` tag.
        result: ``Result`` tag: ``1-0``, ``0-1``, ``1/2-1/2`` or ``*``.
        extra: Every other tag, in file order.
    """

    event: str = "?"
    site: str = "?"
    date: str = "????.??.??"
    round: str = "?"
    white: str = "?"
    black: str = "?"
    result: str = "*"
    extra: tuple[PgnTag, ...] = ()

    def get(self, name: str) -> str | None:
        """Look up any header by name, roster or extra.

        Args:
            name: The tag name; matched case-sensitively, as PGN requires.

        Returns:
            The tag value, or ``None`` when the tag is absent.
        """
        roster = {
            "Event": self.event,
            "Site": self.site,
            "Date": self.date,
            "Round": self.round,
            "White": self.white,
            "Black": self.black,
            "Result": self.result,
        }
        if name in roster:
            return roster[name]
        for tag in self.extra:
            if tag.name == name:
                return tag.value
        return None

    def as_tuples(self) -> tuple[tuple[str, str], ...]:
        """Return every header as ``(name, value)`` in PGN write order.

        Returns:
            The Seven Tag Roster first, then the extra tags in their own order.
        """
        roster = (
            self.event,
            self.site,
            self.date,
            self.round,
            self.white,
            self.black,
            self.result,
        )
        pairs = list(zip(SEVEN_TAG_ROSTER, roster, strict=True))
        pairs.extend((tag.name, tag.value) for tag in self.extra)
        return tuple(pairs)


@ir_node("clock_annotation")
@dataclass(frozen=True, slots=True, kw_only=True)
class ClockAnnotation:
    """A clock reading attached to a move, from a ``[%clk]``-family command.

    Attributes:
        kind: Which command it came from.
        text: The reading exactly as written, e.g. ``"1:23:45"``. Kept verbatim
            so an export reproduces the source.
        seconds: The reading in seconds, when it could be parsed.
    """

    kind: ClockKind = ClockKind.CLOCK
    text: str = ""
    seconds: float | None = None


@ir_node("eval_annotation")
@dataclass(frozen=True, slots=True, kw_only=True)
class EvalAnnotation:
    """An engine evaluation attached to a move, from a ``[%eval]`` command.

    Attributes:
        kind: Centipawn score or forced mate.
        value: Centipawns from White's point of view, or the number of moves to
            mate (negative when Black mates).
        depth: Search depth, when reported.
        text: The evaluation exactly as written.
    """

    kind: EvalKind = EvalKind.CENTIPAWNS
    value: float = 0.0
    depth: int | None = None
    text: str = ""


@ir_node("game_render_options")
@dataclass(frozen=True, slots=True, kw_only=True)
class GameRenderOptions:
    """Presentation defaults for a whole game score.

    Attributes:
        language: BCP-47 tag the moves are printed in.
        render: Figurine, language letters, or both.
        figurine_set: Which glyph set figurine forms use.
        variation_style: How variations are laid out.
        show_result: Whether the result token is printed after the last move.
        show_headers: Whether the header block is printed.
        max_variation_depth: Depth beyond which variations are omitted from the
            printed page. ``None`` prints everything. The IR always keeps them.
        move_props: Character formatting applied to every move.
        comment_props: Character formatting applied to every comment.
        variation_props: Character formatting applied inside variations.
    """

    language: str = DEFAULT_LANGUAGE
    render: MoveRenderStyle = MoveRenderStyle.LETTERS
    figurine_set: FigurineSet = FigurineSet.BLACK
    variation_style: VariationStyle = VariationStyle.INLINE
    show_result: bool = True
    show_headers: bool = True
    max_variation_depth: int | None = None
    move_props: RunProps = field(default_factory=RunProps)
    comment_props: RunProps = field(default_factory=RunProps)
    variation_props: RunProps = field(default_factory=RunProps)


@ir_node("move_node")
@dataclass(frozen=True, slots=True, kw_only=True)
class MoveNode(IRNode):
    """One move in the game tree, with everything PGN can attach to it.

    Attributes:
        san: Canonical English SAN for the move.
        ply: Half-move number from the start of the game, ``1`` for White's
            first move.
        position_before: FEN before the move. Empty when the importer could not
            establish it; the notation subsystem fills it in.
        position_after: FEN after the move.
        uci: Long algebraic form, when known.
        nags: Numeric Annotation Glyphs, ``$1`` through ``$255``.
        comment_before: PGN starting comment -- text printed *before* the move.
        comment_after: PGN comment -- text printed after the move.
        arrows: ``[%cal]`` arrows.
        highlights: ``[%csl]`` highlighted squares.
        clock: Clock reading.
        evaluation: Engine evaluation.
        emphasis: Whether this move is set apart typographically, the "key
            move" treatment used in tactics collections.
        children: Continuations. ``children[0]`` is the main line;
            ``children[1:]`` are variations offered instead of it.
    """

    san: str
    ply: int = 0
    position_before: str = ""
    position_after: str = ""
    uci: str | None = None
    nags: tuple[int, ...] = ()
    comment_before: str = ""
    comment_after: str = ""
    arrows: tuple[Mark, ...] = ()
    highlights: tuple[Mark, ...] = ()
    clock: ClockAnnotation | None = None
    evaluation: EvalAnnotation | None = None
    emphasis: bool = False
    children: tuple[MoveNode, ...] = ()

    @property
    def main_continuation(self) -> MoveNode | None:
        """The next move of the line this node belongs to, if any."""
        return self.children[0] if self.children else None

    @property
    def variations(self) -> tuple[MoveNode, ...]:
        """Alternatives to :attr:`main_continuation`, in PGN order."""
        return self.children[1:]

    @property
    def move_number(self) -> int:
        """The full-move number this ply belongs to."""
        return (max(self.ply, 1) + 1) // 2

    @property
    def is_black_move(self) -> bool:
        """Whether this ply is Black's."""
        return self.ply % 2 == 0 and self.ply > 0


@ir_node("game_score")
@dataclass(frozen=True, slots=True, kw_only=True)
class GameScore(IRNode):
    """A complete game or fragment, headers plus move tree.

    Attributes:
        headers: PGN headers.
        initial_fen: Starting position. ``None`` means the standard array; any
            other value implies the ``SetUp`` and ``FEN`` tags on export.
        variant: Rules variant, e.g. ``"standard"`` or ``"chess960"``.
        initial_comment: Comment printed before the first move.
        children: Opening continuations, same convention as
            :attr:`MoveNode.children`.
        render: Presentation defaults for this score.
        title: Optional heading printed above the score.
        annotator: Who annotated it, when not carried as a PGN tag.
    """

    headers: GameHeaders = field(default_factory=GameHeaders)
    initial_fen: str | None = None
    variant: str = "standard"
    initial_comment: str = ""
    children: tuple[MoveNode, ...] = ()
    render: GameRenderOptions = field(default_factory=GameRenderOptions)
    title: str | None = None
    annotator: str | None = None

    @property
    def result(self) -> str:
        """The game result token from the headers."""
        return self.headers.result

    def mainline(self) -> tuple[MoveNode, ...]:
        """Return the main line, ignoring every variation.

        Returns:
            The moves of the principal line, in order.
        """
        return tuple(iter_mainline(self))

    def move_count(self) -> int:
        """Count every move in the tree, variations included.

        Returns:
            The total number of move nodes.
        """
        return sum(1 for _ in iter_move_nodes(self))


def iter_mainline(score: GameScore) -> list[MoveNode]:
    """Walk the principal line of a game score.

    Args:
        score: The game.

    Returns:
        The main-line moves, in order.
    """
    line: list[MoveNode] = []
    current = score.children[0] if score.children else None
    while current is not None:
        line.append(current)
        current = current.main_continuation
    return line


def iter_move_nodes(score: GameScore) -> list[MoveNode]:
    """Walk every move in a game tree, variations included, depth first.

    Args:
        score: The game.

    Returns:
        Every move node, main line before variations at each branch point.
    """
    collected: list[MoveNode] = []
    stack: list[MoveNode] = list(reversed(score.children))
    while stack:
        node = stack.pop()
        collected.append(node)
        stack.extend(reversed(node.children))
    return collected
