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

**Scope, majority and window — ciclo 2, passo B10** (``OCR_UI_ANALISE_C2.md``
§5.7).  Three things the first version could not do, each visible in the
tables the corpus produced:

* **the row's piece was whichever came first.**  ``observe`` fixed
  ``entry.piece`` on the first observation and counted everything else as a
  contradiction, so a symbol whose first swap was the glyph reader's one
  mistake (``'it`` → Q ×3, then K ×26) could never prove the piece 26
  observations said.  The piece of a row is now the **majority** of its
  evidence, and support/contradictions are derived from the counts;
* **the key had no style.**  A book that sets its main line in one face and
  its variations in a smaller one can use the same look-alike for two
  figurines; counted together, the row never proved.  Every observation now
  carries a coarse *style* — the line's size class relative to the page's
  body text (``r`` regular, ``s`` small, ``l`` large; ``""`` unknown) — and
  :meth:`BookCipher.proven` settles per style first, falling back to the
  style-less row;
* **a contradiction counted for ever.**  The evidence keeps the last
  observations by page, and a row whose recent pages agree is proven for the
  pages that follow even when an early page disagreed (a window of pages, not
  of tokens: swaps come in bursts from one page and are not independent).

Each rule can be switched off at the call (``style=None``, ``window=0``), which
is what the benchmark's sabotage does.  Examples now carry the confidence of
the swap that produced them, so a reviewer sees *how sure* the reader was.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["CIPHER_FILE", "DEFAULT_MIN_SUPPORT", "DEFAULT_WINDOW_PAGES", "STYLE_ANY",
           "BookCipher", "CipherEntry", "body_size_of", "size_class"]

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
#: The style-less key: evidence whose line size was unknown, and the fallback.
STYLE_ANY = ""
#: The window of the recency rule, in distinct pages with observations.  Six
#: pages of a problem book are a few hundred moves; a row that agreed with
#: itself for that long has outlived an early mistake.
DEFAULT_WINDOW_PAGES = 6
#: Recent observations kept per entry (page, piece, source, style).  Enough
#: for the window of pages on the densest book of the corpus (~30 swaps of one
#: symbol per page).
_RECENT_KEEP = 240
#: Size classes: a line under ``_SMALL`` × the body size is small type (the
#: variations and footnotes of most chess books), over ``_LARGE`` × is display.
_SMALL = 0.85
_LARGE = 1.25


def size_class(line_size: float, body_size: float) -> str:
    """The coarse style of a line from its size against the page's body size.

    ``""`` when either is unknown: an unknown style is the style-less row, never
    a guess at one of the three.
    """
    if not line_size or not body_size or line_size <= 0 or body_size <= 0:
        return STYLE_ANY
    ratio = line_size / body_size
    if ratio < _SMALL:
        return "s"
    if ratio > _LARGE:
        return "l"
    return "r"


def _settle(counts: Mapping[str, Mapping[str, int]], *, min_support: int,
            min_visual_support: int, piece: str = "") -> str:
    """The piece the evidence in ``counts`` (piece → source → n) settles, or ``""``.

    Settled = the majority piece (or ``piece``, when given: the first-observed
    row of the version-1 rule) has no contradiction and ``min_support``
    legality proofs, or ``min_visual_support`` observations of any kind with
    contradictions inside the glyph reader's own error rate.
    """
    totals = {piece_: sum(sources.values()) for piece_, sources in counts.items() if piece_}
    if not totals:
        return ""
    if piece:
        if piece not in totals:
            return ""
    else:
        piece = max(totals, key=lambda p: (totals[p], p))
    support = totals[piece]
    contradictions = sum(totals.values()) - support
    legal = counts[piece].get("legality", 0)
    if contradictions == 0 and legal >= min_support:
        return piece
    if support >= min_visual_support and contradictions <= support * VISUAL_CONTRADICTION_SHARE:
        # The glyph reader is a 99,1 % classifier: one disagreement in
        # fifty agreeing swaps is its own error rate, not a second
        # meaning of the symbol.  A legality proof keeps the zero.
        return piece
    return ""


@dataclass(slots=True)
class CipherEntry:
    """What the book's evidence says about one symbol.

    ``evidence`` is the whole of it: piece → source → count.  ``piece``,
    ``support``, ``contradictions``, ``disputed`` and ``by_source`` are read
    from it (the majority piece and what disagreed), so the file keeps saying
    what the first version said while the counts are what decides.
    """

    evidence: dict[str, dict[str, int]] = field(default_factory=dict)
    #: ``(page, raw token, legal SAN, confidence)`` of observations that agree
    #: with the majority piece when they were recorded.
    examples: list[tuple[int, str, str, float]] = field(default_factory=list)
    #: style → piece → count, for :meth:`BookCipher.proven` per style.
    by_style: dict[str, dict[str, int]] = field(default_factory=dict)
    #: The last observations, oldest first: ``(page, piece, source, style)``.
    recent: list[tuple[int, str, str, str]] = field(default_factory=list)
    #: The piece of the first observation: the row's piece under the version-1
    #: rule (kept so the majority rule can be switched off and measured).
    first_piece: str = ""

    # -- derived views ----------------------------------------------------- #

    @property
    def totals(self) -> dict[str, int]:
        return {piece: sum(sources.values()) for piece, sources in self.evidence.items()}

    @property
    def piece(self) -> str:
        totals = self.totals
        if not totals:
            return ""
        return max(totals, key=lambda p: (totals[p], p))

    @property
    def support(self) -> int:
        return self.totals.get(self.piece, 0)

    @property
    def contradictions(self) -> int:
        return sum(self.totals.values()) - self.support

    @property
    def disputed(self) -> dict[str, int]:
        piece = self.piece
        return {p: n for p, n in self.totals.items() if p != piece and n}

    @property
    def by_source(self) -> dict[str, int]:
        return dict(self.evidence.get(self.piece, {}))

    def record(self, piece: str, *, source: str, style: str, page: int) -> None:
        if not self.first_piece:
            self.first_piece = piece
        sources = self.evidence.setdefault(piece, {})
        sources[source] = sources.get(source, 0) + 1
        styled = self.by_style.setdefault(style, {})
        styled[piece] = styled.get(piece, 0) + 1
        self.recent.append((page, piece, source, style))
        if len(self.recent) > _RECENT_KEEP:
            del self.recent[: len(self.recent) - _RECENT_KEEP]

    def settled(self, *, min_support: int, min_visual_support: int,
                style: str | None = STYLE_ANY, window: int = DEFAULT_WINDOW_PAGES,
                majority: bool = True) -> str:
        """The piece this entry proves for ``style`` (``None`` = ignore styles).

        Order: the style's own evidence, then the whole row, then the whole
        row over the last ``window`` pages.  ``window=0`` disables the last;
        ``majority=False`` is the version-1 rule (the first-observed piece is
        the row's, whatever came after) -- the sabotage.
        """
        fixed = "" if majority else (self.first_piece or self.piece)
        if style is not None and style and style in self.by_style:
            # A style row is visual evidence with the style's counts; the
            # sources are unknown per style, and a legality proof would have
            # proven the whole row anyway.
            styled = {p: {"glyph": n} for p, n in self.by_style[style].items()}
            piece = _settle(styled, min_support=min_support, min_visual_support=min_visual_support,
                            piece=fixed)
            if piece:
                return piece
        piece = _settle(self.evidence, min_support=min_support, min_visual_support=min_visual_support,
                        piece=fixed)
        if piece or window <= 0 or not self.recent:
            return piece
        pages = sorted({page for page, *_ in self.recent if page >= 0}, reverse=True)[:window]
        if len(pages) < 2:
            # One page is one burst: not a window.
            return ""
        floor = min(pages)
        recent: dict[str, dict[str, int]] = {}
        for page, seen_piece, source, seen_style in self.recent:
            if page < floor or (style is not None and style and seen_style not in (style, STYLE_ANY)):
                continue
            sources = recent.setdefault(seen_piece, {})
            sources[source] = sources.get(source, 0) + 1
        return _settle(recent, min_support=min_support, min_visual_support=min_visual_support,
                       piece=fixed)

    # -- persistence ------------------------------------------------------- #

    def as_dict(self) -> dict[str, Any]:
        return {"piece": self.piece, "support": self.support,
                "contradictions": self.contradictions,
                "examples": [list(e) for e in self.examples], "disputed": dict(self.disputed),
                "by_source": dict(self.by_source),
                "evidence": {p: dict(s) for p, s in sorted(self.evidence.items())},
                "by_style": {st: dict(c) for st, c in sorted(self.by_style.items())},
                "recent": [list(r) for r in self.recent],
                "first_piece": self.first_piece}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CipherEntry:
        evidence = {str(p): {str(s): int(n) for s, n in dict(sources).items()}
                    for p, sources in dict(data.get("evidence", {})).items()}
        if not evidence:
            # A version-1 file: the first piece with its sources, the
            # disputed pieces with no source of their own (a legality proof
            # against the row would have been visible in ``disputed`` only,
            # so they are counted as visual — the weaker kind).
            piece = str(data.get("piece", ""))
            by_source = {str(s): int(n) for s, n in dict(data.get("by_source", {})).items()}
            support = int(data.get("support", 0))
            if piece and support:
                if not by_source:
                    by_source = {"legality": support}
                evidence[piece] = by_source
            for other, n in dict(data.get("disputed", {})).items():
                if int(n):
                    evidence.setdefault(str(other), {})["glyph"] = int(n)
        first_piece = str(data.get("first_piece", "") or data.get("piece", ""))
        examples: list[tuple[int, str, str, float]] = []
        for e in data.get("examples", ()):
            if len(e) >= 3:
                examples.append((int(e[0]), str(e[1]), str(e[2]),
                                 float(e[3]) if len(e) > 3 and e[3] is not None else 0.0))
        return cls(evidence=evidence, examples=examples,
                   by_style={str(st): {str(p): int(n) for p, n in dict(c).items()}
                             for st, c in dict(data.get("by_style", {})).items()},
                   recent=[(int(r[0]), str(r[1]), str(r[2]), str(r[3]) if len(r) > 3 else "")
                           for r in data.get("recent", ()) if len(r) >= 3],
                   first_piece=first_piece)


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
                san: str = "", source: str = "legality", style: str = STYLE_ANY,
                confidence: float = 0.0) -> None:
        """One proved observation: ``symbol`` stood for ``piece`` (by ``source``).

        ``style`` is the line's size class (:func:`size_class`) and
        ``confidence`` the reader's confidence in the swap, kept with the
        example; neither changes what counts as a proof.
        """
        if not symbol or not piece:
            return
        entry = self.entries.setdefault(symbol, CipherEntry())
        entry.record(piece, source=source, style=style or STYLE_ANY, page=page)
        if entry.piece == piece and len(entry.examples) < _MAX_EXAMPLES:
            entry.examples.append((page, raw, san, round(float(confidence), 3)))
        self.dirty = True

    def proven(self, min_support: int | None = None,
               min_visual_support: int = DEFAULT_MIN_VISUAL_SUPPORT, *,
               style: str | None = STYLE_ANY,
               window: int = DEFAULT_WINDOW_PAGES,
               majority: bool = True) -> dict[str, str]:
        """``symbol → piece`` for the rows the evidence settled.

        Settled = no contradiction and either ``min_support`` legality proofs
        or ``min_visual_support`` observations of any kind — per ``style``
        first (``None`` ignores styles), then for the whole row, then over the
        last ``window`` pages (``0`` disables the window).  ``majority=False``
        judges the first-observed piece instead of the majority (version 1).
        """
        floor = self.min_support if min_support is None else min_support
        out: dict[str, str] = {}
        for symbol, entry in self.entries.items():
            piece = entry.settled(min_support=floor, min_visual_support=min_visual_support,
                                  style=style, window=window, majority=majority)
            if piece:
                out[symbol] = piece
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
            styles = [st for st in entry.by_style if st]
            parts.append(f"{symbol!r}→{entry.piece or '?'} ({entry.support}×"
                         + (f", {entry.contradictions} contra" if entry.contradictions else "")
                         + (f", estilos {''.join(sorted(styles))}" if styles else "")
                         + f", {state})")
        return "cifra do livro: " + ", ".join(parts)

    # -- persistence ------------------------------------------------------- #

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 2, "fingerprint": self.fingerprint, "document": self.document,
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


def body_size_of(sizes: Iterable[float]) -> float:
    """The page's body size: the median of the line sizes that are known."""
    known = sorted(float(s) for s in sizes if s and s > 0)
    if not known:
        return 0.0
    middle = len(known) // 2
    if len(known) % 2:
        return known[middle]
    return (known[middle - 1] + known[middle]) / 2.0
