"""The figurine cipher of one book, proved by legality and kept — OCR_UI_ROADMAP passo 3.

:mod:`caissa.ocr.notation.cipher` reads a page and says which Latin symbols the
engine used where the figurines were (``W``, ``H``, ``S``); it resolves the
queen through a promotion and, by design, guesses nothing else.  What resolves
the rest is the legality replay of :mod:`caissa.notation.legality_repair`,
one block at a time, when the block has a position to start from — and 98 %
of the blocks in a book do not (``docs/quality/SOL_REPORT.md`` §3).

The fact this module rests on was measured in ``F5_REPORT_C2.md`` §4 and
``HANDOFF.md`` §4.1: the cipher is **stable within a book** — ``W`` is the queen
on every page of the Gaprindashvili, because the font is the same on every
page — and it **differs between books**, because the fonts do.  So a symbol
the replay proved on the pages that *have* a position is evidence for the
pages that do not, and the evidence is countable: how many independent
positions proved it, and how many contradicted it.

Rules, in the order they matter:

* an entry is **proven** at ``min_support`` independent observations and
  **zero** contradictions (``OCR_UI_SPEC.md`` R2.4, Q5).  A later contradiction
  demotes it and the report says so;
* a proven table is applied only to tokens that are **not words and not
  moves** — the mangled ones — and only where the page's own cipher report
  says the page is ciphered (:func:`cipher.decode` keeps its guard).  Nothing
  here widens the decoder's alphabet (``HANDOFF.md`` §4.1: do not);
* the table lives with the book's other artefacts, keyed by the PDF's
  content hash (``models/tessdata/livros/<slug>/cipher.json``,
  :mod:`caissa.ocr.training.books`), so a second import of the same book
  starts where the first one ended.  A copy under another name finds it; a
  different book with the same name does not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["CIPHER_FILE", "DEFAULT_MIN_SUPPORT", "BookCipher", "CipherEntry"]

CIPHER_FILE = "cipher.json"
#: Q5 of the SPEC: five independent positions, no contradiction.
DEFAULT_MIN_SUPPORT = 5
#: A visual proof — the glyph reader swapping the look-alike for a figurine
#: at ≥ 0,70 (SOL-6) — is weaker than a legal replay and needs more of them
#: before the table trusts it alone.  Measured on the corpus: the books whose
#: notation is damaged keep their positions on other pages (exercise books),
#: so without this second source the table stays empty (OCR_UI_REPORT_C1 §3).
DEFAULT_MIN_VISUAL_SUPPORT = 10
#: Contradictions a visually proven row may carry, as a share of its support
#: (2 %: half the glyph reader's measured error rate, 99,1 % on its test set).
VISUAL_CONTRADICTION_SHARE = 0.02
#: Kept per entry so a reviewer can see *which* moves proved it.
_MAX_EXAMPLES = 6


@dataclass(slots=True)
class CipherEntry:
    """What the book's evidence says about one symbol."""

    piece: str = ""
    support: int = 0
    contradictions: int = 0
    #: ``(page, raw token, legal SAN)`` of the observations that agree.
    examples: list[tuple[int, str, str]] = field(default_factory=list)
    #: The pieces that disagreed, with a count each.
    disputed: dict[str, int] = field(default_factory=dict)
    #: Agreeing observations by kind of proof: ``legality`` (a complete legal
    #: replay) or ``glyph`` (the glyph reader's figurine at ≥ 0,70).
    by_source: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"piece": self.piece, "support": self.support,
                "contradictions": self.contradictions,
                "examples": [list(e) for e in self.examples], "disputed": dict(self.disputed),
                "by_source": dict(self.by_source)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CipherEntry:
        return cls(piece=str(data.get("piece", "")), support=int(data.get("support", 0)),
                   contradictions=int(data.get("contradictions", 0)),
                   examples=[(int(e[0]), str(e[1]), str(e[2])) for e in data.get("examples", ())],
                   disputed={str(k): int(v) for k, v in dict(data.get("disputed", {})).items()},
                   by_source={str(k): int(v)
                              for k, v in dict(data.get("by_source", {})).items()})


@dataclass(slots=True)
class BookCipher:
    """The symbol → piece table of one book, with the evidence for each row."""

    fingerprint: str = ""
    document: str = ""
    entries: dict[str, CipherEntry] = field(default_factory=dict)
    min_support: int = DEFAULT_MIN_SUPPORT
    updated_at: str = ""
    #: Set when :meth:`observe` changed anything since the last :meth:`save`.
    dirty: bool = False

    # -- evidence ---------------------------------------------------------- #

    def observe(self, symbol: str, piece: str, *, page: int = -1, raw: str = "",
                san: str = "", source: str = "legality") -> None:
        """One proved observation: ``symbol`` stood for ``piece`` (by ``source``)."""
        if not symbol or not piece:
            return
        entry = self.entries.setdefault(symbol, CipherEntry())
        if not entry.piece or entry.piece == piece:
            entry.piece = piece
            entry.support += 1
            entry.by_source[source] = entry.by_source.get(source, 0) + 1
            if len(entry.examples) < _MAX_EXAMPLES:
                entry.examples.append((page, raw, san))
        else:
            entry.contradictions += 1
            entry.disputed[piece] = entry.disputed.get(piece, 0) + 1
        self.dirty = True

    def proven(self, min_support: int | None = None,
               min_visual_support: int = DEFAULT_MIN_VISUAL_SUPPORT) -> dict[str, str]:
        """``symbol → piece`` for the rows the evidence settled.

        Settled = no contradiction and either ``min_support`` legality proofs
        or ``min_visual_support`` observations of any kind.
        """
        floor = self.min_support if min_support is None else min_support
        out: dict[str, str] = {}
        for symbol, entry in self.entries.items():
            if not entry.piece:
                continue
            legal = entry.by_source.get("legality", 0)
            if entry.contradictions == 0 and legal >= floor:
                out[symbol] = entry.piece
            elif (entry.support >= min_visual_support
                  and entry.contradictions <= entry.support * VISUAL_CONTRADICTION_SHARE):
                # The glyph reader is a 99,1 % classifier: one disagreement in
                # fifty agreeing swaps is its own error rate, not a second
                # meaning of the symbol.  A legality proof keeps the zero.
                out[symbol] = entry.piece
        return out

    @property
    def observations(self) -> int:
        return sum(e.support + e.contradictions for e in self.entries.values())

    def describe_pt(self) -> str:
        if not self.entries:
            return "cifra do livro: nenhuma observação ainda."
        proven = self.proven()
        parts = []
        for symbol, entry in sorted(self.entries.items()):
            state = ("provada" if symbol in proven
                     else "contraditada" if entry.contradictions else "em evidência")
            parts.append(f"{symbol!r}→{entry.piece or '?'} ({entry.support}×"
                         + (f", {entry.contradictions} contra" if entry.contradictions else "")
                         + f", {state})")
        return "cifra do livro: " + ", ".join(parts)

    # -- persistence ------------------------------------------------------- #

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1, "fingerprint": self.fingerprint, "document": self.document,
            "min_support": self.min_support, "updated_at": self.updated_at,
            "entries": {s: e.as_dict() for s, e in sorted(self.entries.items())},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BookCipher:
        return cls(
            fingerprint=str(data.get("fingerprint", "")), document=str(data.get("document", "")),
            entries={str(s): CipherEntry.from_dict(e)
                     for s, e in dict(data.get("entries", {})).items()},
            min_support=int(data.get("min_support", DEFAULT_MIN_SUPPORT)),
            updated_at=str(data.get("updated_at", "")))

    @classmethod
    def load(cls, path: Path | str, *, fingerprint: str | None = None) -> BookCipher | None:
        """The table at ``path``.

        ``None`` when absent, unreadable, or — when ``fingerprint`` is given —
        belonging to another PDF.
        """
        file = Path(path)
        if not file.is_file():
            return None
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        table = cls.from_dict(data)
        if fingerprint and table.fingerprint and table.fingerprint != fingerprint:
            return None
        return table

    def save(self, path: Path | str) -> Path:
        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        file.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        self.dirty = False
        return file
