"""O que fica FORA do bundle e chega ao usuario depois -- pesos e lexicos (F12).

Por que este modulo existe
--------------------------
A SPEC secao 12 pede o instalador **abaixo de 150 MB** e diz, na mesma frase, como:
*"Modelos baixados sob demanda no primeiro uso, com verificacao de integridade SHA-256 e
opcao de instalacao offline por pacote."* Sao duas exigencias diferentes e este arquivo
atende as duas, mais uma terceira que a SPEC nao previa e a LICENSING.md explica: **dois
dos cinco componentes tem licenca nao apurada e por isso nao podem viajar dentro do
binario nem ser instalados sem o usuario dizer que sim.**

O manifesto (`manifesto.json`) e a unica fonte de verdade. Cada entrada carrega o hash e o
tamanho medidos em disco, o que o componente faz, e -- a parte que costuma faltar -- **o
que acontece se ele nao estiver la**. Um instalador que so diz "faltou o modelo" transfere
para o usuario um diagnostico que o programa ja tinha.

O contrato de destino
---------------------
Os arquivos vao para **ao lado do executavel**, nunca para dentro do bundle:

    Caissa/
      Caissa.exe
      _internal/           <- o bundle; reinstalar sobrescreve
      models/              <- daqui
      assets/lexico/       <- e daqui

E a mesma regra do tronco (`chess_diagram_ocr.config._project_root`, que resolve para a
pasta do `.exe` quando `sys.frozen` esta posto) e existe pelo mesmo motivo: reinstalar nao
pode apagar o que o usuario baixou ou treinou.

Rede
----
`base_url` do manifesto e `null` hoje: **nao ha servidor de distribuicao publicado**. O
codigo de download existe, e testado, e recusa qualquer coisa que nao seja HTTPS -- mas
enquanto nao houver URL o unico caminho e `instalar_de_pasta`, e o assistente diz isso em
vez de fingir uma tentativa de rede que vai falhar.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DIGITOS_DO_SHA256",
    "MANIFESTO_PADRAO",
    "TAMANHO_DO_BLOCO",
    "Componente",
    "Manifesto",
    "Resultado",
    "baixar",
    "carregar_manifesto",
    "instalar_de_pasta",
    "raiz_de_instalacao",
    "sha256_do_arquivo",
    "verificar",
]

DIGITOS_DO_SHA256 = 64
"""Um SHA-256 em hexadecimal minusculo. Conferido no CARREGAMENTO do manifesto, e nao
depois -- na hora em que o usuario ja baixou o arquivo e a comparacao nunca poderia bater."""

TAMANHO_DO_BLOCO = 1 << 20
"""1 MiB. Ler o arquivo inteiro na memoria para hashear um `.pt` de 8 MB e desnecessario, e
seria um erro assim que alguem puser um peso de 2 GB no manifesto."""

MANIFESTO_PADRAO = Path(__file__).resolve().parent / "manifesto.json"


@dataclass(frozen=True)
class Componente:
    """Uma linha do manifesto: um arquivo que o usuario recebe depois da instalacao."""

    id: str
    titulo: str
    destino: str
    sha256: str
    bytes: int
    obrigatorio: bool
    consentimento: bool
    licenca: str
    procedencia: str
    sem_ele: str
    origem_no_tronco: str | None = None

    @property
    def mb(self) -> float:
        """Tamanho declarado em MB, para o texto que o usuario le."""
        return self.bytes / (1024 * 1024)

    @classmethod
    def de_dict(cls, bruto: dict[str, Any]) -> Componente:
        """Constroi a partir de uma entrada de `manifesto.json`."""
        return cls(
            id=str(bruto["id"]),
            titulo=str(bruto["titulo"]),
            destino=str(bruto["destino"]),
            sha256=str(bruto["sha256"]).lower(),
            bytes=int(bruto["bytes"]),
            obrigatorio=bool(bruto.get("obrigatorio", False)),
            consentimento=bool(bruto.get("consentimento", False)),
            licenca=str(bruto.get("licenca", "?")),
            procedencia=str(bruto.get("procedencia", "")),
            sem_ele=str(bruto.get("sem_ele", "")),
            origem_no_tronco=(
                str(bruto["origem_no_tronco"]) if bruto.get("origem_no_tronco") else None
            ),
        )


@dataclass(frozen=True)
class Manifesto:
    """O arquivo inteiro, ja validado."""

    esquema: int
    gerado_em: str
    base_url: str | None
    componentes: tuple[Componente, ...]

    def por_id(self, ident: str) -> Componente:
        """Busca um componente pelo `id`. Levanta `KeyError` com a lista do que existe."""
        for componente in self.componentes:
            if componente.id == ident:
                return componente
        conhecidos = ", ".join(c.id for c in self.componentes)
        raise KeyError(f"componente desconhecido: {ident!r}. Conhecidos: {conhecidos}")

    @property
    def obrigatorios(self) -> tuple[Componente, ...]:
        """Os que, ausentes, tiram uma funcao inteira do programa."""
        return tuple(c for c in self.componentes if c.obrigatorio)

    @property
    def sob_consentimento(self) -> tuple[Componente, ...]:
        """Os que so entram se o usuario disser que sim. Ver LICENSING.md."""
        return tuple(c for c in self.componentes if c.consentimento)

    @property
    def bytes_totais(self) -> int:
        """Soma de tudo, para o assistente dizer quanto disco vai gastar."""
        return sum(c.bytes for c in self.componentes)


def carregar_manifesto(caminho: Path | None = None) -> Manifesto:
    """Le e valida `manifesto.json`.

    Valida de verdade: um `id` repetido ou um `sha256` que nao e um hexadecimal de 64
    caracteres para o carregamento aqui, e nao depois -- na hora em que o usuario ja baixou
    o arquivo e a comparacao nunca poderia bater.
    """
    caminho = caminho or MANIFESTO_PADRAO
    bruto = json.loads(caminho.read_text(encoding="utf-8"))

    componentes = tuple(Componente.de_dict(item) for item in bruto["componentes"])
    if not componentes:
        raise ValueError(f"{caminho} nao declara nenhum componente.")

    vistos: set[str] = set()
    for componente in componentes:
        if componente.id in vistos:
            raise ValueError(f"{caminho}: id repetido {componente.id!r}.")
        vistos.add(componente.id)
        if len(componente.sha256) != DIGITOS_DO_SHA256 or not all(
            c in "0123456789abcdef" for c in componente.sha256
        ):
            raise ValueError(
                f"{caminho}: {componente.id!r} tem sha256 invalido ({componente.sha256!r}). "
                "Sao 64 digitos hexadecimais minusculos."
            )
        if componente.bytes <= 0:
            raise ValueError(f"{caminho}: {componente.id!r} declara {componente.bytes} bytes.")
        destino = Path(componente.destino)
        if destino.is_absolute() or ".." in destino.parts:
            raise ValueError(
                f"{caminho}: {componente.id!r} tem destino {componente.destino!r}. "
                "O destino e relativo a pasta do executavel e nao pode escapar dela."
            )

    base_url = bruto.get("base_url")
    if base_url is not None and not str(base_url).startswith("https://"):
        raise ValueError(f"{caminho}: base_url precisa ser https, nao {base_url!r}.")

    return Manifesto(
        esquema=int(bruto["esquema"]),
        gerado_em=str(bruto["gerado_em"]),
        base_url=str(base_url) if base_url else None,
        componentes=componentes,
    )


def raiz_de_instalacao() -> Path:
    """Onde os componentes sao gravados: **ao lado do executavel**, nunca dentro dele.

    Congelado, e a pasta do `.exe` -- a mesma que `chess_diagram_ocr.config._project_root`
    devolve, e por isso o programa acha o que este modulo grava sem nenhuma ponte.
    Num checkout e a raiz do repositorio.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def sha256_do_arquivo(caminho: Path) -> str:
    """Hash em blocos de 1 MiB."""
    digest = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(TAMANHO_DO_BLOCO), b""):
            digest.update(bloco)
    return digest.hexdigest()


@dataclass(frozen=True)
class Resultado:
    """O que aconteceu com um componente. Nunca uma excecao para o caminho normal."""

    componente: Componente
    ok: bool
    estado: str
    detalhe: str = ""
    caminho: Path | None = None

    def __bool__(self) -> bool:
        """Permite `if resultado:` na chamada."""
        return self.ok


def verificar(componente: Componente, raiz: Path | None = None) -> Resultado:
    """O arquivo esta la, com o tamanho e o hash que o manifesto declara?

    Confere o **tamanho primeiro**: um arquivo truncado por download interrompido e o caso
    comum, e comparar 4 bytes de metadado e mais barato que hashear 8 MB para chegar a
    mesma conclusao.
    """
    raiz = raiz or raiz_de_instalacao()
    destino = raiz / componente.destino
    if not destino.exists():
        return Resultado(componente, False, "ausente", componente.sem_ele, destino)

    tamanho = destino.stat().st_size
    if tamanho != componente.bytes:
        return Resultado(
            componente,
            False,
            "tamanho-errado",
            f"{tamanho} bytes em disco, {componente.bytes} declarados. "
            "Download interrompido, ou o arquivo nao e o do manifesto.",
            destino,
        )

    obtido = sha256_do_arquivo(destino)
    if obtido != componente.sha256:
        return Resultado(
            componente,
            False,
            "hash-errado",
            f"sha256 {obtido[:16]}... em disco, {componente.sha256[:16]}... declarado.",
            destino,
        )
    return Resultado(componente, True, "ok", "", destino)


def instalar_de_pasta(
    componente: Componente,
    origem: Path,
    raiz: Path | None = None,
    *,
    consentido: bool = False,
) -> Resultado:
    """Instalacao **offline**: copia de uma pasta local (um pendrive, o checkout do tronco).

    E o caminho que a SPEC secao 12 chama de "opcao de instalacao offline por pacote", e
    hoje e o unico caminho que existe, porque nao ha servidor.

    A copia e **atomica por renomeacao**: grava em `<destino>.parcial` e so entao renomeia.
    Sem isso, uma copia interrompida deixa um arquivo com o nome certo e o conteudo pela
    metade -- e o programa seguinte carrega um checkpoint truncado em vez de dizer que
    faltou. E a mesma disciplina da gravacao de PDF do tronco (ASSETS secao 2.9).

    `consentido` nao tem valor padrao verdadeiro de proposito: os componentes de licenca
    nao apurada so entram se quem chamou disse que sim, e a recusa e um `Resultado`, nao uma
    excecao, porque nao e um erro -- e o comportamento correto.
    """
    if componente.consentimento and not consentido:
        return Resultado(
            componente,
            False,
            "sem-consentimento",
            f"{componente.titulo}: licenca {componente.licenca}. "
            "Nao entra sem o usuario aceitar explicitamente (ver LICENSING.md).",
        )

    raiz = raiz or raiz_de_instalacao()
    candidatos = [origem / componente.destino, origem / Path(componente.destino).name]
    if componente.origem_no_tronco:
        candidatos.insert(0, origem / componente.origem_no_tronco)

    fonte = next((c for c in candidatos if c.is_file()), None)
    if fonte is None:
        tentados = "\n  ".join(str(c) for c in candidatos)
        return Resultado(
            componente,
            False,
            "nao-encontrado",
            f"nao achei {componente.titulo} em {origem}. Procurei em:\n  {tentados}",
        )

    obtido = sha256_do_arquivo(fonte)
    if obtido != componente.sha256:
        return Resultado(
            componente,
            False,
            "hash-errado",
            f"{fonte} tem sha256 {obtido[:16]}..., o manifesto declara "
            f"{componente.sha256[:16]}.... Nao copiei.",
            fonte,
        )

    destino = raiz / componente.destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    try:
        shutil.copyfile(fonte, parcial)
        parcial.replace(destino)
    except OSError as exc:
        parcial.unlink(missing_ok=True)
        return Resultado(componente, False, "erro-de-escrita", str(exc), destino)
    return Resultado(componente, True, "instalado", f"de {fonte}", destino)


def baixar(
    componente: Componente,
    base_url: str,
    raiz: Path | None = None,
    *,
    consentido: bool = False,
    tempo_limite: float = 60.0,
) -> Resultado:
    """Baixa um componente e **so grava depois de conferir o hash**.

    A ordem importa e e o ponto do metodo: baixa para `.parcial`, hasheia o `.parcial`, e
    so entao renomeia. Um arquivo com o nome final nunca existiu com conteudo nao
    verificado, nem por um instante -- o que fecha a janela em que um download interrompido
    e um download adulterado sao indistinguiveis de um arquivo bom.

    Recusa qualquer esquema que nao seja `https`. Sem isso, uma `base_url` trocada no
    manifesto viraria execucao de codigo remoto na primeira execucao: os `.pt` sao pickles
    do torch.
    """
    if componente.consentimento and not consentido:
        return Resultado(
            componente,
            False,
            "sem-consentimento",
            f"{componente.titulo}: licenca {componente.licenca}. Ver LICENSING.md.",
        )
    if not base_url.startswith("https://"):
        return Resultado(
            componente,
            False,
            "url-recusada",
            f"base_url {base_url!r} nao e https. Os pesos sao pickles do torch; "
            "baixa-los por canal nao autenticado seria execucao de codigo remoto.",
        )

    import urllib.request

    url = f"{base_url.rstrip('/')}/{componente.destino}"
    raiz = raiz or raiz_de_instalacao()
    destino = raiz / componente.destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")

    try:
        with (
            urllib.request.urlopen(url, timeout=tempo_limite) as resposta,  # noqa: S310
            parcial.open("wb") as fh,
        ):
            shutil.copyfileobj(resposta, fh, TAMANHO_DO_BLOCO)
    except Exception as exc:  # noqa: BLE001 - urllib levanta de tudo, e nada disso e fatal
        parcial.unlink(missing_ok=True)
        return Resultado(componente, False, "erro-de-rede", f"{type(exc).__name__}: {exc}", destino)

    obtido = sha256_do_arquivo(parcial)
    if obtido != componente.sha256:
        parcial.unlink(missing_ok=True)
        return Resultado(
            componente,
            False,
            "hash-errado",
            f"o que veio de {url} tem sha256 {obtido[:16]}..., o manifesto declara "
            f"{componente.sha256[:16]}.... Apaguei.",
            destino,
        )

    parcial.replace(destino)
    return Resultado(componente, True, "baixado", f"de {url}", destino)
