"""SPEC 5.5 -- a move is an object, so the same IR prints in every language.

The canonical form is English SAN. Everything else is a projection:
``to_language`` renders it, ``from_language`` reads it back, and the invariant
that makes a move *not text* is::

    from_language(to_language(san, lang), lang) == san

for every SAN and every supported language, byte for byte.

The stakes are highest for Portuguese, where ``R`` means **Rei** (king) while in
English ``R`` means **Rook**. A tool that treats notation as text turns every
Portuguese king move into a rook move and every rook move into a king move --
silently, in both directions, throughout a whole book. That collision gets its
own section below, and so does the same trap in the six other languages that
reuse an English piece letter for a different piece.
"""

from __future__ import annotations

import itertools

import pytest

from caissa.core.chess.notation_tables import (
    DEFAULT_LANGUAGE,
    FIGURINE_BLACK,
    FIGURINE_WHITE,
    PIECE_TABLES,
    SUPPORTED_LANGUAGES,
    FigurineSet,
    MoveRenderStyle,
    NotationError,
    PieceType,
    figurine_for_piece,
    from_figurine,
    from_language,
    is_supported_language,
    language_table,
    piece_for_letter,
    piece_letter,
    render_san,
    to_figurine,
    to_language,
)

FILES = "abcdefgh"
RANKS = "12345678"
OFFICERS = "KQRBN"


def _san_corpus() -> tuple[str, ...]:
    """Every SAN shape the lexer accepts, enumerated rather than sampled.

    Roughly two thousand tokens: pawn pushes and captures, all five officers on
    all sixty-four squares in all five disambiguation shapes, castling, every
    promotion piece on both promotion ranks, and every suffix combination.
    """
    tokens: list[str] = []
    tokens.extend(f"{file}{rank}" for file in FILES for rank in "234567")
    tokens.extend(
        f"{left}x{right}5"
        for left, right in itertools.product(FILES, repeat=2)
        if abs(FILES.index(left) - FILES.index(right)) == 1
    )
    for piece, file, rank in itertools.product(OFFICERS, FILES, RANKS):
        tokens.extend(
            (
                f"{piece}{file}{rank}",
                f"{piece}x{file}{rank}",
                f"{piece}a{file}{rank}",
                f"{piece}1{file}{rank}",
                f"{piece}a1{file}{rank}",
                f"{piece}a1x{file}{rank}",
            )
        )
    tokens.extend(("O-O", "O-O-O"))
    for file, piece in itertools.product(FILES, "QRBN"):
        tokens.extend((f"{file}8={piece}", f"{file}1={piece}"))
        tokens.append(f"{file}x{FILES[(FILES.index(file) + 1) % 8]}8={piece}")
    for base, suffix in itertools.product(
        ("Nf3", "O-O", "O-O-O", "exd5", "e8=Q", "Qxd8", "R1a3", "Nbd7", "Kh1"),
        ("+", "#", "!", "?", "!!", "??", "!?", "?!", "+!", "#!!"),
    ):
        tokens.append(base + suffix)
    return tuple(sorted(set(tokens)))


SAN_CORPUS = _san_corpus()


# --------------------------------------------------------------------------- #
# The corpus round trip -- every token, every language
# --------------------------------------------------------------------------- #


def test_the_corpus_is_large_enough_to_mean_something():
    assert len(SAN_CORPUS) > 2000


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_the_whole_corpus_round_trips_byte_identically(language):
    """The F1 gate: no token, in no language, comes back different."""
    failures: list[tuple[str, str, str]] = []
    for san in SAN_CORPUS:
        rendered = to_language(san, language)
        try:
            back = from_language(rendered, language)
        except NotationError as exc:  # pragma: no cover - only on a real defect
            failures.append((san, rendered, f"NotationError: {exc}"))
            continue
        if back != san:
            failures.append((san, rendered, back))
    assert not failures, (
        f"{len(failures)} of {len(SAN_CORPUS)} tokens broke in {language!r}; "
        f"first five: {failures[:5]}"
    )


@pytest.mark.parametrize("figurine_set", list(FigurineSet))
def test_the_whole_corpus_round_trips_through_figurine(figurine_set):
    failures = [
        (san, to_figurine(san, figurine_set))
        for san in SAN_CORPUS
        if from_figurine(to_figurine(san, figurine_set)) != san
    ]
    assert not failures, f"{len(failures)} tokens broke; first five: {failures[:5]}"


def test_english_is_the_identity_projection():
    assert [to_language(san, "en") for san in SAN_CORPUS] == list(SAN_CORPUS)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_translation_is_injective_over_the_corpus(language):
    """Two different English moves must never render as the same token.

    This is the property the round trip depends on: if it failed, some pair of
    moves would be indistinguishable on the page and no reader -- human or
    parser -- could recover the original.
    """
    rendered = [to_language(san, language) for san in SAN_CORPUS]
    assert len(set(rendered)) == len(rendered)


# --------------------------------------------------------------------------- #
# The Portuguese R collision -- the highest-stakes case in the product
# --------------------------------------------------------------------------- #


def test_portuguese_letters_are_the_ones_a_brazilian_book_prints():
    table = language_table("pt")
    assert (table.king, table.queen, table.rook, table.bishop, table.knight) == (
        "R",  # Rei
        "D",  # Dama
        "T",  # Torre
        "B",  # Bispo
        "C",  # Cavalo
    )


def test_english_rook_becomes_portuguese_torre_not_rei():
    """``Ra1`` is a *rook* move; in Portuguese it must print ``Ta1``."""
    assert to_language("Ra1", "pt") == "Ta1"
    assert to_language("Rxe5+", "pt") == "Txe5+"
    assert to_language("R1a3", "pt") == "T1a3"
    assert to_language("Rae1", "pt") == "Tae1"


def test_english_king_becomes_portuguese_rei():
    assert to_language("Kg1", "pt") == "Rg1"
    assert to_language("Kxf7", "pt") == "Rxf7"


def test_portuguese_r_reads_back_as_king_not_rook():
    """The mirror image, and the one that silently corrupts an import."""
    assert from_language("Rg1", "pt") == "Kg1"
    assert from_language("Rxf7+", "pt") == "Kxf7+"


def test_portuguese_t_reads_back_as_rook():
    assert from_language("Ta1", "pt") == "Ra1"
    assert from_language("T1a3", "pt") == "R1a3"


def test_the_collision_is_stable_in_both_directions():
    """King and rook cross over cleanly and neither one lands on the other."""
    for english, portuguese in (("Ka1", "Ra1"), ("Ra1", "Ta1")):
        assert to_language(english, "pt") == portuguese
        assert from_language(portuguese, "pt") == english


def test_reading_portuguese_as_english_is_exactly_the_bug_this_prevents():
    """Documents the damage: the naive reading is wrong, and wrong differently."""
    naive = from_language("Ra1", "en")
    correct = from_language("Ra1", "pt")
    assert naive == "Ra1", "read as English this is a rook move"
    assert correct == "Ka1", "read as Portuguese it is a king move"
    assert naive != correct


def test_portuguese_bishop_b_survives_even_though_english_shares_the_letter():
    """``B`` means bishop in both languages -- the one letter that does not move."""
    assert to_language("Bb5", "pt") == "Bb5"
    assert from_language("Bb5", "pt") == "Bb5"


def test_the_whole_corpus_survives_the_portuguese_collision():
    king_moves = [san for san in SAN_CORPUS if san.startswith("K")]
    rook_moves = [san for san in SAN_CORPUS if san.startswith("R")]
    assert king_moves
    assert rook_moves
    for san in king_moves:
        assert to_language(san, "pt").startswith("R")
        assert from_language(to_language(san, "pt"), "pt") == san
    for san in rook_moves:
        assert to_language(san, "pt").startswith("T")
        assert from_language(to_language(san, "pt"), "pt") == san


# --------------------------------------------------------------------------- #
# The same trap in the other languages
# --------------------------------------------------------------------------- #

#: ``(language, letter, the piece it means there, the piece it means in English)``
FALSE_FRIENDS = (
    ("pt", "R", PieceType.KING, PieceType.ROOK),
    ("es", "R", PieceType.KING, PieceType.ROOK),
    ("fr", "R", PieceType.KING, PieceType.ROOK),
    ("it", "R", PieceType.KING, PieceType.ROOK),
    ("ca", "R", PieceType.KING, PieceType.ROOK),
    ("ro", "R", PieceType.KING, PieceType.ROOK),
    ("fi", "R", PieceType.KNIGHT, PieceType.ROOK),
    ("is", "R", PieceType.KNIGHT, PieceType.ROOK),
    ("nl", "P", PieceType.KNIGHT, PieceType.PAWN),
    ("hu", "B", PieceType.ROOK, PieceType.BISHOP),
    ("ro", "N", PieceType.BISHOP, PieceType.KNIGHT),
    ("de", "B", PieceType.PAWN, PieceType.BISHOP),
    ("cs", "S", PieceType.BISHOP, None),
    ("pl", "W", PieceType.ROOK, None),
)


@pytest.mark.parametrize(("language", "letter", "local", "english"), FALSE_FRIENDS)
def test_a_letter_that_means_two_different_pieces_resolves_per_language(
    language, letter, local, english
):
    assert piece_for_letter(letter, language) is local
    if english is not None:
        assert piece_for_letter(letter, "en") is english


def test_german_knight_is_s_and_castling_uses_the_digit_zero():
    assert to_language("Nf3", "de") == "Sf3"
    assert to_language("O-O", "de") == "0-0"
    assert to_language("O-O-O", "de") == "0-0-0"
    assert from_language("0-0-0+", "de") == "O-O-O+"


def test_russian_king_is_two_characters_and_wins_over_the_knight():
    """``Кр`` (king) must match before ``К`` (knight), or every king move breaks."""
    assert to_language("Kg1", "ru") == "Крg1"
    assert to_language("Nf3", "ru") == "Кf3"
    assert from_language("Крg1", "ru") == "Kg1"
    assert from_language("Кf3", "ru") == "Nf3"


def test_russian_ocr_homoglyphs_are_folded_back_to_latin_files():
    """A Cyrillic ``а`` scanned from a Russian book still reads as file ``a``."""
    assert from_language("Ла1", "ru") == "Ra1"
    assert from_language("ехd5", "ru") == "exd5"


def test_dutch_pawn_letter_is_empty_because_p_is_already_the_knight():
    table = language_table("nl")
    assert table.knight == "P"
    assert table.pawn == ""
    assert to_language("Nf3", "nl") == "Pf3"
    assert from_language("Pf3", "nl") == "Nf3"


# --------------------------------------------------------------------------- #
# Tables and lookups
# --------------------------------------------------------------------------- #


def test_the_eight_languages_the_brief_names_are_all_present():
    for code in ("en", "pt", "de", "es", "fr", "it", "ru", "nl"):
        assert is_supported_language(code), code


def test_supported_languages_is_sorted_and_matches_the_tables():
    assert tuple(sorted(PIECE_TABLES)) == SUPPORTED_LANGUAGES
    assert len(SUPPORTED_LANGUAGES) >= 8


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_every_table_names_all_five_officers_uniquely(language):
    table = PIECE_TABLES[language]
    letters = [table.king, table.queen, table.rook, table.bishop, table.knight]
    assert all(letters), f"{language} left an officer letter empty"
    assert len(set(letters)) == 5, f"{language} reuses a letter for two officers"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_officer_letters_are_ordered_longest_first(language):
    lengths = [len(letter) for letter, _piece in PIECE_TABLES[language].officer_letters()]
    assert lengths == sorted(lengths, reverse=True)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_the_pawn_is_never_offered_as_a_san_prefix(language):
    """SAN never writes a pawn letter; offering it would misparse Dutch ``P``."""
    pieces = {piece for _letter, piece in PIECE_TABLES[language].officer_letters()}
    assert PieceType.PAWN not in pieces


def test_a_regional_subtag_resolves_to_its_primary_language():
    assert is_supported_language("pt-BR")
    assert language_table("pt-BR").code == "pt"
    assert language_table("PT_br").code == "pt"
    assert to_language("Nf3", "pt-BR") == "Cf3"


def test_an_unknown_language_is_refused_with_the_options_listed():
    assert not is_supported_language("klingon")
    with pytest.raises(NotationError, match="idioma sem tabela"):
        language_table("klingon")
    with pytest.raises(NotationError, match="idioma sem tabela"):
        to_language("Nf3", "klingon")


def test_piece_letter_and_piece_for_letter_are_inverse_in_every_language():
    for language in SUPPORTED_LANGUAGES:
        for piece in (
            PieceType.KING,
            PieceType.QUEEN,
            PieceType.ROOK,
            PieceType.BISHOP,
            PieceType.KNIGHT,
        ):
            letter = piece_letter(piece, language)
            assert piece_for_letter(letter, language) is piece, (language, piece)


def test_an_unassigned_letter_names_no_piece():
    assert piece_for_letter("Z", "en") is None
    assert piece_for_letter("", "en") is None


def test_default_language_is_english():
    assert DEFAULT_LANGUAGE == "en"
    assert piece_letter(PieceType.KNIGHT) == "N"


# --------------------------------------------------------------------------- #
# Figurine
# --------------------------------------------------------------------------- #


def test_both_glyph_sets_cover_all_six_pieces():
    assert set(FIGURINE_WHITE) == set(PieceType)
    assert set(FIGURINE_BLACK) == set(PieceType)
    assert len(set(FIGURINE_WHITE.values()) | set(FIGURINE_BLACK.values())) == 12


def test_solid_glyphs_are_the_print_default():
    assert figurine_for_piece(PieceType.KNIGHT) == "♞"
    assert figurine_for_piece(PieceType.KNIGHT, FigurineSet.WHITE) == "♘"


def test_figurine_replaces_only_the_piece_letter():
    assert to_figurine("Nf3") == "♞f3"
    assert to_figurine("exd5") == "exd5", "pawn moves keep no glyph, by convention"
    assert to_figurine("O-O") == "O-O", "castling keeps no glyph either"
    # (kept as separate assertions so a failure names the case)
    assert to_figurine("e8=Q+") == "e8=♛+"


def test_figurine_glyphs_are_read_in_every_language():
    for language in SUPPORTED_LANGUAGES:
        assert from_language("♞f3", language) == "Nf3"
        assert from_language("♘f3", language) == "Nf3"


# --------------------------------------------------------------------------- #
# render_san -- what a Move node actually asks for
# --------------------------------------------------------------------------- #


def test_render_letters_uses_the_language_table():
    assert render_san("Nf3", language="pt", style=MoveRenderStyle.LETTERS) == "Cf3"
    assert render_san("Nf3", language="de", style=MoveRenderStyle.LETTERS) == "Sf3"
    assert render_san("Nf3", language="ru", style=MoveRenderStyle.LETTERS) == "Кf3"


def test_render_figurine_ignores_the_language():
    for language in ("en", "pt", "de", "ru"):
        assert render_san("Nf3", language=language, style=MoveRenderStyle.FIGURINE) == "♞f3"


def test_render_both_prints_the_glyph_then_the_letters():
    assert render_san("Nf3", language="pt", style=MoveRenderStyle.BOTH) == "♞f3 (Cf3)"


def test_the_spec_5_5_example_holds_exactly():
    """SPEC 5.5: "Cf3" in Portuguese, the knight glyph in figurine, "Sf3" in German."""
    assert to_language("Nf3", "pt") == "Cf3"
    assert to_figurine("Nf3") == "♞f3"
    assert to_language("Nf3", "de") == "Sf3"


# --------------------------------------------------------------------------- #
# Reading what is actually printed in books
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("0-0", "O-O"),
        ("0-0-0", "O-O-O"),
        ("o-o", "O-O"),
        ("O–O", "O-O"),
        ("O—O—O", "O-O-O"),
        ("N×d5", "Nxd5"),
        ("Nd5†", "Nd5+"),
        ("Nd5‡", "Nd5#"),
        ("Nd5++", "Nd5#"),
        ("e:d5", "exd5"),
        ("e8(Q)", "e8=Q"),
        ("e8Q", "e8=Q"),
        ("  Nf3  ", "Nf3"),
    ],
)
def test_printed_variants_normalise_to_canonical_san(printed, expected):
    assert from_language(printed, "en") == expected


@pytest.mark.parametrize("token", ["--", "Z0", "z0", "0000", "(null)"])
def test_null_moves_pass_through_untouched(token):
    assert from_language(token, "pt") == token
    assert to_language(token, "pt") == token
    assert to_figurine(token) == token


@pytest.mark.parametrize("garbage", ["", "   ", "xyz", "Nz9", "9f3", "Nf", "N", "e9"])
def test_unreadable_tokens_are_refused_rather_than_guessed(garbage):
    with pytest.raises(NotationError):
        from_language(garbage, "en")


@pytest.mark.parametrize("garbage", ["", "Nf", "hello", "e9", "Kx"])
def test_to_language_refuses_a_token_that_is_not_english_san(garbage):
    with pytest.raises(NotationError, match=r"SAN ingles invalido|lance"):
        to_language(garbage, "pt")


def test_a_portuguese_token_is_refused_when_read_as_a_language_without_that_letter():
    """``Cf3`` is a knight in Portuguese and nothing at all in German."""
    assert from_language("Cf3", "pt") == "Nf3"
    with pytest.raises(NotationError):
        from_language("Cf3", "de")
