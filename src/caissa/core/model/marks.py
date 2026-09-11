"""Board annotations: arrows, highlighted squares, circles and labels.

Shared by :class:`~caissa.core.model.diagram.Diagram` (SPEC section 5.3,
"marcas") and by :class:`~caissa.core.model.game.MoveNode`, which carries the
``[%cal]`` and ``[%csl]`` PGN commands (SPEC section 5.4). One type serves both
so that "the arrows drawn on the diagram" and "the arrows the annotator wrote
into the game score" are the same kind of thing, and a diagram generated from a
move inherits its marks without translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from caissa.core.model.props import Color, Measure
from caissa.core.model.registry import ir_node

__all__ = [
    "SQUARE_NAMES",
    "Mark",
    "MarkKind",
    "MarkLineStyle",
    "arrow",
    "circle",
    "highlight",
    "is_square_name",
    "square_index",
    "square_name",
]

#: Algebraic square names, ``a1`` first, indexed the way FEN ranks are read.
SQUARE_NAMES: Final[tuple[str, ...]] = tuple(
    f"{file_char}{rank}" for rank in range(1, 9) for file_char in "abcdefgh"
)

_SQUARE_RE: Final = re.compile(r"^[a-h][1-8]$")
_SQUARE_TO_INDEX: Final[dict[str, int]] = {name: index for index, name in enumerate(SQUARE_NAMES)}

#: Squares on a chessboard.
_SQUARE_COUNT: Final = 64


def is_square_name(text: str) -> bool:
    """Report whether ``text`` is a valid algebraic square name.

    Args:
        text: Candidate square name.

    Returns:
        ``True`` for ``a1`` through ``h8``.
    """
    return bool(_SQUARE_RE.match(text))


def square_index(name: str) -> int:
    """Return the ``0``-``63`` index of a square, ``a1`` being ``0``.

    Args:
        name: An algebraic square name.

    Returns:
        The index, counting files within ranks from ``a1``.

    Raises:
        ValueError: If the name is not a valid square.
    """
    try:
        return _SQUARE_TO_INDEX[name]
    except KeyError as exc:
        msg = f"casa invalida: {name!r}"
        raise ValueError(msg) from exc


def square_name(index: int) -> str:
    """Return the algebraic name of a square index.

    Args:
        index: A value in ``[0, 64)``, ``0`` being ``a1``.

    Returns:
        The algebraic square name.

    Raises:
        ValueError: If the index is out of range.
    """
    if not 0 <= index < _SQUARE_COUNT:
        msg = f"indice de casa fora da faixa: {index}"
        raise ValueError(msg)
    return SQUARE_NAMES[index]


class MarkKind(StrEnum):
    """What a mark draws.

    ``ARROW`` needs exactly two squares; ``SQUARE``, ``CIRCLE``, ``CROSS`` and
    ``DOT`` need at least one; ``LABEL`` needs exactly one and a ``text``.
    :func:`caissa.core.model.validate.validate` enforces the arity.
    """

    ARROW = "arrow"
    SQUARE = "square"
    CIRCLE = "circle"
    CROSS = "cross"
    DOT = "dot"
    LABEL = "label"


class MarkLineStyle(StrEnum):
    """Stroke pattern of a mark."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DOUBLE = "double"


@ir_node("mark")
@dataclass(frozen=True, slots=True, kw_only=True)
class Mark:
    """One annotation drawn on a board.

    Attributes:
        kind: What to draw.
        squares: The squares involved, in drawing order. An arrow reads
            ``(origin, target)``.
        color: Stroke or fill colour. ``None`` means the diagram style's default
            for this kind.
        line_style: Stroke pattern.
        width: Stroke width; ``None`` means the style default, which scales with
            the square size.
        opacity: Opacity in ``[0, 1]``.
        text: Label content, required for ``MarkKind.LABEL``.
        layer: Paint order; higher numbers are drawn later, so an arrow can be
            put above or below a highlight deliberately.
        filled: Whether ``CIRCLE`` and ``SQUARE`` are painted solid rather than
            outlined.
    """

    kind: MarkKind
    squares: tuple[str, ...] = ()
    color: Color | None = None
    line_style: MarkLineStyle = MarkLineStyle.SOLID
    width: Measure | None = None
    opacity: float | None = None
    text: str | None = None
    layer: int = 0
    filled: bool = False

    @property
    def origin(self) -> str | None:
        """First square, or ``None`` when the mark names no squares."""
        return self.squares[0] if self.squares else None

    @property
    def target(self) -> str | None:
        """Last square, which for an arrow is where the head points."""
        return self.squares[-1] if self.squares else None


def arrow(origin: str, target: str, *, color: Color | None = None) -> Mark:
    """Build an arrow mark, the ``[%cal]`` primitive.

    Args:
        origin: Square the arrow starts from.
        target: Square the arrow points at.
        color: Stroke colour.

    Returns:
        The mark.
    """
    return Mark(kind=MarkKind.ARROW, squares=(origin, target), color=color)


def highlight(*squares: str, color: Color | None = None) -> Mark:
    """Build a highlighted-square mark, the ``[%csl]`` primitive.

    Args:
        *squares: One or more squares to highlight.
        color: Fill colour.

    Returns:
        The mark.
    """
    return Mark(kind=MarkKind.SQUARE, squares=tuple(squares), color=color, filled=True)


def circle(*squares: str, color: Color | None = None) -> Mark:
    """Build a circled-square mark.

    Args:
        *squares: One or more squares to circle.
        color: Stroke colour.

    Returns:
        The mark.
    """
    return Mark(kind=MarkKind.CIRCLE, squares=tuple(squares), color=color)
