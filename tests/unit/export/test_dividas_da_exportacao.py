"""As dívidas da exportação que o editor poria na tela (Editor HTML/CSS, passo H4; spec §2.7).

Um teste por item dos 3 a 9, cada um reprovando no código de antes do passo. Os itens 1, 2 e 10
têm as fixtures positivas do importador real em `benchmarks/editor_dividas.py` (`--fixtures`).
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle, PieceType
from caissa.core.model import (
    Diagram,
    Document,
    DocumentSettings,
    Heading,
    Paragraph,
    PieceGlyph,
    Provenance,
    RecognitionPath,
    RecognitionResult,
    Text,
)
from caissa.export import export
from caissa.export.base import Capability, ExportContext, ExportOptions
from caissa.export.diagrams import (
    DiagramRenderer,
    descrever_posicao,
    diagram_alt_text,
    numeros_de_diagrama,
)
from caissa.export.html import BASE_CSS, PILHA_DE_FIGURINAS, read_html_text
from caissa.export.profiles import EPUB_PROFILE, HTML_PROFILE
from caissa.export.text import game_from_pgn
from caissa.ingest.pdf.games import render_do_livro

KINGS = "4k3/8/8/8/8/8/8/4K3"


def _html(tmp_path: Path, documento: Document) -> str:
    destino = tmp_path / "livro.html"
    export(documento, destino, "html", options=ExportOptions(embed_ir=False))
    return destino.read_text(encoding="utf-8")


def _epub(tmp_path: Path, documento: Document) -> dict[str, str]:
    destino = tmp_path / "livro.epub"
    export(documento, destino, "epub", options=ExportOptions(embed_ir=False))
    with zipfile.ZipFile(destino) as pacote:
        return {i.filename: pacote.read(i.filename).decode("utf-8", "replace")
                for i in pacote.infolist() if not i.is_dir()}


# ---------------------------------------------------------------------- item 3: o alt


def test_descrever_posicao_e_pura_e_nao_cita_confianca_nem_motor() -> None:
    assert descrever_posicao(f"{KINGS} b - - 0 1", "b", "pt-BR") == (
        "Diagrama de xadrez, jogam as pretas. Rei preto em e8; Rei branco em e1.")
    assert descrever_posicao(f"{KINGS} w - - 0 1", "w", "en-GB") == (
        "Chess diagram, White to move. Black king on e8; White king on e1.")
    lida = descrever_posicao("8/8/8/8/8/8/4P3/8", None, "pt-BR", conferida=False)
    assert lida == ("Diagrama de xadrez, lado a jogar desconhecido. Peão branco em e2. "
                    "posição lida por máquina, não conferida por uma pessoa.")
    assert descrever_posicao(None, None) == (
        "Diagrama de xadrez, lado a jogar desconhecido. posição não reconhecida.")
    for texto in (lida, descrever_posicao(f"{KINGS} b - - 0 1", "b", "en", conferida=False)):
        assert "%" not in texto
        assert "confian" not in texto


def test_a_revisao_na_proveniencia_conta_como_posicao_conferida() -> None:
    """O revisor que decidiu marca a proveniência, e não o nó (importador e decisões)."""
    lida = RecognitionResult(fen=f"{KINGS} b - - 0 1", path=RecognitionPath.NEURAL,
                             overall_confidence=0.9, side_to_move_source="default")
    sem_revisao = Diagram(fen=f"{KINGS} b - - 0 1", recognition=lida)
    revisado = Diagram(fen=f"{KINGS} b - - 0 1", recognition=lida,
                       provenance=Provenance(verified_by_human=True))
    assert "lado a jogar desconhecido" in diagram_alt_text(sem_revisao)
    assert "jogam as pretas" in diagram_alt_text(revisado)


def test_o_alt_vai_no_idioma_do_livro(tmp_path: Path) -> None:
    documento = Document(body=(Diagram(fen=f"{KINGS} w - - 0 1"),))
    documento = Document(metadata=documento.metadata.__class__(language="en"),
                         body=documento.body)
    html = _html(tmp_path, documento)
    assert 'aria-label="Chess diagram, White to move. Black king on e8; White king on e1."' in html


# ---------------------------------------------------------------------- item 4: a partida


def test_a_coluna_do_livro_sai_sem_cabecalho_e_na_notacao_impressa() -> None:
    com_figurina = Paragraph(content=(
        Text(content="1."), PieceGlyph(piece=PieceType.KNIGHT, figurine_set=FigurineSet.WHITE),
        Text(content="f3 d5")))
    opcoes = render_do_livro(com_figurina, "en")
    assert opcoes.show_headers is False
    assert opcoes.render is MoveRenderStyle.FIGURINE
    assert opcoes.figurine_set is FigurineSet.WHITE
    em_letras = render_do_livro(Paragraph(content=(Text(content="1.Cf3 d5"),)), "pt")
    assert (em_letras.show_headers, em_letras.render, em_letras.language) == (
        False, MoveRenderStyle.LETTERS, "pt")


def test_o_cabecalho_nunca_imprime_interrogacao_nem_asterisco(tmp_path: Path) -> None:
    anonima = game_from_pgn("1. e4 e5 2. Nf3 *\n")
    assert anonima.render.show_headers is True
    html = _html(tmp_path, Document(body=(anonima,)))
    assert '<p class="headers">' not in html
    assert "? &#8211; ?" not in html
    assert "&#183; *" not in html
    relida = next(b for b in read_html_text(html).body if type(b).__name__ == "GameScore")
    assert relida.render.show_headers is True, "o data-headers guarda o cabeçalho ligado"

    meia = game_from_pgn('[White "Carlsen"]\n[Black "?"]\n[Result "1-0"]\n\n1. e4 1-0\n')
    html = _html(tmp_path, Document(body=(meia,)))
    cabecalho = re.search(r'<p class="headers">(.*?)</p>', html).group(1)
    assert cabecalho == "Carlsen &#8211; &#183; 1-0"


# ---------------------------------------------------------------------- item 5: a Merida


def test_o_epub_so_de_diagramas_nao_embute_fonte(tmp_path: Path) -> None:
    arquivos = _epub(tmp_path, Document(body=(Diagram(fen=f"{KINGS} w - - 0 1"),)))
    assert not [n for n in arquivos if "/Fonts/" in n or n.endswith("fonts.css")]
    assert not any("@font-face" in texto for texto in arquivos.values())


# ---------------------------------------------------------------------- item 6: as cores


def test_o_svg_embutido_segue_a_cor_do_texto_do_leitor(tmp_path: Path) -> None:
    arquivos = _epub(tmp_path, Document(body=(Diagram(fen=f"{KINGS} w - - 0 1"),)))
    capitulo = next(t for n, t in arquivos.items() if n.endswith(".xhtml") and "<svg" in t)
    svg = capitulo[capitulo.index("<svg"):capitulo.index("</svg>")]
    assert "currentColor" in svg
    assert not re.search(r'<rect x="0" y="0" [^>]*fill="#', svg), "sem o fundo pintado"


def test_o_pdf_e_o_docx_continuam_com_o_fundo_do_papel() -> None:
    contexto = ExportContext(HTML_PROFILE, Document(), ExportOptions())
    svg = DiagramRenderer(contexto).svg(Diagram(fen=f"{KINGS} w - - 0 1")).svg
    assert "currentColor" not in svg
    assert re.search(r'<rect x="0" y="0" [^>]*fill="#FFFFFF"', svg)


# ---------------------------------------------------------------------- item 7: a figurina


def test_a_figurina_do_pdf_fica_com_a_pilha_das_figurinas(tmp_path: Path) -> None:
    assert f".piece {{ font-family: {PILHA_DE_FIGURINAS}; }}" in BASE_CSS
    paragrafo = Paragraph(content=(
        Text(content="1."), PieceGlyph(piece=PieceType.KNIGHT, font_family="FigurineCBTimes"),
        Text(content="f3")))
    html = _html(tmp_path, Document(body=(paragrafo,)))
    classe = re.search(r'<span class="piece[^"]*\b(d\d+)\b', html).group(1)
    regra = re.search(rf"\.{classe} \{{([^}}]*)\}}", html).group(1)
    assert "FigurineCBTimes" not in regra
    assert PILHA_DE_FIGURINAS in regra
    assert 'data-font-family="FigurineCBTimes"' in html, "o valor do IR viaja para a volta"


# ---------------------------------------------------------------------- item 8: o perfil


def test_o_perfil_nao_declara_perdido_o_que_o_html_escreve(tmp_path: Path) -> None:
    for perfil in (HTML_PROFILE, EPUB_PROFILE):
        for campo in ("diagram.verified_by_human", "diagram.move_context"):
            assert perfil.node_fields[campo].capability is Capability.FULL, (perfil.name, campo)
    destino = tmp_path / "livro.html"
    resultado = export(Document(body=(Diagram(fen=f"{KINGS} w - - 0 1",
                                              verified_by_human=True),)),
                       destino, "html", options=ExportOptions(embed_ir=False))
    assert not [w for w in resultado.degradation.warnings if "verified" in w.property]


# ---------------------------------------------------------------------- item 9: a numeração


def test_a_numeracao_automatica_segue_o_numero_impresso() -> None:
    diagramas = (Diagram(fen=KINGS), Diagram(fen=KINGS, number=12), Diagram(fen=KINGS),
                 Diagram(fen=KINGS, label="Diagrama 13a"), Diagram(fen=KINGS))
    numeros = numeros_de_diagrama(Document(body=diagramas))
    assert [numeros.get(str(d.id)) for d in diagramas] == [1, None, 13, None, 14]
    desligada = Document(settings=DocumentSettings(auto_number_diagrams=False), body=diagramas)
    assert numeros_de_diagrama(desligada) == {}


def test_a_numeracao_recomeca_no_capitulo_quando_pedida() -> None:
    corpo = (Heading(level=1, content=(Text(content="I"),)), Diagram(fen=KINGS),
             Diagram(fen=KINGS), Heading(level=1, content=(Text(content="II"),)),
             Diagram(fen=KINGS))
    por_capitulo = Document(settings=DocumentSettings(number_diagrams_per_chapter=True,
                                                      diagram_numbering_start=1), body=corpo)
    numeros = numeros_de_diagrama(por_capitulo)
    assert [numeros[str(b.id)] for b in corpo if isinstance(b, Diagram)] == [1, 2, 1]


def test_a_legenda_leva_o_numero_automatico_sem_o_congelar(tmp_path: Path) -> None:
    html = _html(tmp_path, Document(body=(Diagram(fen=f"{KINGS} w - - 0 1"),
                                          Diagram(fen=f"{KINGS} b - - 0 1"))))
    assert html.count('<span class="label">Diagrama 1</span>') == 1
    assert html.count('<span class="label">Diagrama 2</span>') == 1
    assert "data-number" not in html
