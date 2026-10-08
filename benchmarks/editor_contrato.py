r"""O contrato de marcação e a política de CSS, conferidos — o portão do passo H3.

`docs/MARKUP_CAISSA.md` é o contrato; as fixtures em `tests/fixtures/editor/` são a prova dele.
Este instrumento confere, sem implementar nada do que o H5 vai construir:

1. **A cobertura:** cada linha da S4 (`LINHAS_DO_S4`) tem a fixture dela, e o §11 do contrato
   nomeia a mesma — 100 %.
2. **O `CB validate`** (`..\Sigil-master\...\sigil_chess\validate.py`, no `sys.path` só aqui) sobre
   as fixtures do contrato e as combinações, com as imagens que o livro leva: **0 erro**, e
   **nada que o CB confunda sem acusar** (o §10 do contrato): nenhum elemento que uma expressão
   do `validate.py` case sem ter a classe dela, e nenhum `cb-move` sem `data-fen`, que ele pula.
   As extensões do H5 (o §12 do contrato) têm as fixtures `extensoes_*.xhtml`, que o
   `--regerar-extensoes` escreve pelo escritor legível, e que entram na cobertura e no CB.
3. **A fixture legada** (`legado_xhtml_builder.xhtml`, saída do exportador HTML de hoje, no perfil
   de máquina) é lida pelo leitor atual (`read_html_text`) e traz o título, o parágrafo, o
   diagrama e a partida.
4. **As fixtures do mapa de estilo:** cada `.css` tem o `.json` com o resultado esperado na forma do
   §9 do contrato; as positivas cobrem cada propriedade do mapa com dois valores e não avisam; as
   negativas avisam `css-fora-do-mapa` com seletor, propriedade, arquivo e linha.
5. **As fixtures douradas do sidecar** (spec Apêndice C) existem, assinadas pelo crítico no
   `LEIAME.md`, com o SHA-256 igual ao do relatório (§H3 do `EDITOR_HTML_CSS_REPORT.md`).

**Sabotagens:** `--sabotar sem_fen` — a negativa `contrato_negativas/negativa_sem_fen.xhtml` (um
diagrama sem `data-fen`) entra no conjunto limpo; o CB acusa, e o portão reprova. `--sabotar
confundida` — a negativa `negativa_classe_confundida.xhtml` (a classe `cb-move-context` da v1 do
contrato e um `cb-move` sem `data-fen`) entra; o CB **não** acusa nada, e o portão reprova pela
conta do que ele confunde.

Uso::

    & $PY benchmarks\editor_contrato.py --saida benchmarks\reports\editor\h3\1
    & $PY benchmarks\editor_contrato.py --regerar-legada
    & $PY benchmarks\editor_contrato.py --regerar-extensoes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

FIXTURES = RAIZ / "tests" / "fixtures" / "editor"
CONTRATO = FIXTURES / "contrato"
NEGATIVAS = FIXTURES / "contrato_negativas"
CSS = FIXTURES / "css"
SIDECAR = FIXTURES / "sidecar"
DOCUMENTO = RAIZ / "docs" / "MARKUP_CAISSA.md"
RELATORIO = RAIZ / "docs" / "quality" / "EDITOR_HTML_CSS_REPORT.md"
SABOTAGENS = ("sem_fen", "confundida")

#: Cada linha da S4 (spec §5.2) e a fixture dela — a tabela do §11 do contrato.
LINHAS_DO_S4: dict[str, str] = {
    "Heading(level)": "titulo.xhtml",
    'Paragraph(style=None)': "paragrafo.xhtml",
    'Paragraph(style="Movetext")': "paragrafo_movetext.xhtml",
    'Paragraph(style="Caption"|"Footnote"|X)': "paragrafo_estilos.xhtml",
    "Emphasis…Subscript": "formatacao.xhtml",
    "RunProps.language": "lingua.xhtml",
    "Link/Anchor/NoteRef": "links_ancoras_notas.xhtml",
    "Diagram": "diagrama.xhtml",
    "GameScore/MoveNode/Move": "partida.xhtml",
    "PieceGlyph": "figurina.xhtml",
    "NagSymbol": "nag.xhtml",
    "página do PDF": "pagina.xhtml",
    "RawPassthrough/RawInline": "bruto.xhtml",
    "html_attributes": "atributos.xhtml",
}
COMBINACOES = ("combinacao_capitulo.xhtml", "combinacao_partida_com_diagrama.xhtml")
#: As extensões do perfil legível (o §12 do contrato, passo H5).
EXTENSOES = ("extensoes_blocos.xhtml", "extensoes_texto.xhtml", "extensoes_xadrez.xhtml")
LEGADA = "legado_xhtml_builder.xhtml"
SIDECAR_DOURADAS = ("v2_completo.jsonl", "v1_de_hoje.jsonl", "v1_migrado_esperado.jsonl")
ASSINATURA = "escrito pelo crítico (Codex)"

#: As propriedades do mapa de estilo (§9 do contrato), cada uma com dois valores nas positivas.
PROPRIEDADES_DO_MAPA = (
    "font-family", "font-size", "font-weight", "font-style", "font-variant", "color",
    "background-color", "text-align", "text-indent", "margin-top", "margin-right",
    "margin-bottom", "margin-left", "line-height", "letter-spacing", "text-transform",
    "break-before", "widows", "orphans",
)
CAMPOS_DO_AVISO = ("codigo", "seletor", "propriedade", "arquivo", "linha")


def _principal() -> Path:
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def pasta_do_cb() -> Path:
    """O `python3lib` do Sigil, onde mora o pacote `sigil_chess` (o CB)."""
    return _principal().parent / "Sigil-master" / "src" / "Resource_Files" / "python3lib"


# --------------------------------------------------------------------------- #
# As conferências
# --------------------------------------------------------------------------- #


def conferir_cobertura() -> list[str]:
    """Cada linha da S4 com a fixture, e o §11 do contrato nomeando a mesma."""
    faltas = [f"a linha «{linha}» da S4 não tem a fixture {nome}"
              for linha, nome in LINHAS_DO_S4.items() if not (CONTRATO / nome).is_file()]
    faltas += [f"a combinação {nome} não existe" for nome in COMBINACOES
               if not (CONTRATO / nome).is_file()]
    faltas += [f"a fixture de extensão {nome} não existe" for nome in EXTENSOES
               if not (CONTRATO / nome).is_file()]
    texto = DOCUMENTO.read_text(encoding="utf-8") if DOCUMENTO.is_file() else ""
    secao = texto.split("## 11.", 1)[-1] if "## 11." in texto else ""
    faltas += [f"o §11 do contrato não nomeia {nome}"
               for nome in (*LINHAS_DO_S4.values(), *COMBINACOES, *EXTENSOES, LEGADA)
               if f"`{nome}`" not in secao]
    return faltas


def documentos_do_livro(nomes: list[Path]) -> tuple[list[dict[str, str]], list[str]]:
    """As fixtures como um livro do EPUB: `Text/<nome>`, com as imagens e a folha que ele leva."""
    documentos = [{"bookpath": f"Text/{p.name}", "text": p.read_text(encoding="utf-8")}
                  for p in nomes]
    arquivos = [d["bookpath"] for d in documentos]
    arquivos += [f"Images/{p.name}" for p in sorted((CONTRATO / "Images").glob("*.svg"))]
    arquivos += [f"Styles/{p.name}" for p in sorted((CONTRATO / "Styles").glob("*.css"))]
    return documentos, arquivos


def validar_no_cb(nomes: list[Path]) -> dict[str, Any]:
    cb = pasta_do_cb()
    if str(cb) not in sys.path:
        sys.path.insert(0, str(cb))
    import sigil_chess.validate as validador

    documentos, arquivos = documentos_do_livro(nomes)
    relatorio = validador.validate_book(documentos, files=arquivos).to_dict()
    # O que o CB toma errado sem acusar (MARKUP §10), e o «0 erro» não diria: o elemento que uma
    # expressão dele casa sem ter a classe dela (o hífen é fronteira de palavra: um
    # `span.cb-move-x` seria lido como lance), e o `cb-move` sem `data-fen`, que ele pula como
    # anterior ao contrato.
    confundidos = []
    for documento in documentos:
        for expressao, classe in MARCACOES_DO_CB:
            for casado in getattr(validador, expressao).finditer(documento["text"]):
                classes = validador._attributes(casado.group("attrs")).get("class", "").split()
                if classe not in classes:
                    confundidos.append(f"{documento['bookpath']}: «{' '.join(classes)}» lido "
                                       f"como {classe}")
    relatorio["confundidos"] = confundidos
    relatorio["pulados"] = [
        f"{d['bookpath']}: {m.san} sem data-fen" for d in documentos
        for m in validador._moves_in(d["text"])
        if "cb-move" in m.attrs.get("class", "").split() and not m.attrs.get("data-fen")]
    return relatorio


MARCACOES_DO_CB = (("_MOVE_OPEN_RE", "cb-move"), ("_LINE_RE", "cb-line"),
                   ("_GAME_RE", "cb-game"), ("_DIAGRAM_RE", "cb-diagram"))
"""As marcações que o `validate.py` do CB acha por expressão, e a classe que cada uma tem de ter."""


def conferir_legada() -> list[str]:
    """O leitor de hoje lê a fixture legada e acha o título, o parágrafo, o diagrama e a partida."""
    from caissa.core.model import Diagram, Heading, Paragraph
    from caissa.core.model.visitor import walk
    from caissa.export.html import read_html_text

    arquivo = CONTRATO / LEGADA
    if not arquivo.is_file():
        return [f"a fixture legada {LEGADA} não existe (rode --regerar-legada)"]
    try:
        documento = read_html_text(arquivo.read_text(encoding="utf-8"))
    except Exception as falha:  # noqa: BLE001 - o leitor não pode derrubar o portão
        return [f"o leitor atual não lê a fixture legada: {type(falha).__name__}: {falha}"]
    tipos = {type(no).__name__ for _, no in walk(documento)}
    esperados = {Heading.__name__, Paragraph.__name__, Diagram.__name__, "GameScore"}
    return [f"a fixture legada relida não tem {nome}" for nome in sorted(esperados - tipos)]


def _aviso_valido(aviso: Any, arquivo: str) -> bool:
    return (isinstance(aviso, dict) and set(aviso) == set(CAMPOS_DO_AVISO)
            and aviso["codigo"] == "css-fora-do-mapa" and aviso["arquivo"] == arquivo
            and isinstance(aviso["seletor"], str) and aviso["seletor"]
            and isinstance(aviso["propriedade"], str)
            and type(aviso["linha"]) is int and aviso["linha"] >= 1)


def conferir_css() -> tuple[list[str], dict[str, int]]:
    """Cada fixture do mapa com o resultado declarado, na forma do §9 do contrato."""
    faltas: list[str] = []
    valores: dict[str, set[str]] = {p: set() for p in PROPRIEDADES_DO_MAPA}
    contagem = {"positivas": 0, "negativas": 0}
    for pasta, tipo in (("mapa_positivo", "positivas"), ("mapa_negativo", "negativas")):
        for folha in sorted((CSS / pasta).glob("*.css")):
            esperado_arquivo = folha.with_suffix(".json")
            if not esperado_arquivo.is_file():
                faltas.append(f"{pasta}/{folha.name} sem o resultado esperado (.json)")
                continue
            esperado = json.loads(esperado_arquivo.read_text(encoding="utf-8"))
            estilos, avisos = esperado.get("estilos"), esperado.get("avisos")
            if not (isinstance(estilos, dict) and isinstance(avisos, list)
                    and set(esperado) == {"estilos", "avisos"}
                    and all(isinstance(v, dict) and all(isinstance(x, str) for x in v.values())
                            for v in estilos.values())):
                faltas.append(f"{pasta}/{esperado_arquivo.name} fora da forma do §9")
                continue
            if not all(_aviso_valido(a, folha.name) for a in avisos):
                faltas.append(f"{pasta}/{esperado_arquivo.name}: aviso fora da forma do §9")
            if tipo == "positivas" and avisos:
                faltas.append(f"{pasta}/{folha.name}: a positiva declara aviso")
            if tipo == "negativas" and not avisos:
                faltas.append(f"{pasta}/{folha.name}: a negativa não declara aviso")
            contagem[tipo] += 1
            if tipo == "positivas":
                for estilo in estilos.values():
                    for propriedade, valor in estilo.items():
                        if propriedade in valores:
                            valores[propriedade].add(valor)
    faltas += [f"a propriedade {p} do mapa tem {len(v)} valor(es) nas positivas (mínimo 2)"
               for p, v in valores.items() if len(v) < 2]
    return faltas, contagem


def _hashes_do_relatorio() -> dict[str, str]:
    """Os SHA-256 que o relatório do H3 registrou: `` `nome.jsonl` `` e o hash na mesma linha."""
    if not RELATORIO.is_file():
        return {}
    texto = RELATORIO.read_text(encoding="utf-8")
    secao = texto.split("## H3", 1)[-1].split("\n## ", 1)[0] if "## H3" in texto else ""
    achados = {}
    for nome in SIDECAR_DOURADAS:
        casado = re.search(rf"`{re.escape(nome)}`[^\n]*?`([0-9a-f]{{64}})`", secao)
        if casado:
            achados[nome] = casado.group(1)
    return achados


def conferir_sidecar() -> tuple[list[str], dict[str, str]]:
    faltas: list[str] = []
    hashes: dict[str, str] = {}
    for nome in SIDECAR_DOURADAS:
        arquivo = SIDECAR / nome
        if not arquivo.is_file():
            faltas.append(f"a fixture dourada do sidecar {nome} não existe")
            continue
        hashes[nome] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    leiame = SIDECAR / "LEIAME.md"
    if not leiame.is_file() or ASSINATURA not in leiame.read_text(encoding="utf-8"):
        faltas.append("as fixtures do sidecar não estão assinadas pelo crítico (LEIAME.md)")
    registrados = _hashes_do_relatorio()
    for nome, valor in hashes.items():
        if registrados.get(nome) != valor:
            faltas.append(f"o SHA-256 de {nome} ({valor[:12]}…) não é o do relatório do H3 "
                          f"({(registrados.get(nome) or 'ausente')[:12]})")
    return faltas, hashes


# --------------------------------------------------------------------------- #
# A fixture legada
# --------------------------------------------------------------------------- #


def regerar_legada() -> Path:
    """A fixture legada: um documento pequeno pelo exportador HTML de hoje (perfil de máquina)."""
    import tempfile

    from caissa.core.model import Diagram, Document, Heading, Paragraph, Text
    from caissa.export import export
    from caissa.export.base import ExportOptions
    from caissa.export.text import game_from_pgn

    partida = game_from_pgn('[White "Carlsen"]\n[Black "Caruana"]\n[Result "1-0"]\n\n'
                            "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0\n")
    documento = Document(body=(
        Heading(level=1, content=(Text(content="Capítulo legado"),)),
        Paragraph(content=(Text(content="Um parágrafo do perfil de máquina."),)),
        Diagram(fen="6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", stipulation="Mate em 1"),
        partida,
    ))
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / "legado.xhtml"
        export(documento, destino, "html", options=ExportOptions(embed_ir=False))
        texto = destino.read_text(encoding="utf-8")
    alvo = CONTRATO / LEGADA
    alvo.write_text(texto, encoding="utf-8", newline="\n")
    return alvo


# --------------------------------------------------------------------------- #
# As extensões do perfil legível (o §12 do contrato)
# --------------------------------------------------------------------------- #

_INICIO = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_DEPOIS_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
_DEPOIS_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
_REIS = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def _extensoes_blocos() -> tuple[Any, ...]:
    from caissa.core.model import (
        Alignment,
        Callout,
        CalloutKind,
        CodeBlock,
        Figure,
        FigurePlacement,
        Footnote,
        Group,
        GroupRole,
        Heading,
        ImageBlock,
        ListBlock,
        ListItem,
        ListMarkerStyle,
        MathBlock,
        Measure,
        NumberingRef,
        PageGeometry,
        Paragraph,
        RawPassthrough,
        SectionBreak,
        SectionBreakKind,
        Table,
        TableCell,
        TableOfContents,
        TableRow,
        Text,
        ThematicBreak,
    )
    from caissa.core.model.blocks import ListKind
    from caissa.core.model.props import LengthUnit

    def p(texto: str) -> Paragraph:
        return Paragraph(content=(Text(content=texto),))

    def celula(texto: str, *, cabeca: bool = False) -> TableCell:
        return TableCell(content=(p(texto),), is_header=cabeca)

    return (
        Heading(level=2, anchor="cap-2", numbering_text="2", toc_text="Capítulo",
                list_in_toc=False, numbering=NumberingRef(definition="Titulo1", level=0),
                content=(Text(content="Um capítulo com a entrada do sumário própria"),)),
        Heading(level=7, content=(Text(content="Um nível abaixo do h6"),)),
        ListBlock(kind=ListKind.ORDERED, start=3, marker_style=ListMarkerStyle.LOWER_ROMAN,
                  tight=True, items=(ListItem(content=(p("começa no cinco"),),
                                              start_override=5),
                                     ListItem(content=(p("feito"),), checked=True))),
        ListBlock(marker_style=ListMarkerStyle.DASH, items=(
            ListItem(term=(Text(content="termo"),), content=(p("com termo"),)),
            ListItem(content=(p("por fazer"),), checked=False, marker_override="→"))),
        ListBlock(kind=ListKind.DEFINITION, items=(
            ListItem(term=(Text(content="Zugzwang"),),
                     content=(p("a obrigação de jogar"),), start_override=2),)),
        Table(caption=(Text(content="Resultados"),), caption_above=True, number=4,
              width=Measure(value=80, unit=LengthUnit.PERCENT), alignment=Alignment.CENTER,
              repeat_header=False, summary="o placar", header_row_count=1, footer_row_count=1,
              rows=(TableRow(cells=(celula("Jogador", cabeca=True),
                                    celula("Pontos", cabeca=True))),
                    TableRow(cells=(celula("Carlsen", cabeca=True), celula("7")),
                             height=Measure(value=12, unit=LengthUnit.MM)),
                    TableRow(cells=(celula("Total"), celula("7")), keep_together=True))),
        ImageBlock(resource="figura.svg", alt_text="Uma figura", title="A figura de teste",
                   alignment=Alignment.RIGHT, crop=(0.1, 0.0, 0.1, 0.0)),
        Figure(content=(p("o conteúdo da figura"),), caption=(Text(content="A legenda"),),
               caption_above=True, number=2, label="Figura 2",
               placement=FigurePlacement.TOP, alt_text="Uma figura com legenda"),
        Footnote(ref="nota-1", marker="*", content=(p("A nota."),)),
        Callout(kind=CalloutKind.TIP, title=(Text(content="Dica"),),
                content=(p("Recolhido."),), collapsed=True),
        CodeBlock(language="pgn", text="1. e4 e5", show_line_numbers=True),
        MathBlock(latex="x^2", display=False, numbered=True, label="eq-1"),
        SectionBreak(kind=SectionBreakKind.ODD_PAGE, header_text=(Text(content="Cabeço"),),
                     footer_text=(Text(content="Rodapé"),), different_first_page=True,
                     page_number_start=1, page_number_format="lower-roman",
                     geometry=PageGeometry(width=Measure(value=148, unit=LengthUnit.MM),
                                           height=Measure(value=210, unit=LengthUnit.MM))),
        ThematicBreak(ornament="❦"),
        Group(role=GroupRole.EXERCISE_SET, title=(Text(content="Exercícios"),), columns=2,
              content=(p("Um exercício."),)),
        TableOfContents(title=(Text(content="Sumário"),), show_page_numbers=False,
                        leader=False, scope="document"),
        RawPassthrough(format="xhtml", text="<p>um parágrafo guardado como bruto</p>"),
    )


def _extensoes_texto() -> tuple[Any, ...]:
    from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle, PieceType
    from caissa.core.model import (
        Anchor,
        Emphasis,
        ImageInline,
        IndexEntry,
        InlineDiagram,
        Link,
        LinkKind,
        Mark,
        MarkKind,
        MathInline,
        Measure,
        Move,
        NoteRef,
        Paragraph,
        PieceGlyph,
        RawInline,
        RunProps,
        Span,
        Text,
    )
    from caissa.core.model.props import LengthUnit

    return (
        Paragraph(content=(
            Text(content="Um trecho com estilo e língua",
                 props=RunProps(style="Lance", language="en")),
            Text(content=", um "),
            Span(props=RunProps(language="de"), content=(
                Text(content="Zwischenzug"), Emphasis(content=(Text(content=" (intermédio)"),)))),
            Text(content=", "),
            Link(target="capitulo-2.xhtml", kind=LinkKind.INTERNAL, tooltip="Vai ao capítulo",
                 title="cap2", content=(
                     Text(content="o capítulo "),
                     Link(target="https://exemplo.org", content=(Text(content="e o site"),)))),
            Text(content=", as notas"),
            NoteRef(ref="nota-1", marker=""),
            NoteRef(ref="nota-2"),
            Anchor(name="aqui", title="Um ponto do texto"),
            IndexEntry(terms=("Finais", "Torre"), sort_key="torre", see_also=("Peões",),
                       primary=True),
            Text(content=" e uma posição "),
            InlineDiagram(fen=_REIS, size=Measure(value=2, unit=LengthUnit.EM),
                          marks=(Mark(kind=MarkKind.CIRCLE, squares=("e4",)),),
                          style="Miniatura"),
            RawInline(format="latex", text=r"\kern1pt"),
            Text(content=" com a peça "),
            PieceGlyph(piece=PieceType.KNIGHT, figurine_set=FigurineSet.WHITE,
                       font_family="Merida"),
            Text(content=", o lance "),
            Move(san="Nf3", position_before=_INICIO, ply=1, show_move_number=True, nags=(1,),
                 render=MoveRenderStyle.FIGURINE, figurine_set=FigurineSet.WHITE),
            Text(content=" e o "),
            Move(san="e5", position_before=_DEPOIS_E4, ply=2, move_number_text="1…"),
            Text(content=", a imagem "),
            ImageInline(resource="figura.svg"),
            Text(content=" e a fórmula "),
            MathInline(latex=r"\frac{1}{2}", mathml="<math/>"),
        )),
    )


def _extensoes_xadrez() -> tuple[Any, ...]:
    from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle
    from caissa.core.model import (
        ClockAnnotation,
        ClockKind,
        Diagram,
        DiagramStyle,
        EvalAnnotation,
        GameHeaders,
        GameRenderOptions,
        GameScore,
        Mark,
        MarkKind,
        MoveNode,
        PgnTag,
        VariationStyle,
    )

    solucao = GameScore(children=(MoveNode(san="e4", ply=1, position_before=_INICIO,
                                           position_after=_DEPOIS_E4),))
    e5 = MoveNode(san="e5", ply=2, position_before=_DEPOIS_E4, position_after=_DEPOIS_E5,
                  comment_before="a resposta simétrica")
    literal = MoveNode(san="Zz9", ply=2, comment_after="um lance que o OCR leu errado")
    outra = MoveNode(san="Zz8", ply=2)
    e4 = MoveNode(san="e4", ply=1, position_before=_INICIO, position_after=_DEPOIS_E4,
                  clock=ClockAnnotation(kind=ClockKind.CLOCK, text="1:59:30", seconds=7170.0),
                  evaluation=EvalAnnotation(value=0.3, depth=20, text="+0.30"),
                  arrows=(Mark(kind=MarkKind.ARROW, squares=("e2", "e4")),),
                  emphasis=True, children=(literal, e5, outra))
    partida = GameScore(
        title="Uma partida com lances literais",
        headers=GameHeaders(white="Branco", black="Preto",
                            extra=(PgnTag(name="Annotator", value="X"),
                                   PgnTag(name="ECO", value="C20"))),
        initial_fen=_INICIO, variant="chess960",
        render=GameRenderOptions(render=MoveRenderStyle.FIGURINE,
                                 figurine_set=FigurineSet.WHITE,
                                 variation_style=VariationStyle.INDENTED,
                                 max_variation_depth=2, show_headers=False, show_result=False),
        children=(e4,))
    # O CB confere o diagrama contra o lance acima dele no livro: o da solução fica por último.
    return (
        Diagram(fen=_REIS, label="Diagrama 9"),
        Diagram(fen="6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", label="Posição A", number=7,
                marks=(Mark(kind=MarkKind.ARROW, squares=("d1", "d8")),),
                style=DiagramStyle(name="Grande"), solution=solucao),
        partida,
    )


def regerar_extensoes() -> list[Path]:
    """As fixtures das extensões (§12): documentos pequenos pelo escritor legível.

    Cada nó é o da linha do §12 com o campo que a extensão diz; as imagens dos diagramas, que são
    derivadas, vão para `Images/` como as das outras fixtures.
    """
    from caissa.core.model import Document
    from caissa.export.legivel import Capitulo, escrever_capitulo

    alvos = []
    for nome, construir, titulo in (
            ("extensoes_blocos.xhtml", _extensoes_blocos, "As extensões dos blocos"),
            ("extensoes_texto.xhtml", _extensoes_texto, "As extensões dentro do parágrafo"),
            ("extensoes_xadrez.xhtml", _extensoes_xadrez, "As extensões do xadrez")):
        blocos = construir()
        documento = Document(body=blocos)
        texto, escritor = escrever_capitulo(
            Capitulo(blocos=blocos, titulo=titulo, folhas=("../Styles/livro.css",)), documento)
        alvo = CONTRATO / nome
        alvo.write_text(texto, encoding="utf-8", newline="\n")
        for imagem, svg in escritor.imagens.items():
            destino = CONTRATO / "Images" / imagem
            if svg and not destino.exists():
                destino.write_text(svg, encoding="utf-8", newline="\n")
        alvos.append(alvo)
    figura = CONTRATO / "Images" / "figura.svg"
    if not figura.exists():
        figura.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                          '<rect width="10" height="10"/></svg>\n', encoding="utf-8",
                          newline="\n")
    return alvos


# --------------------------------------------------------------------------- #
# O portão
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--regerar-legada", action="store_true")
    parser.add_argument("--regerar-extensoes", action="store_true")
    args = parser.parse_args(argv)
    if args.regerar_legada:
        print(f"a fixture legada regravada: {regerar_legada()}")
        return 0
    if args.regerar_extensoes:
        for alvo in regerar_extensoes():
            print(f"a fixture de extensão regravada: {alvo}")
        return 0

    exigencias: dict[str, bool] = {}
    cobertura = conferir_cobertura()
    exigencias["cobertura: 100 % das linhas da S4 com fixture, e o §11 com as mesmas"
               + ("" if not cobertura else " -- " + "; ".join(cobertura))] = not cobertura

    limpas = [CONTRATO / n for n in (*LINHAS_DO_S4.values(), *COMBINACOES, *EXTENSOES)
              if (CONTRATO / n).is_file()]
    if args.sabotar == "sem_fen":
        limpas.append(NEGATIVAS / "negativa_sem_fen.xhtml")
    elif args.sabotar == "confundida":
        limpas.append(NEGATIVAS / "negativa_classe_confundida.xhtml")
    relatorio_cb = validar_no_cb(limpas)
    erros = [i for i in relatorio_cb["issues"] if i["severity"] == "error"]
    confunde = [*relatorio_cb["confundidos"], *relatorio_cb["pulados"]]
    exigencias[f"CB validate: {relatorio_cb['error_count']} erro(s) em {len(limpas)} fixtures "
               f"({relatorio_cb['warning_count']} aviso(s)), "
               f"{len(relatorio_cb['confundidos'])} marcação(ões) que o CB confunde e "
               f"{len(relatorio_cb['pulados'])} lance(s) que ele pula por não ter data-fen"
               + ("" if not erros else " -- " + "; ".join(
                   f"{e['bookpath']}:{e['line']} {e['message']}" for e in erros[:5]))
               + ("" if not confunde else " -- " + "; ".join(confunde[:5]))] = (
        not erros and not confunde)

    legada = conferir_legada()
    exigencias["a fixture legada lida pelo leitor atual"
               + ("" if not legada else " -- " + "; ".join(legada))] = not legada

    css, contagem = conferir_css()
    exigencias[f"mapa de estilo: {contagem['positivas']} positivas e {contagem['negativas']} "
               "negativas com o resultado declarado"
               + ("" if not css else " -- " + "; ".join(css[:5]))] = not css

    sidecar, hashes = conferir_sidecar()
    exigencias["sidecar: as três fixtures douradas do crítico, com o SHA-256 do relatório"
               + ("" if not sidecar else " -- " + "; ".join(sidecar))] = not sidecar

    registro = {"sabotagem": args.sabotar, "exigencias": exigencias, "cb": relatorio_cb,
                "sidecar_sha256": hashes, "css": contagem, "cb_em": str(pasta_do_cb())}
    if args.saida is not None:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "contrato.json").write_text(
            json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
        metricas = {"linhas_do_s4": len(LINHAS_DO_S4),
                    "linhas_cobertas": sum((CONTRATO / n).is_file() for n in LINHAS_DO_S4.values()),
                    "erros_do_cb": relatorio_cb["error_count"],
                    "avisos_do_cb": relatorio_cb["warning_count"],
                    "fixtures_de_css": contagem["positivas"] + contagem["negativas"]}
        (args.saida / "metricas.json").write_text(json.dumps(metricas, indent=1),
                                                  encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
