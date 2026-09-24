"""Shared constants and helpers for the exporter tests.

Kept out of ``conftest.py`` because the IR tests already have a module of that
name on ``sys.path``, and two ``conftest`` modules cannot both be imported by
name.
"""

from __future__ import annotations

import json
import re
import zipfile
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


ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:|[\\/])")
"""A string that names a place on a disk: a drive letter or a leading slash (root, UNC)."""


def local_paths_in_epub(package: Path, folder: Path) -> list[str]:
    """What an EPUB says about the disk it was made on -- empty when it says nothing.

    Every string of the embedded IR (``OEBPS/caissa-ir.json``) that starts like an
    absolute path, and every text part that names ``folder`` in either slash form.
    """
    found: list[str] = []
    mentions = (str(folder), folder.as_posix())
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            if name == "OEBPS/caissa-ir.json":
                pending: list[object] = [json.loads(archive.read(name))]
                while pending:
                    item = pending.pop()
                    if isinstance(item, dict):
                        pending.extend(item.values())
                    elif isinstance(item, list):
                        pending.extend(item)
                    elif isinstance(item, str) and ABSOLUTE_PATH.match(item):
                        found.append(f"{name}: {item}")
            elif name.endswith((".opf", ".xhtml", ".ncx", ".xml", ".css")):
                text = archive.read(name).decode("utf-8")
                found.extend(f"{name}: {mention}" for mention in mentions if mention in text)
    return found
