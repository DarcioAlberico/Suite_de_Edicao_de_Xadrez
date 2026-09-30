"""O perfil legível do motor HTML (Editor HTML/CSS, passo H5): `caissa.export.legivel`."""

from __future__ import annotations

from pathlib import Path

import pytest

from caissa.core.model import (
    Diagram,
    Document,
    GameScore,
    Heading,
    Paragraph,
    ParagraphProps,
    Provenance,
    RawInline,
    RawPassthrough,
    Text,
)
from caissa.export.legivel import (
    Capitulo,
    canon,
    escrever_capitulo,
    ler_capitulo,
)
from caissa.export.text import game_from_pgn

CONTRATO = Path(__file__).resolve().parents[2] / "fixtures" / "editor" / "contrato"
FIXTURES = sorted(p for p in CONTRATO.glob("*.xhtml") if not p.name.startswith("legado"))
KINGS = "4k3/8/8/8/8/8/8/4K3"


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
def test_a_volta_fecha_nas_fixtures_do_contrato(fixture: Path) -> None:
    """canon(escrever(ler(x))) == canon(x): a spec R2.2a."""
    original = fixture.read_text(encoding="utf-8")
    escrito, _ = escrever_capitulo(ler_capitulo(original))
    assert canon(escrito) == canon(original)


def test_as_fixtures_existem() -> None:
    assert len(FIXTURES) == 19


def test_o_canon_normaliza_so_o_insignificante() -> None:
    assert canon('<p a="1"  b="2">x  y</p>') == canon('<p b="2" a="1">x y</p>')
    assert canon("<div>\n  <p>x</p>\n</div>") == canon("<div><p>x</p></div>")
    assert canon("<p><em>a</em> <em>b</em></p>") != canon("<p><em>a</em><em>b</em></p>")


def test_o_leitor_aceita_o_diagrama_sem_data_mode() -> None:
    """O `InsertDiagram` do CB omite o `data-mode`: ausente é `svg` (o contrato, §6.1)."""
    texto = (f'<html xmlns="http://www.w3.org/1999/xhtml"><body>'
             f'<figure class="cb-diagram" data-fen="{KINGS} b - - 0 1" data-stm="b">'
             f'<img class="cb-svg" src="../Images/x.svg" alt="Posição"/></figure>'
             f"</body></html>")
    diagrama = ler_capitulo(texto).blocos[0]
    assert isinstance(diagrama, Diagram)
    assert diagrama.fen == f"{KINGS} b - - 0 1"
    assert diagrama.html_attributes == ()


def test_o_que_o_contrato_nao_modela_e_preservado() -> None:
    capitulo = ler_capitulo((CONTRATO / "bruto.xhtml").read_text(encoding="utf-8"))
    assert isinstance(capitulo.blocos[0], RawPassthrough)
    assert "<address>" in capitulo.blocos[0].text
    brutos = [i for i in capitulo.blocos[1].content if isinstance(i, RawInline)]
    assert [b.text.split(">")[0] for b in brutos] == ["<kbd", "<kbd", "<mark",
                                                     '<abbr title="Federação Internacional"']
    atributos = ler_capitulo((CONTRATO / "atributos.xhtml").read_text(encoding="utf-8"))
    paragrafo = atributos.blocos[0]
    assert paragrafo.props.style == "Caption"
    assert dict(paragrafo.html_attributes) == {
        "id": "p61-1", "class": "minha-classe", "style": "color: #444444", "title": "uma dica",
        "data-meu": "x", "aria-describedby": "p61-2"}


def test_a_partida_volta_como_arvore() -> None:
    capitulo = ler_capitulo((CONTRATO / "partida.xhtml").read_text(encoding="utf-8"))
    partida = capitulo.blocos[0]
    assert isinstance(partida, GameScore)
    assert (partida.headers.white, partida.headers.black, partida.headers.result) == (
        "Magnus Carlsen", "Fabiano Caruana", "1-0")
    principal = [n.san for n in partida.mainline()]
    assert principal[:8] == ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"]
    lance = partida.children[0]  # 1.e4
    for _ in range(4):  # e5, Nf3, Nc6, Bb5
        lance = lance.children[0]
    bispo = lance
    assert [f.san for f in bispo.children] == ["a6", "Nf6"], "a variante é irmã do a6"
    assert bispo.children[0].comment_after == "A outra defesa é a berlinense."
    assert bispo.nags == (1,)


def test_o_mapa_da_proveniencia_leva_o_id_e_a_pagina_e_os_devolve() -> None:
    proveniencia = Provenance(page_index=54)
    documento = Document(body=(
        Heading(level=1, content=(Text(content="Título"),), provenance=proveniencia),
        Paragraph(content=(Text(content="Um parágrafo."),), provenance=proveniencia),
        Paragraph(content=(Text(content="Autoral."),)),
    ))
    capitulo = Capitulo(blocos=documento.body, titulo="c")
    escrito, escritor = escrever_capitulo(capitulo, documento, folios={55: "54"})
    assert '<span epub:type="pagebreak" role="doc-pagebreak" id="pg55" aria-label="54"/>' in escrito
    assert '<h1 id="p55-1">' in escrito
    assert '<p id="p55-2">' in escrito
    assert set(escritor.mapa.nos) == {"p55-1", "p55-2"}
    relido = ler_capitulo(escrito, mapa=escritor.mapa)
    assert [b.id for b in relido.blocos] == [b.id for b in documento.body[:2]] + [
        relido.blocos[2].id]
    assert relido.blocos[0].provenance == proveniencia
    assert relido.blocos[0].html_attributes == ()
    de_novo, _ = escrever_capitulo(relido, documento, folios=escritor.mapa.folios)
    assert canon(de_novo) == canon(escrito)
    sem_mapa = ler_capitulo(escrito)
    assert isinstance(sem_mapa.blocos[0], RawPassthrough), "o marcador fica como veio"
    assert sem_mapa.blocos[1].anchor == "p55-1", "o título tem âncora: o id vai para ela"
    assert [dict(b.html_attributes).get("id") for b in sem_mapa.blocos[1:]] == [
        None, "p55-2", None]
    de_novo, _ = escrever_capitulo(sem_mapa)
    assert canon(de_novo) == canon(escrito)


def test_o_estilo_de_paragrafo_volta_pelo_slug() -> None:
    documento = Document(body=(Paragraph(content=(Text(content="x"),),
                                         props=ParagraphProps(style="Citação longa")),))
    escrito, _ = escrever_capitulo(Capitulo(blocos=documento.body), documento)
    assert 'class="cb-style-citacao-longa"' in escrito
    assert ler_capitulo(escrito, estilos=["Citação longa"]).blocos[0].props.style == (
        "Citação longa")


def test_a_partida_do_pgn_vai_e_volta() -> None:
    partida = game_from_pgn(
        '[White "A"]\n[Black "B"]\n[Result "0-1"]\n\n'
        "1. d4 Nf6 2. c4 e6 (2... g6 3. Nc3 Bg7) 3. Nc3 $1 Bb4 {a Nimzo} 4. e3 0-1\n")
    escrito, _ = escrever_capitulo(Capitulo(blocos=(partida,)))
    relida = ler_capitulo(escrito).blocos[0]
    assert isinstance(relida, GameScore)
    de_novo, _ = escrever_capitulo(Capitulo(blocos=(relida,)))
    assert canon(de_novo) == canon(escrito)
    no_c4 = relida.children[0].children[0].children[0]
    assert [f.san for f in no_c4.children] == ["e6", "g6"]
