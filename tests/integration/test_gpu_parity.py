"""Correctness gate for front F4-GPU: the fast path must read the same boards.

A speedup that changes a FEN is not a speedup, it is a regression with a good
stopwatch. These tests take real board crops from the acervo -- the detector's own
800x800 warps, not synthetic ones -- and demand that the accelerated path agree
with the trunk's CPU fp32 path on:

* the placement field of the FEN,
* the per-square ``class_indices`` after constrained decoding,
* the raw per-square argmax of the (64, 13) matrix, before decoding,
* the orientation the policy chose.

The argmax is checked as well as the FEN because constrained decoding (S-11) can
absorb a single-square disagreement into the same legal position; that would hide
exactly the drift these tests exist to catch.

``is_available()`` proving nothing on Blackwell is treated as a first-class
concern: :func:`test_cuda_actually_computes` runs real kernels and compares
against CPU references, because the sm_120 failure modes are a silent CPU
fallback and ``no kernel image is available for execution on the device``.

Run:
    .venv/Scripts/python.exe -m pytest tests/integration/test_gpu_parity.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "src", REPO_ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from benchmarks.board_corpus import load_board_crops  # noqa: E402
from caissa.vision.classify import (  # noqa: E402
    BatchedClassifier,
    assert_equivalent_to_trunk,
    load_classifier,
    predict_boards_batched,
    trunk_model_path,
)
from caissa.vision.classify.cvoff import ensure_cvoff_on_path  # noqa: E402

ensure_cvoff_on_path()

MIN_CROPS = 200
"""The gate's own floor. Fewer crops is not a smaller test, it is a weaker claim."""

VRAM_BUDGET_BYTES = 7 * 1024**3
"""ADR-0004: 7,0 GB shared with detector, OCR and LLM. Not ours alone."""

BOARDS_PER_CALL = 16
"""16 boards x 2 orientations x 64 squares = 2048 cells, the production batch size."""


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _torch() -> Any:
    torch = pytest.importorskip("torch")
    return torch


@pytest.fixture(scope="session")
def crops() -> list[np.ndarray]:
    """At least :data:`MIN_CROPS` real board warps from the acervo.

    The corpus deliberately keeps each crop at the size the detector produced, so the
    shapes are heterogeneous and cannot be stacked into one rectangular array. Every
    consumer here iterates or slices, so a list is the honest container: forcing a
    common shape would silently resample the very pixels the parity test exists to
    compare.
    """
    try:
        array, meta = load_board_crops(max(MIN_CROPS, 220))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Corpus de recortes indisponivel: {exc!r}")
    if len(array) < MIN_CROPS:
        pytest.skip(f"So {len(array)} recortes colhidos; o portao pede {MIN_CROPS}.")
    shapes = {tuple(crop.shape) for crop in array[:MIN_CROPS]}
    print(
        f"\ncorpus: {len(array)} recortes de {len({m['pdf'] for m in meta})} livros, "
        f"{len(shapes)} formas distintas"
    )
    return [np.ascontiguousarray(crop) for crop in array[:MIN_CROPS]]


@pytest.fixture(scope="session")
def model_path() -> Path:
    path = trunk_model_path()
    if not path.is_file():
        pytest.skip(f"Checkpoint de producao ausente: {path}")
    return path


@pytest.fixture(scope="session")
def device_info() -> Any:
    from caissa.vision.runtime import get_device_info

    return get_device_info()


@pytest.fixture(scope="session")
def cpu_model(model_path: Path) -> tuple[Any, str]:
    from chess_diagram_ocr.inference import load_model

    return load_model(model_path, device="cpu")


@pytest.fixture(scope="session")
def cpu_reference(crops: list[np.ndarray], cpu_model: tuple[Any, str]) -> list[dict[str, Any]]:
    """The trunk's own per-board CPU fp32 reading. This is the thing to match."""
    from chess_diagram_ocr.inference import predict_with_orientation

    model, device = cpu_model
    out: list[dict[str, Any]] = []
    for board in crops:
        oriented = predict_with_orientation(np.ascontiguousarray(board), model, device)
        prediction = oriented.prediction
        out.append(
            {
                "fen": prediction.fen_board,
                "classes": list(prediction.class_indices),
                "argmax": prediction.probs.argmax(axis=1).tolist(),
                "rotation": oriented.rotation,
                "min_confidence": prediction.min_confidence,
            }
        )
    return out


def _accelerated_readings(classifier: BatchedClassifier, crops: list[np.ndarray]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for start in range(0, len(crops), BOARDS_PER_CALL):
        chunk = [np.ascontiguousarray(board) for board in crops[start : start + BOARDS_PER_CALL]]
        for oriented in predict_boards_batched(chunk, classifier):
            prediction = oriented.prediction
            out.append(
                {
                    "fen": prediction.fen_board,
                    "classes": list(prediction.class_indices),
                    "argmax": prediction.probs.argmax(axis=1).tolist(),
                    "rotation": oriented.rotation,
                    "min_confidence": prediction.min_confidence,
                }
            )
    return out


def _compare(reference: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    assert len(reference) == len(candidate)
    fen_diffs: list[dict[str, Any]] = []
    class_diffs = 0
    argmax_diffs = 0
    rotation_diffs = 0
    for index, (want, got) in enumerate(zip(reference, candidate, strict=True)):
        if want["fen"] != got["fen"]:
            fen_diffs.append({"index": index, "cpu": want["fen"], "fast": got["fen"]})
        class_diffs += sum(1 for a, b in zip(want["classes"], got["classes"], strict=True) if a != b)
        argmax_diffs += sum(1 for a, b in zip(want["argmax"], got["argmax"], strict=True) if a != b)
        rotation_diffs += int(want["rotation"] != got["rotation"])
    return {
        "boards": len(reference),
        "squares": 64 * len(reference),
        "fen_mismatches": len(fen_diffs),
        "fen_examples": fen_diffs[:5],
        "class_square_mismatches": class_diffs,
        "argmax_square_mismatches": argmax_diffs,
        "rotation_mismatches": rotation_diffs,
    }


# --------------------------------------------------------------------------- #
# 1. Does the GPU actually compute?
# --------------------------------------------------------------------------- #


def test_cuda_actually_computes(device_info: Any) -> None:
    """Real kernels, real numbers. ``is_available()`` is not evidence on sm_120."""
    torch = _torch()
    if device_info.kind != "cuda":
        pytest.skip(f"Sem GPU utilizavel: {device_info.failure_reason}")

    assert device_info.usable, device_info.failure_reason
    capability = device_info.capability
    assert capability is not None
    assert capability == (12, 0), f"Esperado Blackwell sm_120, obtido sm_{capability}"
    assert device_info.cuda_build is not None and device_info.cuda_build >= (12, 8), (
        f"Blackwell exige rodas cu128; esta e cu{device_info.cuda_build} (SPEC R1)."
    )
    assert "sm_120" in torch.cuda.get_arch_list(), (
        "A roda nao traz kernels sm_120: o modo de falha e 'no kernel image is available'."
    )

    generator = torch.Generator().manual_seed(20260907)
    left = torch.randn(512, 384, generator=generator, dtype=torch.float32)
    right = torch.randn(384, 256, generator=generator, dtype=torch.float32)
    expected = left @ right
    got = (left.cuda() @ right.cuda()).cpu()
    error = (expected - got).abs().max().item()
    assert error < 1e-3, f"matmul fp32 divergiu na GPU: max abs err {error}"
    assert got.abs().sum().item() > 0.0, "matmul devolveu zeros -- kernel nao executou"

    # A conv, because that is what the classifier is made of.
    weight = torch.randn(32, 1, 3, 3, generator=generator, dtype=torch.float32)
    image = torch.randn(8, 1, 64, 64, generator=generator, dtype=torch.float32)
    reference = torch.nn.functional.conv2d(image, weight, padding=1)
    on_gpu = torch.nn.functional.conv2d(image.cuda(), weight.cuda(), padding=1).cpu()
    conv_error = (reference - on_gpu).abs().max().item()
    assert conv_error < 1e-3, f"conv2d fp32 divergiu na GPU: max abs err {conv_error}"
    print(f"\ncuda fp32: matmul max abs err {error:.3e}, conv2d max abs err {conv_error:.3e}")


# --------------------------------------------------------------------------- #
# 2. Preprocessing
# --------------------------------------------------------------------------- #


def test_preprocess_is_byte_identical_to_trunk(crops: list[np.ndarray]) -> None:
    """The whole-board shortcut must produce the trunk's bytes, not near them."""
    from chess_diagram_ocr.model import DEFAULT_ARCH

    worst = 0.0
    differing = 0
    total = 0
    for board in crops:
        report = assert_equivalent_to_trunk(np.ascontiguousarray(board), DEFAULT_ARCH)
        worst = max(worst, report["max_abs_diff"])
        differing += int(report["differing"])
        total += int(report["count"])
    print(f"\npreprocess: max abs diff {worst}, {differing}/{total} valores diferentes")
    assert worst == 0.0
    assert differing == 0


# --------------------------------------------------------------------------- #
# 3. Batching alone, no device change
# --------------------------------------------------------------------------- #


def test_batched_cpu_matches_trunk_per_board(
    crops: list[np.ndarray], cpu_model: tuple[Any, str], cpu_reference: list[dict[str, Any]]
) -> None:
    """Batching a whole page must not move a single square, on the same device."""
    model, device = cpu_model
    classifier = BatchedClassifier(model, device, dtype="fp32", pin_memory=False)
    report = _compare(cpu_reference, _accelerated_readings(classifier, crops))
    print("\ncpu batched vs trunk:", json.dumps(report, ensure_ascii=False))
    assert report["fen_mismatches"] == 0
    assert report["class_square_mismatches"] == 0
    assert report["argmax_square_mismatches"] == 0
    assert report["rotation_mismatches"] == 0


# --------------------------------------------------------------------------- #
# 4. The gate: GPU fp32 against CPU fp32
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def gpu_fp32(model_path: Path, device_info: Any) -> BatchedClassifier:
    if device_info.kind != "cuda" or not device_info.usable:
        pytest.skip(f"Sem GPU utilizavel: {device_info.failure_reason}")
    classifier = load_classifier(model_path, prefer="cuda", dtype="fp32")
    classifier.warmup(128)
    return classifier


def test_gpu_fp32_matches_cpu_fp32(
    crops: list[np.ndarray], cpu_reference: list[dict[str, Any]], gpu_fp32: BatchedClassifier
) -> None:
    report = _compare(cpu_reference, _accelerated_readings(gpu_fp32, crops))
    print("\ngpu fp32 vs cpu fp32:", json.dumps(report, ensure_ascii=False))
    assert report["fen_mismatches"] == 0, report["fen_examples"]
    assert report["class_square_mismatches"] == 0
    assert report["argmax_square_mismatches"] == 0
    assert report["rotation_mismatches"] == 0


# --------------------------------------------------------------------------- #
# 5. fp16, measured rather than assumed
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def gpu_fp16(model_path: Path, device_info: Any) -> BatchedClassifier:
    if device_info.kind != "cuda" or not device_info.usable:
        pytest.skip(f"Sem GPU utilizavel: {device_info.failure_reason}")
    classifier = load_classifier(model_path, prefer="cuda", dtype="fp16")
    classifier.warmup(128)
    return classifier


def test_gpu_fp16_parity(
    crops: list[np.ndarray],
    cpu_reference: list[dict[str, Any]],
    gpu_fp16: BatchedClassifier,
    parity_out: Path,
) -> None:
    """fp16 ships only if no FEN moves. The number goes in the report either way.

    The report used to land straight in ``benchmarks/reports/``, so every
    ``pytest tests`` run rewrote a published file that critique documents cite by
    name and by sha256. The F9 cycle-15 critic found it the only way it could be
    found: by watching its own suite run do it. The report is still written; the
    destination now comes from the ``parity_out`` fixture, which defaults to the
    test's ``tmp_path`` and leaves it only when ``--parity-out`` says so.
    """
    report = _compare(cpu_reference, _accelerated_readings(gpu_fp16, crops))
    print("\ngpu fp16 vs cpu fp32:", json.dumps(report, ensure_ascii=False))
    parity_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    assert report["fen_mismatches"] == 0, (
        f"fp16 mudou {report['fen_mismatches']} FEN(s) em {report['boards']} tabuleiros; "
        f"nao embarcar fp16 neste caminho. Detalhes em {parity_out}"
    )
    assert report["argmax_square_mismatches"] == 0, (
        f"fp16 mudou o argmax de {report['argmax_square_mismatches']} casas em "
        f"{report['squares']}; o FEN sobreviveu por causa da decodificacao com restricoes, "
        "o que e exatamente o mascaramento que este teste existe para nao aceitar."
    )


# --------------------------------------------------------------------------- #
# 6. VRAM discipline (ADR-0004)
# --------------------------------------------------------------------------- #


def test_peak_vram_within_budget(crops: list[np.ndarray], gpu_fp32: BatchedClassifier) -> None:
    torch = _torch()
    gpu_fp32.reset_peak_vram()
    _accelerated_readings(gpu_fp32, crops[:64])
    peak = gpu_fp32.peak_vram_bytes()
    reserved = int(torch.cuda.max_memory_reserved())
    print(
        f"\npeak VRAM: allocated {peak / 1024**2:.1f} MiB, reserved {reserved / 1024**2:.1f} MiB "
        f"(orcamento ADR-0004 {VRAM_BUDGET_BYTES / 1024**3:.1f} GiB, compartilhado)"
    )
    assert 0 < peak < VRAM_BUDGET_BYTES
    assert reserved < VRAM_BUDGET_BYTES


# --------------------------------------------------------------------------- #
# 7. The shipped page-level entry point against the untouched service
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def field_pages() -> list[tuple[Path, int]]:
    """A handful of real annotated pages, for an end-to-end comparison."""
    from benchmarks.bench_recognition import field_set_pages

    pages = field_set_pages(limit=12)
    if not pages:
        pytest.skip("Acervo em PDF/ ausente.")
    return [(p.pdf, p.index) for p in pages]


def test_recognize_page_batched_matches_service(
    field_pages: list[tuple[Path, int]], model_path: Path, gpu_fp32: BatchedClassifier
) -> None:
    """``recognize_page_batched`` must return what ``OcrService.recognize_page`` returns.

    This is the API the rest of Caissa will call, so it is checked against the
    trunk's own entry point rather than against an internal of the fast path --
    placement, side to move and chosen rotation, page by page.
    """
    from chess_diagram_ocr.board_detection import NoBoardDetectedError
    from chess_diagram_ocr.config import DEFAULT_MODEL_PATH
    from chess_diagram_ocr.inference import load_model
    from chess_diagram_ocr.service import OcrService, RecognitionOptions

    from caissa.vision.classify import recognize_page_batched

    options = RecognitionOptions(model_path=model_path, max_boards=12, dpi=220)
    service = OcrService(model_path=model_path, loader=lambda p: load_model(p, device="cpu"))
    service.load(model_path)
    assert DEFAULT_MODEL_PATH  # the trunk's config is importable; keeps the linter honest

    compared = 0
    for pdf, index in field_pages:
        try:
            reference = service.recognize_page(pdf, index, options=options)
        except NoBoardDetectedError:
            reference = []
        try:
            fast = recognize_page_batched(pdf, index, gpu_fp32, options=options)
        except NoBoardDetectedError:
            fast = []

        assert len(reference) == len(fast), f"{pdf.name}#{index}: contagem de diagramas mudou"
        for want, got in zip(reference, fast, strict=True):
            assert want.placement == got.placement, f"{pdf.name}#{index}"
            assert want.side_to_move == got.side_to_move, f"{pdf.name}#{index}"
            assert want.rotation == got.rotation, f"{pdf.name}#{index}"
            compared += 1
    print(f"\nrecognize_page_batched: {compared} diagramas identicos ao OcrService")
    assert compared > 0
