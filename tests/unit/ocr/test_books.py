"""A fine-tune belongs to one book: registered by content hash, applied to that
PDF by the importer and the labelling window, and to no other."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.ocr.training import (
    BookModel,
    BookRegistry,
    FineTuneConfig,
    FineTuneReport,
    book_dir,
    book_slug,
    models_root,
    pdf_fingerprint,
    register_training,
)
from caissa.ocr.training.tesseract_finetune import _index_rows, preflight

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _pdf(tmp_path: Path, name: str = "Dvoretsky SFC4.pdf", payload: bytes = b"%PDF-1.4 abc") -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def _trained(root: Path, document: str, *, lang: str = "eng") -> FineTuneReport:
    out = book_dir(root, document)
    out.mkdir(parents=True)
    model = out / f"caissa_{lang}.traineddata"
    model.write_bytes(b"model")
    return FineTuneReport(
        model_name=f"caissa_{lang}",
        out_dir=out,
        finished_at="2026-09-14T01:00:00+00:00",
        model_path=str(model),
        model_sha256="ab" * 32,
        lines_train=482,
        lines_eval=262,
        cer_before=10.2,
        cer_after=2.0,
        status="trained",
    )


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def test_book_slug_is_directory_safe_and_stable():
    assert book_slug("Dvoretsky & Yusupov — Secrets of Positional Play (1996)") == (
        "dvoretsky_yusupov_secrets_of_positional"
    )
    assert book_slug("!!!") == "livro"
    assert book_dir("models/tessdata", "Livro A") == Path("models/tessdata/livros/livro_a")


def test_fingerprint_is_the_content_hash_not_the_path(tmp_path: Path):
    a = _pdf(tmp_path, "a.pdf")
    b = _pdf(tmp_path, "b.pdf")
    other = _pdf(tmp_path, "a copy.pdf", b"%PDF-1.4 xyz")
    assert pdf_fingerprint(a) == pdf_fingerprint(b)
    assert pdf_fingerprint(a) != pdf_fingerprint(other)
    assert len(pdf_fingerprint(a)) == 64


def test_register_training_binds_the_model_to_the_pdf_and_round_trips(tmp_path: Path):
    root = tmp_path / "tessdata"
    pdf = _pdf(tmp_path)
    registry = BookRegistry.load(root / "livros.json")
    assert registry.for_pdf(pdf) is None, "no entries: nothing is hashed or found"

    book = register_training(registry, pdf, "Dvoretsky SFC4", _trained(root, "Dvoretsky SFC4"))
    assert book.models == ("caissa_eng",)
    assert book.base_lang == "eng"
    assert book.tessdata_dir == str(book_dir(root, "Dvoretsky SFC4").resolve())
    assert "CER avaliação 10.2 → 2.0 %" in book.describe()
    assert "482 linhas de treino" in book.describe()

    again = BookRegistry.load(root / "livros.json")
    found = again.for_pdf(pdf)
    assert found is not None and found.fingerprint == pdf_fingerprint(pdf)
    # A copy of the same book elsewhere finds the model; another book does not.
    (tmp_path / "elsewhere").mkdir()
    assert again.for_pdf(_pdf(tmp_path / "elsewhere", "renamed.pdf")) is not None
    assert again.for_pdf(_pdf(tmp_path, "other.pdf", b"%PDF-1.4 other")) is None
    assert again.for_pdf(tmp_path / "missing.pdf") is None
    assert again.for_document("Dvoretsky SFC4") is not None
    assert again.for_document("Chernev") is None
    payload = json.loads((root / "livros.json").read_text("utf-8"))
    assert payload["version"] == 1
    assert payload["books"][0]["models"] == ["caissa_eng"]


def test_a_model_moved_away_is_not_offered(tmp_path: Path):
    root = tmp_path / "tessdata"
    pdf = _pdf(tmp_path)
    registry = BookRegistry.load(root / "livros.json")
    book = register_training(registry, pdf, "Livro", _trained(root, "Livro"))
    Path(book.tessdata_dir, "caissa_eng.traineddata").unlink()
    assert not book.available
    assert BookRegistry.load(root / "livros.json").for_pdf(pdf) is None
    assert registry.forget(book.fingerprint) is book
    registry.save()
    assert BookRegistry.load(root / "livros.json").books == {}


def test_register_training_refuses_a_failed_run(tmp_path: Path):
    root = tmp_path / "tessdata"
    report = _trained(root, "Livro")
    report.status = "failed"
    with pytest.raises(ValueError, match="não terminou"):
        register_training(BookRegistry.load(root / "livros.json"), _pdf(tmp_path), "Livro", report)


def test_models_root_follows_the_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CAISSA_FIGURINE_TESSDATA", str(tmp_path / "elsewhere"))
    assert models_root() == tmp_path / "elsewhere"
    assert models_root(tmp_path / "explicit") == tmp_path / "explicit"
    monkeypatch.delenv("CAISSA_FIGURINE_TESSDATA")
    assert models_root().name == "tessdata"
    assert BookRegistry.default(tmp_path).path == tmp_path / "livros.json"


def test_book_model_from_dict_tolerates_missing_numbers():
    book = BookModel.from_dict({"fingerprint": "f", "models": ["caissa_por"]})
    assert book.cer_before is None
    assert book.describe() == "modelo ajustado para este livro: caissa_por"


# --------------------------------------------------------------------------- #
# The trainer trains one book
# --------------------------------------------------------------------------- #


def _gt_two_books(tmp_path: Path) -> Path:
    gt = tmp_path / "gt"
    gt.mkdir()
    rows = [
        ("a1", "Livro A", "dev"),
        ("a2", "Livro A", "calib"),
        ("b1", "Livro B", "dev"),
        ("x1", None, "dev"),
    ]
    with (gt / "index.jsonl").open("w", encoding="utf-8") as handle:
        for name, document, partition in rows:
            (gt / f"{name}.png").write_bytes(b"PNG")
            (gt / f"{name}.gt.txt").write_text("ab\n", encoding="utf-8")
            row = {"name": name, "partition": partition}
            if document:
                row["document"] = document
            handle.write(json.dumps(row) + "\n")
    return gt


def test_index_rows_and_preflight_restrict_to_the_book(tmp_path: Path):
    gt = _gt_two_books(tmp_path)
    assert [r["name"] for r in _index_rows(gt)] == ["a1", "a2", "b1", "x1"]
    assert [r["name"] for r in _index_rows(gt, ("Livro A",))] == ["a1", "a2"]
    assert _index_rows(gt, ("Livro C",)) == []

    from caissa.ocr.training.tesseract_finetune import TrainingTools

    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    tools = TrainingTools(
        tesseract="tesseract",
        lstmtraining="lstmtraining",
        combine_tessdata="combine_tessdata",
        lstmeval="lstmeval",
        tessdata_dir=str(tessdata),
    )
    info = preflight(gt, FineTuneConfig(base_lang="eng", documents=("Livro A",)), tools)
    assert info["lines"] == 2
    assert info["documents"] == ["Livro A"]
    assert info["by_partition"] == {"dev": 1, "calib": 1}
    assert "problem" in info, "no base model in the fake tessdata"
    assert FineTuneConfig(documents=("Livro A",)).as_dict()["documents"] == ["Livro A"]
