"""Pulling the moves out of a paragraph that also contains prose — SPEC §7.1.

``RegionKind.MOVETEXT`` has been in the taxonomy since F1.  It has a Tesseract
page-segmentation mode of its own and it counts as prose for the IR.  **Nothing
in the project ever assigned it**, and that omission is what stops the repair
chain from closing.

The chain is otherwise complete and was measured end to end on Nunn p200:
the vision front reads the diagram to ``1R6/8/2r5/8/k2B4/3K4/8/8``, Tesseract
reads the text under it, :mod:`caissa.ocr.notation.cipher` inverts the figurine
cipher as far as evidence allows, and
:func:`caissa.notation.legality_repair.repair_movetext` takes the legal moves of
that position as the candidate space.  What it got handed was **162 tokens of
prose with moves embedded in it**:

    296 =/= Wahls — Ziiger Munich 1989 (296): Although such a 'third rank'
    defence is less reliable than the defensive schemes outlined in section
    7.1, it is nevertheless usually enough for a draw: 1 Nc...

It accepted **two moves**, could not place the third, and reported seven
locales tied at confidence **0.01**.  A replay that eliminates wrong readings
"within two or three plies" needs two or three plies of *moves*; given a
paragraph it stops at the first word it cannot parse.

So this module does one thing: find the **contiguous runs of move tokens** in a
region's text, so that what reaches the replay is a sequence and not a
sentence.  It does not correct, translate or judge anything — that is the
repairer's job and it is already good at it.

What counts as being in a run is deliberately generous in one direction: a run
may swallow a few ordinary words, because published analysis says "1 Nc5 and
now 1...Rh6 is forced" and cutting at "and" would shatter every sequence into
two-ply fragments that discriminate nothing.  It is strict in the other: a run
has to be mostly moves, and short runs are not runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from caissa.notation.nag_table import move_suffix_class

from .cipher import CIPHER_SLOT, _MOVE_BODY, _MOVE_NUMBER, _piece_letters

__all__ = ["MoveRun", "longest_run", "move_runs"]

#: Results, and the evaluation glyphs that punctuate analysis.  These belong to
#: a run without being moves: a game ending in ``1-0`` is still move text.
_BOOKKEEPING = frozenset({
    "1-0", "0-1", "1/2-1/2", "½-½", "1/2", "½", "+-", "-+", "=", "∞",
    "+/-", "-/+", "+/=", "=/+", "⩲", "⩱", "±", "∓", "!", "?", "!!", "??",
    "!?", "?!", "(", ")", "[", "]",
})

#: Castling, in the spellings a PDF actually emits; the tail is the annotation
#: alphabet of :mod:`caissa.notation.nag_table` (passo A4).
_CASTLING = re.compile(
    rf"^[O0oО]\s?-\s?[O0oО](?:\s?-\s?[O0oО])?[{move_suffix_class()}]{{0,3}}$")

#: An ellipsis standing in for Black's move: ``1...Rh6``, ``1 ... Rh6``.
_ELLIPSIS = re.compile(r"^\.{2,4}$|^…$")


@dataclass(frozen=True, slots=True)
class MoveRun:
    """One stretch of analysis, with the prose taken out of it.

    :attr:`text` is the **moves alone**, in order, with the move numbers and
    results that belong to them.  The words the paragraph interrupted itself
    with are dropped, because what the replay needs is a sequence: "and now"
    carries no ply and keeping it only gives the repairer another token to
    fail on.  :attr:`start` and :attr:`end` still point at the original span,
    so a caller that wants to highlight the passage on the page can.
    """

    text: str
    #: Token offsets into the source text's ``split()``.
    start: int
    end: int
    #: Moves in the run, and tokens the source span held — including the prose
    #: that was dropped, so that :attr:`density` says how concentrated the
    #: moves really were.
    moves: int
    tokens: int

    @property
    def density(self) -> float:
        return self.moves / self.tokens if self.tokens else 0.0

    def describe_pt(self) -> str:
        return (f"{self.moves} lances em {self.tokens} tokens "
                f"({self.density:.0%}), posições {self.start}–{self.end}")


def _is_move(token: str, native: frozenset[str]) -> bool:
    """True for a token that carries a move, cipher slot included.

    A ``?d6+`` from :func:`caissa.ocr.notation.decode` is a move whose piece is
    still open, and it has to keep its place in the sequence — dropping it
    would splice two half-games together and make every later move illegal.
    """
    stripped = token.strip("(),;:.")
    if not stripped:
        return False
    # The move number comes off before anything else: ``5.O-O`` is a castling
    # with its number glued on (passo A5), exactly as ``5.Nf3`` is a knight move.
    unnumbered = _MOVE_NUMBER.sub("", stripped)
    if _CASTLING.match(unnumbered):
        return True
    body = _MOVE_BODY.search(unnumbered)
    if body is None:
        return False
    prefix = unnumbered[:body.start()]
    if not prefix:
        return True                       # a pawn move
    return prefix in native or prefix == CIPHER_SLOT or len(prefix) == 1


def _is_filler(token: str) -> bool:
    """A token that belongs to a run without being a move of its own."""
    if token == _VARIATION:      # a variation the trunk steps over
        return True
    stripped = token.strip("(),;:")
    if not stripped:
        return True
    if stripped in _BOOKKEEPING or _ELLIPSIS.match(stripped):
        return True
    # A bare move number: "1.", "23...", or the number alone before a space.
    return bool(re.fullmatch(r"\d{1,3}\.{0,3}", stripped))


#: Stands in for a bracketed span that :func:`_main_line` removed.  It must be
#: a token no page can produce and that is neither a move nor filler, so that a
#: variation *breaks* the trunk instead of being silently spliced into it.
_VARIATION = chr(1)

#: How many tokens a bracketed variation may span before the opening bracket is
#: presumed to have lost its partner.  Published variations run to a dozen
#: plies; sixty tokens without a close means the ``)`` was dropped by the OCR,
#: and scanning further would delete the rest of the page.
_MAX_VARIATION = 60


def _main_line(tokens: list[str]) -> list[str]:
    """``tokens`` with each bracketed span collapsed to one placeholder.

    Analysis is a **tree**, not a line, and only the trunk starts from the
    diagram.  Measured on Nunn p140: the longest run on the page sits six plies
    deep inside ``(4...g3 5 Qe5+ transposes)``, so replaying it from the
    diagram's position is illegal by construction and the repairer accepted
    **zero** moves.  Taking the trunk instead accepted **four of four**.

    Each span collapses to a *single* placeholder rather than one per token,
    because after a variation the main line resumes **from the position it
    left** — ``1 Qh7+ Kf6 (1...Kg8 2 Qg6+) 2 Qf7+`` is the contiguous line
    ``Qh7+ Kf6 Qf7+``.  Joining across the brackets is therefore correct, and
    letting a long variation cost many gaps would break the trunk at exactly
    the pages that have the most analysis on them.

    When the brackets do not balance — OCR loses closing ones — nothing is
    stripped at all.  A depth counter that never comes back down would drop
    every move after the first ``(``, which is the whole page.
    """
    out: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if "(" in token or "[" in token:
            close = _matching_close(tokens, index)
            if close is not None:
                out.append(_VARIATION)
                index = close + 1
                continue
        out.append(token)
        index += 1
    return out


def _matching_close(tokens: list[str], start: int) -> int | None:
    """Index of the bracket that closes the one at ``start``, or ``None``.

    Bounded by :data:`_MAX_VARIATION` because OCR loses closing brackets, and a
    scan that runs to the end of the page would delete every move after the
    first ``(``.  An unmatched bracket is left alone: a stray character in the
    middle of the trunk costs one gap, while deleting the rest of the page
    costs the page.
    """
    depth = 0
    for index in range(start, min(len(tokens), start + _MAX_VARIATION)):
        token = tokens[index]
        depth += token.count("(") + token.count("[")
        depth -= token.count(")") + token.count("]")
        if depth <= 0:
            return index
    return None


def move_runs(text: str, *, notation_lang: str = "", min_moves: int = 4,
              max_gap: int = 3, min_density: float = 0.40,
              main_line_only: bool = True) -> tuple[MoveRun, ...]:
    """Every stretch of ``text`` that reads as a sequence of moves.

    ``max_gap`` is how many ordinary words a run may swallow before it is
    considered over.  Three, because published analysis interrupts itself
    constantly — "1 Nc5 and now Black is lost", "2 Rh2 winning the rook" — and
    a run that breaks at the first word produces two-ply fragments, which is
    exactly the state that made the replay tie seven ways at confidence 0.01.

    ``main_line_only`` drops everything inside brackets before looking for
    runs — see :func:`_main_line`.  It is on by default because the caller that
    matters replays from a diagram's position, and only the trunk starts there.

    ``min_moves`` and ``min_density`` are what keep a sentence that happens to
    mention ``e4`` from being called a game.  The density is measured over the
    **source span**, prose included, because that is the question being asked —
    "was this a stretch of analysis?" — even though the prose does not survive
    into :attr:`MoveRun.text`.  Two fifths is low enough to accept a heavily
    annotated line and high enough to reject a paragraph with a move in it.
    """
    native = _piece_letters(notation_lang)
    tokens = text.split()
    if main_line_only:
        tokens = _main_line(tokens)
    runs: list[MoveRun] = []

    start: int | None = None
    gap = 0
    moves = 0
    last_move = -1
    kept: list[str] = []

    def close(end: int) -> None:
        nonlocal start, gap, moves, last_move, kept
        if start is not None and moves >= min_moves:
            span = tokens[start:end]
            if span and moves / len(span) >= min_density:
                runs.append(MoveRun(text=" ".join(kept[:_kept_upto(end)]),
                                    start=start, end=end,
                                    moves=moves, tokens=len(span)))
        start = None
        gap = 0
        moves = 0
        last_move = -1
        kept = []

    #: ``kept`` may run past the closing point when a run ends on trailing
    #: bookkeeping; this trims it back to the last move.
    def _kept_upto(end: int) -> int:
        while kept and kept_index and kept_index[-1] >= end:
            kept.pop()
            kept_index.pop()
        return len(kept)

    kept_index: list[int] = []
    for index, token in enumerate(tokens):
        if _is_move(token, native):
            if start is None:
                start = index
            gap = 0
            moves += 1
            last_move = index
            kept.append(token)
            kept_index.append(index)
        elif _is_filler(token):
            if start is not None:
                gap = 0
                kept.append(token)
                kept_index.append(index)
        elif start is not None:
            gap += 1
            if gap > max_gap:
                # The run ended at its last actual move, not at the words that
                # trailed after it.
                close(last_move + 1)
    close(len(tokens))
    return tuple(runs)


def longest_run(text: str, **kwargs: object) -> MoveRun | None:
    """The run with the most moves — what a caller hands to the replay.

    Most pages of analysis have one main line and several short variations;
    the main line is the one with the plies to discriminate with.
    """
    runs = move_runs(text, **kwargs)  # type: ignore[arg-type]
    return max(runs, key=lambda r: (r.moves, r.density)) if runs else None
