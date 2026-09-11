"""The tokenizer is the crux of F10, so it is tested against SQLite itself.

A test that only checked ``tokens()`` would pass while the index stayed
unsearchable: the failure mode this front exists to avoid is FTS5 shredding a
token *after* Python produced it.  So the round-trip tests below actually create
an FTS5 table with the real ``tokenize=`` directive and search it.
"""

from __future__ import annotations

import sqlite3

import pytest

from caissa.index.tokenizer import (
    FTS5_TOKENIZE,
    ChessTokenizer,
    decode_token,
    encode_case,
    is_notation,
)

TOKENIZER = ChessTokenizer()


@pytest.fixture
def fts():
    """A real FTS5 table with the index's own tokenizer directive."""
    connection = sqlite3.connect(":memory:")
    connection.execute(f'CREATE VIRTUAL TABLE t USING fts5(body, tokenize="{FTS5_TOKENIZE}")')
    yield connection
    connection.close()


def _search(fts, text: str, query: str) -> int:
    fts.execute("DELETE FROM t")
    fts.execute("INSERT INTO t(body) VALUES (?)", (TOKENIZER.encode(text),))
    expression = TOKENIZER.match_term(query, relax_check=False)
    if not expression:
        return 0
    return fts.execute("SELECT count(*) FROM t WHERE t MATCH ?", (expression,)).fetchone()[0]


# --------------------------------------------------------------------------- #
# The acceptance gate: notation survives tokenization
# --------------------------------------------------------------------------- #

NOTATION_FORMS = [
    "Nf3",
    "O-O",
    "O-O-O",
    "1.e4",
    "12...Nf6",
    "Qxd5+",
    "e8=Q#",
    "exd5",
    "Nbd7",
    "N3xd5",
    "Ne2xd4",
    "Rxf7+",
    "1-0",
    "0-1",
    "1/2-1/2",
]


@pytest.mark.parametrize("form", NOTATION_FORMS)
def test_notation_survives_the_round_trip(fts, form):
    """Every notation form is findable, through SQLite, exactly as written."""
    assert _search(fts, f"as brancas jogam {form} e vencem", form) == 1


@pytest.mark.parametrize("form", NOTATION_FORMS)
def test_notation_is_one_token(form):
    """A notation form contributes one token, or one plus its bare move."""
    tokens = TOKENIZER.tokens(form)
    assert 1 <= len(tokens) <= 2
    assert " " not in tokens[0]


def test_castling_zero_form_folds_to_letter_form(fts):
    """``0-0-0`` is the same move as ``O-O-O`` and answers the same query."""
    assert _search(fts, "as brancas fazem 0-0-0", "O-O-O") == 1
    assert _search(fts, "as brancas fazem O-O-O", "0-0-0") == 1


def test_figurine_answers_an_english_query(fts):
    """A figurine book and an English book give the same answer."""
    assert _search(fts, "as brancas jogam ♘f3", "Nf3") == 1
    assert _search(fts, "as brancas jogam ♞f3", "Nf3") == 1


def test_glued_move_number_is_findable_both_ways(fts):
    """``1.e4`` is a token, and ``e4`` still finds it."""
    assert _search(fts, "a partida comecou 1.e4 c5", "1.e4") == 1
    assert _search(fts, "a partida comecou 1.e4 c5", "e4") == 1


def test_glued_move_number_is_not_a_prefix_match(fts):
    """``1.e4`` must not match ``12.e4``: that is what one token buys."""
    assert _search(fts, "a posicao apos 12.e4", "1.e4") == 0


# --------------------------------------------------------------------------- #
# Case: the failure every built-in FTS5 tokenizer has
# --------------------------------------------------------------------------- #


def test_bishop_and_pawn_capture_are_different_tokens(fts):
    """``Bxc4`` is a bishop and ``bxc4`` is a pawn.  SQLite folds case; we do not."""
    assert _search(fts, "as brancas jogam Bxc4", "Bxc4") == 1
    assert _search(fts, "as brancas jogam Bxc4", "bxc4") == 0
    assert _search(fts, "as brancas jogam bxc4", "bxc4") == 1
    assert _search(fts, "as brancas jogam bxc4", "Bxc4") == 0


def test_prose_case_still_folds(fts):
    """Case marking is for notation only; prose stays case-insensitive."""
    assert _search(fts, "O Gambito da Dama", "gambito") == 1
    assert _search(fts, "o gambito da dama", "Gambito") == 1


def test_encode_case_round_trips():
    for token in ("Bxc4", "bxc4", "O-O-O", "Nf3", "e8=Q#", "1.e4", "peao"):
        assert decode_token(encode_case(token)) == token


# --------------------------------------------------------------------------- #
# Annotations and evaluation marks
# --------------------------------------------------------------------------- #


def test_annotation_does_not_hide_the_move(fts):
    """``Nf3!?`` is still the move ``Nf3``."""
    assert _search(fts, "seguiu-se Nf3!? e a posicao ficou tensa", "Nf3") == 1


def test_annotation_is_searchable(fts):
    """"Todos os lances marcados com ??" is a term, not a special API."""
    assert _search(fts, "24...Kg7?? perdeu a partida", "??") == 1
    assert _search(fts, "24...Kg7?? perdeu a partida", "!!") == 0


def test_numeric_nag_folds_to_its_glyph(fts):
    """A PGN's ``$4`` and a book's ``??`` are the same judgement."""
    assert _search(fts, "Kg7 $4 e as pretas perdem", "??") == 1


def test_evaluation_glyph_does_not_become_a_check(fts):
    """``Nf3⩲`` is ``Nf3`` with an assessment, not the move ``Nf3+``."""
    assert TOKENIZER.tokens("Nf3⩲") == ["n_f3", "+="]


def test_check_mark_is_kept_when_it_is_one(fts):
    assert TOKENIZER.tokens("Qxd5+") == ["q_xd5+"]
    assert _search(fts, "seguiu Qxd5+ Kh8", "Qxd5+") == 1


def test_relaxed_check_finds_the_annotated_move(fts):
    """A reader typing ``Qxd5`` means the move, not the printed mark."""
    fts.execute("INSERT INTO t(body) VALUES (?)", (TOKENIZER.encode("seguiu Qxd5+ Kh8"),))
    expression = TOKENIZER.match_term("Qxd5")
    assert fts.execute("SELECT count(*) FROM t WHERE t MATCH ?", (expression,)).fetchone()[0] == 1


# --------------------------------------------------------------------------- #
# Prose must not be mistaken for notation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("word", ["Bad", "Kasparov", "Nunn", "Rei", "Berlim", "exd5e"])
def test_prose_is_not_case_marked(word):
    """A permissive classifier would split every word into two index terms."""
    assert TOKENIZER.tokens(word) == [word]
    assert not is_notation(word)


def test_move_numbers_are_dropped():
    """PGN furniture is not a search term, and it is a third of the tokens."""
    assert TOKENIZER.tokens("12.") == []
    assert TOKENIZER.tokens("1...") == []


def test_hyphenated_prose_splits_but_castling_does_not():
    assert TOKENIZER.tokens("anti-Siciliana") == ["anti", "Siciliana"]
    assert TOKENIZER.tokens("O-O-O") == ["o_-o_-o_"]


def test_diacritics_fold_in_sqlite(fts):
    """Portuguese is the user's language; ``peao`` must find ``peão``."""
    assert _search(fts, "o peão passado decide", "peao") == 1


def test_cyrillic_prose_survives(fts):
    """CORPUS.md E6: Russian books are in the acervo."""
    assert _search(fts, "шахматы в СССР", "шахматы") == 1


# --------------------------------------------------------------------------- #
# Query construction
# --------------------------------------------------------------------------- #


def test_match_phrase_keeps_multi_token_input_together():
    assert TOKENIZER.match_phrase("Nf3!?") == '"n_f3 !?"'


def test_match_term_expands_the_check_mark():
    assert TOKENIZER.match_term("Qxd5") == '("q_xd5" OR "q_xd5+" OR "q_xd5#")'


def test_empty_input_produces_no_expression():
    assert TOKENIZER.tokens("") == []
    assert TOKENIZER.match_term("") == ""
    assert TOKENIZER.match_phrase("   ") == ""


def test_folding_can_be_turned_off():
    """The flag exists so a test can show what the folding buys."""
    plain = ChessTokenizer(fold_notation=False)
    assert plain.tokens("N:d5") != TOKENIZER.tokens("N:d5")
