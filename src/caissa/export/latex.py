"""LaTeX output: a diagram is text, not a picture.

SPEC section 8.5 asks for ``xskak`` / ``chessboard`` / ``chessfss``, diagrams as
``\\chessboard[setfen=...]`` -- **editaveis em texto** -- figurine notation via
``skaknew``, and a generated ``Makefile``. All five already exist in
:mod:`caissa.typeset.latex`, which F7 built and tested against a real TeX
installation. This module does not reimplement any of it: it walks the IR and
*calls* that module, so a fix to the diagram macro reaches both the typesetter
and the exporter.

The known crack between the two paths
-------------------------------------
``docs/quality/F7_REPORT.md`` records that the SVG path and the LaTeX path draw
from different piece sets, so a book exported to both comes out with different
drawings. The cause is upstream of this module: ``chessfss`` selects a *TeX*
font family, and the reference machine's TeX tree carries only ``alpha`` and
``berlin`` while the screen renders Merida. This module cannot install a font,
but it can stop the mismatch being silent -- :meth:`LatexExporter.write` asks
:func:`caissa.typeset.latex.chessfss_family_available` whether the document's
own piece set is installed and records a substitution warning naming both sets
when it is not. See ``docs/quality/F8_REPORT.md``.

Reading it back
---------------
There is no LaTeX parser here and there should not be: recovering an IR from
TeX means implementing TeX. The exporter therefore writes the serialised IR into
the ``.tex`` file as a comment block, and :func:`read_latex` reads *that*. Any
fidelity number measured through it is labelled ``method="sidecar"`` by
:mod:`caissa.export.fidelity`, because it is a statement about JSON and not
about this writer.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from caissa.core.model import (
    Block,
    Callout,
    CalloutKind,
    CodeBlock,
    Diagram,
    Document,
    Emphasis,
    Endnote,
    Figure,
    Footnote,
    GameScore,
    Group,
    Heading,
    ImageBlock,
    ImageInline,
    Inline,
    InlineDiagram,
    LineBreak,
    Link,
    ListBlock,
    ListItem,
    ListKind,
    MathBlock,
    MathInline,
    Move,
    MoveNode,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    PageBreak,
    Paragraph,
    PieceGlyph,
    Quote,
    RawInline,
    RawPassthrough,
    SectionBreak,
    SmallCaps,
    Space,
    Strike,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableOfContents,
    Text,
    ThematicBreak,
    Underline,
    document_from_payload,
    document_to_payload,
    tag_of,
)
from caissa.export.base import ExportContext, Exporter, ExportOptions, ExportResult
from caissa.export.diagrams import DiagramRenderer
from caissa.export.profiles import LATEX_PROFILE
from caissa.export.text import game_to_pgn, inline_plain_text, nag_symbol, render_move
from caissa.typeset import latex as tex

__all__ = ["LatexExporter", "LatexOptions", "read_latex"]

SIDECAR_PREFIX = "%%CAISSA-IR "
"""Comment prefix of the embedded IR, one line per chunk of JSON."""

_SIDECAR_WIDTH = 200


@dataclass(frozen=True, slots=True, kw_only=True)
class LatexOptions(ExportOptions):
    """Settings specific to LaTeX output.

    Attributes:
        document_class: ``book``, ``article``, ``report``.
        class_options: Options passed to the class.
        geometry: The ``geometry`` package's option string.
        chess_font: A key of :data:`caissa.typeset.latex.CHESSFSS_FAMILIES`, or
            ``None`` to leave ``chessfss`` on its own default.
        board_font_size: ``chessboard``'s board unit; the board is eight of it.
        engine: Which engine the generated ``Makefile`` drives.
        write_makefile: Emit the ``Makefile`` beside the ``.tex``.
        two_column: Wrap the body in ``multicols``.
    """

    document_class: str = "book"
    class_options: str = "11pt,a5paper,twoside"
    geometry: str = "a5paper,inner=20mm,outer=15mm,top=18mm,bottom=20mm"
    chess_font: str | None = "merida"
    board_font_size: str = "20pt"
    engine: str = "pdflatex"
    write_makefile: bool = True
    two_column: bool = False


_LIST_ENVIRONMENT = {
    ListKind.ORDERED: "enumerate",
    ListKind.UNORDERED: "itemize",
    ListKind.DEFINITION: "description",
}

_CALLOUT_LABEL = {
    CalloutKind.NOTE: "Nota",
    CalloutKind.TIP: "Dica",
    CalloutKind.WARNING: "Atencao",
    CalloutKind.IMPORTANT: "Importante",
    CalloutKind.EXAMPLE: "Exemplo",
    CalloutKind.EXERCISE: "Exercicio",
    CalloutKind.SOLUTION: "Solucao",
    CalloutKind.THEORY: "Teoria",
    CalloutKind.SUMMARY: "Resumo",
    CalloutKind.SIDEBAR: "Quadro",
}

_FIGURINE_MACRO: dict[str, str] = {
    "\u2654": "king",
    "\u2655": "queen",
    "\u2656": "rook",
    "\u2657": "bishop",
    "\u2658": "knight",
    "\u2659": "pawn",
    "\u265a": "king",
    "\u265b": "queen",
    "\u265c": "rook",
    "\u265d": "bishop",
    "\u265e": "knight",
    "\u265f": "pawn",
}
"""Unicode chess glyphs mapped to the ``chessfss`` command that draws them.

``pdflatex`` with ``inputenc`` refuses a codepoint no font in the document
declares -- "Unicode character not set up for use with LaTeX" is a fatal
error, not a missing glyph. The figurines have to become the package's own
commands before they reach the file.
"""


def _figurines_to_macros(text: str) -> str:
    """Replace Unicode chess glyphs with ``chessfss`` commands.

    Args:
        text: Already-escaped LaTeX text.

    Returns:
        The text with every figurine drawn by the chess font.
    """
    if not any(char in _FIGURINE_MACRO for char in text):
        return text
    return "".join(
        (
            f"\\sym{_FIGURINE_MACRO[char]}{{}}"
            if char in _FIGURINE_MACRO
            else char
        )
        for char in text
    )


_CELL_SPEC: dict[str, str] = {
    "left": "l",
    "center": "c",
    "right": "r",
    "justify": "l",
    "justify-low": "l",
    "distribute": "l",
    "start": "l",
    "end": "r",
}
"""Cell alignment as a ``tabular`` column specifier.

Inside a cell LaTeX is in LR mode, where an alignment environment is a fatal
error rather than a layout choice. The column specifier is where alignment
belongs.
"""

_HEADING_COMMAND = (
    "chapter",
    "section",
    "subsection",
    "subsubsection",
    "paragraph",
    "subparagraph",
)


class LatexExporter(Exporter):
    """Writes a LaTeX project: one ``.tex``, and a ``Makefile`` that builds it."""

    format_name: ClassVar[str] = "latex"
    profile: ClassVar[Any] = LATEX_PROFILE
    suffix: ClassVar[str] = ".tex"

    def write(
        self, document: Document, destination: Path, context: ExportContext
    ) -> ExportResult:
        """Write the project.

        Args:
            document: The IR to write.
            destination: The ``.tex`` file.
            context: The export context.

        Returns:
            The result.
        """
        options = context.options
        self._context = context
        self._diagrams = DiagramRenderer(context)
        self._notes: list[Footnote | Endnote] = []
        self._in_cell = 0

        settings = tex.LatexOptions(
            language=(context.options.language or document.metadata.language or "pt")[:2],
            font_family=getattr(options, "chess_font", "merida"),
            board_font_size=getattr(options, "board_font_size", "20pt"),
            document_class=getattr(options, "document_class", "book"),
            class_options=getattr(options, "class_options", "11pt,a5paper,twoside"),
            geometry=getattr(options, "geometry", "a5paper,inner=20mm,outer=15mm,top=18mm"),
            two_column=getattr(options, "two_column", False),
        )
        settings = self._check_piece_set(settings, document, context)

        project = tex.LatexDocument(
            options=settings,
            title=document.metadata.title,
            author=", ".join(
                person.name for person in document.metadata.contributors
            )
            or None,
        )
        if context.options.include_toc:
            project.add("\\tableofcontents")
        for block in document.body:
            project.add(self.block(block))
        if self._notes:
            project.add(self._endnotes())

        text = _with_extra_packages(project.render())
        if context.options.embed_ir:
            text = text + "\n" + _sidecar(document)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        context.count("bytes", len(text.encode("utf-8")))

        artifacts = [destination]
        if getattr(options, "write_makefile", True):
            makefile = destination.parent / "Makefile"
            makefile.write_text(
                tex.makefile(destination.name, engine=getattr(options, "engine", "pdflatex")),
                encoding="utf-8",
            )
            artifacts.append(makefile)
        engine = tex.tex_available(getattr(options, "engine", "pdflatex"))
        context.note(
            f"Motor TeX encontrado em {engine}."
            if engine
            else "Nenhum motor TeX encontrado nesta maquina; o .tex nao foi compilado."
        )
        return context.finish(destination, artifacts)

    # -- piece sets --------------------------------------------------------

    def _check_piece_set(
        self, settings: tex.LatexOptions, document: Document, context: ExportContext
    ) -> tex.LatexOptions:
        """Fall back to an installed piece set, and say that it happened.

        ``docs/quality/F7_REPORT.md`` records that the SVG and LaTeX paths can
        draw different pieces. The cause is a missing Type1 package rather than
        a bug in either renderer, and it has a sharp consequence: naming a
        family whose ``.pfb`` is not in the TeX tree does not merely change the
        drawing, it stops ``pdflatex`` with ``cannot open Type 1 font file`` and
        produces no PDF at all. Measured on this machine with ``merida``.

        So the family is *checked* rather than assumed, an installed one stands
        in when it has to, and the report names both -- which is what a book
        exported to LaTeX and to EPUB needs, because the two will not match.

        Args:
            settings: The typesetter options about to be used.
            document: The IR, for the family the screen renders.
            context: The export context.

        Returns:
            The settings, with an installed family.
        """
        from dataclasses import replace as _replace

        wanted = document.settings.chess_font_family
        family = settings.font_family
        if family and not tex.chessfss_family_available(family):
            fallback = tex.first_available_family(("merida", "alpha", "berlin"))
            context.recorder.substituted(
                prop="chess_font",
                path=context.path,
                original=family,
                replacement=fallback or "padrao do chessfss",
                detail=(
                    f"A familia de pecas '{family}' nao esta instalada na arvore TeX "
                    f"desta maquina. Pedi-la assim mesmo faz o pdflatex parar com "
                    f"'cannot open Type 1 font file' e nao gerar PDF nenhum, entao o "
                    f"documento foi gravado com "
                    f"'{fallback or 'o padrao do chessfss'}'. O SVG (HTML, EPUB, PDF) "
                    f"continua usando '{wanted or family}': o mesmo livro sai com "
                    "desenhos diferentes nos dois caminhos ate que o pacote Type1 "
                    "correspondente seja instalado."
                ),
            )
            return _replace(settings, font_family=fallback)
        if wanted and family and wanted.lower() not in family.lower():
            context.note(
                f"O documento pede '{wanted}' e o LaTeX vai usar a familia chessfss "
                f"'{family}'. Confira se sao o mesmo conjunto de pecas."
            )
        return settings

    # -- blocks ------------------------------------------------------------

    def block(self, node: Block) -> str:
        """Render one block.

        Args:
            node: The block.

        Returns:
            The LaTeX.
        """
        with self._context.at(f"{tag_of(node)}/"):
            self._context.count("nodes")
            self._context.audit_node_fields(node)
            handler = getattr(self, f"_block_{tag_of(node)}", None)
            if handler is None:
                self._context.audit_node(node)
                return f"% no nao suportado: {tag_of(node)}"
            if getattr(node, "props", None) is not None:
                self._context.audit_paragraph_props(node.props, node=node)
            return str(handler(node))

    def blocks(self, nodes: Sequence[Block]) -> str:
        """Render a sequence of blocks.

        Args:
            nodes: The blocks.

        Returns:
            The LaTeX, one block per paragraph.
        """
        return "\n\n".join(self.block(node) for node in nodes if node is not None)

    def _block_heading(self, node: Heading) -> str:
        if self._in_cell:
            return f"\\textbf{{{self.inlines(node.content)}}}"
        command = _HEADING_COMMAND[min(node.level, len(_HEADING_COMMAND)) - 1]
        body = self.inlines(node.content)
        star = "" if node.list_in_toc else "*"
        label = f"\\label{{{tex.escape_latex(node.anchor)}}}" if node.anchor else ""
        # A heading is a *moving argument*: the ``book`` class copies it into
        # the table of contents and into the running head, and the running head
        # is uppercased. A ``\chessboard[setfen=...]`` that goes through that
        # comes out as ``SETFEN`` and stops the compiler. The optional argument
        # is LaTeX's own answer: plain text travels, the real title stays put.
        short = tex.escape_latex(
            node.toc_text or inline_plain_text(node.content, self._context.document)
        )
        optional = f"[{short}]" if star == "" and short else ""
        return f"\\{command}{star}{optional}{{{body}}}{label}"

    def _block_paragraph(self, node: Paragraph) -> str:
        body = self.inlines(node.content)
        if node.drop_cap:
            self._context.audit_feature("drop_cap", node=node, original="capitular")
        if self._in_cell:
            return body
        return _aligned(body, node.props)

    def _block_list_block(self, node: ListBlock) -> str:
        environment = _LIST_ENVIRONMENT.get(node.kind, "itemize")
        parts = [f"\\begin{{{environment}}}"]
        for item in node.items:
            parts.append(self._list_item(item, environment))
        parts.append(f"\\end{{{environment}}}")
        return "\n".join(parts)

    def _list_item(self, item: ListItem, environment: str) -> str:
        self._context.count("nodes")
        self._context.audit_node_fields(item)
        label = ""
        if environment == "description" and item.term:
            label = f"[{self.inlines(item.term)}]"
        body = self.blocks(item.content).replace("\n\n", "\n\n  ")
        return f"  \\item{label} {body}"

    def _block_quote(self, node: Quote) -> str:
        body = self.blocks(node.content)
        if node.attribution:
            body += f"\n\n\\hfill\\textit{{{self.inlines(node.attribution)}}}"
        return f"\\begin{{quote}}\n{body}\n\\end{{quote}}"

    def _block_callout(self, node: Callout) -> str:
        title = (
            self.inlines(node.title)
            if node.title
            else tex.escape_latex(_CALLOUT_LABEL.get(node.kind, "Nota"))
        )
        self._context.audit_feature("callout", node=node, original=node.kind.value)
        return (
            "\\begin{quote}\n"
            f"\\textbf{{{title}}}\\par\n"
            f"{self.blocks(node.content)}\n"
            "\\end{quote}"
        )

    def _block_code_block(self, node: CodeBlock) -> str:
        self._context.audit_feature("code_block", node=node, original=node.language or "texto")
        return f"\\begin{{verbatim}}\n{node.text}\n\\end{{verbatim}}"

    def _block_math_block(self, node: MathBlock) -> str:
        body = node.latex.strip()
        if node.numbered:
            return f"\\begin{{equation}}\n{body}\n\\end{{equation}}"
        return f"\\[\n{body}\n\\]"

    def _block_table(self, node: Table) -> str:
        columns = node.column_count or (
            max((len(row.cells) for row in node.rows), default=1)
        )
        spec = "|" + "l|" * columns
        parts = [f"\\begin{{tabular}}{{{spec}}}", "\\hline"]
        for row in node.rows:
            self._context.count("nodes")
            self._context.audit_node_fields(row)
            cells = []
            for cell in row.cells:
                self._context.count("nodes")
                self._context.audit_node_fields(cell)
                # A table cell is LR mode: an alignment *environment* inside one
                # stops the compiler dead with "Not allowed in LR mode". LaTeX's
                # own answer is the column specifier, so the cell's alignment
                # goes there instead.
                self._in_cell += 1
                try:
                    body = " ".join(self.block(child) for child in cell.content)
                finally:
                    self._in_cell -= 1
                spec = _CELL_SPEC.get(
                    cell.alignment.value if cell.alignment else "left", "l"
                )
                if cell.col_span > 1 or spec != "l":
                    body = f"\\multicolumn{{{cell.col_span}}}{{|{spec}|}}{{{body}}}"
                if cell.row_span > 1:
                    self._context.audit_feature(
                        "table_spans", node=cell, original=f"rowspan={cell.row_span}"
                    )
                cells.append(body)
            parts.append(" & ".join(cells) + " \\\\")
            parts.append("\\hline")
        parts.append("\\end{tabular}")
        table = "\n".join(parts)
        if node.caption:
            table = (
                "\\begin{table}[htbp]\n\\centering\n"
                + table
                + f"\n\\caption{{{self.inlines(node.caption)}}}\n\\end{{table}}"
            )
        return table

    def _block_figure(self, node: Figure) -> str:
        body = self.blocks(node.content)
        caption = (
            f"\n\\caption{{{self.inlines(node.caption)}}}" if node.caption else ""
        )
        return f"\\begin{{figure}}[htbp]\n\\centering\n{body}{caption}\n\\end{{figure}}"

    def _block_diagram(self, node: Diagram) -> str:
        """A diagram as ``\\chessboard``: still editable, never an image."""
        self._context.count("diagrams")
        marks = tuple(self._diagrams._marks_for(node))
        caption = self.inlines(node.caption) if node.caption else None
        return tex.diagram_block(
            node.fen,
            caption=caption,
            number=node.number is not None,
            marks=marks,
            inverse=node.orientation == "black",
            stipulation=node.stipulation,
        )

    def _block_image_block(self, node: ImageBlock) -> str:
        self._context.audit_feature("images", node=node, original=node.resource)
        path = self._image_path(node.resource)
        if path is None:
            return self._missing_image(node)
        return f"\\includegraphics[width=\\linewidth]{{{path}}}"

    def _image_path(self, key: str) -> str | None:
        """Resolve a resource key to a file pdflatex will actually find.

        Args:
            key: The resource key.

        Returns:
            The path, or ``None`` when the file is not on disk. Naming a
            file that is not there is a *fatal* pdflatex error rather than a
            missing picture, so it is never worth guessing.
        """
        resource = self._context.document.resource(key)
        if resource is None or not resource.path:
            return None
        return resource.path if Path(resource.path).exists() else None

    def _missing_image(self, node: Any) -> str:
        """Render an image whose file the project does not contain.

        Args:
            node: The image node.

        Returns:
            The placeholder, carrying the key so the author can find it.
        """
        self._context.recorder.unsupported(
            prop="images",
            node=node,
            path=self._context.path,
            original=node.resource,
            detail=(
                f"O arquivo do recurso '{node.resource}' nao esta no disco. Um "
                "\\\\includegraphics apontando para um arquivo ausente e erro "
                "fatal no pdflatex, entao a imagem virou um marcador de texto."
            ),
        )
        return f"\\texttt{{[{tex.escape_latex(node.resource)}]}}"

    def _block_game_score(self, node: GameScore) -> str:
        """A game as ``\\newchessgame`` plus ``\\mainline``: the moves stay text."""
        self._context.count("games")
        moves = _mainline_text(node)
        if moves and not _is_playable(moves, node.initial_fen):
            # ``\\mainline`` hands the moves to xskak, which replays them on a
            # real board and stops the compiler dead on the first one it cannot
            # make. A game that does not replay is still worth printing; it just
            # cannot drive a diagram, and the report says so.
            self._context.recorder.substituted(
                prop="game_score",
                node=node,
                path=self._context.path,
                original="\\mainline",
                replacement="texto monoespacado",
                detail=(
                    "Os lances desta partida nao sao jogaveis a partir da posicao "
                    "inicial declarada. O xskak recusa uma partida assim e o pdflatex "
                    "para de compilar, entao ela foi gravada como texto: legivel, mas "
                    "sem tabuleiro que a acompanhe."
                ),
            )
            body = tex.escape_latex(moves)
            return f"\\begin{{quote}}\\texttt{{{body}}}\\end{{quote}}"
        parts = [tex.newgame(node.initial_fen if node.initial_fen else None)]
        if moves:
            parts.append(tex.mainline(moves))
        parts.extend(
            tex.variation(line)
            for line in _variation_lines(node)
            if _is_playable(line, node.initial_fen)
        )
        return "\n".join(parts)

    def _block_footnote(self, node: Footnote) -> str:
        return f"\\footnote{{{self.blocks(node.content)}}}"

    def _block_endnote(self, node: Endnote) -> str:
        self._notes.append(node)
        return ""

    def _block_page_break(self, node: PageBreak) -> str:
        return "\\newpage"

    def _block_section_break(self, node: SectionBreak) -> str:
        for feature, present in (
            ("columns", node.columns is not None),
            ("page_geometry", node.geometry is not None),
            ("headers_footers", bool(node.header_text or node.footer_text)),
        ):
            if present:
                self._context.audit_feature(feature, node=node, original=node.kind.value)
        return "\\clearpage"

    def _block_thematic_break(self, node: ThematicBreak) -> str:
        if node.ornament:
            return f"\\begin{{center}}{tex.escape_latex(node.ornament)}\\end{{center}}"
        return "\\begin{center}\\rule{0.3\\linewidth}{0.4pt}\\end{center}"

    def _block_group(self, node: Group) -> str:
        title = f"\\textbf{{{self.inlines(node.title)}}}\\par\n" if node.title else ""
        if node.columns:
            self._context.audit_feature("columns", node=node, original=str(node.columns))
            return (
                f"\\begin{{multicols}}{{{node.columns}}}\n{title}"
                f"{self.blocks(node.content)}\n\\end{{multicols}}"
            )
        return title + self.blocks(node.content)

    def _block_table_of_contents(self, node: TableOfContents) -> str:
        return "\\tableofcontents"

    def _block_raw_passthrough(self, node: RawPassthrough) -> str:
        if node.format.lower() in ("latex", "tex"):
            return node.text
        self._context.audit_feature("raw_passthrough", node=node, original=node.format)
        return f"% RawPassthrough({node.format}) ignorado"

    def _endnotes(self) -> str:
        """Render the collected endnotes as a final section."""
        parts = ["\\section*{Notas}", "\\begin{enumerate}"]
        for note in self._notes:
            parts.append(f"  \\item {self.blocks(note.content)}")
        parts.append("\\end{enumerate}")
        return "\n".join(parts)

    # -- inlines -----------------------------------------------------------

    def inlines(self, nodes: Sequence[Inline]) -> str:
        """Render inline content.

        Args:
            nodes: The inlines.

        Returns:
            The LaTeX.
        """
        return "".join(self.inline(node) for node in nodes)

    def inline(self, node: Inline) -> str:
        """Render one inline.

        Args:
            node: The inline.

        Returns:
            The LaTeX.
        """
        self._context.count("nodes")
        self._context.audit_node_fields(node)
        if getattr(node, "props", None) is not None:
            self._context.audit_run_props(node.props, node=node)
        handler = getattr(self, f"_inline_{tag_of(node)}", None)
        if handler is None:
            self._context.audit_node(node)
            return ""
        return str(handler(node))

    def _inline_text(self, node: Text) -> str:
        return _styled(_figurines_to_macros(tex.escape_latex(node.content)), node.props)

    def _inline_emphasis(self, node: Emphasis) -> str:
        return f"\\emph{{{self.inlines(node.content)}}}"

    def _inline_strong(self, node: Strong) -> str:
        return f"\\textbf{{{self.inlines(node.content)}}}"

    def _inline_underline(self, node: Underline) -> str:
        return f"\\underline{{{self.inlines(node.content)}}}"

    def _inline_strike(self, node: Strike) -> str:
        self._context.audit_feature("strike", node=node, original="tachado")
        return f"\\sout{{{self.inlines(node.content)}}}"

    def _inline_small_caps(self, node: SmallCaps) -> str:
        return f"\\textsc{{{self.inlines(node.content)}}}"

    def _inline_superscript(self, node: Superscript) -> str:
        return f"\\textsuperscript{{{self.inlines(node.content)}}}"

    def _inline_subscript(self, node: Subscript) -> str:
        return f"\\textsubscript{{{self.inlines(node.content)}}}"

    def _inline_span(self, node: Any) -> str:
        return self.inlines(node.content)

    def _inline_link(self, node: Link) -> str:
        body = self.inlines(node.content)
        target = tex.escape_latex(node.target)
        return f"\\href{{{target}}}{{{body}}}"

    def _inline_move(self, node: Move) -> str:
        rendered = render_move(node, self._context.document)
        body = _figurines_to_macros(tex.escape_latex(rendered))
        return f"\\mbox{{{body}}}"

    def _inline_piece_glyph(self, node: PieceGlyph) -> str:
        # The trailing braces stop TeX gluing the next word onto the
        # control sequence: \\symknight followed by "torre" is
        # read as one undefined macro named \\symknighttorre.
        return f"\\sym{node.piece.value}{{}}"

    def _inline_nag_symbol(self, node: NagSymbol) -> str:
        return _figurines_to_macros(tex.escape_latex(nag_symbol(node.nag)))

    def _inline_note_ref(self, node: NoteRef) -> str:
        return f"\\textsuperscript{{{tex.escape_latex(node.marker or node.ref)}}}"

    def _inline_inline_diagram(self, node: InlineDiagram) -> str:
        self._context.count("diagrams")
        return tex.chessboard_command(
            node.fen,
            marks=tuple(self._diagrams._marks_for(node)),
            inverse=node.orientation.value == "black",
            board_font_size="8pt",
        )

    def _inline_math_inline(self, node: MathInline) -> str:
        return f"${node.latex}$"

    def _inline_image_inline(self, node: ImageInline) -> str:
        self._context.audit_feature("images", node=node, original=node.resource)
        path = self._image_path(node.resource)
        if path is None:
            return self._missing_image(node)
        return f"\\includegraphics[height=1em]{{{path}}}"

    def _inline_anchor(self, node: Any) -> str:
        return f"\\label{{{tex.escape_latex(node.name)}}}"

    def _inline_index_entry(self, node: Any) -> str:
        self._context.audit_feature("index_entry", node=node, original="|".join(node.terms))
        return f"\\index{{{tex.escape_latex('!'.join(node.terms))}}}"

    def _inline_line_break(self, node: LineBreak) -> str:
        return "\\\\\n"

    def _inline_non_breaking_space(self, node: NonBreakingSpace) -> str:
        return "~"

    def _inline_space(self, node: Space) -> str:
        return "\\ "

    def _inline_tab(self, node: Any) -> str:
        self._context.audit_paragraph_props(None, node=node)
        return "\\quad "

    def _inline_raw_inline(self, node: RawInline) -> str:
        if node.format.lower() in ("latex", "tex"):
            return node.text
        self._context.audit_feature("raw_passthrough", node=node, original=node.format)
        return ""


# --------------------------------------------------------------------------- #
# Run and paragraph formatting
# --------------------------------------------------------------------------- #
def _styled(body: str, props: Any) -> str:
    """Wrap escaped text in the LaTeX commands its run properties call for.

    Args:
        body: The already-escaped text.
        props: The run properties.

    Returns:
        The wrapped text.
    """
    if props is None or not body:
        return body
    if props.italic:
        body = f"\\emph{{{body}}}"
    if props.font_weight is not None and props.font_weight >= 600:
        body = f"\\textbf{{{body}}}"
    if props.small_caps is not None and props.small_caps.value != "none":
        body = f"\\textsc{{{body}}}"
    if props.no_break:
        body = f"\\mbox{{{body}}}"
    return body


def _aligned(body: str, props: Any) -> str:
    """Wrap a paragraph in an alignment environment when it asks for one.

    Args:
        body: The rendered inlines.
        props: The paragraph properties.

    Returns:
        The paragraph.
    """
    if props is None or props.alignment is None:
        return body
    environment = {
        "center": "center",
        "right": "flushright",
        "left": "flushleft",
    }.get(props.alignment.value)
    if environment is None:
        return body
    return f"\\begin{{{environment}}}\n{body}\n\\end{{{environment}}}"


def _is_playable(moves: str, initial_fen: str | None) -> bool:
    """Whether ``xskak`` will manage to replay this move text.

    ``\\mainline`` is not a formatting command: it plays the moves on a board so
    that ``\\chessboard`` can show the position afterwards. A move it cannot
    make is a *compile error*, not a rendering glitch, so the question has to be
    asked before the macro is written.

    Args:
        moves: The SAN move text, without headers or result.
        initial_fen: The position the game starts from, if it is not the usual
            one.

    Returns:
        ``True`` when every move is legal in turn.
    """
    import chess

    try:
        board = chess.Board(initial_fen) if initial_fen else chess.Board()
    except ValueError:
        return False
    for token in moves.replace("...", " ").split():
        if token[0].isdigit() and token.rstrip(".").isdigit():
            continue
        try:
            board.push_san(token)
        except (ValueError, AssertionError):
            return False
    return True


def _mainline_text(score: GameScore) -> str:
    """Render a game's main line as ``xskak`` move text.

    Args:
        score: The game.

    Returns:
        The move text, without headers or result.
    """
    pgn = game_to_pgn(score, include_headers=False)
    body = re.sub(r"\([^()]*\)", "", pgn)
    body = re.sub(r"\{[^{}]*\}", "", body)
    body = re.sub(r"\$\d+", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    for result in ("1-0", "0-1", "1/2-1/2", "*"):
        if body.endswith(result):
            body = body[: -len(result)].strip()
            break
    return body


def _variation_lines(score: GameScore) -> list[str]:
    """Collect the side lines, so they are not lost with the parentheses.

    ``\\mainline`` cannot carry a variation, and dropping the parenthesised text
    would delete analysis. Each variation becomes its own ``\\variation``.

    Args:
        score: The game.

    Returns:
        One move-text string per variation, outermost first.
    """
    from dataclasses import replace

    lines: list[str] = []

    def visit(node: MoveNode) -> None:
        for index, child in enumerate(node.children):
            if index:
                text = _mainline_text(replace(score, children=(child,)))
                if text:
                    lines.append(text)
            visit(child)

    for child in score.children:
        visit(child)
    return lines


# --------------------------------------------------------------------------- #
# The sidecar
# --------------------------------------------------------------------------- #
EXTRA_PACKAGES = r"""
% --- pacotes que o exportador precisa alem do preambulo do typesetter ---
% caissa.typeset.latex monta o preambulo de xadrez, que e o que importa e o
% que nao deve ser duplicado aqui. Estes tres sao exigencias do *conteudo*
% que qualquer documento pode ter e que o preambulo de xadrez nao precisa
% conhecer: ligacoes, texto tachado e entradas remissivas. Sem eles o
% pdflatex para com "Undefined control sequence" -- medido, nao suposto.
\usepackage[normalem]{ulem}        % \sout, sem sequestrar \emph
\usepackage{makeidx}               % \index
\makeindex
\usepackage[hidelinks]{hyperref}   % \href e \label; por ultimo
"""
"""Preamble lines the exported content needs and the chess preamble does not."""


def _with_extra_packages(text: str) -> str:
    r"""Insert the extra package block just before ``\begin{document}``.

    Args:
        text: The rendered document.

    Returns:
        The document with the packages loaded.

    Raises:
        ValueError: The rendered document has no ``\begin{document}``.
    """
    marker = r"\begin{document}"
    if marker not in text:
        raise ValueError(r"O documento LaTeX gerado nao tem \begin{document}.")
    head, _, tail = text.partition(marker)
    return head + EXTRA_PACKAGES + chr(10) + marker + tail


def _sidecar(document: Document) -> str:
    """Serialise the IR into TeX comment lines.

    Args:
        document: The IR.

    Returns:
        The comment block.
    """
    payload = json.dumps(document_to_payload(document), ensure_ascii=True, separators=(",", ":"))
    chunks = [
        payload[index : index + _SIDECAR_WIDTH]
        for index in range(0, len(payload), _SIDECAR_WIDTH)
    ]
    lines = [
        "% ---------------------------------------------------------------------",
        "% IR do Caissa Studio. Nao edite: e o que permite reabrir este arquivo",
        "% no editor sem perder nada. Remova o bloco inteiro para descarta-lo.",
    ]
    lines.extend(SIDECAR_PREFIX + chunk for chunk in chunks)
    return "\n".join(lines) + "\n"


def read_latex(path: Path | str) -> Document:
    """Read a ``.tex`` written by :class:`LatexExporter` back into the IR.

    This reads the embedded IR, not the TeX. See the module docstring: a
    fidelity number obtained through it measures serialisation, and
    :mod:`caissa.export.fidelity` labels it ``method="sidecar"`` for exactly
    that reason.

    Args:
        path: The ``.tex`` file.

    Returns:
        The document.

    Raises:
        ValueError: The file carries no embedded IR.
    """
    text = Path(path).read_text(encoding="utf-8")
    chunks = [
        line[len(SIDECAR_PREFIX) :]
        for line in text.splitlines()
        if line.startswith(SIDECAR_PREFIX)
    ]
    if not chunks:
        raise ValueError(
            "Este .tex nao carrega o IR embutido; nao ha como reconstruir o documento "
            "a partir de LaTeX."
        )
    document, _migrations = document_from_payload(json.loads("".join(chunks)))
    return document
