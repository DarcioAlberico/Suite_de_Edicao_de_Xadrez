"""Lossless JSON serialisation of the Document IR.

The codec is reflection-driven rather than hand-written: encoding walks
dataclass fields, decoding is steered by each field's declared type. That is a
deliberate choice, because a hand-written pair of methods per node type is
exactly the place where a new field gets added to one side and forgotten on the
other -- and a silently dropped field is the failure mode ADR-0002 exists to
prevent.

Shape on disk::

    {
      "schema_version": 1,
      "kind": "caissa.document",
      "generator": "caissa-ir/1",
      "document": { "type": "document", "id": "01J...", ... }
    }

Every dataclass writes a ``type`` key holding its stable registry tag, so the
payload is self-describing and a union field (``Block``, ``Inline``) decodes
without guessing. Fields equal to their declared default are omitted, which
keeps a document readable and shrinks a large book by roughly an order of
magnitude without costing any fidelity: the decoder puts the same default back.

Round-trip identity is a hard guarantee and is tested against a ten-thousand
node corpus: ``loads(dumps(document)) == document``, including every node id.
"""

from __future__ import annotations

import base64
import json
import math
import types
from dataclasses import is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Final, Literal, TypeVar, get_args, get_origin

from caissa.core.model.base import IRNode
from caissa.core.model.document import Document
from caissa.core.model.ids import ULID
from caissa.core.model.migrations import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_REGISTRY,
    JsonObject,
    JsonValue,
    MigrationRegistry,
)
from caissa.core.model.reflect import field_defaults, field_types, union_members
from caissa.core.model.registry import IRTypeError, class_for_tag, tag_of

__all__ = [
    "GENERATOR",
    "PAYLOAD_KIND",
    "TYPE_KEY",
    "SerializationError",
    "decode_value",
    "document_from_payload",
    "document_to_payload",
    "dumps",
    "encode_value",
    "loads",
    "node_from_payload",
    "node_to_payload",
]

#: Key every serialised dataclass writes its registry tag under.
TYPE_KEY: Final = "type"

#: Envelope discriminator, so a stray JSON file is recognised for what it is.
PAYLOAD_KIND: Final = "caissa.document"

#: Identifies the writer in the envelope, for diagnosing a bad export.
GENERATOR: Final = f"caissa-ir/{CURRENT_SCHEMA_VERSION}"

_NONE_TYPE: Final = type(None)

#: ``tuple[X, ...]`` resolves to exactly two type arguments, the second being
#: ``Ellipsis``; that is what distinguishes a variadic tuple from a fixed one.
_VARIADIC_ARGS: Final = 2

_T = TypeVar("_T")


class SerializationError(ValueError):
    """Raised when a value cannot be encoded, or a payload cannot be decoded."""


# --------------------------------------------------------------------------- #
# Encoding
# --------------------------------------------------------------------------- #


def encode_value(value: object, *, omit_defaults: bool = True) -> JsonValue:
    """Encode any IR value to JSON-compatible data.

    Args:
        value: A node, a value object, or any scalar the IR uses.
        omit_defaults: Leave out fields whose value equals their declared
            default. Lossless -- the decoder restores them -- and much smaller.

    Returns:
        JSON-compatible data.

    Raises:
        SerializationError: If the value is of a type the IR does not use.
    """
    if value is None or (
        isinstance(value, (bool, int, float, str)) and not isinstance(value, Enum)
    ):
        return _encode_scalar(value)
    if isinstance(value, Enum):
        member_value = value.value
        if isinstance(member_value, (str, int, float, bool)) or member_value is None:
            return member_value
        msg = f"enum com valor nao serializavel: {value!r}"
        raise SerializationError(msg)
    if isinstance(value, (ULID, datetime, bytes)):
        return _encode_atom(value)
    if isinstance(value, (tuple, list, frozenset, set)):
        items = sorted(value, key=repr) if isinstance(value, (frozenset, set)) else list(value)
        return [encode_value(item, omit_defaults=omit_defaults) for item in items]
    if is_dataclass(value) and not isinstance(value, type):
        return _encode_dataclass(value, omit_defaults=omit_defaults)
    msg = f"tipo nao serializavel no IR: {type(value).__module__}.{type(value).__qualname__}"
    raise SerializationError(msg)


def _encode_atom(value: ULID | datetime | bytes) -> JsonValue:
    """Encode the three non-JSON leaf types the IR uses.

    Args:
        value: An identifier, an instant, or raw bytes.

    Returns:
        The canonical ULID string, an ISO 8601 timestamp, or base64 text.
    """
    if isinstance(value, ULID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return base64.b64encode(value).decode("ascii")


def _encode_scalar(value: object) -> JsonValue:
    """Encode a JSON scalar, rejecting non-finite floats.

    Args:
        value: ``None``, a bool, an int, a float or a str.

    Returns:
        The value unchanged.

    Raises:
        SerializationError: If a float is NaN or infinite, which JSON cannot
            represent portably.
    """
    if isinstance(value, float) and not math.isfinite(value):
        msg = f"float nao finito nao e representavel em JSON: {value!r}"
        raise SerializationError(msg)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    msg = f"escalar inesperado: {value!r}"
    raise SerializationError(msg)


def _encode_dataclass(value: object, *, omit_defaults: bool) -> JsonObject:
    """Encode a registered IR dataclass, writing its tag and its non-default fields.

    Args:
        value: A registered dataclass instance.
        omit_defaults: Leave out fields equal to their declared default.

    Returns:
        The JSON object.

    Raises:
        SerializationError: If the class was never registered.
    """
    cls = type(value)
    try:
        tag = tag_of(value)
    except IRTypeError as exc:
        raise SerializationError(str(exc)) from exc
    result: JsonObject = {TYPE_KEY: tag}
    defaults = field_defaults(cls) if omit_defaults else {}
    for name in field_types(cls):
        field_value = getattr(value, name)
        if (
            name in defaults
            and type(field_value) is type(defaults[name])
            and field_value == defaults[name]
        ):
            continue
        result[name] = encode_value(field_value, omit_defaults=omit_defaults)
    return result


# --------------------------------------------------------------------------- #
# Decoding
# --------------------------------------------------------------------------- #


def decode_value(data: JsonValue, annotation: Any) -> Any:
    """Decode JSON data into the type an annotation asks for.

    Args:
        data: JSON-compatible data, as produced by :func:`encode_value`.
        annotation: The resolved type the value must become.

    Returns:
        The decoded value.

    Raises:
        SerializationError: If the data does not fit the annotation.
    """
    if annotation is Any or annotation is object:
        return _decode_untyped(data)

    members = union_members(annotation)
    if members:
        return _decode_union(data, members, annotation)

    origin = get_origin(annotation)
    if origin is Literal:
        return _decode_literal(data, annotation)
    if origin is tuple:
        return _decode_tuple(data, get_args(annotation), annotation)
    if origin in (list, frozenset, set):
        decoded = _decode_tuple(data, (get_args(annotation)[0], Ellipsis), annotation)
        return list(decoded) if origin is list else origin(decoded)
    if origin is not None:
        msg = f"anotacao generica nao suportada pelo IR: {annotation!r}"
        raise SerializationError(msg)

    return _decode_class(data, annotation)


def _decode_untyped(data: JsonValue) -> Any:
    """Decode data whose annotation gives no guidance.

    Args:
        data: JSON-compatible data.

    Returns:
        A registered dataclass when the data carries a tag, otherwise the data
        itself with lists turned into tuples.
    """
    if isinstance(data, dict) and TYPE_KEY in data:
        tag = data[TYPE_KEY]
        if isinstance(tag, str):
            return _decode_tagged(data, class_for_tag(tag))
    if isinstance(data, list):
        return tuple(_decode_untyped(item) for item in data)
    return data


def _decode_union(data: JsonValue, members: tuple[Any, ...], annotation: Any) -> Any:
    """Decode a value whose annotation is a union.

    Args:
        data: JSON-compatible data.
        members: The union's members.
        annotation: The full annotation, for error messages.

    Returns:
        The decoded value.

    Raises:
        SerializationError: If no member accepts the data.
    """
    if data is None:
        if any(member is _NONE_TYPE for member in members):
            return None
        msg = f"null nao e valor valido para {_name_of(annotation)}"
        raise SerializationError(msg)

    concrete = tuple(member for member in members if member is not _NONE_TYPE)
    if len(concrete) == 1:
        return decode_value(data, concrete[0])

    if isinstance(data, dict) and TYPE_KEY in data:
        tag = data[TYPE_KEY]
        if not isinstance(tag, str):
            msg = f"chave {TYPE_KEY!r} deve ser texto; recebido {tag!r}"
            raise SerializationError(msg)
        cls = class_for_tag(tag)
        for member in concrete:
            if isinstance(member, type) and issubclass(cls, member):
                return _decode_tagged(data, cls)
        options = ", ".join(_name_of(member) for member in concrete)
        msg = f"tipo {tag!r} nao pertence a {options}"
        raise SerializationError(msg)

    errors: list[str] = []
    for member in concrete:
        try:
            return decode_value(data, member)
        except (SerializationError, IRTypeError, ValueError, TypeError) as exc:
            errors.append(f"{_name_of(member)}: {exc}")
    detail = "; ".join(errors)
    msg = f"valor {data!r} nao satisfaz {_name_of(annotation)} ({detail})"
    raise SerializationError(msg)


def _decode_literal(data: JsonValue, annotation: Any) -> Any:
    """Decode a ``Literal`` annotation.

    Args:
        data: JSON-compatible data.
        annotation: The literal annotation.

    Returns:
        The value, unchanged.

    Raises:
        SerializationError: If the value is not one of the allowed literals.
    """
    allowed = get_args(annotation)
    if data in allowed:
        return data
    options = ", ".join(repr(item) for item in allowed)
    msg = f"valor {data!r} fora dos literais permitidos ({options})"
    raise SerializationError(msg)


def _decode_tuple(data: JsonValue, args: tuple[Any, ...], annotation: Any) -> tuple[Any, ...]:
    """Decode a tuple annotation, variadic or fixed length.

    Args:
        data: JSON-compatible data; must be a list.
        args: The tuple's type arguments.
        annotation: The full annotation, for error messages.

    Returns:
        The decoded tuple.

    Raises:
        SerializationError: If the data is not a list, or its length does not
            match a fixed-length tuple.
    """
    if not isinstance(data, list):
        msg = f"esperado uma lista para {_name_of(annotation)}; recebido {type(data).__name__}"
        raise SerializationError(msg)
    if not args or args == ((),):
        return ()
    if len(args) == _VARIADIC_ARGS and args[1] is Ellipsis:
        return tuple(decode_value(item, args[0]) for item in data)
    if len(args) != len(data):
        msg = f"{_name_of(annotation)} exige {len(args)} itens; recebidos {len(data)}"
        raise SerializationError(msg)
    return tuple(decode_value(item, arg) for item, arg in zip(data, args, strict=True))


def _decode_class(data: JsonValue, annotation: Any) -> Any:
    """Decode a value whose annotation is a plain class.

    Args:
        data: JSON-compatible data.
        annotation: The target class.

    Returns:
        The decoded value.

    Raises:
        SerializationError: If the data does not fit the class.
    """
    if annotation is _NONE_TYPE:
        if data is None:
            return None
        msg = f"esperado null; recebido {data!r}"
        raise SerializationError(msg)
    if not isinstance(annotation, type):
        msg = f"anotacao nao suportada pelo IR: {annotation!r}"
        raise SerializationError(msg)
    # Enum before the primitives: ``StrEnum`` is a ``str`` subclass and would
    # otherwise decode to a bare string, losing the member.
    if issubclass(annotation, (Enum, ULID, datetime)):
        return _decode_atom(data, annotation)
    if issubclass(annotation, (bool, int, float, str, bytes)):
        return _decode_primitive(data, annotation)
    if is_dataclass(annotation):
        return _decode_dataclass(data, annotation)
    msg = f"tipo nao desserializavel pelo IR: {annotation.__name__}"
    raise SerializationError(msg)


def _decode_atom(data: JsonValue, annotation: type[Any]) -> Any:
    """Decode the three leaf types whose JSON form is a string with structure.

    Args:
        data: JSON-compatible data.
        annotation: An ``Enum``, ``ULID`` or ``datetime`` subclass.

    Returns:
        The decoded value.

    Raises:
        SerializationError: If the data is not the right shape for the type.
    """
    if issubclass(annotation, Enum):
        try:
            return annotation(data)
        except ValueError as exc:
            msg = f"valor {data!r} nao pertence a {annotation.__name__}"
            raise SerializationError(msg) from exc
    if issubclass(annotation, ULID):
        if not isinstance(data, str):
            msg = f"ULID deve ser texto; recebido {type(data).__name__}"
            raise SerializationError(msg)
        return ULID.from_string(data)
    if not isinstance(data, str):
        msg = f"datetime deve ser texto ISO 8601; recebido {type(data).__name__}"
        raise SerializationError(msg)
    try:
        return datetime.fromisoformat(data)
    except ValueError as exc:
        msg = f"data ISO 8601 invalida: {data!r}"
        raise SerializationError(msg) from exc


def _decode_primitive(data: JsonValue, annotation: type[Any]) -> Any:
    """Decode a JSON primitive, refusing the bool/int confusion JSON invites.

    ``True`` is an ``int`` in Python but never an acceptable value for an
    ``int`` field, so it is rejected explicitly rather than silently read
    as ``1``.

    Args:
        data: JSON-compatible data.
        annotation: A ``bool``, ``int``, ``float``, ``str`` or ``bytes``
            subclass.

    Returns:
        The decoded value.

    Raises:
        SerializationError: If the data is not of the expected primitive type.
    """
    if issubclass(annotation, bool):
        if isinstance(data, bool):
            return data
        msg = f"esperado booleano; recebido {data!r}"
        raise SerializationError(msg)
    if issubclass(annotation, int):
        if isinstance(data, bool) or not isinstance(data, int):
            msg = f"esperado inteiro; recebido {data!r}"
            raise SerializationError(msg)
        return data
    if issubclass(annotation, float):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            msg = f"esperado numero; recebido {data!r}"
            raise SerializationError(msg)
        return float(data)
    if issubclass(annotation, str):
        if not isinstance(data, str):
            msg = f"esperado texto; recebido {type(data).__name__}"
            raise SerializationError(msg)
        return data
    if not isinstance(data, str):
        msg = f"esperado texto base64; recebido {type(data).__name__}"
        raise SerializationError(msg)
    return base64.b64decode(data.encode("ascii"))


def _decode_dataclass(data: JsonValue, annotation: type[Any]) -> Any:
    """Decode a dataclass, honouring the tag when the payload carries one.

    Args:
        data: JSON-compatible data; must be an object.
        annotation: The declared class.

    Returns:
        The decoded instance.

    Raises:
        SerializationError: If the data is not an object, or its tag names a
            class incompatible with the annotation.
    """
    if not isinstance(data, dict):
        msg = f"esperado um objeto para {annotation.__name__}; recebido {type(data).__name__}"
        raise SerializationError(msg)
    cls = annotation
    tag = data.get(TYPE_KEY)
    if isinstance(tag, str):
        resolved = class_for_tag(tag)
        if not issubclass(resolved, annotation):
            msg = f"tipo {tag!r} nao e compativel com {annotation.__name__}"
            raise SerializationError(msg)
        cls = resolved
    return _decode_tagged(data, cls)


def _decode_tagged(data: dict[str, JsonValue], cls: type[Any]) -> Any:
    """Build one dataclass instance from a payload object.

    Args:
        data: The payload object, including its ``type`` key.
        cls: The class to build.

    Returns:
        The instance.

    Raises:
        SerializationError: If the payload has unknown keys, misses a required
            field, or a field value does not fit its declared type.
    """
    annotations = field_types(cls)
    unknown = set(data) - set(annotations) - {TYPE_KEY}
    if unknown:
        listed = ", ".join(sorted(unknown))
        msg = f"campos desconhecidos em {cls.__name__}: {listed}"
        raise SerializationError(msg)
    kwargs: dict[str, Any] = {}
    for name, annotation in annotations.items():
        if name not in data:
            continue
        try:
            kwargs[name] = decode_value(data[name], annotation)
        except SerializationError as exc:
            msg = f"{cls.__name__}.{name}: {exc}"
            raise SerializationError(msg) from exc
    try:
        return cls(**kwargs)
    except TypeError as exc:
        msg = f"nao foi possivel construir {cls.__name__}: {exc}"
        raise SerializationError(msg) from exc


def _name_of(annotation: Any) -> str:
    """Render an annotation for an error message.

    Args:
        annotation: Any annotation.

    Returns:
        A short readable name.
    """
    if isinstance(annotation, type):
        return annotation.__name__
    if isinstance(annotation, types.UnionType):
        return " | ".join(_name_of(member) for member in get_args(annotation))
    return str(annotation)


# --------------------------------------------------------------------------- #
# Document-level API
# --------------------------------------------------------------------------- #


def document_to_payload(document: Document, *, omit_defaults: bool = True) -> JsonObject:
    """Wrap a document in the versioned envelope.

    Args:
        document: The document to serialise.
        omit_defaults: Leave out fields equal to their declared default.

    Returns:
        The complete payload, ready for :func:`json.dumps`.
    """
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": PAYLOAD_KIND,
        "generator": GENERATOR,
        "document": _encode_dataclass(document, omit_defaults=omit_defaults),
    }


def document_from_payload(
    payload: JsonObject,
    *,
    registry: MigrationRegistry = DEFAULT_REGISTRY,
) -> tuple[Document, tuple[str, ...]]:
    """Read a document out of a versioned envelope, migrating it if needed.

    Args:
        payload: The parsed JSON payload.
        registry: Migration chain to bring the payload up to date.

    Returns:
        The document and a description of every migration applied.

    Raises:
        SerializationError: If the envelope is malformed or the body is not a
            document.
        MigrationError: If the payload cannot be brought to the current schema
            version.
    """
    kind = payload.get("kind")
    if kind is not None and kind != PAYLOAD_KIND:
        msg = f"payload nao e um documento Caissa: kind={kind!r}"
        raise SerializationError(msg)
    raw_version = payload.get("schema_version")
    if not isinstance(raw_version, int) or isinstance(raw_version, bool):
        msg = f"schema_version ausente ou invalida: {raw_version!r}"
        raise SerializationError(msg)
    migrated, applied = registry.migrate(payload, raw_version)
    body = migrated.get("document")
    if not isinstance(body, dict):
        msg = "payload sem a chave 'document'"
        raise SerializationError(msg)
    document = _decode_dataclass(body, Document)
    if not isinstance(document, Document):
        msg = f"raiz do payload nao e um documento: {type(document).__name__}"
        raise SerializationError(msg)
    return document, applied


def dumps(
    document: Document,
    *,
    indent: int | None = None,
    omit_defaults: bool = True,
) -> str:
    """Serialise a document to a JSON string.

    Args:
        document: The document.
        indent: Indentation for a human-readable file; ``None`` writes it
            compactly.
        omit_defaults: Leave out fields equal to their declared default.

    Returns:
        The JSON text, UTF-8 clean and with non-finite floats refused rather
        than written as invalid JSON.
    """
    payload = document_to_payload(document, omit_defaults=omit_defaults)
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        allow_nan=False,
        separators=(",", ":") if indent is None else None,
    )


def loads(text: str, *, registry: MigrationRegistry = DEFAULT_REGISTRY) -> Document:
    """Parse a document from a JSON string.

    Args:
        text: JSON text written by :func:`dumps`.
        registry: Migration chain to bring the payload up to date.

    Returns:
        The document.

    Raises:
        SerializationError: If the text is not valid JSON, or not a document
            payload.
        MigrationError: If the payload cannot be brought to the current schema
            version.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"JSON invalido: {exc}"
        raise SerializationError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"esperado um objeto JSON na raiz; recebido {type(parsed).__name__}"
        raise SerializationError(msg)
    document, _applied = document_from_payload(parsed, registry=registry)
    return document


def node_to_payload(node: IRNode, *, omit_defaults: bool = True) -> JsonObject:
    """Serialise a single node, without an envelope.

    Useful for the clipboard, for undo records and for tests.

    Args:
        node: The node.
        omit_defaults: Leave out fields equal to their declared default.

    Returns:
        The JSON object.
    """
    return _encode_dataclass(node, omit_defaults=omit_defaults)


def node_from_payload(data: JsonObject, expected: type[_T]) -> _T:
    """Deserialise a single node, without an envelope.

    Args:
        data: The JSON object.
        expected: The class the payload must produce.

    Returns:
        The node.

    Raises:
        SerializationError: If the payload does not produce that class.
    """
    result = _decode_dataclass(data, expected)
    if not isinstance(result, expected):
        msg = f"esperado {expected.__name__}; recebido {type(result).__name__}"
        raise SerializationError(msg)
    return result
