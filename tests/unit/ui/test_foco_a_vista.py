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
