"""O dado da máquina dos nós sem `id` no `proveniencia.json` (Editor HTML/CSS, H5, ciclo 2).

O XHTML legível não leva proveniência (R2.4). O bloco com `id` volta com a dele pelo mapa; o nó
sem `id` — o texto, o lance, a linha e a célula, o item, o bloco sem página, o diagrama sem `id`,
o `Span` que só carrega proveniência — fica guardado com o lugar dele, e `conferir_mapa` prova que
o lugar existe no IR relido. Nada se perde: a N3 da forma normal é exatamente o que o mapa guarda.
"""

from __future__ import annotations

import json
from dataclasses import replace

from caissa.core.model import (
    Diagram,
    DiagramSource,
    Document,
    GameScore,
    ListBlock,
    ListItem,
    MoveNode,
    Paragraph,
    Provenance,
    RecognitionResult,
    SourceKind,
    Span,
    Table,
    TableCell,
    TableRow,
    Text,
)
from caissa.core.model.ids import new_ulid
from caissa.editor.leitura import conferir_mapa, mapa_de_json, mapa_para_json
from caissa.export.legivel import (
    Capitulo,
    Duvida,
    RegistroDoMapa,
    escrever_capitulo,
    forma_normal,
    ler_capitulo,
)

INICIO = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
DEPOIS_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _prov(pagina: int | None, nota: str) -> Provenance:
    return Provenance(kind=SourceKind.OCR, page_index=pagina, note=nota, confidence=0.5)


def _documento() -> Document:
    celula = TableCell(content=(Paragraph(content=(
        Text(content="na célula", provenance=_prov(None, "texto da célula")),
        Span(provenance=_prov(9, "dúvida na célula"), content=(Text(content=" duvidosa"),)))),),
        provenance=_prov(None, "a célula"))
    return Document(body=(
        Paragraph(provenance=_prov(9, "o bloco"), content=(
            Text(content="Um texto "), Text(content="lido", provenance=_prov(9, "a palavra")),
            Span(provenance=_prov(9, "trecho duvidoso"), content=(Text(content=" talvez"),)))),
        Paragraph(content=(Text(content="Autoral com "),
                           Text(content="um trecho", provenance=_prov(9, "trecho sem dono")))),
        Paragraph(provenance=_prov(None, "do DOCX, sem página"),
                  content=(Text(content="Sem página."),)),
        Table(rows=(TableRow(cells=(celula,), provenance=_prov(None, "a linha")),)),
        ListBlock(items=(ListItem(content=(Paragraph(content=(Text(content="item"),)),),
                                  provenance=_prov(None, "o item")),)),
        Diagram(fen="4k3/8/8/8/8/8/8/4K3 w - - 0 1", verified_by_human=True,
                source=DiagramSource(kind=SourceKind.VISION, dpi=300.0),
                recognition=RecognitionResult(fen="4k3/8/8/8/8/8/8/4K3 w - - 0 1",
                                              overall_confidence=0.9)),
        GameScore(provenance=_prov(9, "a partida"), children=(
            MoveNode(san="e4", ply=1, position_before=INICIO, position_after=DEPOIS_E4,
                     provenance=_prov(9, "o lance")),)),
    ))


def _ida(documento: Document) -> tuple[Capitulo, object, dict]:
    escrito, escritor = escrever_capitulo(Capitulo(blocos=documento.body), documento,
                                          folios={10: "8"})
    dados = json.loads(json.dumps(mapa_para_json(escritor.mapa)))
    mapa = mapa_de_json(dados)
    return ler_capitulo(escrito, mapa=mapa), mapa, dados


def test_todo_dado_da_maquina_sem_id_fica_no_mapa_e_acha_o_lugar() -> None:
    documento = _documento()
    relido, mapa, _ = _ida(documento)
    assert conferir_mapa(relido, mapa) == []
    _, contagem = forma_normal(documento.body)
    n3 = sum(n for chave, n in contagem.items() if chave.startswith("N3:"))
    assert n3 > 0
    assert mapa.registros() == n3, "cada normalização N3 é um registro do mapa, e só"


def test_o_json_segue_a_s2() -> None:
    _, _, dados = _ida(_documento())
    bloco = dados["blocos"]["p10-1"]
    assert set(bloco) >= {"ir_id", "origem", "folio", "proveniencia", "duvidas", "revisao", "nos"}
    assert bloco["folio"] == "8"
    assert bloco["revisao"] == {"estado": "", "decisoes": []}
    assert [d["proveniencia"]["note"] for d in bloco["duvidas"]] == ["trecho duvidoso"]
    assert [(n["tipo"], n["campo"], n["ini"], n["fim"]) for n in bloco["nos"]] == [
        ("text", "content", 9, 13)]
    partida = dados["blocos"]["p10-g1"]
    assert [(n["tipo"], n["caminho"]) for n in partida["nos"]] == [("move_node",
                                                                   [["children", 0]])]
    capitulo = {(n["tipo"], n["proveniencia"]["note"] if n["proveniencia"] else None)
                for n in dados["capitulo"]["nos"]}
    assert ("text", "trecho sem dono") in capitulo
    assert ("paragraph", "do DOCX, sem página") in capitulo
    assert ("table_row", "a linha") in capitulo
    assert ("table_cell", "a célula") in capitulo
    assert ("list_item", "o item") in capitulo
    assert ("diagram", None) in capitulo, "o diagrama sem id guarda o reconhecimento"
    duvida = next(n for n in dados["capitulo"]["nos"] if n.get("duvida"))
    assert duvida["tipo"] == "span"


def test_o_json_devolve_o_mapa_inteiro() -> None:
    documento = _documento()
    _, escritor = escrever_capitulo(Capitulo(blocos=documento.body), documento,
                                    folios={10: "8"})
    mapa = escritor.mapa
    bloco = mapa.nos["p10-1"]
    mapa.nos["p10-1"] = replace(bloco, duvidas=tuple(
        replace(d, alternativas=("talvez", "tal vez")) for d in bloco.duvidas))
    mapa.nos["p10-d1"] = RegistroDoMapa(
        ir_id=new_ulid(), origem="pagina", proveniencia=_prov(9, "o diagrama"),
        fonte=DiagramSource(kind=SourceKind.VISION, page_index=9),
        reconhecimento=RecognitionResult(fen=INICIO), conferido=True,
        duvidas=(Duvida(ini=0, fim=4, proveniencia=_prov(9, "a legenda"), texto_sha="0" * 64),))
    assert mapa_de_json(json.loads(json.dumps(mapa_para_json(mapa)))) == mapa


def test_o_trecho_editado_nao_acha_mais_o_lugar() -> None:
    documento = _documento()
    escrito, escritor = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    editado = escrito.replace("Um texto lido", "Um texto relido", 1)
    relido = ler_capitulo(editado, mapa=escritor.mapa)
    problemas = conferir_mapa(relido, escritor.mapa)
    assert any("o trecho não é mais o mesmo" in p for p in problemas)
    assert any("a dúvida" in p for p in problemas)
