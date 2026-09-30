"""Closing the cycle correct → measure → improve, one book at a time — C6/X6.

``OCR_UI_ANALISE_C2.md`` §7.6: the corrections existed (the review queue's log, the
labelling project's lines, the window's saved positions, the diagram decisions) and every
use of them was a manual step somebody had to remember.  This module is the one command
that consumes them, and it consumes them under the one rule nobody may break: **a page of
the blind partition contributes nothing** (:func:`caissa.ocr.review.blind_guard`).

What one closure does, for one PDF:

1. **Collects the text corrections** — the labelling project's decided lines
   (:func:`caissa.ocr.labeling.export.calibration_pairs`, per-word confidence) and the
   review queue's log (:meth:`caissa.ocr.review.ReviewQueue.corrections`, region score) —
   and writes them as a **calibration manifest**: one JSONL of ``(engine, facet, raw
   confidence, correct)`` pairs the SOL-4 calibration can be refitted from.  Blind pages
   are withheld and counted.
2. **Collects the diagram corrections** — the trunk's ``labels.csv`` rows that came from
   this book with a human procedure (accepted, corrected, transcribed, second opinion)
   and the window's diagram decisions (:mod:`caissa.ocr.diagram_decisions`) — measures
   the ink of every occupied square (:mod:`chess_diagram_ocr.cor_por_livro`) and builds
   the book's **colour calibrator** (C5).  Blind pages withheld.
3. **Measures before/after** on those same diagrams, leave-one-out: each board is read by
   the production classifier with no calibrator (before) and with the calibrator built
   from the *other* boards (after); the report says exact boards, colour squares fixed
   and colour squares broken.
4. **Records identity** — classifier fingerprint, ``labels.csv`` hash, suite commit,
   document hash — and writes ``perfil.proposto.json``.  With approval (``--aprovar``)
   the proposal becomes ``perfil.json`` and a :class:`~caissa.ocr.book_profile.ClosureRecord`
   is appended to the history.  Without it, nothing the product reads changes.

Nothing here retrains a model, moves a threshold or touches the golden manifest.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ocr.book_profile import BookProfile, ClosureRecord, profile_path
from caissa.ocr.review import BlindGuard, blind_guard

LOGGER = logging.getLogger("caissa.ocr.closing")

__all__ = [
    "HUMAN_PROCEDURES",
    "ClosureOutcome",
    "DiagramTruth",
    "close_cycle",
    "collect_diagram_truths",
    "collect_text_pairs",
    "default_blind_guard",
    "field_pages_of",
]

#: ``labels.csv`` procedures that mean a person settled the position.  An empty
#: ``corrected_by`` is a legacy row of unknown provenance and is never used.
HUMAN_PROCEDURES = frozenset({"ocr-aceito", "ocr-corrigido", "transcricao-manual", "segunda-opiniao"})
PROPOSAL_FILE = "perfil.proposto.json"
MANIFEST_DIR = "fechamento"


@dataclass(slots=True)
class DiagramTruth:
    """One human-settled board of the book: the image and the placement."""

    image_path: Path
    placement: str
    page_index: int | None
    source: str
    """``labels.csv`` or ``decisao`` (the window's diagram decision)."""
    procedure: str = ""


@dataclass(slots=True)
class ClosureOutcome:
    """Everything one closure did, for the report and the tests."""

    pdf: Path
    fingerprint: str = ""
    profile_path: Path | None = None
    proposal_path: Path | None = None
    manifest_path: Path | None = None
    text_pairs: int = 0
    text_regions: int = 0
    text_withheld: int = 0
    diagrams: int = 0
    diagrams_withheld: int = 0
    colour_samples: tuple[int, int] = (0, 0)
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    model_identity: str = ""
    dataset_version: str = ""
    suite_commit: str = ""
    approved: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def withheld(self) -> int:
        return self.text_withheld + self.diagrams_withheld

    def describe_pt(self) -> str:
        lines = [
            f"Fechamento de ciclo — {self.pdf.name}",
            f"  documento {self.fingerprint[:12] or '?'} · modelo {self.model_identity[:12] or '?'} · "
            f"rótulos {self.dataset_version[:12] or '?'} · suíte {self.suite_commit[:10] or '?'}",
            f"  texto: {self.text_pairs} pares de calibração em {self.text_regions} região(ões)"
            + (f"; {self.text_withheld} decisão(ões) retida(s) pela partição cega" if self.text_withheld else ""),
            f"  diagramas: {self.diagrams} corrigido(s) → calibrador de cor com "
            f"{self.colour_samples[0]} brancas e {self.colour_samples[1]} pretas"
            + (f"; {self.diagrams_withheld} retido(s) (partição cega ou página do conjunto de campo)"
               if self.diagrams_withheld else ""),
        ]
        if self.before or self.after:
            lines.append(f"  antes:  {_fmt(self.before)}")
            lines.append(f"  depois: {_fmt(self.after)}")
        if self.manifest_path is not None:
            lines.append(f"  manifesto: {self.manifest_path}")
        lines.append(f"  proposta: {self.proposal_path}" if self.proposal_path else "  proposta: nenhuma")
        lines.append("  perfil gravado (aprovado)." if self.approved
                     else "  perfil NÃO alterado: aprove com --aprovar para gravar.")
        lines.extend(f"  nota: {note}" for note in self.notes)
        return "\n".join(lines)


def _fmt(measure: dict[str, Any]) -> str:
    if not measure:
        return "não medido"
    return (f"{measure.get('exact', 0)}/{measure.get('boards', 0)} exatos, "
            f"{measure.get('colour_wrong', 0)} casa(s) de cor errada"
            + (f", {measure.get('colour_repaired', 0)} trocada(s) pela tinta"
               f" ({measure.get('colour_repaired_right', 0)} certas)" if "colour_repaired" in measure else ""))


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


def default_blind_guard(manifest: Path | None = None) -> BlindGuard:
    """The guard from the golden manifest on this machine, or one that withholds nothing.

    The private manifest when it exists, else the versioned public one — the same
    order ``bench_sol`` uses.
    """
    from caissa.ocr.golden import load_manifest

    candidates = [manifest] if manifest is not None else []
    root = Path(__file__).resolve().parents[3]
    candidates += [root / "benchmarks" / "corpus" / "golden" / "manifest.private.json",
                   root / "benchmarks" / "corpus" / "golden" / "manifest.json"]
    for path in candidates:
        if path is not None and path.is_file():
            try:
                return blind_guard(i.id for i in load_manifest(path, include_blind=True).items)
            except (OSError, ValueError):
                continue
    return blind_guard(())


def _suite_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parents[3], timeout=10, check=False)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _labels_hash(labels_csv: Path) -> str:
    """SHA-256 of the ``(filename, fen)`` pairs, sorted — the trunk's ``labels_hash`` rule."""
    if not labels_csv.is_file():
        return ""
    digest = hashlib.sha256()
    with labels_csv.open(encoding="utf-8", newline="") as handle:
        pairs = sorted((row.get("filename", ""), row.get("fen", "")) for row in csv.DictReader(handle))
    for filename, fen in pairs:
        digest.update(f"{filename}\t{fen}\n".encode())
    return digest.hexdigest()


def _model_identity(model_path: Path | None) -> str:
    try:
        from caissa.vision.classify.cvoff import ensure_cvoff_on_path, trunk_model_path

        ensure_cvoff_on_path()
        from chess_diagram_ocr.checkpoint import checkpoint_fingerprint

        path = model_path or trunk_model_path()
        return checkpoint_fingerprint(path) if Path(path).is_file() else ""
    except Exception:  # noqa: BLE001 - identity is a courtesy, never a failure
        return ""


# --------------------------------------------------------------------------- #
# Text: calibration pairs
# --------------------------------------------------------------------------- #


def collect_text_pairs(pdf_path: Path, *, blind: BlindGuard, project_dir: Path | None = None,
                       queue_path: Path | None = None) -> tuple[list[dict[str, Any]], int, int]:
    """``(rows, regions, withheld)``: the calibration pairs of this book's corrections.

    From the labelling project (per-word confidence; its own blind rule already applied
    per region) and from the review queue's log (region score for every word — the queue
    item keeps no confidence per word, and the row says so in ``granularity``).
    """
    stem = pdf_path.stem
    rows: list[dict[str, Any]] = []
    regions = 0
    withheld = 0

    project_root = project_dir
    if project_root is None:
        from caissa.ocr.labeling.helpers import default_project_dir

        project_root = default_project_dir()
    project_file = project_root / "project.json"
    if project_file.is_file():
        try:
            from caissa.ocr.labeling.export import calibration_pairs
            from caissa.ocr.labeling.model import LabelProject

            project = LabelProject.load(project_root)
            pages = {key: page for key, page in project.pages.items() if page.document == stem}
            if pages:
                project.pages = pages
                for entry in calibration_pairs(project):
                    regions += 1
                    rows.append({**entry, "source": "rotulagem", "granularity": "word", "document": stem})
        except Exception as exc:  # noqa: BLE001 - a broken project is a note, not a stop
            rows.append({"source": "rotulagem", "error": str(exc), "document": stem})

    queue_file = queue_path
    if queue_file is None:
        from caissa.ocr.review import decisions_path

        queue_file = decisions_path(pdf_path).with_suffix(".fila.json")
    if queue_file.is_file():
        from caissa.ocr.calibration import pairs_from_alignment
        from caissa.ocr.review import ReviewQueue

        queue = ReviewQueue.load(queue_file, blind=blind)
        for correction in queue.corrections():
            hypothesis = correction["hypothesis"].split()
            score = float(next((i.score for i in queue.items
                                if i.document == correction["document"]
                                and i.page_index == correction["page_index"]
                                and list(i.rect) == list(correction["rect"])), 0.0))
            pairs = pairs_from_alignment(((w, score) for w in hypothesis), correction["truth"].split())
            if pairs:
                regions += 1
                rows.append({"engine": correction["engine"], "kind": correction["kind"],
                             "page_index": correction["page_index"], "source": "fila",
                             "granularity": "region", "document": stem,
                             "pairs": [[round(c, 4), ok] for c, ok in pairs]})
        withheld += queue.withheld()
    return rows, regions, withheld


def _write_manifest(rows: Sequence[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


# --------------------------------------------------------------------------- #
# Diagrams: human truths and the colour calibrator
# --------------------------------------------------------------------------- #


def _same_book(source_pdf: str, pdf_path: Path) -> bool:
    return bool(source_pdf) and Path(source_pdf).name.lower() == pdf_path.name.lower()


def field_pages_of(pdf_path: Path, field_set: Path | None = None) -> set[int]:
    """The pages of this book in the trunk's field set (``data/field_set.jsonl``).

    The field set is the measurement; a profile learnt from its pages would measure itself.
    The trunk's ``labels.pages_with_training_samples`` counts that contamination for the
    classifier; this is the same rule for the profile.
    """
    path = field_set
    if path is None:
        try:
            from caissa.vision.classify.cvoff import cvoff_root

            path = cvoff_root() / "data" / "field_set.jsonl"
        except FileNotFoundError:
            return set()
    if not path.is_file():
        return set()
    pages: set[int] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if _same_book(str(entry.get("pdf", "")), pdf_path):
                pages.add(int(entry.get("page", -1)))
    return pages


def _page_index_of_label(source_page: str | None) -> int | None:
    """The 0-based page of a ``labels.csv`` row (``source_page`` is 1-based), or ``None``."""
    text = (source_page or "").strip()
    try:
        page = int(float(text))
    except ValueError:
        return None
    return page - 1 if page >= 1 else None


def collect_diagram_truths(pdf_path: Path, *, blind: BlindGuard, labels_csv: Path | None,
                           samples_dir: Path | None, decisions: Any = None,
                           render: Callable[[int, tuple[float, float, float, float]], Path | None] | None = None,
                           max_diagrams: int | None = None,
                           field_pages: set[int] | None = None) -> tuple[list[DiagramTruth], int]:
    """``(truths, withheld)``: the human-settled boards of this book, blind pages withheld.

    ``labels.csv`` rows of the trunk (a saved sample is a warped 800×800 crop) and the
    window's diagram decisions (rendered through ``render(page, rect) -> image path``
    when given).  ``max_diagrams`` keeps the first *k* in file order — the knob of the
    measurement (k = 3, 6, 12).  ``field_pages`` (the trunk's field set by default) are
    withheld like blind ones: the field set measures the profile, it never feeds it.

    **Page base.** ``labels.csv`` writes ``source_page`` as the window shows it, **1-based**
    (the trunk's ``labels.pages_with_training_samples`` subtracts one for the same reason);
    the field set, the golden manifest and the window's decisions are 0-based.  Every page
    here is 0-based, so a label's page is ``source_page - 1``.  Measured before the rule: the
    two Koblenz boards of field page 50 were kept (labelled ``51``) and two boards of page 49
    were withheld in their place — the profile measured itself.
    """
    stem = pdf_path.stem
    truths: list[DiagramTruth] = []
    withheld = 0
    field = field_pages if field_pages is not None else field_pages_of(pdf_path)

    def _withheld(page_index: int | None) -> bool:
        if page_index is None:
            return False
        return blind(stem, page_index) or page_index in field
    if labels_csv is not None and labels_csv.is_file() and samples_dir is not None:
        with labels_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if not _same_book(row.get("source_pdf", ""), pdf_path):
                    continue
                if (row.get("corrected_by") or "") not in HUMAN_PROCEDURES:
                    continue
                page_index = _page_index_of_label(row.get("source_page"))
                if _withheld(page_index):
                    withheld += 1
                    continue
                image = samples_dir / row["filename"]
                if not image.is_file():
                    continue
                truths.append(DiagramTruth(image, row["fen"].split()[0], page_index, "labels.csv",
                                           row.get("corrected_by", "")))
    if decisions is not None and render is not None:
        for decision in decisions.items:
            if _withheld(decision.page_index):
                withheld += 1
                continue
            image = render(decision.page_index, decision.rect)
            if image is None:
                continue
            truths.append(DiagramTruth(image, decision.fen.split()[0], decision.page_index, "decisao",
                                       decision.source or "janela"))
    if max_diagrams is not None:
        truths = truths[:max_diagrams]
    return truths, withheld


def _colour_samples(truths: Iterable[DiagramTruth]) -> tuple[dict[str, list[float]], dict[str, list[float]], int]:
    """The ink measure of every occupied square of the truths, per piece type:
    ``(whites, blacks, boards)``.
    """
    from caissa.vision.classify.cvoff import ensure_cvoff_on_path

    ensure_cvoff_on_path()
    import cv2
    from chess_diagram_ocr.board_detection import split_board_into_cells
    from chess_diagram_ocr.cor_por_livro import amostras_do_tabuleiro
    from chess_diagram_ocr.fen_utils import labels_from_fen

    whites: dict[str, list[float]] = {}
    blacks: dict[str, list[float]] = {}
    boards = 0
    for truth in truths:
        image = cv2.imread(str(truth.image_path))
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        try:
            labels = labels_from_fen(truth.placement)
        except Exception as exc:  # noqa: BLE001 - a bad FEN in a label is skipped, not fatal
            LOGGER.warning("rótulo com FEN inválida ignorado (%s): %s", truth.image_path.name, exc)
            continue
        w, b = amostras_do_tabuleiro(split_board_into_cells(image), labels)
        for tipo, valores in w.items():
            whites.setdefault(tipo, []).extend(valores)
        for tipo, valores in b.items():
            blacks.setdefault(tipo, []).extend(valores)
        boards += 1
    return whites, blacks, boards


def _measure(truths: Sequence[DiagramTruth], model_path: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Before/after on the truths, leave-one-out: the classifier alone, then with the
    calibrator built from the *other* boards.
    """
    from caissa.vision.classify.cvoff import ensure_cvoff_on_path

    ensure_cvoff_on_path()
    import cv2
    import numpy as np
    from chess_diagram_ocr.board_detection import split_board_into_cells
    from chess_diagram_ocr.config import PIECE_CLASSES
    from chess_diagram_ocr.cor_por_livro import (
        CalibradorDeCor,
        amostras_do_tabuleiro,
        trocas_de_cor,
    )
    from chess_diagram_ocr.fen_utils import labels_from_fen
    from chess_diagram_ocr.inference import load_model, predict_board

    if model_path is None:
        from chess_diagram_ocr.config import DEFAULT_MODEL_PATH

        model_path = Path(DEFAULT_MODEL_PATH)
    model, device = load_model(model_path)
    boards: list[tuple[list[np.ndarray], list[int], Any]] = []
    for truth in truths:
        image = cv2.imread(str(truth.image_path))
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (800, 800))
        labels = labels_from_fen(truth.placement)
        prediction = predict_board(image, model, device)
        boards.append((split_board_into_cells(image), labels, prediction))

    def colour_wrong(read: Sequence[int], labels: Sequence[int]) -> int:
        return sum(1 for r, t in zip(read, labels, strict=True)
                   if r != t and PIECE_CLASSES[r] != "empty" and PIECE_CLASSES[t] != "empty"
                   and PIECE_CLASSES[r].lower() == PIECE_CLASSES[t].lower())

    before = {"boards": len(boards), "exact": 0, "colour_wrong": 0}
    after = {"boards": len(boards), "exact": 0, "colour_wrong": 0, "colour_repaired": 0,
             "colour_repaired_right": 0}
    for index, (cells, labels, prediction) in enumerate(boards):
        read = list(prediction.class_indices)
        before["exact"] += int(read == list(labels))
        before["colour_wrong"] += colour_wrong(read, labels)
        whites: dict[str, list[float]] = {}
        blacks: dict[str, list[float]] = {}
        for other, (o_cells, o_labels, _) in enumerate(boards):
            if other == index:
                continue
            w, b = amostras_do_tabuleiro(o_cells, o_labels)
            for tipo, valores in w.items():
                whites.setdefault(tipo, []).extend(valores)
            for tipo, valores in b.items():
                blacks.setdefault(tipo, []).extend(valores)
        calibrador = CalibradorDeCor(brancas=whites, pretas=blacks, diagramas=len(boards) - 1)
        trocas = trocas_de_cor(prediction.probs, read, cells, calibrador)
        repaired = list(read)
        for troca in trocas:
            repaired[troca.casa] = troca.para
            after["colour_repaired"] += 1
            after["colour_repaired_right"] += int(labels[troca.casa] == troca.para)
        after["exact"] += int(repaired == list(labels))
        after["colour_wrong"] += colour_wrong(repaired, labels)
    return before, after


# --------------------------------------------------------------------------- #
# The closure
# --------------------------------------------------------------------------- #


def close_cycle(
    pdf_path: Path | str,
    *,
    approve: bool = False,
    blind: BlindGuard | None = None,
    labels_csv: Path | None = None,
    samples_dir: Path | None = None,
    model_path: Path | None = None,
    project_dir: Path | None = None,
    queue_path: Path | None = None,
    decisions: Any = None,
    render: Callable[[int, tuple[float, float, float, float]], Path | None] | None = None,
    max_diagrams: int | None = None,
    measure: bool = True,
    profile_root: Path | None = None,
    manifest_dir: Path | None = None,
    now: datetime | None = None,
) -> ClosureOutcome:
    """Close one cycle for ``pdf_path``; see the module docstring for the steps.

    ``labels_csv``/``samples_dir`` default to the trunk's ``data/`` when the trunk is
    reachable; ``blind`` defaults to the golden manifest's guard.  ``approve=False`` writes
    the proposal only.
    """
    pdf = Path(pdf_path)
    outcome = ClosureOutcome(pdf=pdf)
    guard = blind if blind is not None else default_blind_guard()
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d_%H%M%S")

    if labels_csv is None or samples_dir is None:
        try:
            from caissa.vision.classify.cvoff import cvoff_root

            root = cvoff_root()
            labels_csv = labels_csv or root / "data" / "labels.csv"
            samples_dir = samples_dir or root / "data" / "samples"
        except FileNotFoundError:
            outcome.notes.append("tronco não encontrado: sem rótulos de diagramas")

    # 1. identity
    from caissa.ocr.training.books import pdf_fingerprint

    outcome.fingerprint = pdf_fingerprint(pdf) if pdf.is_file() else ""
    outcome.model_identity = _model_identity(model_path)
    outcome.dataset_version = _labels_hash(labels_csv) if labels_csv is not None else ""
    outcome.suite_commit = _suite_commit()

    # 2. text corrections → calibration manifest
    rows, regions, text_withheld = collect_text_pairs(pdf, blind=guard, project_dir=project_dir,
                                                      queue_path=queue_path)
    outcome.text_regions = regions
    outcome.text_withheld = text_withheld
    outcome.text_pairs = sum(len(row.get("pairs", ())) for row in rows)
    if rows:
        target_dir = manifest_dir
        if target_dir is None:
            from caissa.ocr.labeling.helpers import default_project_dir

            target_dir = default_project_dir() / MANIFEST_DIR
        outcome.manifest_path = _write_manifest(
            [{"document": pdf.stem, "fingerprint": outcome.fingerprint, "model_identity": outcome.model_identity,
              "dataset_version": outcome.dataset_version, "suite_commit": outcome.suite_commit,
              "at": stamp, "kind": "header"}, *rows],
            target_dir / f"{pdf.stem[:40]}_{stamp}.jsonl")

    # 3. diagram corrections → colour calibrator
    truths, diagrams_withheld = collect_diagram_truths(
        pdf, blind=guard, labels_csv=labels_csv, samples_dir=samples_dir, decisions=decisions,
        render=render, max_diagrams=max_diagrams)
    outcome.diagrams = len(truths)
    outcome.diagrams_withheld = diagrams_withheld
    colour: dict[str, Any] | None = None
    if truths:
        whites, blacks, boards = _colour_samples(truths)
        outcome.colour_samples = (sum(len(v) for v in whites.values()), sum(len(v) for v in blacks.values()))
        from caissa.vision.classify.cvoff import ensure_cvoff_on_path

        ensure_cvoff_on_path()
        from chess_diagram_ocr.cor_por_livro import CalibradorDeCor

        colour = CalibradorDeCor(brancas=whites, pretas=blacks, diagramas=boards).as_dict()
        if measure and boards >= 2:
            try:
                outcome.before, outcome.after = _measure(truths, model_path)
            except Exception as exc:  # noqa: BLE001 - the measurement is a courtesy; the profile is the deliverable
                outcome.notes.append(f"medição antes/depois não rodou: {exc}")
    else:
        outcome.notes.append("nenhum diagrama corrigido deste livro fora da partição cega")

    # 4. the proposal, and the profile on approval
    path = profile_path(pdf, root=profile_root)
    outcome.profile_path = path
    current = BookProfile.load(path, fingerprint=outcome.fingerprint) or BookProfile.fresh(pdf) if pdf.is_file() \
        else BookProfile(document=pdf.stem)
    proposal = BookProfile(
        fingerprint=outcome.fingerprint or current.fingerprint, document=pdf.stem,
        model_identity=outcome.model_identity, dataset_version=outcome.dataset_version,
        suite_commit=outcome.suite_commit, ocr_config=dict(current.ocr_config),
        colour=colour if colour is not None else current.colour, history=list(current.history),
    )
    record = ClosureRecord(
        at=stamp, corrections_text=outcome.text_regions, corrections_diagrams=outcome.diagrams,
        withheld=outcome.withheld, manifest=str(outcome.manifest_path or ""),
        model_identity=outcome.model_identity, dataset_version=outcome.dataset_version,
        before=dict(outcome.before), after=dict(outcome.after), approved=approve,
    )
    proposal.history.append(record)
    outcome.proposal_path = proposal.save(path.with_name(PROPOSAL_FILE))
    if approve:
        proposal.save(path)
        outcome.approved = True
    return outcome


def main(argv: Sequence[str] | None = None) -> int:
    """``caissa-fechar-ciclo <pdf> [--aprovar] [--max-diagramas K] [--sem-medir]``."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__ and __doc__.split("\n", 1)[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--aprovar", action="store_true", help="grava o perfil (sem isto só a proposta)")
    parser.add_argument("--max-diagramas", type=int, default=None, help="usa só os K primeiros diagramas corrigidos")
    parser.add_argument("--sem-medir", action="store_true", help="não roda o antes/depois")
    parser.add_argument("--modelo", type=Path, default=None)
    parser.add_argument("--manifesto", type=Path, default=None, help="manifesto dourado para a guarda cega")
    parser.add_argument("--json", type=Path, default=None, help="grava o resultado em JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)

    outcome = close_cycle(args.pdf, approve=args.aprovar, max_diagrams=args.max_diagramas,
                          measure=not args.sem_medir, model_path=args.modelo,
                          blind=default_blind_guard(args.manifesto) if args.manifesto else None)
    print(outcome.describe_pt())
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        data = {k: (str(v) if isinstance(v, Path) else v) for k, v in outcome.__dict__.items()} \
            if not hasattr(outcome, "__slots__") else {
                name: (str(getattr(outcome, name)) if isinstance(getattr(outcome, name), Path)
                       else getattr(outcome, name)) for name in outcome.__slots__}
        args.json.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
