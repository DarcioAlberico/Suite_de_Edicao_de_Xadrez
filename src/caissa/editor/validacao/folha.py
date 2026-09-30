"""As folhas de estilo de um arquivo, com a posição de cada nó no arquivo.

Uma folha é o `.css` do projeto, o conteúdo de um `<style>` ou o de um `style=""`. O `tinycss2`
dá a linha e a coluna de cada nó dentro do texto que ele leu; aqui elas viram as do arquivo (o
`<style>` começa no meio do XHTML). O `style=""` acusa no elemento: o `expat` não dá a posição do
atributo.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import tinycss2

from caissa.editor.validacao.problema import Local
from caissa.editor.validacao.xml import XHTML, Documento, Elemento, Trecho

__all__ = ["Folha", "folhas_do_documento", "nos_de", "urls"]


@dataclass
class Folha:
    """Um texto CSS e onde ele começa no arquivo."""

    arquivo: str
    texto: str
    linha0: int = 1
    coluna0: int = 1
    elemento: Elemento | None = None
    """O elemento do `style=""`: tudo acusa nele."""
    declaracoes_so: bool = False
    """O `style=""` é uma lista de declarações, sem regras."""

    def local(self, no: Any) -> Local:
        if self.elemento is not None:
            return Local(self.arquivo, self.elemento.linha, self.elemento.coluna)
        linha = getattr(no, "source_line", 1) or 1
        coluna = getattr(no, "source_column", 1) or 1
        if linha == 1:
            return Local(self.arquivo, self.linha0, self.coluna0 + coluna - 1)
        return Local(self.arquivo, self.linha0 + linha - 1, coluna)

    def regras(self) -> list[Any]:
        if self.declaracoes_so:
            return []
        return list(tinycss2.parse_stylesheet(self.texto, skip_comments=True,
                                              skip_whitespace=True))

    def _itens(self) -> Iterator[tuple[Any, Any]]:
        """Cada item das listas de declarações (declaração ou erro) com a regra dele."""
        if self.declaracoes_so:
            for item in tinycss2.parse_declaration_list(self.texto, skip_comments=True,
                                                        skip_whitespace=True):
                yield None, item
            return
        pilha = list(self.regras())
        while pilha:
            regra = pilha.pop(0)
            if regra.type == "qualified-rule" or (regra.type == "at-rule"
                                                   and regra.lower_at_keyword in (
                                                       "font-face", "page")
                                                   and regra.content is not None):
                for item in tinycss2.parse_declaration_list(
                        regra.content, skip_comments=True, skip_whitespace=True):
                    yield regra, item
            elif regra.type == "at-rule" and regra.content is not None and \
                    regra.lower_at_keyword in ("media", "supports", "document"):
                pilha[:0] = list(tinycss2.parse_rule_list(regra.content, skip_comments=True,
                                                          skip_whitespace=True))

    def declaracoes(self) -> Iterator[tuple[Any, Any]]:
        """Cada declaração com a regra de onde ela veio (`None` no `style=""`)."""
        return ((r, d) for r, d in self._itens() if d.type == "declaration")

    def erros(self) -> Iterator[Any]:
        """Os erros de sintaxe: os das regras e os das listas de declarações."""
        yield from (r for r in self.regras() if r.type == "error")
        yield from (d for _, d in self._itens() if d.type == "error")


def nos_de(nos: Any) -> Iterator[Any]:
    """Todos os nós de uma lista de componentes, os de dentro das funções e blocos também."""
    pilha = list(nos or [])
    while pilha:
        no = pilha.pop(0)
        yield no
        filhos = getattr(no, "arguments", None) or getattr(no, "content", None)
        if isinstance(filhos, list):
            pilha[:0] = filhos


def urls(nos: Any) -> Iterator[tuple[Any, str]]:
    """Os endereços `url(...)` de uma lista de componentes, com o nó de cada um."""
    for no in nos_de(nos):
        if no.type == "url":
            yield no, no.value
        elif no.type == "function" and no.lower_name == "url":
            texto = next((a.value for a in no.arguments if a.type == "string"), None)
            if texto is not None:
                yield no, texto


def folhas_do_documento(documento: Documento) -> list[Folha]:
    """Os `<style>` e os `style=""` de um XHTML."""
    folhas: list[Folha] = []
    for elemento in documento.elementos():
        if elemento.nome == "style" and elemento.espaco in (XHTML, ""):
            trechos = [f for f in elemento.filhos if isinstance(f, Trecho)]
            if trechos:
                primeiro = trechos[0]
                folhas.append(Folha(documento.arquivo, "".join(t.texto for t in trechos),
                                    primeiro.linha, primeiro.coluna))
        estilo = elemento.get("style")
        if estilo:
            folhas.append(Folha(documento.arquivo, estilo, elemento=elemento,
                                declaracoes_so=True))
    return folhas
