"""Notation-aware post-correction of OCR output — SPEC §7.3.

The boundary this package sits on: :mod:`caissa.ocr` knows what the engines
produced and how badly, and :mod:`caissa.notation` knows what a legal chess
move is.  Neither should grow a dependency on the other's internals, so the
bridge lives here.
"""

from .cipher import (
    CIPHER_SLOT,
    ENGLISH_PIECES,
    CipherReport,
    CipherSymbol,
    candidate_locales,
    decode,
    infer_cipher,
)

#: ``decode`` is unambiguous inside this package and far too generic at the
#: surface of :mod:`caissa.ocr`, where it would read as "decode what?".
decode_cipher = decode

from .movetext import MoveRun, longest_run, move_runs  # noqa: E402

__all__ = [
    "CIPHER_SLOT",
    "ENGLISH_PIECES",
    "CipherReport",
    "CipherSymbol",
    "candidate_locales",
    "decode",
    "decode_cipher",
    "MoveRun",
    "infer_cipher",
    "longest_run",
    "move_runs",
]
