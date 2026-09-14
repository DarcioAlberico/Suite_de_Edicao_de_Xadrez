"""OCR_UI_ROADMAP passo 10: a board in a chess font the catalog does not know.

The lattice is exact and torch-free (:func:`detect_unknown_font_lattices`);
the read goes through the square classifier in
:func:`caissa.ingest.pdf.finders.inferred_font_finder` with provenance
``VECTOR_INFERRED`` and a capped confidence.  Both are exercised here by the
roadmap's own sabotage — hiding Merida from the catalog — because the shelf
has no font outside the catalog to test on (``vector_survey.py``, 2026-09-14:
0 of 46 books).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from caissa.core.model import RecognitionPath
from caissa.vision.detect import (
    detect_unknown_font_lattices,
    detect_vector_boards,
    lookup_family,
)

from .conftest import build_diagram_pdf, merida_rows

PLACEMENT = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R"


def _hide_merida(name: str):
    return None if "merida" in name.lower() else lookup_family(name)


def test_the_unknown_font_lattice_is_the_exact_boards_rectangle(merida_font: Path) -> None:
    doc = build_diagram_pdf(merida_font, merida_rows(PLACEMENT))
    try:
        page = doc[0]  # type: ignore[index]
        exact = detect_vector_boards(page)
        assert len(exact) == 1
        assert detect_unknown_font_lattices(page) == [], "a catalogued font is not unknown"
        found = detect_unknown_font_lattices(page, lookup=_hide_merida)
        assert len(found) == 1
        lattice = found[0]
        # The exact path keeps an origin-based rectangle (half a cell to the
        # left); the lattice's is the union of the 64 cell boxes — the board.
        assert lattice.rect_pdf == pytest.approx((72.0, 98.0, 248.0, 274.0), abs=0.1)
        assert lattice.cell_pitch_pt == pytest.approx(22.0)
        assert exact[0].rect_pdf[0] < lattice.rect_pdf[0] < exact[0].rect_pdf[2]
        assert "merida" in lattice.font_name.lower()
        assert lattice.missing_cells == 0
        assert len(lattice.raw_rows) == 8
    finally:
        doc.close()  # type: ignore[attr-defined]


def test_the_inferred_finder_reads_through_the_classifier_with_a_capped_confidence(
    merida_font: Path, monkeypatch
) -> None:
    from caissa.ingest.pdf import finders
    from caissa.vision.classify import page as classify_page

    doc = build_diagram_pdf(merida_font, merida_rows(PLACEMENT))
    try:
        page = doc[0]  # type: ignore[index]
        crops: list[np.ndarray] = []

        def fake_predict(boards, classifier, **_kwargs):
            crops.extend(boards)
            return [SimpleNamespace(prediction=SimpleNamespace(fen_board=PLACEMENT,
                                                               min_confidence=0.97),
                                    rotation=0) for _ in boards]

        monkeypatch.setattr(classify_page, "predict_boards_batched", fake_predict)
        finder = finders.inferred_font_finder(classifier=object(), lookup=_hide_merida)
        hits = finder(page, SimpleNamespace(index=0), None)
        assert len(hits) == 1
        hit = hits[0]
        assert hit.path is RecognitionPath.VECTOR_INFERRED
        assert hit.fen == f"{PLACEMENT} w - - 0 1"
        assert hit.confidence == pytest.approx(finders.INFERRED_CONFIDENCE_CAP), (
            "0,97 from the classifier is capped: the font was not decoded")
        assert "fonte fora do catálogo" in hit.method
        assert crops
        assert crops[0].ndim == 3
        assert crops[0].shape[2] == 3
        side = crops[0].shape[0]
        assert abs(crops[0].shape[1] - side) <= 2, "the crop is the square board"
        # The catalogued book is untouched: the finder yields nothing.
        catalogued = finders.inferred_font_finder(classifier=object())
        assert catalogued(page, SimpleNamespace(index=0), None) == []
        # Without a classifier the board is located and left unread.
        def no_weights():
            raise RuntimeError("sem pesos")

        monkeypatch.setattr("caissa.vision.classify.batched.load_classifier", no_weights)
        unread = finders.inferred_font_finder(lookup=_hide_merida)
        located = unread(page, SimpleNamespace(index=0), None)
        assert len(located) == 1
        assert located[0].fen is None
        assert located[0].path is RecognitionPath.VECTOR_INFERRED
    finally:
        doc.close()  # type: ignore[attr-defined]


def test_the_combined_finder_puts_the_inferred_route_between_vector_and_raster(
    merida_font: Path,
) -> None:
    from caissa.ingest.pdf import finders

    doc = build_diagram_pdf(merida_font, merida_rows(PLACEMENT))
    try:
        page = doc[0]  # type: ignore[index]
        calls: list[str] = []

        def raster(page, frame, text):
            calls.append("raster")
            x0, y0, x1, y1 = detect_vector_boards(page)[0].rect_pdf
            return [finders.DiagramHit(box=(x0 + 3, y0 + 3, x1 - 3, y1 - 3), fen=None,
                                       confidence=0.5, path=RecognitionPath.GEOMETRIC)]

        def inferred(page, frame, text):
            calls.append("inferred")
            return []

        finder = finders.combined_finder(raster, inferred=inferred)
        hits = finder(page, SimpleNamespace(index=0), None)
        assert calls == ["inferred", "raster"]
        assert [h.path for h in hits] == [RecognitionPath.VECTOR], "the exact read wins the overlap"
    finally:
        doc.close()  # type: ignore[attr-defined]


def test_fill_holes_trusts_the_classifier_only_where_the_font_was_silent() -> None:
    from caissa.ingest.pdf.finders import INFERRED_CONFIDENCE_CAP, DiagramHit, fill_holes

    # Polgar p. 91: the rook on a5 (lattice row 3, col 0) was dropped by the
    # extractor and the exact path took it for an empty square.
    hit = DiagramHit(box=(0, 0, 100, 100), fen="k7/2pN4/K7/2P5/P7/8/8/8 w - - 0 1",
                     confidence=0.6, holes=((3, 0),), cells_box=(0, 0, 100, 100))
    fixed = fill_holes(hit, "k7/2pN4/K7/R1P5/P7/8/8/8")
    assert fixed is not None
    assert fixed.fen == "k7/2pN4/K7/R1P5/P7/8/8/8 w - - 0 1"
    assert fixed.path is RecognitionPath.VECTOR_INFERRED
    assert fixed.confidence == pytest.approx(0.6)
    assert fixed.confidence <= INFERRED_CONFIDENCE_CAP
    assert fixed.holes == ()
    assert "1 casa(s) ausentes" in fixed.method
    # A classifier that disagrees on a cell the font *did* give is not believed.
    assert fill_holes(hit, "k7/2pN4/K7/R1P5/P7/8/8/7Q") is None
    # A hole the classifier also sees as empty is filled with nothing, honestly.
    same = fill_holes(hit, "k7/2pN4/K7/2P5/P7/8/8/8")
    assert same is not None
    assert same.fen == hit.fen
    assert "0 com peça" in same.method
    # Black at the bottom: the lattice is the board turned around, so the
    # printed top-left cell (0, 0) is h1.
    flipped = DiagramHit(box=(0, 0, 100, 100), fen="8/8/8/8/8/8/8/k7 w - - 0 1", confidence=0.6,
                         holes=((0, 0),), cells_box=(0, 0, 100, 100), orientation_white=False)
    fixed = fill_holes(flipped, "8/8/8/8/8/8/8/k6R")
    assert fixed is not None
    assert fixed.fen.startswith("8/8/8/8/8/8/8/k6R")
    assert fill_holes(flipped, "8/8/8/8/8/8/8/R6k") is None, "a1 was given by the font"
    # No holes, nothing to do.
    whole = DiagramHit(box=(0, 0, 1, 1), fen="8/8/8/8/8/8/8/8 w - - 0 1")
    assert fill_holes(whole, "8/8/8/8/8/8/8/8") is None


def test_the_combined_finder_completes_holed_exact_reads_with_the_classifier(
    merida_font: Path, monkeypatch
) -> None:
    from caissa.ingest.pdf import finders
    from caissa.vision.classify import page as classify_page

    doc = build_diagram_pdf(merida_font, merida_rows(PLACEMENT))
    try:
        page = doc[0]  # type: ignore[index]
        exact = detect_vector_boards(page)[0]
        # Pretend the extractor dropped the knight on f3 (lattice row 5, col 5).
        holed = finders.DiagramHit(
            box=exact.rect_pdf,
            fen="r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNBQK2R w - - 0 1",
            confidence=0.6, holes=((5, 5),), cells_box=exact.evidence.cells_rect_pdf,
        )
        monkeypatch.setattr(finders, "vector_diagram_finder", lambda p, f, t: [holed])
        seen: list[str] = []

        def fake_predict(boards, classifier, **kwargs):
            seen.append(kwargs.get("mode"))
            return [SimpleNamespace(prediction=SimpleNamespace(fen_board=PLACEMENT,
                                                               min_confidence=0.99),
                                    rotation=0) for _ in boards]

        monkeypatch.setattr(classify_page, "predict_boards_batched", fake_predict)
        finder = finders.combined_finder(raster=lambda p, f, t: [], inferred=lambda p, f, t: [],
                                         classifier=object())
        hits = finder(page, SimpleNamespace(index=0), None)
        assert seen == ["0"], "the crop is classified as printed; the finder turns it itself"
        assert len(hits) == 1
        assert hits[0].fen.startswith(PLACEMENT)
        assert hits[0].path is RecognitionPath.VECTOR_INFERRED
        assert hits[0].holes == ()
    finally:
        doc.close()  # type: ignore[attr-defined]


def test_a_holed_exact_read_is_capped_and_reports_its_holes(merida_font: Path, monkeypatch) -> None:
    """The exact path no longer calls a board with missing cells exact."""
    from caissa.ingest.pdf.importer import vector_diagram_finder
    from caissa.vision.detect import vector_detect

    doc = build_diagram_pdf(merida_font, merida_rows(PLACEMENT))
    try:
        page = doc[0]  # type: ignore[index]
        original = vector_detect._collect_glyphs

        def drop_f3(page, allow_unverified):
            glyphs, unknown = original(page, allow_unverified)
            # f3 is lattice row 5, col 5: origin (72 + 5*22, 120 + 5*22).
            kept = [g for g in glyphs if abs(g.ox - 182.0) >= 0.5 or abs(g.oy - 230.0) >= 0.5]
            return kept, unknown

        monkeypatch.setattr(vector_detect, "_collect_glyphs", drop_f3)
        board = detect_vector_boards(page)[0]
        assert board.evidence.inferred_cells == 1
        assert board.confidence <= vector_detect.HOLE_CONFIDENCE_CAP
        assert board.piece_placement == "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNBQK2R"
        assert board.evidence.raw_rows[5][5] == "~"
        hit = vector_diagram_finder(page, SimpleNamespace(index=0), None)[0]
        assert hit.holes == ((5, 5),)
        assert hit.cells_box == pytest.approx(board.evidence.cells_rect_pdf)
    finally:
        doc.close()  # type: ignore[attr-defined]
