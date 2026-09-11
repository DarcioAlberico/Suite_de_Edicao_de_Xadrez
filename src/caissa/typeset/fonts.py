"""Chess font discovery, glyph mapping, outline access and subsetting.

Origem: Editor_Diagramas_de_Xadrez/src/chess_pdf_editor/renderer.py (tabelas Merida)
        + PDFimport/PDFImport_v1.2.0/PDFImport/chessfig.py (deteccao por nome)
        + PDFimport/PDFImport_v1.2.0/PDFImport/fontembed.py (cmap sintetizada)
Absorvido em 2026-09-07.

Alteracoes e por que
--------------------
* ``renderer.py`` trazia UMA tabela (Merida) embutida no codigo. Aqui a tabela virou
  ``ChessFontSpec``: acrescentar uma familia e *dado*, nao codigo.
* ``renderer.py`` resolvia o caractere deixando o Pillow procurar no cmap. Isso falha
  silenciosamente na Merida instalada como TTF, que so tem cmap ``(3, 0)`` simbolica --
  o Pillow desenha o vazio e o tabuleiro sai em branco. Ver `CharacterResolver`.
* ``fontembed.py`` reconstroi a cmap de fontes subconjuntadas *na importacao*. A mesma
  ideia serve na exportacao, e pela mesma razao: sem uma cmap Unicode ``(3, 1)`` o
  navegador nao mapeia 'p' e o EPUB sai sem pecas. Ver `subset_font`.

The two glyph models
--------------------
**Legacy.** The piece sits on an ASCII letter, and the letter differs by square colour:
in the Marroquin/Bentzen convention a white pawn is ``p`` on a light square and ``P`` on
a dark one. The dark-square glyph carries the square's hatch or tint *inside the glyph*,
which is why only the light-square glyph is used for artwork (see ``outlines`` module).

**Unicode.** U+2654..U+265F, one codepoint per piece, no square background at all. This
is what a modern text font provides, and it is the fallback when no legacy font is
installed.

Honesty rule
------------
``ChessFontSpec.confidence`` is not an opinion. ``VERIFIED`` means `verify_spec` was run
against a real font file on disk and every structural invariant held. Anything else is
``UNVERIFIED`` or ``PARTIAL`` and says so. Re-run the check any time with
``python -m caissa.typeset.fonts --verify``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sys
import warnings
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .outlines import Outline, PathBuilder, outline_from_pen

__all__ = [
    "FontUnreadableError",
    "CHESS_FONT_SPECS",
    "ChessFontSpec",
    "Confidence",
    "FontModel",
    "FontNotFoundError",
    "LoadedFont",
    "PIECES",
    "UNICODE_PIECES",
    "available_specs",
    "find_font_file",
    "get_spec",
    "load_font",
    "pin_font_timestamp",
    "search_paths",
    "subset_font",
    "SUBSET_EPOCH",
    "woff2_available",
    "verify_spec",
    "verified_specs",
]

PIECES: tuple[str, ...] = ("K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p")
"""FEN piece letters. Upper case is White, lower case is Black."""

UNICODE_PIECES: dict[str, str] = {
    "K": "\u2654",
    "Q": "\u2655",
    "R": "\u2656",
    "B": "\u2657",
    "N": "\u2658",
    "P": "\u2659",
    "k": "\u265A",
    "q": "\u265B",
    "r": "\u265C",
    "b": "\u265D",
    "n": "\u265E",
    "p": "\u265F",
}


class FontModel(str, Enum):
    LEGACY = "legacy"
    """Piece on an ASCII letter, a different letter per square colour."""

    UNICODE = "unicode"
    """Piece on U+2654..U+265F, no square background."""


class Confidence(str, Enum):
    VERIFIED = "verified"
    """`verify_spec` passed against a real file: every invariant in §Verification held."""

    PARTIAL = "partial"
    """The file exists and some pieces check out, but the family is incomplete."""

    UNVERIFIED = "unverified"
    """No font file was available to check the mapping against. Do not trust the table."""


class FontNotFoundError(RuntimeError):
    """Nenhum arquivo de fonte encontrado para a familia pedida."""


class FontUnreadableError(RuntimeError):
    """O arquivo existe mas nao pode ser lido (tabela corrompida, formato invalido).

    Acontece de verdade: varias fontes de xadrez em circulacao tem `cmap` truncada ou
    `head` com data invalida, heranca de ferramentas dos anos 90. Uma familia assim e
    tratada como indisponivel, nunca como motivo para derrubar a renderizacao inteira.
    """


# --------------------------------------------------------------------------- #
# The Marroquin / Bentzen legacy layout
# --------------------------------------------------------------------------- #
# Shared by the whole Armando Marroquin + Eric Bentzen family of diagram fonts. Taken
# from Editor_Diagramas_de_Xadrez/renderer.py, which has been rendering boards with it
# in production, and re-checked here per font by `verify_spec`.
_MARROQUIN_LIGHT: dict[str, str] = {
    "P": "p", "N": "n", "B": "b", "R": "r", "Q": "q", "K": "k",
    "p": "o", "n": "m", "b": "v", "r": "t", "q": "w", "k": "l",
}
_MARROQUIN_DARK: dict[str, str] = {
    "P": "P", "N": "N", "B": "B", "R": "R", "Q": "Q", "K": "K",
    "p": "O", "n": "M", "b": "V", "r": "T", "q": "W", "k": "L",
}

# Chess Alpha and Chess Regular are Bentzen designs that do NOT use the layout above,
# and assuming they did produces a board with two bishops and no knights. Established
# here by inspection of the actual outlines (2026-09-07): in both files 'm' and 'v' are
# empty, 'n' draws a solid *bishop*, and the knights live on 'h' (white) and 'j' (black).
_ALPHA_LIGHT: dict[str, str] = {
    "P": "p", "N": "h", "B": "b", "R": "r", "Q": "q", "K": "k",
    "p": "o", "n": "j", "b": "n", "r": "t", "q": "w", "k": "l",
}
_ALPHA_DARK: dict[str, str] = {
    "P": "P", "N": "H", "B": "B", "R": "R", "Q": "Q", "K": "K",
    "p": "O", "n": "J", "b": "N", "r": "T", "q": "W", "k": "L",
}


@dataclass(frozen=True)
class FigurineSpec:
    """How a family's piece glyphs behave when set inline in running text.

    ``baseline_shift_em`` and ``optical_scale`` are *measured* by
    :func:`caissa.typeset.figurine.measure_family`, not guessed; the values carried here
    are the fallback used before a measurement is available.
    """

    source: str = "light"
    """Which glyph set supplies the inline piece: ``light`` (bare piece, legacy
    diagram font), ``figurine`` (a dedicated figurine font) or ``unicode``."""

    baseline_shift_em: float = 0.0
    optical_scale: float = 1.0


@dataclass(frozen=True)
class ChessFontSpec:
    """Everything needed to draw a board with one font family. Data, not code."""

    key: str
    family: str
    model: FontModel
    file_names: tuple[str, ...]
    light: Mapping[str, str] = field(default_factory=dict)
    dark: Mapping[str, str] = field(default_factory=dict)
    empty_light: str = " "
    empty_dark: str = "+"
    confidence: Confidence = Confidence.UNVERIFIED
    verified_sha256: str | None = None
    figurine: FigurineSpec = field(default_factory=FigurineSpec)
    notes: str = ""

    def char_for(self, piece: str, *, dark_square: bool) -> str:
        """The character carrying ``piece`` on a square of the given colour."""
        if self.model is FontModel.UNICODE:
            return UNICODE_PIECES[piece]
        table = self.dark if dark_square else self.light
        return table[piece]

    def artwork_char(self, piece: str) -> str:
        """The character whose glyph is the bare piece, with no square background.

        For a legacy font that is always the light-square glyph; for Unicode it is the
        codepoint itself.
        """
        if self.model is FontModel.UNICODE:
            return UNICODE_PIECES[piece]
        return self.light[piece]


def _legacy(
    key: str,
    family: str,
    files: Sequence[str],
    *,
    layout: str = "marroquin",
    confidence: Confidence = Confidence.UNVERIFIED,
    sha: str | None = None,
    notes: str = "",
    figurine: FigurineSpec | None = None,
) -> ChessFontSpec:
    light, dark = {
        "marroquin": (_MARROQUIN_LIGHT, _MARROQUIN_DARK),
        "alpha": (_ALPHA_LIGHT, _ALPHA_DARK),
    }[layout]
    return ChessFontSpec(
        key=key,
        family=family,
        model=FontModel.LEGACY,
        file_names=tuple(files),
        light=dict(light),
        dark=dict(dark),
        confidence=confidence,
        verified_sha256=sha,
        figurine=figurine or FigurineSpec(source="light"),
        notes=notes,
    )


# --------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------- #
# `confidence` and `verified_sha256` below are written by
# `python -m caissa.typeset.fonts --emit-verification`, which runs `verify_spec` against
# whatever is installed. They are evidence, not claims. A family with no file on this
# machine stays UNVERIFIED however plausible its layout looks.
CHESS_FONT_SPECS: dict[str, ChessFontSpec] = {}


def _register(spec: ChessFontSpec) -> None:
    CHESS_FONT_SPECS[spec.key] = spec


_register(
    ChessFontSpec(
        key="unicode",
        family="Unicode (U+2654-U+265F)",
        model=FontModel.UNICODE,
        file_names=(
            "DejaVuSans.ttf",
            "seguisym.ttf",
            "NotoSansSymbols2-Regular.ttf",
            "Segoe UI Symbol.ttf",
            "arialuni.ttf",
            "Arial-Unicode-MS.ttf",
        ),
        confidence=Confidence.VERIFIED,
        figurine=FigurineSpec(source="unicode"),
        notes=(
            "Reserva universal. Sem fundo de casa no glifo, entao serve tanto para "
            "diagrama quanto para figurino; o desenho depende da fonte de texto."
        ),
    )
)

_register(_legacy("merida", "Chess Merida", ["ChessMerida.ttf", "chessmerida.otf", "Merida.ttf"]))
_register(
    _legacy(
        "alpha",
        "Chess Alpha",
        ["ChessAlpha.ttf", "Chess Alpha.ttf"],
        layout="alpha",
        notes="Cavalos em 'h'/'j', bispo preto em 'n'. NAO usa o layout Marroquin.",
    )
)
_register(_legacy("cases", "Chess Cases", ["Chess Cases.ttf", "ChessCases.ttf"]))
_register(_legacy("berlin", "Chess Berlin", ["Chess Berlin.ttf", "ChessBerlin.ttf"]))
_register(_legacy("leipzig", "Chess Leipzig", ["Chess Leipzig.ttf", "ChessLeipzig.ttf"]))
_register(_legacy("marroquin", "Chess Marroquin", ["Chess Marroquin.ttf", "ChessMarroquin.ttf"]))
_register(_legacy("condal", "Chess Condal", ["Chess Condal.ttf"]))
_register(_legacy("lucena", "Chess Lucena", ["Chess Lucena.ttf"]))
_register(_legacy("maya", "Chess Maya", ["Chess Maya.ttf"]))
_register(
    ChessFontSpec(
        key="utrecht",
        family="Chess Utrecht",
        model=FontModel.LEGACY,
        file_names=("Chess Utrecht.ttf",),
        light=dict(_MARROQUIN_LIGHT),
        dark=dict(_MARROQUIN_DARK),
        confidence=Confidence.UNVERIFIED,
        notes=(
            "Modelo diferente e incompativel: em 'Chess Utrecht' o segundo conjunto "
            "('o','m','v','t','w','l') nao sao as pecas PRETAS -- sao as mesmas pecas "
            "BRANCAS sobre casa escura hachurada. So ha 37 glifos no arquivo, sem jogo "
            "de pecas pretas. Nao use para diagrama."
        ),
    )
)
_register(_legacy("kingdom", "Chess Kingdom", ["Chess Kingdom.ttf"]))
_register(_legacy("mediaeval", "Chess Mediaeval", ["Chess Mediaeval.ttf"]))
_register(_legacy("motif", "Chess Motif", ["Chess Motif.ttf"]))
_register(_legacy("harlequin", "Chess Harlequin", ["Chess Harlequin.ttf"]))
_register(_legacy("alfonso", "Chess Alfonso-X", ["Chess Alfonso-X.ttf"]))
_register(_legacy("magnetic", "Chess Magnetic", ["Chess Magnetic.ttf"]))
_register(_legacy("millennia", "Chess Millennia", ["Chess Millennia-L.ttf", "Chess Millennia-D.ttf"]))
_register(_legacy("adventurer", "Chess Adventurer", ["Chess Adventurer.ttf"]))
_register(_legacy("line", "Chess Line", ["Chess Line.ttf"]))
_register(
    _legacy(
        "regular",
        "Chess Regular",
        ["Chess Regular.ttf"],
        layout="alpha",
        notes="Mesmo layout da Chess Alpha: cavalos em 'h'/'j', bispo preto em 'n'.",
    )
)

# Families whose real-world encoding is NOT the Marroquin layout. The tables here are
# filled in only where a file could be inspected; otherwise the family is registered
# with an empty mapping and UNVERIFIED so that callers get a clear failure rather than a
# board full of wrong pieces.
_register(
    ChessFontSpec(
        key="diagramttf",
        family="DiagramTTF (Fritz)",
        model=FontModel.LEGACY,
        file_names=("DiaTTFri.ttf", "DiagramTTF.ttf"),
        light=dict(_MARROQUIN_LIGHT),
        dark=dict(_MARROQUIN_DARK),
        confidence=Confidence.UNVERIFIED,
        notes=(
            "DiagramTTFritz nao segue o layout Marroquin: 'm', 'v', 't', 'w' desenham "
            "figuras minusculas em vez das pecas pretas. Tabela NAO confiavel."
        ),
    )
)
_register(
    ChessFontSpec(
        key="zurich",
        family="Zurich",
        model=FontModel.LEGACY,
        file_names=("AFMOBA-ZurichDiagram.ttf", "ZurichDiagram.ttf", "Zurich.ttf"),
        light=dict(_MARROQUIN_LIGHT),
        dark=dict(_MARROQUIN_DARK),
        confidence=Confidence.UNVERIFIED,
        notes=(
            "O unico arquivo Zurich nesta maquina e um SUBCONJUNTO extraido de PDF "
            "(nome com etiqueta 'AFMOBA+'), com 22 caracteres mapeados de 230 glifos. "
            "Nao da para verificar a familia inteira a partir dele."
        ),
    )
)
_register(
    ChessFontSpec(
        key="linares",
        family="Linares",
        model=FontModel.LEGACY,
        file_names=("AFEOHC-LinaresDiagram.ttf", "LinaresDiagram.ttf", "Linares.ttf"),
        light=dict(_MARROQUIN_LIGHT),
        dark=dict(_MARROQUIN_DARK),
        confidence=Confidence.UNVERIFIED,
        notes=(
            "Idem Zurich: so ha subconjunto extraido de PDF ('AFEOHC+LinaresDiagram', "
            "17 caracteres mapeados). Tabela nao verificavel."
        ),
    )
)


# --------------------------------------------------------------------------- #
# Verification record
# --------------------------------------------------------------------------- #
# Produced by `python -m caissa.typeset.fonts --emit-verification` on 2026-09-07 against
# the fonts installed on the reference machine, and cross-checked by eye on rendered
# contact sheets of all twelve pieces per family. The sha256 prefix names the exact file
# the claim was made against; a different file re-opens the question, which is why
# `verify_spec` is public and cheap to re-run.
#
# VERIFIED here means: every mapped glyph exists and is non-empty; white and black share
# a silhouette; the six white pieces are six distinct shapes; the dark-square glyph
# carries more ink than the light-square one; and a human looked at the rendered pieces
# and saw a pawn where the table promised a pawn.
_VERIFICATION_RECORD: dict[str, tuple[Confidence, str | None]] = {
    "unicode": (Confidence.VERIFIED, "58e770f0690df91f"),
    "merida": (Confidence.VERIFIED, "9a55747c13bb4d70"),
    "alpha": (Confidence.VERIFIED, "f2aba3d221667d80"),
    "cases": (Confidence.VERIFIED, "d8c43026135377c5"),
    "berlin": (Confidence.UNVERIFIED, None),
    "leipzig": (Confidence.VERIFIED, "84b0cd332b3aef22"),
    "marroquin": (Confidence.VERIFIED, "7bdbaf0147a448d3"),
    "condal": (Confidence.VERIFIED, "fafb9695a2c1e0b1"),
    "lucena": (Confidence.VERIFIED, "7643d5621da797c6"),
    "maya": (Confidence.VERIFIED, "b05a332e6699b826"),
    "utrecht": (Confidence.UNVERIFIED, "0d49f0ac2774a0da"),
    "kingdom": (Confidence.VERIFIED, "a2b23f7e71ba05da"),
    "mediaeval": (Confidence.VERIFIED, "f0ac3423a5d23422"),
    "motif": (Confidence.VERIFIED, "44f329ab7f190543"),
    "harlequin": (Confidence.VERIFIED, "ccd43c8f3216bdcc"),
    "alfonso": (Confidence.VERIFIED, "69765f975470b704"),
    "magnetic": (Confidence.VERIFIED, "8a952f7f68e1c7d4"),
    "millennia": (Confidence.UNVERIFIED, None),
    "adventurer": (Confidence.VERIFIED, "e4d7336f6da0817e"),
    "line": (Confidence.VERIFIED, "d7b3ffeaaf5e2126"),
    "regular": (Confidence.VERIFIED, "f571f28ceffda5d7"),
    "diagramttf": (Confidence.UNVERIFIED, "5885351b790801b2"),
    "zurich": (Confidence.UNVERIFIED, "265523aa2d37b133"),
    "linares": (Confidence.UNVERIFIED, "a5bbebc98d4f027b"),
}

for _key, (_conf, _sha) in _VERIFICATION_RECORD.items():
    _spec = CHESS_FONT_SPECS.get(_key)
    if _spec is not None:
        CHESS_FONT_SPECS[_key] = replace(_spec, confidence=_conf, verified_sha256=_sha)
del _key, _conf, _sha, _spec


def verified_specs() -> list[ChessFontSpec]:
    """Families that are both installed and VERIFIED. What a renderer should offer."""
    return [
        spec
        for spec in CHESS_FONT_SPECS.values()
        if spec.confidence is Confidence.VERIFIED and find_font_file(spec) is not None
    ]


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def search_paths() -> list[Path]:
    """Where to look for chess fonts, most specific first.

    ``CAISSA_FONT_PATH`` (os.pathsep-separated) wins, so a packaged build can ship its
    own fonts and a user can point at a private collection without installing anything.
    """
    paths: list[Path] = []
    env = os.environ.get("CAISSA_FONT_PATH", "").strip()
    if env:
        paths.extend(Path(p) for p in env.split(os.pathsep) if p.strip())

    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "assets" / "fonts"
        if cand.is_dir():
            paths.append(cand)
        if (parent / "pyproject.toml").exists():
            break

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            paths.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
        windir = os.environ.get("WINDIR", r"C:\Windows")
        paths.append(Path(windir) / "Fonts")
    else:
        paths.extend(
            [
                Path.home() / ".local" / "share" / "fonts",
                Path.home() / ".fonts",
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library" / "Fonts",
            ]
        )
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def find_font_file(spec: ChessFontSpec) -> Path | None:
    """First existing file for ``spec``, or None. Case-insensitive on every platform."""
    wanted = {n.lower() for n in spec.file_names}
    for root in search_paths():
        if not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        # Exact (case-folded) name match first, in the order the spec lists them.
        by_lower = {e.name.lower(): e for e in entries if e.is_file()}
        for name in spec.file_names:
            hit = by_lower.get(name.lower())
            if hit is not None:
                return hit
        del wanted
        wanted = {n.lower() for n in spec.file_names}
    return None


def available_specs(*, require_file: bool = True) -> list[ChessFontSpec]:
    """Specs whose font file is present, in registry order."""
    out = []
    for spec in CHESS_FONT_SPECS.values():
        if not require_file or find_font_file(spec) is not None:
            out.append(spec)
    return out


def get_spec(key: str) -> ChessFontSpec:
    try:
        return CHESS_FONT_SPECS[key]
    except KeyError:
        raise KeyError(
            f"Familia de fonte desconhecida: {key!r}. "
            f"Disponiveis: {', '.join(sorted(CHESS_FONT_SPECS))}"
        ) from None


# --------------------------------------------------------------------------- #
# Character -> glyph resolution
# --------------------------------------------------------------------------- #
class CharacterResolver:
    """Maps a character to a glyph name across every cmap flavour a chess font uses.

    Legacy chess fonts are encoded three different ways in the wild and a renderer that
    handles only one of them silently draws nothing:

    * ``(3, 1)`` Windows Unicode -- ASCII maps straight through. Chess Alpha, Cases.
    * ``(3, 0)`` Windows Symbol  -- ASCII lives at ``U+F000 + code``. The installed
      Chess Merida TTF is symbol-only, which is exactly why Pillow renders it blank.
    * ``(1, 0)`` Macintosh Roman -- the original 1990s encoding; still the only table in
      some files.

    Order matters: Unicode first (it is the authoritative one when present), then the
    symbol plane, then Mac Roman.
    """

    def __init__(self, ttfont) -> None:  # noqa: ANN001 - fontTools TTFont
        self._tables: list[tuple[tuple[int, int], dict[int, str]]] = []
        for table in ttfont["cmap"].tables:
            key = (table.platformID, table.platEncID)
            self._tables.append((key, dict(table.cmap)))
        # (3,1)/(0,x) Unicode, then (3,0) symbol, then (1,0) Mac.
        def rank(item: tuple[tuple[int, int], dict[int, str]]) -> int:
            pid, eid = item[0]
            if pid == 3 and eid in (1, 10):
                return 0
            if pid == 0:
                return 1
            if pid == 3 and eid == 0:
                return 2
            if pid == 1:
                return 3
            return 4

        self._tables.sort(key=rank)

    def glyph_name(self, char: str) -> str | None:
        code = ord(char)
        candidates = [code]
        if code < 0x100:
            candidates.append(0xF000 + code)
        for (pid, eid), table in self._tables:
            for cand in candidates:
                # A symbol cmap only ever holds the F0xx plane; asking it for plain
                # ASCII is how the blank-board bug happens.
                if pid == 3 and eid == 0 and cand < 0xF000 and 0xF000 + code in table:
                    return table[0xF000 + code]
                name = table.get(cand)
                if name is not None:
                    return name
        return None


@dataclass
class LoadedFont:
    """An opened chess font plus its resolved glyph access."""

    spec: ChessFontSpec
    path: Path
    units_per_em: float
    _ttfont: object = field(repr=False, default=None)
    _resolver: CharacterResolver = field(repr=False, default=None)
    _glyphset: object = field(repr=False, default=None)
    _cache: dict[str, Outline] = field(repr=False, default_factory=dict)

    def has_char(self, char: str) -> bool:
        return self._resolver.glyph_name(char) is not None

    def glyph_name(self, char: str) -> str | None:
        return self._resolver.glyph_name(char)

    def outline(self, char: str) -> Outline:
        """Outline for ``char``; an empty Outline when the font has no such glyph."""
        cached = self._cache.get(char)
        if cached is not None:
            return cached
        name = self._resolver.glyph_name(char)
        if name is None or name not in self._glyphset:
            result = Outline(contours=(), advance=0.0, units_per_em=self.units_per_em)
        else:
            from fontTools.pens.transformPen import TransformPen  # noqa: F401  (kept for parity)

            glyph = self._glyphset[name]
            builder = PathBuilder()
            try:
                # Composites must be decomposed so that a component-built piece still
                # yields real contours rather than an addComponent call we drop.
                from fontTools.pens.recordingPen import DecomposingRecordingPen

                rec = DecomposingRecordingPen(self._glyphset)
                glyph.draw(rec)
                rec.replay(builder)
            except Exception:
                try:
                    glyph.draw(builder)
                except Exception:
                    pass
            result = outline_from_pen(
                builder, advance=getattr(glyph, "width", 0.0) or 0.0, units_per_em=self.units_per_em
            )
        self._cache[char] = result
        return result

    def piece_outline(self, piece: str) -> Outline:
        """The bare-piece artwork for a FEN piece letter."""
        return self.outline(self.spec.artwork_char(piece))

    def ascender(self) -> float:
        try:
            return float(self._ttfont["hhea"].ascender)
        except Exception:
            return self.units_per_em * 0.8

    def descender(self) -> float:
        try:
            return float(self._ttfont["hhea"].descender)
        except Exception:
            return -self.units_per_em * 0.2

    def cap_height(self) -> float:
        """Cap height from OS/2 when the font declares a usable one.

        Many legacy chess fonts leave ``sCapHeight`` at 0, so a measured fallback --
        the height of the letter 'H', then 0.7 em -- keeps optical sizing sane.
        """
        try:
            os2 = self._ttfont["OS/2"]
            value = float(getattr(os2, "sCapHeight", 0) or 0)
            if value > 0:
                return value
        except Exception:
            pass
        h = self.outline("H")
        if not h.is_empty():
            _, y0, _, y1 = h.bbox()
            if y1 > y0:
                return y1
        return self.units_per_em * 0.7

    def x_height(self) -> float:
        try:
            os2 = self._ttfont["OS/2"]
            value = float(getattr(os2, "sxHeight", 0) or 0)
            if value > 0:
                return value
        except Exception:
            pass
        x = self.outline("x")
        if not x.is_empty():
            _, y0, _, y1 = x.bbox()
            if y1 > y0:
                return y1
        return self.units_per_em * 0.5


@lru_cache(maxsize=32)
def _open_ttfont(path_str: str):  # noqa: ANN201
    """Open a font file, holding the BYTES rather than the file handle.

    `TTFont(path)` keeps the descriptor open for as long as the object lives, and this
    cache is process-lifetime, so running the suite left two dozen files open and printed
    a `ResourceWarning` for each one at interpreter shutdown (cycle-1 report §7.3 nº 16).
    Reading the file once into memory costs 50 to 200 kB per family and closes the
    handle immediately; `lazy=True` still defers the table parsing.
    """
    import io

    from fontTools.ttLib import TTFont

    return TTFont(io.BytesIO(Path(path_str).read_bytes()), fontNumber=0, lazy=True)


def load_font(spec_or_key: ChessFontSpec | str, *, path: Path | None = None) -> LoadedFont:
    """Open a family's font file and prepare glyph access.

    Raises :class:`FontNotFoundError` with the paths that were searched -- a message the
    user can act on, per the error-quality rule in the critic charter.
    """
    spec = get_spec(spec_or_key) if isinstance(spec_or_key, str) else spec_or_key
    font_path = path or find_font_file(spec)
    if font_path is None:
        searched = "\n  ".join(str(p) for p in search_paths())
        raise FontNotFoundError(
            f"Fonte da familia {spec.family!r} nao encontrada.\n"
            f"Arquivos aceitos: {', '.join(spec.file_names)}\n"
            f"Procurado em:\n  {searched}\n"
            f"Defina CAISSA_FONT_PATH para apontar uma pasta com a fonte."
        )
    try:
        ttfont = _open_ttfont(str(font_path))
        upem = float(ttfont["head"].unitsPerEm)
        resolver = CharacterResolver(ttfont)
        glyphset = ttfont.getGlyphSet()
    except FontUnreadableError:
        raise
    except Exception as exc:
        raise FontUnreadableError(
            f"Arquivo de fonte ilegivel para {spec.family!r}: {font_path}\n"
            f"Causa: {type(exc).__name__}: {exc}\n"
            f"A familia foi ignorada. Substitua o arquivo ou aponte outro por "
            f"CAISSA_FONT_PATH."
        ) from exc
    return LoadedFont(
        spec=spec,
        path=Path(font_path),
        units_per_em=upem,
        _ttfont=ttfont,
        _resolver=resolver,
        _glyphset=glyphset,
    )


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
# Thresholds, calibrated against every chess font installed on the reference machine
# (2026-09-07). The measured gap is wide, which is what makes the check worth having:
#   correct pairings   0.883 .. 1.000   (Chess Regular is the low one; its black pawn is
#                                        drawn slightly smaller than its white pawn)
#   wrong pairings     0.000 .. 0.770   (Chess Alpha with the Marroquin table, Utrecht,
#                                        DiagramTTF, the PDF-subset Zurich and Linares)
# Anything in the empty band between 0.77 and 0.88 would be genuinely ambiguous, and
# none of the twenty-odd files tested landed there.
_PAIRING_MIN = 0.85

# The pawn may be *as* tall as the tallest piece -- several designs top every piece out
# at the same height -- but not meaningfully taller. See invariant (4).
_PAWN_HEIGHT_MARGIN = 1.05

# Three or more broken pairings is not an incomplete font, it is a wrong table.
_WRONG_TABLE_PAIRS = 3


@dataclass
class VerificationResult:
    key: str
    path: Path | None
    confidence: Confidence
    sha256: str | None
    problems: list[str] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.confidence is Confidence.VERIFIED


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_similarity(a: Outline, b: Outline) -> float:
    """Overlap of two glyph bounding boxes, 0..1. Cheap, and enough for pairing."""
    if a.is_empty() or b.is_empty():
        return 0.0
    ax0, ay0, ax1, ay1 = a.bbox()
    bx0, by0, bx1, by1 = b.bbox()
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / union if union > 0 else 0.0


def verify_spec(spec: ChessFontSpec, *, path: Path | None = None) -> VerificationResult:
    """Check a mapping against a real font file. Structural, not cosmetic.

    Invariants, each of which a wrong table breaks:

    1. **Every mapped character exists** and has a non-empty outline. A table that
       points at a blank glyph produces an invisible piece.
    2. **White and black share a silhouette.** Chess fonts draw one outline per piece
       and fill it differently, so ``light['P']`` and ``light['p']`` must have nearly
       the same bounding box. This is what catches a mis-paired letter.
    3. **The six white pieces are all different shapes.** A table that sends two pieces
       to the same character -- the commonest way to get one wrong -- makes two glyphs
       identical, and comparing their path data catches it outright.
    4. **The pawn is not the tallest piece.** Deliberately weak. An earlier version of
       this check required the pawn to have the *smallest bounding box*, and it wrongly
       failed Chess Marroquin, Maya, Alfonso-X and Adventurer, whose pieces all stand on
       one shared pedestal of identical width. Height alone survives that design.
    5. **The dark-square glyph is bigger than the light-square glyph**, because it
       carries the square background as well as the piece.

    None of these needs a human to look at the board, and together they are strong: a
    table with two letters swapped fails (2) or (3), a table off by one fails (3).

    What they do NOT establish is that the piece called a knight *looks* like a knight;
    only an eye can settle that. The families marked VERIFIED in this registry were also
    inspected as rendered contact sheets on 2026-09-07.
    """
    result = VerificationResult(key=spec.key, path=None, confidence=Confidence.UNVERIFIED, sha256=None)
    try:
        font = load_font(spec, path=path)
    except (FontNotFoundError, FontUnreadableError) as exc:
        result.problems.append(str(exc).splitlines()[0])
        return result
    result.path = font.path
    result.sha256 = _sha256(font.path)

    if spec.model is FontModel.UNICODE:
        missing = [p for p in PIECES if font.outline(UNICODE_PIECES[p]).is_empty()]
        if missing:
            result.problems.append(f"sem glifo Unicode para: {' '.join(missing)}")
            result.confidence = Confidence.PARTIAL if len(missing) < len(PIECES) else Confidence.UNVERIFIED
        else:
            result.confidence = Confidence.VERIFIED
        return result

    # (1) presence
    empty_light: list[str] = []
    empty_dark: list[str] = []
    for piece in PIECES:
        if not spec.light or not spec.dark:
            result.problems.append("tabela de mapeamento vazia")
            return result
        if font.outline(spec.light[piece]).is_empty():
            empty_light.append(f"{piece}->{spec.light[piece]!r}")
        if font.outline(spec.dark[piece]).is_empty():
            empty_dark.append(f"{piece}->{spec.dark[piece]!r}")
    if empty_light:
        result.problems.append(f"glifo de casa clara vazio: {', '.join(empty_light)}")
    if empty_dark:
        result.problems.append(f"glifo de casa escura vazio: {', '.join(empty_dark)}")

    # (2) white/black silhouette pairing
    pairings: dict[str, float] = {}
    for white, black in (("P", "p"), ("N", "n"), ("B", "b"), ("R", "r"), ("Q", "q"), ("K", "k")):
        sim = _bbox_similarity(font.piece_outline(white), font.piece_outline(black))
        pairings[white] = sim
        if sim < _PAIRING_MIN:
            result.problems.append(
                f"silhuetas de {white} e {black} nao batem "
                f"(IoU de caixa {sim:.3f} < {_PAIRING_MIN:.2f})"
            )
    result.details["pairing"] = pairings
    bad_pairs = sum(1 for v in pairings.values() if v < _PAIRING_MIN)

    # (3) the six white pieces must be six different shapes
    shapes: dict[str, str] = {}
    for piece in ("P", "N", "B", "R", "Q", "K"):
        o = font.piece_outline(piece)
        if o.is_empty():
            continue
        shapes[piece] = o.to_svg_path(scale=1.0)
    seen: dict[str, str] = {}
    for piece, path in shapes.items():
        twin = seen.get(path)
        if twin is not None:
            result.problems.append(
                f"{piece!r} e {twin!r} desenham o MESMO glifo "
                f"({spec.light.get(piece)!r} e {spec.light.get(twin)!r}): tabela errada"
            )
        else:
            seen[path] = piece

    # (4) height ordering, weak on purpose -- see the docstring
    heights: dict[str, float] = {}
    for piece in ("P", "N", "B", "R", "Q", "K"):
        o = font.piece_outline(piece)
        if o.is_empty():
            continue
        _, y0, _, y1 = o.bbox()
        heights[piece] = y1 - y0
    result.details["heights"] = heights
    if len(heights) >= 4:
        others = [v for k, v in heights.items() if k != "P"]
        if others and heights.get("P", 0.0) > max(others) * _PAWN_HEIGHT_MARGIN:
            result.problems.append(
                f"o peao e a peca mais alta com folga (alturas: "
                f"{', '.join(f'{k}={v:.0f}' for k, v in heights.items())}): tabela suspeita"
            )

    # (4) the dark-square glyph carries the square, so it must cover more area
    thin: list[str] = []
    for piece in PIECES:
        light = font.outline(spec.light[piece])
        dark = font.outline(spec.dark[piece])
        if light.is_empty() or dark.is_empty():
            continue
        lx0, ly0, lx1, ly1 = light.bbox()
        dx0, dy0, dx1, dy1 = dark.bbox()
        if (dx1 - dx0) * (dy1 - dy0) <= (lx1 - lx0) * (ly1 - ly0) * 1.02:
            thin.append(piece)
    if len(thin) > len(PIECES) // 2:
        result.problems.append(
            "os glifos de casa escura nao sao maiores que os de casa clara "
            f"({len(thin)}/{len(PIECES)}): o par claro/escuro pode estar trocado"
        )

    if not result.problems:
        result.confidence = Confidence.VERIFIED
    elif len(empty_light) + len(empty_dark) >= len(PIECES) or bad_pairs >= _WRONG_TABLE_PAIRS:
        # Not a font that happens to be incomplete -- a table that is simply wrong for
        # this file. Callers must treat it as unusable, not as "mostly fine".
        result.confidence = Confidence.UNVERIFIED
    else:
        result.confidence = Confidence.PARTIAL
    return result


def verify_all() -> list[VerificationResult]:
    return [verify_spec(spec) for spec in CHESS_FONT_SPECS.values()]


# --------------------------------------------------------------------------- #
# Subsetting
# --------------------------------------------------------------------------- #
SUBSET_EPOCH: int = 0x7C259DC0
"""Fixed `head` timestamp for every font this module writes: 2 082 844 800.

OpenType counts `head.created` / `head.modified` in seconds since 1904-01-01, so this
constant is exactly **1970-01-01 00:00:00 UTC** -- the Unix epoch expressed in the font
epoch. Two reasons for that particular instant and not, say, zero:

* fontTools warns ``'modified' timestamp seems very low; regarding as unix timestamp``
  for anything **strictly below** `0x7C259DC0` and then silently adds `0x7C259DC0` to
  it. Pinning to zero would therefore round-trip to this value anyway, with a warning
  on every read -- and this project turns warnings into errors.
* It is the same instant every other reproducible-build convention uses, so a reader
  who inspects the subset sees an obviously synthetic date rather than a plausible one.
"""


def pin_font_timestamp(
    ttfont,  # noqa: ANN001
    *,
    when: int = SUBSET_EPOCH,
    pin_created: bool = False,
) -> None:
    """Pin a `TTFont`'s `head.modified` so saving it twice gives the same bytes.

    Without this, `TTFont.save` stamps `head.modified` with `timestampNow()` -- see
    `fontTools.ttLib.tables._h_e_a_d.table__h_e_a_d.compile`, guarded by the
    `recalcTimestamp=True` that `TTFont.__init__` defaults to. Two subsets of the same
    font, taken in different seconds, then differ in **three bytes**: one in
    `head.modified` and two in the `checkSumAdjustment` that covers it. Measured on
    `ChessMerida.ttf`: offsets 67, 183 and 207, each moving by +-1.

    That is a real cost, not a cosmetic one. It makes `test_subset_is_deterministic` a
    coin toss (cycle-10 critique: one failure in twelve isolated runs, and the whole
    suite red in one run of three), and it means no artefact that embeds a subset can be
    compared by hash. Every other artefact this front ships is byte-reproducible; a font
    subset has no business being the exception.

    `recalcTimestamp = False` alone would only stop the clock from being *read*; the
    subset would still inherit whatever `head.modified` the source file happens to
    carry, and several of the chess families here are 1990s fonts whose stamps fontTools
    has to repair on load. Pinning removes both sources of drift at once.

    `head.created` is left alone by default, and that is a measurement and not an
    assumption: fontTools only ever recalculates `modified` (`compile` above touches
    nothing else), and `decompile` repairs a bogus `created` deterministically from the
    file's own bytes, so it does not drift between two calls a second apart. Verified --
    `test_subset_pins_the_modification_stamp_and_leaves_created_alone` reads both fields
    out of the emitted subset. `pin_created=True` is there for a caller that wants the
    subset to carry no date from the source at all.

    Callers outside this module -- `caissa/export/pdfwrite.py::_subset_font` has exactly
    the same flaw, and is owned by another front -- get the fix in one line by calling
    this before `save()`.
    """
    head = ttfont.get("head") if hasattr(ttfont, "get") else None
    if head is None:
        return
    head.modified = when
    if pin_created:
        head.created = when
    ttfont.recalcTimestamp = False


def woff2_available() -> bool:
    """Public alias: whether `subset_font(..., flavor="woff2")` can succeed."""
    return _brotli_available()


def _brotli_available() -> bool:
    """Can fontTools actually write WOFF2 here?

    WOFF2 is Brotli-compressed, and fontTools does not vendor the compressor: it comes
    from the ``fonttools[woff]`` extra. Without it every EPUB and HTML export that asks
    for the default flavour dies deep inside the library.
    """
    import importlib.util

    return any(
        importlib.util.find_spec(name) is not None
        for name in ("brotli", "brotlicffi")
    )


def subset_font(
    spec_or_key: ChessFontSpec | str,
    characters: Iterable[str],
    *,
    path: Path | None = None,
    synthesize_unicode_cmap: bool = True,
    flavor: str | None = "woff2",
) -> bytes:
    """Subset a chess font to ``characters`` for embedding in EPUB/HTML/PDF.

    ``synthesize_unicode_cmap`` is the part that matters and the part every naive
    implementation misses. A legacy chess font may carry only a ``(3, 0)`` symbol cmap;
    embed that in an EPUB and the reader maps nothing, because it looks up ``U+0070``
    and the font only answers to ``U+F070``. So a ``(3, 1)`` table is built that maps
    the plain ASCII codepoints onto the same glyphs.

    Origem da ideia: PDFimport/fontembed.py §2.10 (reconstrucao de cmap), aplicada na
    direcao oposta -- exportacao em vez de importacao.
    """
    from fontTools import subset as ft_subset
    from fontTools.ttLib import TTFont

    spec = get_spec(spec_or_key) if isinstance(spec_or_key, str) else spec_or_key
    font_path = path or find_font_file(spec)
    if font_path is None:
        raise FontNotFoundError(f"Fonte {spec.family!r} nao encontrada para subconjunto.")

    wanted = list(dict.fromkeys(characters))
    if not wanted:
        raise ValueError("Nenhum caractere pedido para o subconjunto.")

    # Resolve to glyph names with the same rules the renderer uses, so the subset keeps
    # exactly what will actually be drawn.
    # `recalcTimestamp=False` here and `pin_font_timestamp` below: without both, `save()`
    # writes the wall clock into `head.modified` and the subset changes every second.
    source = TTFont(str(font_path), fontNumber=0, recalcTimestamp=False)
    resolver = CharacterResolver(source)
    glyph_names: list[str] = []
    ascii_map: dict[int, str] = {}
    for ch in wanted:
        name = resolver.glyph_name(ch)
        if name is None:
            continue
        glyph_names.append(name)
        ascii_map[ord(ch)] = name
    if not glyph_names:
        raise ValueError(
            f"Nenhum dos caracteres pedidos existe em {spec.family!r}: {''.join(wanted)!r}"
        )

    options = ft_subset.Options()
    options.set(layout_features=[], name_IDs=["*"], name_legacy=True, notdef_outline=True)
    options.drop_tables += ["FFTM"]
    options.recalc_bounds = True
    subsetter = ft_subset.Subsetter(options=options)
    subsetter.populate(glyphs=glyph_names)
    subsetter.subset(source)

    if synthesize_unicode_cmap:
        _install_unicode_cmap(source, ascii_map)

    if flavor:
        # Setting `.flavor` succeeds; it is `save()` that needs the compressor, and it
        # raises `ImportError("No module named brotli")` from inside fontTools with no
        # hint that the fix is an extra. Check up front and say what to install.
        if flavor == "woff2" and not _brotli_available():
            raise FontUnreadableError(
                "WOFF2 pedido, mas o compressor Brotli nao esta instalado, entao "
                "fontTools nao consegue gravar o arquivo.\n"
                "  Instale:  pip install 'fonttools[woff]'   (ou 'pip install brotli')\n"
                "  Ou peca TrueType sem compressao:  subset_font(..., flavor=None)"
            )
        try:
            source.flavor = flavor
        except Exception:
            source.flavor = None

    import io

    pin_font_timestamp(source)
    buf = io.BytesIO()
    source.save(buf)
    return buf.getvalue()


def _install_unicode_cmap(ttfont, ascii_map: dict[int, str]) -> None:  # noqa: ANN001
    """Add or replace a ``(3, 1)`` cmap so plain ASCII reaches the piece glyphs."""
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    cmap = ttfont["cmap"]
    kept = [t for t in cmap.tables if not (t.platformID == 3 and t.platEncID == 1)]
    merged: dict[int, str] = {}
    for table in cmap.tables:
        if table.platformID == 3 and table.platEncID == 1:
            merged.update(table.cmap)
    merged.update(ascii_map)

    sub = CmapSubtable.newSubtable(4)
    sub.platformID = 3
    sub.platEncID = 1
    sub.language = 0
    sub.cmap = merged
    cmap.tables = kept + [sub]
    cmap.tableVersion = 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv: Sequence[str]) -> int:
    # Several of the chess fonts on this machine are from the 1990s and carry a
    # `head.created` outside the range fontTools expects. fontTools reports it through
    # `logging`, once per file, and it buried the verification table under ~48 lines of
    # noise (cycle-1 critique, defeito nao bloqueante nº 11). Silenced for exactly the
    # one logger that emits it, and only in the CLI -- a library caller still sees it.
    logging.getLogger("fontTools.ttLib.tables._h_e_a_d").setLevel(logging.ERROR)
    for message in (r".*timestamp.*out of range.*", r".*timestamp seems very low.*"):
        warnings.filterwarnings("ignore", message=message)

    if "--verify" in argv or not argv:
        rows = verify_all()
        width = max(len(r.key) for r in rows)
        for r in rows:
            where = r.path.name if r.path else "(sem arquivo)"
            print(f"{r.key:<{width}}  {r.confidence.value:<10}  {where}")
            for problem in r.problems:
                print(f"{'':<{width}}    - {problem}")
        return 0
    if "--emit-verification" in argv:
        for r in verify_all():
            sha = f'"{r.sha256[:16]}"' if r.sha256 else "None"
            print(f'    "{r.key}": (Confidence.{r.confidence.name}, {sha}),')
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
