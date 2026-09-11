"""Versioned prompt templates, loaded from files rather than string literals.

A prompt is part of the product's behaviour: changing one word can move a
recognition metric. So prompts live in ``prompts/<id>.v<n>.toml`` under version
control, are addressed by ``(id, version)``, and every rendered call records the
file's ``sha256`` in the audit log. That is what makes "the numbers moved on
Tuesday" traceable to "someone edited the prompt on Tuesday".

The format is TOML because :mod:`tomllib` is in the 3.11 standard library and
this package deliberately adds no dependencies.
"""

from __future__ import annotations

import hashlib
import os
import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any, Final

__all__ = [
    "PromptError",
    "PromptTemplate",
    "clear_prompt_cache",
    "list_prompts",
    "load_prompt",
    "prompts_dir",
]

_FILENAME_RE: Final = re.compile(r"^(?P<id>[a-z0-9_]+)\.v(?P<version>\d+)\.toml$")
_REQUIRED: Final = ("id", "version", "system", "template")


class PromptError(RuntimeError):
    """A prompt file is missing, malformed, or rendered with the wrong fields."""


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """One versioned prompt.

    Attributes:
        id: Stable identifier, equal to the file stem.
        version: Monotonic integer. Bump on any content change.
        description: One-line English summary.
        system: The system turn, used verbatim.
        template: The user turn, a :meth:`str.format` template.
        max_tokens: Hard generation cap for this prompt.
        temperature: Sampling temperature; 0.0 for anything structured.
        output: ``"json"`` or ``"text"``. Drives guardrail selection.
        stop: Stop strings.
        sha256: Digest of the source file, recorded on every call.
        path: Where it came from.
    """

    id: str
    version: int
    description: str
    system: str
    template: str
    max_tokens: int
    temperature: float
    output: str
    stop: tuple[str, ...]
    sha256: str
    path: Path

    @property
    def ref(self) -> str:
        """Short human reference such as ``verify_diagram.v1``."""
        return f"{self.id}.v{self.version}"

    def fields(self) -> frozenset[str]:
        """The placeholder names :meth:`render` expects."""
        return frozenset(
            name for _, name, _, _ in Formatter().parse(self.template) if name is not None
        )

    def render(self, **values: object) -> str:
        """Fill the template.

        Args:
            **values: One entry per placeholder. Values are stringified; ``None``
                becomes an empty string so callers do not have to pre-clean
                optional context.

        Returns:
            The rendered user turn.

        Raises:
            PromptError: If a placeholder is missing or an unknown one is given.
                Both are bugs that should surface in a test, not a truncated
                prompt reaching the model.
        """
        expected = self.fields()
        supplied = frozenset(values)
        if missing := expected - supplied:
            raise PromptError(
                f"{self.ref}: campos ausentes {sorted(missing)}; esperados {sorted(expected)}"
            )
        if extra := supplied - expected:
            raise PromptError(f"{self.ref}: campos desconhecidos {sorted(extra)}")
        cleaned = {key: ("" if value is None else str(value)) for key, value in values.items()}
        try:
            return self.template.format(**cleaned)
        except (IndexError, KeyError) as exc:
            raise PromptError(f"{self.ref}: template invalido ({exc})") from exc


def prompts_dir() -> Path:
    """Locate the ``prompts/`` directory.

    Resolution order:

    1. ``CAISSA_PROMPTS_DIR`` -- lets a packaged build point at its own copy and
       lets a test point at a fixture.
    2. ``<repo root>/prompts`` -- found by walking up from this file.

    Raises:
        PromptError: If neither exists, which is a broken installation.
    """
    if raw := os.environ.get("CAISSA_PROMPTS_DIR"):
        candidate = Path(raw)
        if candidate.is_dir():
            return candidate
        raise PromptError(f"CAISSA_PROMPTS_DIR aponta para '{raw}', que nao e um diretorio")
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "prompts"
        if candidate.is_dir():
            return candidate
    raise PromptError(
        "diretorio 'prompts/' nao encontrado; defina CAISSA_PROMPTS_DIR "
        "ou reinstale a aplicacao"
    )


def _parse(path: Path) -> PromptTemplate:
    """Read and validate one prompt file."""
    raw = path.read_bytes()
    try:
        data: dict[str, Any] = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise PromptError(f"{path.name}: TOML invalido ({exc})") from exc
    if missing := [key for key in _REQUIRED if key not in data]:
        raise PromptError(f"{path.name}: chaves obrigatorias ausentes {missing}")

    match = _FILENAME_RE.match(path.name)
    if match is None:
        raise PromptError(f"{path.name}: nome deve seguir '<id>.v<n>.toml'")
    if data["id"] != match["id"] or int(data["version"]) != int(match["version"]):
        raise PromptError(
            f"{path.name}: id/version do conteudo "
            f"({data['id']}.v{data['version']}) nao batem com o nome do arquivo"
        )
    output = str(data.get("output", "text"))
    if output not in {"json", "text"}:
        raise PromptError(f"{path.name}: output deve ser 'json' ou 'text' (recebido {output!r})")

    return PromptTemplate(
        id=str(data["id"]),
        version=int(data["version"]),
        description=str(data.get("description", "")),
        system=str(data["system"]).strip(),
        template=str(data["template"]).strip(),
        max_tokens=int(data.get("max_tokens", 256)),
        temperature=float(data.get("temperature", 0.0)),
        output=output,
        stop=tuple(str(item) for item in data.get("stop", ())),
        sha256=hashlib.sha256(raw).hexdigest(),
        path=path,
    )


@lru_cache(maxsize=64)
def _load_cached(directory: str, prompt_id: str, version: int | None) -> PromptTemplate:
    """Cached inner loader keyed by resolved directory."""
    base = Path(directory)
    candidates = sorted(base.glob(f"{prompt_id}.v*.toml"))
    parsed = [_parse(path) for path in candidates]
    if not parsed:
        known = ", ".join(sorted({template.id for template in _scan(base)})) or "nenhum"
        raise PromptError(f"prompt '{prompt_id}' nao encontrado em {base}; disponiveis: {known}")
    if version is None:
        return max(parsed, key=lambda template: template.version)
    for template in parsed:
        if template.version == version:
            return template
    have = sorted(template.version for template in parsed)
    raise PromptError(f"prompt '{prompt_id}' nao tem versao {version}; existem {have}")


def _scan(base: Path) -> list[PromptTemplate]:
    """Parse every prompt file in ``base``, skipping unparseable names."""
    found: list[PromptTemplate] = []
    for path in sorted(base.glob("*.toml")):
        if _FILENAME_RE.match(path.name):
            found.append(_parse(path))
    return found


def load_prompt(prompt_id: str, *, version: int | None = None) -> PromptTemplate:
    """Load a prompt by id, defaulting to its highest version.

    Args:
        prompt_id: The file stem, e.g. ``"verify_diagram"``.
        version: Pin a specific version. ``None`` takes the newest, which is
            what production does; the benchmark pins versions to compare two
            revisions on the same corpus.

    Raises:
        PromptError: If the prompt or the requested version does not exist.
    """
    return _load_cached(str(prompts_dir()), prompt_id, version)


def list_prompts() -> tuple[PromptTemplate, ...]:
    """Every prompt available, newest version of each first."""
    templates = _scan(prompts_dir())
    templates.sort(key=lambda template: (template.id, -template.version))
    return tuple(templates)


def clear_prompt_cache() -> None:
    """Forget cached prompt files. For tests and for hot-reload during authoring."""
    _load_cached.cache_clear()
