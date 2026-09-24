"""A prévia do Resultado pelo MuPDF, como função de módulo para o processo de trabalho (S6, H2/H13).

O PyMuPDF segura o GIL (43–49 ms por página, T `processo_de_trabalho.py`): o leiaute da prévia não
pode rodar na thread da janela, nem numa `QThread` da mesma — só num processo à parte. Por isso a
função é de módulo (picklável), sem Qt, e devolve só números e bytes.

Este é o mínimo que o protótipo do H2 precisa para provar que a prévia fica ligada enquanto se
digita (o pedido vai, a resposta volta, a janela não trava). O motor completo — `Archive` com o
CSS, os SVG e as fontes do projeto, as posições dos elementos, os modos Leitor e Página — é do H13.
"""

from __future__ import annotations

from typing import Any

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
