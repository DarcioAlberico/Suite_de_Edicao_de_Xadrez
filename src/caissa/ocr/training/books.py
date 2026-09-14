"""Models trained for one book, and the book they belong to.

FineReader's pattern training is *per document*: what the user teaches on a
scan improves that scan, and the next book starts clean.  The measurement
in ``ROTULAGEM.md`` §4c says the same of a fine-tuned Tesseract: the model
that reads 94 % of the Dvoretsky's moves invents figurines on other books'
noise and forgets a little of the base language.  So a fine-tune is not a
better ``eng``; it is a reader of one book, and it must be applied to that
book only.

This module is the binding.  A trained model lives in its own directory
(``models/tessdata/livros/<livro>/``, usable as ``--tessdata-dir`` on its
own because the trainer copies the base languages and ``configs/`` next to
it), and ``models/tessdata/livros.json`` maps the **content hash** of the
PDF to that directory — the same SHA-256 :attr:`PdfDocument.content_hash`
computes, so a copy of the book under another name or path still finds its
model and a different book with the same file name never does.

The importer asks :meth:`BookRegistry.for_pdf` before building its
:class:`~caissa.ingest.pdf.ocr_service.OcrService`; the labelling window
asks the same question when it recognises a page, so the reviewer sees the
hypothesis the importer would emit.  Nothing here loads a model: the
directory is handed to the service, which keeps using the fine-tune as a
*secondary* candidate (never the anchor — the fusion takes its figurines
and cannot take its inventions).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .tesseract_finetune import FineTuneReport

__all__ = [
    "REGISTRY_NAME",
    "BookModel",
    "BookRegistry",
    "book_dir",
    "book_slug",
    "models_root",
    "pdf_fingerprint",
    "register_training",
]

#: File name of the registry inside the models root.
REGISTRY_NAME = "livros.json"
#: Subdirectory of the models root that holds one directory per book.
BOOKS_DIR = "livros"
#: Environment variable that relocates the models root (the service reads it too).
ROOT_ENV = "CAISSA_FIGURINE_TESSDATA"
_HASH_CHUNK = 1 << 20


def models_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Where the fine-tuned models live.

    The argument, ``$CAISSA_FIGURINE_TESSDATA``, or ``<repo>/models/tessdata``.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get(ROOT_ENV)
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        # The bundle keeps its writable folders next to the executable
        # (``packaging/build_windows.py``: ``models/``, ``runtime/``).
        return Path(sys.executable).resolve().parent / "models" / "tessdata"
    return Path(__file__).resolve().parents[4] / "models" / "tessdata"


def pdf_fingerprint(path: Path | str) -> str:
    """SHA-256 of the file's bytes — identical to ``PdfDocument.content_hash``."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def book_slug(document: str, limit: int = 40) -> str:
    """A directory-safe name for the book (the PDF's stem)."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", document).strip("_").lower()
    return (slug or "livro")[:limit].rstrip("_")


def book_dir(root: Path | str, document: str) -> Path:
    return Path(root) / BOOKS_DIR / book_slug(document)


@dataclass(slots=True)
class BookModel:
    """One book's fine-tuned model directory and how it was trained."""

    fingerprint: str
    document: str
    pdf_path: str
    tessdata_dir: str
    models: tuple[str, ...] = ()
    base_lang: str = ""
    trained_at: str = ""
    lines_train: int = 0
    lines_eval: int = 0
    cer_before: float | None = None
    cer_after: float | None = None
    model_sha256: str = ""
    note: str = ""

    @property
    def directory(self) -> Path:
        return Path(self.tessdata_dir)

    @property
    def available(self) -> bool:
        """Whether every registered model file is still where the registry says."""
        return bool(self.models) and all(
            (self.directory / f"{name}.traineddata").is_file() for name in self.models
        )

    def describe(self) -> str:
        """One line for a report note or a status bar."""
        names = ", ".join(self.models) or "—"
        parts = [f"modelo ajustado para este livro: {names}"]
        if self.trained_at:
            parts.append(f"treinado em {self.trained_at[:10]}")
        if self.lines_train:
            parts.append(f"{self.lines_train} linhas de treino")
        if self.cer_before is not None and self.cer_after is not None:
            parts.append(f"CER avaliação {self.cer_before:.1f} → {self.cer_after:.1f} %")
        return " · ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "document": self.document,
            "pdf_path": self.pdf_path,
            "tessdata_dir": self.tessdata_dir,
            "models": list(self.models),
            "base_lang": self.base_lang,
            "trained_at": self.trained_at,
            "lines_train": self.lines_train,
            "lines_eval": self.lines_eval,
            "cer_before": self.cer_before,
            "cer_after": self.cer_after,
            "model_sha256": self.model_sha256,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BookModel:
        def number(value: Any) -> float | None:
            return None if value is None else float(value)

        return cls(
            fingerprint=str(data["fingerprint"]),
            document=str(data.get("document", "")),
            pdf_path=str(data.get("pdf_path", "")),
            tessdata_dir=str(data.get("tessdata_dir", "")),
            models=tuple(str(m) for m in data.get("models", ())),
            base_lang=str(data.get("base_lang", "")),
            trained_at=str(data.get("trained_at", "")),
            lines_train=int(data.get("lines_train", 0)),
            lines_eval=int(data.get("lines_eval", 0)),
            cer_before=number(data.get("cer_before")),
            cer_after=number(data.get("cer_after")),
            model_sha256=str(data.get("model_sha256", "")),
            note=str(data.get("note", "")),
        )


@dataclass(slots=True)
class BookRegistry:
    """``livros.json``: content hash of a PDF → its :class:`BookModel`."""

    path: Path
    books: dict[str, BookModel] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> BookRegistry:
        path = Path(path)
        registry = cls(path=path)
        if path.is_file():
            data = json.loads(path.read_text("utf-8"))
            for raw in data.get("books", ()):
                book = BookModel.from_dict(raw)
                registry.books[book.fingerprint] = book
        return registry

    @classmethod
    def default(cls, root: Path | str | None = None) -> BookRegistry:
        """The registry under :func:`models_root`."""
        return cls.load(models_root(root) / REGISTRY_NAME)

    @property
    def root(self) -> Path:
        return self.path.parent

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "books": [b.as_dict() for b in sorted(self.books.values(), key=lambda b: b.document)],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    def register(self, book: BookModel) -> None:
        self.books[book.fingerprint] = book

    def forget(self, fingerprint: str) -> BookModel | None:
        return self.books.pop(fingerprint, None)

    def lookup(self, fingerprint: str | None) -> BookModel | None:
        """The book's model when it is registered *and* still on disk."""
        if not fingerprint:
            return None
        book = self.books.get(fingerprint)
        return book if book is not None and book.available else None

    def for_pdf(self, path: Path | str | None) -> BookModel | None:
        """Fingerprint the file and look it up.

        ``None`` for no file, no entry, or a model that was moved away.
        """
        if path is None or not self.books:
            return None
        path = Path(path)
        if not path.is_file():
            return None
        return self.lookup(pdf_fingerprint(path))

    def for_document(self, document: str) -> BookModel | None:
        """By book name, for a window that has no file to hash yet."""
        for book in self.books.values():
            if book.document == document and book.available:
                return book
        return None


def register_training(
    registry: BookRegistry,
    pdf_path: Path | str,
    document: str,
    report: FineTuneReport,
    *,
    base_lang: str = "",
) -> BookModel:
    """Bind a finished fine-tune to the book it was trained on and save.

    The report must have ``status == "trained"``; the model directory is the
    report's ``out_dir``, which the trainer left usable as ``--tessdata-dir``.
    """
    if report.status != "trained":
        raise ValueError(f"o treino não terminou ({report.status}): nada a registrar")
    model_name = Path(report.model_path).stem if report.model_path else report.model_name
    book = BookModel(
        fingerprint=pdf_fingerprint(pdf_path),
        document=document,
        pdf_path=str(Path(pdf_path).resolve()),
        tessdata_dir=str(Path(report.out_dir).resolve()),
        models=(model_name,),
        base_lang=base_lang or model_name.rpartition("_")[2],
        trained_at=report.finished_at,
        lines_train=int(report.lines_train),
        lines_eval=int(report.lines_eval),
        cer_before=report.cer_before,
        cer_after=report.cer_after,
        model_sha256=report.model_sha256,
    )
    registry.register(book)
    registry.save()
    return book
