"""OCR_UI_ROADMAP passo 14: the text-review window visits the doubtful regions — N and
only N — decides them over ``ReviewQueue``, refuses a correction on a blind page with
the phrase, saves every decision, and measures the time per page.

Sem PyQt6 no ambiente (o ``.venv`` da suíte não o tem, de propósito) os testes de
janela pulam; os das funções compartilhadas rodam sempre.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from caissa.ocr.golden import Partition, partition_for
from caissa.ocr.review import Action, blind_guard
from caissa.ui.widgets.cartao_da_linha import leitura_em_html

# --------------------------------------------------------------------------- #
# Shared, toolkit-free
# --------------------------------------------------------------------------- #


def test_the_reading_html_paints_weak_words_conferir_and_very_weak_revisar():
    """A regra do editor de texto do tronco (`ui/texto_cores.py`): a confiança vai na **letra**
    (`conferir` em `ATENCAO`, `revisar` em `PROBLEMA_TEXTO`), nunca no fundo, que é o canal do
    autor. Os hexadecimais vêm da pele em vigor -- o tronco quando está ao alcance, a reserva
    da suíte quando não --, por isso o teste pergunta à pele em vez de fixá-los."""
    from caissa.ui.theme import pele

    html = leitura_em_html([("the", 0.9), ("r0ok", 0.4), ("belongs", 0.2)], 0.5)
    assert html.startswith("the ")
    assert f'<span style="color:{pele.cor("cartao_palavra_conferir")}">r0ok</span>' in html
    assert f'<span style="color:{pele.cor("cartao_palavra_revisar")}">belongs</span>' in html
    assert pele.cor("cartao_palavra_conferir") != pele.cor("cartao_palavra_revisar")
    assert "background:" not in html
    assert leitura_em_html([], 0.5, fallback="a < b") == "a &lt; b"


# --------------------------------------------------------------------------- #
# The Qt panel
# --------------------------------------------------------------------------- #

PyQt6 = pytest.importorskip(
    "PyQt6", reason="a janela de revisão é PyQt6; o .venv da suíte não o tem"
)


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "Livro X.pdf"
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page(width=612, height=792)
    doc.save(path)
    doc.close()
    return path


def _report(pages=(0, 1, 2)):
    """Three doubtful regions on three pages: one abstained, two for review."""
    items = [
        SimpleNamespace(
            page_index=pages[0],
            rect=(72.0, 100.0, 300.0, 112.0),
            kind="paragraph",
            decision="review",
            reasons=("Escore 0.70 abaixo do limite",),
            text="the r0ok belongs",
            engine="tesseract",
            score=0.70,
            alternatives=(("upscale/tesseract", "the rook belongs"),),
        ),
        SimpleNamespace(
            page_index=pages[1],
            rect=(72.0, 300.0, 300.0, 340.0),
            kind="movetext",
            decision="abstained",
            reasons=("Nenhum texto",),
            text="",
            engine="tesseract",
            score=0.1,
            alternatives=(),
        ),
        SimpleNamespace(
            page_index=pages[2],
            rect=(72.0, 20.0, 300.0, 60.0),
            kind="movetext",
            decision="review",
            reasons=("1 lance(s) sem leitura legal: Nz6",),
            text="1.e4 e5 2.Nf3 Nz6",
            engine="tesseract",
            score=0.82,
            alternatives=(),
        ),
    ]
    return SimpleNamespace(review_items=items, ocr_traces={}, pages=[1, 2, 3])


def _panel(app, pdf: Path, tmp_path: Path, *, cega=None, report=None):
    from caissa.ui.views.revisao_de_texto import PainelDeRevisaoDeTexto

    painel = PainelDeRevisaoDeTexto(
        revisor="ana", pdf_inicial=pdf, cega=cega or blind_guard(()), pasta=tmp_path / "proj"
    )
    painel.show()
    app.processEvents()
    painel._importado(SimpleNamespace(report=report or _report()))
    app.processEvents()
    return painel


def test_the_panel_mounts_names_its_controls_and_lists_n_and_only_n(app, pdf, tmp_path):
    from caissa.ui.views.revisao_de_texto import TITULO

    painel = _panel(app, pdf, tmp_path)
    assert TITULO == "Revisão de texto"
    assert painel.doc_label.text().startswith("Livro X.pdf · 3 páginas")
    assert painel.table.accessibleName() == "Dúvidas do livro"
    assert painel.cartao.verdade.accessibleName() == "Verdade da linha"
    assert painel.table.rowCount() == 3, "N doubtful regions, N rows — nothing else"
    assert "3 região(ões) em dúvida" in painel.status.text()
    painel._refresh_status()
    assert "0 decidida(s), 3 pendente(s) de 3" in painel.status.text()
    # The first pending item is selected and shown: the abstained one comes
    # first (highest risk), with its crop, its reasons and an empty truth.
    assert painel.current is not None
    assert painel.current.decision == "abstained"
    assert "abstained" in painel.cartao.contexto.text()
    assert "Nenhum texto" in painel.cartao.motivo.text()
    assert painel.cartao.recorte.pixmap() is not None
    assert not painel.cartao.recorte.pixmap().isNull()
    painel.close()


def _ordem_do_tab(painel) -> list:
    """The widgets Tab reaches from the table, in the focus chain's order."""
    from PyQt6.QtCore import Qt

    ordem, atual = [], painel.table
    while True:
        if atual.focusPolicy().value & Qt.FocusPolicy.TabFocus.value and atual.isVisible():
            ordem.append(atual)
        atual = atual.nextInFocusChain()
        if atual is painel.table or len(ordem) > 500:
            return ordem


def test_the_tab_order_follows_the_eye_table_card_then_the_actions(app, pdf, tmp_path, monkeypatch):
    """Crítico da fase 5, ciclo 3: taken out of the card's scroll (C18), the six actions entered
    the focus chain right after the table -- positions 11–16, the card 17–26 --, while the eye
    reads the card first and the actions below it."""
    from types import SimpleNamespace as Ns

    import caissa.ui.views.revisao_de_texto as vista

    painel = _panel(app, pdf, tmp_path)
    ordem = _ordem_do_tab(painel)
    cartao = [painel.cartao.leitura, painel.cartao.alternativas, painel.cartao.verdade]
    acoes = list(painel.acoes.values())
    posicoes = [ordem.index(w) for w in (painel.table, *cartao, *acoes)]
    assert posicoes == sorted(posicoes), "the table, the card top down, then the actions"
    figurinas = [w for w in ordem if painel.cartao.isAncestorOf(w)]
    assert max(ordem.index(w) for w in figurinas) < ordem.index(acoes[0])
    painel.close()
    # the sabotage: no explicit order -- the chain the widget tree leaves
    monkeypatch.setattr(vista, "itertools", Ns(pairwise=lambda _cadeia: ()))
    painel = _panel(app, pdf, tmp_path)
    ordem = _ordem_do_tab(painel)
    assert ordem.index(painel.acoes["Aceitar leitura"]) < ordem.index(painel.cartao.leitura)
    painel.close()


def _com_a_tecla(app, inicio, tecla, modificadores, passos: int, *, ate=None) -> list:
    """``(widget, à vista)`` for every widget the real key reaches from ``inicio`` --
    ``QTest.keyClick`` on whoever has the focus, as the keyboard does --, whether it had a pixel
    on screen *when it took the focus*, until the focus stops moving or reaches ``ate``."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    inicio.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    caminho = [(app.focusWidget(), not app.focusWidget().visibleRegion().isEmpty())]
    for _ in range(passos):
        antes = app.focusWidget()
        QTest.keyClick(antes, tecla, modificadores)
        app.processEvents()
        agora = app.focusWidget()
        if agora is antes:
            break
        caminho.append((agora, not agora.visibleRegion().isEmpty()))
        if agora is ate:
            break
    return caminho


def test_the_tab_key_walks_the_table_the_card_and_the_actions_in_sight(app, pdf, tmp_path):
    """Crítico da fase 5, ciclo 4: the order held in the focus chain, not under the key -- Tab
    stopped in the truth field writing tabulations into it, the figurines and the six actions
    out of reach; and Shift+Tab from «Aceitar leitura» into the card focused «Letras →
    figurinas» below the fold, 0 px on screen.  Pressed for real, on a window short enough for
    the card to scroll: from the table to the last action and back, every control in its place
    and on screen when it takes the focus."""
    from PyQt6.QtCore import Qt

    tab, sem = Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier
    volta, shift = Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier
    painel = _panel(app, pdf, tmp_path)
    painel.resize(1000, 420)
    app.processEvents()
    acoes = list(painel.acoes.values())
    marcos = [painel.table, painel.cartao.leitura, painel.cartao.verdade, *acoes]
    frente = _com_a_tecla(app, painel.table, tab, sem, 60, ate=acoes[-1])
    na_frente = [w for w, _ in frente]
    assert na_frente[-1] is acoes[-1], "the key reaches the last action"
    posicoes = [na_frente.index(w) for w in marcos]
    assert posicoes == sorted(posicoes), "the table, the card, the actions -- by the key"
    assert [w.accessibleName() for w, a_vista in frente if not a_vista] == []
    assert "\t" not in painel.cartao.verdade.toPlainText()
    tras = _com_a_tecla(app, acoes[-1], volta, shift, 60, ate=painel.table)
    para_tras = [w for w, _ in tras]
    assert para_tras == na_frente[::-1], "Shift+Tab walks the same path back"
    assert [w.accessibleName() for w, a_vista in tras if not a_vista] == []
    # the sabotages: the truth field keeps the Tab; the card no longer scrolls to the focus
    painel.cartao.verdade.setTabChangesFocus(False)
    preso = [w for w, _ in _com_a_tecla(app, painel.table, tab, sem, 60, ate=acoes[-1])]
    assert acoes[0] not in preso
    assert "\t" in painel.cartao.verdade.toPlainText()
    painel.cartao.verdade.setPlainText("")
    painel.cartao.verdade.setTabChangesFocus(True)
    painel._segue_o_foco.desligar()
    painel._rolagem.verticalScrollBar().setValue(0)
    app.processEvents()
    tras = _com_a_tecla(app, acoes[-1], volta, shift, 60, ate=painel.table)
    assert [w for w, a_vista in tras if not a_vista], "without the filter the focus hides"
    painel.close()


def test_the_arrows_walk_the_doubts_with_the_focus_in_the_table_and_enter_goes_to_the_truth(
        app, pdf, tmp_path, monkeypatch):
    """Crítico da fase 5, ciclo 5: the comment said «the arrows walk the lines», and the first ↓
    moved to the next doubt and sent the focus to «Verdade da linha», where the next arrows stayed.
    The arrows walk the doubts and the card follows them; Enter takes the focus to the truth.  The
    sabotage: the card takes the focus on every doubt, as before."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    import caissa.ui.views.revisao_de_texto as vista

    painel = _panel(app, pdf, tmp_path)
    painel.table.setFocus()
    app.processEvents()
    vistas = [painel.current.key]
    for _ in range(2):
        QTest.keyClick(painel.table, Qt.Key.Key_Down)
        app.processEvents()
        assert app.focusWidget() is painel.table, "the arrow keeps the focus in the table"
        assert painel.current.key != vistas[-1], "the arrow moved to the next doubt"
        assert painel.cartao.verdade.toPlainText() == painel.current.text, "the card follows"
        vistas.append(painel.current.key)
    QTest.keyClick(painel.table, Qt.Key.Key_Return)
    app.processEvents()
    assert app.focusWidget() is painel.cartao.verdade
    monkeypatch.setattr(vista, "pelas_setas", lambda _tabela: False)
    painel.table.setFocus()
    app.processEvents()
    QTest.keyClick(painel.table, Qt.Key.Key_Up)
    app.processEvents()
    assert app.focusWidget() is painel.cartao.verdade, "sabotaged: the card takes the focus"
    painel.close()


def test_decisions_move_on_save_themselves_and_reach_the_importers_file(app, pdf, tmp_path):
    from caissa.ocr.review import ReviewDecisions

    painel = _panel(app, pdf, tmp_path)
    visited = []
    # Abstained first: keep it as an image.
    visited.append(painel.current.key)
    assert painel.decide(Action.KEEP_IMAGE)
    app.processEvents()
    # Next pending: the lowest score (0.70) outranks the legality one (0.82;
    # no trace, so no legality bonus).
    assert painel.current.key not in visited
    visited.append(painel.current.key)
    assert painel.current.text == "the r0ok belongs"
    painel._use_alternative(0)
    assert painel.cartao.texto_da_verdade() == "the rook belongs"
    painel.cartao.verdade.setPlainText(painel.current.text)
    painel._on_enter()  # Enter with the same text is "aceitar"
    app.processEvents()
    visited.append(painel.current.key)
    assert painel.current.text == "1.e4 e5 2.Nf3 Nz6"
    painel.cartao.verdade.setPlainText("1.e4 e5 2.Nf3 Nc6")
    painel._on_enter()  # Enter with a changed text is "gravar edição"
    app.processEvents()
    assert len(set(visited)) == 3, "each doubtful region visited once"
    assert painel.table.rowCount() == 0, "only pending rows are listed"
    assert "3 decidida(s), 0 pendente(s) de 3" in painel.status.text()
    assert "s/página" in painel.status.text(), "the time per page is measured"
    assert "Nada pendente" in painel.cartao.recorte.text()
    log = painel.queue.log
    assert [e.action for e in log] == [Action.KEEP_IMAGE, Action.ACCEPT, Action.EDIT]
    assert log[2].text == "1.e4 e5 2.Nf3 Nc6"
    assert all(e.reviewer == "ana" for e in log)
    # Every decision was written as it was taken: the importer's file exists
    # without anyone pressing "Gravar".
    saved = ReviewDecisions.load(tmp_path / "proj" / "revisao" / "Livro X.json")
    assert {d.action for d in saved.entries} == {Action.KEEP_IMAGE, Action.EDIT, Action.ACCEPT}
    fila = json.loads((tmp_path / "proj" / "revisao" / "Livro X.fila.json").read_text("utf-8"))
    assert len(fila["log"]) == 3
    painel.so_pendentes.setChecked(False)
    assert painel.table.rowCount() == 3
    assert any("→ edit" in painel.table.item(r, 3).text() for r in range(3))
    painel.close()
    # Reopening the book brings the queue back with its log.
    from caissa.ui.views.revisao_de_texto import PainelDeRevisaoDeTexto

    painel2 = PainelDeRevisaoDeTexto(
        revisor="ana", pdf_inicial=pdf, cega=blind_guard(()), pasta=tmp_path / "proj"
    )
    assert painel2.queue is not None
    assert len(painel2.queue.pending()) == 0
    assert "retomada" in painel2.status.text()
    painel2.close()


def test_the_enter_on_a_page_nobody_read_accepts_nothing(app, pdf, tmp_path, monkeypatch):
    """Crítico da fase 5, ciclo 6: the page item of an OCR that raised (no reading, the whole
    page's rectangle) comes first in the queue with the focus on its empty truth, and the Enter
    recorded an accept that the next import applied to the whole page.  The Enter is refused with
    the phrase and nothing is recorded; writing the page's text, or keeping it as a picture, is
    what the reviewer can do.  The sabotage: the accept of nothing goes through and reaches the
    importer's file."""
    from caissa.ocr import review
    from caissa.ocr.review import ReviewDecisions

    pagina = SimpleNamespace(
        page_index=0, rect=(0.0, 0.0, 612.0, 792.0), kind="page", decision="abstained",
        reasons=("O OCR falhou nesta página (o provedor falhou: bad allocation): ela não foi "
                 "lida.",),
        text="", engine="", score=0.0, alternatives=())
    report = SimpleNamespace(review_items=[pagina], ocr_traces={}, pages=[1, 2, 3])
    painel = _panel(app, pdf, tmp_path, report=report)
    assert painel.current.kind == "page"
    assert painel.cartao.texto_da_verdade() == ""
    painel._on_enter()
    app.processEvents()
    assert "Recusado: não há leitura para aceitar" in painel.status.text()
    assert painel.queue.log == [], "nothing recorded"
    assert not painel.decide(Action.ACCEPT)
    painel.cartao.verdade.setPlainText("1.e4 e5")
    painel._on_enter()
    app.processEvents()
    assert [e.action for e in painel.queue.log] == [Action.EDIT]
    painel.close()

    monkeypatch.setattr(review, "accepts_nothing", lambda action, reading: False)
    sabotado = _panel(app, pdf, tmp_path / "s", report=report)
    sabotado._on_enter()
    app.processEvents()
    assert [e.action for e in sabotado.queue.log] == [Action.ACCEPT]
    saved = ReviewDecisions.load(tmp_path / "s" / "proj" / "revisao" / "Livro X.json")
    assert [d.action for d in saved.entries] == [Action.ACCEPT], "the importer's file has it"
    sabotado.close()


def test_a_correction_on_a_blind_page_is_refused_with_the_phrase(app, pdf, tmp_path):
    ids = [f"real:Livro X:{n}:100" for n in range(200)]
    blind_pages = [int(i.split(":")[2]) for i in ids if partition_for(i) is Partition.BLIND]
    clear = [p for p in range(200) if p not in blind_pages]
    report = _report(pages=(blind_pages[0], clear[0], clear[1]))
    guard = blind_guard(ids)
    painel = _panel(app, pdf, tmp_path, cega=guard, report=report)
    blind_key = next(i.key for i in painel.queue.items if i.page_index == blind_pages[0])
    painel._show_item(painel.queue.open(blind_key))
    assert "partição cega" in painel.cartao.contexto.text()
    painel.cartao.verdade.setPlainText("typed on a blind page")
    assert not painel.decide(Action.EDIT)
    assert "partição cega" in painel.status.text()
    assert not painel.decide(Action.ACCEPT)
    assert painel.queue.log == [], "nothing recorded"
    assert painel.decide(Action.KEEP_IMAGE), "an image changes no text: allowed"
    saved = json.loads((tmp_path / "proj" / "revisao" / "Livro X.json").read_text("utf-8"))
    assert [e["action"] for e in saved["entries"]] == ["keep_image"]
    painel.close()
    # Sabotage — the guard off: the same correction goes through and lands in
    # the importer's file. This is what the guard exists to stop.
    sabotado = _panel(app, pdf, tmp_path / "s", cega=blind_guard(()), report=report)
    key = next(i.key for i in sabotado.queue.items if i.page_index == blind_pages[0])
    sabotado._show_item(sabotado.queue.open(key))
    sabotado.cartao.verdade.setPlainText("typed on a blind page")
    assert sabotado.decide(Action.EDIT)
    leaked = json.loads((tmp_path / "s" / "proj" / "revisao" / "Livro X.json").read_text("utf-8"))
    assert any(
        e["page_index"] == blind_pages[0] and e["action"] == "edit" for e in leaked["entries"]
    ), "with the guard off the blind page is written"
    sabotado.close()


class _ServiceLikeOcr:
    """A provider shaped like ``OcrService``: it keeps ``last``, the page recognition."""

    def __init__(self) -> None:
        self.last = None

    def __call__(self, _page, frame, _verdict):
        from caissa.ingest.pdf.ocr_service import PageRecognition, RegionRecognition
        from caissa.ocr.decision import Decision, RegionDecision
        from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind

        box = BBox(300.0, 400.0, 950.0, 50.0)
        words = tuple(OcrWord(text=w, box=box, confidence=0.7) for w in ("the", "r0ok", "belongs"))
        result = OcrResult(
            engine="tesseract",
            lang="eng",
            lines=(OcrLine(words=words, box=box, kind=RegionKind.PARAGRAPH),),
        )
        region = RegionRecognition(
            reading_order=0,
            kind=RegionKind.PARAGRAPH,
            box_px=box,
            result=result,
            decision=RegionDecision(Decision.REVIEW, 0.7, 0.78, 0.55, ("Escore baixo",)),
            engine="tesseract",
            variant="base",
            score=0.7,
        )
        self.last = PageRecognition(
            page_index=frame.index,
            dpi=300.0,
            regions=[region],
            portfolio=None,
            notes=[],
            duration_s=0.1,
            whole_page=False,
            engines={},
        )
        return self.last.to_page_text(frame)


def _scanned_pdf(path: Path) -> Path:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 260), False)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)
    doc.close()
    return path


def test_the_panel_takes_an_import_result_from_the_window_without_running_ocr(app, pdf, tmp_path):
    """OCR_UI ciclo 2, passo C7: the window's own import hands its ``ImportResult`` over
    and the queue is built from it -- this tab's importer never starts."""
    from caissa.ui.views.revisao_de_texto import PainelDeRevisaoDeTexto

    painel = PainelDeRevisaoDeTexto(revisor="ana", cega=blind_guard(()), pasta=tmp_path / "proj")
    painel.show()
    app.processEvents()
    assert painel.pdf is None
    assert not painel.receber_importacao(None, pdf=pdf), "nothing to take"
    assert painel.receber_importacao(SimpleNamespace(report=_report()), pdf=pdf)
    app.processEvents()
    assert painel.pdf == pdf, "the result's book is opened here"
    assert painel.queue is not None
    assert painel.table.rowCount() == 3
    assert not painel.importador.rodando, "the tab did not run the OCR a second time"
    assert "3 região(ões) em dúvida" in painel.status.text()
    # The same book again: no reopen, the queue is rebuilt from the fresh result.
    assert painel.receber_importacao(SimpleNamespace(report=_report(pages=(0, 0, 0))), pdf=pdf)
    assert {i.page_index for i in painel.queue.items} == {0}
    painel.close()


def test_the_import_runs_in_a_thread_and_fills_the_queue(app, tmp_path):
    import time

    from caissa.ingest.pdf import PdfImportOptions
    from caissa.ui.views.revisao_de_texto import PainelDeRevisaoDeTexto

    path = _scanned_pdf(tmp_path / "scan.pdf")
    painel = PainelDeRevisaoDeTexto(
        revisor="ana", pdf_inicial=path, cega=blind_guard(()), pasta=tmp_path / "proj"
    )
    painel.pages_edit.setText("9-12")
    assert not painel.importar(), "a range outside the book is refused with its phrase"
    assert painel.status.text()
    painel.pages_edit.setText("")
    assert painel.importar(opcoes=PdfImportOptions(ocr=_ServiceLikeOcr(), detect_diagrams=False))
    assert not painel.btn_importar.isEnabled(), "locked while the thread runs"
    for _ in range(600):
        app.processEvents()
        if not painel.importador.rodando and painel.queue is not None:
            break
        time.sleep(0.02)
    assert painel.queue is not None
    assert [i.text for i in painel.queue.items] == ["the r0ok belongs"]
    assert painel.btn_importar.isEnabled()
    assert painel.table.rowCount() == 1
    painel.close()


def test_decisions_taken_before_survive_a_fresh_import_result(app, pdf, tmp_path):
    """Critic, fase 1 ciclo 1: the rail's import handed over a result built with the earlier
    decisions applied, the tab rebuilt its queue from scratch, and the next ``gravar`` wrote
    the decisions file *without* them.  Now the earlier decisions come along."""
    from caissa.ocr.review import ReviewDecisions

    painel = _panel(app, pdf, tmp_path)
    first_key = painel.current.key
    assert painel.decide(Action.KEEP_IMAGE)
    app.processEvents()
    destino = painel.gravar(quiet=True)
    assert destino is not None
    assert len(ReviewDecisions.load(destino)) == 1
    # The rail imports again: the decided region was applied, so the fresh report
    # lists only the two still pending (a report with no abstained region).
    fresh = _report()
    fresh.review_items = [i for i in fresh.review_items if i.decision != "abstained"]
    assert painel.receber_importacao(SimpleNamespace(report=fresh), pdf=pdf)
    app.processEvents()
    assert painel.table.rowCount() == 2, "the two pending ones; the decided one is not listed"
    assert painel.decide(Action.ACCEPT)
    app.processEvents()
    painel.gravar(quiet=True)
    saved = ReviewDecisions.load(destino)
    assert len(saved) == 2, "the earlier decision was carried over, not overwritten"
    assert {e.action for e in saved.entries} == {Action.KEEP_IMAGE, Action.ACCEPT}
    assert first_key != painel.current.key if painel.current else True
    # A cancelled (partial) result never replaces the queue.
    partial = _report()
    partial.canceled = True
    assert not painel.receber_importacao(SimpleNamespace(report=partial), pdf=pdf)
    painel.close()
