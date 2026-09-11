"""LaTeX export: structure, and a real compile when a TeX engine is installed.

Every structural assertion here corresponds to a way the first generated document failed
to compile on this machine. They are regression tests in the strict sense: each one was
written after pdfTeX rejected the output, not in anticipation of it.

The compile test is skipped -- loudly, with the reason -- when no engine is present. It
is never replaced by a structural check pretending to be a compile.
"""

from __future__ import annotations

import shutil

import pytest

from caissa.typeset import latex
from caissa.typeset.board_svg import Arrow, CircleMark, SquareHighlight
from caissa.typeset.latex import (
    CHESSFSS_FAMILIES,
    LatexDocument,
    LatexOptions,
    chessboard_command,
    compile_document,
    diagram_block,
    escape_latex,
    figurine_move,
    mainline,
    makefile,
    newgame,
    preamble,
    tex_available,
)

FEN = "r2q1rk1/pb1n1ppp/1p6/2Pp4/8/6P1/PP1NPPBP/2RQ1RK1 b - - 0 13"
FEN_W = "4rnk1/pbr2ppB/1pq1p3/4P1BQ/2P5/P5R1/5PPP/R5K1 b - - 0 21"


# --------------------------------------------------------------------------- #
# Escaping
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "expect"),
    [
        ("50%", r"50\%"),
        ("a&b", r"a\&b"),
        ("$5", r"\$5"),
        ("a_b", r"a\_b"),
        ("#1", r"\#1"),
        ("{x}", r"\{x\}"),
    ],
)
def test_special_characters_are_escaped(raw, expect):
    assert escape_latex(raw) == expect


def test_backslash_does_not_escape_into_a_new_command():
    out = escape_latex(r"a\b")
    assert "textbackslash" in out
    assert out.count("\\b") == 0 or "textbackslash" in out


# --------------------------------------------------------------------------- #
# The FEN must be braced
# --------------------------------------------------------------------------- #
def test_setfen_is_braced():
    """`chessboard` parses its options with keyval, where a comma ends a value. A FEN
    carries spaces and hyphens, and unbraced it makes the parser run past the end of the
    option list -- pdfTeX reports `Paragraph ended before \\FenBoard was complete` and
    produces nothing. Observed, then fixed."""
    out = chessboard_command(FEN)
    assert f"setfen={{{FEN}}}" in out


def test_newgame_braces_the_fen_too():
    assert f"setfen={{{FEN}}}" in newgame(FEN)


def test_newgame_sets_the_move_counter_from_the_fen():
    """xskak starts a `setfen` game at move 1 whatever the FEN says, so a following
    `\\mainline{13...bxc5}` is refused with `mainline: 13 is not the correct move
    number`. The counter comes from the FEN's own fullmove field."""
    assert "moveid=13b" in newgame(FEN)
    assert "moveid=21b" in newgame(FEN_W)
    assert "moveid=1w" in newgame(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )


def test_newgame_without_a_fen_is_the_bare_command():
    assert newgame() == "\\newchessgame"


def test_newgame_accepts_an_explicit_moveid():
    assert "moveid=40w" in newgame(FEN, moveid="40w")


# --------------------------------------------------------------------------- #
# Diagrams
# --------------------------------------------------------------------------- #
def test_diagram_is_markup_not_an_image():
    """SPEC §8.5: the position must be editable text. An `\\includegraphics` here would
    make the export a PDF with extra steps."""
    out = diagram_block(FEN)
    assert "\\chessboard[" in out
    assert "includegraphics" not in out
    assert FEN in out


def test_diagram_block_is_balanced():
    out = diagram_block(FEN, caption="After 13.dxc5.")
    assert out.count("\\begin{diagrama}") == 1
    assert out.count("\\end{diagrama}") == 1
    assert out.count("[") == out.count("]")
    assert out.count("{") == out.count("}")


def test_caption_is_escaped():
    out = diagram_block(FEN, caption="100% winning & clear")
    assert r"\%" in out and r"\&" in out


def test_highlights_are_a_tint_not_a_solid_fill():
    """`pgfstyle=color` with no colour named fills the square solid black and the piece
    standing on it disappears. Observed on the first compiled proof."""
    out = chessboard_command(FEN, marks=[SquareHighlight("c5")])
    assert "backfields={c5}" in out
    assert "color=" in out
    assert "black!" in out, "o destaque precisa ser um tom, nao preto solido"


def test_arrows_carry_a_head():
    """The named `straightmove` style alone draws a headless bar the width of a square:
    it reads as a blacked-out file, not as a move."""
    out = chessboard_command(FEN, marks=[Arrow("g3", "g7")])
    assert "backmoves={g3-g7}" in out, "a haste vai na camada de fundo"
    assert "Stealth" in out, "a seta precisa de uma ponta"
    assert "line width" in out


def test_the_arrow_shaft_goes_under_the_pieces_and_only_the_head_on_top():
    """Q1 of the cycle-3 critique, on the LaTeX side.

    `chessboard` draws its `back*` pgf picture before the board and its `mark*` picture
    after, so the whole arrow goes in `backmoves` and only the last leg -- shortened to
    its head -- comes back in `markmoves`. Cycle 2 drew everything in the mark layer with
    a white rule under it, and on a board of white outline pieces that keyline erased the
    outlines: the critic measured the b2 and f2 pawns coming apart.
    """
    out = chessboard_command(FEN, marks=[Arrow("g3", "g7")])
    assert "backstyle=" in out and "backmoves={g3-g7}" in out
    assert "markmoves={g6-g7}" in out, "so a ultima etapa leva a ponta por cima"
    assert "draw=white" in out, "a ponta leva um contorno na cor da casa"
    assert "shorten <=" in out, "o resto da etapa fica escondido: so a ponta aparece"
    assert "-,line width=3.4pt,draw=white" not in out, (
        "o recorte branco do ciclo 2 nao pode voltar"
    )


def test_a_knight_move_uses_the_knight_style():
    out = chessboard_command(FEN, marks=[Arrow("d2", "b3")])
    assert "knightmove" in out


def test_a_straight_move_does_not_use_the_knight_style():
    out = chessboard_command(FEN, marks=[Arrow("d1", "d7")])
    assert "straightmove" in out
    assert "knightmove" not in out


def test_mark_kinds_are_grouped_not_interleaved():
    """`chessboard` applies one `pgfstyle` at a time and consumes the fields listed after
    it. Interleaving silently drops all but the last group."""
    out = chessboard_command(
        FEN, marks=[SquareHighlight("c5"), CircleMark("d5"), Arrow("g3", "g7")]
    )
    assert "backfields={c5}" in out
    assert "markfields={d5}" in out
    assert "backmoves={g3-g7}" in out


def test_circle_marks_use_markfields():
    out = chessboard_command(FEN, marks=[CircleMark("e4")])
    assert "pgfstyle=circle" in out
    assert "markfields={e4}" in out


# --------------------------------------------------------------------------- #
# Figurines
# --------------------------------------------------------------------------- #
def test_figurine_macro_is_braced():
    """`\\symknight` followed directly by `xc5` is read by TeX as a control sequence
    named `symknightxc5`. The literal string `\\symknightxc5` was what appeared on the
    first compiled page."""
    out = figurine_move("Nxc5")
    assert "{\\symknight}" in out
    assert out.endswith("xc5")


def test_figurine_move_covers_every_piece():
    for san, macro in (
        ("Kd2", "symking"), ("Qd2", "symqueen"), ("Rd2", "symrook"),
        ("Bd2", "symbishop"), ("Nd2", "symknight"),
    ):
        assert f"{{\\{macro}}}" in figurine_move(san)


def test_a_pawn_move_has_no_figurine():
    assert "sym" not in figurine_move("e4")


def test_castling_is_not_figurined():
    assert "sym" not in figurine_move("O-O")
    assert "O-O" in figurine_move("O-O")


def test_promotion_figurines_the_new_piece():
    out = figurine_move("e8=Q")
    assert "{\\symqueen}" in out


def test_unparseable_move_is_escaped_not_emitted_raw():
    assert escape_latex("50%") in figurine_move("50%")


# --------------------------------------------------------------------------- #
# Preamble
# --------------------------------------------------------------------------- #
def test_preamble_loads_the_packages_in_a_working_order():
    """`xskak` configures `chessboard`, so it comes after it; the other order leaves
    `\\mainline` without a board."""
    out = preamble()
    board = out.index("{chessboard}")
    xskak = out.index("{xskak}")
    assert board < xskak


def test_preamble_sets_widow_and_orphan_penalties():
    """TeX's defaults tolerate both. A book does not, and the charter fails them."""
    out = preamble()
    assert "\\widowpenalty=10000" in out
    assert "\\clubpenalty=10000" in out


def test_preamble_omits_the_font_family_when_none_is_asked_for():
    """A named family whose Type1 font is not installed stops pdfTeX dead. `None` means
    'leave chessfss on its default', which is always present."""
    out = preamble(LatexOptions(font_family=None))
    assert "\\setchessfontfamily" not in out


def test_preamble_sets_the_family_when_one_is_asked_for():
    out = preamble(LatexOptions(font_family="alpha"))
    assert "\\setchessfontfamily{alpha}" in out


def test_every_registered_family_maps_to_a_chessfss_name():
    for key, name in CHESSFSS_FAMILIES.items():
        assert name and name.isascii(), key


def test_preamble_declares_the_geometry_it_was_given():
    out = preamble(LatexOptions(geometry="paperwidth=160.9mm,paperheight=228.6mm"))
    assert "160.9mm" in out


def test_makefile_names_the_engine():
    out = makefile("livro.tex", engine="xelatex")
    assert "xelatex" in out
    assert "livro" in out


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #
def test_document_renders_a_complete_source():
    doc = LatexDocument(options=LatexOptions(font_family=None))
    doc.add(newgame())
    doc.add(mainline("1.d4 Nf6 2.c4"))
    doc.add_diagram(FEN, caption="After 13.dxc5.")
    out = doc.render()
    assert out.startswith("\\documentclass")
    assert "\\begin{document}" in out
    assert out.rstrip().endswith("\\end{document}")
    assert out.index("\\begin{document}") < out.index("\\chessboard")


def test_add_text_escapes_and_add_does_not():
    """`add_text` is for prose and `add` for markup. Passing a figurine through
    `add_text` prints the macro name on the page -- which is what happened."""
    doc = LatexDocument(options=LatexOptions(font_family=None))
    doc.add_text("100% sure")
    doc.add(figurine_move("Nxc5"))
    out = doc.render()
    assert r"100\% sure" in out
    assert "{\\symknight}xc5" in out


def test_document_write_round_trips(tmp_path):
    doc = LatexDocument(options=LatexOptions(font_family=None))
    doc.add_diagram(FEN)
    path = doc.write(tmp_path / "livro.tex")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == doc.render()


# --------------------------------------------------------------------------- #
# Font family availability
# --------------------------------------------------------------------------- #
def test_family_availability_is_checked_not_assumed():
    """A chessfss family name is not a font. `chess-merida` is absent from this
    machine's MiKTeX, and asking for it stops pdfTeX with
    `cannot open chess-merida-board-fig-raw.pfb`."""
    if shutil.which("kpsewhich") is None:
        pytest.skip("kpsewhich nao esta no PATH; nao ha como consultar a arvore TeX.")
    assert latex.chessfss_family_available("definitely-not-a-family") is False
    picked = latex.first_available_family(["definitely-not-a-family", "alpha", "berlin"])
    assert picked in {None, "alpha", "berlin"}


def test_first_available_family_returns_none_when_nothing_matches():
    if shutil.which("kpsewhich") is None:
        pytest.skip("kpsewhich nao esta no PATH.")
    assert latex.first_available_family(["nope-a", "nope-b"]) is None


# --------------------------------------------------------------------------- #
# The real compile
# --------------------------------------------------------------------------- #
def test_tex_available_reports_honestly():
    found = tex_available("pdflatex")
    assert found is None or shutil.which("pdflatex") is not None


def test_compile_reports_the_absence_of_an_engine_clearly():
    result = compile_document("\\documentclass{article}", engine="definitely-not-a-tex")
    assert result.ok is False
    assert result.engine is None
    assert "TeX" in result.reason or "tex" in result.reason.lower()


@pytest.mark.slow
def test_generated_document_actually_compiles(tmp_path):
    """The one that matters. Skipped with a reason when no engine is installed --
    never quietly replaced by a structural check."""
    engine = tex_available("pdflatex")
    if engine is None:
        pytest.skip(
            "Nenhum motor TeX no PATH (procurado: pdflatex). A saida LaTeX fica "
            "NAO VERIFICADA neste ambiente. Instale MiKTeX ou TeX Live."
        )

    family = latex.first_available_family(["alpha", "berlin", "merida", "skaknew"])
    options = LatexOptions(
        language="en",
        font_family=family,
        document_class="article",
        class_options="10pt",
        geometry="a5paper,margin=15mm",
    )
    doc = LatexDocument(options=options)
    doc.add(newgame())
    doc.add(mainline("1.d4 Nf6 2.c4 e6 3.g3"))
    doc.add_diagram(FEN, caption="After 13.dxc5.")
    doc.add(newgame(FEN))
    doc.add(mainline("13...bxc5 14.Nb3"))
    doc.add_diagram(
        FEN_W,
        marks=[SquareHighlight("h7"), Arrow("g3", "g7"), CircleMark("g8")],
        caption="Marks: highlight, arrow, circle.",
    )
    doc.add(figurine_move("Nxc5"))

    result = compile_document(
        doc.render(), engine="pdflatex", workdir=tmp_path, runs=2, timeout=300
    )
    assert result.ok, f"a compilacao falhou: {result.reason}\n{result.log[-2000:]}"
    assert result.pdf is not None and result.pdf.exists()
    assert result.pdf.stat().st_size > 1000

    import pymupdf

    with pymupdf.open(result.pdf) as pdf:
        assert pdf.page_count >= 1
        text = pdf[0].get_text()
    # The macro name must not have leaked onto the page as literal text.
    assert "symknight" not in text
    assert "chessboard" not in text
