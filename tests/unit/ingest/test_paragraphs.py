"""Rows to paragraphs: hyphenation, indents, justification, page breaks, headings."""

from __future__ import annotations

import pytest

from caissa.ingest.pdf.document import OutlineEntry, open_pdf
from caissa.ingest.pdf.paragraphs import (
    BlockDraft,
    ParagraphBuilder,
    ParagraphConfig,
    Row,
    _append_row,
    _hyphen_wrap,
    _split_move,
    attach_outline,
    diagram_extents,
    finish_document,
    layout_page,
    looks_like_moves,
    promote_bold_headings,
    tag_captions,
)
from caissa.ingest.pdf.textlayer import TextSpan, extract_page_text
from caissa.ocr.types import RegionKind

from .conftest import LOREM, PageSpec, lines_of, requires_pymupdf

pytestmark = requires_pymupdf


def _rows_of(pdf_path, index=0, **kwargs):
    with open_pdf(pdf_path) as doc:
        frame = doc.frame(index)
        with doc.locked() as raw:
            text = extract_page_text(raw[index], frame)
    return layout_page(text, **kwargs), text


def _blocks(pages) -> list[BlockDraft]:
    builder = ParagraphBuilder()
    out: list[BlockDraft] = []
    for page in pages:
        out.extend(builder.feed(page))
    tail = builder.flush()
    if tail is not None:
        out.append(tail)
    return out


# --------------------------------------------------------------------------- #
# Line joining
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tail", "head", "expected"),
    [
        ("preci-", "são", True),
        ("2-", "3", False),  # digits keep their hyphen
        ("Nf3-", "Kg1", False),  # before a capital it is text
        ("-", "x", False),
        ("a‐", "b", True),  # U+2010
    ],
)
def test_hyphen_wrap(tail, head, expected):
    assert _hyphen_wrap(tail, head) is expected


def test_split_move_closes_up():
    assert _split_move("26.Bxc6 K", "h8!")
    assert _split_move("♘", "xe5")
    assert not _split_move("the king", "h8")


def test_append_row_undoes_hyphenation_and_joins_moves():
    def span(text: str) -> TextSpan:
        return TextSpan(text=text, box=(0, 0, 1, 1))

    spans = [span("preci-")]
    _append_row(spans, [span("são total")])
    assert "".join(s.text for s in spans) == "precisão total"
    spans = [span("26.Bxc6 K")]
    _append_row(spans, [span("h8!")])
    assert "".join(s.text for s in spans) == "26.Bxc6 Kh8!"
    spans = [span("fim da linha")]
    _append_row(spans, [span("continua")])
    assert "".join(s.text for s in spans) == "fim da linha continua"


# --------------------------------------------------------------------------- #
# Paragraph breaks on a page
# --------------------------------------------------------------------------- #


def test_indented_first_lines_open_paragraphs(pdf_file):
    spec = PageSpec()
    y = 100.0
    paragraphs = [LOREM, "Segundo parágrafo curto.", LOREM]
    for paragraph in paragraphs:
        items = lines_of(paragraph, x=72, y=y, width_chars=60, indent_first=14.0)
        spec.items.extend(items)
        y += 13.2 * len(items)
    path = pdf_file([spec])
    page, _ = _rows_of(path)
    blocks = _blocks([page])
    assert [b.text for b in blocks] == paragraphs


def test_vertical_gap_opens_a_paragraph(pdf_file):
    spec = PageSpec()
    spec.items.extend(lines_of(LOREM, x=72, y=100, width_chars=60))
    spec.items.extend(lines_of("Depois de um espaço.", x=72, y=100 + 13.2 * 3 + 20, width_chars=60))
    path = pdf_file([spec])
    page, _ = _rows_of(path)
    assert [b.text for b in _blocks([page])] == [LOREM, "Depois de um espaço."]


def test_hyphenated_wraps_are_rejoined(pdf_file):
    spec = PageSpec()
    text = (
        "A concentração absoluta do enxadrista profissional é determinante para o resultado final."
    )
    spec.items.extend(lines_of(text, x=72, y=100, width_chars=30, hyphenate=True))
    hyphenated = [i.text for i in spec.items if i.text.endswith("-")]
    assert hyphenated, "o gerador deveria ter hifenizado alguma linha"
    path = pdf_file([spec])
    page, _ = _rows_of(path)
    assert [b.text for b in _blocks([page])] == [text]


def test_fragments_on_one_baseline_become_one_row(pdf_file):
    """A block is not a paragraph: two blocks on one baseline are one line."""
    spec = PageSpec()
    spec.text("primeira metade", 72, 100)
    spec.text("segunda metade", 180, 100)
    spec.text("linha seguinte do mesmo parágrafo", 72, 113)
    path = pdf_file([spec])
    page, _ = _rows_of(path)
    assert len(page.rows) == 2
    assert page.rows[0].text == "primeira metade segunda metade"
    assert [b.text for b in _blocks([page])] == [
        "primeira metade segunda metade linha seguinte do mesmo parágrafo"
    ]


def test_justified_column_reads_its_right_margin(pdf_file):
    """A hanging-indent list: the indent rule alone cuts items in half."""
    spec = PageSpec()
    # Courier: every glyph 6 pt wide at 10 pt, so a 12 pt hanging indent is
    # exactly two characters and every full line ends on the same margin.
    full = "x" * 58
    y = 100.0
    lines = []
    for n in range(1, 5):
        lines.append((f"{n}. {full[:55]}", 72))
        lines.append((full[:56], 84))
        lines.append((full[:30] + ".", 84))
    for text, x in lines:
        spec.text(text, x, y, size=10, font="cour")
        y += 12
    for i in range(8):
        spec.text(full, 72, y + i * 12, size=10, font="cour")
    path = pdf_file([spec])
    page, _ = _rows_of(path)
    assert page.measures, "a coluna justificada devia ter medida"
    blocks = _blocks([page])
    items = [b.text for b in blocks if b.text.startswith(("1.", "2.", "3.", "4."))]
    assert len(items) == 4
    assert all(b.text.endswith(".") for b in blocks[:4])


# --------------------------------------------------------------------------- #
# Across pages
# --------------------------------------------------------------------------- #


def test_a_paragraph_continues_across_the_page_break(pdf_file):
    first = PageSpec()
    first.items.extend(
        lines_of(
            "A posição exige precisão porque cada tempo conta e o", x=72, y=700, width_chars=60
        )
    )
    second = PageSpec()
    second.items.extend(
        lines_of("rei precisa chegar ao canto antes do peão.", x=72, y=100, width_chars=60)
    )
    path = pdf_file([first, second])
    with open_pdf(path) as doc:
        pages = []
        for index in range(2):
            with doc.locked() as raw:
                text = extract_page_text(raw[index], doc.frame(index))
            pages.append(layout_page(text))
    blocks = _blocks(pages)
    assert len(blocks) == 1
    assert blocks[0].first_page == 0
    assert blocks[0].last_page == 1
    assert blocks[0].text == (
        "A posição exige precisão porque cada tempo conta e o rei precisa chegar ao canto "
        "antes do peão."
    )


def test_a_sentence_that_ended_does_not_continue(pdf_file):
    first = PageSpec().text("Frase completa no fim da página.", 72, 700)
    second = PageSpec().text("Nova frase na página seguinte.", 72, 100)
    path = pdf_file([first, second])
    with open_pdf(path) as doc:
        pages = []
        for index in range(2):
            with doc.locked() as raw:
                text = extract_page_text(raw[index], doc.frame(index))
            pages.append(layout_page(text))
    assert len(_blocks(pages)) == 2


# --------------------------------------------------------------------------- #
# Document-level passes
# --------------------------------------------------------------------------- #


def _draft(
    text: str, size: float, kind=RegionKind.PARAGRAPH, bold=False, page=0, rows=1
) -> BlockDraft:
    span = TextSpan(text=text, box=(0, 0, 100, size), size=size, bold=bold)
    return BlockDraft(
        kind=kind,
        spans=[span],
        size=size,
        first_page=page,
        last_page=page,
        boxes={page: span.box},
        rows=rows,
    )


def test_heading_levels_are_ranked_by_size():
    blocks = [
        _draft("Capítulo Um", 24.0, RegionKind.HEADING),
        _draft("Seção", 16.0, RegionKind.HEADING),
        _draft("corpo", 10.0),
        _draft("Outra Seção", 16.0, RegionKind.HEADING),
        _draft("curto", 16.0, RegionKind.HEADING),  # 5 letters: heading needs 4, fine
        _draft("x", 16.0, RegionKind.HEADING),  # too short: demoted
    ]
    finish_document(blocks, body_size=10.0)
    assert [(b.kind, b.heading_level) for b in blocks[:2]] == [
        (RegionKind.HEADING, 1),
        (RegionKind.HEADING, 2),
    ]
    assert blocks[3].heading_level == 2
    assert blocks[5].kind is RegionKind.PARAGRAPH
    assert blocks[0].style == "Heading 1"
    assert blocks[2].style == "Body"


def test_bold_run_in_heads_are_promoted_below_the_ranked_levels():
    blocks = [
        _draft("Capítulo", 24.0, RegionKind.HEADING),
        _draft("Tragicomedies", 10.0, bold=True),
        _draft("1.Bb1!! Kc3 2.Kb5", 10.0, bold=True),  # moves, not a title
        _draft("Frase terminada em ponto.", 10.0, bold=True),
    ]
    assert promote_bold_headings(blocks, 10.0, ParagraphConfig()) == 1
    finish_document(blocks, body_size=10.0)
    assert blocks[1].kind is RegionKind.HEADING
    assert blocks[1].heading_level == 2
    assert blocks[2].kind is RegionKind.MOVETEXT
    assert blocks[3].kind is RegionKind.PARAGRAPH


def test_outline_attaches_by_title_within_a_page_window():
    blocks = [
        _draft("Introdução", 10.0, page=3),
        _draft("prosa", 10.0, page=3),
        _draft("Finais de torre", 10.0, page=10),
    ]
    outline = [
        OutlineEntry(1, "Introdução", 2),
        OutlineEntry(2, "Finais de Torre", 10),
        OutlineEntry(1, "Nada", 50),
    ]
    assert attach_outline(blocks, outline) == 2
    assert (blocks[0].kind, blocks[0].heading_level, blocks[0].outline_title) == (
        RegionKind.HEADING,
        1,
        "Introdução",
    )
    assert (blocks[2].kind, blocks[2].heading_level) == (RegionKind.HEADING, 2)
    assert blocks[1].kind is RegionKind.PARAGRAPH


def test_captions_by_wording_and_by_italics_after_a_figure():
    italic = TextSpan(text="Kasparov – Karpov, 1985", box=(0, 0, 100, 10), size=10.0, italic=True)
    blocks = [
        _draft("Position after 23.Nf3", 10.0),
        BlockDraft(
            kind=RegionKind.PARAGRAPH,
            spans=[italic],
            size=10.0,
            first_page=1,
            last_page=1,
            boxes={1: italic.box},
        ),
        _draft("Texto comum.", 10.0, page=2),
    ]
    tag_captions(blocks, {1: 1})
    assert [b.kind for b in blocks] == [
        RegionKind.CAPTION,
        RegionKind.CAPTION,
        RegionKind.PARAGRAPH,
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.e4 e5 2.Nf3 Nc6 3.Bb5 a6", True),
        ("1.e4", True),
        ("White had to play 1.Kh2! Black can neither drive White's king from the corner.", False),
        ("1...Kxb1 also loses: 2.Kb3 Kc1 3.Kc3 Kd1 (3...Kb1 4.g6+–) 4.Kd3", True),
        ("Prosa sem lance algum.", False),
    ],
)
def test_looks_like_moves_needs_notation_to_carry_the_paragraph(text, expected):
    assert looks_like_moves(text) is expected


# --------------------------------------------------------------------------- #
# Diagrams and labels
# --------------------------------------------------------------------------- #


def test_axis_labels_leave_the_flow_and_grow_the_diagram_extent(pdf_file):
    spec = PageSpec()
    board = (100.0, 100.0, 300.0, 300.0)
    for i, digit in enumerate("87654321"):
        spec.text(digit, 88, 118 + i * 25, size=9)
    spec.text("a b c d e f g h", 110, 318, size=9)
    spec.text("Legenda do diagrama", 130, 345, size=10)
    spec.items.extend(lines_of(LOREM, x=330, y=100, width_chars=40))
    path = pdf_file([spec])
    with open_pdf(path) as doc, doc.locked() as raw:
        text = extract_page_text(raw[0], doc.frame(0))
    extents = diagram_extents(text, [board])
    assert extents[0][0] < board[0]
    assert extents[0][3] > board[3]
    page = layout_page(text, diagrams=extents)
    texts = [r.text for r in page.rows]
    assert "8" not in texts
    assert "a b c d e f g h" not in texts
    assert "Legenda do diagrama" in texts


def test_row_helpers():
    span = TextSpan(text="￼", box=(0, 0, 5, 5))
    row = Row(
        box=(0, 0, 5, 5),
        spans=(span,),
        blocks=frozenset({0}),
        size=10.0,
        column=0,
        kind=RegionKind.PARAGRAPH,
        page_index=0,
    )
    assert row.starts_with_image
    assert row.ends_with_image
