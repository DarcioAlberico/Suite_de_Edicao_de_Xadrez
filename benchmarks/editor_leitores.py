r"""A aba Texto contra a fusão do produto, nas mesmas regiões — EDITOR_HTML_CSS_ROADMAP passo H0.

O usuário decidiu (spec Q1 = C, 2026-09-24) que o editor recebe o OCR mais preciso para texto e
símbolos de xadrez, ou a combinação dos leitores. Os dois leitores que existem nunca foram
comparados nas mesmas páginas:

- **a fusão do produto** — o `import_pdf` da suíte (Python 3.11): camada de texto, Tesseract,
  RapidOCR, o classificador de glifos do tronco, o modelo e a cifra do livro, decididos por página
  em `PdfImporter._decide_source`;
- **o leitor da aba Texto** — `text.leitor.ler_pagina` do tronco (Python 3.10), nos três modos da
  aba: `glifo` (o padrão), `glifo` com o modo bloco (RapidOCR por bloco) e `camada`.

Este instrumento lê as mesmas páginas pelos dois, cada um no seu ambiente (um subprocesso com o
Python de cada repositório, JSON na ida e na volta), e compara região por região contra a verdade
do manifesto dourado. **Nada aqui decide**: o H0b mede a combinação e liga só o que provar ganho.

## O conjunto com verdade, e o que conta como região casada

O manifesto dourado (`benchmarks/corpus/golden/manifest.private.json`, só nesta máquina),
partições `dev` e `calib` — a `blind` nunca é carregada (R1.4). Cada item de PDF tem uma região,
com a caixa em pontos (a do item quando a região não tem a sua). O estrato é o do manifesto:
`Source.PDF_SCAN` é o digitalizado e `Source.PDF_NATIVE` o nativo. A lista das regiões, com o
hash, é gravada (`unidades.json`) antes de qualquer leitura.

A leitura de cada leitor são linhas com caixa **em pontos PDF**, e a conversão acontece uma vez,
dentro do próprio leitor: o produto passa os pixels do OCR a pontos em
`PageRecognition.to_page_text` (`frame.pixels_to_page`), o tronco em `montar` (`_para_pontos`).
A fixture de geometria prova isso a cada execução: um PDF sintético com dois parágrafos em
caixas conhecidas, em alturas diferentes da página, lidos pelos dois; para cada caixa, as linhas
de cada leitor que caem nela têm união com IoU ≥ 0,9 contra a caixa das palavras (dois retângulos
provam também que a leitura não junta os dois parágrafos num só).

Para cada região *G* e cada leitor, entram as linhas com ao menos metade da área dentro de *G*,
de cima para baixo. A região está **casada** quando, para algum leitor, a união dessas linhas
tem IoU ≥ 0,5 com *G* — a caixa da verdade está onde há texto. Todos os leitores são medidos em
todas as regiões casadas: o leitor que não leu nada ali paga CER 1,0 (é o erro dele).

## O que se publica

Por estrato e por métrica, com intervalo de 95 % por reamostragem das regiões (1.000 reamostras,
semente 42, pareada — as mesmas regiões para os dois lados de cada diferença):

- **CER** (média por região);
- **lances certos** e **lances inventados** (inserção), pelo `move_accounting` de `ocr/metrics.py`
  — a régua do `bench_sol`;
- **figurinas certas**: dos lances da verdade que levam figurina, a fração que a leitura tem com
  a mesma figurina (a interseção de multiconjuntos dos `move_tokens` com figurina);
- **ordem de leitura**: o `reading_order_accuracy` de `ocr/metrics.py` (a régua do `sol_gate`)
  sobre a ordem das regiões casadas de cada página com duas ou mais, com o intervalo por
  reamostragem das **páginas**; e, ao lado, a **precisão de regiões** (as regiões achadas sobre os
  blocos do leitor que caem nelas), porque a régua da ordem não vê região a mais.

**As cinco métricas são obrigatórias** (roadmap H0, 1.17): o `editor_portoes.py` reprova «métrica
ausente» quando uma falta. A única ausência aceita é a declarada — `nao_se_aplica`, com o motivo —
quando a verdade do estrato não tem o denominador: no nativo do manifesto de 2026-09-24 nenhum
lance leva figurina (0 de 198), e «figurinas certas» ali é 0/0 (mutação registrada no roadmap §10).

**A ordem verdadeira** entre as regiões de uma página não está no manifesto (cada item tem a sua
região com `reading_order` 0). Ela é derivada das caixas rotuladas, pela regra que um leitor
segue (a mesma do tronco, `text/pagina.py`): o elemento que atravessa as colunas separa faixas;
em cada faixa, as colunas da esquerda para a direita; em cada coluna, de cima para baixo. A ordem
de cada leitor é a ordem em que ele entrega as regiões: a aba, a das linhas da `PaginaLida`; o
produto, a dos **blocos do IR** (a que o editor recebe), e não a das linhas cruas da página.
- as **diferenças** de cada modo da aba contra a fusão, orientadas para que positivo seja melhor
  para o modo;
- a **margem do oráculo**: a métrica se cada região ficasse com a melhor leitura entre a fusão e
  o modo — o teto do que a combinação pode ganhar;
- o tempo por página de cada leitor; o hash do manifesto, o da lista das regiões e o das
  respostas de cada leitor (as três execuções do portão têm de repeti-lo);
- o resultado **por região e por página** — a entrada do H0b, que reamostra por página e decide
  com ele o leitor padrão da aba.

Sem verdade, para o contexto: o livro do pedido p. 50–60 e o `LIVRO` p. 31–38 — a discordância
por caractere de cada modo contra a fusão, as figurinas, os diagramas e o tempo por página.

## O portão e a sabotagem

Com menos de 150 regiões casadas, de menos de 2 livros, ou sem um estrato, o instrumento
**REPROVA** «verdade insuficiente» e não publica números. `--sabotar so_uma_pagina` limita a
verdade a uma página e tem de reprovar assim. `--sabotar sem_ordem` publica sem a ordem de
leitura do modo `camada`, e o portão tem de reprovar «métrica ausente»; ela usa `--reusar` (as
leituras de uma execução anterior, republicadas sem ler de novo).

Os textos lidos ficam em `leituras.private.json`, na pasta da execução (sob
`benchmarks/reports/`, que o git ignora): o acervo não sai da máquina. O `leitores.json` e o
`metricas.json` só têm números. A importação não grava nada: a cifra do livro é lida do disco e
não é salva de volta, para as três execuções lerem o mesmo estado.

Uso::

    & $PY benchmarks\editor_leitores.py --saida benchmarks\reports\editor\h0\leitores\1
    & $PY benchmarks\editor_leitores.py --so-geometria --saida <pasta temporária>
"""

from __future__ import annotations

# Este arquivo também roda no Python 3.10 do tronco (`--lado tronco`): nada de 3.11 aqui.
import argparse
import fnmatch
import hashlib
import itertools
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]

MODOS: dict[str, dict[str, Any]] = {
    "glifo": {"motor": "glifo", "modo_bloco": False},
    "glifo_bloco": {"motor": "glifo", "modo_bloco": True},
    "camada": {"motor": "camada", "modo_bloco": False},
}
LEITORES = ("fusao", *MODOS)
#: A resolução da aba Texto (`ler_pagina`, dpi=220).
DPI_DA_ABA = 220

MIN_REGIOES = 150
MIN_LIVROS = 2
IOU_CASADA = 0.5
DENTRO_DA_REGIAO = 0.5
IOU_DA_GEOMETRIA = 0.9
REAMOSTRAS = 1000
SEMENTE = 42

ESTRATOS = ("digitalizado", "nativo")
METRICAS_DE_REGIAO = ("cer", "lances", "insercao", "figurinas")
METRICAS = (*METRICAS_DE_REGIAO, "ordem")
#: O sentido de cada métrica: +1 quando maior é melhor, -1 quando menor é melhor.
SENTIDO = {"cer": -1, "lances": 1, "insercao": -1, "figurinas": 1, "ordem": 1}
#: A fração da largura útil da página a partir da qual uma região é «larga» mesmo sem atravessar
#: uma calha (um título de página inteira numa página de uma coluna).
LARGA = 0.6

#: Contexto sem verdade (índices 0-based): o pedido p. 50–60 e o `LIVRO` p. 31–38.
CONTEXTO = (
    ("pedido", "A Matter of Endgame Technique*Jacob Aagaard.pdf", tuple(range(49, 60))),
    ("livro", "AAGAARD - Practical Chess Defence.pdf", tuple(range(30, 38))),
)

FIGURINAS = frozenset(chr(c) for c in range(0x2654, 0x2660))

#: `na_falso_<métrica>`: a métrica some do estrato digitalizado com um «não se aplica» falso
#: (denominador 0 declarado; a verdade tem lances e figurinas) — o executor tem de recontar.
SABOTAGENS = ("so_uma_pagina", "sem_ordem", "na_falso_figurinas", "na_falso_lances",
              "na_falso_insercao")

Caixa = tuple[float, float, float, float]
Linha = dict[str, Any]


class VerdadeInsuficiente(RuntimeError):  # noqa: N818 - o nome é a frase que o portão procura
    """O conjunto casado não sustenta número nenhum."""


# --------------------------------------------------------------------------- #
# Onde as coisas estão
# --------------------------------------------------------------------------- #


def _checkout_principal() -> Path:
    try:
        comum = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    except OSError:
        return RAIZ
    return Path(comum).parent if comum else RAIZ


PRINCIPAL = _checkout_principal()
TRONCO = PRINCIPAL.parent / "ChessVisionOFF_Puro"
PASTA_DE_PDF = TRONCO / "PDF"


def _no_checkout(relativo: str) -> Path:
    """Um arquivo que o git não guarda (o manifesto privado, o `labeling/`).

    Vem desta árvore ou da principal: a árvore limpa do crítico não os tem.
    """
    for base in (RAIZ, PRINCIPAL):
        if (base / relativo).exists():
            return base / relativo
    return RAIZ / relativo


def python_da_suite() -> Path:
    for base in (RAIZ, PRINCIPAL):
        candidato = base / ".venv" / "Scripts" / "python.exe"
        if candidato.is_file():
            return candidato
    return Path(sys.executable)


def python_do_tronco() -> Path:
    """O Python 3.10 do tronco — sem reserva: ler a aba com outro ambiente mediria outra coisa."""
    return TRONCO / ".venv" / "Scripts" / "python.exe"


def pdfs_rotulados() -> dict[str, Path]:
    """Os livros que os projetos de rotulagem registram (o SFC4 mora fora de `PDF/`)."""
    indice = _no_checkout("labeling/project.json")
    if not indice.is_file():
        return {}
    dados = json.loads(indice.read_text(encoding="utf-8"))
    return {str(livro): Path(caminho) for livro, caminho in dados.get("documents", {}).items()
            if Path(caminho).is_file()}


def arquivo_do_livro(livro: str, rotulados: dict[str, Path]) -> Path | None:
    """A mesma regra do `sol_corpus._open_pdf`: os 50 primeiros caracteres do nome."""
    for caminho in sorted(PASTA_DE_PDF.glob("*.pdf")):
        if caminho.stem[:50] == livro[:50]:
            return caminho
    for nome, caminho in rotulados.items():
        if nome[:50] == livro[:50]:
            return caminho
    return None


def livro_por_padrao(padrao: str) -> Path | None:
    achados = sorted(p for p in PASTA_DE_PDF.glob("*.pdf") if fnmatch.fnmatch(p.name, padrao))
    return achados[0] if achados else None


# --------------------------------------------------------------------------- #
# Geometria
# --------------------------------------------------------------------------- #


def area(caixa: Caixa) -> float:
    return max(0.0, caixa[2] - caixa[0]) * max(0.0, caixa[3] - caixa[1])


def intersecao(a: Caixa, b: Caixa) -> Caixa:
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def uniao(caixas: list[Caixa]) -> Caixa | None:
    if not caixas:
        return None
    return (min(c[0] for c in caixas), min(c[1] for c in caixas),
            max(c[2] for c in caixas), max(c[3] for c in caixas))


def iou(a: Caixa, b: Caixa) -> float:
    comum = area(intersecao(a, b))
    total = area(a) + area(b) - comum
    return comum / total if total > 0 else 0.0


def dentro(linha: Caixa, regiao: Caixa) -> bool:
    """A linha entra na região quando ao menos metade dela está lá dentro."""
    propria = area(linha)
    if propria <= 0:
        cx, cy = (linha[0] + linha[2]) / 2, (linha[1] + linha[3]) / 2
        return regiao[0] <= cx <= regiao[2] and regiao[1] <= cy <= regiao[3]
    return area(intersecao(linha, regiao)) >= DENTRO_DA_REGIAO * propria


def em_ordem(linhas: list[Linha]) -> list[Linha]:
    """De cima para baixo, e da esquerda para a direita na mesma faixa: a região é uma coluna."""
    if not linhas:
        return []
    alturas = sorted(max(1e-6, ln["caixa"][3] - ln["caixa"][1]) for ln in linhas)
    faixa = max(1.0, 0.5 * alturas[len(alturas) // 2])
    return sorted(linhas, key=lambda ln: (round((ln["caixa"][1] + ln["caixa"][3]) / 2 / faixa),
                                          ln["caixa"][0]))


def leitura_da_regiao(linhas: list[Linha], regiao: Caixa) -> tuple[str, float]:
    """O texto que o leitor tem na região, e o IoU da união das linhas com ela."""
    escolhidas = em_ordem([ln for ln in linhas if dentro(tuple(ln["caixa"]), regiao)])
    juntas = uniao([tuple(ln["caixa"]) for ln in escolhidas])
    return ("\n".join(ln["texto"] for ln in escolhidas),
            iou(juntas, regiao) if juntas is not None else 0.0)


# --------------------------------------------------------------------------- #
# O lado do tronco (Python 3.10)
# --------------------------------------------------------------------------- #


def _linhas_da_pagina_lida(dados: dict[str, Any]
                           ) -> tuple[list[Linha], list[dict[str, Any]], list[dict[str, Any]]]:
    """A `PaginaLida.para_json()` em linhas (texto, caixa em pontos, bloco), diagramas e blocos.

    As linhas saem na ordem da `PaginaLida` — a ordem de leitura da aba.
    """
    linhas: list[Linha] = []
    diagramas: list[dict[str, Any]] = []
    blocos: list[dict[str, Any]] = []

    def guardar(dado: dict[str, Any] | None, bloco: int) -> None:
        if dado and str(dado.get("texto", "")).strip():
            linhas.append({"texto": str(dado["texto"]), "caixa": [float(v) for v in dado["bbox"]],
                           "bloco": bloco})

    def novo_bloco(caixa: Any, tipo: str) -> int:
        blocos.append({"caixa": [float(v) for v in caixa] if caixa else [0.0, 0.0, 0.0, 0.0],
                       "tipo": tipo})
        return len(blocos) - 1

    if dados.get("cabecalho"):
        guardar(dados["cabecalho"], novo_bloco(dados["cabecalho"]["bbox"], "cabecalho"))
    for coluna in dados.get("colunas", []):
        for bloco in coluna.get("blocos", []):
            tipo = bloco.get("tipo")
            if tipo in ("texto", "tarja"):
                indice = novo_bloco(bloco.get("bbox"), tipo)
                for dado in bloco.get("linhas", []):
                    guardar(dado, indice)
            elif tipo == "tabela":
                texto = "\n".join("\t".join(fila) for fila in bloco.get("celulas", []))
                guardar({"texto": texto, "bbox": bloco.get("bbox")},
                        novo_bloco(bloco.get("bbox"), tipo))
            elif tipo == "diagrama":
                diagramas.append({"caixa": bloco.get("bbox"),
                                  "lido": bool(bloco.get("placement"))})
    if dados.get("rodape"):
        guardar(dados["rodape"], novo_bloco(dados["rodape"]["bbox"], "rodape"))
    return linhas, diagramas, blocos


def lado_tronco(pedido: dict[str, Any]) -> dict[str, Any]:
    fonte = str(Path(pedido["tronco"]) / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)
    from chess_diagram_ocr.text.leitor import ler_pagina

    paginas = []
    for pagina in pedido["paginas"]:
        modos: dict[str, Any] = {}
        for modo in pedido["modos"]:
            inicio = time.perf_counter()
            try:
                lida = ler_pagina(pagina["arquivo"], int(pagina["indice"]), dpi=int(pedido["dpi"]),
                                  **MODOS[modo])
                linhas, diagramas, blocos = _linhas_da_pagina_lida(lida.para_json())
                erro = None
            except Exception as falha:  # noqa: BLE001 - a falha é um dado da medição, e fica dita
                linhas, diagramas, blocos = [], [], []
                erro = f"{type(falha).__name__}: {falha}"
            modos[modo] = {"linhas": linhas, "diagramas": diagramas, "blocos": blocos,
                           "erro": erro, "segundos": round(time.perf_counter() - inicio, 3)}
        paginas.append({"arquivo": pagina["arquivo"], "indice": pagina["indice"], "modos": modos})
    return {"paginas": paginas, "python": platform.python_version()}


# --------------------------------------------------------------------------- #
# O lado do produto (Python 3.11)
# --------------------------------------------------------------------------- #

#: O que cada fonte de `_decide_source` emite: as páginas que viram imagem não têm texto no IR.
FONTES_COM_TEXTO = frozenset({"ocr", "text-layer", "text-layer+ocr", "text-layer/review"})


def blocos_do_ir(documento: Any) -> dict[int, list[dict[str, Any]]]:
    """Os blocos-folha do IR com página e retângulo, na ordem do documento, por página.

    É a ordem que o editor recebe (o `import_pdf` já passou por `layout_page` e pelo
    `_sort_like_a_reader`); as linhas cruas do `PageText` estão na ordem do produtor.
    """
    from caissa.core.model.blocks import block_children

    por_pagina: dict[int, list[dict[str, Any]]] = {}
    ordem = 0
    pilha = list(reversed(documento.body))
    while pilha:
        bloco = pilha.pop()
        filhos = block_children(bloco)
        if filhos:
            pilha.extend(reversed(filhos))
            continue
        proveniencia = getattr(bloco, "provenance", None)
        retangulo = getattr(proveniencia, "rect", None)
        pagina = getattr(proveniencia, "page_index", None)
        if retangulo is None or pagina is None:
            continue
        por_pagina.setdefault(int(pagina), []).append({
            "ordem": ordem,
            "caixa": [float(retangulo.x), float(retangulo.y),
                      float(retangulo.x + retangulo.width), float(retangulo.y + retangulo.height)],
            "tipo": type(bloco).__name__,
        })
        ordem += 1
    return por_pagina


def lado_produto(pedido: dict[str, Any]) -> dict[str, Any]:
    """Importa as páginas de cada livro e guarda o `PageText` que `_decide_source` decide.

    Uma importação por livro, com as páginas dele juntas: a cifra do livro acumula como no
    produto. Nada é gravado — a cifra é lida do disco e não é salva de volta, para que as três
    execuções leiam o mesmo estado e o arnês não mexa nos modelos do usuário.
    """
    fonte = str(RAIZ / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)
    from caissa.ingest.pdf.importer import PdfImporter, PdfImportOptions, import_pdf

    capturas: dict[int, dict[str, Any]] = {}
    decidir = PdfImporter._decide_source
    montar = PdfImporter._build_page

    def decidir_e_guardar(self: Any, page: Any, frame: Any, text: Any, verdict: Any) -> Any:
        resposta = decidir(self, page, frame, text, verdict)
        fonte_da_pagina, _, _, lida = resposta
        linhas = ([{"texto": linha.text, "caixa": [float(v) for v in linha.box]}
                   for linha in lida.lines if linha.text.strip()]
                  if fonte_da_pagina in FONTES_COM_TEXTO else [])
        capturas.setdefault(frame.index, {}).update(fonte=fonte_da_pagina, linhas=linhas)
        return resposta

    def montar_e_medir(self: Any, index: int, builder: Any, finder: Any) -> Any:
        inicio = time.perf_counter()
        resposta = montar(self, index, builder, finder)
        capturas.setdefault(index, {}).update(
            segundos=round(time.perf_counter() - inicio, 3),
            diagramas=int(resposta[0].diagrams), diagramas_lidos=int(resposta[0].diagrams_read))
        return resposta

    PdfImporter._decide_source = decidir_e_guardar  # type: ignore[method-assign]
    PdfImporter._build_page = montar_e_medir  # type: ignore[method-assign]
    PdfImporter._save_book_cipher = lambda _self: None  # type: ignore[method-assign]

    por_livro: dict[str, list[int]] = {}
    for pagina in pedido["paginas"]:
        por_livro.setdefault(pagina["arquivo"], []).append(int(pagina["indice"]))
    paginas = []
    notas: dict[str, list[str]] = {}
    for arquivo, indices in sorted(por_livro.items()):
        capturas.clear()
        opcoes = PdfImportOptions(pages=sorted(set(indices)),
                                  ocr_config=pedido.get("ocr_config") or None)
        blocos: dict[int, list[dict[str, Any]]] = {}
        try:
            resultado = import_pdf(arquivo, opcoes)
            notas[arquivo] = list(resultado.report.notes)[:20]
            blocos = blocos_do_ir(resultado.document)
            erro = None
        except Exception as falha:  # noqa: BLE001 - a falha é um dado da medição, e fica dita
            erro = f"{type(falha).__name__}: {falha}"
        for indice in sorted(set(indices)):
            captura = capturas.get(indice, {})
            paginas.append({"arquivo": arquivo, "indice": indice,
                            "fonte": captura.get("fonte"), "linhas": captura.get("linhas", []),
                            "blocos": blocos.get(indice, []),
                            "segundos": captura.get("segundos"),
                            "diagramas": captura.get("diagramas", 0),
                            "diagramas_lidos": captura.get("diagramas_lidos", 0),
                            "erro": erro})
    return {"paginas": paginas, "notas": notas, "python": platform.python_version()}


# --------------------------------------------------------------------------- #
# A fixture de geometria
# --------------------------------------------------------------------------- #

#: Dois parágrafos de cinco a seis linhas, em alturas diferentes da página.
#:
#: **Por que tão longos.** A caixa de uma palavra da camada é a da *fonte* (ascendente e
#: descendente inteiros); a da leitura por glifo é a da *tinta*. Num parágrafo de duas linhas sem
#: descendente na última, a folga de ~0,2 em some da altura e o IoU cai para 0,8997 — medido em
#: 2026-09-24 — sem erro nenhum de unidade. Com cinco linhas a folga fica abaixo de 5 % da altura,
#: e um erro de unidade de verdade (a caixa em pixels de 220 dpi lida como pontos, ×3,06) dá IoU
#: bem abaixo do mínimo (0,35 no `test_a_geometria_pega_o_erro_de_unidade`).
PARAGRAFOS_DA_GEOMETRIA = (
    ((108.0, 120.0, 420.0, 300.0),
     "The rook belongs behind the passed pawn, whether the pawn is ours or the "
     "opponent's. After 1.Rb1 Kf7 2.b4 Ke6 3.b5 Kd7 the black king arrives in time, "
     "and the ending is a draw because the rook keeps checking from behind. Tarrasch "
     "wrote this rule in 1908, and it still decides most of the rook endings we play."),
    ((140.0, 430.0, 470.0, 610.0),
     "In the main line 4.Rb4 Kc7 5.Kf2 Kb6 the pawn falls, but the draw holds: the "
     "white king is cut off on the second rank, and every attempt to cross it costs a "
     "tempo. Grandmasters still lose this position in rapid games, which is why the "
     "rule is worth learning by heart before the next tournament game."),
)


def pdf_da_geometria(destino: Path) -> list[Caixa]:
    """Um PDF A4 com dois parágrafos em caixas conhecidas; a caixa das palavras de cada um."""
    import pymupdf

    documento = pymupdf.open()
    pagina = documento.new_page(width=595, height=842)
    verdades: list[Caixa] = []
    for caixa, paragrafo in PARAGRAFOS_DA_GEOMETRIA:
        sobra = pagina.insert_textbox(pymupdf.Rect(*caixa), paragrafo, fontsize=13,
                                      fontname="helv")
        if sobra < 0:          # o PyMuPDF não escreve nada quando o texto não cabe
            raise RuntimeError(f"o parágrafo da geometria não coube na caixa {caixa}")
    palavras = [tuple(float(v) for v in p[:4]) for p in pagina.get_text("words")]
    for caixa, _ in PARAGRAFOS_DA_GEOMETRIA:
        verdade = uniao([p for p in palavras if dentro(p, caixa)])
        if verdade is None:
            raise RuntimeError("a fixture de geometria saiu sem palavras")
        verdades.append(verdade)
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(str(destino))
    documento.close()
    return verdades


def _subprocesso(python: Path, lado: str, pedido: dict[str, Any], pasta: Path,
                 cwd: Path) -> dict[str, Any]:
    pasta.mkdir(parents=True, exist_ok=True)
    entrada = pasta / f"pedido_{lado}.json"
    resposta = pasta / f"resposta_{lado}.json"
    log = pasta / f"lado_{lado}.log"
    entrada.write_text(json.dumps(pedido, ensure_ascii=False, indent=1), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    comando = [str(python), str(Path(__file__).resolve()), "--lado", lado,
               "--pedido", str(entrada), "--resposta", str(resposta)]
    with log.open("w", encoding="utf-8") as destino:
        codigo = subprocess.run(comando, cwd=cwd, env=env, stdout=destino,  # noqa: S603
                                stderr=subprocess.STDOUT, check=False).returncode
    if codigo != 0 or not resposta.is_file():
        cauda = log.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
        raise RuntimeError(f"o lado {lado} falhou (código {codigo}):\n" + "\n".join(cauda))
    return json.loads(resposta.read_text(encoding="utf-8"))


def ler_pelos_dois(paginas: list[dict[str, Any]], pasta: Path
                   ) -> tuple[dict[tuple[str, int], dict[str, dict[str, Any]]], dict[str, Any]]:
    """As páginas lidas pela aba (três modos, no tronco) e pela fusão (na suíte), em sequência."""
    tronco = _subprocesso(python_do_tronco(), "tronco",
                          {"tronco": str(TRONCO), "paginas": paginas, "modos": list(MODOS),
                           "dpi": DPI_DA_ABA}, pasta, TRONCO)
    produto = _subprocesso(python_da_suite(), "produto", {"paginas": paginas}, pasta, RAIZ)
    leituras: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for dados in produto["paginas"]:
        leituras.setdefault((dados["arquivo"], dados["indice"]), {})["fusao"] = dados
    for dados in tronco["paginas"]:
        for modo, lido in dados["modos"].items():
            leituras.setdefault((dados["arquivo"], dados["indice"]), {})[modo] = lido
    ambiente = {"suite": platform.python_version(), "tronco": tronco.get("python"),
                "notas_do_produto": produto.get("notas", {})}
    return leituras, ambiente


def releitura(pasta: Path) -> tuple[dict[tuple[str, int], dict[str, dict[str, Any]]],
                                     dict[str, Any]]:
    """As leituras de uma execução anterior (`resposta_*.json`), sem ler de novo."""
    tronco = json.loads((pasta / "resposta_tronco.json").read_text(encoding="utf-8"))
    produto = json.loads((pasta / "resposta_produto.json").read_text(encoding="utf-8"))
    leituras: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for dados in produto["paginas"]:
        leituras.setdefault((dados["arquivo"], dados["indice"]), {})["fusao"] = dados
    for dados in tronco["paginas"]:
        for modo, lido in dados["modos"].items():
            leituras.setdefault((dados["arquivo"], dados["indice"]), {})[modo] = lido
    return leituras, {"suite": platform.python_version(), "tronco": tronco.get("python"),
                      "reusado_de": str(pasta)}


def medir_geometria(pasta: Path) -> dict[str, Any]:
    """A fixture de coordenadas conhecidas, lida pelos dois leitores (roadmap H0).

    Cada leitor, em cada um dos dois retângulos: as linhas que caem nele (a mesma regra das
    regiões do manifesto) têm união com IoU ≥ 0,9 contra a caixa das palavras.
    """
    arquivo = pasta / "geometria.pdf"
    verdades = pdf_da_geometria(arquivo)
    leituras, _ = ler_pelos_dois([{"arquivo": str(arquivo), "indice": 0}], pasta)
    resultado: dict[str, Any] = {"verdades": [[round(v, 2) for v in c] for c in verdades],
                                 "iou": {}}
    for leitor, lido in leituras[(str(arquivo), 0)].items():
        resultado["iou"][leitor] = [
            round(leitura_da_regiao(lido.get("linhas", []), verdade)[1], 4)
            for verdade in verdades]
    resultado["passou"] = (set(resultado["iou"]) == set(LEITORES)
                           and all(v >= IOU_DA_GEOMETRIA
                                   for valores in resultado["iou"].values() for v in valores))
    return resultado


# --------------------------------------------------------------------------- #
# A ordem de leitura
# --------------------------------------------------------------------------- #


def calhas(caixas: list[Caixa]) -> list[tuple[float, float]]:
    """As calhas entre colunas.

    Uma calha é uma faixa vertical coberta por no máximo uma região em cinco (o título que a
    atravessa), com uma região inteira de cada lado.
    """
    if len(caixas) < 2:
        return []
    bordas = sorted({v for c in caixas for v in (c[0], c[2])})
    teto = max(1, len(caixas) // 5)
    achadas: list[tuple[float, float]] = []
    for a, b in itertools.pairwise(bordas):
        meio = (a + b) / 2
        cobrem = sum(1 for c in caixas if c[0] < meio < c[2])
        esquerda = any(c[2] <= a for c in caixas)
        direita = any(c[0] >= b for c in caixas)
        if cobrem > teto or not (esquerda and direita):
            continue
        if achadas and achadas[-1][1] == a:
            achadas[-1] = (achadas[-1][0], b)          # a mesma calha, em dois pedaços
        else:
            achadas.append((a, b))
    return achadas


def ordem_verdadeira(regioes: list[dict[str, Any]]) -> list[str]:
    """Os ids das regiões da página na ordem em que se leem (ver o cabeçalho).

    As colunas são o que as calhas separam; a região que atravessa uma calha, ou que tem mais de
    `LARGA` da largura útil, é um separador de faixas: o que está acima dela se lê coluna a
    coluna, depois ela, depois o que está abaixo.
    """
    if not regioes:
        return []
    caixas = {r["id"]: tuple(r["caixa"]) for r in regioes}
    util = max(1e-6, max(c[2] for c in caixas.values()) - min(c[0] for c in caixas.values()))
    divisas = calhas(list(caixas.values()))

    def atravessa(caixa: Caixa) -> bool:
        return (caixa[2] - caixa[0]) >= LARGA * util or any(
            caixa[0] < (a + b) / 2 < caixa[2] for a, b in divisas)

    def coluna(caixa: Caixa) -> int:
        centro = (caixa[0] + caixa[2]) / 2
        return sum(1 for a, b in divisas if centro >= (a + b) / 2)

    largas = sorted((i for i, c in caixas.items() if atravessa(c)), key=lambda k: caixas[k][1])
    restantes = [i for i in caixas if i not in largas]
    ordem: list[str] = []
    acima = float("-inf")
    for corte, separador in [*((caixas[i][1], i) for i in largas), (float("inf"), None)]:
        faixa = [i for i in restantes if acima <= caixas[i][1] < corte]
        faixa.sort(key=lambda k: (coluna(caixas[k]), caixas[k][1], caixas[k][0]))
        ordem.extend(faixa)
        if separador is not None:
            ordem.append(separador)
        acima = corte
    return ordem


def posicoes(leitor: str, lido: dict[str, Any], regioes: list[dict[str, Any]]
             ) -> dict[str, tuple[float, float, float]]:
    """Onde cada região aparece na ordem do leitor (menor = antes); as que ele não tem, faltam.

    A aba: o índice da primeira linha dela que cai na região. O produto: a ordem do primeiro bloco
    do IR que cai na região, ou em que ela cai. O desempate (duas regiões no mesmo bloco) é a
    própria posição de cada uma na página, de cima para baixo.
    """
    saida: dict[str, tuple[float, float, float]] = {}
    for regiao in regioes:
        caixa = tuple(regiao["caixa"])
        if leitor == "fusao":
            achados = [b["ordem"] for b in lido.get("blocos", [])
                       if dentro(tuple(b["caixa"]), caixa) or dentro(caixa, tuple(b["caixa"]))]
        else:
            achados = [n for n, ln in enumerate(lido.get("linhas", []))
                       if dentro(tuple(ln["caixa"]), caixa)]
        if achados:
            saida[regiao["id"]] = (float(min(achados)), caixa[1], caixa[0])
    return saida


def precisao_de_regioes(leitor: str, lido: dict[str, Any], regioes: list[dict[str, Any]]
                        ) -> tuple[int, int]:
    """(regiões achadas, blocos do leitor que caem nelas): a razão vê região a mais."""
    blocos = lido.get("blocos", [])
    sobre = [b for b in blocos
             if any(dentro(tuple(b["caixa"]), tuple(r["caixa"])) for r in regioes)]
    achadas = len(posicoes(leitor, lido, regioes))
    return achadas, len(sobre)


# --------------------------------------------------------------------------- #
# Métricas
# --------------------------------------------------------------------------- #


def _com_figurina(tokens: list[str]) -> list[str]:
    return [t for t in tokens if any(c in FIGURINAS for c in t)]


def medir_regiao(verdade: str, hipotese: str) -> dict[str, float]:
    from caissa.ocr.metrics import move_accounting, move_tokens, score_text

    texto = hipotese if hipotese.strip() else None
    cer = score_text(verdade, texto).cer if texto is not None else 1.0
    conta = move_accounting(verdade, hipotese)
    verdade_fig = Counter(_com_figurina(move_tokens(verdade)))
    lida_fig = Counter(_com_figurina(move_tokens(hipotese)))
    return {
        "cer": round(float(cer), 6),
        "lances_verdade": conta.truth,
        "lances_certos": conta.kept,
        "lances_inventados": conta.invented,
        "figurinas_verdade": sum(verdade_fig.values()),
        "figurinas_certas": sum((verdade_fig & lida_fig).values()),
    }


def _razao(regioes: list[dict[str, float]], parte: str, todo: str) -> float | None:
    total = sum(r[todo] for r in regioes)
    return sum(r[parte] for r in regioes) / total if total else None


def agregar(regioes: list[dict[str, float]], metrica: str) -> float | None:
    """A métrica sobre um conjunto: CER e ordem, médias; as outras, razão das somas."""
    if not regioes:
        return None
    if metrica in ("cer", "ordem"):
        return sum(r[metrica] for r in regioes) / len(regioes)
    partes = {"lances": ("lances_certos", "lances_verdade"),
              "insercao": ("lances_inventados", "lances_verdade"),
              "figurinas": ("figurinas_certas", "figurinas_verdade")}
    return _razao(regioes, *partes[metrica])


def _melhor(a: dict[str, float], b: dict[str, float], metrica: str) -> dict[str, float]:
    """A leitura que o oráculo guardaria para a região (ou página), olhando só a métrica pedida."""
    if metrica == "ordem":
        return a if a["ordem"] >= b["ordem"] else b
    if metrica == "cer":
        return a if a["cer"] <= b["cer"] else b
    if metrica == "lances":
        return a if a["lances_certos"] >= b["lances_certos"] else b
    if metrica == "insercao":
        return a if a["lances_inventados"] <= b["lances_inventados"] else b
    return a if a["figurinas_certas"] >= b["figurinas_certas"] else b


class _Sorteio:
    """O LCG do `bootstrap_mean_ci` de `ocr/metrics.py`: o mesmo intervalo em toda máquina."""

    def __init__(self, semente: int) -> None:
        self.estado = semente & 0xFFFFFFFF

    def indice(self, n: int) -> int:
        self.estado = (1103515245 * self.estado + 12345) & 0x7FFFFFFF
        return self.estado % n


def reamostras(n: int) -> list[list[int]]:
    sorteio = _Sorteio(SEMENTE)
    return [[sorteio.indice(n) for _ in range(n)] for _ in range(REAMOSTRAS)] if n else []


def _percentis(valores: list[float]) -> tuple[float, float]:
    ordenados = sorted(valores)
    baixo = ordenados[max(0, int(0.025 * len(ordenados)))]
    alto = ordenados[min(len(ordenados) - 1, int(0.975 * len(ordenados)) - 1)]
    return baixo, alto


def diferenca(testada: list[dict[str, float]], referencia: list[dict[str, float]],
              metrica: str, sorteios: list[list[int]]) -> dict[str, Any] | None:
    """Δ orientada (positivo = melhor para a testada), com o intervalo pareado de 95 %."""
    ponto_t, ponto_r = agregar(testada, metrica), agregar(referencia, metrica)
    if ponto_t is None or ponto_r is None:
        return None
    sentido = SENTIDO[metrica]
    deltas = []
    for amostra in sorteios:
        t = agregar([testada[i] for i in amostra], metrica)
        r = agregar([referencia[i] for i in amostra], metrica)
        if t is not None and r is not None:
            deltas.append(sentido * (t - r))
    if not deltas:
        return None
    baixo, alto = _percentis(deltas)
    return {"delta": round(sentido * (ponto_t - ponto_r), 6),
            "ic95": [round(baixo, 6), round(alto, 6)]}


def intervalo(regioes: list[dict[str, float]], metrica: str,
              sorteios: list[list[int]]) -> list[float] | None:
    valores = [v for amostra in sorteios
               if (v := agregar([regioes[i] for i in amostra], metrica)) is not None]
    return [round(x, 6) for x in _percentis(valores)] if valores else None


def verificar_denominador(casadas: list[dict[str, Any]], *,
                          o_que: str = "regiões casadas") -> None:
    livros = {u["livro"] for u in casadas}
    estratos = {u["estrato"] for u in casadas}
    faltas = []
    if len(casadas) < MIN_REGIOES:
        faltas.append(f"{len(casadas)} {o_que} (mínimo {MIN_REGIOES})")
    if len(livros) < MIN_LIVROS:
        faltas.append(f"{len(livros)} livro(s) (mínimo {MIN_LIVROS})")
    faltas += [f"nenhuma região do estrato {e}" for e in ESTRATOS if e not in estratos]
    if faltas:
        raise VerdadeInsuficiente("verdade insuficiente: " + "; ".join(faltas))


# --------------------------------------------------------------------------- #
# A orquestração (Python 3.11)
# --------------------------------------------------------------------------- #


def unidades_do_manifesto(manifesto: Path) -> tuple[list[dict[str, Any]], str]:
    fonte = str(RAIZ / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)
    from caissa.ocr.golden import Source, items_sorted, load_manifest

    identidade = load_manifest(manifesto, include_blind=True).content_hash()
    carregado = load_manifest(manifesto)          # sem a partição cega (R1.4)
    rotulados = pdfs_rotulados()
    unidades = []
    for item in items_sorted(carregado.items):
        if item.source not in (Source.PDF_SCAN, Source.PDF_NATIVE):
            continue
        arquivo = arquivo_do_livro(item.book, rotulados)
        for regiao in item.regions:
            caixa = regiao.box or item.clip
            if caixa is None:
                continue
            unidades.append({
                "id": item.id if len(item.regions) == 1 else f"{item.id}#{regiao.reading_order}",
                "livro": item.book,
                "arquivo": str(arquivo) if arquivo else None,
                "indice": item.page_index,
                "caixa": [float(v) for v in caixa],
                "estrato": "digitalizado" if item.source is Source.PDF_SCAN else "nativo",
                "tipo": regiao.kind,
                "particao": str(item.partition),
                "verdade": regiao.truth,
            })
    return unidades, identidade


def _hash(objeto: Any) -> str:
    return hashlib.sha256(json.dumps(objeto, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()[:16]


def pontuar(unidades: list[dict[str, Any]],
            leituras: dict[tuple[str, int], dict[str, dict[str, Any]]]
            ) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """Cada região contra cada leitor: as métricas, o IoU e se ela casou."""
    regioes = []
    textos: dict[str, dict[str, str]] = {}
    for unidade in unidades:
        pagina = leituras.get((unidade["arquivo"], unidade["indice"]), {})
        registro: dict[str, Any] = {k: unidade[k] for k in ("id", "livro", "indice", "estrato",
                                                            "tipo", "particao")}
        textos[unidade["id"]] = {}
        for leitor in LEITORES:
            hipotese, sobreposicao = leitura_da_regiao(
                pagina.get(leitor, {}).get("linhas", []), tuple(unidade["caixa"]))
            registro[leitor] = {**medir_regiao(unidade["verdade"], hipotese),
                                "iou": round(sobreposicao, 4)}
            textos[unidade["id"]][leitor] = hipotese
        registro["casada"] = any(registro[r]["iou"] >= IOU_CASADA for r in LEITORES)
        registro["caixa"] = unidade["caixa"]
        regioes.append(registro)
    return regioes, textos


def ordem_das_paginas(casadas: list[dict[str, Any]],
                      leituras: dict[tuple[str, int], dict[str, dict[str, Any]]],
                      arquivos: dict[tuple[str, int], str]) -> list[dict[str, Any]]:
    """A ordem de leitura e a precisão de regiões de cada página, para cada leitor."""
    from caissa.ocr.metrics import reading_order_accuracy

    grupos: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for regiao in casadas:
        grupos.setdefault((regiao["livro"], regiao["indice"]), []).append(regiao)
    saida = []
    for (livro, indice), regioes in sorted(grupos.items()):
        verdade = ordem_verdadeira(regioes)
        pagina: dict[str, Any] = {"livro": livro, "indice": indice,
                                  "estrato": regioes[0]["estrato"], "regioes": len(regioes),
                                  "ordem_verdadeira": verdade}
        lidas = leituras.get((arquivos[(livro, indice)], indice), {})
        for leitor in LEITORES:
            lido = lidas.get(leitor, {})
            achadas = posicoes(leitor, lido, regioes)
            achada = sorted(achadas, key=lambda i: achadas[i])
            achadas_n, blocos_n = precisao_de_regioes(leitor, lido, regioes)
            pagina[leitor] = {
                "ordem": round(reading_order_accuracy(verdade, achada), 6),
                "ordem_achada": achada,
                "regioes_achadas": achadas_n,
                "blocos_sobre_as_regioes": blocos_n,
            }
        saida.append(pagina)
    return saida


def nao_se_aplica(grupo: list[dict[str, Any]], metrica: str) -> dict[str, Any] | None:
    """A ausência declarada quando a verdade do estrato não tem o denominador da métrica.

    Estruturada (ciclo 19): a métrica, o denominador — que o executor reconta no manifesto antes de
    aceitar — e o motivo por extenso.
    """
    lances = sum(r["fusao"]["lances_verdade"] for r in grupo)
    figurinas = sum(r["fusao"]["figurinas_verdade"] for r in grupo)
    if metrica == "figurinas" and figurinas == 0:
        return {"metrica": metrica, "denominador": "lances com figurina na verdade",
                "valor_do_denominador": 0, "lances_na_verdade": lances, "regioes": len(grupo),
                "motivo": f"a verdade do estrato não tem lance com figurina (0 de {lances} lances, "
                          f"{len(grupo)} regiões)"}
    if metrica in ("lances", "insercao") and lances == 0:
        return {"metrica": metrica, "denominador": "lances na verdade",
                "valor_do_denominador": 0, "regioes": len(grupo),
                "motivo": f"a verdade do estrato não tem lance (0 lances em {len(grupo)} regiões)"}
    return None


def publicar_estrato(grupo: list[dict[str, Any]], paginas: list[dict[str, Any]]
                     ) -> dict[str, Any]:
    """Os leitores, as diferenças contra a fusão e o oráculo, num estrato.

    As quatro métricas de região reamostram as regiões; a ordem de leitura, que é da página,
    reamostra as páginas com duas regiões ou mais.
    """
    sorteios = reamostras(len(grupo))
    com_ordem = [p for p in paginas if p["regioes"] >= 2]
    sorteios_de_pagina = reamostras(len(com_ordem))
    bloco: dict[str, Any] = {
        "regioes": len(grupo),
        "livros": sorted({r["livro"] for r in grupo}),
        "casadas_por_leitor": {
            leitor: sum(1 for r in grupo if r[leitor]["iou"] >= IOU_CASADA) for leitor in LEITORES},
        "paginas_com_ordem": len(com_ordem),
        "leitores": {}, "diferencas": {}, "oraculo": {}, "precisao_de_regioes": {},
        "nao_se_aplica": {m: motivo for m in METRICAS if (motivo := nao_se_aplica(grupo, m))},
    }

    def unidades(leitor: str, metrica: str) -> tuple[list[dict[str, float]], list[list[int]]]:
        if metrica == "ordem":
            return [p[leitor] for p in com_ordem], sorteios_de_pagina
        return [r[leitor] for r in grupo], sorteios

    for leitor in LEITORES:
        bloco["leitores"][leitor] = {}
        for m in METRICAS:
            valores, amostras = unidades(leitor, m)
            valor = agregar(valores, m)
            bloco["leitores"][leitor][m] = {
                "valor": None if valor is None else round(valor, 6),
                "ic95": intervalo(valores, m, amostras)}
        achadas = sum(p[leitor]["regioes_achadas"] for p in paginas)
        blocos = sum(p[leitor]["blocos_sobre_as_regioes"] for p in paginas)
        bloco["precisao_de_regioes"][leitor] = {
            "achadas": achadas, "blocos": blocos,
            "valor": round(min(1.0, achadas / blocos), 6) if blocos else None}
    for modo in MODOS:
        bloco["diferencas"][modo] = {}
        bloco["oraculo"][modo] = {}
        for m in METRICAS:
            referencia, amostras = unidades("fusao", m)
            testada, _ = unidades(modo, m)
            bloco["diferencas"][modo][m] = diferenca(testada, referencia, m, amostras)
            valor = agregar([_melhor(a, b, m) for a, b in zip(referencia, testada, strict=True)], m)
            bloco["oraculo"][modo][m] = None if valor is None else round(valor, 6)
    bloco["oraculo"]["qualquer_modo"] = {}
    for m in METRICAS:
        linhas = com_ordem if m == "ordem" else grupo
        escolhidas = []
        for r in linhas:
            escolha = r["fusao"]
            for modo in MODOS:
                escolha = _melhor(escolha, r[modo], m)
            escolhidas.append(escolha)
        valor = agregar(escolhidas, m)
        bloco["oraculo"]["qualquer_modo"][m] = None if valor is None else round(valor, 6)
    return bloco


def contexto_sem_verdade(contexto: list[tuple[str, str, int]],
                         leituras: dict[tuple[str, int], dict[str, dict[str, Any]]]
                         ) -> dict[str, Any]:
    """Nas páginas sem verdade: quanto cada modo discorda da fusão, figurinas, diagramas."""
    from caissa.ocr.metrics import score_text

    def texto_de(lido: dict[str, Any]) -> str:
        return "\n".join(ln["texto"] for ln in em_ordem(list(lido.get("linhas", []))))

    saida: dict[str, Any] = {}
    for nome in sorted({n for n, _, _ in contexto}):
        paginas = [(a, i) for n, a, i in contexto if n == nome]
        bloco: dict[str, Any] = {"paginas": len(paginas), "leitores": {}}
        for leitor in LEITORES:
            discordancia, figurinas, diagramas, com_fen = [], 0, 0, 0
            for chave in paginas:
                lido = leituras.get(chave, {}).get(leitor, {})
                texto = texto_de(lido)
                referencia = texto_de(leituras.get(chave, {}).get("fusao", {}))
                if leitor != "fusao" and referencia.strip():
                    discordancia.append(score_text(referencia, texto).cer if texto.strip() else 1.0)
                figurinas += sum(1 for c in texto if c in FIGURINAS)
                if leitor == "fusao":
                    diagramas += int(lido.get("diagramas", 0))
                    com_fen += int(lido.get("diagramas_lidos", 0))
                else:
                    diagramas += len(lido.get("diagramas", []))
                    com_fen += sum(1 for d in lido.get("diagramas", []) if d.get("lido"))
            bloco["leitores"][leitor] = {
                "discordancia_da_fusao": (round(sum(discordancia) / len(discordancia), 4)
                                          if discordancia else None),
                "figurinas": figurinas, "diagramas": diagramas, "diagramas_com_fen": com_fen}
        saida[nome] = bloco
    return saida


def por_pagina(casadas: list[dict[str, Any]], ordens: list[dict[str, Any]]
               ) -> list[dict[str, Any]]:
    """O resultado de cada página com verdade: as somas que o H0b reamostra por página."""
    ordem_de = {(p["livro"], p["indice"]): p for p in ordens}
    grupos: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for regiao in casadas:
        grupos.setdefault((regiao["livro"], regiao["indice"]), []).append(regiao)
    saida = []
    for (livro, indice), regioes in sorted(grupos.items()):
        pagina: dict[str, Any] = {"livro": livro, "indice": indice,
                                  "estrato": regioes[0]["estrato"], "regioes": len(regioes),
                                  "ids": [r["id"] for r in regioes]}
        for leitor in LEITORES:
            valores = [r[leitor] for r in regioes]
            pagina[leitor] = {
                "cer_soma": round(sum(v["cer"] for v in valores), 6),
                **{campo: sum(int(v[campo]) for v in valores)
                   for campo in ("lances_verdade", "lances_certos", "lances_inventados",
                                 "figurinas_verdade", "figurinas_certas")},
                **{campo: ordem_de[(livro, indice)][leitor][campo]
                   for campo in ("ordem", "regioes_achadas", "blocos_sobre_as_regioes")},
            }
        pagina["ordem_verdadeira"] = ordem_de[(livro, indice)]["ordem_verdadeira"]
        saida.append(pagina)
    return saida


def tempos_por_pagina(leituras: dict[tuple[str, int], dict[str, dict[str, Any]]]
                      ) -> dict[str, dict[str, float] | None]:
    tempos: dict[str, list[float]] = {r: [] for r in LEITORES}
    for pagina in leituras.values():
        for leitor, lido in pagina.items():
            if lido.get("segundos") is not None:
                tempos[leitor].append(float(lido["segundos"]))
    return {r: {"mediana": round(statistics.median(v), 3), "paginas": len(v)} if v else None
            for r, v in tempos.items()}


def carregar_unidades(args: argparse.Namespace, pasta: Path
                      ) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]]]:
    """As regiões com verdade, gravadas com o hash antes de qualquer leitura."""
    manifesto = args.manifesto or _no_checkout("benchmarks/corpus/golden/manifest.private.json")
    if not manifesto.is_file():
        raise VerdadeInsuficiente(f"verdade insuficiente: manifesto ausente ({manifesto})")
    unidades, identidade = unidades_do_manifesto(manifesto)
    sem_arquivo = sorted({u["livro"] for u in unidades if u["arquivo"] is None})
    unidades = [u for u in unidades if u["arquivo"] is not None]
    if args.sabotar == "so_uma_pagina" and unidades:
        primeira = (unidades[0]["arquivo"], unidades[0]["indice"])
        unidades = [u for u in unidades if (u["arquivo"], u["indice"]) == primeira]
    lista = [{k: u[k] for k in ("id", "livro", "indice", "caixa", "estrato")} for u in unidades]
    (pasta / "unidades.json").write_text(json.dumps(
        {"manifesto": str(manifesto), "hash_do_manifesto": identidade,
         "hash_da_lista": _hash(lista), "livros_sem_arquivo": sem_arquivo,
         "sabotagem": args.sabotar, "unidades": lista},
        ensure_ascii=False, indent=1), encoding="utf-8")
    # O teto: nenhuma leitura casa mais regiões do que as que a verdade tem.
    verificar_denominador(unidades, o_que="regiões com verdade, no máximo")
    return unidades, identidade, lista


def paginas_a_ler(unidades: list[dict[str, Any]], com_contexto: bool
                  ) -> tuple[list[dict[str, Any]], list[tuple[str, str, int]]]:
    com_verdade = sorted({(u["arquivo"], u["indice"]) for u in unidades})
    contexto: list[tuple[str, str, int]] = []
    if com_contexto:
        for nome, padrao, indices in CONTEXTO:
            arquivo = livro_por_padrao(padrao)
            if arquivo is not None:
                contexto += [(nome, str(arquivo), i) for i in indices]
    ja = set(com_verdade)
    paginas = [{"arquivo": a, "indice": i} for a, i in com_verdade]
    paginas += [{"arquivo": a, "indice": i} for _, a, i in contexto if (a, i) not in ja]
    return paginas, contexto


def metricas_planas(publicado: dict[str, Any], casadas: list[dict[str, Any]]) -> dict[str, float]:
    """Os números de `metricas.json`, de que o executor tira a mediana das três execuções."""
    metricas: dict[str, float] = {"regioes_casadas": len(casadas),
                                  "livros": len({r["livro"] for r in casadas})}
    for estrato, bloco in publicado["por_estrato"].items():
        metricas[f"regioes_{estrato}"] = bloco["regioes"]
        for leitor, valores in bloco["leitores"].items():
            for m in METRICAS:
                if m in valores and valores[m]["valor"] is not None:
                    metricas[f"{m}_{estrato}_{leitor}"] = valores[m]["valor"]
    for leitor, dados in publicado["segundos_por_pagina"].items():
        if dados:
            metricas[f"segundos_por_pagina_{leitor}"] = dados["mediana"]
    return metricas


def orquestrar(args: argparse.Namespace) -> int:
    pasta: Path = args.saida
    pasta.mkdir(parents=True, exist_ok=True)
    comeco = time.perf_counter()
    if args.so_geometria:
        geometria = medir_geometria(pasta / "geometria")
        print(f"geometria: IoU {geometria['iou']} (mínimo {IOU_DA_GEOMETRIA})")
        return 0 if geometria["passou"] else 1

    try:
        unidades, identidade, lista = carregar_unidades(args, pasta)
    except VerdadeInsuficiente as falta:
        print(f"REPROVADO: {falta}")
        return 1
    geometria = (json.loads((args.reusar / "leitores.json").read_text(encoding="utf-8"))
                 .get("geometria", {}) if args.reusar is not None
                 else medir_geometria(pasta / "geometria"))
    print(f"geometria: IoU {geometria['iou']} (mínimo {IOU_DA_GEOMETRIA})")
    if not geometria["passou"]:
        print("REPROVADO: a fixture de geometria não casa -- as caixas não estão na mesma unidade")
        (pasta / "leitores.json").write_text(json.dumps({"geometria": geometria}, indent=1),
                                             encoding="utf-8")
        return 1

    paginas, contexto = paginas_a_ler(unidades, com_contexto=not args.sem_contexto)
    print(f"{len(unidades)} regiões em {len(paginas) - len(contexto)} páginas com verdade; "
          f"{len(contexto)} páginas de contexto")
    if args.reusar is not None:
        leituras, ambiente = releitura(args.reusar)
    else:
        leituras, ambiente = ler_pelos_dois(paginas, pasta)
    regioes, textos = pontuar(unidades, leituras)
    casadas = [r for r in regioes if r["casada"]]
    arquivos = {(u["livro"], u["indice"]): u["arquivo"] for u in unidades}
    try:
        verificar_denominador(casadas)
    except VerdadeInsuficiente as falta:
        print(f"REPROVADO: {falta}")
        (pasta / "leitores.json").write_text(json.dumps(
            {"regioes": regioes, "motivo": str(falta)}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        return 1

    paginas_da_ordem = ordem_das_paginas(casadas, leituras, arquivos)
    publicado: dict[str, Any] = {
        "por_estrato": {e: publicar_estrato([r for r in casadas if r["estrato"] == e],
                                            [p for p in paginas_da_ordem if p["estrato"] == e])
                        for e in ESTRATOS},
        "segundos_por_pagina": tempos_por_pagina(leituras),
        "contexto": contexto_sem_verdade(contexto, leituras),
        "fontes_do_produto": dict(Counter(str(p["fusao"].get("fonte"))
                                          for p in leituras.values() if "fusao" in p)),
        "falhas": sorted(f"{leitor} {Path(a).name} p{i + 1}: {lido['erro']}"
                         for (a, i), pagina in leituras.items()
                         for leitor, lido in pagina.items() if lido.get("erro")),
        "hash_das_respostas": {leitor: _hash([textos[u][leitor] for u in sorted(textos)])
                               for leitor in LEITORES},
        "geometria": geometria,
        "hash_do_manifesto": identidade,
        "hash_da_lista": _hash(lista),
        "regioes": regioes,
        "paginas": por_pagina(casadas, paginas_da_ordem),
        "ambiente": ambiente,
        "reusou": str(args.reusar) if args.reusar is not None else None,
        "segundos_totais": round(time.perf_counter() - comeco, 1),
    }
    if args.sabotar == "sem_ordem":
        # A sabotagem: a ordem de um modo da aba some do JSON, e o portão tem de acusar.
        for bloco in publicado["por_estrato"].values():
            bloco["leitores"]["camada"].pop("ordem", None)
    elif args.sabotar and args.sabotar.startswith("na_falso_"):
        # A sabotagem do ciclo 19: a métrica some com um «não se aplica» falso no estrato que tem
        # o denominador, e o executor tem de recontar a verdade para acusar.
        metrica = args.sabotar.removeprefix("na_falso_")
        bloco = publicado["por_estrato"]["digitalizado"]
        for valores in bloco["leitores"].values():
            valores[metrica] = {"valor": None, "ic95": None}
        bloco["nao_se_aplica"][metrica] = {
            "metrica": metrica, "denominador": "declarado sem contar", "valor_do_denominador": 0,
            "motivo": "não se aplica (falso: a sabotagem declarou sem contar)"}
    metricas = metricas_planas(publicado, casadas)
    (pasta / "leitores.json").write_text(json.dumps(publicado, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    (pasta / "leituras.private.json").write_text(json.dumps(textos, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    (pasta / "metricas.json").write_text(json.dumps(metricas, indent=1), encoding="utf-8")
    imprimir(publicado)
    return 0


def imprimir(publicado: dict[str, Any]) -> None:
    for estrato, bloco in publicado["por_estrato"].items():
        print(f"\n{estrato}: {bloco['regioes']} regiões, {len(bloco['livros'])} livro(s)")
        for leitor, valores in bloco["leitores"].items():
            numeros = "  ".join(
                f"{m}={valores[m]['valor']:.4f}"
                if m in valores and valores[m]["valor"] is not None else f"{m}=—"
                for m in METRICAS)
            print(f"  {leitor:12s} {numeros}")
        for modo, deltas in bloco["diferencas"].items():
            partes = [
                (f"{m} Δ={deltas[m]['delta']:+.4f} "
                 f"[{deltas[m]['ic95'][0]:+.4f}, {deltas[m]['ic95'][1]:+.4f}]")
                if deltas[m] else f"{m} —"
                for m in METRICAS]
            print(f"  Δ {modo:10s} " + "  ".join(partes))
    print("\nsegundos por página:", {k: v["mediana"] if v else None
                                     for k, v in publicado["segundos_por_pagina"].items()})
    if publicado["falhas"]:
        print(f"falhas ({len(publicado['falhas'])}):", *publicado["falhas"][:10], sep="\n  ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--saida", type=Path, help="pasta desta execução (obrigatória)")
    parser.add_argument("--manifesto", type=Path, default=None)
    parser.add_argument("--sabotar", choices=SABOTAGENS, default=None)
    parser.add_argument("--sem-contexto", action="store_true",
                        help="só as páginas com verdade (o pedido e o LIVRO ficam de fora)")
    parser.add_argument("--so-geometria", action="store_true",
                        help="só a fixture de coordenadas conhecidas")
    parser.add_argument("--reusar", type=Path, default=None,
                        help="republica as leituras de uma execução anterior (a pasta dela)")
    parser.add_argument("--lado", choices=("tronco", "produto"), help=argparse.SUPPRESS)
    parser.add_argument("--pedido", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--resposta", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.lado:
        pedido = json.loads(args.pedido.read_text(encoding="utf-8"))
        resposta = lado_tronco(pedido) if args.lado == "tronco" else lado_produto(pedido)
        args.resposta.write_text(json.dumps(resposta, ensure_ascii=False), encoding="utf-8")
        return 0
    if args.saida is None:
        parser.error("--saida é obrigatória")
    args.saida = args.saida if args.saida.is_absolute() else Path.cwd() / args.saida
    return orquestrar(args)


if __name__ == "__main__":
    raise SystemExit(main())
