"""``semantic_diff()`` -- the instrument SPEC 11.3's fidelity gate is measured on.

"At least 99 % of nodes preserved" is only a number if something counts. Comparing
files is worthless: two identical documents written by two exporters differ in
every byte. What matters is whether the *tree* survived, and that is what this
module measures -- node by node, field by field, with a path for each finding.

Five change classes, each tested here with the path it must report:

``ADDED`` / ``REMOVED``
    a node that exists on one side only;
``CHANGED``
    a paired node whose scalar field differs, named field by field;
``MOVED``
    the same node (by id) at a different path;
``RETYPED``
    the same id carrying a different node type -- the failure that looks like a
    successful round trip until you read the output.
"""

from __future__ import annotations

import dataclasses

import pytest

from caissa.core.chess.fen import STARTING_FEN
from caissa.core.model import (
    ULID,
    ChangeKind,
    Diagram,
    Document,
    DocumentMetadata,
    Heading,
    Paragraph,
    Provenance,
    RunProps,
    SourceKind,
    Strong,
    Text,
    dumps,
    loads,
    semantic_diff,
    walk,
)


def ulid(n: int) -> ULID:
    """A deterministic id, so a diff is reproducible."""
    return ULID.from_parts(1_700_000_000_000 + n, n)


def base_document() -> Document:
    """Three paragraphs with fixed ids, the substrate for every case below."""
    return Document(
        id=ulid(1),
        metadata=DocumentMetadata(title="Livro", language="pt-BR"),
        body=(
            Paragraph(id=ulid(2), content=(Text(id=ulid(3), content="primeiro"),)),
            Paragraph(id=ulid(4), content=(Text(id=ulid(5), content="segundo"),)),
            Paragraph(id=ulid(6), content=(Text(id=ulid(7), content="terceiro"),)),
        ),
    )


def kinds(report) -> set[ChangeKind]:
    """The set of change kinds a report contains."""
    return {entry.kind for entry in report.entries}


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


def test_a_document_is_identical_to_itself():
    document = base_document()
    report = semantic_diff(document, document)
    assert report.is_identical
    assert report.entries == ()
    assert report.fidelity == 1.0
    assert report.left_node_count == report.right_node_count == report.matched_node_count


def test_a_document_is_identical_to_its_round_trip():
    document = base_document()
    assert semantic_diff(document, loads(dumps(document))).is_identical


def test_the_report_summarises_itself_readably():
    document = base_document()
    report = semantic_diff(document, document)
    assert "identic" in report.summary().lower() or report.summary()
    assert str(report)


# --------------------------------------------------------------------------- #
# CHANGED
# --------------------------------------------------------------------------- #


def test_a_changed_scalar_is_reported_with_its_field_and_path():
    left = base_document()
    right = dataclasses.replace(
        left,
        body=(
            left.body[0],
            dataclasses.replace(
                left.body[1],
                content=(dataclasses.replace(left.body[1].content[0], content="alterado"),),
            ),
            left.body[2],
        ),
    )
    report = semantic_diff(left, right)
    changed = report.of_kind(ChangeKind.CHANGED)
    assert len(changed) == 1
    entry = changed[0]
    assert entry.field == "content"
    assert entry.path == "$.body[1].content[0]"
    assert entry.before == "'segundo'"
    assert entry.after == "'alterado'"
    assert entry.node_type == "text"
    assert "segundo" in str(entry)


def test_a_changed_property_object_is_reported_as_one_field():
    left = base_document()
    right = dataclasses.replace(
        left,
        body=(
            dataclasses.replace(
                left.body[0],
                content=(
                    dataclasses.replace(left.body[0].content[0], props=RunProps(italic=True)),
                ),
            ),
            *left.body[1:],
        ),
    )
    changed = semantic_diff(left, right).of_kind(ChangeKind.CHANGED)
    assert [entry.field for entry in changed] == ["props"]


def test_several_changed_fields_on_one_node_are_reported_separately():
    left = Document(id=ulid(1), body=(Heading(id=ulid(2), level=1, anchor="a"),))
    right = Document(id=ulid(1), body=(Heading(id=ulid(2), level=3, anchor="b"),))
    changed = semantic_diff(left, right).of_kind(ChangeKind.CHANGED)
    assert {entry.field for entry in changed} == {"level", "anchor"}


def test_a_differing_id_is_a_change_unless_ignored():
    left = Document(id=ulid(1), body=(Paragraph(id=ulid(2)),))
    right = Document(id=ulid(1), body=(Paragraph(id=ulid(99)),))
    assert any(entry.field == "id" for entry in semantic_diff(left, right).entries)
    assert semantic_diff(left, right, ignore_ids=True, match="position").is_identical


def test_provenance_can_be_ignored_when_the_format_cannot_carry_it():
    left = Document(id=ulid(1), body=(Paragraph(id=ulid(2)),))
    right = Document(
        id=ulid(1),
        body=(Paragraph(id=ulid(2), provenance=Provenance(kind=SourceKind.OCR)),),
    )
    assert not semantic_diff(left, right).is_identical
    assert semantic_diff(left, right, ignore_provenance=True).is_identical


# --------------------------------------------------------------------------- #
# ADDED and REMOVED
# --------------------------------------------------------------------------- #


def test_an_added_node_is_reported_with_the_path_it_appears_at():
    left = base_document()
    extra = Paragraph(id=ulid(8), content=(Text(id=ulid(9), content="quarto"),))
    right = dataclasses.replace(left, body=(*left.body, extra))
    report = semantic_diff(left, right)
    added = report.of_kind(ChangeKind.ADDED)
    assert {entry.path for entry in added} == {"$.body[3]", "$.body[3].content[0]"}
    assert {entry.node_id for entry in added} == {ulid(8), ulid(9)}
    assert report.right_node_count == report.left_node_count + 2


def test_a_removed_node_is_reported_with_the_path_it_used_to_be_at():
    left = base_document()
    right = dataclasses.replace(left, body=left.body[:2])
    report = semantic_diff(left, right)
    removed = report.of_kind(ChangeKind.REMOVED)
    assert {entry.path for entry in removed} == {"$.body[2]", "$.body[2].content[0]"}
    assert all(entry.before for entry in removed)


def test_fidelity_falls_when_nodes_are_lost():
    left = base_document()
    right = dataclasses.replace(left, body=left.body[:2])
    report = semantic_diff(left, right)
    assert report.left_node_count == 7
    assert report.matched_node_count == 5, "two nodes gone"
    assert report.fidelity == pytest.approx(4 / 7), "the document node changed shape too"
    assert report.fidelity < 0.99, "this is what failing SPEC 11.3 looks like"


def test_a_node_that_came_back_altered_does_not_count_as_preserved():
    """Fidelity is about survival, not attendance: a changed node did not survive."""
    left = base_document()
    right = dataclasses.replace(
        left,
        body=(
            dataclasses.replace(
                left.body[0],
                content=(dataclasses.replace(left.body[0].content[0], content="outro"),),
            ),
            *left.body[1:],
        ),
    )
    report = semantic_diff(left, right)
    assert report.matched_node_count == 7, "every node was paired"
    assert report.fidelity == pytest.approx(6 / 7), "but one of them is not what went in"
    assert not report.is_identical


def test_fidelity_is_one_only_when_nothing_moved_and_nothing_changed():
    document = base_document()
    reordered = dataclasses.replace(
        document,
        body=(document.body[1], document.body[0], document.body[2]),
    )
    assert semantic_diff(document, document).fidelity == 1.0
    assert semantic_diff(document, reordered).fidelity == 1.0, "a move preserves the node"


# --------------------------------------------------------------------------- #
# MOVED
# --------------------------------------------------------------------------- #


def test_a_node_that_moved_is_matched_by_id_and_reported_as_moved():
    left = base_document()
    right = dataclasses.replace(left, body=(left.body[2], left.body[0], left.body[1]))
    report = semantic_diff(left, right)
    assert report.strategy == "id"
    moved = report.of_kind(ChangeKind.MOVED)
    assert moved, "reordering with stable ids must read as MOVED, not add+remove"
    assert not report.of_kind(ChangeKind.ADDED)
    assert not report.of_kind(ChangeKind.REMOVED)
    entry = next(item for item in moved if item.node_id == ulid(6))
    assert entry.other_path == "$.body[2]"
    assert entry.path == "$.body[0]"
    assert "->" in str(entry)


def test_a_move_is_not_a_change():
    left = base_document()
    right = dataclasses.replace(left, body=(left.body[1], left.body[0], left.body[2]))
    report = semantic_diff(left, right)
    assert not report.of_kind(ChangeKind.CHANGED)
    assert report.fidelity == 1.0


# --------------------------------------------------------------------------- #
# RETYPED
# --------------------------------------------------------------------------- #


def test_the_same_id_carrying_a_different_type_is_reported_as_retyped():
    left = Document(id=ulid(1), body=(Paragraph(id=ulid(2)),))
    right = Document(id=ulid(1), body=(Heading(id=ulid(2)),))
    report = semantic_diff(left, right)
    entry = report.of_kind(ChangeKind.RETYPED)[0]
    assert entry.before == "paragraph"
    assert entry.after == "heading"
    assert entry.path == "$.body[0]"


# --------------------------------------------------------------------------- #
# Pairing strategy
# --------------------------------------------------------------------------- #


def test_identity_matching_is_chosen_when_the_ids_overlap():
    document = base_document()
    assert semantic_diff(document, document).strategy == "id"


def test_position_matching_is_chosen_when_a_foreign_importer_minted_new_ids():
    left = base_document()
    right = Document(
        metadata=left.metadata,
        body=tuple(
            Paragraph(content=(Text(content=block.content[0].content),)) for block in left.body
        ),
    )
    report = semantic_diff(left, right, ignore_ids=True)
    assert report.strategy == "position"
    assert report.is_identical, "structure survived even though identity did not"


def test_position_matching_can_be_forced():
    document = base_document()
    assert semantic_diff(document, document, match="position").strategy == "position"


def test_identity_matching_falls_back_to_position_for_whatever_it_cannot_pair():
    """A partly-preserved set of ids still yields a useful diff, not a wall of adds."""
    left = base_document()
    right = Document(body=(Paragraph(),))
    report = semantic_diff(left, right, match="id")
    assert report.strategy == "id"
    assert report.matched_node_count == 2, "$ and $.body[0] paired by path"
    assert report.of_kind(ChangeKind.REMOVED), "the rest of the left document is gone"


def test_position_matching_reads_a_reorder_as_content_changes():
    """The honest consequence of losing identity, stated so nobody is surprised."""
    left = base_document()
    right = dataclasses.replace(left, body=(left.body[2], left.body[0], left.body[1]))
    report = semantic_diff(left, right, match="position", ignore_ids=True)
    assert report.of_kind(ChangeKind.CHANGED)
    assert not report.of_kind(ChangeKind.MOVED)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #


def test_entries_are_sorted_by_path_so_a_report_reads_in_document_order():
    left = base_document()
    right = dataclasses.replace(left, body=(left.body[0],))
    paths = [entry.path for entry in semantic_diff(left, right).entries]
    assert paths == sorted(paths)


def test_of_kind_filters_without_losing_anything():
    left = base_document()
    right = dataclasses.replace(
        left,
        body=(
            dataclasses.replace(
                left.body[0],
                content=(dataclasses.replace(left.body[0].content[0], content="x"),),
            ),
        ),
    )
    report = semantic_diff(left, right)
    total = sum(len(report.of_kind(kind)) for kind in ChangeKind)
    assert total == len(report.entries)


def test_a_deep_change_inside_a_diagram_is_found():
    left = Document(id=ulid(1), body=(Diagram(id=ulid(2), fen=STARTING_FEN),))
    right = Document(
        id=ulid(1),
        body=(Diagram(id=ulid(2), fen="8/8/8/8/8/8/8/8 w - - 0 1"),),
    )
    entry = semantic_diff(left, right).of_kind(ChangeKind.CHANGED)[0]
    assert entry.field == "fen"


def test_a_change_nested_three_wrappers_deep_is_found_with_a_full_path():
    left = Document(
        id=ulid(1),
        body=(
            Paragraph(
                id=ulid(2),
                content=(Strong(id=ulid(3), content=(Text(id=ulid(4), content="a"),)),),
            ),
        ),
    )
    right = Document(
        id=ulid(1),
        body=(
            Paragraph(
                id=ulid(2),
                content=(Strong(id=ulid(3), content=(Text(id=ulid(4), content="b"),)),),
            ),
        ),
    )
    entry = semantic_diff(left, right).of_kind(ChangeKind.CHANGED)[0]
    assert entry.path == "$.body[0].content[0].content[0]"


def test_node_counts_match_the_walk():
    document = base_document()
    report = semantic_diff(document, document)
    assert report.left_node_count == sum(1 for _ in walk(document))
