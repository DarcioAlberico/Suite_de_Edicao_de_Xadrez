"""Structural validation of a Document IR tree.

The validator answers one question: *is this document internally consistent
enough to export?* It does not judge typography or taste. It catches the classes
of defect that turn into a broken EPUB, an unopenable DOCX or a wrong diagram:

* dangling references -- a note reference with no note, a link to an anchor that
  does not exist, an image pointing at an undeclared resource;
* impossible chess -- a malformed FEN, a board with two white kings, a mark
  naming a square that is not on the board;
* impossible layout -- a table row whose spans overflow the declared columns, a
  heading at level nine;
* unresolved names -- a run asking for a character style the stylesheet does not
  define, a cyclic ``based_on`` chain;
* accessibility gaps that make an export fail validation downstream -- an image
  with no alternative text.

Every issue carries a stable ``code`` (for tests and for suppression), a path
(so the user can be taken to it) and a message in Brazilian Portuguese.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from caissa.core.chess.fen import position_problems, validate_fen
from caissa.core.chess.notation_tables import is_supported_language
from caissa.core.model.base import IRNode, tag_of
from caissa.core.model.blocks import (
    Callout,
    Figure,
    Heading,
    ImageBlock,
    ListBlock,
    ListItem,
    ListKind,
    ListMarkerStyle,
    RawPassthrough,
    Table,
    TableOfContents,
)
from caissa.core.model.diagram import SQUARE_COUNT, Diagram, DiagramStyle, RecognitionResult
from caissa.core.model.document import Document
from caissa.core.model.game import GameScore, MoveNode
from caissa.core.model.ids import ULID
from caissa.core.model.inline import (
    Anchor,
    ImageInline,
    IndexEntry,
    InlineDiagram,
    Link,
    LinkKind,
    Move,
    NagSymbol,
    NoteRef,
    RawInline,
    Text,
)
from caissa.core.model.marks import Mark, MarkKind, is_square_name
from caissa.core.model.props import Color, NumberingRef, ParagraphProps, RunProps
from caissa.core.model.registry import ir_node
from caissa.core.model.styles import StyleError, StyleSheet, style_chain
from caissa.core.model.visitor import walk

__all__ = [
    "Severity",
    "ValidationIssue",
    "validate",
]

_VALID_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2", "*"})
_MIN_HEADING_LEVEL = 1
_MAX_HEADING_LEVEL = 6
_MIN_NAG = 1
_MAX_NAG = 255
_MIN_FONT_WEIGHT = 1
_MAX_FONT_WEIGHT = 1000
_ARROW_SQUARES = 2
_CORNER_VALUES = 8


class Severity(StrEnum):
    """How much an issue matters.

    ``ERROR`` blocks an export, ``WARNING`` degrades it, ``INFO`` is an
    observation worth surfacing but not acting on.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@ir_node("validation_issue")
@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationIssue:
    """One problem found in a document.

    Attributes:
        severity: How much it matters.
        code: Stable machine-readable identifier, e.g. ``"nota.referencia-orfa"``.
        message: What is wrong, in Brazilian Portuguese, for the user.
        path: Where it is, as a document path.
        node_id: Identity of the offending node.
        node_type: Serialisation tag of the offending node.
        hint: How to fix it, in Brazilian Portuguese.
    """

    severity: Severity
    code: str
    message: str
    path: str = "$"
    node_id: ULID | None = None
    node_type: str = ""
    hint: str | None = None

    def __str__(self) -> str:
        """Render as ``severity code path: message``."""
        return f"{self.severity.value} {self.code} {self.path}: {self.message}"


@dataclass(slots=True)
class _Index:
    """Cross-reference tables gathered on the first pass."""

    ids: dict[ULID, list[str]] = field(default_factory=dict)
    note_defs: dict[str, list[str]] = field(default_factory=dict)
    note_refs: dict[str, list[str]] = field(default_factory=dict)
    anchors: dict[str, list[str]] = field(default_factory=dict)
    diagram_numbers: dict[int, list[str]] = field(default_factory=dict)


def validate(document: Document, *, strict_styles: bool = True) -> list[ValidationIssue]:
    """Check a document for structural defects.

    Args:
        document: The document to check.
        strict_styles: Report references to styles the stylesheet does not
            define. Turn it off while a document is mid-import and its
            stylesheet has not been built yet.

    Returns:
        Every issue found, in document order, errors and warnings interleaved
        exactly where they occur.
    """
    issues: list[ValidationIssue] = []
    index = _build_index(document)
    known_styles = document.styles.known_names()

    issues.extend(_check_document(document))
    issues.extend(_check_stylesheet(document.styles))

    for path, node in walk(document):
        where = str(path)
        issues.extend(_check_node(node, where, document, index, known_styles, strict_styles))

    issues.extend(_check_cross_references(index))
    return issues


# --------------------------------------------------------------------------- #
# Index
# --------------------------------------------------------------------------- #


def _build_index(document: Document) -> _Index:
    """Collect the tables the cross-reference checks need.

    Args:
        document: The document to scan.

    Returns:
        The gathered index.
    """
    index = _Index()
    for path, node in walk(document):
        where = str(path)
        index.ids.setdefault(node.id, []).append(where)
        ref = getattr(node, "ref", None)
        if isinstance(ref, str) and ref:
            if isinstance(node, NoteRef):
                index.note_refs.setdefault(ref, []).append(where)
            else:
                index.note_defs.setdefault(ref, []).append(where)
        anchor = getattr(node, "anchor", None)
        if isinstance(anchor, str) and anchor:
            index.anchors.setdefault(anchor, []).append(where)
        if isinstance(node, Anchor) and node.name:
            index.anchors.setdefault(node.name, []).append(where)
        if isinstance(node, Diagram) and node.number is not None:
            index.diagram_numbers.setdefault(node.number, []).append(where)
    return index


# --------------------------------------------------------------------------- #
# Document-level checks
# --------------------------------------------------------------------------- #


def _check_document(document: Document) -> list[ValidationIssue]:
    """Check the document's own metadata and resources.

    Args:
        document: The document.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    metadata = document.metadata
    if not metadata.title.strip():
        issues.append(
            _issue(
                Severity.WARNING,
                "documento.sem-titulo",
                "o documento nao tem titulo.",
                "$",
                document,
                hint="preencha metadata.title; EPUB e PDF/A exigem um titulo.",
            )
        )
    if not metadata.language.strip():
        issues.append(
            _issue(
                Severity.ERROR,
                "documento.sem-idioma",
                "o documento nao declara idioma.",
                "$",
                document,
                hint="preencha metadata.language com uma etiqueta BCP-47, por exemplo 'pt-BR'.",
            )
        )
    if not is_supported_language(document.settings.notation_language):
        issues.append(
            _issue(
                Severity.WARNING,
                "documento.idioma-de-notacao-desconhecido",
                (
                    "idioma de notacao sem tabela de pecas: "
                    f"{document.settings.notation_language!r}."
                ),
                "$",
                document,
                hint="os lances serao impressos em ingles.",
            )
        )
    seen: set[str] = set()
    for resource in document.resources:
        if not resource.key:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "recurso.chave-vazia",
                    "um recurso foi declarado sem chave.",
                    "$.resources",
                    document,
                )
            )
        elif resource.key in seen:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "recurso.chave-duplicada",
                    f"chave de recurso repetida: {resource.key!r}.",
                    "$.resources",
                    document,
                )
            )
        seen.add(resource.key)
    return issues


def _check_stylesheet(stylesheet: StyleSheet) -> list[ValidationIssue]:
    """Check style names for duplicates and ``based_on`` chains for cycles.

    Args:
        stylesheet: The sheet to check.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    families: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("paragraph", tuple(style.name for style in stylesheet.paragraph_styles)),
        ("character", tuple(style.name for style in stylesheet.character_styles)),
        ("table", tuple(style.name for style in stylesheet.table_styles)),
        ("list", tuple(style.name for style in stylesheet.list_styles)),
        ("diagram", tuple(style.name for style in stylesheet.diagram_styles)),
    )
    for kind, names in families:
        seen: set[str] = set()
        for name in names:
            if not name:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "estilo.nome-vazio",
                        f"estilo de {kind} sem nome.",
                        "$.styles",
                        None,
                    )
                )
            elif name in seen:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "estilo.nome-duplicado",
                        f"estilo de {kind} repetido: {name!r}.",
                        "$.styles",
                        None,
                    )
                )
            seen.add(name)
            try:
                style_chain(stylesheet, name, kind)
            except StyleError as exc:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "estilo.ciclo",
                        str(exc),
                        "$.styles",
                        None,
                        hint="quebre a cadeia 'based_on'.",
                    )
                )
    return issues


# --------------------------------------------------------------------------- #
# Per-node checks
# --------------------------------------------------------------------------- #


def _check_node(
    node: IRNode,
    where: str,
    document: Document,
    index: _Index,
    known_styles: frozenset[str],
    strict_styles: bool,
) -> list[ValidationIssue]:
    """Run every check that applies to a single node.

    Args:
        node: The node to check.
        where: Its document path.
        document: The owning document, for resource lookups.
        index: The cross-reference tables.
        known_styles: Every style name the stylesheet defines.
        strict_styles: Whether to report unresolved style names.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    issues.extend(_check_props(node, where, known_styles, strict_styles))
    issues.extend(_check_chess(node, where))
    issues.extend(_check_structure(node, where, document, index))
    return issues


def _check_props(
    node: IRNode,
    where: str,
    known_styles: frozenset[str],
    strict_styles: bool,
) -> list[ValidationIssue]:
    """Check formatting records hanging off a node.

    Args:
        node: The node.
        where: Its document path.
        known_styles: Every style name the stylesheet defines.
        strict_styles: Whether to report unresolved style names.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    for attribute in ("props", "run_props", "move_props", "comment_props"):
        value = getattr(node, attribute, None)
        if isinstance(value, (RunProps, ParagraphProps)):
            issues.extend(_check_props_record(value, node, where, known_styles, strict_styles))
    referenced: list[str] = []
    style_value = getattr(node, "style", None)
    if isinstance(style_value, str) and style_value:
        referenced.append(style_value)
    elif isinstance(style_value, DiagramStyle) and style_value.name:
        referenced.append(style_value.name)
    for attribute in ("props", "numbering"):
        holder = getattr(node, attribute, None)
        numbering = (
            holder if isinstance(holder, NumberingRef) else getattr(holder, "numbering", None)
        )
        if isinstance(numbering, NumberingRef) and numbering.definition:
            referenced.append(numbering.definition)
    if strict_styles:
        issues.extend(
            _issue(
                Severity.ERROR,
                "estilo.nao-resolvido",
                f"estilo nao definido na folha de estilos: {name!r}.",
                where,
                node,
                hint="defina o estilo ou remova a referencia.",
            )
            for name in referenced
            if name not in known_styles
        )
    return issues


def _check_props_record(
    props: RunProps | ParagraphProps,
    node: IRNode,
    where: str,
    known_styles: frozenset[str],
    strict_styles: bool,
) -> list[ValidationIssue]:
    """Check one property record's style reference, colours and measures.

    Args:
        props: The record.
        node: The node it belongs to.
        where: The node's document path.
        known_styles: Every style name the stylesheet defines.
        strict_styles: Whether to report unresolved style names.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if strict_styles and props.style and props.style not in known_styles:
        issues.append(
            _issue(
                Severity.ERROR,
                "estilo.nao-resolvido",
                f"estilo nao definido na folha de estilos: {props.style!r}.",
                where,
                node,
                hint="defina o estilo ou remova a referencia.",
            )
        )
    if isinstance(props, RunProps):
        if props.font_size is not None and props.font_size.value < 0:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "medida.tamanho-negativo",
                    f"corpo de fonte negativo: {props.font_size}.",
                    where,
                    node,
                )
            )
        if props.font_weight is not None and not (
            _MIN_FONT_WEIGHT <= props.font_weight <= _MAX_FONT_WEIGHT
        ):
            issues.append(
                _issue(
                    Severity.ERROR,
                    "fonte.peso-fora-da-faixa",
                    f"peso de fonte fora de [1, 1000]: {props.font_weight}.",
                    where,
                    node,
                )
            )
        if props.opacity is not None and not 0.0 <= props.opacity <= 1.0:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "cor.opacidade-fora-da-faixa",
                    f"opacidade fora de [0, 1]: {props.opacity}.",
                    where,
                    node,
                )
            )
        if props.language is not None and props.language and not props.language.strip():
            issues.append(
                _issue(
                    Severity.WARNING,
                    "texto.idioma-vazio",
                    "etiqueta de idioma em branco.",
                    where,
                    node,
                )
            )
        for color in (props.color, props.highlight, props.background, props.underline_color):
            issues.extend(_check_color(color, node, where))
    return issues


def _check_color(color: Color | None, node: IRNode, where: str) -> list[ValidationIssue]:
    """Check a colour's component count and channel range.

    Args:
        color: The colour, or ``None``.
        node: The node it belongs to.
        where: The node's document path.

    Returns:
        Any issues found.
    """
    if color is None:
        return []
    issues: list[ValidationIssue] = []
    expected = color.expected_component_count()
    if expected is not None and len(color.components) != expected:
        issues.append(
            _issue(
                Severity.ERROR,
                "cor.componentes",
                (
                    f"cor {color.space.value!r} exige {expected} componentes; "
                    f"recebidos {len(color.components)}."
                ),
                where,
                node,
            )
        )
    if any(not 0.0 <= channel <= 1.0 for channel in color.components):
        issues.append(
            _issue(
                Severity.ERROR,
                "cor.canal-fora-da-faixa",
                f"componente de cor fora de [0, 1]: {color.components}.",
                where,
                node,
            )
        )
    if not 0.0 <= color.alpha <= 1.0:
        issues.append(
            _issue(
                Severity.ERROR,
                "cor.opacidade-fora-da-faixa",
                f"alfa fora de [0, 1]: {color.alpha}.",
                where,
                node,
            )
        )
    if color.space.value in ("named", "spot") and not color.name:
        issues.append(
            _issue(
                Severity.ERROR,
                "cor.sem-nome",
                f"cor {color.space.value!r} exige um nome.",
                where,
                node,
            )
        )
    return issues


def _check_chess(node: IRNode, where: str) -> list[ValidationIssue]:
    """Check FENs, marks, moves and game scores.

    Args:
        node: The node.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if isinstance(node, Diagram):
        issues.extend(_check_fen(node.fen, node, where, "diagrama", legality=True))
        issues.extend(_check_marks(node.marks, node, where))
        issues.extend(_check_recognition(node.recognition, node, where))
        if node.alt_text is None and not node.caption:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "diagrama.sem-texto-alternativo",
                    "diagrama sem legenda nem texto alternativo.",
                    where,
                    node,
                    hint="EPUB e PDF marcado exigem descricao acessivel.",
                )
            )
    elif isinstance(node, InlineDiagram):
        issues.extend(_check_fen(node.fen, node, where, "diagrama em linha", legality=True))
        issues.extend(_check_marks(node.marks, node, where))
    elif isinstance(node, Move):
        issues.extend(_check_move(node, where))
    elif isinstance(node, MoveNode):
        issues.extend(_check_move_node(node, where))
    elif isinstance(node, GameScore):
        issues.extend(_check_game(node, where))
    elif isinstance(node, NagSymbol) and not _MIN_NAG <= node.nag <= _MAX_NAG:
        issues.append(
            _issue(
                Severity.ERROR,
                "nag.fora-da-faixa",
                f"NAG fora de [{_MIN_NAG}, {_MAX_NAG}]: {node.nag}.",
                where,
                node,
            )
        )
    return issues


def _check_fen(
    fen: str,
    node: IRNode,
    where: str,
    label: str,
    *,
    legality: bool = False,
    required: bool = True,
) -> list[ValidationIssue]:
    """Check one FEN string.

    Args:
        fen: The FEN.
        node: The node carrying it.
        where: The node's document path.
        label: What the FEN describes, for the message.
        legality: Also apply the SPEC 6.4 legality constraints, as a warning.
        required: Whether an empty value is itself an error.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not fen:
        if required:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "fen.ausente",
                    f"{label} sem posicao (FEN vazia).",
                    where,
                    node,
                )
            )
        return issues
    problems = validate_fen(fen)
    if problems:
        issues.append(
            _issue(
                Severity.ERROR,
                "fen.invalida",
                f"{label} com FEN invalida: {problems[0]}",
                where,
                node,
                hint=f"FEN recebida: {fen!r}",
            )
        )
        return issues
    if legality:
        issues.extend(
            _issue(
                Severity.WARNING,
                "fen.posicao-ilegal",
                f"{label}: {problem}",
                where,
                node,
                hint="posicoes de problema podem legitimamente violar isto.",
            )
            for problem in position_problems(fen, allow_composition=True)
        )
    return issues


def _check_marks(marks: tuple[Mark, ...], node: IRNode, where: str) -> list[ValidationIssue]:
    """Check the square names and arity of board marks.

    Args:
        marks: The marks to check.
        node: The node carrying them.
        where: The node's document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    for mark in marks:
        bad = [name for name in mark.squares if not is_square_name(name)]
        if bad:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "marca.casa-invalida",
                    f"marca com casas invalidas: {', '.join(bad)}.",
                    where,
                    node,
                )
            )
        if mark.kind is MarkKind.ARROW and len(mark.squares) != _ARROW_SQUARES:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "marca.aridade",
                    f"seta exige exatamente 2 casas; recebidas {len(mark.squares)}.",
                    where,
                    node,
                )
            )
        elif mark.kind is not MarkKind.ARROW and not mark.squares:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "marca.aridade",
                    f"marca {mark.kind.value!r} exige ao menos 1 casa.",
                    where,
                    node,
                )
            )
        if mark.kind is MarkKind.LABEL and not mark.text:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "marca.rotulo-vazio",
                    "marca de rotulo sem texto.",
                    where,
                    node,
                )
            )
        if mark.opacity is not None and not 0.0 <= mark.opacity <= 1.0:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "marca.opacidade-fora-da-faixa",
                    f"opacidade de marca fora de [0, 1]: {mark.opacity}.",
                    where,
                    node,
                )
            )
    return issues


def _check_recognition(
    recognition: RecognitionResult,
    node: IRNode,
    where: str,
) -> list[ValidationIssue]:
    """Check a recognition record's confidence vector and repairs.

    Args:
        recognition: The record.
        node: The diagram carrying it.
        where: The node's document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    confidences = recognition.per_square_confidence
    if confidences and len(confidences) != SQUARE_COUNT:
        issues.append(
            _issue(
                Severity.ERROR,
                "reconhecimento.confianca-tamanho",
                (
                    f"per_square_confidence deve ter {SQUARE_COUNT} valores; "
                    f"recebidos {len(confidences)}."
                ),
                where,
                node,
            )
        )
    if any(not 0.0 <= value <= 1.0 for value in confidences):
        issues.append(
            _issue(
                Severity.ERROR,
                "reconhecimento.confianca-faixa",
                "ha confianca por casa fora de [0, 1].",
                where,
                node,
            )
        )
    for scalar_name, scalar in (
        ("overall_confidence", recognition.overall_confidence),
        ("orientation_confidence", recognition.orientation_confidence),
        ("side_to_move_confidence", recognition.side_to_move_confidence),
    ):
        if scalar is not None and not 0.0 <= scalar <= 1.0:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "reconhecimento.confianca-faixa",
                    f"{scalar_name} fora de [0, 1]: {scalar}.",
                    where,
                    node,
                )
            )
    if recognition.corners and len(recognition.corners) != _CORNER_VALUES:
        issues.append(
            _issue(
                Severity.ERROR,
                "reconhecimento.cantos",
                f"corners deve ter 8 valores (4 pontos); recebidos {len(recognition.corners)}.",
                where,
                node,
            )
        )
    issues.extend(
        _issue(
            Severity.ERROR,
            "reconhecimento.reparo-casa-invalida",
            f"reparo em casa invalida: {repair.square!r}.",
            where,
            node,
        )
        for repair in recognition.repairs
        if not is_square_name(repair.square)
    )
    if recognition.fen:
        issues.extend(_check_fen(recognition.fen, node, where, "leitura do reconhecimento"))
    return issues


def _check_move(node: Move, where: str) -> list[ValidationIssue]:
    """Check an inline move.

    Args:
        node: The move.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not node.san.strip():
        issues.append(_issue(Severity.ERROR, "lance.san-vazio", "lance sem SAN.", where, node))
    if node.ply < 0:
        issues.append(
            _issue(
                Severity.ERROR,
                "lance.ply-negativo",
                f"ply negativo: {node.ply}.",
                where,
                node,
            )
        )
    if not is_supported_language(node.language):
        issues.append(
            _issue(
                Severity.WARNING,
                "lance.idioma-desconhecido",
                f"idioma sem tabela de pecas: {node.language!r}.",
                where,
                node,
                hint="o lance sera impresso em ingles.",
            )
        )
    issues.extend(_check_nags(node.nags, node, where))
    if node.position_before:
        issues.extend(_check_fen(node.position_before, node, where, "posicao anterior ao lance"))
    return issues


def _check_move_node(node: MoveNode, where: str) -> list[ValidationIssue]:
    """Check a move inside a game tree.

    Args:
        node: The move node.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not node.san.strip():
        issues.append(
            _issue(
                Severity.ERROR,
                "partida.lance-vazio",
                "no de lance sem SAN.",
                where,
                node,
                hint="um no sem lance quebra a exportacao para PGN.",
            )
        )
    if node.ply < 0:
        issues.append(
            _issue(
                Severity.ERROR,
                "lance.ply-negativo",
                f"ply negativo: {node.ply}.",
                where,
                node,
            )
        )
    issues.extend(_check_nags(node.nags, node, where))
    issues.extend(_check_marks(node.arrows, node, where))
    issues.extend(_check_marks(node.highlights, node, where))
    for label, fen in (
        ("posicao anterior ao lance", node.position_before),
        ("posicao posterior ao lance", node.position_after),
    ):
        if fen:
            issues.extend(_check_fen(fen, node, where, label))
    return issues


def _check_nags(nags: tuple[int, ...], node: IRNode, where: str) -> list[ValidationIssue]:
    """Check that NAG numbers are inside the PGN range.

    Args:
        nags: The NAG numbers.
        node: The node carrying them.
        where: The node's document path.

    Returns:
        Any issues found.
    """
    return [
        _issue(
            Severity.ERROR,
            "nag.fora-da-faixa",
            f"NAG fora de [{_MIN_NAG}, {_MAX_NAG}]: {nag}.",
            where,
            node,
        )
        for nag in nags
        if not _MIN_NAG <= nag <= _MAX_NAG
    ]


def _check_game(node: GameScore, where: str) -> list[ValidationIssue]:
    """Check a game score's headers and starting position.

    Args:
        node: The game.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if node.headers.result not in _VALID_RESULTS:
        options = ", ".join(sorted(_VALID_RESULTS))
        issues.append(
            _issue(
                Severity.ERROR,
                "partida.resultado-invalido",
                f"resultado invalido: {node.headers.result!r}. Validos: {options}.",
                where,
                node,
            )
        )
    if node.initial_fen is not None:
        issues.extend(
            _check_fen(node.initial_fen, node, where, "posicao inicial da partida", legality=True)
        )
    seen: set[str] = set()
    for tag in node.headers.extra:
        if not tag.name.strip():
            issues.append(
                _issue(
                    Severity.ERROR,
                    "partida.etiqueta-sem-nome",
                    "etiqueta PGN sem nome.",
                    where,
                    node,
                )
            )
        elif tag.name in seen:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "partida.etiqueta-duplicada",
                    f"etiqueta PGN repetida: {tag.name!r}.",
                    where,
                    node,
                )
            )
        seen.add(tag.name)
    return issues


def _check_structure(
    node: IRNode,
    where: str,
    document: Document,
    index: _Index,
) -> list[ValidationIssue]:
    """Check layout structure: headings, tables, lists, links and resources.

    Args:
        node: The node.
        where: Its document path.
        document: The owning document, for resource lookups.
        index: The cross-reference tables.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if isinstance(node, Heading):
        if not _MIN_HEADING_LEVEL <= node.level <= _MAX_HEADING_LEVEL:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "titulo.nivel-invalido",
                    (
                        f"nivel de titulo fora de [{_MIN_HEADING_LEVEL}, "
                        f"{_MAX_HEADING_LEVEL}]: {node.level}."
                    ),
                    where,
                    node,
                )
            )
        if not node.content:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "titulo.vazio",
                    "titulo sem texto.",
                    where,
                    node,
                )
            )
    elif isinstance(node, Table):
        issues.extend(_check_table(node, where))
    elif isinstance(node, ListBlock):
        issues.extend(_check_list(node, where))
    elif isinstance(node, ListItem):
        issues.extend(_check_list_item(node, where))
    elif isinstance(node, Link):
        issues.extend(_check_link(node, where, index))
    elif isinstance(node, (ImageBlock, ImageInline)):
        issues.extend(_check_image(node, where, document))
    elif isinstance(node, Text):
        issues.extend(_check_text(node, where))
    else:
        issues.extend(_check_leaf_structure(node, where))
    return issues


def _check_leaf_structure(node: IRNode, where: str) -> list[ValidationIssue]:
    """Check the node types whose only structural rule is "do not be empty".

    Split out of :func:`_check_structure` so neither function grows past the
    point where a reader can hold it in their head.

    Args:
        node: The node.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if isinstance(node, (RawPassthrough, RawInline)) and not node.format.strip():
        issues.append(
            _issue(
                Severity.ERROR,
                "passthrough.formato-vazio",
                "conteudo bruto sem formato de destino.",
                where,
                node,
                hint="informe o formato, por exemplo 'latex' ou 'html'.",
            )
        )
    elif isinstance(node, IndexEntry) and not node.terms:
        issues.append(
            _issue(
                Severity.ERROR,
                "indice.entrada-vazia",
                "entrada de indice sem termos.",
                where,
                node,
            )
        )
    elif isinstance(node, Anchor) and not node.name.strip():
        issues.append(_issue(Severity.ERROR, "ancora.nome-vazio", "ancora sem nome.", where, node))
    elif isinstance(node, Figure) and not node.caption and node.number is not None:
        issues.append(
            _issue(
                Severity.INFO,
                "figura.sem-legenda",
                "figura numerada sem legenda.",
                where,
                node,
            )
        )
    elif isinstance(node, TableOfContents) and node.min_level > node.max_level:
        issues.append(
            _issue(
                Severity.ERROR,
                "sumario.faixa-invalida",
                f"min_level ({node.min_level}) maior que max_level ({node.max_level}).",
                where,
                node,
            )
        )
    elif isinstance(node, Callout) and not node.content:
        issues.append(
            _issue(
                Severity.INFO,
                "destaque.vazio",
                f"caixa de destaque {node.kind.value!r} sem conteudo.",
                where,
                node,
            )
        )
    return issues


def _check_table(node: Table, where: str) -> list[ValidationIssue]:
    """Check a table's column declaration against its cell spans.

    Args:
        node: The table.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    declared = node.column_count
    if declared == 0 and node.rows:
        issues.append(
            _issue(
                Severity.ERROR,
                "tabela.sem-colunas",
                "tabela com linhas mas sem colunas declaradas.",
                where,
                node,
                hint="preencha 'columns'; os exportadores dependem dela para a largura.",
            )
        )
    if node.header_row_count + node.footer_row_count > len(node.rows):
        issues.append(
            _issue(
                Severity.ERROR,
                "tabela.cabecalho-excede",
                (
                    f"cabecalho ({node.header_row_count}) e rodape ({node.footer_row_count}) "
                    f"somam mais que as {len(node.rows)} linhas."
                ),
                where,
                node,
            )
        )
    for row_index, row in enumerate(node.rows):
        width = 0
        for cell in row.cells:
            if cell.col_span < 1 or cell.row_span < 1:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "tabela.span-invalido",
                        (
                            f"linha {row_index}: span deve ser >= 1; recebido "
                            f"col_span={cell.col_span}, row_span={cell.row_span}."
                        ),
                        where,
                        node,
                    )
                )
            width += max(cell.col_span, 1)
        if declared and width > declared:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "tabela.span-excede",
                    (f"linha {row_index} ocupa {width} colunas, mas a tabela declara {declared}."),
                    where,
                    node,
                    hint="ajuste col_span ou declare mais colunas.",
                )
            )
    return issues


def _check_list(node: ListBlock, where: str) -> list[ValidationIssue]:
    """Check a list's kind against the shape of its items.

    Args:
        node: The list.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if node.kind is ListKind.DEFINITION:
        issues.extend(
            _issue(
                Severity.ERROR,
                "lista.termo-ausente",
                f"item {position} de lista de definicoes sem termo.",
                where,
                node,
                hint="preencha ListItem.term.",
            )
            for position, item in enumerate(node.items)
            if not item.term
        )
    else:
        issues.extend(
            _issue(
                Severity.WARNING,
                "lista.termo-inesperado",
                f"item {position} tem termo, mas a lista nao e de definicoes.",
                where,
                node,
            )
            for position, item in enumerate(node.items)
            if item.term
        )
    if node.marker_style is ListMarkerStyle.CUSTOM and not node.marker_text:
        issues.append(
            _issue(
                Severity.ERROR,
                "lista.marcador-vazio",
                "estilo de marcador 'custom' sem texto de marcador.",
                where,
                node,
            )
        )
    return issues


def _check_list_item(node: ListItem, where: str) -> list[ValidationIssue]:
    """Check a list item's body and definition term.

    Args:
        node: The item.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not node.content and not node.term:
        issues.append(
            _issue(Severity.INFO, "lista.item-vazio", "item de lista vazio.", where, node)
        )
    return issues


def _check_link(node: Link, where: str, index: _Index) -> list[ValidationIssue]:
    """Check a link's target.

    Args:
        node: The link.
        where: Its document path.
        index: The cross-reference tables.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not node.target.strip():
        issues.append(_issue(Severity.ERROR, "link.alvo-vazio", "link sem destino.", where, node))
        return issues
    if node.kind is LinkKind.INTERNAL or node.target.startswith("#"):
        name = node.target.removeprefix("#")
        if name and name not in index.anchors:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "link.ancora-inexistente",
                    f"link interno para ancora inexistente: {name!r}.",
                    where,
                    node,
                    hint="crie a ancora ou corrija o destino.",
                )
            )
    return issues


def _check_image(
    node: ImageBlock | ImageInline,
    where: str,
    document: Document,
) -> list[ValidationIssue]:
    """Check an image's resource reference and alternative text.

    Args:
        node: The image.
        where: Its document path.
        document: The owning document.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not node.resource.strip():
        issues.append(
            _issue(Severity.ERROR, "imagem.sem-recurso", "imagem sem recurso.", where, node)
        )
    elif document.resource(node.resource) is None:
        issues.append(
            _issue(
                Severity.ERROR,
                "recurso.inexistente",
                f"imagem aponta para recurso nao declarado: {node.resource!r}.",
                where,
                node,
                hint="declare o recurso em Document.resources.",
            )
        )
    if not node.alt_text:
        issues.append(
            _issue(
                Severity.WARNING,
                "imagem.sem-texto-alternativo",
                "imagem sem texto alternativo.",
                where,
                node,
                hint="EPUB e PDF marcado exigem descricao acessivel.",
            )
        )
    return issues


def _check_text(node: Text, where: str) -> list[ValidationIssue]:
    """Check a text run's content.

    Args:
        node: The run.
        where: Its document path.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    if not node.content:
        issues.append(_issue(Severity.INFO, "texto.vazio", "trecho de texto vazio.", where, node))
    if "\n" in node.content or "\r" in node.content:
        issues.append(
            _issue(
                Severity.ERROR,
                "texto.quebra-de-linha",
                "trecho de texto contem quebra de linha literal.",
                where,
                node,
                hint="use LineBreak para quebrar linha e um novo bloco para novo paragrafo.",
            )
        )
    return issues


# --------------------------------------------------------------------------- #
# Cross-reference checks
# --------------------------------------------------------------------------- #


def _check_cross_references(index: _Index) -> list[ValidationIssue]:
    """Check references that can only be judged once the whole tree is known.

    Args:
        index: The cross-reference tables.

    Returns:
        Any issues found.
    """
    issues: list[ValidationIssue] = []
    for node_id, paths in index.ids.items():
        if len(paths) > 1:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "no.id-duplicado",
                    f"identidade repetida em {len(paths)} nos: {node_id}.",
                    paths[0],
                    None,
                    hint=f"tambem em {paths[1]}; ids devem ser unicos no documento.",
                )
            )
    for ref, paths in index.note_refs.items():
        if ref not in index.note_defs:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "nota.referencia-orfa",
                    f"referencia a nota inexistente: {ref!r}.",
                    paths[0],
                    None,
                    hint="crie a Footnote ou Endnote correspondente.",
                )
            )
    for ref, paths in index.note_defs.items():
        if len(paths) > 1:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "nota.ref-duplicada",
                    f"duas notas com a mesma chave: {ref!r}.",
                    paths[0],
                    None,
                )
            )
        if ref not in index.note_refs:
            issues.append(
                _issue(
                    Severity.INFO,
                    "nota.nunca-referenciada",
                    f"nota {ref!r} nunca e referenciada no texto.",
                    paths[0],
                    None,
                )
            )
    for name, paths in index.anchors.items():
        if len(paths) > 1:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "ancora.duplicada",
                    f"ancora repetida: {name!r}.",
                    paths[0],
                    None,
                    hint=f"tambem em {paths[1]}.",
                )
            )
    for number, paths in index.diagram_numbers.items():
        if len(paths) > 1:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "diagrama.numero-duplicado",
                    f"numero de diagrama repetido: {number}.",
                    paths[0],
                    None,
                    hint="deixe a numeracao automatica cuidar disso.",
                )
            )
    return issues


def _issue(
    severity: Severity,
    code: str,
    message: str,
    path: str,
    node: IRNode | None,
    *,
    hint: str | None = None,
) -> ValidationIssue:
    """Build a validation issue.

    Args:
        severity: How much it matters.
        code: Stable machine-readable identifier.
        message: What is wrong, in Brazilian Portuguese.
        path: Where it is.
        node: The offending node, when there is one.
        hint: How to fix it.

    Returns:
        The issue.
    """
    return ValidationIssue(
        severity=severity,
        code=code,
        message=message,
        path=path,
        node_id=None if node is None else node.id,
        node_type="" if node is None else tag_of(node),
        hint=hint,
    )
