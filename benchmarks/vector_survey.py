"""Which books on the shelf the vector path reads -- the survey the trunk never named.

``chess_diagram_ocr/detection/__init__.py`` says 2 of 27 sampled books are "diagrama
vetorial/fonte, sem imagem embutida" and that no current path reads them.  It does not say
which.  This runs :mod:`caissa.vision.detect.survey` over every PDF in the shelf of
``docs/quality/CORPUS.md`` 0 and prints the verdict per book with its evidence: the chess
font names found, the drawn 8x8 grids found, and how many pages would come out **exact**.

Nothing is rendered and nothing is inferred -- it is text and display-list queries only.

    .venv/Scripts/python.exe benchmarks/vector_survey.py --sample 24
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root  # noqa: E402
from caissa.vision.detect.survey import survey_pdf  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=24, help="Paginas amostradas por livro.")
    parser.add_argument("--pdf-dir", type=Path, default=None)
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)

    pdf_dir = args.pdf_dir or (cvoff_root() / "PDF")
    paths = sorted(p for p in pdf_dir.glob("*.pdf") if p.is_file())
    if not paths:
        raise SystemExit(f"nenhum PDF em {pdf_dir}")

    books: list[dict[str, Any]] = []
    started = time.perf_counter()
    for path in paths:
        clock = time.perf_counter()
        book = survey_pdf(path, sample=args.sample, allow_unverified=args.allow_unverified)
        data = book.as_dict()
        data["seconds"] = round(time.perf_counter() - clock, 2)
        books.append(data)
        print(
            f"{book.verdict:<16} {path.name[:64]:<66} "
            f"glifos={data['glyph_boards']:<4} desenhos={data['drawing_boards']:<4} "
            f"exatas={data['exact_pages']}/{book.sampled:<4} {data['seconds']:>6.2f}s "
            f"{','.join(book.chess_fonts) or '-'}"
        )
    elapsed = time.perf_counter() - started

    by_verdict: dict[str, list[str]] = {}
    for data in books:
        by_verdict.setdefault(data["verdict"], []).append(data["pdf"])

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pdf_dir": str(pdf_dir),
        "books": len(books),
        "sample": args.sample,
        "wall_s": round(elapsed, 1),
        "by_verdict": {k: sorted(v) for k, v in sorted(by_verdict.items())},
        "detail": books,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / f"vector_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(books)} livros em {elapsed:.1f}s")
    for verdict, names in report["by_verdict"].items():
        print(f"  {verdict:<16} {len(names)}")
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
