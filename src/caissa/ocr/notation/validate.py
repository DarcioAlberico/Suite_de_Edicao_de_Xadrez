"""Chess validation of a recognised movetext region — Sol §SOL-8.

The legality repairer (:mod:`caissa.notation.legality_repair`) existed and
nothing in the import path called it: the cascade emitted ``Kfz`` and ``bs``
as text and moved on.  This module is the link, and it is written around
one rule from Sol §2: **context constrains; it never creates.**  Legality
chooses between readings the OCR actually produced (and their one-glyph
confusions); it never completes a game the page does not show.

For one region the steps are:

1. **Homoglyphs.**  Cyrillic capitals that are visually Latin (``Кd2``)
   are folded before analysis so the locale replay sees one alphabet.
2. **Cipher.**  A figurine font whose glyphs came out as stray letters is
   detected and decoded (:mod:`caissa.ocr.notation.cipher`), only when the
   cipher module resolves it with its own guards.
3. **Separators.**  Tokens the OCR glued (``Nf3Nc6``) or split (``N f3``)
   get candidate readings; a candidate is used only if the replay accepts
   it and the original does not.
4. **Position.**  A replay needs a start.  It comes from a diagram whose FEN
   provenance is trusted, or from the text itself when it starts at move
   one.  ``side_to_move`` is taken from the caption or the numbering and is
   *never* defaulted in silence: an unknown side means no replay, and the
   report says so.
5. **Replay** of the main line and of each parenthesised variation from
   the position before its parent move; comments in braces are skipped.
6. **Decision.**  A correction is auto-applied only when it is unique and
   the whole block (with it) replays legally.  Anything else — an
   unresolved token, a disputed locale, two plausible repairs — goes to
   review with the alternatives spelled out.  A move-shaped token that only
   the replay could not justify keeps the OCR's reading: deleting it would
   be an invention in reverse.

Everything counted here — corrected, unresolved, invented-looking, repeated
— goes into the region's provenance and the benchmark.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import chess

from ..decision import Decision, RegionDecision, decide
from ..lexicon import is_move_token, normalise_lang, tokenize
from ..types import OcrLine, OcrResult, OcrWord
from .cipher import (ENGLISH_PIECES, _fold_homoglyphs, _piece_letters, _split, decode,
                     infer_cipher)

__all__ = ["ValidationOutcome", "validate_region"]

_TO_LOCALE = {"eng": "en", "por": "pt", "spa": "es", "fra": "fr", "ita": "it",
              "deu": "de", "nld": "nl", "rus": "ru"}
_FIRST_MOVE = re.compile(r"^\s*1\.(?!\.)")
_BLACK_START = re.compile(r"^\s*(\d+)\.\.\.")
_WHITE_START = re.compile(r"^\s*(\d+)\.(?!\.)")
_COMMENT = re.compile(r"\{[^}]*\}")
_GLUED = re.compile(r"^([KQRBNDTCSAFL]?[a-h]?[1-8]?x?[a-h][1-8][+#]?)([KQRBNDTCSAFL]?[a-h]?[1-8]?x?[a-h][1-8][+#]?)$")
_REPEAT_LIMIT = 3
_MOVE_NUMBER_PREFIX = re.compile(r"^\d{1,3}\.{1,3}")
_NUMBER_PREFIX = re.compile(r"^(\d+\.{1,3})(.+)$")
#: Glyph pairs an engine actually confuses.  A repair that changes one of
#: these is *supported by the image*; a repair that turns a confident ``B``
#: into an ``N`` is not, however legal the result, and is offered to the
#: reviewer instead of applied (Sol §2: legality chooses among observed
#: candidates, it does not create them).
_CONFUSIONS: frozenset[frozenset[str]] = frozenset(
    frozenset(pair) for pair in (
        ("l", "1"), ("I", "1"), ("|", "1"), ("i", "1"), ("0", "O"), ("o", "0"), ("S", "5"),
        ("s", "5"), ("B", "8"), ("G", "6"), ("Z", "2"), ("z", "2"), ("q", "g"), ("g", "9"),
        ("ó", "6"), ("ö", "6"), ("ô", "6"), ("á", "4"), ("ä", "4"), ("à", "4"), ("í", "1"),
        ("é", "e"), ("è", "e"), ("c", "e"), ("e", "c"), ("f", "t"), ("h", "b"), ("n", "h"),
        ("d", "a"), ("×", "x"), (":", "x"), ("K", "R"), ("R", "K"), ("Q", "O"), ("D", "O"),
        ("T", "I"), ("C", "G"), ("L", "I"), ("A", "4"), ("+", "t"), ("#", "+"),
    )
)
_MOVE_CONFIDENCE_FOR_DOUBT = 0.80
#: Accented vowels an engine reads for a rank digit in a serif face: ``dó``
#: for ``d6``, ``exdá`` for ``exd4``.  Only ever a *candidate*; the replay
#: decides.
_ACCENT_DIGITS = str.maketrans({"ó": "6", "ö": "6", "ô": "6", "á": "4", "ä": "4", "à": "4",
                                "í": "1", "ì": "1", "é": "e", "è": "e"})


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    result: OcrResult
    decision: RegionDecision
    attempted: bool
    replayed_to_end: bool = False
    language: str | None = None
    start_fen: str | None = None
    side_to_move: str | None = None
    moves_seen: int = 0
    moves_replayed: int = 0
    corrected: tuple[tuple[str, str], ...] = ()
    unresolved: tuple[tuple[str, tuple[str, ...]], ...] = ()
    repeated: tuple[str, ...] = ()
    variations: int = 0
    variations_ok: int = 0
    reasons_pt: tuple[str, ...] = ()
    cipher: dict[str, Any] = field(default_factory=dict)
    #: OCR_UI_ROADMAP passo 3: ``(symbol, piece, raw token, legal SAN)`` for every
    #: cipher symbol this block's *complete* legal replay proved — the
    #: evidence :class:`~caissa.ocr.notation.book_cipher.BookCipher` collects.
    proven_pieces: tuple[tuple[str, str, str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "replayed_to_end": self.replayed_to_end,
            "language": self.language,
            "start_fen": self.start_fen,
            "side_to_move": self.side_to_move,
            "moves_seen": self.moves_seen,
            "moves_replayed": self.moves_replayed,
            "corrected": [list(c) for c in self.corrected],
            "unresolved": [[raw, list(near)] for raw, near in self.unresolved],
            "repeated": list(self.repeated),
            "variations": self.variations,
            "variations_ok": self.variations_ok,
            "reasons": list(self.reasons_pt),
            "cipher": dict(self.cipher),
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _side_from_numbering(text: str) -> tuple[str | None, int | None]:
    """``("w", 12)`` for ``12.Nf3 …``, ``("b", 12)`` for ``12...Nf6 …``."""
    match = _BLACK_START.match(text)
    if match:
        return "b", int(match.group(1))
    match = _WHITE_START.match(text)
    if match:
        return "w", int(match.group(1))
    return None, None


def _with_side(fen: str, side: str) -> str:
    parts = fen.split()
    if len(parts) >= 2:
        parts[1] = side
        return " ".join(parts)
    return fen


def _split_number(token: str) -> tuple[str, str]:
    match = _NUMBER_PREFIX.match(token)
    return (match.group(1), match.group(2)) if match else ("", token)


def _separator_candidates(text: str) -> list[str]:
    """Readings with one glued pair split, one split pair joined, or accented
    vowels read back as rank digits."""
    tokens = text.split()
    out: list[str] = []

    def fold(token: str) -> str:
        prefix, body = _split_number(token)
        if is_move_token(body):
            return token
        folded = body.translate(_ACCENT_DIGITS)
        return prefix + folded if is_move_token(folded) else token

    folded = [fold(t) for t in tokens]
    if folded != tokens:
        out.append(" ".join(folded))
    for i, token in enumerate(tokens):
        prefix, body = _split_number(token)
        if is_move_token(body):
            continue
        match = _GLUED.match(body)
        if match and is_move_token(match.group(1)) and is_move_token(match.group(2)):
            out.append(" ".join(tokens[:i] + [prefix + match.group(1), match.group(2)]
                                + tokens[i + 1:]))
    for i in range(len(tokens) - 1):
        prefix, a = _split_number(tokens[i])
        b = tokens[i + 1]
        if (len(a) == 1 and a in "KQRBNDTCSAFL" and is_move_token(b)
                and is_move_token(a + b)):
            out.append(" ".join(tokens[:i] + [prefix + a + b] + tokens[i + 2:]))
    return out[:4]


def _repeated_moves(tokens: Sequence[str]) -> tuple[str, ...]:
    """Move sequences printed again and again — the VLM's tell (F11 cycle 2).

    A single move three times in a row, or a run of two to four moves twice
    in a row.  A legitimate repetition (a perpetual check) also matches, so
    the caller only holds it against a block that does *not* replay.
    """
    moves = [t for t in tokens if is_move_token(t)]
    out: list[str] = []
    for n in range(1, 5):
        needed = _REPEAT_LIMIT if n == 1 else 2
        for i in range(0, len(moves) - n * needed + 1):
            window = moves[i:i + n]
            if all(moves[i + k * n:i + (k + 1) * n] == window for k in range(1, needed)):
                key = " ".join(window)
                if key not in out:
                    out.append(key)
    return tuple(out)


def _supported(raw: str, new: str, confidence: float) -> bool:
    """Is the repair ``raw → new`` something the image could have produced?

    Yes when the OCR itself doubted the token, or when every changed glyph
    is a known confusion pair.  A confident token rewritten through an
    unrelated letter is a legal *invention*, and stays a suggestion.
    """
    if confidence < _MOVE_CONFIDENCE_FOR_DOUBT:
        return True
    a, b = _split_number(raw)[1], _split_number(new)[1]
    if len(a) != len(b):
        return abs(len(a) - len(b)) == 1 and (a in b or b in a)   # a dropped/added mark
    changed = [(x, y) for x, y in zip(a, b, strict=True) if x != y]
    return all(frozenset(pair) in _CONFUSIONS for pair in changed)


def _apply_corrections(result: OcrResult, corrections: dict[str, str]) -> OcrResult:
    """Rewrite the corrected tokens in place; every other word untouched."""
    if not corrections:
        return result
    lines = []
    for line in result.lines:
        words = []
        for word in line.words:
            key = word.text.strip()
            new = corrections.get(key)
            if new is None or new == key:
                words.append(word)
                continue
            words.append(OcrWord(text=new, box=word.box, confidence=word.confidence, chars=(),
                                 block_index=word.block_index,
                                 paragraph_index=word.paragraph_index,
                                 line_index=word.line_index, word_index=word.word_index))
        lines.append(OcrLine(words=tuple(words), box=line.box, baseline=line.baseline,
                             block_index=line.block_index, paragraph_index=line.paragraph_index,
                             line_index=line.line_index, kind=line.kind,
                             font_size=line.font_size))
    return OcrResult(engine=result.engine, lang=result.lang, lines=tuple(lines),
                     region_kind=result.region_kind, duration_s=result.duration_s,
                     warnings=result.warnings, meta=result.meta)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate_region(result: OcrResult, decision: RegionDecision, *, lang: str = "",
                    start_fen: str | None = None, fen_trusted: bool = False,
                    side_to_move: str | None = None, notation_locale: str | None = None,
                    image: Any = None,
                    book_cipher: Mapping[str, str] | None = None) -> ValidationOutcome:
    """Replay the region's moves and decide what the legality evidence allows.

    ``book_cipher`` (OCR_UI_ROADMAP passo 3) is the ``symbol → piece`` table the
    book's earlier blocks proved by legality.  It fills the holes the page's
    own cipher report leaves, under the decoder's own guard (the page must be
    ciphered), and a token it turns into a move is applied to the reading —
    the token was not a word and not a move before, and the table is evidence
    from this book, not a guess.
    """
    text = _fold_homoglyphs(result.text)
    original_text = text
    langs = normalise_lang(lang)
    reasons: list[str] = []
    cipher_info: dict[str, Any] = {}
    decoded_by_table: dict[str, str] = {}

    # 2. Cipher
    report = infer_cipher(text, notation_lang=_TO_LOCALE.get(langs[0], "") if langs else "",
                          # A symbol the book proved is not a smudge even when
                          # this region shows it once.
                          min_support=1 if book_cipher else 2)
    page_alphabet = {s.symbol for s in report.symbols}
    table = {s: p for s, p in (book_cipher or {}).items() if s in page_alphabet}
    # The page's own resolution outranks the book's on a symbol both settled.
    table.update(report.assignment)
    # The page-level guard (12 judged moves, a ciphered majority) is the
    # decoder's safety property against text that was never broken.  A book
    # table is evidence that *this* book's font is broken, so with one at
    # hand a region needs a ciphered majority and two ciphered moves, not
    # twelve: the analysis blocks of a problem book are short.
    book_symbols = [s for s in table if s not in report.assignment]
    ciphered = report.is_ciphered or (
        bool(book_symbols) and report.ciphered_moves >= 2
        and report.ciphered_moves > 0.5 * report.judged)
    if ciphered and table:
        decoded = decode(text, report, assignment=table, force=not report.is_ciphered)
        cipher_info = {"symbols": dict(table), "judged": report.judged,
                       "from_book": sorted(s for s in table if s not in report.assignment)}
        if decoded != text:
            if report.assignment:
                reasons.append("cifra de figurinos inferida e decodificada: "
                               + ", ".join(f"{k}→{v}"
                                           for k, v in sorted(report.assignment.items())))
            if cipher_info["from_book"]:
                reasons.append("cifra do livro aplicada: "
                               + ", ".join(f"{k}→{table[k]}" for k in cipher_info["from_book"]))
            decoded_by_table = _decoded_tokens(text, decoded, set(table))
            text = decoded

    tokens = tokenize(text)
    move_count = sum(1 for t in tokens if is_move_token(t))
    repeated = _repeated_moves(tokens)
    if repeated:
        reasons.append("sequência de lances repetida: " + "; ".join(repeated)
                       + " (suspeita de invenção se o bloco não reproduzir)")

    # 4. Position and side
    side_hint, number = _side_from_numbering(text)
    fen: str | None = None
    side: str | None = side_to_move
    if start_fen and fen_trusted:
        fen = start_fen
        if side is None:
            side = side_hint
            fen_side = fen.split()[1] if len(fen.split()) > 1 else None
            if side is not None and fen_side is not None and fen_side != side:
                reasons.append(f"a FEN do diagrama diz '{fen_side}' a jogar e a numeração "
                               f"impressa diz '{side}': a numeração prevalece, por ser "
                               f"evidência da página.")
        if side is None:
            reasons.append("posição de partida conhecida, mas o lado a jogar não: replay não "
                           "tentado (nenhum valor padrão foi assumido).")
            fen = None
        else:
            fen = _with_side(fen, side)
    elif _FIRST_MOVE.match(text):
        fen, side = chess.STARTING_FEN, "w"
    elif (start := _game_start(text)) is not None:
        # OCR_UI_ROADMAP passo 3: a whole game printed after its header
        # ("Smith – Jones, London 1990") starts at move one a few tokens in;
        # the header is prose and the replay begins where the game does.
        fen, side = chess.STARTING_FEN, "w"
        text = text[start:]
        original_text = original_text[_game_start(original_text) or 0:]
        reasons.append("bloco reproduzido a partir do lance 1 depois do cabeçalho.")
    elif start_fen and not fen_trusted:
        reasons.append("diagrama próximo sem proveniência confiável da FEN: replay não tentado.")

    if fen is None or move_count == 0:
        if fen is None and move_count:
            reasons.append("posição inicial desconhecida: a legalidade não foi testada.")
        # No replay, but the book's proven table still applies (that is what
        # it is for: the 98 % of blocks without a position).
        new_result = _apply_corrections(result, decoded_by_table) if decoded_by_table else result
        if decoded_by_table:
            new_result = new_result.with_meta(book_cipher_applied=dict(decoded_by_table))
            reasons.append(f"{len(decoded_by_table)} lance(s) reescritos pela cifra do livro.")
        new_decision = decision if not reasons else RegionDecision(
            decision.decision, decision.score, decision.accept_threshold,
            decision.review_threshold, decision.reasons_pt + tuple(reasons),
            decision.evidence, decision.flagged_words, decision.demoted, decision.legality)
        return ValidationOutcome(new_result, new_decision, attempted=False,
                                 moves_seen=move_count, repeated=repeated,
                                 reasons_pt=tuple(reasons), cipher=cipher_info,
                                 side_to_move=side)

    # 5. Replay: the original reading, then the separator candidates.
    locale = notation_locale or None

    # 5a. OCR_UI_ROADMAP passo 3: the cipher symbols the page (and the book)
    # could not settle are a *hypothesis space*, like a locale — ``W``/``H``/
    # ``S`` is to English what ``D``/``T``/``K`` is to German — and a replay
    # decides between assignments the way it decides between locales.  Each
    # assignment decodes the block and replays it; the one that replays
    # furthest, alone, wins, and the symbols it used in legal moves are the
    # evidence the book table collects.  A tie is left as it was found.
    free = [s.symbol for s in report.symbols if s.symbol not in table]
    if ciphered and free:
        hypothesis = _best_assignment(original_text, report, table, free, locale, fen)
        if hypothesis is not None:
            table = dict(hypothesis)
            decoded = decode(original_text, report, assignment=table, force=True)
            decoded_by_table = _decoded_tokens(original_text, decoded, set(table))
            text = decoded
            cipher_info = {**cipher_info, "symbols": dict(table),
                           "by_replay": sorted(set(free) & set(table))}
            reasons.append("cifra resolvida pela reprodução legal do bloco: "
                           + ", ".join(f"{k}→{table[k]}" for k in sorted(set(free) & set(table))))

    main_line, variations, best_report, best_text = _replay_block(text, locale, fen)
    if best_text != main_line:
        reasons.append("leitura alternativa (separador ou acento lido como dígito) adotada "
                       "porque reproduz legalmente melhor que a original.")

    from caissa.notation.legality_repair import repair_movetext

    variations_ok = 0
    for variation in variations:
        parent_side, parent_number = _side_from_numbering(variation)
        moves = best_report.moves
        before = None
        if parent_number is not None:
            ply = (parent_number - 1) * 2 + (0 if parent_side == "w" else 1)
            before = next((m.fen_before for m in moves if m.ply == ply), None)
        if before is None:
            continue
        sub = repair_movetext(variation, language=best_report.language, start_fen=before)
        if sub.replayed_to_end and not sub.unresolved:
            variations_ok += 1

    # 6. Decide.
    corrections: dict[str, str] = {}
    for move in best_report.moves:
        if move.was_repaired:
            rendered = _render(move.san, best_report.language)
            if rendered != move.raw:
                corrections[move.raw] = rendered
    # A separator or accent candidate that won is itself a correction of the
    # tokens it changed, applied only under the same uniqueness rule.
    if best_text != main_line:
        for before, after in zip(main_line.split(), best_text.split(), strict=False):
            if before != after and before not in corrections:
                corrections[before] = after
    unique = (best_report.replayed_to_end and not best_report.unresolved
              and not best_report.reading_disputed)
    proven = (_proven_pieces(best_report.moves, original_text, text,
                             language=best_report.language) if unique else ())
    unresolved = tuple((u.raw, tuple(u.near_misses)) for u in best_report.unresolved)
    confidences = {w.text.strip(): w.confidence for w in result.words}
    applied: dict[str, str] = {}
    suggested: dict[str, str] = {}
    if unique and corrections:
        for raw, new in corrections.items():
            if _supported(raw, new, confidences.get(raw, 0.0)):
                applied[raw] = new
            else:
                suggested[raw] = new
        if applied:
            reasons.append("correções únicas e integralmente legais aplicadas: "
                           + ", ".join(f"{a}→{b}" for a, b in sorted(applied.items())))
        if suggested:
            reasons.append("correções legais mas sem apoio visual (glifo confiante, sem par de "
                           "confusão), deixadas para revisão: "
                           + ", ".join(f"{a}→{b}" for a, b in sorted(suggested.items())))
            unresolved = unresolved + tuple((raw, (new,)) for raw, new in suggested.items())
    elif corrections:
        reasons.append("correções possíveis não aplicadas (bloco não reproduz até o fim ou "
                       "leitura disputada): " + ", ".join(f"{a}→{b}" for a, b in
                                                          sorted(corrections.items())))
    if best_report.reading_disputed:
        reasons.append("convenção de peças disputada entre "
                       + ", ".join(best_report.language_disputed) + ".")
    if unresolved:
        reasons.append(f"{len(unresolved)} lance(s) sem leitura legal: "
                       + ", ".join(f"{raw} (próximos: {', '.join(near) or '—'})"
                                   for raw, near in unresolved[:4]))

    if decoded_by_table:
        # The cipher's rewrites are applied on their own evidence — the book's
        # proven table, or the assignment this very block replayed under —
        # not on the visual-support rule of a one-glyph confusion; and they
        # stand even when the block did not replay to the end, because a hole
        # elsewhere in the block does not un-prove them.
        for raw, new in decoded_by_table.items():
            applied.setdefault(raw, new)
        reasons.append(f"{len(decoded_by_table)} lance(s) reescritos pela cifra "
                       f"({'do livro' if cipher_info.get('from_book') else 'do bloco'}).")
    new_result = _apply_corrections(result, applied) if applied else result
    if applied:
        new_result = new_result.with_meta(legality_corrections=applied)
    if decoded_by_table:
        new_result = new_result.with_meta(book_cipher_applied=dict(decoded_by_table))
    legality = {
        "replayed_to_end": best_report.replayed_to_end,
        "unresolved": len(unresolved),
        "moves": len(best_report.moves),
        "corrected": len(applied),
        "disputed": best_report.reading_disputed,
        "repeated": len(repeated),
    }
    new_decision = decide(
        new_result, decision.score, image=image, langs=langs, region_kind=result.region_kind,
        accept_threshold=decision.accept_threshold,
        reached_threshold=not decision.below_threshold, legality=legality,
        trusted_source=result.engine == "pdf_text_layer")
    suspicious_repeat = bool(repeated) and not best_report.replayed_to_end
    if (unresolved or best_report.reading_disputed or suspicious_repeat) and \
            new_decision.decision is Decision.ACCEPTED:
        new_decision = RegionDecision(
            Decision.REVIEW, new_decision.score, new_decision.accept_threshold,
            new_decision.review_threshold, new_decision.reasons_pt + tuple(reasons),
            new_decision.evidence, new_decision.flagged_words, True, legality)
    elif reasons:
        new_decision = RegionDecision(
            new_decision.decision, new_decision.score, new_decision.accept_threshold,
            new_decision.review_threshold, new_decision.reasons_pt + tuple(reasons),
            new_decision.evidence, new_decision.flagged_words, new_decision.demoted, legality)
    return ValidationOutcome(
        result=new_result, decision=new_decision, attempted=True,
        replayed_to_end=best_report.replayed_to_end, language=best_report.language,
        start_fen=fen, side_to_move=side, moves_seen=move_count,
        moves_replayed=len(best_report.moves), corrected=tuple(sorted(applied.items())),
        unresolved=unresolved, repeated=repeated, variations=len(variations),
        variations_ok=variations_ok, reasons_pt=tuple(reasons), cipher=cipher_info,
        proven_pieces=proven)


#: Ceiling on the assignment hypotheses replayed for one block: the three
#: most frequent free symbols over five pieces give 60 permutations; a block
#: with more symbols keeps the rest as slots and the table fills them later.
_MAX_FREE_SYMBOLS = 3


def _replay_block(text: str, locale: str | None, fen: str) -> tuple[str, list[str], Any, str]:
    """``(main line, variations, best repair report, best reading)`` of one block."""
    from caissa.notation.legality_repair import repair_movetext

    main_text = _COMMENT.sub(" ", text)
    variations = re.findall(r"\(([^()]*)\)", main_text)
    main_line = re.sub(r"\([^()]*\)", " ", main_text)
    best_report = None
    best_text = main_line
    for candidate in [main_line, *_separator_candidates(main_line)]:
        candidate_report = repair_movetext(candidate, language=locale, start_fen=fen)
        if best_report is None or _replay_key(candidate_report) > _replay_key(best_report):
            best_report, best_text = candidate_report, candidate
    assert best_report is not None
    return main_line, variations, best_report, best_text


def _replay_key(report: Any) -> tuple[int, bool, int]:
    return (len(report.moves), bool(report.replayed_to_end), -len(report.unresolved))


def _best_assignment(text: str, report: Any, fixed: Mapping[str, str], free: Sequence[str],
                     locale: str | None, fen: str) -> dict[str, str] | None:
    """The one symbol assignment under which the block replays best, or ``None``.

    ``None`` when no hypothesis beats decoding nothing, or when two of them
    tie for the best replay — a tie means the page does not say which piece
    the symbol is, and guessing would be inventing.
    """
    from itertools import permutations

    support = {s.symbol: s.support for s in report.symbols}
    free = sorted(free, key=lambda sym: -support.get(sym, 0))[:_MAX_FREE_SYMBOLS]
    remaining = [p for p in ENGLISH_PIECES if p not in fixed.values()]
    if not free or len(remaining) < len(free):
        return None
    baseline = _replay_key(_replay_block(
        decode(text, report, assignment=dict(fixed), force=True), locale, fen)[2])
    scored: list[tuple[tuple[int, bool, int], dict[str, str]]] = []
    for combination in permutations(remaining, len(free)):
        assignment = dict(fixed)
        assignment.update(dict(zip(free, combination, strict=True)))
        decoded = decode(text, report, assignment=assignment, force=True)
        scored.append((_replay_key(_replay_block(decoded, locale, fen)[2]), assignment))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_key, best = scored[0]
    if best_key <= baseline:
        return None
    if len(scored) > 1 and scored[1][0] == best_key:
        return None
    return best


_FIRST_MOVE_ANYWHERE = re.compile(r"(?:^|\s)(1\.(?!\.)\s*[a-hKQRBN♔♕♖♗♘♙O0])")


def _game_start(text: str) -> int | None:
    """Offset of a ``1.`` that opens a game after prose, or ``None``.

    Only when nothing move-shaped precedes it: a ``1.`` inside a block that
    already carried moves is a variation, not a game start.
    """
    match = _FIRST_MOVE_ANYWHERE.search(text)
    if match is None:
        return None
    head = text[:match.start(1)]
    if any(is_move_token(t) for t in tokenize(head)):
        return None
    return match.start(1)


def _decoded_tokens(before: str, after: str, symbols: set[str]) -> dict[str, str]:
    """``original token → decoded token`` for the tokens the cipher turned into a move.

    A token qualifies when its piece slot held one of the resolved ``symbols``
    and the decoded form is a move; ``is_move_token`` is *not* asked about the
    original, because it answers for every locale at once — ``Wd5`` is a
    Polish rook move — and what settled ``W`` here is this book's own legality
    evidence, not a table of alphabets.  A token still holding a ``?`` slot is
    not a reading anyone should be handed and stays out.
    """
    def core(token: str) -> str:
        return _MOVE_NUMBER_PREFIX.sub("", token.strip("(),;:."))

    out: dict[str, str] = {}
    for old, new in zip(before.split(), after.split(), strict=False):
        if old == new or not is_move_token(core(new)):
            continue
        parts = _split(old)
        if parts is not None and (parts[0] in symbols or parts[2] in symbols):
            out[old] = new
    return out


def _proven_pieces(moves: Sequence[Any], before: str, after: str, *,
                   language: str | None) -> tuple[tuple[str, str, str, str], ...]:
    """The cipher symbols a complete legal replay settled.

    A move whose original token carried a one-character prefix that is **not
    a piece letter of the block's own notation language** (the symbol) and
    whose legal SAN names a piece proves ``symbol → piece``.  The language
    guard is what keeps a Portuguese ``Txb7`` from being recorded as a cipher
    ``T`` → ``R``: the book prints letters, and letters are not a cipher.  The
    decoded text is mapped back to the original token by position, so a
    symbol the table already rewrote still counts — the replay confirmed it.
    """
    letters = _piece_letters(language or "") | frozenset(ENGLISH_PIECES)
    original_of: dict[str, str] = {}
    for old, new in zip(before.split(), after.split(), strict=False):
        original_of.setdefault(new, old)
    out: list[tuple[str, str, str, str]] = []
    for move in moves:
        raw = str(getattr(move, "raw", "") or "")
        san = str(getattr(move, "san", "") or "")
        if not raw or not san or san[0] not in ENGLISH_PIECES:
            continue
        original = original_of.get(raw, raw)
        parts = _split(original)
        if parts is None:
            continue
        prefix = parts[0]
        if len(prefix) == 1 and prefix not in letters and not prefix.isdigit():
            out.append((prefix, san[0], original, san))
    return tuple(out)


def _render(san: str, language: str | None) -> str:
    """SAN back in the page's own piece letters, so a corrected token keeps
    the book's convention."""
    if not language or language == "en":
        return san
    from caissa.notation.languages import to_language

    try:
        return to_language(san, language)
    except (KeyError, ValueError):
        return san
