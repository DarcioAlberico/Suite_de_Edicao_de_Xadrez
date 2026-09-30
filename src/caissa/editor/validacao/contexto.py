"""O contexto da validação: o projeto em volta do arquivo que se valida.

Uma camada é `(documento, contexto) → [Problema]`. O contexto diz o que o arquivo sozinho não
diz: os outros arquivos do projeto (a folha ligada, a imagem, a fonte), o motor da prévia, a
lista de abreviaturas, o glossário, o mapa da proveniência e as fontes do registro. Tudo é
opcional: a regra que precisa de um dado que o contexto não tem não roda (e não acusa).
"""

from __future__ import annotations

import posixpath
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ABREVIATURAS", "Contexto", "resolver"]

ABREVIATURAS: tuple[str, ...] = ("GM", "MI", "MF", "WGM", "WIM", "IM", "FM", "CM", "FIDE", "ECO")
"""As abreviaturas que o livro marca com `<abbr title>` (WCAG 3.1.4; spec §5.6)."""


def resolver(arquivo: str, href: str) -> str | None:
    """O caminho no projeto de um `href` relativo a `arquivo`, ou `None` se ele sai do projeto.

    O fragmento (`#x`) e a consulta caem. Um endereço com esquema, um caminho absoluto ou um que
    sobe além da raiz do livro não se resolvem dentro dele.
    """
    alvo = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not alvo:
        return arquivo
    if ":" in alvo.split("/", 1)[0] or alvo.startswith(("/", "\\")):
        return None
    caminho = posixpath.normpath(posixpath.join(posixpath.dirname(arquivo),
                                                alvo.replace("\\", "/")))
    if caminho == ".." or caminho.startswith("../"):
        return None
    return caminho


@dataclass
class Contexto:
    """O projeto em volta do arquivo."""

    arquivos: Mapping[str, bytes] = field(default_factory=dict)
    """Os arquivos do projeto, pelo caminho relativo à raiz do livro (`Text/cap1.xhtml`)."""
    raiz: Path | None = None
    """A pasta do livro no disco, quando há (a conferência do link simbólico para fora)."""
    motor: str = "mupdf"
    """O motor da prévia ativa: `mupdf` ou `chromium`."""
    abreviaturas: tuple[str, ...] = ABREVIATURAS
    glossario: frozenset[str] | None = None
    """Os símbolos e termos definidos no glossário do livro; `None` quando ele ainda não existe."""
    mapa: Any = None
    """O `MapaDaProveniencia` do projeto (o `proveniencia.json`), quando há."""
    fontes: Mapping[str, str] = field(default_factory=dict)
    """Família → o arquivo da fonte (ou o nome de uma fonte embutida do MuPDF)."""
    medir_contraste: bool = True
    idioma: str = "pt-BR"
    """A língua do livro (o conserto do `lang` a usa)."""

    def texto(self, caminho: str) -> str | None:
        dados = self.arquivos.get(caminho)
        return dados.decode("utf-8", "replace") if dados is not None else None
