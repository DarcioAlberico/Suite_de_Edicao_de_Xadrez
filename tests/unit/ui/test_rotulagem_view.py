"""A aba Rotulagem (PyQt6) monta sobre o projeto, e as decisões que ela toma são as da
bancada Tk — porque as duas chamam os mesmos módulos sem toolkit.

Sem PyQt6 no ambiente (o `.venv` da suíte não o tem, de propósito) os testes de janela
pulam; os das funções compartilhadas rodam sempre.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from caissa.ocr.labeling import LineStatus
from caissa.ocr.labeling.helpers import (
    FIGURINE_KEYS,
    STATUS_COLOR,
    default_project_dir,
    fen_problem,
    letters_to_figurines,
    status_pt,
)
from caissa.ocr.training.negatives import RECOMMENDED_NEGATIVES

# --------------------------------------------------------------------------- #
# Shared, toolkit-free
# --------------------------------------------------------------------------- #


def test_letters_become_figurines_only_where_a_move_starts():
    assert letters_to_figurines("22...Bf8 Nf3 e4 Kg1") == "22...♗f8 ♘f3 e4 ♔g1"
    assert letters_to_figurines("Black is Better") == "Black is Better"
    assert letters_to_figurines("♖e8!") == "♖e8!"


def test_fen_problem_and_status_names():
    assert fen_problem("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1") == ""
    assert fen_problem("not a fen").startswith("FEN")
    assert status_pt(LineStatus.EDITED) == "editada"
    assert set(STATUS_COLOR) == set(LineStatus)
    assert "".join(FIGURINE_KEYS.values()) == "♔♕♖♗♘♙"


def test_default_project_dir_is_the_repository_labeling_folder_in_a_checkout():
    assert default_project_dir().name == "labeling"
    assert (default_project_dir().parent / "pyproject.toml").is_file()


# --------------------------------------------------------------------------- #
# The Qt tab
# --------------------------------------------------------------------------- #

PyQt6 = pytest.importorskip("PyQt6", reason="a aba Rotulagem é PyQt6; o .venv da suíte não o tem")


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_tab_mounts_on_an_empty_project_and_names_its_controls(app, tmp_path: Path):
    from caissa.ui.views.rotulagem import TITULO, DialogoDeTreino, PainelDeRotulagem, abrir_projeto

    project = abrir_projeto(tmp_path / "proj", revisor="ana")
    painel = PainelDeRotulagem(projeto=project)
    painel.show()
    app.processEvents()
    assert TITULO == "Rotulagem"
    assert painel.document is None
    assert "F5 reconhece" in painel.status.text()
    assert painel.table.rowCount() == 0
    assert painel.visor.accessibleName()
    assert painel.truth.accessibleName() == "Verdade da linha"
    dialogo = DialogoDeTreino(painel, project, document=None)
    assert not dialogo.for_book.isEnabled(), "no book open: nothing to bind the model to"
    assert dialogo._config().documents == ()
    dialogo.close()
    painel.close()


def test_the_key_walks_the_tab_both_ways_with_every_control_in_sight(app, tmp_path: Path):
    """OCR_UI ciclo 2, fase 5, crítico do ciclo 4: the `teclado` gate, pressing the real key, put
    the focus on «Leitura do motor» with 0 px on screen at 1280x641 -- the card lives in a scroll
    area, and the scroll area only follows the focus that moves inside it.  Walked with the gate's
    own instrument (``QTest.keyClick``, Tab and Shift+Tab) on a window short enough to scroll: no
    control takes the key and keeps it, and each one is on screen when it takes the focus.  The
    sabotage: the scroll area no longer follows the focus that comes from outside."""
    from caissa.ui.audit import teclado
    from caissa.ui.views.rotulagem import PainelDeRotulagem, abrir_projeto

    painel = PainelDeRotulagem(projeto=abrir_projeto(tmp_path / "proj", revisor="ana"))
    painel.resize(1000, 360)
    painel.show()
    app.processEvents()
    focaveis = teclado._focaveis(painel)
    for de_volta in (False, True):
        volta = teclado._volta_da_tecla(painel, focaveis, de_volta=de_volta)
        assert volta.passou(), volta
    painel._segue_o_foco.desligar()
    escondidos = []
    for de_volta in (False, True):
        for barra in painel.findChildren(type(painel.truth.verticalScrollBar())):
            barra.setValue(0)
        app.processEvents()
        escondidos += teclado._volta_da_tecla(painel, focaveis, de_volta=de_volta).escondidos
    assert escondidos, "without the filter the focus hides below the fold"
    painel.close()


class _PaginaDeLinhas:
    """A service that reads ``n`` lines in one region: the tab in its working state, the table
    full -- the critic of cycle 5 recognised the Gallagher p. 51 in the panel itself (66 lines),
    where the gate and the test above had only ever measured the empty table."""

    lang = "eng"

    def __init__(self, n: int = 12) -> None:
        self.n = n

    def recognize_image(self, image, *, dpi, lang="", page_index=0):
        from types import SimpleNamespace

        from caissa.ocr.types import BBox

        s = dpi / 72.0
        linhas = []
        for k in range(self.n):
            y = (60 + 14 * k) * s
            words = (
                SimpleNamespace(text=f"linha{k}", confidence=0.5,
                                box=BBox(50 * s, y, 40 * s, 10 * s)),
                SimpleNamespace(text="fraca", confidence=0.4, box=BBox(95 * s, y, 30 * s, 10 * s)),
            )
            linhas.append(SimpleNamespace(words=words, text=f"linha{k} fraca", confidence=0.4,
                                          box=BBox(50 * s, y, 75 * s, 10 * s), block_index=0,
                                          paragraph_index=0))
        result = SimpleNamespace(lines=tuple(linhas))
        decision = SimpleNamespace(decision="review", reasons_pt=())
        region = SimpleNamespace(reading_order=0, kind="paragraph",
                                 box_px=BBox(0, 0, 400 * s, 600 * s), result=result,
                                 decision=decision, engine="tesseract", variant="original",
                                 score=0.5,
                                 candidates=(SimpleNamespace(variant="original", engine="tesseract",
                                                             result=result),))
        return SimpleNamespace(dpi=dpi, regions=[region], engines={"tesseract": "5.5"}, notes=[])


def _rotulagem_com_linhas(app, tmp_path: Path, n: int = 12):
    """The tab with a book open and its page recognised by the panel itself (F5), ``n`` lines."""
    import time

    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ui.views.rotulagem import PainelDeRotulagem, abrir_projeto

    pdf = tmp_path / "Livro L.pdf"
    doc = pymupdf.open()
    doc.new_page(width=400, height=600)
    doc.save(pdf)
    doc.close()
    project = abrir_projeto(tmp_path / "proj", revisor="ana")
    project.languages["Livro L"] = "eng"
    painel = PainelDeRotulagem(projeto=project, pdf_inicial=pdf)
    painel.show()
    app.processEvents()
    painel.service = _PaginaDeLinhas(n)
    painel.recognise_page()
    deadline = time.monotonic() + 30
    while painel.fila.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    assert painel.table.rowCount() == n
    return painel


def _no_topo(painel, app) -> None:
    """Every scroll area as the user finds it: at the top."""
    from PyQt6.QtWidgets import QScrollArea

    for rolagem in painel.findChildren(QScrollArea):
        rolagem.verticalScrollBar().setValue(0)
        rolagem.horizontalScrollBar().setValue(0)
    app.processEvents()


def test_with_a_page_of_lines_the_key_walks_every_control_both_ways_in_sight(app, tmp_path: Path):
    """OCR_UI ciclo 2, fase 5, crítico do ciclo 5: with a page recognised (66 lines of the Gallagher
    p. 51), Tab went from cell to cell of «Linhas da página» -- the Qt default -- and every change
    of line sent the focus to «Verdade da linha»: the key never left the loop, and Shift+Tab reached
    23 of 37 controls, never the figurines nor the six actions.  The test above measured the empty
    table.  Walked with the gate's instrument, both ways, every scroll area at the top before each
    way: every control reached, each on screen when it takes the focus.  The sabotage: the table
    keeps the Tab again."""
    from caissa.ui.audit import teclado

    painel = _rotulagem_com_linhas(app, tmp_path)
    painel.resize(1000, 360)
    app.processEvents()
    focaveis = teclado._focaveis(painel)
    assert painel.table in focaveis
    # a stop per control: the editable combo box and its line edit are one (the focus proxy)
    paradas = len({id(w.focusProxy() or w) for w in focaveis})
    for de_volta in (False, True):
        _no_topo(painel, app)
        volta = teclado._volta_da_tecla(painel, focaveis, de_volta=de_volta)
        assert volta.passou(), volta
        assert volta.alcancados == paradas, (de_volta, volta.alcancados, paradas)
    painel.table.setTabKeyNavigation(True)
    voltas = []
    for de_volta in (False, True):
        _no_topo(painel, app)
        voltas.append(teclado._volta_da_tecla(painel, focaveis, de_volta=de_volta))
    assert not all(v.passou() and v.alcancados == paradas for v in voltas), voltas
    painel.close()


def test_the_arrows_walk_the_lines_with_the_focus_in_the_table_and_enter_goes_to_the_truth(
        app, tmp_path: Path, monkeypatch):
    """Crítico da fase 5, ciclo 5 (the same in «Revisão de texto»): the first arrow in the table
    moved to the next line and sent the focus to the truth field, where the next arrows stayed.
    The arrows walk the lines and the card follows them; Enter takes the focus to the truth.  The
    sabotage: the card takes the focus on every line, as before."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    import caissa.ui.views.rotulagem as vista

    painel = _rotulagem_com_linhas(app, tmp_path)
    painel.table.setFocus()
    app.processEvents()
    vistas = [painel.current[1]]
    for _ in range(3):
        QTest.keyClick(painel.table, Qt.Key.Key_Down)
        app.processEvents()
        assert app.focusWidget() is painel.table, "the arrow keeps the focus in the table"
        assert painel.current[1] is not vistas[-1], "the arrow moved to the next line"
        assert painel.truth.toPlainText() == painel.current[1].hypothesis, "the card follows"
        vistas.append(painel.current[1])
    QTest.keyClick(painel.table, Qt.Key.Key_Return)
    app.processEvents()
    assert app.focusWidget() is painel.truth
    monkeypatch.setattr(vista, "pelas_setas", lambda _tabela: False)
    painel.table.setFocus()
    app.processEvents()
    QTest.keyClick(painel.table, Qt.Key.Key_Down)
    app.processEvents()
    assert app.focusWidget() is painel.truth, "sabotaged: the card takes the focus"
    painel.close()


def test_the_tab_opens_a_book_and_defaults_training_to_it(app, tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ui.views.rotulagem import DialogoDeTreino, PainelDeRotulagem, abrir_projeto

    pdf = tmp_path / "Livro X.pdf"
    doc = pymupdf.open()
    doc.new_page(width=400, height=600)
    doc.new_page(width=400, height=600)
    doc.save(pdf)
    doc.close()
    project = abrir_projeto(tmp_path / "proj", revisor="ana")
    project.languages["Livro X"] = "eng"
    painel = PainelDeRotulagem(projeto=project, pdf_inicial=pdf)
    painel.show()
    app.processEvents()
    assert painel.document == "Livro X"
    assert painel.page_total.text() == "/ 1"
    assert painel.lang_box.currentText() == "eng"
    painel.go_page(5)
    assert painel.page_index == 1, "clamped to the last page"
    painel.toggle_drawing()
    assert painel.visor.desenhando and painel.page is not None
    painel._stop_drawing()
    assert not painel.visor.desenhando
    dialogo = DialogoDeTreino(painel, project, document="Livro X")
    assert dialogo.for_book.isChecked()
    assert dialogo.out_edit.text().endswith(os.path.join("livros", "livro_x"))
    assert dialogo.base_lang.currentText() == "eng"
    assert dialogo._config().documents == ("Livro X",)
    assert dialogo.negatives.value() == RECOMMENDED_NEGATIVES
    dialogo.negatives.setValue(40)
    dialogo.oversample.setValue(1.5)
    assert (dialogo._config().negatives, dialogo._config().oversample_rare) == (40, 1.5)
    dialogo.for_book.setChecked(False)
    assert not dialogo.out_edit.text().endswith("livro_x")
    dialogo.close()
    painel.close()


def test_abrir_selects_the_book_without_writing_the_project(app, tmp_path: Path):
    """OCR_UI ciclo 2, passo C7: the window opens one book and this tab follows it.
    Merely looking at a book must not enrol it in ``labeling/``: the project file is
    written only by *Abrir PDF…* (``gravar=True``) or by the first label decided."""
    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ui.views.rotulagem import PainelDeRotulagem, abrir_projeto

    pdf = tmp_path / "Livro Y.pdf"
    doc = pymupdf.open()
    doc.new_page(width=400, height=600)
    doc.save(pdf)
    doc.close()
    project = abrir_projeto(tmp_path / "proj", revisor="ana")
    project.save()
    arquivo = tmp_path / "proj" / "project.json"
    antes = arquivo.read_text(encoding="utf-8")
    painel = PainelDeRotulagem(projeto=project)
    painel.show()
    app.processEvents()
    assert painel.abrir(pdf) == "Livro Y"
    assert painel.document == "Livro Y"
    assert painel.doc_box.currentText() == "Livro Y"
    assert "Livro Y" in project.documents
    assert arquivo.read_text(encoding="utf-8") == antes, "looking at a book wrote the project"
    painel.abrir(pdf, gravar=True)
    assert "Livro Y" in arquivo.read_text(encoding="utf-8")
    painel.close()


class _QueueFakeService:
    """A service whose every region is ``REVIEW`` with one weak word — enough
    for the queue to have something to rank — and page 2 clean."""

    lang = "eng"

    def __init__(self) -> None:
        self.seen: list[int] = []

    def recognize_image(self, image, *, dpi, lang="", page_index=0):
        from types import SimpleNamespace

        from caissa.ocr.types import BBox

        self.seen.append(page_index)
        clean = page_index == 2
        scale = dpi / 72.0
        words = (
            SimpleNamespace(text="Olá", confidence=0.98,
                            box=BBox(50 * scale, 100 * scale, 30 * scale, 10 * scale)),
            SimpleNamespace(text="mundo", confidence=0.99 if clean else 0.4,
                            box=BBox(85 * scale, 100 * scale, 40 * scale, 10 * scale)),
        )
        line = SimpleNamespace(words=words, text="Olá mundo",
                               confidence=min(w.confidence for w in words),
                               box=BBox(50 * scale, 100 * scale, 75 * scale, 10 * scale),
                               block_index=0, paragraph_index=0)
        result = SimpleNamespace(lines=(line,))
        decision = SimpleNamespace(decision="accepted" if clean else "review", reasons_pt=())
        region = SimpleNamespace(reading_order=0, kind="paragraph",
                                 box_px=BBox(0, 0, 400 * scale, 600 * scale), result=result,
                                 decision=decision, engine="tesseract", variant="original",
                                 score=0.9 if clean else 0.5,
                                 candidates=(SimpleNamespace(variant="original", engine="tesseract",
                                                             result=result),))
        return SimpleNamespace(dpi=dpi, regions=[region], engines={"tesseract": "5.5"}, notes=[])


def test_the_queue_button_scores_the_book_in_a_thread_and_opens_the_best_page(app, tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ui.views.rotulagem import DialogoDaFila, PainelDeRotulagem, abrir_projeto

    pdf = tmp_path / "Livro Q.pdf"
    doc = pymupdf.open()
    for _ in range(6):
        doc.new_page(width=400, height=600)
    doc.save(pdf)
    doc.close()
    project = abrir_projeto(tmp_path / "proj", revisor="ana")
    project.languages["Livro Q"] = "eng"
    painel = PainelDeRotulagem(projeto=project, pdf_inicial=pdf)
    painel.show()
    app.processEvents()
    painel.service = _QueueFakeService()
    painel.dpi_spin.setValue(150)
    assert painel.queue_button.text() == "Próxima que vale"
    painel.next_valuable()
    assert painel.queue_button.text() == "Cancelar fila", "a click during scoring cancels"
    import time

    deadline = time.monotonic() + 30
    while painel.fila.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    assert painel.ranking is not None
    assert not painel.ranking.cancelled
    assert painel.queue_button.text() == "Próxima que vale"
    # A six-page book sampled at twelve: every page but the labelled ones; page 2 is clean.
    assert painel.ranking.values[-1].page_index == 2
    dialogo = next(d for d in painel.findChildren(DialogoDaFila))
    assert dialogo.lista.count() == len(painel.ranking.values)
    assert dialogo.lista.currentRow() == 0
    dialogo.abrir()
    assert painel.page_index == painel.ranking.values[0].page_index
    assert "Fila: p." in painel.status.text()
    # The second click reopens the list without scoring again.
    seen = list(painel.service.seen)
    painel.next_valuable()
    app.processEvents()
    assert painel.service.seen == seen
    for d in painel.findChildren(DialogoDaFila):
        d.close()
    painel.close()
