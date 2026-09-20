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


def test_the_reading_html_paints_weak_words_amber_and_very_weak_red():
    html = leitura_em_html([("the", 0.9), ("r0ok", 0.4), ("belongs", 0.2)], 0.5)
    assert html.startswith("the ")
    assert '<span style="background:#fde68a">r0ok</span>' in html
    assert '<span style="background:#fca5a5">belongs</span>' in html
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
