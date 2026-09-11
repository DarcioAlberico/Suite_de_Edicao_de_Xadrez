"""Does the local LLM actually improve recognition, or does it just cost 6 GB?

This front's value is unproven until measured, so this script is the point of
it. It asks four questions and answers each with numbers from the real corpus:

**A. Can it tell a correct FEN from a subtly wrong one?**
    The decisive experiment. Boards from the held-out ``test`` split of
    ``labels.csv`` are presented twice: once with their true FEN, once with a
    single square corrupted in a way that keeps the position *legal*, so the
    free legality checker in SPEC 6.4 cannot catch it. That isolates what the
    LLM adds beyond what the pipeline already gets for nothing. Reported as
    precision / recall / balanced accuracy / MCC of the "this FEN is wrong"
    signal, against the trivial "always say wrong" baseline -- because a model
    that rejects everything scores 100 % recall while carrying zero
    information.

**B. What does it say about the real review queue?**
    The 27 low-confidence items in ``review_queue.json`` and the audited
    rejects in ``quarantine.csv``. The queue has no ground truth, so this
    reports the verdict distribution and latency and claims nothing about
    accuracy. The quarantine rows do have ground truth -- they are known-bad --
    but every one of them is *illegal*, which the constraint solver already
    catches at zero cost. Both caveats are printed with the numbers.

**C. Does it fit next to the vision pipeline?**
    Peak VRAM with the LLM resident and a vision-sized allocation live, against
    the ADR-0004 cap of 7.0 GiB.

**D. What does it cost per call?**
    Median latency over at least three runs, per task, per CORPUS.md rule 1.

Cycle 2 adds the three *text* tasks that cycle 1 left unmeasured. They are the
ones in the domain the model is actually good at, and each has a decisive
metric of its own:

**E. Does it read a stipulation without inventing one?**
    233 real captions pulled out of the corpus by ``chess_diagram_ocr.pdf_text``
    and labelled by hand (``benchmarks/corpus/derived/llm_captions.jsonl``), in
    six languages. Three arms -- rules only, model only, production
    (rules first, model for the gaps) -- scored for precision, recall and, the
    number that decides shippability, the **abstention rate on captions that
    state no stipulation**. A fabricated stipulation is worse than none.

**F. Does it ever touch a move?**
    92 real annotated paragraphs. Every move token in the output is compared
    with every move token in the input. The bar is zero alterations; anything
    else fails the task outright.

**G. Are generated captions safe?**
    Objective properties only -- no move notation, no invented year or name,
    right language, sane length. Caption *quality* is not objectively
    measurable, and the report says so instead of inventing a score.

Cycle 3 measures the fifth and last task, which cycles 1 and 2 left untouched:

**I. Does last-resort transcription repair anything?**
    Regions with exact ground truth, degraded to three scan qualities, read
    by the installed cascade (Tesseract) and then by ``repair_ocr_region``.
    Scored on the regions the cascade *rejected*, because that is the only
    place production calls the model: moves fixed against moves broken, net
    CER, and an unreadable control where any confident answer is a
    hallucination. Lives in ``bench_ocr_repair.py``.

Usage::

    python benchmarks/bench_llm.py --experiments a,b,c,d --pairs 40
    python benchmarks/bench_llm.py --experiments e,f,g --repeats 3
    python benchmarks/bench_llm.py --experiments a --pairs 100 --json out.json
    python benchmarks/bench_llm.py --experiments i --repeats 3

Nothing here leaves the machine, and no image bytes are written to any report --
the corpus is copyrighted material (CORPUS.md).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import chess  # noqa: E402
from PIL import Image  # noqa: E402

from bench_ocr_repair import experiment_i  # noqa: E402
from caissa.llm.runtime import OllamaRuntime, get_runtime  # noqa: E402
from caissa.llm.tasks import (  # noqa: E402
    _MASKABLE_RE,
    caption_for_diagram,
    extract_stipulation,
    material_summary,
    translate_notation_prose,
    verify_diagram,
)

CORPUS = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro\data")
LABELS_CSV = CORPUS / "labels.csv"
SPLITS_CSV = CORPUS / "splits.csv"
SAMPLES_DIR = CORPUS / "samples"
QUARANTINE_CSV = CORPUS / "quarantine.csv"
ORPHANS_DIR = CORPUS / "orphans"
REVIEW_QUEUE = CORPUS / "review_queue.json"
REPORTS_DIR = REPO_ROOT / "benchmarks" / "reports"
DERIVED_DIR = REPO_ROOT / "benchmarks" / "corpus" / "derived"

#: Hand-labelled captions harvested from the corpus. See F11_REPORT_C2.md 2.
CAPTIONS_JSONL = DERIVED_DIR / "llm_captions.jsonl"

#: Real annotated paragraphs, prose plus moves.
PROSE_JSONL = DERIVED_DIR / "llm_prose.jsonl"

#: Images are downscaled before they reach the model. The vision tower resizes
#: anyway, and 800x800 PNGs make the request payload the dominant cost.
IMAGE_SIDE = 512


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def load_image(path: Path, side: int = IMAGE_SIDE) -> bytes | None:
    """Read and downscale one board image to PNG bytes."""
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            if max(rgb.size) > side:
                rgb = rgb.resize((side, side), Image.LANCZOS)
            buffer = io.BytesIO()
            rgb.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()
    except (OSError, ValueError) as exc:
        print(f"  ! imagem ilegivel {path.name}: {exc}")
        return None


def nvml_used_mib() -> int | None:
    """Total VRAM in use on the device, from nvidia-smi. ``None`` if absent."""
    try:
        out = subprocess.run(  # noqa: S603, S607 - fixed argv, resolved from PATH
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return int(out.stdout.strip().splitlines()[0])
    except (IndexError, ValueError):
        return None


def corrupt_one_square(fen: str, rng: random.Random, *, attempts: int = 60) -> str | None:
    """Change exactly one square, keeping the position legal.

    Legality is the whole point: SPEC 6.4's constraint solver already catches
    illegal readings for free, so an experiment built on illegal corruptions
    would measure nothing the product does not already have. This reproduces the
    residual failure mode -- one square misread into a position that still looks
    like a real game.
    """
    board = chess.Board(fen)
    occupied = [
        square
        for square in chess.SQUARES
        if (piece := board.piece_at(square)) is not None and piece.piece_type != chess.KING
    ]
    if not occupied:
        return None
    empties = [square for square in chess.SQUARES if board.piece_at(square) is None]
    for _ in range(attempts):
        mutated = board.copy()
        square = rng.choice(occupied)
        original = mutated.piece_at(square)
        if original is None:  # pragma: no cover - defensive
            continue
        roll = rng.random()
        if roll < 0.45:  # noqa: PLR2004 - three-way split of mutation styles
            # Misread the piece type: the classifier's commonest single error.
            choices = [
                kind
                for kind in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
                if kind != original.piece_type
            ]
            mutated.set_piece_at(square, chess.Piece(rng.choice(choices), original.color))
        elif roll < 0.75:  # noqa: PLR2004
            # Misread the colour.
            mutated.set_piece_at(square, chess.Piece(original.piece_type, not original.color))
        elif roll < 0.90 and empties:  # noqa: PLR2004
            # Shift the piece one square: a rectification-error signature.
            mutated.remove_piece_at(square)
            mutated.set_piece_at(rng.choice(empties), original)
        else:
            # Miss the piece entirely.
            mutated.remove_piece_at(square)
        candidate = mutated.fen()
        if candidate == fen:
            continue
        try:
            check = chess.Board(candidate)
        except ValueError:
            continue
        if check.status() == chess.STATUS_VALID:
            return candidate
    return None


@dataclass
class BinaryScore:
    """Confusion matrix for the "this FEN is wrong" signal."""

    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0
    abstained_on_wrong: int = 0
    abstained_on_right: int = 0

    @property
    def total(self) -> int:
        """Every scored trial."""
        return (
            self.true_positive + self.false_positive + self.true_negative + self.false_negative
        )

    def as_dict(self) -> dict[str, Any]:
        """Derived metrics, with the trivial baseline alongside."""
        tp, fp, tn, fn = (
            self.true_positive,
            self.false_positive,
            self.true_negative,
            self.false_negative,
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        specificity = tn / (tn + fp) if tn + fp else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        balanced = (recall + specificity) / 2
        denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
        mcc = ((tp * tn) - (fp * fn)) / denominator if denominator else 0.0
        return {
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn,
            "abstained_on_wrong": self.abstained_on_wrong,
            "abstained_on_right": self.abstained_on_right,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "f1": round(f1, 4),
            "balanced_accuracy": round(balanced, 4),
            "mcc": round(mcc, 4),
            "baseline_always_wrong": {
                "precision": round((tp + fn) / self.total, 4) if self.total else 0.0,
                "recall": 1.0,
                "balanced_accuracy": 0.5,
                "mcc": 0.0,
            },
        }


@dataclass
class Report:
    """Everything one benchmark run produced."""

    started_at: str
    model: str
    server: str
    experiments: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #


def load_test_boards(limit: int, rng: random.Random) -> list[tuple[Path, str]]:
    """Boards from the held-out ``test`` split, with their ground-truth FEN."""
    if not LABELS_CSV.exists() or not SPLITS_CSV.exists():
        return []
    with SPLITS_CSV.open(encoding="utf-8") as handle:
        splits = {row["filename"]: row["split"] for row in csv.DictReader(handle)}
    rows: list[tuple[Path, str]] = []
    with LABELS_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row["filename"]
            if splits.get(name) != "test":
                continue
            fen = (row.get("fen") or "").strip()
            if not fen:
                continue
            if len(fen.split()) == 1:
                fen = f"{fen} {row.get('side_to_move') or 'w'} - - 0 1"
            try:
                board = chess.Board(fen)
            except ValueError:
                continue
            if board.status() != chess.STATUS_VALID:
                continue
            path = SAMPLES_DIR / name
            if path.exists():
                rows.append((path, board.fen()))
    rng.shuffle(rows)
    return rows[:limit]


def load_review_queue(limit: int) -> list[dict[str, Any]]:
    """Low-confidence items the pipeline itself escalated."""
    if not REVIEW_QUEUE.exists():
        return []
    data = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
    items = [item for item in data.get("items", []) if Path(item.get("board_image", "")).exists()]
    return items[:limit]


def load_quarantine(limit: int) -> list[tuple[Path, str, str]]:
    """Audited rejects: image, the FEN that was rejected, and why."""
    if not QUARANTINE_CSV.exists():
        return []
    index: dict[str, Path] = {}
    for path in ORPHANS_DIR.rglob("*.png"):
        index.setdefault(path.name, path)
    rows: list[tuple[Path, str, str]] = []
    with QUARANTINE_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = index.get(row["filename"]) or (SAMPLES_DIR / row["filename"])
            if not path.exists():
                continue
            fen = (row.get("fen") or "").strip()
            if fen:
                rows.append((path, fen, (row.get("motivo") or "").strip()))
    return rows[:limit]


# --------------------------------------------------------------------------- #
# Experiment A -- the decisive one
# --------------------------------------------------------------------------- #


def experiment_a(pairs: int, rng: random.Random, runtime: Any) -> dict[str, Any]:
    """Correct FEN versus legally-corrupted FEN, on held-out boards."""
    print(f"\n=== A. FEN correto x FEN corrompido (split 'test', {pairs} pares) ===")
    boards = load_test_boards(pairs * 2, rng)
    if not boards:
        return {"error": "labels.csv/splits.csv indisponiveis"}

    score = BinaryScore()
    latencies: list[float] = []
    verdicts: dict[str, int] = {}
    square_hits = 0
    square_scored = 0
    used = 0

    for path, true_fen in boards:
        if used >= pairs:
            break
        corrupted = corrupt_one_square(true_fen, rng)
        if corrupted is None:
            continue
        image = load_image(path)
        if image is None:
            continue
        used += 1

        # Trial 1: the FEN is right. A verdict of "inconsistent" is a false alarm.
        right = verify_diagram(image, true_fen, "", runtime=runtime, seed=0)
        latencies.append(right.latency_ms)
        verdicts[f"correct/{right.verdict}"] = verdicts.get(f"correct/{right.verdict}", 0) + 1
        if not right.used_llm:
            score.abstained_on_right += 1
        elif right.verdict == "inconsistent":
            score.false_positive += 1
        elif right.verdict == "consistent":
            score.true_negative += 1
        else:
            score.abstained_on_right += 1

        # Trial 2: one square is wrong, and the position is still legal.
        wrong = verify_diagram(image, corrupted, "", runtime=runtime, seed=0)
        latencies.append(wrong.latency_ms)
        verdicts[f"corrupted/{wrong.verdict}"] = verdicts.get(f"corrupted/{wrong.verdict}", 0) + 1
        if not wrong.used_llm:
            score.abstained_on_wrong += 1
        elif wrong.verdict == "inconsistent":
            score.true_positive += 1
            square_scored += 1
            if _changed_squares(true_fen, corrupted) & set(wrong.suspect_squares):
                square_hits += 1
        elif wrong.verdict == "consistent":
            score.false_negative += 1
        else:
            score.abstained_on_wrong += 1

        print(
            f"  {used:>3}/{pairs} {path.name[:34]:<34} "
            f"correto->{right.verdict:<12} corrompido->{wrong.verdict:<12}"
        )

    result = score.as_dict()
    result["pairs"] = used
    result["verdict_counts"] = verdicts
    result["latency_ms_median"] = round(statistics.median(latencies), 1) if latencies else 0.0
    result["suspect_square_hit_rate"] = (
        round(square_hits / square_scored, 4) if square_scored else None
    )
    result["suspect_square_scored"] = square_scored
    return result


def _changed_squares(fen_a: str, fen_b: str) -> set[str]:
    """Algebraic names of the squares that differ between two positions."""
    board_a = chess.Board(fen_a)
    board_b = chess.Board(fen_b)
    return {
        chess.square_name(square)
        for square in chess.SQUARES
        if board_a.piece_at(square) != board_b.piece_at(square)
    }


# --------------------------------------------------------------------------- #
# Experiment B -- the real queue
# --------------------------------------------------------------------------- #


def experiment_b(limit: int, runtime: Any) -> dict[str, Any]:
    """The pipeline's own low-confidence queue, plus the audited rejects."""
    print(f"\n=== B. Fila de revisao real e quarentena (ate {limit} itens de cada) ===")
    queue_result: dict[str, Any] = {
        "caveat": (
            "review_queue.json nao tem verdade de campo: estes numeros descrevem o que o "
            "modelo disse, nao se ele acertou."
        ),
        "verdicts": {},
        "items": [],
    }
    latencies: list[float] = []
    for item in load_review_queue(limit):
        image = load_image(Path(item["board_image"]))
        if image is None:
            continue
        result = verify_diagram(image, item.get("fen", ""), "", runtime=runtime, seed=0)
        latencies.append(result.latency_ms)
        queue_result["verdicts"][result.verdict] = (
            queue_result["verdicts"].get(result.verdict, 0) + 1
        )
        decision = result.decide(float(item.get("min_confidence") or 0.0))
        queue_result["items"].append(
            {
                "page": item.get("page_index"),
                "diagram": item.get("diagram_index"),
                "min_confidence": round(float(item.get("min_confidence") or 0.0), 4),
                "verdict": result.verdict,
                "llm_confidence": round(result.confidence, 3),
                "suspect_squares": list(result.suspect_squares),
                "confidence_after": round(decision.adjusted, 4),
                "flagged": decision.flagged,
            }
        )
        print(
            f"  p{item.get('page_index')}/d{item.get('diagram_index')} "
            f"conf={float(item.get('min_confidence') or 0):.3f} -> {result.verdict}"
        )
    queue_result["latency_ms_median"] = (
        round(statistics.median(latencies), 1) if latencies else 0.0
    )

    quarantine_score = BinaryScore()
    quarantine_latencies: list[float] = []
    for path, fen, motivo in load_quarantine(limit):
        image = load_image(path)
        if image is None:
            continue
        result = verify_diagram(image, fen, "", runtime=runtime, seed=0)
        quarantine_latencies.append(result.latency_ms)
        if not result.used_llm:
            quarantine_score.abstained_on_wrong += 1
        elif result.verdict == "inconsistent":
            quarantine_score.true_positive += 1
        elif result.verdict == "consistent":
            quarantine_score.false_negative += 1
        else:
            quarantine_score.abstained_on_wrong += 1
        print(f"  quarentena {path.name[:30]:<30} ({motivo[:28]:<28}) -> {result.verdict}")

    detected = quarantine_score.true_positive
    scored = detected + quarantine_score.false_negative + quarantine_score.abstained_on_wrong
    return {
        "review_queue": queue_result,
        "quarantine": {
            "caveat": (
                "Todo FEN em quarantine.csv e ILEGAL (rei ausente, peao na primeira fila...). "
                "O verificador de legalidade da SPEC 6.4 ja os pega de graca, sem LLM. "
                "Este numero mede se o LLM concorda, nao se ele acrescenta algo."
            ),
            "known_wrong_items": scored,
            "flagged_wrong": detected,
            "recall": round(detected / scored, 4) if scored else 0.0,
            "latency_ms_median": (
                round(statistics.median(quarantine_latencies), 1) if quarantine_latencies else 0.0
            ),
        },
    }


# --------------------------------------------------------------------------- #
# Experiment C -- VRAM co-residency
# --------------------------------------------------------------------------- #


def experiment_c(runtime: Any, vision_gib: float) -> dict[str, Any]:
    """Peak VRAM with the LLM resident and a vision-sized allocation live."""
    print(f"\n=== C. VRAM simultanea (LLM + {vision_gib:.1f} GiB de pipeline de visao) ===")
    runtime.unload()
    time.sleep(4)
    idle = nvml_used_mib()
    if idle is None:
        return {"error": "nvidia-smi indisponivel"}
    print(f"  linha de base (desktop, sem modelos): {idle} MiB")

    runtime.load()
    time.sleep(2)
    with_llm = nvml_used_mib() or idle
    print(f"  com o LLM residente:                 {with_llm} MiB (+{with_llm - idle})")

    peak = with_llm
    torch_error = ""
    try:
        import torch  # noqa: PLC0415 - optional, only for this measurement

        if torch.cuda.is_available():
            block = torch.empty(
                int(vision_gib * 1024**3 // 2), dtype=torch.float16, device="cuda"
            )
            block.fill_(0)
            torch.cuda.synchronize()
            time.sleep(2)
            peak = nvml_used_mib() or with_llm
            print(f"  + alocacao de visao simulada:        {peak} MiB")
            del block
            torch.cuda.empty_cache()
        else:
            torch_error = "torch.cuda indisponivel"
    except Exception as exc:  # noqa: BLE001 - a failed allocation is itself the result
        torch_error = f"{type(exc).__name__}: {exc}"
        peak = nvml_used_mib() or with_llm
        print(f"  ! alocacao de visao falhou: {torch_error}")

    budget_mib = 7.0 * 1024
    return {
        "idle_mib": idle,
        "with_llm_mib": with_llm,
        "llm_footprint_mib": with_llm - idle,
        "peak_with_vision_mib": peak,
        "simulated_vision_gib": vision_gib,
        "adr0004_budget_mib": budget_mib,
        "peak_within_budget": peak <= budget_mib,
        "declared_vram_gib_adr0005": 3.5,
        "measured_vram_gib": round((with_llm - idle) / 1024, 2),
        "torch_note": torch_error,
    }


# --------------------------------------------------------------------------- #
# Experiment D -- latency and the stipulation task
# --------------------------------------------------------------------------- #

_STIPULATION_CASES: tuple[tuple[str, str, int | None, int | None], ...] = (
    ("Diagrama 12. Brancas jogam e ganham.", "win", None, 12),
    ("Mate em 2", "mate", 2, None),
    ("No. 45 - White to play and win", "win", None, 45),
    ("Mate in 3", "mate", 3, None),
    ("Weiss zieht und gewinnt", "win", None, None),
    ("Matt in 2 Zuegen", "mate", 2, None),
    ("Blancas juegan y ganan", "win", None, None),
    ("Mate en 2", "mate", 2, None),
    ("Les Blancs jouent et gagnent", "win", None, None),
    ("Mat en 3 coups", "mate", 3, None),
    ("Il Bianco muove e vince", "win", None, None),
    ("Matto in 2 mosse", "mate", 2, None),
    ("Белые начинают и выигрывают", "win", None, None),
    ("Мат в 2 хода", "mate", 2, None),
    ("Brancas jogam e empatam", "draw", None, None),
    ("White to play and draw", "draw", None, None),
    ("Qual o melhor lance das brancas?", "best_move", None, None),
    ("Diagrama 88", "unknown", None, 88),
    ("Posicao 7 - Estudo de Reti", "study", None, 7),
    ("Position after 15...Rxe4", "unknown", None, None),
)


def experiment_d(runtime: Any, repeats: int) -> dict[str, Any]:
    """Per-task latency (median of ``repeats``) and stipulation accuracy."""
    print(f"\n=== D. Latencia por tarefa (mediana de {repeats}) e estipulacao ===")
    boards = load_test_boards(repeats, random.Random(11))
    latency: dict[str, float] = {}

    if boards:
        samples: list[float] = []
        for path, fen in boards:
            image = load_image(path)
            if image is None:
                continue
            started = time.perf_counter()
            verify_diagram(image, fen, "", runtime=runtime, seed=0)
            samples.append((time.perf_counter() - started) * 1000.0)
        if samples:
            latency["verify_diagram_ms"] = round(statistics.median(samples), 1)
            latency["verify_diagram_n"] = len(samples)
            print(f"  verify_diagram: mediana {latency['verify_diagram_ms']} ms")

    caption_samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        caption_for_diagram(
            "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1", "Final de rei e peao", runtime=runtime, seed=0
        )
        caption_samples.append((time.perf_counter() - started) * 1000.0)
    latency["caption_for_diagram_ms"] = round(statistics.median(caption_samples), 1)
    print(f"  caption_for_diagram: mediana {latency['caption_for_diagram_ms']} ms")

    rules_ok = 0
    llm_ok = 0
    llm_latencies: list[float] = []
    misses: list[str] = []
    for caption, kind, moves, number in _STIPULATION_CASES:
        rules = extract_stipulation(caption, allow_llm=False)
        if rules and rules.kind == kind and rules.moves == moves and rules.diagram_number == number:
            rules_ok += 1
        started = time.perf_counter()
        full = extract_stipulation(caption, runtime=runtime, seed=0)
        llm_latencies.append((time.perf_counter() - started) * 1000.0)
        if full and full.kind == kind and full.moves == moves and full.diagram_number == number:
            llm_ok += 1
        else:
            misses.append(f"{caption!r} -> {full}")

    total = len(_STIPULATION_CASES)
    print(f"  estipulacao: regras {rules_ok}/{total}, regras+LLM {llm_ok}/{total}")
    for miss in misses:
        print(f"    erro: {miss}")

    return {
        "latency": latency,
        "stipulation": {
            "cases": total,
            "rules_only_correct": rules_ok,
            "rules_plus_llm_correct": llm_ok,
            "rules_only_accuracy": round(rules_ok / total, 4),
            "rules_plus_llm_accuracy": round(llm_ok / total, 4),
            "median_latency_ms": round(statistics.median(llm_latencies), 1),
            "misses": misses,
        },
    }


# --------------------------------------------------------------------------- #
# Experiment E -- stipulation extraction against corpus ground truth
# --------------------------------------------------------------------------- #

#: Kinds that assert a task. Anything here on a caption that states none is a
#: fabrication, which is the failure mode this experiment exists to catch.
_ASSERTIVE = ("mate", "win", "draw", "best_move", "study")


def load_captions() -> list[dict[str, Any]]:
    """The hand-labelled caption set, or an empty list if it was not built."""
    if not CAPTIONS_JSONL.exists():
        return []
    with CAPTIONS_JSONL.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _score_stipulation_run(
    rows: list[dict[str, Any]], answers: list[Any]
) -> dict[str, Any]:
    """Turn one pass over the caption set into metrics.

    ``answers[i]`` is the :class:`~caissa.llm.tasks.Stipulation` or ``None`` the
    arm produced for ``rows[i]``.
    """
    tp = fp = tn = fn = 0
    kind_ok = kind_total = 0
    moves_ok = moves_total = 0
    number_ok = number_total = 0
    side_ok = side_total = 0
    per_lang: dict[str, dict[str, int]] = {}
    fabrications: list[dict[str, str]] = []

    for row, answer in zip(rows, answers, strict=True):
        klass = row["class"]
        lang = row["lang"]
        bucket = per_lang.setdefault(
            lang,
            {"n": 0, "abstain_n": 0, "abstain_ok": 0, "kind_n": 0, "kind_ok": 0, "fabricated": 0},
        )
        bucket["n"] += 1
        said = (answer.kind if answer is not None else "unknown") or "unknown"
        asserted = said in _ASSERTIVE

        if klass == "P":
            if asserted:
                tp += 1
            else:
                fn += 1
            kind_total += 1
            bucket["kind_n"] += 1
            if said == row["kind"]:
                kind_ok += 1
                bucket["kind_ok"] += 1
            if row["kind"] == "mate":
                moves_total += 1
                if answer is not None and answer.moves == row["moves"]:
                    moves_ok += 1
        else:
            bucket["abstain_n"] += 1
            if asserted:
                fp += 1
                bucket["fabricated"] += 1
                fabrications.append({"caption": row["caption"][:110], "said": said})
            else:
                tn += 1
                bucket["abstain_ok"] += 1

        if row["number_known"]:
            number_total += 1
            got = answer.diagram_number if answer is not None else None
            if got == row["number"]:
                number_ok += 1
        if klass in {"P", "S"} and row["side"] is not None:
            side_total += 1
            got_side = answer.side_to_move if answer is not None else None
            if got_side == row["side"]:
                side_ok += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    # `None`, not zero, when the slice has no negatives at all: an abstention
    # rate of 0.000 and "there was nothing to abstain from" are not the same
    # claim, and only one of them condemns a model.
    abstention = tn / (tn + fp) if tn + fp else None
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    mcc = ((tp * tn) - (fp * fn)) / denominator if denominator else 0.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "abstention_on_negatives": None if abstention is None else round(abstention, 4),
        "fabrication_rate": None if abstention is None else round(1.0 - abstention, 4),
        "f1": round(f1, 4),
        "mcc": round(mcc, 4),
        "kind_accuracy_on_positives": round(kind_ok / kind_total, 4) if kind_total else 0.0,
        "kind_n": kind_total,
        "mate_moves_accuracy": round(moves_ok / moves_total, 4) if moves_total else 0.0,
        "mate_moves_n": moves_total,
        "diagram_number_accuracy": round(number_ok / number_total, 4) if number_total else 0.0,
        "diagram_number_n": number_total,
        "side_accuracy": round(side_ok / side_total, 4) if side_total else 0.0,
        "side_n": side_total,
        "per_language": {
            lang: {
                "n": data["n"],
                "abstention": (
                    round(data["abstain_ok"] / data["abstain_n"], 4) if data["abstain_n"] else None
                ),
                "abstention_n": data["abstain_n"],
                "fabricated": data["fabricated"],
                "kind_accuracy": (
                    round(data["kind_ok"] / data["kind_n"], 4) if data["kind_n"] else None
                ),
                "kind_n": data["kind_n"],
            }
            for lang, data in sorted(per_lang.items())
        },
        "fabrication_examples": fabrications[:12],
    }


def _summary_line(scored: dict[str, Any]) -> str:
    """One readable line per arm, tolerant of the `None`s that mean "no data"."""

    def show(key: str) -> str:
        value = scored.get(key)
        return "  n/d" if value is None else f"{value:.3f}"

    latency = scored.get("median_latency_ms")
    tail = "" if latency is None else f"  {latency:.0f} ms"
    return (
        f"abstencao {show('abstention_on_negatives')}  precisao {show('precision')}  "
        f"revocacao {show('recall')}  numero {show('diagram_number_accuracy')}"
        f"  lado {show('side_accuracy')}{tail}"
    )


def _median_of_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Median of every scalar metric across runs; nested dicts recurse."""
    if not runs:
        return {}
    merged: dict[str, Any] = {}
    for key, value in runs[0].items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            samples = [run[key] for run in runs if isinstance(run.get(key), (int, float))]
            merged[key] = round(statistics.median(samples), 4)
        elif isinstance(value, dict):
            nested = [run[key] for run in runs if isinstance(run.get(key), dict)]
            merged[key] = _median_of_runs(nested)
        else:
            merged[key] = value
    return merged


def experiment_e(runtime: Any, repeats: int, limit: int) -> dict[str, Any]:
    """Stipulation extraction, three arms, against the labelled caption set."""
    rows = load_captions()[:limit] if limit else load_captions()
    print(f"\n=== E. Estipulacao em {len(rows)} legendas reais do acervo ===")
    if not rows:
        return {"error": f"{CAPTIONS_JSONL} nao existe; rode o levantamento de legendas"}

    from collections import Counter  # noqa: PLC0415 - local, report-only

    result: dict[str, Any] = {
        "captions": len(rows),
        "by_class": dict(Counter(row["class"] for row in rows)),
        "by_language": dict(Counter(row["lang"] for row in rows)),
        "arms": {},
        "ground_truth": str(CAPTIONS_JSONL),
    }

    # -- arm 1: the deterministic matcher alone, no model at all ------------- #
    rules_answers = [extract_stipulation(row["caption"], allow_llm=False) for row in rows]
    result["arms"]["rules_only"] = _score_stipulation_run(rows, rules_answers)
    print("  regras  : " + _summary_line(result["arms"]["rules_only"]))

    # -- arm 2: the model alone, so the result can be attributed to it ------- #
    for arm, kwargs in (
        ("llm_only", {"allow_rules": False, "force_schema": True}),
        ("llm_only_no_schema", {"allow_rules": False, "force_schema": False}),
        ("production_rules_then_llm", {"force_schema": True}),
    ):
        passes = repeats if arm != "llm_only_no_schema" else 1
        runs: list[dict[str, Any]] = []
        latencies: list[float] = []
        for attempt in range(passes):
            answers = []
            for row in rows:
                started = time.perf_counter()
                answers.append(
                    extract_stipulation(row["caption"], runtime=runtime, seed=attempt, **kwargs)
                )
                latencies.append((time.perf_counter() - started) * 1000.0)
            runs.append(_score_stipulation_run(rows, answers))
        merged = _median_of_runs(runs)
        merged["runs"] = passes
        merged["median_latency_ms"] = round(statistics.median(latencies), 1)
        result["arms"][arm] = merged
        print(f"  {arm:26s}: " + _summary_line(merged))
    return result


# --------------------------------------------------------------------------- #
# Experiment F -- the LLM must never touch a move
# --------------------------------------------------------------------------- #


def load_prose() -> list[dict[str, Any]]:
    """Real annotated paragraphs, or an empty list if the set was not built."""
    if not PROSE_JSONL.exists():
        return []
    with PROSE_JSONL.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _survived_in_order(tokens: list[str], text: str) -> list[str]:
    """Which of `tokens` are missing from `text` as an ordered substring scan.

    This, and not a token re-scan, is the guarantee
    :func:`~caissa.llm.tasks.translate_notation_prose` actually makes: every
    move that was masked comes back byte-for-byte, in order. A token re-scan
    fails on things that are not damage -- translated prose names squares
    ("the square g7"), and this corpus's OCR writes captures as U+00D7 so a
    restored "b6" can land next to an "a4x" the mask never covered and stop
    looking like a standalone token while being perfectly intact.
    """
    cursor = 0
    missing: list[str] = []
    for token in tokens:
        found = text.find(token, cursor)
        if found < 0:
            missing.append(token)
        else:
            cursor = found + len(token)
    return missing


_LANG_NAMES = {
    "pt": "portugues",
    "en": "ingles",
    "de": "alemao",
    "es": "espanhol",
    "nl": "neerlandes",
    "ru": "russo",
    "fr": "frances",
}


def experiment_f(runtime: Any, repeats: int, limit: int) -> dict[str, Any]:
    """Translate real prose and check that not one move token changed."""
    rows = load_prose()[:limit] if limit else load_prose()
    print(f"\n=== F. Traducao de prosa: {len(rows)} paragrafos, lances intocados? ===")
    if not rows:
        return {"error": f"{PROSE_JSONL} nao existe"}

    runs: list[dict[str, Any]] = []
    latencies: list[float] = []
    corruptions: list[dict[str, Any]] = []
    for attempt in range(repeats):
        translated = unchanged = corrupted = extra = 0
        for row in rows:
            source = row["text"]
            target = "en" if row["lang"] != "en" else "pt"
            started = time.perf_counter()
            output = translate_notation_prose(
                source,
                _LANG_NAMES.get(row["lang"], row["lang"]),
                _LANG_NAMES[target],
                runtime=runtime,
                seed=attempt,
            )
            latencies.append((time.perf_counter() - started) * 1000.0)
            before = _MASKABLE_RE.findall(source)
            if output == source:
                unchanged += 1
                continue
            missing = _survived_in_order(before, output)
            if not missing:
                translated += 1
                extra += max(0, len(_MASKABLE_RE.findall(output)) - len(before))
            else:
                corrupted += 1
                if attempt == 0 and len(corruptions) < 8:
                    corruptions.append(
                        {
                            "book": row["book"],
                            "lang": row["lang"],
                            "moves_in": len(before),
                            "tokens_lost": missing[:8],
                        }
                    )
        runs.append(
            {
                "paragraphs": len(rows),
                "translated_moves_intact": translated,
                "returned_source_unchanged": unchanged,
                "moves_corrupted": corrupted,
                "corruption_rate": round(corrupted / len(rows), 4),
                "translation_rate": round(translated / len(rows), 4),
                "extra_move_shaped_tokens_in_prose": extra,
            }
        )
        print(
            f"  passada {attempt + 1}: traduzidos {translated}, devolvidos intactos {unchanged}, "
            f"lances corrompidos {corrupted}"
        )

    merged = _median_of_runs(runs)
    merged["runs"] = repeats
    merged["median_latency_ms"] = round(statistics.median(latencies), 1)
    merged["by_language"] = {}
    for row in rows:
        merged["by_language"][row["lang"]] = merged["by_language"].get(row["lang"], 0) + 1
    merged["corruption_examples"] = corruptions
    merged["gate_zero_corruption"] = merged["moves_corrupted"] == 0
    return merged


# --------------------------------------------------------------------------- #
# Experiment G -- generated captions: safety, not taste
# --------------------------------------------------------------------------- #

_YEAR_RE = re.compile(r"\b(1[6-9]\d{2}|20[0-4]\d)\b")
_PROPER_RE = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{3,}\b")


def load_field_positions(limit: int) -> list[tuple[str, str]]:
    """``(fen, note)`` pairs from the hand-annotated field set."""
    path = CORPUS / "field_set.jsonl"
    if not path.exists():
        return []
    found: list[tuple[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            page = json.loads(line)
            for diagram in page.get("diagrams") or ():
                placement = (diagram.get("placement") or "").strip()
                if not placement:
                    continue
                side = diagram.get("side_to_move") or "w"
                fen = f"{placement} {side} - - 0 1"
                try:
                    chess.Board(fen)
                except ValueError:
                    continue
                found.append((fen, str(diagram.get("note") or "")))
    return found[:limit]


def experiment_g(runtime: Any, repeats: int, limit: int) -> dict[str, Any]:
    """Objective safety properties of generated captions. Not a quality score."""
    positions = load_field_positions(limit)
    print(f"\n=== G. Legendas geradas: {len(positions)} posicoes do conjunto de campo ===")
    if not positions:
        return {"error": "field_set.jsonl indisponivel"}

    runs: list[dict[str, Any]] = []
    latencies: list[float] = []
    samples: list[dict[str, str]] = []
    for attempt in range(repeats):
        with_move = invented_year = invented_name = fell_back = 0
        lengths: list[int] = []
        for fen, note in positions:
            started = time.perf_counter()
            caption = caption_for_diagram(fen, note, runtime=runtime, language="pt", seed=attempt)
            latencies.append((time.perf_counter() - started) * 1000.0)
            lengths.append(len(caption))
            if caption in {"Brancas jogam", "Pretas jogam"}:
                fell_back += 1
                continue
            if _MASKABLE_RE.search(caption):
                with_move += 1
            if any(year not in note for year in _YEAR_RE.findall(caption)):
                invented_year += 1
            context_words = set(_PROPER_RE.findall(note))
            if any(word not in context_words for word in _PROPER_RE.findall(caption)):
                invented_name += 1
            if attempt == 0 and len(samples) < 8:
                samples.append({"note": note, "caption": caption})
        runs.append(
            {
                "positions": len(positions),
                "fell_back_to_deterministic": fell_back,
                "captions_with_move_notation": with_move,
                "captions_with_year_absent_from_context": invented_year,
                "captions_with_proper_noun_absent_from_context": invented_name,
                "median_length_chars": round(statistics.median(lengths), 1),
            }
        )
        print(
            f"  passada {attempt + 1}: fallback {fell_back}, com lance {with_move}, "
            f"ano inventado {invented_year}, nome inventado {invented_name}"
        )

    merged = _median_of_runs(runs)
    merged["runs"] = repeats
    merged["median_latency_ms"] = round(statistics.median(latencies), 1)
    merged["samples"] = samples
    merged["quality_caveat"] = (
        "Qualidade de legenda nao e medida aqui: nao ha metrica objetiva de "
        "'boa legenda'. Estes numeros medem apenas seguranca."
    )
    return merged


# --------------------------------------------------------------------------- #
# Experiment H -- do the LLM and the vision pipeline actually fit together?
# --------------------------------------------------------------------------- #


def _sample_peak(process: subprocess.Popen[str], period: float = 2.0) -> tuple[int, list[int]]:
    """Poll total device VRAM while `process` runs. Returns (peak, samples)."""
    samples: list[int] = []
    while process.poll() is None:
        used = nvml_used_mib()
        if used is not None:
            samples.append(used)
        time.sleep(period)
    used = nvml_used_mib()
    if used is not None:
        samples.append(used)
    return (max(samples) if samples else 0), samples


def _run_vision(workers: int, pages: int, tag: str) -> tuple[subprocess.Popen[str], list[str]]:
    """Start the real 6-worker CUDA recognition run as a child process."""
    argv = [
        sys.executable,
        str(REPO_ROOT / "benchmarks" / "bench_batch_throughput.py"),
        "--workers",
        str(workers),
        "--device",
        "cuda",
        "--runs",
        "3",
        "--pages",
        str(pages),
        "--tag",
        tag,
    ]
    return (
        subprocess.Popen(  # noqa: S603 - fixed argv, our own script
            argv,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ),
        argv,
    )


def experiment_h(runtime: Any, workers: int, pages: int) -> dict[str, Any]:
    """Peak VRAM with **both** paths exercised for real, against ADR-0004.

    Not a simulated allocation: this starts the same ``bench_batch_throughput``
    run the vision front measures with, at the same worker count, and samples
    the device while it runs -- once with the LLM resident and once after the
    residency manager has evicted it. Those two numbers are the whole answer to
    "can they co-reside".
    """
    print(f"\n=== H. VRAM real: LLM + reconhecimento com {workers} workers CUDA ===")
    runtime.unload()
    time.sleep(5)
    idle = nvml_used_mib()
    if idle is None:
        return {"error": "nvidia-smi indisponivel"}
    print(f"  ocioso (nenhum modelo):              {idle} MiB")

    # The default keep_alive is five minutes and a six-worker recognition run is
    # longer than that. Measured the first time this experiment ran: the LLM
    # expired partway through and the "peak with both resident" number was a
    # peak with one of them gone. A dedicated runtime holds the weights for the
    # whole window, which is the condition the experiment is about.
    holder = runtime
    if isinstance(runtime, OllamaRuntime):
        holder = OllamaRuntime(runtime.model, keep_alive="45m")
    holder.load()
    time.sleep(3)
    with_llm = nvml_used_mib() or idle
    print(f"  LLM residente:                       {with_llm} MiB (+{with_llm - idle})")

    together, argv = _run_vision(workers, pages, "llm_resident")
    peak_together, _ = _sample_peak(together)
    output_together = (together.stdout.read() if together.stdout else "") or ""
    ok_together = together.returncode == 0
    # Did it actually stay? The experiment is worthless if it did not.
    still_resident = (nvml_used_mib() or 0) >= idle + (with_llm - idle) // 2
    print(
        f"  pico com LLM residente + visao:      {peak_together} MiB  "
        f"({'concluiu' if ok_together else 'FALHOU'})"
    )

    evicted = False
    try:
        from caissa.llm.residency import LLM_MODEL_NAME, register_llm  # noqa: PLC0415
        from caissa.vision.runtime.residency import (  # noqa: PLC0415
            get_residency_manager,
        )

        manager = get_residency_manager()
        register_llm(manager, runtime=holder)
        evicted = bool(manager.unload(LLM_MODEL_NAME, force=True))
    except Exception as exc:  # noqa: BLE001 - the failure is itself the result
        print(f"  ! gerenciador de residencia: {type(exc).__name__}: {exc}")
        holder.unload()
    time.sleep(5)
    after_evict = nvml_used_mib() or idle
    print(f"  apos despejo do LLM:                 {after_evict} MiB")

    alone, _ = _run_vision(workers, pages, "llm_evicted")
    peak_alone, _ = _sample_peak(alone)
    output_alone = (alone.stdout.read() if alone.stdout else "") or ""
    ok_alone = alone.returncode == 0
    print(
        f"  pico so com a visao:                 {peak_alone} MiB  "
        f"({'concluiu' if ok_alone else 'FALHOU'})"
    )

    budget_mib = int(7.0 * 1024)
    return {
        "workers": workers,
        "pages": pages,
        "command": " ".join(argv),
        "idle_mib": idle,
        "llm_resident_mib": with_llm,
        "llm_footprint_mib": with_llm - idle,
        "peak_llm_plus_vision_mib": peak_together,
        "vision_completed_with_llm_resident": ok_together,
        "llm_still_resident_after_vision_run": still_resident,
        "after_eviction_mib": after_evict,
        "llm_actually_evicted": evicted,
        "eviction_freed_mib": with_llm - after_evict,
        "peak_vision_alone_mib": peak_alone,
        "vision_completed_alone": ok_alone,
        "adr0004_budget_mib": budget_mib,
        "together_within_budget": peak_together <= budget_mib,
        "alone_within_budget": peak_alone <= budget_mib,
        "vision_tail_with_llm": output_together[-1200:],
        "vision_tail_alone": output_alone[-1200:],
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """Run the requested experiments and write a JSON report."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--experiments", default="a,b,c,d", help="subset of a,b,c,d,e,f,g,h,i"
    )
    parser.add_argument("--regions", type=int, default=0, help="cap for I (0 = all)")
    parser.add_argument("--captions", type=int, default=0, help="cap for E (0 = all)")
    parser.add_argument("--prose", type=int, default=0, help="cap for F (0 = all)")
    parser.add_argument("--positions", type=int, default=30, help="cap for G")
    parser.add_argument("--workers", type=int, default=6, help="CUDA workers for H")
    parser.add_argument("--vision-pages", type=int, default=24, help="pages per vision run in H")
    parser.add_argument("--pairs", type=int, default=25, help="board pairs for experiment A")
    parser.add_argument("--limit", type=int, default=30, help="items per source in experiment B")
    parser.add_argument("--repeats", type=int, default=5, help="runs per latency median (>= 3)")
    parser.add_argument("--vision-gib", type=float, default=2.0, help="simulated vision footprint")
    parser.add_argument("--seed", type=int, default=20260907)
    parser.add_argument("--json", type=Path, default=None, help="report path")
    args = parser.parse_args(argv)

    if args.repeats < 3:  # noqa: PLR2004 - CORPUS.md rule 1
        parser.error("--repeats deve ser >= 3 (regra 1 de docs/quality/CORPUS.md)")

    runtime = get_runtime(force=True)
    info = runtime.info()
    print(f"runtime : {info.backend} {info.server_version}")
    print(f"modelo  : {info.model}  (visao: {info.vision})")
    if not info.available:
        print(f"INDISPONIVEL: {info.detail}")
        return 1
    if isinstance(runtime, OllamaRuntime):
        runtime.load()

    rng = random.Random(args.seed)
    report = Report(
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        model=info.model,
        server=f"{info.backend} {info.server_version}",
    )
    wanted = {part.strip().lower() for part in args.experiments.split(",") if part.strip()}
    started = time.perf_counter()

    if "a" in wanted:
        report.experiments["A_fen_discrimination"] = experiment_a(args.pairs, rng, runtime)
    if "b" in wanted:
        report.experiments["B_review_queue"] = experiment_b(args.limit, runtime)
    if "d" in wanted:
        report.experiments["D_latency_and_stipulation"] = experiment_d(runtime, args.repeats)
    if "e" in wanted:
        report.experiments["E_stipulation_corpus"] = experiment_e(
            runtime, args.repeats, args.captions
        )
    if "f" in wanted:
        report.experiments["F_translation_move_safety"] = experiment_f(
            runtime, args.repeats, args.prose
        )
    if "g" in wanted:
        report.experiments["G_caption_safety"] = experiment_g(
            runtime, args.repeats, args.positions
        )
    if "i" in wanted:
        report.experiments["I_ocr_repair"] = experiment_i(
            runtime, args.repeats, args.regions, args.seed, _median_of_runs
        )
    if "h" in wanted:
        report.experiments["H_vram_both_paths"] = experiment_h(
            runtime, args.workers, args.vision_pages
        )
    if "c" in wanted:
        # Last: it unloads and reloads the model, which would poison D's timings.
        report.experiments["C_vram"] = experiment_c(runtime, args.vision_gib)

    report.notes.append(f"tempo total: {time.perf_counter() - started:.1f}s")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = args.json or (
        REPORTS_DIR / f"llm_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    )
    destination.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nrelatorio: {destination}")
    print(json.dumps(report.experiments, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
