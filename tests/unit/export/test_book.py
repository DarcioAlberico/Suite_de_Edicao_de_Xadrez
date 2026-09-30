"""A PDF becomes an EPUB or a DOCX -- whole, or the pages asked for.

The books are the synthetic ones of the F2 fixtures (``tests/unit/ingest``),
so every assertion about *which* pages came out is against known text.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest
from corpus import local_paths_in_epub

_INGEST_TESTS = Path(__file__).resolve().parent.parent / "ingest"
if str(_INGEST_TESTS) not in sys.path:
    sys.path.insert(0, str(_INGEST_TESTS))

from caissa.core.model import Diagram, RecognitionPath  # noqa: E402
from caissa.export import (  # noqa: E402
    BOOK_FORMATS,
    ExportError,
    PageRangeError,
    default_output_path,
    describe_pages,
    export_book,
    parse_page_range,
    read_docx,
    read_epub,
)
from caissa.export.book import format_for_path  # noqa: E402
from caissa.export.cli import main  # noqa: E402
from caissa.ingest.pdf import DiagramHit, ImportCanceled, PdfImportOptions  # noqa: E402
from caissa.ocr.diagram_decisions import ENV_ROOT  # noqa: E402

PNG_HEAD = bytes([0x89]) + b"PNG"
from conftest import PageSpec, build_pdf, requires_pymupdf  # noqa: E402

# --------------------------------------------------------------------------- #
# Page ranges: no PDF needed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", tuple(range(12))),
        ("   ", tuple(range(12))),
        ("7", (6,)),
        ("10-12", (9, 10, 11)),
        ("10..12", (9, 10, 11)),
        ("10–12", (9, 10, 11)),
        ("1-3, 7, 10-", (0, 1, 2, 6, 9, 10, 11)),
        ("-2", (0, 1)),
        ("3, 1, 2, 2", (0, 1, 2)),
    ],
)
def test_ranges_are_one_based_in_text_and_zero_based_out(text, expected):
    assert parse_page_range(text, 12) == expected


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("0", "não existe"),
        ("13", "o PDF tem 12"),
        ("5-2", "termina antes"),
        ("a-b", "Não entendi"),
        ("1,,3", "Não entendi"),
        ("-", "Falta um número"),
    ],
)
def test_a_range_that_cannot_be_read_says_why_in_portuguese(text, fragment):
    with pytest.raises(PageRangeError, match=fragment):
        parse_page_range(text, 12)


def test_an_empty_book_has_no_range():
    with pytest.raises(PageRangeError):
        parse_page_range("1", 0)


def test_describe_pages_collapses_runs_and_names_the_whole_book():
    assert describe_pages(None, 5) == "livro completo"
    assert describe_pages((0, 1, 2, 3, 4), 5) == "livro completo"
    assert describe_pages((4, 3, 2, 1, 0), 5) == "livro completo"
    assert describe_pages((1, 2, 3), 5) == "2-4"
    assert describe_pages((0, 2, 3, 4, 9), 12) == "1, 3-5, 10"
    assert describe_pages((), 5) == "nenhuma página"


def test_the_default_name_carries_the_selection_only_when_partial(tmp_path: Path):
    pdf = tmp_path / "Livro.pdf"
    assert default_output_path(pdf, "epub", None, 9) == tmp_path / "Livro.epub"
    assert default_output_path(pdf, "docx", tuple(range(9)), 9) == tmp_path / "Livro.docx"
    assert default_output_path(pdf, "epub", (1, 2, 3), 9) == tmp_path / "Livro (p. 2-4).epub"
    with pytest.raises(ExportError, match="Formato de livro desconhecido"):
        default_output_path(pdf, "html", None, 9)


def test_the_format_is_read_from_the_extension():
    assert format_for_path(Path("x.EPUB")) == "epub"
    assert format_for_path(Path("x.docx")) == "docx"
    with pytest.raises(ExportError, match="não é de livro"):
        format_for_path(Path("x.pdf"))
    assert BOOK_FORMATS == ("epub", "docx")


# --------------------------------------------------------------------------- #
# The pipeline on a synthetic book
# --------------------------------------------------------------------------- #


def _book(tmp_path: Path, pages: int = 6) -> Path:
    specs = [
        PageSpec().text(
            f"Capítulo {i + 1} começa aqui com texto suficiente para ser parágrafo.", 72, 100
        )
        for i in range(pages)
    ]
    target = tmp_path / "Livro de Finais.pdf"
    target.write_bytes(build_pdf(specs))
    return target


def _texts(path: Path) -> str:
    """All the text the written file carries, read back through the exporters' own readers."""
    if path.suffix == ".epub":
        with zipfile.ZipFile(path) as archive:
            return "\n".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith((".xhtml", ".html"))
            )
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


@requires_pymupdf
@pytest.mark.parametrize("format_name", BOOK_FORMATS)
def test_the_whole_book_is_written_beside_the_pdf(tmp_path: Path, format_name: str):
    pdf = _book(tmp_path)
    result = export_book(pdf, None, format_name, enable_ocr=False)
    assert result.path == tmp_path / f"Livro de Finais.{format_name}"
    assert result.path.is_file()
    assert result.pages == "livro completo"
    assert len(result.page_indices) == 6
    body = _texts(result.path)
    for i in range(6):
        assert f"Capítulo {i + 1}" in body
    assert "livro completo" in result.summary()
    assert not any(entry.name == "pages" for entry in result.document.metadata.custom)


@requires_pymupdf
def test_a_page_range_writes_only_those_pages_and_says_so(tmp_path: Path):
    pdf = _book(tmp_path)
    result = export_book(pdf, None, "epub", pages="2-3, 6", enable_ocr=False)
    assert result.path == tmp_path / "Livro de Finais (p. 2-3, 6).epub"
    assert result.page_indices == (1, 2, 5)
    body = _texts(result.path)
    assert "Capítulo 2" in body
    assert "Capítulo 3" in body
    assert "Capítulo 6" in body
    assert "Capítulo 1" not in body
    assert "Capítulo 4" not in body
    assert "Capítulo 5" not in body
    stamped = [e for e in result.document.metadata.custom if e.name == "pages"]
    assert stamped
    assert stamped[0].value == "2-3, 6"
    assert stamped[0].scheme == "caissa"
    assert "Páginas 2-3, 6 de 6" in (result.document.metadata.description or "")
    # the file itself carries the note: an EPUB reader shows the description
    read_back = read_epub(result.path)
    assert "Páginas 2-3, 6 de 6" in (read_back.metadata.description or "")


@requires_pymupdf
def test_the_images_of_the_pages_travel_inside_the_epub(tmp_path: Path):
    """A scanned or illustrated page is worth nothing as a placeholder: the
    importer extracts the images to a scratch folder, the EPUB packages them
    under ``Images/`` and points every ``src`` there -- never at a path on the
    author's disk."""
    spec = PageSpec(images=[(72.0, 72.0, 272.0, 272.0, 120, 120)]).text(
        "Uma figura acima e este parágrafo abaixo dela.", 72, 320
    )
    pdf = tmp_path / "Ilustrado.pdf"
    pdf.write_bytes(build_pdf([spec]))
    result = export_book(pdf, None, "epub", enable_ocr=False)
    assert result.export_result.stats.get("images", 0) >= 1
    with zipfile.ZipFile(result.path) as archive:
        names = archive.namelist()
        images = [n for n in names if n.startswith("OEBPS/Images/")]
        assert images, names
        page = archive.read("OEBPS/Text/s000.xhtml").decode("utf-8")
        opf = archive.read("OEBPS/content.opf").decode("utf-8")
        assert archive.read(images[0])[:4] == PNG_HEAD  # b"\x89PNG"
    assert 'src="../Images/' in page
    assert "image-missing" not in page
    assert str(tmp_path) not in page, "no path of this machine inside the book"
    assert f'href="Images/{images[0].rsplit("/", 1)[1]}"' in opf
    # the scratch folder is gone with the export
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("caissa-export-")]


@requires_pymupdf
def test_no_path_of_this_machine_travels_inside_the_epub(tmp_path: Path, monkeypatch):
    """The importer records where the PDF was and where each image was extracted --
    absolute paths, the user's name in them on Windows -- in the book's ``source``, in
    every node's provenance, in the diagram's source and in the resources.  The package
    names the files only (embedded IR, ``dc:source``, pages), the content hash still says
    which PDF it was; the document in memory keeps the real paths."""
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "decisoes"))
    spec = PageSpec(images=[(72.0, 72.0, 272.0, 272.0, 120, 120)]).text(
        "Uma figura acima e este parágrafo abaixo dela.", 72, 320
    )
    pdf = tmp_path / "Ilustrado.pdf"
    pdf.write_bytes(build_pdf([spec]))
    hit = DiagramHit(box=(72.0, 400.0, 272.0, 600.0), fen="8/8/8/4k3/8/8/4K3/8 w - - 0 1",
                     confidence=0.9, path=RecognitionPath.NEURAL, method="contour",
                     square_confidences=(0.95,) * 64)
    result = export_book(pdf, None, "epub", enable_ocr=False, import_options=PdfImportOptions(
        diagram_finder=lambda *_: [hit], games=False))
    source = result.document.metadata.source
    assert source is not None
    assert Path(source).is_absolute(), "the IR in memory keeps the path"
    assert local_paths_in_epub(result.path, tmp_path) == []
    back = read_epub(result.path, use_sidecar=True)
    (original,) = [b for b in result.document.body if isinstance(b, Diagram)]
    (diagram,) = [b for b in back.body if isinstance(b, Diagram)]
    assert back.metadata.source == diagram.source.path == "Ilustrado.pdf"
    assert original.source.content_hash
    assert diagram.source.content_hash == original.source.content_hash
    assert back.resources
    assert {r.path for r in back.resources} == {
        Path(r.path).name for r in result.document.resources if r.path
    }


@requires_pymupdf
def test_the_images_of_the_pages_are_embedded_in_the_docx(tmp_path: Path):
    """The same page in Word: the figure is an image part under ``word/media``
    and a ``w:drawing`` in the body -- not a ``[figura-p1-0001]`` marker."""
    spec = PageSpec(images=[(72.0, 72.0, 272.0, 272.0, 120, 120)]).text(
        "Uma figura acima e este parágrafo abaixo dela.", 72, 320
    )
    pdf = tmp_path / "Ilustrado.pdf"
    pdf.write_bytes(build_pdf([spec]))
    result = export_book(pdf, None, "docx", enable_ocr=False)
    assert result.export_result.stats.get("images", 0) >= 1
    with zipfile.ZipFile(result.path) as archive:
        media = [n for n in archive.namelist() if n.startswith("word/media/imagem")]
        assert media, archive.namelist()
        assert archive.read(media[0])[:4] == PNG_HEAD
        body = archive.read("word/document.xml").decode("utf-8")
        rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
        types = archive.read("[Content_Types].xml").decode("utf-8")
    assert "<w:drawing>" in body
    assert "[figura-p1-0001]" not in body
    assert 'Target="media/imagem1.png"' in rels
    assert 'Extension="png"' in types
    assert not any(
        warning.property == "images" for warning in result.export_result.degradation.warnings
    ), "with the file on disk no image falls back to the marker"


@requires_pymupdf
def test_zero_based_indices_and_an_explicit_destination(tmp_path: Path):
    pdf = _book(tmp_path)
    target = tmp_path / "saida" / "cap.docx"
    target.parent.mkdir()
    result = export_book(pdf, target, "docx", pages=[0, 4], enable_ocr=False)
    assert result.path == target
    assert result.page_indices == (0, 4)
    body = _texts(target)
    assert "Capítulo 1" in body
    assert "Capítulo 5" in body
    assert "Capítulo 3" not in body
    assert read_docx(target).body


@requires_pymupdf
def test_progress_comes_in_two_phases_and_cancel_writes_nothing(tmp_path: Path):
    pdf = _book(tmp_path)
    seen: list[tuple[str, int, int]] = []
    export_book(
        pdf, None, "epub", pages="1-2", enable_ocr=False, progress=lambda *a: seen.append(a)
    )
    phases = [p for p, _, _ in seen]
    assert phases[0] == "importando"
    assert phases[-1] == "gravando"
    assert seen[-1] == ("gravando", 1, 1)
    assert phases.index("gravando") > phases.index("importando")

    target = tmp_path / "nunca.epub"
    with pytest.raises(ImportCanceled):
        export_book(pdf, target, "epub", enable_ocr=False, should_cancel=lambda: True)
    assert not target.exists()


@requires_pymupdf
def test_bad_inputs_are_refused_before_anything_is_written(tmp_path: Path):
    pdf = _book(tmp_path)
    with pytest.raises(ExportError):
        export_book(pdf, None, "html")
    with pytest.raises(PageRangeError, match="não existe"):
        export_book(pdf, None, "epub", pages="1-40")
    with pytest.raises(IndexError):
        export_book(pdf, None, "epub", pages=[40])
    assert not list(tmp_path.glob("*.epub"))


# --------------------------------------------------------------------------- #
# The command line
# --------------------------------------------------------------------------- #


@requires_pymupdf
def test_the_cli_exports_a_range_and_reports(tmp_path: Path, capsys):
    pdf = _book(tmp_path)
    assert main([str(pdf), "--docx", "--paginas", "4-", "--sem-ocr"]) == 0
    out = capsys.readouterr().out
    assert "DOCX gravado em Livro de Finais (p. 4-6).docx" in out
    assert "3 página(s) (4-6)" in out
    assert (tmp_path / "Livro de Finais (p. 4-6).docx").is_file()


@requires_pymupdf
def test_the_cli_takes_the_format_from_the_output_name(tmp_path: Path, capsys):
    pdf = _book(tmp_path)
    target = tmp_path / "tudo.epub"
    assert main([str(pdf), "--saida", str(target), "--sem-ocr"]) == 0
    assert target.is_file()
    assert "livro completo" in capsys.readouterr().out


@requires_pymupdf
def test_the_cli_fails_loudly_on_a_bad_range_or_a_missing_format(tmp_path: Path, capsys):
    pdf = _book(tmp_path)
    assert main([str(pdf), "--epub", "--paginas", "5-3"]) == 2
    assert "termina antes" in capsys.readouterr().err
    with pytest.raises(SystemExit) as stop:
        main([str(pdf)])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        main([str(pdf), "--saida", str(tmp_path / "x.pdf")])
