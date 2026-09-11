"""SPEC 5.2's golden rule, made mechanical.

    Nenhum exportador pode *silenciosamente* descartar uma propriedade.

The rule only holds if recording a loss is cheaper than ignoring it, so the
recorder has four verbs and a report. What these tests pin down is that each
verb produces a warning the user can act on: which format, which property,
which node, what was asked for, what was written instead, and why.

A warning with no node attached is legal (a document-level loss) but a warning
with no property is not -- ``property`` is the field the export report groups by
and the one the user searches for when a book comes out wrong.
"""

from __future__ import annotations

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.model import (
    ULID,
    DegradationKind,
    DegradationRecorder,
    DegradationReport,
    DegradationWarning,
    Diagram,
    Text,
)
from caissa.core.model.serialize import decode_value, encode_value


@pytest.fixture
def recorder() -> DegradationRecorder:
    """A recorder aimed at DOCX, the format that loses the most."""
    return DegradationRecorder("docx")


@pytest.fixture
def node() -> Text:
    """A node for a warning to point at."""
    return Text(id=ULID.from_parts(1_700_000_000_000, 7), content="versalete real")


# --------------------------------------------------------------------------- #
# The four verbs
# --------------------------------------------------------------------------- #


def test_unsupported_records_a_property_that_is_simply_gone(recorder, node):
    warning = recorder.unsupported(
        prop="variation_axes",
        node=node,
        path="$.body[0].content[0]",
        original="wght=612.5",
        detail="DOCX embute fontes estaticas",
    )
    assert warning.kind is DegradationKind.UNSUPPORTED
    assert warning.property == "variation_axes"
    assert warning.target_format == "docx"
    assert warning.node_type == "text"
    assert warning.node_id == node.id
    assert warning.path == "$.body[0].content[0]"
    assert warning.original == "wght=612.5"
    assert warning.replacement is None
    assert "DOCX" in warning.message
    assert "variation_axes" in warning.message


def test_approximated_records_what_was_written_instead(recorder, node):
    warning = recorder.approximated(
        prop="letter_spacing",
        node=node,
        original="0.02em",
        replacement="0.2pt",
        detail="DOCX mede tracking em vintimos de ponto",
    )
    assert warning.kind is DegradationKind.APPROXIMATED
    assert warning.original == "0.02em"
    assert warning.replacement == "0.2pt"
    assert "0.02em" in warning.message
    assert "0.2pt" in warning.message


def test_substituted_records_a_different_mechanism_standing_in(recorder, node):
    warning = recorder.substituted(
        prop="small_caps",
        node=node,
        original="real",
        replacement="sintetico",
        detail="a fonte embutida nao traz a caracteristica OpenType 'smcp'",
    )
    assert warning.kind is DegradationKind.SUBSTITUTED
    assert "small_caps" in warning.message
    assert warning.detail.endswith("'smcp'")


def test_rasterised_is_its_own_verb_because_it_is_the_failure_that_matters():
    """A rasterised diagram is exactly what every competing tool produces."""
    recorder = DegradationRecorder("epub")
    diagram = Diagram(fen=STARTING_FEN)
    warning = recorder.rasterised(node=diagram, detail="o leitor nao suporta SVG embutido")
    assert warning.kind is DegradationKind.RASTERISED
    assert warning.property == "vector"
    assert warning.original == "vetorial"
    assert warning.replacement == "raster"
    assert warning.node_type == "diagram"
    assert "nitidez" in warning.message


def test_a_warning_can_name_no_node_at_all(recorder):
    warning = recorder.unsupported(prop="embed_fonts", detail="perfil restrito")
    assert warning.node_id is None
    assert warning.node_type == ""


def test_a_caller_can_record_a_warning_it_built_itself(recorder):
    warning = DegradationWarning(
        target_format="latex",
        kind=DegradationKind.UNSUPPORTED,
        property="emphasis_mark",
        message="mensagem propria",
    )
    assert recorder.record(warning) is warning
    assert recorder.report().warnings == (warning,)


# --------------------------------------------------------------------------- #
# The recorder as a ledger
# --------------------------------------------------------------------------- #


def test_a_fresh_recorder_is_empty_and_falsy(recorder):
    assert len(recorder) == 0
    assert not recorder
    assert recorder.report().is_lossless
    assert recorder.target_format == "docx"


def test_recording_makes_it_truthy(recorder, node):
    recorder.unsupported(prop="shadow", node=node)
    assert recorder
    assert len(recorder) == 1
    assert not recorder.report().is_lossless


def test_warnings_are_kept_in_the_order_they_happened(recorder, node):
    recorder.unsupported(prop="a", node=node)
    recorder.approximated(prop="b", node=node)
    recorder.substituted(prop="c", node=node)
    recorder.rasterised(prop="d", node=node)
    assert [warning.property for warning in recorder.report().warnings] == ["a", "b", "c", "d"]


def test_the_report_is_a_frozen_snapshot(recorder, node):
    recorder.unsupported(prop="a", node=node)
    report = recorder.report()
    recorder.unsupported(prop="b", node=node)
    assert len(report.warnings) == 1, "an old report must not grow behind the caller's back"
    assert len(recorder.report().warnings) == 2


def test_counts_are_grouped_by_property_and_by_kind(recorder, node):
    recorder.unsupported(prop="small_caps", node=node)
    recorder.unsupported(prop="small_caps", node=node)
    recorder.approximated(prop="letter_spacing", node=node)
    report = recorder.report()
    assert report.by_property() == {"small_caps": 2, "letter_spacing": 1}
    assert report.by_kind() == {
        DegradationKind.UNSUPPORTED: 2,
        DegradationKind.APPROXIMATED: 1,
    }


def test_warnings_can_be_pulled_out_one_property_at_a_time(recorder, node):
    recorder.unsupported(prop="small_caps", node=node)
    recorder.approximated(prop="letter_spacing", node=node)
    report = recorder.report()
    assert len(report.of_property("small_caps")) == 1
    assert report.of_property("nao-existe") == ()


def test_the_summary_names_the_format_and_the_count(recorder, node):
    recorder.unsupported(prop="small_caps", node=node)
    summary = recorder.report().summary()
    assert "docx" in summary.lower()
    assert "1" in summary


def test_a_lossless_report_says_so(recorder):
    summary = recorder.report().summary()
    assert summary
    assert DegradationReport(target_format="pdf").is_lossless


def test_a_warning_renders_as_one_readable_line(recorder, node):
    warning = recorder.substituted(
        prop="small_caps",
        node=node,
        path="$.body[2].content[0]",
        original="real",
        replacement="sintetico",
    )
    line = str(warning)
    assert line.startswith("[docx] substituted small_caps em $.body[2].content[0]:")


def test_a_warning_without_a_path_still_renders(recorder, node):
    assert " em " not in str(recorder.unsupported(prop="shadow", node=node))


def test_the_report_renders_as_text(recorder, node):
    recorder.unsupported(prop="shadow", node=node)
    assert str(recorder.report())


# --------------------------------------------------------------------------- #
# Kinds and serialisation
# --------------------------------------------------------------------------- #


def test_the_four_kinds_are_ordered_worst_first():
    """An export report lists what was lost before what was merely approximated."""
    assert [kind.value for kind in DegradationKind] == [
        "unsupported",
        "substituted",
        "approximated",
        "rasterised",
    ]


def test_a_warning_is_a_registered_ir_value_and_round_trips(recorder, node):
    warning = recorder.approximated(
        prop="letter_spacing",
        node=node,
        path="$.body[0]",
        original="0.02em",
        replacement="0.2pt",
        detail="arredondamento",
    )
    assert decode_value(encode_value(warning), DegradationWarning) == warning


@pytest.mark.parametrize("kind", list(DegradationKind))
def test_every_kind_round_trips(kind):
    warning = DegradationWarning(target_format="pdf", kind=kind, property="x")
    assert decode_value(encode_value(warning), DegradationWarning) == warning


# --------------------------------------------------------------------------- #
# What an exporter actually does with it
# --------------------------------------------------------------------------- #


def test_a_realistic_export_pass_produces_a_grouped_ledger():
    """The shape an export report shows the user: what was lost, and where."""
    recorder = DegradationRecorder("docx")
    for index in range(3):
        run = Text(content=f"trecho {index}")
        recorder.substituted(
            prop="small_caps",
            node=run,
            path=f"$.body[{index}].content[0]",
            original="real",
            replacement="sintetico",
        )
    recorder.unsupported(prop="variation_axes", node=Text(content="titulo"))
    recorder.rasterised(node=Diagram(fen=STARTING_FEN), path="$.body[9]")

    report = recorder.report()
    assert not report.is_lossless
    assert report.by_property() == {"small_caps": 3, "variation_axes": 1, "vector": 1}
    assert report.by_kind()[DegradationKind.SUBSTITUTED] == 3
    assert all(warning.target_format == "docx" for warning in report.warnings)
    assert all(warning.message for warning in report.warnings), "every warning is user-facing"
