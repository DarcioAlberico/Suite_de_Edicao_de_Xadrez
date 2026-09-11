"""The codec's generic machinery, exercised past what today's nodes reach.

``encode_value`` and ``decode_value`` are reflection-driven and deliberately more
general than the current node vocabulary: they handle ``Literal``, ``bytes``,
``list``/``set``/``frozenset``, fixed-length tuples and untyped fields, none of
which any node uses *yet*. Leaving those paths untested until the day someone
adds such a field is how a schema change turns into a corrupted save file, so
they are exercised here directly.

The same goes for the tag registry's refusals. They only fire on a programming
error -- two classes claiming one tag, a decorator on a non-dataclass -- but the
error message is what a developer sees at import time, so it is worth pinning.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

import pytest

from caissa.core.model import (
    ULID,
    Color,
    Document,
    IRTypeError,
    Measure,
    Paragraph,
    RunProps,
    SerializationError,
    Text,
    class_for_tag,
    ir_node,
    is_ir_dataclass,
    iter_registered,
    tag_for_class,
    tag_of,
)
from caissa.core.model.serialize import (
    TYPE_KEY,
    decode_value,
    encode_value,
    node_from_payload,
    node_to_payload,
)

# --------------------------------------------------------------------------- #
# Annotations no node uses yet
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["white", "black"])
def test_a_literal_annotation_accepts_its_members(value):
    assert decode_value(value, Literal["white", "black"]) == value


def test_a_literal_annotation_refuses_anything_else():
    with pytest.raises(SerializationError, match="fora dos literais permitidos"):
        decode_value("green", Literal["white", "black"])


def test_bytes_travel_as_base64():
    payload = encode_value(b"\x00\x01\xfe\xff")
    assert payload == base64.b64encode(b"\x00\x01\xfe\xff").decode("ascii")
    assert decode_value(payload, bytes) == b"\x00\x01\xfe\xff"


@pytest.mark.parametrize("container", [list, set, frozenset])
def test_the_other_sequence_containers_decode(container):
    decoded = decode_value(["a", "b"], container[str])
    assert isinstance(decoded, container)
    assert set(decoded) == {"a", "b"}


def test_a_set_encodes_deterministically():
    """Sorted on the way out, so two runs produce byte-identical JSON."""
    assert encode_value({"b", "a", "c"}) == encode_value(frozenset({"c", "a", "b"}))


def test_a_fixed_length_tuple_checks_its_arity():
    assert decode_value([1, "x"], tuple[int, str]) == (1, "x")
    with pytest.raises(SerializationError, match="exige 2 itens"):
        decode_value([1], tuple[int, str])


def test_an_empty_tuple_annotation_decodes_to_nothing():
    assert decode_value([], tuple[()]) == ()


def test_an_untyped_field_keeps_tagged_values_and_tuples():
    payload = encode_value(Measure.points(3.0))
    assert decode_value(payload, Any) == Measure.points(3.0)
    assert decode_value([1, 2], Any) == (1, 2)
    assert decode_value("texto", Any) == "texto"


def test_an_untyped_field_ignores_an_untagged_object():
    assert decode_value({"a": 1}, Any) == {"a": 1}


def test_an_unsupported_generic_annotation_is_refused():
    with pytest.raises(SerializationError, match="anotacao generica nao suportada"):
        decode_value({"a": 1}, dict[str, int])


def test_a_non_type_annotation_is_refused():
    with pytest.raises(SerializationError, match="anotacao nao suportada"):
        decode_value(1, "nao e um tipo")


def test_a_class_the_ir_cannot_build_is_refused():
    class Foreign:
        pass

    with pytest.raises(SerializationError, match="tipo nao desserializavel"):
        decode_value({}, Foreign)


def test_the_none_type_annotation_accepts_only_null():
    assert decode_value(None, type(None)) is None
    with pytest.raises(SerializationError, match="esperado null"):
        decode_value(1, type(None))


# --------------------------------------------------------------------------- #
# Unions
# --------------------------------------------------------------------------- #


def test_a_union_with_one_concrete_member_decodes_straight_through():
    assert decode_value("x", str | None) == "x"
    assert decode_value(None, str | None) is None


def test_a_union_of_scalars_tries_each_member():
    assert decode_value(7, int | str) == 7
    assert decode_value("sete", int | str) == "sete"


def test_a_union_that_nothing_satisfies_reports_every_attempt():
    with pytest.raises(SerializationError, match="nao satisfaz") as excinfo:
        decode_value([1, 2], int | str)
    assert "int" in str(excinfo.value)
    assert "str" in str(excinfo.value)


def test_a_non_string_type_key_is_refused():
    payload = {TYPE_KEY: 7, "content": "x"}
    with pytest.raises(SerializationError, match="deve ser texto"):
        decode_value(payload, Text | Paragraph)


# --------------------------------------------------------------------------- #
# Encoding refusals
# --------------------------------------------------------------------------- #


def test_an_enum_whose_value_is_not_json_is_refused():
    class Weird(Enum):
        THING = (1, 2)

    with pytest.raises(SerializationError, match="enum com valor nao serializavel"):
        encode_value(Weird.THING)


def test_an_unregistered_dataclass_is_refused_at_encode_time():
    @dataclass(frozen=True)
    class Unregistered:
        value: int = 1

    with pytest.raises(SerializationError, match="classe nao registrada"):
        encode_value(Unregistered())


def test_an_object_of_no_known_shape_is_refused():
    with pytest.raises(SerializationError, match="tipo nao serializavel"):
        encode_value(object())


def test_a_payload_missing_a_required_field_names_the_class():
    payload = node_to_payload(Text(content="x"))
    del payload["content"]
    with pytest.raises(SerializationError, match="nao foi possivel construir Text"):
        node_from_payload(payload, Text)


def test_a_nested_error_carries_the_path_of_field_names():
    payload = node_to_payload(Text(content="x", props=RunProps(font_size=Measure.points(9.0))))
    payload["props"]["font_size"]["value"] = "nove"
    with pytest.raises(SerializationError, match=r"Text\.props") as excinfo:
        node_from_payload(payload, Text)
    assert "font_size" in str(excinfo.value)


def test_a_document_payload_whose_body_is_not_a_document_is_refused():
    from caissa.core.model.serialize import document_from_payload

    payload = {
        "schema_version": 1,
        "kind": "caissa.document",
        "document": node_to_payload(Paragraph()),
    }
    with pytest.raises(SerializationError, match=r"nao e compativel|nao e um documento"):
        document_from_payload(payload)


# --------------------------------------------------------------------------- #
# Round trips of the leaf types, one at a time
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "annotation"),
    [
        (True, bool),
        (False, bool),
        (0, int),
        (-42, int),
        (0.0, float),
        (-1.5e-7, float),
        ("", str),
        ("acentuação ♞", str),
        (None, str | None),
        (b"\x00\xff", bytes),
        (datetime(2026, 9, 7, tzinfo=UTC), datetime),
        (ULID.from_parts(1_700_000_000_000, 3), ULID),
        (Measure.points(11.0), Measure),
        (Color.rgb8(1, 2, 3), Color),
    ],
)
def test_each_leaf_type_round_trips(value, annotation):
    assert decode_value(encode_value(value), annotation) == value


def test_a_very_small_and_a_very_large_float_survive():
    for value in (1e-300, 1e300, 0.1 + 0.2):
        node = Measure(value=value)
        assert decode_value(encode_value(node), Measure).value == value


# --------------------------------------------------------------------------- #
# The tag registry
# --------------------------------------------------------------------------- #


def test_a_tag_resolves_to_its_class_and_back():
    assert class_for_tag("paragraph") is Paragraph
    assert tag_for_class(Paragraph) == "paragraph"
    assert tag_of(Paragraph()) == "paragraph"


def test_an_unknown_tag_is_refused_by_name():
    with pytest.raises(IRTypeError, match="tipo de no desconhecido: 'fantasma'"):
        class_for_tag("fantasma")


def test_an_unregistered_class_is_refused_by_name():
    class Foreign:
        pass

    with pytest.raises(IRTypeError, match="classe nao registrada"):
        tag_for_class(Foreign)


def test_registering_a_non_dataclass_is_refused():
    with pytest.raises(IRTypeError, match="exige uma dataclass"):

        @ir_node("nao_dataclass")
        class NotADataclass:
            pass


def test_registering_a_tag_twice_names_the_existing_owner():
    with pytest.raises(IRTypeError, match=r"tag 'paragraph' ja registrada por .*Paragraph"):

        @ir_node("paragraph")
        @dataclass(frozen=True)
        class Impostor:
            pass


def test_registering_the_same_class_under_the_same_tag_is_idempotent():
    """Re-importing a module must not explode."""
    assert ir_node("paragraph")(Paragraph) is Paragraph


def test_is_ir_dataclass_is_exact_not_by_subclass():
    assert is_ir_dataclass(Paragraph())
    assert not is_ir_dataclass("texto")
    assert not is_ir_dataclass(object())


def test_the_registry_is_sorted_by_tag():
    tags = [tag for tag, _cls in iter_registered()]
    assert tags == sorted(tags)


def test_a_node_reports_its_own_tag_as_a_property():
    assert Document().node_type == "document"
    assert Text(content="x").node_type == "text"
