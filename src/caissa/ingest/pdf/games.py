"""Movetext paragraphs → :class:`GameScore` nodes (OCR_UI_ROADMAP passo 11, F2 pendência 3).

A paragraph of style ``Movetext`` that follows a diagram whose position was
read has everything a game needs: a starting position (the diagram's FEN,
side included — passo 7) and a sequence of moves.  This post-pass replays the
paragraph's **main line** from that position with the legality repairer the
OCR validator already uses (:func:`caissa.notation.legality_repair.repair_movetext`)
and, when the line chains, replaces the paragraph by a :class:`GameScore`
whose moves carry provenance one by one: the token as printed, the SAN the
board accepted, the repair applied, the confidence.

What stays a paragraph (R2.4: nothing is lost, nothing invented):

* a ``Movetext`` paragraph with no readable diagram before it on the same
  page — there is no position to start from;
* a paragraph whose first move is not legal from that position (the text
  continues a line from another page, or opens with a variation);
* the words and the variations around the main line: the trunk becomes
  moves, the rest of the paragraph text is kept as the first move's
  ``comment_before`` when it precedes the trunk and as ``comment_after`` of
  the last move otherwise — verbatim, so the reader loses no sentence.

Composes :mod:`caissa.notation` (the tolerant analyser that came from the
PGN_Live_Editor); rewrites none of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

import chess

from caissa.core.chess.notation_tables import DEFAULT_LANGUAGE, MoveRenderStyle
from caissa.core.model import (
    Diagram,
    GameRenderOptions,
    GameScore,
    MoveNode,
    Paragraph,
    PieceGlyph,
)
from caissa.core.model.inline import plain_text
from caissa.core.model.provenance import Provenance
from caissa.ingest.pdf.captions import move_start
from caissa.notation.legality_repair import RepairReport, repair_movetext, split_tail
from caissa.notation.nag_table import nags_from_suffix
from caissa.ocr.notation.movetext import MoveRun, move_runs

__all__ = ["GamesReport", "attach_games", "game_from_paragraph", "is_invention"]

MOVETEXT_STYLE = "Movetext"
_NUMBER = re.compile(r"^\d{1,3}\s*(?:\.{1,3}|…)?$")
EMPTY_BOARD = "8/8/8/8/8/8/8/8"
#: A line needs at least this many legal moves in a row to be called a game.
MIN_CHAINED_MOVES = 2
#: Why a column stayed ``Movetext`` instead of becoming a game, for the report
#: and for the paragraph's provenance note (OCR_UI_ROADMAP_C2 passo A5, X1).
NO_ANCHOR_REASON = "sem diagrama âncora acima da coluna"
SIDE_MISMATCH_REASON = "a numeração do primeiro lance contradiz o lado a jogar do diagrama"
NUMBER_MISMATCH_REASON = "o número do primeiro lance não continua a posição da âncora"
#: What a printed move token *says*: the piece, the destination, whether it
#: takes, the promotion — the parts a repair may not change.  ``1d4`` and
#: ``d4`` agree; ``♖g6`` and ``Bg6`` do not, nor do ``Nxe5`` and ``Ne5`` (a
#: printed capture onto an empty square says the position is not the page's).
_CORE = re.compile(
    r"^(?:\d{1,3}\s*(?:\.{1,3}|…)?\s*)?"
    r"(?P<piece>[KQRBN♔♕♖♗♘]?)[a-h]?[1-8]?(?P<takes>[x:]?)(?P<dest>[a-h][1-8])"
    r"(?:=?(?P<promo>[QRBN]))?$"
)
_CASTLING = re.compile(r"^[O0]-[O0](?:-[O0])?$")
#: A move number the OCR glued to its move (``1d4``, ``20g3``, ``5.O-O``): the
#: tokenizer of the main line would drop the token; a space puts it back.  The
#: castling form is spelled out (``O-O`` / ``0-0`` with any dash) so that a
#: decimal such as ``5.0`` is left alone.
_GLUED_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}\.{0,3})(?=[a-hKQRBN♔♕♖♗♘]|[Oo0][-‐‑‒–—−][Oo0])")
_FIGURINE = dict(zip("♔♕♖♗♘", "KQRBN", strict=True))


@dataclass
class GamesReport:
    """What the pass did, for the import report."""

    movetext_seen: int = 0
    games: int = 0
    moves: int = 0
    #: Paragraphs kept as they were, by reason.
    kept_no_position: int = 0
    kept_no_chain: int = 0
    kept_short: int = 0
    #: The column's first move number contradicts the anchor (side or number):
    #: kept as ``Movetext``, never replayed from a board the page did not give it.
    kept_anchor_mismatch: int = 0

    def counters(self) -> dict[str, int]:
        return {
            "games": self.games,
            "game_moves": self.moves,
            "movetext_kept_no_position": self.kept_no_position,
            "movetext_kept_no_chain": self.kept_no_chain,
            "movetext_kept_short": self.kept_short,
            "movetext_kept_anchor_mismatch": self.kept_anchor_mismatch,
        }


def _is_movetext(block: Any) -> bool:
    return isinstance(block, Paragraph) and getattr(block.props, "style", None) == MOVETEXT_STYLE


def _usable_fen(diagram: Diagram) -> str | None:
    """The diagram's position, when it was actually read (not the empty placeholder)."""
    fen = (diagram.fen or "").strip()
    if not fen or fen.split()[0] == EMPTY_BOARD:
        return None
    if not diagram.recognition.fen:
        return None
    return fen


def _trunk(text: str, *, notation_lang: str = "") -> MoveRun | None:
    """The main line of the paragraph, starting where the paragraph starts."""
    runs = move_runs(
        text, notation_lang=notation_lang, min_moves=MIN_CHAINED_MOVES, main_line_only=True
    )
    return runs[0] if runs else None


def _after(fen_before: str, san: str) -> str:
    board = chess.Board(fen_before)
    try:
        board.push_san(san)
    except ValueError:
        return ""
    return board.fen()


def _core(token: str) -> tuple[str, str, bool, str] | None:
    """``(piece, destination, takes, promotion)`` of a move token; ``None`` when not one."""
    # The annotation tail comes off through the one alphabet (passo A4):
    # ``Nf6±`` and ``Nf6`` say the same move.
    token = split_tail(token)[0].strip("+# ").replace("х", "x")
    if _CASTLING.match(token):
        return ("O", token.replace("0", "O"), False, "")
    match = _CORE.match(token)
    if match is None:
        return None
    piece = _FIGURINE.get(match["piece"], match["piece"])
    return (piece, match["dest"], bool(match["takes"]), match["promo"] or "")


def is_invention(move: Any) -> bool:
    """A move the repairer *changed* into another move — not what the page says.

    The repairer's edit-distance rescue is right for a token the OCR mangled
    and wrong for a game: a chain of guessed moves is a game that is not on
    the page.  What the page says is the piece, the square, the capture and
    the promotion of the printed token; a repair that keeps them (``1d4`` →
    ``d4``, ``♖g8`` → ``Rg8``) is a spelling, one that changes them (``Nb4``
    → ``Nb8``, ``♖g6`` → ``Bg6``, ``Nxe5`` → ``Ne5`` onto an empty e5) is an
    invention and ends the chain (roadmap portão: 0 lances que não estão na
    página).  A printed capture the board does not see is the surest sign
    the position is not the one the line continues from.
    """
    printed, accepted = _core(move.raw), _core(move.san)
    if printed is None or accepted is None:
        return any("edit(s)" in note for note in move.repairs)
    return printed != accepted


def _accepted(report: RepairReport) -> list[Any]:
    """The replayed moves up to the first invention."""
    out: list[Any] = []
    for move in report.moves:
        if is_invention(move):
            break
        out.append(move)
    return out


def _move_nodes(moves: list[Any], base: Provenance | None) -> list[MoveNode]:
    nodes: list[MoveNode] = []
    for move in moves:
        note = f"{move.raw} → {move.san}"
        if move.repairs:
            note += "; " + "; ".join(move.repairs)
        provenance = (
            replace(base, confidence=float(move.confidence), note=note)
            if base is not None
            else Provenance(confidence=float(move.confidence), note=note)
        )
        # Passo B3: the annotation tail the repairer set aside (``Nf6!?±``,
        # ``Rad8³``) becomes the node's NAGs, the side-dependent ones by the
        # side that made the move.  Until here no NAG survived the PDF path.
        white_moved = " w " in f" {move.fen_before} " or move.fen_before.split()[1:2] == ["w"]
        nags = nags_from_suffix(getattr(move, "suffix", "") or "", white_moved)
        nodes.append(
            MoveNode(
                san=move.san,
                ply=int(move.ply) + 1,
                position_before=move.fen_before,
                position_after=_after(move.fen_before, move.san),
                nags=nags,
                provenance=provenance,
            )
        )
    return nodes


def _chain(nodes: list[MoveNode]) -> MoveNode:
    head = nodes[-1]
    for node in reversed(nodes[:-1]):
        head = replace(node, children=(head,))
    return head


def game_from_paragraph(
    paragraph: Paragraph, start_fen: str, *, notation_lang: str = ""
) -> tuple[GameScore | None, str]:
    """The paragraph as a game from ``start_fen``, or ``(None, reason)``.

    The main line is replayed; the first printed move must be legal from the
    position, or the paragraph is not the continuation of that diagram.
    """
    text = _GLUED_NUMBER.sub(r"\1 ", plain_text(paragraph.content))
    run = _trunk(text, notation_lang=notation_lang)
    if run is None:
        return None, "short"
    mismatch = _anchor_mismatch(text.split(), run.start, start_fen)
    if mismatch is not None:
        return None, mismatch
    report = repair_movetext(run.text, start_fen=start_fen)
    moves = _accepted(report)
    if len(moves) < MIN_CHAINED_MOVES:
        return None, "no_chain"
    if moves[0].raw not in run.text.split()[:3]:
        return None, "no_chain"  # the line replays only from the middle: not this diagram's
    nodes = _move_nodes(moves, paragraph.provenance)
    tokens = text.split()
    start = run.start
    if start and _NUMBER.match(tokens[start - 1]):
        start -= 1  # the move number belongs to the first move, not to the prose
    before = " ".join(tokens[:start]).strip()
    after = " ".join(tokens[run.end :]).strip()
    # Everything the chain did not accept stays as text, verbatim.
    left_out = [m.raw for m in report.moves[len(moves) :]] + [u.raw for u in report.unresolved]
    if left_out:
        after = (after + " " if after else "") + "[não reproduzidos: " + " ".join(left_out) + "]"
    if before:
        nodes[0] = replace(nodes[0], comment_before=before)
    if after:
        nodes[-1] = replace(nodes[-1], comment_after=after)
    score = GameScore(
        initial_fen=None if start_fen == chess.STARTING_FEN else start_fen,
        children=(_chain(nodes),),
        provenance=paragraph.provenance,
        render=render_do_livro(paragraph, notation_lang),
    )
    return score, "game"


def render_do_livro(paragraph: Paragraph, notation_lang: str = "") -> GameRenderOptions:
    """Como a partida sai: a notação que a coluna imprimiu, e sem cabeçalho.

    A coluna do livro não traz jogadores, evento nem resultado: com o cabeçalho ligado, o
    exportador imprimia «? – ? · *». E ela imprimiu figurinas quando tem `PieceGlyph`; senão, as
    letras do idioma que o importador detectou (Editor HTML/CSS, H4, item 4 da spec §2.7).
    """
    figurinas = [i for i in paragraph.content if isinstance(i, PieceGlyph)]
    opcoes = GameRenderOptions(show_headers=False, language=notation_lang or DEFAULT_LANGUAGE)
    if figurinas:
        return replace(opcoes, render=MoveRenderStyle.FIGURINE,
                       figurine_set=figurinas[0].figurine_set)
    return opcoes


def _anchor_mismatch(tokens: list[str], start: int, start_fen: str) -> str | None:
    """X1 (analysis §7.1): the column's own numbering against the anchor.

    The page says which side moves first (``22...`` is Black, ``23 ♘c4`` is
    White) and from which move; the anchor's FEN says the same things.  When
    they disagree the anchor is not this column's board -- legal moves from the
    wrong diagram are the worst outcome, plausible and displaced -- so the
    column stays ``Movetext`` with the reason.  The move number is checked
    only when the anchor carries one (a game's end, or a diagram whose FEN was
    numbered); a recognised diagram's ``1`` says nothing.
    """
    if start >= len(tokens):
        return None
    opening = tokens[start]
    if start and _NUMBER.match(tokens[start - 1]):
        opening = f"{tokens[start - 1]} {opening}"
    numbering = move_start(opening)
    if numbering is None:
        return None
    number, black = numbering
    try:
        board = chess.Board(start_fen)
    except ValueError:
        return None
    if black != (board.turn == chess.BLACK):
        return "side_mismatch"
    if board.fullmove_number > 1 and number != board.fullmove_number:
        return "number_mismatch"
    return None


@dataclass(frozen=True)
class _Anchor:
    """A position on the page and where it sits: a read diagram, or a game's end."""

    fen: str | None
    page: int | None
    box: tuple[float, float, float, float] | None  # x0, top, x1, bottom


def _box_of(block: Any) -> tuple[int | None, tuple[float, float, float, float] | None]:
    provenance = getattr(block, "provenance", None)
    rect = getattr(provenance, "rect", None)
    if rect is None:
        return (getattr(provenance, "page_index", None), None)
    return (
        provenance.page_index,
        (float(rect.x), float(rect.y), float(rect.x + rect.width), float(rect.y + rect.height)),
    )


def _position_for(group: list[Paragraph], anchors: list[_Anchor]) -> tuple[str | None, str]:
    """The position the column continues from, or ``(None, why)``.

    By geometry when the page gives it: the nearest anchor whose bottom is
    above the column's first line and whose x-range overlaps it — the
    importer lists a page's diagrams before its text, so reading order alone
    would hand the left column the right column's board.  A column **with** a
    box and no anchor above it gets no position at all (passo A5, X1): the
    last diagram in reading order used to stand in, and a game replayed from
    a board the page never put over the column is the invention this pass
    exists to refuse.  Only blocks without boxes (no page geometry at all)
    still take the last anchor before them.
    """
    if not anchors:
        return None, NO_ANCHOR_REASON
    page, box = _box_of(group[0])
    if box is not None:
        x0, top, x1, _bottom = box
        above = [
            a
            for a in anchors
            if a.box is not None
            and a.page == page
            and a.box[3] <= top + 5
            and max(a.box[0], x0) < min(a.box[2], x1)
        ]
        if not above:
            return None, NO_ANCHOR_REASON
        nearest = max(above, key=lambda a: a.box[3])  # type: ignore[index]
        return nearest.fen, "" if nearest.fen else NO_ANCHOR_REASON
    last = anchors[-1]
    return last.fen, "" if last.fen else NO_ANCHOR_REASON


def attach_games(
    blocks: list[Any], *, notation_lang: str = "", report: GamesReport | None = None
) -> list[Any]:
    """The page's blocks with each chained ``Movetext`` paragraph replaced by its game.

    The position is the readable diagram nearest **above** the column (same
    page, overlapping x-range) when the blocks carry their boxes, else the
    nearest one before it in reading order; a game that chained hands the
    position it reached to the column under it.  Blocks that are not diagrams
    or movetext pass through untouched.
    """
    report = report if report is not None else GamesReport()
    out: list[Any] = []
    anchors: list[_Anchor] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if isinstance(block, Diagram):
            anchors.append(_Anchor(_usable_fen(block), *_box_of(block)))
            out.append(block)
            index += 1
            continue
        if not _is_movetext(block):
            out.append(block)
            index += 1
            continue
        # A column of moves comes out of the layout as one paragraph per
        # printed line; the game is the whole column.
        group = [block]
        while index + len(group) < len(blocks) and _is_movetext(blocks[index + len(group)]):
            group.append(blocks[index + len(group)])
        index += len(group)
        report.movetext_seen += len(group)
        joined = _joined(group)
        fen, why = _position_for(group, anchors)
        if fen is None and _opens_at_move_one(plain_text(joined.content)):
            # A game printed from its first move needs no diagram.
            fen, why = chess.STARTING_FEN, ""
        if fen is None:
            report.kept_no_position += len(group)
            out.extend(_noted(group, why))
            continue
        score, reason = game_from_paragraph(joined, fen, notation_lang=notation_lang)
        if score is None:
            if reason == "short":
                report.kept_short += len(group)
                out.extend(group)
            elif reason in ("side_mismatch", "number_mismatch"):
                report.kept_anchor_mismatch += len(group)
                out.extend(_noted(
                    group,
                    SIDE_MISMATCH_REASON if reason == "side_mismatch" else NUMBER_MISMATCH_REASON,
                ))
            else:
                report.kept_no_chain += len(group)
                out.extend(group)
            continue
        report.games += 1
        report.moves += _length(score)
        out.append(score)
        # The game moved the position on: what follows continues from where
        # it ended, not from the diagram.
        anchors.append(_Anchor(_last(score).position_after or fen, *_box_of(group[-1])))
    return out


_MOVE_ONE = re.compile(r"^1(?!\d)\s*\.?\s*(?=[a-hKQRBN♔♕♖♗♘O0])")


def _opens_at_move_one(text: str) -> bool:
    """Whether the column starts at move 1 (``1 d4``, ``1.e4``, ``1d4``)."""
    return _MOVE_ONE.match(text.strip()) is not None


def _noted(group: list[Paragraph], why: str) -> list[Paragraph]:
    """The column as it was, with ``why`` on the first paragraph's provenance.

    A ``Movetext`` column that did not become a game says so where the
    reviewer looks; the text itself is untouched.  A paragraph without
    provenance, or whose note is already taken, is passed through as is.
    """
    if not why or not group:
        return group
    first = group[0]
    provenance = getattr(first, "provenance", None)
    if provenance is None or getattr(provenance, "note", None):
        return group
    return [replace(first, provenance=replace(provenance, note=f"lances não reproduzidos: {why}")),
            *group[1:]]


def _joined(group: list[Paragraph]) -> Paragraph:
    """One paragraph out of a column of one-line ``Movetext`` paragraphs."""
    if len(group) == 1:
        return group[0]
    from caissa.core.model.inline import Text

    content: list[Any] = []
    for n, paragraph in enumerate(group):
        if n:
            content.append(Text(content=" "))
        content.extend(paragraph.content)
    return replace(group[0], content=tuple(content))


def _length(score: GameScore) -> int:
    count = 0
    node = score.children[0] if score.children else None
    while node is not None:
        count += 1
        node = node.children[0] if node.children else None
    return count


def _last(score: GameScore) -> MoveNode:
    node = score.children[0]
    while node.children:
        node = node.children[0]
    return node
