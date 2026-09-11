"""O portão dos comandos: **um item habilitado tem de poder acontecer** (F9-C16).

**Catorze ciclos mediram a tinta de cada rótulo e nenhum perguntou se o item fazia alguma coisa.**
O crítico do ciclo 15 perguntou e achou três: `Analisar a posição com o motor`, `Análise contínua
enquanto se navega` e `Pôr a linha do motor como variante` saíam `habilitado=True` em **qualquer**
máquina, e os três respondiam *"ponha o Stockfish em engines/ e reabra"* -- uma receita que não
resolvia, porque a janela nunca procurava o binário: `engine.find_engine`, `EngineAnalyzer` e
`settings.EngineSettings.path` não tinham **um chamador em `src/`**.

Estes testes cobram a aritmética do portão -- classificar um comando medido -- e a declaração do
produto sobre que comandos exigem motor. A parte que abre janela está no portão e é rodada com as
duas provas de vida (`--desligar`, `--religar`); aqui não há Qt, porque o venv desta suíte não tem
binding nenhum.
"""

from __future__ import annotations

import pytest

from caissa.ui.audit import comandos as pc


def _comando(**campos: object) -> pc.Comando:
    padrao: dict[str, object] = {
        "acao": "salvar",
        "superficie": "menu",
        "rotulo": "Salvar a posição",
        "habilitado": True,
        "visivel": True,
        "receptores": 1,
    }
    padrao.update(campos)
    return pc.Comando(**padrao)  # type: ignore[arg-type]


COM_MOTOR = {pc.MOTOR: True}
SEM_MOTOR = {pc.MOTOR: False}


class TestAsTresPerguntas:
    """As três maneiras de um comando desenhado estar errado, e nenhuma é sobre o texto dele."""

    def test_habilitado_e_sem_receptor_e_solto(self) -> None:
        """Clicar não faz nada, e nada avisa. É o pior dos três."""
        assert pc.defeito_de(_comando(receptores=0), recursos=SEM_MOTOR) == "solto"
        assert pc.defeito_de(_comando(receptores=1), recursos=SEM_MOTOR) == ""

    def test_habilitado_e_exigindo_o_que_nao_ha_e_promessa(self) -> None:
        """**O defeito do ciclo 15, na forma em que um portão o pega.**

        Não é sobre a mensagem: é sobre o item estar oferecido numa sessão em que ele não pode
        ter efeito. Com motor, o mesmo comando está certo.
        """
        motor = _comando(acao="analisar_posicao", exige=pc.MOTOR)
        assert pc.defeito_de(motor, recursos=SEM_MOTOR) == "promete"
        assert pc.defeito_de(motor, recursos=COM_MOTOR) == ""

    def test_desabilitado_sem_dica_e_cinza_sem_motivo(self) -> None:
        """Desabilitar sem explicar é o mesmo defeito com o sinal trocado.

        Uma `QAction` cinza não recebe clique e não mostra mensagem: a dica é a única superfície
        que sobra, e sem ela a pessoa procura o erro na própria máquina.
        """
        cinza = _comando(habilitado=False, exige=pc.MOTOR)
        assert pc.defeito_de(cinza, recursos=SEM_MOTOR) == "cinza sem motivo"
        com_razao = _comando(habilitado=False, exige=pc.MOTOR, dica="Precisa de um motor UCI.")
        assert pc.defeito_de(com_razao, recursos=SEM_MOTOR) == ""

    def test_o_invisivel_nao_e_julgado(self) -> None:
        """Um item que a janela não oferece não promete nada. Ver `_secao_do_motor`."""
        assert pc.defeito_de(_comando(visivel=False, receptores=0), recursos=SEM_MOTOR) == ""

    def test_sinal_que_nao_soube_perguntar_nao_vira_defeito(self) -> None:
        """`-1` é ponto cego e não defeito, e a diferença é o assunto desta frente inteira.

        Um portão que grita sobre o que não mediu é tão ruim quanto um que se cala: `receptores`
        negativo sai numa conta própria (`nao_perguntados`), publicada ao lado do placar.
        """
        assert pc.defeito_de(_comando(receptores=-1), recursos=SEM_MOTOR) == ""

    def test_a_ordem_das_perguntas_diz_a_coisa_mais_grave(self) -> None:
        """Solto ganha de promete: um comando que não faz nada é pior que um que não pode fazer."""
        os_dois = _comando(acao="analisar_posicao", exige=pc.MOTOR, receptores=0)
        assert pc.defeito_de(os_dois, recursos=SEM_MOTOR) == "solto"


class TestOPlacar:
    """O que a passada publica, e o que ela recusa a publicar."""

    def test_uma_medicao_omissa_nao_vira_aprovacao(self) -> None:
        """Zero medições é `REPROVOU`: foi assim que o ciclo 9 publicou uma pele que não mediu."""
        assert pc.veredito([]) == "REPROVOU"
        assert pc.veredito([{"veredito": "PASSOU"}]) == "PASSOU"
        assert pc.veredito([{"veredito": "PASSOU"}, {"veredito": "REPROVOU"}]) == "REPROVOU"

    def test_a_passada_conta_por_superficie_e_por_defeito(self) -> None:
        """O placar não fica sem dizer de quem é: menu, fita e fila são contados separados."""
        medicao = pc.Medicao(
            arranjo="fita/compacta",
            recursos=dict(SEM_MOTOR),
            comandos=[
                _comando(acao="salvar"),
                _comando(acao="abrir_pdf", superficie="fita"),
                _comando(acao="analisar_posicao", exige=pc.MOTOR),
                _comando(acao="analise_continua", habilitado=False, receptores=1),
            ],
        )
        saida = medicao.como_dicionario()
        assert saida["medidos"] == 4
        assert saida["por_superficie"] == {"fita": 1, "menu": 3}
        assert saida["habilitados"] == 3
        assert (saida["soltos"], saida["prometem"], saida["cinzas_sem_motivo"]) == (0, 1, 1)
        assert saida["veredito"] == "REPROVOU"
        assert {d["acao"] for d in saida["defeitos"]} == {"analisar_posicao", "analise_continua"}


class TestOProdutoDeclaraQuemExigeMotor:
    """A lista não mora no portão, e é o que impede o segundo recurso de nascer só na janela."""

    def test_os_tres_do_ciclo_15_estao_declarados(self) -> None:
        from chess_diagram_ocr.ui import sala_declarada

        assert set(sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR) == {
            "analisar_posicao",
            "analise_continua",
            "variante_do_motor",
        }

    def test_partidas_da_posicao_nao_exige_motor(self) -> None:
        """A quarta linha do mesmo bloco de menu, e ela funciona sem Stockfish nenhum.

        Desabilitá-la por parecer do mesmo grupo seria o mesmo defeito com o sinal trocado: quem
        a atende é a base de partidas.
        """
        from chess_diagram_ocr.ui import sala_declarada

        assert "partidas_da_posicao" not in sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR
        assert "partidas_da_posicao" in sala_declarada.COMANDOS_DA_ABA

    def test_todo_comando_que_exige_motor_e_um_comando_do_catalogo(self) -> None:
        """Um nome torto aqui desabilitaria coisa nenhuma, calado."""
        from chess_diagram_ocr.ui import comandos as catalogo
        from chess_diagram_ocr.ui import sala_declarada

        fora = catalogo.acoes_fora_do_catalogo(sala_declarada.COMANDOS_QUE_EXIGEM_MOTOR)
        assert not fora, fora

    def test_a_frase_do_status_deixou_de_mandar_fazer_o_que_nao_resolve(self) -> None:
        """A receita de antes -- *"ponha o Stockfish em engines/ e reabra"* -- não resolvia nada.

        Reabrir não mudava coisa alguma porque ninguém procurava o binário. A carta §3.3 cobra que
        a mensagem diga o que fazer a seguir; dizer o que **não** funciona é pior que não dizer.
        """
        from chess_diagram_ocr.ui import strings

        assert "reabra" not in strings.SEM_MOTOR_STATUS.lower()
        # E a dica do item cinza nomeia os dois caminhos que `find_engine` de fato percorre.
        assert "engines/" in strings.SEM_MOTOR_DICA
        assert "settings.json" in strings.SEM_MOTOR_DICA

    @pytest.mark.parametrize("simbolo", ["find_engine", "EngineAnalyzer"])
    def test_o_motor_deixou_de_ser_codigo_sem_chamador(self, simbolo: str, raiz_do_tronco) -> None:
        """**`engine.find_engine` tinha zero chamadores em `src/`** (F9-C15 §6.1).

        O `ROADMAP.md:901` marcava ✅ o item do motor e a corrente estava solta em quatro pontos.
        Este teste é a contagem: fora do próprio `engine.py`, alguém em `src/` tem de chamar.
        """
        fontes = [
            arquivo
            for arquivo in (raiz_do_tronco / "src").rglob("*.py")
            if arquivo.name != "engine.py"
        ]
        chamadores = [
            arquivo.relative_to(raiz_do_tronco).as_posix()
            for arquivo in fontes
            if f"{simbolo}(" in arquivo.read_text(encoding="utf-8")
        ]
        assert chamadores, f"{simbolo} continua sem chamador em src/"
