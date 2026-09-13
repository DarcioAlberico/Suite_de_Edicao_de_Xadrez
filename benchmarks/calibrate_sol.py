"""Fit the per-engine confidence calibration (Sol §SOL-4) on the calibration partition.

For every item of the **calibration** partition (never the blind one, and
not the development one either — the thresholds are tuned there) and every
stratum it declares, the raster engines are run on the rendered image and
each recognised word is aligned to the truth.  The pairs ``(raw confidence,
correct)`` are grouped by facet — engine, language, script, resolution
bucket, region kind — and an isotonic table is fitted per group with enough
samples.  The result is written to ``src/caissa/ocr/data/calibration.json``
(the arbiter loads it as the packaged set) and summarised in
``docs/quality/sol/calibration.md`` with ECE and Brier before and after.

    python benchmarks/calibrate_sol.py

Nothing here touches thresholds; that is what keeps the calibration partition
exclusive (Sol §SOL-4, "usar partição exclusiva de calibração").
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "benchmarks") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from bench_sol import MANIFEST  # noqa: E402
from sol_corpus import render, tesseract_lang  # noqa: E402

from caissa.ocr.calibration import (  # noqa: E402
    MIN_SAMPLES,
    CalibrationSet,
    FacetKey,
    fit_isotonic,
    pairs_from_alignment,
)
from caissa.ocr.golden import Partition, items_sorted, load_manifest  # noqa: E402
from caissa.ocr.metrics import normalise  # noqa: E402
from caissa.ocr.types import RegionKind  # noqa: E402

TARGET = REPO_ROOT / "src" / "caissa" / "ocr" / "data" / "calibration.json"
SUMMARY = REPO_ROOT / "docs" / "quality" / "sol" / "calibration.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--out", type=Path, default=TARGET)
    parser.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    args = parser.parse_args()

    from caissa.ocr.engines.registry import default_registry

    manifest = load_manifest(args.manifest)
    items = [i for i in items_sorted(manifest.items)
             if i.partition is Partition.CALIB and not i.is_control]
    engines = [e for e in default_registry().available()
               if not e.capabilities().requires_pdf_page]
    if not engines:
        print("nenhum motor de rasterização disponível")
        return 1

    pairs: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    counted = 0
    for item in items:
        lang = tesseract_lang(item)
        truth_words = normalise(item.truth).split()
        kind = (RegionKind.MOVETEXT if item.genre == "movetext" else RegionKind.PARAGRAPH)
        for stratum in item.strata:
            rendered = render(item, stratum)
            if rendered is None:
                continue
            for engine in engines:
                if not engine.supports_language(lang):
                    continue
                result = engine.recognize(rendered.gray, lang=lang, psm_hint=RegionKind.PAGE)
                aligned = pairs_from_alignment(
                    ((w.text, w.confidence) for w in result.words), truth_words)
                key = FacetKey(engine=engine.name, lang=lang.split("+")[0],
                               script=item.script, dpi=rendered.dpi, kind=str(kind))
                for name in key.candidates():
                    pairs[name].extend(aligned)
                counted += len(aligned)
        print(f"  {item.id[:40]:40s} {counted} palavras")

    fitted = CalibrationSet(
        fitted_at=datetime.now(UTC).isoformat(timespec="seconds"),
        corpus_hash=manifest.content_hash(), partition="calib",
        notes=[f"{len(items)} itens da partição de calibração; "
               f"motores: {', '.join(e.name for e in engines)}"],
    )
    for name, group in sorted(pairs.items()):
        table = fit_isotonic([c for c, _ in group], [ok for _, ok in group],
                             min_samples=args.min_samples)
        if table is not None:
            fitted.tables[name] = table
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(args.out)

    lines = [
        "# Sol · calibração por faceta (SOL-4)", "",
        f"> {fitted.fitted_at} · corpus `{fitted.corpus_hash}` · partição `calib` · "
        f"{counted} palavras alinhadas", "",
        "| chave | n | ECE antes | ECE depois | Brier antes | Brier depois |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for name, table in sorted(fitted.tables.items()):
        lines.append(f"| `{name}` | {table.samples} | {table.ece_before:.4f} | "
                     f"{table.ece_after:.4f} | {table.brier_before:.4f} | "
                     f"{table.brier_after:.4f} |")
    skipped = [n for n in pairs if n not in fitted.tables]
    if skipped:
        lines += ["", f"Sem amostras suficientes (< {args.min_samples}): "
                  + ", ".join(f"`{n}`" for n in sorted(skipped))]
    lines += ["", f"Tabelas em `{args.out.relative_to(REPO_ROOT)}`; recalibrar com "
              "`python benchmarks/calibrate_sol.py`.", ""]
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(fitted.tables)} tabelas -> {args.out}\n{SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
