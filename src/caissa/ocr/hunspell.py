"""A minimal Hunspell reader — enough to ask "is this a word?" (Sol §SOL-9).

The packaged dictionaries are Hunspell ``.dic`` stems with their affix flags
and the ``.aff`` rules that inflect them.  Expanding every stem through every
rule would produce millions of forms and a package nobody could ship; this
module does the reverse instead, at lookup time: strip a candidate suffix
(and prefix) whose rule condition the remaining stem satisfies, and accept
the word when that stem is in the dictionary *with that rule's flag*.  That
is the same test Hunspell makes, restricted to what a lexicon lookup needs:
no compounding, no replacement tables, no suggestions.

Supported: ``SFX``/``PFX`` rules with ``strip``, ``add`` and ``condition``;
cross-product of one prefix with one suffix when both rules allow it;
``FLAG UTF-8`` and the default single-character flags; ``FLAG long`` and
``FLAG num`` flag encodings.  Continuation flags on affixes (an affix that
carries flags of its own) are honoured one level deep, which covers the
Portuguese ``-mente`` on ``-a`` forms and the English plural of ``-er``.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Iterable

__all__ = ["HunspellDictionary", "load_packaged_dictionary"]


@dataclass(frozen=True, slots=True)
class Affix:
    flag: str
    strip: str
    add: str
    condition: re.Pattern[str] | None
    cross: bool
    continuation: frozenset[str]


class HunspellDictionary:
    """Stems with flags plus the rules, queried by :meth:`is_word`."""

    def __init__(self) -> None:
        self.stems: dict[str, frozenset[str]] = {}
        self.flag_mode = "char"
        self.suffixes: dict[str, list[Affix]] = {}     # keyed by ``add``
        self.prefixes: dict[str, list[Affix]] = {}
        self.max_suffix = 0
        self.max_prefix = 0
        self.flags_by_rule: dict[str, bool] = {}       # rule flag -> cross-product

    # -- loading ----------------------------------------------------------- #

    def parse_flags(self, raw: str) -> frozenset[str]:
        if not raw:
            return frozenset()
        if self.flag_mode == "long":
            return frozenset(raw[i:i + 2] for i in range(0, len(raw) - 1, 2))
        if self.flag_mode == "num":
            return frozenset(part for part in raw.split(",") if part)
        return frozenset(raw)

    def load_aff(self, lines: Iterable[str]) -> None:
        for line in lines:
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if parts[0] == "FLAG" and len(parts) > 1:
                mode = parts[1].lower()
                self.flag_mode = "long" if mode == "long" else "num" if mode == "num" else "char"
                continue
            if parts[0] not in ("SFX", "PFX") or len(parts) < 4:
                continue
            if len(parts) == 4 and parts[2] in ("Y", "N"):
                self.flags_by_rule[parts[1]] = parts[2] == "Y"
                continue
            flag, strip, add = parts[1], parts[2], parts[3]
            condition = parts[4] if len(parts) > 4 else "."
            strip = "" if strip == "0" else strip
            continuation: frozenset[str] = frozenset()
            if "/" in add:
                add, extra = add.split("/", 1)
                continuation = self.parse_flags(extra)
            add = "" if add == "0" else add
            pattern = None
            if condition and condition != ".":
                anchor = f"{_condition_regex(condition)}$" if parts[0] == "SFX" else (
                    f"^{_condition_regex(condition)}")
                try:
                    pattern = re.compile(anchor)
                except re.error:
                    pattern = None
            affix = Affix(flag, strip, add, pattern, self.flags_by_rule.get(flag, False),
                          continuation)
            table = self.suffixes if parts[0] == "SFX" else self.prefixes
            table.setdefault(add, []).append(affix)
            if parts[0] == "SFX":
                self.max_suffix = max(self.max_suffix, len(add))
            else:
                self.max_prefix = max(self.max_prefix, len(add))

    def load_dic(self, lines: Iterable[str]) -> None:
        first = True
        for line in lines:
            line = line.strip().lstrip("﻿")
            if first:
                first = False
                if line.isdigit():
                    continue
            if not line or line.startswith("#"):
                continue
            word, _, rest = line.partition("/")
            word = word.split("\t", 1)[0].strip()
            if not word:
                continue
            flags = self.parse_flags(rest.split("\t", 1)[0].strip())
            folded = word.casefold()
            self.stems[folded] = self.stems.get(folded, frozenset()) | flags

    # -- lookup ------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self.stems)

    def __contains__(self, word: str) -> bool:
        return self.is_word(word)

    def is_word(self, word: str) -> bool:
        w = word.casefold()
        if w in self.stems:
            return True
        for stem, needed, cross in self._strip_suffix(w):
            flags = self.stems.get(stem)
            if flags is not None and needed <= flags:
                return True
            if cross:
                for stem2, needed2, _ in self._strip_prefix(stem, cross_only=True):
                    flags2 = self.stems.get(stem2)
                    if flags2 is not None and (needed | needed2) <= flags2:
                        return True
        for stem, needed, _ in self._strip_prefix(w):
            flags = self.stems.get(stem)
            if flags is not None and needed <= flags:
                return True
        return False

    def _strip_suffix(self, w: str) -> list[tuple[str, frozenset[str], bool]]:
        out: list[tuple[str, frozenset[str], bool]] = []
        for n in range(0, min(self.max_suffix, len(w)) + 1):
            add = w[len(w) - n:] if n else ""
            for affix in self.suffixes.get(add, ()):
                base = w[:len(w) - n] + affix.strip
                if not base:
                    continue
                if affix.condition is not None and not affix.condition.search(base):
                    continue
                out.append((base, frozenset({affix.flag}), affix.cross))
                # One level of continuation: the affix itself carries flags.
                for flag in affix.continuation:
                    out.append((base, frozenset({affix.flag}) - {flag}, affix.cross))
        return out

    def _strip_prefix(self, w: str, *, cross_only: bool = False
                      ) -> list[tuple[str, frozenset[str], bool]]:
        out: list[tuple[str, frozenset[str], bool]] = []
        for n in range(0, min(self.max_prefix, len(w)) + 1):
            add = w[:n]
            for affix in self.prefixes.get(add, ()):
                if cross_only and not affix.cross:
                    continue
                base = affix.strip + w[n:]
                if not base:
                    continue
                if affix.condition is not None and not affix.condition.search(base):
                    continue
                out.append((base, frozenset({affix.flag}), affix.cross))
        return out


def _condition_regex(condition: str) -> str:
    """A Hunspell condition is already a regex fragment: ``[^ã][gpk]``."""
    return condition.replace("(", "\\(").replace(")", "\\)")


@lru_cache(maxsize=8)
def load_packaged_dictionary(code: str, package: str = "caissa.ocr.data.lexicon"
                             ) -> HunspellDictionary | None:
    """``<code>.dic.gz`` + ``<code>.aff.gz`` from the package, or ``None``."""
    try:
        dic = resources.files(package).joinpath(f"{code}.dic.gz").read_bytes()
        aff = resources.files(package).joinpath(f"{code}.aff.gz").read_bytes()
    except (FileNotFoundError, OSError, ModuleNotFoundError):
        return None
    try:
        dictionary = HunspellDictionary()
        dictionary.load_aff(gzip.decompress(aff).decode("utf-8", "replace").splitlines())
        dictionary.load_dic(gzip.decompress(dic).decode("utf-8", "replace").splitlines())
    except (OSError, EOFError, gzip.BadGzipFile, ValueError):
        return None
    return dictionary
