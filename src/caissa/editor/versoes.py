"""As versões: uma por gravação, até 200 MB, e as 20 últimas sempre guardadas (spec S2, R2.8).

Toda gravação de um arquivo do projeto guarda o conteúdo gravado em `versoes/<carimbo>/<arquivo>`.
A poda tira as mais velhas quando o total passa do teto — **menos as 20 mais novas**, que ficam
mesmo que sozinhas passem dele: o piso vence o teto, porque é ele que garante «desfazer as últimas
gravações» a quem trabalha num livro de imagens grandes.

O carimbo é o relógio em nanossegundos mais um contador: ordena em ordem de criação e não colide
entre duas gravações no mesmo tique.
"""

from __future__ import annotations

import itertools
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from caissa.editor.gravacao import gravar_atomico

PASTA = "versoes"
TETO_BYTES = 200 * 1024 * 1024
PISO = 20

_contador = itertools.count()


@dataclass(frozen=True)
class Versao:
    carimbo: str
    arquivo: str
    tamanho: int

    @property
    def quando(self) -> float:
        return int(self.carimbo.split("-")[0]) / 1e9


class Versoes:
    def __init__(self, projeto: Path, *, teto_bytes: int = TETO_BYTES, piso: int = PISO) -> None:
        self.pasta = projeto / PASTA
        self.teto_bytes = teto_bytes
        self.piso = piso

    def guardar(self, arquivo: str, dados: bytes) -> str:
        """Guarda uma versão de `arquivo` e poda; devolve o carimbo."""
        carimbo = f"{time.time_ns():020d}-{next(_contador) % 10**6:06d}"
        gravar_atomico(self.pasta / carimbo / arquivo, dados)
        self.podar()
        return carimbo

    def listar(self, arquivo: str | None = None) -> list[Versao]:
        """As versões, da mais nova para a mais velha."""
        if not self.pasta.is_dir():
            return []
        saida = []
        for pasta in sorted(self.pasta.iterdir(), reverse=True):
            if not pasta.is_dir():
                continue
            for caminho in sorted(p for p in pasta.rglob("*") if p.is_file()):
                relativo = caminho.relative_to(pasta).as_posix()
                if arquivo is None or relativo == arquivo:
                    saida.append(Versao(pasta.name, relativo, caminho.stat().st_size))
        return saida

    def ler(self, carimbo: str, arquivo: str) -> bytes:
        return (self.pasta / carimbo / arquivo).read_bytes()

    def podar(self) -> list[str]:
        """Apaga as mais velhas além do teto, nunca uma das `piso` mais novas."""
        if not self.pasta.is_dir():
            return []
        carimbos = sorted((p for p in self.pasta.iterdir() if p.is_dir()), reverse=True)
        tamanhos = {p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                    for p in carimbos}
        total = sum(tamanhos.values())
        apagados = []
        for pasta in reversed(carimbos[self.piso:]):      # das mais velhas para as mais novas
            if total <= self.teto_bytes:
                break
            total -= tamanhos[pasta]
            shutil.rmtree(pasta, ignore_errors=True)
            apagados.append(pasta.name)
        return apagados

    def total_bytes(self) -> int:
        if not self.pasta.is_dir():
            return 0
        return sum(f.stat().st_size for f in self.pasta.rglob("*") if f.is_file())
