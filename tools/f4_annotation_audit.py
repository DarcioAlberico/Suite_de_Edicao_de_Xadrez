"""Audit the field set's own annotations with an **independent** reader.

The failure dump (``tools/f4_field_failures.py``) can only see the diagrams where the
production model and the annotation disagree.  That is one direction of error.  The other
direction is invisible to it and is the one that flatters the number: the field set was
seeded by ``field_eval.draft_page``, which drafts from *this model's* output, so a
confident model error that the human reviewer rubber-stamped counts today as a **correct**
read.  An audit that can only find errors in the favourable direction is not an audit.

So this script reads all 96 annotated placements with a second, unrelated model -- the
``Chess_diagram_to_FEN`` reader of ``tsoj_reader.py``, a different architecture trained on
different data (``docs/ASSETS.md`` 2.13) -- over the **same crops** the production model
saw, and lists every diagram where the second opinion disagrees with the annotation.

Reading the list correctly matters:

* second opinion == annotation, production == annotation -> nothing to see.
* production disagrees, second opinion agrees with annotation -> production model error.
* **production agrees with the annotation, second opinion disagrees** -> the candidate
  class this script exists for.  Either the second reader is wrong (common: it is a
  different model, not an oracle) or the annotation carries a model error.  Every one of
  these has to be looked at by hand; the script only shortlists.

Nothing here writes to the field set.  It prints a shortlist for a human.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

FILES = "abcdefgh"
TSOJ_DEFAULT = Path("C:/Python-Chess2/Chess_diagram_to_FEN")


def square_name(index: int) -> str:
    return f"{FILES[index % 8]}{8 - index // 8}"


def diff_squares(a: str, b: str) -> list[int] | None:
    from chess_diagram_ocr.fen_utils import labels_from_fen

    try:
        left, right = labels_from_fen(a), labels_from_fen(b)
    except (ValueError, KeyError):
        return None
    return [i for i in range(64) if left[i] != right[i]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tsoj", type=Path, default=TSOJ_DEFAULT)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--max-boards", type=int, default=12)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--crops", action="store_true", help="Save the crop of every disagreement.")
    args = parser.parse_args(argv)

    import cv2
    from chess_diagram_ocr.board_detection import NoBoardDetectedError
    from chess_diagram_ocr.config import ACCEPT_MIN_CONFIDENCE, DEFAULT_MODEL_PATH
    from chess_diagram_ocr.field_eval import _match, load_field_set
    from chess_diagram_ocr.service import OcrService, RecognitionOptions
    from chess_diagram_ocr.tsoj_reader import TsojDiagramReader

    from caissa.vision.detect.recall import recall_pack

    root = cvoff_root()
    pages = load_field_set(root / "data" / "field_set.jsonl")
    model = Path(DEFAULT_MODEL_PATH)
    if not model.is_file():
        model = root / "models" / "piece_classifier.pt"
    options = RecognitionOptions(model_path=model, max_boards=args.max_boards, dpi=args.dpi)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or REPO_ROOT / "benchmarks" / "reports" / f"f4_annotation_audit_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    service = OcrService(model_path=options.model_path)
    second = TsojDiagramReader(args.tsoj)

    rows: list[dict[str, Any]] = []
    with recall_pack():
        for page in pages:
            if not page.reviewed or not any(d.placement for d in page.diagrams):
                continue
            pdf_path = root / "PDF" / page.pdf
            try:
                read = service.recognize_page(pdf_path, page.page, options=options)
            except NoBoardDetectedError:
                read = []
            matched = _match(page.diagrams, read)
            for index, annotated in enumerate(page.diagrams):
                slot = matched.get(index)
                if slot is None or not annotated.placement:
                    continue
                got = read[slot]
                try:
                    other = second.predict(got.board_rgb)
                    error = ""
                except Exception as exc:  # noqa: BLE001 - a reader failure is a datum, not a stop
                    other, error = "", f"{type(exc).__name__}: {exc}"

                prod_ok = got.placement == annotated.placement
                second_ok = other == annotated.placement
                d_prod = diff_squares(got.placement, annotated.placement) or []
                d_second = diff_squares(other, annotated.placement) if other else None
                agree_prod_second = other and other == got.placement

                row = {
                    "pdf": page.pdf,
                    "page": page.page,
                    "diagram": index,
                    "regime": page.regime,
                    "note": annotated.note,
                    "exported": (got.is_fatal is not True) and got.min_confidence >= ACCEPT_MIN_CONFIDENCE,
                    "min_confidence": round(float(got.min_confidence), 4),
                    "production_matches_annotation": prod_ok,
                    "second_matches_annotation": second_ok,
                    "production_matches_second": bool(agree_prod_second),
                    "n_prod_vs_annot": len(d_prod),
                    "n_second_vs_annot": (len(d_second) if d_second is not None else None),
                    "second_vs_annot_squares": (
                        [f"{square_name(s)}" for s in d_second] if d_second is not None else None
                    ),
                    "annotation": annotated.placement,
                    "production": got.placement,
                    "second": other,
                    "second_error": error,
                }
                rows.append(row)
                if args.crops and not (prod_ok and second_ok):
                    name = f"{len(rows):03d}_p{page.page}_d{index}.png"
                    cv2.imwrite(str(out / name), cv2.cvtColor(got.board_rgb, cv2.COLOR_RGB2BGR))
                    row["crop"] = name

    total = len(rows)
    both_ok = sum(1 for r in rows if r["production_matches_annotation"] and r["second_matches_annotation"])
    prod_only = [r for r in rows if r["production_matches_annotation"] and not r["second_matches_annotation"]]
    second_only = [r for r in rows if not r["production_matches_annotation"] and r["second_matches_annotation"]]
    neither = [r for r in rows if not r["production_matches_annotation"] and not r["second_matches_annotation"]]
    failed = [r for r in rows if r["second_error"]]

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "second_reader": second.name,
        "totals": {
            "comparable": total,
            "both_agree_with_annotation": both_ok,
            "only_production_agrees": len(prod_only),
            "only_second_agrees": len(second_only),
            "neither_agrees": len(neither),
            "second_reader_failed": len(failed),
        },
        "rows": rows,
    }
    (out / "audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"second reader: {second.name}")
    print(f"comparable diagrams          {total}")
    print(f"  both agree with annotation {both_ok}")
    print(f"  only production agrees     {len(prod_only)}   <- shortlist for hidden annotation error")
    print(f"  only second agrees         {len(second_only)}   <- production model error")
    print(f"  neither agrees             {len(neither)}")
    print(f"  second reader failed       {len(failed)}")
    print("\nSHORTLIST (production agrees with annotation, second reader does not):")
    for r in sorted(prod_only, key=lambda x: -(x["n_second_vs_annot"] or 0)):
        count = r["n_second_vs_annot"]
        shown = "unreadable" if count is None else f"{count:>2} squares {r['second_vs_annot_squares']}"
        print(f"  {r['pdf'][:44]:<44} p{r['page']:<4} d{r['diagram']} regime={r['regime']:<16}"
              f" second differs on {shown}")
    print(f"\naudit -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
