"""A janela de **revisão de texto** (SOL-11, OCR_UI_ROADMAP passo 14).

O revisor corrige só o que está em dúvida: a vista mostra os spans ``REVIEW`` e
``ABSTAINED`` do livro importado — recorte, leitura, alternativas, motivo — e três
ações por item: **aceitar** a leitura, **gravar** o texto corrigido, **manter como
imagem**. Cada decisão entra na trilha de auditoria da fila (quem, quando, quanto
tempo), e as decisões sobrevivem à janela: gravadas em ``labeling/revisao/<livro>.json``,
o importador as aplica na próxima leitura do livro (``PdfImportOptions.review_decisions``)
e a exportação diz quantas dúvidas restam.

Nada é decidido aqui. A fila, a ordem por risco, a recusa da partição cega, a redução
do diário em decisões e a aplicação delas ao OCR são de :mod:`caissa.ocr.review`, sem
toolkit; a importação é a de :mod:`caissa.ingest.pdf`. O cartão da direita é o mesmo
da aba Rotulagem (:mod:`caissa.ui.widgets.cartao_da_linha`), porque quem revisa o
produto e quem rotula a bancada olham a mesma coisa. Este módulo é o desenho.

A importação roda numa thread e volta por sinais Qt (o desenho de
:class:`caissa.ui.views.exportacao.ExportadorDeLivro`); com OCR, um livro inteiro leva
minutos — por isso o campo de páginas, para revisar um capítulo de cada vez.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from caissa.ui.theme import pele
from caissa.export.book import PageRangeError, parse_page_range
from caissa.ingest.pdf import ImportCanceled, PdfImportOptions, import_pdf, open_pdf
from caissa.ocr.labeling.recognise import render_rgb
from caissa.ocr.review import (
    Action,
    BlindGuard,
    ReviewItem,
    ReviewQueue,
    blind_guard,
    decisions_path,
)
from caissa.ui.widgets.cartao_da_linha import CartaoDaLinha
from caissa.ui.widgets.rotulo_que_encolhe import RotuloQueEncolhe

__all__ = [
    "TITULO",
    "ImportadorParaRevisao",
    "PainelDeRevisaoDeTexto",
    "fila_path",
    "guarda_cega_padrao",
]

TITULO = "Revisão de texto"
"""O rótulo da aba. O tronco o lê daqui para não escrever o nome duas vezes."""

SEM_ITEM = "Abra um PDF e importe as páginas a revisar."
#: The reading's weak words are painted against this threshold (the queue
#: brings the words, not their confidences).
WEAK_THRESHOLD = 0.5
CROP_PAD_PT = 3.0
COLUNAS = ("#", "pág.", "tipo", "decisão", "escore", "motivo", "texto")


def guarda_cega_padrao(manifest: Path | None = None) -> BlindGuard:
    """The blind guard from the golden manifest on this machine — or one that says no."""
    from caissa.ocr.labeling.app import DEFAULT_MANIFEST

    path = manifest or DEFAULT_MANIFEST
    try:
        from caissa.ocr.golden import load_manifest

        return blind_guard(i.id for i in load_manifest(path, include_blind=True).items)
    except (OSError, ValueError):
        return blind_guard(())


def fila_path(pdf_path: Path | str) -> Path:
    """Where the queue itself (items + audit log) is saved: next to the decisions."""
    return decisions_path(pdf_path).with_suffix(".fila.json")


# --------------------------------------------------------------------------- #
# Background import
# --------------------------------------------------------------------------- #


class ImportadorParaRevisao(QObject):
    """Importa as páginas pedidas (com OCR) numa thread e entrega o resultado."""

    estado = pyqtSignal(str)
    progresso = pyqtSignal(int, int)
    controles = pyqtSignal(bool)
    terminou = pyqtSignal(object)

    _acabou = pyqtSignal(object)
    _falhou = pyqtSignal(str)
    _avancou = pyqtSignal(int, int)

    def __init__(self, pai: QWidget | None) -> None:
        super().__init__(pai)
        self._pai = pai
        self._cancelar: threading.Event | None = None
        self._rodando = False
        self._acabou.connect(self._concluiu)
        self._falhou.connect(self._deu_errado)
        self._avancou.connect(self.progresso.emit)

    @property
    def rodando(self) -> bool:
        return self._rodando

    def iniciar(
        self,
        pdf_path: Path,
        pages: tuple[int, ...] | None,
        *,
        opcoes: PdfImportOptions | None = None,
    ) -> None:
        if self._rodando:
            self.estado.emit("Já existe uma importação em execução.")
            return
        self._rodando = True
        self._cancelar = threading.Event()
        self.controles.emit(False)
        alcance = "todas as páginas" if pages is None else f"{len(pages)} página(s)"
        self.estado.emit(f"Importando {pdf_path.name} com OCR ({alcance})…")
        threading.Thread(
            target=self._trabalho, args=(pdf_path, pages, opcoes, self._cancelar), daemon=True
        ).start()

    def cancelar(self) -> None:
        if self._cancelar is not None:
            self._cancelar.set()
            self.estado.emit("Cancelando a importação… responde entre uma página e outra.")

    def _trabalho(
        self,
        pdf_path: Path,
        pages: tuple[int, ...] | None,
        opcoes: PdfImportOptions | None,
        cancelar: threading.Event,
    ) -> None:
        try:
            options = opcoes or PdfImportOptions()
            options.pages = pages
            options.enable_ocr = True
            options.progress = lambda done, total: self._avancou.emit(done, total)
            options.should_cancel = cancelar.is_set
            result = import_pdf(pdf_path, options)
        except ImportCanceled as exc:
            self._falhou.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - shown to the reviewer, never lost
            self._falhou.emit(f"{type(exc).__name__}: {exc}")
            return
        self._acabou.emit(result)

    def _concluiu(self, result: Any) -> None:
        self._encerrar()
        self.terminou.emit(result)

    def _deu_errado(self, detalhe: str) -> None:
        self._encerrar()
        self.estado.emit(f"A importação não terminou: {detalhe}")
        if self._pai is not None and "cancelad" not in detalhe.lower():
            QMessageBox.warning(self._pai, "Importação", detalhe)

    def _encerrar(self) -> None:
        self._rodando = False
        self._cancelar = None
        self.controles.emit(True)


# --------------------------------------------------------------------------- #
# The panel
# --------------------------------------------------------------------------- #


class PainelDeRevisaoDeTexto(QWidget):
    """Lista de dúvidas à esquerda, o cartão à direita, três ações e um relógio."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        revisor: str = "",
        pdf_inicial: Path | str | None = None,
        cega: BlindGuard | None = None,
        pasta: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.revisor = revisor
        self.pdf: Path | None = None
        self.page_count = 0
        self.queue: ReviewQueue | None = None
        self.current: ReviewItem | None = None
        self._cega = cega if cega is not None else guarda_cega_padrao()
        self._pasta = pasta
        self._montar()
        self._atalhos()
        self.importador = ImportadorParaRevisao(self)
        self.importador.estado.connect(self._set_status)
        self.importador.progresso.connect(self._progresso)
        self.importador.controles.connect(self._controles)
        self.importador.terminou.connect(self._importado)
        if pdf_inicial is not None:
            self.abrir(Path(pdf_inicial))
        else:
            self._refresh_status()

    # -- layout ------------------------------------------------------------- #

    def _montar(self) -> None:  # noqa: PLR0915 - one widget tree, top to bottom
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(4, 4, 4, 4)
        barra = QHBoxLayout()
        raiz.addLayout(barra)

        def botao(texto: str, acao: Callable[[], Any], *, dica: str = "") -> QPushButton:
            b = QPushButton(texto, self)
            b.clicked.connect(lambda _c=False: acao())
            if dica:
                b.setToolTip(dica)
            barra.addWidget(b)
            return b

        self.btn_abrir = botao("Abrir PDF…", self.escolher_pdf)
        self.doc_label = QLabel("(nenhum PDF)", self)
        self.doc_label.setAccessibleName("Documento aberto")
        barra.addWidget(self.doc_label, 1)
        barra.addWidget(QLabel("Páginas:", self))
        self.pages_edit = QLineEdit(self)
        self.pages_edit.setPlaceholderText("todas · ex.: 10-25, 40")
        self.pages_edit.setFixedWidth(150)
        self.pages_edit.setAccessibleName("Páginas a importar")
        barra.addWidget(self.pages_edit)
        self.btn_importar = botao(
            "Importar (OCR)", self.importar, dica="Lê as páginas com OCR e monta a fila de dúvidas"
        )
        self.btn_cancelar = botao("Cancelar", self.importador_cancelar)
        self.btn_cancelar.setEnabled(False)
        self.btn_gravar = botao(
            "Gravar decisões", self.gravar, dica="Ctrl+S — as decisões valem na próxima importação"
        )
        self.so_pendentes = QCheckBox("só pendentes", self)
        self.so_pendentes.setChecked(True)
        self.so_pendentes.toggled.connect(lambda _v: self._fill_table())
        barra.addWidget(self.so_pendentes)

        corpo = QSplitter(Qt.Orientation.Horizontal, self)
        raiz.addWidget(corpo, 1)
        self.table = QTableWidget(0, len(COLUNAS), corpo)
        self.table.setHorizontalHeaderLabels(list(COLUNAS))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAccessibleName("Dúvidas do livro")
        self.table.itemSelectionChanged.connect(self._on_table_select)
        corpo.addWidget(self.table)

        # C18: o cartão numa rolagem vertical. Solto, ele punha esta aba em 501 px de altura -- a
        # segunda mais alta da pilha de áreas, logo abaixo da Galeria do tronco (516 px, que é quem
        # segura a pele Foco em 640, no teto do portão `caissa.ui.audit.minimo`). Na rolagem a aba
        # pede 135 px: quando a Galeria deixar de decidir a altura, não será esta a decidir.
        rolagem = QScrollArea(corpo)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rolagem.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        direita = QWidget()
        dir_ = QVBoxLayout(direita)
        dir_.setContentsMargins(4, 0, 0, 0)
        self.cartao = CartaoDaLinha(direita, vazio=SEM_ITEM)
        self.cartao.aceitar.connect(self._on_enter)
        self.cartao.gravar.connect(lambda: self.decide(Action.EDIT))
        self.cartao.rejeitar.connect(lambda: self.decide(Action.KEEP_IMAGE))
        self.cartao.andar.connect(self.step)
        self.cartao.alternativa_pedida.connect(self._use_alternative)
        dir_.addWidget(self.cartao)
        botoes = QHBoxLayout()
        self.acoes: dict[str, QPushButton] = {}
        for texto, acao in (
            ("Aceitar leitura", lambda: self.decide(Action.ACCEPT)),
            ("Gravar edição", lambda: self.decide(Action.EDIT)),
            ("Manter como imagem", lambda: self.decide(Action.KEEP_IMAGE)),
            ("Pular", lambda: self.decide(Action.SKIP)),
        ):
            b = QPushButton(texto, direita)
            b.clicked.connect(lambda _c=False, a=acao: a())
            botoes.addWidget(b)
            self.acoes[texto] = b
        botoes.addStretch(1)
        paginador = []
        for texto, delta in (("Anterior", -1), ("Próxima", 1)):
            b = QPushButton(texto, direita)
            b.clicked.connect(lambda _c=False, d=delta: self.step(d))
            botoes.addWidget(b)
            paginador.append(b)
        pele.vestir_paginador(*paginador)   # o desenho do tronco ao lado da palavra (C9)
        dir_.addLayout(botoes)
        dir_.addStretch(1)
        rolagem.setWidget(direita)
        corpo.addWidget(rolagem)
        corpo.setStretchFactor(0, 2)
        corpo.setStretchFactor(1, 3)
        corpo.setSizes([440, 560])

        self.status = RotuloQueEncolhe("", self)   # C18
        self.status.setStyleSheet(f"padding:3px 6px; border-top:1px solid {pele.cor('moldura')};")
        self.status.setAccessibleName("Estado da revisão")
        raiz.addWidget(self.status)

    def _atalhos(self) -> None:
        """Nenhum atalho local desde o passo C8: ``Ctrl+S`` e ``Ctrl+O`` eram ambíguos com os
        globais da janela do tronco (com a aba à frente, nem um nem outro disparava). As duas
        ações estão em :data:`caissa.ui.views.declarados.COMANDOS_DA_REVISAO_DE_TEXTO`; a
        janela as liga ao catálogo, ao menu, à paleta e às teclas -- e roteia o ``Ctrl+S``
        global para :meth:`gravar` quando esta aba está à frente."""

    # -- the book ----------------------------------------------------------- #

    def escolher_pdf(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "PDF (*.pdf)")
        if caminho:
            self.abrir(Path(caminho))

    def abrir(self, pdf: Path, *, page_count: int | None = None) -> None:
        """Open the book; a queue saved for it earlier comes back with its log.

        The window passes ``page_count`` (it already has it) so this tab does not
        reopen the PDF on the interface thread -- the heavy opening that
        ``caissa.ui.audit.bloqueio`` caught lived in the labelling tab, which
        defers it until shown.
        """
        self.pdf = pdf
        if page_count is not None:
            self.page_count = int(page_count)
        else:
            try:
                with open_pdf(pdf) as doc:
                    self.page_count = doc.page_count
            except Exception as exc:  # noqa: BLE001 - said in the status, not raised at the window
                self.page_count = 0
                self._set_status(f"Não abriu {pdf.name}: {exc}")
                return
        self.doc_label.setText(f"{pdf.name} · {self.page_count} páginas")
        salva = self._fila_path()
        self.queue = None
        if salva is not None and salva.is_file():
            self.queue = ReviewQueue.load(salva, blind=self._cega)
            self.queue.reviewer = self.queue.reviewer or self.revisor
        self.current = None
        self._fill_table()
        self.cartao.limpar()
        if self.queue is not None:
            self._set_status(
                f"Fila gravada retomada: {len(self.queue.pending())} pendente(s) de "
                f"{len(self.queue.items)}."
            )
            self._select_first_pending()
        else:
            self._set_status("Importe as páginas a revisar (Importar (OCR)).")

    def paginas(self) -> tuple[int, ...] | None:
        """Zero-based indices from the field, ``None`` for the whole book."""
        texto = self.pages_edit.text().strip()
        if not texto:
            return None
        return parse_page_range(texto, self.page_count)

    def importar(self, *, opcoes: PdfImportOptions | None = None) -> bool:
        if self.pdf is None:
            self._set_status("Abra um PDF antes de importar.")
            return False
        try:
            pages = self.paginas()
        except PageRangeError as exc:
            self._set_status(str(exc))
            return False
        self.importador.iniciar(self.pdf, pages, opcoes=opcoes)
        return True

    def importador_cancelar(self) -> None:
        self.importador.cancelar()

    def receber_importacao(self, result: Any, *, pdf: Path | str | None = None) -> bool:
        """Take an ``ImportResult`` produced elsewhere and build the queue from it.

        OCR_UI ciclo 2, passo C7: the window's own import (the page rail's *Importar*)
        already ran the OCR; this tab used to run it a second time to get its
        queue. Now the trunk hands the result over and the OCR runs once per book.
        ``pdf`` names the book the result belongs to; if it is not the one open
        here, it is opened first (a saved queue for it is superseded by the
        fresh result). ``False`` when nothing could be taken (no result, no PDF).
        """
        if result is None or getattr(result, "report", None) is None:
            return False
        if getattr(result.report, "canceled", False):
            # A cancelled import is half a book: it serves the page rail, not this
            # queue, which would replace the book's queue with a partial one.
            self._set_status("Importação cancelada: a fila de dúvidas não foi substituída.")
            return False
        alvo = Path(pdf) if pdf is not None else None
        if alvo is not None and alvo != self.pdf:
            self.abrir(alvo)
        if self.pdf is None:
            return False
        self._importado(result)
        return True

    def _importado(self, result: Any) -> None:
        if self.pdf is None:
            return
        anterior = self.queue
        self.queue = ReviewQueue.from_import(
            result.report, document=self.pdf.stem, reviewer=self.revisor, blind=self._cega
        )
        # The decisions already taken on this book (loaded from its file, or
        # taken in this session) come along: the regions they settled were
        # applied on the import and are not in the new queue, and ``gravar``
        # writes what the queue knows (C7; critic, fase 1 ciclo 1).
        if anterior is not None and anterior.items and anterior.items[0].document == self.pdf.stem:
            self.queue.carry_over(anterior)
        self.current = None
        self._fill_table()
        self.cartao.limpar()
        n = len(self.queue.items)
        self._set_status(
            f"{n} região(ões) em dúvida em {len(result.report.pages)} página(s)."
            if n
            else "Nenhuma região em dúvida nas páginas importadas."
        )
        self._select_first_pending()

    def _progresso(self, done: int, total: int) -> None:
        self._set_status(f"Importando… {done}/{total} página(s)")

    def _controles(self, livres: bool) -> None:
        for b in (self.btn_abrir, self.btn_importar, self.btn_gravar):
            b.setEnabled(livres)
        self.btn_cancelar.setEnabled(not livres)

    # -- the list ----------------------------------------------------------- #

    def _visible(self) -> list[ReviewItem]:
        if self.queue is None:
            return []
        return self.queue.pending() if self.so_pendentes.isChecked() else list(self.queue.items)

    def _fill_table(self) -> None:
        items = self._visible()
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))
        decided = self.queue.decided() if self.queue is not None else {}
        for row, item in enumerate(items):
            entry = decided.get(item.key)
            values = (
                str(row + 1),
                str(item.page_index + 1),
                item.kind,
                f"{item.decision} → {entry.action}" if entry else item.decision,
                f"{item.score:.2f}",
                "; ".join(item.reasons)[:60],
                (item.text or "(sem leitura)")[:60],
            )
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.key)
                self.table.setItem(row, col, cell)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self._refresh_status()

    def _on_table_select(self) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows or self.queue is None:
            return
        key = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._show_item(self.queue.open(key))

    def _select_row(self, row: int) -> None:
        if 0 <= row < self.table.rowCount():
            # After a refill the same row may already be selected and Qt
            # would not signal; the card must follow the row regardless.
            self.table.blockSignals(True)
            self.table.selectRow(row)
            self.table.blockSignals(False)
            self._on_table_select()

    def _select_first_pending(self) -> None:
        if self.queue is None:
            return
        pending = {i.key for i in self.queue.pending()}
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) in pending:
                self._select_row(row)
                return
        self.cartao.limpar("Nada pendente: todas as dúvidas foram decididas.")

    def step(self, delta: int) -> None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        atual = rows[0].row() if rows else -1
        self._select_row(atual + delta)

    # -- the card ----------------------------------------------------------- #

    def _show_item(self, item: ReviewItem) -> None:
        self.current = item
        if self.pdf is not None:
            x0, y0, x1, y1 = item.rect
            pad = CROP_PAD_PT
            try:
                self.cartao.mostrar_recorte(
                    render_rgb(
                        self.pdf,
                        item.page_index,
                        300,
                        clip=(x0 - pad, y0 - pad, x1 + pad, y1 + pad),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - a crop that fails is said, not fatal
                self.cartao.recorte.setPixmap(QPixmap())
                self.cartao.recorte.setText(f"(recorte indisponível: {exc})")
        weak = set(item.low_confidence_words)
        words = [(w, 0.0 if w in weak else 1.0) for w in item.text.split()]
        self.cartao.mostrar_leitura(words, WEAK_THRESHOLD, fallback=item.text or "(sem leitura)")
        self.cartao.mostrar_alternativas(item.alternatives)
        parts = [
            f"p. {item.page_index + 1} · {item.kind} · {item.decision}",
            f"{item.engine} {item.score:.2f}",
        ]
        recusa = self.queue.refusal(item.key, Action.EDIT) if self.queue else ""
        if recusa:
            parts.append("partição cega")
        entry = self.queue.decided().get(item.key) if self.queue else None
        if entry is not None:
            parts.append(f"{entry.action} por {entry.reviewer or '?'} em {entry.seconds:.0f}s")
        self.cartao.contexto.setText(" · ".join(parts))
        reasons = list(item.reasons[:2])
        if item.low_confidence_words:
            reasons.append("palavras fracas: " + ", ".join(item.low_confidence_words[:6]))
        if item.disputed_tokens:
            reasons.append("disputa: " + ", ".join(f"{a}↔{b}" for a, b in item.disputed_tokens[:4]))
        if item.legality.get("unresolved"):
            reasons.append(f"{item.legality['unresolved']} lance(s) sem leitura legal")
        if item.suggestion:
            reasons.append(f"sugestão (não aplicada): {item.suggestion}")
        self.cartao.motivo.setText(" · ".join(reasons))
        self.cartao.mostrar_verdade(entry.text if entry and entry.text else item.text)

    def _use_alternative(self, index: int) -> None:
        texto = self.cartao.alternativa(index)
        if texto is not None:
            self.cartao.verdade.setPlainText(texto)

    # -- deciding ----------------------------------------------------------- #

    def _on_enter(self) -> None:
        typed = self.cartao.texto_da_verdade().strip()
        if self.current is not None and typed and typed != self.current.text.strip():
            self.decide(Action.EDIT)
        else:
            self.decide(Action.ACCEPT)

    def decide(self, action: Action) -> bool:
        """Record ``action`` on the current item and move to the next pending one."""
        if self.queue is None or self.current is None:
            self._set_status("Selecione uma dúvida.")
            return False
        recusa = self.queue.refusal(self.current.key, action)
        if recusa:
            self._set_status("Recusado: " + recusa)
            return False
        text = self.cartao.texto_da_verdade().strip() if action is Action.EDIT else None
        if action is Action.EDIT and not text:
            self._set_status(
                "Gravar edição exige um texto; para tirar a região, mantenha-a como imagem."
            )
            return False
        self.queue.decide(self.current.key, action, text=text)
        self._autosave()
        self._fill_table()
        self._select_first_pending()
        return True

    def _autosave(self) -> None:
        """Every decision reaches the disk: nothing typed is lost to a crash."""
        try:
            self.gravar(quiet=True)
        except OSError as exc:
            self._set_status(f"Decisão registrada, mas não gravada: {exc}")

    def gravar(self, *, quiet: bool = False) -> Path | None:
        """The queue (audit log) and the decisions the importer applies."""
        if self.queue is None or self.pdf is None:
            if not quiet:
                self._set_status("Nada a gravar.")
            return None
        destino = self._decisions_path(self.pdf)
        fila = destino.with_suffix(".fila.json")
        fila.parent.mkdir(parents=True, exist_ok=True)
        self.queue.save(fila)
        self.queue.decisions().save(destino)
        if not quiet:
            self._set_status(
                f"Gravado: {len(self.queue.decisions())} decisão(ões) em {destino.name}; "
                f"{self.queue.withheld()} retida(s) da partição cega."
            )
        return destino

    # -- paths ------------------------------------------------------------- #

    def _decisions_path(self, pdf: Path) -> Path:
        if self._pasta is not None:
            return self._pasta / "revisao" / (pdf.stem + ".json")
        return decisions_path(pdf)

    def _fila_path(self) -> Path | None:
        if self.pdf is None:
            return None
        return self._decisions_path(self.pdf).with_suffix(".fila.json")

    # -- status ------------------------------------------------------------- #

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def _refresh_status(self) -> None:
        if self.queue is None:
            if not self.status.text():
                self._set_status(SEM_ITEM)
            return
        pendentes = len(self.queue.pending())
        total = len(self.queue.items)
        seconds = self.queue.seconds_per_page()
        tempo = ""
        if seconds:
            media = sum(seconds.values()) / len(seconds)
            tempo = f" · {media:.0f} s/página em {len(seconds)} página(s)"
        self._set_status(
            f"{total - pendentes} decidida(s), {pendentes} pendente(s) de {total}{tempo}"
        )
