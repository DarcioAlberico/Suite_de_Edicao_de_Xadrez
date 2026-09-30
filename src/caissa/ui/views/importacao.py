"""A importação do livro como tarefa da janela (OCR_UI_ROADMAP passo 17, R3.5).

Progresso por página, cancelável, parcial aproveitável.

**O mesmo desenho do exportador** (:class:`caissa.ui.views.exportacao.ExportadorDeLivro`):
``estado`` fala pela linha de status, ``progresso`` alimenta uma barra determinada,
``controles`` tranca quem o montou, ``terminou`` entrega o
:class:`~caissa.ingest.pdf.importer.ImportResult` -- inteiro ou **parcial**. A diferença que
importa é a última: a importação corre com ``keep_partial=True``, então cancelar não descarta
nada; o que já foi montado volta como documento, e o relatório diz ``canceled``. É esse
documento que o trilho pinta e que *Exportar* grava, sem reimportar.

``pagina_montada`` sai a cada página construída, com o índice dela: o trilho acende a miniatura
enquanto a importação anda, em vez de esperar o fim.
"""

from __future__ import annotations

import functools
import itertools
import logging
import threading
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from caissa.ingest.pdf import PdfImportOptions, import_pdf
from caissa.ingest.pdf.importer import ImportResult

logger = logging.getLogger(__name__)

def _nome_seguro(nome: str) -> str:
    """Uma subpasta por livro: dois livros com as mesmas páginas não partilham ``p31-0001.png``."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in nome)[:80] or "livro"


@functools.lru_cache(maxsize=1)
def _pasta_de_recursos() -> Path:
    """One temporary folder per process for the images the window's import extracts.

    Kept until the process ends (``atexit``): the export of the same book reuses the
    document in memory and needs the files to still be there.
    """
    import atexit
    import shutil
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="caissa-importacao-"))
    atexit.register(shutil.rmtree, pasta, True)
    return pasta


_IMPORTACOES = itertools.count(1)


def pasta_da_importacao(pdf_path: Path) -> Path:
    """A folder of its own for **this** import's images (OCR_UI ciclo 2, A13).

    One folder per book was not enough: importing the same book again while an export
    of the previous result was still reading its images overwrote them under the same
    names (critic of phase 1, item 5).  Every import gets ``<livro>-<n>``; the previous
    folder stays until the process ends, so the document that points at it stays whole.
    """
    return _pasta_de_recursos() / f"{_nome_seguro(pdf_path.stem)}-{next(_IMPORTACOES)}"

__all__ = ["ImportadorDoLivro"]


class ImportadorDoLivro(QObject):
    """Roda ``import_pdf`` numa thread, página a página, e guarda o resultado para o trilho."""

    estado = pyqtSignal(str)
    progresso = pyqtSignal(int, int)
    pagina_montada = pyqtSignal(int)
    controles = pyqtSignal(bool)
    terminou = pyqtSignal(object)
    """O :class:`ImportResult`, inteiro ou parcial (``result.report.canceled``)."""

    _acabou = pyqtSignal(object)
    _falhou = pyqtSignal(str)
    _avancou = pyqtSignal(int, int)

    def __init__(self, pai: QWidget | None) -> None:
        super().__init__(pai)
        self._pai = pai
        self._cancelar: threading.Event | None = None
        self._motivo_do_cancelamento = ""
        self._rodando = False
        self._indices: tuple[int, ...] = ()
        self._montadas = 0
        self.resultado: ImportResult | None = None
        """A última importação que terminou (inteira ou parcial). ``None`` antes da primeira."""
        self.pdf_path: Path | None = None
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
        paginas: tuple[int, ...] | None = None,
        enable_ocr: bool = True,
    ) -> bool:
        """Começa a importar. ``False`` se não havia PDF ou já rodava."""
        if pdf_path is None:
            self.estado.emit("Abra um PDF antes de importar o livro.")
            return False
        if self._rodando:
            self.estado.emit("Já existe uma importação em execução.")
            return False
        self._indices = tuple(paginas) if paginas is not None else tuple(range(page_count))
        self._montadas = 0
        self._rodando = True
        self._cancelar = threading.Event()
        self.pdf_path = Path(pdf_path)
        self.controles.emit(False)
        self.estado.emit(f"Importando {self.pdf_path.name} ({len(self._indices)} página(s))…")
        threading.Thread(
            target=self._trabalho,
            args=(self.pdf_path, self._indices, enable_ocr, self._cancelar),
            daemon=True,
        ).start()
        return True

    def cancelar(self, *, motivo: str = "") -> None:
        """Pede o cancelamento.  ``motivo="troca_de_livro"`` (A13) diz que o resultado vai ser
        descartado por quem chamou: o rodapé não promete exportar o que já foi lido."""
        if self._cancelar is None:
            return
        self._motivo_do_cancelamento = motivo
        self._cancelar.set()
        if motivo == "troca_de_livro":
            return
        self.estado.emit("Cancelando a importação… o que já foi lido fica.")

    def _trabalho(
        self,
        pdf_path: Path,
        indices: tuple[int, ...],
        enable_ocr: bool,
        cancelar: threading.Event,
    ) -> None:
        try:
            from caissa.ocr.review import ReviewDecisions

            resultado = import_pdf(
                pdf_path,
                PdfImportOptions(
                    pages=indices,
                    enable_ocr=enable_ocr,
                    progress=lambda feito, total: self._avancou.emit(feito, total),
                    should_cancel=cancelar.is_set,
                    keep_partial=True,
                    review_decisions=ReviewDecisions.for_pdf(pdf_path),
                    # The images of the pages go to a folder of this process, so the
                    # document can be exported as it is (passo A3) instead of read again;
                    # without it every image resource would have ``path=None`` and the
                    # EPUB would silently drop them.
                    asset_dir=pasta_da_importacao(pdf_path),
                ),
            )
        except Exception as exc:  # a thread não pode derrubar a janela
            logger.exception("A importação de %s falhou.", pdf_path)
            self._falhou.emit(str(exc))
            return
        self._acabou.emit(resultado)

    def _mostrar_progresso(self, feito: int, total: int) -> None:
        self.progresso.emit(feito, total)
        metade = total // 2
        if feito <= metade:
            self.estado.emit(f"Importando… lendo a camada de texto ({feito}/{metade}).")
            return
        # A segunda metade é a montagem, uma página por passo (ver `PdfImporter._build`).
        montadas = feito - metade
        while self._montadas < montadas and self._montadas < len(self._indices):
            self.pagina_montada.emit(self._indices[self._montadas])
            self._montadas += 1
        self.estado.emit(f"Importando… montando as páginas ({montadas}/{metade}).")

    def _concluiu(self, resultado: Any) -> None:
        self._encerrar()
        if not isinstance(resultado, ImportResult):  # pragma: no cover - o sinal é object
            return
        self.resultado = resultado
        relatorio = resultado.report
        motivo, self._motivo_do_cancelamento = self._motivo_do_cancelamento, ""
        if relatorio.canceled and motivo == "troca_de_livro":
            # A13: quem trocou de livro vai descartar este resultado e dizê-lo -- prometer
            # «podem ser exportadas» aqui era a segunda das duas frases contraditórias.
            pass
        elif relatorio.canceled:
            self.estado.emit(
                f"Importação cancelada: {relatorio.pages_built} de {relatorio.pages_planned} "
                "página(s) ficaram lidas e podem ser exportadas."
            )
        else:
            self.estado.emit(f"Importação concluída. {relatorio.describe_pt()}")
        self.terminou.emit(resultado)

    def _deu_errado(self, detalhe: str) -> None:
        self._encerrar()
        self.estado.emit("Falha na importação do livro.")
        QMessageBox.critical(
            self._pai, "Importar livro", f"Não foi possível importar o livro:\n{detalhe}"
        )

    def _encerrar(self) -> None:
        self._rodando = False
        self._cancelar = None
        self.controles.emit(True)
