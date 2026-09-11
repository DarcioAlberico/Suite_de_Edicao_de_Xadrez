"""A largura do portão de teclado no eixo **janela** (F9-C12).

**O ciclo 11 reprovou esta frente por um defeito só, e ele era de escopo.** O portão publicava
`216 / 240 / 360 focáveis, 0 sem nome, PASSOU` percorrendo `janela.abas` -- as seis abas da
janela principal. O produto tem **doze `QDialog`**, e em onze ciclos nenhum portão desta frente
abriu um. Rodada a régua do próprio portão em seis deles, ela devolvia **11 controles sem nome
acessível**: o campo onde se digita o comando na paleta (`Ctrl+Shift+P`), que é a superfície de
quem usa o teclado, e **dois `QLineEdit` sem nome lado a lado** em `Achar e substituir`.

É a mesma cegueira do ciclo 9 num eixo diferente: lá era *qual aparência*, aqui é *qual janela*.
E a resposta tem de ser a mesma -- **estrutural**. O ciclo 10 fez a lista de peles sair de
`ui/pele.PELES`, e o crítico a testou por mutação: registrada uma quarta pele, o portão passou a
percorrê-la sozinho. Estes testes são a mesma prova no eixo da janela.

**Nada aqui abre Qt**, e é o que faz o teste existir: o venv desta suíte não tem binding de Qt
nenhum. `qt.dialogos_do_produto()` lê a **árvore sintática** de `chess_diagram_ocr/qt/*.py`
justamente por isso -- uma varredura que importasse o PyQt6 deixaria este arquivo pulado, que é
o mesmo que não existir.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from caissa.ui.audit import teclado


def _produto() -> object:
    from chess_diagram_ocr import qt

    return qt


class TestALarguraNoEixoJanela:
    """A lista de diálogos sai do produto, e o arnês não pode ter outra."""

    def test_o_produto_declara_os_doze_dialogos(self) -> None:
        """Doze é o número que o crítico do ciclo 11 contou à mão, arquivo por arquivo."""
        do_produto = _produto().dialogos_do_produto()
        assert len(do_produto) >= 12, (
            f"o produto declara menos diálogos que o ciclo 11 contou: {do_produto}"
        )
        for esperado in (
            "JanelaDaPaleta",  # Ctrl+Shift+P -- a superfície de quem usa o teclado
            "JanelaDeBusca",  # os dois QLineEdit lado a lado
            "JanelaDeAtalhos",
            "JanelaDeEstatisticas",
            "_JanelaDeColar",
            "ControladorDeTreino",
        ):
            assert esperado in do_produto

    def test_o_arnes_sabe_abrir_todo_dialogo_do_produto(self) -> None:
        """**O teste que cai quando o décimo terceiro entrar.**

        `RECEITAS` é a metade que ninguém consegue derivar -- com que argumentos cada janela
        abre. A **lista** não é dela: é de `qt.dialogos_do_produto()`. Quando as duas divergem,
        o portão levanta em vez de medir doze de treze e publicar `PASSOU`.
        """
        do_produto = set(_produto().dialogos_do_produto())
        do_arnes = set(teclado.RECEITAS)
        assert do_arnes == do_produto, (
            f"sem receita no arnês: {sorted(do_produto - do_arnes)}; "
            f"receita para quem o produto não define: {sorted(do_arnes - do_produto)}"
        )

    def test_um_dialogo_novo_aparece_sozinho_na_lista(self, tmp_path: Path) -> None:
        """A prova de vida da varredura, por mutação e não por leitura.

        Um pacote de mentira com um `QDialog` a mais: a varredura tem de achá-lo **sem que
        ninguém a atualize**. É a resposta à pergunta que o ciclo 11 fez -- "uma janela nova
        consegue entrar no produto sem entrar no portão?".
        """
        pacote = tmp_path / "qt"
        pacote.mkdir()
        (pacote / "janela.py").write_text(
            "class JanelaPrincipal(QMainWindow):\n    pass\n", encoding="utf-8"
        )
        (pacote / "dialogos.py").write_text(
            "class DialogoDeBases(QDialog):\n    pass\n", encoding="utf-8"
        )
        antes = _produto().dialogos_do_produto(pacote)
        assert antes == ("DialogoDeBases",)

        (pacote / "sonda.py").write_text(
            "class _JanelaDeSonda(QDialog):\n    pass\n", encoding="utf-8"
        )
        depois = _produto().dialogos_do_produto(pacote)
        assert depois == ("DialogoDeBases", "_JanelaDeSonda")
        assert set(depois) - set(teclado.RECEITAS), "o arnês não teria receita para a sonda"

    def test_quem_herda_de_um_dialogo_tambem_entra(self, tmp_path: Path) -> None:
        """O fecho é transitivo: o dia em que alguém escrever uma base comum de diálogo aqui
        dentro, as filhas dela não podem sumir da conta."""
        pacote = tmp_path / "qt"
        pacote.mkdir()
        (pacote / "base.py").write_text(
            "class Dialogo(QDialog):\n    pass\n", encoding="utf-8"
        )
        (pacote / "filha.py").write_text(
            "class JanelaDeAlgo(Dialogo):\n    pass\n", encoding="utf-8"
        )
        assert _produto().dialogos_do_produto(pacote) == ("Dialogo", "JanelaDeAlgo")

    def test_a_varredura_nao_confunde_importacao_com_definicao(self, tmp_path: Path) -> None:
        """Uma classe que só é importada não é definida ali, e contá-la duas vezes faria o
        arnês procurar receita para um nome que já tem."""
        pacote = tmp_path / "qt"
        pacote.mkdir()
        (pacote / "a.py").write_text("class JanelaX(QDialog):\n    pass\n", encoding="utf-8")
        (pacote / "b.py").write_text("from .a import JanelaX\n", encoding="utf-8")
        assert _produto().dialogos_do_produto(pacote) == ("JanelaX",)

    def test_um_apelido_da_base_nao_esconde_o_dialogo(self, tmp_path: Path) -> None:
        """**A sabotagem (d) do crítico do ciclo 13**, e o portão passava calado nela.

        `Base = QDialog` no topo do módulo e `class X(Base)` embaixo: a árvore sintática lê o
        nome escrito na linha da classe, e o nome escrito é `Base`. Uma janela de diálogo que
        some da lista é o defeito do ciclo 11 com a fachada trocada.
        """
        pacote = tmp_path / "qt"
        pacote.mkdir()
        (pacote / "a.py").write_text(
            "Base = QDialog\nclass JanelaDeApelido(Base):\n    pass\n", encoding="utf-8"
        )
        assert _produto().dialogos_do_produto(pacote) == ("JanelaDeApelido",)

    def test_uma_caixa_de_mensagem_com_classe_propria_entra(self, tmp_path: Path) -> None:
        """**A sabotagem (e)**: `QMessageBox` *é* um `QDialog` no Qt, e a varredura não sabia.

        A lista de bases é do Qt (`qt.BASES_DE_DIALOGO_DO_QT`) e não deste produto: ela só cresce
        quando o Qt ganha um diálogo novo.
        """
        pacote = tmp_path / "qt"
        pacote.mkdir()
        (pacote / "a.py").write_text(
            "class CaixaPropria(QMessageBox):\n    pass\n", encoding="utf-8"
        )
        assert _produto().dialogos_do_produto(pacote) == ("CaixaPropria",)

    def test_um_dialogo_num_submodulo_entra(self, tmp_path: Path) -> None:
        """**A sabotagem (f)**: `glob("*.py")` não desce, e `qt/<pasta>/novo.py` passava calado."""
        pacote = tmp_path / "qt"
        (pacote / "sub").mkdir(parents=True)
        (pacote / "a.py").write_text("class JanelaX(QDialog):\n    pass\n", encoding="utf-8")
        (pacote / "sub" / "novo.py").write_text(
            "class JanelaEmSubpasta(QDialog):\n    pass\n", encoding="utf-8"
        )
        assert _produto().dialogos_do_produto(pacote) == ("JanelaEmSubpasta", "JanelaX")

    def test_o_portao_publica_o_que_a_varredura_NAO_alcanca(self) -> None:
        """**O portão parou de afirmar mais largura do que tem** (item 6 do §7 do ciclo 13).

        A linha publicada dizia "os 12 `QDialog` que o produto declara", e o produto tem uma 14ª
        tela: o `QDialog(self)` construído em linha em `painel_de_estudo.ampliar_recorte` (S-282),
        mais as oito formas de `QMessageBox`. Nenhuma varredura sintática pode achá-las, e as
        nove estão limpas porque o remédio mora no `QEvent.Show`. O número continua certo; o que
        entrou foi a frase que impede alguém de o ler como se fosse o total.
        """
        assert "COMO CLASSE" in teclado.tabela(_relatorio_de_exemplo())
        assert teclado.FORA_DA_VARREDURA in teclado.tabela(_relatorio_de_exemplo())
        assert "ampliar_recorte" in teclado.FORA_DA_VARREDURA
        assert "QMessageBox" in teclado.FORA_DA_VARREDURA


def _relatorio_de_exemplo() -> dict:
    """O menor relatório que faz `tabela` imprimir o bloco dos diálogos."""
    tela = {
        "nome": "DialogoDeBases (Estudo | Bases)",
        "focaveis": 3,
        "alcancados_pelo_tab": 3,
        "a_volta_fecha": True,
        "sem_nome": [],
        "sem_papel": [],
        "nome_vazio_de_sentido": [],
        "inalcancaveis": [],
        "veredito": "PASSOU",
    }
    return {
        "portao": "exemplo",
        "abas": [],
        "dialogos": [tela],
        "dialogos_do_produto": ["DialogoDeBases"],
        "veredito": "PASSOU",
    }


class TestAVarreduraAlcancaTodoDialogo:
    """O lado do produto: **uma** varredura, e não doze chamadas espalhadas.

    É o antipadrão que `qt/acessibilidade.py` recusa por escrito no próprio docstring -- *"as
    vinte chamadas seriam vinte lugares que alguém precisa lembrar, e a vigésima primeira -- o
    campo que o próximo item acrescenta -- nasceria muda"*. A frase estava certa e a varredura
    rodava numa janela só.
    """

    def _fonte(self, raiz_do_tronco: Path, caminho: str) -> str:
        return (raiz_do_tronco / "src" / "chess_diagram_ocr" / caminho).read_text(encoding="utf-8")

    def test_existe_um_filtro_de_evento_de_show_para_qdialog(self, raiz_do_tronco: Path) -> None:
        fonte = self._fonte(raiz_do_tronco, "qt/acessibilidade.py")
        assert "def vigiar_dialogos" in fonte
        assert "installEventFilter" in fonte
        assert "QEvent.Type.Show" in fonte
        assert "isinstance(alvo, QDialog)" in fonte

    def test_a_janela_pede_acessibilidade_numa_linha_so(self, raiz_do_tronco: Path) -> None:
        """**Uma chamada, e ela cobre a janela e os diálogos.**

        Duas linhas em `qt/janela.py` seriam duas coisas para lembrar, e a segunda é a que se
        esquece -- que é a forma exata do defeito do ciclo 11. `tornar_acessivel` põe a decisão
        em `qt/acessibilidade.py`, que é onde ela mora.
        """
        arvore = ast.parse(self._fonte(raiz_do_tronco, "qt/janela.py"))
        chamadas = [
            no.func.attr
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        ]
        assert chamadas.count("tornar_acessivel") == 1, "a janela pede acessibilidade uma vez"
        assert "vigiar_dialogos" not in chamadas, "a instalação do filtro não mora na janela"

    def test_o_ponto_de_entrada_faz_as_duas_metades(self, raiz_do_tronco: Path) -> None:
        fonte = self._fonte(raiz_do_tronco, "qt/acessibilidade.py")
        corpo = fonte[fonte.index("def tornar_acessivel(") :]
        assert "nomear_tudo(janela)" in corpo
        assert "vigiar_dialogos()" in corpo

    def test_nenhum_dialogo_chama_nomear_tudo_por_conta_propria(self, raiz_do_tronco: Path) -> None:
        """**O antipadrão, cobrado.** Doze `nomear_tudo(self)` espalhados passariam neste ciclo
        e falhariam no décimo terceiro diálogo -- que é a definição do defeito que o ciclo 11
        reprovou. Quem varre é o filtro."""
        pasta = raiz_do_tronco / "src" / "chess_diagram_ocr" / "qt"
        culpados = [
            arquivo.name
            for arquivo in sorted(pasta.glob("*.py"))
            if arquivo.name != "acessibilidade.py"
            and "nomear_tudo(" in arquivo.read_text(encoding="utf-8")
        ]
        assert culpados == [], f"varredura chamada à mão em {culpados}"


class TestAReguaDosDialogosEAMesmaDasAbas:
    """Nenhuma régua nova para os diálogos: as mesmas classes, as mesmas funções.

    Uma segunda régua seria uma segunda oportunidade de as duas divergirem sem ninguém notar --
    e o portão passaria a publicar dois números que ninguém consegue comparar.
    """

    def test_a_medicao_de_uma_tela_e_uma_funcao_so(self) -> None:
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        assert fonte.count("def _medir_uma_tela") == 1
        # `auditar` (as abas) e `_medir_os_dialogos` (os diálogos) chamam a mesma função.
        assert fonte.count("_medir_uma_tela(") >= 3

    def test_o_relatorio_traz_uma_linha_por_dialogo(self) -> None:
        """O alvo, com as palavras do ciclo 11: *"o portão de teclado publica uma linha por
        diálogo registrado"*."""
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        assert '"dialogos": [_como_json(aba) for aba in dialogos]' in fonte
        assert '"dialogos_do_produto": dialogos_registrados(caminho_do_tronco)' in fonte

    def test_o_veredito_soma_abas_e_dialogos(self) -> None:
        """Um diálogo que reprova **tem** de derrubar o portão. Enquanto o veredito olhasse só
        `abas`, onze defeitos conviviam com um `PASSOU`."""
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        assert 'veredito([*abas, *dialogos])' in fonte


class TestOsMotivosRefinadosContinuamPegandoODefeitoQueOsCriou:
    """Três réguas foram afinadas neste ciclo. **Nenhuma pode ter perdido o caso que a pediu.**

    Afinar é o oposto de afrouxar, e a diferença se demonstra: cada teste aqui repõe o defeito
    exato que criou a regra e exige que ele continue reprovando.
    """

    def _controle(self, **campos: object) -> teclado.Controle:
        base = {
            "classe": "QCheckBox",
            "nome": "",
            "origem_do_nome": "texto",
            "papel": "CheckBox",
            "alcancado_pelo_tab": True,
        }
        return teclado.Controle(**{**base, **campos})  # type: ignore[arg-type]

    def test_a_dica_longa_vazando_para_o_anuncio_continua_reprovando(self) -> None:
        """O defeito do ciclo 3, em seis abas: o `QComboBox` de regime anunciava a **dica**
        truncada pelo Qt em 67 caracteres, no 14º lugar da ordem do `Tab`."""
        frase = "Em que condição esta página foi lida. Entra na anotação e separa as"
        controle = self._controle(
            classe="QComboBox", nome=frase, origem_do_nome="dica", papel="ComboBox"
        )
        assert controle.nome_vazio_de_sentido() == "e prosa, nao nome"

    def test_um_nome_derivado_do_rotulo_vizinho_longo_tambem(self) -> None:
        """O caso do ciclo 12: a varredura deriva o nome do rótulo ao lado, e o rótulo é uma
        instrução inteira. Não está desenhado **no** controle, então o teto vale."""
        controle = self._controle(
            classe="QTextEdit",
            nome="Cole aqui uma FEN ou um PGN. O texto diz qual dos dois é.",
            origem_do_nome="accessibleName",
            papel="EditableText",
        )
        assert controle.nome_vazio_de_sentido() == "e prosa, nao nome"

    def test_o_rotulo_desenhado_longo_nao_e_prosa(self) -> None:
        """O nome **é** o texto que a pessoa vidente lê -- a WCAG 2.5.3 pede exatamente isso.
        O caso medido: a caixa de marcar de `DialogoDeBases`, cujo rótulo é o nome do arquivo."""
        controle = self._controle(
            nome="Endgame_Study_Database_VI_Harold_van_der_Heijden_December_2020.pgn"
        )
        assert controle.nome_vazio_de_sentido() == ""

    def test_duas_oracoes_continuam_sendo_prosa_mesmo_desenhadas(self) -> None:
        """O sinal forte não depende da origem: um rótulo com duas orações é defeito na tela
        também."""
        controle = self._controle(nome="Isto faz uma coisa. Aquilo faz outra")
        assert controle.nome_vazio_de_sentido() == "e prosa, nao nome"

    def test_o_glifo_continua_sem_letras(self) -> None:
        """O defeito nº 1 do ciclo 1: `-`, `+`, `|◀`, `.md`. O piso de três letras fica."""
        for glifo in ("-", "+", "|◀", ".md", "121"):
            assert self._controle(nome=glifo).nome_vazio_de_sentido() == "sem letras"

    def test_o_eco_do_papel_continua_reprovando(self) -> None:
        """`"Campo de texto"` no campo da paleta de comandos -- o caso deste ciclo."""
        controle = self._controle(
            classe="QLineEdit",
            nome="Campo de texto",
            origem_do_nome="accessibleName",
            papel="EditableText",
        )
        assert controle.nome_vazio_de_sentido() == "eco do papel"


class TestAVoltaDoTabNumaTelaDeUmControle:
    """A volta fecha com um controle só, e continua sendo beco com dois."""

    def test_a_regra_esta_escrita_no_tamanho_do_conjunto(self) -> None:
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        assert "return visto, passos, len(focaveis) == 1" in fonte

    def test_o_beco_de_dois_controles_continua_reprovando(self) -> None:
        """A régua da `Aba`: uma volta que não fecha reprova, e é o que a linha acima preserva."""
        aba = teclado.Aba(nome="beco", fechou=False)
        aba.controles.append(
            teclado.Controle(
                classe="QPushButton",
                nome="Salvar",
                origem_do_nome="texto",
                papel="Button",
                alcancado_pelo_tab=True,
            )
        )
        assert not aba.passou()


class TestOGrupoParaNaJanela:
    """O grupo de um controle de diálogo não pode vir da janela que ficou atrás dele."""

    def test_a_subida_para_na_janela(self) -> None:
        fonte = Path(teclado.__file__).read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def _grupo_de(") : fonte.index("def _papel_de(")]
        assert "if pai.isWindow():" in trecho


class TestOPadraoDeSaidaNaoApontaParaAPastaDoConstrutor:
    """**Higiene de arnês, e ela pegou o crítico do ciclo 11 uma vez** (F9-C11, nota de
    procedimento). `caissa.ui.audit.execucao --saida` tinha padrão em `benchmarks/reports/ui/`
    -- a pasta do construtor --, e uma sabotagem rodada sem `--saida` gravou lá dentro.

    Um padrão que escreve na pasta de outro agente é uma armadilha, e a saída certa é não ter
    padrão: quem roda um portão diz onde quer o relatório.
    """

    @pytest.mark.parametrize(
        "modulo", ["execucao", "teclado", "contraste", "progresso", "bloqueio", "quadros"]
    )
    def test_o_saida_e_obrigatorio(self, modulo: str) -> None:
        from importlib import import_module

        arquivo = Path(import_module(f"caissa.ui.audit.{modulo}").__file__)
        fonte = arquivo.read_text(encoding="utf-8")
        trecho = fonte[fonte.index('"--saida"') :][:400]
        # Ou o argumento é obrigatório, ou o módulo recusa a chamada sem caminho nenhum
        # (`teclado` aceita `--json` no lugar, que também diz onde gravar).
        exige = "required=True" in trecho or "parser.error(" in fonte
        assert exige, f"{modulo}: --saida sem exigência de caminho"
        assert "RELATORIOS" not in fonte, (
            f"{modulo}: ainda guarda um caminho para benchmarks/reports/ui"
        )
        codigo = [linha for linha in trecho.splitlines() if not linha.lstrip().startswith("#")]
        padroes = [linha for linha in codigo if "default=" in linha and "default=None" not in linha]
        assert padroes == [], f"{modulo}: --saida com padrão embutido: {padroes}"

