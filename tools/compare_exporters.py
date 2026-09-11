"""Compare the SVG export and the LaTeX export of the SAME page -- whole, not in patches.

Run it:

    .venv\\Scripts\\python.exe tools\\compare_exporters.py

Exit status is the number of divergences, so it can be used as a gate.

What changed after cycle 3
--------------------------
Cycle 2's version compared **two passages of moves** and reported one divergence. The
critic measured five, all outside what it looked at:

* the space after the ellipsis in the running head -- 5.12 pt in LaTeX, 0.00 pt in SVG;
* the check symbol in a diagram caption -- ``After 21.Bxh7+`` against ``After 21.Bxh7†.``;
* the caption's dash -- U+2014 against U+2013;
* **71 bold spans on the SVG side against 7 in LaTeX**: the LaTeX export set no move line
  in bold at all, so the convention that separates a main line from prose existed in one
  exporter and not in the other;
* the ellipsis glyph itself (admitted).

This version compares the whole text layer of both pages: every token, the captions, the
running head, and the *structure* -- which runs come out bold and which come out italic.
It can do that because both exports are now built from one source through one markup
pass; see the header of `tools/build_latex.py`.

What cycle 4 added
------------------
* **Italic.** Only bold was compared, and bold is half the structure: italic is what
  separates a caption and a player's name from prose, and the two exporters reach it from
  the same ``Run.face`` through different faces (``TimesNewRomanPS-ItalicMT`` against
  ``LMRoman9-Italic``). Fifteen runs on each side, compared token by token.
* **What this script still cannot see.** A box is not a token. `chessboard` defaults to
  ``showmover=true`` and the SVG side draws no mover box, so the cycle-3 LaTeX proof
  carried a filled square at the top right of every diagram while this script reported
  zero divergences. `tools/build_latex.py` now asks for ``show_mover=False`` and
  `test_the_two_exporters_draw_the_same_board_furniture` holds the two settings together.
  The lesson is in the test, not here: run the script *and* look at the two pages.

What cycle 6 added: the pieces
------------------------------
Cycle 5's version normalised the **figurines out of both sides**. The critic sabotaged a
copy of `livro.tex`, turned one `\\cfig{knight}` into `\\cfig{queen}` so that the page
printed `1.d4` with a queen on f6 -- an impossible move in the book's first line -- and
this script still reported *"222 tokens, identicos ... 0 divergencias nao declaradas"*
and exited 0. A parity gate that cannot tell a knight from a queen cannot certify parity
of a chess book, and about 15 % of the tokens on the page are pieces.

It could not see them because neither exporter left the piece in the text layer at all,
so there was nothing to compare and the normalisation was the only way to make the two
streams line up. Both sides now emit the piece as text -- an invisible letter under the
vector path on the SVG side (`typeset_page.Canvas.hidden_text`), a corrected ToUnicode on
the LaTeX side (`caissa.typeset.latex.retag_figurine_text`) -- so:

* the whole-page token stream **contains the pieces** and a wrong piece is a wrong token;
* `--- identidade das pecas` compares the ordered list of piece glyphs of the two pages,
  read from the drawings themselves: on the SVG side the letter must sit on a vector
  path, on the LaTeX side it must be a glyph of the chess font;
* `--- identidade das pecas na fonte` compares the `\\cfig{...}` arguments of the
  generated `.tex`, when it is beside the PDF, against the same run list the SVG page is
  set from -- so a sabotage of the source is caught even before it is compiled.

`tests/unit/typeset/test_latex.py::test_a_wrong_piece_in_the_tex_is_caught_by_the_gate`
runs the critic's own sabotage, for each of the six pieces, and requires a non-zero exit.

What is normalised, and why
---------------------------
* **The board.** A line whose only non-piece tokens are rank digits and file letters is a
  row of a diagram, and diagrams are compared as diagrams. On the SVG side a board is
  vector paths and leaves no text; on the LaTeX side it is a row of chess-font glyphs.
* **The ellipsis.** T1 has no ellipsis glyph. `\\caissadots` sets three tight periods,
  which is what a reader sees on both sides, but the text layer says `...` where the SVG
  says U+2026. It is the one declared divergence; it is counted and printed, never hidden,
  and the space after it is measured on both sides.
* **Line breaks.** The two measures differ, so tokens are compared as a stream and a word
  broken at a line end is rejoined.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import pymupdf  # noqa: E402

CHESS_FONT_HINTS = ("chess", "skaknew", "merida", "alpha", "diagram")

ELLIPSIS = "…"


def _is_chess(font: str) -> bool:
    name = font.lower()
    return any(hint in name for hint in CHESS_FONT_HINTS)


def _board_boxes(page) -> list[tuple[float, float, float, float]]:  # noqa: ANN001
    """Bounding boxes of the diagrams, widened to take in their coordinate labels.

    Everything inside one is board furniture: the rank digits and file letters are set by
    the diagram, not by the text, and the two exporters neither place them in the same
    reading order nor in the same font. They are compared as *diagrams*, not as prose.
    """
    out = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.width > 60 and rect.height > 60 and abs(rect.width - rect.height) < 24:
            out.append((rect.x0 - 16, rect.y0 - 16, rect.x1 + 16, rect.y1 + 16))
    return out


def _inside(bbox, box) -> bool:  # noqa: ANN001
    x0, y0, x1, y1 = bbox
    bx0, by0, bx1, by1 = box
    return x0 >= bx0 - 2 and x1 <= bx1 + 2 and y0 >= by0 - 2 and y1 <= by1 + 2


def _is_furniture(line) -> bool:  # noqa: ANN001
    """True for a line that is a diagram's own rank and file labels, and nothing else.

    Board furniture is compared as part of the *diagram*: the two exporters set it in
    different fonts (Times here, a sans there), and on the LaTeX side the board is a row
    of glyphs of the chess font rather than a drawing, so a geometric test has nothing to
    test against. What both sides do share is that a row of labels is a line of
    one-character tokens and a line of prose is not.
    """
    pieces: list[str] = []
    for span in line["spans"]:
        if _is_chess(span["font"]):
            continue
        pieces.extend(span["text"].split())
    if not pieces:
        return True
    return all(len(p) == 1 and p in "abcdefgh12345678" for p in pieces)


def _vector_boxes(page) -> list[tuple[float, float, float, float]]:  # noqa: ANN001
    """Every drawn path on the page, as a box. A figurine is one of them."""
    return [tuple(drawing["rect"]) for drawing in page.get_drawings()]


def _is_piece_span(span, vectors) -> bool:  # noqa: ANN001
    """True when this span **is** a piece glyph, on either exporter.

    LaTeX sets the piece as a glyph of the chess family, so the font name says so. The
    SVG side draws it as a vector path and sets the letter invisibly underneath, so the
    test is positional and is a check in its own right: the letter only counts as a piece
    if it really sits on the drawing it names. A rank digit or a file letter cannot pass
    it -- coordinates are `a`-`h` and `1`-`8`, never `K`, `Q`, `R`, `B` or `N`.
    """
    text = span["text"].strip()
    if not text:
        return False          # a kerning space set in the chess family is not a piece
    if _is_chess(span["font"]):
        return True
    if len(text) != 1 or text not in "KQRBN":
        return False
    x0, y0, x1, y1 = span["bbox"]
    width = max(x1 - x0, 1e-6)
    for vx0, vy0, vx1, vy1 in vectors:
        overlap = min(x1, vx1) - max(x0, vx0)
        if overlap > 0.5 * width and vy0 < y1 and vy1 > y0:
            return True
    return False


def piece_runs(page) -> list[str]:  # noqa: ANN001
    """The page's piece glyphs, in reading order. The heart of the parity gate.

    Not the token strings: the *pieces*. `Run.kind == "piece"` on one side and
    `\\cfig{...}` on the other are the same list by construction, and this reads it back
    out of each finished PDF.
    """
    out: list[str] = []
    for line in ordered_lines(page):
        if _is_furniture(line):
            continue
        vectors = _vector_boxes(page)
        for span in line["spans"]:
            if _is_piece_span(span, vectors):
                # One entry per glyph: pdfTeX may set two neighbouring figurines in one
                # span, and a list that counts them as one would let a swap hide inside.
                out.extend(span["text"].strip())
    return out


def head_baseline(page) -> float:  # noqa: ANN001
    """Top of the running-head line. Everything above the text block sits on it."""
    tops = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if "".join(s["text"] for s in line["spans"]).strip():
                tops.append(line["bbox"][1])
    return min(tops) if tops else 0.0


def ordered_lines(page, *, skip_head: bool = True):  # noqa: ANN001, ANN201
    """The page's text lines in READING order: column, then baseline, then x.

    Imposed rather than inherited. PyMuPDF returns blocks in content order, and two
    multi-column engines do not lay their content stream down in the same order; without
    this the same paragraph turns up at two different places in the two token streams and
    every token after it counts as a divergence.
    """
    head = head_baseline(page) if skip_head else -1e9
    mid = page.rect.width / 2.0
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if abs(line["bbox"][1] - head) < 2.0 or not line["spans"]:
                continue
            x0 = min(s["bbox"][0] for s in line["spans"])
            out.append((0 if x0 < mid else 1, round(line["bbox"][1]), x0, line))
    return [line for *_, line in sorted(out, key=lambda item: item[:3])]


def spans(page, *, skip_head: bool = True) -> list[tuple[str, bool, bool]]:  # noqa: ANN001
    """``(text, bold, is_piece)`` for every span of the page, in reading order.

    The running-head line is skipped by default and compared on its own: it carries the
    folio, which is 44 on the SVG page and 1 on the LaTeX one, and a page number is not
    a divergence of typography.
    """
    vectors = _vector_boxes(page)
    out: list[tuple[str, bool, bool]] = []
    for line in ordered_lines(page, skip_head=skip_head):
        if _is_furniture(line):
            continue
        for span in line["spans"]:
            out.append((span["text"], "bold" in span["font"].lower(),
                        _is_piece_span(span, vectors)))
        out.append(("\n", False, False))
    return out


def page_text(page) -> str:  # noqa: ANN001
    return "".join(text for text, _, _ in spans(page))


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ").replace(" ", " ")
    text = re.sub(r"[-­]\s*\n\s*", "", text)   # rejoin a word broken at a line end
    text = text.replace(ELLIPSIS, "...")
    # The one declared divergence carries a tokenisation difference with it: pdfTeX
    # emits `\caissadots` as three periods and the extractor puts a space after the
    # third, where the SVG's single U+2026 glyph has none. `13...bxc5` is one token in
    # chess notation on both sides, so the space beside the ellipsis is removed on both.
    text = re.sub(r"\s*\.\.\.\s*", "...", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokens(text: str) -> list[str]:
    return [t for t in normalise(text).split(" ") if t]


def bold_tokens(page) -> list[str]:  # noqa: ANN001
    """Every token that comes out BOLD, in order. The structure, not the string.

    Piece glyphs are left out of *this* comparison and compared by `piece_runs` instead,
    and the reason is declared rather than convenient: the legacy chess families are cut
    in one series, so `\\cfig` forces `\\mdseries` and a LaTeX figurine inside a bold
    move line is not a bold span. The SVG side bolds its figurine by outsetting the
    drawing (`figurine.FIGURINE_INK_GAIN_BOLD`), which is measured at 1200 DPI by
    `measure_typography.py figset` and cannot be seen in a font name at all. What is
    compared here is which *words* come out bold; what is compared in `piece_runs` is
    which piece each figurine is.
    """
    runs = [text for text, bold, piece in spans(page) if bold and not piece]
    return tokens(" ".join(runs))


def _is_italic(font: str) -> bool:
    name = font.lower()
    return "italic" in name or "slant" in name or "oblique" in name


def italic_tokens(page) -> list[str]:  # noqa: ANN001
    """Every token that comes out ITALIC, in order.

    The second half of "span by span". Bold separates a move line from prose; italic
    separates a caption and a player's name from both, and the two exporters reach it by
    different routes -- ``TimesNewRomanPS-ItalicMT`` on one side, ``LMRoman9-Italic`` on
    the other -- from the same ``Run.face``. Comparing only bold left half the structure
    unchecked.
    """
    runs: list[str] = []
    vectors = _vector_boxes(page)
    for line in ordered_lines(page):
        if _is_furniture(line):
            continue
        for span in line["spans"]:
            if _is_piece_span(span, vectors):
                continue
            if _is_italic(span["font"]):
                runs.append(span["text"])
    return tokens(" ".join(runs))


def _lines(page) -> list[tuple[str, bool]]:  # noqa: ANN001
    """``(line text, the whole line is italic)`` in reading order.

    Both exporters set a diagram caption in italic; the flag is what tells a caption from
    a sentence of prose that happens to open with the same word.
    """
    out: list[tuple[str, bool]] = []
    vectors = _vector_boxes(page)
    for line in ordered_lines(page):
        if _is_furniture(line):
            continue
        body = []
        italic = True
        for span in line["spans"]:
            body.append(span["text"])
            if span["text"].strip() and not _is_piece_span(span, vectors):
                name = span["font"].lower()
                italic = italic and ("italic" in name or "slant" in name
                                     or "oblique" in name)
        out.append(("".join(body), italic))
    return out


def caption_lines(page) -> list[str]:  # noqa: ANN001
    """The diagram captions, gathered line by line rather than by a regex on the page.

    A caption may wrap, and a regex over the flattened page either stops at the first
    period of `After 14.Nb3` or runs on into the paragraph after it. The lines are
    already in reading order, so a caption is the run of lines that opens with `After`
    and closes at the first one ending in a full stop.
    """
    out: list[str] = []
    current: list[str] = []
    for raw, italic in _lines(page):
        line = raw.strip()
        if not line:
            continue
        if current:
            current.append(line)
        elif italic and line.startswith("After"):
            current = [line]
        else:
            continue
        if current[-1].endswith("."):
            out.append(normalise(" ".join(current)))
            current = []
    if current:
        out.append(normalise(" ".join(current)))
    return out


def running_head(page) -> str:  # noqa: ANN001
    """The running head, without its folio.

    Everything on the topmost line, in x order, minus the page number: the SVG page is
    folioed 44 and the LaTeX one 1, and a page number is not a divergence of typography.
    """
    head = head_baseline(page)
    pieces = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            if abs(line["bbox"][1] - head) > 2.0:
                continue
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                pieces.append((line["bbox"][0], text))
    joined = " ".join(text for _, text in sorted(pieces))
    return re.sub(r"(^\s*\d+\s+|\s+\d+\s*$)", "", joined).strip()


def ellipsis_space(page) -> float:  # noqa: ANN001
    """Gap after the ellipsis of the running head, in points.

    The critic's measurement: 5.12 pt on the LaTeX side against 0.00 pt on the SVG side,
    while the report called the two "visually identical".
    """
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            for span in line["spans"]:
                for char in span["chars"]:
                    chars.append((line["bbox"][1], char["bbox"][0], char["bbox"][2],
                                  char["c"]))
    if not chars:
        return 0.0
    top = min(c[0] for c in chars)
    head = sorted((c for c in chars if abs(c[0] - top) < 2.0), key=lambda c: c[1])
    for index, (_, x0, x1, char) in enumerate(head):
        if char in (ELLIPSIS, ".") and index + 1 < len(head):
            following = head[index + 1]
            if following[3] in (".", ELLIPSIS):
                continue
            return following[1] - x1
    return 0.0


_CFIG = re.compile(r"\\cfig\{([a-z]+)\}")

_CFIG_LETTER = {"king": "K", "queen": "Q", "rook": "R", "bishop": "B",
                "knight": "N", "pawn": "P"}


def tex_source_pieces(tex_path: Path) -> list[str] | None:
    """The pieces the generated ``.tex`` asks for, in order, as letters.

    The critique's own wording: *"do lado LaTeX a partir do argumento de `\cfig{...}` no
    `.tex` gerado, do lado SVG a partir do `Run.kind == 'piece'` da lista de corridas"*.
    Reading the source as well as the compiled page catches a swap before it is compiled,
    and it is the check that does not depend on any font, encoding or CMap being right.
    Returns None when the source is not beside the PDF.
    """
    if not tex_path.exists():
        return None
    body = tex_path.read_text(encoding="utf-8")
    return [_CFIG_LETTER.get(name, name) for name in _CFIG.findall(body)]


def svg_source_pieces() -> list[str]:
    """The pieces the SVG page is set from, in order: ``Run.kind == "piece"``.

    Straight from the composer's own run list, through the same
    ``prepared`` + ``parse_markup`` pass both exporters use.
    """
    import typeset_page as tp
    import typeset_proofsheet as ps

    out: list[str] = []
    for item in ps.book_source_mareco():
        text = item.get("text") or item.get("caption") or ""
        if not text:
            continue
        for run in tp.parse_markup(tp.prepared(text, "en")):
            if run.kind == "piece":
                out.append(run.content.upper())
    return out


def _diff(name: str, left: list[str], right: list[str]) -> int:
    bad = 0
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else "<falta>"
        b = right[index] if index < len(right) else "<falta>"
        if a != b:
            bad += 1
            print(f"    divergencia {name}: {index}  SVG {a!r}  vs  LaTeX {b!r}")
    if not bad:
        print(f"    {len(left)} {name}, identicos.")
    return bad


def compare(svg_pdf: Path, svg_page: int, tex_pdf: Path, tex_page: int) -> int:
    svg_doc = pymupdf.open(svg_pdf)
    tex_doc = pymupdf.open(tex_pdf)
    svg, tex = svg_doc[svg_page], tex_doc[tex_page]

    svg_text = page_text(svg)
    tex_text = page_text(tex)

    bad = 0
    print("--- pagina inteira, token a token (reticencia normalizada nos dois lados)")
    bad += _diff("tokens", tokens(svg_text), tokens(tex_text))

    print("--- identidade das pecas, glifo a glifo, nas duas paginas")
    left_pieces, right_pieces = piece_runs(svg), piece_runs(tex)
    print(f"    SVG {len(left_pieces)} figurinos, LaTeX {len(right_pieces)}")
    bad += _diff("peca", left_pieces, right_pieces)

    tex_source = tex_source_pieces(tex_pdf.with_suffix(".tex"))
    if tex_source is not None:
        print("--- identidade das pecas na fonte: \cfig{...} contra a lista de corridas")
        bad += _diff("peca (fonte)", svg_source_pieces(), tex_source)
    else:
        print(f"--- identidade das pecas na fonte: {tex_pdf.with_suffix('.tex')} ausente, "
              "comparacao NAO feita")

    print("--- legendas dos diagramas")
    bad += _diff("legendas", caption_lines(svg), caption_lines(tex))

    print("--- cabeca corrente")
    left, right = normalise(running_head(svg)), normalise(running_head(tex))
    same = left == right
    bad += 0 if same else 1
    print(f"    SVG   {left!r}\n    LaTeX {right!r}   "
          f"{'iguais' if same else '*** DIVERGEM'}")

    print("--- estrutura: quais corridas saem em negrito")
    left_bold = bold_tokens(svg)
    right_bold = bold_tokens(tex)
    print(f"    SVG {len(left_bold)} tokens em negrito, LaTeX {len(right_bold)}")
    bad += _diff("negrito", left_bold, right_bold)

    print("--- estrutura: quais corridas saem em italico")
    left_italic = italic_tokens(svg)
    right_italic = italic_tokens(tex)
    print(f"    SVG {len(left_italic)} tokens em italico, LaTeX {len(right_italic)}")
    bad += _diff("italico", left_italic, right_italic)

    print("--- a divergencia declarada: a reticencia")
    svg_raw = re.sub(r"\s+", " ", svg_text)
    tex_raw = re.sub(r"\s+", " ", tex_text)
    svg_glyph = ELLIPSIS if ELLIPSIS in svg_raw else ("..." if "..." in svg_raw else "-")
    tex_glyph = ELLIPSIS if ELLIPSIS in tex_raw else ("..." if "..." in tex_raw else "-")
    declared = 1 if svg_glyph != tex_glyph else 0
    svg_gap, tex_gap = ellipsis_space(svg), ellipsis_space(tex)
    print(f"    glifo   SVG {svg_glyph!r}   LaTeX {tex_glyph!r}   "
          f"{'DIVERGENCIA DECLARADA' if declared else 'iguais'}")
    print(f"    espaco depois dela   SVG {svg_gap:.2f} pt   LaTeX {tex_gap:.2f} pt   "
          f"{'ok' if abs(svg_gap - tex_gap) < 0.5 else '*** DIVERGEM'}")
    if abs(svg_gap - tex_gap) >= 0.5:
        bad += 1

    svg_doc.close()
    tex_doc.close()
    print(f"\nTOTAL: {bad} divergencia(s) nao declarada(s) + {declared} declarada "
          f"(a reticencia). Ciclo 2 media 1 e o critico mediu 5.")
    return bad


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", default=str(ROOT / "benchmarks/reports/proofsheet.pdf"))
    parser.add_argument("--svg-page", type=int, default=0,
                        help="1-based page of the SVG export holding the book page; "
                             "0 means the third page from the end, which is where the "
                             "proof sheet's first book page is however many specimen "
                             "pages precede it")
    parser.add_argument("--tex", default=str(ROOT / "benchmarks/reports/latex/livro.pdf"))
    parser.add_argument("--tex-page", type=int, default=1)
    args = parser.parse_args(argv)
    svg_index = args.svg_page - 1
    if args.svg_page == 0:
        doc = pymupdf.open(args.svg)
        svg_index = doc.page_count - 3
        doc.close()
    return compare(Path(args.svg), svg_index, Path(args.tex), args.tex_page - 1)


if __name__ == "__main__":
    raise SystemExit(main())
