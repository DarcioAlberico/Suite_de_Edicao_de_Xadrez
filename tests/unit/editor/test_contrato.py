"""O instrumento do H3 (`benchmarks/editor_contrato.py`) reprova o que tem de reprovar."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "benchmarks"))

import editor_contrato as contrato  # noqa: E402


def _folha(pasta: Path, nome: str, css: str, esperado: dict | None) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.css").write_text(css, encoding="utf-8")
    if esperado is not None:
        (pasta / f"{nome}.json").write_text(json.dumps(esperado), encoding="utf-8")


def _aviso(arquivo: str, troca: dict | None = None) -> dict:
    aviso = {"codigo": "css-fora-do-mapa", "seletor": ".x", "propriedade": "float",
             "arquivo": arquivo, "linha": 1}
    aviso.update(troca or {})
    return aviso


@pytest.fixture
def css(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(contrato, "CSS", tmp_path)
    monkeypatch.setattr(contrato, "PROPRIEDADES_DO_MAPA", ("color",))
    _folha(tmp_path / "mapa_positivo", "cor", ".a { color: red; }\np.b { color: blue; }\n",
           {"estilos": {"p.a": {"color": "#ff0000"}, "p.b": {"color": "#0000ff"}}, "avisos": []})
    _folha(tmp_path / "mapa_negativo", "float", ".x { float: left; }\n",
           {"estilos": {}, "avisos": [_aviso("float.css")]})
    return tmp_path


def test_as_fixtures_de_verdade_passam() -> None:
    faltas, contagem = contrato.conferir_css()
    assert faltas == []
    assert contagem["positivas"] >= len(contrato.PROPRIEDADES_DO_MAPA)
    assert contrato.conferir_cobertura() == []


def test_o_conjunto_minimo_passa(css: Path) -> None:
    assert contrato.conferir_css() == ([], {"positivas": 1, "negativas": 1})


def test_fixture_sem_o_resultado_esperado_reprova(css: Path) -> None:
    _folha(css / "mapa_negativo", "orfa", ".y { position: absolute; }\n", None)
    faltas, _ = contrato.conferir_css()
    assert faltas == ["mapa_negativo/orfa.css sem o resultado esperado (.json)"]


def test_positiva_com_aviso_e_negativa_sem_aviso_reprovam(css: Path) -> None:
    _folha(css / "mapa_positivo", "suja", ".z { color: red; }\n",
           {"estilos": {}, "avisos": [_aviso("suja.css")]})
    _folha(css / "mapa_negativo", "muda", ".w { float: left; }\n", {"estilos": {}, "avisos": []})
    faltas, _ = contrato.conferir_css()
    assert "mapa_positivo/suja.css: a positiva declara aviso" in faltas
    assert "mapa_negativo/muda.css: a negativa não declara aviso" in faltas


@pytest.mark.parametrize("troca", [{"codigo": "outro"}, {"arquivo": "outra.css"}, {"linha": 0},
                                   {"linha": True}, {"seletor": ""}])
def test_aviso_fora_da_forma_reprova(css: Path, troca: dict) -> None:
    _folha(css / "mapa_negativo", "torto", ".t { float: left; }\n",
           {"estilos": {}, "avisos": [_aviso("torto.css", troca)]})
    faltas, _ = contrato.conferir_css()
    assert faltas == ["mapa_negativo/torto.json: aviso fora da forma do §9"]


def test_propriedade_com_um_valor_so_reprova(css: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(contrato, "PROPRIEDADES_DO_MAPA", ("color", "widows"))
    faltas, _ = contrato.conferir_css()
    assert faltas == ["a propriedade widows do mapa tem 0 valor(es) nas positivas (mínimo 2)"]


def test_a_sabotagem_poe_a_negativa_no_cb() -> None:
    limpas = [contrato.CONTRATO / nome for nome in contrato.LINHAS_DO_S4.values()]
    assert contrato.validar_no_cb(limpas)["error_count"] == 0
    sujas = [*limpas, contrato.NEGATIVAS / "negativa_sem_fen.xhtml"]
    relatorio = contrato.validar_no_cb(sujas)
    assert [i["message"] for i in relatorio["issues"] if i["severity"] == "error"] == [
        "Diagram has no data-fen"]
