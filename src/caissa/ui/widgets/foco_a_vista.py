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

**O clique não rola; o que o programa foca durante ele, depois dele.** O Qt dá o foco ao controle no
*pressionar* do clique, antes de entregar o evento; rolar ali tirava o controle de baixo do
ponteiro, e o *soltar* caía noutro lugar — o clique se perdia (crítico da fase 5, ciclo 6: 15 de 15
cliques em controles meio à vista, o «Gravar» da Galeria, o rádio do lado a jogar do Resultado). O
foco que o clique dá ao controle sob o ponteiro fica onde está (:func:`veio_do_mouse`): o controle
já está à vista, onde o ponteiro está. Mas no mesmo pressionar um painel pode mandar o foco a
**outro** controle — a linha da tabela da Rotulagem e da Revisão de texto manda o foco à «Verdade
da linha» —, e esse não está sob o ponteiro: calar o seguidor ali deixava a verdade fora da vista, e
o que se digitava ia para lá (crítico da fase 5, ciclo 7: 0×0 px a 1280×641 nas três peles). Esse
foco é mostrado **depois do soltar** (:func:`no_meio_do_clique`): o clique termina onde foi dado,
e a rolagem vem em seguida. O gêmeo deste arquivo no tronco é `chess_diagram_ocr.qt.foco_a_vista`.
"""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, pyqtSlot
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
    """Põe o intervalo ``[inicio, fim)`` do conteúdo dentro dos ``vista`` px que a barra mostra.

    Com a :data:`FOLGA` em volta quando cabe, e com menos folga quando só o controle cabe: a
    «Verdade da linha» da Rotulagem tem 549 px numa vista de 550, e a folga inteira a deixava com
    3 px cortados (crítico da fase 5, ciclo 7: «546 à vista»). Maior que a vista, o começo dele.
    """
    atual = barra.value()
    tamanho = fim - inicio
    if tamanho > vista:
        alvo = inicio - FOLGA
    else:
        folga = min(FOLGA, (vista - tamanho) // 2)
        if inicio - folga < atual:
            alvo = inicio - folga
        elif fim + folga > atual + vista:
            alvo = fim + folga - vista
        else:
            return
    barra.setValue(max(barra.minimum(), min(barra.maximum(), alvo)))


def sob_o_ponteiro(controle: QWidget) -> bool:
    """O ponteiro está sobre ``controle``, ou sobre quem o tem por procurador do foco.

    A caixa de escolha editável e a de número passam o foco ao campo delas (`focusProxy`): o clique
    na seta dá o foco ao campo, e é a caixa que está sob o ponteiro.
    """
    atual: QWidget | None = controle
    while atual is not None:
        if atual.underMouse():
            return True
        pai = atual.parentWidget()
        if pai is None or pai.focusProxy() is not atual:
            return False
        atual = pai
    return False


def no_meio_do_clique() -> bool:
    """Um botão do mouse está apertado: o clique está entre o pressionar e o soltar."""
    return QApplication.mouseButtons() != Qt.MouseButton.NoButton


def veio_do_mouse(controle: QWidget) -> bool:
    """O foco que ``controle`` acaba de receber é o do mouse sobre ele, e a rolagem não se mexe.

    O clique nele: um botão está apertado (o clique dá o foco no pressionar) e ele está sob o
    ponteiro (:func:`sob_o_ponteiro`) — o foco que o programa manda a outro controle no mesmo
    pressionar não é do mouse, e é mostrado depois do soltar. Ou a roda: o controle toma o foco dela
    (`Qt.FocusPolicy.WheelFocus`: as caixas de escolha e de número) e está sob o ponteiro. Estar sob
    o ponteiro parado não basta: o Tab que cai num botão sob o ponteiro rola até ele como até
    qualquer outro. Numa caixa de escolha sob o ponteiro parado, o Tab não rola (o sinal não diz se
    o foco veio da roda ou da tecla); ela já está à vista, ao menos onde o ponteiro está.
    """
    if no_meio_do_clique():
        return sob_o_ponteiro(controle)
    return controle.focusPolicy() == Qt.FocusPolicy.WheelFocus and controle.underMouse()


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
        self._pendente: QWidget | None = None
        self._esperando = False
        aplicacao = QApplication.instance()
        if isinstance(aplicacao, QApplication):
            aplicacao.focusChanged.connect(self._foco_mudou)

    @pyqtSlot(QWidget, QWidget)
    def _foco_mudou(self, _antigo: QWidget | None, novo: QWidget | None) -> None:
        # Primeiro se há foco novo e se a rolagem vive: a rolagem destruída com o foco dentro (o
        # diálogo de bases depois da pergunta) limpa o foco no destrutor, quando a rolagem já se
        # foi e este seguidor, filho dela, ainda não.
        if not self._ligado or novo is None or sip.isdeleted(self._rolagem):
            return
        conteudo = self._rolagem.widget()
        if conteudo is None or not conteudo.isAncestorOf(novo) or veio_do_mouse(novo):
            return
        if no_meio_do_clique():
            self._esperar_o_soltar(novo)
            return
        mostrar(self._rolagem, novo)

    def _esperar_o_soltar(self, controle: QWidget) -> None:
        """O foco que o programa moveu no meio do clique é mostrado quando o botão sobe.

        O filtro fica na aplicação só entre o pressionar e o soltar.
        """
        self._pendente = controle
        aplicacao = QApplication.instance()
        if not self._esperando and aplicacao is not None:
            aplicacao.installEventFilter(self)
            self._esperando = True

    def eventFilter(self, objeto: QObject | None, evento: QEvent | None) -> bool:  # noqa: N802 - Qt
        soltou = evento is not None and evento.type() == QEvent.Type.MouseButtonRelease
        if soltou and self._esperando:
            aplicacao = QApplication.instance()
            if aplicacao is not None:
                aplicacao.removeEventFilter(self)
            self._esperando = False
            # depois de o soltar chegar ao controle clicado: o clique termina onde foi dado
            QTimer.singleShot(0, self._mostrar_o_pendente)
        return super().eventFilter(objeto, evento)

    def _mostrar_o_pendente(self) -> None:
        controle, self._pendente = self._pendente, None
        if (controle is None or not self._ligado or sip.isdeleted(controle)
                or sip.isdeleted(self._rolagem) or QApplication.focusWidget() is not controle):
            return
        mostrar(self._rolagem, controle)

    def desligar(self) -> None:
        """A rolagem volta a seguir só o foco que anda dentro dela — o antes, para a sabotagem."""
        self._ligado = False
