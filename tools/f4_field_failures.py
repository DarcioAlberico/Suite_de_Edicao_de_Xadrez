"""Failure dump for the last recognition metric below target: ``field_exact``.

``docs/ROADMAP.md`` puts field-perfect diagrams at 97,87 % against a target of 98,0 %,
and records that the number **did not move in any detection variant** -- it is a
classification limit, not a detection one.  Before any fix is proposed, this script
answers the only question that can aim one: *which* boards are read wrong, and why.

What it produces, under ``benchmarks/reports/f4_field_failures_<stamp>/``:

* ``failures.json`` -- one record per annotated diagram that was matched by the
  detector and whose predicted placement differs from the annotation, carrying the
  predicted FEN, the annotated FEN, the differing squares with the annotated piece,
  the predicted piece, that square's confidence and the model's top-3 classes for it,
  plus ``min_confidence``, legality, whether the gate exported it, whether constrained
  decoding had to repair anything, the detection source and the IoU of the match.
* ``<n>_<book>_p<page>.png`` -- the warped crop the classifier actually saw, so the
  root cause can be **looked at** instead of guessed.
* ``<n>_..._page.png`` -- optionally the whole rendered page with the annotated bbox
  and the detected bbox drawn on it, which is what distinguishes "framed badly" from
  "read badly".
* ``summary.json`` -- the field report counters, per regime and per book.

Measurement rules of ``docs/quality/CORPUS.md`` 5 apply: this runs the trunk's own
``field_eval`` matching rule (IoU >= 0,5 on PDF points, greedy), never trains on the
field set, and names the stratum.

``--barrados`` (OCR_UI_ROADMAP passo 9, tarefa 1) adds the *other* population: every
matched diagram the export gate **barred** -- illegal, repaired (a repair caps
``min_confidence`` at 0,5 by construction, ``decode.py``) or a weak square without
repair -- and every matched diagram whose annotation has **no placement** (18 of the 19 of
``OCR_UI_REPORT_C1.md`` §4.1 are matched; the human work of passo 0b).  Each gets its crop, the
read FEN, the reason it was barred and, when the annotation allows, whether it was
right.  ``barrados.json`` / ``barrados.md`` are the table the roadmap asks for;
``ficha_0b.md`` lists what the annotator still has to write.

Usage::

    .venv/Scripts/python.exe tools/f4_field_failures.py --variant recall-pack
    .venv/Scripts/python.exe tools/f4_field_failures.py --barrados --out benchmarks/reports/f4_barrados
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

FILES = "abcdefgh"


def square_name(index: int) -> str:
    """Index 0 is a8 in FEN reading order (rank 8 first, file a first)."""
    rank = 8 - index // 8
    return f"{FILES[index % 8]}{rank}"


def _slug(text: str, limit: int = 34) -> str:
    keep = [ch if ch.isalnum() else "_" for ch in text]
    out = "".join(keep).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out[:limit]


def _diff_squares(predicted: str, annotated: str) -> list[int] | None:
    """Square indices where the two placements disagree, or ``None`` if unparseable."""
    from chess_diagram_ocr.fen_utils import labels_from_fen

    try:
        a = labels_from_fen(predicted)
        b = labels_from_fen(annotated)
    except (ValueError, KeyError):
        return None
    return [i for i in range(64) if a[i] != b[i]]


def _piece_at(placement: str, index: int) -> str:
    from chess_diagram_ocr.config import PIECE_CLASSES
    from chess_diagram_ocr.fen_utils import labels_from_fen

    return PIECE_CLASSES[labels_from_fen(placement)[index]]


def _top3(probs: Any, index: int) -> list[dict[str, Any]]:
    from chess_diagram_ocr.config import PIECE_CLASSES

    if probs is None:
        return []
    row = np.asarray(probs)[index]
    order = np.argsort(row)[::-1][:3]
    return [{"class": PIECE_CLASSES[int(k)], "p": round(float(row[int(k)]), 4)} for k in order]


def _weakest(got: Any, limit: int = 3) -> list[dict[str, Any]]:
    """The ``limit`` least confident squares of a read board, with the model's top-3."""
    confs = [float(v) for v in (got.square_confidences or [])]
    order = sorted(range(len(confs)), key=lambda i: confs[i])[:limit]
    return [{"square": square_name(i), "index": i, "confidence": round(confs[i], 4),
             "repaired": i in (got.changed_squares or []), "top3": _top3(got.probs, i)}
            for i in order]


def _block_reason(got: Any, legal: bool, above: bool) -> str:
    """Why the export gate barred a board -- the three causes the roadmap names."""
    if not legal:
        return "ilegal"
    if not above and got.changed_squares:
        return "reparo"
    if not above:
        return "casa fraca"
    return "exportado"


def _verdict(read: str, truth: str) -> str:
    if not truth:
        return "sem FEN"
    return "certo" if read == truth else "errado"


def _write_barrados(out: Path, barred: list[dict[str, Any]]) -> None:
    """``barrados.md`` (the table) and ``ficha_0b.md`` (what the annotator owes)."""
    lines = ["# Diagramas casados e barrados pelo portão de exportação", "",
             "| n | livro | p. | motivo | veredito | min_conf | reparos | casas erradas "
             "| recorte |", "|---|---|---|---|---|---|---|---|---|"]
    for b in barred:
        wrong = b["n_wrong_squares"] if b["n_wrong_squares"] is not None else "—"
        lines.append(
            f"| {b['n']} | {b['pdf'][:40]} | {b['page']} | {b['reason']} | {b['verdict']} | "
            f"{b['min_confidence']:.3f} | {', '.join(b['repaired_squares']) or '—'} | "
            f"{wrong} | `{b['crop']}` |")
    by_reason: dict[str, dict[str, int]] = {}
    for b in barred:
        counts = by_reason.setdefault(b["reason"], {})
        counts[b["verdict"]] = counts.get(b["verdict"], 0) + 1
    lines += ["", "## Por motivo × veredito", "", "| motivo | certo | errado | sem FEN |",
              "|---|---|---|---|"]
    for reason, counts in sorted(by_reason.items()):
        lines.append(f"| {reason} | {counts.get('certo', 0)} | {counts.get('errado', 0)} | "
                     f"{counts.get('sem FEN', 0)} |")
    (out / "barrados.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    owed = [b for b in barred if b["verdict"] == "sem FEN"]
    ficha = ["# Ficha do passo 0b — diagramas casados sem FEN anotada", "",
             "A leitura do modelo está ao lado **só para orientar**: a verdade é o que a página "
             "mostra, conferida no recorte, e entra pelo painel de campo do tronco "
             "(`Anotar página`).", ""]
    for b in owed:
        weak = "; ".join(
            f"{w['square']} {w['confidence']:.2f} " + "/".join(t["class"] for t in w["top3"])
            for w in b["weakest"])
        repaired = ", ".join(b["repaired_squares"]) or "nenhum"
        ficha += [f"## {b['n']:02d} — {b['pdf']} p. {b['page']} "
                  f"(diagrama {b['diagram']}, {b['regime']})", "",
                  f"- recorte: `{b['crop']}`  bbox anotada: {b['annotated_bbox']}",
                  f"- leitura do modelo: `{b['read_placement']}` "
                  f"(min_conf {b['min_confidence']:.3f}, motivo: {b['reason']}, reparos: {repaired})",
                  f"- casas mais fracas: {weak}",
                  f"- nota da anotação: {b['note'] or '—'}", ""]
    (out / "ficha_0b.md").write_text("\n".join(ficha) + "\n", encoding="utf-8")


def _variant(name: str) -> Any:
    import contextlib

    from caissa.vision.detect.recall import recall_pack

    if name == "baseline":
        return contextlib.nullcontext()
    if name == "recall-pack":
        return recall_pack()
    raise SystemExit(f"variante desconhecida: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", default="recall-pack", choices=("baseline", "recall-pack"))
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--max-boards", type=int, default=12)
    parser.add_argument("--refine", action="store_true", help="RecognitionOptions.refine_detected_boards")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--pages", action="store_true", help="Also dump the full page with both bboxes drawn.")
    parser.add_argument("--tag", default="")
    parser.add_argument("--barrados", action="store_true",
                        help="Also dump every matched diagram the gate barred, and every one without annotated FEN.")
    args = parser.parse_args(argv)

    import cv2
    from chess_diagram_ocr.board_detection import NoBoardDetectedError
    from chess_diagram_ocr.config import ACCEPT_MIN_CONFIDENCE, DEFAULT_MODEL_PATH
    from chess_diagram_ocr.field_eval import _match, bbox_iou, evaluate_page, load_field_set
    from chess_diagram_ocr.service import OcrService, RecognitionOptions

    root = cvoff_root()
    pages = load_field_set(root / "data" / "field_set.jsonl")
    model = Path(DEFAULT_MODEL_PATH)
    if not model.is_file():
        model = root / "models" / "piece_classifier.pt"
    options = RecognitionOptions(
        model_path=model,
        max_boards=args.max_boards,
        dpi=args.dpi,
        refine_detected_boards=args.refine,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    out = args.out or REPO_ROOT / "benchmarks" / "reports" / f"f4_field_failures_{stamp}{tag}"
    out.mkdir(parents=True, exist_ok=True)

    service = OcrService(model_path=options.model_path)
    failures: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = []
    barred: list[dict[str, Any]] = []
    totals: dict[str, Any] = {}
    per_regime: dict[str, dict[str, int]] = {}
    per_book: dict[str, dict[str, int]] = {}
    counter = 0

    from chess_diagram_ocr.field_eval import FieldReport, _accumulate

    total = FieldReport()
    with _variant(args.variant):
        for page in pages:
            if not page.reviewed:
                continue
            pdf_path = root / "PDF" / page.pdf
            started = time.perf_counter()
            try:
                read = service.recognize_page(pdf_path, page.page, options=options)
            except NoBoardDetectedError:
                read = []
            elapsed = time.perf_counter() - started

            part = evaluate_page(page, read, accept_threshold=ACCEPT_MIN_CONFIDENCE, seconds=elapsed)
            _accumulate(total, part)
            if page.regime:
                _accumulate(total.per_regime.setdefault(page.regime, FieldReport()), part)
            _accumulate(total.per_book.setdefault(page.pdf, FieldReport()), part)

            matched = _match(page.diagrams, read)
            for index, annotated in enumerate(page.diagrams):
                slot = matched.get(index)
                if slot is None:
                    misses.append({"pdf": page.pdf, "page": page.page, "bbox": list(annotated.bbox),
                                   "regime": page.regime, "note": annotated.note})
                    continue
                got = read[slot]
                legal = got.is_fatal is not True
                above = got.min_confidence >= ACCEPT_MIN_CONFIDENCE
                exported = legal and above
                if args.barrados and (not exported or not annotated.placement):
                    bn = len(barred) + 1
                    bcrop = f"b{bn:02d}_{_slug(page.pdf)}_p{page.page}_d{index}.png"
                    if got.board_rgb is not None:
                        cv2.imwrite(str(out / bcrop),
                                    cv2.cvtColor(got.board_rgb, cv2.COLOR_RGB2BGR))
                    bdiff = (_diff_squares(got.placement, annotated.placement)
                             if annotated.placement else None)
                    barred.append({
                        "n": bn, "pdf": page.pdf, "page": page.page, "diagram": index,
                        "regime": page.regime, "note": annotated.note, "crop": bcrop,
                        "exported": exported, "legal": legal, "above_gate": above,
                        "reason": _block_reason(got, legal, above),
                        "verdict": _verdict(got.placement, annotated.placement),
                        "min_confidence": round(float(got.min_confidence), 4),
                        "mean_confidence": round(float(got.mean_confidence), 4),
                        "repaired_squares": [square_name(sq) for sq in (got.changed_squares or [])],
                        "weakest": _weakest(got),
                        "annotated_bbox": [round(v, 2) for v in annotated.bbox],
                        "read_placement": got.placement,
                        "truth_placement": annotated.placement,
                        "n_wrong_squares": len(bdiff) if bdiff is not None else None,
                        "wrong_squares": [square_name(sq) for sq in bdiff] if bdiff else [],
                    })
                if not annotated.placement:
                    unmeasured.append({"pdf": page.pdf, "page": page.page, "regime": page.regime,
                                       "exported": exported, "read": got.placement})
                    continue
                if got.placement == annotated.placement:
                    continue

                counter += 1
                diff = _diff_squares(got.placement, annotated.placement)
                squares: list[dict[str, Any]] = []
                if diff is not None:
                    for sq in diff:
                        conf = (
                            round(float(got.square_confidences[sq]), 4)
                            if sq < len(got.square_confidences)
                            else None
                        )
                        squares.append({
                            "square": square_name(sq),
                            "index": sq,
                            "truth": _piece_at(annotated.placement, sq),
                            "read": _piece_at(got.placement, sq),
                            "confidence": conf,
                            "repaired": sq in (got.changed_squares or []),
                            "top3": _top3(got.probs, sq),
                        })

                base = f"{counter:02d}_{_slug(page.pdf)}_p{page.page}_d{index}"
                crop_name = f"{base}.png"
                board = got.board_rgb
                if board is not None:
                    cv2.imwrite(str(out / crop_name), cv2.cvtColor(board, cv2.COLOR_RGB2BGR))

                page_name = ""
                if args.pages:
                    page_rgb = service.render_page(pdf_path, page.page, dpi=args.dpi)
                    canvas = cv2.cvtColor(page_rgb, cv2.COLOR_RGB2BGR)
                    scale = args.dpi / 72.0
                    ax0, ay0, ax1, ay1 = (v * scale for v in annotated.bbox)
                    cv2.rectangle(canvas, (int(ax0), int(ay0)), (int(ax1), int(ay1)), (0, 180, 0), 3)
                    if got.bbox_pdf is not None:
                        bx0, by0, bx1, by1 = (v * scale for v in got.bbox_pdf)
                        cv2.rectangle(canvas, (int(bx0), int(by0)), (int(bx1), int(by1)), (0, 0, 255), 3)
                    page_name = f"{base}_page.png"
                    cv2.imwrite(str(out / page_name), canvas)

                failures.append({
                    "n": counter,
                    "pdf": page.pdf,
                    "page": page.page,
                    "diagram": index,
                    "regime": page.regime,
                    "note": annotated.note,
                    "crop": crop_name,
                    "page_png": page_name,
                    "exported": exported,
                    "legal": legal,
                    "above_gate": above,
                    "min_confidence": round(float(got.min_confidence), 4),
                    "mean_confidence": round(float(got.mean_confidence), 4),
                    "detection_source": got.detection_source,
                    "rotation": got.rotation,
                    "orientation_reason": got.orientation_reason,
                    "repaired_squares": [square_name(s) for s in (got.changed_squares or [])],
                    "iou": round(bbox_iou(annotated.bbox, got.bbox_pdf), 4) if got.bbox_pdf else None,
                    "annotated_bbox": [round(v, 2) for v in annotated.bbox],
                    "detected_bbox": [round(v, 2) for v in got.bbox_pdf] if got.bbox_pdf else None,
                    "crop_shape": list(board.shape[:2]) if board is not None else None,
                    "read_placement": got.placement,
                    "truth_placement": annotated.placement,
                    "n_wrong_squares": len(diff) if diff is not None else None,
                    "squares": squares,
                })

    data = total.as_dict()
    totals = {k: data[k] for k in (
        "pages", "annotated", "detected", "matched", "false_positives", "detection_recall",
        "detection_precision", "legal", "above_gate", "exported", "export_rate", "comparable",
        "exact", "conditional_exact", "exported_comparable", "exported_exact", "exported_wrong",
        "field_exact", "repaired_squares", "repaired_diagrams", "seconds", "seconds_per_diagram")}
    keep = ("annotated", "matched", "exported", "comparable", "exact", "exported_comparable",
            "exported_exact", "field_exact", "detection_recall")
    per_regime = {n: {k: r.as_dict()[k] for k in keep} for n, r in sorted(total.per_regime.items())}
    per_book = {n: {k: r.as_dict()[k] for k in keep} for n, r in sorted(total.per_book.items())}

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "variant": args.variant,
        "dpi": args.dpi,
        "refine_detected_boards": args.refine,
        "model": str(options.model_path),
        "accept_threshold": ACCEPT_MIN_CONFIDENCE,
        "totals": totals,
        "per_regime": per_regime,
        "per_book": per_book,
        "n_failures": len(failures),
        "failures": failures,
        "misses": misses,
        "unmeasured_matched": unmeasured,
    }
    (out / "failures.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.barrados:
        (out / "barrados.json").write_text(
            json.dumps({"generated_at": payload["generated_at"], "accept_threshold": ACCEPT_MIN_CONFIDENCE,
                        "n": len(barred), "barrados": barred}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        _write_barrados(out, barred)

    print(f"variant={args.variant} refine={args.refine}")
    print(f"  annotated {totals['annotated']}  matched {totals['matched']}  recall {totals['detection_recall']:.4f}"
          f"  precision {totals['detection_precision']:.4f}")
    print(f"  comparable {totals['comparable']}  exact {totals['exact']}"
          f"  conditional_exact {totals['conditional_exact']:.4f}")
    print(f"  exported_comparable {totals['exported_comparable']}  exported_exact {totals['exported_exact']}"
          f"  field_exact {totals['field_exact']:.4f}")
    print(f"  wrong-but-matched diagrams dumped: {len(failures)}")
    for item in failures:
        flag = "EXPORTED" if item["exported"] else "blocked  "
        print(f"   [{item['n']:02d}] {flag} {item['pdf'][:46]:<46} p{item['page']:<4}"
              f" wrong={item['n_wrong_squares']} minconf={item['min_confidence']:.3f} {item['regime']}")
    if args.barrados:
        print(f"  barred-or-unannotated matched diagrams dumped: {len(barred)}")
        for b in barred:
            print(f"   [b{b['n']:02d}] {b['reason']:<10} {b['verdict']:<7} {b['pdf'][:40]:<40}"
                  f" p{b['page']:<4} minconf={b['min_confidence']:.3f}"
                  f" reparos={len(b['repaired_squares'])} {b['regime']}")
    print(f"\ndump -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
