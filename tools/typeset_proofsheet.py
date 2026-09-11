"""Gera `benchmarks/reports/proofsheet.pdf` — a evidência da frente F7.

Como rodar:

    .venv\\Scripts\\python.exe tools\\typeset_proofsheet.py
    .venv\\Scripts\\python.exe tools\\typeset_proofsheet.py --png   # e rasteriza

A folha existe para ser *olhada*, e está disposta de modo que os defeitos que a carta
dos críticos lista fiquem visíveis em vez de enterrados:

1. todas as famílias instaladas e verificadas, mesma posição, mesmo tamanho — uma família
   com a tabela errada mostra um bispo onde devia haver um cavalo, à primeira vista;
2. todas as molduras, colocações de coordenada e indicadores de lance;
3. texto corrido com figurino a 9, 10, 11 e 12 pt sobre uma régua de linha de base,
   porque um figurino que flutua fora da linha é invisível até se encostar nele algo reto;
4. o mesmo diagrama a 20, 40, 60 e 90 mm — onde pesos de traço e corpos de coordenada
   se desmancham;
5. uma página densa de livro em duas colunas, prosa e lances e três diagramas;
6. a mesma página no tema escuro, que é onde a qualidade costuma desabar.

**Tudo passa pelo compositor de `typeset_page.py`.** Nenhuma seção posiciona nada por
coordenada fixa: no ciclo 1 essa era a causa de metade das dez páginas emitirem conteúdo
fora do papel, uma delas por 70 mm. Aqui uma seção que não cabe transborda para a página
seguinte, e um bloco que não cabe em página nenhuma levanta `CompositionError`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import typeset_page as tp  # noqa: E402
from caissa.typeset import fonts  # noqa: E402
from caissa.typeset.typography import Hyphenator  # noqa: E402

from caissa.typeset.board_svg import (  # noqa: E402
    Arrow,
    CircleMark,
    CoordinateStyle,
    DiagramStyle,
    FrameStyle,
    SideToMove,
    SquareHighlight,
    get_theme,
)

LEFT_HYPHEN_MIN, RIGHT_HYPHEN_MIN = 2, 3
"""The house's edge minimums: two letters may stay on the line before the hyphen, three
must go over to the next.

These are the minimums the pattern files were *made* for -- `hyphen.tex` and `hyph-pt.tex`
are both published with ``\\lefthyphenmin=2 \\righthyphenmin=3`` -- and cycle 6's 3/3 was a
deviation from them that cost breakpoints without buying anything. The fragment a reader
notices is the one that **starts** a line, and that is the *right* minimum, kept at 3.
With 3 on the left, `pa-gina`, `se-guinte`, `ga-nham` and `ob-tains` are all illegal, and
the report shows what refusing them cost: the Portuguese page's word-space band is 3.37x
with 3/3 and **2.13x** with 2/3, its standard deviation 0.340 against 0.222 and its lines
outside 0.85x-1.50x 8 of 22 against 4 of 22 -- the same text through the same breaker,
with only the left minimum changed."""


def book_hyphenator(language: str) -> Hyphenator:
    """The hyphenator the composed pages use, at the house minimums."""
    return Hyphenator(language, left=LEFT_HYPHEN_MIN, right=RIGHT_HYPHEN_MIN)


OUT = ROOT / "benchmarks" / "reports"

# Aparo Quality Chess, medido no PDF de referência: 456 x 648 pt.
TRIM_W, TRIM_H = 160.9, 228.6

# Duas posições transcritas da página de referência e *provadas* jogando os lances do
# próprio livro em python-chess — ver docs/quality/F7_REPORT.md §3.
FEN_MARECO = "r2q1rk1/pb1n1ppp/1p6/2Pp4/8/6P1/PP1NPPBP/2RQ1RK1 b - - 0 13"
FEN_RIOS21 = "4rnk1/pbr2ppB/1pq1p3/4P1BQ/2P5/P5R1/5PPP/R5K1 b - - 0 21"
# Depois de 14.Nb3, a posição de que fala o último parágrafo da coluna direita.
FEN_AFTER_14NB3 = "r2q1rk1/pb1n1ppp/8/2pp4/8/1N4P1/PP2PPBP/2RQ1RK1 b - - 1 14"
FEN_START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# A position whose a-file and first rank leave a free corner on every labelled square,
# which is what `CoordinateStyle.INSIDE` needs. A rook or a queen on one of them leaves
# no corner at any printable label size, and the renderer then falls back to the outside
# convention rather than cutting the piece -- both cases are shown in section 3.
FEN_INSIDE = "4rrk1/pp3ppp/2n1b3/8/8/2N1B3/PP3PPP/6K1 w - - 0 1"

BODY_PT = 8.6
"""Corpo do texto da página de livro, medido na página de referência: a Quality Chess
compõe este livro a cerca de 8,6/10,4 pt numa coluna de 63 mm."""


def gallery_geometry() -> tp.PageGeometry:
    """Uma coluna larga para as seções de espécimes."""
    return tp.PageGeometry(TRIM_W, TRIM_H, top=17.0, bottom=16.0, outer=14.0,
                           inner=14.0, columns=1, gutter=0.0)


# A margem interior e a exterior são iguais **por decisão declarada**, não por omissão --
# a pergunta que a crítica do ciclo 8 deixou em aberto ao lado do R5.
#
# A referência que esta página imita é medível, e medi-a: no PDF da Quality Chess (Chess
# Structures, 2015) a tinta do corpo de 12 páginas seguidas dá, a 200 DPI,
#
#     par/verso    n=6   margem esq 11,03 mm   margem dir 10,99 mm
#     ímpar/recto  n=6   margem esq 11,09 mm   margem dir 11,07 mm
#
# -- assimetria média |esq-dir| = 0,032 mm e diferença par x ímpar = 0,063 mm, isto é um
# quarto e metade de um pixel. **A editora que compõe este livro compõe-o com margens
# simétricas**, sem reserva de lombada, e a folha faz o mesmo. (A medida da folha é 14,0 e
# não 11,0: é uma decisão de medida de coluna anterior a este ciclo, não de simetria.)
# `mirror_margins` continua ligado porque o que alterna não é só a margem: é o fólio, e
# esse alterna mesmo com `inner == outer` -- que é por que o R5 era um defeito e a simetria
# das margens não é. Ver `docs/quality/F7_REPORT_C9.md` §1.
BOOK_INNER_MM = 14.0
BOOK_OUTER_MM = 14.0


def book_geometry(first_folio: int = 44, *, mirror_margins: bool = True) -> tp.PageGeometry:
    """A geometria da página de livro, com a paridade do fólio que ela vai imprimir.

    `first_folio` é o número **impresso** da primeira página da composição, e é dele que
    sai recto/verso. Sem ele o compositor não tem como saber de que lado fica a margem
    exterior, que foi exatamente o buraco do ciclo 8.
    """
    return tp.PageGeometry(TRIM_W, TRIM_H, top=17.0, bottom=16.0,
                           outer=BOOK_OUTER_MM, inner=BOOK_INNER_MM,
                           columns=2, gutter=6.0,
                           mirror_margins=mirror_margins, first_folio=first_folio)


def gallery_style(language: str = "pt") -> tp.TextStyle:
    font, metrics = tp.metrics_for("merida")
    size = 8.6 * 25.4 / 72.0
    return tp.TextStyle(
        size=size,
        leading=size * 1.30,
        metrics=metrics,
        font=font,
        language=language,
        hyphenator=book_hyphenator(language),
    )


def _folio(first: int):  # noqa: ANN202
    def decorate(canvas: tp.Canvas, index: int) -> None:
        canvas.text(TRIM_W / 2, 11.0, str(first + index), size=3.0,
                    fill="#666666", anchor="middle")
    return decorate


# --------------------------------------------------------------------------- #
# 1. Famílias
# --------------------------------------------------------------------------- #
def verified_specs():  # noqa: ANN201
    return [s for s in fonts.available_specs()
            if s.confidence is fonts.Confidence.VERIFIED]


def section_families() -> list[tp.Block]:
    specs = verified_specs()
    from caissa.typeset.board_svg import frame_origin

    items = []
    for spec in specs:
        style = DiagramStyle(font=spec.key, theme="book", width_mm=40.0,
                             coordinates=CoordinateStyle.NONE,
                             frame=FrameStyle.HAIRLINE)
        items.append((tp.diagram(FEN_MARECO, style), spec.family,
                      f"{spec.key} — {spec.confidence.value}", frame_origin(style)[0]))
    return [
        tp.Heading(kind="head", text=f"1. Famílias de fonte — as {len(specs)} VERIFIED",
                   size=4.2, align="left", label="h1"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="Mesma posição, mesmo tamanho, mesma moldura. "
                     "Uma família cuja tabela de glifos esteja errada desenha um bispo "
                     "onde devia haver um cavalo, e isso aparece à primeira vista.",
                     size=2.7, align="left", figurines=False,
                     label="s1"),
        tp.Gallery(kind="gallery", items=items, per_row=3, space_before=1,
                   label="familias"),
    ]


# --------------------------------------------------------------------------- #
# 2. Molduras, coordenadas, indicador de lance
# --------------------------------------------------------------------------- #
SPECIMEN_SQUARE = 4.0
"""Square size shared by every specimen on the frame and indicator rows.

`width_mm` is the *finished* width, so two diagrams that differ only in carrying a
side-to-move marker come out with different boards for the same declared width. Asking
`width_for_square` for the width instead is what keeps a row of specimens comparable --
which is the whole point of a specimen row.
"""

COORDINATE_SPECIMEN_SQUARE = 6.3
"""Bigger, and for a stated reason: an *inside* label is set at 0.32 of a square (see
`DiagramStyle.inside_coordinate_scale`, which is the largest scale that still leaves a
king, a bishop or a pawn a free corner), so it needs a 6.1 mm square to clear the 5.5 pt
printing floor. 6,3 mm gives 5,71 pt e mantem dois especimes por fileira."""


def _specimen(square: float = SPECIMEN_SQUARE, fen: str = FEN_MARECO, **kwargs) -> str:
    from caissa.typeset.board_svg import width_for_square

    style = DiagramStyle(font="merida", theme="book", **kwargs)
    return tp.diagram(fen,
                      DiagramStyle(font="merida", theme="book",
                                   width_mm=width_for_square(style, square),
                                   **kwargs))


def _frame_dx(width_mm: float, fen: str = FEN_MARECO, **kwargs) -> float:
    """How far the board's frame sits from the diagram's left edge, in mm.

    A caption is set from this and not from the fragment: see `board_svg.frame_origin`.
    """
    from caissa.typeset.board_svg import frame_origin

    return frame_origin(
        DiagramStyle(font="merida", theme="book", width_mm=width_mm, **kwargs), fen
    )[0]


def _specimen_pair(square: float = SPECIMEN_SQUARE, fen: str = FEN_MARECO,
                   **kwargs) -> tuple[str, float]:
    """``(svg, frame offset)`` for one specimen, both from the same style."""
    from caissa.typeset.board_svg import width_for_square

    width = width_for_square(DiagramStyle(font="merida", theme="book", **kwargs), square)
    style = DiagramStyle(font="merida", theme="book", width_mm=width, **kwargs)
    return tp.diagram(fen, style), _frame_dx(width, fen, **kwargs)


STM_TEXT_SQUARE = 6.6
"""Square for the ``SideToMove.TEXT`` specimen alone.

The words need a board. At the 4 mm square the other five markers are shown on, "Pretas
jogam" sets at **3.40 pt** -- smaller than the 3.92 pt cycle 1 was failed for, printed on
the sheet that announces a 5.5 pt floor. The renderer now refuses to set it that small
(`board_svg.resolved_side_to_move`), so the specimen is given the 7 mm square it needs:
5.95 pt."""


# A section deck -- the small paragraph under a numbered heading -- carries
# `keep_with_next` for the same reason the heading does. The heading was already bound to
# the deck and the deck to nothing, so the pair could sit alone at the foot of a column
# with the specimens they introduce overleaf: `critique/c5/orphanheads.py` measured
# `2. Molduras` at y = 553.2 of page 2 with **zero** of its six frames on that page. Bound,
# the chain is heading + deck + the first row of specimens, about 20 of the page's 49
# slots, so it always has somewhere to go.
def section_frames() -> list[tp.Block]:
    frames = []
    for style in FrameStyle:
        svg, dx = _specimen_pair(frame=style)
        frames.append((svg, style.value, "", dx))
    return [
        tp.Heading(kind="head", text="2. Molduras", size=4.2, align="left",
                   space_before=2, label="h2"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="Os seis FrameStyle. O peso de todos vem de uma "
                     "única regra de sistema — largura do tabuleiro sobre 110, ±15 % — "
                     "de modo que o que distingue um estilo do outro é a estrutura, e "
                     "não o peso.",
                     size=2.7, align="left", figurines=False,
                     label="s2"),
        tp.Gallery(kind="gallery", items=frames, per_row=3, space_before=1,
                   label="molduras"),
    ]


def section_indicator() -> list[tp.Block]:
    stms = []
    for stm in SideToMove:
        square = STM_TEXT_SQUARE if stm is SideToMove.TEXT else SPECIMEN_SQUARE
        svg, dx = _specimen_pair(square, coordinates=CoordinateStyle.NONE,
                                 side_to_move=stm)
        stms.append((svg, stm.value, "", dx))
    return [
        tp.Heading(kind="head", text="4. Indicador de lance", size=4.2, align="left",
                   space_before=2, label="h4"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="Os seis indicadores. O de palavras vai num "
                     "tabuleiro maior porque **não é composto abaixo do piso de "
                     "5,5 pt**: a 4 mm de casa ele sairia a 3,4 pt, e o renderizador "
                     "troca-o pelo quadrado em vez de o imprimir ilegível.",
                     size=2.7, align="left", figurines=False,
                     label="s4"),
        tp.Gallery(kind="gallery", items=stms, rows=(3, 2, 1), space_before=1,
                   label="stm"),
    ]


def section_coordinates() -> list[tp.Block]:
    coords = []
    for c in (CoordinateStyle.OUTSIDE, CoordinateStyle.OUTSIDE_RIGHT,
              CoordinateStyle.INSIDE):
        svg, dx = _specimen_pair(COORDINATE_SPECIMEN_SQUARE, FEN_INSIDE, coordinates=c)
        coords.append((svg, c.value, "", dx))
    # The same option on a position that leaves it no room: c1, d1 and f1 carry a rook or
    # a queen, no corner of those squares is free, and the diagram comes back with the
    # labels OUTSIDE rather than with four bitten pieces.
    svg, dx = _specimen_pair(COORDINATE_SPECIMEN_SQUARE, FEN_MARECO,
                             coordinates=CoordinateStyle.INSIDE)
    coords.append((svg, "inside — casa ocupada", "devolvido para fora", dx))
    return [
        tp.Heading(kind="head", text="3. Coordenadas", size=4.2, align="left",
                   space_before=2, label="h3"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="As três colocações. Um rótulo de dentro vai num "
                     "canto **livre** da própria casa, medido contra a silhueta da peça "
                     "que lá está: nunca por cima dela, nunca cortado pela aresta. Numa "
                     "casa sem canto livre — torre ou dama — o diagrama devolve as "
                     "coordenadas para fora, e o quarto espécime mostra isso.",
                     size=2.7, align="left", figurines=False,
                     label="s3"),
        tp.Gallery(kind="gallery", items=coords, per_row=2, space_before=1,
                   label="coordenadas"),
    ]


# --------------------------------------------------------------------------- #
# 3. Marcas
# --------------------------------------------------------------------------- #
def section_marks() -> list[tp.Block]:
    sets = [
        ("setas retas", [Arrow("d1", "d7"), Arrow("g2", "b7"), Arrow("c1", "c5")]),
        ("salto de cavalo", [Arrow("d2", "b3"), Arrow("d2", "f3"), Arrow("d2", "e4")]),
        ("destaques + círculos",
         [SquareHighlight("c5"), SquareHighlight("d5"), CircleMark("b7"),
          CircleMark("g2")]),
        ("misto sobre peças",
         [SquareHighlight("d5"), Arrow("g2", "d5"), CircleMark("d5"),
          Arrow("c1", "c5")]),
    ]
    from caissa.typeset.board_svg import frame_origin

    style = DiagramStyle(font="merida", theme="book", width_mm=62.0,
                         frame=FrameStyle.HAIRLINE)
    dx = frame_origin(style)[0]
    items = [
        (tp.diagram(FEN_MARECO, style, marks=marks), label, "", dx)
        for label, marks in sets
    ]
    return [
        tp.Heading(kind="head", text="5. Marcas", size=4.2, align="left",
                   space_before=2, label="h5"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="Setas, destaques e círculos. A marca passa "
                     "**por baixo** das peças e só a ponta volta por cima, contornada "
                     "na cor da própria casa de destino: é o que deixa uma haste "
                     "atravessar uma peça sem lhe romper o contorno. O recorte branco "
                     "do ciclo 2 fazia o contrário — decapitava os peões de b2 e f2.",
                     size=2.7, align="left", figurines=False,
                     label="s5"),
        tp.Gallery(kind="gallery", items=items, per_row=2, space_before=1,
                   label="marcas"),
    ]


# --------------------------------------------------------------------------- #
# 4. Figurino em texto corrido
# --------------------------------------------------------------------------- #
BODY = (
    "White's plan is straightforward: **13.dxc5** wins a tempo and **14.Nb3!** attacks "
    "the hanging pawns fixed on c5 and d5; __Vitiugov - Bologan__ reached the same "
    "structure by **16.e3+/-**."
)
"""The specimen paragraph, at four sizes.

Cycle 3 set a 362-character paragraph here, which came to 4/4/5/5 lines and made the
section 36 grid slots. The specimen sheet's page holds 49, the marks gallery's second row
takes 18, and the four sizes therefore did not fit together: the sheet shipped 9, 10 and
11 pt on page 6 and 12 pt alone on page 7 -- the same fault Q4 nº 6 names for the 20/40/60/
90 mm series, in the section whose own caption says *9, 10, 11 e 12 pt*. At 186 characters
it is 2/2/3/3 lines, the section is 28 slots, and the series fits under the gallery with
three slots to spare. It still carries everything the section exists to show: figurines in
running text (`13.dxc5`, `14.Nb3!`), a bold run, an italic run, and an evaluation symbol.
"""


def section_figurines() -> list[tp.Block]:
    """Q4 nº 6, second series. The four sizes are ONE object, like `section_sizes`.

    Every block from the heading to the 12 pt line carries ``keep_with_next``, so the
    composer moves the series entire or not at all -- and the gaps inside it are rigid,
    because `compose` makes the gap after a bound block rigid. Cycle 3 had the chain only
    on the size labels, which held a label to its paragraph and let the page break fall
    between two sizes.
    """
    blocks: list[tp.Block] = [
        tp.Heading(kind="head", text="6. Figurino em texto corrido", size=4.2,
                   align="left", space_before=2, label="h6"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="9, 10, 11 e 12 pt, na mesma página. A régua cinza "
                     "**é** a linha de base: o pé da peça tem de tocá-la. O figurino "
                     "também responde ao peso do texto em volta — em contexto negrito "
                     "ele é composto numa variante mais pesada.",
                     size=2.7, align="left", figurines=False,
                     label="s6"),
    ]
    for size_pt in (9, 10, 11, 12):
        blocks.append(
            tp.Paragraph(kind="label", text=f"**{size_pt} pt**", size=2.7, align="left",
                         space_before=1, keep_with_next=True, figurines=False,
                         label=f"fig{size_pt}lbl")
        )
        blocks.append(
            tp.RuledParagraph(kind="body", text=BODY, size=size_pt * 25.4 / 72.0,
                              keep_with_next=True, label=f"fig{size_pt}")
        )
        blocks.append(
            tp.RuledParagraph(kind="body", text="**24.Bxh7+!** e **24...Kxh7 25.Qh5+**",
                              size=size_pt * 25.4 / 72.0, align="left",
                              keep_with_next=size_pt != 12,
                              label=f"fig{size_pt}bold")
        )
    return blocks


def section_piece_by_piece() -> list[tp.Block]:
    specs = verified_specs()
    blocks: list[tp.Block] = [
        tp.Heading(kind="head", text=f"7. Peça a peça — as {len(specs)} famílias "
                   "verificadas", size=4.2, align="left", space_before=2, label="h7"),
        tp.Paragraph(kind="sub", keep_with_next=True,
                     text="Rei, dama, torre, bispo, cavalo e peão, nessa "
                     "ordem, sobre a régua de linha de base, e dois lances compostos. "
                     "Todas as famílias verificadas aparecem aqui — no ciclo 1 a página "
                     "mostrava treze e cortava a décima quarta pela borda.",
                     size=2.7, align="left", figurines=False,
                     label="s7"),
    ]
    for index, spec in enumerate(specs):
        # `rigid_before`, not `keep_with_next`: eighteen rows of the same object must
        # keep one pitch, and the first row has nothing to be rigid in front of.
        blocks.append(tp.PieceRow(kind="pieces", family=spec.key,
                                  rigid_before=index > 0,
                                  label=f"pieces:{spec.key}"))
    return blocks


# --------------------------------------------------------------------------- #
# 5. Tamanhos
# --------------------------------------------------------------------------- #
def section_sizes() -> list[tp.Block]:
    """The four sizes of one theme, in ONE gallery, bound together.

    Cycle 2 built this as two galleries -- 20/40/60 in one and 90 in another -- and the
    flow put them on different pages, twice. The section exists to compare the four; a
    comparison split across a page turn is not one. One `Gallery` with `rows=(3, 1)` and
    `keep_together=True` is the whole fix: the composer now moves the series entire or
    not at all.
    """
    blocks: list[tp.Block] = []
    for number, (theme_key, label) in enumerate(
        (("book", "cinza neutro"), ("hatched", "hachurado")), start=8
    ):
        items = []
        for width in (20, 40, 60, 90):
            style = DiagramStyle(font="merida", theme=theme_key, width_mm=width)
            from caissa.typeset.board_svg import frame_origin

            items.append((tp.diagram(FEN_MARECO, style), f"{width} mm", "",
                          frame_origin(style)[0]))
        blocks += [
            tp.Heading(kind="head", text=f"{number}. Tamanhos — tema “{label}”",
                       size=4.2, align="left", space_before=2,
                       label=f"h{number}{theme_key}"),
            tp.Paragraph(kind="sub", keep_with_next=True,
                         text="20, 40, 60 e 90 mm, na mesma página. O peso "
                         "do traço e o corpo das coordenadas têm de sobreviver aos "
                         "quatro. Abaixo de ≈28 mm as coordenadas são **suprimidas** em "
                         "vez de impressas: 3,9 pt de uma serifada não sobrevive a "
                         "impressão nenhuma, e é o que o ciclo 1 imprimia.",
                         size=2.7, align="left", figurines=False,
                         label=f"s{number}{theme_key}"),
            tp.Gallery(kind="gallery", items=items, rows=(3, 1), space_before=1,
                       keep_together=True, label=f"sizes-{theme_key}"),
        ]
    return blocks


# --------------------------------------------------------------------------- #
# 6. A página de livro
# --------------------------------------------------------------------------- #
# UMA fonte, composta em três temas. No ciclo 1 havia três fontes ligeiramente
# diferentes travestidas de "a mesma página em três temas": uma delas trazia a cabeça
# `14.Nb3!` **duas vezes** (uma na lista da coluna esquerda e outra acrescentada pelo
# parâmetro `third_diagram`), e outra não trazia o terceiro diagrama. O crítico pegou as
# duas coisas com um diff pixel a pixel.
MARECO_RUNNING_HEAD = "Family One – d4 and ...d5"
RIOS_RUNNING_HEAD = "Capítulo 4 — peões pendentes"
"""The running head of each source page, beside the source it belongs to.

Two defects of cycle 5 come from this string having been written out again, by hand, in
the blind harness. `tools/build_blind.py` carried
``"Capitulo 4 - peoes pendentes"`` -- ASCII, in a file whose comments are all written in
Portuguese without accents -- so the page submitted for blind judgement against five
published books printed `peoes`, which is not a Portuguese word, one line above a title
that spells `peões` correctly. The critic found it and said what nothing in the project
could: no check anywhere looked at diacritics. There is one now, in
`typography.missing_diacritics`, and the head lives here so there is one of it.

The dash is the second: the head used a hyphen (an EN DASH after `prepared`) for the same
construction the subtitle sets with an EM DASH -- 20 px against 37 px, measured. Both are
EM DASH now, because `Capítulo 4 — peões pendentes` is a title and its subtitle, not a
range and not a pair of names."""


def book_source_mareco() -> list[dict]:
    return [
        dict(kind="title", text="Sandro Mareco – Christian Toth"),
        dict(kind="centre", text="Osasco 2012"),
        dict(kind="body0", text="**Learning objective:** This game illustrates how the "
             "hanging pawns may be blocked and subsequently attacked."),
        dict(kind="move", text="**1.d4 Nf6 2.c4 e6 3.g3 Bb4+ 4.Bd2 Bxd2+ 5.Nxd2 d5**"),
        dict(kind="body", text="More common is **5...d6** followed by ...e6-e5, "
             "especially since White's knight is on d2."),
        dict(kind="move", text="**6.Bg2 0-0 7.Ngf3 b6 8.0-0 Bb7 9.Rc1 Nbd7 10.cxd5 exd5 "
             "11.Ne5 c5 12.Nxd7 Nxd7 13.dxc5**"),
        dict(kind="body", text="After a careless opening, Black is already in a "
             "difficult position."),
        dict(kind="diagram", fen=FEN_MARECO, caption="After 13.dxc5."),
        dict(kind="move", text="**13...bxc5?!**"),
        dict(kind="body", text="Black obtains a terrible version of the hanging pawns "
             "structure, due to a simple tactical problem."),
        dict(kind="body0", text="Better was: **13...Nxc5 14.Nb3 Ne6 15.Qd2 Qf6 16.e3+/-** "
             "with a pleasant version of an isolani position; compare Vitiugov – "
             "Bologan from the previous chapter."),
        dict(kind="move", text="**14.Nb3!**"),
        dict(kind="body", text="Black cannot maintain his hanging pawns in the ideal "
             "c5-d5 position."),
        dict(kind="diagram", fen=FEN_AFTER_14NB3,
             caption="After 14.Nb3 — the pawns cannot both be held."),
        dict(kind="body", text="**14...c4** runs into **15.Nd4**, and **14...Rc8 "
             "15.Rc2** only prepares to double."),
        dict(kind="centre-bold", text="A sharper example"),
        dict(kind="move", text="**21.Bxh7+!+-**"),
        dict(kind="body", text="Checkmate cannot be avoided."),
        # The one diagram that carries marks, and it carries them on BOTH exporters:
        # this is the LaTeX diagram the critic measured the arrowhead on.
        dict(kind="diagram", fen=FEN_RIOS21, caption="After 21.Bxh7+.",
             marks=[SquareHighlight("h7"), Arrow("g3", "g7")]),
        dict(kind="move", text="**21...Nxh7 22.Bf6 Qxc4**"),
        dict(kind="variation", text="**22...g6 23.Qxh7+! Kxh7 24.Rh3+ Kg8 25.Rh8#**"),
        dict(kind="move", text="**23.Rxg7+ Kf8 24.Qh6 Rec8 25.Rg8+**"),
        dict(kind="variation", text="Or **23...Ne7 24.Bxe7 Rdxe7 25.Qg4+-**."),
        dict(kind="move", text="**1-0**"),
        dict(kind="centre-bold", text="Final remarks"),
        dict(kind="body0", text="Black lost this game in one move, with **17...Nd7**. "
             "After dxe5 the initiative is the only thing worth playing for."),
    ]


def book_source_rios() -> list[dict]:
    """Uma segunda página-fonte, para o conjunto cego pedir páginas diferentes entre si.

    O ciclo 1 pôs três renderizações da MESMA página-fonte no conjunto de sete, e o
    crítico as diferenciou com um diff pixel a pixel antes de olhar para a tipografia.
    """
    return [
        dict(kind="title", text="A estrutura de peões pendentes"),
        dict(kind="centre", text="Capítulo 4 — os planos das brancas"),
        dict(kind="body0", text="**Objetivo:** entender por que os peões pendentes são "
             "ora uma força ora um alvo, e qual é o lance que decide de que lado a "
             "balança cai."),
        dict(kind="body", text="Os peões pendentes em c5 e d5 controlam quatro casas "
             "centrais e prometem a ruptura ...d4. A questão é sempre a mesma: quem "
             "chega primeiro, a ruptura ou o bloqueio."),
        dict(kind="body", text="A resposta depende de uma só casa. Enquanto as brancas "
             "não puserem uma peça em b3 ou d4, o par de peões avança; posto o bloqueio, "
             "os mesmos dois peões deixam de ser uma ameaça e passam a ser duas "
             "fraquezas fixas, que não se defendem uma à outra."),
        dict(kind="diagram", fen=FEN_AFTER_14NB3,
             caption="O bloqueio já está em b3."),
        dict(kind="move", text="**14.Nb3! Qc7 15.Qd2 Rfd8 16.Rfd1**"),
        dict(kind="body", text="As brancas dobram e o peão de d5 deixa de ser uma "
             "ameaça para virar uma fraqueza."),
        dict(kind="variation", text="**16...d4 17.Nxc5 dxc3 18.Nxb7**"),
        dict(kind="body0", text="Repare que a dama branca em d2 cumpre duas funções: "
             "sustenta o cavalo de b3 e prepara a torre de d1. É a economia de meios "
             "que distingue o plano correto do plano plausível."),
        dict(kind="move", text="**16...Ne5 17.Nxc5 Bxc5 18.Rxc5**"),
        dict(kind="body", text="E as brancas ganham o peão de d5 no lance seguinte."),
        dict(kind="diagram", fen=FEN_RIOS21,
             caption="A mesma ideia, um ataque adiante."),
        dict(kind="move", text="**21.Bxh7+! Kxh7 22.Qh5+ Kg8 23.Rg3**"),
        dict(kind="body", text="O ataque só é possível porque as pretas gastaram tempo "
             "defendendo os peões pendentes em vez de completar o desenvolvimento."),
        dict(kind="body0", text="O mesmo motivo aparece com a dama em h5 e a torre "
             "em g3: duas peças contra o rei, e as pretas com uma peça a três lances "
             "do flanco onde a partida se decide."),
        dict(kind="diagram", fen=FEN_MARECO,
             caption="A posição de partida da estrutura."),
        dict(kind="move", text="**13...bxc5?! 14.Nb3!**"),
        dict(kind="body", text="Comparar as duas capturas é o exercício desta "
             "página: **13...Nxc5** deixa um isolado; **13...bxc5** deixa dois peões "
             "que as brancas bloqueiam de imediato."),
        dict(kind="centre-bold", text="Resumo"),
        dict(kind="body0", text="Bloqueie primeiro, ataque depois: **Nb3** e **Rfd1** "
             "custam dois lances e valem a partida."),
    ]


def book_blocks(source: list[dict], language: str = "en", *,
                diagram_theme: str = "hatched", diagram_font: str = "merida",
                column_width: float = 63.45) -> list[tp.Block]:
    """Traduz a fonte para blocos do compositor. Independente do tema."""
    size = BODY_PT * 25.4 / 72.0
    indent = size * 1.1
    blocks: list[tp.Block] = []
    for index, item in enumerate(source):
        kind = item["kind"]
        label = f"{kind}:{index}"
        if kind == "diagram":
            blocks.append(tp.DiagramBlock(
                kind="diagram", label=label, fen=item["fen"],
                marks=item.get("marks", ()),
                caption=item.get("caption", ""), caption_size=size * 0.82,
                # 0.90 of the measure: the finished frame comes to 51.4 mm against the
                # reference page's 52.2 mm (measured by ink extent at 300 DPI), and the
                # diagram then costs a whole 18 grid slots instead of 18-and-a-bit --
                # which is what lets the column pack to the foot without feathering.
                style=DiagramStyle(font=diagram_font, theme=diagram_theme,
                                   width_mm=column_width * 0.90, frame=FrameStyle.RULE,
                                   coordinates=CoordinateStyle.OUTSIDE),
            ))
        elif kind == "title":
            blocks.append(tp.Heading(kind="title", label=label, text=item["text"],
                                     size=size * 1.30, align="centre", rule=True))
        elif kind == "centre":
            # The venue line belongs to the game heading: name, Scotch rule, venue are
            # ONE object. Cycle 2 gave it `space_before=1` and let the vertical
            # justification feather that gap, and the critic measured 9.7 mm of white
            # between the rule and `Osasco 2012` against 4.0 mm in the Quality Chess
            # page that sets the same construction. `space_before=0` and the rigid gap
            # that follows a heading (see `compose`) hold it at one leading.
            blocks.append(tp.Paragraph(kind="centre", label=label, text=item["text"],
                                       align="centre", space_before=0,
                                       keep_with_next=True, figurines=False))
        elif kind == "centre-bold":
            # `cross` and not `centre`: a cross-head and a venue line are centred the
            # same way and are not the same object, and the composer knows a block only
            # by its kind. Under one name their gaps land in one `gap_class` -- the
            # venue's rigid one slot and the cross-head's rigid zero -- and any audit of
            # "equivalent elements, equal space" reports a class with two heights that
            # nothing can ever even out, because both gaps are rigid by design.
            blocks.append(tp.Paragraph(kind="cross", label=label, text=item["text"],
                                       align="centre", weight="bold", space_before=1,
                                       keep_with_next=True, figurines=False))
        elif kind == "move":
            blocks.append(tp.Paragraph(kind="move", label=label, text=item["text"]))
        elif kind == "body0":
            # A flush paragraph after the game head needs a line of air, or the venue
            # line and the learning objective run together. The gap is rigid, so the
            # vertical justification cannot grow it (see `compose`).
            previous = source[index - 1]["kind"] if index else ""
            after_head = previous == "centre"
            # A paragraph opens flush only after something DISPLAYED -- a title, a venue
            # line, a cross-head, a diagram. After another paragraph it opens indented,
            # like every other paragraph on the page, because the indent is the only mark
            # that says a new one began. Cycle 5 set three of these flush in the middle
            # of running prose: `A questao e sempre a mesma:` began at the margin on the
            # line after a line that reached the measure, and the critic recorded a page
            # with three different paragraph-separation styles on which "the reader
            # cannot tell where a paragraph ends".
            displayed = previous in ("title", "centre", "centre-bold", "diagram")
            blocks.append(tp.Paragraph(
                kind="body0", label=label, text=item["text"],
                first_indent=0.0 if displayed else indent,
                space_before=1 if after_head else 0))
        elif kind == "variation":
            # A sub-variation is an indented BLOCK, so its continuation lines keep the
            # indent. Cycle 2 set it as a paragraph with a first-line indent and the
            # continuation came back out to 0.00 pt, where a chess reader reads it as a
            # new main-line move.
            blocks.append(tp.Paragraph(kind="variation", label=label, text=item["text"],
                                       block_indent=indent))
        else:
            blocks.append(tp.Paragraph(kind="body", label=label, text=item["text"],
                                       first_indent=indent))
    return blocks


def compose_book_page(theme_key: str, *, source=None, page_number: int = 44,
                      running_head: str = "Family One – d4 and ...d5",
                      recto_running_head: str | None = None,
                      different_odd_even: bool = False,
                      mirror_margins: bool = True,
                      repeat: int = 1,
                      diagram_theme: str | None = None,
                      language: str = "en",
                      equalise_budget: int = tp.MAX_EQUALISE_SPREAD_SLOTS,
                      ) -> tp.Composition:
    """Set one book page.

    `mirror_margins` and `different_odd_even` are the two fields that
    `caissa.core.model.blocks` declares and that no composer read until cycle 9 --
    `PageGeometry.mirror_margins` and `SectionBreak.different_odd_even`. The first
    decides the side of the outer margin **and of the folio**; the second decides
    whether a recto carries a different running head from the facing verso.

    `mirror_margins=False` is the liveness handle: it forces the folio to one side,
    which is exactly the cycle-8 defect, and the parity test must fail against it.
    """
    theme = get_theme(theme_key)
    ink = "#E8E8E4" if theme.is_dark() else "#000000"
    geometry = book_geometry(page_number, mirror_margins=mirror_margins)
    font, metrics = tp.metrics_for("merida")
    size = BODY_PT * 25.4 / 72.0
    style = tp.TextStyle(size=size, leading=size * 1.21, metrics=metrics, font=font,
                         ink=ink, language=language, hyphenator=book_hyphenator(language))
    head = tp.prepared(running_head, language)
    recto_head = tp.prepared(recto_running_head or running_head, language)

    def decorate(canvas: tp.Canvas, index: int) -> None:
        # R5, the cycle-8 blocker. The folio goes to the OUTER edge, which swaps sides
        # with the parity of the number the reader sees: 44 is a verso and takes the
        # left, 45 is a recto and takes the right. Cycle 8 wrote every folio at
        # `geometry.outer` -- 14.0 mm from the left on all three -- so page 45 carried
        # its number 129.6 mm from where a bound book puts it, against the spine.
        canvas.text(geometry.outer_x(index), geometry.top - 6,
                    str(geometry.folio(index)), size=3.3, fill=ink,
                    anchor=geometry.outer_anchor(index))
        text = recto_head if (different_odd_even and geometry.is_recto(index)) else head
        canvas.text(TRIM_W / 2, geometry.top - 6, text, size=3.3, fill=ink,
                    anchor="middle")

    blocks = book_blocks(source or book_source_mareco(), language=language,
                         diagram_theme=diagram_theme or theme_key,
                         column_width=geometry.column_width)
    return tp.compose(
        blocks * max(1, repeat),
        geometry=geometry,
        style=style,
        background=theme.page,
        decorate=decorate,
        equalise_budget=equalise_budget,
    )


BOOK_RUN_FIRST_FOLIO = 44
BOOK_RUN_PAGES = 4


def compose_book_run(pages: int = BOOK_RUN_PAGES,
                     first_folio: int = BOOK_RUN_FIRST_FOLIO,
                     *, mirror_margins: bool = True,
                     **kwargs) -> tp.Composition:
    """A run of at least `pages` book pages, numbered from `first_folio`.

    The critique of cycle 8 asks for the folio to be checked "nas três páginas de livro
    da folha entregue (44, 45, 46) **e numa corrida de pelo menos quatro páginas gerada
    de propósito**". The three pages of the sheet are three separate one-page
    compositions, so they only ever exercise `decorate(canvas, 0)`; this exercises
    `decorate(canvas, index)` for index 0..n inside ONE composition, which is where a
    multi-page book actually lives.

    The copy is the English source repeated -- this is a geometry artefact, not a read.
    """
    repeat = max(1, pages)
    for _ in range(4):
        composition = compose_book_page(
            "book", page_number=first_folio, diagram_theme="hatched",
            mirror_margins=mirror_margins, repeat=repeat, **kwargs)
        if len(composition.pages) >= pages:
            return composition
        repeat += max(1, pages - len(composition.pages))
    return composition


# --------------------------------------------------------------------------- #
def build(verbose: bool = False) -> list[str]:
    pages: list[str] = []
    style = gallery_style("pt")
    geometry = gallery_geometry()

    sections = (
        section_families()
        + section_frames()
        + section_coordinates()
        + section_indicator()
        + section_marks()
        + section_figurines()
        + section_piece_by_piece()
        + section_sizes()
    )
    # A specimen sheet may open its gaps wider than a book page -- its objects are
    # diagrams 40 to 90 mm tall -- but not without a ceiling: `SPECIMEN_GAP_SLOTS` holds
    # any gap to 3 slots, which is 3.4 leadings of white against the 4 the critic set.
    # The book page keeps the strict book value of 1.
    gallery = tp.compose(sections, geometry=geometry, style=style,
                         decorate=_folio(1), balance_last=False, max_feather=2,
                         max_gap_slots=tp.SPECIMEN_GAP_SLOTS)
    pages += gallery.pages

    books = []
    for theme_key, diagram_theme, number in (
        ("book", "hatched", 44), ("book", "book", 45), ("dark", "dark", 46)
    ):
        composition = compose_book_page(theme_key, diagram_theme=diagram_theme,
                                        page_number=number)
        books.append(composition)
        pages += composition.pages

    if verbose:
        print(f"galeria: {len(gallery.pages)} paginas, "
              f"{len(gallery.blocks)} blocos emitidos")
        for name, composition in zip(("hachurado", "cinza", "escuro"), books):
            feet = composition.column_feet
            spread = composition.foot_spread_mm
            print(f"livro/{name}: {len(composition.pages)} pagina(s), "
                  f"{len(composition.blocks)} blocos, pes {feet}, "
                  f"desnivel {spread:.3f} mm, residuo {composition.residual}")
        first = books[0].blocks
        for name, composition in zip(("cinza", "escuro"), books[1:]):
            same = composition.blocks == first
            print(f"mesma lista de blocos que o hachurado ({name}): {same}")
    return pages


def build_rios(verbose: bool = False) -> list[str]:
    """The Portuguese book page, on its own, as a delivered artefact.

    The cycle-5 critique asks for two of its numbers on *this* page and not only on the
    three that go into `proofsheet.pdf`: R1's *"nas tres paginas de livro **e** numa
    pagina composta a partir de `book_source_rios`"*, and R4's `Rfd1`, which is a move
    this source plays and the English one does not. Until now the only rendering of it
    lived inside the critic's blind set, where the front cannot measure it and a reader
    cannot look at it.
    """
    composition = compose_book_page(
        "book", source=book_source_rios(), diagram_theme="hatched", page_number=44,
        running_head=RIOS_RUNNING_HEAD, language="pt",
    )
    if verbose:
        print(f"livro/rios: {len(composition.pages)} pagina(s), "
              f"{len(composition.blocks)} blocos, pes {composition.column_feet}, "
              f"desnivel {composition.foot_spread_mm:.3f} mm, "
              f"residuo {composition.residual}")
    return composition.pages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", action="store_true", help="tambem escreve um PNG por pagina")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--out", default=str(OUT / "proofsheet.pdf"))
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    pages = build(verbose=True)
    path = tp.pages_to_pdf(pages, args.out)
    print(f"{len(pages)} paginas -> {path}")

    rios_path = tp.pages_to_pdf(build_rios(verbose=True),
                                str(Path(args.out).with_name("proofsheet_rios.pdf")))
    print(f"1 pagina -> {rios_path}")

    # The purpose-built run the cycle-8 critique asks for beside the three book pages of
    # the sheet: four consecutive folios inside ONE composition, so the folio is seen to
    # alternate over a run and not only between three separate one-page compositions.
    run = compose_book_run()
    run_path = tp.pages_to_pdf(run.pages,
                               str(Path(args.out).with_name("proofsheet_run.pdf")))
    print(f"{len(run.pages)} paginas (corrida {BOOK_RUN_FIRST_FOLIO}-"
          f"{BOOK_RUN_FIRST_FOLIO + len(run.pages) - 1}) -> {run_path}")

    if args.png:
        import pymupdf

        doc = pymupdf.open(path)
        png_dir = OUT / "proofsheet_png"
        png_dir.mkdir(exist_ok=True)
        for old in png_dir.glob("page_*.png"):
            old.unlink()
        for index, page in enumerate(doc):
            out = png_dir / f"page_{index + 1:02d}.png"
            page.get_pixmap(dpi=args.dpi).save(str(out))
            print("  ", out)
        doc.close()
        # The Portuguese page too, and by the same command: a page nobody can look at is
        # a page nobody looks at, and this one is the one the blind set submits.
        rios_doc = pymupdf.open(rios_path)
        out = png_dir / "rios_01.png"
        rios_doc[0].get_pixmap(dpi=args.dpi).save(str(out))
        rios_doc.close()
        print("  ", out)
        # And the folio run, for the same reason: the parity is a thing you look at.
        run_doc = pymupdf.open(run_path)
        for old in png_dir.glob("run_*.png"):
            old.unlink()
        for index, page in enumerate(run_doc):
            out = png_dir / f"run_{BOOK_RUN_FIRST_FOLIO + index:02d}.png"
            page.get_pixmap(dpi=args.dpi).save(str(out))
            print("  ", out)
        run_doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
