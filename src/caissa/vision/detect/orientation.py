"""Which way up is the diagram?

Origem: Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/orientation.py (heurística
de plausibilidade) e .../pdf_service.py (localização das coordenadas impressas
em volta do diagrama).
Absorvido em 2026-09-07.  Alterações: a heurística ficou intacta no essencial,
mas passou a devolver evidência estruturada; a busca por coordenadas deixou de
servir ao apagamento e passou a **ler** a ordem das letras e dos números, que é
o sinal decisivo e que o projeto de origem não usava.

Two sources, in this order
--------------------------
1. **Printed coordinates.**  A book diagram almost always prints ``a``-``h``
   under the board and ``1``-``8`` beside it.  Their *order* settles the
   question outright: ``a`` on the left and ``1`` at the bottom is White at the
   bottom; the reverse is a board seen from Black's side.  This is evidence,
   not inference.
2. **Plausibility of the position.**  With no coordinates, score the four
   rotations.  Pawns are the signal that separates 0 deg from 180 deg, because
   a legal position stays legal when you turn it upside down -- everything else
   is merely eliminatory.

The heuristic is deliberately pure: it touches no PDF, no OpenCV and no torch,
so it works in any installation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Sequence

__all__ = [
    "AMBIGUOUS_MARGIN",
    "MIN_LABELS_IN_A_ROW",
    "OrientationSource",
    "BoardOrientation",
    "OrientationCandidate",
    "CoordinateLabel",
    "plausibility",
    "rank_orientations",
    "auto_orient",
    "orientation_from_labels",
    "rotate_placement",
    "unknown_orientation",
    "rotate_matrix_clockwise",
    "matrix_from_placement",
    "placement_from_matrix",
]

OrientationSource = Literal["labels", "heuristic", "unknown"]

#: Score gap below which the heuristic's choice is not trustworthy.
#: Origem: Editor .../orientation.py (AMBIGUOUS_MARGIN).
AMBIGUOUS_MARGIN: Final = 0.75

_FILES: Final = "abcdefgh"
_RANKS: Final = "12345678"

#: A row of coordinates needs this many labels before it is believed.  A single
#: stray letter under a diagram is a caption word, not a coordinate -- in
#: Portuguese ``a`` and ``e`` are whole words, and "brancas jogam **e** ganham"
#: sits exactly where the coordinate row sits.  Origem: pdf_service.py.
MIN_LABELS_IN_A_ROW: Final = 4

#: Width of the band searched around the board, as a fraction of its side.
COORDINATE_RING_RATIO: Final = 0.10
COORDINATE_RING_MIN_PT: Final = 9.0
COORDINATE_RING_MAX_PT: Final = 30.0

#: ``(text, x0, y0, x1, y1)`` for one short text found near the board, in a
#: space where y grows downwards -- which is what PyMuPDF hands back.
CoordinateLabel = tuple[str, float, float, float, float]


@dataclass(frozen=True, slots=True)
class BoardOrientation:
    """How the board is turned, and why we think so."""

    #: Quarter turns clockwise to apply to the printed diagram to bring rank 1
    #: to the bottom and file ``a`` to the left.  0 means it is already upright.
    rotation_cw: int
    #: True when rank 1 is at the bottom of the printed diagram.
    white_at_bottom: bool
    #: True when file ``a`` is on the left of the printed diagram.
    files_left_to_right: bool
    source: OrientationSource
    confidence: float
    evidence: tuple[str, ...] = ()

    @property
    def upright(self) -> bool:
        """Is the diagram printed the usual way round?"""
        return self.white_at_bottom and self.files_left_to_right

    @property
    def mirrored(self) -> bool:
        """Files and ranks disagree: the diagram is a mirror, not a rotation."""
        return self.white_at_bottom != self.files_left_to_right


@dataclass(frozen=True, slots=True)
class OrientationCandidate:
    """One of the four rotations of a position, with its score."""

    piece_placement: str
    #: Degrees clockwise applied to the original position.
    rotation: int
    score: float
    reasons: tuple[str, ...]


# --------------------------------------------------------------------------
# Board matrix helpers (kept local so this module depends on nothing)
# --------------------------------------------------------------------------


def matrix_from_placement(piece_placement: str) -> list[list[str]]:
    """8x8 matrix from the piece-placement field of a FEN; ``.`` is empty."""
    matrix: list[list[str]] = []
    for row in piece_placement.split("/"):
        cells: list[str] = []
        for ch in row:
            if ch.isdigit():
                cells.extend("." * int(ch))
            else:
                cells.append(ch)
        if len(cells) != 8:
            raise ValueError(f"linha inválida no FEN: {row!r}")
        matrix.append(cells)
    if len(matrix) != 8:
        raise ValueError("o campo de posição precisa ter 8 linhas")
    return matrix


def placement_from_matrix(matrix: Sequence[Sequence[str]]) -> str:
    """Piece-placement field of a FEN from an 8x8 matrix."""
    rows: list[str] = []
    for row in matrix:
        out: list[str] = []
        run = 0
        for cell in row:
            if cell == ".":
                run += 1
                continue
            if run:
                out.append(str(run))
                run = 0
            out.append(cell)
        if run:
            out.append(str(run))
        rows.append("".join(out))
    return "/".join(rows)


def rotate_placement(piece_placement: str) -> str:
    """The same position seen from the other side of the board.

    A diagram printed from Black's point of view has its pieces drawn
    upright and rank 1 at the top: a reader that takes the top row for rank
    8 gets every square mirrored through the centre.  What has to turn is
    the **placement**, never the pixels (rotating the image would put the
    pieces on their heads) -- OCR_UI_ROADMAP_C2 passo C10.  Rows reversed
    and each row reversed; a run of empties is one digit, so reversing the
    characters of a row is exact (``3p4`` → ``4p3``).
    """
    rows = piece_placement.split("/")
    return "/".join(row[::-1] for row in reversed(rows))


def rotate_matrix_clockwise(matrix: Sequence[Sequence[str]]) -> list[list[str]]:
    """Turn the board a quarter turn clockwise."""
    return [list(row) for row in zip(*matrix[::-1])]


def _rank_of_row(row: int) -> int:
    """Row 0 of the matrix is the 8th rank."""
    return 8 - row


# --------------------------------------------------------------------------
# 1. Printed coordinates
# --------------------------------------------------------------------------


def _monotonic(values: Sequence[int]) -> int:
    """+1 if strictly increasing, -1 if strictly decreasing, 0 otherwise."""
    if len(values) < 2:
        return 0
    ups = sum(1 for a, b in zip(values, values[1:]) if b > a)
    downs = sum(1 for a, b in zip(values, values[1:]) if b < a)
    if ups and not downs:
        return 1
    if downs and not ups:
        return -1
    return 0


def _split_run(token: str, sequence: str) -> list[str] | None:
    """A contiguous, in-order slice of ``sequence``, split into characters.

    The coordinate row very often reaches the extractor as one text run --
    ``abcdefgh`` in a single span -- so a multi-character token has to be
    accepted.  Requiring it to be a contiguous slice of the sequence (forwards
    or backwards) is what separates ``cdef`` from ``faced``: both use only
    ``a``-``h``, only one is part of the run.
    Origem: pdf_service._coordinate_run_kind.
    """
    lowered = token.lower()
    if len(lowered) < 2:
        return None
    if lowered in sequence or lowered in sequence[::-1]:
        return list(lowered)
    return None


def _spread(chars: Sequence[str], low: float, high: float) -> list[tuple[str, float]]:
    """Place each character of a run evenly across the box the run occupies."""
    n = len(chars)
    if n == 1:
        return [(chars[0], (low + high) / 2.0)]
    span = high - low
    return [(c, low + span * (i + 0.5) / n) for i, c in enumerate(chars)]


def orientation_from_labels(
    labels: Sequence[CoordinateLabel],
    board: tuple[float, float, float, float],
) -> BoardOrientation | None:
    """Read the orientation off the coordinates printed around the board.

    Returns ``None`` when there is no row of coordinates to read.  That is not
    a failure, only an absence of evidence -- the caller then falls back to
    :func:`auto_orient`.
    """
    bx0, by0, bx1, by1 = board
    side = max(bx1 - bx0, by1 - by0)
    if side <= 0:
        return None
    ring = min(COORDINATE_RING_MAX_PT, max(COORDINATE_RING_MIN_PT, side * COORDINATE_RING_RATIO))

    files_below: list[tuple[str, float]] = []
    files_above: list[tuple[str, float]] = []
    ranks_left: list[tuple[str, float]] = []
    ranks_right: list[tuple[str, float]] = []

    for text, x0, y0, x1, y1 in labels:
        token = text.strip()
        if not token:
            continue
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        if not (bx0 - ring <= cx <= bx1 + ring and by0 - ring <= cy <= by1 + ring):
            continue
        # "Outside the board" is judged by the centre, not by an empty
        # intersection: the coordinate row touches the border and its word box
        # bites 1 or 2 pt into the detected rectangle.  Origem: pdf_service.py.
        if bx0 < cx < bx1 and by0 < cy < by1:
            continue

        if len(token) == 1:
            chars = [token.lower()]
        else:
            run = _split_run(token, _FILES) or _split_run(token, _RANKS)
            if run is None:
                continue
            chars = run

        if all(c in _FILES for c in chars) and bx0 - ring <= cx <= bx1 + ring:
            target = files_below if cy > by1 else (files_above if cy < by0 else None)
            if target is not None:
                target.extend(_spread(chars, x0, x1))
        elif all(c in _RANKS for c in chars) and by0 - ring <= cy <= by1 + ring:
            column = ranks_right if cx > bx1 else (ranks_left if cx < bx0 else None)
            if column is not None:
                column.extend(_spread(chars, y0, y1))

    evidence: list[str] = []

    files_dir = 0
    for where, row in (("abaixo", files_below), ("acima", files_above)):
        if len(row) < MIN_LABELS_IN_A_ROW:
            continue
        row.sort(key=lambda item: item[1])
        direction = _monotonic([_FILES.index(c) for c, _ in row])
        if direction:
            files_dir = direction
            evidence.append(
                f"coordenadas a-h {where} do tabuleiro, "
                f"{'da esquerda para a direita' if direction > 0 else 'da direita para a esquerda'}"
            )
            break

    ranks_dir = 0
    for where, column in (("à esquerda", ranks_left), ("à direita", ranks_right)):
        if len(column) < MIN_LABELS_IN_A_ROW:
            continue
        column.sort(key=lambda item: item[1])
        direction = _monotonic([_RANKS.index(c) for c, _ in column])
        if direction:
            # y grows downwards, so ranks printed 8 down to 1 decrease.
            ranks_dir = -direction
            evidence.append(
                f"coordenadas 1-8 {where}, {'8 em cima' if direction < 0 else '1 em cima'}"
            )
            break

    if not files_dir and not ranks_dir:
        return None

    white_at_bottom = ranks_dir > 0 if ranks_dir else files_dir > 0
    files_left_to_right = files_dir > 0 if files_dir else white_at_bottom
    confidence = 0.99 if (files_dir and ranks_dir) else 0.90
    if files_dir and ranks_dir and (files_dir > 0) != (ranks_dir > 0):
        # Letters and numbers disagree: a mirrored diagram, or a misread.  Say
        # so instead of picking one and pretending it was certain.
        confidence = 0.55
        evidence.append("letras e números discordam entre si")
    rotation = 0 if white_at_bottom else 180
    return BoardOrientation(
        rotation_cw=rotation,
        white_at_bottom=white_at_bottom,
        files_left_to_right=files_left_to_right,
        source="labels",
        confidence=confidence,
        evidence=tuple(evidence),
    )


# --------------------------------------------------------------------------
# 2. Plausibility of the position
# --------------------------------------------------------------------------


def plausibility(piece_placement: str) -> tuple[float, tuple[str, ...]]:
    """How plausible is this position as an upright diagram?  Higher is better.

    Origem: Editor .../orientation.py, sem mudança de critério.  Todos os testes
    são independentes do lado a jogar, porque um diagrama de livro não carrega
    essa informação.
    """
    matrix = matrix_from_placement(piece_placement)
    flat = [cell for row in matrix for cell in row]
    reasons: list[str] = []
    score = 0.0

    white_kings = flat.count("K")
    black_kings = flat.count("k")
    if white_kings == 1 and black_kings == 1:
        score += 3.0
    else:
        # Turning the board neither creates nor destroys a king, so this almost
        # never breaks a tie between rotations -- but it keeps the score honest
        # when the reading itself came out broken.
        score -= 3.0 * (abs(white_kings - 1) + abs(black_kings - 1))
        reasons.append(f"reis: {white_kings} branco(s), {black_kings} preto(s)")

    backrank_pawns = sum(1 for row in (0, 7) for cell in matrix[row] if cell in ("P", "p"))
    if backrank_pawns:
        score -= 2.0 * backrank_pawns
        reasons.append(f"{backrank_pawns} peão(ões) na 1ª/8ª fila")

    white_ranks = [_rank_of_row(r) for r in range(8) for c in range(8) if matrix[r][c] == "P"]
    black_ranks = [_rank_of_row(r) for r in range(8) for c in range(8) if matrix[r][c] == "p"]
    if white_ranks and black_ranks:
        gap = sum(black_ranks) / len(black_ranks) - sum(white_ranks) / len(white_ranks)
        score += max(-4.0, min(4.0, gap)) * 0.75
        if gap < 0:
            reasons.append(f"peões apontam o sentido oposto ({gap:+.1f} filas)")
    else:
        # With no pawn of one colour the strongest signal has nothing to say.
        # Inventing a number would be worse than admitting it: the ambiguity
        # stays visible in the margin.
        reasons.append("sem peões dos dois lados: sentido indeterminado")

    for label, pawn, pieces in (("brancas", "P", "PNBRQK"), ("pretas", "p", "pnbrqk")):
        pawn_count = flat.count(pawn)
        piece_count = sum(flat.count(ch) for ch in pieces)
        if pawn_count > 8:
            score -= 2.0 * (pawn_count - 8)
            reasons.append(f"peões {label} demais ({pawn_count})")
        if piece_count > 16:
            score -= 2.0 * (piece_count - 16)
            reasons.append(f"peças {label} demais ({piece_count})")

    return score, tuple(reasons)


def rank_orientations(piece_placement: str) -> list[OrientationCandidate]:
    """The four rotations, most plausible first."""
    matrix = matrix_from_placement(piece_placement)
    candidates: list[OrientationCandidate] = []
    for rotation in (0, 90, 180, 270):
        placement = placement_from_matrix(matrix)
        score, reasons = plausibility(placement)
        candidates.append(
            OrientationCandidate(
                piece_placement=placement, rotation=rotation, score=score, reasons=reasons
            )
        )
        matrix = rotate_matrix_clockwise(matrix)
    # `sorted` is stable, so a tie keeps 0 -> 90 -> 180 -> 270: not turning wins
    # over turning when nothing tells them apart.  Least surprising behaviour.
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def auto_orient(piece_placement: str) -> BoardOrientation:
    """Fall back to the position itself when no coordinates were printed."""
    ranked = rank_orientations(piece_placement)
    best, runner_up = ranked[0], ranked[1]
    margin = best.score - runner_up.score
    ambiguous = margin < AMBIGUOUS_MARGIN
    evidence = (f"rotação mais plausível: {best.rotation}° (margem {margin:+.2f})",) + best.reasons
    return BoardOrientation(
        rotation_cw=best.rotation,
        white_at_bottom=best.rotation == 0,
        files_left_to_right=best.rotation == 0,
        source="heuristic",
        confidence=0.45 if ambiguous else 0.75,
        evidence=evidence,
    )


def unknown_orientation() -> BoardOrientation:
    """No evidence either way: assume the usual, and say the confidence is low."""
    return BoardOrientation(
        rotation_cw=0,
        white_at_bottom=True,
        files_left_to_right=True,
        source="unknown",
        confidence=0.30,
        evidence=("sem coordenadas impressas e sem sinal na posição",),
    )
