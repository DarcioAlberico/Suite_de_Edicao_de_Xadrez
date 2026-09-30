"""The three recall recoveries, seen from the suite: the trunk's default and the harness.

Since OCR_UI cycle 2 step A1 the recoveries live in the trunk (``RecallOptions``, on by
default) and ``caissa.vision.detect.recall`` is a wrapper: ``recall_pack()`` with the
defaults only checks that the trunk ships the pack, and with a *variant* it is the benchmark
harness that forces that variant on the trunk's two entry points.  What is pinned here:

* the trunk's default **is** the pack, so the product gets it by calling ``detect_diagrams``;
* the harness puts the trunk back exactly as it was, even when the body raises;
* the recoveries still do what they were built for (the trunk's own tests cover them
  candidate by candidate in ``tests/test_board_detection_recall.py``; here the synthetic
  pages assert the pair once more through the suite's names: raw finds nothing, the pack
  finds the board where it is).

The corpus regressions at the end pin the measured numbers themselves.  They skip when
``ChessVisionOFF_Puro`` is not on the machine; the synthetic ones never skip.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from caissa.vision.classify.cvoff import ensure_cvoff_on_path  # noqa: E402

try:
    CVOFF_ROOT: Path | None = ensure_cvoff_on_path()
except FileNotFoundError:  # pragma: no cover - only on a machine without the trunk
    CVOFF_ROOT = None

pytestmark = pytest.mark.skipif(CVOFF_ROOT is None, reason="tronco ChessVisionOFF_Puro ausente")

if CVOFF_ROOT is not None:
    from chess_diagram_ocr import board_detection as bd
    from chess_diagram_ocr.board_detection import _score_quad
    from chess_diagram_ocr.config import DEFAULT_RECALL, RecallOptions

    from caissa.vision.detect.recall import (
        SQUARE_MIN_ELONGATION,
        embedded_checker_floor,
        multiscale_search,
        recall_pack,
        square_anchors,
        trunk_default_is_the_pack,
    )

    RAW = None
    NO_EMBEDDED_FLOOR = RecallOptions(embedded_floor=None)

CORPUS = CVOFF_ROOT / "PDF" if CVOFF_ROOT is not None else None
needs_corpus = pytest.mark.skipif(
    CORPUS is None or not CORPUS.is_dir(), reason="acervo de PDFs ausente"
)


# --------------------------------------------------------------------------
# Synthetic pages
# --------------------------------------------------------------------------


def board_page(
    *,
    side: int = 320,
    origin: tuple[int, int] = (90, 80),
    page: tuple[int, int] = (520, 720),
    caption_height: int = 0,
    hatch_step: int = 0,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """A white page with one 8x8 board on it, plus the defect asked for.

    ``caption_height`` welds a black bar to the bottom edge of the board, which is what a
    bold exercise number does to the contour in the ``Reinfeld``.  ``hatch_step`` draws the
    dark squares as diagonal strokes instead of solid ink, which is the ``Niemeijer``.

    Returns the page and the board's true ``(x, y, w, h)``.
    """
    image = np.full((page[1], page[0], 3), 255, np.uint8)
    x0, y0 = origin
    cell = side // 8
    for row in range(8):
        for col in range(8):
            if (row + col) % 2 == 0:
                continue
            x, y = x0 + col * cell, y0 + row * cell
            if hatch_step:
                for offset in range(0, cell, hatch_step):
                    cv2.line(image, (x, y + offset), (x + cell - 1 - offset, y + cell - 1), (50, 50, 50), 1)
                    cv2.line(image, (x + offset, y), (x + cell - 1, y + cell - 1 - offset), (50, 50, 50), 1)
            else:
                cv2.rectangle(image, (x, y), (x + cell - 1, y + cell - 1), (70, 70, 70), -1)
    if caption_height:
        cv2.rectangle(image, (x0, y0 + side), (x0 + 90, y0 + side + caption_height), (20, 20, 20), -1)
    return image, (x0, y0, side, side)


def boxes_of(image: np.ndarray, recall: object = "default") -> list[tuple[int, int, int, int]]:
    kwargs = {} if recall == "default" else {"recall": recall}
    found = bd.detect_boards(image, max_boards=6, **kwargs)  # type: ignore[arg-type]
    return [bd._bbox_from_quad(quad) for _, quad in found if quad is not None]


def best_iou(boxes: list[tuple[int, int, int, int]], target: tuple[int, int, int, int]) -> float:
    return max((bd._bbox_iou(box, target) for box in boxes), default=0.0)


# --------------------------------------------------------------------------
# The trunk ships the pack; the harness must not leave a mark
# --------------------------------------------------------------------------


def test_the_trunk_default_is_the_pack() -> None:
    """The point of A1: the product gets the recoveries by calling the trunk, unpatched."""
    assert trunk_default_is_the_pack()
    assert DEFAULT_RECALL == RecallOptions(scales=(0.5,), rescue_squares=True, embedded_floor=0.0)


def test_the_default_pack_touches_nothing_and_yields_the_trunk_default() -> None:
    from chess_diagram_ocr.detection import hybrid

    before_quads = bd._extract_candidate_quads
    before_diagrams = hybrid.detect_diagrams
    with recall_pack() as options:
        assert options == DEFAULT_RECALL
        assert bd._extract_candidate_quads is before_quads
        assert hybrid.detect_diagrams is before_diagrams


def test_a_variant_is_forced_for_the_duration_and_the_trunk_comes_back() -> None:
    """The variant travels by a ``ContextVar``, never by swapping a module attribute."""
    from chess_diagram_ocr.config import recall_em_vigor
    from chess_diagram_ocr.detection import hybrid

    before_quads = bd._extract_candidate_quads
    before_diagrams = hybrid.detect_diagrams
    assert recall_em_vigor(DEFAULT_RECALL) == DEFAULT_RECALL
    with recall_pack(scales=(), rescue_squares=False) as options:
        assert options == RecallOptions(scales=(), rescue_squares=False)
        assert recall_em_vigor(DEFAULT_RECALL) == options, "the trunk sees the variant"
        assert bd._extract_candidate_quads is before_quads, "no attribute was swapped"
        assert hybrid.detect_diagrams is before_diagrams
    assert recall_em_vigor(DEFAULT_RECALL) == DEFAULT_RECALL


def test_another_thread_never_sees_the_variant() -> None:
    import threading

    from chess_diagram_ocr.config import recall_em_vigor

    seen: list[object] = []
    with recall_pack(scales=(), rescue_squares=False):
        thread = threading.Thread(target=lambda: seen.append(recall_em_vigor(DEFAULT_RECALL)))
        thread.start()
        thread.join()
    assert seen == [DEFAULT_RECALL], "a ContextVar is per thread; the product path is untouched"


def test_the_harness_puts_the_trunk_back_even_when_the_body_raises() -> None:
    from chess_diagram_ocr.config import recall_em_vigor

    with pytest.raises(RuntimeError):
        with recall_pack(scales=()):
            raise RuntimeError("boom")
    assert recall_em_vigor(DEFAULT_RECALL) == DEFAULT_RECALL


def test_an_out_of_range_scale_is_refused() -> None:
    image, _ = board_page()
    with pytest.raises(ValueError, match="escala"):
        with multiscale_search(scales=(1.5,)):
            bd.detect_boards(image, max_boards=4)


# --------------------------------------------------------------------------
# One ruler, not two
# --------------------------------------------------------------------------


def test_the_rescue_scores_a_quad_exactly_as_the_raw_pass_does() -> None:
    """A rescued candidate competes with raw candidates, so it must be measured alike.

    ``_score_quad`` repeats the formula of ``_contour_candidates``; if the two ever drift,
    the pooled list is sorted by two different rulers and the wrong candidate wins --
    silently. This pins them together on the raw pass's own output, where the answer is known.
    """
    image, _ = board_page()
    trunk = bd._contour_candidates(image)
    assert trunk, "a pagina sintetica precisa produzir candidatos"
    area = float(image.shape[0] * image.shape[1])
    for quad, score, _ in trunk:
        measured = _score_quad(image, quad, area)
        assert measured is not None
        assert measured[0] == pytest.approx(score, rel=1e-9, abs=1e-9)


def test_the_pack_never_drops_what_the_raw_pass_found() -> None:
    image, target = board_page()
    trunk = boxes_of(image, RAW)
    packed = boxes_of(image, NO_EMBEDDED_FLOOR)
    assert best_iou(trunk, target) > 0.9
    for box in trunk:
        assert best_iou(packed, box) > 0.9, f"o pacote perdeu {box}, que o tronco achava"


# --------------------------------------------------------------------------
# Square rescue
# --------------------------------------------------------------------------


def test_square_anchors_are_the_largest_square_at_three_positions() -> None:
    quads = square_anchors((10, 20, 100, 160))
    assert len(quads) == 3
    for quad in quads:
        xs, ys = quad[:, 0], quad[:, 1]
        assert float(xs.max() - xs.min()) == pytest.approx(100.0)
        assert float(ys.max() - ys.min()) == pytest.approx(100.0)
    tops = sorted(float(q[:, 1].min()) for q in quads)
    assert tops == [20.0, 50.0, 80.0]  # topo, meio, base do vao de 60 pt


def test_square_anchors_of_a_square_box_are_the_box() -> None:
    for quad in square_anchors((5, 7, 64, 64)):
        assert bd._bbox_from_quad(quad) == (5, 7, 64, 64)


def test_a_caption_welded_to_the_board_is_recovered_as_a_square() -> None:
    """The ``Reinfeld`` shape: the contour fuses board and caption, so the checker reads zero.

    The guard is right about the crop it was shown -- 320x410 is not a chessboard. The pack
    offers it the largest square inside that crop and the **same** guard accepts it.
    """
    image, target = board_page(caption_height=90)
    trunk = boxes_of(image, RAW)
    assert trunk == [], f"o tronco cru deveria falhar nesta pagina, devolveu {trunk}"

    rejected: list[object] = []
    bd.detect_boards(image, max_boards=6, rejected=rejected, recall=None)
    reasons = {item.reason for item in rejected}  # type: ignore[attr-defined]
    assert "sem-contraste-de-casa" in reasons

    packed = boxes_of(image, NO_EMBEDDED_FLOOR)
    assert best_iou(packed, target) > 0.95, f"esperado {target}, veio {packed}"


def test_the_rescue_leaves_an_already_square_rejection_alone() -> None:
    """A square crop with no checkerboard stays rejected: the rescue adds no second chance.

    Photographs, portraits and frames are square often enough. The rescue exists for a crop
    whose *shape* says the registration is off, and :data:`SQUARE_MIN_ELONGATION` is where
    that begins; below it the largest square inside the crop is the crop.
    """
    rng = np.random.default_rng(20260907)
    image = np.full((720, 520, 3), 255, np.uint8)
    noise = rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)
    image[80:380, 90:390] = cv2.GaussianBlur(noise, (9, 9), 0)
    cv2.rectangle(image, (90, 80), (390, 380), (0, 0, 0), 3)
    packed = boxes_of(image, NO_EMBEDDED_FLOOR)
    assert best_iou(packed, (90, 80, 300, 300)) < 0.5, f"ruido quadrado virou tabuleiro: {packed}"


def test_the_elongation_floor_is_where_the_rescue_can_still_gain() -> None:
    assert SQUARE_MIN_ELONGATION > 1.0
    box = (0, 0, 100, int(100 * SQUARE_MIN_ELONGATION))
    quads = square_anchors(box)
    assert {bd._bbox_from_quad(q)[3] for q in quads} == {100}


# --------------------------------------------------------------------------
# Multi-scale search
# --------------------------------------------------------------------------


def test_a_hatched_board_is_found_by_the_half_scale_pass() -> None:
    """The ``Niemeijer`` shape: dark squares drawn as strokes, not ink.

    At full resolution the local-mean threshold sees a picket fence and the board is not one
    component. ``INTER_AREA`` at half scale averages the strokes into flat grey first.
    """
    image, target = board_page(hatch_step=5)
    assert boxes_of(image, RAW) == [], "o tronco cru deveria falhar na pagina hachurada"
    with multiscale_search(rescue_squares=False) as options:
        packed = boxes_of(image, options)
    assert best_iou(packed, target) > 0.9, f"esperado {target}, veio {packed}"


def test_turning_the_scales_off_gives_the_raw_pass_back() -> None:
    image, _ = board_page(hatch_step=5)
    with multiscale_search(scales=(), rescue_squares=False) as options:
        assert boxes_of(image, options) == []


def test_the_harness_forces_the_variant_on_the_trunk_entry_point() -> None:
    """``validate_detection.py --variant multiscale`` goes through ``field_eval``, which has
    no ``recall=`` to pass: the harness has to reach the default call."""
    image, _ = board_page(hatch_step=5)
    assert boxes_of(image) != [], "o padrao do tronco acha a pagina hachurada"
    with recall_pack(scales=(), rescue_squares=False):
        assert boxes_of(image) == [], "o arnes tem de forcar a variante na chamada padrao"
    assert boxes_of(image) != []


# --------------------------------------------------------------------------
# Embedded checker floor
# --------------------------------------------------------------------------


def _pdf_with_image(image_rgb: np.ndarray) -> object:
    """A one-page PDF whose only content is ``image_rgb``, embedded as an image."""
    pymupdf = pytest.importorskip("pymupdf")
    height, width = image_rgb.shape[:2]
    doc = pymupdf.open()
    page = doc.new_page(width=420.0, height=560.0)
    pixmap = pymupdf.Pixmap(
        pymupdf.csRGB, width, height, np.ascontiguousarray(image_rgb).tobytes(), False
    )
    page.insert_image(pymupdf.Rect(60, 60, 60 + width, 60 + height), pixmap=pixmap)
    blob = doc.tobytes()
    doc.close()
    return pymupdf.open("pdf", blob)


def _board_bitmap(side: int = 240) -> np.ndarray:
    image = np.full((side, side, 3), 250, np.uint8)
    cell = side // 8
    for row in range(8):
        for col in range(8):
            if (row + col) % 2:
                cv2.rectangle(
                    image, (col * cell, row * cell), ((col + 1) * cell - 1, (row + 1) * cell - 1), (60, 60, 60), -1
                )
    return image


def test_the_embedded_floor_keeps_a_board_and_drops_a_photograph() -> None:
    """The S-143 zero floor, applied to the source that never had it.

    It does not contradict S-12: the PDF declared an *image* there, and never declared that
    the image is a diagram -- which is the argument S-176 already made for `is_page_band`.
    """
    from chess_diagram_ocr.detection import hybrid

    rng = np.random.default_rng(11)
    photo = cv2.GaussianBlur(rng.integers(0, 255, (240, 240, 3), dtype=np.uint8), (11, 11), 0)

    for bitmap, expected in ((_board_bitmap(), 1), (photo, 0)):
        doc = _pdf_with_image(bitmap)
        try:
            page = doc[0]  # type: ignore[index]
            rgb = _render(page)
            assert len(hybrid.candidates_from_embedded_images(page)) == 1
            raw = [c for c in hybrid.detect_diagrams(page, rgb, recall=None) if c.source == "embedded"]
            assert len(raw) == 1
            with embedded_checker_floor() as options:
                floored = [c for c in hybrid.detect_diagrams(page, rgb, recall=options) if c.source == "embedded"]
            assert len(floored) == expected
            by_default = [c for c in hybrid.detect_diagrams(page, rgb) if c.source == "embedded"]
            assert len(by_default) == expected
        finally:
            doc.close()  # type: ignore[attr-defined]


def _render(page: object, dpi: int = 220) -> np.ndarray:
    import pymupdf

    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)  # type: ignore[attr-defined]
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()


# --------------------------------------------------------------------------
# Corpus regressions: the measured pages, pinned
# --------------------------------------------------------------------------

RECOVERED = [
    # (pdf, page, annotated boxes in PDF points that the trunk alone loses)
    ("Niemeijer - Zwarte Magie 100 zwarte dame‑problemen (1945).pdf", 20,
     [(108.0, 241.0, 385.0, 518.0), (108.0, 693.0, 385.0, 970.0), (395.0, 693.0, 672.0, 970.0)]),
    ("Reinfeld_1001_Sacrificios_y_Combinaciones_Brillantes_1977.pdf", 40,
     [(162.5, 335.0, 278.6, 450.8)]),
    ("Reinfeld_1001_Sacrificios_y_Combinaciones_Brillantes_1977.pdf", 150,
     [(160.0, 191.7, 276.8, 307.5)]),
]

FALSE_POSITIVE_PAGES = [
    ("1937 Kemeri.pdf", 276),
    ("1937 Kemeri.pdf", 279),
    ("\U0001f4daYusupov Artur. Build Up Your Chess (all volumes).pdf", 2),
]


def _detect(pdf_name: str, page_index: int, *, packed: bool) -> list[tuple[float, float, float, float]]:
    import pymupdf

    from chess_diagram_ocr.detection.hybrid import detect_diagrams
    from chess_diagram_ocr.pdf_io import render_pdf_page

    assert CORPUS is not None
    path = CORPUS / pdf_name
    if not path.is_file():
        pytest.skip(f"livro ausente: {pdf_name}")
    image = render_pdf_page(path, page_index, dpi=220)
    with pymupdf.open(path) as doc:
        recall = DEFAULT_RECALL if packed else None
        return [c.bbox_pdf for c in detect_diagrams(doc[page_index], image, max_boards=12, recall=recall)]


@needs_corpus
@pytest.mark.parametrize(("pdf_name", "page_index", "boxes"), RECOVERED, ids=lambda v: str(v)[:24])
def test_the_pack_recovers_the_pages_the_trunk_loses(
    pdf_name: str, page_index: int, boxes: list[tuple[float, float, float, float]]
) -> None:
    from chess_diagram_ocr.field_eval import MATCH_IOU, bbox_iou

    plain = _detect(pdf_name, page_index, packed=False)
    packed = _detect(pdf_name, page_index, packed=True)
    for box in boxes:
        assert max((bbox_iou(box, other) for other in plain), default=0.0) < MATCH_IOU
        assert max((bbox_iou(box, other) for other in packed), default=0.0) >= MATCH_IOU


@needs_corpus
@pytest.mark.parametrize(("pdf_name", "page_index"), FALSE_POSITIVE_PAGES, ids=lambda v: str(v)[:24])
def test_the_pack_clears_the_false_positives_of_the_field_set(pdf_name: str, page_index: int) -> None:
    """Three pages that the field set marks ``sem-diagrama`` and the trunk reads anyway."""
    assert _detect(pdf_name, page_index, packed=False), "esta pagina era um falso positivo do tronco"
    assert _detect(pdf_name, page_index, packed=True) == []
