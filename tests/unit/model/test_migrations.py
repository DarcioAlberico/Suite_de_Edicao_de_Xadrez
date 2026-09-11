"""Schema versioning: a document written by an older build still opens.

A user's book outlives the build that wrote it. The registry's job is therefore
narrow and unforgiving:

* bring a payload of any past version up to the present, one step at a time;
* refuse a payload from the **future** rather than reading half of it, because
  silently dropping the half it does not understand corrupts the user's work;
* refuse a **gap** in the chain, naming the missing step.

Version 1 is the first published shape, so the shipped registry has no steps
yet. That is exactly why these tests build private registries: the machinery
must be proven working *before* the first real migration is written, not after
someone's book fails to open.
"""

from __future__ import annotations

import copy

import pytest

from caissa.core.model import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_REGISTRY,
    Document,
    DocumentMetadata,
    JsonObject,
    Migration,
    MigrationError,
    MigrationRegistry,
    Paragraph,
    Text,
    dumps,
    loads,
)
from caissa.core.model.serialize import (
    PAYLOAD_KIND,
    SerializationError,
    document_from_payload,
    document_to_payload,
)


def v1_payload() -> JsonObject:
    """A current-version payload, the substrate for the downgrade fixtures."""
    document = Document(
        metadata=DocumentMetadata(title="Livro antigo", language="pt-BR"),
        body=(Paragraph(content=(Text(content="uma frase"),)),),
    )
    return document_to_payload(document)


# --------------------------------------------------------------------------- #
# The shipped registry
# --------------------------------------------------------------------------- #


def test_the_current_version_is_declared_and_positive():
    assert CURRENT_SCHEMA_VERSION >= 1
    assert DEFAULT_REGISTRY.current_version == CURRENT_SCHEMA_VERSION


def test_a_current_document_needs_no_migration():
    payload = v1_payload()
    _document, applied = document_from_payload(payload)
    assert applied == ()


def test_a_document_from_the_future_is_refused_with_advice_to_upgrade():
    payload = v1_payload()
    payload["schema_version"] = CURRENT_SCHEMA_VERSION + 1
    with pytest.raises(MigrationError, match="Atualize o Caissa Studio"):
        document_from_payload(payload)


@pytest.mark.parametrize("version", [0, -1, -99])
def test_a_nonsensical_version_is_refused(version):
    payload = v1_payload()
    payload["schema_version"] = version
    with pytest.raises(MigrationError, match="schema_version invalida"):
        document_from_payload(payload)


@pytest.mark.parametrize("version", [None, "1", 1.0, True])
def test_a_non_integer_version_is_refused_before_any_migration_runs(version):
    payload = v1_payload()
    payload["schema_version"] = version
    with pytest.raises(SerializationError, match="schema_version"):
        document_from_payload(payload)


def test_a_payload_of_another_kind_is_refused():
    payload = v1_payload()
    payload["kind"] = "outra.coisa"
    with pytest.raises(SerializationError, match="nao e um documento"):
        document_from_payload(payload)


def test_a_payload_without_a_document_body_is_refused():
    payload = v1_payload()
    del payload["document"]
    with pytest.raises(SerializationError, match="sem a chave 'document'"):
        document_from_payload(payload)


def test_the_envelope_kind_is_written_so_a_stray_file_is_recognisable():
    assert v1_payload()["kind"] == PAYLOAD_KIND


# --------------------------------------------------------------------------- #
# A real one-step migration: v(N-1) -> v(N)
# --------------------------------------------------------------------------- #


def registry_with_one_step() -> tuple[MigrationRegistry, list[str]]:
    """A private registry whose single step renames a field, plus a call log."""
    registry = MigrationRegistry(current_version=2)
    log: list[str] = []

    @registry.register(1, description="v1 -> v2: 'titulo' passou a chamar-se 'title'")
    def _rename_title(payload: JsonObject) -> JsonObject:
        log.append("ran")
        updated = copy.deepcopy(payload)
        document = updated["document"]
        assert isinstance(document, dict)
        metadata = document.get("metadata")
        if isinstance(metadata, dict) and "titulo" in metadata:
            metadata["title"] = metadata.pop("titulo")
        updated["schema_version"] = 2
        return updated

    return registry, log


def old_shape_payload() -> JsonObject:
    """A payload as a hypothetical v1 build would have written it."""
    return {
        "schema_version": 1,
        "kind": PAYLOAD_KIND,
        "generator": "caissa-ir/1",
        "document": {
            "type": "document",
            "id": "01J0000000000000000000000A",
            "metadata": {"type": "document_metadata", "titulo": "Livro antigo"},
            "body": [
                {
                    "type": "paragraph",
                    "id": "01J0000000000000000000000B",
                    "content": [
                        {
                            "type": "text",
                            "id": "01J0000000000000000000000C",
                            "content": "uma frase",
                        }
                    ],
                }
            ],
        },
    }


def test_an_old_payload_migrates_and_then_decodes_correctly():
    registry, log = registry_with_one_step()
    document, applied = document_from_payload(old_shape_payload(), registry=registry)
    assert log == ["ran"], "the step actually ran"
    assert applied == ("v1 -> v2: 'titulo' passou a chamar-se 'title'",)
    assert document.metadata.title == "Livro antigo"
    assert document.body[0].content[0].content == "uma frase"
    assert str(document.id) == "01J0000000000000000000000A"


def test_the_old_payload_is_genuinely_unreadable_without_the_migration():
    """Otherwise the previous test proves nothing."""
    with pytest.raises(SerializationError, match="campos desconhecidos"):
        document_from_payload(old_shape_payload(), registry=MigrationRegistry(1))


def test_migration_does_not_mutate_the_caller_payload():
    registry, _log = registry_with_one_step()
    payload = old_shape_payload()
    before = copy.deepcopy(payload)
    document_from_payload(payload, registry=registry)
    assert payload == before


def test_a_payload_already_at_the_target_version_skips_the_step():
    registry, log = registry_with_one_step()
    payload = old_shape_payload()
    payload["schema_version"] = 2
    payload["document"]["metadata"] = {"type": "document_metadata", "title": "Ja novo"}
    document, applied = document_from_payload(payload, registry=registry)
    assert applied == ()
    assert log == []
    assert document.metadata.title == "Ja novo"


# --------------------------------------------------------------------------- #
# Chaining several steps
# --------------------------------------------------------------------------- #


def test_three_steps_chain_in_order():
    registry = MigrationRegistry(current_version=4)
    order: list[int] = []

    for version in (1, 2, 3):

        def step(payload: JsonObject, version: int = version) -> JsonObject:
            order.append(version)
            updated = dict(payload)
            updated["schema_version"] = version + 1
            return updated

        registry.add(
            Migration(
                from_version=version,
                to_version=version + 1,
                upgrade=step,
                description=f"passo {version}",
            )
        )

    payload, applied = registry.migrate({"schema_version": 1}, 1)
    assert order == [1, 2, 3]
    assert applied == ("passo 1", "passo 2", "passo 3")
    assert payload["schema_version"] == 4


def test_a_plan_starting_midway_runs_only_the_remaining_steps():
    registry = MigrationRegistry(current_version=4)
    for version in (1, 2, 3):
        registry.add(
            Migration(from_version=version, to_version=version + 1, upgrade=dict, description="")
        )
    assert [step.from_version for step in registry.plan(3)] == [3]
    assert registry.plan(4) == ()


def test_steps_are_reported_in_order_regardless_of_registration_order():
    registry = MigrationRegistry(current_version=4)
    for version in (3, 1, 2):
        registry.add(
            Migration(from_version=version, to_version=version + 1, upgrade=dict, description="")
        )
    assert [step.from_version for step in registry.steps] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #


def test_a_gap_in_the_chain_names_the_missing_step():
    registry = MigrationRegistry(current_version=4)
    registry.add(Migration(from_version=1, to_version=2, upgrade=dict))
    registry.add(Migration(from_version=3, to_version=4, upgrade=dict))
    with pytest.raises(MigrationError, match="falta migracao da versao 2 para 3"):
        registry.plan(1)


def test_a_step_that_skips_a_version_is_refused_at_registration():
    registry = MigrationRegistry(current_version=5)
    with pytest.raises(MigrationError, match="exatamente uma versao"):
        registry.add(Migration(from_version=1, to_version=3, upgrade=dict))


def test_a_step_past_the_current_version_is_refused():
    registry = MigrationRegistry(current_version=2)
    with pytest.raises(MigrationError, match="ultrapassa a versao corrente"):
        registry.add(Migration(from_version=2, to_version=3, upgrade=dict))


def test_two_steps_from_the_same_version_are_refused():
    registry = MigrationRegistry(current_version=3)
    registry.add(Migration(from_version=1, to_version=2, upgrade=dict))
    with pytest.raises(MigrationError, match="ja existe migracao"):
        registry.add(Migration(from_version=1, to_version=2, upgrade=dict))


def test_a_step_that_raises_is_reported_with_the_versions_named():
    registry = MigrationRegistry(current_version=2)

    def explode(_payload: JsonObject) -> JsonObject:
        raise RuntimeError("o formato antigo estava corrompido")

    registry.add(Migration(from_version=1, to_version=2, upgrade=explode))
    with pytest.raises(MigrationError, match="falha ao migrar da versao 1 para 2") as excinfo:
        registry.migrate({"schema_version": 1}, 1)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_a_step_falls_back_to_a_generated_label_when_it_has_no_description():
    registry = MigrationRegistry(current_version=2)
    registry.add(Migration(from_version=1, to_version=2, upgrade=lambda payload: payload))
    _payload, applied = registry.migrate({"schema_version": 1}, 1)
    assert applied == ("v1 -> v2",)


# --------------------------------------------------------------------------- #
# Round trip through the public API
# --------------------------------------------------------------------------- #


def test_loads_accepts_a_private_registry():
    registry, _log = registry_with_one_step()
    import json

    document = loads(json.dumps(old_shape_payload()), registry=registry)
    assert document.metadata.title == "Livro antigo"


def test_dumps_always_writes_the_current_version():
    document = Document(metadata=DocumentMetadata(title="x"))
    import json

    assert json.loads(dumps(document))["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loads(dumps(document)) == document
