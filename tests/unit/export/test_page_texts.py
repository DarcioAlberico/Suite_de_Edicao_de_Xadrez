"""The trunk's corrected pages replace the import's reading before the book is written (R7).

The trunk's *Texto* tab keeps every page a person corrected in a notebook; *Exportar o livro
para EPUB…/DOCX…* wrote the suite's reading of the same pages.  What is pinned here:

* on a hand-built import, the page's text goes and its pictures stay, each diagram mark of the
  notebook taking the next diagram of the page, the rest after the text;
* the image of an unread page and the figure of an abstained region go with the text;
* the report of the import in hand is never touched -- the window exports it again;
* the losses are said: a paragraph joined across pages, a mark with no diagram;
* end to end, a synthetic PDF exported with one corrected page carries the correction on that
  page and the reading on the other, and the summary says how many pages came from the notebook.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_INGEST_TESTS = Path(__file__).resolve().parent.parent / "ingest"
if str(_INGEST_TESTS) not in sys.path:
    sys.path.insert(0, str(_INGEST_TESTS))

from caissa.core.model import (  # noqa: E402
    Alignment,
    Diagram,
    DiagramSource,
    Document,
    Figure,
    Heading,
    ImageBlock,
    Paragraph,
    Provenance,
    SourceKind,
    Text,
)
from caissa.export import export_book, read_epub  # noqa: E402
from caissa.export.page_texts import PageText, apply_page_texts  # noqa: E402
from caissa.ingest.pdf import (  # noqa: E402
    ImportReport,
    ImportResult,
    PageReport,
    PdfImportOptions,
    import_pdf,
)
from conftest import LOREM, PageSpec, build_pdf, lines_of, requires_pymupdf  # noqa: E402

FEN = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"


def _prov(page: int, *, note: str | None = None, kind: SourceKind = SourceKind.OCR,
          confidence: float | None = 0.9) -> Provenance:
    return Provenance(kind=kind, page_index=page, confidence=confidence, note=note,
                      document_path="livro.pdf", document_hash="cc" * 32)


def _para(page: int, text: str, **kwargs: object) -> Paragraph:
    return Paragraph(content=(Text(content=text),), provenance=_prov(page, **kwargs))  # type: ignore[arg-type]


def _diagram(page: int, fen: str = FEN) -> Diagram:
    return Diagram(
        fen=fen,
        source=DiagramSource(kind=SourceKind.PDF_TEXT_LAYER, path="livro.pdf", page_index=page,
                             rect=(10.0, 20.0, 110.0, 120.0)),
        provenance=_prov(page),
    )


def _imported(*body: object, pages: tuple[int, ...] = (0, 1, 2)) -> ImportResult:
    report = ImportReport(pages=[PageReport(index=i, source="text-layer") for i in pages])
    return ImportResult(document=Document(body=tuple(body)), report=report)  # type: ignore[arg-type]


def _page(index: int, *paragraphs: dict[str, object], saved_at: str = "") -> dict[str, object]:
    return {"format": 1, "page_index": index, "state": "editada", "saved_at": saved_at,
            "paragraphs": list(paragraphs)}


def _text(text: str, **kwargs: object) -> dict[str, object]:
    return {"kind": "text", "runs": [{"text": text}], **kwargs}


MARK = {"kind": "diagram", "fen": "", "alignment": "center"}


def _words(block: object) -> str:
    return "".join(getattr(i, "content", "") for i in getattr(block, "content", ()))


def test_the_page_text_goes_and_each_mark_takes_the_next_diagram() -> None:
    first, second = _diagram(1), _diagram(1, "8/8/8/8/8/8/8/K6k w - - 0 1")
    imported = _imported(
        _para(0, "página um"), _para(1, "lida errada"), first, _para(1, "entre"), second,
        _para(1, "fim lido"), _para(2, "página três"),
    )
    applied = apply_page_texts(
        imported, [_page(1, _text("corrigida"), MARK, _text("depois do primeiro"))]
    )
    body = applied.imported.document.body
    assert [_words(b) or type(b).__name__ for b in body] == [
        "página um", "corrigida", "Diagram", "depois do primeiro", "Diagram", "página três",
    ], "the mark takes the first diagram; the one no mark took follows the page's text"
    assert body[2] is first
    assert body[4] is second
    assert applied.pages == (1,)
    new = body[1]
    assert new.provenance is not None
    assert new.provenance.kind is SourceKind.HUMAN
    assert new.provenance.verified_by_human
    assert new.provenance.page_index == 1
    assert new.provenance.document_hash == "cc" * 32, "the sidecar header reads it from here"


def test_emphasis_style_and_alignment_reach_the_ir() -> None:
    applied = apply_page_texts(_imported(_para(0, "x")), [_page(
        0,
        {"kind": "text", "style": "heading", "alignment": "center",
         "runs": [{"text": "Capítulo 3", "bold": True}]},
        {"kind": "text", "runs": [{"text": "normal "}, {"text": "forte", "bold": True},
                                  {"text": " e "}, {"text": "inclinado", "italic": True}]},
        _text("1.e4 e5", style="notation"),
    )])
    heading, prose, moves = applied.imported.document.body
    assert isinstance(heading, Heading)
    assert heading.level == 1
    assert heading.props.style == "Heading 1"
    assert heading.props.alignment is Alignment.CENTER
    assert isinstance(prose, Paragraph)
    assert prose.props.style == "Body"
    assert [(t.content, t.props.font_weight, t.props.italic) for t in prose.content] == [
        ("normal ", None, None), ("forte", 700, None), (" e ", None, None),
        ("inclinado", None, True),
    ]
    assert moves.props.style == "Movetext", "the style the importer gives notation"


def test_the_unread_page_image_and_the_abstained_region_go_with_the_text() -> None:
    scan = ImageBlock(resource="pagina-p1", provenance=_prov(0, kind=SourceKind.IMAGE,
                                                               confidence=0.0, note="image-only"))
    abstained = Figure(content=(ImageBlock(resource="regiao-p1"),),
                       provenance=_prov(0, kind=SourceKind.IMAGE, confidence=0.0,
                                        note="OCR abstido: baixa confiança"))
    figure = Figure(content=(ImageBlock(resource="figura-p1"),),
                    provenance=_prov(0, kind=SourceKind.IMAGE, confidence=1.0))
    applied = apply_page_texts(_imported(scan, abstained, figure), [_page(0, _text("lido à mão"))])
    assert [_words(b) or b for b in applied.imported.document.body] == ["lido à mão", figure]


def test_a_page_the_import_had_nothing_on_goes_between_its_neighbours() -> None:
    imported = _imported(_para(0, "um"), _para(2, "três"))
    applied = apply_page_texts(imported, [_page(1, _text("dois"))])
    assert [_words(b) for b in applied.imported.document.body] == ["um", "dois", "três"]


def test_pages_the_import_did_not_build_are_ignored_and_nothing_changes() -> None:
    imported = _imported(_para(0, "um"), pages=(0,))
    applied = apply_page_texts(imported, [_page(5, _text("fora"))])
    assert applied.imported is imported
    assert applied.pages == ()


def test_the_report_in_hand_is_not_touched() -> None:
    imported = _imported(_para(0, "um"))
    before = dict(imported.report.counters)
    for _ in range(2):  # the window exports the same import twice
        applied = apply_page_texts(imported, [_page(0, _text("corrigido"))])
        assert applied.imported.report is imported.report
    assert imported.report.counters == before
    assert [_words(b) for b in imported.document.body] == ["um"], "the import in hand stays as read"


def test_the_losses_are_said() -> None:
    joined = _para(0, "começa aqui e", note="continua até a página 1")
    applied = apply_page_texts(_imported(joined), [_page(0, _text("começa aqui e"), MARK)])
    assert applied.notes == (
        "página 1: o parágrafo que seguia na página seguinte saiu com o texto do caderno, e a "
        "parte de lá ficou de fora",
        "página 1: 1 diagrama(s) do caderno sem diagrama correspondente na importação",
    )


def test_an_unknown_format_is_refused() -> None:
    with pytest.raises(ValueError, match="formato"):
        PageText.from_dict({"format": 2, "page_index": 0})
    with pytest.raises(ValueError, match="tipo"):
        PageText.from_dict({"format": 1, "page_index": 0, "paragraphs": [{"kind": "tabela"}]})


@pytest.fixture
def book(tmp_path: Path) -> Path:
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=80, width_chars=60))
    path = tmp_path / "livro.pdf"
    path.write_bytes(build_pdf([spec, spec]))
    return path


def _paragraphs(path: Path) -> list[str]:
    return [_words(b) for b in read_epub(path).body if isinstance(b, (Paragraph, Heading))]


@requires_pymupdf
def test_the_corrected_page_reaches_the_epub_imported_now_or_in_hand(
    book: Path, tmp_path: Path
) -> None:
    folhas = [_page(0, _text("Folha corrigida no caderno."), saved_at="2026-10-28T10:00:00")]
    result = export_book(book, tmp_path / "agora.epub", "epub", pages=[0, 1], enable_ocr=False,
                         import_options=PdfImportOptions(games=False), page_texts=folhas)
    lidos = _paragraphs(result.path)
    assert lidos[0] == "Folha corrigida no caderno."
    assert len(lidos) > 1
    assert lidos[-1].startswith(LOREM[:20]), "the second page keeps the reading"
    assert result.page_texts_applied == 1
    assert "1 folha(s) com o texto corrigido no caderno" in result.summary()

    imported = import_pdf(book, PdfImportOptions(pages=[0, 1], games=False, enable_ocr=False,
                                                 asset_dir=tmp_path / "assets"))
    em_maos = export_book(book, tmp_path / "em-maos.epub", "epub", pages=[0, 1],
                          document=imported, page_texts=folhas)
    assert em_maos.import_report is imported.report, "the import in hand was used"
    assert _paragraphs(em_maos.path) == lidos


@requires_pymupdf
def test_sabotage_without_page_texts_the_epub_has_the_reading(book: Path, tmp_path: Path) -> None:
    result = export_book(book, tmp_path / "sem.epub", "epub", pages=[0, 1], enable_ocr=False,
                         import_options=PdfImportOptions(games=False))
    assert "Folha corrigida no caderno." not in _paragraphs(result.path)
    assert result.page_texts_applied == 0
    assert "caderno" not in result.summary()
