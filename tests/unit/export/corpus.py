"""Shared constants and helpers for the exporter tests.

Kept out of ``conftest.py`` because the IR tests already have a module of that
name on ``sys.path``, and two ``conftest`` modules cannot both be imported by
name.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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

    ``CAISSA_EPUBCHECK`` wins when set; otherwise the temporary directory is
    searched, which is where the F8 work unpacked it.

    Returns:
        The jar path, or ``None`` when EPUBCheck is not installed.
    """
    named = os.environ.get("CAISSA_EPUBCHECK")
    if named and Path(named).exists():
        return Path(named)
    roots = [Path(os.environ.get("TEMP", "/tmp")), Path.home()]
    for root in roots:
        if not root.exists():
            continue
        try:
            for candidate in root.glob("**/epubcheck*/epubcheck.jar"):
                return candidate
        except OSError:
            continue
    return None


def java_available() -> bool:
    """Whether a Java runtime is on this machine.

    Returns:
        ``True`` when ``java -version`` runs.
    """
    if shutil.which("java") is None:
        return False
    try:
        subprocess.run(["java", "-version"], capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def run_epubcheck(jar: Path, package: Path) -> tuple[int, str]:
    """Validate one EPUB package.

    Args:
        jar: The EPUBCheck jar.
        package: The ``.epub`` to check.

    Returns:
        ``(error count, full output)``. The count is parsed from EPUBCheck's own
        summary line, which it prints in the JVM's locale, so both the English
        and the Portuguese wordings are accepted.
    """
    import re

    result = subprocess.run(
        ["java", "-jar", str(jar), str(package)],
        capture_output=True,
        timeout=600,
        check=False,
    )
    output = (result.stdout + result.stderr).decode("utf-8", "replace")
    match = re.search(r"/\s*(\d+)\s+(?:erros?|errors?)\s*/", output)
    if match:
        return int(match.group(1)), output
    return (0 if result.returncode == 0 else 1), output
