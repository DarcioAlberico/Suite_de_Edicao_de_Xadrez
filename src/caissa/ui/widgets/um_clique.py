"""O botão que decide e anda não toma o segundo clique de um duplo clique por outra decisão.

«Aceitar leitura» decide a linha atual e passa à próxima; o segundo clique de um duplo clique, se
ainda cai no botão, decidia a próxima uma fração de segundo depois de ela aparecer -- uma leitura
aceita que ninguém viu (crítico da fase 5, ciclo 9: na Revisão de texto, 2 itens em 4 de 4, de
antes; na Rotulagem, desde que nada mais se mexe debaixo do ponteiro no duplo clique, 2 linhas em 8
de 12, e «Próxima» andava duas linhas). O Qt 6 entrega o segundo clique de um duplo clique como
um pressionar, que baixa o botão, seguido de um `MouseButtonDblClick`; o filtro engole o duplo
clique e levanta o botão, e o soltar que vem depois não clica. Outro clique, passado o intervalo do
duplo clique, decide como sempre; o teclado não muda.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QAbstractButton


class _UmCliquePorVez(QObject):
    """Engole o `MouseButtonDblClick` dos botões que vigia, e levanta o botão."""

    def eventFilter(self, objeto: QObject | None, evento: QEvent | None) -> bool:  # noqa: N802 - Qt
        if evento is None or evento.type() != QEvent.Type.MouseButtonDblClick:
            return False
        if isinstance(objeto, QAbstractButton):
            objeto.setDown(False)  # o pressionar do segundo clique o baixou: o soltar não clica
        return True


def um_clique_por_vez(dono: QObject, *botoes: QAbstractButton) -> QObject:
    """Os ``botoes`` não tomam o segundo clique de um duplo clique por outro clique.

    Devolve o filtro, filho de ``dono``: guarde-o, para o objeto Python viver com o painel.
    """
    filtro = _UmCliquePorVez(dono)
    for botao in botoes:
        botao.installEventFilter(filtro)
    return filtro
