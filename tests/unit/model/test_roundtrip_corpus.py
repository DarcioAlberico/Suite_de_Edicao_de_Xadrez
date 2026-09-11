"""The F1 acceptance gate: ten thousand synthetic nodes survive JSON intact.

SPEC 11.3 sets the bar at ">= 99 % dos nos preservados" for an export/import
round trip. The IR's own codec is held to a stricter bar, because it is the one
hop in the whole product that has no excuse to lose anything: **100 %**,
including every node id, every enum member and every float.

The corpus is generated, not handwritten. A handwritten fixture tests the node
types whoever wrote it remembered; a seeded generator that draws from the type
registry tests the ones nobody remembered, and a new node type is covered the
day it is added. The seed is fixed, so a failure here reproduces exactly.
"""

from __future__ import annotations

import json

import pytest
from generators import NodeFactory, all_node_types, construct_minimal

from caissa.core.model import (
    ChangeKind,
    Document,
    IRNode,
    dumps,
    is_ir_dataclass,
    iter_registered,
    loads,
    node_from_payload,
    node_to_payload,
    semantic_diff,
    tag_for_class,
    walk,
)
from caissa.core.model.serialize import (
    GENERATOR,
    PAYLOAD_KIND,
    TYPE_KEY,
    document_from_payload,
    document_to_payload,
)
from conftest import CORPUS_NODES, CORPUS_SEED

# --------------------------------------------------------------------------- #
# The ten-thousand-node gate
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def corpus() -> Document:
    """A reproducible document of at least :data:`CORPUS_NODES` nodes."""
    return NodeFactory(CORPUS_SEED).document(min_nodes=CORPUS_NODES)


def test_corpus_reaches_the_required_size(corpus):
    assert sum(1 for _ in walk(corpus)) >= CORPUS_NODES


def test_corpus_is_deterministic_from_its_seed():
    first = NodeFactory(CORPUS_SEED).document(min_nodes=500)
    second = NodeFactory(CORPUS_SEED).document(min_nodes=500)
    assert first == second, "the generator is not reproducible from its seed"


def test_corpus_round_trips_through_json_identically(corpus):
    restored = loads(dumps(corpus))
    assert restored == corpus, f"round trip lost data; reproduce with seed {CORPUS_SEED:#x}"


def test_corpus_round_trip_preserves_every_node_id(corpus):
    restored = loads(dumps(corpus))
    before = [node.id for _path, node in walk(corpus)]
    after = [node.id for _path, node in walk(restored)]
    assert after == before


def test_corpus_round_trip_preserves_every_path_and_type(corpus):
    restored = loads(dumps(corpus))
    before = [(str(path), node.node_type) for path, node in walk(corpus)]
    after = [(str(path), node.node_type) for path, node in walk(restored)]
    assert after == before


def test_corpus_round_trip_is_semantically_identical(corpus):
    """The fidelity instrument agrees with plain equality -- 100 %, not 99 %."""
    report = semantic_diff(corpus, loads(dumps(corpus)))
    assert report.is_identical, report.summary()
    assert report.fidelity == pytest.approx(1.0)
    assert report.strategy == "id"


def test_corpus_round_trip_is_stable_under_repetition(corpus):
    """Serialising twice produces byte-identical text: no dict-order jitter."""
    once = dumps(corpus)
    twice = dumps(loads(once))
    assert twice == once


def test_corpus_round_trips_with_defaults_written_out(corpus):
    """``omit_defaults=False`` is the debugging shape and must be lossless too."""
    verbose = dumps(corpus, omit_defaults=False)
    assert len(verbose) > len(dumps(corpus))
    assert loads(verbose) == corpus


def test_corpus_json_is_valid_utf8_json(corpus):
    payload = json.loads(dumps(corpus))
    assert payload["kind"] == PAYLOAD_KIND
    assert payload["generator"] == GENERATOR
    assert payload["document"][TYPE_KEY] == "document"


@pytest.mark.parametrize("seed", [1, 7, 99, 20260907, 0xDECAF])
def test_other_seeds_round_trip_too(seed):
    """One lucky seed proves nothing; five independent corpora prove a bit more."""
    document = NodeFactory(seed).document(min_nodes=400)
    assert loads(dumps(document)) == document, f"seed {seed} failed"


# --------------------------------------------------------------------------- #
# Every registered type, not just the ones the generator happened to draw
# --------------------------------------------------------------------------- #


def test_every_registered_node_type_appears_in_the_corpus(corpus):
    """The corpus is only a gate if it actually visits every node type."""
    seen = {node.node_type for _path, node in walk(corpus)}
    declared = {
        tag for tag, cls in iter_registered() if isinstance(cls, type) and issubclass(cls, IRNode)
    }
    assert declared - seen == set(), "node types never generated"


@pytest.mark.parametrize(
    ("tag", "cls"),
    iter_registered(),
    ids=[tag for tag, _cls in iter_registered()],
)
def test_every_registered_type_constructs_and_round_trips(tag, cls):
    """Reflection-driven, so a type added tomorrow is covered tomorrow."""
    instance = construct_minimal(cls)
    payload = node_to_payload(instance)
    assert payload[TYPE_KEY] == tag
    assert node_from_payload(payload, cls) == instance


@pytest.mark.parametrize(
    ("tag", "cls"),
    iter_registered(),
    ids=[tag for tag, _cls in iter_registered()],
)
def test_every_registered_type_round_trips_with_defaults_written(tag, cls):
    instance = construct_minimal(cls)
    payload = node_to_payload(instance, omit_defaults=False)
    assert node_from_payload(payload, cls) == instance
    assert set(payload) - {TYPE_KEY} != set(), f"{tag} wrote no fields at all"


def test_registry_is_a_bijection():
    pairs = iter_registered()
    tags = [tag for tag, _cls in pairs]
    classes = [cls for _tag, cls in pairs]
    assert len(set(tags)) == len(tags), "duplicate tag"
    assert len(set(classes)) == len(classes), "one class under two tags"
    for tag, cls in pairs:
        assert tag_for_class(cls) == tag
        assert is_ir_dataclass(construct_minimal(cls))


def test_every_node_class_carries_identity_and_provenance():
    """SPEC 5: identity per node is what makes fidelity measurable at all."""
    for cls in all_node_types():
        instance = construct_minimal(cls)
        assert instance.id is not None
        assert instance.provenance is None
        assert instance.node_type == tag_for_class(cls)


def test_node_ids_are_unique_across_the_corpus(corpus):
    ids = [node.id for _path, node in walk(corpus)]
    assert len(set(ids)) == len(ids), "the generator minted a duplicate id"


# --------------------------------------------------------------------------- #
# The envelope
# --------------------------------------------------------------------------- #


def test_document_payload_carries_the_versioned_envelope(corpus):
    payload = document_to_payload(corpus)
    assert set(payload) == {"schema_version", "kind", "generator", "document"}
    restored, applied = document_from_payload(payload)
    assert restored == corpus
    assert applied == ()


def test_round_trip_detects_a_deliberate_wound(corpus):
    """A round-trip test that cannot fail is not a test. Break one node."""
    restored = loads(dumps(corpus))
    victim_path, victim = next(
        (path, node) for path, node in walk(restored) if node.node_type == "text"
    )
    assert victim.content != "", victim_path
    damaged = dumps(corpus).replace(f'"{victim.content}"', '"conteudo trocado"', 1)
    report = semantic_diff(corpus, loads(damaged))
    assert not report.is_identical
    assert report.of_kind(ChangeKind.CHANGED)
