r"""A página que o contraste mede (spec S10; roadmap H10): o capítulo como o MuPDF o desenha.

O contraste AAA é medido na página que o `Story` do MuPDF (a prévia do produto) desenha, com o CSS
do projeto inteiro: as folhas ligadas (e o `@import` local delas), os `<style>` e os `style=""`,
na ordem do documento. O que o MuPDF sozinho desenharia diferente do livro — medido no H10
(2026-09-30, PyMuPDF 1.28.2) — é corrigido antes, sem mudar cor nem fundo de nada:

- **O `var()`** — o MuPDF não o resolve. A cascata do `cssselect2` dá a cada elemento o valor
  das propriedades personalizadas dele (definidas em qualquer regra ou `style=""`, herdadas do
  pai), e a declaração vencedora que usa `var()` vai resolvida para o `style=""` do elemento, com
  `!important`. Quando toda propriedade personalizada vem de uma regra `:root`/`html`, a
  substituição é uma só, no texto.
- **A cor** — o MuPDF lê o alfa do `rgba()` de 0 a 255 (o texto em `rgba(…, .5)` some), desenha
  o `hsl()` em preto e erra o `rgb(r g b / a)`; toda cor de função vira `#rrggbb` ou `#rrggbbaa`,
  que ele desenha certo (o alfa do texto no trecho, o da caixa no `fill_opacity`).
- **O papel** — o MuPDF não pinta o fundo do `html` nem do `body`: o papel da medida é esse
  fundo (o do `body` sobre o do `html` sobre o branco), pela cascata.
- **A quebra de página** — `page-break-*` e `break-*` saem: não mudam cor nem fundo, e o
  `page-break-before` no primeiro elemento faz o MuPDF paginar para sempre (H1). A página é alta
  (a largura da prévia, `ALTURA_DA_MEDIDA` de altura): o capítulo de 260 KB com a folha base cabe
  em 5 páginas (92 ms), e não em mais de 400 A5 (as tabelas com `break-inside: avoid`).
- **As imagens** — cada SVG vira um substituto do mesmo tamanho (a raiz com o `width`, o
  `height` e o `viewBox` do original: o mesmo leiaute, medido — 326 → 142 ms no arquivo de
  260 KB); a de mapa de bits vai como é. A imagem de verdade só entra quando um texto passa por
  cima de uma (o MuPDF honra `position` e a entrelinha pequena): `PaginaMedida.arquivo(reais=True)`.
- **O link** — o MuPDF pinta o `<a href>` de azul com o `a:link` da folha dele, que vence o
  `a { color }` do autor pela especificidade (medido: `a { color: #9ecbff }` sai `#0000ff`); no
  livro, a folha do autor vence a do leitor sempre. A cor que a cascata do autor dá ao link vai
  no `style=""` dele, com `!important`; o link que o autor não pinta fica o azul (o do leitor).
- **O `@media`** — o MuPDF ignora o bloco inteiro, qualquer mídia; a cascata também. A
  `@font-face` sai (a fonte não muda a cor; o negrito do trecho vem do MuPDF).

Nada disto vai para o livro: é a cópia que o MuPDF desenha para medir.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree

import tinycss2
import tinycss2.color4

from caissa.editor.validacao.contexto import Contexto, resolver
from caissa.editor.validacao.xml import XHTML, XLINK_HREF, XML_LANG, Documento, Elemento, Trecho

__all__ = ["ALTURA_DA_MEDIDA", "PaginaMedida", "cores_em_hex", "preparar", "substituir"]

ALTURA_DA_MEDIDA = 14_000.0
"""A altura da página medida, em pontos (a largura é a da prévia)."""
QUEBRAS = frozenset({"page-break-before", "page-break-after", "page-break-inside",
                     "break-before", "break-after", "break-inside"})
FUNCOES_DE_COR = frozenset({"rgb", "rgba", "hsl", "hsla", "hwb"})
PROPRIEDADES_DE_COR = frozenset({
    "color", "background-color", "background", "border-color", "border-top-color",
    "border-right-color", "border-bottom-color", "border-left-color", "outline-color",
    "text-decoration-color", "column-rule-color"})
"""Onde um nome de cor (`rebeccapurple`) também vira `#rrggbb`."""
HERDADAS = frozenset({
    "color", "font", "font-family", "font-size", "font-style", "font-variant", "font-weight",
    "font-stretch", "letter-spacing", "word-spacing", "line-height", "text-align",
    "text-indent", "text-transform", "white-space", "direction", "visibility", "hyphens",
    "quotes", "list-style", "list-style-type", "list-style-position", "list-style-image",
    "orphans", "widows", "caption-side", "border-collapse", "border-spacing", "empty-cells"})
"""O que o valor inválido na hora do cálculo (o `var()` sem valor) faz herdar."""
SEM_TEXTO = frozenset({"head", "script", "style", "link", "meta", "title", "noscript",
                       "template", "base"})
SEM_DESENHO = frozenset({"object", "embed", "iframe", "video", "audio", "canvas"})
"""O que sai da cópia: não é texto, e o que o MuPDF desenharia dele quebraria a ordem das imagens
(a imagem que o MuPDF desenha é, na ordem, a `<img>` ou o `<svg>` da cópia)."""
VAZIOS = frozenset({"area", "br", "col", "embed", "hr", "img", "input", "source", "track",
                    "wbr"})
RAIZ = (":root", "html")
_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)")
_RAIZ_DO_SVG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_ATRIBUTO_DO_TAMANHO = re.compile(
    r"\s(width|height|viewBox|preserveAspectRatio)\s*=\s*(\"[^\"]*\"|'[^']*')")
_IMPORT_PROFUNDIDADE = 4
BRANCO = (1.0, 1.0, 1.0)
Cor = tuple[float, float, float]
Chave = tuple[int, int, tuple[int, int, int], int]
"""A ordem da cascata: `!important`, o `style=""`, a especificidade, a ordem no documento."""


@dataclass
class PaginaMedida:
    """O que vai ao `Story`, o papel, e o texto do corpo na ordem em que vai."""

    texto: str
    css: str
    papel: Cor
    trechos: list[Trecho]
    substitutos: dict[str, bytes] = field(default_factory=dict)
    """O que o `Story` lê pelo caminho: os SVG substitutos e as imagens de mapa de bits."""
    reais: dict[str, bytes] = field(default_factory=dict)
    """Os mesmos caminhos, com as imagens de verdade."""
    imagens: list[str | None] = field(default_factory=list)
    """Cada imagem que o MuPDF desenha, na ordem: o caminho da `<img>`, ou `None` no `<svg>` do
    texto (que vai como é)."""

    def arquivo(self, *, reais: bool = False) -> Any:
        """O `pymupdf.Archive` das imagens (os substitutos, ou as de verdade), ou `None`."""
        import pymupdf

        fonte = self.reais if reais else self.substitutos
        if not fonte:
            return None
        arquivo = pymupdf.Archive()
        for caminho, dados in fonte.items():
            arquivo.add((dados, caminho))
        return arquivo


# --------------------------------------------------------------------------- #
# As cores e o var()
# --------------------------------------------------------------------------- #


def _rgba(no: Any) -> tuple[float, float, float, float] | None:
    """A cor de um nó do `tinycss2` em sRGB com alfa (0 a 1), ou `None`."""
    try:
        cor = tinycss2.color4.parse_color(no)
        if cor is None or isinstance(cor, str):  # `currentcolor`
            return None
        vermelho, verde, azul = (min(1.0, max(0.0, c or 0.0))
                                 for c in cor.to("srgb").coordinates)
    except (NotImplementedError, TypeError, ValueError):  # lab(), oklch()…: fica como está
        return None
    alfa = 1.0 if cor.alpha is None else min(1.0, max(0.0, float(cor.alpha)))
    return vermelho, verde, azul, alfa


def _hex(cor: tuple[float, float, float, float]) -> str:
    canais = "".join(f"{round(c * 255):02x}" for c in cor[:3])
    return f"#{canais}" if cor[3] >= 1.0 else f"#{canais}{round(cor[3] * 255):02x}"


def cores_em_hex(valor: str, *, nomes: bool = False) -> str:
    """O valor com cada cor de função (e, com `nomes`, cada nome de cor) em `#rrggbb[aa]`."""
    if "(" not in valor and not nomes:
        return valor
    partes = []
    for no in tinycss2.parse_component_value_list(valor):
        troca = None
        if (no.type == "function" and no.lower_name in FUNCOES_DE_COR) or (
                nomes and no.type == "ident"
                and no.lower_value not in ("transparent", "currentcolor")):
            cor = _rgba(no)
            troca = _hex(cor) if cor is not None else None
        partes.append(troca if troca is not None else tinycss2.serialize([no]))
    return "".join(partes)


def substituir(valor: str, variaveis: Mapping[str, str]) -> str | None:
    """O valor com cada `var(--x[, reserva])` trocado; `None` se falta uma sem reserva."""
    if "var(" not in valor:
        return valor
    invalido = False

    def trocar(casado: re.Match[str]) -> str:
        nonlocal invalido
        if casado.group(1) in variaveis:
            return variaveis[casado.group(1)]
        if casado.group(2) is not None:
            return casado.group(2).strip()
        invalido = True
        return ""

    for _ in range(10):  # a variável que usa outra
        novo = _VAR.sub(trocar, valor)
        if novo == valor:
            break
        valor = novo
    return None if invalido or "var(" in valor else valor


def _resolver_personalizadas(herdadas: Mapping[str, str],
                             proprias: Mapping[str, str]) -> dict[str, str]:
    """As propriedades personalizadas calculadas do elemento (a que se referencia em laço cai)."""
    brutas = {**herdadas, **proprias}
    calculadas = dict(herdadas)
    for nome, valor in proprias.items():
        pendente = valor
        for _ in range(10):
            novo = substituir(pendente, brutas)
            if novo is None or novo == pendente:
                pendente = novo  # type: ignore[assignment]
                break
            pendente = novo
        if pendente is None or "var(" in pendente:
            calculadas.pop(nome, None)
        else:
            calculadas[nome] = pendente
    return calculadas


def _valor_invalido(nome: str) -> str:
    """O valor da declaração cujo `var()` não tem valor (CSS Variables §3).

    Ela fica inválida na hora do cálculo: a propriedade herda, ou volta ao inicial.
    """
    if nome in HERDADAS:
        return "inherit"
    return "transparent" if nome in ("background-color", "background") else "initial"


# --------------------------------------------------------------------------- #
# As folhas
# --------------------------------------------------------------------------- #


@dataclass
class _Declaracao:
    nome: str
    valor: str
    importante: bool


@dataclass
class _Regra:
    prelude: str
    declaracoes: list[_Declaracao]
    seletores: list[Any] = field(default_factory=list)


def _declaracoes(itens: Iterable[Any]) -> list[_Declaracao]:
    return [_Declaracao(item.name if item.name.startswith("--") else item.lower_name,
                        tinycss2.serialize(item.value).strip(), bool(item.important))
            for item in itens if item.type == "declaration"]


def _url_do_import(regra: Any) -> str | None:
    for no in regra.prelude:
        if no.type in ("url", "string"):
            return str(no.value)
        if no.type == "function" and no.lower_name == "url":
            texto = [a for a in no.arguments if a.type == "string"]
            return str(texto[0].value) if texto else None
    return None


def _regras_da_folha(texto: str, arquivo: str, contexto: Contexto,
                     vistos: set[str], profundidade: int = 0) -> list[_Regra]:
    """As regras de estilo da folha, com o `@import` local expandido no lugar dele.

    O `@media`, a `@font-face`, a `@page` e o resto dos `@` saem: o MuPDF ignora o `@media` e o
    resto não muda a cor.
    """
    regras: list[_Regra] = []
    for regra in tinycss2.parse_stylesheet(texto, skip_comments=True, skip_whitespace=True):
        if regra.type == "qualified-rule":
            regras.append(_Regra(tinycss2.serialize(regra.prelude).strip(), _declaracoes(
                tinycss2.parse_declaration_list(regra.content, skip_comments=True,
                                                skip_whitespace=True))))
        elif regra.type == "at-rule" and regra.lower_at_keyword == "import" and \
                profundidade < _IMPORT_PROFUNDIDADE:
            url = _url_do_import(regra)
            caminho = resolver(arquivo, url) if url else None
            importado = contexto.texto(caminho) if caminho and caminho not in vistos else None
            if caminho and importado is not None:
                vistos.add(caminho)
                regras += _regras_da_folha(importado, caminho, contexto, vistos,
                                           profundidade + 1)
    return regras


def _regras_do_documento(documento: Documento, contexto: Contexto) -> list[_Regra]:
    """As folhas ligadas e os `<style>`, na ordem do documento."""
    regras: list[_Regra] = []
    for elemento in documento.elementos():
        rel = (elemento.get("rel") or "").lower().split()
        if elemento.nome == "link" and "stylesheet" in rel and "alternate" not in rel:
            caminho = resolver(documento.arquivo, elemento.get("href") or "")
            texto = contexto.texto(caminho) if caminho else None
            if caminho and texto is not None:
                regras += _regras_da_folha(texto, caminho, contexto, {caminho})
        elif elemento.nome == "style":
            regras += _regras_da_folha(elemento.texto(), documento.arquivo, contexto, set())
    return regras


def _declaracoes_do_estilo(elemento: Elemento) -> list[_Declaracao]:
    estilo = elemento.get("style")
    if not estilo:
        return []
    return _declaracoes(tinycss2.parse_declaration_list(estilo, skip_comments=True,
                                                        skip_whitespace=True))


# --------------------------------------------------------------------------- #
# A cascata
# --------------------------------------------------------------------------- #


class _Cascata:
    """A cascata do `cssselect2` sobre a árvore do `expat` (um espelho `ElementTree`).

    `rasa` espelha só a raiz e os filhos dela (o `html`, o `head` e o `body`): basta para o
    papel quando toda variável é da raiz.
    """

    def __init__(self, raiz: Elemento, regras: list[_Regra], *, rasa: bool = False) -> None:
        import cssselect2

        self.regras = regras
        self.casador = cssselect2.Matcher()
        for indice, regra in enumerate(regras):
            try:
                seletores = cssselect2.compile_selector_list(regra.prelude)
            except cssselect2.SelectorError:
                continue  # um seletor que o cssselect2 não entende: o MuPDF também não
            for seletor in seletores:
                self.casador.add_selector(seletor, indice)
        self.elementos: dict[int, Elemento] = {}
        espelho = self._espelho(raiz, rasa=rasa)
        self.embrulho = cssselect2.ElementWrapper.from_xml_root(espelho)

    def _espelho(self, raiz: Elemento, *, rasa: bool) -> ElementTree.Element:
        def criar(elemento: Elemento) -> ElementTree.Element:
            etiqueta = f"{{{elemento.espaco}}}{elemento.nome}" if elemento.espaco \
                else elemento.nome
            espelho = ElementTree.Element(etiqueta, dict(elemento.atributos))
            self.elementos[id(espelho)] = elemento
            return espelho

        topo = criar(raiz)
        pilha = [(raiz, topo)]
        while pilha:
            elemento, espelho = pilha.pop()
            for filho in elemento.filhos:
                if isinstance(filho, Elemento):
                    novo = criar(filho)
                    espelho.append(novo)
                    if not rasa:
                        pilha.append((filho, novo))
        return topo

    def vencedoras(self, embrulho: Any) -> dict[str, tuple[Chave, _Declaracao]]:
        """A declaração que vence em cada propriedade do elemento (sem os pseudoelementos)."""
        vencedoras: dict[str, tuple[Chave, _Declaracao]] = {}
        candidatas: list[tuple[Chave, _Declaracao]] = []
        for especificidade, ordem, pseudo, indice in self.casador.match(embrulho):
            if pseudo is not None:
                continue
            candidatas += [((int(d.importante), 0, especificidade, ordem), d)
                           for d in self.regras[indice].declaracoes]
        elemento = self.elementos[id(embrulho.etree_element)]
        candidatas += [((int(d.importante), 1, (0, 0, 0), 0), d)
                       for d in _declaracoes_do_estilo(elemento)]
        for chave, declaracao in candidatas:
            atual = vencedoras.get(declaracao.nome)
            if atual is None or chave >= atual[0]:
                vencedoras[declaracao.nome] = (chave, declaracao)
        return vencedoras

    def percorrer(self) -> Iterator[tuple[Elemento, Any]]:
        for embrulho in self.embrulho.iter_subtree():
            yield self.elementos[id(embrulho.etree_element)], embrulho


def _vencedoras_do_estilo(elemento: Elemento) -> dict[str, tuple[Chave, _Declaracao]]:
    """As declarações do `style=""` (sem folha, é a cascata inteira do elemento)."""
    vencedoras: dict[str, tuple[Chave, _Declaracao]] = {}
    for ordem, declaracao in enumerate(_declaracoes_do_estilo(elemento)):
        chave: Chave = (int(declaracao.importante), 1, (0, 0, 0), ordem)
        if declaracao.nome not in vencedoras or chave >= vencedoras[declaracao.nome][0]:
            vencedoras[declaracao.nome] = (chave, declaracao)
    return vencedoras


def _fundo(vencedoras: Mapping[str, tuple[Chave, _Declaracao]],
           variaveis: Mapping[str, str]) -> tuple[float, float, float, float] | None:
    """A cor de fundo que vence (`background-color` ou a do atalho `background`)."""
    candidatas = [(vencedoras[n][0], n, vencedoras[n][1].valor)
                  for n in ("background-color", "background") if n in vencedoras]
    if not candidatas:
        return None
    _, nome, valor = max(candidatas)
    valor = substituir(valor, variaveis) or ""
    for no in tinycss2.parse_component_value_list(valor):
        if no.type in ("whitespace", "comment"):
            continue
        cor = _rgba(no)
        if cor is not None:
            return cor
        if nome == "background-color":
            break
    return (0.0, 0.0, 0.0, 0.0)  # o atalho sem cor, ou a cor que não se lê: transparente


def _compor(cima: tuple[float, float, float, float] | None, baixo: Cor) -> Cor:
    if cima is None:
        return baixo
    alfa = cima[3]
    return tuple(alfa * c + (1 - alfa) * b for c, b in zip(cima[:3], baixo, strict=True))  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# A página
# --------------------------------------------------------------------------- #


def _so_da_raiz(regras: list[_Regra], documento: Documento) -> bool:
    """Toda propriedade personalizada vem de uma regra `:root`/`html` (e de nenhum `style=""`)."""
    for regra in regras:
        if regra.prelude not in RAIZ and any(d.nome.startswith("--") for d in regra.declaracoes):
            return False
    return not any("--" in (e.get("style") or "") for e in documento.elementos())


def _declaracoes_em_texto(declaracoes: Iterable[_Declaracao], variaveis: Mapping[str, str],
                          sobrepor: Mapping[str, str] | None = None) -> str:
    """As declarações para o MuPDF: sem quebra de página, com o `var()` e as cores trocados."""
    partes = []
    for declaracao in declaracoes:
        if declaracao.nome in QUEBRAS or declaracao.nome.startswith("--"):
            continue
        valor = substituir(declaracao.valor, variaveis)
        valor = _valor_invalido(declaracao.nome) if valor is None else valor
        valor = cores_em_hex(valor, nomes=declaracao.nome in PROPRIEDADES_DE_COR)
        partes.append(f"{declaracao.nome}: {valor}{' !important' if declaracao.importante else ''}")
    for nome, valor in (sobrepor or {}).items():
        partes.append(f"{nome}: {cores_em_hex(valor, nomes=nome in PROPRIEDADES_DE_COR)} "
                      "!important")
    return "; ".join(partes)


def _escapar(texto: str, *, atributo: bool = False) -> str:
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return texto.replace('"', "&quot;") if atributo else texto


def _substituto(svg: bytes) -> bytes:
    """Um SVG do tamanho do original: a raiz com o `width`, o `height` e o `viewBox` dele."""
    raiz = _RAIZ_DO_SVG.search(svg[:65536].decode("utf-8", "replace"))
    atributos = "".join(f" {nome}={valor}"
                        for nome, valor in _ATRIBUTO_DO_TAMANHO.findall(raiz.group(0))) \
        if raiz else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg"{atributos}><rect x="-1e5" y="-1e5" '
            'width="2e5" height="2e5" fill="#808080"/></svg>').encode()


class _Escritor:
    """Serializa a cópia que o MuPDF desenha, e guarda o texto do corpo na ordem."""

    def __init__(self, documento: Documento, contexto: Contexto,
                 estilos: Mapping[int, str]) -> None:
        self.documento = documento
        self.contexto = contexto
        self.estilos = estilos
        self.partes: list[str] = []
        self.trechos: list[Trecho] = []
        self.substitutos: dict[str, bytes] = {}
        self.reais: dict[str, bytes] = {}
        self.imagens: list[str | None] = []

    def _imagem(self, elemento: Elemento) -> str | None:
        """O caminho da imagem no `Archive` (o do projeto), ou `None` se ela não está nele."""
        caminho = resolver(self.documento.arquivo, elemento.get("src") or "")
        dados = self.contexto.arquivos.get(caminho) if caminho else None
        if not caminho or not dados:
            return None
        if caminho not in self.reais:
            self.reais[caminho] = dados
            self.substitutos[caminho] = _substituto(dados) if caminho.lower().endswith(".svg") \
                else dados
        return caminho

    def _atributos(self, elemento: Elemento, espaco_pai: str) -> str | None:
        atributos = []
        if elemento.espaco and elemento.espaco != espaco_pai:
            atributos.append(f'xmlns="{_escapar(elemento.espaco, atributo=True)}"')
        for nome, valor in elemento.atributos.items():
            if nome.startswith("{"):
                if nome == XML_LANG and "lang" not in elemento.atributos:
                    atributos.append(f'lang="{_escapar(valor, atributo=True)}"')
                elif nome == XLINK_HREF:
                    atributos.append(f'xlink:href="{_escapar(valor, atributo=True)}"')
                continue
            baixo = nome.lower()
            if baixo.startswith("on") or baixo in ("style", "srcset"):
                continue
            if baixo == "src" and elemento.nome == "img":
                continue
            atributos.append(f'{nome}="{_escapar(valor, atributo=True)}"')
        if elemento.nome == "img":
            caminho = self._imagem(elemento)
            if caminho is None:
                return None  # a imagem que falta: o MuPDF desenharia o alt, que não é texto
            atributos.append(f'src="{_escapar(caminho, atributo=True)}"')
        estilo = self.estilos.get(id(elemento))
        if estilo:
            atributos.append(f'style="{_escapar(estilo, atributo=True)}"')
        return " ".join(atributos)

    def escrever(self, raiz: Elemento) -> str:
        """O texto da cópia; guarda os trechos do corpo e as imagens, na ordem."""
        pilha: list[tuple[Elemento | Trecho | str, str, bool]] = [(raiz, "", False)]
        while pilha:
            no, espaco_pai, no_corpo = pilha.pop()
            if isinstance(no, str):
                self.partes.append(no)
                continue
            if isinstance(no, Trecho):
                self.partes.append(_escapar(no.texto))
                if no_corpo:
                    self.trechos.append(no)
                continue
            if no.nome in (SEM_TEXTO | SEM_DESENHO) and no.espaco in (XHTML, ""):
                continue
            atributos = self._atributos(no, espaco_pai)
            if atributos is None:
                continue
            if no.nome == "img":
                self.imagens.append(resolver(self.documento.arquivo, no.get("src") or ""))
            elif no.nome == "svg" and espaco_pai != no.espaco:
                self.imagens.append(None)
            self.partes.append(f"<{no.nome}{' ' + atributos if atributos else ''}>")
            if no.nome in VAZIOS and not no.filhos:
                continue
            dentro = (no_corpo or no.nome == "body") and no.nome != "svg"
            pilha.append((f"</{no.nome}>", "", False))
            pilha.extend((filho, no.espaco, dentro) for filho in reversed(no.filhos))
        return "".join(self.partes)


Fundo = tuple[float, float, float, float] | None


@dataclass
class _Estilo:
    """O que a cascata dá à cópia.

    As variáveis da folha, o `style=""` de cada elemento, e o fundo do `html` e do `body` (o
    papel).
    """

    variaveis: dict[str, str] = field(default_factory=dict)
    estilos: dict[int, str] = field(default_factory=dict)
    fundo_html: Fundo = None
    fundo_corpo: Fundo = None


def _cor_do_link(elemento: Elemento, vencedoras: Mapping[str, tuple[Chave, _Declaracao]],
                 variaveis: Mapping[str, str]) -> dict[str, str]:
    """A cor que o autor dá ao `<a href>` (a do `a:link` do MuPDF perderia para ela no livro)."""
    if elemento.nome != "a" or elemento.get("href") is None or "color" not in vencedoras:
        return {}
    valor = substituir(vencedoras["color"][1].valor, variaveis)
    return {"color": _valor_invalido("color") if valor is None else valor}


def _estilo_da_raiz(raiz: Elemento, corpo: Elemento | None, regras: list[_Regra]) -> _Estilo:
    """Toda variável é da raiz: uma substituição só, e a cascata do `html` e do `body`."""
    estilo = _Estilo()
    if regras:
        cascata = _Cascata(raiz, regras, rasa=True)
        for elemento, embrulho in cascata.percorrer():
            if elemento is raiz:
                vencedoras = cascata.vencedoras(embrulho)
                estilo.variaveis = _resolver_personalizadas({}, {
                    n: d.valor for n, (_, d) in vencedoras.items() if n.startswith("--")})
                estilo.fundo_html = _fundo(vencedoras, estilo.variaveis)
            elif elemento is corpo:
                estilo.fundo_corpo = _fundo(cascata.vencedoras(embrulho), estilo.variaveis)
    else:  # sem folha: o papel só pode vir do style="" do html ou do body
        estilo.fundo_html = _fundo(_vencedoras_do_estilo(raiz), {})
        estilo.fundo_corpo = _fundo(_vencedoras_do_estilo(corpo), {}) if corpo else None
    for elemento in raiz.elementos():
        if elemento.get("style"):
            estilo.estilos[id(elemento)] = _declaracoes_em_texto(
                _declaracoes_do_estilo(elemento), estilo.variaveis)
    links = [e for e in raiz.elementos() if e.nome == "a" and e.get("href") is not None]
    if links and any(d.nome == "color" for r in regras for d in r.declaracoes):
        # A cor do link pede a cascata do link inteira (os ancestrais dele contam no seletor).
        cascata = _Cascata(raiz, regras)
        alvos = {id(e) for e in links}
        for elemento, embrulho in cascata.percorrer():
            if id(elemento) not in alvos:
                continue
            cor = _cor_do_link(elemento, cascata.vencedoras(embrulho), estilo.variaveis)
            if cor:
                estilo.estilos[id(elemento)] = _declaracoes_em_texto(
                    _declaracoes_do_estilo(elemento), estilo.variaveis, cor)
    return estilo


def _estilo_da_cascata(raiz: Elemento, corpo: Elemento | None, regras: list[_Regra]) -> _Estilo:
    """A cascata elemento a elemento.

    A declaração vencedora com `var()`, resolvida com as variáveis do elemento, vai no
    `style=""` dele.
    """
    estilo = _Estilo()
    cascata = _Cascata(raiz, regras)
    herdadas: dict[int, dict[str, str]] = {}
    for elemento, embrulho in cascata.percorrer():
        vencedoras = cascata.vencedoras(embrulho)
        pai = herdadas.get(id(elemento.pai), {}) if elemento.pai is not None else {}
        proprias = {n: d.valor for n, (_, d) in vencedoras.items() if n.startswith("--")}
        variaveis = _resolver_personalizadas(pai, proprias) if proprias else pai
        herdadas[id(elemento)] = variaveis
        if elemento is raiz:
            estilo.variaveis = variaveis
            estilo.fundo_html = _fundo(vencedoras, variaveis)
        elif elemento is corpo:
            estilo.fundo_corpo = _fundo(vencedoras, variaveis)
        sobrepor = _cor_do_link(elemento, vencedoras, variaveis)
        for nome, (_, declaracao) in vencedoras.items():
            if nome.startswith("--") or nome in QUEBRAS or "var(" not in declaracao.valor:
                continue
            valor = substituir(declaracao.valor, variaveis)
            sobrepor[nome] = _valor_invalido(nome) if valor is None else valor
        if sobrepor or elemento.get("style"):
            estilo.estilos[id(elemento)] = _declaracoes_em_texto(
                _declaracoes_do_estilo(elemento), variaveis, sobrepor)
    return estilo


def preparar(documento: Documento, contexto: Contexto) -> PaginaMedida:
    """A cópia do capítulo que o `Story` desenha para medir o contraste, e o papel dela."""
    raiz = documento.raiz
    if raiz is None:
        return PaginaMedida("", "", BRANCO, [])
    regras = _regras_do_documento(documento, contexto)
    corpo = next((f for f in raiz.filhos if isinstance(f, Elemento) and f.nome == "body"), None)
    estilo = (_estilo_da_raiz if _so_da_raiz(regras, documento) else _estilo_da_cascata)(
        raiz, corpo, regras)
    css = "\n".join(
        f"{regra.prelude} {{ {_declaracoes_em_texto(regra.declaracoes, estilo.variaveis)} }}"
        for regra in regras if regra.declaracoes)
    escritor = _Escritor(documento, contexto, estilo.estilos)
    texto = escritor.escrever(raiz)
    papel = _compor(estilo.fundo_corpo, _compor(estilo.fundo_html, BRANCO))
    return PaginaMedida(texto, css, papel, escritor.trechos, escritor.substitutos,
                        escritor.reais, escritor.imagens)
