"""The deciding button takes one click per double click (`caissa.ui.widgets.um_clique`).

Crítico da fase 5, ciclo 9 (não bloqueante 2): «Aceitar leitura» decided the current line and the
next one in a double click.  What reaches the button in a double click through the platform's path
(`QTest.mouseDClick` on the ``QWindow`` goes through the `QGuiApplication` and the
`QWidgetWindow`): press, release, `MouseButtonDblClick`, release -- the second press is marked as a
double click and kept by the window (QTBUG-25831), and the button takes the double click for a
press (`QWidget.mouseDoubleClickEvent`), so the release clicks again.  The filter swallows the
double click; and lifts the button when a press delivered by hand before the double click pushed
it down (a probe: the critic's of cycles 8 and 9, and the keyboard gate's up to cycle 10).
"""

from __future__ import annotations

import os

import pytest

PyQt6 = pytest.importorskip("PyQt6", reason="um botão PyQt6")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _Anota:
    """What reaches the button, and how many times it clicked."""

    def __init__(self, botao) -> None:
        from PyQt6.QtCore import QEvent, QObject

        nomes = {
            QEvent.Type.MouseButtonPress: "pressionar",
            QEvent.Type.MouseButtonRelease: "soltar",
            QEvent.Type.MouseButtonDblClick: "duplo",
        }
        eventos: list[str] = []

        class _Filtro(QObject):
            def eventFilter(self, _objeto, evento):  # noqa: N802 - Qt
                if evento is not None and evento.type() in nomes:
                    eventos.append(nomes[evento.type()])
                return False

        self.eventos = eventos
        self.cliques = 0
        self._filtro = _Filtro()
        botao.installEventFilter(self._filtro)
        botao.clicked.connect(self._clicou)

    def _clicou(self) -> None:
        self.cliques += 1


def _janela(app, *, com_o_filtro: bool):
    from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from caissa.ui.widgets.um_clique import um_clique_por_vez

    janela = QWidget()
    arranjo = QVBoxLayout(janela)
    botao = QPushButton("Aceitar leitura")
    arranjo.addWidget(botao)
    janela.resize(300, 80)
    if com_o_filtro:
        janela.um_clique = um_clique_por_vez(janela, botao)
    anota = _Anota(botao)  # after the product's filter: Qt asks the last one installed first
    janela.show()
    for _vez in range(3):
        app.processEvents()
    return janela, botao, anota


def _duplo_clique_da_plataforma(app, janela, botao) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    ponto = botao.mapTo(janela, botao.rect().center())
    QTest.mouseDClick(janela.windowHandle(), Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier, ponto)
    for _vez in range(3):
        app.processEvents()


def _duplo_clique_de_uma_sonda(app, janela, botao) -> None:
    """The critic's probe (cycles 8 and 9): the second press delivered to the button too."""
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    alca = janela.windowHandle()
    ponto = botao.mapTo(janela, botao.rect().center())
    esquerdo, nenhum = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    QTest.mouseClick(alca, esquerdo, nenhum, ponto)
    QTest.mousePress(alca, esquerdo, nenhum, ponto)
    centro = botao.rect().center()
    duplo = QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(centro),
                        QPointF(botao.mapToGlobal(centro)), esquerdo, esquerdo, nenhum)
    QApplication.sendEvent(botao, duplo)
    QTest.mouseRelease(alca, esquerdo, nenhum, ponto)
    for _vez in range(3):
        app.processEvents()


def test_the_platforms_double_click_clicks_a_deciding_button_once(app):
    """Through the platform's path the button gets press, release, double click, release -- no
    second press -- and clicks once; without the filter (the sabotage) the double click is taken
    for a press, and the button clicks twice."""
    janela, botao, anota = _janela(app, com_o_filtro=True)
    _duplo_clique_da_plataforma(app, janela, botao)
    assert anota.eventos == ["pressionar", "soltar", "duplo", "soltar"], anota.eventos
    assert anota.cliques == 1, "the double click clicks once"
    janela.close()

    janela, botao, anota = _janela(app, com_o_filtro=False)
    _duplo_clique_da_plataforma(app, janela, botao)
    assert anota.eventos == ["pressionar", "soltar", "duplo", "soltar"], anota.eventos
    assert anota.cliques == 2, "sabotaged: the double click clicks twice"
    janela.close()


def test_a_probes_double_click_with_the_second_press_clicks_once(app, monkeypatch):
    """A probe that delivers the second press to the button too (press, release, press, double
    click, release): the press pushes the button down, and the filter lifts it -- one click.  The
    sabotage: the filter that only swallows the double click (no ``setDown(False)``) -- two."""
    from PyQt6.QtCore import QEvent

    from caissa.ui.widgets import um_clique

    janela, botao, anota = _janela(app, com_o_filtro=True)
    _duplo_clique_de_uma_sonda(app, janela, botao)
    assert anota.eventos == ["pressionar", "soltar", "pressionar", "duplo", "soltar"], (
        anota.eventos)
    assert anota.cliques == 1, "the probe's double click clicks once"
    janela.close()

    def so_engole(_self, _objeto, evento):
        return evento is not None and evento.type() == QEvent.Type.MouseButtonDblClick

    monkeypatch.setattr(um_clique._UmCliquePorVez, "eventFilter", so_engole)
    janela, botao, anota = _janela(app, com_o_filtro=True)
    _duplo_clique_de_uma_sonda(app, janela, botao)
    assert anota.cliques == 2, "sabotaged: the button the press pushed down clicks on the release"
    janela.close()


def test_two_clicks_past_the_double_click_interval_click_twice(app):
    """Two clicks the double-click interval apart are two decisions: the filter changes nothing
    (`QTest` puts the double-click interval between two clicks of its own)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    janela, botao, anota = _janela(app, com_o_filtro=True)
    ponto = botao.mapTo(janela, botao.rect().center())
    for _vez in range(2):
        QTest.mouseClick(janela.windowHandle(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, ponto)
        app.processEvents()
    assert "duplo" not in anota.eventos, anota.eventos
    assert anota.cliques == 2
    janela.close()
