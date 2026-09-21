"""The OCR profile of one book, versioned and kept next to its other artefacts — C5/X3.

``OCR_UI_ANALISE_C2.md`` §7.3: the importer had one ``TextLayerThresholds`` for every
book, ``_book_ocr_config`` specialised only the figurine tessdata, and nothing recorded
*which* profile read a book — a report, a checkpoint, a queue and an export could not be
reproduced against the settings that produced them.  This module is the recipient:

* **identity** — the PDF's content hash (the same SHA-256 :attr:`PdfDocument.content_hash`
  and :func:`caissa.ocr.training.books.pdf_fingerprint` compute), the classifier that read
  the book (``model_identity``), the labels that trained it (``dataset_version``) and the
  suite commit, so a number can be traced to the code and the truth that produced it;
* **settings** — ``ocr_config``: the :class:`~caissa.ingest.pdf.ocr_service.OcrServiceConfig`
  overrides for this book (the flat dict ``PdfImportOptions.ocr_config`` takes), applied
  by the importer under any explicit option;
* **the colour calibrator** (C5, D6) — ``colour``: the ink samples per colour of the
  book's *corrected* diagrams, in the trunk's own format
  (``chess_diagram_ocr.cor_por_livro.CalibradorDeCor.as_dict``), so the trunk reads the
  profile through :func:`colour_for_pdf` and never writes it;
* **history** — one record per closed cycle (C6, :mod:`caissa.ocr.closing`): what was
  consumed, what was withheld by the blind guard, the manifest written, the before/after.

The file is ``models/tessdata/livros/<slug>/perfil.json``, beside ``cipher.json``
(:mod:`caissa.ocr.notation.book_cipher`) — the same directory, the same slug and the same
fingerprint check, so a copy of the book under another name finds its profile and a
different book with the same name does not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caissa.ocr.training.books import book_dir, models_root, pdf_fingerprint

__all__ = [
    "PROFILE_FILE",
    "BookProfile",
    "ClosureRecord",
    "colour_for_pdf",
    "profile_path",
]

PROFILE_FILE = "perfil.json"
#: A profile with another ``version`` is not read: the fields' meaning changed.
PROFILE_VERSION = 1


@dataclass(slots=True)
class ClosureRecord:
    """What one closed cycle (C6) did to this profile."""

    at: str = ""
    corrections_text: int = 0
    corrections_diagrams: int = 0
    withheld: int = 0
    """Decisions the blind guard refused (pages of the blind partition)."""
    manifest: str = ""
    """Path of the calibration manifest written (JSONL of ``(confidence, correct)`` pairs)."""
    model_identity: str = ""
    dataset_version: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"at": self.at, "corrections_text": self.corrections_text,
                "corrections_diagrams": self.corrections_diagrams, "withheld": self.withheld,
                "manifest": self.manifest, "model_identity": self.model_identity,
                "dataset_version": self.dataset_version, "before": dict(self.before),
                "after": dict(self.after), "approved": self.approved, "note": self.note}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ClosureRecord:
        return cls(at=str(data.get("at", "")), corrections_text=int(data.get("corrections_text", 0)),
                   corrections_diagrams=int(data.get("corrections_diagrams", 0)),
                   withheld=int(data.get("withheld", 0)), manifest=str(data.get("manifest", "")),
                   model_identity=str(data.get("model_identity", "")),
                   dataset_version=str(data.get("dataset_version", "")),
                   before=dict(data.get("before", {})), after=dict(data.get("after", {})),
                   approved=bool(data.get("approved", False)), note=str(data.get("note", "")))


@dataclass(slots=True)
class BookProfile:
    """The profile of one book: identity, settings, colour calibrator, history."""

    fingerprint: str = ""
    document: str = ""
    updated_at: str = ""
    model_identity: str = ""
    dataset_version: str = ""
    suite_commit: str = ""
    ocr_config: dict[str, Any] = field(default_factory=dict)
    colour: dict[str, Any] | None = None
    history: list[ClosureRecord] = field(default_factory=list)

    @property
    def closures(self) -> int:
        return len(self.history)

    def describe_pt(self) -> str:
        parts = [f"perfil do livro: {self.closures} fechamento(s)"]
        if self.colour:
            def _count(group: Any) -> int:
                if isinstance(group, Mapping):
                    return sum(len(v) for v in group.values())
                return len(group) if group else 0

            parts.append(f"calibrador de cor com {_count(self.colour.get('brancas'))} brancas e "
                         f"{_count(self.colour.get('pretas'))} pretas de "
                         f"{self.colour.get('diagramas', 0)} diagrama(s)")
        if self.ocr_config:
            parts.append("ajustes de OCR: " + ", ".join(f"{k}={v}" for k, v in sorted(self.ocr_config.items())))
        if self.model_identity:
            parts.append(f"modelo {self.model_identity[:12]}")
        return "; ".join(parts) + "."

    # -- persistence ------------------------------------------------------- #

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": PROFILE_VERSION, "fingerprint": self.fingerprint, "document": self.document,
            "updated_at": self.updated_at, "model_identity": self.model_identity,
            "dataset_version": self.dataset_version, "suite_commit": self.suite_commit,
            "ocr_config": dict(self.ocr_config), "colour": dict(self.colour) if self.colour else None,
            "history": [record.as_dict() for record in self.history],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BookProfile | None:
        if int(data.get("version", 0)) != PROFILE_VERSION:
            return None
        colour = data.get("colour")
        return cls(
            fingerprint=str(data.get("fingerprint", "")), document=str(data.get("document", "")),
            updated_at=str(data.get("updated_at", "")), model_identity=str(data.get("model_identity", "")),
            dataset_version=str(data.get("dataset_version", "")), suite_commit=str(data.get("suite_commit", "")),
            ocr_config=dict(data.get("ocr_config", {})),
            colour=dict(colour) if isinstance(colour, Mapping) else None,
            history=[ClosureRecord.from_dict(r) for r in data.get("history", ())],
        )

    @classmethod
    def load(cls, path: Path | str, *, fingerprint: str | None = None) -> BookProfile | None:
        """The profile at ``path``; ``None`` when absent, unreadable, of another version or —
        with ``fingerprint`` — of another PDF.
        """
        file = Path(path)
        if not file.is_file():
            return None
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, Mapping):
            return None
        profile = cls.from_dict(data)
        if profile is None:
            return None
        if fingerprint and profile.fingerprint and profile.fingerprint != fingerprint:
            return None
        return profile

    def save(self, path: Path | str) -> Path:
        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        file.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        return file

    @classmethod
    def for_pdf(cls, pdf_path: Path | str, *, root: Path | str | None = None) -> BookProfile | None:
        """The stored profile of this PDF, by content hash; ``None`` when it has none."""
        path = profile_path(pdf_path, root=root)
        return cls.load(path, fingerprint=pdf_fingerprint(pdf_path))

    @classmethod
    def fresh(cls, pdf_path: Path | str) -> BookProfile:
        pdf = Path(pdf_path)
        return cls(fingerprint=pdf_fingerprint(pdf), document=pdf.stem)


def profile_path(pdf_path: Path | str, *, root: Path | str | None = None) -> Path:
    """``models/tessdata/livros/<slug>/perfil.json`` for this PDF (next to ``cipher.json``)."""
    return book_dir(models_root(root), Path(pdf_path).stem) / PROFILE_FILE


def _pdf_path_of(pdf_source: Any) -> Path | None:
    """The file behind whatever the trunk calls a ``pdf_source`` (a path, or an opened PDF
    that remembers its path); ``None`` for bytes and anything else.
    """
    if isinstance(pdf_source, (str, Path)):
        return Path(pdf_source)
    inner = getattr(pdf_source, "source", None)
    if isinstance(inner, (str, Path)):
        return Path(inner)
    return None


def colour_for_pdf(pdf_source: Any, *, root: Path | str | None = None) -> dict[str, Any] | None:
    """The colour calibrator dict of this PDF's profile — what the trunk's
    :func:`chess_diagram_ocr.cor_por_livro.calibrador_do_livro` asks for.  ``None`` when the
    source is not a file on disk, or the book has no profile or no calibrator.
    """
    path = _pdf_path_of(pdf_source)
    if path is None or not path.is_file():
        return None
    profile = BookProfile.for_pdf(path, root=root)
    if profile is None or not profile.colour:
        return None
    return dict(profile.colour)
