"""Pre-processing, measured against degradation this file itself applied.

The discipline here is the whole reason these tests are worth writing: every
page starts clean, *this test* damages it by a known amount, and the assertion
is about how much of the known amount came back.  A test that merely checks
"deskew returned an array" proves nothing; a test that asserts 2.30 degrees of
applied skew was recovered to within 0.2 degrees proves the estimator works.

Where a quality claim cannot be stated as "the number the test put in came
back", it is stated as a comparison against the undamaged page's own ink mask
(F1 of recovered ink), which is still ground truth because the clean page was
generated here too.
"""

from __future__ import annotations

import numpy as np
import pytest

from caissa.ocr.preprocess import (
    Binarize,
    BleedThroughReduction,
    Deskew,
    Despeckle,
    Dewarp,
    PreprocessContext,
    PreprocessPipeline,
    ShadowRemoval,
    Upscale,
    default_pipeline,
    deskew_image,
    estimate_skew_angle,
    otsu_threshold,
    sauvola_threshold,
    to_gray,
)

from .conftest import (
    add_faint_bleed_through,
    add_illumination,
    add_specks,
    curl,
    render_text_page,
    requires_font,
    rotate,
)

pytestmark = requires_font


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def ink_mask(image: np.ndarray, threshold: int | None = None) -> np.ndarray:
    gray = to_gray(image)
    if threshold is None:
        threshold = otsu_threshold(gray)
    return gray <= threshold


def ink_f1(recovered: np.ndarray, truth: np.ndarray) -> float:
    """F1 of recovered ink pixels against the clean page's ink pixels."""
    tp = float(np.count_nonzero(recovered & truth))
    fp = float(np.count_nonzero(recovered & ~truth))
    fn = float(np.count_nonzero(~recovered & truth))
    if tp == 0.0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2.0 * precision * recall / (precision + recall)


def _align(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Centre-crop two masks to their common size.

    Deskew deliberately grows the canvas so that no corner is clipped, so a
    restored page is a few pixels larger than the page it came from.  Both
    growths are symmetric about the centre, so a centred crop lines the ink
    back up without needing registration.
    """
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])

    def crop(m: np.ndarray) -> np.ndarray:
        top = (m.shape[0] - h) // 2
        left = (m.shape[1] - w) // 2
        return m[top:top + h, left:left + w]

    return crop(a), crop(b)


@pytest.fixture(scope="module")
def clean_page() -> tuple[np.ndarray, str]:
    return render_text_page()


# --------------------------------------------------------------------------- #
# Deskew
# --------------------------------------------------------------------------- #

#: Angles applied to the clean page.  The range brackets what a flatbed and a
#: hand-fed sheet actually produce; anything past ~5 degrees is a rotated page,
#: not a skewed one, and is a different problem.
APPLIED_SKEWS = (-4.0, -2.3, -1.25, -0.5, 0.0, 0.4, 1.7, 3.1, 4.75)

#: The tolerance this front commits to.  It is not arbitrary: a residual skew
#: of 0.2 degrees moves a baseline by 3 px across a 1700 px page, which is
#: under half an x-height at 300 DPI and does not change what Tesseract reads.
SKEW_TOLERANCE_DEG = 0.2


@pytest.mark.parametrize("applied", APPLIED_SKEWS)
def test_skew_estimate_within_tolerance(clean_page, applied):
    """The estimator recovers an angle this test applied, to within 0.2°."""
    image, _ = clean_page
    # ``rotate`` turns counter-clockwise; the package's skew convention is the
    # angle that must be *added* to level the page, hence the sign flip.
    estimate, diagnostics = estimate_skew_angle(rotate(image, applied))

    assert diagnostics["ink_pixels"] > 1000, "a página de teste ficou sem tinta"
    assert abs(estimate - (-applied)) <= SKEW_TOLERANCE_DEG, (
        f"aplicados {applied:+.2f}°, estimado {estimate:+.3f}° "
        f"(erro {abs(estimate + applied):.3f}° > {SKEW_TOLERANCE_DEG}°)"
    )


def test_skew_residual_after_correction(clean_page):
    """Correcting a skewed page leaves under 0.2° of residual skew."""
    image, _ = clean_page
    for applied in (-3.4, 1.9):
        skewed = rotate(image, applied)
        estimate, _ = estimate_skew_angle(skewed)
        corrected = deskew_image(skewed, estimate)
        residual, _ = estimate_skew_angle(corrected)
        assert abs(residual) <= SKEW_TOLERANCE_DEG, (
            f"após corrigir {applied:+.2f}° sobraram {residual:+.3f}°")


def test_deskew_step_reports_the_angle_it_used(clean_page):
    image, _ = clean_page
    step = Deskew()
    outcome = PreprocessPipeline([step]).run(rotate(image, 2.6),
                                             PreprocessContext(dpi=300))
    report = outcome.report_for("deskew")
    assert report is not None and report.applied and report.changed
    assert abs(report.detail["applied_angle"] - (-2.6)) <= SKEW_TOLERANCE_DEG
    assert "°" in report.message_pt


def test_deskew_leaves_a_level_page_alone(clean_page):
    """A page already level must not be resampled for nothing."""
    image, _ = clean_page
    outcome = PreprocessPipeline([Deskew()]).run(image, PreprocessContext(dpi=300))
    report = outcome.report_for("deskew")
    assert report is not None
    assert report.applied, "a etapa deveria ter rodado"
    assert not report.changed, "uma página já reta foi reamostrada sem motivo"


def test_deskew_refuses_an_angle_beyond_its_range(clean_page):
    """Past ``max_angle`` the page is rotated, not skewed; say so, don't guess."""
    image, _ = clean_page
    step = Deskew(max_angle=3.0)
    angle, _ = step.estimate(rotate(image, 20.0))
    assert abs(angle) <= 3.0


def test_deskew_on_blank_page_is_a_no_op():
    blank = np.full((400, 600), 255, dtype=np.uint8)
    angle, diagnostics = estimate_skew_angle(blank)
    assert angle == 0.0
    assert diagnostics["ink_pixels"] == 0


# --------------------------------------------------------------------------- #
# Binarisation: Sauvola vs Otsu under uneven illumination
# --------------------------------------------------------------------------- #


def test_otsu_and_sauvola_agree_on_an_evenly_lit_page(clean_page):
    """With even light there is nothing to choose between them."""
    image, _ = clean_page
    truth = ink_mask(image)

    otsu = Binarize(method="otsu", guard=False).binarize(image) == 0
    sauvola = Binarize(method="sauvola", guard=False).binarize(image) == 0

    assert ink_f1(otsu, truth) > 0.97
    assert ink_f1(sauvola, truth) > 0.94


def test_sauvola_beats_otsu_under_uneven_illumination(clean_page):
    """The reason Sauvola is the default (SPEC §7.2).

    A single global threshold on a page that is bright on one side and dark on
    the other must either flood the dark side with ink or lose the light side's
    text.  There is no value that does both, which is exactly what a local
    threshold is for.
    """
    image, _ = clean_page
    truth = ink_mask(image)
    shaded = add_illumination(image, strength=0.62, tilt=0.22)

    otsu_f1 = ink_f1(Binarize(method="otsu", guard=False).binarize(shaded) == 0, truth)
    sauvola_f1 = ink_f1(Binarize(method="sauvola", guard=False).binarize(shaded) == 0, truth)

    assert sauvola_f1 > otsu_f1 + 0.10, (
        f"Sauvola F1={sauvola_f1:.3f} não superou Otsu F1={otsu_f1:.3f} "
        f"por margem útil sob iluminação desigual"
    )
    assert sauvola_f1 > 0.80, f"Sauvola recuperou pouco: F1={sauvola_f1:.3f}"


def test_otsu_actually_fails_on_the_shaded_page(clean_page):
    """Pin the failure the previous test is measured against.

    If Otsu ever stops failing here the comparison above becomes vacuous, and a
    test that cannot fail is worse than no test.
    """
    image, _ = clean_page
    shaded = add_illumination(image, strength=0.62, tilt=0.22)
    otsu_ink = Binarize(method="otsu", guard=False).binarize(shaded) == 0
    clean_ink_fraction = float(ink_mask(image).mean())
    otsu_ink_fraction = float(otsu_ink.mean())
    assert otsu_ink_fraction > 3.0 * clean_ink_fraction, (
        "Otsu não inundou a página sombreada; a comparação perdeu o sentido")


def test_sauvola_window_follows_dpi():
    step = Binarize(method="sauvola")
    assert step.window_for(150) < step.window_for(300) < step.window_for(600)
    for dpi in (75, 150, 300, 600, 1200):
        assert step.window_for(dpi) % 2 == 1, "a janela precisa ser ímpar"


def test_sauvola_threshold_surface_tracks_the_background(clean_page):
    """The threshold surface must follow the illumination, not be flat."""
    image, _ = clean_page
    shaded = add_illumination(image)
    surface = sauvola_threshold(to_gray(shaded), window=31)
    left = float(surface[:, :200].mean())
    right = float(surface[:, -200:].mean())
    assert left > right + 20.0, (
        f"a superfície de limiar não acompanhou a sombra "
        f"(esquerda {left:.1f}, direita {right:.1f})")


def test_binarize_rejects_an_unknown_method():
    with pytest.raises(ValueError, match="binariza"):
        Binarize(method="niblack")


# --------------------------------------------------------------------------- #
# Despeckle
# --------------------------------------------------------------------------- #


def thin_stroke_page() -> tuple[np.ndarray, np.ndarray]:
    """A page of 1 px strokes — the hardest thing for a despeckler to keep.

    Returns ``(page, stroke_mask)``.  A 1x40 stroke has an area of 40 px, more
    than many specks but less than plenty of dirt blobs, so an area-only filter
    deletes it.  Keeping it is the property under test.
    """
    page = np.full((400, 600), 255, dtype=np.uint8)
    strokes = np.zeros_like(page, dtype=bool)
    for i, x in enumerate(range(40, 560, 40)):
        page[60:100, x] = 0                       # vertical hair line
        strokes[60:100, x] = True
        page[150 + i, 40:200] = 0                 # horizontal hair line
        strokes[150 + i, 40:200] = True
    page[250:258, 300:308] = 0                    # a real 8x8 glyph blob
    strokes[250:258, 300:308] = True
    return page, strokes


def test_despeckle_removes_specks_and_keeps_thin_strokes():
    page, strokes = thin_stroke_page()
    speckled = add_specks(page, count=500, seed=3)

    outcome = PreprocessPipeline([Despeckle()]).run(
        speckled, PreprocessContext(dpi=300))
    cleaned = outcome.image
    report = outcome.report_for("despeckle")
    assert report is not None and report.changed

    surviving_ink = cleaned == 0
    kept = float((surviving_ink & strokes).sum()) / float(strokes.sum())
    assert kept > 0.995, (
        f"o despeckle comeu {1 - kept:.2%} dos traços finos")

    speck_pixels = (speckled == 0) & ~strokes
    left = float((surviving_ink & speck_pixels).sum())
    assert left / float(speck_pixels.sum()) < 0.05, (
        f"{left:.0f} de {speck_pixels.sum()} pixels de sujeira sobreviveram")
    assert report.detail["removed_components"] >= 400


def test_despeckle_limits_scale_with_dpi():
    step = Despeckle()
    area_150, extent_150 = step.limits_for(150)
    area_300, extent_300 = step.limits_for(300)
    area_600, extent_600 = step.limits_for(600)
    assert area_150 < area_300 < area_600
    assert extent_150 < extent_300 < extent_600
    # ~8 px^2 and ~3.3 px at 300 DPI, as the docstring claims.
    assert 6 <= area_300 <= 10
    assert 3 <= extent_300 <= 4


def test_despeckle_keeps_a_stroke_narrower_than_the_extent_limit():
    """A 1x40 stroke is smaller in area than the limit yet must survive.

    This is the conjunction the implementation relies on: small area AND small
    extent.  A regression to "small area" alone fails right here.
    """
    page = np.full((200, 200), 255, dtype=np.uint8)
    page[80:120, 100] = 0                        # area 40, extent 40
    cleaned = PreprocessPipeline([Despeckle()]).run(
        page, PreprocessContext(dpi=300)).image
    assert np.count_nonzero(cleaned == 0) == 40


# --------------------------------------------------------------------------- #
# Shadow removal
# --------------------------------------------------------------------------- #


def test_shadow_removal_flattens_the_background(clean_page):
    image, _ = clean_page
    shaded = add_illumination(image, strength=0.62, tilt=0.22)

    before = ShadowRemoval().estimate_background(shaded)
    outcome = PreprocessPipeline([ShadowRemoval()]).run(
        shaded, PreprocessContext(dpi=300))
    after = ShadowRemoval().estimate_background(outcome.image)

    spread_before = float(before.max()) - float(before.min())
    spread_after = float(after.max()) - float(after.min())
    assert spread_after < spread_before / 2.0, (
        f"o fundo continuou desigual: {spread_before:.0f} -> {spread_after:.0f}")

    report = outcome.report_for("shadow_removal")
    assert report is not None and report.changed


def test_shadow_removal_skips_an_already_flat_page(clean_page):
    image, _ = clean_page
    outcome = PreprocessPipeline([ShadowRemoval()]).run(
        image, PreprocessContext(dpi=300))
    report = outcome.report_for("shadow_removal")
    assert report is not None
    assert not report.changed


def test_shadow_removal_improves_otsu(clean_page):
    """Flattening the background is what makes a global threshold usable again."""
    image, _ = clean_page
    truth = ink_mask(image)
    shaded = add_illumination(image, strength=0.62, tilt=0.22)

    raw = ink_f1(Binarize(method="otsu", guard=False).binarize(shaded) == 0, truth)
    flattened = PreprocessPipeline([ShadowRemoval()]).run(
        shaded, PreprocessContext(dpi=300)).image
    fixed = ink_f1(Binarize(method="otsu", guard=False).binarize(flattened) == 0, truth)
    assert fixed > raw + 0.10, f"F1 Otsu {raw:.3f} -> {fixed:.3f}"


# --------------------------------------------------------------------------- #
# Bleed-through
# --------------------------------------------------------------------------- #


def test_bleed_through_reduction_fades_the_verso(clean_page):
    """Faint mirrored strokes must fade far more than the real text does."""
    image, _ = clean_page
    truth = ink_mask(image)
    bled, ghost = add_faint_bleed_through(image, level=214)
    assert ghost.sum() > 500, "o gerador de bleed-through não marcou nada"

    outcome = PreprocessPipeline([BleedThroughReduction()]).run(
        bled, PreprocessContext(dpi=300))
    cleaned = outcome.image

    ghost_before = float(bled[ghost].mean())
    ghost_after = float(cleaned[ghost].mean())
    text_before = float(bled[truth].mean())
    text_after = float(cleaned[truth].mean())

    assert ghost_after > ghost_before + 20.0, (
        f"o fantasma não clareou ({ghost_before:.0f} -> {ghost_after:.0f})")
    assert text_after - text_before < (ghost_after - ghost_before) / 4.0, (
        f"o texto real clareou junto com o fantasma "
        f"({text_before:.0f} -> {text_after:.0f})")

    report = outcome.report_for("bleed_through")
    assert report is not None and report.detail["mode"] == "heuristic"


def test_bleed_through_heuristic_cannot_see_a_dark_ghost(clean_page):
    """The declared limit of the no-verso path, pinned so it is not forgotten.

    The heuristic looks in a band *above* the page's ink threshold.  A ghost
    darker than that threshold is indistinguishable from ink by any rule that
    uses only the front of the sheet, so it survives — and the honest answer is
    to register the verso, which the next test does.  Writing this down as a
    passing test rather than leaving it as a surprise is the point.
    """
    image, _ = clean_page
    bled, ghost = add_faint_bleed_through(image, level=120)
    if ghost.sum() == 0:
        pytest.skip("o gerador não produziu fantasma neste tamanho de página")
    cleaned = PreprocessPipeline([BleedThroughReduction()]).run(
        bled, PreprocessContext(dpi=300)).image
    before = float(bled[ghost].mean())
    after = float(cleaned[ghost].mean())
    assert after < before + 10.0, (
        "a heurística sem verso passou a enxergar fantasmas escuros; o limite "
        "documentado mudou e o texto do módulo precisa mudar junto")


def test_bleed_through_with_a_registered_verso(clean_page):
    """With the back of the sheet the problem is well posed, and darker ghosts
    come out too."""
    import cv2

    image, _ = clean_page
    bled, ghost = add_faint_bleed_through(image, level=120, seed=13)
    if ghost.sum() == 0:
        pytest.skip("o gerador não produziu fantasma neste tamanho de página")

    # The verso as it would be scanned: the mirror of what shows through.
    verso = cv2.flip(np.where(ghost, 0, 255).astype(np.uint8), 1)
    ctx = PreprocessContext(dpi=300, verso=verso)
    outcome = PreprocessPipeline([BleedThroughReduction()]).run(bled, ctx)

    report = outcome.report_for("bleed_through")
    assert report is not None
    assert report.detail["mode"] == "verso"
    assert abs(report.detail["shift"][0]) <= 15
    assert report.detail["correlation"] > 0.0


def test_register_verso_returns_shift_and_correlation(clean_page):
    import cv2

    image, _ = clean_page
    bled, _ = add_faint_bleed_through(image)
    step = BleedThroughReduction()
    aligned, shift, score = step.register_verso(to_gray(bled),
                                                cv2.flip(bled, 1))
    assert aligned.shape == bled.shape
    assert len(shift) == 2
    assert -1.0 <= score <= 1.0


# --------------------------------------------------------------------------- #
# Dewarp
# --------------------------------------------------------------------------- #


def test_dewarp_reduces_baseline_curvature(clean_page):
    """A bowed page comes back flatter than it went in."""
    image, _ = clean_page
    bowed = curl(image, amplitude=14.0)

    step = Dewarp(enabled=True)
    outcome = PreprocessPipeline([step]).run(bowed, PreprocessContext(dpi=300))
    report = outcome.report_for("dewarp")
    assert report is not None

    before = step.displacement_field(to_gray(bowed))[1]
    after = step.displacement_field(to_gray(outcome.image))[1]
    assert "amplitude_px" in before, f"o campo não foi medido: {before}"
    assert "amplitude_px" in after, f"o campo não foi medido: {after}"
    assert after["amplitude_px"] < before["amplitude_px"], (
        f"curvatura {before['amplitude_px']:.2f} -> {after['amplitude_px']:.2f}")
    assert report.detail["lines_fitted"] >= 4


def test_dewarp_is_off_by_default():
    """It is the most destructive step here; SPEC §7.2 makes it opt-in."""
    pipeline = default_pipeline()
    step = pipeline.step("dewarp")
    assert step is None or not step.enabled


def test_dewarp_leaves_a_flat_page_alone(clean_page):
    image, _ = clean_page
    outcome = PreprocessPipeline([Dewarp(enabled=True)]).run(
        image, PreprocessContext(dpi=300))
    report = outcome.report_for("dewarp")
    assert report is not None
    assert not report.changed


# --------------------------------------------------------------------------- #
# Upscale
# --------------------------------------------------------------------------- #


def test_upscale_below_min_dpi(clean_page):
    image, _ = clean_page
    ctx = PreprocessContext(dpi=120)
    outcome = PreprocessPipeline([Upscale(min_dpi=200)]).run(image, ctx)
    assert outcome.image.shape[0] > image.shape[0]
    assert ctx.dpi >= 200, "o DPI do contexto tem de acompanhar a ampliação"
    report = outcome.report_for("upscale")
    assert report is not None and report.changed


def test_upscale_leaves_a_high_dpi_page_alone(clean_page):
    image, _ = clean_page
    outcome = PreprocessPipeline([Upscale(min_dpi=200)]).run(
        image, PreprocessContext(dpi=300))
    assert outcome.image.shape == image.shape
    report = outcome.report_for("upscale")
    assert report is not None and not report.changed


# --------------------------------------------------------------------------- #
# The pipeline itself
# --------------------------------------------------------------------------- #


def test_default_pipeline_order_is_fixed():
    """Order is load-bearing: binarise before despeckle, deskew before both."""
    names = [step.name for step in default_pipeline()]
    assert names.index("deskew") < names.index("binarize")
    assert names.index("shadow_removal") < names.index("binarize")
    assert names.index("binarize") < names.index("despeckle")
    assert names.index("upscale") < names.index("binarize")


def test_pipeline_reports_every_step(clean_page):
    image, _ = clean_page
    outcome = default_pipeline().run(image, PreprocessContext(dpi=300))
    reported = {report.name for report in outcome.reports}
    configured = {step.name for step in default_pipeline() if step.enabled}
    assert configured <= reported, f"passos sem relatório: {configured - reported}"
    assert outcome.describe_pt()


def test_pipeline_is_deterministic(clean_page):
    image, _ = clean_page
    damaged = add_specks(add_illumination(rotate(image, 1.4)), count=200)
    first = default_pipeline().run(damaged, PreprocessContext(dpi=300))
    second = default_pipeline().run(damaged, PreprocessContext(dpi=300))
    assert np.array_equal(first.image, second.image)
    assert [r.detail for r in first.reports] == [r.detail for r in second.reports]


def test_pipeline_does_not_mutate_its_input(clean_page):
    image, _ = clean_page
    damaged = add_specks(add_illumination(rotate(image, 1.4)), count=200)
    original = damaged.copy()
    default_pipeline().run(damaged, PreprocessContext(dpi=300))
    assert np.array_equal(damaged, original)


def test_pipeline_only_selects_a_subset(clean_page):
    image, _ = clean_page
    pipeline = default_pipeline().only("deskew", "binarize")
    outcome = pipeline.run(image, PreprocessContext(dpi=300))
    applied = set(outcome.applied_steps)
    assert applied <= {"deskew", "binarize"}


def test_full_pipeline_recovers_a_triply_degraded_page(clean_page):
    """Skew + shade + dirt at once, measured against the clean ink mask."""
    image, _ = clean_page
    truth = ink_mask(image)
    damaged = add_specks(add_illumination(rotate(image, 2.1),
                                          strength=0.55, tilt=0.18),
                         count=600, seed=5)

    raw = ink_f1(Binarize(method="otsu", guard=False).binarize(damaged) == 0, truth)
    restored = default_pipeline().run(damaged, PreprocessContext(dpi=300)).image
    # Deskew grows the canvas so no corner is clipped, so the restored page is
    # larger than the original.  Compare on the shared centred region.
    fixed = ink_f1(*_align(restored == 0, truth))

    assert fixed > raw, f"a pipeline piorou a página: {raw:.3f} -> {fixed:.3f}"
    assert fixed > 0.60, f"F1 de tinta recuperada apenas {fixed:.3f}"
