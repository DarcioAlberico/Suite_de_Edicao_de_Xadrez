"""Decoding the figurine cipher an OCR engine leaves behind — SPEC §7.3.

A chess book prints its moves with figurines: ``♘xe5``, not ``Nxe5``.  No OCR
engine reads a figurine, because a figurine is not a letter.  What every engine
does instead is guess the nearest Latin shape, and the useful fact — measured
over 24 corpus pages in ``docs/quality/F5_REPORT_C2.md`` §4 — is that it guesses
**consistently**:

======================  ==============  =====================================
book                    1-char errors   what the symbols collapse onto
======================  ==============  =====================================
Gaprindashvili (E8)     96.7 %          ``W``×175 ``H``×113 ``S``×88 ``A``×67
Nunn (E2)               98.0 %          ``B``×65 ``W``×63 ``H``×55 ``S``×49
Aagaard (E1)            93.0 %          ``&``×23 ``W``×19 ``B``×14
======================  ==============  =====================================

So ``♕`` comes back as ``W`` every time, ``♖`` as ``H`` every time.  That is a
**substitution cipher**, and a cipher can be inverted.  Contrast the PDF's own
text layer, which loses the same glyphs as *noise* — 204 distinct forms in one
book, across 23 synthesised font subsets — and cannot be inverted at all.  That
asymmetry is the whole reason this module reads OCR output rather than the
layer that was already there.

What this module does **not** do is guess *which* piece a symbol is.  It infers
the cipher's alphabet, resolves the symbols that hard evidence pins down, and
hands the rest on as an explicit ambiguity.  The piece that resolves the rest
already exists and is not this one:
:mod:`caissa.notation.legality_repair` takes the legal moves of a position as
the candidate space, and a cipher assignment is structurally the same kind of
hypothesis as a language — ``W``/``H``/``S`` is to English what ``D``/``T``/``K``
is to German.  Give it a position and it decides; without one, nothing here can,
and pretending otherwise would be inventing a reading.

The honest win, then, is narrower than "the moves are fixed" and still large:
a token that was not notation at all becomes a move with a **known destination,
capture, disambiguator and check mark**, and a piece narrowed to five
candidates.  That is the difference between a proofreading task and a
retyping task.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from caissa.notation.nag_table import move_suffix_class

__all__ = [
    "CIPHER_SLOT",
    "CipherReport",
    "CipherSymbol",
    "ENGLISH_PIECES",
    "decode",
    "infer_cipher",
]

#: The English piece letters, which are what a decoded move is written in.
#: The pawn is not here: a pawn move carries no letter, which is precisely why
#: an empty prefix is evidence of a pawn and not of a lost glyph.
ENGLISH_PIECES: tuple[str, ...] = ("K", "Q", "R", "B", "N")

#: OCR language codes (ISO-639-2, what :mod:`caissa.ocr` speaks) to notation
#: locale codes (what :mod:`caissa.notation.languages` speaks).  Written out
#: rather than derived because the two vocabularies are genuinely different
#: standards; ``test_every_notation_locale_is_reachable`` fails if a locale
#: ever becomes unreachable through this table.
_OCR_TO_LOCALE: Mapping[str, str] = {
    "eng": "en", "por": "pt", "spa": "es", "fra": "fr",
    "ita": "it", "deu": "de", "nld": "nl", "rus": "ru",
}


#: Cyrillic letters and the Latin letters they are visually identical to.  A
#: PDF of a Russian book routinely carries the Latin one — ``Kd2`` where the
#: page printed ``Кd2`` — and that is a *different* defect from the figurine
#: cipher: the token still parses, as the wrong move, which is worse than
#: garbage because nothing downstream flags it.  Folding here keeps this module
#: from claiming a case it cannot fix; the fix belongs with a homoglyph
#: normaliser and :mod:`caissa.notation.legality_repair`'s locale replay.
#: See docs/quality/F5_REPORT_C2.md §6.
_HOMOGLYPHS: Mapping[str, str] = {
    "К": "K", "С": "C", "Р": "P", "В": "B", "А": "A", "Е": "E",
    "М": "M", "Т": "T", "Н": "H", "О": "O", "Х": "X",
}


def _fold_homoglyphs(text: str) -> str:
    return "".join(_HOMOGLYPHS.get(c, c) for c in text)


def _piece_letters(notation_lang: str) -> frozenset[str]:
    """Every letter that is a legitimate piece in ``notation_lang``.

    **This is the guard that keeps the decoder from corrupting correct text.**
    Russian prints the knight as ``К`` and the bishop as ``С``; neither is an
    English piece letter, so without this every correct Russian page reads as
    a cipher and gets rewritten.  Measured before the guard: Boleslávski, five
    pages of correct notation, **5 of 5 accused**.

    The letters come from :data:`caissa.notation.languages.LOCALES`, so adding
    a locale there is enough — there is no second table here to forget.

    **The empty default is the one to use unless you are certain.**  Narrowing
    to one locale is what makes ``Q`` and ``N`` look like cipher symbols, and
    the language of a book's *prose* is not the language of its *moves*:
    measured on `400 Quebra-cabeças` p160, a Portuguese book printing English
    notation, passing ``"por"`` here made the decoder rewrite eight correct
    moves into ``?f6``, ``?xg3``, ``?d2``.  That is the decoder becoming a new
    way to break books.

    With no language every locale's letters count as clean, so the decoder
    misses symbols rather than inventing them.  It costs recall — ``S``, ``A``
    and ``B`` are piece letters somewhere, so a Tesseract page that uses them
    as figurine stand-ins keeps those moves unreadable — and that is the right
    side to err on.
    """
    from caissa.notation.languages import LOCALES

    lang = notation_lang.lower()
    codes = ([_OCR_TO_LOCALE.get(lang, lang)] if lang else list(LOCALES))
    letters: set[str] = set()
    for code in codes:
        locale = LOCALES.get(code)
        if locale is None:
            continue
        for attribute in ("king", "queen", "rook", "bishop", "knight", "pawn"):
            value = getattr(locale, attribute, None)
            if value:
                letters.add(value)
                letters.add(_fold_homoglyphs(value))
    return frozenset(letters or ENGLISH_PIECES)

#: What :func:`decode` writes where a symbol is known to be a piece but not
#: *which* piece.  Deliberately not a letter: a placeholder that parses as a
#: move would be a lie that spreads, and the whole point is that the caller
#: must see the ambiguity.
CIPHER_SLOT = "?"
#: Longest prefix the decoder rewrites — the look-alike clusters of a damaged
#: text layer run to five characters (``ll:'i`` for ♕).
_MAX_PREFIX = 5

#: Every dash a PDF emits where notation means "moves to".  Long-form notation
#: writes ``Кра8—b7``, and a body that only accepts the ASCII hyphen reads that
#: as a prefix of four characters and calls it damage.  The same list
#: :mod:`caissa.notation.legality_repair` keeps, for the same reason.
_LINKS = r"x:×\-‐‑‒–—−"

#: The body of a move after the piece letter.  Anchored at the end so that what
#: sits in front of it is exactly the piece slot.  The **tail** it tolerates
#: after the square is the annotation alphabet of
#: :mod:`caissa.notation.nag_table` (``±``, ``⩲``, ``!?``, ``²``…, passo A4) --
#: it is the tail that widens here, never the substitution alphabet of the
#: cipher, which stays what the page proves.
_MOVE_BODY = re.compile(
    rf"(?:[a-h]?[1-8]?[{_LINKS}]?[a-h][1-8]"
    rf"(?:=(?P<promo>[A-Za-z?]))?[{move_suffix_class()}]{{0,3}})$")

#: A move number glued to the move: ``4.Kd3``, ``1...Nf6``.
_MOVE_NUMBER = re.compile(r"^\d{1,3}\.{1,3}")
_BARE_RANK_BODY = re.compile(r"^[1-8][a-h][1-8]")

#: Trailing punctuation a sentence leaves on a move.
_TRIM = "(),;:."


@dataclass(frozen=True, slots=True)
class CipherSymbol:
    """One symbol the engine used where a figurine should have been."""

    symbol: str
    support: int
    #: The English piece letter, when something *proved* it.  Never a guess.
    piece: str = ""
    #: Why, in Brazilian Portuguese, for the UI and for the report.
    evidence_pt: str = ""

    @property
    def resolved(self) -> bool:
        return bool(self.piece)


@dataclass(frozen=True, slots=True)
class CipherReport:
    """What the text says about its own cipher."""

    symbols: tuple[CipherSymbol, ...] = ()
    #: Move tokens whose prefix was already a correct English piece letter.
    clean_moves: int = 0
    #: Move tokens carrying a cipher symbol.
    ciphered_moves: int = 0
    #: Move tokens with no prefix at all — pawn moves.
    pawn_moves: int = 0
    notes: tuple[str, ...] = ()

    @property
    def judged(self) -> int:
        return self.clean_moves + self.ciphered_moves

    @property
    def is_ciphered(self) -> bool:
        """True when most of the piece moves carry a symbol that is not a
        piece letter.  A page of correct notation must answer ``False`` here,
        or the decoder would rewrite text that was never broken."""
        return self.judged >= 12 and self.ciphered_moves > 0.5 * self.judged

    @property
    def assignment(self) -> Mapping[str, str]:
        """``symbol -> English piece letter`` for the symbols that are settled."""
        return {s.symbol: s.piece for s in self.symbols if s.resolved}

    @property
    def unresolved(self) -> tuple[CipherSymbol, ...]:
        return tuple(s for s in self.symbols if not s.resolved)

    def describe_pt(self) -> str:
        if not self.symbols:
            return "Nenhum símbolo de figurino encontrado nesta página."
        head = (f"{self.ciphered_moves} de {self.judged} lances usam um símbolo "
                f"no lugar do figurino.")
        lines = [head]
        for symbol in self.symbols:
            if symbol.resolved:
                lines.append(f"  {symbol.symbol!r} = {symbol.piece} "
                             f"({symbol.support}×) — {symbol.evidence_pt}")
            else:
                lines.append(f"  {symbol.symbol!r} = ? ({symbol.support}×) — "
                             f"peça indeterminada; é preciso a posição para "
                             f"decidir (caissa.notation.legality_repair)")
        return "\n".join(lines)


def _is_cluster(prefix: str) -> bool:
    """A damaged layer's multi-character look-alike: short, not all alphanumeric."""
    return 1 < len(prefix) <= _MAX_PREFIX and not all(ch.isalnum() for ch in prefix)


def _split(token: str) -> tuple[str, str, str] | None:
    """``(prefix, body, promotion)`` for a token that ends in a move body."""
    trimmed = token.strip(_TRIM)
    match = _MOVE_BODY.search(trimmed)
    if match is None or match.start() == len(trimmed):
        return None
    prefix = _MOVE_NUMBER.sub("", trimmed[:match.start()])
    body = match.group(0)
    if not prefix and _BARE_RANK_BODY.match(body):
        # ``2g5``: a rank disambiguator needs a piece letter before it, so a
        # bare digit in front of a square is a look-alike (Tesseract reads ♗
        # as ``2`` on the Gaprindashvili), not part of the move.
        prefix, body = body[0], body[1:]
    return prefix, body, match.group("promo") or ""


def infer_cipher(text: str, *, notation_lang: str = "",
                 min_support: int = 2) -> CipherReport:
    """Read ``text`` and report the figurine cipher it uses, if it uses one.

    ``min_support`` keeps a one-off OCR smudge from being promoted to a piece
    symbol.  Two is the floor at which "twice is a pattern" begins to hold; a
    symbol seen once stays out of the alphabet and its move stays unreadable,
    which is the safe direction.

    ``notation_lang`` is the language the **moves** are printed in, which is
    not the language of the prose around them — see :func:`_piece_letters`.
    Leave it empty unless something proved it; empty is the safe reading.

    The only evidence this function acts on is **promotion**.  ``f8=W`` is a
    pawn reaching the eighth rank and becoming something, and in published
    games that something is a queen overwhelmingly often — under-promotion is
    rare enough to be a named event.  So a symbol that appears after ``=`` is
    the queen.  Every other symbol is reported with its support and left
    unresolved, because frequency alone cannot tell a rook from a king and
    saying otherwise would be a guess wearing a number.
    """
    native = _piece_letters(notation_lang)
    symbols: Counter[str] = Counter()
    promoted: Counter[str] = Counter()
    clean = ciphered = pawns = 0

    for raw in text.split():
        parts = _split(raw)
        if parts is None:
            continue
        prefix, _body, promotion = parts
        if promotion and promotion not in native:
            promoted[promotion] += 1
        if not prefix:
            pawns += 1
            continue
        if prefix in native:
            clean += 1
            continue
        if len(prefix) == 1 or _is_cluster(prefix):
            # One character: an OCR engine's look-alike.  A short cluster with
            # a non-alphanumeric character in it: a damaged text layer's
            # look-alike (``'it>`` for ♔, ``l:t`` for ♖ — OCR_UI_ROADMAP passo 3,
            # consistent per figurine on the Gaprindashvili).  Both are symbols.
            symbols[prefix] += 1
            ciphered += 1
        else:
            # A plain run of letters glued to a square: the glyph did not
            # survive as one symbol, or it is a word.  Counted, never decoded.
            ciphered += 1

    notes: list[str] = []
    alphabet = [(s, n) for s, n in symbols.most_common() if n >= min_support]
    dropped = sum(n for s, n in symbols.items() if n < min_support)
    if dropped:
        notes.append(f"{dropped} símbolo(s) vistos menos de {min_support} vezes "
                     f"ficaram de fora do alfabeto")

    queen = promoted.most_common(1)[0][0] if promoted else ""
    if queen and queen not in {s for s, _ in alphabet}:
        # Promotion is strong enough to admit a symbol the move text alone did
        # not support: a glyph that only ever appears after "=" is still a
        # queen.
        alphabet.append((queen, symbols.get(queen, 0)))

    out: list[CipherSymbol] = []
    for symbol, support in alphabet:
        if symbol == queen:
            out.append(CipherSymbol(
                symbol=symbol, support=support, piece="Q",
                evidence_pt=(f"aparece depois de «=» em {promoted[symbol]} "
                             f"promoção(ões); promoção é para dama salvo "
                             f"exceção nomeada")))
        else:
            out.append(CipherSymbol(symbol=symbol, support=support))

    return CipherReport(
        symbols=tuple(out), clean_moves=clean, ciphered_moves=ciphered,
        pawn_moves=pawns, notes=tuple(notes))


def decode(text: str, report: CipherReport, *,
           assignment: Mapping[str, str] | None = None, force: bool = False) -> str:
    """Rewrite ``text`` with the cipher inverted as far as it is known.

    A symbol the report resolved becomes its English piece letter.  A symbol in
    the alphabet but unresolved becomes :data:`CIPHER_SLOT`, so the token
    afterwards is a move with an explicit hole rather than a move that quietly
    claims the wrong piece.  Anything the report never recognised is left
    exactly as it was found: this function does not improvise.

    ``assignment`` overrides the report — that is how a caller feeds back a
    reading that :mod:`caissa.notation.legality_repair` settled against a real
    position, and re-decodes the page with the holes filled.

    ``force`` skips the page-level guard below.  It is for a caller holding
    evidence of a wider scope than one page — the book's proven table
    (:mod:`caissa.ocr.notation.book_cipher`) — on a region too short for the
    guard's twelve moves; the caller still has to show a ciphered majority.
    """
    if not report.is_ciphered and not force:
        # Refusing here is the whole safety property: a page whose notation was
        # never broken must come back byte for byte, or the decoder is a new
        # way to break books.  ``is_ciphered`` needs a majority of the piece
        # moves to carry a symbol, which correct text never reaches.
        return text
    table = dict(report.assignment)
    if assignment:
        table.update(assignment)
    known = {s.symbol for s in report.symbols}
    if not known:
        return text

    out: list[str] = []
    for raw in text.split():
        parts = _split(raw)
        if parts is None:
            out.append(raw)
            continue
        prefix, _body, promotion = parts
        token = raw

        # The promotion letter is the same cipher in a different slot: "f8=W"
        # is a pawn becoming a queen, and leaving it as W would keep the one
        # move whose piece is *certain* unreadable.
        if promotion and promotion in known:
            replacement = table.get(promotion, CIPHER_SLOT)
            index = token.rfind("=" + promotion)
            if index >= 0:
                token = token[:index + 1] + replacement + token[index + 2:]

        # One character (Tesseract's look-alike) or a short cluster (a damaged
        # layer's: ``'it>`` for ♔) — the alphabet decides what counts.
        if prefix in known and 0 < len(prefix) <= _MAX_PREFIX:
            replacement = table.get(prefix, CIPHER_SLOT)
            # Rebuild from the original token so that trimmed punctuation and
            # the move number survive untouched.
            index = token.find(prefix)
            if index >= 0:
                token = token[:index] + replacement + token[index + len(prefix):]

        out.append(token)
    return " ".join(out)


def candidate_locales(report: CipherReport,
                      pieces: Sequence[str] = ENGLISH_PIECES) -> Iterable[
                          Mapping[str, str]]:
    """Every assignment of the unresolved symbols to the remaining pieces.

    These are the hypotheses a caller hands to
    :func:`caissa.notation.legality_repair.repair_movetext` once a position is
    known — the same shape of hypothesis that module already generates for
    languages, because a cipher *is* a locale: ``W``/``H``/``S`` is to English
    what ``D``/``T``/``K`` is to German.

    The count is small on purpose.  Five pieces give at most 120 permutations,
    and the queen is usually pinned by promotion first, which leaves 24.
    """
    from itertools import permutations

    fixed = dict(report.assignment)
    free = [s.symbol for s in report.unresolved]
    remaining = [p for p in pieces if p not in fixed.values()]
    if not free:
        yield dict(fixed)
        return
    for combination in permutations(remaining, len(free)):
        candidate = dict(fixed)
        candidate.update(dict(zip(free, combination)))
        yield candidate
