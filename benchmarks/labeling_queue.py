r"""Does the queue by value find the pages worth labelling? — OCR_UI_ROADMAP passo 5.

For each of three scanned books of the reference collection, the queue
(:mod:`caissa.ocr.labeling.queue`) scores a spaced sample of pages with the
production service, in an empty labelling project (nothing labelled, nothing
skipped).  The number is the one the reviewer feels: **how many lines the
service would send to review** on the five pages the queue puts first,
against the median page of the sample.

Two numbers per book, both printed, one of them the gate:

* **razão** — mean ``REVIEW`` lines of the top five over the median page of
  the sample (median floored at one line).  This is the roadmap's number
  (passo 5: "≥ 2×"), kept and reported next to its **ceiling** — the same
  ratio for the oracle order (pages sorted by their true review lines).  On
  scans where the service sends nearly every line to review the ceiling is
  below 2 (measured 1,1–1,3: the distribution is compressed), so no ordering
  at all can clear that bar; the ratio says how the book is, not how the
  queue is.
* **captura do oráculo** — the review lines on the queue's top five as a
  share of those on the oracle's top five.  This is what the queue controls
  and this is the gate: ≥ 0,90 in *every* book.

Sabotage (``--sabotar constante``): the score of every page is the same
constant, so the queue degenerates to the sampled (sequential) order — the
capture must fall well under the bar and the gate go red.  A gate that stays
green under a constant score is measuring the sample, not the queue.

Usage::

    .venv\Scripts\python.exe benchmarks\labeling_queue.py --pdfs 3
    .venv\Scripts\python.exe benchmarks\labeling_queue.py --pdfs 3 --sabotar constante   # must fail
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from caissa.ocr.labeling import LabelProject  # noqa: E402
from caissa.ocr.labeling.queue import PageValue, Ranking, rank_pages  # noqa: E402

CORPUS = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF")
REPORTS = ROOT / "benchmarks" / "reports"
#: Scanned books without a usable text layer, three languages, three decades.
BOOKS: tuple[tuple[str, str], ...] = (
    ("Koblenz - El dominio del arte de la combinacion (1978).pdf", "spa+eng"),
    ("Levenfis - Cartea sahistului inceparator (1962).pdf", "ron+eng"),
    ("Estrin - Bauernopfer in der Eroeffnung (1980).pdf", "deu+eng"),
)
TOP = 5
#: The roadmap's bar for the ratio — reported, with its ceiling, not gated.
RATIO_FLOOR = 2.0
MEDIAN_FLOOR = 1.0
#: The gate: share of the oracle's top-five review lines the queue captures.
CAPTURE_FLOOR = 0.90


def _service(lang: str) -> Any:
    from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig

    return OcrService(lang=lang, config=OcrServiceConfig())


def measure_book(
    pdf: Path, lang: str, *, sample: int, dpi: int, sabotage: str | None
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        project = LabelProject(root=Path(tmp), reviewer="bancada")
        document = project.add_document(pdf)
        project.languages[document] = lang
        service = _service(lang)
        started = time.perf_counter()
        score = None
        if sabotage == "constante":
            def score(page: Any) -> PageValue:
                return PageValue(page.document, page.page_index, score=1.0)
        ranking: Ranking = rank_pages(
            service, project, document, sample=sample, dpi=dpi, lang=lang, score=score,
            progress=lambda text: print(f"  {document[:32]}: {text}", file=sys.stderr),
        )
        elapsed = time.perf_counter() - started
    # Under sabotage the values carry no counts: score the same pages for real
    # to know how many review lines the constant order actually surfaced.
    if sabotage == "constante":
        with tempfile.TemporaryDirectory() as tmp:
            project = LabelProject(root=Path(tmp), reviewer="bancada")
            document = project.add_document(pdf)
            project.languages[document] = lang
            real = rank_pages(
                _service(lang), project, document,
                indices=[v.page_index for v in ranking.values], dpi=dpi, lang=lang,
            )
        by_page = {v.page_index: v for v in real.values}
        ordered = [by_page[v.page_index] for v in ranking.values]
    else:
        ordered = list(ranking.values)
    review = [v.review_lines for v in ordered]
    top = review[:TOP]
    oracle = sorted(review, reverse=True)[:TOP]
    med = float(sorted(review)[len(review) // 2]) if review else 0.0
    ratio = (mean(top) if top else 0.0) / max(med, MEDIAN_FLOOR)
    ceiling = (mean(oracle) if oracle else 0.0) / max(med, MEDIAN_FLOOR)
    capture = sum(top) / sum(oracle) if sum(oracle) else 1.0
    return {
        "pdf": pdf.name,
        "lang": lang,
        "pages_scored": len(ordered),
        "seconds": round(elapsed, 1),
        "order": [v.page_index for v in ordered],
        "review_lines_in_order": review,
        "top_mean_review": round(mean(top), 2) if top else 0.0,
        "oracle_top_mean_review": round(mean(oracle), 2) if oracle else 0.0,
        "median_review": med,
        "ratio": round(ratio, 3),
        "ratio_ceiling": round(ceiling, 3),
        "ratio_bar_reachable": ceiling >= RATIO_FLOOR,
        "capture": round(capture, 3),
        "passed": capture >= CAPTURE_FLOOR,
        "top": [v.as_dict() for v in ordered[:TOP]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pdfs", type=int, default=3, help="quantos livros da lista fixa")
    parser.add_argument("--sample", type=int, default=12, help="páginas amostradas por livro")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--sabotar", choices=("constante",), default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    books = BOOKS[: max(1, args.pdfs)]
    results = []
    for name, lang in books:
        pdf = CORPUS / name
        if not pdf.is_file():
            print(f"livro ausente: {pdf}", file=sys.stderr)
            return 2
        result = measure_book(pdf, lang, sample=args.sample, dpi=args.dpi, sabotage=args.sabotar)
        results.append(result)
        print(
            f"{name[:48]:48s} top-{TOP} média {result['top_mean_review']:5.1f} linhas em revisão | "
            f"mediana {result['median_review']:4.1f} | razão {result['ratio']:.2f} "
            f"(teto {result['ratio_ceiling']:.2f}"
            f"{'' if result['ratio_bar_reachable'] else ', 2× inatingível'}) | "
            f"captura do oráculo {result['capture']:.2f} "
            f"{'✓' if result['passed'] else '✗'}  ({result['seconds']:.0f} s)"
        )
        print(f"  ordem: {result['order']}")
        print(f"  linhas em revisão nessa ordem: {result['review_lines_in_order']}")
    passed = all(r["passed"] for r in results)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    suffix = f"_{args.sabotar}" if args.sabotar else ""
    out = args.out or REPORTS / f"labeling_queue_{stamp}{suffix}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sample": args.sample, "dpi": args.dpi, "sabotage": args.sabotar,
        "top": TOP, "ratio_floor": RATIO_FLOOR, "median_floor": MEDIAN_FLOOR,
        "capture_floor": CAPTURE_FLOOR,
        "books": results, "passed": passed,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"portão: captura do oráculo no top-{TOP} ≥ {CAPTURE_FLOOR:.2f} em cada livro → "
        f"{'PASSOU' if passed else 'REPROVOU'}"
        f"{'  (sabotagem: ' + args.sabotar + ')' if args.sabotar else ''}"
    )
    print(f"relatório: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(main())
