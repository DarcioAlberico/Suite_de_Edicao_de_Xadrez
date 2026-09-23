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

**Caber não basta: o que cabe tem de estar à vista** (crítico da fase 5). A primeira versão lia só
`minimumSizeHint`, e passou com a janela escondendo conteúdo: dentro das rolagens novas, sem barra
horizontal, a barra de ações do Resultado e os botões da Revisão de texto ficavam com 0 px à vista,
e a mensagem do rodapé com 0 px ao lado de um nome de livro de 149 caracteres. Agora, no mínimo da
janela e em 1366×728, em **toda área**: nenhum controle (botão, rótulo com texto, campo, lista de
escolha) fora da vista **sem uma barra de rolagem que leve a ele**, nenhum controle espremido abaixo
do próprio mínimo (o Qt espreme quando a área é menor que o leiaute), e o rodapé medido **com a
linha cheia** -- a frase longa, uma importação em curso com a ocupação e a barra, os dispositivos
da queda para a CPU, e na zona do documento o nome mais longo do acervo e um comum (`NOMES`): as
**quatro zonas** à vista -- a mensagem com ao menos `MENSAGEM_LEGIVEL` px, o documento com ao
menos `DOCUMENTO_LEGIVEL`, os dispositivos e a ocupação inteiros -- e nenhum botão espremido. A
linha cheia é posta pelo arnês, e não esperada da importação do livro: o portão com o livro achou
o botão das mensagens com 27 de 82 px enquanto a barra estava na linha, e uma medida que
dependesse de a importação ainda estar correndo naquele instante não seria uma medida. E as zonas
de dispositivos e de ocupação entraram na conta depois que o crítico (ciclo 2) as achou com 0 px
-- a reserva de 480 px da mensagem saía delas, e o portão, que só olhava a mensagem e o
documento, passava. E a linha medida é a do arnês (crítico, ciclo 3): a visita às áreas acende
trabalho do próprio produto, que reescreve as zonas depois de o arnês enchê-las; o arnês a põe de
novo, mede quando ela assenta e grava quantas vezes precisou -- e o JSON grava o commit e o que o
`src` de cada repositório tem fora dele.

**Sabotagens:** `--sabotar rodape` (a frase num `QLabel` comum: o mínimo sobe), `--sabotar corte`
(toda rolagem sem barra horizontal, como no ciclo 1: sobra conteúdo sem caminho até ele),
`--sabotar mensagem` (a mensagem sem largura garantida: some ao lado do nome longo),
`--sabotar aperto` (o botão das mensagens com o piso de um pixel de antes: espremido na linha
cheia), `--sabotar reserva` (o rodapé do ciclo 2: 480 px reservados à mensagem e as zonas curtas
sem mínimo -- os dispositivos e a ocupação cortados) e `--sabotar linha` (o produto reescrevendo a
zona dos dispositivos a cada volta do laço de eventos: nenhuma medida sai na linha do arnês, e as
duas passadas, a da vista e a do rodapé, têm de dizê-lo).

    PYTHONPATH=src;..\\ChessVisionOFF_Puro\\src;.venv-pack\\Lib\\site-packages ^
    QT_QPA_PLATFORM=offscreen .venv\\Scripts\\python.exe -m caissa.ui.audit.minimo ^
        --saida benchmarks\\reports\\ui\\c2_fase5\\minimo [--pdf X] [--sabotar S]
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

SABOTAGENS = ("", "rodape", "corte", "mensagem", "aperto", "reserva", "linha")

MENSAGEM_LEGIVEL = 320
"""Pixels lógicos da mensagem do rodapé que têm de estar à vista, no mínimo da janela e com o nome
longo: ~57 caracteres na fonte do produto (5,6 px cada, medido pelo crítico da fase 5, ciclo 3) --
o começo de qualquer frase de erro. Uma frase mais longa sai elidida no meio, com o todo na dica:
a do produto sem o modelo de casas (84 caracteres, 474 px) sai assim até 1440 px de largura."""

NOME_LONGO = ("Gaprindashvili, Paata - Imagination in Chess. How To Think Creatively And Avoid "
              "Foolish Mistakes (Bastford, 2005) 2p 145p_OCR_Aprimorar_Aprimorar.pdf · "
              "p. 1 de 289 · nenhum diagrama nesta página")
"""A zona do documento com o nome mais longo do acervo (149 caracteres): o caso do crítico."""

NOME_COMUM = ("Karpov A - Chess Combinations -World Champions-2 (2011).pdf · p. 268 de 305 · "
              "nenhum diagrama nesta página")
"""...e com um nome comum do acervo (58 caracteres), o outro caso que o crítico pediu."""

NOMES = (NOME_LONGO, NOME_COMUM)

DOCUMENTO_LEGIVEL = 120
"""Pixels lógicos da zona do documento que têm de estar à vista com a linha cheia: ~18
caracteres, elididos no meio -- o começo do nome e o fim da frase (a página e os diagramas)."""

TAMANHOS = ((1366, 728),)
"""Além do mínimo da janela: um portátil 1366×768 a 100 %, menos o título."""

APERTO_TOLERADO = 0.9
"""Um controle é **espremido** abaixo desta fração do próprio mínimo: o mínimo de um botão tem o
acolchoamento dentro (8–16 px), e 40 de 42 px come a borda, não o texto; 57 de 107 é meia
palavra."""

VISIVEL_MINIMO = 2
"""Pixels abaixo dos quais um controle não conta **quando o mínimo dele também fica aí**: um
separador, um rótulo elidido sem espaço. Um botão de 82 px de mínimo com 1 px na tela não é
nenhum dos dois -- é o pior aperto, e conta (a sabotagem `aperto` o mostrou escapando por aqui
quando a régua olhava só a largura)."""

CADEIA = 4
"""Quantos pais a descrição de um controle nomeia: o bastante para achar o painel."""

VOLTAS_MINIMAS = 6
"""Voltas do laço de eventos antes de medir o rodapé: as da primeira versão do arnês."""

VOLTAS_MAXIMAS = 200
"""...e no máximo estas, esperando a linha do arnês assentar: se o produto a reescrever o tempo
todo, a medida sai marcada fora da linha do arnês, e não passa."""

_VIVOS: list[Any] = []
"""A aplicação e a janela medidas, presas aqui até o `os._exit`. Variáveis locais não bastavam: ao
sair de `medir_uma_pele` o Python soltava a `QApplication` que ela criou, o PyQt a desmontava com a
leitura do `labels.csv` do Dataset ainda correndo numa tarefa, e a pele morria em `access
violation` antes de gravar o JSON. Medido nesta fase com `PYTHONFAULTHANDLER`: quatro peles mortas
em dez corridas com a máquina ocupada (o `bench_sol` e a população do B14 ao lado), as quatro no
retorno de `medir_uma_pele` e com a tarefa do Dataset esperando o processo de trabalho; prender só
a janela não bastou (a quarta) -- a leitura só perde a corrida quando demora."""


def _estado_do_git(pasta: Path) -> dict[str, Any]:
    """O commit de ``pasta`` e o que o ``src`` dela tem fora dele (``git status --porcelain``)."""

    def git(*argumentos: str) -> str:
        feito = subprocess.run(  # noqa: S603 - argv nosso
            ["git", "-C", str(pasta), *argumentos],  # noqa: S607 - o git do PATH
            capture_output=True, text=True, encoding="utf-8", check=False)
        return feito.stdout.strip() if feito.returncode == 0 else ""

    return {"caminho": str(pasta), "commit": git("rev-parse", "HEAD"),
            "fora_do_commit": git("status", "--porcelain", "--", "src").splitlines()}


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

        def definir_piso(self, _piso: int) -> None:
            """Um `QLabel` comum já pede o texto inteiro: não há piso a pôr."""

        @property
        def texto_inteiro(self) -> str:
            return self.text()

    rodape.RotuloElidido = RotuloComum  # type: ignore[attr-defined]


def _sabotar_a_mensagem() -> None:
    """O rodapé do ciclo 1: a mensagem sem largura garantida, a primeira a encolher."""
    from chess_diagram_ocr.qt import rodape

    rodape.LARGURA_DA_MENSAGEM = 0  # type: ignore[attr-defined]


def _sabotar_a_reserva() -> None:
    """O rodapé do ciclo 2: 480 px reservados à mensagem, e as zonas curtas sem mínimo.

    No aperto o leiaute tirava dos dispositivos e da ocupação a mesma parte que do nome do livro.
    """
    from chess_diagram_ocr.qt import rodape

    rodape.LARGURA_DA_MENSAGEM = 480  # type: ignore[attr-defined]
    rodape.LARGURA_DA_ZONA = 0  # type: ignore[attr-defined]


def _sabotar_o_aperto(janela: Any) -> None:
    """O botão das mensagens com o piso de um pixel de antes: o primeiro a ceder na linha cheia."""
    janela.rodape._btn_mensagens.setMinimumWidth(1)   # a sabotagem é o defeito antigo


def _sabotar_o_corte(janela: Any) -> None:
    """As rolagens do ciclo 1: nenhuma barra horizontal, o que passa da largura fica sem caminho."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QScrollArea

    for rolagem in janela.findChildren(QScrollArea):
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


def _sabotar_a_linha(janela: Any) -> None:
    """O produto reescrevendo a zona dos dispositivos a cada volta do laço de eventos.

    É o caso da leitura do `labels.csv` e da detecção dos dispositivos, sem fim: o arnês repõe a
    linha dele e o produto a desfaz de novo, e nenhuma medida sai na linha do arnês.
    """
    from chess_diagram_ocr.ui.estado_do_rodape import Dispositivos
    from PyQt6.QtCore import QTimer

    relogio = QTimer(janela)
    relogio.setInterval(0)
    relogio.timeout.connect(lambda: janela.rodape.definir_dispositivos(Dispositivos()))
    relogio.start()


def _controles(janela: Any) -> list[Any]:
    """Os controles que alguém lê ou clica: botões, rótulos com texto, campos, escolhas."""
    from PyQt6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox, QLabel, QLineEdit

    saida = []
    tipos = (QAbstractButton, QLabel, QLineEdit, QComboBox, QAbstractSpinBox)
    for widget in janela.findChildren(tipos):
        if not widget.isVisible():
            continue
        dica = widget.minimumSizeHint()
        if (min(widget.width(), widget.height()) <= VISIVEL_MINIMO
                and min(dica.width(), dica.height()) <= VISIVEL_MINIMO):
            continue
        if isinstance(widget, QLabel) and not widget.text().strip():
            continue
        if (isinstance(widget, QAbstractButton)
                and not widget.text().strip() and widget.icon().isNull()):
            continue
        saida.append(widget)
    return saida


def _descricao(widget: Any, janela: Any) -> dict[str, Any]:
    texto = widget.text() if hasattr(widget, "text") and callable(widget.text) else ""
    cadeia, pai = [], widget.parentWidget()
    while pai is not None and pai is not janela and len(cadeia) < CADEIA:
        cadeia.append(type(pai).__name__)
        pai = pai.parentWidget()
    return {"tipo": type(widget).__name__, "texto": str(texto)[:40], "cadeia": " < ".join(cadeia),
            "largura": widget.width(), "minimo": widget.minimumSizeHint().width()}


def _fora_da_vista(widget: Any, janela: Any) -> tuple[bool, bool]:
    """(fora da vista, há barra que leve a ele).

    A barra conta quando é a de uma rolagem que contém o controle, na direção em que ele sai da
    vista dela.
    """
    from PyQt6.QtCore import QPoint, QRect
    from PyQt6.QtWidgets import QAbstractScrollArea

    visivel = widget.visibleRegion().boundingRect()
    if visivel.width() >= widget.width() - 1 and visivel.height() >= widget.height() - 1:
        return False, False
    pai = widget.parentWidget()
    while pai is not None and pai is not janela:
        dono = pai.parentWidget()
        if isinstance(dono, QAbstractScrollArea) and pai is dono.viewport():
            onde = QRect(widget.mapTo(pai, QPoint(0, 0)), widget.size())
            vista = pai.rect()
            fora_h = onde.left() < vista.left() or onde.right() > vista.right()
            fora_v = onde.top() < vista.top() or onde.bottom() > vista.bottom()
            if not fora_h and not fora_v:
                return True, False   # cortado por outro pai, dentro da vista da rolagem
            barra_h = not fora_h or dono.horizontalScrollBar().isVisible()
            barra_v = not fora_v or dono.verticalScrollBar().isVisible()
            return True, barra_h and barra_v
        pai = dono
    return True, False


def _vista(janela: Any, aplicacao: Any, areas: list[Any]) -> dict[str, Any]:
    """No tamanho em que a janela está: o que fica fora da vista sem barra, e o que é espremido."""
    from PyQt6.QtWidgets import QLabel

    sem_barra: list[dict[str, Any]] = []
    espremidos: list[dict[str, Any]] = []
    alcancaveis = 0
    repostas = 0
    fora_da_linha: list[str] = []
    for area in areas:
        area.mostrar()
        for _ in range(5):
            aplicacao.processEvents()
        # a linha do arnês, assentada, como na medida do rodapé (crítico da fase 5, ciclo 4: com
        # a máquina ocupada, esta passada mediu na Clássica, com o livro, a zona de dispositivos
        # com o texto que o próprio produto tinha escrito nela, «peças ainda …to desligado»,
        # espremida a 135 de 162 px)
        _, repostas_da_area, assentou = _assentar_a_linha(janela, aplicacao, NOME_LONGO)
        repostas += repostas_da_area
        if not assentou:
            fora_da_linha.append(area.nome)
        for widget in _controles(janela):
            fora, barra = _fora_da_vista(widget, janela)
            if fora and barra:
                alcancaveis += 1
            elif fora:
                sem_barra.append({"area": area.nome, **_descricao(widget, janela)})
            elif widget.width() < APERTO_TOLERADO * widget.minimumSizeHint().width() and not (
                    isinstance(widget, QLabel) and widget.wordWrap()):
                espremidos.append({"area": area.nome, **_descricao(widget, janela)})
    return {"tamanho": [janela.width(), janela.height()], "fora_sem_barra": sem_barra,
            "espremidos": espremidos, "alcancaveis_pela_barra": alcancaveis,
            "linha_reposta": repostas, "fora_da_linha_do_arnes": fora_da_linha}


def _linha_cheia(janela: Any, nome: str = NOME_LONGO) -> dict[str, str]:
    """O pior caso do rodapé, com ``nome`` na zona do documento; devolve o texto de cada zona.

    A frase longa, uma importação com a barra e os dispositivos da queda para a CPU.
    """
    from chess_diagram_ocr.ui.busy import BusyOperation
    from chess_diagram_ocr.ui.estado_do_rodape import Dispositivos

    janela.rodape.definir_documento(nome)
    janela.rodape.mostrar(_frase())
    janela.rodape.definir_dispositivos(Dispositivos(pecas="cpu", caracteres=None))
    janela.rodape.aplicar_ocupacao([BusyOperation(
        name="Importando o livro", loses_work=False, cancellable=True,
        detail="p. 12 de 289", feito=12, total=289)])
    return _textos_do_rodape(janela)


def _textos_do_rodape(janela: Any) -> dict[str, str]:
    rodape = janela.rodape
    # o arnês mede o que o rodapé desenha, e por isso lê os rótulos dele
    return {"mensagem": rodape._lbl_mensagem.texto_inteiro,
            "documento": rodape._lbl_documento.texto_inteiro,
            "dispositivos": rodape._lbl_dispositivos.texto_inteiro,
            "ocupacao": rodape._lbl_ocupacao.texto_inteiro}


def _assentar_a_linha(janela: Any, aplicacao: Any, nome: str) -> tuple[int, int, bool]:
    """Põe a linha cheia do arnês e espera ela assentar. Devolve `(voltas, repostas, assentou)`.

    Mede a linha do arnês (crítico da fase 5, ciclo 3: o primeiro nome saía às vezes com
    dispositivos 162 e ocupação 152). A visita às áreas acende trabalho do próprio produto -- a
    leitura do `labels.csv` do Dataset, a detecção dos dispositivos --, e ele reescreve as zonas
    depois de o arnês enchê-las: «leitura do dataset (labels.csv)» e «peças ainda não · texto
    desligado» eram as medidas. Quando o produto reescreve, o arnês põe a linha de novo (e
    conta); assenta quando duas voltas seguidas do laço de eventos dão as mesmas larguras com a
    linha dele. Servem a esta espera a medida do rodapé e, desde o ciclo 4 do crítico, a passada
    da vista.

    Só uma linha assentada conta como a do arnês. Até a sabotagem `linha` (ciclo 5), a resposta
    era se o texto das zonas, na saída do laço, era o do arnês -- e com o produto reescrevendo a
    zona sem parar a última volta repunha a linha e saía: a medida dizia «na linha do arnês» e o
    portão passava sem ela ter assentado nunca.
    """
    rodape = janela.rodape

    def larguras() -> tuple[int, ...]:
        zonas = (rodape._lbl_mensagem, rodape._lbl_documento, rodape._lbl_dispositivos,
                 rodape._lbl_ocupacao, rodape.barra_de_progresso())
        return tuple(z.visibleRegion().boundingRect().width() if z.isVisible() else 0
                     for z in zonas)

    esperado = _linha_cheia(janela, nome)
    antes, voltas, repostas = None, 0, 0
    while voltas < VOLTAS_MAXIMAS:
        aplicacao.processEvents()
        voltas += 1
        if _textos_do_rodape(janela) != esperado:
            esperado = _linha_cheia(janela, nome)
            repostas += 1
            antes = None
            continue
        agora = larguras()
        if voltas >= VOLTAS_MINIMAS and agora == antes:
            return voltas, repostas, True
        antes = agora
    return voltas, repostas, False


def _rodape(janela: Any, aplicacao: Any) -> dict[str, Any]:
    """As quatro zonas do rodapé com a linha cheia, para cada nome de `NOMES`.

    No tamanho em que a janela está.
    """
    from PyQt6.QtWidgets import QAbstractButton

    rodape = janela.rodape
    # o arnês mede o que o rodapé desenha, e por isso lê os rótulos dele
    zonas = {"mensagem": rodape._lbl_mensagem, "documento": rodape._lbl_documento,
             "dispositivos": rodape._lbl_dispositivos, "ocupacao": rodape._lbl_ocupacao}

    def a_vista(widget: Any) -> int:
        return widget.visibleRegion().boundingRect().width() if widget.isVisible() else 0

    nomes = []
    for nome in NOMES:
        voltas, repostas, assentou = _assentar_a_linha(janela, aplicacao, nome)
        medida: dict[str, Any] = {"nome": nome.split(" · ")[0][:60], "voltas": voltas,
                                  "linha_reposta": repostas, "linha_do_arnes": assentou}
        for zona, rotulo in zonas.items():
            medida[f"{zona}_px"] = a_vista(rotulo)
        medida["barra_px"] = a_vista(rodape.barra_de_progresso())
        # uma zona curta só vale inteira: elidida ou sem pixel nenhum, ela está cortada
        medida["cortadas"] = [zona for zona in ("dispositivos", "ocupacao")
                              if zonas[zona].texto_inteiro
                              and (medida[f"{zona}_px"] == 0
                                   or zonas[zona].text() != zonas[zona].texto_inteiro)]
        medida["espremidos"] = [
            _descricao(botao, janela) for botao in rodape.findChildren(QAbstractButton)
            if botao.isVisible()
            and botao.width() < APERTO_TOLERADO * botao.minimumSizeHint().width()]
        nomes.append(medida)
    return {"tamanho": [janela.width(), janela.height()], "nomes": nomes}


def _rodape_a_vista(rodape: dict[str, Any]) -> bool:
    """As quatro zonas à vista, medidas na linha do arnês (outra linha não é o pior caso)."""
    return all(n["linha_do_arnes"] and n["mensagem_px"] >= MENSAGEM_LEGIVEL
               and n["documento_px"] >= DOCUMENTO_LEGIVEL and not n["cortadas"]
               and not n["espremidos"] for n in rodape["nomes"])


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
            saida.append({"minimo": [largura, altura], "cadeia": " < ".join(cadeia[:6]),
                          "texto": texto})
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
    _VIVOS.append(aplicacao)
    impor_a_fonte_do_produto(aplicacao)
    # as sabotagens do rodapé mudam o módulo antes de a janela existir; as outras, a janela
    antes_da_janela = {"rodape": _sabotar_o_rodape, "mensagem": _sabotar_a_mensagem,
                       "reserva": _sabotar_a_reserva}
    na_janela = {"corte": _sabotar_o_corte, "aperto": _sabotar_o_aperto,
                 "linha": _sabotar_a_linha}
    if sabotar in antes_da_janela:
        antes_da_janela[sabotar]()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal

    # **A janela não é desmontada aqui.** Visitar a área do Dataset dispara a leitura do
    # `labels.csv` numa tarefa ao fundo; fechar e sair do interpretador com ela viva derruba o
    # processo no C++ (medido nesta fase, `access violation` no `close`). Quem chama grava o
    # JSON e sai por `os._exit` -- o produto fecha pelo `closeEvent`, que espera; o arnês não
    # precisa fechar para medir.
    pasta = Path(tempfile.mkdtemp(prefix="caissa_minimo_"))
    janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(pasta))
    _VIVOS.append(janela)
    janela.show()
    for _ in range(5):
        aplicacao.processEvents()
    if pdf is not None and pdf.exists():
        janela.abrir_pdf(pdf)
        aguardar_a_folha(janela)
    if sabotar in na_janela:
        na_janela[sabotar](janela)
    todas = list(areas_de_trabalho(janela))
    areas = [area.nome for area in todas]
    for area in todas:
        area.mostrar()
        for _ in range(3):
            aplicacao.processEvents()
    _linha_cheia(janela)
    janela.resize(400, 300)
    for _ in range(6):
        aplicacao.processEvents()
    dica = janela.minimumSizeHint()
    vistas = [_vista(janela, aplicacao, todas)]
    rodapes = [_rodape(janela, aplicacao)]
    for largura, altura in TAMANHOS:
        janela.resize(largura, altura)
        for _ in range(6):
            aplicacao.processEvents()
        vistas.append(_vista(janela, aplicacao, todas))
        rodapes.append(_rodape(janela, aplicacao))
    medida = {
        "pele": nome_da_pele,
        "pdf": str(pdf) if pdf else "",
        "sabotagem": sabotar,
        "areas_visitadas": areas,
        "frase_no_rodape": len(_frase()),
        "minimo": [dica.width(), dica.height()],
        "ficou": [janela.width(), janela.height()],
        "motores": _motores(janela, 600, 380),
        "vistas": vistas,
        "rodape": rodapes,
    }
    medida["cabe"] = medida["minimo"][0] <= TETO[0] and medida["minimo"][1] <= TETO[1]
    medida["a_vista"] = (
        all(not v["fora_sem_barra"] and not v["espremidos"] and not v["fora_da_linha_do_arnes"]
            for v in vistas)
        and all(_rodape_a_vista(r) for r in rodapes))
    return medida


def medir(saida: Path, *, pdf: Path | None = None, sabotar: str = "",
          caminho_do_tronco: Path = TRONCO,
          peles: tuple[tuple[str, str], ...] = PELES) -> dict[str, Any]:
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
            raise RuntimeError(
                f"a pele {nome!r} não mediu: o subprocesso morreu antes de gravar {alvo}")
        medidas.append(json.loads(alvo.read_text(encoding="utf-8")))
        alvo.unlink()
    relatorio = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "teto": list(TETO),
        "sabotagem": sabotar,
        # de onde veio o código medido (crítico da fase 5, ciclo 3): o commit e o que a árvore
        # tinha fora dele, nos dois repositórios
        "suite": _estado_do_git(Path(__file__).resolve().parents[4]),
        "tronco": _estado_do_git(caminho_do_tronco),
        "medidas": medidas,
        "passou": all(m["cabe"] and m["a_vista"] for m in medidas),
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
        medida = medir_uma_pele(args.pele, pdf=args.pdf, sabotar=args.sabotar,
                                caminho_do_tronco=args.tronco)
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
    relatorio = medir(args.saida, pdf=args.pdf, sabotar=args.sabotar,
                      caminho_do_tronco=args.tronco)
    for medida in relatorio["medidas"]:
        _imprimir(medida)
    print("PASSOU" if relatorio["passou"] else "REPROVOU")
    return 0 if relatorio["passou"] else 1


def _imprimir(medida: dict[str, Any]) -> None:
    largura, altura = medida["minimo"]
    print(f"  {medida['pele']:<10} mínimo {largura}×{altura} "
          f"({'cabe' if medida['cabe'] else 'NÃO cabe'} em {TETO[0]}×{TETO[1]})")
    for motor in medida["motores"][:4]:
        w, h = motor["minimo"]
        print(f"      {w}×{h}  {motor['cadeia']}  {motor['texto']!r}")
    for vista in medida["vistas"]:
        largura, altura = vista["tamanho"]
        linha = ""
        if vista["fora_da_linha_do_arnes"]:
            linha = (", MEDIDA FORA DA LINHA DO ARNÊS em "
                     f"{', '.join(vista['fora_da_linha_do_arnes'])}")
        elif vista["linha_reposta"]:
            linha = f" (o produto reescreveu a linha: reposta {vista['linha_reposta']}×)"
        print(f"    a {largura}×{altura}: {len(vista['fora_sem_barra'])} fora da vista sem barra, "
              f"{len(vista['espremidos'])} espremidos, "
              f"{vista['alcancaveis_pela_barra']} alcançáveis pela barra{linha}")
        for item in (vista["fora_sem_barra"] + vista["espremidos"])[:6]:
            print(f"      [{item['area']}] {item['tipo']} {item['texto']!r} "
                  f"{item['largura']}/{item['minimo']} px ({item['cadeia']})")
    for rodape in medida["rodape"]:
        largura, altura = rodape["tamanho"]
        for n in rodape["nomes"]:
            cortadas = f", CORTADAS: {', '.join(n['cortadas'])}" if n["cortadas"] else ""
            if not n["linha_do_arnes"]:
                cortadas += ", MEDIDA FORA DA LINHA DO ARNÊS"
            elif n["linha_reposta"]:
                cortadas += f" (o produto reescreveu a linha: reposta {n['linha_reposta']}×)"
            print(f"    rodapé a {largura}×{altura}, {n['nome'][:24]}…: "
                  f"mensagem {n['mensagem_px']} "
                  f"(≥ {MENSAGEM_LEGIVEL}), documento {n['documento_px']} (≥ {DOCUMENTO_LEGIVEL}), "
                  f"dispositivos {n['dispositivos_px']}, ocupação {n['ocupacao_px']}, "
                  f"barra {n['barra_px']} px, {len(n['espremidos'])} botões espremidos{cortadas}")
            for item in n["espremidos"]:
                print(f"      {item['tipo']} {item['texto']!r} "
                      f"{item['largura']}/{item['minimo']} px")


if __name__ == "__main__":
    raise SystemExit(main())
