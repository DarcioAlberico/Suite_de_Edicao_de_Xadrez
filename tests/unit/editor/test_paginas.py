"""A base das páginas, uma regra só (spec R2.7): `caissa.editor.paginas`."""

from __future__ import annotations

import pytest

from caissa.editor import paginas


def test_janela_em_base_1_e_ir_em_base_0() -> None:
    assert paginas.pagina_da_janela(54) == 55
    assert paginas.indice_do_ir(55) == 54
    for indice in (0, 1, 54, 897):
        assert paginas.indice_do_ir(paginas.pagina_da_janela(indice)) == indice
    with pytest.raises(ValueError, match="começa em 1"):
        paginas.indice_do_ir(0)
    with pytest.raises(ValueError, match="negativo"):
        paginas.pagina_da_janela(-1)


def test_os_ids_do_livro_usam_a_pagina_da_janela() -> None:
    assert paginas.id_de_bloco(55, 3) == "p55-3"
    assert paginas.id_de_diagrama(55, 1) == "p55-d1"
    assert paginas.id_de_partida(55, 2) == "p55-g2"
    assert paginas.id_de_marcador(55) == "pg55"
    with pytest.raises(ValueError, match="a página começa em 1"):
        paginas.id_de_bloco(0, 1)


def test_a_chave_v1_usa_o_indice_do_ir() -> None:
    """A mesma página: `p54:d1` no sidecar v1 é o `p55-d1` do livro (Apêndice C)."""
    assert paginas.chave_v1(54, "d", 1) == "p54:d1"
    lido = paginas.ler_id("p55-d1")
    assert lido is not None
    assert paginas.chave_v1(lido.indice, "d", lido.n) == "p54:d1"


def test_ler_id() -> None:
    assert paginas.ler_id("p55-3") == paginas.IdDoLivro(55, "bloco", 3)
    assert paginas.ler_id("p55-g2") == paginas.IdDoLivro(55, "partida", 2)
    assert paginas.ler_id("pg55") == paginas.IdDoLivro(55, "marcador", 0)
    for estranho in ("p0-1", "p55-0", "chapter-3", "game-012", "p55:d1", "pg0"):
        assert paginas.ler_id(estranho) is None, estranho


def test_o_folio_e_o_impresso_ou_o_numero_do_pdf_com_a_nota() -> None:
    impresso = paginas.folio(55, "54")
    assert (impresso.texto, impresso.lido, impresso.nota) == ("54", True, None)
    sem = paginas.folio(55, None)
    assert (sem.texto, sem.lido, sem.nota) == ("55", False, "fólio não lido")
    assert paginas.folio(55, "  ").texto == "55"
    assert paginas.folio(12, "xii").texto == "xii"


def test_o_marcador_do_contrato() -> None:
    assert paginas.marcador_de_pagina(55, "54") == (
        '<span epub:type="pagebreak" role="doc-pagebreak" id="pg55" aria-label="54"/>')
    assert 'aria-label="55"' in paginas.marcador_de_pagina(55, None)
    assert "&quot;" in paginas.marcador_de_pagina(1, 'a"b') or "'" in paginas.marcador_de_pagina(
        1, 'a"b')
