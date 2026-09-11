"""A prancha `papel × estado` **desenha** o que os rótulos dela prometem (F9-C3).

**Por que isto é um teste e não uma conferência a olho.** A prancha mentiu em dois ciclos
seguidos, e nas duas vezes a mentira era o rótulo: no ciclo 1 a célula rotulada "Com foco" saía
em repouso porque o `setFocus()` da linha seguinte era noutro widget; no ciclo 2 a coluna "sob o
ponteiro" saía **byte a byte igual** à de repouso -- ΔRGB máximo zero nas 8 imagens, nas 4
linhas, nas 2 peles -- enquanto o relatório afirmava por escrito o mecanismo (`WA_Hover`) que
teria evitado exatamente isso. Uma prova errada é pior que prova nenhuma, e uma prova que só um
humano ampliando o PNG consegue contestar volta a errar no ciclo seguinte.

Então o gerador publica `estados_celulas.json` -- onde cada célula está e quanto ela difere da
de repouso da mesma linha -- e estes testes **refazem a conta sobre o PNG gravado**. Um número
que só existe na memória de quem gerou não prova nada; este é conferível contra a imagem.

Os testes que precisam das imagens **pulam com o motivo** quando elas não foram geradas, porque
gerá-las precisa de PyQt6 e o venv desta suíte não o tem (ADR-0009). A aritmética de diferença é
pura e é afirmada sem imagem nenhuma.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.ui.audit import amostrario

PRANCHAS = Path(__file__).resolve().parents[3] / "benchmarks" / "reports" / "ui"

PAPEIS_DE_BOTAO = ("NEUTRO", "PRIMARIO", "DESTRUTIVO")
"""As três linhas cuja coluna `sob o ponteiro` **tem** de diferir do repouso.

O `campo` fica de fora, e a exclusão é medida e não conveniência: `ui/folha_de_estilo.py` declara
`:focus` e `:disabled` para os oito seletores de campo e **nenhum** `:hover`. Um campo de texto
que mudasse de cor sob o ponteiro seria a prancha inventando um estado que o produto não tem --
o mesmo defeito na direção contrária. `test_o_campo_declara_por_que_fica_em_zero` cobra a
declaração, para que essa isenção não vire um lugar onde se esconde um `hover` quebrado."""


def _manifesto() -> dict:
    caminho = PRANCHAS / amostrario.MANIFESTO
    if not caminho.is_file():
        pytest.skip(
            f"{caminho} não existe; gere com "
            "`<tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.amostrario --saida "
            "benchmarks/reports/ui --estados`"
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


def _imagem(nome: str):
    Image = pytest.importorskip("PIL.Image", reason="Pillow não instalada")
    caminho = PRANCHAS / nome
    if not caminho.is_file():
        pytest.skip(f"{caminho} não existe; gere as pranchas antes")
    return Image.open(caminho).convert("RGB")


def _pixels(imagem, celula: dict) -> list[tuple[int, int, int]]:
    recorte = imagem.crop(
        (
            celula["x"],
            celula["y"],
            celula["x"] + celula["largura"],
            celula["y"] + celula["altura"],
        )
    )
    return list(recorte.getdata())


# ------------------------------------------------------------------ a aritmética, sem imagem


class TestDiferencaMaxima:
    def test_duas_imagens_iguais_diferem_em_zero(self) -> None:
        a = [(10, 20, 30)] * 4
        assert amostrario.diferenca_maxima(a, list(a)) == 0

    def test_um_pixel_diferente_ja_conta(self) -> None:
        """É a afirmação que a prancha precisa fazer: *existe* pixel diferente."""
        a = [(10, 20, 30)] * 4
        b = [(10, 20, 30), (10, 20, 37), (10, 20, 30), (10, 20, 30)]
        assert amostrario.diferenca_maxima(a, b) == 7

    def test_e_o_maximo_e_nao_a_media(self) -> None:
        """Uma média diluiria a mudança de estado no fundo que não mudou -- ver o docstring."""
        a = [(0, 0, 0)] * 100
        b = [(0, 0, 0)] * 99 + [(0, 0, 200)]
        assert amostrario.diferenca_maxima(a, b) == 200

    def test_tamanhos_diferentes_sao_a_maior_diferenca_possivel(self) -> None:
        assert amostrario.diferenca_maxima([(0, 0, 0)], [(0, 0, 0)] * 2) == 255

    def test_a_coluna_de_hover_e_a_segunda_e_a_de_repouso_a_primeira(self) -> None:
        """Os dois nomes que o gerador e estes testes comparam saem da mesma tabela."""
        assert amostrario.REPOUSO == amostrario.ESTADOS[0]
        assert amostrario.SOB_O_PONTEIRO == amostrario.ESTADOS[1]


# ------------------------------------------------------------------- a prancha, sobre o PNG


class TestPranchaDeEstados:
    def test_as_oito_pranchas_estao_no_manifesto(self) -> None:
        """Duas peles × quatro alvos de foco. Uma a menos é uma prancha que não foi conferida."""
        assert sorted(_manifesto()["pranchas"]) == [
            f"estados_{pele}_foco{indice}.png" for pele in ("claro", "escuro") for indice in range(4)
        ]

    def test_o_hover_dos_tres_papeis_difere_do_repouso_nas_oito_pranchas(self) -> None:
        """**O item bloqueante nº 3 do ciclo 3**, cobrado sobre o pixel do PNG gravado.

        Não confia no número do manifesto: recorta as duas células da imagem e refaz a conta. Um
        gerador que passasse a publicar um delta inventado falharia aqui.
        """
        manifesto = _manifesto()
        for nome, celulas in manifesto["pranchas"].items():
            imagem = _imagem(nome)
            for papel in PAPEIS_DE_BOTAO:
                repouso = _celula(celulas, papel, amostrario.REPOUSO)
                hover = _celula(celulas, papel, amostrario.SOB_O_PONTEIRO)
                medido = amostrario.diferenca_maxima(
                    _pixels(imagem, hover), _pixels(imagem, repouso)
                )
                assert medido > 0, (
                    f"{nome}: a célula '{amostrario.SOB_O_PONTEIRO}' do papel {papel} é idêntica "
                    "à de repouso. É o defeito nº 8 do ciclo 1 e o bloqueante nº 3 do ciclo 3: "
                    "a prancha está afirmando um estado que a imagem não contém."
                )
                assert medido == hover["delta_rgb"], (
                    f"{nome}: o manifesto diz ΔRGB={hover['delta_rgb']} para {papel} e o PNG diz "
                    f"{medido}. O número publicado tem de sair da imagem gravada."
                )

    def test_todo_estado_com_rotulo_proprio_difere_do_repouso(self) -> None:
        """A regra geral, e é ela que apanha o próximo estado a apagar: rótulo bate com célula.

        **Duas isenções, e as duas são o desenho e não uma folga.** A primeira é o `campo` sob o
        ponteiro: a folha do produto não declara `:hover` para campo de texto, e a prancha diz
        isso por escrito (`test_o_campo_declara_por_que_fica_em_zero`). A segunda é `com foco`
        fora da linha em foco: o Qt tem **um** foco só, e é por isso que há quatro pranchas por
        pele em vez de uma -- em `foco0` só a linha 0 tem anel, e exigir anel nas outras seria
        exigir da imagem um estado que a janela nunca mostra.
        """
        linhas = [*PAPEIS_DE_BOTAO, "campo"]
        for nome, celulas in _manifesto()["pranchas"].items():
            em_foco = linhas[int(nome.split("foco")[1][0])]
            for celula in celulas:
                if celula["estado"] == amostrario.REPOUSO:
                    continue
                if celula["papel"] == "campo" and celula["estado"] == amostrario.SOB_O_PONTEIRO:
                    continue
                if celula["estado"] == "com foco" and celula["papel"] != em_foco:
                    assert celula["delta_rgb"] == 0, (
                        f"{nome}: a linha {celula['papel']} não é a que tem o foco e mesmo assim "
                        "difere do repouso -- ou a prancha ganhou dois anéis, ou o nome do "
                        "arquivo deixou de dizer qual linha está em foco."
                    )
                    continue
                assert celula["delta_rgb"] > 0, (
                    f"{nome}: a célula '{celula['estado']}' do papel {celula['papel']} é idêntica "
                    "à de repouso e ainda assim tem rótulo próprio."
                )

    def test_o_campo_declara_por_que_fica_em_zero(self) -> None:
        """A isenção só vale enquanto ela estiver escrita **na prancha**, e não só aqui.

        Sem isto, "o campo não tem hover" viraria uma linha de teste que autoriza a imagem a
        continuar dizendo "sob o ponteiro" sobre uma célula em repouso -- que é o defeito.
        """
        manifesto = _manifesto()
        nota = manifesto["nota_do_campo"]
        assert nota == amostrario.NOTA_DO_CAMPO
        assert "folha_de_estilo" in nota and ":hover" in nota
        for celulas in manifesto["pranchas"].values():
            campo = _celula(celulas, "campo", amostrario.SOB_O_PONTEIRO)
            assert campo["delta_rgb"] == 0, (
                "o campo passou a ter `hover`: tire a isenção de PAPEIS_DE_BOTAO e de "
                "`NOTA_DO_CAMPO` em vez de deixar a nota afirmando o contrário do produto."
            )


def _celula(celulas: list[dict], papel: str, estado: str) -> dict:
    for celula in celulas:
        if celula["papel"] == papel and celula["estado"] == estado:
            return celula
    raise AssertionError(f"a prancha não tem a célula ({papel}, {estado})")
