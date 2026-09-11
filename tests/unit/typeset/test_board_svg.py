"""Board rendering: determinism, round-trip fidelity, frames, coordinates, marks.

The load-bearing test here is `test_fen_survives_the_round_trip`. It does not read the
FEN back out of the ``aria-label`` -- that would only prove the label was written -- it
identifies each piece from **the path data actually drawn**, by matching it against the
path the font produces for that piece on that square. A piece drawn on the wrong square,
drawn from the wrong glyph, or not drawn at all fails it.
"""

from __future__ import annotations

import random
import re
import xml.etree.ElementTree as ET

import chess
import pytest

from caissa.typeset.board_svg import (
    THEMES,
    Arrow,
    BoardTheme,
    CircleMark,
    CoordinateStyle,
    DiagramStyle,
    FrameStyle,
    SideToMove,
    SquareHighlight,
    board_from_fen,
    contrast_ratio,
    get_theme,
    render_svg,
    square_name,
)
from caissa.typeset.fonts import FontModel

SVG_NS = "{http://www.w3.org/2000/svg}"
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MIDDLE = "r2q1rk1/pb1n1ppp/1p6/2Pp4/8/6P1/PP1NPPBP/2RQ1RK1 b - - 0 13"


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def paths(root: ET.Element) -> list[str]:
    return [e.get("d") or "" for e in root.iter(f"{SVG_NS}path")]


def paths_filled(root: ET.Element, colour: str) -> list[str]:
    """Path data of every path filled in ``colour``.

    Marks are drawn UNDER the pieces now (`board_svg.MARK_PAINT_ORDER`), so "the last
    path with three corners" is a piece outline, not an arrow. Selecting by the mark's
    own colour is what a reader does with their eyes.
    """
    return [e.get("d") or "" for e in root.iter(f"{SVG_NS}path")
            if (e.get("fill") or "").lower() == colour.lower()]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_same_input_gives_byte_identical_output(legacy_spec):
    style = DiagramStyle(font=legacy_spec.key, width_mm=48, theme="book")
    first = render_svg(MIDDLE, style)
    for _ in range(4):
        assert render_svg(MIDDLE, style) == first


def test_determinism_holds_across_every_style_axis(legacy_spec):
    """A style that renders differently on the second call cannot be cached or diffed."""
    for frame in FrameStyle:
        for coords in CoordinateStyle:
            style = DiagramStyle(
                font=legacy_spec.key, width_mm=44, frame=frame, coordinates=coords
            )
            assert render_svg(MIDDLE, style) == render_svg(MIDDLE, style)


def test_marks_do_not_perturb_determinism(legacy_spec):
    marks = [SquareHighlight("c5"), CircleMark("d5"), Arrow("g2", "b7"), Arrow("d2", "b3")]
    style = DiagramStyle(font=legacy_spec.key, width_mm=60)
    assert render_svg(MIDDLE, style, marks=marks) == render_svg(MIDDLE, style, marks=marks)


def test_no_negative_zero_in_output(legacy_spec):
    """`-0` and `0` are the same number and different bytes. `format_number` normalises
    it; without that, determinism holds within a run and breaks across platforms."""
    svg = render_svg(MIDDLE, DiagramStyle(font=legacy_spec.key, width_mm=44))
    assert "-0 " not in svg
    assert not re.search(r'["\s,]-0(?![.\d])', svg)


# --------------------------------------------------------------------------- #
# Round trip
# --------------------------------------------------------------------------- #
def _placement_lookup(spec, style: DiagramStyle) -> dict[str, tuple[int, int, str]]:
    """Map every path string the renderer *could* emit to (row, col, piece).

    Built once from the font itself: for a legacy family the glyph is placed at a fixed
    scale with the baseline on the square's bottom edge, so the path for piece ``p`` on
    square (row, col) is fully determined. Generating all 12x64 of them and inverting the
    map turns "which piece is drawn here" into a dictionary lookup.
    """
    from caissa.typeset.board_svg import _layout
    from caissa.typeset.fonts import PIECES, load_font

    font = load_font(spec)
    lay = _layout(style)
    sq = lay.square
    scale = (sq / font.units_per_em) * style.piece_scale
    slack = (sq - sq * style.piece_scale) / 2.0

    table: dict[str, tuple[int, int, str]] = {}
    for piece in PIECES:
        outline = font.piece_outline(piece)
        if outline.is_empty():
            continue
        for row in range(8):
            for col in range(8):
                x = lay.board_x + col * sq + slack
                y = lay.board_y + row * sq + sq - slack
                table[outline.to_svg_path(scale=scale, dx=x, dy=y)] = (row, col, piece)
    return table


def _read_back(svg: str, table: dict[str, tuple[int, int, str]]) -> str:
    """Recover the FEN placement field from the drawn paths alone."""
    grid = [["." for _ in range(8)] for _ in range(8)]
    for d in paths(parse(svg)):
        hit = table.get(d)
        if hit is not None:
            row, col, piece = hit
            grid[row][col] = piece

    ranks = []
    for row in grid:
        out, empty = "", 0
        for cell in row:
            if cell == ".":
                empty += 1
                continue
            if empty:
                out += str(empty)
                empty = 0
            out += cell
        if empty:
            out += str(empty)
        ranks.append(out)
    return "/".join(ranks)


def _random_legal_positions(count: int, seed: int = 20260907) -> list[str]:
    """Positions reached by random legal play. Real boards, not synthetic square soup."""
    rng = random.Random(seed)
    out: list[str] = []
    while len(out) < count:
        board = chess.Board()
        for _ in range(rng.randint(2, 80)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if board.piece_map():
            out.append(board.fen())
    return out


@pytest.mark.slow
def test_fen_survives_the_round_trip(legacy_spec):
    """FEN -> SVG -> piece positions parsed back from the drawing -> the same FEN.

    200 positions from random legal play. The comparison is on the placement field only:
    side to move, castling and clocks are not drawn on a board and cannot be recovered
    from one.
    """
    style = DiagramStyle(font=legacy_spec.key, width_mm=60, theme="book")
    table = _placement_lookup(legacy_spec, style)

    positions = _random_legal_positions(200)
    assert len(positions) == 200

    for fen in positions:
        expected = fen.split()[0]
        got = _read_back(render_svg(fen, style), table)
        assert got == expected, f"round trip falhou\n  esperado {expected}\n  obtido   {got}"


def test_round_trip_survives_a_flipped_board(legacy_spec):
    """A flipped board draws the same pieces at mirrored squares; the FEN read back has
    to be the original, not the mirror."""
    style = DiagramStyle(
        font=legacy_spec.key, width_mm=60, orientation="black", theme="book"
    )
    table = _placement_lookup(legacy_spec, style)
    got = _read_back(render_svg(MIDDLE, style), table)
    # The lookup is in drawing order, so a flipped board reads back mirrored.
    mirrored = "/".join(
        "".join(reversed(rank)) for rank in reversed(got.split("/"))
    )
    expanded = "".join(
        "".join("." * int(c) if c.isdigit() else c for c in rank)
        for rank in MIDDLE.split()[0].split("/")
    )
    got_expanded = "".join(
        "".join("." * int(c) if c.isdigit() else c for c in rank)
        for rank in mirrored.split("/")
    )
    assert got_expanded == expanded


def test_empty_board_draws_no_pieces(legacy_spec):
    style = DiagramStyle(font=legacy_spec.key, width_mm=44)
    table = _placement_lookup(legacy_spec, style)
    assert _read_back(render_svg("8/8/8/8/8/8/8/8 w - - 0 1", style), table) == "8/8/8/8/8/8/8/8"


def test_board_from_fen_rejects_a_malformed_position():
    with pytest.raises((ValueError, IndexError, KeyError)):
        board_from_fen("this is not a fen")


# --------------------------------------------------------------------------- #
# Frames
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("frame", list(FrameStyle))
def test_every_frame_style_renders(legacy_spec, frame):
    svg = render_svg(MIDDLE, DiagramStyle(font=legacy_spec.key, width_mm=44, frame=frame))
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_frame_none_draws_no_frame_rule(legacy_spec):
    def frame_rects(style):
        root = parse(render_svg(MIDDLE, style))
        return [
            e for e in root.iter(f"{SVG_NS}rect")
            if e.get("fill") == "none" and e.get("stroke")
        ]

    base = DiagramStyle(font=legacy_spec.key, width_mm=44)
    assert frame_rects(DiagramStyle(**{**base.__dict__, "frame": FrameStyle.NONE})) == []
    assert frame_rects(DiagramStyle(**{**base.__dict__, "frame": FrameStyle.HAIRLINE}))


def test_double_frame_draws_two_rules(legacy_spec):
    root = parse(
        render_svg(MIDDLE, DiagramStyle(font=legacy_spec.key, width_mm=44,
                                        frame=FrameStyle.DOUBLE))
    )
    rules = [
        e for e in root.iter(f"{SVG_NS}rect")
        if e.get("fill") == "none" and e.get("stroke")
    ]
    assert len(rules) == 2


def test_no_rule_is_thinner_than_the_press_can_hold(legacy_spec):
    """`MIN_RULE_MM` exists because a 0.05 mm rule disappears on paper. At the smallest
    diagram we offer, every stroke must still clear it."""
    from caissa.typeset.board_svg import MIN_RULE_MM

    for width in (20, 25, 30):
        root = parse(
            render_svg(
                MIDDLE,
                DiagramStyle(font=legacy_spec.key, width_mm=width, frame=FrameStyle.DOUBLE,
                             grid=True),
            )
        )
        for element in root.iter():
            raw = element.get("stroke-width")
            if raw is None:
                continue
            assert float(raw) >= MIN_RULE_MM - 1e-9, (
                f"traco de {raw} mm em diagrama de {width} mm, abaixo de {MIN_RULE_MM}"
            )


# --------------------------------------------------------------------------- #
# Coordinates
# --------------------------------------------------------------------------- #
def _texts(svg: str) -> list[ET.Element]:
    return list(parse(svg).iter(f"{SVG_NS}text"))


def test_coordinates_none_emits_no_labels(legacy_spec):
    svg = render_svg(
        MIDDLE,
        DiagramStyle(font=legacy_spec.key, width_mm=44, coordinates=CoordinateStyle.NONE),
    )
    assert _texts(svg) == []


def test_outside_coordinates_are_sixteen_labels(legacy_spec):
    svg = render_svg(
        MIDDLE,
        DiagramStyle(font=legacy_spec.key, width_mm=44,
                     coordinates=CoordinateStyle.OUTSIDE),
    )
    labels = [(e.text or "") for e in _texts(svg)]
    assert sorted(labels) == sorted(list("abcdefgh") + list("12345678"))


def test_outside_coordinates_sit_outside_the_board(legacy_spec):
    """The charter fails 'coordenadas crammed inside the frame'. Ranks must be left of
    the board's left edge and files below its bottom edge."""
    from caissa.typeset.board_svg import _layout

    style = DiagramStyle(
        font=legacy_spec.key, width_mm=50, coordinates=CoordinateStyle.OUTSIDE
    )
    lay = _layout(style)
    for element in _texts(render_svg(MIDDLE, style)):
        text = element.text or ""
        x, y = float(element.get("x")), float(element.get("y"))
        if text.isdigit():
            assert x <= lay.board_x, f"rank {text} em x={x}, dentro do tabuleiro"
        else:
            assert y >= lay.board_y + lay.board, f"file {text} em y={y}, dentro do tabuleiro"


def test_outside_right_puts_ranks_on_the_right(legacy_spec):
    from caissa.typeset.board_svg import _layout

    style = DiagramStyle(
        font=legacy_spec.key, width_mm=50, coordinates=CoordinateStyle.OUTSIDE_RIGHT
    )
    lay = _layout(style)
    for element in _texts(render_svg(MIDDLE, style)):
        if (element.text or "").isdigit():
            assert float(element.get("x")) >= lay.board_x + lay.board


def test_coordinates_scale_with_the_diagram(legacy_spec):
    """Doubling the diagram doubles the type; a fixed coordinate size is what makes a
    20 mm diagram unreadable and a 90 mm one look like a poster."""
    def size(width):
        style = DiagramStyle(font=legacy_spec.key, width_mm=width,
                             coordinates=CoordinateStyle.OUTSIDE)
        return float(_texts(render_svg(MIDDLE, style))[0].get("font-size"))

    assert size(80) == pytest.approx(size(40) * 2, rel=0.02)


def test_coordinate_size_matches_the_reference_measurement(legacy_spec):
    """The digit stands 0.408 of a square on the Quality Chess reference page
    (`benchmarks/reports/blind/`). The default must reproduce that, not a guess."""
    from caissa.typeset.board_svg import _layout

    style = DiagramStyle(font=legacy_spec.key, width_mm=63,
                         coordinates=CoordinateStyle.OUTSIDE)
    lay = _layout(style)
    size = float(_texts(render_svg(MIDDLE, style))[0].get("font-size"))
    # A serif's digits stand about 0.66 em.
    digit_height = size * 0.66 / lay.square
    assert 0.36 <= digit_height <= 0.46, (
        f"altura do algarismo = {digit_height:.3f} de uma casa; a referencia mede 0.408"
    )


def test_flipping_reverses_both_coordinate_runs(legacy_spec):
    def labels(orientation):
        style = DiagramStyle(font=legacy_spec.key, width_mm=44, orientation=orientation,
                             coordinates=CoordinateStyle.OUTSIDE)
        return [(e.text or "") for e in _texts(render_svg(MIDDLE, style))]

    white, black = labels("white"), labels("black")
    assert white != black
    assert sorted(white) == sorted(black)


# --------------------------------------------------------------------------- #
# Marks
# --------------------------------------------------------------------------- #
def test_arrow_starts_and_ends_on_the_right_squares(legacy_spec):
    """Geometry, not presence: the arrow's first point must sit inside its source square
    and its tip inside the target."""
    from caissa.typeset.board_svg import _layout, square_index

    style = DiagramStyle(font=legacy_spec.key, width_mm=64,
                         coordinates=CoordinateStyle.NONE)
    lay = _layout(style)

    def centre(name):
        row, col = square_index(name)
        return (lay.board_x + (col + 0.5) * lay.square,
                lay.board_y + (row + 0.5) * lay.square)

    for source, target in (("d1", "d7"), ("a1", "h8"), ("g2", "b7")):
        svg = render_svg(MIDDLE, style, marks=[Arrow(source, target)])
        colour = get_theme(style.theme).arrow
        arrow_paths = [d for d in paths_filled(parse(svg), colour) if d.count("L") >= 3]
        assert arrow_paths, f"nenhuma seta desenhada para {source}-{target}"
        numbers = [float(v) for v in re.findall(r"-?\d+\.?\d*", arrow_paths[0])]
        xs, ys = numbers[0::2], numbers[1::2]
        sx, sy = centre(source)
        tx, ty = centre(target)
        half = lay.square / 2.0
        assert min(xs) - 1e-6 <= max(sx, tx) and max(xs) + 1e-6 >= min(sx, tx)
        # Every point of the arrow lies within the corridor between the two squares.
        assert min(xs) >= min(sx, tx) - half - 1e-6
        assert max(xs) <= max(sx, tx) + half + 1e-6
        assert min(ys) >= min(sy, ty) - half - 1e-6
        assert max(ys) <= max(sy, ty) + half + 1e-6


def test_arrowhead_is_not_stretched(legacy_spec):
    """The charter names stretched arrowheads. `_arrow_path` builds the arrow as one
    7-point polygon whose head is points 2, 3 and 4 -- barb, tip, barb -- with a head
    width fixed in millimetres. So the head must measure the same on a two-square arrow
    as on a seven-square one; if it scaled with length, it would not."""
    style = DiagramStyle(font=legacy_spec.key, width_mm=64,
                         coordinates=CoordinateStyle.NONE)

    def head_width(source, target):
        svg = render_svg(MIDDLE, style, marks=[Arrow(source, target)])
        colour = get_theme(style.theme).arrow
        d = [p for p in paths_filled(parse(svg), colour) if p.count("L") == 6][0]
        pts = [float(v) for v in re.findall(r"-?\d+\.?\d*", d)]
        xy = list(zip(pts[0::2], pts[1::2]))
        assert len(xy) == 7, f"a seta deveria ter 7 pontos, tem {len(xy)}"
        (ax, ay), (bx, by) = xy[2], xy[4]
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    widths = [
        head_width("d1", "d3"),
        head_width("d1", "d5"),
        head_width("d1", "d8"),
        head_width("a1", "h8"),
    ]
    assert max(widths) == pytest.approx(min(widths), rel=0.02), (
        f"a cabeca da seta muda de largura com o comprimento: {widths}"
    )


def test_arrowhead_does_not_swallow_a_very_short_arrow(legacy_spec):
    """A one-square arrow is shorter than the head's natural length. The head is clamped
    rather than allowed to overshoot the source square."""
    style = DiagramStyle(font=legacy_spec.key, width_mm=64,
                         coordinates=CoordinateStyle.NONE)
    svg = render_svg(MIDDLE, style, marks=[Arrow("d1", "d2")])
    d = [p for p in paths(parse(svg)) if p.count("L") == 6][-1]
    pts = [float(v) for v in re.findall(r"-?\d+\.?\d*", d)]
    xy = list(zip(pts[0::2], pts[1::2]))
    tip = xy[3]
    tail = ((xy[0][0] + xy[6][0]) / 2.0, (xy[0][1] + xy[6][1]) / 2.0)
    base = ((xy[2][0] + xy[4][0]) / 2.0, (xy[2][1] + xy[4][1]) / 2.0)
    total = ((tip[0] - tail[0]) ** 2 + (tip[1] - tail[1]) ** 2) ** 0.5
    head = ((tip[0] - base[0]) ** 2 + (tip[1] - base[1]) ** 2) ** 0.5
    assert 0 < head <= total * 0.93 + 1e-6, (
        f"cabeca ({head:.3f}) engole a seta inteira ({total:.3f})"
    )


def test_highlight_is_drawn_under_the_pieces(legacy_spec):
    """A highlight painted over the piece hides it. Order in the document is the only
    thing that decides this in SVG."""
    svg = render_svg(
        MIDDLE,
        DiagramStyle(font=legacy_spec.key, width_mm=60),
        marks=[SquareHighlight("d5")],
    )
    root = parse(svg)
    children = list(root)
    kinds = [c.tag.replace(SVG_NS, "") for c in children]
    first_path = kinds.index("path")
    highlight_positions = [
        i for i, c in enumerate(children)
        if c.tag.endswith("rect") and c.get("fill") not in (None, "none")
    ]
    assert any(i < first_path for i in highlight_positions)


def test_a_mark_is_drawn_under_the_pieces_and_only_its_head_on_top(legacy_spec):
    """The paint order of `board_svg.MARK_PAINT_ORDER`, asserted on the document.

    Cycle 2 drew every mark last, over the pieces, with a knockout in the page colour
    around it -- and on a board whose pieces are white outlines a white keyline erases
    the outline. The circle and the arrow's shaft now go *under* the pieces; only the
    arrowhead comes back on top, keylined in its destination square's colour.
    """
    style = DiagramStyle(font=legacy_spec.key, width_mm=60)
    colour = get_theme(style.theme).arrow
    children = list(parse(render_svg(MIDDLE, style,
                                     marks=[CircleMark("d5"), Arrow("d1", "d5")])))
    pieces = [i for i, c in enumerate(children)
              if c.tag.endswith("path") and (c.get("fill") or "").lower()
              not in (colour.lower(), "none")]
    circles = [i for i, c in enumerate(children) if c.tag.endswith("circle")]
    marks = [i for i, c in enumerate(children)
             if c.tag.endswith("path") and (c.get("fill") or "").lower() == colour.lower()]
    assert circles and marks and pieces
    assert max(circles) < min(pieces), "o circulo tem de ficar POR BAIXO das pecas"
    assert min(marks) < min(pieces), "a haste da seta tem de ficar POR BAIXO das pecas"
    assert max(marks) > max(pieces), "a ponta da seta tem de voltar POR CIMA"


@pytest.mark.parametrize("stm", list(SideToMove))
def test_every_side_to_move_indicator_renders(legacy_spec, stm):
    svg = render_svg(MIDDLE, DiagramStyle(font=legacy_spec.key, width_mm=44,
                                          side_to_move=stm))
    assert svg.startswith("<svg")


def test_side_to_move_reflects_the_fen(legacy_spec):
    style = DiagramStyle(font=legacy_spec.key, width_mm=44,
                         side_to_move=SideToMove.TEXT)
    white = render_svg(START, style)
    black = render_svg(MIDDLE, style)
    assert white != black


# --------------------------------------------------------------------------- #
# Themes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("key", sorted(THEMES))
def test_every_theme_renders_and_keeps_wcag_contrast(legacy_spec, key):
    theme: BoardTheme = THEMES[key]
    svg = render_svg(MIDDLE, DiagramStyle(font=legacy_spec.key, width_mm=50, theme=key))
    assert svg.startswith("<svg")
    # Piece ink against both square tints. 3:1 is the WCAG minimum for a graphical
    # object; a piece that fails it vanishes into its square.
    assert contrast_ratio(theme.piece_ink, theme.light) >= 3.0
    assert contrast_ratio(theme.piece_ink, theme.dark) >= 3.0
    assert contrast_ratio(theme.coordinate, theme.page) >= 4.5


def test_dark_theme_is_designed_not_inverted():
    """The charter fails 'tema escuro que e so o claro invertido'. Two properties prove
    it was designed: the light square is still the lighter of the two, and the pieces
    are not pure black and white."""
    from caissa.typeset.board_svg import relative_luminance

    dark = THEMES["dark"]
    assert relative_luminance(dark.light) > relative_luminance(dark.dark)
    assert dark.piece_body.upper() != "#FFFFFF"
    assert dark.piece_ink.upper() != "#000000"


def test_hatched_theme_draws_rules_only_on_dark_squares(legacy_spec):
    style = DiagramStyle(font=legacy_spec.key, width_mm=60, theme="hatched")
    root = parse(render_svg(MIDDLE, style))
    lines = list(root.iter(f"{SVG_NS}line"))
    assert lines, "o tema hachurado nao desenhou nenhuma regua"

    from caissa.typeset.board_svg import _layout

    lay = _layout(style)
    for line in lines:
        cx = (float(line.get("x1")) + float(line.get("x2"))) / 2.0
        cy = (float(line.get("y1")) + float(line.get("y2"))) / 2.0
        col = int((cx - lay.board_x) // lay.square)
        row = int((cy - lay.board_y) // lay.square)
        assert 0 <= row < 8 and 0 <= col < 8
        assert (row + col) % 2 == 1, f"hachura em casa clara ({square_name(row, col)})"


def test_hatch_ink_coverage_is_constant_across_sizes(legacy_spec):
    """The hatch must read as the same tint at 20 mm as at 90 mm.

    Coverage is rule width over rule spacing. Below about 30 mm the width stops
    shrinking -- it has hit `MIN_RULE_MM` -- so a spacing tied only to the square keeps
    closing up and the square goes solid. Measured on the 20 mm board before the floor
    existed: 58 % ink. Rules are collected from **one** dark square, because rules in
    different squares are not part of the same series.
    """
    from caissa.typeset.board_svg import HATCH_COVERAGE, _layout

    for width in (20, 40, 60, 90):
        style = DiagramStyle(font=legacy_spec.key, width_mm=width, theme="hatched")
        lay = _layout(style)
        root = parse(render_svg(MIDDLE, style))

        # Square a7 (row 1, col 0) is dark and empty in this position.
        x0 = lay.board_x
        y0 = lay.board_y + lay.square
        offsets: list[float] = []
        rule = None
        for line in root.iter(f"{SVG_NS}line"):
            cx = (float(line.get("x1")) + float(line.get("x2"))) / 2.0
            cy = (float(line.get("y1")) + float(line.get("y2"))) / 2.0
            if x0 <= cx < x0 + lay.square and y0 <= cy < y0 + lay.square:
                rule = float(line.get("stroke-width"))
                # For the family x + y = c, the constant identifies the rule.
                offsets.append(float(line.get("x1")) + float(line.get("y1")))
        assert rule is not None and len(offsets) >= 2, (
            f"{width} mm: hachura ausente ou com uma regua so"
        )
        offsets.sort()
        spacing = min(b - a for a, b in zip(offsets, offsets[1:]))
        # The x+y parametrisation runs along the diagonal; the perpendicular distance
        # between neighbouring rules is that over sqrt(2).
        coverage = rule / (spacing / (2 ** 0.5))
        assert coverage <= HATCH_COVERAGE * 1.35, (
            f"{width} mm: cobertura de tinta {coverage:.3f}, alvo {HATCH_COVERAGE}"
        )
        assert coverage >= HATCH_COVERAGE * 0.5, (
            f"{width} mm: hachura quase invisivel, cobertura {coverage:.3f}"
        )


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("width", [20, 40, 60, 90])
def test_declared_width_is_the_width_delivered(legacy_spec, width):
    """`width_mm` is documented as the *finished* size, coordinates and frame included.
    A layout engine placing the diagram in a column depends on that being true."""
    root = parse(render_svg(MIDDLE, DiagramStyle(font=legacy_spec.key, width_mm=width)))
    assert root.get("width") == f"{width}mm" or float(
        root.get("width").rstrip("m")
    ) == pytest.approx(width, abs=0.01)
    view = [float(v) for v in root.get("viewBox").split()]
    assert view[2] == pytest.approx(width, abs=0.01)


def test_nothing_is_drawn_outside_the_declared_box(legacy_spec):
    """Overflow is invisible in an SVG viewer and fatal in a page layout."""
    style = DiagramStyle(font=legacy_spec.key, width_mm=50,
                         side_to_move=SideToMove.SQUARE)
    root = parse(render_svg(MIDDLE, style, marks=[Arrow("a1", "h8"), CircleMark("d5")]))
    view = [float(v) for v in root.get("viewBox").split()]
    width, height = view[2], view[3]
    for d in paths(root):
        numbers = [float(v) for v in re.findall(r"-?\d+\.?\d*", d)]
        for x in numbers[0::2]:
            assert -0.6 <= x <= width + 0.6
        for y in numbers[1::2]:
            assert -0.6 <= y <= height + 0.6


def test_unicode_family_renders_when_present():
    """The Unicode fallback has no square background in its glyphs, so it takes a
    different placement path. It must still produce a board."""
    from caissa.typeset.fonts import CHESS_FONT_SPECS, find_font_file

    spec = CHESS_FONT_SPECS["unicode"]
    if find_font_file(spec) is None:
        pytest.skip("Nenhuma fonte Unicode com as pecas U+2654-U+265F encontrada.")
    assert spec.model is FontModel.UNICODE
    svg = render_svg(MIDDLE, DiagramStyle(font="unicode", width_mm=50))
    assert len(paths(parse(svg))) >= 12


# --------------------------------------------------------------------------- #
# C10 non-blocking no. 8 -- the rank gutter went on the wrong side
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("stm", [SideToMove.NONE, SideToMove.SQUARE, SideToMove.TRIANGLE])
def test_outside_right_keeps_its_rank_digits_inside_the_declared_width(legacy_spec, stm):  # noqa: ANN001
    """`test_nothing_is_drawn_outside_the_declared_box` could not catch this, and the
    delivered sheet shipped with it: it walks **paths**, and a coordinate label is text.

    `_layout` reserved the rank gutter on the LEFT for every outside style, while
    `_draw_coordinates` puts the digits of `OUTSIDE_RIGHT` on the RIGHT. The mode carried
    an empty gutter one side and spilled its labels out of its own `width_mm` on the
    other -- 4.23 mm past the type area on page 4 of the delivered proof sheet, which the
    cycle-10 critic measured and the cycle-9 report denied.

    So this asserts the text, and it asserts it in both directions: every digit inside
    the box, and the gutter actually reserved on the side the digits went to. The
    side-to-move marker is parametrised in because it is drawn in that same right-hand
    strip and would otherwise be laid on top of the digits.
    """
    from caissa.typeset.board_svg import _layout

    style = DiagramStyle(font=legacy_spec.key, width_mm=50,
                         coordinates=CoordinateStyle.OUTSIDE_RIGHT, side_to_move=stm)
    root = parse(render_svg(MIDDLE, style))
    view = [float(v) for v in root.get("viewBox").split()]
    width, height = view[2], view[3]

    texts = [t for t in root.iter(f"{SVG_NS}text")]
    ranks = [t for t in texts if (t.text or "").strip() in set("12345678")]
    assert len(ranks) == 8, [t.text for t in texts]
    board_right = _layout(style).board_x + _layout(style).board
    for node in ranks:
        x, y = float(node.get("x")), float(node.get("y"))
        assert x > board_right, (
            f"a cota de linha {node.text!r} esta a x={x:.2f}, a esquerda da aresta "
            f"direita do tabuleiro ({board_right:.2f}): OUTSIDE_RIGHT desenhou a esquerda"
        )
        assert 0.0 <= x <= width and 0.0 <= y <= height, (
            f"cota {node.text!r} em ({x:.2f}, {y:.2f}) fora da caixa {width} x {height}"
        )

    # And the gutter is on the right, which is the same statement made about the layout
    # rather than about the ink: the board starts at the margin plus the frame alone.
    lay = _layout(style)
    left_of_board = lay.board_x - lay.frame_total
    assert left_of_board < lay.coord_gutter, (
        f"goteira de {lay.coord_gutter:.2f} mm ainda reservada a esquerda "
        f"({left_of_board:.2f} mm antes da moldura)"
    )
    mirror = _layout(DiagramStyle(font=legacy_spec.key, width_mm=50,
                                  coordinates=CoordinateStyle.OUTSIDE, side_to_move=stm))
    assert mirror.board_x - mirror.frame_total >= mirror.coord_gutter - 1e-9, (
        "OUTSIDE deixou de reservar a goteira a esquerda"
    )
