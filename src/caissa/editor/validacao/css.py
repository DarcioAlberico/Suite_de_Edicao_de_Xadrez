"""A camada CSS (spec S10): da sintaxe ao contraste AAA medido na página renderizada.

- **Sintaxe** — o erro do `tinycss2`, com linha e coluna.
- **Propriedade desconhecida** — o nome que nenhum módulo do CSS define (a personalizada `--x` e
  a de prefixo de fabricante passam).
- **O motor ativo não desenha** — medido no H1 (a matriz de CSS): o que o MuPDF, o motor da prévia
  que o produto leva, não desenha. O `var()` das variáveis da `:root` a prévia resolve
  (`previa.resolver_variaveis`); a variável de fora dela, não.
- **O DOCX não leva** — o que o mapa de estilo do H5 deixa de fora (`css-fora-do-mapa`).
- **Contraste AAA (1.4.6)** — o capítulo paginado pelo `Story` do MuPDF (`previa.paginar`, a
  mesma do H1 e da prévia), com as folhas do projeto: cada trecho de texto, com a cor calculada,
  contra o fundo local (o retângulo preenchido embaixo dele, ou o papel): 7:1 no texto normal,
  4,5:1 no grande (≥ 24 px, ou ≥ 18,67 px em negrito — o MuPDF conta o px do CSS). Vale para
  qualquer CSS do projeto, tema ou não.
"""

from __future__ import annotations

import re

import tinycss2

from caissa.editor.css.mapa_de_estilo import resolver as mapa_de_estilo
from caissa.editor.validacao.contexto import Contexto, resolver
from caissa.editor.validacao.folha import Folha, folhas_do_documento
from caissa.editor.validacao.problema import Local, Problema, Severidade, regra
from caissa.editor.validacao.xml import Documento, Elemento

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
a propriedade inteira; o conjunto, os valores medidos."""
MUPDF_FONTES_QUE_FALTAM = frozenset({"georgia", "palatino", "palatino linotype",
                                     "source serif 4", "dejavu sans"})
"""As famílias que a matriz do H1 pediu e o MuPDF não tinha (ele cai na genérica)."""
_NEUTROS = frozenset({"none", "initial", "inherit", "unset", "0", "normal", "auto", "1"})
_SEM_LINK = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
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
            if texto is not None:
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


def _linear(canal: float) -> float:
    return canal / 12.92 if canal <= _JOELHO_SRGB else ((canal + 0.055) / 1.055) ** 2.4


def razao(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """A razão de contraste do WCAG entre duas cores (componentes de 0 a 1)."""
    la = 0.2126 * _linear(a[0]) + 0.7152 * _linear(a[1]) + 0.0722 * _linear(a[2])
    lb = 0.2126 * _linear(b[0]) + 0.7152 * _linear(b[1]) + 0.0722 * _linear(b[2])
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _cor(inteiro: int) -> tuple[float, float, float]:
    return ((inteiro >> 16) & 255) / 255, ((inteiro >> 8) & 255) / 255, (inteiro & 255) / 255


def _normal(texto: str) -> str:
    return " ".join(texto.split())


def contraste(documento: Documento, contexto: Contexto) -> list[Problema]:
    """Cada trecho abaixo do AAA, acusado no elemento do XHTML que o tem (um por elemento)."""
    import pymupdf

    from caissa.editor.previa import paginar

    css = "\n".join(t for _, t in folhas_ligadas(documento, contexto))
    # As folhas vão pelo `user_css`, com as variáveis resolvidas: o <link> sai do texto que o
    # MuPDF lê (sem o `Archive`, ele só reclamaria de não achar o arquivo). O que o MuPDF diria
    # do CSS a camada já diz, com o local: as mensagens dele não vão ao console.
    mostrava = pymupdf.TOOLS.mupdf_display_errors()
    pymupdf.TOOLS.mupdf_display_errors(False)
    try:
        paginado = paginar(_SEM_LINK.sub("", documento.texto), css, maximo=200)
    finally:
        pymupdf.TOOLS.mupdf_display_errors(mostrava)
    problemas: list[Problema] = []
    acusados: set[int] = set()
    with pymupdf.open("pdf", paginado.pdf) as pdf:
        for pagina in pdf:
            fundos = [(d["rect"], d["fill"]) for d in pagina.get_drawings()
                      if d.get("fill") is not None]
            for bloco in pagina.get_text("dict")["blocks"]:
                for linha in bloco.get("lines", []):
                    for trecho in linha["spans"]:
                        falha = _falha(trecho, fundos)
                        if falha is None:
                            continue
                        elemento = _elemento_do_texto(documento, trecho["text"])
                        if elemento is None or id(elemento) in acusados:
                            continue
                        acusados.add(id(elemento))
                        problemas.append(Problema(CONTRASTE, documento.local(elemento), falha))
    return problemas


def _falha(trecho: dict, fundos: list[tuple[object, tuple[float, float, float]]]) -> str | None:
    texto = trecho["text"].strip()
    if not texto:
        return None
    x0, y0, x1, y1 = trecho["bbox"]
    centro = ((x0 + x1) / 2, (y0 + y1) / 2)
    fundo = (1.0, 1.0, 1.0)
    for retangulo, cor in fundos:  # o último desenhado embaixo do centro é o fundo local
        if retangulo.x0 <= centro[0] <= retangulo.x1 and \
                retangulo.y0 <= centro[1] <= retangulo.y1:  # type: ignore[attr-defined]
            fundo = tuple(cor)[:3]  # type: ignore[assignment]
    valor = razao(_cor(trecho["color"]), fundo)
    negrito = bool(trecho["flags"] & 16)
    grande = trecho["size"] >= GRANDE_PX or (negrito and trecho["size"] >= GRANDE_NEGRITO_PX)
    minimo = 4.5 if grande else 7.0
    if valor + 1e-9 >= minimo:
        return None
    return (f"{valor:.2f}:1 em «{texto[:40]}» ({trecho['size']:.1f} px"
            f"{', negrito' if negrito else ''}; o mínimo é {minimo}:1)")


def _elemento_do_texto(documento: Documento, texto: str) -> Elemento | None:
    """O elemento do primeiro trecho do XHTML que tem este texto (o da página do MuPDF)."""
    procurado = _normal(texto)
    if not procurado or documento.raiz is None:
        return None
    for trecho in documento.raiz.trechos():
        if procurado in _normal(trecho.texto):
            return trecho.pai
    # A ligadura ou a hifenização do MuPDF mudou o texto: o problema não se perde, vai ao corpo.
    return next((e for e in documento.elementos() if e.nome == "body"), documento.raiz)
