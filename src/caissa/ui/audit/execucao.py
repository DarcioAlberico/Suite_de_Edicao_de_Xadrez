r"""Portão de **execução**: a operação de fundo é achada vendo-a correr, não lendo o código.

**Por que a régua mudou de forma, e não de tamanho.** O detector de `caissa.ui.audit.progresso`
é sintático: ele lê a AST de `qt/` e procura as formas conhecidas de abrir trabalho. A história
dele, ciclo a ciclo, é uma corrida perdida:

| rodada | sabotagem | pegou |
|---|---|---|
| ciclo 5 (crítico) | 6 formas | 1 de 6 → depois 6 de 6 |
| ciclo 7 (crítico) | 8 formas | 1 de 8 → depois 8 de 8 |
| ciclo 8 (construtor) | 8 formas | 1 de 8 → depois 8 de 8 |
| **ciclo 9 (crítico)** | **8 formas novas** | **0 de 8** |

Cada rodada fecha as formas da rodada anterior e a seguinte inventa outras. A classe devolvida
por uma função, o apelido por walrus, o campo anotado de uma `dataclass`, `QProcess.startDetached`,
`QtConcurrent.run`, um decorador que mora noutro módulo, `type("Fundo", (Thread,), {})` -- não há
lista de padrões que termine. **Uma thread que a AST não escreveu não existe para a AST; uma
thread que corre existe para o `threading`.**

---

**O que este portão observa.** Duas medidas independentes, e a segunda é a que fecha a corrida:

1. **Os pontos de abertura**, interceptados: `threading.Thread.start`,
   `_thread.start_new_thread` (e `start_new`), `multiprocessing.Process.start`, `QThread.start`,
   `QThreadPool.start` e `tryStart`, `QProcess.start` e `startDetached`, `subprocess.Popen` e
   `os.startfile` -- **dez**, e os dois primeiros entraram no ciclo 12 porque o crítico do ciclo
   11 os atravessou com biblioteca-padrão pura. Cada interceptação guarda **a origem** -- o quadro de pilha mais interno que
   não é da biblioteca-padrão nem deste módulo. É isso que faz `executor.submit(...)`,
   `asyncio.to_thread(...)` e `ThreadPool.map(...)` serem atribuídos a **quem os chamou**, e não
   a `concurrent/futures/thread.py`.

2. **`threading.enumerate()` antes e depois**, que é a rede: qualquer thread de Python que tenha
   nascido e que a lista de (1) **não** explique aparece como `NAO ATRIBUIDA`, com o nome e o
   `target` dela. Uma forma nova de abrir thread não escapa do portão -- ela escapa da
   *atribuição*, e o portão diz isso em vez de ficar calado. Era exatamente isso que a régua de
   AST não conseguia fazer: o que ela não conhecia, ela não reportava.

**O que ele ainda não vê, dito sem atenuar, e a frase encolheu porque estava larga** (F9-C12).
Trabalho aberto por **chamada à API do sistema**, que não passe por nenhum dos dez pontos e não
crie objeto de Python nenhum -- `ctypes.windll.kernel32.CreateThread` é o caso, e o crítico do
ciclo 11 o plantou e o portão ficou calado. `threading.enumerate()` só lista threads que o
`threading` conhece. **A frase de antes dizia "para atravessá-la é preciso sair do Python", e
isso era falso**: `_thread.start_new_thread` e `multiprocessing.Process` são biblioteca-padrão e
atravessavam. Os dois entraram na lista; o que resta fora é quem chama a API do sistema por
`ctypes`, e aí não nasce objeto de Python para interceptar. É uma fronteira de mecanismo, não uma
lista de padrões que envelhece: para atravessá-la
é preciso sair do Python, e não inventar uma nova sintaxe.

---

**A regra de cobertura.** Uma abertura observada está coberta quando:

* a origem `(arquivo, função)` está declarada em `ui/busy.FORA_DO_REGISTRO` -- a tabela que diz
  *"esta operação não perde trabalho ao fechar"*, com o motivo escrito; **ou**
* houve um `BusyRegistry.register(...)` **do mesmo arquivo** durante a mesma ação. O registro é
  interceptado com a mesma resolução de origem, então "o mesmo arquivo" é medido e não suposto.

Fora disso a abertura é um **defeito**: trabalho correndo ao fundo sem nada na tela e sem uma
decisão escrita sobre o que se perde ao fechar a janela.

Uso:

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
    PYTHONPATH=<suite>/src;<tronco>/src \
    <tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.execucao --pdf "<livro>.pdf" \
        --saida benchmarks/reports/ui/c10
    ... --sabotagem benchmarks/reports/ui/c10/sab_c9    # a árvore do crítico do ciclo 9
"""

from __future__ import annotations

import _thread
import argparse
import importlib.util
import inspect
import json
import multiprocessing
import multiprocessing.process
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` só existe no 3.11 e o venv do tronco -- onde o PyQt6 mora -- é 3.10. Escrito
como `timezone(timedelta(0))` pela mesma razão de `audit/teclado.py`: o `ruff --fix` desta suíte
tem alvo py311 e reescreveria o alias para o `datetime.UTC` que morre no 3.10."""

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
PASTA_DE_FONTES = r"C:\Windows\Fonts"

_PASTAS_DA_BIBLIOTECA = tuple(
    str(Path(caminho).resolve()).lower()
    for chave in ("stdlib", "platstdlib", "purelib", "platlib")
    if (caminho := sysconfig.get_paths().get(chave))
)
"""As pastas cujos quadros de pilha **não** são a origem de uma abertura.

`ThreadPoolExecutor.submit` chama `Thread.start` de dentro de `concurrent/futures/thread.py`;
atribuir a abertura àquele arquivo diria o nome do mecanismo em vez do nome de quem o usou -- que
é a queixa literal do crítico do ciclo 7 contra a régua de AST: *"uma linha dizendo `__init__`
constrói `QThread` não diz que `e_move_to_thread` é uma operação de fundo"*."""

_E_FORMA = re.compile(r"^[a-z][0-9]?_")
"""Que método de uma classe de sabotagem é uma forma a medir.

`a_classe_devolvida`, `h_subclasse_dinamica`, `n1_relogio`, `n4_reduce` -- letra, dígito
opcional, sublinhado. Os que começam por `_` são ajudantes da própria sabotagem e não são a
forma; os que começam por `n` são os **controles negativos**, e o silêncio deles é medido junto:
um portão que passasse a gritar seria a outra maneira de ficar cego."""

TEMPO_DE_ASSENTAR_S = 0.35
"""Quanto esperar depois de cada ação antes de recontar as threads.

Uma thread aberta por `QTimer.singleShot` ou por um sinal enfileirado nasce **depois** do
`processEvents` que a pediu. Sem essa espera o portão mediria o instante errado -- e é a mesma
forma de cegueira do §4.2 da crítica do ciclo 9, onde um tique apagava um portão inteiro."""


# ------------------------------------------------------------------ o que se observa (sem Qt)


@dataclass(frozen=True)
class Abertura:
    """Uma abertura de trabalho de fundo, com a origem de quem a abriu."""

    tipo: str
    """Por qual ponto ela passou: `threading.Thread.start`, `QThread.start`, ..."""

    detalhe: str
    """O que foi aberto, quando dá para dizer: o `target`, o programa, o nome da thread."""

    arquivo: str
    """O nome do arquivo de origem, **sem pasta** -- a chave de `FORA_DO_REGISTRO`."""

    funcao: str
    """A função de origem. A outra metade da chave."""

    linha: int = 0
    acao: str = ""
    """A ação da janela durante a qual ela aconteceu."""

    def chave(self) -> tuple[str, str]:
        return (self.arquivo, self.funcao)


@dataclass(frozen=True)
class Registro:
    """Um `BusyRegistry.register(...)` observado, com a origem de quem registrou."""

    nome: str
    arquivo: str
    funcao: str
    acao: str = ""


@dataclass
class Acao:
    """Uma ação da janela e tudo o que ela abriu."""

    nome: str
    aberturas: list[Abertura] = field(default_factory=list)
    registros: list[Registro] = field(default_factory=list)
    nao_atribuidas: list[str] = field(default_factory=list)
    """Threads que nasceram e que nenhum ponto interceptado explica. Ver o docstring do módulo."""

    def descobertas(self, declaradas: dict[tuple[str, str], str]) -> list[Abertura]:
        """As aberturas sem registro e sem declaração. É o defeito que este portão existe para achar."""
        arquivos_que_registraram = {registro.arquivo for registro in self.registros}
        return [
            abertura
            for abertura in self.aberturas
            if abertura.chave() not in declaradas
            and abertura.arquivo not in arquivos_que_registraram
        ]


def origem_da_pilha(pular: Sequence[str] = ()) -> tuple[str, str, int]:
    """`(arquivo, função, linha)` do quadro mais interno que não é biblioteca nem arnês.

    Pura o suficiente para ser afirmada sem janela: recebe a pilha do interpretador e devolve a
    primeira posição que pertence a código de produto. O `pular` acrescenta caminhos -- é como o
    próprio `execucao.py` sai da conta sem se nomear numa constante.
    """
    ignorar = tuple(str(Path(caminho).resolve()).lower() for caminho in pular)
    quadro = inspect.currentframe()
    while quadro is not None:
        caminho = str(Path(quadro.f_code.co_filename).resolve()).lower()
        interno = caminho.startswith(_PASTAS_DA_BIBLIOTECA) or caminho.startswith(ignorar)
        if not interno and "<" not in quadro.f_code.co_filename:
            return (
                Path(quadro.f_code.co_filename).name,
                quadro.f_code.co_name,
                quadro.f_lineno,
            )
        quadro = quadro.f_back
    return ("(desconhecido)", "(desconhecido)", 0)


# ------------------------------------------------------------------------------ o vigia


class Vigia:
    """Intercepta toda abertura de trabalho de fundo enquanto o bloco corre.

    **Restaura tudo no `__exit__`, inclusive quando o bloco levanta.** Um vigia que deixasse
    `threading.Thread.start` remendado contaminaria toda medição posterior do processo -- e este
    módulo roda três, quatro ações seguidas na mesma janela.
    """

    def __init__(self, *, simular_processos: bool = False) -> None:
        self.aberturas: list[Abertura] = []
        self.registros: list[Registro] = []
        self.fios_vistos: set[int] = set()
        """A identidade de cada `threading.Thread` interceptada. É contra ela que a rede do
        `threading.enumerate()` compara -- contar quantas foram interceptadas seria uma
        aproximação, e a pergunta "qual thread nasceu sem ninguém a ver" pede a identidade."""
        self._simular = simular_processos
        """Em modo de sabotagem, `QProcess.startDetached`, `subprocess.Popen` e `os.startfile`
        são **registrados e não executados**: uma sabotagem que abrisse um programa de verdade na
        máquina de quem roda o portão seria um efeito colateral que nenhum arnês pode ter."""
        self._desfazer: list[Callable[[], None]] = []
        self._eu = str(Path(__file__).resolve().parent)

    # ------------------------------------------------------------------ montagem

    def _origem(self) -> tuple[str, str, int]:
        return origem_da_pilha((self._eu,))

    def _anotar(self, tipo: str, detalhe: str) -> None:
        arquivo, funcao, linha = self._origem()
        self.aberturas.append(
            Abertura(tipo=tipo, detalhe=detalhe, arquivo=arquivo, funcao=funcao, linha=linha)
        )

    def _remendar(self, alvo: Any, nome: str, feitor: Callable[[Any], Any]) -> None:
        """Troca `alvo.nome` e guarda o **descritor** original, não o que `getattr` devolve.

        **A diferença quebrou três testes do tronco, e é sutil.** Para uma classe do sip
        (`QThread`), `getattr(QThread, "start")` devolve um `builtin_function_or_method`
        **desligado da classe**; devolvê-lo por `setattr` deixa `QThread.start` com um objeto que
        já não sabe se ligar à instância, e a chamada seguinte morre com
        *"first argument of unbound method must have type 'QThread'"*. Quem restaura de verdade é
        `QThread.__dict__["start"]`, o `sip.methoddescriptor`.

        Foi a suíte do tronco que achou: três testes de `qt/trabalho.py` passaram a falhar
        **depois** deste vigia rodar no mesmo processo. Um instrumento que estraga o que mediu é
        pior que um que não mede.
        """
        proprio = getattr(alvo, "__dict__", {})
        original = proprio.get(nome, getattr(alvo, nome, None)) if hasattr(alvo, "__dict__") else getattr(alvo, nome, None)
        if original is None:
            return
        try:
            setattr(alvo, nome, feitor(getattr(alvo, nome)))
        except (TypeError, AttributeError):  # pragma: no cover - tipo de extensão fechado
            return
        self._desfazer.append(lambda: setattr(alvo, nome, original))

    def __enter__(self) -> Vigia:
        vigia = self

        def _thread_start(original: Any) -> Any:
            def dentro(self: Any, *args: Any, **kwargs: Any) -> Any:
                alvo = getattr(self, "_target", None)
                nome = getattr(alvo, "__qualname__", None) or getattr(self, "name", "")
                vigia.fios_vistos.add(id(self))
                vigia._anotar("threading.Thread.start", f"{type(self).__name__} -> {nome}")
                return original(self, *args, **kwargs)

            return dentro

        self._remendar(threading.Thread, "start", _thread_start)

        # **`_thread.start_new_thread`, e ele não é exótico: é uma linha da biblioteca-padrão**
        # (F9-C12). O crítico do ciclo 11 plantou quatro formas contra a *fronteira de
        # mecanismo* declarada -- *"para atravessá-la é preciso sair do Python"* -- e três delas
        # não saem do Python. Esta é a pior: `_thread.start_new_thread(f, ())` cria uma thread de
        # verdade sem construir `threading.Thread`, e **`threading.enumerate()` não a lista**
        # enquanto ela não tocar no módulo `threading`. Ou seja, ela escapava do ponto E da rede.
        def _thread_cru(original: Any) -> Any:
            def dentro(funcao: Any, *args: Any, **kwargs: Any) -> Any:
                nome = getattr(funcao, "__qualname__", None) or repr(funcao)
                vigia._anotar("_thread.start_new_thread", f"_thread -> {nome}")
                return original(funcao, *args, **kwargs)

            return dentro

        self._remendar(_thread, "start_new_thread", _thread_cru)
        self._remendar(_thread, "start_new", _thread_cru)

        # **`multiprocessing.Process.start`**, pela mesma medição. O `Popen` que ele usa é o
        # `multiprocessing.popen_spawn_win32`, e não o `subprocess.Popen` que o ponto F cobre --
        # então um processo de fundo de verdade passava calado. `ProcessPoolExecutor` já era
        # pego, mas por acidente: pela thread alimentadora interna dele, não pelo processo.
        def _processo_de_mp(original: Any) -> Any:
            def dentro(self: Any, *args: Any, **kwargs: Any) -> Any:
                alvo = getattr(self, "_target", None)
                nome = getattr(alvo, "__qualname__", None) or getattr(self, "name", "")
                vigia._anotar("multiprocessing.Process.start", f"{type(self).__name__} -> {nome}")
                return original(self, *args, **kwargs)

            return dentro

        self._remendar(multiprocessing.process.BaseProcess, "start", _processo_de_mp)

        def _register(original: Any) -> Any:
            def dentro(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
                arquivo, funcao, _linha = vigia._origem()
                vigia.registros.append(Registro(nome=name, arquivo=arquivo, funcao=funcao))
                return original(self, name, *args, **kwargs)

            return dentro

        try:
            from chess_diagram_ocr.ui.busy import BusyRegistry

            self._remendar(BusyRegistry, "register", _register)
        except Exception:  # pragma: no cover - sem o tronco no path, o portão ainda mede aberturas
            pass

        self._remendar(subprocess, "Popen", self._processo("subprocess.Popen"))
        self._remendar(os, "startfile", self._processo("os.startfile"))
        self._remendar_o_qt()
        return self

    def _processo(self, tipo: str) -> Callable[[Any], Any]:
        vigia = self

        def feitor(original: Any) -> Any:
            def dentro(*args: Any, **kwargs: Any) -> Any:
                vigia._anotar(tipo, str(args[0]) if args else "")
                if vigia._simular:
                    return None
                return original(*args, **kwargs)

            return dentro

        return feitor

    def _remendar_o_qt(self) -> None:
        try:
            from PyQt6.QtCore import QProcess, QThread, QThreadPool
        except Exception:  # pragma: no cover - sem binding do Qt o portão mede o resto
            return
        vigia = self

        def _metodo(tipo: str, *, simulavel: bool = False) -> Callable[[Any], Any]:
            def feitor(original: Any) -> Any:
                def dentro(*args: Any, **kwargs: Any) -> Any:
                    alvo = args[1] if len(args) > 1 else ""
                    vigia._anotar(tipo, str(alvo))
                    if simulavel and vigia._simular:
                        return False
                    return original(*args, **kwargs)

                return dentro

            return feitor

        self._remendar(QThread, "start", _metodo("QThread.start"))
        self._remendar(QThreadPool, "start", _metodo("QThreadPool.start"))
        self._remendar(QThreadPool, "tryStart", _metodo("QThreadPool.tryStart"))
        self._remendar(QProcess, "start", _metodo("QProcess.start", simulavel=True))
        self._remendar(QProcess, "startDetached", _metodo("QProcess.startDetached", simulavel=True))

    def __exit__(self, *_args: object) -> None:
        for desfazer in reversed(self._desfazer):
            desfazer()
        self._desfazer.clear()


@contextmanager
def observar(
    nome: str,
    *,
    simular_processos: bool = False,
    escoar: Callable[[], None] | None = None,
) -> Iterator[Acao]:
    """Roda uma ação sob o vigia e devolve o que ela abriu, com a rede do `threading.enumerate`.

    `escoar` é chamado **depois** da espera de assentamento e antes de fechar a conta: é por onde
    o Qt gira a fila de eventos, e sem ele uma thread aberta por `QTimer.singleShot` nasceria
    depois da medição. Um portão que não vê o que um tique adia é o defeito do §4.2 da crítica do
    ciclo 9, e ele não vai ser reposto aqui.
    """
    acao = Acao(nome=nome)
    antes = {id(fio) for fio in threading.enumerate()}
    with Vigia(simular_processos=simular_processos) as vigia:
        yield acao
        time.sleep(TEMPO_DE_ASSENTAR_S)
        if escoar is not None:
            escoar()
            time.sleep(TEMPO_DE_ASSENTAR_S)
        acao.aberturas = [
            Abertura(**{**asdict(abertura), "acao": nome}) for abertura in vigia.aberturas
        ]
        acao.registros = [
            Registro(**{**asdict(registro), "acao": nome}) for registro in vigia.registros
        ]
        vistos = set(vigia.fios_vistos)
    acao.nao_atribuidas = [
        f"{fio.name} -> {getattr(getattr(fio, '_target', None), '__qualname__', '?')}"
        for fio in threading.enumerate()
        if id(fio) not in antes and id(fio) not in vistos
    ]


# --------------------------------------------------------------------- a janela (Qt aqui)


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def auditar(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
) -> dict[str, Any]:
    """Abre a janela do tronco, executa as ações e devolve o que cada uma abriu ao fundo."""
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from chess_diagram_ocr.ui.busy import FORA_DO_REGISTRO
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit.capture import estado_de_medicao

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    # Estado próprio, pela razão de `capture.estado_de_medicao`: um portão não lê nem reescreve
    # a sessão de quem o roda.
    with tempfile.TemporaryDirectory() as temporaria:
        janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(Path(temporaria)))
    janela.show()
    janela.resize(1280, 800)

    def escoar(voltas: int = 12) -> None:
        for _ in range(voltas):
            aplicacao.processEvents()

    escoar()
    acoes: list[Acao] = []

    def rodar(nome: str, fazer: Callable[[], object]) -> None:
        with observar(nome, escoar=escoar) as acao:
            try:
                fazer()
            except Exception as exc:  # noqa: BLE001 - a ação que falha é dado, não parada
                print(f"  ({nome} levantou: {exc})", file=sys.stderr)
            escoar()
        acoes.append(acao)
        print(
            f"  {nome:<28} {len(acao.aberturas):>2} aberturas  "
            f"{len(acao.registros):>2} registros  "
            f"{len(acao.descobertas(FORA_DO_REGISTRO)):>2} sem cobertura  "
            f"{len(acao.nao_atribuidas):>2} nao atribuidas"
        )

    from caissa.ui.audit.capture import aguardar_a_folha, areas_de_trabalho

    if pdf is not None and pdf.exists():
        rodar("abrir o livro", lambda: (janela.abrir_pdf(pdf), aguardar_a_folha(janela)))
        rodar("ir para a pagina 41", lambda: (janela.pdf.ir_para_pagina(40), aguardar_a_folha(janela)))
        rodar("ir para a pagina 121", lambda: (janela.pdf.ir_para_pagina(120), aguardar_a_folha(janela)))
    # Cada área uma vez -- as abas do acervo e os modos da aba `Livro` (OCR_UI passo 17).
    for area in areas_de_trabalho(janela):
        rodar(f"abrir a aba {area.nome}", area.mostrar)

    janela.close()
    janela.deleteLater()
    escoar()

    descobertas = [
        asdict(abertura)
        for acao in acoes
        for abertura in acao.descobertas(FORA_DO_REGISTRO)
    ]
    nao_atribuidas = [
        {"acao": acao.nome, "thread": linha} for acao in acoes for linha in acao.nao_atribuidas
    ]
    return {
        "portao": "operacao de fundo achada por EXECUCAO -- ver caissa.ui.audit.execucao",
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "metodo": {
            "pontos_interceptados": [
                "threading.Thread.start",
                "_thread.start_new_thread",
                "_thread.start_new",
                "multiprocessing.Process.start",
                "QThread.start",
                "QThreadPool.start",
                "QThreadPool.tryStart",
                "QProcess.start",
                "QProcess.startDetached",
                "subprocess.Popen",
                "os.startfile",
            ],
            "fora_da_fronteira": (
                "chamada a API do sistema por ctypes (kernel32.CreateThread): nao nasce objeto "
                "de Python para interceptar, e threading.enumerate() nao a lista"
            ),
            "rede": "threading.enumerate() antes e depois de cada acao",
            "cobertura": (
                "declarada em ui/busy.FORA_DO_REGISTRO, ou um register() do mesmo arquivo "
                "durante a mesma acao"
            ),
            "assentar_s": TEMPO_DE_ASSENTAR_S,
        },
        "declaradas": {f"{a}::{f}": motivo for (a, f), motivo in FORA_DO_REGISTRO.items()},
        "acoes": [
            {
                "nome": acao.nome,
                "aberturas": [asdict(a) for a in acao.aberturas],
                "registros": [asdict(r) for r in acao.registros],
                "sem_cobertura": [asdict(a) for a in acao.descobertas(FORA_DO_REGISTRO)],
                "nao_atribuidas": acao.nao_atribuidas,
            }
            for acao in acoes
        ],
        "sem_cobertura": descobertas,
        "nao_atribuidas": nao_atribuidas,
        "veredito": "PASSOU" if not descobertas and not nao_atribuidas else "REPROVOU",
    }


# ---------------------------------------------------------------------------- sabotagem


def _importar(caminho: Path, nome: str) -> Any:
    especificacao = importlib.util.spec_from_file_location(nome, caminho)
    if especificacao is None or especificacao.loader is None:
        raise ImportError(f"nao consegui importar {caminho}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[nome] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


def auditar_a_sabotagem(arvore: Path, *, caminho_do_tronco: Path = TRONCO) -> dict[str, Any]:
    """Roda cada forma de uma árvore de sabotagem e diz quais o portão pegou.

    A árvore é a mesma que `caissa.ui.audit.progresso --tronco` recebe: um `src/chess_diagram_ocr`
    com o módulo sabotador dentro. **A diferença é que aqui as formas são executadas**, e é por
    isso que "uma forma que a AST não conhece" deixa de ser uma forma que escapa.

    Toda forma cujo nome começa por uma letra e `_` é forma; as que começam por `n` são os
    **controles negativos**, que não abrem trabalho nenhum e cujo silêncio é medido junto: um
    portão que passasse a gritar seria a outra maneira de ficar cego.
    """
    _preparar(caminho_do_tronco)
    from PyQt6.QtWidgets import QApplication

    aplicacao = QApplication.instance() or QApplication(sys.argv[:1])

    def escoar() -> None:
        for _ in range(12):
            aplicacao.processEvents()

    fonte = arvore / "src"
    if str(fonte) not in sys.path:
        sys.path.insert(0, str(fonte))

    # **Os ajudantes da árvore entram em `sys.modules` com o nome real que o sabotador usa.**
    # `sabotador_c9.py` faz `from chess_diagram_ocr.qt.ajudante_de_fundo import em_fundo`, e o
    # `chess_diagram_ocr` que já está importado é o **do tronco**, onde esse módulo não existe.
    # Registrar os da árvore é aditivo (nenhum deles existe no tronco) e é desfeito no fim.
    postos: list[str] = []
    for caminho in sorted((fonte / "chess_diagram_ocr" / "qt").glob("*.py")):
        if caminho.name == "__init__.py" or "sabot" in caminho.name:
            continue
        dotado = f"chess_diagram_ocr.qt.{caminho.stem}"
        if dotado in sys.modules:
            continue
        _importar(caminho, dotado)
        postos.append(dotado)

    modulos = sorted(
        p
        for p in (fonte / "chess_diagram_ocr" / "qt").glob("*.py")
        if p.name not in ("__init__.py",) and "sabot" in p.name
    )
    linhas: list[dict[str, Any]] = []
    nao_importaram: list[dict[str, str]] = []
    for caminho in modulos:
        try:
            modulo = _importar(caminho, f"sabotagem_{caminho.stem}")
        except Exception as exc:  # noqa: BLE001 - um modulo que nao importa e' dado, nao parada
            # **Um portao de execucao so mede o que corre**, e dizer isso e' metade do valor
            # dele. O `sabotador_c9.py` do critico importa `PyQt6.QtCore.QtConcurrent`, que
            # **nao existe neste binding** -- conferido: o nome nao esta em `QtCore.pyd`. A
            # forma (f) daquela sabotagem, portanto, nunca foi executavel nesta maquina, e
            # nenhum portao de execucao poderia te-la observado. Ver `sab_c9x`, a transcricao
            # executavel das oito, onde ela vira o que `QtConcurrent.run` faz por baixo.
            nao_importaram.append({"modulo": caminho.name, "motivo": f"{type(exc).__name__}: {exc}"})
            continue
        for nome_da_classe in dir(modulo):
            classe = getattr(modulo, nome_da_classe)
            if not (isinstance(classe, type) and nome_da_classe.lower().startswith("sabot")):
                continue
            instancia = classe()
            for nome in sorted(dir(instancia)):
                if not _E_FORMA.match(nome):
                    continue
                with observar(nome, simular_processos=True, escoar=escoar) as acao:
                    try:
                        getattr(instancia, nome)()
                    except Exception as exc:  # noqa: BLE001 - a forma que levanta e' dado
                        acao.registros.append(Registro(nome=f"levantou: {exc}", arquivo="", funcao=""))
                pego = bool(acao.aberturas) or bool(acao.nao_atribuidas)
                negativo = nome.startswith("n")
                linhas.append(
                    {
                        "arvore": arvore.name,
                        "modulo": caminho.name,
                        "forma": nome,
                        "negativo": negativo,
                        "aberturas": [asdict(a) for a in acao.aberturas],
                        "nao_atribuidas": acao.nao_atribuidas,
                        "pego": pego,
                        "certo": (not pego) if negativo else pego,
                    }
                )
    for dotado in postos:
        sys.modules.pop(dotado, None)
    formas = [linha for linha in linhas if not linha["negativo"]]
    negativos = [linha for linha in linhas if linha["negativo"]]
    return {
        "arvore": str(arvore),
        "nao_importaram": nao_importaram,
        "formas": len(formas),
        "pegas": sum(1 for linha in formas if linha["pego"]),
        "controles_negativos": len(negativos),
        "negativos_calados": sum(1 for linha in negativos if not linha["pego"]),
        "linhas": linhas,
        "veredito": (
            "PASSOU"
            if linhas and all(linha["certo"] for linha in linhas) and not nao_importaram
            else "REPROVOU"
        ),
    }


def tabela_da_sabotagem(relatorio: dict[str, Any]) -> str:
    linhas = [f"  arvore {Path(relatorio['arvore']).name}", ""]
    for falha in relatorio.get("nao_importaram", []):
        linhas.append(f"  MODULO NAO EXECUTAVEL  {falha['modulo']}: {falha['motivo']}")
    if relatorio.get("nao_importaram"):
        linhas.append("")
    for linha in relatorio["linhas"]:
        tipos = ", ".join(sorted({a["tipo"] for a in linha["aberturas"]})) or "-"
        onde = ", ".join(sorted({f"{a['arquivo']}::{a['funcao']}" for a in linha["aberturas"]}))
        marca = "ok" if linha["certo"] else "<<< ERRADO"
        veredito = "PEGA" if linha["pego"] else "calada"
        rotulo = "controle negativo" if linha["negativo"] else "forma"
        linhas.append(f"  {rotulo:<18} {linha['forma']:<24} {veredito:<7} {marca:<11} {tipos} {onde}")
        for nao in linha["nao_atribuidas"]:
            linhas.append(f"      thread NAO ATRIBUIDA: {nao}")
    linhas.append("")
    linhas.append(
        f"  formas pegas: {relatorio['pegas']} de {relatorio['formas']}   "
        f"controles negativos calados: {relatorio['negativos_calados']} de "
        f"{relatorio['controles_negativos']}   -> {relatorio['veredito']}"
    )
    return "\n".join(linhas)


def tabela(relatorio: dict[str, Any]) -> str:
    linhas = [relatorio["portao"], ""]
    for acao in relatorio["acoes"]:
        linhas.append(
            f"  {acao['nome']:<28} {len(acao['aberturas']):>2} aberturas  "
            f"{len(acao['registros']):>2} registros  "
            f"{len(acao['sem_cobertura']):>2} sem cobertura"
        )
        for abertura in acao["aberturas"]:
            estado = (
                "SEM COBERTURA"
                if abertura in acao["sem_cobertura"]
                else "coberta"
            )
            linhas.append(
                f"      {abertura['tipo']:<26} {abertura['arquivo']}::{abertura['funcao']}"
                f":{abertura['linha']}  {estado}   {abertura['detalhe'][:48]}"
            )
        for nao in acao["nao_atribuidas"]:
            linhas.append(f"      thread NAO ATRIBUIDA: {nao}")
    linhas.append("")
    linhas.append(f"  Aberturas sem cobertura: {len(relatorio['sem_cobertura'])}")
    linhas.append(f"  Threads nao atribuidas : {len(relatorio['nao_atribuidas'])}")
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--pdf", type=Path, default=None)
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
    parser.add_argument(
        "--sabotagem",
        type=Path,
        default=None,
        help="arvore de sabotagem a executar em vez da janela",
    )
    args = parser.parse_args(argv)
    args.saida.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    if args.sabotagem is not None:
        relatorio = auditar_a_sabotagem(args.sabotagem, caminho_do_tronco=args.tronco)
        alvo = args.saida / f"execucao_sab_{args.sabotagem.name}_{carimbo}.json"
        alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
        print(tabela_da_sabotagem(relatorio))
        print(f"\nRelatorio: {alvo}")
        return 0 if relatorio["veredito"] == "PASSOU" else 1

    relatorio = auditar(caminho_do_tronco=args.tronco, pdf=args.pdf)
    alvo = args.saida / f"execucao_{carimbo}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
