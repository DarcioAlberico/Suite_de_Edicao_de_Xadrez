"""Deterministic synthetic Document IR, for round-trip and coverage tests.

Two generators live here.

``NodeFactory``
    Builds random but *reproducible* documents from a seed. Used for the
    ten-thousand-node round-trip corpus the F1 gate requires: same seed, same
    document, every run, so a failure is reproducible from the seed alone.

``construct_minimal``
    Builds one instance of an arbitrary registered IR class by filling its
    required fields from their declared types. Reflection-driven on purpose --
    a node type added later is covered automatically, which is the only way a
    "every node type is constructible and serialisable" test can stay true.
"""

from __future__ import annotations

import random
from dataclasses import MISSING, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, get_origin

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.chess.notation_tables import FigurineSet, MoveRenderStyle, PieceType
from caissa.core.model.base import IRNode
from caissa.core.model.blocks import (
    Block,
    Callout,
    CalloutKind,
    CodeBlock,
    ColumnLayout,
    Endnote,
    Figure,
    FigurePlacement,
    Footnote,
    Group,
    GroupRole,
    Heading,
    ImageBlock,
    ListBlock,
    ListItem,
    ListKind,
    ListMarkerStyle,
    MathBlock,
    PageBreak,
    PageGeometry,
    Paragraph,
    Quote,
    RawPassthrough,
    SectionBreak,
    SectionBreakKind,
    Table,
    TableCell,
    TableColumn,
    TableOfContents,
    TableRow,
    ThematicBreak,
)
from caissa.core.model.diagram import (
    BoardTheme,
    CoordinateStyle,
    Diagram,
    DiagramSource,
    DiagramStyle,
    FenCandidate,
    PiecePlacementStyle,
    RecognitionPath,
    RecognitionResult,
    SquareRepair,
)
from caissa.core.model.document import (
    Contributor,
    ContributorRole,
    Document,
    DocumentMetadata,
    DocumentSettings,
    MetadataEntry,
    Resource,
    ResourceKind,
)
from caissa.core.model.game import (
    ClockAnnotation,
    ClockKind,
    EvalAnnotation,
    EvalKind,
    GameHeaders,
    GameRenderOptions,
    GameScore,
    MoveNode,
    PgnTag,
    VariationStyle,
)
from caissa.core.model.ids import ULID
from caissa.core.model.inline import (
    Anchor,
    Emphasis,
    ImageInline,
    IndexEntry,
    Inline,
    InlineDiagram,
    LineBreak,
    Link,
    LinkKind,
    MathInline,
    Move,
    NagSymbol,
    NonBreakingSpace,
    NoteRef,
    Orientation,
    PieceGlyph,
    RawInline,
    SmallCaps,
    Space,
    SpaceKind,
    Span,
    Strike,
    Strong,
    Subscript,
    Superscript,
    Tab,
    Text,
    Underline,
)
from caissa.core.model.marks import Mark, MarkKind, MarkLineStyle
from caissa.core.model.props import (
    Alignment,
    Border,
    Borders,
    BorderStyle,
    Color,
    EmphasisMark,
    FontFeature,
    FontStretch,
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
    TextDirection,
    TextOutline,
    TextShadow,
    TextTransform,
    UnderlineStyle,
    VariationAxis,
    VerticalAlign,
)
from caissa.core.model.provenance import ConfidenceBand, Provenance, Rect, SourceKind
from caissa.core.model.reflect import field_types
from caissa.core.model.styles import (
    CharacterStyle,
    DiagramStyleDef,
    ListStyle,
    ListStyleLevel,
    ParagraphStyle,
    StyleSheet,
    TableStyle,
)
from caissa.core.model.visitor import walk

WORDS = (
    "abertura",
    "meio-jogo",
    "final",
    "peao",
    "torre",
    "bispo",
    "cavalo",
    "dama",
    "rei",
    "tempo",
    "iniciativa",
    "estrutura",
    "coluna",
    "diagonal",
    "sacrificio",
    "zugzwang",
    "profilaxia",
)

SANS = (
    "e4",
    "e5",
    "Nf3",
    "Nc6",
    "Bb5",
    "a6",
    "Ba4",
    "Nf6",
    "O-O",
    "Be7",
    "Re1",
    "b5",
    "Bb3",
    "d6",
    "c3",
    "O-O",
    "h3",
    "Na5",
    "exd5",
    "cxd4",
    "Qxd8+",
    "Rxf7#",
    "e8=Q",
    "bxa8=N+",
    "Kh1",
    "R1a3",
    "Nbd7",
    "Qh4e1",
)

FENS = (
    STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 4 4",
    "8/8/8/4k3/8/4K3/4P3/8 w - - 0 1",
    "8/5k2/8/8/8/8/5PPP/6K1 w - - 0 1",
    "r4rk1/pp3ppp/2p5/8/8/2N5/PPP2PPP/2KR3R w - - 0 1",
    "4k3/8/8/8/8/8/8/4K2R w K - 0 1",
)

SQUARES = ("a1", "b2", "c3", "d4", "e4", "e5", "f6", "g7", "h8", "d5", "c4", "f7")

LANGUAGES = ("en", "pt", "de", "es", "fr", "it", "ru", "nl")

STYLE_NAMES = (
    "Corpo",
    "Titulo1",
    "Titulo2",
    "Legenda",
    "Notacao",
    "Variante",
    "Enfase",
    "LanceChave",
)


class NodeFactory:
    """Builds reproducible synthetic documents.

    The same seed always produces the same document, so a round-trip failure in
    CI can be reproduced locally from the seed printed in the assertion.
    """

    def __init__(self, seed: int = 0xCA155A) -> None:
        self.random = random.Random(seed)
        self._counter = 0

    # -- primitives --------------------------------------------------------

    def next_ulid(self) -> ULID:
        self._counter += 1
        return ULID.from_parts(1_700_000_000_000 + self._counter, self._counter)

    def word(self) -> str:
        return self.random.choice(WORDS)

    def sentence(self, words: int = 6) -> str:
        return " ".join(self.random.choice(WORDS) for _ in range(words))

    def maybe(self, probability: float = 0.5) -> bool:
        return self.random.random() < probability

    def color(self) -> Color:
        pick = self.random.randrange(4)
        if pick == 0:
            return Color.rgb8(
                self.random.randrange(256), self.random.randrange(256), self.random.randrange(256)
            )
        if pick == 1:
            return Color.cmyk(
                round(self.random.random(), 3),
                round(self.random.random(), 3),
                round(self.random.random(), 3),
                round(self.random.random(), 3),
            )
        if pick == 2:
            return Color.gray(round(self.random.random(), 3))
        return Color.spot("PANTONE 032 U", Color.rgb(0.9, 0.1, 0.2))

    def measure(self) -> Measure:
        return Measure(
            value=round(self.random.uniform(-24.0, 48.0), 3),
            unit=self.random.choice(list(LengthUnit)),
        )

    def provenance(self) -> Provenance:
        return Provenance(
            kind=self.random.choice(list(SourceKind)),
            document_path=f"acervo/{self.word()}.pdf",
            document_hash=f"sha256:{self._counter:064x}",
            page_index=self.random.randrange(500),
            block_index=self.random.randrange(40),
            rect=Rect(
                x=round(self.random.uniform(0, 500), 2),
                y=round(self.random.uniform(0, 700), 2),
                width=round(self.random.uniform(10, 300), 2),
                height=round(self.random.uniform(10, 300), 2),
            ),
            dpi=float(self.random.choice((150, 200, 300, 600))),
            engine=self.random.choice(("tesseract", "surya", "paddle", "vector")),
            engine_version="5.3.4",
            confidence=round(self.random.random(), 4),
            band=self.random.choice(list(ConfidenceBand)),
            extracted_at=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
            verified_by_human=self.maybe(0.2),
            out_of_model=self.maybe(0.1),
            note=self.sentence(3),
        )

    def run_props(self, *, rich: bool = True) -> RunProps:
        if not rich and self.maybe(0.6):
            return RunProps()
        return RunProps(
            style=self.random.choice(STYLE_NAMES) if self.maybe(0.3) else None,
            font_family=self.random.choice(("Minion Pro", "Merida", "Source Serif")),
            font_fallbacks=("DejaVu Serif", "Noto Serif") if self.maybe(0.3) else (),
            font_size=self.measure() if self.maybe(0.7) else None,
            font_weight=self.random.choice((100, 300, 400, 437, 600, 700, 900)),
            italic=self.maybe(),
            oblique_angle=round(self.random.uniform(-15, 15), 2) if self.maybe(0.2) else None,
            font_stretch=self.random.choice(list(FontStretch)),
            color=self.color() if self.maybe(0.6) else None,
            highlight=self.color() if self.maybe(0.2) else None,
            background=self.color() if self.maybe(0.2) else None,
            letter_spacing=self.measure() if self.maybe(0.4) else None,
            word_spacing=self.measure() if self.maybe(0.2) else None,
            horizontal_scale=round(self.random.uniform(80, 120), 1) if self.maybe(0.2) else None,
            kerning=self.maybe(),
            kerning_min_size=self.measure() if self.maybe(0.2) else None,
            ligatures=self.random.choice(list(LigatureMode)),
            font_features=(FontFeature(tag="ss01", value=1), FontFeature(tag="liga", value=0))
            if self.maybe(0.3)
            else (),
            variation_axes=(
                VariationAxis(tag="wght", value=round(self.random.uniform(100, 900), 1)),
                VariationAxis(tag="opsz", value=round(self.random.uniform(6, 72), 1)),
            )
            if self.maybe(0.3)
            else (),
            small_caps=self.random.choice(list(SmallCapsMode)),
            text_transform=self.random.choice(list(TextTransform)),
            baseline_shift=self.measure() if self.maybe(0.3) else None,
            rise_relative=round(self.random.uniform(-0.5, 0.5), 3) if self.maybe(0.2) else None,
            vertical_align=self.random.choice(list(VerticalAlign)),
            language=self.random.choice(("pt-BR", "en", "de", "ru")),
            numeral_figure=self.random.choice(list(NumeralFigure)),
            numeral_spacing=self.random.choice(list(NumeralSpacing)),
            underline=self.random.choice(list(UnderlineStyle)),
            underline_color=self.color() if self.maybe(0.2) else None,
            underline_thickness=self.measure() if self.maybe(0.2) else None,
            underline_offset=self.measure() if self.maybe(0.2) else None,
            underline_skip_ink=self.maybe(),
            strikethrough=self.random.choice(list(StrikeStyle)),
            strikethrough_color=self.color() if self.maybe(0.2) else None,
            overline=self.maybe(0.1),
            outline=TextOutline(width=self.measure(), color=self.color(), fill=self.maybe())
            if self.maybe(0.15)
            else None,
            shadow=TextShadow(
                offset_x=self.measure(),
                offset_y=self.measure(),
                blur=self.measure(),
                color=self.color(),
            )
            if self.maybe(0.15)
            else None,
            emboss=self.maybe(0.1),
            engrave=self.maybe(0.1),
            emphasis_mark=self.random.choice(list(EmphasisMark)),
            opacity=round(self.random.random(), 3) if self.maybe(0.2) else None,
            hyphenate=self.maybe(),
            spell_check=self.maybe(),
            direction=self.random.choice(list(TextDirection)),
            no_break=self.maybe(0.1),
            hidden=self.maybe(0.05),
        )

    def paragraph_props(self) -> ParagraphProps:
        return ParagraphProps(
            style=self.random.choice(STYLE_NAMES) if self.maybe(0.5) else None,
            alignment=self.random.choice(list(Alignment)),
            indent_left=self.measure() if self.maybe(0.4) else None,
            indent_right=self.measure() if self.maybe(0.2) else None,
            indent_first_line=self.measure() if self.maybe(0.4) else None,
            space_before=self.measure() if self.maybe(0.4) else None,
            space_after=self.measure() if self.maybe(0.4) else None,
            contextual_spacing=self.maybe(),
            line_spacing=LineSpacing(
                rule=self.random.choice(list(LineSpacingRule)),
                value=round(self.random.uniform(0.8, 2.0), 2),
                length=self.measure() if self.maybe(0.3) else None,
            ),
            keep_together=self.maybe(),
            keep_with_next=self.maybe(),
            page_break_before=self.maybe(0.1),
            widow_control=self.maybe(),
            outline_level=self.random.randrange(1, 7) if self.maybe(0.2) else None,
            tab_stops=(
                TabStop(
                    position=self.measure(),
                    alignment=self.random.choice(list(TabAlignment)),
                    leader=self.random.choice(list(TabLeader)),
                ),
            )
            if self.maybe(0.3)
            else (),
            borders=self.borders() if self.maybe(0.2) else None,
            padding=Padding(top=self.measure(), bottom=self.measure()) if self.maybe(0.2) else None,
            shading=self.color() if self.maybe(0.2) else None,
            direction=self.random.choice(list(TextDirection)),
            hyphenate=self.maybe(),
            suppress_line_numbers=self.maybe(0.1),
            numbering=NumberingRef(
                definition=self.random.choice(STYLE_NAMES),
                level=self.random.randrange(3),
                start_override=self.random.randrange(1, 20) if self.maybe(0.2) else None,
            )
            if self.maybe(0.2)
            else None,
            mark_props=self.run_props(rich=False) if self.maybe(0.2) else None,
            default_run=self.run_props(rich=False) if self.maybe(0.2) else None,
        )

    def borders(self) -> Borders:
        def edge() -> Border:
            return Border(
                style=self.random.choice(list(BorderStyle)),
                width=self.measure(),
                color=self.color(),
                space=self.measure(),
                shadow=self.maybe(0.1),
            )

        return Borders(top=edge(), bottom=edge(), left=edge(), right=edge())

    def marks(self, count: int = 3) -> tuple[Mark, ...]:
        result: list[Mark] = []
        for _ in range(self.random.randrange(count + 1)):
            kind = self.random.choice(list(MarkKind))
            squares = (
                tuple(self.random.sample(SQUARES, 2))
                if kind is MarkKind.ARROW
                else (self.random.choice(SQUARES),)
            )
            result.append(
                Mark(
                    kind=kind,
                    squares=squares,
                    color=self.color(),
                    line_style=self.random.choice(list(MarkLineStyle)),
                    width=self.measure() if self.maybe(0.3) else None,
                    opacity=round(self.random.random(), 3),
                    text=self.word() if kind is MarkKind.LABEL else None,
                    layer=self.random.randrange(-2, 3),
                    filled=self.maybe(),
                )
            )
        return tuple(result)

    # -- inlines -----------------------------------------------------------

    def text(self) -> Text:
        return Text(
            id=self.next_ulid(),
            provenance=self.provenance() if self.maybe(0.3) else None,
            content=self.sentence(self.random.randrange(1, 8)),
            props=self.run_props(rich=self.maybe(0.4)),
        )

    def move(self) -> Move:
        return Move(
            id=self.next_ulid(),
            san=self.random.choice(SANS),
            ply=self.random.randrange(1, 120),
            position_before=self.random.choice(FENS),
            nags=tuple(self.random.sample(range(1, 256), self.random.randrange(3))),
            render=self.random.choice(list(MoveRenderStyle)),
            language=self.random.choice(LANGUAGES),
            figurine_set=self.random.choice(list(FigurineSet)),
            uci="g1f3" if self.maybe(0.4) else None,
            show_move_number=self.maybe(),
            move_number_text="24..." if self.maybe(0.2) else None,
            props=self.run_props(rich=False),
        )

    def leaf_inline(self) -> Inline:  # noqa: PLR0911 - a dispatch table, one branch per node type
        pick = self.random.randrange(16)
        if pick <= 4:
            return self.text()
        if pick == 5:
            return self.move()
        if pick == 6:
            return PieceGlyph(
                id=self.next_ulid(),
                piece=self.random.choice(list(PieceType)),
                figurine_set=self.random.choice(list(FigurineSet)),
                font_family="Merida" if self.maybe() else None,
                props=self.run_props(rich=False),
            )
        if pick == 7:
            return NagSymbol(id=self.next_ulid(), nag=self.random.randrange(1, 256))
        if pick == 8:
            return InlineDiagram(
                id=self.next_ulid(),
                fen=self.random.choice(FENS),
                size=self.measure(),
                orientation=self.random.choice(list(Orientation)),
                marks=self.marks(2),
                style="Diagrama" if self.maybe(0.3) else None,
                alt_text=self.sentence(4),
            )
        if pick == 9:
            return MathInline(
                id=self.next_ulid(),
                latex=r"\frac{1}{2}",
                mathml="<math/>" if self.maybe() else None,
            )
        if pick == 10:
            return self.random.choice(
                (
                    LineBreak(id=self.next_ulid()),
                    NonBreakingSpace(id=self.next_ulid()),
                    Tab(id=self.next_ulid()),
                    Space(id=self.next_ulid(), kind=self.random.choice(list(SpaceKind))),
                )
            )
        if pick == 11:
            return IndexEntry(
                id=self.next_ulid(),
                terms=tuple(self.word() for _ in range(self.random.randrange(1, 4))),
                sort_key=self.word() if self.maybe(0.3) else None,
                see_also=(self.word(),) if self.maybe(0.2) else (),
                primary=self.maybe(),
            )
        if pick == 12:
            return RawInline(id=self.next_ulid(), format="latex", text=r"\kern1pt")
        if pick == 13:
            return NoteRef(
                id=self.next_ulid(),
                ref=f"nota-{self.random.randrange(1, 40)}",
                marker="*" if self.maybe(0.2) else None,
                props=self.run_props(rich=False),
            )
        if pick == 14:
            return Anchor(
                id=self.next_ulid(),
                name=f"ancora-{self._counter}",
                title=self.sentence(2) if self.maybe(0.3) else None,
            )
        return ImageInline(
            id=self.next_ulid(),
            resource="img-1",
            alt_text=self.sentence(3),
            width=self.measure(),
            height=self.measure(),
            baseline_shift=self.measure(),
        )

    def inline(self, depth: int = 0) -> Inline:  # noqa: PLR0911 - one branch per wrapper type
        if depth >= 2 or self.maybe(0.65):
            return self.leaf_inline()
        content = tuple(self.inline(depth + 1) for _ in range(self.random.randrange(1, 4)))
        props = self.run_props(rich=False)
        pick = self.random.randrange(9)
        if pick == 0:
            return Emphasis(id=self.next_ulid(), content=content, props=props)
        if pick == 1:
            return Strong(id=self.next_ulid(), content=content, props=props)
        if pick == 2:
            return Underline(id=self.next_ulid(), content=content, props=props)
        if pick == 3:
            return Strike(id=self.next_ulid(), content=content, props=props)
        if pick == 4:
            return SmallCaps(id=self.next_ulid(), content=content, props=props)
        if pick == 5:
            return Superscript(id=self.next_ulid(), content=content, props=props)
        if pick == 6:
            return Subscript(id=self.next_ulid(), content=content, props=props)
        if pick == 7:
            return Span(id=self.next_ulid(), content=content, props=props)
        return Link(
            id=self.next_ulid(),
            target=self.random.choice(("https://exemplo.org", "#ancora-1", "mailto:a@b.c")),
            content=content,
            tooltip=self.sentence(3),
            title=self.word(),
            kind=self.random.choice(list(LinkKind)),
            props=props,
        )

    def inlines(self, count: int = 4) -> tuple[Inline, ...]:
        return tuple(self.inline() for _ in range(self.random.randrange(1, count + 1)))

    # -- chess -------------------------------------------------------------

    def move_node(self, depth: int = 0, ply: int = 1) -> MoveNode:
        children: list[MoveNode] = []
        if depth < 3 and self.maybe(0.7):
            children.append(self.move_node(depth + 1, ply + 1))
            if self.maybe(0.35):
                children.append(self.move_node(depth + 2, ply + 1))
        return MoveNode(
            id=self.next_ulid(),
            san=self.random.choice(SANS),
            ply=ply,
            position_before=self.random.choice(FENS),
            position_after=self.random.choice(FENS) if self.maybe(0.4) else "",
            uci="e2e4" if self.maybe(0.3) else None,
            nags=tuple(self.random.sample(range(1, 256), self.random.randrange(3))),
            comment_before=self.sentence(4) if self.maybe(0.2) else "",
            comment_after=self.sentence(6) if self.maybe(0.4) else "",
            arrows=tuple(m for m in self.marks(2) if m.kind is MarkKind.ARROW),
            highlights=tuple(m for m in self.marks(2) if m.kind is MarkKind.SQUARE),
            clock=ClockAnnotation(
                kind=self.random.choice(list(ClockKind)),
                text="1:23:45",
                seconds=5025.0,
            )
            if self.maybe(0.3)
            else None,
            evaluation=EvalAnnotation(
                kind=self.random.choice(list(EvalKind)),
                value=round(self.random.uniform(-9, 9), 2),
                depth=self.random.randrange(1, 40),
                text="+0.34",
            )
            if self.maybe(0.3)
            else None,
            emphasis=self.maybe(0.15),
            children=tuple(children),
        )

    def game_score(self) -> GameScore:
        return GameScore(
            id=self.next_ulid(),
            headers=GameHeaders(
                event=self.sentence(3),
                site=self.word(),
                date="2026.09.07",
                round=str(self.random.randrange(1, 15)),
                white=self.word().title(),
                black=self.word().title(),
                result=self.random.choice(("1-0", "0-1", "1/2-1/2", "*")),
                extra=(
                    PgnTag(name="ECO", value="B90"),
                    PgnTag(name="WhiteElo", value="2712"),
                    PgnTag(name="Annotator", value=self.word()),
                ),
            ),
            initial_fen=self.random.choice(FENS) if self.maybe(0.25) else None,
            variant=self.random.choice(("standard", "chess960")),
            initial_comment=self.sentence(6) if self.maybe(0.3) else "",
            children=tuple(self.move_node() for _ in range(self.random.randrange(1, 3))),
            render=GameRenderOptions(
                language=self.random.choice(LANGUAGES),
                render=self.random.choice(list(MoveRenderStyle)),
                figurine_set=self.random.choice(list(FigurineSet)),
                variation_style=self.random.choice(list(VariationStyle)),
                show_result=self.maybe(),
                show_headers=self.maybe(),
                max_variation_depth=self.random.randrange(1, 6) if self.maybe(0.3) else None,
                move_props=self.run_props(rich=False),
                comment_props=self.run_props(rich=False),
                variation_props=self.run_props(rich=False),
            ),
            title=self.sentence(3) if self.maybe(0.3) else None,
            annotator=self.word() if self.maybe(0.3) else None,
        )

    def diagram(self) -> Diagram:
        return Diagram(
            id=self.next_ulid(),
            provenance=self.provenance() if self.maybe(0.5) else None,
            fen=self.random.choice(FENS),
            orientation=self.random.choice(list(Orientation)),
            source=DiagramSource(
                kind=self.random.choice(list(SourceKind)),
                path=f"acervo/{self.word()}.pdf",
                content_hash=f"sha256:{self._counter:064x}",
                page_index=self.random.randrange(400),
                rect=Rect(x=10.0, y=20.0, width=180.0, height=180.0),
                dpi=300.0,
                rotation_degrees=round(self.random.uniform(-2, 2), 3),
                image_hash=f"phash:{self._counter:016x}",
                extracted_at=datetime(2026, 9, 7, 10, 30, tzinfo=UTC),
                extractor="caissa.ingest.pdf",
                extractor_version="0.1.0",
            ),
            recognition=RecognitionResult(
                fen=self.random.choice(FENS),
                per_square_confidence=tuple(round(self.random.random(), 5) for _ in range(64)),
                overall_confidence=round(self.random.random(), 5),
                orientation_confidence=round(self.random.random(), 5),
                side_to_move_confidence=round(self.random.random(), 5),
                path=self.random.choice(list(RecognitionPath)),
                model_name="squares-cnn",
                model_version="3.2.1",
                model_hash=f"sha256:{self._counter:064x}",
                recognised_at=datetime(2026, 9, 7, 10, 31, tzinfo=UTC),
                duration_ms=round(self.random.uniform(5, 700), 3),
                corners=tuple(round(self.random.uniform(0, 600), 2) for _ in range(8)),
                alternatives=(
                    FenCandidate(fen=self.random.choice(FENS), score=-1.2, legal=True),
                    FenCandidate(fen=self.random.choice(FENS), score=-4.8, legal=False),
                ),
                repairs=(
                    SquareRepair(
                        square="e4",
                        recognised="P",
                        repaired="",
                        reason="peao na 1a fileira",
                        confidence_before=0.41,
                    ),
                ),
                warnings=("moldura decorativa removida",),
            ),
            verified_by_human=self.maybe(0.3),
            style=DiagramStyle(
                name="Diagrama" if self.maybe(0.4) else None,
                piece_set=self.random.choice(("Merida", "Alpha", "Leipzig", "USCF")),
                piece_font_family="Merida",
                piece_scale=round(self.random.uniform(0.7, 1.0), 3),
                theme=BoardTheme(
                    light_square=self.color(),
                    dark_square=self.color(),
                    border=self.color(),
                    grid_line=self.color(),
                    highlight=self.color(),
                    arrow=self.color(),
                ),
                coordinates=CoordinateStyle(
                    placement=self.random.choice(list(PiecePlacementStyle)),
                    files=self.maybe(),
                    ranks=self.maybe(),
                    both_sides=self.maybe(),
                    props=self.run_props(rich=False),
                    gap=self.measure(),
                ),
                size=self.measure(),
                square_size=self.measure(),
                border=Border(style=BorderStyle.SOLID, width=self.measure(), color=self.color()),
                margin=self.measure(),
                show_side_to_move=self.maybe(),
                caption_position=None,
                shadow=self.maybe(),
                grid_lines=self.maybe(),
                keep_with_caption=self.maybe(),
            ),
            caption=self.inlines(2),
            number=self.random.randrange(1, 400),
            label=f"Diagrama {self.random.randrange(1, 400)}" if self.maybe(0.2) else None,
            marks=self.marks(),
            side_to_move_indicator=self.maybe(),
            stipulation=self.random.choice(("Mate em 2", "Brancas jogam e ganham", None)),
            solution=self.game_score() if self.maybe(0.25) else None,
            anchor=None,
            alt_text=self.sentence(6),
            move_context="apos 24...Txf2" if self.maybe(0.3) else None,
        )

    # -- blocks ------------------------------------------------------------

    def block(self, depth: int = 0) -> Block:  # noqa: PLR0911, PLR0912 - one branch per block type
        pick = self.random.randrange(20)
        if pick <= 4:
            return Paragraph(
                id=self.next_ulid(),
                provenance=self.provenance() if self.maybe(0.3) else None,
                content=self.inlines(5),
                props=self.paragraph_props(),
                drop_cap=self.random.randrange(2, 5) if self.maybe(0.1) else None,
            )
        if pick == 5:
            return Heading(
                id=self.next_ulid(),
                level=self.random.randrange(1, 7),
                content=self.inlines(3),
                numbering=NumberingRef(definition="Titulo1", level=0) if self.maybe(0.3) else None,
                numbering_text="1.2" if self.maybe(0.2) else None,
                anchor=None,
                toc_text=self.sentence(2) if self.maybe(0.2) else None,
                props=self.paragraph_props(),
                run_props=self.run_props(rich=False),
                list_in_toc=self.maybe(0.9),
            )
        if pick == 6:
            return self.diagram()
        if pick == 7:
            return self.game_score()
        if pick == 8:
            return ListBlock(
                id=self.next_ulid(),
                kind=self.random.choice(list(ListKind)),
                items=tuple(self.list_item(depth) for _ in range(self.random.randrange(1, 4))),
                marker_style=self.random.choice(list(ListMarkerStyle)),
                marker_text=("♞" if self.maybe(0.2) else None),
                start=self.random.randrange(1, 10),
                tight=self.maybe(),
                numbering=NumberingRef(definition="Corpo", level=1) if self.maybe(0.2) else None,
                props=self.paragraph_props(),
                indent=self.measure(),
            )
        if pick == 9:
            return self.table(depth)
        if pick == 10:
            return Figure(
                id=self.next_ulid(),
                content=(self.diagram(),) if self.maybe(0.6) else (self.image_block(),),
                caption=self.inlines(2),
                number=self.random.randrange(1, 200),
                label=None,
                placement=self.random.choice(list(FigurePlacement)),
                caption_above=self.maybe(),
                anchor=None,
                alt_text=self.sentence(4),
                props=self.paragraph_props(),
            )
        if pick == 11:
            return CodeBlock(
                id=self.next_ulid(),
                language=self.random.choice(("pgn", "fen", "python", "")),
                text="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6\n",
                show_line_numbers=self.maybe(),
                props=self.paragraph_props(),
                run_props=self.run_props(rich=False),
            )
        if pick == 12:
            return MathBlock(
                id=self.next_ulid(),
                latex=r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
                mathml="<math/>" if self.maybe(0.3) else None,
                display=self.maybe(0.8),
                numbered=self.maybe(0.3),
                label=None,
                props=self.paragraph_props(),
            )
        if pick == 13:
            return Quote(
                id=self.next_ulid(),
                content=(self.simple_paragraph(),),
                attribution=self.inlines(2),
                props=self.paragraph_props(),
            )
        if pick == 14:
            return Callout(
                id=self.next_ulid(),
                kind=self.random.choice(list(CalloutKind)),
                title=self.inlines(2),
                content=(self.simple_paragraph(),),
                props=self.paragraph_props(),
                borders=self.borders() if self.maybe(0.4) else None,
                padding=Padding(top=self.measure(), left=self.measure()),
                shading=self.color(),
                collapsed=self.maybe(0.3),
            )
        if pick == 15:
            return SectionBreak(
                id=self.next_ulid(),
                kind=self.random.choice(list(SectionBreakKind)),
                columns=ColumnLayout(
                    count=self.random.randrange(1, 4),
                    gap=self.measure(),
                    rule=Border(style=BorderStyle.SOLID, width=self.measure()),
                    balanced=self.maybe(),
                    widths=(self.measure(), self.measure()) if self.maybe(0.3) else (),
                ),
                geometry=PageGeometry(
                    width=self.measure(),
                    height=self.measure(),
                    margin_top=self.measure(),
                    margin_bottom=self.measure(),
                    margin_inner=self.measure(),
                    margin_outer=self.measure(),
                    gutter=self.measure(),
                    landscape=self.maybe(0.2),
                    mirror_margins=self.maybe(0.8),
                ),
                header_text=self.inlines(2),
                footer_text=self.inlines(2),
                different_first_page=self.maybe(),
                different_odd_even=self.maybe(),
                page_number_start=self.random.randrange(1, 400) if self.maybe(0.2) else None,
                page_number_format=self.random.choice(("decimal", "lower-roman", None)),
                vertical_alignment=None,
            )
        if pick == 16:
            return self.random.choice(
                (
                    PageBreak(id=self.next_ulid()),
                    ThematicBreak(id=self.next_ulid(), ornament="* * *"),
                    TableOfContents(
                        id=self.next_ulid(),
                        title=self.inlines(1),
                        min_level=1,
                        max_level=3,
                        show_page_numbers=self.maybe(),
                        leader=self.maybe(),
                        scope=self.random.choice(("headings", "figures", "diagrams", "games")),
                    ),
                    RawPassthrough(id=self.next_ulid(), format="latex", text=r"\clearpage"),
                )
            )
        if pick == 17:
            return Footnote(
                id=self.next_ulid(),
                ref=f"nota-{self._counter}",
                content=(self.simple_paragraph(),),
                marker="*" if self.maybe(0.3) else None,
                props=self.paragraph_props(),
            )
        if pick == 18:
            return Endnote(
                id=self.next_ulid(),
                ref=f"fim-{self._counter}",
                content=(self.simple_paragraph(),),
                marker=None,
                props=self.paragraph_props(),
            )
        if depth < 2:
            return Group(
                id=self.next_ulid(),
                role=self.random.choice(list(GroupRole)),
                content=tuple(self.block(depth + 1) for _ in range(self.random.randrange(1, 4))),
                title=self.inlines(1),
                props=self.paragraph_props(),
                anchor=None,
                columns=self.random.randrange(1, 4) if self.maybe(0.3) else None,
            )
        return self.simple_paragraph()

    def simple_paragraph(self) -> Paragraph:
        return Paragraph(
            id=self.next_ulid(),
            content=(self.text(),),
            props=self.paragraph_props(),
        )

    def image_block(self) -> ImageBlock:
        return ImageBlock(
            id=self.next_ulid(),
            resource="img-1",
            alt_text=self.sentence(4),
            width=self.measure(),
            height=self.measure(),
            alignment=self.random.choice(list(Alignment)),
            title=self.word(),
            crop=(0.0, 0.05, 1.0, 0.95),
        )

    def list_item(self, depth: int = 0) -> ListItem:
        return ListItem(
            id=self.next_ulid(),
            content=(self.simple_paragraph(),) if depth < 2 else (),
            term=self.inlines(1) if self.maybe(0.3) else (),
            marker_override="—" if self.maybe(0.2) else None,
            start_override=self.random.randrange(1, 10) if self.maybe(0.2) else None,
            checked=self.maybe() if self.maybe(0.2) else None,
        )

    def table(self, depth: int = 0) -> Table:
        columns = self.random.randrange(2, 5)
        rows = self.random.randrange(1, 4)
        return Table(
            id=self.next_ulid(),
            columns=tuple(
                TableColumn(
                    width=self.measure(),
                    alignment=self.random.choice(list(Alignment)),
                    min_width=self.measure() if self.maybe(0.3) else None,
                )
                for _ in range(columns)
            ),
            rows=tuple(
                TableRow(
                    id=self.next_ulid(),
                    cells=tuple(
                        TableCell(
                            id=self.next_ulid(),
                            content=(self.simple_paragraph(),) if depth < 2 else (),
                            row_span=1,
                            col_span=1,
                            alignment=self.random.choice(list(Alignment)),
                            vertical_alignment=None,
                            borders=self.borders() if self.maybe(0.3) else None,
                            padding=Padding(top=self.measure()),
                            shading=self.color() if self.maybe(0.3) else None,
                            is_header=index == 0,
                        )
                        for _ in range(columns)
                    ),
                    height=self.measure(),
                    is_header=index == 0,
                    repeat_on_break=index == 0,
                    keep_together=self.maybe(),
                )
                for index in range(rows)
            ),
            header_row_count=1 if rows > 1 else 0,
            footer_row_count=0,
            repeat_header=self.maybe(),
            borders=self.borders(),
            cell_padding=Padding(top=self.measure(), left=self.measure()),
            width=self.measure(),
            alignment=self.random.choice(list(Alignment)),
            caption=self.inlines(2),
            caption_above=self.maybe(),
            number=self.random.randrange(1, 100),
            style=None,
            anchor=None,
            summary=self.sentence(5),
        )

    # -- document ----------------------------------------------------------

    def stylesheet(self) -> StyleSheet:
        return StyleSheet(
            default_paragraph=self.paragraph_props(),
            default_run=self.run_props(),
            paragraph_styles=tuple(
                ParagraphStyle(
                    name=name,
                    display_name=name.upper(),
                    based_on="Corpo" if name != "Corpo" else None,
                    next_style="Corpo",
                    paragraph=self.paragraph_props(),
                    run=self.run_props(rich=False),
                    outline_level=index if index < 6 else None,
                    hidden=False,
                    locked=self.maybe(0.2),
                    priority=index,
                    description=self.sentence(4),
                )
                for index, name in enumerate(STYLE_NAMES)
            ),
            character_styles=tuple(
                CharacterStyle(
                    name=f"c-{name}",
                    display_name=name,
                    based_on=None,
                    props=self.run_props(rich=False),
                    hidden=False,
                    locked=False,
                    priority=index,
                    description=None,
                )
                for index, name in enumerate(STYLE_NAMES)
            ),
            table_styles=(
                TableStyle(
                    name="TabelaAberturas",
                    display_name="Tabela de aberturas",
                    based_on=None,
                    borders=self.borders(),
                    cell_padding=Padding(top=self.measure()),
                    header_run=self.run_props(rich=False),
                    header_shading=self.color(),
                    body_run=self.run_props(rich=False),
                    band_size=2,
                    band_shading=self.color(),
                    first_column_run=self.run_props(rich=False),
                    description=None,
                ),
            ),
            list_styles=(
                ListStyle(
                    name="Corpo",
                    display_name="Numeracao do corpo",
                    based_on=None,
                    levels=tuple(
                        ListStyleLevel(
                            level=level,
                            marker_style="decimal",
                            marker_text=f"%{level + 1}.",
                            start=1,
                            indent=self.measure(),
                            hanging=self.measure(),
                            props=self.paragraph_props(),
                            run_props=self.run_props(rich=False),
                            restart_after_level=level - 1 if level else None,
                        )
                        for level in range(3)
                    ),
                    description=None,
                ),
            ),
            diagram_styles=(
                DiagramStyleDef(
                    name="Diagrama",
                    display_name="Diagrama padrao",
                    based_on=None,
                    style=DiagramStyle(piece_set="Merida", size=self.measure()),
                    description=None,
                ),
            ),
            default_paragraph_style="Corpo",
            default_character_style=None,
            default_diagram_style="Diagrama",
        )

    def document(self, *, min_nodes: int = 0, max_blocks: int = 2000) -> Document:
        body: list[Block] = []
        total = 0
        while total < min_nodes and len(body) < max_blocks:
            block = self.block()
            body.append(block)
            total += sum(1 for _ in walk(block))
        if not body:
            body.append(self.simple_paragraph())
        return Document(
            id=self.next_ulid(),
            metadata=DocumentMetadata(
                title=self.sentence(4).title(),
                subtitle=self.sentence(6),
                short_title=self.word(),
                contributors=tuple(
                    Contributor(
                        name=self.word().title(),
                        role=role,
                        sort_name=f"{self.word().title()}, {self.word().title()}",
                        identifier=None,
                    )
                    for role in list(ContributorRole)[:4]
                ),
                language="pt-BR",
                additional_languages=("en", "de"),
                identifier="urn:uuid:0f0f0f0f-0000-4000-8000-000000000000",
                isbn="978-85-000-0000-0",
                issn=None,
                publisher=self.word().title(),
                imprint=None,
                publication_date="2026-09-07",
                modified=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
                edition="2a edicao",
                series=self.word().title(),
                series_index=3,
                description=self.sentence(10),
                subjects=("xadrez", "aberturas", "estrategia"),
                rights="(c) 2026",
                source="acervo/original.pdf",
                cover_resource="img-1",
                page_count=320,
                custom=(
                    MetadataEntry(name="dcterms:audience", value="avancado", scheme="dcterms"),
                ),
            ),
            styles=self.stylesheet(),
            settings=DocumentSettings(
                notation_language=self.random.choice(LANGUAGES),
                move_render=self.random.choice(list(MoveRenderStyle)),
                figurine_set=self.random.choice(list(FigurineSet)),
                chess_font_family="Merida",
                default_diagram_style="Diagrama",
                diagram_numbering_start=1,
                figure_numbering_start=1,
                table_numbering_start=1,
                auto_number_diagrams=True,
                number_diagrams_per_chapter=self.maybe(),
                hyphenation=self.maybe(0.9),
                footnote_restart_per_page=self.maybe(0.2),
                confidence_threshold=0.9,
                embed_fonts=True,
            ),
            resources=(
                Resource(
                    key="img-1",
                    kind=ResourceKind.IMAGE,
                    path="assets/capa.png",
                    media_type="image/png",
                    content_hash="sha256:" + "0" * 64,
                    byte_size=123456,
                    width=1200,
                    height=1800,
                    dpi=300.0,
                    embed=True,
                    subset=False,
                    description="capa",
                ),
                Resource(
                    key="font-merida",
                    kind=ResourceKind.FONT,
                    path="assets/Merida.otf",
                    media_type="font/otf",
                    family="Merida",
                    weight=400,
                    italic=False,
                    license_note="licenca do editor",
                ),
            ),
            body=tuple(body),
        )


# --------------------------------------------------------------------------- #
# Reflection-driven minimal construction
# --------------------------------------------------------------------------- #

_SAMPLE_STRINGS = {
    "fen": STARTING_FEN,
    "square": "e4",
    "san": "Nf3",
    "recognised": "P",
    "repaired": "N",
    "target": "#ancora",
    "format": "latex",
    "tag": "ss01",
    "code": "teste.codigo",
    "message": "mensagem de teste",
    "property": "small_caps",
    "target_format": "docx",
}


def construct_minimal(cls: type[Any]) -> Any:
    """Build one instance of an IR class, filling only what has no default.

    Args:
        cls: A registered IR dataclass.

    Returns:
        An instance.
    """
    kwargs: dict[str, Any] = {}
    annotations = field_types(cls)
    for item in fields(cls):
        if item.default is not MISSING or item.default_factory is not MISSING:
            continue
        kwargs[item.name] = _sample_for(item.name, annotations[item.name])
    return cls(**kwargs)


def _sample_for(name: str, annotation: Any) -> Any:  # noqa: PLR0911 - one branch per leaf type
    """Produce a plausible value for one field.

    Args:
        name: The field name, used to pick a chess-shaped sample.
        annotation: Its declared type.

    Returns:
        A value the field accepts.
    """
    origin = get_origin(annotation)
    if origin is tuple:
        return ()
    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return next(iter(annotation))
        if issubclass(annotation, ULID):
            return ULID.from_parts(1_700_000_000_000, 1)
        if issubclass(annotation, bool):
            return False
        if issubclass(annotation, int):
            return 1
        if issubclass(annotation, float):
            return 1.0
        if issubclass(annotation, str):
            return _SAMPLE_STRINGS.get(name, name.replace("_", "-"))
        if is_dataclass(annotation):
            return construct_minimal(annotation)
    return None


def all_node_types() -> tuple[type[IRNode], ...]:
    """Return every registered class that is an addressable node.

    Returns:
        The node classes, sorted by tag.
    """
    from caissa.core.model.registry import iter_registered

    return tuple(
        cls for _tag, cls in iter_registered() if isinstance(cls, type) and issubclass(cls, IRNode)
    )
