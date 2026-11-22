"""The square marks endgame books print -- X, cross, dot, ring, star -- drawn as the book has them.

They reach the IR from the trunk's notebook (:mod:`caissa.export.page_texts`) as ``CROSS``, ``DOT``
and ``LABEL`` marks.  What is pinned here:

* the canonical renderer draws each as a symbol in the middle of the square, in the piece ink,
  and a board without them renders exactly as before;
* the diagram translation turns those IR marks into symbols with no degradation, and keeps the
  fallback (and its warning) for a label that is not one of the book's symbols;
* two diagrams of the same position with different symbols do not share a cached render;
* LaTeX, whose ``chessboard`` has no symbols, draws the ring and says so.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from caissa.core.model import Diagram, Document, DocumentMetadata, Mark, MarkKind
from caissa.export import export
from caissa.export.base import ExportContext
from caissa.export.diagrams import DiagramRenderer
from caissa.export.profiles import HTML_PROFILE
from caissa.typeset.board_svg import DiagramStyle, SymbolMark, SymbolShape, get_theme, render_svg

SVG_NS = "{http://www.w3.org/2000/svg}"
KINGS = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"


def _symbols(svg: str, ink: str) -> list[ET.Element]:
    """The elements drawn in ``ink`` that are not pieces: what a mark adds to the board."""
    root = ET.fromstring(svg)  # noqa: S314 - o SVG foi gerado aqui, não veio de fora
    return [
        element
        for element in root.iter()
        if element.tag in (f"{SVG_NS}path", f"{SVG_NS}circle")
        and ink.lower() in ((element.get("fill") or "") + (element.get("stroke") or "")).lower()
    ]


@pytest.mark.parametrize("shape", ["cross", "plus", "dot", "ring", "star", "star-outline"])
def test_each_symbol_adds_ink_to_the_board(shape: SymbolShape) -> None:
    style = DiagramStyle()
    ink = get_theme(style.theme).piece_ink
    plain = render_svg(KINGS, style)
    marked = render_svg(KINGS, style, marks=[SymbolMark("c6", shape)])
    assert marked != plain
    assert len(_symbols(marked, ink)) > len(_symbols(plain, ink))


def test_a_board_without_symbols_renders_as_before() -> None:
    style = DiagramStyle()
    assert render_svg(KINGS, style) == render_svg(KINGS, style, marks=[])


def _render(*marks: Mark) -> tuple[str, list[str]]:
    diagram = Diagram(fen=KINGS, marks=marks)
    context = ExportContext(HTML_PROFILE, Document(body=(diagram,)))
    svg = DiagramRenderer(context).svg(diagram).svg
    return svg, [w.property for w in context.recorder.report().warnings]


def test_the_book_marks_become_symbols_without_degradation() -> None:
    marks = (
        Mark(kind=MarkKind.CROSS, squares=("d4",)),
        Mark(kind=MarkKind.DOT, squares=("f3",), filled=True),
        Mark(kind=MarkKind.DOT, squares=("c6",)),
        Mark(kind=MarkKind.LABEL, squares=("b2",), text="+"),
        Mark(kind=MarkKind.LABEL, squares=("e6",), text="★"),
        Mark(kind=MarkKind.LABEL, squares=("g6",), text="☆"),
    )
    _svg, warnings = _render(*marks)
    assert warnings == []


def test_a_label_that_is_not_a_book_symbol_still_degrades() -> None:
    _svg, warnings = _render(Mark(kind=MarkKind.LABEL, squares=("d4",), text="A"))
    assert warnings == ["mark"]


def test_different_symbols_do_not_share_a_cached_render() -> None:
    star = Diagram(fen=KINGS, marks=(Mark(kind=MarkKind.LABEL, squares=("c6",), text="★"),))
    cross = Diagram(fen=KINGS, marks=(Mark(kind=MarkKind.CROSS, squares=("c6",)),))
    renderer = DiagramRenderer(ExportContext(HTML_PROFILE, Document(body=(star, cross))))
    assert renderer.svg(star).svg != renderer.svg(cross).svg


def test_latex_draws_the_ring_and_says_so(tmp_path: Path) -> None:
    diagram = Diagram(fen=KINGS, marks=(Mark(kind=MarkKind.CROSS, squares=("d4",)),))
    document = Document(metadata=DocumentMetadata(title="x"), body=(diagram,))
    result = export(document, tmp_path / "livro.tex", "latex")
    substituted = [w for w in result.degradation.warnings if w.property == "mark"]
    assert [(w.original, w.replacement) for w in substituted] == [("cross", "circulo")]
    assert "markfields={d4}" in (tmp_path / "livro.tex").read_text(encoding="utf-8")
