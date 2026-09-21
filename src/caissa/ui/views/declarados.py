"""O que as abas da suíte declaram fora do widget (OCR_UI ciclo 2, passo C8).

A tabela ``comando -> método`` das duas abas que a suíte empresta à janela do tronco (Rotulagem,
Revisão de texto), no molde de ``chess_diagram_ocr.ui.sala_declarada.COMANDOS_DA_ABA``: o tronco
gera as ligações a partir dela, e o comando chega ao menu, à paleta de comandos, à legenda de
atalhos e ao portão ``caissa.ui.audit.comandos`` -- que só varre o catálogo e não via os
``QShortcut`` locais que as abas tinham (``Ctrl+S`` e ``Ctrl+O``, ambíguos com os globais da
janela: com a aba à frente, nem um nem outro disparava).

O tronco não importa ``caissa`` sem guarda; ``chess_diagram_ocr.qt.painel_de_rotulagem.comandos``
e o par da revisão de texto leem esta tabela quando a suíte está ao alcance e devolvem ``{}``
quando não. Os nomes dos comandos moram no catálogo do tronco (``ui/comandos.py``); os métodos
moram aqui, nas views, e é por isso que a tabela fica deste lado.
"""

from __future__ import annotations

__all__ = ["COMANDOS_DA_REVISAO_DE_TEXTO", "COMANDOS_DA_ROTULAGEM"]

COMANDOS_DA_ROTULAGEM: dict[str, str] = {
    "rotulagem_ler_pagina": "recognise_page",
    "rotulagem_salvar": "save",
    "rotulagem_desenhar": "toggle_drawing",
}
"""Aba Rotulagem: ler a página com o modelo do livro, gravar os rótulos, desenhar uma caixa."""

COMANDOS_DA_REVISAO_DE_TEXTO: dict[str, str] = {
    "revisao_texto_gravar": "gravar",
    "revisao_texto_abrir": "escolher_pdf",
}
"""Aba Revisão de texto: gravar as decisões (valem na próxima importação) e abrir outro PDF."""
