"""A higiene tipográfica do **catálogo de texto** do produto (F9-C16, §8 item 8).

**Marcação de Markdown vazando para texto de interface.** `ui/strings.COLECAO_VAZIA_FRASE`, escrita
no ciclo 14, mandava *"Escolha outro `.pgn`"* -- e as duas crases eram **desenhadas**, ampliadas no
retrato `c14_dialogo__JanelaDeColecao__Estudo___Abrir_P.png` do próprio construtor. É a mesma
família das aspas retas que esta frente caçou no ciclo 12 (`"` de máquina de escrever em 12 das 36
capturas).

E, na mesma varredura, o crítico do ciclo 15 contou **13 textos desenhados com três pontos ASCII**
contra 19 literais com `…` -- inclusive `Aplicar aos vizinhos...`, desenhado num retrato daquele
ciclo, enquanto o menu que abre a mesma janela escreve `Colar posição ou partida…`.

---

**A população deste teste é o catálogo, e digo o que ela não alcança.** Ele lê as constantes de
texto de `ui/strings.py` -- as atribuições de módulo cujo valor é uma cadeia (ou um
`sem_orfa(...)` em volta de uma). Ficam de fora, e é decisão:

* os **dicionários** (`SIDE_LABELS`, `TRADUZIDOS_PELO_QT`, `DIVERGENCIAS_DECLARADAS`): o último
  guarda a **razão escrita** de uma divergência, que é prosa de manutenção e não texto de tela, e
  separá-los por nome seria a lista escrita à mão que esta frente já pagou três vezes para tirar
  de dentro de um teste;
* os literais montados dentro de `qt/`, que são muitos e não passam por aqui.

Quem cobre os dois é a **tela**, e com número publicado:
`benchmarks/reports/ui/c16/c16_rotulos_de_campo.py` mede os 117 rótulos desenhados das seis abas
nas três peles (0 crases, 0 reticências ASCII) e
`benchmarks/reports/ui/c16/c16_retratar_os_dialogos.py` lista os botões desenhados dos treze
diálogos. Este teste é a metade que roda sem Qt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

CRASE = "`"
TRES_PONTOS = "..."
RETICENCIA = "…"


def _catalogo(raiz: Path) -> list[tuple[str, int, str]]:
    """`(nome, linha, texto)` de cada constante de texto de `ui/strings.py`.

    Só atribuição de módulo com valor de cadeia -- incluindo `sem_orfa("…")`, que é como este
    catálogo escreve frase longa. Ver o cabeçalho para o que fica de fora e por quê.
    """
    arquivo = raiz / "src" / "chess_diagram_ocr" / "ui" / "strings.py"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    achados: list[tuple[str, int, str]] = []
    for no in arvore.body:
        if not isinstance(no, (ast.Assign, ast.AnnAssign)):
            continue
        alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
        nomes = [a.id for a in alvos if isinstance(a, ast.Name)]
        if not nomes or no.value is None:
            continue
        valor = no.value
        if isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name):
            # `sem_orfa("…")` -- o embrulho que este catálogo usa para não deixar órfã.
            valor = valor.args[0] if valor.args else valor
        if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
            achados.append((nomes[0], no.lineno, valor.value))
    return achados


@pytest.fixture(scope="module")
def catalogo(raiz_do_tronco: Path) -> list[tuple[str, int, str]]:
    achados = _catalogo(raiz_do_tronco)
    assert len(achados) >= 30, f"o catálogo encolheu para {len(achados)} constantes de texto"
    return achados


def test_nenhuma_crase_de_markdown_em_texto_desenhado(catalogo) -> None:
    """`` `.pgn` `` chegava à tela com os dois acentos graves. Aspas angulares é o que se usa aqui."""
    com_crase = [(nome, linha, texto) for nome, linha, texto in catalogo if CRASE in texto]
    assert not com_crase, (
        "marcação de Markdown em texto de interface: "
        + ", ".join(f"{nome} (strings.py:{linha})" for nome, linha, _ in com_crase)
    )


def test_nenhuma_reticencia_de_tres_pontos_em_texto_desenhado(catalogo) -> None:
    """13 textos usavam `...` enquanto 19 literais usavam `…`. Um só caractere, e é o certo."""
    com_pontos = [(nome, linha, texto) for nome, linha, texto in catalogo if TRES_PONTOS in texto]
    assert not com_pontos, (
        "reticência de três pontos ASCII em texto de interface: "
        + ", ".join(f"{nome} (strings.py:{linha})" for nome, linha, _ in com_pontos)
    )


def test_o_produto_de_fato_usa_a_reticencia_certa(catalogo, raiz_do_tronco: Path) -> None:
    """A prova de que "0 três pontos" não é "0 reticências": o caractere certo está em uso.

    Sem esta linha, apagar toda reticência do produto faria os dois testes acima passarem.
    """
    fonte = (raiz_do_tronco / "src" / "chess_diagram_ocr" / "ui" / "strings.py").read_text(
        encoding="utf-8"
    )
    assert fonte.count(RETICENCIA) >= 5, "o catálogo perdeu as reticências em vez de as consertar"


def test_a_frase_da_colecao_vazia_perdeu_as_crases_e_continua_dizendo_o_mesmo(
    raiz_do_tronco: Path,
) -> None:
    """O defeito nomeado, pelo nome. A frase tem de continuar nomeando o formato do arquivo."""
    import sys

    if str(raiz_do_tronco / "src") not in sys.path:
        sys.path.insert(0, str(raiz_do_tronco / "src"))
    from chess_diagram_ocr.ui import strings

    assert CRASE not in strings.COLECAO_VAZIA_FRASE
    assert ".pgn" in strings.COLECAO_VAZIA_FRASE, "tirar a crase não é tirar a informação"


def test_a_reticencia_do_lance_preto_e_notacao_e_nao_tipografia(raiz_do_tronco: Path) -> None:
    """**O único `...` que fica, e ele fica declarado.**

    `ui/estudo_lista.py:225` escreve `f"{fullmove}... "` -- `12... Nf6`, a numeração de um lance
    das pretas em PGN. São três pontos por convenção de notação de xadrez, como no arquivo `.pgn`
    de onde a linha vem, e trocá-los por `…` faria a lista de lances divergir do texto que ela
    representa. Está aqui para que "0 reticências ASCII em texto desenhado" seja uma afirmação
    com a exceção nomeada, e não uma afirmação com um buraco.
    """
    fonte = (raiz_do_tronco / "src" / "chess_diagram_ocr" / "ui" / "estudo_lista.py").read_text(
        encoding="utf-8"
    )
    assert 'f"{board.fullmove_number}... "' in fonte
