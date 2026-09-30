"""A camada do xadrez (spec S10): o lance legal, a notação e a figurina que a fonte tem.

Origem: as regras do lance e do diagrama vêm do `validate.py` do ChessBook Studio (GPLv3 ou
posterior; ver `contrato.py`): `_check_move_follows` (o lance se joga da posição de antes, e a
`data-fen` é a que ele produz), `_check_diagram_matches_line` (o diagrama mostra a posição do lance
de cima) e `_check_notation_consistency` (as letras das peças de uma língua só), com a tabela de
letras de `sigil_chess.core.san.PIECE_LETTERS`. Como no CB, o primeiro lance de uma linha só se
confere quando a posição de antes está dita (`data-fen-before`): a variante parte de antes do
parêntese, e adivinhar acusaria análise certa como ilegal.

O diagrama que difere do lance de cima **avisa** (no CB é erro): o livro pode ter razão — o
diagrama de outra linha —, e quem decide é a pessoa.
"""

from __future__ import annotations

from collections.abc import Iterator

import chess

from caissa.editor.validacao.contexto import Contexto
from caissa.editor.validacao.contrato import ler_fen
from caissa.editor.validacao.css import folhas_ligadas
from caissa.editor.validacao.folha import Folha
from caissa.editor.validacao.problema import Problema, Severidade, regra
from caissa.editor.validacao.xml import Documento, Elemento

__all__ = ["LETRAS_DAS_PECAS", "verificar"]

X = "xadrez"
ILEGAL = regra("xadrez-lance-ilegal", X, Severidade.BLOQUEIA,
               "O lance não se joga da posição de antes (do CB)",
               "Corrija o lance ou a posição de antes; se o livro imprime assim, use a forma "
               "literal (span.cb-literal-move).")
FEN_DIVERGENTE = regra("xadrez-fen-divergente", X, Severidade.BLOQUEIA,
                       "A data-fen não é a posição que o lance produz (do CB)",
                       "Regere a posição do lance (a data-fen sai do lance jogado).")
DIAGRAMA = regra("xadrez-diagrama-diverge", X, Severidade.AVISA,
                 "O diagrama não mostra a posição do lance de cima (do CB)",
                 "Confira: o diagrama pode ser de outra linha; se for do lance, corrija a FEN.")
NOTACAO = regra("xadrez-notacao-misturada", X, Severidade.AVISA,
                "As letras das peças são de mais de uma língua (do CB)",
                "Escreva os lances numa língua só (ou com figurinas).")
FIGURINA = regra("xadrez-figurina-fora-da-fonte", X, Severidade.AVISA,
                 "A fonte ativa não tem a figurina",
                 "Use uma fonte com as figurinas (U+2654–265F) no texto dos lances.")

LETRAS_DAS_PECAS: dict[str, dict[str, str]] = {
    "en": {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N"},
    "pt": {"K": "R", "Q": "D", "R": "T", "B": "B", "N": "C"},
    "es": {"K": "R", "Q": "D", "R": "T", "B": "A", "N": "C"},
    "de": {"K": "K", "Q": "D", "R": "T", "B": "L", "N": "S"},
    "fr": {"K": "R", "Q": "D", "R": "T", "B": "F", "N": "C"},
    "it": {"K": "R", "Q": "D", "R": "T", "B": "A", "N": "C"},
    "nl": {"K": "K", "Q": "D", "R": "T", "B": "L", "N": "P"},
    "pl": {"K": "K", "Q": "H", "R": "W", "B": "G", "N": "S"},
    "ru": {"K": "Кр", "Q": "Ф", "R": "Л", "B": "С", "N": "К"},
    "cs": {"K": "K", "Q": "D", "R": "V", "B": "S", "N": "J"},
    "da": {"K": "K", "Q": "D", "R": "T", "B": "L", "N": "S"},
    "sv": {"K": "K", "Q": "D", "R": "T", "B": "L", "N": "S"},
    "hu": {"K": "K", "Q": "V", "R": "B", "B": "F", "N": "H"},
    "ro": {"K": "R", "Q": "D", "R": "T", "B": "N", "N": "C"},
    "fi": {"K": "K", "Q": "D", "R": "T", "B": "L", "N": "R"},
}
"""As letras das peças por língua (de `sigil_chess.core.san.PIECE_LETTERS`, sem o peão)."""
FIGURINAS = {"♔": "K", "♕": "Q", "♖": "R", "♗": "B", "♘": "N", "♙": "",
             "♚": "K", "♛": "Q", "♜": "R", "♝": "B", "♞": "N", "♟": ""}


def verificar(documento: Documento, contexto: Contexto) -> list[Problema]:
    if documento.raiz is None:
        return []
    problemas = _linhas(documento)
    problemas += _diagramas(documento)
    problemas += _notacao(documento)
    problemas += _figurinas(documento, contexto)
    return problemas


def _lances(elemento: Elemento) -> Iterator[Elemento]:
    return (e for e in elemento.elementos()
            if e is not elemento and e.nome == "span" and "cb-move" in e.classes())


def _san(lance: Elemento) -> str:
    """O lance em SAN inglês: o `data-san`; senão, o texto, com a peça do `cb-piece`."""
    san = (lance.get("data-san") or "").strip()
    if san:
        return san
    peca = next((e.get("data-piece") or "" for e in lance.elementos()
                 if "cb-piece" in e.classes()), "")
    texto = _visivel(lance)
    for figura, letra in FIGURINAS.items():
        texto = texto.replace(figura, letra)
    if peca and texto and not texto[0].isdigit():
        texto = peca + texto[1:]
    return texto.rstrip("!?±∓⩲⩱∞→↑⇆∆⊙+#=-/").strip() or texto


def _visivel(lance: Elemento) -> str:
    """O texto do lance sem o número e sem os NAG."""
    partes = []
    for trecho in lance.trechos():
        nomes = {c for a in (trecho.pai, *trecho.pai.ancestrais()) for c in a.classes()}
        if nomes & {"cb-movenum", "cb-nag"}:
            continue
        partes.append(trecho.texto)
    texto = "".join(partes).strip()
    return texto.lstrip("0123456789.…  ")


def _linhas(documento: Documento) -> list[Problema]:
    problemas = []
    for linha in documento.elementos():
        if linha.nome != "p" or "cb-line" not in linha.classes():
            continue
        anterior: str | None = None
        for lance in _lances(linha):
            fen = lance.get("data-fen")
            depois = ler_fen(fen) if fen else None
            antes = lance.get("data-fen-before") or anterior
            if depois is None:
                anterior = None
                continue
            san = _san(lance)
            tabuleiro = ler_fen(antes) if antes else None
            if tabuleiro is not None and san:
                try:
                    tabuleiro.push_san(san)
                except ValueError:
                    problemas.append(Problema(ILEGAL, documento.local(lance), san))
                else:
                    if tabuleiro.fen() != depois.fen():
                        problemas.append(Problema(FEN_DIVERGENTE, documento.local(lance), san))
            anterior = depois.fen()
    return problemas


def _diagramas(documento: Documento) -> list[Problema]:
    problemas = []
    ultimo: str | None = None
    for elemento in documento.elementos():
        classes = elemento.classes()
        if elemento.nome == "span" and "cb-move" in classes and elemento.get("data-fen"):
            tabuleiro = ler_fen(elemento.get("data-fen") or "")
            if tabuleiro is not None and any(
                    "cb-line" in a.classes() for a in elemento.ancestrais()):
                ultimo = tabuleiro.fen()
        elif elemento.nome == "figure" and "cb-diagram" in classes and ultimo is not None:
            tabuleiro = ler_fen(elemento.get("data-fen") or "")
            if tabuleiro is None:
                continue
            if tabuleiro.fen() != ultimo and \
                    tabuleiro.board_fen() != chess.Board(ultimo).board_fen():
                deixa = chess.Board(ultimo).board_fen()
                problemas.append(Problema(DIAGRAMA, documento.local(elemento),
                                          f"o lance de cima deixa {deixa}"))
    return problemas


def _candidatas(texto: str) -> frozenset[str]:
    """As línguas cujas letras escreveriam este lance (vazio: peão, roque ou figurina)."""
    if not texto or not texto[0].isupper() or texto.startswith("O"):
        return frozenset()
    return frozenset(lingua for lingua, letras in LETRAS_DAS_PECAS.items()
                     if any(texto.startswith(letra) for letra in letras.values()))


def _notacao(documento: Documento) -> list[Problema]:
    sobreviventes: set[str] | None = None
    for lance in documento.elementos():
        if lance.nome != "span" or "cb-move" not in lance.classes():
            continue
        if any("cb-piece" in e.classes() for e in lance.elementos()):
            continue
        candidatas = _candidatas(_visivel(lance))
        if not candidatas:
            continue
        sobreviventes = set(candidatas) if sobreviventes is None else sobreviventes & candidatas
        if not sobreviventes:
            return [Problema(NOTACAO, documento.local(lance),
                             f"«{_visivel(lance)}» não é da língua dos lances de antes")]
    return []


def _familia_das_figurinas(documento: Documento, contexto: Contexto) -> str | None:
    """A primeira família da `font-family` do `.cb-piece` (ou do lance, ou do corpo)."""
    import tinycss2

    melhores: dict[int, str] = {}
    for caminho, texto in folhas_ligadas(documento, contexto):
        for regra_, declaracao in Folha(caminho, texto).declaracoes():
            if regra_ is None or declaracao.type != "declaration" or \
                    declaracao.lower_name != "font-family":
                continue
            seletor = tinycss2.serialize(regra_.prelude)
            prioridade = 0 if "cb-piece" in seletor else 1 if "cb-move" in seletor else \
                2 if seletor.strip() in ("body", "html", ":root") else None
            if prioridade is not None and prioridade not in melhores:
                valor = tinycss2.serialize(declaracao.value)
                melhores[prioridade] = valor.split(",")[0].strip().strip("\"'")
    return melhores[min(melhores)] if melhores else None


def _figurinas(documento: Documento, contexto: Contexto) -> list[Problema]:
    if not contexto.fontes or documento.raiz is None:
        return []
    familia = _familia_das_figurinas(documento, contexto)
    fontes = {k.lower(): v for k, v in contexto.fontes.items()}
    if familia is None or familia.lower() not in fontes:
        return []
    import pymupdf

    origem = fontes[familia.lower()]
    try:
        fonte = pymupdf.Font(fontfile=origem) if "." in origem or "/" in origem or \
            "\\" in origem else pymupdf.Font(fontname=origem)
    except (RuntimeError, ValueError):
        return []
    problemas = []
    vistas: set[str] = set()
    for trecho in documento.raiz.trechos():
        for deslocamento, caractere in enumerate(trecho.texto):
            if caractere in FIGURINAS and caractere not in vistas and \
                    not fonte.has_glyph(ord(caractere)):
                vistas.add(caractere)
                problemas.append(Problema(FIGURINA, documento.local(trecho, deslocamento),
                                          f"{caractere} em {familia}"))
    return problemas
