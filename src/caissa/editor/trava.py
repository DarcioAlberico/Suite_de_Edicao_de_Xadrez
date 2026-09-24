"""Um livro, uma janela: a trava do projeto do editor (spec S2 `.trava`, §5.3, R5).

**O mecanismo é o de `ocr.diagram_decisions._locked`, com o que faltava lá.** A criação com
`O_CREAT | O_EXCL` é atômica em todo sistema de arquivos local: dois processos que tentam ao mesmo
tempo, um ganha e o outro vê `FileExistsError`. Lá a trava vive segundos e «mais velha que um
minuto é queda». Aqui ela vive enquanto a janela estiver aberta — horas —, então a idade não diz
nada, e o arquivo guarda **quem** a tem:

- o **PID** do dono: trava de processo morto é retomada na hora (a queda da janela não prende o
  livro até alguém apagar um arquivo à mão);
- a **validade**, que o dono renova (`renovar`, a cada minuto pela janela): um PID reaproveitado
  pelo Windows depois da queda parece vivo para sempre, e a validade vencida desempata.

**A retomada tem a própria trava.** Dois processos que acham a mesma trava vencida não podem os
dois apagá-la e criar a sua: o segundo apagaria a trava nova do primeiro. Quem retoma cria antes
`.trava.retomando` com `O_EXCL`, relê a trava e só a apaga se ela ainda é a mesma que julgou
vencida.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from caissa.editor.gravacao import gravar_atomico

NOME = ".trava"
NOME_DA_RETOMADA = ".trava.retomando"
#: Por quanto tempo a trava vale sem renovação. A janela renova a cada minuto.
VALIDADE_S = 10 * 60.0
#: Uma trava sem conteúdo legível é de quem acabou de criá-la e ainda não escreveu — ou de quem
#: morreu entre as duas coisas. Passado este tempo, é queda.
CRIACAO_EM_CURSO_S = 5.0
#: A trava da retomada é de uma operação de milissegundos; mais velha que isto é queda.
RETOMADA_VENCIDA_S = 10.0


class LivroJaAberto(RuntimeError):  # noqa: N818 - um estado, não um defeito
    """O livro já está aberto numa janela viva."""

    def __init__(self, caminho: Path, dono: DonoDaTrava | None) -> None:
        self.caminho = caminho
        self.dono = dono
        quem = f"pelo processo {dono.pid} em {dono.maquina}" if dono else "por outro processo"
        super().__init__(
            f"Este livro já está aberto {quem}. Feche aquela janela do Editor HTML/CSS, ou "
            "traga-a à frente, em vez de abrir outra.")


def processo_vivo(pid: int) -> bool:
    """O processo `pid` ainda existe nesta máquina?"""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        return _vivo_no_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _vivo_no_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    consulta_limitada = 0x1000          # PROCESS_QUERY_LIMITED_INFORMATION
    ainda_ativo = 259                   # STILL_ACTIVE
    acesso_negado = 5                   # ERROR_ACCESS_DENIED: existe, e não é nosso
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    identificador = kernel32.OpenProcess(consulta_limitada, False, pid)
    if not identificador:
        return ctypes.get_last_error() == acesso_negado
    try:
        codigo = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(identificador, ctypes.byref(codigo)):
            return True
        return codigo.value == ainda_ativo
    finally:
        kernel32.CloseHandle(identificador)


@dataclass(frozen=True)
class DonoDaTrava:
    pid: int
    maquina: str
    desde: float
    ate: float

    def valida(self, agora: float, vivo: Callable[[int], bool] = processo_vivo) -> bool:
        """Vale enquanto o dono vive e renova; nesta máquina (a de outra não se consulta)."""
        if self.maquina != platform.node():
            return agora <= self.ate
        return agora <= self.ate and vivo(self.pid)

    def como_json(self) -> str:
        return json.dumps({"pid": self.pid, "maquina": self.maquina,
                           "desde": self.desde, "ate": self.ate})


def ler_dono(caminho: Path) -> DonoDaTrava | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return DonoDaTrava(int(dados["pid"]), str(dados["maquina"]), float(dados["desde"]),
                           float(dados["ate"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


class Trava:
    """A trava de um projeto, na mão de quem a adquiriu."""

    def __init__(self, caminho: Path, dono: DonoDaTrava, validade_s: float) -> None:
        self.caminho = caminho
        self.dono = dono
        self.validade_s = validade_s
        self.solta = False

    @classmethod
    def adquirir(cls, pasta: Path, *, validade_s: float = VALIDADE_S,
                 relogio: Callable[[], float] = time.time,
                 vivo: Callable[[int], bool] = processo_vivo) -> Trava:
        """A trava de `pasta`, ou `LivroJaAberto` quando uma janela viva a tem."""
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / NOME
        for _ in range(20):
            agora = relogio()
            dono = DonoDaTrava(os.getpid(), platform.node(), agora, agora + validade_s)
            try:
                descritor = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                atual = ler_dono(caminho)
                if atual is not None and atual.valida(agora, vivo):
                    raise LivroJaAberto(caminho, atual) from None
                if atual is None and _idade(caminho, agora) < CRIACAO_EM_CURSO_S:
                    time.sleep(0.05)             # alguém acabou de criar e ainda vai escrever
                    continue
                _retomar(caminho, atual, agora)
                continue
            with os.fdopen(descritor, "w", encoding="utf-8") as saida:
                saida.write(dono.como_json())
            return cls(caminho, dono, validade_s)
        raise LivroJaAberto(caminho, ler_dono(caminho))

    def renovar(self, *, relogio: Callable[[], float] = time.time) -> None:
        """Empurra a validade para a frente; a janela chama a cada minuto."""
        if self.solta:
            return
        agora = relogio()
        self.dono = DonoDaTrava(self.dono.pid, self.dono.maquina, self.dono.desde,
                                agora + self.validade_s)
        gravar_atomico(self.caminho, self.dono.como_json())

    def soltar(self) -> None:
        """Apaga a trava — só se ela ainda é nossa (uma retomada pode tê-la levado)."""
        if self.solta:
            return
        self.solta = True
        atual = ler_dono(self.caminho)
        if atual is not None and atual.pid == self.dono.pid and atual.desde == self.dono.desde:
            self.caminho.unlink(missing_ok=True)

    def __enter__(self) -> Trava:
        return self

    def __exit__(self, *_: object) -> None:
        self.soltar()


def _idade(caminho: Path, agora: float) -> float:
    try:
        return agora - caminho.stat().st_mtime
    except OSError:
        return 0.0


def _retomar(caminho: Path, vencida: DonoDaTrava | None, agora: float) -> None:
    """Apaga a trava vencida sob a trava da retomada, se ela ainda é a mesma que se julgou."""
    retomada = caminho.with_name(NOME_DA_RETOMADA)
    if retomada.exists() and _idade(retomada, agora) > RETOMADA_VENCIDA_S:
        retomada.unlink(missing_ok=True)
    try:
        descritor = os.open(retomada, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        time.sleep(0.05)                          # outro processo está retomando; tenta de novo
        return
    os.close(descritor)
    try:
        if ler_dono(caminho) == vencida:
            with contextlib.suppress(FileNotFoundError):
                caminho.unlink()
    finally:
        retomada.unlink(missing_ok=True)


@contextlib.contextmanager
def travado(pasta: Path, **opcoes: object) -> Iterator[Trava]:
    trava = Trava.adquirir(pasta, **opcoes)  # type: ignore[arg-type]
    try:
        yield trava
    finally:
        trava.soltar()
