"""SPEC 5.2 -- every run property, set explicitly, serialised, restored.

The table in SPEC 5.2 is a promise to the user: eight families of typographic
property that must reach PDF, DOCX, EPUB/HTML and LaTeX. The IR cannot keep that
promise if it cannot *hold* the property, so this module does two things:

1. asserts that each row of the SPEC table maps onto named ``RunProps`` fields
   -- by name, so deleting a field breaks the test rather than the product;
2. builds a ``RunProps`` with **every** field set to a non-default value and
   round-trips it, which is the only way to catch a field the codec skips.

``test_maximal_run_props_sets_every_declared_field`` is the guard that keeps
this honest: add a field to ``RunProps`` without adding it here and the suite
fails.
"""

from __future__ import annotations

import math
from dataclasses import fields

import pytest

from caissa.core.model import (
    Alignment,
    Border,
    Borders,
    BorderStyle,
    Color,
    ColorSpace,
    EmphasisMark,
    FontFeature,
    FontStretch,
    FontWeight,
    LengthUnit,
    LigatureMode,
    LineSpacing,
    LineSpacingRule,
    Measure,
    NumberingRef,
    NumeralFigure,
    NumeralSpacing,
    Padding,
    ParagraphProps,
    RunProps,
    SmallCapsMode,
    StrikeStyle,
    TabAlignment,
    TabLeader,
    TabStop,
    Text,
    TextDirection,
    TextOutline,
    TextShadow,
    TextTransform,
    UnderlineStyle,
    VariationAxis,
    VerticalAlign,
    node_from_payload,
    node_to_payload,
)
from caissa.core.model.serialize import SerializationError, decode_value, encode_value

# --------------------------------------------------------------------------- #
# The SPEC 5.2 table, transcribed
# --------------------------------------------------------------------------- #

#: Each row of the SPEC 5.2 property table, mapped to the fields that carry it.
SPEC_5_2_ROWS: dict[str, tuple[str, ...]] = {
    "familia, tamanho, peso, italico": (
        "font_family",
        "font_fallbacks",
        "font_size",
        "font_weight",
        "italic",
        "oblique_angle",
        "font_stretch",
    ),
    "cor de texto e realce": ("color", "highlight", "background"),
    "espacamento entre letras (tracking)": (
        "letter_spacing",
        "word_spacing",
        "horizontal_scale",
    ),
    "kerning e ligaduras": (
        "kerning",
        "kerning_min_size",
        "ligatures",
        "font_features",
    ),
    "versalete real vs sintetico": ("small_caps",),
    "deslocamento de linha de base": (
        "baseline_shift",
        "rise_relative",
        "vertical_align",
    ),
    "idioma (hifenizacao / leitor de tela)": ("language", "hyphenate"),
    "variacoes OpenType": ("variation_axes",),
}


def maximal_run_props() -> RunProps:
    """A ``RunProps`` with every single field set away from its default."""
    return RunProps(
        style="LanceChave",
        font_family="Minion Pro",
        font_fallbacks=("Source Serif", "DejaVu Serif"),
        font_size=Measure(value=10.5, unit=LengthUnit.PT),
        font_weight=437,
        italic=True,
        oblique_angle=-12.5,
        font_stretch=FontStretch.SEMI_CONDENSED,
        color=Color.rgb8(17, 34, 51),
        highlight=Color.named("amarelo"),
        background=Color.cmyk(0.1, 0.2, 0.3, 0.05),
        letter_spacing=Measure(value=0.02, unit=LengthUnit.EM),
        word_spacing=Measure(value=-0.5, unit=LengthUnit.PT),
        horizontal_scale=97.5,
        kerning=True,
        kerning_min_size=Measure(value=8.0, unit=LengthUnit.PT),
        ligatures=LigatureMode.DISCRETIONARY,
        font_features=(FontFeature(tag="ss01", value=1), FontFeature(tag="liga", value=0)),
        variation_axes=(
            VariationAxis(tag="wght", value=612.5),
            VariationAxis(tag="opsz", value=11.0),
        ),
        small_caps=SmallCapsMode.REAL,
        text_transform=TextTransform.UPPERCASE,
        baseline_shift=Measure(value=1.5, unit=LengthUnit.PT),
        rise_relative=0.22,
        vertical_align=VerticalAlign.SUPERSCRIPT,
        language="pt-BR",
        numeral_figure=NumeralFigure.OLDSTYLE,
        numeral_spacing=NumeralSpacing.TABULAR,
        underline=UnderlineStyle.WAVY_DOUBLE,
        underline_color=Color.gray(0.4),
        underline_thickness=Measure(value=0.6, unit=LengthUnit.PT),
        underline_offset=Measure(value=-1.2, unit=LengthUnit.PT),
        underline_skip_ink=False,
        strikethrough=StrikeStyle.DOUBLE,
        strikethrough_color=Color.spot("PANTONE 032 U", Color.rgb(0.9, 0.1, 0.2)),
        overline=True,
        outline=TextOutline(
            width=Measure(value=0.3, unit=LengthUnit.PT),
            color=Color.rgb(0.0, 0.0, 0.0),
            fill=False,
        ),
        shadow=TextShadow(
            offset_x=Measure(value=0.8, unit=LengthUnit.PT),
            offset_y=Measure(value=1.2, unit=LengthUnit.PT),
            blur=Measure(value=2.0, unit=LengthUnit.PT),
            color=Color.gray(0.7),
        ),
        emboss=True,
        engrave=True,
        emphasis_mark=EmphasisMark.UNDER_DOT,
        opacity=0.85,
        hyphenate=False,
        spell_check=False,
        direction=TextDirection.RTL,
        no_break=True,
        hidden=True,
    )


def maximal_paragraph_props() -> ParagraphProps:
    """A ``ParagraphProps`` with every field set away from its default."""
    return ParagraphProps(
        style="Corpo",
        alignment=Alignment.JUSTIFY,
        indent_left=Measure(value=18.0, unit=LengthUnit.PT),
        indent_right=Measure(value=6.0, unit=LengthUnit.PT),
        indent_first_line=Measure(value=-12.0, unit=LengthUnit.PT),
        space_before=Measure(value=4.0, unit=LengthUnit.PT),
        space_after=Measure(value=8.0, unit=LengthUnit.PT),
        contextual_spacing=True,
        line_spacing=LineSpacing(
            rule=LineSpacingRule.EXACT,
            value=1.0,
            length=Measure(value=13.0, unit=LengthUnit.PT),
        ),
        keep_together=True,
        keep_with_next=True,
        page_break_before=True,
        widow_control=False,
        outline_level=2,
        tab_stops=(
            TabStop(
                position=Measure(value=120.0, unit=LengthUnit.PT),
                alignment=TabAlignment.DECIMAL,
                leader=TabLeader.DOT,
            ),
        ),
        borders=Borders(
            top=Border(style=BorderStyle.DOUBLE, width=Measure(value=1.0, unit=LengthUnit.PT)),
            bottom=Border(style=BorderStyle.WAVE, color=Color.gray(0.2)),
        ),
        padding=Padding(top=Measure(value=2.0, unit=LengthUnit.PT)),
        shading=Color.rgb8(240, 240, 235),
        direction=TextDirection.LTR,
        hyphenate=True,
        suppress_line_numbers=True,
        numbering=NumberingRef(definition="Titulo1", level=1, start_override=7),
        mark_props=RunProps(font_weight=700),
        default_run=RunProps(font_family="Merida"),
    )


# --------------------------------------------------------------------------- #
# Completeness
# --------------------------------------------------------------------------- #


def test_every_spec_5_2_row_maps_onto_declared_fields():
    declared = {item.name for item in fields(RunProps)}
    for row, names in SPEC_5_2_ROWS.items():
        missing = set(names) - declared
        assert not missing, f"SPEC 5.2 row {row!r} has no field for {sorted(missing)}"


def test_maximal_run_props_sets_every_declared_field():
    """The guard: a new ``RunProps`` field must be added to the fixture above."""
    props = maximal_run_props()
    default = RunProps()
    unset = [
        item.name
        for item in fields(RunProps)
        if getattr(props, item.name) == getattr(default, item.name)
    ]
    assert unset == [], f"fields never exercised by the SPEC 5.2 test: {unset}"


def test_maximal_paragraph_props_sets_every_declared_field():
    props = maximal_paragraph_props()
    default = ParagraphProps()
    unset = [
        item.name
        for item in fields(ParagraphProps)
        if getattr(props, item.name) == getattr(default, item.name)
    ]
    assert unset == [], f"paragraph fields never exercised: {unset}"


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def test_maximal_run_props_round_trips():
    props = maximal_run_props()
    payload = encode_value(props)
    assert decode_value(payload, RunProps) == props


def test_maximal_run_props_round_trips_field_by_field():
    """A whole-object comparison hides which field died; this one names it."""
    props = maximal_run_props()
    restored = decode_value(encode_value(props), RunProps)
    for item in fields(RunProps):
        assert getattr(restored, item.name) == getattr(props, item.name), item.name


def test_maximal_paragraph_props_round_trips_field_by_field():
    props = maximal_paragraph_props()
    restored = decode_value(encode_value(props), ParagraphProps)
    for item in fields(ParagraphProps):
        assert getattr(restored, item.name) == getattr(props, item.name), item.name


def test_run_props_reach_a_text_node_and_survive():
    text = Text(content="Cf3 e a jogada", props=maximal_run_props())
    restored = node_from_payload(node_to_payload(text), Text)
    assert restored == text
    assert restored.props.small_caps is SmallCapsMode.REAL


def test_empty_run_props_serialise_to_nothing_but_a_tag():
    payload = encode_value(RunProps())
    assert payload == {"type": "run_props"}
    assert RunProps().is_empty
    assert not maximal_run_props().is_empty


def test_paragraph_props_is_empty_agrees_with_equality():
    assert ParagraphProps().is_empty
    assert not maximal_paragraph_props().is_empty


# --------------------------------------------------------------------------- #
# Individual property semantics
# --------------------------------------------------------------------------- #


def test_bold_reads_font_weight_not_a_separate_flag():
    """SPEC 5.2 says "peso", not "negrito": weight is the honest model."""
    assert RunProps().bold is None
    assert RunProps(font_weight=400).bold is False
    assert RunProps(font_weight=599).bold is False
    assert RunProps(font_weight=600).bold is True
    assert RunProps(font_weight=900).bold is True


def test_font_weight_enum_projects_to_integers():
    assert FontWeight.BOLD.to_int() == 700
    assert FontWeight.REGULAR.to_int() == 400
    assert {member.to_int() for member in FontWeight} == {
        100,
        200,
        300,
        400,
        500,
        600,
        700,
        800,
        900,
    }


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (LengthUnit.PT, 12.0),
        (LengthUnit.PX, 9.0),
        (LengthUnit.INCH, 864.0),
        (LengthUnit.PICA, 144.0),
        (LengthUnit.TWIP, 0.6),
    ],
)
def test_measure_converts_absolute_units_to_points(unit, expected):
    assert Measure(value=12.0, unit=unit).to_points() == pytest.approx(expected)


@pytest.mark.parametrize("unit", [LengthUnit.EM, LengthUnit.EX, LengthUnit.REM, LengthUnit.PERCENT])
def test_relative_measures_refuse_to_pretend_they_are_absolute(unit):
    measure = Measure(value=1.5, unit=unit)
    assert not measure.is_absolute
    with pytest.raises(ValueError, match=r"relativa|absoluta|converte"):
        measure.to_points()


def test_measure_constructors():
    assert Measure.points(11.0).unit is LengthUnit.PT
    assert Measure.percent(50.0).unit is LengthUnit.PERCENT
    assert Measure.em(1.25).unit is LengthUnit.EM
    assert str(Measure.points(11.0)) == "11pt"


@pytest.mark.parametrize(
    ("text", "expected_hex"),
    [
        ("#112233", "#112233"),
        ("112233", "#112233"),
        ("#123", "#112233"),
        ("#11223344", "#112233"),
    ],
)
def test_colour_hex_round_trips(text, expected_hex):
    assert Color.from_hex(text).to_hex() == expected_hex


def test_colour_hex_carries_alpha_when_asked():
    colour = Color.from_hex("#11223380")
    assert colour.alpha == pytest.approx(0x80 / 255.0)
    assert colour.to_hex(include_alpha=True).endswith("80")


def test_colour_spaces_declare_their_component_count():
    assert Color.rgb(0.1, 0.2, 0.3).expected_component_count() == 3
    assert Color.cmyk(0.1, 0.2, 0.3, 0.4).expected_component_count() == 4
    assert Color.gray(0.5).expected_component_count() == 1
    assert Color.named("vermelho").expected_component_count() is None


def test_cmyk_converts_to_rgb_for_preview():
    red, green, blue = Color.cmyk(0.0, 1.0, 1.0, 0.0).to_rgb_tuple()
    assert (red, green, blue) == pytest.approx((1.0, 0.0, 0.0))


def test_spot_colour_keeps_its_name_and_its_fallback():
    spot = Color.spot("PANTONE 032 U", Color.rgb(0.9, 0.1, 0.2))
    assert spot.space is ColorSpace.SPOT
    assert spot.name == "PANTONE 032 U"
    assert spot.to_rgb_tuple() == pytest.approx((0.9, 0.1, 0.2))
    assert decode_value(encode_value(spot), Color) == spot


def test_automatic_colour_has_no_numeric_value():
    auto = Color.automatic()
    assert auto.space is ColorSpace.AUTO
    with pytest.raises(ValueError, match="componentes"):
        auto.to_rgb_tuple()


# --------------------------------------------------------------------------- #
# Merging -- the mechanism the whole style cascade is built on
# --------------------------------------------------------------------------- #


def test_merge_lets_unspecified_fields_fall_through():
    base = RunProps(font_family="Minion Pro", font_size=Measure.points(10.0), italic=True)
    override = RunProps(font_size=Measure.points(12.0))
    merged = base.merged_with(override)
    assert merged.font_family == "Minion Pro"
    assert merged.font_size == Measure.points(12.0)
    assert merged.italic is True


def test_merge_treats_false_as_specified_but_none_as_absent():
    """``italic=False`` must win over ``italic=True``; ``None`` must not."""
    base = RunProps(italic=True)
    assert base.merged_with(RunProps(italic=False)).italic is False
    assert base.merged_with(RunProps()).italic is True


def test_merge_treats_the_empty_tuple_as_absent():
    base = RunProps(font_fallbacks=("A", "B"))
    assert base.merged_with(RunProps()).font_fallbacks == ("A", "B")
    assert base.merged_with(RunProps(font_fallbacks=("C",))).font_fallbacks == ("C",)


def test_merging_an_empty_override_returns_the_same_object():
    base = maximal_run_props()
    assert base.merged_with(RunProps()) is base


def test_merge_is_associative_over_three_layers():
    a = RunProps(font_family="A", italic=True)
    b = RunProps(font_family="B")
    c = RunProps(italic=False)
    assert a.merged_with(b).merged_with(c) == a.merged_with(b.merged_with(c))


def test_paragraph_props_merge_the_same_way():
    base = ParagraphProps(alignment=Alignment.LEFT, keep_together=True)
    merged = base.merged_with(ParagraphProps(alignment=Alignment.CENTER))
    assert merged.alignment is Alignment.CENTER
    assert merged.keep_together is True


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_floats_are_refused_rather_than_written_as_invalid_json(value):
    props = RunProps(opacity=value)
    with pytest.raises(SerializationError, match="finito"):
        encode_value(props)


def test_bad_hex_literal_is_refused():
    with pytest.raises(ValueError, match="hexadecimal"):
        Color.from_hex("#xyz")


def test_props_are_immutable():
    props = RunProps(italic=True)
    with pytest.raises((AttributeError, TypeError)):
        props.italic = False  # type: ignore[misc]
