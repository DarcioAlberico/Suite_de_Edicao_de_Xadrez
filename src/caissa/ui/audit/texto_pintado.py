"""O portão do texto **pintado**: a régua pergunta a fonte a quem o Qt de fato consulta.

**Por que este arquivo existe, e ele é o conserto de uma cegueira e não de um número.** Toda régua
de texto desta frente -- a de texto cortado do ciclo 11, o censo de ícones, a de rótulo de botão --
pergunta a largura e a altura do desenho a `QWidget.fontMetrics()`. E a janela **não** é
necessariamente pintada com aquela fonte: a folha de estilo tem regras de subcontrole que trocam o
tamanho e o peso na hora de desenhar. O que faltava era a régua da outra metade.

**E "a outra metade" não é sempre a folha -- é o que o ciclo 16 conserta.** A primeira forma desta
régua perguntava a fonte à folha nos três subcontroles, sobre a premissa escrita em
`ui/folha_de_estilo._escala_tipografica` de que *"o QSS de subcontrole é o que o Qt honra ao
pintar"*. Medida no pixel, a premissa é falsa em um dos quatro seletores: em `QGroupBox::title` o
Qt **descarta** a fonte da folha e desenha com a do widget, e na janela do produto isso era esta
régua dizendo **85 px onde a tela desenhava 34**. Quem responde qual das duas ganha é
`ui/folha_de_estilo.QUEM_PINTA`, medido em `benchmarks/reports/ui/c16/c16_quem_pinta.py`; quem a
consulta é `fonte_que_pinta`, e é dela que sai toda medida daqui.

O preço foi medido: `QGroupBox::title` pinta 12 pt negrito -- **21 px** -- dentro de uma faixa que
`margin-top` reservava a partir de `espaco.linha()`, **4 px na compacta**. Seis de seis títulos da
janela saíam com até 8 dos seus 21 px **debaixo do primeiro filho do próprio grupo**, e as réguas
todas devolviam `0` porque mediam 16 px de altura onde o Qt desenhava 21. Estava fotografado nos
ciclos 10, 12 e 13 e nenhuma régua o via.

---

**A régua não tem uma tabela de regras, e é o ponto.** Uma lista de "as quatro regras que trocam
a fonte" é a mesma doença um andar acima: a quinta regra nasceria fora dela. `regras_de_fonte`
**lê a folha aplicada** (`QApplication.styleSheet()`), acha toda declaração de `font-*` e devolve
o seletor de cada uma. Uma regra nova entra na régua no mesmo commit em que entra na folha.

**E o tamanho do ponto cego vira número publicado.** Cada achado sabe dizer se ele é `cego` --
se a fonte que **pinta** difere da fonte do widget --, e o portão soma. É a medida da distância
entre o que a tela desenha e o que uma régua comum enxerga. No ciclo 14 ela era 84 de 564 e caiu a
24 porque o produto parou de divergir (o cabeçalho dos treze diálogos); no ciclo 16 ela cai de
novo, e desta vez porque a **régua** parou de errar: os títulos de grupo, que a régua contava como
cegos, são pintados pela fonte do widget e portanto nunca foram cegos. O número que sobra é o dos
seletores em que a folha de fato ganha.

**Dois defeitos, e os dois apagam letra:**

* **coberto** -- a tinta do texto e a geometria de outro widget se cruzam. É o bloqueante do
  ciclo 13: não é elisão com reticência, que é recurso legítimo; é tinta que outro widget pinta
  por cima, e o leitor não tem como recuperar o que sumiu.
* **cortado** -- a tinta pede mais largura do que a caixa tem. É o `Resultad·` do cabeçalho de
  `DialogoDePartidas`: 76 px pintados numa seção de 68.

**A aritmética mora antes do primeiro `import PyQt6`, e é deliberado** -- é a mesma disciplina de
`quadros.py`. A parte que decide (ler a folha, casar seletor com widget, dizer quanto foi coberto
e quanto foi cortado) é pura e afirmada por teste no venv da suíte, que **não tem binding de Qt**.
O Qt só entra dentro das funções que abrem a janela.

Uso (venv do tronco, que é onde o PyQt6 mora):

    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
    PYTHONPATH=<suite>/src;<tronco>/src \
    <tronco>/.venv/Scripts/python.exe -m caissa.ui.audit.texto_pintado \
        --pdf "<livro>.pdf" --saida <pasta>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UTC = timezone(timedelta(0))
"""`datetime.UTC` só existe no 3.11 e o venv do tronco é 3.10. Ver `capture.UTC`."""

TRONCO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

PROPRIEDADES_DE_FONTE = ("font-size", "font-weight", "font-family", "font-style")
"""As declarações de `QSS` que mudam o **desenho** do texto, e que esta régua sabe interpretar.

`font` (a forma curta) não está aqui porque esta análise **não a interpreta**: ela empacota
família, tamanho, peso e estilo numa gramática própria, e adivinhar qual metade de
`font: bold 20pt "Segoe UI"` é o tamanho seria um analisador a mais para manter sem um caso na
folha que o exercite.

**O que mudou no ciclo 16 é que não interpretar deixou de ser não enxergar.** Enquanto
`_declaracoes_de_fonte` filtrava por esta mesma tupla, uma regra escrita na forma curta escapava
das **duas** peneiras ao mesmo tempo -- `regras_de_fonte` não a via e `seletores_ignorados` não a
contava --, e o portão publicava `0 seletores fora da análise` sobre uma folha que ele não tinha
lido. O crítico do ciclo 15 sabotou a folha por quatro caminhos e este foi o único que passou
calado. Hoje quem decide se uma declaração **mexe na fonte** é `mexe_na_fonte`, que é mais larga
que esta tupla; quem decide se a régua **sabe interpretá-la** é esta tupla; e a diferença entre as
duas vira `seletores_ignorados` -- número publicado, ver `test_a_forma_curta_de_font_nao_escapa`."""

PREFIXO_DE_FONTE = "font"
"""Toda declaração de `QSS` que mexe na fonte começa assim: `font`, `font-size`, `font-weight`…"""

O_WIDGET = "widget"
"""Quem pinta este subcontrole é `QWidget.font()`: o Qt descarta o `font-*` da folha."""

A_FOLHA = "folha"
"""Quem pinta este subcontrole é a declaração da folha, que ganha do `QWidget.font()`."""

SELETOR_DO_TITULO = "QGroupBox::title"
SELETOR_DO_CABECALHO = "QHeaderView::section"
SELETOR_DA_ABA = "QTabBar::tab:selected"
"""Os três seletores que as três réguas daqui medem, escritos como a folha os escreve.

São a chave de `ui/folha_de_estilo.QUEM_PINTA`, e por isso o literal é o de lá. Um seletor que a
folha renomeie faz `_quem_pinta` levantar em vez de a régua medir a fonte errada em silêncio."""

PONTOS_POR_PIXEL = 72 / 96
"""Um pixel a 96 dpi vale `72/96` de ponto. É a conversão que o Qt faz para `font-size: Npx`."""

PESO_NEGRITO = 600
"""De onde para cima um `font-weight` numérico conta como negrito, como em `ui/tipografia.PESOS`."""


# --------------------------------------------------------------------- a aritmética, pura


@dataclass(frozen=True)
class Fonte:
    """A fonte de um desenho: família, tamanho em ponto, peso e estilo. Comparável por valor.

    **`italico` entrou no ciclo 16 e a razão é a mesma da forma curta `font:`**: `font-style`
    estava em `PROPRIEDADES_DE_FONTE` -- isto é, declarado como "eu sei ler isto" -- e `_aplicar`
    não tinha ramo para ele. Uma regra `font-style: italic` era contada como analisada e jogada
    fora em seguida, e o itálico muda o avanço horizontal do texto. Era o mesmo defeito da forma
    curta com o sinal trocado: em vez de escapar das duas peneiras, escapava só da segunda.
    """

    familia: str = ""
    pontos: float = 0.0
    negrito: bool = False
    italico: bool = False

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "familia": self.familia,
            "pontos": self.pontos,
            "negrito": self.negrito,
            "italico": self.italico,
        }


@dataclass(frozen=True)
class Regra:
    """Uma regra da folha que mexe na fonte: para quem ela vale e o que ela declara."""

    classe: str
    subcontrole: str = ""
    estados: tuple[str, ...] = ()
    propriedades: tuple[tuple[str, str], ...] = ()
    declaracoes: tuple[tuple[str, str], ...] = ()

    def vale_para(
        self,
        *,
        classes: Sequence[str],
        subcontrole: str = "",
        estados: Sequence[str] = (),
        propriedades: Mapping[str, str] | None = None,
    ) -> bool:
        """A regra alcança este widget neste subcontrole?

        O casamento é o do `QSS` no que esta régua precisa dele: a classe tem de estar na
        ascendência do widget (`classes` é o MRO, e é o que faz `QTextBrowser` receber o que a
        folha diz de `QTextEdit`), o subcontrole tem de ser o mesmo, e os estados e as
        propriedades da regra têm de estar presentes -- os do widget podem ser mais.
        """
        if self.classe not in classes or self.subcontrole != subcontrole:
            return False
        if not set(self.estados).issubset({str(e) for e in estados}):
            return False
        tem = {str(chave): str(valor) for chave, valor in (propriedades or {}).items()}
        return all(tem.get(chave) == valor for chave, valor in self.propriedades)


_BLOCO = re.compile(r"([^{}]+)\{([^{}]*)\}")
_SELETOR = re.compile(
    r"^(?P<classe>[A-Za-z_]\w*)"
    r"(?P<propriedades>(?:\[[^\]]*\])*)"
    r"(?:::(?P<subcontrole>[\w-]+))?"
    r"(?P<estados>(?::[!\w-]+)*)$"
)
_PROPRIEDADE = re.compile(r"\[\s*([\w-]+)\s*=\s*\"?([^\"\]]*)\"?\s*\]")


def regras_da_folha(qss: str) -> tuple[Regra, ...]:
    """Toda regra da folha que esta análise entende, **na ordem em que ela aparece**.

    A ordem importa e é a do `QSS`: entre duas regras de mesma especificidade, a última ganha.
    Manter a ordem do texto é o que faz `fonte_da_folha` e `caixa_da_folha` responderem o que o
    Qt desenha, e não uma média de declarações.

    Seletor que esta análise não entende -- descendência, vírgula, `*` -- é **ignorado**, e
    ignorado em silêncio seria o defeito desta régua. Ver `seletores_ignorados`.
    """
    achadas: list[Regra] = []
    for seletor_bruto, corpo in _BLOCO.findall(qss):
        declaracoes = _declaracoes(corpo)
        if not declaracoes:
            continue
        partes = _analisar_seletor(seletor_bruto.strip())
        if partes is None:
            continue
        achadas.append(Regra(**partes, declaracoes=declaracoes))
    return tuple(achadas)


def regras_de_fonte(qss: str) -> tuple[Regra, ...]:
    """Só as regras que declaram `font-*`. É o subconjunto de onde o ponto cego desta frente sai."""
    return tuple(
        Regra(
            classe=regra.classe,
            subcontrole=regra.subcontrole,
            estados=regra.estados,
            propriedades=regra.propriedades,
            declaracoes=tuple(
                (chave, valor)
                for chave, valor in regra.declaracoes
                if chave in PROPRIEDADES_DE_FONTE
            ),
        )
        for regra in regras_da_folha(qss)
        if any(chave in PROPRIEDADES_DE_FONTE for chave, _ in regra.declaracoes)
    )


def seletores_ignorados(qss: str) -> tuple[str, ...]:
    """Os seletores com declaração de fonte que `regras_de_fonte` **não** soube analisar.

    Existe para que a estreiteza desta régua seja um número publicado e não um silêncio: uma
    folha que passe a usar descendência (`QGroupBox QLabel { font-size: ... }`) aparece aqui, e o
    portão diz que mediu menos do que a folha pinta.

    **São duas estreitezas e não uma**, e a segunda foi a que passou pela sabotagem do ciclo 15:

    1. o **seletor** que a análise não entende -- vírgula, descendência, `#id`, `*`;
    2. a **declaração** que ela não interpreta -- hoje só a forma curta `font:`, e amanhã o que
       for acrescentado à gramática do `QSS` sem entrar em `PROPRIEDADES_DE_FONTE`.

    A segunda escapava porque a peneira que decidia "isto mexe na fonte" era a **mesma** tupla que
    decidia "eu sei ler isto": o que ela não sabia ler, ela também não via. Ver `mexe_na_fonte`.
    """
    perdidos: list[str] = []
    for seletor_bruto, corpo in _BLOCO.findall(qss):
        declaracoes = _declaracoes_que_mexem_na_fonte(corpo)
        if not declaracoes:
            continue
        seletor = seletor_bruto.strip()
        if _analisar_seletor(seletor) is None:
            perdidos.append(seletor)
            continue
        if any(chave not in PROPRIEDADES_DE_FONTE for chave, _ in declaracoes):
            perdidos.append(seletor)
    return tuple(perdidos)


def _declaracoes(corpo: str) -> tuple[tuple[str, str], ...]:
    achadas: list[tuple[str, str]] = []
    for pedaco in corpo.split(";"):
        if ":" not in pedaco:
            continue
        chave, _, valor = pedaco.partition(":")
        achadas.append((chave.strip().lower(), valor.strip()))
    return tuple(achadas)


def mexe_na_fonte(chave: str) -> bool:
    """Esta declaração muda o desenho do texto? **Mais larga que `PROPRIEDADES_DE_FONTE`.**

    É a peneira que precisava ser a mais larga das duas: ver que uma regra mexe na fonte é o que
    permite dizer *"e eu não sei ler esta"*. Enquanto as duas eram a mesma tupla,
    `font: bold 20pt "Segoe UI"` era invisível para as duas ao mesmo tempo.
    """
    limpa = chave.strip().lower()
    return limpa == PREFIXO_DE_FONTE or limpa.startswith(f"{PREFIXO_DE_FONTE}-")


def _declaracoes_que_mexem_na_fonte(corpo: str) -> tuple[tuple[str, str], ...]:
    return tuple((chave, valor) for chave, valor in _declaracoes(corpo) if mexe_na_fonte(chave))


def _declaracoes_de_fonte(corpo: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (chave, valor) for chave, valor in _declaracoes(corpo) if chave in PROPRIEDADES_DE_FONTE
    )


def _analisar_seletor(seletor: str) -> dict[str, Any] | None:
    casado = _SELETOR.match(seletor)
    if casado is None:
        return None
    propriedades = tuple(
        (chave, valor) for chave, valor in _PROPRIEDADE.findall(casado.group("propriedades") or "")
    )
    estados = tuple(
        estado for estado in (casado.group("estados") or "").split(":") if estado
    )
    return {
        "classe": casado.group("classe"),
        "subcontrole": casado.group("subcontrole") or "",
        "estados": estados,
        "propriedades": propriedades,
    }


def fonte_da_folha(
    regras: Sequence[Regra],
    *,
    classes: Sequence[str],
    subcontrole: str = "",
    estados: Sequence[str] = (),
    propriedades: Mapping[str, str] | None = None,
    base: Fonte,
) -> Fonte:
    """A fonte com que o Qt vai **pintar** este subcontrole, partindo da fonte do widget. Pura.

    `base` é o que `QWidget.font()` devolve -- o ponto de partida, porque uma regra que só diz
    `font-weight` herda o tamanho e a família do widget. O que sai daqui é o que a régua tem de
    medir; a diferença entre os dois é exatamente o tamanho do ponto cego.
    """
    resultado = base
    for regra in regras:
        if not regra.vale_para(
            classes=classes,
            subcontrole=subcontrole,
            estados=estados,
            propriedades=propriedades,
        ):
            continue
        for chave, valor in regra.declaracoes:
            resultado = _aplicar(resultado, chave, valor)
    return resultado


def _quem_pinta(tabela: Mapping[str, str], seletor: str) -> str:
    """A resposta do produto para este seletor. Levanta se ele não tiver uma.

    Levantar e não escolher um padrão é a disciplina de `tema.fonte_pintada` e de `tokens.cor`:
    um padrão silencioso aqui devolveria uma largura plausível medida na fonte errada -- que é
    exatamente como o décimo segundo instrumento cego passou por catorze ciclos.
    """
    resposta = tabela.get(seletor)
    if resposta is None:
        raise KeyError(
            f"folha_de_estilo.QUEM_PINTA nao diz quem pinta {seletor!r}. Os que ela responde: "
            f"{sorted(tabela)}."
        )
    return resposta


def fonte_que_pinta(
    regras: Sequence[Regra],
    *,
    quem_pinta: str,
    classes: Sequence[str],
    subcontrole: str = "",
    estados: Sequence[str] = (),
    propriedades: Mapping[str, str] | None = None,
    base: Fonte,
) -> Fonte:
    """A fonte que o Qt **de fato** usa neste subcontrole -- a que ganha, não a que está escrita.

    **Este é o décimo segundo instrumento cego, e ele errou o mecanismo e não a regra** (F9-C15
    §4). `fonte_da_folha` responde *"o que a folha declara"*, e a régua a chamava nos três
    subcontroles como se a folha sempre ganhasse. Ela não ganha sempre, e o crítico mediu as duas
    respostas opostas no mesmo produto -- reproduzidas por mim em
    `benchmarks/reports/ui/c16/c16_quem_pinta.py`, texto `Comentário do lance`:

    ```
      QGroupBox::title       folha 20pt / widget  9pt -> a tela desenha 109 px    ganha o WIDGET
      QHeaderView::section   folha 20pt / widget  9pt -> a tela desenha 265 px    ganha a FOLHA
    ```

    Na janela do produto isso era a régua dizendo **85 px onde a tela desenhava 34**. Hoje ela
    pergunta a quem ganha, e `quem_pinta` vem de `folha_de_estilo.QUEM_PINTA`, que é do produto:
    uma tabela só, e não uma cópia dela aqui dentro.

    `base` continua sendo `QWidget.font()`. Quando o widget ganha, ele **é** a resposta.
    """
    if quem_pinta == O_WIDGET:
        return base
    if quem_pinta != A_FOLHA:
        raise ValueError(
            f"quem_pinta={quem_pinta!r} nao e' {O_WIDGET!r} nem {A_FOLHA!r}. Quem responde e' "
            "folha_de_estilo.QUEM_PINTA, e um seletor sem resposta la' e' um seletor que a "
            "regua nao pode medir."
        )
    return fonte_da_folha(
        regras,
        classes=classes,
        subcontrole=subcontrole,
        estados=estados,
        propriedades=propriedades,
        base=base,
    )


def _aplicar(fonte: Fonte, chave: str, valor: str) -> Fonte:
    from dataclasses import replace

    if chave == "font-size":
        pontos = _em_pontos(valor)
        return fonte if pontos is None else replace(fonte, pontos=pontos)
    if chave == "font-weight":
        return replace(fonte, negrito=_e_negrito(valor, fonte.negrito))
    if chave == "font-family":
        return replace(fonte, familia=valor.strip().strip("\"'") or fonte.familia)
    if chave == "font-style":
        return replace(fonte, italico=_e_italico(valor, fonte.italico))
    return fonte


def _em_pontos(valor: str) -> float | None:
    texto = valor.strip().lower()
    casado = re.match(r"^([\d.]+)\s*(pt|px)?$", texto)
    if casado is None:
        return None
    numero = float(casado.group(1))
    return numero * PONTOS_POR_PIXEL if casado.group(2) == "px" else numero


def _e_negrito(valor: str, atual: bool) -> bool:
    texto = valor.strip().lower()
    if texto in {"bold", "bolder"}:
        return True
    if texto in {"normal", "lighter"}:
        return False
    try:
        return int(texto) >= PESO_NEGRITO
    except ValueError:
        return atual


def _e_italico(valor: str, atual: bool) -> bool:
    texto = valor.strip().lower()
    if texto in {"italic", "oblique"}:
        return True
    return False if texto == "normal" else atual


@dataclass(frozen=True)
class Caixa:
    """O que a folha come da caixa antes do texto: recheio mais borda, nos quatro lados."""

    esquerda: int = 0
    direita: int = 0
    topo: int = 0
    base: int = 0

    @property
    def horizontal(self) -> int:
        return self.esquerda + self.direita

    @property
    def vertical(self) -> int:
        return self.topo + self.base


_LADOS = ("topo", "direita", "base", "esquerda")
"""A ordem do `QSS` para `padding: a b c d` -- topo, direita, base, esquerda."""

_POR_NOME = {"top": "topo", "right": "direita", "bottom": "base", "left": "esquerda"}
"""O lado como o `QSS` o escreve -> o lado como este módulo o chama."""


def caixa_da_folha(
    regras: Sequence[Regra],
    *,
    classes: Sequence[str],
    subcontrole: str = "",
    estados: Sequence[str] = (),
    propriedades: Mapping[str, str] | None = None,
) -> Caixa:
    """O recheio e a borda que **a folha** dá a este subcontrole, em pixel. Pura.

    **Esta é a segunda metade do ponto cego, e o crítico do ciclo 13 mediu a diferença.** A régua
    que pergunta `header.sectionSize(i)` acha 80 px de espaço para o cabeçalho `Resultado`; a
    folha diz `QHeaderView::section { padding: 2px 6px }`, e então o texto tem 68. Doze pixels --
    e `Resultado` pinta 76. Perguntar a caixa ao estilo da plataforma (`PM_HeaderMargin`) devolve
    um terceiro número ainda, porque quando há folha quem manda é a folha.

    Uma régua que lê a fonte da folha e a caixa do estilo mede duas janelas diferentes. As duas
    perguntas saem do mesmo texto, e é por isso que as duas moram aqui.
    """
    recheio = dict.fromkeys(_LADOS, 0)
    borda = dict.fromkeys(_LADOS, 0)
    for regra in regras:
        if not regra.vale_para(
            classes=classes,
            subcontrole=subcontrole,
            estados=estados,
            propriedades=propriedades,
        ):
            continue
        for chave, valor in regra.declaracoes:
            _somar_caixa(recheio, borda, chave, valor)
    return Caixa(
        esquerda=recheio["esquerda"] + borda["esquerda"],
        direita=recheio["direita"] + borda["direita"],
        topo=recheio["topo"] + borda["topo"],
        base=recheio["base"] + borda["base"],
    )


def _somar_caixa(recheio: dict[str, int], borda: dict[str, int], chave: str, valor: str) -> None:
    if chave == "padding":
        recheio.update(_quatro_lados(valor))
    elif chave.startswith("padding-") and chave[8:] in _POR_NOME:
        recheio[_POR_NOME[chave[8:]]] = _pixels(valor)
    elif chave == "border":
        borda.update(dict.fromkeys(_LADOS, _largura_de_borda(valor)))
    elif chave.startswith("border-") and chave[7:] in _POR_NOME:
        borda[_POR_NOME[chave[7:]]] = _largura_de_borda(valor)
    elif chave.startswith("border-") and chave.endswith("-width") and chave[7:-6] in _POR_NOME:
        borda[_POR_NOME[chave[7:-6]]] = _pixels(valor)


UM_LADO, DOIS_LADOS, TRES_LADOS = 1, 2, 3
"""Quantas medidas a forma curta do `padding` traz: `1` vale para os quatro lados, `2` é vertical
e horizontal, `3` é topo/horizontal/base e `4` é a ordem de `_LADOS`."""


def _quatro_lados(valor: str) -> dict[str, int]:
    partes = [_pixels(pedaco) for pedaco in valor.split() if pedaco]
    if not partes:
        return dict.fromkeys(_LADOS, 0)
    if len(partes) == UM_LADO:
        return dict.fromkeys(_LADOS, partes[0])
    if len(partes) == DOIS_LADOS:
        return {"topo": partes[0], "base": partes[0], "direita": partes[1], "esquerda": partes[1]}
    if len(partes) == TRES_LADOS:
        return {"topo": partes[0], "direita": partes[1], "esquerda": partes[1], "base": partes[2]}
    return dict(zip(_LADOS, partes[:4], strict=False))


def _largura_de_borda(valor: str) -> int:
    """`border: 1px solid #aaa` -> 1; `border: none` -> 0. A largura e' a primeira medida."""
    for pedaco in valor.split():
        if pedaco.lower() in {"none", "hidden"}:
            return 0
        if re.match(r"^-?[\d.]+\s*(px|pt)?$", pedaco.strip().lower()):
            return _pixels(pedaco)
    return 0


def _pixels(valor: str) -> int:
    casado = re.match(r"^(-?[\d.]+)\s*(px|pt)?$", valor.strip().lower())
    if casado is None:
        return 0
    numero = float(casado.group(1))
    return round(numero / PONTOS_POR_PIXEL) if casado.group(2) == "pt" else round(numero)


def coberto(tinta: tuple[int, int, int, int], caixa: tuple[int, int, int, int]) -> int:
    """Quantos pixels de **altura** da tinta a caixa de outro widget cobre. Pura.

    Retângulos como `(x, y, largura, altura)`. Devolve `0` quando não se cruzam, e é a conta do
    bloqueante: o título pinta de 0 a 21 e o primeiro filho começa em 13, então 8 px de letra
    saem debaixo dele.
    """
    x1, y1, l1, a1 = tinta
    x2, y2, l2, a2 = caixa
    largura = min(x1 + l1, x2 + l2) - max(x1, x2)
    altura = min(y1 + a1, y2 + a2) - max(y1, y2)
    return altura if largura > 0 and altura > 0 else 0


def cortado(tinta_em_pixel: int, disponivel_em_pixel: int) -> int:
    """Quantos pixels de largura a tinta pede além do que a caixa tem. Pura, nunca negativa."""
    return max(0, int(tinta_em_pixel) - int(disponivel_em_pixel))


@dataclass
class Achado:
    """Um texto pintado, e o que aconteceu com a tinta dele."""

    tela: str
    onde: str
    classe: str
    subcontrole: str
    texto: str
    fonte_do_widget: Fonte
    fonte_pintada: Fonte
    tinta_larga: int = 0
    tinta_alta: int = 0
    disponivel: int = 0
    coberto: int = 0
    cortado: int = 0
    por_quem: tuple[str, ...] = ()

    @property
    def cego(self) -> bool:
        """A fonte que **pinta** difere da do widget -- é onde uma régua comum erra.

        Desde o ciclo 16 `fonte_pintada` é a fonte que ganha e não a que a folha declara, e por
        isso um subcontrole pintado pelo widget (`QGroupBox::title`) nunca é cego: ali a régua
        comum acerta, e dizer que ela erra era o erro.
        """
        return self.fonte_pintada != self.fonte_do_widget

    @property
    def defeito(self) -> bool:
        return self.coberto > 0 or self.cortado > 0

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "tela": self.tela,
            "onde": self.onde,
            "classe": self.classe,
            "subcontrole": self.subcontrole,
            "texto": self.texto,
            "fonte_do_widget": self.fonte_do_widget.como_dicionario(),
            "fonte_pintada": self.fonte_pintada.como_dicionario(),
            "tinta_larga": self.tinta_larga,
            "tinta_alta": self.tinta_alta,
            "disponivel": self.disponivel,
            "coberto": self.coberto,
            "cortado": self.cortado,
            "por_quem": list(self.por_quem),
            "cego": self.cego,
        }


@dataclass
class Medicao:
    """O que uma passada mediu, e o veredito dela."""

    arranjo: str
    tamanho: tuple[int, int]
    achados: list[Achado] = field(default_factory=list)
    ignorados: tuple[str, ...] = ()

    def como_dicionario(self) -> dict[str, Any]:
        cobertos = [a for a in self.achados if a.coberto > 0]
        cortados = [a for a in self.achados if a.cortado > 0]
        return {
            "arranjo": self.arranjo,
            "largura": self.tamanho[0],
            "altura": self.tamanho[1],
            "medidos": len(self.achados),
            "cegos": sum(1 for a in self.achados if a.cego),
            "cobertos": len(cobertos),
            "cortados": len(cortados),
            "pior_coberto": max((a.coberto for a in self.achados), default=0),
            "pior_cortado": max((a.cortado for a in self.achados), default=0),
            "seletores_ignorados": list(self.ignorados),
            "defeitos": [a.como_dicionario() for a in self.achados if a.defeito],
            "veredito": "PASSOU" if not (cobertos or cortados) else "REPROVOU",
        }


def veredito(medicoes: Iterable[Mapping[str, Any]]) -> str:
    """`PASSOU` só se toda medição passou. Uma passada omissa não vira aprovação."""
    medidas = list(medicoes)
    if not medidas:
        return "REPROVOU"
    return "PASSOU" if all(m.get("veredito") == "PASSOU" for m in medidas) else "REPROVOU"


# ------------------------------------------------------------------- daqui para baixo, Qt


def _preparar(caminho_do_tronco: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pasta_de_fontes = Path(r"C:\Windows\Fonts")
    if pasta_de_fontes.is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", str(pasta_de_fontes))
    fonte = str(caminho_do_tronco / "src")
    if fonte not in sys.path:
        sys.path.insert(0, fonte)


def _fonte_de(qfont: Any) -> Fonte:
    tamanho = float(qfont.pointSizeF())
    if tamanho <= 0:
        tamanho = float(qfont.pixelSize()) * PONTOS_POR_PIXEL
    return Fonte(str(qfont.family()), round(tamanho, 2), bool(qfont.bold()), bool(qfont.italic()))


def _qfont(fonte: Fonte, molde: Any) -> Any:
    from PyQt6.QtGui import QFont

    saida = QFont(molde)
    saida.setFamily(fonte.familia or saida.family())
    saida.setPointSizeF(fonte.pontos or saida.pointSizeF())
    saida.setBold(fonte.negrito)
    saida.setItalic(fonte.italico)
    return saida


def _classes(objeto: Any) -> tuple[str, ...]:
    return tuple(classe.__name__ for classe in type(objeto).__mro__)


def _propriedades(widget: Any) -> dict[str, str]:
    """As propriedades dinâmicas do widget, como texto -- é assim que o `QSS` as compara."""
    saida: dict[str, str] = {}
    for nome in widget.dynamicPropertyNames():
        chave = bytes(nome).decode("utf-8", "replace")
        valor = widget.property(chave)
        if isinstance(valor, bool):
            saida[chave] = "true" if valor else "false"
        elif valor is not None:
            saida[chave] = str(valor)
    return saida


def _visivel(widget: Any) -> bool:
    return bool(widget.isVisible()) and widget.width() > 0 and widget.height() > 0


def _dentro_de(widget: Any, fora: Any) -> bool:
    """O widget está debaixo de `fora`? Serve para não medir o mesmo grupo duas vezes.

    A passada da janela existe para alcançar o cromo -- fita, rodapé, barra --, e
    `janela.findChildren` traz também o conteúdo da aba em foco. Sem esta guarda, os dois grupos
    da Galeria entram na conta uma vez pela aba e outra pela janela, e o placar do portão fica
    8 onde a tela tem 6. Um portão que conta duas vezes é um portão que não confere com o olho.
    """
    if fora is None:
        return False
    pai = widget
    while pai is not None:
        if pai is fora:
            return True
        pai = pai.parentWidget()
    return False


def medir_titulos_de_grupo(
    raiz: Any, *, regras: Sequence[Regra], quem_pinta: Mapping[str, str], tela: str,
    fora: Any = None,
) -> list[Achado]:
    """Todo `QGroupBox` visível: a tinta do título contra a geometria dos filhos do grupo.

    **O primeiro filho é quem apaga a letra**, e por isso a conta é contra os filhos diretos e
    não contra o quadro: o quadro do grupo pinta fundo, o filho pinta por cima do fundo *e* do
    título. É a diferença entre "o título encosta na borda" e "o título não está mais lá".
    """
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QGroupBox, QStyle, QStyleOptionGroupBox, QWidget

    achados: list[Achado] = []
    for grupo in raiz.findChildren(QGroupBox):
        titulo = (grupo.title() or "").replace("&", "").strip()
        if not titulo or not _visivel(grupo) or _dentro_de(grupo, fora):
            continue
        pintada = fonte_que_pinta(
            regras,
            quem_pinta=_quem_pinta(quem_pinta, SELETOR_DO_TITULO),
            classes=_classes(grupo),
            subcontrole="title",
            propriedades=_propriedades(grupo),
            base=_fonte_de(grupo.font()),
        )
        metrica = QFontMetrics(_qfont(pintada, grupo.font()))
        opcao = QStyleOptionGroupBox()
        grupo.initStyleOption(opcao)
        rotulo = grupo.style().subControlRect(
            QStyle.ComplexControl.CC_GroupBox, opcao, QStyle.SubControl.SC_GroupBoxLabel, grupo
        )
        tinta = (
            rotulo.left(),
            rotulo.top(),
            metrica.horizontalAdvance(titulo),
            metrica.height(),
        )
        caixa = caixa_da_folha(
            regras,
            classes=_classes(grupo),
            subcontrole="title",
            propriedades=_propriedades(grupo),
        )
        largura_util = max(0, grupo.width() - rotulo.left() - caixa.horizontal)
        pior, culpados = 0, []
        for filho in grupo.findChildren(QWidget):
            if not _visivel(filho) or filho.parentWidget() is not grupo:
                continue
            canto = filho.mapTo(grupo, QPoint(0, 0))
            quanto = coberto(tinta, (canto.x(), canto.y(), filho.width(), filho.height()))
            if quanto > 0:
                pior = max(pior, quanto)
                culpados.append(type(filho).__name__)
        achados.append(
            Achado(
                tela=tela,
                onde=titulo,
                classe=type(grupo).__name__,
                subcontrole="title",
                texto=titulo,
                fonte_do_widget=_fonte_de(grupo.font()),
                fonte_pintada=pintada,
                tinta_larga=tinta[2],
                tinta_alta=tinta[3],
                disponivel=largura_util,
                coberto=pior,
                cortado=cortado(tinta[2], largura_util),
                por_quem=tuple(sorted(set(culpados))),
            )
        )
    return achados


def medir_cabecalhos(
    raiz: Any, *, regras: Sequence[Regra], quem_pinta: Mapping[str, str], tela: str,
    fora: Any = None,
) -> list[Achado]:
    """Toda seção visível de `QHeaderView`: a tinta do cabeçalho contra a largura da seção.

    O espaço útil é a seção menos as duas margens que o estilo reserva (`PM_HeaderMargin`) e
    menos o indicador de ordenação quando ele está desenhado -- que é a conta que o próprio
    `QHeaderView` faz antes de elidir. Medir contra a seção inteira diria que cabe o que não
    cabe por 8 px, que é a folga que o `Resultad·` do ciclo 13 usava para passar despercebido.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QHeaderView, QStyle

    achados: list[Achado] = []
    for cabecalho in raiz.findChildren(QHeaderView):
        if not _visivel(cabecalho) or _dentro_de(cabecalho, fora):
            continue
        pintada = fonte_que_pinta(
            regras,
            quem_pinta=_quem_pinta(quem_pinta, SELETOR_DO_CABECALHO),
            classes=_classes(cabecalho),
            subcontrole="section",
            propriedades=_propriedades(cabecalho),
            base=_fonte_de(cabecalho.font()),
        )
        metrica = QFontMetrics(_qfont(pintada, cabecalho.font()))
        caixa = caixa_da_folha(
            regras,
            classes=_classes(cabecalho),
            subcontrole="section",
            propriedades=_propriedades(cabecalho),
        )
        indicador = (
            cabecalho.style().pixelMetric(
                QStyle.PixelMetric.PM_HeaderMarkSize, None, cabecalho
            )
            if cabecalho.isSortIndicatorShown()
            else 0
        )
        modelo = cabecalho.model()
        if modelo is None:
            continue
        for secao in range(cabecalho.count()):
            if cabecalho.isSectionHidden(secao):
                continue
            dado = modelo.headerData(secao, cabecalho.orientation(), Qt.ItemDataRole.DisplayRole)
            texto = "" if dado is None else str(dado).strip()
            if not texto:
                continue
            tamanho = cabecalho.sectionSize(secao)
            disponivel = max(0, tamanho - caixa.horizontal - indicador)
            largura = metrica.horizontalAdvance(texto)
            achados.append(
                Achado(
                    tela=tela,
                    onde=f"{type(cabecalho.parentWidget()).__name__}[{secao}]",
                    classe=type(cabecalho).__name__,
                    subcontrole="section",
                    texto=texto,
                    fonte_do_widget=_fonte_de(cabecalho.font()),
                    fonte_pintada=pintada,
                    tinta_larga=largura,
                    tinta_alta=metrica.height(),
                    disponivel=disponivel,
                    cortado=cortado(largura, disponivel),
                )
            )
    return achados


def medir_abas(
    raiz: Any, *, regras: Sequence[Regra], quem_pinta: Mapping[str, str], tela: str,
    fora: Any = None,
) -> list[Achado]:
    """A aba **selecionada** de todo `QTabBar`, que a folha desenha em negrito.

    O Qt mede a fila de abas com a fonte não-negrito do widget, e a folha desenha a ativa com
    outra. É a terceira das quatro regras de fonte da folha, e a que mais parece inofensiva: negrito não
    muda o tamanho, muda a largura. Numa fila que já transborda, os pixels a mais da aba ativa
    são o `QToolButton: Scroll Right` que o `QTabBar` acrescenta -- e aí a fila inteira anda.
    """
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QStyle, QTabBar

    achados: list[Achado] = []
    for fila in raiz.findChildren(QTabBar):
        if not _visivel(fila) or _dentro_de(fila, fora):
            continue
        atual = fila.currentIndex()
        if atual < 0:
            continue
        pintada = fonte_que_pinta(
            regras,
            quem_pinta=_quem_pinta(quem_pinta, SELETOR_DA_ABA),
            classes=_classes(fila),
            subcontrole="tab",
            estados=("selected",),
            propriedades=_propriedades(fila),
            base=_fonte_de(fila.font()),
        )
        metrica = QFontMetrics(_qfont(pintada, fila.font()))
        caixa = caixa_da_folha(
            regras,
            classes=_classes(fila),
            subcontrole="tab",
            estados=("selected",),
            propriedades=_propriedades(fila),
        )
        texto = (fila.tabText(atual) or "").replace("&", "").strip()
        if not texto:
            continue
        quadro = fila.tabRect(atual)
        icone = fila.iconSize().width() if not fila.tabIcon(atual).isNull() else 0
        vao = 0 if caixa.horizontal else fila.style().pixelMetric(
            QStyle.PixelMetric.PM_TabBarTabHSpace, None, fila
        )
        disponivel = max(0, quadro.width() - icone - caixa.horizontal - vao)
        largura = metrica.horizontalAdvance(texto)
        achados.append(
            Achado(
                tela=tela,
                onde=f"{type(fila.parentWidget()).__name__}[{atual}]",
                classe=type(fila).__name__,
                subcontrole="tab",
                texto=texto,
                fonte_do_widget=_fonte_de(fila.font()),
                fonte_pintada=pintada,
                tinta_larga=largura,
                tinta_alta=metrica.height(),
                disponivel=disponivel,
                cortado=cortado(largura, disponivel),
            )
        )
    return achados


def medir_a_tela(
    raiz: Any, *, regras: Sequence[Regra], quem_pinta: Mapping[str, str], tela: str,
    fora: Any = None,
) -> list[Achado]:
    """As três réguas juntas sobre uma tela -- uma aba da janela ou um diálogo.

    `fora` é a subárvore a **não** medir aqui porque outra passada já a mediu. Ver `_dentro_de`.

    **A população que estas três alcançam, dita sem eufemismo** (F9-C15 §4.4): os `QGroupBox` com
    título **visíveis nesta árvore no estado em que ela está**, todo `QHeaderView` visível e a aba
    corrente de cada `QTabBar`. Não há `medir_rotulos`: `QLabel[apoio="true"]` é o quarto seletor
    que a folha pinta e **nenhuma passada o mede** -- 8 pt é o degrau mais baixo da escala, o que
    sobra em volta dele é ar, e medi-lo pediria uma quarta régua sem um defeito que a exercite.
    Está aqui escrito porque a tabela do relatório do ciclo 14 dizia que ele era medido, e não era.
    """
    return (
        medir_titulos_de_grupo(raiz, regras=regras, quem_pinta=quem_pinta, tela=tela, fora=fora)
        + medir_cabecalhos(raiz, regras=regras, quem_pinta=quem_pinta, tela=tela, fora=fora)
        + medir_abas(raiz, regras=regras, quem_pinta=quem_pinta, tela=tela, fora=fora)
    )


def medir_uma_passada(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    tamanhos: Sequence[tuple[int, int]] = ((1280, 800), (1366, 768), (1920, 1080), (3840, 2160)),
    faixa_do_titulo: int | None = None,
    faixa_de_antes: bool = False,
) -> list[dict[str, Any]]:
    """Abre a janela **uma vez**, mede as seis abas e os diálogos em cada tamanho pedido.

    `faixa_do_titulo` reaplica a folha com aquela reserva de faixa **sem tocar um byte do
    produto**. É a prova de vida desta régua: com `4` -- o `espaco.linha()` da compacta, que era
    o valor de antes do conserto -- ela tem de voltar a acusar os seis títulos cobertos; com o
    valor do produto, `0`. Uma régua que não sabe reprovar não sabe aprovar.

    Quatro tamanhos numa passada, e não quatro processos: a pele e a densidade é que precisam de
    processo próprio (`ui/pele` resolve na importação), e redimensionar a mesma janela é o que a
    captura já faz.
    """
    _preparar(caminho_do_tronco)
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit import teclado
    from caissa.ui.audit.capture import estado_de_medicao, impor_a_fonte_do_produto

    aplicacao = QApplication.instance() or QApplication(sys.argv[:1])
    impor_a_fonte_do_produto(aplicacao)
    from chess_diagram_ocr.qt import tema
    from chess_diagram_ocr.qt.janela import JanelaPrincipal
    from chess_diagram_ocr.ui import espaco

    with tempfile.TemporaryDirectory() as temporaria:
        janela = JanelaPrincipal(caminho_do_estado=estado_de_medicao(Path(temporaria)))
    janela.show()
    if pdf is not None and Path(pdf).exists():
        janela.abrir_pdf(Path(pdf))
    for _ in range(8):
        aplicacao.processEvents()

    # **A folha lida é a que o produto aplicou**, e não uma que esta régua monte: é a janela quem
    # decide pele e densidade na construção, e uma folha remontada aqui mediria outra coisa.
    base, densidade = espaco.vigente()
    if faixa_de_antes:
        # A reserva **exata** de antes do ciclo 14: `margin-top: espaco.linha()px`, que é 4 px na
        # compacta e 6 px na confortável. É esta a linha que a régua tem de voltar a acusar.
        faixa_do_titulo = espaco.linha()
    if faixa_do_titulo is not None:
        from chess_diagram_ocr.ui import folha_de_estilo as folha_pura

        escuro = tema.cromo_escuro_em_vigor()
        aplicacao.setStyleSheet(
            folha_pura.folha_de_estilo(
                cromo_escuro=escuro,
                base=base,
                densidade=densidade,
                marcas=tema.gravar_marcas(cromo_escuro=escuro, base=base, densidade=densidade),
                altura_do_titulo=faixa_do_titulo,
            )
        )
        # **Reaplicar a folha desfaz a varredura da escala, e sem esta linha a prova de vida
        # media outra tela** (F9-C16, §8 item 11). O Qt despole e repole a janela inteira, e
        # toda `QWidget.font()` volta ao corpo de 9 pt -- inclusive a dos títulos de grupo, que
        # é justamente quem os pinta (`folha_de_estilo.QUEM_PINTA`). O estado que se quer
        # reproduzir é *"a fonte do produto dentro da faixa de antes"*, e não *"outra fonte
        # dentro da faixa de antes"*: sem a reaplicação a régua acusa 36 títulos cobertos onde a
        # tela do ciclo 13 tinha 108, porque ela mede 16 px de tinta onde havia 21.
        from chess_diagram_ocr.qt import escala

        escala.aplicar_escala(janela)
        for _ in range(4):
            aplicacao.processEvents()

    regras = regras_da_folha(aplicacao.styleSheet())
    ignorados = seletores_ignorados(aplicacao.styleSheet())
    # **A tabela de quem pinta é do produto, e é lida e não copiada.** Uma cópia aqui seria a
    # segunda tabela que o §4 da crítica do ciclo 15 nomeia -- e o dia em que a folha mudasse de
    # ideia, a régua continuaria medindo a fonte de ontem sem dizer nada.
    from chess_diagram_ocr.ui import folha_de_estilo as folha_do_produto

    quem_pinta = dict(folha_do_produto.QUEM_PINTA)
    arranjo = f"{os.environ.get('CVOFF_SKIN', '?')}/{densidade}"

    saida: list[dict[str, Any]] = []
    for largura, altura in tamanhos:
        janela.resize(largura, altura)
        for _ in range(8):
            aplicacao.processEvents()
        medicao = Medicao(arranjo=arranjo, tamanho=(largura, altura), ignorados=ignorados)
        for indice in range(janela.abas.count()):
            janela.abas.setCurrentIndex(indice)
            for _ in range(6):
                aplicacao.processEvents()
            nome = janela.abas.tabText(indice).split(" (")[0].replace("&", "")
            medicao.achados += medir_a_tela(
                janela.abas.widget(indice),
                regras=regras,
                quem_pinta=quem_pinta,
                tela=f"aba {nome}",
            )
        medicao.achados += medir_a_tela(
            janela,
            regras=regras,
            quem_pinta=quem_pinta,
            tela="janela",
            fora=janela.abas.currentWidget(),
        )
        if (largura, altura) == tuple(tamanhos[0]):
            # Os diálogos abrem no tamanho **deles**, e não no da janela: medi-los quatro vezes
            # daria quatro cópias do mesmo número e faria o placar parecer mais largo do que é.
            medicao.achados += _medir_os_dialogos(
                janela, regras=regras, quem_pinta=quem_pinta
            )
        saida.append(medicao.como_dicionario())

    teclado._descartar(janela, aplicacao)
    return saida


def _medir_os_dialogos(
    janela: Any, *, regras: Sequence[Regra], quem_pinta: Mapping[str, str]
) -> list[Achado]:
    """Os diálogos do produto, montados pela mesma receita do portão de teclado.

    Reusa `teclado.RECEITAS_DE_DIALOGO` de propósito: duas listas de como abrir treze janelas
    seriam duas listas para esquecer, e foi uma lista esquecida que reprovou o ciclo 11.
    """
    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QApplication

    from caissa.ui.audit import teclado

    aplicacao = QApplication.instance()
    do_produto = set(teclado.dialogos_registrados())
    faltando = sorted(do_produto - set(teclado.RECEITAS))
    if faltando:
        raise RuntimeError(
            "a lista de dialogos do arnes divergiu da do produto (qt.dialogos_do_produto): "
            f"sem receita no arnes = {faltando}."
        )
    sala = teclado._sala_de_dialogos(janela)
    achados: list[Achado] = []
    for classe in sorted(teclado.RECEITAS):
        try:
            telas = teclado.RECEITAS[classe](sala)
        except Exception as exc:  # noqa: BLE001 - um diálogo que não abre é defeito, não silêncio
            print(f"  {classe}: NAO ABRIU ({exc})", file=sys.stderr)
            continue
        for rotulo, dialogo in telas:
            dialogo.show()
            for _ in range(4):
                aplicacao.processEvents()
            achados += medir_a_tela(
                dialogo, regras=regras, quem_pinta=quem_pinta, tela=f"diálogo {rotulo}"
            )
            dialogo.close()
            dialogo.setParent(None)
            dialogo.deleteLater()
        aplicacao.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        aplicacao.processEvents()
    return achados


def auditar_os_arranjos(
    *,
    caminho_do_tronco: Path = TRONCO,
    pdf: Path | None = None,
    saida: Path,
    faixa_do_titulo: int | None = None,
    faixa_de_antes: bool = False,
) -> dict[str, Any]:
    """O portão inteiro: um processo por arranjo (pele × densidade), os quatro tamanhos em cada.

    Um processo por pele pela mesma razão escrita em `teclado.auditar_as_peles`: a pele resolve
    na importação, e duas janelas no mesmo processo abortavam o interpretador.
    """
    _preparar(caminho_do_tronco)
    from chess_diagram_ocr.ui import pele

    saida.mkdir(parents=True, exist_ok=True)
    por_arranjo: dict[str, Any] = {}
    for registro in pele.PELES:
        for densidade in pele.DENSIDADES:
            arranjo = f"{registro.nome}/{densidade}"
            carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            alvo = saida / f"texto_pintado_{registro.nome}_{densidade}_{carimbo}.json"
            ambiente = dict(os.environ)
            ambiente["CVOFF_SKIN"] = registro.nome
            ambiente["CVOFF_DENSITY"] = densidade
            argumentos = [
                sys.executable,
                "-m",
                "caissa.ui.audit.texto_pintado",
                "--uma-passada",
                "--tronco",
                str(caminho_do_tronco),
                "--json",
                str(alvo),
            ]
            if pdf is not None:
                argumentos += ["--pdf", str(pdf)]
            if faixa_do_titulo is not None:
                argumentos += ["--faixa-do-titulo", str(faixa_do_titulo)]
            if faixa_de_antes:
                argumentos += ["--faixa-de-antes"]
            subprocess.run(argumentos, env=ambiente, check=False)  # noqa: S603 - argv nosso
            if not alvo.exists():
                raise RuntimeError(
                    f"o arranjo {arranjo!r} nao produziu relatorio: o subprocesso morreu antes "
                    f"de escrever {alvo}."
                )
            por_arranjo[arranjo] = json.loads(alvo.read_text(encoding="utf-8"))

    todas = [medida for medidas in por_arranjo.values() for medida in medidas]
    return {
        "portao": (
            "Texto PINTADO: a regua le a fonte que DE FATO pinta cada subcontrole "
            "(folha_de_estilo.QUEM_PINTA) -- nem sempre a da folha, nem sempre a do widget. "
            "0 tinta coberta e 0 tinta cortada."
        ),
        # **A frase diz a populacao que ele alcanca, e o que fica fora** (F9-C15 §8 item 10). O
        # relatorio do ciclo 14 publicava "6 de 6 titulos" como se fosse o produto: e' a janela
        # **recem-aberta**, e ha um setimo QGroupBox -- `painel_de_estudo.py:404`,
        # `Motor (<binario>)`, o unico titulo de largura variavel do produto -- que so' existe
        # com um motor UCI instalado e que nenhuma passada visita.
        "populacao": (
            "os QGroupBox com titulo VISIVEIS na janela recem-aberta (um PDF, nenhum PGN, "
            "nenhum filtro digitado, motor conforme a maquina), todo QHeaderView visivel e a aba "
            "corrente de cada QTabBar, nas seis abas mais os treze dialogos. FORA: a setima "
            "QGroupBox 'Motor (<binario>)', que so' existe com motor instalado; e "
            "QLabel[apoio=true], o quarto seletor que a folha pinta, para o qual nao ha regua "
            "(8 pt e' o degrau mais baixo da escala e o que sobra em volta dele e' ar)."
        ),
        "quando": datetime.now(UTC).isoformat(timespec="seconds"),
        "faixa_do_titulo_forcada": "espaco.linha()" if faixa_de_antes else faixa_do_titulo,
        "arranjos": por_arranjo,
        "medidos": sum(m["medidos"] for m in todas),
        "cegos": sum(m["cegos"] for m in todas),
        "cobertos": sum(m["cobertos"] for m in todas),
        "cortados": sum(m["cortados"] for m in todas),
        "veredito": veredito(todas),
    }


def tabela(relatorio: Mapping[str, Any]) -> str:
    """Uma linha por arranjo e tamanho. O placar não fica sem dizer de quem é."""
    linhas = [str(relatorio["portao"]), ""]
    linhas.append(
        f"  {'arranjo':<20} {'tamanho':>10} {'medidos':>8} {'cegos':>6} "
        f"{'cobertos':>9} {'cortados':>9}  veredito"
    )
    for arranjo, medidas in relatorio["arranjos"].items():
        for medida in medidas:
            linhas.append(
                f"  {arranjo:<20} {medida['largura']}x{medida['altura']:<5} "
                f"{medida['medidos']:>8} {medida['cegos']:>6} "
                f"{medida['cobertos']:>9} {medida['cortados']:>9}  {medida['veredito']}"
            )
    defeitos = [
        (arranjo, medida, defeito)
        for arranjo, medidas in relatorio["arranjos"].items()
        for medida in medidas
        for defeito in medida["defeitos"]
    ]
    if defeitos:
        linhas.append("")
        linhas.append("  DEFEITOS")
        for arranjo, medida, defeito in defeitos:
            qual = "COBERTO" if defeito["coberto"] else "CORTADO"
            quanto = defeito["coberto"] or defeito["cortado"]
            quem = ", ".join(defeito["por_quem"]) or f"{defeito['disponivel']}px disponiveis"
            linhas.append(
                f"    {arranjo:<18} {medida['largura']:>5}  {defeito['tela'][:26]:<26} "
                f"{defeito['texto'][:26]:<26} {qual} {quanto}px  ({quem})"
            )
    ignorados = sorted(
        {
            seletor
            for medidas in relatorio["arranjos"].values()
            for medida in medidas
            for seletor in medida["seletores_ignorados"]
        }
    )
    linhas.append("")
    linhas.append(f"  seletores de fonte que a regua NAO analisou: {len(ignorados)} {ignorados}")
    linhas.append(
        f"  medidos {relatorio['medidos']} | cegos (a fonte que PINTA != a do widget) "
        f"{relatorio['cegos']} | "
        f"cobertos {relatorio['cobertos']} | cortados {relatorio['cortados']}"
    )
    linhas.append(f"  Veredito: {relatorio['veredito']}")
    if relatorio.get("populacao"):
        linhas.append(f"  Populacao medida: {relatorio['populacao']}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Portao do texto pintado: a fonte da folha, e nao a do widget."
    )
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--tronco", type=Path, default=TRONCO)
    parser.add_argument(
        "--faixa-do-titulo",
        type=int,
        default=None,
        help=(
            "reaplica a folha com esta reserva de faixa do titulo, em pixel, sem tocar o "
            "produto. E' a prova de vida: --faixa-do-titulo 4 devolve o defeito do ciclo 13."
        ),
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        # Sem padrão, pelo mesmo motivo de `quadros.py` (item 16 do ciclo 11): um padrão que
        # escreve na pasta do construtor é uma armadilha para quem roda o portão de fora.
        help="onde gravar o relatorio. Obrigatorio, exceto com --uma-passada --json.",
    )
    parser.add_argument(
        "--faixa-de-antes",
        action="store_true",
        help=(
            "reaplica a folha com a reserva de antes do ciclo 14 -- `espaco.linha()`, 4 px na "
            "compacta e 6 px na confortavel. E' a prova de vida desta regua."
        ),
    )
    parser.add_argument("--uma-passada", action="store_true", help="uso interno: um arranjo so.")
    parser.add_argument("--json", type=Path, default=None, help="uso interno: destino da passada.")
    args = parser.parse_args(argv)

    if args.uma_passada:
        if args.json is None:
            parser.error("--uma-passada exige --json.")
        medidas = medir_uma_passada(
            caminho_do_tronco=args.tronco,
            pdf=args.pdf,
            faixa_do_titulo=args.faixa_do_titulo,
            faixa_de_antes=args.faixa_de_antes,
        )
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(medidas, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.saida is None:
        parser.error("--saida e' obrigatorio: este portao nao escolhe pasta por voce.")
    relatorio = auditar_os_arranjos(
        caminho_do_tronco=args.tronco,
        pdf=args.pdf,
        saida=args.saida,
        faixa_do_titulo=args.faixa_do_titulo,
        faixa_de_antes=args.faixa_de_antes,
    )
    carimbo = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    alvo = args.saida / f"texto_pintado_{carimbo}.json"
    alvo.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(tabela(relatorio))
    print(f"\nRelatorio: {alvo}")
    return 0 if relatorio["veredito"] == "PASSOU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
