"""C4 (ciclo 2 OCR/UI): a ablação do aumento dirigido — ``aug0`` × ``mhsp`` × ``mhspe`` × ``e``.

``docs/OCR_UI_ANALISE_C2.md`` §3.4 exige a ablação antes de qualquer troca do checkpoint de
produção: sem ela o ganho do ``RandomStroke`` (letra ``e``) não se isola do ``mhsp`` que a
S-40 já mediu. Este script treina cada variante **do zero**, com a mesma semente, o mesmo
split persistido (sem atribuir splits novos — ``assign_splits=False``, para a partição ser a
mesma de ponta a ponta) e o mesmo orçamento de épocas, e grava por variante o histórico de
épocas e os metadados do checkpoint em ``benchmarks/reports/c4_ablation/``.

Não decide nada: quem decide é ``lab_gate.py --candidate … --runs 3 --unconstrained`` (o
laboratório), ``field_exact.py --model …`` (o campo) e ``f4_field_failures.py`` (as casas de
cor), e a decisão de trocar o ``.pt`` de produção é da pessoa (análise §10.2).

Usage::

    .venv/Scripts/python.exe benchmarks/c4_ablation.py --seeds 42 --epochs 16
    .venv/Scripts/python.exe benchmarks/c4_ablation.py --seeds 43,44 --variants mhsp,mhspe
    .venv/Scripts/python.exe benchmarks/c4_ablation.py --seeds 42 --variants i50   # a sabotagem
    .venv/Scripts/python.exe benchmarks/c4_ablation.py --seeds 42 --variants x10,w3  # C16 (fase 4)

Roda na venv da suíte (torch com CUDA) sobre o código do tronco; o checkpoint gravado
carrega na venv do tronco (CPU) — ``lab_gate`` e ``field_exact`` conferem isso ao medir.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

VARIANTS = ("aug0", "mhsp", "mhspe", "e")
OUT_DIR = REPO_ROOT / "benchmarks" / "reports" / "c4_ablation"

#: A sabotagem forte: inversão de contraste **sem** troca de rótulo em metade dos lotes.
#: A letra ``i`` inverte em 3 % (``augment.from_letters``), e a 3 % a sabotagem foi inerte
#: — indistinguível do ``aug0`` no laboratório e no campo (relatório da fase 3, §C4).
SABOTAGE_VARIANTS = {"i50": 0.5}

#: C16 (fase 4): a sabotagem **de rótulo** — ``x10`` troca a cor (``X↔x``) de 10 % das casas
#: ocupadas dos tabuleiros de treino (``OptimPlan.label_noise``); as de contraste foram
#: inertes porque inverter sem trocar o rótulo não confunde a cor. Um instrumento que não a
#: acusa não tem resolução para a pergunta do C4, e o relatório o diz.
LABEL_NOISE_VARIANTS = {"x10": 0.10, "x25": 0.25}

#: C16: o peso da correção humana — ``w3`` repete três vezes por época os tabuleiros de rota
#: humana (``dataset.ROTAS_HUMANAS``, ``OptimPlan.corrected_repeat``), sobre o ``aug0``.
CORRECTED_REPEAT_VARIANTS = {"w3": 3, "w5": 5}

logger = logging.getLogger("c4_ablation")


def _augment(letters: str):
    from chess_diagram_ocr.cli.train import _augment_from_letters

    if letters in SABOTAGE_VARIANTS:
        from chess_diagram_ocr.augment import AugmentConfig

        return AugmentConfig(invert=SABOTAGE_VARIANTS[letters])
    if letters in LABEL_NOISE_VARIANTS or letters in CORRECTED_REPEAT_VARIANTS:
        return _augment_from_letters("aug0")
    return _augment_from_letters(letters)


def _training_knobs(variant: str) -> dict[str, Any]:
    """Os botões do C16 que a variante liga além do aumento (vazio para as outras)."""
    knobs: dict[str, Any] = {}
    if variant in LABEL_NOISE_VARIANTS:
        knobs["label_noise"] = LABEL_NOISE_VARIANTS[variant]
    if variant in CORRECTED_REPEAT_VARIANTS:
        knobs["corrected_repeat"] = CORRECTED_REPEAT_VARIANTS[variant]
    return knobs


def train_variant(variant: str, seed: int, epochs: int, workers: int) -> dict[str, Any]:
    from chess_diagram_ocr.checkpoint import load_checkpoint
    from chess_diagram_ocr.training import train_model

    root = cvoff_root()
    model_path = root / "models" / "experiments" / f"c4_{variant}_s{seed}.pt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    augment = _augment(variant)
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []

    def observe(row: dict[str, Any]) -> None:
        plain = {k: v for k, v in row.items() if k != "val_per_class_recall"}
        rows.append(plain)
        logger.info("%s s%d %s", variant, seed, json.dumps(plain, ensure_ascii=False))

    run = train_model(
        csv_path=root / "data" / "labels.csv",
        samples_dir=root / "data" / "samples",
        model_path=model_path,
        epochs=epochs,
        batch_size=128,
        fresh=True,
        splits_path=root / "data" / "splits.csv",
        assign_splits=False,
        seed=seed,
        num_workers=workers,
        calibrate=True,
        augment=augment,
        progress_cb=observe,
        **_training_knobs(variant),
    )
    checkpoint = load_checkpoint(model_path, map_location="cpu")
    metadata = dict(checkpoint.metadata) if isinstance(checkpoint.metadata, dict) else {}
    result = {
        "variant": variant,
        "augment_version": augment.version,
        "training_knobs": _training_knobs(variant),
        "seed": seed,
        "epochs_requested": epochs,
        "epochs_run": len(run.history),
        "best_epoch": run.best_epoch,
        "best_metric_name": run.best_metric_name,
        "best_metric": run.best_metric,
        "temperature": run.temperature,
        "ece_before": run.ece_before,
        "ece_after": run.ece_after,
        "wall_s": round(time.perf_counter() - started, 1),
        "model": str(model_path),
        "checkpoint_metadata": {k: v for k, v in metadata.items() if k not in ("metrics",)},
        "history": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    destination = OUT_DIR / f"c4_{variant}_s{seed}.json"
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info("gravado %s (%.1f min)", destination, result["wall_s"] / 60)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default="42", help="Sementes separadas por vírgula.")
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args(argv)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if args.log:
        handlers.append(logging.FileHandler(args.log, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    logger.info("ablação C4: variantes %s, sementes %s, %d épocas, %d workers (%s)",
                variants, seeds, args.epochs, args.workers, datetime.now().isoformat(timespec="seconds"))
    for seed in seeds:
        for variant in variants:
            destination = OUT_DIR / f"c4_{variant}_s{seed}.json"
            if destination.exists():
                logger.info("já existe: %s — pulado", destination)
                continue
            train_variant(variant, seed, args.epochs, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
