"""The exporter's golden rule, made mechanical.

SPEC section 5.2:

    Nenhum exportador pode *silenciosamente* descartar uma propriedade. Se um
    formato nao suporta algo, o exportador registra um ``DegradationWarning``
    visivel no relatorio de exportacao.

The rule only holds if recording a loss is easier than ignoring it, so this
module is deliberately tiny: an exporter holds one
:class:`DegradationRecorder`, calls one of four verbs when it hits a limit, and
hands the report back at the end. Every message is written for the user, in
Brazilian Portuguese, and every warning names the node it happened to -- so the
export report can take the reader straight to the paragraph that lost its spot
colour.

The four verbs distinguish outcomes the user genuinely cares about::

    recorder.unsupported(...)  # the property is gone
    recorder.approximated(...)  # it survived, but not exactly
    recorder.substituted(...)  # something else stood in for it
    recorder.rasterised(...)  # vector content became pixels

Typical use inside an exporter::

    if props.small_caps is SmallCapsMode.REAL and not font.has_smcp:
        recorder.substituted(
            node=text,
            prop="small_caps",
            original="real",
            replacement="sintetico",
            detail="a fonte embutida nao traz a caracteristica OpenType 'smcp'",
        )
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from caissa.core.model.base import IRNode, tag_of
from caissa.core.model.ids import ULID
from caissa.core.model.registry import ir_node

__all__ = [
    "DegradationKind",
    "DegradationRecorder",
    "DegradationReport",
    "DegradationWarning",
]


class DegradationKind(StrEnum):
    """How badly a property fared on the way out.

    Ordered from worst to mildest, which is the order an export report should
    list them in: what was lost matters more than what was merely approximated.
    """

    UNSUPPORTED = "unsupported"
    SUBSTITUTED = "substituted"
    APPROXIMATED = "approximated"
    RASTERISED = "rasterised"


@ir_node("degradation_warning")
@dataclass(frozen=True, slots=True, kw_only=True)
class DegradationWarning:
    """One property that an output format could not carry faithfully.

    Attributes:
        target_format: Format being written, e.g. ``"docx"`` or ``"epub"``.
        kind: How badly the property fared.
        property: Name of the property, matching the IR field name so the
            report can be grouped and the user can search for it.
        node_type: Serialisation tag of the node it happened to.
        node_id: Identity of that node.
        path: Document path of that node.
        message: What happened, in Brazilian Portuguese, for the user.
        original: The value the document asked for.
        replacement: What was written instead, when anything was.
        detail: Why the format could not do better.
    """

    target_format: str
    kind: DegradationKind
    property: str
    node_type: str = ""
    node_id: ULID | None = None
    path: str | None = None
    message: str = ""
    original: str | None = None
    replacement: str | None = None
    detail: str | None = None

    def __str__(self) -> str:
        """Render as one readable line."""
        where = f" em {self.path}" if self.path else ""
        return f"[{self.target_format}] {self.kind.value} {self.property}{where}: {self.message}"


@dataclass(frozen=True, slots=True, kw_only=True)
class DegradationReport:
    """Everything one export lost, ready to show the user.

    Attributes:
        target_format: Format that was written.
        warnings: Every warning recorded, in the order they happened.
    """

    target_format: str
    warnings: tuple[DegradationWarning, ...] = ()

    @property
    def is_lossless(self) -> bool:
        """Whether the export carried everything the document asked for."""
        return not self.warnings

    def by_property(self) -> dict[str, int]:
        """Count warnings per property.

        Returns:
            A mapping from property name to how many nodes it affected,
            ordered from most to least affected.
        """
        counter = Counter(warning.property for warning in self.warnings)
        return dict(counter.most_common())

    def by_kind(self) -> dict[DegradationKind, int]:
        """Count warnings per outcome.

        Returns:
            A mapping from outcome to how many warnings had it.
        """
        counter = Counter(warning.kind for warning in self.warnings)
        return {kind: counter[kind] for kind in DegradationKind if counter[kind]}

    def of_property(self, name: str) -> tuple[DegradationWarning, ...]:
        """Return the warnings about one property.

        Args:
            name: The property name.

        Returns:
            The matching warnings.
        """
        return tuple(warning for warning in self.warnings if warning.property == name)

    def summary(self) -> str:
        """Render a one-paragraph report in Brazilian Portuguese.

        Returns:
            A human-readable summary for the export dialog.
        """
        if self.is_lossless:
            return f"Exportacao para {self.target_format}: nenhuma propriedade foi perdida."
        counts = self.by_property()
        listed = ", ".join(f"{name} ({count})" for name, count in counts.items())
        return (
            f"Exportacao para {self.target_format}: {len(self.warnings)} propriedade(s) "
            f"degradada(s) em {len(counts)} tipo(s) -- {listed}."
        )

    def __str__(self) -> str:
        """Render the summary followed by every warning, one per line."""
        lines = [self.summary()]
        lines.extend(str(warning) for warning in self.warnings)
        return "\n".join(lines)


class DegradationRecorder:
    """Collects degradation warnings while an exporter runs.

    One recorder per export. Not thread-safe by design: an exporter writes one
    document on one thread, and making it safe would invite sharing it across
    exports, which would mix two reports together.
    """

    __slots__ = ("_target_format", "_warnings")

    def __init__(self, target_format: str) -> None:
        """Create an empty recorder.

        Args:
            target_format: Name of the format being written.
        """
        self._target_format = target_format
        self._warnings: list[DegradationWarning] = []

    @property
    def target_format(self) -> str:
        """The format this recorder is collecting for."""
        return self._target_format

    def __len__(self) -> int:
        """Return how many warnings have been recorded."""
        return len(self._warnings)

    def __bool__(self) -> bool:
        """Return whether anything has been recorded.

        Defined explicitly so that ``if recorder:`` reads as "did anything go
        wrong?" rather than being confused with ``__len__`` semantics.
        """
        return bool(self._warnings)

    def record(self, warning: DegradationWarning) -> DegradationWarning:
        """Record a warning built by the caller.

        Args:
            warning: The warning.

        Returns:
            The same warning, so a caller can log it too.
        """
        self._warnings.append(warning)
        return warning

    def unsupported(
        self,
        *,
        prop: str,
        node: IRNode | None = None,
        path: str | None = None,
        original: str | None = None,
        detail: str | None = None,
    ) -> DegradationWarning:
        """Record a property the format cannot represent at all.

        Args:
            prop: Name of the property, matching the IR field name.
            node: The node it was on.
            path: Document path of that node.
            original: The value that was dropped.
            detail: Why the format cannot carry it.

        Returns:
            The recorded warning.
        """
        message = (
            f"{self._target_format.upper()} nao representa '{prop}'; a propriedade foi perdida."
        )
        return self._add(
            DegradationKind.UNSUPPORTED,
            prop=prop,
            node=node,
            path=path,
            message=message,
            original=original,
            replacement=None,
            detail=detail,
        )

    def approximated(
        self,
        *,
        prop: str,
        node: IRNode | None = None,
        path: str | None = None,
        original: str | None = None,
        replacement: str | None = None,
        detail: str | None = None,
    ) -> DegradationWarning:
        """Record a property that survived only approximately.

        Args:
            prop: Name of the property.
            node: The node it was on.
            path: Document path of that node.
            original: The value asked for.
            replacement: The value written.
            detail: Why the format cannot be exact.

        Returns:
            The recorded warning.
        """
        message = (
            f"{self._target_format.upper()} aproximou '{prop}'"
            f"{f': {original} -> {replacement}' if original and replacement else ''}."
        )
        return self._add(
            DegradationKind.APPROXIMATED,
            prop=prop,
            node=node,
            path=path,
            message=message,
            original=original,
            replacement=replacement,
            detail=detail,
        )

    def substituted(
        self,
        *,
        prop: str,
        node: IRNode | None = None,
        path: str | None = None,
        original: str | None = None,
        replacement: str | None = None,
        detail: str | None = None,
    ) -> DegradationWarning:
        """Record a property replaced by a different mechanism.

        Args:
            prop: Name of the property.
            node: The node it was on.
            path: Document path of that node.
            original: The value asked for.
            replacement: What stood in for it.
            detail: Why the substitution was needed.

        Returns:
            The recorded warning.
        """
        message = (
            f"{self._target_format.upper()} substituiu '{prop}'"
            f"{f': {original} -> {replacement}' if original and replacement else ''}."
        )
        return self._add(
            DegradationKind.SUBSTITUTED,
            prop=prop,
            node=node,
            path=path,
            message=message,
            original=original,
            replacement=replacement,
            detail=detail,
        )

    def rasterised(
        self,
        *,
        prop: str = "vector",
        node: IRNode | None = None,
        path: str | None = None,
        detail: str | None = None,
    ) -> DegradationWarning:
        """Record vector content that had to be written as pixels.

        Its own verb because it is the degradation this product cares about
        most: a rasterised diagram is exactly what every competing tool
        produces, and shipping one is a failure of the core promise.

        Args:
            prop: Name of the property; defaults to ``"vector"``.
            node: The node it happened to.
            path: Document path of that node.
            detail: Why the vector path was unavailable.

        Returns:
            The recorded warning.
        """
        message = (
            f"{self._target_format.upper()} recebeu imagem rasterizada em vez de vetorial; "
            "a nitidez em zoom e impressao fica limitada."
        )
        return self._add(
            DegradationKind.RASTERISED,
            prop=prop,
            node=node,
            path=path,
            message=message,
            original="vetorial",
            replacement="raster",
            detail=detail,
        )

    def report(self) -> DegradationReport:
        """Freeze everything recorded so far into a report.

        Returns:
            The report.
        """
        return DegradationReport(
            target_format=self._target_format,
            warnings=tuple(self._warnings),
        )

    def _add(
        self,
        kind: DegradationKind,
        *,
        prop: str,
        node: IRNode | None,
        path: str | None,
        message: str,
        original: str | None,
        replacement: str | None,
        detail: str | None,
    ) -> DegradationWarning:
        """Build and store a warning.

        Args:
            kind: How badly the property fared.
            prop: Name of the property.
            node: The node it was on.
            path: Document path of that node.
            message: User-facing text.
            original: The value asked for.
            replacement: The value written.
            detail: Why.

        Returns:
            The recorded warning.
        """
        return self.record(
            DegradationWarning(
                target_format=self._target_format,
                kind=kind,
                property=prop,
                node_type="" if node is None else tag_of(node),
                node_id=None if node is None else node.id,
                path=path,
                message=message,
                original=original,
                replacement=replacement,
                detail=detail,
            )
        )
