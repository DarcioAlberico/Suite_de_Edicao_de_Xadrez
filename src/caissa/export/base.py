"""The exporter contract: one interface, and the golden rule made mechanical.

SPEC section 5.2 states the rule this whole front exists to honour:

    Nenhum exportador pode *silenciosamente* descartar uma propriedade. Se um
    formato nao suporta algo, o exportador registra um ``DegradationWarning``
    visivel no relatorio de exportacao.

A rule enforced by discipline alone is a rule that decays. So this module turns
it into a *table lookup*. Every output format declares a
:class:`FormatProfile` -- an explicit, reviewable statement of what it can carry
for every field of :class:`~caissa.core.model.props.RunProps`, every field of
:class:`~caissa.core.model.props.ParagraphProps`, and every structural feature.
:meth:`ExportContext.audit_run_props` then walks a property record and records a
warning for every field that is *set* and whose declared capability is anything
short of :attr:`Capability.FULL`.

The consequence is the one that matters: adding a run property to the IR without
saying what each of the five formats does with it makes
``tests/unit/export/test_degradation.py`` fail. A property cannot be dropped
silently because a property cannot even be *ignored* silently.

Noise control
-------------
A four-hundred-page book with tracking on every run would otherwise produce forty
thousand identical warnings, and a report nobody reads is the same as no report.
:class:`ExportContext` therefore emits at most
:attr:`ExportOptions.max_warnings_per_property` warnings for any one property and
finishes with a single roll-up naming the true count. Nothing is hidden; the
first offenders are named with their node ids, and the tally is exact.

Origem do padrao de ida-e-volta: ``PGN_Live_Editor/services/export_service.py``
(nada e gravado sem ser relido e conferido). Absorvido em 2026-09-07 e
generalizado de PGN para os cinco formatos -- ver :mod:`caissa.export.fidelity`.
"""

from __future__ import annotations

import abc
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from caissa.core.model import (
    DegradationKind,
    DegradationRecorder,
    DegradationReport,
    DegradationWarning,
    Document,
    IRNode,
    ParagraphProps,
    RunProps,
    StyleSheet,
    tag_of,
)

__all__ = [
    "PARAGRAPH_PROPERTY_NAMES",
    "RUN_PROPERTY_NAMES",
    "Capability",
    "ExportContext",
    "ExportError",
    "ExportOptions",
    "ExportResult",
    "Exporter",
    "FormatProfile",
    "PropertySupport",
    "approximate",
    "full",
    "is_specified",
    "substitute",
    "unsupported",
]


class ExportError(RuntimeError):
    """An export could not be produced at all.

    Distinct from a degradation: a degradation is a file that was written and is
    honest about what it lost, while this is no file.
    """


class Capability(StrEnum):
    """How faithfully a format carries one property.

    The four values line up one-for-one with the four verbs of
    :class:`~caissa.core.model.degradation.DegradationRecorder`, so the audit is a
    dispatch rather than a decision.
    """

    FULL = "full"
    APPROXIMATE = "approximate"
    SUBSTITUTE = "substitute"
    NONE = "none"

    @property
    def is_lossless(self) -> bool:
        """Whether this capability carries the property exactly."""
        return self is Capability.FULL


@dataclass(frozen=True, slots=True)
class PropertySupport:
    """What one format does with one property.

    Attributes:
        capability: How faithfully the property survives.
        detail: Why the format cannot do better, in Brazilian Portuguese. Shown
            to the user, so it names the mechanism rather than the field.
        replacement: What is written instead, for the substituted and
            approximated cases.
        by_value: Per-value override, keyed by the value's key. Small caps are
            the motivating case: DOCX carries ``synthetic`` exactly and can only
            fake ``real``, so the capability depends on what the author asked
            for, not merely on which property it is.
        value_key: How to derive the ``by_value`` key from a value. The default
            uses an enum's own value, or ``str``. Colour is why this exists: the
            question is never "which colour" but "which colour *space*", and a
            CMYK ink surviving as sRGB is a different outcome from an RGB one
            surviving exactly.
    """

    capability: Capability = Capability.FULL
    detail: str | None = None
    replacement: str | None = None
    by_value: Mapping[str, PropertySupport] = field(default_factory=dict)
    value_key: Callable[[Any], str] | None = None

    def resolve(self, value: object) -> PropertySupport:
        """Return the support that applies to a concrete value.

        Args:
            value: The value the document asked for.

        Returns:
            This support, or the per-value override when one matches.
        """
        if not self.by_value:
            return self
        if self.value_key is not None:
            try:
                key = self.value_key(value)
            except Exception:  # pragma: no cover - a key function must never break an export
                return self
        elif isinstance(value, StrEnum):
            key = value.value
        else:
            key = str(value)
        return self.by_value.get(key, self)


def full(detail: str | None = None) -> PropertySupport:
    """Build a lossless support entry.

    Args:
        detail: Optional note about the mechanism used.

    Returns:
        The support entry.
    """
    return PropertySupport(capability=Capability.FULL, detail=detail)


def approximate(detail: str, replacement: str | None = None) -> PropertySupport:
    """Build an approximated support entry.

    Args:
        detail: Why the format cannot be exact.
        replacement: What is written instead.

    Returns:
        The support entry.
    """
    return PropertySupport(
        capability=Capability.APPROXIMATE, detail=detail, replacement=replacement
    )


def substitute(detail: str, replacement: str) -> PropertySupport:
    """Build a substituted support entry.

    Args:
        detail: Why a different mechanism was needed.
        replacement: The mechanism that stood in.

    Returns:
        The support entry.
    """
    return PropertySupport(
        capability=Capability.SUBSTITUTE, detail=detail, replacement=replacement
    )


def unsupported(detail: str) -> PropertySupport:
    """Build a dropped-property support entry.

    Args:
        detail: Why the format cannot carry the property at all.

    Returns:
        The support entry.
    """
    return PropertySupport(capability=Capability.NONE, detail=detail)


RUN_PROPERTY_NAMES: tuple[str, ...] = tuple(f.name for f in fields(RunProps))
"""Every field of :class:`~caissa.core.model.props.RunProps`, in declaration order.

Derived from the dataclass rather than typed out, so a property added to the IR
appears here on the next import and every profile is immediately asked about it.
"""

PARAGRAPH_PROPERTY_NAMES: tuple[str, ...] = tuple(f.name for f in fields(ParagraphProps))
"""Every field of :class:`~caissa.core.model.props.ParagraphProps`."""


_UNSET_SENTINELS: tuple[object, ...] = (None, (), "", {})


def is_specified(value: object) -> bool:
    """Whether a property field carries an author decision.

    ``None`` means "not specified at this level" throughout the IR, and an empty
    tuple means the same for the sequence-valued fields. Auditing unset fields
    would drown the report in warnings about formatting nobody asked for.

    Args:
        value: A field value.

    Returns:
        Whether the field was specified.
    """
    if value is None:
        return False
    if isinstance(value, (tuple, list, dict, str)) and len(value) == 0:
        return False
    return True


@dataclass(frozen=True, slots=True)
class FormatProfile:
    """Everything one output format can and cannot carry.

    This is a specification, not an implementation detail: it is the document a
    reviewer reads to answer "what does our EPUB do with spot colour?" without
    reading the EPUB writer. The exporter is then *checked against* it.

    Attributes:
        name: Format name, matching :attr:`Exporter.format_name`.
        run: Support for each :class:`~caissa.core.model.props.RunProps` field.
            Fields absent from the mapping are considered fully supported.
        paragraph: Support for each
            :class:`~caissa.core.model.props.ParagraphProps` field.
        features: Support for named structural features -- ``"columns"``,
            ``"footnotes"``, ``"vector_diagram"`` and so on. Exporters look these
            up by name when they reach the corresponding construct.
        nodes: Support keyed by node serialisation tag, for whole node types a
            format cannot represent.
        node_fields: Support keyed by ``"tag.field"``, for individual fields of
            a node the format cannot carry -- the scan rectangle a diagram came
            from, say, which no reader of the file has anywhere to put. A
            ``"*.field"`` key applies to that field on every node type, which is
            how ``provenance`` is declared once instead of forty-nine times.
        vector_diagrams: Whether diagrams leave as vector art. A ``False`` here
            is the failure this product cares about most (SPEC section 8).
    """

    name: str
    run: Mapping[str, PropertySupport] = field(default_factory=dict)
    paragraph: Mapping[str, PropertySupport] = field(default_factory=dict)
    features: Mapping[str, PropertySupport] = field(default_factory=dict)
    nodes: Mapping[str, PropertySupport] = field(default_factory=dict)
    node_fields: Mapping[str, PropertySupport] = field(default_factory=dict)
    vector_diagrams: bool = True

    def run_support(self, name: str) -> PropertySupport:
        """Return the support for a run property.

        Args:
            name: The field name.

        Returns:
            The declared support, defaulting to lossless.
        """
        return self.run.get(name, _FULL)

    def paragraph_support(self, name: str) -> PropertySupport:
        """Return the support for a paragraph property.

        Args:
            name: The field name.

        Returns:
            The declared support, defaulting to lossless.
        """
        return self.paragraph.get(name, _FULL)

    def feature_support(self, name: str) -> PropertySupport:
        """Return the support for a named structural feature.

        Args:
            name: The feature name.

        Returns:
            The declared support, defaulting to lossless.
        """
        return self.features.get(name, _FULL)

    def node_support(self, tag: str) -> PropertySupport:
        """Return the support for a whole node type.

        Args:
            tag: The node's serialisation tag.

        Returns:
            The declared support, defaulting to lossless.
        """
        return self.nodes.get(tag, _FULL)

    def node_field_support(self, tag: str, field_name: str) -> PropertySupport:
        """Return the support for one field of one node type.

        The specific declaration wins over the wildcard, so a format that keeps
        provenance on diagrams but nowhere else says so by declaring both.

        Args:
            tag: The node's serialisation tag.
            field_name: The dataclass field name.

        Returns:
            The declared support, defaulting to lossless.
        """
        specific = self.node_fields.get(f"{tag}.{field_name}")
        if specific is not None:
            return specific
        return self.node_fields.get(f"*.{field_name}", _FULL)

    def lossy_run_properties(self) -> tuple[str, ...]:
        """Names of the run properties this format cannot carry exactly.

        Returns:
            The property names, in IR declaration order.
        """
        return tuple(
            name
            for name in RUN_PROPERTY_NAMES
            if not self.run_support(name).capability.is_lossless
            or self.run_support(name).by_value
        )


_FULL = PropertySupport()


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportOptions:
    """Settings shared by every exporter.

    Attributes:
        embed_fonts: Embed and subset the fonts the document names, so a chess
            book keeps its own piece glyphs on a machine that has never seen
            them.
        vector_diagrams: Require vector diagrams. When a format cannot honour
            this the exporter records a rasterisation warning rather than
            quietly shipping pixels.
        diagram_dpi: Resolution of the raster fallback, used only where vector
            art is impossible.
        embed_ir: Write the serialised IR into the container as a sidecar. It is
            what lets a re-import be exact, and it is *never* counted towards a
            fidelity measurement -- see :mod:`caissa.export.fidelity`.
        max_warnings_per_property: Cap on individual warnings per property
            before the recorder switches to counting. Zero means no cap.
        dark_mode: Emit a dark colour scheme alongside the light one, where the
            format supports it.
        interactive: Emit interactive game replay, where the format supports it.
        language: Override for the document language; ``None`` uses the
            document's own metadata.
        page_break_between_chapters: Start each level-1 heading on a new page or
            in a new file, depending on the format.
        include_toc: Emit a table of contents even when the body has no
            :class:`~caissa.core.model.blocks.TableOfContents` node.
        pretty: Indent generated markup. Costs bytes; helps a reviewer.
    """

    embed_fonts: bool = True
    vector_diagrams: bool = True
    diagram_dpi: int = 600
    embed_ir: bool = True
    max_warnings_per_property: int = 25
    dark_mode: bool = True
    interactive: bool = False
    language: str | None = None
    page_break_between_chapters: bool = True
    include_toc: bool = True
    pretty: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportResult:
    """What one export produced and what it cost.

    Attributes:
        format: The format written.
        path: The primary artefact -- the ``.docx``, the ``.epub``, the
            ``index.html``.
        artifacts: Every file written, the primary one included.
        degradation: What the format could not carry.
        notes: Remarks for the user that are not degradations, e.g. "a fonte
            Merida foi subconjuntada para 21 glifos".
        stats: Counters worth showing: nodes written, diagrams drawn, bytes.
    """

    format: str
    path: Path
    artifacts: tuple[Path, ...] = ()
    degradation: DegradationReport = field(
        default_factory=lambda: DegradationReport(target_format="")
    )
    notes: tuple[str, ...] = ()
    stats: Mapping[str, int] = field(default_factory=dict)

    @property
    def is_lossless(self) -> bool:
        """Whether the export carried everything the document asked for."""
        return self.degradation.is_lossless

    def summary(self) -> str:
        """Render a user-facing summary in Brazilian Portuguese.

        Returns:
            One paragraph naming the file and what it lost.
        """
        head = f"{self.format.upper()} gravado em {self.path.name}"
        if self.stats:
            counted = ", ".join(f"{key}: {value}" for key, value in sorted(self.stats.items()))
            head = f"{head} ({counted})"
        return f"{head}.\n{self.degradation.summary()}"


class ExportContext:
    """The per-export mutable state every exporter carries.

    It bundles the four things an exporter needs in every method -- the
    degradation recorder, the format's capability table, the document's
    stylesheet, and where in the tree we are -- so that recording a loss is a
    one-liner at the point of loss rather than a plumbing exercise.

    Not thread-safe, deliberately: one context per export, one export per
    thread. Sharing one would merge two reports.
    """

    __slots__ = (
        "_counts",
        "_document",
        "_emitted",
        "_notes",
        "_options",
        "_path",
        "_profile",
        "_recorder",
        "_stats",
    )

    def __init__(
        self,
        profile: FormatProfile,
        document: Document,
        options: ExportOptions | None = None,
    ) -> None:
        """Create a context for one export.

        Args:
            profile: The format's capability table.
            document: The document being written.
            options: Export settings; defaults are used when omitted.
        """
        self._profile = profile
        self._document = document
        self._options = options or ExportOptions()
        self._recorder = DegradationRecorder(profile.name)
        self._counts: Counter[str] = Counter()
        self._emitted: Counter[str] = Counter()
        self._notes: list[str] = []
        self._stats: Counter[str] = Counter()
        self._path: list[str] = ["/"]

    # -- accessors ---------------------------------------------------------

    @property
    def profile(self) -> FormatProfile:
        """The capability table of the format being written."""
        return self._profile

    @property
    def document(self) -> Document:
        """The document being written."""
        return self._document

    @property
    def options(self) -> ExportOptions:
        """The settings this export runs under."""
        return self._options

    @property
    def stylesheet(self) -> StyleSheet:
        """The document's named styles."""
        return self._document.styles

    @property
    def recorder(self) -> DegradationRecorder:
        """The raw recorder, for the rare case a caller must build a warning."""
        return self._recorder

    @property
    def path(self) -> str:
        """Where in the document tree the exporter currently is."""
        return "".join(self._path)

    # -- position ----------------------------------------------------------

    def enter(self, step: str) -> None:
        """Descend one level in the document path.

        Args:
            step: The path fragment, e.g. ``"body[3]"``.
        """
        self._path.append(step if step.startswith("/") else f"{step}/")

    def leave(self) -> None:
        """Ascend one level in the document path."""
        if len(self._path) > 1:
            self._path.pop()

    def at(self, step: str) -> _PathScope:
        """Return a context manager that enters and leaves one level.

        Args:
            step: The path fragment.

        Returns:
            A scope object usable in a ``with`` statement.
        """
        return _PathScope(self, step)

    # -- statistics --------------------------------------------------------

    def count(self, name: str, amount: int = 1) -> None:
        """Increment an export statistic.

        Args:
            name: Counter name, shown in the result.
            amount: How much to add.
        """
        self._stats[name] += amount

    def note(self, text: str) -> None:
        """Record a user-facing remark that is not a degradation.

        Args:
            text: The remark, in Brazilian Portuguese.
        """
        if text not in self._notes:
            self._notes.append(text)

    # -- the golden rule ---------------------------------------------------

    def degrade(
        self,
        support: PropertySupport,
        *,
        prop: str,
        node: IRNode | None = None,
        original: object = None,
    ) -> DegradationWarning | None:
        """Record one loss described by a capability entry.

        The single choke point every loss passes through. Capping happens here,
        so no caller can accidentally bypass it, and no caller has to think
        about it.

        Args:
            support: What the format does with this property.
            prop: The property name, matching the IR field name.
            node: The node it happened to.
            original: The value the document asked for.

        Returns:
            The warning, or ``None`` when the capability is lossless or the
            per-property cap has been reached.
        """
        resolved = support.resolve(original)
        if resolved.capability.is_lossless:
            return None

        self._counts[prop] += 1
        cap = self._options.max_warnings_per_property
        if cap and self._emitted[prop] >= cap:
            return None
        self._emitted[prop] += 1

        rendered = _render_value(original)
        if resolved.capability is Capability.NONE:
            return self._recorder.unsupported(
                prop=prop,
                node=node,
                path=self.path,
                original=rendered,
                detail=resolved.detail,
            )
        if resolved.capability is Capability.SUBSTITUTE:
            return self._recorder.substituted(
                prop=prop,
                node=node,
                path=self.path,
                original=rendered,
                replacement=resolved.replacement,
                detail=resolved.detail,
            )
        return self._recorder.approximated(
            prop=prop,
            node=node,
            path=self.path,
            original=rendered,
            replacement=resolved.replacement,
            detail=resolved.detail,
        )

    def rasterised(self, *, node: IRNode | None = None, detail: str) -> DegradationWarning:
        """Record vector content that had to become pixels.

        Args:
            node: The node it happened to.
            detail: Why the vector path was unavailable.

        Returns:
            The recorded warning.
        """
        self._counts["vector"] += 1
        self._emitted["vector"] += 1
        return self._recorder.rasterised(prop="vector", node=node, path=self.path, detail=detail)

    def audit_run_props(self, props: RunProps | None, *, node: IRNode | None = None) -> None:
        """Record a warning for every set run property the format cannot carry.

        This is the mechanical form of the golden rule. Call it once per run,
        with the *resolved* properties -- what the reader will actually be
        asked for -- and every shortfall is on record with the node that caused
        it.

        Args:
            props: The resolved run properties; ``None`` audits nothing.
            node: The node the properties sit on.
        """
        if props is None:
            return
        for name in RUN_PROPERTY_NAMES:
            value = getattr(props, name)
            if not is_specified(value):
                continue
            self.degrade(self._profile.run_support(name), prop=name, node=node, original=value)

    def audit_paragraph_props(
        self, props: ParagraphProps | None, *, node: IRNode | None = None
    ) -> None:
        """Record a warning for every set paragraph property the format drops.

        Args:
            props: The resolved paragraph properties; ``None`` audits nothing.
            node: The node the properties sit on.
        """
        if props is None:
            return
        for name in PARAGRAPH_PROPERTY_NAMES:
            if name in ("default_run", "mark_props"):
                continue
            value = getattr(props, name)
            if not is_specified(value):
                continue
            self.degrade(
                self._profile.paragraph_support(name), prop=name, node=node, original=value
            )

    def audit_feature(
        self, name: str, *, node: IRNode | None = None, original: object = None
    ) -> DegradationWarning | None:
        """Record a warning when a named structural feature is not carried.

        Args:
            name: The feature name, as declared in the profile.
            node: The node that needed it.
            original: What the document asked for.

        Returns:
            The warning, if one was recorded.
        """
        return self.degrade(
            self._profile.feature_support(name),
            prop=name,
            node=node,
            original=original if original is not None else name,
        )

    def audit_node(self, node: IRNode) -> DegradationWarning | None:
        """Record a warning when a whole node type is not carried.

        Args:
            node: The node about to be written.

        Returns:
            The warning, if one was recorded.
        """
        tag = tag_of(node)
        warning = self.degrade(
            self._profile.node_support(tag), prop=tag, node=node, original=tag
        )
        self.audit_node_fields(node)
        return warning

    def audit_node_fields(self, node: IRNode) -> None:
        """Record a warning for every field of a node the format cannot carry.

        The golden rule of SPEC section 5.2 is about *properties*, but a node
        field is a property by another name: a diagram whose per-square
        confidences vanish has lost something the author can no longer audit,
        and saying so is the whole point of this front. Only fields that are
        actually set are reported -- an empty ``marks`` tuple lost nothing.

        Args:
            node: The node about to be written.
        """
        tag = tag_of(node)
        for descriptor in fields(node):
            support = self._profile.node_field_support(tag, descriptor.name)
            if support.capability.is_lossless and not support.by_value:
                continue
            value = getattr(node, descriptor.name, None)
            if not is_specified(value):
                continue
            self.degrade(
                support.resolve(value),
                prop=f"{tag}.{descriptor.name}",
                node=node,
                original=_render_value(value),
            )

    # -- finishing ---------------------------------------------------------

    def report(self) -> DegradationReport:
        """Freeze the degradation report, adding the capped-count roll-ups.

        Returns:
            The report, with one extra warning per property whose individual
            warnings were capped, naming the true number of occurrences.
        """
        cap = self._options.max_warnings_per_property
        if cap:
            for prop, total in sorted(self._counts.items()):
                shown = self._emitted[prop]
                if total > shown:
                    self._recorder.record(
                        DegradationWarning(
                            target_format=self._profile.name,
                            kind=DegradationKind.UNSUPPORTED,
                            property=prop,
                            message=(
                                f"'{prop}' foi degradada em {total} no(s) no total; "
                                f"as {shown} primeiras ocorrencias estao listadas acima."
                            ),
                            detail="Limite de avisos por propriedade atingido.",
                        )
                    )
        return self._recorder.report()

    def occurrences(self) -> Mapping[str, int]:
        """Return the true occurrence count per property, capping aside.

        Returns:
            A mapping from property name to how many nodes it affected.
        """
        return dict(self._counts)

    def notes(self) -> tuple[str, ...]:
        """Return the user-facing remarks recorded during the export."""
        return tuple(self._notes)

    def stats(self) -> Mapping[str, int]:
        """Return the export statistics."""
        return dict(self._stats)

    def finish(self, path: Path, artifacts: Sequence[Path] = ()) -> ExportResult:
        """Build the result object for a finished export.

        Args:
            path: The primary artefact.
            artifacts: Every file written; ``path`` is added if absent.

        Returns:
            The result.
        """
        every = list(artifacts)
        if path not in every:
            every.insert(0, path)
        return ExportResult(
            format=self._profile.name,
            path=path,
            artifacts=tuple(every),
            degradation=self.report(),
            notes=self.notes(),
            stats=self.stats(),
        )


class _PathScope:
    """Context manager returned by :meth:`ExportContext.at`."""

    __slots__ = ("_context", "_step")

    def __init__(self, context: ExportContext, step: str) -> None:
        """Store the context and the path fragment.

        Args:
            context: The export context.
            step: The path fragment.
        """
        self._context = context
        self._step = step

    def __enter__(self) -> ExportContext:
        """Descend one level.

        Returns:
            The context, so ``with ctx.at(...) as c`` reads naturally.
        """
        self._context.enter(self._step)
        return self._context

    def __exit__(self, *exc: object) -> None:
        """Ascend one level."""
        self._context.leave()


def _render_value(value: object) -> str | None:
    """Render a property value for a warning message.

    Args:
        value: Any property value.

    Returns:
        A short readable form, or ``None`` when there is nothing to say.
    """
    if value is None:
        return None
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, tuple):
        if not value:
            return None
        rendered = ", ".join(str(_render_value(item)) for item in value[:4])
        return rendered if len(value) <= 4 else f"{rendered}, ..."
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."


class Exporter(abc.ABC):
    """Base class of every output format.

    Subclasses declare their format name and capability profile as class
    attributes and implement :meth:`write`. :meth:`export` is concrete: it
    builds the context, runs the subclass, and returns the result -- so no
    exporter can forget to produce a degradation report.
    """

    format_name: ClassVar[str] = ""
    """Short lowercase name, e.g. ``"docx"``."""

    profile: ClassVar[FormatProfile]
    """The format's capability table."""

    suffix: ClassVar[str] = ""
    """Conventional file extension, including the dot."""

    def export(
        self,
        document: Document,
        destination: Path | str,
        options: ExportOptions | None = None,
    ) -> ExportResult:
        """Write ``document`` to ``destination``.

        Args:
            document: The IR to write.
            destination: Path of the primary artefact. Parent directories are
                created.
            options: Export settings.

        Returns:
            The result, including the degradation report.

        Raises:
            ExportError: The file could not be produced.
        """
        target = Path(destination)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        context = ExportContext(self.profile, document, options)
        return self.write(document, target, context)

    @abc.abstractmethod
    def write(self, document: Document, destination: Path, context: ExportContext) -> ExportResult:
        """Do the actual writing.

        Args:
            document: The IR to write.
            destination: Path of the primary artefact.
            context: The export context to record losses on.

        Returns:
            The result, normally built with :meth:`ExportContext.finish`.
        """
        raise NotImplementedError


def merge_profiles(base: FormatProfile, name: str, **overrides: Any) -> FormatProfile:
    """Derive a profile from another one.

    Used where two outputs share almost everything -- single-file HTML and a
    static site, reflowable and fixed-layout EPUB.

    Args:
        base: The profile to start from.
        name: Name of the derived format.
        **overrides: Fields to replace. Mapping fields are merged, not replaced,
            so a derivation only states its differences.

    Returns:
        The derived profile.
    """
    merged: dict[str, Any] = {"name": name}
    for key, value in overrides.items():
        current = getattr(base, key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            combined = dict(current)
            combined.update(value)
            merged[key] = combined
        else:
            merged[key] = value
    return replace(base, **merged)


def iter_set_run_properties(props: RunProps) -> Iterable[tuple[str, object]]:
    """Yield the run properties that carry an author decision.

    Args:
        props: The properties to inspect.

    Yields:
        ``(name, value)`` for every field that is set.
    """
    for name in RUN_PROPERTY_NAMES:
        value = getattr(props, name)
        if is_specified(value):
            yield name, value
