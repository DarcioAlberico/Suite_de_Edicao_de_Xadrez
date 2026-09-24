r"""A sonda de UI Automation do passo H2: o leitor de tela lê o editor de código?

Pela UI Automation do Windows (o que o Narrador e o NVDA usam), a sonda lê o `TextPattern` do
editor depois de pôr o cursor em 50 posições sorteadas: a seleção degenerada (o cursor), o
caractere sob ele e a linha dele; numa posição em cinco, uma seleção de verdade. A posição conta
quando as três leituras (quatro, com a seleção) são o texto certo. **O portão: 50/50.**

Dois processos, porque a UIA é um cliente de fora:
- o **editor** (`--papel editor`, o Python da suíte com o PyQt6 do `.venv-pack`) abre o protótipo
  numa janela de verdade — a plataforma `offscreen` não fala UIA —, sem roubar o foco, e obedece
  ao stdin: `mover <posição>`, `selecionar <início> <fim>`, `sair`; responde `ok` depois que o Qt
  assenta;
- a **sonda** (o Python do `.venv-medicao`, o único com o `pywinauto`; o produto não o leva) acha
  a janela pelo PID, acha o elemento com `TextPattern` e confere cada leitura com o texto.

**Sabotagem** `--sabotar uia_mudo`: o editor mostra um `QWidget` que só **pinta** o texto; sem a
interface de texto não há `TextPattern`, e a sonda marca 0/50 — prova que ela lê pela interface de
texto, e não por acaso.

Uso::

    & .venv-medicao\Scripts\python.exe benchmarks\editor_uia.py `
        --saida benchmarks\reports\editor\h2\uia
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
POSICOES = 50
SEMENTE = 42
TITULO = "Caissa H2 - sonda UIA"
SABOTAGENS = ("uia_mudo",)
#: Os valores de `TextUnit` da UIA (UIAutomationClient.h).
UNIDADE_CARACTERE = 0
UNIDADE_LINHA = 3
#: `UIA_IsTextPatternAvailablePropertyId`.
TEM_TEXTPATTERN = 30040


def capitulo() -> str:
    """Um capítulo XHTML sintético e determinístico, com acentos e figurinas.

    Só o plano básico do Unicode: a posição do Qt conta unidades UTF-16, e a do Python, caracteres.
    """
    sorteio = random.Random(SEMENTE)
    palavras = ("lance", "peão", "torre", "diagonal", "coluna", "xeque", "ação", "defesa",
                "♘f3", "♗b5", "Dvoretsky", "final", "posição", "tempo", "é", "à")
    linhas = ['<?xml version="1.0" encoding="utf-8"?>',
              '<html xmlns="http://www.w3.org/1999/xhtml">', "<head>", "<title>Sonda</title>",
              "</head>", "<body>", "<section>"]
    for numero in range(120):
        frase = " ".join(sorteio.choice(palavras) for _ in range(sorteio.randint(3, 14)))
        linhas.append(f'<p class="cb-move" id="p{numero}">{frase}</p>')
    linhas += ["</section>", "</body>", "</html>"]
    return "\n".join(linhas) + "\n"


def sortear_posicoes(texto: str, quantas: int = POSICOES) -> list[int]:
    """Posições dentro das linhas (nunca num fim de linha: ali o «caractere» é o separador)."""
    candidatas = [i for i, c in enumerate(texto) if c != "\n"]
    return sorted(random.Random(SEMENTE).sample(candidatas, quantas))


def esperado(texto: str, posicao: int, fim: int | None = None) -> dict[str, str]:
    inicio_da_linha = texto.rfind("\n", 0, posicao) + 1
    fim_da_linha = texto.find("\n", posicao)
    lido = {"caractere": texto[posicao], "linha": texto[inicio_da_linha:fim_da_linha]}
    if fim is not None:
        lido["selecao"] = texto[posicao:fim]
    return lido


# --------------------------------------------------------------------------- #
# O editor (Python da suíte + PyQt6 do .venv-pack)
# --------------------------------------------------------------------------- #


def papel_editor(sabotagem: str | None) -> int:
    if str(RAIZ / "src") not in sys.path:
        sys.path.insert(0, str(RAIZ / "src"))
    from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QPainter, QTextCursor
    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication(sys.argv)
    texto = capitulo()

    class Pintor(QWidget):
        """A sabotagem: o texto só pintado, sem interface de texto para a acessibilidade."""

        def paintEvent(self, _evento: object) -> None:  # noqa: N802 - assinatura do Qt
            pintor = QPainter(self)
            altura = self.fontMetrics().height()
            for numero, linha in enumerate(texto.splitlines()[:60]):
                pintor.drawText(4, (numero + 1) * altura, linha)
            pintor.end()

    editor: Any = None
    if sabotagem == "uia_mudo":
        janela: QWidget = Pintor()
    else:
        from caissa.ui.widgets.editor_de_codigo import montar

        editor = montar(texto, tipo="xhtml", classes_do_projeto=("cb-move",),
                        com_previa=False).editor
        janela = editor
    janela.setWindowTitle(TITULO)
    # Sem roubar o foco nem a vista de quem usa a máquina: a UIA lê a janela fora da tela.
    janela.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    janela.setWindowFlag(Qt.WindowType.Tool)
    janela.resize(900, 640)
    janela.move(-4000, 0)
    janela.show()

    class Leitor(QObject):
        comando = pyqtSignal(str)

    leitor = Leitor()

    def responder() -> None:
        print("ok", flush=True)

    def executar(linha: str) -> None:
        partes = linha.split()
        if not partes or partes[0] == "sair":
            app.quit()
            return
        if editor is not None:
            cursor = editor.textCursor()
            cursor.setPosition(int(partes[1]))
            if partes[0] == "selecionar":
                cursor.setPosition(int(partes[2]), QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
            editor.ensureCursorVisible()
        QTimer.singleShot(30, responder)

    leitor.comando.connect(executar)

    def ler_o_stdin() -> None:
        for linha in sys.stdin:
            leitor.comando.emit(linha.strip())
        leitor.comando.emit("sair")

    def anunciar() -> None:
        if editor is not None and editor.carregando:
            QTimer.singleShot(20, anunciar)
            return
        print(f"pronto {os.getpid()}", flush=True)
        threading.Thread(target=ler_o_stdin, daemon=True).start()

    QTimer.singleShot(0, anunciar)
    return app.exec()


# --------------------------------------------------------------------------- #
# A sonda (Python do .venv-medicao, com o pywinauto)
# --------------------------------------------------------------------------- #


def _principal() -> Path:
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def _no_checkout(relativo: str) -> Path:
    for base in (RAIZ, _principal()):
        if (base / relativo).exists():
            return base / relativo
    return RAIZ / relativo


def abrir_o_editor(sabotagem: str | None) -> tuple[subprocess.Popen[str], int]:
    ambiente = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    ambiente["PYTHONPATH"] = os.pathsep.join(
        [str(RAIZ / "src"), str(_no_checkout(".venv-pack/Lib/site-packages"))])
    ambiente["PYTHONIOENCODING"] = "utf-8"
    comando = [str(_no_checkout(".venv/Scripts/python.exe")), str(Path(__file__).resolve()),
               "--papel", "editor"]
    if sabotagem:
        comando += ["--sabotar", sabotagem]
    filho = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE,  # noqa: S603
                             text=True, encoding="utf-8", env=ambiente, cwd=RAIZ)
    assert filho.stdout is not None
    limite = time.monotonic() + 60
    while time.monotonic() < limite:
        linha = filho.stdout.readline()
        if not linha:
            break
        if linha.startswith("pronto "):
            return filho, int(linha.split()[1])
    filho.kill()
    raise RuntimeError("o editor não anunciou «pronto» em 60 s")


def pedir(filho: subprocess.Popen[str], comando: str) -> None:
    assert filho.stdin is not None
    assert filho.stdout is not None
    filho.stdin.write(comando + "\n")
    filho.stdin.flush()
    while True:
        linha = filho.stdout.readline()
        if not linha:
            raise RuntimeError(f"o editor saiu no meio de «{comando}»")
        if linha.strip() == "ok":
            return


def achar_o_texto(pid: int) -> tuple[Any, Any]:
    """A janela do editor e o primeiro elemento dela com `TextPattern` (ou `None`)."""
    from pywinauto import Desktop

    # A janela pelo processo: o nome UIA dela é o nome acessível do editor, não o título.
    janela = Desktop(backend="uia").window(process=pid)
    janela.wait("exists", timeout=30)
    embrulho = janela.wrapper_object()
    for elemento in [embrulho, *embrulho.descendants()]:
        bruto = elemento.element_info.element
        if bruto.GetCurrentPropertyValue(TEM_TEXTPATTERN):
            return embrulho, elemento
    return embrulho, None


def ler(elemento: Any) -> dict[str, str]:
    """O cursor pela UIA: a seleção, o caractere sob ela e a linha dela."""
    from pywinauto.uia_defines import get_elem_interface

    padrao = get_elem_interface(elemento.element_info.element, "Text")
    faixa = padrao.GetSelection().GetElement(0)
    caractere = faixa.Clone()
    caractere.ExpandToEnclosingUnit(UNIDADE_CARACTERE)
    linha = faixa.Clone()
    linha.ExpandToEnclosingUnit(UNIDADE_LINHA)
    return {"selecao": faixa.GetText(-1), "caractere": caractere.GetText(-1),
            "linha": linha.GetText(-1).rstrip("\r\n  ")}


def sondar(sabotagem: str | None) -> dict[str, Any]:
    texto = capitulo()
    posicoes = sortear_posicoes(texto)
    filho, pid = abrir_o_editor(sabotagem)
    erros: list[dict[str, Any]] = []
    acertos = 0
    try:
        janela, elemento = achar_o_texto(pid)
        if elemento is None:
            return {"acertos": 0, "posicoes": len(posicoes), "janela": janela.element_info.name,
                    "motivo": "nenhum elemento com TextPattern", "erros": []}
        for indice, posicao in enumerate(posicoes):
            fim = None
            if indice % 5 == 4:
                fim_da_linha = texto.find("\n", posicao)
                fim = min(fim_da_linha, posicao + 1 + indice % 9)
                pedir(filho, f"selecionar {posicao} {fim}")
            else:
                pedir(filho, f"mover {posicao}")
            lido = ler(elemento)
            certo = esperado(texto, posicao, fim)
            if fim is None:
                lido_sem_selecao = {k: lido[k] for k in ("caractere", "linha")}
                bateu = lido_sem_selecao == certo and lido["selecao"] == ""
            else:
                # Com seleção, o «caractere» é o primeiro dela.
                bateu = lido == certo
            if bateu:
                acertos += 1
            elif len(erros) < 10:
                erros.append({"posicao": posicao, "fim": fim, "lido": lido, "certo": certo})
        return {"acertos": acertos, "posicoes": len(posicoes),
                "janela": janela.element_info.name,
                "elemento": elemento.element_info.control_type, "erros": erros}
    finally:
        encerrar(filho)


def encerrar(filho: subprocess.Popen[str]) -> None:
    try:
        assert filho.stdin is not None
        filho.stdin.write("sair\n")
        filho.stdin.close()
    except OSError:
        pass
    try:
        filho.wait(timeout=10)
    except subprocess.TimeoutExpired:
        filho.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--papel", choices=("sonda", "editor"), default="sonda")
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    args = parser.parse_args(argv)
    if args.papel == "editor":
        return papel_editor(args.sabotar)
    resultado = sondar(args.sabotar)
    resultado["sabotagem"] = args.sabotar
    if args.saida is not None:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "uia.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    placar = f"{resultado['acertos']}/{resultado['posicoes']}"
    if resultado["acertos"] == resultado["posicoes"]:
        print(f"PASSOU: a UIA leu certo em {placar} posições ({resultado.get('elemento')})")
        return 0
    motivo = resultado.get("motivo") or f"primeiro erro: {resultado['erros'][:1]}"
    print(f"REPROVADO: a UIA leu certo em {placar} posições -- {motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
