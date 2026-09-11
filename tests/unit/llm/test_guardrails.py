"""Guardrails: a hallucination must cost nothing but a log line.

These tests are adversarial on purpose. Each one plays the part of a model that
is wrong in a specific, plausible way -- confident and illegal, confident and
contentless, malformed, truncated, over-long -- and asserts that the wrongness
does not escape the module.
"""

from __future__ import annotations

import json
import random

import pytest

from caissa.llm.guardrails import (
    MAX_TOKENS_CEILING,
    TIMEOUT_CEILING_S,
    ConfidencePolicy,
    FieldSpec,
    SchemaViolation,
    apply_verdict,
    extract_json_object,
    guarded_json_call,
    normalise_square_names,
    validate_fen,
    validate_schema,
)
from caissa.llm.prompts import load_prompt
from caissa.llm.tasks import verify_diagram

from .conftest import GOOD_FEN, PNG_BYTES, FakeRuntime, verdict_reply

# --------------------------------------------------------------------------- #
# Bounded authority -- the invariant that matters most
# --------------------------------------------------------------------------- #


def test_llm_can_never_raise_a_confidence():
    """Randomised: no verdict, at any stated confidence, ever raises the number."""
    rng = random.Random(20260907)
    policy = ConfidencePolicy()
    for _ in range(3000):
        original = rng.random()
        verdict = rng.choice(["consistent", "inconsistent", "uncertain", "garbage"])
        stated = rng.random()
        decision = apply_verdict(original, verdict, stated, policy=policy)
        assert decision.adjusted <= original + 1e-12, (verdict, original, stated)
        assert 0.0 <= decision.adjusted <= 1.0


def test_llm_can_never_touch_a_high_confidence_result():
    """Above the floor the model may flag, and may do nothing else."""
    rng = random.Random(11)
    policy = ConfidencePolicy(high_confidence_floor=0.90)
    for _ in range(2000):
        original = rng.uniform(0.90, 1.0)
        decision = apply_verdict(original, "inconsistent", rng.uniform(0.5, 1.0), policy=policy)
        assert decision.adjusted == original
        assert decision.changed is False
        assert decision.flagged is True


def test_agreement_is_not_evidence():
    """"Consistent" never moves anything: the model agrees with almost anything."""
    for confidence in (0.01, 0.3, 0.5, 0.89, 0.95):
        decision = apply_verdict(confidence, "consistent", 1.0)
        assert decision.adjusted == confidence
        assert decision.flagged is False


def test_low_confidence_llm_disagreement_is_ignored():
    """A model that is itself unsure gets no vote."""
    policy = ConfidencePolicy(min_llm_confidence=0.5)
    decision = apply_verdict(0.4, "inconsistent", 0.2, policy=policy)
    assert decision.adjusted == 0.4
    assert decision.flagged is False


def test_confident_disagreement_lowers_a_weak_result():
    """Below the floor, a confident disagreement is allowed to bite."""
    decision = apply_verdict(0.40, "inconsistent", 1.0, policy=ConfidencePolicy(max_penalty=0.6))
    assert decision.adjusted == pytest.approx(0.16)
    assert decision.flagged is True
    assert decision.changed is True


def test_penalty_is_bounded():
    """Even a maximally confident model cannot drive a result to zero."""
    rng = random.Random(3)
    for _ in range(500):
        original = rng.uniform(0.01, 0.89)
        decision = apply_verdict(original, "inconsistent", 1.0)
        assert decision.adjusted >= original * (1.0 - 0.6) - 1e-12


# --------------------------------------------------------------------------- #
# The model cannot return a FEN at all
# --------------------------------------------------------------------------- #


def test_verification_result_has_no_fen_field():
    """Structural guarantee: there is nowhere to put an invented position."""
    from caissa.llm.tasks import VerificationResult  # noqa: PLC0415 - local by design

    assert "fen" not in VerificationResult.__dataclass_fields__


def test_hallucinated_fen_in_the_reply_is_simply_dropped():
    """A model that volunteers a FEN gets it discarded, not honoured."""
    runtime = FakeRuntime(
        [
            json.dumps(
                {
                    "verdict": "inconsistent",
                    "confidence": 0.99,
                    "suspect_squares": ["e4"],
                    "notes": "corrigido",
                    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    "corrected_fen": "8/8/8/8/8/8/8/8 w - - 0 1",
                }
            )
        ]
    )
    result = verify_diagram(PNG_BYTES, GOOD_FEN, runtime=runtime)
    assert result.verdict == "inconsistent"
    assert not hasattr(result, "fen")
    assert not hasattr(result, "corrected_fen")


# --------------------------------------------------------------------------- #
# Chess is validated by chess
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fen",
    [
        "",
        "not a fen at all",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN w KQkq - 0 1",  # short rank
        "8/8/8/8/8/8/8/8 w - - 0 1",  # no kings
        "4k3/8/8/8/8/8/8/4K2K w - - 0 1",  # two white kings
        "4k3/8/8/8/8/8/8/KKKKKKKK w - - 0 1",
        "pppppppp/4k3/8/8/8/8/8/4K3 w - - 0 1",  # pawns on the 8th rank
    ],
)
def test_illegal_or_malformed_fens_are_rejected(fen):
    """`python-chess` is the arbiter; anything it dislikes returns None."""
    assert validate_fen(fen) is None


def test_bare_placement_is_accepted_and_normalised():
    """A placement-only field is completed rather than rejected."""
    normalised = validate_fen("4k3/8/8/8/8/8/8/4K3")
    assert normalised == "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def test_composition_positions_can_skip_the_legality_check():
    """Problem diagrams break game legality, so the check is a flag, not a law."""
    fen = "8/8/8/8/8/8/8/4K3 w - - 0 1"  # black king missing
    assert validate_fen(fen) is None
    assert validate_fen(fen, require_legal=False) is not None


def test_invented_square_names_are_dropped():
    """Advisory hints are filtered to real squares."""
    assert normalise_square_names(["e4", "j9", "the knight", "", "H8", "e4"]) == ("e4", "h8")


def test_square_hints_are_capped():
    """A model listing every square is not giving a hint."""
    everything = [f"{file}{rank}" for file in "abcdefgh" for rank in "12345678"]
    assert len(normalise_square_names(everything, limit=6)) == 6


def test_inconsistent_without_a_square_is_demoted():
    """"It's wrong" with nothing to point at carries no information."""
    runtime = FakeRuntime([verdict_reply("inconsistent", 0.99, squares=[])])
    result = verify_diagram(PNG_BYTES, GOOD_FEN, runtime=runtime)
    assert result.verdict == "uncertain"
    assert result.disagrees is False
    assert result.decide(0.3).adjusted == 0.3


def test_inconsistent_with_only_junk_squares_is_demoted():
    """Junk square names are dropped, and then the demotion rule applies."""
    runtime = FakeRuntime([verdict_reply("inconsistent", 0.99, squares=["z9", "banana"])])
    assert verify_diagram(PNG_BYTES, GOOD_FEN, runtime=runtime).verdict == "uncertain"


# --------------------------------------------------------------------------- #
# JSON extraction and schema validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        'Sure! Here is the result:\n{"a": 1}\nHope that helps.',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        '{"nested": {"b": 2}, "a": 1}',
        '{"quoted": "a } brace inside a string", "a": 1}',
        '{"escaped": "a \\" quote", "a": 1}',
    ],
)
def test_json_is_found_through_the_usual_wrappers(text):
    """Parsing is tolerant; validation is where strictness lives."""
    assert extract_json_object(text)["a"] == 1


@pytest.mark.parametrize(
    "text", ["", "   ", "no json here", "[1, 2, 3]", '{"unclosed": ', '{"bad": ,}']
)
def test_unparseable_replies_raise(text):
    """Anything that is not a complete object is a violation."""
    with pytest.raises(SchemaViolation):
        extract_json_object(text)


def test_schema_rejects_a_missing_required_field():
    schema = {"verdict": FieldSpec(kind="str", choices=("a", "b"))}
    with pytest.raises(SchemaViolation, match="obrigatorio"):
        validate_schema({}, schema)


def test_schema_rejects_a_value_outside_the_vocabulary():
    """This is what stops a model inventing a verdict."""
    schema = {"verdict": FieldSpec(kind="str", choices=("consistent", "inconsistent"))}
    with pytest.raises(SchemaViolation, match="fora de"):
        validate_schema({"verdict": "probably fine"}, schema)


@pytest.mark.parametrize("value", [-0.5, 1.5, 42, "high", None])
def test_schema_rejects_out_of_range_confidence(value):
    schema = {"confidence": FieldSpec(kind="float", minimum=0.0, maximum=1.0)}
    with pytest.raises(SchemaViolation):
        validate_schema({"confidence": value}, schema)


def test_schema_rejects_a_string_where_a_number_belongs():
    schema = {"moves": FieldSpec(kind="int", minimum=1, maximum=20)}
    with pytest.raises(SchemaViolation):
        validate_schema({"moves": "two"}, schema)


def test_schema_rejects_a_boolean_smuggled_as_a_number():
    schema = {"moves": FieldSpec(kind="int")}
    with pytest.raises(SchemaViolation):
        validate_schema({"moves": True}, schema)


def test_unknown_keys_are_dropped_not_rejected():
    """A chatty extra field is not a lie, but it does not get through either."""
    schema = {"a": FieldSpec(kind="int")}
    assert validate_schema({"a": 1, "explanation": "because"}, schema) == {"a": 1}


def test_optional_fields_fall_back_to_their_default():
    schema = {"notes": FieldSpec(kind="str", required=False, default="")}
    assert validate_schema({}, schema) == {"notes": ""}
    assert validate_schema({"notes": None}, schema) == {"notes": ""}


def test_over_long_strings_are_truncated_not_rejected():
    schema = {"notes": FieldSpec(kind="str", max_length=10)}
    assert validate_schema({"notes": "x" * 500}, schema)["notes"] == "x" * 10


# --------------------------------------------------------------------------- #
# Every failure path is bounded and audited
# --------------------------------------------------------------------------- #


def _call(runtime, audit, values=None):
    return guarded_json_call(
        runtime,
        load_prompt("verify_diagram"),
        {"verdict": FieldSpec(kind="str", choices=("consistent", "inconsistent", "uncertain"))},
        values
        or {"placement": "8/8", "inventory": "", "caption": "", "language": "portugues"},
        task="test",
        log=audit,
    )


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("", "empty"),
        ("I cannot help with that.", "not_json"),
        ('{"verdict": "maybe"}', "schema_violation"),
        ('{"nope": 1}', "schema_violation"),
    ],
)
def test_bad_replies_are_rejected_with_a_named_reason(reply, expected, audit):
    outcome = _call(FakeRuntime([reply]), audit)
    assert outcome.ok is False
    assert outcome.decision == expected
    assert audit.records()[-1].decision == expected


def test_truncated_replies_are_rejected(audit):
    """A cut-off structured answer is discarded, not salvaged."""
    outcome = _call(FakeRuntime(['{"verdict": "consistent"}'], truncated=True), audit)
    assert outcome.decision == "truncated"


def test_unavailable_runtime_is_audited(audit):
    outcome = _call(FakeRuntime(available=False), audit)
    assert outcome.decision == "unavailable"
    assert audit.records()[-1].task == "test"


def test_domain_violation_rejects_after_the_schema_passes(audit):
    outcome = guarded_json_call(
        FakeRuntime(['{"verdict": "consistent"}']),
        load_prompt("verify_diagram"),
        {"verdict": FieldSpec(kind="str")},
        {"placement": "8/8", "inventory": "", "caption": "", "language": "pt"},
        task="test",
        post_validate=lambda _payload: "reprovado pelo dominio",
        log=audit,
    )
    assert outcome.decision == "domain_violation"
    assert outcome.detail == "reprovado pelo dominio"


def test_token_cap_and_timeout_are_clamped(audit):
    """Prompt files are data; the ceilings in code do not trust them."""
    runtime = FakeRuntime([verdict_reply()])
    guarded_json_call(
        runtime,
        load_prompt("verify_diagram"),
        {"verdict": FieldSpec(kind="str")},
        {"placement": "8/8", "inventory": "", "caption": "", "language": "pt"},
        task="test",
        timeout_s=99_999.0,
        log=audit,
    )
    request = runtime.requests[0]
    assert request.max_tokens <= MAX_TOKENS_CEILING
    assert request.timeout_s <= TIMEOUT_CEILING_S


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #


def test_audit_records_prompt_identity_and_latency(audit):
    """A regression must be traceable to the exact prompt revision that caused it."""
    _call(FakeRuntime([verdict_reply()]), audit)
    record = audit.records()[-1]
    template = load_prompt("verify_diagram")
    assert record.prompt_id == "verify_diagram"
    assert record.prompt_version == template.version
    assert record.prompt_sha256 == template.sha256
    assert record.decision == "accepted"
    assert record.latency_ms > 0
    assert record.prompt_text
    assert record.system_text


def test_audit_stores_image_digests_not_image_bytes(audit):
    """The corpus is copyrighted; a log must not become a second copy of it."""
    guarded_json_call(
        FakeRuntime([verdict_reply()]),
        load_prompt("verify_diagram"),
        {"verdict": FieldSpec(kind="str")},
        {"placement": "8/8", "inventory": "", "caption": "", "language": "pt"},
        task="test",
        images=[PNG_BYTES],
        log=audit,
    )
    record = audit.records()[-1]
    assert record.image_digests and len(record.image_digests[0]) == 16
    payload = json.dumps(record.as_dict())
    assert "PNG" not in payload


def test_audit_survives_an_unwritable_path(tmp_path):
    """A broken log directory must not break a batch."""
    from caissa.llm.guardrails import AuditLog  # noqa: PLC0415 - local by design

    log = AuditLog(path=tmp_path / "missing_dir" / "x" / "audit.jsonl")
    _call(FakeRuntime([verdict_reply()]), log)
    assert len(log.records()) == 1


def test_audit_writes_jsonl(tmp_path):
    from caissa.llm.guardrails import AuditLog  # noqa: PLC0415 - local by design

    destination = tmp_path / "audit.jsonl"
    log = AuditLog(path=destination)
    _call(FakeRuntime([verdict_reply()]), log)
    _call(FakeRuntime(["nonsense"]), log)
    lines = destination.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["decision"] == "accepted"
    assert json.loads(lines[1])["decision"] == "not_json"
