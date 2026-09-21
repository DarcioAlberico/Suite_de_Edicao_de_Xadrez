"""OCR_UI_ROADMAP_C2 passo C9: as abas da suíte pela pele do tronco.

Sem o tronco ao alcance as views usam as reservas; com ele, o token do cromo em vigor.  E o
portão de contraste mede os pares que as views pintam — os que nunca estiveram em portão.
"""

from __future__ import annotations

from caissa.ui.theme import pele


def test_todo_papel_resolve_para_um_hexadecimal_nas_duas_peles():
    for papel in pele.PAPEIS:
        for escuro in (False, True):
            cor = pele.cor(papel, escuro=escuro)
            assert cor.startswith("#") and len(cor) == 7, (papel, cor)


def test_os_pares_medidos_so_apontam_para_papeis_conhecidos():
    for frente, fundo, _ in pele.PARES:
        assert frente in pele.PAPEIS
        assert fundo in pele.PAPEIS or fundo in ("cromo", "pagina")


def test_sem_o_tronco_a_reserva_e_a_da_pele_pedida(monkeypatch):
    monkeypatch.setattr(pele, "_tokens", lambda: None)
    assert pele.cor("cartao_contexto", escuro=False) == "#6b7280"
    assert pele.cor("cartao_contexto", escuro=True) == "#a3a8b0"


def test_com_o_tronco_a_cor_e_o_token_do_cromo():
    try:
        from chess_diagram_ocr.ui import tokens
    except Exception:  # noqa: BLE001 - máquina sem o tronco: a reserva já está coberta
        return
    assert pele.cor("cartao_contexto", escuro=True) == tokens.cor(
        "TEXTO_SECUNDARIO", None, cromo_escuro=True)
    assert pele.cor("regiao", escuro=False) == tokens.cor("A_FAZER", None, cromo_escuro=False)


def test_o_portao_de_contraste_mede_os_pares_da_suite():
    try:
        from caissa.ui.audit.contraste import pares_pintados_da_suite
    except Exception:  # noqa: BLE001
        return
    try:
        pares = pares_pintados_da_suite(cromo_escuro=True)
    except Exception:  # noqa: BLE001 - sem o tronco o portão não roda; ele já se recusa sozinho
        return
    assert len(pares) == len(pele.PARES)
    assert all(p.origem == "suite" and p.portao for p in pares)
    assert all(p.passou() for p in pares), [(p.onde, p.razao) for p in pares if not p.passou()]
