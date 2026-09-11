"""Notation repair driven by legality -- SPEC 7.3, ADR-0008.

The idea in one sentence: **the legal moves of the current position are the
candidate space.**  A typical middlegame has thirty-odd legal moves.  A token
that is one character-substitution away from exactly one of them is that move,
with a probability that no character classifier can match -- and the whole-game
replay turns "very probably" into "certain", because a wrong repair almost
always makes some later move illegal.

That is the asymmetry this module trades on.  Generic OCR sees ``Rf3`` and asks
"is that glyph an R?".  This module asks "is there a piece that could go to f3
at all?", and in most positions the answer eliminates every reading but one.

What it fixes
-------------
=============================  ==================================================
input                          how it is decided
=============================  ==================================================
``0-0`` / ``o-o`` / ``O—O``    canonicalised to ``O-O``; the dash may be any of
                               the five Unicode dashes a PDF emits
``l`` ``1`` ``I`` ``|``        confusion table, filtered by legality
``5`` ``S`` / ``8`` ``B``      idem -- and note ``S`` and ``B`` are *also* piece
                               letters in German, so both readings are tried
``0`` ``O`` ``Q``              idem
missing or wrong ``+`` / ``#`` never trusted: the mark is re-derived from the
                               position, because :mod:`chess` does not verify it
``1.e4`` ``1 . e4`` ``1...e4`` numbering split off before anything else
``Cf3`` ``Sf3`` ``Кf3``        every locale in :mod:`caissa.notation.languages`
                               is a hypothesis; whole-game replay picks one
=============================  ==================================================

Why the language is chosen by replay and not by the detector
------------------------------------------------------------
:func:`~caissa.notation.languages.detect_language` gives a prior.  It is a good
prior, and for a page of Portuguese moves it is decisive.  But the case that
actually costs a book is the one it *cannot* settle: a rook ending printed in
Portuguese, where ``Rc7`` is legal as a rook move and as a king move, and where
the page may contain no other piece letter at all.

So the detector ranks, and the replay decides: each surviving locale is used to
read the entire move list, and the reading that gets furthest without an illegal
move wins.  A wrong locale does not merely mistranslate one move -- it puts the
board in a position the rest of the game contradicts, usually within two or
three plies.  When two locales replay *equally* well, the module says so
(:attr:`RepairReport.language_disputed`) instead of picking; a disputed reading
is a review item, not a correction.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Final, Iterable, Mapping, Sequence

import chess

from .languages import (
    DETECTABLE,
    Detection,
    detect_language,
    from_language,
    get_locale,
)

__all__ = [
    "CONFUSIONS",
    "LegalityRepairer",
    "RepairReport",
    "RepairedMove",
    "Unresolved",
    "canonical_castling",
    "repair_movetext",
    "split_numbering",
]


# --------------------------------------------------------------------------- #
# Character confusions
# --------------------------------------------------------------------------- #

#: Glyphs an OCR engine mixes up, as an undirected map: every key lists the
#: characters it might *actually* have been.
#:
#: The list is not general typography -- it is what this corpus produces.  The
#: digit/letter pairs come straight from SPEC 7.3; the Cyrillic entries come
#: from stratum E6, where Latin and Cyrillic homoglyphs (``К``/``K``, ``С``/``C``,
#: ``Р``/``P``, ``х``/``x``, ``о``/``o``, ``е``/``e``, ``а``/``a``) are visually
#: identical and the engine picks whichever script it was told to expect.
#:
#: Every substitution is filtered by legality afterwards, so a wrong entry costs
#: a wasted parse attempt and never a wrong move.
CONFUSIONS: Final[Mapping[str, tuple[str, ...]]] = {
    "l": ("1", "I", "i", "|"),
    "1": ("l", "I", "i", "|"),
    "I": ("1", "l", "i"),
    "i": ("1", "l", "I"),
    "|": ("1", "l"),
    "5": ("S", "s"),
    "S": ("5",),
    "s": ("5",),
    "8": ("B", "3"),
    "B": ("8",),
    "0": ("O", "o", "Q", "D"),
    "O": ("0", "Q", "D"),
    "o": ("0", "O"),
    "Q": ("O", "0"),
    "6": ("b", "G", "5"),
    "b": ("6",),
    "G": ("6",),
    "2": ("Z", "z"),
    "Z": ("2",),
    "9": ("g", "q"),
    "g": ("9",),
    "q": ("9",),
    "4": ("A",),
    "A": ("4",),
    "7": ("T", "/"),
    "T": ("7",),
    "3": ("8",),
    "c": ("e",),
    "e": ("c",),
    "D": ("0", "O"),
    "R": ("P",),
    # Cyrillic <-> Latin homoglyphs (stratum E6).
    "К": ("K",),
    "K": ("К",),
    "С": ("C",),
    "C": ("С",),
    "Р": ("P", "R"),
    "P": ("Р",),
    "х": ("x",),
    "x": ("х", ":", "×"),
    ":": ("x",),
    "×": ("x",),
    "о": ("o", "0", "O"),
    "е": ("e",),
    "а": ("a",),
    "р": ("p", "r"),
}

#: Every dash a PDF ever put between the two ``O`` of a castling move.
_DASHES: Final[str] = "-‐‑‒–—―−­_"

#: Evaluation glyphs and editorial marks that ride along at the end of a move
#: and are not part of it.  Kept out of the repair entirely -- they belong to
#: :mod:`caissa.notation.nag_table`, which already owns the full table.
_TRAILING_JUNK: Final[str] = "!?∞±∓⧱⧲□→↑⇆©.,;:)]}"

_CASTLING_RE: Final[re.Pattern[str]] = re.compile(
    rf"^[0OoQОоС]\s*[{re.escape(_DASHES)}]\s*"
    rf"[0OoQОоС](?:\s*[{re.escape(_DASHES)}]\s*[0OoQОоС])?$"
)

#: ``1.e4``, ``1 . e4``, ``1...e4``, ``12…Qd8``, ``1)e4`` -- a move number glued
#: to the move that follows it.  Group 3 is what is left over, and is empty when
#: the number stood alone.
_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"^(\d{1,3})\s*((?:\.\s*){1,4}|…\s*|\)\s*)(.*)$"
)


def canonical_castling(token: str) -> str | None:
    """``O-O`` / ``O-O-O`` if ``token`` is a castling move in any spelling, else ``None``.

    Accepts zeros for letters, letters for zeros, every Unicode dash, internal
    spaces (``0 - 0`` is what a two-column scan produces), and the Cyrillic
    ``О``/``о`` that Russian books print.
    """
    core = token.strip().rstrip(_TRAILING_JUNK + "+#").strip()
    if not _CASTLING_RE.match(core):
        return None
    parts = [p for p in re.split(f"[{re.escape(_DASHES)}]", core) if p.strip()]
    return "O-O-O" if len(parts) == 3 else "O-O"


#: The digits an OCR engine writes as letters, restricted to the leading run of
#: a token that is followed by a dot.  ``l.e4`` is a ``1.`` the classifier read
#: as an ``l``; ``S0.Rd1`` is a ``50.``.  Applying this anywhere else would turn
#: bishops into eights, which is why it is confined to the numbering position.
_DIGIT_LOOKALIKES: Final[Mapping[str, str]] = {
    "l": "1", "I": "1", "i": "1", "|": "1", "O": "0", "o": "0",
    "S": "5", "s": "5", "B": "8", "Z": "2", "G": "6", "g": "9", "q": "9",
}

_NUMBERISH_RE: Final[re.Pattern[str]] = re.compile(
    rf"^([\d{''.join(re.escape(c) for c in _DIGIT_LOOKALIKES)}]{{1,3}})"
    r"((?:\.\s*){1,4}|…\s*|\)\s*)(.*)$"
)


def split_numbering(token: str) -> tuple[int | None, bool, str]:
    """Peel a move number off the front of ``token``.

    Returns ``(number, is_black_continuation, rest)``.  ``1...e4`` yields
    ``(1, True, "e4")``, ``1.e4`` yields ``(1, False, "e4")``, and a token with
    no number yields ``(None, False, token)``.

    The ellipsis matters: ``18...Rd8`` is Black's eighteenth move, and a reader
    that drops the dots reads it as White's and desynchronises the whole line.

    OCR'd digits are accepted **only here**: a leading run followed by a dot is
    a move number, so ``l.e4`` and ``S0.Rd1`` are read as ``1.`` and ``50.``.
    Nothing else in the module lets a letter become a digit for free.
    """
    stripped = token.strip()
    match = _NUMBER_RE.match(stripped)
    if match is None:
        lookalike = _NUMBERISH_RE.match(stripped)
        if lookalike is None or not any(char.isdigit() or char in _DIGIT_LOOKALIKES for char in lookalike.group(1)):
            return (None, False, stripped)
        digits = "".join(_DIGIT_LOOKALIKES.get(char, char) for char in lookalike.group(1))
        if not digits.isdigit():
            return (None, False, stripped)
        match = lookalike
        number = int(digits)
    else:
        number = int(match.group(1))
    dots = match.group(2).replace(" ", "")
    is_black = dots.count(".") >= 2 or "…" in dots
    return (number, is_black, match.group(3).strip())


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RepairedMove:
    """One move, as printed and as understood."""

    raw: str
    """The token exactly as it came in, junk and all."""

    san: str
    """Canonical English SAN, re-rendered by :mod:`chess` -- so the check and
    mate marks are the position's, never the page's."""

    ply: int
    fen_before: str
    number: int | None = None
    """The move number the page printed, when it printed one."""

    confidence: float = 1.0
    repairs: tuple[str, ...] = ()
    """Human-readable notes, one per transformation applied, in order."""

    @property
    def was_repaired(self) -> bool:
        return bool(self.repairs)


@dataclass(frozen=True)
class Unresolved:
    """A token that could not be turned into a legal move."""

    raw: str
    ply: int
    fen_before: str
    reason: str
    near_misses: tuple[str, ...] = ()
    """Legal moves that were close but not close enough, for the review panel."""


@dataclass(frozen=True)
class RepairReport:
    """What the repairer made of a block of movetext."""

    moves: tuple[RepairedMove, ...] = ()
    unresolved: tuple[Unresolved, ...] = ()
    language: str | None = None
    """The locale whose reading produced :attr:`moves`.

    ``None`` means the tokens were read as plain English SAN.  This is *not* a
    claim about the language of the book -- see :attr:`language_disputed`."""

    detection: Detection | None = None
    language_disputed: tuple[str, ...] = ()
    """Other locales that replayed the block exactly as well.

    Non-empty means the board could not separate them.  Read together with
    :attr:`reading_disputed`: when that is ``False`` the tie is harmless (all of
    them produce the same moves -- Portuguese, Spanish, French and Italian
    agree on every letter that appeared), and when it is ``True`` the tie
    changes the game and needs a human."""

    reading_disputed: bool = False
    """``True`` when the tied locales disagree about at least one move."""

    replayed_to_end: bool = False
    final_fen: str = ""
    tokens_seen: int = 0

    @property
    def repaired_count(self) -> int:
        return sum(1 for move in self.moves if move.was_repaired)

    @property
    def confidence(self) -> float:
        """Block confidence.

        A block that replays legally from the first token to the last is worth
        far more than the product of its per-move confidences: internal
        consistency over dozens of plies is evidence no single move carries
        (SPEC 7.3, "a confianca do bloco sobe para praticamente 1,0").  So a
        clean replay lifts the floor to 0.55 and scales the rest by the worst
        move -- a block whose weakest step was a coin-flip still does not reach
        1.0, and a block of untouched moves does.

        A block that did *not* replay cleanly gets the worst move's confidence,
        discounted by the share of tokens that never became moves.
        """
        if not self.moves:
            return 0.0
        worst = min(move.confidence for move in self.moves)
        if self.replayed_to_end and not self.unresolved:
            return round(min(1.0, 0.55 + 0.45 * worst), 3)
        return round(worst * (len(self.moves) / max(1, self.tokens_seen)), 3)


# --------------------------------------------------------------------------- #
# The repairer
# --------------------------------------------------------------------------- #

#: Tokens that end a game and are not moves.
_RESULTS: Final[frozenset[str]] = frozenset(
    {"1-0", "0-1", "1/2-1/2", "½-½", "*", "1:0", "0:1"}
)

#: Shape of a token that could be a move.  This is
#: :func:`caissa.notation.candidates.looks_like_move` widened to the scripts
#: that module never had to read: Cyrillic (stratum E6) and the figurine block.
#: The rule it encodes is the same and is worth restating -- **a move needs a
#: rank digit** -- because that single requirement is what keeps ``Cada``,
#: ``chances`` and ``brancas`` from ever reaching the board.
_MOVE_SHAPE: Final[re.Pattern[str]] = re.compile(
    r"^[\w♔-♟][\w♔-♟.\-+#=!?:×∞±∓⧱⧲□]{1,9}$",
    re.UNICODE,
)


def _is_move_like(token: str) -> bool:
    """Cheap gate: could this token be a move at all?

    Prose must never reach the repairer.  A token the repairer cannot resolve
    aborts the replay -- that is deliberate, because an unresolved move
    desynchronises everything after it -- so a stray word in the block would
    silently truncate a game.  Requiring a rank digit costs nothing and stops
    every word in every one of the eight languages.
    """
    if canonical_castling(token) is not None:
        return True
    core = token.strip().strip("()[]{}").rstrip(_TRAILING_JUNK)
    if not core or not _MOVE_SHAPE.match(core):
        return False
    if not any(char.isalpha() or char in "♔♕♖♗♘♙♚♛♜♝♞♟" for char in core):
        return False
    return any(char in "12345678" for char in core)


@dataclass
class _Attempt:
    """One locale's replay of the whole block -- the unit the winner is picked from."""

    locale: str | None
    prior: float = 0.0
    """The detector's score for this locale.  Only ever a **tie-breaker**: it
    decides the rook-ending case, where both readings replay perfectly and the
    board therefore has nothing left to say."""

    moves: list[RepairedMove] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    final_fen: str = ""

    @property
    def key(self) -> tuple[int, int, float, float]:
        """Sort key: most legal moves, fewest failures, worst-move confidence, prior.

        Move count comes first because it is the only term backed by the rules
        of chess.  The prior comes last because it is the only term that can be
        wrong about a specific game.
        """
        confidence = min((m.confidence for m in self.moves), default=0.0)
        return (len(self.moves), -len(self.unresolved), confidence, self.prior)

    @property
    def evidence_key(self) -> tuple[int, int, float]:
        """The part of :attr:`key` the board actually justifies, prior excluded."""
        count, failures, confidence, _prior = self.key
        return (count, failures, confidence)


class LegalityRepairer:
    """Repairs OCR'd notation using the legal moves of the position it is in.

    Args:
        language: force a locale instead of detecting one.  ``None`` (the
            default) runs the detector and then the replay.
        max_substitutions: how many confusion swaps may be combined in one
            token.  Two is the measured sweet spot: one catches the classic
            single-glyph error, two catches ``l``+``5`` in the same token, and
            three explodes the candidate set without recovering anything the
            single-edit-to-a-legal-move rule does not already catch.
        allow_unique_edit: enable the ADR-0008 rule -- a token exactly one edit
            away from exactly *one* legal move is that move even when no
            confusion-table entry explains the difference.
    """

    def __init__(
        self,
        *,
        language: str | None = None,
        max_substitutions: int = 2,
        allow_unique_edit: bool = True,
    ) -> None:
        self.language = language
        self.max_substitutions = max_substitutions
        self.allow_unique_edit = allow_unique_edit

    # -- public ----------------------------------------------------------- #

    def repair(
        self,
        text: str,
        *,
        start_fen: str = chess.STARTING_FEN,
        candidates: Sequence[str] | None = None,
    ) -> RepairReport:
        """Read a block of movetext and return every move it can justify."""
        tokens = self._tokenize(text)
        detection = detect_language(text) if self.language is None else None
        priors = self._priors(detection)

        hypotheses = self._locale_hypotheses(detection, candidates)
        attempts = [
            self._replay(tokens, locale, start_fen, priors.get(locale or "en", 0.0))
            for locale in hypotheses
        ]
        attempts.sort(key=lambda attempt: attempt.key, reverse=True)

        best = attempts[0]
        # A dispute is measured on the *evidence*, not on the prior: two
        # readings the board cannot separate are disputed even when the detector
        # happens to like one of them.  It is always reported -- claiming a
        # language the block does not prove is exactly the mistake this front
        # exists to avoid.
        ties = [
            attempt
            for attempt in attempts[1:]
            if attempt.evidence_key == best.evidence_key and attempt.locale != best.locale
        ]
        disputed = tuple(attempt.locale or "en" for attempt in ties)

        return RepairReport(
            moves=tuple(best.moves),
            unresolved=tuple(best.unresolved),
            language=best.locale,
            detection=detection,
            language_disputed=disputed,
            reading_disputed=not self._readings_agree(ties, best),
            replayed_to_end=not best.unresolved and len(best.moves) > 0,
            final_fen=best.final_fen or start_fen,
            tokens_seen=len(tokens),
        )

    def repair_token(self, token: str, board: chess.Board, *, locale: str | None = None) -> str | None:
        """The SAN this token means in this position, or ``None``.

        The single-token entry point, for callers that already own the board --
        the OCR arbiter uses it to re-score a region without replaying anything.
        """
        result = self._resolve(token, board, locale)
        return result[0] if result else None

    # -- internals -------------------------------------------------------- #

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Whitespace split, with the move number peeled off whatever it is glued to.

        Numbering is handled here and not in the per-token repair because
        ``1.e4`` is *two* tokens that a bad space collapsed into one, and every
        later stage is simpler once that is undone.
        """
        out: list[str] = []
        for raw in text.split():
            token = raw.strip()
            while token:
                number, is_black, rest = split_numbering(token)
                if number is None:
                    out.append(token)
                    break
                out.append(f"{number}{'...' if is_black else '.'}")
                if not rest:
                    break
                token = rest
        return out

    def _locale_hypotheses(
        self, detection: Detection | None, candidates: Sequence[str] | None
    ) -> list[str | None]:
        """The locales worth replaying, best prior first.

        ``None`` means "read the tokens as plain English SAN" and is always
        tried: it is the PGN standard, and a PGN pasted into the program must
        never be reinterpreted as a foreign language (this is the whole reason
        an English ``Rf1`` survives).
        """
        if self.language is not None:
            return [None if self.language == "en" else self.language]

        pool = list(candidates) if candidates is not None else list(DETECTABLE)
        ordered: list[str | None] = [None]
        if detection is not None:
            ranked = [score.code for score in detection.ranked if score.code in pool]
            ordered += [code for code in ranked if code != "en"]
        else:
            ordered += [code for code in pool if code != "en"]
        return ordered

    @staticmethod
    def _priors(detection: Detection | None) -> Mapping[str, float]:
        if detection is None:
            return {}
        return {score.code: score.score for score in detection.ranked}

    @staticmethod
    def _readings_agree(ties: Sequence[_Attempt], best: _Attempt) -> bool:
        """Do the tied locales produce the same move list as the winner?"""
        best_sans = [move.san for move in best.moves]
        return all([move.san for move in tie.moves] == best_sans for tie in ties)

    def _replay(
        self, tokens: Sequence[str], locale: str | None, start_fen: str, prior: float = 0.0
    ) -> _Attempt:
        """Play the whole block under one locale hypothesis."""
        board = chess.Board(start_fen)
        attempt = _Attempt(locale=locale, prior=prior)
        ply = 0
        pending_number: int | None = None

        for token in tokens:
            if self._is_numbering(token):
                pending_number = int(token.rstrip(".…"))
                continue
            if token in _RESULTS:
                break
            if not _is_move_like(token):
                # Prose, a caption, an ECO code: skipped, not failed.  Only a
                # token that *looks* like a move and still cannot be resolved
                # stops the replay.
                continue

            resolved = self._resolve(token, board, locale)
            if resolved is None:
                attempt.unresolved.append(
                    Unresolved(
                        raw=token,
                        ply=ply,
                        fen_before=board.fen(),
                        reason="no legal move matches this token",
                        near_misses=tuple(self._near_misses(token, board)),
                    )
                )
                break

            san, confidence, repairs = resolved
            attempt.moves.append(
                RepairedMove(
                    raw=token,
                    san=san,
                    ply=ply,
                    fen_before=board.fen(),
                    number=pending_number,
                    confidence=confidence,
                    repairs=repairs,
                )
            )
            board.push_san(san)
            ply += 1
            pending_number = None

        attempt.final_fen = board.fen()
        return attempt

    @staticmethod
    def _is_numbering(token: str) -> bool:
        return bool(re.fullmatch(r"\d{1,3}(?:\.{1,3}|…)", token))

    # -- the actual repair ------------------------------------------------ #

    def _resolve(
        self, token: str, board: chess.Board, locale: str | None
    ) -> tuple[str, float, tuple[str, ...]] | None:
        """Best legal reading of ``token`` here: ``(san, confidence, notes)``.

        The hypotheses are ordered by how much they claim, and the *first* legal
        one wins -- not the closest.  Reading the token as written is always
        tried first, because a correct token must never be "improved".
        """
        for text, confidence, notes in self._hypotheses(token, locale):
            move = self._parse(text, board)
            if move is not None:
                # Re-render from the board: this is what fixes a missing `+`, a
                # spurious `#`, and a disambiguator the page left out.  `chess`
                # strips the mark without checking it, so the page's mark is
                # never evidence of anything.
                san = board.san(move)
                extra = notes
                if san != text and "mark" not in " ".join(notes):
                    if san.rstrip("+#") == text.rstrip("+#"):
                        extra = (*notes, f"check/mate mark from the position: {text} -> {san}")
                    else:
                        extra = (*notes, f"canonical form from the position: {text} -> {san}")
                return (san, confidence, extra)

        if self.allow_unique_edit:
            unique = self._unique_within_one_edit(token, board)
            if unique is not None:
                san, distance = unique
                return (
                    san,
                    0.86 if distance == 1 else 0.66,
                    (
                        f"the only legal move within {distance} edit(s) of "
                        f"{self._core(token)!r} is {san}",
                    ),
                )
        return None

    @staticmethod
    def _parse(text: str, board: chess.Board) -> chess.Move | None:
        try:
            return board.parse_san(text)
        except (ValueError, AssertionError):
            return None

    @staticmethod
    def _core(token: str) -> str:
        """The token without leading/trailing decoration."""
        return token.strip().strip("()[]{}").rstrip(_TRAILING_JUNK).strip()

    def _hypotheses(
        self, token: str, locale: str | None
    ) -> Iterable[tuple[str, float, tuple[str, ...]]]:
        """Every reading worth trying, in decreasing order of "as written"."""
        seen: set[str] = set()

        def emit(
            text: str, confidence: float, notes: tuple[str, ...]
        ) -> Iterable[tuple[str, float, tuple[str, ...]]]:
            cleaned = text.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                yield (cleaned, confidence, notes)

        core = self._core(token)
        base_notes: tuple[str, ...] = () if core == token else ("trailing annotation removed",)

        # THE ORDERING THAT MATTERS.
        #
        # Normally the token is tried exactly as written first: a correct move
        # must never be "improved", and an imported English PGN must stay
        # English.  The exception is a letter that means a *different piece* in
        # this locale than in English -- `R` in pt/es/fr/it, `B` in de, `P` in
        # nl.  Inside a locale hypothesis, the locale's reading of such a letter
        # comes first, because both readings are frequently legal at the same
        # time (a rook ending: `Rc7` plays as a rook and as a king) and taking
        # the English one there rewrites the rest of the game.
        #
        # This is the same inversion `PGN_Live_Editor/core/candidates.py`
        # arrived at by discounting the "exact" reading once the document had
        # proved its notation; expressing it as an *order* rather than a score
        # keeps it from being outvoted by an unrelated confidence factor.
        disputed_letter = (
            locale is not None
            and core[:1] in get_locale(locale).collides_with_english
        )

        if disputed_letter and locale is not None:
            translated = from_language(core, locale)
            if translated is not None and translated != core:
                yield from emit(
                    translated,
                    0.95,
                    (
                        *base_notes,
                        f"{get_locale(locale).name} notation: {core} -> {translated} "
                        f"('{core[:1]}' means a different piece in English)",
                    ),
                )

        yield from emit(
            core,
            0.80 if disputed_letter else 1.0,
            (
                (*base_notes, f"read as English SAN despite the {locale} hypothesis")
                if disputed_letter
                else base_notes
            ),
        )

        castling = canonical_castling(token)
        if castling is not None:
            yield from emit(
                castling,
                0.99 if core in ("O-O", "O-O-O") else 0.97,
                () if core == castling else (f"castling normalised: {core} -> {castling}",),
            )

        # NFKC folds the fullwidth and ligature forms a PDF font can emit.  It
        # runs *after* the as-written attempt so a correct token is never
        # rewritten by it.
        folded = unicodedata.normalize("NFKC", core)
        yield from emit(folded, 0.99, ("Unicode NFKC folding",))

        if locale is not None:
            translated = from_language(core, locale)
            if translated is not None:
                name = get_locale(locale).name
                yield from emit(
                    translated,
                    0.95 if translated != core else 1.0,
                    () if translated == core else (f"{name} notation: {core} -> {translated}",),
                )

        # Case: `nf3`, `o-o`, `BXF6`.  Cheap, and books do print small caps.
        if core[:1].islower() and len(core) > 1:
            yield from emit(
                core[0].upper() + core[1:], 0.94, (f"piece letter case: {core}",)
            )
            if locale is not None:
                translated = from_language(core[0].upper() + core[1:], locale)
                if translated is not None:
                    yield from emit(translated, 0.90, (f"case + {locale} notation: {core}",))

        for variant, swaps in self._confusion_variants(core):
            note = f"OCR confusion: {core} -> {variant}"
            yield from emit(variant, 0.92 if swaps == 1 else 0.80, (note,))
            if locale is not None:
                translated = from_language(variant, locale)
                if translated is not None and translated != variant:
                    yield from emit(
                        translated,
                        0.88 if swaps == 1 else 0.74,
                        (note, f"{locale} notation: {variant} -> {translated}"),
                    )

    def _confusion_variants(self, token: str) -> Iterable[tuple[str, int]]:
        """Every string reachable by up to ``max_substitutions`` confusion swaps.

        Breadth-first so that single swaps are all offered before any double
        one: a one-character repair that produces a legal move outranks a
        two-character repair that also does.
        """
        frontier = {token}
        seen = {token}
        for depth in range(1, max(0, self.max_substitutions) + 1):
            nxt: set[str] = set()
            for current in frontier:
                for index, char in enumerate(current):
                    for replacement in CONFUSIONS.get(char, ()):
                        variant = current[:index] + replacement + current[index + 1 :]
                        if variant not in seen:
                            seen.add(variant)
                            nxt.add(variant)
                            yield (variant, depth)
            frontier = nxt
            if not frontier:
                return

    def _unique_within_one_edit(
        self, token: str, board: chess.Board
    ) -> tuple[str, int] | None:
        """ADR-0008's rule, spelled out.

        A token whose nearest legal move is *uniquely* nearest, and near enough
        for its length, is that move.  The threshold scales with length for the
        reason `PGN_Live_Editor/core/candidates.py` already measured: at
        distance 2 a three-character token "corrects" to almost anything, so
        short tokens get one edit and longer ones get two.
        """
        core = self._core(token).rstrip("+#")
        if not core:
            return None
        legal = [board.san(move) for move in board.legal_moves]
        if not legal:
            return None

        limit = 1 if len(core) <= 3 else 2
        scored = sorted((_edit_distance(core, san.rstrip("+#")), san) for san in legal)
        best_distance, best_san = scored[0]
        if best_distance == 0 or best_distance > limit:
            return None
        if len(scored) > 1 and scored[1][0] == best_distance:
            # Tied: two legal moves are equally close, so the token does not
            # identify one.  Refuse rather than pick -- this is the case that
            # produces a legal-but-wrong move, the worst outcome available.
            return None
        return (best_san, best_distance)

    def _near_misses(self, token: str, board: chess.Board, limit: int = 3) -> list[str]:
        core = self._core(token).rstrip("+#")
        legal = [board.san(move) for move in board.legal_moves]
        scored = sorted((_edit_distance(core, san.rstrip("+#")), san) for san in legal)
        return [san for _, san in scored[:limit]]


def _edit_distance(left: str, right: str) -> int:
    from .distance import levenshtein

    return levenshtein(left, right)


def repair_movetext(
    text: str,
    *,
    language: str | None = None,
    start_fen: str = chess.STARTING_FEN,
) -> RepairReport:
    """Convenience wrapper: repair ``text`` with default settings.

    This is the function the OCR post-corrector calls.  Leave ``language`` at
    ``None`` -- letting the replay choose is the point.
    """
    return LegalityRepairer(language=language).repair(text, start_fen=start_fen)
