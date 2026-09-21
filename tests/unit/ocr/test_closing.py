"""C6 (ciclo 2): closing the cycle correct → measure → improve, one book at a time.

What has to hold: the corrections of a book become a calibration manifest and a colour
calibrator in the book's profile; a decision on a page of the blind partition (or of the
field set) contributes nothing and is counted; nothing the product reads changes without
approval; and the identity (document hash, model, labels, suite commit) is recorded.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from caissa.ocr.book_profile import BookProfile, profile_path
from caissa.ocr.closing import (
    HUMAN_PROCEDURES,
    close_cycle,
    collect_diagram_truths,
    collect_text_pairs,
    field_pages_of,
)
from caissa.ocr.golden import Partition, partition_for
from caissa.ocr.review import Action, ReviewItem, ReviewQueue, blind_guard


def _blind_id(book: str, page: int) -> str:
    """A manifest id of this page that the partition rule calls blind (the rule hashes the id)."""
    for region in range(500):
        item_id = f"real:{book}:{page}:{region}"
        if partition_for(item_id) is Partition.BLIND:
            return item_id
    raise AssertionError("nenhum id cego em 500 regiões")


PLACEMENT = "r4rk1/1p3ppp/p2q4/3p4/3P4/2N2N2/PP3PPP/R2Q1RK1"


def _board(path: Path) -> None:
    board = np.full((800, 800, 3), 235, dtype=np.uint8)
    cv2.imwrite(str(path), board)


def _labels(root: Path, pdf: Path, rows: list[tuple[str, int, str]]) -> tuple[Path, Path]:
    samples = root / "samples"
    samples.mkdir()
    csv_path = root / "labels.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["filename", "fen", "side_to_move", "source_pdf", "source_page", "source_diagram",
                         "detection_source", "created_at", "corrected_by", "illegal_ok"])
        for name, page, procedure in rows:
            _board(samples / name)
            writer.writerow([name, f"{PLACEMENT} w - - 0 1", "w", str(pdf), page, 0, "contour", "", procedure, ""])
    return csv_path, samples


@pytest.fixture
def book(tmp_path: Path) -> Path:
    pdf = tmp_path / "Livro.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")
    return pdf


def test_a_blind_page_and_a_field_page_contribute_nothing(tmp_path: Path, book: Path):
    """The sabotage of the step: a decision on a blind page is withheld by ``blind_guard``.

    ``labels.csv`` writes the page as the window shows it (1-based: ``10`` is page index 9);
    the guard and the field set are 0-based.  Measured on the Koblenz before the rule: the
    two boards of field page 50 (labelled ``51``) fed the profile that measured them.
    """
    csv_path, samples = _labels(tmp_path, book, [
        ("a.png", 6, "ocr-corrigido"), ("b.png", 10, "ocr-corrigido"), ("c.png", 13, "transcricao-manual"),
        ("d.png", 21, ""),  # legacy row: no human procedure
    ])
    guard = blind_guard([_blind_id(book.stem[:24], 9)])  # page index 9 of this book is blind
    truths, withheld = collect_diagram_truths(book, blind=guard, labels_csv=csv_path, samples_dir=samples,
                                             field_pages={12})
    assert [t.page_index for t in truths] == [5]
    assert withheld == 2, "page 9 (blind) and page 12 (field set) are withheld and counted"
    assert all(t.procedure in HUMAN_PROCEDURES for t in truths)

    # Without the guard, page 9 would feed the profile: the guard is what stops it.
    truths, withheld = collect_diagram_truths(book, blind=blind_guard(()), labels_csv=csv_path,
                                              samples_dir=samples, field_pages=set())
    assert [t.page_index for t in truths] == [5, 9, 12] and withheld == 0

    # The off-by-one that fed the profile: a label on the field page itself, compared 1-based.
    truths, withheld = collect_diagram_truths(book, blind=blind_guard(()), labels_csv=csv_path,
                                              samples_dir=samples, field_pages={13})
    assert [t.page_index for t in truths] == [5, 9, 12] and withheld == 0, "13 is not a page of these labels"


def test_field_pages_come_from_the_trunks_field_set(tmp_path: Path, book: Path):
    field_set = tmp_path / "field_set.jsonl"
    field_set.write_text("\n".join([
        json.dumps({"pdf": book.name, "page": 30, "reviewed": True, "diagrams": []}),
        json.dumps({"pdf": "Outro.pdf", "page": 7, "reviewed": True, "diagrams": []}),
        json.dumps({"pdf": book.name, "page": 50, "reviewed": True, "diagrams": []}),
    ]) + "\n", encoding="utf-8")
    assert field_pages_of(book, field_set) == {30, 50}
    assert field_pages_of(book, tmp_path / "missing.jsonl") == set()


def test_text_corrections_become_calibration_pairs_minus_the_blind_page(tmp_path: Path, book: Path):
    queue = ReviewQueue(reviewer="ana")
    queue.blind = blind_guard([_blind_id(book.stem[:24], 3)])
    queue.items = [
        ReviewItem(key="Livro:p1:r0", document=book.stem, page_index=1, rect=(0.0, 0.0, 10.0, 10.0),
                   kind="movetext", decision="review", reasons=(), text="1.e4 e5 2.Nf3 Nc6", engine="tesseract",
                   score=0.7),
        ReviewItem(key="Livro:p3:r0", document=book.stem, page_index=3, rect=(0.0, 0.0, 10.0, 10.0),
                   kind="movetext", decision="review", reasons=(), text="3.Bb5 a6", engine="tesseract",
                   score=0.6),
    ]
    queue.open("Livro:p1:r0")
    queue.decide("Livro:p1:r0", Action.EDIT, text="1.e4 e5 2.Nf3 Nc6 3.Bb5")
    assert queue.refusal("Livro:p3:r0", Action.ACCEPT), "the window would refuse the blind page"
    # The sabotage: the decision is recorded anyway (a harness, an older window) -- the
    # closure withholds it all the same, and counts it.
    queue.open("Livro:p3:r0")
    queue.decide("Livro:p3:r0", Action.ACCEPT)
    queue_path = tmp_path / "fila.json"
    queue.save(queue_path)

    rows, regions, withheld = collect_text_pairs(book, blind=queue.blind, project_dir=tmp_path / "no-project",
                                                 queue_path=queue_path)
    assert regions == 1 and withheld == 1
    assert all(row["page_index"] == 1 for row in rows)
    assert rows[0]["source"] == "fila" and rows[0]["granularity"] == "region"
    assert rows[0]["pairs"] == [[0.7, True]] * 4, "four hypothesis words, all in the truth, at the region score"


def test_close_cycle_writes_a_proposal_and_only_approval_writes_the_profile(tmp_path: Path, book: Path):
    csv_path, samples = _labels(tmp_path, book, [(f"{i}.png", i, "ocr-corrigido") for i in range(1, 4)])
    root = tmp_path / "models"
    manifests = tmp_path / "fechamento"

    outcome = close_cycle(book, blind=blind_guard(()), labels_csv=csv_path, samples_dir=samples,
                          measure=False, profile_root=root, manifest_dir=manifests,
                          queue_path=tmp_path / "no-queue.json", project_dir=tmp_path / "no-project")
    assert outcome.diagrams == 3 and outcome.diagrams_withheld == 0
    assert outcome.colour_samples[0] > 0 and outcome.colour_samples[1] > 0
    assert outcome.fingerprint and outcome.dataset_version
    assert outcome.proposal_path is not None and outcome.proposal_path.exists()
    assert not outcome.approved
    assert BookProfile.load(profile_path(book, root=root)) is None, "the product reads nothing new yet"
    assert "NÃO alterado" in outcome.describe_pt()

    approved = close_cycle(book, approve=True, blind=blind_guard(()), labels_csv=csv_path, samples_dir=samples,
                           measure=False, profile_root=root, manifest_dir=manifests,
                           queue_path=tmp_path / "no-queue.json", project_dir=tmp_path / "no-project")
    profile = BookProfile.load(profile_path(book, root=root), fingerprint=approved.fingerprint)
    assert profile is not None and profile.colour is not None
    assert profile.colour["diagramas"] == 3 and profile.colour["medida"]
    assert profile.closures == 1 and profile.history[0].approved
    assert profile.history[0].corrections_diagrams == 3
    assert profile.model_identity == approved.model_identity
    assert profile.dataset_version == approved.dataset_version
    assert profile.describe_pt().startswith("perfil do livro: 1 fechamento(s)")


def test_a_book_without_corrections_proposes_nothing_of_colour(tmp_path: Path, book: Path):
    root = tmp_path / "models"
    csv_path, samples = _labels(tmp_path, book, [])
    outcome = close_cycle(book, blind=blind_guard(()), labels_csv=csv_path, samples_dir=samples, measure=False,
                          profile_root=root, manifest_dir=tmp_path / "f",
                          queue_path=tmp_path / "no-queue.json", project_dir=tmp_path / "no-project")
    assert outcome.diagrams == 0
    assert any("nenhum diagrama corrigido" in note for note in outcome.notes)
    proposal = BookProfile.load(outcome.proposal_path)
    assert proposal is not None and proposal.colour is None
