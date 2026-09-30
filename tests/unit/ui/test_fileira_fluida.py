"""A fileira que quebra linha em vez de cortar (OCR_UI ciclo 2, fase 5, C18; crítico do ciclo 1).

Os botões da Revisão de texto, as teclas de figurina do cartão e as barras da Rotulagem viviam em
`QHBoxLayout`: a largura mínima era a soma, e com a janela no mínimo de 1248x640 «Pular»,
«Anterior» e «Próxima» ficavam com 0 px à vista.  A fileira fluida pede só o maior controle, desce
para a linha de baixo, e a altura acompanha a largura.
"""

from __future__ import annotations

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")


@pytest.fixture
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _fileira(app, textos):
    from caissa.ui.widgets.fileira_fluida import FileiraFluida

    fileira = FileiraFluida()
    botoes = [fileira.adicionar(QtWidgets.QPushButton(t)) for t in textos]
    return fileira, botoes


TEXTOS = ["Aceitar leitura", "Gravar edição", "Manter como imagem", "Pular", "Anterior", "Próxima"]


def test_o_minimo_e_o_maior_controle_e_nao_a_soma(app) -> None:
    fileira, botoes = _fileira(app, TEXTOS)
    maior = max(b.minimumSizeHint().width() for b in botoes)
    soma = sum(b.sizeHint().width() for b in botoes)
    assert fileira.minimumSizeHint().width() == maior
    assert fileira.sizeHint().width() >= soma          # o desejado continua sendo uma linha só


def test_estreita_ela_desce_de_linha_e_nada_sai_da_largura(app) -> None:
    fileira, botoes = _fileira(app, TEXTOS)
    larga = fileira.heightForWidth(2000)
    estreita = fileira.heightForWidth(300)
    assert estreita > larga
    fileira.resize(300, estreita)
    fileira.show()
    for _ in range(3):
        app.processEvents()
    for botao in botoes:
        assert botao.geometry().right() <= 300
        assert botao.width() >= botao.minimumSizeHint().width()   # nenhum espremido


def test_um_rotulo_mais_largo_que_a_linha_fica_com_a_largura_da_linha(app) -> None:
    from caissa.ui.widgets.fileira_fluida import FileiraFluida
    from caissa.ui.widgets.rotulo_que_encolhe import RotuloQueEncolhe

    fileira = FileiraFluida()
    rotulo = fileira.adicionar(RotuloQueEncolhe("x" * 400))
    fileira.resize(250, fileira.heightForWidth(250))
    fileira.show()
    for _ in range(3):
        app.processEvents()
    assert rotulo.geometry().right() <= 250
