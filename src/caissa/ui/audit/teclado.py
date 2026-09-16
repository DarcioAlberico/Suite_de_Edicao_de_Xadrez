r"""Navegação só com o teclado e nome acessível em todo controle (SPEC §10.6 e §11.3).

**A promessa é "atalhos de teclado para tudo", e uma promessa dessas se quebra em silêncio.** O
mouse continua funcionando enquanto ela está quebrada: ninguém descobre que a aba Galeria tem um
botão inalcançável por `Tab` até a pessoa que não usa mouse chegar nela. Por isso este módulo não
lê o código -- ele **anda** pela janela como um teclado andaria, e reporta onde parou.

---

**Três instrumentos, e cada um responde a uma pergunta diferente.**

1. **A volta do `Tab`.** `QWidget.focusNextPrevChild(True)` é exatamente o que o Qt faz quando a
   tecla é apertada, e chamá-lo em laço percorre a cadeia de foco de verdade -- com as regras de
   `focusPolicy`, de `setTabOrder` e de proxy que a janela montou. O que se mede é: quantos
   controles focáveis existem, quantos a volta alcança, e se ela **fecha** (volta ao ponto de
   partida) em vez de parar num beco.

2. **O nome acessível, e se ele nomeia.** Um leitor de tela anuncia `accessibleName()`; quando ele
   está vazio o Qt cai no texto do widget, e quando nem isso existe o controle é anunciado como o
   tipo dele -- "botão", sem dizer qual. O instrumento aceita as três fontes na ordem em que o Qt
   as consulta, e reprova quem não tem **nenhuma**: exigir `accessibleName` explícito num botão
   escrito "Salvar PGN" seria burocracia, porque o nome já está lá.

   **E reprova, desde o ciclo 2, o nome que não nomeia.** A versão anterior media `bool(nome)`, e
   o crítico mostrou o preço exato: 34 de 256 controles (13,3 %) passavam no portão anunciando
   `"121"` (o **valor** de um spinner, que muda quando a pessoa vira a página), `"-"`, `"+"`,
   `"|◀"`, `"Escolha"` (cinco controles diferentes, três deles na mesma aba) e `"Lista"`. Uma
   pessoa cega ouve "121" e não aprende nada. `nome_vazio_de_sentido` é o portão que faltava, e
   ele reprova pelos motivos declarados em `MOTIVOS_DE_NOME_VAZIO`: eco do papel, sem letras,
   repetido na aba, o valor do próprio controle, prosa em vez de nome, e -- desde o ciclo 10 --
   **quebra de linha no nome**, que é o leiaute vazando para o anúncio. **Uma métrica que passa
   enquanto a coisa que ela mede está quebrada é pior que métrica nenhuma.**

3. **O papel.** `PyQt6` **não empacota `QAccessible`** -- conferido neste venv, o nome não existe
   em `QtGui`, `QtWidgets` nem `QtCore` --, então o papel não pode ser perguntado ao Qt daqui. Ele
   é derivado de `PAPEL_POR_CLASSE`, uma tabela do que o `QAccessibleWidget` de cada classe
   reporta ao sistema. O que ela pega é o defeito que importa: um `QLabel` que recebe foco e
   responde a clique continua sendo anunciado como **texto estático**, e um leitor de tela nunca
   diz que dá para clicar nele.

**O que este módulo não afirma.** Que a ordem do `Tab` é *boa* -- que ela segue a leitura da tela.
Isso é julgamento, e um número não o substitui; o relatório lista a ordem inteira para quem quiser
julgá-la. O que ele afirma é que a ordem **existe, é completa e fecha**.

Uso:

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \\
    PYTHONPATH=<tronco>/src;<suite>/src \\
    <tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.teclado
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` só existe no 3.11, e o venv do **tronco** -- que é onde o PyQt6 mora
(ADR-0009) -- é 3.10. O alias deixa o resto do módulo escrito na forma nova e faz o arnês rodar
nos dois interpretadores.

**Escrito como `timezone(timedelta(0))` e não como `timezone.utc`, e isso foi aprendido do jeito
caro.** O `ruff --fix` desta suíte tem alvo py311: ele reescreve `timezone.utc` como
`datetime.UTC` e acrescenta o `import` correspondente -- que é exatamente o `import` que morre no
3.10. Um `# noqa` não protege, porque a regra pega o **uso** e não a linha do alias. A forma
construída é idêntica por definição (`timezone(timedelta(0)) is timezone.utc`) e não tem por onde
ser reescrita. A regra está certa para o resto do repositório; aqui ela quebrava o arnês."""

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")
PASTA_DE_FONTES = r"C:\Windows\Fonts"

CONTROLES_LISTADOS = 12
"""Quantos controles a tabela do terminal lista por categoria antes de resumir o resto.

O JSON tem todos; esta é a leitura de relance, e uma lista de sessenta linhas no terminal deixa
de ser leitura de relance."""

TETO_DE_VOLTAS = 4000
"""Quantos `Tab` no máximo antes de desistir de fechar a volta.

A janela tem ~250 controles focáveis por aba; 4.000 é uma folga de mais de uma ordem de grandeza
e ainda assim termina em menos de um segundo. O teto existe porque uma cadeia de foco quebrada
**não** fecha, e um laço sem teto viraria um travamento no lugar de um defeito reportado."""

PAPEL_POR_CLASSE: dict[str, str] = {
    "QPushButton": "Button",
    "QToolButton": "Button",
    "QCheckBox": "CheckBox",
    "QRadioButton": "RadioButton",
    "QComboBox": "ComboBox",
    "QLineEdit": "EditableText",
    "QTextEdit": "EditableText",
    "QPlainTextEdit": "EditableText",
    "QSpinBox": "SpinBox",
    "QDoubleSpinBox": "SpinBox",
    "QAbstractSpinBox": "SpinBox",
    "QSlider": "Slider",
    "QProgressBar": "ProgressBar",
    "QTreeWidget": "Tree",
    "QTreeView": "Tree",
    "QTableWidget": "Table",
    "QTableView": "Table",
    "QListWidget": "List",
    "QListView": "List",
    "QTabBar": "PageTabList",
    "QTabWidget": "PageTabList",
    "QMenuBar": "MenuBar",
    "QMenu": "PopupMenu",
    "QScrollBar": "ScrollBar",
    "QSplitterHandle": "Splitter",
    "QGroupBox": "Grouping",
    "QLabel": "StaticText",
    "QScrollArea": "Pane",
    "QAbstractScrollArea": "Pane",
    "QFrame": "Pane",
    "QWidget": "Pane",
}
"""Classe de widget -> papel que o `QAccessibleWidget` do Qt reporta ao sistema.

**Existe porque `PyQt6` não empacota `QAccessible`**, e foi conferido neste venv antes de a
tabela ser escrita: o nome não está em `QtGui`, `QtWidgets` nem `QtCore`. Perguntar ao Qt seria
melhor; não perguntar seria não medir. A tabela é fato da biblioteca -- é o mapa de
`qaccessiblewidgets.cpp` --, e não uma escolha nossa.

**`StaticText` e `Pane` estão aqui de propósito, e são o que a auditoria procura.** Um controle
que recebe foco de teclado e reporta um desses dois papéis é um controle que o leitor de tela
anuncia como se não fosse clicável -- e é isso que `PAPEIS_NAO_INTERATIVOS` reprova."""

PAPEIS_NAO_INTERATIVOS: frozenset[str] = frozenset({"StaticText", "Pane", "NoRole", ""})
"""Papéis que não anunciam "isto se opera".

Um widget focável com um destes é o defeito: ou ele não devia aceitar foco, ou ele devia ser a
classe do que ele faz. As exceções declaradas em `SEM_NOME_POR_NATUREZA` também saem daqui --
uma superfície de desenho que aceita foco de teclado para receber setas é um `Pane` legítimo."""

SEM_NOME_POR_NATUREZA: tuple[str, ...] = (
    "QScrollBar",
    "QSplitterHandle",
    "QTabBar",
    "_Folha",
    "Visor",
)
"""Classes cujo nome acessível vem de outro lugar, e cobrá-lo aqui produziria ruído.

A barra de rolagem e o divisor são anunciados pelo **papel** (`ScrollBar`, `Splitter`), que já
diz tudo o que há para dizer; a `QTabBar` é anunciada pelas abas que ela contém, uma a uma; e a
folha do visor é a superfície de desenho da página, cujo conteúdo é a imagem e não um rótulo.

A lista é curta de propósito. Toda isenção aqui é um controle que um leitor de tela vai anunciar
sem nome, e a régua para entrar nela é "o papel sozinho já responde qual é este controle"."""


# ------------------------------------------------- o nome que não nomeia (portão do ciclo 2)

ECO_DO_PAPEL: dict[str, tuple[str, ...]] = {
    "List": ("lista", "list"),
    "Table": ("tabela", "table", "grade"),
    "Tree": ("tabela", "árvore", "arvore", "tree"),
    "ComboBox": ("escolha", "caixa de escolha", "seleção", "selecao", "combo", "opções", "opcoes"),
    "EditableText": ("campo", "campo de texto", "editor", "editor de texto", "texto", "edição", "edicao"),
    "Button": ("botão", "botao", "button"),
    "CheckBox": ("caixa", "caixa de seleção", "caixa de selecao", "marca"),
    "RadioButton": ("opção", "opcao", "rádio", "radio"),
    "SpinBox": ("número", "numero", "valor", "campo de número", "campo de numero"),
    "Slider": ("régua", "regua", "deslizador", "barra"),
    "PageTabList": ("abas", "aba", "guias"),
    "Pane": ("painel", "área", "area", "região", "regiao"),
}
"""Papel -> as palavras que **só repetem o papel**, em minúsculas e sem pontuação.

**Este é o motivo (a) do portão, e a régua é exata:** um nome acessível existe para dizer *qual*
controle é este, e o leitor de tela já anuncia o papel logo em seguida. `"Escolha, caixa de
escolha"` gasta duas palavras para não dizer nada; `"Filtro por conjunto, caixa de escolha"` diz.

As entradas saem de `ui/nomes_acessiveis.POR_CLASSE` do tronco -- o último degrau da cascata,
cujo próprio docstring declara que os nomes ali são "genéricos de propósito". Eles são a resposta
certa para um controle que **não tem** rótulo na tela; são a resposta errada para o portão, porque
o portão pergunta se a pessoa aprende alguma coisa ao ouvi-los. A tabela é escrita aqui, e não
importada, para que o portão seja afirmável mesmo se o tronco não estiver no caminho -- e para que
acrescentar um nome genérico lá não afrouxe o portão aqui em silêncio.

`"Régua de zoom"` e `"Página do livro"` **não** estão na lista, e a diferença é o que se aprende:
"zoom" diz o que a régua move, "livro" diz de que é a página. `"Régua"` sozinha, não."""

CLASSES_COM_VALOR: frozenset[str] = frozenset(
    {"QSpinBox", "QDoubleSpinBox", "QAbstractSpinBox", "QSlider", "QProgressBar", "QLineEdit"}
)
"""Classes cujo `text()` é o **conteúdo** e não a identidade -- o motivo (d) do portão.

`QSpinBox.text()` devolve `"121"`, e a cascata do nome acessível cai em `text()` quando não há
`accessibleName`. O resultado é pior que não ter nome: o leitor anuncia "121, campo de número", e
o **nome do controle muda quando a pessoa vira a página**. A identidade do objeto passa a ser o
conteúdo dele, que é a definição de não ter identidade.

Um `QPushButton` escrito "Salvar" **não** está aqui, e a diferença é que o texto de um botão é o
que ele faz -- ele não muda quando o documento muda."""

MOTIVOS_DE_NOME_VAZIO: tuple[str, ...] = (
    "eco do papel",
    "sem letras",
    "repetido na aba",
    "o valor do proprio controle",
    "e prosa, nao nome",
    "quebra de linha no nome",
)
"""Os motivos pelos quais um nome não nomeia. Existe para o teste afirmar a lista fechada.

**O sexto entrou porque a prova de vida do ciclo 10 o cobrou, e ele estava faltando havia dois
ciclos.** Sabotei a fita apagando o `setAccessibleName` que este ciclo pôs nela -- que é
exatamente o defeito do ciclo 9 reposto -- e o portão continuou devolvendo `PASSOU`. A razão: sem
nome próprio a cascata cai no `text()`, e o texto de um botão da fita é
`quebrar_rotulo("Abrir PDF")` = **`"Abrir\nPDF"`**. Aquilo tem letras, não é eco do papel, não é
o valor do controle, não é prosa -- e **não bate com `"Abrir PDF"`**, então nem repetido ficava.

Uma quebra de linha num nome acessível é o **leiaute vazando para o anúncio**: ela existe porque
o botão tem duas linhas de altura, e um leitor de tela lê `"Abrir, PDF"` com uma pausa no meio.
E foi ela que mascarou, até este ciclo, os onze nomes da fita que batem com os da barra do visor:
o portão comparava `"Abrir\nPDF"` com `"Abrir PDF"` e não via repetição nenhuma."""

FORA_DA_VARREDURA = (
    "fora da varredura sintatica: QDialog construido em linha (painel_de_estudo.ampliar_recorte, "
    "S-282) e toda QMessageBox; quem os prepara e' o filtro de QEvent.Show de qt/acessibilidade."
)
"""O que a lista do portão **não** alcança, publicado ao lado do número que ela alcança (F9-C14).

**A largura de um portão é uma afirmação, e esta estava maior que a medição.** A varredura de
`qt.dialogos_do_produto` lê `class X(QDialog)` da árvore sintática; um `QDialog(self)` construído
dentro de um método não tem classe para ler, e as oito formas de `QMessageBox` que o produto
levanta também não. As nove telas estão limpas -- o crítico do ciclo 13 mediu: 14 botões, 0 em
inglês, 0 sem nome --, e estão limpas **porque o remédio mora no `QEvent.Show`** e não numa
lista. Esta frase é o que impede alguém de ler o número do portão como se fosse o total."""

LETRAS_MINIMAS = 3
"""Quantos caracteres alfabéticos seguidos um nome precisa ter para ser palavra.

`"-"`, `"+"`, `"|◀"`, `"<"`, `">"` e `"121"` têm zero; `".md"` tem dois. Três é onde começa a
palavra mais curta que este produto usa (`"PGN"`, `"OCR"`, `"FEN"`) -- ou seja, o piso foi posto
onde a sigla legítima mais curta ainda passa.

**E é aqui que ele parou de valer para o que não é glifo.** Ver `PALAVRAS_CURTAS_LEGITIMAS`."""

PALAVRAS_CURTAS_LEGITIMAS: frozenset[str] = frozenset({"ok"})
"""Palavras de menos de `LETRAS_MINIMAS` letras que **nomeiam**, e por isso passam.

**A exceção que o ciclo 13 cobrou, e ela é escrita porque a régua sem ela custou 32 telas.**
`LETRAS_MINIMAS` nasceu no ciclo 1 para reprovar `-`, `+` e `◀` -- glifos que não anunciam nada.
No ciclo 12 ela foi usada como argumento para **escrever** um texto na tela: `ui/strings` trocou
o `OK` do botão único de uma caixa de aviso por `Confirmar`, em 32 chamadas de
`information`/`critical`/`warning`/`about`, incluindo a de *Sobre o produto*. Confirmar o quê?

`OK` não é um glifo: é a palavra que o Windows em pt-BR usa, que o catálogo do próprio Qt usa
(`ui/strings.TRADUZIDOS_PELO_QT`) e que todo leitor de tela pronuncia. Uma régua de **nome
acessível** aplicada a **texto desenhado** escreveu a palavra errada; a régua continua valendo
para glifo, e passa a ter uma lista curta e nomeada do que é palavra apesar de curto.

A lista é curta de propósito: cada entrada é uma palavra que alguém teve de justificar."""


def _sem_pontuacao(nome: str) -> str:
    """O nome em minúsculas, sem pontuação de leiaute nem reticências. Puro."""
    limpo = "".join(caractere for caractere in nome if caractere.isalnum() or caractere.isspace())
    return " ".join(limpo.casefold().split())


LETRAS_MAXIMAS_DE_UM_NOME = 48
"""Acima disto um nome acessível deixou de nomear e passou a explicar (F9-C3).

**O quinto motivo, e o defeito que o pediu está em seis abas.** O `QComboBox` de regime
(`qt/campo.py`) não tinha `accessibleName`, a cascata caiu na **dica**, e o leitor de tela
anunciava, no 14º lugar da ordem do `Tab` de todas as seis abas:

    "Em que condição esta página foi lida. Entra na anotação e separa as"

-- **67 caracteres terminando no meio da frase**, porque o Qt corta a dica. Os quatro motivos
anteriores do portão (eco do papel, menos de três letras, repetido na aba, o próprio valor)
aprovavam isso: é longo, tem letras, é único e não é o valor.

Quarenta e oito e não trinta: `"Varrer o livro para encher a galeria"` tem 36 e é um nome
legítimo -- ele diz o que o controle faz, com o objeto direto. O teto foi posto acima do nome
verdadeiro mais longo que a janela tem hoje, e abaixo da frase de ajuda mais curta que ela
escreve."""


def _e_prosa(nome: str, *, e_o_texto_desenhado: bool = False) -> bool:
    """O nome é uma frase de ajuda em vez de um nome. Puro. Ver `LETRAS_MAXIMAS_DE_UM_NOME`.

    Dois sinais, e cada um sozinho basta:

    - **um ponto final seguido de espaço** -- um nome não tem duas orações;
    - **comprimento** acima de `LETRAS_MAXIMAS_DE_UM_NOME`.

    A pontuação vem primeiro porque ela é o sinal forte: `"Isto faz X. Aquilo faz Y"` é prosa com
    qualquer comprimento. E o teto sozinho não bastaria: a frase que o portão deixou passar em seis
    abas **estava truncada em 67 caracteres pelo Qt**, sem ponto nenhum no fim.

    **O teto não vale quando o nome é o texto que está desenhado no controle** (F9-C12), e a
    razão é a WCAG 2.5.3. O defeito que criou este motivo era uma **dica** vazando para o
    anúncio: o rótulo na tela dizia uma coisa e o leitor de tela lia outra, mais longa. Quando o
    nome **é** o rótulo desenhado, o leitor de tela está lendo o que a pessoa vidente lê, e a
    2.5.3 exige justamente isso. O caso medido é a caixa de marcar de `DialogoDeBases`, cujo
    rótulo é um nome de arquivo de 66 caracteres
    (`Endgame_Study_Database_VI_Harold_van_der_Heijden_December_2020.pgn`): encurtá-lo tiraria
    a única coisa que distingue uma base da outra. O sinal do ponto final continua valendo para
    todo mundo -- um botão cuja legenda tem duas orações é defeito na tela também.
    """
    if ". " in nome:
        return True
    return not e_o_texto_desenhado and len(nome.strip()) > LETRAS_MAXIMAS_DE_UM_NOME


def _letras_seguidas(nome: str, quantas: int = LETRAS_MINIMAS) -> bool:
    """Se há `quantas` letras seguidas em algum ponto do nome. Puro, e Unicode.

    `str.isalpha` e não uma classe de regex ASCII: `"Revisão"`, `"Página"` e `"Ação"` são
    palavras, e um portão que as reprovasse mediria o alfabeto e não o significado."""
    seguidas = 0
    for caractere in nome:
        seguidas = seguidas + 1 if caractere.isalpha() else 0
        if seguidas >= quantas:
            return True
    return False


# ------------------------------------------------------------------ o que se acha (sem Qt)


@dataclass(frozen=True)
class Controle:
    """Um controle focável da janela, e o que a API de acessibilidade diz sobre ele."""

    classe: str
    nome: str
    """O que um leitor de tela anuncia: `accessibleName`, senão o texto, senão vazio."""

    origem_do_nome: str
    """`accessibleName`, `texto`, `dica` ou `nenhuma` -- de onde o nome saiu."""

    papel: str
    """O `QAccessible.Role`, pelo nome. `NoRole` é o defeito."""

    alcancado_pelo_tab: bool

    grupo: str = ""
    """O `accessibleName` do contêiner **nomeado** mais próximo acima deste controle.

    **É a metade do anúncio que o portão não lia** (F9-C10). O produto declara este modelo desde
    o ciclo 2, e está escrito no docstring de `qt/painel_do_pdf._bloco`: *"o nome do bloco é o que
    um leitor de tela anuncia ao entrar nele -- sem ele a pessoa ouve doze botões seguidos sem
    saber onde um grupo acaba"*. Quem entra num bloco ouve **"Navegar, grupo"** e depois
    **"Página anterior, botão"**; o portão comparava só a segunda metade.

    Vazio quando não há contêiner nomeado acima -- e isso é informação, não ausência: era o caso
    de **todos** os botões do cromo (a fita e a fila) até este ciclo, e é por isso que eles
    chegavam ao leitor de tela indistinguíveis dos botões do painel que fazem a mesma coisa."""

    posicao_no_tab: int = -1
    """Em que passo da volta ele apareceu. `-1` quando a volta não passou por ele."""

    politica: str = ""
    """A `focusPolicy` do widget, pelo nome. Decide se ele **deve** estar na volta do `Tab`."""

    por_seta: bool = False
    """Se ele é alcançado pelas **setas** e não pelo `Tab`, por estar num grupo exclusivo.

    **Não é uma desculpa, é a regra do Qt e a da plataforma.** Num grupo de escolha exclusiva
    (`autoExclusive`), só o botão marcado entra na cadeia do `Tab`; as setas movem a escolha
    dentro do grupo. É assim no Windows, no macOS e no que a WCAG 2.1.1 chama de navegação por
    teclado -- um grupo de rádio é **um** ponto de parada, não seis. Contar os cinco não marcados
    como inalcançáveis produziria um defeito por grupo de escolha da janela inteira, e enterraria
    os de verdade."""

    def nome_qualificado(self) -> str:
        """O anúncio inteiro: o grupo e o nome, como um leitor de tela os diz. Puro.

        **É contra isto que "repetido na aba" passa a ser medido**, e a mudança é de escopo e não
        de rigor: dois controles com o mesmo nome dentro do **mesmo** grupo continuam reprovando,
        e um controle que não estiver em grupo nomeado nenhum continua sendo comparado pelo nome
        cru -- que é a situação em que a repetição é de fato ambígua.

        A régua nova **cobra do produto uma coisa a mais**: nomear os grupos. Enquanto a fita não
        nomeava os dela, os vinte e quatro botões dela colidiam com os da barra do visor e o
        portão acusava; nomeados, o anúncio passa a dizer onde o botão está, que é o que faltava
        para a pessoa saber qual dos dois ela alcançou.
        """
        return f"{self.grupo}: {self.nome}" if self.grupo else self.nome

    def so_por_ponteiro(self) -> bool:
        """Região de texto que só o ponteiro foca, e é assim que o Qt e a plataforma a tratam.

        **`ClickFocus` num papel não interativo não é defeito, e a distinção importa.** O painel
        "Detalhes do diagrama" recebe foco de clique porque o texto dele é selecionável -- é de
        onde se copia a explicação de por que a posição é ilegal --, e o Qt deixa `ClickFocus`
        **fora** da cadeia do `Tab` de propósito, em toda plataforma. A WCAG 2.1.1 pede que a
        *funcionalidade* seja operável por teclado; o conteúdo de um texto estático chega ao
        leitor de tela pela árvore de acessibilidade, com o nome que ele tem, sem precisar de
        parada de tabulação. Um **botão** com `ClickFocus` continua sendo defeito -- por isso a
        isenção exige também o papel não interativo.
        """
        return self.politica == "ClickFocus" and self.papel in PAPEIS_NAO_INTERATIVOS

    def alcancavel(self) -> bool:
        return self.alcancado_pelo_tab or self.por_seta or self.so_por_ponteiro()

    def anonimo(self) -> bool:
        return not self.nome and self.classe not in SEM_NOME_POR_NATUREZA

    def nome_vazio_de_sentido(self, repetidos: Sequence[str] = ()) -> str:
        """Por que este nome não nomeia, ou `""` quando ele nomeia. Puro.

        `repetidos` são os nomes que aparecem mais de uma vez **na mesma aba** -- é a aba que
        sabe disso, e não o controle, e por isso ela chega de fora.

        A ordem dos motivos é a do quanto cada um é grave, e o primeiro que casar responde: um
        nome que é o valor do controle já é errado antes de alguém contar as letras dele.
        """
        if self.classe in SEM_NOME_POR_NATUREZA or not self.nome:
            return ""  # ausência de nome é `anonimo()`, e é outro defeito e outra linha
        if self.origem_do_nome == "texto" and self.classe in CLASSES_COM_VALOR:
            return "o valor do proprio controle"
        curta_mas_palavra = _sem_pontuacao(self.nome) in PALAVRAS_CURTAS_LEGITIMAS
        if not _letras_seguidas(self.nome) and not curta_mas_palavra:
            return "sem letras"
        if _sem_pontuacao(self.nome) in ECO_DO_PAPEL.get(self.papel, ()):
            return "eco do papel"
        if "\n" in self.nome or "\r" in self.nome:
            return "quebra de linha no nome"
        if self.nome_qualificado() in repetidos:
            return "repetido na aba"
        if _e_prosa(self.nome, e_o_texto_desenhado=self.origem_do_nome == "texto"):
            return "e prosa, nao nome"
        return ""

    def sem_papel(self) -> bool:
        """Papel que não anuncia "isto se opera" **e** sem nome que diga o que é.

        **O nome resgata o papel, e é a regra certa.** A superfície onde a página do livro é
        desenhada é um `Pane` -- é o que ela é, e é o papel que a WAI-ARIA chama de `region`. Um
        `Pane` **nomeado** ("Página do livro") é anunciado como uma região navegável, que é
        exatamente o que ela é; um `Pane` anônimo é um retângulo que o leitor de tela não sabe
        descrever. O defeito é o anonimato, não o papel.
        """
        return (
            self.papel in PAPEIS_NAO_INTERATIVOS
            and not self.nome
            and self.classe not in SEM_NOME_POR_NATUREZA
        )


@dataclass
class Aba:
    """O resultado de uma aba: os controles dela e o que a volta do `Tab` fez."""

    nome: str
    controles: list[Controle] = field(default_factory=list)
    passos_ate_fechar: int = 0
    fechou: bool = False
    """Se a volta voltou ao ponto de partida dentro do teto. Uma cadeia quebrada não fecha."""

    def focaveis(self) -> int:
        return len(self.controles)

    def alcancados(self) -> int:
        return sum(1 for controle in self.controles if controle.alcancavel())

    def inalcancaveis(self) -> list[Controle]:
        return [controle for controle in self.controles if not controle.alcancavel()]

    def anonimos(self) -> list[Controle]:
        return [controle for controle in self.controles if controle.anonimo()]

    def sem_papel(self) -> list[Controle]:
        return [controle for controle in self.controles if controle.sem_papel()]

    def repetidos(self) -> list[str]:
        """Os **anúncios** que dois ou mais controles visíveis nesta aba fazem. Motivo (c).

        A contagem é por aba e não pela janela: dois botões "Remover" em duas abas diferentes
        nunca são ouvidos um depois do outro, e reprová-los mediria a janela inteira contra uma
        regra que só faz sentido dentro de uma tela. Três `"Escolha"` na aba Dataset, sim.

        **E é o anúncio inteiro, e não só o nome do controle** (F9-C10). Ver
        `Controle.nome_qualificado`: um leitor de tela diz o grupo antes do controle, e o produto
        declara esses grupos desde o ciclo 2 (`qt/painel_do_pdf._bloco`). Comparar só a segunda
        metade fazia duas coisas erradas ao mesmo tempo -- deixava passar dois "Escolha" postos em
        grupos que ninguém nomeou, e acusava o botão da fita ao lado do botão do painel que o
        próprio desenho põe em dois lugares de propósito.
        """
        vistos: dict[str, int] = {}
        for controle in self.controles:
            if controle.nome and controle.classe not in SEM_NOME_POR_NATUREZA:
                anuncio = controle.nome_qualificado()
                vistos[anuncio] = vistos.get(anuncio, 0) + 1
        return sorted(nome for nome, quantos in vistos.items() if quantos > 1)

    def nomes_vazios(self) -> list[tuple[Controle, str]]:
        """Os controles cujo nome não nomeia, com o motivo. É o portão do ciclo 2."""
        repetidos = self.repetidos()
        with_motivo = ((c, c.nome_vazio_de_sentido(repetidos)) for c in self.controles)
        return [(controle, motivo) for controle, motivo in with_motivo if motivo]

    def passou(self) -> bool:
        return (
            self.fechou
            and not self.inalcancaveis()
            and not self.anonimos()
            and not self.sem_papel()
            and not self.nomes_vazios()
        )


def _como_json(aba: Aba) -> dict[str, Any]:
    """Uma superficie medida, na forma do relatorio. Serve aba e dialogo, e e de proposito.

    **A mesma regua e o mesmo formato**: quem le o JSON nao precisa aprender duas gramaticas
    para descobrir que a paleta de comandos tinha dois controles sem nome e a aba Texto nao
    tinha nenhum."""
    return {
        "nome": aba.nome,
        "focaveis": aba.focaveis(),
        "alcancados_pelo_tab": aba.alcancados(),
        "a_volta_fecha": aba.fechou,
        "passos": aba.passos_ate_fechar,
        "sem_nome": [asdict(c) for c in aba.anonimos()],
        "sem_papel": [asdict(c) for c in aba.sem_papel()],
        "nome_vazio_de_sentido": [
            {**asdict(c), "motivo": motivo} for c, motivo in aba.nomes_vazios()
        ],
        "nomes_repetidos": aba.repetidos(),
        "inalcancaveis": [asdict(c) for c in aba.inalcancaveis()],
        "ordem_do_tab": [
            f"{c.posicao_no_tab:>4} {c.classe}: {c.nome or '(sem nome)'}"
            for c in sorted(aba.controles, key=lambda c: c.posicao_no_tab)
            if c.posicao_no_tab >= 0
        ],
        "veredito": "PASSOU" if aba.passou() else "REPROVOU",
    }


def veredito(abas: Sequence[Aba]) -> str:
    return "PASSOU" if all(aba.passou() for aba in abas) else "REPROVOU"


# ---------------------------------------------------------------------- a janela (Qt aqui)


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if Path(PASTA_DE_FONTES).is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", PASTA_DE_FONTES)
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def _descartar(janela: Any, aplicacao: Any) -> None:
    """Fecha a janela e **destrói o C++ agora**, em vez de "quando a linha de eventos girar".

    **Sem isto a terceira pele derruba o processo, e o sintoma não é um traceback.** O portão
    passou a montar uma janela por pele (F9-C9); a segunda janela morria por coleta de lixo do
    Python enquanto o Qt ainda tinha `DeferredDelete` pendentes dela, e a terceira abortava no
    meio da aba Texto sem escrever uma linha. `processEvents` não esvazia essa fila -- a
    documentação do Qt diz que só a linha de eventos principal a esvazia --, e quem a esvazia à
    mão é `sendPostedEvents(None, DeferredDelete)`. É a mesma `descartar` de `tests/qt_app.py` do
    tronco, e pela mesma razão que ela registra: a fita deixa seguidor em
    `comandos._SEGUIDORES` enquanto o botão dela estiver vivo.
    """
    from PyQt6.QtCore import QCoreApplication, QEvent

    janela.close()
    janela.deleteLater()
    for _ in range(2):
        aplicacao.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    aplicacao.processEvents()


def _focaveis(raiz: Any) -> list[Any]:
    """Todo descendente que aceita foco de teclado, em ordem de árvore.

    `Qt.FocusPolicy.NoFocus` sai; o resto entra, inclusive o que só aceita clique
    (`ClickFocus`) -- e ele entra de propósito: um controle que o mouse pode focar e o `Tab` não
    é exatamente a assimetria que este módulo existe para achar.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QAbstractSpinBox, QWidget

    achados: list[Any] = []
    for widget in raiz.findChildren(QWidget):
        if not widget.isVisible():
            continue
        # O poço interno de um campo de número **não é um controle**: o Qt o anuncia junto com o
        # `QSpinBox` que o contém, e contá-lo aqui inventaria um "inalcançável" por campo de
        # número da janela -- seis deles, todos falsos.
        if isinstance(widget.parentWidget(), QAbstractSpinBox):
            continue
        # **Desabilitado sai, e a razão é que ele não é um defeito de teclado.** O Qt tira o
        # controle desligado da cadeia de foco de propósito, como toda plataforma faz: "Cancelar
        # exportação" fora do `Tab` enquanto não há exportação é o comportamento certo, e
        # reportá-lo encheria a lista de falsos positivos que escondem os verdadeiros.
        if not widget.isEnabled():
            continue
        if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
            continue
        achados.append(widget)
    return achados


def _grupos_alcancados(focaveis: Sequence[Any], visto: dict[int, int]) -> set[int]:
    """Os grupos de escolha exclusiva que a volta do `Tab` visitou. Ver `_por_seta`."""
    alcancados: set[int] = set()
    for widget in focaveis:
        if id(widget) in visto:
            identidade = _grupo_exclusivo(widget)
            if identidade is not None:
                alcancados.add(identidade)
    return alcancados


def _grupo_exclusivo(widget: Any) -> int | None:
    """A identidade do grupo de escolha exclusiva deste botão, ou `None` se ele não está num.

    O Qt tem dois jeitos de formar o grupo, e os dois contam: um `QButtonGroup` explícito, e --
    quando não há grupo -- **todos os botões `autoExclusive` com o mesmo pai**, que é a regra
    que o `QAbstractButton` documenta.

    **O `QButtonGroup` conta por si, sem `autoExclusive`** (OCR_UI passo 17, tarefa 3). A forma
    anterior só olhava o grupo depois de `autoExclusive()` responder sim -- e um botão dentro de
    um `QButtonGroup` **não** é `autoExclusive` (a propriedade é para botões sem grupo). É a
    regra do próprio Qt, `QAbstractButtonPrivate::fixFocusPolicy`: `if (!group && !autoExclusive)
    return;` -- um botão marcável num grupo, exclusivo ou não, vira **um** ponto de parada do
    `Tab` com os outros do grupo, e as setas andam entre eles (`moveFocus`). A barra de modos da
    aba `Livro` -- quatro `QToolButton` marcáveis num `QButtonGroup` exclusivo -- foi o primeiro
    grupo desse tipo na janela, e a régua antiga acusou três modos inalcançáveis que as setas
    alcançam.
    """
    grupo = getattr(widget, "group", None)
    achado = grupo() if callable(grupo) else None
    if achado is not None:
        return id(achado)
    exclusivo = getattr(widget, "autoExclusive", None)
    if not (exclusivo and exclusivo()):
        return None
    pai = widget.parentWidget()
    return id(pai) if pai is not None else None


def _por_seta(widget: Any, alcancados_do_grupo: set[int] | None = None) -> bool:
    """Se este controle é alcançado pelas **setas** e não pelo `Tab`, por estar em grupo exclusivo.

    **A régua passou a olhar o grupo, e não o "está marcado?"** (F9-C12). A forma anterior dizia
    "exclusivo e não marcado", o que supõe que o ponto de parada do `Tab` é sempre o botão
    marcado. O Qt não promete isso: o ponto de parada é o **último** botão do grupo que teve
    foco, e a volta deste arnês começa forçando o foco em `focaveis[0]`. Em `DialogoDeEscopo`,
    com a pasta marcada e o foco começando em "Escolher livro(s) em disco…", o botão **marcado**
    aparecia fora do `Tab` -- um defeito que descreve o arnês, não o produto.

    A pergunta certa é a da plataforma e a da WCAG 2.1.1: um grupo de escolha exclusiva é **um**
    ponto de parada, e de dentro dele as setas alcançam os outros. Então um membro não alcançado
    pelo `Tab` está alcançado desde que **algum** membro do grupo dele esteja. Um grupo inteiro
    fora da cadeia continua sendo o defeito que este ramo existe para achar.

    `alcancados_do_grupo` são as identidades de grupo que a volta do `Tab` visitou. Sem ela --
    o uso antigo, que os instrumentos do crítico ainda fazem -- vale a régua conservadora de
    antes.
    """
    identidade = _grupo_exclusivo(widget)
    if identidade is None:
        return False
    if alcancados_do_grupo is not None:
        return identidade in alcancados_do_grupo
    marcado = getattr(widget, "isChecked", None)
    return bool(marcado and not marcado())


def _nome_de(widget: Any) -> tuple[str, str]:
    """O nome anunciado e de onde ele veio, na ordem em que o Qt o procura."""
    nome = str(widget.accessibleName() or "")
    if nome:
        return nome, "accessibleName"
    texto = str(getattr(widget, "text", lambda: "")() or "")
    if texto:
        return texto, "texto"
    dica = str(widget.toolTip() or "")
    if dica:
        return dica.splitlines()[0], "dica"
    return "", "nenhuma"


def _grupo_de(widget: Any) -> str:
    """O `accessibleName` do contêiner nomeado mais próximo acima daquele controle.

    É a primeira metade do que um leitor de tela anuncia (ver `Controle.grupo`). Sobe pelos
    **pais** e não pela hierarquia de classes: quem agrupa é o widget que contém, e é nele que
    `qt/painel_do_pdf._bloco` põe o nome desde o ciclo 2.

    O próprio widget fica de fora do laço de propósito: o nome dele é a segunda metade do
    anúncio, e somá-lo às duas produziria `"Salvar: Salvar"`.

    **A subida pára na janela** (F9-C12). Um `QDialog` é filho da janela que o abriu, então sem
    esta parada o campo `Achar` de `Achar e substituir` herdaria o grupo de um contêiner da
    janela principal atrás dele -- e um leitor de tela não anuncia isso: quem entra num diálogo
    modal ouve o título do diálogo, não o painel que ficou embaixo. Na janela principal a
    parada não muda nada, porque a `QMainWindow` é o fim da subida de qualquer jeito.
    """
    pai = widget.parentWidget()
    while pai is not None:
        nome = str(pai.accessibleName() or "")
        if nome:
            return nome
        if pai.isWindow():
            break
        pai = pai.parentWidget()
    return ""


def _papel_de(widget: Any) -> str:
    """O papel de acessibilidade daquele widget, pela cadeia de classes dele.

    Sobe a hierarquia Python porque os painéis do tronco derivam das classes do Qt: um
    `PainelDoPdf(QWidget)` reporta o papel de `QWidget`, e é a primeira classe **conhecida** da
    cadeia que responde. Classe fora da tabela devolve `NoRole`, que é o que o relatório reprova.
    """
    for classe in type(widget).__mro__:
        papel = PAPEL_POR_CLASSE.get(classe.__name__)
        if papel is not None:
            return papel
    return "NoRole"


def _volta_do_tab(janela: Any, focaveis: Sequence[Any]) -> tuple[dict[int, int], int, bool]:
    """Percorre a cadeia de foco como o `Tab` faria. Devolve `(passo por widget, passos, fechou)`.

    **`focusNextPrevChild` e não um `QKeyEvent` sintético**, e a diferença é o que se está
    medindo. Um evento de tecla enfileirado passa antes por filtros de evento e por atalhos, e
    numa janela com paleta de comandos ele pode ser consumido antes de chegar ao gerenciador de
    foco -- o que mediria "a tecla foi entregue", que é outra pergunta. `focusNextPrevChild` é o
    método que o próprio `QWidget` chama quando decide mover o foco: chamá-lo mede a **cadeia**.
    """
    indice_de = {id(widget): posicao for posicao, widget in enumerate(focaveis)}
    if not focaveis:
        return {}, 0, False
    focaveis[0].setFocus()
    partida = janela.focusWidget()
    visto: dict[int, int] = {}
    passos = 0
    while passos < TETO_DE_VOLTAS:
        atual = janela.focusWidget()
        if atual is not None and id(atual) in indice_de and id(atual) not in visto:
            visto[id(atual)] = passos
        passos += 1
        if not janela.focusNextPrevChild(True):
            break
        seguinte = janela.focusWidget()
        if seguinte is partida and passos > 1:
            return visto, passos, True
        if seguinte is atual:
            break
    # **Com um controle só, a volta está fechada por definição** (F9-C12). A ordem do `Tab` é
    # uma lista circular, e uma lista de um elemento volta ao começo no primeiro passo: o Qt
    # devolve `False` de `focusNextPrevChild` (não há para onde ir) ou deixa o foco onde está,
    # e os dois são o mesmo fato. `NÃO FECHA` ali descreveria o Qt e não o produto -- e o caso
    # existe: `JanelaDeEstatisticas` é um `QPlainTextEdit` e mais nada. Com dois ou mais
    # focáveis, sair por aqui continua sendo o beco que estes dois ramos existem para achar.
    return visto, passos, len(focaveis) == 1


def peles_registradas(caminho_do_tronco: Path = TRONCO) -> list[str]:
    """Os nomes das peles que o produto registra, na ordem do menu. Lidos de `ui/pele.PELES`.

    **Lidos, e não escritos aqui** (F9-C9). O ciclo 9 reprovou porque este portão media **uma**
    das três peles que `Ver ▸ Aparência` oferece: ele herdava `CVOFF_SKIN` do ambiente e publicava
    `PASSOU` sem dizer de qual pele estava falando -- e o mesmo comando, na pele ao lado, devolvia
    `REPROVOU` com 36 controles anunciados como `-`, `+`, `◀`, `▶`, `|◀`, `▶|`. Uma lista escrita
    aqui teria a mesma doença um ciclo depois: quem registrasse a quarta pele não viria mexer no
    arnês. A fonte é a do produto, e é a mesma que o menu lê.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import pele

    return [registro.nome for registro in pele.PELES]


# ------------------------------------------------------ os doze diálogos (portão do ciclo 12)


def dialogos_registrados(caminho_do_tronco: Path = TRONCO) -> list[str]:
    """Os `QDialog` que o produto define, em ordem alfabética. De `qt.dialogos_do_produto`.

    **Lidos, e não escritos aqui**, pela razão exata que fez `peles_registradas` existir
    (F9-C9) e que reprovou este portão no ciclo 11 (F9-C11). O portão andava por `janela.abas`
    -- as seis abas da janela principal -- e publicava `0 sem nome` sem dizer que era da janela
    principal; a mesma régua, aplicada aos diálogos, devolvia **11 controles sem nome
    acessível**, dois deles no campo da paleta de comandos (`Ctrl+Shift+P`), que é a superfície
    de quem usa o teclado. Uma lista de diálogos escrita aqui teria a mesma doença um ciclo
    depois: quem acrescentar o décimo terceiro não vem mexer no arnês.

    A varredura do produto lê a árvore sintática de `chess_diagram_ocr/qt/*.py` e **não importa
    o PyQt6**, o que faz `RECEITAS` ser comparável com ela no venv desta suíte, que não tem
    binding de Qt nenhum -- ver `tests/unit/ui/test_dialogos.py`.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr import qt

    return list(qt.dialogos_do_produto())


@dataclass
class _Sala:
    """A janela viva e os painéis de onde os diálogos nascem. Só existe para as `RECEITAS`."""

    janela: Any
    texto: Any = None
    """`PainelDeTexto`: é dele que `JanelaDeBusca` é filha, e é a folha que ela procura."""

    estudo: Any = None
    """`PainelDeEstudo`: as três janelas privadas de `Estudo` são filhas dele."""

    galeria: Any = None
    """`PainelDaGaleria`: `DialogoDePartidas` recebe o `GalleryModel` que mora aqui."""


def _dialogo_de_colar(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.painel_de_estudo import _JanelaDeColar

    return [("_JanelaDeColar (Estudo | Colar)", _JanelaDeColar(sala.estudo, lambda _t: None))]


def _dialogo_de_colecao(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.painel_de_estudo import _JanelaDeColecao

    return [
        (
            "_JanelaDeColecao (Estudo | Abrir PGN)",
            _JanelaDeColecao(sala.estudo, "colecao.pgn", [], lambda _e: None),
        )
    ]


def _dialogo_de_partidas_da_posicao(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr import estudo_partidas
    from chess_diagram_ocr.qt.painel_de_estudo import _JanelaDePartidas

    resposta = estudo_partidas.consultar(None, "")
    return [("_JanelaDePartidas (Estudo | Partidas)", _JanelaDePartidas(sala.estudo, resposta))]


def _dialogo_de_busca(sala: _Sala) -> list[tuple[str, Any]]:
    """As **duas** formas da mesma janela: achar, e achar e substituir.

    Duas linhas para uma classe porque são duas telas: a segunda acrescenta `Trocar por` ao
    lado de `Achar`, e foi esse par de `QLineEdit` sem nome, lado a lado, que o ciclo 11
    nomeou como o pior caso -- quem não vê a tela não distingue um do outro.
    """
    from chess_diagram_ocr.qt.painel_de_texto import JanelaDeBusca

    return [
        ("JanelaDeBusca (Achar no texto)", JanelaDeBusca(sala.texto)),
        ("JanelaDeBusca (substituindo)", JanelaDeBusca(sala.texto, substituindo=True)),
    ]


def _dialogo_da_paleta(sala: _Sala) -> list[tuple[str, Any]]:
    """Aberta **pelo caminho do produto** (`paleta.abrir`), que é o que `Ctrl+Shift+P` chama."""
    from chess_diagram_ocr.qt import paleta

    janela = paleta.abrir(sala.janela, sala.janela._comandos())
    return [("JanelaDaPaleta (Ctrl+Shift+P)", janela)]


def _dialogo_de_atalhos(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.legenda import JanelaDeAtalhos

    return [("JanelaDeAtalhos (Ver | Atalhos)", JanelaDeAtalhos(sala.janela))]


def _dialogo_de_estatisticas(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.painel_do_dataset import JanelaDeEstatisticas

    corpo = "classes:\n  peao: 1234\nsplits:\n  treino: 100"
    return [("JanelaDeEstatisticas (Dataset)", JanelaDeEstatisticas(corpo, sala.janela))]


def _dialogo_de_bases(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.dialogos import DialogoDeBases

    return [("DialogoDeBases (Estudo | Bases)", DialogoDeBases(sala.janela))]


def _dialogo_de_escopo(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.dialogos import DialogoDeEscopo

    return [("DialogoDeEscopo (Galeria | Varrer)", DialogoDeEscopo(sala.janela))]


def _dialogo_de_partidas_da_base(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.dialogos import DialogoDePartidas

    modelo = getattr(sala.galeria, "model", None)
    return [
        ("DialogoDePartidas (Galeria | Partidas)", DialogoDePartidas(sala.janela, modelo=modelo))
    ]


def _dialogo_de_treino(sala: _Sala) -> list[tuple[str, Any]]:
    from chess_diagram_ocr.qt.dialogos import DialogoDeTreino

    return [("DialogoDeTreino (Dataset | Treinar)", DialogoDeTreino(sala.janela))]


def _controlador_de_treino(sala: _Sala) -> list[tuple[str, Any]]:
    """O `QDialog` que **nunca é mostrado** -- e é por isso que ele aparece com zero focáveis.

    O docstring dele diz o motivo: *"Um `QDialog` só para ter sinais -- ele nunca é mostrado;
    quem aparece é o `DialogoDeTreino`"*. A herança existe porque a thread do treino precisa
    falar com widget, e no Qt isso é sinal. **Ele continua na conta de propósito**: uma
    exceção calada no arnês é como a lista de peles voltaria a ter dois terços do produto. A
    linha `0 focáveis` no relatório é a resposta certa, e ela se lê sozinha.
    """
    from chess_diagram_ocr.qt.dialogos import ControladorDeTreino

    return [
        (
            "ControladorDeTreino (nunca mostrado)",
            ControladorDeTreino(sala.janela, pedido=lambda: None),
        )
    ]


RECEITAS: dict[str, Any] = {
    "ControladorDeTreino": _controlador_de_treino,
    "DialogoDeBases": _dialogo_de_bases,
    "DialogoDeEscopo": _dialogo_de_escopo,
    "DialogoDePartidas": _dialogo_de_partidas_da_base,
    "DialogoDeTreino": _dialogo_de_treino,
    "JanelaDaPaleta": _dialogo_da_paleta,
    "JanelaDeAtalhos": _dialogo_de_atalhos,
    "JanelaDeBusca": _dialogo_de_busca,
    "JanelaDeEstatisticas": _dialogo_de_estatisticas,
    "_JanelaDeColar": _dialogo_de_colar,
    "_JanelaDeColecao": _dialogo_de_colecao,
    "_JanelaDePartidas": _dialogo_de_partidas_da_posicao,
}
"""`nome da classe -> como abri-la para medir`. **As chaves são cobradas contra o produto.**

Uma receita monta o diálogo com o mínimo que ele precisa para existir na tela, e devolve uma ou
mais telas: `JanelaDeBusca` devolve duas, porque `Achar` e `Achar e substituir` são duas telas da
mesma classe e a segunda é a que tem os dois `QLineEdit` lado a lado.

**Esta tabela não é a lista de diálogos** -- a lista é `dialogos_registrados()`, que sai do
produto. Esta é a metade que o arnês precisa saber e que ninguém consegue derivar: com que
argumentos a janela abre. Quando o décimo terceiro diálogo entrar no produto,
`_medir_os_dialogos` levanta nomeando-o e `tests/unit/ui/test_dialogos.py` cai -- por
construção, e não por alguém lembrar."""


def _sala_de_dialogos(janela: Any) -> _Sala:
    """Acha, dentro da janela viva, os painéis de onde os diálogos nascem."""
    from chess_diagram_ocr.qt.painel_da_galeria import PainelDaGaleria
    from chess_diagram_ocr.qt.painel_de_estudo import PainelDeEstudo
    from chess_diagram_ocr.qt.painel_de_texto import PainelDeTexto

    return _Sala(
        janela=janela,
        texto=janela.findChild(PainelDeTexto),
        estudo=janela.findChild(PainelDeEstudo),
        galeria=janela.findChild(PainelDaGaleria),
    )


def _medir_uma_tela(nome: str, raiz: Any) -> Aba:
    """A régua do portão -- a mesma dos seis painéis -- aplicada a uma janela qualquer."""
    aba = Aba(nome=nome)
    focaveis = _focaveis(raiz)
    visto, passos, fechou = _volta_do_tab(raiz, focaveis)
    aba.passos_ate_fechar, aba.fechou = passos, fechou
    if not focaveis:
        # Uma tela sem controle nenhum não tem volta para fechar, e `NÃO FECHA` ali seria uma
        # acusação sobre o que não existe. Ver `_controlador_de_treino`.
        aba.fechou = True
    grupos_alcancados = _grupos_alcancados(focaveis, visto)
    for widget in focaveis:
        # **O procurador de foco conta pelo procurado.** Um `QTabWidget` declara
        # `focusProxy() == tabBar`: quem o `Tab` visita é a faixa de abas, e o contêiner é
        # alcançado por definição. Sem esta linha, todo `QTabWidget` da janela apareceria
        # como inalcançável -- seis defeitos que descrevem o Qt, e não o produto.
        procurador = widget.focusProxy()
        alcancado = id(widget) in visto or (procurador is not None and id(procurador) in visto)
        nome_do_controle, origem = _nome_de(widget)
        aba.controles.append(
            Controle(
                classe=type(widget).__name__,
                nome=nome_do_controle,
                origem_do_nome=origem,
                grupo=_grupo_de(widget),
                papel=_papel_de(widget),
                alcancado_pelo_tab=alcancado,
                posicao_no_tab=visto.get(id(widget), -1),
                por_seta=_por_seta(widget, grupos_alcancados),
                politica=widget.focusPolicy().name,
            )
        )
    return aba


def _medir_os_dialogos(janela: Any, aplicacao: Any) -> list[Aba]:
    """Uma linha por diálogo do produto, com a régua das abas. Levanta quando a lista derivar.

    **A guarda é a primeira coisa que roda**, e é o que torna a largura estrutural: a lista sai
    de `qt.dialogos_do_produto()` -- a árvore sintática do produto -- e o arnês só sabe abrir o
    que está em `RECEITAS`. Um diálogo novo no produto sem receita aqui **derruba o portão**
    com o nome dele; ele não passa despercebido, que foi o que aconteceu por onze ciclos.

    Os diálogos são medidos **depois** das seis abas, e cada um é destruído antes do seguinte:
    um `QDialog` vivo é filho da janela, e `janela.findChildren` o traria para dentro da conta
    da aba -- que é como um portão passa a medir uma coisa e a publicar outra.
    """
    do_produto = set(dialogos_registrados())
    faltando = sorted(do_produto - set(RECEITAS))
    sobrando = sorted(set(RECEITAS) - do_produto)
    if faltando or sobrando:
        raise RuntimeError(
            "a lista de dialogos do arnes divergiu da do produto (qt.dialogos_do_produto): "
            f"sem receita no arnes = {faltando}; receita para quem o produto nao define = "
            f"{sobrando}."
        )

    from PyQt6.QtCore import QCoreApplication, QEvent

    sala = _sala_de_dialogos(janela)
    medidos: list[Aba] = []
    for classe in sorted(RECEITAS):
        try:
            telas = RECEITAS[classe](sala)
        except Exception as exc:  # noqa: BLE001 - um diálogo que não abre é defeito, não silêncio
            aba = Aba(nome=f"{classe} (NAO ABRIU: {type(exc).__name__})")
            medidos.append(aba)
            print(f"  {'':<9} {aba.nome:<38} NAO ABRIU: {exc}", file=sys.stderr)
            continue
        for rotulo, dialogo in telas:
            dialogo.show()
            for _ in range(4):
                aplicacao.processEvents()
            aba = _medir_uma_tela(rotulo, dialogo)
            medidos.append(aba)
            print(
                f"  {os.environ.get('CVOFF_SKIN', '?'):<9} "
                f"{aba.nome:<38} {aba.focaveis():>4} focáveis  "
                f"{aba.alcancados():>4} pelo Tab  "
                f"{len(aba.anonimos()):>3} sem nome  {len(aba.sem_papel()):>3} sem papel  "
                f"{len(aba.nomes_vazios()):>3} nome vazio"
            )
            dialogo.close()
            dialogo.setParent(None)
            dialogo.deleteLater()
        aplicacao.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        aplicacao.processEvents()
    return medidos


def densidades_registradas(caminho_do_tronco: Path = TRONCO) -> list[str]:
    """As densidades que `Ver ▸ Aparência` oferece. Lidas de `ui/pele.DENSIDADES` (F9-C12).

    **É o terceiro eixo da mesma pergunta, e o crítico do ciclo 11 mostrou o preço de não
    percorrê-lo.** `Ver ▸ Aparência` oferece **três peles × duas densidades = seis arranjos**; o
    portão media três -- cada pele na densidade que ela sugere. Rodado o censo de ícones com
    `CVOFF_DENSITY=confortavel`, a amplitude da caixa do ícone na `fita` sai **2×17 px** contra
    os **0×11 px** publicados, e a família só-de-ícone deixa de ter caixa única. O eixo não
    escondia bloqueante -- os três arranjos não medidos devolvem 216 / 240 / 360 e `PASSOU` --,
    mas escondia um número, e um portão que publica um número de metade da superfície é o
    defeito do ciclo 9 outra vez.

    O portão de contraste já percorria as duas densidades desde o ciclo 10 (`lista =
    [CONFORTAVEL, COMPACTA]`), e o crítico registrou que ele era o modelo a copiar. Isto é a
    cópia -- com a lista saindo do produto, como a de peles sai.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import pele

    return list(pele.DENSIDADES)


def auditar(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    largura: int = 1280,
    altura: int = 800,
    pele_pedida: str = "",
) -> dict[str, Any]:
    """Percorre todas as abas da janela do tronco com o teclado e devolve o relatório.

    `pele_pedida` crava a aparência desta passada. Vazio herda o ambiente, que é o que este
    módulo fazia antes do ciclo 10 -- e o que fazia a medição valer por uma pele das três.
    """
    _preparar(caminho_do_tronco)
    if pele_pedida:
        from chess_diagram_ocr.ui import pele as _pele

        os.environ[_pele.PELE_ENV] = pele_pedida
        # A cor do traço é a da pele, e o cache do ícone tem a cor na chave: sem limpar, a
        # segunda pele desta passada desenharia com a tinta da primeira.
        from chess_diagram_ocr.qt import icones as _icones

        _icones.limpar_cache()
    from chess_diagram_ocr.qt.plataforma import politica_de_escala

    politica_de_escala()
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from PyQt6.QtCore import QT_VERSION_STR
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit.capture import aguardar_a_folha, areas_de_trabalho, estado_de_medicao

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    # **Estado próprio, e não o `data/app_tkinter_state.json` do tronco** (F9-C10). Ver
    # `capture.estado_de_medicao`: sem isto o portão lê a sessão de quem abriu a janela por
    # último **e a reescreve ao sair** -- mede um estado que ninguém pediu e estraga o de quem
    # roda o portão.
    with tempfile.TemporaryDirectory() as temporaria:
        estado = estado_de_medicao(Path(temporaria))
        janela = JanelaPrincipal(caminho_do_estado=estado)
    janela.show()
    janela.resize(largura, altura)
    for _ in range(4):
        aplicacao.processEvents()
    if pdf is not None and pdf.exists():
        try:
            janela.abrir_pdf(pdf)
            aguardar_a_folha(janela)
        except Exception as exc:
            print(f"  (livro {pdf.name} não abriu: {exc})", file=sys.stderr)
        for _ in range(4):
            aplicacao.processEvents()

    abas: list[Aba] = []
    # Cada área uma vez -- as abas do acervo e os modos da aba `Livro` (OCR_UI passo 17). Ver
    # `capture.areas_de_trabalho`, o único laço do arnês sobre elas.
    for area in areas_de_trabalho(janela):
        area.mostrar()
        for _ in range(4):
            aplicacao.processEvents()
        # **A mesma régua das outras telas, e desde o ciclo 12 é literalmente a mesma função.**
        # Ver `_medir_uma_tela`: duas cópias do laço eram duas oportunidades de a aba e o
        # diálogo passarem a ser medidos por réguas que divergem sem ninguém notar.
        aba = _medir_uma_tela(area.nome, janela)
        abas.append(aba)
        print(
            f"  {os.environ.get('CVOFF_SKIN', '?'):<9} "
            f"{aba.nome:<12} {aba.focaveis():>4} focáveis  {aba.alcancados():>4} pelo Tab  "
            f"{'fecha' if aba.fechou else 'NÃO FECHA':<10} "
            f"{len(aba.anonimos()):>3} sem nome  {len(aba.sem_papel()):>3} sem papel  "
            f"{len(aba.nomes_vazios()):>3} nome vazio"
        )
    # **Os diálogos depois das abas, e é a metade que faltava** (F9-C12). Ver
    # `_medir_os_dialogos`: por onze ciclos este portão publicou `0 sem nome` sobre a janela
    # principal e nunca abriu um dos doze `QDialog` do produto.
    dialogos = _medir_os_dialogos(janela, aplicacao)
    _descartar(janela, aplicacao)

    return {
        "portao": "SPEC 10.6/11.3 -- navegação inteira por teclado, nome e papel em todo controle",
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "ambiente": {
            "qt": QT_VERSION_STR,
            "python": sys.version.split()[0],
            "plataforma_qpa": os.environ.get("QT_QPA_PLATFORM", ""),
            "janela_px": [largura, altura],
            "pele": os.environ.get("CVOFF_SKIN", ""),
            # **A densidade entra no carimbo** (F9-C12): sem ela o JSON de `fita/compacta` e o
            # de `fita/confortavel` são indistinguíveis, que é como um portão publica um número
            # sem dizer de qual arranjo ele é.
            "densidade": os.environ.get("CVOFF_DENSITY", ""),
        },
        "metodo": {
            "volta": "QWidget.focusNextPrevChild(True) em laço, que é o que a tecla Tab chama",
            "nome": "accessibleName, senão text(), senão a 1a linha da dica -- a ordem do Qt",
            "grupo": (
                "o accessibleName do conteiner nomeado mais proximo -- a primeira metade do que "
                "um leitor de tela anuncia; 'repetido na aba' compara as duas juntas"
            ),
            "nome_informativo": (
                "e o nome tem de nomear: reprova eco do papel, menos de "
                f"{LETRAS_MINIMAS} letras seguidas, nome repetido na mesma aba, "
                "e nome que é o valor do próprio controle"
            ),
            "papel": "QAccessible.queryAccessibleInterface(w).role()",
            "isentos_de_nome": list(SEM_NOME_POR_NATUREZA),
            "motivos_de_nome_vazio": list(MOTIVOS_DE_NOME_VAZIO),
            "teto_de_voltas": TETO_DE_VOLTAS,
        },
        "abas": [_como_json(aba) for aba in abas],
        "dialogos": [_como_json(aba) for aba in dialogos],
        "dialogos_do_produto": dialogos_registrados(caminho_do_tronco),
        "veredito": veredito([*abas, *dialogos]),
    }


def auditar_as_peles(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    largura: int = 1280,
    altura: int = 800,
    saida: Path | None = None,
) -> dict[str, Any]:
    """O portão inteiro: uma passada por **cada** pele registrada, e um veredito só no fim.

    **É o `for` que faltava, e a falta dele reprovou o ciclo 9.** O portão media a pele que
    estivesse em `CVOFF_SKIN` -- na prática a clássica -- e publicava `216 focáveis, 0 sem nome,
    PASSOU`. Rodado na `foco` ele devolvia 2 defeitos e na `fita`, **36**. Nenhuma regra estava
    errada: a medição cobria **um terço da superfície**, e a largura da medição é tão carregada
    quanto a profundidade dela.

    A lista de peles vem de `ui/pele.PELES` (ver `peles_registradas`), então uma pele nova entra
    neste portão no mesmo commit em que ela entra no menu.

    **Uma pele por processo, e isso foi medido e não escolhido.** A primeira forma deste laço
    montava as três janelas no mesmo processo; a terceira **abortava o interpretador** no meio da
    aba Texto, sem traceback nenhum -- a `JanelaPrincipal` anterior morria por coleta de lixo do
    Python com `DeferredDelete` ainda pendentes no Qt. Destruir à mão
    (`sendPostedEvents(..., DeferredDelete)`, como `tests/qt_app.descartar`) adiou o aborto sem o
    apagar. Um processo por pele também é a medição mais limpa: nenhuma pele herda o cache de
    ícone, o tema aplicado nem os seguidores de `comandos._SEGUIDORES` da anterior -- que é
    exatamente a contaminação que faria uma pele passar por causa da outra.

    **E um subprocesso que morre não vira uma pele que some**: sem o JSON dela este método
    levanta, nomeando a pele. Uma pele perdida em silêncio é o defeito do ciclo 9 outra vez.
    """
    nomes = peles_registradas(caminho_do_tronco)
    densidades = densidades_registradas(caminho_do_tronco)
    por_arranjo: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as temporaria:
        destino = Path(saida) if saida is not None else Path(temporaria)
        destino.mkdir(parents=True, exist_ok=True)
        for nome in nomes:
            for densidade in densidades:
                arranjo = f"{nome}/{densidade}"
                carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                alvo = destino / f"teclado_{nome}_{densidade}_{carimbo}.json"
                ambiente = dict(os.environ)
                ambiente["CVOFF_SKIN"] = nome
                ambiente["CVOFF_DENSITY"] = densidade
                argumentos = [
                    sys.executable,
                    "-m",
                    "caissa.ui.audit.teclado",
                    "--pele",
                    nome,
                    "--densidade",
                    densidade,
                    "--tronco",
                    str(caminho_do_tronco),
                    "--largura",
                    str(largura),
                    "--altura",
                    str(altura),
                    "--json",
                    str(alvo),
                ]
                if pdf is not None:
                    argumentos += ["--pdf", str(pdf)]
                subprocess.run(argumentos, env=ambiente, check=False)  # noqa: S603 - argv nosso
                if not alvo.exists():
                    raise RuntimeError(
                        f"o arranjo {arranjo!r} nao produziu relatorio: o subprocesso morreu "
                        f"antes de escrever {alvo}."
                    )
                por_arranjo[arranjo] = json.loads(alvo.read_text(encoding="utf-8"))
    return {
        "portao": (
            "SPEC 10.6/11.3 -- teclado, nome e papel, em TODOS os arranjos registrados "
            "(pele x densidade) e em TODO dialogo do produto"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        # A mesma tabela sob os dois nomes: `arranjos` é o certo desde o ciclo 12 (a chave é
        # `pele/densidade`), e `peles` fica para não quebrar quem lê o JSON do ciclo passado.
        "arranjos": por_arranjo,
        "peles": por_arranjo,
        "veredito": (
            "PASSOU"
            if all(r["veredito"] == "PASSOU" for r in por_arranjo.values())
            else "REPROVOU"
        ),
    }


def tabela_das_peles(relatorio: dict[str, Any]) -> str:
    """Uma linha por pele, e o detalhe de cada uma embaixo. O placar não fica sem dizer de quem."""
    linhas = [relatorio["portao"], ""]
    for nome, por_pele in relatorio.get("arranjos", relatorio["peles"]).items():
        for rotulo, chave in (("abas", "abas"), ("diálogos", "dialogos")):
            telas = por_pele.get(chave, [])
            focaveis = sum(aba["focaveis"] for aba in telas)
            vazios = sum(len(aba["nome_vazio_de_sentido"]) for aba in telas)
            sem_nome = sum(len(aba["sem_nome"]) for aba in telas)
            sem_papel = sum(len(aba["sem_papel"]) for aba in telas)
            fora = sum(len(aba["inalcancaveis"]) for aba in telas)
            reprovou = [aba for aba in telas if aba["veredito"] != "PASSOU"]
            linhas.append(
                f"  {nome:<20} {len(telas):>2} {rotulo:<9} {focaveis:>4} focáveis  "
                f"{sem_nome:>3} sem nome  {sem_papel:>3} sem papel  {vazios:>3} nome vazio  "
                f"{fora:>3} fora do Tab  {'REPROVOU' if reprovou else 'PASSOU'}"
            )
    linhas.append("")
    for nome, por_pele in relatorio.get("arranjos", relatorio["peles"]).items():
        linhas.append(f"--- arranjo {nome} " + "-" * 48)
        linhas.append(tabela(por_pele))
    linhas.append("")
    linhas.append(f"  Veredito de TODOS os arranjos: {relatorio['veredito']}")
    return "\n".join(linhas)


def tabela(relatorio: dict[str, Any]) -> str:
    linhas = [relatorio["portao"], ""]
    dialogos = relatorio.get("dialogos", [])
    for aba in relatorio["abas"]:
        linhas.append(
            f"  {aba['nome']:<38} {aba['focaveis']:>4} focáveis  "
            f"{aba['alcancados_pelo_tab']:>4} pelo Tab  "
            f"{'fecha' if aba['a_volta_fecha'] else 'NÃO FECHA':<10} "
            f"{len(aba['sem_nome']):>3} sem nome  {len(aba['sem_papel']):>3} sem papel  "
            f"{len(aba['nome_vazio_de_sentido']):>3} nome vazio  "
            f"{aba['veredito']}"
        )
    if dialogos:
        # **Uma linha por diálogo, e é o item 1 do §7 do ciclo 11.** O portão publicava
        # `0 sem nome` sobre seis abas e nunca abria uma das doze janelas de diálogo.
        registrados = relatorio.get("dialogos_do_produto", [])
        linhas.append("")
        # **A frase diz o que a varredura alcança, e não mais do que isso** (F9-C14, item 6 do
        # §7 do ciclo 13). Ela dizia "os 12 QDialog que o produto declara", e o produto tem uma
        # **14ª** tela: o `QDialog(self)` construído em linha em `painel_de_estudo.py:1339`
        # (S-282, `ampliar_recorte`), que não é classe e que nenhuma varredura sintática pode
        # achar. Um portão que afirma mais largura do que tem é a terceira cegueira por largura
        # desta frente, dita em voz alta antes de virar a quarta.
        linhas.append(
            f"  --- os {len(registrados)} QDialog que o produto declara COMO CLASSE, "
            f"em {len(dialogos)} telas " + "-" * 12
        )
        linhas.append(f"      {FORA_DA_VARREDURA}")
        for aba in dialogos:
            linhas.append(
                f"  {aba['nome']:<38} {aba['focaveis']:>4} focáveis  "
                f"{aba['alcancados_pelo_tab']:>4} pelo Tab  "
                f"{'fecha' if aba['a_volta_fecha'] else 'NÃO FECHA':<10} "
                f"{len(aba['sem_nome']):>3} sem nome  {len(aba['sem_papel']):>3} sem papel  "
                f"{len(aba['nome_vazio_de_sentido']):>3} nome vazio  "
                f"{aba['veredito']}"
            )
    for aba in [*relatorio["abas"], *dialogos]:
        for chave, titulo in (
            ("sem_nome", "sem nome acessível"),
            ("nome_vazio_de_sentido", "nome que não nomeia"),
            ("sem_papel", "sem papel de acessibilidade"),
            ("inalcancaveis", "inalcançáveis pelo Tab"),
        ):
            if aba[chave]:
                linhas.append(f"\n  {aba['nome']} -- {titulo}:")
                for controle in aba[chave][:CONTROLES_LISTADOS]:
                    motivo = f"  <- {controle['motivo']}" if controle.get("motivo") else ""
                    grupo = f"[{controle['grupo']}] " if controle.get("grupo") else ""
                    linhas.append(
                        f"    {controle['classe']}: {grupo}{controle['nome'] or '(vazio)'}{motivo}"
                    )
                if len(aba[chave]) > CONTROLES_LISTADOS:
                    restantes = len(aba[chave]) - CONTROLES_LISTADOS
                    linhas.append(f"    ... e mais {restantes}")
    linhas.append("")
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        # **Sem padrão, e isto é um conserto de higiene** (F9-C12, item 16 do ciclo 11). O
        # padrão era `benchmarks/reports/ui/` -- a pasta do construtor --, e o crítico do
        # ciclo 11 rodou uma sabotagem sem `--saida`: o JSON foi gravar na pasta que ele não
        # pode tocar, e ele teve de movê-lo à mão. Um padrão que escreve na pasta de outro
        # agente é uma armadilha; quem roda um portão diz onde quer o relatório.
        help="onde gravar o relatorio. Obrigatorio: este portao nao escolhe pasta por voce.",
    )
    parser.add_argument("--largura", type=int, default=1280)
    parser.add_argument("--altura", type=int, default=800)
    parser.add_argument(
        "--pele",
        default="",
        help="mede UMA pele. Sem isto o portao percorre todos os arranjos registrados.",
    )
    parser.add_argument(
        "--densidade",
        default="",
        help=(
            "crava a densidade desta passada. Sem isto o portao percorre todas as de "
            "ui/pele.DENSIDADES, cruzadas com as peles -- seis arranjos, e nao tres."
        ),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="onde gravar o JSON desta passada; o laco de uma pele por processo o usa.",
    )
    args = parser.parse_args(argv)
    if args.saida is None and args.json is None:
        # **Sem padrão, e sem escolher pasta por quem chama** (F9-C12). O `--json` é a saída de
        # uma passada só -- é o que o laço de um arranjo por processo usa --, e ele já diz onde
        # gravar; fora disso, o caminho é obrigatório.
        parser.error("diga onde gravar: --saida <pasta> (ou --json <arquivo>, numa passada so).")

    if args.pele:
        if args.densidade:
            _preparar(args.tronco)
            from chess_diagram_ocr.ui import pele as _pele

            os.environ[_pele.DENSIDADE_ENV] = args.densidade
        relatorio = auditar(
            caminho_do_tronco=args.tronco,
            pdf=args.pdf,
            largura=args.largura,
            altura=args.altura,
            pele_pedida=args.pele,
        )
        alvo = args.json
        if alvo is None:
            args.saida.mkdir(parents=True, exist_ok=True)
            carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            alvo = args.saida / f"teclado_{args.pele}_{carimbo}.json"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
        print(tabela(relatorio))
        print(f"\nRelatorio: {alvo}")
        return 0 if relatorio["veredito"] == "PASSOU" else 1

    args.saida.mkdir(parents=True, exist_ok=True)
    relatorio = auditar_as_peles(
        caminho_do_tronco=args.tronco,
        pdf=args.pdf,
        largura=args.largura,
        altura=args.altura,
        saida=args.saida,
    )
    # **Carimbado, pelo mesmo motivo de `contraste.py`** (F9-C5, §7.10): um nome fixo apaga a
    # medição do ciclo anterior sem aviso, e este defeito de família já custou 17 capturas em
    # dois ciclos e por pouco não custou o `contraste.json` na sessão do próprio crítico.
    alvo = args.saida / f"teclado_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela_das_peles(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
