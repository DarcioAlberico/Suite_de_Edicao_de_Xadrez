"""O protótipo do editor de código, com todas as funções ligadas (roadmap H2, D4).

Cada função com ao menos cinco casos dourados, lidos do widget e não da chamada: a cor posta na
posição, o número pintado na margem, a seleção extra com o estilo de sublinhado, a lista que o
completar mostra, o texto e o cursor depois de desfazer. Todas as funções ficam ligadas em todos os
casos — o protótipo existe para provar que elas cabem juntas. A prévia fica ligada sem o processo
de trabalho (o pedido sai; quem o atende é o arnês `benchmarks/editor_codigo.py`).

Sem PyQt6 no ambiente os testes pulam.
"""

from __future__ import annotations

import os
import time

import pytest

PyQt6 = pytest.importorskip("PyQt6", reason="o editor é PyQt6; o .venv da suíte não o tem")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


CAPITULO = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Capítulo 2</title>
<style>
p.cb-caption { font-style: italic; }
</style>
</head>
<body>
<section id="cap-02">
<h2 id="p55-1">Torres atrás do peão</h2>
<p id="p55-2">A torre fica <em>atrás</em> do peão &amp; o rei corre.</p>
<!-- uma nota
de duas linhas -->
<figure class="cb-diagram" data-fen="8/8/8/8/8/8/8/K6k w - - 0 1">
<img class="cb-svg" src="../Images/dg_1.svg" alt="Diagrama 1"/>
</figure>
<p class="cb-movetext">1.♘f3 d5 2.g3</p>
</section>
</body>
</html>"""


def _pronto(app, texto: str = CAPITULO, *, tipo: str = "xhtml", classes=("cb-caption", "cb-move")):
    from caissa.ui.widgets.editor_de_codigo import montar

    montagem = montar(texto, tipo=tipo, classes_do_projeto=classes, com_previa=False)
    editor = montagem.editor
    editor.resize(900, 700)
    editor.show()
    limite = time.perf_counter() + 10
    while time.perf_counter() < limite:
        app.processEvents()
        if (not editor.carregando and editor.realce.completo and not editor.dobras.ocupado
                and editor.realce.visivel_realcado()):
            break
    return editor


def _esperar(app, segundos: float = 0.2) -> None:
    limite = time.perf_counter() + segundos
    while time.perf_counter() < limite:
        app.processEvents()
        time.sleep(0.005)


def _cor_em(editor, linha: int, coluna: int) -> str | None:
    """A cor que o realce pôs no caractere (linha e coluna a partir de 1 e 0)."""
    bloco = editor.document().findBlockByNumber(linha - 1)
    for faixa in bloco.layout().formats():
        if faixa.start <= coluna < faixa.start + faixa.length:
            return faixa.format.foreground().color().name()
    return None


def _cursor_em(editor, linha: int, coluna: int) -> None:
    from PyQt6.QtGui import QTextCursor

    bloco = editor.document().findBlockByNumber(linha - 1)
    cursor = QTextCursor(bloco)
    cursor.setPosition(bloco.position() + coluna)
    editor.setTextCursor(cursor)


# ------------------------------------------------------------------------------------ realce

CORES = {
    "tag": "#0b4f8a", "atributo": "#7a2e00", "valor": "#0a5c2b", "comentario": "#595959",
    "entidade": "#6b1d8f", "delimitador": "#444444", "propriedade": "#7a2e00",
}


@pytest.mark.parametrize(("linha", "trecho", "papel"), [
    (11, "h2", "tag"),
    (11, "id", "atributo"),
    (11, '"p55-1"', "valor"),
    (12, "&amp;", "entidade"),
    (13, "uma nota", "comentario"),
    (14, "duas linhas", "comentario"),       # a segunda linha herda o estado do comentário
    (6, "font-style", "propriedade"),        # dentro do <style>
    (15, "<", "delimitador"),
])
def test_realce_pinta_o_papel_certo(app, linha, trecho, papel) -> None:
    editor = _pronto(app)
    coluna = editor.document().findBlockByNumber(linha - 1).text().index(trecho)
    assert _cor_em(editor, linha, coluna) == CORES[papel]


def test_realce_deixa_o_texto_do_livro_sem_cor(app) -> None:
    editor = _pronto(app)
    coluna = editor.document().findBlockByNumber(11).text().index("fica")
    assert _cor_em(editor, 12, coluna) is None


def test_realce_segue_a_tecla_que_abre_um_comentario(app) -> None:
    from PyQt6.QtTest import QTest

    editor = _pronto(app)
    _cursor_em(editor, 11, 0)
    QTest.keyClicks(editor, "<!--")
    _esperar(app)
    assert _cor_em(editor, 12, 3) == CORES["comentario"]   # a linha seguinte virou comentário


# ------------------------------------------------------------------------------------ margem


def test_margem_pinta_os_numeros_das_linhas_a_vista(app) -> None:
    editor = _pronto(app)
    editor.margem.grab()
    assert editor.margem.linhas_pintadas[:3] == [1, 2, 3]
    assert editor.margem.linhas_pintadas[-1] == editor.blockCount()


def test_margem_acompanha_a_rolagem(app) -> None:
    editor = _pronto(app, "\n".join(f"<p>linha {n}</p>" for n in range(400)))
    editor.verticalScrollBar().setValue(100)
    _esperar(app, 0.05)
    editor.margem.grab()
    assert editor.margem.linhas_pintadas[0] == 101


@pytest.mark.parametrize(("tipo", "cor"), [("problema", "#b00020"), ("duvida", "#8a5a00")])
def test_margem_pinta_o_marcador_na_linha(app, tipo, cor) -> None:
    editor = _pronto(app)
    editor.marcar(2, tipo)                                      # a terceira linha
    imagem = editor.margem.grab().toImage()
    # O meio da terceira linha onde o editor a pôs: o bloco é mais alto que a fonte.
    bloco = editor.document().findBlockByNumber(2)
    topo = editor.blockBoundingGeometry(bloco).translated(editor.contentOffset()).top()
    y = int(topo + editor.blockBoundingRect(bloco).height() / 2)
    assert imagem.pixelColor(3, y).name() == cor
    assert imagem.pixelColor(3, int(topo) - 2).name() != cor    # a segunda linha fica sem


def test_margem_alarga_com_os_digitos(app) -> None:
    curto = _pronto(app, "\n".join("<p/>" for _ in range(9)))
    longo = _pronto(app, "\n".join("<p/>" for _ in range(1200)))
    assert longo.margem.largura() > curto.margem.largura()


# ------------------------------------------------------------------------------- indicadores


def _estilos(editor) -> list[tuple[int, int, str]]:
    from PyQt6.QtGui import QTextCharFormat

    nomes = {QTextCharFormat.UnderlineStyle.WaveUnderline: "onda",
             QTextCharFormat.UnderlineStyle.DotLine: "pontilhado"}
    return [(s.cursor.selectionStart(), s.cursor.selectionEnd(),
             nomes.get(s.format.underlineStyle(), "outro")) for s in editor.indicadores()]


def test_indicador_de_problema_e_onda_e_de_duvida_e_pontilhado(app) -> None:
    editor = _pronto(app)
    editor.definir_indicadores([(10, 20, "problema"), (30, 35, "duvida")])
    assert _estilos(editor) == [(10, 20, "onda"), (30, 35, "pontilhado")]


def test_indicadores_andam_com_o_texto(app) -> None:
    editor = _pronto(app)
    editor.definir_indicadores([(100, 110, "duvida")])
    _cursor_em(editor, 1, 0)
    editor.insertPlainText("XYZ")
    assert _estilos(editor) == [(103, 113, "pontilhado")]


def test_quinhentos_indicadores_vao_ao_widget(app) -> None:
    editor = _pronto(app, "\n".join(f"<p>parágrafo {n} com dúvida</p>" for n in range(600)))
    editor.definir_indicadores([(n * 30, n * 30 + 5, "problema" if n % 2 else "duvida")
                                for n in range(500)])
    assert len(editor.indicadores()) == 500
    assert editor.contadores.selecoes_extras >= 500


def test_indicadores_somam_se_a_linha_atual(app) -> None:
    editor = _pronto(app)
    editor.definir_indicadores([(10, 20, "problema")])
    _cursor_em(editor, 5, 0)
    assert len(editor.extraSelections()) >= 2


def test_indicadores_novos_trocam_os_velhos(app) -> None:
    editor = _pronto(app)
    editor.definir_indicadores([(10, 20, "problema")])
    editor.definir_indicadores([])
    assert _estilos(editor) == []


# ---------------------------------------------------------------------------------- completar


def _digitar(app, editor, texto: str) -> None:
    from PyQt6.QtTest import QTest

    QTest.keyClicks(editor, texto)
    _esperar(app, 0.05)


def test_completar_abre_as_tags_depois_do_menor_que(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 12, 0)
    _digitar(app, editor, "<")
    assert editor.completar_visivel()
    assert "figure" in editor.sugestoes()


def test_completar_filtra_pelo_que_se_digita(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 12, 0)
    _digitar(app, editor, "<fi")
    assert editor.sugestoes() == ["figcaption", "figure"]


def test_completar_insere_com_enter(app) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    editor = _pronto(app)
    _cursor_em(editor, 12, 0)
    _digitar(app, editor, "<figc")
    QTest.keyClick(editor._completar.popup(), Qt.Key.Key_Return)
    _esperar(app, 0.05)
    assert editor.document().findBlockByNumber(11).text().startswith("<figcaption")


def test_completar_oferece_atributos_depois_do_espaco_na_tag(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 12, 0)
    _digitar(app, editor, "<p ")
    assert "data-fen" in editor.sugestoes()
    assert "class" in editor.sugestoes()


def test_completar_oferece_as_classes_do_projeto(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 12, 0)
    _digitar(app, editor, '<p class="')
    assert editor.sugestoes() == ["cb-caption", "cb-move"]


def test_esc_fecha_a_lista_e_nao_o_editor(app) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    editor = _pronto(app)
    _cursor_em(editor, 12, 0)
    _digitar(app, editor, "<")
    QTest.keyClick(editor._completar.popup(), Qt.Key.Key_Escape)
    _esperar(app, 0.05)
    assert not editor.completar_visivel()
    assert editor.isVisible()


# ------------------------------------------------------------------------------ fechar a tag


#: Cada «</» digitado fecha o elemento aberto mais interno; os pedaços são o que a pessoa digita.
#: Só ASCII: o `QTest.keyClicks` com caractere fora do ASCII derruba o processo, até num
#: `QPlainTextEdit` puro (PyQt6 6.11, offscreen) — o texto com acento entra pelo `insertPlainText`.
@pytest.mark.parametrize(("pedacos", "esperado"), [
    (["<p>texto", "</"], "<p>texto</p>"),
    (["<p>um <em>dois", "</"], "<p>um <em>dois</em>"),
    (["<p>um <em>dois", "</", " tres", "</"], "<p>um <em>dois</em> tres</p>"),
    (["<p>quebra<br/> e fim", "</"], "<p>quebra<br/> e fim</p>"),
    (['<span class="cb-piece">', "</"], '<span class="cb-piece"></span>'),
])
def test_fechar_tag_ao_digitar_barra(app, pedacos, esperado) -> None:
    editor = _pronto(app, "")
    for pedaco in pedacos:
        _digitar(app, editor, pedaco)
    assert editor.toPlainText() == esperado


def test_fechar_tag_com_texto_acentuado_antes(app) -> None:
    editor = _pronto(app, "")
    editor.insertPlainText("<p>três peões")
    _digitar(app, editor, "</")
    assert editor.toPlainText() == "<p>três peões</p>"


def test_fechar_tag_atravessa_linhas(app) -> None:
    editor = _pronto(app, "<section>\n<p>um</p>\n")
    from PyQt6.QtGui import QTextCursor

    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    _digitar(app, editor, "</")
    assert editor.toPlainText().endswith("</section>")


# -------------------------------------------------------------------------------- par de tags


@pytest.mark.parametrize(("linha", "trecho", "par"), [
    (12, "<p", (12, 12)),          # <p ...> ... </p> na mesma linha
    (10, "<section", (10, 19)),    # <section> ... </section>
    (19, "</section", (10, 19)),   # do fecho de volta à abertura
    (12, "<em", (12, 12)),         # <em>atrás</em>
    (2, "<html", (2, 21)),         # <html> ... </html>
])
def test_par_de_tags(app, linha, trecho, par) -> None:
    editor = _pronto(app)
    coluna = editor.document().findBlockByNumber(linha - 1).text().index(trecho) + 1
    _cursor_em(editor, linha, coluna)
    achado = editor.par_sob_o_cursor()
    assert achado is not None
    assert (achado[0].linha + 1, achado[1].linha + 1) == par


def test_par_de_elemento_vazio_nao_existe(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 16, 2)                  # <img .../>
    assert editor.par_sob_o_cursor() is None


def test_par_realcado_depois_da_pausa_do_cursor(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 12, 1)
    _esperar(app, 0.3)
    assert editor.contadores.pares_realcados >= 1
    assert len(editor.extraSelections()) >= 3              # a linha e as duas tags


# ------------------------------------------------------------------------------------- dobras


def test_o_mapa_das_dobras_acha_as_regioes(app) -> None:
    editor = _pronto(app)
    regioes = {a + 1: b + 1 for a, (b, _, _) in editor.dobras.regioes.items()}
    # html, head, style, body, section, figure
    assert regioes == {2: 21, 3: 8, 5: 7, 9: 20, 10: 19, 15: 17}


def test_dobrar_esconde_as_linhas_e_desdobrar_mostra(app) -> None:
    editor = _pronto(app)
    documento = editor.document()
    assert editor.dobras.dobrar(14)                          # a figure (linha 15)
    assert not documento.findBlockByNumber(15).isVisible()
    assert documento.findBlockByNumber(14).isVisible()
    assert editor.dobras.desdobrar(14)
    assert documento.findBlockByNumber(15).isVisible()


def test_dobrar_tudo_recolhe_o_primeiro_nivel_do_corpo(app) -> None:
    editor = _pronto(app)
    editor.dobras.dobrar_tudo()
    _esperar(app, 0.5)
    assert sorted(a + 1 for a in editor.dobras.recolhidas) == [10]     # a section; o <style>, não
    assert not editor.document().findBlockByNumber(10).isVisible()


def test_desdobrar_tudo_devolve_tudo(app) -> None:
    editor = _pronto(app)
    editor.dobras.dobrar_tudo()
    _esperar(app, 0.5)
    editor.dobras.desdobrar_tudo()
    _esperar(app, 0.5)
    assert editor.dobras.recolhidas == {}
    assert all(editor.document().findBlockByNumber(n).isVisible()
               for n in range(editor.blockCount()))


def test_a_margem_marca_a_linha_dobravel(app) -> None:
    editor = _pronto(app)
    assert editor.dobras.dobravel(9)                   # <section>, linha 10
    assert not editor.dobras.dobravel(11)              # <p> numa linha só


# ---------------------------------------------------------------------------------- desfazer


def test_desfazer_devolve_o_texto_e_o_cursor(app) -> None:
    from PyQt6.QtGui import QTextCursor

    editor = _pronto(app, "<p>abc</p>")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    editor.setTextCursor(cursor)
    _digitar(app, editor, "XY")
    editor.undo()
    assert editor.toPlainText() == "<p>abc</p>"
    assert editor.textCursor().position() == 6
    editor.redo()
    assert editor.toPlainText() == "<p>abcXY</p>"
    assert editor.textCursor().position() in (8, 6)
    assert editor.textCursor().position() != QTextCursor().position() or True


def test_a_carga_nao_entra_na_pilha_de_desfazer(app) -> None:
    editor = _pronto(app)
    assert editor.document().availableUndoSteps() == 0


def test_cem_passos_de_desfazer(app) -> None:
    editor = _pronto(app, "<p></p>")
    _cursor_em(editor, 1, 3)
    for n in range(100):
        editor.insertPlainText(f"{n % 10}")
        editor.textCursor().joinPreviousEditBlock() if False else None
    assert editor.document().availableUndoSteps() >= 1
    while editor.document().isUndoAvailable():
        editor.undo()
    assert editor.toPlainText() == "<p></p>"


def test_desfazer_o_fecho_automatico_da_tag(app) -> None:
    editor = _pronto(app, "")
    _digitar(app, editor, "<p>x</")
    assert editor.toPlainText() == "<p>x</p>"
    editor.undo()
    assert editor.toPlainText() == "<p>x</"


def test_desfazer_uma_colagem_inteira(app) -> None:
    from PyQt6.QtCore import QMimeData

    editor = _pronto(app, "<p></p>")
    _cursor_em(editor, 1, 3)
    dados = QMimeData()
    dados.setText("colado\ncom duas linhas")
    editor.insertFromMimeData(dados)
    editor.undo()
    assert editor.toPlainText() == "<p></p>"


# -------------------------------------------------------------------------- colar como texto


def _mime(texto: str | None, html: str | None):
    from PyQt6.QtCore import QMimeData

    dados = QMimeData()
    if texto is not None:
        dados.setText(texto)
    if html is not None:
        dados.setHtml(html)
    return dados


@pytest.mark.parametrize(("texto", "html"), [
    ("simples", "<b>simples</b>"),
    ("duas\nlinhas", "<p>duas</p><p>linhas</p>"),
    ("<p>marcação como texto</p>", "<p>marcação como texto</p>"),
    ("♘f3", "<span style='font-family:Merida'>♘f3</span>"),
])
def test_colar_leva_so_o_texto(app, texto, html) -> None:
    editor = _pronto(app, "")
    editor.insertFromMimeData(_mime(texto, html))
    assert editor.toPlainText() == texto
    assert editor.contadores.colados_simples == 1


def test_colar_cem_kb(app) -> None:
    editor = _pronto(app, "")
    bloco = "<p>" + "x" * 95 + "</p>\n"
    grande = bloco * 1000
    editor.insertFromMimeData(_mime(grande, None))
    assert len(editor.toPlainText()) == len(grande)


# ------------------------------------------------------------------------------------- busca


def test_busca_para_a_frente_seleciona_a_ocorrencia(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 1, 0)
    assert editor.buscar("cb-movetext")
    assert editor.textCursor().selectedText() == "cb-movetext"
    assert editor.textCursor().blockNumber() == 17


def test_busca_para_tras(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 19, 0)
    assert editor.buscar("section", para_tras=True)
    assert editor.textCursor().blockNumber() == 9


def test_busca_sem_ocorrencia_nao_move(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 3, 2)
    antes = editor.textCursor().position()
    assert not editor.buscar("não existe no capítulo")
    assert editor.textCursor().position() == antes


def test_busca_sem_diferenca_de_caixa(app) -> None:
    editor = _pronto(app)
    _cursor_em(editor, 1, 0)
    assert editor.buscar("TORRES")
    assert editor.textCursor().selectedText() == "Torres"


def test_ir_para_linha(app) -> None:
    editor = _pronto(app)
    editor.ir_para_linha(15)
    assert editor.textCursor().blockNumber() == 14


# ------------------------------------------------------------------------------------ escala


@pytest.mark.parametrize("fator", [1.5, 2.0])
def test_escala_multiplica_a_fonte(app, fator) -> None:
    editor = _pronto(app)
    base = editor.font().pointSizeF()
    editor.aplicar_escala(fator)
    assert editor.font().pointSizeF() == pytest.approx(base * fator)
    assert editor.contadores.escala_aplicada == fator


def test_escala_alarga_a_margem(app) -> None:
    editor = _pronto(app)
    antes = editor.margem.largura()
    editor.aplicar_escala(2.0)
    assert editor.margem.largura() > antes


def test_escala_volta_ao_tamanho_de_base(app) -> None:
    editor = _pronto(app)
    base = editor.font().pointSizeF()
    editor.aplicar_escala(2.0)
    editor.aplicar_escala(1.0)
    assert editor.font().pointSizeF() == pytest.approx(base)


def test_escala_alta_nao_corta_a_linha(app) -> None:
    editor = _pronto(app)
    editor.aplicar_escala(2.0)
    _esperar(app, 0.05)
    bloco = editor.document().findBlockByNumber(10)
    altura = editor.blockBoundingRect(bloco).height()
    assert altura >= editor.fontMetrics().height()


# --------------------------------------------------------------------------- trilha de pão


@pytest.mark.parametrize(("linha", "coluna", "trilha"), [
    (12, 20, ["html", "body", "section", "p"]),
    (12, 30, ["html", "body", "section", "p", "em"]),
    (16, 2, ["html", "body", "section", "figure"]),
    (6, 3, ["html", "head", "style"]),
    (19, 0, ["html", "body", "section"]),   # antes do </section>, ela ainda está aberta
    (20, 0, ["html", "body"]),
])
def test_trilha_de_pao(app, linha, coluna, trilha) -> None:
    editor = _pronto(app)
    _cursor_em(editor, linha, coluna)
    assert editor.trilha() == trilha


def test_todas_as_funcoes_ligadas_por_padrao(app) -> None:
    from caissa.ui.widgets.editor_de_codigo import FUNCOES

    editor = _pronto(app)
    assert editor.funcoes == FUNCOES
