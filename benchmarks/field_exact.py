"""``field_exact`` -- the last recognition metric below target -- measured properly.

``benchmarks/validate_detection.py`` already guards recall and precision.  This one is
pointed at the number that did not move in any detection variant: **of the diagrams that
reach the PGN, how many are right**, which ``field_eval.FieldReport`` defines as
``exported_exact / exported_comparable``.

Three things it does that the detection harness does not:

1. **Both rulers.**  ``--corrections`` applies ``benchmarks/field_corrections.json``, the
   overlay of *proven* annotation errors in the field set, and the run reports the metric
   as-annotated and corrected side by side.  Nothing is written to the field set; the
   overlay is applied in memory, and every entry in it carries its evidence.  A corrected
   number published without the raw one beside it is a number nobody can check.
2. **Per stratum.**  ``docs/quality/CORPUS.md`` 5.2 and 5.4: a mean hides the worst
   stratum.  Every run prints per ``regime`` and per book.
3. **Median of >= 3.**  ``docs/quality/CORPUS.md`` 5.1.  Recognition is deterministic here,
   so the run *asserts* that the counts are identical across repetitions and fails loudly
   if they are not -- a metric that moves between identical runs is a defect, not noise --
   and takes the median of the clock.

Variants::

    baseline           trunk detection as it ships -- since OCR_UI cycle 2 step A1 this
                       is the recall pack (`config.DEFAULT_RECALL`), so it equals recall-pack
    raw                the detector with every recovery off (the pre-A1 baseline)
    recall-pack        the three recoveries of caissa.vision.detect.recall (what ships)
    recall-pack+refine recall-pack plus RecognitionOptions.refine_detected_boards

Usage::

    .venv/Scripts/python.exe benchmarks/field_exact.py --variant recall-pack --runs 3 --corrections
"""

from __future__ import annotations

import argparse
import contextlib
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

CORRECTIONS = REPO_ROOT / "benchmarks" / "field_corrections.json"

INVARIANT_KEYS = (
    "annotated", "detected", "matched", "false_positives", "comparable", "exact",
    "exported", "exported_comparable", "exported_exact", "detection_recall",
    "detection_precision", "field_exact",
)
"""Counts that cannot legitimately differ between two identical runs."""


def apply_corrections(pages: list[Any], path: Path) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return a copy of ``pages`` with the overlay applied, and the entries that hit.

    An entry that does not match, or whose ``from`` no longer matches the file, raises:
    an overlay that silently stops applying is worse than no overlay, because the number it
    produces still looks corrected.
    """
    import dataclasses

    from chess_diagram_ocr.field_eval import AnnotatedDiagram

    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("corrections", [])
    by_key = {(entry["pdf"], int(entry["page"]), int(entry["diagram"])): entry for entry in entries}
    hit: list[dict[str, Any]] = []

    out = []
    for page in pages:
        diagrams = list(page.diagrams)
        changed = False
        for index, diagram in enumerate(diagrams):
            entry = by_key.get((page.pdf, page.page, index))
            if entry is None:
                continue
            if diagram.placement != entry["from"]:
                raise SystemExit(
                    f"correcao nao aplica: {entry['pdf']} p{entry['page']} d{entry['diagram']} "
                    f"tem {diagram.placement!r}, a correcao esperava {entry['from']!r}. "
                    "O conjunto de campo mudou; reveja a correcao antes de medir."
                )
            diagrams[index] = AnnotatedDiagram(
                bbox=diagram.bbox,
                placement=entry["to"],
                side_to_move=diagram.side_to_move,
                note=(diagram.note + " | " if diagram.note else "") + "corrigido por benchmarks/field_corrections.json",
            )
            changed = True
            hit.append(entry)
        out.append(dataclasses.replace(page, diagrams=tuple(diagrams)) if changed else page)

    missed = [key for key in by_key if key not in {(e["pdf"], int(e["page"]), int(e["diagram"])) for e in hit}]
    if missed:
        raise SystemExit(f"correcoes que nao encontraram a pagina anotada: {missed}")
    return out, hit


def _variant(name: str) -> Any:
    from caissa.vision.detect.recall import recall_pack

    if name == "baseline":
        return contextlib.nullcontext()
    if name == "raw":
        return recall_pack(scales=(), rescue_squares=False, embedded_floor=None)
    return recall_pack()


def _slice(report: Any) -> dict[str, Any]:
    data = report.as_dict()
    keep = (
        "pages", "annotated", "detected", "matched", "false_positives", "detection_recall",
        "detection_precision", "legal", "above_gate", "exported", "export_rate", "comparable",
        "exact", "conditional_exact", "exported_comparable", "exported_exact", "exported_wrong",
        "field_exact", "repaired_squares", "repaired_diagrams", "next_move_checked",
        "next_move_replayed", "next_move_repaired", "next_move_repaired_exact",
        "next_move_repaired_wrong", "next_move_ambiguous", "colour_repaired",
        "colour_repaired_squares", "colour_repaired_exact", "colour_repaired_wrong",
        "seconds", "seconds_per_diagram",
    )
    return {key: data[key] for key in keep if key in data}


def _profile_calibrator(path: Path | None, sabotage: str = "") -> Any:
    """A colour calibrator taken from one profile file for every PDF (C5 measurement), or the
    default resolver (the profile stored per book) when no path is given.  ``cor_trocada``
    swaps the white and black samples of whatever calibrator is resolved."""
    from chess_diagram_ocr.cor_por_livro import CalibradorDeCor, calibrador_do_livro

    fixed = None
    if path is not None:
        import json

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        fixed = CalibradorDeCor.from_dict(data.get("colour") if "colour" in data else data)

    def resolve(pdf_source: Any) -> Any:
        calibrador = fixed if fixed is not None else calibrador_do_livro(pdf_source)
        if calibrador is not None and sabotage == "cor_trocada":
            return CalibradorDeCor(brancas=calibrador.pretas, pretas=calibrador.brancas,
                                   diagramas=calibrador.diagramas, medida=calibrador.medida)
        return calibrador

    return resolve if (path is not None or sabotage == "cor_trocada") else None


@contextlib.contextmanager
def _sabotage(name: str):
    """C11 sabotage ``lance_vizinho``: every diagram of a page gets the *next* diagram's line
    of moves (cyclic); a page with one diagram keeps its own.  A next-move signal that still
    repairs under this feeds on coincidence, and the gate must say so."""
    if name != "lance_vizinho":
        yield
        return
    import dataclasses

    from chess_diagram_ocr import service as trunk_service

    original = trunk_service.contexts_for_pdf_page

    def rotated(*args: Any, **kwargs: Any) -> Any:
        contexts = list(original(*args, **kwargs))
        if len(contexts) < 2:
            return contexts
        lines = [getattr(c, "first_moves_text", "") if c is not None else "" for c in contexts]
        numbers = [getattr(c, "first_move_number", None) if c is not None else None for c in contexts]
        out = []
        for index, context in enumerate(contexts):
            source = (index + 1) % len(contexts)
            if context is None:
                out.append(None)
                continue
            out.append(dataclasses.replace(
                context, first_moves_text=lines[source], first_move_number=numbers[source]))
        return out

    trunk_service.contexts_for_pdf_page = rotated
    try:
        yield
    finally:
        trunk_service.contexts_for_pdf_page = original


def run_once(pages: list[Any], options: Any, variant: str, pdf_dir: Path,
             sabotage: str = "") -> tuple[dict[str, Any], Any]:
    from chess_diagram_ocr.field_eval import evaluate_field

    started = time.perf_counter()
    with _variant(variant), _sabotage(sabotage):
        report = evaluate_field(pages, options=options, pdf_dir=pdf_dir)
    elapsed = time.perf_counter() - started
    row = _slice(report)
    row["wall_s"] = round(elapsed, 3)
    return row, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", action="append", default=[],
                        choices=("baseline", "raw", "recall-pack", "recall-pack+refine"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--max-boards", type=int, default=12)
    parser.add_argument("--model", type=Path, default=None, help="Checkpoint under test; default is production.")
    parser.add_argument("--corrections", action="store_true", help="Also report with the proven-error overlay.")
    parser.add_argument("--tag", default="")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "reports")
    parser.add_argument("--sabotar", default="", choices=("", "sem_lance", "lance_vizinho", "sem_cor",
                                                            "cor_trocada", "sem_evidencia"),
                        help="C11: sem_lance desliga o lance seguinte (RecognitionOptions.next_move); "
                             "lance_vizinho dá a cada diagrama a linha de lances do diagrama vizinho. "
                             "C5: sem_cor desliga o calibrador de cor; cor_trocada troca as amostras "
                             "brancas pelas pretas no perfil do livro (os protótipos embaralhados). "
                             "sem_evidencia desliga os dois (o antes da fase 3).")
    parser.add_argument("--perfil", type=Path, default=None,
                        help="C5: um perfil de livro (JSON de caissa.ocr.book_profile) a usar em todo "
                             "PDF da medição, em vez do perfil gravado por livro.")
    args = parser.parse_args(argv)
    variants = args.variant or ["recall-pack"]
    if args.runs < 3:
        raise SystemExit("docs/quality/CORPUS.md 5.1: mediana de no minimo 3 execucoes. Uma execucao nao e medicao.")

    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH
    from chess_diagram_ocr.field_eval import load_field_set
    from chess_diagram_ocr.service import RecognitionOptions

    root = cvoff_root()
    raw_pages = load_field_set(root / "data" / "field_set.jsonl")
    model = args.model or Path(DEFAULT_MODEL_PATH)
    if not Path(model).is_file():
        model = root / "models" / "piece_classifier.pt"

    rulers: list[tuple[str, list[Any], list[dict[str, Any]]]] = [("as-annotated", raw_pages, [])]
    if args.corrections:
        fixed, hit = apply_corrections(raw_pages, CORRECTIONS)
        rulers.append(("corrected", fixed, hit))

    results: list[dict[str, Any]] = []
    for variant in variants:
        refine = variant.endswith("+refine")
        detection = "recall-pack" if refine else variant
        options = RecognitionOptions(
            model_path=Path(model), max_boards=args.max_boards, dpi=args.dpi,
            refine_detected_boards=refine,
            next_move=args.sabotar not in ("sem_lance", "sem_evidencia"),
            colour=args.sabotar not in ("sem_cor", "sem_evidencia"),
            colour_calibrator=_profile_calibrator(args.perfil, args.sabotar),
        )
        for ruler, pages, hit in rulers:
            runs = []
            reports = []
            for _ in range(args.runs):
                row, report = run_once(pages, options, detection, root / "PDF", args.sabotar)
                runs.append(row)
                reports.append(report)
            drift = {key for row in runs for key in INVARIANT_KEYS if row[key] != runs[0][key]}
            if drift:
                raise SystemExit(
                    f"{variant}/{ruler}: {sorted(drift)} mudou entre execucoes identicas. "
                    "O reconhecimento nao tem aleatoriedade; isto e defeito, nao ruido."
                )
            chosen = dict(runs[len(runs) // 2])
            chosen["wall_s"] = round(statistics.median(row["wall_s"] for row in runs), 3)
            chosen["wall_s_all"] = [row["wall_s"] for row in runs]
            chosen["runs"] = args.runs
            chosen["variant"] = variant
            chosen["sabotage"] = args.sabotar
            chosen["ruler"] = ruler
            chosen["model"] = str(model)
            chosen["corrections_applied"] = [
                f"{e['pdf']} p{e['page']} d{e['diagram']}: {', '.join(e['squares'])}" for e in hit
            ]
            report = reports[0]
            chosen["per_regime"] = {name: _slice(part) for name, part in sorted(report.per_regime.items())}
            chosen["per_book"] = {name: _slice(part) for name, part in sorted(report.per_book.items())}
            chosen["wrong"] = list(report.wrong)
            results.append(chosen)

    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    destination = args.out / f"field_exact_{datetime.now().strftime('%Y%m%d_%H%M%S')}{tag}.json"
    destination.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "results": results}, indent=2,
                   ensure_ascii=False),
        encoding="utf-8",
    )

    header = f"{'variant':<20}{'ruler':<14}{'recall':>8}{'prec':>7}{'exp':>6}{'cmp':>5}{'ok':>5}{'field_exact':>13}{'s/diag':>9}"
    print("\n" + header)
    print("-" * len(header))
    for row in results:
        print(f"{row['variant']:<20}{row['ruler']:<14}{row['detection_recall']:>8.4f}{row['detection_precision']:>7.4f}"
              f"{row['exported']:>6}{row['exported_comparable']:>5}{row['exported_exact']:>5}"
              f"{row['field_exact']:>13.4f}{row['seconds_per_diagram']:>9.4f}")

    print("\nper stratum (regime), last variant/ruler shown above:")
    last = results[-1]
    for name, part in last["per_regime"].items():
        print(f"  {name:<20} annotated {part['annotated']:>3}  matched {part['matched']:>3}"
              f"  exported_comparable {part['exported_comparable']:>3}  exact {part['exported_exact']:>3}"
              f"  field_exact {part['field_exact']:.4f}")
    if last["wrong"]:
        print("\nexported and wrong:")
        for item in last["wrong"]:
            print("  " + item.replace("\n", "\n  "))
    print(f"\nreport -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
