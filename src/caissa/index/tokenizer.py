"""The notation-preserving tokenizer -- ADR-0007's hard part.

A default full-text tokenizer destroys chess.  ``unicode61`` splits on every
non-alphanumeric character, so ``O-O-O`` becomes three ``o``'s, ``1.e4`` becomes
``1`` and ``e4``, ``Qxd5+`` loses the check, and ``♘f3`` loses the knight
entirely because the glyph is punctuation to it.  A library indexed that way
cannot answer the one question a chess library exists to answer.

Three problems have to be solved at once, and only the third is obvious.

**Segmentation.**  ``O-O-O``, ``1.e4``, ``Qxd5+``, ``e8=Q#`` and ``1/2-1/2``
must each survive as one token.  Solved by doing the segmentation *here*, in
Python, and handing SQLite a stream it only has to split on spaces
(:data:`FTS5_TOKENIZE` adds ``-+#=._!?/`` to the token characters).  Writing a
real FTS5 tokenizer would mean C: the ``fts5_api`` that registers one is not
exposed by :mod:`sqlite3`, and requiring ``apsw`` to search a book is not a
trade this project makes.

**Case.**  ``Bxc4`` is a bishop and ``bxc4`` is a pawn.  Every built-in FTS5
tokenizer case-folds -- ``unicode61``, ``ascii``, all of them -- so the two
collapse into one token and the index answers the wrong question with total
confidence.  There is no option to turn it off.  Solved by moving the case
*into the letters*: an uppercase letter is written lowercase followed by
:data:`UPPER_MARK`, so ``Bxc4`` -> ``b_xc4`` and ``bxc4`` -> ``bxc4``, and the
distinction survives folding because ``_`` is not a letter.  The encoding is
applied identically when indexing and when querying, so it is invisible to the
user; :func:`decode_token` exists for tests and for reading the index by hand.

**Identity.**  The same move is printed as ``Nf3`` in English, ``Cf3`` in
Portuguese, ``Sf3`` in German, ``Кf3`` in Russian and ``♘f3`` in figurine, and a
reader searching one of those wants all five.  Solved by folding notation to
canonical English SAN before encoding, reusing the tables in
:mod:`caissa.core.chess.notation_tables` rather than inventing a second set.
That is why a figurine book and an English book answer the same query.

What the encoder emits, by case:

===========================  ==========================  =========================
input                        emitted                     why
===========================  ==========================  =========================
``O-O-O`` / ``0-0-0``        ``o_-o_-o_``                one token, case kept
``Nf3`` / ``Cf3`` / ``♘f3``  ``n_f3``                    one move, one token
``1.e4``                     ``1.e4`` then ``e4``        both queries must work
``Qxd5+``                    ``qxd5+``                   the check is part of it
``Nf3!?``                    ``n_f3`` then ``!?``        the mark is searchable,
                                                         the move is still ``Nf3``
``12.``                      *(nothing)*                 furniture, not a term
``peão,``                    ``peao``                    prose: folded by SQLite
===========================  ==========================  =========================

The doubled emission for ``1.e4`` is the one place this file spends index space
deliberately.  A reader searching ``e4`` must find ``1.e4``, and a reader
searching ``1.e4`` must not match ``12.e4``; emitting the glued form followed by
the bare move satisfies both, and phrase queries still line up because the query
string goes through this same expansion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from caissa.core.chess.notation_tables import FIGURINE_BLACK, FIGURINE_WHITE, PieceType
from caissa.notation.nag_table import NAG_BY_CODE

__all__ = [
    "FTS5_TOKENCHARS",
    "FTS5_TOKENIZE",
    "TOKENIZER_VERSION",
    "UPPER_MARK",
    "ChessTokenizer",
    "TokenKind",
    "decode_token",
    "encode_case",
    "is_notation",
]

#: Bumped whenever the emitted stream changes.  An index built by another
#: version answers different questions and is refused as stale, because a
#: tokenizer change is a silent recall bug otherwise.
TOKENIZER_VERSION: Final = "1"

#: Marks the preceding letter as uppercase.  Chosen because SQLite's folding
#: leaves it alone, it is not a chess character, and it reads.
UPPER_MARK: Final = "_"

#: Characters SQLite must treat as part of a token rather than as a separator.
#: Everything the encoder can emit is a letter, a digit, or one of these.
FTS5_TOKENCHARS: Final = "-+#=._!?/"

#: The complete ``tokenize=`` directive.  ``remove_diacritics 2`` is the full
#: Unicode folding, which is what makes ``peao`` find ``peão`` in a Portuguese
#: book; the encoder guarantees chess tokens are pure ASCII, so folding cannot
#: touch them.
FTS5_TOKENIZE: Final = (
    f"unicode61 remove_diacritics 2 tokenchars '{FTS5_TOKENCHARS}' separators ' '"
)


class TokenKind:
    """Why a token was emitted.  Values are stable strings, for debugging."""

    PROSE: Final = "prose"
    MOVE: Final = "move"
    NUMBERED_MOVE: Final = "numbered_move"
    ANNOTATION: Final = "annotation"
    RESULT: Final = "result"
    SQUARE: Final = "square"


# --------------------------------------------------------------------------- #
# Character-level normalisation
# --------------------------------------------------------------------------- #

_PIECE_LETTER: Final[dict[PieceType, str]] = {
    PieceType.KING: "K",
    PieceType.QUEEN: "Q",
    PieceType.ROOK: "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
    PieceType.PAWN: "P",
}

#: Figurine glyph -> English piece letter, both the outline and the solid set.
#: Taken from the F6 tables so that one edit changes both fronts.
_FIGURINE_TO_LETTER: Final[dict[str, str]] = {
    glyph: _PIECE_LETTER[piece]
    for mapping in (FIGURINE_WHITE, FIGURINE_BLACK)
    for piece, glyph in mapping.items()
}

#: Every dash a typesetter has ever used for ``O-O`` or ``1-0``, plus the quotes
#: that wrap a word and would otherwise ride along on the token.
_CHAR_FOLD: Final[dict[int, str]] = {
    **{ord(glyph): letter for glyph, letter in _FIGURINE_TO_LETTER.items()},
    ord("‐"): "-",
    ord("‑"): "-",
    ord("‒"): "-",
    ord("–"): "-",
    ord("—"): "-",
    ord("―"): "-",
    ord("−"): "-",
    ord("½"): "1/2",
    ord("‘"): "'",
    ord("’"): "'",
    ord("“"): '"',
    ord("”"): '"',
    ord(" "): " ",
    ord("…"): "...",
    ord("†"): "+",  # dagger for check, older German and Dutch typography
    ord("‡"): "#",
    # Evaluation symbols in their ASCII PGN spellings.  Folded rather than
    # dropped so that "every position White is slightly better in" is a term:
    # the glyphs are not token characters and would otherwise vanish.
    ord("±"): "+/-",
    ord("∓"): "-/+",
    ord("⩲"): "+=",
    ord("⩱"): "=+",
}

_NEEDS_FOLD: Final[frozenset[str]] = frozenset(chr(code) for code in _CHAR_FOLD)


# --------------------------------------------------------------------------- #
# Notation recognition
# --------------------------------------------------------------------------- #

#: Canonical English SAN, and only that: the encoder folds language and
#: figurine to English before this runs.  Deliberately strict -- a permissive
#: pattern here would case-mark ordinary prose ("Bad", "Ne") and split the index
#: for a word into two tokens.  ``caissa.notation.looks_like_move`` is the
#: permissive one, for repair; the two must not be merged (``ASSETS.md`` 2.15).
_SAN_RE: Final = re.compile(
    r"""
    ^(?:
        O-O(?:-O)?                                   # castling, either side
      | [KQRBN][a-h]?[1-8]?x?[a-h][1-8]              # piece move, any disambiguator
      | [a-h]x[a-h][1-8](?:=[KQRBN])?                # pawn capture, promotion
      | [a-h][1-8](?:=[KQRBN])?                      # pawn push, promotion
    )
    [+#]?$
    """,
    re.VERBOSE,
)

#: ``1.e4``, ``12...Nf6``, ``5. Nf3`` once the space is gone.
_NUMBERED_RE: Final = re.compile(r"^(\d{1,4})(\.{1,3})(.*)$")

#: A move number on its own: PGN furniture, never a search term.  Dropping it
#: is worth roughly one token in three across a movetext-heavy corpus.
_BARE_NUMBER_RE: Final = re.compile(r"^\d{1,4}\.{1,3}$")

_RESULT_RE: Final = re.compile(r"^(?:1-0|0-1|1/2-1/2|\*)$")

_SQUARE_RE: Final = re.compile(r"^[a-h][1-8]$")

#: SAN as a *prefix*, with whatever the page printed after it captured
#: separately.  Matching a prefix rather than the whole token is what keeps
#: ``Nf3!?``, ``Nf3⩲`` and ``Nf3.`` all indexed as the move ``Nf3``: a
#: whole-token pattern would fail on each of them and quietly file the move as
#: prose, where a search for ``Nf3`` would never find it.
_SAN_PREFIX_RE: Final = re.compile(
    r"""
    ^(
        O-O(?:-O)?
      | [KQRBN][a-h]?[1-8]?x?[a-h][1-8]
      | [a-h]x[a-h][1-8](?:=[KQRBN])?
      | [a-h][1-8](?:=[KQRBN])?
    )
    ((?:[+#](?![-=/+]))?)
    (.*)$
    """,
    re.VERBOSE,
)

#: What may follow a move and still leave it a move.  Anything with a letter or
#: a digit in it is not an annotation, it is a different word.
_ANNOTATION_RE: Final = re.compile(r"^[^0-9A-Za-z]*$")

#: Of an annotation, only the characters SQLite will keep as a token.
_ANNOTATION_KEEP: Final = frozenset(FTS5_TOKENCHARS)

#: An annotation is only worth a token if it says something.  A trailing full
#: stop is punctuation; ``!?`` and ``+/-`` are the reader's question.
_ANNOTATION_MEANINGFUL: Final = frozenset("!?+-=/#")

#: ``$4`` -- the machine spelling of ``??``.  Folded to the glyph so that a PGN
#: and a book that print the same judgement answer the same query.
_NAG_CODE_RE: Final = re.compile(r"^\$(\d{1,3})$")

#: Wrappers a token can arrive inside.  Leading and trailing sets differ: a
#: trailing ``.``/``!``/``?`` may belong to the notation, a leading one never
#: does.
_STRIP_LEADING: Final = "([{<«\"'‹"
_STRIP_TRAILING: Final = ")]}>»\"'›,;:"

#: Old German and Dutch books write captures with a colon: ``N:d5``, ``d:e5``.
_COLON_CAPTURE_RE: Final = re.compile(r"^([KQRBN]?[a-h]?[1-8]?):([a-h][1-8].*)$")

_CASTLE_RE: Final = re.compile(r"^[0oO]-[0oO](-[0oO])?$")

#: ``O-O-O`` has two dashes, ``O-O`` has one.
_LONG_CASTLE_DASHES: Final = 2


def is_notation(token: str) -> bool:
    """Is ``token`` canonical English SAN, castling included?

    Strict on purpose.  See :data:`_SAN_RE`.
    """
    return _SAN_RE.match(token) is not None


def encode_case(token: str) -> str:
    """Rewrite ``token`` so its capitals survive SQLite's case folding.

    ``"Bxc4"`` -> ``"b_xc4"``, ``"bxc4"`` -> ``"bxc4"``, ``"O-O-O"`` ->
    ``"o_-o_-o_"``.  Exactly reversed by :func:`decode_token`.
    """
    if not any(char.isupper() for char in token):
        return token
    out: list[str] = []
    for char in token:
        if char.isupper():
            out.append(char.lower())
            out.append(UPPER_MARK)
        else:
            out.append(char)
    return "".join(out)


def decode_token(token: str) -> str:
    """Invert :func:`encode_case`.  Used by tests and by index dumps."""
    out: list[str] = []
    index = 0
    length = len(token)
    while index < length:
        char = token[index]
        if index + 1 < length and token[index + 1] == UPPER_MARK and char.isalpha():
            out.append(char.upper())
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


# --------------------------------------------------------------------------- #
# The tokenizer
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ChessTokenizer:
    """Turns text into the stream SQLite indexes, and queries into the same shape.

    Stateless and cheap to construct; one instance can serve every worker.

    Args:
        fold_notation: Fold figurine and non-English piece letters to English
            SAN.  On by default -- it is what makes a Portuguese book answer an
            English query.  Turned off only to prove in a test what the folding
            buys.
        emit_bare_move: Emit the bare move after a glued ``1.e4``.  On by
            default; see the module docstring for the cost and the reason.
    """

    fold_notation: bool = True
    emit_bare_move: bool = True

    # -- indexing --------------------------------------------------------- #

    def encode(self, text: str) -> str:
        """The space-joined token stream to hand to FTS5."""
        return " ".join(self.tokens(text))

    def tokens(self, text: str) -> list[str]:
        """Every token ``text`` contributes, in order.

        Order matters: FTS5 phrase queries are position-based, and a caller
        searching ``"e4 c5"`` is asking about adjacency in the movetext.
        """
        if not text:
            return []
        if _NEEDS_FOLD.intersection(text):
            text = text.translate(_CHAR_FOLD)
        out: list[str] = []
        for chunk in text.split():
            self._emit(chunk, out)
        return out

    # -- one whitespace-delimited chunk ----------------------------------- #

    def _emit(self, chunk: str, out: list[str]) -> None:
        core = chunk.strip(_STRIP_LEADING).rstrip(_STRIP_TRAILING)
        if not core:
            return

        if _BARE_NUMBER_RE.match(core):
            return

        nag = _NAG_CODE_RE.match(core)
        if nag is not None:
            entry = NAG_BY_CODE.get(core)
            glyph = (entry.glyph if entry is not None else "").translate(_CHAR_FOLD)
            kept = "".join(char for char in glyph if char in _ANNOTATION_KEEP)
            if kept:
                out.append(kept)
            return

        if _RESULT_RE.match(core):
            out.append(core)
            return

        number_prefix = ""
        body = core
        numbered = _NUMBERED_RE.match(core)
        if numbered is not None and numbered.group(3):
            number_prefix = numbered.group(1) + numbered.group(2)
            body = numbered.group(3)

        move, marks = self._as_move(body)
        if move is None:
            if number_prefix:
                # ``3.Rxf7`` where the body did not parse: keep the glued form
                # rather than dropping the reader's only handle on it.
                out.append(encode_case(core))
                return
            self._emit_prose(core, out)
            return

        encoded = encode_case(move)
        if number_prefix:
            out.append(number_prefix + encoded)
            if self.emit_bare_move:
                out.append(encoded)
        else:
            out.append(encoded)
        if marks:
            out.append(marks)

    def san_of(self, chunk: str) -> str | None:
        """Canonical English SAN for one printed chunk, or ``None``.

        ``"3.Nxd5"``, ``"Nxd5!?"``, ``"(♘xd5)"`` and ``"N:d5"`` all come back as
        ``"Nxd5"``.  Exposed because a move-pattern search over a book's text
        has to answer the same question the indexer answered, and two
        implementations of "is this chunk a move" would drift apart -- the
        difference between them being exactly the moves a search silently
        misses.
        """
        if not chunk:
            return None
        if _NEEDS_FOLD.intersection(chunk):
            chunk = chunk.translate(_CHAR_FOLD)
        core = chunk.strip(_STRIP_LEADING).rstrip(_STRIP_TRAILING)
        if not core or _BARE_NUMBER_RE.match(core):
            return None
        numbered = _NUMBERED_RE.match(core)
        body = numbered.group(3) if numbered is not None and numbered.group(3) else core
        move, _marks = self._as_move(body)
        return move

    def _as_move(self, body: str) -> tuple[str | None, str]:
        """``body`` as canonical SAN plus its annotation, or ``(None, "")``."""
        if not body:
            return (None, "")

        castle = _CASTLE_RE.match(body)
        if castle is not None:
            return ("O-O-O" if body.count("-") == _LONG_CASTLE_DASHES else "O-O", "")

        if self.fold_notation:
            colon = _COLON_CAPTURE_RE.match(body)
            if colon is not None:
                body = f"{colon.group(1)}x{colon.group(2)}"

        match = _SAN_PREFIX_RE.match(body)
        if match is None:
            return (None, "")
        tail = match.group(3)
        if tail and _ANNOTATION_RE.match(tail) is None:
            return (None, "")
        marks = "".join(char for char in tail if char in _ANNOTATION_KEEP)
        if not _ANNOTATION_MEANINGFUL.intersection(marks):
            marks = ""
        return (match.group(1) + match.group(2), marks)

    def _emit_prose(self, core: str, out: list[str]) -> None:
        """Split ordinary text the way SQLite would, but without the surprises.

        Punctuation inside a word (``don't``, ``anti-Sicilian``, ``e.g.``) is a
        separator here even though ``-``, ``.`` and ``'`` are token characters
        for the notation's sake.  Without this, ``jogada!`` and ``jogada`` would
        be different terms and half the prose in the corpus would be
        unreachable.
        """
        if core.isalnum():
            out.append(core)
            return
        annotation = self._annotation_token(core)
        if annotation:
            # A judgement standing on its own -- ``?? `` in prose, and the whole
            # of a query for it.  Without this the index would hold ``??`` and
            # the query for ``??`` would tokenize to nothing.
            out.append(annotation)
            return
        out.extend(part for part in _PROSE_SPLIT_RE.split(core) if part)

    @staticmethod
    def _annotation_token(core: str) -> str:
        """``core`` as a bare annotation token, or ``""`` if it is not one."""
        if _ANNOTATION_RE.match(core) is None:
            return ""
        kept = "".join(char for char in core if char in _ANNOTATION_KEEP)
        return kept if _ANNOTATION_MEANINGFUL.intersection(kept) else ""

    # -- querying --------------------------------------------------------- #

    def query_tokens(self, text: str) -> list[str]:
        """The tokens a user's query text expands to.  Same encoder, no surprises."""
        return self.tokens(text)

    def match_phrase(self, text: str) -> str:
        """``text`` as one FTS5 phrase, quoted and escaped.

        Multi-token input stays a *phrase* rather than becoming an implicit AND:
        a user typing ``Nf3!?`` means that move with that mark, not the two
        anywhere in a 900-page book.
        """
        tokens = self.tokens(text)
        if not tokens:
            return ""
        return '"' + " ".join(token.replace('"', '""') for token in tokens) + '"'

    def match_term(self, text: str, *, relax_check: bool = True) -> str:
        """One search term as an FTS5 expression, with the forgiving expansions.

        ``relax_check`` makes a bare ``Qxd5`` also find ``Qxd5+`` and ``Qxd5#``.
        A reader asking for a move is asking about the move; whether the printed
        page carried the check mark is not what they typed.  Turning it off is
        how a caller asks the literal question.
        """
        tokens = self.tokens(text)
        if not tokens:
            return ""
        if relax_check and len(tokens) == 1:
            token = tokens[0]
            bare = decode_token(token)
            if is_notation(bare) and not bare.endswith(("+", "#")):
                variants = (token, token + "+", token + "#")
                return "(" + " OR ".join(f'"{variant}"' for variant in variants) + ")"
        return self.match_phrase(text)


#: Prose is split on anything that is not a letter or a digit, in any script --
#: the corpus is Cyrillic and Greek as well as Latin (``CORPUS.md`` E6).
#: Underscore is a separator here even though it is the case mark: prose never
#: carries one, and letting it through would let a crafted word collide with a
#: move token.
_PROSE_SPLIT_RE: Final = re.compile(r"[\W_]+")


#: The instance nearly everything uses.
DEFAULT_TOKENIZER: Final = ChessTokenizer()
