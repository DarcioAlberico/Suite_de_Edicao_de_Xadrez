"""O esquema v2 do IR: `IRNode.html_attributes` (Editor HTML/CSS, passo H5; spec S3, R2.3)."""

from __future__ import annotations

import json

import pytest
from generators import NodeFactory

from caissa.core.model import (
    CURRENT_SCHEMA_VERSION,
    Document,
    MigrationError,
    Paragraph,
    Text,
    document_to_payload,
    dumps,
    loads,
    rebaixar_para_v1,
    walk,
)
from caissa.core.model.serialize import document_from_payload


def _documento(atributos: tuple[tuple[str, str], ...] = ()) -> Document:
    return Document(body=(Paragraph(content=(Text(content="texto"),),
                                    html_attributes=atributos),))


def _carregar(texto: str) -> Document:
    carregado = loads(texto)
    return carregado[0] if isinstance(carregado, tuple) else carregado


def test_a_versao_corrente_e_a_2() -> None:
    assert CURRENT_SCHEMA_VERSION == 2
    assert json.loads(dumps(_documento()))["schema_version"] == 2


def test_os_atributos_vao_e_voltam_na_ordem() -> None:
    atributos = (("aria-describedby", "n1"), ("style", "color: red"), ("title", "t"))
    relido = _carregar(dumps(_documento(atributos)))
    assert relido.body[0].html_attributes == atributos


def test_o_vazio_nao_se_grava() -> None:
    assert "html_attributes" not in dumps(_documento())


def test_um_documento_v1_abre_na_v2() -> None:
    payload = document_to_payload(_documento())
    payload["schema_version"] = 1
    documento, aplicadas = document_from_payload(payload)
    assert len(aplicadas) == 1
    assert "html_attributes" in aplicadas[0]
    assert documento.body[0].html_attributes == ()


def test_o_caminho_de_volta_sem_atributos() -> None:
    payload = document_to_payload(_documento())
    v1 = rebaixar_para_v1(payload)
    assert v1["schema_version"] == 1
    assert "html_attributes" not in json.dumps(v1)
    documento, _ = document_from_payload(v1)
    assert documento.body[0].content[0].content == "texto"


def test_o_caminho_de_volta_recusa_a_perda() -> None:
    payload = document_to_payload(_documento((("style", "color: red"),)))
    with pytest.raises(MigrationError, match="atributos HTML preservados"):
        rebaixar_para_v1(payload)
    payload["schema_version"] = 1
    with pytest.raises(MigrationError, match="pede um documento v2"):
        rebaixar_para_v1(payload)


def test_o_corpus_sintetico_tem_atributos_e_os_devolve() -> None:
    """O `test_roundtrip_corpus` passa a exercer o campo: o corpus o gera, e a ida e volta o
    devolve igual."""
    documento = NodeFactory(7).document(min_nodes=2000)
    com = [n for _, n in walk(documento) if n.html_attributes]
    assert len(com) >= 10
    relido = _carregar(dumps(documento))
    assert [n.html_attributes for _, n in walk(relido) if n.html_attributes] == [
        n.html_attributes for n in com]
