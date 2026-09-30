"""How many diagrams on the shelf are printed from Black's point of view?

OCR_UI_ROADMAP_C2 passo C10 (analysis §3.8, D7): the trunk's ``CoordinateRule``
has never spoken because nothing builds ``BoardCoordinates``, and the S-45
measurement covered the field set only (49 of 49 conclusive diagrams from
White's side).  Before wiring the coordinate reader into the raster path the
question is how often the shelf prints a board the other way round -- if the
answer is zero, what remains is the vector-path bug (a placement never rotated
when ``white_at_bottom`` is false).

Text-layer only, no rendering: every page of every PDF is scanned for the
rows of coordinates a diagram prints around itself -- a horizontal run of
single letters ``a``..``h`` (or one word ``abcdefgh``) and a vertical run of
digits ``1``..``8`` -- and each run is classified by the direction it reads
in.  Files left-to-right and ranks 8-at-top are White's point of view; the
reverse is Black's.  A run is counted only when it is monotonic over at
least six labels, so a table of contents or a list of numbered items does
not count.

    .venv/Scripts/python.exe benchmarks/coordinate_survey.py [--sabotar espelhar]

``--sabotar espelhar`` mirrors every run before classifying it: the two
columns of the table must swap, or the survey is not reading direction.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root  # noqa: E402

FILES = "abcdefgh"
RANKS = "12345678"
MIN_RUN = 6


def _runs(words: list[tuple[float, float, float, float, str]], *, axis: str
          ) -> list[list[tuple[float, str]]]:
    """Runs of single-character labels aligned on one line (files) or one column (ranks)."""
    alphabet = FILES if axis == "files" else RANKS
    singles = [(w, t.strip().lower()) for *w, t in [(x0, y0, x1, y1, t) for x0, y0, x1, y1, t in words]
               if len(t.strip()) == 1 and t.strip().lower() in alphabet]
    groups: dict[int, list[tuple[float, str]]] = {}
    for (x0, y0, x1, y1), text in singles:
        if axis == "files":
            key = int(round((y0 + y1) / 2.0 / 3.0))     # same baseline within 3 pt
            groups.setdefault(key, []).append(((x0 + x1) / 2.0, text))
        else:
            key = int(round((x0 + x1) / 2.0 / 3.0))
            groups.setdefault(key, []).append(((y0 + y1) / 2.0, text))
    out = []
    for members in groups.values():
        members.sort()
        # Split a line into runs of neighbouring labels: two diagrams side by
        # side print two rows on the same baseline.
        run: list[tuple[float, str]] = []
        for pos, text in members:
            if run and pos - run[-1][0] > 40.0:
                out.append(run)
                run = []
            run.append((pos, text))
        if run:
            out.append(run)
    return [r for r in out if len(r) >= MIN_RUN]


def _direction(run: list[tuple[float, str]], alphabet: str) -> int:
    indices = [alphabet.index(t) for _, t in run]
    if all(b > a for a, b in zip(indices, indices[1:], strict=False)):
        return 1
    if all(b < a for a, b in zip(indices, indices[1:], strict=False)):
        return -1
    return 0


def survey_page(page: Any, *, mirror: bool = False) -> Counter[str]:
    words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
    counts: Counter[str] = Counter()
    # One-word rows: "abcdefgh" / "hgfedcba" printed as a single string.
    for _x0, _y0, _x1, _y1, text in words:
        t = text.strip().lower()
        if t in (FILES, FILES[::-1]):
            forward = (t == FILES) != mirror
            counts["files_white" if forward else "files_black"] += 1
    for run in _runs(words, axis="files"):
        if mirror:
            run = [(p, t) for p, t in zip([q for q, _ in run], [t for _, t in run][::-1], strict=True)]
        direction = _direction(run, FILES)
        if direction:
            counts["files_white" if direction > 0 else "files_black"] += 1
    for run in _runs(words, axis="ranks"):
        if mirror:
            run = [(p, t) for p, t in zip([q for q, _ in run], [t for _, t in run][::-1], strict=True)]
        direction = _direction(run, RANKS)   # y grows downwards: 8 at top reads as -1
        if direction:
            counts["ranks_white" if direction < 0 else "ranks_black"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    import pymupdf

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pdf-dir", type=Path, default=None)
    parser.add_argument("--sabotar", choices=("", "espelhar"), default="")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    args = parser.parse_args(argv)

    pdf_dir = args.pdf_dir or (cvoff_root() / "PDF")
    paths = sorted(p for p in pdf_dir.glob("*.pdf") if p.is_file())
    if not paths:
        raise SystemExit(f"nenhum PDF em {pdf_dir}")
    mirror = args.sabotar == "espelhar"
    started = time.perf_counter()
    books: list[dict[str, Any]] = []
    total: Counter[str] = Counter()
    print(f"{'livro':<60} {'págs':>5} {'a-h →':>6} {'h-a ←':>6} {'8 topo':>6} {'1 topo':>6}")
    for path in paths:
        counts: Counter[str] = Counter()
        try:
            doc = pymupdf.open(path)
        except Exception as exc:  # noqa: BLE001 - a broken PDF is a row, not a crash
            print(f"{path.name[:60]:<60} ERRO {exc}")
            continue
        pages = doc.page_count
        for page in doc:
            counts.update(survey_page(page, mirror=mirror))
        doc.close()
        total.update(counts)
        books.append({"book": path.name, "pages": pages, **{k: counts[k] for k in sorted(counts)}})
        if counts:
            print(f"{path.name[:60]:<60} {pages:5d} {counts['files_white']:6d} "
                  f"{counts['files_black']:6d} {counts['ranks_white']:6d} {counts['ranks_black']:6d}")
    print(f"\ntotal: a-h → {total['files_white']}, h-a ← {total['files_black']}, "
          f"8 no topo {total['ranks_white']}, 1 no topo {total['ranks_black']} "
          f"em {len(books)} livros, {time.perf_counter() - started:.0f} s"
          + (" (sabotagem: espelhar)" if mirror else ""))
    black = total["files_black"] + total["ranks_black"]
    white = total["files_white"] + total["ranks_white"]
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out / f"coordinate_survey_{stamp}{'_espelhar' if mirror else ''}.json"
    out.write_text(json.dumps({"generated_at": stamp, "mirror": mirror, "books": books,
                               "total": dict(total), "white_pov_runs": white,
                               "black_pov_runs": black}, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(f"gravado em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
