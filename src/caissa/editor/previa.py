"""A prévia do Resultado pelo MuPDF, como função de módulo para o processo de trabalho (S6, H2/H13).

O PyMuPDF segura o GIL (43–49 ms por página, T `processo_de_trabalho.py`): o leiaute da prévia não
pode rodar na thread da janela, nem numa `QThread` da mesma — só num processo à parte. Por isso a
função é de módulo (picklável), sem Qt, e devolve só números e bytes.

Este é o mínimo que o protótipo do H2 precisa para provar que a prévia fica ligada enquanto se
digita (o pedido vai, a resposta volta, a janela não trava). O motor completo — `Archive` com o
CSS, os SVG e as fontes do projeto, as posições dos elementos, os modos Leitor e Página — é do H13.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import tinycss2

#: A página da prévia no protótipo: A5 em pontos.
LARGURA_PT = 420.0
ALTURA_PT = 595.0
#: Um livro hostil (um elemento que nunca cabe) não pagina para sempre.
MAXIMO_DE_PAGINAS = 500


def renderizar(texto: str, *, dpi: int = 72) -> dict[str, Any]:
    """Pagina o XHTML pelo `Story` do MuPDF e desenha a primeira página; números e o PNG."""
    import io

    import pymupdf

    historia = pymupdf.Story(html=texto)
    saida = io.BytesIO()
    escritor = pymupdf.DocumentWriter(saida)
    paginas = 0
    caixa = pymupdf.Rect(36, 36, LARGURA_PT - 36, ALTURA_PT - 36)
    mais = True
    while mais:
        dispositivo = escritor.begin_page(pymupdf.Rect(0, 0, LARGURA_PT, ALTURA_PT))
        mais, _ = historia.place(caixa)
        historia.draw(dispositivo)
        escritor.end_page()
        paginas += 1
        if paginas >= MAXIMO_DE_PAGINAS:
            break
    escritor.close()
    with pymupdf.open("pdf", saida.getvalue()) as documento:
        png = documento[0].get_pixmap(dpi=dpi).tobytes("png")
    return {"paginas": paginas, "png": png}


_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)")


def resolver_variaveis(css: str) -> str:
    """O CSS com cada `var(--x)` trocado pelo valor da `:root` (o MuPDF não resolve `var()`).

    Medido no H1: sem isto, toda cor, borda e medida do `BASE_CSS` por variável cai no padrão
    na prévia do MuPDF. Valem as variáveis das regras `:root` e `html` de fora de `@media` (o
    tema claro; o escuro de `prefers-color-scheme` não entra); o valor de reserva de
    `var(--x, reserva)` vale quando a variável falta.
    """
    variaveis: dict[str, str] = {}
    for regra in tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True):
        if regra.type != "qualified-rule" or \
                tinycss2.serialize(regra.prelude).strip() not in (":root", "html"):
            continue
        for declaracao in tinycss2.parse_declaration_list(regra.content, skip_comments=True,
                                                          skip_whitespace=True):
            if declaracao.type == "declaration" and declaracao.name.startswith("--"):
                variaveis[declaracao.name] = tinycss2.serialize(declaracao.value).strip()

    def trocar(casado: re.Match[str]) -> str:
        return variaveis.get(casado.group(1), (casado.group(2) or "").strip()) or "initial"

    for _ in range(5):  # a variável que usa outra
        novo = _VAR.sub(trocar, css)
        if novo == css:
            break
        css = novo
    return css


@dataclass
class Paginas:
    """O capítulo paginado pelo MuPDF: o PDF em memória e se a paginação bateu no teto."""

    pdf: bytes
    paginas: int
    laco: bool
    """A paginação não terminou no teto (o `page-break-before` no primeiro elemento, H1)."""


def paginar(texto: str, css: str = "", *, largura: float = LARGURA_PT,
            altura: float = ALTURA_PT, maximo: int = MAXIMO_DE_PAGINAS,
            em: float = 16.0) -> Paginas:
    """Pagina o XHTML pelo `Story` do MuPDF, com o CSS dado (as variáveis resolvidas).

    O `em` de 16 é o do navegador: o MuPDF conta o px do CSS como a unidade da página.
    """
    import io

    import pymupdf

    historia = pymupdf.Story(html=texto, user_css=resolver_variaveis(css), em=em)
    saida = io.BytesIO()
    escritor = pymupdf.DocumentWriter(saida)
    caixa = pymupdf.Rect(36, 36, largura - 36, altura - 36)
    paginas = 0
    mais = True
    while mais and paginas < maximo:
        dispositivo = escritor.begin_page(pymupdf.Rect(0, 0, largura, altura))
        mais, _ = historia.place(caixa)
        historia.draw(dispositivo)
        escritor.end_page()
        paginas += 1
    escritor.close()
    return Paginas(saida.getvalue(), paginas, bool(mais))
