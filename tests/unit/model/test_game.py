"""SPEC 5.4 -- the game is a tree, and everything printed around it survives.

The SPEC asks for six things a PGN carries and most importers quietly drop:
variations nested to arbitrary depth, comments *before* and *after* a move, NAGs
``$1``-``$255``, evaluation symbols, clock times, and ``[%cal]`` / ``[%csl]``
arrows and highlights -- plus the full PGN header roster, not just the seven tag
roster.

Losing any of them turns an annotated book into a bare move list, which is the
single most common failure of chess-import tooling. So each is built, walked,
serialised and compared here, and the deep-variation test goes to depth six
rather than the four the brief asks for, because an off-by-one in a recursive
writer shows up one level past where you stopped looking.
"""

from __future__ import annotations

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle
from caissa.core.model import (
    SEVEN_TAG_ROSTER,
    ClockAnnotation,
    ClockKind,
    Color,
    Diagram,
    Document,
    DocumentMetadata,
    EvalAnnotation,
    EvalKind,
    GameHeaders,
    GameRenderOptions,
    GameScore,
    Mark,
    MarkKind,
    MoveNode,
    PgnTag,
    RunProps,
    VariationStyle,
    arrow,
    dumps,
    highlight,
    loads,
    node_from_payload,
    node_to_payload,
    validate,
    walk,
)
from caissa.core.model.game import iter_mainline, iter_move_nodes

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


# --------------------------------------------------------------------------- #
# Headers -- the full roster, not just the seven tags
# --------------------------------------------------------------------------- #


def test_the_seven_tag_roster_is_the_pgn_standard_one():
    assert SEVEN_TAG_ROSTER == ("Event", "Site", "Date", "Round", "White", "Black", "Result")


def test_default_headers_use_the_pgn_placeholders():
    headers = GameHeaders()
    assert headers.event == "?"
    assert headers.date == "????.??.??"
    assert headers.result == "*"


def full_headers() -> GameHeaders:
    """The seven tags plus the supplemental roster a real book carries."""
    return GameHeaders(
        event="Torneio de Candidatos",
        site="Zurique SUI",
        date="1953.09.14",
        round="15",
        white="Smyslov, Vasily",
        black="Reshevsky, Samuel",
        result="1-0",
        extra=(
            PgnTag(name="WhiteElo", value="2680"),
            PgnTag(name="BlackElo", value="2650"),
            PgnTag(name="ECO", value="B99"),
            PgnTag(name="Opening", value="Siciliana Najdorf"),
            PgnTag(name="Variation", value="7.f4 Be7 8.Qf3 Qc7"),
            PgnTag(name="Annotator", value="Bronstein"),
            PgnTag(name="PlyCount", value="83"),
            PgnTag(name="EventDate", value="1953.08.29"),
            PgnTag(name="TimeControl", value="40/9000:20/3600"),
            PgnTag(name="Termination", value="normal"),
            PgnTag(name="SetUp", value="1"),
            PgnTag(name="FEN", value=STARTING_FEN),
            PgnTag(name="Source", value="Zurich 1953, Bronstein"),
            PgnTag(name="UTCDate", value="2026.09.07"),
        ),
    )


def test_headers_expose_the_seven_tags_and_the_extras_uniformly():
    headers = full_headers()
    for name in SEVEN_TAG_ROSTER:
        assert headers.get(name) is not None, name
    assert headers.get("ECO") == "B99"
    assert headers.get("NaoExiste") is None


def test_as_tuples_puts_the_seven_tag_roster_first():
    pairs = full_headers().as_tuples()
    assert [name for name, _value in pairs][:7] == list(SEVEN_TAG_ROSTER)
    assert ("ECO", "B99") in pairs


def test_the_full_header_roster_round_trips():
    score = GameScore(headers=full_headers())
    restored = node_from_payload(node_to_payload(score), GameScore)
    assert restored.headers == score.headers
    assert len(restored.headers.extra) == 14


def test_an_empty_tag_name_is_reported():
    document = _document_with(GameScore(headers=GameHeaders(extra=(PgnTag(name=" ", value="x"),))))
    assert "partida.etiqueta-sem-nome" in {issue.code for issue in validate(document)}


def test_a_duplicate_tag_name_is_reported():
    headers = GameHeaders(
        extra=(PgnTag(name="ECO", value="B99"), PgnTag(name="ECO", value="C42")),
    )
    document = _document_with(GameScore(headers=headers))
    assert "partida.etiqueta-duplicada" in {issue.code for issue in validate(document)}


@pytest.mark.parametrize("result", ["1-0", "0-1", "1/2-1/2", "*"])
def test_the_four_legal_results_are_accepted(result):
    document = _document_with(GameScore(headers=GameHeaders(result=result)))
    assert "partida.resultado-invalido" not in {issue.code for issue in validate(document)}


@pytest.mark.parametrize("result", ["1:0", "won", "0.5-0.5", ""])
def test_an_invalid_result_is_reported(result):
    document = _document_with(GameScore(headers=GameHeaders(result=result)))
    assert "partida.resultado-invalido" in {issue.code for issue in validate(document)}


# --------------------------------------------------------------------------- #
# Nested variations
# --------------------------------------------------------------------------- #


def deep_line(depth: int, *, ply: int = 1) -> MoveNode:
    """A chain of moves whose first child carries a variation at every level."""
    children: tuple[MoveNode, ...] = ()
    if depth > 0:
        children = (
            deep_line(depth - 1, ply=ply + 1),
            MoveNode(
                san="a3",
                ply=ply + 1,
                comment_before=f"alternativa no nivel {depth}",
                nags=(depth,),
            ),
        )
    return MoveNode(san="e4" if ply % 2 else "e5", ply=ply, children=children)


def test_variations_nest_to_depth_six_and_survive_json():
    score = GameScore(children=(deep_line(6),))
    restored = loads(dumps(Document(body=(score,)))).body[0]
    assert restored == score

    node = restored.children[0]
    depth = 0
    while node.main_continuation is not None:
        assert node.variations, f"variation lost at depth {depth}"
        node = node.main_continuation
        depth += 1
    assert depth == 6


def test_the_mainline_is_the_chain_of_first_children():
    score = GameScore(children=(deep_line(4),))
    line = score.mainline()
    assert [node.ply for node in line] == [1, 2, 3, 4, 5]
    assert line == tuple(iter_mainline(score))


def test_move_count_counts_the_whole_tree_not_just_the_mainline():
    score = GameScore(children=(deep_line(4),))
    assert score.move_count() == len(iter_move_nodes(score))
    assert score.move_count() > len(score.mainline())


def test_variations_are_every_child_after_the_first():
    node = deep_line(2)
    assert node.main_continuation is node.children[0]
    assert node.variations == node.children[1:]


def test_a_leaf_move_has_no_continuation_and_no_variations():
    leaf = MoveNode(san="e4")
    assert leaf.main_continuation is None
    assert leaf.variations == ()


def test_walk_reaches_every_move_in_a_deep_tree():
    score = GameScore(children=(deep_line(6),))
    walked = [node for _path, node in walk(score) if isinstance(node, MoveNode)]
    assert len(walked) == score.move_count()


def test_ply_projects_to_move_number_and_colour():
    assert MoveNode(san="e4", ply=1).move_number == 1
    assert MoveNode(san="e4", ply=1).is_black_move is False
    assert MoveNode(san="e5", ply=2).move_number == 1
    assert MoveNode(san="e5", ply=2).is_black_move is True
    assert MoveNode(san="Nf3", ply=3).move_number == 2


# --------------------------------------------------------------------------- #
# Everything printed around a move
# --------------------------------------------------------------------------- #


def annotated_move() -> MoveNode:
    """One move carrying every annotation SPEC 5.4 lists."""
    return MoveNode(
        san="Nf3",
        ply=3,
        position_before=AFTER_E4,
        position_after=STARTING_FEN,
        uci="g1f3",
        nags=(1, 13, 145, 255),
        comment_before="Aqui as brancas tem de escolher.",
        comment_after="Desenvolvendo com ganho de tempo.",
        arrows=(
            arrow("g1", "f3", color=Color.rgb8(0, 128, 0)),
            arrow("f3", "e5"),
        ),
        highlights=(
            highlight("e5", "d4"),
            Mark(kind=MarkKind.CIRCLE, squares=("f7",), color=Color.rgb8(255, 0, 0)),
        ),
        clock=ClockAnnotation(kind=ClockKind.CLOCK, text="1:58:41", seconds=7121.0),
        evaluation=EvalAnnotation(kind=EvalKind.CENTIPAWNS, value=0.34, depth=22, text="+0.34"),
        emphasis=True,
    )


def test_pre_and_post_comments_are_separate_fields():
    move = annotated_move()
    assert move.comment_before.startswith("Aqui")
    assert move.comment_after.startswith("Desenvolvendo")


def test_nags_cover_the_whole_one_to_255_range():
    move = annotated_move()
    assert move.nags == (1, 13, 145, 255)
    restored = node_from_payload(node_to_payload(move), MoveNode)
    assert restored.nags == move.nags


@pytest.mark.parametrize("nag", [0, -1, 256, 1000])
def test_a_nag_outside_one_to_255_is_reported(nag):
    document = _document_with(GameScore(children=(MoveNode(san="e4", nags=(nag,)),)))
    assert "nag.fora-da-faixa" in {issue.code for issue in validate(document)}


def test_cal_arrows_and_csl_highlights_are_first_class_marks():
    """``[%cal Gg1f3]`` and ``[%csl Re5]`` become marks, not comment text."""
    move = annotated_move()
    assert all(mark.kind is MarkKind.ARROW for mark in move.arrows)
    assert {mark.kind for mark in move.highlights} == {MarkKind.SQUARE, MarkKind.CIRCLE}
    assert move.arrows[0].origin == "g1"
    assert move.arrows[0].target == "f3"


def test_clock_and_evaluation_survive_the_round_trip():
    move = annotated_move()
    restored = node_from_payload(node_to_payload(move), MoveNode)
    assert restored.clock == move.clock
    assert restored.evaluation == move.evaluation
    assert restored.clock.seconds == pytest.approx(7121.0)


@pytest.mark.parametrize("kind", list(ClockKind))
def test_every_clock_kind_round_trips(kind):
    annotation = ClockAnnotation(kind=kind, text="0:05:00", seconds=300.0)
    move = MoveNode(san="e4", clock=annotation)
    assert node_from_payload(node_to_payload(move), MoveNode).clock == annotation


@pytest.mark.parametrize("kind", list(EvalKind))
def test_every_evaluation_kind_round_trips(kind):
    annotation = EvalAnnotation(kind=kind, value=-3.0, depth=30, text="#-3")
    move = MoveNode(san="e4", evaluation=annotation)
    assert node_from_payload(node_to_payload(move), MoveNode).evaluation == annotation


def test_an_annotated_move_round_trips_field_by_field():
    move = annotated_move()
    restored = node_from_payload(node_to_payload(move), MoveNode)
    for name in MoveNode.__dataclass_fields__:
        assert getattr(restored, name) == getattr(move, name), name


def test_an_empty_san_is_reported():
    document = _document_with(GameScore(children=(MoveNode(san="  "),)))
    assert "partida.lance-vazio" in {issue.code for issue in validate(document)}


# --------------------------------------------------------------------------- #
# A whole annotated game
# --------------------------------------------------------------------------- #


def annotated_game() -> GameScore:
    """Headers, an initial comment, a deep tree, and render options."""
    return GameScore(
        headers=full_headers(),
        initial_fen=STARTING_FEN,
        variant="standard",
        initial_comment="Uma das partidas decisivas do torneio.",
        children=(annotated_move(), deep_line(5)),
        render=GameRenderOptions(
            language="pt",
            render=MoveRenderStyle.BOTH,
            figurine_set=FigurineSet.BLACK,
            variation_style=VariationStyle.INDENTED,
            show_result=True,
            show_headers=True,
            max_variation_depth=4,
            move_props=RunProps(font_weight=700),
            comment_props=RunProps(italic=True),
            variation_props=RunProps(font_family="Minion Pro"),
        ),
        title="Smyslov -- Reshevsky, Zurique 1953",
        annotator="Bronstein",
    )


def test_a_whole_annotated_game_round_trips_through_the_document_envelope():
    game = annotated_game()
    document = Document(metadata=DocumentMetadata(title="Livro"), body=(game,))
    assert loads(dumps(document)) == document


def test_the_game_result_reads_through_to_the_headers():
    assert annotated_game().result == "1-0"


def test_render_options_are_a_display_decision_carried_by_the_ir():
    render = annotated_game().render
    assert render.language == "pt"
    assert render.render is MoveRenderStyle.BOTH
    assert render.variation_style is VariationStyle.INDENTED
    assert render.max_variation_depth == 4


def test_a_game_score_nested_inside_a_diagram_solution_round_trips():
    diagram = Diagram(fen=STARTING_FEN, stipulation="Mate em 2", solution=annotated_game())
    document = Document(body=(diagram,))
    restored = loads(dumps(document))
    assert restored == document
    assert restored.body[0].solution.headers.white == "Smyslov, Vasily"


def test_move_ids_are_preserved_through_a_deep_round_trip():
    game = annotated_game()
    document = Document(body=(game,))
    before = [node.id for _path, node in walk(document) if isinstance(node, MoveNode)]
    after = [node.id for _path, node in walk(loads(dumps(document))) if isinstance(node, MoveNode)]
    assert after == before
    assert len(before) > 10


def _document_with(score: GameScore) -> Document:
    """Wrap one game score in an otherwise valid document."""
    return Document(
        metadata=DocumentMetadata(title="Teste", language="pt-BR"),
        body=(score,),
    )
