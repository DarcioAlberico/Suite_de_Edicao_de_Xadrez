"""O controle que recebe o foco numa rolagem fica à vista, inteiro, venha o foco de onde vier.

`QScrollArea.focusNextPrevChild` só rola até o foco que anda **dentro** da rolagem: o foco que entra
nela vindo de fora — o Shift+Tab de uma ação abaixo dela, o Tab de uma lista ao lado — cai onde o
controle estiver, e abaixo da dobra ele fica com 0 px à vista. Medido com a tecla de verdade: na
Revisão de texto a 1280×641 o Shift+Tab das ações punha o foco em «Letras → figurinas» (crítico da
fase 5, ciclo 4), e na Rotulagem o Tab da lista punha na «Leitura do motor» (o portão do teclado com
a tecla, ciclo 5). A «Carta» do crítico põe o foco invisível entre os defeitos que reprovam
sozinhos.

**A troca de foco da aplicação, e não um filtro por controle.** A primeira versão punha um filtro
de evento em cada controle que a rolagem tinha ao nascer; um controle criado depois (uma lista que
se redesenha) ficava de fora. `QApplication.focusChanged` diz todo foco novo, e a rolagem pergunta
se ele é dela.

**O controle inteiro, e não o cursor.** `ensureWidgetVisible` rola até a `microFocus` de um campo de
texto — o retângulo do cursor —, e a «Leitura do motor» da Revisão de texto recebia o foco com 28
de 48 px à vista na pele Fita (crítico da fase 5, ciclo 5). :func:`mostrar` rola até o retângulo do
controle; quando ele é maior que a vista, até o começo dele.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QPoint, QRect, Qt, pyqtSlot
from PyQt6.QtWidgets import QApplication, QScrollArea, QScrollBar, QWidget

#: A folga em volta do controle que a rolagem mostra, em px: a moldura do foco fica à vista.
FOLGA = 6


def focaveis(raiz: QWidget) -> list[QWidget]:
    """Os descendentes de ``raiz`` que o Tab alcança, na ordem em que a cadeia do foco os tem."""
    achados: list[QWidget] = []
    atual = raiz.nextInFocusChain()
    # a cadeia é circular e passa por `raiz`: a volta termina nela
    while atual is not None and atual is not raiz:
        tab = atual.focusPolicy().value & Qt.FocusPolicy.TabFocus.value
        if tab and raiz.isAncestorOf(atual):
            achados.append(atual)
        atual = atual.nextInFocusChain()
    return achados


def _encaixar(barra: QScrollBar, inicio: int, fim: int, vista: int) -> None:
    """Põe o intervalo ``[inicio, fim)`` do conteúdo dentro dos ``vista`` px que a barra mostra."""
    atual = barra.value()
    if fim - inicio + 2 * FOLGA > vista or inicio - FOLGA < atual:
        alvo = inicio - FOLGA
    elif fim + FOLGA > atual + vista:
        alvo = fim + FOLGA - vista
    else:
        return
    barra.setValue(max(barra.minimum(), min(barra.maximum(), alvo)))


def mostrar(rolagem: QScrollArea, controle: QWidget) -> None:
    """Rola ``rolagem`` até ``controle`` ficar inteiro à vista, ou o começo dele quando não cabe."""
    conteudo = rolagem.widget()
    if conteudo is None or not conteudo.isAncestorOf(controle):
        return
    alvo = QRect(controle.mapTo(conteudo, QPoint(0, 0)), controle.size())
    vista = rolagem.viewport().size()
    _encaixar(rolagem.verticalScrollBar(), alvo.top(), alvo.top() + alvo.height(), vista.height())
    _encaixar(rolagem.horizontalScrollBar(), alvo.left(), alvo.left() + alvo.width(), vista.width())


class RolagemSegueOFoco(QObject):
    """Mostra, na ``rolagem``, todo controle dela que recebe o foco, venha o foco de onde vier."""

    def __init__(self, rolagem: QScrollArea) -> None:
        super().__init__(rolagem)
        self._rolagem = rolagem
        self._ligado = True
        aplicacao = QApplication.instance()
        if isinstance(aplicacao, QApplication):
            aplicacao.focusChanged.connect(self._foco_mudou)

    @pyqtSlot(QWidget, QWidget)
    def _foco_mudou(self, _antigo: QWidget | None, novo: QWidget | None) -> None:
        if self._ligado and novo is not None:
            mostrar(self._rolagem, novo)

    def desligar(self) -> None:
        """A rolagem volta a seguir só o foco que anda dentro dela — o antes, para a sabotagem."""
        self._ligado = False
