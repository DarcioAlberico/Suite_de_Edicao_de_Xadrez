"""Stable serialisation tags for every Document IR dataclass.

The tag -- not the Python class name -- is what appears in serialised JSON, so
classes can be renamed, split or moved between modules without invalidating
documents already written to disk. Renaming a *tag* is a schema change and goes
through :mod:`caissa.core.model.migrations`.

The registry is also how the test suite proves completeness: ``iter_registered``
enumerates every declared type, and a test asserts that each one is
constructible, serialisable and round-trips.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, TypeVar

__all__ = [
    "IRTypeError",
    "class_for_tag",
    "ir_node",
    "is_ir_dataclass",
    "iter_registered",
    "tag_for_class",
    "tag_of",
]


class IRTypeError(TypeError):
    """Raised when a value is not a legal Document IR type."""


_TAG_TO_CLASS: dict[str, type[Any]] = {}
_CLASS_TO_TAG: dict[type[Any], str] = {}

_C = TypeVar("_C", bound=type[Any])


def ir_node(tag: str) -> Callable[[_C], _C]:
    """Register a dataclass under a stable serialisation tag.

    Apply *above* ``@dataclass`` so that the registered object is the final
    class -- ``slots=True`` makes ``dataclass`` return a freshly built class, so
    a decorator applied underneath would capture the wrong one::

        @ir_node("paragraph")
        @dataclass(frozen=True, slots=True, kw_only=True)
        class Paragraph(IRNode): ...

    Args:
        tag: The stable identifier written to JSON as the ``type`` key. Must be
            unique across the whole IR.

    Returns:
        A decorator that records the class and returns it unchanged.
    """

    def decorate(cls: _C) -> _C:
        if not dataclasses.is_dataclass(cls):
            msg = f"@ir_node({tag!r}) exige uma dataclass; recebido {cls!r}"
            raise IRTypeError(msg)
        existing = _TAG_TO_CLASS.get(tag)
        if existing is not None and existing is not cls:
            msg = f"tag {tag!r} ja registrada por {existing.__module__}.{existing.__qualname__}"
            raise IRTypeError(msg)
        _TAG_TO_CLASS[tag] = cls
        _CLASS_TO_TAG[cls] = tag
        return cls

    return decorate


def class_for_tag(tag: str) -> type[Any]:
    """Look up the dataclass registered under ``tag``.

    Args:
        tag: A serialisation tag.

    Returns:
        The registered class.

    Raises:
        IRTypeError: If no class is registered under that tag.
    """
    try:
        return _TAG_TO_CLASS[tag]
    except KeyError as exc:
        msg = f"tipo de no desconhecido: {tag!r}"
        raise IRTypeError(msg) from exc


def tag_for_class(cls: type[Any]) -> str:
    """Return the serialisation tag of a registered class.

    Args:
        cls: A class previously decorated with :func:`ir_node`.

    Returns:
        Its stable tag.

    Raises:
        IRTypeError: If the class was never registered.
    """
    try:
        return _CLASS_TO_TAG[cls]
    except KeyError as exc:
        msg = f"classe nao registrada no IR: {cls.__module__}.{cls.__qualname__}"
        raise IRTypeError(msg) from exc


def tag_of(value: object) -> str:
    """Return the serialisation tag of an instance.

    Args:
        value: An instance of a registered IR dataclass.

    Returns:
        Its stable tag.

    Raises:
        IRTypeError: If the value's class was never registered.
    """
    return tag_for_class(type(value))


def is_ir_dataclass(value: object) -> bool:
    """Report whether ``value`` is an instance of a registered IR dataclass.

    Args:
        value: Any object.

    Returns:
        ``True`` when the value's exact class carries a serialisation tag.
    """
    return type(value) in _CLASS_TO_TAG


def iter_registered() -> tuple[tuple[str, type[Any]], ...]:
    """Return every ``(tag, class)`` pair known to the registry, sorted by tag.

    Returns:
        A tuple of pairs ordered by tag.
    """
    return tuple(sorted(_TAG_TO_CLASS.items()))
