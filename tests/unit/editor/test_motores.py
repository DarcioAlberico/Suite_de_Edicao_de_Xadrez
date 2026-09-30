"""O instrumento dos motores de pré-visualização (`benchmarks/editor_motores.py`, passo H1).

As partes sem o Chromium: a extração dos casos da matriz de CSS, a família genérica da
`font-family`, o veredito por propriedade, a comparação de pixels, o laço de paginação do MuPDF e
o livro hostil montado com a porta e a sentinela.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "benchmarks"))
import editor_motores as motores


def test_extrai_um_caso_por_par_com_o_contexto_da_regra_e_o_pseudo() -> None:
    css = (":root { --tinta: #123; }\n"
           ".a { color: var(--tinta); margin: 0 }\n"
           ".b { color: var(--tinta); }\n"
           ".c::before { content: '§'; margin-right: .2em }\n"
           "@media print { .d { page-break-before: always } }\n"
           "@page { margin: 2cm }\n")
    casos, extras = motores.extrair_casos({"f": css})
    reais = {c.chave: c for c in casos if c.controle is None}
    # o tinycss2 serializa a cadeia com aspas duplas
    assert set(reais) == {"color: var(--tinta)", "margin: 0", 'content: "§"',
                          "margin-right: .2em", "page-break-before: always"}
    cor = reais["color: var(--tinta)"]
    assert cor.contexto == [("margin", "0")], "o resto da regra de onde o par veio"
    assert "--tinta: #123" in cor.variaveis
    assert reais['content: "§"'].pseudo == "::before"
    assert extras["nao_testado"] == {"@page": 1}
    assert [c.controle for c in casos if c.controle is not None] == [True, False]


def test_a_font_family_sem_a_declaracao_fica_com_a_generica_da_lista() -> None:
    assert motores.generica('Georgia, "Source Serif 4", serif', "") == "serif"
    assert motores.generica('"Source Sans 3", Helvetica, Arial, sans-serif', "") == "sans-serif"
    assert motores.generica("Palatino", "") == "serif"
    variaveis = ':root { --mono: "Cascadia Mono", Consolas, monospace }'
    assert motores.generica("var(--mono)", variaveis) == "monospace"
    caso = motores.Caso(propriedade="font-family", valor="Georgia, serif", contexto=[],
                        pseudo="", molde="bloco", variaveis="")
    assert "font-family: Georgia, serif" in caso.folha(com=True)
    assert re.search(r"#alvo \{ font-family: serif \}", caso.folha(com=False))


def _linha(valor: str, chromium: str, mupdf: str) -> dict:
    return {"valor": valor, "chromium": {"veredito": chromium}, "mupdf": {"veredito": mupdf}}


@pytest.mark.parametrize(("linhas", "esperado"), [
    ([_linha("a", "desenha", "desenha")], "desenha"),
    ([_linha("a", "desenha", "desenha"), _linha("b", "desenha", "nao_desenha")], "parcial"),
    ([_linha("a", "desenha", "nao_desenha")], "nao_desenha"),
    ([_linha("a", "nao_desenha", "nao_desenha")], "sem_efeito_aqui"),
    ([_linha("a", "desenha", "desenha"), _linha("b", "nao_desenha", "laco")], "laco"),
])
def test_o_veredito_do_mupdf_conta_so_o_que_o_chromium_desenha(linhas: list[dict],
                                                                esperado: str) -> None:
    assert motores.veredito_da_propriedade(linhas, "mupdf")["veredito"] == esperado


def test_os_pixels_mudados_pedem_diferenca_de_16_no_canal() -> None:
    largura, altura = 4, 2
    fundo = bytes([200, 200, 200]) * (largura * altura)
    quase = bytearray(fundo)
    quase[0] = 215  # 15 de diferença: não conta
    muda = bytearray(fundo)
    muda[3 * 5 + 1] = 100  # o pixel (1, 1)
    assert motores.pixels_mudados(fundo, bytes(quase), largura, altura, None) == 0
    assert motores.pixels_mudados(fundo, bytes(muda), largura, altura, None) == 1
    assert motores.pixels_mudados(fundo, bytes(muda), largura, altura, (0, 0, 0, 0)) == 1, (
        "a folga de 4 px alcança o vizinho")


def test_o_mupdf_entra_em_laco_com_a_quebra_antes_do_primeiro_elemento() -> None:
    """O achado do H1: a prévia pelo MuPDF precisa de teto de páginas (H13)."""
    corpo = motores.MOLDES["bloco"]
    raster = motores.render_mupdf(corpo, motores.FOLHA_DO_MOLDE
                                  + "#alvo { page-break-before: always }")
    assert raster.laco
    assert len(raster.paginas) == motores.MAXIMO_DE_PAGINAS
    assert not motores.render_mupdf(corpo, motores.FOLHA_DO_MOLDE).laco


def test_o_mupdf_nao_resolve_var() -> None:
    """O achado do H1: a cor por variável não chega ao MuPDF (o `BASE_CSS` usa variáveis)."""
    corpo = motores.MOLDES["bloco"]
    base = motores.render_mupdf(corpo, motores.FOLHA_DO_MOLDE)
    direta = motores.render_mupdf(corpo, motores.FOLHA_DO_MOLDE + "#alvo { color: #c00 }")
    variavel = motores.render_mupdf(corpo, motores.FOLHA_DO_MOLDE
                                    + ":root { --t: #c00 } #alvo { color: var(--t) }")
    assert direta.paginas != base.paginas
    assert variavel.paginas == base.paginas


def test_o_livro_hostil_leva_a_porta_e_a_sentinela(tmp_path: Path) -> None:
    livro, sentinela = motores.livro_hostil(tmp_path, 4321)
    assert sentinela.is_file()
    assert sentinela.parent == tmp_path
    textos = [p.read_text(encoding="utf-8") for p in livro.rglob("*")
              if p.suffix in (".xhtml", ".css", ".svg")]
    assert textos
    assert not any("{PORTA}" in t or "{FORA}" in t for t in textos)
    assert any("http://127.0.0.1:4321/" in t for t in textos)
    fora = (livro / "Text" / "09_arquivos_fora.xhtml").read_text(encoding="utf-8")
    assert sentinela.as_uri() in fora
    assert (livro / "Images" / "dentro.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(list((livro / "Text").glob("*.xhtml"))) == 9


def test_o_clique_acha_o_bloco_e_a_continuacao_na_pagina_seguinte() -> None:
    """A regra do clique: o retângulo que contém; a continuação acima do primeiro bloco da
    página (o MuPDF só dá o bloco que passa da página na primeira); a folga da primeira linha."""
    posicoes = [(0, "a", (36.0, 36.0, 384.0, 300.0)), (0, "b", (36.0, 310.0, 384.0, 700.0)),
                (1, "c", (36.0, 200.0, 384.0, 400.0))]
    assert motores.bloco_no_clique(posicoes, 0, 100, 100) == "a"
    assert motores.bloco_no_clique(posicoes, 0, 100, 400) == "b"
    assert motores.bloco_no_clique(posicoes, 1, 100, 100) == "b", "a continuação de b"
    assert motores.bloco_no_clique(posicoes, 1, 100, 300) == "c"
    assert motores.bloco_no_clique(posicoes, 1, 100, 404) == "c", "a folga de 6 pt"
    assert motores.bloco_no_clique(posicoes, 1, 100, 450) is None
    assert motores.bloco_no_clique(posicoes, 0, 100, 20) is None, "a cabeça do livro: nenhum"


def test_o_capitulo_cresce_por_blocos_e_conta_so_o_corpo() -> None:
    """O capítulo de 50 KB tem blocos (a cabeça da página, com o CSS e as fontes embutidas, não
    conta), e a edição põe um caractere no texto de um bloco, sem tocar nas etiquetas."""
    import random

    capitulos = motores.capitulos(None)
    for nome, alvo in motores.ALVOS_DOS_CAPITULOS.items():
        capitulo = capitulos[nome]
        assert capitulo.blocos, nome
        assert capitulo.kb * 1024 >= alvo
        assert capitulo.origem.startswith("o corpus sintético")
    capitulo = capitulos["50kb"]
    indice, novo = motores.editar(capitulo, random.Random(42))
    antigo = capitulo.blocos[indice]
    assert len(novo) == len(antigo) + 1
    assert re.sub(r"<[^>]*>", "", novo) != re.sub(r"<[^>]*>", "", antigo)
    assert re.findall(r"<[^>]*>", novo) == re.findall(r"<[^>]*>", antigo)


def test_a_cobertura_das_posicoes_cai_sem_os_ids() -> None:
    """A sabotagem `sem_ids`: sem o `id` nos blocos, o MuPDF não dá a posição de nenhum."""
    capitulo = motores.capitulos(None)["50kb"]
    com = motores.posicoes_no_mupdf(capitulo)
    sem = motores.posicoes_no_mupdf(capitulo, sem_ids=True)
    assert com["cobertura"] == 1.0
    assert sem["cobertura"] < 1.0
