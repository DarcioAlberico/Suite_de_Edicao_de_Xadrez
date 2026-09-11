r"""F2 on the reference collection: import sampled pages of every book and measure.

Usage::

    .venv\\Scripts\\python.exe benchmarks\\bench_ingest.py --sample 12
    .venv\\Scripts\\python.exe benchmarks\\bench_ingest.py --only Dvoretsky --pages 200-206 --dump

What is measured, per book: pages per second for the two passes, how each
page's text was sourced (text layer / OCR / image-only / rejected), how many
paragraphs, headings, captions, footnotes, move blocks, diagrams (located,
read, with a side to move) came out, how many columns the layout saw, and
the *continuity split ratio* -- the share of paragraph boundaries where the
first block ends without terminal punctuation and the next opens in lower
case, which is what a wrongly split or wrongly ordered paragraph looks like
from the outside.  It is a proxy, not a ground truth: books legitimately
break paragraphs mid-sentence at a diagram.

``--dump`` writes each imported page's blocks as text next to the report, for
the side-by-side reading the F2 gate asks a critic to do.

The report goes to ``benchmarks/reports/ingest_<timestamp>.json``.  No number
in ``docs/quality/F2_REPORT.md`` should exist without the run that produced it.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from caissa.core.model import Diagram, Heading, Paragraph, plain_text  # noqa: E402
from caissa.ingest.pdf import PdfImportOptions, import_pdf, open_pdf  # noqa: E402
from caissa.ingest.pdf.document import sample_indices  # noqa: E402

CORPUS = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF")
REPORTS = ROOT / "benchmarks" / "reports"
SENTENCE_END = ".!?…:;”’\"')]}»"


def _pages_arg(value: str | None, page_count: int, sample: int) -> list[int]:
    if value:
        out: list[int] = []
        for part in value.split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                out.extend(range(int(a), int(b) + 1))
            else:
                out.append(int(part))
        return [p for p in out if 0 <= p < page_count]
    return sample_indices(page_count, sample)


def _continuity(document) -> tuple[int, int]:
    """(suspicious boundaries, boundaries) between consecutive paragraphs."""
    texts = [
        plain_text(b.content).strip() for b in document.body if isinstance(b, (Paragraph, Heading))
    ]
    boundaries = 0
    suspicious = 0
    for a, b in itertools.pairwise(texts):
        if not a or not b:
            continue
        boundaries += 1
        if a[-1] not in SENTENCE_END and b[0].islower():
            suspicious += 1
    return suspicious, boundaries


def _dump(document, target: Path) -> None:
    lines: list[str] = []
    for block in document.body:
        page = block.provenance.page_index if block.provenance else -1
        if isinstance(block, Heading):
            lines.append(f"[p{page + 1}] # {'#' * (block.level - 1)} {plain_text(block.content)}")
        elif isinstance(block, Paragraph):
            lines.append(f"[p{page + 1}] ({block.props.style}) {plain_text(block.content)}")
        elif isinstance(block, Diagram):
            lines.append(
                f"[p{page + 1}] [DIAGRAMA {block.label or block.number or ''} {block.fen} "
                f"{block.stipulation or ''} :: {plain_text(block.caption)}]"
            )
        else:
            lines.append(f"[p{page + 1}] [{type(block).__name__}]")
        lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")


def run_book(
    path: Path, pages: list[int], *, dump_dir: Path | None, finder: object = None
) -> dict[str, object]:
    started = time.perf_counter()
    with open_pdf(path) as doc:
        page_count = doc.page_count
        result = import_pdf(doc, PdfImportOptions(pages=pages, diagram_finder=finder))  # type: ignore[arg-type]
    elapsed = time.perf_counter() - started
    report = result.report
    suspicious, boundaries = _continuity(result.document)
    columns = Counter(p.columns for p in report.pages)
    row: dict[str, object] = {
        "book": path.name,
        "page_count": page_count,
        "pages_imported": len(pages),
        "seconds": round(elapsed, 2),
        "pages_per_second": round(len(pages) / elapsed, 2) if elapsed else None,
        "sources": report.pages_by_source,
        "body_size": round(report.body_size, 1),
        "counters": report.counters,
        "columns": {str(k): v for k, v in sorted(columns.items())},
        "furniture_patterns": report.furniture_patterns,
        "figurines_mapped": report.figurines_mapped,
        "figurine_fonts": list(report.figurine_fonts),
        "bold_by_ink": list(report.bold_fonts),
        "continuity_suspicious": suspicious,
        "continuity_boundaries": boundaries,
        "continuity_ratio": round(suspicious / boundaries, 3) if boundaries else None,
        "notes": report.notes[:10],
        "page_ms_median": (
            round(sorted(p.duration_ms for p in report.pages)[len(report.pages) // 2], 1)
            if report.pages
            else None
        ),
    }
    if dump_dir is not None:
        dump_dir.mkdir(parents=True, exist_ok=True)
        _dump(result.document, dump_dir / (path.stem[:60] + ".txt"))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sample", type=int, default=12, help="páginas por livro (espaçadas)")
    parser.add_argument("--pages", help="páginas explícitas, ex. 200-206,300")
    parser.add_argument("--only", action="append", help="fragmento do nome do livro (repetível)")
    parser.add_argument(
        "--dump", action="store_true", help="grava os blocos de cada livro em texto"
    )
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument(
        "--raster",
        action="store_true",
        help="liga a via raster (detector do tronco + classificador F4 na GPU) além da vetorial",
    )
    args = parser.parse_args()
    finder = None
    if args.raster:
        from caissa.ingest.pdf.finders import combined_finder

        finder = combined_finder()

    corpus = Path(args.corpus)
    books = sorted(p for p in corpus.glob("*.pdf") if p.is_file())
    if args.only:
        wanted = [w.lower() for w in args.only]
        books = [b for b in books if any(w in b.name.lower() for w in wanted)]
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    REPORTS.mkdir(parents=True, exist_ok=True)
    dump_dir = REPORTS / f"ingest_{stamp}_dump" if args.dump else None

    rows: list[dict[str, object]] = []
    for book in books:
        with open_pdf(book) as doc:
            pages = _pages_arg(args.pages, doc.page_count, args.sample)
        try:
            row = run_book(book, pages, dump_dir=dump_dir, finder=finder)
        except Exception as exc:  # noqa: BLE001 - a crash is a finding, recorded and continued
            row = {"book": book.name, "error": f"{type(exc).__name__}: {exc}"}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False)[:400])

    out = REPORTS / f"ingest_{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "generated": stamp,
                "sample": args.sample,
                "pages": args.pages,
                "raster": args.raster,
                "books": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nrelatório: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
