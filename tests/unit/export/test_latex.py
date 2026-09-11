"""LaTeX output, and the four things that stop ``pdflatex`` dead.

A ``.tex`` file that does not compile is not a degraded export, it is no export
at all -- and none of the four failures below shows up in any check short of
running the engine. Each was measured on the reference machine, and each has a
test here so it cannot come back:

*   an alignment environment inside a table cell (``Not allowed in LR mode``);
*   a game whose moves ``xskak`` cannot replay;
*   a Unicode chess glyph, which ``inputenc`` refuses outright;
*   a piece family whose Type 1 file is not in the TeX tree.

``test_the_project_compiles`` runs the engine when the machine has one, which is
the only check that proves the rest are complete.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from caissa.core.model import (
    Alignment,
    Document,
    DocumentMetadata,
    GameHeaders,
    GameScore,
    Heading,
    MoveNode,
    Paragraph,
    ParagraphProps,
    PieceGlyph,
    Table,
    TableCell,
    TableColumn,
    TableRow,
    Text,
)
from caissa.core.chess.notation_tables import PieceType
from caissa.export import export
from caissa.export.latex import LatexOptions, read_latex

STARTING = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _document(*blocks: object) -> Document:
    """Wrap blocks in a minimal document.

    Args:
        *blocks: The body.

    Returns:
        The document.
    """
    return Document(
        metadata=DocumentMetadata(title="Teste", language="pt-BR"),
        body=tuple(blocks),  # type: ignore[arg-type]
    )


def test_a_cell_never_opens_an_alignment_environment(tmp_path: Path) -> None:
    """``\\begin{flushright}`` inside a cell is a fatal LR-mode error.

    The alignment goes into the column specifier, which is where LaTeX keeps it.
    """
    table = Table(
        columns=(TableColumn(),),
        rows=(
            TableRow(
                cells=(
                    TableCell(
                        content=(
                            Paragraph(
                                content=(Text(content="direita"),),
                                props=ParagraphProps(alignment=Alignment.RIGHT),
                            ),
                        ),
                        alignment=Alignment.RIGHT,
                    ),
                )
            ),
        ),
    )
    target = tmp_path / "tabela.tex"
    export(_document(table), target, "latex")
    source = target.read_text(encoding="utf-8").split("%%CAISSA-IR")[0]

    assert "\\begin{flushright}" not in source
    assert "\\multicolumn{1}{|r|}" in source


def test_an_unplayable_game_becomes_text_and_says_so(tmp_path: Path) -> None:
    """``\\mainline`` replays the moves; one it cannot make stops the compiler."""
    game = GameScore(
        headers=GameHeaders(),
        children=(
            MoveNode(san="Nbd7", ply=1, position_before=STARTING),
            MoveNode(san="Qh8", ply=2, position_before=STARTING),
        ),
    )
    target = tmp_path / "partida.tex"
    result = export(_document(game), target, "latex")
    # The body only: the typesetter's preamble names the macro in a comment.
    source = (
        target.read_text(encoding="utf-8")
        .split("%%CAISSA-IR")[0]
        .partition("\\begin{document}")[2]
    )

    assert "\\mainline" not in source
    assert "\\texttt{" in source
    assert any(
        warning.property == "game_score" for warning in result.degradation.warnings
    ), "a partida virou texto sem que o relatorio dissesse por que"


def test_a_figurine_becomes_a_chessfss_command(tmp_path: Path) -> None:
    """``inputenc`` refuses a raw chess glyph; ``\\symknight`` it understands."""
    target = tmp_path / "figurino.tex"
    export(
        _document(Paragraph(content=(PieceGlyph(piece=PieceType.KNIGHT),))),
        target,
        "latex",
    )
    source = target.read_text(encoding="utf-8").split("%%CAISSA-IR")[0]

    assert "\\symknight{}" in source
    assert not any(0x2654 <= ord(char) <= 0x265F for char in source)


def test_an_uninstalled_piece_set_is_replaced_and_reported(tmp_path: Path) -> None:
    """A family with no Type 1 file produces no PDF at all, so it is swapped.

    This is the F7 defect seen from the export side: the SVG path and the LaTeX
    path draw different pieces because the TeX tree lacks the font. The export
    cannot install it, but it refuses to ship a file that will not build, and
    the report names both sets.
    """
    from caissa.typeset import latex as tex

    absent = "estaFamiliaNaoExiste"
    target = tmp_path / "fonte.tex"
    result = export(
        _document(Paragraph(content=(Text(content="x"),))),
        target,
        "latex",
        options=LatexOptions(chess_font=absent),
    )
    if tex.chessfss_family_available(absent):  # pragma: no cover - defensive
        pytest.skip("a familia inventada existe nesta maquina")
    warnings = [w for w in result.degradation.warnings if w.property == "chess_font"]
    assert warnings, "a familia foi trocada em silencio"
    assert absent in (warnings[0].original or "")
    assert warnings[0].replacement


def test_the_preamble_loads_what_the_content_needs(tmp_path: Path) -> None:
    """Links, strike-through and index entries each need a package."""
    target = tmp_path / "pacotes.tex"
    export(_document(Paragraph(content=(Text(content="x"),))), target, "latex")
    source = target.read_text(encoding="utf-8")

    assert "\\usepackage[normalem]{ulem}" in source
    assert "\\usepackage{makeidx}" in source
    assert "hyperref}" in source
    assert "\\usepackage{chessboard}" in source, "o preambulo de xadrez sumiu"


def test_a_heading_travels_as_plain_text(tmp_path: Path) -> None:
    """A heading is a moving argument; the ``book`` class uppercases it.

    A ``\\chessboard[setfen=...]`` that goes through that comes back as
    ``SETFEN`` and the compile fails. The optional argument carries plain text.
    """
    target = tmp_path / "titulo.tex"
    export(
        _document(Heading(level=1, content=(Text(content="Primeiro"),))),
        target,
        "latex",
    )
    source = target.read_text(encoding="utf-8").split("%%CAISSA-IR")[0]
    assert "\\chapter[Primeiro]{" in source


def test_the_makefile_is_written_beside_the_source(tmp_path: Path) -> None:
    """SPEC section 8.5 asks for a generated ``Makefile``."""
    target = tmp_path / "livro.tex"
    result = export(_document(Paragraph(content=(Text(content="x"),))), target, "latex")
    makefile = tmp_path / "Makefile"
    assert makefile.exists()
    assert makefile in result.artifacts


def test_the_sidecar_reads_back(tmp_path: Path) -> None:
    """The embedded IR is what makes "reopen my export" work."""
    document = _document(Paragraph(content=(Text(content="x"),)))
    target = tmp_path / "livro.tex"
    export(document, target, "latex")
    assert read_latex(target).body


def _pdflatex() -> str | None:
    """Find a ``pdflatex`` on this machine.

    Returns:
        Its path, or ``None``.
    """
    from caissa.typeset import latex as tex

    return tex.tex_available("pdflatex") or shutil.which("pdflatex")


@pytest.mark.skipif(_pdflatex() is None, reason="Nenhum pdflatex nesta maquina.")
@pytest.mark.timeout(600)
def test_the_project_compiles(tmp_path: Path) -> None:
    """The only check that proves the others are complete: run the engine."""
    from generators import NodeFactory

    from corpus import CORPUS_SEED

    document = NodeFactory(CORPUS_SEED).document(min_nodes=200)
    target = tmp_path / "livro.tex"
    export(document, target, "latex")

    engine = _pdflatex()
    assert engine is not None
    result = subprocess.run(
        [engine, "-interaction=nonstopmode", target.name],
        cwd=tmp_path,
        capture_output=True,
        timeout=540,
        check=False,
    )
    output = (result.stdout + result.stderr).decode("utf-8", "replace")
    assert (tmp_path / "livro.pdf").exists(), output[-4000:]
