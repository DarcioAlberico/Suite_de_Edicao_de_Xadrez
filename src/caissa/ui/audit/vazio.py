r"""O maior retângulo vazio de cada painel nas capturas a 4K -- o portão do passo 16 da OCR_UI.

**De onde vem o número.** O crítico do ciclo 9 da F9 abriu a janela a 3840×2160 (a tela de quem
edita material para publicação, metade do §3.2 da carta que oito ciclos não rodaram) e mediu o
que ninguém tinha medido: o painel esquerdo do Estudo com **1 569,6 kpx** de nada, porque o
tabuleiro para de crescer e a coluna de lances não ocupa a sobra. O ciclo 15 generalizou:
**5 de 6 painéis acima de 200 kpx**, pior 3 104,2 (Revisão). O item ficou aberto até aqui com o
número repetido, nunca remedido -- e é isso que este módulo fecha: um instrumento do arnês, e
não um script avulso em `benchmarks/reports/critique/`.

**O que ele mede, exatamente.** Sobre cada captura `*_3840x2160_*.png` de `capture`, o painel
esquerdo (da margem até o divisor, sem a faixa de abas nem o rodapé) vira uma máscara de blocos
de 4×4 px "sem tinta" -- bloco em que todo pixel está a ≤ 6 níveis da cor de fundo dominante do
painel --, e o maior retângulo de blocos sem tinta é achado pelo algoritmo do histograma
(exato, O(n·m), o mesmo de `c5_vazios.py`). O número publicado é a área dele em kpx; o portão é
**≤ 200 kpx em todo painel, nas três peles**. É a regra §2.4 da carta dos críticos ("nenhuma
região acima de 200 kpx com menos de 2 % de tinta"), com o limiar de tinta zerado -- que é o
lado mais exigente.

**Por que sobre a captura e não sobre a árvore de widgets.** O que a pessoa vê a 4K é a
fotografia; um `QWidget` de 2000 px que desenha um retângulo liso é vazio para o olho e cheio
para `findChildren`. O instrumento mede o olho.

    PYTHONPATH=src;..\ChessVisionOFF_Puro\src .venv\Scripts\python.exe -m caissa.ui.audit.vazio ^
        --capturas benchmarks\reports\ui\c18 --marca antes16 --saida benchmarks\reports\ui\c18
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "BLOCO",
    "TETO_KPX",
    "Painel",
    "maior_retangulo",
    "mascara_vazia",
    "medir",
    "medir_captura",
]

BLOCO = 4
"""Lado do bloco, em px. Um bloco é "sem tinta" quando nenhum pixel dele foge do fundo."""

TOLERANCIA = 6
"""Quantos níveis (0–255, no canal que mais difere) um pixel pode fugir do fundo e ainda ser
fundo. Cobre o serrilhado de borda e o ruído de compressão; não cobre um separador de 1 px, que
é tinta."""

TETO_KPX = 200.0
"""O portão: nenhum painel com um vazio maior que isto, a 4K, em pele nenhuma."""

TAMANHO_4K = "3840x2160"

ALTURA_DAS_ABAS = 55
ALTURA_DO_RODAPE = 34
MARGEM = 10
"""Onde o painel esquerdo começa e acaba na captura: abaixo da faixa de abas, acima do rodapé,
com a margem da janela fora. Os mesmos recortes de `c5_vazios.py`, para o número ser comparável
ao do ciclo 15."""


@dataclass
class Painel:
    captura: str
    pele: str
    aba: str
    largura_do_painel: int
    altura_do_painel: int
    vazio_largura: int
    vazio_altura: int
    vazio_kpx: float
    vazio_em: tuple[int, int]
    fundo: str

    def viola(self, teto_kpx: float = TETO_KPX) -> bool:
        return self.vazio_kpx > teto_kpx


CORES_DE_UM_DIVISOR = 2
"""Quantas cores distintas uma coluna de pixels pode ter e ainda ser o divisor (alça e fundo)."""


def divisor(a: np.ndarray) -> int:
    """A coluna x do divisor: a primeira, entre 45 % e 80 % da largura, quase toda de uma cor só."""
    altura, largura = a.shape[:2]
    for x in range(int(largura * 0.45), int(largura * 0.80)):
        if len(np.unique(a[80 : altura - 40, x], axis=0)) <= CORES_DE_UM_DIVISOR:
            return x
    return int(largura * 0.55)


def mascara_vazia(
    a: np.ndarray, x0: int, y0: int, x1: int, y1: int, *, tolerancia: int = TOLERANCIA
) -> tuple[np.ndarray, str]:
    """Blocos de `BLOCO`×`BLOCO` sem tinta no recorte, e a cor de fundo que definiu "tinta"."""
    recorte = a[y0:y1, x0:x1].astype(np.int16)
    cores, contagens = np.unique(recorte.reshape(-1, 3), axis=0, return_counts=True)
    fundo = cores[contagens.argmax()]
    difere = np.abs(recorte - fundo).max(axis=2) > tolerancia
    altura, largura = difere.shape
    altura -= altura % BLOCO
    largura -= largura % BLOCO
    blocos = (
        difere[:altura, :largura]
        .reshape(altura // BLOCO, BLOCO, largura // BLOCO, BLOCO)
        .max(axis=(1, 3))
    )
    r, g, b = (int(c) for c in fundo)
    return ~blocos, f"#{r:02x}{g:02x}{b:02x}"


def maior_retangulo(m: np.ndarray) -> tuple[int, int, int, int, int]:
    """`(área em blocos, x0, y0, x1, y1)` do maior retângulo só de `True`. Histograma, exato."""
    linhas, colunas = m.shape
    alturas = np.zeros(colunas, int)
    melhor = (0, 0, 0, 0, 0)
    for i in range(linhas):
        alturas = np.where(m[i], alturas + 1, 0)
        pilha: list[tuple[int, int]] = []
        for j in range(colunas + 1):
            h = int(alturas[j]) if j < colunas else 0
            inicio = j
            while pilha and pilha[-1][1] >= h:
                inicio, altura = pilha.pop()
                area = altura * (j - inicio)
                if area > melhor[0]:
                    melhor = (area, inicio, i - altura + 1, j, i + 1)
            pilha.append((inicio, h))
    return melhor


_NOME = re.compile(r"^(?P<marca>[^_]+)_(?P<pele>[^_]+)_(?P<tamanho>\d+x\d+)_(?P<aba>.+)\.png$")


def medir_captura(caminho: Path) -> Painel:
    from PIL import Image

    partes = _NOME.match(caminho.name)
    pele = partes.group("pele") if partes else "?"
    aba = partes.group("aba") if partes else caminho.stem
    a = np.asarray(Image.open(caminho).convert("RGB"))
    altura = a.shape[0]
    xd = divisor(a)
    x0, y0, x1, y1 = MARGEM, ALTURA_DAS_ABAS, xd - 6, altura - ALTURA_DO_RODAPE
    mascara, fundo = mascara_vazia(a, x0, y0, x1, y1)
    _area, bx0, by0, bx1, by1 = maior_retangulo(mascara)
    vazio_largura, vazio_altura = (bx1 - bx0) * BLOCO, (by1 - by0) * BLOCO
    return Painel(
        captura=caminho.name,
        pele=pele,
        aba=aba,
        largura_do_painel=x1 - x0,
        altura_do_painel=y1 - y0,
        vazio_largura=vazio_largura,
        vazio_altura=vazio_altura,
        vazio_kpx=round(vazio_largura * vazio_altura / 1000.0, 1),
        vazio_em=(x0 + bx0 * BLOCO, y0 + by0 * BLOCO),
        fundo=fundo,
    )


def medir(capturas: Path, *, marca: str, teto_kpx: float = TETO_KPX) -> dict[str, Any]:
    arquivos = sorted(capturas.glob(f"{marca}_*_{TAMANHO_4K}_*.png"))
    if not arquivos:
        raise SystemExit(
            f"nenhuma captura {marca}_*_{TAMANHO_4K}_*.png em {capturas}: rode capture antes"
        )
    paineis = [medir_captura(caminho) for caminho in arquivos]
    violam = [p for p in paineis if p.viola(teto_kpx)]
    por_pele: dict[str, dict[str, Any]] = {}
    for p in paineis:
        entrada = por_pele.setdefault(
            p.pele, {"paineis": 0, "acima": 0, "pior_kpx": 0.0, "pior_aba": ""}
        )
        entrada["paineis"] += 1
        if p.viola(teto_kpx):
            entrada["acima"] += 1
        if p.vazio_kpx > entrada["pior_kpx"]:
            entrada["pior_kpx"], entrada["pior_aba"] = p.vazio_kpx, p.aba
    return {
        "portao": (
            f"OCR_UI passo 16 -- maior vazio de painel a 4K <= {teto_kpx:.0f} kpx em todo painel, "
            "nas tres peles"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "metodo": {
            "capturas": str(capturas),
            "marca": marca,
            "bloco_px": BLOCO,
            "tolerancia": TOLERANCIA,
            "painel": (
                "esquerdo: da margem ao divisor, abaixo das abas, acima do rodape (c5_vazios.py)"
            ),
            "algoritmo": (
                "maior retangulo em histograma sobre a mascara de blocos sem tinta (exato)"
            ),
        },
        "paineis": [asdict(p) for p in paineis],
        "por_pele": por_pele,
        "violam_o_portao": [f"{p.pele}/{p.aba}: {p.vazio_kpx} kpx" for p in violam],
        "veredito": "REPROVOU" if violam else "PASSOU",
    }


def tabela(relatorio: dict[str, Any]) -> str:
    linhas = [relatorio["portao"], ""]
    linhas.append(
        f"  {'pele':<8}{'aba':<20}{'painel':>12}{'maior vazio':>14}{'kpx':>9}  veredito"
    )
    for p in relatorio["paineis"]:
        marca = "!!" if p["vazio_kpx"] > TETO_KPX else "ok"
        painel = f"{p['largura_do_painel']}x{p['altura_do_painel']}"
        linhas.append(
            f"{marca} {p['pele']:<8}{p['aba']:<20}{painel:>12}"
            f"{p['vazio_largura']}x{p['vazio_altura']:>6}{p['vazio_kpx']:>9.1f}  "
            f"{'ACIMA' if p['vazio_kpx'] > TETO_KPX else 'dentro'}"
        )
    linhas.append("")
    for pele, resumo in relatorio["por_pele"].items():
        linhas.append(
            f"  {pele:<8} {resumo['acima']} de {resumo['paineis']} acima de {TETO_KPX:.0f} kpx; "
            f"pior {resumo['pior_kpx']} ({resumo['pior_aba']})"
        )
    linhas.append(f"\n  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maior vazio de painel a 4K (OCR_UI passo 16).")
    parser.add_argument(
        "--capturas", type=Path, required=True, help="pasta com as capturas de `capture`"
    )
    parser.add_argument(
        "--marca", default="antes", help="prefixo das capturas: antes | depois | ..."
    )
    parser.add_argument("--saida", type=Path, required=True, help="onde gravar o relatorio")
    parser.add_argument("--teto-kpx", type=float, default=TETO_KPX)
    args = parser.parse_args(argv)

    relatorio = medir(args.capturas, marca=args.marca, teto_kpx=args.teto_kpx)
    args.saida.mkdir(parents=True, exist_ok=True)
    alvo = args.saida / f"vazio_{args.marca}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    sys.exit(main())
