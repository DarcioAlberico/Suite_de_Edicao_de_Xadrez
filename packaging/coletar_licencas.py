r"""Recolhe o texto da licenca de cada dependencia distribuida (F12, ciclo 2).

O problema que este arquivo fecha
---------------------------------
O ciclo 1 terminou com esta frase em `LICENSING.md`: *"faltam os textos completos da
AGPL-3.0, da GPL-3.0 e da LGPL-3.0, e o arquivo consolidado de avisos de terceiros dentro do
pacote. A AGPL exige que acompanhem a distribuicao. Ate isso ser feito, o build e para uso
proprio."*

A AGPL-3.0 secao 4 e explicita: quem transmite copias tem de manter *intactos todos os avisos*
e **entregar junto uma copia da licenca**. A GPL-3.0 diz o mesmo, e as licencas permissivas
(BSD, MIT, Apache) todas exigem que o texto e o aviso de copyright acompanhem as
redistribuicoes binarias. Um pacote sem esses arquivos nao pode ser entregue a ninguem --
nao por rigor, por obrigacao.

O que "dependencia distribuida" quer dizer aqui
-----------------------------------------------
Nao e "o que o `pyproject.toml` declara". E **o que sai no bundle**: cada pasta de primeiro
nivel de `dist/Caissa/_internal/` mapeada de volta para a distribuicao que a instalou, mais
as rodas que o assistente de primeira execucao entrega em `runtime/` (torch e companhia).
A diferenca importa: o `pyproject` declara `pyside6-essentials`, que nao esta no bundle, e
**nao** declara `mpmath`, que esta -- e e o segundo que cria obrigacao, nao o primeiro.

O texto integral da AGPL-3.0
----------------------------
`pymupdf-1.28.2.dist-info/COPYING` tem **64 bytes**: a frase "Dual Licensed - GNU AFFERO GPL
3.0 or Artifex Commercial License", e nada mais. O texto da licenca que rege o binario
inteiro nao vem com a dependencia que a impoe. Ele foi tirado de uma copia integral que ja
existe nesta maquina (ver `FONTES_DOS_TEXTOS` abaixo) e o `sha256` esta registrado no indice,
para que qualquer pessoa possa conferir que e o texto canonico e nao uma parafrase.

    .venv-pack\Scripts\python.exe packaging/coletar_licencas.py
    .venv-pack\Scripts\python.exe packaging/coletar_licencas.py --conferir
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

PROJETO = Path(__file__).resolve().parents[1]
PACOTE = PROJETO / "packaging"
LICENCAS = PACOTE / "licenses"
INDICE = LICENCAS / "INDICE.json"

LIMITE_DE_UMA_LINHA = 200
"""Acima disso o campo `License` do metadado nao e um nome de licenca e sim o texto dela
inteiro colado no campo errado -- caso comum, e usa-lo como rotulo daria uma tabela
ilegivel."""

PAR = 2
"""Um `.toc` do PyInstaller e ou uma lista de entradas, ou a tupla `(cabecalho, entradas)`;
cada entrada e `(nome, caminho, tipo)`. As duas comparacoes sao contra esse formato."""
TERCEIROS = LICENCAS / "TERCEIROS.md"

FONTES_DOS_TEXTOS: dict[str, tuple[str, str]] = {
    "AGPL-3.0.txt": (
        r"C:\Python-Chess2\build\bin\Lib\site-packages\ebooklib-0.20.dist-info\licenses\LICENSE.txt",
        "GNU AFFERO GENERAL PUBLIC LICENSE",
    ),
    "GPL-3.0.txt": (
        r"pyqt6-6.11.0.dist-info/licenses/LICENSE",
        "GNU GENERAL PUBLIC LICENSE",
    ),
    "LGPL-3.0.txt": (
        r"pyqt6_qt6-6.11.2.dist-info/LICENSE",
        "GNU LESSER GENERAL PUBLIC LICENSE",
    ),
}
"""De onde sai cada texto integral, e a primeira linha que ele TEM de conter.

Os dois ultimos vem do proprio ambiente de empacotamento -- o PyQt6 traz a GPL-3.0 inteira
(35.147 bytes) e o PyQt6-Qt6 traz a LGPL-3.0 (7.687 bytes). O primeiro nao: nenhuma
dependencia deste projeto embarca o texto da AGPL, inclusive a que a impoe. A copia usada e
a que acompanha o `ebooklib` num venv vizinho desta maquina; o `sha256` fica no indice e a
verificacao de cabecalho acontece a cada coleta, porque copiar o arquivo errado com o nome
certo seria pior do que nao ter arquivo nenhum."""

ARTEFATOS_NAO_PYTHON: dict[str, dict[str, str]] = {
    "assets-piece_images": {
        "titulo": "assets/piece_images/ (12 PNG de peca, conjunto cburnett)",
        "licenca": "GPL-2.0-or-later, redistribuido sob GPL-3.0 (Colin M.L. Burnett)",
        "arquivo": "PECAS_CBURNETT.md",
    },
    "pecas-do-tronco": {
        "titulo": "assets/piece_images/ do tronco - NAO DISTRIBUIDO",
        "licenca": "NAO APURADA - a arte foi medida como identica a um conjunto descrito"
        " como 'All rights reserved'",
        "arquivo": "PECAS_PROCEDENCIA.md",
    },
    "assets-lexico-acervo": {
        "titulo": "assets/lexico/acervo.txt.gz",
        "licenca": "do projeto (derivado do acervo do dono do projeto)",
        "arquivo": "",
    },
}
"""O que entra no bundle sem ser uma distribuicao Python. Um inventario de licencas que so
olha para `dist-info` deixa de fora exatamente os arquivos cuja procedencia e duvidosa."""

DISTRIBUICOES_QUE_NENHUM_MAPA_ENCONTRA = ("PyQt6-Qt6",)
"""Distribuicoes que instalam DENTRO da arvore de outra e por isso somem do mapa automatico.

`PyQt6-Qt6` grava em `PyQt6/Qt6/`, sem nome de topo proprio: `packages_distributions()`
devolve so `PyQt6` e `PyQt6_sip` para aquela pasta. Mas quem viaja no bundle sao as DLLs do
Qt -- 72 MB -- e elas sao **LGPL v3**, que e uma obrigacao de aviso de verdade. Uma linha
escrita a mao aqui e melhor do que uma obrigacao perdida por causa de um mapa incompleto."""


@dataclass
class Entrada:
    """Uma distribuicao e os textos de licenca que ela trouxe."""

    distribuicao: str
    versao: str
    licenca: str
    arquivos: list[str] = field(default_factory=list)
    onde_no_bundle: list[str] = field(default_factory=list)
    origem: str = "bundle"
    versoes_por_variante: dict[str, str] = field(default_factory=dict)
    """So para o que chega em `runtime/`: `{"cu128": "2.11.0+cu128", "cpu": "2.14.0+cpu"}`.

    Existe porque `versao` sai de `importlib.metadata` do venv de EMPACOTAMENTO, e o que a
    maquina do usuario recebe nao e essa roda -- e a que a GPU dele pedir. Um documento de
    licenca que declara `torch 2.14.0+cpu` para quem instalou `2.11.0+cu128` esta errado
    sobre o unico campo que identifica o que foi entregue."""

    def como_dict(self) -> dict[str, Any]:
        """Forma serializavel para `INDICE.json`."""
        return {
            "distribuicao": self.distribuicao,
            "versao": self.versao,
            "versoes_por_variante": dict(sorted(self.versoes_por_variante.items())),
            "licenca": self.licenca,
            "arquivos": sorted(self.arquivos),
            "onde_no_bundle": sorted(self.onde_no_bundle),
            "origem": self.origem,
        }


def _licenca_declarada(dist: metadata.Distribution) -> str:
    """`License-Expression`, `License:` ou os classificadores -- nessa ordem de confianca."""
    meta = dist.metadata
    expressao = meta.get("License-Expression")
    if expressao:
        return str(expressao).strip()
    texto = meta.get("License")
    if texto and len(str(texto)) < LIMITE_DE_UMA_LINHA and "\n" not in str(texto):
        return str(texto).strip()
    classificadores = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classificadores:
        return " / ".join(classificadores)
    return str(texto).strip().splitlines()[0][:120] if texto else "NAO DECLARADA"


def _arquivos_de_licenca(dist: metadata.Distribution) -> list[Path]:
    """Todo arquivo de licenca que a distribuicao embarca, sem duplicar por conteudo.

    O `torch` traz **97** arquivos de licenca (as dependencias vendorizadas dele), e a maioria
    e a mesma Apache-2.0 repetida. Deduplicar por hash e o que torna a pasta legivel sem
    perder nenhum texto distinto -- e o texto distinto e a obrigacao, nao o numero de copias.
    """
    base = dist._path if isinstance(getattr(dist, "_path", None), Path) else None
    if base is None or not base.is_dir():
        return []
    candidatos: list[Path] = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        alto = p.name.upper()
        if any(marca in alto for marca in ("LICEN", "COPYING", "NOTICE", "AUTHORS")):
            candidatos.append(p)
    vistos: set[str] = set()
    unicos: list[Path] = []
    for p in candidatos:
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest in vistos:
            continue
        vistos.add(digest)
        unicos.append(p)
    return unicos


PASTA_DE_BUILD = PROJETO / "build" / "caissa"


def _topos_do_toc() -> set[str] | None:
    r"""Os nomes de topo que o PyInstaller REALMENTE coletou, lidos dos `.toc` do build.

    **Isto e o conserto de um erro de metodo.** A primeira versao desta funcao olhava as
    pastas de `_internal/`, e por isso perdia toda distribuicao **pura em Python** -- que o
    PyInstaller nao extrai como pasta, e sim congela dentro do arquivo compilado. O resultado
    media 10 distribuicoes onde ha 17, e entre as sete perdidas estava a **python-chess
    (GPL-3.0+)**: uma dependencia copyleft ausente do inventario de licencas e exatamente o
    tipo de furo que este arquivo existe para fechar.

    Os `.toc` sao a lista que o build gravou, com o caminho de origem de cada modulo. Um
    caminho dentro de `site-packages` identifica a distribuicao sem ambiguidade.
    """
    if not PASTA_DE_BUILD.is_dir():
        return None
    import ast

    topos: set[str] = set()
    marca = f"site-packages{os.sep}"
    for toc in sorted(PASTA_DE_BUILD.glob("*.toc")):
        try:
            dados = ast.literal_eval(toc.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        eh_par = isinstance(dados, tuple) and len(dados) == PAR
        entradas = dados[1] if eh_par else dados
        if not isinstance(entradas, list):
            continue
        for entrada in entradas:
            if not (isinstance(entrada, tuple) and len(entrada) >= PAR):
                continue
            origem = str(entrada[1])
            if marca not in origem:
                continue
            resto = origem.split(marca, 1)[1]
            primeiro = Path(resto).parts[0]
            topos.add(primeiro[:-3] if primeiro.endswith(".py") else primeiro)
    return topos or None


def distribuicoes_do_bundle(bundle: Path | None) -> dict[str, list[str]]:
    """Mapa `distribuicao -> nomes de topo dela no bundle`.

    Tres fontes, em ordem de confianca: os `.toc` do build (a lista que o PyInstaller
    gravou), as pastas de `_internal/` (so pega o que tem binario ou dado), e -- sem nenhum
    build -- o proprio ambiente de empacotamento. O indice registra qual foi usada, porque a
    diferenca entre "o que o bundle leva" e "o que o venv tem" e justamente o que a regra de
    `excludes` produz.
    """
    de_pacote: dict[str, list[str]] = {}
    for topo, dists in metadata.packages_distributions().items():
        for d in dists:
            de_pacote.setdefault(d, []).append(topo)

    presentes = _topos_do_toc()
    if presentes is None:
        if bundle is None or not (bundle / "_internal").is_dir():
            return {d: sorted(set(t)) for d, t in de_pacote.items()}
        interno = bundle / "_internal"
        presentes = {p.name for p in interno.iterdir()}
        presentes |= {p.stem for p in interno.iterdir() if p.suffix in {".pyd", ".dll"}}
    elif bundle is not None and (bundle / "_internal").is_dir():
        interno = bundle / "_internal"
        presentes |= {p.name for p in interno.iterdir()}
        presentes |= {p.stem for p in interno.iterdir() if p.suffix in {".pyd", ".dll"}}

    saida: dict[str, list[str]] = {}
    for dist, topos in de_pacote.items():
        no_bundle = [t for t in set(topos) if t in presentes]
        if no_bundle:
            saida[dist] = sorted(no_bundle)
    return saida


def distribuicoes_do_runtime() -> dict[str, dict[str, str]]:
    """As rodas que o assistente entrega depois -- torch e as bibliotecas que so ele usa.

    Elas nao estao no bundle, mas **sao distribuidas por este projeto**: o instalador
    determina quais sao e o assistente as baixa. A obrigacao de licenca e a mesma.
    """
    caminho = PACOTE / "torch_manifesto.json"
    if not caminho.exists():
        return {}
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    saida: dict[str, dict[str, str]] = {}
    for variante in bruto["variantes"]:
        for roda in variante["rodas"]:
            chave = roda["distribuicao"].lower().replace("-", "_")
            saida.setdefault(chave, {})[variante["id"]] = roda["versao"]
    return saida


def coletar(bundle: Path | None = None) -> dict[str, Any]:
    """Recolhe tudo em `packaging/licenses/` e devolve o indice."""
    LICENCAS.mkdir(parents=True, exist_ok=True)
    no_bundle = distribuicoes_do_bundle(bundle)
    no_runtime = distribuicoes_do_runtime()

    entradas: dict[str, Entrada] = {}
    faltando: list[str] = []

    alvos: dict[str, str] = {}
    for d in no_bundle:
        alvos[d] = "bundle"
    for d in no_runtime:
        alvos.setdefault(d, "runtime (primeira execucao)")
    for d in DISTRIBUICOES_QUE_NENHUM_MAPA_ENCONTRA:
        alvos.setdefault(d, "bundle")

    for nome, origem in sorted(alvos.items()):
        try:
            dist = metadata.distribution(nome)
        except metadata.PackageNotFoundError:
            faltando.append(nome)
            continue
        entrada = Entrada(
            distribuicao=dist.metadata["Name"] or nome,
            versao=dist.version,
            licenca=_licenca_declarada(dist),
            onde_no_bundle=no_bundle.get(nome, []),
            origem=origem,
            versoes_por_variante={} if origem == "bundle" else no_runtime.get(nome, {}),
        )
        pasta = LICENCAS / entrada.distribuicao
        arquivos = _arquivos_de_licenca(dist)
        if arquivos:
            shutil.rmtree(pasta, ignore_errors=True)
            pasta.mkdir(parents=True, exist_ok=True)
            usados: set[str] = set()
            for p in arquivos:
                nome_alvo = p.name
                sufixo = 1
                while nome_alvo in usados:
                    sufixo += 1
                    nome_alvo = f"{p.stem}-{sufixo}{p.suffix}"
                usados.add(nome_alvo)
                shutil.copyfile(p, pasta / nome_alvo)
                entrada.arquivos.append(f"{entrada.distribuicao}/{nome_alvo}")
        entradas[entrada.distribuicao] = entrada

    textos = _copiar_textos_integrais()
    _escrever_pecas()

    sem_texto = sorted(e.distribuicao for e in entradas.values() if not e.arquivos)
    indice = {
        "esquema": 1,
        "gerado_em": datetime.now(UTC).date().isoformat(),
        "medido_com_bundle": str(bundle) if bundle else None,
        "comentario": [
            "Gerado por `packaging/coletar_licencas.py`. 'distribuicoes' lista TODA",
            "dependencia distribuida -- as que viajam em _internal/ e as que o assistente",
            "de primeira execucao entrega em runtime/. 'sem_texto' precisa ficar vazia:",
            "tests/integration/test_packaging.py reprova o build se nao ficar.",
        ],
        "textos_integrais": textos,
        "artefatos_nao_python": ARTEFATOS_NAO_PYTHON,
        "distribuicoes": [
            e.como_dict() for e in sorted(entradas.values(), key=lambda x: x.distribuicao.lower())
        ],
        "sem_texto": sem_texto,
        "nao_encontradas_no_ambiente": sorted(faltando),
    }
    INDICE.write_text(json.dumps(indice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _escrever_terceiros(indice)
    return indice


def _copiar_textos_integrais() -> dict[str, dict[str, Any]]:
    """AGPL-3.0, GPL-3.0 e LGPL-3.0 inteiras, conferidas pelo cabecalho."""
    site = Path(sys.prefix) / "Lib" / "site-packages"
    saida: dict[str, dict[str, Any]] = {}
    for nome, (origem, cabecalho) in FONTES_DOS_TEXTOS.items():
        caminho = Path(origem)
        if not caminho.is_absolute():
            caminho = site / origem
        if not caminho.is_file():
            saida[nome] = {"ok": False, "erro": f"nao encontrei {caminho}"}
            continue
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        if cabecalho not in texto[:600].upper():
            saida[nome] = {"ok": False, "erro": f"{caminho} nao comeca com {cabecalho!r}"}
            continue
        destino = LICENCAS / nome
        shutil.copyfile(caminho, destino)
        saida[nome] = {
            "ok": True,
            "origem": str(caminho),
            "bytes": destino.stat().st_size,
            "sha256": hashlib.sha256(destino.read_bytes()).hexdigest(),
        }
    return saida


def _escrever_pecas() -> None:
    """A atribuicao das pecas que entram e a procedencia das que saem.

    Os dois arquivos, e nao so o primeiro: quem recebe o pacote precisa saber sob que licenca
    esta a arte que ele carrega **e** por que a anterior nao esta la. A segunda pergunta e a
    que o ciclo 1 deixou aberta.
    """
    for nome in ("PECAS_CBURNETT.md", "PECAS_PROCEDENCIA.md"):
        (LICENCAS / nome).write_text((PACOTE / nome).read_text(encoding="utf-8"), encoding="utf-8")


def _escrever_terceiros(indice: dict[str, Any]) -> None:
    """O arquivo consolidado que a AGPL secao 4 e as licencas permissivas exigem."""
    linhas = [
        "# Avisos de terceiros - Caissa Studio",
        "",
        f"Gerado em {indice['gerado_em']} por `packaging/coletar_licencas.py`, a partir dos",
        "metadados das distribuicoes instaladas -- nao de memoria.",
        "",
        "O binario do Caissa Studio e uma obra combinada sob **AGPL-3.0-or-later** (ver",
        "`LICENSING.md`). Cada componente abaixo mantem a sua propria licenca; o texto de cada",
        "uma esta nesta pasta, no caminho indicado.",
        "",
        "## Textos integrais",
        "",
        "| Licenca | Arquivo | bytes | sha256 |",
        "|---|---|---:|---|",
    ]
    for nome, dados in sorted(indice["textos_integrais"].items()):
        if dados.get("ok"):
            linhas.append(
                f"| {nome[:-4]} | `{nome}` | {dados['bytes']} | `{dados['sha256'][:16]}...` |"
            )
        else:
            linhas.append(f"| {nome[:-4]} | **AUSENTE** | - | {dados.get('erro', '?')} |")

    linhas += [
        "",
        "## Dependencias distribuidas",
        "",
        "| Distribuicao | Versao | Licenca declarada | Onde | Texto |",
        "|---|---|---|---|---|",
    ]
    for d in indice["distribuicoes"]:
        arquivos = ", ".join(f"`{a}`" for a in d["arquivos"]) or "**FALTANDO**"
        no_bundle = ", ".join(f"`{o}`" for o in d["onde_no_bundle"])
        onde = no_bundle or d["origem"]
        por_variante = d.get("versoes_por_variante") or {}
        distintas = sorted(set(por_variante.values()))
        if len(distintas) > 1:
            # Repetir "1.14.0 (cpu) ou 1.14.0 (cu128)" para o que nao muda entre as rodas
            # so faria a coluna ilegivel; a distincao so importa onde ela existe.
            versao = " ou ".join(f"{v} ({k})" for k, v in sorted(por_variante.items()))
        elif distintas:
            versao = distintas[0]
        else:
            versao = d["versao"]
        linhas.append(f"| {d['distribuicao']} | {versao} | {d['licenca']} | {onde} | {arquivos} |")

    linhas += [
        "",
        "## Artefatos que nao sao distribuicoes Python",
        "",
        "| Artefato | Licenca | Registro |",
        "|---|---|---|",
    ]
    for dados in indice["artefatos_nao_python"].values():
        registro = f"`{dados['arquivo']}`" if dados["arquivo"] else "-"
        linhas.append(f"| {dados['titulo']} | {dados['licenca']} | {registro} |")

    linhas += [
        "",
        "## O que a AGPL-3.0 exige de quem distribui este build",
        "",
        "1. Entregar o **codigo-fonte correspondente** -- o do Caissa e o das bibliotecas",
        "   copyleft -- ou uma oferta escrita e valida de obte-lo, junto com o binario.",
        "2. Manter os avisos de copyright e **entregar o texto das licencas** (esta pasta).",
        "3. Licenciar o conjunto sob **AGPL-3.0-or-later**, e nao sob termos mais restritivos.",
        "4. Nao impedir que o usuario modifique e reinstale.",
        "5. Secao 13: se o programa **modificado** for oferecido pela rede, o fonte vai para os",
        "   usuarios desse servico, mesmo sem distribuir binario nenhum.",
        "",
    ]
    TERCEIROS.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada."""
    analisador = argparse.ArgumentParser(description="Coleta os textos de licenca (F12).")
    analisador.add_argument("--bundle", type=Path, default=PROJETO / "dist" / "Caissa")
    analisador.add_argument("--conferir", action="store_true", help="so confere e devolve codigo")
    args = analisador.parse_args(argv)

    bundle = args.bundle if args.bundle and args.bundle.exists() else None
    if args.conferir:
        if not INDICE.exists():
            print("INDICE.json nao existe. Rode sem --conferir.")
            return 1
        indice = json.loads(INDICE.read_text(encoding="utf-8"))
    else:
        indice = coletar(bundle)

    faltando = indice["sem_texto"]
    ausentes = [n for n, d in indice["textos_integrais"].items() if not d.get("ok")]
    print(
        f"{len(indice['distribuicoes'])} distribuicoes distribuidas; "
        f"bundle={indice['medido_com_bundle']}"
    )
    print(f"textos integrais: {sorted(indice['textos_integrais'])} ausentes={ausentes}")
    if faltando:
        print(f"SEM TEXTO DE LICENCA: {faltando}")
        return 1
    if ausentes:
        return 1
    print(f"Tudo com texto. Indice em {INDICE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
