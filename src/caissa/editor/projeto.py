"""O projeto do editor em disco (spec S2, R2.1, R2.8, R2.9, R5, §5.3, §5.4; passo H6).

```
editor/<slug>/
  projeto.json        {formato, pdf_sha256, pdf_nome, criado_em, paginas: {"55": {"estado", ...}},
                       espinha, metadados, tema, motor}
  OEBPS/Text/*.xhtml  o que a pessoa edita
  OEBPS/Styles/*.css  as folhas do livro (vão byte a byte ao EPUB)
  diario/             o texto sujo, para a queda não levar o trabalho
  versoes/            uma por gravação (200 MB, as 20 últimas sempre)
  .trava              um livro, uma janela
```

**Nada se perde** (R2.8, `CRITIC_CHARTER` §3.3): toda gravação é atômica (temporário, `fsync`,
`os.replace`), guarda uma versão e apaga a anotação do diário do arquivo; a abertura depois de
uma queda devolve o que o diário tinha e apaga os parciais dos processos mortos. **Um livro, uma
janela:** abrir o mesmo livro de novo, com a primeira janela viva, é recusado pela trava.

**As páginas** são contadas como a spec as escreve: o número da página do PDF, a partir de 1 (a
chave `"55"` de `paginas` é a página 55 do PDF, a mesma do `id="pg55"` do XHTML). A conversão para
o índice 0-based do PyMuPDF é de `editor/paginas.py` (R2.7), não daqui.

**`mudou_por_fora`** compara o arquivo com a última leitura ou gravação deste projeto, por data de
modificação **e** conteúdo: um programa que regrava o mesmo texto não conta como mudança, e um que
muda o texto e devolve a data antiga, conta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from caissa.editor import migracoes
from caissa.editor.diario import Anotacao, Diario, sha256_de
from caissa.editor.gravacao import gravar_atomico, limpar_parciais
from caissa.editor.livros import IndiceDeLivros, raiz_do_editor, sha256_do_pdf
from caissa.editor.trava import Trava, processo_vivo
from caissa.editor.versoes import Versao, Versoes

NOME_DO_PROJETO = "projeto.json"
#: Onde o projeto aceita gravar: o livro, e nada fora dele.
PREFIXO_EDITAVEL = "OEBPS/"


class EstadoDaPagina(StrEnum):
    NAO_GERADA = "NAO_GERADA"
    GERADA = "GERADA"
    EDITADA = "EDITADA"
    REVISADA = "REVISADA"


class CaminhoInvalido(ValueError):  # noqa: N818 - o nome diz o que houve, como PaginaInvalida
    """O arquivo pedido não é do livro (fora de `OEBPS/`, absoluto, ou com `..`)."""


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def validar_arquivo(arquivo: str) -> str:
    """O caminho relativo POSIX dentro de `OEBPS/`, ou `CaminhoInvalido`."""
    caminho = PurePosixPath(arquivo.replace("\\", "/"))
    if caminho.is_absolute() or ".." in caminho.parts or ":" in arquivo:
        raise CaminhoInvalido(f"{arquivo}: o editor só grava dentro do livro")
    texto = caminho.as_posix()
    if not texto.startswith(PREFIXO_EDITAVEL) or texto == PREFIXO_EDITAVEL.rstrip("/"):
        raise CaminhoInvalido(f"{arquivo}: o editor só grava em {PREFIXO_EDITAVEL}")
    return texto


@dataclass
class _Visto:
    """O que este projeto leu ou gravou por último num arquivo."""

    mtime_ns: int
    sha256: str


@dataclass
class ProjetoDoEditor:
    pasta: Path
    dados: dict[str, Any]
    trava: Trava
    diario: Diario = field(init=False)
    versoes: Versoes = field(init=False)
    _vistos: dict[str, _Visto] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.diario = Diario(self.pasta)
        self.versoes = Versoes(self.pasta)

    # ------------------------------------------------------------------ abrir e criar

    @classmethod
    def criar(cls, pdf: Path | str, paginas: list[int] | tuple[int, ...] | None = None, *,
              raiz: Path | str | None = None) -> ProjetoDoEditor:
        """O projeto do livro, novo — ou o que já existe, aberto (a chave é o conteúdo do PDF).

        `paginas` são as páginas do PDF (a partir de 1) que o projeto cobre; sem elas, o livro
        inteiro. Todas nascem `NAO_GERADA`.
        """
        caminho_pdf = Path(pdf)
        sha = sha256_do_pdf(caminho_pdf)
        indice = IndiceDeLivros(raiz_do_editor(raiz))
        if indice.pasta_de(sha) is not None and (indice.pasta_de(sha) / NOME_DO_PROJETO).is_file():
            return cls.abrir(caminho_pdf, raiz=raiz)
        pasta = indice.registrar(sha, caminho_pdf.name)
        trava = Trava.adquirir(pasta)
        try:
            numeros = list(paginas) if paginas is not None else _todas_as_paginas(caminho_pdf)
            dados = {
                "formato": migracoes.FORMATO_ATUAL,
                "pdf_sha256": sha,
                "pdf_nome": caminho_pdf.name,
                "criado_em": _agora(),
                "paginas": {str(n): {"estado": str(EstadoDaPagina.NAO_GERADA)}
                            for n in sorted(set(numeros))},
                "espinha": [],
                "metadados": {},
                "tema": None,
                "motor": "mupdf",
            }
            for sub in ("OEBPS/Text", "OEBPS/Styles", "OEBPS/Images"):
                (pasta / sub).mkdir(parents=True, exist_ok=True)
            projeto = cls(pasta, dados, trava)
            projeto._gravar_projeto()
        except BaseException:
            trava.soltar()
            raise
        return projeto

    @classmethod
    def abrir(cls, pdf: Path | str, *, raiz: Path | str | None = None) -> ProjetoDoEditor:
        """O projeto que já existe para este PDF (a chave é o conteúdo); `FileNotFoundError`."""
        sha = sha256_do_pdf(pdf)
        pasta = IndiceDeLivros(raiz_do_editor(raiz)).pasta_de(sha)
        if pasta is None or not (pasta / NOME_DO_PROJETO).is_file():
            raise FileNotFoundError(f"não há projeto do Editor HTML/CSS para {Path(pdf).name}")
        return cls.abrir_pasta(pasta)

    @classmethod
    def abrir_pasta(cls, pasta: Path) -> ProjetoDoEditor:
        trava = Trava.adquirir(pasta)
        try:
            bruto = json.loads((pasta / NOME_DO_PROJETO).read_text(encoding="utf-8"))
            dados = migracoes.migrar(bruto)
            projeto = cls(pasta, dados, trava)
            if dados != bruto:
                projeto._gravar_projeto()
            limpar_parciais(pasta, processo_vivo)
        except BaseException:
            trava.soltar()
            raise
        return projeto

    def fechar(self) -> None:
        self.trava.soltar()

    def __enter__(self) -> ProjetoDoEditor:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    # ------------------------------------------------------------------ arquivos

    def arquivos(self) -> list[str]:
        """Os arquivos do livro, na ordem da espinha e depois os demais em ordem de nome."""
        raiz = self.pasta / PREFIXO_EDITAVEL
        todos = sorted(p.relative_to(self.pasta).as_posix() for p in raiz.rglob("*")
                       if p.is_file() and not p.name.startswith("."))
        espinha = [a for a in self.dados.get("espinha", []) if a in todos]
        return espinha + [a for a in todos if a not in espinha]

    def ler(self, arquivo: str) -> str:
        caminho = self.pasta / validar_arquivo(arquivo)
        dados = caminho.read_bytes()
        self._vistos[validar_arquivo(arquivo)] = _Visto(caminho.stat().st_mtime_ns,
                                                        sha256_de(dados))
        return dados.decode("utf-8")

    def gravar(self, arquivo: str, texto: str) -> str:
        """Grava atômico, guarda a versão, apaga a anotação do diário; devolve o carimbo."""
        relativo = validar_arquivo(arquivo)
        caminho = self.pasta / relativo
        dados = texto.encode("utf-8")
        gravar_atomico(caminho, dados)
        self._vistos[relativo] = _Visto(caminho.stat().st_mtime_ns, sha256_de(dados))
        carimbo = self.versoes.guardar(relativo, dados)
        self.diario.descartar(relativo)
        return carimbo

    def mudou_por_fora(self, arquivo: str) -> bool:
        """O arquivo não é mais o que este projeto leu ou gravou por último."""
        relativo = validar_arquivo(arquivo)
        visto = self._vistos.get(relativo)
        caminho = self.pasta / relativo
        if visto is None:
            return False
        if not caminho.is_file():
            return True
        if caminho.stat().st_mtime_ns == visto.mtime_ns:
            # A data é a mesma; o conteúdo ainda pode ter mudado (quem devolve a data antiga).
            return sha256_de(caminho.read_bytes()) != visto.sha256
        return sha256_de(caminho.read_bytes()) != visto.sha256

    # ------------------------------------------------------------------ diário e versões

    def anotar(self, arquivo: str, texto: str) -> None:
        """O texto sujo de `arquivo` vai ao diário (a janela chama até 2 s depois da mudança)."""
        relativo = validar_arquivo(arquivo)
        visto = self._vistos.get(relativo)
        base = visto.sha256 if visto else self._sha_no_disco(relativo)
        self.diario.anotar(relativo, texto, base_sha256=base)

    def recuperar_do_diario(self) -> dict[str, Anotacao]:
        """As anotações que sobraram de uma queda, por arquivo — o que a gravação não levou."""
        saida = {}
        for anotacao in self.diario.anotacoes():
            try:
                relativo = validar_arquivo(anotacao.arquivo)
            except CaminhoInvalido:
                continue
            if anotacao.texto.encode("utf-8") != self._bytes_no_disco(relativo):
                saida[relativo] = anotacao
        return saida

    def versao(self, arquivo: str | None = None) -> list[Versao]:
        return self.versoes.listar(None if arquivo is None else validar_arquivo(arquivo))

    def restaurar(self, carimbo: str, arquivo: str) -> str:
        """Grava de novo o conteúdo da versão (uma gravação: desfeita restaurando a anterior)."""
        relativo = validar_arquivo(arquivo)
        return self.gravar(relativo, self.versoes.ler(carimbo, relativo).decode("utf-8"))

    # ------------------------------------------------------------------ páginas

    def estado(self, pagina: int) -> EstadoDaPagina:
        entrada = self.dados["paginas"].get(str(pagina))
        return EstadoDaPagina(entrada["estado"]) if entrada else EstadoDaPagina.NAO_GERADA

    def marcar(self, paginas: list[int] | tuple[int, ...], estado: EstadoDaPagina) -> None:
        agora = _agora()
        for numero in paginas:
            entrada = self.dados["paginas"].setdefault(str(numero), {})
            entrada["estado"] = str(estado)
            if estado is EstadoDaPagina.EDITADA:
                entrada["editada_em"] = agora
            elif estado is EstadoDaPagina.REVISADA:
                entrada["revisada_em"] = agora
            elif estado is EstadoDaPagina.GERADA:
                entrada["gerada_em"] = agora
        self._gravar_projeto()

    def marcar_editada(self, paginas: list[int] | tuple[int, ...]) -> None:
        self.marcar(paginas, EstadoDaPagina.EDITADA)

    # ------------------------------------------------------------------ interno

    def _gravar_projeto(self) -> None:
        gravar_atomico(self.pasta / NOME_DO_PROJETO,
                       json.dumps(self.dados, ensure_ascii=False, indent=1) + "\n")

    def _bytes_no_disco(self, relativo: str) -> bytes | None:
        caminho = self.pasta / relativo
        return caminho.read_bytes() if caminho.is_file() else None

    def _sha_no_disco(self, relativo: str) -> str:
        dados = self._bytes_no_disco(relativo)
        return sha256_de(dados) if dados is not None else ""


def _todas_as_paginas(pdf: Path) -> list[int]:
    import pymupdf

    with pymupdf.open(pdf) as documento:
        return list(range(1, documento.page_count + 1))
