"""Mede quanto tempo cada operação segura a thread da interface (SPEC §11.3: nunca > 16 ms).

**O portão é uma afirmação sobre o laço de eventos, e por isso a medida é um relógio dentro
dele.** Cronometrar a operação por fora responde "quanto ela demorou", que é outra pergunta:
uma exportação de dez minutos numa thread de trabalho não viola nada, e um `load_rows` de 400
ms na thread da janela viola vinte e cinco vezes. O que o §11.3 proíbe é a janela parar de
responder -- então o instrumento tem de estar onde a resposta acontece.

**O instrumento são duas peças, e cada uma sabe algo que a outra não pode saber.**

1. **O pulso** é um `QTimer` de `INTERVALO_MS` na thread da interface. Ele não consegue disparar
   enquanto ela está ocupada, e é exatamente isso que o torna útil: o **vão** entre dois
   disparos, menos o intervalo pedido, é o tempo em que ninguém atendeu o laço de eventos.
   Este número é exato mesmo quando o bloqueio está dentro de código C, porque é relógio de
   parede e não introspecção.
2. **O amostrador** é uma thread comum que vigia o pulso e, quando ele passa do piso, fotografa
   a pilha Python da thread da interface. Ele existe porque um número sem nome não é acionável:
   "algo travou 412 ms" manda alguém procurar; "412 ms em `render_pdf_page` <- `desenhar_pagina`
   <- `load_pdf`" manda alguém consertar.

**O limite honesto do amostrador, dito antes de alguém descobrir.** Ele precisa da GIL para ler
`sys._current_frames()`. Uma extensão C que segure a GIL o congela junto com a thread da
interface, e a foto sai do instante em que a GIL voltou -- perto do fim do travamento, não do
começo. A **duração** continua correta (é o vão do pulso); a **pilha** é a melhor aproximação
possível de dentro do processo. Onde a pilha for duvidosa, o nome da operação vem do
`medindo(...)` que a envolveu, e esse não depende de amostragem nenhuma.

**A aritmética não importa Qt**, e é ela que os testes da suíte afirmam -- o venv da suíte tem
PySide6, não PyQt6. O Qt só aparece dentro de `Vigia` e das funções que dirigem a janela.

Uso:

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
    PYTHONPATH=C:/Python-Chess2/ChessVisionOFF_Puro/src \
    <tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.bloqueio --pdf "<livro>.pdf"
"""

from __future__ import annotations

import argparse
import cProfile
import itertools
import json
import os
import pstats
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

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

ORCAMENTO_MS = 16.0
"""O piso do SPEC §11.3. Um quadro a 60 Hz -- acima disto a janela pulou um quadro."""

INTERVALO_MS = 4
"""Intervalo do pulso.

Quatro milissegundos, e não um: o pulso tem de ser bem menor que o orçamento de 16 ms para que
um travamento de 17 ms seja visível como vão, e grande o bastante para que o próprio pulso não
seja a carga. A 4 ms são 250 disparos por segundo de uma função de três linhas.

Também não pode ser 16: um pulso com o mesmo período do orçamento não distingue "atrasou" de
"chegou na hora com jitter", e o portão passaria a depender do relógio do sistema."""

AMOSTRAGEM_MS = 2.0
"""De quanto em quanto tempo o amostrador confere o pulso. Metade do pulso, pela mesma razão."""

MINIMO_PARA_UM_VAO = 2
"""Instantes mínimos para haver um vão. Menos que dois não define atraso nenhum -- e é
diferente de "não travou": quem lê `Resumo.pulsos` vê que não houve medição."""

PROFUNDIDADE_DA_PILHA = 12
"""Quantos quadros da pilha guardar. Doze alcança do `main` até dentro do PyMuPDF sem virar um
despejo que ninguém lê -- e o topo, que é o que interessa, nunca cai fora."""


# ------------------------------------------------------------- a aritmética (sem Qt algum)


@dataclass(frozen=True)
class Travamento:
    """Um intervalo em que a thread da interface não atendeu o laço de eventos."""

    duracao_ms: float
    """Vão entre dois pulsos **menos** o intervalo pedido: o tempo em que ninguém atendeu."""

    quando_s: float
    """`perf_counter` do pulso que fechou o travamento. Serve para ordenar, não para datar."""

    operacao: str = ""
    """O nome que `medindo(...)` deu à operação em curso. Vazio fora de um contexto medido."""

    pilha: tuple[str, ...] = ()
    """A foto da pilha Python da thread da interface, se o amostrador conseguiu tirar uma."""

    def acima_de(self, piso_ms: float = ORCAMENTO_MS) -> bool:
        return self.duracao_ms > piso_ms


@dataclass(frozen=True)
class Resumo:
    """O veredito de uma medição: quanto travou, quantas vezes e qual foi a pior."""

    operacao: str
    pulsos: int
    travamentos: int
    """Quantos vãos passaram do piso."""

    pior_ms: float
    total_bloqueado_ms: float
    """Soma de **todos** os atrasos, inclusive os abaixo do piso.

    Inclusive os pequenos porque é essa soma que responde "a janela ficou fluida?": trinta
    atrasos de 10 ms não violam o portão uma única vez e ainda assim são 300 ms de janela
    pastosa. O portão é o `pior_ms`; este número é o que o crítico usa para não ser enganado
    por uma operação que fatiou o bloqueio em pedaços de quinze milissegundos."""

    piso_ms: float = ORCAMENTO_MS

    def passou(self) -> bool:
        return self.pior_ms <= self.piso_ms


def atrasos(marcas_s: Sequence[float], intervalo_ms: float = INTERVALO_MS) -> list[float]:
    """Os atrasos, em ms, de uma sequência de instantes de disparo do pulso.

    Cada atraso é `vão - intervalo`, com piso em zero. O piso existe porque um disparo que chega
    **antes** da hora (o Qt tem tolerância de coarse timer, e o relógio do Windows granula em
    ~0,5 ms) produziria atraso negativo, e um negativo somado a um positivo esconderia metade de
    um travamento real.

    Menos de dois instantes não define vão nenhum e devolve lista vazia -- e é diferente de "não
    travou": quem lê `Resumo.pulsos` vê que não houve medição.
    """
    # **A cópia é obrigatória, e a falta dela era um defeito de verdade.** `marcas_s` costuma ser
    # a lista viva do `Vigia`, e o `QTimer` acrescenta um instante a ela **durante** esta função:
    # `zip` consome o primeiro argumento preguiçosamente e o segundo é uma fatia já congelada, de
    # modo que os dois divergem no meio da iteração. Com `strict=True` isso levantava
    # `ValueError: zip() argument 2 is shorter than argument 1` -- e derrubava a medição inteira
    # no meio da terceira execução, que é o pior momento possível para um arnês falhar.
    marcas = list(marcas_s)
    if len(marcas) < MINIMO_PARA_UM_VAO:
        return []
    intervalo_s = float(intervalo_ms) / 1000.0
    return [
        max(0.0, (depois - antes - intervalo_s) * 1000.0)
        for antes, depois in itertools.pairwise(marcas)
    ]


def travamentos_de(
    marcas_s: Sequence[float],
    *,
    intervalo_ms: float = INTERVALO_MS,
    piso_ms: float = ORCAMENTO_MS,
    operacao: str = "",
) -> list[Travamento]:
    """Só os vãos que passaram do piso, já como `Travamento` -- sem pilha, que é do amostrador."""
    marcas = list(marcas_s)
    return [
        Travamento(duracao_ms=atraso, quando_s=marcas[indice + 1], operacao=operacao)
        for indice, atraso in enumerate(atrasos(marcas, intervalo_ms))
        if atraso > piso_ms
    ]


def resumir(
    atrasos_ms: Sequence[float],
    *,
    operacao: str = "",
    piso_ms: float = ORCAMENTO_MS,
    pulsos: int | None = None,
) -> Resumo:
    """O resumo de uma lista de atrasos. Lista vazia é `pior_ms = 0` e `passou()` verdadeiro.

    Vazio passa de propósito: uma operação instantânea não tem como violar um piso de tempo, e
    inventar uma reprovação por ausência de amostra tornaria o portão inútil justamente nos
    casos em que ele deveria calar. Quem precisa distinguir "não travou" de "não mediu" lê
    `pulsos`.
    """
    return Resumo(
        operacao=operacao,
        pulsos=len(atrasos_ms) + 1 if pulsos is None else pulsos,
        travamentos=sum(1 for atraso in atrasos_ms if atraso > piso_ms),
        pior_ms=max(atrasos_ms, default=0.0),
        total_bloqueado_ms=sum(atrasos_ms),
        piso_ms=piso_ms,
    )


def piores(travamentos: Sequence[Travamento], quantos: int = 5) -> list[Travamento]:
    """Os travamentos mais longos primeiro. É a lista que vira "quem consertar primeiro"."""
    return sorted(travamentos, key=lambda item: item.duracao_ms, reverse=True)[:quantos]


# ---------------------------------------------------------- a atribuição (também sem Qt algum)


@dataclass(frozen=True)
class Atribuicao:
    """Quanto tempo **próprio** uma família de arquivos gastou dentro de uma operação."""

    familia: str
    ms: float
    fracao: float
    """Da soma dos tempos próprios da operação, entre 0,0 e 1,0."""


FAMILIA_DESTA_FRENTE = ("qt/ (esta frente)", "ui/ (esta frente)")
"""As duas famílias cujo custo é da F9. Existem como constante porque `viola_por_conta_propria`
pergunta por elas, e uma string repetida em dois lugares é a que muda num só."""


def familia(caminho: str, nome: str = "") -> str:
    """A que família de código pertence esta função. É o eixo da atribuição.

    **Por que a classificação é do arnês e não do perfilador.** `cProfile` devolve tempo por
    função, e uma lista de duzentas funções não responde a pergunta que o ciclo 3 fez: *de quem é
    o resíduo?* O relatório do ciclo 2 escreveu "é `PyMuPDF` de verdade, e `pdf_io` não é desta
    frente" olhando **uma** foto de pilha, e a foto estava certa e a conclusão errada -- 30 % da
    virada eram 108.620 chamadas Python de `qt/`, pequenas demais para ganhar uma amostra e
    grandes demais para ignorar. Somar por família é o que faz esses 30 % aparecerem sozinhos.

    **`nome` não é opcional na prática, e a falta dele custou uma versão deste arnês.** Toda
    função C aparece no `cProfile` com o arquivo `~` e a linha 0 -- então classificar só pelo
    caminho jogava 94,7 % da virada num balde chamado "builtins" e escondia justamente o que se
    quer separar: `<built-in method pymupdf._mupdf.fz_run_display_list>` e `<built-in method
    nt.stat>` são a rasterização e o disco, e não "builtins". O nome da função C **diz** de qual
    biblioteca ela é, e é o único lugar onde essa informação existe.
    """
    limpo = caminho.replace("\\", "/")
    if limpo in ("~", "") or limpo.startswith("<"):
        return _familia_de_builtin(nome)
    if "fitz" in limpo or "mupdf" in limpo or "pymupdf" in limpo:
        return "PyMuPDF"
    if "/chess_diagram_ocr/qt/" in limpo:
        return FAMILIA_DESTA_FRENTE[0]
    if "/chess_diagram_ocr/ui/" in limpo:
        return FAMILIA_DESTA_FRENTE[1]
    if "pdf_io" in limpo:
        return "pdf_io (tronco)"
    if "/chess_diagram_ocr/" in limpo:
        return "tronco (outros)"
    if limpo.endswith(("pathlib.py", "ntpath.py", "posixpath.py", "genericpath.py")):
        return "pathlib/os (disco)"
    return "stdlib/terceiros"


PISTAS_DE_DISCO = (
    "method nt.",
    "method posix.",
    "method io.",
    "method _io.",
    "method builtins.open",
    "sqlite3.",
    "'sqlite3.connection'",
    "'sqlite3.cursor'",
)
"""O que, no nome de uma função C, a denuncia como toque de disco.

São os módulos por onde o `open`, o `stat` e o `listdir` do CPython saem para o sistema de
arquivos. Existem como tabela porque foi o disco -- e não a rasterização -- que respondeu por
71 % da abertura de livro no ciclo 3, e um balde chamado "builtins" não teria dito isso.

**O `sqlite3` entrou no ciclo 14, e a falta dele é a razão de a lista declarada ter dito quatro
onde o perfil dizia seis** (F9-C13, §5.6). `<built-in method _sqlite3.connect>` a 30,6 ms e
`<method '__exit__' of 'sqlite3.Connection'>` a 28,6 ms, os dois em
`painel_da_galeria.py:1106 _abrir_cache_de_posicoes`, caíam no balde `builtins (C)` -- e um
`connect` é abrir um arquivo, um `execute` é lê-lo e um `__exit__` é o `COMMIT` que o escreve.
Chamar isso de "builtins" é o mesmo erro que chamar `nt.stat` de builtin, um nome depois.

**Isto move tempo entre famílias publicadas**, e é o preço declarado: o que era `builtins (C)`
passa a ser `pathlib/os (disco)` na mesma medição. A partição continua sem contar ninguém duas
vezes; o que muda é o nome certo no balde certo."""


def _familia_de_builtin(nome: str) -> str:
    """A família de uma função C, pelo nome que o `cProfile` lhe dá. Ver `familia`."""
    agulha = nome.lower()
    if "mupdf" in agulha or "fitz" in agulha:
        return "PyMuPDF"
    if "pyqt" in agulha or "sip." in agulha:
        return "Qt (toolkit)"
    if any(pista in agulha for pista in PISTAS_DE_DISCO):
        return "pathlib/os (disco)"
    return "builtins (C)"


PISO_DA_LISTA_DE_DISCO = 0.05
"""Abaixo de quantos milissegundos um quadro de disco sai da **lista publicada** (F9-C14).

Ele não sai da medição -- o JSON traz todos --, sai da tabela do terminal. `pathlib` classifica
como disco porque é por ele que o `stat` e o `open` saem, mas montar um `Path` não toca disco: a
passada de uma aba traz doze quadros de `parse_parts` a 0,0 ms, e eles afogariam os dois
`sqlite3` de 30 ms que o item 8 do §7 do ciclo 13 mandou nomear. Cinquenta microssegundos é onde
o quadro deixa de ser aritmética de string."""

COBERTURA_MINIMA = 50.0
"""Abaixo de quantos por cento do pior travamento a atribuição deixa de descrever o evento.

**Cinquenta, e o número tem um caso** (F9-C7, §4.4c): a passada de `cProfile` da aba Dataset
reproduzia **1,05-1,41 ms de um congelamento medido de 74,5 ms** -- 1,9 % --, porque ela rodava
depois das três execuções medidas, com a aba **já mostrada e o CSV já lido**. O relatório
publicava as famílias daquele 1,4 ms sem dizer que elas não eram as do congelamento, e foi assim
que "o resto é PyMuPDF" cobriu 4 de 7 operações e errou na maior.

O piso é frouxo de propósito: a passada perfilada nunca reproduz 100 % (o `cProfile` muda o
tempo de tudo), e o que se quer é separar "viu a operação" de "viu outra coisa"."""


def atribuir(
    estatisticas: "Mapping[tuple[str, int, str], Sequence[Any]]", *, quantas_funcoes: int = 8
) -> dict[str, Any]:
    """Tempo **próprio** por família e as funções mais caras, a partir de `pstats.Stats.stats`.

    A entrada é o dicionário cru do `cProfile` -- `{(arquivo, linha, nome): (cc, nc, tt, ct,
    chamadores)}` --, e `tt` é o tempo próprio: o que a função gastou sem contar as que ela
    chamou. Somar `tt` por família dá uma partição do tempo perfilado que **não conta ninguém
    duas vezes**, e é por isso que a soma vale como atribuição e a soma de `ct` não valeria.

    Pura de propósito: o venv desta suíte não tem PyQt6, e é aqui que mora a aritmética que os
    testes afirmam contra casos calculados à mão.
    """
    por_familia: dict[str, float] = {}
    por_funcao: list[tuple[float, tuple[str, int, str]]] = []
    for chave, medidas in estatisticas.items():
        arquivo, linha, nome = chave
        proprio = float(medidas[2])
        qual = familia(arquivo, nome)
        por_familia[qual] = por_familia.get(qual, 0.0) + proprio
        por_funcao.append((proprio, chave))
    soma = sum(por_familia.values())
    familias = [
        Atribuicao(familia=nome, ms=valor * 1000.0, fracao=(valor / soma) if soma else 0.0)
        for nome, valor in sorted(por_familia.items(), key=lambda par: -par[1])
    ]
    caras = sorted(por_funcao, key=lambda par: (-par[0], par[1]))[:quantas_funcoes]
    return {
        "total_perfilado_ms": soma * 1000.0,
        "por_familia": [
            {"familia": item.familia, "ms": item.ms, "fracao": item.fracao} for item in familias
        ],
        "ms_desta_frente": sum(
            item.ms for item in familias if item.familia in FAMILIA_DESTA_FRENTE
        ),
        "fracao_desta_frente": sum(
            item.fracao for item in familias if item.familia in FAMILIA_DESTA_FRENTE
        ),
        "funcoes_mais_caras": [
            {
                "ms": ms * 1000.0,
                "quem": f"{Path(chave[0]).name}:{chave[1]} {chave[2]}",
                "disparada_por": quem_desta_frente_disparou(estatisticas, chave),
            }
            for ms, chave in caras
        ],
        # **A lista de E/S de disco deixou de ser prosa de relatório** (F9-C14, item 8 do §7 do
        # ciclo 13). Ela era escrita à mão no relatório do construtor, dizia **quatro** caminhos,
        # e o perfil do crítico nomeava **seis** -- as duas de `sqlite3` que `PISTAS_DE_DISCO`
        # não via. Uma lista escrita à mão sobre uma medição que o programa já tem é a forma de
        # errar que este arnês inteiro existe para não ter: agora ela sai da mesma passada.
        "e_s_de_disco": [
            {
                "ms": ms * 1000.0,
                "quem": f"{Path(chave[0]).name}:{chave[1]} {chave[2]}",
                "disparada_por": quem_desta_frente_disparou(estatisticas, chave),
            }
            for ms, chave in sorted(por_funcao, key=lambda par: (-par[0], par[1]))
            if familia(chave[0], chave[2]) == "pathlib/os (disco)" and ms > 0.0
        ],
    }


def quem_desta_frente_disparou(
    estatisticas: "Mapping[tuple[str, int, str], Sequence[Any]]",
    alvo: tuple[str, int, str],
    *,
    profundidade: int = 40,
) -> str:
    """O quadro de `qt/`/`ui/` mais próximo **acima** de `alvo` no grafo de chamadas.

    **Isto é a metade que faltava para a atribuição não repetir o erro do ciclo 2.** Somar tempo
    próprio por família responde *onde* o tempo foi gasto; ele foi gasto em `labels.py`, que é do
    tronco -- e foi exatamente esse recorte que autorizou a frase *"`pdf_io` não é desta frente"*.
    A pergunta que decide de quem é o conserto é outra: **quem disparou?** Aqui, quatro quadros de
    `qt/` disparavam 108.620 chamadas de `labels._clean` por virada de página.

    O quinto elemento da tupla do `cProfile` é o dicionário de chamadores, então o grafo já está
    na medição -- só não estava sendo lido. Vazio quando nada desta frente aparece acima: uma
    operação disparada de fora é uma resposta legítima, e é a que o ciclo 2 alegou sem checar.
    """
    vistos: set[tuple[str, int, str]] = {alvo}
    fila: list[tuple[tuple[str, int, str], int]] = [(alvo, 0)]
    while fila:
        chave, passos = fila.pop(0)
        if passos >= profundidade:
            continue
        medidas = estatisticas.get(chave)
        chamadores = medidas[4] if medidas is not None and len(medidas) > 4 else {}
        for quem in chamadores or {}:
            if quem in vistos:
                continue
            vistos.add(quem)
            if familia(quem[0], quem[2]) in FAMILIA_DESTA_FRENTE:
                return f"{Path(quem[0]).name}:{quem[1]} {quem[2]}"
            fila.append((quem, passos + 1))
    return ""


# --------------------------------------------------------------------- o vigia (Qt aqui, e só)


class Vigia:
    """O pulso e o amostrador, ligados enquanto durar a medição.

    **Não é um `QObject`.** O `QTimer` que ele cria é filho de ninguém e é parado no `desligar`;
    herdar de `QObject` só para hospedar um temporizador amarraria este objeto à ordem de
    destruição de widgets do Qt, e um vigia destruído junto com a janela mediria menos do que o
    fechamento dela custa -- que é justamente uma das operações a medir.
    """

    def __init__(
        self,
        *,
        intervalo_ms: int = INTERVALO_MS,
        piso_ms: float = ORCAMENTO_MS,
        amostrar: bool = True,
    ) -> None:
        self.intervalo_ms = int(intervalo_ms)
        self.piso_ms = float(piso_ms)
        self._amostrar = bool(amostrar)

        self._marcas: list[float] = []
        self._travamentos: list[Travamento] = []
        self._operacao = ""
        self._pulso = 0.0
        self._pilha_pendente: tuple[str, ...] = ()
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread_da_interface = threading.get_ident()
        self._amostrador: threading.Thread | None = None
        self._relogio: Any = None

    # --------------------------------------------------------------------------- ciclo de vida

    def ligar(self) -> Vigia:
        from PyQt6.QtCore import Qt, QTimer

        agora = time.perf_counter()
        self._pulso = agora
        self._marcas = [agora]
        self._relogio = QTimer()
        # `PreciseTimer` explícito: o padrão do Qt é o coarse, cuja tolerância de 5% num
        # intervalo de 4 ms é ruído da mesma ordem do que se quer medir. Precise no Windows usa
        # o temporizador multimídia, e o jitter cai para a granularidade do relógio.
        self._relogio.setTimerType(Qt.TimerType.PreciseTimer)
        self._relogio.timeout.connect(self._tique)
        self._relogio.start(self.intervalo_ms)

        if self._amostrar:
            self._parar.clear()
            self._amostrador = threading.Thread(
                target=self._amostrar_pilha, name="vigia-do-bloqueio", daemon=True
            )
            self._amostrador.start()
        return self

    def desligar(self) -> None:
        self._parar.set()
        if self._relogio is not None:
            self._relogio.stop()
            self._relogio = None
        if self._amostrador is not None:
            self._amostrador.join(timeout=1.0)
            self._amostrador = None

    def __enter__(self) -> Vigia:
        return self.ligar()

    def __exit__(self, *_args: object) -> None:
        self.desligar()

    # ------------------------------------------------------------------------------ o pulso

    def _tique(self) -> None:
        """Roda na thread da interface. Três linhas, porque ele é o instrumento e não a carga."""
        agora = time.perf_counter()
        atraso = (agora - self._pulso - self.intervalo_ms / 1000.0) * 1000.0
        self._marcas.append(agora)
        self._pulso = agora
        if atraso > self.piso_ms:
            with self._trava:
                pilha, self._pilha_pendente = self._pilha_pendente, ()
            self._travamentos.append(
                Travamento(
                    duracao_ms=atraso, quando_s=agora, operacao=self._operacao, pilha=pilha
                )
            )

    # ------------------------------------------------------------------------- o amostrador

    def _amostrar_pilha(self) -> None:
        """Roda fora da thread da interface, e por isso continua vivo enquanto ela não está.

        Guarda a **primeira** foto de cada travamento, e não a última: a pergunta acionável é
        "o que estava rodando quando o orçamento estourou", e a última foto tende a pegar o
        desenrolar da pilha, que aponta para quem chamou em vez de para quem gastou.
        """
        intervalo = AMOSTRAGEM_MS / 1000.0
        while not self._parar.wait(intervalo):
            parado_ha = (time.perf_counter() - self._pulso) * 1000.0
            if parado_ha <= self.piso_ms:
                continue
            with self._trava:
                if self._pilha_pendente:
                    continue  # já temos a foto deste travamento
                self._pilha_pendente = self._fotografar()

    def _fotografar(self) -> tuple[str, ...]:
        quadro = sys._current_frames().get(self._thread_da_interface)
        if quadro is None:  # pragma: no cover - a thread da interface sempre existe aqui
            return ()
        pilha = traceback.extract_stack(quadro)[-PROFUNDIDADE_DA_PILHA:]
        return tuple(
            f"{Path(item.filename).name}:{item.lineno} {item.name}" for item in pilha
        )

    # -------------------------------------------------------------------------- o que se lê

    @property
    def atrasos_ms(self) -> list[float]:
        return atrasos(self._marcas, self.intervalo_ms)

    @property
    def travamentos(self) -> list[Travamento]:
        return list(self._travamentos)

    def resumo(self, operacao: str = "") -> Resumo:
        return resumir(
            self.atrasos_ms,
            operacao=operacao or self._operacao,
            piso_ms=self.piso_ms,
            pulsos=len(self._marcas),
        )

    def zerar(self, operacao: str = "") -> None:
        """Recomeça a contagem sem parar o pulso.

        Recomeçar sem parar é o item: religar o `QTimer` entre duas operações mediria a partida
        do temporizador como se fosse um travamento da operação seguinte.
        """
        self._operacao = operacao
        self._travamentos.clear()
        self._marcas = [time.perf_counter()]
        self._pulso = self._marcas[0]
        with self._trava:
            self._pilha_pendente = ()


# ------------------------------------------------------------------ como um teste usa isto


@dataclass
class Medicao:
    """O que `medindo(...)` entrega: o nome, o resumo e os travamentos com pilha."""

    operacao: str
    resumo: Resumo = field(default_factory=lambda: resumir([]))
    travamentos: list[Travamento] = field(default_factory=list)

    def passou(self) -> bool:
        return self.resumo.passou()

    def relato(self) -> str:
        """A frase que uma falha de teste mostra. Nome, número e pilha -- nessa ordem."""
        if self.passou():
            return f"{self.operacao}: pior travamento {self.resumo.pior_ms:.1f} ms (dentro)"
        linhas = [
            f"{self.operacao} travou a thread da interface por "
            f"{self.resumo.pior_ms:.1f} ms (piso {self.resumo.piso_ms:.0f} ms), "
            f"{self.resumo.travamentos} vez(es), {self.resumo.total_bloqueado_ms:.0f} ms no total."
        ]
        for travamento in piores(self.travamentos, 3):
            linhas.append(f"  {travamento.duracao_ms:8.1f} ms")
            linhas.extend(f"      {quadro}" for quadro in travamento.pilha)
        return "\n".join(linhas)


@contextmanager
def medindo(
    operacao: str,
    *,
    vigia: Vigia | None = None,
    piso_ms: float = ORCAMENTO_MS,
    escoar: Callable[[], None] | None = None,
) -> Iterator[Medicao]:
    """Mede quanto a operação de dentro segurou a thread da interface.

    **`escoar` é obrigatório na prática, e a assinatura não o exige de propósito.** O pulso é um
    `QTimer`: ele só dispara quando alguém atende o laço de eventos, e uma operação chamada
    direto (que é como o produto a chama, de dentro de um slot) não atende ninguém enquanto roda.
    O disparo atrasado que fecha o vão só acontece na volta ao laço -- então quem mede tem de
    passar `QApplication.processEvents` aqui, e é isso que `_escoar_de` monta. Sem ele, o
    travamento existe e não é contado, que é o modo mais discreto de um portão dar tudo certo.
    """
    proprio = vigia is None
    ativo = vigia if vigia is not None else Vigia(piso_ms=piso_ms).ligar()
    medicao = Medicao(operacao=operacao)
    try:
        if escoar is not None:
            escoar()
        ativo.zerar(operacao)
        yield medicao
    finally:
        if escoar is not None:
            escoar()
        medicao.resumo = ativo.resumo(operacao)
        medicao.travamentos = ativo.travamentos
        if proprio:
            ativo.desligar()


F = TypeVar("F", bound=Callable[..., Any])


def nao_pode_travar(
    operacao: str = "", *, piso_ms: float = ORCAMENTO_MS, escoar: Callable[[], None] | None = None
) -> Callable[[F], F]:
    """Decorador: falha a função se o que ela faz segurar a interface por mais que `piso_ms`.

    Levanta `AssertionError` e não um tipo próprio porque quem lê a falha é o pytest, e uma
    exceção de asserção é o que ele sabe apresentar com o relato inteiro no corpo da mensagem.
    """

    def envolver(funcao: F) -> F:
        @wraps(funcao)
        def dentro(*args: Any, **kwargs: Any) -> Any:
            nome = operacao or funcao.__name__
            with medindo(nome, piso_ms=piso_ms, escoar=escoar) as medicao:
                resultado = funcao(*args, **kwargs)
            if not medicao.passou():
                raise AssertionError(medicao.relato())
            return resultado

        return dentro  # type: ignore[return-value]

    return envolver


@contextmanager
def sem_travar(
    operacao: str, *, piso_ms: float = ORCAMENTO_MS, escoar: Callable[[], None] | None = None
) -> Iterator[Medicao]:
    """Contexto que **levanta** se a operação de dentro violar o portão do §11.3."""
    with medindo(operacao, piso_ms=piso_ms, escoar=escoar) as medicao:
        yield medicao
    if not medicao.passou():
        raise AssertionError(medicao.relato())


# ------------------------------------------------------- exercício contra o tronco de verdade


def _preparar(caminho_do_tronco: Path = TRONCO) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def _descartar(janela: Any, aplicacao: Any) -> None:
    """Fecha a janela e **destrói o C++ agora**. É a `_descartar` de `teclado.py`, reusada.

    Reusada e não copiada de propósito: duas formas do mesmo encerramento seriam duas para
    esquecer, e foi justamente por este módulo não ter nenhuma que ele abortava calado (§8 item 9
    do ciclo 15). Ver o docstring de lá para a medição que a obrigou.
    """
    from caissa.ui.audit import teclado

    teclado._descartar(janela, aplicacao)


def _escoar_de(aplicacao: Any) -> Callable[[], None]:
    """A função que devolve o controle ao laço de eventos para os pulsos atrasados chegarem.

    Cinco voltas porque um `processEvents` só entrega os eventos já enfileirados: o disparo que
    fecha o vão pode ser postado durante a primeira volta e ser atendido na segunda.
    """

    def escoar() -> None:
        for _ in range(5):
            aplicacao.processEvents()

    return escoar


def _operacoes(
    janela: Any, pdf: Path, *, paginas: Sequence[int]
) -> list[tuple[str, Callable[[], object]]]:
    """As operações do tronco que este relatório mede, e por que estas.

    São os caminhos em que a S-116, a S-119 e a S-329 já registraram custo medido em centenas de
    milissegundos -- ou seja, os candidatos onde a violação, se existir, existe. Um harness que
    só exercitasse cliques baratos daria tudo certo e não teria medido nada.
    """
    from chess_diagram_ocr.pdf_io import get_pdf_page_count, render_pdf_page

    indice_do_dataset = _indice_da_aba(janela, "dataset")
    indice_da_galeria = _indice_da_aba(janela, "galeria")

    lista: list[tuple[str, Callable[[], object]]] = [
        ("contar paginas do PDF", lambda: get_pdf_page_count(pdf)),
        ("abrir PDF (load_pdf, 1a pagina a 300 DPI)", lambda: janela.abrir_pdf(pdf)),
        (
            "rasterizar pagina a 300 DPI (render_pdf_page)",
            lambda: render_pdf_page(pdf, paginas[0], dpi=300),
        ),
    ]
    lista += [
        (
            f"virar para a pagina {pagina + 1} (ir_para_pagina)",
            lambda p=pagina: janela.pdf.ir_para_pagina(p),
        )
        for pagina in paginas
    ]
    lista += [
        ("ajustar a pagina (fit-to-page + repintura)", lambda: _ajustar(janela)),
        (
            "carregar indice da Galeria do livro",
            lambda: janela.galeria.load_pdf(pdf, request_page=False),
        ),
    ]
    if indice_do_dataset is not None:
        lista.append(
            (
                "aba Dataset: mostrar e carregar as amostras",
                lambda: janela.abas.setCurrentIndex(indice_do_dataset),
            )
        )
    if indice_da_galeria is not None:
        lista.append(
            ("aba Galeria: mostrar", lambda: janela.abas.setCurrentIndex(indice_da_galeria))
        )
    return lista


def _ajustar(janela: Any) -> None:
    janela.pdf.ajustar_a_pagina()
    area = janela.pdf.visor.viewport()
    if area is not None:
        area.repaint()


def _indice_da_aba(janela: Any, agulha: str) -> int | None:
    for indice in range(janela.abas.count()):
        if agulha in janela.abas.tabText(indice).strip().lower():
            return indice
    return None


def medir(
    pdf: Path,
    *,
    paginas: Sequence[int] = (40, 41, 120),
    piso_ms: float = ORCAMENTO_MS,
    execucoes: int = 3,
    perfilar: bool = True,
    caminho_do_tronco: Path = TRONCO,
) -> dict[str, Any]:
    """Roda as operações do tronco sob o vigia, `execucoes` vezes, e devolve o relatório.

    Três execuções pela carta dos críticos (§6). **O portão olha o pior travamento de todas as
    execuções, e a mediana é publicada ao lado dele** -- e a inversão foi paga caro.

    A versão anterior deste módulo cobrava a mediana, com o argumento de que o máximo de três
    execuções mede o antivírus junto. O argumento é bom para operação repetível e é **falso para
    operação de primeiro uso**, que é a maioria das que este arnês exercita. Medido pelo crítico
    do ciclo 1, três invocações da operação "aba Dataset: mostrar e carregar as amostras":

    | invocação | execução 1 | execução 2 | execução 3 | mediana publicada | `viola` |
    |---|---|---|---|---|---|
    | 194639 | **1244,4 ms** | 13,3 | 14,6 | 14,6 | `False` |
    | 194727 | **1447,3 ms** | 15,8 | 15,4 | 15,8 | `False` |
    | 194737 | **1302,2 ms** | 15,5 | 17,7 | 17,7 | `False` |

    As execuções 2 e 3 não medem o antivírus nem o agendador: elas medem **nada**. Trocar para a
    aba que já está na frente não dispara `showEvent`, e o CSV de 5 431 linhas já está lido. A
    mediana de três execuções das quais duas são no-op é o no-op -- e o usuário encontra a
    execução 1, sempre, uma vez por sessão.

    A dispersão não é escondida: `pior_ms_por_execucao` continua no relatório, `pior_ms_mediana`
    continua publicado, e `pior_ms_frio` nomeia a primeira execução, que é a única em que uma
    leitura de disco é de fato uma leitura de disco. O que mudou é **quem decide `viola`**.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from PyQt6.QtCore import QT_VERSION_STR
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit.capture import estado_de_medicao

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    escoar = _escoar_de(aplicacao)
    # **Estado próprio, e não o `data/janela.json` do tronco** (F9-C12). Estas eram as **duas
    # únicas** construções de `JanelaPrincipal` no arnês inteiro sem `caminho_do_estado`, e o
    # preço foi cobrado ao crítico do ciclo 11: depois de três execuções deste portão, o
    # `data/janela.json` dele estava com `last_pdf = 1937 Kemeri.pdf`, `last_page = 120` e o zoom
    # da corrida -- a sessão de quem rodou o portão escrita por cima. A certidão de higiene do
    # ciclo 10 não pegou porque conferia o `data/app_tkinter_state.json`, que é o estado do Tk;
    # o da janela Qt é outro arquivo (`qt/janela.py: CAMINHO_DO_ESTADO`).
    #
    # **O número não depende disto**, e o crítico mediu: com o estado envenenado (zoom 1,0,
    # página 0, enquadramento por largura) a abertura do PDF deu 204 ms contra 207/212/205 ms
    # com o estado herdado. Não é um conserto de medição; é o portão parando de estragar a
    # sessão de quem o roda.
    temporaria = tempfile.TemporaryDirectory()
    estado = estado_de_medicao(Path(temporaria.name))
    janela = JanelaPrincipal(caminho_do_estado=estado)
    janela.resize(1280, 800)
    janela.show()
    escoar()

    vigia = Vigia(piso_ms=piso_ms).ligar()
    por_operacao: dict[str, list[Medicao]] = {}
    for _ in range(execucoes):
        for nome, funcao in _operacoes(janela, pdf, paginas=paginas):
            with medindo(nome, vigia=vigia, escoar=escoar) as medicao:
                try:
                    funcao()
                except Exception as exc:
                    print(f"  ! {nome} levantou {type(exc).__name__}: {exc}", file=sys.stderr)
            por_operacao.setdefault(nome, []).append(medicao)
    vigia.desligar()

    def _nova_janela() -> Any:
        nova = JanelaPrincipal(caminho_do_estado=estado)  # ver a nota acima
        nova.resize(1280, 800)
        nova.show()
        return nova

    atribuicoes = (
        _perfilar(janela, pdf, paginas=paginas, escoar=escoar, fabricar=_nova_janela)
        if perfilar
        else {}
    )
    linhas = [
        _consolidar(nome, medicoes, piso_ms, atribuicoes.get(nome))
        for nome, medicoes in por_operacao.items()
    ]
    linhas.sort(key=lambda item: item["pior_ms"], reverse=True)
    violam = [linha for linha in linhas if linha["viola"]]
    # **`_descartar` e não `close()`, e é o conserto do item 9 do §8 do ciclo 15.** Este portão
    # morria com `0xC0000005` **sem imprimir um caractere** em 5 de 8 invocações pela receita
    # publicada (2 de 8 aqui, mesma falha), e a causa não era o `PYTHONPATH` nem o amostrador de
    # pilha: medido, desligar a foto da pilha deixa 3 de 8 mortos. Era a `JanelaPrincipal`
    # morrendo por **coleta de lixo do Python** com `DeferredDelete` ainda pendentes no Qt -- o
    # mesmo aborto sem traceback que `teclado._descartar` documenta desde o ciclo 9, e que este
    # módulo era o único do arnês a não usar. `processEvents` não esvazia aquela fila; só
    # `sendPostedEvents(None, DeferredDelete)` esvazia.
    #
    # Um portão que aborta sem imprimir nada é, num CI, indistinguível de um portão que passou.
    _descartar(janela, aplicacao)
    temporaria.cleanup()  # a sessão de medição some com a medição; ver a nota lá em cima
    return {
        "portao": "SPEC 11.3 -- nenhuma operacao segura a thread da interface por mais de 16 ms",
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "ambiente": {
            "qt": QT_VERSION_STR,
            "python": sys.version.split()[0],
            "plataforma_qpa": os.environ.get("QT_QPA_PLATFORM", ""),
        },
        "metodo": {
            "instrumento": f"QTimer PreciseTimer de {INTERVALO_MS} ms na thread da interface",
            "amostrador": f"thread separada a cada {AMOSTRAGEM_MS} ms, sys._current_frames()",
            "piso_ms": piso_ms,
            "execucoes": execucoes,
            "reportado": (
                "PIOR travamento de todas as execucoes (é ele quem decide `viola`); "
                "a mediana e a execucao fria vao ao lado, em `pior_ms_mediana` e `pior_ms_frio`"
            ),
            "por_que_o_pior": (
                "a execucao 1 é a unica fria: trocar para a aba ja mostrada nao dispara showEvent "
                "e o CSV ja esta lido, entao as execucoes 2 e 3 medem no-op. A mediana de tres "
                "execucoes das quais duas sao no-op escondeu 1302 ms de congelamento no ciclo 1."
            ),
            "limite_conhecido": (
                "o amostrador precisa da GIL; extensao C que a segure atrasa a foto da pilha. "
                "A duracao nao depende disso."
            ),
            "atribuicao": (
                "tempo PROPRIO (tottime do cProfile) somado por familia de arquivo, numa passada "
                "a mais fora do vigia -- ver `_perfilar`. Existe porque `pilha_do_pior` e UMA "
                "amostra e sempre premia o maior bloco C contiguo: no ciclo 3 ela atribuiu a "
                "virada de pagina inteira ao PyMuPDF, e 30 % dela eram 108.620 chamadas Python "
                "de qt/. A soma de tottime nao conta ninguem duas vezes; a de cumtime contaria."
            )
            if perfilar
            else "desligada (--sem-perfil)",
        },
        "amostra": {"pdf": str(pdf), "paginas_base_1": [p + 1 for p in paginas]},
        "operacoes": linhas,
        "violam_o_portao": [linha["operacao"] for linha in violam],
        "veredito": "REPROVOU" if violam else "PASSOU",
    }


def _perfilar(
    janela: Any,
    pdf: Path,
    *,
    paginas: Sequence[int],
    escoar: Callable[[], None],
    fabricar: Callable[[], Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Uma passada a mais, sob `cProfile`, para dizer **de quem** é o tempo de cada operação.

    **É a resposta ao terceiro portão que mediu a coisa errada.** `pilha_do_pior` é uma foto: ela
    premia sempre o maior bloco C contíguo, e nunca vê custo espalhado por milhares de chamadas
    Python minúsculas. Foi assim que o ciclo 2 publicou "virar de página é `PyMuPDF`, e `pdf_io`
    não é desta frente" -- e 30 % da virada eram 108.620 chamadas de `labels._clean` disparadas
    por quatro quadros de `qt/`. A foto estava certa; ela só não era a operação inteira.

    **Passada separada, e não perfil das execuções medidas**, porque `cProfile` cobra por chamada:
    perfilar sob o vigia infla os vãos do pulso e o portão passaria a medir o instrumento. Os
    números do portão saem das execuções limpas; a atribuição sai desta, e o relatório diz qual é
    qual (`atribuicao.metodo`).
    """
    # **Uma janela nova, e é o conserto do §4.4c** (F9-C7). Esta passada rodava sobre a janela
    # que acabou de sofrer três execuções medidas -- ou seja, com o PDF aberto, a aba Dataset já
    # mostrada e o CSV já lido. O `method.por_que_o_pior` do próprio relatório diz que **só a
    # execução 1 é fria**, e ninguém aplicou a frase a esta passada: o perfil da aba Dataset
    # reproduzia **1,4 ms de um congelamento de 74,5 ms**, e o relatório publicava as famílias
    # desse 1,4 ms como se fossem as do congelamento.
    #
    # Com a janela nova, cada operação é perfilada no mesmo estado em que ela foi medida pela
    # primeira vez, que é o estado que decide `viola`. `fabricar=None` mantém o comportamento
    # antigo para quem chamar sem ele -- e `_linhas_da_atribuicao` publica a cobertura, então
    # uma passada que não reproduza o evento passa a **dizer** que não reproduziu.
    if fabricar is not None:
        antiga, janela = janela, fabricar()
        escoar()
    else:
        antiga = None
    saida: dict[str, dict[str, Any]] = {}
    for nome, funcao in _operacoes(janela, pdf, paginas=paginas):
        escoar()
        perfil = cProfile.Profile()
        perfil.enable()
        try:
            funcao()
            # **O escoamento entra no perfil, e é a outra metade do §4.4c.** `medindo` drena a
            # fila de eventos **dentro** da janela medida (ver o `finally` dele), então o que o
            # portão cobra inclui o que o Qt faz depois da chamada -- montar a tabela, aplicar o
            # leiaute, repintar. Perfilar só `funcao()` deixava tudo isso de fora: a pilha do
            # pior da aba Dataset aponta para `bloqueio.py:667 escoar`, e o perfil não o via.
            # Com a janela fria **e** o escoamento dentro, a passada perfila o mesmo intervalo
            # que a passada medida cronometrou, e a linha de COBERTURA passa a poder dizê-lo.
            escoar()
        except Exception as exc:  # noqa: BLE001 - a operação já foi reportada na passada medida
            print(f"  ! {nome} levantou {type(exc).__name__} ao perfilar: {exc}", file=sys.stderr)
        finally:
            perfil.disable()
        escoar()
        saida[nome] = atribuir(pstats.Stats(perfil).stats)  # type: ignore[attr-defined]
    if antiga is not None:
        # A janela fria desta passada some pelo mesmo caminho da janela medida: `close()` sozinho
        # deixava o C++ para "quando a linha de eventos girar", e ela nunca gira aqui.
        from PyQt6.QtWidgets import QApplication

        _descartar(janela, QApplication.instance())
        escoar()
    return saida


def _mediana(valores: Sequence[float]) -> float:
    ordenados = sorted(valores)
    return ordenados[(len(ordenados) - 1) // 2] if ordenados else 0.0


def _consolidar(
    nome: str,
    medicoes: Sequence[Medicao],
    piso_ms: float,
    atribuicao: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A linha de uma operação. **`viola` olha o pior, não a mediana** -- ver `medir`.

    `pilha_do_pior` sai do travamento mais longo de **todas** as execuções, e não da mediana:
    é a pilha do número que o portão cobra, senão o relatório publicaria um diagnóstico de
    outra execução que não a reprovada -- o defeito nº 5 da crítica do ciclo 1.

    `atribuicao` fica **ao lado** dela e não no lugar dela: as duas respondem perguntas
    diferentes -- a pilha diz onde a thread estava no pior instante, a atribuição diz para onde
    foi o tempo todo. Ver `_perfilar`.
    """
    piores_ms = [medicao.resumo.pior_ms for medicao in medicoes]
    mediana = _mediana(piores_ms)
    pior_ms = max(piores_ms) if piores_ms else 0.0
    todos = [travamento for medicao in medicoes for travamento in medicao.travamentos]
    pior = piores(todos, 1)
    return {
        "operacao": nome,
        "pior_ms": pior_ms,
        "pior_ms_mediana": mediana,
        "pior_ms_frio": piores_ms[0] if piores_ms else 0.0,
        "pior_ms_por_execucao": piores_ms,
        "total_bloqueado_ms_mediana": _mediana(
            [medicao.resumo.total_bloqueado_ms for medicao in medicoes]
        ),
        "travamentos_mediana": _mediana(
            [float(medicao.resumo.travamentos) for medicao in medicoes]
        ),
        "viola": pior_ms > piso_ms,
        "excesso_ms": max(0.0, pior_ms - piso_ms),
        "pilha_do_pior": list(pior[0].pilha) if pior else [],
        "atribuicao": atribuicao or {},
    }


def tabela(relatorio: dict[str, Any]) -> str:
    linhas = [
        f"Bloqueio da thread da interface -- piso {relatorio['metodo']['piso_ms']:.0f} ms, "
        f"{relatorio['metodo']['execucoes']} execucoes -- a coluna e o PIOR de todas elas",
        f"Livro: {Path(relatorio['amostra']['pdf']).name}",
        "",
        f"  {'':<3}{'operacao':<46}{'pior(ms)':>10}{'frio(ms)':>10}"
        f"{'mediana':>9}{'travas':>8}  veredito",
    ]
    for linha in relatorio["operacoes"]:
        marca = "!!" if linha["viola"] else "ok"
        linhas.append(
            # **A coluna imprime o `pior_ms`, que e quem decide `viola`** (F9-C2). Ela imprimia
            # `pior_ms_mediana` enquanto o veredito ja olhava o pior: a aba Dataset saia com
            # "14.6 ms  VIOLA" na mesma linha, um numero que nao explicava o proprio veredito.
            f"  {marca:<3}{linha['operacao'][:44]:<46}{linha['pior_ms']:>10.1f}"
            f"{linha['pior_ms_frio']:>10.1f}{linha['pior_ms_mediana']:>9.1f}"
            f"{linha['travamentos_mediana']:>8.0f}  "
            f"{'VIOLA' if linha['viola'] else 'dentro'}"
        )
    if relatorio["violam_o_portao"]:
        linhas.append("")
        linhas.append("Piores infratores, com amostra de pilha E atribuicao por familia:")
        # **Todas as que violam, e não as quatro primeiras** (F9-C7, §4.4a). O corte `[:4]`
        # estava aqui, e com sete violações ele deixava **três** sem atribuição nenhuma no
        # relatório de texto -- que é o único que se lê. Um portão que reprova sete e explica
        # quatro convida a estender a explicação das quatro às sete, e foi o que aconteceu:
        # "o resto é PyMuPDF" cobria 4 de 7.
        for linha in relatorio["operacoes"]:
            if not linha["viola"]:
                continue
            linhas.append(f"  {linha['pior_ms']:.0f} ms -- {linha['operacao']}")
            linhas.append("    pilha do pior (UMA amostra -- ve o maior bloco C contiguo):")
            linhas.extend(f"      {quadro}" for quadro in linha["pilha_do_pior"])
            linhas.extend(
                _linhas_da_atribuicao(linha.get("atribuicao") or {}, linha["pior_ms"])
            )
    linhas.append("")
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def _linhas_da_atribuicao(atribuicao: dict[str, Any], pior_ms: float = 0.0) -> list[str]:
    """O bloco de atribuição de uma operação, para a tabela do terminal.

    **É o que o §7.2 do ciclo 3 pediu com estas palavras**: *"o relatório do arnês, sozinho,
    mostrar que a virada de página tem custo em `qt/` sem ninguém precisar escrever um instrumento
    novo"*. A linha `DESTA FRENTE` é impressa mesmo quando dá zero, porque um zero afirmado é a
    resposta e um zero ausente é uma pergunta.
    """
    if not atribuicao:
        return []
    saida = ["    tempo PROPRIO por familia (cProfile, passada separada -- ve custo espalhado):"]
    for item in atribuicao["por_familia"][:6]:
        saida.append(
            f"      {item['ms']:8.1f} ms  {item['fracao'] * 100:5.1f} %  {item['familia']}"
        )
    saida.append(
        f"      -> DESTA FRENTE (qt/ + ui/): {atribuicao['ms_desta_frente']:.1f} ms "
        f"({atribuicao['fracao_desta_frente'] * 100:.1f} % do perfilado)"
    )
    # **A cobertura, e ela é a linha mais importante do bloco** (F9-C7, §4.4c). O crítico mediu
    # que a atribuição da aba Dataset reproduzia **1,05-1,41 ms de um congelamento de 74,5 ms**
    # -- 1,9 % --, e o relatório publicava as porcentagens *daquele 1,4 ms* como se fossem as do
    # congelamento. Percentagem de uma amostra que não reproduz o evento não descreve o evento.
    # Sem esta linha, quem lê não tem como saber a diferença; com ela, "o resto é PyMuPDF" deixa
    # de ser dizível quando o perfil só viu 2 % da coisa.
    if pior_ms > 0:
        cobertura = 100.0 * atribuicao["total_perfilado_ms"] / pior_ms
        aviso = "" if cobertura >= COBERTURA_MINIMA else "   <<< o perfil NAO reproduz o congelamento"
        saida.append(
            f"      -> COBERTURA: o perfil viu {atribuicao['total_perfilado_ms']:.1f} ms de um "
            f"pior de {pior_ms:.1f} ms ({cobertura:.1f} %){aviso}"
        )
    for item in atribuicao["funcoes_mais_caras"][:4]:
        disparo = item.get("disparada_por") or ""
        de_onde = f"   <- {disparo}" if disparo else ""
        saida.append(f"      {item['ms']:8.1f} ms  {item['quem']}{de_onde}")
    # A lista de E/S de disco sai da medição, e não do relatório escrito à mão (F9-C14, item 8).
    # O piso é para a lista publicada dizer **caminhos** e não análise de string: `pathlib` monta
    # e desmonta caminho sem tocar disco, e as dezenas de quadros de 0,0 ms dela afogariam os
    # dois `sqlite3` de 30 ms que o crítico do ciclo 13 nomeou. O JSON continua com todos.
    disco = atribuicao.get("e_s_de_disco", [])
    acima = [item for item in disco if item["ms"] >= PISO_DA_LISTA_DE_DISCO]
    saida.append(
        f"    E/S de disco na thread da janela que o perfil nomeia: {len(acima)} acima de "
        f"{PISO_DA_LISTA_DE_DISCO} ms ({len(disco)} no total, o resto e' analise de caminho)"
    )
    for item in acima[:10]:
        disparo = item.get("disparada_por") or ""
        de_onde = f"   <- {disparo}" if disparo else ""
        saida.append(f"      {item['ms']:8.2f} ms  {item['quem']}{de_onde}")
    return saida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bloqueio da thread da interface (SPEC 11.3).")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--paginas", type=int, nargs="*", default=[41, 42, 121], help="base 1")
    parser.add_argument("--piso-ms", type=float, default=ORCAMENTO_MS)
    parser.add_argument("--execucoes", type=int, default=3)
    parser.add_argument(
        "--sem-perfil",
        action="store_true",
        help="pula a passada de cProfile que atribui o tempo por familia de arquivo",
    )
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

    relatorio = medir(
        args.pdf,
        paginas=[max(0, pagina - 1) for pagina in args.paginas],
        piso_ms=args.piso_ms,
        execucoes=args.execucoes,
        perfilar=not args.sem_perfil,
        caminho_do_tronco=args.tronco,
    )
    args.saida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"bloqueio_{marca}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")

    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
