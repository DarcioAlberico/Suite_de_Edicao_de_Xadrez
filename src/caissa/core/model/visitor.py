"""Generic traversal and rewriting of the Document IR.

Two shapes, both driven by reflection so they work on every node type -- present
and future -- without a match statement anyone can forget to extend:

:class:`Visitor`
    Read-only. Dispatches to ``visit_<tag>`` when the subclass defines one,
    otherwise to :meth:`Visitor.generic_visit`, which recurses.
:class:`Transformer`
    Rewriting. Same dispatch, but each method returns the replacement: a node,
    a tuple of nodes (splice), or ``None`` (delete). Because every node is
    frozen, rewriting rebuilds only the spine from the changed node up to the
    root -- untouched subtrees are shared, so transforming one paragraph of a
    five-hundred-page book copies a handful of objects rather than the book.

:func:`walk` is the imperative form for callers that just want an iterator.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from caissa.core.model.base import IRNode, tag_of
from caissa.core.model.reflect import allows_none, child_nodes, field_types

__all__ = [
    "NodePath",
    "PathStep",
    "TransformError",
    "Transformer",
    "Visitor",
    "find",
    "walk",
]

_N = TypeVar("_N", bound=IRNode)


class TransformError(ValueError):
    """Raised when a transformation result cannot be placed back into the tree."""


@dataclass(frozen=True, slots=True)
class PathStep:
    """One hop from a parent node to a child.

    Attributes:
        field: Name of the field the child sits in.
        index: Position within that field when it holds a tuple, else ``None``.
    """

    field: str
    index: int | None = None

    def __str__(self) -> str:
        """Render as ``field`` or ``field[index]``."""
        return self.field if self.index is None else f"{self.field}[{self.index}]"


@dataclass(frozen=True, slots=True)
class NodePath:
    """The route from the root of a document to a node.

    Paths are what make a validation issue or a diff entry actionable: they say
    *where*, in a form a human can read and a tool can follow.

    Attributes:
        steps: The hops, root first.
    """

    steps: tuple[PathStep, ...] = ()

    def child(self, field: str, index: int | None = None) -> NodePath:
        """Extend the path by one hop.

        Args:
            field: Name of the field the child sits in.
            index: Position within that field, when it holds a tuple.

        Returns:
            The extended path.
        """
        return NodePath(steps=(*self.steps, PathStep(field=field, index=index)))

    @property
    def depth(self) -> int:
        """How many hops from the root."""
        return len(self.steps)

    def __str__(self) -> str:
        """Render as a dotted path, e.g. ``body[3].content[0]``."""
        if not self.steps:
            return "$"
        text = "$"
        for step in self.steps:
            text += f".{step.field}" if step.index is None else f".{step.field}[{step.index}]"
        return text


def walk(root: IRNode, *, path: NodePath | None = None) -> Iterator[tuple[NodePath, IRNode]]:
    """Yield every node in the tree, pre-order, with its path.

    Args:
        root: The node to start from; usually a
            :class:`~caissa.core.model.document.Document`.
        path: Path of ``root`` itself, for walking a subtree in a wider
            context.

    Yields:
        ``(path, node)`` pairs, parents before children and siblings in
        document order.
    """
    base = path if path is not None else NodePath()
    stack: list[tuple[NodePath, IRNode]] = [(base, root)]
    while stack:
        current_path, node = stack.pop()
        yield current_path, node
        children = child_nodes(node)
        for name, index, child in reversed(children):
            stack.append((current_path.child(name, index), child))


def find(root: IRNode, tag: str) -> Iterator[tuple[NodePath, IRNode]]:
    """Yield every node of one type in the tree.

    Args:
        root: The node to start from.
        tag: The serialisation tag to match, e.g. ``"diagram"``.

    Yields:
        ``(path, node)`` pairs for matching nodes only.
    """
    for path, node in walk(root):
        if tag_of(node) == tag:
            yield path, node


class Visitor:
    """Read-only traversal with per-type dispatch.

    Subclasses define ``visit_<tag>(node, path)`` for the types they care
    about; everything else falls through to :meth:`generic_visit`, which
    recurses. A method that does not call ``generic_visit`` prunes that
    subtree, which is how a visitor stops at a boundary such as a nested game
    score.
    """

    def run(self, root: IRNode, *, path: NodePath | None = None) -> None:
        """Visit a tree.

        Args:
            root: The node to start from.
            path: Path of ``root`` itself.
        """
        self.visit(root, path if path is not None else NodePath())

    def visit(self, node: IRNode, path: NodePath) -> None:
        """Dispatch one node to its handler.

        Args:
            node: The node to visit.
            path: Where it sits.
        """
        handler = getattr(self, f"visit_{tag_of(node)}", None)
        if handler is None:
            self.generic_visit(node, path)
        else:
            handler(node, path)

    def generic_visit(self, node: IRNode, path: NodePath) -> None:
        """Visit every child of a node.

        Args:
            node: The node whose children to visit.
            path: Where it sits.
        """
        for name, index, child in child_nodes(node):
            self.visit(child, path.child(name, index))


class Transformer:
    """Rewriting traversal with per-type dispatch.

    Subclasses define ``visit_<tag>(node, path)`` returning the replacement:

    * a node -- substituted in place;
    * a tuple or list of nodes -- spliced into the surrounding sequence, which
      only makes sense for a field that holds several nodes;
    * ``None`` -- deleted, which is legal in a sequence field and in an
      optional single-valued field.

    A handler that wants to keep recursing calls :meth:`generic_visit` and
    returns its result. Not calling it leaves the subtree untouched, which is
    the cheap way to stop at a boundary.
    """

    def transform(self, root: _N) -> _N:
        """Rewrite a whole tree.

        Args:
            root: The node to start from.

        Returns:
            The rewritten tree. The same object is returned when nothing
            changed, so an unchanged document allocates nothing.

        Raises:
            TransformError: If the handler for the root deletes it or returns
                several nodes.
        """
        result = self.visit(root, NodePath())
        if isinstance(result, IRNode):
            if not isinstance(result, type(root)):
                msg = (
                    f"transformacao da raiz devolveu {tag_of(result)!r}, esperado {tag_of(root)!r}"
                )
                raise TransformError(msg)
            return result
        msg = "a raiz do documento nao pode ser removida nem multiplicada"
        raise TransformError(msg)

    def visit(self, node: IRNode, path: NodePath) -> IRNode | Sequence[IRNode] | None:
        """Dispatch one node to its handler.

        Args:
            node: The node to rewrite.
            path: Where it sits.

        Returns:
            The replacement.
        """
        handler = getattr(self, f"visit_{tag_of(node)}", None)
        if handler is None:
            return self.generic_visit(node, path)
        result: IRNode | Sequence[IRNode] | None = handler(node, path)
        return result

    def generic_visit(self, node: _N, path: NodePath) -> _N:
        """Rewrite every child of a node and rebuild it if any changed.

        Args:
            node: The node whose children to rewrite.
            path: Where it sits.

        Returns:
            The node itself when nothing changed, otherwise a copy with the new
            children.

        Raises:
            TransformError: If a result cannot be placed back into its field --
                deleting a required single-valued child, or returning several
                nodes for a field that holds one.
        """
        changes: dict[str, Any] = {}
        types = field_types(type(node))
        for name, annotation in types.items():
            value = getattr(node, name)
            if isinstance(value, IRNode):
                replacement = self._single(value, path.child(name), name, annotation)
                if replacement is not value:
                    changes[name] = replacement
            elif isinstance(value, tuple) and value and isinstance(value[0], IRNode):
                rebuilt = self._sequence(value, path, name)
                if rebuilt is not None:
                    changes[name] = rebuilt
        if not changes:
            return node
        return replace(node, **changes)

    # -- internals ---------------------------------------------------------

    def _single(
        self,
        child: IRNode,
        child_path: NodePath,
        name: str,
        annotation: Any,
    ) -> IRNode | None:
        """Rewrite a field that holds exactly one node.

        Args:
            child: The current child.
            child_path: Where the child sits.
            name: Name of the field.
            annotation: The field's declared type.

        Returns:
            The replacement child, or ``None`` when it was deleted.

        Raises:
            TransformError: If the result cannot be stored in the field.
        """
        result = self.visit(child, child_path)
        if result is None:
            if allows_none(annotation):
                return None
            msg = f"campo {name!r} de {tag_of(child)!r} nao aceita remocao em {child_path}"
            raise TransformError(msg)
        if isinstance(result, IRNode):
            return result
        items = tuple(result)
        if len(items) == 1:
            return items[0]
        msg = (
            f"campo {name!r} guarda um no so, mas a transformacao devolveu "
            f"{len(items)} em {child_path}"
        )
        raise TransformError(msg)

    def _sequence(
        self,
        value: tuple[IRNode, ...],
        path: NodePath,
        name: str,
    ) -> tuple[IRNode, ...] | None:
        """Rewrite a field that holds a tuple of nodes.

        Args:
            value: The current children.
            path: Path of the parent node.
            name: Name of the field.

        Returns:
            The rebuilt tuple, or ``None`` when nothing changed.
        """
        rebuilt: list[IRNode] = []
        changed = False
        for index, item in enumerate(value):
            result = self.visit(item, path.child(name, index))
            if result is None:
                changed = True
                continue
            if isinstance(result, IRNode):
                rebuilt.append(result)
                changed = changed or result is not item
                continue
            items = list(result)
            rebuilt.extend(items)
            changed = changed or len(items) != 1 or items[0] is not item
        return tuple(rebuilt) if changed else None
