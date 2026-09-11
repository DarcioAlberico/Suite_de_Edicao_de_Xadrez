"""Where does the production classifier's *style* coverage end?

The one remaining exported-and-wrong field diagram (``docs/quality/F4_FIELD_REPORT.md``)
is a **black queen read as a white queen at p = 0,998** in a chess-font book, and the
jitter probe shows it does not move under +-8 px of crop shift -- so it is not framing and
it is not something test-time augmentation reaches (TTA is already rejected by measurement,
``docs/ASSETS.md`` 2.14).  What is left is a style the model never saw: the production
checkpoint was trained on 3.290 real diagrams from this one collection.

Before proposing "port the synthetic generator and fine-tune", the proposal has to be
measurable, and this is the measurement that aims it.  ``Chess_diagram_to_FEN`` ships 86
piece sets and a set of board themes (``docs/ASSETS.md`` 3).  This script renders every
piece of every set on a light and on a dark square and asks the **production model** to
name it.  The output is a per-set accuracy map:

* sets the model reads at 100 % are styles it already covers -- synthetic data drawn from
  them adds nothing;
* sets it fails are the styles the generator would actually teach, and the failure modes
  it lists (which piece, mistaken for what, at what confidence) say whether the field
  failure is *in* that population or is its own thing.

It deliberately renders the pieces **clean** -- no warp, no hue shift, no noise, no text
overlay.  A model that cannot name a clean, centred, full-contrast glyph has a coverage
gap; one that can, and still fails in the book, has a degradation problem instead, and
those two want different fixes.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

TSOJ_DEFAULT = Path("C:/Python-Chess2/Chess_diagram_to_FEN")

SYMBOLS = "PNBRQKpnbrqk"
"""The twelve pieces, in the trunk's own class naming (``config.PIECE_CLASSES``)."""


@contextlib.contextmanager
def _cwd(path: Path):
    """``render_config`` resolves ``resources/pieces`` against the current directory."""
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _import_tsoj(checkout: Path) -> Any:
    if str(checkout) not in sys.path:
        sys.path.insert(0, str(checkout))
    with _cwd(checkout):
        import importlib

        return importlib.import_module("src.fen_recognition.generate_chessboards")


def _plain_board(tile: int, light: tuple[int, int, int], dark: tuple[int, int, int]) -> Any:
    from PIL import Image

    img = Image.new("RGBA", (tile * 8, tile * 8), (*light, 255))
    px = img.load()
    for row in range(8):
        for col in range(8):
            if (row + col) % 2 == 1:
                for y in range(row * tile, (row + 1) * tile):
                    for x in range(col * tile, (col + 1) * tile):
                        px[x, y] = (*dark, 255)
    return img


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tsoj", type=Path, default=TSOJ_DEFAULT)
    parser.add_argument("--tile", type=int, default=100, help="Pixels per square; 100 matches the 800 px field crop.")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--save-worst", type=int, default=8, help="Save the N worst sets as PNG boards.")
    parser.add_argument("--model", type=Path, action="append", default=[],
                        help="Checkpoint(s) to score. Default: production only.")
    parser.add_argument("--sets", default="all", choices=("all", "train", "holdout"),
                        help="Which half of caissa.vision.train.split_piece_sets to score.")
    parser.add_argument("--tag", default="")
    args = parser.parse_args(argv)

    import cv2
    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH, PIECE_CLASSES
    from chess_diagram_ocr.inference import board_probabilities, load_model

    root = cvoff_root()
    production = Path(DEFAULT_MODEL_PATH)
    if not production.is_file():
        production = root / "models" / "piece_classifier.pt"
    checkpoints = args.model or [production]

    gen = _import_tsoj(args.tsoj)
    with _cwd(args.tsoj):
        from src.render_config import get_render_config

        config = get_render_config("chess")
        piece_sets = gen._load_piece_images("chess", args.tile)
        names = [f"{s.provider}/{s.set_name}" for s in config.piece_sets]

    if args.sets != "all":
        from caissa.vision.train.synthgen import split_piece_sets

        train_sets, held_sets = split_piece_sets(names)
        wanted = set(train_sets if args.sets == "train" else held_sets)
        kept = [(name, images) for name, images in zip(names, piece_sets, strict=True) if name in wanted]
        names = [name for name, _ in kept]
        piece_sets = [images for _, images in kept]

    tile = args.tile
    # Two boards per set. Board A puts every piece on a light square, board B on a dark one,
    # so each of the twelve glyphs is scored against both backgrounds -- the field failure is
    # a piece on a dark square, and colour-on-colour is exactly what went wrong there.
    # The boards are built once and every checkpoint is scored on the same pixels: two models
    # compared on two renderings would differ by the rendering as well as by the model.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    out = args.out or REPO_ROOT / "benchmarks" / "reports" / f"style_coverage_{stamp}{tag}"
    out.mkdir(parents=True, exist_ok=True)

    boards_by_set: list[tuple[str, dict[str, tuple[Any, list[tuple[int, str]]]]]] = []
    for name, images in zip(names, piece_sets, strict=True):
        boards: dict[str, tuple[Any, list[tuple[int, str]]]] = {}
        for parity, background in ((0, "light"), (1, "dark")):
            board = _plain_board(tile, (240, 217, 181), (181, 136, 99))
            slots: list[tuple[int, str]] = []
            index = 0
            for row in range(8):
                for col in range(8):
                    if (row + col) % 2 != parity:
                        continue
                    if index >= len(SYMBOLS):
                        break
                    symbol = SYMBOLS[index]
                    glyph = images[gen._symbol_to_asset_key(symbol)]
                    board.paste(glyph, (col * tile, row * tile), glyph)
                    slots.append((row * 8 + col, symbol))
                    index += 1
            boards[background] = (board, slots)
        boards_by_set.append((name, boards))

    payloads: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        model, device = load_model(Path(checkpoint))
        results: list[dict[str, Any]] = []
        confusion: Counter[str] = Counter()
        for name, boards in boards_by_set:
            record: dict[str, Any] = {"set": name, "tested": 0, "correct": 0, "errors": []}
            for background, (board, slots) in boards.items():
                arr = np.asarray(board.convert("RGB"), dtype=np.uint8)
                probs = board_probabilities(arr, model, device)
                for square, symbol in slots:
                    row = probs[square]
                    best = int(np.argmax(row))
                    got = PIECE_CLASSES[best]
                    record["tested"] += 1
                    if got == symbol:
                        record["correct"] += 1
                    else:
                        confusion[f"{symbol}->{got}"] += 1
                        record["errors"].append({
                            "square": square, "background": background, "truth": symbol,
                            "read": got, "p": round(float(row[best]), 4),
                            "p_truth": round(float(row[PIECE_CLASSES.index(symbol)]), 4),
                        })
            record["accuracy"] = round(record["correct"] / record["tested"], 4) if record["tested"] else 0.0
            results.append(record)

        tested = sum(r["tested"] for r in results)
        correct = sum(r["correct"] for r in results)
        perfect = sum(1 for r in results if r["accuracy"] == 1.0)
        colour_flips = sum(
            count for pair, count in confusion.items()
            if pair[0].islower() and pair[-1].isupper() and pair[0] == pair[-1].lower()
        )
        payloads.append({
            "model": str(checkpoint),
            "sets_scope": args.sets,
            "piece_sets": len(results),
            "glyphs_tested": tested,
            "glyphs_correct": correct,
            "glyph_accuracy": round(correct / tested, 4) if tested else 0.0,
            "sets_at_100pct": perfect,
            "black_read_as_white": colour_flips,
            "top_confusions": confusion.most_common(20),
            "sets": sorted(results, key=lambda r: (r["accuracy"], r["set"])),
        })

    worst = sorted(payloads[0]["sets"], key=lambda r: r["accuracy"])
    saved = {r["set"] for r in worst[: args.save_worst]}
    for name, boards in boards_by_set:
        if name not in saved:
            continue
        for background, (board, _slots) in boards.items():
            cv2.imwrite(
                str(out / f"{name.replace('/', '__')}_{background}.png"),
                cv2.cvtColor(np.asarray(board.convert("RGB")), cv2.COLOR_RGB2BGR),
            )

    (out / "style_coverage.json").write_text(
        json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "tile": tile,
                    "models": payloads}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    header = f"{'model':<34}{'sets':>6}{'glyphs':>8}{'accuracy':>11}{'perfect':>9}{'b->w flips':>12}"
    print("")
    print(header)
    print("-" * len(header))
    for payload in payloads:
        print(f"{Path(payload['model']).name[:33]:<34}{payload['piece_sets']:>6}{payload['glyphs_tested']:>8}"
              f"{payload['glyph_accuracy']:>11.4f}{payload['sets_at_100pct']:>9}{payload['black_read_as_white']:>12}")

    first = payloads[0]
    print("")
    print(f"worst sets for {Path(first['model']).name}:")
    for record in sorted(first["sets"], key=lambda r: r["accuracy"])[:20]:
        wrong = ", ".join(f"{e['truth']}->{e['read']}@{e['p']:.2f}" for e in record["errors"][:6])
        print(f"  {record['set']:<28} {record['accuracy']:.3f}  {record['correct']}/{record['tested']}  {wrong}")
    print("")
    print(f"top confusions for {Path(first['model']).name}:")
    for pair, count in first["top_confusions"][:15]:
        print(f"  {pair:<12} {count}")
    print("")
    print(f"report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
