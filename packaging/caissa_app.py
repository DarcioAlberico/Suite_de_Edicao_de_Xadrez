"""Ponto de entrada da janela empacotada do Caissa Studio (F12).

Por que existe uma casca em vez de empacotar `app_pyqt.py` direto
-----------------------------------------------------------------
A janela do produto **e** a do tronco: a ADR-0009 escolheu PyQt6 justamente porque ~19.600
linhas de interface ja existem la, e a F9 mantem a disciplina `ui/` (decide) contra `qt/`
(pinta). Empacotar `app_pyqt.py` como script de entrada funcionaria. O que ele nao faria e
o que este arquivo faz antes de a janela subir:

1. **Falar quando falta um peso.** Um `.exe` com `console=False` que nao acha o checkpoint
   fecha sem dizer nada -- e o sintoma que o `--selftest` do tronco foi criado para
   diagnosticar, so que depois. Aqui o programa abre uma caixa de dialogo em pt-BR,
   nomeia o que falta e o comando que resolve.
2. **Levar o assistente de primeira execucao junto.** `Caissa.exe --primeira-execucao`
   chama o mesmo codigo que `CaissaPrimeiraExecucao.exe`, para quem tiver apagado o atalho.
3. **Deixar `caissa` importavel de dentro da janela.** No bundle os dois pacotes -- o do
   tronco e o da suite -- moram no mesmo arquivo compilado, e nao ha `sys.path` para
   arrumar; num checkout, ha, e o ajuste esta aqui em vez de espalhado.

O que este arquivo **nao** faz e reimplementar nada da janela. Ele importa `app_pyqt` e
chama `main()`. Se um dia a F9 entregar uma janela propria em `src/caissa/ui/`, o unico
lugar que muda e a funcao `_principal_do_tronco`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = ["APRESENTACAO", "main", "preparar_caminhos"]

APRESENTACAO = "Caissa Studio"

CODIGO_DE_ERRO_NAO_TRATADO = 7
"""Sete, e nao 1: os codigos de 1 a 6 sao do `--selftest` do tronco e cada um nomeia uma
causa. "Uma excecao escapou" e uma sexta resposta diferente das outras, e colapsa-la em 1
diria "a pagina nao foi reconhecida" para um erro que nem chegou a olhar a pagina."""

_TRONCO_PADRAO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
"""Onde o frontend mora num checkout. Absoluto, e pelo mesmo motivo que em
`tests/unit/ui/conftest.py`: o tronco e um repositorio vizinho e nao um pacote instalado.
Congelado isto nao e usado -- os modulos ja estao dentro do bundle."""


def preparar_caminhos() -> None:
    """Num checkout, poe o `src/` do tronco e o da suite no caminho. Congelado, nao faz nada."""
    if getattr(sys, "frozen", False):
        return
    aqui = Path(__file__).resolve().parent
    candidatos = [
        aqui.parent / "src",
        _TRONCO_PADRAO / "src",
        _TRONCO_PADRAO,
    ]
    for caminho in candidatos:
        if caminho.is_dir() and str(caminho) not in sys.path:
            sys.path.insert(0, str(caminho))


def _faltam_obrigatorios() -> list[str]:
    """Nomes dos componentes obrigatorios que nao estao instalados. Lista vazia = tudo la."""
    try:
        import caissa_modelos as mod
    except ImportError:
        return []
    try:
        manifesto = mod.carregar_manifesto()
    except (OSError, ValueError):
        return []
    return [c.titulo for c in manifesto.obrigatorios if not mod.verificar(c)]


def _avisar_e_oferecer(faltando: list[str]) -> bool:
    """Caixa de dialogo em pt-BR. Devolve `True` se o usuario pediu o assistente.

    Sem PyQt6 nao ha caixa, e a mensagem vai para o stderr -- que num `.exe` sem console
    ninguem le, e por isso o retorno e `False` e o programa segue: melhor uma janela que
    abre com menos do que um processo que morre sem rastro.
    """
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        sys.stderr.write("Faltam componentes: " + ", ".join(faltando) + "\n")
        return False

    app = QApplication.instance() or QApplication(sys.argv[:1])
    caixa = QMessageBox()
    caixa.setIcon(QMessageBox.Icon.Warning)
    caixa.setWindowTitle(APRESENTACAO)
    caixa.setText("Faltam arquivos que nao vem dentro do instalador.")
    caixa.setInformativeText(
        "Nao esta instalado:\n  - "
        + "\n  - ".join(faltando)
        + "\n\nEles ficam fora do instalador de proposito, para ele caber abaixo de "
        "150 MB (SPEC secao 12).\n\nO assistente de primeira execucao instala e confere "
        "cada um pelo SHA-256. Abrir agora?"
    )
    caixa.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    caixa.setDefaultButton(QMessageBox.StandardButton.Yes)
    caixa.button(QMessageBox.StandardButton.Yes).setText("Abrir o assistente")
    caixa.button(QMessageBox.StandardButton.No).setText("Abrir assim mesmo")
    escolha = caixa.exec()
    del app  # a janela real monta a sua propria QApplication
    return escolha == QMessageBox.StandardButton.Yes


def _principal_do_tronco() -> None:
    """Chama a janela. Unico ponto que sabe qual modulo e a janela do produto."""
    import app_pyqt

    app_pyqt.main()


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do executavel."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    preparar_caminhos()

    if "--primeira-execucao" in argumentos:
        argumentos.remove("--primeira-execucao")
        import caissa_primeira_execucao as assistente

        return assistente.main(argumentos)

    if not os.environ.get("CAISSA_SEM_CHECAGEM"):
        faltando = _faltam_obrigatorios()
        if faltando and _avisar_e_oferecer(faltando):
            import caissa_primeira_execucao as assistente

            return assistente.main(["--pausar"])

    sys.argv = [sys.argv[0], *argumentos]
    try:
        _principal_do_tronco()
    except SystemExit as saida:  # `app_pyqt.main` sai por SystemExit no `--selftest`
        return int(saida.code or 0)
    except BaseException as exc:  # noqa: BLE001 - ver o bloco abaixo; e deliberado
        # **Por que engolir tudo aqui, e por que isto nao e "esconder o erro".**
        #
        # `Caissa.exe` e `console=False`. Quando uma excecao escapa de um `.exe` empacotado
        # sem console, o PyInstaller abre uma **caixa de dialogo modal** com o traceback e
        # espera alguem clicar. Medido: o auto-teste do bundle, chamado pelo assistente sem
        # ninguem olhando, ficou **7 minutos e 10 segundos** parado nessa caixa e so terminou
        # porque o tempo limite o matou -- e o relatorio disse "nao terminou", que e a coisa
        # menos util que ele podia dizer sobre um `RuntimeError` perfeitamente diagnostico.
        #
        # O erro nao some: ele vai para o log, ao lado do executavel, com traceback inteiro.
        # O que some e a caixa que trava a maquina de quem instalou.
        import logging
        import traceback

        logging.getLogger("caissa").critical(
            "O programa parou antes de terminar:\n%s", traceback.format_exc()
        )
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        return CODIGO_DE_ERRO_NAO_TRATADO
    return 0


if __name__ == "__main__":
    import multiprocessing

    # Sem isto, cada `Process` filho reexecuta o `.exe` inteiro e abre outra janela --
    # o modo de falha classico do PyInstaller no Windows, que o tronco ja documenta.
    multiprocessing.freeze_support()
    raise SystemExit(main())
