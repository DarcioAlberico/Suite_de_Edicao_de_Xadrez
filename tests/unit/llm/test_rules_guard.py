"""Strong evidence versus weak evidence in the deterministic matcher.

F11 cycle 2 measured the matcher against 233 real captions harvested from the
corpus and found it asserting a stipulation on **ten** captions that state none
-- scanned commentary, OCR wreckage, and a French primer paragraph that became
"mate in 2". Every one of those came from a single ambiguous word ("gewinnt.",
"Remis.", "vence.") or from a lone capital M next to a digit, read out of a
paragraph of running text.

The fix splits the evidence in two. A phrase that names the side *and* the
result, or a mate word followed closely by its number, is strong and is read
wherever it appears. One word that might be a result is weak, and is read only
from something caption-shaped. Measured on the held-out half of that set, which
was not looked at while the rule was written: fabrications 5 -> 2, precision
0.750 -> 0.882, MCC 0.705 -> 0.783, **recall unchanged at 0.750**.

These tests pin both halves so a later "simplification" cannot quietly undo it.
"""

from __future__ import annotations

import pytest

from caissa.llm.tasks import extract_stipulation

ASSERTIVE = frozenset({"mate", "win", "draw", "best_move", "study"})


def kind_of(caption: str) -> str:
    """What the matcher alone says the caption stipulates."""
    found = extract_stipulation(caption, allow_llm=False)
    return (found.kind if found is not None else "unknown") or "unknown"


# --------------------------------------------------------------------------- #
# Strong evidence is read wherever it appears
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("caption", "kind"),
    [
        ("Mate en 2. 1913", "mate"),
        ("Mate in 5 moves.", "mate"),
        ("Diagrama 47. Mate em 2 lances. Brancas jogam.", "mate"),
        ("Weiss zieht und gewinnt.", "win"),
        ("Weiss zieht und macht remis.", "draw"),
        ("White to play and win", "win"),
        ("Black to play and win", "win"),
        ("La condicion es: las blancas juegan y ganan", "win"),
        ("Las negras juegan y ganan", "win"),
        ("Qual o melhor lance das brancas?", "best_move"),
    ],
)
def test_strong_phrases_are_read(caption: str, kind: str) -> None:
    """A phrase that names the task is a stipulation, whatever surrounds it."""
    assert kind_of(caption) == kind


def test_a_strong_phrase_survives_a_long_caption() -> None:
    """Real captions carry the composer, the source and the year alongside."""
    caption = (
        "F. LAZARD Las blancas ganan -solver desde el principio hasta el "
        "Y el ultimo problema es para re- * (Ver soluciones en pagina 65)"
    )
    assert kind_of(caption) == "win"


def test_a_mate_number_must_belong_to_the_mate_word() -> None:
    """"...pour faire mat. ... 2) s'il ne reste..." is not "mate in 2"."""
    caption = (
        "4) si un joueur donne un echec perpetuel. 3) si les deuxjoueurs repetent "
        "toujours les memes coups; 2) s'il ne reste pas de forces suffisantes pour faire mat"
    )
    assert kind_of(caption) not in ASSERTIVE


# --------------------------------------------------------------------------- #
# Weak evidence is read only from something caption-shaped
# --------------------------------------------------------------------------- #


# The exact strings below are the captions as `pdf_text` produced them, copied
# out of `benchmarks/corpus/derived/llm_captions.jsonl` by id. Transliterating
# them would test a different string than the one that failed.
_VARIATION_PT = '(21…♗xd4 22 ♕xe4 ♗g7 23 ♖xh5) 22 gxh5 e5 23 h6 vence. 21 ♖dg1 ♗xd4 22 ♖xg4+! hxg4 23 ♕h6 leva ao mate) 21 ♕e3 ♘f6 Agora as Pretas ameaçam obter algum contrajogo com …a5-a4. ♘xe4 (em 20…hxg4 21 ♖dg1 e5 22 ♗e3 ♖d8 23 ♗h6; ou 20…♘xg4'  # noqa: E501 - legenda literal do acervo; quebrar a linha muda a string
_RUNNING_NL = 'ZWART WIT Deze combinatie leidt tot een Om g4 te dreigen. Deze zet ging niet dadelijk, daar zwart slot vol effect, maar is incorrect. ƒ61! dan natuurlijk zou hebben geof\xad remise. In Zandvoort heeft nie\xad Dreigt met 28............Le3 : Stelling na 34........... Pg4— 27.......... Le5—d4 c5xd4 e4—e3 man'  # noqa: E501 - legenda literal do acervo; quebrar a linha muda a string
_WRECKAGE_EN = '!\\mr(Jٽپmٿ•ڀ * Ç m1i* · -- -?\x10--\x08L-ڃjf. ٣ "\'m·- --?m ···\'m····- ڄ m1 i* D m m.m • Marianske Lanze, 1925 J anowski-Saemisch 53'  # noqa: E501 - legenda literal do acervo; quebrar a linha muda a string
_WRECKAGE_DE = '(Stellung nach 8. Sg5) k mjLM&M 1. A l i i k ¡¡§ ¡¡§ j§ |5 ff ¡3 % m m mm HS 1 mmmm A 3JLIS S fcO Hiernach wies Keres auf den Springerzug nach g5 hin, also 8. Sg5. A. ... Sh5 5. De2 g5 6. g4 fg 7. d4 g4. M e i n Dr. Filip und B. Koch schrieben mir, ohne Kenntnis der anderen Zuschriften, Die theoreti'  # noqa: E501 - legenda literal do acervo; quebrar a linha muda a string
_STILL_FIRES_DE_DRAW = 'Schwarz: Stellung nach dem 79. Zuge von 80. Df5—e6f Nach 80. Df5 : e4 würde Schwarz auf glänzende Weise das Remis er\xad zwingen und zwar unter Hergabe ei\xad Eesti Rahvusraamatukogu digitaalarhiiv DIGAR nes weitern Bauern; z. B.: 80. . . ., Weiß: S. Reslievsky. Schwarz: V. Petrovs. 102. Dg5—g6f 103. Dg6—'  # noqa: E501 - legenda literal do acervo; quebrar a linha muda a string
_STILL_FIRES_DE_WIN = 'Weiß: Stellung nach dem 20. Zuge von 20 ................ Sf6—e4! 21. Dd3—e2 ............. Natürlich konnte 21. S : e4, f : e 22. L : e4 nicht geschehen, wegen L : h2f und Schwarz gewinnt. 21 ................ Sei—g5'  # noqa: E501 - legenda literal do acervo; quebrar a linha muda a string


@pytest.mark.parametrize("caption", [_VARIATION_PT, _RUNNING_NL])
def test_a_lone_result_word_in_running_text_is_not_a_stipulation(caption: str) -> None:
    """This is the whole point: analysis is not a stipulation."""
    assert kind_of(caption) not in ASSERTIVE


@pytest.mark.parametrize("caption", [_WRECKAGE_EN, _WRECKAGE_DE])
def test_ocr_wreckage_does_not_become_mate_in_one(caption: str) -> None:
    """A lone capital M next to a digit is a glyph, not a stipulation."""
    assert kind_of(caption) not in ASSERTIVE


@pytest.mark.parametrize(
    ("caption", "kind"), [(_STILL_FIRES_DE_DRAW, "draw"), (_STILL_FIRES_DE_WIN, "win")]
)
def test_the_two_that_still_fire_are_recorded_rather_than_hidden(
    caption: str, kind: str
) -> None:
    """The residual, pinned so it cannot grow back unnoticed.

    Both are German commentary that prints the side and the result next to each
    other inside a subordinate clause -- "wuerde Schwarz ... das Remis
    erzwingen", "weil Weiss dann gewinnt". They are the two false positives left
    on the held-out half. Excluding them would mean writing a rule against two
    sentences, which is how a matcher gets tuned onto its own test set; F11
    cycle 2 stopped here and wrote the number down instead.
    """
    assert kind_of(caption) == kind


def test_weak_evidence_still_counts_in_a_real_caption() -> None:
    """The guard must not throw away the short captions it exists to protect."""
    assert kind_of("Remis.") == "draw"
    assert kind_of("Estudo de Reti") == "study"


def test_the_guard_does_not_touch_side_or_number() -> None:
    """A caption that states no task still yields what it does state."""
    found = extract_stipulation("Diagrama 120. Brancas jogam.", allow_llm=False)
    assert found is not None
    assert found.kind == "unknown"
    assert found.side_to_move == "w"
    assert found.diagram_number == 120
