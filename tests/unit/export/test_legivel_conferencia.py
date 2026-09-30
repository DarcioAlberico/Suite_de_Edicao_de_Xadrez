"""A conferência do leitor legível (Editor HTML/CSS, passo H5): nada se perde em silêncio.

O leitor reescreve cada elemento que leu e o compara com o original; o que o IR não guarda (a
marcação num comentário da partida, o `title` na imagem do diagrama) faz o elemento inteiro ficar
bruto, preservado (spec R2.3). O que o contrato diz derivado (a imagem do diagrama, o `data-stm`,
o `data-mode`) não conta.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.core.model import Diagram, GameScore, MathInline, Paragraph, RawInline, RawPassthrough
from caissa.export.legivel import Capitulo, canon, escrever_capitulo, ler_capitulo

EDITADOS = Path(__file__).resolve().parents[2] / "fixtures" / "editor" / "editados"
CONTRATO = EDITADOS.parent / "contrato"
CABECA = ('<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
          'xmlns:epub="http://www.idpf.org/2007/ops" lang="pt-BR" xml:lang="pt-BR">'
          "<head><title>t</title></head><body>")
PE = "</body></html>"
MATE = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


def _volta(texto: str) -> str:
    escrito, _ = escrever_capitulo(ler_capitulo(texto))
    return escrito


@pytest.mark.parametrize("arquivo", sorted(EDITADOS.glob("*.xhtml")), ids=lambda p: p.stem)
def test_a_volta_fecha_nas_edicoes_a_mao(arquivo: Path) -> None:
    texto = arquivo.read_text(encoding="utf-8")
    assert canon(_volta(texto)) == canon(texto)


def test_ha_vinte_edicoes() -> None:
    assert len(list(EDITADOS.glob("*.xhtml"))) >= 20


def test_a_conferencia_guarda_como_bruto_so_o_que_o_esperado_diz() -> None:
    esperado = json.loads((EDITADOS / "esperado.json").read_text(encoding="utf-8"))["brutos"]
    for arquivo in sorted(EDITADOS.glob("*.xhtml")):
        brutos = list(ler_capitulo(arquivo.read_text(encoding="utf-8")).brutos)
        assert brutos == esperado.get(arquivo.name, {}).get("esperado", []), arquivo.name
    for fixture in sorted(CONTRATO.glob("*.xhtml")):
        if not fixture.name.startswith("legado"):
            assert ler_capitulo(fixture.read_text(encoding="utf-8")).brutos == (), fixture.name


def test_a_marcacao_no_comentario_deixa_a_partida_bruta() -> None:
    texto = (CABECA + '<section class="cb-game"><div class="cb-moves">'
             '<p class="cb-line cb-mainline"><span class="cb-movenum">1.</span> '
             '<span class="cb-move" data-uci="e2e4" '
             'data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1">e4</span></p>'
             '<p class="cb-comment">Um lance <em>clássico</em>.</p></div></section>' + PE)
    bloco = ler_capitulo(texto).blocos[0]
    assert isinstance(bloco, RawPassthrough), "o comentário do IR é texto: o <em> se perderia"
    assert canon(_volta(texto)) == canon(texto)
    sem_marcacao = texto.replace("<em>clássico</em>", "clássico")
    assert isinstance(ler_capitulo(sem_marcacao).blocos[0], GameScore)


def test_o_title_na_imagem_do_diagrama_deixa_o_diagrama_bruto() -> None:
    texto = (CABECA + f'<figure class="cb-diagram" data-fen="{MATE}" data-stm="w" '
             'data-mode="svg" data-orientation="white"><img class="cb-svg" '
             'src="../Images/dg_01cfdcf32961.svg" alt="x" title="da pessoa"/></figure>' + PE)
    assert isinstance(ler_capitulo(texto).blocos[0], RawPassthrough)
    assert canon(_volta(texto)) == canon(texto)


def test_o_diagrama_do_cb_sem_os_derivados_continua_diagrama() -> None:
    """O `InsertDiagram` do CB omite o `data-mode`; a imagem desatualizada é derivada (§6.1)."""
    texto = (CABECA + f'<figure class="cb-diagram" data-fen="{MATE}"><img class="cb-svg" '
             'src="../Images/dg_antiga.svg" alt="O mate do corredor."/></figure>' + PE)
    bloco = ler_capitulo(texto).blocos[0]
    assert isinstance(bloco, Diagram)
    escrito = _volta(texto)
    assert 'data-mode="svg"' in escrito
    assert "dg_01cfdcf32961.svg" in escrito, "o escritor refaz o nome da imagem pela FEN"


def test_o_mathml_da_pessoa_fica_bruto_e_a_formula_do_contrato_nao() -> None:
    texto = (CABECA + '<p>x <math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math> '
             '<math xmlns="http://www.w3.org/1998/Math/MathML"><annotation '
             'encoding="application/x-tex">\\frac{1}{2}</annotation></math></p>' + PE)
    paragrafo = ler_capitulo(texto).blocos[0]
    assert isinstance(paragrafo, Paragraph)
    tipos = [type(n) for n in paragrafo.content if type(n).__name__ != "Text"]
    assert tipos == [RawInline, MathInline]
    assert canon(_volta(texto)) == canon(texto)


def test_o_canon_nao_confunde_o_espaco_sem_quebra_com_o_espaco() -> None:
    assert canon("<p>12\u00a0de julho</p>") != canon("<p>12 de julho</p>")
    assert canon("<p>12  de\njulho</p>") == canon("<p>12 de julho</p>")


def test_o_svg_e_o_mathml_brutos_saem_com_o_prefixo_declarado() -> None:
    texto = (EDITADOS / "16_svg_da_pessoa.xhtml").read_text(encoding="utf-8")
    escrito, _ = escrever_capitulo(ler_capitulo(texto))
    assert 'xmlns:svg="http://www.w3.org/2000/svg"' in escrito
    relido = ler_capitulo(escrito)  # o arquivo escrito é XML bem formado
    assert isinstance(relido, Capitulo)
    assert isinstance(relido.blocos[1], RawPassthrough)
