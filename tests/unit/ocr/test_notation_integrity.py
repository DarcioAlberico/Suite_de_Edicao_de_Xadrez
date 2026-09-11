"""The notation-integrity signal — SPEC §7.1, docs/quality/F5_REPORT_C2.md.

This gate exists because twelve instruments of measurement were found blind
during this project, and this is the thirteenth: on a chess book whose figurine
font did not survive extraction, *every* lexical signal reports a healthy page.
The prose is the bulk of the tokens and the prose is perfect; the move text —
the reason the book exists — is gone.

So the tests here are built the way the charter demands.  The truth is
generated, not sampled, so the expected counts are exact; and the central test
is a **sabotage**: it damages a page that the old signals pass, and asserts
that the old signals still pass it while the new one catches it.  A gate that
only ever returns zero is indistinguishable from a gate that is blind.
"""

from __future__ import annotations

import pytest

from caissa.ocr.lexicon import (
    NOTATION_ALPHABET,
    dictionary_hit_rate,
    implausible_char_ratio,
    is_chess_notation,
    is_mangled_move,
    is_move_token,
    mangled_move_ratio,
    nonword_ratio,
    normalise_lang,
    tokenize,
)

ENG = normalise_lang("eng")


# --------------------------------------------------------------------------- #
# The damage, reproduced
# --------------------------------------------------------------------------- #

#: How the figurines of the corpus actually came back, glyph by glyph.  Taken
#: from the books themselves, not invented: Batsford's queen in Gaprindashvili
#: reads ``'i'``, the Fd-subset knight in Aagaard reads ``ll'l``, the Cyrillic
#: rook in Boleslavsky reads ``Jl``.
FIGURINE_DAMAGE = {
    "N": "ll'l",
    "B": "i.",
    "R": "l:t",
    "Q": "'i'",
    "K": "@",
}

CLEAN_MOVETEXT = (
    "1 e4 e5 2 Nf3 Nc6 3 Bb5 a6 4 Ba4 Nf6 5 O-O Be7 6 Re1 b5 7 Bb3 d6 "
    "8 c3 O-O 9 h3 Nb8 10 d4 Nbd7 11 Nbd2 Bb7 12 Bc2 Re8 13 Nf1 Bf8 "
    "14 Ng3 g6 15 a4 c5 16 d5 c4 17 Bg5 h6 18 Be3 Nc5 19 Qd2 h5 20 Qxc4 "
)

CLEAN_PROSE = (
    "The rook belongs behind the passed pawn, and the reason is not hard to "
    "see. When the rook stands in front of the pawn it must move away before "
    "the pawn can advance, so the attacking side loses time with every step "
    "while the defender simply waits and keeps his own rook where it stands. "
)


def damage_figurines(text: str) -> str:
    """Break only the piece glyphs, exactly as a lost ToUnicode does."""
    for piece, garbage in FIGURINE_DAMAGE.items():
        text = text.replace(piece, garbage)
    return text


# --------------------------------------------------------------------------- #
# Token-level truth
# --------------------------------------------------------------------------- #

#: Correct notation in every supported language, plus the forms that have
#: tripped naive detectors before.  Not one of these may be called damaged.
CLEAN_TOKENS = [
    "Nf3", "Cf3", "Sf3", "Ff3", "Tf3", "Pf3", "Df3", "Rf3",   # eight languages
    "Кd2", "Лf3",                                    # Cyrillic Кd2, Лf3
    "♘f3", "♕d1", "♖h8",                        # Unicode figurines
    "exd5", "cxd3", "e8=Q", "a1", "h8", "Lf2-d4", "Sb1-c3",
    "O-O", "O-O-O", "0-0", "1-0", "1/2-1/2", "33.", "Kd3",
    "Rd1!?", "Nf3+", "Qh5#", "Bxf7!!",
]

#: Real tokens, copied out of the corpus with their book of origin.
DAMAGED_TOKENS = {
    "'i'd6+": "Gaprindashvili p202 — dama Batsford",
    "l:th7": "Gaprindashvili p202 — torre Batsford",
    "J:!.'.8c7": "Gaprindashvili p202 — torre, com ruído",
    "!txg7": "Gaprindashvili p202 — torre, marca de anotação à frente",
    "ti'h5": "Aagaard p148 — dama do subconjunto Fd",
    "ll'lxe5": "Aagaard p222 — cavalo do subconjunto Fd",
    "lhc3": "Aagaard p260 — cavalo",
    "i'e6": "Nunn p200 — dama",
    "lDe7": "Nunn p120 — cavalo",
    "JIfd8": "Boleslávski p168 — torre cirílica Л",
    "á7-d7": "Capablanca p410 — a coluna 'a' voltou como 'á'",
    "@xf5": "Gaprindashvili p202 — rei",
    "'iit>e7": "Gaprindashvili p245 — rei",
}


@pytest.mark.parametrize("token", CLEAN_TOKENS)
def test_clean_notation_is_never_called_damaged(token):
    """One-sided by construction: correct notation must score zero."""
    assert not is_mangled_move(token, ENG), (
        f"{token!r} é notação correta e foi acusada de dano")


@pytest.mark.parametrize("token,origin", sorted(DAMAGED_TOKENS.items()))
def test_real_damaged_tokens_are_caught(token, origin):
    assert is_mangled_move(token, ENG), f"{token!r} ({origin}) passou"


@pytest.mark.parametrize("word", [
    "f2-pawn", "e4-square", "d5-outpost",     # English compounds with a square
    "rook", "bishop", "zugzwang", "the",
    "Nimzo-Indian", "well-known",
])
def test_ordinary_words_are_not_moves(word):
    """A hyphenated compound whose other half is a word is a word.

    ``f2-pawn`` was a live false positive in the first draft, measured on
    Dvoretsky p500 — the only two the clean control produced.
    """
    assert not is_mangled_move(word, ENG), word


def test_annotation_glyphs_only_trail():
    """``Kd3ʘ`` is annotated, ``!txg7`` is broken, and the difference is
    position.  Dvoretsky's zugzwang mark is the reason this rule exists."""
    assert not is_mangled_move("Kd3ʘ", ENG)
    assert not is_mangled_move("Rd1⩲", ENG)
    assert is_mangled_move("!txg7", ENG)


@pytest.mark.parametrize("token", ["33.", "1.", "1-0", "0-1", "1/2-1/2", "½-½",
                                  "±", "=", "7"])
def test_the_denominator_counts_moves_and_not_bookkeeping(token):
    """A page of bare move numbers and results must not look like healthy
    notation.  ``1-0`` is the trap: it is valid notation and it has a hyphen,
    so a "notation with a hyphen is a move" rule counts every game result as a
    healthy move and dilutes the damage away."""
    assert not is_move_token(token), token


@pytest.mark.parametrize("token", ["Nf3", "O-O", "O-O-O", "0-0", "exd5",
                                   "Lf2-d4", "e8=Q", "Кd2", "♘f3"])
def test_real_moves_are_counted(token):
    assert is_move_token(token), token


def test_the_alphabet_is_derived_and_not_copied():
    """Guard against the twelfth blind gate: two tables that agree by
    coincidence rather than by construction.

    Every piece letter the notation regex is built from must be a character
    the integrity test also accepts, or a correct move in some language would
    be reported as damage the moment it appears with a stray mark.  Reaching
    into the private constant is deliberate: the point of the test is that
    both derive from *one* table, and only the private name can prove it.
    """
    from caissa.ocr.lexicon import _PIECE_LETTERS

    assert set(_PIECE_LETTERS) <= NOTATION_ALPHABET
    for letter in _PIECE_LETTERS:
        assert is_chess_notation(f"{letter}f3"), letter
        assert not is_mangled_move(f"{letter}f3", ENG), letter


# --------------------------------------------------------------------------- #
# Ratios, on text whose counts are known exactly
# --------------------------------------------------------------------------- #

def test_clean_movetext_scores_zero():
    ratio, judged = mangled_move_ratio(CLEAN_MOVETEXT, ENG)
    assert judged >= 30, judged
    assert ratio == 0.0


def test_damaged_movetext_scores_above_the_verdict_bar():
    """Exact, and deliberately *not* the number a first guess would give.

    The line has 39 moves, 22 of which carry a piece glyph, so a reader
    expects 22/39 = 0.564.  The detector reports 11/39 = 0.282, and the gap is
    a real limitation worth naming rather than smoothing over: when the damage
    inserts a character the tokenizer splits on, the move comes apart before
    it can be judged.  ``Bb5`` damaged to ``i.b5`` becomes the tokens ``i``,
    ``.`` and ``b5`` — and ``b5`` is a perfectly good move.  ``Re1`` damaged to
    ``l:te1`` splits into ``l``, ``:`` and ``te1``, and ``te1`` is valid
    notation too, because ``t`` is the Dutch/Romanian rook.

    So the measure **under**-reports damage, which is the safe direction for a
    signal that lowers confidence: it never invents damage that is not there.
    Both halves are asserted, so a change to the tokenizer that alters either
    one shows up here instead of drifting silently.
    """
    moves = [t for t in tokenize(CLEAN_MOVETEXT) if is_move_token(t)]
    piece_moves = [t for t in moves if t[0] in FIGURINE_DAMAGE]
    assert (len(moves), len(piece_moves)) == (39, 22)

    ratio, judged = mangled_move_ratio(damage_figurines(CLEAN_MOVETEXT), ENG)
    assert judged == 39, judged
    assert ratio == pytest.approx(11 / 39), ratio
    assert ratio > 0.15, "abaixo do limite do veredito; o caso perdeu a graça"


def test_damage_that_splits_a_token_is_a_known_miss():
    """The limitation above, isolated so it cannot be forgotten.

    A single move, damaged with a separator, is invisible on its own.  This is
    why the ratio is a page-level signal with a floor of twelve moves and not
    a per-move verdict.
    """
    assert is_mangled_move("ll'lf3", ENG)        # no separator: caught
    # The damage is only invisible because the tokenizer never hands the
    # detector the whole thing: it arrives as three tokens, one of which is a
    # perfectly good move.
    assert tokenize("i.b5") == ["i", ".", "b5"]
    assert [t for t in tokenize("i.b5") if is_move_token(t)] == ["b5"]
    assert not any(is_mangled_move(t, ENG) for t in tokenize("i.b5"))


def test_a_page_that_quotes_two_moves_is_not_judged():
    """The guard the caller must honour: a ratio over a handful of moves says
    nothing, and prose must not be condemned by the moves it happens to cite."""
    _, judged = mangled_move_ratio(CLEAN_PROSE + " after 1 e4 e5 the game...",
                                   ENG)
    assert judged < 12


def test_prose_dilutes_the_ratio_but_does_not_erase_it():
    """The defect's own shape: the more prose, the safer the page looks to a
    signal that averages over tokens.  This one does not average over prose."""
    damaged = damage_figurines(CLEAN_MOVETEXT)
    alone, _ = mangled_move_ratio(damaged, ENG)
    buried, _ = mangled_move_ratio(CLEAN_PROSE * 6 + damaged, ENG)
    assert alone == pytest.approx(buried), (
        "a prosa mudou o índice de notação; o denominador não está restrito "
        "a lances")


# --------------------------------------------------------------------------- #
# Vitality: sabotage the page, and watch the old gates wave it through
# --------------------------------------------------------------------------- #

def test_the_old_signals_are_blind_to_this_damage():
    """**The proof that this gate is not redundant.**

    Take a page of correct prose and correct move text, damage *only* the
    piece glyphs, and measure the three signals that were supposed to notice.
    Not one of them comes close to its own bar:

    ==================  =======  ==========  =========  ==========
    signal              clean    damaged     moves by   its bar
    ==================  =======  ==========  =========  ==========
    nonword_ratio       0.000    0.077       +0.077     0.45 max
    dictionary_hit      1.000    0.952       -0.048     0.12 min
    implausible_char    0.000    0.000       **0.000**  0.15 max
    mangled_move        0.000    **0.282**   +0.282     0.15 max
    ==================  =======  ==========  =========  ==========

    ``implausible_char_ratio`` moves by *exactly nothing* — the damaged
    figurines are ordinary Latin letters, which is the entire problem.  This
    is how Aagaard p222 came to be accepted at 0.98 with its notation
    destroyed.

    If this ever fails because an old signal now catches the damage, the new
    gate may be redundant — check before deleting it.
    """
    page = CLEAN_PROSE * 4 + CLEAN_MOVETEXT
    damaged = CLEAN_PROSE * 4 + damage_figurines(CLEAN_MOVETEXT)

    before_nonword, _ = nonword_ratio(page, ENG)
    after_nonword, _ = nonword_ratio(damaged, ENG)
    before_dict, _ = dictionary_hit_rate(page, ENG)
    after_dict, _ = dictionary_hit_rate(damaged, ENG)
    before_implausible, _ = implausible_char_ratio(page)
    after_implausible, _ = implausible_char_ratio(damaged)

    # Not merely under the bars in TextLayerThresholds — nowhere near them.
    # Asserted tight on purpose: a loose bound would pass against a signal
    # that had started to notice, and the claim being made here is that they
    # do not notice at all.
    assert after_nonword < 0.10, after_nonword           # bar is 0.45
    assert after_dict > 0.90, after_dict                 # bar is 0.12
    assert after_implausible == 0.0, after_implausible   # bar is 0.15

    # The damage is invisible to them, not merely tolerated by them.
    assert before_dict - after_dict < 0.06
    assert after_nonword - before_nonword < 0.10
    assert after_implausible == before_implausible == 0.0, (
        "os figurinos danificados voltaram como letras latinas comuns; se "
        "este sinal se moveu, a natureza do dano mudou")

    # The new signal, on the same two strings.
    clean_ratio, _ = mangled_move_ratio(page, ENG)
    damaged_ratio, judged = mangled_move_ratio(damaged, ENG)
    assert clean_ratio == 0.0
    assert judged >= 12
    assert damaged_ratio > 0.15, (
        f"a sabotagem não foi vista: {damaged_ratio:.3f}")


def test_the_gate_fails_when_the_damage_is_removed():
    """The other half of a vitality proof: undo the sabotage and the gate must
    go quiet.  A detector that fires on everything is as useless as one that
    fires on nothing."""
    for repeats in (1, 2, 4, 8):
        ratio, judged = mangled_move_ratio(CLEAN_PROSE * repeats
                                           + CLEAN_MOVETEXT, ENG)
        assert judged >= 12
        assert ratio == 0.0, (repeats, ratio)


def test_every_damaged_token_is_a_move_that_kept_its_square():
    """Why the test is one-sided: the file and the rank are ordinary Latin
    that no figurine font touches, so the square survives and the piece does
    not.  Anything the detector accuses must still look like a move."""
    damaged = damage_figurines(CLEAN_MOVETEXT)
    accused = [t for t in tokenize(damaged) if is_mangled_move(t, ENG)]
    assert accused
    for token in accused:
        assert any(f"{f}{r}" in token
                   for f in "abcdefgh" for r in "12345678"), token
