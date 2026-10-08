r"""A camada do contrato (spec S10): as classes e os atributos do `docs/MARKUP_CAISSA.md`.

Origem: o `validate.py` do ChessBook Studio (`..\Sigil-master\src\Resource_Files\python3lib\
sigil_chess\validate.py`, GPLv3 ou posterior — compatível com a AGPLv3 da suíte), cujas regras
do diagrama e do lance vivem aqui e na camada do xadrez (`xadrez.py`). Duas diferenças de
propósito: a árvore do `expat` dá a **linha e a coluna** de cada elemento (o CB lê por expressão
e dá a linha), e o que o CB pula em silêncio — o `cb-move` sem `data-fen`, a classe que as
expressões dele confundem — aqui é acusado (o contrato v2, §10).

- `figure.cb-diagram` sem `data-fen` (do CB), e a `data-fen` que não se lê (do CB), no diagrama, no
  diagrama do texto e no lance;
- o `data-stm` que diz outro lado que a FEN;
- o `img.cb-svg` com o nome derivado de outra posição (`dg_<hash>` da FEN e da orientação, §6.1);
- a imagem que o livro não tem (do CB: «Diagram image not found in the book»);
- o `cb-move` sem `data-fen` (o CB o pula);
- o elemento que uma expressão do CB casa sem ter a classe dela (§10), e a classe `cb-*` que o
  contrato não tem.
"""

from __future__ import annotations

import re

import chess

from caissa.editor.validacao.contexto import Contexto, resolver
from caissa.editor.validacao.problema import Problema, Severidade, regra
from caissa.editor.validacao.xml import Documento, Elemento
from caissa.export.legivel import imagem_do_diagrama

__all__ = ["CLASSES", "ler_fen", "verificar"]

K = "contrato"
SEM_FEN = regra("contrato-diagrama-sem-fen", K, Severidade.BLOQUEIA,
                "Diagrama sem data-fen (do CB)",
                "Dê ao diagrama a posição em data-fen (a FEN inteira).")
FEN_INVALIDA = regra("contrato-fen-invalida", K, Severidade.BLOQUEIA,
                     "A FEN não se lê (do CB)",
                     "Corrija a FEN: seis campos, oito fileiras de oito casas.")
STM = regra("contrato-stm-incoerente", K, Severidade.BLOQUEIA,
            "data-stm diz outro lado que a FEN",
            "Deixe data-stm igual ao segundo campo da FEN (w ou b).")
SVG = regra("contrato-svg-incoerente", K, Severidade.AVISA,
            "A imagem do diagrama é de outra posição (o nome derivado, §6.1)",
            "Regere a imagem do diagrama (o nome sai da FEN e da orientação).")
IMAGEM_AUSENTE = regra("contrato-imagem-ausente", K, Severidade.BLOQUEIA,
                       "A imagem não está no livro (do CB)",
                       "Ponha o arquivo no projeto, ou corrija o src.")
LANCE_SEM_FEN = regra("contrato-lance-sem-fen", K, Severidade.AVISA,
                      "Lance sem data-fen: o CB o pula",
                      "Dê ao lance a posição depois dele (data-fen), ou use a forma literal "
                      "(span.cb-literal-move).")
CONFUNDIDA = regra("contrato-classe-confundida", K, Severidade.AVISA,
                   "O validador do CB confunde esta classe (§10)",
                   "Troque o nome: ele casa com a expressão com que o CB acha a marcação dele.")
DESCONHECIDA = regra("contrato-classe-desconhecida", K, Severidade.AVISA,
                     "Classe cb-* fora do contrato",
                     "Confira o nome no MARKUP_CAISSA; uma classe sua não usa o prefixo cb-.")

_LISTA_DO_CONTRATO = """
cb-annotator cb-black cb-callout cb-callout-title cb-caption cb-caption-text cb-chapter
cb-chapter-title cb-comment cb-date cb-diagram cb-diagram-caption cb-diagram-context
cb-diagram-label cb-dropcap cb-eco cb-elo cb-event cb-event-name cb-figure-label cb-font-board
cb-footnote cb-game cb-game-header cb-game-number cb-game-title cb-group-title cb-heading-number
cb-image cb-index cb-index-entry cb-index-heading cb-index-mark cb-index-name cb-index-players
cb-index-refs cb-inline-diagram cb-line cb-link cb-literal-move cb-mainline cb-move cb-movenum
cb-moves cb-movetext cb-nag cb-name cb-noteref cb-opening cb-opening-name cb-ornament
cb-page-break cb-piece cb-player cb-rank cb-raw cb-ref cb-ref-black cb-ref-white cb-result
cb-round cb-run-in cb-running-foot cb-running-head cb-section-break cb-site cb-smallcaps
cb-solution cb-stipulation cb-stm-marker cb-svg cb-svg-fallback cb-tag cb-term cb-toc
cb-variation cb-white cb-imagem-de-texto cb-resumo-simples
"""
CLASSES = frozenset(_LISTA_DO_CONTRATO.split())
"""As classes do contrato v2 (`docs/MARKUP_CAISSA.md`); `cb-depth-<n>` e `cb-style-<slug>` são
famílias."""
_FAMILIAS = (re.compile(r"^cb-depth-\d+$"), re.compile(r"^cb-style-[a-z0-9-]+$"))
MARCACOES_DO_CB = (("span", "cb-move"), ("p", "cb-line"), ("section", "cb-game"),
                   ("figure", "cb-diagram"))
"""O elemento e a classe que cada expressão do `validate.py` do CB casa (MARKUP §10)."""


def ler_fen(fen: str) -> chess.Board | None:
    """O tabuleiro da FEN, ou `None` se ela não se lê."""
    try:
        return chess.Board(fen)
    except ValueError:
        return None


def verificar(documento: Documento, contexto: Contexto) -> list[Problema]:
    problemas: list[Problema] = []
    for elemento in documento.elementos():
        problemas += _classes(documento, elemento)
        classes = elemento.classes()
        if elemento.nome == "figure" and "cb-diagram" in classes:
            problemas += _diagrama(documento, elemento)
        elif elemento.nome == "span" and "cb-inline-diagram" in classes:
            fen = elemento.get("data-fen")
            if fen and ler_fen(fen) is None:
                problemas.append(Problema(FEN_INVALIDA, documento.local(elemento), fen))
        elif elemento.nome == "span" and "cb-move" in classes:
            problemas += _lance(documento, elemento)
        if elemento.nome == "img" and contexto.arquivos:
            caminho = resolver(documento.arquivo, elemento.get("src") or "")
            if caminho is not None and caminho not in contexto.arquivos:
                problemas.append(Problema(IMAGEM_AUSENTE, documento.local(elemento),
                                          elemento.get("src") or ""))
    return problemas


def _classes(documento: Documento, elemento: Elemento) -> list[Problema]:
    problemas = []
    classes = elemento.classes()
    atributo = elemento.get("class") or ""
    for etiqueta, classe in MARCACOES_DO_CB:
        if elemento.nome == etiqueta and classe not in classes and \
                re.search(rf"\b{re.escape(classe)}\b", atributo):
            problemas.append(Problema(CONFUNDIDA, documento.local(elemento),
                                      f"«{atributo}» num <{etiqueta}> é lido como {classe}"))
    problemas += [Problema(DESCONHECIDA, documento.local(elemento), classe)
                  for classe in classes if classe.startswith("cb-") and classe not in CLASSES
                  and not any(f.match(classe) for f in _FAMILIAS)]
    return problemas


def _diagrama(documento: Documento, figura: Elemento) -> list[Problema]:
    local = documento.local(figura)
    fen = (figura.get("data-fen") or "").strip()
    if not fen:
        return [Problema(SEM_FEN, local)]
    tabuleiro = ler_fen(fen)
    if tabuleiro is None:
        return [Problema(FEN_INVALIDA, local, fen)]
    problemas = []
    lado = (figura.get("data-stm") or "").strip()
    if lado and lado != fen.split()[1]:
        problemas.append(Problema(STM, local, f"data-stm={lado}, a FEN diz {fen.split()[1]}"))
    orientacao = figura.get("data-orientation") or "white"
    esperado = imagem_do_diagrama(fen, orientacao)
    for img in figura.elementos():
        if img.nome == "img" and "cb-svg" in img.classes():
            nome = (img.get("src") or "").rsplit("/", 1)[-1]
            if nome.startswith("dg_") and nome != esperado:
                problemas.append(Problema(SVG, documento.local(img),
                                          f"{nome}; a posição pede {esperado}"))
    return problemas


def _lance(documento: Documento, lance: Elemento) -> list[Problema]:
    local = documento.local(lance)
    fen = lance.get("data-fen")
    if not fen:
        return [Problema(LANCE_SEM_FEN, local, lance.get("data-san") or lance.texto().strip())]
    problemas = []
    for atributo in ("data-fen", "data-fen-before", "data-fen-after"):
        valor = lance.get(atributo)
        if valor and ler_fen(valor) is None:
            problemas.append(Problema(FEN_INVALIDA, local, f"{atributo}={valor}"))
    return problemas
