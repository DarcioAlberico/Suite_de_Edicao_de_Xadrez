"""LaTeX output: diagrams as editable markup, notation as figurines.

SPEC §8.5. The requirement that shapes this module is one word: **editable**. A LaTeX
export whose diagrams are included images is a PDF with extra steps -- the author cannot
move a piece, cannot flip the board, cannot restyle the set. So every diagram leaves here
as ``\\chessboard[setfen=...]``: a position an author can edit in a text editor and
recompile, exactly as they would have typed it themselves.

The packages
------------
``chessboard`` draws the board and takes the position as a FEN. ``xskak`` tracks a game
and gives ``\\mainline`` / ``\\variation``, which typeset moves as figurines and keep the
board in step. ``chessfss`` is the font-selection layer both sit on, and it is what makes
``\\setchessfontfamily`` work -- the reason a whole book can change piece set with one
line, which is the same promise ``fonts.py`` makes on our side.

Honesty about compilation
-------------------------
:func:`compile_document` runs a real TeX and returns what happened. It never reports
success it did not observe, and when no TeX is installed it says so rather than pretending
the output is fine. See ``docs/quality/F7_REPORT.md`` for the result on this machine.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

from .board_svg import Arrow, CircleMark, DiagramStyle, FrameStyle, Mark, SquareHighlight
from .figurine import language_letter, parse_san

__all__ = [
    "CompileResult",
    "LatexDocument",
    "LatexOptions",
    "chessboard_command",
    "compile_document",
    "retag_figurine_text",
    "escape_latex",
    "typographic_tex",
    "diagram_block",
    "figurine_move",
    "mainline",
    "moveline",
    "played",
    "typeset_move",
    "typeset_moves",
    "figurine_symbol",
    "newgame",
    "variation",
    "makefile",
    "preamble",
    "tex_available",
    "chessfss_family_available",
    "first_available_family",
]


# ``chessfss`` font family names, as the package knows them. Keyed by our own family key
# so a document can be exported in the same piece set the screen showed.
CHESSFSS_FAMILIES: dict[str, str] = {
    "merida": "merida",
    "alpha": "alpha",
    "cases": "cases",
    "berlin": "berlin",
    "leipzig": "leipzig",
    "marroquin": "marroquin",
    "condal": "condal",
    "lucena": "lucena",
    "maya": "maya",
    "utrecht": "utrecht",
    "adventurer": "adventurer",
    "harlequin": "harlequin",
    "kingdom": "kingdom",
    "line": "line",
    "magnetic": "magnetic",
    "mediaeval": "mediaeval",
    "motif": "motif",
    "skaknew": "skaknew",
    "unicode": "skaknew",
}

# Mark appearance. A highlight is a tint the piece still reads through, and an arrow
# is a rule with a head, not a filled bar. Both are `xcolor`/`pgf` expressions passed
# straight to `chessboard`.
HIGHLIGHT_TINT = "black!18"

ARROW_COLOUR = "black!62"
"""Grey of the mark. Chosen for one measurement: contrast against the piece it lands on.

`black!62` is RGB(97,97,97) on white paper -- **3.39:1** against a black piece, where
cycle 2's `black!75` measured 1.99:1 and failed WCAG 1.4.11 and our own 3:1 rule at the
same time. It is the same value the SVG side uses (`board_svg.BoardTheme.arrow`), so the
two exporters mark a board in one ink."""

ARROW_SHAFT_PGF = "[-,line width=1.2pt]"
"""The shaft, drawn in the **background** layer -- under the pieces.

This replaces cycle 2's white knockout, and the reason is the same as on the SVG side
(`board_svg.MARK_PAINT_ORDER`): our pieces are white outlines, and a white keyline drawn
over a white outline erases it. `chessboard` draws its `back*` pgf picture before the
board and its `mark*` picture after, so `backmoves` puts the whole arrow beneath the
position and nothing is cut."""

ARROW_HEAD_PGF = (
    "[-{{Stealth[length=5pt,width=5pt]}},line width={width}pt,"
    "{colour}shorten <={back}pt,shorten >={front}pt]"
)
"""Only the head, drawn again on top, on the last leg of the move.

Emitted twice: once as a wider white rule -- the keyline the SVG side draws in the
destination square's colour -- and once in `ARROW_COLOUR`. `shorten <=` hides all of the
last leg but its tip, so what lands on the piece is an arrowhead and not a bar; the
critic measured cycle 2's head covering the whole base of the c5 pawn."""

ARROW_HEAD_BACK_PT = 12.0
"""How much of the final leg is hidden, in points, so only the head shows on top."""

ARROW_HEAD_FRONT_PT = 4.5
"""How far short of the destination square's centre the tip stops.

The SVG side stops at 0.30 of a square (`board_svg.MARK_HEAD_LANDING`) so the head sits
on the *edge* of the piece and leaves its ink readable; this is the same landing in
points at the board size this document sets."""

BABEL_LANGUAGES: dict[str, str] = {
    "pt": "brazilian",
    "en": "british",
    "en_us": "american",
    "de": "ngerman",
    "es": "spanish",
    "fr": "french",
    "it": "italian",
    "ru": "russian",
}

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    """Escape the ten characters TeX treats specially."""
    return "".join(_LATEX_SPECIALS.get(char, char) for char in text)


# What `typography.prepared` puts on the page, and the LaTeX that sets the same
# character. Each is wrapped in braces so it cannot swallow the space after it: cycle 2
# wrote `\caissadots{}` in the running head and pdfTeX set 5.12 pt of space after the
# ellipsis where the SVG set 0.00, which the critic measured and counted as a divergence
# between the two exporters.
#
# `\input{glyphtounicode}` in the preamble is what makes these come *back out* of the PDF
# as the characters they are: without it TS1's minus extracts as a hyphen. Verified by
# extracting the compiled page, not assumed.
_TYPOGRAPHIC_TEX = {
    "–": "--",                    # EN DASH
    "—": "---",                   # EM DASH
    "−": "{\\textminus}",         # MINUS SIGN
    "…": "{\\caissadots}",        # HORIZONTAL ELLIPSIS
    "†": "{\\textdagger}",        # check
    "‡": "{\\textdaggerdbl}",     # mate
    "±": "{\\textpm}",            # White is slightly better
    "½": "{\\textonehalf}",
    " ": "~",                     # no-break space
    " ": "\\,",                   # thin space
    " ": "\\,",                   # narrow no-break space
}


def typographic_tex(text: str) -> str:
    """One run of prepared text as LaTeX, typographic characters and all.

    The input is what the SVG path sets -- the output of ``typography.prepared`` -- so the
    two exporters start from the *same string* and can be compared token by token. Cycle 2
    ran the two paths from two different sources and then compared two move passages;
    the critic found five divergences outside what the comparison looked at.
    """
    out: list[str] = []
    for char in text:
        replacement = _TYPOGRAPHIC_TEX.get(char)
        out.append(replacement if replacement is not None
                   else _LATEX_SPECIALS.get(char, char))
    return "".join(out)


@dataclass(frozen=True)
class LatexOptions:
    """Document-level choices for a LaTeX export."""

    language: str = "pt"
    font_family: str | None = "merida"
    """A key of ``CHESSFSS_FAMILIES``, or None to leave chessfss on its own default.

    The named family must have its Type1 font installed in the TeX tree, which is a
    *separate* package from ``chessfss`` -- ask `chessfss_family_available` before
    committing to one. On the reference machine's MiKTeX only ``alpha`` and ``berlin``
    are present; ``merida`` is not, and asking for it stops pdfTeX dead with
    ``cannot open chess-merida-board-fig-raw.pfb``."""

    board_font_size: str = "20pt"
    """``chessboard``'s unit of board size: the square is one em of the board font, so
    the board is eight times this. 20 pt gives a board about 56 mm wide."""

    document_class: str = "book"
    class_options: str = "11pt,a5paper,twoside"
    geometry: str = "a5paper,inner=20mm,outer=15mm,top=18mm,bottom=20mm"
    show_mover: bool = True
    coordinates: bool = True
    border: bool = True
    two_column: bool = False
    inverse: bool = False
    """Flip the board to Black's view."""

    body_size_pt: float | None = None
    """Set the body at this size instead of the class's own, over ``body_leading_pt``.

    The SVG path sets this book at 8.6 over 10.406 pt, measured off the Quality Chess
    reference page. Leaving the LaTeX side at the class's 10 over 12 makes the same
    source run to two pages where the other exporter needs one: not a difference of
    content, but not a book anyone would call the same either."""

    body_leading_pt: float | None = None

    extra_packages: tuple[str, ...] = ()


def preamble(options: LatexOptions | None = None) -> str:
    """A complete, compilable preamble.

    ``xskak`` is loaded after ``chessboard`` because it configures it; loading them the
    other way round leaves ``\\mainline`` without its board. ``chessfss`` comes with
    ``chessboard`` but is named explicitly so the font commands are unambiguous.
    """
    opt = options or LatexOptions()
    babel = BABEL_LANGUAGES.get(opt.language, "english")
    family = CHESSFSS_FAMILIES.get(opt.font_family) if opt.font_family else None

    lines = [
        f"\\documentclass[{opt.class_options}]{{{opt.document_class}}}",
        "",
        "% --- encoding and text fonts -------------------------------------------",
        "\\usepackage[T1]{fontenc}",
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage{lmodern}",
        # `chessfss` asks T1/lmss for shape `up` while it is loading; Latin Modern Sans
        # declares `n` and not `up`, and pdfTeX substitutes in silence -- an undeclared
        # font substitution in the middle of a typography deliverable. Declaring the
        # substitution here makes it a decision instead of a log line.
        "\\makeatletter\\input{t1lmss.fd}\\makeatother",
        "\\DeclareFontShape{T1}{lmss}{m}{up}{<->ssub*lmss/m/n}{}",
        "\\usepackage{textcomp}   % TS1: a real dagger, minus sign and plus-minus",
        # Build the PDF's ToUnicode map from the glyph names, so `\\textminus` extracts
        # as U+2212 rather than as a hyphen and `\\textdagger` as U+2020. Without it the
        # text layer of a typographic export cannot be compared with anything -- and
        # comparing it with the SVG export, token by token, is the point.
        "\\input{glyphtounicode}",
        "\\pdfgentounicode=1",
        f"\\usepackage[{babel}]{{babel}}",
        "\\usepackage{microtype}   % real protrusion and expansion, not decoration",
        "",
        "% --- page ---------------------------------------------------------------",
        f"\\usepackage[{opt.geometry}]{{geometry}}",
        "\\usepackage{graphicx}",
        "\\usepackage{multicol}",
        "",
        "% --- chess --------------------------------------------------------------",
        "\\usepackage{chessfss}    % font selection layer",
        "\\usepackage{chessboard}  % the diagram",
        "\\usepackage{xskak}       % game tracking, \\mainline, \\variation",
        "",
        "% Widows and orphans: TeX's defaults tolerate both. A book does not.",
        "\\widowpenalty=10000",
        "\\clubpenalty=10000",
        "\\brokenpenalty=10000     % no hyphen across a page break",
        "\\raggedbottom",
        "",
        "% Piece set for the whole document -- one line changes every diagram.",
        (
            f"\\setchessfontfamily{{{family}}}"
            if family
            else "% (conjunto de pecas padrao do chessfss: nenhuma familia pedida)"
        ),
        "",
        "% Board defaults. Every diagram may still override any of these locally.",
        "\\setchessboard{",
        f"  boardfontsize={opt.board_font_size},",
        f"  showmover={'true' if opt.show_mover else 'false'},",
        f"  label={'true' if opt.coordinates else 'false'},",
        f"  border={'true' if opt.border else 'false'},",
        "  labelleft=true, labelbottom=true, labelright=false, labeltop=false,",
        "  labelfontsize=6pt,",
        "  padding=0pt,",
        "}",
        "",
        "% A diagram is a float-free block, centred, with air above and below that is",
        "% proportional to the text -- not a fixed rule that breaks at other sizes.",
        "\\newenvironment{diagrama}",
        "  {\\par\\addvspace{\\baselineskip}\\centering}",
        "  {\\par\\addvspace{\\baselineskip}}",
        "",
        "% Diagram numbering that the text can refer to (SPEC: numeracao automatica).",
        "\\newcounter{diagrama}",
        "\\newcommand{\\diagramnumber}{%",
        "  \\refstepcounter{diagrama}\\textbf{\\thediagrama}}",
        "",
        "% ONE piece design per document. `\\symknight` and its family select",
        "% LSF/<family>/<series>, and the legacy chess families are cut in the MEDIUM",
        "% series only -- ask for bold and LaTeX substitutes a different family",
        "% (skaknew), which is how the cycle-1 export ended up with Chess-Alpha on the",
        "% board and SkakNew-Figurine-Bold in the text: two piece drawings in one book.",
        # `\\upshape` as well as `\\mdseries`, for the same reason: the legacy chess
        # families are cut in ONE series and ONE shape, so a figurine that inherits the
        # italic of a caption makes LaTeX substitute another family and the book gets two
        # piece drawings again. The compiler reported it as
        # `Font shape 'LSF/alpha/m/it' undefined`.
        "\\newcommand{\\cfig}[1]{{\\mdseries\\upshape\\csname sym#1\\endcsname}}",
        "",
        "% The ellipsis a chess book sets before a Black move. T1 has no ellipsis glyph",
        "% and `\\ldots` sets three periods a full space apart -- `13. . . bxc5` is what",
        "% the cycle-1 proof printed. Three tight dots read as the SVG side's U+2026.",
        "\\newcommand{\\caissadots}{\\kern.04em.\\kern.04em.\\kern.04em.\\relax}",
        "",
        "% A game heading is a COLUMN heading, not a chapter opening. `\\chapter*`",
        "% inside `multicols` injects the chapter's opening space into the column (25 mm",
        "% of dead white in the cycle-1 proof) and sets the title at display size in a",
        "% 63 mm measure, where it breaks in the middle of the phrase.",
        "\\newcommand{\\gameheading}[1]{%",
        "  \\par\\addvspace{0.6\\baselineskip}%",
        "  {\\centering\\bfseries #1\\par}%",
        "  \\nobreak\\vspace{0.25\\baselineskip}%",
        "  \\hrule height 0.35mm\\vspace{0.35mm}\\hrule height 0.18mm%",
        "  \\nobreak\\vspace{0.5\\baselineskip}}",
    ]
    for package in opt.extra_packages:
        lines.append(f"\\usepackage{{{package}}}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Diagrams
# --------------------------------------------------------------------------- #
def _mark_options(marks: Sequence[Mark]) -> list[str]:
    """Translate our marks into ``chessboard``'s pgf mark keys.

    ``chessboard`` applies one ``pgfstyle`` at a time and then consumes the fields or
    moves listed after it, so the marks are grouped by kind and emitted as a sequence of
    style-then-targets pairs. Interleaving them silently drops all but the last.
    """
    highlights = [m for m in marks if isinstance(m, SquareHighlight)]
    circles = [m for m in marks if isinstance(m, CircleMark)]
    arrows = [m for m in marks if isinstance(m, Arrow)]

    out: list[str] = []
    if highlights:
        fields = ",".join(m.square for m in highlights)
        # `pgfstyle=color` with no colour named fills the square SOLID BLACK and the
        # piece standing on it disappears -- observed in the first compiled proof. A
        # highlight has to sit *under* the piece, so it is set as a light tint.
        out.append(f"color={HIGHLIGHT_TINT}")
        out.append("pgfstyle=color")
        out.append(f"backfields={{{fields}}}")
    if circles:
        fields = ",".join(m.square for m in circles)
        out.append("pgfstyle=circle")
        out.append(f"markfields={{{fields}}}")
    if arrows:
        straight = [m for m in arrows if not _is_knight(m)]
        knights = [m for m in arrows if _is_knight(m)]
        # 1. The whole arrow in the BACKGROUND layer, under the pieces. The named
        #    `straightmove` style on its own draws a headless bar the width of a square
        #    -- on the first compiled proof it read as a blacked-out g-file -- so the
        #    line width is given as a pgf option list in front of the style name, which
        #    is the form `chessboard` accepts.
        out.append(f"color={ARROW_COLOUR}")
        if straight:
            moves = ",".join(f"{m.source}-{m.target}" for m in straight)
            out.append(f"backstyle={{{ARROW_SHAFT_PGF}straightmove}}")
            out.append(f"backmoves={{{moves}}}")
        if knights:
            # chessboard draws the L for a knight itself, which is why the style exists.
            moves = ",".join(f"{m.source}-{m.target}" for m in knights)
            out.append(f"backstyle={{{ARROW_SHAFT_PGF}knightmove}}")
            out.append(f"backmoves={{{moves}}}")
        # 2. The head alone, back on top, keylined in the page colour. `_last_leg` is
        #    the one-square move into the destination, so `shorten <=` can hide all of
        #    it but the tip.
        legs = [(_last_leg(m), m) for m in arrows]
        for width, colour in ((2.8, "draw=white,"), (1.0, "")):
            moves = ",".join(leg for leg, _ in legs if leg)
            if not moves:
                break
            style = ARROW_HEAD_PGF.format(
                width=width, colour=colour,
                back=ARROW_HEAD_BACK_PT, front=ARROW_HEAD_FRONT_PT,
            )
            out.append(f"markstyle={{{style}straightmove}}")
            out.append(f"markmoves={{{moves}}}")
    return out


def _last_leg(arrow: Arrow) -> str:
    """The one-square move that ends where ``arrow`` ends, as ``e6-e7``.

    The head is drawn on this leg alone. Along the arrow's own direction for a straight
    move; along the second leg of the L for a knight's move, which is how `chessboard`
    draws `knightmove` and therefore where the head has to sit.
    """
    from .board_svg import FILES, square_index, square_name

    r0, c0 = square_index(arrow.source)
    r1, c1 = square_index(arrow.target)
    dr, dc = r1 - r0, c1 - c0
    if sorted((abs(dr), abs(dc))) == [1, 2]:
        # `chessboard` travels the long leg first, then turns: the final step is the
        # short one.
        step = (0, (1 if dc > 0 else -1)) if abs(dc) == 1 else ((1 if dr > 0 else -1), 0)
    else:
        step = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
    pr, pc = r1 - step[0], c1 - step[1]
    if not (0 <= pr < 8 and 0 <= pc < 8):
        return f"{arrow.source}-{arrow.target}"
    del FILES
    return f"{square_name(pr, pc)}-{arrow.target}"


def _is_knight(arrow: Arrow) -> bool:
    from .board_svg import square_index

    r0, c0 = square_index(arrow.source)
    r1, c1 = square_index(arrow.target)
    return sorted((abs(r1 - r0), abs(c1 - c0))) == [1, 2]


def chessboard_command(
    fen: str,
    *,
    marks: Sequence[Mark] = (),
    inverse: bool = False,
    board_font_size: str | None = None,
    show_mover: bool | None = None,
    coordinates: bool | None = None,
    extra: Sequence[str] = (),
) -> str:
    """One ``\\chessboard`` call. Editable text, never an image.

    The FEN goes in whole -- side to move, castling rights and all -- because
    ``showmover`` reads it from there, and a diagram that has lost its side-to-move is a
    diagram that has lost its point.

    **The FEN must be braced.** ``chessboard`` parses its optional argument with keyval,
    where a comma ends the value and a blank line ends the argument; a full FEN carries
    spaces and hyphens (``... b - - 0 21``) and unbraced it makes the parser run off the
    end of the option list. The compiler's report of this is
    ``Paragraph ended before \\FenBoard was complete`` -- observed, not predicted: it is
    what `tools/build_latex.py` produced before this brace was added, and it stopped the
    document compiling at all.
    """
    keys: list[str] = [f"setfen={{{fen}}}"]
    if inverse:
        keys.append("inverse=true")
    if board_font_size:
        keys.append(f"boardfontsize={board_font_size}")
    if show_mover is not None:
        keys.append(f"showmover={'true' if show_mover else 'false'}")
    if coordinates is not None:
        keys.append(f"label={'true' if coordinates else 'false'}")
    keys.extend(_mark_options(marks))
    keys.extend(extra)
    body = ",\n  ".join(keys)
    return f"\\chessboard[\n  {body}]"


def diagram_block(
    fen: str,
    *,
    caption: str | None = None,
    number: bool = False,
    marks: Sequence[Mark] = (),
    inverse: bool = False,
    board_font_size: str | None = None,
    stipulation: str | None = None,
    caption_tex: str | None = None,
) -> str:
    """A complete diagram with its caption and optional automatic number.

    ``caption_tex`` is LaTeX the caller has already built -- the route the shared
    translation in ``tools/build_latex.py`` uses, so that the caption goes through the
    same typographic pass and the same figurine runs as the SVG page's. Cycle 2 escaped a
    raw ASCII string here and the caption came out `After 21.Bxh7+` on one exporter and
    `After 21.Bxh7†.` on the other.
    """
    parts = ["\\begin{diagrama}"]
    if stipulation:
        parts.append(f"  {{\\small\\itshape {escape_latex(stipulation)}}}\\par\\smallskip")
    parts.append("  " + chessboard_command(
        fen, marks=marks, inverse=inverse, board_font_size=board_font_size
    ).replace("\n", "\n  "))
    if caption or number or caption_tex:
        bits = []
        if number:
            bits.append("\\diagramnumber")
        if caption_tex:
            bits.append(caption_tex)
        elif caption:
            bits.append(escape_latex(caption))
        parts.append("  \\par\\smallskip{\\small\\itshape " + " \\quad ".join(bits) + "}")
    parts.append("\\end{diagrama}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Notation
# --------------------------------------------------------------------------- #
def figurine_move(san: str, *, language: str = "en") -> str:
    """One move as figurine markup.

    ``chessfss`` exposes the pieces as ``\\symking`` and friends, so a move becomes the
    symbol plus the rest of the move set as text. For a whole line prefer
    :func:`mainline`, which lets ``xskak`` do it and keeps the board in step.
    """
    symbols = {
        "K": "\\symking",
        "Q": "\\symqueen",
        "R": "\\symrook",
        "B": "\\symbishop",
        "N": "\\symknight",
        "P": "\\sympawn",
    }
    move = parse_san(san)
    if move is None:
        return escape_latex(san)
    if move.is_castle:
        return f"{move.castle}{move.suffix}"
    # The symbol macros must be braced. `\symknight` followed directly by `xc5` is
    # read by TeX as a control sequence named `symknightxc5`, which is undefined -- and
    # `\newcommand`-style macros do not error on that in text mode, they typeset the
    # name. The observed output was the literal string `\symknightxc5` on the page.
    def sym(letter: str) -> str:
        macro = symbols.get(letter)
        return f"{{{macro}}}" if macro else escape_latex(letter)

    out = sym(move.piece) if move.piece else ""
    out += move.disambiguation
    if move.capture:
        out += "x"
    out += move.target
    if move.promotion:
        out += "=" + sym(move.promotion)
    return out + move.suffix


# --------------------------------------------------------------------------- #
# House style -- the SAME house the SVG path sets
# --------------------------------------------------------------------------- #
# Cycle 1 handed raw SAN to `\mainline` and took whatever xskak's default style produced.
# Extracting the text layer of both exports of the same passage, they diverged in five
# places:
#
#     element        SVG            LaTeX (cycle 1)
#     move number    1.d4           1 d4        (no period)
#     capture        cxd5           c*d5        (multiplication sign)
#     castling       0-0 (en dash)  O-O         (letter O, hyphen)
#     check          Bxd2 dagger    Xd2+        (plus)
#     ellipsis       13...  U+2026  13. . .     (three spaced periods)
#
# A book exported in both formats came out in two notations. The cure is not to configure
# xskak: it is to stop asking xskak to *print*. The moves are played invisibly with
# `\hidemoves`, so the game state, `\xskakget` and every later diagram stay exactly as
# they were, and the visible notation is set here, from the same rules
# `caissa.typeset.typography` applies on the SVG side.

CASTLING_SHORT_TEX = r"\mbox{0--0}"
CASTLING_LONG_TEX = r"\mbox{0--0--0}"
"""Zero and an en dash, the Quality Chess form -- ``--`` is TeX's en dash.

Boxed, because TeX will otherwise break the line at the dash: the first compile of this
change printed ``8.0--`` at the end of one line and ``0`` at the start of the next."""

CHECK_TEX = r"\textdagger{}"
MATE_TEX = r"\textdaggerdbl{}"
"""`textcomp`'s TS1 dagger and double dagger. Both carry a real ToUnicode mapping
(U+2020, U+2021), so the text layer of the two exports matches character for character."""

ELLIPSIS_TEX = r"\caissadots{}"
"""A macro, not `\\ldots`: T1 has no ellipsis glyph and `\\ldots` sets three periods a
full space apart, which is what the cycle-1 proof printed as `13. . . bXc5`."""

DASH_TEX = "--"

_FIGURINE_NAMES = {
    "K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight", "P": "pawn",
}

_MOVE_NUMBER = re.compile(r"^(\d{1,3})(\.{1,3}|\.?…)")
_RESULT = re.compile(r"^(1-0|0-1|1/2-1/2|½-½)$")


def figurine_symbol(letter: str) -> str:
    """One piece glyph, in the document's own chess family and medium series.

    ``\\cfig`` rather than ``\\symknight`` directly: see the preamble comment. The legacy
    chess families are cut in the medium series only, so a figurine that inherits a bold
    context makes LaTeX substitute a *different family* -- which is exactly how the
    cycle-1 export ended up with Chess-Alpha on the board and SkakNew-Figurine-Bold in
    the text, two piece designs in one book.
    """
    name = _FIGURINE_NAMES.get(letter.upper())
    return f"\\cfig{{{name}}}" if name else escape_latex(letter)


def typeset_move(
    san: str,
    *,
    language: str = "en",
    figurine: bool = True,
    check_style: str = "dagger",
) -> str:
    """One SAN move in the house style, as LaTeX."""
    move = parse_san(san)
    if move is None:
        return escape_latex(san)

    def suffix(text: str) -> str:
        out = ""
        for char in text:
            if char == "+":
                out += CHECK_TEX if check_style == "dagger" else "+"
            elif char == "#":
                out += MATE_TEX if check_style == "dagger" else "\\#"
            else:
                out += char
        return out

    if move.is_castle:
        base = CASTLING_LONG_TEX if move.castle == "O-O-O" else CASTLING_SHORT_TEX
        return base + suffix(move.suffix)

    out = ""
    if move.piece:
        out += figurine_symbol(move.piece) if figurine else language_letter(move.piece, language)
    out += move.disambiguation
    if move.capture:
        out += "x"  # lower case, as on the SVG side
    out += move.target
    if move.promotion:
        out += "="
        out += (
            figurine_symbol(move.promotion) if figurine
            else language_letter(move.promotion, language)
        )
    return out + suffix(move.suffix)


def typeset_moves(
    moves: str,
    *,
    language: str = "en",
    figurine: bool = True,
    check_style: str = "dagger",
) -> str:
    """A whole line of moves in the house style, move numbers and all.

    Accepts the same string ``mainline`` accepts -- ``"1.d4 Nf6 2.c4 e6"`` or
    ``"13...bxc5 14.Nb3"`` -- and returns LaTeX. Nothing here consults the board, so the
    caller is responsible for the moves being legal; :func:`played` plays them.
    """
    out: list[str] = []
    for token in moves.split():
        if _RESULT.match(token):
            out.append(token.replace("-", DASH_TEX))
            continue
        prefix = ""
        match = _MOVE_NUMBER.match(token)
        if match:
            dots = match.group(2)
            prefix = match.group(1) + (
                ELLIPSIS_TEX if (dots in ("...", "…", ".…")) else "."
            )
            token = token[match.end():]
        if not token:
            out.append(prefix)
            continue
        out.append(prefix + typeset_move(
            token, language=language, figurine=figurine, check_style=check_style
        ))
    return " ".join(out)


def played(moves: str) -> str:
    """``\\hidemoves``: advance the game without printing anything.

    ``skak``'s own command, which ``xskak`` loads. It keeps every promise ``\\mainline``
    kept -- the board follows the moves, ``\\xskakget`` still answers, a later
    ``\\chessboard`` is in the right position -- and gives up only the printing, which is
    the part the two exporters disagreed about.
    """
    return f"\\hidemoves{{{moves}}}"


def moveline(
    moves: str,
    *,
    language: str = "en",
    figurine: bool = True,
    check_style: str = "dagger",
) -> str:
    """The replacement for ``\\mainline``: play the moves, then set them our way."""
    return played(moves) + typeset_moves(
        moves, language=language, figurine=figurine, check_style=check_style
    )


def mainline(moves: str) -> str:
    """``xskak``'s ``\\mainline``: figurines, move numbers and board state in one go."""
    return f"\\mainline{{{moves}}}"


def variation(moves: str) -> str:
    return f"\\variation{{{moves}}}"


def newgame(fen: str | None = None, *, moveid: str | None = None) -> str:
    """``\\newchessgame``, with the move counter set from the FEN.

    ``xskak`` starts a ``setfen`` game at move 1 regardless of the FEN's own fullmove
    number, so a following ``\\mainline{13...bxc5}`` is rejected outright with
    ``mainline: 13 is not the correct move number`` and the document does not compile.
    The counter has to be set explicitly through ``moveid``, whose form is the fullmove
    number followed by ``w`` or ``b`` -- ``13b`` for Black to play move 13.

    Deriving it here rather than asking the caller for it is deliberate: the information
    is already in the FEN, and a caller who has to restate it is a caller who will one
    day restate it wrongly.
    """
    if not fen:
        return "\\newchessgame"
    if moveid is None:
        parts = fen.split()
        if len(parts) >= 6 and parts[5].isdigit():
            moveid = f"{int(parts[5])}{'b' if parts[1] == 'b' else 'w'}"
    if moveid:
        return f"\\newchessgame[setfen={{{fen}}}, moveid={moveid}]"
    return f"\\newchessgame[setfen={{{fen}}}]"


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@dataclass
class LatexDocument:
    """Assemble a compilable document."""

    options: LatexOptions = field(default_factory=LatexOptions)
    title: str | None = None
    author: str | None = None
    body: list[str] = field(default_factory=list)

    def add(self, tex: str) -> None:
        self.body.append(tex)

    def add_text(self, text: str) -> None:
        self.body.append(escape_latex(text))

    def add_diagram(self, fen: str, **kwargs) -> None:
        self.body.append(diagram_block(fen, **kwargs))

    def render(self) -> str:
        parts = [preamble(self.options), ""]
        if self.title:
            parts.append(f"\\title{{{escape_latex(self.title)}}}")
        if self.author:
            parts.append(f"\\author{{{escape_latex(self.author)}}}")
        parts.append("\\begin{document}")
        if self.options.body_size_pt:
            leading = self.options.body_leading_pt or self.options.body_size_pt * 1.21
            parts.append(
                f"\\fontsize{{{self.options.body_size_pt}pt}}{{{leading}pt}}"
                f"\\selectfont"
            )
        if self.title:
            parts.append("\\maketitle")
        if self.options.two_column:
            parts.append("\\begin{multicols}{2}")
        parts.extend(self.body)
        if self.options.two_column:
            parts.append("\\end{multicols}")
        parts.append("\\end{document}")
        return "\n".join(parts) + "\n"

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render(), encoding="utf-8")
        return target


def makefile(tex_name: str = "livro.tex", *, engine: str = "pdflatex") -> str:
    """A Makefile that builds the document reproducibly.

    ``latexmk`` is used when present because it works out how many passes the cross
    references need; the plain fallback runs the engine three times, which is enough for
    a table of contents and diagram numbering to settle.
    """
    stem = Path(tex_name).stem
    return f"""# Gerado por caissa.typeset.latex
# Alvos: make (pdf) | make watch | make clean

TEX      = {engine}
LATEXMK  = latexmk
MAIN     = {stem}
FLAGS    = -interaction=nonstopmode -halt-on-error -file-line-error

.PHONY: all pdf watch clean distclean

all: pdf

pdf: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex
\t@if command -v $(LATEXMK) >/dev/null 2>&1; then \\
\t\t$(LATEXMK) -pdf -$(TEX) $(FLAGS) $(MAIN).tex; \\
\telse \\
\t\t$(TEX) $(FLAGS) $(MAIN).tex && \\
\t\t$(TEX) $(FLAGS) $(MAIN).tex && \\
\t\t$(TEX) $(FLAGS) $(MAIN).tex; \\
\tfi

watch:
\t$(LATEXMK) -pdf -pvc -$(TEX) $(FLAGS) $(MAIN).tex

clean:
\trm -f $(MAIN).aux $(MAIN).log $(MAIN).out $(MAIN).toc \\
\t      $(MAIN).fls $(MAIN).fdb_latexmk $(MAIN).synctex.gz

distclean: clean
\trm -f $(MAIN).pdf
"""


# --------------------------------------------------------------------------- #
# Compilation
# --------------------------------------------------------------------------- #
@dataclass
class CompileResult:
    ok: bool
    engine: str | None
    pdf: Path | None
    log: str
    errors: list[str] = field(default_factory=list)
    reason: str = ""

    def summary(self) -> str:
        if self.ok:
            return f"compilado com {self.engine}: {self.pdf}"
        if self.engine is None:
            return f"nao compilado: {self.reason}"
        return f"falhou com {self.engine}: {'; '.join(self.errors[:3]) or self.reason}"


# chessfss names a piece family; the *font* behind it comes from a separate TeX package
# (`chess-<family>` / `enpassant` / `skaknew`), and asking for a family whose Type1 file
# is not installed does not degrade -- pdfTeX stops with
# `cannot open chess-merida-board-fig-raw.pfb` and produces nothing. So the family is
# checked against the file system before it is written into a preamble, exactly as
# `fonts.verify_spec` checks a glyph table against a real font file.
CHESSFSS_PROBE = "chess-{family}-board-fig-raw.pfb"


def chessfss_family_available(family: str) -> bool:
    """Is the Type1 font behind this chessfss family actually installed?"""
    kpse = shutil.which("kpsewhich")
    if kpse is None:
        return False
    try:
        proc = subprocess.run(
            [kpse, CHESSFSS_PROBE.format(family=family)],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(proc.stdout.strip())


def first_available_family(candidates: Sequence[str]) -> str | None:
    """The first family in ``candidates`` whose font is installed, or None."""
    for family in candidates:
        if chessfss_family_available(family):
            return family
    return None


def tex_available(engine: str = "pdflatex") -> str | None:
    """Path to a TeX engine, or None. Checked, never assumed."""
    return shutil.which(engine)


_ERROR_LINE = re.compile(r"^(?:! |.*?:\d+: )(.*)$", re.MULTILINE)


# --------------------------------------------------------------------------- #
# The searchable text layer
# --------------------------------------------------------------------------- #
_FIG_TOUNICODE_HEAD = """/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Caissa) /Ordering (chess-figurine) /Supplement 0 >> def
/CMapName /Caissa-chess-figurine-0 def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
"""

_FIG_TOUNICODE_TAIL = """endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""


def retag_figurine_text(pdf_path: str | Path) -> dict[str, str]:
    """Give the inline chess font a ToUnicode that says what the reader sees.

    A legacy chess family is a *symbol* font: chessfss sets the knight from the slot the
    text encoding calls `dagger`, the bishop from `ellipsis` and the queen from `florin`,
    and pdfTeX -- which builds its ToUnicode from those glyph names -- therefore wrote

        1.d4 (dagger)f6 2.c4 e6 3.g3 (ellipsis)b4(dagger) 4.(ellipsis)d2

    into the text layer of the cycle-5 proof. Two of those three characters are in use on
    the same page for something else: `dagger` is this book's check mark and `ellipsis`
    is its Black-move ellipsis. Searching the delivered PDF for `Nf6`, `Nb3` or `Qxh7`
    returned zero hits, copy and paste gave mutilated notation, and a screen reader read
    `1.d4 f6`.

    The codes themselves are already right -- chessfss encodes the figurine font so that
    `\symknight` is character `N`, `\symbishop` is `B`, and so on -- so the repair is
    to replace the CMap that mistranslates them, not the font, the encoding or the
    document. Only the **figurine** font is touched; the board font, whose glyphs really
    are squares and not letters, is left alone and named in the return value.

    Returns ``{"<xref> <BaseFont>": what was done}`` for every chess font found, so the
    caller can print it rather than assume it. Keyed by object number because a document
    carries the same ``BaseFont`` twice -- once for the board and once for the figurine
    -- and a report keyed by name would show only the second and hide the repair.
    """
    import pymupdf

    doc = pymupdf.open(str(pdf_path))
    report: dict[str, str] = {}
    try:
        for xref in range(1, doc.xref_length()):
            if doc.xref_get_key(xref, "Type")[1] != "/Font":
                continue
            base = doc.xref_get_key(xref, "BaseFont")[1] or ""
            if "chess" not in base.lower() and "skak" not in base.lower():
                continue
            kind, value = doc.xref_get_key(xref, "ToUnicode")
            name = f"{xref} {base.lstrip(chr(47))}"
            if kind != "xref":
                report[name] = "sem ToUnicode: nao tocado"
                continue
            cmap_xref = int(value.split()[0])
            current = doc.xref_stream(cmap_xref) or b""
            if b"board" in current:
                report[name] = "fonte de tabuleiro: nao tocada"
                continue
            codes = sorted(set(int(m, 16) for m in re.findall(
                rb"<([0-9A-Fa-f]{2})>\s*<[0-9A-Fa-f]{4,}>", current)))
            letters = {}
            for code in codes:
                char = chr(code)
                if char.upper() not in _FIGURINE_CODE_LETTERS:
                    raise ValueError(
                        f"{name}: o codigo {code} ({char!r}) nao e uma letra de peca; "
                        "a fonte de figurinos deixou de ser codificada por letra e a "
                        "camada de texto tem de ser refeita, nao remendada"
                    )
                letters[code] = _FIGURINE_CODE_LETTERS[char.upper()]
            body = "".join(f"<{code:02X}> <{ord(letter):04X}>\n"
                           for code, letter in sorted(letters.items()))
            stream = (_FIG_TOUNICODE_HEAD
                      + f"{len(letters)} beginbfchar\n{body}endbfchar\n"
                      + _FIG_TOUNICODE_TAIL).encode("ascii")
            doc.update_stream(cmap_xref, stream)
            report[name] = ("figurinos remapeados: "
                            + " ".join(f"{c:02X}->{l}" for c, l in sorted(letters.items())))
        doc.saveIncr()
    finally:
        doc.close()
    return report


_FIGURINE_CODE_LETTERS = {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N", "P": "P"}
"""Character code of the figurine font to the letter a reader searches for.

The identity on the five piece letters, because chessfss already encodes them that way.
It is written out rather than assumed so that :func:`retag_figurine_text` can *fail* if a
future family encodes its pieces somewhere else, instead of silently writing a CMap that
says the wrong thing -- which is the failure this function exists to repair."""


def compile_document(
    tex_source: str | Path,
    *,
    engine: str = "pdflatex",
    workdir: str | Path | None = None,
    runs: int = 2,
    timeout: int = 180,
) -> CompileResult:
    """Compile and report exactly what happened.

    ``-interaction=nonstopmode`` is essential: without it a missing package stops at a
    prompt and the call hangs until the timeout, which reads as a crash rather than as
    the missing dependency it is.
    """
    exe = tex_available(engine)
    if exe is None:
        return CompileResult(
            ok=False,
            engine=None,
            pdf=None,
            log="",
            reason=(
                f"nenhum motor TeX encontrado no PATH (procurado: {engine}). "
                f"Instale MiKTeX ou TeX Live para compilar a saida LaTeX."
            ),
        )

    source = Path(tex_source)
    if source.is_file():
        directory = Path(workdir) if workdir else source.parent
        tex_file = source
    else:
        directory = Path(workdir or tempfile.mkdtemp(prefix="caissa-tex-"))
        directory.mkdir(parents=True, exist_ok=True)
        tex_file = directory / "documento.tex"
        tex_file.write_text(str(tex_source), encoding="utf-8")

    # Remove any PDF left by an earlier run BEFORE compiling. Without this a failed
    # compile leaves the previous PDF on disk, `pdf.exists()` is true, and the function
    # reports success for a document that did not compile -- which is exactly what
    # happened to this cycle's first attempt at the `\DeclareFontShape` line: the build
    # printed "compilado com pdflatex" over a fatal error and a three-hour-old PDF.
    stale = Path(tex_source).with_suffix(".pdf") if Path(tex_source).is_file() else None
    if stale is not None and stale.exists():
        try:
            stale.unlink()
        except OSError:  # pragma: no cover - a locked file is reported by the caller
            pass

    log = ""
    for _ in range(max(1, runs)):
        try:
            proc = subprocess.run(
                [
                    exe,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-file-line-error",
                    tex_file.name,
                ],
                cwd=str(directory),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return CompileResult(
                ok=False,
                engine=engine,
                pdf=None,
                log=log,
                reason=f"tempo esgotado ({timeout}s)",
            )
        log = proc.stdout + proc.stderr

    pdf = tex_file.with_suffix(".pdf")
    log_file = tex_file.with_suffix(".log")
    if log_file.exists():
        log = log_file.read_text(encoding="utf-8", errors="replace")

    errors = [
        line.strip()
        for line in _ERROR_LINE.findall(log)
        if line.strip() and not line.startswith("=")
    ]
    if pdf.exists() and pdf.stat().st_size > 0:
        return CompileResult(ok=True, engine=engine, pdf=pdf, log=log, errors=errors)
    return CompileResult(
        ok=False,
        engine=engine,
        pdf=None,
        log=log,
        errors=errors,
        reason="o motor terminou sem produzir PDF",
    )
