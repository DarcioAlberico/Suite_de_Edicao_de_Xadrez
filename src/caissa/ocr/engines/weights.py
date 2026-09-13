"""Model weights: what each optional engine downloads, and under what terms.

Sol §SOL-5: "controlar download, hash e versão dos pesos" and "verificar
termos de licença dos pesos antes de distribuição comercial".  The engines
fetch their own weights on first use; this module is the ledger that says
which artefacts a given adapter version expects, where they come from,
what licence they carry, and — once a copy has been seen on this machine —
its SHA-256, so a replaced or truncated download is caught instead of
silently changing every score.

The ledger ships as ``caissa/ocr/data/weights.json``.  Hashes are recorded
by :func:`record_weights` after a verified run and compared by
:func:`verify_weights`; an artefact with no recorded hash is *unknown*, not
verified, and the report says so.

Licence notes are facts about the sources as published, not legal advice:
PaddleOCR's models are Apache-2.0; Surya's code is GPL-3.0 and its model
weights are published under CC-BY-NC-SA-4.0 with a commercial exception
tied to the vendor's revenue threshold — which is exactly the case Sol
flags as needing a check before any commercial distribution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

__all__ = ["WeightArtifact", "WeightsLedger", "load_ledger", "verify_weights"]

DATA_FILE = "weights.json"


@dataclass(frozen=True, slots=True)
class WeightArtifact:
    engine: str
    name: str
    source: str
    license: str
    commercial_use: str            # "ok" | "verify" | "no"
    version: str = ""
    sha256: str = ""
    size_bytes: int = 0
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine, "name": self.name, "source": self.source,
            "license": self.license, "commercial_use": self.commercial_use,
            "version": self.version, "sha256": self.sha256, "size_bytes": self.size_bytes,
            "note": self.note,
        }


@dataclass(slots=True)
class WeightsLedger:
    artifacts: list[WeightArtifact] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def for_engine(self, engine: str) -> list[WeightArtifact]:
        return [a for a in self.artifacts if a.engine == engine]

    def needs_licence_check(self) -> list[WeightArtifact]:
        return [a for a in self.artifacts if a.commercial_use != "ok"]

    def as_dict(self) -> dict[str, Any]:
        return {"version": 1, "notes": list(self.notes),
                "artifacts": [a.as_dict() for a in self.artifacts]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeightsLedger":
        return cls(
            artifacts=[WeightArtifact(**{k: v for k, v in row.items()
                                         if k in WeightArtifact.__dataclass_fields__})
                       for row in data.get("artifacts", ())],
            notes=list(data.get("notes", ())))


def load_ledger(path: Path | str | None = None) -> WeightsLedger:
    if path is not None:
        return WeightsLedger.from_dict(json.loads(Path(path).read_text("utf-8")))
    try:
        text = resources.files("caissa.ocr.data").joinpath(DATA_FILE).read_text("utf-8")
    except (FileNotFoundError, OSError, ModuleNotFoundError):
        return WeightsLedger()
    return WeightsLedger.from_dict(json.loads(text))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_weights(artifact: WeightArtifact, path: Path) -> tuple[str, str]:
    """``("verified" | "mismatch" | "unknown" | "missing", detail)``."""
    if not path.is_file():
        return "missing", f"{path} não existe"
    if not artifact.sha256:
        return "unknown", "sem hash registrado para este artefato; registre após uma execução verificada"
    actual = sha256_of(path)
    if actual == artifact.sha256:
        return "verified", actual[:16]
    return "mismatch", f"esperado {artifact.sha256[:16]}…, encontrado {actual[:16]}…"


def record_weights(artifact: WeightArtifact, path: Path) -> WeightArtifact:
    """The artefact with the hash and size of ``path`` filled in."""
    return WeightArtifact(
        engine=artifact.engine, name=artifact.name, source=artifact.source,
        license=artifact.license, commercial_use=artifact.commercial_use,
        version=artifact.version, sha256=sha256_of(path), size_bytes=path.stat().st_size,
        note=artifact.note)
