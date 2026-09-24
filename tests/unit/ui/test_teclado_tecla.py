"""A volta da **tecla** de verdade no portão do teclado (crítico da fase 5, ciclo 4).

A volta da cadeia (`focusNextPrevChild`) dizia «a tabela, o cartão, as ações» na Revisão de texto,
e a tecla `Tab` parava no campo da verdade escrevendo tabulações; de volta, o `Shift+Tab` das ações
punha o foco numa figurina abaixo da dobra do cartão. `teclado._volta_da_tecla` aperta a tecla nos
dois sentidos. Aqui, numa janela pequena com os dois defeitos montados à mão -- a sabotagem do
portão --, ele tem de achar os dois; e, consertados, passar.
"""

from __future__ import annotations

import os

import pytest

PyQt6 = pytest.importorskip("PyQt6", reason="o portão anda por uma janela PyQt6")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _Janela:
    """Um campo de uma linha, um editor que guarda o `Tab`, uma rolagem baixa com seis botões
    empilhados e um botão fora dela -- a forma da Revisão de texto, sem o produto."""

    def __init__(self, app) -> None:
        from PyQt6.QtWidgets import (
            QLineEdit,
            QPlainTextEdit,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
            QWidget,
        )

        self.janela = QWidget()
        coluna = QVBoxLayout(self.janela)
        self.campo = QLineEdit(self.janela)
        self.campo.setAccessibleName("Campo")
        coluna.addWidget(self.campo)
        self.editor = QPlainTextEdit(self.janela)
        self.editor.setAccessibleName("Verdade")
        coluna.addWidget(self.editor)
        self.rolagem = QScrollArea(self.janela)
        self.rolagem.setWidgetResizable(True)
        self.rolagem.setFixedHeight(60)
        dentro = QWidget()
        pilha = QVBoxLayout(dentro)
        self.botoes = []
        for n in range(6):
            botao = QPushButton(f"Figurina {n}", dentro)
            botao.setMinimumHeight(30)
            pilha.addWidget(botao)
            self.botoes.append(botao)
        self.rolagem.setWidget(dentro)
        coluna.addWidget(self.rolagem)
        self.fora = QPushButton("Aceitar", self.janela)
        coluna.addWidget(self.fora)
        self.janela.resize(300, 260)
        self.janela.show()
        app.processEvents()

    def consertar(self) -> None:
        """O conserto da Revisão de texto: o `Tab` sai do editor, e a rolagem segue o foco."""
        from PyQt6.QtCore import QEvent, QObject

        self.editor.setTabChangesFocus(True)
        rolagem = self.rolagem

        class _Segue(QObject):
            def eventFilter(self, obj, event):  # noqa: N802 - assinatura do Qt
                if event.type() == QEvent.Type.FocusIn:
                    rolagem.ensureWidgetVisible(obj)
                return False

        self._segue = _Segue(self.janela)
        for botao in self.botoes:
            botao.installEventFilter(self._segue)


def test_the_key_walk_finds_the_editor_that_keeps_the_tab_and_the_focus_out_of_sight(app):
    from caissa.ui.audit import teclado

    tela = _Janela(app)
    focaveis = teclado._focaveis(tela.janela)
    frente = teclado._volta_da_tecla(tela.janela, focaveis)
    assert frente.empaca_em == "Verdade"
    assert frente.escreve
    assert not frente.passou()
    assert tela.editor.toPlainText() == "", "what the key wrote is undone"
    tras = teclado._volta_da_tecla(tela.janela, focaveis, de_volta=True)
    # from the first control, Shift+Tab goes round to «Aceitar», then into the scroll area from
    # outside: the last figurine takes the focus below the fold
    assert "Figurina 5" in tras.escondidos
    assert not tras.passou()
    tela.janela.close()


def test_each_way_starts_with_the_scroll_areas_at_the_top(app):
    """Crítico da fase 5, ciclo 5: the Shift+Tab walk ran right after the Tab walk, with the scroll
    areas left scrolled down by it -- the focus that enters a scroll area from outside landed on a
    control already in sight, and the gate said PASSOU on the Resultado and the Galeria (0x0 px
    with the area at the top, as the user finds it), and with the fix of cycle 4 undone.  Here the
    editor lets the Tab go and nothing follows the focus: walked the old way (``no_topo=False``,
    after a Tab walk) the hidden figurine is not seen; each way from the top, it is."""
    from caissa.ui.audit import teclado

    tela = _Janela(app)
    tela.editor.setTabChangesFocus(True)
    focaveis = teclado._focaveis(tela.janela)
    teclado._volta_da_tecla(tela.janela, focaveis, no_topo=False)
    cega = teclado._volta_da_tecla(tela.janela, focaveis, de_volta=True, no_topo=False)
    assert cega.escondidos == [], "the old walk: the area left at the bottom by the Tab walk"
    teclado._volta_da_tecla(tela.janela, focaveis)
    atenta = teclado._volta_da_tecla(tela.janela, focaveis, de_volta=True)
    assert "Figurina 5" in atenta.escondidos
    tela.janela.close()


def test_the_gate_clicks_the_controls_half_in_sight_and_the_sabotage_loses_the_click(
        app, monkeypatch):
    """Crítico da fase 5, ciclo 6: the follower scrolled on the click -- Qt gives the focus on the
    *press* -- and the *release* fell outside the control; the gate walked only the key.  It clicks,
    through the ``QWindow``, every control half in sight in a scroll area that follows the focus,
    press and release at the same point, a filter swallowing both (no action runs).  With the guard
    the click stays where it was given; the sabotage ``clique`` (the followers scroll on the mouse's
    focus again) loses it, and the screen fails."""
    import importlib

    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import (
        QCheckBox,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from caissa.ui.audit import teclado
    from caissa.ui.widgets.foco_a_vista import RolagemSegueOFoco

    janela = QWidget()
    coluna = QVBoxLayout(janela)
    rolagem = QScrollArea(janela)
    rolagem.setWidgetResizable(True)
    conteudo = QWidget(rolagem)
    pilha = QVBoxLayout(conteudo)
    for k in range(3):
        pilha.addWidget(QLineEdit(f"campo {k}", conteudo))
    marca = QCheckBox("Esconder incerteza", conteudo)
    pilha.addWidget(marca)
    for k in range(6):
        pilha.addWidget(QLineEdit(f"depois {k}", conteudo))
    rolagem.setWidget(conteudo)
    rolagem.setFixedHeight(60)     # shorter than the content: the content keeps its own height
    coluna.addWidget(rolagem)
    coluna.addWidget(QPushButton("Abrir PDF", janela))
    RolagemSegueOFoco(rolagem)
    janela.resize(360, 400)
    janela.show()
    app.processEvents()
    # the area cuts through the check box: 9 px of it in sight, with the area at the top
    topo = marca.mapTo(conteudo, QPoint(0, 0)).y()
    rolagem.setFixedHeight(topo + 9 + rolagem.height() - rolagem.viewport().height())
    app.processEvents()

    cliques = teclado._cliques_meio_a_vista(janela)
    assert [c["controle"] for c in cliques] == ["Esconder incerteza"], cliques
    assert cliques[0]["no_lugar"]
    assert cliques[0]["rolou_px"] == 0
    assert cliques[0]["a_vista_px"][1] == 9
    assert not marca.isChecked(), "the filter swallows the click: no action runs"
    assert not teclado.Aba(nome="Janela", cliques=cliques).cliques_perdidos()

    for nome in ("caissa.ui.widgets.foco_a_vista", "chess_diagram_ocr.qt.foco_a_vista"):
        try:
            modulo = importlib.import_module(nome)
        except ImportError:
            continue
        for funcao in ("veio_do_mouse", "no_meio_do_clique"):  # undone at teardown
            if hasattr(modulo, funcao):
                monkeypatch.setattr(modulo, funcao, getattr(modulo, funcao))
    monkeypatch.setitem(teclado._PASSADA, "sabotagem", "clique")
    teclado._sabotar(janela)
    cliques = teclado._cliques_meio_a_vista(janela)
    assert cliques, cliques
    assert not cliques[0]["no_lugar"], cliques
    assert cliques[0]["rolou_px"] > 0, cliques
    assert not cliques[0]["soltar_dentro"]
    assert teclado.Aba(nome="Janela", cliques=cliques).cliques_perdidos()
    janela.close()


def _janela_da_lista_e_da_verdade(app):
    """A list at the top of a scroll area that follows the focus, and a text box below the fold: the
    line chosen on the press sends the focus to the box, as the tables of the Rotulagem and of the
    Revisão de texto send it to «Verdade da linha»."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QLineEdit,
        QListWidget,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    from caissa.ui.widgets.foco_a_vista import RolagemSegueOFoco

    janela = QWidget()
    coluna = QVBoxLayout(janela)
    rolagem = QScrollArea(janela)
    rolagem.setWidgetResizable(True)
    conteudo = QWidget(rolagem)
    pilha = QVBoxLayout(conteudo)
    linhas = QListWidget(conteudo)
    linhas.addItems(["linha 1", "linha 2", "linha 3"])
    linhas.setFixedHeight(90)
    pilha.addWidget(linhas)
    for k in range(12):
        pilha.addWidget(QLineEdit(f"campo {k}", conteudo))
    verdade = QTextEdit(conteudo)
    verdade.setFixedHeight(60)
    pilha.addWidget(verdade)
    rolagem.setWidget(conteudo)
    coluna.addWidget(rolagem)
    coluna.addWidget(QPushButton("Abrir PDF", janela))
    RolagemSegueOFoco(rolagem)
    # the panels: the line chosen on the press sends the focus to the truth
    linhas.currentRowChanged.connect(lambda _r: verdade.setFocus(Qt.FocusReason.OtherFocusReason))
    janela.resize(360, 260)
    janela.show()
    for _vez in range(2):
        app.processEvents()
    return janela, rolagem, verdade


def _guardas_desfeitas_no_fim(monkeypatch) -> None:
    """The two followers' guards, as they are, put back at teardown: a sabotage replaces them."""
    import importlib

    for nome in ("caissa.ui.widgets.foco_a_vista", "chess_diagram_ocr.qt.foco_a_vista"):
        try:
            modulo = importlib.import_module(nome)
        except ImportError:
            continue
        for funcao in ("veio_do_mouse", "no_meio_do_clique"):
            if hasattr(modulo, funcao):
                monkeypatch.setattr(modulo, funcao, getattr(modulo, funcao))


def test_the_gate_clicks_a_line_with_the_action_and_finds_the_focus_left_out_of_sight(
        app, monkeypatch):
    """Crítico da fase 5, ciclo 7: a line of the tables of the Rotulagem and of the Revisão de texto
    sends the focus to «Verdade da linha» on the press, and the guard of cycle 7 left the truth out
    of sight -- the gate did not see it: its click swallows the press and the release, and no panel
    moves the focus.  The click with the action: in each item view of the area with two lines or
    more, a click through the ``QWindow`` on a line whole in sight, no filter, and the focus left
    after it has to be whole in the scroll area that follows it.  Here a list at the top of the
    area sends the focus to the text box below the fold: shown after the release, it passes; the
    sabotage ``guarda`` (the guard of cycle 7) leaves it out of sight, and the screen fails."""
    from caissa.ui.audit import teclado

    janela, _rolagem, verdade = _janela_da_lista_e_da_verdade(app)
    cliques = teclado._cliques_com_acao(janela, janela)
    medidos = [c for c in cliques if c["linha"] is not None]
    assert medidos, cliques
    assert all(c["foco"] == teclado._nome_curto(verdade) for c in medidos), medidos
    assert all(c["a_vista"] for c in medidos), medidos
    assert not teclado.Aba(nome="Janela", cliques_com_acao=cliques).focos_escondidos()

    _guardas_desfeitas_no_fim(monkeypatch)
    monkeypatch.setitem(teclado._PASSADA, "sabotagem", "guarda")
    teclado._sabotar(janela)
    cliques = teclado._cliques_com_acao(janela, janela)
    escondidos = teclado.Aba(nome="Janela", cliques_com_acao=cliques).focos_escondidos()
    assert escondidos, cliques
    assert escondidos[0]["a_vista_px"] == [0, 0], escondidos
    janela.close()


def test_the_stale_mark_the_swallowed_clicks_leave_does_not_hide_the_focus(app, monkeypatch):
    """Found by the builder at the gate of cycle 8 (fase 5): the swallowed clicks end with the
    pointer out of the window, and offscreen Qt sends no leave event for that -- «Verdade da linha»,
    hovered before, kept its mark «under the mouse».  The first guard of cycle 8 asked that mark
    (``underMouse``), took the focus the panel sends to the truth on the press of a line for the
    click's own, and left the truth half in sight (17 to 33 of 60 px in the Revisão de texto, in
    Clássica at 1248x640 and 1280x641 and in Fita at 1280x800).  The guard asks the reason of the
    focus: the truth is shown whole.  The sabotage ``ponteiro`` (that first guard) leaves it out of
    sight, and the screen fails."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest

    from caissa.ui.audit import teclado

    janela, rolagem, verdade = _janela_da_lista_e_da_verdade(app)
    alca = janela.windowHandle()

    def marca_velha() -> None:
        barra = rolagem.verticalScrollBar()
        barra.setValue(barra.maximum())
        app.processEvents()
        QTest.mouseMove(alca, verdade.mapTo(janela, QPoint(8, 8)))
        QTest.mouseMove(alca, QPoint(-20, -20))
        app.processEvents()
        assert verdade.underMouse(), "the stale mark"

    marca_velha()
    cliques = teclado._cliques_com_acao(janela, janela)
    medidos = [c for c in cliques if c["linha"] is not None]
    assert medidos, cliques
    assert all(c["a_vista"] for c in medidos), medidos
    assert not teclado.Aba(nome="Janela", cliques_com_acao=cliques).focos_escondidos()

    _guardas_desfeitas_no_fim(monkeypatch)
    monkeypatch.setitem(teclado._PASSADA, "sabotagem", "ponteiro")
    teclado._sabotar(janela)
    marca_velha()
    cliques = teclado._cliques_com_acao(janela, janela)
    escondidos = teclado.Aba(nome="Janela", cliques_com_acao=cliques).focos_escondidos()
    assert escondidos, cliques
    assert escondidos[0]["foco"] == teclado._nome_curto(verdade), escondidos
    janela.close()


def test_the_key_walk_passes_once_the_tab_leaves_the_editor_and_the_scroll_follows(app):
    from caissa.ui.audit import teclado

    tela = _Janela(app)
    tela.consertar()
    focaveis = teclado._focaveis(tela.janela)
    for de_volta in (False, True):
        volta = teclado._volta_da_tecla(tela.janela, focaveis, de_volta=de_volta)
        assert volta.passou(), volta
        assert volta.alcancados == len(focaveis)
    aba = teclado._medir_uma_tela("Janela", tela.janela)
    assert aba.tecla.passou()
    assert aba.tecla_de_volta.passou()
    tela.janela.close()
