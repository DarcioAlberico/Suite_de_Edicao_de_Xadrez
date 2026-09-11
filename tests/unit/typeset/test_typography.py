"""Character-level typography: quotes, dashes, chess symbols, hyphenation, columns.

Every case in the "defects that fail on their own" list under §3.3 of
`docs/quality/CRITIC_CHARTER.md` that belongs to text has a test here, and the
regressions found while setting the proof sheet have one each.
"""

from __future__ import annotations

import pytest

from caissa.typeset import typography as typo
from caissa.typeset.typography import (
    EM_DASH,
    EN_DASH,
    NBSP,
    ColumnPolicy,
    Hyphenator,
    Line,
    ParagraphBlock,
    break_lines,
    check_marks,
    chess_symbols,
    fill_columns,
    get_style,
    hyphenate_word,
    looks_like_chess,
    protect_chess_notation,
    small_caps_runs,
    smart_dashes,
    smart_quotes,
    typeset_text,
)


def render(text: str, language: str = "en", **kwargs) -> str:
    return typeset_text(text, language, **kwargs)


# --------------------------------------------------------------------------- #
# Quotes
# --------------------------------------------------------------------------- #
def test_no_straight_quote_survives():
    """The charter fails 'aspas retas onde deveriam ser tipograficas'."""
    out = render('He said "the knight is bad" and left.')
    assert '"' not in out
    assert "'" not in render("Karpov's plan")


def test_british_english_uses_single_outer_quotes():
    """`en` is British -- which is also Quality Chess's house style, the reference this
    front is judged against. `en_us` is the one with double outer quotes."""
    assert render('a "quote" here', "en").count("‘") == 1
    assert render('a "quote" here', "en_us").count("“") == 1


def test_apostrophe_inside_a_word_is_never_an_opening_quote():
    out = render("White's knight and Black's bishop")
    assert out.count("’") == 2
    assert "‘" not in out


def test_nested_quotes_use_the_inner_pair():
    style = get_style("en")
    out = smart_quotes("\"outer 'inner' outer\"", "en")
    assert out.startswith(style.quotes.open_outer)
    assert style.quotes.open_inner in out


def test_german_uses_low_nine_and_high_six():
    """Getting this wrong is the classic tell of a book set by someone who does not read
    the language."""
    out = render('er sagte "so" und ging', "de")
    assert "„" in out and "“" in out


def test_french_puts_a_narrow_space_inside_its_guillemets():
    out = render('il a dit "oui" ensuite', "fr")
    assert "«" in out and "»" in out
    assert " " in out


def test_leading_apostrophe_on_a_year_is_an_apostrophe():
    assert render("the '90s") .count("’") == 1


# --------------------------------------------------------------------------- #
# Dashes
# --------------------------------------------------------------------------- #
def test_a_result_takes_an_en_dash_and_is_set_tight():
    for source, expect in (("1-0", "1–0"), ("0-1", "0–1"), ("1/2-1/2", "1/2–1/2")):
        assert render(source) == expect


def test_castling_is_left_alone_by_default():
    """`0-0` is castling, and the result and range rules both match it on sight. Letting
    either through gives the reader `0`-en dash-`0`, which reads as a drawn game."""
    # The move-number binding inserts a narrow no-break space, so compare on the
    # dashes rather than on the whole string.
    assert "0-0" in render("6.Bg2 0-0 7.Ngf3")
    assert "0–0" not in render("6.Bg2 0-0 7.Ngf3")
    assert "0-0-0" in render("8.0-0-0 Qa5")


def test_castling_dash_is_an_explicit_house_style():
    """Quality Chess sets `0`-en dash-`0`, verified on the reference page. It has to be
    asked for, never inferred."""
    out = render("6.Bg2 0-0 7.Ngf3", castling_dash=EN_DASH)
    assert "0–0" in out
    assert render("8.0-0-0", castling_dash=EN_DASH).count("–") == 2


def test_numeric_ranges_take_an_en_dash():
    assert "12–15" in render("pages 12-15")


def test_a_square_to_square_move_keeps_its_hyphen():
    """`c5-d5` and `...e6-e5` are notation, not ranges. An en dash there is wrong."""
    assert "c5-d5" in render("the ideal c5-d5 position")
    assert "e6-e5" in render("followed by ...e6-e5")


def test_double_and_triple_hyphens_are_the_tex_convention():
    assert EN_DASH in smart_dashes("a--b")
    assert EM_DASH in smart_dashes("a---b")


def test_a_spaced_dash_never_starts_a_line():
    """A parenthetical dash belongs to the phrase it follows. Ours put it at the head of
    the next line in the first setting of the blind-comparison page."""
    out = render("compare the game Vitiugov - Bologan from the previous chapter")
    assert f"Vitiugov{NBSP}– Bologan" in out


# --------------------------------------------------------------------------- #
# Evaluation symbols
# --------------------------------------------------------------------------- #
def test_evaluation_symbols_are_set_as_characters_when_the_face_has_them():
    always = lambda ch: True  # noqa: E731
    assert render("16.e3+/- and", can_render=always).startswith("16.e3±")
    assert "∓" in render("15.Nf3 -/+ x", can_render=always)
    assert "⩲" in render("15.Nf3 +/= x", can_render=always)
    assert "⩱" in render("15.Nf3 =/+ x", can_render=always)


def test_plus_minus_pair_keeps_the_plus_and_takes_a_MINUS_SIGN():
    """U+2212, not an en dash. Cycle 2 set `+–` and the critic caught it: on one page
    one evaluation came out as a correct single glyph (`16.e3±`) and the other as a
    forged pair. Times New Roman carries U+2212 -- checked in its cmap -- so this was
    never a coverage limit, it was the wrong character."""
    always = lambda ch: True  # noqa: E731
    assert "+−" in render("26.h5+- followed", can_render=always)
    assert "−+" in render("and -+ wins", can_render=always)
    # And when the face is not asked, or has no U+2212, the ASCII the author typed
    # survives rather than becoming a notdef box.
    assert "+-" in render("26.h5+- followed")


def test_a_symbol_the_face_cannot_draw_is_not_substituted():
    """The worst outcome is a notdef box where the author typed something readable.
    Times New Roman has U+00B1 and none of U+2213, U+2A71, U+2A72 -- checked, not
    assumed, in `tools/typeset_page.py`."""
    only_latin1 = lambda ch: ord(ch) < 0x100  # noqa: E731
    out = chess_symbols("a +/= b -/+ c +/- d", can_render=only_latin1)
    assert "+/=" in out and "-/+" in out
    assert "±" in out, "o simbolo que a fonte TEM deve ser trocado"


def test_chess_symbols_with_no_predicate_assumes_nothing():
    out = chess_symbols("a +/= b +/- c")
    assert "+/=" in out
    assert "±" in out


def test_arithmetic_is_not_mistaken_for_an_evaluation():
    assert render("x+-3 math") == "x+-3 math"


# --------------------------------------------------------------------------- #
# Check marks
# --------------------------------------------------------------------------- #
def test_check_marks_default_to_the_pgn_standard():
    assert render("24.Bxh7+ Kxh7 25.Rh8#").count("+") == 1
    assert "#" in render("25.Rh8#")


def test_dagger_check_marks_are_a_house_style():
    always = lambda ch: True  # noqa: E731
    out = render("24.Bxh7+ Kxh7 25.Rh8#", check_style="dagger", can_render=always)
    assert "†" in out and "‡" in out
    assert "+" not in out and "#" not in out


def test_dagger_style_leaves_an_evaluation_plus_alone():
    """`h5+-` is an evaluation, not a check. Turning its plus into a dagger gives
    `h5`-dagger-minus, which was the first thing this style got wrong."""
    always = lambda ch: True  # noqa: E731
    out = render("26.h5+- x", check_style="dagger", can_render=always)
    assert "+−" in out
    assert "†" not in out


def test_dagger_style_does_not_touch_ordinary_prose():
    always = lambda ch: True  # noqa: E731
    assert "C++" in render("the C++ language", check_style="dagger", can_render=always)


def test_check_marks_are_skipped_when_the_face_lacks_the_glyph():
    never = lambda ch: ord(ch) < 0x100  # noqa: E731
    out = check_marks("24.Bxh7+", "dagger", can_render=never)
    assert out == "24.Bxh7+"


# --------------------------------------------------------------------------- #
# Chess protection
# --------------------------------------------------------------------------- #
def test_move_number_is_bound_to_its_move():
    """The charter's line-break rule: `12.` and `Nf3` are one thing."""
    out = protect_chess_notation("12. Nf3 and 13. Bg5")
    assert "12. Nf3" in out or "12. Nf3" in out


def test_black_move_ellipsis_becomes_one_character():
    assert "13…" in render("13...bxc5")
    assert "..." not in render("13...bxc5")


def test_a_nag_never_starts_a_line():
    out = protect_chess_notation("Nf3 !?")
    assert "Nf3!?" in out


def test_looks_like_chess_protects_notation_from_hyphenation():
    for token in ("Nf3", "Rxd4", "O-O", "e4", "Qh5+", "Bxh7"):
        assert looks_like_chess(token), token
    for token in ("knight", "position", "hanging"):
        assert not looks_like_chess(token), token


# --------------------------------------------------------------------------- #
# Hyphenation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("language", ["en", "pt", "de", "es", "fr", "it", "ru", "en_us"])
def test_every_declared_language_has_working_patterns(language):
    """The charter fails 'hifenizacao ausente ou errada para o idioma'. A language in
    the table with no pattern file is exactly that defect."""
    style = get_style(language)
    assert style.hyphen_patterns, f"{language} nao declara arquivo de padroes"
    hyphenator = Hyphenator(language)
    assert hyphenator._patterns, f"{language}: nenhum padrao carregado"


def test_english_hyphenation_matches_tex():
    """Liang's algorithm with the canonical patterns; these are the splits TeX makes."""
    hyphenator = Hyphenator("en")
    assert hyphenator.split("subsequently") == ["sub", "sequently"]
    assert hyphenator.split("difficult") == ["dif", "fi", "cult"]
    assert hyphenator.split("position") == ["pos", "i", "tion"]


def test_portuguese_hyphenation_works():
    """`cavalo` is deliberately not the example: with the standard 3/3 edge minimums
    `ca-va-lo` has no legal break, and a test that demanded one would be testing the
    minimums rather than the patterns."""
    hyphenator = Hyphenator("pt")
    assert hyphenator.split("estrutura") == ["estru", "tura"]
    assert len(hyphenator.split("posicao")) > 1
    assert hyphenator.split("cavalo") == ["cavalo"]


def test_chess_notation_is_never_hyphenated():
    """`Nf3` must never become `Nf-3`."""
    hyphenator = Hyphenator("en")
    for token in ("Nf3", "Rxd4", "O-O-O", "Qh5+", "bxc5"):
        assert hyphenate_word(token, hyphenator) == [token]


def test_short_words_are_left_whole():
    hyphenator = Hyphenator("en")
    assert hyphenator.split("cat") == ["cat"]
    assert hyphenator.split("the") == ["the"]


def test_hyphen_points_respect_the_edge_minimums():
    hyphenator = Hyphenator("en", left=3, right=3)
    for word in ("subsequently", "initiative", "hanging", "structure"):
        for point in hyphenator.positions(word):
            assert point >= 3
            assert len(word) - point >= 3


def test_soft_hyphenate_inserts_only_soft_hyphens():
    hyphenator = Hyphenator("en")
    out = hyphenator.soft_hyphenate("subsequently")
    assert out.replace("­", "") == "subsequently"
    assert "­" in out


# --------------------------------------------------------------------------- #
# Line breaking and columns
# --------------------------------------------------------------------------- #
def _measure(text: str) -> float:
    return float(len(text))


def test_break_lines_respects_the_measure():
    text = "the hanging pawns may be blocked and subsequently attacked in this game"
    lines = break_lines(text, width=30, measure=_measure)
    assert lines
    for line in lines:
        assert _measure(line.text) <= 30


def test_break_lines_never_stacks_more_than_two_hyphens():
    """Three hyphens down a column edge is banned by every house style, and a narrow
    chess column reaches three easily."""
    text = " ".join(["subsequently", "initiative", "difficult", "positional"] * 6)
    lines = break_lines(
        text, width=14, measure=_measure, hyphenator=Hyphenator("en"),
        max_consecutive_hyphens=2,
    )
    run = 0
    for line in lines:
        run = run + 1 if line.hyphenated else 0
        assert run <= 2, "tres hifens consecutivos no fim de linha"


def test_a_bound_move_is_never_split_across_lines():
    """`protect_chess_notation` is only worth applying if the breaker honours it."""
    text = protect_chess_notation("White played 13. dxc5 and then 14. Nb3 quickly")
    lines = break_lines(text, width=18, measure=_measure)
    for line in lines:
        assert not line.text.endswith("13.")
        assert not line.text.endswith("14.")


def test_fill_columns_leaves_no_orphan():
    """An orphan is the first line of a paragraph stranded at the foot of a column."""
    blocks = [ParagraphBlock(lines=[Line(f"p{i} l{j}", 10) for j in range(5)])
              for i in range(4)]
    columns = fill_columns(blocks, lines_per_column=7, policy=ColumnPolicy(2, 2))
    for column in columns:
        if not column:
            continue
        first_index = column[0][0]
        count = sum(1 for index, _ in column if index == first_index)
        # A paragraph that *starts* in this column must leave at least two lines here.
        starts_here = column[0][1].text.endswith("l0")
        if starts_here:
            assert count >= 2


def test_fill_columns_leaves_no_widow():
    blocks = [ParagraphBlock(lines=[Line(f"p{i} l{j}", 10) for j in range(5)])
              for i in range(4)]
    columns = fill_columns(blocks, lines_per_column=7, policy=ColumnPolicy(2, 2))
    for column in columns[1:]:
        if not column:
            continue
        first_index = column[0][0]
        carried = sum(1 for index, _ in column if index == first_index)
        assert carried != 1, "uma linha orfa no topo da coluna seguinte"


def test_fill_columns_preserves_every_line():
    blocks = [ParagraphBlock(lines=[Line(f"p{i} l{j}", 10) for j in range(5)])
              for i in range(4)]
    columns = fill_columns(blocks, lines_per_column=6)
    total = sum(len(c) for c in columns)
    assert total == 20, "o preenchimento de colunas perdeu ou duplicou linhas"


def test_fill_columns_handles_the_empty_case():
    assert fill_columns([], lines_per_column=10) == [[]]


# --------------------------------------------------------------------------- #
# Small caps
# --------------------------------------------------------------------------- #
def test_small_caps_runs_split_on_case():
    """The lower-case letters are raised to capitals and flagged; the capitals the
    author typed stay full size. That is what makes `Karpov` read as K-ARPOV rather
    than as a shout."""
    runs = small_caps_runs("Karpov")
    assert runs == [("K", False), ("ARPOV", True)]
    assert "".join(text for text, _ in runs) == "KARPOV"
    assert small_caps_runs("") == []


# --------------------------------------------------------------------------- #
# Language table
# --------------------------------------------------------------------------- #
def test_unknown_language_says_what_is_available():
    with pytest.raises(KeyError) as excinfo:
        get_style("klingon")
    assert "en" in str(excinfo.value)


def test_regional_variants_fall_back_to_the_base_language():
    assert get_style("pt_PT").code in {"pt", "pt_pt"}
    assert get_style("de-AT").code == "de"


def test_typeset_text_is_idempotent():
    """Running the pass twice must not change the result -- an export pipeline will."""
    for source in (
        'He said "the knight" -- 1-0',
        "13...bxc5?! and 14.Nb3",
        "pages 12-15, see Vitiugov - Bologan",
    ):
        once = render(source)
        assert render(once) == once, f"nao idempotente: {source!r}"
