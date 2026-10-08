"""O diário: o texto sujo de cada arquivo, para a queda não levar o trabalho (spec §5.3, R2.8).

A janela anota o texto de um arquivo sujo **até 2 s depois** de cada mudança (o temporizador é da
janela, H11/H17); gravar o arquivo apaga a anotação dele. Depois de uma queda, a próxima abertura
acha as anotações que sobraram e oferece «Recuperar» com a diferença à vista.

Cada anotação guarda o **hash do arquivo de onde a edição partiu**. Na recuperação isso separa os
dois casos que parecem iguais: a anotação sobre o arquivo como ele está (o trabalho perdido pela
queda) e a anotação sobre um arquivo que mudou por fora depois dela (aí é conflito, e quem decide
é a pessoa, com a diferença).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

from caissa.editor.gravacao import gravar_atomico

PASTA = "diario"


def sha256_de(dados: bytes | str) -> str:
    conteudo = dados.encode("utf-8") if isinstance(dados, str) else dados
    return hashlib.sha256(conteudo).hexdigest()


@dataclass(frozen=True)
class Anotacao:
    arquivo: str
    texto: str
    base_sha256: str
    quando: float


class Diario:
    """As anotações de um projeto, uma por arquivo sujo."""

    def __init__(self, projeto: Path) -> None:
        self.pasta = projeto / PASTA

    def _caminho(self, arquivo: str) -> Path:
        return self.pasta / (quote(arquivo, safe="") + ".json")

    def anotar(self, arquivo: str, texto: str, *, base_sha256: str,
               quando: float | None = None) -> None:
        anotacao = {"arquivo": arquivo, "texto": texto, "base_sha256": base_sha256,
                    "quando": time.time() if quando is None else quando}
        gravar_atomico(self._caminho(arquivo), json.dumps(anotacao, ensure_ascii=False))

    def descartar(self, arquivo: str) -> None:
        self._caminho(arquivo).unlink(missing_ok=True)

    def anotacoes(self) -> list[Anotacao]:
        """As anotações legíveis; uma ilegível (queda no meio da escrita dela) não existe."""
        if not self.pasta.is_dir():
            return []
        saida = []
        for caminho in sorted(self.pasta.glob("*.json")):
            try:
                dados = json.loads(caminho.read_text(encoding="utf-8"))
                saida.append(Anotacao(str(dados["arquivo"]), str(dados["texto"]),
                                      str(dados["base_sha256"]), float(dados["quando"])))
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if unquote(caminho.stem) != saida[-1].arquivo:
                saida.pop()
        return saida
