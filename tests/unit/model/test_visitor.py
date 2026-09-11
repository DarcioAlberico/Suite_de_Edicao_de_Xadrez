"""Traversal and rewriting -- the two operations everything else is built on.

``walk`` feeds the validator and the differ, so a node it misses is a node
nothing checks. ``Transformer`` is how "change the notation language of the whole
book" is one edit rather than N, and because every node is frozen it must rebuild
only the spine from the changed node up to the root -- untouched subtrees are
shared. That structural-sharing claim is tested here by identity (``is``), not
equality, because sharing is the whole point: a five-hundred-page book must not
be copied to edit one paragraph.
"""

from __future__ import annotations

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.model import (
    Diagram,
    Document,
    DocumentMetadata,
    Emphasis,
    Figure,
    GameScore,
    Heading,
    Move,
    MoveNode,
    NodePath,
    Paragraph,
    PathStep,
    Strong,
    Text,
    Transformer,
    TransformError,
    Visitor,
    find,
    walk,
)
from caissa.core.model.reflect import (
    allows_none,
    child_nodes,
    field_defaults,
    field_types,
    is_node_field,
    union_members,
)


@pytest.fixture
def document() -> Document:
    """A small but structurally varied tree."""
    return Document(
        metadata=DocumentMetadata(title="Livro"),
        body=(
            Heading(level=1, content=(Text(content="Capitulo"),)),
            Paragraph(
                content=(
                    Text(content="antes "),
                    Strong(content=(Emphasis(content=(Text(content="dentro"),)),)),
                    Move(san="Nf3", language="en"),
                ),
            ),
            Figure(
                content=(Diagram(fen=STARTING_FEN),),
                caption=(Text(content="Posicao inicial"),),
            ),
            GameScore(children=(MoveNode(san="e4", children=(MoveNode(san="e5"),)),)),
        ),
    )


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #


def test_the_root_path_is_a_dollar_sign():
    assert str(NodePath()) == "$"
    assert NodePath().depth == 0


def test_a_path_renders_as_a_dotted_expression():
    path = NodePath().child("body", 3).child("content", 0).child("props")
    assert str(path) == "$.body[3].content[0].props"
    assert path.depth == 3


def test_a_step_renders_on_its_own():
    assert str(PathStep(field="body", index=2)) == "body[2]"
    assert str(PathStep(field="metadata")) == "metadata"


def test_extending_a_path_leaves_the_original_alone():
    base = NodePath().child("body", 0)
    extended = base.child("content", 1)
    assert str(base) == "$.body[0]"
    assert str(extended) == "$.body[0].content[1]"


# --------------------------------------------------------------------------- #
# walk
# --------------------------------------------------------------------------- #


def test_walk_yields_the_root_first(document):
    first_path, first_node = next(iter(walk(document)))
    assert first_node is document
    assert str(first_path) == "$"


def test_walk_is_pre_order_and_in_document_order(document):
    paths = [str(path) for path, _node in walk(document)]
    assert paths[:4] == ["$", "$.body[0]", "$.body[0].content[0]", "$.body[1]"]
    assert paths == sorted(set(paths), key=paths.index), "no path repeats"


def test_walk_reaches_every_nesting_level(document):
    paths = {str(path) for path, _node in walk(document)}
    assert "$.body[1].content[1].content[0].content[0]" in paths, "three wrappers deep"
    assert "$.body[2].content[0]" in paths, "a diagram inside a figure"
    assert "$.body[3].children[0].children[0]" in paths, "a move inside a variation"


def test_walk_can_start_from_a_subtree_with_an_offset_path(document):
    subtree = document.body[1]
    base = NodePath().child("body", 1)
    paths = [str(path) for path, _node in walk(subtree, path=base)]
    assert paths[0] == "$.body[1]"
    assert paths[1] == "$.body[1].content[0]"


def test_walk_yields_a_leaf_exactly_once(document):
    nodes = [node for _path, node in walk(document)]
    assert len(nodes) == len({id(node) for node in nodes})


def test_find_selects_one_type(document):
    found = list(find(document, "text"))
    assert len(found) == 4
    assert all(node.node_type == "text" for _path, node in found)
    assert list(find(document, "callout")) == []


# --------------------------------------------------------------------------- #
# Visitor
# --------------------------------------------------------------------------- #


def test_a_visitor_dispatches_by_tag_and_recurses_otherwise(document):
    class Counter(Visitor):
        def __init__(self) -> None:
            self.texts: list[str] = []
            self.moves = 0

        def visit_text(self, node, path):
            self.texts.append(node.content)

        def visit_move(self, node, path):
            self.moves += 1

    counter = Counter()
    counter.run(document)
    assert counter.texts == ["Capitulo", "antes ", "dentro", "Posicao inicial"]
    assert counter.moves == 1


def test_a_handler_that_does_not_recurse_prunes_the_subtree(document):
    class StopAtGames(Visitor):
        def __init__(self) -> None:
            self.moves = 0

        def visit_game_score(self, node, path):
            return  # deliberately not calling generic_visit

        def visit_move_node(self, node, path):
            self.moves += 1

    visitor = StopAtGames()
    visitor.run(document)
    assert visitor.moves == 0, "the game subtree was pruned"


def test_a_visitor_sees_the_path_of_each_node(document):
    seen: list[str] = []

    class Recorder(Visitor):
        def visit_text(self, node, path):
            seen.append(str(path))

    Recorder().run(document)
    assert "$.body[1].content[1].content[0].content[0]" in seen


# --------------------------------------------------------------------------- #
# Transformer -- replace, splice, delete
# --------------------------------------------------------------------------- #


def test_a_transformer_replaces_a_node_in_place(document):
    class Shout(Transformer):
        def visit_text(self, node, path):
            return Text(id=node.id, content=node.content.upper(), props=node.props)

    result = Shout().transform(document)
    assert [node.content for _path, node in find(result, "text")] == [
        "CAPITULO",
        "ANTES ",
        "DENTRO",
        "POSICAO INICIAL",
    ]


def test_the_notation_language_of_a_whole_book_changes_in_one_pass(document):
    """ADR-0002's headline claim, exercised."""

    class Translate(Transformer):
        def visit_move(self, node, path):
            return Move(
                id=node.id,
                san=node.san,
                ply=node.ply,
                language="pt",
                render=node.render,
            )

    result = Translate().transform(document)
    moves = [node for _path, node in find(result, "move")]
    assert [move.language for move in moves] == ["pt"]
    assert [move.san for move in moves] == ["Nf3"], "the canonical SAN never changes"


def test_an_untouched_subtree_is_shared_not_copied(document):
    """Structural sharing: editing one paragraph must not copy the book."""

    class TouchFirstHeading(Transformer):
        def visit_heading(self, node, path):
            return Heading(id=node.id, level=2, content=node.content)

    result = TouchFirstHeading().transform(document)
    assert result is not document, "the spine was rebuilt"
    assert result.body[0] is not document.body[0], "the changed node is new"
    assert result.body[1] is document.body[1], "an untouched sibling is the same object"
    assert result.body[3] is document.body[3]
    assert result.metadata is document.metadata


def test_a_transformer_that_changes_nothing_returns_the_same_object(document):
    class Nothing(Transformer):
        pass

    assert Nothing().transform(document) is document


def test_a_handler_returning_a_tuple_splices_into_the_sequence(document):
    class Split(Transformer):
        def visit_move(self, node, path):
            return (Text(content="["), node, Text(content="]"))

    result = Split().transform(document)
    paragraph = result.body[1]
    assert len(paragraph.content) == len(document.body[1].content) + 2
    assert paragraph.content[-1].content == "]"


def test_a_handler_returning_none_deletes_from_a_sequence(document):
    class DropMoves(Transformer):
        def visit_move(self, node, path):
            return None

    result = DropMoves().transform(document)
    assert list(find(result, "move")) == []
    assert len(result.body[1].content) == len(document.body[1].content) - 1


def test_an_optional_single_valued_child_may_be_deleted():
    diagram = Diagram(fen=STARTING_FEN, solution=GameScore(children=(MoveNode(san="e4"),)))
    document = Document(body=(diagram,))

    class DropSolutions(Transformer):
        def visit_game_score(self, node, path):
            return None

    result = DropSolutions().transform(document)
    assert result.body[0].solution is None


def test_value_objects_are_not_nodes_and_are_never_visited():
    """``DocumentMetadata`` is a property *of* a node, not a node: no handler fires."""
    document = Document(metadata=DocumentMetadata(title="x"))
    fired = []

    class TryMetadata(Transformer):
        def visit_document_metadata(self, node, path):  # pragma: no cover - must not run
            fired.append(node)

    assert TryMetadata().transform(document) is document
    assert fired == []


def test_deleting_a_required_single_valued_child_is_refused():
    """Guard for a node shape the vocabulary does not yet have.

    Every single-valued node field in the IR today is optional
    (``Diagram.solution`` is the only one at all), so this branch is reached
    directly rather than through a document -- registering a throwaway node type
    would pollute the global tag registry the completeness tests read.
    """

    class DropEverything(Transformer):
        def visit_game_score(self, node, path):
            return None

    with pytest.raises(TransformError, match="nao aceita remocao"):
        DropEverything()._single(
            GameScore(),
            NodePath().child("solution"),
            "solution",
            GameScore,
        )


def test_returning_several_nodes_for_a_single_valued_field_is_refused():
    diagram = Diagram(fen=STARTING_FEN, solution=GameScore())
    document = Document(body=(diagram,))

    class DoubleSolution(Transformer):
        def visit_game_score(self, node, path):
            return (node, node)

    with pytest.raises(TransformError, match="guarda um no so"):
        DoubleSolution().transform(document)


def test_returning_exactly_one_node_for_a_single_valued_field_is_fine():
    diagram = Diagram(fen=STARTING_FEN, solution=GameScore(title="antes"))
    document = Document(body=(diagram,))

    class Rename(Transformer):
        def visit_game_score(self, node, path):
            return [GameScore(id=node.id, title="depois")]

    assert Rename().transform(document).body[0].solution.title == "depois"


def test_deleting_the_root_is_refused(document):
    class DropEverything(Transformer):
        def visit_document(self, node, path):
            return None

    with pytest.raises(TransformError, match="raiz do documento"):
        DropEverything().transform(document)


def test_retyping_the_root_is_refused(document):
    class Retype(Transformer):
        def visit_document(self, node, path):
            return Paragraph()

    with pytest.raises(TransformError, match="transformacao da raiz"):
        Retype().transform(document)


def test_a_transformer_reaches_arbitrarily_deep(document):
    class Renumber(Transformer):
        def visit_move_node(self, node, path):
            return self.generic_visit(node, path).__class__(
                id=node.id,
                san=node.san,
                ply=node.ply + 100,
                children=self.generic_visit(node, path).children,
            )

    result = Renumber().transform(document)
    plies = [node.ply for _path, node in find(result, "move_node")]
    assert all(ply >= 100 for ply in plies)
    assert len(plies) == 2


# --------------------------------------------------------------------------- #
# Reflection, the layer underneath
# --------------------------------------------------------------------------- #


def test_field_types_resolves_forward_references():
    types = field_types(Paragraph)
    assert set(types) == set(Paragraph.__dataclass_fields__)
    assert types["content"] is not None


def test_field_types_are_cached_by_class():
    assert field_types(Paragraph) is field_types(Paragraph)


def test_field_types_refuses_a_non_dataclass():
    with pytest.raises(TypeError, match="nao e uma dataclass"):
        field_types(int)


def test_identity_factories_are_never_treated_as_omissible_defaults():
    """``id`` is minted fresh each call, so it can never be dropped as a default."""
    assert "id" not in field_defaults(Paragraph)
    assert field_defaults(Paragraph)["content"] == ()


def test_value_object_factories_do_count_as_defaults():
    from caissa.core.model import RunProps

    assert field_defaults(Text)["props"] == RunProps()


def test_union_members_handles_both_spellings():
    assert union_members(str | None) == (str, type(None))
    assert union_members(int) == ()


def test_allows_none_reads_optionality():
    assert allows_none(str | None)
    assert allows_none(None)
    assert not allows_none(str)


def test_is_node_field_recognises_nodes_and_node_tuples():
    assert is_node_field(Text(content="x"))
    assert is_node_field((Text(content="x"),))
    assert not is_node_field(())
    assert not is_node_field(("nao e um no",))
    assert not is_node_field("texto")


def test_child_nodes_reports_field_and_index(document):
    children = child_nodes(document.body[1])
    assert [(name, index) for name, index, _node in children] == [
        ("content", 0),
        ("content", 1),
        ("content", 2),
    ]


def test_child_nodes_reports_a_single_valued_field_with_no_index():
    diagram = Diagram(fen=STARTING_FEN, solution=GameScore())
    assert ("solution", None) in [(name, index) for name, index, _node in child_nodes(diagram)]


def test_child_nodes_of_a_leaf_is_empty():
    assert child_nodes(Text(content="x")) == ()
