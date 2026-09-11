"""Figurine placement, measured against real font metrics.

Nothing here is asserted against a constant someone typed. Every number is read out of
the font file on this machine and checked against the geometric property it is supposed
to guarantee, so a font swap changes the numbers and the assertions still hold.
"""

from __future__ import annotations

import pytest

from caissa.typeset import figurine as fig
from caissa.typeset.fonts import PIECES, Confidence, load_font

PIECE_LETTERS = "KQRBNP"

# A figurine is fitted to the text's cap height times a small optical boost. These are
# the tolerances a typographer would accept on a printed page: a quarter of a point at
# 10 pt is 0.0025 em, and that is the level at which a misplaced foot becomes visible.
FOOT_TOLERANCE_EM = 0.004
HEIGHT_TOLERANCE = 0.02


def _families(verified_specs):
    return [s for s in verified_specs]


def test_measure_family_fits_the_cap_height(legacy_font):
    """The reference piece, scaled, stands exactly cap height x boost."""
    metrics = fig.measure_family(legacy_font)
    target = fig.DEFAULT_TEXT_CAP_HEIGHT * fig.FIGURINE_OPTICAL_BOOST

    tallest = 0.0
    for piece in PIECE_LETTERS:
        outline = legacy_font.piece_outline(piece)
        if outline.is_empty():
            continue
        _, y0, _, y1 = outline.bbox()
        tallest = max(tallest, (y1 - y0) / legacy_font.units_per_em)
    assert tallest * metrics.scale == pytest.approx(target, rel=HEIGHT_TOLERANCE)


def test_no_piece_overshoots_the_fitted_height(verified_specs):
    """Every family, every piece: nothing stands above the fitted cap height.

    This is the property `measure_family` promises. It used to fit the **king**, on the
    reasoning that the king is the tallest piece in a Staunton set -- which is false for
    seven of the families installed here (Chess Leipzig's rook stands 6.7 % above its
    king, Chess Cases' bishop 5.5 %, Chess Marroquin's queen 4.6 %). Those pieces then
    stood proud of the line they were set in. Fitting the tallest piece makes the
    promise true by construction, and this test is what holds it true.
    """
    target = fig.DEFAULT_TEXT_CAP_HEIGHT * fig.FIGURINE_OPTICAL_BOOST
    offenders: list[str] = []
    for spec in verified_specs:
        font = load_font(spec)
        metrics = fig.measure_family(font)
        for piece in PIECE_LETTERS:
            outline = font.piece_outline(piece)
            if outline.is_empty():
                continue
            _, y0, _, y1 = outline.bbox()
            height = (y1 - y0) / font.units_per_em * metrics.scale
            if height > target * (1.0 + 1e-6):
                offenders.append(f"{spec.key}:{piece}={height / target:.3f}")
    assert not offenders, "pecas acima da altura ajustada: " + ", ".join(offenders)


def test_every_piece_foot_lands_on_the_baseline(verified_specs):
    """The charter fails 'figurino desalinhado da linha de base'.

    For each piece: place it with the family's metrics at 10 pt and check that the
    lowest point of the drawn outline sits on the baseline, within a quarter point.
    """
    text_size = 10.0
    bad: list[str] = []
    for spec in verified_specs:
        font = load_font(spec)
        metrics = fig.measure_family(font)
        for piece in PIECE_LETTERS:
            outline = font.piece_outline(piece)
            if outline.is_empty():
                continue
            size = metrics.size_for(text_size)
            scale = size / font.units_per_em
            _, y0, _, _ = outline.bbox()
            # Drawn at baseline_y, the glyph origin moves down by shift_for; the foot is
            # then y0 * scale above that origin (font y is up).
            foot_below_baseline = metrics.shift_for(piece, text_size) - y0 * scale
            if abs(foot_below_baseline) > FOOT_TOLERANCE_EM * text_size:
                bad.append(f"{spec.key}:{piece}={foot_below_baseline:+.4f}pt")
    assert not bad, "pes fora da linha de base: " + ", ".join(bad)


def test_metrics_are_unitless_and_scale_linearly(legacy_font):
    """One measurement has to serve 9, 10, 11 and 12 pt. If it did not scale linearly,
    a document with mixed sizes would need a measurement per size."""
    metrics = fig.measure_family(legacy_font)
    base = metrics.size_for(10.0)
    for size in (9.0, 11.0, 12.0, 24.0):
        assert metrics.size_for(size) == pytest.approx(base * size / 10.0)
        assert metrics.shift_for("N", size) == pytest.approx(
            metrics.shift_for("N", 10.0) * size / 10.0
        )


def test_advance_leaves_air_but_not_a_gap(legacy_font):
    """The advance must clear the widest piece and add a little air -- enough that the
    knight's muzzle does not touch the following letter, not so much that the move
    splits into two words."""
    metrics = fig.measure_family(legacy_font)
    widest = 0.0
    for piece in PIECE_LETTERS:
        outline = legacy_font.piece_outline(piece)
        if outline.is_empty():
            continue
        x0, _, x1, _ = outline.bbox()
        widest = max(widest, (x1 - x0) / legacy_font.units_per_em * metrics.scale)
    assert metrics.advance >= widest
    assert metrics.advance - widest == pytest.approx(fig.FIGURINE_TRAILING_SPACE, abs=1e-9)
    assert metrics.advance < widest + 0.25


def test_missing_reference_piece_does_not_crash(legacy_font):
    """A family with no king still has to produce usable metrics rather than raise."""

    class NoPieces:
        spec = legacy_font.spec
        units_per_em = legacy_font.units_per_em

        def piece_outline(self, piece):  # noqa: ANN001, ANN201
            from caissa.typeset.outlines import Outline

            return Outline(contours=(), advance=0.0, units_per_em=self.units_per_em)

    metrics = fig.measure_family(NoPieces())
    assert metrics.scale == 1.0
    assert metrics.advance > 0


# --------------------------------------------------------------------------- #
# SAN
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("san", "expect"),
    [
        ("Nf3", [("piece", "N"), ("text", "f3")]),
        ("e4", [("text", "e4")]),
        ("Rxd4", [("piece", "R"), ("text", "xd4")]),
        ("Qh5+", [("piece", "Q"), ("text", "h5"), ("text", "+")]),
        ("Rh8#", [("piece", "R"), ("text", "h8"), ("text", "#")]),
        ("Nbd7", [("piece", "N"), ("text", "bd7")]),
        ("R1e2", [("piece", "R"), ("text", "1e2")]),
        ("exd5", [("text", "exd5")]),
        ("e8=Q", [("text", "e8"), ("text", "="), ("piece", "Q")]),
        ("O-O", [("text", "O-O")]),
        ("O-O-O", [("text", "O-O-O")]),
        ("Nf3!?", [("piece", "N"), ("text", "f3"), ("text", "!?")]),
    ],
)
def test_san_splits_into_the_right_runs(san, expect):
    runs = [(r.kind, r.content) for r in fig.san_to_figurine_runs(san)]
    assert runs == expect


def test_castling_is_never_figurined():
    """`O-O` names no piece. A king glyph there is simply wrong, and it is the mistake a
    naive 'first letter is the piece' rule makes."""
    for castle in ("O-O", "O-O-O", "0-0", "0-0-0"):
        runs = fig.san_to_figurine_runs(castle)
        assert all(r.kind == "text" for r in runs)


def test_unparseable_text_passes_through_untouched():
    for junk in ("hello", "1-0", "", "..."):
        runs = fig.san_to_figurine_runs(junk)
        assert [r.content for r in runs] == [junk]


def test_missing_glyph_falls_back_to_a_letter_not_a_blank():
    """A font without a knight must give the reader `N`, never nothing."""
    runs = fig.san_to_figurine_runs("Nf3", have_glyph={"K", "Q", "R", "B", "P"})
    assert runs[0].kind == "text"
    assert runs[0].content in {"N", "C", "S"}


def test_language_letters_are_used_for_the_fallback():
    runs = fig.san_to_figurine_runs(
        "Nf3", have_glyph=set(), fallback_language="pt"
    )
    assert runs[0].content == "C", "em portugues o cavalo e 'C'"


def test_translate_san_maps_the_portuguese_trap():
    """`R` is Rei in Portuguese and Rook in English -- the collision CORPUS.md §E7 calls
    the most important test case in the notation front."""
    assert fig.translate_san("Rd1", "pt").startswith("T")   # Rook -> Torre
    assert fig.translate_san("Kd1", "pt").startswith("R")   # King -> Rei


# --------------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------------- #
def _path_points(markup: str) -> list[tuple[float, float]]:
    """Coordinates from the ``d`` attribute only.

    Slicing at ``d="`` and running a number regex over the rest also matches the digits
    inside ``fill="#000000"``, which reads as a point at the origin and makes any
    bounding-box assertion trivially true.
    """
    import re
    import xml.etree.ElementTree as ET

    element = ET.fromstring(f"<g xmlns='http://www.w3.org/2000/svg'>{markup}</g>")
    data = "".join(
        child.get("d") or ""
        for child in element
        if child.tag.endswith("path")
    )
    numbers = [float(v) for v in re.findall(r"-?\d+\.?\d*", data)]
    return list(zip(numbers[0::2], numbers[1::2]))


def test_figurine_svg_seats_the_glyph_on_the_given_baseline(legacy_font):
    metrics = fig.measure_family(legacy_font)
    markup, advance = fig.figurine_svg(
        "N", font=legacy_font, metrics=metrics, text_size=10.0, x=0.0, baseline_y=100.0
    )
    assert markup.startswith("<path")
    assert advance > 0

    ys = [y for _, y in _path_points(markup)]
    # SVG y grows downward, so the foot is the largest y, and it belongs on the baseline.
    assert max(ys) == pytest.approx(100.0, abs=0.05), (
        f"o pe do cavalo caiu em y={max(ys):.3f}, a linha de base esta em 100"
    )
    assert min(ys) < 100.0, "o glifo nao subiu acima da linha de base"


def test_every_piece_svg_seats_on_the_baseline(legacy_font):
    """Not just the knight: every piece, at every size the proof sheet sets."""
    metrics = fig.measure_family(legacy_font)
    for text_size in (9.0, 10.0, 11.0, 12.0):
        for piece in PIECE_LETTERS:
            markup, _ = fig.figurine_svg(
                piece, font=legacy_font, metrics=metrics,
                text_size=text_size, x=0.0, baseline_y=50.0,
            )
            if not markup:
                continue
            ys = [y for _, y in _path_points(markup)]
            assert max(ys) == pytest.approx(50.0, abs=0.05), (
                f"{piece} a {text_size} pt: pe em {max(ys):.3f}, esperado 50"
            )


def test_figurine_svg_starts_at_the_glyphs_left_edge(legacy_font):
    """Legacy chess glyphs carry a full square of side bearing. Honouring the origin
    instead of the ink's left edge opens a board-square-wide hole between the piece and
    the file letter."""
    metrics = fig.measure_family(legacy_font)
    markup, _ = fig.figurine_svg(
        "Q", font=legacy_font, metrics=metrics, text_size=10.0, x=7.0, baseline_y=0.0
    )
    xs = [x for x, _ in _path_points(markup)]
    assert min(xs) == pytest.approx(7.0, abs=0.05)


def test_a_character_with_no_glyph_yields_nothing_not_a_broken_path(legacy_font):
    """`figurine_svg` returns empty markup and a zero advance for a piece the family
    cannot draw, so a caller that concatenates the result gets a gap it can detect
    rather than a `<path d="">` the renderer will choke on."""

    class NoGlyph:
        spec = legacy_font.spec
        units_per_em = legacy_font.units_per_em

        def piece_outline(self, piece):  # noqa: ANN001, ANN201
            from caissa.typeset.outlines import Outline

            return Outline(contours=(), advance=0.0, units_per_em=self.units_per_em)

    metrics = fig.measure_family(legacy_font)
    markup, advance = fig.figurine_svg(
        "N", font=NoGlyph(), metrics=metrics, text_size=10.0, x=0.0, baseline_y=0.0
    )
    assert markup == ""
    assert advance == 0.0


def test_all_twelve_pieces_are_drawable_in_a_verified_family(verified_specs):
    """A family marked VERIFIED must actually draw all twelve."""
    for spec in verified_specs:
        if spec.confidence is not Confidence.VERIFIED:
            continue
        font = load_font(spec)
        missing = [p for p in PIECES if font.piece_outline(p).is_empty()]
        assert not missing, f"{spec.key} marcada VERIFIED mas sem glifo para {missing}"
