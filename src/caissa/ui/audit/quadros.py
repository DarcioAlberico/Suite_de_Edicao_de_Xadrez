"""Mede o tempo de quadro do pan e do zoom no visor do tronco (SPEC §11.3: >= 55 fps).

**Por que este arquivo existe em vez de um número no relatório.** A carta dos críticos (§6)
diz que um portão numérico reportado pelo construtor é remedido pelo crítico, e que métrica
medida uma vez não conta. Então a medição tem de ser um programa que um terceiro hostil roda
sem perguntar nada a ninguém -- e que roda **três vezes** e reporta a mediana, porque é isso
que a carta exige.

**A parte de cima deste módulo não importa Qt, e é deliberado.** A aritmética de percentil, de
fps e de fração acima do orçamento é onde o número pode ser massageado sem que ninguém veja;
por isso ela é pura, mora antes de qualquer `import PyQt6` e é afirmada por teste no venv da
suíte, que **não tem PyQt6**. O Qt só entra dentro das funções que dirigem a janela.

---

**Três decisões de medição, e cada uma responde a um jeito de mentir.**

1. **`repaint()`, e nunca `update()`.** `update()` só marca a região como suja e volta na hora:
   um laço de mil `update()` mede a velocidade de agendar, não a de pintar, e reportaria
   dezenas de milhares de fps sobre uma janela que engasga. `repaint()` sincroniza o
   *backing store* -- quando ele volta, os pixels existem.
2. **O relógio envolve o gesto *e* a repintura.** Um quadro é o que acontece entre o mouse
   andar e os pixels ficarem prontos, e no visor do tronco parte do custo está no gesto: o
   zoom invalida `_escalada`, e quem paga o reescalonamento é a repintura seguinte. Medir só
   a repintura esconderia metade do trabalho de metade dos quadros.
3. **O fps sai do p95, e não da média.** A média de 60 quadros com 6 travadas continua bonita;
   o que a pessoa vê é a travada. O p95 é o pior quadro de cada vinte -- ~3 vezes por segundo
   a 60 Hz --, e é o número que corresponde à palavra "sustentados" do portão.

**O que fica de fora, e é honesto dizer.** `QT_QPA_PLATFORM=offscreen` usa o mesmo motor
raster do QPainter que o Windows usa para widgets, então o custo de CPU da pintura é o mesmo;
o que ele não paga é a apresentação da moldura ao compositor. O número medido aqui é portanto
um **piso** do tempo de quadro real, e um resultado reprovado aqui é reprovado com folga.

Uso (venv do tronco, que é onde o PyQt6 mora):

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
    PYTHONPATH=C:/Python-Chess2/ChessVisionOFF_Puro/src \
    <tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.quadros --pdf "<livro>.pdf"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` só existe no 3.11, e o venv do **tronco** -- que é onde o PyQt6 mora
(ADR-0009) -- é 3.10. O alias deixa o resto do módulo escrito na forma nova e faz o arnês rodar
nos dois interpretadores.

**Escrito como `timezone(timedelta(0))` e não como `timezone.utc`, e isso foi aprendido do jeito
caro.** O `ruff --fix` desta suíte tem alvo py311: ele reescreve `timezone.utc` como
`datetime.UTC` e acrescenta o `import` correspondente -- que é exatamente o `import` que morre no
3.10. Um `# noqa` não protege, porque a regra pega o **uso** e não a linha do alias. A forma
construída é idêntica por definição (`timezone(timedelta(0)) is timezone.utc`) e não tem por onde
ser reescrita. A regra está certa para o resto do repositório; aqui ela quebrava o arnês."""

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
PASTA_DE_FONTES = r"C:\Windows\Fonts"
"""Sem esta variável o `offscreen` do Windows sobe com **zero** famílias de fonte, e toda
métrica de texto passa a ser a da fonte de reserva -- o achado que `capture.py` registra."""

"""`src/caissa/ui/audit/quadros.py` -> quatro níveis acima é a raiz da suíte."""

ORCAMENTO_MS = 16.0
"""O piso do SPEC §11.3: nenhuma operação segura a thread da interface por mais que isto."""

ORCAMENTO_DE_55_FPS_MS = 1000.0 / 55.0
"""18,18 ms -- o tempo de quadro que corresponde exatamente ao portão de 55 fps.

Escrito como divisão e não como `18.2` de propósito: um arredondamento para cima no
orçamento é meio ponto de fps de folga que ninguém autorizou."""

DPI_DA_MEDICAO = 300
"""O portão fala de "uma página de 300 DPI", e é essa a página que este módulo rasteriza."""

TETO_DA_FAIXA_DE_ZOOM = 1.999
PISO_DA_FAIXA_DE_ZOOM = 0.2501
"""Onde a varredura de zoom inverte o sentido.

São os limites de `visor.zoom` com meio passo de folga: sem a folga o giro seguinte seria
grampeado pelo visor e descartado sem repintar nada -- quadros de custo zero que puxariam a
mediana para baixo."""

QUADROS_DE_PAN = 120
QUADROS_DE_ZOOM = 60
"""Quantos quadros por varredura.

120 no pan porque é ~2 s de arrasto contínuo a 60 Hz -- tempo suficiente para o portão
"sustentados" significar alguma coisa. 60 no zoom porque o curso inteiro de `MIN_ZOOM` a
`MAX_ZOOM` são ~15 passos de roda, e 60 são quatro travessias do curso: ida, volta, ida,
volta. Menos que isso mediria um trecho da faixa de zoom em vez da faixa."""

AQUECIMENTO = 6
"""Quadros pintados **antes** de o relógio começar, e o número aparece no relatório.

A primeira repintura de um widget aloca o *backing store* e resolve a fonte; nenhuma das duas
volta a acontecer, e nenhuma é um quadro de pan. Descartá-las sem dizer quantas seria
maquiagem, e por isso o campo `aquecimento` vai no JSON."""

EXECUCOES = 3
"""O mínimo da carta dos críticos (§6). Menos que três não é uma mediana."""


# --------------------------------------------------------------- a aritmética (sem Qt algum)


@dataclass(frozen=True)
class Estatisticas:
    """O resumo de uma varredura. É o que o JSON grava e o que o teste afirma."""

    quadros: int
    media_ms: float
    mediana_ms: float
    p95_ms: float
    p99_ms: float
    pior_ms: float
    fps_p95: float
    """Os fps derivados do **p95**, e não da média -- ver o topo do módulo."""

    fps_mediana: float
    """Só para comparação: é o número bonito, e ele está aqui para o crítico ver a distância."""

    fracao_acima_de_16ms: float
    fracao_acima_de_55fps: float
    """Fração de quadros acima de `ORCAMENTO_MS` e de `ORCAMENTO_DE_55_FPS_MS`."""

    def passou(self) -> bool:
        """O portão do SPEC §11.3: >= 55 fps sustentados, medidos no p95.

        **A comparação é de tempo de quadro contra o orçamento, e não de fps contra 55**, e a
        diferença é um épsilon que o teste achou: `1000 / (1000 / 55)` dá **54,99999999999999** em
        ponto flutuante, então uma varredura em que todo quadro custa exatamente o orçamento
        declarado reprovava por 1e-14 de fps. O tempo de quadro é a grandeza medida; os fps são a
        divisão que a torna legível. Comparar na grandeza medida elimina a divisão do portão.
        """
        return self.quadros > 0 and self.p95_ms <= ORCAMENTO_DE_55_FPS_MS


def percentil(valores: Sequence[float], fracao: float) -> float:
    """O percentil por **posto mais próximo**, sem interpolar. Zero numa sequência vazia.

    Sem interpolação porque o valor interpolado é um tempo de quadro que **nenhum quadro
    teve**. Num conjunto de 60 medições, o p95 interpolado do numpy mistura o 57º e o 58º
    quadro e produz um número que não é observação de nada; o posto mais próximo devolve o 57º,
    que é um quadro que existiu e que dá para ir procurar no rastro.

    A fórmula é `ceil(fracao * n)`, grampeada em `[1, n]`: com `n = 20` e `fracao = 0,95` cai no
    20º, o pior de vinte, que é o que a palavra "p95" promete.
    """
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    posto = math.ceil(float(fracao) * len(ordenados))
    return ordenados[max(1, min(len(ordenados), posto)) - 1]


def _fps(tempo_ms: float) -> float:
    """Quadros por segundo de um tempo de quadro. Zero quando não houve quadro nenhum.

    Zero e não infinito: um tempo de quadro nulo é ausência de medição, e `inf` num relatório de
    fps é lido como "rápido demais para medir" -- que é exatamente a conclusão errada.
    """
    return 1000.0 / tempo_ms if tempo_ms > 0.0 else 0.0


def estatisticas(tempos_ms: Sequence[float]) -> Estatisticas:
    """O resumo de uma lista de tempos de quadro, em milissegundos.

    Sequência vazia devolve tudo em zero -- inclusive `fps_p95`, e é por isso que `passou()`
    exige `quadros > 0`: uma varredura que não mediu quadro nenhum não pode ser aprovada por
    omissão, que é o modo mais silencioso de um portão numérico deixar de existir.
    """
    if not tempos_ms:
        return Estatisticas(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    total = len(tempos_ms)
    mediana = percentil(tempos_ms, 0.5)
    p95 = percentil(tempos_ms, 0.95)
    acima_16 = sum(1 for valor in tempos_ms if valor > ORCAMENTO_MS)
    acima_55 = sum(1 for valor in tempos_ms if valor > ORCAMENTO_DE_55_FPS_MS)
    return Estatisticas(
        quadros=total,
        media_ms=sum(tempos_ms) / total,
        mediana_ms=mediana,
        p95_ms=p95,
        p99_ms=percentil(tempos_ms, 0.99),
        pior_ms=max(tempos_ms),
        fps_p95=_fps(p95),
        fps_mediana=_fps(mediana),
        fracao_acima_de_16ms=acima_16 / total,
        fracao_acima_de_55fps=acima_55 / total,
    )


def execucao_mediana(execucoes: Sequence[Estatisticas]) -> Estatisticas:
    """A execução **mediana** de várias, escolhida pelo `fps_p95`.

    **Uma execução inteira, e não um Frankenstein de medianas por campo.** Tirar a mediana de
    cada métrica separadamente produziria um bloco cuja média vem de uma execução, o p95 de
    outra e o pior de uma terceira -- números que nunca coexistiram numa mesma medição, e que
    portanto ninguém consegue reproduzir. Aqui o bloco reportado é uma execução que aconteceu.

    O critério é o `fps_p95` porque é ele que o portão do §11.3 lê: assim o fps reportado é, de
    fato, a mediana dos fps das execuções. Em número par de execuções, ganha a **pior** das duas
    do meio -- o portão não é lugar para arredondar a favor.
    """
    if not execucoes:
        return estatisticas([])
    ordenadas = sorted(execucoes, key=lambda item: item.fps_p95)
    return ordenadas[(len(ordenadas) - 1) // 2]


# ------------------------------------------------------------------- a janela (Qt aqui, e só)


def _preparar(caminho_do_tronco: Path = TRONCO) -> None:
    """Offscreen, fontes e `PYTHONPATH` -- as três condições de a medição não mentir."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def _montar(pdf: Path, *, pagina: int, dpi: int, largura: int, altura: int) -> tuple[Any, Any]:
    """Sobe a aplicação, abre o livro na página pedida e devolve `(aplicacao, painel)`.

    **`show()` antes de `load_pdf`**, porque só um widget mostrado tem área visível -- e é a área
    visível que decide o `pageStep` das barras, que é o passo do pan. Um painel medido antes do
    `show` teria barras de tamanho zero e o arrasto não moveria nada.
    """
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt.painel_do_pdf import PainelDoPdf
    from PyQt6.QtWidgets import QApplication

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    painel = PainelDoPdf(None, dpi=lambda: dpi)
    painel.resize(largura, altura)
    painel.show()
    aplicacao.processEvents()
    painel.load_pdf(pdf)
    painel.ir_para_pagina(pagina)
    for _ in range(3):
        aplicacao.processEvents()
    if painel.page_rgb is None:
        raise RuntimeError(f"{pdf.name} não rasterizou a página {pagina + 1} a {dpi} DPI.")
    return aplicacao, painel


def _alvo_da_repintura(painel: Any) -> Any:
    """O widget cuja repintura *é* o quadro do pan e do zoom: a área visível do visor.

    Não é o painel inteiro de propósito. As barras de ferramentas acima da página não ficam
    sujas quando a página rola -- o Qt não as repinta --, e incluí-las carregaria o tempo de
    quadro com trabalho que o quadro real não faz. Inflar o número para o lado da reprovação é
    tão desonesto quanto inflá-lo para o lado da aprovação.

    Repintar a área visível pinta também a folha que está dentro dela, e a folha é onde estão as
    duas contas caras: o `drawPixmap` da página e o reescalonamento suave do zoom.
    """
    area = painel.visor.viewport()
    if area is None:  # pragma: no cover - só num QScrollArea em desmontagem
        raise RuntimeError("O visor está sem área visível.")
    return area


def varredura_de_pan(painel: Any, *, quadros: int = QUADROS_DE_PAN) -> list[float]:
    """Um arrasto contínuo pela página, e o tempo de cada quadro em milissegundos.

    **O caminho é uma espiral, e não uma linha reta.** Uma reta desce a página encostando na
    borda inferior depois de poucas dezenas de quadros, e daí em diante as barras não se movem
    mais: os quadros seguintes mediriam uma repintura idêntica à anterior e o resultado seria
    o custo de repintar a mesma coisa, que é a pergunta errada. A espiral mantém as duas barras
    andando o tempo todo e mede o que o pan de verdade custa.

    O gesto entra pelos métodos públicos do visor (`apertou_em`/`arrastou_para`/`soltou_em`) e
    não por `QMouseEvent` sintético porque os manipuladores do Qt em `_Folha` só repassam a
    posição -- enfileirar eventos acrescentaria a latência do laço de eventos ao tempo de
    quadro sem acrescentar nenhuma decisão do produto ao que está sendo medido.
    """
    visor = painel.visor
    alvo = _alvo_da_repintura(painel)
    centro_x, centro_y = alvo.width() / 2.0, alvo.height() / 2.0
    visor.apertou_em(centro_x, centro_y)
    for _ in range(AQUECIMENTO):
        alvo.repaint()

    tempos: list[float] = []
    ultimo = (centro_x, centro_y)
    for indice in range(quadros):
        angulo = indice * 0.12
        ponto = (
            centro_x + 220.0 * math.cos(angulo),
            centro_y + 180.0 * math.sin(angulo) - indice * 2.0,
        )
        comeco = time.perf_counter()
        visor.arrastou_para(*ponto)
        alvo.repaint()
        tempos.append((time.perf_counter() - comeco) * 1000.0)
        ultimo = ponto
    visor.soltou_em(*ultimo)
    return tempos


def varredura_de_zoom(painel: Any, *, quadros: int = QUADROS_DE_ZOOM) -> list[float]:
    """A roda com Ctrl, ancorada no ponteiro, percorrendo a faixa de zoom -- e o custo de cada.

    **Passa por `girar_roda` com um `QWheelEvent` de verdade**, e aqui isso importa: é a roda que
    decide entre rolar, virar a página e dar zoom, e chamar o método privado de zoom pularia a
    decisão que o portão diz medir ("pan/zoom"). O ponteiro fica fixo num ponto fora do centro
    para que a âncora tenha o que ancorar -- zoom no centro exato não move barra nenhuma, e o
    reposicionamento das duas barras faz parte do quadro.

    O sentido inverte nos extremos da faixa: sem isso, os ~15 passos de `MIN_ZOOM` a `MAX_ZOOM`
    se esgotariam e o resto da varredura mediria giros que `zoomed` grampeia e o visor descarta
    sem repintar nada -- quadros de custo zero que puxariam a mediana para baixo.
    """
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    visor = painel.visor
    alvo = _alvo_da_repintura(painel)
    ponteiro = QPointF(alvo.width() * 0.35, alvo.height() * 0.35)
    for _ in range(AQUECIMENTO):
        alvo.repaint()

    tempos: list[float] = []
    sentido = 1
    for _ in range(quadros):
        if visor.zoom >= TETO_DA_FAIXA_DE_ZOOM:
            sentido = -1
        elif visor.zoom <= PISO_DA_FAIXA_DE_ZOOM:
            sentido = 1
        evento = QWheelEvent(
            ponteiro,
            ponteiro,
            QPoint(0, 0),
            QPoint(0, 120 * sentido),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        comeco = time.perf_counter()
        visor.girar_roda(evento)
        alvo.repaint()
        tempos.append((time.perf_counter() - comeco) * 1000.0)
    return tempos


def uma_execucao(painel: Any, *, quadros_de_pan: int, quadros_de_zoom: int) -> dict[str, Any]:
    """Uma execução completa: a varredura de pan, a de zoom, e as duas juntas.

    "As duas juntas" existe porque o portão do §11.3 diz "pan/zoom" numa linha só: separar é o
    que torna o defeito acionável, mas o veredito é sobre o conjunto, e concatenar as amostras
    é a única forma de o p95 do conjunto ser um p95 e não uma média de dois p95.
    """
    painel.aplicar_zoom(1.0)
    pan = varredura_de_pan(painel, quadros=quadros_de_pan)
    painel.aplicar_zoom(1.0)
    zoom = varredura_de_zoom(painel, quadros=quadros_de_zoom)
    return {
        "pan": asdict(estatisticas(pan)),
        "zoom": asdict(estatisticas(zoom)),
        "juntos": asdict(estatisticas([*pan, *zoom])),
        "_tempos": {"pan": pan, "zoom": zoom},
    }


def medir(
    pdf: Path,
    *,
    pagina: int = 40,
    dpi: int = DPI_DA_MEDICAO,
    largura: int = 1280,
    altura: int = 800,
    execucoes: int = EXECUCOES,
    quadros_de_pan: int = QUADROS_DE_PAN,
    quadros_de_zoom: int = QUADROS_DE_ZOOM,
    caminho_do_tronco: Path = TRONCO,
    guardar_tempos: bool = True,
) -> dict[str, Any]:
    """Roda `execucoes` medições completas e devolve o relatório, com a mediana já escolhida.

    Guardar os tempos de quadro crus é o item: uma mediana sem a amostra que a produziu não é
    reproduzível nem conferível, e a carta (§6) reprova o que não se consegue reproduzir.
    """
    _preparar(caminho_do_tronco)
    aplicacao, painel = _montar(pdf, pagina=pagina, dpi=dpi, largura=largura, altura=altura)
    alvo = _alvo_da_repintura(painel)

    corridas: list[dict[str, Any]] = []
    for numero in range(execucoes):
        corrida = uma_execucao(
            painel, quadros_de_pan=quadros_de_pan, quadros_de_zoom=quadros_de_zoom
        )
        corrida["execucao"] = numero + 1
        corridas.append(corrida)
        aplicacao.processEvents()

    from PyQt6.QtCore import QT_VERSION_STR

    medianas = {
        chave: asdict(
            execucao_mediana([Estatisticas(**corrida[chave]) for corrida in corridas])
        )
        for chave in ("pan", "zoom", "juntos")
    }
    tempos = [corrida.pop("_tempos") for corrida in corridas]
    relatorio: dict[str, Any] = {
        "portao": "SPEC 11.3 -- pan/zoom >= 55 fps sustentados em pagina de 300 DPI",
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "ambiente": {
            "qt": QT_VERSION_STR,
            "python": sys.version.split()[0],
            "plataforma_qpa": os.environ.get("QT_QPA_PLATFORM", ""),
            "fontdir": os.environ.get("QT_QPA_FONTDIR", ""),
            "aviso": (
                "offscreen usa o mesmo motor raster do QPainter; nao paga a apresentacao ao "
                "compositor. Os tempos aqui sao um piso do tempo de quadro real."
            ),
        },
        "amostra": {
            "pdf": str(pdf),
            "pagina_base_1": pagina + 1,
            "dpi": dpi,
            "pagina_px": list(painel.page_rgb.shape[:2][::-1]),
            "area_visivel_px": [alvo.width(), alvo.height()],
            "janela_px": [largura, altura],
        },
        "metodo": {
            "repintura": "viewport().repaint() -- sincrono; update() mediria agendamento",
            "relogio": "envolve o gesto e a repintura",
            "aquecimento": AQUECIMENTO,
            "execucoes": execucoes,
            "quadros_por_execucao": {"pan": quadros_de_pan, "zoom": quadros_de_zoom},
            "fps": "derivado do p95, nao da media",
            "percentil": "posto mais proximo, sem interpolacao",
            "escolha_da_mediana": "a execucao com o fps_p95 mediano, inteira",
        },
        "execucoes": corridas,
        "mediana": medianas,
        "veredito": {
            chave: "PASSOU" if Estatisticas(**medianas[chave]).passou() else "REPROVOU"
            for chave in medianas
        },
    }
    if guardar_tempos:
        relatorio["tempos_de_quadro_ms"] = tempos
    painel.close()
    return relatorio


# ------------------------------------------------------------------------ saída para humanos


def _linha(nome: str, dado: dict[str, Any]) -> str:
    return (
        f"  {nome:<8} {dado['quadros']:>5}  {dado['media_ms']:>8.2f} {dado['mediana_ms']:>8.2f} "
        f"{dado['p95_ms']:>8.2f} {dado['p99_ms']:>8.2f} {dado['pior_ms']:>8.2f} "
        f"{dado['fps_p95']:>8.1f} {dado['fracao_acima_de_16ms'] * 100:>7.1f}% "
        f"{dado['fracao_acima_de_55fps'] * 100:>7.1f}%"
    )


def tabela(relatorio: dict[str, Any]) -> str:
    """A tabela curta para o terminal. O JSON é a prova; isto é o que se lê de relance."""
    amostra = relatorio["amostra"]
    linhas = [
        f"Pan/zoom -- {Path(amostra['pdf']).name}, pagina {amostra['pagina_base_1']}, "
        f"{amostra['dpi']} DPI ({amostra['pagina_px'][0]}x{amostra['pagina_px'][1]} px)",
        f"Area visivel {amostra['area_visivel_px'][0]}x{amostra['area_visivel_px'][1]} px  "
        f"| {relatorio['metodo']['execucoes']} execucoes, mediana reportada",
        "",
        f"  {'gesto':<8} {'quadros':>5}  {'media':>8} {'mediana':>8} {'p95':>8} {'p99':>8} "
        f"{'pior':>8} {'fps@p95':>8} {'>16ms':>8} {'>18.2ms':>8}",
    ]
    for chave in ("pan", "zoom", "juntos"):
        linhas.append(_linha(chave, relatorio["mediana"][chave]))
    linhas.append("")
    for chave in ("pan", "zoom", "juntos"):
        fps = relatorio["mediana"][chave]["fps_p95"]
        linhas.append(f"  {chave:<8} {relatorio['veredito'][chave]:<8} ({fps:.1f} fps @ p95)")
    por_execucao = ", ".join(
        f"{corrida['juntos']['fps_p95']:.1f}" for corrida in relatorio["execucoes"]
    )
    linhas.append(f"  fps@p95 (juntos) por execucao: {por_execucao}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tempo de quadro do pan/zoom (SPEC 11.3).")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pagina", type=int, default=41, help="base 1")
    parser.add_argument("--dpi", type=int, default=DPI_DA_MEDICAO)
    parser.add_argument("--largura", type=int, default=1280)
    parser.add_argument("--altura", type=int, default=800)
    parser.add_argument("--execucoes", type=int, default=EXECUCOES)
    parser.add_argument("--quadros-de-pan", type=int, default=QUADROS_DE_PAN)
    parser.add_argument("--quadros-de-zoom", type=int, default=QUADROS_DE_ZOOM)
    parser.add_argument(
        "--saida",
        type=Path,
        required=True,
        # **Sem padrão, e isto é um conserto de higiene** (F9-C12, item 16 do ciclo 11). O
        # padrão era `benchmarks/reports/ui/` -- a pasta do construtor --, e o crítico do
        # ciclo 11 rodou uma sabotagem sem `--saida`: o JSON foi gravar na pasta que ele não
        # pode tocar, e ele teve de movê-lo à mão. Um padrão que escreve na pasta de outro
        # agente é uma armadilha; quem roda um portão diz onde quer o relatório.
        help="onde gravar o relatorio. Obrigatorio: este portao nao escolhe pasta por voce.",
    )
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    args = parser.parse_args(argv)

    if args.execucoes < EXECUCOES:
        # Não é conselho: a carta dos críticos (§6) diz que menos de três execuções não conta,
        # e um relatório gravado com duas seria uma medição que já nasce reprovada.
        print(
            f"! {args.execucoes} execucoes: a carta dos criticos exige no minimo {EXECUCOES}.",
            file=sys.stderr,
        )

    relatorio = medir(
        args.pdf,
        pagina=max(0, args.pagina - 1),
        dpi=args.dpi,
        largura=args.largura,
        altura=args.altura,
        execucoes=args.execucoes,
        quadros_de_pan=args.quadros_de_pan,
        quadros_de_zoom=args.quadros_de_zoom,
        caminho_do_tronco=args.tronco,
    )
    args.saida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"fps_{marca}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")

    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"]["juntos"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
