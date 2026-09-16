"""O portão de contraste do SPEC §11.3: **WCAG AA em 100 % dos pares, nas duas polaridades**.

**"Peles" era a palavra errada, e o crítico do ciclo 11 a pegou** (F9-C12): o que este portão
percorre são as duas **polaridades de cromo** (clara e escura) cruzadas com as duas
**densidades** -- quatro folhas de estilo --, e não as três peles de `Ver ▸ Aparência`. A
medição sempre esteve certa; o cabeçalho é que contava outra história. O eixo densidade estava
aqui antes de estar em qualquer outro portão desta frente, e é por isso que o crítico o chamou
de modelo a copiar; a cópia para o portão de teclado e para o censo de ícones é do ciclo 12.

**O problema de um portão que diz "100 %" é a palavra "pares", e é ela que este módulo resolve.**
Um checador que recebe uma lista de pares escrita à mão mede a diligência de quem a escreveu:
o par esquecido é justamente o que reprova, e o próximo componente entra sem ninguém lembrar de
acrescentá-lo. A carta dos críticos (§6) manda remedir tudo que o construtor afirma -- então a
lista de pares não pode ser uma afirmação do construtor.

**Aqui ela é derivada do artefato que embarca.** A folha de estilo do produto é uma string
gerada por `ui/folha_de_estilo.folha_de_estilo`; este módulo a **analisa**, resolve a cascata do
Qt para descobrir sobre que fundo cada `color:` de fato cai, e mede o par resultante. Um
componente novo na folha vira par novo no relatório sem que ninguém escreva uma linha aqui. As
outras três fontes seguem a mesma regra: a `QPalette` sai de `PAPEIS_DA_PALETA`, as marcações
saem de `tokens.SIGNIFICADO`, e o tabuleiro sai dos papéis de casa e de glifo.

**Sem Qt, e é o que torna o portão executável na suíte.** O venv da suíte não tem binding de Qt
nenhum -- foi por isso que a folha mudou de `qt/` para `ui/` na F9. Este módulo importa
`chess_diagram_ocr.ui`, que é livre de toolkit por teste de arquitetura, e nada mais.

---

**Os quatro pisos, e por que não é um só.**

| espécie | piso | de onde vem |
|---|---|---|
| `texto` | 4,5:1 | WCAG 2.1 AA 1.4.3, texto normal |
| `foco` | 3,0:1 | WCAG 2.1 AA 1.4.11 -- indicador de foco é elemento gráfico |
| `borda` | 3,0:1 | WCAG 2.1 AA 1.4.11 -- limite de componente de interface |
| `grafico` | 3,0:1 | WCAG 2.1 AA 1.4.11 -- polegar, preenchimento, marcação |
| `estado` | 3,0:1 | a distância entre a tinta viva e a morta -- F9-C10, ver `PARES_DE_ESTADO` |

**E as duas isenções, declaradas antes que alguém as descubra.**

1. **`:disabled` não é portão.** A WCAG isenta componente inativo em 1.4.3 e em 1.4.11, e a
   isenção é do critério, não deste relatório: os pares mortos aparecem com a razão medida e a
   coluna `portao` em `False`. Neste produto eles passariam de qualquer forma -- o texto morto é
   `TEXTO_SECUNDARIO`, que é o cinza medido da S-146 --, e mostrar o número é mais barato que
   defender a isenção.
2. **`SEPARADOR` é hierarquia, não informação.** É a única cor da paleta deliberadamente abaixo
   de qualquer piso (1,39:1 na clara, 1,47:1 na escura), e a razão está em `ui/tokens.py`: uma
   régua entre grupos que passasse 3:1 competiria com a borda dos controles. O reconhecimento é
   **por valor** -- compara-se o hexadecimal com o que `tokens.cor(SEPARADOR)` devolve --, e não
   por nome de seletor: assim ninguém isenta uma borda de verdade escrevendo "separador" nela.

Uso:

    python -m caissa.ui.audit.contraste --tronco C:/Python-Chess2/ChessVisionOFF_Puro
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator, Sequence
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

AA_TEXTO = 4.5
AA_GRAFICO = 3.0

TEXTO = "texto"
FOCO = "foco"
BORDA = "borda"
GRAFICO = "grafico"
ESTADO = "estado"
"""As cinco espécies de par. O piso sai daqui e não do ponto de chamada.

**`ESTADO` entrou no F9-C10**, e o defeito que o pediu foi medido pelo crítico do ciclo 9: a
distância entre a tinta do rótulo **vivo** e a do rótulo **morto** era de 2,82:1 na pele clássica
e **1,88:1 na Foco**, com 22 de 22 rótulos mortos mais legíveis que o rótulo vivo mais fraco
daquela pele. Nenhum portão a cobria: o de contraste media `:disabled` contra a superfície e o
declarava **isento** (e a isenção está certa para a WCAG 1.4.3), e `c7_estados_do_botao.py` media
*quantos pixels mudam* -- 98,9 % --, que não é *o quanto*.

"Você não pode apertar isto" é informação, e informação que não é texto tem piso de 3,0:1 no
próprio produto: uma listra de tabela e uma marca de diagrama já o respeitam."""

PISO: dict[str, float] = {
    TEXTO: AA_TEXTO,
    FOCO: AA_GRAFICO,
    BORDA: AA_GRAFICO,
    GRAFICO: AA_GRAFICO,
    ESTADO: AA_GRAFICO,
}


# --------------------------------------------------------------- a árvore de classes do Qt

HERANCA: dict[str, tuple[str, ...]] = {
    "QWidget": (),
    "QFrame": ("QWidget",),
    "QLabel": ("QFrame", "QWidget"),
    "QAbstractButton": ("QWidget",),
    "QPushButton": ("QAbstractButton", "QWidget"),
    "QToolButton": ("QAbstractButton", "QWidget"),
    "QCheckBox": ("QAbstractButton", "QWidget"),
    "QRadioButton": ("QAbstractButton", "QWidget"),
    "QComboBox": ("QWidget",),
    "QLineEdit": ("QWidget",),
    "QAbstractSpinBox": ("QWidget",),
    "QSpinBox": ("QAbstractSpinBox", "QWidget"),
    "QDoubleSpinBox": ("QAbstractSpinBox", "QWidget"),
    "QAbstractScrollArea": ("QFrame", "QWidget"),
    "QAbstractItemView": ("QAbstractScrollArea", "QFrame", "QWidget"),
    "QListView": ("QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QTreeView": ("QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QTableView": ("QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QListWidget": ("QListView", "QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QTreeWidget": ("QTreeView", "QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QTableWidget": ("QTableView", "QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QTextEdit": ("QAbstractScrollArea", "QFrame", "QWidget"),
    "QPlainTextEdit": ("QAbstractScrollArea", "QFrame", "QWidget"),
    "QHeaderView": ("QAbstractItemView", "QAbstractScrollArea", "QFrame", "QWidget"),
    "QScrollBar": ("QAbstractSlider", "QWidget"),
    "QAbstractSlider": ("QWidget",),
    "QSlider": ("QAbstractSlider", "QWidget"),
    "QProgressBar": ("QWidget",),
    "QTabWidget": ("QWidget",),
    "QTabBar": ("QWidget",),
    "QMenuBar": ("QWidget",),
    "QMenu": ("QWidget",),
    "QToolBar": ("QWidget",),
    "QStatusBar": ("QWidget",),
    "QSplitter": ("QFrame", "QWidget"),
    "QGroupBox": ("QWidget",),
    # **`QToolTip` não é um `QWidget` no Qt**, e a linha é deliberada: ele é um `QObject` de
    # fachada, e a folha que se escreve como `QToolTip { ... }` é aplicada pelo Qt ao rótulo
    # interno que ele desenha, que **é** um widget. Declará-lo aqui é o que faz o portão medir
    # aquele rótulo contra a superfície certa. Fica escrito porque o instrumento
    # `benchmarks/reports/ui/c16/c16_heranca_contra_o_qt.py` a acusa como divergente do MRO, e
    # divergência declarada é o contrário de divergência esquecida.
    "QToolTip": ("QWidget",),
    "QDialog": ("QWidget",),
}
"""A cadeia de herança de cada classe que a folha menciona, do pai ao `QWidget`.

**Existe porque o seletor de classe do Qt casa com as subclasses**, e é isso que faz
`QListWidget` receber a regra escrita em `QAbstractItemView`. Sem a cadeia, um fundo declarado na
base ficaria invisível para o checador e o par medido seria contra o cinza errado -- que é o
modo mais silencioso de um portão de contraste dar tudo certo.

É fato da biblioteca e não decisão nossa; está escrita à mão porque lê-la exigiria importar Qt,
que é justamente o que este módulo não faz.

**Quem a confere contra o binding é `benchmarks/reports/ui/c16/c16_heranca_contra_o_qt.py`**, e
não um teste desta suíte -- o venv daqui não tem Qt, e um teste que sempre pula não é defesa. Até
o ciclo 15 este parágrafo citava um `test_a_heranca_bate_com_a_do_qt` que **não existe em nenhuma
das duas suítes**: era a mesma doença que o §4.3 da crítica do ciclo 15 achou em
`texto_pintado.PROPRIEDADES_DE_FONTE`, um módulo nomeando como sua defesa um teste que ninguém
escreveu. Rodado, o instrumento achou o que a defesa inexistente deixava passar: `QScrollBar` e
`QSlider` sem `QAbstractSlider` na cadeia -- 37 classes conferidas, 2 divergências reais, hoje 0
mais a de `QToolTip`, que é declarada logo abaixo."""


def _cadeia(classe: str) -> tuple[str, ...]:
    """A classe e seus ancestrais, do mais derivado ao `QWidget`. Classe desconhecida fica só."""
    return (classe, *HERANCA.get(classe, ()))


def profundidade(classe: str) -> int:
    """Quão derivada é a classe. `QWidget` é 0, e é o que perde toda disputa de cascata."""
    return len(HERANCA.get(classe, ()))


# ----------------------------------------------------------------- o analisador da folha

_REGRA = re.compile(r"^\s*(?P<seletor>[^{]+?)\s*\{\s*(?P<corpo>[^}]*)\}\s*$")
_ATRIBUTO = re.compile(r"\[[^\]]*\]")
_SUBCONTROLE = re.compile(r"::([A-Za-z-]+)")
_ESTADO = re.compile(r"(?<!:):(!?[A-Za-z-]+)")
_COR = re.compile(r"#[0-9a-fA-F]{6}\b")
_COR_COM_ALFA = re.compile(r"#[0-9a-fA-F]{8}\b")
_RGBA = re.compile(
    r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+%?)\s*\)", re.IGNORECASE
)


@dataclass(frozen=True)
class Alvo:
    """O que um seletor aponta: uma classe, talvez uma subpeça, talvez estados."""

    classe: str
    subcontrole: str = ""
    atributo: str = ""
    estados: frozenset[str] = frozenset()
    ancestral: str = ""
    """A classe à esquerda num seletor descendente: o `QComboBox` de `QComboBox QAbstractItemView`.

    **Sem ele a lista suspensa da caixa de escolha pintava toda lista do produto.** O seletor
    descendente vale só dentro daquele ancestral, e colapsá-lo em `QAbstractItemView` fazia a face
    elevada do menu suspenso virar o fundo de repouso de qualquer item -- e a seleção passava a ser
    medida contra o fundo errado, o que dava 2,75:1 num par que na tela vale 3,72:1."""

    def __str__(self) -> str:
        sufixo = "".join(sorted(f":{estado}" for estado in self.estados))
        prefixo = f"{self.ancestral} " if self.ancestral else ""
        return (
            f"{prefixo}{self.classe}{self.atributo}"
            f"{'::' + self.subcontrole if self.subcontrole else ''}{sufixo}"
        )

    def sem_subcontrole(self) -> Alvo:
        """O mesmo alvo sem a subpeça: é a superfície contra a qual a subpeça é desenhada."""
        return Alvo(self.classe, "", self.atributo, self.estados, self.ancestral)


@dataclass(frozen=True)
class Regra:
    """Uma linha da folha, já analisada. `ordem` é a posição, que desempata a cascata."""

    alvo: Alvo
    propriedades: dict[str, str]
    ordem: int
    seletor: str


def _alvo_de(seletor: str) -> Alvo:
    """Um seletor simples (sem vírgula) como `Alvo`. O descendente vale pelo último termo.

    `QComboBox QAbstractItemView` é a lista suspensa da caixa de escolha: quem recebe a cor é a
    lista, e é ela que decide o fundo dos itens. Guardar o ancestral não mudaria nenhum par
    medido e faria a cascata precisar de um modelo de árvore de widgets, que não existe fora de
    uma janela viva.
    """
    texto = seletor.strip()
    atributos = _ATRIBUTO.findall(texto)
    texto_sem_atributo = _ATRIBUTO.sub("", texto)
    subcontroles = _SUBCONTROLE.findall(texto_sem_atributo)
    sem_sub = _SUBCONTROLE.sub("", texto_sem_atributo)
    estados = _ESTADO.findall(sem_sub)
    termos = _ESTADO.sub("", sem_sub).split()
    return Alvo(
        classe=termos[-1] if termos else "QWidget",
        subcontrole=subcontroles[0] if subcontroles else "",
        atributo=atributos[0] if atributos else "",
        estados=frozenset(estados),
        ancestral=termos[-2] if len(termos) > 1 else "",
    )


def analisar(folha: str) -> list[Regra]:
    """A folha inteira como regras. Uma regra por seletor -- vírgula vira duas.

    Linha que não casa com `seletor { corpo }` é ignorada em silêncio: a folha do produto é
    gerada e sempre casa, e um `raise` aqui transformaria um comentário futuro em falha de
    portão de contraste, que é a mensagem errada para o problema errado.
    """
    regras: list[Regra] = []
    for numero, linha in enumerate(folha.splitlines()):
        casou = _REGRA.match(linha)
        if not casou:
            continue
        propriedades: dict[str, str] = {}
        for declaracao in casou.group("corpo").split(";"):
            if ":" not in declaracao:
                continue
            nome, _, valor = declaracao.partition(":")
            propriedades[nome.strip().lower()] = valor.strip()
        for seletor in casou.group("seletor").split(","):
            if seletor.strip():
                regras.append(Regra(_alvo_de(seletor), dict(propriedades), numero, seletor.strip()))
    return regras


def _alcanca(regra: Regra, alvo: Alvo) -> bool:
    """Se a regra pinta este alvo, pelas regras de casamento do QSS."""
    return (
        regra.alvo.subcontrole == alvo.subcontrole
        and regra.alvo.classe in _cadeia(alvo.classe)
        and regra.alvo.ancestral == alvo.ancestral
        and (not regra.alvo.atributo or regra.alvo.atributo == alvo.atributo)
        and regra.alvo.estados <= alvo.estados
    )


def _peso(regra: Regra) -> tuple[int, int, int, int]:
    """A ordem de especificidade do QSS, aproximada: classe, atributo, estados, posição."""
    return (
        profundidade(regra.alvo.classe),
        1 if regra.alvo.atributo else 0,
        len(regra.alvo.estados),
        regra.ordem,
    )


def valor_de(regras: Sequence[Regra], alvo: Alvo, propriedade: str) -> str:
    """O valor que a cascata deixa valendo para aquela propriedade naquele alvo. `""` se nenhum."""
    candidatas = [
        regra for regra in regras if _alcanca(regra, alvo) and propriedade in regra.propriedades
    ]
    return max(candidatas, key=_peso).propriedades[propriedade] if candidatas else ""


def _cor_de(valor: str) -> str:
    """O hexadecimal de um valor de propriedade (`1px solid #767e88` -> `#767e88`). `""` se não há."""
    achado = _COR.search(valor)
    return achado.group(0).lower() if achado else ""


def cor_e_alfa(valor: str) -> tuple[str, int]:
    """`(#rrggbb, alfa 0..255)` de um valor de propriedade. Alfa 255 quando ele não diz.

    Reconhece as três formas com que uma cor **translúcida** pode chegar aqui: `rgba(r, g, b, a)`
    com `a` em 0–255 ou em 0–1, `rgba(r, g, b, p%)`, e `#rrggbbaa`. `("", 255)` quando não há cor.

    **Existe porque o portão media a cor errada, e o defeito nº 1 do ciclo 5 é isso.** Um valor
    opaco lido de onde o produto desenha um translúcido dá um número que a tela não contém --
    e na direção que transforma reprovação em aprovação.
    """
    texto = valor.strip()
    achado = _RGBA.search(texto)
    if achado:
        r, g, b = (int(float(achado.group(i))) for i in (1, 2, 3))
        bruto = achado.group(4).strip()
        if bruto.endswith("%"):
            alfa = round(float(bruto[:-1]) * 255 / 100)
        else:
            numero = float(bruto)
            alfa = round(numero * 255) if numero <= 1.0 else round(numero)
        return f"#{r:02x}{g:02x}{b:02x}", max(0, min(255, alfa))
    achado = _COR_COM_ALFA.search(texto)
    if achado:
        cru = achado.group(0).lower()
        return cru[:7], int(cru[7:9], 16)
    return _cor_de(texto), 255


def compor(frente: str, fundo: str, *, alfa: int = 255) -> str:
    """A cor **composta**: `frente` a `alfa` sobre `fundo`, devolvida opaca em `#rrggbb`.

    É a aritmética que o Qt aplica e que este arnês não aplicava. `#000000` a alpha 128 sobre o
    poço `#f8f9fb` da pele clara dá `#7c7c7d` -- **3,96:1** contra o mesmo poço, e não os
    **7,08:1** do token opaco que o portão publicava para esse par (razão de **1,79×**, na
    direção errada). Alfa 255 devolve a frente intacta, e por isso ela pode ser chamada em todo
    par sem custo nem exceção.

    Sem `fundo`, não há sobre o que compor: devolve a frente como está. Compor contra nada e
    inventar um cinza seria a mesma família de defeito que este método vem fechar.
    """
    if alfa >= 255 or not frente or not fundo:
        return frente
    peso = alfa / 255.0
    a = frente.lstrip("#")
    b = fundo.lstrip("#")
    if len(a) != 6 or len(b) != 6:
        return frente
    canais = [
        round(int(a[i : i + 2], 16) * peso + int(b[i : i + 2], 16) * (1 - peso)) for i in (0, 2, 4)
    ]
    return "#" + "".join(f"{c:02x}" for c in canais)


ALFA_DA_DICA = 128
"""O alfa com que o Qt desenha o `placeholderText` quando a folha **não** declara a cor da dica.

Não é estimativa: sondado na janela viva, `le.palette().color(Active, PlaceholderText)` devolve
`#000000` **alpha 128** na pele clara e `#e9eaec` **alpha 128** na escura -- a cor de texto da
folha a 50 %. Com `placeholder-text-color` declarada, o mesmo sonda devolve o valor declarado a
alpha 255.

**É a regra que faltava ao portão.** Ele resolvia `PlaceholderText` pelo token opaco da
`QPalette`, que o Qt não pinta -- e por isso era estruturalmente incapaz de ver o par abaixo de
AA que a tela desenhava."""

CLASSES_COM_DICA = ("QLineEdit", "QTextEdit", "QPlainTextEdit", "QAbstractSpinBox")
"""As classes de campo que desenham `placeholderText`. Lista, árvore e tabela não têm dica."""


TRANSPARENTE = ("transparent", "none")


def fundo_de(regras: Sequence[Regra], alvo: Alvo) -> str:
    """A cor que fica **atrás** do texto daquele alvo, seguindo a cascata e a transparência.

    Três degraus, e cada um responde a um caso que a folha do produto tem:

    1. O `background-color` que a cascata deixa valendo naquele alvo.
    2. Se ele for transparente (`QMenuBar::item`, `QTabBar`), o fundo da **superfície de trás** --
       o mesmo alvo sem a subpeça, e depois sem os estados.
    3. Se nada disso responder, o `QWidget` -- que é o fundo de tudo, porque a folha o declara.

    Sem o degrau 2 o item de menu seria medido contra "nada" e um par real sumiria do relatório;
    é o mesmo defeito de não conhecer a herança de classes, num eixo diferente.
    """
    for propriedade in ("background-color", "background"):
        valor = valor_de(regras, alvo, propriedade)
        cor = _cor_de(valor)
        if cor:
            return cor
        if valor and valor.strip().lower() in TRANSPARENTE:
            break
    if alvo.subcontrole:
        return fundo_de(regras, alvo.sem_subcontrole())
    if alvo.estados:
        return fundo_de(regras, Alvo(alvo.classe, alvo.subcontrole, alvo.atributo, ancestral=alvo.ancestral))
    if alvo.classe != "QWidget":
        return fundo_de(regras, Alvo("QWidget"))
    return ""


# ------------------------------------------------------------------------------- os pares


@dataclass(frozen=True)
class Par:
    """Um par medido: onde ele aparece, que duas cores são, e se ele passa o piso dele."""

    onde: str
    frente: str
    fundo: str
    razao: float
    piso: float
    especie: str
    portao: bool
    """Se este par **reprova o build**. `False` para os isentos declarados no cabeçalho."""

    origem: str
    """`folha`, `paleta`, `marcacao` ou `tabuleiro` -- de que fonte o par foi derivado."""

    nota: str = ""

    def passou(self) -> bool:
        return (not self.portao) or self.razao >= self.piso


def _razao(a: str, b: str) -> float:
    from chess_diagram_ocr.ui.tokens import razao_de_contraste

    return razao_de_contraste(a, b)


def _morto(alvo: Alvo) -> bool:
    return "disabled" in alvo.estados


def _e_separador(cor: str, cromo_escuro: bool) -> bool:
    """Se aquele hexadecimal **é** o `SEPARADOR` da paleta em uso. Por valor, não por nome."""
    from chess_diagram_ocr.ui import tokens

    return cor.lower() == tokens.cor(tokens.SEPARADOR, None, cromo_escuro=cromo_escuro).lower()


def _e_foco(cor: str, cromo_escuro: bool) -> bool:
    from chess_diagram_ocr.ui import tokens

    return cor.lower() == tokens.cor(tokens.FOCO, None, cromo_escuro=cromo_escuro).lower()


SUBPECAS_SEM_TEXTO = frozenset(
    {"handle", "groove", "sub-page", "add-page", "chunk", "indicator", "separator", "pane"}
)
"""Subpeças que não desenham texto: a cor herdada delas não é par de texto, é enfeite.

Medir `color` contra fundo numa `QScrollBar::handle` produziria um par que nenhum olho vê. Elas
continuam sendo medidas como `grafico` -- é o preenchimento delas contra o trilho que importa."""

ESTADOS_TRANSITORIOS = frozenset({"hover", "pressed"})
"""Estados que existem só enquanto o ponteiro está lá.

A WCAG 1.4.11 fala de *estados* de componente, e a leitura razoável é a persistente: `checked`,
`selected`, `focus`. Um realce sob o ponteiro não é o único jeito de identificar o controle --
ele é a confirmação de que o ponteiro chegou --, e exigir 3:1 dele proibiria o realce discreto
que toda ferramenta profissional usa. Eles continuam medidos e aparecem no relatório; o que não
fazem é reprovar o build.

**O texto deles não entra nesta isenção**, e é onde estava o defeito de verdade: o rótulo do
botão primário caía para 4,47:1 sob o ponteiro e 3,09:1 pressionado."""

FUNDO_DO_PAINEL = "QWidget"
"""A classe cujo fundo é "o que está atrás" de um controle de topo.

A folha declara `QWidget { background-color: ... }`, e é ele que pinta todo painel: um botão
solto numa aba está sobre esse cinza. Um modelo mais fino exigiria a árvore de widgets, que só
existe numa janela viva -- e a diferença mudaria zero pares neste produto, porque nenhum painel
declara fundo próprio."""


def _limite(
    onde: str,
    *,
    borda: str,
    dentro: str,
    atras: str,
    especie: str,
    portao: bool,
    nota: str = "",
) -> Par:
    """O par de **limite de componente**: o controle se separa do fundo pela borda ou pelo corpo.

    **É o operador `max`, e a escolha é o item.** A primeira versão deste checador media a borda
    contra a própria face *e* contra o painel, e reprovava vinte pares em que a borda sumia dentro
    do botão -- o que não é defeito nenhum: uma borda que se funde ao preenchimento faz o
    preenchimento parecer um pouco maior, e o controle continua se lendo contra o painel. A 1.4.11
    pede que *alguma* informação visual que identifique o componente esteja a 3:1 das cores
    adjacentes; ela não pede que **todas** estejam.

    O que se mede, então, é o melhor dos dois caminhos pelos quais o olho acha o limite do
    controle -- e a nota carrega o número perdedor, para ninguém precisar acreditar no `max`.
    """
    por_borda = _razao(borda, atras) if borda and atras else 0.0
    por_corpo = _razao(dentro, atras) if dentro and atras else 0.0
    vence_a_borda = por_borda >= por_corpo
    return Par(
        onde=onde,
        frente=borda if vence_a_borda else dentro,
        fundo=atras,
        razao=max(por_borda, por_corpo),
        piso=PISO[especie],
        especie=especie,
        portao=portao,
        origem="folha",
        nota=(nota + " " if nota else "")
        + f"(borda {por_borda:.2f}:1, corpo {por_corpo:.2f}:1)",
    )


def pares_da_folha(folha: str, *, cromo_escuro: bool) -> list[Par]:
    """Os pares que a própria folha de estilo declara -- **derivados, e não listados**.

    Longa e ramificada de propósito: cada bloco é uma **família** de par (texto, seleção interna,
    limite de componente, estado persistente, preenchimento contra trilho, marca do indicador), e
    o que os une é a folha analisada uma vez. Quebrá-los em seis funções obrigaria a reanalisar a
    folha seis vezes ou a passar `regras`, `alvos`, `painel`, `vistos` e `guardar` adiante em
    todas -- cinco parâmetros de acoplamento para esconder um número de ramos.
    """
    regras = analisar(folha)
    pares: list[Par] = []
    vistos: set[tuple[str, str, str, str]] = set()

    def guardar(par: Par) -> None:
        chave = (par.onde, par.frente, par.fundo, par.especie)
        if chave not in vistos:
            vistos.add(chave)
            pares.append(par)

    alvos = {regra.alvo for regra in regras}
    # **`QAbstractItemView::item` vira os itens das classes concretas**, e é o que faz a seleção
    # ser medida contra o poço em que ela de fato cai. A regra da folha é escrita na base porque
    # ela vale para lista, árvore e tabela; o **fundo de repouso**, porém, é declarado em cada
    # classe concreta (`QListWidget { background-color: ... }`). Medir o item abstrato mediria a
    # seleção contra o cinza do painel, que é um fundo que nenhum item tem.
    concretas = sorted(
        {a.classe for a in alvos if "QAbstractItemView" in HERANCA.get(a.classe, ()) and not a.ancestral}
    )
    for alvo in [a for a in alvos if a.classe == "QAbstractItemView" and a.subcontrole and not a.ancestral]:
        alvos |= {
            Alvo(classe, alvo.subcontrole, alvo.atributo, alvo.estados) for classe in concretas
        }
    painel = fundo_de(regras, Alvo(FUNDO_DO_PAINEL))

    def descontado(alvo: Alvo) -> str:
        """Por que este alvo não reprova, se for o caso. Vazio quando ele é portão."""
        if _morto(alvo):
            return "componente inativo: isento pela WCAG 1.4.3/1.4.11"
        if alvo.estados & ESTADOS_TRANSITORIOS:
            return "estado transitório sob o ponteiro: medido, não é portão"
        return ""

    for alvo in sorted(alvos, key=str):
        fundo = fundo_de(regras, alvo)
        if not fundo:
            continue
        isento = descontado(alvo)

        # ---------------------------------------------------------------------------- texto
        frente = _cor_de(valor_de(regras, alvo, "color"))
        if frente and alvo.subcontrole not in SUBPECAS_SEM_TEXTO:
            # A régua e a linha de `QFrame` levam a cor do `SEPARADOR` na propriedade `color` e
            # não em `border`: o Qt pinta a moldura do `QFrame` com a cor do texto. Reconhecer
            # pelo **valor** é o que faz a isenção não depender do nome da propriedade.
            separador = _e_separador(frente, cromo_escuro)
            guardar(
                Par(
                    onde=str(alvo),
                    frente=frente,
                    fundo=fundo,
                    razao=_razao(frente, fundo),
                    piso=PISO[TEXTO],
                    especie=TEXTO,
                    # O texto do estado transitório **é** portão: foi exatamente ali que o
                    # rótulo do botão primário perdeu o piso AA.
                    portao=not _morto(alvo) and not separador,
                    origem="folha",
                    nota=(
                        "SEPARADOR: hierarquia e não informação (ver ui/tokens.py)"
                        if separador
                        else ("componente inativo: isento pela WCAG 1.4.3" if _morto(alvo) else "")
                    ),
                )
            )

        # ------------------------------------------------------------------- seleção interna
        selecao = _cor_de(valor_de(regras, alvo, "selection-color"))
        fundo_da_selecao = _cor_de(valor_de(regras, alvo, "selection-background-color"))
        if selecao and fundo_da_selecao:
            guardar(
                Par(
                    onde=f"{alvo} (texto selecionado)",
                    frente=selecao,
                    fundo=fundo_da_selecao,
                    razao=_razao(selecao, fundo_da_selecao),
                    piso=PISO[TEXTO],
                    especie=TEXTO,
                    portao=not _morto(alvo),
                    origem="folha",
                    nota="componente inativo: isento pela WCAG 1.4.3" if _morto(alvo) else "",
                )
            )

        # ------------------------------------------------------- a dica dentro do campo
        # **O par que o ciclo 5 reprovou, e o motivo de ele agora sair da folha e não do token.**
        # A `QPalette` deste produto declara `PlaceholderText = TEXTO_SECUNDARIO`, opaco -- e o
        # Qt **não pinta isso**: quando a folha põe `color:` num campo, o `QStyleSheetStyle`
        # recalcula a dica a partir dessa cor de texto, a `ALFA_DA_DICA`. O portão publicava o
        # token (7,08:1) para uma tela de 3,96:1. Aqui a dica é derivada como o Qt a deriva:
        # `placeholder-text-color` quando a folha a declara, senão `color` a alpha 128 -- e as
        # duas **compostas sobre o poço do campo** antes de a razão ser calculada.
        if alvo.classe in CLASSES_COM_DICA and not alvo.subcontrole:
            declarada, alfa_declarado = cor_e_alfa(valor_de(regras, alvo, "placeholder-text-color"))
            if declarada:
                dica = compor(declarada, fundo, alfa=alfa_declarado)
                razao_da_dica = "declarada na folha"
            elif frente:
                dica = compor(frente, fundo, alfa=ALFA_DA_DICA)
                razao_da_dica = (
                    f"NÃO declarada: o Qt deriva de color: {frente} a alpha {ALFA_DA_DICA}"
                )
            else:
                dica = ""
                razao_da_dica = ""
            if dica and dica != fundo:
                guardar(
                    Par(
                        onde=f"{alvo} (dica: placeholderText)",
                        frente=dica,
                        fundo=fundo,
                        razao=_razao(dica, fundo),
                        piso=PISO[TEXTO],
                        especie=TEXTO,
                        portao=not _morto(alvo),
                        origem="folha",
                        nota=(
                            f"{razao_da_dica}. "
                            + (
                                "componente inativo: isento pela WCAG 1.4.3"
                                if _morto(alvo)
                                else "campo habilitado: é o estado normal da aba"
                            )
                        ),
                    )
                )

        # ------------------------------------------------------------- limite do componente
        bordas = [
            _cor_de(valor_de(regras, alvo, propriedade))
            for propriedade in (
                "border",
                "border-bottom",
                "border-top",
                "border-right",
                "border-left",
            )
        ]
        borda = next((cor for cor in bordas if cor), "")
        atras = fundo_de(regras, alvo.sem_subcontrole()) if alvo.subcontrole else painel
        if not atras or atras == fundo:
            atras = painel
        if not borda:
            continue
        if _e_separador(borda, cromo_escuro):
            guardar(
                _limite(
                    f"{alvo} (limite)",
                    borda=borda,
                    dentro=fundo,
                    atras=atras,
                    especie=BORDA,
                    portao=False,
                    nota="SEPARADOR: hierarquia e não informação.",
                )
            )
        elif _e_foco(borda, cromo_escuro):
            guardar(
                _limite(
                    f"{alvo} (anel de foco)",
                    borda=borda,
                    dentro=fundo,
                    atras=atras,
                    especie=FOCO,
                    portao=True,
                    nota="WCAG 2.4.11: o foco tem de se ver.",
                )
            )
        else:
            guardar(
                _limite(
                    f"{alvo} (limite)",
                    borda=borda,
                    dentro=fundo,
                    atras=atras,
                    especie=BORDA,
                    portao=not isento,
                    nota=isento,
                )
            )

    # ------------------------------------------------- estado persistente contra o repouso
    # `checked` e `selected` são o que a 1.4.11 chama de estado: eles têm de se distinguir do
    # repouso, e por isso a comparação não é contra o painel e sim contra a **mesma peça sem o
    # estado**. O `max` de novo: o item de menu selecionado da paleta escura fica a 2,75:1 pelo
    # preenchimento e a 5,26:1 pela borda de foco, e é a borda que o identifica.
    for alvo in sorted((a for a in alvos if a.estados & {"checked", "selected"}), key=str):
        repouso = Alvo(
            alvo.classe, alvo.subcontrole, alvo.atributo, alvo.estados - {"checked", "selected"}
        )
        aceso, apagado = fundo_de(regras, alvo), fundo_de(regras, repouso)
        if not aceso or not apagado or aceso == apagado:
            continue
        guardar(
            _limite(
                f"{alvo} contra {repouso}",
                borda=_cor_de(valor_de(regras, alvo, "border")),
                dentro=aceso,
                atras=apagado,
                especie=GRAFICO,
                portao=not _morto(alvo),
            )
        )

    # ------------------------------------------------------- preenchimento contra o trilho
    for classe, subpeca, trilho in (
        ("QProgressBar", "chunk", Alvo("QProgressBar")),
        ("QScrollBar", "handle", Alvo("QScrollBar")),
        ("QSlider", "sub-page", Alvo("QSlider", "groove", estados=frozenset({"horizontal"}))),
        ("QSlider", "handle", Alvo("QSlider", "groove", estados=frozenset({"horizontal"}))),
    ):
        escolhidos = [a for a in alvos if a.subcontrole == subpeca and a.classe == classe]
        for alvo in sorted(escolhidos, key=str):
            frente = _cor_de(valor_de(regras, alvo, "background-color"))
            atras = fundo_de(regras, trilho)
            if not frente or not atras or frente == atras:
                continue
            guardar(
                _limite(
                    f"{alvo} sobre {trilho}",
                    borda=_cor_de(valor_de(regras, alvo, "border")),
                    dentro=frente,
                    atras=atras,
                    especie=GRAFICO,
                    portao=not _morto(alvo) and not (alvo.estados & ESTADOS_TRANSITORIOS),
                    nota=descontado(alvo),
                )
            )

    # ------------------------------------------------------- a marca dentro do indicador
    # O que diz "esta caixa está marcada" é o preenchimento **contra o preenchimento da caixa
    # vazia**, e não contra o painel: a caixa vazia já se identifica pela borda dela, medida
    # acima. Sem esta distinção o checador reprovava o poço vazio por ser parecido com o painel,
    # que é exatamente o que ele deve ser.
    for classe in ("QCheckBox", "QRadioButton"):
        vazio = fundo_de(regras, Alvo(classe, "indicator"))
        for estado in ("checked", "indeterminate"):
            alvo = Alvo(classe, "indicator", estados=frozenset({estado}))
            marca = _cor_de(valor_de(regras, alvo, "background-color"))
            if not marca or not vazio or marca == vazio:
                continue
            guardar(
                Par(
                    onde=f"{alvo} contra o indicador vazio",
                    frente=marca,
                    fundo=vazio,
                    razao=_razao(marca, vazio),
                    piso=PISO[GRAFICO],
                    especie=GRAFICO,
                    portao=True,
                    origem="folha",
                )
            )
    return pares


PARES_DA_PALETA: tuple[tuple[str, str, str], ...] = (
    ("WindowText", "Window", TEXTO),
    ("Text", "Base", TEXTO),
    ("ButtonText", "Button", TEXTO),
    ("HighlightedText", "Highlight", TEXTO),
    ("PlaceholderText", "Base", TEXTO),
    ("ToolTipText", "ToolTipBase", TEXTO),
    ("Link", "Base", TEXTO),
    ("Link", "Window", TEXTO),
    ("LinkVisited", "Base", TEXTO),
    ("Mid", "Window", BORDA),
    ("Highlight", "Base", GRAFICO),
    ("Highlight", "Window", GRAFICO),
)
"""`(frente, fundo, espécie)` da `QPalette`, pelos nomes dos papéis do Qt.

**São os pares que o desenho nativo produz por baixo da folha**, e por isso não podem ser
derivados dela. `HighlightedText` sobre `Highlight` é o item selecionado que o *delegate* pinta;
`PlaceholderText` sobre `Base` é a dica dentro do campo; `Mid` sobre `Window` é a borda que o
`QStyle` desenha em quem a folha não alcança. `Highlight` sobre `Base` e sobre `Window` é a
linha selecionada contra as duas superfícies em que uma seleção **persiste** -- o poço da lista e
o painel.

**`BrightText` não está aqui, e a ausência é decisão.** O Qt o usa como letra sobre fundo
saturado, e o único fundo saturado deste produto são as duas faces de ênfase -- que a folha
declara e o par `QPushButton[papel=...]` já mede. Um par `BrightText` sobre `Highlight` seria um
par que o produto não desenha, e um checador que inventa pares mede a si mesmo.

A lista é curta porque a `QPalette` é pequena e fechada: ela não cresce com o produto, ao
contrário da folha. É o único lugar deste módulo em que pares são escritos à mão."""


def pares_da_paleta(*, cromo_escuro: bool, folha: str = "") -> list[Par]:
    """Os pares da `QPalette`, do grupo vivo e do grupo morto -- **com o alfa composto**.

    **Duas correções, e as duas são o defeito nº 1 do ciclo 5.**

    1. **Compõe o alfa antes de calcular a razão.** Um papel de paleta que chegue translúcido
       era medido pelo valor opaco, e um portão que reporta o token opaco de um pixel
       translúcido esconde o próximo defeito desta família tão bem quanto escondeu este.
    2. **`PlaceholderText` sai da folha, e não do token.** O Qt não pinta o
       `PAPEIS_DA_PALETA["PlaceholderText"]` num campo que a folha estiliza: o
       `QStyleSheetStyle` sobrescreve a dica com `placeholder-text-color`, se ela existir, ou
       com a cor de texto da folha a `ALFA_DA_DICA`. Enquanto este par foi resolvido pelo
       token, ele publicou **7,08:1** para uma tela de **3,96:1**.

    Sem `folha`, o par de dica cai no token e **diz isso na nota** -- um número sem a folha é um
    número sobre a paleta e não sobre a tela, e o relatório não deve deixar isso implícito.
    """
    from chess_diagram_ocr.ui import tokens
    from chess_diagram_ocr.ui.folha_de_estilo import PAPEIS_DA_PALETA, PAPEIS_DA_PALETA_MORTA

    regras = analisar(folha) if folha else []

    def tinta(mapa: dict[str, str], nome: str) -> tuple[str, int]:
        papel = mapa.get(nome) or PAPEIS_DA_PALETA[nome]
        return cor_e_alfa(tokens.cor(papel, None, cromo_escuro=cromo_escuro))

    def dica_da_folha(morto: bool) -> tuple[str, int, str]:
        """`(cor, alfa, nota)` da dica como o **Qt** a resolve, lida da folha do produto."""
        if not regras:
            return "", 255, "sem a folha: token da paleta, que o QSS sobrescreve"
        alvo = Alvo("QLineEdit", estados=frozenset({"disabled"}) if morto else frozenset())
        declarada, alfa = cor_e_alfa(valor_de(regras, alvo, "placeholder-text-color"))
        if declarada:
            return declarada, alfa, "placeholder-text-color declarada na folha"
        texto = _cor_de(valor_de(regras, alvo, "color"))
        return texto, ALFA_DA_DICA, f"NÃO declarada: o Qt deriva de color: a alpha {ALFA_DA_DICA}"

    pares: list[Par] = []
    for grupo, mapa, portao in (
        ("Active", PAPEIS_DA_PALETA, True),
        ("Disabled", PAPEIS_DA_PALETA_MORTA, False),
    ):
        for frente, fundo, especie in PARES_DA_PALETA:
            a, alfa_a = tinta(mapa, frente)
            b, _ = tinta(mapa, fundo)
            observacao = ""
            if frente == "PlaceholderText":
                da_folha, alfa_da_folha, observacao = dica_da_folha(grupo == "Disabled")
                if da_folha:
                    a, alfa_a = da_folha, alfa_da_folha
            composta = compor(a, b, alfa=alfa_a)
            if composta == b:
                continue
            nota = "componente inativo: isento" if not portao else ""
            if alfa_a < 255:
                nota = (nota + " " if nota else "") + f"{a} a alpha {alfa_a} composto sobre {b}"
            if observacao:
                nota = (nota + " " if nota else "") + observacao
            pares.append(
                Par(
                    onde=f"QPalette.{grupo}: {frente} sobre {fundo}",
                    frente=composta,
                    fundo=b,
                    razao=_razao(composta, b),
                    piso=PISO[especie],
                    especie=especie,
                    portao=portao,
                    origem="paleta",
                    nota=nota,
                )
            )
    return pares


NAO_DESENHADO_NO_QT = ("COORDENADA",)
"""Papéis da paleta que o frontend Qt **não pinta**, e que por isso não geram par.

`COORDENADA` é a letra a–h e o número 8–1 em volta do tabuleiro. O tabuleiro do Qt não os
desenha -- está escrito na constante que decide a folga: `qt/tabuleiro.py`, `MARGEM = 8`, *"é o
mesmo `margin` que `board_widget` passa quando não desenha coordenadas -- e este tabuleiro não
desenha"*. Medir um par que o produto não pinta encheria o relatório de uma reprovação que
ninguém consegue ver na tela, que é a forma mais rápida de um portão de contraste perder a
autoridade.

**Continua sendo um débito, e o relatório o nomeia**: no dia em que a aba Estudo ganhar
coordenadas, `COORDENADA` (`#5c5c5c`) sobre `SUPERFICIE_TABULEIRO` dá **2,02:1** e precisa de
valor novo antes de a primeira letra ser desenhada."""


PARES_DE_ESTADO: tuple[tuple[str, str, str], ...] = (
    ("TEXTO_PADRAO", "TEXTO_MORTO", "a letra do rótulo vivo contra a do morto"),
)
"""`(papel vivo, papel morto, frase)` -- as distâncias entre estados que o olho tem de ler.

Uma só hoje, e ela é a que o ciclo 9 mediu. A tupla existe para a segunda: no dia em que o
produto tiver um terceiro estado de tinta (um "somente leitura", digamos), a distância dele entra
aqui e o portão a cobra sem que ninguém precise lembrar."""


def pares_de_estado(*, cromo_escuro: bool) -> list[Par]:
    """A distância vivo ↔ morto, como par próprio e com piso de 3,0:1 (F9-C10).

    **É o par que faltava, e ele não é uma medida de legibilidade.** Os outros pares perguntam
    *"dá para ler?"*; este pergunta *"dá para ver que não responde?"*. São perguntas diferentes e
    podem puxar em sentidos opostos: no cromo escuro, `morto ≥ 4,5:1 contra a superfície` e
    `vivo↔morto ≥ 3,0:1` são incompatíveis por uma casa decimal, e o produto escolheu o segundo
    -- com o motivo escrito em `ui/tokens.TEXTO_MORTO`, e amparado na isenção que a própria WCAG
    1.4.3 dá ao texto de componente inativo.

    O par de legibilidade continua medido, e continua no relatório: `TEXTO_MORTO` contra a
    superfície entra como `GRAFICO` -- o piso que o produto assume para ele -- em vez de sumir.
    """
    from chess_diagram_ocr.ui import tokens

    def cor(papel: str) -> str:
        return tokens.cor(papel, None, cromo_escuro=cromo_escuro)

    pares: list[Par] = []
    for vivo, morto, frase in PARES_DE_ESTADO:
        a, b = cor(vivo), cor(morto)
        pares.append(
            Par(
                onde=f"estado: {frase}",
                frente=a,
                fundo=b,
                razao=_razao(a, b),
                piso=PISO[ESTADO],
                especie=ESTADO,
                portao=True,
                origem="estado",
                nota=(
                    "um estado que o olho não separa não é um estado; era 2,82:1 (clássica) e "
                    "1,88:1 (Foco) antes do F9-C10"
                ),
            )
        )
        superficie = cor("SUPERFICIE_PADRAO")
        pares.append(
            Par(
                onde=f"estado: a letra do rótulo morto sobre a superfície",
                frente=b,
                fundo=superficie,
                razao=_razao(b, superficie),
                piso=PISO[GRAFICO],
                especie=GRAFICO,
                portao=True,
                origem="estado",
                nota=(
                    "isento do piso de texto pela WCAG 1.4.3 (componente inativo) e medido "
                    "mesmo assim: o morto continua tendo de se ler"
                ),
            )
        )
    return pares


def pares_pintados(*, cromo_escuro: bool) -> list[Par]:
    """As marcações sobre a página e o tabuleiro -- o que o `QPainter` desenha sem folha.

    **Derivados de `tokens.SIGNIFICADO`**, a tabela em que cada marcação declara em que
    superfície ela vive. Uma marcação nova entra no relatório por existir na tabela, que é a
    mesma disciplina que `test_ui_semantica_cor` usa do outro lado.

    **A marcação de tabuleiro é medida contra as casas, e não contra o fundo em volta**, e a
    diferença não é sutil: `SUPERFICIE_TABULEIRO` é a cor **fora** do tabuleiro, e nenhuma das
    cinco marcações de casa cai ali. Uma medição contra o fundo errado reprovaria as cinco por um
    contraste que ninguém vê e deixaria passar o que importa -- que é a marcação sumir dentro da
    casa clara ou da escura.

    As superfícies de documento **não seguem a pele** (S-224): a folha do livro e o tabuleiro
    ficam na paleta medida, e por isso estes pares repetem valor entre as duas peles. Repetir é a
    resposta certa -- o que mudaria o número aqui seria justamente o defeito.
    """
    from chess_diagram_ocr.ui import tokens

    def cor(papel: str) -> str:
        return tokens.cor(papel, None, cromo_escuro=cromo_escuro)

    pares: list[Par] = []
    fundos_de = {
        tokens.PAGINA: ((tokens.SUPERFICIE_PAGINA, "a folha do livro"),),
        tokens.TABULEIRO: ((tokens.CASA_CLARA, "a casa clara"), (tokens.CASA_ESCURA, "a casa escura")),
    }
    for papel, (superficie, frase) in sorted(tokens.SIGNIFICADO.items()):
        if papel in NAO_DESENHADO_NO_QT:
            continue
        for fundo, rotulo in fundos_de[superficie]:
            a, b = cor(papel), cor(fundo)
            pares.append(
                Par(
                    onde=f"marcação {papel} sobre {rotulo}",
                    frente=a,
                    fundo=b,
                    razao=_razao(a, b),
                    piso=PISO[GRAFICO],
                    especie=GRAFICO,
                    portao=True,
                    origem="marcacao",
                    nota=frase,
                )
            )

    # ------------------------------------------------------------------ a peça sobre a casa
    # **O par é o traço, e não o preenchimento.** O glifo de reserva é desenhado com contorno
    # (`qt/tabuleiro.py`), porque o `#f8f8f8` da peça branca sobre a casa clara `#f0d9b5` dá
    # **1,29:1** -- uma peça desenhada e invisível em metade do tabuleiro. Quem separa a peça da
    # casa é a linha em volta dela, e é ela que este par mede.
    for glifo, traco in (
        (tokens.GLIFO_CLARO, tokens.GLIFO_ESCURO),
        (tokens.GLIFO_ESCURO, tokens.GLIFO_CLARO),
    ):
        for casa in (tokens.CASA_CLARA, tokens.CASA_ESCURA, tokens.CASA_ULTIMO_LANCE):
            par = _limite(
                f"peça {glifo} sobre {casa}",
                borda=cor(traco),
                dentro=cor(glifo),
                atras=cor(casa),
                especie=GRAFICO,
                portao=True,
            )
            pares.append(
                Par(**{**par.__dict__, "origem": "tabuleiro", "nota": "corpo ou traço: o que separar melhor. " + par.nota})
            )
    return pares


# ----------------------------------------------------------------------------- o relatório


@dataclass
class Pele:
    """O resultado de uma pele: todos os pares dela e o veredito."""

    nome: str
    cromo_escuro: bool
    pares: list[Par] = field(default_factory=list)

    def reprovados(self) -> list[Par]:
        return [par for par in self.pares if not par.passou()]

    def sob_portao(self) -> list[Par]:
        return [par for par in self.pares if par.portao]

    def pior(self) -> Par | None:
        candidatos = self.sob_portao()
        return min(candidatos, key=lambda par: par.razao - par.piso) if candidatos else None

    def passou(self) -> bool:
        return not self.reprovados()


SABOTAGEM_ESCURA = "#787d85"
"""`TEXTO_SECUNDARIO` a **3,90:1** sobre a superfície padrão do cromo escuro (`#1f2124`).

É a sabotagem do passo 16 da OCR_UI: um par de texto abaixo do piso AA de 4,5:1, plantado só
na pele escura. O portão tem de acusar exatamente um par a mais na escura e nenhum na clara;
se não acusar, ele não está lendo a folha da Foco."""


def medir(
    *, caminho_do_tronco: Path = TRONCO, densidades: Iterable[str] = (), sabotar: bool = False
) -> dict[str, Any]:
    """Mede as duas peles inteiras e devolve o relatório. É o que o teste e o CLI chamam.

    `sabotar` troca `TEXTO_SECUNDARIO` do cromo escuro por `SABOTAGEM_ESCURA` só durante a
    medição -- a tabela de tokens é restaurada antes de devolver, porque um portão que deixa o
    produto sabotado é pior que um que não mede.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import folha_de_estilo as folha_pura
    from chess_diagram_ocr.ui import pele as peles
    from chess_diagram_ocr.ui import tokens as tokens_do_tronco

    if sabotar:
        original = tokens_do_tronco.NO_CROMO_ESCURO[tokens_do_tronco.TEXTO_SECUNDARIO]
        tokens_do_tronco.NO_CROMO_ESCURO[tokens_do_tronco.TEXTO_SECUNDARIO] = SABOTAGEM_ESCURA
        try:
            relatorio = medir(caminho_do_tronco=caminho_do_tronco, densidades=densidades)
        finally:
            tokens_do_tronco.NO_CROMO_ESCURO[tokens_do_tronco.TEXTO_SECUNDARIO] = original
        relatorio["sabotagem"] = f"TEXTO_SECUNDARIO do cromo escuro = {SABOTAGEM_ESCURA} (3,90:1)"
        return relatorio

    lista = list(densidades) or [peles.CONFORTAVEL, peles.COMPACTA]
    resultados: list[Pele] = []
    for nome, cromo_escuro in (("claro", False), ("escuro", True)):
        pele = Pele(nome=nome, cromo_escuro=cromo_escuro)
        vistos: set[tuple[str, str, str]] = set()
        folhas = [
            folha_pura.folha_de_estilo(cromo_escuro=cromo_escuro, densidade=densidade)
            for densidade in lista
        ]
        for folha in folhas:
            for par in pares_da_folha(folha, cromo_escuro=cromo_escuro):
                chave = (par.onde, par.frente, par.fundo)
                if chave not in vistos:
                    vistos.add(chave)
                    pele.pares.append(par)
        # A folha entra aqui porque a `QPalette` **não** é a última palavra sobre o que o Qt
        # pinta: o QSS sobrescreve a dica do campo. A densidade não move cor nenhuma -- ela
        # move folga e raio --, então a primeira folha responde por todas.
        pele.pares += pares_da_paleta(cromo_escuro=cromo_escuro, folha=folhas[0])
        pele.pares += pares_pintados(cromo_escuro=cromo_escuro)
        pele.pares += pares_de_estado(cromo_escuro=cromo_escuro)
        resultados.append(pele)

    reprovados = {pele.nome: [asdict(par) for par in pele.reprovados()] for pele in resultados}
    return {
        "portao": (
            "SPEC 11.3 -- contraste WCAG 2.1 AA em 100 % dos pares, nas duas polaridades de "
            "cromo x as duas densidades"
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "metodo": {
            "pares": "derivados da folha de estilo, da QPalette, de tokens.SIGNIFICADO e do tabuleiro",
            "pisos": {
                "texto": AA_TEXTO,
                "foco": AA_GRAFICO,
                "borda": AA_GRAFICO,
                "grafico": AA_GRAFICO,
                "estado": AA_GRAFICO,
            },
            "densidades": lista,
            "isencoes": [
                ":disabled -- componente inativo, isento pela WCAG 1.4.3 e 1.4.11 (medido mesmo assim)",
                (
                    "TEXTO_MORTO sobre a superficie -- 4,10:1 na pele escura, abaixo do piso de "
                    "texto e acima do de grafico. A isencao e' da WCAG 1.4.3; a escolha esta em "
                    "ui/tokens.TEXTO_MORTO, e o par de estado (3,27:1) e' o que ela compra."
                ),
                "SEPARADOR -- reconhecido por valor; hierarquia e não informação (ui/tokens.py)",
            ],
        },
        "peles": [
            {
                "nome": pele.nome,
                "pares": len(pele.pares),
                "sob_portao": len(pele.sob_portao()),
                "reprovados": len(pele.reprovados()),
                "pior_folga": (
                    f"{pele.pior().razao:.2f}:1 contra piso {pele.pior().piso:.1f} em {pele.pior().onde}"
                    if pele.pior()
                    else ""
                ),
                "por_origem": {
                    origem: sum(1 for par in pele.pares if par.origem == origem)
                    for origem in ("folha", "paleta", "marcacao", "tabuleiro")
                },
                "veredito": "PASSOU" if pele.passou() else "REPROVOU",
            }
            for pele in resultados
        ],
        "reprovados": reprovados,
        "todos_os_pares": {
            pele.nome: [asdict(par) for par in sorted(pele.pares, key=lambda p: p.razao)]
            for pele in resultados
        },
        "veredito": "PASSOU" if all(pele.passou() for pele in resultados) else "REPROVOU",
    }


def tabela(relatorio: dict[str, Any]) -> str:
    """A tabela curta do terminal. O JSON é a prova; isto é o que se lê de relance."""
    linhas = [relatorio["portao"], ""]
    for pele in relatorio["peles"]:
        linhas.append(
            f"  {pele['nome']:<8} {pele['pares']:>4} pares  "
            f"{pele['sob_portao']:>4} sob portão  {pele['reprovados']:>3} reprovados  "
            f"{pele['veredito']}"
        )
        linhas.append(f"           menor folga: {pele['pior_folga']}")
    for nome, reprovados in relatorio["reprovados"].items():
        if not reprovados:
            continue
        linhas.append("")
        linhas.append(f"  Reprovados na pele {nome}:")
        for par in sorted(reprovados, key=lambda p: p["razao"]):
            linhas.append(
                f"    {par['razao']:>6.2f}:1 (piso {par['piso']:.1f}, {par['especie']}) "
                f"{par['frente']} sobre {par['fundo']} -- {par['onde']}"
            )
    linhas.append("")
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    return "\n".join(linhas)


def _preparar(caminho_do_tronco: Path) -> None:
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contraste WCAG AA de todos os pares (SPEC 11.3).")
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument(
        "--saida",
        type=Path,
        required=True,
        # **Sem padrão, e isto é um conserto de higiene** (F9-C12, item 16 do ciclo 11). O
        # padrão era `benchmarks/reports/ui/` -- a pasta do construtor --, e o crítico do
        # ciclo 11 rodou uma sabotagem sem `--saida`: o JSON foi gravar na pasta que ele não
        # pode tocar, e ele teve de movê-lo à mão. Um padrão que escreve na pasta de outro
        # agente é uma armadilha; quem roda um portão diz onde quer o relatório.
        help="onde gravar o relatorio. Obrigatorio: este portao nao escolhe pasta por voce.",
    )
    parser.add_argument("--todos", action="store_true", help="lista todos os pares, não só os reprovados")
    parser.add_argument(
        "--sabotar",
        action="store_true",
        help="planta um par de texto a 3,9:1 na pele escura; o portao tem de acusar exatamente ele",
    )
    args = parser.parse_args(argv)

    relatorio = medir(caminho_do_tronco=args.tronco, sabotar=args.sabotar)
    args.saida.mkdir(parents=True, exist_ok=True)
    # **Carimbado, e o motivo é uma perda de evidência real.** `contraste.json` era um nome
    # fixo: rodar o portão apagava a medição do ciclo anterior sem aviso. O crítico do ciclo 5
    # caiu nisso na sessão dele e declarou; o mesmo defeito, na família de instrumentos que
    # grava PNG, já tinha destruído 17 capturas em dois ciclos. `bloqueio_*.json`,
    # `fps_*.json` e `progresso_*.json` sempre carimbaram -- este passou a carimbar também.
    alvo = args.saida / f"contraste_{'sabotagem_' if args.sabotar else ''}{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")

    print(tabela(relatorio))
    if args.todos:
        for nome, pares in relatorio["todos_os_pares"].items():
            print(f"\n--- {nome} ---")
            for par in pares:
                print(
                    f"  {par['razao']:>6.2f}:1 piso {par['piso']:.1f} {par['especie']:<9} "
                    f"{'portao' if par['portao'] else 'isento':<7} {par['onde']}"
                )
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


def _todos(relatorio: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for pares in relatorio["todos_os_pares"].values():
        yield from pares


if __name__ == "__main__":
    raise SystemExit(main())
