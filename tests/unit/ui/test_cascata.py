"""A cascata do QSS que o portão de contraste usa para achar o fundo de cada texto.

**Este é o pedaço em que um portão de contraste mente sem que ninguém veja.** Se a resolução do
fundo estiver errada, cada par continua sendo medido -- contra a cor errada. O relatório fica
verde, o número existe, e o defeito na tela continua lá. Por isso a cascata é afirmada aqui
contra folhas escritas à mão, cujo resultado se lê no próprio caso.

As folhas de teste são minúsculas de propósito. Uma asserção contra a folha do produto mediria a
folha e a cascata ao mesmo tempo, e um dia em que a folha mudasse a falha não diria qual das duas
quebrou.
"""

from __future__ import annotations

import pytest

from caissa.ui.audit import contraste
from caissa.ui.audit.contraste import Alvo


def _resolver(folha: str, alvo: Alvo) -> str:
    return contraste.fundo_de(contraste.analisar(folha), alvo)


class TestAnalise:
    def test_uma_regra_por_seletor_e_a_virgula_vira_duas(self) -> None:
        regras = contraste.analisar(
            "QCheckBox::indicator, QRadioButton::indicator { width: 14px; }"
        )
        assert [regra.alvo.classe for regra in regras] == ["QCheckBox", "QRadioButton"]
        assert all(regra.alvo.subcontrole == "indicator" for regra in regras)

    def test_o_estado_negado_e_lido_como_estado_proprio(self) -> None:
        """`:!selected` não é `:selected`, e confundi-los faria a aba inativa herdar a ativa."""
        (regra,) = contraste.analisar("QTabBar::tab:!selected { color: #555555; }")
        assert regra.alvo.estados == frozenset({"!selected"})

    def test_o_atributo_dinamico_entra_no_alvo(self) -> None:
        (regra,) = contraste.analisar('QPushButton[papel="PRIMARIO"] { color: #ffffff; }')
        assert regra.alvo.atributo == '[papel="PRIMARIO"]'
        assert regra.alvo.classe == "QPushButton"

    def test_o_seletor_descendente_guarda_o_ancestral(self) -> None:
        (regra,) = contraste.analisar("QComboBox QAbstractItemView { background-color: #fff000; }")
        assert regra.alvo.classe == "QAbstractItemView"
        assert regra.alvo.ancestral == "QComboBox"

    def test_linha_que_nao_e_regra_e_ignorada_sem_levantar(self) -> None:
        assert contraste.analisar("# um comentário\n\nQWidget { color: #000000; }") != []


class TestCascata:
    def test_a_subclasse_herda_a_regra_escrita_na_base(self) -> None:
        """É o que faz `QListWidget` receber o que a folha escreve em `QAbstractItemView`."""
        folha = "QAbstractItemView { background-color: #101010; }"
        assert _resolver(folha, Alvo("QListWidget")) == "#101010"

    def test_a_classe_mais_derivada_ganha_da_base(self) -> None:
        folha = (
            "QAbstractItemView { background-color: #101010; }\n"
            "QListWidget { background-color: #202020; }"
        )
        assert _resolver(folha, Alvo("QListWidget")) == "#202020"

    def test_a_base_escrita_depois_nao_ganha_da_derivada(self) -> None:
        """A ordem desempata **entre iguais**; especificidade de classe vem antes da posição."""
        folha = (
            "QListWidget { background-color: #202020; }\n"
            "QAbstractItemView { background-color: #101010; }"
        )
        assert _resolver(folha, Alvo("QListWidget")) == "#202020"

    def test_o_estado_ganha_de_quem_nao_tem_estado(self) -> None:
        folha = (
            "QPushButton { background-color: #101010; }\n"
            "QPushButton:disabled { background-color: #303030; }"
        )
        alvo = Alvo("QPushButton", estados=frozenset({"disabled"}))
        assert _resolver(folha, alvo) == "#303030"
        assert _resolver(folha, Alvo("QPushButton")) == "#101010"

    def test_o_ancestral_de_um_descendente_nao_pinta_o_alvo_solto(self) -> None:
        """**O defeito que isto fecha valia 0,97 de razão de contraste** (F9).

        `QComboBox QAbstractItemView` é a lista suspensa da caixa de escolha, e colapsá-la em
        `QAbstractItemView` fazia a face elevada do menu suspenso virar o fundo de repouso de
        **qualquer** item da janela. A seleção passava a ser medida contra `#2c3036` em vez de
        `#15171a`, e o par saía como 2,75:1 num lugar em que a tela mostra 3,72:1.
        """
        folha = (
            "QWidget { background-color: #1f2124; }\n"
            "QComboBox QAbstractItemView { background-color: #2c3036; }"
        )
        assert _resolver(folha, Alvo("QAbstractItemView")) == "#1f2124"
        assert _resolver(folha, Alvo("QAbstractItemView", ancestral="QComboBox")) == "#2c3036"

    def test_a_subpeca_transparente_cai_na_superficie_de_tras(self) -> None:
        """`QMenuBar::item { background: transparent }` é desenhado sobre a barra do menu."""
        folha = (
            "QMenuBar { background-color: #1f2124; }\n"
            "QMenuBar::item { background: transparent; }"
        )
        assert _resolver(folha, Alvo("QMenuBar", "item")) == "#1f2124"

    def test_a_subpeca_sem_fundo_proprio_herda_a_do_widget(self) -> None:
        folha = (
            "QTabBar::tab { background-color: #1f2124; }\n"
            "QTabBar::tab:selected { border-bottom: 2px solid #84b6ff; }"
        )
        alvo = Alvo("QTabBar", "tab", estados=frozenset({"selected"}))
        assert _resolver(folha, alvo) == "#1f2124"

    def test_sem_nenhuma_regra_o_fundo_e_o_do_qwidget(self) -> None:
        assert _resolver("QWidget { background-color: #f0f0f0; }", Alvo("QSlider")) == "#f0f0f0"


class TestPares:
    def test_um_texto_sobre_um_fundo_declarado_vira_par_de_texto(self) -> None:
        folha = "QWidget { background-color: #ffffff; color: #777777; }"
        pares = contraste.pares_da_folha(folha, cromo_escuro=False)
        texto = [par for par in pares if par.especie == contraste.TEXTO]
        assert len(texto) == 1
        assert texto[0].piso == contraste.AA_TEXTO
        # `#777777` sobre branco é a âncora conhecida de `tokens.razao_de_contraste`: 4,48:1,
        # o cinza que fica logo **abaixo** do piso AA. Um par que passasse aqui denunciaria a
        # conta, e não a folha.
        assert texto[0].razao == pytest.approx(4.48, abs=0.01)
        assert not texto[0].passou()

    def test_o_limite_do_componente_e_o_melhor_dos_dois_caminhos(self) -> None:
        """Uma borda que some dentro do preenchimento não é defeito se o corpo se vê no painel.

        A 1.4.11 pede que *alguma* informação visual que identifique o componente esteja a 3:1
        das cores adjacentes; ela não pede que **todas** estejam.
        """
        folha = (
            "QWidget { background-color: #ffffff; }\n"
            "QPushButton { background-color: #222222; border: 1px solid #232323; }"
        )
        limites = [
            par
            for par in contraste.pares_da_folha(folha, cromo_escuro=False)
            if par.especie == contraste.BORDA
        ]
        assert len(limites) == 1
        assert limites[0].passou(), "o corpo escuro identifica o botão mesmo com a borda invisível"
        assert "borda" in limites[0].nota and "corpo" in limites[0].nota

    def test_o_estado_transitorio_e_medido_e_nao_reprova(self) -> None:
        folha = (
            "QWidget { background-color: #ffffff; }\n"
            "QPushButton { background-color: #ffffff; border: 1px solid #cccccc; }\n"
            "QPushButton:hover { background-color: #fefefe; border: 1px solid #fdfdfd; }"
        )
        pares = contraste.pares_da_folha(folha, cromo_escuro=False)
        hover = [par for par in pares if "hover" in par.onde and par.especie == contraste.BORDA]
        assert hover, "o estado sob o ponteiro tem de aparecer no relatório"
        assert not hover[0].portao
        assert hover[0].nota.startswith("estado transitório")

    def test_o_texto_do_estado_transitorio_continua_sendo_portao(self) -> None:
        """Foi exatamente ali que o rótulo do botão primário caiu para 4,47:1."""
        folha = (
            "QWidget { background-color: #ffffff; }\n"
            "QPushButton:hover { background-color: #3676d4; color: #ffffff; }"
        )
        pares = contraste.pares_da_folha(folha, cromo_escuro=False)
        texto = [par for par in pares if par.especie == contraste.TEXTO and "hover" in par.onde]
        assert texto and texto[0].portao and not texto[0].passou()

    def test_o_componente_inativo_e_medido_e_isento_com_motivo(self) -> None:
        folha = (
            "QWidget { background-color: #ffffff; }\n"
            "QPushButton:disabled { background-color: #ffffff; color: #eeeeee; }"
        )
        pares = contraste.pares_da_folha(folha, cromo_escuro=False)
        mortos = [par for par in pares if "disabled" in par.onde]
        assert mortos, "o inativo continua no relatório"
        assert all(not par.portao and par.nota for par in mortos)
