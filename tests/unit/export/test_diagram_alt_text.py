"""The alt text never asserts what nobody read.

OCR_UI_ROADMAP_C2 passo A9 (analise §7.7): the importer builds a ``Diagram``
with the provisional empty board when it located a diagram it could not read,
and ``side_to_move_source="default"`` when nothing said whose move it is. The
alt text then read "tabuleiro vazio, jogam as brancas" to a screen-reader user
-- two claims with no reading behind them. These tests pin the wording the
exporters emit for an unread position, an unrecorded side and a low
confidence, and check it reaches the HTML that carries it.

The sabotage is the importer's own value: force the empty placement on a
node and the test must see the warning, not the enumeration.
"""

from __future__ import annotations

from pathlib import Path

from caissa.core.model import (
    Diagram,
    Document,
    DocumentMetadata,
    InlineDiagram,
    Paragraph,
    RecognitionPath,
    RecognitionResult,
    Text,
)
from caissa.export import export
from caissa.export.base import ExportOptions
from caissa.export.diagrams import _EMPTY_PLACEMENT, diagram_alt_text

EMPTY_BOARD = "8/8/8/8/8/8/8/8 w - - 0 1"
"""What ``caissa.ingest.pdf.importer._EMPTY_BOARD`` puts in an unread diagram."""

KINGS = "4k3/8/8/8/8/8/8/4K3"


def _machine(fen: str, **fields: object) -> RecognitionResult:
    return RecognitionResult(fen=fen, path=RecognitionPath.NEURAL, **fields)  # type: ignore[arg-type]


def test_the_constant_matches_the_importers_placeholder() -> None:
    """Compared, not imported; this is the check that the two do not drift apart."""
    from caissa.ingest.pdf import importer

    assert importer._EMPTY_BOARD.split()[0] == _EMPTY_PLACEMENT
    assert EMPTY_BOARD == importer._EMPTY_BOARD


def test_an_unread_diagram_says_so_instead_of_an_empty_board() -> None:
    """FEN vazia: the importer's node for a diagram it located but could not read."""
    node = Diagram(
        fen=EMPTY_BOARD,
        recognition=RecognitionResult(
            fen="", overall_confidence=0.0, side_to_move_source="default",
            path=RecognitionPath.VECTOR,
        ),
    )
    alt = diagram_alt_text(node)
    assert "posição não reconhecida" in alt
    assert "lado a jogar desconhecido" in alt
    assert "confiança da leitura: 0%" in alt
    assert "jogam as brancas" not in alt
    assert "tabuleiro vazio" not in alt


def test_a_side_nobody_read_is_not_white_by_default() -> None:
    """Lado ausente: a good reading whose side came from the importer's default."""
    node = Diagram(
        fen=f"{KINGS} w - - 0 1",
        recognition=_machine(KINGS, overall_confidence=0.97, side_to_move_source="default"),
    )
    alt = diagram_alt_text(node)
    assert "lado a jogar desconhecido" in alt
    assert "jogam as" not in alt
    assert "Rei preto em e8" in alt, "a posicao foi lida e continua descrita"
    assert "confiança de 97%" in alt


def test_a_bare_placement_has_no_side_to_assert() -> None:
    assert "lado a jogar desconhecido" in diagram_alt_text(Diagram(fen=KINGS))
    assert "lado a jogar desconhecido" in diagram_alt_text(InlineDiagram(fen=KINGS))


def test_a_low_confidence_reading_quotes_its_confidence() -> None:
    """Confianca baixa: the number travels with the description."""
    node = Diagram(
        fen=f"{KINGS} b - - 0 1",
        recognition=_machine(KINGS, overall_confidence=0.31, side_to_move_source="caption-after"),
    )
    alt = diagram_alt_text(node)
    assert "jogam as pretas" in alt
    assert "confiança de 31%" in alt
    assert "posição não reconhecida" not in alt


def test_a_machine_reading_without_confidence_is_not_asserted() -> None:
    node = Diagram(fen=f"{KINGS} w - - 0 1", recognition=_machine(KINGS))
    alt = diagram_alt_text(node)
    assert "posição não reconhecida" in alt
    assert "lado a jogar desconhecido" in alt
    assert "leitura provisória: Rei preto em e8" in alt


def test_a_hand_written_diagram_is_trusted_as_written() -> None:
    """The default ``RecognitionResult`` is a manual node: no machine, no doubt."""
    alt = diagram_alt_text(Diagram(fen=f"{KINGS} b - - 0 1"))
    assert alt == "Diagrama de xadrez, jogam as pretas. Rei preto em e8; Rei branco em e1."
    assert "desconhecid" not in diagram_alt_text(InlineDiagram(fen=f"{KINGS} w - - 0 1"))


def test_a_human_verified_diagram_is_trusted_over_the_machine() -> None:
    node = Diagram(
        fen=f"{KINGS} b - - 0 1",
        verified_by_human=True,
        recognition=_machine(KINGS, overall_confidence=0.0, side_to_move_source="default"),
    )
    alt = diagram_alt_text(node)
    assert "jogam as pretas" in alt
    assert "desconhecid" not in alt and "não reconhecida" not in alt


def test_a_hand_written_empty_board_is_still_an_empty_board() -> None:
    """Only the importer's placeholder is a non-reading; an author's empty board is a board."""
    alt = diagram_alt_text(Diagram(fen=EMPTY_BOARD))
    assert "tabuleiro vazio" in alt and "não reconhecida" not in alt
    alt = diagram_alt_text(Diagram(fen=EMPTY_BOARD, verified_by_human=True,
                                   recognition=_machine("", overall_confidence=0.0)))
    assert "tabuleiro vazio" in alt and "não reconhecida" not in alt


def test_an_explicit_alt_text_still_wins() -> None:
    node = Diagram(fen=EMPTY_BOARD, alt_text="Posicao do problema 12")
    assert diagram_alt_text(node) == "Posicao do problema 12"


def test_the_warning_reaches_the_exported_html(tmp_path: Path) -> None:
    """Teste de exportacao: FEN vazia, lado ausente, confianca baixa numa pagina."""
    document = Document(
        metadata=DocumentMetadata(title="Alt", language="pt-BR"),
        body=(
            Paragraph(content=(Text(content="Tres diagramas."),)),
            Diagram(
                fen=EMPTY_BOARD,
                recognition=RecognitionResult(
                    fen="", overall_confidence=0.0, side_to_move_source="default",
                    path=RecognitionPath.VECTOR,
                ),
            ),
            Diagram(
                fen=f"{KINGS} w - - 0 1",
                recognition=_machine(KINGS, overall_confidence=0.9, side_to_move_source="default"),
            ),
            Diagram(
                fen=f"{KINGS} b - - 0 1",
                recognition=_machine(KINGS, overall_confidence=0.31, side_to_move_source="text"),
            ),
        ),
    )
    target = tmp_path / "alt.html"
    export(document, target, "html", options=ExportOptions(embed_ir=False))
    html = target.read_text(encoding="utf-8")
    assert "posição não reconhecida" in html
    # Each diagram carries the description twice: aria-label and <title>.
    assert html.count("lado a jogar desconhecido") == 2 * 2
    assert "confiança de 31%" in html
    assert "jogam as pretas" in html
    assert "jogam as brancas" not in html
    assert "tabuleiro vazio" not in html


def test_the_render_cache_does_not_share_a_description_across_provenances() -> None:
    """Two nodes with the same FEN and different readings get different alt text."""
    from caissa.export.base import ExportContext
    from caissa.export.diagrams import DiagramRenderer
    from caissa.export.profiles import HTML_PROFILE

    document = Document(metadata=DocumentMetadata(title="x"), body=())
    renderer = DiagramRenderer(ExportContext(HTML_PROFILE, document))
    trusted = Diagram(fen=f"{KINGS} w - - 0 1")
    doubtful = Diagram(
        fen=f"{KINGS} w - - 0 1",
        recognition=_machine(KINGS, overall_confidence=0.9, side_to_move_source="default"),
    )
    assert "jogam as brancas" in renderer.svg(trusted).alt_text
    assert "lado a jogar desconhecido" in renderer.svg(doubtful).alt_text


def test_sabotage_forcing_the_empty_placement_demands_the_warning() -> None:
    """Sabotagem executada: the importer's placeholder on a node that looked read."""
    from dataclasses import replace

    node = Diagram(
        fen=f"{KINGS} w - - 0 1",
        recognition=_machine(KINGS, overall_confidence=0.95, side_to_move_source="text"),
    )
    assert "posição não reconhecida" not in diagram_alt_text(node)
    forced = replace(node, fen=EMPTY_BOARD)
    alt = diagram_alt_text(forced)
    assert "posição não reconhecida" in alt, alt
    assert "tabuleiro vazio" not in alt
