"""The five tasks: schemas, fail-closed behaviour, and the move-safety rule.

The recurring shape of these tests is "the model said something wrong; prove
that nothing wrong came out".
"""

from __future__ import annotations

import json

import pytest

from caissa.llm.tasks import (
    Stipulation,
    caption_for_diagram,
    extract_stipulation,
    material_summary,
    repair_ocr_region,
    translate_notation_prose,
    verify_diagram,
)

from .conftest import GOOD_FEN, PNG_BYTES, FakeRuntime, verdict_reply

# --------------------------------------------------------------------------- #
# verify_diagram
# --------------------------------------------------------------------------- #


def test_verify_accepts_a_well_formed_reply():
    runtime = FakeRuntime([verdict_reply("inconsistent", 0.8, ["e4", "d5"], "peca errada")])
    result = verify_diagram(PNG_BYTES, GOOD_FEN, "Diagrama 3", runtime=runtime)
    assert result.verdict == "inconsistent"
    assert result.confidence == 0.8
    assert result.suspect_squares == ("e4", "d5")
    assert result.used_llm is True
    assert result.disagrees is True


def test_verify_attaches_the_image_and_the_inventory():
    """The prompt hands the model a checkable inventory, not just "read the board"."""
    runtime = FakeRuntime([verdict_reply()])
    verify_diagram(PNG_BYTES, GOOD_FEN, "legenda", runtime=runtime)
    request = runtime.requests[0]
    assert request.images == (PNG_BYTES,)
    assert "Torre branca" in request.prompt
    assert "legenda" in request.prompt


def test_verify_refuses_an_unparseable_candidate_without_calling_the_model():
    """A FEN that does not parse is not the model's problem."""
    runtime = FakeRuntime([verdict_reply()])
    result = verify_diagram(PNG_BYTES, "not a fen", runtime=runtime)
    assert result.used_llm is False
    assert runtime.requests == []


def test_verify_refuses_an_empty_image():
    runtime = FakeRuntime([verdict_reply()])
    assert verify_diagram(b"", GOOD_FEN, runtime=runtime).used_llm is False
    assert runtime.requests == []


def test_verify_accepts_an_illegal_candidate_because_that_is_the_interesting_case():
    """Composition diagrams and misreadings are exactly what needs a second opinion."""
    runtime = FakeRuntime([verdict_reply("inconsistent", 0.9, ["e1"])])
    illegal = "8/8/8/8/8/8/8/4K3 w - - 0 1"  # no black king
    assert verify_diagram(PNG_BYTES, illegal, runtime=runtime).used_llm is True


def test_material_summary_counts_correctly():
    summary = material_summary("4k3/pppp4/8/8/8/8/4PPPP/4K3 w - - 0 1")
    assert "1x Rei branco" in summary
    assert "4x Peao branco" in summary
    assert "4x Peao preto" in summary
    assert material_summary("8/8/8/8/8/8/8/8 w - - 0 1") == "vazio"


# --------------------------------------------------------------------------- #
# extract_stipulation -- seven languages, rules first
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("caption", "kind", "moves"),
    [
        ("Mate em 2", "mate", 2),
        ("Xeque-mate em 3 lances", "mate", 3),
        ("Mate in 2", "mate", 2),
        ("Matt in 2 Zuegen", "mate", 2),
        ("Mate en 3", "mate", 3),
        ("Mat en 2 coups", "mate", 2),
        ("Matto in 4 mosse", "mate", 4),
        ("Мат в 2 хода", "mate", 2),
        ("Brancas jogam e ganham", "win", None),
        ("White to play and win", "win", None),
        ("Weiss zieht und gewinnt", "win", None),
        ("Blancas juegan y ganan", "win", None),
        ("Les Blancs jouent et gagnent", "win", None),
        ("Il Bianco muove e vince", "win", None),
        ("Белые начинают и выигрывают", "win", None),
        ("Brancas jogam e empatam", "draw", None),
        ("White to play and draw", "draw", None),
        ("Schwarz haelt remis", "draw", None),
        ("Negras juegan y tablas", "draw", None),
        ("Qual o melhor lance?", "best_move", None),
        ("Find the best move", "best_move", None),
    ],
)
def test_stipulations_are_recognised_without_an_llm(caption, kind, moves):
    """Seven languages, deterministic, free, and exact. The model is not consulted."""
    runtime = FakeRuntime([verdict_reply()])
    result = extract_stipulation(caption, runtime=runtime, allow_llm=False)
    assert result is not None, caption
    assert result.kind == kind
    assert result.moves == moves
    assert result.source == "rules"
    assert runtime.requests == []


@pytest.mark.parametrize(
    ("caption", "number"),
    [
        ("Diagrama 12", 12),
        ("Diagram 7", 7),
        ("Abbildung 41", 41),
        ("No. 45", 45),
        ("Problema 3", 3),
        ("Exercicio 108", 108),
        ("Posicao 7", 7),
        ("#3", 3),
    ],
)
def test_diagram_numbers_are_extracted(caption, number):
    result = extract_stipulation(caption, allow_llm=False)
    assert result is not None
    assert result.diagram_number == number


def test_side_to_move_is_read_from_the_caption():
    assert extract_stipulation("Brancas jogam e ganham", allow_llm=False).side_to_move == "w"
    assert extract_stipulation("Pretas jogam e ganham", allow_llm=False).side_to_move == "b"
    assert extract_stipulation("Black to play and win", allow_llm=False).side_to_move == "b"


def test_language_is_detected():
    assert extract_stipulation("Brancas jogam e ganham", allow_llm=False).language == "pt"
    assert extract_stipulation("Белые начинают и выигрывают", allow_llm=False).language == "ru"
    assert extract_stipulation("Weiss zieht und gewinnt", allow_llm=False).language == "de"


def test_rules_answer_is_never_overridden_by_the_model():
    """The rules path is exact where it fires; the model only fills gaps."""
    runtime = FakeRuntime(
        [json.dumps({"kind": "draw", "moves": None, "confidence": 0.99, "language": "pt"})]
    )
    result = extract_stipulation("Mate em 2", runtime=runtime)
    assert result is not None
    assert result.kind == "mate"
    assert result.source == "rules"
    assert runtime.requests == []


def test_model_fills_a_gap_the_rules_left():
    runtime = FakeRuntime(
        [
            json.dumps(
                {
                    "kind": "mate",
                    "moves": 2,
                    "side_to_move": "w",
                    "diagram_number": 9,
                    "language": "nl",
                    "confidence": 0.9,
                }
            )
        ]
    )
    result = extract_stipulation("Wit speelt en geeft mat in twee zetten", runtime=runtime)
    assert result is not None
    assert result.kind == "mate"
    assert result.source == "llm"
    assert result.confidence <= 0.85  # LLM answers are capped below rules answers


def test_model_answer_outside_the_vocabulary_is_rejected():
    runtime = FakeRuntime([json.dumps({"kind": "helpmate_in_seven", "confidence": 0.99})])
    assert extract_stipulation("iets in het Nederlands", runtime=runtime) is None


def test_absurd_move_counts_are_rejected():
    """"Mate in 400" is a typo or a page number, not a stipulation."""
    assert extract_stipulation("Mate em 400", allow_llm=False) is None
    runtime = FakeRuntime([json.dumps({"kind": "mate", "moves": 400, "confidence": 0.9})])
    assert extract_stipulation("iets", runtime=runtime) is None


def test_empty_caption_yields_nothing():
    assert extract_stipulation("", allow_llm=False) is None
    assert extract_stipulation("   ", allow_llm=False) is None


def test_stipulation_is_a_frozen_dataclass():
    stipulation = Stipulation(kind="mate", moves=2)
    with pytest.raises((AttributeError, TypeError)):
        stipulation.kind = "draw"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# repair_ocr_region
# --------------------------------------------------------------------------- #


def test_ocr_repair_returns_the_transcription():
    runtime = FakeRuntime([json.dumps({"text": "As brancas ganham.", "confidence": 0.9})])
    assert repair_ocr_region(PNG_BYTES, "As brancaz garham.", "pt", runtime=runtime) == (
        "As brancas ganham."
    )


def test_ocr_repair_rejects_a_low_confidence_answer():
    runtime = FakeRuntime([json.dumps({"text": "algo", "confidence": 0.1})])
    assert repair_ocr_region(PNG_BYTES, "a", "pt", runtime=runtime) is None


def test_ocr_repair_rejects_a_runaway_transcription():
    """Length explosion is the signature of a model that started narrating."""
    runtime = FakeRuntime([json.dumps({"text": "x " * 900, "confidence": 0.95})])
    assert repair_ocr_region(PNG_BYTES, "short region text here", "pt", runtime=runtime) is None


def test_ocr_repair_accepts_a_reasonable_expansion():
    """A short region may legitimately transcribe a little longer than the failed read."""
    runtime = FakeRuntime([json.dumps({"text": "A" * 70, "confidence": 0.9})])
    assert repair_ocr_region(PNG_BYTES, "", "pt", runtime=runtime) is not None


def test_ocr_repair_rejects_an_empty_answer():
    runtime = FakeRuntime([json.dumps({"text": "", "confidence": 0.99})])
    assert repair_ocr_region(PNG_BYTES, "abc", "pt", runtime=runtime) is None


# --------------------------------------------------------------------------- #
# caption_for_diagram
# --------------------------------------------------------------------------- #


def test_caption_uses_the_model_when_it_behaves():
    runtime = FakeRuntime([json.dumps({"caption": "Final de torres com peao passado."})])
    assert caption_for_diagram(GOOD_FEN, runtime=runtime) == "Final de torres com peao passado."


@pytest.mark.parametrize(
    "caption",
    [
        "As brancas ganham com Nf3!",
        "Depois de 1.e4 a posicao muda.",
        "A chave e Qxh7#",
        "O lance O-O-O decide.",
        "Apos Rxe4 as pretas caem.",
    ],
)
def test_a_caption_containing_a_move_is_discarded(caption):
    """Moves come from the exact F6 engine. A generated one is a defect, not a feature."""
    runtime = FakeRuntime([json.dumps({"caption": caption})])
    assert caption_for_diagram(GOOD_FEN, runtime=runtime, language="pt") == "Brancas jogam"


def test_caption_falls_back_when_the_model_returns_nothing():
    runtime = FakeRuntime([json.dumps({"caption": "   "})])
    assert caption_for_diagram(GOOD_FEN, runtime=runtime, language="pt") == "Brancas jogam"


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("pt", "Brancas jogam"),
        ("en", "White to move"),
        ("de", "Weiss am Zug"),
        ("es", "Juegan blancas"),
        ("fr", "Les Blancs jouent"),
        ("it", "Muove il Bianco"),
        ("ru", "Ход белых"),
    ],
)
def test_fallback_caption_speaks_the_users_language(language, expected):
    runtime = FakeRuntime(available=False)
    assert caption_for_diagram(GOOD_FEN, runtime=runtime, language=language) == expected


# --------------------------------------------------------------------------- #
# translate_notation_prose -- the model must never touch a move
# --------------------------------------------------------------------------- #


def test_moves_never_reach_the_model():
    """The prompt that leaves this process contains sentinels, not notation."""
    runtime = FakeRuntime([json.dumps({"translation": "White plays [[M0]] [[M1]] [[M2]]."})])
    translate_notation_prose("As brancas jogam 1.e4 e5 2.Cf3.", "pt", "en", runtime=runtime)
    sent = runtime.requests[0].prompt
    assert "e4" not in sent
    assert "Cf3" not in sent
    assert "[[M0]]" in sent


def test_moves_come_back_byte_identical():
    runtime = FakeRuntime([json.dumps({"translation": "White plays [[M0]][[M1]] [[M2]][[M3]]."})])
    result = translate_notation_prose("Brancas jogam 1.e4 2.Cf3.", "pt", "en", runtime=runtime)
    assert "e4" in result
    assert "Cf3" in result


@pytest.mark.parametrize(
    "translation",
    [
        "White plays [[M0]] and wins.",  # a sentinel was dropped
        "White plays [[M0]] [[M1]] [[M1]].",  # one was duplicated
        "White plays [[M1]] [[M0]].",  # reordered
        "White plays e4 and Nf3.",  # the model wrote moves itself
        "White plays [[M0]] [[M1]] [[M9]].",  # invented a sentinel
    ],
)
def test_a_broken_mask_discards_the_whole_translation(translation):
    """A book with one corrupted move is worse than an untranslated one."""
    source = "Brancas jogam 1.e4 2.Cf3."
    runtime = FakeRuntime([json.dumps({"translation": translation})])
    assert translate_notation_prose(source, "pt", "en", runtime=runtime) == source


def test_prose_without_moves_still_translates():
    runtime = FakeRuntime([json.dumps({"translation": "This is a quiet position."})])
    result = translate_notation_prose("Esta e uma posicao tranquila.", "pt", "en", runtime=runtime)
    assert result == "This is a quiet position."


@pytest.mark.parametrize(
    "token",
    ["1.e4", "Nf3", "Cf3", "Sf3", "O-O", "0-0-0", "Qxh7#", "exd5", "e8=Q", "1-0", "15...Rxe4"],
)
def test_move_like_tokens_are_all_masked(token):
    """Masking is deliberately greedy: a false positive is cheap, a miss is not."""
    runtime = FakeRuntime([json.dumps({"translation": "x"})])
    translate_notation_prose(f"O lance {token} decide.", "pt", "en", runtime=runtime)
    assert token not in runtime.requests[0].prompt


def test_empty_text_is_returned_untouched():
    runtime = FakeRuntime([json.dumps({"translation": "should not be used"})])
    assert translate_notation_prose("", "pt", "en", runtime=runtime) == ""
    assert runtime.requests == []
