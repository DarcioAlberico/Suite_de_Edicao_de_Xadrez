"""O diálogo *Exportar livro…* e o controlador que roda a exportação numa thread.

Sem PyQt6 no ambiente (o `.venv` da suíte não o tem, de propósito) tudo aqui pula. Para
rodar: o `.venv-pack` tem o PyQt6 do bundle e o mesmo numpy, então basta emprestá-lo::

    $env:PYTHONPATH = ".venv-pack\\Lib\\site-packages"
    .venv\\Scripts\\python.exe -m pytest tests\\unit\\ui\\test_exportacao_view.py -q
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

PyQt6 = pytest.importorskip("PyQt6", reason="o diálogo é PyQt6; o .venv da suíte não o tem")
pymupdf = pytest.importorskip("pymupdf")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def livro(tmp_path: Path) -> Path:
    pdf = tmp_path / "Livro X.pdf"
    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=400, height=600)
        page.insert_text((40, 80), f"Página {i + 1} do livro com texto de verdade.", fontsize=11)
    doc.save(pdf)
    doc.close()
    return pdf


def test_the_dialog_starts_on_the_whole_book_and_names_the_file(app, livro: Path):
    from caissa.ui.views.exportacao import DialogoDeExportacao

    dialogo = DialogoDeExportacao(None, livro, 5, formato="docx", pagina_atual=2)
    assert dialogo.formato == "docx"
    assert dialogo.completo.isChecked()
    assert dialogo.paginas() == (0, 1, 2, 3, 4)
    assert dialogo.destino.text() == str(livro.with_suffix(".docx"))
    assert dialogo.de.value() == 3, "the page on screen, one-based"
    assert dialogo.ate.value() == 5
    for widget in (dialogo.de, dialogo.ate, dialogo.lista_edit, dialogo.destino, dialogo.ocr):
        assert widget.accessibleName()
    # Botão feito à mão: o tronco retraduz botões padrão ao mostrar o diálogo (F9-C14) e um
    # Ok renomeado voltava a dizer «OK» no Caissa.exe.
    from PyQt6.QtWidgets import QDialogButtonBox

    caixa = dialogo.botao_exportar.parent()
    assert caixa.standardButton(dialogo.botao_exportar) == QDialogButtonBox.StandardButton.NoButton
    assert dialogo.botao_exportar.text() == "Exportar"
    dialogo.close()


def test_touching_a_counter_picks_the_range_and_renames_the_file(app, livro: Path):
    from caissa.ui.views.exportacao import DialogoDeExportacao

    dialogo = DialogoDeExportacao(None, livro, 5)
    dialogo.ate.setValue(3)
    assert dialogo.intervalo.isChecked()
    assert dialogo.paginas() == (0, 1, 2)
    assert dialogo.destino.text() == str(livro.with_name("Livro X (p. 1-3).epub"))
    dialogo.botao_formato["docx"].setChecked(True)
    assert dialogo.destino.text() == str(livro.with_name("Livro X (p. 1-3).docx"))
    dialogo.completo.setChecked(True)
    assert dialogo.destino.text() == str(livro.with_suffix(".docx"))
    escolha = dialogo.escolha()
    assert escolha.formato == "docx"
    assert escolha.alcance == "livro completo"
    assert escolha.ocr
    dialogo.close()


def test_a_typed_name_is_kept_and_a_bad_list_blocks_accept(app, livro: Path, tmp_path: Path):
    from caissa.ui.views.exportacao import DialogoDeExportacao

    dialogo = DialogoDeExportacao(None, livro, 5)
    dialogo.destino.setText(str(tmp_path / "meu nome"))
    dialogo.destino.textEdited.emit(dialogo.destino.text())
    dialogo.ate.setValue(2)
    assert dialogo.destino.text() == str(tmp_path / "meu nome"), "a name the person typed stays"

    dialogo.lista_edit.setText("2-9")
    dialogo.lista_edit.textEdited.emit("2-9")
    assert dialogo.lista.isChecked()
    dialogo.accept()
    assert "não existe" in dialogo.aviso.text()
    assert dialogo.result() != dialogo.DialogCode.Accepted

    dialogo.lista_edit.setText("2, 4-5")
    dialogo.lista_edit.textEdited.emit("2, 4-5")
    dialogo.accept()
    assert dialogo.aviso.text() == ""
    assert dialogo.result() == dialogo.DialogCode.Accepted
    escolha = dialogo.escolha()
    assert escolha.paginas == (1, 3, 4)
    assert escolha.destino == tmp_path / "meu nome.epub", "the extension follows the format"
    dialogo.close()


def test_the_controller_exports_in_a_thread_and_ends_in_the_status_line(
    app, livro: Path, tmp_path: Path
):
    from caissa.ui.views.exportacao import EscolhaDeExportacao, ExportadorDeLivro

    exportador = ExportadorDeLivro(None)
    frases: list[str] = []
    resultados: list[object] = []
    trancas: list[bool] = []
    exportador.estado.connect(frases.append)
    exportador.terminou.connect(resultados.append)
    exportador.controles.connect(trancas.append)
    destino = tmp_path / "parte.epub"
    exportador.iniciar(
        livro,
        EscolhaDeExportacao("epub", (1, 2), destino, page_count=5, ocr=False),
    )
    assert exportador.rodando
    assert trancas == [False]
    limite = time.monotonic() + 30
    while exportador.rodando and time.monotonic() < limite:
        app.processEvents()
        time.sleep(0.02)
    assert not exportador.rodando
    assert trancas == [False, True]
    assert destino.is_file()
    assert len(resultados) == 1
    assert frases[0].startswith("Exportando Livro X.pdf para EPUB (2-3)")
    assert frases[-1].startswith(
        "Exportação concluída. EPUB gravado em parte.epub: 2 página(s) (2-3)"
    )
    assert not exportador.comecar(None, 5)
    assert frases[-1] == "Abra um PDF antes de exportar o livro."


def _esperar(app, exportador) -> None:
    limite = time.monotonic() + 30
    while exportador.rodando and time.monotonic() < limite:
        app.processEvents()
        time.sleep(0.02)
    assert not exportador.rodando


def test_the_notebook_pages_reach_the_book_and_a_failing_notebook_is_said(
    app, livro: Path, tmp_path: Path
):
    """R7 do tronco: as folhas do caderno da aba Texto entram no lugar da leitura."""
    from caissa.export import read_epub
    from caissa.ui.views.exportacao import EscolhaDeExportacao, ExportadorDeLivro

    exportador = ExportadorDeLivro(None)
    frases: list[str] = []
    resultados: list[object] = []
    exportador.estado.connect(frases.append)
    exportador.terminou.connect(resultados.append)
    pedidas: list[object] = []

    def folhas_para(paginas):
        pedidas.append(paginas)
        return [{"format": 1, "page_index": 1, "paragraphs": [
            {"kind": "text", "runs": [{"text": "Corrigida no caderno."}]}]}]

    destino = tmp_path / "caderno.epub"
    exportador.iniciar(livro, EscolhaDeExportacao("epub", (1, 2), destino, page_count=5, ocr=False),
                       folhas_para=folhas_para)
    _esperar(app, exportador)
    assert pedidas == [(1, 2)], "the range of the dialog, asked once on the window's thread"
    textos = ["".join(getattr(i, "content", "") for i in getattr(b, "content", ()))
              for b in read_epub(destino).body]
    assert "Corrigida no caderno." in textos
    assert not any(t.startswith("Página 2 ") for t in textos), "the reading of page 2 went"
    assert any(t.startswith("Página 3 ") for t in textos)
    assert "1 folha(s) com o texto corrigido no caderno" in frases[-1]

    def quebrado(_paginas):
        raise OSError("caderno travado")

    exportador.iniciar(livro, EscolhaDeExportacao("epub", (1,), tmp_path / "sem.epub", page_count=5,
                                                  ocr=False), folhas_para=quebrado)
    _esperar(app, exportador)
    assert any("caderno travado" in f and "leitura da importação" in f for f in frases)
    assert (tmp_path / "sem.epub").is_file(), "the book is still written, with the reading"


def test_the_tab_offers_the_book_export_from_its_menu(app, livro: Path, tmp_path: Path):
    from caissa.ui.views.rotulagem import PainelDeRotulagem, abrir_projeto

    project = abrir_projeto(tmp_path / "proj", revisor="ana")
    painel = PainelDeRotulagem(projeto=project, pdf_inicial=livro)
    painel.show()
    app.processEvents()
    textos = [
        acao.text()
        for botao in painel.findChildren(PyQt6.QtWidgets.QToolButton)
        if botao.text() == "Exportar" and botao.menu() is not None
        for acao in botao.menu().actions()
    ]
    assert "Livro para EPUB…" in textos
    assert "Livro para DOCX…" in textos
    assert painel.exportador_de_livro is not None

    # R7 do tronco: com quem dê as folhas do caderno, a aba as pede pelo livro do projeto dela.
    pedidos: list[tuple[Path, object]] = []
    painel.folhas_para = lambda pdf, paginas: pedidos.append((pdf, paginas)) or []
    chamadas: list[dict[str, object]] = []
    painel.exportador_de_livro.comecar = lambda *a, **k: chamadas.append(k) or True
    assert painel.export_book("docx")
    folhas = chamadas[-1]["folhas_para"]
    assert callable(folhas)
    folhas((0, 2))
    assert pedidos == [(Path(painel.project.pdf_for(painel.document)), (0, 2))]
    painel.folhas_para = None
    painel.export_book("epub")
    assert chamadas[-1]["folhas_para"] is None, "sozinha, a aba exporta a leitura"

    painel.document = None
    assert not painel.export_book("epub")
    assert "Abra um PDF" in painel.status.text()
    painel.close()
