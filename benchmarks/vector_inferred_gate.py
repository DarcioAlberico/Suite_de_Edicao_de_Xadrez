r"""The fallback for chess fonts outside the catalog — OCR_UI_ROADMAP passo 10 — gated.

The shelf has no such font (``vector_survey.py``, 2026-09-14: 0 of 46 books
list an unknown chess font), so the fallback is measured the way the roadmap
sabotages it: the two font-set books (``Dvoretsky's Endgame Manual``, Chess
Merida; ``Polgar 5334``, SkakNew) are read with their family **hidden from
the catalog**.  The exact vector read of the same page is the truth.

Per sampled page: boards the exact path reads; lattices the unknown-font
detector finds with the family hidden; how many of those the classifier
reads; how many placements agree with the exact read; the confidences.

Gate: with the catalog intact the inferred finder yields **nothing** (the
catalogued books do not change); with the family hidden it reads > 0 boards,
every confidence ≤ 0,85, and ≥ 0,90 of the placements agree with the
product's read — the exact one, completed by the classifier where the text
layer had holes (a fallback that reads wrong positions is worse than a
located, unread board).

Found on the way (2026-09-14): on the Polgar the extractor drops every rook
on a dark square, the exact path took the hole for an empty square, and 61
of 114 boards were wrong; ``combined_finder`` now completes holed reads
with the classifier (``fill_holes``) and marks them ``VECTOR_INFERRED``.

    .venv\Scripts\python.exe benchmarks\vector_inferred_gate.py --sample 12
    .venv\Scripts\python.exe benchmarks\vector_inferred_gate.py --sample 12 --sabotar cobertura
    # (the sabotage must fail)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from caissa.core.model import RecognitionPath  # noqa: E402
from caissa.ingest.pdf.document import sample_indices  # noqa: E402
from caissa.ingest.pdf.finders import (  # noqa: E402
    INFERRED_CONFIDENCE_CAP,
    combined_finder,
    inferred_font_finder,
)
from caissa.vision.detect import detect_vector_boards, lookup_family  # noqa: E402

CORPUS = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF")
REPORTS = ROOT / "benchmarks" / "reports"
BOOKS: tuple[tuple[str, str], ...] = (
    ("Dvoretsky - Dvoretsky's Endgame Manual (2025).pdf", "merida"),
    ("Polgar,_Laszlo_Chess_5334_Problems,_Combinations,_and_Games.pdf", "skak"),
)
AGREEMENT_FLOOR = 0.90


def _overlap(a, b) -> float:
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = width * height
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / smaller if smaller > 0 else 0.0


def measure_book(pdf: Path, family: str, *, sample: int, sabotage: str | None) -> dict[str, Any]:
    import pymupdf

    def hidden(name: str):
        key = name.lower().replace("-", "").replace(" ", "")
        return None if family in key else lookup_family(name)

    intact = inferred_font_finder()
    fallback = inferred_font_finder(lookup=hidden)
    # The product's finder with the catalog intact: exact reads whose text
    # layer lacked cells are completed by the classifier (fill_holes).
    product = combined_finder(raster=lambda _p, _f, _t: [], inferred=lambda _p, _f, _t: [])
    doc = pymupdf.open(pdf)
    pages = sample_indices(len(doc), sample)
    rows = []
    started = time.perf_counter()
    for index in pages:
        page = doc[index]
        exact = detect_vector_boards(page)
        frame = SimpleNamespace(index=index)
        with_catalog = intact(page, frame, None)
        inferred = fallback(page, frame, None)
        refined = product(page, frame, None)
        holed = sum(1 for b in exact if b.evidence.inferred_cells)
        filled = [h for h in refined if h.path is RecognitionPath.VECTOR_INFERRED]
        filled_agree = 0
        for hit in filled:
            twin = next((i for i in inferred if i.fen and _overlap(hit.box, i.box) > 0.5), None)
            if twin is not None and twin.fen.split()[0] == hit.fen.split()[0]:
                filled_agree += 1
        agree = 0
        read = 0
        confidences = []
        for hit in inferred:
            if hit.fen is None:
                continue
            read += 1
            confidences.append(hit.confidence)
            # Truth: the product's read — exact, or exact completed by the
            # classifier where the text layer had holes (Polgar: 29 of 54).
            match = next((b for b in refined if b.fen and _overlap(hit.box, b.box) > 0.5), None)
            got = hit.fen.split()[0]
            truth = match.fen.split()[0] if match is not None else None
            if sabotage == "cobertura":
                got = got[::-1]  # the sabotage: the read comes back mirrored
            if truth is not None and got == truth:
                agree += 1
        rows.append({
            "page": index, "exact": len(exact), "holed": holed, "filled": len(filled),
            "filled_agree_with_full_read": filled_agree,
            "inferred_with_catalog": len(with_catalog),
            "lattices": len(inferred), "read": read, "agree": agree,
            "confidences": [round(c, 3) for c in confidences],
            "paths": sorted({str(h.path) for h in inferred}),
        })
    doc.close()
    exact_total = sum(r["exact"] for r in rows)
    read_total = sum(r["read"] for r in rows)
    agree_total = sum(r["agree"] for r in rows)
    confidences = [c for r in rows for c in r["confidences"]]
    return {
        "pdf": pdf.name, "family_hidden": family, "pages": pages,
        "seconds": round(time.perf_counter() - started, 1),
        "exact_boards": exact_total,
        "holed": sum(r["holed"] for r in rows),
        "filled": sum(r["filled"] for r in rows),
        "filled_agree_with_full_read": sum(r["filled_agree_with_full_read"] for r in rows),
        "inferred_with_catalog": sum(r["inferred_with_catalog"] for r in rows),
        "lattices": sum(r["lattices"] for r in rows),
        "read": read_total, "agree": agree_total,
        "agreement": round(agree_total / read_total, 4) if read_total else None,
        "max_confidence": max(confidences) if confidences else None,
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "paths": sorted({p for r in rows for p in r["paths"]}),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=12)
    parser.add_argument("--sabotar", choices=("cobertura",), default=None,
                        help="cobertura: a leitura volta espelhada — a concordância tem de cair")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    results = []
    for name, family in BOOKS:
        pdf = CORPUS / name
        if not pdf.is_file():
            print(f"livro ausente: {pdf}", file=sys.stderr)
            return 2
        result = measure_book(pdf, family, sample=args.sample, sabotage=args.sabotar)
        results.append(result)
        print(f"{name[:52]:52s} exatos {result['exact_boards']:3d} (com casas ausentes "
              f"{result['holed']}, completados pelo classificador {result['filled']}, dos quais "
              f"{result['filled_agree_with_full_read']} iguais à leitura inteira) | com catálogo: "
              f"inferidos {result['inferred_with_catalog']} | família oculta: reticulados "
              f"{result['lattices']}, "
              f"lidos {result['read']}, concordam {result['agree']} "
              f"({(result['agreement'] or 0) * 100:.1f} %), conf. máx "
              f"{result['max_confidence']}, vias {result['paths']}  ({result['seconds']:.0f} s)")
    untouched = all(r["inferred_with_catalog"] == 0 for r in results)
    read = all(r["read"] > 0 for r in results)
    capped = all((r["max_confidence"] or 0.0) <= INFERRED_CONFIDENCE_CAP + 1e-9 for r in results)
    agree = all((r["agreement"] or 0.0) >= AGREEMENT_FLOOR for r in results)
    passed = untouched and read and capped and agree
    print(f"portão: catálogo intacto → 0 inferidos {'✓' if untouched else '✗'} · família oculta → "
          f"lidos > 0 {'✓' if read else '✗'} · confiança ≤ {INFERRED_CONFIDENCE_CAP} "
          f"{'✓' if capped else '✗'} · concordância ≥ {AGREEMENT_FLOOR} {'✓' if agree else '✗'} → "
          f"{'PASSOU' if passed else 'REPROVOU'}"
          f"{'  (sabotagem: ' + args.sabotar + ')' if args.sabotar else ''}")
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    suffix = f"_{args.sabotar}" if args.sabotar else ""
    out = args.out or REPORTS / f"vector_inferred_{stamp}{suffix}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "sample": args.sample,
        "sabotage": args.sabotar, "confidence_cap": INFERRED_CONFIDENCE_CAP,
        "agreement_floor": AGREEMENT_FLOOR, "books": results, "passed": passed,
        "gates": {"untouched": untouched, "read": read, "capped": capped, "agree": agree},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"relatório: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(main())
