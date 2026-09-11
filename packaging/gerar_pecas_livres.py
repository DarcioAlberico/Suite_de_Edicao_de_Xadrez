r"""Gera os 12 PNG de peça do bundle a partir de um conjunto de licença conhecida (F12, ciclo 2).

Por que este arquivo existe
---------------------------
`packaging/PECAS_PROCEDENCIA.md` mede que os 12 PNG de `assets/piece_images/` do tronco são
a mesma arte de um conjunto que o único documento de atribuição disponível descreve como
**"All rights reserved"**. Eles saem do bundle pela mesma regra dos dois léxicos.

Mas tirá-los sem repor quebraria o desenho de tabuleiro — e o auto-teste da primeira
execução, que desenha um diagrama e manda o `--selftest` do tronco lê-lo. Então o bundle
passa a levar um conjunto **com licença explícita**: `cburnett`, de Colin M.L. Burnett,
o mesmo desenho que a Wikipédia e o Lichess usam.

A licença, e por que ela fecha
------------------------------
`Chess_diagram_to_FEN/resources/COPYING.md` registra, para `pieces/chess/lichess/cburnett`:
autor **Colin M.L. Burnett**, licença **GPLv2 ou posterior**. "Ou posterior" é uma escolha
de quem redistribui, e esta frente escolhe a **GPL-3.0** — que é a licença cujo texto
integral o pacote já carrega (`licenses/GPL-3.0.txt`, vinda do PyQt6) e que combina sem
atrito com o AGPL-3.0-or-later do conjunto. Nenhum texto novo precisa entrar, e nenhuma
obrigação fica descoberta.

O que o script faz
------------------
1. Copia os 12 SVG originais para `packaging/assets/piece_images_fonte/`, com o SHA-256 de
   cada um gravado em `PROCEDENCIA.json` — para o build ser reprodutível sem depender do
   clone de terceiro estar no lugar.
2. Rasteriza cada um para 70×70 RGBA com o **PyMuPDF do próprio ambiente de empacotamento**,
   que é o mesmo que abre os livros. 70×70 é o tamanho exato dos PNG que saíram, para não
   mudar nada além da arte.

    .venv-pack\Scripts\python.exe packaging/gerar_pecas_livres.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

PACOTE = Path(__file__).resolve().parent
FONTE_PADRAO = Path(
    r"C:\Python-Chess2\Chess_diagram_to_FEN\resources\pieces\chess\lichess\cburnett"
)
DESTINO_SVG = PACOTE / "assets" / "piece_images_fonte"
DESTINO_PNG = PACOTE / "assets" / "piece_images"
LADO = 70
"""O mesmo lado dos PNG que saíram (medido: 70×70). Trocar a arte já é uma mudança; trocar
também a geometria mudaria o que o detector e o classificador veem, e aí a comparação com o
que existia deixaria de ser possível."""

DE_PARA = {
    "bB": "bb",
    "bK": "bk",
    "bN": "bn",
    "bP": "bp",
    "bQ": "bq",
    "bR": "br",
    "wB": "wb",
    "wK": "wk",
    "wN": "wn",
    "wP": "wp",
    "wQ": "wq",
    "wR": "wr",
}
"""Lichess nomeia `wK.svg`; o tronco lê `wk.png`. O mapa é explícito porque um `lower()`
esconderia o dia em que um dos dois lados mudar de convenção."""


def gerar(fonte: Path = FONTE_PADRAO) -> int:
    """Copia os SVG, rasteriza os PNG e grava a procedência. Devolve o código de saída."""
    import pymupdf

    if not fonte.is_dir():
        print(f"Conjunto de origem não encontrado em {fonte}.")
        return 2

    DESTINO_SVG.mkdir(parents=True, exist_ok=True)
    DESTINO_PNG.mkdir(parents=True, exist_ok=True)
    registro: list[dict[str, object]] = []

    for original, curto in sorted(DE_PARA.items()):
        svg = fonte / f"{original}.svg"
        if not svg.is_file():
            print(f"FALTA {svg}")
            return 1
        bruto = svg.read_bytes()
        (DESTINO_SVG / f"{original}.svg").write_bytes(bruto)

        documento = pymupdf.open(str(svg))
        pagina = documento[0]
        caixa = pagina.rect
        zoom = LADO / max(caixa.width, caixa.height)
        pixels = pagina.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
        alvo = DESTINO_PNG / f"{curto}.png"
        pixels.save(str(alvo))
        documento.close()

        registro.append(
            {
                "svg": f"{original}.svg",
                "png": f"{curto}.png",
                "sha256_do_svg": hashlib.sha256(bruto).hexdigest(),
                "sha256_do_png": hashlib.sha256(alvo.read_bytes()).hexdigest(),
                "bytes_do_png": alvo.stat().st_size,
                "largura": pixels.width,
                "altura": pixels.height,
            }
        )

    (DESTINO_SVG / "PROCEDENCIA.json").write_text(
        json.dumps(
            {
                "conjunto": "cburnett",
                "autor": "Colin M.L. Burnett",
                "licenca_declarada": "GPLv2-or-later",
                "licenca_escolhida_para_redistribuir": "GPL-3.0 (opção 'ou posterior')",
                "fonte_local": str(fonte),
                "documento_de_atribuicao": (
                    r"C:\Python-Chess2\Chess_diagram_to_FEN\resources\COPYING.md"
                    ", seção Lichess (lila)"
                ),
                "upstream": "https://github.com/lichess-org/lila",
                "gerado_em": datetime.now(UTC).date().isoformat(),
                "gerado_por": "packaging/gerar_pecas_livres.py (PyMuPDF do .venv-pack)",
                "lado_px": LADO,
                "arquivos": registro,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(registro)} peças em {DESTINO_PNG} ({LADO}x{LADO} RGBA), fontes em {DESTINO_SVG}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada."""
    analisador = argparse.ArgumentParser(description="Gera os PNG de peça do bundle (F12).")
    analisador.add_argument("--fonte", type=Path, default=FONTE_PADRAO)
    return gerar(analisador.parse_args(argv).fonte)


if __name__ == "__main__":
    raise SystemExit(main())
