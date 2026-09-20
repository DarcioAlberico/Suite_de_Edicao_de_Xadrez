"""Shared IR-to-text services every exporter needs and none should reinvent.

Three jobs live here because getting them wrong in five different places is
exactly the failure mode the Document IR exists to prevent:

**Rendering a move.** SPEC section 5.5 is the promise that ``Nf3`` becomes
``Cf3`` in Portuguese, ``Sf3`` in German and a knight glyph in figurine *from the
same IR*. The translation itself belongs to
:mod:`caissa.core.chess.notation_tables`; what belongs here is the decision of
which language and style apply -- the node's own, falling back to the document's
settings -- so that the five formats cannot disagree.

**NAG symbols.** ``$1`` is ``!`` and ``$14`` is a plus-over-equals sign, and a
chess book that prints ``$14`` has failed. The table is the PGN standard's, with
the typographic characters a publisher actually sets.

**PGN.** A :class:`~caissa.core.model.game.GameScore` written back out as PGN,
with variations, comments, NAGs, clocks and evaluations. Every exporter needs it:
HTML puts it in a data attribute so a replay script can read it, LaTeX feeds it
to ``xskak``, and :mod:`caissa.export.fidelity` reads it back to prove the game
survived.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from caissa.core.chess.notation_tables import (
    DEFAULT_LANGUAGE,
    FigurineSet,
    MoveRenderStyle,
    NotationError,
    render_san,
)
from caissa.core.model import (
    Color,
    Document,
    GameHeaders,
    GameScore,
    Inline,
    InlineDiagram,
    LineBreak,
    Mark,
    MarkKind,
    MathInline,
    Move,
    MoveNode,
    NagSymbol,
    NonBreakingSpace,
    PieceGlyph,
    Space,
    Tab,
    Text,
    inline_children,
)
from caissa.notation.nag_table import NAG_BY_CODE

__all__ = [
    "NAG_SYMBOLS",
    "escape_pgn_comment",
    "figurine_char",
    "game_from_pgn",
    "game_to_pgn",
    "inline_plain_text",
    "move_commands",
    "nag_symbol",
    "render_move",
    "split_move_commands",
]


_PGN_ONLY_NAGS: Mapping[int, str] = {
    8: "□",  # singular move: the same box as $7
    11: "=",  # equal, quiet position
    12: "=",  # equal, active position
}
"""PGN NAGs with a printed form that :mod:`caissa.notation.nag_table` has no row for.

Only the codes; when the table gains them these entries lose to it.
"""

NAG_SYMBOLS: Mapping[int, str] = {
    **_PGN_ONLY_NAGS,
    **{int(code[1:]): nag.glyph for code, nag in NAG_BY_CODE.items()},
}
"""PGN Numeric Annotation Glyphs and the characters a publisher sets for them.

Derived from :data:`caissa.notation.nag_table.NAG_BY_CODE` (OCR_UI_ROADMAP_C2
A6) so the exported book and the import tokenizer agree on the glyph: ``$22``
is the zugzwang circle ``⨀`` and ``$138`` the time-pressure ``⨁``, never the
same sign for both. Only the glyphs that have a conventional printed form are
listed. A NAG with no entry renders as ``$n``, which is both honest and
searchable -- silently dropping it would lose the annotator's judgement.
"""

_FIGURINE_WHITE: Mapping[str, str] = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
}

_FIGURINE_BLACK: Mapping[str, str] = {
    "K": "♚",
    "Q": "♛",
    "R": "♜",
    "B": "♝",
    "N": "♞",
    "P": "♟",
}

_PIECE_LETTER: Mapping[str, str] = {
    "king": "K",
    "queen": "Q",
    "rook": "R",
    "bishop": "B",
    "knight": "N",
    "pawn": "P",
}


def nag_symbol(nag: int) -> str:
    """Render one Numeric Annotation Glyph.

    Args:
        nag: The glyph number, ``1``-``255``.

    Returns:
        The conventional symbol, or ``$n`` when the glyph has no printed form.
    """
    return NAG_SYMBOLS.get(nag, f"${nag}")


def figurine_char(piece: str, figurine_set: FigurineSet = FigurineSet.BLACK) -> str:
    """Return the Unicode chess glyph for a piece.

    Args:
        piece: A piece name (``"knight"``) or an English SAN letter (``"N"``).
        figurine_set: Which glyph set to use. ``BLACK`` -- the solid glyphs --
            is the print convention regardless of whose piece it is.

    Returns:
        The glyph, or the letter when there is no glyph.
    """
    letter = _PIECE_LETTER.get(piece.lower(), piece.upper()[:1])
    table = _FIGURINE_WHITE if figurine_set is FigurineSet.WHITE else _FIGURINE_BLACK
    return table.get(letter, letter)


def render_move(move: Move, document: Document | None = None) -> str:
    """Render a move node in the language and style it asks for.

    Args:
        move: The move.
        document: The document, for the settings a move leaves unspecified.

    Returns:
        The printed form, move number prefix and NAG symbols included.
    """
    settings = document.settings if document is not None else None
    language = move.language or (settings.notation_language if settings else DEFAULT_LANGUAGE)
    style = move.render if move.render is not None else MoveRenderStyle.LETTERS
    figurine_set = move.figurine_set or (settings.figurine_set if settings else FigurineSet.BLACK)
    try:
        body = render_san(
            move.san, language=language, style=style, figurine_set=figurine_set
        )
    except NotationError:
        # An unrecognised token is printed verbatim. A book that silently drops a
        # move the reader can see in the source PDF is worse than one that prints
        # something odd, and the OCR front's confidence data is the place to flag it.
        body = move.san

    prefix = ""
    if move.move_number_text:
        prefix = move.move_number_text
    elif move.show_move_number and move.ply:
        prefix = f"{move.move_number}..." if move.is_black_move else f"{move.move_number}."
    suffix = "".join(nag_symbol(nag) for nag in move.nags)
    return f"{prefix}{body}{suffix}" if prefix else f"{body}{suffix}"


def inline_plain_text(nodes: Sequence[Inline], document: Document | None = None) -> str:
    """Flatten inlines to plain text, rendering moves and glyphs properly.

    :func:`caissa.core.model.inline.plain_text` exists and is the right tool for
    a structural comparison; this is the tool for anything a *person* reads -- a
    caption, an alt text, a bookmark title -- because it prints ``Cf3`` where
    the IR holds a :class:`~caissa.core.model.inline.Move`.

    Args:
        nodes: The inlines to flatten.
        document: The document, for notation settings.

    Returns:
        The plain text.
    """
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.content)
        elif isinstance(node, Move):
            parts.append(render_move(node, document))
        elif isinstance(node, PieceGlyph):
            parts.append(figurine_char(node.piece.value, node.figurine_set))
        elif isinstance(node, NagSymbol):
            parts.append(nag_symbol(node.nag))
        elif isinstance(node, MathInline):
            parts.append(node.latex)
        elif isinstance(node, InlineDiagram):
            parts.append("[diagrama]")
        elif isinstance(node, LineBreak):
            parts.append("\n")
        elif isinstance(node, NonBreakingSpace):
            parts.append(" ")
        elif isinstance(node, Tab):
            parts.append("\t")
        elif isinstance(node, Space):
            parts.append(" ")
        else:
            children = inline_children(node)
            if children:
                parts.append(inline_plain_text(children, document))
    return "".join(parts)


# --------------------------------------------------------------------------- #
# PGN
# --------------------------------------------------------------------------- #
def game_to_pgn(score: GameScore, *, include_headers: bool = True) -> str:
    """Serialise a game score back to PGN.

    Everything the IR carries is written: variations to any depth, comments
    before and after a move, NAGs, ``[%clk]`` and ``[%eval]`` commands, and
    ``[%cal]``/``[%csl]`` arrows and highlights. That completeness is the point:
    :mod:`caissa.export.fidelity` reads the result back with ``python-chess`` and
    compares, exactly as ``PGN_Live_Editor`` did, so anything not written here
    shows up as a measured loss rather than a quiet one.

    Args:
        score: The game.
        include_headers: Write the tag pair section.

    Returns:
        The PGN text, newline-terminated.
    """
    lines: list[str] = []
    if include_headers:
        for name, value in score.headers.as_tuples():
            lines.append(f'[{name} "{_escape_tag(value)}"]')
        if score.initial_fen:
            lines.append('[SetUp "1"]')
            lines.append(f'[FEN "{_escape_tag(score.initial_fen)}"]')
        if score.variant and score.variant != "standard":
            lines.append(f'[Variant "{_escape_tag(score.variant)}"]')
        lines.append("")

    tokens: list[str] = []
    if score.initial_comment:
        tokens.append(f"{{{_escape_comment(score.initial_comment)}}}")

    _write_continuations(score.children, tokens, force_number=True)
    tokens.append(score.result)
    lines.append(_wrap(tokens))
    return "\n".join(lines) + "\n"


def _write_continuations(
    children: Sequence[MoveNode], tokens: list[str], *, force_number: bool
) -> None:
    """Append a mainline and its alternatives to a PGN token list.

    The shape of the IR and the shape of PGN differ in exactly one place, and it
    is the classic bug: ``children[1:]`` are alternatives to ``children[0]``, so
    they are written *after* ``children[0]``'s move token, not after the move
    that preceded them. Getting this backwards produces a file ``python-chess``
    rejects with ``illegal san``, which is why
    :mod:`caissa.export.fidelity` reads every game back.

    The mainline is walked iteratively and only variations recurse, so a
    three-hundred-move game costs no stack.

    Args:
        children: Continuations; ``children[0]`` is the mainline.
        tokens: The token list being built.
        force_number: Print the move number even for a Black move, which PGN
            requires at the start of a line and after a comment.
    """
    current: Sequence[MoveNode] = children
    needs_number = force_number
    while current:
        main = current[0]
        needs_number = _write_single(main, tokens, force_number=needs_number)
        for alternative in current[1:]:
            tokens.append("(")
            _write_continuations((alternative,), tokens, force_number=True)
            tokens.append(")")
            needs_number = True
        current = main.children


def _write_single(node: MoveNode, tokens: list[str], *, force_number: bool) -> bool:
    """Append one move -- comments, number, SAN and NAGs -- to the token list.

    Args:
        node: The move.
        tokens: The token list being built.
        force_number: Print the number even for a Black move.

    Returns:
        Whether the *next* move needs an explicit number, which it does after a
        comment.
    """
    needs_number = force_number
    if node.comment_before:
        tokens.append(f"{{{_escape_comment(node.comment_before)}}}")
        needs_number = True

    if not node.is_black_move:
        tokens.append(f"{node.move_number}.")
    elif needs_number:
        tokens.append(f"{node.move_number}...")

    tokens.append(node.san)
    for nag in node.nags:
        tokens.append(f"${nag}")

    trailing = _trailing_comment(node)
    if trailing:
        tokens.append(f"{{{trailing}}}")
        return True
    return False


def _trailing_comment(node: MoveNode) -> str:
    """Build the comment written after a move, commands included.

    Args:
        node: The move.

    Returns:
        The comment text, empty when there is nothing to write.
    """
    parts: list[str] = []
    if node.comment_after:
        parts.append(node.comment_after.strip())
    if node.clock is not None and node.clock.text:
        parts.append(f"[%{node.clock.kind.value} {node.clock.text}]")
    if node.evaluation is not None and node.evaluation.text:
        parts.append(f"[%eval {node.evaluation.text}]")
    arrows = _mark_command("cal", node.arrows)
    if arrows:
        parts.append(arrows)
    highlights = _mark_command("csl", node.highlights)
    if highlights:
        parts.append(highlights)
    return " ".join(part for part in parts if part)


def _mark_command(command: str, marks: Sequence[Mark]) -> str:
    """Render board marks as a PGN ``[%cal]`` or ``[%csl]`` command.

    Args:
        command: ``"cal"`` for arrows, ``"csl"`` for highlighted squares.
        marks: The marks.

    Returns:
        The command, or an empty string when there is nothing to write.
    """
    items: list[str] = []
    for mark in marks:
        letter = _mark_colour_letter(mark)
        if command == "cal":
            if mark.kind is MarkKind.ARROW and mark.origin and mark.target:
                items.append(f"{letter}{mark.origin}{mark.target}")
        else:
            for square in mark.squares:
                items.append(f"{letter}{square}")
    if not items:
        return ""
    return f"[%{command} {','.join(items)}]"


def _mark_colour_letter(mark: Mark) -> str:
    """Map a mark colour onto the four letters the ``[%cal]`` syntax allows.

    Args:
        mark: The mark.

    Returns:
        ``G``, ``R``, ``Y`` or ``B``.
    """
    if mark.color is None:
        return "G"
    try:
        red, green, blue = mark.color.to_rgb_tuple()
    except Exception:
        return "G"
    if red > 0.55 and green > 0.55 and blue < 0.45:
        return "Y"
    if red >= green and red >= blue:
        return "R"
    if blue >= green:
        return "B"
    return "G"


def _escape_tag(value: str) -> str:
    """Escape a PGN tag value.

    Args:
        value: The raw value.

    Returns:
        The value with backslashes and quotes escaped.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def escape_pgn_comment(text: str) -> str:
    """Make a comment safe to sit between PGN braces.

    Args:
        text: The raw comment.

    Returns:
        The comment with braces neutralised and newlines folded.
    """
    return _escape_comment(text)


def move_commands(node: MoveNode) -> str:
    """Render the ``[%clk]``, ``[%eval]``, ``[%cal]`` and ``[%csl]`` of one move.

    Args:
        node: The move.

    Returns:
        The commands, space separated, or an empty string.
    """
    parts: list[str] = []
    if node.clock is not None and node.clock.text:
        parts.append(f"[%{node.clock.kind.value} {node.clock.text}]")
    if node.evaluation is not None and node.evaluation.text:
        parts.append(f"[%eval {node.evaluation.text}]")
    arrows = _mark_command("cal", node.arrows)
    if arrows:
        parts.append(arrows)
    highlights = _mark_command("csl", node.highlights)
    if highlights:
        parts.append(highlights)
    return " ".join(parts)


def split_move_commands(
    comment: str,
) -> tuple[object | None, object | None, tuple[Mark, ...], tuple[Mark, ...], str]:
    """Pull the PGN commands out of a comment.

    Args:
        comment: The raw comment text.

    Returns:
        A tuple of clock, evaluation, arrows, highlights and the rest.
    """
    return _split_commands(comment)


def _escape_comment(text: str) -> str:
    """Make a comment safe to sit between PGN braces.

    Args:
        text: The raw comment.

    Returns:
        The comment with braces neutralised and newlines folded.
    """
    return text.replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def _wrap(tokens: Iterable[str], width: int = 79) -> str:
    """Wrap PGN movetext at the standard column.

    Args:
        tokens: The movetext tokens.
        width: Maximum line length.

    Returns:
        The wrapped movetext.
    """
    flat = " ".join(tokens).replace("( ", "(").replace(" )", ")")
    lines: list[str] = []
    current = ""
    for word in flat.split(" "):
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# PGN, read back
# --------------------------------------------------------------------------- #
def game_from_pgn(pgn: str) -> GameScore:
    """Rebuild a game score from PGN.

    Uses ``python-chess`` rather than a hand-rolled parser, for the same reason
    ``PGN_Live_Editor`` did: the point of reading our own output back is to be
    checked by something that is not us. A reader that shared this module's
    assumptions would validate nothing.

    Args:
        pgn: The PGN text.

    Returns:
        The reconstructed game; an empty score when the text is unreadable.
    """
    import io

    import chess.pgn

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return GameScore()
    if game is None:
        return GameScore()

    headers = _headers_from_pgn(game.headers)
    initial_fen = game.headers.get("FEN") if game.headers.get("SetUp") == "1" else None
    variant = game.headers.get("Variant", "standard") or "standard"
    return GameScore(
        headers=headers,
        initial_fen=initial_fen,
        variant=variant,
        initial_comment=(game.comment or "").strip(),
        children=tuple(_move_node_from_pgn(child) for child in game.variations),
    )


def _headers_from_pgn(headers: Mapping[str, str]) -> GameHeaders:
    """Split PGN tags into the seven-tag roster and the rest.

    Args:
        headers: The tag pairs as ``python-chess`` read them.

    Returns:
        The reconstructed headers.
    """
    from caissa.core.model import PgnTag

    roster = {"Event", "Site", "Date", "Round", "White", "Black", "Result"}
    skipped = roster | {"SetUp", "FEN", "Variant"}
    extra = tuple(
        PgnTag(name=name, value=value) for name, value in headers.items() if name not in skipped
    )
    return GameHeaders(
        event=headers.get("Event", "?"),
        site=headers.get("Site", "?"),
        date=headers.get("Date", "????.??.??"),
        round=headers.get("Round", "?"),
        white=headers.get("White", "?"),
        black=headers.get("Black", "?"),
        result=headers.get("Result", "*"),
        extra=extra,
    )


def _move_node_from_pgn(node: object) -> MoveNode:
    """Rebuild one move node and everything under it.

    Args:
        node: A ``chess.pgn.ChildNode``.

    Returns:
        The move node.
    """
    board = node.parent.board()  # type: ignore[attr-defined]
    move = node.move  # type: ignore[attr-defined]
    san = board.san(move)
    ply = board.ply() + 1
    after = node.board()  # type: ignore[attr-defined]
    comment = (node.comment or "").strip()  # type: ignore[attr-defined]
    clock, evaluation, arrows, highlights, remainder = _split_commands(comment)
    return MoveNode(
        san=san,
        ply=ply,
        position_before=board.fen(),
        position_after=after.fen(),
        uci=move.uci(),
        nags=tuple(sorted(node.nags)),  # type: ignore[attr-defined]
        comment_before=(node.starting_comment or "").strip(),  # type: ignore[attr-defined]
        comment_after=remainder,
        arrows=arrows,
        highlights=highlights,
        clock=clock,
        evaluation=evaluation,
        children=tuple(_move_node_from_pgn(child) for child in node.variations),  # type: ignore[attr-defined]
    )


_COMMAND_RE = None


def _split_commands(
    comment: str,
) -> tuple[object | None, object | None, tuple[Mark, ...], tuple[Mark, ...], str]:
    """Pull ``[%clk]``, ``[%eval]``, ``[%cal]`` and ``[%csl]`` out of a comment.

    Args:
        comment: The raw comment text.

    Returns:
        A tuple of clock, evaluation, arrows, highlights and the remaining text.
    """
    import re as _re

    from caissa.core.model import (
        ClockAnnotation,
        ClockKind,
        EvalAnnotation,
    )
    from caissa.core.model import (
        Mark as IrMark,
    )
    from caissa.core.model import (
        MarkKind as IrMarkKind,
    )

    clock: ClockAnnotation | None = None
    evaluation: EvalAnnotation | None = None
    arrows: list[IrMark] = []
    highlights: list[IrMark] = []

    def take(match: _re.Match[str]) -> str:
        nonlocal clock, evaluation
        name = match.group(1)
        body = match.group(2).strip()
        if name in ("clk", "emt", "egt", "mct"):
            clock = ClockAnnotation(kind=ClockKind(name), text=body, seconds=_seconds(body))
        elif name == "eval":
            evaluation = _eval_from_text(body)
        elif name == "cal":
            for item in body.split(","):
                item = item.strip()
                if len(item) == 5:
                    arrows.append(
                        IrMark(
                            kind=IrMarkKind.ARROW,
                            squares=(item[1:3], item[3:5]),
                            color=_colour_for_letter(item[0]),
                        )
                    )
        elif name == "csl":
            for item in body.split(","):
                item = item.strip()
                if len(item) == 3:
                    highlights.append(
                        IrMark(
                            kind=IrMarkKind.SQUARE,
                            squares=(item[1:3],),
                            color=_colour_for_letter(item[0]),
                        )
                    )
        return ""

    remainder = _re.sub(r"\[%(\w+)\s+([^\]]*)\]", take, comment).strip()
    return clock, evaluation, tuple(arrows), tuple(highlights), remainder


def _colour_for_letter(letter: str) -> Color:
    """Map a ``[%cal]`` colour letter back to a colour.

    Args:
        letter: ``G``, ``R``, ``Y`` or ``B``.

    Returns:
        The colour.
    """
    return {
        "G": Color.rgb8(21, 128, 61),
        "R": Color.rgb8(185, 28, 28),
        "Y": Color.rgb8(217, 180, 40),
        "B": Color.rgb8(29, 78, 216),
    }.get(letter.upper(), Color.rgb8(21, 128, 61))


def _seconds(text: str) -> float | None:
    """Parse a clock reading into seconds.

    Args:
        text: The reading, ``"1:23:45"`` or ``"83.4"``.

    Returns:
        The value in seconds, or ``None`` when unparseable.
    """
    parts = text.split(":")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    total = 0.0
    for number in numbers:
        total = total * 60.0 + number
    return total


def _eval_from_text(text: str) -> object:
    """Parse an ``[%eval]`` body.

    Args:
        text: The body, ``"+0.34"``, ``"#-3"`` or ``"0.21/22"``.

    Returns:
        The evaluation annotation.
    """
    from caissa.core.model import EvalAnnotation, EvalKind

    body, _, depth_text = text.partition("/")
    body = body.strip()
    depth = int(depth_text) if depth_text.strip().isdigit() else None
    if body.startswith("#"):
        try:
            value = float(body[1:])
        except ValueError:
            value = 0.0
        return EvalAnnotation(kind=EvalKind.MATE, value=value, depth=depth, text=text)
    try:
        value = float(body)
    except ValueError:
        value = 0.0
    return EvalAnnotation(kind=EvalKind.CENTIPAWNS, value=value, depth=depth, text=text)
