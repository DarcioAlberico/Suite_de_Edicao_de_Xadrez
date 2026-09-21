"""O estado por página do trilho (OCR_UI passo 17), afirmado sem janela."""

from __future__ import annotations

from dataclasses import dataclass, field

from caissa.ui import trilho


@dataclass
class _Pagina:
    index: int
    source: str = "text-layer"
    lines: int = 12
    diagrams: int = 0
    diagrams_read: int = 0


@dataclass
class _Item:
    page_index: int
    rect: tuple[float, float, float, float]


@dataclass
class _Relatorio:
    pages: list[_Pagina] = field(default_factory=list)
    review_items: list[_Item] = field(default_factory=list)
    pages_planned: int = 0
    canceled: bool = False


class _Decisoes:
    """`ReviewDecisions.match` de mentira: decidida quem estiver na lista."""

    def __init__(self, decididas: set[tuple[int, tuple[float, float, float, float]]]) -> None:
        self._decididas = decididas

    def match(self, page_index: int, rect: tuple[float, float, float, float]) -> object | None:
        return object() if (page_index, rect) in self._decididas else None


def _relatorio() -> _Relatorio:
    return _Relatorio(
        pages=[
            _Pagina(0, lines=20),
            _Pagina(1, diagrams=2, diagrams_read=2),
            _Pagina(2, diagrams=3, diagrams_read=1),
            _Pagina(3, source="ocr", lines=8),
            _Pagina(4, source="scan", lines=0),
        ],
        review_items=[_Item(3, (0, 0, 10, 10)), _Item(3, (0, 20, 10, 30)), _Item(4, (0, 0, 5, 5))],
        pages_planned=6,
    )


def test_a_pagina_duvidosa_e_a_que_tem_trabalho_para_a_pessoa() -> None:
    estados = trilho.estados(_relatorio())
    assert [e.pagina for e in estados] == [0, 1, 2, 3, 4, 5]
    assert not estados[0].duvidosa, "texto limpo não é dúvida"
    assert not estados[1].duvidosa, "dois diagramas lidos não são dúvida"
    assert estados[2].duvidosos == 2, "três diagramas, um lido: dois a ler"
    assert estados[3].duvidosos == 2, "duas regiões em revisão sem decisão"
    assert estados[4].duvidosos == 1
    assert not estados[4].texto
    assert not estados[5].montada, "planejada e não montada: um cancelamento a deixou fora"
    assert trilho.primeira_duvidosa(estados) == 2


def test_as_decisoes_do_revisor_apagam_a_duvida_e_marcam_revisada() -> None:
    relatorio = _relatorio()
    decisoes = _Decisoes({(3, (0, 0, 10, 10)), (3, (0, 20, 10, 30))})
    estados = trilho.estados(relatorio, decisions=decisoes)
    assert estados[3].duvidosos == 0
    assert estados[3].revisada
    assert not estados[4].revisada, "uma região sem decisão não é página revisada"
    assert trilho.primeira_duvidosa(estados) == 2


def test_o_trilho_vai_ate_a_ultima_pagina_do_pdf_mesmo_sem_importacao() -> None:
    estados = trilho.estados(_Relatorio(), page_count=3)
    assert len(estados) == 3
    assert all(not e.montada for e in estados)
    assert trilho.primeira_duvidosa(estados) is None


def test_o_progresso_e_o_resumo_dizem_o_parcial() -> None:
    relatorio = _relatorio()
    relatorio.canceled = True
    assert trilho.progresso(relatorio) == (5, 6, True)
    estados = trilho.estados(relatorio)
    frase = trilho.resumo_pt(estados, relatorio)
    assert "5 de 6 página(s)" in frase
    assert "3 de 5 diagrama(s)" in frase
    assert "3 página(s) para rever" in frase
    assert "cancelada" in frase


def test_sem_diagramas_o_resumo_nao_inventa_denominador() -> None:
    relatorio = _Relatorio(pages=[_Pagina(0), _Pagina(1)], pages_planned=2)
    frase = trilho.resumo_pt(trilho.estados(relatorio), relatorio)
    assert "diagrama" not in frase
    assert frase.endswith("nada para rever")


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP_C2 passo C8: hesitation counts, corrections uncount, next/previous
# --------------------------------------------------------------------------- #


def _documento(*diagramas):
    from caissa.core.model import Diagram, RecognitionResult
    from caissa.core.model.provenance import Provenance, Rect

    class _Doc:
        def __init__(self, body):
            self.body = body

    body = []
    for pagina, confiancas, humano in diagramas:
        body.append(Diagram(
            fen="4k3/8/8/8/8/8/8/4K3 w - - 0 1",
            recognition=RecognitionResult(fen="4k3/8/8/8/8/8/8/4K3 w - - 0 1",
                                          per_square_confidence=tuple(confiancas)),
            provenance=Provenance(page_index=pagina, rect=Rect(x=10, y=10, width=100, height=100),
                                  verified_by_human=humano),
        ))
    return _Doc(body)


class _DecisoesDeDiagrama:
    def __init__(self, paginas: set[int]) -> None:
        self._paginas = paginas

    def match(self, page_index: int, rect) -> object | None:
        return object() if page_index in self._paginas else None


def test_um_diagrama_lido_com_hesitacao_e_duvidoso_ate_alguem_o_corrigir() -> None:
    relatorio = _relatorio()
    firme = [0.99] * 64
    hesitante = [0.99] * 63 + [0.42]
    documento = _documento((1, firme, False), (1, hesitante, False))
    # Without the document: page 1 (2 read of 2) is not doubtful -- the old rule.
    assert not trilho.estados(relatorio)[1].duvidosa
    # With it: the hesitant diagram counts.
    estados = trilho.estados(relatorio, document=documento)
    assert estados[1].hesitantes == 1 and estados[1].duvidosos == 1
    # A decision saved for its box uncounts it (the rail learns).
    estados = trilho.estados(relatorio, document=documento,
                             diagram_decisions=_DecisoesDeDiagrama({1}))
    assert estados[1].hesitantes == 0 and not estados[1].duvidosa
    # ...and so does a diagram verified by a human.
    estados = trilho.estados(relatorio, document=_documento((1, hesitante, True)))
    assert estados[1].hesitantes == 0


def test_proxima_e_anterior_duvidosa_andam_a_partir_da_pagina_atual() -> None:
    estados = trilho.estados(_relatorio())
    duvidosas = [e.pagina for e in estados if e.duvidosa]
    assert duvidosas == [2, 3, 4]
    assert trilho.proxima_duvidosa(estados, 2) == 3
    assert trilho.proxima_duvidosa(estados, 0) == 2
    assert trilho.proxima_duvidosa(estados, 4) is None
    assert trilho.anterior_duvidosa(estados, 4) == 3
    assert trilho.anterior_duvidosa(estados, 2) is None
