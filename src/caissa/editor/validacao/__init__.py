"""A validação em camadas do Editor HTML/CSS (spec S10; roadmap H10).

Cada camada é `(documento, contexto) → [Problema]`, e todo problema tem código, severidade, local
(`arquivo:linha:coluna`), o que fazer e, quando seguro, conserto:

- **XML** (`xml.py`) — bem formado, com a linha e a coluna do `expat`; e a leitura patológica da
  R4.3 (o tamanho, o aninhamento, as entidades);
- **segurança** (`seguranca.py`) — a R4.2 e a R4.3;
- **contrato** (`contrato.py`) — as classes e os atributos do `MARKUP_CAISSA` (do CB);
- **xadrez** (`xadrez.py`) — o lance legal, a notação, a figurina na fonte (do CB);
- **CSS** (`css.py`) — a sintaxe, a propriedade, o motor, o DOCX, o contraste AAA;
- **acessibilidade** (`acessibilidade.py`) — o WCAG 2.2 AA e o AAA que se aplica;
- **OCR** (`ocr.py`) — as dúvidas pendentes;
- **EPUBCheck** (`epubcheck.py`) — o livro montado, mensagem a mensagem, com o local.

Nada aqui usa o Qt, e nada roda na thread da janela: a janela (H12) chama `validar_arquivo` num
trabalhador.
"""

from __future__ import annotations

from collections.abc import Iterable

from caissa.editor.validacao import (
    acessibilidade,
    contrato,
    css,
    ocr,
    seguranca,
    xadrez,
    xml,
)
from caissa.editor.validacao.contexto import Contexto
from caissa.editor.validacao.folha import Folha
from caissa.editor.validacao.problema import REGRAS, Problema, Severidade

__all__ = ["REGRAS", "Contexto", "Problema", "Severidade", "ordenar", "validar_arquivo",
           "validar_projeto"]

_ORDEM = {Severidade.BLOQUEIA: 0, Severidade.AVISA: 1, Severidade.INFORMA: 2}
XHTML = (".xhtml", ".html", ".htm")


def ordenar(problemas: Iterable[Problema]) -> list[Problema]:
    """O que bloqueia primeiro; depois pelo arquivo, a linha e a coluna."""
    return sorted(problemas, key=lambda p: (_ORDEM[p.severidade], p.local.arquivo,
                                            p.local.linha, p.local.coluna, p.codigo))


def validar_arquivo(arquivo: str, texto: str, contexto: Contexto | None = None) -> list[Problema]:
    """Todas as camadas num arquivo do projeto (XHTML, CSS ou SVG)."""
    contexto = contexto if contexto is not None else Contexto()
    nome = arquivo.lower()
    if nome.endswith(".css"):
        folha = Folha(arquivo, texto)
        problemas = seguranca.verificar_folha(folha, contexto)
        problemas += css.verificar_folha(folha, contexto)
        problemas += css.verificar_mapa(folha)
        problemas += acessibilidade.verificar_folha(folha, contexto)
        return ordenar(problemas)
    documento, problemas = xml.ler(arquivo, texto)
    if documento.raiz is None:
        return ordenar(problemas)
    problemas += seguranca.verificar(documento, contexto)
    if nome.endswith(".svg"):
        return ordenar(problemas)
    for camada in (contrato, xadrez, css, acessibilidade, ocr):
        problemas += camada.verificar(documento, contexto)
    return ordenar(problemas)


def validar_projeto(contexto: Contexto) -> dict[str, list[Problema]]:
    """Todos os arquivos de texto do projeto, cada um com os seus problemas."""
    resultado = {}
    for caminho, dados in sorted(contexto.arquivos.items()):
        if caminho.lower().endswith((*XHTML, ".css", ".svg")):
            resultado[caminho] = validar_arquivo(caminho, dados.decode("utf-8", "replace"),
                                                 contexto)
    return resultado
