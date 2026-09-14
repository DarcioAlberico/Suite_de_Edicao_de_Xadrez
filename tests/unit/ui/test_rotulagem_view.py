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
    dialogo.for_book.setChecked(False)
    assert not dialogo.out_edit.text().endswith("livro_x")
    dialogo.close()
    painel.close()
