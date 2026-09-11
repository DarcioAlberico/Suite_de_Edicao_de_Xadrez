"""The two coordinate spaces, proven against the pixels MuPDF actually paints.

Every conversion here is checked three ways: against PyMuPDF's own matrices,
against the ink of a rendered page, and against the *wrong* formula (the
Editor's origin term) which must fail on the geometry that exposes it.  A
conversion test that only compares two formulas can be wrong twice.
"""

from __future__ import annotations

import numpy as np
import pytest

from caissa.ingest.pdf.geometry import (
    IDENTITY,
    PageFrame,
    affine_apply,
    affine_compose,
    affine_invert,
    affine_rect,
    rotation_affine,
)

from .conftest import requires_pymupdf

pytestmark = requires_pymupdf


# --------------------------------------------------------------------------- #
# Pure arithmetic
# --------------------------------------------------------------------------- #


def test_identity_is_a_no_op():
    assert affine_apply(IDENTITY, 3.0, 4.0) == (3.0, 4.0)
    assert affine_rect(IDENTITY, (1.0, 2.0, 3.0, 4.0)) == (1.0, 2.0, 3.0, 4.0)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotation_affine_matches_pymupdf(rotation):
    """Both directions of trust: our matrix must equal the library's."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.set_rotation(rotation)
    ours = rotation_affine(rotation, 400.0, 600.0)
    theirs = page.rotation_matrix
    assert ours == pytest.approx((theirs.a, theirs.b, theirs.c, theirs.d, theirs.e, theirs.f))
    inverse = affine_invert(ours)
    dm = page.derotation_matrix
    assert inverse == pytest.approx((dm.a, dm.b, dm.c, dm.d, dm.e, dm.f))


def test_invert_composes_to_identity():
    m = rotation_affine(90, 300.0, 460.0)
    assert affine_compose(m, affine_invert(m)) == pytest.approx(IDENTITY)


def test_singular_matrix_is_refused():
    with pytest.raises(ValueError, match="singular"):
        affine_invert((1.0, 2.0, 2.0, 4.0, 0.0, 0.0))


def test_rotation_affine_refuses_a_non_right_angle():
    with pytest.raises(ValueError, match="rotação"):
        rotation_affine(45, 100.0, 100.0)


def test_synthetic_frame_swaps_sides_when_rotated():
    frame = PageFrame.synthetic(0, 300.0, 460.0, rotation=90)
    assert (frame.width, frame.height) == (460.0, 300.0)
    assert (frame.text_width, frame.text_height) == (300.0, 460.0)
    assert frame.is_rotated
    # Text space (10, 20) - (30, 40) on a 300x460 page turned 90 cw lands at
    # x = 460 - y, y = x.
    assert frame.text_to_page((10.0, 20.0, 30.0, 40.0)) == pytest.approx((420.0, 10.0, 440.0, 30.0))
    back = frame.page_to_text(frame.text_to_page((10.0, 20.0, 30.0, 40.0)))
    assert back == pytest.approx((10.0, 20.0, 30.0, 40.0))


# --------------------------------------------------------------------------- #
# Against the ink
# --------------------------------------------------------------------------- #


def _ink_box(page, dpi=72):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    ys, xs = np.where(array[:, :, 0] < 128)
    return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)


def _page_with_text(rotation, cropbox=None, mediabox=None):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    if mediabox is not None:
        page.set_mediabox(pymupdf.Rect(*mediabox))
    if cropbox is not None:
        page.set_cropbox(pymupdf.Rect(*cropbox))
    page.set_rotation(rotation)
    page.insert_text(pymupdf.Point(100, 100), "Hello", fontsize=12)
    return doc, page


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize(
    ("mediabox", "cropbox"),
    [
        (None, None),
        (None, (50, 40, 350, 500)),
        ((20, 30, 420, 630), (70, 70, 370, 530)),
    ],
)
def test_text_box_maps_onto_the_ink(rotation, mediabox, cropbox):
    """``get_text`` boxes through the frame land where the glyphs are painted.

    Four rotations, a displaced CropBox, and a MediaBox whose origin is not
    ``(0, 0)``: twelve geometries, and the box must overlap the ink in all
    of them with at most 2 pt of slack (glyph side bearings).
    """
    doc, page = _page_with_text(rotation, cropbox, mediabox)
    frame = PageFrame.from_page(page)
    raw = page.get_text("dict")["blocks"][0]["bbox"]
    box = frame.text_to_page(tuple(float(v) for v in raw))
    ink = _ink_box(page)
    assert box[0] <= ink[0] + 2
    assert box[1] <= ink[1] + 2
    assert box[2] >= ink[2] - 2
    assert box[3] >= ink[3] - 2
    # ...and it is not a sloppy box: larger than the ink only by the face's
    # ascender and descender ("Hello" has no descender, so the 12 pt box
    # outgrows its 9 pt of ink by about 7) -- along whichever axis the glyphs
    # stand on after rotation -- and by side bearings on the other.
    excess = sorted(((box[2] - box[0]) - (ink[2] - ink[0]), (box[3] - box[1]) - (ink[3] - ink[1])))
    assert excess[0] < 4
    assert excess[1] < 9
    doc.close()


def test_the_origin_formula_is_wrong_on_a_rotated_cropped_page():
    """Proof of vitality for the test above.

    The Editor's section-48 formula (also carried by ``vector_detect``) adds
    the CropBox top-left in write space.  On a rotated page with a displaced
    CropBox it lands the box 100 pt away from the ink; a test that could not
    tell the two formulas apart would be no test.
    """
    import pymupdf

    doc, page = _page_with_text(90, cropbox=(50, 40, 350, 500))
    raw = page.get_text("dict")["blocks"][0]["bbox"]
    media, crop = page.mediabox, page.cropbox
    native = pymupdf.Rect(crop.x0, media.y1 - crop.y1, crop.x1, media.y1 - crop.y0)
    origin = (native * page.transformation_matrix).tl
    wrong = (
        pymupdf.Rect(raw) * pymupdf.Matrix(1, 0, 0, 1, -origin.x, -origin.y) * page.rotation_matrix
    )
    wrong.normalize()
    ink = _ink_box(page)
    assert abs(wrong.x0 - ink[0]) > 50, "a fórmula com origem deveria errar aqui"
    doc.close()


def test_clip_in_text_space_finds_the_text_and_page_space_does_not():
    """``get_text(clip=)`` wants text space -- the frame's ``page_to_text``."""
    doc, page = _page_with_text(90, cropbox=(50, 40, 350, 500))
    frame = PageFrame.from_page(page)
    raw = page.get_text("dict")["blocks"][0]["bbox"]
    page_box = frame.text_to_page(tuple(float(v) for v in raw))
    import pymupdf

    found = page.get_text("text", clip=pymupdf.Rect(*frame.page_to_text(page_box))).strip()
    assert found == "Hello"
    missed = page.get_text("text", clip=pymupdf.Rect(*page_box)).strip()
    assert missed == ""
    doc.close()


# --------------------------------------------------------------------------- #
# Points <-> pixels
# --------------------------------------------------------------------------- #


def test_pixel_size_matches_a_real_render():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    frame = PageFrame.from_page(page)
    for dpi in (72, 96, 150, 200, 300):
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        assert frame.pixel_size(dpi) == (pix.width, pix.height), dpi
    doc.close()


def test_points_and_pixels_round_trip_with_a_clip_origin():
    frame = PageFrame.synthetic(0, 612.0, 792.0)
    rect = (100.0, 200.0, 150.0, 260.0)
    px = frame.page_to_pixels(rect, 300.0, origin=(90.0, 190.0))
    assert px == pytest.approx((41.6667, 41.6667, 250.0, 291.6667), abs=1e-3)
    assert frame.pixels_to_page(px, 300.0, origin=(90.0, 190.0)) == pytest.approx(rect)


def test_clamp_keeps_a_box_on_the_page():
    frame = PageFrame.synthetic(0, 100.0, 50.0)
    assert frame.clamp((-10.0, -5.0, 120.0, 60.0)) == (0.0, 0.0, 100.0, 50.0)
    assert frame.clamp((120.0, 10.0, 130.0, 20.0)) == (100.0, 10.0, 100.0, 20.0)
