"""A fronteira que a ADR-0009 depende de manter: **`ui/` não conhece toolkit nenhum**.

**Por que isto é um teste e não uma convenção.** A ADR-0009 escolhe PyQt6 e deixa uma escotilha
de saída aberta: as ~13.000 linhas de `ui/` decidem, as ~14.000 de `qt/` desenham, e trocar de
toolkit é reescrever a segunda metade. A escotilha só continua aberta enquanto a fronteira é
real, e uma fronteira mantida por hábito dura até o primeiro `from PyQt6...` escrito com pressa
num arquivo de `ui/` -- que ninguém percebe, porque tudo continua funcionando na máquina de quem
o escreveu.

**O tronco já tem metade deste teste**, e só metade: `tests/test_editor_model.SemTkinterTests`
vigia `tkinter` e `PIL`, que eram o toolkit do frontend antigo. Nenhum teste vigia PyQt6 --
justamente o toolkit em uso --, e foi por isso que a folha de estilo pôde morar em `qt/` com o
conteúdo de `ui/` sem que nada reclamasse. Este arquivo fecha o outro lado, e vale para os quatro
bindings de Qt que existem para Python: um `from PySide6...` numa contribuição futura seria a
mesma quebra com outro nome.

**A varredura é sobre a árvore de importação, e não sobre o texto.** Vários módulos de `ui/`
citam `tkinter` ou `PyQt6` no docstring exatamente para dizer que eles não existem ali -- este
próprio arquivo cita --, e um `assertNotIn` sobre o texto reprovaria a explicação junto com o
defeito. É a mesma razão que o teste do tronco já registra, com um alvo a mais.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TOOLKITS: frozenset[str] = frozenset(
    {"PyQt6", "PyQt5", "PySide6", "PySide2", "tkinter", "wx", "gi", "kivy"}
)
"""Todo pacote que **abre janela**, e que `ui/` não pode importar.

Os quatro bindings de Qt que existem para Python, o `tkinter` do frontend anterior, e três que
o projeto nunca usou -- estes três estão aqui porque a fronteira é sobre a **categoria**, e a
contribuição que a quebrasse com `wx` a quebraria igual.

**`PIL` ficou de fora, e a ausência é uma decisão medida e não um esquecimento.** O teste do
tronco (`tests/test_editor_model.SemTkinterTests`) a vigia junto com o `tkinter`, e ali isso está
certo: ela era a companheira do `PhotoImage` do Tk. Depois do corte do frontend antigo (S-506) os
dois usos que sobraram em `ui/` são aritmética de imagem sem janela -- `pecas.engrossar_traco`,
que dilata o traço de um PNG, e `plataforma.compor_icone`, que monta o `.ico` do executável atrás
de um import guardado dentro da função. Nenhum dos dois pede um servidor gráfico, nenhum dos dois
muda se o toolkit mudar, e proibi-los aqui seria uma regra que só ensina a contorná-la.

O que a ADR-0009 precisa que continue verdade é mais estreito e mais duro: **nenhum módulo de
`ui/` importa o toolkit da janela, e nenhum importa `chess_diagram_ocr.qt`.** É o que os dois
testes abaixo afirmam."""

ISENTOS: dict[str, str] = {}
"""Arquivos de `ui/` que podem importar toolkit, com o motivo de cada um. **Vazio.**

E vazio é a afirmação: hoje **nenhum** dos 54 módulos de `ui/` importa binding de janela, e a
tabela existe para o dia em que alguém precisar de uma exceção ter de escrever o motivo dela
aqui, à vista, em vez de acrescentar um `# noqa` no arquivo. `test_nenhuma_isencao_sobra` cobra
o outro sentido: uma isenção que nomeie um arquivo que já saiu vira ruído com aparência de
permissão."""


def _pastas_de_ui(raiz: Path) -> Path:
    return raiz / "src" / "chess_diagram_ocr" / "ui"


def _importados(caminho: Path) -> set[str]:
    """Os pacotes de primeiro nível que este arquivo importa, pela árvore sintática."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module.split(".")[0])
    return nomes


def _modulos(raiz: Path) -> list[Path]:
    return sorted(p for p in _pastas_de_ui(raiz).glob("*.py") if p.name != "__init__.py")


def test_nenhum_modulo_de_ui_importa_toolkit(raiz_do_tronco: Path) -> None:
    """O portão. Um `from PyQt6...` em `ui/` fecha a escotilha da ADR-0009 sem avisar."""
    culpados = [
        f"{caminho.name}: {sorted(TOOLKITS & _importados(caminho))}"
        for caminho in _modulos(raiz_do_tronco)
        if caminho.name not in ISENTOS and TOOLKITS & _importados(caminho)
    ]
    assert culpados == [], "\n".join(
        ["Módulos de `ui/` que passaram a importar toolkit:", *culpados]
    )


def test_nenhum_modulo_de_ui_importa_o_pacote_do_toolkit_do_projeto(raiz_do_tronco: Path) -> None:
    """A outra direção da mesma fronteira: `ui/` não pode importar `chess_diagram_ocr.qt`.

    **Sem esta asserção a fronteira vaza por dentro.** Um módulo de `ui/` que importasse
    `qt/tema` não escreveria `PyQt6` em lugar nenhum e continuaria passando no teste de cima --
    e ainda assim precisaria de PyQt6 instalado para ser importado, que é a propriedade inteira
    que a separação existe para dar.
    """
    culpados = []
    for caminho in _modulos(raiz_do_tronco):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            alvo = ""
            if isinstance(no, ast.ImportFrom) and no.module:
                alvo = no.module
            elif isinstance(no, ast.Import):
                alvo = " ".join(alias.name for alias in no.names)
            if "chess_diagram_ocr.qt" in alvo:
                culpados.append(f"{caminho.name}:{no.lineno}: {alvo}")
    assert culpados == [], "\n".join(["Módulos de `ui/` que importam `qt/`:", *culpados])


def test_a_folha_de_estilo_e_a_paleta_moram_em_ui(raiz_do_tronco: Path) -> None:
    """A decisão de cor mora do lado que decide, e é o que faz o portão de contraste rodar aqui.

    Não é uma asserção sobre onde um arquivo está por gosto: enquanto `folha_de_estilo` morava
    em `qt/tema.py`, o venv desta suíte -- que **não tem binding de Qt** -- não conseguia
    importá-la, e o portão "WCAG AA em 100 % dos pares" do §11.3 não podia ser afirmado por
    teste nenhum deste lado.
    """
    modulo = _pastas_de_ui(raiz_do_tronco) / "folha_de_estilo.py"
    assert modulo.exists(), "ui/folha_de_estilo.py sumiu: o portão de contraste perde a fonte"
    fonte = modulo.read_text(encoding="utf-8")
    for nome in ("def folha_de_estilo(", "PAPEIS_DA_PALETA", "PAPEIS_DA_PALETA_MORTA"):
        assert nome in fonte, f"{nome} não está mais em ui/folha_de_estilo.py"


def test_nenhuma_isencao_sobra(raiz_do_tronco: Path) -> None:
    """Isenção que sobra é isenção que esconde: ela precisa nomear um arquivo que existe.

    Hoje `ISENTOS` está vazio e a asserção é trivial -- e é assim que ela deve ficar. Ela existe
    para o dia em que alguém precisar de uma exceção: no dia em que o arquivo isentado sair, a
    linha que o isentava sai junto, em vez de envelhecer como permissão para nada.
    """
    existentes = {caminho.name for caminho in _modulos(raiz_do_tronco)}
    orfas = sorted(set(ISENTOS) - existentes)
    assert orfas == [], f"isenções para arquivos que não existem mais: {orfas}"


def _arneses_de_auditoria() -> list[str]:
    """Todo módulo de `caissa/ui/audit/`, **lido da pasta** e não declarado (F9-C14).

    A lista era escrita à mão, com sete nomes. Um arnês novo -- `texto_pintado`, deste ciclo --
    nasceria fora dela e a disciplina "o Qt só entra dentro das funções" deixaria de ser cobrada
    nele em silêncio. É a mesma forma do defeito que reprovou os ciclos 9, 11 e 13, um andar
    abaixo: a régua certa sobre a população errada.
    """
    from caissa.ui import audit

    pasta = Path(audit.__file__).resolve().parent
    return sorted(
        caminho.stem for caminho in pasta.glob("*.py") if not caminho.stem.startswith("_")
    )


@pytest.mark.parametrize("modulo", _arneses_de_auditoria())
def test_o_arnes_de_auditoria_importa_sem_qt(modulo: str) -> None:
    """Os arneses sobem num venv sem binding nenhum -- é onde a CI os roda.

    **A asserção é o `import`, e ela é mais forte do que parece.** Um `from PyQt6...` no topo de
    qualquer um deles falharia aqui na hora; o que a disciplina exige é que o Qt só apareça
    dentro das funções que dirigem a janela, e é isso que este teste cobra a cada execução.
    """
    import importlib
    import sys

    alvo = importlib.import_module(f"caissa.ui.audit.{modulo}")
    assert alvo is not None
    assert not any(nome.startswith(("PyQt", "PySide")) for nome in sys.modules), (
        "importar o arnês trouxe um binding de Qt junto"
    )
