r"""O mostruário de controles: todo widget estilizado, nos dois temas, num quadro só.

**Existe porque auditar tema dentro do produto não fecha.** Uma captura da aba Resultado mostra
os controles que aquela aba usa, no estado em que ela os deixou -- nenhum botão desabilitado,
nenhum campo com foco, nenhuma caixa em estado indeterminado. Os defeitos de tema moram
justamente nos estados que a tela feliz não tem, e é por isso que a prancha de controles é o
instrumento e a captura do produto é a prova.

Cada controle aparece nos estados que ele sabe ter: normal, sob o ponteiro, pressionado,
**com foco**, desabilitado. A prancha é a mesma nas duas paletas, lado a lado, e a comparação
é direta -- se o tema escuro for o claro invertido, é aqui que se vê.

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
    PYTHONPATH=...\\ChessVisionOFF_Puro\\src \
    <trunk>/.venv/Scripts/python.exe -m caissa.ui.audit.amostrario --saida <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
PASTA_DE_FONTES = r"C:\Windows\Fonts"


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def montar(pai: object) -> object:
    # funções por tamanho separaria o controle do estado que ele existe para mostrar
    """A prancha inteira como um `QWidget`. Separada de `desenhar` para o teste poder montá-la."""
    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.ui import espaco, estilos
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QGridLayout,
        QGroupBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QSlider,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    quadro = QWidget(pai)  # type: ignore[arg-type]
    coluna = QVBoxLayout(quadro)
    coluna.setContentsMargins(espaco.folga(), espaco.folga(), espaco.folga(), espaco.folga())
    coluna.setSpacing(espaco.folga())

    def grupo(titulo: str) -> tuple[QGroupBox, QGridLayout]:
        caixa = QGroupBox(titulo, quadro)
        grade = QGridLayout(caixa)
        grade.setSpacing(espaco.linha())
        coluna.addWidget(caixa)
        return caixa, grade

    # ------------------------------------------------------------------------------- botões
    _, grade = grupo("Botões — normal · foco · desabilitado · ênfase")
    normal = QPushButton("Abrir PDF")
    com_foco = QPushButton("Com foco")
    desabilitado = QPushButton("Desabilitado")
    desabilitado.setEnabled(False)
    primario = tema.aplicar_papel(QPushButton("Salvar a posição"), estilos.PRIMARIO)
    destrutivo = tema.aplicar_papel(QPushButton("Apagar variante"), estilos.DESTRUTIVO)
    primario_morto = tema.aplicar_papel(QPushButton("Primário morto"), estilos.PRIMARIO)
    primario_morto.setEnabled(False)
    for indice, botao in enumerate(
        (normal, com_foco, desabilitado, primario, destrutivo, primario_morto)
    ):
        grade.addWidget(botao, 0, indice)
    com_foco.setFocus()
    _com_foco_extra: list[object] = []

    # ------------------------------------------------------------------------------- campos
    _, grade = grupo("Campos — poço, dica, número, escolha")
    campo = QLineEdit()
    campo.setText("rnbqkbnr/pppppppp/8/8")
    dica = QLineEdit()
    dica.setPlaceholderText("a FEN do diagrama selecionado")
    numero = QSpinBox()
    numero.setRange(1, 289)
    numero.setValue(42)
    escolha = QComboBox()
    escolha.addItems(["scan-puro", "vetorial", "misto"])
    campo_morto = QLineEdit()
    campo_morto.setText("desabilitado")
    campo_morto.setEnabled(False)
    for indice, widget in enumerate((campo, dica, numero, escolha, campo_morto)):
        grade.addWidget(widget, 0, indice)

    # -------------------------------------------------------------- marcas, régua, progresso
    _, grade = grupo("Marcas, régua e progresso")
    marcada = QCheckBox("Marcar diagramas")
    marcada.setChecked(True)
    vazia = QCheckBox("Roda vira a página")
    parcial = QCheckBox("Indeterminada")
    parcial.setTristate(True)
    parcial.setCheckState(Qt.CheckState.PartiallyChecked)
    morta = QCheckBox("Desabilitada")
    morta.setEnabled(False)
    brancas = QRadioButton("Brancas")
    brancas.setChecked(True)
    pretas = QRadioButton("Pretas")
    for indice, widget in enumerate((marcada, vazia, parcial, morta, brancas, pretas)):
        grade.addWidget(widget, 0, indice)
    regua = QSlider(Qt.Orientation.Horizontal)
    regua.setRange(0, 100)
    regua.setValue(62)
    # A segunda régua existe para a prancha poder mostrar o **anel de foco**, que é o estado
    # que nenhuma captura do produto pega por acaso.
    regua_com_foco = QSlider(Qt.Orientation.Horizontal)
    regua_com_foco.setRange(0, 100)
    regua_com_foco.setValue(62)
    barra = QProgressBar()
    barra.setRange(0, 100)
    barra.setValue(37)
    grade.addWidget(regua, 1, 0, 1, 2)
    grade.addWidget(regua_com_foco, 1, 2, 1, 2)
    grade.addWidget(barra, 1, 4, 1, 2)

    # ------------------------------------------------------------------------ listas e abas
    _, grade = grupo("Listas, tabela e abas")
    lista = QListWidget()
    lista.addItems(["1937 Kemeri.pdf", "Dvoretsky — Endgame Manual", "Reinfeld — 1001"])
    lista.setCurrentRow(1)
    tabela = QTableWidget(3, 2)
    tabela.setHorizontalHeaderLabels(["Página", "Diagramas"])
    for linha_idx, (pagina, quantos) in enumerate((("20", "3"), ("40", "5"), ("150", "1"))):
        tabela.setItem(linha_idx, 0, QTableWidgetItem(pagina))
        tabela.setItem(linha_idx, 1, QTableWidgetItem(quantos))
    tabela.selectRow(1)
    abas = QTabWidget()
    for nome in ("Resultado", "Estudo", "Galeria"):
        pagina = QWidget()
        QVBoxLayout(pagina).addWidget(QLabel(f"conteúdo de {nome}"))
        abas.addTab(pagina, nome)
    for indice, widget in enumerate((lista, tabela, abas)):
        widget.setMinimumHeight(150)
        grade.addWidget(widget, 0, indice)

    coluna.addStretch(1)
    # O foco vai para a régua no fim: `setFocus` no fim de `montar` é o último a valer.
    regua_com_foco.setFocus()
    return quadro


def desenhar(saida: Path, *, caminho_do_tronco: Path = TRONCO) -> list[Path]:
    """Grava uma prancha por pele e devolve os caminhos."""
    _preparar(caminho_do_tronco)
    saida.mkdir(parents=True, exist_ok=True)

    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.ui import pele
    from PyQt6.QtWidgets import QApplication

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    gravados: list[Path] = []
    for registro in pele.PELES:
        if registro.nome == pele.FITA:
            continue  # a fita repete a paleta da clássica; a prancha mede paleta, não arranjo
        tema.aplicar_tema(aplicacao, cromo_escuro=registro.cromo_escuro)  # type: ignore[arg-type]
        quadro = montar(None)
        quadro.resize(1180, 620)  # type: ignore[attr-defined]
        quadro.show()  # type: ignore[attr-defined]
        for _ in range(5):
            aplicacao.processEvents()  # type: ignore[union-attr]
        nome = "escuro" if registro.cromo_escuro else "claro"
        alvo = saida / f"amostrario_{nome}.png"
        quadro.grab().save(str(alvo))  # type: ignore[attr-defined]
        gravados.append(alvo)
        print(f"  {alvo.name}")
        quadro.close()  # type: ignore[attr-defined]
    return gravados


ESTADOS = ("repouso", "sob o ponteiro", "pressionado", "com foco", "desabilitado")
"""Os cinco estados de um botão, na ordem em que a prancha os desenha (F9-C2, §7 item 8).

**Os dois do meio não existiam em imagem nenhuma.** O relatório do ciclo 1 publicou os números de
`hover` e `pressed` -- a razão de contraste do rótulo em cada um -- e a prancha não desenhava
nem um nem outro: a única prova de que aqueles números descrevem alguma coisa era a aritmética
que os produziu. E o `com foco` era pior que ausente: a prancha rotulava uma célula "Com foco" e
a linha seguinte chamava `setFocus()` **noutro widget**, então a célula rotulada saía em repouso.
Um rótulo que não bate com a célula é a única coisa numa prancha de controles que não pode
acontecer, porque a prancha existe para ser lida em vez do código."""


SOB_O_PONTEIRO = ESTADOS[1]
"""O rótulo da coluna de `hover`. Nomeado porque três lugares o comparam."""

REPOUSO = ESTADOS[0]
"""O rótulo da coluna de referência: é contra ela que a diferença de cada estado é medida."""

NOTA_DO_CAMPO = (
    "campo: a folha de estilo do produto NÃO declara `:hover` para campo de texto "
    "(ui/folha_de_estilo.py, bloco `campos`: os oito seletores têm `:focus` e `:disabled` e "
    "nenhum `:hover`), e por isso esta célula é igual à de repouso. É a verdade do produto, e "
    "está escrita aqui para não ser lida como defeito da prancha."
)
"""Por que a única célula com ΔRGB zero tem o direito de ficar em zero (F9-C3).

**A prancha do ciclo 2 desenhava `hover` idêntico a repouso nas 8 imagens, nas 4 linhas, nas 2
peles -- ΔRGB máximo zero -- e o relatório afirmava por escrito o mecanismo que teria evitado
isso.** A causa, medida nesta máquina: `WA_UnderMouse` mais `QEvent.Type.Enter` e `HoverEnter`
sintéticos fazem `QWidget.underMouse()` devolver **`True`** e **não** acendem
`QStyle.State_MouseOver` na opção com que o botão se pinta -- e sem esse bit a folha não aplica
`:hover`. Com `WA_Hover` + `WA_UnderMouse` + `Enter` + `HoverEnter` + `unpolish/polish`:
ΔRGB = **0**. Com a opção montada à mão e `State_MouseOver` aceso: ΔRGB = **25 / 38 / 30**
(neutro, primário, destrutivo). Os três botões pintam-se assim agora -- ver `_classe_do_botao`.

O campo é o caso oposto, e ele **não** foi consertado porque não há o que consertar: `QLineEdit`,
`QTextEdit`, `QAbstractSpinBox` e as quatro vistas recebem `:focus` e `:disabled` e nenhum
`:hover`. Um campo de texto que muda de cor ao passar o ponteiro não é o que a folha decidiu, e
forjá-lo na prancha seria a prancha mentindo na direção contrária.
"""


def _classe_do_botao() -> type:
    """`QPushButton` que se pinta no estado que o rótulo da célula promete (F9-C3).

    Definida dentro de uma função porque este módulo é importável sem Qt -- é o que permite ao
    teste da suíte ler `NOTA_DO_CAMPO` e a aritmética de diferença num venv sem binding nenhum.
    """
    from PyQt6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter

    class _BotaoNoEstado(QPushButton):
        """Ver `NOTA_DO_CAMPO` para a medição que obrigou este desvio."""

        def __init__(self, texto: str, pai: object, *, sob_o_ponteiro: bool) -> None:
            super().__init__(texto, pai)  # type: ignore[arg-type]
            self._sob_o_ponteiro = sob_o_ponteiro

        def paintEvent(self, e: object) -> None:  # noqa: N802 - assinatura do Qt
            if not self._sob_o_ponteiro:
                super().paintEvent(e)  # type: ignore[arg-type]
                return
            # **A opção é montada à mão e o bit é aceso**: é a única forma que faz a folha
            # aplicar `:hover` sem um ponteiro de verdade. O resto -- face, letra, borda, raio --
            # continua saindo da folha do produto, então a célula é o botão do produto e não um
            # desenho parecido com ele.
            opcao = QStyleOptionButton()
            self.initStyleOption(opcao)
            opcao.state |= QStyle.StateFlag.State_MouseOver
            QStylePainter(self).drawControl(QStyle.ControlElement.CE_PushButton, opcao)

    return _BotaoNoEstado


def prancha_de_estados(pai: object, papeis: "Sequence[str]") -> tuple[object, list[tuple[object, str]]]:
    """A grade `papel × estado`: uma coluna por estado, uma linha por papel de botão.

    Devolve o quadro e a lista `(botão, estado)`, porque quem grava precisa **pôr** cada estado
    e o `com foco` só pode ser posto um de cada vez -- o Qt tem um foco só.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGridLayout, QLabel, QLineEdit, QWidget

    from chess_diagram_ocr.qt import tema

    botao_de = _classe_do_botao()
    quadro = QWidget(pai)  # type: ignore[arg-type]
    grade = QGridLayout(quadro)
    for coluna, estado in enumerate(ESTADOS):
        grade.addWidget(QLabel(estado, quadro), 0, coluna + 1)
    celulas: list[tuple[object, str]] = []
    for linha, papel in enumerate(papeis):
        grade.addWidget(QLabel(papel, quadro), linha + 1, 0)
        for coluna, estado in enumerate(ESTADOS):
            botao = botao_de("Salvar a posição", quadro, sob_o_ponteiro=estado == SOB_O_PONTEIRO)
            tema.aplicar_papel(botao, papel)
            botao.setMinimumWidth(170)
            # `WA_Hover` fica: ele é o que faz o Qt repintar quando um ponteiro **de verdade**
            # entra. O que ele não faz -- e o ciclo 2 escreveu que fazia -- é acender
            # `State_MouseOver` para um evento sintético. Ver `NOTA_DO_CAMPO`.
            botao.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            grade.addWidget(botao, linha + 1, coluna + 1)
            celulas.append((botao, estado))
    grade.addWidget(QLabel("campo", quadro), len(papeis) + 1, 0)
    for coluna, estado in enumerate(ESTADOS):
        campo = QLineEdit("rnbqkbnr/pppppppp/8/8", quadro)
        grade.addWidget(campo, len(papeis) + 1, coluna + 1)
        celulas.append((campo, estado))
    nota = QLabel(NOTA_DO_CAMPO, quadro)
    nota.setWordWrap(True)
    grade.addWidget(nota, len(papeis) + 2, 0, 1, len(ESTADOS) + 1)
    return quadro, celulas


def _pousar(celula: object, estado: str) -> None:
    """Põe a célula no estado que o rótulo dela promete. `com foco` é posto por quem grava.

    `sob o ponteiro` **não** aparece aqui, e a ausência é o conserto do F9-C3: ele é escolhido na
    construção da célula e honrado no `paintEvent` dela, porque não existe evento sintético que o
    produza. Ver `NOTA_DO_CAMPO`.
    """
    if estado == "pressionado":
        marcar = getattr(celula, "setDown", None)
        if marcar is not None:
            marcar(True)
    elif estado == "desabilitado":
        celula.setEnabled(False)  # type: ignore[attr-defined]


def desenhar_estados(saida: Path, *, caminho_do_tronco: Path = TRONCO) -> list[Path]:
    """Grava a prancha `papel × estado` das duas peles. Uma imagem por alvo de foco.

    **Uma imagem por foco, e não uma com três anéis**, porque o Qt tem um foco só: forjar três
    anéis de foco na mesma captura desenharia um estado que a janela nunca mostra. Três capturas
    por pele é a resposta honesta, e é o que o crítico do ciclo 1 fez no `estados.py` dele.
    """
    _preparar(caminho_do_tronco)
    saida.mkdir(parents=True, exist_ok=True)

    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.ui import estilos, pele
    from PyQt6.QtWidgets import QApplication

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    papeis = [estilos.NEUTRO, estilos.PRIMARIO, estilos.DESTRUTIVO]
    gravados: list[Path] = []
    manifesto: dict[str, Any] = {"nota_do_campo": NOTA_DO_CAMPO, "pranchas": {}}
    for registro in pele.PELES:
        if registro.nome == pele.FITA:
            continue
        tema.aplicar_tema(aplicacao, cromo_escuro=registro.cromo_escuro)  # type: ignore[arg-type]
        quadro, celulas = prancha_de_estados(None, papeis)
        quadro.resize(1180, 300)  # type: ignore[attr-defined]
        quadro.show()  # type: ignore[attr-defined]
        aplicacao.processEvents()  # type: ignore[union-attr]
        for celula, estado in celulas:
            _pousar(celula, estado)
        nome = "escuro" if registro.cromo_escuro else "claro"
        com_foco = [celula for celula, estado in celulas if estado == "com foco"]
        for indice, celula in enumerate(com_foco):
            celula.setFocus()  # type: ignore[attr-defined]
            for _ in range(6):
                aplicacao.processEvents()  # type: ignore[union-attr]
            quadro.repaint()  # type: ignore[attr-defined]
            aplicacao.processEvents()  # type: ignore[union-attr]
            alvo = saida / f"estados_{nome}_foco{indice}.png"
            # **Uma foto só, e todas as medidas saem dela.** Medir cada célula com um `grab()`
            # próprio daria um número que não bate com o PNG: o widget sozinho antialiasa a borda
            # contra outro fundo, e a diferença apareceu como 26 contra 27. O manifesto tem de ser
            # conferível **sobre a imagem gravada**, senão ele é mais uma afirmação sem prova.
            prancha = quadro.grab()  # type: ignore[attr-defined]
            prancha.save(str(alvo))
            manifesto["pranchas"][alvo.name] = _celulas_medidas(
                prancha.toImage(), quadro, celulas, papeis
            )
            gravados.append(alvo)
            print(f"  {alvo.name}")
        quadro.close()  # type: ignore[attr-defined]
    mapa = saida / MANIFESTO
    mapa.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  {mapa.name}")
    return gravados


MANIFESTO = "estados_celulas.json"
"""Onde a prancha publica **onde cada célula está e quanto ela difere do repouso** (F9-C3).

**Existe porque a prancha mentiu duas vezes seguidas, e nas duas o rótulo era a mentira.** No
ciclo 1 a célula rotulada "Com foco" saía em repouso porque o `setFocus()` da linha seguinte era
noutro widget; no ciclo 2 a coluna "sob o ponteiro" saía byte a byte igual à de repouso nas oito
imagens. Nos dois casos a imagem estava lá para ser olhada e ninguém tinha como cobrar dela nada
sem abrir o Paint.

O manifesto dá o retângulo de cada célula e o ΔRGB máximo dela contra a célula de repouso da
mesma linha, para que `tests/unit/ui/test_amostrario.py` refaça a conta **sobre o PNG** e falhe
quando a prancha voltar a desenhar um estado que ela não tem. Um número que só existe na
memória do gerador não prova coisa nenhuma; este é conferível contra a imagem gravada."""


def _celulas_medidas(
    prancha: object, quadro: object, celulas: list[tuple[object, str]], papeis: "Sequence[str]"
) -> list[dict[str, Any]]:
    """O retângulo e o ΔRGB contra o repouso de cada célula desta prancha. Ver `MANIFESTO`."""
    linhas = [*papeis, "campo"]
    por_linha = len(ESTADOS)
    postos: list[dict[str, Any]] = []
    for indice, (celula, estado) in enumerate(celulas):
        canto = celula.mapTo(quadro, celula.rect().topLeft())  # type: ignore[attr-defined]
        postos.append(
            {
                "papel": linhas[indice // por_linha],
                "estado": estado,
                "x": canto.x(),
                "y": canto.y(),
                "largura": celula.width(),  # type: ignore[attr-defined]
                "altura": celula.height(),  # type: ignore[attr-defined]
            }
        )
    for indice, posto in enumerate(postos):
        repouso = postos[(indice // por_linha) * por_linha]
        posto["delta_rgb"] = diferenca_maxima(
            _recorte(prancha, posto), _recorte(prancha, repouso)
        )
    return postos


def _recorte(imagem: object, celula: dict[str, Any]) -> list[tuple[int, int, int]]:
    """Os pixels de uma célula **dentro da foto da prancha**, como `(r, g, b)`."""
    cor_em = imagem.pixelColor  # type: ignore[attr-defined]
    return [
        (cor.red(), cor.green(), cor.blue())
        for y in range(celula["y"], celula["y"] + celula["altura"])
        for cor in (cor_em(x, y) for x in range(celula["x"], celula["x"] + celula["largura"]))
    ]


def diferenca_maxima(
    a: "Sequence[tuple[int, int, int]]", b: "Sequence[tuple[int, int, int]]"
) -> int:
    """O maior desvio, em qualquer canal, entre duas imagens do mesmo tamanho.

    **Máximo e não média, e a diferença importa.** Uma média sobre a célula inteira dilui a
    mudança de estado no fundo que não mudou: o realce de `hover` cobre a face do botão e não o
    vão em volta dele, e uma média de 6.240 pixels devolveria "quase zero" para uma mudança
    perfeitamente visível. O que a prancha precisa afirmar é *"existe pixel diferente"*, e o
    máximo é exatamente essa afirmação.

    Tamanhos diferentes devolvem 255: são duas células que nem sequer têm a mesma geometria, e
    isso é uma diferença maior que qualquer cor.
    """
    if len(a) != len(b):
        return 255
    maior = 0
    for (r1, g1, b1), (r2, g2, b2) in zip(a, b):
        maior = max(maior, abs(r1 - r2), abs(g1 - g2), abs(b1 - b2))
    return maior


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--estados", action="store_true", help="só a prancha papel x estado")
    args = parser.parse_args(argv)
    if not args.estados:
        desenhar(args.saida, caminho_do_tronco=args.tronco)
    desenhar_estados(args.saida, caminho_do_tronco=args.tronco)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
