"""O portão de contraste do SPEC §11.3, como teste. **WCAG AA em 100 % dos pares.**

Este arquivo é o portão, e não uma amostra dele: `contraste.medir` deriva os pares da folha de
estilo que embarca, da `QPalette` que a janela aplica, da tabela de marcações e do tabuleiro --
e o teste falha se **um** deles cair abaixo do piso. Um par novo entra sozinho quando alguém
acrescenta um componente à folha; ninguém precisa lembrar de escrever um teste para ele.

**Roda sem Qt**, que é a razão de a folha ter mudado de `qt/` para `ui/` na F9: o venv desta
suíte não tem binding nenhum, e um portão que só roda na máquina do frontend é um portão que a
CI não cobra.
"""

from __future__ import annotations

import pytest

from caissa.ui.audit import contraste

from .conftest import TRONCO


@pytest.fixture(scope="module")
def relatorio() -> dict:
    """Uma medição para o módulo inteiro: ela é pura e custa o mesmo em toda asserção."""
    return contraste.medir(caminho_do_tronco=TRONCO)


def test_nenhum_par_reprova_o_piso_wcag_aa(relatorio: dict) -> None:
    """O portão. A mensagem de falha traz o par inteiro, para não obrigar a abrir o JSON."""
    culpados = [
        f"{pele['nome']}: {par['razao']:.2f}:1 (piso {par['piso']:.1f}, {par['especie']}) "
        f"{par['frente']} sobre {par['fundo']} -- {par['onde']}"
        for pele in relatorio["peles"]
        for par in relatorio["reprovados"][pele["nome"]]
    ]
    assert culpados == [], "\n".join(["Pares abaixo do piso WCAG AA:", *culpados])


def test_as_duas_peles_sao_medidas_e_nenhuma_fica_de_fora(relatorio: dict) -> None:
    """Uma pele que sumisse do relatório passaria o portão por ausência, que é o pior modo."""
    assert {pele["nome"] for pele in relatorio["peles"]} == {"claro", "escuro"}
    for pele in relatorio["peles"]:
        assert pele["pares"] > 200, f"{pele['nome']} mediu só {pele['pares']} pares"
        assert pele["sob_portao"] > 150, f"{pele['nome']} tem só {pele['sob_portao']} sob portão"


def test_as_quatro_origens_de_par_estao_todas_representadas(relatorio: dict) -> None:
    """A folha, a paleta, as marcações e o tabuleiro.

    **É a asserção que impede o portão de encolher em silêncio.** Se um dia a derivação da
    `QPalette` parar de achar pares -- porque alguém renomeou um papel --, o total continua
    grande por causa da folha, e o portão continuaria verde medindo três quartos do produto.
    """
    for pele in relatorio["peles"]:
        for origem in ("folha", "paleta", "marcacao", "tabuleiro"):
            assert pele["por_origem"][origem] > 0, f"{pele['nome']} não mediu par de {origem}"


def test_o_texto_do_botao_com_enfase_passa_o_piso_tambem_sob_o_ponteiro(relatorio: dict) -> None:
    """O defeito que a F9 mediu: o realce andava **na direção da letra** e apagava o rótulo.

    `#ffffff` sobre a face primária clareada dava 4,47:1 sob o ponteiro e 3,09:1 pressionada --
    o botão mais importante da janela perdendo o piso AA no instante entre apontar e clicar.
    A asserção é sobre o par medido, e não sobre a fórmula: uma fórmula nova que produzisse o
    mesmo defeito falharia aqui igual.
    """
    for pele in relatorio["peles"]:
        alvos = [
            par
            for par in relatorio["todos_os_pares"][pele["nome"]]
            if par["especie"] == "texto" and "papel=" in par["onde"]
        ]
        assert alvos, f"{pele['nome']}: nenhum par de botão com ênfase foi medido"
        for par in alvos:
            if not par["portao"]:
                continue
            assert par["razao"] >= contraste.AA_TEXTO, (
                f"{pele['nome']}: {par['onde']} dá {par['razao']:.2f}:1"
            )


def test_a_selecao_se_distingue_do_fundo_em_que_ela_cai(relatorio: dict) -> None:
    """A linha selecionada tinha 1,63:1 contra o poço da lista -- uma seleção que mal se via.

    O piso é o gráfico (3,0), porque seleção é **estado de componente** pela WCAG 1.4.11, e o
    fundo é o poço e o painel: os dois lugares em que uma seleção persiste.
    """
    for pele in relatorio["peles"]:
        pares = [
            par
            for par in relatorio["todos_os_pares"][pele["nome"]]
            if par["onde"].startswith("QPalette.Active: Highlight sobre")
        ]
        assert len(pares) >= 2, f"{pele['nome']}: a seleção não foi medida contra os dois fundos"
        for par in pares:
            assert par["razao"] >= contraste.AA_GRAFICO, (
                f"{pele['nome']}: {par['onde']} dá {par['razao']:.2f}:1"
            )


def test_as_isencoes_sao_poucas_e_nomeadas(relatorio: dict) -> None:
    """Uma isenção sem motivo escrito é um portão furado.

    Todo par fora do portão tem de dizer por quê -- inativo, separador ou estado transitório --,
    e a proporção de isentos não pode passar de um terço: acima disso o portão estaria medindo
    menos do que declara.
    """
    for pele in relatorio["peles"]:
        isentos = [
            par for par in relatorio["todos_os_pares"][pele["nome"]] if not par["portao"]
        ]
        sem_motivo = [par["onde"] for par in isentos if not par["nota"]]
        assert sem_motivo == [], f"{pele['nome']}: isenção sem motivo em {sem_motivo}"
        assert len(isentos) < pele["pares"] / 3, (
            f"{pele['nome']}: {len(isentos)} de {pele['pares']} pares isentos"
        )


# ------------------------------------------------------------- a dica dentro do campo (C6)


def test_a_dica_do_campo_habilitado_passa_o_piso_aa_nas_duas_peles(relatorio: dict) -> None:
    """O bloqueante do ciclo 5, cobrado pelo lado do arnês.

    A dica renderizava a **3,96:1** na pele clara -- abaixo do piso AA -- e o portão publicava
    **7,08:1** para o mesmo par, porque resolvia `PlaceholderText` pelo token opaco da
    `QPalette` e nunca compunha o alfa com que o Qt a desenha. Aqui o par é medido em todo campo
    **habilitado**, que é o estado normal da aba, e nas duas peles.
    """
    for pele in relatorio["peles"]:
        dicas = [
            par
            for par in relatorio["todos_os_pares"][pele["nome"]]
            if "dica: placeholderText" in par["onde"] and par["portao"]
        ]
        assert len(dicas) >= 4, f"{pele['nome']}: só {len(dicas)} dicas de campo medidas"
        for par in dicas:
            assert par["razao"] >= contraste.AA_TEXTO, (
                f"{pele['nome']}: {par['onde']} dá {par['razao']:.2f}:1 -- "
                f"{par['frente']} sobre {par['fundo']} ({par['nota']})"
            )


def test_o_par_da_paleta_concorda_com_a_dica_derivada_da_folha(relatorio: dict) -> None:
    """As duas réguas do mesmo pixel têm de dar o mesmo número.

    `QPalette.Active: PlaceholderText sobre Base` e `QLineEdit (dica: placeholderText)` medem o
    **mesmo** texto na mesma superfície. No ciclo 5 elas divergiam por 1,79× -- uma lia o token,
    a outra não existia. Divergirem de novo é o defeito voltando por outro nome.
    """
    for pele in relatorio["peles"]:
        pares = {
            par["onde"]: par for par in relatorio["todos_os_pares"][pele["nome"]]
        }
        da_paleta = pares["QPalette.Active: PlaceholderText sobre Base"]
        do_campo = pares["QLineEdit (dica: placeholderText)"]
        assert da_paleta["frente"] == do_campo["frente"], (
            f"{pele['nome']}: a paleta diz {da_paleta['frente']} e a folha diz "
            f"{do_campo['frente']} para a mesma dica"
        )
        assert abs(da_paleta["razao"] - do_campo["razao"]) < 0.01


def test_a_folha_declara_a_cor_da_dica_em_vez_de_deixar_o_qt_deriva_la() -> None:
    """A metade do conserto que mora na folha, afirmada no texto que embarca.

    Sem `placeholder-text-color`, o Qt deriva a dica de `color:` a `ALFA_DA_DICA` -- e o
    comentário que promete o conserto na folha já esteve, uma vez, em cima de uma regra de
    `selection-background-color`, que é outra propriedade. Esta asserção olha a **regra**.
    """
    from chess_diagram_ocr.ui import folha_de_estilo as folha_pura

    for cromo_escuro in (False, True):
        folha = folha_pura.folha_de_estilo(cromo_escuro=cromo_escuro)
        regras = contraste.analisar(folha)
        for classe in contraste.CLASSES_COM_DICA:
            valor = contraste.valor_de(regras, contraste.Alvo(classe), "placeholder-text-color")
            assert contraste._cor_de(valor), (
                f"{'escuro' if cromo_escuro else 'claro'}: {classe} não declara a cor da dica"
            )


def test_o_portao_reprova_quando_a_declaracao_da_dica_some() -> None:
    """**A prova de vida do portão**, e ela é o item que o ciclo 5 exigiu.

    Um portão novo sem sabotagem é uma promessa. Esta apaga a declaração da folha gerada -- o
    estado exato do ciclo 5 -- e exige que o relatório **reprove** com o número que o crítico
    mediu no pixel: **3,96:1** na pele clara. Se ela passar a ficar verde, o portão voltou a ser
    incapaz de cobrar o conserto que acabou de receber.
    """
    import re

    from chess_diagram_ocr.ui import folha_de_estilo as folha_pura

    original = folha_pura.folha_de_estilo
    try:
        folha_pura.folha_de_estilo = lambda **kw: re.sub(  # type: ignore[assignment]
            r" placeholder-text-color: #[0-9a-fA-F]{6};", "", original(**kw)
        )
        sabotado = contraste.medir(caminho_do_tronco=TRONCO)
    finally:
        folha_pura.folha_de_estilo = original  # type: ignore[assignment]

    assert sabotado["veredito"] == "REPROVOU", "a folha sem a dica passou o portão"
    reprovados = sabotado["reprovados"]["claro"]
    assert reprovados, "a pele clara não acusou a dica derivada a alpha 128"
    razoes = {round(par["razao"], 2) for par in reprovados}
    assert razoes == {3.96}, f"esperava 3,96:1 (o pixel do crítico), veio {sorted(razoes)}"


def test_compor_faz_a_aritmetica_que_o_qt_faz() -> None:
    """A função nova, contra o pixel medido na janela viva.

    `#000000` a alpha 128 sobre o poço `#f8f9fb` é o que o crítico fotografou: `rgb(124,124,126)`
    no núcleo do glifo, **3,96:1**. Alfa 255 tem de ser identidade -- senão todo par opaco do
    relatório mudaria de valor por causa desta função.
    """
    composta = contraste.compor("#000000", "#f8f9fb", alfa=contraste.ALFA_DA_DICA)
    assert composta == "#7c7c7d"
    assert round(contraste._razao(composta, "#f8f9fb"), 2) == 3.96
    assert contraste.compor("#123456", "#ffffff") == "#123456"
    assert contraste.compor("#123456", "", alfa=128) == "#123456"


def test_cor_e_alfa_le_as_tres_grafias_de_translucido() -> None:
    """`rgba()` em 0–255, em 0–1, em porcento, e `#rrggbbaa`. Opaco continua opaco."""
    assert contraste.cor_e_alfa("#f8f9fb") == ("#f8f9fb", 255)
    assert contraste.cor_e_alfa("#00000080") == ("#000000", 128)
    assert contraste.cor_e_alfa("rgba(0, 0, 0, 128)") == ("#000000", 128)
    assert contraste.cor_e_alfa("rgba(0, 0, 0, 0.5)") == ("#000000", 128)
    assert contraste.cor_e_alfa("rgba(0, 0, 0, 50%)") == ("#000000", 128)
    assert contraste.cor_e_alfa("1px solid #767e88") == ("#767e88", 255)
    assert contraste.cor_e_alfa("nada") == ("", 255)
