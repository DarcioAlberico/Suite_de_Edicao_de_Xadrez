"""Fixtures for the index tests.

Everything here is synthetic and tiny.  The real corpus is measured by
``benchmarks``-style scripts and reported in ``docs/quality/F10_REPORT.md``;
a unit test that needed an 8 GB PGN would not be a unit test.
"""

from __future__ import annotations

import pytest

from caissa.core.model import (
    Diagram,
    Document,
    DocumentMetadata,
    Figure,
    GameHeaders,
    GameScore,
    Heading,
    MoveNode,
    Paragraph,
    PgnTag,
    Text,
)
from caissa.index import TextIndex, TextSource

STARTING_PLACEMENT = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

#: After 1.e4 c5 2.Nf3 d6 3.d4 cxd4.
SICILIAN_PLACEMENT = "rnbqkbnr/pp2pppp/3p4/8/3pP3/5N2/PPP2PPP/RNBQKB1R"

#: Opposite-coloured bishops, four pawns.  The SPEC 9 material example.
OPPOSITE_BISHOPS = "8/5pk1/6p1/3B4/8/2b5/5PPP/6K1"


@pytest.fixture
def index(tmp_path):
    """A fresh on-disk index.  On disk rather than in memory because the budget
    and the size gate are both measured with ``stat``.
    """
    with TextIndex(tmp_path / "idx.sqlite") as handle:
        yield handle


@pytest.fixture
def book_text():
    """A page of a chess book, in Portuguese, with the notation forms that matter."""
    return (
        "Capitulo 3: o Gambito da Dama\n\n"
        "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Bg5 Be7 5.e3 O-O 6.Nf3 h6\n\n"
        "As brancas jogam Bxc4 e ficam melhor.\n\n"
        "Aqui bxc4 seria um erro grave.\n\n"
        "Diagrama 12: as brancas jogam e ganham com O-O-O!!\n\n"
        "O peao passado decide: Qxd5+ Kh8 e depois e8=Q# encerra.\n"
    )


@pytest.fixture
def book(book_text):
    """``book_text`` as a source."""
    return TextSource(uri="mem://livro", title="Livro de Teste", text=book_text)


def _paragraph(text: str) -> Paragraph:
    return Paragraph(content=(Text(content=text),))


@pytest.fixture
def ir_document():
    """A small Document IR with a heading, a caption, a diagram and a game.

    Deliberately covers every scope the index distinguishes, because the scope
    mapping is the thing that makes "só legendas" possible at all.
    """
    game = GameScore(
        headers=GameHeaders(
            event="Torneio de Teste",
            site="Sao Paulo",
            date="1985.06.12",
            white="Kasparov, Garry",
            black="Karpov, Anatoly",
            result="1-0",
            extra=(PgnTag(name="ECO", value="B90"),),
        ),
        children=(
            MoveNode(
                san="e4",
                ply=1,
                position_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
                comment_after="Uma escolha classica de zugzwang futuro.",
                children=(
                    MoveNode(
                        san="c5",
                        ply=2,
                        nags=(4,),
                        position_after="rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    ),
                    MoveNode(
                        san="e5",
                        ply=2,
                        position_after="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    ),
                ),
            ),
        ),
    )
    return Document(
        metadata=DocumentMetadata(title="Manual de Finais"),
        body=(
            Heading(level=1, content=(Text(content="Finais de bispos opostos"),)),
            _paragraph("O bispo de cores opostas empata muitos finais."),
            Figure(caption=(Text(content="Figura 1: a estrutura tipica"),)),
            Diagram(
                fen=f"{OPPOSITE_BISHOPS} w - - 0 1",
                caption=(Text(content="Diagrama 7: as brancas jogam e empatam"),),
                stipulation="Brancas jogam e empatam",
            ),
            game,
        ),
    )
