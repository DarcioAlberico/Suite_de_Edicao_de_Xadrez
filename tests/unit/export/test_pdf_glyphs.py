"""The exported PDF carries the figurines and the NAG signs the IR asked for.

OCR_UI_ROADMAP_C2 passo A6 (analise §5.4): the PDF writer chose its faces
from a list of text fonts none of which has U+2654-265F nor ``⩲ ⩱ ⨁``, and
``_draw_line`` dropped every character the face lacked without a word. A
figurine book exported to PDF lost every piece. The gate here is the text
layer PyMuPDF reads back: every code point the IR rendered must be in it.

The sabotage is the same table without the ``symbol`` face: the gate must go
red *and* the export must declare the substitution, so the fidelity report
counts the loss instead of quoting 100 %.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle, PieceType
from caissa.core.model import (
    Document,
    DocumentMetadata,
    DocumentSettings,
    Move,
    NagSymbol,
    Paragraph,
    PieceGlyph,
    Space,
    Text,
)
from caissa.core.model.degradation import DegradationKind
from caissa.export import pdf as pdf_module
from caissa.export.base import ExportResult
from caissa.export.pdf import PdfExporter, PdfOptions
from caissa.export.text import figurine_char, nag_symbol, render_move

pymupdf = pytest.importorskip("pymupdf")

FIGURINE_MOVE = Move(san="Nf3", ply=1, render=MoveRenderStyle.FIGURINE, show_move_number=True)
LOOSE_SYMBOLS = "⩲ ⩱ ⨁"
"""The three signs the analysis measured as absent from every text face."""


def _fixture() -> Document:
    """One paragraph with every kind of chess glyph the IR can ask for."""
    return Document(
        metadata=DocumentMetadata(title="Glifos", language="pt-BR"),
        settings=DocumentSettings(notation_language="pt", figurine_set=FigurineSet.BLACK),
        body=(
            Paragraph(
                content=(
                    Text(content="Depois de "),
                    FIGURINE_MOVE,
                    Space(),
                    PieceGlyph(piece=PieceType.KNIGHT),
                    Space(),
                    NagSymbol(nag=14),
                    Space(),
                    NagSymbol(nag=22),
                    Space(),
                    Text(content=LOOSE_SYMBOLS),
                    Text(content=" as brancas estao melhor."),
                )
            ),
        ),
    )


def _expected_codepoints(document: Document) -> set[str]:
    """Every non-space character the IR renders, as the exporter renders it."""
    wanted: set[str] = set()
    wanted.update(render_move(FIGURINE_MOVE, document))
    wanted.update(figurine_char(PieceType.KNIGHT.value, FigurineSet.BLACK))
    wanted.update(nag_symbol(14))
    wanted.update(nag_symbol(22))
    wanted.update(LOOSE_SYMBOLS)
    return {char for char in wanted if not char.isspace()}


def _export(tmp_path: Path, document: Document) -> tuple[ExportResult, str]:
    target = tmp_path / "glifos.pdf"
    result = PdfExporter().export(document, target, PdfOptions(embed_ir=False))
    with pymupdf.open(str(target)) as handle:
        text = "".join(page.get_text() for page in handle)
    return result, text


def _substitutions(result: ExportResult) -> list[str]:
    return [
        warning.original or ""
        for warning in result.degradation.warnings
        if warning.kind is DegradationKind.SUBSTITUTED and warning.property == "font_glyph"
    ]


def test_symbol_face_is_installed_on_this_machine() -> None:
    """Without it the gate below cannot be green, and the reason must be visible."""
    assert pdf_module._find_font(pdf_module._FALLBACK_FILES["symbol"]) is not None, (
        "nenhuma face de simbolos (seguisym.ttf, DejaVuSans.ttf, Noto Sans Symbols 2) "
        "instalada; o PDF nao pode carregar figurinas nesta maquina"
    )


def test_pdf_text_layer_carries_every_chess_codepoint(tmp_path: Path) -> None:
    """Portao A6: cada ponto de codigo do IR esta no texto que o PyMuPDF le."""
    document = _fixture()
    result, text = _export(tmp_path, document)

    missing = sorted(char for char in _expected_codepoints(document) if char not in text)
    assert not missing, (
        "faltam no PDF: " + ", ".join(f"U+{ord(c):04X} {c!r}" for c in missing)
    )
    assert "♞" in text, "o lance em figurina perdeu o cavalo"
    assert "⩲" in text and "⨀" in text, "os NAG $14/$22 nao chegaram ao PDF"
    assert _substitutions(result) == [], "nenhum glifo devia ter sido substituido"
    assert result.stats.get("pages", 0) >= 1


def test_without_the_symbol_face_the_loss_is_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sabotagem executada: sem a face symbol o texto perde os glifos E o registo acusa.

    This is the analysis' finding reproduced on purpose -- the old table -- so
    that the declared fidelity can never again say 100 % over a page that lost
    its figurines.
    """
    without_symbol = {
        key: value for key, value in pdf_module._FALLBACK_FILES.items() if key != "symbol"
    }
    monkeypatch.setattr(pdf_module, "_FALLBACK_FILES", without_symbol)
    document = _fixture()
    result, text = _export(tmp_path, document)

    missing = [char for char in _expected_codepoints(document) if char not in text]
    assert missing, "a sabotagem nao mordeu: as faces de texto desta maquina tem os glifos"
    substituted = _substitutions(result)
    assert substituted, "o glifo sumiu do PDF sem uma substituicao registada"
    assert any("U+265E" in item for item in substituted), substituted
    assert any("sem glifo" in note for note in result.notes), result.notes


def test_a_mixed_line_is_measured_with_the_faces_it_is_set_in(tmp_path: Path) -> None:
    """A figurine inside a Times paragraph does not throw the line's width off.

    The run is split by face *before* the words are measured, so the advance
    the layout adds up is the advance the page shows. The check is on the
    content stream: the symbol face is selected (``/F<n> <size> Tf``) between
    two selections of the roman face on the same line.
    """
    document = _fixture()
    target = tmp_path / "linha.pdf"
    PdfExporter().export(document, target, PdfOptions(embed_ir=False))
    with pymupdf.open(str(target)) as handle:
        page = handle[0]
        spans = [
            (span["font"], span["text"])
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", ())
            for span in line["spans"]
        ]
    fonts_used = {font for font, _ in spans}
    assert len(fonts_used) >= 2, f"uma face so na linha mista: {spans}"
    knight_spans = [font for font, text in spans if "♞" in text]
    roman_spans = [font for font, text in spans if "Depois" in text]
    assert knight_spans and roman_spans
    assert knight_spans[0] != roman_spans[0], "o cavalo saiu da face de texto"


def test_latex_russian_prints_the_canonical_letters() -> None:
    """``typeset/latex.py`` reads the canonical table: ``Кр`` for the king, ``К`` for the knight."""
    from caissa.typeset import latex

    assert latex.typeset_move("Kd1", language="ru", figurine=False).startswith("Кр")
    assert latex.typeset_move("Nf3", language="ru", figurine=False).startswith("Кf3")
    assert latex.typeset_move("e8=Q", language="ru", figurine=False).endswith("=Ф")


def test_nag_symbols_follow_the_notation_table() -> None:
    """``$22`` is the zugzwang circle and ``$138`` time pressure -- not one sign for both."""
    from caissa.notation.nag_table import NAG_BY_CODE

    for code, nag in NAG_BY_CODE.items():
        assert nag_symbol(int(code[1:])) == nag.glyph, code
    assert nag_symbol(22) != nag_symbol(138)
    assert nag_symbol(44) == "©"
    assert nag_symbol(8) == "□" and nag_symbol(11) == "=" and nag_symbol(12) == "="
    assert nag_symbol(99) == "$99"
