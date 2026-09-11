"""The style cascade: named style -> inherited -> direct formatting.

Four layers, each beating the one before it:

1. document defaults (``StyleSheet.default_run`` / ``default_paragraph``);
2. the named style, walking ``based_on`` from the root ancestor down;
3. inherited context (the paragraph's run defaults, then enclosing wrappers);
4. direct formatting on the node itself.

Every test here pins one boundary between two adjacent layers, because that is
where a cascade actually goes wrong: getting the *set* of layers right is easy,
getting their order right is not, and a DOCX that opens with the wrong font is
almost always an inverted pair somewhere in this list.
"""

from __future__ import annotations

import pytest

from caissa.core.model import (
    Alignment,
    CharacterStyle,
    Color,
    DiagramStyle,
    DiagramStyleDef,
    LengthUnit,
    ListStyle,
    ListStyleLevel,
    Measure,
    ParagraphProps,
    ParagraphStyle,
    RunProps,
    StyleError,
    StyleSheet,
    TableStyle,
    resolve_paragraph_props,
    resolve_run_props,
    style_chain,
)
from caissa.core.model.serialize import decode_value, encode_value

PT = LengthUnit.PT


def pt(value: float) -> Measure:
    """A measure in points, spelled short because this module is full of them."""
    return Measure(value=value, unit=PT)


@pytest.fixture
def sheet() -> StyleSheet:
    """A stylesheet with a real inheritance chain in each family."""
    return StyleSheet(
        default_paragraph=ParagraphProps(alignment=Alignment.LEFT, space_after=pt(0.0)),
        default_run=RunProps(font_family="DocumentDefault", font_size=pt(9.0), italic=False),
        paragraph_styles=(
            ParagraphStyle(
                name="Base",
                paragraph=ParagraphProps(alignment=Alignment.JUSTIFY, indent_left=pt(0.0)),
                run=RunProps(font_family="BaseFamily", font_size=pt(10.0)),
            ),
            ParagraphStyle(
                name="Corpo",
                based_on="Base",
                paragraph=ParagraphProps(indent_first_line=pt(12.0)),
                run=RunProps(font_size=pt(11.0)),
            ),
            ParagraphStyle(
                name="Variante",
                based_on="Corpo",
                paragraph=ParagraphProps(indent_left=pt(18.0)),
                run=RunProps(italic=True),
            ),
        ),
        character_styles=(
            CharacterStyle(
                name="Notacao",
                props=RunProps(font_family="Merida", font_size=pt(10.0), kerning=True),
            ),
            CharacterStyle(
                name="LanceChave",
                based_on="Notacao",
                props=RunProps(font_weight=700, color=Color.rgb8(180, 0, 0)),
            ),
        ),
        table_styles=(
            TableStyle(name="TabelaBase"),
            TableStyle(name="Aberturas", based_on="TabelaBase", band_size=2),
        ),
        list_styles=(
            ListStyle(name="Numerada", levels=(ListStyleLevel(level=0, start=1),)),
            ListStyle(name="Exercicios", based_on="Numerada"),
        ),
        diagram_styles=(
            DiagramStyleDef(name="Diagrama", style=DiagramStyle(piece_set="merida")),
            DiagramStyleDef(
                name="DiagramaGrande",
                based_on="Diagrama",
                style=DiagramStyle(size=pt(180.0)),
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# The chain itself
# --------------------------------------------------------------------------- #


def test_chain_runs_root_first(sheet):
    assert style_chain(sheet, "Variante", "paragraph") == ("Base", "Corpo", "Variante")


def test_chain_of_a_root_style_is_just_itself(sheet):
    assert style_chain(sheet, "Base", "paragraph") == ("Base",)


@pytest.mark.parametrize(
    ("kind", "name", "expected"),
    [
        ("paragraph", "Corpo", ("Base", "Corpo")),
        ("character", "LanceChave", ("Notacao", "LanceChave")),
        ("table", "Aberturas", ("TabelaBase", "Aberturas")),
        ("list", "Exercicios", ("Numerada", "Exercicios")),
        ("diagram", "DiagramaGrande", ("Diagrama", "DiagramaGrande")),
    ],
)
def test_every_style_family_resolves_its_chain(sheet, kind, name, expected):
    assert style_chain(sheet, name, kind) == expected


def test_unknown_family_is_refused_with_the_valid_options_named(sheet):
    with pytest.raises(StyleError, match="familia de estilo desconhecida"):
        style_chain(sheet, "Corpo", "paragrafo")


def test_undefined_name_ends_the_walk_quietly_by_default(sheet):
    assert style_chain(sheet, "NaoExiste", "paragraph") == ()


def test_undefined_name_raises_under_strict(sheet):
    with pytest.raises(StyleError, match="nao definido"):
        style_chain(sheet, "NaoExiste", "paragraph", strict=True)


def test_a_missing_parent_truncates_the_chain_rather_than_inventing_one():
    sheet = StyleSheet(
        paragraph_styles=(ParagraphStyle(name="Filho", based_on="PaiAusente"),),
    )
    assert style_chain(sheet, "Filho", "paragraph") == ("Filho",)


def test_a_cycle_raises_instead_of_looping_forever():
    sheet = StyleSheet(
        character_styles=(
            CharacterStyle(name="A", based_on="B"),
            CharacterStyle(name="B", based_on="A"),
        ),
    )
    with pytest.raises(StyleError, match="ciclo"):
        style_chain(sheet, "A", "character")


def test_a_style_based_on_itself_is_a_cycle():
    sheet = StyleSheet(character_styles=(CharacterStyle(name="A", based_on="A"),))
    with pytest.raises(StyleError, match="ciclo"):
        style_chain(sheet, "A", "character")


def test_a_very_deep_chain_is_refused_rather_than_recursed():
    depth = 64
    styles = tuple(
        CharacterStyle(name=f"S{i}", based_on=f"S{i - 1}" if i else None) for i in range(depth)
    )
    sheet = StyleSheet(character_styles=styles)
    with pytest.raises(StyleError, match="excede"):
        style_chain(sheet, f"S{depth - 1}", "character")


# --------------------------------------------------------------------------- #
# Layer precedence, one boundary at a time
# --------------------------------------------------------------------------- #


def test_document_default_applies_when_nothing_else_speaks(sheet):
    resolved = resolve_run_props(sheet)
    assert resolved.font_family == "DocumentDefault"
    assert resolved.font_size == pt(9.0)


def test_named_style_beats_the_document_default(sheet):
    resolved = resolve_run_props(sheet, style_name="Notacao")
    assert resolved.font_family == "Merida"


def test_a_child_style_beats_its_parent(sheet):
    resolved = resolve_run_props(sheet, style_name="LanceChave")
    assert resolved.font_family == "Merida", "inherited from Notacao"
    assert resolved.font_weight == 700, "set by LanceChave itself"


def test_inherited_context_beats_the_named_style(sheet):
    resolved = resolve_run_props(
        sheet,
        style_name="Notacao",
        inherited=RunProps(font_family="Herdada"),
    )
    assert resolved.font_family == "Herdada"
    assert resolved.kerning is True, "unmentioned by the inherited layer, so it falls through"


def test_direct_formatting_beats_inherited_context(sheet):
    resolved = resolve_run_props(
        sheet,
        RunProps(font_family="Direta"),
        inherited=RunProps(font_family="Herdada"),
        style_name="Notacao",
    )
    assert resolved.font_family == "Direta"


def test_the_full_four_layer_order_in_one_assertion(sheet):
    """One run, four layers, four different fields -- each layer wins exactly one."""
    resolved = resolve_run_props(
        sheet,
        RunProps(color=Color.rgb8(0, 0, 255)),
        inherited=RunProps(letter_spacing=pt(0.4)),
        style_name="Notacao",
    )
    assert resolved.italic is False, "layer 1: document default"
    assert resolved.font_family == "Merida", "layer 2: named style"
    assert resolved.letter_spacing == pt(0.4), "layer 3: inherited"
    assert resolved.color == Color.rgb8(0, 0, 255), "layer 4: direct"


def test_direct_props_name_their_own_style(sheet):
    """``RunProps.style`` is how a run says which character style it wears."""
    resolved = resolve_run_props(sheet, RunProps(style="Notacao"))
    assert resolved.font_family == "Merida"


def test_explicit_style_name_overrides_the_one_in_the_props(sheet):
    resolved = resolve_run_props(sheet, RunProps(style="Notacao"), style_name="LanceChave")
    assert resolved.font_weight == 700


def test_an_unknown_style_is_ignored_by_default_and_raises_under_strict(sheet):
    assert resolve_run_props(sheet, style_name="Fantasma").font_family == "DocumentDefault"
    with pytest.raises(StyleError, match="nao definido"):
        resolve_run_props(sheet, style_name="Fantasma", strict=True)


# --------------------------------------------------------------------------- #
# Paragraphs resolve two layers in lockstep
# --------------------------------------------------------------------------- #


def test_paragraph_style_reaches_both_the_paragraph_and_its_runs(sheet):
    resolved = resolve_paragraph_props(sheet, style_name="Corpo")
    assert resolved.paragraph.alignment is Alignment.JUSTIFY, "from Base"
    assert resolved.paragraph.indent_first_line == pt(12.0), "from Corpo"
    assert resolved.run.font_family == "BaseFamily", "run block of Base"
    assert resolved.run.font_size == pt(11.0), "run block of Corpo overrides Base"


def test_paragraph_chain_applies_root_first(sheet):
    resolved = resolve_paragraph_props(sheet, style_name="Variante")
    assert resolved.paragraph.indent_left == pt(18.0), "Variante overrides Base"
    assert resolved.paragraph.indent_first_line == pt(12.0), "still inherited from Corpo"
    assert resolved.run.italic is True


def test_direct_paragraph_formatting_beats_the_style(sheet):
    resolved = resolve_paragraph_props(
        sheet,
        ParagraphProps(alignment=Alignment.CENTER),
        style_name="Corpo",
    )
    assert resolved.paragraph.alignment is Alignment.CENTER


def test_inherited_paragraph_props_sit_between_style_and_direct(sheet):
    resolved = resolve_paragraph_props(
        sheet,
        ParagraphProps(indent_right=pt(3.0)),
        inherited=ParagraphProps(alignment=Alignment.RIGHT, indent_right=pt(99.0)),
        style_name="Corpo",
    )
    assert resolved.paragraph.alignment is Alignment.RIGHT, "inherited beat the style"
    assert resolved.paragraph.indent_right == pt(3.0), "direct beat inherited"


def test_paragraph_default_run_becomes_the_baseline_for_its_runs(sheet):
    """A paragraph can set the character baseline for everything inside it."""
    resolved = resolve_paragraph_props(
        sheet,
        ParagraphProps(default_run=RunProps(font_family="DoParagrafo")),
        style_name="Corpo",
    )
    assert resolved.run.font_family == "DoParagrafo"


def test_a_run_inside_that_paragraph_still_wins_with_direct_formatting(sheet):
    paragraph = resolve_paragraph_props(
        sheet,
        ParagraphProps(default_run=RunProps(font_family="DoParagrafo", font_size=pt(8.0))),
        style_name="Corpo",
    )
    run = resolve_run_props(sheet, RunProps(font_size=pt(7.0)), inherited=paragraph.run)
    assert run.font_family == "DoParagrafo", "inherited from the paragraph"
    assert run.font_size == pt(7.0), "direct formatting still wins"


def test_nested_inline_wrappers_stack_as_successive_inherited_layers(sheet):
    """Span(font=A) > Emphasis(italic) > Text(size): the SPEC 5.1 nesting model."""
    outer = resolve_run_props(sheet, RunProps(font_family="Externa"))
    middle = resolve_run_props(sheet, RunProps(italic=True), inherited=outer)
    inner = resolve_run_props(sheet, RunProps(font_size=pt(6.0)), inherited=middle)
    assert inner.font_family == "Externa"
    assert inner.italic is True
    assert inner.font_size == pt(6.0)


# --------------------------------------------------------------------------- #
# Lookups and bookkeeping
# --------------------------------------------------------------------------- #


def test_lookups_find_defined_styles_and_return_none_otherwise(sheet):
    assert sheet.paragraph_style("Corpo") is not None
    assert sheet.character_style("Notacao") is not None
    assert sheet.table_style("Aberturas") is not None
    assert sheet.list_style("Numerada") is not None
    assert sheet.diagram_style("Diagrama") is not None
    assert sheet.paragraph_style("Fantasma") is None
    assert sheet.character_style("Fantasma") is None
    assert sheet.table_style("Fantasma") is None
    assert sheet.list_style("Fantasma") is None
    assert sheet.diagram_style("Fantasma") is None


def test_known_names_is_the_union_across_every_family(sheet):
    assert sheet.known_names() == {
        "Base",
        "Corpo",
        "Variante",
        "Notacao",
        "LanceChave",
        "TabelaBase",
        "Aberturas",
        "Numerada",
        "Exercicios",
        "Diagrama",
        "DiagramaGrande",
    }


def test_list_style_levels_are_addressable_by_depth():
    style = ListStyle(
        name="N",
        levels=(ListStyleLevel(level=0, start=1), ListStyleLevel(level=2, start=5)),
    )
    assert style.level(0).start == 1
    assert style.level(2).start == 5
    assert style.level(1) is None


def test_a_stylesheet_round_trips(sheet):
    assert decode_value(encode_value(sheet), StyleSheet) == sheet
