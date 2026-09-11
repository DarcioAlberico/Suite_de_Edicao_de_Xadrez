"""The codec's edges: what it refuses, and what it must never silently drop.

The bulk round trip lives in ``test_roundtrip_corpus``. This module covers the
parts a ten-thousand-node corpus cannot reach: malformed payloads, the
default-omission optimisation, unions, and the refusals that exist so a
corrupted file fails loudly instead of loading as something subtly wrong.

The default-omission tests matter more than they look. Omitting a field equal to
its declared default is what shrinks a book by an order of magnitude, and it is
also the single easiest place to lose data: omit a field whose default the
decoder restores differently and the loss is invisible until a reader complains.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.model import (
    ULID,
    Color,
    Diagram,
    Document,
    DocumentMetadata,
    GameScore,
    Heading,
    IRTypeError,
    LengthUnit,
    Measure,
    MoveNode,
    Paragraph,
    Provenance,
    RunProps,
    SerializationError,
    SourceKind,
    Strong,
    Text,
    dumps,
    loads,
    node_from_payload,
    node_to_payload,
)
from caissa.core.model.serialize import (
    TYPE_KEY,
    decode_value,
    document_to_payload,
    encode_value,
)

# --------------------------------------------------------------------------- #
# Self-describing payloads
# --------------------------------------------------------------------------- #


def test_every_dataclass_writes_its_registry_tag():
    payload = node_to_payload(Paragraph(content=(Text(content="x"),)))
    assert payload[TYPE_KEY] == "paragraph"
    assert payload["content"][0][TYPE_KEY] == "text"


def test_the_tag_is_what_lets_a_union_field_decode_without_guessing():
    """``body`` holds ``Block``; only the tag says which block."""
    document = Document(body=(Heading(level=2), Paragraph(), Diagram(fen=STARTING_FEN)))
    restored = loads(dumps(document))
    assert [block.node_type for block in restored.body] == ["heading", "paragraph", "diagram"]


def test_a_tag_that_does_not_belong_to_the_union_is_refused():
    payload = document_to_payload(Document(body=(Paragraph(),)))
    payload["document"]["body"][0][TYPE_KEY] = "run_props"
    with pytest.raises(SerializationError, match=r"nao pertence a|nao e compativel"):
        loads(json.dumps(payload))


def test_an_unknown_tag_is_refused():
    payload = node_to_payload(Paragraph())
    payload[TYPE_KEY] = "nao_existe"
    with pytest.raises(IRTypeError, match="tipo de no desconhecido"):
        node_from_payload(payload, Paragraph)


def test_an_unknown_field_is_refused_rather_than_ignored():
    """Ignoring it would let a newer file load as a silently smaller document."""
    payload = node_to_payload(Text(content="x"))
    payload["campo_do_futuro"] = 1
    with pytest.raises(SerializationError, match="campos desconhecidos"):
        node_from_payload(payload, Text)


def test_a_decoding_error_names_the_class_and_the_field():
    payload = node_to_payload(Heading(level=2))
    payload["level"] = "dois"
    with pytest.raises(SerializationError, match=r"Heading\.level"):
        node_from_payload(payload, Heading)


# --------------------------------------------------------------------------- #
# Default omission
# --------------------------------------------------------------------------- #


def test_a_field_equal_to_its_default_is_omitted():
    payload = node_to_payload(Text(content="x"))
    assert "props" not in payload, "an empty RunProps is the default"
    assert "provenance" not in payload
    assert payload["content"] == "x"


def test_an_identity_field_is_never_omitted():
    """``id`` has a factory that answers differently every call, so it must be written."""
    assert "id" in node_to_payload(Text(content="x"))
    assert "id" in node_to_payload(Text(content="x"), omit_defaults=False)


def test_omission_is_lossless_for_every_field_of_a_rich_node():
    node = Text(
        content="x",
        props=RunProps(italic=True),
        provenance=Provenance(kind=SourceKind.OCR, confidence=0.5),
    )
    compact = node_from_payload(node_to_payload(node), Text)
    verbose = node_from_payload(node_to_payload(node, omit_defaults=False), Text)
    assert compact == verbose == node


def test_omission_actually_shrinks_the_payload():
    document = Document(body=tuple(Paragraph(content=(Text(content="x"),)) for _ in range(50)))
    assert len(dumps(document)) < len(dumps(document, omit_defaults=False)) / 2


def test_a_value_that_merely_compares_equal_to_the_default_is_still_written():
    """``False == 0`` in Python; the codec omits only on an exact type match."""
    from caissa.core.model import Table

    assert "header_row_count" not in node_to_payload(Table(header_row_count=0))
    payload = node_to_payload(Table(header_row_count=False))
    assert payload["header_row_count"] is False, "a bool is not the int default"


def test_a_field_differing_from_its_default_is_always_written():
    assert node_to_payload(Heading(level=4))["level"] == 4
    assert "level" not in node_to_payload(Heading(level=1)), "1 is the declared default"


# --------------------------------------------------------------------------- #
# Leaf types
# --------------------------------------------------------------------------- #


def test_a_ulid_is_written_as_its_canonical_string():
    node = Text(id=ULID.from_parts(1_700_000_000_000, 42), content="x")
    payload = node_to_payload(node)
    assert isinstance(payload["id"], str)
    assert len(payload["id"]) == 26
    assert node_from_payload(payload, Text).id == node.id


def test_a_datetime_is_written_as_iso_8601_and_keeps_its_zone():
    moment = datetime(2026, 9, 7, 14, 30, 5, 123456, tzinfo=UTC)
    node = Text(content="x", provenance=Provenance(extracted_at=moment))
    payload = node_to_payload(node)
    assert payload["provenance"]["extracted_at"].startswith("2026-09-07T14:30:05")
    assert node_from_payload(payload, Text).provenance.extracted_at == moment


def test_a_naive_datetime_survives_too():
    moment = datetime(2026, 9, 7, 14, 30)  # noqa: DTZ001 - a naive value is the case
    node = Text(content="x", provenance=Provenance(extracted_at=moment))
    assert node_from_payload(node_to_payload(node), Text).provenance.extracted_at == moment


def test_an_enum_is_written_as_its_value():
    payload = node_to_payload(Text(content="x", provenance=Provenance(kind=SourceKind.OCR)))
    assert payload["provenance"]["kind"] == "ocr"


def test_an_unknown_enum_value_is_refused():
    payload = node_to_payload(Text(content="x", provenance=Provenance(kind=SourceKind.OCR)))
    payload["provenance"]["kind"] = "telepatia"
    with pytest.raises(SerializationError, match="nao pertence a SourceKind"):
        node_from_payload(payload, Text)


def test_a_tuple_of_floats_survives_exactly():
    values = tuple(index / 7.0 for index in range(64))
    node = Diagram(fen=STARTING_FEN)
    from caissa.core.model import RecognitionResult

    node = Diagram(fen=STARTING_FEN, recognition=RecognitionResult(per_square_confidence=values))
    restored = node_from_payload(node_to_payload(node), Diagram)
    assert restored.recognition.per_square_confidence == values


def test_an_int_where_a_float_is_declared_is_widened():
    payload = node_to_payload(Provenance(dpi=300.0))
    payload["dpi"] = 300
    assert decode_value(payload, Provenance).dpi == 300.0


def test_a_bool_is_not_accepted_where_an_int_is_declared():
    payload = node_to_payload(Heading(level=2))
    payload["level"] = True
    with pytest.raises(SerializationError, match="esperado inteiro"):
        node_from_payload(payload, Heading)


@pytest.mark.parametrize(
    ("value", "annotation", "fragment"),
    [
        (1, str, "esperado texto"),
        ("x", int, "esperado inteiro"),
        ("x", float, "esperado numero"),
        (1, bool, "esperado booleano"),
        ("nao-e-uma-data", datetime, "ISO 8601"),
        (7, ULID, "ULID deve ser texto"),
        ("nao-e-um-objeto", RunProps, "esperado um objeto"),
        (7, tuple[str, ...], "esperado uma lista"),
    ],
)
def test_a_value_of_the_wrong_shape_is_refused(value, annotation, fragment):
    with pytest.raises(SerializationError, match=fragment):
        decode_value(value, annotation)


def test_a_type_the_ir_does_not_use_is_refused_at_encode_time():
    with pytest.raises(SerializationError, match="tipo nao serializavel"):
        encode_value({1, 2, 3}.__iter__())


def test_null_is_refused_for_a_field_that_does_not_admit_it():
    with pytest.raises(SerializationError, match="null nao e valor valido"):
        decode_value(None, int | str)


# --------------------------------------------------------------------------- #
# Envelope
# --------------------------------------------------------------------------- #


def test_loads_refuses_text_that_is_not_json():
    with pytest.raises(SerializationError, match="JSON invalido"):
        loads("{isto nao e json")


def test_loads_refuses_a_json_array_at_the_root():
    with pytest.raises(SerializationError, match="esperado um objeto JSON"):
        loads("[1, 2, 3]")


def test_dumps_writes_utf8_without_escapes():
    document = Document(body=(Paragraph(content=(Text(content="peão çãí ♞"),)),))
    text = dumps(document)
    assert "peão" in text
    assert "♞" in text
    assert loads(text) == document


def test_indent_is_only_a_presentation_choice():
    document = Document(body=(Paragraph(content=(Text(content="x"),)),))
    assert loads(dumps(document, indent=2)) == loads(dumps(document))
    assert "\n" in dumps(document, indent=2)
    assert "\n" not in dumps(document)


def test_a_node_payload_has_no_envelope():
    payload = node_to_payload(Paragraph())
    assert "schema_version" not in payload
    assert payload[TYPE_KEY] == "paragraph"


def test_node_from_payload_checks_the_class_it_was_asked_for():
    payload = node_to_payload(Paragraph())
    with pytest.raises(SerializationError, match="nao e compativel"):
        node_from_payload(payload, Heading)


# --------------------------------------------------------------------------- #
# Deep structures
# --------------------------------------------------------------------------- #


def test_deeply_nested_inline_wrappers_survive():
    node: Text | Strong = Text(content="fundo")
    for _ in range(40):
        node = Strong(content=(node,))
    document = Document(body=(Paragraph(content=(node,)),))
    assert loads(dumps(document)) == document


def test_a_deeply_nested_game_tree_survives():
    node = MoveNode(san="e4", ply=40)
    for ply in range(39, 0, -1):
        node = MoveNode(san="e4", ply=ply, children=(node,))
    document = Document(body=(GameScore(children=(node,)),))
    assert loads(dumps(document)) == document


def test_a_document_with_no_body_survives():
    document = Document(metadata=DocumentMetadata(title="Vazio"))
    assert loads(dumps(document)) == document


def test_measures_and_colours_survive_inside_nested_property_objects():
    props = RunProps(
        font_size=Measure(value=10.5, unit=LengthUnit.PT),
        color=Color.cmyk(0.1, 0.2, 0.3, 0.4),
    )
    document = Document(body=(Paragraph(content=(Text(content="x", props=props),)),))
    restored = loads(dumps(document))
    assert restored.body[0].content[0].props.color == props.color
    assert restored.body[0].content[0].props.font_size == props.font_size
