"""A aba **Rotulagem** da janela do produto (PyQt6) — o ciclo do FineReader por livro.

O mesmo trabalho da bancada Tk (:mod:`caissa.ocr.labeling.app`), dentro da janela do
tronco: a página à esquerda com as regiões do layout e uma caixa por linha colorida
pelo estado; à direita o recorte da linha, a leitura do motor com as palavras fracas
em destaque, as leituras alternativas, o motivo da dúvida e o campo da verdade.
*Treinar…* ajusta o Tesseract com as linhas **deste livro** e registra o modelo para o
PDF (``livros.json``); a importação e o F5 desta aba passam a usá-lo. *Medir no livro…*
relê as páginas rotuladas sem e com o modelo.

Nada é decidido aqui: o projeto, as decisões, a partição cega, as exportações, o treino
e a medida são de :mod:`caissa.ocr.labeling` e :mod:`caissa.ocr.training`, sem toolkit.
Este módulo é o desenho — a regra que o tronco mantém entre ``ui/`` e ``qt/``.

A cena do visor está em **pontos da página**: a imagem renderizada leva ``setScale(72/dpi)``
e as caixas das linhas são desenhadas nas coordenadas dos rótulos, sem conversão; o zoom
é a transformação da vista. O trabalho longo (reconhecer, exportar, treinar, medir) roda
numa thread e volta por uma fila lida por ``QTimer`` — o mesmo desenho da bancada.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from caissa.ocr.labeling import LabelProject, LineLabel, LineStatus, PageLabels, RegionLabel
from caissa.ocr.labeling.export import (
    calibration_pairs,
    corrections,
    manifest_items,
    merge_into_manifest,
    withheld_lines,
    write_ground_truth,
)
from caissa.ocr.labeling.helpers import (
    FIGURINE_KEYS,
    STATUS_COLOR,
    default_project_dir,
    fen_problem,
    letters_to_figurines,
    status_pt,
)
from caissa.ocr.labeling.measure import BookMeasure, measure_book
from caissa.ocr.labeling.recognise import (
    kinds_for_menu,
    label_page,
    page_count,
    page_size,
    recognise_rect,
    render_rgb,
)
from caissa.ocr.training import (
    BookModel,
    BookRegistry,
    FineTuneConfig,
    TesseractFineTuner,
    TrainingToolsError,
    book_dir,
    download_base_model,
    find_training_tools,
    models_root,
    preflight,
    register_training,
)

__all__ = [
    "TITULO",
    "DialogoDeMedida",
    "DialogoDeTreino",
    "PainelDeRotulagem",
    "abrir_projeto",
]

TITULO = "Rotulagem"
"""O rótulo da aba. O tronco o lê daqui para não escrever o nome duas vezes."""

REGION_COLOR = "#7c3aed"
SELECTED_COLOR = "#dc2626"
PAGE_DPI = 150  # the page image in the viewer; the crop on the right is at 300
CROP_HEIGHT_PX = 90
CROP_MAX_ZOOM = 3.0
CLICK_SLOP_PX = 4
WEAK_WORDS_SHOWN = 6
LANGS = ["por+eng", "eng", "por", "spa+eng", "deu+eng", "rus+eng", "fra+eng", "ita+eng", "nld+eng"]
BASE_LANGS = ["por", "eng", "deu", "spa", "rus", "fra", "ita", "nld"]


def abrir_projeto(caminho: Path | str | None = None, *, revisor: str = "") -> LabelProject:
    """O projeto de rotulagem, criado se não existir.

    ``labeling/`` num checkout, ``rotulagem/`` ao lado do executável no bundle.
    """
    return LabelProject.open_or_create(
        Path(caminho) if caminho else default_project_dir(), reviewer=revisor
    )


def _pixmap(rgb: np.ndarray) -> QPixmap:
    """A numpy ``HxWx3`` uint8 array as a pixmap (the bytes are copied)."""
    array = np.ascontiguousarray(rgb)
    height, width = array.shape[:2]
    image = QImage(array.data, width, height, 3 * width, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())


# --------------------------------------------------------------------------- #
# Background work
# --------------------------------------------------------------------------- #


class _Fila(QObject):
    """One background thread at a time; results come back on the GUI thread."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.queue: queue.Queue[tuple[Any, tuple[str, Any]]] = queue.Queue()
        self.busy = False
        self.timer = QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def run(self, fn: Callable[[], Any], done: Callable[[str, Any], None]) -> bool:
        if self.busy:
            return False
        self.busy = True

        def target() -> None:
            try:
                self.queue.put((done, ("ok", fn())))
            except Exception as exc:  # noqa: BLE001 - surfaced to the reviewer
                self.queue.put((done, ("error", exc)))

        threading.Thread(target=target, daemon=True).start()
        return True

    def _poll(self) -> None:
        try:
            while True:
                done, payload = self.queue.get_nowait()
                self.busy = False
                done(*payload)
        except queue.Empty:
            pass


# --------------------------------------------------------------------------- #
# The page viewer
# --------------------------------------------------------------------------- #


class _Visor(QGraphicsView):
    """The page with its boxes. Scene units are page points."""

    def __init__(
        self,
        parent: QWidget,
        *,
        ao_clicar: Callable[[float, float], None],
        ao_clicar_direito: Callable[[float, float, Any], None],
        ao_desenhar: Callable[[tuple[float, float, float, float]], None],
    ) -> None:
        super().__init__(parent)
        self.cena = QGraphicsScene(self)
        self.setScene(self.cena)
        self.setBackgroundBrush(QBrush(QColor("#3f3f46")))
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAccessibleName("Página com as regiões e linhas reconhecidas")
        self._ao_clicar = ao_clicar
        self._ao_clicar_direito = ao_clicar_direito
        self._ao_desenhar = ao_desenhar
        self.desenhando = False
        self._inicio: QPointF | None = None
        self._inicio_tela: Any = None
        self._rascunho: QGraphicsRectItem | None = None
        self.imagem: QGraphicsPixmapItem | None = None
        self.caixas: list[Any] = []
        self.zoom = 1.6

    # -- image and boxes ---------------------------------------------------- #

    def mostrar_pagina(self, rgb: np.ndarray | None, dpi: float) -> None:
        self.cena.clear()
        self.caixas = []
        self.imagem = None
        if rgb is None:
            return
        self.imagem = self.cena.addPixmap(_pixmap(rgb))
        self.imagem.setScale(72.0 / dpi)
        self.cena.setSceneRect(self.imagem.sceneBoundingRect())
        self.aplicar_zoom()

    def aplicar_zoom(self) -> None:
        self.resetTransform()
        self.scale(self.zoom, self.zoom)

    def ajustar_largura(self) -> None:
        if self.imagem is None:
            return
        largura = max(1.0, self.cena.sceneRect().width())
        self.zoom = max(0.4, min(6.0, (self.viewport().width() - 4) / largura))
        self.aplicar_zoom()

    def desenhar_caixas(
        self, page: PageLabels | None, *, selecionada: RegionLabel | None, atual: LineLabel | None
    ) -> None:
        for item in self.caixas:
            self.cena.removeItem(item)
        self.caixas = []
        if page is None:
            return
        for region in page.regions:
            x0, y0, x1, y1 = region.rect
            pen = QPen(QColor(SELECTED_COLOR if region is selecionada else REGION_COLOR))
            pen.setCosmetic(True)
            pen.setWidth(2 if region is selecionada else 1)
            if region is not selecionada:
                pen.setStyle(Qt.PenStyle.DashLine)
            self.caixas.append(
                self.cena.addRect(QRectF(x0 - 2, y0 - 2, x1 - x0 + 4, y1 - y0 + 4), pen)
            )
            texto = QGraphicsSimpleTextItem(f"{region.index} {region.kind}")
            texto.setBrush(QBrush(QColor(REGION_COLOR)))
            texto.setFlag(texto.GraphicsItemFlag.ItemIgnoresTransformations)
            texto.setPos(x0 - 2, y0 - 12)
            self.cena.addItem(texto)
            self.caixas.append(texto)
            for line in region.lines:
                lx0, ly0, lx1, ly1 = line.box
                pen = QPen(QColor(STATUS_COLOR[line.status]))
                pen.setCosmetic(True)
                pen.setWidth(3 if line is atual else 1)
                self.caixas.append(self.cena.addRect(QRectF(lx0, ly0, lx1 - lx0, ly1 - ly0), pen))

    def centralizar(self, box: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = box
        self.ensureVisible(QRectF(x0, y0, x1 - x0, y1 - y0), 40, 60)

    # -- mouse -------------------------------------------------------------- #

    def modo_desenho(self, ligado: bool) -> None:
        self.desenhando = ligado
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag if ligado else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.viewport().setCursor(
            Qt.CursorShape.CrossCursor if ligado else Qt.CursorShape.OpenHandCursor
        )

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        ponto = self.mapToScene(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton:
            self._ao_clicar_direito(ponto.x(), ponto.y(), event.globalPosition().toPoint())
            return
        self._inicio = ponto
        self._inicio_tela = event.position().toPoint()
        if self.desenhando:
            pen = QPen(QColor(SELECTED_COLOR))
            pen.setCosmetic(True)
            pen.setWidth(2)
            self._rascunho = self.cena.addRect(QRectF(ponto, ponto), pen)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        if self.desenhando and self._rascunho is not None and self._inicio is not None:
            ponto = self.mapToScene(event.position().toPoint())
            self._rascunho.setRect(QRectF(self._inicio, ponto).normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        if event.button() != Qt.MouseButton.LeftButton or self._inicio is None:
            super().mouseReleaseEvent(event)
            return
        ponto = self.mapToScene(event.position().toPoint())
        tela = event.position().toPoint()
        moveu = (
            abs(tela.x() - self._inicio_tela.x()) > CLICK_SLOP_PX
            or abs(tela.y() - self._inicio_tela.y()) > CLICK_SLOP_PX
        )
        inicio, self._inicio = self._inicio, None
        if self.desenhando:
            if self._rascunho is not None:
                self.cena.removeItem(self._rascunho)
                self._rascunho = None
            self.modo_desenho(False)
            if moveu:
                rect = QRectF(inicio, ponto).normalized()
                self._ao_desenhar((rect.left(), rect.top(), rect.right(), rect.bottom()))
            return
        super().mouseReleaseEvent(event)
        if not moveu:
            self._ao_clicar(ponto.x(), ponto.y())

    def wheelEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            fator = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.zoom = max(0.4, min(6.0, self.zoom * fator))
            self.aplicar_zoom()
            return
        super().wheelEvent(event)


# --------------------------------------------------------------------------- #
# The tab
# --------------------------------------------------------------------------- #


class PainelDeRotulagem(QWidget):
    """A aba: o projeto, o livro aberto, a página e a linha atual."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        projeto: LabelProject | None = None,
        revisor: str = "",
        pdf_inicial: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = projeto or abrir_projeto(revisor=revisor)
        if revisor and not self.project.reviewer:
            self.project.reviewer = revisor
        self.fila = _Fila(self)
        self.service: Any = None
        self.book: BookModel | None = None
        self.document: str | None = None
        self.page_index = 0
        self.page: PageLabels | None = None
        self.current: tuple[RegionLabel, LineLabel] | None = None
        self.selected_region: RegionLabel | None = None
        self.opened_at = 0.0
        self._montar()
        self._atalhos()
        if pdf_inicial is not None:
            self.project.add_document(pdf_inicial)
            self.project.save()
            self.doc_box.clear()
            self.doc_box.addItems(sorted(self.project.documents))
        docs = sorted(self.project.documents)
        if pdf_inicial is not None:
            self._select_document(pdf_inicial.stem)
        elif docs:
            self._select_document(docs[0])
        self._refresh_status()

    # -- widgets ------------------------------------------------------------ #

    def _montar(self) -> None:  # noqa: PLR0915 - one widget tree, top to bottom
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(4, 4, 4, 4)
        # Two rows: the pane the trunk gives a tab is ~800 px wide, and one
        # row of everything was measured truncating every button label.
        linha1 = QHBoxLayout()
        raiz.addLayout(linha1)
        barra = QHBoxLayout()
        raiz.addLayout(barra)

        def botao(
            texto: str, acao: Callable[[], Any], *, dica: str = "", em: QHBoxLayout | None = None
        ) -> QPushButton:
            b = QPushButton(texto, self)
            b.clicked.connect(lambda _c=False: acao())
            if dica:
                b.setToolTip(dica)
            (em if em is not None else barra).addWidget(b)
            return b

        botao("Adicionar PDF…", self.add_pdf, em=linha1)
        self.doc_box = QComboBox(self)
        self.doc_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.doc_box.setMinimumContentsLength(24)
        self.doc_box.addItems(sorted(self.project.documents))
        self.doc_box.setAccessibleName("Documento aberto")
        self.doc_box.activated.connect(lambda _i: self._select_document(self.doc_box.currentText()))
        linha1.addWidget(self.doc_box, 1)
        b = botao(
            "◀",
            lambda: self.go_page(self.page_index - 1),
            dica="Página anterior (PageUp)",
            em=linha1,
        )
        b.setFixedWidth(28)
        self.page_spin = QSpinBox(self)
        self.page_spin.setAccessibleName("Página")
        self.page_spin.setRange(0, 0)
        self.page_spin.editingFinished.connect(lambda: self.go_page(self.page_spin.value()))
        linha1.addWidget(self.page_spin)
        self.page_total = QLabel("/ 0", self)
        linha1.addWidget(self.page_total)
        b = botao(
            "▶",
            lambda: self.go_page(self.page_index + 1),
            dica="Próxima página (PageDown)",
            em=linha1,
        )
        b.setFixedWidth(28)
        botao("Salvar", self.save, dica="Ctrl+S", em=linha1)
        exportar = QToolButton(self)
        exportar.setText("Exportar")
        exportar.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(exportar)
        menu.addAction("Verdade para treino (ground_truth/)", self.export_ground_truth)
        menu.addAction("Fundir no manifesto dourado…", self.export_manifest)
        menu.addAction("Correções e pares de calibração", self.export_corrections)
        menu.addSeparator()
        menu.addAction("Idioma do documento = caixa «idioma»", self.apply_language)
        menu.addAction("Resumo do projeto", self.show_summary)
        exportar.setMenu(menu)
        linha1.addWidget(exportar)
        botao("Medir no livro…", self.open_measure, em=linha1)
        botao("Treinar…", self.open_training, em=linha1)
        barra.addWidget(QLabel("DPI", self))
        self.dpi_spin = QSpinBox(self)
        self.dpi_spin.setAccessibleName("Resolução do reconhecimento")
        self.dpi_spin.setRange(150, 600)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.setValue(300)
        barra.addWidget(self.dpi_spin)
        barra.addWidget(QLabel("idioma", self))
        self.lang_box = QComboBox(self)
        self.lang_box.setEditable(True)
        self.lang_box.addItems(LANGS)
        self.lang_box.setAccessibleName("Idioma do reconhecimento")
        barra.addWidget(self.lang_box)
        botao(
            "Reconhecer (F5)",
            self.recognise_page,
            dica="Reconhecer a página com o serviço do produto",
        )
        self.draw_button = botao("Desenhar região (D)", self.toggle_drawing)
        self.only_doubtful = QCheckBox("só duvidosas", self)
        self.only_doubtful.toggled.connect(lambda _v: self._fill_table())
        barra.addWidget(self.only_doubtful)
        botao(
            "Aceitar confiáveis",
            lambda: self.accept_confident(),
            dica="Aceita toda linha da página sem palavra fraca nem candidato discordante",
        )
        barra.addStretch(1)

        # Page above, line below: the pane is narrow and tall, so a side-by-side
        # split left the page 180 px wide.
        corpo = QSplitter(Qt.Orientation.Vertical, self)
        raiz.addWidget(corpo, 1)
        esquerda = QWidget(corpo)
        esq = QVBoxLayout(esquerda)
        esq.setContentsMargins(0, 0, 0, 0)
        zoom_bar = QHBoxLayout()
        esq.addLayout(zoom_bar)
        for texto, acao in (("−", lambda: self.zoom(1 / 1.25)), ("+", lambda: self.zoom(1.25))):
            b = QPushButton(texto, esquerda)
            b.setFixedWidth(28)
            b.clicked.connect(lambda _c=False, a=acao: a())
            zoom_bar.addWidget(b)
        ajustar = QPushButton("Ajustar largura", esquerda)
        ajustar.clicked.connect(lambda _c=False: self.fit_width())
        zoom_bar.addWidget(ajustar)
        self.zoom_label = QLabel("", esquerda)
        zoom_bar.addWidget(self.zoom_label)
        zoom_bar.addStretch(1)
        self.visor = _Visor(
            esquerda,
            ao_clicar=self._click_at,
            ao_clicar_direito=self._right_click,
            ao_desenhar=self._recognise_drawn,
        )
        esq.addWidget(self.visor, 1)
        corpo.addWidget(esquerda)

        direita = QWidget(corpo)
        dir_ = QVBoxLayout(direita)
        dir_.setContentsMargins(4, 0, 0, 0)
        self.crop_label = QLabel("Reconheça a página (F5) ou desenhe uma região (D).", direita)
        self.crop_label.setStyleSheet("background:#e5e7eb; padding:2px;")
        self.crop_label.setMinimumHeight(CROP_HEIGHT_PX + 8)
        self.crop_label.setMaximumHeight(CROP_HEIGHT_PX + 8)
        self.crop_label.setAccessibleName("Recorte da linha atual")
        dir_.addWidget(self.crop_label)
        self.context_label = QLabel("", direita)
        self.context_label.setStyleSheet("color:#6b7280;")
        dir_.addWidget(self.context_label)
        dir_.addWidget(QLabel("Leitura do motor (palavras fracas em destaque):", direita))
        self.reading = QTextEdit(direita)
        self.reading.setReadOnly(True)
        self.reading.setMaximumHeight(48)
        self.reading.setAccessibleName("Leitura do motor")
        dir_.addWidget(self.reading)
        self.alternatives = QListWidget(direita)
        self.alternatives.setMaximumHeight(52)
        self.alternatives.setAccessibleName("Leituras alternativas")
        self.alternatives.itemDoubleClicked.connect(lambda _i: self._use_alternative())
        dir_.addWidget(self.alternatives)
        self.reason_label = QLabel("", direita)
        self.reason_label.setStyleSheet("color:#b45309;")
        self.reason_label.setWordWrap(True)
        dir_.addWidget(self.reason_label)
        dir_.addWidget(
            QLabel(
                "Verdade (Enter aceita · Ctrl+Enter grava a edição · Ctrl+R rejeita):",
                direita,
            )
        )
        self.truth = QPlainTextEdit(direita)
        self.truth.setMaximumHeight(60)
        self.truth.setAccessibleName("Verdade da linha")
        self.truth.installEventFilter(self)
        dir_.addWidget(self.truth)
        paleta = QHBoxLayout()
        paleta.addWidget(QLabel("Figurinas:", direita))
        for key, glyph in FIGURINE_KEYS.items():
            b = QPushButton(glyph, direita)
            b.setToolTip(f"Alt+{key.upper()}")
            b.setFixedWidth(34)
            b.clicked.connect(lambda _c=False, g=glyph: self.insert_figurine(g))
            paleta.addWidget(b)
        conv = QPushButton("Letras → figurinas", direita)
        conv.clicked.connect(lambda _c=False: self.letters_to_figurines())
        paleta.addWidget(conv)
        paleta.addStretch(1)
        dir_.addLayout(paleta)
        botoes = QHBoxLayout()
        for texto, acao in (
            ("Aceitar leitura", lambda: self.decide(LineStatus.ACCEPTED)),
            ("Gravar edição", lambda: self.decide(LineStatus.EDITED)),
            ("Rejeitar (imagem)", lambda: self.decide(LineStatus.REJECTED)),
            ("Desfazer decisão", self._undo_line),
        ):
            b = QPushButton(texto, direita)
            b.clicked.connect(lambda _c=False, a=acao: a())
            botoes.addWidget(b)
        botoes.addStretch(1)
        for texto, delta in (("◀ anterior", -1), ("próxima ▶", 1)):
            b = QPushButton(texto, direita)
            b.clicked.connect(lambda _c=False, d=delta: self.step(d))
            botoes.addWidget(b)
        dir_.addLayout(botoes)
        self.table = QTableWidget(0, 5, direita)
        self.table.setHorizontalHeaderLabels(["#", "reg.", "estado", "conf.", "texto"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAccessibleName("Linhas da página")
        self.table.itemSelectionChanged.connect(self._on_table_select)
        dir_.addWidget(self.table, 1)
        corpo.addWidget(direita)
        corpo.setStretchFactor(0, 3)
        corpo.setStretchFactor(1, 2)
        corpo.setSizes([560, 440])

        self.status = QLabel("", self)
        self.status.setStyleSheet("padding:3px 6px; border-top:1px solid #d1d5db;")
        raiz.addWidget(self.status)

    def _atalhos(self) -> None:
        contexto = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for tecla, acao in (
            ("F5", self.recognise_page),
            ("Ctrl+S", self.save),
            ("PgUp", lambda: self.go_page(self.page_index - 1)),
            ("PgDown", lambda: self.go_page(self.page_index + 1)),
            ("Escape", self._stop_drawing),
        ):
            atalho = QShortcut(QKeySequence(tecla), self)
            atalho.setContext(contexto)
            atalho.activated.connect(acao)
        desenhar = QShortcut(QKeySequence("D"), self.visor)
        desenhar.setContext(contexto)
        desenhar.activated.connect(self.toggle_drawing)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802, PLR0911 - Qt name; one return per key
        """The truth field's keys: Enter decides, Ctrl+R rejects, Alt+n copies, Alt+k types ♔."""
        if obj is self.truth and event.type() == QEvent.Type.KeyPress:
            tecla, mods = event.key(), event.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            alt = bool(mods & Qt.KeyboardModifier.AltModifier)
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.decide(LineStatus.EDITED) if ctrl else self._on_enter()
                return True
            if ctrl and tecla == Qt.Key.Key_R:
                self.decide(LineStatus.REJECTED)
                return True
            if ctrl and tecla == Qt.Key.Key_Down:
                self.step(1)
                return True
            if ctrl and tecla == Qt.Key.Key_Up:
                self.step(-1)
                return True
            if alt and tecla in (Qt.Key.Key_1, Qt.Key.Key_2):
                self._use_alternative(index=tecla - Qt.Key.Key_1)
                return True
            if alt:
                letra = event.text().lower() or QKeySequence(tecla).toString().lower()
                if letra in FIGURINE_KEYS:
                    self.insert_figurine(FIGURINE_KEYS[letra])
                    return True
        return super().eventFilter(obj, event)

    # -- service ------------------------------------------------------------ #

    def _service(self) -> Any:
        if self.service is None:
            self.service = self._build_service(with_book=True)
        return self.service

    def _build_service(self, *, with_book: bool) -> Any:
        from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig

        config = OcrServiceConfig()
        if with_book and self.book is not None:
            config.figurine_tessdata = self.book.tessdata_dir
        else:
            config.figurine_candidates = with_book
        return OcrService(lang=self.lang_box.currentText(), config=config)

    def _refresh_book(self) -> None:
        self.book = None
        if self.document is not None:
            try:
                self.book = BookRegistry.default().for_pdf(self.project.pdf_for(self.document))
            except Exception as exc:  # noqa: BLE001 - a broken registry is a status line
                self._set_status(f"registro de modelos por livro ilegível: {exc}")
        self.service = None

    # -- documents ---------------------------------------------------------- #

    def add_pdf(self) -> None:
        caminho, _f = QFileDialog.getOpenFileName(self, "PDF digitalizado", "", "PDF (*.pdf)")
        if not caminho:
            return
        book = self.project.add_document(caminho)
        self.project.save()
        self.doc_box.clear()
        self.doc_box.addItems(sorted(self.project.documents))
        self._select_document(book)

    def _select_document(self, book: str) -> None:
        if book not in self.project.documents:
            return
        self.document = book
        self.doc_box.setCurrentText(book)
        try:
            total = page_count(self.project.pdf_for(book))
        except Exception as exc:  # noqa: BLE001 - a missing PDF is a message, not a crash
            QMessageBox.critical(
                self, "PDF", f"Não foi possível abrir {self.project.documents[book]}:\n{exc}"
            )
            return
        self.page_spin.setRange(0, max(0, total - 1))
        self.page_total.setText(f"/ {total - 1}")
        remembered = self.project.languages.get(book)
        if remembered:
            self.lang_box.setCurrentText(remembered)
        self._refresh_book()
        labelled = self.project.pages_of(book)
        self.go_page(labelled[0].page_index if labelled else 0)

    def go_page(self, index: int) -> None:
        if self.document is None:
            return
        total = page_count(self.project.pdf_for(self.document))
        index = max(0, min(total - 1, index))
        self._flush_timer()
        self.page_index = index
        self.page_spin.setValue(index)
        self.page = self.project.page(self.document, index)
        self.current = None
        self.selected_region = None
        self._render_page()
        self._fill_table()
        if self.page and self.page.regions:
            self._select_first_pending()
        else:
            self._show_line(None)
        self._refresh_status()

    # -- recognition -------------------------------------------------------- #

    def recognise_page(self) -> None:
        if self.document is None:
            QMessageBox.information(self, TITULO, "Adicione um PDF primeiro.")
            return
        decided = self.page is not None and any(line.done for _, line in self.page.lines())
        if (
            decided
            and QMessageBox.question(
                self,
                "Reconhecer de novo",
                "Esta página já tem decisões. Reconhecer de novo descarta todas. Continuar?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        pdf, book, index = self.project.pdf_for(self.document), self.document, self.page_index
        dpi, lang = int(self.dpi_spin.value()), self.lang_box.currentText()
        if self.project.languages.get(book) != lang:
            self.project.set_language(book, lang)
        self._set_status(f"Reconhecendo página {index} a {dpi} DPI ({lang})…")
        service = self._service()

        def done(kind: str, payload: Any) -> None:
            if kind == "error":
                QMessageBox.critical(self, "OCR", str(payload))
                self._refresh_status()
                return
            page: PageLabels = payload
            self.project.put_page(page)
            self.project.save()
            if self.page_index == page.page_index and self.document == page.document:
                self.page = page
                self._render_page()
                self._fill_table()
                self._select_first_pending()
            self._refresh_status()

        if not self.fila.run(
            lambda: label_page(service, pdf, book, index, dpi=dpi, lang=lang), done
        ):
            self._set_status("Aguarde: há uma tarefa em andamento.")

    def toggle_drawing(self) -> None:
        if self.page is None:
            self._ensure_page()
        ligado = not self.visor.desenhando
        self.visor.modo_desenho(ligado)
        self.draw_button.setText("Desenhando… (Esc)" if ligado else "Desenhar região (D)")

    def _stop_drawing(self) -> None:
        if self.visor.desenhando:
            self.toggle_drawing()

    def _ensure_page(self) -> PageLabels | None:
        if self.page is not None or self.document is None:
            return self.page
        pdf = self.project.pdf_for(self.document)
        width, height = page_size(pdf, self.page_index)
        self.page = PageLabels(
            document=self.document,
            pdf_path=str(pdf),
            page_index=self.page_index,
            width_pt=width,
            height_pt=height,
            dpi=float(self.dpi_spin.value()),
            lang=self.lang_box.currentText(),
        )
        self.project.put_page(self.page)
        return self.page

    def _recognise_drawn(self, rect: tuple[float, float, float, float]) -> None:
        self.draw_button.setText("Desenhar região (D)")
        page = self._ensure_page()
        if page is None:
            return
        service = self._service()
        lang = self.lang_box.currentText()
        self._set_status("Reconhecendo a região desenhada…")

        def done(kind: str, payload: Any) -> None:
            if kind == "error":
                QMessageBox.critical(self, "OCR", str(payload))
                return
            region: RegionLabel = payload
            page.regions.append(region)
            self.project.save()
            self._draw_boxes()
            self._fill_table()
            if region.lines:
                self._select_line(region, region.lines[0])
            self._refresh_status()

        self.fila.run(lambda: recognise_rect(service, page, rect, lang=lang), done)

    # -- page view ---------------------------------------------------------- #

    def _render_page(self) -> None:
        if self.document is None:
            self.visor.mostrar_pagina(None, PAGE_DPI)
            return
        rgb = render_rgb(self.project.pdf_for(self.document), self.page_index, PAGE_DPI)
        self.visor.mostrar_pagina(rgb, PAGE_DPI)
        self.zoom_label.setText(f"{self.visor.zoom * 100 / 1.6:.0f} %")
        self._draw_boxes()

    def _draw_boxes(self) -> None:
        self.visor.desenhar_caixas(
            self.page,
            selecionada=self.selected_region,
            atual=self.current[1] if self.current else None,
        )

    def zoom(self, factor: float) -> None:
        self.visor.zoom = max(0.4, min(6.0, self.visor.zoom * factor))
        self.visor.aplicar_zoom()
        self.zoom_label.setText(f"{self.visor.zoom * 100 / 1.6:.0f} %")

    def fit_width(self) -> None:
        self.visor.ajustar_largura()
        self.zoom_label.setText(f"{self.visor.zoom * 100 / 1.6:.0f} %")

    def _click_at(self, x: float, y: float) -> None:
        if self.page is None:
            return
        best: tuple[float, RegionLabel, LineLabel | None] | None = None
        for region in self.page.regions:
            for line in region.lines:
                bx0, by0, bx1, by1 = line.box
                if bx0 <= x <= bx1 and by0 <= y <= by1:
                    area = (bx1 - bx0) * (by1 - by0)
                    if best is None or area < best[0]:
                        best = (area, region, line)
            rx0, ry0, rx1, ry1 = region.rect
            if best is None and rx0 <= x <= rx1 and ry0 <= y <= ry1:
                best = ((rx1 - rx0) * (ry1 - ry0) + 1e9, region, None)
        if best is None:
            return
        _, region, line = best
        if line is not None:
            self._select_line(region, line)
        else:
            self.selected_region = region
            self._draw_boxes()

    def _right_click(self, x: float, y: float, onde: Any) -> None:
        if self.page is None:
            return
        region = next(
            (
                r
                for r in self.page.regions
                if r.rect[0] <= x <= r.rect[2] and r.rect[1] <= y <= r.rect[3]
            ),
            None,
        )
        if region is None:
            return
        self.selected_region = region
        self._draw_boxes()
        menu = QMenu(self)
        tipos = menu.addMenu(f"Tipo da região {region.index} ({region.kind})")
        for kind in kinds_for_menu():
            tipos.addAction(kind, lambda k=kind, r=region: self._set_kind(r, k))
        menu.addAction(
            "Aceitar linhas confiáveis desta região", lambda r=region: self.accept_confident(r)
        )
        menu.addAction(
            "Rejeitar todas as linhas (não é texto)", lambda r=region: self._reject_region(r)
        )
        menu.addAction(
            f"FEN inicial dos lances… ({region.start_fen or 'sem FEN'})",
            lambda r=region: self._set_start_fen(r),
        )
        menu.addSeparator()
        menu.addAction("Remover região", lambda r=region: self._remove_region(r))
        menu.exec(onde)

    def _set_kind(self, region: RegionLabel, kind: str) -> None:
        region.kind = kind
        self.project.save()
        self._draw_boxes()
        self._fill_table()

    def _set_start_fen(self, region: RegionLabel) -> None:
        fen, ok = QInputDialog.getText(
            self,
            "FEN inicial",
            "FEN da posição antes do primeiro lance desta região (vazio remove):",
            QLineEdit.EchoMode.Normal,
            region.start_fen,
        )
        if not ok:
            return
        fen = fen.strip()
        if fen:
            problem = fen_problem(fen)
            if problem:
                QMessageBox.critical(self, "FEN", problem)
                return
        region.start_fen = fen
        self.project.save()
        self._fill_table()

    def _remove_region(self, region: RegionLabel) -> None:
        if self.page is None:
            return
        if (
            any(line.done for line in region.lines)
            and QMessageBox.question(
                self, "Remover região", "A região tem decisões gravadas. Remover mesmo assim?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.page.regions.remove(region)
        if self.current and self.current[0] is region:
            self.current = None
        self.selected_region = None
        self.project.save()
        self._draw_boxes()
        self._fill_table()
        self._select_first_pending()

    def _reject_region(self, region: RegionLabel) -> None:
        if self.page is None:
            return
        for line in region.lines:
            self.project.decide(self.page, line, LineStatus.REJECTED, note="região rejeitada")
        self.project.save()
        self._after_decision()

    # -- lines -------------------------------------------------------------- #

    def _visible_lines(self) -> list[tuple[RegionLabel, LineLabel]]:
        if self.page is None:
            return []
        threshold = self.project.doubt_threshold
        pairs = list(self.page.lines())
        if self.only_doubtful.isChecked():
            pairs = [(r, line) for r, line in pairs if not line.done and line.doubtful(threshold)]
        return pairs

    def _fill_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        threshold = self.project.doubt_threshold
        selecionar = -1
        for row, (region, line) in enumerate(self._visible_lines()):
            self.table.insertRow(row)
            text = line.text if line.done else line.hypothesis
            valores = (
                str(line.index),
                str(region.index),
                status_pt(line.status),
                f"{line.confidence:.2f}",
                text.replace("\n", " "),
            )
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                item.setForeground(QBrush(QColor(STATUS_COLOR[line.status])))
                if not line.done and line.doubtful(threshold):
                    fonte = item.font()
                    fonte.setBold(True)
                    item.setFont(fonte)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, (region.index, line.index))
                self.table.setItem(row, col, item)
            if self.current is not None and line is self.current[1]:
                selecionar = row
        self.table.resizeColumnsToContents()
        if selecionar >= 0:
            self.table.selectRow(selecionar)
            self.table.scrollToItem(self.table.item(selecionar, 0))
        self.table.blockSignals(False)

    def _on_table_select(self) -> None:
        linhas = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not linhas or self.page is None:
            return
        item = self.table.item(linhas[0].row(), 0)
        if item is None:
            return
        region_index, line_index = item.data(Qt.ItemDataRole.UserRole)
        region = next((r for r in self.page.regions if r.index == region_index), None)
        if region is None:
            return
        line = next((c for c in region.lines if c.index == line_index), None)
        if line is not None and (self.current is None or line is not self.current[1]):
            self._select_line(region, line, from_table=True)

    def _select_first_pending(self) -> None:
        pairs = self._visible_lines()
        pending = next(((r, line) for r, line in pairs if not line.done), None) or (
            pairs[0] if pairs else None
        )
        if pending:
            self._select_line(*pending)
        else:
            self._show_line(None)

    def _select_line(
        self, region: RegionLabel, line: LineLabel, *, from_table: bool = False
    ) -> None:
        self._flush_timer()
        self.current = (region, line)
        self.selected_region = region
        self.opened_at = time.perf_counter()
        self._draw_boxes()
        self._show_line(line)
        self.visor.centralizar(line.box)
        if not from_table:
            self._fill_table()

    def _show_line(self, line: LineLabel | None) -> None:
        self.reading.clear()
        self.alternatives.clear()
        self.truth.clear()
        if line is None or self.page is None:
            self.crop_label.setPixmap(QPixmap())
            self.crop_label.setText("Reconheça a página (F5) ou desenhe uma região (D).")
            self.context_label.setText("")
            self.reason_label.setText("")
            return
        region = self.current[0] if self.current else None
        pad = 3.0
        x0, y0, x1, y1 = line.box
        rgb = render_rgb(
            self.page.pdf_path,
            self.page.page_index,
            300,
            clip=(x0 - pad, y0 - pad, x1 + pad, y1 + pad),
        )
        pixmap = _pixmap(rgb)
        avail = max(300, self.crop_label.width() - 8)
        ratio = min(
            avail / max(1, pixmap.width()), CROP_HEIGHT_PX / max(1, pixmap.height()), CROP_MAX_ZOOM
        )
        self.crop_label.setText("")
        self.crop_label.setPixmap(
            pixmap.scaled(
                max(1, int(pixmap.width() * ratio)),
                max(1, int(pixmap.height() * ratio)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        threshold = self.project.doubt_threshold
        html: list[str] = []
        for word in line.words:
            texto = word.text.replace("&", "&amp;").replace("<", "&lt;")
            if word.confidence >= threshold:
                html.append(texto)
            elif word.confidence < threshold * 0.7:
                html.append(f'<span style="background:#fca5a5">{texto}</span>')
            else:
                html.append(f'<span style="background:#fde68a">{texto}</span>')
        self.reading.setHtml(" ".join(html) if line.words else line.hypothesis)
        for source, text in line.alternatives:
            self.alternatives.addItem(f"{source}: {text}")
        if not line.alternatives:
            self.alternatives.addItem("(nenhum candidato leu esta linha de outro jeito)")
        partition = self.page.region_partition(region).value if region else ""
        if partition == "blind":
            partition = "blind (cega: não treina)"
        weak = line.low_confidence_words(threshold)
        parts = [
            f"linha {line.index} · região {region.index} ({region.kind})" if region else "",
            f"conf. {line.confidence:.2f}",
            f"partição {partition}",
        ]
        if line.done:
            parts.append(
                f"{status_pt(line.status)} por {line.reviewer or '?'} em {line.seconds:.0f}s"
            )
        self.context_label.setText(" · ".join(p for p in parts if p))
        reasons = []
        if weak:
            reasons.append("palavras fracas: " + ", ".join(weak[:WEAK_WORDS_SHOWN]))
        if region and region.reasons:
            reasons.append("; ".join(region.reasons[:2]))
        if line.alternatives:
            reasons.append(
                f"{len(line.alternatives)} leitura(s) alternativa(s) — Alt+1/Alt+2 copia"
            )
        self.reason_label.setText(" · ".join(reasons))
        self.truth.setPlainText(line.text if line.done else line.hypothesis)
        self.truth.setFocus()
        self.truth.moveCursor(QTextCursor.MoveOperation.End)

    def _use_alternative(self, *, index: int | None = None) -> None:
        if index is None:
            index = max(0, self.alternatives.currentRow())
        if self.current and index < len(self.current[1].alternatives):
            self.truth.setPlainText(self.current[1].alternatives[index][1])

    def insert_figurine(self, glyph: str) -> None:
        self.truth.insertPlainText(glyph)
        self.truth.setFocus()

    def letters_to_figurines(self) -> None:
        text = self.truth.toPlainText()
        converted = letters_to_figurines(text)
        if converted != text:
            self.truth.setPlainText(converted)
        self.truth.setFocus()

    def _on_enter(self) -> None:
        typed = self.truth.toPlainText().strip()
        if self.current and typed and typed != self.current[1].hypothesis.strip():
            self.decide(LineStatus.EDITED)
        else:
            self.decide(LineStatus.ACCEPTED)

    def decide(self, status: LineStatus) -> None:
        if self.current is None or self.page is None:
            return
        _, line = self.current
        typed = self.truth.toPlainText().strip()
        seconds = time.perf_counter() - self.opened_at if self.opened_at else 0.0
        self.opened_at = 0.0
        if status is LineStatus.EDITED and not typed:
            status = LineStatus.REJECTED
        if status is LineStatus.EDITED and typed == line.hypothesis.strip():
            status = LineStatus.ACCEPTED
        self.project.decide(
            self.page,
            line,
            status,
            text=typed if status is LineStatus.EDITED else None,
            seconds=seconds,
        )
        self._after_decision(advance=True)

    def _undo_line(self) -> None:
        if self.current and self.page:
            self.project.reset(self.page, self.current[1])
            self._after_decision()

    def _after_decision(self, *, advance: bool = False) -> None:
        self.project.save()
        self._fill_table()
        self._draw_boxes()
        self._refresh_status()
        if advance:
            self.step(1, pending_only=True)
        elif self.current:
            self._show_line(self.current[1])

    def step(self, delta: int, *, pending_only: bool = False) -> None:
        pairs = self._visible_lines()
        if not pairs:
            return
        if self.current is None:
            self._select_line(*pairs[0])
            return
        position = next((i for i, (_r, line) in enumerate(pairs) if line is self.current[1]), -1)
        if pending_only:
            after = pairs[position + 1 :] + pairs[: position + 1]
            target = next(((r, line) for r, line in after if not line.done), None)
            if target is None:
                self._flush_timer()
                self._show_line(self.current[1])
                self._set_status("Página concluída: todas as linhas decididas.")
                return
        else:
            target = pairs[(position + delta) % len(pairs)]
        self._select_line(*target)

    def accept_confident(self, region: RegionLabel | None = None) -> None:
        if self.page is None:
            return
        threshold = self.project.doubt_threshold
        count = 0
        for reg in [region] if region else self.page.regions:
            for line in reg.lines:
                if not line.done and not line.doubtful(threshold):
                    self.project.decide(
                        self.page, line, LineStatus.ACCEPTED, note="aceita em lote (confiante)"
                    )
                    count += 1
        self._after_decision()
        self._set_status(f"{count} linha(s) confiantes aceitas; as duvidosas continuam pendentes.")

    def _flush_timer(self) -> None:
        if self.opened_at and self.page is not None:
            self.page.seconds += time.perf_counter() - self.opened_at
        self.opened_at = 0.0

    # -- status ------------------------------------------------------------- #

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def _book_status(self) -> str:
        if self.book is None:
            return ""
        return f" · modelo do livro: {', '.join(self.book.models)} ({self.book.trained_at[:10]})"

    def _refresh_status(self) -> None:
        if self.page is None:
            self._set_status(
                "Sem reconhecimento nesta página. F5 reconhece; D desenha uma região."
                + self._book_status()
            )
            return
        counts = self.page.counts()
        threshold = self.project.doubt_threshold
        doubtful = sum(
            1 for _, line in self.page.lines() if not line.done and line.doubtful(threshold)
        )
        blind = (
            f" · {self.page.blind_regions} região(ões) na partição cega: entram no manifesto, "
            f"ficam fora do treino e da calibração"
            if self.page.blind_regions
            else ""
        )
        minutes, seconds = divmod(int(self.page.seconds), 60)
        self._set_status(
            f"{counts['total']} linhas · {counts['pending']} pendentes ({doubtful} duvidosas) · "
            f"{counts['accepted']} aceitas · {counts['edited']} editadas · "
            f"{counts['rejected']} rejeitadas · tempo na página {minutes:02d}:{seconds:02d}{blind}"
            + self._book_status()
        )

    # -- exports ------------------------------------------------------------ #

    def save(self) -> None:
        self._flush_timer()
        self.project.save()
        self._set_status(f"Projeto salvo em {self.project.root}")

    def export_ground_truth(self) -> None:
        self.save()
        out = self.project.root / "ground_truth"
        self._set_status("Gerando a verdade por linha…")

        def done(kind: str, payload: Any) -> None:
            if kind == "error":
                QMessageBox.critical(self, "Exportar", str(payload))
                return
            QMessageBox.information(
                self,
                "Verdade para treino",
                f"{payload.written} linhas escritas em {out}"
                f"\npor partição: {payload.by_partition}"
                f"\nretidas (regiões cegas): {payload.withheld_blind}"
                f" · minúsculas: {payload.skipped_tiny}",
            )
            self._refresh_status()

        self.fila.run(lambda: write_ground_truth(self.project, out), done)

    def export_manifest(self) -> None:
        self.save()
        items = manifest_items(self.project)
        if not items:
            QMessageBox.information(
                self,
                "Manifesto",
                "Nenhuma região completa (todas as linhas decididas e ao menos uma mantida).",
            )
            return
        sugestao = (
            models_root().parents[1] / "benchmarks" / "corpus" / "golden" / "manifest.private.json"
        )
        caminho, _f = QFileDialog.getSaveFileName(
            self,
            "Manifesto dourado",
            str(sugestao),
            "JSON (*.json)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not caminho:
            return
        try:
            added, replaced = merge_into_manifest(caminho, items)
        except Exception as exc:  # noqa: BLE001 - shown to the reviewer
            QMessageBox.critical(self, "Manifesto", str(exc))
            return
        QMessageBox.information(
            self, "Manifesto", f"{added} itens novos, {replaced} substituídos em {caminho}"
        )

    def export_corrections(self) -> None:
        self.save()
        rows = corrections(self.project)
        pairs = calibration_pairs(self.project)
        (self.project.root / "corrections.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        (self.project.root / "calibration_pairs.json").write_text(
            json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        QMessageBox.information(
            self,
            "Correções",
            f"{len(rows)} correções e {len(pairs)} linhas de pares gravadas em "
            f"{self.project.root}\n"
            f"(retidas por região cega: {withheld_lines(self.project)})",
        )

    def apply_language(self) -> None:
        if self.document is None:
            return
        lang = self.lang_box.currentText().strip()
        changed = self.project.set_language(self.document, lang)
        self.project.save()
        QMessageBox.information(
            self,
            "Idioma",
            f"{self.document}: idioma {lang}; {changed} página(s) rotulada(s) re-marcadas "
            f"(faceta prose_lang = {lang.split('+')[0]}). Refaça «Fundir no manifesto» para o "
            "corpus refletir.",
        )
        self._refresh_status()

    def show_summary(self) -> None:
        summary = self.project.summary()
        lines = summary.pop("lines")
        text = "\n".join(f"{k}: {v}" for k, v in summary.items())
        text += "\nlinhas: " + ", ".join(f"{k} {v}" for k, v in lines.items())
        QMessageBox.information(self, "Resumo do projeto", text)

    # -- training and measuring --------------------------------------------- #

    def open_training(self) -> None:
        self.save()
        dialogo = DialogoDeTreino(
            self, self.project, document=self.document, on_trained=self._trained
        )
        dialogo.show()

    def _trained(self, book: BookModel | None) -> None:
        self._refresh_book()
        self._refresh_status()
        if book is not None:
            QMessageBox.information(
                self,
                "Modelo do livro",
                f"{', '.join(book.models)} registrado para\n{book.pdf_path}\n\n"
                "A importação deste PDF e o F5 desta aba passam a usá-lo como segunda opinião "
                "nas regiões de lances. «Medir no livro…» diz quanto mudou.",
            )

    def open_measure(self) -> None:
        if self.document is None:
            QMessageBox.information(self, "Medir no livro", "Adicione um PDF primeiro.")
            return
        self.save()
        self._refresh_book()
        if self.book is None:
            QMessageBox.information(
                self,
                "Medir no livro",
                "Este livro ainda não tem modelo registrado: treine primeiro (Treinar…, com "
                "«modelo deste livro» marcado).",
            )
            return
        dialogo = DialogoDeMedida(
            self,
            self.project,
            self.document,
            services={
                "sem modelo": self._build_service(with_book=False),
                "com modelo": self._build_service(with_book=True),
            },
        )
        dialogo.show()


# --------------------------------------------------------------------------- #
# Dialogs
# --------------------------------------------------------------------------- #


class DialogoDeTreino(QDialog):
    """*Treinar…* — o ajuste fino, por padrão para o livro aberto (ROTULAGEM.md §7a)."""

    def __init__(  # noqa: PLR0915 - one form, row by row
        self,
        parent: QWidget,
        project: LabelProject,
        *,
        document: str | None = None,
        on_trained: Callable[[BookModel | None], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.document = document
        self.on_trained = on_trained
        self.setWindowTitle("Ajuste fino do Tesseract")
        self.resize(900, 680)
        self.tuner: TesseractFineTuner | None = None
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        raiz = QVBoxLayout(self)
        form = QGridLayout()
        raiz.addLayout(form)
        modelos = models_root()
        best = modelos.parent / "tessdata_best"
        book_lang = (project.languages.get(document or "") or "por").split("+")[0] or "por"
        self.gt_edit = QLineEdit(str(project.root / "ground_truth"), self)
        self.out_edit = QLineEdit(str(modelos), self)
        candidato = best / f"{book_lang}.traineddata"
        self.base_edit = QLineEdit(str(candidato) if candidato.is_file() else "", self)
        for n, (rotulo, edit, pasta) in enumerate(
            (
                ("Verdade (ground_truth/)", self.gt_edit, True),
                ("Pasta de saída (tessdata)", self.out_edit, True),
                ("Modelo base float (tessdata_best)", self.base_edit, False),
            )
        ):
            form.addWidget(QLabel(rotulo, self), n, 0)
            edit.setAccessibleName(rotulo)
            form.addWidget(edit, n, 1)
            b = QPushButton("…", self)
            b.setFixedWidth(28)
            b.clicked.connect(lambda _c=False, e=edit, p=pasta: self._pick(e, pasta=p))
            form.addWidget(b, n, 2)
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Idioma base", self))
        self.base_lang = QComboBox(self)
        self.base_lang.setEditable(True)
        self.base_lang.addItems(BASE_LANGS)
        self.base_lang.setCurrentText(book_lang)
        linha.addWidget(self.base_lang)
        linha.addWidget(QLabel("nome do modelo", self))
        self.name_edit = QLineEdit("", self)
        self.name_edit.setAccessibleName("Nome do modelo")
        linha.addWidget(self.name_edit)
        linha.addWidget(QLabel("iterações", self))
        self.iterations = QSpinBox(self)
        self.iterations.setRange(100, 50000)
        self.iterations.setSingleStep(100)
        self.iterations.setValue(2000)
        self.iterations.setAccessibleName("Iterações")
        linha.addWidget(self.iterations)
        linha.addWidget(QLabel("taxa", self))
        self.rate = QLineEdit("0.001", self)
        self.rate.setAccessibleName("Taxa de aprendizado")
        self.rate.setFixedWidth(70)
        linha.addWidget(self.rate)
        self.extend = QCheckBox("estender alfabeto (figurinas)", self)
        self.extend.setChecked(True)
        linha.addWidget(self.extend)
        linha.addStretch(1)
        form.addLayout(linha, 3, 0, 1, 3)
        self.for_book = QCheckBox(self._book_label(), self)
        self.for_book.setChecked(document is not None)
        self.for_book.setEnabled(document is not None)
        self.for_book.toggled.connect(lambda _v: self._apply_book_choice())
        form.addWidget(self.for_book, 4, 0, 1, 3)
        self._apply_book_choice()
        botoes = QHBoxLayout()
        raiz.addLayout(botoes)
        for texto, acao in (
            ("Baixar base (tessdata_best)…", self.download_base),
            ("Verificar (preflight)", self.run_preflight),
        ):
            b = QPushButton(texto, self)
            b.clicked.connect(lambda _c=False, a=acao: a())
            botoes.addWidget(b)
        self.train_button = QPushButton("Treinar", self)
        self.train_button.clicked.connect(lambda _c=False: self.run_training())
        botoes.addWidget(self.train_button)
        cancelar = QPushButton("Cancelar", self)
        cancelar.clicked.connect(lambda _c=False: self.cancel())
        botoes.addWidget(cancelar)
        botoes.addStretch(1)
        self.progress_label = QLabel("", self)
        botoes.addWidget(self.progress_label)
        self.progress = QProgressBar(self)
        self.progress.setFixedWidth(260)
        botoes.addWidget(self.progress)
        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background:#111827; color:#e5e7eb; font-family:Consolas;")
        self.log.setAccessibleName("Registro do treino")
        raiz.addWidget(self.log, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._hint()

    def _book_label(self) -> str:
        if self.document is None:
            return "modelo deste livro (abra um PDF primeiro)"
        return (
            f"modelo deste livro: só as linhas de «{self.document}», salvo em "
            f"{book_dir(models_root(), self.document)} e usado ao importar este PDF"
        )

    def _apply_book_choice(self) -> None:
        if self.for_book.isChecked() and self.document is not None:
            self.out_edit.setText(str(book_dir(models_root(), self.document)))
        elif self.out_edit.text() == str(book_dir(models_root(), self.document or "")):
            self.out_edit.setText(str(models_root()))

    def _hint(self) -> None:
        try:
            tools = find_training_tools()
            self._append(f"ferramentas: {tools.lstmtraining}\ntessdata: {tools.tessdata_dir}")
            self._append(
                "Atenção: o instalador do Windows traz modelos inteiros (tessdata_fast); "
                "o ajuste fino exige o modelo float de tessdata_best — indique-o em "
                "«Modelo base float»."
            )
        except TrainingToolsError as exc:
            self._append(f"ERRO: {exc}")
            self.train_button.setEnabled(False)

    def _pick(self, edit: QLineEdit, *, pasta: bool) -> None:
        if pasta:
            caminho = QFileDialog.getExistingDirectory(self, "Pasta", edit.text())
        else:
            caminho, _f = QFileDialog.getOpenFileName(
                self, "Modelo base", "", "traineddata (*.traineddata)"
            )
        if caminho:
            edit.setText(caminho)

    def _config(self) -> FineTuneConfig:
        for_book = self.for_book.isChecked() and self.document is not None
        return FineTuneConfig(
            base_lang=self.base_lang.currentText().strip() or "por",
            base_model=Path(self.base_edit.text()) if self.base_edit.text().strip() else None,
            model_name=self.name_edit.text().strip(),
            max_iterations=int(self.iterations.value()),
            learning_rate=float(self.rate.text() or "0.001"),
            extend_charset=self.extend.isChecked(),
            documents=(self.document,) if for_book and self.document else (),
        )

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)

    def download_base(self) -> None:
        lang = self.base_lang.currentText().strip() or "por"
        best = models_root().parent / "tessdata_best"
        if (
            QMessageBox.question(
                self,
                "Baixar modelo base",
                f"Baixar tessdata_best/{lang}.traineddata (Apache-2.0, ~10–30 MB) de\n"
                f"github.com/tesseract-ocr/tessdata_best para {best}?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        def work() -> None:
            try:
                path = download_base_model(lang, best, log=lambda t: self.queue.put(("log", t)))
                self.queue.put(("base", str(path)))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", f"ERRO no download: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def run_preflight(self) -> None:
        gt_dir = Path(self.gt_edit.text())
        if not (gt_dir / "index.jsonl").is_file():
            self._append(
                f"Sem {gt_dir / 'index.jsonl'}: exporte a verdade para treino primeiro "
                "(menu Exportar)."
            )
            return
        config = self._config()

        def work() -> None:
            try:
                self.queue.put(
                    ("log", json.dumps(preflight(gt_dir, config), ensure_ascii=False, indent=1))
                )
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", f"ERRO: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def run_training(self) -> None:
        if self.tuner is not None:
            self._append("Já há um treino em andamento.")
            return
        gt_dir, out_dir = Path(self.gt_edit.text()), Path(self.out_edit.text())
        if not (gt_dir / "index.jsonl").is_file():
            self._append("Exporte a verdade para treino primeiro (menu Exportar).")
            return
        config = self._config()
        self.train_button.setEnabled(False)
        self.progress.setRange(0, config.max_iterations)
        self.progress.setValue(0)

        def work() -> None:
            try:
                self.tuner = TesseractFineTuner(
                    gt_dir,
                    out_dir,
                    config,
                    log=lambda line: self.queue.put(("log", line)),
                    progress=lambda info: self.queue.put(("progress", info)),
                )
                self.queue.put(("done", self.tuner.run()))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("done_error", exc))

        threading.Thread(target=work, daemon=True).start()

    def cancel(self) -> None:
        if self.tuner is not None:
            self.tuner.cancel()
            self._append(
                "Cancelado: a ferramenta em execução foi encerrada; o relatório registra a falha."
            )

    def _finish(self, report: Any) -> None:
        book: BookModel | None = None
        if report.status == "trained" and self.for_book.isChecked() and self.document is not None:
            try:
                registry = BookRegistry.default()
                book = register_training(
                    registry,
                    self.project.pdf_for(self.document),
                    self.document,
                    report,
                    base_lang=self.base_lang.currentText().strip(),
                )
                self._append(
                    f"registrado em {registry.path}: ao importar {book.pdf_path} o caissa "
                    f"usa {', '.join(book.models)}."
                )
            except Exception as exc:  # noqa: BLE001 - the model exists; only the binding failed
                self._append(f"ERRO ao registrar o modelo do livro: {exc}")
        if self.on_trained is not None:
            self.on_trained(book)

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append(str(payload))
                elif kind == "base":
                    self.base_edit.setText(str(payload))
                elif kind == "progress":
                    if "iteration" in payload:
                        self.progress.setValue(int(payload["iteration"]))
                        self.progress_label.setText(
                            f"iteração {payload['iteration']} · erro de treino "
                            f"{payload['char_train']:.2f} %"
                        )
                    elif "lstmf" in payload:
                        self.progress_label.setText(
                            f"lstmf {payload['lstmf']}/{payload['lstmf_total']}"
                        )
                elif kind == "done":
                    self.tuner = None
                    self.train_button.setEnabled(True)
                    self._append(payload.markdown())
                    self._finish(payload)
                elif kind == "done_error":
                    self.tuner = None
                    self.train_button.setEnabled(True)
                    self._append(f"ERRO: {payload}")
        except queue.Empty:
            pass


class DialogoDeMedida(QDialog):
    """*Medir no livro…* — as páginas rotuladas relidas sem e com o modelo (ROTULAGEM.md §7c)."""

    def __init__(
        self, parent: QWidget, project: LabelProject, document: str, *, services: dict[str, Any]
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.document = document
        self.services = services
        self.cancelled = False
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.setWindowTitle(f"Medir no livro — {document}")
        self.resize(860, 560)
        raiz = QVBoxLayout(self)
        barra = QHBoxLayout()
        raiz.addLayout(barra)
        pages = [p.page_index for p in project.pages_of(document) if p.regions]
        barra.addWidget(
            QLabel(
                f"{len(pages)} página(s) rotulada(s) serão lidas de novo, sem e "
                "com o modelo, e comparadas com a verdade.",
                self,
            )
        )
        barra.addStretch(1)
        cancelar = QPushButton("Cancelar", self)
        cancelar.clicked.connect(lambda _c=False: self.cancel())
        barra.addWidget(cancelar)
        self.run_button = QPushButton("Medir", self)
        self.run_button.clicked.connect(lambda _c=False: self.run())
        barra.addWidget(self.run_button)
        self.progress_label = QLabel("", self)
        raiz.addWidget(self.progress_label)
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setStyleSheet("font-family:Consolas;")
        self.text.setAccessibleName("Resultado da medição")
        raiz.addWidget(self.text, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def run(self) -> None:
        self.run_button.setEnabled(False)
        self.cancelled = False

        def work() -> None:
            try:
                measure = measure_book(
                    self.project,
                    self.document,
                    self.services,
                    progress=lambda t: self.queue.put(("progress", t)),
                    should_cancel=lambda: self.cancelled,
                )
                self.queue.put(("done", measure))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()

    def cancel(self) -> None:
        self.cancelled = True

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "progress":
                    self.progress_label.setText(str(payload))
                elif kind == "done":
                    self.run_button.setEnabled(True)
                    self._show(payload)
                elif kind == "error":
                    self.run_button.setEnabled(True)
                    self.progress_label.setText(f"ERRO: {payload}")
        except queue.Empty:
            pass

    def _show(self, measure: BookMeasure) -> None:
        json_path, md_path = measure.save(self.project.root / "medidas")
        self.progress_label.setText(f"gravado em {md_path} e {json_path.name}")
        self.text.setPlainText(measure.markdown())
