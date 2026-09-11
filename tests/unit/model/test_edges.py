"""The corners the main modules do not reach.

Each case here is a real behaviour that the obvious tests miss: a rank of the
validator nobody thinks to trip, a rendering branch that only fires on a report
with findings, the ULID entropy counter overflowing inside one millisecond.
They are grouped here rather than scattered so the intent of each main module
stays legible.
"""

from __future__ import annotations

import contextlib
import dataclasses
import threading
import time
from datetime import datetime
from unittest import mock

import pytest

from caissa.core.chess.fen import STARTING_FEN, position_problems
from caissa.core.chess.notation_tables import (
    NotationError,
    PieceType,
    from_language,
    piece_for_letter,
)
from caissa.core.model import (
    ULID,
    ChangeKind,
    Color,
    Diagram,
    DiagramStyle,
    Document,
    DocumentMetadata,
    GameScore,
    Heading,
    Mark,
    MarkKind,
    Measure,
    MoveNode,
    Paragraph,
    ParagraphProps,
    ParagraphStyle,
    RecognitionResult,
    RunProps,
    StyleSheet,
    Transformer,
    dumps,
    loads,
    new_ulid,
    resolve_paragraph_props,
    semantic_diff,
    validate,
)
from caissa.core.model.diff import DiffReport
from caissa.core.model.props import _merge_props
from caissa.core.model.reflect import field_defaults
from caissa.core.model.serialize import SerializationError, decode_value
from caissa.core.model.styles import _MISSING
from caissa.core.model.visitor import NodePath


def document(*blocks, **kwargs) -> Document:
    """A valid-apart-from-the-contents document."""
    kwargs.setdefault("metadata", DocumentMetadata(title="Teste", language="pt-BR"))
    return Document(body=tuple(blocks), **kwargs)


def codes(doc: Document) -> set[str]:
    """The set of issue codes for a document."""
    return {issue.code for issue in validate(doc)}


# --------------------------------------------------------------------------- #
# FEN
# --------------------------------------------------------------------------- #


def test_too_many_black_pieces_is_reported():
    seventeen_black = "4k3/qqqqqqqq/qqqqqqqq/qqq5/8/8/8/4K3 w - - 0 1"
    assert any("pecas pretas" in problem for problem in position_problems(seventeen_black))


# --------------------------------------------------------------------------- #
# Notation
# --------------------------------------------------------------------------- #


def test_a_figurine_glyph_names_its_piece_in_any_language():
    assert piece_for_letter("♞", "pt") is PieceType.KNIGHT
    assert piece_for_letter("♔", "de") is PieceType.KING


@pytest.mark.parametrize("token", ["e8=Z", "e8(Z)", "e8=", "e8()"])
def test_a_promotion_to_something_that_is_not_a_piece_is_refused(token):
    with pytest.raises(NotationError):
        from_language(token, "en")


def test_a_bare_letter_after_a_digit_is_only_read_as_a_promotion_when_it_is_one():
    assert from_language("e8Q", "en") == "e8=Q"
    with pytest.raises(NotationError):
        from_language("e8Z", "en")


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def _restored_id_state():
    """Save and restore the module-level monotonic counters."""
    from caissa.core.model import ids

    with ids._MONOTONIC_LOCK:
        saved = (ids._last_timestamp_ms, ids._last_randomness)
    try:
        yield ids
    finally:
        with ids._MONOTONIC_LOCK:
            ids._last_timestamp_ms, ids._last_randomness = saved


def test_the_entropy_counter_rolls_over_inside_one_millisecond_without_repeating():
    """Regression: borrowing a millisecond must not un-borrow it on the next call.

    The overflow branch bumps the timestamp forward to keep ordering. Before the
    fix, the following call read the real clock again -- still in the *previous*
    millisecond -- and minted an id that sorted before the one just issued.
    """
    with _restored_id_state() as ids:
        with ids._MONOTONIC_LOCK:
            ids._last_timestamp_ms = int(time.time() * 1000.0)
            ids._last_randomness = (1 << 80) - 1
        minted = [new_ulid() for _ in range(5)]
    assert minted == sorted(minted), "monotonicity broke after the rollover"
    assert len(set(minted)) == len(minted)


def test_a_backwards_clock_step_does_not_reorder_ids():
    """Regression: an NTP correction or a resumed VM must not rewind identity.

    ``ids`` promises "strictly greater than every identifier minted earlier by
    this process". A clock that steps backwards used to break that silently,
    which would reorder a diff and, worse, make it non-reproducible.
    """
    base = int(time.time() * 1000.0)
    clock = [base, base - 5, base - 5, base - 4, base + 1]
    with (
        _restored_id_state() as ids,
        mock.patch.object(ids.time, "time", side_effect=[value / 1000.0 for value in clock]),
    ):
        minted = [new_ulid() for _ in clock]
    assert minted == sorted(minted), "a backwards clock reordered the ids"
    assert len(set(minted)) == len(minted)


def test_the_lock_is_a_real_lock():
    from caissa.core.model import ids

    assert isinstance(ids._MONOTONIC_LOCK, type(threading.Lock()))


# --------------------------------------------------------------------------- #
# Colour and property merging
# --------------------------------------------------------------------------- #


def test_a_grey_converts_to_rgb_by_repeating_its_level():
    assert Color.gray(0.25).to_rgb_tuple() == pytest.approx((0.25, 0.25, 0.25))


def test_merging_a_record_with_itself_short_circuits():
    props = RunProps(italic=True)
    assert _merge_props(props, props) is props


def test_field_defaults_refuses_a_non_dataclass():
    with pytest.raises(TypeError, match="nao e uma dataclass"):
        field_defaults(str)


def test_a_field_declared_with_a_tuple_factory_counts_as_defaulting_to_empty():
    """No node spells it this way today; the codec must handle it when one does."""

    @dataclasses.dataclass(frozen=True)
    class Future:
        items: tuple[str, ...] = dataclasses.field(default_factory=tuple)

    assert field_defaults(Future) == {"items": ()}


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def test_a_datetime_field_refuses_a_number():
    with pytest.raises(SerializationError, match="datetime deve ser texto"):
        decode_value(7, datetime)


def test_a_bytes_field_refuses_a_number():
    with pytest.raises(SerializationError, match="esperado texto base64"):
        decode_value(7, bytes)


def test_an_untyped_field_ignores_a_non_string_type_key():
    """A hand-edited file with ``"type": 7`` is data, not a tagged node."""
    assert decode_value({"type": 7, "outro": 1}, object) == {"type": 7, "outro": 1}


def test_a_dataclass_payload_without_a_tag_still_decodes_against_its_annotation():
    """Hand-written payloads and clipboard fragments omit the tag; that is fine."""
    assert decode_value({"value": 11.0, "unit": "pt"}, Measure) == Measure.points(11.0)


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #


def test_inherited_run_properties_reach_a_paragraphs_runs():
    """A ``Group`` hands its character baseline down to the paragraphs inside."""
    sheet = StyleSheet(paragraph_styles=(ParagraphStyle(name="Corpo"),))
    resolved = resolve_paragraph_props(
        sheet,
        ParagraphProps(style="Corpo"),
        inherited_run=RunProps(font_family="DoGrupo"),
    )
    assert resolved.run.font_family == "DoGrupo"


def test_the_missing_style_sentinel_names_itself():
    assert repr(_MISSING) == "<missing style>"


# --------------------------------------------------------------------------- #
# Diff rendering
# --------------------------------------------------------------------------- #


def test_an_added_entry_renders_without_a_field():
    left = Document(id=_ulid(1))
    right = Document(id=_ulid(1), body=(Paragraph(id=_ulid(2)),))
    entry = semantic_diff(left, right).of_kind(ChangeKind.ADDED)[0]
    assert str(entry) == "added paragraph $.body[0]"


def test_a_removed_entry_renders_the_node_it_lost():
    left = Document(id=_ulid(1), body=(Paragraph(id=_ulid(2)),))
    right = Document(id=_ulid(1))
    entry = semantic_diff(left, right).of_kind(ChangeKind.REMOVED)[0]
    assert str(entry) == "removed paragraph $.body[0]"
    assert entry.before.startswith("<paragraph 01")


def test_the_summary_of_a_report_with_findings_lists_the_counts():
    left = Document(id=_ulid(1), body=(Paragraph(id=_ulid(2)),))
    right = Document(id=_ulid(1))
    summary = semantic_diff(left, right).summary()
    assert "Fidelidade" in summary
    assert "removed" in summary


def test_an_empty_report_is_perfectly_faithful():
    """Defensive: nothing compared means nothing lost."""
    assert DiffReport().fidelity == 1.0


def test_a_change_in_child_count_is_reported_on_the_parent():
    left = Document(id=_ulid(1), body=(Paragraph(id=_ulid(2)), Paragraph(id=_ulid(3))))
    right = Document(id=_ulid(1), body=(Paragraph(id=_ulid(2)),))
    entry = next(
        item
        for item in semantic_diff(left, right).of_kind(ChangeKind.CHANGED)
        if item.field == "body"
    )
    assert entry.before == "2 no(s)"
    assert entry.after == "1 no(s)"


def test_an_optional_child_appearing_is_reported_as_a_child_count_change():
    """``None`` on one side and a node on the other: zero children became one."""
    left = Document(id=_ulid(1), body=(Diagram(id=_ulid(2), fen=STARTING_FEN),))
    right = Document(
        id=_ulid(1),
        body=(Diagram(id=_ulid(2), fen=STARTING_FEN, solution=GameScore(id=_ulid(3))),),
    )
    entry = next(
        item
        for item in semantic_diff(left, right).of_kind(ChangeKind.CHANGED)
        if item.field == "solution"
    )
    assert entry.before == "0 no(s)"
    assert entry.after == "1 no(s)"


# --------------------------------------------------------------------------- #
# Transformer
# --------------------------------------------------------------------------- #


def test_a_single_valued_child_can_be_replaced_by_one_node():
    diagram = Diagram(fen=STARTING_FEN, solution=GameScore(title="antes"))
    doc = Document(body=(diagram,))

    class Rename(Transformer):
        def visit_game_score(self, node, path):
            assert str(path) == "$.body[0].solution"
            return GameScore(id=node.id, title="depois")

    assert Rename().transform(doc).body[0].solution.title == "depois"


# --------------------------------------------------------------------------- #
# Validation corners
# --------------------------------------------------------------------------- #


def test_a_block_level_anchor_registers_as_a_link_destination():
    """``Heading.anchor`` is an anchor too, not only the ``Anchor`` node."""
    from caissa.core.model import Link, LinkKind, Text

    doc = document(
        Heading(level=1, content=(Text(content="Cap"),), anchor="cap-1"),
        Paragraph(content=(Link(target="#cap-1", kind=LinkKind.INTERNAL),)),
    )
    assert "link.ancora-inexistente" not in codes(doc)


def test_a_duplicate_block_level_anchor_is_reported():
    from caissa.core.model import Text

    doc = document(
        Heading(level=1, content=(Text(content="a"),), anchor="dup"),
        Heading(level=1, content=(Text(content="b"),), anchor="dup"),
    )
    assert "ancora.duplicada" in codes(doc)


def test_a_diagram_style_object_naming_an_undefined_style_is_reported():
    doc = document(
        Diagram(fen=STARTING_FEN, alt_text="x", style=DiagramStyle(name="Fantasma")),
    )
    assert "estilo.nao-resolvido" in codes(doc)


@pytest.mark.parametrize("node_factory", ["table", "inline_diagram"])
def test_a_node_naming_a_style_by_string_is_checked(node_factory):
    """``Table.style`` and ``InlineDiagram.style`` name a style by plain string."""
    from caissa.core.model import InlineDiagram, Table, TableCell, TableColumn, TableRow

    if node_factory == "table":
        node = Table(
            columns=(TableColumn(),),
            rows=(TableRow(cells=(TableCell(),)),),
            style="Fantasma",
        )
        doc = document(node)
    else:
        doc = document(Paragraph(content=(InlineDiagram(fen=STARTING_FEN, style="Fantasma"),)))
    assert "estilo.nao-resolvido" in codes(doc)


def test_a_defined_diagram_style_resolves():
    from caissa.core.model import DiagramStyleDef

    doc = document(
        Diagram(fen=STARTING_FEN, alt_text="x", style=DiagramStyle(name="Diagrama")),
        styles=StyleSheet(diagram_styles=(DiagramStyleDef(name="Diagrama"),)),
    )
    assert "estilo.nao-resolvido" not in codes(doc)


@pytest.mark.parametrize("alpha", [-0.5, 1.5])
def test_a_colour_alpha_outside_zero_to_one_is_reported(alpha):
    from caissa.core.model import Text

    colour = Color.rgb(0.1, 0.2, 0.3, alpha)
    doc = document(Paragraph(content=(Text(content="x", props=RunProps(color=colour)),)))
    assert "cor.opacidade-fora-da-faixa" in codes(doc)


def test_a_non_arrow_mark_with_no_squares_is_reported():
    diagram = Diagram(
        fen=STARTING_FEN,
        alt_text="x",
        marks=(Mark(kind=MarkKind.CIRCLE, squares=()),),
    )
    assert "marca.aridade" in codes(document(diagram))


@pytest.mark.parametrize(
    "field_name",
    ["overall_confidence", "orientation_confidence", "side_to_move_confidence"],
)
def test_a_scalar_confidence_outside_zero_to_one_is_reported(field_name):
    recognition = RecognitionResult(**{field_name: 1.5})
    diagram = Diagram(fen=STARTING_FEN, alt_text="x", recognition=recognition)
    assert "reconhecimento.confianca-faixa" in codes(document(diagram))


def test_the_fen_the_recogniser_produced_is_validated_too():
    """``recognition.fen`` is what the model *read*; a broken one is a real defect."""
    diagram = Diagram(
        fen=STARTING_FEN,
        alt_text="x",
        recognition=RecognitionResult(fen="lixo"),
    )
    assert "fen.invalida" in codes(document(diagram))


def test_a_move_node_with_a_negative_ply_is_reported():
    doc = document(GameScore(children=(MoveNode(san="e4", ply=-3),)))
    assert "lance.ply-negativo" in codes(doc)


def test_a_move_node_position_after_is_validated():
    doc = document(GameScore(children=(MoveNode(san="e4", position_after="lixo"),)))
    assert "fen.invalida" in codes(doc)


def test_a_game_initial_fen_is_validated_for_legality_too():
    doc = document(GameScore(initial_fen="4k3/8/8/8/8/8/8/K3K3 w - - 0 1"))
    assert "fen.posicao-ilegal" in codes(doc)


def test_a_game_with_a_legal_initial_fen_is_clean():
    doc = document(GameScore(initial_fen=STARTING_FEN))
    assert not {code for code in codes(doc) if code.startswith("fen.")}


def test_move_positions_are_checked_for_structure_but_not_for_legality():
    """A midgame FEN is structural only: a study's position may be "illegal"."""
    two_white_kings = "4k3/8/8/8/8/8/8/K3K3 w - - 0 1"
    doc = document(
        GameScore(
            children=(
                MoveNode(san="e4", ply=1, position_before=STARTING_FEN),
                MoveNode(san="e5", ply=2, position_before=two_white_kings),
            ),
        ),
    )
    found = codes(doc)
    assert "fen.invalida" not in found
    assert "fen.posicao-ilegal" not in found, "legality is only enforced on diagrams"


# --------------------------------------------------------------------------- #
# End to end
# --------------------------------------------------------------------------- #


def test_a_validated_document_still_round_trips():
    """Validation and serialisation must agree about what a document is."""
    doc = document(
        Heading(level=1, content=(), anchor="cap-1"),
        Diagram(fen=STARTING_FEN, alt_text="x"),
    )
    restored = loads(dumps(doc))
    assert restored == doc
    assert [issue.code for issue in validate(restored)] == [issue.code for issue in validate(doc)]


def _ulid(n: int) -> ULID:
    """A deterministic id."""
    return ULID.from_parts(1_700_000_000_000 + n, n)


def test_node_path_helpers_are_consistent():
    path = NodePath().child("body", 0)
    assert path.depth == 1
    assert str(path.child("content")) == "$.body[0].content"
