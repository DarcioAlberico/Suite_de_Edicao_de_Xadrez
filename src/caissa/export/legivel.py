"""O perfil legível do motor HTML: o XHTML que o Editor HTML/CSS gera, mostra e relê (passo H5).

O contrato é `docs/MARKUP_CAISSA.md`: as classes e os atributos `cb-*` para o xadrez e as poucas
extensões que o livro precisa, HTML semântico para o resto, **nada** de `data-ir`, de classe
gerada (`.pN/.rN/.dN`) ou de dado da máquina. Este módulo tem as três peças que a ida e volta
precisa (spec R2.2a):

- :func:`canon` — a árvore XML com os atributos em ordem e o espaço insignificante normalizado (a
  N4): ``canon(escrever(ler(x))) == canon(x)`` é o portão da volta;
- :class:`EscritorLegivel` — IR → XHTML legível (o capítulo inteiro, e as imagens dos diagramas,
  que são derivadas);
- :func:`ler_capitulo` — XHTML legível → IR. O que o contrato não modela é **preservado**
  (spec R2.3): o elemento desconhecido vira `RawPassthrough`/`RawInline` `xhtml`, e o atributo
  desconhecido vai para `IRNode.html_attributes`.

**O que o XHTML não diz e o IR precisa** — os `id` de proveniência (`p55-3`), os marcadores de
página, a posição de cada nó no PDF — volta pelo **mapa da proveniência** que o escritor devolve
(:attr:`EscritorLegivel.mapa`, o que o projeto guarda em `proveniencia.json`). Sem o mapa, o
leitor guarda esses elementos literalmente (o `id` no nó, o marcador como `RawPassthrough`), e a
volta fecha do mesmo jeito.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from caissa.core.chess.notation_tables import (
    PIECE_TABLES,
    FigurineSet,
    MoveRenderStyle,
    PieceType,
)
from caissa.core.model import (
    Anchor,
    Callout,
    CodeBlock,
    Diagram,
    Document,
    Emphasis,
    Endnote,
    Figure,
    Footnote,
    GameHeaders,
    GameRenderOptions,
    GameScore,
    Group,
    Heading,
    IRNode,
    LineBreak,
    Link,
    ListBlock,
    ListItem,
    MathBlock,
    MathInline,
    MoveNode,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    PageBreak,
    Paragraph,
    ParagraphProps,
    PgnTag,
    PieceGlyph,
    Quote,
    RawInline,
    RawPassthrough,
    RunProps,
    SectionBreak,
    SmallCaps,
    Span,
    Strike,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
    Underline,
)
from caissa.core.model.blocks import ListKind

__all__ = [
    "Capitulo",
    "EscritorLegivel",
    "MapaDaProveniencia",
    "canon",
    "ler_capitulo",
]

XHTML = "http://www.w3.org/1999/xhtml"
EPUB = "http://www.idpf.org/2007/ops"
XML = "http://www.w3.org/XML/1998/namespace"
SVG = "http://www.w3.org/2000/svg"
MATHML = "http://www.w3.org/1998/Math/MathML"
_PREFIXOS = {XHTML: "", EPUB: "epub", XML: "xml", SVG: "svg", MATHML: "m"}

#: Os elementos de bloco: o espaço junto deles é insignificante (a N4).
BLOCOS = frozenset({
    "html", "head", "body", "title", "link", "meta", "style", "section", "header", "footer",
    "div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "dl", "dt", "dd",
    "blockquote", "aside", "pre", "table", "thead", "tbody", "tfoot", "tr", "td", "th",
    "caption", "figure", "figcaption", "nav", "hr", "address", "details", "summary", "main",
    "article",
})

ESTILOS_DO_CONTRATO = {"Movetext": "cb-movetext", "Caption": "cb-caption",
                       "Footnote": "cb-footnote"}
_CLASSE_DO_ESTILO = {v: k for k, v in ESTILOS_DO_CONTRATO.items()}


# --------------------------------------------------------------------------- #
# Nomes, escapes e a forma canônica
# --------------------------------------------------------------------------- #


def _nome(etiqueta: str) -> str:
    """``{ns}local`` → ``local`` (XHTML) ou ``prefixo:local``."""
    if etiqueta.startswith("{"):
        ns, _, local = etiqueta[1:].partition("}")
        prefixo = _PREFIXOS.get(ns)
        if prefixo is None:
            return f"{{{ns}}}{local}"
        return f"{prefixo}:{local}" if prefixo else local
    return etiqueta


def _local(elemento: ET.Element) -> str:
    return _nome(elemento.tag).rpartition(":")[2] if _nome(elemento.tag).startswith(
        ("svg:", "m:", "epub:")) else _nome(elemento.tag)


def _atributos(elemento: ET.Element) -> list[tuple[str, str]]:
    return [(_nome(nome), valor) for nome, valor in elemento.attrib.items()]


def _texto(valor: str) -> str:
    return escape(valor)


def _atributo(nome: str, valor: str) -> str:
    return f" {nome}={quoteattr(valor)}"


def slug(nome: str) -> str:
    """O `slug` do contrato (`caissa.editor.livros.slug`), sem o limite de tamanho da pasta."""
    import unicodedata

    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "estilo"


def _normalizar(elemento: ET.Element) -> None:  # noqa: PLR0912 - as bordas de cada bloco
    """A N4: espaço colapsado, e sem espaço junto das bordas dos blocos."""
    if elemento.text is not None:
        elemento.text = re.sub(r"\s+", " ", elemento.text)
    for filho in elemento:
        _normalizar(filho)
        if filho.tail is not None:
            filho.tail = re.sub(r"\s+", " ", filho.tail)
    if _local(elemento) in BLOCOS or _nome(elemento.tag) == "m:math":
        if elemento.text:
            elemento.text = elemento.text.lstrip()
        if len(elemento):
            ultimo = elemento[-1]
            if ultimo.tail:
                ultimo.tail = ultimo.tail.rstrip()
        elif elemento.text:
            elemento.text = elemento.text.rstrip()
    anterior: ET.Element | None = None
    for filho in elemento:
        if _local(filho) in BLOCOS:
            if anterior is None:
                if elemento.text:
                    elemento.text = elemento.text.rstrip()
            elif anterior.tail:
                anterior.tail = anterior.tail.rstrip()
            if filho.tail:
                filho.tail = filho.tail.lstrip()
        anterior = filho


def _serializar(elemento: ET.Element, *, ordenar: bool) -> str:
    atributos = _atributos(elemento)
    if ordenar:
        atributos.sort()
    cabeca = _nome(elemento.tag) + "".join(_atributo(n, v) for n, v in atributos)
    corpo = _texto(elemento.text or "") + "".join(
        _serializar(f, ordenar=ordenar) + _texto(f.tail or "") for f in elemento)
    if not corpo:
        return f"<{cabeca}/>"
    return f"<{cabeca}>{corpo}</{_nome(elemento.tag)}>"


def canon(texto: str) -> str:
    """A forma canônica do XHTML: atributos em ordem, espaço insignificante normalizado (N4)."""
    raiz = ET.fromstring(texto.encode("utf-8") if isinstance(texto, str) else texto)  # noqa: S314
    _normalizar(raiz)
    return _serializar(raiz, ordenar=True)


def serializar_elemento(elemento: ET.Element) -> str:
    """O elemento como está (sem a cauda), no XHTML sem prefixo: o texto do `RawPassthrough`."""
    return _serializar(elemento, ordenar=False)


# --------------------------------------------------------------------------- #
# O mapa da proveniência e o capítulo
# --------------------------------------------------------------------------- #


@dataclass
class MapaDaProveniencia:
    """O que o XHTML não diz e o IR precisa: por `id` do livro, o nó; e o fólio de cada página.

    O escritor o preenche; o leitor o consulta (o projeto o guarda em `proveniencia.json`).
    """

    nos: dict[str, IRNode] = field(default_factory=dict)
    folios: dict[int, str] = field(default_factory=dict)
    """O fólio impresso, pela página do PDF em base 1."""


@dataclass
class Capitulo:
    """Um arquivo XHTML do livro: o título, as folhas, o idioma e os blocos."""

    blocos: tuple[Any, ...] = ()
    titulo: str = ""
    folhas: tuple[str, ...] = ()
    idioma: str = "pt-BR"


# --------------------------------------------------------------------------- #
# O escritor
# --------------------------------------------------------------------------- #

_NAG = None


def _nag(codigo: int) -> str:
    from caissa.export.text import nag_symbol

    return nag_symbol(codigo)


_LETRA_DO_PECA = {PieceType.KING: "K", PieceType.QUEEN: "Q", PieceType.ROOK: "R",
                  PieceType.BISHOP: "B", PieceType.KNIGHT: "N", PieceType.PAWN: "P"}
_PECA_DA_LETRA = {v: k for k, v in _LETRA_DO_PECA.items()}


def _visivel_da_peca(letra: str, figurinas: bool, conjunto: FigurineSet, idioma: str) -> str:
    """O que o livro imprime na cabeça do lance: a figurina, ou a letra do idioma."""
    if figurinas:
        from caissa.export.text import figurine_char

        return figurine_char(letra, conjunto)
    tabela = PIECE_TABLES.get(idioma.split("-")[0]) or PIECE_TABLES["en"]
    nome = _PECA_DA_LETRA[letra].value
    return str(getattr(tabela, nome))


class EscritorLegivel:
    """IR → XHTML legível, pelo contrato (`docs/MARKUP_CAISSA.md`)."""

    def __init__(self, documento: Document | None = None, *,
                 folios: Mapping[int, str] | None = None) -> None:
        self.documento = documento or Document()
        self.idioma = self.documento.metadata.language or "pt-BR"
        self.mapa = MapaDaProveniencia(folios=dict(folios or {}))
        self.imagens: dict[str, str] = {}
        """As imagens derivadas dos diagramas: `dg_<hash>.svg` → o SVG."""
        self._pagina: int | None = None
        self._ordem: dict[tuple[int, str], int] = {}

    # -- o arquivo --------------------------------------------------------

    def capitulo(self, capitulo: Capitulo) -> str:
        linhas = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE html>",
                  f'<html xmlns="{XHTML}" xmlns:epub="{EPUB}"'
                  f"{_atributo('lang', capitulo.idioma)}{_atributo('xml:lang', capitulo.idioma)}>",
                  "<head>", f"<title>{_texto(capitulo.titulo)}</title>"]
        linhas += [f'<link rel="stylesheet" type="text/css" href={quoteattr(folha)}/>'
                   for folha in capitulo.folhas]
        linhas += ["</head>", "<body>", self.blocos(capitulo.blocos), "</body>", "</html>", ""]
        return "\n".join(linha for linha in linhas if linha != "")+"\n"

    # -- os blocos --------------------------------------------------------

    def blocos(self, blocos: Iterable[Any], *, no_topo: bool = True) -> str:
        partes = []
        for bloco in blocos:
            if no_topo:
                marcador = self._marcador(bloco)
                if marcador:
                    partes.append(marcador)
            partes.append(self.bloco(bloco, no_topo=no_topo))
        return "\n".join(p for p in partes if p)

    def _marcador(self, bloco: Any) -> str:
        from caissa.editor.paginas import marcador_de_pagina, pagina_da_janela

        proveniencia = getattr(bloco, "provenance", None)
        indice = getattr(proveniencia, "page_index", None)
        if indice is None:
            return ""
        pagina = pagina_da_janela(int(indice))
        if pagina == self._pagina:
            return ""
        self._pagina = pagina
        return marcador_de_pagina(pagina, self.mapa.folios.get(pagina))

    def _id(self, no: Any, tipo: str, *, no_topo: bool) -> str | None:
        """O `id` do bloco: o que o arquivo trazia, a âncora, ou o da proveniência (`p55-3`)."""
        from caissa.editor.paginas import id_de_bloco, id_de_diagrama, id_de_partida

        proprio = dict(no.html_attributes).get("id")
        if proprio:
            return proprio
        ancora = getattr(no, "anchor", None)
        if ancora:
            return str(ancora)
        proveniencia = getattr(no, "provenance", None)
        indice = getattr(proveniencia, "page_index", None)
        if not no_topo or indice is None:
            return None
        pagina = int(indice) + 1
        chave = (pagina, tipo)
        self._ordem[chave] = self._ordem.get(chave, 0) + 1
        n = self._ordem[chave]
        ident = {"b": id_de_bloco, "d": id_de_diagrama, "g": id_de_partida}[tipo](pagina, n)
        self.mapa.nos[ident] = no
        return ident

    def _abrir(self, etiqueta: str, no: Any, *, classes: Sequence[str] = (),
               atributos: Sequence[tuple[str, str]] = (), ident: str | None = None) -> str:
        """A etiqueta de abertura, com os atributos na ordem do contrato.

        O `id`, as classes do contrato mais as extras, os atributos do contrato e os preservados
        (`html_attributes`).
        """
        extras = [(n, v) for n, v in no.html_attributes if n not in ("id", "class")]
        classe_extra = dict(no.html_attributes).get("class", "")
        todas = " ".join(c for c in (*classes, classe_extra) if c)
        texto = f"<{etiqueta}"
        if ident:
            texto += _atributo("id", ident)
        if todas:
            texto += _atributo("class", todas)
        for nome, valor in (*atributos, *extras):
            texto += _atributo(nome, valor)
        return texto + ">"

    def bloco(self, no: Any, *, no_topo: bool = False) -> str:  # noqa: PLR0911, PLR0912
        if isinstance(no, Heading):
            return self._titulo(no, no_topo=no_topo)
        if isinstance(no, Paragraph):
            return self._paragrafo(no, no_topo=no_topo)
        if isinstance(no, Diagram):
            return self._diagrama(no, no_topo=no_topo)
        if isinstance(no, GameScore):
            return _EscritorDePartida(self).partida(no, self._id(no, "g", no_topo=no_topo))
        if isinstance(no, RawPassthrough):
            if no.format == "xhtml":
                return no.text
            return (self._abrir("pre", no, classes=("cb-raw",),
                                atributos=(("data-format", no.format),))
                    + _texto(no.text) + "</pre>")
        if isinstance(no, Footnote | Endnote):
            tipo = "footnote" if isinstance(no, Footnote) else "endnote"
            abre = self._abrir("aside", no, atributos=(
                ("epub:type", tipo), ("role", f"doc-{tipo}")), ident=no.ref or None)
            return f"{abre}\n{self.blocos(no.content, no_topo=False)}\n</aside>"
        if isinstance(no, Quote):
            rodape = (f"\n<footer>{self.inlines(no.attribution)}</footer>"
                      if no.attribution else "")
            return (f"{self._abrir('blockquote', no)}\n{self.blocos(no.content, no_topo=False)}"
                    f"{rodape}\n</blockquote>")
        if isinstance(no, ListBlock):
            return self._lista(no)
        if isinstance(no, ThematicBreak):
            return self._abrir("hr", no)[:-1] + "/>"
        if isinstance(no, SectionBreak):
            return self._abrir("hr", no, classes=("cb-section-break",))[:-1] + "/>"
        if isinstance(no, PageBreak):
            return self._abrir("div", no, classes=("cb-page-break",)) + "</div>"
        if isinstance(no, CodeBlock):
            return f"{self._abrir('pre', no)}<code>{_texto(no.text)}</code></pre>"
        if isinstance(no, Group):
            classes = ("cb-chapter",) if no.role == "chapter" else ()
            ident = self._id(no, "b", no_topo=False)
            return (f"{self._abrir('section' if no.role == 'chapter' else 'div', no, classes=classes, ident=ident)}\n"  # noqa: E501
                    f"{self.blocos(no.content, no_topo=False)}\n"
                    f"</{'section' if no.role == 'chapter' else 'div'}>")
        if isinstance(no, Callout):
            titulo = (f'<p class="cb-callout-title">{self.inlines(no.title)}</p>\n'
                      if no.title else "")
            return (f"{self._abrir('aside', no, classes=('cb-callout',), atributos=(('data-kind', str(no.kind)),))}\n"  # noqa: E501
                    f"{titulo}{self.blocos(no.content, no_topo=False)}\n</aside>")
        if isinstance(no, MathBlock):
            return f'<m:math xmlns:m="{MATHML}" display="block">{_texto(no.latex)}</m:math>'
        if isinstance(no, Figure):
            legenda = f"\n<figcaption>{self.inlines(no.caption)}</figcaption>" if no.caption else ""
            return (f"{self._abrir('figure', no, ident=self._id(no, 'b', no_topo=False))}\n"
                    f"{self.blocos(no.content, no_topo=False)}{legenda}\n</figure>")
        return f"<!-- sem forma legível: {type(no).__name__} -->"

    def _titulo(self, no: Heading, *, no_topo: bool) -> str:
        nivel = max(1, min(6, no.level))
        numero = (f'<span class="cb-heading-number">{_texto(no.numbering_text)}</span> '
                  if no.numbering_text else "")
        return (self._abrir(f"h{nivel}", no, ident=self._id(no, "b", no_topo=no_topo))
                + numero + self.inlines(no.content) + f"</h{nivel}>")

    def _paragrafo(self, no: Paragraph, *, no_topo: bool) -> str:
        classes: list[str] = []
        estilo = no.props.style
        if estilo:
            classes.append(ESTILOS_DO_CONTRATO.get(estilo) or f"cb-style-{slug(estilo)}")
        atributos: list[tuple[str, str]] = []
        if no.drop_cap:
            classes.append("cb-dropcap")
            atributos.append(("data-drop-cap", str(no.drop_cap)))
        return (self._abrir("p", no, classes=classes, atributos=atributos,
                            ident=self._id(no, "b", no_topo=no_topo))
                + self.inlines(no.content) + "</p>")

    def _lista(self, no: ListBlock) -> str:
        if no.kind is ListKind.DEFINITION:
            itens = []
            for item in no.items:
                itens.append(f"<dt>{self.inlines(item.term)}</dt>")
                itens.append(f"<dd>{self.blocos(item.content, no_topo=False)}</dd>")
            return f"{self._abrir('dl', no)}\n" + "\n".join(itens) + "\n</dl>"
        ordenada = no.kind is ListKind.ORDERED
        atributos = (("start", str(no.start)),) if ordenada and no.start != 1 else ()
        etiqueta = "ol" if ordenada else "ul"
        itens = [f"{self._abrir('li', item)}{self._conteudo_do_item(item)}</li>"
                 for item in no.items]
        return (f"{self._abrir(etiqueta, no, atributos=atributos)}\n" + "\n".join(itens)
                + f"\n</{etiqueta}>")

    def _conteudo_do_item(self, item: ListItem) -> str:
        if len(item.content) == 1 and isinstance(item.content[0], Paragraph) and not (
                item.content[0].html_attributes or item.content[0].props.style):
            return self.inlines(item.content[0].content)
        return self.blocos(item.content, no_topo=False)

    # -- o diagrama -------------------------------------------------------

    def _diagrama(self, no: Diagram, *, no_topo: bool) -> str:
        from caissa.export.diagrams import _reading_status, descrever_posicao

        fen = no.fen or ""
        campos = fen.split()
        stm = campos[1] if len(campos) > 1 and campos[1] in ("w", "b") else "w"
        orientacao = "black" if str(no.orientation.value) == "black" else "white"
        chave = hashlib.sha256(f"{fen}|{orientacao}".encode()).hexdigest()[:12]
        nome = f"dg_{chave}.svg"
        if nome not in self.imagens:
            self.imagens[nome] = self._svg(no)
        alt = no.alt_text
        if not alt:
            desconhecida, lado_desconhecido, _ = _reading_status(no)
            conferida = bool(no.verified_by_human or getattr(no.provenance, "verified_by_human",
                                                             False))
            alt = descrever_posicao(None if desconhecida else fen,
                                    None if lado_desconhecido else stm, self.idioma,
                                    conferida or no.recognition is None)
        atributos = [("data-fen", fen), ("data-stm", stm), ("data-mode", "svg"),
                     ("data-orientation", orientacao)]
        legenda = []
        rotulo = no.label or (f"Diagrama {no.number}" if no.number is not None else "")
        if rotulo:
            legenda.append(f'<span class="cb-diagram-label">{_texto(rotulo)}</span>')
        if no.stipulation:
            legenda.append(f'<span class="cb-stipulation">{_texto(no.stipulation)}</span>')
        if no.move_context:
            legenda.append(f'<span class="cb-move-context">{_texto(no.move_context)}</span>')
        if no.caption:
            legenda.append(f'<span class="cb-caption-text">{self.inlines(no.caption)}</span>')
        if no.side_to_move_indicator:
            falado = {"w": "Brancas jogam", "b": "Pretas jogam"} if not self.idioma.startswith(
                "en") else {"w": "White to move", "b": "Black to move"}
            legenda.append(f'<span class="cb-stm-marker" aria-label="{falado[stm]}"></span>')
        corpo = f'  <img class="cb-svg" src="../Images/{nome}" alt={quoteattr(alt)}/>'
        if legenda:
            corpo += ('\n  <figcaption class="cb-diagram-caption">\n    '
                      + "\n    ".join(legenda) + "\n  </figcaption>")
        abre = self._abrir("figure", no, classes=("cb-diagram",), atributos=atributos,
                           ident=self._id(no, "d", no_topo=no_topo))
        return f"{abre}\n{corpo}\n</figure>"

    def _svg(self, no: Diagram) -> str:
        from caissa.export.base import ExportContext
        from caissa.export.diagrams import DiagramRenderer
        from caissa.export.profiles import HTML_PROFILE

        contexto = ExportContext(HTML_PROFILE, self.documento)
        try:
            return DiagramRenderer(contexto, tinta_do_leitor=True).svg(no).svg
        except Exception:  # noqa: BLE001 - a imagem é derivada; a FEN fica no XHTML
            return ""

    # -- dentro do parágrafo ---------------------------------------------

    def inlines(self, inlines: Iterable[Any]) -> str:
        return "".join(self.inline(no) for no in inlines)

    def _envolver(self, etiqueta: str, no: Any, conteudo: str, **kw: Any) -> str:
        return self._abrir(etiqueta, no, **kw) + conteudo + f"</{etiqueta}>"

    def inline(self, no: Any) -> str:  # noqa: PLR0911, PLR0912 - um ramo por nó
        if isinstance(no, Text):
            return self._texto_com_props(no)
        simples = {Emphasis: "em", Strong: "strong", Underline: "u", Strike: "s",
                   Superscript: "sup", Subscript: "sub"}
        for classe, etiqueta in simples.items():
            if isinstance(no, classe):
                return self._envolver(etiqueta, no, self.inlines(no.content))
        if isinstance(no, SmallCaps):
            return self._envolver("span", no, self.inlines(no.content),
                                  classes=("cb-smallcaps",))
        if isinstance(no, Span):
            return self._span(no)
        if isinstance(no, NoteRef):
            return self._envolver("a", no, _texto(no.marker or ""), classes=("cb-noteref",),
                                  atributos=(("epub:type", "noteref"), ("role", "doc-noteref"),
                                             ("href", f"#{no.ref}")))
        if isinstance(no, Link):
            return self._envolver("a", no, self.inlines(no.content),
                                  atributos=(("href", no.target),))
        if isinstance(no, Anchor):
            return self._abrir("span", no, ident=no.name) + "</span>"
        if isinstance(no, LineBreak):
            return self._abrir("br", no)[:-1] + "/>"
        if isinstance(no, NonBreakingSpace):
            return " "
        if isinstance(no, RawInline):
            return no.text if no.format == "xhtml" else _texto(no.text)
        if isinstance(no, PieceGlyph):
            letra = _LETRA_DO_PECA.get(no.piece, "N")
            from caissa.export.text import figurine_char

            return self._envolver("span", no, _texto(figurine_char(letra, no.figurine_set)),
                                  classes=("cb-piece",), atributos=(("data-piece", letra),))
        if isinstance(no, NagSymbol):
            return self._envolver("span", no, _texto(_nag(no.nag)), classes=("cb-nag",),
                                  atributos=(("data-nag", str(no.nag)),))
        if isinstance(no, MathInline):
            return f'<m:math xmlns:m="{MATHML}">{_texto(no.latex)}</m:math>'
        return _texto(getattr(no, "text", "") or getattr(no, "content", "") or "")

    def _span(self, no: Span) -> str:
        classes = (f"cb-style-{slug(no.props.style)}",) if no.props.style else ()
        atributos: tuple[tuple[str, str], ...] = ()
        if no.props.language:
            atributos = (("lang", no.props.language), ("xml:lang", no.props.language))
        return self._envolver("span", no, self.inlines(no.content), classes=classes,
                              atributos=atributos)

    def _texto_com_props(self, no: Text) -> str:
        """O texto, com as `RunProps` que o contrato expressa: a semântica e a língua (N1)."""
        conteudo = _texto(no.content)
        props = no.props
        if no.html_attributes:
            conteudo = self._envolver("span", no, conteudo)
        embrulhos: list[tuple[str, tuple[str, ...], tuple[tuple[str, str], ...]]] = []
        if props.language:
            embrulhos.append(("span", (), (("lang", props.language),
                                           ("xml:lang", props.language))))
        if props.style:
            embrulhos.append(("span", (f"cb-style-{slug(props.style)}",), ()))
        for texto in reversed(embrulhos):
            etiqueta, classes, atributos = texto
            classe = f" class={quoteattr(' '.join(classes))}" if classes else ""
            attrs = "".join(_atributo(n, v) for n, v in atributos)
            conteudo = f"<{etiqueta}{classe}{attrs}>{conteudo}</{etiqueta}>"
        return conteudo


class _EscritorDePartida:
    """A partida no contrato do CB: cabeçalho, linhas de lances, comentários e variantes."""

    def __init__(self, escritor: EscritorLegivel) -> None:
        self.escritor = escritor

    def partida(self, no: GameScore, ident: str | None) -> str:
        import chess

        cabecalhos = no.headers
        extras = {t.name: t.value for t in cabecalhos.extra}
        atributos = []
        if extras.get("ECO"):
            atributos.append(("data-eco", extras["ECO"]))
        # O resultado: o `data-result` quando se sabe; o `p.cb-result` quando, além disso, a
        # partida o imprime (`show_result`). Um resultado desconhecido (`*`) não se escreve.
        conhecido = cabecalhos.result not in ("", "*")
        if conhecido:
            atributos.append(("data-result", cabecalhos.result))
        if no.initial_fen and no.initial_fen != chess.STARTING_FEN:
            atributos.append(("data-initial-fen", no.initial_fen))
        partes = [self.escritor._abrir("section", no, classes=("cb-game",),
                                       atributos=atributos, ident=ident)]
        if no.render.show_headers:
            cabecalho = self._cabecalho(no, extras)
            if cabecalho:
                partes.append(cabecalho)
        partes.append('<div class="cb-moves">')
        tabuleiro = chess.Board(no.initial_fen) if no.initial_fen else chess.Board()
        if no.initial_comment:
            partes.append(f'<p class="cb-comment">{_texto(no.initial_comment)}</p>')
        self._linhas(no.children, tabuleiro, 0, partes, no.render)
        partes.append("</div>")
        if conhecido and no.render.show_result:
            partes.append(f'<p class="cb-result">{_texto(cabecalhos.result)}</p>')
        partes.append("</section>")
        return "\n".join(partes)

    def _cabecalho(self, no: GameScore, extras: Mapping[str, str]) -> str:
        h = no.headers
        linhas = ['<header class="cb-game-header">']
        if extras.get("GameNumber"):
            linhas.append(f'<p class="cb-game-number">{_texto(extras["GameNumber"])}</p>')
        for cor, nome, elo in (("cb-white", h.white, extras.get("WhiteElo")),
                               ("cb-black", h.black, extras.get("BlackElo"))):
            if nome and nome != "?":
                elo_html = f'<span class="cb-elo">{_texto(elo)}</span> ' if elo else ""
                linhas.append(f'<p class="cb-player {cor}">{elo_html}'
                              f'<span class="cb-name">{_texto(nome)}</span></p>')
        evento = []
        if h.event and h.event != "?":
            evento.append(f'<span class="cb-event-name">{_texto(h.event)}</span>')
        if h.site and h.site != "?":
            evento.append(f'<span class="cb-site">{_texto(h.site)}</span>')
        if h.round and h.round != "?":
            evento.append(f'<span class="cb-round">({_texto(h.round)})</span>')
        if h.date and h.date != "????.??.??":
            iso = h.date.replace(".", "-")
            evento.append(f'<time class="cb-date" datetime={quoteattr(iso)}>{_texto(h.date)}'
                          "</time>")
        if evento:
            linhas.append('<p class="cb-event">' + " ".join(evento) + "</p>")
        abertura = []
        if extras.get("Opening"):
            abertura.append(f'<span class="cb-opening-name">{_texto(extras["Opening"])}</span>')
        if extras.get("ECO"):
            abertura.append(f'<span class="cb-eco">{_texto(extras["ECO"])}</span>')
        if abertura:
            linhas.append('<p class="cb-opening">' + " ".join(abertura) + "</p>")
        if no.annotator:
            linhas.append(f'<p class="cb-annotator">{_texto(no.annotator)}</p>')
        linhas.append("</header>")
        return "\n".join(linhas) if len(linhas) > 2 else ""  # noqa: PLR2004 - abre e fecha

    def _linhas(self, filhos: Sequence[MoveNode], tabuleiro: Any, profundidade: int,
                partes: list[str], render: GameRenderOptions) -> None:
        """Uma linha de lances; o comentário e as variantes quebram o parágrafo."""
        classe = ("cb-line cb-mainline" if profundidade == 0
                  else f"cb-line cb-variation cb-depth-{profundidade}")
        fichas: list[str] = []
        primeiro = True
        atual = tuple(filhos)
        while atual:
            principal = atual[0]
            if principal.comment_before:
                if fichas:
                    partes.append(f'<p class="{classe}">' + " ".join(fichas) + "</p>")
                    fichas = []
                partes.append(f'<p class="cb-comment">{_texto(principal.comment_before)}</p>')
                primeiro = True
            antes = tabuleiro.copy()
            fichas += self._lance(principal, tabuleiro, primeiro, render)
            primeiro = False
            quebra = bool(principal.comment_after) or len(atual) > 1
            if quebra:
                partes.append(f'<p class="{classe}">' + " ".join(fichas) + "</p>")
                fichas = []
                if principal.comment_after:
                    partes.append(f'<p class="cb-comment">{_texto(principal.comment_after)}</p>')
                for variante in atual[1:]:
                    self._linhas((variante,), antes.copy(), profundidade + 1, partes, render)
                primeiro = True
            atual = principal.children
        if fichas:
            partes.append(f'<p class="{classe}">' + " ".join(fichas) + "</p>")

    def _lance(self, no: MoveNode, tabuleiro: Any, primeiro: bool,
               render: GameRenderOptions) -> list[str]:
        import chess

        fichas = []
        numero = tabuleiro.fullmove_number
        if tabuleiro.turn == chess.WHITE:
            fichas.append(f'<span class="cb-movenum">{numero}.</span>')
        elif primeiro:
            fichas.append(f'<span class="cb-movenum">{numero}…</span>')
        lance = tabuleiro.parse_san(no.san) if not no.uci else chess.Move.from_uci(no.uci)
        san = tabuleiro.san(lance)
        peca = tabuleiro.piece_at(lance.from_square)
        tabuleiro.push(lance)
        corpo = _texto(san)
        if peca is not None and peca.piece_type != chess.PAWN and not san.startswith("O-O"):
            letra = san[0]
            visivel = _visivel_da_peca(letra, render.render is MoveRenderStyle.FIGURINE,
                                       render.figurine_set, render.language)
            corpo = (f'<span class="cb-piece" data-piece="{letra}">{_texto(visivel)}</span>'
                     f"{_texto(san[1:])}")
        fichas.append(f'<span class="cb-move" data-uci="{lance.uci()}" '
                      f'data-fen="{tabuleiro.fen()}">{corpo}</span>')
        fichas += [f'<span class="cb-nag" data-nag="{n}">{_texto(_nag(n))}</span>'
                   for n in no.nags]
        return fichas


# --------------------------------------------------------------------------- #
# O leitor
# --------------------------------------------------------------------------- #

_ID_DE_BLOCO = re.compile(r"^p[1-9]\d*-[dg]?[1-9]\d*$")
_MARCADOR = re.compile(r"^pg[1-9]\d*$")
_ROTULO_NUMERADO = re.compile(r"^Diagrama (\d+)$")


def _classes(elemento: ET.Element) -> list[str]:
    return (elemento.get("class") or "").split()


def _preservados(elemento: ET.Element, *, conhecidos: Iterable[str] = (),
                 classes_conhecidas: Iterable[str] = (), guardar_id: bool = True
                 ) -> tuple[tuple[str, str], ...]:
    """Os atributos que o contrato não modela neste elemento, para `html_attributes`."""
    fora = set(conhecidos)
    if not guardar_id:
        fora.add("id")
    pares = []
    for nome, valor in _atributos(elemento):
        if nome == "class":
            extras = [c for c in valor.split() if c not in set(classes_conhecidas)]
            if extras:
                pares.append(("class", " ".join(extras)))
        elif nome not in fora:
            pares.append((nome, valor))
    return tuple(pares)


class _Leitor:
    """XHTML legível → IR, pelo contrato; o resto, preservado."""

    def __init__(self, mapa: MapaDaProveniencia | None, estilos: Iterable[str] = (),
                 idioma: str = "pt-BR") -> None:
        self.mapa = mapa
        self.idioma = idioma
        self.estilo_do_slug = {slug(nome): nome for nome in estilos}

    # -- identidade ------------------------------------------------------

    def _identidade(self, elemento: ET.Element) -> dict[str, Any]:
        """O `id` e a proveniência do nó pelo mapa; sem o mapa, o `id` fica no nó."""
        ident = elemento.get("id")
        if ident and self.mapa is not None and ident in self.mapa.nos:
            original = self.mapa.nos[ident]
            return {"id": original.id, "provenance": original.provenance, "_guardar_id": False}
        return {"_guardar_id": True}

    @staticmethod
    def _limpar(kw: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in kw.items() if not k.startswith("_")}

    # -- blocos ----------------------------------------------------------

    def blocos(self, pai: ET.Element) -> list[Any]:
        resultado: list[Any] = []
        for filho in pai:
            no = self.bloco(filho)
            if no is not None:
                resultado.append(no)
        return resultado

    def bloco(self, elemento: ET.Element) -> Any:  # noqa: PLR0911, PLR0912 - um ramo por forma
        nome = _local(elemento)
        classes = _classes(elemento)
        if nome in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return self._titulo(elemento, int(nome[1]))
        if nome == "p":
            return self._paragrafo(elemento)
        if nome == "figure" and "cb-diagram" in classes:
            return self._diagrama(elemento)
        if nome == "section" and "cb-game" in classes:
            return _LeitorDePartida(self).partida(elemento)
        if nome == "section" and "cb-chapter" in classes:
            ident = self._identidade(elemento)
            return Group(role="chapter", content=tuple(self.blocos(elemento)),
                         anchor=elemento.get("id") if ident["_guardar_id"] else None,
                         html_attributes=_preservados(elemento, conhecidos=("id",),
                                                      classes_conhecidas=("cb-chapter",)),
                         **self._limpar(ident))
        if nome == "aside" and elemento.get(f"{{{EPUB}}}type") in ("footnote", "endnote"):
            classe = Footnote if elemento.get(f"{{{EPUB}}}type") == "footnote" else Endnote
            return classe(ref=elemento.get("id") or "", content=tuple(self.blocos(elemento)),
                          html_attributes=_preservados(
                              elemento, conhecidos=("id", "epub:type", "role")))
        if nome == "blockquote":
            rodape = next((f for f in elemento if _local(f) == "footer"), None)
            corpo = [f for f in elemento if f is not rodape]
            falso = ET.Element(elemento.tag)
            falso.extend(corpo)
            return Quote(content=tuple(self.blocos(falso)),
                         attribution=tuple(self.inlines(rodape)) if rodape is not None else (),
                         html_attributes=_preservados(elemento))
        if nome in ("ul", "ol", "dl"):
            return self._lista(elemento, nome)
        if nome == "hr":
            if "cb-section-break" in classes:
                return SectionBreak(html_attributes=_preservados(
                    elemento, classes_conhecidas=("cb-section-break",)))
            return ThematicBreak(html_attributes=_preservados(elemento))
        if nome == "div" and "cb-page-break" in classes and not len(elemento):
            return PageBreak(html_attributes=_preservados(
                elemento, classes_conhecidas=("cb-page-break",)))
        if nome == "pre" and "cb-raw" in classes:
            return RawPassthrough(format=elemento.get("data-format") or "text",
                                  text="".join(elemento.itertext()))
        if nome == "pre" and len(elemento) == 1 and _local(elemento[0]) == "code" and not (
                elemento.text or "").strip():
            return CodeBlock(text="".join(elemento[0].itertext()),
                             html_attributes=_preservados(elemento))
        if nome == "div" and not classes and elemento.attrib == {}:
            return Group(content=tuple(self.blocos(elemento)))
        return RawPassthrough(format="xhtml", text=serializar_elemento(elemento))

    def _titulo(self, elemento: ET.Element, nivel: int) -> Heading:
        ident = self._identidade(elemento)
        numero = None
        filhos = list(elemento)
        texto_inicial = elemento.text
        if filhos and "cb-heading-number" in _classes(filhos[0]) and not (
                texto_inicial or "").strip():
            numero = "".join(filhos[0].itertext())
            resto = ET.Element(elemento.tag)
            resto.text = (filhos[0].tail or "")[1:] if (filhos[0].tail or "").startswith(
                " ") else filhos[0].tail
            resto.extend(filhos[1:])
            conteudo = self.inlines(resto)
        else:
            conteudo = self.inlines(elemento)
        return Heading(level=nivel, content=tuple(conteudo), numbering_text=numero,
                       html_attributes=_preservados(elemento,
                                                    guardar_id=ident["_guardar_id"]),
                       **self._limpar(ident))

    def _paragrafo(self, elemento: ET.Element) -> Paragraph:
        ident = self._identidade(elemento)
        classes = _classes(elemento)
        estilo = None
        conhecidas: list[str] = []
        for classe in classes:
            if estilo is None and classe in _CLASSE_DO_ESTILO:
                estilo = _CLASSE_DO_ESTILO[classe]
                conhecidas.append(classe)
            elif estilo is None and classe.startswith("cb-style-"):
                pedaco = classe.removeprefix("cb-style-")
                estilo = self.estilo_do_slug.get(pedaco, pedaco)
                conhecidas.append(classe)
        drop = elemento.get("data-drop-cap")
        conhecidos = ["data-drop-cap"] if drop and "cb-dropcap" in classes else []
        if conhecidos:
            conhecidas.append("cb-dropcap")
        return Paragraph(content=tuple(self.inlines(elemento)),
                         props=ParagraphProps(style=estilo) if estilo else ParagraphProps(),
                         drop_cap=int(drop) if conhecidos else None,
                         html_attributes=_preservados(elemento, conhecidos=conhecidos,
                                                      classes_conhecidas=conhecidas,
                                                      guardar_id=ident["_guardar_id"]),
                         **self._limpar(ident))

    def _lista(self, elemento: ET.Element, nome: str) -> ListBlock:
        if nome == "dl":
            itens = []
            filhos = list(elemento)
            for termo, definicao in zip(filhos[::2], filhos[1::2], strict=False):
                itens.append(ListItem(term=tuple(self.inlines(termo)),
                                      content=tuple(self._conteudo_do_item(definicao))))
            return ListBlock(kind=ListKind.DEFINITION, items=tuple(itens),
                             html_attributes=_preservados(elemento))
        itens = [ListItem(content=tuple(self._conteudo_do_item(li)),
                          html_attributes=_preservados(li)) for li in elemento
                 if _local(li) == "li"]
        inicio = int(elemento.get("start") or 1)
        return ListBlock(kind=ListKind.ORDERED if nome == "ol" else ListKind.BULLET,
                         items=tuple(itens), start=inicio,
                         html_attributes=_preservados(elemento, conhecidos=("start",)))

    def _conteudo_do_item(self, item: ET.Element) -> list[Any]:
        if any(_local(f) in BLOCOS for f in item):
            return self.blocos(item)
        return [Paragraph(content=tuple(self.inlines(item)))]

    def _diagrama(self, elemento: ET.Element) -> Diagram:
        from caissa.core.model import Orientation

        ident = self._identidade(elemento)
        img = next((f for f in elemento.iter() if _local(f) == "img"), None)
        legenda = next((f for f in elemento if _local(f) == "figcaption"), None)
        partes = {c: f for f in (legenda if legenda is not None else [])
                  for c in _classes(f)}
        rotulo = "".join(partes["cb-diagram-label"].itertext()) if "cb-diagram-label" in partes \
            else None
        numero = None
        if rotulo and (casado := _ROTULO_NUMERADO.match(rotulo)):
            numero, rotulo = int(casado.group(1)), None
        texto = ("".join(partes[c].itertext()) if c in partes else None for c in (
            "cb-stipulation", "cb-move-context"))
        estipulacao, contexto = texto
        legenda_livre = tuple(self.inlines(partes["cb-caption-text"])) \
            if "cb-caption-text" in partes else ()
        return Diagram(
            fen=elemento.get("data-fen") or "",
            orientation=Orientation.BLACK if elemento.get("data-orientation") == "black"
            else Orientation.WHITE,
            number=numero, label=rotulo, stipulation=estipulacao, move_context=contexto,
            caption=legenda_livre,
            side_to_move_indicator="cb-stm-marker" in partes,
            alt_text=img.get("alt") if img is not None else None,
            html_attributes=_preservados(
                elemento, conhecidos=("data-fen", "data-stm", "data-mode", "data-orientation"),
                classes_conhecidas=("cb-diagram",), guardar_id=ident["_guardar_id"]),
            **self._limpar(ident))

    # -- dentro do parágrafo --------------------------------------------

    def inlines(self, elemento: ET.Element | None) -> list[Any]:
        if elemento is None:
            return []
        resultado: list[Any] = []
        self._texto_solto(elemento.text, resultado)
        for filho in elemento:
            no = self.inline(filho)
            if no is not None:
                resultado.append(no)
            self._texto_solto(filho.tail, resultado)
        return resultado

    @staticmethod
    def _texto_solto(texto: str | None, resultado: list[Any]) -> None:
        if not texto:
            return
        pedacos = texto.split(" ")
        for indice, pedaco in enumerate(pedacos):
            if indice:
                resultado.append(NonBreakingSpace())
            if pedaco:
                resultado.append(Text(content=pedaco))

    def inline(self, elemento: ET.Element) -> Any:  # noqa: PLR0911 - um ramo por forma
        nome = _local(elemento)
        classes = _classes(elemento)
        simples = {"em": Emphasis, "strong": Strong, "u": Underline, "s": Strike,
                   "sup": Superscript, "sub": Subscript}
        if nome in simples:
            return simples[nome](content=tuple(self.inlines(elemento)),
                                 html_attributes=_preservados(elemento))
        if (nome == "span" and classes == ["cb-smallcaps"]) or (
                nome == "span" and "cb-smallcaps" in classes):
            return SmallCaps(content=tuple(self.inlines(elemento)),
                             html_attributes=_preservados(
                                 elemento, classes_conhecidas=("cb-smallcaps",)))
        if nome == "span" and "cb-piece" in classes:
            from caissa.export.text import figurine_char

            letra = elemento.get("data-piece") or "N"
            visivel = "".join(elemento.itertext())
            conjunto = FigurineSet.BLACK if visivel == figurine_char(letra, FigurineSet.BLACK) \
                else FigurineSet.WHITE
            return PieceGlyph(piece=_PECA_DA_LETRA.get(letra, PieceType.KNIGHT),
                              figurine_set=conjunto,
                              html_attributes=_preservados(
                                  elemento, conhecidos=("data-piece",),
                                  classes_conhecidas=("cb-piece",)))
        if nome == "span" and "cb-nag" in classes and (elemento.get("data-nag") or "").isdigit():
            return NagSymbol(nag=int(elemento.get("data-nag") or 0),
                             html_attributes=_preservados(elemento, conhecidos=("data-nag",),
                                                          classes_conhecidas=("cb-nag",)))
        if nome == "span" and elemento.get("id") and not len(elemento) and not elemento.text \
                and set(elemento.attrib) == {"id"}:
            return Anchor(name=elemento.get("id") or "")
        if nome == "span" and not any(c for c in classes if c.startswith("cb-") and not
                                      c.startswith("cb-style-")):
            return self._span(elemento, classes)
        if nome == "a" and "cb-noteref" in classes:
            return NoteRef(ref=(elemento.get("href") or "").lstrip("#"),
                           marker="".join(elemento.itertext()),
                           html_attributes=_preservados(
                               elemento, conhecidos=("href", "epub:type", "role"),
                               classes_conhecidas=("cb-noteref",)))
        if nome == "a" and elemento.get("href"):
            return Link(target=elemento.get("href") or "", content=tuple(self.inlines(elemento)),
                        html_attributes=_preservados(elemento, conhecidos=("href",)))
        if nome == "br":
            return LineBreak(html_attributes=_preservados(elemento))
        return RawInline(format="xhtml", text=serializar_elemento(elemento))

    def _span(self, elemento: ET.Element, classes: list[str]) -> Any:
        lingua = elemento.get("lang")
        estilo = None
        conhecidas = []
        for classe in classes:
            if classe.startswith("cb-style-") and estilo is None:
                pedaco = classe.removeprefix("cb-style-")
                estilo = self.estilo_do_slug.get(pedaco, pedaco)
                conhecidas.append(classe)
        conhecidos = ("lang", "xml:lang") if lingua and elemento.get(
            f"{{{XML}}}lang") == lingua else ()
        props = RunProps(style=estilo, language=lingua if conhecidos else None)
        return Span(content=tuple(self.inlines(elemento)), props=props,
                    html_attributes=_preservados(elemento, conhecidos=conhecidos,
                                                 classes_conhecidas=conhecidas))


class _LeitorDePartida:
    """A `section.cb-game` de volta ao `GameScore`."""

    def __init__(self, leitor: _Leitor) -> None:
        self.leitor = leitor

    def partida(self, secao: ET.Element) -> Any:
        import chess

        movimentos = next((f for f in secao if "cb-moves" in _classes(f)), None)
        if movimentos is None or any(_local(f) != "p" for f in movimentos):
            # Um diagrama no meio da partida, ou uma forma que o IR não guarda: a seção inteira
            # fica como está (spec R2.3).
            return RawPassthrough(format="xhtml", text=serializar_elemento(secao))
        ident = self.leitor._identidade(secao)
        inicial = secao.get("data-initial-fen")
        cabecalhos, extras, anotador, ha_cabecalho = self._cabecalho(secao)
        impresso = next((f for f in secao if "cb-result" in _classes(f)), None)
        resultado = (secao.get("data-result")
                     or ("".join(impresso.itertext()).strip() if impresso is not None else "")
                     or "*")
        if secao.get("data-eco"):
            extras = [t for t in extras if t.name != "ECO"]
            extras.append(PgnTag(name="ECO", value=secao.get("data-eco") or ""))
        try:
            filhos, comentario_inicial, render = self._lances(
                movimentos, chess.Board(inicial) if inicial else chess.Board())
        except (ValueError, KeyError, IndexError):
            return RawPassthrough(format="xhtml", text=serializar_elemento(secao))
        return GameScore(
            headers=replace(cabecalhos, result=resultado, extra=tuple(extras)),
            initial_fen=inicial, initial_comment=comentario_inicial, children=filhos,
            render=replace(render, show_headers=ha_cabecalho, show_result=impresso is not None),
            annotator=anotador,
            html_attributes=_preservados(
                secao, conhecidos=("data-eco", "data-result", "data-initial-fen"),
                classes_conhecidas=("cb-game",), guardar_id=ident["_guardar_id"]),
            **self.leitor._limpar(ident))

    @staticmethod
    def _cabecalho(  # noqa: PLR0912 - um ramo por linha do cabeçalho do MARKUP
            secao: ET.Element) -> tuple[GameHeaders, list[PgnTag], str | None, bool]:
        cabecalho = next((f for f in secao if "cb-game-header" in _classes(f)), None)
        campos: dict[str, str] = {}
        extras: list[PgnTag] = []
        anotador = None
        if cabecalho is None:
            return GameHeaders(), extras, anotador, False
        for linha in cabecalho:
            classes = _classes(linha)
            texto = "".join(linha.itertext()).strip()
            if "cb-game-number" in classes:
                extras.append(PgnTag(name="GameNumber", value=texto))
            elif "cb-player" in classes:
                cor = "white" if "cb-white" in classes else "black"
                for parte in linha:
                    valor = "".join(parte.itertext())
                    if "cb-name" in _classes(parte):
                        campos[cor] = valor
                    elif "cb-elo" in _classes(parte):
                        extras.append(PgnTag(name="WhiteElo" if cor == "white" else "BlackElo",
                                             value=valor))
            elif "cb-event" in classes:
                for parte in linha:
                    valor = "".join(parte.itertext())
                    classe = _classes(parte)
                    if "cb-event-name" in classe:
                        campos["event"] = valor
                    elif "cb-site" in classe:
                        campos["site"] = valor
                    elif "cb-round" in classe:
                        campos["round"] = valor.strip("()")
                    elif "cb-date" in classe:
                        campos["date"] = valor
            elif "cb-opening" in classes:
                for parte in linha:
                    valor = "".join(parte.itertext())
                    if "cb-opening-name" in _classes(parte):
                        extras.append(PgnTag(name="Opening", value=valor))
                    elif "cb-eco" in _classes(parte):
                        extras.append(PgnTag(name="ECO", value=valor))
            elif "cb-annotator" in classes:
                anotador = texto
        return GameHeaders(**campos), extras, anotador, True

    def _lances(self, movimentos: ET.Element, tabuleiro: Any
                ) -> tuple[tuple[MoveNode, ...], str, GameRenderOptions]:
        """As linhas de lances de volta à árvore.

        Cada lance entra como **continuação** da linha da profundidade dele quando é legal ali e
        dá a FEN que o `data-fen` diz; senão, como **variante**: irmã do último lance da linha de
        cima, jogada da posição de antes dele. O comentário fica no lance anterior (ou é o
        comentário inicial da partida).
        """
        import chess

        raiz: list[dict[str, Any]] = []
        comentario_inicial = ""
        render = GameRenderOptions(show_headers=False)
        pecas: list[tuple[str, str]] = []
        estado: dict[int, dict[str, Any]] = {}
        ultimo: dict[str, Any] | None = None
        for paragrafo in movimentos:
            classes = _classes(paragrafo)
            if "cb-comment" in classes:
                comentario = "".join(paragrafo.itertext())
                if ultimo is None:
                    comentario_inicial = comentario
                else:
                    ultimo["depois"] = comentario
                continue
            if "cb-line" not in classes:
                raise ValueError(f"parágrafo fora do contrato na partida: {classes}")
            profundidade = next((int(c.removeprefix("cb-depth-")) for c in classes
                                 if c.startswith("cb-depth-")), 0)
            for filho in paragrafo:
                classe = _classes(filho)
                if "cb-nag" in classe and ultimo is not None:
                    ultimo["nags"].append(int(filho.get("data-nag") or 0))
                    continue
                if "cb-move" not in classe:
                    continue
                peca = next((p for p in filho if "cb-piece" in _classes(p)), None)
                if peca is not None:
                    pecas.append((peca.get("data-piece") or "N", "".join(peca.itertext())))
                movimento = chess.Move.from_uci(filho.get("data-uci") or "")
                fen = filho.get("data-fen")
                registro = self._colocar(movimento, fen, profundidade, estado, raiz, tabuleiro)
                ultimo = registro
        return tuple(_no(r) for r in raiz), comentario_inicial, self._render_das_pecas(
            pecas, render)

    @staticmethod
    def _colocar(movimento: Any, fen: str | None, profundidade: int,
                 estado: dict[int, dict[str, Any]], raiz: list[dict[str, Any]],
                 inicio: Any) -> dict[str, Any]:
        """Põe o lance na árvore: continuação da linha, ou variante do lance de cima."""
        def jogar(tabuleiro: Any) -> Any:
            if movimento not in tabuleiro.legal_moves:
                return None
            depois = tabuleiro.copy()
            depois.push(movimento)
            return depois if fen is None or depois.fen() == fen else None

        linha = estado.get(profundidade)
        onde: list[dict[str, Any]] | None = None
        antes = None
        if linha is not None and (depois := jogar(linha["depois"])) is not None:
            antes, onde = linha["depois"], linha["registro"]["filhos"]
        elif profundidade == 0 and not raiz and (depois := jogar(inicio)) is not None:
            antes, onde = inicio, raiz
        elif profundidade > 0 and (de_cima := estado.get(profundidade - 1)) is not None and (
                depois := jogar(de_cima["antes"])) is not None:
            antes, onde = de_cima["antes"], de_cima["lista"]
        if onde is None or antes is None:
            raise ValueError(f"o lance {movimento.uci()} não cabe na partida")
        registro = {"uci": movimento.uci(), "san": antes.san(movimento), "antes": antes.fen(),
                    "depois_fen": depois.fen(), "nags": [], "depois": "", "filhos": [],
                    "ply": (antes.fullmove_number - 1) * 2 + (1 if antes.turn else 2)}
        onde.append(registro)
        estado[profundidade] = {"registro": registro, "lista": onde, "antes": antes,
                                "depois": depois}
        for mais_funda in [d for d in estado if d > profundidade]:
            del estado[mais_funda]
        return registro

    def _render_das_pecas(self, pecas: list[tuple[str, str]],
                          atual: GameRenderOptions) -> GameRenderOptions:
        """A notação que a partida imprimiu.

        As figurinas (e o conjunto delas), ou o idioma cujas letras explicam **todas** as peças: o
        do capítulo primeiro, depois o inglês.
        """
        from caissa.export.text import figurine_char

        if not pecas:
            return atual
        for conjunto in (FigurineSet.WHITE, FigurineSet.BLACK):
            if all(visivel == figurine_char(letra, conjunto) for letra, visivel in pecas):
                return replace(atual, render=MoveRenderStyle.FIGURINE, figurine_set=conjunto)
        preferidas = [self.leitor.idioma.split("-")[0], "en", *PIECE_TABLES]
        for codigo in dict.fromkeys(preferidas):
            tabela = PIECE_TABLES.get(codigo)
            if tabela is not None and all(
                    str(getattr(tabela, _PECA_DA_LETRA.get(letra, PieceType.KNIGHT).value))
                    == visivel for letra, visivel in pecas):
                return replace(atual, render=MoveRenderStyle.LETTERS, language=codigo)
        raise ValueError(f"nenhuma notação explica as peças da partida: {pecas[:5]}")


def _no(registro: dict[str, Any]) -> MoveNode:
    return MoveNode(
        san=registro["san"], ply=registro["ply"], position_before=registro["antes"],
        position_after=registro["depois_fen"], uci=registro["uci"],
        nags=tuple(registro["nags"]), comment_after=registro.get("depois", ""),
        children=tuple(_no(f) for f in registro["filhos"]))


def ler_capitulo(texto: str, *, mapa: MapaDaProveniencia | None = None,
                 estilos: Iterable[str] = ()) -> Capitulo:
    """O XHTML legível de volta ao IR (os blocos do capítulo, o título, as folhas e o idioma).

    Args:
        texto: O arquivo XHTML.
        mapa: O mapa da proveniência do projeto; sem ele, os `id` e os marcadores ficam no IR
            como vieram.
        estilos: Os nomes dos estilos do documento, para a classe `cb-style-<slug>` voltar ao
            nome.
    """
    raiz = ET.fromstring(texto.encode("utf-8"))  # noqa: S314 - o arquivo do projeto
    cabeca = next((f for f in raiz if _local(f) == "head"), None)
    corpo = next((f for f in raiz if _local(f) == "body"), None)
    titulo = ""
    folhas: list[str] = []
    if cabeca is not None:
        for filho in cabeca:
            if _local(filho) == "title":
                titulo = "".join(filho.itertext())
            elif _local(filho) == "link" and filho.get("rel") == "stylesheet":
                folhas.append(filho.get("href") or "")
    idioma = raiz.get("lang") or raiz.get(f"{{{XML}}}lang") or "pt-BR"
    leitor = _Leitor(mapa, estilos, idioma)
    blocos: list[Any] = []
    for filho in (corpo if corpo is not None else []):
        if (_local(filho) == "span" and filho.get(f"{{{EPUB}}}type") == "pagebreak"
                and mapa is not None and _MARCADOR.match(filho.get("id") or "")):
            pagina = int((filho.get("id") or "pg0")[2:])
            mapa.folios.setdefault(pagina, filho.get("aria-label") or str(pagina))
            continue
        no = leitor.bloco(filho)
        if no is not None:
            blocos.append(no)
    return Capitulo(blocos=tuple(blocos), titulo=titulo, folhas=tuple(folhas), idioma=idioma)


def escrever_capitulo(capitulo: Capitulo, documento: Document | None = None, *,
                      folios: Mapping[int, str] | None = None) -> tuple[str, EscritorLegivel]:
    """O capítulo em XHTML legível, e o escritor (com o mapa da proveniência e as imagens)."""
    escritor = EscritorLegivel(documento, folios=folios)
    escritor.idioma = capitulo.idioma or escritor.idioma
    return escritor.capitulo(capitulo), escritor


_ = (Callable, _NAG)
