"""A ida IR → XHTML legível → IR (Editor HTML/CSS, passo H5): só as normalizações N1–N4.

O portão inteiro (10 mil nós e o IR real) é o `benchmarks/editor_ida_e_volta.py`; aqui, o corpus
pequeno e cada forma que a ida precisou dizer (o contrato, §12).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from caissa.core.model import (
    Diagram,
    Document,
    GameHeaders,
    GameRenderOptions,
    GameScore,
    MoveNode,
    Paragraph,
    ParagraphProps,
    PgnTag,
    Provenance,
    RawInline,
    RawPassthrough,
    RunProps,
    SourceKind,
    Span,
    Table,
    TableCell,
    TableRow,
    Text,
    semantic_diff,
)
from caissa.core.model.props import Alignment
from caissa.editor.leitura import mapa_de_json, mapa_para_json, nomes_de_estilo
from caissa.export.legivel import (
    CLASSE_LITERAL,
    Capitulo,
    canon,
    escrever_capitulo,
    forma_normal,
    ler_capitulo,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "model"))
from generators import NodeFactory

KINGS = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def _ida(documento: Document) -> tuple[list[object], Document]:
    """A ida pelo arquivo e pelo `proveniencia.json`: as diferenças fora da forma normal."""
    escrito, escritor = escrever_capitulo(Capitulo(blocos=documento.body, titulo="t"), documento)
    mapa = mapa_de_json(json.loads(json.dumps(mapa_para_json(escritor.mapa))))
    relido = ler_capitulo(escrito, mapa=mapa, estilos=nomes_de_estilo(documento))
    normal, _ = forma_normal(documento.body)
    antes = Document(metadata=documento.metadata, body=normal)
    depois = Document(metadata=documento.metadata, body=relido.blocos)
    return list(semantic_diff(antes, depois, ignore_ids=True).entries), depois


@pytest.mark.parametrize("semente", [7, 11, 42])
def test_a_ida_fecha_no_corpus_sintetico(semente: int) -> None:
    documento = NodeFactory(semente).document(min_nodes=400)
    diferencas, _ = _ida(documento)
    assert diferencas == []


def test_a_forma_normal_conta_cada_normalizacao() -> None:
    ocr = Provenance(kind=SourceKind.OCR, page_index=4)
    documento = Document(body=(
        Paragraph(provenance=ocr, props=ParagraphProps(alignment=Alignment.CENTER),
                  content=(Text(content="a", props=RunProps(font_family="Serif")),
                           Text(content="b"),
                           Span(provenance=ocr, content=(Text(content="c"),)))),))
    normal, contagem = forma_normal(documento.body)
    paragrafo = normal[0]
    assert paragrafo.props == ParagraphProps()
    assert [t.content for t in paragrafo.content] == ["abc"], "texto solto vizinho vira um só"
    classes = {chave.split(":")[0] for chave in contagem}
    assert classes == {"N1", "N2", "N3", "N4"}
    assert contagem["N1:text.props"] == 1
    assert contagem["N3:span"] == 1
    diferencas, _ = _ida(documento)
    assert diferencas == []


def _partida(*filhos: MoveNode, **kw: object) -> GameScore:
    return GameScore(children=filhos, **kw)  # type: ignore[arg-type]


def test_o_lance_que_nao_se_joga_vai_na_forma_literal_e_a_variante_dele_na_do_contrato() -> None:
    inicio = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    literal = MoveNode(san="Nc6", ply=1, position_before=inicio)
    jogavel = MoveNode(san="e4", ply=1, position_before=inicio,
                       position_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    documento = Document(body=(_partida(literal, jogavel),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert 'data-san="Nc6"' in escrito
    assert 'data-ply="1"' in escrito
    assert 'data-variation-start' not in escrito, "a variante do contrato se acha pela FEN"
    assert "data-uci" not in escrito, "o IR não tinha o uci: o contrato não o inventa"
    # O `validate.py` do CB acha o lance por `\bcb-move\b` num span (MARKUP §10): a forma literal
    # não casa com a expressão, e todo span que casa carrega a posição.
    assert re.search(rf'<span class="[^"]*\b{CLASSE_LITERAL}\b[^"]*" data-san="Nc6"', escrito)
    lances = re.findall(r'<span\b[^>]*\bclass="[^"]*\bcb-move\b[^"]*"[^>]*>', escrito)
    assert lances, "o lance jogável é um cb-move"
    assert all("data-fen=" in lance for lance in lances), "o CB pularia o lance sem data-fen"
    diferencas, depois = _ida(documento)
    assert diferencas == []
    partida = depois.body[0]
    assert [f.san for f in partida.children] == ["Nc6", "e4"]


def test_a_variante_literal_depois_de_um_comentario_diz_onde_comeca() -> None:
    a = MoveNode(san="Zz1", ply=1, comment_after="fim da linha")
    b = MoveNode(san="Zz2", ply=1)
    principal = MoveNode(san="Zz0", ply=1, children=())
    documento = Document(body=(_partida(principal, a, b),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert escrito.count('data-variation-start="1"') == 2
    diferencas, depois = _ida(documento)
    assert diferencas == []
    assert [f.san for f in depois.body[0].children] == ["Zz0", "Zz1", "Zz2"]


def test_o_comentario_antes_do_lance_fica_antes_dele() -> None:
    inicio = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    depois_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    e5 = MoveNode(san="e5", ply=2, position_before=depois_e4, comment_before="a simétrica",
                  position_after="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    e4 = MoveNode(san="e4", ply=1, position_before=inicio, position_after=depois_e4,
                  children=(e5,))
    documento = Document(body=(_partida(e4, initial_comment="antes de tudo"),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert '<p class="cb-comment" data-attach="before">a simétrica</p>' in escrito
    diferencas, depois = _ida(documento)
    assert diferencas == []
    assert depois.body[0].children[0].children[0].comment_before == "a simétrica"


def test_o_cabecalho_oculto_e_a_ordem_das_etiquetas_voltam() -> None:
    cabecalho = GameHeaders(white="Tal", black="Botvinnik", result="1-0",
                            extra=(PgnTag(name="Annotator", value="X"),
                                   PgnTag(name="ECO", value="B90")))
    documento = Document(body=(_partida(headers=cabecalho,
                                        render=GameRenderOptions(show_headers=False)),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert 'hidden="hidden"' in escrito
    assert 'data-tag-order="Annotator ECO"' in escrito
    diferencas, depois = _ida(documento)
    assert diferencas == []
    assert [t.name for t in depois.body[0].headers.extra] == ["Annotator", "ECO"]


@pytest.mark.parametrize(("rotulo", "numero", "no_texto", "atributos"), [
    (None, 12, "Diagrama 12", []),
    ("Diagrama 5", 5, "Diagrama 5", ['data-literal="1"', 'data-number="5"']),
    ("Diagrama 3", None, "Diagrama 3", ['data-literal="1"']),
    ("Figura A", 7, "Figura A", ['data-number="7"']),
])
def test_o_rotulo_e_o_numero_do_diagrama(rotulo: str | None, numero: int | None, no_texto: str,
                                         atributos: list[str]) -> None:
    documento = Document(body=(Diagram(fen=KINGS, label=rotulo, number=numero),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert f">{no_texto}</span>" in escrito
    for atributo in atributos:
        assert atributo in escrito
    if not atributos:
        assert "data-number" not in escrito
        assert "data-literal" not in escrito
    diferencas, _ = _ida(documento)
    assert diferencas == []


def test_o_atributo_preservado_que_colide_com_o_do_contrato_e_recusado() -> None:
    texto = Text(content="x", props=RunProps(language="de"), html_attributes=(("lang", "en"),))
    documento = Document(body=(Paragraph(content=(texto,)),))
    with pytest.raises(ValueError, match="colide"):
        escrever_capitulo(Capitulo(blocos=documento.body), documento)


def test_o_bruto_vai_como_esta_so_quando_volta_bruto() -> None:
    documento = Document(body=(
        RawPassthrough(format="xhtml", text="<address>Rua X</address>"),
        RawPassthrough(format="xhtml", text="<p>isto seria um parágrafo</p>"),
        Paragraph(content=(RawInline(format="xhtml", text="<kbd>Ctrl</kbd>"),
                           RawInline(format="latex", text=r"\kern1pt"))),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert "<address>Rua X</address>" in escrito
    assert '<pre class="cb-raw" data-format="xhtml">&lt;p&gt;' in escrito
    assert '<span class="cb-raw" data-format="latex">\\kern1pt</span>' in escrito
    diferencas, _ = _ida(documento)
    assert diferencas == []


def test_a_celula_de_cabecalho_e_a_do_corpo_pelo_proprio_elemento() -> None:
    def celula(texto: str, *, cabeca: bool = False) -> TableCell:
        return TableCell(content=(Paragraph(content=(Text(content=texto),)),), is_header=cabeca)

    tabela = Table(rows=(TableRow(cells=(celula("a", cabeca=True), celula("b"))),
                         TableRow(cells=(celula("c", cabeca=True), celula("d")))),
                   header_row_count=1, repeat_header=False, number=3)
    documento = Document(body=(tabela,))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert "<thead>\n<tr><th>a</th><td>b</td></tr>" in escrito
    assert 'data-repeat-header="0"' in escrito
    assert 'data-number="3"' in escrito
    diferencas, _ = _ida(documento)
    assert diferencas == []


def test_a_volta_do_que_a_ida_escreveu_fecha() -> None:
    """O arquivo que a ida escreve também é um arquivo do projeto: a volta vale nele."""
    documento = NodeFactory(5).document(min_nodes=400)
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body, titulo="t"), documento)
    relido = ler_capitulo(escrito, estilos=nomes_de_estilo(documento))
    de_novo, _ = escrever_capitulo(relido, documento)
    assert canon(de_novo) == canon(escrito)
