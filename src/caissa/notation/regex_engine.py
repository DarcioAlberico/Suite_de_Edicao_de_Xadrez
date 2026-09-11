"""Regex and chess-aware search over notation -- SPEC 9.

Three things a plain ``re.finditer`` over a book cannot do, and that this module
exists to do instead.

**Scope.**  ``Nf3`` inside a comment is not the same finding as ``Nf3`` in the
main line, and ``1.e4`` inside a caption is not a move at all.  Every search
takes a :class:`Scope`, and the scopes are spans over the *same* raw text, so a
match always carries an offset the editor can select.

**Structure.**  "Every knight capture on d5" is not a text question.  It is a
question about moves, and answering it by regex over the printed page fails on
figurines, on Portuguese, and on ``N3xd5`` vs ``Nbxd5``.  So the engine searches
the *move index* -- SAN plus ply, colour, depth, NAGs and the FEN either side --
and reports text offsets for what it finds.

**Consequence.**  Replace-all over a 900-page book with a bad pattern is
unrecoverable in an editor that applies edits as it finds them.  Substitution
here produces a :class:`SubstitutionPlan` -- every match with its replacement,
individually acceptable or rejectable -- and applying one returns an undo token
that restores the exact previous text.

Engine
------
Uses the ``regex`` package (PCRE-compatible: named groups, lookbehind of
variable width, ``\\p{...}`` Unicode properties, possessive quantifiers) and
falls back to :mod:`re` when it is not installed.  The fallback is not silent:
:data:`PCRE` says which one is live, and patterns that need the real thing raise
:class:`PatternError` with that fact in the message.
"""

from __future__ import annotations

import importlib
import re as _stdlib_re
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import ModuleType
from typing import Any, Final, Iterable, Iterator, Mapping, Protocol, Sequence, cast

import chess

__all__ = [
    "PCRE",
    "ENGINE_NAME",
    "AnnotationQuery",
    "EcoQuery",
    "MaterialSignature",
    "Match",
    "MoveQuery",
    "MoveRecord",
    "PatternError",
    "PlannedEdit",
    "PositionPattern",
    "RegexEngine",
    "Region",
    "Scope",
    "SearchDocument",
    "SubstitutionPlan",
    "SubstitutionResult",
    "UndoStack",
    "build_move_index",
    "compile_move_pattern",
]

def _load_engine() -> tuple[ModuleType, bool]:
    """``regex`` if it is installed, otherwise stdlib ``re``.

    Loaded by name rather than with a bare ``import regex`` so that the fallback
    is a value the module can report, not a shape mypy has to be told to ignore.
    """
    try:
        return (importlib.import_module("regex"), True)
    except ImportError:  # pragma: no cover - depends on the environment
        return (_stdlib_re, False)


_ENGINE, _HAVE_PCRE = _load_engine()

#: ``True`` when the PCRE-compatible ``regex`` package is driving the searches.
PCRE: Final[bool] = _HAVE_PCRE
ENGINE_NAME: Final[str] = "regex" if _HAVE_PCRE else "re"


class PatternError(ValueError):
    """A pattern that will not compile, with the engine that refused it named."""


class _Pattern(Protocol):
    """The slice of a compiled pattern this module uses, from either engine."""

    def finditer(self, string: str, pos: int = ..., endpos: int = ...) -> Iterator[Any]: ...

    def fullmatch(self, string: str) -> Any: ...

    @property
    def pattern(self) -> str: ...


#: Flag values, spelled here so callers never import the engine themselves.
IGNORECASE: Final[int] = int(_ENGINE.IGNORECASE)
MULTILINE: Final[int] = int(_ENGINE.MULTILINE)
DOTALL: Final[int] = int(_ENGINE.DOTALL)
VERBOSE: Final[int] = int(_ENGINE.VERBOSE)


def compile_pattern(pattern: str, flags: int = 0) -> _Pattern:
    """Compile ``pattern``, raising :class:`PatternError` with useful context."""
    try:
        return cast(_Pattern, _ENGINE.compile(pattern, flags))
    except Exception as error:  # noqa: BLE001 - both engines raise their own type
        hint = "" if PCRE else " (the `regex` package is not installed; running on stdlib `re`)"
        raise PatternError(f"{pattern!r}: {error}{hint}") from error


# --------------------------------------------------------------------------- #
# Scoped document
# --------------------------------------------------------------------------- #


class Scope(StrEnum):
    """Where in a document a search is allowed to look."""

    ALL = "all"
    HEADERS = "headers"
    MOVES = "moves"
    COMMENTS = "comments"
    CAPTIONS = "captions"
    VARIATIONS = "variations"
    MAINLINE = "mainline"

    @property
    def is_move_scope(self) -> bool:
        return self in (Scope.MOVES, Scope.VARIATIONS, Scope.MAINLINE)


@dataclass(frozen=True)
class Region:
    """A labelled span of the raw text.

    Regions may overlap: a move inside a variation is in both ``MOVES`` and
    ``VARIATIONS``, and asking for either finds it.  That is why a region is a
    label on a span rather than a partition of the document.
    """

    scope: Scope
    start: int
    end: int
    depth: int = 0
    """Variation nesting depth; 0 is the main line."""

    def contains(self, start: int, end: int) -> bool:
        return self.start <= start and end <= self.end


@dataclass(frozen=True)
class SearchDocument:
    """Raw text plus the regions a search can be restricted to."""

    text: str
    regions: tuple[Region, ...] = ()
    moves: tuple[MoveRecord, ...] = ()
    headers: Mapping[str, str] = field(default_factory=dict)

    def spans_for(self, scope: Scope) -> tuple[tuple[int, int], ...]:
        """The searchable spans for ``scope``, merged and in document order.

        ``Scope.ALL`` is the whole text and not the union of the regions: text
        that no region claims (page furniture, stray prose) is still text, and a
        user who did not ask for a scope asked for everything.
        """
        if scope is Scope.ALL:
            return ((0, len(self.text)),)
        spans = sorted(
            (region.start, region.end) for region in self.regions if region.scope is scope
        )
        return _merge_spans(spans)


def _merge_spans(spans: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)


@dataclass(frozen=True)
class MoveRecord:
    """One move as the structured search sees it."""

    san: str
    """Canonical English SAN -- the search language, whatever the page printed."""

    ply: int
    number: int
    """Full-move number as printed."""

    turn: bool
    """``chess.WHITE`` / ``chess.BLACK``: the side that played it."""

    depth: int = 0
    is_mainline: bool = True
    nags: tuple[str, ...] = ()
    """Glyphs and ``$n`` codes attached to the move, e.g. ``("??",)``."""

    comment: str = ""
    fen_before: str = ""
    fen_after: str = ""
    start: int = -1
    end: int = -1
    """Offsets into the document text, or ``-1`` when the move came from a PGN
    rather than from an edited buffer."""

    display: str = ""
    """What the page actually printed, when it differs from :attr:`san`."""

    @property
    def piece(self) -> str:
        """English piece letter, ``"K"`` for castling, ``""`` for a pawn move."""
        if self.san.startswith("O-O"):
            return "K"
        return self.san[0] if self.san[:1] in "KQRBN" else ""

    @property
    def is_capture(self) -> bool:
        return "x" in self.san

    @property
    def is_check(self) -> bool:
        return self.san.endswith("+")

    @property
    def is_mate(self) -> bool:
        return self.san.endswith("#")

    @property
    def to_square(self) -> str:
        match = _stdlib_re.search(r"([a-h][1-8])(?:=[QRBN])?[+#]?$", self.san)
        return match.group(1) if match else ""

    @property
    def promotion(self) -> str:
        match = _stdlib_re.search(r"=([QRBN])", self.san)
        return match.group(1) if match else ""


# --------------------------------------------------------------------------- #
# Building a searchable document from what the rest of the front produces
# --------------------------------------------------------------------------- #


def build_move_index(
    pgn_or_ast: Any,
    *,
    start_fen: str = chess.STARTING_FEN,
) -> tuple[MoveRecord, ...]:
    """Flatten a :class:`~caissa.notation.parser.GameAST` into move records.

    Accepts the AST the tolerant parser produces.  Variations are walked
    depth-first so that ``depth`` and ``is_mainline`` are meaningful, and each
    record carries the FEN either side, which is what the position and material
    queries need.

    The position for each node comes from the node's own ``parent_fen`` when the
    parser set one, and only falls back to replaying from the parent line when
    it did not.  That matters for variations: the parser anchors a line either
    *before* or *after* the move it hangs off (``variation_anchor_after``), and
    a walker that assumed one of the two silently indexed half the variations
    from the wrong position -- producing plausible, wrong SAN.
    """
    records: list[MoveRecord] = []

    def walk(moves: Sequence[Any], fen: str, depth: int) -> None:
        board = chess.Board(fen)
        for node in moves:
            san = str(getattr(node, "display_san", None) or getattr(node, "san", ""))
            parent_fen = getattr(node, "parent_fen", None)
            if parent_fen:
                board = chess.Board(parent_fen)
            before = board.fen()
            try:
                move = board.parse_san(san)
            except (ValueError, AssertionError):
                # An unresolved token: it keeps its place in the tree but cannot
                # be indexed as a move.  Its variations still can, from here.
                for variation in getattr(node, "variations", ()) or ():
                    walk(variation, before, depth + 1)
                continue
            canonical = board.san(move)
            snapshot = chess.Board(before)
            board.push(move)
            records.append(
                MoveRecord(
                    san=canonical,
                    ply=len(records),
                    number=snapshot.fullmove_number,
                    turn=snapshot.turn,
                    depth=depth,
                    is_mainline=depth == 0,
                    nags=tuple(getattr(node, "nags", ()) or ()),
                    comment=" ".join(getattr(node, "comments_after", ()) or ()),
                    fen_before=before,
                    fen_after=board.fen(),
                    start=getattr(node, "san_start_index", -1),
                    end=getattr(node, "san_end_index", -1),
                    display=getattr(node, "raw_text", "") or "",
                )
            )
            for variation in getattr(node, "variations", ()) or ():
                walk(variation, before, depth + 1)

    walk(getattr(pgn_or_ast, "moves", pgn_or_ast), start_fen, 0)
    return tuple(records)


def document_from_ast(
    text: str,
    ast: Any,
    *,
    start_fen: str = chess.STARTING_FEN,
    captions: Sequence[tuple[int, int]] = (),
) -> SearchDocument:
    """Wrap a parsed game as a :class:`SearchDocument` with every scope filled in.

    ``captions`` is supplied by the caller because captions live in the Document
    IR (SPEC 5.3), not in the game tree -- the ingest front knows where they are
    and this module must not guess.
    """
    regions: list[Region] = []
    records = build_move_index(ast, start_fen=start_fen)

    for record in records:
        if record.start < 0:
            continue
        regions.append(Region(Scope.MOVES, record.start, record.end, record.depth))
        regions.append(
            Region(
                Scope.MAINLINE if record.is_mainline else Scope.VARIATIONS,
                record.start,
                record.end,
                record.depth,
            )
        )

    for start, end in _comment_spans(text):
        regions.append(Region(Scope.COMMENTS, start, end))
    for start, end in _header_spans(text):
        regions.append(Region(Scope.HEADERS, start, end))
    for start, end in captions:
        regions.append(Region(Scope.CAPTIONS, start, end))

    headers = {
        match.group(1): match.group(2)
        for match in _stdlib_re.finditer(r'^\[(\w+)\s+"([^"]*)"\]', text, _stdlib_re.MULTILINE)
    }
    return SearchDocument(text=text, regions=tuple(regions), moves=records, headers=headers)


def _comment_spans(text: str) -> Iterable[tuple[int, int]]:
    from .normalizer import COMMENT_RE

    for match in COMMENT_RE.finditer(text):
        yield match.span()


def _header_spans(text: str) -> Iterable[tuple[int, int]]:
    for match in _stdlib_re.finditer(r'^\[\w+\s+"[^"]*"\]', text, _stdlib_re.MULTILINE):
        yield match.span()


# --------------------------------------------------------------------------- #
# Matches
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Match:
    """One hit, with everything the UI needs to show and act on it."""

    start: int
    end: int
    text: str
    scope: Scope = Scope.ALL
    groups: Mapping[str, str] = field(default_factory=dict)
    """Named groups only -- positional ones are in :attr:`numbered`."""

    numbered: tuple[str | None, ...] = ()
    move: MoveRecord | None = None
    """Set when the match came from the structured index rather than the text."""

    def context(self, text: str, width: int = 40) -> str:
        """The match with up to ``width`` characters either side, for a result list."""
        left = max(0, self.start - width)
        right = min(len(text), self.end + width)
        return text[left:right].replace("\n", " ")


# --------------------------------------------------------------------------- #
# Chess-aware primitives
# --------------------------------------------------------------------------- #

_GLOB_SPECIALS: Final[str] = ".^$+{}[]|()\\"


def compile_move_pattern(spec: str, flags: int = 0) -> _Pattern:
    """Compile a move pattern into a regex over canonical SAN.

    The little language, in full:

    * ``*`` -- any run of characters, including none.  ``N*xd5`` is "a knight
      capture on d5", covering ``Nxd5``, ``Nbxd5``, ``N3xd5`` and ``Ne3xd5``.
    * ``?`` -- exactly one character.
    * ``re:`` prefix -- the rest is a raw regex, for anything the glob cannot
      say (``re:^[QR][a-h]?x?h[1-8][+#]$``).

    The check/mate mark is optional in every glob pattern: a user searching for
    ``Qxh7`` means the move, not the mark, and a pattern that missed ``Qxh7#``
    would be worse than useless.  Anchoring is implicit -- ``e4`` matches the
    move ``e4`` and not the ``e4`` inside ``Nxe4``.
    """
    if spec.startswith("re:"):
        return compile_pattern(spec[3:], flags)
    body = "".join(
        ".*" if char == "*" else "." if char == "?" else
        ("\\" + char if char in _GLOB_SPECIALS else char)
        for char in spec
    )
    suffix = "" if spec.rstrip("*?").endswith(("+", "#")) else "[+#]?"
    return compile_pattern(rf"^{body}{suffix}$", flags)


@dataclass(frozen=True)
class MoveQuery:
    """A structured question about moves, every field ``None`` meaning "don't care"."""

    pattern: str | None = None
    """A :func:`compile_move_pattern` spec, e.g. ``"N*xd5"``."""

    piece: str | None = None
    to_square: str | None = None
    is_capture: bool | None = None
    is_check: bool | None = None
    is_mate: bool | None = None
    promotion: str | None = None
    turn: bool | None = None
    nag: str | None = None
    """Exact annotation to require, e.g. ``"??"`` or ``"$4"``."""

    min_ply: int | None = None
    max_ply: int | None = None
    mainline_only: bool = False
    position: PositionPattern | None = None
    material: MaterialSignature | None = None

    def matches(self, record: MoveRecord) -> bool:
        """Does ``record`` satisfy every stated field?"""
        if self.pattern is not None and not compile_move_pattern(self.pattern).fullmatch(record.san):
            return False
        if self.piece is not None and record.piece != self.piece:
            return False
        if self.to_square is not None and record.to_square != self.to_square:
            return False
        if self.is_capture is not None and record.is_capture != self.is_capture:
            return False
        if self.is_check is not None and record.is_check != self.is_check:
            return False
        if self.is_mate is not None and record.is_mate != self.is_mate:
            return False
        if self.promotion is not None and record.promotion != self.promotion:
            return False
        if self.turn is not None and record.turn != self.turn:
            return False
        if self.nag is not None and self.nag not in record.nags:
            return False
        if self.min_ply is not None and record.ply < self.min_ply:
            return False
        if self.max_ply is not None and record.ply > self.max_ply:
            return False
        if self.mainline_only and not record.is_mainline:
            return False
        if self.position is not None and not self.position.matches(record.fen_after):
            return False
        return not (self.material is not None and not self.material.matches(record.fen_after))


@dataclass(frozen=True)
class AnnotationQuery:
    """"All moves marked ``??``" -- the shorthand, since it is asked constantly."""

    glyph: str

    def as_move_query(self) -> MoveQuery:
        return MoveQuery(nag=self.glyph)


@dataclass(frozen=True)
class EcoQuery:
    """Match the ``ECO`` header against a regex.

    ``EcoQuery("B9[0-9]")`` is the Najdorf complex; ``EcoQuery("C")`` is every
    open game.  Anchored at the start so ``"B90"`` does not match ``"AB90"``.
    """

    pattern: str

    def matches(self, headers: Mapping[str, str]) -> bool:
        eco = headers.get("ECO", "")
        if not eco:
            return False
        return next(compile_pattern(f"^(?:{self.pattern})").finditer(eco), None) is not None


@dataclass(frozen=True)
class PositionPattern:
    """A board pattern with wildcards, matched against a FEN.

    The placement string is FEN piece-placement with two additions: ``?``
    matches any single square (occupied or not) and ``*`` at the end of a rank
    fills the rest of it with wildcards.  So::

        PositionPattern("????????/????????/????????/????????/????????/"
                        "????????/????????/????????")

    matches every position, and a rank written ``r?b?k??r`` pins the pieces it
    names and leaves the rest open.

    :attr:`turn` and :attr:`requires` add the two constraints a placement string
    cannot express: whose move it is, and "this piece is somewhere on this
    square" for a handful of squares (which is how most real queries are
    phrased -- "white bishop on g5").
    """

    placement: str | None = None
    turn: bool | None = None
    requires: Mapping[str, str] = field(default_factory=dict)
    """Square name -> piece symbol, e.g. ``{"g5": "B", "d5": "n"}``.  Upper case
    is White, lower case is Black, exactly as in FEN."""

    forbids: Mapping[str, str] = field(default_factory=dict)

    def matches(self, fen: str) -> bool:
        if not fen:
            return False
        board = chess.Board(fen)
        if self.turn is not None and board.turn != self.turn:
            return False
        for square_name, symbol in self.requires.items():
            piece = board.piece_at(chess.parse_square(square_name))
            if piece is None or piece.symbol() != symbol:
                return False
        for square_name, symbol in self.forbids.items():
            piece = board.piece_at(chess.parse_square(square_name))
            if piece is not None and piece.symbol() == symbol:
                return False
        return self.placement is None or self._placement_matches(board)

    def _placement_matches(self, board: chess.Board) -> bool:
        assert self.placement is not None
        actual = board.board_fen().split("/")
        wanted = self.placement.split("/")
        if len(wanted) != 8:
            return False
        for rank_index, rank in enumerate(wanted):
            expanded = _expand_rank(rank)
            if expanded is None:
                return False
            real = _expand_rank(actual[rank_index])
            if real is None:  # pragma: no cover - a FEN from `chess` is always valid
                return False
            for wanted_square, real_square in zip(expanded, real, strict=True):
                if wanted_square != "?" and wanted_square != real_square:
                    return False
        return True


def _expand_rank(rank: str) -> list[str] | None:
    """One FEN rank as eight single-character squares; ``.`` is empty, ``?`` any."""
    squares: list[str] = []
    for char in rank:
        if char.isdigit():
            squares.extend("." * int(char))
        elif char == "*":
            squares.extend("?" * (8 - len(squares)))
        else:
            squares.append(char)
    return squares if len(squares) == 8 else None


_PIECE_ORDER: Final[str] = "KQRBNP"


@dataclass(frozen=True)
class MaterialSignature:
    """What is on the board, as a query.

    Two ways to use it.  As an **exact** signature, ``MaterialSignature.parse
    ("KRPvKR")`` matches only positions with exactly those pieces -- the shape
    an endgame tablebase name has, and the one an endgame book indexes by.  As a
    **predicate**, the flags express the questions books actually ask:
    ``opposite_bishops=True, max_pawns=6`` is SPEC 9's own example.
    """

    white: str = ""
    """Piece letters, most valuable first, e.g. ``"KRP"``.  Empty = don't care."""

    black: str = ""
    opposite_bishops: bool | None = None
    max_pawns: int | None = None
    min_pawns: int | None = None

    @classmethod
    def parse(cls, spec: str) -> MaterialSignature:
        """``"KRPvKR"`` or ``"KRP v KR"`` -> a signature."""
        parts = _stdlib_re.split(r"\s*[vV]s?\.?\s*", spec.strip(), maxsplit=1)
        if len(parts) != 2:
            raise PatternError(f"material signature {spec!r} needs a 'v' between the sides")
        return cls(white=_canonical_material(parts[0]), black=_canonical_material(parts[1]))

    @classmethod
    def from_board(cls, board: chess.Board) -> MaterialSignature:
        return cls(
            white=_material_of(board, chess.WHITE),
            black=_material_of(board, chess.BLACK),
        )

    def matches(self, fen: str) -> bool:
        if not fen:
            return False
        board = chess.Board(fen)
        if self.white and _material_of(board, chess.WHITE) != self.white:
            return False
        if self.black and _material_of(board, chess.BLACK) != self.black:
            return False
        pawns = len(board.pieces(chess.PAWN, chess.WHITE)) + len(board.pieces(chess.PAWN, chess.BLACK))
        if self.max_pawns is not None and pawns > self.max_pawns:
            return False
        if self.min_pawns is not None and pawns < self.min_pawns:
            return False
        if self.opposite_bishops is not None:
            if _has_opposite_bishops(board) != self.opposite_bishops:
                return False
        return True

    def __str__(self) -> str:
        return f"{self.white or '*'}v{self.black or '*'}"


def _material_of(board: chess.Board, colour: chess.Color) -> str:
    out: list[str] = []
    for letter, piece_type in zip(
        _PIECE_ORDER,
        (chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN),
        strict=True,
    ):
        out.append(letter * len(board.pieces(piece_type, colour)))
    return "".join(out)


def _canonical_material(spec: str) -> str:
    letters = [char for char in spec.upper() if char in _PIECE_ORDER]
    return "".join(sorted(letters, key=_PIECE_ORDER.index))


def _has_opposite_bishops(board: chess.Board) -> bool:
    """Exactly one bishop each, on squares of different colours.

    The strict reading, and the right one: "opposite-coloured bishops" is an
    endgame term, and a position with two bishops a side is not one.
    """
    white = board.pieces(chess.BISHOP, chess.WHITE)
    black = board.pieces(chess.BISHOP, chess.BLACK)
    if len(white) != 1 or len(black) != 1:
        return False
    return _square_colour(next(iter(white))) != _square_colour(next(iter(black)))


def _square_colour(square: chess.Square) -> int:
    """0 for a dark square, 1 for a light one."""
    return (chess.square_rank(square) + chess.square_file(square)) % 2


# --------------------------------------------------------------------------- #
# Substitution: plan, preview, apply, undo
# --------------------------------------------------------------------------- #


@dataclass
class PlannedEdit:
    """One match and what it would become.  Accepted by default."""

    match: Match
    replacement: str
    accepted: bool = True

    @property
    def before(self) -> str:
        return self.match.text

    def describe(self) -> str:
        state = "keep" if self.accepted else "skip"
        return f"[{state}] {self.match.start}:{self.match.end} {self.before!r} -> {self.replacement!r}"


@dataclass(frozen=True)
class SubstitutionResult:
    """The outcome of applying a plan, with everything needed to take it back."""

    text: str
    applied: int
    skipped: int
    previous_text: str

    def undo(self) -> str:
        """The text as it was before this substitution."""
        return self.previous_text


class SubstitutionPlan:
    """Every replacement a pattern would make, before any of them happen.

    Nothing here mutates the document.  :meth:`preview` renders the result of
    the currently accepted edits, :meth:`apply` returns a
    :class:`SubstitutionResult` carrying the old text, and the caller decides
    what to do with either.
    """

    def __init__(self, text: str, edits: Sequence[PlannedEdit]) -> None:
        self._text = text
        # Left to right, so indices in the report read in document order; the
        # application walks them backwards so earlier edits do not move later
        # ones.
        self._edits: list[PlannedEdit] = sorted(edits, key=lambda edit: edit.match.start)

    def __len__(self) -> int:
        return len(self._edits)

    def __iter__(self) -> Iterator[PlannedEdit]:
        return iter(self._edits)

    def __getitem__(self, index: int) -> PlannedEdit:
        return self._edits[index]

    @property
    def text(self) -> str:
        return self._text

    @property
    def accepted(self) -> tuple[PlannedEdit, ...]:
        return tuple(edit for edit in self._edits if edit.accepted)

    def accept(self, index: int) -> None:
        self._edits[index].accepted = True

    def reject(self, index: int) -> None:
        self._edits[index].accepted = False

    def accept_all(self) -> None:
        for edit in self._edits:
            edit.accepted = True

    def reject_all(self) -> None:
        for edit in self._edits:
            edit.accepted = False

    def describe(self) -> str:
        """One line per match: position, old text, new text, accept state."""
        return "\n".join(f"{index:4d} {edit.describe()}" for index, edit in enumerate(self._edits))

    def preview(self) -> str:
        """The text that :meth:`apply` would produce, without producing it."""
        out = self._text
        for edit in sorted(self.accepted, key=lambda item: item.match.start, reverse=True):
            out = out[: edit.match.start] + edit.replacement + out[edit.match.end :]
        return out

    def apply(self) -> SubstitutionResult:
        """Apply the accepted edits and return the result with an undo payload."""
        accepted = self.accepted
        return SubstitutionResult(
            text=self.preview(),
            applied=len(accepted),
            skipped=len(self._edits) - len(accepted),
            previous_text=self._text,
        )


class UndoStack:
    """A linear undo history of whole-document states.

    Whole states, not diffs: a book chapter is a few hundred kilobytes, a
    substitution touches an unbounded number of places at once, and a diff-based
    stack that gets one hunk wrong corrupts the document in a way the user
    cannot see.  Memory is the cheap resource here.
    """

    def __init__(self, initial: str, limit: int = 100) -> None:
        self._states: list[str] = [initial]
        self._cursor = 0
        self._limit = max(1, limit)

    @property
    def current(self) -> str:
        return self._states[self._cursor]

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor + 1 < len(self._states)

    def push(self, text: str) -> None:
        """Record a new state, discarding any redo branch."""
        del self._states[self._cursor + 1 :]
        self._states.append(text)
        if len(self._states) > self._limit:
            del self._states[0]
        self._cursor = len(self._states) - 1

    def undo(self) -> str:
        if self.can_undo:
            self._cursor -= 1
        return self.current

    def redo(self) -> str:
        if self.can_redo:
            self._cursor += 1
        return self.current


# --------------------------------------------------------------------------- #
# The engine
# --------------------------------------------------------------------------- #


class RegexEngine:
    """Scoped regex and chess-aware search over a :class:`SearchDocument`."""

    def __init__(self, *, flags: int = 0) -> None:
        self.flags = flags

    # -- text ------------------------------------------------------------- #

    def search(
        self,
        pattern: str,
        document: SearchDocument | str,
        *,
        scope: Scope = Scope.ALL,
        flags: int | None = None,
        limit: int | None = None,
    ) -> list[Match]:
        """Find ``pattern`` in ``document``, restricted to ``scope``.

        Named groups come back in :attr:`Match.groups`; positional ones in
        :attr:`Match.numbered`.  Offsets are always into the *whole* document,
        never into the scope slice -- an offset a caller cannot select is not an
        offset.
        """
        doc = document if isinstance(document, SearchDocument) else SearchDocument(text=document)
        compiled = compile_pattern(pattern, self.flags if flags is None else flags)
        found: list[Match] = []
        for start, end in doc.spans_for(scope):
            for raw in compiled.finditer(doc.text, start, end):
                found.append(
                    Match(
                        start=raw.start(),
                        end=raw.end(),
                        text=raw.group(0),
                        scope=scope,
                        groups={k: v for k, v in (raw.groupdict() or {}).items() if v is not None},
                        numbered=tuple(raw.groups()),
                    )
                )
                if limit is not None and len(found) >= limit:
                    return found
        found.sort(key=lambda match: match.start)
        return found

    # -- structure -------------------------------------------------------- #

    def search_moves(
        self,
        document: SearchDocument,
        query: MoveQuery | AnnotationQuery | str,
        *,
        scope: Scope = Scope.MOVES,
    ) -> list[Match]:
        """Find moves matching ``query`` in the structured index.

        ``query`` may be a :class:`MoveQuery`, an :class:`AnnotationQuery`, or a
        bare move pattern string (``"N*xd5"``).  ``scope`` narrows to the main
        line or to variations; :data:`Scope.MOVES` is both.
        """
        if isinstance(query, str):
            query = MoveQuery(pattern=query)
        elif isinstance(query, AnnotationQuery):
            query = query.as_move_query()
        if scope is Scope.MAINLINE:
            query = replace(query, mainline_only=True)

        found: list[Match] = []
        for record in document.moves:
            if scope is Scope.VARIATIONS and record.is_mainline:
                continue
            if not query.matches(record):
                continue
            found.append(
                Match(
                    start=record.start,
                    end=record.end,
                    text=record.san,
                    scope=scope,
                    move=record,
                )
            )
        return found

    def search_positions(
        self,
        document: SearchDocument,
        pattern: PositionPattern | MaterialSignature,
    ) -> list[Match]:
        """Every move after which the position satisfies ``pattern``."""
        query = (
            MoveQuery(position=pattern)
            if isinstance(pattern, PositionPattern)
            else MoveQuery(material=pattern)
        )
        return self.search_moves(document, query)

    @staticmethod
    def matches_eco(document: SearchDocument, query: EcoQuery | str) -> bool:
        """Does this document's ``ECO`` header match?"""
        eco = query if isinstance(query, EcoQuery) else EcoQuery(query)
        return eco.matches(document.headers)

    # -- substitution ----------------------------------------------------- #

    def plan_substitution(
        self,
        pattern: str,
        replacement: str,
        document: SearchDocument | str,
        *,
        scope: Scope = Scope.ALL,
        flags: int | None = None,
    ) -> SubstitutionPlan:
        """Build the plan for ``pattern`` -> ``replacement``, applying nothing.

        ``replacement`` uses the engine's own syntax, so ``\\g<name>`` and
        ``\\1`` work.  Group expansion happens per match, which is why the plan
        can show the *actual* replacement text for every hit instead of the
        template.
        """
        doc = document if isinstance(document, SearchDocument) else SearchDocument(text=document)
        compiled = compile_pattern(pattern, self.flags if flags is None else flags)
        edits: list[PlannedEdit] = []
        for start, end in doc.spans_for(scope):
            for raw in compiled.finditer(doc.text, start, end):
                edits.append(
                    PlannedEdit(
                        match=Match(
                            start=raw.start(),
                            end=raw.end(),
                            text=raw.group(0),
                            scope=scope,
                            groups={
                                k: v for k, v in (raw.groupdict() or {}).items() if v is not None
                            },
                            numbered=tuple(raw.groups()),
                        ),
                        replacement=raw.expand(replacement),
                    )
                )
        return SubstitutionPlan(doc.text, edits)
