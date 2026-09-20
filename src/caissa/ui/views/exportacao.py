"""*Exportar livro…* — o PDF aberto vira EPUB ou DOCX, inteiro ou por intervalo de páginas.

Duas peças, e nenhuma decide nada: :class:`DialogoDeExportacao` pergunta **o formato, o
alcance e o destino**; :class:`ExportadorDeLivro` roda :func:`caissa.export.book.export_book`
numa thread e devolve o resultado na thread da interface por sinais Qt. O que é regra —
como se lê ``"10-25"``, que nome o arquivo ganha, o que a importação e a gravação
relatam — mora em :mod:`caissa.export.book`, sem toolkit, e é o mesmo que a linha de
comando ``caissa-exportar`` usa.

O diálogo conta páginas **de 1**, como a janela do produto e como um leitor conta: o
``page_index`` interno da aba Rotulagem é zero-based e a conversão é feita aqui, uma vez,
ao preencher o campo *de* com a página que está na tela.

**Termina no rodapé, e não numa caixa que precisa de clique.** Um livro de 400 páginas com
OCR é justamente o que se deixa rodando enquanto se faz outra coisa; o sinal ``estado``
leva a frase para quem o montou (a linha de status da aba, o rodapé do tronco), e uma
caixa só aparece quando a exportação **falha** — porque aí há uma decisão a tomar.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from caissa.export.book import (
    BOOK_FORMATS,
    BookExportResult,
    PageRangeError,
    default_output_path,
    describe_pages,
    export_book,
    parse_page_range,
)
from caissa.ingest.pdf import ImportCanceled

logger = logging.getLogger(__name__)

__all__ = ["DialogoDeExportacao", "EscolhaDeExportacao", "ExportadorDeLivro"]

ROTULO = {"epub": "EPUB (leitores, reflow)", "docx": "DOCX (Word, editável)"}
FILTRO = {"epub": "EPUB (*.epub)", "docx": "Word (*.docx)"}


class EscolhaDeExportacao:
    """O que o diálogo respondeu: formato, índices zero-based, destino e OCR."""

    __slots__ = ("destino", "formato", "ocr", "page_count", "paginas")

    def __init__(
        self,
        formato: str,
        paginas: tuple[int, ...],
        destino: Path,
        *,
        page_count: int,
        ocr: bool,
    ) -> None:
        self.formato = formato
        self.paginas = paginas
        self.destino = destino
        self.page_count = page_count
        self.ocr = ocr

    @property
    def alcance(self) -> str:
        """``"livro completo"`` ou o intervalo contado de 1, para o rodapé."""
        return describe_pages(self.paginas, self.page_count)


class DialogoDeExportacao(QDialog):
    """Formato, *livro completo* ou *de … até …* (ou uma lista livre), destino, OCR.

    Args:
        parent: A janela que o abre.
        pdf_path: O livro aberto.
        page_count: Quantas páginas ele tem; limita os dois contadores.
        formato: Qual botão de formato começa marcado.
        pagina_atual: Índice zero-based da página na tela; vira o *de* do intervalo.
    """

    def __init__(
        self,
        parent: QWidget | None,
        pdf_path: Path,
        page_count: int,
        *,
        formato: str = "epub",
        pagina_atual: int = 0,
    ) -> None:
        super().__init__(parent)
        self.pdf_path = Path(pdf_path)
        self.page_count = max(1, int(page_count))
        self._destino_editado = False
        self.setWindowTitle("Exportar livro")
        self.setModal(True)
        self._montar(formato, pagina_atual)

    # -- layout ------------------------------------------------------------- #

    def _montar(self, formato: str, pagina_atual: int) -> None:
        raiz = QVBoxLayout(self)
        raiz.addWidget(QLabel(f"<b>{self.pdf_path.name}</b> · {self.page_count} página(s)", self))

        raiz.addWidget(QLabel("Formato", self))
        self.formatos = QButtonGroup(self)
        linha = QHBoxLayout()
        raiz.addLayout(linha)
        self.botao_formato: dict[str, QRadioButton] = {}
        for nome in BOOK_FORMATS:
            botao = QRadioButton(ROTULO[nome], self)
            botao.setAccessibleName(f"Formato {nome.upper()}")
            self.formatos.addButton(botao)
            self.botao_formato[nome] = botao
            linha.addWidget(botao)
        self.botao_formato[formato if formato in BOOK_FORMATS else "epub"].setChecked(True)
        self.formatos.buttonToggled.connect(lambda _b, _on: self._sugerir_destino())

        raiz.addWidget(QLabel("Páginas", self))
        grade = QGridLayout()
        raiz.addLayout(grade)
        self.alcance = QButtonGroup(self)
        self.completo = QRadioButton("Livro completo", self)
        self.completo.setAccessibleName("Livro completo")
        self.intervalo = QRadioButton("Intervalo: de", self)
        self.intervalo.setAccessibleName("Intervalo de páginas")
        self.lista = QRadioButton("Lista:", self)
        self.lista.setAccessibleName("Lista de páginas")
        for botao in (self.completo, self.intervalo, self.lista):
            self.alcance.addButton(botao)
        grade.addWidget(self.completo, 0, 0, 1, 4)
        grade.addWidget(self.intervalo, 1, 0)
        self.de = QSpinBox(self)
        self.de.setAccessibleName("Primeira página")
        self.de.setRange(1, self.page_count)
        self.de.setFixedWidth(90)
        self.de.setValue(min(self.page_count, max(1, pagina_atual + 1)))
        grade.addWidget(self.de, 1, 1)
        grade.addWidget(QLabel("até", self), 1, 2)
        self.ate = QSpinBox(self)
        self.ate.setAccessibleName("Última página")
        self.ate.setRange(1, self.page_count)
        self.ate.setFixedWidth(90)
        self.ate.setValue(self.page_count)
        grade.addWidget(self.ate, 1, 3)
        grade.setColumnStretch(4, 1)
        grade.addWidget(self.lista, 2, 0)
        self.lista_edit = QLineEdit(self)
        self.lista_edit.setAccessibleName("Páginas em lista")
        self.lista_edit.setPlaceholderText("ex.: 1-3, 7, 40-")
        grade.addWidget(self.lista_edit, 2, 1, 1, 3)
        self.completo.setChecked(True)
        # Mexer num contador é escolher o intervalo; digitar na lista é escolher a lista.
        self.de.valueChanged.connect(lambda _v: self._escolheu(self.intervalo))
        self.ate.valueChanged.connect(lambda _v: self._escolheu(self.intervalo))
        self.lista_edit.textEdited.connect(lambda _t: self._escolheu(self.lista))
        self.alcance.buttonToggled.connect(lambda _b, _on: self._sugerir_destino())

        raiz.addWidget(QLabel("Arquivo de saída", self))
        linha = QHBoxLayout()
        raiz.addLayout(linha)
        self.destino = QLineEdit(self)
        self.destino.setAccessibleName("Arquivo de saída")
        self.destino.setMinimumWidth(420)
        self.destino.textEdited.connect(self._destino_foi_editado)
        linha.addWidget(self.destino, 1)
        escolher = QPushButton("Escolher…", self)
        escolher.clicked.connect(lambda _c=False: self.escolher_destino())
        linha.addWidget(escolher)

        self.ocr = QCheckBox("Reconhecer com OCR as páginas sem camada de texto (mais lento)", self)
        self.ocr.setAccessibleName("Usar OCR")
        self.ocr.setChecked(True)
        raiz.addWidget(self.ocr)

        self.aviso = QLabel("", self)
        self.aviso.setStyleSheet("color:#b91c1c;")
        self.aviso.setWordWrap(True)
        raiz.addWidget(self.aviso)

        # «Exportar» é botão feito à mão, e não um Ok renomeado: o tronco retraduz todo botão
        # padrão ao mostrar o diálogo (F9-C14, `qt/acessibilidade.py`) e «Exportar» virava «OK».
        # O botão à mão sobrevive à varredura -- é o mesmo contrato do «Varrer» de lá.
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.botao_exportar = botoes.addButton("Exportar", QDialogButtonBox.ButtonRole.AcceptRole)
        self.botao_exportar.setDefault(True)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        raiz.addWidget(botoes)
        self._sugerir_destino()

    # -- reading the form --------------------------------------------------- #

    @property
    def formato(self) -> str:
        for nome, botao in self.botao_formato.items():
            if botao.isChecked():
                return nome
        return "epub"

    def paginas(self) -> tuple[int, ...]:
        """Os índices zero-based escolhidos.

        Raises:
            PageRangeError: A lista não se lê, ou o intervalo termina antes de começar.
        """
        if self.completo.isChecked():
            return tuple(range(self.page_count))
        if self.intervalo.isChecked():
            texto = f"{self.de.value()}-{self.ate.value()}"
        else:
            texto = self.lista_edit.text()
            if not texto.strip():
                raise PageRangeError("Digite as páginas da lista, ou escolha «Livro completo».")
        return parse_page_range(texto, self.page_count)

    def escolha(self) -> EscolhaDeExportacao:
        """A resposta do diálogo, validada. Chame depois de ``accept``."""
        return EscolhaDeExportacao(
            self.formato,
            self.paginas(),
            Path(self.destino.text().strip()),
            page_count=self.page_count,
            ocr=self.ocr.isChecked(),
        )

    def accept(self) -> None:
        try:
            self.paginas()
        except PageRangeError as exc:
            self.aviso.setText(str(exc))
            return
        destino = self.destino.text().strip()
        if not destino:
            self.aviso.setText("Diga onde gravar o arquivo.")
            return
        caminho = Path(destino)
        if caminho.suffix.lower() != f".{self.formato}":
            caminho = caminho.with_suffix(f".{self.formato}")
            self.destino.setText(str(caminho))
        if caminho.exists() and not self._confirmar_sobrescrever(caminho):
            return
        self.aviso.setText("")
        super().accept()

    def _confirmar_sobrescrever(self, caminho: Path) -> bool:
        resposta = QMessageBox.question(
            self,
            "Exportar livro",
            f"{caminho.name} já existe. Substituir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return resposta == QMessageBox.StandardButton.Yes

    # -- helpers ------------------------------------------------------------ #

    def _escolheu(self, botao: QRadioButton) -> None:
        if not botao.isChecked():
            botao.setChecked(True)
        else:
            self._sugerir_destino()

    def _destino_foi_editado(self, _texto: str) -> None:
        self._destino_editado = True

    def _sugerir_destino(self) -> None:
        """O nome padrão segue formato e alcance até a pessoa escrever um nome dela."""
        if self._destino_editado:
            return
        try:
            indices: tuple[int, ...] | None = self.paginas()
        except PageRangeError:
            indices = None
        sugestao = default_output_path(self.pdf_path, self.formato, indices, self.page_count)
        self.destino.setText(str(sugestao))

    def escolher_destino(self) -> None:
        atual = self.destino.text().strip() or str(
            default_output_path(self.pdf_path, self.formato, None, self.page_count)
        )
        nome, _f = QFileDialog.getSaveFileName(
            self, "Exportar livro", atual, f"{FILTRO[self.formato]};;Todos (*.*)"
        )
        if nome:
            self._destino_editado = True
            self.destino.setText(nome)


class ExportadorDeLivro(QObject):
    """Abre o diálogo, roda a exportação numa thread e fala pelo ``estado``.

    O mesmo desenho do ``Exportador`` de PGN do tronco: ``estado`` é uma frase para a
    linha de status, ``progresso`` alimenta uma barra determinada, ``controles`` tranca e
    destranca quem o montou, e ``terminou`` entrega o
    :class:`~caissa.export.book.BookExportResult` a quem quiser mais do que a frase.
    """

    estado = pyqtSignal(str)
    progresso = pyqtSignal(int, int)
    controles = pyqtSignal(bool)
    terminou = pyqtSignal(object)

    _acabou = pyqtSignal(object)
    _falhou = pyqtSignal(str)
    _avancou = pyqtSignal(str, int, int)

    def __init__(self, pai: QWidget | None) -> None:
        super().__init__(pai)
        self._pai = pai
        self._cancelar: threading.Event | None = None
        self._documento: Any = None
        self._rodando = False
        self._acabou.connect(self._concluiu)
        self._falhou.connect(self._deu_errado)
        self._avancou.connect(self._mostrar_progresso)

    @property
    def rodando(self) -> bool:
        return self._rodando

    def comecar(
        self,
        pdf_path: Path | None,
        page_count: int,
        *,
        formato: str = "epub",
        pagina_atual: int = 0,
        documento_para: Callable[[Sequence[int] | None], Any] | None = None,
    ) -> bool:
        """Pergunta e começa. ``False`` se não havia PDF, já rodava, ou a pessoa desistiu.

        ``documento_para(paginas)`` (A3) devolve o ``ImportResult`` que o trilho já tem
        quando cobre as páginas pedidas -- a exportação reaproveita-o em vez de reimportar
        (minutos de OCR) -- ou ``None``, e aí importa como sempre.
        """
        if pdf_path is None:
            self.estado.emit("Abra um PDF antes de exportar o livro.")
            return False
        if self._rodando:
            self.estado.emit("Já existe uma exportação de livro em execução.")
            return False
        dialogo = DialogoDeExportacao(
            self._pai, pdf_path, page_count, formato=formato, pagina_atual=pagina_atual
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return False
        escolha = dialogo.escolha()
        self.iniciar(pdf_path, escolha, documento_para=documento_para)
        return True

    def iniciar(
        self,
        pdf_path: Path,
        escolha: EscolhaDeExportacao,
        *,
        documento_para: Callable[[Sequence[int] | None], Any] | None = None,
    ) -> None:
        """Começa sem perguntar — para quem já tem a escolha (testes, macros)."""
        documento = None
        if documento_para is not None:
            try:
                documento = documento_para(escolha.paginas)
            except Exception as exc:  # noqa: BLE001 - um trilho sem importação não impede exportar
                # Dito no rodapé e no log, nunca engolido: a exportação segue, mas
                # reimportando o livro -- minutos de OCR que o trilho já tinha pago.
                logger.exception("documento_para falhou; a exportação reimporta o livro.")
                self.estado.emit(
                    f"A importação já feita não pôde ser reaproveitada ({exc}); o livro será "
                    "importado de novo para exportar."
                )
                documento = None
        self._documento = documento
        self._rodando = True
        self._cancelar = threading.Event()
        self.controles.emit(False)
        self.estado.emit(
            f"Exportando {pdf_path.name} para {escolha.formato.upper()} ({escolha.alcance})…"
        )
        threading.Thread(
            target=self._trabalho, args=(pdf_path, escolha, self._cancelar), daemon=True
        ).start()

    def cancelar(self) -> None:
        if self._cancelar is None:
            return
        self._cancelar.set()
        self.estado.emit("Cancelando a exportação… responde entre uma página e outra.")

    def _trabalho(
        self, pdf_path: Path, escolha: EscolhaDeExportacao, cancelar: threading.Event
    ) -> None:
        try:
            resultado = export_book(
                pdf_path,
                escolha.destino,
                escolha.formato,
                pages=escolha.paginas,
                enable_ocr=escolha.ocr,
                document=self._documento,
                progress=lambda fase, feito, total: self._avancou.emit(fase, feito, total),
                should_cancel=cancelar.is_set,
            )
        except ImportCanceled as exc:
            self._falhou.emit(f"cancelada: {exc}")
            return
        except Exception as exc:
            self._falhou.emit(str(exc))
            return
        if self._documento is not None and getattr(resultado, "import_report", None) is not getattr(
            self._documento, "report", None
        ):
            # `export_book` recusou o documento em mãos (páginas diferentes das pedidas, ou
            # imagens fora do disco) e importou de novo -- dito, não só no log.
            self.estado.emit(
                "A importação já feita não serviu a esta exportação (páginas ou imagens "
                "diferentes): o livro foi importado de novo."
            )
        self._acabou.emit(resultado)

    def _mostrar_progresso(self, fase: str, feito: int, total: int) -> None:
        self.progresso.emit(feito, total)
        if fase == "importando":
            self.estado.emit(f"Exportando… lendo o PDF ({feito}/{total}).")
        elif feito < total:
            self.estado.emit("Exportando… gravando o arquivo.")

    def _concluiu(self, resultado: Any) -> None:
        self._encerrar()
        if not isinstance(resultado, BookExportResult):  # pragma: no cover - the sinal é object
            return
        self.estado.emit(f"Exportação concluída. {resultado.summary()}")
        self.terminou.emit(resultado)

    def _deu_errado(self, detalhe: str) -> None:
        self._encerrar()
        if detalhe.startswith("cancelada:"):
            self.estado.emit("Exportação cancelada; nada foi gravado.")
            return
        self.estado.emit("Falha na exportação do livro.")
        QMessageBox.critical(
            self._pai, "Exportar livro", f"Não foi possível exportar o livro:\n{detalhe}"
        )

    def _encerrar(self) -> None:
        self._rodando = False
        self._cancelar = None
        self.controles.emit(True)
