"""O mínimo da janela: o menor tamanho em que ela aceita ficar — OCR_UI_ROADMAP_C2 passo C18.

A fase 4 mediu **1248×695** lógicos pela recusa de `capture --escala`; esta fase remediu com o
rodapé e as áreas **visitadas** — o caso real de quem trabalha — e achou **1538×659**: a barra de
anotação sob o visor (combo + três botões numa `QHBoxLayout`, 810 px na pele Foco), a frase do
rodapé num `QLabel` comum (1.246 px com um livro aberto) e rótulos de estado das abas da suíte
que pediam a largura do texto inteiro (2.868 px). Nenhum desses é desenho: é texto decidindo a
tela em que o programa cabe.

**A régua** (`TETO`): a área útil de um portátil 1920×1080 a 150 % — a configuração de fábrica
mais comum de um 14" — é 1280×720 lógicos menos a barra de tarefas (48) e a barra de título
(31): **1280×641**; e 1366×768 a 100 % dá 1366×728 menos o título. O teto é 1250×640, com a
borda da janela dentro. A 125 % sobre 1366×768 (1093×582) o número é **dito**, não exigido:
os pisos declarados das duas colunas (abas 540, visor 520) já somam mais que isso, e mudá-los é
desenho (crítico C3).

O que o arnês faz, por pele e **num processo por pele** (a razão é a de `capture`): monta a
janela, abre o livro quando há um, mostra cada área de trabalho uma vez (é o que acende o painel
da Rotulagem com o projeto e as linhas de estado longas), escreve no rodapé uma frase de
`FRASE_LONGA` caracteres e lê `minimumSizeHint()`. Os «motores» — os widgets-folha que pedem mais
largura ou altura — vão para o JSON, para o próximo a mexer saber onde olhar.

**Sabotagem** (`--sabotar rodape`): a frase do rodapé volta a um `QLabel` comum antes de a
janela nascer; o mínimo sobe com a frase e o portão reprova.

    PYTHONPATH=src;..\\ChessVisionOFF_Puro\\src;.venv-pack\\Lib\\site-packages QT_QPA_PLATFORM=offscreen ^
        .venv\\Scripts\\python.exe -m caissa.ui.audit.minimo --saida benchmarks\\reports\\ui\\c2_fase5\\minimo [--pdf X]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ui.audit.capture import PELES, TRONCO, _preparar

TETO: tuple[int, int] = (1250, 640)
"""Largura e altura lógicas máximas do mínimo da janela. Ver a docstring do módulo."""

FRASE_LONGA = 300
"""Caracteres da frase escrita no rodapé: mais longa que qualquer frase real medida (a maior
dos relatórios da fase 4 tem ~180), para que o portão não dependa de qual frase apareceu."""

SABOTAGENS = ("", "rodape")


def _frase() -> str:
    base = ("A importação de 1937 Kemeri.pdf terminou depois de o livro mudar e foi descartada; "
            "as páginas lidas continuam no cache e podem ser exportadas quando o livro voltar. ")
    return (base * 4)[:FRASE_LONGA]


def _sabotar_o_rodape() -> None:
    """O rodapé de antes do C18: a frase num `QLabel` comum, que pede o texto inteiro."""
    from chess_diagram_ocr.qt import rodape
    from PyQt6.QtWidgets import QLabel

    class RotuloComum(QLabel):
        def __init__(self, texto: str = "", parent: Any = None, **_kw: Any) -> None:
            super().__init__(texto, parent)

        def definir_texto(self, texto: str) -> None:
            self.setText(texto)

        @property
        def texto_inteiro(self) -> str:
            return self.text()

    rodape.RotuloElidido = RotuloComum  # type: ignore[attr-defined]


def _motores(janela: Any, limite_w: int, limite_h: int) -> list[dict[str, Any]]:
    """As folhas que pedem ao menos `limite_*` e nenhum filho que peça tanto."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QAbstractButton, QLabel, QWidget

    def minimo(widget: QWidget) -> tuple[int, int]:
        dica = widget.minimumSizeHint()
        return max(dica.width(), widget.minimumWidth()), max(dica.height(), widget.minimumHeight())

    saida = []
    for widget in janela.findChildren(QWidget):
        if not widget.isVisible():
            continue
        largura, altura = minimo(widget)
        filhos = widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
        filho_largo = any(minimo(f)[0] >= limite_w for f in filhos if f.isVisible())
        filho_alto = any(minimo(f)[1] >= limite_h for f in filhos if f.isVisible())
        if (largura >= limite_w and not filho_largo) or (altura >= limite_h and not filho_alto):
            cadeia, pai = [], widget
            while pai is not None and pai is not janela:
                cadeia.append(type(pai).__name__)
                pai = pai.parentWidget()
            texto = widget.text()[:80] if isinstance(widget, (QLabel, QAbstractButton)) else ""
            saida.append({"minimo": [largura, altura], "cadeia": " < ".join(cadeia[:6]), "texto": texto})
    return sorted(saida, key=lambda m: (-m["minimo"][0], -m["minimo"][1]))[:12]


def medir_uma_pele(nome_da_pele: str, *, pdf: Path | None, sabotar: str,
                   caminho_do_tronco: Path = TRONCO) -> dict[str, Any]:
    """Uma pele, neste processo: o mínimo da janela com as áreas visitadas e a frase longa."""
    _preparar(caminho_do_tronco)
    os.environ["CVOFF_SKIN"] = nome_da_pele
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit.capture import (
        aguardar_a_folha,
        areas_de_trabalho,
        estado_de_medicao,
        impor_a_fonte_do_produto,
    )

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    impor_a_fonte_do_produto(aplicacao)
    if sabotar == "rodape":
        _sabotar_o_rodape()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal

    # **A janela não é desmontada aqui.** Visitar a área do Dataset dispara a leitura do
    # `labels.csv` numa tarefa ao fundo; fechar e sair do interpretador com ela viva derruba o
    # processo no C++ (medido nesta fase, `access violation` no `close`). Quem chama grava o
    # JSON e sai por `os._exit` -- o produto fecha pelo `closeEvent`, que espera; o arnês não
    # precisa fechar para medir.
    pasta = Path(tempfile.mkdtemp(prefix="caissa_minimo_"))
    janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(pasta))
    janela.show()
    for _ in range(5):
        aplicacao.processEvents()
    if pdf is not None and pdf.exists():
        janela.abrir_pdf(pdf)
        aguardar_a_folha(janela)
    areas = [area.nome for area in areas_de_trabalho(janela)]
    for area in areas_de_trabalho(janela):
        area.mostrar()
        for _ in range(3):
            aplicacao.processEvents()
    janela.rodape.mostrar(_frase())
    janela.resize(400, 300)
    for _ in range(6):
        aplicacao.processEvents()
    dica = janela.minimumSizeHint()
    medida = {
        "pele": nome_da_pele,
        "pdf": str(pdf) if pdf else "",
        "sabotagem": sabotar,
        "areas_visitadas": areas,
        "frase_no_rodape": len(_frase()),
        "minimo": [dica.width(), dica.height()],
        "ficou": [janela.width(), janela.height()],
        "motores": _motores(janela, 600, 380),
    }
    medida["cabe"] = medida["minimo"][0] <= TETO[0] and medida["minimo"][1] <= TETO[1]
    return medida


def medir(saida: Path, *, pdf: Path | None = None, sabotar: str = "",
          caminho_do_tronco: Path = TRONCO, peles: tuple[tuple[str, str], ...] = PELES) -> dict[str, Any]:
    """Todas as peles, um subprocesso por pele; grava e devolve o relatório."""
    saida.mkdir(parents=True, exist_ok=True)
    medidas: list[dict[str, Any]] = []
    for nome, _rotulo in peles:
        alvo = saida / f"_minimo_{nome}.json"
        argumentos = [sys.executable, "-m", "caissa.ui.audit.minimo", "--pele", nome,
                      "--json-da-pele", str(alvo), "--tronco", str(caminho_do_tronco)]
        if pdf is not None:
            argumentos += ["--pdf", str(pdf)]
        if sabotar:
            argumentos += ["--sabotar", sabotar]
        subprocess.run(argumentos, env=dict(os.environ), check=False)  # noqa: S603 - argv nosso
        if not alvo.exists():
            raise RuntimeError(f"a pele {nome!r} não mediu: o subprocesso morreu antes de gravar {alvo}")
        medidas.append(json.loads(alvo.read_text(encoding="utf-8")))
        alvo.unlink()
    relatorio = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "teto": list(TETO),
        "sabotagem": sabotar,
        "medidas": medidas,
        "passou": all(m["cabe"] for m in medidas),
    }
    marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    nome = f"minimo{'_sabotado_' + sabotar if sabotar else ''}_{marca}.json"
    (saida / nome).write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    return relatorio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--saida", type=Path, default=Path("benchmarks/reports/ui/c2_fase5/minimo"))
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--sabotar", default="", choices=SABOTAGENS)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--pele", default="", help="(interno) mede só esta pele, neste processo")
    parser.add_argument("--json-da-pele", type=Path, default=None, help="(interno)")
    args = parser.parse_args(argv)
    if args.pele:
        medida = medir_uma_pele(args.pele, pdf=args.pdf, sabotar=args.sabotar, caminho_do_tronco=args.tronco)
        destino = args.json_da_pele or Path(f"_minimo_{args.pele}.json")
        destino.write_text(json.dumps(medida, indent=2, ensure_ascii=False), encoding="utf-8")
        sys.stdout.flush()
        # O filho do processo de trabalho do tronco (o `spawn` que rasteriza e lê o CSV) não
        # morre com o pai no Windows: sair por `os._exit` sem encerrá-lo deixou seis órfãos
        # vivos nesta fase, e um deles segurava a medição seguinte. Encerra-se, esperando o que
        # estiver em curso, e só então sai-se sem desmontar a janela.
        try:
            from chess_diagram_ocr.processo_de_trabalho import processo_de_trabalho

            processo_de_trabalho().encerrar(esperar=True)
        except Exception:  # noqa: BLE001 - a medida já foi gravada; sair é o que resta
            pass
        os._exit(0)   # ver `medir_uma_pele`: a janela fica montada até o processo acabar
    relatorio = medir(args.saida, pdf=args.pdf, sabotar=args.sabotar, caminho_do_tronco=args.tronco)
    for medida in relatorio["medidas"]:
        largura, altura = medida["minimo"]
        print(f"  {medida['pele']:<10} mínimo {largura}×{altura} "
              f"({'cabe' if medida['cabe'] else 'NÃO cabe'} em {TETO[0]}×{TETO[1]})")
        for motor in medida["motores"][:4]:
            print(f"      {motor['minimo'][0]}×{motor['minimo'][1]}  {motor['cadeia']}  {motor['texto']!r}")
    print("PASSOU" if relatorio["passou"] else "REPROVOU")
    return 0 if relatorio["passou"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
