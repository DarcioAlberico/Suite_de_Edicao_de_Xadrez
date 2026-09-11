"""As legendas dos botões padrão: onde o Qt tem palavra, a palavra é do Qt (F9-C14).

**Este arquivo existe por uma regressão minha, medida pelo crítico do ciclo 13.** O ciclo 12
fotografou os treze diálogos pela primeira vez, viu um botão escrito `Close` e mediu **7 de 12**
botões padrão em inglês num produto inteiramente em pt-BR. O conserto -- traduzir pelo **nome do
enum**, no mesmo filtro de `QEvent.Show` que nomeia os diálogos -- foi a decisão certa e paga:
numa máquina cujo Qt fala alemão o produto continua em português.

E ele **piorou 32 telas**. `BOTOES_PADRAO["Ok"]` virou `"Confirmar"`, e o produto tem 32 chamadas
de `QMessageBox.information/critical/warning/about` -- todas com um botão só. A caixa *Sobre o
produto* e vinte e tantas caixas de erro passaram a dizer `[Confirmar]`. Confirmar o quê? O
argumento escrito era `LETRAS_MINIMAS`, a régua de **nome acessível** que nasceu no ciclo 1 para
reprovar `-`, `+` e `◀` -- glifos que não anunciam nada. `OK` não é glifo: é a palavra que o
Windows em pt-BR usa, que o `qtbase_pt_BR.qm` desta árvore usa e que todo leitor de tela
pronuncia.

**Nada aqui abre Qt.** O catálogo do Qt está registrado em `ui/strings.TRADUZIDOS_PELO_QT`,
medido por `benchmarks/reports/ui/c14/c14_catalogo_do_qt.py` contra o `.qm` de verdade; estes
testes cobram a **regra** sobre esse registro, e o instrumento cobra o registro contra o `.qm`.
"""

from __future__ import annotations

from caissa.ui.audit import teclado


def _strings() -> object:
    from chess_diagram_ocr.ui import strings

    return strings


class TestOndeOQtTemPalavraAPalavraEDoQt:
    def test_o_botao_unico_de_um_aviso_diz_ok(self) -> None:
        """O item 3 do §7 do ciclo 13, na sua forma mais curta."""
        assert _strings().BOTOES_PADRAO["Ok"] == "OK"

    def test_toda_divergencia_do_catalogo_do_qt_tem_motivo_escrito(self) -> None:
        """**A regra, e ela é o que impede a próxima regressão da mesma forma.**

        A tabela do produto existe para a máquina que não tem catálogo nenhum -- não para
        reescrever o vocabulário de quem tem. Divergir é possível, e custa uma frase.
        """
        strings = _strings()
        divergem = {
            enum
            for enum, palavra in strings.TRADUZIDOS_PELO_QT.items()
            if enum in strings.BOTOES_PADRAO and strings.BOTOES_PADRAO[enum] != palavra
        }
        nao_declaradas = sorted(divergem - set(strings.DIVERGENCIAS_DECLARADAS))
        assert not nao_declaradas, (
            f"estes botões escrevem outra palavra que a do catálogo pt-BR do Qt sem dizer "
            f"por quê: {nao_declaradas}"
        )

    def test_nenhuma_divergencia_declarada_sobra_sem_uso(self) -> None:
        """Um motivo escrito para uma divergência que não existe mais é documentação mentindo."""
        strings = _strings()
        for enum, motivo in strings.DIVERGENCIAS_DECLARADAS.items():
            assert enum in strings.BOTOES_PADRAO, enum
            assert strings.BOTOES_PADRAO[enum] != strings.TRADUZIDOS_PELO_QT.get(enum), (
                f"{enum} não diverge mais do Qt: o motivo declarado ficou obsoleto"
            )
            assert len(motivo.strip()) > 40, f"{enum}: o motivo precisa dizer alguma coisa"

    def test_a_tabela_cobre_todo_botao_que_o_qt_traduz(self) -> None:
        """Dezoito de dezoito: nenhum `StandardButton` fica de fora numa máquina sem catálogo."""
        strings = _strings()
        assert set(strings.TRADUZIDOS_PELO_QT) <= set(strings.BOTOES_PADRAO)
        assert len(strings.BOTOES_PADRAO) == 18


class TestARegraDeNomeParouDeEscreverTexto:
    def test_ok_nao_e_mais_um_nome_sem_letras(self) -> None:
        """A exceção escrita que o ciclo 13 cobrou, cobrada de volta pelo teste."""
        controle = _controle_chamado("OK")
        assert controle.nome_vazio_de_sentido(repetidos=set()) == ""

    def test_os_glifos_continuam_reprovados(self) -> None:
        """A régua não afrouxou: ela continua pegando o que ela nasceu para pegar."""
        for glifo in ("-", "+", "|◀", "<", ">", "121", "..."):
            controle = _controle_chamado(glifo)
            assert controle.nome_vazio_de_sentido(repetidos=set()) == "sem letras", glifo

    def test_a_lista_de_excecoes_e_curta_e_nomeada(self) -> None:
        """Cada entrada é uma palavra que alguém teve de justificar por escrito."""
        assert frozenset({"ok"}) == teclado.PALAVRAS_CURTAS_LEGITIMAS


def _controle_chamado(nome: str) -> object:
    """Um `Controle` do portão de teclado com aquele nome desenhado, e nada mais."""
    return teclado.Controle(
        classe="QPushButton",
        nome=nome,
        papel="Botão",
        origem_do_nome="texto",
        alcancado_pelo_tab=True,
    )
