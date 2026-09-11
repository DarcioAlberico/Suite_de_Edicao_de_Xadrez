"""The decoding grammar: one declaration drives both the ask and the check.

``json_schema_for`` translates the ``FieldSpec`` map that
:func:`caissa.llm.guardrails.validate_schema` already enforces into the JSON
Schema Ollama compiles into a decoding grammar. The risk it introduces is
*drift*: a grammar that permits what the validator rejects, or forbids what it
requires, would show up as a mysterious rejection rate rather than as a bug.
These tests pin the two to each other.
"""

from __future__ import annotations

import json

from caissa.llm.guardrails import (
    FieldSpec,
    guarded_json_call,
    json_schema_for,
    validate_schema,
)
from caissa.llm.prompts import load_prompt
from caissa.llm.tasks import (
    _CAPTION_SCHEMA,
    _OCR_SCHEMA,
    _STIPULATION_SCHEMA,
    _TRANSLATION_SCHEMA,
    _VERIFY_SCHEMA,
)

from .conftest import FakeRuntime

ALL_SCHEMAS = (
    ("verify_diagram", _VERIFY_SCHEMA),
    ("extract_stipulation", _STIPULATION_SCHEMA),
    ("repair_ocr_region", _OCR_SCHEMA),
    ("caption_for_diagram", _CAPTION_SCHEMA),
    ("translate_notation_prose", _TRANSLATION_SCHEMA),
)


def test_every_task_schema_translates() -> None:
    """No task may carry a shape the grammar generator cannot express."""
    for name, schema in ALL_SCHEMAS:
        translated = json_schema_for(schema)
        assert translated["type"] == "object", name
        assert set(translated["properties"]) == set(schema), name
        assert json.dumps(translated), name


def test_required_fields_match_the_validator() -> None:
    """What the grammar demands is exactly what the validator demands."""
    for name, schema in ALL_SCHEMAS:
        translated = json_schema_for(schema)
        expected = {
            field for field, spec in schema.items() if spec.required and spec.default is None
        }
        assert set(translated["required"]) >= expected, name


def test_closed_vocabularies_reach_the_grammar() -> None:
    """The enum is what stops a model inventing a sixth verdict."""
    verify = json_schema_for(_VERIFY_SCHEMA)
    assert verify["properties"]["verdict"]["enum"] == [
        "consistent",
        "inconsistent",
        "uncertain",
    ]
    stipulation = json_schema_for(_STIPULATION_SCHEMA)
    assert "unknown" in stipulation["properties"]["kind"]["enum"]


def test_optional_fields_admit_null() -> None:
    """"No diagram number" must be sayable, or the model will invent one."""
    stipulation = json_schema_for(_STIPULATION_SCHEMA)
    assert "null" in stipulation["properties"]["diagram_number"]["type"]
    assert "null" in stipulation["properties"]["moves"]["type"]
    assert stipulation["properties"]["kind"]["type"] == "string"


def test_lists_declare_their_item_type() -> None:
    """A bare ``array`` would let the grammar emit numbers where squares go."""
    verify = json_schema_for(_VERIFY_SCHEMA)
    assert verify["properties"]["suspect_squares"]["items"] == {"type": "string"}


def test_anything_the_grammar_allows_the_validator_accepts() -> None:
    """A reply that satisfies the declared shape must survive validation."""
    payload = {
        "kind": "mate",
        "moves": 2,
        "side_to_move": "w",
        "diagram_number": None,
        "language": "pt",
        "confidence": 0.5,
    }
    cleaned = validate_schema(payload, _STIPULATION_SCHEMA)
    assert cleaned["kind"] == "mate"
    assert cleaned["diagram_number"] is None


def test_the_schema_is_actually_sent_by_default() -> None:
    """Default on: it is the difference between empty replies and answers."""
    runtime = FakeRuntime(['{"caption": "Final de rei e peao"}'])
    guarded_json_call(
        runtime,
        load_prompt("caption_for_diagram"),
        _CAPTION_SCHEMA,
        {
            "fen": "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
            "side": "brancas",
            "material": "1x Rei branco",
            "context": "(nenhum)",
            "language": "pt",
        },
        task="test",
    )
    assert runtime.requests[0].json_schema == json_schema_for(_CAPTION_SCHEMA)


def test_the_schema_can_be_turned_off_for_the_ab_measurement() -> None:
    """The benchmark measures the difference instead of asserting it."""
    runtime = FakeRuntime(['{"caption": "Final de rei e peao"}'])
    guarded_json_call(
        runtime,
        load_prompt("caption_for_diagram"),
        _CAPTION_SCHEMA,
        {
            "fen": "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
            "side": "brancas",
            "material": "1x Rei branco",
            "context": "(nenhum)",
            "language": "pt",
        },
        task="test",
        force_schema=False,
    )
    assert runtime.requests[0].json_schema is None


def test_thinking_stays_off_on_every_structured_call() -> None:
    """Gemma 4 spends the whole budget on reasoning tokens when it is on."""
    runtime = FakeRuntime(['{"caption": "x"}'])
    guarded_json_call(
        runtime,
        load_prompt("caption_for_diagram"),
        _CAPTION_SCHEMA,
        {
            "fen": "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
            "side": "brancas",
            "material": "1x Rei branco",
            "context": "(nenhum)",
            "language": "pt",
        },
        task="test",
    )
    assert runtime.requests[0].think is False


def test_a_grammar_is_a_help_and_not_a_guarantee() -> None:
    """Shape is constrained upstream; truth is still checked downstream."""
    # A reply that satisfies the grammar's *shape* but breaks the validator's
    # range still has to be rejected, or the grammar would have become the
    # only check.
    schema = {"confidence": FieldSpec(kind="float", minimum=0.0, maximum=1.0)}
    runtime = FakeRuntime(['{"confidence": 4.2}'])
    outcome = guarded_json_call(
        runtime,
        load_prompt("caption_for_diagram"),
        schema,
        {
            "fen": "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
            "side": "brancas",
            "material": "1x Rei branco",
            "context": "(nenhum)",
            "language": "pt",
        },
        task="test",
    )
    assert outcome.ok is False
    assert outcome.decision == "schema_violation"
