"""O controle que recebe o foco numa rolagem fica à vista, também quando o foco vem de fora dela.

`QScrollArea.focusNextPrevChild` só rola até o foco que anda **dentro** da rolagem: o foco que entra
nela vindo de fora — o Shift+Tab de uma ação abaixo dela, o Tab de uma lista ao lado — cai onde o
controle estiver, e abaixo da dobra ele fica com 0 px à vista. Medido com a tecla de verdade: na
Revisão de texto a 1280×641 o Shift+Tab das ações punha o foco em «Letras → figurinas» (crítico da
fase 5, ciclo 4), e na Rotulagem o Tab da lista punha na «Leitura do motor» (o portão do teclado com
a tecla, ciclo 5). A «Carta» do crítico põe o foco invisível entre os defeitos que reprovam
sozinhos.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QScrollArea, QWidget


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


class RolagemSegueOFoco(QObject):
    """Pede à ``rolagem`` que mostre o controle de ``raiz`` que recebe o foco, venha de onde vier.

    Os controles são os de ``raiz`` quando o filtro nasce (`focaveis`): monte-o depois do conteúdo.
    """

    def __init__(self, rolagem: QScrollArea, raiz: QWidget) -> None:
        super().__init__(rolagem)
        self._rolagem = rolagem
        self.controles = focaveis(raiz)
        for controle in self.controles:
            controle.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - assinatura do Qt
        if event.type() == QEvent.Type.FocusIn and isinstance(obj, QWidget):
            self._rolagem.ensureWidgetVisible(obj)
        return False

    def desligar(self) -> None:
        """Tira o filtro de todo controle — o antes, para a sabotagem dos testes."""
        for controle in self.controles:
            controle.removeEventFilter(self)
