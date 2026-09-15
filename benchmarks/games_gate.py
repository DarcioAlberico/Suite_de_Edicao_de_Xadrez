r"""Movetext → GameScore — OCR_UI_ROADMAP passo 11 — gated on the Nunn pages and the SFC4 truth.

Two populations, both through the product (``import_pdf`` with the raster
finder and OCR, ``games=True``):

* **Nunn, 6 pages** (the F5 chain: p120, 140, 160, 200, 220, 240): how many
  legal moves chain into games per page, against the move-looking tokens the
  page's ``Movetext`` paragraphs hold.  F5 got 12 of 18; the roadmap asks
  ≥ 16 of 18.
* **SFC4, the regions with ``start_fen``** (passo 0, out of the blind
  partition): the truth is the region's own text replayed from its FEN with no
  invention; the product's games on that page are compared with it — share of
  the truth's moves found in order (≥ 90 %), and moves in the games that are
  not printed on the page (must be 0).

Sabotage (``--sabotar fen``): every diagram's position is replaced by another
legal position of the same book before the games pass; the chaining must fall
under 30 % — a legal move by chance does not sustain a sequence.

    .venv\Scripts\python.exe benchmarks\games_gate.py
    .venv\Scripts\python.exe benchmarks\games_gate.py --sabotar fen     # must fail
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from caissa.core.model import GameScore, Paragraph  # noqa: E402
from caissa.core.model.inline import plain_text  # noqa: E402
from caissa.core.model.visitor import walk  # noqa: E402
from caissa.ingest.pdf import games as games_module  # noqa: E402
from caissa.ocr.golden import load_manifest  # noqa: E402
from caissa.ocr.labeling import LabelProject  # noqa: E402

CORPUS = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF")
NUNN = CORPUS / "📚Nunn J. Secrets of Minor Piece Endings.pdf"
NUNN_PAGES = (120, 140, 160, 200, 220, 240)
GOLDEN = ROOT / "benchmarks" / "corpus" / "golden"
MANIFEST = (
    GOLDEN / "manifest.private.json"
    if (GOLDEN / "manifest.private.json").exists()
    else GOLDEN / "manifest.json"
)
REPORTS = ROOT / "benchmarks" / "reports"
NUNN_FLOOR = 16
COVERAGE_FLOOR = 0.90
SABOTAGE_CEILING = 0.30
#: A legal position of the SFC4 (p. 10, the endgame) — what every diagram
#: becomes under ``--sabotar fen``.
OTHER_POSITION = "8/6k1/3b4/1R1p4/1PpPr1p1/2P3n1/3B2K1/6N1 b - - 0 36"
_MOVE_TOKEN = re.compile(
    r"^(?:\d{1,3}\.{0,3})?[♔-♟KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#!?]*$|^O-O(?:-O)?[+#!?]*$"
)
_FIG = dict(zip("♔♕♖♗♘♙", "KQRBNP", strict=True))


def _norm(token: str) -> str:
    token = re.sub(r"^\d{1,3}\.{0,3}", "", token.strip("(),;"))
    token = "".join(_FIG.get(ch, ch) for ch in token)
    return re.sub(r"[+#!?]+$", "", token)


def _move_tokens(text: str) -> list[str]:
    return [_norm(t) for t in text.split() if _MOVE_TOKEN.match(t.strip("(),;"))]


def _games_on(document: Any) -> list[list[str]]:
    out = []
    for _path, node in walk(document):
        if isinstance(node, GameScore) and node.children:
            sans, move = [], node.children[0]
            while move is not None:
                sans.append(move.san.rstrip("+#"))
                move = move.children[0] if move.children else None
            out.append(sans)
    return out


def _movetext_tokens(document: Any) -> list[str]:
    tokens: list[str] = []
    for _path, node in walk(document):
        if isinstance(node, Paragraph) and getattr(node.props, "style", "") == "Movetext":
            tokens.extend(_move_tokens(plain_text(node.content)))
        elif isinstance(node, GameScore):
            move = node.children[0] if node.children else None
            while move is not None:
                tokens.append(move.san.rstrip("+#"))
                move = move.children[0] if move.children else None
    return tokens


def _import(pdf: Path, page: int, lang: str) -> Any:
    from caissa.ingest.pdf import PdfImportOptions, import_pdf
    from caissa.ingest.pdf.finders import combined_finder

    return import_pdf(
        pdf, PdfImportOptions(pages=[page], lang=lang, diagram_finder=combined_finder())
    )


def measure_nunn() -> list[dict[str, Any]]:
    rows = []
    for page in NUNN_PAGES:
        result = _import(NUNN, page, "eng")
        games = _games_on(result.document)
        rows.append(
            {
                "page": page,
                "games": len(games),
                "chained": sum(len(g) for g in games),
                "tokens": len(_movetext_tokens(result.document)),
                "lines": [" ".join(g) for g in games],
                "counters": {
                    k: v
                    for k, v in result.report.counters.items()
                    if "game" in k or "movetext" in k
                },
            }
        )
        print(
            f"  Nunn p{page:<4} jogos {len(games)}  lances encadeados {rows[-1]['chained']:2d} / "
            f"{rows[-1]['tokens']:2d} tokens de lance  {rows[-1]['lines'][:2]}"
        )
    return rows


def _truth_moves(text: str, fen: str) -> list[str]:
    from caissa.notation.legality_repair import repair_movetext

    report = repair_movetext(text, start_fen=fen)
    out = []
    for move in report.moves:
        if games_module.is_invention(move):
            break
        out.append(move.san.rstrip("+#"))
    return out


def measure_sfc4(project: LabelProject) -> list[dict[str, Any]]:
    manifest = load_manifest(MANIFEST, include_blind=True)
    items = [
        (i, r)
        for i in manifest.items
        for r in i.regions
        if r.start_fen and str(i.partition) != "blind"
    ]
    rows = []
    cache: dict[int, Any] = {}
    for item, region in items:
        if item.page_index not in cache:
            cache[item.page_index] = _import(
                project.pdf_for(item.book), item.page_index, project.languages.get(item.book, "eng")
            )
        result = cache[item.page_index]
        truth = _truth_moves(region.truth, region.start_fen)
        games = _games_on(result.document)
        page = project.page(item.book, item.page_index)
        printed = set()
        for reg in page.regions:
            for line in reg.lines:
                printed.update(_move_tokens(line.text if line.trainable else line.hypothesis))
        # Coverage: the truth's moves found in one game (the best one).
        found = max((len([s for s in truth if s in g]) for g in games), default=0)
        invented = [s for g in games for s in g if s not in printed]
        rows.append(
            {
                "id": item.id,
                "page": item.page_index,
                "partition": str(item.partition),
                "first_line": region.truth.splitlines()[0][:26],
                "truth": truth,
                "truth_n": len(truth),
                "found": found,
                "coverage": (found / len(truth)) if truth else None,
                "games": [" ".join(g) for g in games],
                "invented": invented,
            }
        )
        print(
            f"  SFC4 p{item.page_index:<3} «{rows[-1]['first_line']}» verdade {len(truth)} lances "
            f"{truth[:6]} | na partida {found} | inventados {len(invented)} | "
            f"jogos {rows[-1]['games'][:2]}"
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--sabotar", choices=("fen",), default=None)
    parser.add_argument("--project", type=Path, default=ROOT / "labeling")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.sabotar == "fen":
        games_module._usable_fen = lambda _diagram: OTHER_POSITION  # type: ignore[assignment]
    started = time.perf_counter()
    nunn = measure_nunn()
    sfc4 = measure_sfc4(LabelProject.load(args.project))
    chained = sum(r["chained"] for r in nunn)
    tokens = sum(r["tokens"] for r in nunn)
    covered = [r for r in sfc4 if r["truth_n"]]
    coverage = (
        (sum(r["found"] for r in covered) / sum(r["truth_n"] for r in covered)) if covered else 0.0
    )
    invented = sum(len(r["invented"]) for r in sfc4)
    nunn_ok = chained >= NUNN_FLOOR
    cov_ok = coverage >= COVERAGE_FLOOR and invented == 0
    passed = nunn_ok and cov_ok
    sabotage_note = (
        f"  (sabotagem: fen — a cobertura tem de ficar < {SABOTAGE_CEILING})"
        if args.sabotar
        else ""
    )
    print(
        f"portão: Nunn {chained} lances encadeados em {tokens} tokens (≥ {NUNN_FLOOR}) "
        f"{'✓' if nunn_ok else '✗'} · SFC4 cobertura {coverage:.2f} (≥ {COVERAGE_FLOOR}) e "
        f"inventados {invented} (= 0) {'✓' if cov_ok else '✗'} → "
        f"{'PASSOU' if passed else 'REPROVOU'}{sabotage_note}"
    )
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = args.out or REPORTS / f"games_{stamp}{'_' + args.sabotar if args.sabotar else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "sabotage": args.sabotar,
                "nunn": nunn,
                "nunn_chained": chained,
                "nunn_tokens": tokens,
                "sfc4": sfc4,
                "sfc4_coverage": coverage,
                "sfc4_invented": invented,
                "passed": passed,
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
