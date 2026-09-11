"""What gets indexed, and how each kind of corpus is streamed into it.

A source turns one thing in the library into a sequence of :class:`IndexUnit` --
the smallest thing a search result can point at.  Everything downstream is
uniform, so adding EPUB or DOCX later is one class here and nothing anywhere
else.

**The unit is a node, not a page and not a file.**  SPEC 9 asks a hit to point
at "this caption, this move, this comment, this heading", so that is the
granularity: a caption is one unit carrying the diagram's FEN, a game is one
unit carrying its headers and its positions.  Indexing whole pages would make
every hit say "somewhere on page 214".

**Every source streams.**  ``units()`` is a generator and nothing accumulates:
a 10 GB PGN is read in fixed-size blocks and yields one game at a time, so peak
memory is a block plus a game, not a file.  The gate for this front is measured
on ``PGN_Database.pgn`` (10.3 GB) and that is only achievable if no stage of the
pipeline is allowed to hold a list.

**Resumability is a byte offset.**  ``units(start=...)`` restarts from where a
cancelled pass stopped.  For a PGN that is a file position; for a paginated
document it is a page number.  It is stored in ``documents.cursor``, which is
why re-indexing after a crash costs the remainder rather than the whole.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from caissa.core.model import (
    CodeBlock,
    Diagram,
    Document,
    Figure,
    GameScore,
    Heading,
    MoveNode,
    Paragraph,
    plain_text,
    walk,
)
from caissa.notation.nag_table import NAG_BY_CODE
from caissa.notation.regex_engine import Scope

if TYPE_CHECKING:  # pragma: no cover - typing only
    from caissa.core.model import IRNode

__all__ = [
    "Facets",
    "IndexUnit",
    "IrSource",
    "PdfTextSource",
    "PgnSource",
    "PositionRef",
    "Source",
    "TextSource",
    "content_key_for",
]


@dataclass(frozen=True, slots=True)
class Facets:
    """Structured fields a query can filter on without touching the text.

    Kept separate from the text because "every Najdorf Karpov played after 1980"
    is a ``WHERE`` clause, and running it as a full-text query would be both
    slower and wrong (a game whose *comment* says "Najdorf" is not a Najdorf).
    """

    white: str = ""
    black: str = ""
    eco: str = ""
    year: int = 0
    result: str = ""


@dataclass(frozen=True, slots=True)
class PositionRef:
    """One position this unit contains, ready for the Zobrist index."""

    placement: str
    ply: int = 0
    turn: bool = True


@dataclass(frozen=True, slots=True)
class IndexUnit:
    """One indexable node.

    Attributes:
        text: The reading text.  Always present for tokenizing; whether it is
            *stored* is :attr:`store_text`.
        scope: Which :class:`~caissa.notation.regex_engine.Scope` this text
            belongs to, so a search can be restricted to captions or comments.
        node_ulid: The IR node's id when there is one -- the jump target.
        page: 1-based page number, or ``-1``.
        byte_start: Offset of :attr:`text` in the source file, or ``-1``.
        byte_len: Length in bytes at :attr:`byte_start`.
        store_text: Store the text in the index.  ``False`` when
            ``(byte_start, byte_len)`` can recover it, which is how a PGN of
            twenty million games costs postings and not gigabytes of copies.
        facets: Structured fields, when the unit has them.
        positions: Positions to add to the Zobrist index.
        cursor: What to pass as ``units(start=...)`` to resume *after* this
            unit.  ``-1`` means "count units", which is right for a source whose
            units are a simple sequence.  A source that skips inputs -- a PDF
            with blank pages, a PGN with junk between games -- must set it, or a
            resumed pass restarts from the wrong place.
    """

    text: str
    scope: Scope = Scope.ALL
    node_ulid: str = ""
    page: int = -1
    byte_start: int = -1
    byte_len: int = 0
    store_text: bool = True
    facets: Facets | None = None
    positions: tuple[PositionRef, ...] = ()
    cursor: int = -1


class Source(Protocol):
    """What the indexer needs from anything indexable."""

    @property
    def uri(self) -> str:
        """Stable identity of the document -- normally an absolute path."""

    @property
    def title(self) -> str:
        """Human-readable name for a result list."""

    @property
    def kind(self) -> str:
        """``"pdf"``, ``"pgn"``, ``"ir"``, ``"text"``."""

    @property
    def size_bytes(self) -> int:
        """Size of the source, for the budget and for the 15 % gate."""

    @property
    def content_key(self) -> str:
        """Fingerprint.  Equal key means "already indexed, do not read"."""

    def units(self, *, start: int = 0) -> Iterator[IndexUnit]:
        """Stream the units, resuming at ``start``."""


def content_key_for(path: Path) -> str:
    """Size and mtime as one string.

    Not a hash of the content: hashing a 10 GB file to decide whether to read a
    10 GB file is not a saving.  Size plus nanosecond mtime misses only a change
    that preserves both, which no editor and no download produces.
    """
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


# --------------------------------------------------------------------------- #
# Plain text -- the shape tests use
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TextSource:
    """A string, as one unit per paragraph.  Used by tests and by pasted text."""

    uri: str
    text: str
    title: str = ""
    kind: str = "text"
    scope: Scope = Scope.ALL

    @property
    def size_bytes(self) -> int:
        return len(self.text.encode("utf-8"))

    @property
    def content_key(self) -> str:
        return f"{len(self.text)}:{hash(self.text) & 0xFFFFFFFF:08x}"

    def units(self, *, start: int = 0) -> Iterator[IndexUnit]:
        for ordinal, block in enumerate(self.text.split("\n\n")):
            if ordinal < start or not block.strip():
                continue
            yield IndexUnit(text=block, scope=self.scope)


# --------------------------------------------------------------------------- #
# Document IR -- the path SPEC 9 asks for
# --------------------------------------------------------------------------- #

#: Only the nodes whose ``content`` is *inlines* appear here.  ``Quote``,
#: ``Callout``, ``ListItem`` and ``TableCell`` hold blocks, and their paragraphs
#: are walked in their own right -- indexing the container as well would file
#: every quoted sentence twice and double the postings for nothing.
_SCOPE_BY_TAG: Final[dict[type, Scope]] = {
    Heading: Scope.HEADERS,
    Paragraph: Scope.ALL,
    CodeBlock: Scope.ALL,
}


@dataclass(frozen=True, slots=True)
class IrSource:
    """A :class:`~caissa.core.model.Document` walked into units.

    The mapping from node type to scope is the whole point of indexing the IR
    rather than a flattened string: a ``Diagram``'s caption is a caption, a
    ``MoveNode``'s comment is a comment, and a ``Heading`` is a heading.  Once
    that is in the index, "só legendas" is a ``WHERE`` clause instead of a
    heuristic over raw text.

    Diagrams and game scores also contribute *positions*, which is what makes
    "which of my books shows this?" answerable at all.
    """

    document: Document
    uri: str
    title: str = ""
    kind: str = "ir"
    index_positions: bool = True

    @property
    def size_bytes(self) -> int:
        return sum(len(unit.text.encode("utf-8")) for unit in self.units())

    @property
    def content_key(self) -> str:
        return str(self.document.id)

    def units(self, *, start: int = 0) -> Iterator[IndexUnit]:
        emitted = 0
        for _path, node in walk(self.document):
            for unit in self._units_for(node):
                if emitted >= start:
                    yield unit
                emitted += 1

    def _units_for(self, node: IRNode) -> Iterator[IndexUnit]:
        page = _page_of(node)
        node_id = str(node.id)

        scope = _SCOPE_BY_TAG.get(type(node))
        if scope is not None:
            if isinstance(node, CodeBlock):
                text = node.text
            elif isinstance(node, Heading | Paragraph):
                text = plain_text(node.content)
            else:  # pragma: no cover - _SCOPE_BY_TAG holds exactly these three
                text = ""
            if text.strip():
                yield IndexUnit(text=text, scope=scope, node_ulid=node_id, page=page)
            return

        if isinstance(node, Figure):
            caption = plain_text(node.caption)
            if caption.strip():
                yield IndexUnit(text=caption, scope=Scope.CAPTIONS, node_ulid=node_id, page=page)
            return

        if isinstance(node, Diagram):
            caption = plain_text(node.caption)
            parts = [part for part in (node.label, caption, node.stipulation) if part]
            positions = (
                (PositionRef(placement=node.fen, ply=0, turn=_turn_of(node.fen)),)
                if self.index_positions and node.fen
                else ()
            )
            yield IndexUnit(
                text=" ".join(parts),
                scope=Scope.CAPTIONS,
                node_ulid=node_id,
                page=page,
                positions=positions,
            )
            return

        if isinstance(node, GameScore):
            yield from self._game_units(node, page)

    def _game_units(self, game: GameScore, page: int) -> Iterator[IndexUnit]:
        headers = game.headers
        facets = Facets(
            white=headers.white,
            black=headers.black,
            eco=_tag(game, "ECO"),
            year=_year(headers.date),
            result=headers.result,
        )
        header_text = " ".join(
            (headers.event, headers.site, headers.white, headers.black, headers.date, headers.round)
        )
        yield IndexUnit(
            text=header_text,
            scope=Scope.HEADERS,
            node_ulid=str(game.id),
            page=page,
            facets=facets,
        )

        mainline: list[str] = []
        variations: list[str] = []
        comments: list[str] = []
        positions: list[PositionRef] = []
        for move, depth in _walk_moves(game.children):
            # The NAG travels with the move so that "todos os lances marcados
            # com ??" is a term in the same token stream, not a second index.
            printed = move.san + "".join(_nag_glyph(nag) for nag in move.nags)
            (mainline if depth == 0 else variations).append(printed)
            comments.extend(
                comment for comment in (move.comment_before, move.comment_after) if comment.strip()
            )
            if self.index_positions and move.position_after:
                positions.append(
                    PositionRef(
                        placement=move.position_after,
                        ply=move.ply,
                        turn=_turn_of(move.position_after),
                    )
                )

        if mainline:
            yield IndexUnit(
                text=" ".join(mainline),
                scope=Scope.MAINLINE,
                node_ulid=str(game.id),
                page=page,
                facets=facets,
                positions=tuple(positions),
            )
        if variations:
            yield IndexUnit(
                text=" ".join(variations),
                scope=Scope.VARIATIONS,
                node_ulid=str(game.id),
                page=page,
                facets=facets,
            )
        if comments:
            yield IndexUnit(
                text=" ".join(comments),
                scope=Scope.COMMENTS,
                node_ulid=str(game.id),
                page=page,
                facets=facets,
            )


def _walk_moves(children: Sequence[MoveNode], depth: int = 0) -> Iterator[tuple[MoveNode, int]]:
    """Depth-first over a move tree, main line first.

    ``children[0]`` is the continuation and the rest are variations -- the
    convention :class:`~caissa.core.model.game.MoveNode` documents.  Getting
    this wrong would file half the book's moves under the wrong scope.
    """
    for index, move in enumerate(children):
        here = depth if index == 0 else depth + 1
        yield (move, here)
        yield from _walk_moves(move.children, here)


def _page_of(node: IRNode) -> int:
    provenance = getattr(node, "provenance", None)
    page = getattr(provenance, "page", None)
    return int(page) if isinstance(page, int) else -1


def _tag(game: GameScore, name: str) -> str:
    for tag in game.headers.extra:
        if tag.name == name:
            return tag.value
    return ""


def _year(date: str) -> int:
    head = date[:4]
    return int(head) if head.isdigit() else 0


def _nag_glyph(nag: int) -> str:
    """``$4`` -> ``"??"``, using F6's table rather than a second copy of it.

    A NAG with no printed glyph (``$14`` and friends) contributes nothing: the
    index is what a reader would search for, and nobody searches for a code the
    page never showed.
    """
    entry = NAG_BY_CODE.get(f"${nag}")
    return entry.glyph if entry is not None and entry.glyph else ""


#: A FEN has its side-to-move field second; a bare placement has none.
_FEN_TURN_FIELDS: Final = 2


def _turn_of(fen: str) -> bool:
    parts = fen.split(" ")
    return len(parts) < _FEN_TURN_FIELDS or parts[1] != "b"


# --------------------------------------------------------------------------- #
# PGN -- the multi-gigabyte path
# --------------------------------------------------------------------------- #

_PGN_TAG_RE: Final = re.compile(rb'\[(\w+)\s+"([^"]*)"\]')

#: Read size.  1 MiB is large enough that syscall overhead disappears and small
#: enough that peak RSS is dominated by Python's own footprint rather than by
#: the buffer.  Measured on ``PGN_Database.pgn``; see ``F10_REPORT.md``.
_BLOCK: Final = 1 << 20

#: How many blocks of carry mean the file is malformed rather than merely large.
_MAX_CARRY_BLOCKS: Final = 16


@dataclass(slots=True)
class PgnSource:
    """A PGN file, streamed game by game.

    Attributes:
        path: The file.
        profile: ``"headers"`` indexes the seven-tag roster and the result;
            ``"full"`` adds the movetext.  The default is ``"headers"`` because
            of what the trunk already measured: a movetext index over the whole
            collection costs tens of gigabytes to answer a question the
            positional index answers in a B-tree descent
            (``games_db.scan_by_positions`` says so in its own docstring).
            ``"full"`` exists for a single study database a user wants to grep.
        index_positions: Replay every game and record its positions.  Off by
            default: it is the expensive mode, and it is opt-in per database
            precisely because 800 million positions do not fit the disk budget.
        max_games: Stop after this many games.  For measuring, and for a user
            who wants a taste of a huge file before committing the disk.
    """

    path: Path
    profile: str = "headers"
    index_positions: bool = False
    max_games: int | None = None
    _read_calls: int = field(default=0, init=False, repr=False)

    @property
    def uri(self) -> str:
        return str(self.path.resolve())

    @property
    def title(self) -> str:
        return self.path.stem

    @property
    def kind(self) -> str:
        return "pgn"

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size

    @property
    def content_key(self) -> str:
        return content_key_for(self.path)

    @property
    def read_calls(self) -> int:
        """How many times the file was opened.  The incremental test asserts on it."""
        return self._read_calls

    def units(self, *, start: int = 0) -> Iterator[IndexUnit]:
        """One unit per game, from byte ``start``.

        The scanner is bytes, not text: decoding 10 GB to ``str`` to find
        ``"[Event"`` costs a full transcode of a file that is 99 % movetext
        nobody is decoding.  Only the header block of each game is decoded, and
        only when the profile asks for it.
        """
        self._read_calls += 1
        emitted = 0
        with self.path.open("rb") as handle:
            handle.seek(start)
            carry = b""
            offset = start
            while True:
                block = handle.read(_BLOCK)
                if not block:
                    break
                buffer = carry + block
                base = offset - len(carry)
                cut = 0
                for game_start, game_end in _game_spans(buffer, final=False):
                    unit = self._unit(buffer[game_start:game_end], base + game_start)
                    if unit is not None:
                        yield unit
                        emitted += 1
                        if self.max_games is not None and emitted >= self.max_games:
                            return
                    cut = game_end
                carry = buffer[cut:]
                offset += len(block)
                # A single game larger than the buffer would grow ``carry``
                # without bound.  Real games are kilobytes; a file that trips
                # this is malformed, and dropping the carry loses one record
                # instead of the machine.
                if len(carry) > _MAX_CARRY_BLOCKS * _BLOCK:
                    carry = b""
            base = offset - len(carry)
            for game_start, game_end in _game_spans(carry, final=True):
                unit = self._unit(carry[game_start:game_end], base + game_start)
                if unit is not None:
                    yield unit
                    emitted += 1
                    if self.max_games is not None and emitted >= self.max_games:
                        return

    def _unit(self, raw: bytes, offset: int) -> IndexUnit | None:
        if not raw.strip():
            return None
        headers = {
            match.group(1).decode("ascii", "replace"): match.group(2).decode("utf-8", "replace")
            for match in _PGN_TAG_RE.finditer(raw)
        }
        if not headers:
            return None
        facets = Facets(
            white=headers.get("White", ""),
            black=headers.get("Black", ""),
            eco=headers.get("ECO", ""),
            year=_year(headers.get("Date", "")),
            result=headers.get("Result", "*"),
        )
        if self.profile == "full":
            text = raw.decode("utf-8", "replace")
            scope = Scope.ALL
        else:
            text = " ".join(
                headers.get(tag, "")
                for tag in ("Event", "Site", "Date", "Round", "White", "Black", "Result", "ECO")
            )
            scope = Scope.HEADERS
        positions = tuple(self._positions(raw)) if self.index_positions else ()
        return IndexUnit(
            text=text,
            scope=scope,
            byte_start=offset,
            byte_len=len(raw),
            # The bytes are on disk already.  Storing a second copy is what
            # makes an index miss the 15 % gate.
            store_text=False,
            facets=facets,
            positions=positions,
            cursor=offset + len(raw),
        )

    def _positions(self, raw: bytes) -> Iterator[PositionRef]:
        from io import StringIO

        import chess.pgn

        try:
            game = chess.pgn.read_game(StringIO(raw.decode("utf-8", "replace")))
        except (ValueError, RuntimeError):
            return
        if game is None:
            return
        board = game.board()
        yield PositionRef(placement=board.board_fen(), ply=0, turn=board.turn)
        for ply, move in enumerate(game.mainline_moves(), start=1):
            if not board.is_legal(move):
                # The trunk's lesson: a broken move ends the game, it does not
                # end the scan (``games_db.GameRecord.positions``).
                return
            board.push(move)
            yield PositionRef(placement=board.board_fen(), ply=ply, turn=board.turn)


#: A game begins at a ``[`` that opens the buffer or follows a blank line.  The
#: capture group is the bracket itself, so the reported offset is the first byte
#: of the game and can be stored as a resume cursor unchanged.
_GAME_START_RE: Final = re.compile(rb"(?:\A|\n[ \t]*\r?\n)[ \t]*(\[)")


def _game_spans(buffer: bytes, *, final: bool) -> Iterator[tuple[int, int]]:
    """Split a byte buffer on game boundaries.

    The last span is withheld unless ``final``, because a mid-file buffer ends
    mid-game and its tail has to become the next block's carry.  Yielding it
    would index half a game and then index the other half again.
    """
    starts = [match.start(1) for match in _GAME_START_RE.finditer(buffer)]
    if not starts:
        return
    for index in range(len(starts) - 1):
        yield (starts[index], starts[index + 1])
    if final:
        yield (starts[-1], len(buffer))


# --------------------------------------------------------------------------- #
# PDF text layer -- the bridge until F2's ingest lands
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class PdfTextSource:
    """A PDF's own text layer, one unit per page.

    A stopgap, and marked as one.  Front F2 owns PDF ingestion and will produce
    a real Document IR; when it does, :class:`IrSource` replaces this and hits
    start pointing at captions instead of at pages.  Until then, the index needs
    a real corpus to be measured against, and 50 books' text layers are that
    corpus (``CORPUS.md`` 0).

    Pages whose text layer is empty are skipped rather than sent to OCR: OCR is
    F5's, calling it from here would make indexing a book cost an hour, and a
    scanned page with no text layer is honestly *not indexed* rather than
    silently missing.
    """

    path: Path
    max_pages: int | None = None
    _read_calls: int = field(default=0, init=False, repr=False)

    @property
    def uri(self) -> str:
        return str(self.path.resolve())

    @property
    def title(self) -> str:
        return self.path.stem

    @property
    def kind(self) -> str:
        return "pdf"

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size

    @property
    def content_key(self) -> str:
        return content_key_for(self.path)

    @property
    def read_calls(self) -> int:
        return self._read_calls

    def units(self, *, start: int = 0) -> Iterator[IndexUnit]:
        import pymupdf

        self._read_calls += 1
        with pymupdf.open(self.path) as document:
            last = len(document) if self.max_pages is None else min(len(document), self.max_pages)
            for number in range(start, last):
                text = document[number].get_text("text")
                if not text.strip():
                    continue
                yield IndexUnit(text=text, scope=Scope.ALL, page=number + 1, cursor=number + 1)
