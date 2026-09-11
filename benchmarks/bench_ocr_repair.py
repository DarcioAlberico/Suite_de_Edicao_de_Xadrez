"""Experiment I of ``bench_llm.py``: does ``repair_ocr_region`` repair anything?

F11 cycles 1 and 2 left one task unmeasured -- the level-4 transcription the
cascade falls back to when every OCR engine scored below the bar. This module
measures it the way the other four were measured: real text, exact truth,
the production code path, and a number that decides.

**What is measured.** A region image, the cascade's own low-confidence read
of it, and the model's transcription given both. Three arms:

- ``tesseract``  -- the cascade as it runs on this machine (Tesseract 5 is the
  only installed engine; levels 2 and 3 are not installed, see F5).
- ``llm_hint``   -- ``repair_ocr_region(image, tesseract_text)``, the
  production call.
- ``llm_blind``  -- the same call with an empty hint, to see whether the hint
  helps or anchors the model to Tesseract's mistakes.

**What decides.** In production the model is only consulted on regions the
cascade *rejected*, so the numbers that matter are on that subset:
``moves_fixed`` against ``moves_broken`` -- moves Tesseract had wrong that the
model got right, against moves Tesseract had right that the model then
broke -- and the net CER. A model that lowers CER by polishing prose while
breaking notation is a net loss in a chess book, so both are reported, and
``moves_invented`` (move-shaped tokens in the answer that are on no page)
is reported beside them, because cycle 2 showed invention is this model's
failure mode.

**Two strata, named on every number** (CORPUS.md rule 2):

- ``real``  -- regions of born-digital PDFs whose ink and text layer were
  verified to agree (``corpus/derived/build_ocr_regions.py``). Few, because
  nearly every born-digital chess book in the corpus uses a figurine font.
- ``synth`` -- paragraphs of those books typeset by this module with an
  ordinary text font (``build_ocr_synth.py``). Exact by construction; not a
  scanned page.

**Degradation.** Each region is rendered at 300 dpi and degraded to one of
three levels chosen by position, so every level sees both strata and every
language: D1 clean scan (200 dpi, JPEG), D2 noisy scan (150 dpi, blur,
noise, skew), D3 historical (110 dpi, faded ink, heavier blur and noise). A
fourth level, D4, is unreadable by construction and is a control: the right
answer is an empty string with confidence 0, and every confident
transcription of it is a hallucination counted as such.

No image bytes are written anywhere. The corpus is copyrighted (CORPUS.md).
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = REPO_ROOT / "benchmarks" / "corpus" / "derived"
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(DERIVED_DIR) not in sys.path:
    sys.path.insert(0, str(DERIVED_DIR))

from build_ocr_regions import (  # noqa: E402  - scoring must match the harvest
    LANG_TESS,
    PDF_DIR,
    cer,
    move_tokens,
    normalise,
)

from caissa.llm.guardrails import guarded_json_call  # noqa: E402
from caissa.llm.prompts import load_prompt  # noqa: E402
from caissa.llm.tasks import (  # noqa: E402
    _OCR_LENGTH_FACTOR,
    _OCR_LENGTH_FLOOR,
    _OCR_MIN_CONFIDENCE,
    _OCR_SCHEMA,
    repair_ocr_region,
)
from caissa.ocr.arbiter import Arbiter, RegionTask  # noqa: E402
from caissa.ocr.engines.tesseract import TesseractEngine  # noqa: E402
from caissa.ocr.types import RegionKind  # noqa: E402

OCR_REGIONS_JSONL = DERIVED_DIR / "llm_ocr_regions.jsonl"
OCR_SYNTH_JSONL = DERIVED_DIR / "llm_ocr_synth.jsonl"
RENDER_DPI = 300
FONTS_DIR = Path(r"C:\Windows\Fonts")
#: Text fonts for the synthetic stratum, cycled by row. All serif but one, as
#: chess books are.
SYNTH_FONTS = ("times.ttf", "BOOKOS.TTF", "georgia.ttf", "constan.ttf", "calibri.ttf")
SYNTH_POINT_SIZE = 10.5
SYNTH_COLUMN_INCHES = 3.9
#: Regions used for the unreadable control, taken from the front of the list.
ILLEGIBLE_CONTROL = 12
#: Production-path mirror is checked against the real function on this many
#: regions of the first pass.
MIRROR_CHECK = 6

#: dpi, gaussian blur sigma (px at that dpi), noise sigma, skew degrees,
#: JPEG quality, ink fade (0 = black ink, 1 = paper).
DEGRADATIONS: dict[str, dict[str, float]] = {
    "D1_scan_limpo": {"dpi": 200, "blur": 0.0, "noise": 0, "angle": 0.0, "jpeg": 60, "fade": 0.0},
    "D2_scan_ruidoso": {
        "dpi": 150, "blur": 0.9, "noise": 12, "angle": 0.6, "jpeg": 45, "fade": 0.15,
    },
    "D3_historico": {
        "dpi": 110, "blur": 1.2, "noise": 18, "angle": -1.0, "jpeg": 35, "fade": 0.35,
    },
    "D4_ilegivel": {"dpi": 45, "blur": 2.5, "noise": 25, "angle": 0.0, "jpeg": 30, "fade": 0.4},
}
MEASURED_LEVELS = ("D1_scan_limpo", "D2_scan_ruidoso", "D3_historico")


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #


@dataclass
class Region:
    """One measured item: truth, its 300-dpi render, and where it came from."""

    key: str
    stratum: str
    lang: str
    book: str
    truth: str
    gray: np.ndarray
    level: str = ""
    tess_text: str = ""
    tess_score: float = 0.0
    tess_rejected: bool = False
    image_png: bytes = b""
    degraded_shape: tuple[int, int] = (0, 0)
    extra: dict[str, Any] = field(default_factory=dict)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _render_real(rows: list[dict[str, Any]]) -> list[Region]:
    """Render the verified regions from their PDFs at 300 dpi."""
    import fitz

    by_book: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_book.setdefault(row["book"], []).append(row)
    regions: list[Region] = []
    for book, items in by_book.items():
        path = next((p for p in sorted(PDF_DIR.glob("*.pdf")) if p.stem[:50] == book), None)
        if path is None:
            print(f"  ! PDF ausente para {book!r}; estrato real perde {len(items)} regioes")
            continue
        doc = fitz.open(path)
        try:
            for ordinal, row in enumerate(items):
                page = doc[row["page_index"]]
                rect = fitz.Rect(*row["clip"])
                pix = page.get_pixmap(
                    clip=rect, dpi=RENDER_DPI, colorspace=fitz.csGRAY, alpha=False
                )
                gray = np.frombuffer(pix.samples, dtype=np.uint8)
                gray = gray.reshape(pix.height, pix.width).copy()
                regions.append(
                    Region(
                        key=f"real:{book[:24]}:{row['page_index']}:{ordinal}",
                        stratum="real",
                        lang=row["lang"],
                        book=book,
                        truth=row["truth"],
                        gray=gray,
                    )
                )
        finally:
            doc.close()
    return regions


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if font.getlength(candidate) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _render_synth(text: str, font_name: str) -> np.ndarray:
    """Typeset a paragraph as a 300-dpi grayscale block, book-column width."""
    size = round(SYNTH_POINT_SIZE * RENDER_DPI / 72)
    font = ImageFont.truetype(str(FONTS_DIR / font_name), size)
    column = int(SYNTH_COLUMN_INCHES * RENDER_DPI)
    lines = _wrap(text, font, column)
    leading = int(size * 1.25)
    margin = 24
    height = margin * 2 + leading * len(lines)
    canvas = Image.new("L", (column + margin * 2, height), 255)
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        draw.text((margin, margin + index * leading), line, font=font, fill=0)
    return np.asarray(canvas, dtype=np.uint8)


def load_regions(limit: int) -> list[Region]:
    """Both strata, interleaved so any prefix is a mixed sample."""
    real = _render_real(_read_jsonl(OCR_REGIONS_JSONL))
    synth: list[Region] = []
    for index, row in enumerate(_read_jsonl(OCR_SYNTH_JSONL)):
        font_name = SYNTH_FONTS[index % len(SYNTH_FONTS)]
        synth.append(
            Region(
                key=f"synth:{row['book'][:24]}:{row['page_index']}:{index}",
                stratum="synth",
                lang=row["lang"],
                book=row["book"],
                truth=row["text"],
                gray=_render_synth(row["text"], font_name),
                extra={"font": font_name},
            )
        )
    merged: list[Region] = []
    for pair in zip(real, synth, strict=False):
        merged.extend(pair)
    longer = real if len(real) > len(synth) else synth
    merged.extend(longer[min(len(real), len(synth)):])
    return merged[:limit] if limit else merged


# --------------------------------------------------------------------------- #
# Degradation
# --------------------------------------------------------------------------- #


def degrade(gray: np.ndarray, spec: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    """Turn a 300-dpi render into a scan of the given quality."""
    scale = spec["dpi"] / RENDER_DPI
    out = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if spec["fade"]:
        out = (255 - (255 - out.astype(np.float32)) * (1.0 - spec["fade"])).astype(np.uint8)
    if spec["angle"]:
        h, w = out.shape
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), spec["angle"], 1.0)
        out = cv2.warpAffine(out, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
    if spec["blur"]:
        out = cv2.GaussianBlur(out, (0, 0), spec["blur"])
    if spec["noise"]:
        noise = rng.normal(0.0, spec["noise"], out.shape).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    ok, encoded = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, int(spec["jpeg"])])
    if ok:
        out = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    return out


def png_bytes(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    return encoded.tobytes() if ok else b""


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _multiset_and(a: list[str], b: list[str]) -> Counter[str]:
    return Counter(a) & Counter(b)


def score_text(truth: str, hypothesis: str | None) -> dict[str, Any]:
    """CER plus move accounting for one answer. ``None`` means abstained."""
    if hypothesis is None:
        return {"answered": False}
    truth_moves = move_tokens(truth)
    got = move_tokens(hypothesis)
    kept = sum((_multiset_and(truth_moves, got)).values())
    return {
        "answered": True,
        "cer": cer(truth, hypothesis),
        "moves_truth": len(truth_moves),
        "moves_kept": kept,
        "moves_missing": len(truth_moves) - kept,
        "moves_invented": len(got) - kept,
        "length_ratio": len(normalise(hypothesis)) / max(1, len(normalise(truth))),
    }


def moves_fixed_and_broken(truth: str, before: str, after: str) -> tuple[int, int]:
    """Moves ``after`` got right that ``before`` had wrong, and the reverse."""
    truth_moves = Counter(move_tokens(truth))
    right_before = truth_moves & Counter(move_tokens(before))
    right_after = truth_moves & Counter(move_tokens(after))
    fixed = sum((right_after - right_before).values())
    broken = sum((right_before - right_after).values())
    return fixed, broken


def _p(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(q * (len(ordered) - 1)))
    return ordered[index]


def summarise(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-region scores of one arm over one subset."""
    answered = [item for item in items if item.get("answered")]
    cers = [item["cer"] for item in answered]
    truth_moves = sum(item["moves_truth"] for item in answered)
    return {
        "n": len(items),
        "answered": len(answered),
        "abstention_rate": round(1 - len(answered) / len(items), 4) if items else 0.0,
        "cer_median": round(statistics.median(cers), 4) if cers else None,
        "cer_p90": round(_p(cers, 0.9), 4) if cers else None,
        "cer_mean": round(statistics.fmean(cers), 4) if cers else None,
        "moves_truth": truth_moves,
        "moves_kept_rate": (
            round(sum(item["moves_kept"] for item in answered) / truth_moves, 4)
            if truth_moves else None
        ),
        "moves_invented": sum(item["moves_invented"] for item in answered),
    }


# --------------------------------------------------------------------------- #
# The production path, with the confidence exposed
# --------------------------------------------------------------------------- #


def repair_raw(
    runtime: Any, image: bytes, ocr_text: str, language: str, seed: int
) -> tuple[str, float, float, str]:
    """The same guarded call ``repair_ocr_region`` makes, before its gates.

    Returns ``(text, confidence, latency_ms, decision)``. The gates are
    re-applied by :func:`gate`, and :func:`experiment_i` checks that mirror
    against the real function on a sample, so calibration can be measured
    without a second model call per region.
    """
    template = load_prompt("repair_ocr_region")
    outcome = guarded_json_call(
        runtime,
        template,
        _OCR_SCHEMA,
        {"language": language, "ocr_text": ocr_text.strip() or "(vazio)"},
        task="repair_ocr_region",
        images=(image,),
        timeout_s=90.0,
        seed=seed,
    )
    if not outcome.ok or outcome.payload is None:
        return "", 0.0, outcome.latency_ms, outcome.decision
    text = str(outcome.payload.get("text") or "").strip()
    confidence = float(outcome.payload.get("confidence") or 0.0)
    return text, confidence, outcome.latency_ms, outcome.decision


def gate(text: str, confidence: float, ocr_text: str) -> str | None:
    """Mirror of the acceptance rules in :func:`caissa.llm.tasks.repair_ocr_region`."""
    if not text or confidence < _OCR_MIN_CONFIDENCE:
        return None
    ceiling = max(_OCR_LENGTH_FLOOR, int(len(ocr_text.strip()) * _OCR_LENGTH_FACTOR))
    if len(text) > ceiling:
        return None
    return text


# --------------------------------------------------------------------------- #
# The experiment
# --------------------------------------------------------------------------- #


def _run_tesseract(regions: list[Region], rng: np.random.Generator) -> None:
    """Degrade every region and record what the cascade makes of it."""
    arbiter = Arbiter([TesseractEngine()])
    threshold = arbiter.config.threshold_for(1)
    for index, region in enumerate(regions):
        region.level = MEASURED_LEVELS[index % len(MEASURED_LEVELS)]
        degraded = degrade(region.gray, DEGRADATIONS[region.level], rng)
        region.image_png = png_bytes(degraded)
        region.degraded_shape = degraded.shape
        outcome = arbiter.run(
            RegionTask(
                image=degraded,
                lang=LANG_TESS[region.lang],
                region_kind=RegionKind.PARAGRAPH,
                region_id=region.key,
            )
        )
        region.tess_text = outcome.result.text
        score = outcome.winner.total if outcome.winner else 0.0
        region.tess_score = round(score, 4)
        region.tess_rejected = score < threshold


def _subset_report(
    regions: list[Region],
    per_region: dict[str, dict[str, dict[str, Any]]],
    keys: list[str],
) -> dict[str, Any]:
    """Every arm, plus the production accounting, over the regions in ``keys``."""
    chosen = [r for r in regions if r.key in set(keys)]
    report: dict[str, Any] = {"regions": len(chosen)}
    for arm in ("tesseract", "llm_hint", "llm_blind", "llm_hint_raw", "llm_blind_raw"):
        report[arm] = summarise([per_region[r.key][arm] for r in chosen])
    # Production: the model's answer where it answered, Tesseract's otherwise.
    improved = worsened = unchanged = 0
    fixed_total = broken_total = 0
    net_cers: list[float] = []
    tess_cers: list[float] = []
    for region in chosen:
        tess = per_region[region.key]["tesseract"]
        hint = per_region[region.key]["llm_hint"]
        tess_cers.append(tess["cer"])
        if not hint["answered"]:
            net_cers.append(tess["cer"])
            continue
        net_cers.append(hint["cer"])
        fixed, broken = moves_fixed_and_broken(region.truth, region.tess_text, hint["text"])
        fixed_total += fixed
        broken_total += broken
        if hint["cer"] < tess["cer"] - 1e-9:
            improved += 1
        elif hint["cer"] > tess["cer"] + 1e-9:
            worsened += 1
        else:
            unchanged += 1
    report["production"] = {
        "cer_median_before": round(statistics.median(tess_cers), 4) if tess_cers else None,
        "cer_median_after": round(statistics.median(net_cers), 4) if net_cers else None,
        "cer_mean_before": round(statistics.fmean(tess_cers), 4) if tess_cers else None,
        "cer_mean_after": round(statistics.fmean(net_cers), 4) if net_cers else None,
        "regions_improved": improved,
        "regions_worsened": worsened,
        "regions_unchanged": unchanged,
        "moves_fixed": fixed_total,
        "moves_broken": broken_total,
        "moves_invented": report["llm_hint"]["moves_invented"],
    }
    return report


def experiment_i(
    runtime: Any, repeats: int, limit: int, seed: int, median_of_runs: Any
) -> dict[str, Any]:
    """Measure ``repair_ocr_region`` against exact truth on degraded regions.

    ``median_of_runs`` is ``bench_llm._median_of_runs``, passed in rather than
    imported so this module never imports the script that imports it.
    """
    regions = load_regions(limit)
    print(f"\n=== I. repair_ocr_region em {len(regions)} regioes (real + sintetico) ===")
    if not regions:
        return {
            "error": f"{OCR_REGIONS_JSONL} / {OCR_SYNTH_JSONL} ausentes; rode os build_ocr_*.py"
        }

    rng = np.random.default_rng(seed)
    started = time.perf_counter()
    _run_tesseract(regions, rng)
    tess_s = time.perf_counter() - started
    rejected = [r for r in regions if r.tess_rejected]
    print(
        f"  tesseract: {len(rejected)}/{len(regions)} regioes rejeitadas pelo arbitro "
        f"(escore < {Arbiter([TesseractEngine()]).config.threshold_for(1)}), {tess_s:.0f}s"
    )

    result: dict[str, Any] = {
        "regions": len(regions),
        "by_stratum": dict(Counter(r.stratum for r in regions)),
        "by_language": dict(Counter(r.lang for r in regions)),
        "by_level": dict(Counter(r.level for r in regions)),
        "tesseract_rejected": len(rejected),
        "tesseract_rejected_by_level": dict(Counter(r.level for r in rejected)),
        "degradations": {k: DEGRADATIONS[k] for k in MEASURED_LEVELS},
        "ground_truth": [str(OCR_REGIONS_JSONL), str(OCR_SYNTH_JSONL)],
        "runs": repeats,
    }

    runs: list[dict[str, Any]] = []
    latencies: list[float] = []
    calibration_samples: list[tuple[float, float]] = []
    mirror_mismatches = 0
    mirror_details: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    for attempt in range(repeats):
        per_region: dict[str, dict[str, dict[str, Any]]] = {}
        for index, region in enumerate(regions):
            scores: dict[str, dict[str, Any]] = {
                "tesseract": score_text(region.truth, region.tess_text),
            }
            for arm, hint in (("llm_hint", region.tess_text), ("llm_blind", "")):
                text, confidence, latency, decision = repair_raw(
                    runtime, region.image_png, hint, region.lang, attempt
                )
                latencies.append(latency)
                accepted = gate(text, confidence, hint)
                entry = score_text(region.truth, accepted)
                entry.update(
                    {"text": accepted or "", "confidence": confidence, "decision": decision}
                )
                # The ungated answer, so the gates themselves can be judged.
                scores[f"{arm}_raw"] = score_text(region.truth, text or None)
                if arm == "llm_hint" and text:
                    calibration_samples.append((confidence, scores["llm_hint_raw"]["cer"]))
                scores[arm] = entry
            if attempt == 0 and index < MIRROR_CHECK:
                real = repair_ocr_region(
                    region.image_png, region.tess_text, region.lang, runtime=runtime, seed=attempt
                )
                if (real or "") != (scores["llm_hint"]["text"] or ""):
                    mirror_mismatches += 1
                    mirror_details.append(
                        {
                            "key": region.key,
                            "mirror_answered": scores["llm_hint"]["answered"],
                            "production_answered": real is not None,
                            "mirror_confidence": scores["llm_hint"]["confidence"],
                            "same_text_prefix": (
                                (real or "")[:40] == (scores["llm_hint"]["text"] or "")[:40]
                            ),
                        }
                    )
            per_region[region.key] = scores
            if attempt == 0 and len(examples) < 10 and scores["llm_hint"]["answered"]:
                fixed, broken = moves_fixed_and_broken(
                    region.truth, region.tess_text, scores["llm_hint"]["text"]
                )
                if fixed or broken or scores["llm_hint"]["moves_invented"]:
                    examples.append(
                        {
                            "key": region.key,
                            "level": region.level,
                            "lang": region.lang,
                            "tess_score": region.tess_score,
                            "cer_tesseract": round(scores["tesseract"]["cer"], 3),
                            "cer_llm": round(scores["llm_hint"]["cer"], 3),
                            "moves_fixed": fixed,
                            "moves_broken": broken,
                            "moves_invented": scores["llm_hint"]["moves_invented"],
                            "truth_moves": move_tokens(region.truth)[:12],
                            "tess_moves": move_tokens(region.tess_text)[:12],
                            "llm_moves": move_tokens(scores["llm_hint"]["text"])[:12],
                        }
                    )
            if (index + 1) % 10 == 0 or index + 1 == len(regions):
                elapsed = time.perf_counter() - started
                print(f"  passada {attempt + 1}: {index + 1}/{len(regions)}  ({elapsed:.0f}s)")

        run: dict[str, Any] = {
            "all": _subset_report(regions, per_region, [r.key for r in regions]),
            "rejected_only": _subset_report(regions, per_region, [r.key for r in rejected]),
        }
        for stratum in sorted({r.stratum for r in regions}):
            run[f"stratum_{stratum}"] = _subset_report(
                regions, per_region, [r.key for r in regions if r.stratum == stratum]
            )
        for level in MEASURED_LEVELS:
            run[level] = _subset_report(
                regions, per_region, [r.key for r in regions if r.level == level]
            )
        for lang in sorted({r.lang for r in regions}):
            run[f"lang_{lang}"] = _subset_report(
                regions, per_region, [r.key for r in regions if r.lang == lang]
            )
        runs.append(run)
        if attempt == 0:
            # One line per region, first pass, so the critic can disagree
            # region by region. Text is not written -- only scores.
            per_region_rows = []
            for region in regions:
                scores = per_region[region.key]
                hint = scores["llm_hint"]
                fixed, broken = (
                    moves_fixed_and_broken(region.truth, region.tess_text, hint["text"])
                    if hint["answered"] else (0, 0)
                )
                per_region_rows.append(
                    {
                        "key": region.key,
                        "stratum": region.stratum,
                        "lang": region.lang,
                        "level": region.level,
                        "font": region.extra.get("font"),
                        "truth_chars": len(region.truth),
                        "moves_truth": scores["tesseract"]["moves_truth"],
                        "tess_score": region.tess_score,
                        "tess_rejected": region.tess_rejected,
                        "tess_cer": round(scores["tesseract"]["cer"], 4),
                        "tess_moves_kept": scores["tesseract"]["moves_kept"],
                        "tess_moves_invented": scores["tesseract"]["moves_invented"],
                        "llm_answered": hint["answered"],
                        "llm_confidence": hint["confidence"],
                        "llm_cer": round(hint["cer"], 4) if hint["answered"] else None,
                        "llm_moves_kept": hint.get("moves_kept"),
                        "llm_moves_invented": hint.get("moves_invented"),
                        "llm_length_ratio": (
                            round(hint["length_ratio"], 3) if hint["answered"] else None
                        ),
                        "moves_fixed": fixed,
                        "moves_broken": broken,
                        "blind_raw_cer": (
                            round(scores["llm_blind_raw"]["cer"], 4)
                            if scores["llm_blind_raw"]["answered"] else None
                        ),
                    }
                )
            result["per_region_first_pass"] = per_region_rows
        production = run["rejected_only"]["production"]
        print(
            f"  passada {attempt + 1} (rejeitadas): "
            f"CER mediana {production['cer_median_before']} -> "
            f"{production['cer_median_after']}, lances consertados {production['moves_fixed']}, "
            f"quebrados {production['moves_broken']}, inventados {production['moves_invented']}"
        )

    merged = median_of_runs(runs)
    merged["per_run_rejected_production"] = [run["rejected_only"]["production"] for run in runs]
    result.update(merged)
    result["median_latency_ms"] = round(statistics.median(latencies), 1) if latencies else None
    result["gate_mirror_mismatches"] = mirror_mismatches
    result["gate_mirror_details"] = mirror_details
    result["calibration"] = _calibration(calibration_samples)
    result["illegible_control"] = _illegible_control(regions, runtime, rng, repeats)
    result["examples"] = examples
    result["notes"] = [
        "tesseract e o unico motor instalado; niveis 2-3 (RapidOCR/Paddle/Surya) ausentes",
        "estrato real: so livros nativos digitais cuja camada de texto bate com a tinta",
        "estrato sintetico: paragrafos reais tipografados por este script, nao paginas escaneadas",
        "CER sobre texto normalizado (NFKC, hifen/aspas unificados, 0-0 -> O-O, espacos)",
    ]
    return result


def _calibration(samples: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Does the model's confidence say anything about its error?"""
    bins = ((0.0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.9), (0.9, 1.01))
    table: list[dict[str, Any]] = []
    for low, high in bins:
        cers = [c for conf, c in samples if low <= conf < high]
        table.append(
            {
                "confidence": f"[{low:.1f}, {min(high, 1.0):.1f}{')' if high < 1.01 else ']'}",
                "n": len(cers),
                "cer_median": round(statistics.median(cers), 4) if cers else None,
                "cer_p90": round(_p(cers, 0.9), 4) if cers else None,
            }
        )
    return table


def _illegible_control(
    regions: list[Region], runtime: Any, rng: np.random.Generator, repeats: int
) -> dict[str, Any]:
    """D4: nothing is readable. Any confident transcription is a hallucination."""
    chosen = regions[:ILLEGIBLE_CONTROL]
    if not chosen:
        return {}
    arbiter = Arbiter([TesseractEngine()])
    answered = hallucinated_moves = 0
    lengths: list[int] = []
    confidences: list[float] = []
    tess_rejected = 0
    for region in chosen:
        degraded = degrade(region.gray, DEGRADATIONS["D4_ilegivel"], rng)
        image = png_bytes(degraded)
        outcome = arbiter.run(
            RegionTask(
                image=degraded, lang=LANG_TESS[region.lang], region_kind=RegionKind.PARAGRAPH
            )
        )
        hint = outcome.result.text
        score = outcome.winner.total if outcome.winner else 0.0
        tess_rejected += score < arbiter.config.threshold_for(1)
        for attempt in range(repeats):
            text, confidence, _, _ = repair_raw(runtime, image, hint, region.lang, attempt)
            confidences.append(confidence)
            accepted = gate(text, confidence, hint)
            if accepted:
                answered += 1
                lengths.append(len(accepted))
                hallucinated_moves += len(move_tokens(accepted))
    calls = len(chosen) * repeats
    return {
        "regions": len(chosen),
        "calls": calls,
        "tesseract_rejected": tess_rejected,
        "accepted_by_gate": answered,
        "hallucination_rate": round(answered / calls, 4) if calls else None,
        "median_confidence": round(statistics.median(confidences), 3) if confidences else None,
        "median_length_of_accepted": statistics.median(lengths) if lengths else 0,
        "move_shaped_tokens_hallucinated": hallucinated_moves,
    }
