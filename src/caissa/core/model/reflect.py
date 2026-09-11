"""Cached type introspection shared by the serialiser, the visitor and the differ.

Three subsystems need to walk an IR dataclass generically: JSON encoding needs
each field's declared type to decode it back, tree traversal needs to know which
fields hold nodes, and the differ needs to know which fields are scalar. Doing
that reflection once and caching it is what keeps a hundred-thousand-node
document affordable -- ``typing.get_type_hints`` is expensive and the answer
never changes for a given class.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, Union, get_args, get_origin, get_type_hints

from caissa.core.model.base import IRNode

__all__ = [
    "allows_none",
    "child_nodes",
    "field_defaults",
    "field_types",
    "is_node_field",
    "union_members",
]

# Hand-rolled memoisation rather than ``functools.lru_cache``: the keys are
# classes, the tables are computed once per class for the life of the process,
# and a plain dict lookup is measurably cheaper than the wrapper on a hot path
# that runs once per field per node.
_FIELD_TYPES: dict[type[Any], Mapping[str, Any]] = {}
_FIELD_DEFAULTS: dict[type[Any], Mapping[str, Any]] = {}


def field_types(cls: type[Any]) -> Mapping[str, Any]:
    """Return each dataclass field's resolved annotation.

    Args:
        cls: A dataclass; annotations are resolved against its defining module,
            so forward references and ``from __future__ import annotations``
            both work.

    Returns:
        A mapping from field name to resolved type, in declaration order.

    Raises:
        TypeError: If ``cls`` is not a dataclass.
    """
    cached = _FIELD_TYPES.get(cls)
    if cached is not None:
        return cached
    if not is_dataclass(cls):
        msg = f"{cls!r} nao e uma dataclass"
        raise TypeError(msg)
    hints = get_type_hints(cls)
    resolved: Mapping[str, Any] = {item.name: hints[item.name] for item in fields(cls)}
    _FIELD_TYPES[cls] = resolved
    return resolved


def field_defaults(cls: type[Any]) -> Mapping[str, Any]:
    """Return each field's plain default, where it has one.

    A ``default_factory`` counts only when its result is stable and comparable:
    the empty tuple, or a value-object dataclass constructed with no arguments.
    A factory that mints identity -- ``ULID.new`` -- answers differently every
    call and must never be treated as omissible, which is why node factories are
    excluded by the :class:`~caissa.core.model.base.IRNode` check.

    Args:
        cls: A dataclass.

    Returns:
        A mapping from field name to its default value, omitting fields that
        have none.

    Raises:
        TypeError: If ``cls`` is not a dataclass.
    """
    cached = _FIELD_DEFAULTS.get(cls)
    if cached is not None:
        return cached
    if not is_dataclass(cls):
        msg = f"{cls!r} nao e uma dataclass"
        raise TypeError(msg)
    defaults: dict[str, Any] = {}
    for item in fields(cls):
        if item.default is not MISSING:
            defaults[item.name] = item.default
            continue
        factory: object = item.default_factory
        if factory is MISSING:
            continue
        if factory is tuple:
            defaults[item.name] = ()
        elif isinstance(factory, type) and _is_value_object(factory):
            defaults[item.name] = factory()
    _FIELD_DEFAULTS[cls] = defaults
    return defaults


def _is_value_object(candidate: type[Any]) -> bool:
    """Report whether a class is a dataclass that carries no identity.

    Args:
        candidate: The class a ``default_factory`` refers to.

    Returns:
        ``True`` for a dataclass that is not an
        :class:`~caissa.core.model.base.IRNode` subclass, so constructing it
        twice gives two equal values.
    """
    return is_dataclass(candidate) and not issubclass(candidate, IRNode)


def union_members(annotation: Any) -> tuple[Any, ...]:
    """Return the members of a union annotation, or an empty tuple.

    Handles both spellings -- ``X | Y`` (``types.UnionType``) and
    ``typing.Union[X, Y]`` -- because ``get_type_hints`` produces whichever the
    source used.

    Args:
        annotation: A resolved annotation.

    Returns:
        The union's members, or ``()`` when the annotation is not a union.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return get_args(annotation)
    return ()


def allows_none(annotation: Any) -> bool:
    """Report whether an annotation admits ``None``.

    Args:
        annotation: A resolved annotation.

    Returns:
        ``True`` when ``None`` is a legal value for the field.
    """
    if annotation is None or annotation is type(None):
        return True
    return any(member is type(None) for member in union_members(annotation))


def is_node_field(value: object) -> bool:
    """Report whether a field value holds one or more nodes.

    Args:
        value: A field value.

    Returns:
        ``True`` for an :class:`~caissa.core.model.base.IRNode` and for a
        non-empty tuple whose first element is one.
    """
    if isinstance(value, IRNode):
        return True
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], IRNode)


def child_nodes(node: IRNode) -> tuple[tuple[str, int | None, IRNode], ...]:
    """Return every child node of ``node``, with its location.

    Args:
        node: The parent node.

    Returns:
        Triples of ``(field name, index or None, child)`` in declaration order.
        ``index`` is ``None`` for a field holding a single node and the position
        for a field holding a tuple of nodes.
    """
    collected: list[tuple[str, int | None, IRNode]] = []
    for name in field_types(type(node)):
        value = getattr(node, name)
        if isinstance(value, IRNode):
            collected.append((name, None, value))
        elif isinstance(value, tuple):
            for index, item in enumerate(value):
                if isinstance(item, IRNode):
                    collected.append((name, index, item))
    return tuple(collected)
