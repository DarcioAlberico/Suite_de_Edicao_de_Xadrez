r"""EPUBCheck as a gate the product can run, not only a test that is skipped (OCR_UI ciclo 2, A12).

SPEC §11.3 demands "0 erros" from EPUBCheck and ``ROADMAP.md`` publishes it for the F8 --
but the only place that ran the validator was one test that **skips** when the jar is not
on the machine, and it was not.  A gate declared and never run in an invariant is a gate
that passes blind (análise §6.9).  This module is the locator and the runner that the test
suite, ``caissa.ui.audit.percurso --fluxo livro`` and anyone else share, so "EPUBCheck 0
erros" is one measurement with one definition.

Where the jar is looked for, in order:

1. ``CAISSA_EPUBCHECK`` (a path to ``epubcheck.jar``);
2. ``tools/epubcheck-*/epubcheck.jar`` under the repository root -- what
   ``tools/instalar_epubcheck.py`` unpacks, git-ignored;
3. ``%LOCALAPPDATA%\\Caissa\\epubcheck-*\\epubcheck.jar`` (the bundle's home);
4. ``%TEMP%\\**\\epubcheck*\\epubcheck.jar`` and the user's home, where the F8 work and the
   Sigil plugin unpack it.

EPUBCheck 4.2.6 runs on Java 8, which is what this machine has; 5.x needs Java 11.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["EpubCheckResult", "find_epubcheck_jar", "java_available", "run_epubcheck"]

ENV_JAR = "CAISSA_EPUBCHECK"
_REPO_ROOT = Path(__file__).resolve().parents[3]
#: EPUBCheck's summary line, in the JVM's locale: ``Messages: 0 fatals / 0 errors / 2 warnings
#: / 0 infos`` or ``Mensagens: 0 erros fatais / 0 erros / 2 advertências / 0 informações``.
_FATAL = re.compile(r"(\d+)\s+(?:erros?\s+fatais|fatals?|fatal errors?)(?!\w)", re.IGNORECASE)
_SUMMARY = re.compile(r"/\s*(\d+)\s+(?:erros?|errors?)\s*/", re.IGNORECASE)
_WARNINGS = re.compile(r"/\s*(\d+)\s+(?:avisos?|advert[êe]ncias?|warnings?)\s*/", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EpubCheckResult:
    """What one EPUBCheck run said.

    Attributes:
        errors: Errors counted from EPUBCheck's own summary line (English or
            Portuguese wording); ``-1`` when the summary could not be parsed and
            the process failed, so a crash never reads as "0 errors".
        warnings: Warnings from the same summary, when printed.
        output: The full stdout+stderr, for the report.
        jar: The jar that ran.
    """

    errors: int
    warnings: int
    output: str
    jar: Path

    @property
    def ok(self) -> bool:
        return self.errors == 0


def _candidates() -> list[Path]:
    named = os.environ.get(ENV_JAR)
    found: list[Path] = []
    if named:
        found.append(Path(named))
    found.extend(sorted(_REPO_ROOT.glob("tools/epubcheck-*/epubcheck.jar"), reverse=True))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        found.extend(sorted(Path(local).glob("Caissa/epubcheck-*/epubcheck.jar"), reverse=True))
    for root in (Path(os.environ.get("TEMP", "/tmp")), Path.home()):  # noqa: S108 - where the F8 work unpacked it
        if not root.exists():
            continue
        try:
            found.extend(root.glob("**/epubcheck*/epubcheck.jar"))
        except OSError:
            continue
    return found


def find_epubcheck_jar() -> Path | None:
    """Locate ``epubcheck.jar`` on this machine, or ``None``."""
    for candidate in _candidates():
        if candidate.is_file():
            return candidate
    return None


def java_available() -> bool:
    """Whether a Java runtime answers ``java -version``."""
    java = shutil.which("java")
    if java is None:
        return False
    try:
        subprocess.run([java, "-version"], capture_output=True, timeout=60, check=False)  # noqa: S603 - the JRE on PATH
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def run_epubcheck(jar: Path, package: Path, *, timeout_s: float = 600.0) -> EpubCheckResult:
    """Validate one ``.epub`` with EPUBCheck.

    Raises:
        OSError: When Java cannot be started at all -- the caller decides whether
            "no validator" is a skip or a red gate.
    """
    java = shutil.which("java") or "java"
    result = subprocess.run(  # noqa: S603 - the JRE on PATH with a jar this module located
        [java, "-jar", str(jar), str(package)],
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    raw = result.stdout + result.stderr
    try:
        output = raw.decode("utf-8")
    except UnicodeDecodeError:
        # The JVM prints in the console code page on Windows (cp1252 here).
        output = raw.decode("cp1252", "replace")
    errors = _SUMMARY.search(output)
    fatal = _FATAL.search(output)
    warnings = _WARNINGS.search(output)
    count = -1
    if errors is not None:
        count = int(errors.group(1)) + (int(fatal.group(1)) if fatal is not None else 0)
    elif result.returncode == 0:
        count = 0
    # A non-zero exit with "0 errors" is a run that did not validate anything (file not
    # found, bad jar): never "0 errors".
    if result.returncode != 0 and count == 0:
        count = -1
    return EpubCheckResult(
        errors=count,
        warnings=int(warnings.group(1)) if warnings is not None else 0,
        output=output,
        jar=Path(jar),
    )
