"""A camada XML (spec S10): o arquivo é XML bem formado — e a árvore, com linha e coluna.

O `expat` lê o arquivo uma vez e dá:

- o erro de boa formação, com a linha e a coluna dele;
- a árvore: cada elemento com a posição da etiqueta de abertura (o `<`), e cada trecho de texto
  com a do primeiro caractere — as outras camadas acusam por ela, sem reler o arquivo;
- o que a R4.3 recusa no próprio documento: o arquivo além de 8 MB, o `DOCTYPE` com entidades
  (a declaração interrompe a leitura: nenhuma entidade é expandida, a externa nunca é resolvida)
  e o aninhamento além de 256.

A árvore é percorrida sem recursão (o aninhamento patológico não derruba a validação).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from xml.parsers import expat

from caissa.editor.validacao.problema import Local, Problema, Severidade, regra

__all__ = [
    "EPUB_TYPE",
    "LIMITE_DE_ANINHAMENTO",
    "LIMITE_DE_BYTES",
    "SVG",
    "XHTML",
    "XLINK_HREF",
    "XML_LANG",
    "Documento",
    "Elemento",
    "Trecho",
    "ler",
]

XHTML = "http://www.w3.org/1999/xhtml"
SVG = "http://www.w3.org/2000/svg"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
LIMITE_DE_BYTES = 8 * 1024 * 1024
LIMITE_DE_ANINHAMENTO = 256

MAL_FORMADO = regra(
    "xml-mal-formado", "xml", Severidade.BLOQUEIA, "O arquivo não é XML bem formado",
    "Corrija a marcação no ponto indicado; o leitor de EPUB recusa o capítulo inteiro.")
TAMANHO = regra(
    "seg-tamanho", "segurança", Severidade.BLOQUEIA, "O arquivo passa de 8 MB (R4.3)",
    "Divida o capítulo em arquivos menores.")
ANINHAMENTO = regra(
    "seg-aninhamento", "segurança", Severidade.BLOQUEIA,
    "Elementos aninhados além de 256 níveis (R4.3)",
    "Achate a estrutura: nenhum livro precisa de tanta profundidade.")
ENTIDADE_INTERNA = regra(
    "seg-doctype-entidade", "segurança", Severidade.BLOQUEIA,
    "O DOCTYPE declara entidades (R4.3)",
    "Tire as declarações do DOCTYPE e escreva os caracteres no texto (UTF-8).")
ENTIDADE_EXTERNA = regra(
    "seg-entidade-externa", "segurança", Severidade.BLOQUEIA,
    "O DOCTYPE declara uma entidade externa, que nunca é resolvida (R4.3)",
    "Tire a declaração: o arquivo não pode puxar nada de fora dele.")


class _Recusado(Exception):  # noqa: N818 - a leitura interrompida de propósito, não um erro
    """A leitura para no DOCTYPE com entidade: nada é expandido nem resolvido."""


@dataclass(eq=False, slots=True)
class Trecho:
    """Um trecho de texto, com a posição do primeiro caractere."""

    texto: str
    linha: int
    coluna: int
    pai: Elemento

    def posicao(self, deslocamento: int) -> tuple[int, int]:
        """A linha e a coluna do caractere `texto[deslocamento]`."""
        antes = self.texto[:deslocamento]
        quebras = antes.count("\n")
        if not quebras:
            return self.linha, self.coluna + deslocamento
        return self.linha + quebras, deslocamento - antes.rfind("\n")


@dataclass(eq=False, slots=True)
class Elemento:
    """Um elemento: o nome local, o espaço de nomes, os atributos e a posição do `<`.

    Os atributos sem espaço de nomes ficam pelo nome (`class`, `href`); os com, na notação de
    Clark (`{http://www.w3.org/XML/1998/namespace}lang` — `XML_LANG`, `EPUB_TYPE`, `XLINK_HREF`).
    """

    nome: str
    espaco: str
    atributos: dict[str, str]
    linha: int
    coluna: int
    pai: Elemento | None = None
    filhos: list[Elemento | Trecho] = field(default_factory=list)

    def get(self, nome: str, padrao: str | None = None) -> str | None:
        return self.atributos.get(nome, padrao)

    def classes(self) -> list[str]:
        return (self.atributos.get("class") or "").split()

    def elementos(self) -> Iterator[Elemento]:
        """Este e os descendentes, na ordem do documento (sem recursão)."""
        pilha: list[Elemento] = [self]
        while pilha:
            atual = pilha.pop()
            yield atual
            pilha.extend(f for f in reversed(atual.filhos) if isinstance(f, Elemento))

    def trechos(self) -> Iterator[Trecho]:
        """Os trechos de texto dos descendentes, na ordem do documento."""
        pilha: list[Elemento | Trecho] = [self]
        while pilha:
            atual = pilha.pop()
            if isinstance(atual, Trecho):
                yield atual
            else:
                pilha.extend(reversed(atual.filhos))

    def texto(self) -> str:
        return "".join(t.texto for t in self.trechos())

    def ancestrais(self) -> Iterator[Elemento]:
        atual = self.pai
        while atual is not None:
            yield atual
            atual = atual.pai


@dataclass(eq=False)
class Documento:
    """O arquivo lido: a raiz (ou `None`, se ele não se leu) e o texto dele."""

    arquivo: str
    texto: str
    raiz: Elemento | None = None
    doctype: str | None = None

    def elementos(self) -> Iterator[Elemento]:
        return self.raiz.elementos() if self.raiz is not None else iter(())

    def local(self, no: Elemento | Trecho, deslocamento: int = 0) -> Local:
        """O local de um elemento (o `<`) ou de um caractere de um trecho."""
        if isinstance(no, Trecho) and deslocamento:
            linha, coluna = no.posicao(deslocamento)
            return Local(self.arquivo, linha, coluna)
        return Local(self.arquivo, no.linha, no.coluna)

    def deslocamento(self, linha: int, coluna: int) -> int:
        """A posição no texto de `linha:coluna` (as duas de 1)."""
        inicio = 0
        for _ in range(linha - 1):
            inicio = self.texto.index("\n", inicio) + 1
        return inicio + coluna - 1


def _nome(qualificado: str) -> tuple[str, str]:
    espaco, _, local = qualificado.rpartition("}")
    return espaco, local


def _atributo(qualificado: str) -> str:
    espaco, local = _nome(qualificado)
    return f"{{{espaco}}}{local}" if espaco else local


class _Leitor:
    def __init__(self, arquivo: str, texto: str) -> None:
        self.arquivo = arquivo
        self.fonte = texto
        self.raiz: Elemento | None = None
        self.pilha: list[Elemento] = []
        self.problemas: list[Problema] = []
        self.doctype: str | None = None
        self._texto: list[str] = []
        self._inicio_do_texto = (0, 0)
        self._fundo_acusado = False
        self.parser = expat.ParserCreate(namespace_separator="}")
        self.parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
        self.parser.StartElementHandler = self._abre
        self.parser.EndElementHandler = self._fecha
        self.parser.CharacterDataHandler = self._caracteres
        self.parser.CommentHandler = self._outro
        self.parser.ProcessingInstructionHandler = self._outro
        self.parser.StartDoctypeDeclHandler = self._doctype
        self.parser.EntityDeclHandler = self._entidade

    def _posicao(self) -> tuple[int, int]:
        return self.parser.CurrentLineNumber, self.parser.CurrentColumnNumber + 1

    def _descarregar(self) -> None:
        if self._texto and self.pilha:
            linha, coluna = self._inicio_do_texto
            self.pilha[-1].filhos.append(Trecho("".join(self._texto), linha, coluna,
                                                self.pilha[-1]))
        self._texto = []

    def _abre(self, nome: str, atributos: dict[str, str]) -> None:
        self._descarregar()
        linha, coluna = self._posicao()
        espaco, local = _nome(nome)
        elemento = Elemento(local, espaco, {_atributo(k): v for k, v in atributos.items()},
                            linha, coluna, self.pilha[-1] if self.pilha else None)
        if self.pilha:
            self.pilha[-1].filhos.append(elemento)
        else:
            self.raiz = elemento
        self.pilha.append(elemento)
        if len(self.pilha) > LIMITE_DE_ANINHAMENTO and not self._fundo_acusado:
            self._fundo_acusado = True
            self.problemas.append(Problema(ANINHAMENTO, Local(self.arquivo, linha, coluna),
                                           f"{len(self.pilha)} níveis em <{local}>"))

    def _fecha(self, _etiqueta: str) -> None:
        self._descarregar()
        self.pilha.pop()

    def _caracteres(self, dados: str) -> None:
        if not self._texto:
            self._inicio_do_texto = self._posicao()
        self._texto.append(dados)

    def _outro(self, *_args: object) -> None:
        self._descarregar()

    def _doctype(self, nome: str, _sistema: str | None, _publico: str | None,
                 _interno: bool) -> None:
        self.doctype = nome

    def _entidade(self, nome: str, _parametro: bool, valor: str | None, _base: str | None,
                  sistema: str | None, _publico: str | None, _notacao: str | None) -> None:
        # O expat dá a posição do valor; o problema aponta o `<!ENTITY` da declaração.
        documento = Documento(self.arquivo, self.fonte)
        agora = documento.deslocamento(*self._posicao())
        inicio = self.fonte.rfind("<!ENTITY", 0, agora + 1)
        linha = self.fonte.count("\n", 0, max(inicio, 0)) + 1
        coluna = max(inicio, 0) - self.fonte.rfind("\n", 0, max(inicio, 0))
        local = Local(self.arquivo, linha, coluna)
        if valor is None and sistema is not None:
            self.problemas.append(Problema(ENTIDADE_EXTERNA, local, f"{nome} → {sistema}"))
        else:
            self.problemas.append(Problema(ENTIDADE_INTERNA, local, nome))
        raise _Recusado


def ler(arquivo: str, texto: str) -> tuple[Documento, list[Problema]]:
    """O documento com a árvore posicionada, e os problemas da camada XML e da R4.3 dele."""
    if len(texto.encode("utf-8")) > LIMITE_DE_BYTES:
        return Documento(arquivo, texto), [Problema(
            TAMANHO, Local(arquivo, 1, 1), f"{len(texto.encode('utf-8')) / 2**20:.1f} MB")]
    leitor = _Leitor(arquivo, texto)
    try:
        leitor.parser.Parse(texto, True)
    except _Recusado:
        return Documento(arquivo, texto, None, leitor.doctype), leitor.problemas
    except expat.ExpatError as erro:
        leitor.problemas.append(Problema(
            MAL_FORMADO, Local(arquivo, erro.lineno, erro.offset + 1),
            expat.errors.messages[erro.code]))
        return Documento(arquivo, texto, None, leitor.doctype), leitor.problemas
    return Documento(arquivo, texto, leitor.raiz, leitor.doctype), leitor.problemas
