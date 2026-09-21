"""OCR_UI ciclo 2, A13: uma pasta por importação; um rodapé só ao trocar de livro.

O crítico da fase 1 (itens 5 e 6) mediu duas coisas: uma pasta por processo para todas as
importações -- reimportar o mesmo livro enquanto a exportação do resultado anterior ainda lia
as imagens sobrescrevia ``diagrama-p31-0001.png`` sob o mesmo nome -- e duas frases
contraditórias no rodapé em 1 s ao abrir outro livro («podem ser exportadas» e, logo a seguir,
«descartada»).  Aqui: a pasta muda a cada importação e a frase da promessa cala quando o
cancelamento foi por troca de livro.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from caissa.ui.views.importacao import _nome_seguro, _pasta_de_recursos, pasta_da_importacao


def test_every_import_gets_its_own_folder_under_the_process_root() -> None:
    livro = Path("C:/livros/Kemeri 1937.pdf")
    primeira = pasta_da_importacao(livro)
    segunda = pasta_da_importacao(livro)
    outro = pasta_da_importacao(Path("C:/livros/Aagaard.pdf"))
    assert primeira != segunda, "reimportar o mesmo livro não pode reutilizar a pasta"
    assert primeira.parent == segunda.parent == outro.parent == _pasta_de_recursos()
    assert primeira.name.startswith(_nome_seguro(livro.stem) + "-")
    assert outro.name.startswith(_nome_seguro("Aagaard") + "-")


PyQt6 = pytest.importorskip(
    "PyQt6", reason="o importador da janela é um QObject; o .venv da suíte não tem PyQt6"
)


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _resultado_cancelado(planned: int = 8):
    from caissa.core.model import Document
    from caissa.ingest.pdf.importer import ImportReport, ImportResult

    report = ImportReport(canceled=True, pages_planned=planned)
    return ImportResult(document=Document(), report=report)


def test_a_cancel_for_a_book_switch_makes_no_export_promise(app) -> None:
    from caissa.ui.views.importacao import ImportadorDoLivro

    importador = ImportadorDoLivro(None)
    frases: list[str] = []
    importador.estado.connect(frases.append)
    importador._rodando = True
    importador._cancelar = __import__("threading").Event()

    importador.cancelar(motivo="troca_de_livro")
    assert not frases, "quem trocou de livro já disse a frase; o importador cala"
    importador._concluiu(_resultado_cancelado())
    assert not any("podem ser exportadas" in f for f in frases), frases

    # O cancelamento comum continua a dizer o que fica.
    importador._rodando = True
    importador._cancelar = __import__("threading").Event()
    importador.cancelar()
    assert any("Cancelando" in f for f in frases)
    importador._concluiu(_resultado_cancelado())
    assert any("podem ser exportadas" in f for f in frases)
