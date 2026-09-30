r"""Unpack an EPUBCheck distribution where ``caissa.export.epubcheck`` looks for it (A12).

The "0 erros" gate of SPEC §11.3 only runs when ``epubcheck.jar`` is on the machine.  This
script puts it there from a release zip (``epubcheck-4.2.6.zip`` from
https://github.com/w3c/epubcheck/releases -- 4.2.x runs on Java 8, 5.x needs Java 11) or
from the copy the Sigil plugin downloads to ``%TEMP%\\sigil-epubcheck-*\\epubcheck.zip``::

    .venv\\Scripts\\python.exe tools\\instalar_epubcheck.py                # finds the Sigil copy
    .venv\\Scripts\\python.exe tools\\instalar_epubcheck.py caminho\\para\\epubcheck-4.2.6.zip
    .venv\\Scripts\\python.exe tools\\instalar_epubcheck.py --destino %LOCALAPPDATA%\\Caissa

The default destination is ``tools/`` in this repository (git-ignored); the bundle's home is
``%LOCALAPPDATA%\\Caissa``.  Nothing is downloaded: the zip must already be on disk.
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def sigil_copy() -> Path | None:
    """The zip the Sigil EPUBCheck plugin left in ``%TEMP%``, newest first."""
    temp = Path(os.environ.get("TEMP", "/tmp"))  # noqa: S108
    copies = sorted(temp.glob("sigil-epubcheck-*/epubcheck.zip"), reverse=True)
    return copies[0] if copies else None


def unpack(zip_path: Path, destination: Path) -> Path:
    """Unpack ``zip_path`` into ``destination`` and return the jar's path.

    The release zip has one top-level folder (``epubcheck-4.2.6/``); it lands as
    ``destination/epubcheck-4.2.6/epubcheck.jar``, which is the pattern the locator globs.
    """
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        jars = [n for n in names if n.endswith("/epubcheck.jar") or n == "epubcheck.jar"]
        if not jars:
            raise SystemExit(f"{zip_path} não contém epubcheck.jar")
        for name in names:
            target = (destination / name).resolve()
            if not str(target).startswith(str(destination.resolve())):
                raise SystemExit(f"entrada fora do destino no zip: {name}")
        archive.extractall(destination)
    jar = destination / jars[0]
    if jar.parent.name.startswith("epubcheck") is False:
        raise SystemExit(f"a pasta do jar não se chama epubcheck-*: {jar.parent}")
    return jar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "zip", nargs="?", type=Path, default=None, help="epubcheck-*.zip (padrão: a cópia do Sigil)"
    )
    parser.add_argument("--destino", type=Path, default=REPO_ROOT / "tools")
    args = parser.parse_args(argv)

    zip_path = args.zip or sigil_copy()
    if zip_path is None or not zip_path.is_file():
        print("Nenhum epubcheck-*.zip encontrado: passe o caminho do zip baixado de "
              "https://github.com/w3c/epubcheck/releases (4.2.6 para Java 8).", file=sys.stderr)
        return 2
    args.destino.mkdir(parents=True, exist_ok=True)
    jar = unpack(zip_path, args.destino)
    print(f"EPUBCheck instalado: {jar}")

    from caissa.export.epubcheck import find_epubcheck_jar, java_available

    found = find_epubcheck_jar()
    print(f"localizado pelo produto: {found}")
    print(f"java disponível: {java_available()}")
    return 0 if found is not None and java_available() else 1


if __name__ == "__main__":
    raise SystemExit(main())
