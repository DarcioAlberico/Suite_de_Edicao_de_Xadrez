"""Generate the LaTeX export of the blind-comparison page and **compile it**.

Writes to `benchmarks/reports/latex/`: `livro.tex`, `Makefile`, the compiler log, and
-- only if the compiler actually produced one -- `livro.pdf`.

One source, two exporters
-------------------------
The page set here is **the same page** `tools/typeset_proofsheet.py` sets through the SVG
path: the same `book_source_*()` list of blocks, the same `typography.prepared()` pass,
the same `parse_markup()` runs. Cycle 2 had two hand-written sources that happened to
share two passages of moves, and `compare_exporters.py` compared exactly those two
passages: the critic found five divergences outside what it looked at -- the caption's
check symbol, the caption's dash, the space after the ellipsis in the running head, and
71 bold spans on one side against 7 on the other.

A divergence is now a bug in the translation of one run list, not a difference between
two documents, and `compare_exporters.py` compares the whole page.

The point of this script is still that it either produces a PDF or says plainly that it
did not. `caissa.typeset.latex.compile_document` reports the engine it found, the exit
status and the first errors from the log; nothing here infers success from the absence of
an exception.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import typeset_page as tp  # noqa: E402
import typeset_proofsheet as ps  # noqa: E402
from caissa.typeset import latex  # noqa: E402
from caissa.typeset.board_svg import SquareHighlight  # noqa: E402

OUT = ROOT / "benchmarks" / "reports" / "latex"

RUNNING_HEAD = ps.MARECO_RUNNING_HEAD
"""Identical to the SVG page's, before `prepared()`; both sides run it through that.

Imported rather than repeated. Cycle 5's blind harness kept its own copy of the *other*
page's head and shipped it without accents; a string that two exporters have to agree on
belongs beside the page it heads."""


# --------------------------------------------------------------------------- #
# The shared translation: one run list, two renderers
# --------------------------------------------------------------------------- #
def runs_to_tex(text: str, *, language: str = "en", figurines: bool = True) -> str:
    """Marked-up source to LaTeX, through the *same* runs the SVG page is set from.

    `tp.prepared` applies the house typography (curly quotes, dashes, the ellipsis, the
    dagger, U+00B1 and U+2212) and `tp.parse_markup` splits the result into runs of one
    face, figurining every move it recognises. Both are the SVG path's own functions.
    Here each run becomes LaTeX: a text run through `latex.typographic_tex`, a piece run
    through `latex.figurine_symbol`, and the face through `\\textbf` / `\\textit`.

    That is what makes the two exports comparable span by span as well as token by token:
    a bold run on one side is a bold run on the other by construction.
    """
    out: list[str] = []
    for run in tp.parse_markup(tp.prepared(text, language), figurines=figurines):
        if run.kind == "piece":
            body = latex.figurine_symbol(run.content)
        else:
            body = latex.typographic_tex(tp.for_output(run.content))
        if run.face in ("bold", "bolditalic"):
            body = f"\\textbf{{{body}}}"
        if run.face in ("italic", "bolditalic"):
            body = f"\\textit{{{body}}}"
        out.append(body)
    return "".join(out)


def _play(board, text: str) -> tuple[str, object]:  # noqa: ANN001
    """``\\hidemoves`` for the moves in ``text``, after proving every one of them legal.

    Two failures this prevents, both of which killed earlier versions of this script:
    a move line with no ``\\newchessgame`` in front of it, and a move that is illegal from
    the current position. Both fail as ``File ended while scanning use of \\FenBoard``, a
    message that names neither the macro at fault nor the line -- so a LaTeX build cannot
    fail here for a reason python-chess could have caught in a millisecond.

    The moves are handed to ``skak`` **with their numbers**, in PGN form: `\\hidemoves`
    parses `13...bxc5 14.Nb3` and rejects a bare `bxc5` with `Argument of \\EatNumberA has
    an extra }`, which is what a first version of this function produced.
    """
    import chess

    played: list[str] = []
    first = True
    for token in re.sub(r"[*_]{2}", "", text).split():
        san = re.sub(r"^\d{1,3}\.{1,3}", "", token).rstrip(".,;:")
        if not san or san in ("1-0", "0-1", "1/2-1/2", "1–0", "0–1"):
            continue
        for mark in ("+-", "-+", "+/-", "-/+", "+/=", "=/+", "!", "?"):
            san = san.replace(mark, "")
        if not san:
            continue
        try:
            move = board.parse_san(san)
        except ValueError:
            return "", board  # a side line, not the game: typeset it, do not play it
        number = board.fullmove_number
        if board.turn == chess.WHITE:
            played.append(f"{number}.{san}")
        elif first:
            played.append(f"{number}...{san}")
        else:
            played.append(san)
        board.push(move)
        first = False
    return (latex.played(" ".join(played)) if played else ""), board


def latex_book(source: list[dict], *, language: str = "en") -> str:
    """The block list of `typeset_proofsheet.book_source_*` as a LaTeX body."""
    import chess

    body: list[str] = []
    indent_em = 1.1  # the same measure the SVG page indents a variation by
    board = chess.Board()
    for index, item in enumerate(source):
        kind = item["kind"]
        text = item.get("text", "")
        if kind == "title":
            body.append(f"\\gameheading{{{runs_to_tex(text, language=language, figurines=False)}}}")
        elif kind == "centre":
            body.append(
                "{\\centering " + runs_to_tex(text, language=language, figurines=False)
                + "\\par}"
            )
        elif kind == "centre-bold":
            body.append(
                "{\\centering\\bfseries "
                + runs_to_tex(text, language=language, figurines=False) + "\\par}"
            )
        elif kind == "diagram":
            fen = item["fen"]
            body.append(latex.newgame(fen))
            body.append(latex.diagram_block(
                fen,
                marks=item.get("marks", ()),
                caption_tex=runs_to_tex(item.get("caption", ""), language=language),
            ))
        elif kind == "variation":
            # An indented BLOCK: `\leftskip` carries the indent onto every line of it,
            # which is the whole point (see `typeset_page.Paragraph.block_indent`).
            body.append(
                f"{{\\par\\leftskip={indent_em}em\\noindent "
                + runs_to_tex(text, language=language) + "\\par}"
            )
        elif kind == "move":
            move_tex, board = _play(board, text)
            body.append(move_tex + "\\noindent "
                        + runs_to_tex(text, language=language) + "\\par")
        elif kind == "body0":
            # `body0` means *flush*, and flush is right only after something displayed --
            # a title, a venue line, a cross-head, a diagram. `book_blocks` applies the
            # same rule on the SVG side and it has to be applied here too, because an
            # indent is not a token: `compare_exporters` reported 198 tokens, 43 pieces
            # and 93 bold runs identical while one exporter opened
            # `Better was: 13...Nxc5` flush and the other opened it indented. Found by
            # putting the two pages side by side, which is what the cycle-4 critique says
            # the token comparison exists to make room for, not to replace.
            previous = source[index - 1]["kind"] if index else ""
            flush = previous in ("title", "centre", "centre-bold", "diagram")
            body.append(("\\noindent " if flush else "")
                        + runs_to_tex(text, language=language) + "\\par")
        else:
            body.append(runs_to_tex(text, language=language) + "\\par")
    return "\n".join(body)


def build_source(source=None, *, language: str = "en") -> str:
    # Pick a piece set whose Type1 font is actually installed. `merida` is our preferred
    # set and matches the SVG side, but it is not in this machine's MiKTeX; asking for it
    # anyway would fail the build rather than degrade.
    family = latex.first_available_family(
        ["merida", "alpha", "berlin", "leipzig", "condal", "skaknew"]
    )
    print(f"familia chessfss disponivel: {family or '(nenhuma -- usando o padrao)'}")
    options = latex.LatexOptions(
        language=language,
        font_family=family,
        board_font_size="16pt",
        # The same body size and leading the SVG page is set at, measured off the
        # Quality Chess reference: 8.6 over 10.406 pt. Same source, same setting.
        body_size_pt=8.6,
        body_leading_pt=8.6 * 1.21,
        # The SVG page's `DiagramStyle` leaves `side_to_move=SideToMove.NONE`, so its
        # diagrams carry no mover box. `chessboard`'s own default is `showmover=true`,
        # and the cycle-3 LaTeX proof therefore printed a filled square at the top right
        # of all three diagrams that the SVG proof does not print. Q5's claim is that the
        # two exporters set the same book *indistinguishably*; a box present on one side
        # and absent on the other is exactly the kind of difference that claim forbids,
        # and it is one line to remove.
        show_mover=False,
        document_class="book",
        class_options="10pt,twoside",
        geometry="paperwidth=160.9mm,paperheight=228.6mm,inner=14mm,outer=14mm,"
        "top=17mm,bottom=16mm",
        two_column=True,
    )
    doc = latex.LatexDocument(options=options)
    # NOT `\chapter*`: inside `multicols` it injects the chapter's opening space into the
    # column -- 25 mm of dead white at the top of column 1 in the cycle-1 proof -- and
    # sets a display-size title in a 63 mm measure, where the title broke mid-phrase.
    # `\markboth` alone sets nothing: the `book` class only shows a running head under
    # `headings`, which it enters at a `\chapter` this document does not have.
    head = runs_to_tex(RUNNING_HEAD, language=language, figurines=False)
    doc.add(r"\pagestyle{myheadings}")
    doc.add(f"\\markboth{{{head}}}{{{head}}}")
    doc.add(latex.newgame())
    doc.add(latex_book(source or ps.book_source_mareco(), language=language))
    return doc.render()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="pdflatex")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / "livro.tex"
    tex_path.write_text(build_source(), encoding="utf-8")
    (out_dir / "Makefile").write_text(
        latex.makefile("livro.tex", engine=args.engine), encoding="utf-8"
    )
    print(f"fonte escrita: {tex_path}  ({len(tex_path.read_text(encoding='utf-8'))} bytes)")

    found = latex.tex_available(args.engine)
    print(f"motor {args.engine}: {found or 'NAO ENCONTRADO'}")

    result = latex.compile_document(
        tex_path, engine=args.engine, workdir=out_dir, runs=2, timeout=args.timeout
    )
    (out_dir / "compile.log").write_text(result.log or "", encoding="utf-8")
    print(result.summary())
    substitutions = [
        line for line in (result.log or "").splitlines()
        if "Font shape" in line and "undefined" in line
    ]
    print(f"substituicoes de fonte nao declaradas: {len(substitutions)}"
          + ("".join("\n    " + s for s in substitutions) if substitutions else ""))
    if result.ok and result.pdf:
        import pymupdf

        # The searchable layer. pdfTeX names the figurine slots after the text glyphs
        # that share them -- `dagger`, `ellipsis`, `florin` -- so the compiled PDF says
        # `1.d4 (dagger)f6` where the page reads `1.d4 Nf6`, and two of those three
        # characters are this book's own check mark and Black-move ellipsis.
        for font, what in latex.retag_figurine_text(result.pdf).items():
            print(f"camada de texto: {font}: {what}")

        doc = pymupdf.open(result.pdf)
        print(f"PDF: {result.pdf}  paginas={doc.page_count}")
        for index in range(min(doc.page_count, 4)):
            png = out_dir / f"page_{index + 1:02d}.png"
            doc[index].get_pixmap(dpi=150).save(str(png))
            print("  ", png)
        doc.close()
        return 0

    print("COMPILACAO FALHOU -- a saida LaTeX NAO esta verificada.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
