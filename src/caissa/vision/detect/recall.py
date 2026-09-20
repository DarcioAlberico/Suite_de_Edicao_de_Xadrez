"""Board detection recall recoveries -- now a thin wrapper over the trunk's ``RecallOptions``.

``docs/ASSETS.md`` 1.2 records detection recall as the product's quality bottleneck: a
diagram that is never found can never be classified, and one in twenty was never found.
The three recoveries that take field recall from 0,9478 to 0,9913 -- multi-scale search
**adding** a half-scale pass, the square rescue of a caption-welded contour, and the
checker-contrast floor on embedded images -- were built here (F3) as a *monkeypatch* of two
trunk functions.  ``docs/OCR_UI_ANALISE_C2.md`` 3.3 measured the cost of that: the window
detected without the pack while the suite's import detected with it, and the two in the
same process (the import runs in a thread next to the window's background detection)
stacked ``patched`` over ``patched``.

**OCR_UI cycle 2, step A1 moved the code into the trunk.**  The logic, the constants and
their measurements now live in ``chess_diagram_ocr.board_detection``
(``_extract_candidate_quads``, ``square_anchors``, ``_score_quad``, ``SQUARE_MIN_ELONGATION``),
``detection.hybrid.detect_diagrams`` (the embedded floor) and
``chess_diagram_ocr.config.RecallOptions`` / ``DEFAULT_RECALL``, as an explicit ``recall=``
parameter of ``detect_boards`` and ``detect_diagrams`` that is **on by default**.  Nothing
here swaps a module attribute any more, and the product (``caissa.ingest.pdf.finders``) no
longer imports this module at all: it calls ``detect_diagrams`` and gets the pack.

Measured on ``ChessVisionOFF_Puro/data/field_set.jsonl`` -- 68 hand-annotated pages, 115
diagrams -- with matching by the field set's own rule (IoU >= 0,5 on PDF points):

| variante | recall | precisao |
|---|---|---|
| tronco cru (`recall=None`) | 0,9478 | 0,9732 |
| busca multiescala (somando) | 0,9826 | 0,9741 |
| so resgate de quadrado | 0,9652 | 0,9737 |
| so piso de contraste no embutido | 0,9478 | **1,0000** |
| **os tres juntos (o padrao do tronco)** | **0,9913** | **1,0000** |

What is left here
-----------------
:func:`recall_pack` stays as a context manager because the benchmarks
(``benchmarks/validate_detection.py``, ``profile_detection.py``, ``field_exact.py``) and the
F4 tools drive the trunk's ``field_eval``/``service`` pipeline, which has no ``recall=``
parameter to pass.  It yields the :class:`RecallOptions` it stands for:

* called with the defaults, it only **checks** that the trunk's default is the pack and
  does nothing else -- ``with recall_pack(): detect_diagrams(...)`` is now the same call
  as ``detect_diagrams(...)``;
* called with a *variant* (a switch off, another scale), it is a **benchmark harness**: it
  forces that variant as the ``recall`` argument of the trunk's two entry points for the
  duration, so ``validate_detection.py --variant multiscale`` still measures what the
  table says.  The product never calls it with a variant; the tests pin that the trunk
  comes back exactly as it was.

``multiscale_search`` and ``embedded_checker_floor`` are kept as the same harness with the
same signatures.  The constants and helpers are re-exported from the trunk so nothing that
imported them from here has to change.
"""

from __future__ import annotations

import contextlib
import inspect
from collections.abc import Iterator, Sequence

from caissa.vision.classify.cvoff import ensure_cvoff_on_path

ensure_cvoff_on_path()

from chess_diagram_ocr import board_detection as bd  # noqa: E402
from chess_diagram_ocr.board_detection import SQUARE_MIN_ELONGATION, square_anchors  # noqa: E402
from chess_diagram_ocr.config import DEFAULT_RECALL, RECALL_EM_VIGOR, RecallOptions  # noqa: E402
from chess_diagram_ocr.detection import hybrid  # noqa: E402

__all__ = [
    "DEFAULT_RECALL",
    "EMBEDDED_CHECKER_FLOOR",
    "SEARCH_SCALES",
    "SQUARE_MIN_ELONGATION",
    "RecallOptions",
    "embedded_checker_floor",
    "multiscale_search",
    "recall_pack",
    "square_anchors",
    "trunk_default_is_the_pack",
]

SEARCH_SCALES: tuple[float, ...] = DEFAULT_RECALL.scales
"""The extra search scales of the trunk's default (0,5 -- see ``RecallOptions.scales``)."""

EMBEDDED_CHECKER_FLOOR: float = DEFAULT_RECALL.embedded_floor  # type: ignore[assignment]
"""The embedded-image checker floor of the trunk's default (``RecallOptions.embedded_floor``)."""


def trunk_default_is_the_pack() -> bool:
    """True when the trunk's ``detect_boards`` and ``detect_diagrams`` default to the pack.

    This is what :func:`recall_pack` asserts with no arguments: the recoveries are a
    default parameter, not a patch, so the product gets them by calling the trunk.
    """
    return all(
        inspect.signature(fn).parameters["recall"].default == DEFAULT_RECALL
        for fn in (bd._extract_candidate_quads, bd.detect_boards, hybrid.detect_diagrams)
    ) and RecallOptions() == DEFAULT_RECALL


@contextlib.contextmanager
def _forced(options: RecallOptions | None) -> Iterator[None]:
    """Benchmark harness: make the trunk's two entry points run with ``recall=options``.

    Only :func:`recall_pack` and its two halves call this, and only for a **variant** --
    the product never does. ``field_eval`` has no ``recall=`` parameter, so the variant
    travels by ``chess_diagram_ocr.config.RECALL_EM_VIGOR``, a :class:`contextvars.ContextVar`
    the trunk consults in ``_extract_candidate_quads`` and ``detect_diagrams``: no module
    attribute is swapped, another thread sees nothing, and the token's ``reset`` restores
    the previous state even when the body raises (the tests pin all three).
    """
    token = RECALL_EM_VIGOR.set(options)
    try:
        yield
    finally:
        RECALL_EM_VIGOR.reset(token)


@contextlib.contextmanager
def recall_pack(
    *,
    scales: Sequence[float] = SEARCH_SCALES,
    rescue_squares: bool = True,
    embedded_floor: float | None = EMBEDDED_CHECKER_FLOOR,
) -> Iterator[RecallOptions]:
    """The three recoveries, as the :class:`RecallOptions` they are in the trunk.

    With the defaults this is a no-op that **verifies** the trunk ships the pack as its
    default (:func:`trunk_default_is_the_pack`) and yields ``DEFAULT_RECALL``.  With a
    variant it is the benchmark harness of :func:`_forced` and yields that variant, so the
    body can also pass ``recall=`` explicitly where it has the trunk's function in hand.
    """
    options = RecallOptions(
        scales=tuple(scales), rescue_squares=rescue_squares, embedded_floor=embedded_floor
    )
    if options == DEFAULT_RECALL:
        if not trunk_default_is_the_pack():
            raise RuntimeError(
                "o tronco não liga o pacote de recall por padrão -- "
                "chess_diagram_ocr.config.DEFAULT_RECALL divergiu de RecallOptions()"
            )
        yield options
        return
    with _forced(options):
        yield options


@contextlib.contextmanager
def multiscale_search(
    *,
    scales: Sequence[float] = SEARCH_SCALES,
    rescue_squares: bool = True,
) -> Iterator[RecallOptions]:
    """The contour half of the pack (multi-scale + square rescue), embedded floor off.

    Kept for the benchmarks and the tests with the F3 signature; it is
    ``recall_pack(scales=..., rescue_squares=..., embedded_floor=None)``.
    """
    with recall_pack(scales=scales, rescue_squares=rescue_squares, embedded_floor=None) as options:
        yield options


@contextlib.contextmanager
def embedded_checker_floor(floor: float = EMBEDDED_CHECKER_FLOOR) -> Iterator[RecallOptions]:
    """The embedded half of the pack alone (``scales=()``, ``rescue_squares=False``)."""
    with recall_pack(scales=(), rescue_squares=False, embedded_floor=floor) as options:
        yield options
