"""A aritmética dos três portões numéricos da F9, afirmada **sem abrir janela**.

**Por que a aritmética tem teste próprio, separado do arnês.** Um portão numérico se quebra de
dois jeitos: a janela pode ficar lenta, ou a conta pode ficar generosa. O primeiro o crítico
descobre rodando o arnês; o segundo não aparece em execução nenhuma -- um p95 que na verdade
interpola, um fps derivado da média, um `zip` que perde o último quadro, todos devolvem números
plausíveis para sempre. Por isso a parte que decide o número é pura, mora antes de qualquer
`import PyQt6`, e é afirmada aqui contra casos cujo resultado se calcula à mão.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from caissa.ui.audit import bloqueio, capture, contraste, progresso, quadros, teclado, vazio

# ------------------------------------------------------------------- o tempo de quadro


class TestPercentil:
    """O p95 por posto mais próximo: o número reportado tem de ser um quadro que existiu."""

    def test_o_posto_do_p95_e_ceil_da_fracao_vezes_o_tamanho(self) -> None:
        """Em 20 amostras o posto é `ceil(0,95 x 20) = 19`: o 19º valor, o segundo pior.

        Escrito como asserção sobre o **posto** e não sobre "o pior de vinte" porque a segunda
        frase é falsa e soa verdadeira -- é o tipo de descrição que faz um portão ser lido errado
        pelo próximo a mexer nele.
        """
        assert quadros.percentil(list(range(1, 21)), 0.95) == 19
        assert quadros.percentil(list(range(1, 21)), 1.0) == 20

    def test_ele_nao_interpola(self) -> None:
        """Numa amostra de 60, o p95 interpolado ficaria entre o 57º e o 58º -- e não é quadro.

        A asserção é que o valor devolvido **pertence** à amostra: é ela que separa "posto mais
        próximo" de qualquer variante que invente um tempo de quadro.
        """
        amostra = [float(i) * 1.7 for i in range(60)]
        assert quadros.percentil(amostra, 0.95) in amostra

    def test_amostra_vazia_e_zero_e_nao_erro(self) -> None:
        assert quadros.percentil([], 0.95) == 0.0

    @pytest.mark.parametrize("fracao", [0.0, 0.5, 0.95, 0.99, 1.0])
    def test_o_posto_fica_dentro_da_amostra_em_qualquer_fracao(self, fracao: float) -> None:
        amostra = [1.0, 2.0, 3.0]
        assert quadros.percentil(amostra, fracao) in amostra


class TestEstatisticas:
    def test_o_fps_sai_do_p95_e_nao_da_media(self) -> None:
        """Cinquenta e seis quadros de 5 ms e quatro de 40 ms: média boa, p95 ruim.

        É o caso que o portão existe para reprovar -- uma janela que engasga quatro vezes em
        sessenta quadros tem média de 7,3 ms (137 fps) e p95 de 40 ms (25 fps). Se o `fps_p95`
        seguisse a média, o portão aprovaria exatamente o defeito que ele nomeia.

        **Quatro e não três**, e o número saiu da definição: com 60 amostras o posto do p95 é
        `ceil(57) = 57`, então três quadros lentos ficam nos postos 58, 59 e 60 e o p95 continua
        sendo um quadro rápido. Três engasgos em sessenta são 5 % exatos -- a fronteira que o p95
        promete não ver.
        """
        resumo = quadros.estatisticas([5.0] * 56 + [40.0] * 4)
        assert resumo.fps_mediana > 100.0
        assert resumo.fps_p95 == pytest.approx(25.0, rel=0.01)
        assert not resumo.passou()

    def test_uma_varredura_sem_quadro_nenhum_nao_passa_por_omissao(self) -> None:
        """Zero quadros é ausência de medição, e ausência de medição não é aprovação."""
        vazio = quadros.estatisticas([])
        assert vazio.quadros == 0
        assert not vazio.passou()

    def test_o_portao_e_55_fps_e_a_fronteira_e_o_orcamento_declarado(self) -> None:
        no_limite = quadros.estatisticas([quadros.ORCAMENTO_DE_55_FPS_MS] * 20)
        assert no_limite.passou(), "18,18 ms é exatamente 55 fps e tem de passar"
        acima = quadros.estatisticas([quadros.ORCAMENTO_DE_55_FPS_MS + 0.5] * 20)
        assert not acima.passou()

    def test_a_fracao_acima_do_orcamento_conta_os_quadros_certos(self) -> None:
        resumo = quadros.estatisticas([10.0] * 15 + [20.0] * 5)
        assert resumo.fracao_acima_de_16ms == pytest.approx(0.25)
        assert resumo.fracao_acima_de_55fps == pytest.approx(0.25)


class TestExecucaoMediana:
    def test_a_mediana_e_uma_execucao_inteira_e_nao_um_frankenstein(self) -> None:
        """O bloco reportado tem de ser uma medição que aconteceu, campo a campo.

        Tirar a mediana de cada métrica separadamente produziria um resumo cuja média vem de uma
        execução e cujo p95 vem de outra -- números que nunca coexistiram, e que por isso ninguém
        consegue reproduzir.
        """
        execucoes = [
            quadros.estatisticas([5.0] * 20),
            quadros.estatisticas([9.0] * 20),
            quadros.estatisticas([7.0] * 20),
        ]
        escolhida = quadros.execucao_mediana(execucoes)
        assert escolhida in execucoes
        assert escolhida.p95_ms == 7.0

    def test_em_numero_par_ganha_a_pior_das_duas_do_meio(self) -> None:
        """O portão não é lugar para arredondar a favor."""
        execucoes = [quadros.estatisticas([float(v)] * 10) for v in (4, 6, 8, 10)]
        assert quadros.execucao_mediana(execucoes).p95_ms == 8.0

    def test_sem_execucao_nenhuma_devolve_o_vazio_que_nao_passa(self) -> None:
        assert not quadros.execucao_mediana([]).passou()


# --------------------------------------------------------------- o bloqueio da interface


class TestAtrasos:
    def test_o_atraso_e_o_vao_menos_o_intervalo_pedido(self) -> None:
        marcas = [0.0, 0.004, 0.008, 0.200]
        atrasos = bloqueio.atrasos(marcas, intervalo_ms=4)
        assert atrasos[:2] == [0.0, 0.0]
        assert atrasos[2] == pytest.approx(188.0, abs=0.1)

    def test_um_disparo_adiantado_nao_vira_atraso_negativo(self) -> None:
        """O relógio do Windows granula em ~0,5 ms, e um negativo somado a um positivo esconde
        metade de um travamento real."""
        assert bloqueio.atrasos([0.0, 0.0035], intervalo_ms=4) == [0.0]

    def test_menos_de_dois_instantes_nao_define_vao_nenhum(self) -> None:
        assert bloqueio.atrasos([1.0]) == []
        assert bloqueio.atrasos([]) == []

    def test_a_lista_viva_e_copiada_antes_de_ser_percorrida(self) -> None:
        """**O defeito que isto fecha derrubava a medição inteira** (F9).

        `marcas_s` costuma ser a lista viva do `Vigia`, e o `QTimer` acrescenta um instante a ela
        durante a leitura: `zip` consome o primeiro argumento preguiçosamente e o segundo é uma
        fatia já congelada. Com `strict=True` o resultado era
        `ValueError: zip() argument 2 is shorter than argument 1` no meio da terceira execução.

        A sequência abaixo cresce enquanto é percorrida, que é exatamente o que a lista viva faz.
        """

        class Crescente(list):
            def __iter__(self):
                for indice, valor in enumerate(list(super().__iter__())):
                    if indice == 1:
                        super().append(valor + 0.004)
                    yield valor

        marcas = Crescente([0.0, 0.004, 0.008])
        assert bloqueio.atrasos(marcas, intervalo_ms=4) == [0.0, 0.0]


class TestResumo:
    def test_uma_operacao_instantanea_passa_e_diz_que_nao_mediu(self) -> None:
        resumo = bloqueio.resumir([], operacao="nada")
        assert resumo.passou()
        assert resumo.pulsos == 1, "quem precisa distinguir 'não travou' de 'não mediu' lê pulsos"

    def test_o_portao_e_o_pior_e_o_total_e_o_que_denuncia_o_fatiamento(self) -> None:
        """Trinta atrasos de 10 ms não violam o piso uma vez e ainda assim são 300 ms pastosos."""
        resumo = bloqueio.resumir([10.0] * 30, piso_ms=16.0)
        assert resumo.passou()
        assert resumo.total_bloqueado_ms == pytest.approx(300.0)
        assert resumo.travamentos == 0

    def test_travamentos_de_so_devolve_o_que_passou_do_piso(self) -> None:
        marcas = [0.0, 0.004, 0.100, 0.104]
        achados = bloqueio.travamentos_de(marcas, intervalo_ms=4, piso_ms=16.0, operacao="x")
        assert len(achados) == 1
        assert achados[0].operacao == "x"
        assert achados[0].duracao_ms == pytest.approx(92.0, abs=0.1)

    def test_piores_ordena_do_maior_para_o_menor(self) -> None:
        travas = [bloqueio.Travamento(duracao_ms=v, quando_s=0.0) for v in (5.0, 90.0, 30.0)]
        assert [t.duracao_ms for t in bloqueio.piores(travas, 2)] == [90.0, 30.0]

    def test_a_referencia_e_publicada_mas_nao_decide_o_veredito(self) -> None:
        """`render_pdf_page` chamado direto mede a thread de trabalho, e não a da interface.

        Desde o passo 15 da OCR_UI o produto nunca rasteriza na thread da janela; a linha continua
        no relatório -- é quanto custa a conta que o filho paga -- e sai de `viola`. Qualquer outra
        operação com o mesmo número continua violando: a exceção é nominal, e só uma.
        """
        pesada = bloqueio.Medicao(operacao=bloqueio.REFERENCIA, resumo=bloqueio.resumir([60.0], piso_ms=16.0))
        linha = bloqueio._consolidar(bloqueio.REFERENCIA, [pesada], 16.0)
        assert linha["referencia"] is True
        assert linha["viola"] is False
        assert linha["pior_ms"] == pytest.approx(60.0)

        outra = bloqueio.Medicao(operacao="abrir PDF", resumo=bloqueio.resumir([60.0], piso_ms=16.0))
        linha = bloqueio._consolidar("abrir PDF", [outra], 16.0)
        assert linha["referencia"] is False
        assert linha["viola"] is True

    def test_o_relato_de_uma_falha_traz_numero_e_pilha(self) -> None:
        """Quem lê a falha é o pytest, e um número sem nome manda alguém procurar."""
        medicao = bloqueio.Medicao(operacao="abrir PDF")
        medicao.resumo = bloqueio.resumir([243.0], operacao="abrir PDF")
        medicao.travamentos = [
            bloqueio.Travamento(duracao_ms=243.0, quando_s=0.0, pilha=("pdf_io.py:186 render",))
        ]
        relato = medicao.relato()
        assert "abrir PDF" in relato
        assert "243" in relato
        assert "pdf_io.py:186 render" in relato


# ------------------------------------------------------------------ o teclado e o nome


class TestTeclado:
    def _controle(self, **kwargs: object) -> teclado.Controle:
        base = {
            "classe": "QPushButton",
            "nome": "Salvar",
            "origem_do_nome": "texto",
            "papel": "Button",
            "alcancado_pelo_tab": True,
        }
        base.update(kwargs)
        return teclado.Controle(**base)  # type: ignore[arg-type]

    def test_um_botao_nomeado_e_alcancado_nao_e_defeito(self) -> None:
        controle = self._controle()
        assert controle.alcancavel() and not controle.anonimo() and not controle.sem_papel()

    def test_o_radio_nao_marcado_e_alcancado_pelas_setas(self) -> None:
        """Um grupo de escolha é **um** ponto de parada do `Tab`, não seis -- é a regra da
        plataforma, e contar os não marcados como inalcançáveis enterraria os defeitos reais."""
        controle = self._controle(
            classe="QRadioButton", papel="RadioButton", alcancado_pelo_tab=False, por_seta=True
        )
        assert controle.alcancavel()

    def test_texto_selecionavel_so_por_ponteiro_nao_e_defeito(self) -> None:
        controle = self._controle(
            classe="QLabel",
            papel="StaticText",
            nome="Detalhes do diagrama",
            alcancado_pelo_tab=False,
            politica="ClickFocus",
        )
        assert controle.so_por_ponteiro() and controle.alcancavel()

    def test_um_botao_so_por_clique_continua_sendo_defeito(self) -> None:
        """A isenção do `ClickFocus` exige **também** o papel não interativo."""
        controle = self._controle(alcancado_pelo_tab=False, politica="ClickFocus")
        assert not controle.so_por_ponteiro() and not controle.alcancavel()

    def test_uma_regiao_nomeada_nao_reprova_pelo_papel(self) -> None:
        """`Pane` nomeado é a região navegável que a WAI-ARIA chama de `region`; anônimo é um
        retângulo que o leitor de tela não sabe descrever. O defeito é o anonimato."""
        nomeada = self._controle(classe="VisorDePagina", papel="Pane", nome="Página do livro")
        anonima = self._controle(classe="VisorDePagina", papel="Pane", nome="")
        assert not nomeada.sem_papel()
        assert anonima.sem_papel() and anonima.anonimo()

    def test_uma_aba_passa_so_quando_a_volta_fecha_e_nada_falta(self) -> None:
        aba = teclado.Aba(nome="Resultado", fechou=True, controles=[self._controle()])
        assert aba.passou()
        aba.fechou = False
        assert not aba.passou(), "uma cadeia de foco que não fecha é um beco"

    def test_o_veredito_reprova_se_uma_unica_aba_reprovar(self) -> None:
        boa = teclado.Aba(nome="a", fechou=True, controles=[self._controle()])
        ma = teclado.Aba(nome="b", fechou=True, controles=[self._controle(nome="")])
        assert teclado.veredito([boa]) == "PASSOU"
        assert teclado.veredito([boa, ma]) == "REPROVOU"


def test_o_orcamento_de_55_fps_nao_foi_arredondado_a_favor() -> None:
    """18,18 ms escrito como divisão, e não como `18.2`.

    Meio ponto de fps de folga que ninguém autorizou é exatamente como um portão numérico
    afrouxa sem que ninguém decida afrouxá-lo.
    """
    assert quadros.ORCAMENTO_DE_55_FPS_MS == 1000.0 / 55.0
    assert not math.isclose(quadros.ORCAMENTO_DE_55_FPS_MS, 18.2, abs_tol=1e-9)


# ------------------------------------------------------ a atribuição do tempo por família


class TestAtribuicao:
    """Somar tempo próprio por família, e dizer **quem desta frente disparou** (F9-C3).

    **O defeito que este bloco existe para impedir de voltar.** `pilha_do_pior` é uma foto: ela
    premia o maior bloco C contíguo e nunca vê custo espalhado. Foi assim que o ciclo 2 publicou
    *"virar de página é `PyMuPDF` de verdade, e `pdf_io` não é desta frente"* enquanto 30 % da
    virada eram 108.620 chamadas Python de `labels.py` disparadas por quatro quadros de `qt/`.
    A foto estava certa; ela só não era a operação inteira, e o portão não tinha a outra metade.
    """

    def _stats(self) -> dict:
        """Um perfil montado à mão: 70 ms de PyMuPDF, 30 ms de `labels.py` chamado por `qt/`.

        As tuplas são as do `cProfile`: `(cc, nc, tottime, cumtime, chamadores)`.
        """
        qt = ("C:/x/src/chess_diagram_ocr/qt/janela.py", 1579, "_aviso_de_treino")
        labels = ("C:/x/src/chess_diagram_ocr/labels.py", 297, "_clean")
        meio = ("C:/x/src/chess_diagram_ocr/labels.py", 380, "_load_rows")
        mupdf = ("~", 0, "<built-in method pymupdf._mupdf.fz_run_display_list>")
        return {
            qt: (1, 1, 0.001, 0.031, {}),
            meio: (1, 1, 0.005, 0.030, {qt: (1, 1, 0.0, 0.030)}),
            labels: (1, 1, 0.024, 0.024, {meio: (1, 1, 0.0, 0.024)}),
            mupdf: (1, 1, 0.070, 0.070, {}),
        }

    def test_a_soma_por_familia_particiona_o_tempo_perfilado(self) -> None:
        """`tottime` não conta ninguém duas vezes -- é o que faz a soma valer como atribuição."""
        saida = bloqueio.atribuir(self._stats())
        assert saida["total_perfilado_ms"] == pytest.approx(100.0)
        assert sum(item["ms"] for item in saida["por_familia"]) == pytest.approx(100.0)

    def test_a_funcao_C_e_classificada_pelo_nome_e_nao_pelo_arquivo(self) -> None:
        """Toda função C aparece como `~:0`. Sem o nome, 94,7 % da virada virava "builtins"."""
        mupdf = "<built-in method pymupdf._mupdf.fz_run_display_list>"
        assert bloqueio.familia("~", mupdf) == "PyMuPDF"
        assert bloqueio.familia("~", "<built-in method nt.stat>") == "pathlib/os (disco)"
        assert bloqueio.familia("~", "<built-in method builtins.len>") == "builtins (C)"

    def test_qt_e_ui_sao_a_familia_desta_frente(self) -> None:
        qt = bloqueio.familia("C:/x/src/chess_diagram_ocr/qt/janela.py")
        ui = bloqueio.familia("C:/x/src/chess_diagram_ocr/ui/busy.py")
        assert (qt, ui) == bloqueio.FAMILIA_DESTA_FRENTE
        assert bloqueio.familia("C:/x/src/chess_diagram_ocr/labels.py") == "tronco (outros)"

    def test_a_funcao_mais_cara_do_tronco_diz_quem_desta_frente_a_disparou(self) -> None:
        """**A metade que faltava.** Sem ela `labels.py` é "do tronco" e a conversa acaba aí."""
        saida = bloqueio.atribuir(self._stats())
        assert "fz_run_display_list" in saida["funcoes_mais_caras"][0]["quem"]
        clean = next(i for i in saida["funcoes_mais_caras"] if "_clean" in i["quem"])
        assert clean["disparada_por"] == "janela.py:1579 _aviso_de_treino"

    def test_quem_nao_tem_chamador_desta_frente_devolve_vazio(self) -> None:
        """Uma operação disparada de fora é resposta legítima -- e é a que o ciclo 2 alegou."""
        mupdf = ("~", 0, "<built-in method pymupdf._mupdf.fz_run_display_list>")
        assert bloqueio.quem_desta_frente_disparou(self._stats(), mupdf) == ""

    def test_um_ciclo_no_grafo_de_chamadas_nao_trava_a_busca(self) -> None:
        a = ("C:/x/a.py", 1, "a")
        b = ("C:/x/b.py", 2, "b")
        estatisticas = {a: (1, 1, 0.1, 0.1, {b: ()}), b: (1, 1, 0.1, 0.1, {a: ()})}
        assert bloqueio.quem_desta_frente_disparou(estatisticas, a) == ""

    def test_a_fracao_desta_frente_e_a_soma_das_duas_familias(self) -> None:
        saida = bloqueio.atribuir(self._stats())
        assert saida["ms_desta_frente"] == pytest.approx(1.0)
        assert saida["fracao_desta_frente"] == pytest.approx(0.01)


# ------------------------------------------ o portão de progresso vê quem não se registra


class TestOperacoesDeFundo:
    """Uma operação que nunca chama `register` era invisível para o portão (F9-C3).

    O inventário devolvia seis linhas com veredito `PASSOU` enquanto duas leituras assíncronas
    rodavam sem progresso e sem cancelamento. A varredura procurava `busy.register`, e quem não
    o chama não aparece numa varredura de `busy.register`.
    """

    def _arvore(self, corpo: str, tmp_path: Path) -> Path:
        """Escreve o módulo falso **e** o `trabalho.py` que declara `class Tarefa(QThread)`.

        A segunda metade não é cenário: é o que faz `Tarefa` ser reconhecida. O detector deixou
        de comparar grafias literais e passou a derivar as classes de thread por **herança**
        (F9-C6), então o `Tarefa` de um módulo só existe se alguém o declarar -- e é assim no
        tronco, onde ele nasce em `qt/trabalho.py` e é construído em cinco outros arquivos.
        """
        pasta = tmp_path / "src" / "chess_diagram_ocr" / "qt"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "trabalho.py").write_text(
            "class Tarefa(QThread):\n    pass\n", encoding="utf-8"
        )
        alvo = pasta / "painel_falso.py"
        alvo.write_text(corpo, encoding="utf-8")
        return alvo

    def _achar(self, corpo: str, tmp_path: Path, declaradas: dict | None = None) -> list:
        alvo = self._arvore(corpo, tmp_path)
        return list(
            progresso._operacoes_de_fundo(
                alvo, tmp_path, declaradas or {}, progresso.classes_de_thread(tmp_path)
            )
        )

    # ------------------------------------------------------ o total conhecido, sem nome nenhum

    def _auditar(self, corpo: str, tmp_path: Path, **kwargs: object) -> list:
        self._arvore(corpo, tmp_path)
        return progresso.auditar(tmp_path, **kwargs)  # type: ignore[arg-type]

    LEITURA = (
        "class PainelFalso:\n"
        "    def _registrar(self):\n"
        "        {nome} = self.contagem_de_amostras()\n"
        "        self._ficha = self._busy_registry.register(\n"
        "            'leitura do dataset',\n"
        "            loses_work=False,\n"
        "            cancellable=True,\n"
        "            cancel=self._cancelar,\n"
        "            detail=f'{{{nome}}} amostra(s)',\n"
        "        )\n"
    )
    """O registro de `qt/painel_do_dataset._registrar_a_leitura` do ciclo 7, com o nome variável.

    Era ele que o crítico usou para mostrar o furo: `f"{quantas} amostra(s)"` dava **0 defeitos**
    e `f"{total} amostra(s)"` dava um **defeito bloqueante** -- mesma tela, mesmo 5431, mesma
    barra andando."""

    @pytest.mark.parametrize("nome", ["quantas", "total", "n", "xyz", "count"])
    def test_o_veredito_do_total_nao_muda_com_o_nome_da_variavel(
        self, nome: str, tmp_path: Path
    ) -> None:
        """**A prova de vida do §4.2 do F9-C7**, e é a que o crítico pediu com todas as letras.

        *"Renomear `quantas` para `n` e o portão continuar acusando."* Com `PISTAS_DE_TOTAL` --
        a régua do ciclo 7, que procurava `("total", "count", …)` no **texto** do `detail=` --
        dois destes cinco nomes acusavam e três não. Hoje os cinco dão a mesma resposta, porque
        o que decide é a **atribuição** (`x = self.contagem_de_amostras()`) e não como ela se
        chama.
        """
        achados = self._auditar(self.LEITURA.format(nome=nome), tmp_path, medir=False)
        leitura = [item for item in achados if item.operacao == "leitura do dataset"]
        assert len(leitura) == 1
        assert leitura[0].total_conhecido, f"o nome {nome!r} apagou a contagem do veredito"
        assert not leitura[0].determinado
        assert leitura[0].bloqueia()
        assert "contagem_de_amostras" in leitura[0].evidencia

    def test_um_detail_interpolado_que_nao_e_contagem_nao_acusa(self, tmp_path: Path) -> None:
        """O outro lado: alargar não pode virar "toda interpolação é um total".

        `qt/painel_de_texto.ler` escreve `detail=f"motor {motor}"` com
        `motor = self._motor` -- um atributo **lido**, não um número calculado. Um portão que o
        acusasse mandaria passar `total=` para uma leitura de folha que não tem total nenhum, e
        portão que grita demais deixa de ser lido.
        """
        corpo = (
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        motor = self._motor\n"
            "        self._ficha = self._busy_registry.register(\n"
            "            'Lendo o texto da folha', loses_work=False, detail=f'motor {motor}'\n"
            "        )\n"
        )
        achados = self._auditar(corpo, tmp_path, medir=False)
        leitura = [item for item in achados if item.especie == "registro"]
        assert len(leitura) == 1
        assert not leitura[0].total_conhecido, leitura[0].evidencia
        assert not leitura[0].bloqueia()

    def test_um_contador_embutido_no_detail_acusa_pela_chamada(self, tmp_path: Path) -> None:
        """`f"{len(rotulos)} imagem(ns)"`: quem decide é a **chamada**, não a palavra "len"."""
        corpo = (
            "class PainelFalso:\n"
            "    def detectar(self):\n"
            "        self._ficha = self._busy_registry.register(\n"
            "            'deteccao', loses_work=False, detail=f'{len(rotulos)} imagem(ns)'\n"
            "        )\n"
        )
        achados = self._auditar(corpo, tmp_path, medir=False)
        registro = next(item for item in achados if item.especie == "registro")
        assert registro.total_conhecido
        assert "chama um contador: len(rotulos)" in registro.evidencia

    def test_a_coluna_determinada_e_a_faixa_do_widget_e_nao_o_argumento(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**A segunda metade do §4.2**: o portão passa a ler a faixa real da barra.

        Antes ele **supunha** que passar `total=` deixava a barra determinada -- uma releitura do
        mesmo código, não uma medida. Aqui o rodapé é sabotado para nunca sair de `(0, 0)`, que é
        a marquise do Qt, e o portão tem de acusar a operação que passa `total=`: a barra anda
        enquanto o programa afirma saber o total, que é exatamente o defeito da carta §3.3.

        Com a régua do ciclo 7 este teste passaria em verde, porque ela lia o argumento e o
        argumento continua lá.

        **E desde o F9-C10 há uma terceira sabotagem**, que é a do §4.2 da crítica do ciclo 9: a
        barra que devolve a **mesma** faixa com e sem ocupação não trocou de modo, e chamá-la de
        determinada é ler o estado inicial do widget.
        """
        corpo = (
            "class PainelFalso:\n"
            "    def exportar(self):\n"
            "        self._ficha = self._busy_registry.register(\n"
            "            'exportacao', loses_work=True, total=289\n"
            "        )\n"
        )
        self._arvore(corpo, tmp_path)

        def faixas(*, com: tuple[int, int], sem: tuple[int, int]) -> None:
            """Sabota a medição da barra **no ponto em que ela é feita hoje**.

            A costura mudou no F9-C10: era `faixas_medidas`, que media duas vezes e resolvia a
            coluna por consulta a esse par; hoje é `faixa_por_operacao`, chamada com o total de
            **cada** operação. Sabotar a costura velha deixaria este teste verde sobre um portão
            que não a usa mais -- que é a forma de cegueira que este arquivo inteiro persegue.
            """
            progresso._FAIXAS_MEDIDAS.clear()
            monkeypatch.setattr(
                progresso,
                "faixa_da_barra_do_rodape",
                lambda total, _raiz=None: com if total else sem,
            )

        faixas(com=(0, 100), sem=(0, 0))
        sadio = next(i for i in progresso.auditar(tmp_path) if i.especie == "registro")
        assert sadio.determinado
        assert "min=0 max=100" in sadio.evidencia and "DETERMINADA" in sadio.evidencia
        assert "a barra TROCOU de modo" in sadio.evidencia
        assert not sadio.bloqueia()

        faixas(com=(0, 0), sem=(0, 0))
        doente = next(i for i in progresso.auditar(tmp_path) if i.especie == "registro")
        assert not doente.determinado, "o portao leu o argumento total= em vez da faixa da barra"
        assert doente.total_conhecido and doente.bloqueia()
        assert "min=0 max=0" in doente.evidencia and "INDETERMINADA" in doente.evidencia

        # **A terceira sabotagem, e ela é o §4.2 da crítica do ciclo 9.** Uma barra que fica em
        # `(0, 100)` para **toda** ocupação não trocou de modo: ela está no estado que
        # `RodapeDaJanela.__init__` deixou. A régua antiga a chamava de determinada -- e é por
        # isso que adiar `_trocar_modo_da_barra` por um tique apagava o portão inteiro.
        faixas(com=(0, 100), sem=(0, 100))
        parada = next(i for i in progresso.auditar(tmp_path) if i.especie == "registro")
        assert not parada.determinado, (
            "a barra devolveu a mesma faixa com e sem ocupacao -- ela nao troca de modo, "
            "e o portao a chamou de determinada"
        )
        assert parada.total_conhecido and parada.bloqueia()
        assert "a barra NAO trocou de modo" in parada.evidencia
        progresso._FAIXAS_MEDIDAS.clear()

    def test_sem_binding_do_qt_a_faixa_e_declarada_como_nao_medida(self, tmp_path: Path) -> None:
        """`medir=False` é o estado da nossa venv, e ele **se declara** em vez de fingir medida."""
        corpo = (
            "class PainelFalso:\n"
            "    def exportar(self):\n"
            "        self._ficha = self._busy_registry.register(\n"
            "            'exportacao', loses_work=True, total=289\n"
            "        )\n"
        )
        registro = next(
            i for i in self._auditar(corpo, tmp_path, medir=False) if i.especie == "registro"
        )
        assert registro.determinado
        assert "faixa NAO medida" in registro.evidencia

    def test_uma_thread_sem_registro_e_sem_declaracao_bloqueia(self, tmp_path: Path) -> None:
        corpo = (
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        tarefa = Tarefa(lambda: 1, nome='x')\n"
            "        tarefa.start()\n"
        )
        achados = self._achar(corpo, tmp_path)
        assert [item.invisivel for item in achados] == [True]
        assert achados[0].bloqueia()
        assert "INVISIVEL" in achados[0].evidencia

    def test_uma_thread_que_registra_nao_bloqueia(self, tmp_path: Path) -> None:
        """Registro de verdade: `X.register(...)` num receptor de ocupação.

        **Era `self._registrar_a_leitura()` sem corpo nenhum**, e passava -- porque a régua
        antiga aceitava qualquer nome contendo `registrar`. Trocar por uma chamada real deixa o
        teste **mais** estrito, não menos: ele agora afirma o que o rodapé de fato observa.
        """
        corpo = (
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        self._busy.register('ler', loses_work=False)\n"
            "        Tarefa(lambda: 1, nome='x').start()\n"
        )
        achados = self._achar(corpo, tmp_path)
        assert not achados[0].invisivel and not achados[0].bloqueia()

    def test_o_registro_por_ajudante_do_mesmo_modulo_continua_valendo(self, tmp_path: Path) -> None:
        """A Galeria e a aba de Texto registram por `_registrar_ocupado`, e isso tem de contar.

        A prova é a **definição** do ajudante, e não o nome dele: seguir o corpo é o que separa
        este caso do `_registrar_atalho_de_teclado` do teste seguinte.
        """
        corpo = (
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        self._registrar_ocupado('ler')\n"
            "        Tarefa(lambda: 1, nome='x').start()\n"
            "\n"
            "    def _registrar_ocupado(self, nome):\n"
            "        return self._busy.register(nome, loses_work=False)\n"
        )
        achados = self._achar(corpo, tmp_path)
        assert not achados[0].invisivel

    def test_registrar_qualquer_coisa_nao_conta_como_registrar_ocupacao(
        self, tmp_path: Path
    ) -> None:
        """A forma (f) da sabotagem do ciclo 5: `registrar` que não registra ocupação.

        O crítico plantou `self._registrar_atalho_de_teclado()` ao lado de uma thread crua e o
        portão a marcou **REGISTRADA**. Não é hipótese: `qt/` tem hoje `historico.registrar`,
        `_historico.registrar` e `_mapa.registrar`, três `registrar` sem relação com ocupação.
        """
        corpo = (
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        self._registrar_atalho_de_teclado()\n"
            "        self.historico.registrar('x')\n"
            "        Tarefa(lambda: 1, nome='x').start()\n"
            "\n"
            "    def _registrar_atalho_de_teclado(self):\n"
            "        return None\n"
        )
        achados = self._achar(corpo, tmp_path)
        assert achados[0].invisivel and achados[0].bloqueia()

    def test_as_seis_formas_de_abrir_thread_sao_todas_vistas(self, tmp_path: Path) -> None:
        """**A prova de vida do detector** -- a sabotagem do §5 do ciclo 5, aqui dentro.

        Das seis operações de fundo que o crítico plantou, o detector antigo achou **uma**,
        marcou **uma** como registrada sem registro nenhum e não viu **quatro**, porque
        `FORMAS_DE_THREAD` comparava `ast.unparse(no.func)` com duas grafias literais. Um portão
        novo sem sabotagem é uma promessa; esta é a cobrança.
        """
        corpo = (
            "import threading\n"
            "from concurrent.futures import ThreadPoolExecutor\n"
            "from threading import Thread\n"
            "\n"
            "class PainelFalso:\n"
            "    def a_thread_crua(self):\n"
            "        threading.Thread(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def b_import_direto(self):\n"
            "        Thread(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def c_pool(self):\n"
            "        ThreadPoolExecutor(max_workers=1).submit(self._ler)\n"
            "\n"
            "    def d_timer(self):\n"
            "        threading.Timer(0.0, self._ler).start()\n"
            "\n"
            "    def e_subclasse(self):\n"
            "        _MinhaThread().start()\n"
            "\n"
            "    def f_registro_de_mentira(self):\n"
            "        self._registrar_atalho_de_teclado()\n"
            "        threading.Thread(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def _registrar_atalho_de_teclado(self):\n"
            "        return None\n"
            "\n"
            "    def _ler(self):\n"
            "        return None\n"
            "\n"
            "class _MinhaThread(threading.Thread):\n"
            "    def run(self):\n"
            "        return None\n"
        )
        achados = self._achar(corpo, tmp_path)
        donas = sorted(item.operacao.split(".", 1)[1].split(":")[0] for item in achados)
        assert donas == [
            "a_thread_crua",
            "b_import_direto",
            "c_pool",
            "d_timer",
            "e_subclasse",
            "f_registro_de_mentira",
        ], f"o detector deixou de ver uma forma: {donas}"
        assert [item.invisivel for item in achados] == [True] * 6
        assert len(progresso.bloqueantes(achados)) == 6

    def test_as_oito_formas_do_ciclo_6_tambem_sao_vistas(self, tmp_path: Path) -> None:
        """**A segunda prova de vida** -- sabotagem própria, contra o detector já alargado.

        Um portão que só passa na sabotagem que motivou o conserto não foi testado, foi
        ajustado. Então, fechadas as seis formas do ciclo 5, escrevi oito novas contra o
        detector novo e rodei: **três passaram** -- `from threading import Thread as T`
        (o termo final é `T`), `class _Derivada(T)` (a herança segue o nome da base, que também
        é `T`) e `QThreadPool.globalInstance().start(tarefa)`, a única forma de enfileirar um
        `QRunnable` no Qt. `apelidos_de_thread` e `RECEPTORES_DE_POOL` são o conserto dessas
        três; as outras cinco já eram vistas e ficam aqui para não regredirem.
        """
        corpo = (
            "import asyncio\n"
            "import multiprocessing\n"
            "import threading\n"
            "from concurrent.futures import ProcessPoolExecutor\n"
            "from threading import Thread as T\n"
            "\n"
            "class _Derivada(T):\n"
            "    def run(self):\n"
            "        return None\n"
            "\n"
            "class PainelFalso:\n"
            "    def g_alias_de_import(self):\n"
            "        T(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def h_modulo_aliasado(self):\n"
            "        import threading as th\n"
            "        th.Thread(target=self._ler).start()\n"
            "\n"
            "    def i_processo(self):\n"
            "        multiprocessing.Process(target=self._ler).start()\n"
            "\n"
            "    def j_pool_de_processo(self):\n"
            "        ProcessPoolExecutor(max_workers=1).submit(self._ler)\n"
            "\n"
            "    def k_executor_do_asyncio(self):\n"
            "        asyncio.get_event_loop().run_in_executor(None, self._ler)\n"
            "\n"
            "    def l_subclasse_de_alias(self):\n"
            "        _Derivada().start()\n"
            "\n"
            "    def m_qthreadpool(self):\n"
            "        QThreadPool.globalInstance().start(self._tarefa)\n"
            "\n"
            "    def n_registro_de_outro_modulo(self):\n"
            "        self._mapa.registrar('x')\n"
            "        threading.Thread(target=self._ler).start()\n"
            "\n"
            "    def _ler(self):\n"
            "        return None\n"
        )
        achados = self._achar(corpo, tmp_path)
        donas = sorted(item.operacao.split(".", 1)[1].split(":")[0] for item in achados)
        assert donas == [
            "g_alias_de_import",
            "h_modulo_aliasado",
            "i_processo",
            "j_pool_de_processo",
            "k_executor_do_asyncio",
            "l_subclasse_de_alias",
            "m_qthreadpool",
            "n_registro_de_outro_modulo",
        ], f"o detector deixou de ver uma forma: {donas}"
        assert [item.invisivel for item in achados] == [True] * 8
        assert len(progresso.bloqueantes(achados)) == 8

    def test_as_oito_formas_do_critico_do_ciclo_7_sao_vistas_pelo_nome_da_funcao(
        self, tmp_path: Path
    ) -> None:
        """**Sete das oito escapavam**, e as duas que apareciam apareciam no nome errado.

        O crítico do ciclo 7 plantou oito formas contra o detector já alargado no ciclo 6 e
        publicou o placar: **uma** nomeada (o `import` dinâmico), **cinco** sem rastro nenhum e
        **duas** aparecendo só pela construção que o `__init__` fazia -- e *"uma linha dizendo
        `__init__ constroi QThread` não diz que `e_move_to_thread` é uma operação de fundo"*.

        Por isso a asserção é sobre o **nome da função dona**, e não sobre a contagem: as oito
        têm de aparecer cada uma na sua. O `__init__`, que constrói o pool e o `QThread`, também
        aparece, e é honesto que apareça -- ele abre duas linhas de execução.
        """
        corpo = (
            "import asyncio\n"
            "import functools\n"
            "import importlib\n"
            "import subprocess\n"
            "import threading\n"
            "\n"
            "class PainelFalso:\n"
            "    def a_apelido_por_atribuicao(self):\n"
            "        Fabrica = threading.Thread\n"
            "        Fabrica(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def b_partial(self):\n"
            "        abrir = functools.partial(threading.Thread, target=self._ler)\n"
            "        abrir().start()\n"
            "\n"
            "    def c_map_no_pool(self):\n"
            "        list(self._pool.map(self._ler_de, range(200)))\n"
            "\n"
            "    def d_to_thread(self):\n"
            "        asyncio.run(asyncio.to_thread(self._ler))\n"
            "\n"
            "    def e_move_to_thread(self):\n"
            "        trabalhador = object()\n"
            "        trabalhador.moveToThread(self._fio)\n"
            "\n"
            "    def f_popen(self):\n"
            "        subprocess.Popen(['python', '-c', 'pass'])\n"
            "\n"
            "    def g_qprocess(self):\n"
            "        QProcess(self).start('python', ['-c', 'pass'])\n"
            "\n"
            "    def h_import_dinamico(self):\n"
            "        mod = importlib.import_module('threading')\n"
            "        mod.Thread(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def _ler(self):\n"
            "        return None\n"
            "\n"
            "    def _ler_de(self, i):\n"
            "        return i\n"
        )
        achados = self._achar(corpo, tmp_path)
        donas = sorted(item.operacao.split(".", 1)[1].split(":")[0] for item in achados)
        assert donas == [
            "a_apelido_por_atribuicao",
            "b_partial",
            "c_map_no_pool",
            "d_to_thread",
            "e_move_to_thread",
            "f_popen",
            "g_qprocess",
            "h_import_dinamico",
        ], f"o detector deixou de ver uma forma do critico do ciclo 7: {donas}"

    def test_as_oito_formas_do_ciclo_8_tambem_sao_vistas(self, tmp_path: Path) -> None:
        """**A terceira prova de vida** -- oito formas contra o detector alargado neste ciclo.

        Sete passaram na primeira execução, e a oitava (`f`) só não passou porque o apelido por
        atribuição já tinha entrado por causa da sabotagem do crítico. É a razão de a catraca
        existir: fechar a sabotagem que motivou o conserto não é ter testado o detector.

        A árvore completa, com os três controles negativos, está em
        `benchmarks/reports/ui/c8/sab_c8/`, ao lado das do ciclo 5 e do ciclo 7.
        """
        corpo = (
            "import asyncio\n"
            "import os\n"
            "import threading\n"
            "from multiprocessing.pool import ThreadPool\n"
            "\n"
            "class PainelFalso:\n"
            "    FABRICA = threading.Thread\n"
            "    FABRICAS = {'fundo': threading.Thread}\n"
            "\n"
            "    def a_fabrica_num_dicionario(self):\n"
            "        self.FABRICAS['fundo'](target=self._ler, daemon=True).start()\n"
            "\n"
            "    def b_thread_pool_do_multiprocessing(self):\n"
            "        ThreadPool(4).close()\n"
            "\n"
            "    def c_create_task(self):\n"
            "        asyncio.create_task(self._corrotina())\n"
            "\n"
            "    def d_run_coroutine_threadsafe(self):\n"
            "        asyncio.run_coroutine_threadsafe(self._corrotina(), self._laco)\n"
            "\n"
            "    def e_try_start_no_pool_do_qt(self):\n"
            "        QThreadPool.globalInstance().tryStart(self._ler)\n"
            "\n"
            "    def f_apelido_de_atributo_de_classe(self):\n"
            "        self.FABRICA(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def g_startfile(self):\n"
            "        os.startfile('relatorio.pdf')\n"
            "\n"
            "    def h_getattr_no_modulo(self):\n"
            "        getattr(threading, 'Thread')(target=self._ler, daemon=True).start()\n"
            "\n"
            "    def _ler(self):\n"
            "        return None\n"
        )
        achados = self._achar(corpo, tmp_path)
        donas = sorted(item.operacao.split(".", 1)[1].split(":")[0] for item in achados)
        assert donas == [
            "a_fabrica_num_dicionario",
            "b_thread_pool_do_multiprocessing",
            "c_create_task",
            "d_run_coroutine_threadsafe",
            "e_try_start_no_pool_do_qt",
            "f_apelido_de_atributo_de_classe",
            "g_startfile",
            "h_getattr_no_modulo",
        ], f"o detector deixou de ver uma forma do ciclo 8: {donas}"
        assert len(progresso.bloqueantes(achados)) == 8

    def test_os_controles_negativos_do_ciclo_8_nao_sao_acusados(self, tmp_path: Path) -> None:
        """O outro lado de alargar: `map`, `partial` e um relógio comuns não são thread.

        Sem este teste, alargar o detector é grátis. `map` ficou **fora** de
        `METODOS_DE_SUBMISSAO` de propósito e entrou em `METODOS_DE_POOL`, onde ele só conta com
        receptor de pool; `partial` só conta com classe de thread no primeiro argumento -- e
        `qt/painel_da_galeria.py` tem dez `partial(self._ir, …)` que não podem acusar.
        """
        corpo = (
            "from functools import partial\n"
            "\n"
            "class PainelFalso:\n"
            "    def ligar(self):\n"
            "        self._relogio.start(250)\n"
            "        linhas = list(map(str, range(10)))\n"
            "        return partial(self._ir, 1), linhas\n"
        )
        assert self._achar(corpo, tmp_path) == []

    def test_o_start_de_um_relogio_nao_e_operacao_de_fundo(self, tmp_path: Path) -> None:
        """A regra do `start` pede pool **e** argumento -- senão ela acusa `qt/` inteiro.

        `self._relogio.start(250)` tem argumento e não é thread; `Tarefa(...).start()` é thread
        e já foi contada na construção -- contá-la de novo infla o placar, que é o defeito que
        `test_uma_linha_conta_uma_operacao_so` cobra do outro lado. Portão que grita demais
        deixa de ser lido, que é a outra forma de ficar cego.
        """
        corpo = (
            "class PainelFalso:\n"
            "    def ligar(self):\n"
            "        self._relogio.start(250)\n"
            "        self._animacao.start()\n"
            "        self._pool.start()\n"
        )
        assert self._achar(corpo, tmp_path) == []

    def test_uma_linha_conta_uma_operacao_so(self, tmp_path: Path) -> None:
        """`ThreadPoolExecutor(1).submit(f)` casa com as duas regras e é a mesma thread.

        Um portão que inflasse o próprio placar seria tão pouco confiável quanto um cego.
        """
        corpo = (
            "from concurrent.futures import ThreadPoolExecutor\n"
            "\n"
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        ThreadPoolExecutor(max_workers=1).submit(self._ler)\n"
        )
        achados = self._achar(corpo, tmp_path)
        assert len(achados) == 1

    def test_uma_thread_declarada_nao_bloqueia_e_o_motivo_aparece(self, tmp_path: Path) -> None:
        corpo = (
            "class PainelFalso:\n"
            "    def ler(self):\n"
            "        threading.Thread(target=lambda: 1).start()\n"
        )
        motivo = "e derivada: refazer recomputa a mesma resposta"
        declaradas = {("painel_falso.py", "ler"): motivo}
        achados = self._achar(corpo, tmp_path, declaradas)
        assert not achados[0].bloqueia()
        assert motivo in achados[0].evidencia

    def test_a_declaracao_e_lida_do_produto_e_nao_copiada(self, tmp_path: Path) -> None:
        """Uma cópia daria um arnês aprovando exceção que o produto já tirou -- e vice-versa."""
        pasta = tmp_path / "src" / "chess_diagram_ocr" / "ui"
        pasta.mkdir(parents=True, exist_ok=True)
        declaracao = 'FORA_DO_REGISTRO: dict[tuple[str, str], str] = {("a.py", "b"): "porque"}\n'
        (pasta / "busy.py").write_text(declaracao, encoding="utf-8")
        assert progresso._fora_do_registro(tmp_path) == {("a.py", "b"): "porque"}

    def test_sem_o_tronco_a_tabela_e_vazia_e_o_portao_fica_estrito(self, tmp_path: Path) -> None:
        """Falhar para o lado de acusar: uma tabela que não foi achada não absolve ninguém."""
        assert progresso._fora_do_registro(tmp_path) == {}


# ---------------------------------------------- o quinto motivo: prosa não é nome (F9-C3)


class TestNomeQueEProsa:
    """Um nome acessível que é uma frase de ajuda não nomeia coisa nenhuma.

    **O defeito estava nas seis abas e os quatro motivos anteriores o aprovavam.** O `QComboBox`
    de regime não tinha `accessibleName`, a cascata caiu na dica, e o leitor de tela anunciava
    -- no 14º lugar da ordem do `Tab` de todas as abas -- 67 caracteres terminando em "separa as",
    cortados no meio da frase pelo Qt. Aquele nome tem letras, é único na aba, não é o valor do
    controle e não é eco do papel: os quatro motivos passavam por ele.
    """

    def _controle(self, nome: str) -> teclado.Controle:
        return teclado.Controle(
            classe="QComboBox",
            nome=nome,
            origem_do_nome="dica",
            papel="ComboBox",
            alcancado_pelo_tab=True,
        )

    def test_a_frase_truncada_do_regime_e_acusada(self) -> None:
        """O caso literal, com o texto que a janela anunciava."""
        nome = "Em que condição esta página foi lida. Entra na anotação e separa as"
        assert self._controle(nome).nome_vazio_de_sentido() == "e prosa, nao nome"

    def test_duas_oracoes_sao_prosa_em_qualquer_comprimento(self) -> None:
        """O ponto seguido de espaço é o sinal forte: um nome não tem duas orações."""
        assert self._controle("Abre. Fecha").nome_vazio_de_sentido() == "e prosa, nao nome"

    def test_o_comprimento_sozinho_basta(self) -> None:
        """A frase do regime chega **sem** ponto final, porque o Qt a cortou antes dele."""
        longo = "Marcar o que o léxico não conhece e depois conferir tudo de novo"
        assert len(longo) > teclado.LETRAS_MAXIMAS_DE_UM_NOME
        assert self._controle(longo).nome_vazio_de_sentido() == "e prosa, nao nome"

    def test_o_nome_verdadeiro_mais_longo_da_janela_passa(self) -> None:
        """O teto foi posto **acima** do nome legítimo mais longo que a janela tem hoje.

        Um portão que reprovasse `"Varrer o livro para encher a galeria"` -- que diz o que o
        controle faz, com objeto direto -- estaria medindo comprimento em vez de significado.
        """
        nome = "Varrer o livro para encher a galeria"
        assert len(nome) <= teclado.LETRAS_MAXIMAS_DE_UM_NOME
        assert self._controle(nome).nome_vazio_de_sentido() == ""

    def test_uma_abreviacao_com_ponto_no_fim_nao_e_prosa(self) -> None:
        """`"Conf. min"` tem ponto e não tem duas orações -- o sinal é o ponto **e o espaço**."""
        assert self._controle("Conf. min").nome_vazio_de_sentido() == "e prosa, nao nome"
        assert self._controle("Prio.").nome_vazio_de_sentido() == ""

    def test_a_ordem_dos_motivos_poe_a_prosa_por_ultimo(self) -> None:
        """Um nome que é o valor do controle já é errado antes de alguém medir o tamanho dele."""
        controle = teclado.Controle(
            classe="QLineEdit",
            nome="Em que condição esta página foi lida. Entra na anotação e separa as",
            origem_do_nome="texto",
            papel="Text",
            alcancado_pelo_tab=True,
        )
        assert controle.nome_vazio_de_sentido() == "o valor do proprio controle"


# ------------------------------------------- a largura da medição (F9-C9: a cegueira de escopo)


class TestTodasAsPeles:
    """**Nenhum portão desta frente pode medir uma pele das três.**

    O ciclo 9 reprovou por isto e só por isto: o portão de teclado publicava
    `216 focáveis, 0 sem nome, PASSOU` medindo a `classica`, e o mesmo comando devolvia
    `REPROVOU` com 2 defeitos na `foco` e **36** na `fita` -- controles que chegavam ao leitor de
    tela como `-`, `+`, `◀`, `▶`, `|◀`, `▶|`, que é o defeito nº 1 do ciclo 1 desta frente. E
    `capture.PELES` listava duas das três, então **nenhum instrumento visual desta frente jamais
    fotografou a `fita`**, onde o defeito morava.

    A resposta não é acrescentar `"fita"` a duas listas: é cada lista sair de `ui/pele.PELES`, e
    estes testes falharem no dia em que alguém registrar a quarta pele sem vir aqui.
    """

    def peles_do_produto(self) -> list[str]:
        return teclado.peles_registradas()

    def test_o_portao_de_teclado_percorre_as_peles_do_produto(self) -> None:
        do_produto = self.peles_do_produto()
        assert len(do_produto) >= 3, "o produto registra menos peles do que o ciclo 9 media"
        assert "fita" in do_produto

    def test_a_captura_cobre_toda_pele_registrada(self) -> None:
        """`capture.PELES` listava `classica` e `foco`. A `fita` é a única que muda a **densidade**
        (`COMPACTA`), que é o eixo do item "espaçamento inconsistente entre elementos
        equivalentes" da carta -- e era a que ninguém fotografava."""
        fotografadas = {nome for nome, _rotulo in capture.PELES}
        assert fotografadas == set(self.peles_do_produto())

    def test_cada_pele_tem_um_rotulo_de_arquivo_proprio(self) -> None:
        """Dois rótulos iguais gravariam duas peles no mesmo nome, e a segunda apagaria a
        primeira em silêncio -- que é a forma de perda que já custou 17 capturas nesta frente."""
        rotulos = [rotulo for _nome, rotulo in capture.PELES]
        assert len(set(rotulos)) == len(rotulos)

    def test_o_4k_esta_nos_tamanhos(self) -> None:
        """A carta §3.2 pede "800×600 e 4K"; oito ciclos mediram até 1920. O crítico do ciclo 9
        abriu a 3840 com instrumento próprio e achou **1 569,6 kpx** de vazio na Estudo, contra
        281,5 a 1920. Um número desses não pode depender de um instrumento fora do arnês."""
        assert (3840, 2160) in capture.TAMANHOS


class TestNomeQualificado:
    """O anúncio é o grupo **e** o nome, e é contra ele que "repetido na aba" mede (F9-C10).

    **Por que a régua mudou, e por que ela não afrouxou.** O produto declara este modelo desde o
    ciclo 2, no docstring de `qt/painel_do_pdf._bloco`: *"o nome do bloco é o que um leitor de
    tela anuncia ao entrar nele"*. O portão comparava só a segunda metade do anúncio. Com o
    `setAccessibleName` que este ciclo pôs na fita, os onze comandos que ela repete da barra do
    visor passaram a bater nome a nome -- e eles **são** o mesmo comando desenhado em dois lugares
    de propósito, um no cromo e um no painel, cada um dentro de um grupo com nome próprio.

    A régua nova cobra do produto **uma coisa a mais**: nomear os grupos. Dois controles com o
    mesmo nome dentro do mesmo grupo continuam reprovando, e um controle sem grupo nomeado
    continua sendo comparado pelo nome cru.
    """

    def _controle(self, nome: str, grupo: str = "") -> teclado.Controle:
        return teclado.Controle(
            classe="QPushButton",
            nome=nome,
            origem_do_nome="accessibleName",
            papel="Button",
            alcancado_pelo_tab=True,
            grupo=grupo,
        )

    def test_o_anuncio_junta_grupo_e_nome(self) -> None:
        assert self._controle("Página anterior", "Navegar").nome_qualificado() == (
            "Navegar: Página anterior"
        )
        assert self._controle("Página anterior").nome_qualificado() == "Página anterior"

    def test_dois_iguais_no_mesmo_grupo_continuam_reprovando(self) -> None:
        """É o caso do ciclo 2: três `"Escolha"` na aba Dataset, três coisas diferentes."""
        aba = teclado.Aba(
            nome="Dataset",
            fechou=True,
            controles=[self._controle("Escolha", "Filtros") for _ in range(3)],
        )
        assert aba.repetidos() == ["Filtros: Escolha"]
        assert len(aba.nomes_vazios()) == 3
        assert not aba.passou()

    def test_tres_iguais_sem_grupo_nenhum_continuam_reprovando(self) -> None:
        aba = teclado.Aba(
            nome="Dataset", fechou=True, controles=[self._controle("Escolha") for _ in range(3)]
        )
        assert aba.repetidos() == ["Escolha"]
        assert len(aba.nomes_vazios()) == 3

    def test_o_mesmo_comando_em_dois_grupos_nomeados_passa(self) -> None:
        """A pílula do cromo e o botão do painel: o mesmo comando, dois lugares, dois grupos.

        Um leitor de tela anuncia `"Ações em destaque, grupo"` antes de uma e `"Reconhecer,
        grupo"` antes da outra, que é exatamente a informação que distingue as duas para quem
        ouve -- e a que quem vê recebe da posição na tela.
        """
        aba = teclado.Aba(
            nome="Galeria",
            fechou=True,
            controles=[
                self._controle("Ler esta página", "Ações em destaque"),
                self._controle("Ler esta página", "Reconhecer"),
            ],
        )
        assert aba.repetidos() == []
        assert aba.nomes_vazios() == []
        assert aba.passou()

    def test_um_grupo_nomeado_e_outro_anonimo_ainda_passam(self) -> None:
        """Só um dos dois lados precisa dizer onde está para o anúncio deixar de ser o mesmo."""
        aba = teclado.Aba(
            nome="Galeria",
            fechou=True,
            controles=[
                self._controle("Próximo diagrama"),
                self._controle("Próximo diagrama", "Áreas de trabalho"),
            ],
        )
        assert aba.repetidos() == []


class TestQuebraDeLinhaNoNome:
    """Uma quebra de linha num nome acessível é o **leiaute vazando para o anúncio** (F9-C10).

    **Este motivo entrou porque a prova de vida do ciclo 10 o cobrou.** Sabotei a fita apagando o
    `setAccessibleName` -- que é o defeito do ciclo 9 reposto -- e o portão continuou verde: sem
    nome próprio a cascata cai no `text()`, e o texto de um botão da fita é
    `quebrar_rotulo("Abrir PDF")` = `"Abrir\nPDF"`. Aquilo tem letras, é único, não é o valor do
    controle e não é prosa. E **não bate** com `"Abrir PDF"`, então nem repetido ficava -- que é
    o mesmo mascaramento que escondia os onze nomes duplicados da fita.

    Com o motivo, a mesma sabotagem devolve **90 controles** acusados na pele `fita`.
    """

    def _controle(self, nome: str) -> teclado.Controle:
        return teclado.Controle(
            classe="QToolButton",
            nome=nome,
            origem_do_nome="texto",
            papel="Button",
            alcancado_pelo_tab=True,
        )

    def test_o_rotulo_quebrado_em_duas_linhas_e_acusado(self) -> None:
        assert self._controle("Abrir\nPDF").nome_vazio_de_sentido() == "quebra de linha no nome"

    def test_o_retorno_de_carro_tambem(self) -> None:
        assert self._controle("Abrir\r\nPDF").nome_vazio_de_sentido() == "quebra de linha no nome"

    def test_o_mesmo_nome_sem_quebra_passa(self) -> None:
        assert self._controle("Abrir PDF").nome_vazio_de_sentido() == ""

    def test_a_lista_de_motivos_esta_fechada_e_declarada(self) -> None:
        """Um motivo que o código usa e a lista não declara é um portão que reprova por uma razão
        que o relatório não sabe nomear."""
        usados = {
            teclado.Controle(
                classe="QToolButton",
                nome=nome,
                origem_do_nome=origem,
                papel=papel,
                alcancado_pelo_tab=True,
            ).nome_vazio_de_sentido(repetidos)
            for nome, origem, papel, repetidos in (
                ("Botão", "accessibleName", "Button", ()),
                ("+", "texto", "Button", ()),
                ("Salvar", "accessibleName", "Button", ("Salvar",)),
                ("Abrir\nPDF", "texto", "Button", ()),
                ("Abre. Fecha", "dica", "Button", ()),
            )
        }
        assert usados - {""} <= set(teclado.MOTIVOS_DE_NOME_VAZIO)


class TestNenhumPortaoEscreveNaSessaoDeQuemORoda:
    """A certidão de higiene virou teste, e passou a conferir o arquivo certo (F9-C12).

    **O ciclo 10 certificou o arquivo errado.** O relatório dizia *"o
    `data/app_tkinter_state.json` do tronco continua com `mtime` 13:25"* -- e é verdade, e é o
    estado do **Tk**, de um frontend cortado em 2026-08-31. O estado da janela **Qt** é o
    `data/janela.json` que `qt/janela.py` declara em `CAMINHO_DO_ESTADO`, e é ele que guarda
    `last_pdf`, `last_page`, `pdf_zoom`, `pdf_enquadramento`, `board_zoom` e `pdf_history`.

    O crítico do ciclo 11 achou o que a certidão não viu: `caissa.ui.audit.bloqueio` construía
    `JanelaPrincipal()` **sem argumento** em dois lugares, e depois de três execuções o
    `data/janela.json` dele estava com `last_pdf = 1937 Kemeri.pdf`, `last_page = 120` e o zoom
    da corrida. Ele mediu se o número dependia disso -- **não depende**, 204 ms com o estado
    envenenado contra 207/212/205 ms com o herdado --, e por isso o defeito é de higiene e não
    de medição. O que não podia continuar é o portão estragando a sessão de quem o roda.

    **Uma frase num relatório certifica uma vez; um teste certifica todo dia.** Este lê os
    módulos do arnês e reprova a construção que não redirecionar -- inclusive a que alguém
    escrever no ciclo que vem.
    """

    def modulos_do_arnes(self) -> list[Path]:
        pasta = Path(teclado.__file__).parent
        return sorted(pasta.glob("*.py"))

    def test_toda_construcao_de_janela_redireciona_o_estado(self) -> None:
        culpados: list[str] = []
        for arquivo in self.modulos_do_arnes():
            fonte = arquivo.read_text(encoding="utf-8")
            for numero, linha in enumerate(fonte.splitlines(), start=1):
                if "JanelaPrincipal(" not in linha or linha.lstrip().startswith("#"):
                    continue
                if "caminho_do_estado" not in linha:
                    culpados.append(f"{arquivo.name}:{numero}: {linha.strip()}")
        assert culpados == [], (
            "portão construindo a janela sem estado próprio (ver capture.estado_de_medicao): "
            + "; ".join(culpados)
        )

    def test_a_certidao_nomeia_o_arquivo_da_janela_qt(self) -> None:
        """O que a certidão do ciclo 10 não fazia: dizer qual arquivo é o da janela Qt."""
        fonte = Path(capture.__file__).read_text(encoding="utf-8")
        assert "data/janela.json" in fonte
        assert "CAMINHO_DO_ESTADO" in fonte

    def test_o_produto_continua_declarando_esse_caminho(self, raiz_do_tronco: Path) -> None:
        """Se o produto trocar de arquivo de estado, esta certidão passa a apontar para o
        lugar errado -- e é exatamente assim que a do ciclo 10 ficou desatualizada."""
        janela = raiz_do_tronco / "src" / "chess_diagram_ocr" / "qt" / "janela.py"
        fonte = janela.read_text(encoding="utf-8")
        assert 'CAMINHO_DO_ESTADO = PROJECT_ROOT / "data" / "janela.json"' in fonte


class TestTodasAsDensidades:
    """**O terceiro eixo, e ele custou um número no ciclo 11** (F9-C12).

    `Ver ▸ Aparência` oferece **três peles × duas densidades = seis arranjos**. Os portões desta
    frente mediam **três** -- cada pele na densidade que ela sugere --, e publicavam o número
    como se fosse da superfície inteira. O crítico do ciclo 11 rodou o censo de ícones com
    `CVOFF_DENSITY=confortavel` e achou o que faltava: na `fita`, a amplitude da caixa do ícone
    é **2×17 px** contra os **0×11 px** publicados, e a família só-de-ícone deixa de ter caixa
    única (**1×1 px**).

    O eixo não escondia bloqueante -- os três arranjos não medidos devolvem 216 / 240 / 360 e
    `PASSOU`, à unidade --, mas um portão que publica um número de metade da superfície é o
    defeito do ciclo 9 num eixo novo. E a resposta é a mesma: a lista sai do produto.

    **O portão de contraste já fazia isto desde o ciclo 10**, e o crítico registrou que ele era
    o modelo a copiar. Estes testes cobram a cópia.
    """

    def test_o_portao_de_teclado_le_as_densidades_do_produto(self) -> None:
        from chess_diagram_ocr.ui import pele

        assert teclado.densidades_registradas() == list(pele.DENSIDADES)
        assert len(pele.DENSIDADES) >= 2

    def test_o_laco_cruza_pele_com_densidade(self) -> None:
        """Seis arranjos, e não três: o laço tem de ser um produto cartesiano."""
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        assert "densidades = densidades_registradas(caminho_do_tronco)" in fonte
        assert "for densidade in densidades:" in fonte
        assert 'arranjo = f"{nome}/{densidade}"' in fonte

    def test_o_carimbo_do_relatorio_diz_a_densidade(self) -> None:
        """Sem ela, o JSON de `fita/compacta` e o de `fita/confortavel` são indistinguíveis --
        que é como um portão publica um número sem dizer de qual arranjo ele é."""
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        assert '"densidade": os.environ.get("CVOFF_DENSITY", "")' in fonte

    def test_o_portao_de_contraste_continua_percorrendo_as_duas(self) -> None:
        """O modelo não pode encolher enquanto os outros o copiam."""
        fonte = Path(contraste.__file__).read_text(encoding="utf-8")
        assert "CONFORTAVEL" in fonte and "COMPACTA" in fonte

    def test_o_cabecalho_do_contraste_nao_diz_mais_peles(self) -> None:
        """Ele percorre duas **polaridades** × duas densidades, e dizia "as duas peles"."""
        fonte = Path(contraste.__file__).read_text(encoding="utf-8")
        assert "nas duas peles" not in fonte


class TestUmSeparadorSo:
    """A interface tem **uma** grafia de separador, e ela é `" · "` (F9-C12).

    **O produto declarava uma e escrevia duas.** Dez lugares usavam `" · "` --
    `ui/estado_do_rodape`, `ui/strings`, `qt/painel_de_resultado`, `qt/painel_da_galeria`,
    `qt/campo`, `qt/paleta` -- e quatro usavam `" | "`, **dois deles desenhados na tela em toda
    pele e em toda largura**: `Clique em uma peça para estudar. | vez: brancas`
    (`qt/painel_de_estudo.py`) e `... | 87% com sinal objetivo de erro`
    (`qt/painel_de_revisao.py`). Nenhuma das cinco regras do censo tipográfico olhava para isso:
    ele mede aspa reta, apóstrofo reto, `...`, hífen entre espaços e faixa com hífen, e o
    separador não é nenhum dos cinco.

    **A régua fica aqui e não num instrumento**, e a razão é a de sempre nesta frente: um
    instrumento mede uma vez, um teste mede todo dia. E o recorte é `ui/` e `qt/` -- o que a
    pessoa lê na tela. `cli/train.py` e `text/dataset.py` também juntam campos com `" | "`, e
    ali isso é linha de log e de conjunto de dados, não interface.
    """

    SEPARADOR = " · "
    PROIBIDO = ' | '

    def modulos_de_interface(self, raiz_do_tronco: Path) -> list[Path]:
        pacote = raiz_do_tronco / "src" / "chess_diagram_ocr"
        return sorted((pacote / "ui").glob("*.py")) + sorted((pacote / "qt").glob("*.py"))

    def test_nenhum_modulo_de_interface_escreve_a_outra_grafia(self, raiz_do_tronco: Path) -> None:
        culpados: list[str] = []
        for arquivo in self.modulos_de_interface(raiz_do_tronco):
            for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                sem_comentario = linha.split("#", 1)[0]
                if f'"{self.PROIBIDO}"' in sem_comentario or f"'{self.PROIBIDO}'" in sem_comentario:
                    culpados.append(f"{arquivo.name}:{numero}")
        assert culpados == [], f"separador com a outra grafia em {culpados}"

    def test_a_grafia_declarada_continua_em_uso(self, raiz_do_tronco: Path) -> None:
        """A régua acima seria satisfeita apagando os separadores todos; esta diz que não é
        isso que se quer."""
        usos = sum(
            arquivo.read_text(encoding="utf-8").count(self.SEPARADOR)
            for arquivo in self.modulos_de_interface(raiz_do_tronco)
        )
        assert usos >= 10, f"o separador declarado quase sumiu da interface: {usos} usos"


# ------------------------------------------------------------------- o vazio de painel a 4K


class TestVazio:
    """O maior retângulo sem tinta, exato -- a régua do passo 16 da OCR_UI sem abrir janela."""

    def test_o_maior_retangulo_e_o_maximo_e_nao_um_chute(self) -> None:
        import numpy as np

        m = np.zeros((6, 8), dtype=bool)
        m[1:5, 2:7] = True  # 4 x 5 = 20 blocos
        m[0, :] = True  # uma linha inteira por cima: 8 blocos sozinha...
        # ...mas com ela o bloco central cresce uma linha: 5 x 5 = 25, e é isso que o exato acha
        # onde uma busca gulosa por linha ficaria nos 20.
        area, x0, y0, x1, y1 = vazio.maior_retangulo(m)
        assert area == 25
        assert (x0, y0, x1, y1) == (2, 0, 7, 5)
        m[0, :] = False
        assert vazio.maior_retangulo(m)[0] == 20

    def test_a_mascara_le_tinta_pelo_fundo_dominante_e_pela_tolerancia(self) -> None:
        import numpy as np

        a = np.full((16, 16, 3), 30, dtype=np.uint8)
        a[4:8, 4:8] = 200  # um quadrado de tinta de 4 x 4 px = um bloco
        a[0, 0] = 33  # ruído dentro da tolerância: continua fundo
        mascara, fundo = vazio.mascara_vazia(a, 0, 0, 16, 16)
        assert fundo == "#1e1e1e"
        assert mascara.shape == (4, 4)
        assert not mascara[1, 1], "o bloco com o quadrado é tinta"
        assert mascara.sum() == 15

    def test_um_painel_todo_vazio_a_4k_reprova_e_um_com_tinta_a_cada_linha_passa(self) -> None:
        import numpy as np

        liso = np.ones((500, 500), dtype=bool)
        area, *_ = vazio.maior_retangulo(liso)
        assert area * vazio.BLOCO * vazio.BLOCO / 1000 > vazio.TETO_KPX
        pautado = np.ones((500, 500), dtype=bool)
        pautado[::7, :] = False  # um traço a cada 28 px
        area, *_ = vazio.maior_retangulo(pautado)
        assert area * vazio.BLOCO * vazio.BLOCO / 1000 <= vazio.TETO_KPX

