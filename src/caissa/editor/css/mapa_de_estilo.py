"""O mapa de estilo: o subconjunto fechado do CSS do livro que o DOCX recebe (spec S3b).

As folhas do projeto vão ao EPUB e ao HTML byte a byte; o DOCX não tem CSS, e recebe **estilos**:
um estilo de parágrafo por `p.<classe>`, um de caractere por `span.<classe>`, os títulos, a
legenda e a citação. Este módulo calcula esses estilos a partir das folhas, **só** dentro do
subconjunto que o contrato define (`docs/MARKUP_CAISSA.md` §9), e **avisa** — regra a regra,
propriedade a propriedade, com o arquivo e a linha — tudo o que fica de fora. Nada se perde em
silêncio (spec R2.2d).

O resultado é o das fixtures do H3 (`tests/fixtures/editor/css/`)::

    {"estilos": {"<alvo>": {"<propriedade>": "<valor calculado>"}},
     "avisos": [{"codigo": "css-fora-do-mapa", "seletor", "propriedade", "arquivo", "linha"}]}
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import tinycss2
import tinycss2.color3

__all__ = ["AVISO", "Aviso", "MapaDeEstilo", "resolver"]

AVISO = "css-fora-do-mapa"

PROPRIEDADES = frozenset({
    "font-family", "font-size", "font-weight", "font-style", "font-variant", "color",
    "background-color", "text-align", "text-indent", "margin-top", "margin-right",
    "margin-bottom", "margin-left", "margin", "line-height", "letter-spacing", "text-transform",
    "break-before", "page-break-before", "widows", "orphans",
})
"""As propriedades do mapa (o contrato, §9)."""

_CLASSE = r"[A-Za-z_-][\w-]*"
_SELETOR = re.compile(rf"^(?:(?P<elemento>p|span|h[1-6])?\.(?P<classe>{_CLASSE})"
                      rf"|(?P<so>h[1-6]|figcaption|blockquote))$")
_PESO = {"normal": "400", "bold": "700"}
_QUEBRA = {"always": "page"}
_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*?))?\s*\)")


@dataclass(frozen=True)
class Aviso:
    """Uma regra ou propriedade fora do mapa, com onde ela está."""

    seletor: str
    propriedade: str
    arquivo: str
    linha: int
    codigo: str = AVISO

    def como_dict(self) -> dict[str, Any]:
        return {"codigo": self.codigo, "seletor": self.seletor, "propriedade": self.propriedade,
                "arquivo": self.arquivo, "linha": self.linha}


@dataclass
class MapaDeEstilo:
    """Os estilos por alvo e os avisos do que ficou de fora."""

    estilos: dict[str, dict[str, str]] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return {"estilos": self.estilos, "avisos": [a.como_dict() for a in self.avisos]}


@dataclass(frozen=True)
class _Seletor:
    """Um seletor do mapa: o que ele atinge e com que especificidade."""

    elemento: str | None
    classe: str | None

    @property
    def especificidade(self) -> tuple[int, int]:
        return (1 if self.classe else 0, 1 if self.elemento else 0)

    def alvos(self) -> list[str]:
        if self.classe and not self.elemento:
            return [f"p.{self.classe}", f"span.{self.classe}"]
        if self.classe:
            return [f"{self.elemento}.{self.classe}"]
        return [str(self.elemento)]

    def casa(self, alvo: str) -> bool:
        elemento, _, classe = alvo.partition(".")
        if self.classe and self.classe != classe:
            return False
        if self.classe and not self.elemento:
            return True
        if self.elemento != elemento:
            return False
        return not self.classe or self.classe == classe


@dataclass
class _Declaracao:
    seletor: _Seletor
    especificidade: tuple[int, int]
    ordem: int
    propriedades: dict[str, str]


def _texto(tokens: Iterable[Any]) -> str:
    return " ".join(tinycss2.serialize(list(tokens)).split())


def _dividir_seletores(prelude: list[Any]) -> list[str]:
    """A lista de seletores da regra, separada nas vírgulas de fora de parênteses."""
    partes: list[list[Any]] = [[]]
    for token in prelude:
        if token.type == "literal" and token.value == ",":
            partes.append([])
        else:
            partes[-1].append(token)
    return [_texto(p) for p in partes if _texto(p)]


def _cor(valor: str) -> str | None:
    cor = tinycss2.color3.parse_color(valor)
    if cor is None or not hasattr(cor, "alpha") or cor.alpha != 1:
        return None
    return "#" + "".join(f"{round(canal * 255):02x}" for canal in (cor.red, cor.green, cor.blue))


def _margem(valores: list[str]) -> dict[str, str] | None:
    if not 1 <= len(valores) <= 4:  # noqa: PLR2004 - o atalho tem de um a quatro valores
        return None
    topo, direita, baixo, esquerda = {
        1: lambda v: (v[0], v[0], v[0], v[0]),
        2: lambda v: (v[0], v[1], v[0], v[1]),
        3: lambda v: (v[0], v[1], v[2], v[1]),
        4: lambda v: tuple(v),
    }[len(valores)](valores)
    return {"margin-top": topo, "margin-right": direita, "margin-bottom": baixo,
            "margin-left": esquerda}


def _calcular(nome: str, valor: str) -> dict[str, str] | None:  # noqa: PLR0911 - uma por regra
    """O valor calculado da declaração (o contrato, §9), ou ``None`` quando ele fica fora."""
    if nome == "font-weight":
        if valor in ("bolder", "lighter"):
            return None
        return {nome: _PESO.get(valor, valor)}
    if nome == "font-variant":
        return {nome: valor} if valor in ("small-caps", "normal") else None
    if nome in ("color", "background-color"):
        cor = _cor(valor)
        return {nome: cor} if cor else None
    if nome == "margin":
        return _margem(valor.split())
    if nome == "page-break-before":
        return {"break-before": _QUEBRA.get(valor, valor)}
    return {nome: valor}


def _resolver_var(valor: str, variaveis: dict[str, str]) -> str | None:
    """`var(--x)` pelas variáveis de `:root`; a reserva quando falta; ``None`` sem as duas."""
    faltou = False

    def trocar(casado: re.Match[str]) -> str:
        nonlocal faltou
        nome, reserva = casado.group(1), casado.group(2)
        if nome in variaveis:
            return variaveis[nome]
        if reserva is not None and reserva.strip():
            return reserva.strip()
        faltou = True
        return ""

    resolvido = _VAR.sub(trocar, valor)
    return None if faltou else resolvido


class _Leitor:
    """Lê as folhas na ordem da espinha, junta o que o mapa leva e avisa o resto."""

    def __init__(self) -> None:
        self.variaveis: dict[str, str] = {}
        self.declaracoes: list[_Declaracao] = []
        self.avisos: list[Aviso] = []
        self._ordem = 0

    def ler(self, arquivo: str, texto: str) -> None:
        regras = tinycss2.parse_stylesheet(texto, skip_comments=True, skip_whitespace=True)
        # As variáveis de `:root` primeiro: o `var()` vale para a folha inteira.
        for regra in regras:
            if regra.type == "qualified-rule" and _dividir_seletores(regra.prelude) == [":root"]:
                for decl in self._declaracoes(regra):
                    if decl.name.startswith("--"):
                        self.variaveis[decl.name] = _texto(decl.value)
        for regra in regras:
            if regra.type == "at-rule":
                self.avisos.append(Aviso(f"@{regra.lower_at_keyword}", "", arquivo,
                                         regra.source_line))
            elif regra.type == "qualified-rule":
                self._regra(arquivo, regra)
            elif regra.type == "error":
                self.avisos.append(Aviso("", "", arquivo, regra.source_line))

    @staticmethod
    def _declaracoes(regra: Any) -> list[Any]:
        return [d for d in tinycss2.parse_declaration_list(
            regra.content, skip_comments=True, skip_whitespace=True) if d.type == "declaration"]

    def _regra(self, arquivo: str, regra: Any) -> None:
        textos = _dividir_seletores(regra.prelude)
        seletores: list[tuple[str, _Seletor]] = []
        for texto in textos:
            if texto == ":root":
                continue
            casado = _SELETOR.match(texto.replace(" ", ""))
            if casado is None:
                self.avisos.append(Aviso(texto, "", arquivo, regra.source_line))
                continue
            seletores.append((texto, _Seletor(casado["elemento"] or casado["so"],
                                              casado["classe"])))
        if not seletores:
            return
        rotulo = ", ".join(t for t, _ in seletores)
        propriedades: dict[str, str] = {}
        for decl in self._declaracoes(regra):
            nome = decl.lower_name
            if nome.startswith("--"):
                continue
            valor = _texto(decl.value)
            calculado = None
            if nome in PROPRIEDADES and not decl.important:
                resolvido = _resolver_var(valor, self.variaveis)
                calculado = _calcular(nome, resolvido) if resolvido is not None else None
            if calculado is None:
                self.avisos.append(Aviso(rotulo, nome, arquivo, decl.source_line))
                continue
            propriedades.update(calculado)
        if not propriedades:
            return
        for _, seletor in seletores:
            self._ordem += 1
            self.declaracoes.append(_Declaracao(seletor, seletor.especificidade, self._ordem,
                                                dict(propriedades)))

    def mapa(self) -> MapaDeEstilo:
        alvos = sorted({a for d in self.declaracoes for a in d.seletor.alvos()})
        estilos: dict[str, dict[str, str]] = {}
        for alvo in alvos:
            casadas = sorted((d for d in self.declaracoes if d.seletor.casa(alvo)),
                             key=lambda d: (d.especificidade, d.ordem))
            estilo: dict[str, str] = {}
            for declaracao in casadas:
                estilo.update(declaracao.propriedades)
            if estilo:
                estilos[alvo] = estilo
        return MapaDeEstilo(estilos, self.avisos)


def resolver(folhas: Sequence[tuple[str, str]]) -> MapaDeEstilo:
    """O mapa de estilo das folhas do livro, na ordem da espinha: ``[(arquivo, texto), …]``."""
    leitor = _Leitor()
    for arquivo, texto in folhas:
        leitor.ler(arquivo, texto)
    return leitor.mapa()
