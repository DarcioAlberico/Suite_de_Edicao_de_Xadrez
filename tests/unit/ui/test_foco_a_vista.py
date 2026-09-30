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


@pytest.fixture(autouse=True)
def _mouse_sossegado(app):
    """Each test starts with the mouse calm: the last release of the test before, which the
    application-wide recorder keeps, does not make the focus of the next one wait."""
    from caissa.ui.widgets import foco_a_vista

    razao = foco_a_vista._razao_do_foco()
    if razao is not None:
        razao.soltou_em = float("-inf")


def _sossegar(app) -> None:
    """The mouse left calm: the double-click interval and a little more, the event loop running."""
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    QTest.qWait(QApplication.styleHints().mouseDoubleClickInterval() + 100)
    app.processEvents()


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

    # the sabotage of cycle 6: the follower scrolls on the press itself
    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda _controle: False)
    monkeypatch.setattr(foco_a_vista, "no_meio_do_clique", lambda: False)
    monkeypatch.setattr(foco_a_vista, "mouse_sossegado", lambda: True)
    antes, depois = clicar_junto_do_corte()
    assert depois != antes, "sabotaged: the click is lost"
    assert not marca.isChecked(), "sabotaged: the click is lost"
    janela.close()


def test_the_program_s_focus_in_a_click_is_shown_when_the_mouse_is_calm(app, monkeypatch):
    """Crítico da fase 5, ciclo 7: a row of the tables of the Rotulagem and of the Revisão de texto
    sends the focus to «Verdade da linha» on the *press* of the click, and the guard of cycle 7 (a
    button is down) took that focus for the mouse's -- the truth stayed out of sight (0x0 px at
    1280x641), and what was typed went there.  Here a list at the top of the scroll area sends the
    focus to the text box at the bottom when its row changes, on the press: the click ends where it
    was given (the row is clicked once), and once the mouse is calm (the double-click interval
    after the release) the box is shown whole, and the typing goes into it.  The sabotages: the
    guard of cycle 7 (the box stays hidden); the follower of cycle 6, which scrolled on the press
    (the list moves away and the click is lost)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QListWidget

    from caissa.ui.audit import teclado
    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, conteudo, _campos, caixa, botao, _segue = _janela(app)
    linhas = QListWidget(conteudo)
    linhas.addItems(["linha 1", "linha 2", "linha 3"])
    linhas.setFixedHeight(90)
    conteudo.layout().insertWidget(0, linhas)
    # the panels: the row chosen on the press sends the focus to the truth
    linhas.currentRowChanged.connect(lambda _r: caixa.setFocus(Qt.FocusReason.OtherFocusReason))
    clicado: list[int] = []
    linhas.clicked.connect(lambda indice: clicado.append(indice.row()))
    for _vez in range(2):
        app.processEvents()

    def clicar_a_linha() -> None:
        clicado.clear()
        linhas.setCurrentRow(0)
        caixa.setPlainText("uma leitura")
        rolagem.verticalScrollBar().setValue(0)
        botao.setFocus(Qt.FocusReason.OtherFocusReason)
        app.processEvents()
        assert caixa.visibleRegion().isEmpty(), "the box starts below the fold"
        alvo = linhas.visualItemRect(linhas.item(1))
        ponto = linhas.viewport().mapTo(janela, alvo.center())
        alca = janela.windowHandle()
        QTest.mousePress(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        app.processEvents()
        QTest.mouseRelease(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        _sossegar(app)  # the release, then the double-click interval, then the scroll
        vista.append(_inteiro(rolagem, caixa))
        QTest.keyClicks(app.focusWidget(), "XYZ")
        app.processEvents()

    vista: list[bool] = []
    clicar_a_linha()
    assert clicado == [1], "the click ends where it was given"
    assert linhas.currentRow() == 1
    assert app.focusWidget() is caixa
    assert vista == [True], "the focus the program moved is shown once the mouse is calm"
    assert "XYZ" in caixa.toPlainText(), "and the typing goes where the eyes are"

    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", teclado._guarda_do_ciclo_7)
    clicar_a_linha()
    assert app.focusWidget() is caixa
    assert caixa.visibleRegion().isEmpty(), "sabotaged (cycle 7): the focus stays out of sight"

    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda _controle: False)
    monkeypatch.setattr(foco_a_vista, "no_meio_do_clique", lambda: False)
    monkeypatch.setattr(foco_a_vista, "mouse_sossegado", lambda: True)
    clicar_a_linha()
    assert clicado == [], "sabotaged (cycle 6): the scroll on the press loses the click"
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


def test_a_control_that_only_just_fits_is_shown_whole(app, monkeypatch):
    """A control 1 px shorter than the view fits it, but not with the margin around it: it is shown
    whole, with less margin -- the «Verdade da linha» of the Rotulagem is 549 px in a view of 550,
    and the whole margin left 3 px of it cut (crítico da fase 5, ciclo 7: «546 à vista»).  The
    sabotage: the fit of cycle 7, which showed its start with the margin, and cut its end."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, _conteudo, _campos, caixa, botao, _segue = _janela(app)
    caixa.setFixedHeight(rolagem.viewport().height() - 1)
    for _vez in range(2):
        app.processEvents()

    def de_volta_do_botao() -> bool:
        rolagem.verticalScrollBar().setValue(0)
        botao.setFocus(Qt.FocusReason.TabFocusReason)
        app.processEvents()
        QTest.keyClick(botao, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        app.processEvents()
        assert app.focusWidget() is caixa
        return _inteiro(rolagem, caixa)

    assert de_volta_do_botao(), "a control that fits is shown whole"

    def encaixe_do_ciclo_7(barra, inicio, fim, vista):
        atual = barra.value()
        if fim - inicio + 2 * foco_a_vista.FOLGA > vista or inicio - foco_a_vista.FOLGA < atual:
            alvo = inicio - foco_a_vista.FOLGA
        elif fim + foco_a_vista.FOLGA > atual + vista:
            alvo = fim + foco_a_vista.FOLGA - vista
        else:
            return
        barra.setValue(max(barra.minimum(), min(barra.maximum(), alvo)))

    monkeypatch.setattr(foco_a_vista, "_encaixar", encaixe_do_ciclo_7)
    assert not de_volta_do_botao(), "sabotaged: the margin cuts its end"
    janela.close()


def test_the_focus_the_program_moves_is_not_the_mouse_s_under_a_stale_mark(app, monkeypatch):
    """Found by the builder with the gate's click that lets the action run (fase 5, ciclo 8):
    after a click on the text box -- the gate's swallowed click on «Verdade da linha» -- the pointer
    left the window, and offscreen Qt sends no leave event for that: the box kept its mark «under
    the mouse».  The next click on a line of the list sends the focus to the box on the press, and
    the guard that asked the box's ``underMouse`` took that focus for the click's own: the box
    stayed half in sight.  The guard asks the reason of the focus (the program's ``setFocus()`` is
    not the mouse's): the box is shown whole after the release.  The sabotage: the guard of the
    pointer, the first version of cycle 8 (the gate's ``ponteiro``) -- the box stays hidden."""
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QListWidget

    from caissa.ui.audit import teclado
    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, conteudo, _campos, caixa, botao, _segue = _janela(app)
    linhas = QListWidget(conteudo)
    linhas.addItems(["linha 1", "linha 2", "linha 3"])
    linhas.setFixedHeight(90)
    conteudo.layout().insertWidget(0, linhas)
    linhas.currentRowChanged.connect(lambda _r: caixa.setFocus(Qt.FocusReason.OtherFocusReason))
    for _vez in range(2):
        app.processEvents()
    alca = janela.windowHandle()

    def clicar_a_linha_com_a_marca_velha() -> None:
        # the pointer over the box, then out of the window: no leave event offscreen
        rolagem.verticalScrollBar().setValue(rolagem.verticalScrollBar().maximum())
        app.processEvents()
        QTest.mouseMove(alca, caixa.mapTo(janela, QPoint(8, 8)))
        QTest.mouseMove(alca, QPoint(-20, -20))
        app.processEvents()
        assert caixa.underMouse(), "the stale mark the gate leaves"
        linhas.setCurrentRow(0)
        rolagem.verticalScrollBar().setValue(0)
        botao.setFocus(Qt.FocusReason.OtherFocusReason)
        app.processEvents()
        ponto = linhas.viewport().mapTo(janela, linhas.visualItemRect(linhas.item(1)).center())
        QTest.mousePress(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        app.processEvents()
        QTest.mouseRelease(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        _sossegar(app)
        assert app.focusWidget() is caixa

    clicar_a_linha_com_a_marca_velha()
    assert _inteiro(rolagem, caixa), "the program's focus is shown once the mouse is calm"
    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", teclado._guarda_do_ponteiro)
    clicar_a_linha_com_a_marca_velha()
    assert not _inteiro(rolagem, caixa), "sabotaged: the stale mark hides the program's focus"
    janela.close()


def test_the_tab_onto_a_combo_box_under_the_pointer_held_still_scrolls_to_it(app, monkeypatch):
    """The Tab from the button outside the scroll area onto a combo box under the pointer held
    still, with 9 px of it in sight: the reason of the focus is the Tab's, and the box is shown
    whole -- the guard that asked the pointer could not tell the Tab from the wheel there, and left
    the box at 9 px (cycle 7, the first version of cycle 8).  The Tab inside the area goes through
    the area's own ``focusNextPrevChild``, which calls ``ensureWidgetVisible``: the Tab here comes
    from outside.  The sabotage: the guard of the pointer (the gate's ``ponteiro``)."""
    from PyQt6.QtCore import QPoint, QRect, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QComboBox

    from caissa.ui.audit import teclado
    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, conteudo, _campos, _caixa, botao, _segue = _janela(app)
    pele = QComboBox(conteudo)
    pele.addItems(["Foco", "Fita", "Clássica"])
    conteudo.layout().insertWidget(12, pele)
    type(janela).setTabOrder(botao, pele)
    for _vez in range(2):
        app.processEvents()
    alca = janela.windowHandle()

    def tab_de_fora_ate_a_caixa_sob_o_ponteiro() -> int:
        botao.setFocus(Qt.FocusReason.OtherFocusReason)
        app.processEvents()
        topo = pele.mapTo(conteudo, QPoint(0, 0)).y()
        rolagem.verticalScrollBar().setValue(topo + 9 - rolagem.viewport().height())
        app.processEvents()
        QTest.mouseMove(alca, QPoint(2, 2))
        QTest.mouseMove(alca, pele.mapTo(janela, QPoint(8, 4)))
        app.processEvents()
        assert pele.underMouse()
        QTest.keyClick(botao, Qt.Key.Key_Tab)
        app.processEvents()
        assert app.focusWidget() is pele
        visivel = QRect(pele.mapTo(rolagem.viewport(), QPoint(0, 0)), pele.size())
        return visivel.intersected(rolagem.viewport().rect()).height()

    assert tab_de_fora_ate_a_caixa_sob_o_ponteiro() == pele.height(), "the Tab shows it whole"
    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", teclado._guarda_do_ponteiro)
    assert tab_de_fora_ate_a_caixa_sob_o_ponteiro() == 9, "sabotaged: the Tab leaves it at 9 px"
    janela.close()


def _janela_com_a_vista_longe_do_foco(app):
    """The window of `_janela` with an «Aceitar» at the end of the scroll area, and a helper that
    gives the focus to the first field and takes the view to the end, as the wheel does: the focus
    stays on the field, out of sight."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton

    janela, rolagem, conteudo, campos, _caixa, _botao, _segue = _janela(app)
    aceitar = QPushButton("Aceitar embaixo", conteudo)
    conteudo.layout().addWidget(aceitar)
    for _vez in range(2):
        app.processEvents()
    barra = rolagem.verticalScrollBar()

    def a_roda_leva_a_vista_ao_fim() -> None:
        campos[0].setFocus(Qt.FocusReason.TabFocusReason)
        app.processEvents()
        barra.setValue(barra.maximum())
        app.processEvents()
        assert campos[0].visibleRegion().isEmpty()

    return janela, rolagem, campos[0], aceitar, a_roda_leva_a_vista_ao_fim


def test_the_focus_given_back_on_return_waits_for_the_click_that_brought_the_window_back(
        app, monkeypatch):
    """Found by the builder in cycle 8 (fase 5): when the window becomes the active one again, Qt
    gives the focus back to the control that had it (``ActiveWindowFocusReason``), and Windows
    activates the window before it delivers the press of the click that brought it back.  With the
    view taken far from that control by the wheel, the follower scrolled to it, and the press fell
    somewhere else (the probe ``c8/sonda_ativacao.py``: the scroll from 242 to 3, «Aceitar» without
    the click).  Here the focus of the return and the press come one right after the other, with no
    event loop between them, as on Windows (offscreen ``activateWindow`` is queued, and ``QTest``
    would deliver the press before it): the button gets the click, and nothing scrolls -- the focus
    of the return waits the double-click interval, and the click took the focus away from it.  The
    sabotage: the focus of the return shown at once, and the click is lost."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, primeiro, aceitar, a_roda_leva_a_vista_ao_fim = (
        _janela_com_a_vista_longe_do_foco(app))
    clicados: list[bool] = []
    aceitar.clicked.connect(lambda: clicados.append(True))
    barra = rolagem.verticalScrollBar()
    alca = janela.windowHandle()

    def a_volta_com_um_clique() -> tuple[int, int]:
        clicados.clear()
        a_roda_leva_a_vista_ao_fim()
        antes = barra.value()
        ponto = aceitar.mapTo(janela, aceitar.rect().center())
        primeiro.clearFocus()  # the window stopped being the active one
        app.processEvents()
        primeiro.setFocus(Qt.FocusReason.ActiveWindowFocusReason)  # the window came back
        QTest.mousePress(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        app.processEvents()
        QTest.mouseRelease(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
        _sossegar(app)
        return antes, barra.value()

    antes, depois = a_volta_com_um_clique()
    assert clicados == [True], "the click that brought the window back counts where it was given"
    assert depois == antes, "nothing scrolls under the pointer"
    assert app.focusWidget() is aceitar

    monkeypatch.setattr(foco_a_vista, "voltou_com_a_janela", lambda _controle: False)
    monkeypatch.setattr(foco_a_vista, "mouse_sossegado", lambda: True)
    antes, depois = a_volta_com_um_clique()
    assert clicados == [], "sabotaged: the click that brought the window back is lost"
    assert depois != antes, "sabotaged: the view scrolls under the pointer"
    janela.close()


def test_the_focus_given_back_on_return_with_no_click_is_shown(app, monkeypatch):
    """The window really activated again (``activateWindow``, after another window was the active
    one), with no click -- the Alt+Tab, the dialog that closed: the focus the window gives back is
    shown whole once the double-click interval passed, as any focus the keyboard sees.  The
    sabotage: the wait that never shows anything, and the field stays out of sight."""
    from PyQt6.QtWidgets import QApplication, QWidget

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, primeiro, _aceitar, a_roda_leva_a_vista_ao_fim = (
        _janela_com_a_vista_longe_do_foco(app))
    outra = QWidget()
    outra.resize(120, 80)
    outra.show()

    def a_volta_sem_clique() -> None:
        a_roda_leva_a_vista_ao_fim()
        outra.activateWindow()
        for _vez in range(3):
            app.processEvents()
        assert QApplication.activeWindow() is not janela
        janela.activateWindow()
        _sossegar(app)
        assert app.focusWidget() is primeiro, "the window gives the focus back to the first field"

    a_volta_sem_clique()
    assert _inteiro(rolagem, primeiro), "with no click, the focus of the return is shown"
    monkeypatch.setattr(foco_a_vista.RolagemSegueOFoco, "_mostrar_o_pendente", lambda _self: None)
    a_volta_sem_clique()
    assert primeiro.visibleRegion().isEmpty(), "sabotaged: the focus of the return stays hidden"
    outra.close()
    janela.close()


def _janela_da_lista(app):
    """The window of `_janela` with a list of three lines at the top of the scroll area, whose line
    chosen on the press sends the focus to the text box at the bottom -- the tables of the
    Rotulagem and of the Revisão de texto and «Verdade da linha».  The fields are named, to say
    where a click fell."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QListWidget

    janela, rolagem, conteudo, campos, caixa, botao, _segue = _janela(app)
    for k, campo in enumerate(campos):
        campo.setObjectName(f"campo {k}")
    linhas = QListWidget(conteudo)
    linhas.addItems(["linha 1", "linha 2", "linha 3"])
    linhas.setFixedHeight(90)
    conteudo.layout().insertWidget(0, linhas)
    linhas.currentRowChanged.connect(lambda _r: caixa.setFocus(Qt.FocusReason.OtherFocusReason))
    for _vez in range(2):
        app.processEvents()
    return janela, rolagem, linhas, caixa, botao


def _na_linha(app, janela, rolagem, linhas, botao):
    """The list on its first line, the scroll area at the top, the focus outside: a point on the
    second line, in the window."""
    from PyQt6.QtCore import Qt

    linhas.setCurrentRow(0)
    rolagem.verticalScrollBar().setValue(0)
    botao.setFocus(Qt.FocusReason.OtherFocusReason)
    app.processEvents()
    return linhas.viewport().mapTo(janela, linhas.visualItemRect(linhas.item(1)).center())


def _clique(app, alca, ponto) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    QTest.mousePress(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    app.processEvents()
    QTest.mouseRelease(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    app.processEvents()


def _segundo_clique_de_um_duplo(app, janela, alca, ponto) -> None:
    """The second click of a double click as the platform delivers it to the widget
    (`teclado._segundo_clique`): the press goes to the window, which keeps it from the widget, and
    the double click and the release go to the widget under the pointer.  Up to cycle 10 the press
    reached the widget too, as the critic's probe of cycle 8 sent it."""
    from caissa.ui.audit import teclado

    assert alca is janela.windowHandle()
    teclado._segundo_clique(janela, ponto)
    app.processEvents()


def test_the_second_click_of_a_double_click_lands_where_the_first_did(app, monkeypatch):
    """Crítico da fase 5, ciclo 8: the scroll that showed the focus the program moved in the click
    came right after the release, and moved the content under the pointer held still before the
    second click of a double click -- in the Rotulagem, with the scroll area at its end, the second
    click on line 4 fell on «Aceitar leitura» and accepted a reading nobody accepted.  Here the
    double click through the ``QWindow`` on the second line of the list (press, release, 80 ms, the
    second click at the same point, as the platform delivers it: the double click and the release):
    nothing moves under the pointer between the two clicks, both land on the list, which gets the
    double click on that line -- and sends the focus
    to the box, as the Rotulagem's double click on a line does (``table.activated``); once the
    mouse is calm the box is whole.  The sabotage: the scroll right after the release (the
    double-click interval at 0) -- the content moves, and the second click falls off the list."""
    from PyQt6.QtCore import QEvent, QObject, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QWidget

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, linhas, caixa, botao = _janela_da_lista(app)
    duplos: list[int] = []
    linhas.doubleClicked.connect(lambda indice: duplos.append(indice.row()))
    linhas.doubleClicked.connect(lambda _i: caixa.setFocus(Qt.FocusReason.OtherFocusReason))
    alca = janela.windowHandle()

    class Receptores(QObject):
        """The first widget each click of the double click is delivered to: the press of the
        first, the double click of the second."""

        def __init__(self) -> None:
            super().__init__()
            self.controles: list[QWidget] = []
            self._visto = False

        def eventFilter(self, objeto, evento):  # noqa: N802 - Qt
            tipo = evento.type()
            if (tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
                    and isinstance(objeto, QWidget)):
                if not self._visto:
                    self.controles.append(objeto)
                    self._visto = True
            elif tipo == QEvent.Type.MouseButtonRelease:
                self._visto = False
            return False

    receptores = Receptores()
    app.installEventFilter(receptores)

    def duplo_clique() -> tuple[object, object]:
        duplos.clear()
        receptores.controles.clear()
        ponto = _na_linha(app, janela, rolagem, linhas, botao)
        assert caixa.visibleRegion().isEmpty(), "the box starts below the fold"
        sob = janela.childAt(ponto)
        _clique(app, alca, ponto)
        QTest.qWait(80)  # the time between the two clicks of a double click
        sob_no_segundo = janela.childAt(ponto)
        _segundo_clique_de_um_duplo(app, janela, alca, ponto)
        _sossegar(app)
        return sob, sob_no_segundo

    sob, sob_no_segundo = duplo_clique()
    assert sob_no_segundo is sob, "nothing moves under the pointer between the two clicks"
    assert receptores.controles == [linhas.viewport()] * 2, "both clicks land on the list"
    assert duplos == [1], "the list gets the double click on its second line"
    assert _inteiro(rolagem, caixa), "and once the mouse is calm the box is whole"

    monkeypatch.setattr(foco_a_vista, "intervalo_do_duplo_clique", lambda: 0)
    sob, sob_no_segundo = duplo_clique()
    assert sob_no_segundo is not sob, "sabotaged: the content moved under the pointer"
    assert duplos == [], "sabotaged: the list does not get the double click"
    assert receptores.controles[0] is linhas.viewport()
    assert receptores.controles[1] is not linhas.viewport(), "sabotaged: the second click is off it"
    app.removeEventFilter(receptores)
    janela.close()


def test_a_key_shows_the_waiting_focus_at_once_and_goes_into_it(app, monkeypatch):
    """The focus the program moved in the click waits for the mouse to be calm -- or for the first
    key: someone who clicks the line and types at once sees the box before the letter reaches it,
    and the letter goes into the box in sight.  A modifier alone (Shift before a Shift+click) does
    not show it.  The sabotage: every key taken for a modifier -- the box stays below the fold
    while the letter goes into it."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, linhas, caixa, botao = _janela_da_lista(app)
    alca = janela.windowHandle()

    def clique_e_tecla() -> tuple[bool, bool, bool]:
        caixa.setPlainText("")
        ponto = _na_linha(app, janela, rolagem, linhas, botao)
        _clique(app, alca, ponto)
        assert app.focusWidget() is caixa
        QTest.keyClick(caixa, Qt.Key.Key_Shift)
        app.processEvents()
        so_o_modificador = caixa.visibleRegion().isEmpty()
        QTest.keyClicks(caixa, "X")
        app.processEvents()
        return so_o_modificador, _inteiro(rolagem, caixa), caixa.toPlainText() == "X"

    so_o_modificador, inteira, digitado = clique_e_tecla()
    assert so_o_modificador, "Shift alone does not show the box"
    assert inteira, "the first key shows the box before the letter reaches it"
    assert digitado
    _sossegar(app)

    class TodasModificam:
        def __contains__(self, _tecla) -> bool:
            return True

    monkeypatch.setattr(foco_a_vista, "_MODIFICADORES", TodasModificam())
    _so, inteira, digitado = clique_e_tecla()
    assert not inteira, "sabotaged: the letter goes into the box below the fold"
    assert digitado
    _sossegar(app)
    janela.close()


def test_the_focus_the_program_moves_on_the_release_waits_for_the_calm_too(app, monkeypatch):
    """A button inside the scroll area whose ``clicked`` -- on the release -- sends the focus to the
    box at the bottom: the button is not down any more, but the second click of a double click on
    it is still to come.  Right after the release nothing moves under the pointer; once the mouse
    is calm the box is whole.  The sabotage: the double-click interval at 0 -- the scroll comes at
    once, and the button leaves the pointer."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, conteudo, _campos, caixa, botao, _segue = _janela(app)
    proxima = QPushButton("Próxima", conteudo)
    conteudo.layout().insertWidget(0, proxima)
    proxima.clicked.connect(lambda: caixa.setFocus(Qt.FocusReason.OtherFocusReason))
    for _vez in range(2):
        app.processEvents()
    alca = janela.windowHandle()

    def clique_no_botao() -> tuple[object, object]:
        rolagem.verticalScrollBar().setValue(0)
        botao.setFocus(Qt.FocusReason.OtherFocusReason)
        app.processEvents()
        ponto = proxima.mapTo(janela, proxima.rect().center())
        _clique(app, alca, ponto)
        for _vez in range(3):
            app.processEvents()
        assert app.focusWidget() is caixa
        return proxima, janela.childAt(ponto)

    antes, sob = clique_no_botao()
    assert sob is antes, "right after the release the button is still under the pointer"
    _sossegar(app)
    assert _inteiro(rolagem, caixa), "once the mouse is calm the box is whole"
    monkeypatch.setattr(foco_a_vista, "intervalo_do_duplo_clique", lambda: 0)
    antes, sob = clique_no_botao()
    assert sob is not antes, "sabotaged: the scroll at once takes the button from under the pointer"
    janela.close()


def _janela_do_cartao(app):
    """A window 220 px tall: a scroll area with a card at the top whose height follows the line
    chosen in the list below it -- 40 px on the even lines, 80 on the odd ones, as the Rotulagem's
    card grows when the reason of the line wraps -- and a list of sixteen lines, all of them in it,
    that takes the room the view has to spare (stretch 1, as the Rotulagem's table).  The line
    chosen by a click anchors the list first (``foco_a_vista.ancorar``, looked up in the module, so
    that the sabotage can take it away), as the Rotulagem's table does."""
    from PyQt6.QtWidgets import QLabel, QListWidget, QScrollArea, QVBoxLayout, QWidget

    from caissa.ui.widgets import foco_a_vista

    janela = QWidget()
    fora = QVBoxLayout(janela)
    rolagem = QScrollArea(janela)
    rolagem.setWidgetResizable(True)
    conteudo = QWidget(rolagem)
    coluna = QVBoxLayout(conteudo)
    cartao = QLabel("o cartão da linha", conteudo)
    cartao.setFixedHeight(40)
    coluna.addWidget(cartao)
    lista = QListWidget(conteudo)
    lista.addItems([f"linha {k}" for k in range(16)])
    lista.setMinimumHeight(lista.sizeHintForRow(0) * 16 + 2 * lista.frameWidth())
    coluna.addWidget(lista, 1)
    rolagem.setWidget(conteudo)
    fora.addWidget(rolagem, 1)
    segue = foco_a_vista.RolagemSegueOFoco(rolagem)

    def escolheu(linha: int) -> None:
        if foco_a_vista.no_meio_do_clique():
            foco_a_vista.ancorar(rolagem, lista)
        cartao.setFixedHeight(80 if linha % 2 else 40)

    lista.currentRowChanged.connect(escolheu)
    janela.resize(360, 220)
    janela.show()
    app.processEvents()
    return janela, rolagem, cartao, lista, segue


def _no_fim_e_na_linha(app, janela, rolagem, lista, linha: int):
    """The list on the line before ``linha``, the scroll area at its end: a point on ``linha``."""
    lista.setCurrentRow(linha - 1)
    app.processEvents()
    barra = rolagem.verticalScrollBar()
    barra.setValue(barra.maximum())
    app.processEvents()
    return lista.viewport().mapTo(janela, lista.visualItemRect(lista.item(linha)).center())


def _linha_sob(janela, lista, ponto) -> int:
    return lista.indexAt(lista.viewport().mapFrom(janela, ponto)).row()


def test_the_line_under_the_pointer_stays_while_the_card_above_it_grows(app, monkeypatch):
    """Construtor, ciclo 9 da fase 5: in the Rotulagem the table «Linhas da página» is in the same
    scroll area as the card of the line, below it, and the card's reason wraps in one or two lines
    depending on the line chosen: with the scroll area at its end and held still, the click on line
    3 of the Gallagher p. 51 at 1280x641 grew the card 16 px, the table slid down, and the second
    click of the double click fell on line 2.  Here: a double click through the ``QWindow`` on an
    odd line, the list on the even line above it -- the card grows 40 px between the two clicks --,
    and the line under the pointer at the second click is still the one clicked, which gets the
    double click.  Once the mouse is calm the anchor lets go: the card that grows afterwards moves
    the list.  The sabotage: no anchor -- the list slides under the pointer, and the second click
    falls on another line."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, cartao, lista, _segue = _janela_do_cartao(app)
    alca = janela.windowHandle()
    duplos: list[int] = []
    lista.doubleClicked.connect(lambda indice: duplos.append(indice.row()))

    def duplo_clique(linha: int) -> tuple[int, int]:
        duplos.clear()
        ponto = _no_fim_e_na_linha(app, janela, rolagem, lista, linha)
        assert cartao.height() == 40
        antes = _linha_sob(janela, lista, ponto)
        _clique(app, alca, ponto)
        QTest.qWait(80)  # the time between the two clicks of a double click
        no_segundo = _linha_sob(janela, lista, ponto)
        _segundo_clique_de_um_duplo(app, janela, alca, ponto)
        return antes, no_segundo

    antes, no_segundo = duplo_clique(9)
    assert antes == 9
    assert cartao.height() == 80, "the click on an odd line grew the card"
    assert no_segundo == 9, "the list stayed under the pointer"
    assert duplos == [9], "the line clicked gets the double click"
    assert lista.currentRow() == 9
    _sossegar(app)
    onde = lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y()
    cartao.setFixedHeight(120)
    for _vez in range(3):  # the scroll area takes the new height one pass after the layout
        app.processEvents()
    assert lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y() == onde + 40, (
        "once the mouse is calm the anchor lets go")

    monkeypatch.setattr(foco_a_vista, "ancorar", lambda _rolagem, _controle: None)
    antes, no_segundo = duplo_clique(9)
    assert antes == 9
    assert no_segundo != 9, "sabotaged: the list slid under the pointer"
    assert duplos != [9], "sabotaged: the second click falls on another line"
    _sossegar(app)
    janela.close()


def test_the_anchor_lets_go_when_the_person_scrolls(app):
    """The anchor holds the list only against what the panel moves: with the button down the card
    that grows does not move the list; the wheel, the bar or the keys of the scroll area
    (``actionTriggered``) let it go -- what the person scrolls is not undone, and the card that
    grows afterwards moves the list."""
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QAbstractSlider

    janela, rolagem, cartao, lista, _segue = _janela_do_cartao(app)
    alca = janela.windowHandle()
    barra = rolagem.verticalScrollBar()
    ponto = _no_fim_e_na_linha(app, janela, rolagem, lista, 9)

    def onde() -> int:
        return lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y()

    QTest.mousePress(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    app.processEvents()
    assert cartao.height() == 80
    antes = onde()
    cartao.setFixedHeight(120)
    for _vez in range(3):  # the scroll area takes the new height one pass after the layout
        app.processEvents()
    assert onde() == antes, "with the button down the anchor holds the list"
    barra.triggerAction(QAbstractSlider.SliderAction.SliderSingleStepSub)
    app.processEvents()
    rolou = onde()
    assert rolou == antes + barra.singleStep(), "the person's scroll is not undone"
    cartao.setFixedHeight(160)
    for _vez in range(3):
        app.processEvents()
    assert onde() == rolou + 40, "and the anchor let go"
    QTest.mouseRelease(alca, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    _sossegar(app)
    janela.close()


def test_at_the_top_the_card_that_shrinks_leaves_a_margin_until_the_mouse_is_calm(app, monkeypatch):
    """With the scroll area at its start the bar cannot go up, and the card that shrinks above the
    list slid the list up under the pointer (the gate's double click line after line, at the top).
    The anchor puts the difference as a margin at the top of the content and takes it away once the
    mouse is calm -- then the list goes up with the content.  The sabotage: no anchor -- the second
    click falls on another line."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    janela, rolagem, cartao, lista, _segue = _janela_do_cartao(app)
    alca = janela.windowHandle()
    arranjo = rolagem.widget().layout()
    margem = arranjo.contentsMargins().top()

    def duplo_clique(linha: int) -> tuple[int, int]:
        lista.setCurrentRow(linha - 1)  # an odd line: the card at 80 px
        for _vez in range(3):
            app.processEvents()
        rolagem.verticalScrollBar().setValue(0)
        app.processEvents()
        assert cartao.height() == 80
        ponto = lista.viewport().mapTo(janela, lista.visualItemRect(lista.item(linha)).center())
        antes = _linha_sob(janela, lista, ponto)
        _clique(app, alca, ponto)
        QTest.qWait(80)  # the time between the two clicks of a double click
        no_segundo = _linha_sob(janela, lista, ponto)
        _segundo_clique_de_um_duplo(app, janela, alca, ponto)
        return antes, no_segundo

    antes, no_segundo = duplo_clique(2)
    assert antes == 2
    assert cartao.height() == 40, "the click on an even line shrank the card"
    assert no_segundo == 2, "the list stayed under the pointer"
    assert arranjo.contentsMargins().top() == margem + 40, "held by a margin at the top"
    onde = lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y()
    _sossegar(app)
    assert arranjo.contentsMargins().top() == margem, "the margin taken away once the mouse is calm"
    assert lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y() == onde - 40, "the list went up"

    monkeypatch.setattr(foco_a_vista, "ancorar", lambda _rolagem, _controle: None)
    antes, no_segundo = duplo_clique(2)
    assert antes == 2
    assert no_segundo != 2, "sabotaged: the list slid up under the pointer"
    _sossegar(app)
    janela.close()


def test_the_anchor_is_one_per_scroll_area_and_outlives_its_release(app, monkeypatch):
    """Construtor, ciclo 9 da fase 5: the first version made one anchor per click and, on release,
    disconnected the scroll bar's signals -- PyQt deletes the proxy of a disconnected Python slot
    with ``deleteLater``, and the critic's probe that leaves by ``os._exit`` right after a click
    showed an «access violation» at the exit, with the deletion pending.  One anchor per scroll
    area, made on the first click and used again, its signals connected once: three double clicks
    on three lines leave one anchor, holding nothing once the mouse is calm; and it goes with the
    scroll area.  The sabotage: an anchor made on every click (the old one never found) -- three."""
    from PyQt6 import sip
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    def tres_duplos_cliques():
        janela, rolagem, _cartao, lista, _segue = _janela_do_cartao(app)
        alca = janela.windowHandle()
        for linha in (5, 7, 9):
            ponto = _no_fim_e_na_linha(app, janela, rolagem, lista, linha)
            _clique(app, alca, ponto)
            QTest.qWait(80)  # the time between the two clicks of a double click
            _segundo_clique_de_um_duplo(app, janela, alca, ponto)
            _sossegar(app)
        ancoras = [o for o in rolagem.children() if isinstance(o, foco_a_vista._Ancora)]
        return janela, rolagem, ancoras

    janela, rolagem, ancoras = tres_duplos_cliques()
    assert len(ancoras) == 1, "one anchor for the scroll area, used again"
    assert ancoras[0].segurando() is None, "once the mouse is calm it holds nothing"
    endereco = foco_a_vista._endereco(rolagem)
    assert foco_a_vista._ANCORAS.get(endereco) is ancoras[0]
    sip.delete(janela)
    assert endereco not in foco_a_vista._ANCORAS, "and it goes with the scroll area"

    monkeypatch.setattr(foco_a_vista, "_a_ancora_de", lambda _rolagem: None)
    janela, _rolagem, ancoras = tres_duplos_cliques()
    assert len(ancoras) == 3, "sabotaged: an anchor made on every click"
    janela.close()


def _segurar_do_ciclo_9(self, controle, vigiados) -> None:
    """The anchor's ``segurar`` of cycle 9: it let go first -- the margin came off on the press of
    the new click."""
    self.soltar()
    self._controle = controle
    self._vigiados = vigiados
    self._y = self._onde(controle)
    for vigiado in vigiados:
        vigiado.installEventFilter(self)
    self._vigia.start()


def test_a_click_on_another_line_before_the_calm_keeps_the_margin(app, monkeypatch):
    """Crítico da fase 5, ciclo 9 (não bloqueante 1): with the bar at its start the card that shrank
    became a margin at the top; a click on another line before the calm anchored again, the margin
    came off on the press, the list rose under the pointer held still, and the second click of the
    double click fell on the next line -- the card and the truth of the neighbour.  Here: the list
    on line 1 (the card at 80), a click on line 2 (the card shrinks: a margin of 40), 150 ms, and a
    double click on line 3 (the card grows again): the line under the pointer at the second click
    is 3, which gets the double click and stays chosen.  The sabotage: the ``segurar`` of cycle 9,
    which let go first -- the second click falls on line 4."""
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    def clique_e_duplo_clique() -> tuple[int, list[int], int]:
        janela, rolagem, cartao, lista, _segue = _janela_do_cartao(app)
        alca = janela.windowHandle()
        duplos: list[int] = []
        lista.doubleClicked.connect(lambda indice: duplos.append(indice.row()))
        lista.setCurrentRow(1)
        for _vez in range(3):
            app.processEvents()
        rolagem.verticalScrollBar().setValue(0)
        app.processEvents()
        assert cartao.height() == 80
        centro_da = lambda linha: lista.viewport().mapTo(  # noqa: E731 - geometry of now
            janela, lista.visualItemRect(lista.item(linha)).center())
        _clique(app, alca, centro_da(2))
        assert rolagem.widget().layout().contentsMargins().top() >= 40, "the margin of the shrink"
        QTest.qWait(150)  # the second click comes before the calm
        ponto = centro_da(3)
        _clique(app, alca, ponto)
        QTest.qWait(80)  # the time between the two clicks of a double click
        no_segundo = _linha_sob(janela, lista, ponto)
        _segundo_clique_de_um_duplo(app, janela, alca, ponto)
        _sossegar(app)
        escolhida = lista.currentRow()
        janela.close()
        return no_segundo, duplos, escolhida

    no_segundo, duplos, escolhida = clique_e_duplo_clique()
    assert no_segundo == 3, "the list stayed under the pointer"
    assert duplos == [3], "the line clicked twice gets the double click"
    assert escolhida == 3

    monkeypatch.setattr(foco_a_vista._Ancora, "segurar", _segurar_do_ciclo_9)
    no_segundo, duplos, escolhida = clique_e_duplo_clique()
    assert no_segundo != 3, "sabotaged: the margin came off on the press, the list rose"
    assert escolhida != 3, "sabotaged: the neighbour chosen"


def _soltar_do_ciclo_9(self, *, dentro_da_acao: bool = False) -> None:
    """The anchor's ``soltar`` of cycle 9: the margin came off the value of now, also inside the
    action of the bar."""
    del dentro_da_acao
    if self._controle is None:
        return
    self._controle = None
    self._vigia.stop()
    self._largar_os_vigiados()
    if self._folga:
        folga = self._folga
        self._folgar(-folga)
        self._barra.setValue(self._barra.value() - folga)


def test_the_wheel_with_the_margin_set_is_not_swallowed(app, monkeypatch):
    """Crítico da fase 5, ciclo 9 (não bloqueante 2): the wheel lets the anchor go, and the release
    took the margin off with ``setValue`` inside ``triggerAction`` -- the position the wheel was
    about to apply was replaced by the one of now: with the margin set, the bar went from 0 to 0.
    Here: with the margin of the shrink set (the bar at its start), a page down of the bar moves
    the bar, and the content goes up by the margin and by what the bar moved.  The sabotage: the
    ``soltar`` of cycle 9 -- the bar stays at 0."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QAbstractSlider

    from caissa.ui.widgets import foco_a_vista

    def pagina_abaixo_com_a_folga() -> tuple[int, int, int]:
        janela, rolagem, _cartao, lista, _segue = _janela_do_cartao(app)
        alca = janela.windowHandle()
        barra = rolagem.verticalScrollBar()
        lista.setCurrentRow(1)
        for _vez in range(3):
            app.processEvents()
        barra.setValue(0)
        app.processEvents()
        ponto = lista.viewport().mapTo(janela, lista.visualItemRect(lista.item(2)).center())
        _clique(app, alca, ponto)
        folga = rolagem.widget().layout().contentsMargins().top()
        onde = lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y()
        barra.triggerAction(QAbstractSlider.SliderAction.SliderPageStepAdd)
        for _vez in range(3):
            app.processEvents()
        andou = barra.value()
        subiu = onde - lista.mapTo(rolagem.viewport(), QPoint(0, 0)).y()
        _sossegar(app)
        janela.close()
        return folga, andou, subiu

    folga, andou, subiu = pagina_abaixo_com_a_folga()
    assert folga >= 40, "the margin of the shrink was set"
    assert andou > 0, "the bar moved"
    assert subiu == 40 + andou, "the content went up by the margin and by what the bar moved"

    monkeypatch.setattr(foco_a_vista._Ancora, "soltar", _soltar_do_ciclo_9)
    _folga, andou, _subiu = pagina_abaixo_com_a_folga()
    assert andou == 0, "sabotaged: the page down swallowed"


def test_the_wheel_during_the_wait_stays_and_the_first_key_shows_the_box(app, monkeypatch):
    """Crítico da fase 5, ciclo 9 (não bloqueante 3): a click on a line sends the focus to the box
    below the fold, which waits for the calm; the wheel 100 ms after the click took the bar away,
    and at the calm the follower brought it back to the box -- the person's wheel undone.  Here:
    after the click, a step down of the bar (the wheel's action); at the calm the bar is where the
    person left it, and the box, not shown; the first key shows it, and the letter goes into it.
    The sabotage: the follower deaf to the person's scroll -- at the calm the bar goes to the
    box."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QAbstractSlider

    from caissa.ui.widgets import foco_a_vista

    def roda_na_espera() -> tuple[int, int, bool, bool]:
        janela, rolagem, linhas, caixa, botao = _janela_da_lista(app)
        alca = janela.windowHandle()
        barra = rolagem.verticalScrollBar()
        caixa.setPlainText("")
        ponto = _na_linha(app, janela, rolagem, linhas, botao)
        _clique(app, alca, ponto)
        assert app.focusWidget() is caixa
        barra.triggerAction(QAbstractSlider.SliderAction.SliderSingleStepAdd)
        app.processEvents()
        rolou = barra.value()
        _sossegar(app)
        depois = barra.value()
        escondida = not _inteiro(rolagem, caixa)
        QTest.keyClick(caixa, Qt.Key.Key_X)
        app.processEvents()
        mostrada = _inteiro(rolagem, caixa) and caixa.toPlainText() == "x"
        janela.close()
        return rolou, depois, escondida, mostrada

    rolou, depois, escondida, mostrada = roda_na_espera()
    assert rolou > 0
    assert depois == rolou, "at the calm the bar is where the person left it"
    assert escondida, "the box is not brought back"
    assert mostrada, "the first key shows the box, and the letter goes into it"

    monkeypatch.setattr(foco_a_vista.RolagemSegueOFoco, "_a_pessoa_rolou",
                        lambda _self, _acao: None)
    rolou, depois, _escondida, _mostrada = roda_na_espera()
    assert depois != rolou, "sabotaged: at the calm the follower takes the bar to the box"


def test_when_the_content_fits_the_card_that_grows_gets_a_floor_until_the_calm(app, monkeypatch):
    """A window where the whole content fits the view: the bar has nowhere to go, and the card that
    grows above the list took the list down under the pointer -- the second click of a double click
    fell on the line above.  The anchor gives the content a floor (a minimum height that lends the
    bar the reach it lacks), and takes it away at the calm.  The sabotage: no floor -- the second
    click falls off the line."""
    from PyQt6.QtTest import QTest

    from caissa.ui.widgets import foco_a_vista

    def duplo_clique_na_janela_alta() -> tuple[int, int, int, int]:
        janela, rolagem, cartao, lista, _segue = _janela_do_cartao(app)
        janela.resize(360, 700)
        for _vez in range(3):
            app.processEvents()
        alca = janela.windowHandle()
        barra = rolagem.verticalScrollBar()
        lista.setCurrentRow(0)
        for _vez in range(3):
            app.processEvents()
        assert barra.maximum() == 0, "the whole content fits the view"
        assert cartao.height() == 40
        ponto = lista.viewport().mapTo(janela, lista.visualItemRect(lista.item(1)).center())
        _clique(app, alca, ponto)
        QTest.qWait(80)  # the time between the two clicks of a double click
        no_segundo = _linha_sob(janela, lista, ponto)
        _segundo_clique_de_um_duplo(app, janela, alca, ponto)
        piso = rolagem.widget().minimumHeight()
        _sossegar(app)
        depois = rolagem.widget().minimumHeight()
        escolhida = lista.currentRow()
        janela.close()
        return no_segundo, escolhida, piso, depois

    no_segundo, escolhida, piso, depois = duplo_clique_na_janela_alta()
    assert no_segundo == 1, "the list stayed under the pointer"
    assert escolhida == 1
    assert piso > 0, "held by a floor"
    assert depois == 0, "the floor taken away at the calm"

    monkeypatch.setattr(foco_a_vista._Ancora, "_pisar", lambda _self, _valor: None)
    no_segundo, _escolhida, _piso, _depois = duplo_clique_na_janela_alta()
    assert no_segundo != 1, "sabotaged: the list went down under the pointer"


def _montar_e_destruir(app) -> None:
    """A scroll area with a follower and a field that has the focus, deleted with the focus in it --
    as the dialog «Base de partidas» is, after its question (`perguntar_bases`)."""
    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QLineEdit, QScrollArea, QVBoxLayout, QWidget

    from caissa.ui.widgets.foco_a_vista import RolagemSegueOFoco

    janela = QWidget()
    coluna = QVBoxLayout(janela)
    rolagem = QScrollArea(janela)
    conteudo = QWidget(rolagem)
    campo = QLineEdit(conteudo)
    QVBoxLayout(conteudo).addWidget(campo)
    rolagem.setWidget(conteudo)
    coluna.addWidget(rolagem)
    RolagemSegueOFoco(rolagem)
    janela.show()
    app.processEvents()
    campo.setFocus()
    app.processEvents()
    assert app.focusWidget() is campo
    rolagem.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()
    janela.close()


def test_a_follower_whose_scroll_area_is_deleted_asks_it_nothing(app, monkeypatch):
    """Found by the builder (fase 5, ciclo 8), with the critic's probe of the dead scroll area: a
    scroll area deleted with the focus in it -- the dialog of bases after its question -- clears the
    focus in its destructor, after the scroll area's wrapper is gone and before the follower, its
    child, is; the first version of cycle 8 asked the dead scroll area for its content before asking
    whether there was a new focus: «wrapped C/C++ object of type QScrollArea has been deleted», 20
    times in 20 questions, and an access violation at the end.  The follower asks first whether
    there is a new focus and whether its scroll area lives.  The sabotage: the order of that first
    version."""
    import sys

    from caissa.ui.widgets import foco_a_vista

    erros: list[str] = []
    def anotar(tipo, valor, _tb) -> None:
        erros.append(f"{tipo.__name__}: {valor}")

    monkeypatch.setattr(sys, "excepthook", anotar)
    _montar_e_destruir(app)
    assert erros == [], erros

    def primeira_versao(self, _antigo, novo):  # a plain callable: connected by PyQt's proxy
        conteudo = self._rolagem.widget()
        if (not self._ligado or novo is None or conteudo is None or not conteudo.isAncestorOf(novo)
                or foco_a_vista.veio_do_mouse(novo)):
            return
        foco_a_vista.mostrar(self._rolagem, novo)

    monkeypatch.setattr(foco_a_vista.RolagemSegueOFoco, "_foco_mudou", primeira_versao)
    _montar_e_destruir(app)
    mortas = [erro for erro in erros if "has been deleted" in erro]
    assert mortas, ("sabotaged: the dead scroll area is asked", erros)


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
