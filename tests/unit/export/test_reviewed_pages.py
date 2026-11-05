"""The pages edited in the *Revisão de texto* window go back to the trunk's notebook (R7 de volta).

What is pinned here:

* an import's page reads back in the trunk's format -- paragraphs, headings and diagrams in
  order, emphasis, style and alignment -- and that format applied to the same import gives the
  same words (the two directions agree);
* only pages with an **edited** region go: accepting a reading or keeping a region as an image
  puts no words of a person on the page;
* the window's import in hand serves when it built the pages and saw the decisions of now; when
  it did not, only those pages are imported again, with the decisions applied;
* with nothing edited there is nothing to import.
"""

from __future__ import annotations

from typing import Any

import pytest

from caissa.core.model import (
    Alignment,
    Diagram,
    DiagramSource,
    Document,
    Emphasis,
    Heading,
    Paragraph,
    ParagraphProps,
    Provenance,
    RunProps,
    SourceKind,
    Strong,
    Text,
)
from caissa.export import reviewed_pages as rp
from caissa.export.page_texts import apply_page_texts, page_text_of, page_texts_of
from caissa.ingest.pdf import ImportReport, ImportResult, PageReport
from caissa.ocr.review import Action, Decided, ReviewDecisions

FEN = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"


def _prov(page: int) -> Provenance:
    return Provenance(
        kind=SourceKind.OCR, page_index=page, confidence=0.9, document_path="livro.pdf"
    )


def _para(
    page: int, *content: Any, style: str | None = None, alignment: Alignment | None = None
) -> Paragraph:
    return Paragraph(
        content=tuple(content),
        props=ParagraphProps(style=style, alignment=alignment),
        provenance=_prov(page),
    )


def _diagram(page: int) -> Diagram:
    return Diagram(
        fen=FEN,
        source=DiagramSource(
            kind=SourceKind.PDF_TEXT_LAYER,
            path="livro.pdf",
            page_index=page,
            rect=(10.0, 20.0, 110.0, 120.0),
        ),
        provenance=_prov(page),
    )


def _imported(*body: Any, pages: tuple[int, ...] = (0, 1), digest: str = "") -> ImportResult:
    report = ImportReport(pages=[PageReport(index=i, source="ocr") for i in pages])
    report.review_decisions_digest = digest
    return ImportResult(document=Document(body=tuple(body)), report=report)


def _decisions(*entries: tuple[int, Action, str]) -> ReviewDecisions:
    return ReviewDecisions(
        document="livro.pdf",
        entries=tuple(
            Decided(page_index=page, rect=(0.0, 0.0, 10.0, 10.0), action=action, text="x", at=at)
            for page, action, at in entries
        ),
    )


def _words(block: Any) -> str:
    return "".join(getattr(i, "content", "") for i in getattr(block, "content", ()))


def test_a_page_reads_back_with_emphasis_style_alignment_and_its_diagram() -> None:
    imported = _imported(
        Heading(
            level=1,
            content=(Text(content="Capítulo 3"),),
            props=ParagraphProps(alignment=Alignment.CENTER),
            provenance=_prov(1),
        ),
        _para(
            1,
            Text(content="normal "),
            Text(content="forte", props=RunProps(font_weight=700)),
            Text(content=" e "),
            Emphasis(content=(Text(content="inclinado"),)),
            Text(content=" e "),
            Strong(content=(Text(content="duro"),)),
        ),
        _diagram(1),
        _para(1, Text(content="1.e4 e5"), style="Movetext"),
        _para(0, Text(content="outra página")),
    )
    page = page_text_of(imported, 1, saved_at="2026-10-29T10:00:00")
    assert page["format"] == 1
    assert (page["page_index"], page["state"], page["saved_at"]) == (
        1,
        "editada",
        "2026-10-29T10:00:00",
    )
    heading, prose, mark, moves = page["paragraphs"]
    assert heading == {
        "kind": "text",
        "style": "heading",
        "alignment": "center",
        "runs": [{"text": "Capítulo 3"}],
    }
    assert prose["runs"] == [
        {"text": "normal "},
        {"text": "forte", "bold": True},
        {"text": " e "},
        {"text": "inclinado", "italic": True},
        {"text": " e "},
        {"text": "duro", "bold": True},
    ]
    assert mark == {"kind": "diagram", "fen": FEN, "alignment": ""}
    assert (moves["style"], moves["runs"]) == ("notation", [{"text": "1.e4 e5"}])


def test_the_two_directions_agree_on_the_words() -> None:
    imported = _imported(
        _para(0, Text(content="lida")),
        _para(1, Text(content="corrigida na revisão")),
        _diagram(1),
        _para(1, Text(content="depois")),
    )
    applied = apply_page_texts(imported, page_texts_of(imported, [1]))
    words = [_words(b) or type(b).__name__ for b in applied.imported.document.body]
    assert words == ["lida", "corrigida na revisão", "Diagram", "depois"]


def test_only_pages_the_import_built_go() -> None:
    imported = _imported(_para(0, Text(content="a")), pages=(0,))
    assert [p["page_index"] for p in page_texts_of(imported, [0, 5])] == [0]


def test_only_edited_regions_count_and_the_last_edit_dates_the_page() -> None:
    decisions = _decisions(
        (2, Action.EDIT, "2026-10-28T09:00:00"),
        (2, Action.EDIT, "2026-10-29T09:00:00"),
        (3, Action.ACCEPT, "2026-10-29T10:00:00"),
        (4, Action.KEEP_IMAGE, ""),
    )
    assert rp.edited_pages(decisions) == {2: "2026-10-29T09:00:00"}
    assert rp.edited_pages(None) == {}


def test_nothing_edited_imports_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ReviewDecisions, "for_pdf", classmethod(lambda cls, _p: _decisions((1, Action.ACCEPT, "")))
    )
    monkeypatch.setattr(
        rp, "import_pdf", lambda *_a, **_k: pytest.fail("imported with nothing edited")
    )
    assert rp.reviewed_page_texts("livro.pdf") == rp.ReviewedPages()


def test_the_import_in_hand_serves_when_it_saw_these_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decisions = _decisions((1, Action.EDIT, "2026-10-29T09:00:00"))
    monkeypatch.setattr(ReviewDecisions, "for_pdf", classmethod(lambda cls, _p: decisions))
    monkeypatch.setattr(
        rp, "import_pdf", lambda *_a, **_k: pytest.fail("the import in hand served")
    )
    em_maos = _imported(_para(1, Text(content="corrigida")), digest=decisions.digest([0, 1]))
    found = rp.reviewed_page_texts("livro.pdf", document=em_maos)
    assert (found.pages, found.reimported) == ((1,), False)
    assert found.page_texts[0]["paragraphs"][0]["runs"] == [{"text": "corrigida"}]
    assert found.page_texts[0]["saved_at"] == "2026-10-29T09:00:00"


def test_a_stale_import_reimports_only_the_edited_pages_with_the_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decisions = _decisions((1, Action.EDIT, ""))
    monkeypatch.setattr(ReviewDecisions, "for_pdf", classmethod(lambda cls, _p: decisions))
    pedidos: list[Any] = []

    def importar(_source: Any, options: Any) -> ImportResult:
        pedidos.append(options)
        return _imported(_para(1, Text(content="com a decisão")), pages=(1,))

    monkeypatch.setattr(rp, "import_pdf", importar)
    velho = _imported(_para(1, Text(content="sem a decisão")), digest="outra")
    found = rp.reviewed_page_texts("livro.pdf", document=velho)
    assert found.reimported
    assert list(pedidos[0].pages) == [1], "only the edited page is read again"
    assert pedidos[0].review_decisions is decisions
    assert found.page_texts[0]["paragraphs"][0]["runs"] == [{"text": "com a decisão"}]


def test_sabotage_without_the_digest_check_the_stale_import_would_be_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check is what keeps the reading of before from going back as if it were the review."""
    decisions = _decisions((1, Action.EDIT, ""))
    monkeypatch.setattr(ReviewDecisions, "for_pdf", classmethod(lambda cls, _p: decisions))
    velho = _imported(_para(1, Text(content="sem a decisão")), digest="outra")
    assert not rp._serves(velho, rp.Path("livro.pdf"), [1])
