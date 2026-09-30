"""O problema da validação (spec S10): código, severidade, local, o que fazer e o conserto.

O conserto vem só quando é seguro. Toda regra do validador é declarada aqui, uma vez, por
`regra()`: o código, a camada, a severidade, o título e o que fazer. A camada não inventa código
na hora de acusar — ela aponta a `Regra` —, e o portão do H10 confere que toda regra registrada
tem a sua fixture de defeito.

Severidade:

- **bloqueia** — a exportação recusa (R4.2) ou o livro afirma algo falso;
- **avisa** — alguém tem de olhar e decidir;
- **informa** — vale saber (o motor da prévia não desenha, o DOCX não leva).

O local é `arquivo:linha:coluna`, as duas contadas a partir de 1, como os editores mostram.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "REGRAS",
    "Conserto",
    "Local",
    "Problema",
    "Regra",
    "Severidade",
    "Troca",
    "regra",
]


class Severidade(StrEnum):
    BLOQUEIA = "bloqueia"
    AVISA = "avisa"
    INFORMA = "informa"


@dataclass(frozen=True, slots=True)
class Local:
    """Onde: o arquivo do projeto (`Text/cap1.xhtml`), a linha e a coluna, de 1.

    A linha e a coluna 0 dizem «o arquivo, sem posição»: a mensagem do EPUBCheck que vem sem
    local.
    """

    arquivo: str
    linha: int
    coluna: int

    def __str__(self) -> str:
        return f"{self.arquivo}:{self.linha}:{self.coluna}"


@dataclass(frozen=True, slots=True)
class Troca:
    """Trocar `texto[inicio:fim]` por `novo` (posições no texto do arquivo)."""

    inicio: int
    fim: int
    novo: str


@dataclass(frozen=True, slots=True)
class Conserto:
    """O conserto seguro de um problema: o que ele faz, dito, e as trocas no texto."""

    descricao: str
    trocas: tuple[Troca, ...]

    def aplicar(self, texto: str) -> str:
        """O texto com as trocas, do fim para o começo (as posições não se movem)."""
        for troca in sorted(self.trocas, key=lambda t: t.inicio, reverse=True):
            texto = texto[:troca.inicio] + troca.novo + texto[troca.fim:]
        return texto


@dataclass(frozen=True, slots=True)
class Regra:
    """Uma regra do validador."""

    codigo: str
    camada: str
    severidade: Severidade
    titulo: str
    o_que_fazer: str


REGRAS: dict[str, Regra] = {}
"""Toda regra, pelo código (o portão confere uma fixture por regra)."""


def regra(codigo: str, camada: str, severidade: Severidade, titulo: str,
          o_que_fazer: str) -> Regra:
    """Declara uma regra (uma vez por código).

    Raises:
        ValueError: O código já está registrado com outra definição.
    """
    nova = Regra(codigo, camada, severidade, titulo, o_que_fazer)
    antiga = REGRAS.get(codigo)
    if antiga is not None and antiga != nova:
        raise ValueError(f"a regra {codigo} já foi declarada de outro jeito")
    REGRAS[codigo] = nova
    return nova


@dataclass(frozen=True, slots=True)
class Problema:
    """Um problema achado: a regra, o local, o detalhe deste caso e o conserto, se houver."""

    regra: Regra
    local: Local
    detalhe: str = ""
    conserto: Conserto | None = None

    @property
    def codigo(self) -> str:
        return self.regra.codigo

    @property
    def severidade(self) -> Severidade:
        return self.regra.severidade

    @property
    def camada(self) -> str:
        return self.regra.camada

    @property
    def mensagem(self) -> str:
        return f"{self.regra.titulo}: {self.detalhe}" if self.detalhe else self.regra.titulo

    def __str__(self) -> str:
        return f"{self.local} [{self.severidade}] {self.codigo} — {self.mensagem}"

    def como_dict(self) -> dict[str, Any]:
        return {"codigo": self.codigo, "camada": self.camada, "severidade": str(self.severidade),
                "arquivo": self.local.arquivo, "linha": self.local.linha,
                "coluna": self.local.coluna, "mensagem": self.mensagem,
                "o_que_fazer": self.regra.o_que_fazer,
                "conserto": self.conserto.descricao if self.conserto else None}
