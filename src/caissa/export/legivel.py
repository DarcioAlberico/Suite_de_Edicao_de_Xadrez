"""O perfil legível do motor HTML: o XHTML que o Editor HTML/CSS gera, mostra e relê (passo H5).

O contrato é `docs/MARKUP_CAISSA.md`: as classes e os atributos `cb-*` para o xadrez, as extensões
`data-*` que o livro precisa (o §12 do contrato), HTML semântico para o resto, **nada** de
`data-ir`, de classe gerada (`.pN/.rN/.dN`) ou de dado da máquina. Este módulo tem as peças que a
ida e volta precisa (spec R2.2a):

- :func:`canon` — a árvore XML com os atributos em ordem e o espaço insignificante normalizado (a
  N4): ``canon(escrever(ler(x))) == canon(x)`` é o portão da volta;
- :class:`EscritorLegivel` — IR → XHTML legível (o capítulo inteiro, e as imagens dos diagramas,
  que são derivadas);
- :func:`ler_capitulo` — XHTML legível → IR. O que o contrato não modela é **preservado**
  (spec R2.3): o elemento desconhecido vira `RawPassthrough`/`RawInline` `xhtml`, e o atributo
  desconhecido vai para `IRNode.html_attributes`;
- :func:`forma_normal` — o IR depois das normalizações declaradas N1–N4 (o contrato, §8), cada
  uma contada: ``ler(escrever(ir)) == forma_normal(ir)`` é o portão da ida.

**O que o XHTML não diz e o IR precisa** — os `id` de proveniência (`p55-3`), os marcadores de
página, a proveniência de cada bloco e o reconhecimento de cada diagrama — volta pelo **mapa da
proveniência** que o escritor devolve (:attr:`EscritorLegivel.mapa`, o que o projeto guarda em
`proveniencia.json`). Sem o mapa, o leitor guarda esses elementos literalmente (o `id` no nó, o
marcador como `RawPassthrough`), e a volta fecha do mesmo jeito.
"""

from __future__ import annotations

import hashlib
import json
import re
import typing
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from caissa.core.chess.notation_tables import (
    PIECE_TABLES,
    FigurineSet,
    MoveRenderStyle,
    PieceType,
)
from caissa.core.model import (
    Alignment,
    Anchor,
    Block,
    Callout,
    CalloutKind,
    ClockAnnotation,
    ClockKind,
    CodeBlock,
    ColumnLayout,
    Diagram,
    DiagramSource,
    DiagramStyle,
    Document,
    Emphasis,
    Endnote,
    EvalAnnotation,
    EvalKind,
    Figure,
    FigurePlacement,
    Footnote,
    GameHeaders,
    GameRenderOptions,
    GameScore,
    Group,
    GroupRole,
    Heading,
    ImageBlock,
    ImageInline,
    IndexEntry,
    Inline,
    InlineDiagram,
    IRNode,
    LineBreak,
    Link,
    LinkKind,
    ListBlock,
    ListItem,
    ListMarkerStyle,
    MathBlock,
    MathInline,
    Move,
    MoveNode,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    NumberingRef,
    Orientation,
    PageBreak,
    PageGeometry,
    Paragraph,
    ParagraphProps,
    PgnTag,
    PieceGlyph,
    Quote,
    RawInline,
    RawPassthrough,
    RecognitionResult,
    ResourceKind,
    RunProps,
    SectionBreak,
    SectionBreakKind,
    SmallCaps,
    SourceKind,
    Space,
    Span,
    Strike,
    Strong,
    Subscript,
    Superscript,
    Tab,
    Table,
    TableCell,
    TableOfContents,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
    VariationStyle,
    VerticalCellAlignment,
)
from caissa.core.model.base import tag_of
from caissa.core.model.blocks import ListKind
from caissa.core.model.inline import SpaceKind

__all__ = [
    "Capitulo",
    "EscritorLegivel",
    "MapaDaProveniencia",
    "canon",
    "escrever_capitulo",
    "folhas_do_livro",
    "forma_normal",
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

#: Os espaços especiais do IR e o caractere Unicode de cada um (o leitor os separa do texto).
ESPACOS = {SpaceKind.THIN: "\u2009", SpaceKind.HAIR: "\u200a", SpaceKind.EN: "\u2002",
           SpaceKind.EM: "\u2003", SpaceKind.FIGURE: "\u2007",
           SpaceKind.PUNCTUATION: "\u2008", SpaceKind.ZERO_WIDTH: "\u200b",
           SpaceKind.ZERO_WIDTH_NON_JOINER: "\u200c", SpaceKind.ZERO_WIDTH_JOINER: "\u200d"}
_ESPACO_DO_CARACTERE = {v: k for k, v in ESPACOS.items()}
_ESPECIAIS = re.compile("([\u00a0\t" + "".join(ESPACOS.values()) + "])")

ESTILOS_DO_CONTRATO = {"Movetext": "cb-movetext", "Caption": "cb-caption",
                       "Footnote": "cb-footnote"}
_CLASSE_DO_ESTILO = {v: k for k, v in ESTILOS_DO_CONTRATO.items()}

#: Os nós que ficam dentro do parágrafo (o `Inline` do modelo).
INLINES: tuple[type, ...] = typing.get_args(Inline)

#: Os nós que o escritor escreve com `id`: os blocos e as seções (o contrato, §3).
_COM_ID: tuple[type, ...] = (
    Heading, Paragraph, Diagram, GameScore, Footnote, Endnote, Quote, ListBlock, ThematicBreak,
    SectionBreak, PageBreak, CodeBlock, Table, ImageBlock, TableOfContents, Group, Callout,
    MathBlock, Figure)

#: A proveniência do PDF digitalizado (a N1): o texto que o OCR leu.
_DIGITALIZADO = frozenset({SourceKind.OCR})

_ROTULO_AUTOMATICO = "Diagrama {}"


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


_ESPACO_DO_XML = " \t\r\n"
"""O espaço que o XML trata como insignificante; o sem quebra e os finos não são."""
_CORRIDA_DO_XML = re.compile("[ \t\r\n]+")


def _normalizar(elemento: ET.Element) -> None:  # noqa: PLR0912 - as bordas de cada bloco
    """A N4: espaço do XML colapsado, e sem espaço junto das bordas dos blocos."""
    if elemento.text is not None:
        elemento.text = _CORRIDA_DO_XML.sub(" ", elemento.text)
    for filho in elemento:
        _normalizar(filho)
        if filho.tail is not None:
            filho.tail = _CORRIDA_DO_XML.sub(" ", filho.tail)
    if _local(elemento) in BLOCOS or _nome(elemento.tag) == "m:math":
        if elemento.text:
            elemento.text = elemento.text.lstrip(_ESPACO_DO_XML)
        if len(elemento):
            ultimo = elemento[-1]
            if ultimo.tail:
                ultimo.tail = ultimo.tail.rstrip(_ESPACO_DO_XML)
        elif elemento.text:
            elemento.text = elemento.text.rstrip(_ESPACO_DO_XML)
    anterior: ET.Element | None = None
    for filho in elemento:
        if _local(filho) in BLOCOS:
            if anterior is None:
                if elemento.text:
                    elemento.text = elemento.text.rstrip(_ESPACO_DO_XML)
            elif anterior.tail:
                anterior.tail = anterior.tail.rstrip(_ESPACO_DO_XML)
            if filho.tail:
                filho.tail = filho.tail.lstrip(_ESPACO_DO_XML)
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


def _fragmento(texto: str) -> ET.Element | None:
    """O elemento único de um trecho de XHTML sem declarações, ou ``None``.

    O texto do `RawPassthrough`/`RawInline` `xhtml` é um elemento serializado sem as
    declarações de espaço de nomes (a forma de :func:`serializar_elemento`).
    """
    if texto != texto.strip() or not texto.startswith("<"):
        return None
    envelope = (f'<r xmlns="{XHTML}" xmlns:epub="{EPUB}" xmlns:svg="{SVG}" '
                f'xmlns:m="{MATHML}">{texto}</r>')
    try:
        raiz = ET.fromstring(envelope.encode("utf-8"))  # noqa: S314 - texto do próprio projeto
    except ET.ParseError:
        return None
    if len(raiz) != 1 or (raiz.text or "") or (raiz[0].tail or ""):
        return None
    return raiz[0]


# --------------------------------------------------------------------------- #
# Os valores dos atributos
# --------------------------------------------------------------------------- #


def _medida(valor: Any) -> str | None:
    from caissa.export.html import _measure_attribute

    return _measure_attribute(valor)


def _medida_de(texto: str | None) -> Any:
    from caissa.export.html import _measure_from_attribute

    return _measure_from_attribute(texto)


def _json(valor: Any) -> str:
    """Um valor do IR num atributo, pela serialização do próprio IR (ida e volta exata).

    O número inteiro sai sem o `.0`, seja qual for o tipo que o IR guardou: `210` e `210.0` são o
    mesmo valor, e o texto do atributo tem de ser um só para a volta fechar.
    """
    from caissa.core.model.serialize import encode_value

    def inteiros(dado: Any) -> Any:
        if isinstance(dado, float) and dado.is_integer():
            return int(dado)
        if isinstance(dado, dict):
            return {k: inteiros(v) for k, v in dado.items()}
        if isinstance(dado, list):
            return [inteiros(v) for v in dado]
        return dado

    return json.dumps(inteiros(encode_value(valor)), ensure_ascii=False, separators=(",", ":"),
                      sort_keys=True)


def _json_de(texto: str | None, tipo: Any) -> Any:
    from caissa.core.model.serialize import decode_value

    return decode_value(json.loads(texto), tipo) if texto else None


def _marcas(marcas: Sequence[Any]) -> str | None:
    from caissa.export.html import _marks_data

    return _marks_data(marcas) or None


def _marcas_de(texto: str | None) -> tuple[Any, ...]:
    from caissa.export.html import _parse_marks

    return _parse_marks(texto) if texto else ()


def _numero(valor: float) -> str:
    return repr(float(valor))


def _sim(valor: bool) -> str | None:
    return "1" if valor else None


# --------------------------------------------------------------------------- #
# O mapa da proveniência e o capítulo
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegistroDoMapa:
    """O que o mapa guarda de um nó com `id`: a identidade e o dado da máquina (R2.4).

    ``origem`` diz de onde o `id` veio, para o leitor o devolver ao mesmo lugar: ``"pagina"``
    (gerado, `p55-3`), ``"ancora"`` (a âncora do nó), ``"html"`` (o `id` que o arquivo trazia)
    ou ``"nota"`` (a referência da nota).
    """

    ir_id: Any
    origem: str
    proveniencia: Any = None
    fonte: DiagramSource | None = None
    reconhecimento: RecognitionResult | None = None
    conferido: bool = False

    @classmethod
    def do_no(cls, no: Any, origem: str) -> RegistroDoMapa:
        if isinstance(no, Diagram):
            return cls(ir_id=no.id, origem=origem, proveniencia=no.provenance, fonte=no.source,
                       reconhecimento=no.recognition, conferido=no.verified_by_human)
        return cls(ir_id=no.id, origem=origem, proveniencia=no.provenance)


@dataclass
class MapaDaProveniencia:
    """O que o XHTML não diz e o IR precisa: por `id` do livro, o registro; e os fólios.

    O escritor o preenche; o leitor o consulta (o projeto o guarda em `proveniencia.json`, pelo
    `caissa.editor.leitura`). Do registro, o leitor devolve a identidade (`id`), a proveniência
    e, no diagrama, o reconhecimento, a origem da imagem e a conferência humana — o dado da
    máquina que o livro não leva (R2.4).
    """

    nos: dict[str, RegistroDoMapa] = field(default_factory=dict)
    folios: dict[int, str] = field(default_factory=dict)
    """O fólio impresso, pela página do PDF em base 1."""


@dataclass
class Capitulo:
    """Um arquivo XHTML do livro: o título, as folhas, o idioma e os blocos."""

    blocos: tuple[Any, ...] = ()
    titulo: str = ""
    folhas: tuple[str, ...] = ()
    idioma: str = "pt-BR"
    brutos: tuple[str, ...] = ()
    """O que a conferência do leitor guardou como bruto, porque o IR não o diria de volta
    (`etiqueta.classe`, na ordem do arquivo): o escritor não o usa; a validação o mostra."""


def _imagem_do_diagrama(fen: str, orientacao: str) -> str:
    """O arquivo da imagem derivada: `dg_<hash>.svg`, pelo conteúdo (o contrato, §6.1)."""
    return f"dg_{hashlib.sha256(f'{fen}|{orientacao}'.encode()).hexdigest()[:12]}.svg"


def _pagina_da_maquina(no: Any) -> int | None:
    """A página do PDF (base 1) de onde o nó veio, para o `id` `p<pág>-<n>`."""
    proveniencia = getattr(no, "provenance", None)
    if proveniencia is not None and proveniencia.page_index is not None:
        return int(proveniencia.page_index) + 1
    if isinstance(no, Diagram) and no.source.page_index is not None:
        return int(no.source.page_index) + 1
    return None


def _id_proprio(no: Any) -> str | None:
    """O `id` que o nó já diz: o do arquivo, a âncora, ou a referência da nota."""
    candidatos = [c for c in (dict(no.html_attributes).get("id"), getattr(no, "anchor", None),
                              no.ref if isinstance(no, Footnote | Endnote) else None) if c]
    if len(set(candidatos)) > 1:
        raise ValueError(f"{type(no).__name__} com dois id: {candidatos}")
    return candidatos[0] if candidatos else None


def _chaveado(no: Any) -> bool:
    """Se o escritor dá `id` ao nó — e o mapa, então, devolve o dado da máquina dele."""
    return isinstance(no, _COM_ID) and (
        _id_proprio(no) is not None or _pagina_da_maquina(no) is not None)


# --------------------------------------------------------------------------- #
# A notação: o que o livro imprime na cabeça do lance
# --------------------------------------------------------------------------- #


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


def _notacao_das_pecas(pecas: Sequence[tuple[str, str]], idioma: str,
                       padrao: tuple[MoveRenderStyle, str, FigurineSet]
                       ) -> tuple[MoveRenderStyle, str, FigurineSet] | None:
    """A notação que as peças impressas dizem, ou ``None`` quando nenhuma as explica.

    As figurinas (e o conjunto delas), ou o idioma cujas letras explicam **todas** as peças: o
    do capítulo primeiro, depois o inglês. Sem peça, o padrão. O escritor chama a mesma função e
    escreve o `data-render`/`data-language`/`data-figurine-set` que ela não acerta.
    """
    from caissa.export.text import figurine_char

    _, lingua, conjunto = padrao
    if not pecas:
        return padrao
    for candidato in (FigurineSet.WHITE, FigurineSet.BLACK):
        if all(visivel == figurine_char(letra, candidato) for letra, visivel in pecas):
            return MoveRenderStyle.FIGURINE, lingua, candidato
    for codigo in dict.fromkeys([idioma.split("-")[0], "en", *PIECE_TABLES]):
        tabela = PIECE_TABLES.get(codigo)
        if tabela is not None and all(
                str(getattr(tabela, _PECA_DA_LETRA.get(letra, PieceType.KNIGHT).value))
                == visivel for letra, visivel in pecas):
            return MoveRenderStyle.LETTERS, codigo, conjunto
    return None


def _atributos_da_notacao(verdade: tuple[MoveRenderStyle, str, FigurineSet],
                          derivada: tuple[MoveRenderStyle, str, FigurineSet] | None
                          ) -> list[tuple[str, str]]:
    """Os `data-*` da notação que a leitura das peças não acertaria."""
    nomes = ("data-render", "data-language", "data-figurine-set")
    valores = (verdade[0].value, verdade[1], verdade[2].value)
    if derivada is None:
        return list(zip(nomes, valores, strict=True))
    achados = (derivada[0].value, derivada[1], derivada[2].value)
    return [(n, v) for n, v, a in zip(nomes, valores, achados, strict=True) if v != a]


def _notacao_lida(elemento: ET.Element, pecas: Sequence[tuple[str, str]], idioma: str,
                  padrao: tuple[MoveRenderStyle, str, FigurineSet]
                  ) -> tuple[MoveRenderStyle, str, FigurineSet]:
    derivada = _notacao_das_pecas(pecas, idioma, padrao)
    explicitos = [elemento.get(n) for n in ("data-render", "data-language", "data-figurine-set")]
    if derivada is None:
        if None in explicitos:
            raise ValueError(f"nenhuma notação explica as peças: {list(pecas)[:5]}")
        derivada = padrao
    render, lingua, conjunto = derivada
    return (MoveRenderStyle(explicitos[0]) if explicitos[0] else render,
            explicitos[1] if explicitos[1] is not None else lingua,
            FigurineSet(explicitos[2]) if explicitos[2] else conjunto)


def _alts_gerados(fen: str, *, idioma: str, miniatura: bool) -> set[str]:
    """As descrições que o escritor gera para a posição (a pessoa não escreveu o `alt`)."""
    from caissa.export.diagrams import descrever_posicao

    campos = fen.split()
    lado = campos[1] if len(campos) > 1 and campos[1] in ("w", "b") else "w"
    alts = set()
    for posicao in (fen, None):
        for cor in (lado, None):
            for conferida in (True, False):
                try:
                    alts.add(descrever_posicao(posicao, cor, idioma, conferida,
                                               miniatura=miniatura))
                except (ValueError, KeyError, IndexError):
                    continue
    return alts


# --------------------------------------------------------------------------- #
# O escritor
# --------------------------------------------------------------------------- #


def _classe_do_estilo(nome: str | None) -> tuple[str, ...]:
    if not nome:
        return ()
    return (ESTILOS_DO_CONTRATO.get(nome) or f"cb-style-{slug(nome)}",)


def _corrida(props: RunProps) -> tuple[tuple[str, ...], list[tuple[str, str]]]:
    """O que o contrato diz das `RunProps`: a classe do estilo e a língua (o resto é N2)."""
    classes = (f"cb-style-{slug(props.style)}",) if props.style else ()
    atributos = ([("lang", props.language), ("xml:lang", props.language)]
                 if props.language else [])
    return classes, atributos


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
        self._no_link = False

    # -- o arquivo --------------------------------------------------------

    def capitulo(self, capitulo: Capitulo) -> str:
        linhas = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE html>",
                  f'<html xmlns="{XHTML}" xmlns:epub="{EPUB}" xmlns:svg="{SVG}" '
                  f'xmlns:m="{MATHML}"'
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
            partes.append(self.bloco(bloco))
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

    def _id(self, no: Any, tipo: str) -> str | None:
        """O `id` do bloco, e o registro dele no mapa.

        O que o nó já diz (o do arquivo, a âncora, a referência da nota), ou o da página de onde
        ele veio (`p55-3`, `p55-d1`, `p55-g1`).
        """
        from caissa.editor.paginas import id_de_bloco, id_de_diagrama, id_de_partida

        ident = _id_proprio(no)
        if ident is not None:
            origem = ("html" if dict(no.html_attributes).get("id") == ident
                      else "nota" if isinstance(no, Footnote | Endnote) else "ancora")
        else:
            pagina = _pagina_da_maquina(no)
            if pagina is None:
                return None
            chave = (pagina, tipo)
            self._ordem[chave] = self._ordem.get(chave, 0) + 1
            ident = {"b": id_de_bloco, "d": id_de_diagrama, "g": id_de_partida}[tipo](
                pagina, self._ordem[chave])
            origem = "pagina"
        self.mapa.nos[ident] = RegistroDoMapa.do_no(no, origem)
        return ident

    def _abrir(self, etiqueta: str, no: Any, *, classes: Sequence[str] = (),
               atributos: Sequence[tuple[str, str | None]] = (), ident: str | None = None,
               vazio: bool = False) -> str:
        """A etiqueta de abertura, com os atributos na ordem do contrato.

        O `id`, as classes do contrato mais as extras, os atributos do contrato e os preservados
        (`html_attributes`). Um atributo preservado com o nome de um que o contrato escreve aqui
        não tem onde ir: o escritor recusa, em vez de perder um dos dois (R2.3).
        """
        html = dict(no.html_attributes)
        todas = " ".join(c for c in (*classes, html.get("class", "")) if c)
        pares: list[tuple[str, str]] = []
        if ident:
            pares.append(("id", ident))
        if todas:
            pares.append(("class", todas))
        pares += [(n, v) for n, v in atributos if v is not None]
        nomes = {n for n, _ in pares}
        for nome, valor in no.html_attributes:
            if nome == "class" or (nome == "id" and ident):
                continue
            if nome in nomes:
                raise ValueError(f"o atributo preservado {nome!r} colide com o do contrato em "
                                 f"<{etiqueta}> ({type(no).__name__})")
            pares.append((nome, valor))
        texto = f"<{etiqueta}" + "".join(_atributo(n, v) for n, v in pares)
        return texto + ("/>" if vazio else ">")

    def bloco(self, no: Any) -> str:
        metodo = getattr(self, f"_bloco_{tag_of(no)}", None)
        if metodo is None:
            raise ValueError(f"sem forma legível: {type(no).__name__}")
        return str(metodo(no))

    def _bloco_heading(self, no: Heading) -> str:
        nivel = max(1, min(6, no.level))
        atributos = [("data-level", str(no.level) if nivel != no.level else None),
                     ("data-toc-text", no.toc_text),
                     ("data-in-toc", None if no.list_in_toc else "0"),
                     ("data-numbering", _json(no.numbering) if no.numbering else None)]
        numero = (f'<span class="cb-heading-number">{_texto(no.numbering_text)}</span> '
                  if no.numbering_text is not None else "")
        return (self._abrir(f"h{nivel}", no, classes=_classe_do_estilo(no.props.style),
                            atributos=atributos, ident=self._id(no, "b"))
                + numero + self.inlines(no.content) + f"</h{nivel}>")

    def _bloco_paragraph(self, no: Paragraph) -> str:
        classes = list(_classe_do_estilo(no.props.style))
        atributos: list[tuple[str, str | None]] = []
        if no.drop_cap is not None:
            classes.append("cb-dropcap")
            atributos.append(("data-drop-cap", str(no.drop_cap)))
        return (self._abrir("p", no, classes=classes, atributos=atributos,
                            ident=self._id(no, "b"))
                + self.inlines(no.content) + "</p>")

    def _bloco_diagram(self, no: Diagram) -> str:
        fen = no.fen or ""
        campos = fen.split()
        stm = campos[1] if len(campos) > 1 and campos[1] in ("w", "b") else "w"
        orientacao = "black" if no.orientation is Orientation.BLACK else "white"
        nome = _imagem_do_diagrama(fen, orientacao)
        if nome not in self.imagens:
            self.imagens[nome] = self._svg(no)
        alt = no.alt_text if no.alt_text is not None else self._alt_do_diagrama(no, fen, stm)
        # O número vai no rótulo automático «Diagrama N» (o contrato, §6.1); o `data-number`, só
        # quando o rótulo é outro texto. O rótulo escrito que parece o automático leva o
        # `data-literal`, para o leitor não o tomar pelo número.
        atributos = [("data-fen", fen), ("data-stm", stm), ("data-mode", "svg"),
                     ("data-orientation", orientacao),
                     ("data-number", str(no.number)
                      if no.number is not None and no.label is not None else None),
                     ("data-marks", _marcas(no.marks))]
        legenda = []
        if no.label is not None:
            literal = ' data-literal="1"' if _ROTULO_NUMERADO.match(no.label) else ""
            legenda.append(f'<span class="cb-diagram-label"{literal}>{_texto(no.label)}</span>')
        elif no.number is not None:
            legenda.append('<span class="cb-diagram-label">'
                           f"{_texto(_ROTULO_AUTOMATICO.format(no.number))}</span>")
        if no.stipulation is not None:
            legenda.append(f'<span class="cb-stipulation">{_texto(no.stipulation)}</span>')
        if no.move_context is not None:
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
        if no.solution is not None:
            corpo += "\n" + _EscritorDePartida(self).partida(
                no.solution, self._id(no.solution, "g"), classes_extras=("cb-solution",))
        classes = ("cb-diagram", *((f"cb-style-{slug(no.style.name)}",) if no.style.name else ()))
        abre = self._abrir("figure", no, classes=classes, atributos=atributos,
                           ident=self._id(no, "d"))
        return f"{abre}\n{corpo}\n</figure>"

    def _alt_do_diagrama(self, no: Diagram, fen: str, stm: str) -> str:
        from caissa.export.diagrams import _reading_status, descrever_posicao

        desconhecida, lado_desconhecido, _ = _reading_status(no)
        conferida = bool(no.verified_by_human or getattr(no.provenance, "verified_by_human",
                                                         False))
        return descrever_posicao(None if desconhecida else fen,
                                 None if lado_desconhecido else stm, self.idioma,
                                 conferida or no.recognition == RecognitionResult())

    def _svg(self, no: Diagram | InlineDiagram) -> str:
        from caissa.export.base import ExportContext
        from caissa.export.diagrams import DiagramRenderer
        from caissa.export.profiles import HTML_PROFILE

        contexto = ExportContext(HTML_PROFILE, self.documento)
        try:
            return DiagramRenderer(contexto, tinta_do_leitor=True).svg(no).svg
        except Exception:  # noqa: BLE001 - a imagem é derivada; a FEN fica no XHTML
            return ""

    def _bloco_game_score(self, no: GameScore) -> str:
        return _EscritorDePartida(self).partida(no, self._id(no, "g"))

    def _bloco_raw_passthrough(self, no: RawPassthrough) -> str:
        if no.html_attributes:
            raise ValueError("RawPassthrough com html_attributes: o texto bruto não os leva")
        if no.format == "xhtml" and _bruto_fica(no.text, bloco=True):
            return no.text
        return (self._abrir("pre", no, classes=("cb-raw",), atributos=(("data-format", no.format),))
                + _texto(no.text) + "</pre>")

    def _nota(self, no: Footnote | Endnote, tipo: str) -> str:
        abre = self._abrir("aside", no, classes=_classe_do_estilo(no.props.style), atributos=(
            ("epub:type", tipo), ("role", f"doc-{tipo}"), ("data-marker", no.marker)),
            ident=self._id(no, "b"))
        return f"{abre}\n{self.blocos(no.content, no_topo=False)}\n</aside>"

    def _bloco_footnote(self, no: Footnote) -> str:
        return self._nota(no, "footnote")

    def _bloco_endnote(self, no: Endnote) -> str:
        return self._nota(no, "endnote")

    def _bloco_quote(self, no: Quote) -> str:
        rodape = (f"\n<footer>{self.inlines(no.attribution)}</footer>"
                  if no.attribution else "")
        abre = self._abrir("blockquote", no, classes=_classe_do_estilo(no.props.style),
                           ident=self._id(no, "b"))
        return f"{abre}\n{self.blocos(no.content, no_topo=False)}{rodape}\n</blockquote>"

    def _bloco_list_block(self, no: ListBlock) -> str:
        etiqueta = {ListKind.ORDERED: "ol", ListKind.DEFINITION: "dl"}.get(no.kind, "ul")
        padrao = ListMarkerStyle.DECIMAL if no.kind is ListKind.ORDERED else ListMarkerStyle.BULLET
        atributos = [
            ("start", str(no.start)) if etiqueta == "ol" and no.start != 1 else
            ("data-start", str(no.start) if no.start != 1 else None),
            ("data-marker-style", no.marker_style.value if no.marker_style is not padrao
             else None),
            ("data-marker-text", no.marker_text), ("data-tight", _sim(no.tight)),
            ("data-numbering", _json(no.numbering) if no.numbering else None),
            ("data-indent", _medida(no.indent))]
        abre = self._abrir(etiqueta, no, classes=_classe_do_estilo(no.props.style),
                           atributos=atributos, ident=self._id(no, "b"))
        itens = []
        for item in no.items:
            atributos_do_item = [
                ("value" if etiqueta == "ol" else "data-value",
                 str(item.start_override) if item.start_override is not None else None),
                ("data-marker", item.marker_override),
                ("data-checked", None if item.checked is None else ("1" if item.checked else "0"))]
            if etiqueta == "dl":
                itens.append(f"<dt>{self.inlines(item.term)}</dt>")
                itens.append(self._abrir("dd", item, atributos=atributos_do_item)
                             + self._conteudo(item.content) + "</dd>")
                continue
            termo = (f'<span class="cb-term">{self.inlines(item.term)}</span>'
                     if item.term else "")
            itens.append(self._abrir("li", item, atributos=atributos_do_item) + termo
                         + self._conteudo(item.content, forcar_blocos=bool(item.term))
                         + "</li>")
        return f"{abre}\n" + "\n".join(itens) + f"\n</{etiqueta}>"

    def _conteudo(self, blocos: Sequence[Any], *, forcar_blocos: bool = False) -> str:
        """O conteúdo da célula ou do item: o parágrafo simples vai como texto solto."""
        if (not forcar_blocos and len(blocos) == 1 and isinstance(blocos[0], Paragraph)
                and blocos[0].content and _paragrafo_simples(blocos[0])):
            return self.inlines(blocos[0].content)
        return self.blocos(blocos, no_topo=False)

    def _bloco_thematic_break(self, no: ThematicBreak) -> str:
        if no.ornament is not None:
            return (self._abrir("p", no, classes=("cb-ornament",), ident=self._id(no, "b"))
                    + _texto(no.ornament) + "</p>")
        return self._abrir("hr", no, ident=self._id(no, "b"), vazio=True)

    def _bloco_section_break(self, no: SectionBreak) -> str:
        atributos = [
            ("data-kind", no.kind.value if no.kind is not SectionBreakKind.NEXT_PAGE else None),
            ("data-columns", _json(no.columns) if no.columns is not None else None),
            ("data-geometry", _json(no.geometry) if no.geometry is not None else None),
            ("data-different-first", _sim(no.different_first_page)),
            ("data-different-odd-even", _sim(no.different_odd_even)),
            ("data-page-number-start", str(no.page_number_start)
             if no.page_number_start is not None else None),
            ("data-page-number-format", no.page_number_format),
            ("data-vertical-alignment", no.vertical_alignment.value
             if no.vertical_alignment is not None else None)]
        ident = self._id(no, "b")
        if not no.header_text and not no.footer_text:
            return self._abrir("hr", no, classes=("cb-section-break",), atributos=atributos,
                               ident=ident, vazio=True)
        cabecas = "".join(f'<span class="cb-running-{nome}">{self.inlines(nos)}</span>'
                          for nome, nos in (("head", no.header_text), ("foot", no.footer_text))
                          if nos)
        return (self._abrir("div", no, classes=("cb-section-break",), atributos=atributos,
                            ident=ident) + cabecas + "</div>")

    def _bloco_page_break(self, no: PageBreak) -> str:
        abre = self._abrir("div", no, classes=("cb-page-break",), ident=self._id(no, "b"))
        return abre + "</div>"

    def _bloco_code_block(self, no: CodeBlock) -> str:
        lingua = f' class="language-{_texto(no.language)}"' if no.language else ""
        abre = self._abrir("pre", no, classes=_classe_do_estilo(no.props.style), atributos=(
            ("data-line-numbers", _sim(no.show_line_numbers)),), ident=self._id(no, "b"))
        return f"{abre}<code{lingua}>{_texto(no.text)}</code></pre>"

    def _bloco_table(self, no: Table) -> str:
        linhas = []
        if no.caption:
            linhas.append(f"<caption>{self.inlines(no.caption)}</caption>")
        rodape = len(no.rows) - no.footer_row_count if no.footer_row_count else len(no.rows)
        grupos = (("thead", no.rows[:no.header_row_count]),
                  ("tbody", no.rows[no.header_row_count:rodape]),
                  ("tfoot", no.rows[rodape:] if no.footer_row_count else ()))
        for grupo, filas in grupos:
            if not filas and grupo != "tbody":
                continue
            linhas.append(f"<{grupo}>")
            for fila in filas:
                celulas = []
                for celula in fila.cells:
                    etiqueta = "th" if celula.is_header else "td"
                    atributos = [("colspan", str(celula.col_span) if celula.col_span != 1
                                  else None),
                                 ("rowspan", str(celula.row_span) if celula.row_span != 1
                                  else None)]
                    celulas.append(self._abrir(etiqueta, celula, atributos=atributos)
                                   + self._conteudo(celula.content) + f"</{etiqueta}>")
                atributos_da_fila = [("data-height", _medida(fila.height)),
                                     ("data-header", _sim(fila.is_header)),
                                     ("data-repeat", _sim(fila.repeat_on_break)),
                                     ("data-keep", _sim(fila.keep_together))]
                linhas.append(self._abrir("tr", fila, atributos=atributos_da_fila)
                              + "".join(celulas) + "</tr>")
            linhas.append(f"</{grupo}>")
        atributos = [("data-caption-above", _sim(no.caption_above)),
                     ("data-repeat-header", None if no.repeat_header else "0"),
                     ("data-width", _medida(no.width)),
                     ("data-alignment", no.alignment.value if no.alignment else None),
                     ("data-number", str(no.number) if no.number is not None else None),
                     ("data-summary", no.summary)]
        abre = self._abrir("table", no, classes=_classe_do_estilo(no.style), atributos=atributos,
                           ident=self._id(no, "b"))
        return abre + "\n" + "\n".join(linhas) + "\n</table>"

    def _bloco_image_block(self, no: ImageBlock) -> str:
        atributos = [("data-alignment", no.alignment.value if no.alignment else None),
                     ("data-crop", _json(no.crop) if no.crop else None)]
        return (self._abrir("figure", no, classes=("cb-image",), atributos=atributos,
                            ident=self._id(no, "b"))
                + self._imagem(no.resource, no.alt_text, no.title) + "</figure>")

    def _imagem(self, recurso: str, alt: str | None, titulo: str | None = None) -> str:
        atributos = _atributo("src", f"../Images/{recurso}")
        if alt is not None:
            atributos += _atributo("alt", alt)
        if titulo is not None:
            atributos += _atributo("title", titulo)
        return f"<img{atributos}/>"

    def _bloco_table_of_contents(self, no: TableOfContents) -> str:
        atributos = (("data-min-level", str(no.min_level)),
                     ("data-max-level", str(no.max_level)),
                     ("data-page-numbers", None if no.show_page_numbers else "0"),
                     ("data-leader", None if no.leader else "0"),
                     ("data-scope", no.scope if no.scope != "headings" else None))
        titulo = f"<h2>{self.inlines(no.title)}</h2>" if no.title else ""
        return (self._abrir("nav", no, classes=("cb-toc",), atributos=atributos,
                            ident=self._id(no, "b")) + f"{titulo}</nav>")

    def _bloco_group(self, no: Group) -> str:
        capitulo = no.role is GroupRole.CHAPTER
        etiqueta = "section" if capitulo else "div"
        classes = (("cb-chapter",) if capitulo else ()) + _classe_do_estilo(no.props.style)
        atributos = [("data-role", no.role.value if no.role not in (GroupRole.GENERIC,
                                                                     GroupRole.CHAPTER)
                      else None),
                     ("data-columns", str(no.columns) if no.columns is not None else None)]
        titulo = (f'<p class="cb-group-title">{self.inlines(no.title)}</p>\n'
                  if no.title else "")
        return (f"{self._abrir(etiqueta, no, classes=classes, atributos=atributos, ident=self._id(no, 'b'))}\n"  # noqa: E501
                f"{titulo}{self.blocos(no.content, no_topo=False)}\n</{etiqueta}>")

    def _bloco_callout(self, no: Callout) -> str:
        titulo = (f'<p class="cb-callout-title">{self.inlines(no.title)}</p>\n'
                  if no.title else "")
        atributos = (("data-kind", no.kind.value), ("data-collapsed", _sim(no.collapsed)))
        classes = ("cb-callout", *_classe_do_estilo(no.props.style))
        return (f"{self._abrir('aside', no, classes=classes, atributos=atributos, ident=self._id(no, 'b'))}\n"  # noqa: E501
                f"{titulo}{self.blocos(no.content, no_topo=False)}\n</aside>")

    def _bloco_math_block(self, no: MathBlock) -> str:
        atributos = (("display", "block" if no.display else "inline"),
                     ("data-numbered", _sim(no.numbered)), ("data-label", no.label),
                     ("data-mathml", no.mathml))
        abre = self._abrir("m:math", no, classes=_classe_do_estilo(no.props.style),
                           atributos=(("xmlns:m", MATHML), *atributos), ident=self._id(no, "b"))
        return (f'{abre}<m:annotation encoding="application/x-tex">{_texto(no.latex)}'
                "</m:annotation></m:math>")

    def _bloco_figure(self, no: Figure) -> str:
        partes = []
        if no.label is not None:
            partes.append(f'<span class="cb-figure-label">{_texto(no.label)}</span>')
        if no.caption:
            partes.append(f'<span class="cb-caption-text">{self.inlines(no.caption)}</span>')
        legenda = f"<figcaption>{' '.join(partes)}</figcaption>" if partes else ""
        atributos = (("data-number", str(no.number) if no.number is not None else None),
                     ("data-placement", no.placement.value
                      if no.placement is not FigurePlacement.HERE else None),
                     ("aria-label", no.alt_text))
        corpo = self.blocos(no.content, no_topo=False)
        miolo = [legenda, corpo] if no.caption_above else [corpo, legenda]
        abre = self._abrir("figure", no, classes=_classe_do_estilo(no.props.style),
                           atributos=(*atributos, ("data-caption-above", _sim(
                               no.caption_above and not legenda))), ident=self._id(no, "b"))
        return f"{abre}\n" + "\n".join(p for p in miolo if p) + "\n</figure>"

    # -- dentro do parágrafo ---------------------------------------------

    def inlines(self, inlines: Iterable[Any]) -> str:
        return "".join(self.inline(no) for no in inlines)

    def inline(self, no: Any) -> str:
        metodo = getattr(self, f"_inline_{tag_of(no)}", None)
        if metodo is None:
            raise ValueError(f"sem forma legível: {type(no).__name__}")
        return str(metodo(no))

    def _envolver(self, etiqueta: str, no: Any, conteudo: str, **kw: Any) -> str:
        return self._abrir(etiqueta, no, **kw) + conteudo + f"</{etiqueta}>"

    def _com_props(self, etiqueta: str, no: Any, conteudo: str, *,
                   classes: Sequence[str] = (), atributos: Sequence[tuple[str, str | None]] = ()
                   ) -> str:
        estilo, lingua = _corrida(no.props)
        return self._envolver(etiqueta, no, conteudo, classes=(*classes, *estilo),
                              atributos=(*atributos, *lingua))

    def _inline_text(self, no: Text) -> str:
        if not no.content:
            return ""
        estilo, lingua = _corrida(no.props)
        if not estilo and not lingua and not no.html_attributes:
            return _texto(no.content)
        return self._envolver("span", no, _texto(no.content), classes=estilo, atributos=lingua)

    def _inline_emphasis(self, no: Emphasis) -> str:
        return self._com_props("em", no, self.inlines(no.content))

    def _inline_strong(self, no: Strong) -> str:
        return self._com_props("strong", no, self.inlines(no.content))

    def _inline_underline(self, no: Underline) -> str:
        return self._com_props("u", no, self.inlines(no.content))

    def _inline_strike(self, no: Strike) -> str:
        return self._com_props("s", no, self.inlines(no.content))

    def _inline_superscript(self, no: Superscript) -> str:
        return self._com_props("sup", no, self.inlines(no.content))

    def _inline_subscript(self, no: Subscript) -> str:
        return self._com_props("sub", no, self.inlines(no.content))

    def _inline_small_caps(self, no: SmallCaps) -> str:
        return self._com_props("span", no, self.inlines(no.content), classes=("cb-smallcaps",))

    def _inline_span(self, no: Span) -> str:
        if _span_so_de_proveniencia(no):
            return self.inlines(no.content)  # N3: o intervalo vai ao proveniencia.json
        return self._com_props("span", no, self.inlines(no.content))

    def _inline_note_ref(self, no: NoteRef) -> str:
        atributos: list[tuple[str, str | None]] = [
            ("data-marker", "" if no.marker == "" else None)]
        if self._no_link:
            return self._com_props("span", no, _texto(no.marker or ""), classes=("cb-noteref",),
                                   atributos=[("data-href", f"#{no.ref}"), *atributos])
        return self._com_props("a", no, _texto(no.marker or ""), classes=("cb-noteref",),
                               atributos=[("epub:type", "noteref"), ("role", "doc-noteref"),
                                          ("href", f"#{no.ref}"), *atributos])

    def _inline_link(self, no: Link) -> str:
        atributos = [("title", no.tooltip), ("data-title", no.title),
                     ("data-kind", no.kind.value if no.kind is not _tipo_do_link(no.target)
                      else None)]
        if self._no_link:
            return self._com_props("span", no, self.inlines(no.content), classes=("cb-link",),
                                   atributos=[("data-href", no.target), *atributos])
        self._no_link = True
        try:
            conteudo = self.inlines(no.content)
        finally:
            self._no_link = False
        return self._com_props("a", no, conteudo, atributos=[("href", no.target), *atributos])

    def _inline_anchor(self, no: Anchor) -> str:
        return self._abrir("span", no, atributos=(("title", no.title),), ident=no.name) + "</span>"

    def _inline_line_break(self, no: LineBreak) -> str:
        return self._abrir("br", no, vazio=True)

    def _sem_atributos(self, no: Any) -> None:
        if no.html_attributes:
            raise ValueError(f"{type(no).__name__} com html_attributes: o caractere não os leva")

    def _inline_non_breaking_space(self, no: NonBreakingSpace) -> str:
        self._sem_atributos(no)
        return "\u00a0"

    def _inline_space(self, no: Space) -> str:
        self._sem_atributos(no)
        return ESPACOS.get(no.kind, " ")

    def _inline_tab(self, no: Tab) -> str:
        self._sem_atributos(no)
        return "\t"

    def _inline_raw_inline(self, no: RawInline) -> str:
        if no.html_attributes:
            raise ValueError("RawInline com html_attributes: o texto bruto não os leva")
        if no.format == "xhtml" and _bruto_fica(no.text, bloco=False):
            return no.text
        return self._envolver("span", no, _texto(no.text), classes=("cb-raw",),
                              atributos=(("data-format", no.format),))

    def _inline_piece_glyph(self, no: PieceGlyph) -> str:
        from caissa.export.text import figurine_char

        letra = _LETRA_DO_PECA.get(no.piece, "N")
        return self._com_props("span", no, _texto(figurine_char(letra, no.figurine_set)),
                               classes=("cb-piece",), atributos=(
                                   ("data-piece", letra), ("data-font-family", no.font_family)))

    def _inline_nag_symbol(self, no: NagSymbol) -> str:
        return self._com_props("span", no, _texto(_nag(no.nag)), classes=("cb-nag",),
                               atributos=(("data-nag", str(no.nag)),))

    def _inline_math_inline(self, no: MathInline) -> str:
        abre = self._abrir("m:math", no, atributos=(("xmlns:m", MATHML),
                                                     ("data-mathml", no.mathml)))
        return (f'{abre}<m:annotation encoding="application/x-tex">{_texto(no.latex)}'
                "</m:annotation></m:math>")

    def _inline_image_inline(self, no: ImageInline) -> str:
        atributos = [("src", f"../Images/{no.resource}"), ("alt", no.alt_text)]
        return self._abrir("img", no, atributos=atributos, vazio=True)

    def _inline_inline_diagram(self, no: InlineDiagram) -> str:
        from caissa.export.diagrams import descrever_posicao

        fen = no.fen or ""
        campos = fen.split()
        orientacao = "black" if no.orientation is Orientation.BLACK else "white"
        nome = _imagem_do_diagrama(fen, orientacao)
        alt = no.alt_text if no.alt_text is not None else descrever_posicao(
            fen, campos[1] if len(campos) > 1 else None, self.idioma, True, miniatura=True)
        if nome not in self.imagens:
            self.imagens[nome] = self._svg(no)
        img = f'<img class="cb-svg" src="../Images/{nome}" alt={quoteattr(alt)}/>'
        classes = ("cb-inline-diagram", *((f"cb-style-{slug(no.style)}",) if no.style else ()))
        return self._envolver("span", no, img, classes=classes, atributos=(
            ("data-fen", fen), ("data-orientation", orientacao), ("data-size", _medida(no.size)),
            ("data-marks", _marcas(no.marks))))

    def _inline_index_entry(self, no: IndexEntry) -> str:
        return self._envolver("span", no, "", classes=("cb-index-mark",), atributos=(
            ("data-term", "|".join(no.terms)), ("data-sort-key", no.sort_key),
            ("data-see-also", "|".join(no.see_also) if no.see_also else None),
            ("data-primary", _sim(no.primary))))

    def _inline_move(self, no: Move) -> str:
        """O lance no meio da prosa: o `cb-move` do contrato.

        Com o `data-san` e o `data-fen-before` (extensões), porque o texto não diz de onde ele
        parte.
        """
        import chess

        atributos: list[tuple[str, str | None]] = [
            ("data-san", no.san), ("data-fen-before", no.position_before or None),
            ("data-uci", no.uci)]
        derivado = None
        if no.position_before:
            try:
                tabuleiro = chess.Board(no.position_before)
                lance = (chess.Move.from_uci(no.uci) if no.uci else tabuleiro.parse_san(no.san))
                if lance in tabuleiro.legal_moves:
                    tabuleiro.push(lance)
                    atributos.append(("data-fen", tabuleiro.fen()))
            except ValueError:
                pass
            derivado = _meio_lance_da_fen(no.position_before)
        if no.ply != (derivado or 0):  # sem posição, o leitor lê o 0
            atributos.append(("data-ply", str(no.ply)))
        automatico = _texto_do_numero(no.ply)
        numero = ""
        if no.show_move_number:
            numero = f'<span class="cb-movenum">{_texto(automatico)}</span>'
        if no.move_number_text is not None:
            atributos.append(("data-number-text", no.move_number_text))
        pecas: list[tuple[str, str]] = []
        corpo = _cabeca_do_lance(no.san, (no.render, no.language, no.figurine_set), pecas)
        nags = "".join(f'<span class="cb-nag" data-nag="{n}">{_texto(_nag(n))}</span>'
                       for n in no.nags)
        padrao = (MoveRenderStyle.LETTERS, "en", FigurineSet.BLACK)
        atributos += _atributos_da_notacao(
            (no.render, no.language, no.figurine_set),
            _notacao_das_pecas(pecas, self.idioma, padrao))
        return self._com_props("span", no, numero + corpo + nags, classes=("cb-move",),
                               atributos=atributos)


def _meio_lance_da_fen(fen: str) -> int | None:
    """O `ply` (1 = o primeiro lance das brancas) do lance jogado a partir da FEN."""
    campos = fen.split()
    if len(campos) < 6 or not campos[5].isdigit() or campos[1] not in ("w", "b"):  # noqa: PLR2004
        return None
    return (int(campos[5]) - 1) * 2 + (1 if campos[1] == "w" else 2)


def _texto_do_numero(ply: int) -> str:
    """O número que o livro imprime antes do lance: `12.` ou `12…`."""
    numero = (max(ply, 1) + 1) // 2
    return f"{numero}…" if ply % 2 == 0 and ply > 0 else f"{numero}."


def _cabeca_do_lance(san: str, notacao: tuple[MoveRenderStyle, str, FigurineSet],
                     pecas: list[tuple[str, str]]) -> str:
    """O SAN como o livro o imprime: a peça num `cb-piece` (figurina ou letra do idioma)."""
    if san and san[0] in "KQRBN" and not san.startswith("O-O"):
        letra = san[0]
        visivel = _visivel_da_peca(letra, notacao[0] is MoveRenderStyle.FIGURINE, notacao[2],
                                   notacao[1])
        pecas.append((letra, visivel))
        return (f'<span class="cb-piece" data-piece="{letra}">{_texto(visivel)}</span>'
                f"{_texto(san[1:])}")
    return _texto(san)


def _tipo_do_link(alvo: str) -> LinkKind:
    """O tipo que o `href` diz sozinho; o `data-kind` só vai quando o IR diz outro."""
    if alvo.startswith("#"):
        return LinkKind.INTERNAL
    if alvo.startswith("mailto:"):
        return LinkKind.EMAIL
    if "://" in alvo:
        return LinkKind.EXTERNAL
    return LinkKind.RESOURCE


def _span_so_de_proveniencia(no: Span) -> bool:
    """O `Span` que só carrega proveniência (a N3): o escritor não o marca."""
    return no.provenance is not None and no.props == RunProps() and not no.html_attributes


def _paragrafo_simples(no: Paragraph) -> bool:
    """O parágrafo que a célula ou o item levam como texto solto: sem nada além do conteúdo."""
    return (not no.props.style and no.drop_cap is None and not no.html_attributes
            and not _chaveado(no))


def _bruto_fica(texto: str, *, bloco: bool) -> bool:
    """Se o texto `xhtml` bruto volta como bruto quando escrito como está."""
    elemento = _fragmento(texto)
    if elemento is None:
        return False
    leitor = _Leitor(None)
    try:
        no = leitor.bloco(elemento) if bloco else leitor.inline(elemento)
    except (ValueError, KeyError, IndexError, TypeError):
        return False
    return isinstance(no, RawPassthrough if bloco else RawInline)


class _EscritorDePartida:
    """A partida no contrato do CB: cabeçalho, linhas de lances, comentários e variantes.

    O lance que o tabuleiro joga vai na forma do contrato (`data-uci` quando o IR o tem, e o
    `data-fen` depois dele); o que os campos do IR dizem e o tabuleiro não deriva vai nos
    `data-*` de extensão. O lance que não se joga ali vai na forma literal: o `data-san`, o
    `data-ply` e as posições que o IR guarda, sem `data-fen` (o CB o lê como anterior ao contrato).
    """

    def __init__(self, escritor: EscritorLegivel) -> None:
        self.escritor = escritor
        self.pecas: list[tuple[str, str]] = []

    def partida(self, no: GameScore, ident: str | None, *,
                classes_extras: Sequence[str] = ()) -> str:
        import chess

        cabecalhos = no.headers
        render = no.render
        linhas: list[str] = []
        try:
            tabuleiro = chess.Board(no.initial_fen) if no.initial_fen else chess.Board()
        except ValueError:
            tabuleiro = None
        if no.initial_comment:
            linhas.append(f'<p class="cb-comment">{_texto(no.initial_comment)}</p>')
        self._linhas(no.children, tabuleiro, 0, linhas, render, variante=False)
        atributos: list[tuple[str, str | None]] = []
        eco = next((t.value for t in cabecalhos.extra if t.name == "ECO"), None)
        atributos.append(("data-eco", eco or None))
        # O resultado: o `data-result` quando se sabe; o `p.cb-result` quando, além disso, a
        # partida o imprime (`show_result`). Um resultado desconhecido (`*`) não se escreve.
        conhecido = cabecalhos.result not in ("", "*")
        atributos.append(("data-result", cabecalhos.result if conhecido else None))
        if cabecalhos.result == "":
            atributos.append(("data-result-empty", "1"))
        atributos.append(("data-initial-fen", no.initial_fen))
        atributos.append(("data-variant", no.variant if no.variant != "standard" else None))
        atributos.append(("data-show-result", "0" if not conhecido and not render.show_result
                          else None))
        atributos.append(("data-variation-style", render.variation_style.value
                          if render.variation_style is not VariationStyle.INLINE else None))
        atributos.append(("data-max-variation-depth", str(render.max_variation_depth)
                          if render.max_variation_depth is not None else None))
        padrao = (GameRenderOptions().render, GameRenderOptions().language,
                  GameRenderOptions().figurine_set)
        atributos += _atributos_da_notacao(
            (render.render, render.language, render.figurine_set),
            _notacao_das_pecas(self.pecas, self.escritor.idioma, padrao))
        partes = [self.escritor._abrir("section", no, classes=("cb-game", *classes_extras),
                                       atributos=atributos, ident=ident)]
        if no.title is not None:
            partes.append(f'<p class="cb-game-title">{_texto(no.title)}</p>')
        cabecalho = self._cabecalho(no)
        if cabecalho:
            partes.append(cabecalho)
        partes.append('<div class="cb-moves">')
        partes += linhas
        partes.append("</div>")
        if conhecido and render.show_result:
            partes.append(f'<p class="cb-result">{_texto(cabecalhos.result)}</p>')
        partes.append("</section>")
        return "\n".join(partes)

    def _cabecalho(self, no: GameScore) -> str:  # noqa: PLR0912 - uma linha por campo do MARKUP
        h = no.headers
        valor = {t.name: t.value for t in h.extra}
        linhas = []
        if "GameNumber" in valor:
            linhas.append(f'<p class="cb-game-number">{_texto(valor["GameNumber"])}</p>')
        for cor, nome, tag in (("cb-white", h.white, "WhiteElo"),
                               ("cb-black", h.black, "BlackElo")):
            partes = []
            if tag in valor:
                partes.append(f'<span class="cb-elo">{_texto(valor[tag])}</span>')
            if nome not in ("", "?"):
                partes.append(f'<span class="cb-name">{_texto(nome)}</span>')
            if partes:
                linhas.append(f'<p class="cb-player {cor}">' + " ".join(partes) + "</p>")
        evento = []
        if h.event not in ("", "?"):
            evento.append(f'<span class="cb-event-name">{_texto(h.event)}</span>')
        if h.site not in ("", "?"):
            evento.append(f'<span class="cb-site">{_texto(h.site)}</span>')
        if h.round not in ("", "?"):
            evento.append(f'<span class="cb-round">({_texto(h.round)})</span>')
        if h.date not in ("", "????.??.??"):
            iso = h.date.replace(".", "-")
            evento.append(f'<time class="cb-date" datetime={quoteattr(iso)}>{_texto(h.date)}'
                          "</time>")
        if evento:
            linhas.append('<p class="cb-event">' + " ".join(evento) + "</p>")
        abertura = []
        if "Opening" in valor:
            abertura.append(f'<span class="cb-opening-name">{_texto(valor["Opening"])}</span>')
        if "ECO" in valor:
            abertura.append(f'<span class="cb-eco">{_texto(valor["ECO"])}</span>')
        if abertura:
            linhas.append('<p class="cb-opening">' + " ".join(abertura) + "</p>")
        if no.annotator is not None:
            linhas.append(f'<p class="cb-annotator">{_texto(no.annotator)}</p>')
        linhas.extend(f'<p class="cb-tag" data-name={quoteattr(tag.name)}>'
                      f"{_texto(tag.value)}</p>"
                      for tag in h.extra if tag.name not in _TAGS_DO_CABECALHO)
        ordem = [t.name for t in h.extra]
        natural = [n for n in _TAGS_DO_CABECALHO if n in valor] + [
            t.name for t in h.extra if t.name not in _TAGS_DO_CABECALHO]
        atributos = ""
        if ordem != natural:
            atributos += f" data-tag-order={quoteattr(' '.join(ordem))}"
        if not no.render.show_headers:
            atributos += ' hidden="hidden"'
        if not linhas and no.render.show_headers:
            return ""
        return "\n".join([f'<header class="cb-game-header"{atributos}>', *linhas, "</header>"])

    def _linhas(self, filhos: Sequence[MoveNode], tabuleiro: Any, profundidade: int,
                partes: list[str], render: GameRenderOptions, *, variante: bool) -> None:
        """Uma linha de lances; o comentário e as variantes quebram o parágrafo."""
        classe = ("cb-line cb-mainline" if profundidade == 0
                  else f"cb-line cb-variation cb-depth-{profundidade}")
        paragrafo: list[str] = []
        abre_variante = variante
        primeiro_literal = False

        def fechar() -> None:
            nonlocal paragrafo, abre_variante
            if not paragrafo:
                return
            marca = ' data-variation-start="1"' if abre_variante and primeiro_literal else ""
            partes.append(f'<p class="{classe}"{marca}>' + " ".join(paragrafo) + "</p>")
            paragrafo = []
            abre_variante = False

        primeiro = True
        atual = tuple(filhos)
        while atual:
            principal = atual[0]
            if principal.comment_before:
                fechar()
                partes.append(f'<p class="cb-comment" data-attach="before">'
                              f"{_texto(principal.comment_before)}</p>")
                primeiro = True
            antes = tabuleiro.copy() if tabuleiro is not None else None
            fichas, tabuleiro, literal = self._lance(principal, tabuleiro, primeiro, render)
            if not paragrafo:
                primeiro_literal = literal
            paragrafo += fichas
            primeiro = False
            if principal.comment_after or len(atual) > 1:
                fechar()
                if principal.comment_after:
                    partes.append(f'<p class="cb-comment">{_texto(principal.comment_after)}</p>')
                for alternativa in atual[1:]:
                    self._linhas((alternativa,), antes.copy() if antes is not None else None,
                                 profundidade + 1, partes, render, variante=True)
                primeiro = True
            atual = principal.children
        fechar()

    @staticmethod
    def _jogavel(no: MoveNode, tabuleiro: Any) -> Any:
        """O lance no tabuleiro, ou ``None`` quando ele não se joga ali."""
        import chess

        if tabuleiro is None:
            return None
        try:
            lance = chess.Move.from_uci(no.uci) if no.uci else tabuleiro.parse_san(no.san)
        except ValueError:
            return None
        return lance if lance in tabuleiro.legal_moves else None

    def _anotacoes(self, no: MoveNode) -> list[tuple[str, str | None]]:
        """As anotações do lance (os comandos `[%...]` do PGN e o lance-chave)."""
        relogio, avaliacao = no.clock, no.evaluation
        return [
            ("data-emphasis", _sim(no.emphasis)),
            ("data-clock", relogio.text if relogio is not None else None),
            ("data-clock-kind", relogio.kind.value if relogio is not None else None),
            ("data-clock-seconds", _numero(relogio.seconds)
             if relogio is not None and relogio.seconds is not None else None),
            ("data-eval", avaliacao.text if avaliacao is not None else None),
            ("data-eval-kind", avaliacao.kind.value if avaliacao is not None else None),
            ("data-eval-value", _numero(avaliacao.value) if avaliacao is not None else None),
            ("data-eval-depth", str(avaliacao.depth)
             if avaliacao is not None and avaliacao.depth is not None else None),
            ("data-arrows", _marcas(no.arrows)),
            ("data-highlights", _marcas(no.highlights))]

    def _lance(self, no: MoveNode, tabuleiro: Any, primeiro: bool,
               render: GameRenderOptions) -> tuple[list[str], Any, bool]:
        """As fichas do lance, o tabuleiro depois dele e se ele foi na forma literal.

        O tabuleiro é ``None`` quando o lance não se joga ali.
        """
        import chess

        fichas = []
        lance = self._jogavel(no, tabuleiro)
        if lance is None:
            if not no.is_black_move or primeiro:
                fichas.append(f'<span class="cb-movenum">{_texto_do_numero(no.ply)}</span>')
            atributos = [("data-san", no.san), ("data-uci", no.uci),
                         ("data-fen-before", no.position_before or None),
                         ("data-fen-after", no.position_after or None),
                         ("data-ply", str(no.ply)), *self._anotacoes(no)]
            fichas.append(self.escritor._envolver("span", no, _texto(no.san),
                                                  classes=("cb-move",), atributos=atributos))
            fichas += [f'<span class="cb-nag" data-nag="{n}">{_texto(_nag(n))}</span>'
                       for n in no.nags]
            return fichas, None, True
        numero = tabuleiro.fullmove_number
        if tabuleiro.turn == chess.WHITE:
            fichas.append(f'<span class="cb-movenum">{numero}.</span>')
        elif primeiro:
            fichas.append(f'<span class="cb-movenum">{numero}…</span>')
        antes = tabuleiro.fen()
        meio_lance = (tabuleiro.fullmove_number - 1) * 2 + (1 if tabuleiro.turn else 2)
        san = tabuleiro.san(lance)
        tabuleiro.push(lance)
        depois = tabuleiro.fen()
        corpo = _cabeca_do_lance(san, (render.render, render.language, render.figurine_set),
                                 self.pecas)
        atributos = [("data-uci", no.uci), ("data-fen", depois),
                     ("data-san", no.san if no.san != san else None),
                     ("data-fen-before", no.position_before if no.position_before != antes
                      else None),
                     ("data-fen-after", no.position_after if no.position_after != depois
                      else None),
                     ("data-ply", str(no.ply) if no.ply != meio_lance else None),
                     *self._anotacoes(no)]
        fichas.append(self.escritor._envolver("span", no, corpo, classes=("cb-move",),
                                              atributos=atributos))
        fichas += [f'<span class="cb-nag" data-nag="{n}">{_texto(_nag(n))}</span>'
                   for n in no.nags]
        return fichas, tabuleiro, False


_TAGS_DO_CABECALHO = ("GameNumber", "WhiteElo", "BlackElo", "Opening", "ECO")
"""As etiquetas do PGN que o cabeçalho do MARKUP imprime, na ordem em que o leitor as acha."""


# --------------------------------------------------------------------------- #
# O leitor
# --------------------------------------------------------------------------- #

_MARCADOR = re.compile(r"^pg[1-9]\d*$")
_ROTULO_NUMERADO = re.compile(r"^Diagrama (\d+)$")


def _classes(elemento: ET.Element) -> list[str]:
    return (elemento.get("class") or "").split()


def _preservados(elemento: ET.Element, *, conhecidos: Iterable[str] = (),
                 classes_conhecidas: Iterable[str] = (), guardar_id: bool = True
                 ) -> tuple[tuple[str, str], ...]:
    """Os atributos que o contrato não modela neste elemento, para `html_attributes`.

    Na ordem do `canon` (o nome), que é a ordem em que o escritor os devolve (N4).
    """
    fora = set(conhecidos)
    if not guardar_id:
        fora.add("id")
    conhecidas = set(classes_conhecidas)
    pares = []
    for nome, valor in _atributos(elemento):
        if nome == "class":
            extras = [c for c in valor.split() if c not in conhecidas]
            if extras:
                pares.append(("class", " ".join(extras)))
        elif nome not in fora:
            pares.append((nome, valor))
    return tuple(sorted(pares))


def _estilo_das_classes(classes: Sequence[str], estilo_do_slug: Mapping[str, str], *,
                        do_contrato: bool = True) -> tuple[str | None, list[str]]:
    """O estilo nomeado (a primeira classe de estilo) e as classes que o disseram."""
    for classe in classes:
        if do_contrato and classe in _CLASSE_DO_ESTILO:
            return _CLASSE_DO_ESTILO[classe], [classe]
        if classe.startswith("cb-style-"):
            pedaco = classe.removeprefix("cb-style-")
            return estilo_do_slug.get(pedaco, pedaco), [classe]
    return None, []


class _Leitor:
    """XHTML legível → IR, pelo contrato; o resto, preservado."""

    def __init__(self, mapa: MapaDaProveniencia | None, estilos: Iterable[str] = (),
                 idioma: str = "pt-BR", *, conferir: bool = True) -> None:
        self.mapa = mapa
        self.idioma = idioma
        self.estilo_do_slug = {slug(nome): nome for nome in estilos}
        self.conferir = conferir
        """Se cada elemento lido é reescrito e comparado com o original (R2.3)."""
        self._dentro_de_link = False
        """Se o elemento em leitura está dentro de um link (o escritor muda a forma, lá)."""
        self.brutos: list[str] = []
        """O que a conferência guardou como bruto (`Capitulo.brutos`)."""

    # -- a conferência ---------------------------------------------------

    def _confere(self, no: Any, elemento: ET.Element, *, bloco: bool) -> bool:
        """Se o nó, reescrito, é o elemento de volta — o que o IR não guardou não se perdeu.

        O que o elemento tem e o nó não diz (um atributo num elemento interno da partida, a
        marcação dentro de um comentário, o `title` na imagem do diagrama) faz a reescrita sair
        diferente; o leitor então guarda o elemento inteiro como bruto, e nada se perde em
        silêncio. A comparação é pelo `canon`, sem os `id` de página (o mapa os devolve) e com o
        que o contrato diz derivado recalculado no original (§6.1: a imagem do diagrama, o
        `data-stm`, o `data-mode` e a fala do lado que joga).
        """
        escritor = EscritorLegivel()
        escritor.idioma = self.idioma
        escritor._no_link = self._dentro_de_link
        try:
            escrito = escritor.bloco(no) if bloco else escritor.inline(no)
            original = _serializar(_entrada_normalizada(elemento, self.idioma), ordenar=False)
            return _canon_de_fragmento(escrito) == _canon_de_fragmento(original)
        except (ValueError, KeyError, TypeError, IndexError, ET.ParseError):
            return False

    # -- identidade ------------------------------------------------------

    def _identidade(  # noqa: PLR0911 - um retorno por origem do `id`
            self, elemento: ET.Element, tipo: type) -> tuple[dict[str, Any], set[str]]:
        """O que o `id` do elemento devolve ao nó, e os nomes que ele consumiu.

        Com o mapa, a identidade e o dado da máquina do nó original; o `id` volta como a âncora,
        a referência da nota ou o `id` preservado que o original tinha. Sem o mapa, o `id` é a
        âncora do nó (quando o tipo tem uma), ou fica em `html_attributes`.
        """
        ident = elemento.get("id")
        kw: dict[str, Any] = {}
        if not ident:
            return kw, set()
        tem_ancora = "anchor" in {f.name for f in fields(tipo)}
        e_nota = tipo in (Footnote, Endnote)
        if self.mapa is not None and ident in self.mapa.nos:
            registro = self.mapa.nos[ident]
            kw["id"] = registro.ir_id
            kw["provenance"] = registro.proveniencia
            if tipo is Diagram:
                kw.update(recognition=registro.reconhecimento or RecognitionResult(),
                          source=registro.fonte or DiagramSource(),
                          verified_by_human=registro.conferido)
            if e_nota:
                return kw, {"id"}
            if tem_ancora and registro.origem == "ancora":
                kw["anchor"] = ident
                return kw, {"id"}
            if registro.origem == "html":
                return kw, set()
            return kw, {"id"}
        if e_nota:
            return kw, {"id"}
        if tem_ancora:
            kw["anchor"] = ident
            return kw, {"id"}
        return kw, set()

    def _estilo(self, classes: Sequence[str]) -> tuple[str | None, list[str]]:
        return _estilo_das_classes(classes, self.estilo_do_slug)

    def _props_de_bloco(self, elemento: ET.Element) -> tuple[ParagraphProps, list[str]]:
        estilo, usadas = self._estilo(_classes(elemento))
        return (ParagraphProps(style=estilo) if estilo else ParagraphProps()), usadas

    def _props_de_corrida(self, elemento: ET.Element) -> tuple[RunProps, list[str], list[str]]:
        """As `RunProps` do elemento: a classe de estilo e a língua (o par `lang`/`xml:lang`)."""
        estilo, usadas = _estilo_das_classes(_classes(elemento), self.estilo_do_slug,
                                             do_contrato=False)
        lingua = elemento.get("lang")
        conhecidos = ["lang", "xml:lang"] if lingua and elemento.get(
            f"{{{XML}}}lang") == lingua else []
        return (RunProps(style=estilo, language=lingua if conhecidos else None), usadas,
                conhecidos)

    # -- blocos ----------------------------------------------------------

    def blocos(self, pai: ET.Element, *, ignorar: Iterable[ET.Element] = ()) -> list[Any]:
        fora = {id(e) for e in ignorar}
        return [self.bloco(filho) for filho in pai if id(filho) not in fora]

    def bloco(self, elemento: ET.Element) -> Any:
        """O bloco do elemento; o que não volta igual pela reescrita fica bruto (R2.3)."""
        no = self._bloco(elemento)
        if self.conferir and not isinstance(no, RawPassthrough) and not self._confere(
                no, elemento, bloco=True):
            self.brutos.append(_descricao(elemento))
            return RawPassthrough(format="xhtml", text=serializar_elemento(elemento))
        return no

    def _bloco(self, elemento: ET.Element) -> Any:  # noqa: PLR0911, PLR0912 - um ramo por forma
        nome = _local(elemento)
        classes = _classes(elemento)
        if nome in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return self._titulo(elemento, int(nome[1]))
        if nome == "p" and "cb-ornament" in classes:
            kw, usados = self._identidade(elemento, ThematicBreak)
            return ThematicBreak(ornament="".join(elemento.itertext()), **kw,
                                 html_attributes=_preservados(
                                     elemento, conhecidos=usados,
                                     classes_conhecidas=("cb-ornament",)))
        if nome == "p":
            return self._paragrafo(elemento)
        if nome == "figure" and "cb-diagram" in classes:
            return self._diagrama(elemento)
        if nome == "section" and "cb-game" in classes:
            return _LeitorDePartida(self).partida(elemento)
        if nome == "aside" and elemento.get(f"{{{EPUB}}}type") in ("footnote", "endnote"):
            return self._nota(elemento)
        if nome == "blockquote":
            return self._citacao(elemento)
        if nome in ("ul", "ol", "dl"):
            return self._lista(elemento, nome)
        if nome == "hr" and "cb-section-break" in classes:
            return self._quebra_de_secao(elemento)
        if nome == "div" and "cb-section-break" in classes:
            return self._quebra_de_secao(elemento)
        if nome == "hr":
            kw, usados = self._identidade(elemento, ThematicBreak)
            return ThematicBreak(**kw, html_attributes=_preservados(elemento, conhecidos=usados))
        if nome == "div" and "cb-page-break" in classes and not len(elemento):
            kw, usados = self._identidade(elemento, PageBreak)
            return PageBreak(**kw, html_attributes=_preservados(
                elemento, conhecidos=usados, classes_conhecidas=("cb-page-break",)))
        if nome == "pre" and "cb-raw" in classes:
            return RawPassthrough(format=elemento.get("data-format") or "text",
                                  text="".join(elemento.itertext()))
        if nome == "pre" and len(elemento) == 1 and _local(elemento[0]) == "code" and not (
                elemento.text or "") and not (elemento[0].tail or ""):
            return self._codigo(elemento)
        if nome == "table":
            return self._tabela(elemento)
        if nome == "figure" and "cb-image" in classes:
            img = next((f for f in elemento if _local(f) == "img"), None)
            if img is not None and len(elemento) == 1:
                return self._imagem(elemento, img)
        if nome == "figure" and "cb-diagram" not in classes:
            return self._figura(elemento)
        if nome == "nav" and "cb-toc" in classes:
            return self._sumario(elemento)
        if nome == "aside" and "cb-callout" in classes:
            return self._destaque(elemento)
        if _formula_do_contrato(elemento):
            return self._formula(elemento)
        if (nome == "section" and "cb-chapter" in classes) or nome == "div":
            return self._grupo(elemento, capitulo=nome == "section")
        return RawPassthrough(format="xhtml", text=serializar_elemento(elemento))

    def _titulo(self, elemento: ET.Element, nivel: int) -> Heading:
        kw, usados = self._identidade(elemento, Heading)
        props, classes = self._props_de_bloco(elemento)
        numero = None
        filhos = list(elemento)
        if filhos and "cb-heading-number" in _classes(filhos[0]) and not elemento.text:
            numero = "".join(filhos[0].itertext())
            resto = ET.Element(elemento.tag)
            cauda = filhos[0].tail or ""
            resto.text = cauda[1:] if cauda.startswith(" ") else cauda
            resto.extend(filhos[1:])
            conteudo = self.inlines(resto)
        else:
            conteudo = self.inlines(elemento)
        numeracao = elemento.get("data-numbering")
        return Heading(
            level=int(elemento.get("data-level") or nivel), content=tuple(conteudo),
            numbering_text=numero, props=props, toc_text=elemento.get("data-toc-text"),
            list_in_toc=elemento.get("data-in-toc") != "0",
            numbering=_json_de(numeracao, NumberingRef),
            html_attributes=_preservados(
                elemento, conhecidos=(*usados, "data-level", "data-toc-text", "data-in-toc",
                                      "data-numbering"), classes_conhecidas=classes), **kw)

    def _paragrafo(self, elemento: ET.Element) -> Paragraph:
        kw, usados = self._identidade(elemento, Paragraph)
        props, conhecidas = self._props_de_bloco(elemento)
        classes = _classes(elemento)
        drop = elemento.get("data-drop-cap")
        conhecidos = ["data-drop-cap"] if drop is not None and "cb-dropcap" in classes else []
        if conhecidos:
            conhecidas.append("cb-dropcap")
        return Paragraph(content=tuple(self.inlines(elemento)), props=props,
                         drop_cap=int(drop) if conhecidos and drop is not None else None,
                         html_attributes=_preservados(elemento,
                                                      conhecidos=(*conhecidos, *usados),
                                                      classes_conhecidas=conhecidas), **kw)

    def _nota(self, elemento: ET.Element) -> Footnote | Endnote:
        classe = Footnote if elemento.get(f"{{{EPUB}}}type") == "footnote" else Endnote
        kw, usados = self._identidade(elemento, classe)
        props, conhecidas = self._props_de_bloco(elemento)
        return classe(ref=elemento.get("id") or "", content=tuple(self.blocos(elemento)),
                      marker=elemento.get("data-marker"), props=props,
                      html_attributes=_preservados(
                          elemento, conhecidos=(*usados, "id", "epub:type", "role",
                                                "data-marker"),
                          classes_conhecidas=conhecidas), **kw)

    def _citacao(self, elemento: ET.Element) -> Quote:
        kw, usados = self._identidade(elemento, Quote)
        props, conhecidas = self._props_de_bloco(elemento)
        rodape = next((f for f in elemento if _local(f) == "footer"), None)
        return Quote(content=tuple(self.blocos(elemento, ignorar=[rodape] if rodape is not None
                                                else [])),
                     attribution=tuple(self.inlines(rodape)) if rodape is not None else (),
                     props=props, html_attributes=_preservados(
                         elemento, conhecidos=usados, classes_conhecidas=conhecidas), **kw)

    def _lista(self, elemento: ET.Element, nome: str) -> ListBlock:
        kw, usados = self._identidade(elemento, ListBlock)
        props, conhecidas = self._props_de_bloco(elemento)
        tipo = {"ol": ListKind.ORDERED, "dl": ListKind.DEFINITION}.get(nome, ListKind.UNORDERED)
        padrao = ListMarkerStyle.DECIMAL if tipo is ListKind.ORDERED else ListMarkerStyle.BULLET
        itens: list[ListItem] = []
        filhos = list(elemento)
        if nome == "dl":
            for termo, definicao in zip(filhos[::2], filhos[1::2], strict=False):
                itens.append(self._item(definicao, termo=tuple(self.inlines(termo)),
                                        valor="data-value"))
        else:
            itens = [self._item(li, valor="value" if nome == "ol" else "data-value")
                     for li in filhos if _local(li) == "li"]
        inicio = elemento.get("start") if nome == "ol" else elemento.get("data-start")
        estilo = elemento.get("data-marker-style")
        return ListBlock(
            kind=tipo, items=tuple(itens), start=int(inicio) if inicio else 1,
            marker_style=ListMarkerStyle(estilo) if estilo else padrao,
            marker_text=elemento.get("data-marker-text"),
            tight=elemento.get("data-tight") == "1",
            numbering=_json_de(elemento.get("data-numbering"), NumberingRef),
            indent=_medida_de(elemento.get("data-indent")), props=props,
            html_attributes=_preservados(
                elemento, conhecidos=(*usados, "start" if nome == "ol" else "data-start",
                                      "data-marker-style", "data-marker-text", "data-tight",
                                      "data-numbering", "data-indent"),
                classes_conhecidas=conhecidas), **kw)

    def _item(self, elemento: ET.Element, *, termo: tuple[Any, ...] = (),
              valor: str = "data-value") -> ListItem:
        filhos = list(elemento)
        ignorar = []
        if filhos and "cb-term" in _classes(filhos[0]) and not elemento.text:
            termo = tuple(self.inlines(filhos[0]))
            ignorar = [filhos[0]]
        marcado = elemento.get("data-checked")
        inicio = elemento.get(valor)
        return ListItem(content=tuple(self._conteudo(elemento, ignorar=ignorar)), term=termo,
                        marker_override=elemento.get("data-marker"),
                        start_override=int(inicio) if inicio is not None else None,
                        checked=None if marcado is None else marcado == "1",
                        html_attributes=_preservados(
                            elemento, conhecidos=(valor, "data-marker", "data-checked")))

    def _conteudo(self, elemento: ET.Element, *, ignorar: Sequence[ET.Element] = ()
                  ) -> list[Any]:
        """O conteúdo da célula ou do item: blocos, ou o texto solto como um parágrafo."""
        filhos = [f for f in elemento if f not in ignorar]
        texto = elemento.text if not ignorar else (ignorar[-1].tail or "")
        # A fórmula de bloco sempre diz o `display`; a de dentro do parágrafo, nunca.
        if any(_local(f) in BLOCOS or (_nome(f.tag) == "m:math" and f.get("display") is not None)
               for f in filhos):
            return self.blocos(elemento, ignorar=ignorar)
        if not filhos and not texto:
            return []
        falso = ET.Element(elemento.tag)
        falso.text = texto
        falso.extend(filhos)
        return [Paragraph(content=tuple(self.inlines(falso)))]

    def _quebra_de_secao(self, elemento: ET.Element) -> SectionBreak:
        kw, usados = self._identidade(elemento, SectionBreak)
        cabeca: tuple[Any, ...] = ()
        pe: tuple[Any, ...] = ()
        for filho in elemento:
            if "cb-running-head" in _classes(filho):
                cabeca = tuple(self.inlines(filho))
            elif "cb-running-foot" in _classes(filho):
                pe = tuple(self.inlines(filho))
        inicio = elemento.get("data-page-number-start")
        alinhamento = elemento.get("data-vertical-alignment")
        conhecidos = ("data-kind", "data-columns", "data-geometry", "data-different-first",
                      "data-different-odd-even", "data-page-number-start",
                      "data-page-number-format", "data-vertical-alignment")
        return SectionBreak(
            kind=SectionBreakKind(elemento.get("data-kind") or "next-page"),
            columns=_json_de(elemento.get("data-columns"), ColumnLayout),
            geometry=_json_de(elemento.get("data-geometry"), PageGeometry),
            header_text=cabeca, footer_text=pe,
            different_first_page=elemento.get("data-different-first") == "1",
            different_odd_even=elemento.get("data-different-odd-even") == "1",
            page_number_start=int(inicio) if inicio else None,
            page_number_format=elemento.get("data-page-number-format"),
            vertical_alignment=VerticalCellAlignment(alinhamento) if alinhamento else None,
            html_attributes=_preservados(elemento, conhecidos=(*usados, *conhecidos),
                                         classes_conhecidas=("cb-section-break",)), **kw)

    def _codigo(self, elemento: ET.Element) -> CodeBlock:
        kw, usados = self._identidade(elemento, CodeBlock)
        props, conhecidas = self._props_de_bloco(elemento)
        classe = elemento[0].get("class") or ""
        return CodeBlock(text="".join(elemento[0].itertext()),
                         language=classe.removeprefix("language-")
                         if classe.startswith("language-") else "",
                         show_line_numbers=elemento.get("data-line-numbers") == "1",
                         props=props, html_attributes=_preservados(
                             elemento, conhecidos=(*usados, "data-line-numbers"),
                             classes_conhecidas=conhecidas), **kw)

    def _tabela(self, elemento: ET.Element) -> Table:
        kw, usados = self._identidade(elemento, Table)
        estilo, conhecidas = _estilo_das_classes(_classes(elemento), self.estilo_do_slug)
        legenda = next((f for f in elemento if _local(f) == "caption"), None)
        filas: list[TableRow] = []
        cabeca = rodape = 0
        for grupo in elemento:
            if _local(grupo) not in ("thead", "tbody", "tfoot"):
                continue
            for fila in grupo:
                celulas = []
                for celula in fila:
                    colunas, linhas = celula.get("colspan"), celula.get("rowspan")
                    celulas.append(TableCell(
                        content=tuple(self._conteudo(celula)),
                        col_span=int(colunas) if colunas else 1,
                        row_span=int(linhas) if linhas else 1,
                        is_header=_local(celula) == "th",
                        html_attributes=_preservados(celula,
                                                     conhecidos=("colspan", "rowspan"))))
                filas.append(TableRow(
                    cells=tuple(celulas), height=_medida_de(fila.get("data-height")),
                    is_header=fila.get("data-header") == "1",
                    repeat_on_break=fila.get("data-repeat") == "1",
                    keep_together=fila.get("data-keep") == "1",
                    html_attributes=_preservados(fila, conhecidos=(
                        "data-height", "data-header", "data-repeat", "data-keep"))))
                if _local(grupo) == "thead":
                    cabeca += 1
                elif _local(grupo) == "tfoot":
                    rodape += 1
        alinhamento = elemento.get("data-alignment")
        numero = elemento.get("data-number")
        return Table(
            rows=tuple(filas), header_row_count=cabeca, footer_row_count=rodape,
            caption=tuple(self.inlines(legenda)) if legenda is not None else (),
            caption_above=elemento.get("data-caption-above") == "1",
            repeat_header=elemento.get("data-repeat-header") != "0",
            width=_medida_de(elemento.get("data-width")),
            alignment=Alignment(alinhamento) if alinhamento else None,
            number=int(numero) if numero is not None else None,
            summary=elemento.get("data-summary"), style=estilo,
            html_attributes=_preservados(
                elemento, conhecidos=(*usados, "data-caption-above", "data-repeat-header",
                                      "data-width", "data-alignment", "data-number",
                                      "data-summary"), classes_conhecidas=conhecidas), **kw)

    def _imagem(self, elemento: ET.Element, img: ET.Element) -> ImageBlock:
        kw, usados = self._identidade(elemento, ImageBlock)
        alinhamento = elemento.get("data-alignment")
        corte = _json_de(elemento.get("data-crop"), tuple[float, ...])
        return ImageBlock(resource=(img.get("src") or "").rpartition("/")[2],
                          alt_text=img.get("alt"), title=img.get("title"),
                          alignment=Alignment(alinhamento) if alinhamento else None,
                          crop=corte or (),
                          html_attributes=_preservados(
                              elemento, conhecidos=(*usados, "data-alignment", "data-crop"),
                              classes_conhecidas=("cb-image",)), **kw)

    def _figura(self, elemento: ET.Element) -> Figure:
        kw, usados = self._identidade(elemento, Figure)
        props, conhecidas = self._props_de_bloco(elemento)
        legenda = next((f for f in elemento if _local(f) == "figcaption"), None)
        rotulo = None
        texto: tuple[Any, ...] = ()
        for parte in (legenda if legenda is not None else []):
            if "cb-figure-label" in _classes(parte):
                rotulo = "".join(parte.itertext())
            elif "cb-caption-text" in _classes(parte):
                texto = tuple(self.inlines(parte))
        corpo = [f for f in elemento if f is not legenda]
        acima = (legenda is not None and bool(corpo) and list(elemento).index(legenda) == 0) or (
            elemento.get("data-caption-above") == "1")
        numero = elemento.get("data-number")
        lugar = elemento.get("data-placement")
        return Figure(content=tuple(self.blocos(elemento, ignorar=[legenda] if legenda is not None
                                                else [])),
                      caption=texto, label=rotulo,
                      number=int(numero) if numero is not None else None,
                      placement=FigurePlacement(lugar) if lugar else FigurePlacement.HERE,
                      caption_above=acima, alt_text=elemento.get("aria-label"), props=props,
                      html_attributes=_preservados(
                          elemento, conhecidos=(*usados, "data-number", "data-placement",
                                                "aria-label", "data-caption-above"),
                          classes_conhecidas=conhecidas), **kw)

    def _sumario(self, elemento: ET.Element) -> TableOfContents:
        kw, usados = self._identidade(elemento, TableOfContents)
        titulo = next((f for f in elemento if _local(f) == "h2"), None)
        return TableOfContents(
            title=tuple(self.inlines(titulo)) if titulo is not None else (),
            min_level=int(elemento.get("data-min-level") or 1),
            max_level=int(elemento.get("data-max-level") or 3),
            show_page_numbers=elemento.get("data-page-numbers") != "0",
            leader=elemento.get("data-leader") != "0",
            scope=elemento.get("data-scope") or "headings",
            html_attributes=_preservados(elemento, conhecidos=(
                *usados, "data-min-level", "data-max-level", "data-page-numbers", "data-leader",
                "data-scope"), classes_conhecidas=("cb-toc",)), **kw)

    def _destaque(self, elemento: ET.Element) -> Callout:
        kw, usados = self._identidade(elemento, Callout)
        props, conhecidas = self._props_de_bloco(elemento)
        titulo = next((f for f in elemento if "cb-callout-title" in _classes(f)), None)
        return Callout(kind=CalloutKind(elemento.get("data-kind") or "note"),
                       title=tuple(self.inlines(titulo)) if titulo is not None else (),
                       content=tuple(self.blocos(elemento, ignorar=[titulo] if titulo is not None
                                                 else [])),
                       collapsed=elemento.get("data-collapsed") == "1", props=props,
                       html_attributes=_preservados(
                           elemento, conhecidos=(*usados, "data-kind", "data-collapsed"),
                           classes_conhecidas=("cb-callout", *conhecidas)), **kw)

    def _formula(self, elemento: ET.Element) -> MathBlock:
        kw, usados = self._identidade(elemento, MathBlock)
        props, conhecidas = self._props_de_bloco(elemento)
        return MathBlock(latex="".join(elemento.itertext()),
                         mathml=elemento.get("data-mathml"),
                         display=elemento.get("display") != "inline",
                         numbered=elemento.get("data-numbered") == "1",
                         label=elemento.get("data-label"), props=props,
                         html_attributes=_preservados(
                             elemento, conhecidos=(*usados, "display", "data-numbered",
                                                   "data-label", "data-mathml"),
                             classes_conhecidas=conhecidas), **kw)

    def _grupo(self, elemento: ET.Element, *, capitulo: bool) -> Group:
        kw, usados = self._identidade(elemento, Group)
        props, conhecidas = self._props_de_bloco(elemento)
        titulo = next((f for f in elemento if "cb-group-title" in _classes(f)), None)
        papel = elemento.get("data-role")
        colunas = elemento.get("data-columns")
        return Group(role=GroupRole.CHAPTER if capitulo else GroupRole(papel or "generic"),
                     content=tuple(self.blocos(elemento, ignorar=[titulo] if titulo is not None
                                               else [])),
                     title=tuple(self.inlines(titulo)) if titulo is not None else (),
                     columns=int(colunas) if colunas is not None else None, props=props,
                     html_attributes=_preservados(
                         elemento, conhecidos=(*usados, "data-role", "data-columns"),
                         classes_conhecidas=(("cb-chapter",) if capitulo else ())
                         + tuple(conhecidas)), **kw)

    def _diagrama(self, elemento: ET.Element) -> Diagram:
        kw, usados = self._identidade(elemento, Diagram)
        img = next((f for f in elemento if _local(f) == "img"), None)
        legenda = next((f for f in elemento if _local(f) == "figcaption"), None)
        solucao = next((f for f in elemento if "cb-game" in _classes(f)), None)
        partes = {c: f for f in (legenda if legenda is not None else []) for c in _classes(f)}
        numero_attr = elemento.get("data-number")
        numero = int(numero_attr) if numero_attr is not None else None
        rotulo = None
        if "cb-diagram-label" in partes:
            rotulo = "".join(partes["cb-diagram-label"].itertext())
            literal = partes["cb-diagram-label"].get("data-literal") == "1"
            if numero is None and not literal and (casado := _ROTULO_NUMERADO.match(rotulo)):
                numero, rotulo = int(casado.group(1)), None
            elif not literal and numero is not None and rotulo == _ROTULO_AUTOMATICO.format(
                    numero):
                rotulo = None
        estipulacao, contexto = ("".join(partes[c].itertext()) if c in partes else None for c in (
            "cb-stipulation", "cb-move-context"))
        legenda_livre = tuple(self.inlines(partes["cb-caption-text"])) \
            if "cb-caption-text" in partes else ()
        fen = elemento.get("data-fen") or ""
        alt = img.get("alt") if img is not None else None
        if alt is not None and alt in _alts_gerados(fen, idioma=self.idioma, miniatura=False):
            alt = None
        estilo, conhecidas = _estilo_das_classes(_classes(elemento), self.estilo_do_slug,
                                                 do_contrato=False)
        return Diagram(
            fen=fen,
            orientation=Orientation.BLACK if elemento.get("data-orientation") == "black"
            else Orientation.WHITE,
            number=numero, label=rotulo, stipulation=estipulacao, move_context=contexto,
            caption=legenda_livre, marks=_marcas_de(elemento.get("data-marks")),
            side_to_move_indicator="cb-stm-marker" in partes, alt_text=alt,
            style=DiagramStyle(name=estilo) if estilo else DiagramStyle(),
            solution=_LeitorDePartida(self).partida(solucao) if solucao is not None else None,
            html_attributes=_preservados(
                elemento, conhecidos=(*usados, "data-fen", "data-stm", "data-mode",
                                      "data-orientation", "data-number", "data-marks"),
                classes_conhecidas=("cb-diagram", *conhecidas)), **kw)

    # -- dentro do parágrafo --------------------------------------------

    def inlines(self, elemento: ET.Element | None) -> list[Any]:
        if elemento is None:
            return []
        resultado: list[Any] = []
        self._texto_solto(elemento.text, resultado)
        for filho in elemento:
            resultado.extend(self._inline_ou_nada(filho))
            self._texto_solto(filho.tail, resultado)
        return resultado

    def _inline_ou_nada(self, elemento: ET.Element) -> list[Any]:
        no = self.inline(elemento)
        return [] if no is None else [no]

    @staticmethod
    def _texto_solto(texto: str | None, resultado: list[Any]) -> None:
        """O texto, com o espaço sem quebra, a tabulação e os espaços especiais como nós."""
        if not texto:
            return
        for pedaco in _ESPECIAIS.split(texto):
            if not pedaco:
                continue
            if pedaco == "\u00a0":
                resultado.append(NonBreakingSpace())
            elif pedaco == "\t":
                resultado.append(Tab())
            elif pedaco in _ESPACO_DO_CARACTERE:
                resultado.append(Space(kind=_ESPACO_DO_CARACTERE[pedaco]))
            elif resultado and isinstance(resultado[-1], Text) and _texto_nu(resultado[-1]):
                resultado[-1] = replace(resultado[-1],
                                        content=resultado[-1].content + pedaco)
            else:
                resultado.append(Text(content=pedaco))

    def _envoltorio(self, classe: type, elemento: ET.Element, *,
                    classes_conhecidas: Sequence[str] = ()) -> Any:
        props, estilos, lingua = self._props_de_corrida(elemento)
        return classe(content=tuple(self.inlines(elemento)), props=props,
                      html_attributes=_preservados(
                          elemento, conhecidos=lingua,
                          classes_conhecidas=(*classes_conhecidas, *estilos)))

    def inline(self, elemento: ET.Element) -> Any:
        """O nó do elemento de dentro do parágrafo; o que não volta igual fica bruto (R2.3)."""
        no = self._inline(elemento)
        if self.conferir and not isinstance(no, RawInline) and not self._confere(
                no, elemento, bloco=False):
            self.brutos.append(_descricao(elemento))
            return RawInline(format="xhtml", text=serializar_elemento(elemento))
        return no

    def _inline(self, elemento: ET.Element) -> Any:  # noqa: PLR0911, PLR0912 - um ramo por forma
        nome = _local(elemento)
        classes = _classes(elemento)
        simples = {"em": Emphasis, "strong": Strong, "u": Underline, "s": Strike,
                   "sup": Superscript, "sub": Subscript}
        if nome in simples:
            return self._envoltorio(simples[nome], elemento)
        if nome == "span" and "cb-smallcaps" in classes:
            return self._envoltorio(SmallCaps, elemento, classes_conhecidas=("cb-smallcaps",))
        if nome == "span" and "cb-piece" in classes:
            return self._peca(elemento)
        if nome == "span" and "cb-inline-diagram" in classes:
            return self._diagrama_no_texto(elemento)
        if nome == "span" and "cb-index-mark" in classes:
            return self._indice(elemento)
        if nome == "span" and "cb-move" in classes and elemento.get("data-san") is not None:
            return self._lance(elemento)
        if nome == "span" and "cb-nag" in classes and (elemento.get("data-nag") or "").isdigit():
            props, estilos, lingua = self._props_de_corrida(elemento)
            return NagSymbol(nag=int(elemento.get("data-nag") or 0), props=props,
                             html_attributes=_preservados(
                                 elemento, conhecidos=("data-nag", *lingua),
                                 classes_conhecidas=("cb-nag", *estilos)))
        if nome == "span" and "cb-raw" in classes:
            return RawInline(format=elemento.get("data-format") or "text",
                             text="".join(elemento.itertext()))
        if nome == "span" and "cb-link" in classes:
            return self._link(elemento, elemento.get("data-href") or "", "data-href")
        if (nome == "a" and "cb-noteref" in classes) or (nome == "span"
                                                          and "cb-noteref" in classes):
            return self._chamada(elemento, nome)
        if nome == "span" and elemento.get("id") and not len(elemento) and not elemento.text \
                and not any(c.startswith("cb-") for c in classes):
            return Anchor(name=elemento.get("id") or "", title=elemento.get("title"),
                          html_attributes=_preservados(elemento, conhecidos=("id", "title")))
        if nome == "span" and not any(c for c in classes if c.startswith("cb-") and not
                                      c.startswith("cb-style-")):
            return self._span(elemento)
        if nome == "a" and elemento.get("href") is not None:
            return self._link(elemento, elemento.get("href") or "", "href")
        if nome == "br":
            return LineBreak(html_attributes=_preservados(elemento))
        if nome == "img":
            return ImageInline(resource=(elemento.get("src") or "").rpartition("/")[2],
                               alt_text=elemento.get("alt"),
                               html_attributes=_preservados(elemento, conhecidos=("src", "alt")))
        if _formula_do_contrato(elemento):
            return MathInline(latex="".join(elemento.itertext()),
                              mathml=elemento.get("data-mathml"),
                              html_attributes=_preservados(elemento,
                                                           conhecidos=("data-mathml",)))
        return RawInline(format="xhtml", text=serializar_elemento(elemento))

    def _span(self, elemento: ET.Element) -> Any:
        """O `span` do texto.

        Com atributos e só texto dentro, é o `Text` com as props dele; senão, o `Span`.
        """
        props, estilos, lingua = self._props_de_corrida(elemento)
        html = _preservados(elemento, conhecidos=lingua, classes_conhecidas=estilos)
        portador = bool(elemento.attrib)
        if portador and not len(elemento) and elemento.text:
            return Text(content=elemento.text, props=props, html_attributes=html)
        return Span(content=tuple(self.inlines(elemento)), props=props, html_attributes=html)

    def _link(self, elemento: ET.Element, alvo: str, atributo_do_alvo: str) -> Link:
        props, estilos, lingua = self._props_de_corrida(elemento)
        tipo = elemento.get("data-kind")
        fora, self._dentro_de_link = self._dentro_de_link, True
        try:
            conteudo = tuple(self.inlines(elemento))
        finally:
            self._dentro_de_link = fora
        return Link(target=alvo, content=conteudo,
                    tooltip=elemento.get("title"), title=elemento.get("data-title"),
                    kind=LinkKind(tipo) if tipo else _tipo_do_link(alvo), props=props,
                    html_attributes=_preservados(
                        elemento, conhecidos=(atributo_do_alvo, "title", "data-title",
                                              "data-kind", *lingua),
                        classes_conhecidas=("cb-link", *estilos)))

    def _chamada(self, elemento: ET.Element, nome: str) -> NoteRef:
        props, estilos, lingua = self._props_de_corrida(elemento)
        alvo = elemento.get("href" if nome == "a" else "data-href") or ""
        texto = "".join(elemento.itertext())
        marcador = texto if texto else ("" if elemento.get("data-marker") == "" else None)
        return NoteRef(ref=alvo.removeprefix("#"), marker=marcador, props=props,
                       html_attributes=_preservados(
                           elemento, conhecidos=("href", "data-href", "epub:type", "role",
                                                 "data-marker", *lingua),
                           classes_conhecidas=("cb-noteref", *estilos)))

    def _peca(self, elemento: ET.Element) -> PieceGlyph:
        from caissa.export.text import figurine_char

        props, estilos, lingua = self._props_de_corrida(elemento)
        letra = elemento.get("data-piece") or "N"
        visivel = "".join(elemento.itertext())
        conjunto = FigurineSet.WHITE if visivel == figurine_char(letra, FigurineSet.WHITE) \
            else FigurineSet.BLACK
        return PieceGlyph(piece=_PECA_DA_LETRA.get(letra, PieceType.KNIGHT),
                          figurine_set=conjunto, font_family=elemento.get("data-font-family"),
                          props=props, html_attributes=_preservados(
                              elemento, conhecidos=("data-piece", "data-font-family", *lingua),
                              classes_conhecidas=("cb-piece", *estilos)))

    def _diagrama_no_texto(self, elemento: ET.Element) -> InlineDiagram:
        img = next((f for f in elemento if _local(f) == "img"), None)
        fen = elemento.get("data-fen") or ""
        alt = img.get("alt") if img is not None else None
        if alt is not None and alt in _alts_gerados(fen, idioma=self.idioma, miniatura=True):
            alt = None
        estilo, conhecidas = _estilo_das_classes(_classes(elemento), self.estilo_do_slug,
                                                 do_contrato=False)
        return InlineDiagram(
            fen=fen,
            orientation=Orientation.BLACK if elemento.get("data-orientation") == "black"
            else Orientation.WHITE,
            size=_medida_de(elemento.get("data-size")),
            marks=_marcas_de(elemento.get("data-marks")), style=estilo, alt_text=alt,
            html_attributes=_preservados(elemento, conhecidos=(
                "data-fen", "data-orientation", "data-size", "data-marks"),
                classes_conhecidas=("cb-inline-diagram", *conhecidas)))

    def _indice(self, elemento: ET.Element) -> IndexEntry:
        termos = tuple(t for t in (elemento.get("data-term") or "").split("|") if t)
        veja = elemento.get("data-see-also")
        return IndexEntry(terms=termos, sort_key=elemento.get("data-sort-key"),
                          see_also=tuple(veja.split("|")) if veja else (),
                          primary=elemento.get("data-primary") == "1",
                          html_attributes=_preservados(elemento, conhecidos=(
                              "data-term", "data-sort-key", "data-see-also", "data-primary"),
                              classes_conhecidas=("cb-index-mark",)))

    def _lance(self, elemento: ET.Element) -> Move:
        props, estilos, lingua = self._props_de_corrida(elemento)
        antes = elemento.get("data-fen-before") or ""
        ply = elemento.get("data-ply")
        derivado = _meio_lance_da_fen(antes) if antes else None
        mostra = False
        pecas: list[tuple[str, str]] = []
        nags = []
        for filho in elemento:
            classe = _classes(filho)
            if "cb-movenum" in classe:
                mostra = True
            elif "cb-piece" in classe:
                pecas.append((filho.get("data-piece") or "N", "".join(filho.itertext())))
            elif "cb-nag" in classe:
                nags.append(int(filho.get("data-nag") or 0))
        padrao = (MoveRenderStyle.LETTERS, "en", FigurineSet.BLACK)
        render, lingua_da_notacao, conjunto = _notacao_lida(elemento, pecas, self.idioma, padrao)
        return Move(san=elemento.get("data-san") or "", uci=elemento.get("data-uci"),
                    position_before=antes,
                    ply=int(ply) if ply is not None else (derivado or 0),
                    nags=tuple(nags), render=render, language=lingua_da_notacao,
                    figurine_set=conjunto, show_move_number=mostra,
                    move_number_text=elemento.get("data-number-text"), props=props,
                    html_attributes=_preservados(
                        elemento, conhecidos=(
                            "data-san", "data-uci", "data-fen", "data-fen-before", "data-ply",
                            "data-number-text", "data-render", "data-language",
                            "data-figurine-set", *lingua),
                        classes_conhecidas=("cb-move", *estilos)))


def _descricao(elemento: ET.Element) -> str:
    """`etiqueta.classe.classe` do elemento, para o registro do que ficou bruto."""
    return ".".join([_nome(elemento.tag), *_classes(elemento)])


_ID_DE_PAGINA = re.compile(r"^p[1-9]\d*-[dg]?[1-9]\d*$")


def _canon_de_fragmento(texto: str) -> str:
    """O `canon` de um trecho sem declarações, sem os `id` que o escritor gera pela página."""
    envelope = (f'<r xmlns="{XHTML}" xmlns:epub="{EPUB}" xmlns:svg="{SVG}" '
                f'xmlns:m="{MATHML}">{texto}</r>')
    raiz = ET.fromstring(envelope.encode("utf-8"))  # noqa: S314 - o texto do próprio escritor
    for elemento in raiz.iter():
        if _ID_DE_PAGINA.match(elemento.get("id") or ""):
            del elemento.attrib["id"]
    _normalizar(raiz)
    return _serializar(raiz, ordenar=True)


def _entrada_normalizada(elemento: ET.Element, idioma: str) -> ET.Element:
    """O elemento com o que o contrato diz derivado recalculado (§6.1), para a conferência.

    O `data-mode` e o `data-orientation` ausentes são os padrões; o `data-stm` ausente sai da
    FEN; o `src` da imagem do diagrama e a fala do marcador do lado que joga são derivados, e
    o leitor não os lê.
    """
    import copy

    copia = copy.deepcopy(elemento)
    for figura in copia.iter():
        classes = _classes(figura)
        if "cb-diagram" not in classes and "cb-inline-diagram" not in classes:
            continue
        fen = figura.get("data-fen") or ""
        campos = fen.split()
        lado = campos[1] if len(campos) > 1 and campos[1] in ("w", "b") else "w"
        if "cb-diagram" in classes:
            figura.attrib.setdefault("data-mode", "svg")
            figura.attrib.setdefault("data-stm", lado)
        figura.attrib.setdefault("data-orientation", "white")
        orientacao = "black" if figura.get("data-orientation") == "black" else "white"
        for parte in figura.iter():
            if "cb-svg" in _classes(parte):
                parte.set("src", f"../Images/{_imagem_do_diagrama(fen, orientacao)}")
            elif "cb-stm-marker" in _classes(parte):
                falado = ({"w": "White to move", "b": "Black to move"} if idioma.startswith("en")
                          else {"w": "Brancas jogam", "b": "Pretas jogam"})
                parte.set("aria-label", falado[lado])
    return copia


def _formula_do_contrato(elemento: ET.Element) -> bool:
    """O `math` que o escritor escreve: uma `annotation` do TeX e nada mais.

    O MathML que a pessoa escreve (`mi`, `mo`, `mfrac`...) não é o `latex` do IR: fica como
    bruto, preservado (R2.3), em vez de virar o texto dele.
    """
    if _nome(elemento.tag) != "m:math" or (elemento.text or "").strip() or len(elemento) != 1:
        return False
    anotacao = elemento[0]
    return (_nome(anotacao.tag) == "m:annotation"
            and anotacao.get("encoding") == "application/x-tex" and not len(anotacao)
            and not (anotacao.tail or "").strip())


def _texto_nu(no: Any) -> bool:
    """O `Text` sem nada além do conteúdo: o que a árvore XML guarda como texto solto."""
    return (isinstance(no, Text) and no.props == RunProps() and not no.html_attributes
            and no.provenance is None)


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
        kw, usados = self.leitor._identidade(secao, GameScore)
        inicial = secao.get("data-initial-fen")
        cabecalho = next((f for f in secao if "cb-game-header" in _classes(f)), None)
        cabecalhos, anotador = self._cabecalho(cabecalho)
        titulo = next((f for f in secao if "cb-game-title" in _classes(f)), None)
        impresso = next((f for f in secao if "cb-result" in _classes(f)), None)
        resultado = (secao.get("data-result")
                     or ("".join(impresso.itertext()).strip() if impresso is not None else "")
                     or ("" if secao.get("data-result-empty") == "1" else "*"))
        try:
            tabuleiro = chess.Board(inicial) if inicial else chess.Board()
        except ValueError:
            tabuleiro = None
        try:
            filhos, comentario_inicial, pecas = self._lances(movimentos, tabuleiro)
            padrao = (GameRenderOptions().render, GameRenderOptions().language,
                      GameRenderOptions().figurine_set)
            render, lingua, conjunto = _notacao_lida(secao, pecas, self.leitor.idioma, padrao)
        except (ValueError, KeyError, IndexError):
            return RawPassthrough(format="xhtml", text=serializar_elemento(secao))
        conhecido = resultado not in ("", "*")
        profundidade = secao.get("data-max-variation-depth")
        estilo_das_variantes = secao.get("data-variation-style")
        opcoes = GameRenderOptions(
            language=lingua, render=render, figurine_set=conjunto,
            variation_style=VariationStyle(estilo_das_variantes) if estilo_das_variantes
            else VariationStyle.INLINE,
            show_result=(impresso is not None) if conhecido
            else secao.get("data-show-result") != "0",
            show_headers=cabecalho is None or cabecalho.get("hidden") is None,
            max_variation_depth=int(profundidade) if profundidade is not None else None)
        conhecidos = ("data-eco", "data-result", "data-result-empty", "data-initial-fen",
                      "data-variant", "data-show-result", "data-variation-style",
                      "data-max-variation-depth", "data-render", "data-language",
                      "data-figurine-set")
        return GameScore(
            headers=replace(cabecalhos, result=resultado),
            initial_fen=inicial, initial_comment=comentario_inicial, children=filhos,
            variant=secao.get("data-variant") or "standard", render=opcoes,
            title="".join(titulo.itertext()) if titulo is not None else None,
            annotator=anotador,
            html_attributes=_preservados(secao, conhecidos=(*usados, *conhecidos),
                                         classes_conhecidas=("cb-game", "cb-solution")),
            **kw)

    @staticmethod
    def _cabecalho(  # noqa: PLR0912 - um ramo por linha do cabeçalho do MARKUP
            cabecalho: ET.Element | None) -> tuple[GameHeaders, str | None]:
        campos: dict[str, str] = {}
        tags: list[PgnTag] = []
        conhecidas: dict[str, str] = {}
        anotador = None
        if cabecalho is None:
            return GameHeaders(), anotador
        for linha in cabecalho:
            classes = _classes(linha)
            texto = "".join(linha.itertext())
            if "cb-game-number" in classes:
                conhecidas["GameNumber"] = texto
            elif "cb-player" in classes:
                cor = "white" if "cb-white" in classes else "black"
                for parte in linha:
                    valor = "".join(parte.itertext())
                    if "cb-name" in _classes(parte):
                        campos[cor] = valor
                    elif "cb-elo" in _classes(parte):
                        conhecidas["WhiteElo" if cor == "white" else "BlackElo"] = valor
            elif "cb-event" in classes:
                for parte in linha:
                    valor = "".join(parte.itertext())
                    classe = _classes(parte)
                    if "cb-event-name" in classe:
                        campos["event"] = valor
                    elif "cb-site" in classe:
                        campos["site"] = valor
                    elif "cb-round" in classe:
                        campos["round"] = valor[1:-1] if valor.startswith("(") and \
                            valor.endswith(")") else valor
                    elif "cb-date" in classe:
                        campos["date"] = valor
            elif "cb-opening" in classes:
                for parte in linha:
                    valor = "".join(parte.itertext())
                    if "cb-opening-name" in _classes(parte):
                        conhecidas["Opening"] = valor
                    elif "cb-eco" in _classes(parte):
                        conhecidas["ECO"] = valor
            elif "cb-annotator" in classes:
                anotador = texto
            elif "cb-tag" in classes:
                tags.append(PgnTag(name=linha.get("data-name") or "", value=texto))
        extras = [PgnTag(name=n, value=conhecidas[n]) for n in _TAGS_DO_CABECALHO
                  if n in conhecidas] + tags
        ordem = cabecalho.get("data-tag-order")
        if ordem:
            por_nome: dict[str, list[PgnTag]] = {}
            for tag in extras:
                por_nome.setdefault(tag.name, []).append(tag)
            extras = [por_nome[n].pop(0) for n in ordem.split() if por_nome.get(n)]
        return GameHeaders(**campos, extra=tuple(extras)), anotador

    def _lances(  # noqa: PLR0912 - um ramo por forma de parágrafo e de lance
            self, movimentos: ET.Element, tabuleiro: Any
            ) -> tuple[tuple[MoveNode, ...], str, list[tuple[str, str]]]:
        """As linhas de lances de volta à árvore.

        O lance com `data-fen` entra como **continuação** da linha da profundidade dele quando é
        legal ali e dá aquela FEN; senão, como **variante**: irmã do último lance da linha de
        cima, jogada da posição de antes dele. O lance literal (sem `data-fen`) entra pela forma
        do texto (o `data-variation-start` marca o começo da variante). O comentário fica no
        lance anterior (ou é o comentário inicial da partida); o `data-attach="before"` o põe
        antes do lance seguinte.
        """
        raiz: list[dict[str, Any]] = []
        comentario_inicial = ""
        pecas: list[tuple[str, str]] = []
        estado: dict[int, dict[str, Any]] = {}
        ultimo: dict[str, Any] | None = None
        pendente: str | None = None
        anterior: tuple[int, bool] | None = None
        """A profundidade do parágrafo de lances anterior, e se um comentário veio depois dele."""
        for paragrafo in movimentos:
            classes = _classes(paragrafo)
            if "cb-comment" in classes:
                comentario = "".join(paragrafo.itertext())
                if paragrafo.get("data-attach") == "before":
                    pendente = comentario
                elif ultimo is None:
                    comentario_inicial = comentario
                else:
                    ultimo["depois"] = comentario
                if anterior is not None:
                    anterior = (anterior[0], True)
                continue
            if "cb-line" not in classes:
                raise ValueError(f"parágrafo fora do contrato na partida: {classes}")
            profundidade = next((int(c.removeprefix("cb-depth-")) for c in classes
                                 if c.startswith("cb-depth-")), 0)
            inicio = paragrafo.get("data-variation-start") == "1"
            primeiro = True
            for filho in paragrafo:
                classe = _classes(filho)
                if "cb-nag" in classe and ultimo is not None:
                    ultimo["nags"].append(int(filho.get("data-nag") or 0))
                    continue
                if "cb-move" not in classe:
                    continue
                peca = next((p for p in filho if "cb-piece" in _classes(p)), None)
                if filho.get("data-fen"):
                    if peca is not None:
                        pecas.append((peca.get("data-piece") or "N", "".join(peca.itertext())))
                    registro = self._colocar(filho.get("data-uci"), filho.get("data-fen") or "",
                                             profundidade, estado, raiz, tabuleiro)
                else:
                    registro = self._colocar_sem_posicao(
                        filho.get("data-san") or "".join(filho.itertext()), profundidade,
                        estado, raiz, tabuleiro, primeiro=primeiro, anterior=anterior,
                        inicio_de_variante=inicio and primeiro)
                self._campos_do_lance(filho, registro)
                if pendente is not None:
                    registro["antes_comentario"] = pendente
                    pendente = None
                ultimo = registro
                primeiro = False
            anterior = (profundidade, False)
        return tuple(_no(r) for r in raiz), comentario_inicial, pecas

    @staticmethod
    def _campos_do_lance(filho: ET.Element, registro: dict[str, Any]) -> None:
        """O que os `data-*` do lance dizem além do tabuleiro, no registro dele."""
        for atributo, chave in (("data-san", "san"), ("data-fen-before", "antes"),
                                ("data-fen-after", "depois_fen")):
            if filho.get(atributo) is not None:
                registro[chave] = filho.get(atributo)
        if filho.get("data-ply") is not None:
            registro["ply"] = int(filho.get("data-ply") or 0)
        registro["uci"] = filho.get("data-uci")
        registro["emphasis"] = filho.get("data-emphasis") == "1"
        if filho.get("data-clock") is not None:
            segundos = filho.get("data-clock-seconds")
            registro["clock"] = ClockAnnotation(
                kind=ClockKind(filho.get("data-clock-kind") or "clk"),
                text=filho.get("data-clock") or "",
                seconds=float(segundos) if segundos is not None else None)
        if filho.get("data-eval") is not None:
            profundidade = filho.get("data-eval-depth")
            registro["evaluation"] = EvalAnnotation(
                kind=EvalKind(filho.get("data-eval-kind") or EvalKind.CENTIPAWNS.value),
                value=float(filho.get("data-eval-value") or 0.0),
                depth=int(profundidade) if profundidade is not None else None,
                text=filho.get("data-eval") or "")
        registro["arrows"] = _marcas_de(filho.get("data-arrows"))
        registro["highlights"] = _marcas_de(filho.get("data-highlights"))
        registro["html"] = _preservados(filho, conhecidos=(
            "data-san", "data-uci", "data-fen", "data-fen-before", "data-fen-after", "data-ply",
            "data-emphasis", "data-clock", "data-clock-kind", "data-clock-seconds", "data-eval",
            "data-eval-kind", "data-eval-value", "data-eval-depth", "data-arrows",
            "data-highlights"), classes_conhecidas=("cb-move",))

    @staticmethod
    def _colocar(uci: str | None, fen: str, profundidade: int,
                 estado: dict[int, dict[str, Any]], raiz: list[dict[str, Any]],
                 inicio: Any) -> dict[str, Any]:
        """Põe o lance na árvore: continuação da linha, ou variante do lance de cima."""
        import chess

        def jogar(tabuleiro: Any) -> tuple[Any, Any] | None:
            if tabuleiro is None:
                return None
            candidatos = ([chess.Move.from_uci(uci)] if uci else list(tabuleiro.legal_moves))
            for movimento in candidatos:
                if movimento not in tabuleiro.legal_moves:
                    continue
                depois = tabuleiro.copy()
                depois.push(movimento)
                if depois.fen() == fen:
                    return movimento, depois
            return None

        linha = estado.get(profundidade)
        onde: list[dict[str, Any]] | None = None
        antes = achado = None
        if linha is not None and (achado := jogar(linha["depois"])) is not None:
            antes, onde = linha["depois"], linha["registro"]["filhos"]
        elif profundidade == 0 and not raiz and (achado := jogar(inicio)) is not None:
            antes, onde = inicio, raiz
        elif profundidade > 0 and (de_cima := estado.get(profundidade - 1)) is not None and (
                achado := jogar(de_cima["antes"])) is not None:
            antes, onde = de_cima["antes"], de_cima["lista"]
        if onde is None or antes is None or achado is None:
            raise ValueError(f"o lance que leva a {fen} não cabe na partida")
        movimento, depois = achado
        registro = _registro(san=antes.san(movimento), antes=antes.fen(),
                             depois_fen=depois.fen(),
                             ply=(antes.fullmove_number - 1) * 2 + (1 if antes.turn else 2))
        onde.append(registro)
        estado[profundidade] = {"registro": registro, "lista": onde, "antes": antes,
                                "depois": depois}
        for mais_funda in [d for d in estado if d > profundidade]:
            del estado[mais_funda]
        return registro

    @staticmethod
    def _colocar_sem_posicao(san: str, profundidade: int,
                             estado: dict[int, dict[str, Any]], raiz: list[dict[str, Any]],
                             inicio: Any, *, primeiro: bool, anterior: tuple[int, bool] | None,
                             inicio_de_variante: bool) -> dict[str, Any]:
        """O lance que não se joga (só `data-san`): entra pela forma do texto, não pela posição.

        No meio do parágrafo, é a continuação. O primeiro de um parágrafo abre uma variante irmã
        do último lance da linha de cima quando o parágrafo diz `data-variation-start`; senão,
        continua a linha da profundidade dele quando volta de uma variante mais funda ou quando um
        comentário a quebrou (e, sem nada disso, abre a variante). A posição de antes dele fica
        guardada quando se sabe: uma variante dele começa dali, e o escritor a joga dali.
        """
        linha = estado.get(profundidade)
        de_cima = estado.get(profundidade - 1) if profundidade > 0 else None
        if not primeiro or profundidade == 0:
            continua = linha is not None
        elif inicio_de_variante:
            continua = False
        else:
            continua = linha is not None and anterior is not None and (
                anterior[0] > profundidade or (anterior[0] == profundidade and anterior[1]))
        if continua and linha is not None:
            onde, meio_lance = linha["registro"]["filhos"], linha["registro"]["ply"] + 1
            antes = linha["depois"]
        elif profundidade == 0 and not raiz:
            onde, meio_lance, antes = raiz, 1, inicio
        elif de_cima is not None:
            onde, meio_lance = de_cima["lista"], de_cima["registro"]["ply"]
            antes = de_cima["antes"]
        else:
            raise ValueError(f"o lance {san} não cabe na partida")
        registro = _registro(san=san, antes="", depois_fen="", ply=meio_lance)
        onde.append(registro)
        estado[profundidade] = {"registro": registro, "lista": onde, "antes": antes,
                                "depois": None}
        for mais_funda in [d for d in estado if d > profundidade]:
            del estado[mais_funda]
        return registro


def _registro(*, san: str, antes: str, depois_fen: str, ply: int) -> dict[str, Any]:
    return {"uci": None, "san": san, "antes": antes, "depois_fen": depois_fen, "nags": [],
            "depois": "", "antes_comentario": "", "filhos": [], "ply": ply, "emphasis": False,
            "clock": None, "evaluation": None, "arrows": (), "highlights": (), "html": ()}


def _no(registro: dict[str, Any]) -> MoveNode:
    return MoveNode(
        san=registro["san"], ply=registro["ply"], position_before=registro["antes"],
        position_after=registro["depois_fen"], uci=registro["uci"],
        nags=tuple(registro["nags"]), comment_before=registro["antes_comentario"],
        comment_after=registro["depois"], emphasis=registro["emphasis"],
        clock=registro["clock"], evaluation=registro["evaluation"],
        arrows=registro["arrows"], highlights=registro["highlights"],
        html_attributes=registro["html"],
        children=tuple(_no(f) for f in registro["filhos"]))


# --------------------------------------------------------------------------- #
# A forma normal: as normalizações declaradas N1–N4, contadas
# --------------------------------------------------------------------------- #


class _FormaNormal:
    """O IR como o perfil legível o devolve, pelas quatro normalizações do contrato (§8).

    - **N1** — as `RunProps` de família e de corpo do texto que o OCR leu não viram marcação.
    - **N2** — a formatação direta que o perfil de máquina escreve nas classes geradas
      `.pN/.rN/.dN` não existe no legível: as `ParagraphProps` além do estilo nomeado, as
      `RunProps` além do estilo e da língua, as bordas, o recuo e o fundo das células e dos
      destaques, as colunas e as bordas da tabela, o traço da linha horizontal, o tamanho das
      imagens e o estilo direto do diagrama (fica o nome dele).
    - **N3** — a proveniência que não tem `id` de bloco para voltar (a do texto, a do lance, a
      da célula) vai ao `proveniencia.json`, e não à marcação; o `Span` que só a carrega sai.
    - **N4** — a árvore XML: o texto solto sem nós vazios nem vizinhos, os espaços especiais
      como nós, o `Span` com atributos e só texto dentro como o `Text` com as props dele, os
      atributos preservados na ordem do `canon`, o bruto `xhtml` na serialização do leitor.
    """

    def __init__(self) -> None:
        self.contagem: Counter[str] = Counter()

    def conta(self, classe: str, no: Any, campo: str = "") -> None:
        self.contagem[f"{classe}:{tag_of(no)}{'.' + campo if campo else ''}"] += 1

    def no(self, no: Any, herdada: Any) -> list[Any]:
        propria = getattr(no, "provenance", None)
        herdada = propria if propria is not None else herdada
        if isinstance(no, Span) and _span_so_de_proveniencia(no):
            self.conta("N3", no)
            return self.inlines(no.content, herdada)
        mudancas: dict[str, Any] = {}
        for campo in fields(no):
            valor = getattr(no, campo.name)
            if isinstance(valor, IRNode):
                novos = self.no(valor, herdada)
                mudancas[campo.name] = novos[0]
            elif isinstance(valor, tuple) and valor and all(isinstance(x, IRNode) for x in valor):
                if all(isinstance(x, INLINES) for x in valor):
                    mudancas[campo.name] = tuple(self.inlines(valor, herdada))
                else:
                    mudancas[campo.name] = tuple(y for x in valor for y in self.no(x, herdada))
        if mudancas:
            no = replace(no, **mudancas)
        no = self._n1_n2(no, herdada)
        no = self._n3(no)
        return [self._n4(no)]

    def inlines(self, itens: Iterable[Any], herdada: Any) -> list[Any]:
        """A sequência de dentro do parágrafo, depois de cada nó dela, na forma da árvore XML."""
        saida: list[Any] = []
        for item in itens:
            for novo in self.no(item, herdada):
                if isinstance(novo, Text) and not novo.content:
                    self.conta("N4", novo, "vazio")
                    continue
                pedacos = [novo]
                if _texto_nu(novo):
                    pedacos = []
                    _Leitor._texto_solto(novo.content, pedacos)
                    if len(pedacos) > 1:
                        self.conta("N4", novo, "espacos")
                for pedaco in pedacos:
                    if saida and _texto_nu(pedaco) and _texto_nu(saida[-1]):
                        saida[-1] = replace(saida[-1], content=saida[-1].content + pedaco.content)
                        self.conta("N4", pedaco, "vizinhos")
                    else:
                        saida.append(pedaco)
        return saida

    def _n1_n2(self, no: Any, herdada: Any) -> Any:  # noqa: PLR0912 - um ramo por família da N2
        mudancas: dict[str, Any] = {}
        props = getattr(no, "props", None)
        if isinstance(props, ParagraphProps) and props != ParagraphProps(style=props.style):
            mudancas["props"] = ParagraphProps(style=props.style)
            self.conta("N2", no, "props")
        if isinstance(props, RunProps):
            alvo = RunProps() if isinstance(no, MathInline) else RunProps(
                style=props.style, language=props.language)
            if props != alvo:
                digitalizado = herdada is not None and herdada.kind in _DIGITALIZADO
                resto = props
                if digitalizado and (props.font_family or props.font_size):
                    self.conta("N1", no, "props")
                    resto = replace(props, font_family=None, font_size=None, font_fallbacks=())
                if resto != alvo:
                    self.conta("N2", no, "props")
                mudancas["props"] = alvo
        for campo in ("run_props",):
            valor = getattr(no, campo, None)
            if isinstance(valor, RunProps) and valor != RunProps():
                mudancas[campo] = RunProps()
                self.conta("N2", no, campo)
        nulos: dict[type, tuple[str, ...]] = {
            TableCell: ("alignment", "vertical_alignment", "borders", "padding", "shading"),
            Callout: ("borders", "padding", "shading"), Table: ("borders", "cell_padding"),
            ThematicBreak: ("rule",), ImageBlock: ("width", "height"),
            ImageInline: ("width", "height", "baseline_shift")}
        for tipo, campos in nulos.items():
            if isinstance(no, tipo):
                for campo in campos:
                    if getattr(no, campo) is not None:
                        mudancas[campo] = None
                        self.conta("N2", no, campo)
        if isinstance(no, Table) and no.columns:
            mudancas["columns"] = ()
            self.conta("N2", no, "columns")
        if isinstance(no, Diagram) and no.style != DiagramStyle(name=no.style.name):
            mudancas["style"] = DiagramStyle(name=no.style.name)
            self.conta("N2", no, "style")
        if isinstance(no, GameScore):
            render = no.render
            limpo = replace(render, move_props=RunProps(), comment_props=RunProps(),
                            variation_props=RunProps())
            if limpo != render:
                mudancas["render"] = limpo
                self.conta("N2", no, "render")
        return replace(no, **mudancas) if mudancas else no

    def _n3(self, no: Any) -> Any:
        if _chaveado(no):
            return no
        mudancas: dict[str, Any] = {}
        if getattr(no, "provenance", None) is not None:
            mudancas["provenance"] = None
            self.conta("N3", no, "provenance")
        if isinstance(no, Diagram):
            padrao = Diagram(fen="")
            for campo in ("recognition", "source", "verified_by_human"):
                if getattr(no, campo) != getattr(padrao, campo):
                    mudancas[campo] = getattr(padrao, campo)
                    self.conta("N3", no, campo)
        return replace(no, **mudancas) if mudancas else no

    def _n4(self, no: Any) -> Any:
        mudancas: dict[str, Any] = {}
        ordenados = tuple(sorted(no.html_attributes))
        if ordenados != no.html_attributes:
            mudancas["html_attributes"] = ordenados
            self.conta("N4", no, "html_attributes")
        if isinstance(no, RawPassthrough | RawInline) and no.format == "xhtml" and _bruto_fica(
                no.text, bloco=isinstance(no, RawPassthrough)):
            elemento = _fragmento(no.text)
            texto = serializar_elemento(elemento) if elemento is not None else no.text
            if texto != no.text:
                mudancas["text"] = texto
                self.conta("N4", no, "text")
        if mudancas:
            no = replace(no, **mudancas)
        if isinstance(no, Span) and (no.props != RunProps() or no.html_attributes) and \
                no.content and all(_texto_nu(x) or isinstance(x, NonBreakingSpace | Tab | Space)
                                   for x in no.content):
            self.conta("N4", no, "texto")
            conteudo = "".join(x.content if isinstance(x, Text) else
                               "\u00a0" if isinstance(x, NonBreakingSpace) else
                               "\t" if isinstance(x, Tab) else ESPACOS.get(x.kind, " ")
                               for x in no.content)
            return Text(id=no.id, content=conteudo, props=no.props,
                        html_attributes=no.html_attributes)
        return no


def forma_normal(blocos: Iterable[Any]) -> tuple[tuple[Any, ...], Counter[str]]:
    """Os blocos depois das normalizações declaradas N1–N4 (o contrato, §8), e a contagem.

    É o que ``ler_capitulo(escrever_capitulo(...), mapa=...)`` devolve de um IR: a ida do portão
    do H5 compara os dois com o `semantic_diff`, e qualquer diferença fora daqui reprova.
    """
    normal = _FormaNormal()
    novos = tuple(n for bloco in blocos for n in normal.no(bloco, None))
    return novos, normal.contagem


def folhas_do_livro(documento: Document) -> list[tuple[str, bytes]]:
    """As folhas do projeto, na ordem do documento, byte a byte (spec R2.2b).

    O CSS é recurso, e não semântica do IR (spec D1): o EPUB e o HTML levam cada
    `Resource(kind=STYLESHEET)` como ela está no disco, com o nome do arquivo. A folha que não
    está no disco é um erro, e não uma folha a menos (R2.3).

    Raises:
        FileNotFoundError: Uma folha do documento não está no caminho dela.
    """
    folhas = []
    for recurso in documento.resources:
        if recurso.kind is not ResourceKind.STYLESHEET:
            continue
        caminho = Path(recurso.path) if recurso.path else None
        if caminho is None or not caminho.is_file():
            raise FileNotFoundError(f"a folha {recurso.key} não está em {recurso.path!r}")
        folhas.append((caminho.name, caminho.read_bytes()))
    return folhas


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
        blocos.append(leitor.bloco(filho))
    return Capitulo(blocos=tuple(blocos), titulo=titulo, folhas=tuple(folhas), idioma=idioma,
                    brutos=tuple(leitor.brutos))


def escrever_capitulo(capitulo: Capitulo, documento: Document | None = None, *,
                      folios: Mapping[int, str] | None = None) -> tuple[str, EscritorLegivel]:
    """O capítulo em XHTML legível, e o escritor (com o mapa da proveniência e as imagens)."""
    escritor = EscritorLegivel(documento, folios=folios)
    escritor.idioma = capitulo.idioma or escritor.idioma
    return escritor.capitulo(capitulo), escritor


_ = (Block,)
