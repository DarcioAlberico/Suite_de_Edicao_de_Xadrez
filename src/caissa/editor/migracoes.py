"""A migração do `projeto.json` por `formato` (spec S2, §5.4).

O formato de hoje é o 1. Cada mudança futura de esquema entra em `MIGRACOES` como um passo
`formato n → n + 1`, e `migrar` os encadeia até o atual. Um projeto de formato **mais novo** que
este Caissa é recusado com a frase que diz o que fazer, em vez de ser lido pela metade e regravado
sem os campos que este código não conhece.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

FORMATO_ATUAL = 1

Migracao = Callable[[dict[str, Any]], dict[str, Any]]

#: `formato n` → a função que devolve os dados no formato `n + 1`. Vazia enquanto só existe o 1.
MIGRACOES: dict[int, Migracao] = {}


class FormatoDesconhecido(ValueError):  # noqa: N818 - a frase que a janela mostra
    """O projeto não é de um formato que este Caissa sabe ler."""


def migrar(dados: dict[str, Any], *, atual: int = FORMATO_ATUAL,
           passos: dict[int, Migracao] | None = None) -> dict[str, Any]:
    """Os dados no formato `atual`, pelos passos encadeados; o original não muda."""
    tabela = MIGRACOES if passos is None else passos
    formato = dados.get("formato")
    if not isinstance(formato, int) or isinstance(formato, bool):
        raise FormatoDesconhecido("projeto.json sem o número do formato: o arquivo não é de um "
                                  "projeto do Editor HTML/CSS, ou foi editado à mão")
    if formato > atual:
        raise FormatoDesconhecido(
            f"o projeto é do formato {formato}, e este Caissa lê até o {atual}: abra-o com a "
            "versão do Caissa que o criou, ou atualize este")
    migrado = dict(dados)
    while formato < atual:
        passo = tabela.get(formato)
        if passo is None:
            raise FormatoDesconhecido(f"falta a migração do formato {formato} para o {formato + 1}")
        migrado = passo(dict(migrado))
        formato += 1
        migrado["formato"] = formato
    return migrado
