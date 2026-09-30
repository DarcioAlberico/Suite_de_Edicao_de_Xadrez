"""Uma fileira de controles que quebra linha em vez de cortar (OCR_UI ciclo 2, fase 5, C18).

**Existe porque uma `QHBoxLayout` soma.** A largura mínima de uma fileira de botões numa caixa
horizontal é a soma dos botões, e ela sobe pela árvore até virar a largura mínima da janela -- ou,
dentro de uma rolagem sem barra horizontal, até cortar o que não cabe.  O crítico da fase 5 mediu
na aba Revisão de texto, com a janela no mínimo de 1248x640: o cartão pedia 466 px e a rolagem
mostrava 293; «Letras → figurinas», «Pular», «Anterior» e «Próxima» ficavam com **0 px** à vista.
Numa fileira fluida os controles descem para a linha de baixo quando não cabem, e a altura pedida
acompanha a largura (`heightForWidth`) -- é o `BarraFluida` do tronco (``qt/barra.py``), escrito
de novo aqui porque as abas da suíte não importam o tronco.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget

__all__ = ["FileiraFluida"]


class _Fluxo(QLayout):
    """O leiaute: os itens da esquerda para a direita, e a linha seguinte quando não cabem."""

    def __init__(self, parent: QWidget | None = None, *, espaco: int = 6) -> None:
        super().__init__(parent)
        self._itens: list[QLayoutItem] = []
        self._espaco = espaco
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, a0: QLayoutItem | None) -> None:  # noqa: N802 - assinatura do Qt
        if a0 is not None:
            self._itens.append(a0)

    def count(self) -> int:
        return len(self._itens)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - assinatura do Qt
        return self._itens[index] if 0 <= index < len(self._itens) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - assinatura do Qt
        return self._itens.pop(index) if 0 <= index < len(self._itens) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 - assinatura do Qt
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - assinatura do Qt
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - assinatura do Qt
        return self._arrumar(QRect(0, 0, width, 0), aplicar=False)

    def setGeometry(self, a0: QRect) -> None:  # noqa: N802 - assinatura do Qt
        super().setGeometry(a0)
        self._arrumar(a0, aplicar=True)

    def sizeHint(self) -> QSize:  # noqa: N802 - assinatura do Qt
        """O desejado: tudo numa linha só."""
        largura = altura = 0
        visiveis = [item for item in self._itens if not item.isEmpty()]
        for item in visiveis:
            dica = item.sizeHint()
            largura += dica.width()
            altura = max(altura, dica.height())
        largura += self._espaco * max(0, len(visiveis) - 1)
        margens = self.contentsMargins()
        return QSize(largura + margens.left() + margens.right(),
                     altura + margens.top() + margens.bottom())

    def minimumSize(self) -> QSize:  # noqa: N802 - assinatura do Qt
        """O mínimo: o maior controle sozinho numa linha -- nunca a soma."""
        tamanho = QSize()
        for item in self._itens:
            if not item.isEmpty():
                tamanho = tamanho.expandedTo(item.minimumSize())
        margens = self.contentsMargins()
        return tamanho + QSize(margens.left() + margens.right(), margens.top() + margens.bottom())

    def _arrumar(self, retangulo: QRect, *, aplicar: bool) -> int:
        margens = self.contentsMargins()
        area = retangulo.adjusted(margens.left(), margens.top(),
                                  -margens.right(), -margens.bottom())
        x, y, altura_da_linha = area.x(), area.y(), 0
        for item in self._itens:
            if item.isEmpty():
                continue
            dica = item.sizeHint()
            # Nunca mais largo que a linha: um rótulo com um nome de 149 caracteres fica com a
            # largura da linha (e elide), em vez de passar da borda.
            dica.setWidth(min(dica.width(), max(item.minimumSize().width(), area.width())))
            if x > area.x() and x + dica.width() > area.right() + 1:
                x = area.x()
                y += altura_da_linha + self._espaco
                altura_da_linha = 0
            if aplicar:
                item.setGeometry(QRect(QPoint(x, y), dica))
            x += dica.width() + self._espaco
            altura_da_linha = max(altura_da_linha, dica.height())
        return y + altura_da_linha - retangulo.y() + margens.bottom()


class FileiraFluida(QWidget):
    """A fileira: um `QWidget` com o leiaute fluido e a altura que a largura pede."""

    def __init__(self, parent: QWidget | None = None, *, espaco: int = 6) -> None:
        super().__init__(parent)
        self._fluxo = _Fluxo(self, espaco=espaco)
        politica = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        politica.setHeightForWidth(True)
        self.setSizePolicy(politica)

    def adicionar(self, widget: QWidget) -> QWidget:
        """Põe ``widget`` no fim da fileira (e o faz filho dela); devolve o próprio widget."""
        self._fluxo.addWidget(widget)
        return widget

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - assinatura do Qt
        return True

    def heightForWidth(self, a0: int) -> int:  # noqa: N802 - assinatura do Qt
        return self._fluxo.heightForWidth(a0)
