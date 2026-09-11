"""Fine-tune the production square classifier on real + synthetic squares, and measure it.

The measurement that aims this is ``benchmarks/style_coverage.py``: the production
checkpoint names only **75,48 %** of the 2.064 clean glyphs of the 86 piece sets that
``Chess_diagram_to_FEN`` ships, and its single most common mistake is ``q -> Q``, a black
queen read as a white one, 48 times.  That is, square for square, the one remaining
exported-and-wrong diagram of the field set.  ``docs/ASSETS.md`` 3 lists the synthetic
generator as a real gap for exactly this reason.

What this harness is careful about
----------------------------------
**It never trains on the field set.**  Real squares come from the trunk's ``train`` split of
``splits.csv``, which is hash-stable and leak-free by construction; the field set is the
measurement and is not readable from here.

**Styles are held out, not images.**  ``synthgen.split_piece_sets`` reserves a third of the
86 piece sets.  Training on a rendering of ``lichess/alpha`` and testing on another
rendering of ``lichess/alpha`` measures memorisation, not coverage.

**It starts from production, not from scratch.**  The incumbent is 0,999854 per square and
0,9906 per lab board.  A fresh model would have to re-earn that; a fine-tune has to only not
lose it, and the gate below is exactly that: if the lab test split regresses, the run says so
and the checkpoint is not adopted.

**It writes its checkpoint into this project, never into the trunk.**  ``models/`` here; the
trunk's ``models/piece_classifier.pt`` is left alone.
"""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path
from caissa.vision.train.synthgen import (
    SynthConfig,
    available_piece_sets,
    render_board,
    split_piece_sets,
)

ensure_cvoff_on_path()

__all__ = ["FineTuneConfig", "build_synthetic_cells", "finetune", "real_train_cells"]


@dataclass(frozen=True)
class FineTuneConfig:
    """Every knob, so the run can be reproduced from the report alone."""

    synth_boards: int = 2500
    synth_seed: int = 20260910
    holdout: float = 0.34

    epochs: int = 4
    batch_size: int = 512
    lr: float = 3e-4
    """Low: this is a fine-tune of a checkpoint that already meets its lab targets."""

    weight_decay: float = 1e-4
    real_repeat: int = 3
    """How many times the real train squares are seen per epoch relative to synthetic.

    The product reads printed book diagrams; the synthetic catalogue is mostly screen piece
    sets.  Letting the synthetic squares outnumber the real ones by 20x would move the model
    to a distribution the product never sees.  Repeating the real squares is the cheapest
    honest way to keep them the majority of the gradient."""

    hue_prob: float = 0.5
    """Per-board hue shift in the synthetic renderer.

    Set to 0 for a *print-like* run.  The classifier reads a grayscale square, so a hue
    shift can only change the luminance the glyph ends up with -- and a book diagram is
    black ink on white paper, never a purple knight on a green board.  Whether that helps
    or hurts is a measurement, not an opinion, which is why it is a knob."""

    themes: bool = True
    """Disk board themes (wood, marble, textured).  Off leaves the procedural gray/uniform
    backgrounds, which are closer to a scanned page."""

    seed: int = 7
    device: str = "cuda"


def _cell_bytes(board_rgb: np.ndarray, size: int = 64) -> np.ndarray:
    """The 64 squares of one board, as the model's own input, uint8 ``(64, size, size)``.

    Uses the trunk's ``preprocess_cell_to_tensor`` semantics -- RGB to gray, ``INTER_AREA``
    to ``image_size`` -- but stops one step short of the division by 255, so a whole dataset
    fits in memory as bytes.  Multiplying back at batch time is exact.
    """
    import cv2

    step = board_rgb.shape[0] // 8
    gray = cv2.cvtColor(board_rgb, cv2.COLOR_RGB2GRAY)
    cells = np.empty((64, size, size), dtype=np.uint8)
    for square in range(64):
        row, col = divmod(square, 8)
        patch = gray[row * step : (row + 1) * step, col * step : (col + 1) * step]
        cells[square] = cv2.resize(patch, (size, size), interpolation=cv2.INTER_AREA)
    return cells


def _labels(placement: str) -> np.ndarray:
    from chess_diagram_ocr.fen_utils import labels_from_fen

    return np.asarray(labels_from_fen(placement), dtype=np.int64)


def build_synthetic_cells(
    piece_sets: Sequence[str],
    boards: int,
    *,
    seed: int,
    size: int = 64,
    hue_prob: float = 0.5,
    themes: bool = True,
    progress: Any = None,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Render ``boards`` synthetic boards and return ``(cells, labels, set_names)``.

    ``cells`` is ``(boards * 64, size, size)`` uint8 -- 4 KiB per square, so 2.500 boards is
    655 MiB in RAM and **nothing on disk**.  The machine has 31,5 GB free and the project
    rule is to check before generating anything; not writing is the cheapest way to comply.
    """
    config = SynthConfig(piece_sets=tuple(piece_sets), seed=seed, hue_prob=hue_prob, themes=themes)
    cells = np.empty((boards * 64, size, size), dtype=np.uint8)
    labels = np.empty(boards * 64, dtype=np.int64)
    names: list[str] = []
    for index in range(boards):
        board, placement, set_name = render_board(config, index)
        cells[index * 64 : (index + 1) * 64] = _cell_bytes(board, size)
        labels[index * 64 : (index + 1) * 64] = _labels(placement)
        names.append(set_name)
        if progress is not None and index % 100 == 0:
            progress(index, boards)
    return cells, labels, names


def real_train_cells(size: int = 64, progress: Any = None) -> tuple[np.ndarray, np.ndarray]:
    """The trunk's ``train`` split, as the same uint8 cell array.

    Split membership comes from ``splits.csv``, which is hash-stable: this cannot reach the
    ``test`` boards of ``docs/BASELINE.md`` and cannot reach the field set at all.
    """
    import cv2
    from chess_diagram_ocr.labels import LabelStore
    from chess_diagram_ocr.splits import load_splits

    root = cvoff_root()
    splits = load_splits(root / "data" / "splits.csv")
    rows = [row for row in LabelStore(root / "data" / "labels.csv").read() if splits.get(row.filename) == "train"]

    cells = np.empty((len(rows) * 64, size, size), dtype=np.uint8)
    labels = np.empty(len(rows) * 64, dtype=np.int64)
    kept = 0
    for index, row in enumerate(rows):
        path = root / "data" / "samples" / row.filename
        image = cv2.imread(str(path))
        if image is None:
            continue
        board = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if board.shape[:2] != (800, 800):
            board = cv2.resize(board, (800, 800))
        try:
            these = _labels(row.fen.split()[0])
        except (ValueError, KeyError):
            continue
        cells[kept * 64 : (kept + 1) * 64] = _cell_bytes(board, size)
        labels[kept * 64 : (kept + 1) * 64] = these
        kept += 1
        if progress is not None and index % 200 == 0:
            progress(index, len(rows))
    return cells[: kept * 64], labels[: kept * 64]


def finetune(
    config: FineTuneConfig,
    out_path: Path,
    *,
    log: Any = print,
) -> dict[str, Any]:
    """Fine-tune and write the checkpoint. Returns the run record (no adoption decision).

    Adoption is not made here on purpose: this function produces a candidate, and
    ``benchmarks/field_exact.py`` plus the lab evaluation decide whether it may ship.  A
    trainer that also grades itself is how a regression gets adopted.
    """
    import torch
    from chess_diagram_ocr.checkpoint import load_checkpoint, save_checkpoint
    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH, PIECE_CLASSES
    from chess_diagram_ocr.model import DEFAULT_ARCH, ArchConfig, build_model
    from torch import nn

    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    random.seed(config.seed)

    base = Path(DEFAULT_MODEL_PATH)
    if not base.is_file():
        base = cvoff_root() / "models" / "piece_classifier.pt"
    checkpoint = load_checkpoint(base, map_location="cpu")
    arch = ArchConfig.from_version(checkpoint.arch_version) if checkpoint.arch_version else DEFAULT_ARCH
    if arch.channels != "gray" or arch.coords:
        raise SystemExit(f"este harness cobre a arquitetura de producao (gray, sem coords); recebido {arch.version}")

    names = available_piece_sets()
    train_sets, held_sets = split_piece_sets(names, holdout=config.holdout)
    log(f"piece sets: {len(train_sets)} para treino, {len(held_sets)} reservados")

    started = time.perf_counter()
    log(f"renderizando {config.synth_boards} tabuleiros sinteticos...")
    synth_cells, synth_labels, used = build_synthetic_cells(
        train_sets, config.synth_boards, seed=config.synth_seed,
        size=arch.image_size, hue_prob=config.hue_prob, themes=config.themes,
        progress=lambda i, n: log(f"  {i}/{n}") if i % 500 == 0 else None,
    )
    log(f"  {len(synth_cells)} casas sinteticas em {time.perf_counter() - started:.0f} s")

    log("carregando o split `train` real do tronco...")
    real_cells, real_labels = real_train_cells(
        size=arch.image_size, progress=lambda i, n: log(f"  {i}/{n}") if i % 1000 == 0 else None
    )
    log(f"  {len(real_cells)} casas reais")

    device = config.device if torch.cuda.is_available() else "cpu"
    model = build_model(arch, pretrained=False)
    model.load_state_dict(checkpoint.state, strict=True)
    model.to(device)

    optimiser = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    criterion = nn.CrossEntropyLoss()

    real_x = torch.from_numpy(real_cells)
    real_y = torch.from_numpy(real_labels)
    synth_x = torch.from_numpy(synth_cells)
    synth_y = torch.from_numpy(synth_labels)

    order_source: list[tuple[int, int]] = []
    for _ in range(config.real_repeat):
        order_source += [(0, i) for i in range(len(real_x))]
    order_source += [(1, i) for i in range(len(synth_x))]
    log(f"por epoca: {config.real_repeat}x{len(real_x)} reais + {len(synth_x)} sinteticas = {len(order_source)} casas")

    history: list[dict[str, Any]] = []
    for epoch in range(config.epochs):
        model.train()
        random.shuffle(order_source)
        total = 0.0
        seen = 0
        correct = 0
        epoch_started = time.perf_counter()
        for start in range(0, len(order_source), config.batch_size):
            chunk = order_source[start : start + config.batch_size]
            real_idx = torch.tensor([i for src, i in chunk if src == 0], dtype=torch.long)
            synth_idx = torch.tensor([i for src, i in chunk if src == 1], dtype=torch.long)
            parts_x, parts_y = [], []
            if len(real_idx):
                parts_x.append(real_x[real_idx])
                parts_y.append(real_y[real_idx])
            if len(synth_idx):
                parts_x.append(synth_x[synth_idx])
                parts_y.append(synth_y[synth_idx])
            batch_x = torch.cat(parts_x).to(device, non_blocking=True).float().div_(255.0).unsqueeze(1)
            batch_y = torch.cat(parts_y).to(device, non_blocking=True)

            optimiser.zero_grad(set_to_none=True)
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimiser.step()

            total += float(loss.item()) * len(batch_y)
            seen += len(batch_y)
            correct += int((logits.argmax(1) == batch_y).sum().item())
        record = {
            "epoch": epoch + 1,
            "loss": round(total / seen, 6),
            "train_accuracy": round(correct / seen, 6),
            "seconds": round(time.perf_counter() - epoch_started, 1),
        }
        history.append(record)
        log(f"epoca {record['epoch']}: loss {record['loss']:.5f}  acc {record['train_accuracy']:.5f}"
            f"  {record['seconds']:.0f} s")

    model.eval()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(checkpoint.metadata)
    metadata.update({
        "arch_version": arch.version,
        "class_names": list(PIECE_CLASSES),
        "finetuned_from": str(base),
        "finetune_config": asdict(config) | {"tsoj_root": None},
        "finetune_train_piece_sets": list(train_sets),
        "finetune_holdout_piece_sets": list(held_sets),
        "finetune_history": history,
        "finetune_at": datetime.now().isoformat(timespec="seconds"),
        "note": (
            "Fine-tune F4: split `train` real do tronco + tabuleiros sinteticos dos conjuntos "
            "de pecas de treino. O conjunto de campo NAO foi usado."
        ),
    })
    save_checkpoint(out_path, {k: v.cpu() for k, v in model.state_dict().items()},
                    metadata=metadata, temperature=1.0)
    log(f"checkpoint -> {out_path}")

    return {
        "checkpoint": str(out_path),
        "base": str(base),
        "arch": arch.version,
        "device": device,
        "config": asdict(config) | {"tsoj_root": None},
        "train_piece_sets": list(train_sets),
        "holdout_piece_sets": list(held_sets),
        "synthetic_cells": int(len(synth_cells)),
        "real_cells": int(len(real_cells)),
        "distinct_sets_rendered": sorted(set(used)),
        "history": history,
        "wall_s": round(time.perf_counter() - started, 1),
    }
