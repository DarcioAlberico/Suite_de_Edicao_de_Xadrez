"""Node identity: the thing that makes round-trip fidelity measurable at all.

``semantic_diff`` pairs nodes across two documents by id. That is what turns
"did the exporter lose anything?" from a guess into a number, so identity has to
be genuinely stable, genuinely unique, and genuinely orderable -- and it has to
survive every export format's id syntax without escaping, which is why it is 26
Crockford base32 characters rather than a UUID with hyphens.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest

from caissa.core.model import ULID, ULIDError, new_ulid


def test_a_fresh_ulid_is_twenty_six_crockford_characters():
    text = str(new_ulid())
    assert len(text) == 26
    assert set(text) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_the_string_form_round_trips():
    identifier = new_ulid()
    assert ULID.from_string(str(identifier)) == identifier


def test_the_integer_form_round_trips():
    identifier = new_ulid()
    assert ULID.from_int(identifier.to_int()) == identifier


def test_the_parts_form_is_deterministic():
    first = ULID.from_parts(1_700_000_000_000, 42)
    second = ULID.from_parts(1_700_000_000_000, 42)
    assert first == second
    assert first.timestamp_ms == 1_700_000_000_000
    assert first.randomness == 42


def test_two_fresh_ids_differ():
    assert new_ulid() != new_ulid()


def test_ids_minted_in_sequence_sort_in_that_order():
    """Monotonic within a millisecond: importers mint thousands per millisecond."""
    ids = [new_ulid() for _ in range(2000)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_string_order_matches_value_order():
    ids = sorted(new_ulid() for _ in range(200))
    assert [str(identifier) for identifier in ids] == sorted(str(identifier) for identifier in ids)


def test_minting_is_thread_safe():
    """The UI paints while a worker imports; both mint ids."""
    collected: list[list[ULID]] = []

    def work() -> None:
        collected.append([new_ulid() for _ in range(500)])

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    flat = [identifier for batch in collected for identifier in batch]
    assert len(set(flat)) == len(flat), "two threads minted the same id"


def test_the_timestamp_component_is_readable_as_a_datetime():
    identifier = ULID.from_parts(1_700_000_000_000, 1)
    assert identifier.created_at == datetime.fromtimestamp(1_700_000_000.0, tz=UTC)
    assert identifier.created_at.tzinfo is UTC


def test_a_fresh_id_carries_roughly_the_current_time():
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    assert abs(new_ulid().timestamp_ms - now_ms) < 60_000


def test_ids_are_hashable_and_usable_as_dictionary_keys():
    identifier = new_ulid()
    assert {identifier: "x"}[ULID.from_string(str(identifier))] == "x"


def test_ids_are_immutable():
    identifier = new_ulid()
    with pytest.raises((AttributeError, TypeError)):
        identifier.raw = b"0" * 16  # type: ignore[misc]


def test_the_repr_shows_the_canonical_form():
    identifier = ULID.from_parts(1_700_000_000_000, 1)
    assert repr(identifier) == f"ULID('{identifier}')"


# --------------------------------------------------------------------------- #
# Crockford tolerances
# --------------------------------------------------------------------------- #


def test_parsing_is_case_insensitive():
    identifier = new_ulid()
    assert ULID.from_string(str(identifier).lower()) == identifier


@pytest.mark.parametrize(("alias", "canonical"), [("I", "1"), ("L", "1"), ("O", "0")])
def test_the_crockford_substitutions_are_accepted(alias, canonical):
    base = "0" * 25
    assert ULID.from_string(base + alias) == ULID.from_string(base + canonical)


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", ["", "0", "0" * 25, "0" * 27])
def test_a_string_of_the_wrong_length_is_refused(text):
    with pytest.raises(ULIDError, match="26 caracteres"):
        ULID.from_string(text)


def test_a_character_outside_the_alphabet_is_refused():
    with pytest.raises(ULIDError, match="caractere invalido"):
        ULID.from_string("U" + "0" * 25)


def test_a_string_that_overflows_128_bits_is_refused():
    with pytest.raises(ULIDError, match="excede 128 bits"):
        ULID.from_string("Z" * 26)


@pytest.mark.parametrize("value", [-1, 1 << 128])
def test_an_integer_out_of_range_is_refused(value):
    with pytest.raises(ULIDError, match="fora da faixa"):
        ULID.from_int(value)


@pytest.mark.parametrize(
    ("timestamp", "randomness"),
    [(-1, 0), (1 << 48, 0), (0, -1), (0, 1 << 80)],
)
def test_out_of_range_parts_are_refused(timestamp, randomness):
    with pytest.raises(ULIDError, match="fora da faixa"):
        ULID.from_parts(timestamp, randomness)


@pytest.mark.parametrize("raw", [b"", b"short", b"0" * 17, "not bytes"])
def test_raw_bytes_of_the_wrong_width_are_refused(raw):
    with pytest.raises(ULIDError, match="16 bytes"):
        ULID(raw)  # type: ignore[arg-type]
