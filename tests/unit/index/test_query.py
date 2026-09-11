"""The unified query API: scoping, chess primitives, combination, pagination.

Each chess-aware primitive gets a known-answer fixture, because "it returned
something" is not a test of a chess query.  The IR document in ``conftest`` has
exactly one opposite-bishops diagram, exactly one game, exactly one ``??`` and
exactly one caption, so every count below is a fact about it.
"""

from __future__ import annotations

import pytest

from caissa.index import IrSource, Query, QueryError, SearchIndex, TextSource
from caissa.notation.regex_engine import MaterialSignature, MoveQuery, PositionPattern, Scope

from .conftest import OPPOSITE_BISHOPS


@pytest.fixture
def library(index, ir_document, book):
    """One IR book plus one plain-text book, indexed."""
    index.add(IrSource(document=ir_document, uri="mem://manual", title="Manual de Finais"))
    index.add(book, stratum="E7")
    return SearchIndex.wrap(index.connection)


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #


def test_plain_word_search(library):
    assert library.search(Query(text="bispo")).total >= 1


def test_notation_search_reaches_the_index(library):
    assert library.search(Query(text="O-O-O")).total == 1


def test_two_words_are_an_implicit_and(library):
    both = library.search(Query(text="bispo cores")).total
    assert both >= 1
    assert library.search(Query(text="bispo jabuticaba")).total == 0


def test_explicit_or(library):
    assert library.search(Query(text="jabuticaba OR bispo")).total >= 1


def test_quoted_phrase_requires_adjacency(library):
    assert library.search(Query(text='"cores opostas"')).total >= 1
    assert library.search(Query(text='"opostas cores"')).total == 0


def test_text_and_match_are_mutually_exclusive():
    with pytest.raises(QueryError):
        Query(text="a", match="b")


def test_bad_pagination_is_refused():
    with pytest.raises(QueryError):
        Query(limit=0)
    with pytest.raises(QueryError):
        Query(offset=-1)


# --------------------------------------------------------------------------- #
# Scope -- SPEC 9's "só legendas, só lances..."
# --------------------------------------------------------------------------- #


def test_caption_scope_finds_only_captions(library):
    page = library.search(Query(text="Diagrama", scope=Scope.CAPTIONS))
    assert page.total == 1
    assert page.hits[0].scope is Scope.CAPTIONS
    assert "Diagrama 7" in page.hits[0].text


def test_heading_scope_finds_only_headings(library):
    page = library.search(Query(text="finais", scope=Scope.HEADERS))
    assert page.total >= 1
    assert all(hit.scope is Scope.HEADERS for hit in page.hits)


def test_comment_scope_finds_only_comments(library):
    page = library.search(Query(text="zugzwang", scope=Scope.COMMENTS))
    assert page.total == 1
    assert page.hits[0].scope is Scope.COMMENTS


def test_mainline_and_variation_are_different_scopes(library):
    mainline = library.search(Query(text="e4", scope=Scope.MAINLINE))
    variations = library.search(Query(text="e5", scope=Scope.VARIATIONS))
    assert mainline.total == 1
    assert variations.total == 1
    assert mainline.hits[0].node_id != variations.hits[0].node_id


def test_scope_all_sees_everything(library):
    assert library.search(Query(text="zugzwang", scope=Scope.ALL)).total == 1
    assert library.search(Query(text="zugzwang", scope=Scope.CAPTIONS)).total == 0


# --------------------------------------------------------------------------- #
# Chess-aware primitives, each with a known answer
# --------------------------------------------------------------------------- #


def test_move_pattern_finds_a_knight_capture(index):
    """``N*xd5`` is every knight capture on d5, however it is disambiguated."""
    source = TextSource(
        uri="mem://lances",
        text=(
            "1.e4 c5 2.Nf3 d6 3.Nxd5 continua\n\n"
            "outra linha com Nbxd5 aqui\n\n"
            "e ainda N3xd5 nesta\n\n"
            "mas Bxd5 nao conta e Nxd4 tampouco\n"
        ),
    )
    index.add(source)
    reader = SearchIndex.wrap(index.connection)
    page = reader.search(Query(move="N*xd5", limit=100))
    assert page.total == 3
    assert all("xd5" in hit.text for hit in page.hits)


def test_move_pattern_ignores_the_check_mark(index):
    index.add(TextSource(uri="mem://x", text="a sequencia Qxh7+ decidiu"))
    reader = SearchIndex.wrap(index.connection)
    assert reader.search(Query(move="Qxh7")).total == 1


def test_annotation_query_finds_the_marked_move(library):
    """"Todos os lances marcados com ??" -- the IR game has exactly one."""
    page = library.search(Query(annotation="??"))
    assert page.total == 1
    assert "??" in page.hits[0].text


def test_material_signature_finds_opposite_bishops(library):
    """SPEC 9's own example: opposite-coloured bishops and at most six pawns."""
    page = library.search(
        Query(material=MaterialSignature(opposite_bishops=True, max_pawns=6), limit=100)
    )
    assert page.total == 1
    assert page.hits[0].scope is Scope.CAPTIONS


def test_material_signature_rejects_when_it_should(library):
    assert library.search(Query(material=MaterialSignature(opposite_bishops=True,
                                                           max_pawns=2))).total == 0
    assert library.search(Query(material="KQvKQ")).total == 0


def test_position_lookup_finds_the_diagram(library):
    page = library.search(Query(position=OPPOSITE_BISHOPS))
    assert page.total == 1
    assert page.hits[0].position_exact is True
    assert "Diagrama 7" in page.hits[0].text


def test_position_pattern_matches_a_wildcard_board(library):
    pattern = PositionPattern(placement="8/5pk1/6p1/3B4/8/2b5/5PPP/6K1")
    assert library.search(Query(position_pattern=pattern, limit=100)).total == 1


def test_eco_query(library):
    assert library.search(Query(eco="B9[0-9]")).total >= 1
    assert library.search(Query(eco="C")).total == 0


def test_player_query(library):
    assert library.search(Query(player="Kasparov")).total >= 1
    assert library.search(Query(player="Fischer")).total == 0


def test_year_range(library):
    assert library.search(Query(year_min=1980, year_max=1990)).total >= 1
    assert library.search(Query(year_min=1990)).total == 0


def test_stratum_restricts_to_a_corpus_stratum(library):
    assert library.search(Query(text="gambito", stratum="E7")).total >= 1
    assert library.search(Query(text="gambito", stratum="E1")).total == 0


def test_document_restriction(library):
    assert library.search(Query(text="bispo", documents=("mem://manual",))).total >= 1
    assert library.search(Query(text="bispo", documents=("mem://livro",))).total == 0


# --------------------------------------------------------------------------- #
# Combination -- the queries the SPEC actually asks for
# --------------------------------------------------------------------------- #


def test_text_and_position_together(library):
    """Text AND position in one query, which is the point of a single API."""
    both = Query(text="Diagrama", position=OPPOSITE_BISHOPS)
    assert library.search(both).total == 1

    contradictory = Query(text="jabuticaba", position=OPPOSITE_BISHOPS)
    assert library.search(contradictory).total == 0


def test_material_and_scope_and_document(library):
    page = library.search(
        Query(
            material=MaterialSignature(opposite_bishops=True),
            scope=Scope.CAPTIONS,
            documents=("mem://manual",),
            limit=100,
        )
    )
    assert page.total == 1


def test_move_query_object_with_extra_conditions(index):
    index.add(TextSource(uri="mem://q", text="1.e4 c5 2.Nf3 Nc6 3.Bb5 g6 4.Bxc6 dxc6"))
    reader = SearchIndex.wrap(index.connection)
    assert reader.search(Query(move=MoveQuery(pattern="B*xc6"))).total == 1
    assert reader.search(Query(move=MoveQuery(pattern="R*xc6"))).total == 0


# --------------------------------------------------------------------------- #
# Regex over the index
# --------------------------------------------------------------------------- #


def test_regex_with_a_named_group(library):
    page = library.search(Query(regex=r"Diagrama (?P<numero>\d+)", scope=Scope.CAPTIONS))
    assert page.total == 1
    assert page.hits[0].groups["numero"] == "7"


def test_regex_is_scoped(library):
    assert library.search(Query(regex=r"zugzwang", scope=Scope.COMMENTS)).total == 1
    assert library.search(Query(regex=r"zugzwang", scope=Scope.CAPTIONS)).total == 0


def test_regex_narrowed_by_text_first(library):
    """Text narrows, regex refines: the combination must not lose hits.

    ``library`` indexes two documents and *both* say ``Diagrama <numero>``: the
    IR manual's caption (``Diagrama 7``) and the plain-text book's paragraph
    (``Diagrama 12``).  Unscoped, the honest answer is therefore two -- and that
    is exactly what this test is for.  The scoped variants above pin which one
    is which; asserting one here would have asserted that the cheap FTS stage is
    allowed to drop a hit the regex stage would have kept, which is the bug the
    docstring says must not happen.
    """
    page = library.search(Query(text="Diagrama", regex=r"Diagrama \d+"))
    assert page.total == 2
    assert {hit.uri for hit in page.hits} == {"mem://manual", "mem://livro"}
    # And scoping still narrows it back down to the caption alone.
    scoped = library.search(Query(text="Diagrama", regex=r"Diagrama \d+", scope=Scope.CAPTIONS))
    assert scoped.total == 1
    assert scoped.hits[0].groups == {} or "Diagrama 7" in scoped.hits[0].text


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


def test_a_hit_can_be_jumped_to(library):
    page = library.search(Query(text="Diagrama", scope=Scope.CAPTIONS))
    hit = page.hits[0]
    assert hit.uri == "mem://manual"
    assert hit.node_ulid, "sem o id do no o resultado nao aponta para lugar nenhum"
    assert hit.node_id > 0
    assert hit.text
    assert hit.snippet


def test_pagination_walks_the_whole_answer(index):
    index.add(
        TextSource(
            uri="mem://muitos",
            text="\n\n".join(f"a posicao {n} com Nf3" for n in range(25)),
        )
    )
    reader = SearchIndex.wrap(index.connection)
    first = reader.search(Query(text="Nf3", limit=10, offset=0))
    second = reader.search(Query(text="Nf3", limit=10, offset=10))
    third = reader.search(Query(text="Nf3", limit=10, offset=20))

    assert first.total == 25
    assert (len(first.hits), len(second.hits), len(third.hits)) == (10, 10, 5)
    seen = {hit.node_id for hit in (*first.hits, *second.hits, *third.hits)}
    assert len(seen) == 25


def test_elapsed_is_reported(library):
    assert library.search(Query(text="bispo")).elapsed_ms >= 0.0


def test_an_invalid_fts_expression_is_named(library):
    with pytest.raises(QueryError):
        library.search(Query(match='"unterminated'))
