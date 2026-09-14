"""Os dois portões da fita (OCR_UI_ROADMAP passo 12), na parte que não abre janela.

A aritmética -- o que é rótulo, o que é hit, o que é cabeçalho ausente, o que é traço fino --
mora antes do primeiro `import PyQt6`, como nos outros portões de `caissa.ui.audit`, e é aqui
que ela se afirma no venv da suíte, que não tem binding de Qt.
"""

from __future__ import annotations

from caissa.ui.audit.fita import HIT_MINIMO, Botao, Medida, veredito
from caissa.ui.audit.icones import CAIXA_MENOR_MINIMA, TINTA_MINIMA, Icone
from caissa.ui.audit.icones import veredito as veredito_dos_icones


def _botao(acao: str, texto: str, *, dica: str = "", largura: int = 76, altura: int = 43) -> Botao:
    return Botao(acao=acao, texto=texto, dica=dica, largura=largura, altura=altura, tem_icone=True)


def test_a_dica_nao_e_rotulo_e_um_glifo_tambem_nao():
    assert _botao("abrir_pdf", "Abrir\nPDF").tem_rotulo
    assert not _botao("zoom_mais", "", dica="Aumentar o zoom da página").tem_rotulo, (
        "R3.4: a dica só aparece a quem parou o ponteiro")
    assert not _botao("proximo_lance", "▶").tem_rotulo, "um glifo não é uma palavra"
    assert _botao("zoom_menos", "Menos\nzoom").tem_rotulo


def test_o_hit_e_medido_nos_dois_eixos():
    assert _botao("a", "A", largura=HIT_MINIMO, altura=HIT_MINIMO).hit_ok
    assert not _botao("a", "A", largura=HIT_MINIMO - 1, altura=60).hit_ok
    assert not _botao("a", "A", largura=60, altura=HIT_MINIMO - 1).hit_ok


def test_a_medida_conta_os_tres_defeitos_e_o_orcamento():
    medida = Medida(
        arranjo="fita/compacta", largura_da_janela=1280, modo="compacto", altura_da_fita=59,
        orcamento=72,
        botoes=[_botao("abrir_pdf", "Abrir\nPDF"), _botao("zoom_mais", "", dica="Aumentar"),
                _botao("fim_da_linha", "Fim da\nlinha", largura=49, altura=38)],
        cabecalhos_declarados=("Arquivo", "Edição", "Estudo"),
        cabecalhos_visiveis=("Arquivo", "Estudo"),
    )
    assert [b.acao for b in medida.sem_rotulo] == ["zoom_mais"]
    assert [b.acao for b in medida.hit_pequeno] == ["fim_da_linha"]
    assert medida.cabecalhos_faltando == ("Edição",)
    assert medida.defeitos == 3
    assert medida.veredito == "REPROVOU"
    dicionario = medida.como_dicionario()
    assert dicionario["com_rotulo"] == 2
    assert dicionario["hit_abaixo_do_ideal"] == 3, "43 px é o hit medido; 44 é o ideal"
    limpa = Medida(arranjo="fita/compacta", largura_da_janela=1280, modo="compacto",
                   altura_da_fita=59, orcamento=72, botoes=[_botao("abrir_pdf", "Abrir")],
                   cabecalhos_declarados=("Arquivo",), cabecalhos_visiveis=("Arquivo",))
    assert limpa.veredito == "PASSOU"
    estourada = Medida(arranjo="fita/compacta", largura_da_janela=1280, modo="compacto",
                       altura_da_fita=80, orcamento=72, botoes=[_botao("abrir_pdf", "Abrir")],
                       cabecalhos_declarados=("Arquivo",), cabecalhos_visiveis=("Arquivo",))
    assert estourada.veredito == "REPROVOU", "acima do orçamento é defeito mesmo sem outro"
    assert veredito([limpa.como_dicionario(), estourada.como_dicionario()]) == "REPROVOU"
    assert veredito([]) == "SEM FITA"


def test_o_icone_e_julgado_pelo_traco_pela_caixa_e_pela_tinta():
    bom = Icone(acao="ler_pagina", icone="ler_pagina", lado=20, traco=2, caixa_largura=20,
                caixa_altura=20, tinta=0.33)
    assert bom.defeitos == ()
    fino = Icone(acao="a", icone="a", lado=20, traco=1, caixa_largura=20, caixa_altura=20,
                 tinta=0.20)
    assert fino.defeitos == ("traco 1 px < 2",)
    achatado = Icone(acao="desfazer", icone="desfazer", lado=20, traco=2, caixa_largura=20,
                     caixa_altura=9, tinta=0.118)
    assert achatado.caixa_menor < CAIXA_MENOR_MINIMA
    assert achatado.defeitos == ("caixa 20x9 no lado 20",), "o desfazer do ciclo 15"
    apagado = Icone(acao="a", icone="a", lado=20, traco=2, caixa_largura=20, caixa_altura=20,
                    tinta=TINTA_MINIMA / 2)
    assert apagado.defeitos == ("tinta 5.0 % < 10 %",)
    assert veredito_dos_icones([bom.como_dicionario()]) == "PASSOU"
    assert veredito_dos_icones([bom.como_dicionario(), fino.como_dicionario()]) == "REPROVOU"
    assert veredito_dos_icones([]) == "SEM ICONES"
