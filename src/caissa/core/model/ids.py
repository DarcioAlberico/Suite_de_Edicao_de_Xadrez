"""Stable node identity for the Document IR.

Every node in the IR carries a :class:`ULID` (Universally Unique
Lexicographically Sortable Identifier, 128 bits: a 48-bit millisecond timestamp
followed by 80 bits of entropy, rendered as 26 Crockford base32 characters).

The IR uses ULIDs rather than UUIDs for three reasons:

* they sort by creation time, so a diff of two documents produces stable,
  human-readable ordering;
* they are 26 characters of case-insensitive base32, which survives every export
  format (XML ``id`` attributes, LaTeX labels, EPUB fragment identifiers) without
  escaping;
* identity is what makes round-trip fidelity measurable -- ``semantic_diff``
  matches nodes by id, so an exporter that preserves ids can be proven lossless.

The implementation is deliberately self-contained (pure standard library) so
that ``caissa.core.model`` has no import-time dependency at all. The string form
is the canonical ULID encoding, so values interoperate byte-for-byte with the
``python-ulid`` package should another subsystem use it.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

__all__ = ["ULID", "ULIDError", "new_ulid"]

#: Crockford base32 alphabet: digits plus uppercase letters minus I, L, O and U.
_ENCODING: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

#: Reverse lookup table, tolerant of lowercase input and of the classic
#: Crockford substitutions (``I``/``L`` read as ``1``, ``O`` reads as ``0``).
_DECODING: Final[dict[str, int]] = {char: index for index, char in enumerate(_ENCODING)}
for _char, _index in list(_DECODING.items()):
    _DECODING[_char.lower()] = _index
for _alias, _target in (("I", 1), ("i", 1), ("L", 1), ("l", 1), ("O", 0), ("o", 0)):
    _DECODING[_alias] = _target

_ULID_LENGTH: Final = 26
_ULID_BYTES: Final = 16
_TIMESTAMP_BYTES: Final = 6
_MAX_TIMESTAMP_MS: Final = (1 << 48) - 1
_MAX_RANDOMNESS: Final = (1 << 80) - 1


class ULIDError(ValueError):
    """Raised when a value cannot be interpreted as a ULID."""


_MONOTONIC_LOCK: Final = threading.Lock()
_last_timestamp_ms: int = -1
_last_randomness: int = 0


def _next_raw() -> bytes:
    """Return the next 16 raw bytes, monotonic within a single millisecond.

    Two ULIDs minted in the same millisecond keep their creation order: the
    randomness component is incremented rather than redrawn. This matters
    because importers create thousands of nodes per millisecond and the IR
    relies on id ordering being meaningful.

    Monotonicity is the stronger guarantee and wins over clock accuracy. The
    timestamp is therefore never allowed to go backwards, which covers the two
    ways it otherwise would: the system clock stepping back (an NTP correction,
    a virtual machine resuming from a snapshot), and the entropy counter
    overflowing inside one millisecond, which borrows a millisecond from the
    future and must keep it until the real clock catches up.

    Returns:
        Sixteen bytes: six of big-endian millisecond timestamp, ten of entropy.
    """
    global _last_timestamp_ms, _last_randomness  # noqa: PLW0603
    with _MONOTONIC_LOCK:
        timestamp_ms = min(int(time.time() * 1000.0), _MAX_TIMESTAMP_MS)
        timestamp_ms = max(timestamp_ms, _last_timestamp_ms)
        if timestamp_ms == _last_timestamp_ms:
            if _last_randomness >= _MAX_RANDOMNESS:
                # Overflow inside one millisecond: borrow the next one rather
                # than break monotonicity.
                timestamp_ms += 1
                randomness = int.from_bytes(os.urandom(10), "big")
            else:
                randomness = _last_randomness + 1
        else:
            randomness = int.from_bytes(os.urandom(10), "big")
        _last_timestamp_ms = timestamp_ms
        _last_randomness = randomness
    return timestamp_ms.to_bytes(_TIMESTAMP_BYTES, "big") + randomness.to_bytes(10, "big")


@dataclass(frozen=True, slots=True, order=True)
class ULID:
    """A 128-bit lexicographically sortable identifier.

    Instances are immutable, hashable and ordered by their raw bytes, which is
    the same order as their canonical string form and as their creation time.

    Attributes:
        raw: Exactly 16 bytes; the first 6 are a big-endian millisecond
            timestamp and the remaining 10 are entropy.
    """

    raw: bytes

    def __post_init__(self) -> None:
        """Validate the raw byte width.

        Raises:
            ULIDError: If ``raw`` is not exactly 16 bytes.
        """
        if not isinstance(self.raw, bytes) or len(self.raw) != _ULID_BYTES:
            msg = f"ULID exige exatamente {_ULID_BYTES} bytes; recebido {self.raw!r}"
            raise ULIDError(msg)

    # -- construction ------------------------------------------------------

    @classmethod
    def new(cls) -> ULID:
        """Mint a fresh ULID from the current clock.

        Returns:
            A new identifier, strictly greater than every identifier minted
            earlier by this process.
        """
        return cls(_next_raw())

    @classmethod
    def from_string(cls, text: str) -> ULID:
        """Parse the canonical 26-character Crockford base32 form.

        Args:
            text: A ULID string. Case-insensitive; the Crockford aliases
                ``I``/``L`` -> ``1`` and ``O`` -> ``0`` are accepted.

        Returns:
            The parsed identifier.

        Raises:
            ULIDError: If the string is the wrong length, contains characters
                outside the alphabet, or overflows 128 bits.
        """
        if len(text) != _ULID_LENGTH:
            msg = f"ULID deve ter {_ULID_LENGTH} caracteres; recebido {len(text)} em {text!r}"
            raise ULIDError(msg)
        value = 0
        for char in text:
            try:
                value = (value << 5) | _DECODING[char]
            except KeyError as exc:
                msg = f"caractere invalido {char!r} em ULID {text!r}"
                raise ULIDError(msg) from exc
        if value >= 1 << 128:
            msg = f"ULID {text!r} excede 128 bits"
            raise ULIDError(msg)
        return cls(value.to_bytes(_ULID_BYTES, "big"))

    @classmethod
    def from_int(cls, value: int) -> ULID:
        """Build a ULID from a 128-bit unsigned integer.

        Args:
            value: An integer in ``[0, 2**128)``.

        Returns:
            The corresponding identifier.

        Raises:
            ULIDError: If ``value`` is out of range.
        """
        if not 0 <= value < 1 << 128:
            msg = f"valor {value} fora da faixa de 128 bits"
            raise ULIDError(msg)
        return cls(value.to_bytes(_ULID_BYTES, "big"))

    @classmethod
    def from_parts(cls, timestamp_ms: int, randomness: int) -> ULID:
        """Build a ULID from an explicit timestamp and entropy value.

        Deterministic construction is what allows tests to generate reproducible
        corpora of tens of thousands of nodes.

        Args:
            timestamp_ms: Milliseconds since the Unix epoch, ``[0, 2**48)``.
            randomness: Entropy component, ``[0, 2**80)``.

        Returns:
            The corresponding identifier.

        Raises:
            ULIDError: If either component is out of range.
        """
        if not 0 <= timestamp_ms <= _MAX_TIMESTAMP_MS:
            msg = f"timestamp {timestamp_ms} fora da faixa de 48 bits"
            raise ULIDError(msg)
        if not 0 <= randomness <= _MAX_RANDOMNESS:
            msg = f"componente aleatorio {randomness} fora da faixa de 80 bits"
            raise ULIDError(msg)
        return cls(timestamp_ms.to_bytes(_TIMESTAMP_BYTES, "big") + randomness.to_bytes(10, "big"))

    # -- projection --------------------------------------------------------

    @property
    def timestamp_ms(self) -> int:
        """Milliseconds since the Unix epoch encoded in the first 48 bits."""
        return int.from_bytes(self.raw[:_TIMESTAMP_BYTES], "big")

    @property
    def randomness(self) -> int:
        """The 80-bit entropy component."""
        return int.from_bytes(self.raw[_TIMESTAMP_BYTES:], "big")

    @property
    def created_at(self) -> datetime:
        """Creation instant, in UTC, derived from the timestamp component."""
        return datetime.fromtimestamp(self.timestamp_ms / 1000.0, tz=UTC)

    def to_int(self) -> int:
        """Return the identifier as a 128-bit unsigned integer."""
        return int.from_bytes(self.raw, "big")

    def __str__(self) -> str:
        """Return the canonical 26-character Crockford base32 encoding."""
        value = int.from_bytes(self.raw, "big")
        chars = ["0"] * _ULID_LENGTH
        for position in range(_ULID_LENGTH - 1, -1, -1):
            chars[position] = _ENCODING[value & 0x1F]
            value >>= 5
        return "".join(chars)

    def __repr__(self) -> str:
        """Return an unambiguous representation showing the canonical form."""
        return f"ULID({str(self)!r})"


def new_ulid() -> ULID:
    """Mint a fresh identifier.

    Module-level alias for :meth:`ULID.new`, used as the ``default_factory`` of
    every node's ``id`` field.

    Returns:
        A new identifier.
    """
    return ULID.new()
