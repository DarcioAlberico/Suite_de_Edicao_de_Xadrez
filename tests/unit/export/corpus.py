"""Shared constants and helpers for the exporter tests.

Kept out of ``conftest.py`` because the IR tests already have a module of that
name on ``sys.path``, and two ``conftest`` modules cannot both be imported by
name.
"""

from __future__ import annotations

from pathlib import Path

CORPUS_SEED = 0x0F8
"""Seed of the corpus every fidelity test measures. Printed on failure."""

CORPUS_NODES = 200
"""Minimum nodes the corpus must reach before a measurement means anything."""

FORMATS = ("html", "epub", "docx", "pdf", "latex")
"""Every format the front ships, in the order the report lists them."""

MARKUP_FORMATS = ("html", "epub", "docx")
"""Formats whose own reader rebuilds the tree, so a number measures the writer."""

SIDECAR_FORMATS = ("pdf", "latex")
"""Formats measured through the embedded IR; see :mod:`caissa.export.fidelity`."""


def epubcheck_jar() -> Path | None:
    """Locate an EPUBCheck jar, if this machine has one.

    OCR_UI ciclo 2, A12: the locator moved to :mod:`caissa.export.epubcheck`,
    where the product (``percurso --fluxo livro``) shares it -- ``CAISSA_EPUBCHECK``
    wins, then ``tools/epubcheck-*/`` in the repository, then the machine.
    """
    from caissa.export.epubcheck import find_epubcheck_jar

    return find_epubcheck_jar()


def java_available() -> bool:
    """Whether a Java runtime is on this machine."""
    from caissa.export.epubcheck import java_available as _java_available

    return _java_available()


def run_epubcheck(jar: Path, package: Path) -> tuple[int, str]:
    """Validate one EPUB package; ``(error count, full output)``."""
    from caissa.export.epubcheck import run_epubcheck as _run

    result = _run(jar, package)
    return (result.errors if result.errors >= 0 else 1), result.output
