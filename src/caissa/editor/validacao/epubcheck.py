"""A camada do EPUBCheck (spec S10): o livro montado, mensagem a mensagem, com o local.

O `run_epubcheck` de `caissa.export.epubcheck` lê só o resumo («0 erros»); o `--json` dá cada
mensagem com o arquivo, a linha e a coluna. O caminho de dentro do pacote (`OEBPS/Text/cap1.xhtml`)
volta ao do projeto (`Text/cap1.xhtml`): a pasta do projeto é a do `OEBPS`.
"""

from __future__ import annotations

from pathlib import Path

from caissa.editor.validacao.problema import Local, Problema, Severidade, regra
from caissa.export.epubcheck import EpubCheckMessage, find_epubcheck_jar, run_epubcheck_json

__all__ = ["problemas_das_mensagens", "verificar_epub"]

E = "epubcheck"
ERRO = regra("epubcheck-erro", E, Severidade.BLOQUEIA, "O EPUBCheck acusa um erro",
             "Corrija no ponto indicado: o EPUB com erro não se publica.")
AVISO = regra("epubcheck-aviso", E, Severidade.AVISA, "O EPUBCheck avisa",
              "Confira no ponto indicado.")
NOTA = regra("epubcheck-nota", E, Severidade.INFORMA, "O EPUBCheck informa",
             "Vale saber; nada a corrigir por força.")
_POR_SEVERIDADE = {"FATAL": ERRO, "ERROR": ERRO, "WARNING": AVISO}
PREFIXO_DO_PACOTE = "OEBPS/"


def problemas_das_mensagens(mensagens: list[EpubCheckMessage]) -> list[Problema]:
    """As mensagens do EPUBCheck como problemas do projeto.

    O local que o EPUBCheck dá passa inteiro; a mensagem que ele dá sem local (a que vem depois
    de um erro fatal, por exemplo) fica com a linha e a coluna 0 — o arquivo, sem posição —, e
    não finge um `1:1`.
    """
    problemas = []
    for mensagem in mensagens:
        caminho = mensagem.path.removeprefix(PREFIXO_DO_PACOTE) or "(o pacote)"
        local = Local(caminho, max(mensagem.line, 0), max(mensagem.column, 0))
        problemas.append(Problema(_POR_SEVERIDADE.get(mensagem.severity.upper(), NOTA), local,
                                  f"{mensagem.id}: {mensagem.message}"))
    return problemas


def verificar_epub(epub: Path, *, jar: Path | None = None) -> list[Problema]:
    """O EPUBCheck num EPUB montado.

    Raises:
        FileNotFoundError: Não há `epubcheck.jar` nesta máquina.
    """
    jar = jar if jar is not None else find_epubcheck_jar()
    if jar is None:
        raise FileNotFoundError("epubcheck.jar não achado (tools/instalar_epubcheck.py)")
    return problemas_das_mensagens(run_epubcheck_json(jar, epub))
