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

**O clique não rola; o que o programa foca durante ele, quando o mouse sossega.** O Qt dá o foco
ao controle no *pressionar* do clique, antes de entregar o evento; rolar ali tirava o controle de
baixo do ponteiro, e o *soltar* caía noutro lugar — o clique se perdia (crítico da fase 5, ciclo 6:
15 de 15 cliques em controles meio à vista, o «Gravar» da Galeria, o rádio do lado a jogar do
Resultado). O foco que o clique dá ao controle clicado fica onde está (:func:`veio_do_mouse`): o
controle já está à vista, onde o ponteiro está. Mas no mesmo clique um painel pode mandar o foco a
**outro** controle — a linha da tabela da Rotulagem e da Revisão de texto manda o foco à «Verdade
da linha» —: calar o seguidor ali deixava a verdade fora da vista, e o que se digitava ia para lá
(crítico da fase 5, ciclo 7: 0×0 px a 1280×641 nas três peles). E mostrá-lo logo depois do soltar
mexia o conteúdo debaixo do ponteiro parado antes do segundo clique de um duplo clique: na
Rotulagem, com a rolagem no fim, o segundo clique na linha 4 caía em «Aceitar leitura» e aceitava
uma leitura que ninguém aceitou (crítico da fase 5, ciclo 8). Esse foco aparece **quando o mouse
sossega** (:func:`mouse_sossegado`) — nenhum botão apertado, e o intervalo do duplo clique da
plataforma passado desde o último soltar: o segundo clique cai onde o primeiro caiu —, ou na
primeira tecla, antes de ela chegar ao controle.

**A razão do foco, e não o ponteiro.** Quem diz qual foco é o do mouse é a razão do `QFocusEvent`
(:class:`_RazaoDoFoco`): o clique e a roda dão `MouseFocusReason`, o Tab dá a dele, o `setFocus()`
do programa dá `OtherFocusReason`. Perguntar ao `underMouse` do controle, como a primeira versão do
ciclo 8, falhava quando a marca ficava velha — o ponteiro que sai da janela sem o evento de saída,
a rolagem que se mexe sob o ponteiro parado —: a verdade, clicada antes, parecia «sob o ponteiro»
no clique da linha, e ficava fora da vista (o portão do teclado, com o clique que deixa a ação
rodar).

**O foco que a janela devolve ao voltar espera o mesmo sossego.** Quando a janela volta a ser a
ativa, o Qt devolve o foco ao controle que o tinha (`ActiveWindowFocusReason`), e o Windows ativa a
janela **antes** de entregar o pressionar do clique que a reativou: se a roda tinha levado a vista
para longe daquele controle, rolar até ele ali tirava de baixo do ponteiro o controle clicado
(achado pelo construtor no ciclo 8: o «Aceitar» não recebia o clique). Esse foco espera o
intervalo do duplo clique inteiro (:func:`voltou_com_a_janela`): o clique que reativou a janela
chega dentro dele, e o foco da volta só aparece se o clique não o levou a outro controle; sem
clique (o Alt+Tab, o diálogo que fechou), aparece passado o intervalo, ou na primeira tecla. O Tab
e o Shift+Tab rolam na hora (:func:`veio_do_teclado`).

**O que está sob o ponteiro também não desliza.** Na Rotulagem a tabela «Linhas da página» fica na
mesma rolagem, abaixo do cartão da linha, e o motivo do cartão quebra em uma ou duas linhas
conforme a linha escolhida: com a rolagem no fim e parada, a 1280×641 na Clássica, o clique na
linha 3 da Gallagher p. 51 fazia o cartão crescer 16 px, a tabela descia, e o segundo clique do
duplo clique caía na linha 2 (achado pelo construtor no ciclo 9, `c9/sonda_tabela_desliza.py`).
:func:`ancorar` mantém o controle clicado no mesmo lugar da vista até o mouse sossegar, compensando
na rolagem cada mudança de altura acima dele -- e, com a rolagem no começo, o que encolhe acima
dele com uma folga no alto do conteúdo, até soltar; a roda ou a barra que a pessoa mexe no meio
soltam a âncora, e o seguidor a solta antes de mostrar um controle. O gêmeo deste arquivo no tronco
é `chess_diagram_ocr.qt.foco_a_vista`, sem a âncora.
"""

from __future__ import annotations

import time
from typing import cast

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import QApplication, QScrollArea, QScrollBar, QWidget

#: A folga em volta do controle que a rolagem mostra, em px: a moldura do foco fica à vista.
FOLGA = 6

#: O intervalo do duplo clique do Qt, em ms, quando a aplicação não diz o dela.
INTERVALO_PADRAO_DO_DUPLO_CLIQUE = 400

#: De quantos em quantos ms a âncora pergunta se o mouse sossegou (:func:`ancorar`).
INTERVALO_DA_VIGIA = 50

#: As teclas que só modificam o clique ou a tecla seguinte: não mostram o foco que espera.
_MODIFICADORES = frozenset(tecla.value for tecla in (
    Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
    Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock, Qt.Key.Key_ScrollLock,
))


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


class _RazaoDoFoco(QObject):
    """A razão do último foco que um controle recebeu na aplicação.

    `QApplication.focusChanged` não diz a razão, e o `QFocusEvent` que a diz chega ao controle antes
    do sinal: o clique dá o foco ao controle clicado (ou a quem aceita o foco acima dele) com
    `MouseFocusReason`, e a roda também; o Tab e o Shift+Tab, com as deles; o `setFocus()` do
    programa, com `OtherFocusReason`. Um filtro só, na aplicação, para todos os seguidores, e ele só
    anota: o controle e a razão (o `FocusIn` vai também ao estilo, que não é um controle), e a
    hora do último soltar de um botão do mouse (:func:`mouse_sossegado`).
    """

    def __init__(self, aplicacao: QApplication) -> None:
        super().__init__(aplicacao)
        self.aplicacao = aplicacao
        self.controle: QWidget | None = None
        self.razao = Qt.FocusReason.OtherFocusReason
        self.soltou_em = float("-inf")
        aplicacao.installEventFilter(self)

    def eventFilter(self, objeto: QObject | None, evento: QEvent | None) -> bool:  # noqa: N802 - Qt
        if evento is None:
            return False
        tipo = evento.type()
        if tipo == QEvent.Type.FocusIn and isinstance(objeto, QWidget):
            self.controle = objeto
            self.razao = evento.reason()  # type: ignore[attr-defined]  # um QFocusEvent
        elif tipo == QEvent.Type.MouseButtonRelease:
            self.soltou_em = time.monotonic()
        return False


_RAZAO: list[_RazaoDoFoco] = []


def _razao_do_foco() -> _RazaoDoFoco | None:
    """O anotador da razão do foco da aplicação de agora, posto nela na primeira vez."""
    aplicacao = QApplication.instance()
    if not isinstance(aplicacao, QApplication):
        return None
    if not _RAZAO or sip.isdeleted(_RAZAO[0]) or _RAZAO[0].aplicacao is not aplicacao:
        _RAZAO[:] = [_RazaoDoFoco(aplicacao)]
    return _RAZAO[0]


def no_meio_do_clique() -> bool:
    """Um botão do mouse está apertado: o clique está entre o pressionar e o soltar."""
    return QApplication.mouseButtons() != Qt.MouseButton.NoButton


def intervalo_do_duplo_clique() -> int:
    """O intervalo do duplo clique da plataforma, em ms (`QStyleHints.mouseDoubleClickInterval`).

    O segundo clique de um duplo clique chega dentro dele: até lá, o que está sob o ponteiro não
    muda.
    """
    dicas = QApplication.styleHints()
    if dicas is None:
        return INTERVALO_PADRAO_DO_DUPLO_CLIQUE
    return dicas.mouseDoubleClickInterval()


def mouse_sossegado() -> bool:
    """Nenhum botão apertado, e o intervalo do duplo clique passado desde o último soltar."""
    if no_meio_do_clique():
        return False
    razao = _razao_do_foco()
    if razao is None:
        return True
    return (time.monotonic() - razao.soltou_em) * 1000 >= intervalo_do_duplo_clique()


def veio_do_mouse(controle: QWidget) -> bool:
    """O foco que ``controle`` acaba de receber é o do mouse sobre ele, e a rolagem não se mexe.

    O clique nele, ou a roda: a razão do `QFocusEvent` dele é `MouseFocusReason`
    (:class:`_RazaoDoFoco`). O foco que o programa manda a outro controle no mesmo clique tem
    outra razão (o `setFocus()`, `OtherFocusReason`), e é mostrado quando o mouse sossega; o Tab e o
    Shift+Tab rolam até o controle, também quando ele está sob o ponteiro parado.
    """
    razao = _razao_do_foco()
    return (razao is not None and razao.controle is controle
            and razao.razao == Qt.FocusReason.MouseFocusReason)


def voltou_com_a_janela(controle: QWidget) -> bool:
    """O foco que ``controle`` acaba de receber é o que a janela devolve ao voltar a ser a ativa.

    A razão é `ActiveWindowFocusReason`: o controle que tinha o foco quando ela deixou de ser. O
    pressionar do clique que a reativou chega depois dele.
    """
    razao = _razao_do_foco()
    return (razao is not None and razao.controle is controle
            and razao.razao == Qt.FocusReason.ActiveWindowFocusReason)


def veio_do_teclado(controle: QWidget) -> bool:
    """O foco que ``controle`` acaba de receber é o do Tab ou do Shift+Tab: rola na hora."""
    razao = _razao_do_foco()
    return (razao is not None and razao.controle is controle
            and razao.razao in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason))


def mostrar(rolagem: QScrollArea, controle: QWidget) -> None:
    """Rola ``rolagem`` até ``controle`` ficar inteiro à vista, ou o começo dele quando não cabe.

    Antes, solta a âncora da rolagem (:func:`ancorar`): ela não desfaz o que o seguidor mostra, e a
    folga que ela pôs no alto do conteúdo sai antes da conta.
    """
    conteudo = rolagem.widget()
    if conteudo is None or not conteudo.isAncestorOf(controle):
        return
    soltar_as_ancoras(rolagem)
    alvo = QRect(controle.mapTo(conteudo, QPoint(0, 0)), controle.size())
    vista = rolagem.viewport().size()
    _encaixar(rolagem.verticalScrollBar(), alvo.top(), alvo.top() + alvo.height(), vista.height())
    _encaixar(rolagem.horizontalScrollBar(), alvo.left(), alvo.left() + alvo.width(), vista.width())


class _Ancora(QObject):
    """Mantém um controle no mesmo lugar da vista de uma rolagem até o mouse sossegar.

    Uma por rolagem, feita no primeiro :func:`ancorar` dela e usada de novo a cada clique: ela
    segura um controle (:meth:`segurar`) e o solta (:meth:`soltar`). Enquanto segura, cada vez que o
    controle, ou um dos que o contêm dentro do conteúdo, se move (o que está acima dele mudou de
    altura), e cada vez que o alcance da barra muda (o conteúdo cresceu ou encolheu), a barra anda o
    que o controle andou na vista, e ele volta aonde estava. O conteúdo mesmo não é vigiado: ele se
    move com a rolagem. Quando o que está acima encolhe mais do que a barra pode subir (ela está no
    começo), a diferença vira uma folga no alto do conteúdo, que a âncora tira ao soltar, subindo a
    barra outro tanto quando pode. Ela solta quando o mouse sossega (uma vigia pergunta a
    :func:`mouse_sossegado`), quando a pessoa rola -- a roda, a barra, as teclas da rolagem
    (`actionTriggered`): o que ela rola não é desfeito -- e quando o seguidor mostra um controle
    (:func:`mostrar`).

    **Os sinais ligados uma vez, e nunca desligados.** A primeira versão (o `5f3c581`) fazia uma
    âncora por clique e desligava os sinais da barra ao soltar: o PyQt apaga o intermediário de um
    slot Python desligado com `deleteLater`, e a sonda do crítico que sai por `os._exit` logo depois
    do clique (`clique_linha_c7.py`) passou a mostrar «access violation» na saída, com o apagamento
    pendente (construtor, ciclo 9: 2 de 2 com a âncora, 0 de 2 sem ela; na bisseção do soltar, só
    com os sinais desligados). O produto não sai por `os._exit`, e o laço de eventos apaga o que
    está pendente ao terminar; a âncora não deixa mais nada pendente.
    """

    def __init__(self, rolagem: QScrollArea, barra: QScrollBar) -> None:
        super().__init__(rolagem)
        self._rolagem = rolagem
        self._barra = barra
        self._controle: QWidget | None = None
        self._vigiados: list[QWidget] = []
        self._devolvendo = False
        self._folga = 0
        self._y = 0
        barra.rangeChanged.connect(self._devolver)
        barra.actionTriggered.connect(self._a_pessoa_rolou)
        self._vigia = QTimer(self)
        self._vigia.setInterval(INTERVALO_DA_VIGIA)
        self._vigia.timeout.connect(self._talvez_soltar)

    def segurando(self) -> QWidget | None:
        """O controle que a âncora segura agora, ou None."""
        return self._controle

    def segurar(self, controle: QWidget, vigiados: list[QWidget]) -> None:
        """Segura ``controle`` onde ele está na vista (``vigiados``: ele e os que o contêm)."""
        self.soltar()
        self._controle = controle
        self._vigiados = vigiados
        self._y = self._onde(controle)
        for vigiado in vigiados:
            vigiado.installEventFilter(self)
        self._vigia.start()

    def _onde(self, controle: QWidget) -> int:
        return controle.mapTo(self._rolagem.viewport(), QPoint(0, 0)).y()

    def eventFilter(self, _objeto: QObject | None, evento: QEvent | None) -> bool:  # noqa: N802 - Qt
        if evento is not None and evento.type() == QEvent.Type.Move:
            self._devolver()
        return False

    def _devolver(self, *_alcance: int) -> None:
        controle = self._controle
        if controle is None or self._devolvendo:
            return
        if (sip.isdeleted(self._rolagem) or sip.isdeleted(self._barra) or sip.isdeleted(controle)
                or mouse_sossegado()):
            self.soltar()
            return
        self._devolvendo = True
        try:
            diferenca = self._onde(controle) - self._y
            if diferenca:
                self._barra.setValue(self._barra.value() + diferenca)
            # o que a barra não devolveu: acima, só uma folga no alto do conteúdo (a barra está no
            # começo); abaixo, a folga posta antes encolhe -- ou o alcance novo da barra devolve
            resto = self._onde(controle) - self._y
            if resto < 0:
                self._folgar(-resto)
            elif resto > 0 and self._folga:
                self._folgar(-min(self._folga, resto))
        finally:
            self._devolvendo = False

    def _folgar(self, quanto: int) -> None:
        """Acrescenta ``quanto`` px à folga no alto do conteúdo (tira, se negativo), e já arruma."""
        conteudo = self._rolagem.widget()
        arranjo = conteudo.layout() if conteudo is not None else None
        if arranjo is None:
            return
        margens = arranjo.contentsMargins()
        arranjo.setContentsMargins(margens.left(), margens.top() + quanto, margens.right(),
                                   margens.bottom())
        self._folga += quanto
        arranjo.activate()

    def _a_pessoa_rolou(self, _acao: int) -> None:
        self.soltar()

    def _talvez_soltar(self) -> None:
        if mouse_sossegado():
            self.soltar()

    def soltar(self) -> None:
        """Solta o controle: ele volta a ir com o conteúdo, e a folga sai."""
        if self._controle is None:
            return
        self._controle = None
        self._vigia.stop()
        for vigiado in self._vigiados:
            if not sip.isdeleted(vigiado):
                vigiado.removeEventFilter(self)
        self._vigiados = []
        if self._folga and not sip.isdeleted(self._rolagem) and not sip.isdeleted(self._barra):
            folga = self._folga
            self._folgar(-folga)
            self._barra.setValue(self._barra.value() - folga)


#: A âncora de cada rolagem, pelo endereço dela: o objeto Python da âncora vive enquanto a rolagem
#: vive (sai daqui quando a âncora, filha dela, é destruída).
_ANCORAS: dict[int, _Ancora] = {}


def _endereco(objeto: QObject) -> int:
    """O endereço do objeto C++ de ``objeto``."""
    # o stub do PyQt6 diz que `unwrapinstance` não devolve nada; ele devolve o endereço
    return cast(int, sip.unwrapinstance(objeto))


def _a_ancora_de(rolagem: QScrollArea) -> _Ancora | None:
    """A âncora da ``rolagem``, se ela já tem uma."""
    ancora = _ANCORAS.get(_endereco(rolagem))
    return None if ancora is None or sip.isdeleted(ancora) else ancora


def soltar_as_ancoras(rolagem: QScrollArea) -> None:
    """Solta o controle que a âncora da ``rolagem`` segura, se ela tem uma (:func:`ancorar`)."""
    ancora = _a_ancora_de(rolagem)
    if ancora is not None:
        ancora.soltar()


def ancorar(rolagem: QScrollArea, controle: QWidget) -> None:
    """Mantém ``controle`` no mesmo lugar da vista da ``rolagem`` até o mouse sossegar.

    Para o clique num controle que o painel responde mudando a altura do que está acima dele na
    mesma rolagem: o segundo clique de um duplo clique cai onde o primeiro caiu. Uma âncora por
    rolagem, feita na primeira vez: o controle novo toma o lugar do velho. Um controle fora do
    conteúdo da rolagem não é ancorado.
    """
    conteudo = rolagem.widget()
    barra = rolagem.verticalScrollBar()
    if conteudo is None or barra is None or not conteudo.isAncestorOf(controle):
        return
    vigiados: list[QWidget] = []
    parte: QWidget | None = controle
    while parte is not None and parte is not conteudo:
        vigiados.append(parte)
        parte = parte.parentWidget()
    ancora = _a_ancora_de(rolagem)
    if ancora is None:
        endereco = _endereco(rolagem)
        ancora = _Ancora(rolagem, barra)
        _ANCORAS[endereco] = ancora
        ancora.destroyed.connect(lambda _objeto=None, chave=endereco: _ANCORAS.pop(chave, None))
    ancora.segurar(controle, vigiados)


class RolagemSegueOFoco(QObject):
    """Mostra, na ``rolagem``, todo controle dela que recebe o foco, venha o foco de onde vier."""

    def __init__(self, rolagem: QScrollArea) -> None:
        super().__init__(rolagem)
        self._rolagem = rolagem
        self._ligado = True
        self._pendente: QWidget | None = None
        self._esperando = False
        self._sossego = QTimer(self)
        self._sossego.setSingleShot(True)
        self._sossego.setTimerType(Qt.TimerType.PreciseTimer)
        self._sossego.timeout.connect(self._sossegou)
        aplicacao = QApplication.instance()
        if isinstance(aplicacao, QApplication):
            _razao_do_foco()
            aplicacao.focusChanged.connect(self._foco_mudou)

    @pyqtSlot(QWidget, QWidget)
    def _foco_mudou(self, _antigo: QWidget | None, novo: QWidget | None) -> None:
        # Primeiro se há foco novo e se a rolagem vive: a rolagem destruída com o foco dentro (o
        # diálogo de bases depois da pergunta) limpa o foco no destrutor, quando a rolagem já se
        # foi e este seguidor, filho dela, ainda não.
        if not self._ligado or novo is None or sip.isdeleted(self._rolagem):
            return
        if self._esperando and novo is not self._pendente:
            self._parar_de_esperar()  # o foco que esperava saiu dele
        conteudo = self._rolagem.widget()
        if conteudo is None or not conteudo.isAncestorOf(novo) or veio_do_mouse(novo):
            return
        if not veio_do_teclado(novo) and (voltou_com_a_janela(novo) or not mouse_sossegado()):
            self._esperar_o_sossego(novo)
            return
        mostrar(self._rolagem, novo)

    def _esperar_o_sossego(self, controle: QWidget) -> None:
        """Mostra ``controle`` quando o mouse sossegar, ou na primeira tecla.

        Sossegar é nenhum botão apertado e o intervalo do duplo clique passado desde o último soltar
        (o relógio para no pressionar e recomeça no soltar); a tecla que não é só um modificador o
        mostra antes de chegar a ele. O filtro fica na aplicação só durante a espera.
        """
        self._pendente = controle
        aplicacao = QApplication.instance()
        if not self._esperando and aplicacao is not None:
            aplicacao.installEventFilter(self)
            self._esperando = True
        if no_meio_do_clique():
            self._sossego.stop()  # o soltar arma o relógio
        else:
            self._sossego.start(intervalo_do_duplo_clique())

    def eventFilter(self, objeto: QObject | None, evento: QEvent | None) -> bool:  # noqa: N802 - Qt
        if self._esperando and evento is not None:
            tipo = evento.type()
            if tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                self._sossego.stop()
            elif tipo == QEvent.Type.MouseButtonRelease:
                self._sossego.start(intervalo_do_duplo_clique())
            elif (tipo == QEvent.Type.KeyPress
                  and evento.key() not in _MODIFICADORES):  # type: ignore[attr-defined]
                self._mostrar_o_pendente()
        return super().eventFilter(objeto, evento)

    def _sossegou(self) -> None:
        if not no_meio_do_clique():
            self._mostrar_o_pendente()

    def _parar_de_esperar(self) -> QWidget | None:
        """Tira o filtro e o relógio, e devolve o controle que esperava."""
        self._sossego.stop()
        aplicacao = QApplication.instance()
        if self._esperando and aplicacao is not None:
            aplicacao.removeEventFilter(self)
        self._esperando = False
        controle, self._pendente = self._pendente, None
        return controle

    def _mostrar_o_pendente(self) -> None:
        controle = self._parar_de_esperar()
        if (controle is None or not self._ligado or sip.isdeleted(controle)
                or sip.isdeleted(self._rolagem) or QApplication.focusWidget() is not controle):
            return
        mostrar(self._rolagem, controle)

    def desligar(self) -> None:
        """A rolagem volta a seguir só o foco que anda dentro dela — o antes, para a sabotagem."""
        self._ligado = False
