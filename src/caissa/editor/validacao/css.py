"""A camada CSS (spec S10): da sintaxe ao contraste AAA medido na página renderizada.

- **Sintaxe** — o erro do `tinycss2`, com linha e coluna.
- **Propriedade desconhecida** — o nome que nenhum módulo do CSS define (a personalizada `--x` e
  a de prefixo de fabricante passam).
- **O motor ativo não desenha** — medido no H1 (a matriz de CSS): o que o MuPDF, o motor da prévia
  que o produto leva, não desenha. O `var()` das variáveis da `:root` a prévia resolve
  (`previa.resolver_variaveis`); a variável de fora dela, não.
- **O DOCX não leva** — o que o mapa de estilo do H5 deixa de fora (`css-fora-do-mapa`).
- **Contraste AAA (1.4.6)** — o capítulo desenhado pelo `Story` do MuPDF (`previa.paginar`, a
  mesma do H1 e da prévia) com o CSS do projeto inteiro — as folhas ligadas, os `<style>` e os
  `style=""`, o `var()` resolvido pela cascata, as cores que o MuPDF lê errado reescritas, o papel
  do `body` (`pagina.py` diz o que muda e por quê). Cada trecho da página, com a cor e o alfa que
  o MuPDF desenhou, contra o fundo que ele pintou embaixo — os retângulos compostos na ordem, com
  a opacidade, célula a célula (o fundo que cobre parte do trecho conta), e o pixel da página
  sem o texto onde há imagem —, no pior fundo: 7:1 no texto normal, 4,5:1 no grande (≥ 24 px, ou
  ≥ 18,67 px em negrito — o MuPDF conta o px do CSS). O trecho volta ao elemento pelo texto, na
  ordem (o repetido cai no lugar dele). Vale para qualquer CSS do projeto, tema ou não; a página
  que não termina é dita (`css-contraste-incompleto`), e não medida pela metade em silêncio.
"""

from __future__ import annotations

import bisect
import itertools
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import tinycss2

from caissa.editor.css.mapa_de_estilo import resolver as mapa_de_estilo
from caissa.editor.validacao.contexto import Contexto, resolver
from caissa.editor.validacao.folha import Folha, folhas_do_documento
from caissa.editor.validacao.problema import Local, Problema, Severidade, regra
from caissa.editor.validacao.xml import Documento, Elemento, Trecho

__all__ = ["PROPRIEDADES", "contraste", "folhas_ligadas", "verificar", "verificar_folha",
           "verificar_mapa"]

C = "css"
SINTAXE = regra("css-sintaxe", C, Severidade.BLOQUEIA, "Erro de sintaxe no CSS",
                "Corrija a regra no ponto indicado; o leitor descarta o que não entende.")
DESCONHECIDA = regra("css-propriedade-desconhecida", C, Severidade.AVISA,
                     "Propriedade CSS desconhecida",
                     "Confira o nome (um erro de digitação?); o leitor ignora a declaração.")
MOTOR = regra("css-motor-nao-desenha", C, Severidade.INFORMA,
              "A prévia do MuPDF não desenha esta declaração (medido no H1)",
              "O leitor de EPUB pode desenhar; confira na prévia do Chromium, ou use o que "
              "a prévia desenha.")
DOCX = regra("css-mapa-docx", C, Severidade.INFORMA,
             "O DOCX não leva esta regra (o mapa de estilo)",
             "No EPUB e no HTML ela vale; no DOCX, use as classes do contrato.")
CONTRASTE = regra("css-contraste", C, Severidade.BLOQUEIA,
                  "Contraste abaixo do AAA (1.4.6)",
                  "Escureça o texto ou clareie o fundo: 7:1 no texto normal, 4,5:1 no grande.")
INCOMPLETO = regra("css-contraste-incompleto", C, Severidade.AVISA,
                   "O contraste não foi medido no arquivo inteiro",
                   "A página do MuPDF não terminou (um elemento que nunca cabe nela?): divida o "
                   "arquivo, ou confira o que vem depois do último texto medido.")

_LISTA_DAS_PROPRIEDADES = """
align-content align-items align-self all animation animation-delay animation-direction
animation-duration animation-fill-mode animation-iteration-count animation-name
animation-play-state animation-timing-function appearance aspect-ratio backface-visibility
background background-attachment background-blend-mode background-clip background-color
background-image background-origin background-position background-position-x
background-position-y background-repeat background-size block-size border border-block
border-block-color border-block-end border-block-start border-block-style border-block-width
border-bottom border-bottom-color border-bottom-left-radius border-bottom-right-radius
border-bottom-style border-bottom-width border-collapse border-color border-end-end-radius
border-end-start-radius border-image border-image-outset border-image-repeat border-image-slice
border-image-source border-image-width border-inline border-inline-color border-inline-end
border-inline-start border-inline-style border-inline-width border-left border-left-color
border-left-style border-left-width border-radius border-right border-right-color
border-right-style border-right-width border-spacing border-start-end-radius
border-start-start-radius border-style border-top border-top-color border-top-left-radius
border-top-right-radius border-top-style border-top-width border-width bottom
box-decoration-break box-shadow box-sizing break-after break-before break-inside caption-side
caret-color clear clip clip-path color color-scheme column-count column-fill column-gap
column-rule column-rule-color column-rule-style column-rule-width column-span column-width
columns contain content counter-increment counter-reset counter-set cursor direction display
empty-cells filter flex flex-basis flex-direction flex-flow flex-grow flex-shrink flex-wrap
float font font-family font-feature-settings font-kerning font-language-override
font-optical-sizing font-size font-size-adjust font-stretch font-style font-synthesis
font-variant font-variant-alternates font-variant-caps font-variant-east-asian
font-variant-ligatures font-variant-numeric font-variant-position font-variation-settings
font-weight gap grid grid-area grid-auto-columns grid-auto-flow grid-auto-rows grid-column
grid-column-end grid-column-gap grid-column-start grid-gap grid-row grid-row-end grid-row-gap
grid-row-start grid-template grid-template-areas grid-template-columns grid-template-rows
hanging-punctuation height hyphenate-character hyphens image-orientation image-rendering
inline-size inset inset-block inset-inline isolation justify-content justify-items
justify-self left letter-spacing line-break line-height list-style list-style-image
list-style-position list-style-type margin margin-block margin-block-end margin-block-start
margin-bottom margin-inline margin-inline-end margin-inline-start margin-left margin-right
margin-top marker marks mask max-block-size max-height max-inline-size max-width
min-block-size min-height min-inline-size min-width mix-blend-mode object-fit object-position
opacity order orphans outline outline-color outline-offset outline-style outline-width
overflow overflow-wrap overflow-x overflow-y padding padding-block padding-block-end
padding-block-start padding-bottom padding-inline padding-inline-end padding-inline-start
padding-left padding-right padding-top page page-break-after page-break-before
page-break-inside perspective perspective-origin place-content place-items place-self
pointer-events position print-color-adjust quotes resize right rotate row-gap ruby-align
ruby-position scale scroll-behavior scroll-margin scroll-padding shape-outside size speak
speak-as src tab-size table-layout text-align text-align-last text-combine-upright
text-decoration text-decoration-color text-decoration-line text-decoration-skip-ink
text-decoration-style text-decoration-thickness text-emphasis text-emphasis-color
text-emphasis-position text-emphasis-style text-indent text-justify text-orientation
text-overflow text-rendering text-shadow text-transform text-underline-offset
text-underline-position top transform transform-origin transform-style transition
transition-delay transition-duration transition-property transition-timing-function translate
unicode-bidi unicode-range user-select vertical-align visibility white-space widows width
will-change word-break word-spacing word-wrap writing-mode z-index zoom font-display
ascent-override descent-override line-gap-override bleed
"""
PROPRIEDADES = frozenset(_LISTA_DAS_PROPRIEDADES.split())
"""As propriedades (e os descritores de `@font-face` e `@page`) dos módulos do CSS."""
PREFIXOS = ("-webkit-", "-moz-", "-ms-", "-o-", "-epub-", "-adobe-", "-apple-", "-prince-")

MUPDF_NAO_DESENHA: dict[str, frozenset[str] | None] = {
    "border-radius": None, "opacity": None, "float": None, "height": None,
    "letter-spacing": None, "font-variant": frozenset({"small-caps"}),
    "font-variant-caps": frozenset({"small-caps"}), "display": frozenset({"inline-block"}),
    "vertical-align": frozenset({"middle"}),
}
"""O que o MuPDF não desenha, medido no H1 (`editor_motores.py --matriz`, 2026-09-30): `None` é
a propriedade inteira; o conjunto, os valores medidos. E, medido no H10 (a página do contraste,
PyMuPDF 1.28.2): a `background-image` (`_motor`) e as cores de função (`CORES_QUE_O_MUPDF_ERRA`)."""
CORES_QUE_O_MUPDF_ERRA = frozenset({"rgba", "hsl", "hsla", "hwb"})
"""O MuPDF lê o alfa do `rgba()` de 0 a 255 (o `rgba(…, 1)` sai com alfa 1/255, o `.5` some),
desenha `hsl()`/`hsla()`/`hwb()` em preto e erra o `rgb(r g b / a)`."""
MUPDF_FONTES_QUE_FALTAM = frozenset({"georgia", "palatino", "palatino linotype",
                                     "source serif 4", "dejavu sans"})
"""As famílias que a matriz do H1 pediu e o MuPDF não tinha (ele cai na genérica)."""
_NEUTROS = frozenset({"none", "initial", "inherit", "unset", "0", "normal", "auto", "1"})
_VARIAVEL = re.compile(r"var\(\s*(--[\w-]+)")


def verificar_folha(folha: Folha, contexto: Contexto) -> list[Problema]:
    """A sintaxe, as propriedades e o motor ativo numa folha (ou `<style>`, ou `style=""`)."""
    problemas = [Problema(SINTAXE, folha.local(erro), erro.message) for erro in folha.erros()]
    for regra_ in folha.regras():
        if contexto.motor == "mupdf" and regra_.type == "qualified-rule":
            seletor = tinycss2.serialize(regra_.prelude)
            if "first-letter" in seletor:
                problemas.append(Problema(MOTOR, folha.local(regra_),
                                          f"{seletor.strip()}: a capitular (::first-letter)"))
    raiz = _variaveis_da_raiz(folha)
    for _, declaracao in folha.declaracoes():
        nome = declaracao.lower_name
        if not nome.startswith("--") and not nome.startswith(PREFIXOS) and \
                nome not in PROPRIEDADES:
            problemas.append(Problema(DESCONHECIDA, folha.local(declaracao), nome))
        if contexto.motor == "mupdf":
            problemas += _motor(folha, declaracao, raiz)
    return problemas


def _variaveis_da_raiz(folha: Folha) -> set[str]:
    nomes: set[str] = set()
    for regra_ in folha.regras():
        if regra_.type == "qualified-rule" and \
                tinycss2.serialize(regra_.prelude).strip() in (":root", "html"):
            nomes |= {d.name for d in tinycss2.parse_declaration_list(
                regra_.content, skip_comments=True, skip_whitespace=True)
                if d.type == "declaration" and d.name.startswith("--")}
    return nomes


def _motor(folha: Folha, declaracao: object, raiz: set[str]) -> list[Problema]:
    nome = declaracao.lower_name  # type: ignore[attr-defined]
    valor = tinycss2.serialize(declaracao.value).strip()  # type: ignore[attr-defined]
    local = folha.local(declaracao)
    problemas = []
    if nome in MUPDF_NAO_DESENHA and valor.lower() not in _NEUTROS:
        valores = MUPDF_NAO_DESENHA[nome]
        if valores is None or valor.lower() in valores:
            problemas.append(Problema(MOTOR, local, f"{nome}: {valor}"))
    if nome == "font-family":
        primeira = valor.split(",")[0].strip().strip("\"'").lower()
        if primeira in MUPDF_FONTES_QUE_FALTAM:
            problemas.append(Problema(MOTOR, local, f"{nome}: a fonte {primeira!r} não é do "
                                                    "MuPDF, que cai na genérica"))
    problemas += [Problema(MOTOR, local, f"{nome}: a variável {variavel} não é da :root "
                                         "(a prévia não a resolve)")
                  for variavel in _VARIAVEL.findall(valor) if variavel not in raiz]
    if nome in ("background-image", "background") and "url(" in valor.lower():
        problemas.append(Problema(MOTOR, local, f"{nome}: a imagem de fundo"))
    for no in declaracao.value:  # type: ignore[attr-defined]
        if no.type == "function" and (no.lower_name in CORES_QUE_O_MUPDF_ERRA or (
                no.lower_name == "rgb" and "/" in tinycss2.serialize(no.arguments))):
            problemas.append(Problema(MOTOR, local, f"{nome}: {no.lower_name}() (use #rrggbb "
                                                    "ou #rrggbbaa)"))
            break
    return problemas


def verificar_mapa(folha: Folha) -> list[Problema]:
    """O que o mapa de estilo do H5 deixa fora do DOCX, com a coluna da declaração ou da regra."""
    avisos = mapa_de_estilo([(folha.arquivo, folha.texto)]).avisos
    declaracoes = [(r, d) for r, d in folha.declaracoes() if d.type == "declaration"]
    regras = [r for r in folha.regras() if r.type in ("qualified-rule", "at-rule")]
    problemas = []
    for aviso in avisos:
        no = None
        if aviso.propriedade:
            no = next((d for _, d in declaracoes if d.source_line == aviso.linha
                       and d.lower_name == aviso.propriedade), None)
        if no is None:
            no = next((r for r in regras if r.source_line == aviso.linha), None)
        local = folha.local(no) if no is not None else Local(folha.arquivo, aviso.linha, 1)
        rotulo = f"{aviso.seletor} {{ {aviso.propriedade} }}" if aviso.propriedade \
            else aviso.seletor
        problemas.append(Problema(DOCX, local, rotulo.strip()))
    return problemas


def verificar(documento: Documento, contexto: Contexto) -> list[Problema]:
    """As folhas de dentro do XHTML (`<style>`, `style=""`) e o contraste da página."""
    problemas: list[Problema] = []
    for folha in folhas_do_documento(documento):
        problemas += verificar_folha(folha, contexto)
    if contexto.medir_contraste and documento.raiz is not None:
        problemas += contraste(documento, contexto)
    return problemas


def folhas_ligadas(documento: Documento, contexto: Contexto) -> list[tuple[str, str]]:
    """As folhas do projeto que o XHTML liga (`<link rel="stylesheet">`), na ordem."""
    folhas = []
    for elemento in documento.elementos():
        if elemento.nome == "link" and "stylesheet" in (elemento.get("rel") or "").split():
            caminho = resolver(documento.arquivo, elemento.get("href") or "")
            texto = contexto.texto(caminho) if caminho else None
            if caminho and texto is not None:
                folhas.append((caminho, texto))
    return folhas


# --------------------------------------------------------------------------- #
# O contraste AAA, na página do MuPDF
# --------------------------------------------------------------------------- #


_JOELHO_SRGB = 0.04045
GRANDE_PX = 24.0
"""O texto grande do WCAG (18 pt) no px do CSS, que é a unidade do MuPDF."""
GRANDE_NEGRITO_PX = 18.66
"""O texto grande em negrito do WCAG (14 pt)."""
IMAGENS = frozenset({"fill-image", "fill-imgmask", "fill-shade"})
"""O que o `get_bboxlog` do MuPDF desenha de imagem (e o degradê): o fundo que só o pixel diz."""
CELULA_MINIMA = 0.25
"""A fresta (em pontos) entre duas bordas de fundo que não conta como fundo próprio."""
DPI_DO_FUNDO = 144
PASSO_NA_IMAGEM = 0.5
"""A distância (em pontos) entre as amostras da imagem sob a faixa de um trecho."""
JANELA = 2000
"""Até onde (em caracteres do texto normalizado) o trecho curto pode pular à frente no
alinhamento: o que o CSS gera (as aspas, o número da lista) casaria com um igual longe dali."""
CURTO = 12
CMYK = 4
FOLGA_DA_CAIXA = 0.5
"""A diferença (em pontos) com que a caixa de um trecho no `rawdict` é a mesma do `dict`."""
_SEM_LARGURA = re.compile(r"[\s\u00ad\u200b-\u200d\u2060\ufeff]+")
_MARCADOR = re.compile(r"^(?:[^\w]+|\d+[.)]|[a-z][.)]|[ivxlcdm]+[.)])", re.IGNORECASE)
Cor = tuple[float, float, float]


def _linear(canal: float) -> float:
    return canal / 12.92 if canal <= _JOELHO_SRGB else ((canal + 0.055) / 1.055) ** 2.4


def razao(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """A razão de contraste do WCAG entre duas cores (componentes de 0 a 1)."""
    la = 0.2126 * _linear(a[0]) + 0.7152 * _linear(a[1]) + 0.0722 * _linear(a[2])
    lb = 0.2126 * _linear(b[0]) + 0.7152 * _linear(b[1]) + 0.0722 * _linear(b[2])
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _cor(inteiro: int) -> Cor:
    return ((inteiro >> 16) & 255) / 255, ((inteiro >> 8) & 255) / 255, (inteiro & 255) / 255


def _hex(cor: Cor) -> str:
    return "#" + "".join(f"{round(c * 255):02x}" for c in cor)


def _rgb(cor: tuple[float, ...]) -> Cor:
    """A cor do `get_drawings` (cinza, RGB ou CMYK) em RGB."""
    if len(cor) == 1:
        return cor[0], cor[0], cor[0]
    if len(cor) == CMYK:
        c, m, y, k = cor
        return (1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)
    return cor[0], cor[1], cor[2]


@dataclass
class _Medido:
    """Um trecho da página do MuPDF: o texto, a caixa, a faixa em que o fundo conta, a tinta."""

    indice: int
    pagina: int
    texto: str
    caixa: tuple[float, float, float, float]
    faixa: tuple[float, float, float, float]
    cor: Cor
    alfa: float
    tamanho: float
    negrito: bool

    @property
    def altura(self) -> float:
        return self.caixa[3] - self.caixa[1]


@dataclass
class _Falha:
    """O trecho abaixo do mínimo: o que dizer, e onde começa o pior fundo.

    O lugar só conta quando o pior fundo não é o trecho todo (o fundo de um elemento de dentro).
    """

    mensagem: str
    x: float | None = None
    deslocamento: int = 0
    """Os caracteres (normalizados) do trecho antes do pior fundo."""
    incompleta: bool = False
    """O fundo não se mediu (a imagem sob o trecho não se lê): `css-contraste-incompleto`."""


def _medidos(folha: Any, numero: int, inicio: int) -> list[_Medido]:
    """Os trechos da página, na ordem do desenho (a do documento)."""
    import pymupdf

    # Sem a imagem no dicionário (o substituto de cada diagrama sairia inteiro, em bytes).
    flags = (pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_LIGATURES
             & ~pymupdf.TEXT_PRESERVE_IMAGES)
    medidos: list[_Medido] = []
    for bloco in folha.get_text("dict", flags=flags)["blocks"]:
        for linha in bloco.get("lines", []):
            for trecho in linha["spans"]:
                alfa = trecho.get("alpha", 255) / 255
                if not trecho["text"].strip() or alfa <= 0:
                    continue  # o texto invisível não é apresentado
                x0, y0, x1, y1 = trecho["bbox"]
                altura, recuo = y1 - y0, min(1.0, 0.1 * (x1 - x0))
                # A caixa do trecho passa da linha (o ascendente da fonte): o fundo conta no miolo
                # dela, onde a tinta está (medido: a caixa sobe 3,6 pt acima do fundo do bloco).
                faixa = (x0 + recuo, y0 + 0.35 * altura, x1 - recuo, y1 - 0.25 * altura)
                medidos.append(_Medido(inicio + len(medidos), numero, trecho["text"],
                                       (x0, y0, x1, y1), faixa, _cor(trecho["color"]), alfa,
                                       trecho["size"], bool(trecho["flags"] & 16)))
    return medidos


def _preenchimentos(folha: Any) -> list[tuple[Any, Cor, float]]:
    """Os retângulos pintados da página, na ordem do desenho, com a cor e a opacidade."""
    retangulos = []
    for desenho in folha.get_drawings():
        cor = desenho.get("fill")
        if cor is None:
            continue
        opacidade = desenho.get("fill_opacity")
        opacidade = 1.0 if opacidade is None else float(opacidade)
        itens = [item[1] if item[0] == "re" else item[1].rect
                 for item in desenho["items"] if item[0] in ("re", "qu")]
        if len(itens) != len(desenho["items"]):
            itens = [desenho["rect"]]  # um caminho que não é retângulo: a caixa dele
        retangulos += [(r, _rgb(tuple(cor)), opacidade) for r in itens]
    return retangulos


def _cruza(faixa: tuple[float, float, float, float], caixa: Any) -> bool:
    return bool(caixa[0] < faixa[2] and faixa[0] < caixa[2] and caixa[1] < faixa[3]
                and faixa[1] < caixa[3])


def _contem(fora: Any, dentro: Any) -> bool:
    return bool(fora[0] <= dentro[0] + 0.01 and fora[1] <= dentro[1] + 0.01
                and dentro[2] <= fora[2] + 0.01 and dentro[3] <= fora[3] + 0.01)


def _mesma_cor(a: Cor, b: Cor) -> bool:
    return all(abs(x - y) <= 2 / 255 for x, y in zip(a, b, strict=True))


def _fundos_vetoriais(medido: _Medido, preenchimentos: list[tuple[Any, Cor, float]],
                      papel: Cor) -> dict[Cor, float | None]:
    """As cores do fundo sob a faixa, e onde cada uma começa: os retângulos sobre o papel.

    As bordas dos retângulos dividem a faixa em células; em cada uma o fundo é o papel com os
    retângulos que a cobrem compostos na ordem do desenho, com a opacidade de cada um. Duas coisas
    do MuPDF não são fundo: o traço fino da cor do texto (o sublinhado, o riscado), e o fundo do
    bloco que ele pinta de novo em cada palavra (medido: o `rgba(0,0,0,.6)` do `<p>` sai no
    bloco e em cada palavra; composto duas vezes, o branco passaria) — o retângulo com a mesma
    tinta dentro de um já aplicado é o mesmo fundo.
    """
    x0, y0, x1, y1 = medido.faixa
    if x1 <= x0 or y1 <= y0:
        meio = ((x0 + x1) / 2, (y0 + y1) / 2)
        x0, x1, y0, y1 = meio[0] - 0.01, meio[0] + 0.01, meio[1] - 0.01, meio[1] + 0.01
    faixa = (x0, y0, x1, y1)
    cobrem = [(r, c, a) for r, c, a in preenchimentos if _cruza(faixa, r)
              and not (_mesma_cor(c, medido.cor) and r[3] - r[1] < 0.3 * medido.altura)]
    if not cobrem:
        return {papel: None}
    xs = sorted({x0, x1, *(min(max(r[0], x0), x1) for r, _, _ in cobrem),
                 *(min(max(r[2], x0), x1) for r, _, _ in cobrem)})
    ys = sorted({y0, y1, *(min(max(r[1], y0), y1) for r, _, _ in cobrem),
                 *(min(max(r[3], y0), y1) for r, _, _ in cobrem)})
    cores: dict[Cor, float | None] = {}
    for xa, xb in itertools.pairwise(xs):
        for ya, yb in itertools.pairwise(ys):
            if xb - xa < CELULA_MINIMA or yb - ya < CELULA_MINIMA:
                continue
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            cor = papel
            aplicados: list[tuple[Any, Cor, float]] = []
            for r, c, a in cobrem:
                if not (r[0] <= cx <= r[2] and r[1] <= cy <= r[3]):
                    continue
                if any(c == c0 and a == a0 and _contem(r0, r) for r0, c0, a0 in aplicados):
                    continue
                aplicados.append((r, c, a))
                cor = tuple(a * ci + (1 - a) * bi  # type: ignore[assignment]
                            for ci, bi in zip(c, cor, strict=True))
            chave: Cor = tuple(round(v, 4) for v in cor)  # type: ignore[assignment]
            anterior = cores.get(chave)
            cores[chave] = xa if anterior is None else min(anterior, xa)
    return cores or {papel: None}


def _fundo_no_ponto(x: float, y: float, cobrem: list[tuple[Any, Cor, float]],
                    papel: Cor) -> Cor:
    cor = papel
    aplicados: list[tuple[Any, Cor, float]] = []
    for r, c, a in cobrem:
        if not (r[0] <= x <= r[2] and r[1] <= y <= r[3]):
            continue
        if any(c == c0 and a == a0 and _contem(r0, r) for r0, c0, a0 in aplicados):
            continue
        aplicados.append((r, c, a))
        cor = tuple(a * ci + (1 - a) * bi for ci, bi in zip(c, cor, strict=True))  # type: ignore[assignment]
    return cor


def _imagem_em(dados: bytes, caminho: str, caixa: Any) -> Any:
    """A imagem de verdade desenhada no tamanho da caixa em que o MuPDF a pôs (com o alfa).

    `None` se ela não se lê (o arquivo corrompido): o fundo do texto sobre ela fica sem medir, e
    isso é dito (`css-contraste-incompleto`), e não medido contra o papel.
    """
    import pymupdf

    tipo = caminho.rsplit(".", 1)[-1].lower()
    try:
        with pymupdf.open(stream=dados, filetype=tipo) as imagem:
            pagina = imagem[0]
            escala = DPI_DO_FUNDO / 72
            matriz = pymupdf.Matrix(
                escala * (caixa[2] - caixa[0]) / max(pagina.rect.width, 1e-6),
                escala * (caixa[3] - caixa[1]) / max(pagina.rect.height, 1e-6))
            return pagina.get_pixmap(matrix=matriz, alpha=True)
    except (RuntimeError, pymupdf.mupdf.FzErrorBase):
        return None


def _fundos_com_imagem(medido: _Medido, preenchimentos: list[tuple[Any, Cor, float]],
                       papel: Cor, imagens: list[tuple[Any, Any]]) -> dict[Cor, float | None]:
    """As cores do fundo sob a faixa de um trecho que passa por cima de uma imagem.

    A faixa é amostrada a cada `PASSO_NA_IMAGEM`: no ponto dentro de uma imagem, o pixel dela
    (a de verdade, no tamanho em que o MuPDF a pôs) composto com o alfa sobre os retângulos; fora,
    os retângulos sobre o papel.
    """
    x0, y0, x1, y1 = medido.faixa
    cobrem = [(r, c, a) for r, c, a in preenchimentos if _cruza(medido.faixa, r)
              and not (_mesma_cor(c, medido.cor) and r[3] - r[1] < 0.3 * medido.altura)]
    cores: dict[Cor, float | None] = {}
    passos_x = max(1, int((x1 - x0) / PASSO_NA_IMAGEM))
    passos_y = max(1, int((y1 - y0) / PASSO_NA_IMAGEM))
    for i in range(passos_x + 1):
        x = x0 + (x1 - x0) * i / passos_x
        for j in range(passos_y + 1):
            y = y0 + (y1 - y0) * j / passos_y
            cor = _fundo_no_ponto(x, y, cobrem, papel)
            for caixa, imagem in imagens:
                if not (caixa[0] <= x < caixa[2] and caixa[1] <= y < caixa[3]):
                    continue
                px = min(imagem.width - 1, int((x - caixa[0]) / (caixa[2] - caixa[0])
                                               * imagem.width))
                py = min(imagem.height - 1, int((y - caixa[1]) / (caixa[3] - caixa[1])
                                                * imagem.height))
                *rgb, alfa = imagem.pixel(px, py)
                a = alfa / 255
                cor = tuple(a * (v / 255) + (1 - a) * b
                            for v, b in zip(rgb, cor, strict=True))
            chave: Cor = tuple(round(v, 4) for v in cor)  # type: ignore[assignment]
            anterior = cores.get(chave)
            cores[chave] = x if anterior is None else min(anterior, x)
    return cores or {papel: None}


def _fundos_rasterizados(folha: Any, medidos: list[_Medido],
                         papel: Cor) -> dict[int, dict[Cor, float | None]]:
    """As cores do fundo sob cada faixa, no pixel: a página sem o texto, sobre o papel.

    Só para o trecho que passa por cima de uma imagem. O texto sai pela redação (as imagens e
    os desenhos ficam), o papel vai por baixo de tudo, e o raster é sem suavização: cada pixel
    é uma cor do fundo, e o traço da cor do texto (a decoração) não conta.
    """
    import pymupdf

    folha.draw_rect(folha.rect, color=None, fill=papel, overlay=False)
    folha.add_redact_annot(folha.rect, fill=False)
    folha.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,  # type: ignore[attr-defined]
                           graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,  # type: ignore[attr-defined]
                           text=pymupdf.PDF_REDACT_TEXT_REMOVE)  # type: ignore[attr-defined]
    antes = pymupdf.TOOLS.show_aa_level()
    pymupdf.TOOLS.set_aa_level(0)
    escala = 72 / DPI_DO_FUNDO
    fundos: dict[int, dict[Cor, float | None]] = {}
    try:
        for medido in medidos:
            recorte = pymupdf.Rect(medido.faixa) & folha.rect
            if recorte.is_empty:
                continue
            imagem = folha.get_pixmap(clip=recorte, dpi=DPI_DO_FUNDO, alpha=False)
            amostras, passo, largura = imagem.samples, imagem.n, imagem.width
            cores: dict[Cor, float | None] = {}
            for pixel in range(len(amostras) // passo):
                i = pixel * passo
                cor = (amostras[i] / 255, amostras[i + 1] / 255, amostras[i + 2] / 255)
                if _mesma_cor(cor, medido.cor):
                    continue
                x = recorte.x0 + (pixel % largura + 0.5) * escala
                anterior = cores.get(cor)
                cores[cor] = x if anterior is None else min(anterior, x)
            fundos[medido.indice] = cores or {papel: None}
    finally:
        pymupdf.TOOLS.set_aa_level(antes["graphics"])
    return fundos


def _falha(medido: _Medido, fundos: dict[Cor, float | None]) -> _Falha | None:
    """A razão no pior fundo, abaixo do mínimo do AAA; `None` se passa."""
    pior: tuple[float, Cor, float | None] | None = None
    for fundo, x in fundos.items():
        tinta = tuple(medido.alfa * t + (1 - medido.alfa) * f
                      for t, f in zip(medido.cor, fundo, strict=True))
        valor = razao(tinta, fundo)  # type: ignore[arg-type]
        if pior is None or valor < pior[0]:
            pior = (valor, fundo, x)
    if pior is None:
        return None
    grande = medido.tamanho >= GRANDE_PX or (medido.negrito and
                                             medido.tamanho >= GRANDE_NEGRITO_PX)
    minimo = 4.5 if grande else 7.0
    if pior[0] + 1e-9 >= minimo:
        return None
    alfa = f" a {medido.alfa:.0%}" if medido.alfa < 1 else ""
    return _Falha(f"{pior[0]:.2f}:1 em «{medido.texto.strip()[:40]}» ({_hex(medido.cor)}{alfa} "
                  f"sobre {_hex(pior[1])}; {medido.tamanho:.1f} px"
                  f"{', negrito' if medido.negrito else ''}; o mínimo é {minimo}:1)",
                  x=pior[2] if len(fundos) > 1 else None)


def _deslocamento(folha: Any, medido: _Medido, x: float) -> int:
    """Os caracteres (normalizados) do trecho antes de `x`: o texto sobre o pior fundo."""
    import pymupdf

    flags = (pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_LIGATURES
             & ~pymupdf.TEXT_PRESERVE_IMAGES)
    # A página de texto só do recorte: a da página alta inteira custa 40 ms.
    pagina_de_texto = folha.get_textpage(clip=pymupdf.Rect(medido.caixa), flags=flags)
    for bloco in pagina_de_texto.extractRAWDICT()["blocks"]:
        for linha in bloco.get("lines", []):
            for trecho in linha["spans"]:
                if any(abs(a - b) > FOLGA_DA_CAIXA
                       for a, b in zip(trecho["bbox"], medido.caixa, strict=True)):
                    continue
                antes = []
                for caractere in trecho["chars"]:
                    if (caractere["bbox"][0] + caractere["bbox"][2]) / 2 >= x:
                        break
                    antes.append(caractere["c"])
                return len(_normal("".join(antes)))
    return 0


def _normal(texto: str) -> str:
    """O texto para casar a página com o documento: NFKC, sem caixa, sem espaço nem hífen mole."""
    return _SEM_LARGURA.sub("", unicodedata.normalize("NFKC", texto).casefold())


def _alinhar(medidos: list[_Medido], fluxo: str, ate: int) -> dict[int, tuple[int, int]]:
    """Onde cada trecho da página começa no texto do corpo, casando na ordem.

    O MuPDF desenha o corpo na ordem do documento: cada trecho da página é procurado no texto do
    corpo a partir de onde o anterior acabou (o texto repetido cai no lugar dele, e não no
    primeiro igual). O que o CSS gera — o marcador da lista, o hífen da quebra — sai da ponta
    antes de procurar. O trecho curto (menos de `CURTO` caracteres) só casa até `JANELA` à frente:
    as aspas e o número da lista que o CSS gera casariam com um igual longe dali e tirariam o resto
    do lugar. O que não se acha fica no lugar do cursor (o texto que vem a seguir). O lugar é o
    par (onde o trecho começaria contando o que o CSS gerou, onde o texto dele começa).
    """
    cursor = 0
    achados: dict[int, tuple[int, int]] = {}
    for medido in medidos:
        if medido.indice > ate:
            break
        chave = _normal(medido.texto)
        variantes = [(v, desconto) for v, desconto in (
            (chave, 0), (chave.rstrip("-\u2010"), 0),
            (_MARCADOR.sub("", chave, count=1), len(chave) - len(_MARCADOR.sub("", chave,
                                                                               count=1))))
            if v]
        lugar = None
        for variante, desconto in variantes:
            fim = None if len(variante) >= CURTO else cursor + JANELA
            achado = fluxo.find(variante, cursor, fim)
            if achado >= 0:
                lugar, cursor = (achado - desconto, achado), achado + len(variante)
                break
        achados[medido.indice] = lugar if lugar is not None else (cursor, cursor)
    return achados


def contraste(documento: Documento, contexto: Contexto) -> list[Problema]:
    """Cada trecho abaixo do AAA, acusado no elemento do XHTML que o tem (um por elemento).

    A página é a do `Story` do MuPDF (`pagina.preparar`: o CSS do projeto inteiro, o `var()`
    resolvido pela cascata, as cores que o MuPDF lê, o papel do `body`); o fundo de cada trecho
    é o que o MuPDF pintou embaixo dele — os retângulos compostos com a opacidade, e o pixel da
    página sem o texto onde há imagem. O MuPDF que falha ao desenhar a página é dito no `<body>`
    (`css-contraste-incompleto`), e a validação do arquivo segue.
    """
    import pymupdf

    from caissa.editor.validacao.pagina import preparar

    pagina = preparar(documento, contexto)
    # A folha que o @import não trouxe inteira (o limite de defesa) é dita no <link>/<style>.
    cortes = [Problema(INCOMPLETO, documento.local(elemento), motivo)
              for elemento, motivo in pagina.incompletas]
    if not pagina.trechos:
        return cortes
    mostrava = pymupdf.TOOLS.mupdf_display_errors()
    pymupdf.TOOLS.mupdf_display_errors(False)  # o que o MuPDF diria do CSS a camada já diz
    try:
        return cortes + _medir_a_pagina(documento, contexto, pagina)
    except (RuntimeError, pymupdf.mupdf.FzErrorBase) as erro:
        corpo = next((e for e in documento.elementos() if e.nome == "body"), documento.raiz)
        if corpo is None:
            return cortes
        return [*cortes, Problema(INCOMPLETO, documento.local(corpo),
                                  f"o MuPDF não desenhou a página: {str(erro)[:120]}")]
    finally:
        pymupdf.TOOLS.mupdf_display_errors(mostrava)


def _medir_a_pagina(documento: Documento, contexto: Contexto, pagina: Any) -> list[Problema]:
    """A página no MuPDF, cada trecho medido contra o fundo dele, e os problemas nos elementos."""
    import pymupdf

    from caissa.editor.previa import LARGURA_PT, paginar
    from caissa.editor.validacao.pagina import ALTURA_DA_MEDIDA

    medidos: list[_Medido] = []
    falhas: dict[int, _Falha] = {}
    medida = paginar(pagina.texto, pagina.css, largura=LARGURA_PT, altura=ALTURA_DA_MEDIDA,
                     maximo=contexto.teto_de_paginas, arquivo=pagina.arquivo())
    with pymupdf.open("pdf", medida.pdf) as pdf:
        sob_imagem = _medir(pdf, pagina, medidos, falhas)
        if sob_imagem:
            # A ordem não bateu (um SVG do texto, uma imagem que o MuPDF não desenhou): o
            # leiaute com os substitutos é o mesmo, e as páginas com as imagens de verdade.
            real = paginar(pagina.texto, pagina.css, largura=LARGURA_PT,
                           altura=ALTURA_DA_MEDIDA, maximo=contexto.teto_de_paginas,
                           arquivo=pagina.arquivo(reais=True))
            with pymupdf.open("pdf", real.pdf) as com_imagens:
                for numero, lista in sob_imagem.items():
                    fundos = _fundos_rasterizados(com_imagens[numero], lista, pagina.papel)
                    for medido in lista:
                        falha = _falha(medido, fundos.get(medido.indice, {pagina.papel: None}))
                        if falha is not None:
                            falhas[medido.indice] = falha
        for indice, falha in falhas.items():
            if falha.x is not None:
                medido = medidos[indice]
                falha.deslocamento = _deslocamento(pdf[medido.pagina], medido, falha.x)
    return _acusar(documento, pagina.trechos, medidos, falhas, medida.laco)


def _medir(pdf: Any, pagina: Any, medidos: list[_Medido],
           falhas: dict[int, _Falha]) -> dict[int, list[_Medido]]:
    """Mede cada trecho da página.

    Devolve os que passam por cima de uma imagem que a ordem não identifica: esses a página com
    as imagens de verdade mede.
    """
    # A imagem que o MuPDF desenha é, na ordem, a da cópia (`PaginaMedida.imagens`).
    caixas = [(numero, caixa) for numero, folha in enumerate(pdf)
              for tipo, caixa in (folha.get_bboxlog() if pagina.imagens else [])
              if tipo in IMAGENS]
    pela_ordem = len(caixas) == len(pagina.imagens) and None not in pagina.imagens
    desenhadas: dict[int, Any] = {}
    sob_imagem: dict[int, list[_Medido]] = {}
    for numero, folha in enumerate(pdf):
        preenchimentos = _preenchimentos(folha)
        imagens = [(k, caixa) for k, (n, caixa) in enumerate(caixas) if n == numero]
        for medido in _medidos(folha, numero, len(medidos)):
            medidos.append(medido)
            embaixo = [(k, c) for k, c in imagens if _cruza(medido.faixa, c)]
            if embaixo and not pela_ordem:
                sob_imagem.setdefault(numero, []).append(medido)
                continue
            if embaixo:
                for k, caixa in embaixo:
                    if k not in desenhadas:
                        caminho = pagina.imagens[k] or ""
                        desenhadas[k] = _imagem_em(pagina.reais[caminho], caminho, caixa)
                ilegiveis = [pagina.imagens[k] for k, _ in embaixo if desenhadas[k] is None]
                if ilegiveis:
                    falhas[medido.indice] = _Falha(
                        f"a imagem {ilegiveis[0]} sob «{medido.texto.strip()[:40]}» não se lê: o "
                        "contraste ali não foi medido", incompleta=True)
                    continue
                fundos = _fundos_com_imagem(medido, preenchimentos, pagina.papel,
                                            [(c, desenhadas[k]) for k, c in embaixo])
            else:
                fundos = _fundos_vetoriais(medido, preenchimentos, pagina.papel)
            falha = _falha(medido, fundos)
            if falha is not None:
                falhas[medido.indice] = falha
    return sob_imagem


def _acusar(documento: Documento, trechos: list[Trecho], medidos: list[_Medido],
            falhas: dict[int, _Falha], laco: bool) -> list[Problema]:
    corpo = next((e for e in documento.elementos() if e.nome == "body"), documento.raiz)
    problemas: list[Problema] = []
    if falhas:
        pedacos = [_normal(t.texto) for t in trechos]
        fluxo = "".join(pedacos)
        inicios = list(itertools.accumulate((len(p) for p in pedacos), initial=0))
        posicoes = _alinhar(medidos, fluxo, max(falhas))
        acusados: dict[int, Cor] = {}
        ordem: list[tuple[Elemento, _Falha]] = []
        for indice in sorted(falhas):
            elemento = corpo
            if indice in posicoes:
                virtual, real = posicoes[indice]
                lugar = min(max(virtual + falhas[indice].deslocamento, real),
                            max(len(fluxo) - 1, 0))
                elemento = trechos[bisect.bisect_right(inicios, lugar) - 1].pai
            if elemento is None or id(elemento) in acusados:
                continue
            acusados[id(elemento)] = medidos[indice].cor
            ordem.append((elemento, falhas[indice]))
        for elemento, falha in ordem:
            cor = acusados[id(elemento)]
            # O descendente com a mesma tinta do ancestral acusado herdou dele: um problema só.
            if any(id(a) in acusados and _mesma_cor(acusados[id(a)], cor)
                   for a in elemento.ancestrais()):
                continue
            problemas.append(Problema(INCOMPLETO if falha.incompleta else CONTRASTE,
                                      documento.local(elemento), falha.mensagem))
    if laco and corpo is not None:
        ultimo = medidos[-1].texto.strip()[:40] if medidos else ""
        problemas.append(Problema(INCOMPLETO, documento.local(corpo),
                                  f"a página parou em {len(medidos)} trechos; depois de "
                                  f"«{ultimo}» o texto não foi medido"))
    return problemas
