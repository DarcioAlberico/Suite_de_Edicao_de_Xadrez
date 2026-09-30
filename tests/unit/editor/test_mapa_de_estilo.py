"""O mapa de estilo (spec S3b) contra as fixtures do H3: `tests/fixtures/editor/css/`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.editor.css.mapa_de_estilo import resolver

CSS = Path(__file__).resolve().parents[2] / "fixtures" / "editor" / "css"
FIXTURES = sorted([*CSS.glob("mapa_positivo/*.css"), *CSS.glob("mapa_negativo/*.css")])


@pytest.mark.parametrize("folha", FIXTURES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_a_fixture_do_h3(folha: Path) -> None:
    esperado = json.loads(folha.with_suffix(".json").read_text(encoding="utf-8"))
    obtido = resolver([(folha.name, folha.read_text(encoding="utf-8"))]).como_dict()
    assert obtido == esperado


def test_ha_fixtures() -> None:
    assert len(FIXTURES) == 48


def test_as_folhas_valem_na_ordem_da_espinha() -> None:
    mapa = resolver([("a.css", ".x { color: red; }\n"), ("b.css", ".x { color: blue; }\n")])
    assert mapa.estilos["p.x"] == {"color": "#0000ff"}
    mapa = resolver([("b.css", ".x { color: blue; }\n"), ("a.css", ".x { color: red; }\n")])
    assert mapa.estilos["p.x"] == {"color": "#ff0000"}


def test_a_variavel_de_uma_folha_vale_na_seguinte() -> None:
    mapa = resolver([("tema.css", ":root { --tinta: #333; }\n"),
                     ("livro.css", "h1 { color: var(--tinta); }\n")])
    assert mapa.estilos == {"h1": {"color": "#333333"}}


def test_seletores_na_mesma_regra_sao_julgados_um_a_um() -> None:
    mapa = resolver([("x.css", ".a, div p, h2 { color: red; }\n")])
    assert set(mapa.estilos) == {"p.a", "span.a", "h2"}
    assert [(a.seletor, a.propriedade) for a in mapa.avisos] == [("div p", "")]
