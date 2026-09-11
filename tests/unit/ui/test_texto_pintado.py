"""A régua do texto **pintado**, e a faixa que a folha reserva para ele (F9-C14).

**O ciclo 13 reprovou esta frente pelo décimo primeiro instrumento cego, e a cegueira era de uma
espécie nova: a fonte.** Toda régua daqui perguntava a medida do texto a `QWidget.fontMetrics()`
e a tela pintava a fonte da folha de estilo -- `QGroupBox::title { font-size: 12pt; bold }`,
**21 px**, dentro de uma faixa que `margin-top` reservava a partir de `espaco.linha()`, **4 px na
densidade compacta**. Seis de seis títulos de grupo da janela chegavam à tela com até 8 dos seus
21 px **debaixo do primeiro filho do próprio grupo**: `Lances`, `Comentário do lance` e `Filtros`
com a metade de baixo de cada letra apagada, fotografados nos ciclos 10, 12 e 13 sem que régua
nenhuma os visse.

Estes testes cobram as duas metades, e as duas **sem abrir Qt** -- o venv desta suíte não tem
binding nenhum, e é isso que faz o portão rodar na CI:

* **o produto**: a faixa do título sai da mesma escala tipográfica que o pinta, e não de um token
  de espaçamento. Não há número cravado a conferir; o que se afirma é que os dois lados leem a
  mesma tabela, em toda densidade e em toda fonte-base.
* **a régua**: ela lê a folha aplicada -- fonte **e** caixa --, e não uma tabela de seletores
  escrita à mão. Uma regra de fonte nova entra na régua no mesmo commit em que entra na folha, e
  um seletor que a análise não entenda aparece como número publicado em vez de virar silêncio.
"""

from __future__ import annotations

import pytest

from caissa.ui.audit import texto_pintado as tp


def _folha() -> object:
    from chess_diagram_ocr.ui import folha_de_estilo

    return folha_de_estilo


def _tipografia() -> object:
    from chess_diagram_ocr.ui import tipografia

    return tipografia


BASES = (7, 9, 10, 12, 14)
"""As fontes-base que a janela tem de aguentar. `9` é a de referência; `12` é a do Windows
em "tamanho grande"."""

DENSIDADES = ("compacta", "confortavel")


class TestAFaixaDoTituloSaiDaEscalaQuePinta:
    """O bloqueante do ciclo 13, pelo lado do produto."""

    @pytest.mark.parametrize("base", BASES)
    @pytest.mark.parametrize("densidade", DENSIDADES)
    def test_a_faixa_cabe_o_titulo_pintado(self, base: int, densidade: str) -> None:
        """`margin-top` do `QGroupBox` >= a altura do que `QGroupBox::title` manda desenhar.

        É a asserção que o defeito violava: 4 px de faixa para 21 px de título.
        """
        folha, tipografia = _folha(), _tipografia()
        qss = folha.folha_de_estilo(base=base, densidade=densidade)
        regras = tp.regras_da_folha(qss)
        faixa = _margem_do_topo(qss)
        pintado = tp.fonte_da_folha(
            regras,
            classes=("QGroupBox", "QWidget"),
            subcontrole="title",
            base=tp.Fonte("Segoe UI", float(base), False),
        )
        precisa = tipografia.altura_do_texto(int(pintado.pontos))
        assert faixa >= precisa, (
            f"base={base} densidade={densidade}: a folha reserva {faixa} px para um título que "
            f"ela manda pintar com {pintado.pontos} pt, e que ocupa {precisa} px."
        )

    @pytest.mark.parametrize("densidade", DENSIDADES)
    def test_a_faixa_nao_e_mais_o_token_de_espacamento(self, densidade: str) -> None:
        """A prova de que os dois números deixaram de vir de escalas diferentes.

        `espaco.linha()` é `FOLGA_DE_LINHA` -- 6 px na confortável, 4 na compacta. Enquanto a
        faixa fosse esse número, ela não tinha como acompanhar o título.
        """
        folha, tipografia = _folha(), _tipografia()
        qss = folha.folha_de_estilo(base=9, densidade=densidade)
        linha = tipografia.folga(tipografia.FOLGA_DE_LINHA, base=9, densidade=densidade)
        assert _margem_do_topo(qss) > linha

    def test_um_degrau_a_mais_no_titulo_move_a_faixa_junto(self) -> None:
        """**A prova de que a deriva deixou de ser possível.**

        O crítico pediu esta: aumentar o título em 1 pt tinha de derrubar o portão *antes*. Com
        os dois lados lendo a mesma escala, ele não derruba -- a faixa sobe junto. É a diferença
        entre consertar o número e fechar a forma do defeito.
        """
        folha, tipografia = _folha(), _tipografia()
        faixas = [_margem_do_topo(folha.folha_de_estilo(base=base)) for base in (9, 10, 12)]
        pontos = [tipografia.escala(base)[tipografia.TITULO] for base in (9, 10, 12)]
        assert faixas == sorted(faixas) and faixas[0] < faixas[-1]
        assert all(
            faixa >= tipografia.altura_do_texto(pt)
            for faixa, pt in zip(faixas, pontos, strict=True)
        )

    def test_a_medida_medida_ganha_da_estimada(self) -> None:
        """Quem tem toolkit passa a altura exata; sem ele, a conta pura -- e ela é **por cima**."""
        folha, tipografia = _folha(), _tipografia()
        estimada = _margem_do_topo(folha.folha_de_estilo(base=9))
        medida = _margem_do_topo(folha.folha_de_estilo(base=9, altura_do_titulo=21))
        assert medida == 21
        assert estimada >= tipografia.altura_do_texto(tipografia.escala(9)[tipografia.TITULO])
        assert estimada >= medida, "a conta pura tem de reservar por cima, nunca por baixo"

    def test_altura_do_texto_e_por_cima_em_toda_a_escala(self) -> None:
        """A conta pura contra a medição de `QFontMetrics` publicada em `ALTURA_POR_PONTO`."""
        tipografia = _tipografia()
        medido = {
            7: 12, 8: 15, 9: 16, 10: 17, 11: 20, 12: 21,
            13: 22, 14: 26, 15: 27, 16: 28, 18: 32, 20: 36, 24: 43,
        }
        for pontos, altura in medido.items():
            assert tipografia.altura_do_texto(pontos) >= altura, pontos
        assert tipografia.altura_do_texto(0) == 1, "reserva zero é reserva que não existe"
        assert tipografia.altura_do_texto(-3) == 1


class TestARegraLeAFolhaEnaoUmaTabela:
    """A régua, pelo lado da largura: ela não pode ter uma lista própria de seletores."""

    @pytest.mark.parametrize("densidade", DENSIDADES)
    def test_acha_toda_regra_de_fonte_da_folha(self, densidade: str) -> None:
        """As quatro regras que trocam a fonte, lidas do texto da folha e não declaradas aqui."""
        qss = _folha().folha_de_estilo(base=9, densidade=densidade)
        achadas = {
            (regra.classe, regra.subcontrole) for regra in tp.regras_de_fonte(qss)
        }
        assert achadas >= {
            ("QGroupBox", "title"),
            ("QHeaderView", "section"),
            ("QTabBar", "tab"),
            ("QLabel", ""),
        }

    @pytest.mark.parametrize("densidade", DENSIDADES)
    def test_a_regua_le_toda_regra_de_fonte_da_folha(self, densidade: str) -> None:
        """**O teste que o módulo citava como defesa e que não existia** (F9-C15 §4.3).

        `PROPRIEDADES_DE_FONTE` escrevia *"se a forma curta aparecer um dia, `regras_de_fonte` não
        a vê e o teste `test_a_regua_le_toda_regra_de_fonte_da_folha` falha"*. O que existia era
        `test_acha_toda_regra_de_fonte_da_folha`, logo acima, e ele afirma um **superconjunto**:
        uma regra que a régua perdesse não o derrubava. A defesa declarada contra a estreiteza da
        régua era a única das quatro válvulas que não fechava, e o nome que ela citava estava
        errado.

        Este é o teste com o nome certo, e ele é uma **partição**: todo bloco da folha que mexe na
        fonte está ou entre os lidos, ou entre os publicados como fora da análise. Nada cai no
        meio, que era exatamente o que a forma curta fazia.
        """
        qss = _folha().folha_de_estilo(base=9, densidade=densidade)
        na_folha = sorted(
            seletor.strip()
            for seletor, corpo in tp._BLOCO.findall(qss)
            if any(tp.mexe_na_fonte(chave) for chave, _ in tp._declaracoes(corpo))
        )
        lidos = [_como_seletor(regra) for regra in tp.regras_de_fonte(qss)]
        ignorados = list(tp.seletores_ignorados(qss))
        assert sorted(lidos + ignorados) == na_folha, (
            "há regra de fonte na folha que a régua não lê e não publica como ignorada: "
            f"{sorted(set(na_folha) - set(lidos) - set(ignorados))}"
        )
        assert ignorados == [], f"a régua deixou de entender {ignorados}"
        assert len(lidos) == 4, f"a folha tem {len(lidos)} regras de fonte, e não 4: {lidos}"

    def test_nenhum_seletor_de_fonte_escapa_da_analise(self) -> None:
        """Um seletor que a régua não entenda é número publicado, e aqui ele tem de ser zero."""
        qss = _folha().folha_de_estilo(base=9, densidade="compacta")
        assert tp.seletores_ignorados(qss) == ()

    @pytest.mark.parametrize(
        "sabotagem",
        [
            'QGroupBox::title { font: bold 20pt "Segoe UI"; }',
            "QGroupBox::title, QHeaderView::section { font-size: 20pt; }",
            "QWidget QGroupBox::title { font-size: 20pt; }",
            "QGroupBox#painel::title { font-size: 20pt; }",
        ],
        ids=["forma-curta", "virgula", "descendencia", "id"],
    )
    def test_a_forma_curta_de_font_nao_escapa(self, sabotagem: str) -> None:
        """**As quatro sabotagens do crítico, e as quatro têm de acusar** (F9-C15 §4.3).

        Ele trocou a linha `QGroupBox::title` da folha por estas quatro, em memória, e mediu:
        vírgula, descendência e `#id` faziam `seletores ignorados` ir a 1 -- a válvula funciona --,
        e a forma curta ia a **0**, calada. A causa era `_declaracoes_de_fonte` peneirar pela
        **mesma** tupla que `regras_de_fonte`: o que a régua não sabia ler, ela também não via.

        As quatro agora acusam, e é `mexe_na_fonte` que separa "isto mexe na fonte" de "eu sei ler
        isto".
        """
        qss = f"QWidget {{ color: #000000; }}\n{sabotagem}"
        assert len(tp.seletores_ignorados(qss)) == 1, (
            f"a sabotagem {sabotagem!r} passou pelas duas peneiras: "
            f"ignorados={tp.seletores_ignorados(qss)}"
        )

    def test_font_style_deixou_de_ser_lido_e_jogado_fora(self) -> None:
        """`font-style` estava declarado como legível e `_aplicar` não tinha ramo para ele.

        Era o mesmo defeito da forma curta com o sinal trocado: a regra passava pela peneira que
        diz "eu sei ler isto" e era descartada em seguida, e o itálico muda o avanço do texto.
        """
        qss = "QLabel { font-style: italic; }"
        saida = tp.fonte_da_folha(
            tp.regras_da_folha(qss), classes=("QLabel",), base=tp.Fonte("x", 9.0, False)
        )
        assert saida.italico is True
        assert tp.seletores_ignorados(qss) == ()
        volta = tp.fonte_da_folha(
            tp.regras_da_folha(qss + "\nQLabel { font-style: normal; }"),
            classes=("QLabel",),
            base=tp.Fonte("x", 9.0, False),
        )
        assert volta.italico is False

    def test_a_fonte_pintada_difere_da_do_widget_onde_o_ponto_cego_mora(self) -> None:
        """O tamanho do ponto cego, em pontos: 9 pt não-negrito contra 12 pt negrito."""
        regras = tp.regras_da_folha(_folha().folha_de_estilo(base=9))
        corpo = tp.Fonte("Segoe UI", 9.0, False)
        titulo = tp.fonte_da_folha(
            regras, classes=("QGroupBox", "QWidget"), subcontrole="title", base=corpo
        )
        secao = tp.fonte_da_folha(
            regras, classes=("QHeaderView", "QWidget"), subcontrole="section", base=corpo
        )
        aba = tp.fonte_da_folha(
            regras,
            classes=("QTabBar", "QWidget"),
            subcontrole="tab",
            estados=("selected",),
            base=corpo,
        )
        assert (titulo.pontos, titulo.negrito) == (12.0, True)
        assert (secao.pontos, secao.negrito) == (12.0, True)
        assert (aba.pontos, aba.negrito) == (9.0, True), "negrito muda a largura, não o tamanho"
        assert tp.fonte_da_folha(regras, classes=("QLabel", "QWidget"), base=corpo) == corpo

    def test_a_propriedade_dinamica_e_respeitada(self) -> None:
        """`QLabel[apoio="true"]` só alcança quem declara a propriedade."""
        regras = tp.regras_da_folha(_folha().folha_de_estilo(base=9))
        corpo = tp.Fonte("Segoe UI", 9.0, False)
        com = tp.fonte_da_folha(
            regras, classes=("QLabel",), propriedades={"apoio": "true"}, base=corpo
        )
        sem = tp.fonte_da_folha(regras, classes=("QLabel",), base=corpo)
        assert com.pontos == 8.0 and sem.pontos == 9.0

    def test_a_caixa_do_cabecalho_sai_da_folha(self) -> None:
        """A segunda metade do ponto cego: quem come a largura do cabeçalho é o recheio da folha.

        `QHeaderView::section { padding: 2px 6px; border-right: 1px }` -> 13 px de largura que
        não são do texto. Perguntar a caixa ao estilo da plataforma devolve outro número.
        """
        regras = tp.regras_da_folha(_folha().folha_de_estilo(base=9, densidade="compacta"))
        caixa = tp.caixa_da_folha(
            regras, classes=("QHeaderView", "QWidget"), subcontrole="section"
        )
        assert caixa.horizontal == 13, caixa
        assert caixa.esquerda == 6 and caixa.direita == 7

    def test_a_ordem_da_folha_decide_quem_ganha(self) -> None:
        """Entre duas regras de mesma especificidade, a última do texto ganha -- como no QSS."""
        qss = "QLabel { font-size: 9pt; }\nQLabel { font-size: 11pt; }"
        saida = tp.fonte_da_folha(
            tp.regras_da_folha(qss), classes=("QLabel",), base=tp.Fonte("x", 9.0, False)
        )
        assert saida.pontos == 11.0

    def test_pixel_vira_ponto(self) -> None:
        """`font-size: 16px` a 96 dpi é 12 pt, que é o que o Qt desenha."""
        qss = "QLabel { font-size: 16px; }"
        saida = tp.fonte_da_folha(
            tp.regras_da_folha(qss), classes=("QLabel",), base=tp.Fonte("x", 9.0, False)
        )
        assert saida.pontos == pytest.approx(12.0)


class TestQuemPintaCadaSubcontrole:
    """**O décimo segundo instrumento cego: a régua perguntava à folha onde a folha não vota.**

    Medido no pixel pelo crítico do ciclo 15 e reproduzido por mim em
    `benchmarks/reports/ui/c16/c16_quem_pinta.py`, texto `Comentário do lance`, referências
    9 pt = 109 px, 12 pt negrito = 159 px, 20 pt negrito = 267 px:

    ```
      QGroupBox::title       folha 20pt neg / widget  9pt     -> a tela desenha 109 px   o WIDGET
      QGroupBox::title       folha 12pt neg / widget 20pt neg -> a tela desenha 265 px   o WIDGET
      QHeaderView::section   folha 20pt neg / widget  9pt     -> a tela desenha 265 px   a FOLHA
      QHeaderView::section   folha 12pt neg / widget 20pt neg -> a tela desenha 157 px   a FOLHA
    ```

    Dois seletores da mesma tabela obedecendo a regras contrárias. Estes testes são a metade
    afirmável sem Qt: que o produto **registre** a resposta, que ela cubra toda a folha, e que a
    régua pergunte a quem ganha.
    """

    def test_quem_pinta_cobre_toda_regra_de_fonte_da_folha(self) -> None:
        """A válvula: um quinto seletor de fonte na folha sem resposta em `QUEM_PINTA` derruba.

        É o que impede a tabela de ficar para trás da folha -- a doença que o §4 da crítica do
        ciclo 15 nomeia, uma lista escrita à mão em que a regra seguinte nasce de fora.
        """
        folha = _folha()
        for densidade in DENSIDADES:
            qss = folha.folha_de_estilo(base=9, densidade=densidade)
            na_folha = {
                seletor.strip()
                for seletor, corpo in tp._BLOCO.findall(qss)
                if any(tp.mexe_na_fonte(chave) for chave, _ in tp._declaracoes(corpo))
            }
            sem_resposta = na_folha - set(folha.QUEM_PINTA)
            assert not sem_resposta, (
                f"a folha pinta {sorted(sem_resposta)} com uma fonte e "
                "folha_de_estilo.QUEM_PINTA não diz qual das duas ganha"
            )
        assert set(folha.QUEM_PINTA.values()) <= {folha.O_WIDGET, folha.A_FOLHA}

    def test_o_titulo_do_grupo_e_pintado_pelo_widget(self) -> None:
        """A resposta que custou o instrumento cego, registrada como dado e não como prosa."""
        folha = _folha()
        assert folha.QUEM_PINTA["QGroupBox::title"] == folha.O_WIDGET
        assert folha.QUEM_PINTA["QHeaderView::section"] == folha.A_FOLHA
        assert folha.QUEM_PINTA["QTabBar::tab:selected"] == folha.A_FOLHA

    def test_a_regua_mede_a_fonte_que_ganha_em_cada_um(self) -> None:
        """**A prova de vida do item 2 do §8: um caso em que as duas discordam.**

        O crítico pôs o título a 20 pt na folha e mediu a régua dizendo 85 px onde a tela
        desenhava 34. Aqui a mesma discordância, em pontos: com o widget a 9 pt e a folha a 20 pt,
        a régua tem de responder **9 pt** no título e **20 pt** no cabeçalho.
        """
        folha = _folha()
        qss = (
            "QGroupBox::title { font-size: 20pt; font-weight: bold; }\n"
            "QHeaderView::section { font-size: 20pt; font-weight: bold; }"
        )
        regras = tp.regras_da_folha(qss)
        widget = tp.Fonte("Segoe UI", 9.0, False)

        titulo = tp.fonte_que_pinta(
            regras,
            quem_pinta=folha.QUEM_PINTA["QGroupBox::title"],
            classes=("QGroupBox", "QWidget"),
            subcontrole="title",
            base=widget,
        )
        secao = tp.fonte_que_pinta(
            regras,
            quem_pinta=folha.QUEM_PINTA["QHeaderView::section"],
            classes=("QHeaderView", "QWidget"),
            subcontrole="section",
            base=widget,
        )
        assert titulo == widget, "no título quem pinta é o widget: a folha de 20 pt é descartada"
        assert (secao.pontos, secao.negrito) == (20.0, True), "no cabeçalho a folha ganha"
        # E a régua antiga -- a que perguntava à folha nos dois -- diria 20 pt nos dois. É a
        # diferença que o §4.2 mediu como "85 px onde a tela desenha 34".
        antiga = tp.fonte_da_folha(
            regras, classes=("QGroupBox", "QWidget"), subcontrole="title", base=widget
        )
        assert antiga.pontos == 20.0 and titulo.pontos == 9.0

    def test_um_seletor_sem_resposta_levanta_em_vez_de_chutar(self) -> None:
        """Sem resposta a régua **para**. Um padrão silencioso mediria a fonte errada calada."""
        with pytest.raises(KeyError, match="QUEM_PINTA"):
            tp._quem_pinta({"QGroupBox::title": tp.O_WIDGET}, "QHeaderView::section")
        with pytest.raises(ValueError, match="quem_pinta"):
            tp.fonte_que_pinta(
                (), quem_pinta="talvez", classes=("QLabel",), base=tp.Fonte("x", 9.0, False)
            )


class TestAsDuasTabelasDoTitulo:
    """**`PAPEL_PINTADO` e `PAPEL_POR_CLASSE` param de ser duas tabelas** (§8 item 3).

    O que mantinha a faixa e a tinta em 21 px era as duas dizerem `TITULO`, cada uma no seu módulo.
    Bastava tirar `QGroupBox` de `PAPEL_POR_CLASSE` -- acreditando no que o produto tinha escrito,
    que era que a folha pinta o título -- para o título cair a 9 pt dentro de uma faixa de 21, com
    o portão devolvendo `0 cobertos` e `PASSOU`.
    """

    def test_o_degrau_do_titulo_e_o_da_classe_do_grupo(self) -> None:
        folha, tipografia = _folha(), _tipografia()
        assert (
            folha.PAPEL_PINTADO["QGroupBox::title"]
            == tipografia.PAPEL_POR_CLASSE["QGroupBox"]
        )
        assert (
            folha.PAPEL_PINTADO["QHeaderView::section"]
            == tipografia.PAPEL_POR_CLASSE["QHeaderView"]
        )

    def test_a_faixa_acompanha_a_classe_e_nao_o_literal(self) -> None:
        """A prova de que é derivação e não coincidência: mudar a classe move a faixa.

        Se as duas ainda fossem dois literais, trocar o degrau de `PAPEL_POR_CLASSE["QGroupBox"]`
        deixaria a faixa onde estava -- e o título, que é pintado pela fonte do widget, encolheria
        dentro dela. Aqui a faixa segue.
        """
        folha, tipografia = _folha(), _tipografia()
        original = dict(tipografia.PAPEL_POR_CLASSE)
        try:
            tipografia.PAPEL_POR_CLASSE["QGroupBox"] = tipografia.AUXILIAR
            import importlib

            recarregada = importlib.reload(folha)
            assert recarregada.PAPEL_PINTADO["QGroupBox::title"] == tipografia.AUXILIAR
            faixa = _margem_do_topo(recarregada.folha_de_estilo(base=9, densidade="compacta"))
            esperada = tipografia.altura_do_texto(
                tipografia.escala(9)[tipografia.AUXILIAR]
            )
            assert faixa == esperada, "a faixa não seguiu o degrau da classe"
        finally:
            tipografia.PAPEL_POR_CLASSE.clear()
            tipografia.PAPEL_POR_CLASSE.update(original)
            import importlib

            importlib.reload(folha)


class TestAAritmeticaDosDoisDefeitos:
    """`coberto` e `cortado`, contra os números que o crítico publicou."""

    def test_coberto_reproduz_o_bloqueante(self) -> None:
        """O título pinta de 0 a 21 e o primeiro filho começa em 13: 8 px de letra apagada."""
        assert tp.coberto((4, 0, 60, 21), (0, 13, 300, 200)) == 8
        assert tp.coberto((4, 0, 60, 21), (0, 21, 300, 200)) == 0, "encostar não é cobrir"
        assert tp.coberto((4, 0, 60, 21), (400, 0, 10, 21)) == 0, "não se cruzam na horizontal"

    def test_cortado_reproduz_o_cabecalho(self) -> None:
        """`Resultado` pinta 76 px numa seção que dá 67 de espaço útil."""
        assert tp.cortado(76, 67) == 9
        assert tp.cortado(44, 42) == 2
        assert tp.cortado(27, 32) == 0

    def test_um_achado_sabe_dizer_se_e_cego(self) -> None:
        """`cego` é a definição do ponto cego: a folha pinta uma fonte que o widget não tem."""
        igual = tp.Achado(
            tela="x", onde="y", classe="QLabel", subcontrole="", texto="t",
            fonte_do_widget=tp.Fonte("a", 9.0, False), fonte_pintada=tp.Fonte("a", 9.0, False),
        )
        diferente = tp.Achado(
            tela="x", onde="y", classe="QGroupBox", subcontrole="title", texto="t",
            fonte_do_widget=tp.Fonte("a", 9.0, False), fonte_pintada=tp.Fonte("a", 12.0, True),
        )
        assert not igual.cego and diferente.cego
        assert not igual.defeito

    def test_uma_medicao_omissa_nao_vira_aprovacao(self) -> None:
        """Zero passadas é `REPROVOU`: foi assim que o ciclo 9 publicou uma pele que não mediu."""
        assert tp.veredito([]) == "REPROVOU"
        assert tp.veredito([{"veredito": "PASSOU"}]) == "PASSOU"
        assert tp.veredito([{"veredito": "PASSOU"}, {"veredito": "REPROVOU"}]) == "REPROVOU"


def _como_seletor(regra: "tp.Regra") -> str:
    """O seletor de volta ao texto, na grafia em que a folha o escreve.

    Existe para `test_a_regua_le_toda_regra_de_fonte_da_folha` comparar o que a régua leu com o
    que está escrito na folha, e não com uma lista escrita aqui.
    """
    texto = regra.classe
    for chave, valor in regra.propriedades:
        texto += f'[{chave}="{valor}"]'
    if regra.subcontrole:
        texto += f"::{regra.subcontrole}"
    for estado in regra.estados:
        texto += f":{estado}"
    return texto


def _margem_do_topo(qss: str) -> int:
    """O `margin-top` que a folha dá ao `QGroupBox`, lido do texto dela."""
    import re

    casado = re.search(r"QGroupBox\s*\{[^}]*margin-top:\s*(\d+)px", qss)
    assert casado is not None, "a folha deixou de reservar faixa para o título do grupo"
    return int(casado.group(1))
