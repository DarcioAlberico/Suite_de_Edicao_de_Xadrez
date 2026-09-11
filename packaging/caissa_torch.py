r"""O torch como componente de primeira execucao, e nao como carga do instalador (F12, ciclo 2).

A decisao que este arquivo executa
----------------------------------
O ciclo 1 desta frente mediu o custo do torch dentro do pacote: **436,7 MB de bundle e
90,2 MB de instalador**. Para caber nos 150 MB da SPEC secao 12, o ciclo 1 empacotou o
torch de **CPU** (506 MB instalados) em vez do **cu128** (4.214 MB) -- e mesmo assim o
instalador saiu em 169,3 MB, 19,3 acima do teto.

O preco dessa escolha nao e cosmetico. `docs/quality/F4GPU_REPORT.md` secao 7 mediu, nesta
maquina:

    vazao em GPU (6 trabalhadores) : 0,0903 s/diagrama
    linha de base em CPU           : 0,5234 s/diagrama

Ou seja: **quem instala pelo instalador recebia 5,8x menos velocidade do que quem roda do
checkout**, sem nunca ser avisado. Trocar 19,3 MB de teto por 5,8x de velocidade, em
silencio, e a troca errada.

A saida ja estava na arquitetura. Os **pesos** ja saem do instalador e chegam na primeira
execucao, com SHA-256 e caminho offline (`caissa_modelos.py`, `manifesto.json`). O torch e
o mesmo tipo de artefato: **grande, especifico da maquina, e errado de congelar dentro de
um instalador** -- porque a roda certa depende de uma GPU que so existe do outro lado.
Entao ele vai para o mesmo lugar.

Como funciona, em tres passos
-----------------------------
1. **Detectar a GPU sem torch.** Ovo e galinha: a sonda real do `scripts/doctor.py` roda
   uma multiplicacao 4096x4096 *em torch*, e aqui ainda nao ha torch. Antes da instalacao
   quem responde e o `nvidia-smi`, que declara `compute_cap` (esta maquina: `12.0`, isto e
   `sm_120`, Blackwell). E uma pergunta de hardware, e o `nvidia-smi` e quem a responde sem
   dependencia nenhuma.
2. **Instalar a roda certa.** `compute_cap >= 7.0` -> **cu128** (SPEC R1: Blackwell so tem
   kernel nas rodas cu128 ou posteriores); sem GPU CUDA -> **cpu**. Cada roda e obtida por
   HTTPS a partir do indice oficial do PyTorch **ou** de uma pasta local, e so e desempacotada
   **depois** de o SHA-256 bater -- a mesma maquina de `caissa_modelos.py`, pelo mesmo motivo:
   um `.whl` e um zip de codigo executavel.
3. **Conferir com a sonda real.** Instalado o torch, o `doctor.py` volta a ser utilizavel e
   e ele quem diz se a roda tem kernel para esta GPU. `is_available()` devolve `True` mesmo
   quando nao ha kernel (ADR-0003); so a multiplicacao de verdade fecha a questao.

Onde o torch e instalado, e por que ali
---------------------------------------
Em `<pasta do executavel>/runtime/`, ao lado de `models/` e pelo mesmo contrato: reinstalar
o programa apaga `_internal/` (ver `[InstallDelete]` do `installer.iss`) e **nao** apaga o
que o usuario baixou. Um torch cu128 de 4,2 GB rebaixado a cada atualizacao seria um jeito
caro de perder a confianca de quem instalou.

`runtime_hook_torch.py` poe essa pasta em `sys.path` **na inicializacao do `.exe`**, antes
de qualquer `import torch`. Ele entra em `runtime_hooks` da `caissa.spec`.

Offline e obrigatorio
---------------------
A SPEC secao 12 exige "opcao de instalacao offline por pacote" e a secao 0 exige
"totalmente funcional sem internet". `--rodas-de <pasta>` instala a partir de um pendrive ou
de um espelho local, com a mesma verificacao de hash. Diferente dos pesos -- cujo
`manifesto.json` tem `base_url: null` porque **nao ha servidor publicado** --, aqui a rede
tem um servidor de verdade e publicado (`download.pytorch.org`), e por isso os dois caminhos
sao reais e os dois foram exercitados. Ver `docs/quality/F12_REPORT_C2.md`.

    CaissaPrimeiraExecucao.exe                       # detecta e instala pela rede
    CaissaPrimeiraExecucao.exe --rodas-de D:\rodas   # instala offline
    python packaging/caissa_torch.py --detectar      # so o diagnostico
    python packaging/caissa_torch.py --gerar-manifesto  # regrava torch_manifesto.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import caissa_modelos as mod

__all__ = [
    "MANIFESTO_DE_TORCH",
    "NOME_DA_PASTA_DE_RUNTIME",
    "SEGUNDOS_POR_DIAGRAMA",
    "Gpu",
    "ManifestoDeTorch",
    "Roda",
    "Variante",
    "carregar_manifesto_de_torch",
    "detectar_gpu",
    "escolher_variante",
    "estado_instalado",
    "instalar_variante",
    "main",
    "obter_roda",
    "raiz_do_runtime",
    "remover_runtime",
]

MANIFESTO_DE_TORCH = Path(__file__).resolve().parent / "torch_manifesto.json"

NOME_DA_PASTA_DE_RUNTIME = "runtime"
"""Irma de `models/`: fica ao lado do `.exe`, sobrevive a reinstalacao, e o
`runtime_hook_torch.py` a poe em `sys.path` antes de qualquer import."""

MARCA = "caissa_torch.json"
"""O que foi instalado, quando, de onde e com que hash. Um diretorio com um `torch/` dentro
nao diz qual roda e; esta marca diz, e e ela que o assistente le para nao rebaixar um cu128
para cpu sem perceber."""

SEGUNDOS_POR_DIAGRAMA = {
    "cu128": 0.0903,
    "cpu": 0.5234,
}
"""Medidos nesta maquina e publicados em `docs/quality/F4GPU_REPORT.md`: 0,0903 s/diagrama
com 6 trabalhadores em GPU (secao 7.1) contra 0,5234 s/diagrama de linha de base em CPU
(secao 3). **Nao sao numeros de folheto** -- e por isso que o assistente pode dizer ao
usuario o que ele esta recebendo, em segundos, e nao em adjetivos."""

CAPACIDADE_MINIMA_PARA_CUDA = (7, 0)
"""Abaixo de sm_70 a roda cu128 nao traz kernel, e instalar 2,6 GB para cair em CPU no
primeiro uso seria pior do que instalar a roda de CPU e dizer isso. A SPEC R1 trata do outro
extremo (Blackwell exige cu128); este limite trata do de baixo."""

CAMPOS_DO_NVIDIA_SMI = 4
"""`nome, compute_cap, driver_version, memory.total` -- a consulta feita em `detectar_gpu`.
Menos campos que isso quer dizer que o `nvidia-smi` respondeu outra coisa, e adivinhar qual
e pior do que desistir da GPU."""

TAMANHO_DO_BLOCO = 1 << 20


# --------------------------------------------------------------------------- #
# 1. a maquina, ANTES de existir torch
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Gpu:
    """O que o `nvidia-smi` diz. Nenhum campo depende de torch."""

    nome: str
    capacidade: tuple[int, int] | None
    driver: str
    memoria_mib: int | None

    @property
    def sm(self) -> str:
        """`sm_120` a partir de `(12, 0)`, que e como a ADR-0003 e a SPEC R1 falam."""
        if self.capacidade is None:
            return "desconhecida"
        return f"sm_{self.capacidade[0]}{self.capacidade[1]}"

    def como_dict(self) -> dict[str, Any]:
        """Forma serializavel, para `--json` e para o relatorio do assistente."""
        return {
            "nome": self.nome,
            "capacidade": list(self.capacidade) if self.capacidade else None,
            "sm": self.sm,
            "driver": self.driver,
            "memoria_mib": self.memoria_mib,
        }


def detectar_gpu(tempo_limite: float = 20.0) -> Gpu | None:
    """Pergunta ao `nvidia-smi`. Devolve `None` quando nao ha GPU NVIDIA utilizavel.

    **Por que nao `torch.cuda`:** porque este codigo roda antes de o torch existir. E por que
    nao adivinhar pelo nome da placa: porque `compute_cap` e um campo declarado pelo driver, e
    o nome comercial nao determina a arquitetura de forma confiavel.

    Nao levanta. Uma maquina sem driver NVIDIA e o caso comum, nao um erro -- ela recebe a
    roda de CPU e uma frase dizendo o que isso custa.
    """
    executavel = shutil.which("nvidia-smi")
    if executavel is None:
        return None
    try:
        processo = subprocess.run(  # noqa: S603 - argv fixo, montado aqui
            [
                executavel,
                "--query-gpu=name,compute_cap,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=tempo_limite,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if processo.returncode != 0:
        return None

    primeira = next((linha for linha in processo.stdout.splitlines() if linha.strip()), "")
    campos = [c.strip() for c in primeira.split(",")]
    if len(campos) < CAMPOS_DO_NVIDIA_SMI:
        return None

    capacidade: tuple[int, int] | None = None
    try:
        maior, menor = campos[1].split(".")
        capacidade = (int(maior), int(menor))
    except (ValueError, IndexError):
        capacidade = None
    try:
        memoria = int(float(campos[3]))
    except ValueError:
        memoria = None
    return Gpu(nome=campos[0], capacidade=capacidade, driver=campos[2], memoria_mib=memoria)


# --------------------------------------------------------------------------- #
# 2. o manifesto das rodas
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Roda:
    """Uma roda (`.whl`): nome de arquivo, URL https, hash e tamanho medidos."""

    nome: str
    url: str
    sha256: str
    bytes: int
    distribuicao: str
    versao: str

    @property
    def mb(self) -> float:
        """Tamanho declarado em MB."""
        return self.bytes / (1024 * 1024)


@dataclass(frozen=True)
class Variante:
    """Um conjunto coerente de rodas: `cu128` ou `cpu`."""

    id: str
    titulo: str
    rodas: tuple[Roda, ...]
    segundos_por_diagrama: float
    explicacao: str

    @property
    def bytes_totais(self) -> int:
        """Quanto o usuario baixa (ou copia do pendrive)."""
        return sum(r.bytes for r in self.rodas)

    @property
    def mb(self) -> float:
        """O mesmo, em MB."""
        return self.bytes_totais / (1024 * 1024)


@dataclass(frozen=True)
class ManifestoDeTorch:
    """`torch_manifesto.json` ja validado."""

    esquema: int
    gerado_em: str
    variantes: tuple[Variante, ...]

    def por_id(self, ident: str) -> Variante:
        """Busca uma variante. `KeyError` com a lista do que existe."""
        for variante in self.variantes:
            if variante.id == ident:
                return variante
        conhecidas = ", ".join(v.id for v in self.variantes)
        raise KeyError(f"variante de torch desconhecida: {ident!r}. Conhecidas: {conhecidas}")


def carregar_manifesto_de_torch(caminho: Path | None = None) -> ManifestoDeTorch:
    """Le e valida. Um hash malformado para aqui, e nao depois de 2,6 GB baixados."""
    caminho = caminho or MANIFESTO_DE_TORCH
    bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))

    variantes: list[Variante] = []
    for item in bruto["variantes"]:
        rodas: list[Roda] = []
        for r in item["rodas"]:
            sha = str(r["sha256"]).lower()
            if len(sha) != mod.DIGITOS_DO_SHA256 or not all(c in "0123456789abcdef" for c in sha):
                raise ValueError(f"{caminho}: {r['nome']!r} tem sha256 invalido ({sha!r}).")
            url = str(r["url"])
            if not url.startswith("https://"):
                raise ValueError(
                    f"{caminho}: {r['nome']!r} tem url {url!r}. Uma roda e um zip de codigo "
                    "executavel; baixa-la por canal nao autenticado seria execucao remota."
                )
            if int(r["bytes"]) <= 0:
                raise ValueError(f"{caminho}: {r['nome']!r} declara {r['bytes']} bytes.")
            nome = str(r["nome"])
            if "/" in nome or "\\" in nome or nome.startswith("."):
                raise ValueError(f"{caminho}: nome de roda invalido ({nome!r}).")
            rodas.append(
                Roda(
                    nome=nome,
                    url=url,
                    sha256=sha,
                    bytes=int(r["bytes"]),
                    distribuicao=str(r["distribuicao"]),
                    versao=str(r["versao"]),
                )
            )
        if not rodas:
            raise ValueError(f"{caminho}: variante {item['id']!r} sem nenhuma roda.")
        variantes.append(
            Variante(
                id=str(item["id"]),
                titulo=str(item["titulo"]),
                rodas=tuple(rodas),
                segundos_por_diagrama=float(item["segundos_por_diagrama"]),
                explicacao=str(item["explicacao"]),
            )
        )
    if not variantes:
        raise ValueError(f"{caminho} nao declara nenhuma variante.")
    return ManifestoDeTorch(
        esquema=int(bruto["esquema"]),
        gerado_em=str(bruto["gerado_em"]),
        variantes=tuple(variantes),
    )


def escolher_variante(gpu: Gpu | None, manifesto: ManifestoDeTorch) -> tuple[Variante, str]:
    """Qual roda esta maquina merece, e a frase que explica por que.

    A frase importa tanto quanto a escolha: o usuario que recebe CPU precisa saber que
    recebeu CPU, e o que isso custa em segundos, **antes** de concluir que o programa e
    lento.
    """
    if gpu is None:
        return (
            manifesto.por_id("cpu"),
            "Nenhuma GPU NVIDIA encontrada (o `nvidia-smi` nao respondeu ou nao esta "
            "instalado). A roda de CPU e a certa para esta maquina.",
        )
    if gpu.capacidade is None:
        return (
            manifesto.por_id("cpu"),
            f"{gpu.nome} encontrada, mas o driver nao declarou `compute_cap`. Sem saber a "
            "arquitetura, instalar 2,6 GB de kernels CUDA seria apostar; a roda de CPU "
            "funciona em qualquer caso.",
        )
    if gpu.capacidade < CAPACIDADE_MINIMA_PARA_CUDA:
        return (
            manifesto.por_id("cpu"),
            f"{gpu.nome} e {gpu.sm}, abaixo de sm_70. As rodas cu128 nao trazem kernel para "
            "essa arquitetura: baixa-las daria 2,6 GB e uma queda silenciosa para CPU.",
        )
    return (
        manifesto.por_id("cu128"),
        f"{gpu.nome} ({gpu.sm}, driver {gpu.driver}). A SPEC R1 e a ADR-0003 dizem que "
        f"{gpu.sm} so tem kernels nas rodas cu128 ou posteriores -- e por isso e a cu128 "
        "que vai ser instalada, e nao a de CPU.",
    )


# --------------------------------------------------------------------------- #
# 3. instalar
# --------------------------------------------------------------------------- #
def raiz_do_runtime(raiz: Path | None = None) -> Path:
    """`<pasta do executavel>/runtime`. Fora de `_internal/`, de proposito."""
    return (raiz or mod.raiz_de_instalacao()) / NOME_DA_PASTA_DE_RUNTIME


def estado_instalado(raiz: Path | None = None) -> dict[str, Any] | None:
    """Le a marca. `None` quando nao ha torch instalado ao lado do executavel.

    Confere tambem que o `torch/` **existe** de fato: uma marca sem pacote e o estado que
    sobra de uma instalacao interrompida, e ela nao pode passar por instalacao boa.
    """
    pasta = raiz_do_runtime(raiz)
    marca = pasta / MARCA
    if not marca.is_file() or not (pasta / "torch" / "__init__.py").is_file():
        return None
    try:
        return dict(json.loads(marca.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def obter_roda(
    roda: Roda,
    destino: Path,
    *,
    origem: Path | None = None,
    tempo_limite: float = 600.0,
    progresso: Any = None,
) -> mod.Resultado:
    """Poe a roda em `destino`, verificada. Rede **ou** pasta local -- nunca sem hash.

    A ordem e a mesma de `caissa_modelos.baixar()` e existe pelo mesmo motivo: grava em
    `.parcial`, hasheia o `.parcial`, e so entao renomeia. Um arquivo com o nome final nunca
    existe com conteudo nao verificado, nem por um instante. Aqui a regra pesa mais do que
    nos pesos: uma roda e um **zip de codigo** que vai ser desempacotado e importado.
    """
    componente = _componente_da_roda(roda)
    # `destino` e a PASTA de cache, e nao um arquivo: quem cria e ela, nao o pai dela. O
    # primeiro rascunho escrevia `destino.parent.mkdir(...)`, e o resultado foi um
    # `FileNotFoundError` na abertura do `.parcial` -- reportado como "erro de rede" numa
    # maquina cuja rede estava perfeita.
    destino.mkdir(parents=True, exist_ok=True)
    final = destino / roda.nome

    if final.is_file() and final.stat().st_size == roda.bytes:
        obtido = mod.sha256_do_arquivo(final)
        if obtido == roda.sha256:
            return mod.Resultado(componente, True, "ja-no-cache", f"{final}", final)
        final.unlink()

    parcial = final.with_suffix(final.suffix + ".parcial")

    if origem is not None:
        candidatos = [origem / roda.nome, *sorted(origem.glob(f"{roda.distribuicao}-*.whl"))]
        fonte = next((c for c in candidatos if c.is_file()), None)
        if fonte is None:
            return mod.Resultado(
                componente,
                False,
                "nao-encontrado",
                f"nao achei {roda.nome} em {origem}.",
            )
        try:
            shutil.copyfile(fonte, parcial)
        except OSError as exc:
            parcial.unlink(missing_ok=True)
            return mod.Resultado(componente, False, "erro-de-escrita", str(exc), final)
        estado = "copiado"
        de_onde = str(fonte)
    else:
        import urllib.request

        pedido = urllib.request.Request(  # noqa: S310 - o esquema foi validado no manifesto
            roda.url, headers={"User-Agent": "caissa-primeira-execucao"}
        )
        try:
            with (
                urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta,  # noqa: S310
                parcial.open("wb") as fh,
            ):
                lidos = 0
                while True:
                    bloco = resposta.read(TAMANHO_DO_BLOCO)
                    if not bloco:
                        break
                    fh.write(bloco)
                    lidos += len(bloco)
                    if progresso is not None:
                        progresso(roda, lidos)
        except Exception as exc:  # noqa: BLE001 - urllib levanta de tudo; nada disso e fatal
            parcial.unlink(missing_ok=True)
            return mod.Resultado(
                componente, False, "erro-de-rede", f"{type(exc).__name__}: {exc}", final
            )
        estado = "baixado"
        de_onde = roda.url

    obtido = mod.sha256_do_arquivo(parcial)
    if obtido != roda.sha256:
        parcial.unlink(missing_ok=True)
        return mod.Resultado(
            componente,
            False,
            "hash-errado",
            f"o que veio de {de_onde} tem sha256 {obtido[:16]}..., o manifesto declara "
            f"{roda.sha256[:16]}.... Apaguei em vez de desempacotar.",
            final,
        )
    parcial.replace(final)
    return mod.Resultado(componente, True, estado, de_onde, final)


def _componente_da_roda(roda: Roda) -> mod.Componente:
    """Adapta uma `Roda` a `Componente`, para reusar `Resultado` sem duplicar a estrutura."""
    return mod.Componente(
        id=f"roda:{roda.distribuicao}",
        titulo=f"{roda.distribuicao} {roda.versao}",
        destino=f"{NOME_DA_PASTA_DE_RUNTIME}/{roda.nome}",
        sha256=roda.sha256,
        bytes=roda.bytes,
        obrigatorio=False,
        consentimento=False,
        licenca="ver licenses/",
        procedencia=roda.url,
        sem_ele="",
    )


def _desempacotar(roda_no_disco: Path, alvo: Path) -> int:
    r"""Desempacota uma roda em `alvo`. Recusa qualquer entrada que escape da pasta.

    Uma roda e um zip, e um zip pode conter `..\\..\\system32\\algo.dll`. O hash ja garante
    que o arquivo e o do manifesto; esta funcao garante que **mesmo o arquivo certo** nao
    escreve fora do lugar -- as duas guardas custam quase nada e cobrem coisas diferentes.
    """
    alvo.mkdir(parents=True, exist_ok=True)
    quantos = 0
    with zipfile.ZipFile(roda_no_disco) as zf:
        for info in zf.infolist():
            nome = info.filename
            if nome.endswith("/"):
                continue
            destino = (alvo / nome).resolve()
            if not str(destino).startswith(str(alvo.resolve())):
                raise ValueError(f"{roda_no_disco.name}: entrada {nome!r} escapa de {alvo}.")
            destino.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as origem, destino.open("wb") as fh:
                shutil.copyfileobj(origem, fh, TAMANHO_DO_BLOCO)
            quantos += 1
    return quantos


def instalar_variante(
    variante: Variante,
    *,
    raiz: Path | None = None,
    origem: Path | None = None,
    cache: Path | None = None,
    manter_rodas: bool = False,
    progresso: Any = None,
) -> tuple[bool, list[mod.Resultado], dict[str, Any]]:
    """Obtem, verifica e desempacota todas as rodas da variante em `runtime/`.

    Devolve `(ok, resultados, marca)`. Nao levanta para o caminho normal: uma rede que caiu
    no meio e um `Resultado` com estado `erro-de-rede`, e o assistente sabe imprimir isso.

    As rodas ficam num cache separado (`runtime/.rodas/`) e sao **apagadas no fim** por
    padrao. Guardar 2,6 GB de `.whl` ao lado de 4,2 GB desempacotados dobraria o custo em
    disco -- e a SPEC R4 chama disco de restricao critica. `--manter-rodas` inverte isso, que
    e o que se quer quando a pasta vai virar o espelho offline de outra maquina.
    """
    pasta = raiz_do_runtime(raiz)
    cache = cache or (pasta / ".rodas")
    resultados: list[mod.Resultado] = []
    arquivos: list[tuple[Roda, Path]] = []

    for roda in variante.rodas:
        resultado = obter_roda(roda, cache, origem=origem, progresso=progresso)
        resultados.append(resultado)
        if not resultado.ok or resultado.caminho is None:
            return False, resultados, {}
        arquivos.append((roda, resultado.caminho))

    # So agora se toca em `runtime/`: se uma das rodas falhar, a instalacao anterior fica
    # intacta em vez de virar meia instalacao nova.
    temporaria = pasta.with_name(pasta.name + ".novo")
    if temporaria.exists():
        shutil.rmtree(temporaria, ignore_errors=True)
    entradas = 0
    try:
        for _roda, arquivo in arquivos:
            entradas += _desempacotar(arquivo, temporaria)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        shutil.rmtree(temporaria, ignore_errors=True)
        resultados.append(
            mod.Resultado(
                _componente_da_roda(arquivos[-1][0] if arquivos else variante.rodas[0]),
                False,
                "erro-ao-desempacotar",
                f"{type(exc).__name__}: {exc}",
            )
        )
        return False, resultados, {}

    marca = {
        "variante": variante.id,
        "titulo": variante.titulo,
        "segundos_por_diagrama": variante.segundos_por_diagrama,
        "instalado_em": _hoje(),
        "rodas": [
            {"nome": r.nome, "versao": r.versao, "sha256": r.sha256, "bytes": r.bytes}
            for r in variante.rodas
        ],
        "arquivos_desempacotados": entradas,
        "manifesto_gerado_em": _hoje(),
    }
    (temporaria / MARCA).write_text(
        json.dumps(marca, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    antiga = pasta.with_name(pasta.name + ".antigo")
    shutil.rmtree(antiga, ignore_errors=True)
    if pasta.exists():
        # O cache de rodas mora dentro de `runtime/`; preserva-lo aqui evita rebaixar um
        # espelho offline montado com `--manter-rodas` a cada reinstalacao.
        if cache.exists() and cache.is_relative_to(pasta):
            destino_do_cache = temporaria / cache.name
            if not destino_do_cache.exists():
                shutil.move(str(cache), str(destino_do_cache))
                cache = destino_do_cache
        pasta.rename(antiga)
    temporaria.rename(pasta)
    shutil.rmtree(antiga, ignore_errors=True)

    if not manter_rodas:
        shutil.rmtree(pasta / ".rodas", ignore_errors=True)
    return True, resultados, marca


def remover_runtime(raiz: Path | None = None) -> bool:
    """Apaga `runtime/`. Existe para o teste e para quem quiser trocar de variante."""
    pasta = raiz_do_runtime(raiz)
    if not pasta.exists():
        return False
    shutil.rmtree(pasta, ignore_errors=True)
    return not pasta.exists()


def _hoje() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).date().isoformat()


# --------------------------------------------------------------------------- #
# gerador do manifesto (nao roda na maquina do usuario)
# --------------------------------------------------------------------------- #
_INDICES = {
    "cu128": "https://download.pytorch.org/whl/cu128/",
    "cpu": "https://download.pytorch.org/whl/cpu/",
}
_PYPI = "https://pypi.org/pypi/{nome}/{versao}/json"


def gerar_manifesto(
    destino: Path, *, marca_python: str = "cp311", plataforma: str = "win_amd64"
) -> int:
    """Regrava `torch_manifesto.json` a partir dos indices oficiais. Ferramenta de build.

    O indice do PyTorch publica o `sha256` no proprio `href` (`...whl#sha256=...`) e o PyPI
    publica em `digests.sha256`. **Nenhum hash aqui foi digitado a mao**; cada um veio do
    publicador, e o tamanho veio de um `Range: bytes=0-0` no proprio arquivo. E por isso que
    a verificacao vale alguma coisa.
    """
    import re
    import urllib.request

    cabecalhos = {"User-Agent": "caissa-packaging"}

    def _abrir(url: str, extra: dict[str, str] | None = None) -> Any:
        h = dict(cabecalhos)
        h.update(extra or {})
        pedido = urllib.request.Request(url, headers=h)  # noqa: S310 - https fixo, acima
        return urllib.request.urlopen(pedido, timeout=120)  # noqa: S310 - idem

    def _entradas(indice: str, distribuicao: str) -> dict[str, tuple[str, str]]:
        html = _abrir(f"{indice}{distribuicao}/").read().decode("utf-8", "replace")
        saida: dict[str, tuple[str, str]] = {}
        for href in re.findall(r'href="([^"]+)"', html):
            nome = href.split("/")[-1].split("#")[0].replace("%2B", "+")
            sha = href.split("sha256=")[-1] if "sha256=" in href else ""
            saida[nome] = (href.split("#")[0], sha)
        return saida

    def _tamanho(url: str) -> int:
        with _abrir(url, {"Range": "bytes=0-0"}) as r:
            faixa = r.headers.get("Content-Range", "")
            return int(faixa.split("/")[-1]) if faixa else -1

    def _do_pytorch(canal: str, distribuicao: str, versao: str) -> dict[str, Any]:
        nome = f"{distribuicao}-{versao}-{marca_python}-{marca_python}-{plataforma}.whl"
        entradas = _entradas(_INDICES[canal], distribuicao)
        if nome not in entradas:
            disponiveis = sorted(n for n in entradas if plataforma in n)[-5:]
            raise SystemExit(
                f"{nome} nao esta em {_INDICES[canal]}{distribuicao}/. Ha: {disponiveis}"
            )
        url, sha = entradas[nome]
        return {
            "nome": nome,
            "url": url,
            "sha256": sha,
            "bytes": _tamanho(url),
            "distribuicao": distribuicao,
            "versao": versao,
        }

    def _do_pypi(distribuicao: str, versao: str) -> dict[str, Any]:
        dados = json.loads(_abrir(_PYPI.format(nome=distribuicao, versao=versao)).read())
        candidatos = [
            u
            for u in dados["urls"]
            if u["packagetype"] == "bdist_wheel"
            and (
                u["filename"].endswith(f"{marca_python}-{plataforma}.whl")
                or u["filename"].endswith("py3-none-any.whl")
                or u["filename"].endswith("py2.py3-none-any.whl")
            )
        ]
        if not candidatos:
            raise SystemExit(f"nenhuma roda utilizavel para {distribuicao} {versao} no PyPI.")
        # Roda especifica da plataforma vence a universal: `markupsafe` tem `_speedups.pyd`.
        escolhida = sorted(candidatos, key=lambda u: "none-any" in u["filename"])[0]
        return {
            "nome": escolhida["filename"],
            "url": escolhida["url"],
            "sha256": escolhida["digests"]["sha256"],
            "bytes": int(escolhida["size"]),
            "distribuicao": distribuicao,
            "versao": versao,
        }

    comuns = [
        _do_pypi(nome, versao)
        for nome, versao in (
            ("filelock", "3.32.3"),
            ("typing_extensions", "4.16.0"),
            ("sympy", "1.14.0"),
            ("mpmath", "1.3.0"),
            ("networkx", "3.6.1"),
            ("jinja2", "3.1.6"),
            ("MarkupSafe", "3.0.3"),
            ("fsspec", "2026.7.0"),
        )
    ]

    variantes = [
        {
            "id": "cu128",
            "titulo": "PyTorch cu128 (GPU NVIDIA Blackwell e posteriores)",
            "segundos_por_diagrama": SEGUNDOS_POR_DIAGRAMA["cu128"],
            "explicacao": (
                "Roda com kernels CUDA 12.8. E a unica que tem kernel para sm_120 (SPEC R1, "
                "ADR-0003). Medido em docs/quality/F4GPU_REPORT.md secao 7.1: 0,0903 "
                "s/diagrama com 6 trabalhadores."
            ),
            "rodas": [
                _do_pytorch("cu128", "torch", "2.11.0+cu128"),
                _do_pytorch("cu128", "torchvision", "0.26.0+cu128"),
                *comuns,
            ],
        },
        {
            "id": "cpu",
            "titulo": "PyTorch CPU (sem GPU NVIDIA utilizavel)",
            "segundos_por_diagrama": SEGUNDOS_POR_DIAGRAMA["cpu"],
            "explicacao": (
                "Roda sem CUDA. Tudo funciona; o caminho neural fica mais lento. Medido em "
                "docs/quality/F4GPU_REPORT.md secao 3: 0,5234 s/diagrama."
            ),
            "rodas": [
                _do_pytorch("cpu", "torch", "2.14.0+cpu"),
                _do_pytorch("cpu", "torchvision", "0.29.0+cpu"),
                *comuns,
            ],
        },
    ]

    documento = {
        "esquema": 1,
        "gerado_em": _hoje(),
        "comentario": [
            "As rodas do PyTorch que NAO viajam dentro do instalador (F12 ciclo 2).",
            "Gerado por `python packaging/caissa_torch.py --gerar-manifesto`: cada sha256 saiu",
            "do proprio indice do publicador (o do PyTorch traz `#sha256=` no href; o PyPI traz",
            "`digests.sha256`) e cada tamanho saiu de um `Range: bytes=0-0` no arquivo real.",
            "Nenhum numero aqui foi digitado a mao.",
        ],
        "marca_python": marca_python,
        "plataforma": plataforma,
        "variantes": variantes,
    }
    destino.write_text(json.dumps(documento, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for v in variantes:
        total = sum(r["bytes"] for r in v["rodas"])
        print(f"{v['id']:6s} {len(v['rodas'])} rodas, {total / 1024 / 1024:9.1f} MB")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def construir_analisador() -> argparse.ArgumentParser:
    """Argumentos da ferramenta autonoma (o assistente chama as funcoes direto)."""
    analisador = argparse.ArgumentParser(
        prog="caissa_torch",
        description="Instala o PyTorch ao lado do executavel, com a roda certa para esta GPU.",
    )
    analisador.add_argument("--detectar", action="store_true", help="so diz o que achou e sai")
    analisador.add_argument("--instalar", action="store_true", help="instala a variante escolhida")
    analisador.add_argument("--variante", default=None, help="forca 'cu128' ou 'cpu'")
    analisador.add_argument("--rodas-de", default=None, help="pasta local com os .whl (offline)")
    analisador.add_argument("--raiz", default=None, help="onde instalar (padrao: pasta do exe)")
    analisador.add_argument("--manter-rodas", action="store_true", help="nao apaga os .whl")
    analisador.add_argument("--remover", action="store_true", help="apaga runtime/ e sai")
    analisador.add_argument("--json", action="store_true", help="emite JSON")
    analisador.add_argument(
        "--gerar-manifesto", action="store_true", help="regrava torch_manifesto.json (build)"
    )
    return analisador


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da ferramenta autonoma."""
    args = construir_analisador().parse_args(argv)
    if args.gerar_manifesto:
        return gerar_manifesto(MANIFESTO_DE_TORCH)

    raiz = Path(args.raiz).resolve() if args.raiz else None
    if args.remover:
        print("removido" if remover_runtime(raiz) else "nao havia nada em runtime/")
        return 0

    gpu = detectar_gpu()
    manifesto = carregar_manifesto_de_torch()
    variante, motivo = escolher_variante(gpu, manifesto)
    if args.variante:
        variante = manifesto.por_id(args.variante)
        motivo = f"forcada por --variante {args.variante}"

    if args.json:
        print(
            json.dumps(
                {
                    "gpu": gpu.como_dict() if gpu else None,
                    "variante": variante.id,
                    "motivo": motivo,
                    "mb": round(variante.mb, 1),
                    "instalado": estado_instalado(raiz),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"GPU     : {gpu.nome + ' ' + gpu.sm if gpu else 'nenhuma NVIDIA'}")
        print(f"Variante: {variante.id} ({variante.mb:.1f} MB em {len(variante.rodas)} rodas)")
        print(f"Motivo  : {motivo}")
        ja = estado_instalado(raiz)
        print(f"Estado  : {ja['variante'] + ' ja instalado' if ja else 'runtime/ vazio'}")

    if not args.instalar:
        return 0

    origem = Path(args.rodas_de).resolve() if args.rodas_de else None

    def progresso(roda: Roda, lidos: int) -> None:
        if roda.bytes > 50 * 1024 * 1024 and lidos % (64 * 1024 * 1024) < TAMANHO_DO_BLOCO:
            pct = 100.0 * lidos / roda.bytes
            print(f"  {roda.nome}: {lidos / 1024 / 1024:.0f} MB ({pct:.0f}%)", flush=True)

    ok, resultados, marca = instalar_variante(
        variante,
        raiz=raiz,
        origem=origem,
        manter_rodas=args.manter_rodas,
        progresso=progresso,
    )
    for r in resultados:
        print(f"  [{r.estado}] {r.componente.titulo} {r.detalhe[:100]}")
    if ok:
        print(f"OK: {marca['arquivos_desempacotados']} arquivos em {raiz_do_runtime(raiz)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
