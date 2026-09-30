"""As condições do CSS na página do contraste (spec S10): a mídia, o `@supports`, as camadas.

O MuPDF ignora o bloco inteiro do `@media`, do `@supports` e do `@layer` (medido no H10,
PyMuPDF 1.28.2); o leitor de EPUB os aplica. A página do contraste mede o livro como o leitor o
mostra, então as condições se avaliam aqui, para o **dispositivo de leitura** (`LEITOR`): a tela,
o esquema claro, em pé, a largura da página medida — e o que casa entra no lugar dele:

- **`@media`** — a lista de consultas (o tipo, o `not`/`only`, as características com `and`, a
  forma de intervalo do Media Queries 4); a característica que não se conhece não casa (como no
  navegador);
- **`@supports`** — a condição (`not`/`and`/`or`, a declaração, o `selector()`): a declaração de
  uma propriedade do CSS (ou personalizada) é suportada;
- **`@layer`** — a ordem das camadas (a da primeira aparição, entre as irmãs) e a chave de
  precedência da regra: a declaração sem camada vence a de camada (a normal), a camada de depois
  vence a de antes, e a regra direta de uma camada vence as das subcamadas dela; na `!important`,
  ao contrário (CSS Cascade 5, §6.4).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import tinycss2

__all__ = ["LEITOR", "Camadas", "casa_a_midia", "suportado"]

LEITOR: dict[str, Any] = {
    "tipo": "screen",
    "largura": 348.0,  # a largura da página medida (a da prévia A5 sem as margens), em px do CSS
    "altura": 13928.0,
    "esquema": "light",
    "orientacao": "portrait",
    "hover": "none",
    "pointer": "coarse",
    "movimento": "no-preference",
    "cor": 8,
}
"""O dispositivo de leitura: o que o `@media` pergunta e o leitor de EPUB responde."""
EM_PX = 16.0
_COMPARACOES: dict[str, Callable[[float, float], bool]] = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b, "=": lambda a, b: math.isclose(a, b)}
_INVERSAS = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "=": "="}


def _sem_espacos(nos: Sequence[Any]) -> list[Any]:
    return [no for no in nos if no.type not in ("whitespace", "comment")]


def _dividir(nos: Sequence[Any], separador: str = ",") -> list[list[Any]]:
    partes: list[list[Any]] = [[]]
    for no in nos:
        if no.type == "literal" and no.value == separador:
            partes.append([])
        else:
            partes[-1].append(no)
    return partes


def _px(no: Any) -> float | None:
    """Um comprimento em px do CSS (o `em`/`rem` a 16 px; o MuPDF conta o pt como o px)."""
    if no.type == "number" and no.value == 0:
        return 0.0
    if no.type != "dimension":
        return None
    unidade = no.lower_unit
    fatores = {"px": 1.0, "pt": 1.0, "em": EM_PX, "rem": EM_PX, "in": 96.0, "cm": 96 / 2.54,
               "mm": 96 / 25.4, "pc": 16.0}
    return float(no.value) * fatores[unidade] if unidade in fatores else None


def _de_tamanho(nome: str, base: str, valor: Any | None) -> bool:
    """`width`, `height` (e o `min-`/`max-`) na página medida."""
    medida = LEITOR["largura" if "width" in base else "altura"]
    if valor is None:
        return bool(medida > 0)
    alvo = _px(valor)
    if alvo is None:
        return False
    if nome.startswith("min-"):
        return bool(medida >= alvo)
    if nome.startswith("max-"):
        return bool(medida <= alvo)
    return math.isclose(medida, alvo)


def _de_cor(nome: str, base: str, valor: Any | None) -> bool:
    """`color` (os bits por canal, e o `min-`/`max-`) e `monochrome` (0: a tela é colorida)."""
    numero = valor.value if valor is not None and valor.type == "number" else None
    if base == "monochrome":
        return numero == 0 and not nome.startswith("min-")
    if valor is None:
        return bool(LEITOR["cor"] > 0)
    if numero is None:
        return False
    comparar = {"min": LEITOR["cor"] >= numero, "max": LEITOR["cor"] <= numero}
    return bool(comparar.get(nome[:3], LEITOR["cor"] == numero))


_SIMPLES = {
    "orientation": "orientacao", "prefers-color-scheme": "esquema", "hover": "hover",
    "any-hover": "hover", "pointer": "pointer", "any-pointer": "pointer",
    "prefers-reduced-motion": "movimento"}


def _caracteristica(nome: str, valor: Any | None) -> bool:
    """Uma característica `(nome: valor)` ou `(nome)` no dispositivo de leitura."""
    base = nome[4:] if nome.startswith(("min-", "max-")) else nome
    if base in ("width", "height", "device-width", "device-height"):
        return _de_tamanho(nome, base, valor)
    if nome in _SIMPLES:
        texto = valor.lower_value if valor is not None and valor.type == "ident" else None
        return valor is None or texto == LEITOR[_SIMPLES[nome]]
    if base in ("color", "monochrome"):
        return _de_cor(nome, base, valor)
    return False  # a característica que não se conhece não casa


def _intervalo(nos: list[Any]) -> bool | None:
    """A forma de intervalo (`width >= 600px`, `400px < width <= 700px`), ou `None` se não é."""
    operadores: list[str] = []
    termos: list[Any] = []
    pendente = ""
    for no in nos:
        if no.type == "literal" and no.value in "<>=":
            pendente += no.value
            continue
        if pendente:
            operadores.append(pendente)
            pendente = ""
        termos.append(no)
    if not operadores or len(termos) != len(operadores) + 1:
        return None
    nomes = [t for t in termos if t.type == "ident"]
    if len(nomes) != 1:
        return None
    medida = LEITOR["largura" if "width" in nomes[0].lower_value else "altura"] \
        if nomes[0].lower_value in ("width", "height") else None
    if medida is None:
        return False
    resultado = True
    for esquerda, operador, direita in zip(termos, operadores, termos[1:], strict=False):
        if operador not in _COMPARACOES:
            return False
        if esquerda.type == "ident":
            alvo = _px(direita)
            resultado &= alvo is not None and _COMPARACOES[operador](medida, alvo)
        else:
            alvo = _px(esquerda)
            resultado &= alvo is not None and _COMPARACOES[_INVERSAS[operador]](medida, alvo)
    return resultado


def _parenteses(bloco: Any) -> bool:
    nos = _sem_espacos(bloco.content)
    dentro = _dividir(nos, ":")
    if len(dentro) == 2 and len(dentro[0]) == 1 and dentro[0][0].type == "ident":  # noqa: PLR2004
        valor = dentro[1][0] if len(dentro[1]) == 1 else None
        return _caracteristica(dentro[0][0].lower_value, valor) if valor is not None else False
    if len(nos) == 1 and nos[0].type == "ident":
        return _caracteristica(nos[0].lower_value, None)
    if nos and nos[0].type == "ident" and nos[0].lower_value == "not":
        return not _condicao_de_midia(nos[1:])
    intervalo = _intervalo(nos)
    if intervalo is not None:
        return intervalo
    return _condicao_de_midia(nos)


def _condicao_de_midia(nos: list[Any]) -> bool:
    """Uma condição com `and`/`or` e parênteses."""
    if not nos:
        return False
    if nos[0].type == "ident" and nos[0].lower_value == "not":
        return not _condicao_de_midia(nos[1:])
    valores: list[bool] = []
    juncao = "and"
    for no in nos:
        if no.type == "() block":
            valores.append(_parenteses(no))
        elif no.type == "ident" and no.lower_value in ("and", "or"):
            juncao = no.lower_value
        else:
            return False
    if not valores:
        return False
    return all(valores) if juncao == "and" else any(valores)


def _consulta(nos: list[Any]) -> bool:
    """Uma consulta da lista: `[not|only] tipo [and condição]` ou só a condição."""
    if not nos:
        return False
    negar = False
    if nos[0].type == "ident" and nos[0].lower_value in ("not", "only"):
        negar = nos[0].lower_value == "not"
        nos = nos[1:]
    if nos and nos[0].type == "ident" and nos[0].lower_value not in ("and", "or", "not"):
        tipo = nos[0].lower_value
        resto = nos[1:]
        casa = tipo in ("all", LEITOR["tipo"])
        if resto:
            if not (resto[0].type == "ident" and resto[0].lower_value == "and"):
                return False
            casa = casa and _condicao_de_midia(resto[1:])
    else:
        casa = _condicao_de_midia(nos)
    return casa != negar


def casa_a_midia(prelude: Sequence[Any]) -> bool:
    """A lista de consultas do `@media` (ou de um `@import`) casa com o dispositivo de leitura."""
    nos = _sem_espacos(prelude)
    if not nos:
        return True
    return any(_consulta(_sem_espacos(parte)) for parte in _dividir(nos))


def suportado(nos: Sequence[Any], propriedades: frozenset[str]) -> bool:
    """A condição do `@supports`: a declaração de uma propriedade conhecida, e o `selector()`."""
    lista = _sem_espacos(nos)
    if not lista:
        return False
    if lista[0].type == "ident" and lista[0].lower_value == "not":
        return not suportado(lista[1:], propriedades)
    valores: list[bool] = []
    juncao = "and"
    for no in lista:
        if no.type == "() block":
            dentro = _sem_espacos(no.content)
            partes = _dividir(dentro, ":")
            if len(partes) >= 2 and len(partes[0]) == 1 and partes[0][0].type == "ident":  # noqa: PLR2004
                nome = partes[0][0].value
                valores.append(nome.startswith("--") or nome.lower() in propriedades
                               or nome.lower().startswith(("-webkit-", "-moz-")))
            else:
                valores.append(suportado(dentro, propriedades))
        elif no.type == "function":
            valores.append(no.lower_name == "selector")
        elif no.type == "ident" and no.lower_value in ("and", "or"):
            juncao = no.lower_value
        else:
            return False
    return bool(valores) and (all(valores) if juncao == "and" else any(valores))


INFINITO = math.inf


@dataclass
class Camadas:
    """A ordem das camadas do documento, pela primeira aparição (o nome inteiro, entre irmãs)."""

    ordem: dict[tuple[str, ...], int] = field(default_factory=dict)
    anonimas: int = 0

    def registrar(self, caminho: tuple[str, ...]) -> tuple[float, ...]:
        """A chave de camada de `caminho` (os índices ao longo dele e o infinito das diretas)."""
        indices: list[float] = []
        for fim in range(1, len(caminho) + 1):
            parcial = caminho[:fim]
            if parcial not in self.ordem:
                irmas = sum(1 for c in self.ordem if len(c) == fim and c[:-1] == parcial[:-1])
                self.ordem[parcial] = irmas
            indices.append(self.ordem[parcial])
        return (*indices, INFINITO)

    def anonima(self) -> str:
        self.anonimas += 1
        return f"\0anônima{self.anonimas}"

    @staticmethod
    def nomes(prelude: Sequence[Any]) -> list[tuple[str, ...]]:
        """Os nomes de um `@layer a.b, c` (cada um, o caminho dos pontos)."""
        texto = tinycss2.serialize(prelude).strip()
        return [tuple(p for p in nome.strip().split(".") if p) for nome in texto.split(",")
                if nome.strip()]


SEM_CAMADA: tuple[float, ...] = (INFINITO,)
"""A chave da regra de fora de toda camada: vence as de camada (a normal)."""


def chave_de_camada(chave: tuple[float, ...], importante: bool) -> tuple[float, ...]:
    """A chave de precedência: na `!important`, a ordem das camadas se inverte."""
    return tuple(-x for x in chave) if importante else chave
