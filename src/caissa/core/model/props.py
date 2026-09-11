"""Formatting property model: lengths, colours, run properties, paragraph properties.

This module is the concrete answer to SPEC section 5.2. Its governing rule is
the *exporter's golden rule*: no exporter may silently drop a property. That is
only enforceable if the property exists here in the first place, expressed
richly enough that an exporter can tell "the author asked for real small caps"
apart from "the author asked for anything that looks like small caps".

Two orthogonal record types carry formatting:

``RunProps``
    Character-level formatting, attached to :class:`~caissa.core.model.inline.Text`
    and to every inline wrapper. Maps to ``w:rPr`` (DOCX), a CSS declaration
    block (EPUB/HTML), a font/graphics-state pair (PDF) and a macro group
    (LaTeX).
``ParagraphProps``
    Block-level formatting. Maps to ``w:pPr``, a CSS block, a paragraph shape
    and the matching length-setting groups respectively.

Every field is optional (``None`` means "not specified at this level"), which is
what makes the three-level cascade in :mod:`caissa.core.model.styles` -- named
style, inherited, direct -- expressible without a separate sentinel type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from typing import Any, Final, TypeVar

from caissa.core.model.registry import ir_node

__all__ = [
    "EMPTY_PARAGRAPH_PROPS",
    "EMPTY_RUN_PROPS",
    "Alignment",
    "Border",
    "BorderStyle",
    "Borders",
    "Color",
    "ColorSpace",
    "EmphasisMark",
    "FontFeature",
    "FontStretch",
    "FontWeight",
    "LengthUnit",
    "LigatureMode",
    "LineSpacing",
    "LineSpacingRule",
    "ListMarkerAlignment",
    "Measure",
    "NumberingRef",
    "NumeralFigure",
    "NumeralSpacing",
    "Padding",
    "ParagraphProps",
    "RunProps",
    "SmallCapsMode",
    "StrikeStyle",
    "TabAlignment",
    "TabLeader",
    "TabStop",
    "TextDirection",
    "TextOutline",
    "TextShadow",
    "TextTransform",
    "UnderlineStyle",
    "VariationAxis",
    "VerticalAlign",
]


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class LengthUnit(StrEnum):
    """Unit of a :class:`Measure`.

    Absolute units convert to points losslessly; relative units (``em``, ``ex``,
    ``rem``, ``percent``) depend on context and are carried through to the
    exporter unresolved, because CSS and LaTeX can express them natively and
    resolving them early would throw away author intent.
    """

    PT = "pt"
    PX = "px"
    MM = "mm"
    CM = "cm"
    INCH = "in"
    PICA = "pc"
    TWIP = "twip"
    EM = "em"
    EX = "ex"
    REM = "rem"
    PERCENT = "%"


class ColorSpace(StrEnum):
    """Colour model of a :class:`Color`."""

    RGB = "rgb"
    CMYK = "cmyk"
    GRAY = "gray"
    SPOT = "spot"
    NAMED = "named"
    AUTO = "auto"
    NONE = "none"


class FontWeight(StrEnum):
    """Named CSS weights, for readability at call sites.

    ``RunProps.font_weight`` stores a plain ``int`` in ``[1, 1000]`` so that
    variable-font weights such as 437 survive; these names exist to spell the
    common values.
    """

    THIN = "100"
    EXTRA_LIGHT = "200"
    LIGHT = "300"
    REGULAR = "400"
    MEDIUM = "500"
    SEMI_BOLD = "600"
    BOLD = "700"
    EXTRA_BOLD = "800"
    BLACK = "900"

    def to_int(self) -> int:
        """Return the numeric weight.

        Returns:
            The CSS weight as an integer.
        """
        return int(self.value)


class FontStretch(StrEnum):
    """Width class of the face, matching the CSS ``font-stretch`` keywords."""

    ULTRA_CONDENSED = "ultra-condensed"
    EXTRA_CONDENSED = "extra-condensed"
    CONDENSED = "condensed"
    SEMI_CONDENSED = "semi-condensed"
    NORMAL = "normal"
    SEMI_EXPANDED = "semi-expanded"
    EXPANDED = "expanded"
    EXTRA_EXPANDED = "extra-expanded"
    ULTRA_EXPANDED = "ultra-expanded"


class SmallCapsMode(StrEnum):
    """How small capitals are produced.

    The distinction is required by SPEC section 5.2 ("versalete real vs
    sintetico") and is not cosmetic: real small caps come from the font's
    ``smcp`` feature and have correct stroke weight; synthetic ones are scaled
    capitals and look thin. An exporter targeting a format that can only fake
    them must record a ``DegradationWarning``.
    """

    NONE = "none"
    REAL = "real"
    SYNTHETIC = "synthetic"
    PETITE = "petite"
    UNICASE = "unicase"


class TextTransform(StrEnum):
    """Case transformation applied at render time, not stored in the text."""

    NONE = "none"
    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    CAPITALIZE = "capitalize"
    FULL_WIDTH = "full-width"


class UnderlineStyle(StrEnum):
    """Underline decoration styles, spanning the DOCX and CSS vocabularies."""

    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"
    THICK = "thick"
    DOTTED = "dotted"
    DOTTED_HEAVY = "dotted-heavy"
    DASHED = "dashed"
    DASHED_HEAVY = "dashed-heavy"
    DASH_LONG = "dash-long"
    DASH_DOT = "dash-dot"
    DASH_DOT_DOT = "dash-dot-dot"
    WAVY = "wavy"
    WAVY_DOUBLE = "wavy-double"
    WAVY_HEAVY = "wavy-heavy"
    WORDS_ONLY = "words-only"


class StrikeStyle(StrEnum):
    """Strikethrough decoration styles."""

    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"


class VerticalAlign(StrEnum):
    """Vertical placement of a run relative to the baseline.

    Distinct from ``baseline_shift``: this is the *semantic* request (a
    superscript footnote marker), while the shift is a typographic nudge in
    absolute units. Exporters need both -- DOCX ``w:vertAlign`` versus
    ``w:position``, CSS ``vertical-align`` versus ``position: relative``.
    """

    BASELINE = "baseline"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"
    TEXT_TOP = "text-top"
    TEXT_BOTTOM = "text-bottom"


class LigatureMode(StrEnum):
    """Which OpenType ligature sets are enabled."""

    NONE = "none"
    STANDARD = "standard"
    CONTEXTUAL = "contextual"
    DISCRETIONARY = "discretionary"
    HISTORICAL = "historical"
    ALL = "all"


class NumeralFigure(StrEnum):
    """Lining versus old-style figures.

    Chess books are full of numbers -- move numbers, diagram numbers, page
    references. Old-style figures inside running text and lining figures inside
    tables is standard practice, so the IR keeps the choice explicit.
    """

    DEFAULT = "default"
    LINING = "lining"
    OLDSTYLE = "oldstyle"


class NumeralSpacing(StrEnum):
    """Proportional versus tabular figure advance widths."""

    DEFAULT = "default"
    PROPORTIONAL = "proportional"
    TABULAR = "tabular"


class EmphasisMark(StrEnum):
    """Emphasis marks drawn beside glyphs (CSS ``text-emphasis``, DOCX ``w:em``)."""

    NONE = "none"
    DOT = "dot"
    COMMA = "comma"
    CIRCLE = "circle"
    UNDER_DOT = "under-dot"


class Alignment(StrEnum):
    """Horizontal paragraph alignment."""

    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    JUSTIFY = "justify"
    JUSTIFY_LOW = "justify-low"
    DISTRIBUTE = "distribute"
    START = "start"
    END = "end"


class LineSpacingRule(StrEnum):
    """Interpretation of :attr:`LineSpacing.value`."""

    MULTIPLE = "multiple"
    EXACT = "exact"
    AT_LEAST = "at-least"


class ListMarkerAlignment(StrEnum):
    """Alignment of a list marker inside the slot reserved for it."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class TabAlignment(StrEnum):
    """Alignment of text against a tab stop."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    DECIMAL = "decimal"
    BAR = "bar"


class TabLeader(StrEnum):
    """Filler drawn in the run-up to a tab stop (a table of contents needs dots)."""

    NONE = "none"
    DOT = "dot"
    HYPHEN = "hyphen"
    UNDERSCORE = "underscore"
    MIDDLE_DOT = "middle-dot"


class BorderStyle(StrEnum):
    """Stroke pattern of a border edge."""

    NONE = "none"
    SOLID = "solid"
    DOUBLE = "double"
    DOTTED = "dotted"
    DASHED = "dashed"
    DASH_DOT = "dash-dot"
    DASH_DOT_DOT = "dash-dot-dot"
    GROOVE = "groove"
    RIDGE = "ridge"
    INSET = "inset"
    OUTSET = "outset"
    WAVE = "wave"
    THICK_THIN = "thick-thin"
    THIN_THICK = "thin-thick"


class TextDirection(StrEnum):
    """Base writing direction."""

    LTR = "ltr"
    RTL = "rtl"


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #

_POINTS_PER_UNIT: Final[dict[LengthUnit, float]] = {
    LengthUnit.PT: 1.0,
    LengthUnit.PX: 0.75,
    LengthUnit.MM: 72.0 / 25.4,
    LengthUnit.CM: 72.0 / 2.54,
    LengthUnit.INCH: 72.0,
    LengthUnit.PICA: 12.0,
    LengthUnit.TWIP: 1.0 / 20.0,
}


@ir_node("measure")
@dataclass(frozen=True, slots=True, kw_only=True)
class Measure:
    """A scalar length with a unit.

    Named ``Measure`` rather than ``Length`` to avoid colliding with the
    everyday word in exporter code and to keep ``len``-adjacent naming clear.

    Attributes:
        value: The magnitude. May be negative (a hanging indent, a raised
            baseline).
        unit: The unit the magnitude is expressed in.
    """

    value: float
    unit: LengthUnit = LengthUnit.PT

    @classmethod
    def points(cls, value: float) -> Measure:
        """Build a measure in typographic points.

        Args:
            value: Magnitude in points.

        Returns:
            The measure.
        """
        return cls(value=value, unit=LengthUnit.PT)

    @classmethod
    def percent(cls, value: float) -> Measure:
        """Build a relative measure expressed as a percentage.

        Args:
            value: Magnitude as a percentage (``100.0`` means "unchanged").

        Returns:
            The measure.
        """
        return cls(value=value, unit=LengthUnit.PERCENT)

    @classmethod
    def em(cls, value: float) -> Measure:
        """Build a measure relative to the current font size.

        Args:
            value: Magnitude in ems.

        Returns:
            The measure.
        """
        return cls(value=value, unit=LengthUnit.EM)

    @property
    def is_absolute(self) -> bool:
        """Whether the unit can be converted to points without context."""
        return self.unit in _POINTS_PER_UNIT

    def to_points(self) -> float:
        """Convert to typographic points.

        Returns:
            The magnitude in points.

        Raises:
            ValueError: If the unit is relative and therefore context-dependent.
        """
        factor = _POINTS_PER_UNIT.get(self.unit)
        if factor is None:
            msg = f"unidade relativa {self.unit.value!r} nao converte para pontos sem contexto"
            raise ValueError(msg)
        return self.value * factor

    def __str__(self) -> str:
        """Render as a compact CSS-like literal (``12pt``, ``-0.5em``)."""
        text = f"{self.value:g}"
        return f"{text}{self.unit.value}"


#: Digit counts of the two abbreviated hexadecimal colour literals.
_HEX_SHORT: Final = 3
_HEX_SHORT_ALPHA: Final = 4

#: Component counts that identify a colour space by shape alone.
_RGB_COMPONENTS: Final = 3
_CMYK_COMPONENTS: Final = 4

#: Weight at or above which a run counts as bold (OpenType convention).
_BOLD_THRESHOLD: Final = 600

_HEX_RE: Final = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

_EXPECTED_COMPONENTS: Final[dict[ColorSpace, int]] = {
    ColorSpace.RGB: 3,
    ColorSpace.CMYK: 4,
    ColorSpace.GRAY: 1,
}


@ir_node("color")
@dataclass(frozen=True, slots=True, kw_only=True)
class Color:
    """A colour in one of several spaces.

    CMYK and spot colours are not decoration: a chess publisher sending a book
    to press works in process or two-colour spot, and converting to RGB on
    import would destroy that. PDF and LaTeX carry them natively; DOCX and
    EPUB/HTML cannot, so exporters convert and record a ``DegradationWarning``.

    Attributes:
        space: The colour model.
        components: Channel values in ``[0, 1]``; three for RGB, four for CMYK,
            one for gray, and any number for a spot colour's alternate space.
        alpha: Opacity in ``[0, 1]``.
        name: Colour name for ``NAMED`` and ``SPOT`` spaces (a CSS keyword, a
            theme colour, or a Pantone reference).
    """

    space: ColorSpace = ColorSpace.RGB
    components: tuple[float, ...] = ()
    alpha: float = 1.0
    name: str | None = None

    @classmethod
    def rgb(cls, red: float, green: float, blue: float, alpha: float = 1.0) -> Color:
        """Build an RGB colour from channel values in ``[0, 1]``.

        Args:
            red: Red channel.
            green: Green channel.
            blue: Blue channel.
            alpha: Opacity.

        Returns:
            The colour.
        """
        return cls(space=ColorSpace.RGB, components=(red, green, blue), alpha=alpha)

    @classmethod
    def rgb8(cls, red: int, green: int, blue: int, alpha: float = 1.0) -> Color:
        """Build an RGB colour from 8-bit channel values.

        Args:
            red: Red channel, ``0``-``255``.
            green: Green channel, ``0``-``255``.
            blue: Blue channel, ``0``-``255``.
            alpha: Opacity.

        Returns:
            The colour.
        """
        return cls.rgb(red / 255.0, green / 255.0, blue / 255.0, alpha)

    @classmethod
    def cmyk(cls, cyan: float, magenta: float, yellow: float, black: float) -> Color:
        """Build a process colour.

        Args:
            cyan: Cyan ink, ``0``-``1``.
            magenta: Magenta ink, ``0``-``1``.
            yellow: Yellow ink, ``0``-``1``.
            black: Key/black ink, ``0``-``1``.

        Returns:
            The colour.
        """
        return cls(space=ColorSpace.CMYK, components=(cyan, magenta, yellow, black))

    @classmethod
    def gray(cls, level: float) -> Color:
        """Build a grayscale colour.

        Args:
            level: Luminance, ``0`` (black) to ``1`` (white).

        Returns:
            The colour.
        """
        return cls(space=ColorSpace.GRAY, components=(level,))

    @classmethod
    def spot(cls, name: str, fallback: Color | None = None) -> Color:
        """Build a named spot colour with an optional process fallback.

        Args:
            name: The ink name, e.g. ``"PANTONE 032 U"``.
            fallback: Alternate-space colour used when the target format cannot
                carry spot inks.

        Returns:
            The colour.
        """
        components = fallback.components if fallback is not None else ()
        return cls(space=ColorSpace.SPOT, components=components, name=name)

    @classmethod
    def named(cls, name: str) -> Color:
        """Build a colour referenced only by name (CSS keyword or theme slot).

        Args:
            name: The colour name.

        Returns:
            The colour.
        """
        return cls(space=ColorSpace.NAMED, components=(), name=name)

    @classmethod
    def automatic(cls) -> Color:
        """Return the "automatic" colour, meaning "whatever the reader's theme says".

        Returns:
            The automatic colour.
        """
        return cls(space=ColorSpace.AUTO, components=())

    @classmethod
    def from_hex(cls, text: str) -> Color:
        """Parse ``#rgb``, ``#rgba``, ``#rrggbb`` or ``#rrggbbaa``.

        Args:
            text: The hexadecimal literal, with or without a leading ``#``.

        Returns:
            The parsed RGB colour.

        Raises:
            ValueError: If the literal is malformed.
        """
        if not _HEX_RE.match(text):
            msg = f"literal hexadecimal de cor invalido: {text!r}"
            raise ValueError(msg)
        digits = text.lstrip("#")
        if len(digits) in (_HEX_SHORT, _HEX_SHORT_ALPHA):
            digits = "".join(char * 2 for char in digits)
        channels = [
            int(digits[index : index + 2], 16) / 255.0 for index in range(0, len(digits), 2)
        ]
        alpha = channels[3] if len(channels) == _CMYK_COMPONENTS else 1.0
        return cls.rgb(channels[0], channels[1], channels[2], alpha)

    def to_hex(self, *, include_alpha: bool = False) -> str:
        """Render as an ``#rrggbb`` literal, converting from CMYK or gray if needed.

        Args:
            include_alpha: Append the alpha channel as two extra digits.

        Returns:
            The hexadecimal literal.

        Raises:
            ValueError: If the colour has no numeric components (``NAMED``,
                ``AUTO`` or ``NONE`` without a fallback).
        """
        red, green, blue = self.to_rgb_tuple()
        digits = f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"
        if include_alpha:
            digits += f"{round(self.alpha * 255):02x}"
        return digits

    def to_rgb_tuple(self) -> tuple[float, float, float]:
        """Convert to RGB channel values in ``[0, 1]``.

        CMYK uses the naive ``(1 - ink)(1 - key)`` conversion, which is what a
        screen preview wants; a colour-managed exporter should do its own
        profile-aware conversion from :attr:`components` instead.

        Returns:
            The red, green and blue channels.

        Raises:
            ValueError: If the colour carries no numeric components.
        """
        if self.space is ColorSpace.RGB and len(self.components) >= _RGB_COMPONENTS:
            return (self.components[0], self.components[1], self.components[2])
        if self.space is ColorSpace.GRAY and len(self.components) >= 1:
            level = self.components[0]
            return (level, level, level)
        if len(self.components) >= _CMYK_COMPONENTS:
            cyan, magenta, yellow, key = self.components[:4]
            return (
                (1.0 - cyan) * (1.0 - key),
                (1.0 - magenta) * (1.0 - key),
                (1.0 - yellow) * (1.0 - key),
            )
        if len(self.components) >= _RGB_COMPONENTS:
            return (self.components[0], self.components[1], self.components[2])
        msg = f"cor {self.space.value!r} sem componentes numericos nao converte para RGB"
        raise ValueError(msg)

    def expected_component_count(self) -> int | None:
        """Return how many components this space requires, or ``None`` if free.

        Returns:
            The required component count, or ``None`` when the space imposes no
            constraint (``SPOT``, ``NAMED``, ``AUTO``, ``NONE``).
        """
        return _EXPECTED_COMPONENTS.get(self.space)


@ir_node("font_feature")
@dataclass(frozen=True, slots=True, kw_only=True)
class FontFeature:
    """A raw OpenType feature setting, e.g. ``ss01=1`` or ``liga=0``.

    Chess fonts routinely expose stylistic sets for alternate piece shapes, so
    the escape hatch of naming a four-letter tag directly is genuinely used.

    Attributes:
        tag: The four-character OpenType feature tag.
        value: The feature selector; ``0`` disables, ``1`` enables, larger
            values pick an alternate.
    """

    tag: str
    value: int = 1


@ir_node("variation_axis")
@dataclass(frozen=True, slots=True, kw_only=True)
class VariationAxis:
    """A position along one OpenType variable-font axis.

    Attributes:
        tag: Four-character axis tag, e.g. ``wght``, ``wdth``, ``opsz``,
            ``slnt``, or a foundry-private axis.
        value: The coordinate on that axis, in the axis's own units.
    """

    tag: str
    value: float


@ir_node("text_outline")
@dataclass(frozen=True, slots=True, kw_only=True)
class TextOutline:
    """Stroked glyph outline (DOCX ``w:outline``, CSS ``-webkit-text-stroke``).

    Attributes:
        width: Stroke width; ``None`` means the format default hairline.
        color: Stroke colour; ``None`` means the text colour.
        fill: Whether the glyph interior is still painted. ``False`` gives
            hollow display capitals, a common chapter-opener treatment.
    """

    width: Measure | None = None
    color: Color | None = None
    fill: bool = True


@ir_node("text_shadow")
@dataclass(frozen=True, slots=True, kw_only=True)
class TextShadow:
    """A drop shadow behind glyphs.

    Attributes:
        offset_x: Horizontal displacement.
        offset_y: Vertical displacement, positive downwards.
        blur: Blur radius; zero gives a hard shadow.
        color: Shadow colour.
    """

    offset_x: Measure = Measure(value=1.0, unit=LengthUnit.PT)
    offset_y: Measure = Measure(value=1.0, unit=LengthUnit.PT)
    blur: Measure | None = None
    color: Color | None = None


@ir_node("tab_stop")
@dataclass(frozen=True, slots=True, kw_only=True)
class TabStop:
    """One tab stop in a paragraph's ruler.

    Attributes:
        position: Distance from the text-area left edge.
        alignment: How text sits against the stop.
        leader: Filler drawn in the run-up to the stop.
    """

    position: Measure
    alignment: TabAlignment = TabAlignment.LEFT
    leader: TabLeader = TabLeader.NONE


@ir_node("border")
@dataclass(frozen=True, slots=True, kw_only=True)
class Border:
    """One edge of a border box.

    Attributes:
        style: Stroke pattern.
        width: Stroke width.
        color: Stroke colour.
        space: Gap between the stroke and the content it encloses.
        shadow: Whether the format should draw the edge with a shadow.
    """

    style: BorderStyle = BorderStyle.NONE
    width: Measure | None = None
    color: Color | None = None
    space: Measure | None = None
    shadow: bool = False


@ir_node("borders")
@dataclass(frozen=True, slots=True, kw_only=True)
class Borders:
    """A full border box, including the inside edges used by tables.

    Attributes:
        top: Top edge.
        bottom: Bottom edge.
        left: Left (or start) edge.
        right: Right (or end) edge.
        inside_horizontal: Horizontal rules between rows.
        inside_vertical: Vertical rules between columns.
    """

    top: Border | None = None
    bottom: Border | None = None
    left: Border | None = None
    right: Border | None = None
    inside_horizontal: Border | None = None
    inside_vertical: Border | None = None


@ir_node("padding")
@dataclass(frozen=True, slots=True, kw_only=True)
class Padding:
    """Inner spacing on four sides.

    Attributes:
        top: Space above the content.
        right: Space to the right of the content.
        bottom: Space below the content.
        left: Space to the left of the content.
    """

    top: Measure | None = None
    right: Measure | None = None
    bottom: Measure | None = None
    left: Measure | None = None


@ir_node("line_spacing")
@dataclass(frozen=True, slots=True, kw_only=True)
class LineSpacing:
    """Leading, expressed the way DOCX and CSS both need it.

    Attributes:
        rule: Whether ``value`` is a multiple of single spacing, an exact
            leading, or a minimum.
        value: A multiplier when ``rule`` is ``MULTIPLE``; otherwise a length.
        length: The leading as a length when ``rule`` is ``EXACT`` or
            ``AT_LEAST``.
    """

    rule: LineSpacingRule = LineSpacingRule.MULTIPLE
    value: float = 1.0
    length: Measure | None = None


@ir_node("numbering_ref")
@dataclass(frozen=True, slots=True, kw_only=True)
class NumberingRef:
    """A reference into a numbering definition in the stylesheet.

    Headings and lists both point at a numbering definition rather than storing
    literal numbers, which is what makes automatic renumbering possible after
    an edit.

    Attributes:
        definition: Name of a ``ListStyle`` in the stylesheet.
        level: Zero-based nesting level within that definition.
        start_override: Restart the counter at this value on this node.
    """

    definition: str
    level: int = 0
    start_override: int | None = None


# --------------------------------------------------------------------------- #
# RunProps
# --------------------------------------------------------------------------- #


@ir_node("run_props")
@dataclass(frozen=True, slots=True, kw_only=True)
class RunProps:
    """Character-level formatting, the complete SPEC section 5.2 model.

    Every field is optional. ``None`` means *unspecified at this level*, which
    is what lets :func:`caissa.core.model.styles.resolve_run_props` layer a
    named style, an inherited context and direct formatting without a separate
    "inherit" sentinel. Tuple-valued fields use the empty tuple for the same
    purpose.

    ``style`` lives inside ``RunProps`` deliberately: OOXML puts ``w:rStyle``
    inside ``w:rPr``, so the mapping stays one-to-one.

    Attributes:
        style: Name of a character style in the document stylesheet.
        font_family: Primary typeface name.
        font_fallbacks: Ordered fallback families, used when the primary family
            lacks a glyph -- essential for mixed Latin/Cyrillic chess texts.
        font_size: Type size.
        font_weight: Numeric weight in ``[1, 1000]``; ``700`` is bold.
        italic: True italic (a separate face), not a slant.
        oblique_angle: Synthetic slant in degrees, for faces with no italic.
        font_stretch: Width class of the face.
        color: Foreground colour.
        highlight: Marker-pen highlight behind the glyphs (DOCX ``w:highlight``).
        background: Background shading fill, distinct from ``highlight``.
        letter_spacing: Tracking; added to every advance width.
        word_spacing: Extra space added at word boundaries.
        horizontal_scale: Horizontal glyph scaling as a percentage.
        kerning: Whether pair kerning is applied.
        kerning_min_size: Size above which kerning applies (DOCX ``w:kern``).
        ligatures: Which OpenType ligature sets are active.
        font_features: Raw OpenType feature settings.
        variation_axes: OpenType variable-font axis coordinates.
        small_caps: Real, synthetic, petite or no small capitals.
        text_transform: Case transformation applied at render time.
        baseline_shift: Vertical nudge in absolute units.
        vertical_align: Semantic superscript/subscript request.
        language: BCP-47 tag driving hyphenation, spell-check and screen
            readers.
        numeral_figure: Lining versus old-style figures.
        numeral_spacing: Proportional versus tabular figures.
        underline: Underline decoration style.
        underline_color: Underline colour; ``None`` follows the text colour.
        underline_thickness: Explicit underline weight.
        underline_offset: Distance from baseline to underline.
        underline_skip_ink: Whether descenders interrupt the underline.
        strikethrough: Strikethrough decoration style.
        strikethrough_color: Strikethrough colour.
        overline: Rule drawn above the glyphs.
        outline: Stroked glyph outline.
        shadow: Drop shadow.
        emboss: Raised relief effect (DOCX ``w:emboss``).
        engrave: Incised relief effect (DOCX ``w:imprint``).
        emphasis_mark: Emphasis marks drawn beside glyphs.
        opacity: Overall run opacity in ``[0, 1]``.
        hyphenate: Whether the run may be hyphenated.
        spell_check: Whether proofing tools should inspect the run. Chess
            notation runs set this to ``False``.
        direction: Base writing direction for the run.
        no_break: Whether the run must not be split across lines.
        hidden: Whether the run is present but not rendered.
        rise_relative: Baseline shift expressed relative to the font size, kept
            alongside ``baseline_shift`` because LaTeX and CSS prefer it.
    """

    style: str | None = None

    # -- face --------------------------------------------------------------
    font_family: str | None = None
    font_fallbacks: tuple[str, ...] = ()
    font_size: Measure | None = None
    font_weight: int | None = None
    italic: bool | None = None
    oblique_angle: float | None = None
    font_stretch: FontStretch | None = None

    # -- colour ------------------------------------------------------------
    color: Color | None = None
    highlight: Color | None = None
    background: Color | None = None

    # -- spacing and micro-typography --------------------------------------
    letter_spacing: Measure | None = None
    word_spacing: Measure | None = None
    horizontal_scale: float | None = None
    kerning: bool | None = None
    kerning_min_size: Measure | None = None
    ligatures: LigatureMode | None = None
    font_features: tuple[FontFeature, ...] = ()
    variation_axes: tuple[VariationAxis, ...] = ()

    # -- case and position -------------------------------------------------
    small_caps: SmallCapsMode | None = None
    text_transform: TextTransform | None = None
    baseline_shift: Measure | None = None
    rise_relative: float | None = None
    vertical_align: VerticalAlign | None = None

    # -- language ----------------------------------------------------------
    language: str | None = None

    # -- figures -----------------------------------------------------------
    numeral_figure: NumeralFigure | None = None
    numeral_spacing: NumeralSpacing | None = None

    # -- decoration --------------------------------------------------------
    underline: UnderlineStyle | None = None
    underline_color: Color | None = None
    underline_thickness: Measure | None = None
    underline_offset: Measure | None = None
    underline_skip_ink: bool | None = None
    strikethrough: StrikeStyle | None = None
    strikethrough_color: Color | None = None
    overline: bool | None = None
    outline: TextOutline | None = None
    shadow: TextShadow | None = None
    emboss: bool | None = None
    engrave: bool | None = None
    emphasis_mark: EmphasisMark | None = None
    opacity: float | None = None

    # -- behaviour ---------------------------------------------------------
    hyphenate: bool | None = None
    spell_check: bool | None = None
    direction: TextDirection | None = None
    no_break: bool | None = None
    hidden: bool | None = None

    @property
    def is_empty(self) -> bool:
        """Whether nothing at all is specified, so the record can be omitted."""
        return self == EMPTY_RUN_PROPS

    @property
    def bold(self) -> bool | None:
        """Convenience read of ``font_weight`` as a boolean bold flag."""
        if self.font_weight is None:
            return None
        return self.font_weight >= _BOLD_THRESHOLD

    def merged_with(self, override: RunProps) -> RunProps:
        """Overlay ``override`` on top of ``self``.

        Any field the override specifies wins; anything it leaves unspecified
        (``None``, or the empty tuple for sequence fields) falls through to
        ``self``. This is the single primitive the whole style cascade is built
        from.

        Args:
            override: The properties that take precedence.

        Returns:
            A new record combining both.
        """
        return _merge_props(self, override)


EMPTY_RUN_PROPS: Final = RunProps()


# --------------------------------------------------------------------------- #
# ParagraphProps
# --------------------------------------------------------------------------- #


@ir_node("paragraph_props")
@dataclass(frozen=True, slots=True, kw_only=True)
class ParagraphProps:
    """Block-level formatting, the paragraph counterpart of :class:`RunProps`.

    Attributes:
        style: Name of a paragraph style in the document stylesheet.
        alignment: Horizontal alignment.
        indent_left: Left (start-side) indent.
        indent_right: Right (end-side) indent.
        indent_first_line: Extra indent on the first line; negative gives a
            hanging indent.
        space_before: Space above the paragraph.
        space_after: Space below the paragraph.
        contextual_spacing: Suppress ``space_before``/``space_after`` between
            consecutive paragraphs of the same style.
        line_spacing: Leading.
        keep_together: Forbid a page break inside the paragraph.
        keep_with_next: Forbid a page break between this paragraph and the next
            -- how a caption stays attached to its diagram.
        page_break_before: Force a page break above the paragraph.
        widow_control: Forbid single lines stranded at a page boundary.
        outline_level: Depth in the document outline, driving PDF bookmarks and
            the EPUB navigation document.
        tab_stops: Explicit tab ruler.
        borders: Paragraph border box.
        padding: Space between border and text.
        shading: Background fill.
        direction: Base writing direction.
        hyphenate: Whether the paragraph may be hyphenated.
        suppress_line_numbers: Exclude from line numbering.
        numbering: Reference into a numbering definition.
        mark_props: Formatting of the paragraph mark itself (DOCX
            ``w:pPr/w:rPr``), which determines the height of an empty
            paragraph.
        default_run: Run properties inherited by every run in the paragraph,
            before per-run direct formatting.
    """

    style: str | None = None
    alignment: Alignment | None = None
    indent_left: Measure | None = None
    indent_right: Measure | None = None
    indent_first_line: Measure | None = None
    space_before: Measure | None = None
    space_after: Measure | None = None
    contextual_spacing: bool | None = None
    line_spacing: LineSpacing | None = None
    keep_together: bool | None = None
    keep_with_next: bool | None = None
    page_break_before: bool | None = None
    widow_control: bool | None = None
    outline_level: int | None = None
    tab_stops: tuple[TabStop, ...] = ()
    borders: Borders | None = None
    padding: Padding | None = None
    shading: Color | None = None
    direction: TextDirection | None = None
    hyphenate: bool | None = None
    suppress_line_numbers: bool | None = None
    numbering: NumberingRef | None = None
    mark_props: RunProps | None = None
    default_run: RunProps | None = None

    @property
    def is_empty(self) -> bool:
        """Whether nothing at all is specified, so the record can be omitted."""
        return self == EMPTY_PARAGRAPH_PROPS

    def merged_with(self, override: ParagraphProps) -> ParagraphProps:
        """Overlay ``override`` on top of ``self``.

        Args:
            override: The properties that take precedence.

        Returns:
            A new record combining both.
        """
        return _merge_props(self, override)


EMPTY_PARAGRAPH_PROPS: Final = ParagraphProps()


# --------------------------------------------------------------------------- #
# Merge primitive
# --------------------------------------------------------------------------- #


_P = TypeVar("_P", RunProps, ParagraphProps)


def _is_unspecified(value: object) -> bool:
    """Report whether a property field carries no author intent.

    Args:
        value: A field value.

    Returns:
        ``True`` for ``None`` and for the empty tuple.
    """
    return value is None or value == ()


def _merge_props(base: _P, override: _P) -> _P:
    """Overlay one property record on another, field by field.

    This is the single primitive the whole style cascade is built from: a field
    the override leaves unspecified falls through, a field it specifies wins.
    There is deliberately no "explicitly inherit" sentinel -- an empty tuple and
    ``None`` both mean "say nothing here", which is what every source format
    (OOXML toggle properties, CSS unset, LaTeX groups) also means.

    Args:
        base: The lower-precedence record.
        override: The higher-precedence record.

    Returns:
        A new record of the same type; fields specified by ``override`` win, the
        rest come from ``base``. Returns ``base`` unchanged when the override
        adds nothing, so a deep cascade does not allocate.
    """
    if base is override:
        return base
    names = tuple(item.name for item in fields(base))
    # ``Any`` rather than ``object``: the values are heterogeneous by
    # construction, and ``dataclasses.replace`` type-checks each keyword against
    # its own field.
    changed: dict[str, Any] = {}
    for name in names:
        override_value = getattr(override, name)
        if _is_unspecified(override_value):
            continue
        if getattr(base, name) != override_value:
            changed[name] = override_value
    if not changed:
        return base
    return replace(base, **changed)
