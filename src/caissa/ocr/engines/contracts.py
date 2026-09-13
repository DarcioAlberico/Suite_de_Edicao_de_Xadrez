"""Version contracts for the optional engines — Sol §SOL-5.

An optional engine is code this project does not control, installed by the
user at whatever version pip resolved.  Two failure modes follow, and both
used to be silent: an API that moved (the adapter's attribute access
returned nothing and the page came out empty), and a version the adapter
was never written against (same symptom).  Sol §SOL-5 asks for the
opposite — "mudança de schema do motor falha de forma explícita, não como
página vazia" — so every optional adapter checks two things at probe time:

* the installed distribution's version lies in the range this adapter was
  tested against (:data:`SUPPORTED`), refusing outside it with the range
  in the message;
* the result it gets back has the shape it expects, raising
  :class:`SchemaError` (an :class:`~caissa.ocr.engines.base.OcrError`)
  when a non-empty payload cannot be parsed — never returning no lines.

The ranges are data.  Widening one after a contract test passes on the new
version is the intended way to support it.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata

from .base import OcrError

__all__ = ["SUPPORTED", "SchemaError", "VersionRange", "check_version", "installed_version"]


@dataclass(frozen=True, slots=True)
class VersionRange:
    minimum: tuple[int, ...]
    below: tuple[int, ...]

    def contains(self, version: tuple[int, ...]) -> bool:
        return self.minimum <= version < self.below

    def describe(self) -> str:
        return (f">={'.'.join(map(str, self.minimum))},"
                f"<{'.'.join(map(str, self.below))}")


#: distribution name → tested range.  PaddleOCR 2.7 is the last 2.x API and
#: 3.x the ``predict`` API; both are parsed.  Surya's ``FoundationPredictor``
#: shape appears in 0.14; the older ``run_ocr`` shape is kept for 0.6+.
SUPPORTED: dict[str, VersionRange] = {
    "paddleocr": VersionRange((2, 7), (4, 0)),
    "surya-ocr": VersionRange((0, 6), (1, 0)),
    "rapidocr-onnxruntime": VersionRange((1, 3), (3, 0)),
}


class SchemaError(OcrError):
    """The engine answered, but not in a shape this adapter understands."""

    def __init__(self, engine: str, detail: str) -> None:
        super().__init__(
            engine,
            "o motor respondeu num formato desconhecido; a versão instalada mudou o "
            "esquema de saída e o adaptador precisa ser atualizado (nada foi importado "
            "como página vazia).",
            detail=detail[:2000],
        )


def parse_version(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in text.split("."):
        digits = ""
        for ch in piece:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or (0,)


def installed_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def check_version(distribution: str, *, engine: str) -> tuple[bool, str | None, str | None]:
    """``(ok, version, reason_pt)`` for the installed distribution."""
    version = installed_version(distribution)
    if version is None:
        return True, None, None          # not installed as a distribution; import decides
    window = SUPPORTED.get(distribution)
    if window is None:
        return True, version, None
    if window.contains(parse_version(version)):
        return True, version, None
    return False, version, (
        f"{engine}: a versão instalada de {distribution} ({version}) está fora da faixa "
        f"testada ({window.describe()}). Instale uma versão da faixa ou atualize o "
        f"adaptador depois de rodar os testes contratuais."
    )
