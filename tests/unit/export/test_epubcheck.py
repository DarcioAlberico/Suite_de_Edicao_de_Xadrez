"""EPUBCheck as a measured gate, not a skipped test (OCR_UI ciclo 2, A12).

Three things: the locator finds the jar the repository carries under ``tools/`` (and the
one ``CAISSA_EPUBCHECK`` names, first); the runner parses EPUBCheck's own summary line in
both wordings; and the sabotage -- a package with its ``mimetype`` corrupted -- makes the
gate report errors, so "0 erros" is a number the validator produced, not a default.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from caissa.export.epubcheck import (
    EpubCheckResult,
    find_epubcheck_jar,
    java_available,
    run_epubcheck,
)

pytestmark = pytest.mark.skipif(
    not java_available() or find_epubcheck_jar() is None,
    reason="EPUBCheck e Java: rode tools/instalar_epubcheck.py (A12) para o portão medir.",
)


def test_the_repository_copy_is_found_and_the_environment_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    jar = find_epubcheck_jar()
    assert jar is not None
    assert jar.name == "epubcheck.jar"
    named = tmp_path / "epubcheck.jar"
    named.write_bytes(b"not a jar")
    monkeypatch.setenv("CAISSA_EPUBCHECK", str(named))
    assert find_epubcheck_jar() == named, "CAISSA_EPUBCHECK vence a cópia do repositório"
    monkeypatch.setenv("CAISSA_EPUBCHECK", str(tmp_path / "ausente.jar"))
    assert find_epubcheck_jar() == jar, "um caminho inexistente na variável não esconde o jar real"


def _small_package(tmp_path: Path) -> Path:
    from caissa.core.model import Document, DocumentMetadata, Paragraph, Text
    from caissa.export.epub import EpubExporter

    document = Document(
        metadata=DocumentMetadata(title="Portão", language="pt"),
        body=(Paragraph(content=(Text(content="Um parágrafo basta para o validador."),)),),
    )
    target = tmp_path / "portao.epub"
    EpubExporter().export(document, target)
    return target


def test_a_valid_package_reports_zero_errors(tmp_path: Path) -> None:
    jar = find_epubcheck_jar()
    assert jar is not None
    result = run_epubcheck(jar, _small_package(tmp_path))
    assert isinstance(result, EpubCheckResult)
    assert result.ok, result.output[-3000:]
    assert result.errors == 0
    assert result.jar == jar


def test_the_sabotage_a_broken_mimetype_is_counted(tmp_path: Path) -> None:
    """The gate must be able to fail: the same package with ``mimetype`` corrupted."""
    jar = find_epubcheck_jar()
    assert jar is not None
    good = _small_package(tmp_path)
    broken = tmp_path / "quebrado.epub"
    with zipfile.ZipFile(good) as source, zipfile.ZipFile(broken, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "mimetype":
                data = b"text/plain"
                target.writestr(info, data, compress_type=zipfile.ZIP_STORED)
            else:
                target.writestr(info, data)
    result = run_epubcheck(jar, broken)
    assert not result.ok
    assert result.errors >= 1, result.output[-3000:]


def test_a_crash_never_reads_as_zero_errors(tmp_path: Path) -> None:
    jar = find_epubcheck_jar()
    assert jar is not None
    missing = tmp_path / "nao-existe.epub"
    result = run_epubcheck(jar, missing)
    assert result.errors != 0


def test_the_installer_unpacks_a_release_zip(tmp_path: Path) -> None:
    """``tools/instalar_epubcheck.py`` puts the jar where the locator globs it."""
    import importlib.util

    script = Path(__file__).resolve().parents[3] / "tools" / "instalar_epubcheck.py"
    spec = importlib.util.spec_from_file_location("instalar_epubcheck", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    real = find_epubcheck_jar()
    assert real is not None
    release = tmp_path / "epubcheck-9.9.9.zip"
    with zipfile.ZipFile(release, "w") as archive:
        archive.write(real, "epubcheck-9.9.9/epubcheck.jar")
        archive.writestr("epubcheck-9.9.9/README.txt", "fake release")
    destination = tmp_path / "destino"
    jar = module.unpack(release, destination)
    assert jar == destination / "epubcheck-9.9.9" / "epubcheck.jar"
    assert jar.is_file()
    shutil.rmtree(destination)


def test_a_custom_metadata_scheme_is_a_declared_prefix(tmp_path: Path) -> None:
    """The gate's first catch on the product path: the importer's ``scheme="pdf"`` entries
    came out as ``property="pdf:Producer"`` with no prefix declared -- four OPF-028 errors on
    every book exported from the window, invisible to the corpus (which has no such entry)."""
    from caissa.core.model import Document, DocumentMetadata, MetadataEntry, Paragraph, Text
    from caissa.export.epub import EpubExporter

    document = Document(
        metadata=DocumentMetadata(
            title="Prefixo", language="pt",
            custom=(MetadataEntry(name="Producer", value="pdfTeX-1.40", scheme="pdf"),
                    MetadataEntry(name="Creation Date", value="D:20200101", scheme="pdf"),
                    MetadataEntry(name="livre", value="x", scheme="9 esquemas/estranhos")),
        ),
        body=(Paragraph(content=(Text(content="Um parágrafo."),)),),
    )
    target = tmp_path / "prefixo.epub"
    EpubExporter().export(document, target)
    with zipfile.ZipFile(target) as archive:
        opf = archive.read("OEBPS/content.opf").decode("utf-8")
    assert 'pdf: https://caissa.studio/ns/pdf#' in opf
    assert '<meta property="pdf:Producer">' in opf
    assert '<meta property="pdf:Creation-Date">' in opf, "o nome vira termo válido"
    assert 'x-9-esquemas-estranhos: ' in opf
    jar = find_epubcheck_jar()
    assert jar is not None
    result = run_epubcheck(jar, target)
    assert result.ok, result.output[-3000:]
