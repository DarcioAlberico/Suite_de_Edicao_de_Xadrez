r"""O executor único de portões do Editor HTML/CSS — `EDITOR_HTML_CSS_ROADMAP.md` §0.2 (passo H0).

O crítico reprovou, nos documentos, os «aliases de pseudocomando» e os portões sem instrumento:
um portão que ninguém consegue rodar do mesmo jeito duas vezes não é portão. Este módulo é o
**único** caminho de execução de portões do programa. Cada passo acrescenta uma entrada na
tabela `PASSOS` — os instrumentos, os comandos do portão, as repetições e as sabotagens — e o
executor, para o passo pedido:

1. confere que **todo** instrumento e toda fixture existem; faltando um, **REPROVA** «instrumento
   ausente» e não roda nada (um portão que roda sem o instrumento mede outra coisa);
2. roda cada comando do portão (3× quando há tempo ou aleatoriedade) e exige PASSOU em **todas**
   as execuções;
3. roda **cada** sabotagem e exige que ela reprove **pelo motivo declarado**; a que passa, ou
   reprova por outro motivo (um `ImportError` não prova que o portão morde), é «sabotagem
   inócua», e o passo **REPROVA**;
4. grava `portao.json` na `--saida`: o HEAD dos dois repositórios, o que cada árvore tem fora do
   commit, cada execução (código, duração, as últimas linhas da saída), as medianas das métricas
   que os instrumentos gravaram e o veredito com os motivos.

Um comando passa quando termina com código 0 **e** a conferência dele, quando declarada, não acha
nada: a do H0 (`metricas_do_h0`) exige as cinco métricas com valor e intervalo para cada leitor,
modo e estrato, e reprova «métrica ausente» — o `sol_gate` faz o contrário com a ordem de leitura,
pula o portão quando ela falta (`gates.py:282-288`). Um instrumento que queira publicar números
grava `metricas.json` (um objeto plano de números) na pasta `{saida}` que recebe; o executor tira a
mediana de cada número entre as repetições.

**Onde grava.** `--saida` é obrigatória e só pode ficar sob `benchmarks/reports/editor/` ou na
pasta temporária do sistema — nunca em `labeling/`, `data/` ou `editor/` do usuário (roadmap
§0.3, anti-padrão 12).

**Os marcadores** de cada `argv`: `{py}` (o Python da suíte), `{pack}` (o do pacote, com PyQt6),
`{pyq}` (o do tronco), `{med}` (o de medição, `.venv-medicao`: o `pywinauto` da sonda UIA do H2,
que o produto não leva), `{saida}` (a pasta desta execução do comando), `{saida_do_passo}` (a pasta
do passo inteiro — a sabotagem que republica a execução 1 a acha ali), `{raiz}` e `{tronco}`; e
`{principal}`, o checkout principal, para o dado que o git não guarda (o manifesto privado) quando
o portão roda numa árvore limpa.

**A sabotagem do próprio executor** (portão do H0): `--sabotar aceita_sem_instrumento`, ou a
variável `EDITOR_PORTOES_SABOTAR=aceita_sem_instrumento`, desliga a conferência do item 1. O
teste do passo falso «instrumento ausente» passa então a ver PASSOU, e o `test_portoes` reprova.

Uso (PowerShell, na raiz da suíte)::

    . .\benchmarks\editor_ambiente.ps1
    & $PY benchmarks\editor_portoes.py --passo H0 --saida benchmarks\reports\editor\h0
    & $PY benchmarks\editor_portoes.py --listar
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]


def _checkout_principal(raiz: Path) -> Path:
    """O checkout principal quando `raiz` é uma árvore de `git worktree`.

    A do crítico, uma árvore limpa de remedição: ali não há `.venv`, e o tronco não é a pasta
    vizinha.
    """
    try:
        comum = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
            cwd=raiz,
            capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    except OSError:
        return raiz
    return Path(comum).parent if comum else raiz


PRINCIPAL = _checkout_principal(RAIZ)
TRONCO = PRINCIPAL.parent / "ChessVisionOFF_Puro"
RELATORIOS = RAIZ / "benchmarks" / "reports" / "editor"

#: As pastas do usuário que nenhum arnês deste programa toca (roadmap §0.3).
PASTAS_DO_USUARIO = ("labeling", "data", "editor")

VARIAVEL_DE_SABOTAGEM = "EDITOR_PORTOES_SABOTAR"
SABOTAGENS_DO_EXECUTOR = ("aceita_sem_instrumento",)

#: Quantas linhas do fim da saída de cada execução vão ao `portao.json`.
LINHAS_NO_RELATORIO = 40

APROVADO = "PASSOU"
REPROVADO = "REPROVADO"


# --------------------------------------------------------------------------- #
# A tabela
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Comando:
    """Um comando de portão ou de sabotagem.

    ``ambiente`` escolhe as variáveis do processo filho:

    - ``suite``: o ambiente de quem chamou, mais ``PYTHONIOENCODING=utf-8``;
    - ``portoes``: o dos portões Qt da suíte (`Enter-AmbienteDosPortoes` do roadmap §0.2) —
      ``PYTHONPATH`` com o ``src`` da suíte, o do tronco e o ``site-packages`` do pacote,
      ``QT_QPA_PLATFORM=offscreen``;
    - ``testes_qt``: o dos testes Qt da suíte (`Enter-AmbienteDosTestesQt`);
    - ``tronco``: o do tronco, com a pasta de trabalho no tronco.
    """

    nome: str
    argv: tuple[str, ...]
    ambiente: str = "suite"
    repeticoes: int = 1
    tempo_limite_s: float = 4 * 3600.0
    env: tuple[tuple[str, str], ...] = ()
    #: A conferência que roda sobre a pasta do comando quando ele sai com 0 (`CONFERENCIAS`).
    conferir: str | None = None


@dataclass(frozen=True)
class Sabotagem:
    """Uma sabotagem: o comando que liga o defeito, e o motivo que a reprovação tem de dizer."""

    nome: str
    comando: Comando
    motivo: str


@dataclass(frozen=True)
class Passo:
    """Uma entrada da tabela: tudo o que o portão de um passo precisa, e só isso."""

    nome: str
    descricao: str
    instrumentos: tuple[str, ...]
    portao: tuple[Comando, ...]
    sabotagens: tuple[Sabotagem, ...] = ()


def _pytest(*alvos: str) -> tuple[str, ...]:
    return ("{py}", "-m", "pytest", *alvos, "-q", "-p", "no:cacheprovider")


# --------------------------------------------------------------------------- #
# As conferências
# --------------------------------------------------------------------------- #

ESTRATOS_DO_H0 = ("digitalizado", "nativo")
LEITORES_DO_H0 = ("fusao", "glifo", "glifo_bloco", "camada")
METRICAS_DO_H0 = ("cer", "lances", "insercao", "figurinas", "ordem")
#: As métricas que podem sair «não se aplica»: as que têm denominador na verdade. O CER e a
#: ordem de leitura existem em toda região e em toda página de duas regiões.
PODEM_NAO_SE_APLICAR = frozenset({"figurinas", "lances", "insercao"})
FIGURINAS = frozenset(chr(c) for c in range(0x2654, 0x2660))


#: O mínimo do H0 (roadmap H0, «denominador mínimo»), que o executor confere por conta própria.
MIN_REGIOES_CASADAS = 150
MIN_LIVROS = 2
#: A região casa quando algum leitor a cobre com IoU ≥ 0,5 (roadmap H0).
IOU_CASADA = 0.5
MANIFESTO_DO_H0 = "benchmarks/corpus/golden/manifest.private.json"
ESTRATO_DA_FONTE = {"pdf-scan": "digitalizado", "pdf-native": "nativo"}
CAMPOS_DA_DECLARACAO = ("metrica", "denominador", "valor_do_denominador", "motivo")


def _hash_da_lista(lista: Any) -> str:
    """O mesmo `_hash` de `editor_leitores.py`: a lista das regiões gravada antes da leitura."""
    import hashlib

    return hashlib.sha256(json.dumps(lista, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()[:16]


@dataclass
class Auditoria:
    """O que o executor conferiu da publicação, e os denominadores contados no manifesto."""

    denominadores: dict[str, dict[str, int]]
    problemas: list[str]


def _contar_o_manifesto(manifesto: Any) -> tuple[dict[str, tuple[str, str]],
                                                  dict[str, dict[str, int]]]:
    """As regiões de PDF do manifesto (id → estrato e livro) e os lances de cada estrato."""
    from caissa.ocr.metrics import move_tokens

    esperadas: dict[str, tuple[str, str]] = {}
    contas: dict[str, dict[str, int]] = {e: {"lances": 0, "figurinas": 0, "regioes": 0}
                                         for e in ESTRATOS_DO_H0}
    for item in manifesto.items:
        estrato = ESTRATO_DA_FONTE.get(str(item.source))
        if estrato is None:
            continue
        for regiao in item.regions:
            if (regiao.box or item.clip) is None:
                continue
            chave = item.id if len(item.regions) == 1 else f"{item.id}#{regiao.reading_order}"
            esperadas[chave] = (estrato, item.book)
            tokens = move_tokens(regiao.truth)
            contas[estrato]["regioes"] += 1
            contas[estrato]["lances"] += len(tokens)
            contas[estrato]["figurinas"] += sum(1 for t in tokens
                                                if any(c in FIGURINAS for c in t))
    return esperadas, contas


def _conferir_lista(unidades: dict[str, Any], esperadas: dict[str, tuple[str, str]]) -> list[str]:
    """A lista gravada antes da leitura: o hash dela, os ids e os estratos contra o manifesto."""
    problemas = []
    lista = unidades.get("unidades")
    if not isinstance(lista, list) or _hash_da_lista(lista) != unidades.get("hash_da_lista"):
        problemas.append("publicação inconsistente: a lista das unidades não confere com o "
                         "hash_da_lista")
        lista = lista if isinstance(lista, list) else []
    if not all(isinstance(u, dict) for u in lista):
        problemas.append("publicação inconsistente: unidade sem a forma de registro na lista")
        lista = [u for u in lista if isinstance(u, dict)]
    ids = [u.get("id") for u in lista]
    if len(ids) != len(set(ids)):
        problemas.append("publicação inconsistente: id repetido na lista das unidades")
    if set(ids) != set(esperadas):
        sem_arquivo = unidades.get("livros_sem_arquivo") or []
        problemas.append(f"publicação inconsistente: a lista tem {len(set(ids))} regiões e o "
                         f"manifesto, {len(esperadas)}"
                         + (f" (livros sem arquivo: {sem_arquivo})" if sem_arquivo else ""))
    problemas += [f"publicação inconsistente: estrato adulterado em {u.get('id')}" for u in lista
                  if u.get("id") in esperadas and u.get("estrato") != esperadas[u["id"]][0]]
    return problemas


def _casada_pelo_iou(regiao: dict[str, Any]) -> bool | None:
    """O `casada` que os IoUs publicados sustentam; `None` quando falta o IoU de um leitor."""
    ious = [regiao.get(leitor, {}).get("iou") if isinstance(regiao.get(leitor), dict) else None
            for leitor in LEITORES_DO_H0]
    if not all(isinstance(i, int | float) and not isinstance(i, bool) for i in ious):
        return None
    return any(i >= IOU_CASADA for i in ious)


def _conferir_regioes(leitores: dict[str, Any], esperadas: dict[str, tuple[str, str]],
                      minimo: int) -> list[str]:
    """As regiões publicadas: as mesmas da lista, os mesmos estratos, e o mínimo do H0."""
    problemas = []
    regioes = leitores.get("regioes")
    if not isinstance(regioes, list):
        problemas.append("publicação inconsistente: o leitores.json não traz as regiões")
        regioes = []
    if not all(isinstance(r, dict) for r in regioes):
        problemas.append("publicação inconsistente: região sem a forma de registro no "
                         "leitores.json")
        regioes = [r for r in regioes if isinstance(r, dict)]
    if {r.get("id") for r in regioes} != set(esperadas) or len(regioes) != len(esperadas):
        problemas.append("publicação inconsistente: as regiões do leitores.json não são as da "
                         "lista")
    problemas += [f"publicação inconsistente: estrato adulterado em {r.get('id')}" for r in regioes
                  if r.get("id") in esperadas and r.get("estrato") != esperadas[r["id"]][0]]
    incoerentes = [r.get("id") for r in regioes if r.get("casada") is not _casada_pelo_iou(r)]
    if incoerentes:
        problemas.append(f"publicação inconsistente: «casada» que os IoUs não sustentam em "
                         f"{len(incoerentes)} região(ões), a primeira {incoerentes[0]}")
    casadas = [r for r in regioes if r.get("casada") is True and r.get("id") in esperadas
               and _casada_pelo_iou(r) is True]
    livros = {esperadas[r["id"]][1] for r in casadas}
    estratos = {esperadas[r["id"]][0] for r in casadas}
    if len(casadas) < minimo or len(livros) < MIN_LIVROS or estratos != set(ESTRATOS_DO_H0):
        problemas.append(f"verdade insuficiente: {len(casadas)} regiões casadas (mínimo {minimo}), "
                         f"{len(livros)} livro(s), estratos {sorted(estratos)}")
    return problemas


def manifesto_do_executor() -> Path:
    """O manifesto dourado que o executor lê por conta própria (o instrumento `{principal}/…`)."""
    for base in (RAIZ, _checkout_principal(RAIZ)):
        if (base / MANIFESTO_DO_H0).is_file():
            return base / MANIFESTO_DO_H0
    return _checkout_principal(RAIZ) / MANIFESTO_DO_H0


def auditar_publicacao(pasta: Path, *, manifesto: Path | None = None,
                       minimo: int = MIN_REGIOES_CASADAS) -> Auditoria:
    """Confere a publicação do H0 contra o manifesto, sem tomar nada dela como dado.

    O manifesto é o do executor (`manifesto_do_executor`), e não o que o `unidades.json` nomeia:
    o hash dele tem de ser o que as duas publicações gravaram. A lista das unidades confere com o
    `hash_da_lista` (e o `leitores.json` traz o mesmo), sem id repetido e igual às regiões de PDF
    do manifesto (`dev` + `calib`), com o estrato de cada uma tirado da fonte do item; as regiões
    do `leitores.json` são exatamente as da lista, com o mesmo estrato e o `casada` que os IoUs
    publicados sustentam; e o mínimo do H0 (`minimo` casadas, dois livros, os dois estratos).

    **Os denominadores do «não se aplica» contam todas as regiões do estrato no manifesto**, e não
    as casadas que a publicação marcou (ciclo 20): se a verdade do estrato tem uma figurina, a
    métrica existe, e nenhuma marca da publicação a apaga.
    """
    if str(RAIZ / "src") not in sys.path:
        sys.path.insert(0, str(RAIZ / "src"))
    from caissa.ocr.golden import load_manifest

    caminho = manifesto or manifesto_do_executor()
    vazias = {e: {"lances": 0, "figurinas": 0, "regioes": 0} for e in ESTRATOS_DO_H0}
    try:
        unidades = json.loads((pasta / "unidades.json").read_text(encoding="utf-8"))
        leitores = json.loads((pasta / "leitores.json").read_text(encoding="utf-8"))
        identidade = load_manifest(caminho, include_blind=True).content_hash()
        carregado = load_manifest(caminho)
    except (OSError, ValueError, KeyError) as falha:
        return Auditoria(vazias, [f"publicação inconsistente: {type(falha).__name__}: {falha}"])
    if not isinstance(unidades, dict) or not isinstance(leitores, dict):
        return Auditoria(vazias, ["publicação inconsistente: o unidades.json ou o leitores.json "
                                  "não é um objeto"])
    problemas = []
    if identidade != unidades.get("hash_do_manifesto") or identidade != leitores.get(
            "hash_do_manifesto"):
        problemas.append("publicação inconsistente: o manifesto não é o da medição (hash)")
    if leitores.get("hash_da_lista") != unidades.get("hash_da_lista"):
        problemas.append("publicação inconsistente: o leitores.json não é da lista gravada antes "
                         "da leitura")
    esperadas, contas = _contar_o_manifesto(carregado)
    problemas += _conferir_lista(unidades, esperadas)
    problemas += _conferir_regioes(leitores, esperadas, minimo)
    return Auditoria(contas, problemas)


def _declaracao_valida(metrica: str, declaracao: Any) -> bool:
    return (isinstance(declaracao, dict)
            and all(campo in declaracao for campo in CAMPOS_DA_DECLARACAO)
            and declaracao["metrica"] == metrica
            and isinstance(declaracao["denominador"], str) and declaracao["denominador"].strip()
            and type(declaracao["valor_do_denominador"]) is int
            and declaracao["valor_do_denominador"] == 0
            and isinstance(declaracao["motivo"], str) and declaracao["motivo"].strip())


#: A faixa de cada métrica: o CER e os lances inventados (÷ lances na verdade) passam de 1 quando o
#: leitor inventa muito; lances certos, figurinas certas e a ordem (LCS ÷ verdade) são frações.
FAIXAS_DO_H0: dict[str, tuple[float, float]] = {
    "cer": (0.0, math.inf), "insercao": (0.0, math.inf),
    "lances": (0.0, 1.0), "figurinas": (0.0, 1.0), "ordem": (0.0, 1.0)}


def _numero(valor: Any) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool) and math.isfinite(valor)


def _defeito_da_metrica(metrica: str, dado: dict[str, Any]) -> str | None:
    """Por que a métrica publicada não vale, ou `None`.

    O valor é um número finito na faixa, e o intervalo, um par de números finitos na mesma
    faixa, com o limite de baixo ≤ o de cima.
    """
    valor, intervalo = dado.get("valor"), dado.get("ic95")
    baixo, alto = FAIXAS_DO_H0[metrica]
    if not _numero(valor):
        return f"o valor {valor!r} não é um número finito"
    if not baixo <= valor <= alto:
        return f"o valor {valor} fora de [{baixo}, {alto}]"
    if not (isinstance(intervalo, list | tuple) and len(intervalo) == 2
            and all(_numero(x) for x in intervalo)):
        return f"o intervalo {intervalo!r} não é um par de números finitos"
    if intervalo[0] > intervalo[1] or not all(baixo <= x <= alto for x in intervalo):
        return f"o intervalo {list(intervalo)} invertido ou fora de [{baixo}, {alto}]"
    return None


def _declaradas(bloco: dict[str, Any], estrato: str, auditoria: Auditoria,
                faltas: list[str]) -> set[str]:
    """As ausências declaradas que valem: o esquema inteiro e o denominador zero na verdade."""
    declaradas = set()
    nao_se_aplica = bloco.get("nao_se_aplica", {})
    if not isinstance(nao_se_aplica, dict):
        faltas.append(f"publicação inconsistente: o «não se aplica» do estrato {estrato} não é um "
                      "objeto")
        return declaradas
    for metrica, declaracao in nao_se_aplica.items():
        if metrica not in PODEM_NAO_SE_APLICAR:
            continue
        if not _declaracao_valida(metrica, declaracao):
            faltas.append(f"métrica ausente: {metrica} no estrato {estrato} com a declaração "
                          "de «não se aplica» incompleta")
            continue
        campo = "figurinas" if metrica == "figurinas" else "lances"
        real = auditoria.denominadores[estrato][campo]
        if real != 0:
            faltas.append(f"métrica ausente: {metrica} no estrato {estrato} declarada «não se "
                          f"aplica», mas a verdade tem {real} ({campo})")
            continue
        declaradas.add(metrica)
    return declaradas


def conferir_metricas_do_h0(pasta: Path, *, auditoria: Auditoria | None = None) -> list[str]:
    """As cinco métricas do H0, com valor e intervalo, para cada leitor, modo e estrato.

    A métrica publicada é um número finito na faixa dela, com o intervalo íntegro (ciclo 21); o
    que não for reprova «métrica inválida». A ausência só passa declarada (`nao_se_aplica`, com o
    esquema inteiro) e com o denominador **zero na verdade do estrato inteiro**, contado no
    manifesto pela `auditar_publicacao`, que confere também a publicação (ciclos 19 e 20); e a
    métrica declarada sai sem valor.
    """
    arquivo = pasta / "leitores.json"
    if not arquivo.is_file():
        return ["métrica ausente: o leitores.json não foi gravado"]
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    auditoria = auditoria or auditar_publicacao(pasta)
    faltas = list(auditoria.problemas)
    por_estrato = dados.get("por_estrato") if isinstance(dados, dict) else None
    for estrato in ESTRATOS_DO_H0:
        bloco = por_estrato.get(estrato) if isinstance(por_estrato, dict) else None
        if not isinstance(bloco, dict):
            faltas.append(f"métrica ausente: o estrato {estrato} não foi publicado")
            continue
        declaradas = _declaradas(bloco, estrato, auditoria, faltas)
        leitores = bloco.get("leitores")
        for leitor in LEITORES_DO_H0:
            valores = leitores.get(leitor) if isinstance(leitores, dict) else None
            valores = valores if isinstance(valores, dict) else {}
            for metrica in METRICAS_DO_H0:
                dado = valores.get(metrica)
                onde = f"{metrica} de {leitor} no estrato {estrato}"
                vazia = not isinstance(dado, dict) or (dado.get("valor") is None
                                                       and dado.get("ic95") is None)
                if metrica in declaradas:
                    if not isinstance(dado, dict) or not vazia:
                        faltas.append(f"métrica inválida: {onde} declarada «não se aplica» e "
                                      "publicada com valor")
                    continue
                if vazia:
                    faltas.append(f"métrica ausente: {onde}")
                elif (defeito := _defeito_da_metrica(metrica, dado)) is not None:
                    faltas.append(f"métrica inválida: {onde} ({defeito})")
    return faltas


CONFERENCIAS: dict[str, Any] = {"metricas_do_h0": conferir_metricas_do_h0}


PASSOS: dict[str, Passo] = {
    "H0": Passo(
        nome="H0",
        descricao="o executor de portões, e os leitores medidos (a aba Texto contra a fusão)",
        instrumentos=(
            "benchmarks/editor_portoes.py",
            "benchmarks/editor_ambiente.ps1",
            "tests/unit/editor/test_portoes.py",
            "benchmarks/editor_leitores.py",
            "{principal}/benchmarks/corpus/golden/manifest.private.json",
            "{pyq}",
        ),
        portao=(
            Comando("test_portoes", _pytest("tests/unit/editor/test_portoes.py")),
            Comando("leitores", ("{py}", "benchmarks/editor_leitores.py", "--saida", "{saida}"),
                    repeticoes=3, conferir="metricas_do_h0"),
        ),
        sabotagens=(
            Sabotagem(
                "aceita_sem_instrumento",
                Comando("test_portoes_sabotado", _pytest("tests/unit/editor/test_portoes.py"),
                        env=((VARIAVEL_DE_SABOTAGEM, "aceita_sem_instrumento"),)),
                motivo="instrumento ausente",
            ),
            Sabotagem(
                "so_uma_pagina",
                Comando("leitores_sabotado", ("{py}", "benchmarks/editor_leitores.py",
                                              "--sabotar", "so_uma_pagina", "--saida", "{saida}")),
                motivo="verdade insuficiente",
            ),
            Sabotagem(
                "sem_ordem",
                Comando("leitores_sem_ordem", (
                    "{py}", "benchmarks/editor_leitores.py", "--sabotar", "sem_ordem",
                    "--reusar", "{saida_do_passo}/leitores/1", "--saida", "{saida}"),
                    conferir="metricas_do_h0"),
                motivo="métrica ausente",
            ),
            *(Sabotagem(
                f"na_falso_{metrica}",
                Comando(f"leitores_na_falso_{metrica}", (
                    "{py}", "benchmarks/editor_leitores.py", "--sabotar", f"na_falso_{metrica}",
                    "--reusar", "{saida_do_passo}/leitores/1", "--saida", "{saida}"),
                    conferir="metricas_do_h0"),
                motivo="declarada «não se aplica», mas a verdade tem",
            ) for metrica in ("figurinas", "lances", "insercao")),
        ),
    ),
    "H2": Passo(
        nome="H2",
        descricao="o editor de código nativo aguenta, com tudo ligado?",
        instrumentos=(
            "src/caissa/editor/lexico.py",
            "src/caissa/editor/previa.py",
            "src/caissa/ui/widgets/editor_de_codigo.py",
            "tests/unit/editor/test_lexico.py",
            "tests/unit/ui/test_editor_de_codigo.py",
            "benchmarks/editor_codigo.py",
            "benchmarks/editor_uia.py",
            "{pack}",
            "{med}",
            "{tronco}/PDF",
        ),
        portao=(
            Comando("test_lexico", _pytest("tests/unit/editor/test_lexico.py")),
            Comando("test_editor_de_codigo", _pytest("tests/unit/ui/test_editor_de_codigo.py"),
                    ambiente="testes_qt"),
            Comando("codigo", ("{py}", "benchmarks/editor_codigo.py", "--saida", "{saida}"),
                    ambiente="testes_qt", repeticoes=3),
            Comando("uia", ("{med}", "benchmarks/editor_uia.py", "--saida", "{saida}")),
        ),
        sabotagens=(
            Sabotagem("realce_sincrono", Comando("codigo_realce_sincrono", (
                "{py}", "benchmarks/editor_codigo.py", "--sabotar", "realce_sincrono",
                "--segundos", "10", "--saida", "{saida}"), ambiente="testes_qt"),
                motivo="REPROVADO: abrir_2mb: pior bloqueio"),
            Sabotagem("funcoes_desligadas", Comando("codigo_funcoes_desligadas", (
                "{py}", "benchmarks/editor_codigo.py", "--sabotar", "funcoes_desligadas",
                "--segundos", "10", "--saida", "{saida}"), ambiente="testes_qt"),
                motivo="REPROVADO: prova de atividade: medida inválida"),
            Sabotagem("uia_mudo", Comando("uia_mudo", (
                "{med}", "benchmarks/editor_uia.py", "--sabotar", "uia_mudo",
                "--saida", "{saida}")), motivo="REPROVADO: a UIA leu certo em 0/50"),
        ),
    ),
    "H6": Passo(
        nome="H6",
        descricao="o projeto em disco: nada se perde sob queda, um livro por janela",
        instrumentos=(
            "src/caissa/editor/projeto.py",
            "src/caissa/editor/diario.py",
            "src/caissa/editor/versoes.py",
            "src/caissa/editor/livros.py",
            "src/caissa/editor/migracoes.py",
            "src/caissa/editor/trava.py",
            "src/caissa/editor/gravacao.py",
            "tests/unit/editor/test_projeto.py",
            "benchmarks/editor_recuperacao.py",
        ),
        portao=(
            Comando("test_projeto", _pytest(
                "tests/unit/editor/test_projeto.py",
                "tests/integration/test_packaging.py::TestPastasGuardadas",
                "tests/unit/ui/test_arquitetura.py::test_o_pacote_do_editor_nao_conhece_toolkit")),
            Comando("recuperacao", ("{py}", "benchmarks/editor_recuperacao.py",
                                    "--saida", "{saida}"), repeticoes=3),
        ),
        sabotagens=(
            Sabotagem("sem_diario", Comando("recuperacao_sem_diario", (
                "{py}", "benchmarks/editor_recuperacao.py", "--sabotar", "sem_diario",
                "--vezes", "5", "--saida", "{saida}")), motivo="REPROVADO: diário"),
            Sabotagem("escrita_direta", Comando("recuperacao_escrita_direta", (
                "{py}", "benchmarks/editor_recuperacao.py", "--sabotar", "escrita_direta",
                "--saida", "{saida}")), motivo="REPROVADO: gravação"),
            Sabotagem("sem_trava", Comando("recuperacao_sem_trava", (
                "{py}", "benchmarks/editor_recuperacao.py", "--sabotar", "sem_trava",
                "--vezes", "1", "--saida", "{saida}")),
                motivo="REPROVADO: trava: a segunda abertura"),
            Sabotagem("lru_sem_piso", Comando("recuperacao_lru_sem_piso", (
                "{py}", "benchmarks/editor_recuperacao.py", "--sabotar", "lru_sem_piso",
                "--vezes", "1", "--saida", "{saida}")), motivo="REPROVADO: versões: o piso"),
        ),
    ),
}


# --------------------------------------------------------------------------- #
# O resultado
# --------------------------------------------------------------------------- #


@dataclass
class Execucao:
    comando: str
    indice: int
    codigo: int
    duracao_s: float
    pasta: str
    saida_final: list[str] = field(default_factory=list)
    metricas: dict[str, float] = field(default_factory=dict)
    motivo_visto: bool | None = None


@dataclass
class Veredito:
    passo: str
    resultado: str
    motivos: list[str]
    instrumentos_ausentes: list[str]
    execucoes: list[Execucao]
    sabotagens: list[Execucao]
    medianas: dict[str, dict[str, float]]

    @property
    def passou(self) -> bool:
        return self.resultado == APROVADO

    def as_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        dados["passou"] = self.passou
        return dados


# --------------------------------------------------------------------------- #
# O executor
# --------------------------------------------------------------------------- #


def _sabotagem_do_executor() -> str:
    return os.environ.get(VARIAVEL_DE_SABOTAGEM, "")


def _ambiente_virtual(nome: str) -> Path:
    """`<raiz>/<nome>/Scripts/python.exe`, ou o do checkout principal numa árvore sem ele."""
    for base in (RAIZ, PRINCIPAL):
        candidato = base / nome / "Scripts" / "python.exe"
        if candidato.is_file():
            return candidato
    return RAIZ / nome / "Scripts" / "python.exe"


def interpretes() -> dict[str, Path]:
    """Os três Pythons do roadmap §0.2 e o de medição; o da suíte cai para o que roda o executor."""
    suite = _ambiente_virtual(".venv")
    return {
        "py": suite if suite.is_file() else Path(sys.executable),
        "pack": _ambiente_virtual(".venv-pack"),
        "pyq": TRONCO / ".venv" / "Scripts" / "python.exe",
        "med": _ambiente_virtual(".venv-medicao"),
    }


def _expandir(texto: str, *, saida: Path, passo: Path | None = None) -> str:
    """Troca só os marcadores conhecidos: um comando pode ter chaves suas (`-c "{...}"`)."""
    valores = {k: str(v) for k, v in interpretes().items()}
    valores.update(saida=str(saida), raiz=str(RAIZ), tronco=str(TRONCO), principal=str(PRINCIPAL),
                   saida_do_passo=str(passo if passo is not None else saida))
    for nome, valor in valores.items():
        texto = texto.replace("{" + nome + "}", valor)
    return texto


def instrumento_existe(nome: str) -> bool:
    """Um caminho relativo à raiz da suíte, ou um marcador de intérprete (`{pyq}`…)."""
    alvo = Path(_expandir(nome, saida=RAIZ))
    if not alvo.is_absolute():
        alvo = RAIZ / alvo
    return alvo.exists()


def pasta_permitida(pasta: Path) -> bool:
    """A `--saida` fica sob `benchmarks/reports/editor/` ou na temporária, fora das do usuário."""
    alvo = pasta.resolve()
    for nome in PASTAS_DO_USUARIO:
        proibida = (RAIZ / nome).resolve()
        if alvo == proibida or proibida in alvo.parents:
            return False
    raizes = (RELATORIOS.resolve(), Path(tempfile.gettempdir()).resolve())
    return any(alvo == r or r in alvo.parents for r in raizes)


def _ambiente(comando: Comando) -> tuple[dict[str, str], Path]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    cwd = RAIZ
    if comando.ambiente in ("portoes", "testes_qt"):
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"
        pacote = _ambiente_virtual(".venv-pack").parents[1] / "Lib" / "site-packages"
        partes = ([str(RAIZ / "src"), str(TRONCO / "src"), str(pacote)]
                  if comando.ambiente == "portoes" else [str(pacote)])
        env["PYTHONPATH"] = os.pathsep.join(partes)
    elif comando.ambiente == "tronco":
        cwd = TRONCO
    elif comando.ambiente != "suite":
        raise ValueError(f"ambiente desconhecido: {comando.ambiente!r}")
    env.update(dict(comando.env))
    return env, cwd


def _metricas(pasta: Path) -> dict[str, float]:
    arquivo = pasta / "metricas.json"
    if not arquivo.is_file():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): float(v) for k, v in dados.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}


def rodar(comando: Comando, pasta: Path, indice: int, *, motivo: str | None = None,
          passo: Path | None = None) -> Execucao:
    """Roda uma execução, com a saída num arquivo (e não num cano que um filho órfão segure)."""
    pasta.mkdir(parents=True, exist_ok=True)
    argv = [_expandir(parte, saida=pasta, passo=passo) for parte in comando.argv]
    env, cwd = _ambiente(comando)
    log = pasta / "saida.log"
    inicio = time.perf_counter()
    with log.open("w", encoding="utf-8") as destino:
        destino.write("$ " + " ".join(argv) + "\n")
        destino.flush()
        try:
            processo = subprocess.run(argv, cwd=cwd, env=env, stdout=destino,  # noqa: S603
                                      stderr=subprocess.STDOUT, timeout=comando.tempo_limite_s,
                                      check=False)
            codigo = processo.returncode
        except subprocess.TimeoutExpired:
            destino.write(f"\n!!! tempo esgotado ({comando.tempo_limite_s:.0f} s)\n")
            codigo = -9
        except OSError as erro:
            destino.write(f"\n!!! não executou: {erro}\n")
            codigo = -1
        if codigo == 0 and comando.conferir:
            faltas = CONFERENCIAS[comando.conferir](pasta)
            for falta in faltas:
                destino.write(f"\n!!! conferência {comando.conferir}: {falta}")
            if faltas:
                codigo = 2
    duracao = time.perf_counter() - inicio
    texto = log.read_text(encoding="utf-8", errors="replace")
    return Execucao(
        comando=comando.nome,
        indice=indice,
        codigo=codigo,
        duracao_s=round(duracao, 3),
        pasta=str(pasta),
        saida_final=texto.splitlines()[-LINHAS_NO_RELATORIO:],
        metricas=_metricas(pasta),
        motivo_visto=None if motivo is None else (motivo in texto),
    )


def _medianas(execucoes: list[Execucao]) -> dict[str, dict[str, float]]:
    por_comando: dict[str, dict[str, list[float]]] = {}
    for execucao in execucoes:
        for nome, valor in execucao.metricas.items():
            por_comando.setdefault(execucao.comando, {}).setdefault(nome, []).append(valor)
    return {comando: {nome: statistics.median(valores) for nome, valores in metricas.items()}
            for comando, metricas in por_comando.items()}


def julgar(passo: Passo, saida: Path) -> Veredito:
    """O veredito de um passo, na ordem do roadmap §0.2."""
    ausentes = [nome for nome in passo.instrumentos if not instrumento_existe(nome)]
    if ausentes and _sabotagem_do_executor() != "aceita_sem_instrumento":
        return Veredito(
            passo=passo.nome, resultado=REPROVADO,
            motivos=[f"instrumento ausente: {nome}" for nome in ausentes],
            instrumentos_ausentes=ausentes, execucoes=[], sabotagens=[], medianas={})

    motivos: list[str] = []
    execucoes: list[Execucao] = []
    for comando in passo.portao:
        for indice in range(comando.repeticoes):
            pasta = saida / comando.nome / str(indice + 1)
            execucao = rodar(comando, pasta, indice + 1, passo=saida)
            execucoes.append(execucao)
            if execucao.codigo != 0:
                motivos.append(f"portão reprovou: {comando.nome}, execução {indice + 1} de "
                               f"{comando.repeticoes} (código {execucao.codigo})")

    sabotagens: list[Execucao] = []
    for sabotagem in passo.sabotagens:
        pasta = saida / "sabotagem" / sabotagem.nome
        execucao = rodar(sabotagem.comando, pasta, 1, motivo=sabotagem.motivo, passo=saida)
        execucao.comando = sabotagem.nome
        sabotagens.append(execucao)
        if execucao.codigo == 0:
            motivos.append(f"sabotagem inócua: {sabotagem.nome} (o portão passou com ela)")
        elif not execucao.motivo_visto:
            motivos.append(f"sabotagem inócua: {sabotagem.nome} (reprovou, mas a saída não diz "
                           f"«{sabotagem.motivo}»; outro defeito não prova que o portão morde)")

    return Veredito(
        passo=passo.nome,
        resultado=REPROVADO if motivos else APROVADO,
        motivos=motivos,
        instrumentos_ausentes=ausentes,
        execucoes=execucoes,
        sabotagens=sabotagens,
        medianas=_medianas(execucoes),
    )


# --------------------------------------------------------------------------- #
# O registro
# --------------------------------------------------------------------------- #


def _git(repositorio: Path, *argumentos: str) -> str:
    try:
        return subprocess.run(["git", *argumentos], cwd=repositorio,  # noqa: S603, S607
                              capture_output=True,
                              text=True, encoding="utf-8", check=False).stdout.strip()
    except OSError:
        return ""


def estado_dos_repositorios() -> dict[str, dict[str, Any]]:
    """O HEAD e o que cada árvore tem fora do commit.

    Um número que não diz de que código veio não é um número (armadilha 36 da fase 5: o registro
    feito no fim da corrida).
    """
    estado: dict[str, dict[str, Any]] = {}
    for nome, repositorio in (("suite", RAIZ), ("tronco", TRONCO)):
        if not (repositorio / ".git").exists():
            estado[nome] = {"head": None, "fora_do_commit": None}
            continue
        sujos = _git(repositorio, "status", "--porcelain", "--untracked-files=all")
        estado[nome] = {
            "head": _git(repositorio, "rev-parse", "--short=12", "HEAD"),
            "ramo": _git(repositorio, "rev-parse", "--abbrev-ref", "HEAD"),
            "fora_do_commit": sorted(linha[3:] for linha in sujos.splitlines() if linha[3:]),
        }
    return estado


def gravar(veredito: Veredito, saida: Path, *, inicio: dict[str, Any],
           comeco: str, argv: list[str]) -> Path:
    registro = {
        "passo": veredito.passo,
        "veredito": veredito.as_dict(),
        "sabotagem_do_executor": _sabotagem_do_executor() or None,
        "argv": argv,
        "comeco": comeco,
        "fim": datetime.now(UTC).isoformat(timespec="seconds"),
        "repositorios_no_comeco": inicio,
        "repositorios_no_fim": estado_dos_repositorios(),
        "interpretes": {k: str(v) for k, v in interpretes().items()},
        "python": platform.python_version(),
        "plataforma": platform.platform(),
    }
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / "portao.json"
    destino.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--passo", help="o passo da tabela (H0, H1, …)")
    parser.add_argument("--saida", type=Path, help="pasta do portao.json (obrigatória com --passo)")
    parser.add_argument("--sabotar", choices=SABOTAGENS_DO_EXECUTOR, default=None,
                        help="sabotagem do próprio executor (o portão do H0)")
    parser.add_argument("--listar", action="store_true", help="imprime a tabela e sai")
    args = parser.parse_args(argv)

    if args.listar:
        for passo in PASSOS.values():
            print(f"{passo.nome}: {passo.descricao}")
            print(f"  instrumentos: {', '.join(passo.instrumentos)}")
            for comando in passo.portao:
                print(f"  portão {comando.nome} ×{comando.repeticoes}: {' '.join(comando.argv)}")
            for sabotagem in passo.sabotagens:
                print(f"  sabotagem {sabotagem.nome} (tem de dizer «{sabotagem.motivo}»)")
        return 0
    if not args.passo or args.saida is None:
        parser.error("--passo e --saida são obrigatórios")
    passo = PASSOS.get(args.passo)
    if passo is None:
        parser.error(f"passo desconhecido: {args.passo} (a tabela tem {', '.join(PASSOS)})")
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    if not pasta_permitida(saida):
        parser.error(f"--saida fora de {RELATORIOS} e da pasta temporária: {saida}")
    if args.sabotar:
        os.environ[VARIAVEL_DE_SABOTAGEM] = args.sabotar

    comeco = datetime.now(UTC).isoformat(timespec="seconds")
    inicio = estado_dos_repositorios()
    veredito = julgar(passo, saida)
    destino = gravar(veredito, saida, inicio=inicio, comeco=comeco, argv=sys.argv)
    print(f"{passo.nome}: {veredito.resultado}")
    for motivo in veredito.motivos:
        print(f"  - {motivo}")
    for comando, medianas in veredito.medianas.items():
        numeros = ", ".join(f"{k}={v:g}" for k, v in sorted(medianas.items()))
        print(f"  mediana {comando}: {numeros}")
    print(f"registro: {destino}")
    return 0 if veredito.passou else 1


if __name__ == "__main__":
    raise SystemExit(main())
