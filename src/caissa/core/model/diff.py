"""Semantic comparison of two documents -- the instrument that proves fidelity.

SPEC section 11.3 sets a hard gate: an export/import round trip must preserve at
least 99 % of nodes. That number is only meaningful if something measures it,
and measuring it by comparing files is worthless -- two identical documents
written by two exporters differ in every byte. What matters is whether the
*tree* survived.

:func:`semantic_diff` answers that. It pairs nodes across the two documents,
compares their scalar fields, and reports what was added, removed, changed or
moved, each with a path. The pairing strategy matters:

``"id"``
    Pair by node identity. Correct whenever the pipeline preserves ids, which
    every Caissa exporter does, and immune to reordering.
``"position"``
    Pair by document path. The fallback for a foreign importer that minted new
    ids -- structure is compared even though identity was lost.
``"auto"``
    Use identity when the two documents share enough ids to make it meaningful,
    otherwise fall back to position. This is the default and the right choice
    for a round-trip test that does not know what the exporter did.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from caissa.core.model.base import IRNode, tag_of
from caissa.core.model.ids import ULID
from caissa.core.model.reflect import field_types
from caissa.core.model.visitor import walk

__all__ = [
    "ChangeKind",
    "DiffEntry",
    "DiffReport",
    "MatchStrategy",
    "semantic_diff",
]

MatchStrategy = Literal["id", "position", "auto"]

_AUTO_ID_OVERLAP_THRESHOLD = 0.5


class ChangeKind(StrEnum):
    """What happened to a node between the two documents."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    MOVED = "moved"
    RETYPED = "retyped"


@dataclass(frozen=True, slots=True, kw_only=True)
class DiffEntry:
    """One difference between two documents.

    Attributes:
        kind: What happened.
        path: Where it happened, in the *left* document for removals and in the
            *right* document otherwise.
        node_type: Serialisation tag of the node concerned.
        node_id: Identity of the node concerned.
        field: Name of the field that changed, for ``CHANGED`` entries.
        before: Value in the left document, rendered for display.
        after: Value in the right document, rendered for display.
        other_path: The counterpart path, for ``MOVED`` entries.
    """

    kind: ChangeKind
    path: str
    node_type: str
    node_id: ULID | None = None
    field: str | None = None
    before: str | None = None
    after: str | None = None
    other_path: str | None = None

    def __str__(self) -> str:
        """Render the entry as one readable line."""
        if self.kind is ChangeKind.CHANGED:
            return f"{self.kind.value} {self.path}.{self.field}: {self.before!r} -> {self.after!r}"
        if self.kind is ChangeKind.MOVED:
            return f"{self.kind.value} {self.node_type} {self.other_path} -> {self.path}"
        return f"{self.kind.value} {self.node_type} {self.path}"


@dataclass(frozen=True, slots=True, kw_only=True)
class DiffReport:
    """The outcome of comparing two documents.

    Attributes:
        entries: Every difference found, in document order.
        left_node_count: How many nodes the left document has.
        right_node_count: How many nodes the right document has.
        matched_node_count: How many nodes were paired across the two.
        strategy: Which pairing strategy was actually used.
    """

    entries: tuple[DiffEntry, ...] = ()
    left_node_count: int = 0
    right_node_count: int = 0
    matched_node_count: int = 0
    strategy: str = "auto"

    @property
    def is_identical(self) -> bool:
        """Whether the two documents are semantically the same."""
        return not self.entries

    @property
    def fidelity(self) -> float:
        """Fraction of the left document's nodes that survived, in ``[0, 1]``.

        This is the number SPEC section 11.3 sets a floor of 0.99 on. A node
        counts as surviving when it was paired *and* none of its fields changed;
        a node that came back with a different FEN did not survive in any sense
        that matters.
        """
        if self.left_node_count == 0:
            return 1.0
        damaged = {
            entry.path
            for entry in self.entries
            if entry.kind in (ChangeKind.CHANGED, ChangeKind.RETYPED)
        }
        preserved = self.matched_node_count - len(damaged)
        return max(0.0, min(1.0, preserved / self.left_node_count))

    def of_kind(self, kind: ChangeKind) -> tuple[DiffEntry, ...]:
        """Return only the entries of one kind.

        Args:
            kind: The change kind to filter by.

        Returns:
            The matching entries.
        """
        return tuple(entry for entry in self.entries if entry.kind is kind)

    def summary(self) -> str:
        """Render a one-paragraph report in Brazilian Portuguese.

        Returns:
            A human-readable summary suitable for an export report.
        """
        if self.is_identical:
            return f"Documentos identicos: {self.left_node_count} nos preservados."
        counts = {kind: len(self.of_kind(kind)) for kind in ChangeKind}
        parts = [f"{count} {kind.value}" for kind, count in counts.items() if count]
        return (
            f"Fidelidade {self.fidelity:.2%} "
            f"({self.matched_node_count}/{self.left_node_count} nos pareados). "
            f"Diferencas: {', '.join(parts)}."
        )

    def __str__(self) -> str:
        """Render the summary followed by every entry, one per line."""
        lines = [self.summary()]
        lines.extend(str(entry) for entry in self.entries)
        return "\n".join(lines)


def semantic_diff(
    left: IRNode,
    right: IRNode,
    *,
    match: MatchStrategy = "auto",
    ignore_ids: bool = False,
    ignore_provenance: bool = False,
) -> DiffReport:
    """Compare two documents and report what differs.

    Args:
        left: The reference document -- typically what went into an exporter.
        right: The document to judge -- typically what came back out.
        match: How to pair nodes: by identity, by position, or automatically.
        ignore_ids: Do not report a differing ``id`` as a change. Useful when
            comparing against an importer that legitimately mints fresh ids.
        ignore_provenance: Do not report differing ``provenance`` as a change.
            Useful when the round trip goes through a format that cannot carry
            it and the loss is already recorded as a ``DegradationWarning``.

    Returns:
        The report.
    """
    left_nodes = _index(left)
    right_nodes = _index(right)
    strategy = _choose_strategy(match, left_nodes, right_nodes)
    pairs, left_only, right_only = _pair(left_nodes, right_nodes, strategy)

    skip: set[str] = set()
    if ignore_ids:
        skip.add("id")
    if ignore_provenance:
        skip.add("provenance")

    entries: list[DiffEntry] = []
    for left_path, left_node, right_path, right_node in pairs:
        if type(left_node) is not type(right_node):
            entries.append(
                DiffEntry(
                    kind=ChangeKind.RETYPED,
                    path=right_path,
                    node_type=tag_of(right_node),
                    node_id=right_node.id,
                    before=tag_of(left_node),
                    after=tag_of(right_node),
                    other_path=left_path,
                )
            )
            continue
        if left_path != right_path:
            entries.append(
                DiffEntry(
                    kind=ChangeKind.MOVED,
                    path=right_path,
                    node_type=tag_of(right_node),
                    node_id=right_node.id,
                    other_path=left_path,
                )
            )
        entries.extend(_compare_fields(left_node, right_node, right_path, skip))

    entries.extend(
        DiffEntry(
            kind=ChangeKind.REMOVED,
            path=path,
            node_type=tag_of(node),
            node_id=node.id,
            before=_render(node),
        )
        for path, node in left_only
    )
    entries.extend(
        DiffEntry(
            kind=ChangeKind.ADDED,
            path=path,
            node_type=tag_of(node),
            node_id=node.id,
            after=_render(node),
        )
        for path, node in right_only
    )

    entries.sort(key=lambda entry: (entry.path, entry.field or "", entry.kind.value))
    return DiffReport(
        entries=tuple(entries),
        left_node_count=len(left_nodes),
        right_node_count=len(right_nodes),
        matched_node_count=len(pairs),
        strategy=strategy,
    )


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Indexed:
    """A document flattened into the two lookups the pairing needs."""

    by_path: dict[str, IRNode] = field(default_factory=dict)
    by_id: dict[ULID, tuple[str, IRNode]] = field(default_factory=dict)
    order: tuple[str, ...] = ()

    def __len__(self) -> int:
        """Return how many nodes the document has."""
        return len(self.by_path)


def _index(root: IRNode) -> _Indexed:
    """Flatten a tree into path and identity lookups.

    Args:
        root: The document to index.

    Returns:
        The lookups plus the document order of the paths.
    """
    by_path: dict[str, IRNode] = {}
    by_id: dict[ULID, tuple[str, IRNode]] = {}
    order: list[str] = []
    for path, node in walk(root):
        text = str(path)
        by_path[text] = node
        order.append(text)
        by_id.setdefault(node.id, (text, node))
    return _Indexed(by_path=by_path, by_id=by_id, order=tuple(order))


def _choose_strategy(match: MatchStrategy, left: _Indexed, right: _Indexed) -> str:
    """Decide how to pair nodes.

    Args:
        match: The requested strategy.
        left: The indexed left document.
        right: The indexed right document.

    Returns:
        ``"id"`` or ``"position"``.
    """
    if match != "auto":
        return match
    if not left.by_id:
        return "position"
    shared = len(set(left.by_id) & set(right.by_id))
    ratio = shared / len(left.by_id)
    return "id" if ratio >= _AUTO_ID_OVERLAP_THRESHOLD else "position"


def _pair(
    left: _Indexed,
    right: _Indexed,
    strategy: str,
) -> tuple[
    list[tuple[str, IRNode, str, IRNode]],
    list[tuple[str, IRNode]],
    list[tuple[str, IRNode]],
]:
    """Pair the nodes of two documents.

    Identity pairing runs first when asked for; whatever it leaves unmatched is
    then paired by path, so a document whose ids were partly preserved still
    yields a useful diff instead of a wall of adds and removes.

    Args:
        left: The indexed left document.
        right: The indexed right document.
        strategy: ``"id"`` or ``"position"``.

    Returns:
        The pairs, the left-only nodes and the right-only nodes.
    """
    pairs: list[tuple[str, IRNode, str, IRNode]] = []
    used_left: set[str] = set()
    used_right: set[str] = set()

    if strategy == "id":
        for node_id, (left_path, left_node) in left.by_id.items():
            found = right.by_id.get(node_id)
            if found is None:
                continue
            right_path, right_node = found
            pairs.append((left_path, left_node, right_path, right_node))
            used_left.add(left_path)
            used_right.add(right_path)

    for path in left.order:
        if path in used_left:
            continue
        counterpart = right.by_path.get(path)
        if counterpart is None or path in used_right:
            continue
        pairs.append((path, left.by_path[path], path, counterpart))
        used_left.add(path)
        used_right.add(path)

    left_only = [(path, left.by_path[path]) for path in left.order if path not in used_left]
    right_only = [(path, right.by_path[path]) for path in right.order if path not in used_right]
    return pairs, left_only, right_only


def _compare_fields(
    left: IRNode,
    right: IRNode,
    path: str,
    skip: set[str],
) -> Iterator[DiffEntry]:
    """Compare the non-node fields of two paired nodes.

    Child nodes are skipped: they are paired and compared in their own right, so
    reporting them here would double-count. Everything else -- scalars, value
    objects such as ``RunProps``, tuples of value objects -- is compared by
    equality, which is exact because every IR value type is a frozen dataclass.

    Args:
        left: The node from the left document.
        right: The node from the right document.
        path: Where the pair sits, in the right document.
        skip: Field names not to report on.

    Yields:
        One entry per differing field.
    """
    for name in field_types(type(left)):
        if name in skip:
            continue
        left_value = getattr(left, name)
        right_value = getattr(right, name)
        if _holds_nodes(left_value) or _holds_nodes(right_value):
            yield from _compare_node_field(left_value, right_value, name, path, right)
            continue
        if left_value != right_value:
            yield DiffEntry(
                kind=ChangeKind.CHANGED,
                path=path,
                node_type=tag_of(right),
                node_id=right.id,
                field=name,
                before=_render(left_value),
                after=_render(right_value),
            )


def _compare_node_field(
    left_value: object,
    right_value: object,
    name: str,
    path: str,
    right: IRNode,
) -> Iterator[DiffEntry]:
    """Report a structural change in a field that holds child nodes.

    The children themselves are compared as nodes; what this reports is a change
    in how many there are, which is the signal that content was dropped rather
    than merely edited.

    Args:
        left_value: The field value in the left document.
        right_value: The field value in the right document.
        name: The field name.
        path: Where the pair sits.
        right: The right node, for identity in the entry.

    Yields:
        At most one entry, describing a change in child count.
    """
    left_count = _node_count(left_value)
    right_count = _node_count(right_value)
    if left_count != right_count:
        yield DiffEntry(
            kind=ChangeKind.CHANGED,
            path=path,
            node_type=tag_of(right),
            node_id=right.id,
            field=name,
            before=f"{left_count} no(s)",
            after=f"{right_count} no(s)",
        )


def _holds_nodes(value: object) -> bool:
    """Report whether a field value holds child nodes.

    Args:
        value: A field value.

    Returns:
        ``True`` for a node or a tuple whose first element is one.
    """
    if isinstance(value, IRNode):
        return True
    return isinstance(value, tuple) and bool(value) and isinstance(value[0], IRNode)


def _node_count(value: object) -> int:
    """Count the child nodes a field value holds.

    Args:
        value: A field value.

    Returns:
        The number of nodes.
    """
    if isinstance(value, IRNode):
        return 1
    if isinstance(value, tuple):
        return sum(1 for item in value if isinstance(item, IRNode))
    return 0


def _render(value: object) -> str:
    """Render a value for a diff entry, keeping it short enough to read.

    Args:
        value: Any value.

    Returns:
        A display string, truncated when long.
    """
    if isinstance(value, IRNode):
        text = f"<{tag_of(value)} {value.id}>"
    elif isinstance(value, Mapping):
        text = repr(dict(value))
    else:
        text = repr(value)
    limit = 160
    return text if len(text) <= limit else f"{text[: limit - 3]}..."
