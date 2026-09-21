"""O estado de cada página do livro, para o trilho de miniaturas (OCR_UI_ROADMAP passo 17).

**Regra, sem toolkit.** O trilho da janela (``qt/trilho.py`` do tronco) desenha uma miniatura por
página com três marcas -- *diagramas*, *texto*, *revisado* -- e leva a pessoa à primeira página
duvidosa. Quais páginas têm o quê, qual é a primeira duvidosa e o que o resumo diz vem daqui, a
partir do :class:`~caissa.ingest.pdf.importer.ImportReport` que a importação devolveu (inteiro
ou parcial, R3.5) e das :class:`~caissa.ocr.review.ReviewDecisions` que o revisor já gravou. É a
mesma fronteira de todo ``ui/`` desta frente (R3.2): a decisão é afirmável sem janela, e o widget
só a pinta.

**"Duvidosa" tem uma definição, e ela é a do fluxo principal (U6):** uma página é duvidosa
quando tem trabalho para a pessoa -- uma região de OCR mandada a revisão ou abstida **que o
revisor ainda não decidiu**, um diagrama localizado que não foi lido, ou (OCR_UI ciclo 2, passo
C8) um diagrama lido **com hesitação** -- uma casa abaixo de 0,90 de confiança, o âmbar da
janela -- **que ninguém corrigiu ainda**. Uma página só de texto limpo não é duvidosa; uma
página com 3 diagramas lidos com folga e 0 regiões em revisão não é duvidosa. A primeira
duvidosa é a primeira **em ordem de página**, não a de maior risco: o trilho é um mapa do
livro, e a fila por risco continua sendo da aba «Revisão de texto» (passo 14).

**E o trilho aprende com o que a pessoa corrige (C8):** a decisão gravada na janela
(:mod:`caissa.ocr.diagram_decisions`) tira o diagrama da conta de hesitantes, e a decisão de
texto gravada tira a região da conta de pendentes -- :func:`estados` é reavaliada a cada
gravação, sobre o mesmo relatório, com as decisões relidas do disco.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "EstadoDaPagina",
    "anterior_duvidosa",
    "estados",
    "hesitantes_por_pagina",
    "primeira_duvidosa",
    "progresso",
    "proxima_duvidosa",
    "resumo_pt",
]

#: A square read below this confidence makes its diagram hesitant -- the
#: same floor :meth:`caissa.core.model.Diagram.doubtful_squares` uses.
LIMIAR_DE_HESITACAO = 0.9


@dataclass(frozen=True, slots=True)
class EstadoDaPagina:
    """O que o trilho sabe de uma página.

    Attributes:
        pagina: Índice em base 0.
        montada: A importação chegou a montá-la (``False`` nas páginas que um cancelamento
            deixou fora -- elas existem no PDF, não no documento).
        fonte: ``PageReport.source`` (``text-layer``, ``ocr``, ``scan``…); vazio se não montada.
        diagramas: Diagramas localizados na página.
        diagramas_lidos: Dos localizados, quantos saíram com posição.
        texto: A página tem texto no documento (camada ou OCR).
        duvidosos: Regiões de OCR em revisão/abstidas ainda sem decisão, mais os diagramas não
            lidos, mais os lidos com hesitação e ainda não corrigidos. Zero é "nada a fazer aqui".
        hesitantes: Dos lidos, quantos têm casa abaixo de :data:`LIMIAR_DE_HESITACAO` e nenhuma
            correção gravada (passo C8).
        revisada: A página **tinha** regiões em revisão e todas estão decididas.
    """

    pagina: int
    montada: bool
    fonte: str = ""
    diagramas: int = 0
    diagramas_lidos: int = 0
    texto: bool = False
    duvidosos: int = 0
    revisada: bool = False
    hesitantes: int = 0

    @property
    def duvidosa(self) -> bool:
        return self.duvidosos > 0


def _pendentes_por_pagina(report: Any, decisions: Any | None) -> dict[int, tuple[int, int]]:
    """``{página: (regiões em revisão/abstidas, quantas delas já decididas)}``."""
    contagem: dict[int, tuple[int, int]] = {}
    for item in getattr(report, "review_items", ()) or ():
        pagina = int(item.page_index)
        total, decididas = contagem.get(pagina, (0, 0))
        decidida = decisions is not None and decisions.match(pagina, item.rect) is not None
        contagem[pagina] = (total + 1, decididas + (1 if decidida else 0))
    return contagem


def hesitantes_por_pagina(
    document: Any, diagram_decisions: Any | None = None, *,
    threshold: float = LIMIAR_DE_HESITACAO,
) -> dict[int, int]:
    """``{página: diagramas lidos com hesitação e sem correção gravada}`` (passo C8).

    Lê os :class:`~caissa.core.model.Diagram` do documento importado: um diagrama hesita quando
    tem casa abaixo de ``threshold`` (:meth:`RecognitionResult.doubtful_squares`); deixa de contar quando
    a pessoa o verificou (``provenance.verified_by_human``) ou quando há uma decisão gravada
    para a caixa dele (``diagram_decisions.match``, IoU ≥ 0,5 sobre o retângulo em pontos).
    """
    contagem: dict[int, int] = {}
    for block in getattr(document, "body", ()) or ():
        if type(block).__name__ != "Diagram":
            continue
        provenance = getattr(block, "provenance", None)
        pagina = getattr(provenance, "page_index", None)
        if pagina is None:
            continue
        recognition = getattr(block, "recognition", None)
        if recognition is None or not getattr(recognition, "fen", ""):
            continue   # not read: already counted as "não lido"
        if getattr(provenance, "verified_by_human", False):
            continue
        if not recognition.doubtful_squares(threshold):
            continue
        rect = getattr(provenance, "rect", None)
        if diagram_decisions is not None and rect is not None:
            box = (float(rect.x), float(rect.y), float(rect.x + rect.width),
                   float(rect.y + rect.height))
            if diagram_decisions.match(int(pagina), box) is not None:
                continue
        contagem[int(pagina)] = contagem.get(int(pagina), 0) + 1
    return contagem


def estados(
    report: Any,
    *,
    decisions: Any | None = None,
    page_count: int | None = None,
    document: Any | None = None,
    diagram_decisions: Any | None = None,
) -> list[EstadoDaPagina]:
    """Um estado por página do livro, em ordem de página.

    ``page_count`` diz quantas páginas o PDF tem; sem ele, o trilho vai até a última que a
    importação planejou (``report.pages_planned``) ou montou. As páginas planejadas e não
    montadas -- o que um cancelamento deixou de fora -- aparecem com ``montada=False``, para o
    trilho desenhá-las como "ainda não lida" e não como vazias.

    ``document`` (o :class:`~caissa.core.model.Document` importado) e ``diagram_decisions``
    (:class:`~caissa.ocr.diagram_decisions.DiagramDecisions`) ligam a conta de hesitantes
    (passo C8); sem o documento a conta é a de antes.
    """
    por_pagina = {int(p.index): p for p in getattr(report, "pages", ()) or ()}
    pendentes = _pendentes_por_pagina(report, decisions)
    hesitantes = hesitantes_por_pagina(document, diagram_decisions) if document is not None else {}
    ultima = max(
        [page_count or 0, int(getattr(report, "pages_planned", 0) or 0)]
        + [indice + 1 for indice in por_pagina]
    )
    resultado: list[EstadoDaPagina] = []
    for pagina in range(ultima):
        relatorio = por_pagina.get(pagina)
        if relatorio is None:
            resultado.append(EstadoDaPagina(pagina=pagina, montada=False))
            continue
        total, decididas = pendentes.get(pagina, (0, 0))
        nao_lidos = max(0, int(relatorio.diagrams) - int(relatorio.diagrams_read))
        hesitam = int(hesitantes.get(pagina, 0))
        resultado.append(
            EstadoDaPagina(
                pagina=pagina,
                montada=True,
                fonte=str(relatorio.source),
                diagramas=int(relatorio.diagrams),
                diagramas_lidos=int(relatorio.diagrams_read),
                texto=int(getattr(relatorio, "lines", 0) or 0) > 0
                or str(relatorio.source).startswith("text"),
                duvidosos=(total - decididas) + nao_lidos + hesitam,
                revisada=total > 0 and decididas == total,
                hesitantes=hesitam,
            )
        )
    return resultado


def primeira_duvidosa(paginas: Iterable[EstadoDaPagina]) -> int | None:
    """A primeira página, em ordem, com trabalho para a pessoa. ``None`` quando não há."""
    for estado in paginas:
        if estado.duvidosa:
            return estado.pagina
    return None


def proxima_duvidosa(paginas: Iterable[EstadoDaPagina], atual: int) -> int | None:
    """A primeira duvidosa **depois** de ``atual`` (passo C8); ``None`` quando não há mais."""
    for estado in paginas:
        if estado.pagina > atual and estado.duvidosa:
            return estado.pagina
    return None


def anterior_duvidosa(paginas: Iterable[EstadoDaPagina], atual: int) -> int | None:
    """A última duvidosa **antes** de ``atual``; ``None`` quando não há."""
    alvo = None
    for estado in paginas:
        if estado.pagina >= atual:
            break
        if estado.duvidosa:
            alvo = estado.pagina
    return alvo


def progresso(report: Any) -> tuple[int, int, bool]:
    """``(montadas, planejadas, cancelada)`` -- o que a barra e o resumo dizem da importação."""
    montadas = len(getattr(report, "pages", ()) or ())
    planejadas = int(getattr(report, "pages_planned", 0) or 0) or montadas
    return montadas, planejadas, bool(getattr(report, "canceled", False))


def resumo_pt(paginas: Sequence[EstadoDaPagina], report: Any | None = None) -> str:
    """A frase do trilho: quantas páginas, quantos diagramas, quantas duvidosas -- e se parou."""
    montadas = [p for p in paginas if p.montada]
    diagramas = sum(p.diagramas for p in montadas)
    lidos = sum(p.diagramas_lidos for p in montadas)
    duvidosas = sum(1 for p in montadas if p.duvidosa)
    partes = [f"{len(montadas)} de {len(paginas)} página(s) lida(s)"]
    if diagramas:
        partes.append(f"{lidos} de {diagramas} diagrama(s) com posição")
    partes.append(f"{duvidosas} página(s) para rever" if duvidosas else "nada para rever")
    if report is not None and bool(getattr(report, "canceled", False)):
        partes.append("importação cancelada: o que está lido é aproveitável")
    return " · ".join(partes)
