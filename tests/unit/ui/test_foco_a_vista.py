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

    # the sabotage of cycle 6: the follower scrolls on the press itself
    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda _controle: False)
    monkeypatch.setattr(foco_a_vista, "no_meio_do_clique", lambda: False)
    antes, depois = clicar_junto_do_corte()
    assert depois != antes, "sabotaged: the click is lost"
    assert not marca.isChecked(), "sabotaged: the click is lost"
    janela.close()


def test_the_focus_the_program_moves_during_a_click_is_shown_after_the_release(app, monkeypatch):
    """Crítico da fase 5, ciclo 7: a row of the tables of the Rotulagem and of the Revisão de texto
    sends the focus to «Verdade da linha» on the *press* of the click, and the guard of cycle 7 (a
    button is down) took that focus for the mouse's -- the truth stayed out of sight (0x0 px at
    1280x641), and what was typed went there.  Here a list at the top of the scroll area sends the
    focus to the text box at the bottom when its row changes, on the press: the click ends where it
    was given (the row is clicked once), and then the box is shown whole, and the typing goes into
    it.  The sabotages: the guard of cycle 7 (the box stays hidden); the follower of cycle 6, which
    scrolled on the press (the list moves away and the click is lost)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QListWidget

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
        for _vez in range(3):  # the release, then the scroll after it
            app.processEvents()
        QTest.keyClicks(app.focusWidget(), "XYZ")
        app.processEvents()

    clicar_a_linha()
    assert clicado == [1], "the click ends where it was given"
    assert linhas.currentRow() == 1
    assert app.focusWidget() is caixa
    assert _inteiro(rolagem, caixa), "the focus the program moved is shown after the release"
    assert "XYZ" in caixa.toPlainText(), "and the typing goes where the eyes are"

    def guarda_do_ciclo_7(controle) -> bool:
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            return True
        return controle.focusPolicy() == Qt.FocusPolicy.WheelFocus and controle.underMouse()

    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", guarda_do_ciclo_7)
    clicar_a_linha()
    assert app.focusWidget() is caixa
    assert caixa.visibleRegion().isEmpty(), "sabotaged (cycle 7): the focus stays out of sight"

    monkeypatch.setattr(foco_a_vista, "veio_do_mouse", lambda _controle: False)
    monkeypatch.setattr(foco_a_vista, "no_meio_do_clique", lambda: False)
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
        for _vez in range(3):
            app.processEvents()
        assert app.focusWidget() is caixa

    clicar_a_linha_com_a_marca_velha()
    assert _inteiro(rolagem, caixa), "the program's focus is shown after the release"
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
    would deliver the press before it): the button gets the click, and nothing scrolls.  The
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
        for _vez in range(3):
            app.processEvents()
        return antes, barra.value()

    antes, depois = a_volta_com_um_clique()
    assert clicados == [True], "the click that brought the window back counts where it was given"
    assert depois == antes, "nothing scrolls under the pointer"
    assert app.focusWidget() is aceitar

    monkeypatch.setattr(foco_a_vista, "voltou_com_a_janela", lambda _controle: False)
    antes, depois = a_volta_com_um_clique()
    assert clicados == [], "sabotaged: the click that brought the window back is lost"
    assert depois != antes, "sabotaged: the view scrolls under the pointer"
    janela.close()


def test_the_focus_given_back_on_return_with_no_click_is_shown(app, monkeypatch):
    """The window really activated again (``activateWindow``, after another window was the active
    one), with no click -- the Alt+Tab, the dialog that closed: the focus the window gives back is
    shown whole right after, as any focus the keyboard sees.  The sabotage: the wait for the events
    of the return that never shows anything, and the field stays out of sight."""
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
        for _vez in range(3):
            app.processEvents()
        assert app.focusWidget() is primeiro, "the window gives the focus back to the first field"

    a_volta_sem_clique()
    assert _inteiro(rolagem, primeiro), "with no click, the focus of the return is shown"
    monkeypatch.setattr(foco_a_vista.RolagemSegueOFoco, "_depois_da_volta", lambda _self: None)
    a_volta_sem_clique()
    assert primeiro.visibleRegion().isEmpty(), "sabotaged: the focus of the return stays hidden"
    outra.close()
    janela.close()


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
