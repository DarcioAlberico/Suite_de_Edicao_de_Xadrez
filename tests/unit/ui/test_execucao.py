"""O portão de execução: a operação de fundo achada vendo-a correr (F9-C10).

**Por que este arquivo existe, e por que ele é curto.** O portão em si só se prova rodando --
contra as árvores de sabotagem em `benchmarks/reports/ui/c10/sab_c9x/` (as oito formas do crítico
do ciclo 9, transcritas para poderem correr) e `sab_c10/` (oito minhas). O que se afirma **aqui**
é a parte que decide, e que não precisa de janela: de quem é a origem de uma abertura, e quando
uma abertura está coberta.

A distinção importa porque é a mesma do resto desta suíte: o arnês descobre que a janela abriu
uma thread; um teste puro descobre que a **regra** de atribuição ficou generosa. A segunda não
aparece em execução nenhuma -- uma origem que caísse em `concurrent/futures/thread.py` devolveria
um relatório plausível para sempre.
"""

from __future__ import annotations

import concurrent.futures
import threading

from caissa.ui.audit import execucao


def _nada() -> None:
    return None


class TestOrigemDaAbertura:
    """A abertura é atribuída a **quem a pediu**, e não ao mecanismo que a executa.

    É a queixa literal do crítico do ciclo 7 contra a régua de AST: *"uma linha dizendo `__init__`
    constrói `QThread` não diz que `e_move_to_thread` é uma operação de fundo"*.
    """

    def test_uma_thread_crua_e_atribuida_a_funcao_que_a_iniciou(self) -> None:
        with execucao.Vigia() as vigia:
            fio = threading.Thread(target=_nada, daemon=True)
            fio.start()
            fio.join(1.0)
        assert [a.tipo for a in vigia.aberturas] == ["threading.Thread.start"]
        assert vigia.aberturas[0].arquivo == "test_execucao.py"
        assert vigia.aberturas[0].funcao == "test_uma_thread_crua_e_atribuida_a_funcao_que_a_iniciou"

    def test_o_executor_nao_e_a_origem(self) -> None:
        """`ThreadPoolExecutor.submit` chama `Thread.start` de dentro da biblioteca-padrão.

        Sem a regra de pular os quadros da biblioteca, toda submissão do programa seria atribuída
        a `concurrent/futures/thread.py` -- o nome do mecanismo, que é justamente o que nenhum
        relatório precisa.
        """
        with execucao.Vigia() as vigia:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(_nada).result(timeout=5)
        assert vigia.aberturas, "a submissão não abriu thread nenhuma?"
        assert {a.arquivo for a in vigia.aberturas} == {"test_execucao.py"}
        assert {a.funcao for a in vigia.aberturas} == {"test_o_executor_nao_e_a_origem"}

    def test_o_vigia_desfaz_o_remendo_ao_sair(self) -> None:
        """Um vigia que deixasse `Thread.start` remendado contaminaria toda medição posterior --
        e este portão roda nove ações seguidas no mesmo processo."""
        antes = threading.Thread.start
        with execucao.Vigia():
            assert threading.Thread.start is not antes
        assert threading.Thread.start is antes

    def test_um_bloco_que_levanta_tambem_desfaz(self) -> None:
        antes = threading.Thread.start
        try:
            with execucao.Vigia():
                raise RuntimeError("a ação da janela levantou")
        except RuntimeError:
            pass
        assert threading.Thread.start is antes


class TestRede:
    """`threading.enumerate()` é a rede, e ela pega o que a lista de pontos não conhece."""

    def test_uma_thread_aberta_por_fora_do_ponto_sai_como_nao_atribuida(self) -> None:
        """**É a propriedade que a régua de AST nunca teve.** Aqui a thread é iniciada pelo
        `start` original, guardado antes do remendo -- é o mais perto que se chega, em Python, de
        "uma forma que o portão não conhece". O portão não fica calado: ele diz que nasceu uma
        thread que nenhum ponto interceptado explica, com o nome e o `target` dela.
        """
        original = threading.Thread.start
        parar = threading.Event()
        fio = threading.Thread(target=parar.wait, daemon=True, name="fora-do-ponto")
        with execucao.observar("a ação") as acao:
            original(fio)
        assert acao.aberturas == []
        assert any("fora-do-ponto" in linha for linha in acao.nao_atribuidas)
        parar.set()
        fio.join(2.0)

    def test_uma_acao_que_nao_abre_nada_fica_calada(self) -> None:
        """O outro lado: um portão que passasse a gritar seria a outra forma de ficar cego."""
        with execucao.observar("nada") as acao:
            _ = [str(numero) for numero in range(10)]
        assert acao.aberturas == []
        assert acao.nao_atribuidas == []


class TestCobertura:
    """Quando uma abertura está coberta -- declarada, ou registrada pelo mesmo arquivo."""

    def _acao(self, arquivo: str, funcao: str) -> execucao.Acao:
        return execucao.Acao(
            nome="acao",
            aberturas=[
                execucao.Abertura(
                    tipo="threading.Thread.start",
                    detalhe="",
                    arquivo=arquivo,
                    funcao=funcao,
                )
            ],
        )

    def test_a_declarada_esta_coberta(self) -> None:
        acao = self._acao("janela.py", "_rodar")
        assert acao.descobertas({("janela.py", "_rodar"): "o laço interno do programa"}) == []

    def test_a_nao_declarada_e_sem_registro_e_defeito(self) -> None:
        acao = self._acao("sabotador.py", "abre_ao_fundo")
        assert len(acao.descobertas({})) == 1

    def test_um_registro_do_mesmo_arquivo_cobre(self) -> None:
        acao = self._acao("painel_do_dataset.py", "_reler_agora")
        acao.registros.append(
            execucao.Registro(
                nome="leitura do dataset", arquivo="painel_do_dataset.py", funcao="_registrar"
            )
        )
        assert acao.descobertas({}) == []

    def test_um_registro_de_OUTRO_arquivo_nao_cobre(self) -> None:
        """Senão bastaria uma operação registrada na mesma ação para absolver todas as outras --
        e a ação "abrir o livro" registra uma e abre duas."""
        acao = self._acao("sabotador.py", "abre_ao_fundo")
        acao.registros.append(
            execucao.Registro(nome="outra coisa", arquivo="marcas.py", funcao="pedir")
        )
        assert len(acao.descobertas({})) == 1


class TestFiltroDeFormas:
    """Que método de uma sabotagem é forma, e qual é controle negativo."""

    def test_letra_e_sublinhado_com_digito_opcional(self) -> None:
        assert execucao._E_FORMA.match("a_classe_devolvida")
        assert execucao._E_FORMA.match("h_subclasse_dinamica")
        assert execucao._E_FORMA.match("n1_relogio")
        assert execucao._E_FORMA.match("n4_reduce")

    def test_ajudante_e_dunder_ficam_de_fora(self) -> None:
        """Sem isto o `_abre_outra` da forma (g) seria contado como uma nona forma."""
        assert not execucao._E_FORMA.match("_abre_outra")
        assert not execucao._E_FORMA.match("__init__")
        assert not execucao._E_FORMA.match("disparo")
