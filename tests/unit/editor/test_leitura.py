"""A leitura do projeto do editor (Editor HTML/CSS, passo H5): `caissa.editor.leitura`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.core.model import (
    Diagram,
    DiagramSource,
    Document,
    Heading,
    Paragraph,
    ParagraphProps,
    Provenance,
    RecognitionResult,
    RunProps,
    SourceKind,
    Text,
)
from caissa.core.model.styles import ParagraphStyle, StyleSheet
from caissa.editor.leitura import (
    FORMATO_DO_MAPA,
    e_legado,
    ler_legivel,
    mapa_de_json,
    mapa_para_json,
    nomes_de_estilo,
)
from caissa.export.legivel import Capitulo, escrever_capitulo

CONTRATO = Path(__file__).resolve().parents[2] / "fixtures" / "editor" / "contrato"
KINGS = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def _documento() -> Document:
    ocr = Provenance(kind=SourceKind.OCR, page_index=54, confidence=0.91)
    return Document(body=(
        Heading(level=2, anchor="cap-2", content=(Text(content="Finais"),), provenance=ocr),
        Paragraph(content=(Text(content="Texto."),), provenance=ocr),
        Diagram(fen=KINGS, number=3, provenance=ocr, verified_by_human=True,
                source=DiagramSource(kind=SourceKind.VISION, page_index=54, dpi=300.0),
                recognition=RecognitionResult(fen=KINGS, overall_confidence=0.97)),
    ))


def test_o_mapa_vai_ao_json_no_formato_2_e_volta_igual() -> None:
    documento = _documento()
    escrito, escritor = escrever_capitulo(Capitulo(blocos=documento.body), documento,
                                          folios={55: "54"})
    dados = json.loads(json.dumps(mapa_para_json(escritor.mapa)))
    assert dados["formato"] == FORMATO_DO_MAPA
    assert dados["folios"] == {"55": "54"}
    assert set(dados["blocos"]) == {"cap-2", "p55-1"}
    assert set(dados["diagramas"]) == {"p55-d1"}
    assert dados["blocos"]["cap-2"]["origem"] == "ancora"
    assert dados["diagramas"]["p55-d1"]["conferido"] is True
    assert mapa_de_json(dados) == escritor.mapa
    relido = ler_legivel(escrito, mapa=mapa_de_json(dados))
    titulo, paragrafo, diagrama = relido.blocos
    assert (titulo.id, titulo.anchor, titulo.provenance) == (
        documento.body[0].id, "cap-2", documento.body[0].provenance)
    assert paragrafo.id == documento.body[1].id
    assert diagrama.recognition == documento.body[2].recognition
    assert diagrama.source == documento.body[2].source
    assert diagrama.verified_by_human is True


def test_o_mapa_de_outro_formato_e_recusado() -> None:
    with pytest.raises(ValueError, match="formato"):
        mapa_de_json({"formato": 1, "blocos": {}})


def test_o_legado_do_perfil_de_maquina_continua_lido() -> None:
    texto = (CONTRATO / "legado_xhtml_builder.xhtml").read_text(encoding="utf-8")
    assert e_legado(texto)
    capitulo = ler_legivel(texto)
    assert capitulo.blocos, "o leitor de máquina devolve os blocos"
    assert all(type(b).__name__ != "RawPassthrough" for b in capitulo.blocos)


def test_o_arquivo_legivel_nao_e_legado() -> None:
    texto = (CONTRATO / "paragrafo.xhtml").read_text(encoding="utf-8")
    assert not e_legado(texto)
    assert isinstance(ler_legivel(texto).blocos[0], Paragraph)


def test_os_nomes_de_estilo_vem_da_folha_e_dos_nos() -> None:
    documento = Document(
        styles=StyleSheet(paragraph_styles=(ParagraphStyle(name="Citação longa"),)),
        body=(Paragraph(content=(Text(content="x", props=RunProps(style="Lance")),),
                        props=ParagraphProps(style="Corpo")),))
    assert nomes_de_estilo(documento) == ("Citação longa", "Corpo", "Lance")
