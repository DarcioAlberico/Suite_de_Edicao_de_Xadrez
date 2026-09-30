"""A tabela de linhas guarda as teclas de lista: PgUp, PgDn, Home e End andam pelas linhas
com o foco nela, e não viram a página do livro (crítico da fase 5, ciclo 6).

O módulo é :mod:`caissa.ui.widgets.tabela_de_linhas`. A guarda de atalhos é a do tronco
(`chess_diagram_ocr.qt.atalhos.GuardaDeAtalhos`): a segunda metade roda quando ele está no caminho
(`PYTHONPATH=<tronco>\\src`), e pula sem ele. Sem PyQt6 no ambiente os testes pulam.
"""

from __future__ import annotations

import os

import pytest

PyQt6 = pytest.importorskip("PyQt6", reason="a tabela é PyQt6; o .venv da suíte não o tem")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _tabela(app, classe):
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

    tabela = classe(40, 2)
    tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    for linha in range(40):
        tabela.setItem(linha, 0, QTableWidgetItem(str(linha + 1)))
        tabela.setItem(linha, 1, QTableWidgetItem(f"linha {linha + 1}"))
    tabela.resize(300, 240)
    tabela.show()
    tabela.setCurrentCell(0, 0)
    tabela.setFocus()
    app.processEvents()
    return tabela


def test_the_list_keys_are_the_table_s_actions_and_walk_its_lines(app):
    """The table declares the window's four page actions for itself (``DonoDeAcoes``, by shape) and
    answers each with a list step: PgDn a page of lines down, End the last line, Home the first,
    PgUp a page up.  Any other action is the window's."""
    from caissa.ui.widgets.tabela_de_linhas import TabelaDeLinhas

    tabela = _tabela(app, TabelaDeLinhas)
    assert tabela.acoes_proprias() == frozenset(
        {"pagina_anterior", "proxima_pagina", "primeira_pagina", "ultima_pagina"})
    assert tabela.atender("salvar") is None
    tabela.atender("proxima_pagina")()
    pagina = tabela.currentRow()
    assert pagina > 1, "a page of lines down"
    tabela.atender("ultima_pagina")()
    assert tabela.currentRow() == 39
    tabela.atender("pagina_anterior")()
    assert 0 < tabela.currentRow() < 39
    tabela.atender("primeira_pagina")()
    assert tabela.currentRow() == 0
    assert tabela.selectedItems(), "the row is selected"
    assert tabela.selectedItems()[0].row() == 0, "the row is selected"
    # without the window's guard (the tab on its own) Home and End go to the ends of the list too
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    QTest.keyClick(tabela, Qt.Key.Key_End)
    assert tabela.currentRow() == 39
    QTest.keyClick(tabela, Qt.Key.Key_Home)
    assert tabela.currentRow() == 0
    tabela.close()


def test_both_tabs_list_their_lines_in_the_table_that_keeps_the_list_keys(app, tmp_path):
    """«Linhas da página» (Rotulagem) and «Dúvidas do livro» (Revisão de texto)."""
    from caissa.ui.views.revisao_de_texto import PainelDeRevisaoDeTexto
    from caissa.ui.views.rotulagem import PainelDeRotulagem, abrir_projeto
    from caissa.ui.widgets.tabela_de_linhas import TabelaDeLinhas

    rotulagem = PainelDeRotulagem(projeto=abrir_projeto(tmp_path / "proj", revisor="ana"))
    revisao = PainelDeRevisaoDeTexto(revisor="ana", pasta=tmp_path / "rev")
    assert isinstance(rotulagem.table, TabelaDeLinhas)
    assert rotulagem.table.accessibleName() == "Linhas da página"
    assert isinstance(revisao.table, TabelaDeLinhas)
    assert revisao.table.accessibleName() == "Dúvidas do livro"
    rotulagem.close()
    revisao.close()


def test_with_the_window_s_guard_the_page_keys_stay_in_the_table(app):
    """The trunk's guard sees the key before the control in focus and gave PgDn to the window --
    the next page of the book, the Rotulagem's table emptied.  With the focus in the table the
    table answers it; the sabotage: a plain ``QTableWidget``, and the window turns the page."""
    atalhos = pytest.importorskip("chess_diagram_ocr.qt.atalhos",
                                  reason="a guarda de atalhos é do tronco")
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QTableWidget

    from caissa.ui.widgets.tabela_de_linhas import TabelaDeLinhas

    for classe, janela_vira in ((TabelaDeLinhas, False), (QTableWidget, True)):
        viradas: list[str] = []
        comandos = {nome: (lambda n=nome, v=viradas: v.append(n))
                    for nome in ("proxima_pagina", "pagina_anterior", "primeira_pagina",
                                 "ultima_pagina")}
        tabela = _tabela(app, classe)
        guarda = atalhos.ligar(tabela, comandos, aplicacao=app)
        try:
            QTest.keyClick(tabela, Qt.Key.Key_PageDown)
            QTest.keyClick(tabela, Qt.Key.Key_End)
            app.processEvents()
        finally:
            app.removeEventFilter(guarda)
        if janela_vira:
            assert viradas == ["proxima_pagina", "ultima_pagina"], "sabotaged: the window's"
            assert tabela.currentRow() == 0
        else:
            assert viradas == [], "the window did not turn the page"
            assert tabela.currentRow() == 39
        tabela.close()
