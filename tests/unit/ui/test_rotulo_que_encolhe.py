"""The suite's label that never decides a width — OCR_UI_ROADMAP_C2 passo C18."""

from __future__ import annotations

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from caissa.ui.widgets.rotulo_que_encolhe import RotuloQueEncolhe  # noqa: E402

LONGO = "87 linhas · 0 pendentes (0 duvidosas) · 86 aceitas · 1 editadas · 0 rejeitadas · " * 4


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_a_long_status_never_raises_the_minimum_width(app) -> None:
    rotulo = RotuloQueEncolhe(LONGO)
    comum = QtWidgets.QLabel(LONGO)
    assert rotulo.minimumSizeHint().width() == 0
    assert comum.minimumSizeHint().width() > 1000          # the sabotage: what a QLabel asks for
    assert rotulo.minimumSizeHint().height() == comum.minimumSizeHint().height()


def test_the_whole_text_stays_readable_by_code_and_tooltip(app) -> None:
    rotulo = RotuloQueEncolhe("")
    rotulo.setText(LONGO)
    assert rotulo.text() == LONGO                           # the views' tests read it back
    assert rotulo.toolTip() == LONGO


def test_a_narrow_label_paints_the_elided_text(app) -> None:
    janela = QtWidgets.QWidget()
    coluna = QtWidgets.QVBoxLayout(janela)
    rotulo = RotuloQueEncolhe(LONGO, janela)
    coluna.addWidget(rotulo)
    janela.resize(240, 60)
    janela.show()
    app.processEvents()
    assert rotulo.width() <= 240
    assert rotulo.elided().endswith("…")
    assert len(rotulo.elided()) < len(LONGO)
    assert not janela.grab().isNull()                       # the painting path runs
    janela.close()


def test_a_layout_with_it_shrinks_below_the_text(app) -> None:
    janela = QtWidgets.QWidget()
    coluna = QtWidgets.QVBoxLayout(janela)
    coluna.addWidget(RotuloQueEncolhe(LONGO, janela))
    assert janela.minimumSizeHint().width() < 100
