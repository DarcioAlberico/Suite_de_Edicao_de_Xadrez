"""Distancia de edicao, sem dependencia externa.

`PGN_Live_Editor/core/candidates.py` importava a extensao C `Levenshtein`. Ela
nao esta declarada no `pyproject.toml` de Caissa e nao ha motivo para declarar:
o que se compara aqui sao tokens de notacao -- **no maximo oito caracteres** --
contra as algumas dezenas de lances legais de uma posicao. A implementacao de
duas linhas de tabela e mais rapida que o custo de uma chamada FFI nesse
tamanho, e mantem `caissa.notation` no conjunto de dependencias `core`
(so `chess`), que e o que faz os testes unitarios rodarem em ambiente magro.

A saida e identica a de `Levenshtein.distance`: substituicao, insercao e
remocao custam 1 cada, sem transposicao (Damerau nao entra -- `Nf3`/`Nc3` e
uma substituicao nos dois modelos, e o acervo nao mostrou troca de digitos
adjacentes como erro tipico de OCR).
"""

from __future__ import annotations

__all__ = ["levenshtein"]


def levenshtein(left: str, right: str) -> int:
    """Numero minimo de insercoes, remocoes e substituicoes de `left` a `right`."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    # Uma linha da matriz por vez: o pico de memoria e `len(right) + 1`.
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[column] + 1,  # remocao
                    current[column - 1] + 1,  # insercao
                    previous[column - 1] + (left_char != right_char),  # substituicao
                )
            )
        previous = current
    return previous[-1]
