"""Board detection -- the three recoveries that take field recall from 0,9478 to 0,9913.

``docs/ASSETS.md`` 1.2 records detection recall as the product's quality bottleneck: a
diagram that is never found can never be classified, and one in twenty was never found.
This module is the fix, and it is an **adapter**, not a rewrite: every gate, every score
and every threshold still belongs to ``chess_diagram_ocr.board_detection``.  What is added
is three ways for a finding that the trunk's guards were right to reject to come back in a
form those same guards accept.

Measured on ``ChessVisionOFF_Puro/data/field_set.jsonl`` -- 68 hand-annotated pages, 115
diagrams, the field measurement of ``docs/quality/CORPUS.md`` 3 -- with matching by the
field set's own rule (IoU >= 0,5 on PDF points, greedy over pairs):

| variante | recall | precisao |
|---|---|---|
| tronco, sem mudanca | 0,9478 | 0,9732 |
| so busca em meia escala (**substituindo**) | **0,9391** | 0,9730 |
| busca multiescala (somando) | 0,9826 | 0,9741 |
| so resgate de quadrado | 0,9652 | 0,9737 |
| so piso de contraste no embutido | 0,9478 | **1,0000** |
| **os tres juntos** | **0,9913** | **1,0000** |

O 0,9913 e 114 de 115: a perda que resta e a anotacao da capa do `Yusupov` (pagina 0), que
nao e diagrama nenhum -- ver `docs/quality/F3_REPORT.md` 3.

Why each one exists
-------------------
**Multiescala (:data:`SEARCH_SCALES`).**  ``INTER_AREA`` a meia escala faz a media da
hachura: uma casa escura desenhada com tracos diagonais vira cinza chapado, e o limiar
adaptativo -- que compara com a media local -- passa a ver uma casa solida em vez de uma
cerca de tracos.  E o unico jeito de o `Niemeijer` fechar contorno.  **Somando, e nao
substituindo:** medido, buscar so a meia escala *perde* seis diagramas do `Reinfeld`, cujo
tabuleiro tem 116 pt e nao sobrevive a reducao.  Os dois regimes precisam um do outro.

**Resgate de quadrado (:func:`square_anchors`).**  Um tabuleiro e quadrado.  Quando o
contorno emenda o diagrama com a legenda embaixo dele -- medido no `Reinfeld`, 356x387 px
onde o tabuleiro mede 356x356 --, as 64 casas saem fora de registro, o contraste de casa da
**exatamente zero** e a guarda da S-143 mata o candidato.  A guarda esta certa sobre o
recorte que ela viu; ela viu o recorte errado.  O resgate oferece o maior quadrado que cabe
dentro do achado, em tres posicoes, e deixa a **mesma** guarda julgar.  Medido nas duas
paginas do `Reinfeld`: o contraste sobe de 0,0000 para 0,2317 e 0,3209.

**Piso de contraste no embutido (:data:`EMBEDDED_CHECKER_FLOOR`).**  E o piso zero da
S-143, aplicado a fonte que nunca o teve.  Nao contradiz a S-12 pela mesma razao que a
S-176 nao contradiz: o PDF declarou uma *imagem* ali, e nunca declarou que ela e um
diagrama.  Medido sobre as 42 imagens embutidas candidatas do conjunto de campo, **6 dao
contraste exatamente 0,0000 e nenhuma delas e diagrama** (as tres fotografias do
`1937 Kemeri` e do `Yusupov`, e tres fragmentos de scan que ja perdiam para o contorno); as
36 restantes vao de 0,0288 para cima.  O corte e em zero, que e onde a comparacao
sinal-contra-ruido troca de sinal, e nao um numero ajustado a amostra.

Como usar
---------
::

    from caissa.vision.detect import recall_pack

    with recall_pack():
        candidates = detect_diagrams(page, page_rgb, max_boards=12)

O gerenciador de contexto e reentrante-seguro no sentido de que desfaz exatamente o que
fez, e nada mais: ele troca duas funcoes do tronco e as devolve no ``finally``.  Nada aqui
escreve no tronco em disco.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator, Sequence

import cv2
import numpy as np

from caissa.vision.classify.cvoff import ensure_cvoff_on_path

ensure_cvoff_on_path()

from chess_diagram_ocr import board_detection as bd  # noqa: E402

__all__ = [
    "EMBEDDED_CHECKER_FLOOR",
    "SEARCH_SCALES",
    "SQUARE_MIN_ELONGATION",
    "embedded_checker_floor",
    "multiscale_search",
    "recall_pack",
    "square_anchors",
]

Quad = np.ndarray
Candidate = tuple[Quad, float, tuple[int, int, int, int]]
_Scored = tuple[Quad, float, tuple[int, int, int, int], float]


SEARCH_SCALES: tuple[float, ...] = (0.5,)
"""As escalas extras em que a busca de contorno roda, alem da escala 1,0.

**0,5 e nao 0,66 nem 0,35.** Medidas no conjunto de campo, somando uma escala so:
0,66 da recall 0,9739, 0,35 da 0,9739 e 0,5 da **0,9826** -- as tres com precisao
essencialmente igual (0,9739 / 0,9739 / 0,9741). Acrescentar 0,35 **junto** com 0,5 nao
muda nem recall nem precisao (0,9913 / 1,0000 nas duas), entao ela sai: passe que nao muda
numero nenhum e custo puro.

O motivo de 0,5 ganhar e o passo da hachura. A 220 DPI os tracos do `Niemeijer` distam
poucos pixels; reduzir pela metade com ``INTER_AREA`` os funde num cinza uniforme. A 0,66 a
reducao nao basta para fundir, e a 0,35 o tabuleiro de 116 pt do `Reinfeld` ja e pequeno
demais para o piso de area -- mas isso nao custa recall porque a escala 1,0 continua ali.
"""

SQUARE_MIN_ELONGATION = 1.02
"""Alongamento a partir do qual vale tentar o resgate de quadrado.

Abaixo disto o maior quadrado que cabe no achado **e** o proprio achado, e o resgate
devolveria o mesmo recorte que a guarda acabou de recusar -- custo sem chance de ganho. Os
dois casos medidos do `Reinfeld` estao em 1,087 e 1,090: nove por cento de legenda a mais
no eixo vertical.
"""

EMBEDDED_CHECKER_FLOOR = 0.0
"""Piso de contraste de casa para uma **imagem embutida** ser candidata a diagrama.

O mesmo numero e o mesmo argumento da ``board_detection.MIN_CHECKER_CONTRAST``, aplicado a
outra fonte. Ver o cabecalho deste modulo para a medicao que o separa.
"""


def _score_quad(image_rgb: np.ndarray, quad: Quad, image_area: float) -> tuple[float, float] | None:
    """``(score, contraste)`` do quad, pelos **medidores do tronco**, ou ``None``.

    ``None`` quando uma guarda do tronco -- geometria, aspecto, fora-da-pagina -- ja diz
    que este quad nao e candidato. A conta do score e a mesma de
    ``_extract_candidate_quads``: ``geometria x (0,55 + 0,45 x textura)``. Estar aqui e nao
    la e o preco de nao editar o tronco; que seja a **mesma** conta e o que impede os dois
    caminhos de divergirem em silencio, e e o que
    ``tests/unit/detect/test_recall_pack.py`` verifica candidato a candidato.
    """
    geom = bd._contour_geometry_score(quad, image_area)
    if geom <= 0:
        return None
    bbox = bd._bbox_from_quad(quad)
    if (
        bd._bbox_visible_ratio(bbox, image_rgb.shape) < bd.MIN_VISIBLE_RATIO
        or bd._quad_point_inside_ratio(quad, image_rgb.shape) < bd.MIN_QUAD_INSIDE_RATIO
    ):
        return None
    small = bd._small_gray(bd.warp_from_quad(image_rgb, quad, target_size=320))
    checker = bd._checker_score(small)
    pattern = bd._texture_from_parts(checker, bd._grid_score(small))
    return float(geom * (0.55 + 0.45 * pattern)), float(checker)


def square_anchors(bbox: tuple[int, int, int, int]) -> list[Quad]:
    """O maior quadrado que cabe na caixa, em tres posicoes: inicio, fim e meio.

    Tres e nao cinco: o quadrado so desliza no eixo **longo** da caixa, entao os quatro
    cantos sao dois a dois o mesmo recorte. Numa caixa 356x387 os tres sao "encostado no
    topo", "encostado na base" e "centrado" -- e e o primeiro que acerta o `Reinfeld`,
    porque a legenda esta embaixo do tabuleiro.

    Args:
        bbox: ``(x, y, largura, altura)`` em pixels da pagina.

    Returns:
        Tres quads de 4 pontos, em ``float32``, na convencao de ``warp_from_quad``.
    """
    x, y, width, height = bbox
    side = float(min(width, height))
    slack_x = float(width) - side
    slack_y = float(height) - side
    quads: list[Quad] = []
    for ox, oy in ((0.0, 0.0), (slack_x, slack_y), (slack_x / 2.0, slack_y / 2.0)):
        ax, ay = float(x) + ox, float(y) + oy
        quads.append(
            np.array(
                [[ax, ay], [ax + side, ay], [ax + side, ay + side], [ax, ay + side]],
                dtype=np.float32,
            )
        )
    return quads


def _pool_finish(pooled: list[_Scored]) -> list[Candidate]:
    """A deduplicacao e o corte de area relativa do tronco, sobre a lista somada.

    Sao as duas unicas etapas de ``_extract_candidate_quads`` que olham a lista inteira e
    nao um candidato por vez, e por isso sao as duas que precisam rodar **depois** de as
    fontes extras entrarem. Os dois limiares continuam sendo os do tronco
    (``DEDUPE_IOU``, ``MIN_RELATIVE_AREA``); nada aqui e um numero novo.
    """
    if not pooled:
        return []
    pooled.sort(key=lambda item: item[1], reverse=True)
    kept: list[_Scored] = []
    for candidate in pooled:
        if any(bd._bbox_iou(candidate[2], other[2]) > bd.DEDUPE_IOU for other in kept):
            continue
        kept.append(candidate)
    largest = max(item[3] for item in kept)
    floor = largest * bd.MIN_RELATIVE_AREA
    out = [item[:3] for item in kept if item[3] >= floor]
    out.sort(key=lambda item: item[1], reverse=True)
    return out


@contextlib.contextmanager
def multiscale_search(
    *,
    scales: Sequence[float] = SEARCH_SCALES,
    rescue_squares: bool = True,
) -> Iterator[None]:
    """Soma a busca em escala reduzida e o resgate de quadrado a ``_extract_candidate_quads``.

    O caminho de escala 1,0 e o do tronco, chamado sem alteracao nenhuma -- inclusive a
    lista ``rejected``, que continua saindo com os mesmos motivos. O que muda e que a lista
    devolvida passa a incluir tambem:

    * os achados da mesma funcao rodando sobre a pagina reduzida, com o quad multiplicado de
      volta e **repontuado na resolucao cheia** (senao dois candidatos da mesma pagina
      teriam sido medidos em imagens diferentes e o score nao os ordenaria);
    * o resgate de quadrado sobre cada recusa por ``sem-contraste-de-casa``.

    Um achado da escala reduzida que ja duplica um achado da escala cheia (IoU acima de
    ``DEDUPE_IOU``) e descartado **antes** de ser repontuado: a deduplicacao ficaria com o
    da escala cheia de qualquer jeito -- ele tem a geometria mais fina -- e o warp de
    320x320 do repontuamento e a parte cara. Medido, e o que mantem o custo do passe extra
    perto do custo teorico dele.

    Args:
        scales: Escalas extras de busca. Vazio desliga o passe multiescala.
        rescue_squares: Liga o resgate de quadrado das recusas por contraste zero.
    """
    original = bd._extract_candidate_quads

    def patched(
        image_rgb: np.ndarray,
        rejected: list[Any] | None = None,
        checker_floor: float | None = bd.MIN_CHECKER_CONTRAST,
    ) -> list[Candidate]:
        image_area = float(image_rgb.shape[0] * image_rgb.shape[1])
        local: list[Any] = []
        pooled: list[_Scored] = [
            (quad, score, bbox, float(cv2.contourArea(quad)))
            for quad, score, bbox in original(image_rgb, local, checker_floor)
        ]
        if rejected is not None:
            rejected.extend(local)

        height, width = image_rgb.shape[:2]
        for scale in scales:
            if scale <= 0.0 or scale >= 1.0:
                raise ValueError(f"escala de busca deve estar em (0, 1); recebida {scale!r}")
            smaller = cv2.resize(
                image_rgb,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
            for quad, _, _ in original(smaller, None, checker_floor):
                back = np.asarray(quad, dtype=np.float32) / scale
                bbox = bd._bbox_from_quad(back)
                if any(bd._bbox_iou(bbox, other[2]) > bd.DEDUPE_IOU for other in pooled):
                    continue
                measured = _score_quad(image_rgb, back, image_area)
                if measured is None:
                    continue
                score, checker = measured
                if checker_floor is not None and checker <= checker_floor:
                    continue
                pooled.append((back, score, bbox, float(cv2.contourArea(back))))

        if rescue_squares:
            for item in local:
                if item.reason != "sem-contraste-de-casa":
                    continue
                _, _, box_w, box_h = item.bbox
                shorter = min(box_w, box_h)
                if shorter <= 0 or max(box_w, box_h) / shorter < SQUARE_MIN_ELONGATION:
                    continue
                for quad in square_anchors(item.bbox):
                    measured = _score_quad(image_rgb, quad, image_area)
                    if measured is None:
                        continue
                    score, checker = measured
                    if checker_floor is not None and checker <= checker_floor:
                        continue
                    pooled.append((quad, score, bd._bbox_from_quad(quad), float(cv2.contourArea(quad))))

        return _pool_finish(pooled)

    bd._extract_candidate_quads = patched  # type: ignore[assignment]
    try:
        yield
    finally:
        bd._extract_candidate_quads = original  # type: ignore[assignment]


@contextlib.contextmanager
def embedded_checker_floor(floor: float = EMBEDDED_CHECKER_FLOOR) -> Iterator[None]:
    """Recusa imagem embutida sem contraste de casa nenhum, antes de ela virar candidata.

    Roda em ``candidates_from_embedded_images`` e nao sobre o que ``detect_diagrams``
    devolve, pela mesma razao que a S-160 moveu o piso da S-143 para dentro do
    ``detect_boards``: a guarda que julga **o que a coisa e** vem antes da guarda que julga
    **com quem ela compete**. Uma fotografia que sobrevive ate a disputa pode vencer por
    tamanho e suprimir por IoU o diagrama de verdade da mesma pagina.
    """
    from chess_diagram_ocr.detection import hybrid
    from chess_diagram_ocr.detection.hybrid import board_checker_contrast

    original = hybrid.candidates_from_embedded_images

    def patched(page: Any) -> list[Any]:
        return [c for c in original(page) if board_checker_contrast(c.board_rgb) > floor]

    hybrid.candidates_from_embedded_images = patched  # type: ignore[assignment]
    try:
        yield
    finally:
        hybrid.candidates_from_embedded_images = original  # type: ignore[assignment]


@contextlib.contextmanager
def recall_pack(
    *,
    scales: Sequence[float] = SEARCH_SCALES,
    rescue_squares: bool = True,
    embedded_floor: float | None = EMBEDDED_CHECKER_FLOOR,
) -> Iterator[None]:
    """As tres recuperacoes juntas. E o que `docs/quality/F3_REPORT.md` mede como `full-pack`.

    Cada parte tem um interruptor proprio porque cada parte foi medida sozinha: um numero de
    conjunto que ninguem consegue decompor nao serve para decidir nada, e o
    ``CRITIC_CHARTER`` remede.
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(multiscale_search(scales=scales, rescue_squares=rescue_squares))
        if embedded_floor is not None:
            stack.enter_context(embedded_checker_floor(embedded_floor))
        yield
