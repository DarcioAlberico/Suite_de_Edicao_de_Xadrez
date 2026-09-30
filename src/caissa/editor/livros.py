"""Onde mora cada projeto: a raiz do editor e o índice SHA-256 do PDF → pasta (spec S2, §5.4, R5).

**A raiz segue a do `labeling/`** (`ocr.labeling.helpers.default_project_dir`): `editor/` na raiz
do repositório num checkout (o git a ignora), `editor/` ao lado do `Caissa.exe` no pacote — onde o
build não toca, porque ela está em `PASTAS_GUARDADAS` —, e `CAISSA_EDITOR_DIR` sobrepõe as duas.

**A chave do livro é o conteúdo, não o nome.** O mesmo PDF renomeado continua achando o seu
projeto, e dois livros de mesmo nome não dividem um. O nome da pasta é só legível: o slug do nome
do PDF, com um número quando dois livros diferentes dariam o mesmo.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.editor.gravacao import gravar_atomico

VARIAVEL_DA_RAIZ = "CAISSA_EDITOR_DIR"
NOME_DO_INDICE = "livros.json"
TAMANHO_DO_SLUG = 60


def raiz_do_editor(explicita: Path | str | None = None) -> Path:
    """A pasta dos projetos: o argumento, `$CAISSA_EDITOR_DIR`, ou a padrão do checkout/pacote."""
    if explicita:
        return Path(explicita)
    do_ambiente = os.environ.get(VARIAVEL_DA_RAIZ, "")
    if do_ambiente:
        return Path(do_ambiente)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "editor"
    return Path(__file__).resolve().parents[3] / "editor"


def sha256_do_pdf(caminho: Path | str) -> str:
    """O SHA-256 dos bytes do PDF — o mesmo `PdfDocument.content_hash` que o resto usa."""
    from caissa.ocr.training.books import pdf_fingerprint

    return pdf_fingerprint(caminho)


def slug(nome: str) -> str:
    """Um nome de pasta legível e seguro em qualquer sistema: minúsculas ASCII e hífens."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    limpo = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return limpo[:TAMANHO_DO_SLUG].rstrip("-") or "livro"


class IndiceDeLivros:
    """`editor/livros.json`: `{sha256: {"pasta", "pdf_nome", "criado_em"}}`."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.caminho = raiz / NOME_DO_INDICE

    def ler(self) -> dict[str, dict[str, Any]]:
        if not self.caminho.is_file():
            return {}
        dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            raise ValueError(f"{self.caminho}: o índice dos livros não é um objeto")
        return dados

    def pasta_de(self, sha256: str) -> Path | None:
        entrada = self.ler().get(sha256)
        return self.raiz / entrada["pasta"] if entrada else None

    def registrar(self, sha256: str, pdf_nome: str) -> Path:
        """A pasta do livro: a que o índice já tem, ou uma nova com slug único."""
        indice = self.ler()
        if sha256 in indice:
            return self.raiz / indice[sha256]["pasta"]
        usados = {str(e.get("pasta", "")) for e in indice.values()}
        base = slug(Path(pdf_nome).stem)
        nome, numero = base, 2
        while nome in usados or (self.raiz / nome).exists():
            nome, numero = f"{base}-{numero}", numero + 1
        indice[sha256] = {"pasta": nome, "pdf_nome": pdf_nome,
                          "criado_em": datetime.now(UTC).isoformat(timespec="seconds")}
        self.raiz.mkdir(parents=True, exist_ok=True)
        gravar_atomico(self.caminho, json.dumps(indice, ensure_ascii=False, indent=1) + "\n")
        return self.raiz / nome
