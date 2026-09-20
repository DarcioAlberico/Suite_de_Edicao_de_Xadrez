"""Grava no conjunto de campo as propostas do passo 0b que um humano **confirmou**.

``docs/quality/0b/propostas_0b.json`` (feito a partir de
``tools/f4_field_failures.py --barrados``) tem uma FEN proposta por diagrama casado sem
placement — leitura de um segundo leitor, não do modelo. Nada disso é verdade até alguém
conferir o recorte contra a página e trocar ``"confirmado": false`` por ``true``. Este
script só grava essas; as outras ficam como estão e são listadas.

Cada entrada é casada com o diagrama pelo par (livro, página) **e** pela bbox anotada
(tolerância 0,5 pt) — nunca pelo índice sozinho, porque o painel de campo pode ter
reordenado a página desde a extração. Diagrama que já tem placement não é sobrescrito.

Rascunho por padrão; ``--gravar`` escreve (``field_eval.save_field_set``, atômico).

Usage::

    .venv/Scripts/python.exe tools/aplicar_0b.py                # mostra o que faria
    .venv/Scripts/python.exe tools/aplicar_0b.py --gravar       # grava as confirmadas
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

PROPOSTAS = REPO_ROOT / "docs" / "quality" / "0b" / "propostas_0b.json"
"""A cópia versionada — é nela que o anotador edita; a de `benchmarks/reports` é a saída crua."""
TOLERANCIA_PT = 0.5
NOTA = "FEN do passo 0b (proposta conferida por humano)"


def _mesma_caixa(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> bool:
    return all(abs(float(x) - float(y)) <= TOLERANCIA_PT for x, y in zip(a, b, strict=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--propostas", type=Path, default=PROPOSTAS)
    parser.add_argument("--set", type=Path, default=None, dest="field_set",
                        help="O field_set.jsonl do tronco (padrão: data/field_set.jsonl).")
    parser.add_argument("--gravar", action="store_true", help="Escreve; sem isto só mostra.")
    args = parser.parse_args(argv)

    from chess_diagram_ocr.fen_utils import labels_from_fen
    from chess_diagram_ocr.field_eval import load_field_set, save_field_set

    field_set = args.field_set or cvoff_root() / "data" / "field_set.jsonl"
    entradas = json.loads(args.propostas.read_text(encoding="utf-8"))["entradas"]
    paginas = load_field_set(field_set)
    por_pagina = {(p.pdf, p.page): p for p in paginas}

    gravadas: list[str] = []
    pendentes: list[str] = []
    recusadas: list[str] = []
    for e in entradas:
        rotulo = f"[{e['n']:02d}] {e['pdf'][:40]} p{e['page']} d{e['diagram']}"
        if not e.get("confirmado"):
            pendentes.append(rotulo)
            continue
        pagina = por_pagina.get((e["pdf"], e["page"]))
        if pagina is None:
            recusadas.append(f"{rotulo}: página não está no conjunto")
            continue
        alvos = [d for d in pagina.diagrams if _mesma_caixa(d.bbox, e["annotated_bbox"])]
        if len(alvos) != 1:
            recusadas.append(f"{rotulo}: {len(alvos)} diagramas com essa bbox")
            continue
        alvo = alvos[0]
        if alvo.placement:
            recusadas.append(f"{rotulo}: já tem placement ({alvo.placement}); não sobrescrevo")
            continue
        try:
            labels_from_fen(e["proposta"])
        except (ValueError, KeyError) as exc:
            recusadas.append(f"{rotulo}: proposta inválida ({exc})")
            continue
        nota = f"{alvo.note}; {NOTA}" if alvo.note else NOTA
        novo = dataclasses.replace(alvo, placement=e["proposta"],
                                   side_to_move=str(e.get("side_to_move", "") or alvo.side_to_move),
                                   note=nota)
        diagramas = tuple(novo if d is alvo else d for d in pagina.diagrams)
        por_pagina[(e["pdf"], e["page"])] = dataclasses.replace(pagina, diagrams=diagramas)
        gravadas.append(f"{rotulo}: {e['proposta']}")

    print(f"confirmadas e aplicáveis: {len(gravadas)}   pendentes: {len(pendentes)}"
          f"   recusadas: {len(recusadas)}")
    for linha in gravadas:
        print("  +", linha)
    for linha in recusadas:
        print("  !", linha)
    if pendentes:
        print("  pendentes (confirmado=false):", ", ".join(p.split(" ")[0] for p in pendentes))

    if args.gravar and gravadas:
        save_field_set(field_set, por_pagina.values())
        print(f"gravado em {field_set}")
    elif gravadas:
        print("rascunho — nada gravado (use --gravar)")
    return 0 if not recusadas else 1


if __name__ == "__main__":
    raise SystemExit(main())
