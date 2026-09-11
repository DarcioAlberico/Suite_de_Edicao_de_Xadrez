"""SPEC 5.3 -- the diagram is a position with provenance, not a picture.

Three things make this node the one the product is built on, and each gets its
own section here:

* the **position**: a validated FEN, an orientation, marks that name real
  squares;
* the **provenance**: which file, which page, which rectangle, at which DPI,
  read by which model at which version -- auditable after the fact;
* the **per-square confidence**: sixty-four floats, one per square, which is
  what lets the UI paint only the doubtful squares amber. That vector is the
  reason 97 % accuracy is usable at all (SPEC 5.3), so its length is checked by
  the validator and its length is checked here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from caissa.core.chess.fen import EMPTY_BOARD_FEN, STARTING_FEN
from caissa.core.model import (
    SQUARE_COUNT,
    BoardTheme,
    CaptionPosition,
    Color,
    CoordinateStyle,
    Diagram,
    DiagramSource,
    DiagramStyle,
    Document,
    FenCandidate,
    GameScore,
    LengthUnit,
    Mark,
    MarkKind,
    MarkLineStyle,
    Measure,
    MoveNode,
    Orientation,
    PiecePlacementStyle,
    Provenance,
    RecognitionPath,
    RecognitionResult,
    Rect,
    Severity,
    SourceKind,
    SquareRepair,
    Text,
    arrow,
    circle,
    highlight,
    node_from_payload,
    node_to_payload,
    validate,
)
from caissa.core.model.marks import SQUARE_NAMES, is_square_name, square_index, square_name

RUY_LOPEZ = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"


def full_diagram() -> Diagram:
    """A diagram with every SPEC 5.3 field populated."""
    return Diagram(
        fen=RUY_LOPEZ,
        orientation=Orientation.BLACK,
        source=DiagramSource(
            kind=SourceKind.PDF_VECTOR,
            path="acervo/aberturas.pdf",
            content_hash="sha256:" + "ab" * 32,
            page_index=41,
            rect=Rect(x=72.0, y=120.5, width=180.0, height=180.0),
            dpi=300.0,
            rotation_degrees=0.0,
            image_hash="sha256:" + "cd" * 32,
            extracted_at=datetime(2026, 9, 7, 10, 30, tzinfo=UTC),
            extractor="pymupdf",
            extractor_version="1.24.9",
        ),
        recognition=RecognitionResult(
            fen=RUY_LOPEZ,
            per_square_confidence=tuple(
                round(0.90 + (index % 11) / 100.0, 4) for index in range(SQUARE_COUNT)
            ),
            overall_confidence=0.9712,
            orientation_confidence=0.999,
            side_to_move_confidence=0.88,
            path=RecognitionPath.NEURAL,
            model_name="caissa-squares",
            model_version="3.1.0",
            model_hash="sha256:" + "ef" * 32,
            recognised_at=datetime(2026, 9, 7, 10, 30, 1, tzinfo=UTC),
            duration_ms=63.5,
            corners=(10.0, 10.0, 190.0, 12.0, 188.0, 190.0, 12.0, 188.0),
            alternatives=(
                FenCandidate(fen=RUY_LOPEZ, score=0.97, legal=True),
                FenCandidate(fen=STARTING_FEN, score=0.02, legal=True),
            ),
            repairs=(
                SquareRepair(
                    square="b5",
                    recognised="Q",
                    repaired="B",
                    reason="dama extra; bispo e a leitura legal",
                    confidence_before=0.51,
                ),
            ),
            warnings=("casa e4 abaixo do limiar",),
        ),
        verified_by_human=True,
        style=DiagramStyle(
            name="Diagrama",
            piece_set="merida",
            piece_font_family="Merida",
            piece_scale=0.92,
            theme=BoardTheme(
                light_square=Color.rgb8(240, 217, 181),
                dark_square=Color.rgb8(181, 136, 99),
                border=Color.gray(0.2),
                arrow=Color.rgb8(255, 170, 0),
            ),
            coordinates=CoordinateStyle(
                placement=PiecePlacementStyle.OUTSIDE,
                files=True,
                ranks=True,
                both_sides=False,
                gap=Measure(value=2.0, unit=LengthUnit.PT),
            ),
            size=Measure(value=160.0, unit=LengthUnit.PT),
            square_size=Measure(value=20.0, unit=LengthUnit.PT),
            margin=Measure(value=4.0, unit=LengthUnit.PT),
            show_side_to_move=True,
            side_to_move_placement=PiecePlacementStyle.OUTSIDE,
            caption_position=CaptionPosition.BELOW,
            shadow=False,
            grid_lines=True,
            keep_with_caption=True,
        ),
        caption=(Text(content="Ruy Lopez, defesa Morphy"),),
        number=12,
        label="diag:ruy-12",
        marks=(
            arrow("b5", "c6", color=Color.rgb8(255, 0, 0)),
            highlight("e4", "e5"),
            circle("f7"),
            Mark(
                kind=MarkKind.LABEL,
                squares=("d4",),
                text="!",
                line_style=MarkLineStyle.DASHED,
                opacity=0.75,
                layer=2,
                filled=True,
            ),
        ),
        side_to_move_indicator=True,
        stipulation="As pretas jogam e igualam",
        solution=GameScore(children=(MoveNode(san="a6", ply=6, position_before=RUY_LOPEZ),)),
        anchor="ancora-diag-12",
        alt_text="Posicao da Ruy Lopez apos 3.Bb5",
        move_context="3.Bb5",
        provenance=Provenance(
            kind=SourceKind.PDF_VECTOR,
            document_path="acervo/aberturas.pdf",
            page_index=41,
            confidence=0.97,
        ),
    )


# --------------------------------------------------------------------------- #
# Shape and round trip
# --------------------------------------------------------------------------- #


def test_every_spec_5_3_field_exists_on_the_node():
    declared = set(Diagram.__dataclass_fields__)
    required = {
        "id",
        "fen",
        "orientation",
        "source",
        "recognition",
        "verified_by_human",
        "style",
        "caption",
        "number",
        "marks",
        "side_to_move_indicator",
        "stipulation",
        "solution",
    }
    assert required <= declared, sorted(required - declared)


def test_a_fully_populated_diagram_round_trips():
    diagram = full_diagram()
    assert node_from_payload(node_to_payload(diagram), Diagram) == diagram


def test_a_fully_populated_diagram_round_trips_field_by_field():
    diagram = full_diagram()
    restored = node_from_payload(node_to_payload(diagram), Diagram)
    for name in Diagram.__dataclass_fields__:
        assert getattr(restored, name) == getattr(diagram, name), name


def test_a_diagram_can_be_minimal():
    """Only the FEN is required; a hand-authored diagram needs nothing else."""
    diagram = Diagram(fen=STARTING_FEN)
    assert diagram.orientation is Orientation.WHITE
    assert diagram.marks == ()
    assert diagram.solution is None
    assert node_from_payload(node_to_payload(diagram), Diagram) == diagram


def test_a_nested_game_score_solution_survives_the_round_trip():
    diagram = full_diagram()
    restored = node_from_payload(node_to_payload(diagram), Diagram)
    assert restored.solution is not None
    assert restored.solution.children[0].san == "a6"
    assert restored.solution.id == diagram.solution.id


# --------------------------------------------------------------------------- #
# Per-square confidence -- SPEC 5.3's central claim
# --------------------------------------------------------------------------- #


def test_square_count_is_sixty_four():
    assert SQUARE_COUNT == 64
    assert len(SQUARE_NAMES) == 64


def test_confidence_vector_is_one_float_per_square():
    diagram = full_diagram()
    assert len(diagram.recognition.per_square_confidence) == SQUARE_COUNT
    assert all(0.0 <= value <= 1.0 for value in diagram.recognition.per_square_confidence)


def test_doubtful_squares_are_exactly_those_below_the_threshold():
    values = [0.99] * SQUARE_COUNT
    values[0] = 0.10
    values[27] = 0.5
    values[63] = 0.8999
    recognition = RecognitionResult(per_square_confidence=tuple(values))
    assert recognition.doubtful_squares(0.9) == (0, 27, 63)
    assert recognition.doubtful_squares(0.05) == ()
    assert len(recognition.doubtful_squares(1.0)) == SQUARE_COUNT


def test_an_empty_confidence_vector_is_allowed_but_reports_nothing_doubtful():
    """A hand-authored diagram was never recognised, so it has no vector."""
    assert RecognitionResult().doubtful_squares() == ()


@pytest.mark.parametrize("length", [0, 63, 65, 128])
def test_the_validator_rejects_a_confidence_vector_of_the_wrong_length(length):
    diagram = Diagram(
        fen=STARTING_FEN,
        recognition=RecognitionResult(per_square_confidence=tuple([0.9] * length)),
    )
    issues = validate(_document_with(diagram))
    codes = {issue.code for issue in issues}
    if length == 0:
        assert "reconhecimento.confianca-tamanho" not in codes, "empty means never recognised"
    else:
        assert "reconhecimento.confianca-tamanho" in codes


@pytest.mark.parametrize("value", [-0.01, 1.01, 2.0, -5.0])
def test_the_validator_rejects_confidences_outside_zero_to_one(value):
    values = [0.9] * SQUARE_COUNT
    values[7] = value
    diagram = Diagram(
        fen=STARTING_FEN,
        recognition=RecognitionResult(per_square_confidence=tuple(values)),
    )
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "reconhecimento.confianca-faixa" in codes


def test_the_validator_wants_four_corner_points_or_none():
    diagram = Diagram(
        fen=STARTING_FEN,
        recognition=RecognitionResult(corners=(1.0, 2.0, 3.0)),
    )
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "reconhecimento.cantos" in codes


def test_a_repair_must_name_a_real_square():
    diagram = Diagram(
        fen=STARTING_FEN,
        recognition=RecognitionResult(
            repairs=(SquareRepair(square="j9", recognised="Q", repaired="B"),),
        ),
    )
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "reconhecimento.reparo-casa-invalida" in codes


# --------------------------------------------------------------------------- #
# FEN validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fen",
    [
        "",
        "   ",
        "not a fen at all",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNRR w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
        "rnbqkbnr/pppppppp/44/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    ],
)
def test_the_validator_rejects_a_malformed_fen(fen):
    codes = {issue.code for issue in validate(_document_with(Diagram(fen=fen)))}
    assert codes & {"fen.invalida", "fen.ausente"}, f"{fen!r} passed validation"


def test_the_validator_reports_an_illegal_position_separately_from_a_malformed_one():
    two_white_kings = "4k3/8/8/8/8/8/8/K3K3 w - - 0 1"
    issues = validate(_document_with(Diagram(fen=two_white_kings)))
    codes = {issue.code for issue in issues}
    assert "fen.invalida" not in codes, "structurally it is a fine FEN"
    assert "fen.posicao-ilegal" in codes


def test_a_valid_fen_produces_no_fen_issue():
    codes = {issue.code for issue in validate(_document_with(Diagram(fen=STARTING_FEN)))}
    assert not {code for code in codes if code.startswith("fen.")}


def test_an_inline_diagram_is_validated_the_same_way():
    from caissa.core.model import InlineDiagram, Paragraph

    document = Document(body=(Paragraph(content=(InlineDiagram(fen="lixo"),)),))
    codes = {issue.code for issue in validate(document)}
    assert "fen.invalida" in codes


# --------------------------------------------------------------------------- #
# Marks: arrows, highlights, circles
# --------------------------------------------------------------------------- #


def test_the_three_helpers_build_the_marks_the_spec_names():
    a = arrow("e2", "e4")
    h = highlight("d4", "d5")
    c = circle("f6")
    assert (a.kind, a.squares, a.origin, a.target) == (MarkKind.ARROW, ("e2", "e4"), "e2", "e4")
    assert (h.kind, h.squares) == (MarkKind.SQUARE, ("d4", "d5"))
    assert (c.kind, c.squares) == (MarkKind.CIRCLE, ("f6",))


def test_origin_and_target_are_the_first_and_last_square():
    """For a one-square mark both ends are that square; for an arrow they differ."""
    assert circle("f6").origin == circle("f6").target == "f6"
    assert Mark(kind=MarkKind.SQUARE).origin is None
    assert Mark(kind=MarkKind.SQUARE).target is None


def test_marks_round_trip_inside_a_diagram():
    diagram = full_diagram()
    restored = node_from_payload(node_to_payload(diagram), Diagram)
    assert restored.marks == diagram.marks
    assert {mark.kind for mark in restored.marks} == {
        MarkKind.ARROW,
        MarkKind.SQUARE,
        MarkKind.CIRCLE,
        MarkKind.LABEL,
    }


@pytest.mark.parametrize("squares", [(), ("e2",), ("e2", "e4", "e5")])
def test_an_arrow_must_name_exactly_two_squares(squares):
    diagram = Diagram(fen=STARTING_FEN, marks=(Mark(kind=MarkKind.ARROW, squares=squares),))
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "marca.aridade" in codes or "marca.casa-invalida" in codes


def test_a_mark_naming_a_square_off_the_board_is_reported():
    diagram = Diagram(fen=STARTING_FEN, marks=(Mark(kind=MarkKind.CIRCLE, squares=("j9",)),))
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "marca.casa-invalida" in codes


def test_a_label_mark_without_text_is_reported():
    diagram = Diagram(fen=STARTING_FEN, marks=(Mark(kind=MarkKind.LABEL, squares=("d4",)),))
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "marca.rotulo-vazio" in codes


def test_mark_opacity_outside_zero_to_one_is_reported():
    diagram = Diagram(
        fen=STARTING_FEN,
        marks=(Mark(kind=MarkKind.CIRCLE, squares=("d4",), opacity=1.5),),
    )
    codes = {issue.code for issue in validate(_document_with(diagram))}
    assert "marca.opacidade-fora-da-faixa" in codes


# --------------------------------------------------------------------------- #
# Square naming
# --------------------------------------------------------------------------- #


def test_square_names_run_a1_to_h8_in_index_order():
    assert SQUARE_NAMES[0] == "a1"
    assert SQUARE_NAMES[7] == "h1"
    assert SQUARE_NAMES[56] == "a8"
    assert SQUARE_NAMES[63] == "h8"


def test_square_index_and_name_are_inverse():
    for index, name in enumerate(SQUARE_NAMES):
        assert square_index(name) == index
        assert square_name(index) == name


@pytest.mark.parametrize("bad", ["", "a", "9", "i4", "a9", "A1", "e44"])
def test_is_square_name_rejects_non_squares(bad):
    assert not is_square_name(bad)


@pytest.mark.parametrize("index", [-1, 64, 999])
def test_square_name_refuses_an_index_off_the_board(index):
    with pytest.raises(ValueError, match="faixa"):
        square_name(index)


def test_square_index_refuses_a_non_square():
    with pytest.raises(ValueError, match="casa"):
        square_index("j9")


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #


def test_provenance_records_the_whole_audit_trail():
    diagram = full_diagram()
    source = diagram.source
    assert source.path == "acervo/aberturas.pdf"
    assert source.page_index == 41
    assert source.rect == Rect(x=72.0, y=120.5, width=180.0, height=180.0)
    assert source.dpi == 300.0
    assert source.extracted_at == datetime(2026, 9, 7, 10, 30, tzinfo=UTC)


def test_recognition_records_which_model_read_the_board():
    recognition = full_diagram().recognition
    assert recognition.model_name == "caissa-squares"
    assert recognition.model_version == "3.1.0"
    assert recognition.model_hash.startswith("sha256:")
    assert recognition.path is RecognitionPath.NEURAL
    assert recognition.recognised_at is not None


def test_rect_derives_its_far_edges_and_area():
    rect = Rect(x=10.0, y=20.0, width=30.0, height=40.0)
    assert rect.right == 40.0
    assert rect.bottom == 60.0
    assert rect.area == 1200.0


def test_provenance_round_trips_on_any_node():
    text = Text(
        content="lido do PDF",
        provenance=Provenance(
            kind=SourceKind.PDF_TEXT_LAYER,
            document_path="a.pdf",
            page_index=3,
            confidence=0.42,
            out_of_model=True,
            note="baixa confianca",
        ),
    )
    assert node_from_payload(node_to_payload(text), Text) == text


# --------------------------------------------------------------------------- #
# Numbering and accessibility
# --------------------------------------------------------------------------- #


def test_duplicate_diagram_numbers_are_reported():
    document = Document(
        body=(
            Diagram(fen=STARTING_FEN, number=1, alt_text="a"),
            Diagram(fen=EMPTY_BOARD_FEN, number=1, alt_text="b"),
        ),
    )
    codes = [issue.code for issue in validate(document)]
    assert "diagrama.numero-duplicado" in codes


def test_a_diagram_without_alt_text_is_flagged_as_an_accessibility_gap():
    issues = validate(_document_with(Diagram(fen=STARTING_FEN)))
    match = [issue for issue in issues if issue.code == "diagrama.sem-texto-alternativo"]
    assert match
    assert match[0].severity is Severity.WARNING


def _document_with(diagram: Diagram) -> Document:
    """Wrap one diagram in an otherwise valid document."""
    from caissa.core.model import DocumentMetadata

    return Document(
        metadata=DocumentMetadata(title="Teste", language="pt-BR"),
        body=(diagram,),
    )
