"""As cores das abas da suíte pela pele do tronco (OCR_UI ciclo 2, passo C9).

As views de ``caissa.ui`` nasceram com cores cravadas -- ``#7c3aed`` na caixa de região,
``#3f3f46`` no fundo do visor, ``#6b7280`` no contexto do cartão, ``#b45309`` no motivo -- e
``Consolas`` fixa. Dentro da janela do tronco elas ignoravam a pele: na Foco (a padrão) o
``#6b7280`` sobre ``#1f2124`` e o ``#b45309`` sobre escuro ficavam **não medidos** pelo portão
de contraste, que só derivava pares da folha do tronco (``OCR_UI_ANALISE_C2.md`` §6.7).

Este módulo é a única porta: cada cor das views tem um **papel** (a coluna da esquerda de
:data:`PAPEIS`), o papel resolve para o token do tronco quando ``chess_diagram_ocr.ui.tokens``
está ao alcance -- com o cromo em vigor -- e para a reserva da suíte quando não (a suíte
sozinha, os testes sem tronco). O portão de contraste lê a mesma tabela
(``caissa.ui.audit.contraste.pares_pintados_da_suite``) e mede cada par frente/fundo nas duas
peles; um papel novo entra no portão por existir aqui.
"""

from __future__ import annotations

from typing import Any

__all__ = ["PAPEIS", "PARES", "cor", "cromo_escuro", "fonte_monoespacada", "tem_tronco", "vestir_paginador"]

#: Papel da suíte -> (token do tronco, reserva clara, reserva escura).
PAPEIS: dict[str, tuple[str, str, str]] = {
    # a caixa de uma região de rotulagem sobre a página, e a selecionada
    # reserva clara #8b5cf6 e não #7c3aed: 4,04:1 sobre a folha, contra 2,99:1 (piso 3,0)
    "regiao": ("A_FAZER", "#8b5cf6", "#a78bfa"),
    # `TRACEJADO` é, na tabela de significado do tronco, "a área que você está selecionando"
    # -- a marcação de página para o que está em foco; `ALVO` é de tabuleiro e some sobre a folha.
    "regiao_selecionada": ("TRACEJADO", "#dc2626", "#f87171"),
    # o vazio em volta da página no visor da Rotulagem
    "vazio_do_visor": ("VAZIO_DE_CANVAS", "#3f3f46", "#26282b"),
    # a linha acima da barra de estado das abas
    "moldura": ("MOLDURA", "#d1d5db", "#3a3d42"),
    # o cartão da linha em revisão
    "cartao_fundo_do_recorte": ("SUPERFICIE_DICA", "#e5e7eb", "#2b2d31"),
    "cartao_contexto": ("TEXTO_SECUNDARIO", "#6b7280", "#a3a8b0"),
    "cartao_motivo": ("DIVERGENTE_TEXTO", "#b45309", "#f5b64a"),
    # as palavras fracas da leitura do motor, na **letra** e não no fundo: é a regra do editor
    # de texto do tronco (`ui/texto_cores.py`: `revisar` em `PROBLEMA_TEXTO`, `conferir` em
    # `ATENCAO`) -- naquela aba a cor da letra já quer dizer confiança, e os realces de fundo
    # (`REALCE_*`) são o canal de quem escreve. A primeira versão pintava o fundo com
    # `REALCE_NOTA`, que é verde: uma palavra duvidosa saía com a cor de "nota do autor"
    "cartao_palavra_revisar": ("PROBLEMA_TEXTO", "#b91c1c", "#f87171"),
    "cartao_palavra_conferir": ("ATENCAO", "#8a5a00", "#c78200"),
    "cartao_texto": ("TEXTO_PADRAO", "#111827", "#e9eaec"),
    # o aviso da exportação
    "aviso": ("PROBLEMA_TEXTO", "#b91c1c", "#f87171"),
    # o registro (log) da Rotulagem
    "log_fundo": ("SUPERFICIE_DICA", "#111827", "#111827"),
    "log_texto": ("TEXTO_PADRAO", "#e5e7eb", "#e5e7eb"),
}

#: Os pares frente/fundo que as views pintam, para o portão de contraste medir: (papel da
#: frente, papel do fundo, o que é). O fundo ``"cromo"`` é a superfície da janela
#: (``SUPERFICIE_CROMO`` do tronco, ou a reserva).
PARES: tuple[tuple[str, str, str], ...] = (
    ("cartao_contexto", "cromo", "o contexto da linha no cartão da revisão"),
    ("cartao_motivo", "cromo", "o motivo da dúvida no cartão da revisão"),
    ("aviso", "cromo", "o aviso da aba Exportação"),
    ("log_texto", "log_fundo", "o registro da Rotulagem"),
    ("cartao_palavra_revisar", "cromo", "a palavra muito fraca da leitura do motor, no cartão"),
    ("cartao_palavra_conferir", "cromo", "a palavra fraca da leitura do motor, no cartão"),
    ("regiao", "pagina", "a caixa de região sobre a página"),
    ("regiao_selecionada", "pagina", "a caixa selecionada sobre a página"),
)

#: Os fundos que os pares medem: a superfície da janela (``SUPERFICIE_PADRAO`` do tronco) e a
#: superfície sob as marcações da página -- a mesma contra a qual o tronco mede as suas
#: (``contraste.pares_pintados``).
_FUNDOS = {"cromo": ("SUPERFICIE_PADRAO", "#ffffff", "#1f2124"),
           "pagina": ("SUPERFICIE_PAGINA", "#1c1c1c", "#1c1c1c")}


def _tokens() -> Any:
    try:
        from chess_diagram_ocr.ui import tokens
    except Exception:  # noqa: BLE001 - sem o tronco, as reservas
        return None
    return tokens


def tem_tronco() -> bool:
    return _tokens() is not None


def cromo_escuro() -> bool:
    """O cromo em vigor na janela do tronco, quando ele está ao alcance; claro sem ele."""
    try:
        from chess_diagram_ocr.qt import tema

        return bool(tema.cromo_escuro_em_vigor())
    except Exception:  # noqa: BLE001 - sem tema (ou sem QApplication) o cromo é o claro
        return False


def cor(papel: str, *, escuro: bool | None = None) -> str:
    """O hexadecimal de um papel da suíte: o token do tronco no cromo em vigor, ou a reserva."""
    token, claro, escuro_reserva = PAPEIS.get(papel) or _FUNDOS[papel]
    if escuro is None:
        escuro = cromo_escuro()
    tokens = _tokens()
    if tokens is not None:
        try:
            return str(tokens.cor(token, None, cromo_escuro=escuro))
        except Exception:  # noqa: BLE001 - um token que o tronco não tem cai na reserva
            pass
    return escuro_reserva if escuro else claro


def fonte_monoespacada() -> Any:
    """A fonte de largura fixa do sistema, para o registro e o texto bruto -- não ``Consolas``."""
    from PyQt6.QtGui import QFontDatabase

    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def vestir_paginador(anterior: Any, proxima: Any) -> bool:
    """Os dois botões do paginador com o desenho do tronco ao lado da palavra (passo C9).

    ``"◀ anterior"`` / ``"próxima ▶"`` como texto era o item 4 do §9 do ciclo 5 do tronco
    voltando por outra porta: o ``◀`` do Segoe UI rende um traço chato de 5×3 px. Com o tronco
    ao alcance, o glifo sai e o ícone ``diagrama_anterior``/``proximo_diagrama`` entra ao lado
    da palavra (``qt/icones.vestir(manter_texto=True)``); sem ele, só a palavra fica.
    ``True`` quando o desenho entrou.
    """
    anterior.setText("Anterior")
    proxima.setText("Próxima")
    try:
        from chess_diagram_ocr.qt import icones
        from chess_diagram_ocr.ui import estilos
    except Exception:  # noqa: BLE001 - sem o tronco, a palavra basta
        return False
    try:
        a = icones.vestir(anterior, "diagrama_anterior", estilos.NEUTRO, manter_texto=True)
        b = icones.vestir(proxima, "proximo_diagrama", estilos.NEUTRO, manter_texto=True)
    except Exception:  # noqa: BLE001 - um ícone que não desenha não derruba a aba
        return False
    return bool(a and b)
