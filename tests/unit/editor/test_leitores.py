"""As partes puras da medição dos leitores (passo H0): casamento, ordem, métricas, intervalo.

A medição inteira roda os dois leitores e leva dezenas de minutos; ela é o portão do H0, pelo
executor. Aqui ficam as regras que decidem cada número, com casos feitos à mão: uma linha entra na
região com metade da área dentro, as linhas saem de cima para baixo, a figurina conta só com a
mesma peça, e a diferença é orientada para que positivo seja melhor para o leitor testado.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[3]


def _carregar() -> ModuleType:
    caminho = RAIZ / "benchmarks" / "editor_leitores.py"
    especificacao = importlib.util.spec_from_file_location("editor_leitores", caminho)
    assert especificacao is not None
    assert especificacao.loader is not None
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules["editor_leitores"] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


leitores = _carregar()


def _linha(texto: str, x0: float, y0: float, x1: float, y1: float) -> dict[str, object]:
    return {"texto": texto, "caixa": [x0, y0, x1, y1]}


def test_a_linha_entra_com_metade_da_area_dentro() -> None:
    regiao = (100.0, 100.0, 300.0, 200.0)
    assert leitores.dentro((100.0, 110.0, 200.0, 120.0), regiao)
    assert leitores.dentro((250.0, 110.0, 350.0, 120.0), regiao)       # metade exata
    assert not leitores.dentro((260.0, 110.0, 360.0, 120.0), regiao)   # 40 % dentro
    assert not leitores.dentro((100.0, 300.0, 200.0, 310.0), regiao)


def test_a_leitura_da_regiao_sai_de_cima_para_baixo_com_o_iou() -> None:
    regiao = (100.0, 100.0, 300.0, 160.0)
    linhas = [
        _linha("terceira", 100, 140, 300, 160),
        _linha("primeira", 100, 100, 300, 120),
        _linha("fora", 400, 100, 500, 120),
        _linha("segunda", 100, 120, 300, 140),
    ]
    texto, sobreposicao = leitores.leitura_da_regiao(linhas, regiao)
    assert texto == "primeira\nsegunda\nterceira"
    assert sobreposicao == pytest.approx(1.0)


def test_na_mesma_faixa_vale_a_esquerda_primeiro() -> None:
    linhas = [_linha("direita", 200, 100, 300, 112), _linha("esquerda", 100, 101, 190, 113)]
    assert [ln["texto"] for ln in leitores.em_ordem(linhas)] == ["esquerda", "direita"]


def test_regiao_sem_linhas_tem_iou_zero_e_texto_vazio() -> None:
    assert leitores.leitura_da_regiao([], (0.0, 0.0, 10.0, 10.0)) == ("", 0.0)


def test_figurina_so_conta_com_a_mesma_peca() -> None:
    verdade = "1.♘f3 d5 2.♗b5+ c6"
    lida = "1.♘f3 d5 2.♖b5+ c6"        # torre no lugar do bispo
    medida = leitores.medir_regiao(verdade, lida)
    assert medida["figurinas_verdade"] == 2
    assert medida["figurinas_certas"] == 1
    assert medida["lances_verdade"] == 4
    assert medida["lances_certos"] == 3
    assert medida["lances_inventados"] == 1


def test_leitura_vazia_paga_cer_um() -> None:
    assert leitores.medir_regiao("Um texto qualquer.", "")["cer"] == 1.0


def test_diferenca_orientada_positivo_e_melhor_para_a_testada() -> None:
    melhor = [{"cer": 0.1, "lances_verdade": 10, "lances_certos": 9, "lances_inventados": 0,
               "figurinas_verdade": 0, "figurinas_certas": 0} for _ in range(20)]
    pior = [{"cer": 0.3, "lances_verdade": 10, "lances_certos": 5, "lances_inventados": 3,
             "figurinas_verdade": 0, "figurinas_certas": 0} for _ in range(20)]
    sorteios = leitores.reamostras(20)
    for metrica in ("cer", "lances", "insercao"):
        d = leitores.diferenca(melhor, pior, metrica, sorteios)
        assert d is not None, metrica
        assert d["delta"] > 0, metrica
        assert d["ic95"][0] > 0, metrica
        d = leitores.diferenca(pior, melhor, metrica, sorteios)
        assert d is not None, metrica
        assert d["delta"] < 0, metrica
        assert d["ic95"][1] < 0, metrica
    assert leitores.diferenca(melhor, pior, "figurinas", sorteios) is None


def test_as_reamostras_sao_as_mesmas_em_toda_execucao() -> None:
    assert leitores.reamostras(7) == leitores.reamostras(7)
    assert len(leitores.reamostras(7)) == leitores.REAMOSTRAS


def test_o_denominador_reprova_verdade_insuficiente() -> None:
    poucas = [{"livro": "a", "estrato": "digitalizado"}] * 149
    poucas.append({"livro": "b", "estrato": "nativo"})
    leitores.verificar_denominador(poucas)                      # 150, 2 livros, 2 estratos
    with pytest.raises(leitores.VerdadeInsuficiente, match="verdade insuficiente"):
        leitores.verificar_denominador(poucas[:-1])             # 149, 1 livro, 1 estrato
    so_um_estrato = [{"livro": f"l{i % 2}", "estrato": "nativo"} for i in range(200)]
    with pytest.raises(leitores.VerdadeInsuficiente, match="estrato digitalizado"):
        leitores.verificar_denominador(so_um_estrato)


def test_a_pagina_lida_vira_linhas_e_diagramas() -> None:
    dados = {
        "cabecalho": {"texto": "Capítulo 3", "bbox": [50, 20, 200, 30]},
        "colunas": [{"blocos": [
            {"tipo": "texto", "linhas": [{"texto": "1.e4 e5", "bbox": [50, 100, 200, 112]},
                                         {"texto": "  ", "bbox": [50, 112, 200, 124]}]},
            {"tipo": "diagrama", "bbox": [50, 130, 250, 330], "placement": "8/8/8/8/8/8/8/K6k"},
            {"tipo": "tabela", "celulas": [["1", "Kasparov"], ["2", "Karpov"]],
             "bbox": [50, 340, 250, 380]},
        ]}],
        "rodape": None,
    }
    linhas, diagramas, blocos = leitores._linhas_da_pagina_lida(dados)
    assert [ln["texto"] for ln in linhas] == ["Capítulo 3", "1.e4 e5", "1\tKasparov\n2\tKarpov"]
    assert [ln["bloco"] for ln in linhas] == [0, 1, 2]
    assert [b["tipo"] for b in blocos] == ["cabecalho", "texto", "tabela"]
    assert diagramas == [{"caixa": [50, 130, 250, 330], "lido": True}]


def _regiao(ident: str, x0: float, y0: float, x1: float, y1: float) -> dict[str, object]:
    return {"id": ident, "caixa": [x0, y0, x1, y1]}


def test_a_ordem_verdadeira_de_duas_colunas_com_titulo() -> None:
    """A página do SFC4: título no alto, atravessando as colunas; esquerda, depois direita."""
    regioes = [
        _regiao("direita-baixo", 223, 471, 408, 492),
        _regiao("titulo", 144, 27, 287, 35),
        _regiao("esquerda-baixo", 26, 451, 210, 604),
        _regiao("direita-alto", 223, 191, 408, 284),
        _regiao("esquerda-alto", 26, 250, 209, 414),
        _regiao("nota-na-esquerda", 152, 420, 171, 428),       # entre os dois da esquerda
    ]
    assert leitores.ordem_verdadeira(regioes) == [
        "titulo", "esquerda-alto", "nota-na-esquerda", "esquerda-baixo", "direita-alto",
        "direita-baixo"]


def test_a_ordem_verdadeira_de_uma_coluna_e_de_cima_para_baixo() -> None:
    regioes = [_regiao("c", 50, 300, 500, 400), _regiao("a", 50, 100, 500, 150),
               _regiao("b", 60, 160, 480, 290)]
    assert leitores.ordem_verdadeira(regioes) == ["a", "b", "c"]


def test_o_elemento_largo_separa_as_faixas() -> None:
    """Um diagrama de página inteira no meio: as colunas de cima, ele, as colunas de baixo."""
    regioes = [_regiao("esq-baixo", 30, 500, 200, 600), _regiao("dir-cima", 230, 50, 400, 150),
               _regiao("largo", 30, 300, 400, 450), _regiao("esq-cima", 30, 60, 200, 200),
               _regiao("dir-baixo", 230, 480, 400, 580)]
    assert leitores.ordem_verdadeira(regioes) == [
        "esq-cima", "dir-cima", "largo", "esq-baixo", "dir-baixo"]


def test_a_ordem_de_cada_leitor_pelas_suas_unidades() -> None:
    regioes = [_regiao("a", 30, 100, 200, 200), _regiao("b", 230, 100, 400, 200)]
    # A aba: a ordem das linhas; ela leu a coluna da direita primeiro.
    aba = {"linhas": [_linha("dir", 235, 110, 395, 120), _linha("esq", 35, 110, 195, 120)]}
    assert sorted(leitores.posicoes("glifo", aba, regioes),
                  key=lambda k: leitores.posicoes("glifo", aba, regioes)[k]) == ["b", "a"]
    # O produto: a ordem dos blocos do IR; um bloco que engole as duas regiões empata, e o
    # desempate é a posição de cada uma na página.
    produto = {"blocos": [{"ordem": 0, "caixa": [30, 100, 400, 200]}]}
    achadas = leitores.posicoes("fusao", produto, regioes)
    assert sorted(achadas, key=lambda k: achadas[k]) == ["a", "b"]
    assert leitores.precisao_de_regioes("fusao", produto, regioes) == (2, 0)


def test_nao_se_aplica_so_com_o_denominador_zero() -> None:
    sem_figurina = [{"fusao": {"figurinas_verdade": 0, "lances_verdade": 7}}] * 3
    declarado = leitores.nao_se_aplica(sem_figurina, "figurinas")
    assert declarado["valor_do_denominador"] == 0
    assert declarado["lances_na_verdade"] == 21
    assert "0 de 21 lances" in declarado["motivo"]
    assert leitores.nao_se_aplica(sem_figurina, "lances") is None
    assert leitores.nao_se_aplica(sem_figurina, "cer") is None
    com_figurina = [{"fusao": {"figurinas_verdade": 2, "lances_verdade": 7}}]
    assert leitores.nao_se_aplica(com_figurina, "figurinas") is None
    sem_lance = [{"fusao": {"figurinas_verdade": 0, "lances_verdade": 0}}] * 2
    assert "0 lances em 2 regiões" in leitores.nao_se_aplica(sem_lance, "insercao")["motivo"]


def test_a_geometria_pega_o_erro_de_unidade(tmp_path: Path) -> None:
    """A régua da fixture: linhas em pontos casam; as mesmas em pixels de 220 dpi, não."""
    import pymupdf

    verdades = leitores.pdf_da_geometria(tmp_path / "geometria.pdf")
    with pymupdf.open(tmp_path / "geometria.pdf") as documento:
        linhas = [{"texto": w[4], "caixa": list(w[:4])}
                  for w in documento[0].get_text("words")]
    escala = leitores.DPI_DA_ABA / 72.0
    em_pixels = [{"texto": ln["texto"], "caixa": [v * escala for v in ln["caixa"]]}
                 for ln in linhas]
    for verdade in verdades:
        assert leitores.leitura_da_regiao(linhas, verdade)[1] > 0.99
        # Palavras do outro parágrafo caem por acaso no retângulo (0,35 medido): bem abaixo
        # do mínimo, que é o que a fixture cobra.
        assert leitores.leitura_da_regiao(em_pixels, verdade)[1] < leitores.IOU_DA_GEOMETRIA / 2
