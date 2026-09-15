r"""Side to move by the numbering — OCR_UI_ROADMAP passo 7 — gated on the passo 0 truth.

Truth: the manifest regions with ``start_fen`` (passo 0: 8 in the SFC4, one of
them blind and left out).  The side of the FEN is the side the reader would
say; the question is whether the caption cascade (``caissa.ingest.pdf.captions``)
gets it, and **from where** (``move-number`` / ``caption-after`` / declared text
/ page scope / ``default``).

Two measurements per region:

* **verdade humana** — the page's labelled lines (the reviewer's text, origin
  ``text``) as the page text, the diagram boxes located by the trunk's detector
  (no classifier), ``page_contexts`` on top: this isolates the *rule* from OCR
  errors and is the gate;
* **produto** — the importer as it runs on a scan (OCR text, raster finder):
  what the book actually gets, reported next to it.

Gate: side inferred = side of the FEN in ≥ 90 % of the non-blind regions, with
origin ≠ ``default`` in ≥ 80 %.  Sabotage (``--sabotar paridade``): the
numbering rule reads the parity backwards — ``22...`` as White's turn — and
the accuracy must fall under 20 %.

    .venv\Scripts\python.exe benchmarks\side_to_move_gate.py
    .venv\Scripts\python.exe benchmarks\side_to_move_gate.py --sabotar paridade   # must fail
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from caissa.ingest.pdf import captions  # noqa: E402
from caissa.ingest.pdf.geometry import PageFrame  # noqa: E402
from caissa.ingest.pdf.textlayer import PageText, TextLine, TextSpan  # noqa: E402
from caissa.ocr.golden import load_manifest  # noqa: E402
from caissa.ocr.labeling import LabelProject  # noqa: E402

GOLDEN = ROOT / "benchmarks" / "corpus" / "golden"
MANIFEST = (
    GOLDEN / "manifest.private.json"
    if (GOLDEN / "manifest.private.json").exists()
    else GOLDEN / "manifest.json"
)
REPORTS = ROOT / "benchmarks" / "reports"
ACCURACY_FLOOR = 0.90
ORIGIN_FLOOR = 0.80


def _page_text_from_labels(page: Any) -> PageText:
    """The reviewer's lines as a page text (origin ``text``), block = region."""
    lines: list[TextLine] = []
    for region in page.regions:
        for line in region.lines:
            text = line.text if line.trainable else line.hypothesis
            if not text.strip():
                continue
            box = tuple(float(v) for v in line.box)
            lines.append(
                TextLine(
                    box=box,
                    spans=(TextSpan(text=text, box=box, size=10.0),),
                    block_index=region.index,
                )
            )
    return PageText(
        frame=PageFrame.synthetic(page.page_index, page.width_pt, page.height_pt),
        lines=tuple(lines),
    )


def _diagram_boxes(pdf: Path, page_index: int) -> list[tuple[float, float, float, float]]:
    """Where the diagrams are, by the trunk's detector — no classifier."""
    import pymupdf

    from caissa.ingest.pdf.finders import raster_diagram_finder

    finder = raster_diagram_finder(classify=False)
    doc = pymupdf.open(pdf)
    try:
        page = doc[page_index]
        frame = PageFrame.synthetic(page_index, page.rect.width, page.rect.height)
        hits = finder(page, frame, PageText(frame=frame, lines=()))
    finally:
        doc.close()
    return [tuple(float(v) for v in h.box) for h in hits]


def _first_move_legal(fen: str, truth: str) -> bool | None:
    """Whether the region's first move is legal from its ``start_fen`` (``None`` = unparsed)."""
    from caissa.ingest.pdf.games import is_invention
    from caissa.notation.legality_repair import repair_movetext

    try:
        report = repair_movetext(truth, start_fen=fen)
    except Exception:  # noqa: BLE001 - the truth is data; a crash is "unknown"
        return None
    # A first move the repairer had to turn into another move is not legal as
    # printed (passo 11 caught p10 «22... ♖g6» → Bg6 this way).
    return len(report.moves) > 0 and not is_invention(report.moves[0])


def _box_above(region_box, boxes) -> tuple[float, float, float, float] | None:
    """The nearest diagram whose bottom sits above the region, same column."""
    x0, top = region_box[0], region_box[1]
    above = [b for b in boxes if b[3] <= top + 5 and abs(b[0] - x0) < 140]
    return max(above, key=lambda b: b[3]) if above else None


def measure_truth(
    project: LabelProject, items: list[Any], *, sabotage: str | None
) -> list[dict[str, Any]]:
    if sabotage == "paridade":
        original = captions.move_start

        def flipped(text: str):
            found = original(text)
            return None if found is None else (found[0], not found[1])

        captions.move_start = flipped  # type: ignore[assignment]
    rows = []
    boxes_cache: dict[tuple[str, int], list] = {}
    for item, region in items:
        page = project.page(item.book, item.page_index)
        key = (item.book, item.page_index)
        if key not in boxes_cache:
            boxes_cache[key] = _diagram_boxes(project.pdf_for(item.book), item.page_index)
        boxes = boxes_cache[key]
        diagram = _box_above(region.box, boxes)
        truth_side = region.start_fen.split()[1]
        row = {
            "id": item.id,
            "page": item.page_index,
            "partition": str(item.partition),
            "truth": truth_side,
            "first_line": region.truth.splitlines()[0][:30],
            "diagram_found": diagram is not None,
            "inferred": None,
            "origin": "default",
            "evidence": "",
        }
        if diagram is not None:
            contexts, _ = captions.page_contexts(_page_text_from_labels(page), [diagram])
            context = contexts[0]
            if context.side_to_move is not None:
                row["inferred"] = "w" if context.side_to_move else "b"
                row["origin"] = str(context.side_to_move_origin)
                row["evidence"] = context.side_to_move_evidence
        if row["inferred"] is None:
            # What the product emits when nothing decides: White, said as "default".
            row["inferred"] = "w"
        row["correct"] = row["inferred"] == truth_side
        # Is the truth itself consistent?  The region's first move must be
        # legal from its FEN; when it is not, the FEN is the diagram's placement
        # with the wrong move number/side (passo 0 data), not a rule failure.
        row["truth_consistent"] = _first_move_legal(region.start_fen, region.truth)
        rows.append(row)
    return rows


def measure_product(project: LabelProject, items: list[Any]) -> list[dict[str, Any]]:
    """The importer on the scan: OCR text, raster finder, the IR's recorded source."""
    from caissa.core.model import Diagram
    from caissa.core.model.visitor import walk
    from caissa.ingest.pdf import PdfImportOptions, import_pdf
    from caissa.ingest.pdf.finders import combined_finder

    by_page: dict[tuple[str, int], list] = {}
    for item, region in items:
        by_page.setdefault((item.book, item.page_index), []).append((item, region))
    rows = []
    for (book, page_index), regions in by_page.items():
        result = import_pdf(
            project.pdf_for(book),
            PdfImportOptions(
                pages=[page_index],
                lang=project.languages.get(book, "eng"),
                diagram_finder=combined_finder(),
            ),
        )
        diagrams = [node for _path, node in walk(result.document) if isinstance(node, Diagram)]
        boxes = [(d, _rect_of(d)) for d in diagrams]
        for item, region in regions:
            truth_side = region.start_fen.split()[1]
            candidates = [(d, b) for d, b in boxes if b is not None]
            diagram = _box_above(region.box, [b for _, b in candidates])
            node = next((d for d, b in candidates if b == diagram), None)
            inferred = node.fen.split()[1] if node and len(node.fen.split()) > 1 else None
            rows.append(
                {
                    "id": item.id,
                    "page": page_index,
                    "truth": truth_side,
                    "inferred": inferred,
                    "origin": (node.recognition.side_to_move_source if node else None) or "default",
                    "correct": inferred == truth_side,
                }
            )
    return rows


def _rect_of(diagram: Any) -> tuple[float, float, float, float] | None:
    rect = getattr(diagram.source, "rect", None)
    if rect is None:
        return None
    # ``provenance.Rect`` is ``x, y, width, height``.
    x, y = getattr(rect, "x", None), getattr(rect, "y", None)
    w, h = getattr(rect, "width", None), getattr(rect, "height", None)
    if None not in (x, y, w, h):
        return (float(x), float(y), float(x) + float(w), float(y) + float(h))
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--project", type=Path, default=ROOT / "labeling")
    parser.add_argument("--sabotar", choices=("paridade",), default=None)
    parser.add_argument(
        "--sem-produto", action="store_true", help="só a medida sobre a verdade humana"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest, include_blind=True)
    project = LabelProject.load(args.project)
    items = [(i, r) for i in manifest.items for r in i.regions if r.start_fen]
    usable = [(i, r) for i, r in items if str(i.partition) != "blind"]
    print(f"regiões com start_fen: {len(items)} ({len(items) - len(usable)} na cega, fora)")
    started = time.perf_counter()
    truth_rows = measure_truth(project, usable, sabotage=args.sabotar)
    for row in truth_rows:
        flag = "" if row["truth_consistent"] else "  [verdade: 1.º lance ilegal da FEN]"
        print(
            f"  p{row['page']:<3} {row['partition']:5s} «{row['first_line']}»  "
            f"verdade {row['truth']}  inferido {row['inferred']}  origem {row['origin']:14s} "
            f"{'✓' if row['correct'] else '✗'}  "
            f"{row['evidence'][:30]!r}{flag}"
        )
    n = len(truth_rows)
    accuracy = sum(r["correct"] for r in truth_rows) / n if n else 0.0
    with_origin = sum(1 for r in truth_rows if r["origin"] != "default") / n if n else 0.0
    product_rows: list[dict[str, Any]] = []
    if not args.sem_produto and not args.sabotar:
        product_rows = measure_product(project, usable)
        print("  produto (OCR + via raster):")
        for row in product_rows:
            print(
                f"    p{row['page']:<3} verdade {row['truth']} inferido {row['inferred']} "
                f"origem {row['origin']:14s} {'✓' if row['correct'] else '✗'}"
            )
    passed = accuracy >= ACCURACY_FLOOR and with_origin >= ORIGIN_FLOOR
    print(
        f"portão (verdade humana, n={n}): acerto {accuracy:.2f} ≥ {ACCURACY_FLOOR} "
        f"{'✓' if accuracy >= ACCURACY_FLOOR else '✗'} · origem ≠ default "
        f"{with_origin:.2f} ≥ {ORIGIN_FLOOR} "
        f"{'✓' if with_origin >= ORIGIN_FLOOR else '✗'} → {'PASSOU' if passed else 'REPROVOU'}"
        f"{'  (sabotagem: ' + args.sabotar + ')' if args.sabotar else ''}"
    )
    if product_rows:
        pa = sum(r["correct"] for r in product_rows) / len(product_rows)
        po = sum(1 for r in product_rows if r["origin"] != "default") / len(product_rows)
        print(
            f"produto (informativo, n={len(product_rows)}): acerto {pa:.2f} · "
            f"origem ≠ default {po:.2f}"
        )
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = (
        args.out
        or REPORTS / f"side_to_move_{stamp}{'_' + args.sabotar if args.sabotar else ''}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "manifest": str(args.manifest),
                "corpus_hash": manifest.content_hash(),
                "sabotage": args.sabotar,
                "n": n,
                "accuracy": accuracy,
                "with_origin": with_origin,
                "passed": passed,
                "truth": truth_rows,
                "product": product_rows,
                "seconds": round(time.perf_counter() - started, 1),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"relatório: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(main())
