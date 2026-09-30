"""O cartão de uma linha duvidosa: recorte, leitura, alternativas, motivo, verdade.

É a metade direita da aba **Rotulagem** (:mod:`caissa.ui.views.rotulagem`) e a metade
direita da janela de **revisão de texto** (:mod:`caissa.ui.views.revisao_de_texto`,
OCR_UI_ROADMAP passo 14): as duas mostram a mesma coisa a quem decide — o recorte da
página em 300 DPI, o que o motor leu com as palavras fracas em destaque, o que os outros
candidatos leram, por que a linha está em dúvida, e o campo onde a pessoa escreve a
verdade — e as duas ouvem as mesmas teclas nesse campo (Enter aceita, Ctrl+Enter grava
a edição, Ctrl+R rejeita, Alt+1/Alt+2 copiam uma alternativa, Alt+K/Q/R/B/N/P digitam a
figurina, Ctrl+↑/↓ andam). O cartão emite sinais; quem o monta decide o que fazer.

Nada aqui é regra: a paleta de figurinas e a conversão «Letras → figurinas» vêm de
:mod:`caissa.ocr.labeling.helpers`, sem toolkit.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QKeySequence, QPixmap, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from caissa.ocr.labeling.helpers import FIGURINE_KEYS, letters_to_figurines
from caissa.ui.theme import pele
from caissa.ui.widgets.fileira_fluida import FileiraFluida
from caissa.ui.widgets.rotulo_que_encolhe import RotuloQueEncolhe

__all__ = ["CROP_HEIGHT_PX", "CROP_MAX_ZOOM", "CartaoDaLinha", "leitura_em_html", "pelas_setas",
           "pixmap_de"]

CROP_HEIGHT_PX = 90
CROP_MAX_ZOOM = 3.0
#: Narrower than this, the crop label has not been laid out yet (width 0, or Qt's default 100).
CROP_LAID_OUT_MIN = 120
#: Below this share of the doubt threshold a weak word is painted red, not amber.
RED_SHARE = 0.7
NOME_DA_PECA = {"♔": "rei", "♕": "dama", "♖": "torre", "♗": "bispo", "♘": "cavalo", "♙": "peão"}


def pelas_setas(tabela: QAbstractItemView) -> bool:
    """Se a linha da ``tabela`` mudou pela tecla, com o foco nela -- e não pelo mouse.

    Quem anda pelas linhas com as setas (ou o PgUp, o PgDn, o Home e o End, que a
    `tabela_de_linhas.TabelaDeLinhas` guarda da janela) continua na tabela, e o cartão mostra a
    linha sem tomar o foco (crítico da fase 5, ciclo 5: a primeira seta mandava o foco ao campo
    da verdade, e as seguintes ficavam nele).
    """
    return tabela.hasFocus() and QApplication.mouseButtons() == Qt.MouseButton.NoButton


def pixmap_de(rgb: np.ndarray) -> QPixmap:
    """A ``QPixmap`` from an ``(h, w, 3)`` uint8 array, copied so the array may go."""
    arr = np.ascontiguousarray(rgb)
    h, w, _ = arr.shape
    image = QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(image)


def leitura_em_html(
    words: Sequence[tuple[str, float]], threshold: float, fallback: str = ""
) -> str:
    """The engine's reading with the weak words in the letter colour of the trunk's text editor:
    `conferir` (`ATENCAO`) under the threshold, `revisar` (`PROBLEMA_TEXTO`) when far under."""
    if not words:
        return fallback.replace("&", "&amp;").replace("<", "&lt;")
    html: list[str] = []
    for text, confidence in words:
        texto = text.replace("&", "&amp;").replace("<", "&lt;")
        if confidence >= threshold:
            html.append(texto)
        elif confidence < threshold * RED_SHARE:
            html.append(f'<span style="color:{pele.cor("cartao_palavra_revisar")}">{texto}</span>')
        else:
            html.append(f'<span style="color:{pele.cor("cartao_palavra_conferir")}">{texto}</span>')
    return " ".join(html)


class CartaoDaLinha(QWidget):
    """Recorte · contexto · leitura · alternativas · motivo · verdade · paleta."""

    aceitar = pyqtSignal()  # Enter
    gravar = pyqtSignal()  # Ctrl+Enter
    rejeitar = pyqtSignal()  # Ctrl+R
    andar = pyqtSignal(int)  # Ctrl+↓ (+1) / Ctrl+↑ (−1)
    alternativa_pedida = pyqtSignal(int)  # Alt+1 / Alt+2 / duplo clique

    def __init__(self, parent: QWidget | None = None, *, vazio: str = "") -> None:
        super().__init__(parent)
        self.mensagem_vazia = vazio
        self._alternativas: list[tuple[str, str]] = []
        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(0, 0, 0, 0)
        self.recorte = QLabel(vazio, self)
        self.recorte.setStyleSheet(f"background:{pele.cor('cartao_fundo_do_recorte')}; padding:2px;")
        # C18 (crítico da fase 5): o convite «Abra um PDF e importe…» sem quebra de linha, e a
        # imagem do recorte, pediam a largura inteira deles -- o cartão ficava com 466 px dentro de
        # uma rolagem de 293. O texto quebra linha; a imagem é escalada para a largura que houver.
        self.recorte.setWordWrap(True)
        self.recorte.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.recorte.setMinimumHeight(CROP_HEIGHT_PX + 8)
        self.recorte.setMaximumHeight(CROP_HEIGHT_PX + 8)
        self.recorte.setAccessibleName("Recorte da linha atual")
        coluna.addWidget(self.recorte)
        # C18: a linha de contexto pedia 1.056 px de largura mínima; elidida, com o todo na dica.
        self.contexto = RotuloQueEncolhe("", self)
        self.contexto.setStyleSheet(f"color:{pele.cor('cartao_contexto')};")
        coluna.addWidget(self.contexto)
        coluna.addWidget(RotuloQueEncolhe("Leitura do motor (palavras fracas em destaque):", self))
        self.leitura = QTextEdit(self)
        self.leitura.setReadOnly(True)
        self.leitura.setMaximumHeight(48)
        self.leitura.setAccessibleName("Leitura do motor")
        coluna.addWidget(self.leitura)
        self.alternativas = QListWidget(self)
        self.alternativas.setMaximumHeight(52)
        self.alternativas.setAccessibleName("Leituras alternativas")
        self.alternativas.itemDoubleClicked.connect(
            lambda _i: self.alternativa_pedida.emit(max(0, self.alternativas.currentRow()))
        )
        coluna.addWidget(self.alternativas)
        self.motivo = QLabel("", self)
        self.motivo.setStyleSheet(f"color:{pele.cor('cartao_motivo')};")
        self.motivo.setWordWrap(True)
        coluna.addWidget(self.motivo)
        coluna.addWidget(
            RotuloQueEncolhe("Verdade (Enter aceita · Ctrl+Enter grava a edição · Ctrl+R rejeita):", self)
        )
        self.verdade = QPlainTextEdit(self)
        self.verdade.setMaximumHeight(60)
        self.verdade.setAccessibleName("Verdade da linha")
        # O Tab sai do campo (crítico da fase 5, ciclo 4): com a tecla, ele escrevia tabulações
        # na verdade da linha e as figurinas e as ações nunca eram alcançadas. A verdade é uma
        # linha de texto; tabulação não tem lugar nela.
        self.verdade.setTabChangesFocus(True)
        self.verdade.installEventFilter(self)
        coluna.addWidget(self.verdade)
        # Fluida (C18, crítico da fase 5): numa `QHBoxLayout` as sete teclas somavam a largura
        # mínima do cartão, e a 1248x640 «Letras → figurinas» ficava com 0 px à vista.
        paleta = FileiraFluida(self)
        paleta.adicionar(QLabel("Figurinas:", self))
        for key, glyph in FIGURINE_KEYS.items():
            b = QPushButton(glyph, self)
            b.setToolTip(f"Alt+{key.upper()}")
            # A screen reader has no letters in ♔: the name says the piece.
            b.setAccessibleName(f"Figurina {NOME_DA_PECA[glyph]} (Alt+{key.upper()})")
            b.setFixedWidth(34)
            b.clicked.connect(lambda _c=False, g=glyph: self.inserir_figurina(g))
            paleta.adicionar(b)
        conv = QPushButton("Letras → figurinas", self)
        conv.clicked.connect(lambda _c=False: self.letras_para_figurinas())
        paleta.adicionar(conv)
        coluna.addWidget(paleta)

    # -- showing ------------------------------------------------------------ #

    def limpar(self, mensagem: str | None = None) -> None:
        self.recorte.setPixmap(QPixmap())
        self.recorte.setText(self.mensagem_vazia if mensagem is None else mensagem)
        self.contexto.setText("")
        self.leitura.clear()
        self.alternativas.clear()
        self._alternativas = []
        self.motivo.setText("")
        self.verdade.clear()

    def mostrar_recorte(self, rgb: np.ndarray) -> None:
        """The crop scaled to the card: at most ``CROP_MAX_ZOOM``×, ``CROP_HEIGHT_PX`` high."""
        pixmap = pixmap_de(rgb)
        # The label's real width once laid out; 300 before the first layout (width 0 or the
        # default 100) -- a floor of 300 on a laid-out label drew past a 293 px card (C18).
        largura = self.recorte.width()
        avail = largura - 8 if largura > CROP_LAID_OUT_MIN else 300
        ratio = min(
            avail / max(1, pixmap.width()), CROP_HEIGHT_PX / max(1, pixmap.height()), CROP_MAX_ZOOM
        )
        self.recorte.setText("")
        self.recorte.setPixmap(
            pixmap.scaled(
                max(1, int(pixmap.width() * ratio)),
                max(1, int(pixmap.height() * ratio)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def mostrar_leitura(
        self, words: Sequence[tuple[str, float]], threshold: float, fallback: str = ""
    ) -> None:
        self.leitura.setHtml(leitura_em_html(words, threshold, fallback))

    def mostrar_alternativas(self, alternativas: Sequence[tuple[str, str]]) -> None:
        self.alternativas.clear()
        self._alternativas = list(alternativas)
        for source, text in self._alternativas:
            self.alternativas.addItem(f"{source}: {text}")
        if not self._alternativas:
            self.alternativas.addItem("(nenhum candidato leu esta linha de outro jeito)")

    def alternativa(self, index: int) -> str | None:
        """The text of alternative ``index``, or ``None`` past the end."""
        if 0 <= index < len(self._alternativas):
            return self._alternativas[index][1]
        return None

    def mostrar_verdade(self, texto: str, *, focar: bool = True) -> None:
        """Põe ``texto`` no campo da verdade e, com ``focar``, o foco nele.

        Quem escolhe a linha com o mouse, ou a acabou de decidir, escreve em seguida; quem anda
        pelas linhas da tabela com as setas continua na tabela (``focar=False``).
        """
        self.verdade.setPlainText(texto)
        if focar:
            self.verdade.setFocus()
        self.verdade.moveCursor(QTextCursor.MoveOperation.End)

    def texto_da_verdade(self) -> str:
        return self.verdade.toPlainText()

    # -- typing -------------------------------------------------------------- #

    def inserir_figurina(self, glyph: str) -> None:
        self.verdade.insertPlainText(glyph)
        self.verdade.setFocus()

    def letras_para_figurinas(self) -> None:
        text = self.verdade.toPlainText()
        converted = letters_to_figurines(text)
        if converted != text:
            self.verdade.setPlainText(converted)
        self.verdade.setFocus()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802, PLR0911 - Qt name; one return per key
        """The truth field's keys: Enter decides, Ctrl+R rejects, Alt+n copies, Alt+k types ♔."""
        if obj is self.verdade and event.type() == QEvent.Type.KeyPress:
            tecla, mods = event.key(), event.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            alt = bool(mods & Qt.KeyboardModifier.AltModifier)
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                (self.gravar if ctrl else self.aceitar).emit()
                return True
            if ctrl and tecla == Qt.Key.Key_R:
                self.rejeitar.emit()
                return True
            if ctrl and tecla == Qt.Key.Key_Down:
                self.andar.emit(1)
                return True
            if ctrl and tecla == Qt.Key.Key_Up:
                self.andar.emit(-1)
                return True
            if alt and tecla in (Qt.Key.Key_1, Qt.Key.Key_2):
                self.alternativa_pedida.emit(tecla - Qt.Key.Key_1)
                return True
            if alt:
                letra = event.text().lower() or QKeySequence(tecla).toString().lower()
                if letra in FIGURINE_KEYS:
                    self.inserir_figurina(FIGURINE_KEYS[letra])
                    return True
        return super().eventFilter(obj, event)
