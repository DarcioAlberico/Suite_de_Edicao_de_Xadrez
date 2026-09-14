"""Export, read back, and prove what survived.

SPEC section 11.3 sets a gate: **at least 99 % of the IR's nodes survive a
round trip**. SPEC section 5.2 sets the rule the gate exists to protect: no
exporter may *silently* drop a property. This module is where the two meet.

The measurement
---------------
:func:`export_then_reimport` writes the document, reads the written file back
into the IR with the format's own reader, and compares the two trees with
:func:`~caissa.core.model.diff.semantic_diff`. Every field that differs is then
looked up in the format's :class:`~caissa.export.base.FormatProfile`:

*   the profile says the format cannot carry it -> the loss is **declared**, and
    the export report already named it;
*   the profile says the format carries it fully -> the loss is **silent**, and
    that is a defect, reported as such and counted against the gate.

Two numbers come out of that, and both are printed because either alone
misleads:

``fidelity``
    Nodes that came back byte-for-byte identical. It is the number SPEC
    section 11.3 names, and it is pessimistic: a paragraph that lost only its
    CMYK ink -- a loss the format declared, the user was told about, and no
    reader could have shown anyway -- counts as damaged.
``declared_fidelity``
    Nodes with no *undeclared* loss. It is the number that says whether the
    exporter is honest, which is the property this front exists to guarantee.

What is not allowed to flatter the number
-----------------------------------------
Every exporter can write the serialised IR into its output as a sidecar, and
reading that back would give a perfect score while proving nothing about the
exporter. So :func:`export_then_reimport` reads the *markup* by default, and
when a format has no markup reader at all -- PDF, LaTeX -- the report says
``method="sidecar"`` in so many words. A sidecar measurement is a statement
about serialisation, not about the writer, and it is labelled so that nobody
quotes it as if it were the latter.

Naming the node that caused a loss
----------------------------------
A format that flattens a wrapper -- OOXML has no emphasis element, only a run
with ``w:i`` -- makes a run come back carrying formatting its own node never
set. Charging that to the run reports a silent loss on a node whose profile says
"full", when the wrapper's entry already explained it; moving the wrapper's
identity onto the run instead would report a node that changed type. So the
loss is **attributed**, by two rules narrow enough not to become an excuse:

*   :func:`_flattened_contributions` finds, for each node, the nearest ancestor
    whose disappearance the profile declared, and a property the node **never
    set** is charged there. A property the node *did* set and lost is still its
    own loss, ancestor or not.
*   :func:`_container_support` asks what happened to a container's children. A
    parent whose content changed only because children the format declared it
    could not keep are gone did not lose anything of its own -- but a child the
    format promised to keep, or a change of order among the survivors, is not
    explained and stays silent.

Both are checked from both sides in ``tests/unit/export/test_fidelity.py``,
because a rule that only ever forgives is not a rule.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from caissa.core.model import (
    ULID,
    DegradationReport,
    DegradationWarning,
    Document,
    IRNode,
    ParagraphProps,
    RunProps,
    tag_of,
    walk,
)
from caissa.core.model.diff import DiffReport, semantic_diff
from caissa.core.model.reflect import child_nodes
from caissa.export.base import (
    Capability,
    ExportOptions,
    ExportResult,
    FormatProfile,
    PropertySupport,
    is_specified,
)
from caissa.export.profiles import profile_for

__all__ = [
    "READERS",
    "FidelityError",
    "FidelityReport",
    "FieldLoss",
    "MissingNode",
    "export_then_reimport",
    "measure",
]

MINIMUM_FIDELITY = 0.99
"""The floor SPEC section 11.3 sets on ``declared_fidelity``."""


class FidelityError(RuntimeError):
    """A round trip could not be performed at all."""


@dataclass(frozen=True, slots=True)
class FieldLoss:
    """One field that did not survive the round trip.

    Attributes:
        node_type: Serialisation tag of the node.
        node_id: Identity of the node.
        path: Where the node sits in the tree.
        field: The field, ``"props.tracking"`` for a run property inside the
            property record and ``"caption"`` for a plain node field.
        before: The value that went in, rendered.
        after: The value that came back, rendered.
        capability: What the format's profile says it does with this field.
        reason: The profile's explanation, in Brazilian Portuguese.
        reported: Whether a ``DegradationWarning`` for this property was
            actually recorded on this node during the export.
    """

    node_type: str
    node_id: ULID | None
    path: str
    field: str
    before: str
    after: str
    capability: Capability
    reason: str = ""
    reported: bool = False

    @property
    def is_declared(self) -> bool:
        """Whether the format said in advance it could not carry this."""
        return self.capability is not Capability.FULL

    @property
    def is_silent(self) -> bool:
        """Whether this loss happened with nothing declared and nothing said.

        This is the cardinal sin of SPEC section 5.2, and the only kind of loss
        that counts against the acceptance gate.
        """
        return not self.is_declared

    def __str__(self) -> str:
        """Render the loss as one readable line."""
        mark = "declarada" if self.is_declared else "SILENCIOSA"
        return f"[{mark}] {self.path}.{self.field}: {self.before} -> {self.after}"


@dataclass(frozen=True, slots=True)
class MissingNode:
    """One node that did not come back at all.

    Attributes:
        node_type: Serialisation tag of the node.
        node_id: Its identity.
        path: Where it sat in the original.
        capability: What the profile says about this node type.
        reason: The profile's explanation.
    """

    node_type: str
    node_id: ULID | None
    path: str
    capability: Capability
    reason: str = ""

    @property
    def is_declared(self) -> bool:
        """Whether the format said it cannot represent this node type."""
        return self.capability is not Capability.FULL

    def __str__(self) -> str:
        """Render the missing node as one readable line."""
        mark = "declarado" if self.is_declared else "SILENCIOSO"
        return f"[{mark}] ausente: {self.node_type} em {self.path}"


@dataclass(frozen=True, slots=True, kw_only=True)
class FidelityReport:
    """What survived one export-and-reimport, and what did not.

    Attributes:
        format: The format measured.
        method: ``"markup"`` when the file's own reader rebuilt the tree,
            ``"sidecar"`` when the measurement went through the embedded IR and
            therefore says nothing about the writer.
        node_count: How many nodes went in.
        matched: How many were found again.
        losses: Every field that changed.
        missing: Every node that did not come back.
        added: Nodes present in the re-import that were not in the original.
        diff: The raw diff, for anyone who wants the detail.
        degradation: What the export itself reported.
        result: The export result, for paths and statistics.
    """

    format: str
    method: str = "markup"
    node_count: int = 0
    matched: int = 0
    losses: tuple[FieldLoss, ...] = ()
    missing: tuple[MissingNode, ...] = ()
    added: tuple[str, ...] = ()
    diff: DiffReport = field(default_factory=DiffReport)
    degradation: DegradationReport = field(
        default_factory=lambda: DegradationReport(target_format="")
    )
    result: ExportResult | None = None

    # -- headline numbers --------------------------------------------------

    @property
    def damaged(self) -> frozenset[str]:
        """Paths of nodes that changed in any way."""
        return frozenset(loss.path for loss in self.losses)

    @property
    def silently_damaged(self) -> frozenset[str]:
        """Paths of nodes that lost something nobody declared."""
        return frozenset(loss.path for loss in self.losses if loss.is_silent) | frozenset(
            item.path for item in self.missing if not item.is_declared
        )

    @property
    def preserved(self) -> int:
        """Nodes that came back exactly as they went in."""
        return max(0, self.matched - len(self.damaged))

    @property
    def fidelity(self) -> float:
        """Fraction of nodes that survived untouched, in ``[0, 1]``."""
        if self.node_count == 0:
            return 1.0
        return max(0.0, min(1.0, self.preserved / self.node_count))

    @property
    def declared_fidelity(self) -> float:
        """Fraction of nodes with no *undeclared* loss, in ``[0, 1]``.

        This is the gate. A node that lost only what the format said in advance
        it could not carry is counted as preserved, because the user was told;
        a node that lost anything else is not, however small the loss.
        """
        if self.node_count == 0:
            return 1.0
        intact = self.node_count - len(self.silently_damaged)
        return max(0.0, min(1.0, intact / self.node_count))

    @property
    def silent_losses(self) -> tuple[FieldLoss, ...]:
        """Every loss the format never declared."""
        return tuple(loss for loss in self.losses if loss.is_silent)

    @property
    def undeclared_missing(self) -> tuple[MissingNode, ...]:
        """Every node that vanished without the format saying it would."""
        return tuple(item for item in self.missing if not item.is_declared)

    @property
    def unreported(self) -> tuple[FieldLoss, ...]:
        """Declared losses for which no warning actually reached the report.

        A profile entry that never fires is a promise nobody kept: the user is
        not told, even though the table says they would be.
        """
        return tuple(loss for loss in self.losses if loss.is_declared and not loss.reported)

    @property
    def passes(self) -> bool:
        """Whether this format clears the SPEC section 11.3 gate."""
        return self.declared_fidelity >= MINIMUM_FIDELITY

    # -- breakdowns --------------------------------------------------------

    def by_node_type(self) -> dict[str, tuple[int, int]]:
        """Damage per node type.

        Returns:
            A mapping from serialisation tag to ``(silently damaged, total)``.
        """
        totals: dict[str, int] = {}
        for _, node in self._original_walk:
            totals[tag_of(node)] = totals.get(tag_of(node), 0) + 1
        seen: dict[str, set[str]] = {}
        for loss in self.silent_losses:
            seen.setdefault(loss.node_type, set()).add(loss.path)
        for item in self.undeclared_missing:
            seen.setdefault(item.node_type, set()).add(item.path)
        return {
            tag: (len(seen.get(tag, ())), total) for tag, total in sorted(totals.items())
        }

    def by_property(self, *, silent_only: bool = False) -> dict[str, int]:
        """How many nodes each lost field affected.

        Args:
            silent_only: Count only the losses the format never declared.

        Returns:
            A mapping from field name to count, largest first.
        """
        counts: dict[str, int] = {}
        for loss in self.losses:
            if silent_only and not loss.is_silent:
                continue
            counts[loss.field] = counts.get(loss.field, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def summary(self) -> str:
        """Render the headline in Brazilian Portuguese.

        Returns:
            Two or three lines naming both numbers and the worst offender.
        """
        lines = [
            f"{self.format.upper()} ({self.method}): fidelidade {self.fidelity:.2%}, "
            f"fidelidade declarada {self.declared_fidelity:.2%} "
            f"({self.node_count - len(self.silently_damaged)}/{self.node_count} nos "
            f"sem perda nao declarada)."
        ]
        if self.silent_losses or self.undeclared_missing:
            worst = sorted(
                self.by_property(silent_only=True).items(),
                key=lambda item: (-item[1], item[0]),
            )[:3]
            lines.append(
                "Perdas silenciosas: "
                + ", ".join(f"{name} ({count})" for name, count in worst)
                + "."
            )
        else:
            lines.append("Nenhuma perda silenciosa: tudo o que mudou estava declarado.")
        if self.unreported:
            lines.append(
                f"Atencao: {len(self.unreported)} perda(s) declarada(s) no perfil "
                "nao geraram aviso no relatorio de exportacao."
            )
        return "\n".join(lines)

    def __str__(self) -> str:
        """Render the summary followed by every silent loss."""
        lines = [self.summary()]
        lines.extend(str(loss) for loss in self.silent_losses)
        lines.extend(str(item) for item in self.undeclared_missing)
        return "\n".join(lines)

    # -- internals ---------------------------------------------------------

    _original_walk: tuple[tuple[str, IRNode], ...] = ()


# --------------------------------------------------------------------------- #
# The readers
# --------------------------------------------------------------------------- #
def _read_html(path: Path) -> Document:
    """Read a page back. See :func:`caissa.export.html.read_html`."""
    from caissa.export.html import read_html

    return read_html(path)


def _read_epub(path: Path) -> Document:
    """Read a package back. See :func:`caissa.export.epub.read_epub`."""
    from caissa.export.epub import read_epub

    return read_epub(path)


def _read_docx(path: Path) -> Document:
    """Read a Word file back. See :func:`caissa.export.docx.read_docx`."""
    from caissa.export.docx import read_docx

    return read_docx(path)


def _read_latex(path: Path) -> Document:
    """Read a LaTeX project back. See :func:`caissa.export.latex.read_latex`."""
    from caissa.export.latex import read_latex

    return read_latex(path)


def _read_pdf(path: Path) -> Document:
    """Read a PDF back. See :func:`caissa.export.pdf.read_pdf`."""
    from caissa.export.pdf import read_pdf

    return read_pdf(path)


READERS: Mapping[str, tuple[Callable[[Path], Document], str]] = {
    "html": (_read_html, "markup"),
    "epub": (_read_epub, "markup"),
    "docx": (_read_docx, "markup"),
    "latex": (_read_latex, "sidecar"),
    "pdf": (_read_pdf, "sidecar"),
}
"""Per-format reader and what a measurement through it actually proves.

``"markup"`` means the reader parses the file the way a browser or Word would,
so the number measures the writer. ``"sidecar"`` means it recovers the embedded
IR, so the number measures :mod:`json` -- true, useful for "reopen my export",
and not evidence about the writer. The distinction is carried into
:attr:`FidelityReport.method` so that it survives into the report.
"""


def _exporter_for(format_name: str) -> Any:
    """Return the exporter class for a format name.

    Args:
        format_name: One of the five format names.

    Returns:
        The exporter class.

    Raises:
        FidelityError: No such format.
    """
    from caissa.export import EXPORTERS

    try:
        return EXPORTERS[format_name]
    except KeyError as error:  # pragma: no cover - guarded by the caller
        raise FidelityError(f"Formato desconhecido: {format_name}") from error


# --------------------------------------------------------------------------- #
# The measurement
# --------------------------------------------------------------------------- #
def export_then_reimport(
    document: Document,
    format_name: str,
    *,
    options: ExportOptions | None = None,
    directory: Path | None = None,
) -> FidelityReport:
    """Write a document, read it back, and report what survived.

    Args:
        document: The IR to measure.
        format_name: ``"html"``, ``"epub"``, ``"docx"``, ``"pdf"`` or
            ``"latex"``.
        options: Export settings. The default keeps the IR sidecar, which is a
            product feature and is *not* used by the markup readers.
        directory: Where to write. A temporary directory is used and left
            behind when omitted, so a failing measurement can be inspected.

    Returns:
        The report.

    Raises:
        FidelityError: The format has no reader, or the file could not be read
            back at all.
    """
    if format_name not in READERS:
        raise FidelityError(f"Formato sem leitor de volta: {format_name}")
    reader, method = READERS[format_name]
    exporter = _exporter_for(format_name)()
    root = Path(directory) if directory is not None else Path(tempfile.mkdtemp(prefix="caissa-"))
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"fidelidade{exporter.suffix}"

    result = exporter.export(document, destination, options=options)
    try:
        reimported = reader(result.path)
    except Exception as error:
        raise FidelityError(
            f"O arquivo {result.path.name} nao pode ser relido: {error}"
        ) from error
    return measure(
        document,
        reimported,
        format_name,
        method=method,
        degradation=result.degradation,
        result=result,
    )


def measure(
    original: Document,
    reimported: Document,
    format_name: str,
    *,
    method: str = "markup",
    degradation: DegradationReport | None = None,
    result: ExportResult | None = None,
) -> FidelityReport:
    """Compare two trees and classify every difference.

    Split out from :func:`export_then_reimport` so a test can feed it a
    hand-built pair without touching the disk.

    Args:
        original: What went in.
        reimported: What came back.
        format_name: The format, for the profile lookup.
        method: ``"markup"`` or ``"sidecar"``; see :data:`READERS`.
        degradation: What the export reported, for the cross-check that a
            declared loss actually produced a warning.
        result: The export result, carried into the report.

    Returns:
        The report.
    """
    profile = profile_for(format_name)
    report = degradation or DegradationReport(target_format=format_name)
    reported = _reported_index(report.warnings)

    diff = semantic_diff(original, reimported)
    left = {node.id: (str(path), node) for path, node in walk(original)}
    right = {node.id: node for _, node in walk(reimported)}
    flattened = _flattened_contributions(original, profile, right)
    owners = _owning_fields(original)

    losses: list[FieldLoss] = []
    missing: list[MissingNode] = []
    for identity, (path, node) in left.items():
        other = right.get(identity)
        if other is None:
            support = _missing_support(node, profile, owners)
            missing.append(
                MissingNode(
                    node_type=tag_of(node),
                    node_id=identity,
                    path=path,
                    capability=support.capability,
                    reason=support.detail or "",
                )
            )
            continue
        if type(other) is not type(node):
            support = profile.node_support(tag_of(node))
            losses.append(
                FieldLoss(
                    node_type=tag_of(node),
                    node_id=identity,
                    path=path,
                    field="__type__",
                    before=tag_of(node),
                    after=tag_of(other),
                    capability=support.capability,
                    reason=support.detail or "",
                    reported=reported.get((identity, tag_of(node)), False)
                    or reported.get((None, tag_of(node)), False),
                )
            )
            continue
        losses.extend(
            _compare(node, other, path, profile, reported, left, flattened.get(identity))
        )

    added = tuple(
        str(path) for path, node in walk(reimported) if node.id not in left
    )
    return FidelityReport(
        format=format_name,
        method=method,
        node_count=len(left),
        matched=len(left) - len(missing),
        losses=tuple(losses),
        missing=tuple(missing),
        added=added,
        diff=diff,
        degradation=report,
        result=result,
        _original_walk=tuple((str(path), node) for path, node in walk(original)),
    )


# --------------------------------------------------------------------------- #
# Classifying one difference
# --------------------------------------------------------------------------- #
_PROPERTY_FIELDS: Mapping[str, str] = {
    "props": "auto",
    "run_props": "run",
    "default_run": "run",
    "mark_props": "run",
}
"""Node fields that hold a property record, and which table describes them."""


def _compare(
    left: IRNode,
    right: IRNode,
    path: str,
    profile: FormatProfile,
    reported: Mapping[tuple[ULID | None, str], bool],
    originals: Mapping[ULID, tuple[str, IRNode]] | None = None,
    contribution: _Attribution | None = None,
) -> list[FieldLoss]:
    """Compare one matched pair of nodes field by field.

    Args:
        left: The original node.
        right: The re-imported node.
        path: Where the node sits.
        profile: The format's capability table.
        reported: Which warnings the export actually recorded.
        originals: Every node of the original tree by identity, so that a
            container whose children changed can ask what happened to them.
        contribution: What a flattened ancestor pushed onto this node; see
            :func:`_flattened_contributions`.

    Returns:
        One :class:`FieldLoss` per differing field, or per differing property
        inside a property record.
    """
    tag = tag_of(left)
    losses: list[FieldLoss] = []
    for descriptor in dataclasses.fields(left):
        name = descriptor.name
        if name == "id":
            continue
        before = getattr(left, name, None)
        after = getattr(right, name, None)
        if before == after:
            continue
        kind = _PROPERTY_FIELDS.get(name)
        if kind is not None and isinstance(before, (RunProps, ParagraphProps)):
            inherited = contribution
            declared = profile.node_support(tag)
            if not declared.capability.is_lossless:
                # The same rule the node *fields* below get: a format that
                # declared it cannot hold this node has declared what is
                # inside it too. A footnote that moved to word/footnotes.xml
                # left its block formatting behind, because CT_FtnEdn is a
                # sequence of paragraphs and has no formatting of its own.
                inherited = _Attribution(support=declared, node_id=left.id, prop=tag)
            losses.extend(
                _compare_props(
                    before,
                    after,
                    name,
                    tag,
                    path,
                    left.id,
                    profile,
                    reported,
                    inherited,
                )
            )
            continue
        support = profile.node_field_support(tag, name).resolve(before)
        key = f"{tag}.{name}"
        attribution: _Attribution | None = None
        if _holds_nodes(before) or _holds_nodes(after):
            # Child nodes are compared on their own; a differing container is
            # a symptom, not a loss of its own.
            if _same_ids(before, after):
                continue
            if support.capability.is_lossless:
                # Nothing was declared about this field, so ask what happened
                # to the children instead.
                attribution = _container_support(before, after, profile, originals)
        if attribution is None:
            if support.capability.is_lossless:
                # A format that declared it cannot carry this *node* has
                # declared everything inside it too: "a partida viaja como PGN"
                # is a statement about the moves, the headers and the comments
                # at once -- and the warning it raised is the one about the node.
                support = profile.node_support(tag)
                key = tag
            attribution = _Attribution(support=support, node_id=left.id, prop=key)
        losses.append(
            FieldLoss(
                node_type=tag,
                node_id=left.id,
                path=path,
                field=name,
                before=_render(before),
                after=_render(after),
                capability=attribution.support.capability,
                reason=attribution.support.detail or "",
                reported=reported.get((attribution.node_id, attribution.prop), False)
                or reported.get((None, attribution.prop), False),
            )
        )
    return losses


def _container_support(
    before: object,
    after: object,
    profile: FormatProfile,
    originals: Mapping[ULID, tuple[str, IRNode]] | None,
) -> _Attribution | None:
    """Judge a container whose children are no longer the same list.

    A paragraph whose ``content`` changed because the anchor inside it became a
    Word bookmark did not lose its content: the anchor's own profile entry
    already said the anchor would stop being a node. Reporting the parent as
    silently damaged as well counts the same declared substitution twice, and
    hides it behind a node whose profile says "full".

    So a container is judged by *what happened to the children*: when every
    child that is gone is one the format declared it could not keep, and every
    child still present is still in its original order, the container changed
    for a reason that is already on the record.

    Args:
        before: The original field value.
        after: The re-imported one.
        profile: The format's capability table.
        originals: Every node of the original tree by identity.

    Returns:
        The declared support to attribute the change to, or ``None`` when the
        change is not explained -- in which case the caller judges it as before
        and it stays silent.
    """
    if originals is None:
        return None
    left_ids = _ids(before)
    right_ids = _ids(after)
    kept = [identity for identity in right_ids if identity in set(left_ids)]
    survivors = [identity for identity in left_ids if identity in set(right_ids)]
    if kept != survivors:
        # The children that did survive came back in a different order. That is
        # a change to the container itself, and nobody declared it.
        return None
    explanation: _Attribution | None = None
    restructured: _Attribution | None = None
    for identity in left_ids:
        found = originals.get(identity)
        if found is None:
            return None
        support = profile.node_support(tag_of(found[1]))
        if not support.capability.is_lossless:
            restructured = restructured or _Attribution(
                support=support, node_id=identity, prop=tag_of(found[1])
            )
        if identity in set(right_ids):
            continue
        if support.capability.is_lossless:
            # A child the format promised to keep is gone. Nobody declared
            # that, and the parent is the only place it shows.
            return None
        explanation = explanation or _Attribution(
            support=support, node_id=identity, prop=tag_of(found[1])
        )
    if explanation is not None:
        return explanation
    # Nothing was dropped, so the list grew: a figure that flattened into a
    # caption and a picture leaves more children than it had. That is the same
    # declared substitution seen from the parent -- but only when this
    # container actually held something the format said it would restructure.
    return restructured


def _compare_props(
    before: RunProps | ParagraphProps,
    after: Any,
    field_name: str,
    tag: str,
    path: str,
    node_id: ULID | None,
    profile: FormatProfile,
    reported: Mapping[tuple[ULID | None, str], bool],
    contribution: _Attribution | None = None,
) -> list[FieldLoss]:
    """Compare two property records property by property.

    Comparing them whole would answer "the formatting changed", which is not
    actionable. Comparing them field by field answers "the tracking is gone",
    which is, and it is the granularity the capability table speaks at.

    Args:
        before: The original record.
        after: The re-imported record, or ``None``.
        field_name: Which field of the node holds it.
        tag: The node's serialisation tag.
        path: Where the node sits.
        node_id: The node's identity.
        profile: The format's capability table.
        reported: Which warnings the export actually recorded.
        contribution: What a flattened ancestor pushed onto this node.

    Returns:
        One loss per differing property.
    """
    empty = type(before)()
    other = after if isinstance(after, type(before)) else empty
    is_run = isinstance(before, RunProps)
    lookup = profile.run_support if is_run else profile.paragraph_support
    losses: list[FieldLoss] = []
    for descriptor in dataclasses.fields(before):
        original = getattr(before, descriptor.name)
        returned = getattr(other, descriptor.name)
        if original == returned:
            continue
        if isinstance(original, RunProps):
            # ``default_run`` and ``mark_props`` are run records living inside a
            # paragraph record. Judging them by the paragraph table would call a
            # declared run loss silent -- unless the whole field is declared
            # lost, in which case nothing inside it can be a surprise.
            outer = lookup(descriptor.name)
            if not outer.capability.is_lossless:
                losses.append(
                    FieldLoss(
                        node_type=tag,
                        node_id=node_id,
                        path=path,
                        field=f"{field_name}.{descriptor.name}",
                        before=_render(original),
                        after=_render(returned),
                        capability=outer.capability,
                        reason=outer.detail or "",
                        reported=reported.get((node_id, descriptor.name), False)
                        or reported.get((None, descriptor.name), False),
                    )
                )
                continue
            losses.extend(
                _compare_props(
                    original,
                    returned,
                    f"{field_name}.{descriptor.name}",
                    tag,
                    path,
                    node_id,
                    profile,
                    reported,
                    contribution,
                )
            )
            continue
        support = lookup(descriptor.name).resolve(original)
        blame = _Attribution(support=support, node_id=node_id, prop=descriptor.name)
        if support.capability.is_lossless and contribution is not None and (
            not is_specified(original) or contribution.node_id == node_id
        ):
            # The node never asked for this property, so it cannot have lost
            # it: the value came *in* from an ancestor the format flattened
            # into this run. OOXML has no emphasis element, only a run with
            # ``w:i``, and the wrapper's profile entry already says so. What
            # would be wrong is to move the wrapper's identity onto the run --
            # that would report a node that changed type. Naming the wrapper as
            # the cause is the honest half of the same fact.
            blame = contribution
        losses.append(
            FieldLoss(
                node_type=tag,
                node_id=node_id,
                path=path,
                field=f"{field_name}.{descriptor.name}",
                before=_render(original),
                after=_render(returned),
                capability=blame.support.capability,
                reason=blame.support.detail or "",
                reported=reported.get((blame.node_id, blame.prop), False)
                or reported.get((None, blame.prop), False),
            )
        )
    return losses


@dataclass(frozen=True, slots=True)
class _Attribution:
    """A declaration that explains a difference, and where it was reported.

    A loss attributed to somewhere else has to carry that somewhere else with
    it, or :attr:`FidelityReport.unreported` counts the export as silent about
    a loss the export did in fact name -- just under the node that caused it.

    Attributes:
        support: What the profile says about the cause.
        node_id: The node the warning was recorded against.
        prop: The property name the warning used.
    """

    support: PropertySupport
    node_id: ULID | None
    prop: str


def _flattened_contributions(
    document: Document,
    profile: FormatProfile,
    right: Mapping[ULID, IRNode],
) -> dict[ULID, _Attribution]:
    """Find, for every node, the ancestor whose formatting was pushed onto it.

    Two things push formatting down a tree and disappear on the way:

    *   an **inline wrapper the format has no element for**. OOXML is flat:
        there is no emphasis element, only a run with ``w:i``. The wrapper is
        genuinely gone from the file and its profile entry says so; what
        survives is its meaning, on every run it contained.
    *   a paragraph's **run defaults**. ``ParagraphProps.default_run`` means
        "every run in this paragraph starts from here"; a format with nowhere
        to put that has to write it onto each run instead.

    Both are declared in the profile, and both make a run come back carrying
    properties its own node never set. This walk records which declaration is
    responsible, so :func:`_compare_props` can name it instead of reporting a
    silent loss on the run.

    Args:
        document: The original tree.
        profile: The format's capability table.
        right: The re-imported nodes by identity, to check that the wrapper
            really is gone rather than merely lossy.

    Returns:
        A mapping from node identity to the nearest declaration that explains
        formatting arriving from above.
    """
    contributions: dict[ULID, _Attribution] = {}
    defaults = profile.paragraph_support("default_run")

    def descend(node: IRNode, inherited: _Attribution | None) -> None:
        found = inherited
        props = getattr(node, "props", None)
        if (
            isinstance(props, ParagraphProps)
            and props.default_run is not None
            and not defaults.capability.is_lossless
        ):
            found = _Attribution(support=defaults, node_id=node.id, prop="default_run")
        for child in _children(node):
            own = found
            tag = tag_of(child)
            node_support = profile.node_support(tag)
            if not node_support.capability.is_lossless and child.id not in right:
                own = _Attribution(support=node_support, node_id=child.id, prop=tag)
            if own is not None:
                contributions[child.id] = own
            descend(child, own)

    descend(document, None)
    return contributions


def _children(node: IRNode) -> tuple[IRNode, ...]:
    """Every IR node one node holds directly.

    Args:
        node: The parent.

    Returns:
        Its child nodes, in field order.
    """
    found: list[IRNode] = []
    for descriptor in dataclasses.fields(node):
        if descriptor.name == "id":
            continue
        value = getattr(node, descriptor.name, None)
        if isinstance(value, IRNode):
            found.append(value)
        elif isinstance(value, (tuple, list)):
            found.extend(item for item in value if isinstance(item, IRNode))
    return tuple(found)


def _reported_index(
    warnings: Sequence[DegradationWarning],
) -> dict[tuple[ULID | None, str], bool]:
    """Index the export's warnings by node and property.

    Args:
        warnings: What the export reported.

    Returns:
        A set-like mapping keyed by ``(node id, property)`` and by
        ``(None, property)``, the second so that a property capped by the
        noise limit still counts as reported.
    """
    index: dict[tuple[ULID | None, str], bool] = {}
    for warning in warnings:
        index[(warning.node_id, warning.property)] = True
        index[(None, warning.property)] = True
    return index


def _owning_fields(root: IRNode) -> dict[ULID, tuple[str, str]]:
    """Map every node to ``(parent tag, field)`` -- the field that holds it.

    Args:
        root: The original document.

    Returns:
        The owner of each node but the root.
    """
    owners: dict[ULID, tuple[str, str]] = {}
    for _, node in walk(root):
        for name, _index, child in child_nodes(node):
            owners[child.id] = (tag_of(node), name)
    return owners


def _missing_support(
    node: IRNode, profile: FormatProfile, owners: Mapping[ULID, tuple[str, str]]
) -> PropertySupport:
    """What the profile said about a node that did not come back.

    The node's own declaration first. When that is lossless, the field that
    held it answers instead: a format that declared *"o cabecalho de secao
    nao e gravado"* declared the text inside the header too -- the user was
    told, which is what separates a declared loss from a silent one. Only
    the immediate owner is consulted: a declaration two levels up is about
    a different field.

    Args:
        node: The node that vanished.
        profile: The format's profile.
        owners: Each node's ``(parent tag, field)``.

    Returns:
        The declaration that covers the loss, lossless when none does.
    """
    support = profile.node_support(tag_of(node))
    if not support.capability.is_lossless:
        return support
    owner = owners.get(node.id)
    if owner is None:
        return support
    field_support = profile.node_field_support(*owner)
    return field_support if not field_support.capability.is_lossless else support


def _holds_nodes(value: object) -> bool:
    """Whether a value is a node or a collection of nodes.

    Args:
        value: The field value.

    Returns:
        ``True`` when the value carries IR nodes.
    """
    if isinstance(value, IRNode):
        return True
    if isinstance(value, (tuple, list)):
        return any(isinstance(item, IRNode) for item in value)
    return False


def _same_ids(left: object, right: object) -> bool:
    """Whether two node containers hold the same identities in the same order.

    Args:
        left: The original value.
        right: The re-imported value.

    Returns:
        ``True`` when the children are the same nodes, so the difference lies
        inside them and is reported there.
    """
    return _ids(left) == _ids(right)


def _ids(value: object) -> tuple[ULID, ...]:
    """Collect the identities a container holds.

    Args:
        value: The field value.

    Returns:
        The identities, in order.
    """
    if isinstance(value, IRNode):
        return (value.id,)
    if isinstance(value, (tuple, list)):
        return tuple(item.id for item in value if isinstance(item, IRNode))
    return ()


def _render(value: object) -> str:
    """Render a value for a report line.

    Args:
        value: The value.

    Returns:
        A short string.
    """
    if value is None:
        return "nao definido"
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."


def measure_all(
    document: Document,
    formats: Iterable[str] = ("html", "epub", "docx", "pdf", "latex"),
    *,
    options: ExportOptions | None = None,
    directory: Path | None = None,
) -> dict[str, FidelityReport]:
    """Measure one document across several formats.

    Args:
        document: The IR to measure.
        formats: Which formats to write.
        options: Export settings.
        directory: Where to write; one sub-directory per format.

    Returns:
        A report per format, keyed by format name.
    """
    root = Path(directory) if directory is not None else Path(tempfile.mkdtemp(prefix="caissa-"))
    return {
        name: export_then_reimport(
            document, name, options=options, directory=root / name
        )
        for name in formats
    }
