"""Finding the moves inside a paragraph — SPEC §7.1, F5_REPORT_C2 §7.

``RegionKind.MOVETEXT`` had been in the taxonomy since F1, with a Tesseract
page-segmentation mode of its own, and **nothing ever assigned it**.  That is a
third kind of blindness this project has now collected: not a gate that
measures nothing, and not a gate pointed at the wrong unit, but a declared
capability that was never wired to anything.

The tests below are built around the one thing that makes this module worth
having: a run has to be long enough to *discriminate*.  A two-ply fragment
replays legally under almost any reading, so a segmenter that shatters
sequences at the first English word is no better than no segmenter, and a
segmenter that swallows whole paragraphs is worse.
"""

from __future__ import annotations

import pytest

from caissa.ocr.notation import longest_run, move_runs

#: A paragraph of real analysis prose with one main line inside it.  The shape
#: is taken from Nunn p200: a citation, a sentence of explanation, the moves,
#: and a closing remark.
PARAGRAPH = (
    "296 Wahls — Ziiger Munich 1989: Although such a third rank defence is "
    "less reliable than the defensive schemes outlined in section 7.1, it is "
    "nevertheless usually enough for a draw: 1 Nc5 Rh6 2 Bc5 Rh2+ 3 Kd4 Rh4+ "
    "4 Ke5 Rh5+ 5 Kf6 Rh6+ 6 Kg5 Rh1 and Black holds the draw comfortably."
)

PROSE_ONLY = (
    "The rook belongs behind the passed pawn, and the reason is not hard to "
    "see. When the rook stands in front of the pawn it must move away before "
    "the pawn can advance, so the attacking side loses time with every step."
)


def test_a_run_is_pulled_out_of_a_paragraph():
    run = longest_run(PARAGRAPH)
    assert run is not None
    assert run.moves == 12
    assert run.text.startswith("Nc5 Rh6")
    assert run.text.endswith("Rh1")
    assert "Although" not in run.text and "comfortably" not in run.text


def test_prose_alone_yields_nothing():
    assert move_runs(PROSE_ONLY) == ()
    assert longest_run(PROSE_ONLY) is None


def test_a_sentence_that_mentions_one_square_is_not_a_game():
    """``min_moves`` is what stops "the pawn on e4 is weak" from being a run."""
    assert move_runs("The pawn on e4 is weak and the knight on f3 defends it.") == ()


def test_a_run_survives_the_words_analysis_interrupts_itself_with():
    """**The reason ``max_gap`` exists.**

    Published analysis never writes ten plies in silence — it says "and now",
    "winning the rook", "but not". Breaking at the first such word turns one
    twelve-ply line into six two-ply fragments, and a two-ply fragment replays
    legally under almost any reading. That is precisely the state that made the
    repairer tie seven locales at confidence 0.01 (F5_REPORT_C2 §7.2).
    """
    text = ("1 Nc5 Rh6 and now 2 Bc5 Rh2+ winning the rook 3 Kd4 Rh4+ "
            "but not 4 Ke5 Rh5+ 5 Kf6 Rh6+")
    run = longest_run(text)
    assert run is not None
    assert run.moves >= 10, run.describe_pt()


def test_but_a_paragraph_is_not_swallowed_whole():
    """The other side of ``max_gap``: four words in a row end the run."""
    text = ("1 Nc5 Rh6 2 Bc5 Rh2+ and this is where the explanation really "
            "begins in earnest with many words 3 Kd4 Rh4+ 4 Ke5 Rh5+ 5 Kf6")
    runs = move_runs(text)
    assert len(runs) == 2, [r.describe_pt() for r in runs]
    assert "explanation" not in runs[0].text
    assert "explanation" not in runs[1].text
    assert runs[0].text.endswith("Rh2+")
    # The move number that opens the second run is not captured: a run starts
    # at its first *move*, and a number is only kept once a run is already
    # open.  Harmless — the repairer re-derives numbering anyway — and
    # asserted so it is a decision rather than a surprise.
    assert runs[1].text.startswith("Kd4")


def test_a_two_move_tail_is_not_promoted_to_a_run():
    """``min_moves`` again, at the end of a paragraph instead of the start.

    Two plies replay legally under almost any reading, so handing them to the
    repairer as if they were a line is worse than handing it nothing: it
    invites a confident answer from evidence that cannot support one.
    """
    text = ("1 Nc5 Rh6 2 Bc5 Rh2+ and this is where the explanation really "
            "begins in earnest with many words 3 Kd4 Rh4+")
    runs = move_runs(text)
    assert len(runs) == 1, [r.describe_pt() for r in runs]
    assert "Kd4" not in runs[0].text


def test_the_run_ends_at_its_last_move_not_at_the_words_after_it():
    run = longest_run("1 Nc5 Rh6 2 Bc5 Rh2+ 3 Kd4 Rh4+ and Black holds on")
    assert run is not None
    assert run.text.endswith("Rh4+"), run.text


@pytest.mark.parametrize("token", ["O-O", "0-0", "O-O-O"])
def test_castling_counts_as_a_move(token):
    text = f"1 e4 e5 2 Nf3 Nc6 3 Bb5 a6 4 Ba4 Nf6 5 {token} Be7 6 Re1 b5"
    run = longest_run(text)
    assert run is not None and token in run.text


def test_a_cipher_slot_keeps_its_place_in_the_sequence():
    """``?h2+`` is a move whose piece is still open, and dropping it would
    splice two half-games together and make every later move illegal."""
    run = longest_run("1 ?c3 Rh6 2 ?c2 ?h2+ 3 Kd2 Rh3 4 ?e3 Rh4 5 Kd4 Rh5")
    assert run is not None
    assert "?h2+" in run.text
    assert run.moves >= 9, run.describe_pt()


def test_results_and_evaluations_belong_to_the_run():
    run = longest_run("1 e4 e5 2 Nf3 Nc6 3 Bb5 a6 4 Ba4 Nf6 5 O-O Be7 1-0")
    assert run is not None and "1-0" in run.text


def test_runs_are_reported_with_their_offsets():
    run = longest_run(PARAGRAPH)
    assert run is not None
    tokens = PARAGRAPH.split()
    assert tokens[run.start] == "Nc5"
    assert run.end - run.start == run.tokens
    assert 0.0 < run.density <= 1.0
    assert "%" in run.describe_pt()


def test_the_notation_language_is_honoured():
    """German analysis is moves too, and the safe default already covers it."""
    german = ("1 e4 e5 2 Sf3 Sc6 3 Lb5 a6 4 La4 Sf6 5 O-O Le7 6 Te1 b5 "
              "7 Lb3 d6 8 c3 O-O")
    run = longest_run(german)
    assert run is not None and run.moves >= 14, (
        run.describe_pt() if run else "nenhuma sequência")


# --------------------------------------------------------------------------- #
# Variations
# --------------------------------------------------------------------------- #


def test_the_trunk_is_taken_and_the_variations_are_not():
    """**Analysis is a tree, and only the trunk starts from the diagram.**

    This was the blocker after the segmenter existed.  On Nunn p140 the longest
    run on the page sits six plies deep inside ``(4...g3 5 Qe5+ transposes)``;
    replayed from the diagram it is illegal by construction, and the repairer
    accepted **zero** moves.  Taking the trunk instead accepted **four of
    four**.
    """
    text = ("1 Qh7+ Kf6 (1...Kg8 2 Qg6+ Kf8 3 Qf6+ Ke8 4 Qe6+ Kd8 5 Qd6+) "
            "2 Qf7+ Kg5 3 Qe7+ Kg4 4 Qe6+ Kf3 5 Qf5+ Ke3")
    runs = move_runs(text)
    assert runs, "a linha principal desapareceu junto com a variante"
    trunk = runs[0]
    assert trunk.text.startswith("Qh7+ Kf6")
    assert "Qg6+" not in trunk.text, "a variante entrou na linha principal"
    assert trunk.moves >= 9, trunk.describe_pt()


def test_the_trunk_is_joined_across_a_variation():
    """After a variation the main line resumes **from the position it left**.

    1 Qh7+ Kf6 (1...Kg8 2 Qg6+) 2 Qf7+ is the contiguous line
    Qh7+ Kf6 Qf7+: the bracket is a side branch, not a gap in the game.
    Letting a long variation cost one gap per token would break the trunk at
    exactly the pages that carry the most analysis.
    """
    text = ("1 Qh7+ Kf6 2 Qf7+ Kg5 "
            "(3 Qg7+ Kh4 4 Qh6+ Kg4 5 Qg6+ Kh3 6 Qh5+ Kg2 7 Qg4+ Kh1) "
            "8 Qe7+ Kg4 9 Qe6+ Kf3 10 Qf5+ Ke3 11 Qe5+")
    runs = move_runs(text)
    assert len(runs) == 1, [r.describe_pt() for r in runs]
    assert "Qg7+" not in runs[0].text
    assert "Qf7+" in runs[0].text and "Qe7+" in runs[0].text


def test_unbalanced_brackets_do_not_swallow_the_page():
    """OCR loses closing brackets.  A depth counter that never comes back down
    would drop every move after the first ``(``."""
    text = ("1 Qh7+ Kf6 (1...Kg8 2 Qg6+ "
            "3 Qf7+ Kg5 4 Qe7+ Kg4 5 Qe6+ Kf3 6 Qf5+ Ke3 7 Qe5+ Kf3")
    assert move_runs(text), "os parênteses desbalanceados engoliram a página"


def test_variations_can_be_kept_when_the_caller_wants_them():
    """The trunk rule serves the replay.  A caller reading the page for the IR
    wants everything, and says so."""
    text = "1 Qh7+ Kf6 (1...Kg8 2 Qg6+ Kf8 3 Qf6+ Ke8 4 Qe6+ Kd8) 2 Qf7+ Kg5"
    with_variations = move_runs(text, main_line_only=False)
    assert with_variations
    assert any("Qg6+" in r.text for r in with_variations)
