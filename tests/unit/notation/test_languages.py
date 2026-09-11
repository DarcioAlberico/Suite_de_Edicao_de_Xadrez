"""Locale tables, exact round-tripping, and the abstaining language detector."""

from __future__ import annotations

import functools
import random

import chess
import pytest

from caissa.notation.languages import (
    DETECTABLE,
    ENGLISH_PIECES,
    FIGURINE_OUTLINE,
    FIGURINE_SOLID,
    LOCALES,
    available_locales,
    detect_language,
    figurine,
    from_language,
    get_locale,
    parse_san,
    to_language,
)

REAL_LOCALES = ("en", "pt", "es", "fr", "it", "de", "nl", "ru")


# --------------------------------------------------------------------------- #
# Corpora
# --------------------------------------------------------------------------- #


@functools.lru_cache(maxsize=1)
def real_sans(count: int = 100_000) -> tuple[str, ...]:
    """``count`` SAN moves from real random games, in the order they were played.

    Real games rather than synthetic strings, because they are what the
    distribution actually looks like: mostly pawn and knight moves, a handful of
    promotions, disambiguators only where the position forces one.
    """
    random.seed(20260907)
    board = chess.Board()
    out: list[str] = []
    while len(out) < count:
        if board.is_game_over() or board.fullmove_number > 150:
            board = chess.Board()
            continue
        move = random.choice(list(board.legal_moves))
        out.append(board.san(move))
        board.push(move)
    return tuple(out)


@functools.lru_cache(maxsize=1)
def synthetic_sans() -> tuple[str, ...]:
    """Every SAN *shape*, whether or not a game ever produces it.

    The real corpus above has 100k moves but only a couple of thousand distinct
    strings.  This one is the complement: a systematic sweep of piece x
    disambiguator x capture x square x promotion x mark, so that a locale which
    mishandles, say, a rank disambiguator in front of a capture is caught even
    though random games almost never print one.
    """
    squares = [f"{file}{rank}" for file in "abcdefgh" for rank in "12345678"]
    disambiguators = ["", *"abcdefgh", *"12345678", "a1", "h8", "d4"]
    out: list[str] = []
    for piece in ("", "K", "Q", "R", "B", "N"):
        for disambiguator in disambiguators:
            for capture in ("", "x"):
                for target in squares[::2]:
                    for suffix in ("", "+", "#"):
                        out.append(f"{piece}{disambiguator}{capture}{target}{suffix}")
    for file in "abcdefgh":
        for promotion in ("Q", "R", "B", "N"):
            for suffix in ("", "+", "#"):
                out.append(f"{file}8={promotion}{suffix}")
                out.append(f"{file}xb8={promotion}{suffix}")
    out += ["O-O", "O-O-O", "O-O+", "O-O-O+", "O-O#", "O-O-O#"]
    return tuple(out)


# --------------------------------------------------------------------------- #
# The tables themselves
# --------------------------------------------------------------------------- #


class TestTables:
    def test_every_locale_defines_five_distinct_move_letters(self):
        for code in REAL_LOCALES:
            locale = get_locale(code)
            letters = locale.move_letters
            assert len(letters) == 5, f"{code} must have K Q R B N and no duplicates"

    def test_the_pawn_never_shares_a_letter_with_a_piece(self):
        for code in REAL_LOCALES:
            locale = get_locale(code)
            if locale.pawn is None:
                continue
            assert locale.pawn not in locale.move_letters, (
                f"{code}: the pawn letter collides with a piece inside its own locale"
            )

    def test_dutch_has_no_pawn_letter_because_p_is_the_knight(self):
        assert get_locale("nl").pawn is None
        assert get_locale("nl").knight == "P"

    def test_the_known_collisions_are_recorded(self):
        # A letter is a collision only when it means a *different* piece than in
        # English.  `B` is the bishop in both English and Portuguese, so it is a
        # coincidence, not a collision; `B` in German is the pawn, so it is one.
        assert get_locale("pt").collides_with_english == frozenset({"R"})
        assert get_locale("es").collides_with_english == frozenset({"R"})
        assert get_locale("fr").collides_with_english == frozenset({"R"})
        assert get_locale("it").collides_with_english == frozenset({"R"})
        assert get_locale("de").collides_with_english == frozenset({"B"})
        assert get_locale("nl").collides_with_english == frozenset({"P"})
        assert get_locale("en").collides_with_english == frozenset()
        assert "B" not in get_locale("pt").collides_with_english

    def test_r_is_the_king_in_four_languages_and_the_rook_in_one(self):
        kings = {code for code in REAL_LOCALES if get_locale(code).reverse_pieces.get("R") == "K"}
        rooks = {code for code in REAL_LOCALES if get_locale(code).reverse_pieces.get("R") == "R"}
        assert kings == {"pt", "es", "fr", "it"}
        assert rooks == {"en"}

    def test_the_ambiguity_set_names_the_rivals(self):
        rivals = get_locale("pt").ambiguity_set()
        assert "en" in rivals["R"], "English reads pt's king letter as a rook"
        assert "de" in rivals["B"], "German reads pt's bishop letter as a pawn"
        assert rivals["C"] == frozenset(), "no locale reads C as anything but the knight"

    def test_russian_king_is_two_characters(self):
        assert get_locale("ru").king == "Кр"
        assert to_language("Kd2", "ru") == "Крd2"
        assert from_language("Крd2", "ru") == "Kd2"
        assert from_language("Кd2", "ru") == "Nd2", "К alone is the knight"

    def test_figurines_are_the_documented_codepoints(self):
        assert [ord(g) for g in FIGURINE_OUTLINE.values()] == list(range(0x2654, 0x265A))
        assert [ord(g) for g in FIGURINE_SOLID.values()] == list(range(0x265A, 0x2660))
        assert tuple(FIGURINE_OUTLINE) == ENGLISH_PIECES

    def test_get_locale_names_the_alternatives_when_it_fails(self):
        with pytest.raises(KeyError, match="unknown notation locale"):
            get_locale("klingon")


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #


class TestRoundTrip:
    @pytest.mark.slow
    @pytest.mark.parametrize("code", available_locales())
    def test_100k_real_moves_survive_the_round_trip_byte_for_byte(self, code):
        corpus = real_sans()
        assert len(corpus) == 100_000
        failures = [
            (san, to_language(san, code))
            for san in corpus
            if from_language(to_language(san, code), code) != san
        ]
        assert failures[:5] == [], f"{len(failures)} of {len(corpus)} failed in {code}"

    @pytest.mark.parametrize("code", available_locales())
    def test_every_san_shape_survives_the_round_trip(self, code):
        failures = [
            (san, to_language(san, code))
            for san in synthetic_sans()
            if from_language(to_language(san, code), code) != san
        ]
        assert failures[:5] == [], f"{len(failures)} shapes failed in {code}"

    def test_the_synthetic_corpus_is_broad(self):
        corpus = synthetic_sans()
        assert len(corpus) > 20_000
        assert "O-O-O#" in corpus
        assert any("=" in san for san in corpus)
        assert any(san[:1] in "KQRBN" and "x" in san for san in corpus)

    def test_translation_is_the_expected_letter(self):
        assert to_language("Nf3", "pt") == "Cf3"
        assert to_language("Nf3", "de") == "Sf3"
        assert to_language("Nf3", "nl") == "Pf3"
        assert to_language("Nf3", "fr") == "Cf3"
        assert to_language("Bxf6", "de") == "Lxf6"
        assert to_language("Bxf6", "es") == "Axf6"
        assert to_language("Qh5+", "it") == "Dh5+"
        assert to_language("e8=Q", "pt") == "e8=D"

    def test_figurines_render_both_fills_and_read_back_from_either(self):
        assert figurine("Nf3") == "♘f3"
        assert figurine("Nf3", solid=True) == "♞f3"
        assert from_language("♘f3", "figurine") == "Nf3"
        assert from_language("♞f3", "figurine") == "Nf3", "outline locale reads solid too"
        assert from_language("♘f3", "figurine-solid") == "Nf3"

    def test_a_figurine_is_readable_inside_any_locale(self):
        # A Portuguese book that prints figurines is still a Portuguese book.
        assert from_language("♘f3", "pt") == "Nf3"
        assert from_language("♜xd1", "de") == "Rxd1"

    def test_a_leading_pawn_letter_is_not_san(self):
        assert from_language("Pe4", "en") is None
        assert from_language("Pe4", "pt") is None
        assert from_language("Pf3", "nl") == "Nf3", "in Dutch P is the knight, not the pawn"

    def test_a_letter_from_the_wrong_locale_is_refused(self):
        assert from_language("Sf3", "pt") is None
        assert from_language("Cf3", "de") is None
        assert from_language("Af3", "fr") is None
        assert from_language("Ff3", "es") is None

    def test_castling_and_capture_aliases_are_read_but_never_written(self):
        assert from_language("0-0", "de") == "O-O"
        assert from_language("0-0-0+", "pt") == "O-O-O+"
        assert to_language("O-O", "de") == "O-O", "rendering is always canonical"
        assert from_language("Л:d1", "ru") == "Rxd1", "Russian books use a colon for captures"

    def test_a_non_san_token_comes_back_unchanged(self):
        assert to_language("Zzz", "pt") == "Zzz"
        assert parse_san("Zzz") is None
        assert parse_san("Nf3") is not None


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

#: One page-sized sample per language, in the style stratum E1-E7 actually
#: contains: a sentence of prose followed by a line of moves.
SAMPLES: dict[str, str] = {
    "en": (
        "White plays for the initiative and Black must not take the pawn. "
        "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Bg5 e6 7.f4 Qb6 "
        "8.Qd2 Qxb2 9.Rb1 Qa3 10.f5 Nc6 11.fxe6 fxe6 12.Nxc6 bxc6 13.e5 dxe5"
    ),
    "pt": (
        "As brancas jogam pela iniciativa e as pretas não devem tomar o peão. "
        "1.e4 c5 2.Cf3 d6 3.d4 cxd4 4.Cxd4 Cf6 5.Cc3 a6 6.Bg5 e6 7.f4 Db6 "
        "8.Dd2 Dxb2 9.Tb1 Da3 10.f5 Cc6 11.fxe6 fxe6 12.Cxc6 bxc6 13.e5 dxe5"
    ),
    "es": (
        "Las blancas juegan por la iniciativa y las negras no deben tomar el peón. "
        "1.e4 c5 2.Cf3 d6 3.d4 cxd4 4.Cxd4 Cf6 5.Cc3 a6 6.Ag5 e6 7.f4 Db6 "
        "8.Dd2 Dxb2 9.Tb1 Da3 10.f5 Cc6 11.fxe6 fxe6 12.Cxc6 bxc6 13.e5 dxe5"
    ),
    "fr": (
        "Les blancs jouent pour l'initiative et les noirs ne doivent pas prendre le pion. "
        "1.e4 c5 2.Cf3 d6 3.d4 cxd4 4.Cxd4 Cf6 5.Cc3 a6 6.Fg5 e6 7.f4 Db6 "
        "8.Dd2 Dxb2 9.Tb1 Da3 10.f5 Cc6 11.fxe6 fxe6 12.Cxc6 bxc6 13.e5 dxe5"
    ),
    "it": (
        "Il bianco gioca per l'iniziativa e il nero non deve prendere il pedone. "
        "1.e4 c5 2.Cf3 d6 3.d4 cxd4 4.Cxd4 Cf6 5.Cc3 a6 6.Ag5 e6 7.f4 Db6 "
        "8.Dd2 Dxb2 9.Tb1 Da3 10.f5 Cc6 11.fxe6 fxe6 12.Cxc6 bxc6 13.e5 dxe5"
    ),
    "de": (
        "Weiß spielt auf Initiative und Schwarz darf den Bauern nicht nehmen. "
        "1.e4 c5 2.Sf3 d6 3.d4 cxd4 4.Sxd4 Sf6 5.Sc3 a6 6.Lg5 e6 7.f4 Db6 "
        "8.Dd2 Dxb2 9.Tb1 Da3 10.f5 Sc6 11.fxe6 fxe6 12.Sxc6 bxc6 13.e5 dxe5"
    ),
    "nl": (
        "Wit speelt op initiatief en zwart mag de pion niet nemen. "
        "1.e4 c5 2.Pf3 d6 3.d4 cxd4 4.Pxd4 Pf6 5.Pc3 a6 6.Lg5 e6 7.f4 Db6 "
        "8.Dd2 Dxb2 9.Tb1 Da3 10.f5 Pc6 11.fxe6 fxe6 12.Pxc6 bxc6 13.e5 dxe5"
    ),
    "ru": (
        "Белые играют на инициативу, и чёрные не должны брать пешку. "
        "1.e4 c5 2.Кf3 d6 3.d4 cxd4 4.Кxd4 Кf6 5.Кc3 a6 6.Сg5 e6 7.f4 Фb6 "
        "8.Фd2 Фxb2 9.Лb1 Фa3 10.f5 Кc6 11.fxe6 fxe6 12.Кxc6 bxc6 13.e5 dxe5"
    ),
}


class TestDetection:
    @pytest.mark.parametrize("code", REAL_LOCALES)
    def test_a_page_of_that_language_is_identified(self, code):
        detection = detect_language(SAMPLES[code])
        assert detection.best == code, (
            f"{code}: ranked {[(s.code, round(s.score, 2)) for s in detection.ranked[:3]]}"
        )
        assert not detection.abstained
        assert detection.confidence > 0.3

    @pytest.mark.parametrize("code", REAL_LOCALES)
    def test_the_ranking_is_a_ranking(self, code):
        detection = detect_language(SAMPLES[code])
        scores = [score.score for score in detection.ranked]
        assert scores == sorted(scores, reverse=True)
        assert len(detection.ranked) == len(DETECTABLE)
        assert abs(sum(scores) - 1.0) < 1e-9, "the ranking is normalised"

    @pytest.mark.parametrize("code", REAL_LOCALES)
    def test_the_moves_alone_are_enough_for_most_languages(self, code):
        """Prose stripped: only the notation is left."""
        moves_only = SAMPLES[code].split(". ", 1)[-1].split("1.", 1)[-1]
        detection = detect_language("1." + moves_only)
        if code in ("es", "it"):
            # Spanish and Italian have identical piece tables.  Nothing in the
            # notation can separate them, so the honest answer is to abstain.
            assert detection.abstained
            assert {score.code for score in detection.ranked[:2]} == {"es", "it"}
        else:
            assert detection.best == code

    def test_a_text_with_no_piece_letters_abstains(self):
        detection = detect_language("1.e4 e5 2.d4 exd4 3.c3 dxc3 4.b4 c5 5.a3")
        assert detection.abstained
        assert detection.best is None
        assert "no evidence" in detection.reason or "observation" in detection.reason

    def test_empty_and_prose_only_input_abstains(self):
        for text in ("", "   ", "a page of nothing much"):
            detection = detect_language(text)
            assert detection.abstained
            assert detection.confidence == 0.0 or detection.best is None

    def test_a_single_stray_letter_is_not_a_language(self):
        # English prose with one Portuguese-looking token.  The answer must not
        # be Portuguese: one token is a typo or a quotation, not a language.
        detection = detect_language("see diagram 4 and the square Cf3 in passing")
        assert detection.best != "pt"
        portuguese = next(score for score in detection.ranked if score.code == "pt")
        assert portuguese.score < 0.5

    def test_one_move_head_and_no_words_abstains(self):
        detection = detect_language("Cf3")
        assert detection.abstained
        assert "observation" in detection.reason

    def test_abstention_still_carries_the_consensus_map(self):
        detection = detect_language("1.Cf3 Dd8 2.Tf1 Rg8 3.Td1 Rf8")
        assert detection.abstained
        assert detection.consensus_pieces is not None
        assert detection.consensus_pieces["C"] == "N"
        assert detection.consensus_pieces["R"] == "K"
        assert "B" not in detection.consensus_pieces, (
            "only Portuguese knows B here, so it is not consensus"
        )

    def test_piece_map_falls_back_to_nothing_when_there_is_no_evidence(self):
        assert dict(detect_language("hello").piece_map()) == {}

    def test_a_miss_costs_more_than_a_hit(self):
        """`Sf3` is impossible in Portuguese; one of them outweighs several `T`."""
        detection = detect_language("1.Tf1 Td1 Te1 Sf3 Sd2")
        assert detection.ranked[0].code == "de"
        portuguese = next(s for s in detection.ranked if s.code == "pt")
        assert portuguese.piece_misses == 2

    def test_evidence_is_reported(self):
        detection = detect_language(SAMPLES["de"])
        german = detection.ranked[0]
        assert german.code == "de"
        assert german.piece_hits > 5
        assert german.piece_misses == 0
        assert german.lexicon_hits > 0
        assert german.evidence, "the UI needs to show what voted"


class TestDetectionAccuracy:
    """The headline number, measured rather than asserted move by move."""

    def test_accuracy_over_every_language(self):
        correct = 0
        wrong: list[tuple[str, str | None]] = []
        for code in REAL_LOCALES:
            detection = detect_language(SAMPLES[code])
            if detection.best == code:
                correct += 1
            else:
                wrong.append((code, detection.best))
        assert wrong == [], f"{correct}/{len(REAL_LOCALES)} correct; wrong: {wrong}"

    def test_no_language_is_ever_confidently_wrong(self):
        """The one failure mode that costs a book: confident and wrong."""
        for code, sample in SAMPLES.items():
            detection = detect_language(sample)
            if detection.abstained:
                continue
            assert detection.best == code, (
                f"{code} was read as {detection.best} with confidence "
                f"{detection.confidence:.2f} -- a confident wrong answer"
            )


class TestLocaleRegistry:
    def test_available_locales_includes_the_figurine_pseudo_locales(self):
        codes = available_locales()
        assert set(REAL_LOCALES) <= set(codes)
        assert "figurine" in codes
        assert "figurine-solid" in codes

    def test_figurines_are_not_detectable_languages(self):
        assert "figurine" not in DETECTABLE, (
            "a figurine book still writes its prose in some language"
        )

    def test_every_locale_has_a_name_and_an_endonym(self):
        for locale in LOCALES.values():
            assert locale.name
            assert locale.endonym
