"""A label that never decides how wide the window or its tab must be — OCR_UI_ROADMAP_C2 passo C18.

A plain ``QLabel`` asks for the width of its whole text as its minimum.  On a status line
that text is the variable part of the screen: measured with the labelling project open, the
Rotulagem status line (``87 linhas · 0 pendentes (0 duvidosas) · …``) asked for **2.868 px**
and the review card's context line (``linha 0 · região 0 (paragraph) · conf. 0.96 · …``) for
1.056 — wider than the whole window, so the tab's content was cut at the right edge instead
of shrinking.  The trunk solved it for the book name (``qt.rotulo.RotuloElidido``, F9-C2);
this is the suite's version, with one difference the suite's tests need: ``text()`` keeps
the **whole** text (the views and their tests read it back), and only the painting is
elided.  The whole text is also the tooltip, where it costs no pixel.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPainter, QPaintEvent
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget

__all__ = ["RotuloQueEncolhe"]


class RotuloQueEncolhe(QLabel):
    """A ``QLabel`` whose minimum width is zero and whose text is painted elided when it does
    not fit.  ``text()`` is the whole text; ``setText`` also sets the tooltip.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None, *,
                 modo: Qt.TextElideMode = Qt.TextElideMode.ElideRight) -> None:
        super().__init__(parent)
        self._modo = modo
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, a0: str | None) -> None:  # noqa: N802 - assinatura do Qt
        texto = a0 or ""
        super().setText(texto)
        self.setToolTip(texto)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - assinatura do Qt
        """Zero de largura: é a linha que tira o texto da conta do leiaute."""
        return QSize(0, super().minimumSizeHint().height())

    def elided(self) -> str:
        """What is painted at the current width."""
        largura = max(0, self.contentsRect().width())
        return self.fontMetrics().elidedText(self.text(), self._modo, largura)

    def paintEvent(self, a0: QPaintEvent | None) -> None:  # noqa: N802 - assinatura do Qt
        if self.fontMetrics().horizontalAdvance(self.text()) <= self.contentsRect().width():
            super().paintEvent(a0)
            return
        painter = QPainter(self)
        try:
            self.style().drawItemText(
                painter, self.contentsRect(), int(self.alignment()), self.palette(),
                self.isEnabled(), self.elided(), self.foregroundRole())
        finally:
            painter.end()
