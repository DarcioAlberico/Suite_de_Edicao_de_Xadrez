"""A tabela de linhas que guarda para si as teclas de lista: PgUp, PgDn, Home e End.

Na janela do tronco essas quatro teclas são atalhos da janela -- a página anterior, a próxima, a
primeira e a última do livro --, e a guarda de atalhos (`qt/atalhos.GuardaDeAtalhos`, um filtro na
aplicação inteira) as vê antes do controle em foco. Ela só as cede a um campo de texto. Com o foco
na tabela «Linhas da página» da Rotulagem, o PgDn levava a aba à página seguinte do livro, e a
tabela e o cartão ficavam vazios; na «Dúvidas do livro» da Revisão de texto, virava a página atrás
da aba e a linha da lista não se mexia (crítico da fase 5, ciclo 6). E o comentário de
`cartao_da_linha.pelas_setas` prometia o PgUp/PgDn andando pelas linhas.

A saída é a da própria guarda: um controle na cadeia do foco que **declara** a ação para si
(`ui/atalhos.DonoDeAcoes`, verificado pelo formato, sem importar o tronco) a atende no lugar da
janela. Com o foco na tabela, as quatro teclas andam pelas linhas, como numa lista; fora dela, viram
a página do livro, como sempre.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget

#: A ação da janela (a tabela de atalhos do tronco) → o passo da lista que a tecla dá na tabela.
PASSOS_DE_LISTA: dict[str, QAbstractItemView.CursorAction] = {
    "pagina_anterior": QAbstractItemView.CursorAction.MovePageUp,
    "proxima_pagina": QAbstractItemView.CursorAction.MovePageDown,
    "primeira_pagina": QAbstractItemView.CursorAction.MoveHome,
    "ultima_pagina": QAbstractItemView.CursorAction.MoveEnd,
}


class TabelaDeLinhas(QTableWidget):
    """Uma `QTableWidget` que atende as ações de página da janela com os passos de lista.

    Com o foco nela (`DonoDeAcoes`: :meth:`acoes_proprias` e :meth:`atender`).
    """

    def acoes_proprias(self) -> frozenset[str]:
        """As ações que esta tabela atende enquanto tem o foco."""
        return frozenset(PASSOS_DE_LISTA)

    def atender(self, acao: str) -> Callable[[], object] | None:
        """O passo de lista para ``acao``, ou `None` quando ela não é uma das teclas de lista."""
        passo = PASSOS_DE_LISTA.get(acao)
        if passo is None:
            return None
        return lambda: self.andar(passo)

    def andar(self, passo: QAbstractItemView.CursorAction) -> None:
        """Move a linha atual como a tecla de lista move numa lista de linhas.

        O Home e o End vão à primeira e à última linha: na `QTableView` eles andam pelas colunas
        da linha, e só com o Ctrl vão às pontas da tabela; aqui a linha inteira é o item.
        """
        pontas = (QAbstractItemView.CursorAction.MoveHome, QAbstractItemView.CursorAction.MoveEnd)
        modificador = (Qt.KeyboardModifier.ControlModifier if passo in pontas
                       else Qt.KeyboardModifier.NoModifier)
        indice = self.moveCursor(passo, modificador)
        if indice.isValid():
            self.setCurrentIndex(indice)

    def keyPressEvent(self, e: QKeyEvent | None) -> None:  # noqa: N802 - assinatura do Qt
        """O Home e o End vão às pontas da lista, e não às da linha.

        Também sem a guarda da janela: a aba aberta sozinha.
        """
        if (e is not None and e.modifiers() == Qt.KeyboardModifier.NoModifier
                and e.key() in (Qt.Key.Key_Home, Qt.Key.Key_End)):
            self.andar(QAbstractItemView.CursorAction.MoveHome if e.key() == Qt.Key.Key_Home
                       else QAbstractItemView.CursorAction.MoveEnd)
            e.accept()
            return
        super().keyPressEvent(e)
