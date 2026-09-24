"""A rolagem mostra o controle que recebe o foco, inteiro, venha o foco de onde vier.

O módulo é :mod:`caissa.ui.widgets.foco_a_vista`.

Sem PyQt6 no ambiente os testes pulam.
"""

from __future__ import annotations

import os

import pytest

PyQt6 = pytest.importorskip("PyQt6", reason="o filtro é PyQt6; o .venv da suíte não o tem")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _janela(app):
    """A window 300 px tall: a scroll area of twenty fields and a text box of 48 px (the height of
    «Leitura do motor»), and a button below it -- outside the scroll area."""
    from PyQt6.QtWidgets import QLineEdit, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

    from caissa.ui.widgets.foco_a_vista import RolagemSegueOFoco

    janela = QWidget()
    fora = QVBoxLayout(janela)
    rolagem = QScrollArea(janela)
    rolagem.setWidgetResizable(True)
    conteudo = QWidget(rolagem)
    coluna = QVBoxLayout(conteudo)
    campos = [QLineEdit(f"campo {k}", conteudo) for k in range(20)]
    for campo in campos:
        coluna.addWidget(campo)
    caixa = QTextEdit(conteudo)
    caixa.setPlainText("uma leitura\ncom três\nlinhas")
    caixa.setFixedHeight(48)
    coluna.addWidget(caixa)
    rolagem.setWidget(conteudo)
    fora.addWidget(rolagem, 1)
    botao = QPushButton("Aceitar", janela)
    fora.addWidget(botao)
    segue = RolagemSegueOFoco(rolagem)
    janela.resize(360, 300)
    janela.show()
    app.processEvents()
    return janela, rolagem, conteudo, campos, caixa, botao, segue


def _inteiro(rolagem, controle) -> bool:
    from PyQt6.QtCore import QPoint, QRect

    ret = QRect(controle.mapTo(rolagem.viewport(), QPoint(0, 0)), controle.size())
    return rolagem.viewport().rect().contains(ret)


def test_the_focus_that_comes_from_outside_is_shown_whole(app):
    """Shift+Tab from the button below the scroll area lands on the text box, the last control in
    it: with the area at the top, and with the box's first 20 px in sight -- where the filter of
    cycle 5 (``ensureWidgetVisible``, which shows the cursor and not the box: the cursor was
    already in sight) left it at 20 of 48 px, the «Leitura do motor» of the Fita skin at 1280x641
    at 28 of 48 (crítico da fase 5, ciclo 5).  Shown whole, both times.  A field made after the
    filter is followed too.  The sabotage: the filter off, the box takes the focus below the
    fold."""
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QLineEdit

    janela, rolagem, conteudo, _campos, caixa, botao, segue = _janela(app)
    topo = caixa.mapTo(conteudo, QPoint(0, 0)).y()
    for valor in (0, topo - rolagem.viewport().height() + 20):
        rolagem.verticalScrollBar().setValue(valor)
        botao.setFocus(Qt.FocusReason.TabFocusReason)
        app.processEvents()
        QTest.keyClick(botao, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        app.processEvents()
        assert app.focusWidget() is caixa
        assert _inteiro(rolagem, caixa), valor
    novo = QLineEdit("feito depois", conteudo)
    conteudo.layout().insertWidget(0, novo)
    app.processEvents()
    rolagem.verticalScrollBar().setValue(rolagem.verticalScrollBar().maximum())
    novo.setFocus(Qt.FocusReason.OtherFocusReason)
    app.processEvents()
    assert _inteiro(rolagem, novo), "a control made after the filter is followed too"
    segue.desligar()
    rolagem.verticalScrollBar().setValue(0)
    botao.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    QTest.keyClick(botao, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    app.processEvents()
    assert app.focusWidget() is caixa
    assert caixa.visibleRegion().isEmpty(), "sabotaged: the focus hides below the fold"
    janela.close()


def test_a_click_on_a_control_half_in_sight_counts_where_it_was_given(app, monkeypatch):
    """Qt gives the focus on the *press* of a click, before the event is delivered; the follower
    scrolled there, and the *release* fell outside the control -- 15 of 15 clicks of the critic on
    controls half in sight, the Galeria's «Gravar» among them (fase 5, ciclo 6).  A check box with
    9 px in sight, clicked next to the cut through the ``QWindow`` (press and release at the same
    point of the window, as a mouse held still): it is checked and nothing scrolls; the keyboard
    still brings a control into sight.  The sabotage: the follower scrolls on the mouse's focus
    too, the box moves up and the click is lost."""
    from PyQt6.QtCore import QPoint, QRect, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QCheckBox

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, conteudo, _campos, caixa, botao, _segue = _janela(app)
    marca = QCheckBox("Esconder incerteza", conteudo)
    conteudo.layout().insertWidget(19, marca)
    app.processEvents()

    def clicar_junto_do_corte() -> tuple[int, int]:
        marca.setChecked(False)
        botao.setFocus(Qt.FocusReason.OtherFocusReason)
        topo = marca.mapTo(conteudo, QPoint(0, 0)).y()
        rolagem.verticalScrollBar().setValue(topo + 9 - rolagem.viewport().height())
        app.processEvents()
        visivel = QRect(marca.mapTo(rolagem.viewport(), QPoint(0, 0)), marca.size())
        assert visivel.intersected(rolagem.viewport().rect()).height() == 9
        antes = rolagem.verticalScrollBar().value()
        ponto = marca.mapTo(janela, QPoint(8, 6))
        alca = janela.windowHandle()
        QTest.mousePress(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        app.processEvents()
        QTest.mouseRelease(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        app.processEvents()
        return antes, rolagem.verticalScrollBar().value()

    antes, depois = clicar_junto_do_corte()
    assert depois == antes, "the click does not scroll"
    assert marca.isChecked()
    assert app.focusWidget() is marca
    rolagem.verticalScrollBar().setValue(0)
    botao.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    QTest.keyClick(botao, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    app.processEvents()
    assert app.focusWidget() is caixa, "the keyboard is still followed"
    assert _inteiro(rolagem, caixa), "the keyboard is still followed"

    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda _controle: False)
    antes, depois = clicar_junto_do_corte()
    assert depois != antes, "sabotaged: the click is lost"
    assert not marca.isChecked(), "sabotaged: the click is lost"
    janela.close()


def test_the_pointer_held_still_is_not_the_mouse_but_the_wheel_is(app, monkeypatch):
    """The mouse's guard is the press and the wheel, and not the pointer: the Tab that lands on a
    button under the pointer held still, with 9 px of it in sight, shows it whole, as any other --
    a guard that took every control under the pointer for the mouse's focus left it at 9 px.  A
    combo box, which takes the focus from the wheel, focused by the mouse while under the pointer
    (a wheel event cannot be made from Python; the focus is the one the wheel gives): nothing
    scrolls, and the wheel goes on over it.  The sabotages: the pointer alone counts as the mouse
    (the button stays at 9 px); no guard at all (the combo box jumps under the wheel)."""
    from PyQt6.QtCore import QPoint, QRect, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QComboBox, QPushButton

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, conteudo, _campos, _caixa, _botao, _segue = _janela(app)
    gravar = QPushButton("Gravar", conteudo)
    conteudo.layout().insertWidget(19, gravar)
    pele = QComboBox(conteudo)
    pele.addItems(["Foco", "Fita", "Clássica"])
    conteudo.layout().insertWidget(10, pele)
    for _vez in range(2):       # the layout grows the content, then the scroll area takes it
        app.processEvents()

    def nove_px_sob_o_ponteiro(controle) -> int:
        """The control with its first 9 px in sight, and the pointer on them, held still."""
        topo = controle.mapTo(conteudo, QPoint(0, 0)).y()
        rolagem.verticalScrollBar().setValue(topo + 9 - rolagem.viewport().height())
        app.processEvents()
        visivel = QRect(controle.mapTo(rolagem.viewport(), QPoint(0, 0)), controle.size())
        assert visivel.intersected(rolagem.viewport().rect()).height() == 9
        # off the control first: the two controls take turns at the same spot of the window
        QTest.mouseMove(janela.windowHandle(), QPoint(2, 2))
        QTest.mouseMove(janela.windowHandle(), controle.mapTo(janela, QPoint(8, 4)))
        app.processEvents()
        assert controle.underMouse()
        assert QApplication.mouseButtons() == Qt.MouseButton.NoButton
        return rolagem.verticalScrollBar().value()

    def tab_ate_o_botao() -> None:
        anterior = gravar.previousInFocusChain()
        anterior.setFocus(Qt.FocusReason.OtherFocusReason)
        nove_px_sob_o_ponteiro(gravar)
        QTest.keyClick(anterior, Qt.Key.Key_Tab)
        app.processEvents()
        assert app.focusWidget() is gravar

    tab_ate_o_botao()
    assert _inteiro(rolagem, gravar), "the Tab under the pointer held still shows the button whole"
    antes = nove_px_sob_o_ponteiro(pele)
    pele.setFocus(Qt.FocusReason.MouseFocusReason)
    app.processEvents()
    assert app.focusWidget() is pele
    assert rolagem.verticalScrollBar().value() == antes, "the wheel's focus does not scroll"

    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda controle: controle.underMouse())
    tab_ate_o_botao()
    assert not _inteiro(rolagem, gravar), "sabotaged: the pointer alone holds the button at 9 px"
    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda _controle: False)
    antes = nove_px_sob_o_ponteiro(pele)
    pele.setFocus(Qt.FocusReason.MouseFocusReason)
    app.processEvents()
    assert rolagem.verticalScrollBar().value() != antes, "sabotaged: the combo box jumps"
    janela.close()


def test_a_control_taller_than_the_view_shows_its_top(app):
    """A control taller than the view cannot be shown whole: its top is, and not its middle."""
    from PyQt6.QtCore import QPoint

    janela, rolagem, _conteudo, campos, caixa, _botao, _segue = _janela(app)
    caixa.setFixedHeight(900)
    app.processEvents()
    rolagem.verticalScrollBar().setValue(0)
    campos[0].setFocus()
    app.processEvents()
    caixa.setFocus()
    app.processEvents()
    topo = caixa.mapTo(rolagem.viewport(), QPoint(0, 0)).y()
    assert 0 <= topo <= 10, topo
    janela.close()
