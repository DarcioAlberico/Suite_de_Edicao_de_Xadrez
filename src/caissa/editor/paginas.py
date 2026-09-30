"""A base das páginas, uma regra só (spec R2.7).

Três números diferentes contam «a página», e confundi-los custou uma rodada no ciclo 2 (a base 1 ×
0 do `labels.csv`). Este módulo é o único lugar que converte um no outro:

- **a página do PDF em base 1** — a que a janela mostra e a que vai nos `id` do livro (`p55-3`,
  `p55-d1`, `pg55`);
- **o índice em base 0** — o do IR (`Provenance.page_index`), das decisões e do sidecar
  (`p54:d1`);
- **o fólio impresso** — o número que o livro imprime na página («54» na p. 55 do PDF do pedido).
  Ele vai só no `aria-label` do marcador de página; na falta, o número do PDF, com a nota «fólio
  não lido» no `proveniencia.json` (nunca no livro).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "Folio",
    "IdDoLivro",
    "chave_v1",
    "folio",
    "id_de_bloco",
    "id_de_diagrama",
    "id_de_marcador",
    "id_de_partida",
    "indice_do_ir",
    "ler_id",
    "marcador_de_pagina",
    "pagina_da_janela",
]

NOTA_SEM_FOLIO = "fólio não lido"
_ID = re.compile(r"^p(?P<pagina>[1-9]\d*)-(?P<tipo>[dg]?)(?P<n>[1-9]\d*)$")
_MARCADOR = re.compile(r"^pg(?P<pagina>[1-9]\d*)$")


def pagina_da_janela(indice: int) -> int:
    """O índice do IR (base 0) como a janela e os `id` o mostram (base 1)."""
    if indice < 0:
        raise ValueError(f"índice de página negativo: {indice}")
    return indice + 1


def indice_do_ir(pagina: int) -> int:
    """A página da janela (base 1) como o IR, as decisões e o sidecar a guardam (base 0)."""
    if pagina < 1:
        raise ValueError(f"a página da janela começa em 1, não em {pagina}")
    return pagina - 1


def _positivo(n: int, o_que: str) -> None:
    if n < 1:
        raise ValueError(f"{o_que} começa em 1, não em {n}")


def id_de_bloco(pagina: int, n: int) -> str:
    """``p55-3``: o terceiro bloco da página 55 do PDF (base 1)."""
    _positivo(pagina, "a página")
    _positivo(n, "a ordem do bloco")
    return f"p{pagina}-{n}"


def id_de_diagrama(pagina: int, n: int) -> str:
    """``p55-d1``: o primeiro diagrama da página 55 do PDF."""
    _positivo(pagina, "a página")
    _positivo(n, "a ordem do diagrama")
    return f"p{pagina}-d{n}"


def id_de_partida(pagina: int, n: int) -> str:
    """``p55-g1``: a primeira partida da página 55 do PDF."""
    _positivo(pagina, "a página")
    _positivo(n, "a ordem da partida")
    return f"p{pagina}-g{n}"


def id_de_marcador(pagina: int) -> str:
    """``pg55``: o marcador da página 55 do PDF."""
    _positivo(pagina, "a página")
    return f"pg{pagina}"


def chave_v1(indice: int, tipo: str, n: int) -> str:
    """A chave da versão 1 do sidecar e das decisões: ``p54:d1`` (índice em base 0)."""
    if tipo not in ("d", "g"):
        raise ValueError(f"tipo de chave desconhecido: {tipo!r}")
    if indice < 0:
        raise ValueError(f"índice de página negativo: {indice}")
    _positivo(n, "a ordem")
    return f"p{indice}:{tipo}{n}"


@dataclass(frozen=True)
class IdDoLivro:
    """Um `id` do livro, lido: a página da janela (base 1), o tipo e a ordem."""

    pagina: int
    tipo: str
    """``"bloco"``, ``"diagrama"``, ``"partida"`` ou ``"marcador"``."""
    n: int

    @property
    def indice(self) -> int:
        """A página em base 0, a do IR."""
        return indice_do_ir(self.pagina)


def ler_id(ident: str) -> IdDoLivro | None:
    """O `id` do livro (`p55-3`, `p55-d1`, `p55-g1`, `pg55`), ou ``None`` se não for um."""
    casado = _ID.match(ident)
    if casado:
        tipo = {"": "bloco", "d": "diagrama", "g": "partida"}[casado["tipo"]]
        return IdDoLivro(int(casado["pagina"]), tipo, int(casado["n"]))
    casado = _MARCADOR.match(ident)
    if casado:
        return IdDoLivro(int(casado["pagina"]), "marcador", 0)
    return None


@dataclass(frozen=True)
class Folio:
    """O número que o marcador da página diz, e se ele foi lido na página."""

    texto: str
    lido: bool

    @property
    def nota(self) -> str | None:
        """A nota do `proveniencia.json` quando o fólio não foi lido; nunca vai ao livro."""
        return None if self.lido else NOTA_SEM_FOLIO


def folio(pagina: int, impresso: str | None) -> Folio:
    """O fólio da página 55 do PDF: o impresso (``running_page_number``), ou o número do PDF."""
    _positivo(pagina, "a página")
    texto = (impresso or "").strip()
    if texto:
        return Folio(texto, True)
    return Folio(str(pagina), False)


def marcador_de_pagina(pagina: int, impresso: str | None) -> str:
    """O marcador de página do contrato (`docs/MARKUP_CAISSA.md` §3), com o fólio no rótulo."""
    from xml.sax.saxutils import quoteattr

    rotulo = folio(pagina, impresso).texto
    return (f'<span epub:type="pagebreak" role="doc-pagebreak" id="{id_de_marcador(pagina)}" '
            f"aria-label={quoteattr(rotulo)}/>")
