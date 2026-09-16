"""Fotografa a janela do tronco: cada aba, cada pele, cada tamanho.

Roda com o venv do tronco (que tem PyQt6) e escreve em `benchmarks/reports/ui/`:

    QT_QPA_PLATFORM=offscreen \
    PYTHONPATH=C:/Python-Chess2/ChessVisionOFF_Puro/src \
    <trunk>/.venv/Scripts/python.exe -m caissa.ui.audit.capture --saida <dir> --marca antes

**Redimensiona depois do `show()`, e é o item.** `JanelaPrincipal.showEvent` restaura a
geometria da sessão anterior; um `resize` antes do `show` é sobrescrito em silêncio e a
auditoria mede um tamanho que ninguém pediu.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` so existe no 3.11 e o venv do tronco -- onde o PyQt6 mora -- e 3.10.

Escrito como `timezone(timedelta(0))` e nao como `timezone.utc` pela mesma razao de
`audit/contraste.py`: o `ruff --fix` desta suite tem alvo py311 e reescreveria o alias
para o `datetime.UTC` que morre no 3.10."""

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

TAMANHOS: tuple[tuple[int, int], ...] = (
    (1280, 800),
    (1366, 768),
    (1920, 1080),
    (3840, 2160),
)
"""Os quatro tamanhos que a auditoria fotografa: 6 abas × 3 peles × 4 tamanhos = **72 capturas**.

O menor comum, **1366×768** (a tela sobre a qual o item 4 foi escrito), o de trabalho, e o **4K**.

**O 4K é a metade da carta §3.2 que oito ciclos não rodaram** (F9-C9 §1, critério 4). O crítico do
ciclo 9 abriu a janela a 2560 e a 3840 com um instrumento próprio e mediu o que ninguém tinha
medido: o painel Resultado **melhora** quando a tela cresce (ocupação 73,1 % → 87,9 % → 89,4 %) e
o da Estudo piora, de 281,5 kpx de vazio a 1920 para **1 569,6 kpx a 3840**. Um número desses não
podia depender de um instrumento fora do arnês: agora ele sai da mesma passada que as outras."""

PELES: tuple[tuple[str, str], ...] = (
    ("classica", "claro"),
    ("foco", "escuro"),
    ("fita", "fita"),
)
"""Pele do tronco -> como ela se chama no nome do arquivo.

**Eram duas, e o produto oferece três** -- e essa foi a reprovação do ciclo 9. `ui/pele.PELES`
registra três e `Ver ▸ Aparência` lista as três; esta tupla listava duas, e por isso **nenhum
instrumento visual desta frente jamais fotografou a `fita`**. O defeito que morava lá (o ícone
novo desenhado ao lado do glifo velho, em seis botões e seis abas) sobreviveu a oito ciclos de
captura por essa única razão. `provar_as_peles` cobre a mesma lista.

**O rótulo do arquivo é o nome que distingue, e não o tema.** `claro` e `escuro` ficam onde estão
porque oito ciclos de medida os usam e trocá-los tornaria as séries incomparáveis; a terceira
entra como `fita`. O cromo da `fita` é **claro** -- o que a S-227 propõe é agrupamento nomeado, e
não cromo escuro --, e é por isso que `fita` não podia se chamar `claro`: dois arquivos com o
mesmo nome, e o segundo apagaria o primeiro em silêncio."""

_CONFERIR = {nome for nome, _ in PELES}
"""Só para a asserção de baixo ser legível.

Ver `tests/unit/ui/test_medicao.py::test_a_captura_cobre_toda_pele_registrada`, que é o nome que
o teste **tem** -- esta linha citava `test_capture_cobre_todas_as_peles`, que não existe (F9-C16;
a mesma varredura que achou o teste inexistente de `contraste.HERANCA`)."""

PASTA_DE_FONTES = r"C:\Windows\Fonts"
"""**Sem isto a captura mede tofu, e a medição mente** (achado da auditoria F9).

`QT_QPA_PLATFORM=offscreen` no Windows sobe com **zero** famílias de fonte: o
`QFontDatabase` fica vazio, todo glifo vira caixa e a métrica de texto passa a ser a da
fonte de reserva. "Resultado" mede 117 px sem esta variável e 52 px com ela -- 2,25x. Uma
captura sem fontes não mostra a janela, e um *teste de layout* sem fontes afirma larguras
que não existem em nenhuma máquina real."""


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def impor_a_fonte_do_produto(aplicacao: object) -> dict[str, str]:
    """Faz a captura medir a **família que o usuário vê**, e devolve a prova de que mediu.

    **O defeito, medido pelo crítico do ciclo 5 e reproduzido aqui.** Com
    `QT_QPA_PLATFORM=offscreen`, `QApplication.font().family()` é `"Sans Serif"` -- um nome
    genérico que o Qt resolve, nesta máquina, para **`Alef`**, uma família hebraica instalada
    junto com alguma coisa. Na plataforma real (`windows`) o mesmo caminho dá **`Segoe UI`**.
    As duas não medem igual:

    | amostra | Alef | Segoe UI |
    |---|---|---|
    | `Copiar headers para todos` (CORPO) | 143,00 px | 138,00 px |
    | a frase do estado vazio da aba Texto | 653,00 px | 625,00 px |
    | altura de linha de `TITULO` | 22 px | 21 px |

    A direção é conservadora para "nada está cortado" -- o texto real é mais estreito que o
    medido --, e por isso o defeito não bloqueou. Mas o critério de **tipografia** era julgado
    sobre imagens numa fonte que o usuário nunca vê: o eixo de peso 600 do papel `ACAO` rende
    **+27 % a +37 % de tinta** em Alef e **+5,4 % a +13,6 %** em Segoe UI. A prancha exagerava
    o degrau por um fator de três.

    **A família não é inventada aqui: ela é a que o produto declara** em
    `qt/tema.FAMILIA_DE_RESERVA`, que é a mesma de `ui/theme.py` e a que a plataforma real
    entrega. Um nome cravado no arnês seria a mesma família de defeito que o arnês veio corrigir
    -- um instrumento afirmando o que o artefato não contém.

    Devolve o manifesto `{pedida, resolvida, plataforma, ...}`, que o chamador imprime e grava:
    o `docstring` deste módulo já falava do tofu, e ele consertou o tofu **sem conferir a
    família**. Agora a captura afirma a família que usou.
    """
    from PyQt6.QtGui import QFont, QFontDatabase, QFontInfo

    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.ui import tipografia

    familia = tema.FAMILIA_DE_RESERVA[0]
    disponiveis = set(QFontDatabase.families())
    antes = QFontInfo(aplicacao.font()).family()  # type: ignore[attr-defined]
    if familia in disponiveis:
        ponto = abs(int(aplicacao.font().pointSize())) or tipografia.BASE_DE_REFERENCIA  # type: ignore[attr-defined]
        aplicacao.setFont(QFont(familia, ponto))  # type: ignore[attr-defined]
    resolvida = QFontInfo(aplicacao.font()).family()  # type: ignore[attr-defined]
    return {
        "plataforma": str(aplicacao.platformName()),  # type: ignore[attr-defined]
        "familia_do_produto": familia,
        "familia_antes": antes,
        "familia_resolvida": resolvida,
        "confere": "sim" if resolvida == familia else "NAO",
    }


PAGINA_DA_AUDITORIA = 120
"""A página do livro que as 36 capturas mostram. **Zero-based**: é a "118" impressa.

**As capturas herdavam a sessão anterior, e por isso não eram comparáveis entre ciclos**
(F9-C6). `JanelaPrincipal.showEvent` restaura a geometria **e a vista** da última sessão: as 36
do ciclo 4 saíram na página 121 a 67 % de zoom e as primeiras deste ciclo saíram na **289**
(a contracapa, uma foto de couro) a 28 %. Nenhuma medida de composição do visor sobrevive a
isso -- o `medidas_c3.py pagina` do crítico procura o retângulo **sépia** de uma página
digitalizada, e uma contracapa de couro não é sépia.

Uma página de texto com dois diagramas é o que a auditoria quer olhar, e ela tem de ser a mesma
todo ciclo. Fixá-la aqui é o que faz "recapture as 36" produzir imagens comparáveis com as do
ciclo passado em vez de duas amostras de estados de sessão diferentes."""


ENQUADRAMENTO_DA_AUDITORIA = "enquadramento_largura"
"""O enquadramento em que as 36 são fotografadas: **ajustar à largura**.

É o que o ciclo 4 usou, e é a régua com que o item 8 do §7 do ciclo 3 foi fechado -- *"o
retângulo sépia da página tem 366 px de largura a 1280, a 1366 e a 1920"*, contra os
**520 / 557 / 800** de depois. Fotografar em "ajustar à página" mediria uma altura constante e
uma largura menor, e a comparação com os dois ciclos anteriores viraria uma regressão
aparente que é só troca de modo. O valor é o literal de `ui/viewport.ENQUADRAMENTO_LARGURA`,
conferido contra ele em `_fixar_a_vista`."""


FRACAO_DO_DIVISOR = 0.566
"""Onde o divisor fica nas 36 capturas -- **declarado**, e não o que o disco disser.

**0,566, e o número foi buscado e não escolhido**: é a fração que reproduz o painel de
**1050 px** com que as 36 capturas do ciclo 6 foram medidas (`c5_vazios.py` sobre
`c6_claro_1920x1080_revisao.png`). Fixá-la é o que faz o item 6 (vazio de painel), o item 7
(ocupação) e o item 8 (largura da coluna "Motivo") deste ciclo comparáveis com os de lá -- e o
que os torna comparáveis com os do próximo. Ver `_fixar_o_divisor`."""


def aguardar_a_folha(janela_ou_painel: Any, limite_ms: int = 15_000) -> bool:
    """Espera a rasterização ao fundo do tronco entregar a folha (OCR_UI passo 15).

    Desde o passo 15 `abrir_pdf` e `ir_para_pagina` voltam antes de a página estar na tela --
    a rasterização corre num processo de trabalho e chega por sinal. Todo arnês que fotografa,
    conta ou mede **a folha** tem de esperar por ela; este é o único lugar em que se espera, e
    ele aceita a janela ou o painel. Num tronco anterior ao passo (sem `aguardar_pagina`) não
    há o que esperar e devolve `True`.
    """
    painel = getattr(janela_ou_painel, "pdf", janela_ou_painel)
    aguardar = getattr(painel, "aguardar_pagina", None)
    if aguardar is None:
        return True
    return bool(aguardar(limite_ms))


@dataclass(frozen=True)
class AreaDeTrabalho:
    """Um lugar onde se trabalha na janela do tronco: aba do acervo ou modo da aba `Livro`."""

    nome: str
    """O nome sem contagem (`Resultado`, `Dataset`), como `ui/abas.nome_base` o devolve."""
    mostrar: Callable[[], object]
    """Traz a área para a frente -- a aba, ou a aba `Livro` no modo certo."""
    widget: Callable[[], Any]
    """O painel da área, para quem mede a subárvore dele e não a janela inteira."""


def areas_de_trabalho(janela: Any) -> list[AreaDeTrabalho]:
    """Cada lugar onde se trabalha, uma vez, na ordem em que a janela os lista.

    **Desde o passo 17 da OCR_UI (tarefa 3) as quatro abas do diagrama são modos da aba `Livro`**
    (`qt/areas_de_trabalho.py` no tronco): um laço `for indice in range(janela.abas.count())`
    passou a ver três abas onde há sete ou oito áreas, e um portão que só andasse pelas abas
    mediria o modo Resultado quatro vezes e Estudo, Revisão e Texto nenhuma. Este é o **único**
    laço do arnês sobre as áreas -- teclado, texto pintado, execução e captura andam por ele -- e
    ele pergunta à janela (`areas`, `mostrar_area`), sem saber se um nome é aba ou modo. Num
    tronco anterior ao passo, sem esses métodos, cada aba é uma área, como sempre foi.
    """
    abas = janela.abas
    listar = getattr(abas, "areas", None)
    mostrar_area = getattr(abas, "mostrar_area", None)
    if listar is None or mostrar_area is None:
        return [
            AreaDeTrabalho(
                nome=abas.tabText(indice).split(" (")[0].replace("&", "").strip(),
                mostrar=lambda i=indice: abas.setCurrentIndex(i),
                widget=lambda i=indice: abas.widget(i),
            )
            for indice in range(abas.count())
        ]

    def widget_de(nome: str) -> Any:
        modo = abas.principal.widget_do_modo(nome)
        if modo is not None:
            return modo
        indice = abas.indice_da_aba(nome)
        return abas.widget(indice) if indice is not None else None

    return [
        AreaDeTrabalho(
            nome=nome,
            mostrar=lambda n=nome: mostrar_area(n),
            widget=lambda n=nome: widget_de(n),
        )
        for nome in listar()
    ]


def estado_de_medicao(pasta: Path) -> Path:
    """Escreve um estado de sessão **próprio** naquela pasta e devolve o caminho dele.

    **Todo instrumento que abre `JanelaPrincipal` tem de passar por aqui** (F9-C10). Sem
    `caminho_do_estado=`, a janela lê e **reescreve** o estado de sessão do tronco ao sair --
    foi o que o ciclo 8 mediu como o oitavo instrumento cego, e é o arquivo que o crítico do
    ciclo 9 teve de envenenar e restaurar à mão para testar este arnês.

    **O arquivo é o `data/janela.json`, e dizer "o `app_tkinter_state.json`" era o erro da
    certidão do ciclo 10** (F9-C12). O estado da janela **Qt** é o que `qt/janela.py` declara em
    `CAMINHO_DO_ESTADO`: ele guarda `last_pdf`, `last_page`, `pdf_zoom`, `pdf_enquadramento`,
    `board_zoom` e `pdf_history`. O do Tk é outro arquivo, de um frontend que foi cortado em
    2026-08-31. A certidão de higiene do ciclo 10 conferiu o `mtime` do arquivo errado e por
    isso não viu que `caissa.ui.audit.bloqueio` -- as duas únicas construções sem
    `caminho_do_estado` no arnês inteiro -- vinha reescrevendo a sessão de quem o rodava.
    Quem cobra isso agora não é uma frase num relatório: é
    `tests/unit/ui/test_medicao.py::TestNenhumPortaoEscreveNaSessaoDeQuemORoda`, que lê os
    módulos do arnês e reprova a construção que não redirecionar.

    Duas consequências, e as duas são defeito:

    * **a medição depende da sessão anterior.** `sash_fraction` decide a largura do painel
      esquerdo, e com ela a largura de todo `QLabel` que quebra linha -- ou seja, o instrumento
      de órfãs media parágrafos de medida diferente conforme quem tivesse aberto a janela antes;
    * **a medição estraga a sessão de quem roda o portão.** Sair de um portão mudando a aba, a
      página e a geometria do programa da pessoa é um efeito colateral que nenhum arnês pode ter.

    O conteúdo é o mesmo de `capturar_uma_pele`: versão e `FRACAO_DO_DIVISOR` declarada. Nada de
    PDF, página nem geometria -- o instrumento que precisa de um livro o abre por método.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / "capture_estado.json"
    alvo.write_text(
        json.dumps({"version": 6, "sash_fraction": FRACAO_DO_DIVISOR}), encoding="utf-8"
    )
    return alvo


def _fixar_o_divisor(janela: Any) -> None:
    """Põe o divisor em `FRACAO_DO_DIVISOR` da largura. Nunca levanta.

    O `QSplitter` grampeia pelo mínimo de cada lado, então a fração pedida e a obtida podem
    divergir numa janela estreita -- e é por isso que quem lê o número o lê da captura, e não
    daqui.
    """
    divisor = getattr(janela, "divisor", None)
    if divisor is None:
        return
    try:
        # **A largura do widget, e não a soma das alças.** Logo depois de um `resize` a soma
        # ainda é a da geometria anterior, e pedir a fração dela punha o divisor no lugar da
        # largura antiga -- medido: 879 px em vez dos 979 pedidos, numa janela de 1920.
        largura = max(divisor.width(), sum(divisor.sizes()))
        if largura <= 0:
            return
        esquerda = max(1, round(largura * FRACAO_DO_DIVISOR))
        divisor.setSizes([esquerda, max(1, largura - esquerda)])
    except Exception:  # noqa: BLE001 - fixar a vista não pode custar a captura
        return


def _fixar_a_vista(janela: object) -> None:
    """Põe o visor na página e no enquadramento da auditoria. Falha em silêncio se não der.

    Silenciosa de propósito: uma captura numa página inesperada continua sendo uma captura, e
    derrubar as 36 por causa da vista seria trocar um defeito de comparabilidade por um de
    disponibilidade. Quem quiser conferir tem o manifesto e a própria imagem.
    """
    from chess_diagram_ocr.ui import viewport

    if ENQUADRAMENTO_DA_AUDITORIA not in viewport.ENQUADRAMENTOS:  # pragma: no cover - guarda
        raise KeyError(
            f"enquadramento {ENQUADRAMENTO_DA_AUDITORIA!r} não existe mais em "
            f"ui/viewport.ENQUADRAMENTOS: {viewport.ENQUADRAMENTOS}"
        )
    painel = getattr(janela, "pdf", None)
    if painel is None:
        return
    try:
        painel.ir_para_pagina(PAGINA_DA_AUDITORIA)
        aguardar_a_folha(painel)
        painel.definir_enquadramento(ENQUADRAMENTO_DA_AUDITORIA)
    except Exception as exc:  # noqa: BLE001 - ver a docstring
        print(f"  (a vista não foi fixada: {exc})", file=sys.stderr)


def capturar(
    saida: Path,
    *,
    marca: str,
    pdf: Path | None = None,
    caminho_do_tronco: Path = TRONCO,
    peles: tuple[tuple[str, str], ...] = PELES,
) -> list[Path]:
    """Grava um PNG por (pele, tamanho, aba), **uma pele por processo**, e devolve o que gravou.

    **Um processo por pele, e isso foi medido e não escolhido** (F9-C10). Com as três peles no
    mesmo processo a terceira `JanelaPrincipal` aborta o interpretador -- a anterior morre por
    coleta de lixo do Python com `DeferredDelete` ainda pendentes no Qt. É a mesma forma que
    `audit/teclado.auditar_as_peles` encontrou, e a mesma resposta; e ela tem o efeito colateral
    certo: nenhuma pele herda o cache de ícone, o tema aplicado nem os seguidores de comando da
    anterior.

    **E uma pele que não fotografa levanta.** Um subprocesso que morre sem escrever PNG nenhum
    devolveria "36 capturas" em vez de 72, e um arnês que perde uma pele em silêncio é a
    reprovação do ciclo 9 de novo.
    """
    _preparar(caminho_do_tronco)
    saida.mkdir(parents=True, exist_ok=True)
    gravados: list[Path] = []
    for nome_da_pele, rotulo in peles:
        antes = set(saida.glob(f"{marca}_{rotulo}_*.png"))
        ambiente = dict(os.environ)
        ambiente["CVOFF_SKIN"] = nome_da_pele
        argumentos = [
            sys.executable,
            "-m",
            "caissa.ui.audit.capture",
            "--pele",
            nome_da_pele,
            "--saida",
            str(saida),
            "--marca",
            marca,
            "--tronco",
            str(caminho_do_tronco),
        ]
        if pdf is not None:
            argumentos += ["--pdf", str(pdf)]
        subprocess.run(argumentos, env=ambiente, check=False)  # noqa: S603 - argv nosso
        depois = sorted(set(saida.glob(f"{marca}_{rotulo}_*.png")) - antes)
        if not depois:
            raise RuntimeError(
                f"a pele {nome_da_pele!r} nao gravou captura nenhuma em {saida}: o subprocesso "
                f"morreu antes de fotografar."
            )
        gravados.extend(depois)
    return gravados


def capturar_uma_pele(
    saida: Path,
    *,
    marca: str,
    nome_da_pele: str,
    rotulo: str,
    pdf: Path | None = None,
    caminho_do_tronco: Path = TRONCO,
) -> list[Path]:
    """Grava um PNG por (tamanho, aba) para **uma** pele. É o que cada subprocesso faz."""
    _preparar(caminho_do_tronco)
    saida.mkdir(parents=True, exist_ok=True)
    gravados: list[Path] = []

    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from PyQt6.QtWidgets import QApplication

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    # **Antes de qualquer janela**, porque `tema.fonte_base()` lê `QApplication.font()` e a
    # folha de estilo é montada na construção do primeiro painel.
    manifesto = impor_a_fonte_do_produto(aplicacao)
    print(
        f"  fonte: plataforma={manifesto['plataforma']} "
        f"pedida={manifesto['familia_do_produto']!r} "
        f"antes={manifesto['familia_antes']!r} "
        f"resolvida={manifesto['familia_resolvida']!r} confere={manifesto['confere']}"
    )
    if manifesto["confere"] != "sim":
        print(
            "  ! a captura NAO esta na fonte do produto: toda medida de tipo abaixo e de outra "
            "familia. Ver capture.impor_a_fonte_do_produto.",
            file=sys.stderr,
        )
    marca_do_tempo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    (saida / f"capture_manifesto_{marca_do_tempo}.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    os.environ["CVOFF_SKIN"] = nome_da_pele
    tema = rotulo
    # A janela é remontada por pele: a folha de estilo é da aplicação e alcança os
    # widgets criados depois dela, então trocar a pele com a janela viva não é o mesmo
    # caminho que abrir nela -- e é abrir nela que a auditoria precisa medir.
    from chess_diagram_ocr.qt.janela import JanelaPrincipal

    # **Estado próprio, e o divisor num número declarado** (F9-C8). As 36 saíam com o
    # `sash_fraction` que estivesse no `data/app_tkinter_state.json` da máquina -- e toda
    # janela aberta e fechada por qualquer instrumento reescreve esse arquivo ao sair. Medido
    # nesta sessão: o divisor foi de **x=980** nas capturas do ciclo 6 para **x=875** nas do
    # ciclo 8 sem que uma linha de leiaute mudasse, porque a fração guardada tinha caído de
    # 0,51 para 0,3755. Todo número que fala do **painel** -- item 6 (vazio de painel), item 7
    # (ocupação) e item 8 (largura da coluna "Motivo") -- depende dessa posição, e por isso
    # nenhum deles era comparável entre ciclos.
    estado = estado_de_medicao(saida)
    janela = JanelaPrincipal(caminho_do_estado=estado)
    janela.show()
    aplicacao.processEvents()
    _fixar_o_divisor(janela)
    if pdf is not None and pdf.exists():
        try:
            janela.abrir_pdf(pdf)
            aguardar_a_folha(janela)
            _fixar_a_vista(janela)
        except Exception as exc:
            print(f"  (livro {pdf.name} não abriu: {exc})", file=sys.stderr)
    for _ in range(3):
        aplicacao.processEvents()

    for largura, altura in TAMANHOS:
        janela.resize(largura, altura)
        for _ in range(8):
            aplicacao.processEvents()
        # De novo a cada largura: o `QSplitter` reparte o que sobra pelos fatores de
        # esticamento (2:3), então a mesma fração guardada dá divisores diferentes conforme a
        # janela cresce -- e as três larguras deixariam de ser a mesma janela em três tamanhos.
        _fixar_o_divisor(janela)
        for _ in range(2):
            aplicacao.processEvents()
        if (janela.width(), janela.height()) != (largura, altura):
            # **A recusa é dado, não ruído.** Uma janela que não encolhe até o tamanho
            # pedido não cabe na tela de quem pediu, e o número exato é o defeito.
            print(
                f"  ! {tema} pediu {largura}x{altura}, ficou "
                f"{janela.width()}x{janela.height()} (mínimo "
                f"{janela.minimumSizeHint().width()}x{janela.minimumSizeHint().height()})"
            )
        for area in areas_de_trabalho(janela):
            area.mostrar()
            for _ in range(4):
                aplicacao.processEvents()
            nome_base = area.nome.lower()
            nome_base = (
                nome_base.replace("ã", "a")
                .replace("é", "e")
                .replace("ç", "c")
                .replace("ó", "o")
            )
            alvo = saida / f"{marca}_{tema}_{largura}x{altura}_{nome_base}.png"
            janela.grab().save(str(alvo))
            gravados.append(alvo)
            print(f"  {alvo.name}")
    janela.close()
    janela.deleteLater()
    aplicacao.processEvents()

    return gravados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--marca", default="antes", help="prefixo: antes | depois")
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument(
        "--pele",
        default="",
        help="fotografa UMA pele. Sem isto, o arnes percorre todas as de PELES.",
    )
    args = parser.parse_args(argv)
    if args.pele:
        rotulo = dict(PELES).get(args.pele)
        if rotulo is None:
            raise SystemExit(f"pele {args.pele!r} nao esta em capture.PELES: {dict(PELES)}")
        gravados = capturar_uma_pele(
            args.saida,
            marca=args.marca,
            nome_da_pele=args.pele,
            rotulo=rotulo,
            pdf=args.pdf,
            caminho_do_tronco=args.tronco,
        )
        print(f"{len(gravados)} capturas da pele {args.pele} em {args.saida}")
        return 0
    gravados = capturar(args.saida, marca=args.marca, pdf=args.pdf, caminho_do_tronco=args.tronco)
    print(f"{len(gravados)} capturas em {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
